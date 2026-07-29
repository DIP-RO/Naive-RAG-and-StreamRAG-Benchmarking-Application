from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from app.retrieval.chunker import Chunk, Chunker
from app.retrieval.vector_store import VectorStoreProtocol


@dataclass(slots=True)
class DocumentRecord:
    document_id: str
    title: str
    content: str
    metadata: dict[str, object]


class DocumentIngestionService:
    def __init__(self, chunker: Chunker, vector_store: VectorStoreProtocol) -> None:
        self.chunker = chunker
        self.vector_store = vector_store

    async def ingest_documents(self, documents: Iterable[DocumentRecord]) -> int:
        chunks: list[Chunk] = []
        for document in documents:
            chunks.extend(
                self.chunker.chunk_document(
                    document_id=document.document_id,
                    title=document.title,
                    content=document.content,
                    metadata=document.metadata,
                )
            )
        await self.vector_store.upsert_chunks(chunks)
        return len(chunks)

    async def ingest_file(self, file_path: Path, document_id: str | None = None) -> int:
        content = file_path.read_text(encoding="utf-8")
        record = DocumentRecord(
            document_id=document_id or file_path.stem,
            title=file_path.name,
            content=content,
            metadata={"path": str(file_path)},
        )
        return await self.ingest_documents([record])
