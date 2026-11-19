"""Deterministic tests for the Load and Chunk stages. No network, no model, no API key."""
from rag.chunking import MAX_CHARS, Document, chunk_document, load_chunks, load_documents

EXPECTED_FILES = {
    "known_defects.md",
    "login_requirements.md",
    "payment_test_policy.md",
    "qa_standards.md",
    "release_gate.md",
}


def test_all_five_knowledge_documents_load_with_a_version():
    documents = load_documents()
    assert {d.source for d in documents} == EXPECTED_FILES
    assert all(d.version.startswith("v") for d in documents), "every document needs a version line"


def test_chunk_ids_are_unique_and_stable():
    first = [c.chunk_id for c in load_chunks()]
    second = [c.chunk_id for c in load_chunks()]
    assert first == second
    assert len(first) == len(set(first))


def test_every_chunk_records_source_version_section_and_a_valid_range():
    documents = {d.source: d for d in load_documents()}
    for chunk in load_chunks():
        doc = documents[chunk.source]
        assert chunk.version == doc.version
        assert chunk.section
        assert 0 <= chunk.start < chunk.end <= len(doc.text), chunk.chunk_id
        assert doc.text[chunk.start:chunk.end].strip() in chunk.text, chunk.chunk_id


def test_live_payment_rule_is_in_a_payment_policy_chunk():
    matches = [c for c in load_chunks() if "PT-2" in c.text]
    assert matches, "PT-2 must be in some chunk"
    assert matches[0].source == "payment_test_policy.md"
    assert "live payment gateway" in matches[0].text


def test_chunks_are_not_larger_than_the_limit_plus_the_title_prefix():
    for chunk in load_chunks():
        assert len(chunk.text) <= MAX_CHARS + 150, chunk.chunk_id


def test_no_password_or_refund_policy_leaks_into_the_index():
    texts = "\n".join(c.text for c in load_chunks()).lower()
    assert "demopass" not in texts
    assert "refund" not in texts, "RAG-09 depends on refunds being absent from the knowledge base"


def test_long_section_is_split_into_overlapping_windows_that_cover_every_line():
    lines = [f"- line number {n:02d} with some padding text" for n in range(40)]
    body = "## Long section\n" + "\n".join(lines) + "\n"
    doc = Document("synthetic.md", "v1", "Synthetic", "# Synthetic\n\nVersion: v1\n\n" + body)
    chunks = chunk_document(doc, max_chars=300, overlap=100)
    long_chunks = [c for c in chunks if c.section == "Long section"]
    assert len(long_chunks) > 1
    for before, after in zip(long_chunks, long_chunks[1:]):
        assert after.start < before.end, "neighbouring windows must overlap"
        assert after.start > before.start, "every window must make progress"
    joined = "\n".join(c.text for c in long_chunks)
    assert all(line in joined for line in lines)
    assert len({c.chunk_id for c in long_chunks}) == len(long_chunks)
