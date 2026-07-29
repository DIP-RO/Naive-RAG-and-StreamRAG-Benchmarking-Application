from __future__ import annotations

from dataclasses import dataclass

from app.models.schemas import RetrievalChunk
from app.utils.text import keyword_overlap_score


@dataclass(slots=True)
class RerankedChunk:
    chunk: RetrievalChunk
    rerank_score: float


class HybridReranker:
    """Combine vector similarity with lexical overlap for more stable retrieval."""

    def rerank(self, query: str, chunks: list[RetrievalChunk]) -> list[RetrievalChunk]:
        scored = []
        for chunk in chunks:
            lexical = keyword_overlap_score(query, chunk.content)
            rerank_score = (0.75 * chunk.score) + (0.25 * lexical)
            scored.append((rerank_score, chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [chunk for _, chunk in scored]
