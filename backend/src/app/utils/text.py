from __future__ import annotations

import re

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def split_sentences(text: str) -> list[str]:
    chunks = _SENTENCE_SPLIT.split(text.strip())
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def keyword_overlap_score(query: str, content: str) -> float:
    query_terms = {term.lower() for term in re.findall(r"[a-zA-Z0-9_]+", query)}
    content_terms = {term.lower() for term in re.findall(r"[a-zA-Z0-9_]+", content)}
    if not query_terms:
        return 0.0
    return len(query_terms & content_terms) / len(query_terms)
