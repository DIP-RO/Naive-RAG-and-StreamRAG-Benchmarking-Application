from __future__ import annotations

import pytest
from langsmith import traceable

from app.retrieval.chunker import Chunker


@pytest.mark.asyncio
@traceable(name="test_chunker_overlap")
async def test_chunker_emits_overlapping_chunks() -> None:
    chunker = Chunker(max_chars=50, overlap_sentences=1)
    text = "First sentence here. Second sentence follows. Third sentence content. Fourth sentence now. Fifth sentence present. Sixth sentence final."
    chunks = chunker.chunk_document(document_id="doc1", title="Test", content=text)
    assert len(chunks) >= 2
    if len(chunks) > 1:
        first_end = set(chunks[0].content.split())
        second_start = set(chunks[1].content.split()[:5])
        overlap = first_end & second_start
        assert len(overlap) > 0, (
            f"No overlap between chunks: {chunks[0].content[-40:]} || {chunks[1].content[:40]}"
        )


@pytest.mark.asyncio
@traceable(name="test_chunker_empty")
async def test_chunker_empty_content() -> None:
    chunker = Chunker()
    chunks = chunker.chunk_document(document_id="doc1", title="Empty", content="")
    assert chunks == []


@pytest.mark.asyncio
@traceable(name="test_chunker_single_sentence")
async def test_chunker_single_sentence() -> None:
    chunker = Chunker(max_chars=1200)
    chunks = chunker.chunk_document(
        document_id="doc1", title="Single", content="Just one sentence."
    )
    assert len(chunks) == 1
    assert "sentence" in chunks[0].content
