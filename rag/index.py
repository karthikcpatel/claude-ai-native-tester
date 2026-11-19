"""Stage 3 of the RAG pipeline: Embed and index (local Chroma index, rebuilt on every run).

Chroma anonymised telemetry is switched off so that no usage data leaves the machine."""
from __future__ import annotations

import hashlib

import chromadb
from chromadb.config import Settings

from rag.chunking import Chunk

COLLECTION = "capstone_knowledge"
EMBEDDING_MODEL = "chroma-default-onnx-all-MiniLM-L6-v2"


def index_version(chunks: list[Chunk]) -> str:
    digest = hashlib.sha256()
    for chunk in chunks:
        digest.update(chunk.chunk_id.encode("utf-8"))
        digest.update(chunk.text.encode("utf-8"))
    return digest.hexdigest()[:12]


def build_index(
    chunks: list[Chunk], embedding_function=None, embedding_model: str = EMBEDDING_MODEL, name: str = COLLECTION
):
    """Create an in-memory collection holding the chunks. Pass embedding_function to override the default model.

    Use a different name for each index that must exist at the same time in one process."""
    client = chromadb.EphemeralClient(settings=Settings(anonymized_telemetry=False))
    try:
        client.delete_collection(name)
    except Exception:  # the collection does not exist yet
        pass
    options = {} if embedding_function is None else {"embedding_function": embedding_function}
    collection = client.create_collection(
        name,
        metadata={
            "hnsw:space": "cosine",
            "index_version": index_version(chunks),
            "embedding_model": embedding_model,
        },
        **options,
    )
    collection.add(
        ids=[c.chunk_id for c in chunks],
        documents=[c.text for c in chunks],
        metadatas=[
            {"source": c.source, "version": c.version, "section": c.section, "start": c.start, "end": c.end}
            for c in chunks
        ],
    )
    return collection
