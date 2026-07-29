from __future__ import annotations

import pytest

from app.retrieval.chunker import Chunker
from app.retrieval.embeddings import DeterministicEmbeddingProvider
from app.retrieval.vector_store import InMemoryVectorStore


@pytest.mark.asyncio
async def test_in_memory_store_upsert_and_search() -> None:
    embeddings = DeterministicEmbeddingProvider(dimensions=128)
    store = InMemoryVectorStore(embeddings)
    chunker = Chunker()

    chunks = chunker.chunk_document(document_id="doc-1", title="Test", content="Machine learning is a subset of artificial intelligence.")
    await store.upsert_chunks(chunks)

    results = await store.search("machine learning", limit=5)
    assert len(results) == 1
    assert results[0].document_id == "doc-1"
    assert results[0].score > 0.0


@pytest.mark.asyncio
async def test_in_memory_store_empty_search() -> None:
    embeddings = DeterministicEmbeddingProvider(dimensions=128)
    store = InMemoryVectorStore(embeddings)
    results = await store.search("anything", limit=5)
    assert results == []


@pytest.mark.asyncio
async def test_in_memory_store_ranking() -> None:
    embeddings = DeterministicEmbeddingProvider(dimensions=128)
    store = InMemoryVectorStore(embeddings)
    chunker = Chunker()

    chunks = chunker.chunk_document(document_id="doc-1", title="AI", content="Artificial intelligence transforms industries.")
    chunks += chunker.chunk_document(document_id="doc-2", title="Cooking", content="Pasta is a traditional Italian dish.")
    await store.upsert_chunks(chunks)

    results = await store.search("artificial intelligence", limit=2)
    assert len(results) == 2
    assert results[0].document_id == "doc-1"


@pytest.mark.asyncio
async def test_in_memory_store_cosine_similarity() -> None:
    embeddings = DeterministicEmbeddingProvider(dimensions=128)
    store = InMemoryVectorStore(embeddings)
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    v3 = [0.0, 1.0, 0.0]
    assert store._cosine_similarity(v1, v2) == pytest.approx(1.0)
    assert store._cosine_similarity(v1, v3) == pytest.approx(0.0)
