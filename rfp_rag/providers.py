from __future__ import annotations

import hashlib
import math

from langchain_core.embeddings import Embeddings

from .fake_provider import lexical_features


class LexicalHashEmbeddings(Embeddings):
    """Deterministic offline embeddings: hashed Korean n-gram lexical features.

    Cosine similarity approximates the legacy fake lexical retrieval, so the
    offline lane keeps meaningful retrieval/abstention behavior without API keys.
    """

    def __init__(self, dim: int = 4096) -> None:
        if dim <= 0:
            raise ValueError("dim must be positive")
        self.dim = dim

    def _vector(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for feature, weight in lexical_features(text).items():
            digest = hashlib.sha256(feature.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % self.dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vec[idx] += sign * float(weight)
        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0.0:
            vec[0] = 1.0
            return vec
        return [v / norm for v in vec]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)
