"""Wiring tests for Index and Retrieve using a tiny deterministic bag-of-words embedding.

They prove that indexing, cosine ranking, metadata and logging work. They do not judge the quality of the real
embedding model; that is measured by the Ragas run on the evaluation dataset.
"""
import json

from helpers import BagOfWordsEmbedding
from rag.chunking import load_chunks
from rag.index import build_index, index_version
from rag.retrieve import log_retrieval, retrieve

def _index():
    chunks = load_chunks()
    return chunks, build_index(chunks, embedding_function=BagOfWordsEmbedding(), embedding_model="bag-of-words-test")


def test_every_chunk_is_indexed_and_the_collection_records_its_version():
    chunks, collection = _index()
    assert collection.count() == len(chunks)
    assert collection.metadata["index_version"] == index_version(chunks)
    assert collection.metadata["embedding_model"] == "bag-of-words-test"


def test_live_gateway_question_retrieves_the_payment_policy_in_the_top_three_with_sorted_scores():
    _, collection = _index()
    found = retrieve(collection, "Can the automated tests use a live payment gateway?", k=3)
    assert "payment_test_policy.md" in [r.source for r in found]
    assert found[0].score >= found[1].score >= found[2].score


def test_release_gate_question_retrieves_release_gate_file():
    _, collection = _index()
    found = retrieve(collection, "Which checks and thresholds are required before release?", k=3)
    assert "release_gate.md" in [r.source for r in found]


def test_retrieval_log_has_ids_and_scores_but_no_chunk_text(tmp_path):
    _, collection = _index()
    found = retrieve(collection, "May logs contain passwords or tokens?", k=2)
    log = tmp_path / "retrieval.jsonl"
    log_retrieval("May logs contain passwords or tokens?", found, path=log)
    record = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
    assert [c["chunk_id"] for c in record["chunks"]] == [r.chunk_id for r in found]
    assert all("text" not in c for c in record["chunks"])
    assert found[0].text not in log.read_text(encoding="utf-8")


def test_chroma_telemetry_is_switched_off():
    _, collection = _index()
    assert collection.count() > 0
    import inspect

    import rag.index as index_module

    assert "anonymized_telemetry=False" in inspect.getsource(index_module)
