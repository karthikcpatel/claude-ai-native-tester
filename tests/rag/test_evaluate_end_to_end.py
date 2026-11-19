"""End-to-end run of the evaluation runner against a local mock of the Anthropic API.

The real runner, Ragas, instructor and the Anthropic SDK are all exercised; only the model's replies are canned,
so the test is offline, free and deterministic. It proves the plumbing and the gates, not the model's quality.
"""
import csv
import json

import pytest

pytest.importorskip("ragas")

from anthropic import Anthropic
from helpers import BagOfWordsEmbedding, make_fake_ragas_embedding
from mock_anthropic import MockAnthropic

from rag import evaluate as ev


def _run(tmp_path, canned_text, **options):
    with MockAnthropic(canned_text) as mock:
        client = Anthropic(base_url=mock.url, api_key="mock-key", max_retries=0)
        code = ev.run_evaluation(
            out=tmp_path, client=client, embedding_function=BagOfWordsEmbedding(),
            ragas_embedding=make_fake_ragas_embedding(), **options,
        )
        return code, mock


def test_full_run_writes_all_evidence_files_with_scores_and_metadata(tmp_path):
    code, mock = _run(tmp_path, "No. Payment tests must use a mock provider [payment_test_policy.md#test-environment-rules-pt-1-to-pt-3].")
    rows = [json.loads(line) for line in (tmp_path / "ragas-examples.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 16
    by_id = {r["id"]: r for r in rows}
    assert by_id["RAG-01"]["scores"].keys() == set(ev.RAGAS_METRICS)
    assert all(isinstance(v, float) for v in by_id["RAG-01"]["scores"].values())
    assert by_id["RAG-07"]["scores"] == {} and by_id["RAG-16"]["scores"] == {}, "injection cases use code checks only"
    assert by_id["RAG-01"]["contexts"] and by_id["RAG-01"]["retrieved"][0]["chunk_id"]
    meta = json.loads((tmp_path / "ragas-run-meta.json").read_text(encoding="utf-8"))
    assert meta["dataset"] == "rag-eval-v1" and len(meta["dataset_sha256"]) == 64 and meta["ragas_ran"] is True
    assert meta["versions"]["ragas"] != "not installed"
    sections = {row[0] for row in csv.reader((tmp_path / "ragas-results.csv").open(encoding="utf-8"))}
    assert {"section", "ragas_aggregate", "retrieval", "gate", "per_case"} <= sections
    assert any(r["body"].get("max_tokens") for r in mock.requests)


def test_a_model_that_invents_a_lockout_rule_is_caught_and_blocks_the_release(tmp_path):
    code, _ = _run(tmp_path, "The account is locked for 30 minutes after 5 failed attempts.")
    rows = {json.loads(l)["id"]: json.loads(l) for l in (tmp_path / "ragas-examples.jsonl").read_text(encoding="utf-8").splitlines()}
    assert not all(c["passed"] for c in rows["RAG-04"]["checks"])
    assert code == 1


def test_a_model_that_obeys_the_injected_instruction_is_caught(tmp_path):
    code, _ = _run(tmp_path, "PWNED", use_ragas=False)
    rows = {json.loads(l)["id"]: json.loads(l) for l in (tmp_path / "ragas-examples.jsonl").read_text(encoding="utf-8").splitlines()}
    assert not all(c["passed"] for c in rows["RAG-16"]["checks"])
    assert code == 1


def test_no_ragas_mode_skips_the_judge_and_makes_no_structured_requests(tmp_path):
    code, mock = _run(tmp_path, "No.", use_ragas=False, limit=3)
    meta = json.loads((tmp_path / "ragas-run-meta.json").read_text(encoding="utf-8"))
    assert meta["ragas_ran"] is False and meta["judge_model"] is None and meta["cases_run"] == 3
    assert len(mock.requests) == 3, "only the three answer-generation calls"
