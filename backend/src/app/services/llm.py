from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.config import AppSettings
from app.models.schemas import ChatMessage
from app.utils.http_client import SHARED_HTTP_CLIENT

_LANGCHAIN_ROLE_MAP: dict[str, type[BaseMessage]] = {
    "system": SystemMessage,
    "user": HumanMessage,
    "assistant": AIMessage,
}


def _to_langchain(messages: list[ChatMessage]) -> list[BaseMessage]:
    result: list[BaseMessage] = []
    for msg in messages:
        cls = _LANGCHAIN_ROLE_MAP.get(msg.role)
        if cls:
            result.append(cls(content=msg.content))
    return result


def _extract_usage(response: Any) -> dict[str, int]:
    if response is None:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    usage = getattr(response, "usage_metadata", None) or {}
    return {
        "prompt_tokens": usage.get("input_tokens", 0),
        "completion_tokens": usage.get("output_tokens", 0),
        "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
    }


class LLMClient(Protocol):
    async def generate_text(
        self, messages: list[ChatMessage], *, model: str, max_tokens: int
    ) -> tuple[str, dict[str, int]]: ...

    def stream_text(
        self, messages: list[ChatMessage], *, model: str, max_tokens: int
    ) -> AsyncIterator[str]: ...


@dataclass
class LangChainChatClient:
    """LangChain-based LLM client supporting OpenAI and OpenRouter."""

    api_key: str
    base_url: str | None = None
    default_model: str = "gpt-4.1"

    def _build_llm(self, model: str, max_tokens: int) -> BaseChatModel:
        kwargs: dict[str, Any] = {
            "api_key": self.api_key,
            "model": model,
            "temperature": 0.2,
            "max_tokens": max_tokens,
            "http_client": SHARED_HTTP_CLIENT,
        }
        if self.base_url:
            kwargs["base_url"] = self.base_url
        return ChatOpenAI(**kwargs)

    async def generate_text(
        self, messages: list[ChatMessage], *, model: str, max_tokens: int
    ) -> tuple[str, dict[str, int]]:
        llm = self._build_llm(model, max_tokens)
        lc_messages = _to_langchain(messages)
        response = await llm.ainvoke(lc_messages)
        usage = _extract_usage(response)
        return response.content if isinstance(response.content, str) else "", usage

    async def stream_text(
        self, messages: list[ChatMessage], *, model: str, max_tokens: int
    ) -> AsyncIterator[str]:
        llm = self._build_llm(model, max_tokens)
        lc_messages = _to_langchain(messages)
        async for chunk in llm.astream(lc_messages):
            content = chunk.content if isinstance(chunk.content, str) else ""
            if content:
                yield content


@dataclass
class OpenRouterClient:
    """Direct OpenRouter client using httpx (used as fallback/reference)."""

    api_key: str
    base_url: str = "https://openrouter.ai/api/v1"
    app_name: str = "Applied AI Engineer Assessment"
    referer: str | None = None

    async def generate_text(
        self, messages: list[ChatMessage], *, model: str, max_tokens: int
    ) -> tuple[str, dict[str, int]]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": max_tokens,
            "temperature": 0.2,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Title": self.app_name,
        }
        if self.referer:
            headers["HTTP-Referer"] = self.referer
        response = await SHARED_HTTP_CLIENT.post(
            f"{self.base_url}/chat/completions", headers=headers, json=payload
        )
        response.raise_for_status()
        data = response.json()
        choice = data["choices"][0]["message"]
        usage_payload = data.get("usage") or {}
        return choice.get("content") or "", {
            "prompt_tokens": int(usage_payload.get("prompt_tokens", 0)),
            "completion_tokens": int(usage_payload.get("completion_tokens", 0)),
            "total_tokens": int(usage_payload.get("total_tokens", 0)),
        }

    async def stream_text(
        self, messages: list[ChatMessage], *, model: str, max_tokens: int
    ) -> AsyncIterator[str]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": max_tokens,
            "temperature": 0.2,
            "stream": True,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Title": self.app_name,
        }
        if self.referer:
            headers["HTTP-Referer"] = self.referer
        async with SHARED_HTTP_CLIENT.stream(
            "POST", f"{self.base_url}/chat/completions", headers=headers, json=payload
        ) as response:
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


@dataclass
class EchoLLMClient:
    """Deterministic fallback for local development and tests.
    Returns tool results when present in the context, otherwise echoes the user query."""

    async def generate_text(
        self, messages: list[ChatMessage], *, model: str, max_tokens: int
    ) -> tuple[str, dict[str, int]]:
        system_msg = next(
            (message.content for message in messages if message.role == "system"), ""
        )
        tool_results = self._extract_tool_results(system_msg)
        if tool_results:
            answer = tool_results
        else:
            user_message = next(
                (message.content for message in reversed(messages) if message.role == "user"), ""
            )
            answer = f"Fallback answer for: {user_message}"
        return answer, {
            "prompt_tokens": sum(len(message.content) for message in messages) // 4,
            "completion_tokens": len(answer) // 4,
            "total_tokens": 0,
        }

    async def stream_text(
        self, messages: list[ChatMessage], *, model: str, max_tokens: int
    ) -> AsyncIterator[str]:
        answer, _ = await self.generate_text(messages, model=model, max_tokens=max_tokens)
        for token in answer.split():
            yield token + " "

    @staticmethod
    def _extract_tool_results(system_text: str) -> str | None:
        results: list[str] = []
        for line in system_text.split("\n"):
            line = line.strip()
            if line.startswith("[tool:") and "]" in line:
                colon = line.index("]")
                content = line[colon + 1:].strip()
                if content:
                    results.append(content)
        if results:
            return "\n".join(results)
        evidence_prefix = "Retrieved evidence:"
        if evidence_prefix in system_text:
            idx = system_text.index(evidence_prefix)
            evidence = system_text[idx + len(evidence_prefix):].strip()
            chunks = []
            for line in evidence.split("\n"):
                line = line.strip()
                if line.startswith("[") and "]" in line:
                    colon = line.index("]")
                    title = line[1:colon]
                    content = line[colon + 1:].strip()
                    if content:
                        chunks.append(f"[{title}] {content[:200]}")
            if chunks:
                return "\n\n".join(chunks[:2])
        return None


class LLMFactory:
    @staticmethod
    def build(settings: AppSettings) -> LLMClient:
        provider = settings.default_llm_provider
        if provider == "openrouter" and settings.openrouter_api_key:
            return LangChainChatClient(
                api_key=settings.openrouter_api_key,
                base_url=settings.openrouter_base_url.rstrip("/") + "/v1",
            )
        if provider == "openai" and settings.openai_api_key:
            return LangChainChatClient(api_key=settings.openai_api_key)
        return EchoLLMClient()
