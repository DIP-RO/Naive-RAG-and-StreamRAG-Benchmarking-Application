from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import AppSettings
from app.models.schemas import ChatMessage


class LLMClient(Protocol):
    async def generate_text(self, messages: list[ChatMessage], *, model: str, max_tokens: int) -> tuple[str, dict[str, int]]:
        ...

    def stream_text(self, messages: list[ChatMessage], *, model: str, max_tokens: int) -> AsyncIterator[str]:
        ...


@dataclass(slots=True)
class OpenAIChatClient:
    api_key: str

    @retry(wait=wait_exponential(min=1, max=8), stop=stop_after_attempt(3), retry=retry_if_exception_type(Exception))
    async def generate_text(self, messages: list[ChatMessage], *, model: str, max_tokens: int) -> tuple[str, dict[str, int]]:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.api_key, http_client=httpx.AsyncClient(timeout=60.0))
        response = await client.chat.completions.create(
            model=model,
            messages=[message.model_dump(exclude_none=True) for message in messages],
            max_tokens=max_tokens,
            temperature=0.2,
        )
        text = response.choices[0].message.content or ""
        usage = {
            "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
            "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            "total_tokens": response.usage.total_tokens if response.usage else 0,
        }
        return text, usage

    async def stream_text(self, messages: list[ChatMessage], *, model: str, max_tokens: int) -> AsyncIterator[str]:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.api_key, http_client=httpx.AsyncClient(timeout=60.0))
        stream = await client.chat.completions.create(
            model=model,
            messages=[message.model_dump(exclude_none=True) for message in messages],
            max_tokens=max_tokens,
            temperature=0.2,
            stream=True,
        )
        async for event in stream:
            delta = event.choices[0].delta.content if event.choices else None
            if delta:
                yield delta


@dataclass(slots=True)
class OpenRouterChatClient:
    api_key: str
    base_url: str = "https://openrouter.ai/api/v1"
    app_name: str = "Applied AI Engineer Assessment"
    referer: str | None = None

    async def generate_text(self, messages: list[ChatMessage], *, model: str, max_tokens: int) -> tuple[str, dict[str, int]]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [message.model_dump(exclude_none=True) for message in messages],
            "max_tokens": max_tokens,
            "temperature": 0.2,
            "reasoning": {"enabled": True},
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Title": self.app_name,
        }
        if self.referer:
            headers["HTTP-Referer"] = self.referer
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        choice = data["choices"][0]["message"]
        usage_payload = data.get("usage") or {}
        return choice.get("content") or "", {
            "prompt_tokens": int(usage_payload.get("prompt_tokens", 0)),
            "completion_tokens": int(usage_payload.get("completion_tokens", 0)),
            "total_tokens": int(usage_payload.get("total_tokens", 0)),
        }

    async def stream_text(self, messages: list[ChatMessage], *, model: str, max_tokens: int) -> AsyncIterator[str]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [message.model_dump(exclude_none=True) for message in messages],
            "max_tokens": max_tokens,
            "temperature": 0.2,
            "stream": True,
            "reasoning": {"enabled": True},
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Title": self.app_name,
        }
        if self.referer:
            headers["HTTP-Referer"] = self.referer
        async with httpx.AsyncClient(timeout=60.0) as client, client.stream("POST", f"{self.base_url}/chat/completions", headers=headers, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data = line.removeprefix("data: ")
                    if data == "[DONE]":
                        break
                    event = json.loads(data)
                    delta = event.get("choices", [{}])[0].get("delta", {}).get("content")
                    if delta:
                        yield delta


@dataclass(slots=True)
class EchoLLMClient:
    """Deterministic fallback for local development and tests."""

    async def generate_text(self, messages: list[ChatMessage], *, model: str, max_tokens: int) -> tuple[str, dict[str, int]]:
        user_message = next((message.content for message in reversed(messages) if message.role == "user"), "")
        answer = f"Fallback answer for: {user_message}"
        return answer, {"prompt_tokens": sum(len(message.content) for message in messages) // 4, "completion_tokens": len(answer) // 4, "total_tokens": 0}

    async def stream_text(self, messages: list[ChatMessage], *, model: str, max_tokens: int) -> AsyncIterator[str]:
        answer, _ = await self.generate_text(messages, model=model, max_tokens=max_tokens)
        for token in answer.split():
            yield token + " "


class LLMFactory:
    @staticmethod
    def build(settings: AppSettings) -> LLMClient:
        if settings.default_llm_provider == "openrouter" and settings.openrouter_api_key:
            return OpenRouterChatClient(
                api_key=settings.openrouter_api_key,
                base_url=settings.openrouter_base_url,
                app_name=settings.openrouter_app_name,
                referer=settings.openrouter_referer,
            )
        if settings.default_llm_provider == "openrouter" and settings.openai_api_key:
            return OpenAIChatClient(api_key=settings.openai_api_key)
        if settings.default_llm_provider == "openai" and settings.openai_api_key:
            return OpenAIChatClient(api_key=settings.openai_api_key)
        if settings.default_llm_provider == "anthropic" and settings.anthropic_api_key:
            return EchoLLMClient()
        if settings.default_llm_provider == "google" and settings.google_api_key:
            return EchoLLMClient()
        return EchoLLMClient()


class JsonLLM:
    def __init__(self, client: LLMClient, model: str) -> None:
        self.client = client
        self.model = model

    async def generate(self, messages: list[ChatMessage], schema_name: str) -> dict[str, Any]:
        prompt = messages + [
            ChatMessage(
                role="system",
                content=(
                    "Return valid JSON only. "
                    f"Schema name: {schema_name}. "
                    "Do not include markdown, code fences, or commentary."
                ),
            )
        ]
        text, _ = await self.client.generate_text(prompt, model=self.model, max_tokens=800)
        return json.loads(text)
