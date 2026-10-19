from __future__ import annotations

import hashlib
import math

from aikit.components._text import tokenize
from aikit.core.registry import register


@register("embedder", "fake")
class FakeEmbedder:
    """Deterministic hashed bag-of-words vectors. Similar wording gives similar vectors,
    which is enough to exercise retrieval offline."""

    def __init__(self, dimensions: int = 256, model: str = "fake-embedder") -> None:
        self.model = model
        self.dimensions = dimensions

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in tokenize(text):
            digest = hashlib.md5(token.encode(), usedforsecurity=False).digest()
            index = int.from_bytes(digest[:4], "little") % self.dimensions
            vector[index] += 1.0 if digest[4] % 2 == 0 else -1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    async def embed_query(self, text: str) -> list[float]:
        return self._vector(text)
