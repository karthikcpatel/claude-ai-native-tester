"""Shared offline helpers for the RAG tests."""
import hashlib
import re

from chromadb import Documents, EmbeddingFunction, Embeddings

DIMENSIONS = 256


class BagOfWordsEmbedding(EmbeddingFunction):
    """Tiny deterministic embedding for wiring tests (not a quality benchmark)."""

    def __init__(self):
        pass

    def __call__(self, input: Documents) -> Embeddings:
        vectors = []
        for text in input:
            vector = [0.0] * DIMENSIONS
            for word in re.findall(r"[a-z0-9]+", text.lower()):
                vector[int(hashlib.md5(word.encode()).hexdigest(), 16) % DIMENSIONS] += 1.0
            vectors.append(vector)
        return vectors

    @staticmethod
    def name() -> str:
        return "bag-of-words-test"

    def get_config(self):
        return {}

    @staticmethod
    def build_from_config(config):
        return BagOfWordsEmbedding()


def make_fake_ragas_embedding():
    from ragas.embeddings.base import BaseRagasEmbedding

    class FakeRagasEmbedding(BaseRagasEmbedding):
        def embed_text(self, text, **kwargs):
            return [float(len(text) % 7 + 1), 1.0, 0.5]

        async def aembed_text(self, text, **kwargs):
            return self.embed_text(text)

    return FakeRagasEmbedding()
