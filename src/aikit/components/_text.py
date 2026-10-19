"""Small text utilities shared by the fake embedder and the in-memory keyword index."""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence

_TOKEN = re.compile(r"[a-z0-9]+")
_STOPWORDS_TEXT = (
    "a an and are as at be by can do does for from has have how i if in is it its me my of "
    "on or our so that the their them then there these they this to was we what when where "
    "which who why will with you your"
)
STOPWORDS = frozenset(_STOPWORDS_TEXT.split())


def tokenize(text: str) -> list[str]:
    tokens = []
    for token in _TOKEN.findall(text.lower()):
        if token in STOPWORDS:
            continue
        if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
            token = token[:-1]
        tokens.append(token)
    return tokens


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class BM25:
    """Okapi BM25 over a fixed list of documents."""

    def __init__(self, documents: Sequence[str], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.docs = [Counter(tokenize(d)) for d in documents]
        self.lengths = [sum(c.values()) for c in self.docs]
        self.avg_len = (sum(self.lengths) / len(self.lengths)) if self.lengths else 0.0
        df: Counter[str] = Counter()
        for counts in self.docs:
            df.update(counts.keys())
        n = len(self.docs)
        self.idf = {
            term: math.log(1 + (n - freq + 0.5) / (freq + 0.5)) for term, freq in df.items()
        }

    def scores(self, query: str) -> list[float]:
        terms = tokenize(query)
        results = []
        for counts, length in zip(self.docs, self.lengths, strict=True):
            score = 0.0
            for term in terms:
                tf = counts.get(term, 0)
                if not tf:
                    continue
                denom = tf + self.k1 * (1 - self.b + self.b * length / (self.avg_len or 1))
                score += self.idf.get(term, 0.0) * tf * (self.k1 + 1) / denom
            results.append(score)
        return results
