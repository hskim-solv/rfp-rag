from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter

_TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")
_HANGUL_RE = re.compile(r"[가-힣]")


def normalize_text(text: str) -> str:
    return unicodedata.normalize("NFC", text or "").lower()


def lexical_features(text: str) -> Counter[str]:
    text = normalize_text(text)
    features: Counter[str] = Counter()
    for token in _TOKEN_RE.findall(text):
        if len(token) >= 2:
            features[token] += 3
        elif token:
            features[token] += 1
        # Korean compound nouns often arrive as long eojeol; n-grams make fake retrieval usable.
        if _HANGUL_RE.search(token):
            for n in (2, 3, 4):
                if len(token) >= n:
                    for i in range(0, len(token) - n + 1):
                        features[token[i : i + n]] += 1
    return features


def cosine_score(query: Counter[str], document: Counter[str]) -> float:
    if not query or not document:
        return 0.0
    dot = sum(weight * document.get(feature, 0) for feature, weight in query.items())
    if dot <= 0:
        return 0.0
    q_norm = math.sqrt(sum(v * v for v in query.values()))
    d_norm = math.sqrt(sum(v * v for v in document.values()))
    return dot / (q_norm * d_norm) if q_norm and d_norm else 0.0
