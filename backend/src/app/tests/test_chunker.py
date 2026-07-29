from __future__ import annotations

from app.retrieval.chunker import Chunker


def test_chunker_emits_overlapping_chunks() -> None:
    chunker = Chunker(max_chars=40, overlap_sentences=1)
    chunks = chunker.chunk_document(
        document_id="doc-1",
        title="Doc",
        content="Sentence one. Sentence two. Sentence three. Sentence four.",
    )
    assert len(chunks) >= 2
    assert chunks[0].document_id == "doc-1"
