from __future__ import annotations

from dataclasses import dataclass

from app.utils.text import normalize_whitespace, split_sentences


@dataclass(slots=True)
class Chunk:
    chunk_id: str
    document_id: str
    title: str
    content: str
    chunk_index: int
    metadata: dict[str, object]


class Chunker:
    """Sentence-aware chunker with overlap for production retrieval quality."""

    def __init__(self, max_chars: int = 1200, overlap_sentences: int = 1) -> None:
        self.max_chars = max_chars
        self.overlap_sentences = overlap_sentences

    def chunk_document(
        self,
        document_id: str,
        title: str,
        content: str,
        metadata: dict[str, object] | None = None,
    ) -> list[Chunk]:
        metadata = metadata or {}
        sentences = split_sentences(normalize_whitespace(content))
        if not sentences:
            return []

        chunks: list[Chunk] = []
        buffer: list[str] = []
        chunk_index = 0
        for sentence in sentences:
            candidate = " ".join(buffer + [sentence])
            if buffer and len(candidate) > self.max_chars:
                chunks.append(
                    Chunk(
                        chunk_id=f"{document_id}:{chunk_index}",
                        document_id=document_id,
                        title=title,
                        content=" ".join(buffer),
                        chunk_index=chunk_index,
                        metadata=metadata,
                    )
                )
                chunk_index += 1
                buffer = buffer[-self.overlap_sentences :] if self.overlap_sentences else []
            buffer.append(sentence)
        if buffer:
            chunks.append(
                Chunk(
                    chunk_id=f"{document_id}:{chunk_index}",
                    document_id=document_id,
                    title=title,
                    content=" ".join(buffer),
                    chunk_index=chunk_index,
                    metadata=metadata,
                )
            )
        return chunks
