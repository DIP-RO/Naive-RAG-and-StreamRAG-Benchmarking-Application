from __future__ import annotations

import pytest
from langsmith import traceable

from app.retrieval.chunker import Chunker
from app.retrieval.embeddings import DeterministicEmbeddingProvider


@pytest.mark.asyncio
@traceable(name="test_embeddings_consistent")
async def test_deterministic_embeddings_produce_consistent_vectors() -> None:
    provider = DeterministicEmbeddingProvider(dimensions=128)
    vectors = await provider.embed_texts(["hello world", "hello world"])
    assert len(vectors) == 2
    assert vectors[0] == vectors[1]
    assert len(vectors[0]) == 128


@pytest.mark.asyncio
@traceable(name="test_embeddings_differ")
async def test_deterministic_embeddings_different_texts_differ() -> None:
    provider = DeterministicEmbeddingProvider(dimensions=128)
    vectors = await provider.embed_texts(["hello world", "goodbye world"])
    assert vectors[0] != vectors[1]


@pytest.mark.asyncio
@traceable(name="test_chunker_with_overlap_embedding")
async def test_chunker_with_overlap() -> None:
    chunker = Chunker(max_chars=20, overlap_sentences=1)
    text = "First paragraph content here. Second paragraph here too. Third paragraph in this doc. Fourth paragraph now."
    chunks = chunker.chunk_document(document_id="d1", title="Test", content=text)
    assert len(chunks) >= 2


@pytest.mark.asyncio
@traceable(name="test_chunker_empty_embedding")
async def test_chunker_empty_content() -> None:
    chunker = Chunker()
    chunks = chunker.chunk_document(document_id="d1", title="Empty", content="")
    assert chunks == []


@pytest.mark.asyncio
@traceable(name="test_chunker_single_embedding")
async def test_chunker_single_sentence() -> None:
    chunker = Chunker(max_chars=1200)
    chunks = chunker.chunk_document(document_id="d1", title="Single", content="Just one sentence.")
    assert len(chunks) == 1
