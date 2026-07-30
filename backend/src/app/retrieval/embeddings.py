from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol

from openai import AsyncOpenAI

from app.utils.http_client import SHARED_HTTP_CLIENT


class EmbeddingProvider(Protocol):
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...


@dataclass
class OpenAIEmbeddingProvider:
    api_key: str
    model: str = "text-embedding-3-small"
    dimensions: int = 1536
    _client: AsyncOpenAI | None = None

    def __post_init__(self) -> None:
        self._client = AsyncOpenAI(api_key=self.api_key, http_client=SHARED_HTTP_CLIENT)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        assert self._client is not None
        BATCH_SIZE = 500
        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i : i + BATCH_SIZE]
            response = await self._client.embeddings.create(model=self.model, input=batch)
            all_embeddings.extend(item.embedding for item in response.data)
        return all_embeddings


class DeterministicEmbeddingProvider:
    """Offline-friendly fallback for tests and local demos."""

    def __init__(self, dimensions: int = 128) -> None:
        self.dimensions = dimensions

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_text(text) for text in texts]

    def _embed_text(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            vector[index] += 1.0
        norm = sum(value * value for value in vector) ** 0.5 or 1.0
        return [value / norm for value in vector]
