from __future__ import annotations

import asyncio
from pathlib import Path

from qdrant_client import AsyncQdrantClient

from app.core.config import AppSettings, get_settings
from app.retrieval.chunker import Chunker
from app.retrieval.embeddings import (
    DeterministicEmbeddingProvider,
    OpenAIEmbeddingProvider,
)
from app.retrieval.vector_store import QdrantVectorStore

DOCUMENTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "documents"


def _build_embeddings(settings: AppSettings):
    if settings.openai_api_key:
        return OpenAIEmbeddingProvider(
            api_key=settings.openai_api_key, model=settings.default_embedding_model
        )
    return DeterministicEmbeddingProvider()


async def ingest() -> None:
    settings = get_settings()
    embeddings = _build_embeddings(settings)
    client = AsyncQdrantClient(url=settings.qdrant_url)
    store = QdrantVectorStore(client, settings.qdrant_collection, embeddings)
    await store.ensure_collection(vector_size=getattr(embeddings, "dimensions", 1536))

    chunker = Chunker()
    total = 0
    for path in sorted(DOCUMENTS_DIR.glob("*.txt")):
        text = path.read_text()
        chunks = chunker.chunk_document(
            document_id=path.stem,
            title=path.name,
            content=text,
            metadata={"path": str(path)},
        )
        await store.upsert_chunks(chunks)
        total += len(chunks)
        print(f"  {path.name}: {len(chunks)} chunks")
    print(f"Done — {total} chunks ingested")


if __name__ == "__main__":
    asyncio.run(ingest())
