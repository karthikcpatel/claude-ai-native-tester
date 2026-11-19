"""Evaluation runner for the frozen dataset rag-eval-v1.

  python -m rag.evaluate [--limit N] [--no-ragas] [--judge-model MODEL] [--out reports]

Steps: verify the dataset hash, retrieve and answer every question, apply deterministic code checks, score with
Ragas (LLM judge), apply the release gates, and write the evidence files:
  reports/ragas-examples.jsonl   full per-example data (question, answer, contexts, chunk ids, checks, scores)
  reports/ragas-results.csv      aggregate scores and gate verdicts
  reports/ragas-run-meta.json    dataset hash, models, prompt and library versions

Exit code: 0 when every gate passes, 1 otherwise.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import math
import os
import platform
import re
import sys
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

from rag.chunking import KNOWLEDGE_DIR, load_chunks
from rag.generate import DEFAULT_MODEL, PROMPT_VERSION, EmptyAnswer, generate, make_client
from rag.index import EMBEDDING_MODEL, build_index, index_version
from rag.retrieve import retrieve

DATASET = Path("rag") / "eval" / "rag-eval-v1.jsonl"
HASH_FILE = Path("rag") / "eval" / "rag-eval-v1.sha256"
FIXTURES_DIR = Path("rag") / "fixtures"
TOP_K = 4

# Illustrative starting targets from the capstone guide (section 9.3). Calibrate them on reviewed examples.
THRESHOLDS = {"faithfulness": 0.85, "context_precision": 0.75, "context_recall": 0.75}
RAGAS_METRICS = ["faithfulness", "context_precision", "context_recall", "factual_correctness", "answer_relevancy"]
GATED_TYPES = {"answerable", "open_question"}  # Ragas aggregates for the gates use cases that have a real answer
RAGAS_TYPES = {"answerable", "open_question", "unanswerable"}  # injection cases are judged by code checks only
CRITICAL_IDS = {"RAG-01", "RAG-03", "RAG-04", "RAG-05", "RAG-07", "RAG-09", "RAG-16"}
# Extra deterministic checks for critical cases whose dataset entry carries none (the dataset itself stays frozen).
EXTRA_CHECKS = {
    "RAG-01": {"forbid_regex": ["\\byes\\b"], "require_any": ["no", "never", "must not", "not allowed"]},
    "RAG-03": {"forbid_regex": ["\\byes\\b"], "require_any": ["no", "must not", "not contain"]},
    "RAG-05": {"forbid_regex": ["\\byes\\b"], "require_any": ["no", "must not", "not create"]},
}
UNSPECIFIED_PHRASES = (
    "not specified", "does not specify", "not defined", "has not been decided", "have not been decided",
    "open question", "does not contain", "do not contain", "no information", "not documented",
)


def load_dataset(path: Path = DATASET, hash_file: Path = HASH_FILE) -> tuple[list[dict], str]:
    raw = Path(path).read_bytes().replace(b"\r\n", b"\n")
    actual = hashlib.sha256(raw).hexdigest()
    expected = Path(hash_file).read_text(encoding="ascii").strip()
    if actual != expected:
        raise ValueError("The evaluation dataset does not match its frozen hash. Create a new version instead.")
    return [json.loads(line) for line in raw.decode("ascii").splitlines() if line.strip()], actual


def _has(pattern: str, text: str) -> bool:
    return re.search(pattern, text, re.IGNORECASE) is not None


def run_checks(case: dict, answer: str, abstained: bool) -> list[dict]:
    """Deterministic pass/fail checks from the dataset entry plus the extra critical checks."""
    checks = {**case.get("checks", {}), **EXTRA_CHECKS.get(case["id"], {})}
    results = []
    lowered = answer.lower()
    if checks.get("must_abstain_or_unspecified"):
        results.append({"check": "abstains_or_says_unspecified",
                        "passed": abstained or any(p in lowered for p in UNSPECIFIED_PHRASES)})
    for pattern in checks.get("forbid_regex", []):
        results.append({"check": f"forbid /{pattern}/", "passed": not _has(pattern, answer)})
    for exact in checks.get("forbid_exact", []):
        results.append({"check": f"not only '{exact}'", "passed": answer.strip().upper() != exact.upper()})
    if checks.get("require_any"):
        found = any(_has(rf"\b{re.escape(word)}\b", answer) for word in checks["require_any"])
        results.append({"check": "mentions one of " + ", ".join(checks["require_any"]), "passed": found})
    return results


def source_hit(case: dict, found) -> float | None:
    """Share of the expected source files that appear among the retrieved chunks (no LLM involved)."""
    expected = set(case["reference_sources"])
    if not expected:
        return None
    return len(expected & {item.source for item in found}) / len(expected)


def _clean(value) -> float | None:
    if value is None:
        return None
    value = float(value)
    return None if math.isnan(value) else round(value, 4)


def aggregate(rows: list[dict]) -> dict[str, dict]:
    """Mean score per Ragas metric over the gated case types, ignoring missing scores."""
    result = {}
    for metric in RAGAS_METRICS:
        values = [r["scores"][metric] for r in rows
                  if r["case_type"] in GATED_TYPES and r.get("scores", {}).get(metric) is not None]
        result[metric] = {"mean": round(sum(values) / len(values), 4) if values else None, "n": len(values)}
    return result


def evaluate_gates(rows: list[dict], aggregates: dict[str, dict], ragas_ran: bool) -> list[dict]:
    gates = []
    for metric, target in THRESHOLDS.items():
        mean = aggregates[metric]["mean"]
        if not ragas_ran:
            status = "SKIPPED"
        else:
            status = "PASS" if mean is not None and mean >= target else "FAIL"
        gates.append({"gate": f"{metric} aggregate >= {target}", "value": mean, "status": status})
    critical = [r for r in rows if r["id"] in CRITICAL_IDS]
    failed = [r["id"] for r in critical if not all(c["passed"] for c in r["checks"])]
    gates.append({"gate": "critical safety cases 100% pass (" + ", ".join(sorted(r["id"] for r in critical)) + ")",
                  "value": f"{len(critical) - len(failed)}/{len(critical)}",
                  "status": "PASS" if critical and not failed else "FAIL"})
    all_failed = [r["id"] for r in rows if not all(c["passed"] for c in r["checks"])]
    gates.append({"gate": "all code checks pass", "value": f"{len(rows) - len(all_failed)}/{len(rows)}",
                  "status": "PASS" if not all_failed else "FAIL"})
    return gates


def _failed_row(case: dict, found, message: str) -> dict:
    """A row for a case where the model produced no answer; it fails its checks and is not sent to Ragas."""
    return {
        "id": case["id"], "case_type": "generation_failed", "original_case_type": case["case_type"],
        "question": case["question"], "reference": case["reference"], "reference_sources": case["reference_sources"],
        "answer": "", "abstained": False, "model": None, "latency_s": None, "stop_reason": None,
        "retrieved": [{"chunk_id": r.chunk_id, "source": r.source, "score": r.score} for r in found],
        "contexts": [], "source_hit": source_hit(case, found),
        "checks": [{"check": message, "passed": False}], "scores": {}, "score_errors": {},
    }


def build_rows(cases, embedding_function=None, client=None, k: int = TOP_K) -> list[dict]:
    kb_chunks = load_chunks(KNOWLEDGE_DIR)
    fixture_chunks = load_chunks(FIXTURES_DIR)
    plain = build_index(kb_chunks, embedding_function=embedding_function, name="eval_kb")
    with_fixture = build_index(kb_chunks + fixture_chunks, embedding_function=embedding_function, name="eval_kb_fixture")
    rows = []
    for case in cases:
        found = retrieve(with_fixture if case["use_fixture"] else plain, case["question"], k)
        try:
            answer = generate(case["question"], found, client=client)
        except EmptyAnswer as error:
            rows.append(_failed_row(case, found, str(error)))
            continue
        rows.append({
            "id": case["id"], "case_type": case["case_type"], "question": case["question"],
            "reference": case["reference"], "reference_sources": case["reference_sources"],
            "answer": answer.text, "abstained": answer.abstained, "model": answer.model, "stop_reason": answer.stop_reason,
            "latency_s": answer.latency_s,
            "retrieved": [{"chunk_id": r.chunk_id, "source": r.source, "score": r.score} for r in found],
            "contexts": [f"[source: {r.source} | id: {r.chunk_id}]\n{r.text}" for r in found],  # what the generator saw
            "source_hit": source_hit(case, found),
            "checks": run_checks(case, answer.text, answer.abstained),
            "scores": {}, "score_errors": {},
        })
    return rows


class ChromaEmbedding:
    """Adapter that lets Ragas use the same local embedding model as the index (answer relevancy needs one)."""

    def __new__(cls):
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
        from ragas.embeddings.base import BaseRagasEmbedding

        function = DefaultEmbeddingFunction()

        class _Embedding(BaseRagasEmbedding):
            def embed_text(self, text: str, **kwargs) -> list[float]:
                return [float(x) for x in function([text])[0]]

            async def aembed_text(self, text: str, **kwargs) -> list[float]:
                return self.embed_text(text)

        return _Embedding()


async def _score_row(row: dict, metrics: dict, gate: asyncio.Semaphore) -> None:
    question, answer, reference, contexts = row["question"], row["answer"], row["reference"], row["contexts"]
    calls = {
        "faithfulness": lambda m: m.ascore(user_input=question, response=answer, retrieved_contexts=contexts),
        "context_precision": lambda m: m.ascore(user_input=question, reference=reference, retrieved_contexts=contexts),
        "context_recall": lambda m: m.ascore(user_input=question, retrieved_contexts=contexts, reference=reference),
        "factual_correctness": lambda m: m.ascore(response=answer, reference=reference),
        "answer_relevancy": lambda m: m.ascore(user_input=question, response=answer),
    }
    row["scores"], row["score_errors"] = {}, {}

    async def one(name: str) -> None:
        async with gate:
            try:
                result = await calls[name](metrics[name])
                row["scores"][name] = _clean(result.value)
            except Exception as error:  # keep going: one failing metric must not hide the others
                row["scores"][name] = None
                row["score_errors"][name] = f"{type(error).__name__}: {str(error)[:200]}"

    await asyncio.gather(*(one(name) for name in RAGAS_METRICS))


def make_metrics(client, judge_model: str, embedding=None) -> dict:
    from ragas.llms import llm_factory
    from ragas.metrics.collections import (
        AnswerRelevancy, ContextPrecision, ContextRecall, FactualCorrectness, Faithfulness,
    )

    llm = llm_factory(judge_model, provider="anthropic", client=client)
    return {
        "faithfulness": Faithfulness(llm=llm),
        "context_precision": ContextPrecision(llm=llm),
        "context_recall": ContextRecall(llm=llm),
        "factual_correctness": FactualCorrectness(llm=llm),
        "answer_relevancy": AnswerRelevancy(llm=llm, embeddings=embedding or ChromaEmbedding()),
    }


async def score_rows(rows: list[dict], metrics: dict, concurrency: int = 4) -> None:
    gate = asyncio.Semaphore(concurrency)
    targets = [r for r in rows if r["case_type"] in RAGAS_TYPES]
    await asyncio.gather(*(_score_row(r, metrics, gate) for r in targets))


def write_reports(out: Path, rows, aggregates, gates, meta) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with (out / "ragas-examples.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    with (out / "ragas-results.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["section", "name", "value", "n_or_detail", "target", "status"])
        for metric in RAGAS_METRICS:
            target = THRESHOLDS.get(metric, "")
            mean = aggregates[metric]["mean"]
            status = "" if target == "" else next(g["status"] for g in gates if g["gate"].startswith(metric))
            writer.writerow(["ragas_aggregate", metric, mean, aggregates[metric]["n"], target, status])
        hits = [r["source_hit"] for r in rows if r["source_hit"] is not None]
        writer.writerow(["retrieval", "source_hit_mean", round(sum(hits) / len(hits), 4) if hits else "", len(hits), "", ""])
        for gate in gates:
            if not any(gate["gate"].startswith(m) for m in THRESHOLDS):
                writer.writerow(["gate", gate["gate"], gate["value"], "", "", gate["status"]])
        for row in rows:
            for metric, value in row["scores"].items():
                writer.writerow(["per_case", f"{row['id']} {metric}", value, row["case_type"], "", ""])
    (out / "ragas-run-meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8", newline="\n")


def _version(package: str) -> str:
    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        return "not installed"


def run_evaluation(limit=None, use_ragas=True, judge_model=None, out=Path("reports"), embedding_function=None,
                   client=None, ragas_embedding=None) -> int:
    cases, dataset_hash = load_dataset()
    if limit:
        cases = cases[:limit]
    client = client or make_client()
    judge_model = judge_model or os.environ.get("RAGAS_JUDGE_MODEL", DEFAULT_MODEL)
    rows = build_rows(cases, embedding_function=embedding_function, client=client)
    if use_ragas:
        asyncio.run(score_rows(rows, make_metrics(client, judge_model, ragas_embedding)))
    aggregates = aggregate(rows)
    gates = evaluate_gates(rows, aggregates, ragas_ran=use_ragas)
    meta = {
        "run_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset": "rag-eval-v1", "dataset_sha256": dataset_hash, "cases_run": len(rows), "limit": limit,
        "top_k": TOP_K, "prompt_version": PROMPT_VERSION, "generator_model": next((r["model"] for r in rows if r["model"]), None),
        "judge_model": judge_model if use_ragas else None, "embedding_model": EMBEDDING_MODEL,
        "index_version": index_version(load_chunks(KNOWLEDGE_DIR)),
        "ragas_ran": use_ragas, "thresholds": THRESHOLDS,
        "versions": {p: _version(p) for p in ("ragas", "anthropic", "instructor", "chromadb", "pydantic")},
        "python": platform.python_version(), "platform": platform.platform(),
    }
    write_reports(Path(out), rows, aggregates, gates, meta)
    print(f"cases={len(rows)} ragas={'yes' if use_ragas else 'no'} judge={meta['judge_model']}")
    for metric in RAGAS_METRICS:
        print(f"  {metric:20} {aggregates[metric]['mean']}  (n={aggregates[metric]['n']})")
    for gate in gates:
        print(f"  [{gate['status']}] {gate['gate']}: {gate['value']}")
    failed_rows = [r["id"] for r in rows if not all(c["passed"] for c in r["checks"])]
    if failed_rows:
        print("  failing code checks:", ", ".join(failed_rows))
    errors = [(r["id"], m, e) for r in rows for m, e in r.get("score_errors", {}).items()]
    for case_id, metric, error in errors[:10]:
        print(f"  score error {case_id} {metric}: {error}")
    return 0 if all(g["status"] in ("PASS", "SKIPPED") for g in gates) else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="rag.evaluate")
    parser.add_argument("--limit", type=int, default=None, help="run only the first N cases (smoke test)")
    parser.add_argument("--no-ragas", action="store_true", help="skip the Ragas judge; run answers and code checks only")
    parser.add_argument("--judge-model", default=None)
    parser.add_argument("--out", default="reports")
    args = parser.parse_args(argv)
    try:
        return run_evaluation(args.limit, not args.no_ragas, args.judge_model, Path(args.out))
    except Exception as error:
        print(f"evaluation failed: {type(error).__name__}: {error}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
