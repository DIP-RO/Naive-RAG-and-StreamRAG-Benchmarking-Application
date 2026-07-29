from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol

import httpx


class EmbeddingProvider(Protocol):
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...


@dataclass(slots=True)
class OpenAIEmbeddingProvider:
    api_key: str
    model: str = "text-embedding-3-small"
    dimensions: int = 1536

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.api_key, http_client=httpx.AsyncClient(timeout=30.0))
        response = await client.embeddings.create(model=self.model, input=texts)
        return [item.embedding for item in response.data]


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
