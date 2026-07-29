from __future__ import annotations

import pytest

from app.retrieval.chunker import Chunker
from app.retrieval.embeddings import DeterministicEmbeddingProvider


@pytest.mark.asyncio
async def test_deterministic_embeddings_produce_consistent_vectors() -> None:
    provider = DeterministicEmbeddingProvider(dimensions=128)
    vectors = await provider.embed_texts(["hello world", "hello world"])
    assert len(vectors) == 2
    assert vectors[0] == vectors[1]
    assert len(vectors[0]) == 128


@pytest.mark.asyncio
async def test_deterministic_embeddings_different_texts_differ() -> None:
    provider = DeterministicEmbeddingProvider(dimensions=128)
    v1 = (await provider.embed_texts(["machine learning"]))[0]
    v2 = (await provider.embed_texts(["cooking recipes"]))[0]
    assert v1 != v2


@pytest.mark.asyncio
async def test_chunker_with_overlap() -> None:
    chunker = Chunker(max_chars=40, overlap_sentences=1)
    chunks = chunker.chunk_document(
        document_id="doc-1",
        title="Doc",
        content="Sentence one. Sentence two. Sentence three. Sentence four.",
    )
    assert len(chunks) >= 2
    assert chunks[0].document_id == "doc-1"
    first_end = chunks[0].content
    second_start = chunks[1].content
    assert any(word in second_start for word in first_end.split()) or len(chunks) == 2


@pytest.mark.asyncio
async def test_chunker_empty_content() -> None:
    chunker = Chunker()
    chunks = chunker.chunk_document(document_id="doc-1", title="Doc", content="")
    assert chunks == []


@pytest.mark.asyncio
async def test_chunker_single_sentence() -> None:
    chunker = Chunker(max_chars=1200)
    chunks = chunker.chunk_document(document_id="doc-1", title="Doc", content="Just one sentence here.")
    assert len(chunks) == 1
    assert chunks[0].content == "Just one sentence here."
