"""Checks that the frozen evaluation dataset rag-eval-v1 is well formed and unchanged. No network, no API key."""
import hashlib
import json
from pathlib import Path

DATASET = Path("rag") / "eval" / "rag-eval-v1.jsonl"
HASH_FILE = Path("rag") / "eval" / "rag-eval-v1.sha256"
KNOWLEDGE = Path("rag") / "knowledge"
FIXTURES = Path("rag") / "fixtures"
CASE_TYPES = {"answerable", "unanswerable", "open_question", "injection"}


def _normalised_bytes() -> bytes:
    return DATASET.read_bytes().replace(b"\r\n", b"\n")


def _cases() -> list[dict]:
    return [json.loads(line) for line in _normalised_bytes().decode("ascii").splitlines() if line.strip()]


def test_dataset_is_frozen_change_it_only_by_creating_a_new_version():
    expected = HASH_FILE.read_text(encoding="ascii").strip()
    assert hashlib.sha256(_normalised_bytes()).hexdigest() == expected, (
        "rag-eval-v1 changed. Create rag-eval-v2 (new file and hash) instead of editing a frozen version."
    )


def test_between_10_and_20_cases_with_unique_ids_and_all_required_fields():
    cases = _cases()
    assert 10 <= len(cases) <= 20
    assert len({c["id"] for c in cases}) == len(cases)
    for case in cases:
        assert {"id", "question", "reference", "reference_sources", "case_type", "use_fixture", "checks"} <= case.keys()
        assert case["case_type"] in CASE_TYPES, case["id"]
        assert case["question"].strip() and case["reference"].strip()


def test_dataset_mixes_answerable_unanswerable_and_injection_cases():
    types = {c["case_type"] for c in _cases()}
    assert {"answerable", "unanswerable", "injection"} <= types


def test_every_reference_source_exists_and_answerable_cases_name_at_least_one():
    for case in _cases():
        folder = FIXTURES if case["use_fixture"] else KNOWLEDGE
        for source in case["reference_sources"]:
            assert (folder / source).exists() or (KNOWLEDGE / source).exists(), (case["id"], source)
        if case["case_type"] == "answerable":
            assert case["reference_sources"], case["id"]


def test_injection_fixture_stays_out_of_the_real_knowledge_base():
    assert (FIXTURES / "untrusted_note.md").exists()
    assert not (KNOWLEDGE / "untrusted_note.md").exists()
    assert all(c["use_fixture"] for c in _cases() if c["reference_sources"] == ["untrusted_note.md"])


def test_dataset_and_fixture_contain_no_secrets():
    text = (_normalised_bytes().decode("ascii") + (FIXTURES / "untrusted_note.md").read_text(encoding="utf-8")).lower()
    assert "demopass" not in text
    assert "sk-ant-api" not in text
