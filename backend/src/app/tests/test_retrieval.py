from __future__ import annotations

import pytest
from langsmith import traceable

from app.retrieval.chunker import Chunk
from app.retrieval.embeddings import DeterministicEmbeddingProvider
from app.retrieval.vector_store import InMemoryVectorStore


@pytest.mark.asyncio
@traceable(name="test_retrieval_upsert_search")
async def test_in_memory_store_upsert_and_search() -> None:
    provider = DeterministicEmbeddingProvider(dimensions=128)
    store = InMemoryVectorStore(provider)
    chunks = [
        Chunk(chunk_id="1", document_id="d1", title="Doc1", content="The weather is sunny today", chunk_index=0, metadata={}),
        Chunk(chunk_id="2", document_id="d1", title="Doc1", content="Machine learning is fun", chunk_index=1, metadata={}),
    ]
    await store.upsert_chunks(chunks)
    results = await store.search("weather", limit=5)
    assert len(results) > 0
    assert results[0].score > 0.0
    assert any("weather" in r.content for r in results)


@pytest.mark.asyncio
@traceable(name="test_retrieval_empty")
async def test_in_memory_store_empty_search() -> None:
    provider = DeterministicEmbeddingProvider(dimensions=128)
    store = InMemoryVectorStore(provider)
    results = await store.search("anything", limit=5)
    assert results == []


@pytest.mark.asyncio
@traceable(name="test_retrieval_ranking")
async def test_in_memory_store_ranking() -> None:
    provider = DeterministicEmbeddingProvider(dimensions=128)
    store = InMemoryVectorStore(provider)
    chunks = [
        Chunk(chunk_id="a", document_id="d1", title="Doc1", content="Python is a programming language", chunk_index=0, metadata={}),
        Chunk(chunk_id="b", document_id="d1", title="Doc1", content="Java is also a language", chunk_index=1, metadata={}),
        Chunk(chunk_id="c", document_id="d1", title="Doc1", content="Weather forecast for London today", chunk_index=2, metadata={}),
    ]
    await store.upsert_chunks(chunks)
    results = await store.search("programming language", limit=3)
    assert len(results) == 3
    assert results[0].score >= results[1].score >= results[2].score


@pytest.mark.asyncio
@traceable(name="test_retrieval_cosine")
async def test_in_memory_store_cosine_similarity() -> None:
    provider = DeterministicEmbeddingProvider(dimensions=128)
    store = InMemoryVectorStore(provider)
    v1 = [0.6, 0.8, 0.0]
    v2 = [0.6, 0.8, 0.0]
    similarity = store._cosine_similarity(v1, v2)
    assert abs(similarity - 1.0) < 0.01
