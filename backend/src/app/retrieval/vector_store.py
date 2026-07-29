from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as rest

from app.models.schemas import RetrievalChunk
from app.retrieval.chunker import Chunk
from app.retrieval.embeddings import EmbeddingProvider
from app.utils.text import keyword_overlap_score


class VectorStoreProtocol:
    async def upsert_chunks(self, chunks: Iterable[Chunk]) -> None:
        raise NotImplementedError

    async def search(self, query: str, limit: int = 5) -> list[RetrievalChunk]:
        raise NotImplementedError


@dataclass(slots=True)
class StoredDocument:
    document_id: str
    title: str
    content: str
    metadata: dict[str, object]


class QdrantVectorStore(VectorStoreProtocol):
    def __init__(self, client: AsyncQdrantClient, collection: str, embeddings: EmbeddingProvider) -> None:
        self.client = client
        self.collection = collection
        self.embeddings = embeddings

    async def ensure_collection(self, vector_size: int = 1536) -> None:
        collections = await self.client.get_collections()
        if any(collection.name == self.collection for collection in collections.collections):
            return
        await self.client.create_collection(
            collection_name=self.collection,
            vectors_config=rest.VectorParams(size=vector_size, distance=rest.Distance.COSINE),
        )

    async def upsert_chunks(self, chunks: Iterable[Chunk]) -> None:
        chunk_list = list(chunks)
        if not chunk_list:
            return
        vectors = await self.embeddings.embed_texts([chunk.content for chunk in chunk_list])
        points = [
            rest.PointStruct(
                id=chunk.chunk_id,
                vector=vector,
                payload={
                    "chunk_id": chunk.chunk_id,
                    "document_id": chunk.document_id,
                    "title": chunk.title,
                    "content": chunk.content,
                    "chunk_index": chunk.chunk_index,
                    **chunk.metadata,
                },
            )
            for chunk, vector in zip(chunk_list, vectors, strict=True)
        ]
        await self.client.upsert(collection_name=self.collection, points=points)

    async def search(self, query: str, limit: int = 5) -> list[RetrievalChunk]:
        query_vector = (await self.embeddings.embed_texts([query]))[0]
        results = await self.client.search(
            collection_name=self.collection,
            query_vector=query_vector,
            limit=limit,
            with_payload=True,
            score_threshold=None,
        )
        chunks: list[RetrievalChunk] = []
        for result in results:
            payload = result.payload or {}
            chunks.append(
                RetrievalChunk(
                    chunk_id=str(payload.get("chunk_id", result.id)),
                    document_id=str(payload.get("document_id", "")),
                    title=str(payload.get("title", "Untitled")),
                    content=str(payload.get("content", "")),
                    score=float(result.score or 0.0),
                    source="qdrant",
                    metadata={key: value for key, value in payload.items() if key not in {"chunk_id", "document_id", "title", "content"}},
                )
            )
        return chunks


class InMemoryVectorStore(VectorStoreProtocol):
    def __init__(self, embeddings: EmbeddingProvider) -> None:
        self.embeddings = embeddings
        self._chunks: list[Chunk] = []
        self._vectors: list[list[float]] = []

    async def upsert_chunks(self, chunks: Iterable[Chunk]) -> None:
        chunk_list = list(chunks)
        if not chunk_list:
            return
        vectors = await self.embeddings.embed_texts([chunk.content for chunk in chunk_list])
        self._chunks.extend(chunk_list)
        self._vectors.extend(vectors)

    async def search(self, query: str, limit: int = 5) -> list[RetrievalChunk]:
        if not self._chunks:
            return []
        query_vector = (await self.embeddings.embed_texts([query]))[0]
        scored: list[tuple[float, Chunk]] = []
        for chunk, vector in zip(self._chunks, self._vectors, strict=True):
            cosine = self._cosine_similarity(query_vector, vector)
            lexical = keyword_overlap_score(query, chunk.content)
            scored.append(((0.8 * cosine) + (0.2 * lexical), chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        results: list[RetrievalChunk] = []
        for score, chunk in scored[:limit]:
            results.append(
                RetrievalChunk(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    title=chunk.title,
                    content=chunk.content,
                    score=score,
                    source="memory",
                    metadata=chunk.metadata,
                )
            )
        return results

    def _cosine_similarity(self, left: list[float], right: list[float]) -> float:
        numerator = sum(a * b for a, b in zip(left, right, strict=True))
        left_norm = sum(value * value for value in left) ** 0.5 or 1.0
        right_norm = sum(value * value for value in right) ** 0.5 or 1.0
        return numerator / (left_norm * right_norm)
