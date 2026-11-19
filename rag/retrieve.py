"""Stage 4 of the RAG pipeline: Retrieve (top-k similarity search) and a log that never stores chunk text."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_LOG = Path("reports") / "rag-retrieval.jsonl"
ANSWER_LOG = Path("reports") / "rag-answers.jsonl"


@dataclass(frozen=True)
class Retrieved:
    chunk_id: str
    source: str
    version: str
    section: str
    score: float  # cosine similarity, higher is closer
    text: str


def retrieve(collection, question: str, k: int = 4) -> list[Retrieved]:
    result = collection.query(
        query_texts=[question], n_results=k, include=["documents", "metadatas", "distances"]
    )
    found = []
    for chunk_id, text, meta, distance in zip(
        result["ids"][0], result["documents"][0], result["metadatas"][0], result["distances"][0]
    ):
        found.append(
            Retrieved(
                chunk_id=chunk_id,
                source=meta["source"],
                version=meta["version"],
                section=meta["section"],
                score=round(1.0 - float(distance), 4),
                text=text,
            )
        )
    return found


def log_retrieval(question: str, found: list[Retrieved], path: Path = DEFAULT_LOG) -> None:
    """Append question, chunk ids, sources and scores. Chunk text is deliberately not logged."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "question": question,
        "chunks": [{"chunk_id": r.chunk_id, "source": r.source, "version": r.version, "score": r.score} for r in found],
    }
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record) + "\n")


def log_answer(question: str, found: list[Retrieved], answer, path: Path = ANSWER_LOG) -> None:
    """Append the question, the answer text, the model, the prompt version, the latency and the chunk ids."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "question": question,
        "answer": answer.text,
        "abstained": answer.abstained,
        "model": answer.model,
        "prompt_version": answer.prompt_version,
        "latency_s": answer.latency_s,
        "input_tokens": answer.input_tokens,
        "output_tokens": answer.output_tokens,
        "chunk_ids": [r.chunk_id for r in found],
    }
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record) + "\n")
