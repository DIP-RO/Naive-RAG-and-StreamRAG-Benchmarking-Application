from __future__ import annotations

import json
import re as _re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
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
class GoogleGenAIClient:
    """LangChain-based client for Google Gemini models with fallback keys."""

    api_key: str
    fallback_api_key: str | None = None
    fallback_api_key_2: str | None = None
    default_model: str = "gemini-flash-latest"

    def _all_keys(self) -> list[str]:
        keys = [self.api_key]
        if self.fallback_api_key:
            keys.append(self.fallback_api_key)
        if self.fallback_api_key_2:
            keys.append(self.fallback_api_key_2)
        return keys

    def _build_llm(self, model: str, max_tokens: int) -> ChatGoogleGenerativeAI:
        return ChatGoogleGenerativeAI(
            api_key=self.api_key,
            model=model,
            temperature=0.2,
            max_output_tokens=max_tokens,
        )

    async def _try_generate(
        self, api_key: str, messages: list[ChatMessage], model: str, max_tokens: int
    ) -> str:
        llm = ChatGoogleGenerativeAI(
            api_key=api_key, model=model, temperature=0.2, max_output_tokens=max_tokens
        )
        lc_messages = _to_langchain(messages)
        response = await llm.ainvoke(lc_messages)
        if isinstance(response.content, str):
            return response.content
        if isinstance(response.content, list):
            return " ".join(p.get("text", "") for p in response.content if isinstance(p, dict))
        return ""

    async def generate_text(
        self, messages: list[ChatMessage], *, model: str, max_tokens: int
    ) -> tuple[str, dict[str, int]]:
        keys = self._all_keys()
        last_error: Exception | None = None
        for key in keys:
            try:
                text = await self._try_generate(key, messages, model, max_tokens)
                return text, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            except Exception as exc:  # noqa: BLE001
                last_error = exc
        raise last_error  # type: ignore[misc]

    async def _try_stream(
        self, api_key: str, messages: list[ChatMessage], model: str, max_tokens: int
    ) -> AsyncIterator[str]:
        llm = ChatGoogleGenerativeAI(
            api_key=api_key, model=model, temperature=0.2, max_output_tokens=max_tokens
        )
        lc_messages = _to_langchain(messages)
        async for chunk in llm.astream(lc_messages):
            if isinstance(chunk.content, str):
                text = chunk.content
            elif isinstance(chunk.content, list):
                parts = [p.get("text", "") for p in chunk.content if isinstance(p, dict)]
                text = " ".join(parts)
            else:
                text = ""
            if text:
                yield text

    async def stream_text(
        self, messages: list[ChatMessage], *, model: str, max_tokens: int
    ) -> AsyncIterator[str]:
        keys = self._all_keys()
        last_error: Exception | None = None
        for key in keys:
            try:
                async for text in self._try_stream(key, messages, model, max_tokens):
                    yield text
                return
            except Exception as exc:  # noqa: BLE001
                last_error = exc
        raise last_error  # type: ignore[misc]


@dataclass
class EchoLLMClient:
    """Deterministic fallback for local development and tests.
    Returns tool results when present in the context, otherwise echoes the user query."""

    async def generate_text(
        self, messages: list[ChatMessage], *, model: str, max_tokens: int
    ) -> tuple[str, dict[str, int]]:
        user_message = next(
            (message.content for message in reversed(messages) if message.role == "user"), ""
        )
        all_system = [m.content for m in messages if m.role == "system"]
        system_text = all_system[-1] if all_system else ""

        answer = None
        for line in system_text.split("\n"):
            line = line.strip()
            if line.startswith("[tool:") and "]" in line:
                colon = line.index("]")
                content = line[colon + 1 :].strip()
                if content:
                    answer = content
        if answer:
            return answer, {
                "prompt_tokens": 0,
                "completion_tokens": len(answer) // 4,
                "total_tokens": 0,
            }

        evidence_prefix = "Retrieved evidence:"
        if evidence_prefix in system_text:
            idx = system_text.index(evidence_prefix)
            evidence = system_text[idx + len(evidence_prefix) :].strip()
            candidates = []
            raw_lines = evidence.split("\n")
            i = 0
            while i < len(raw_lines):
                line = raw_lines[i].strip()
                if not line.startswith("["):
                    i += 1
                    continue
                if "]" not in line:
                    i += 1
                    continue
                colon = line.index("]")
                title = line[1:colon]
                if title.startswith("skill:"):
                    i += 1
                    continue
                content = line[colon + 1 :].strip()
                i += 1
                while i < len(raw_lines):
                    nxt = raw_lines[i].strip()
                    if nxt.startswith("["):
                        break
                    if nxt:
                        content += " " + nxt
                    i += 1
                if not content:
                    continue
                qt = {t.strip("?,.;:!\"'()[]{}-") for t in user_message.lower().split()} - {""}
                ct = {t.strip("?,.;:!\"'()[]{}-") for t in content.lower().split()} - {""}
                tt = {w for w in _re.split(r"[^a-z0-9]+", title.lower()) if w}
                cs = len(qt & ct)
                tss = len(qt & tt)
                candidates.append((cs, tss, title, content))
            if candidates:
                _stop = {
                    "the",
                    "a",
                    "an",
                    "is",
                    "are",
                    "was",
                    "were",
                    "be",
                    "been",
                    "being",
                    "have",
                    "has",
                    "had",
                    "do",
                    "does",
                    "did",
                    "will",
                    "would",
                    "shall",
                    "should",
                    "may",
                    "might",
                    "can",
                    "could",
                    "of",
                    "in",
                    "on",
                    "at",
                    "to",
                    "for",
                    "with",
                    "by",
                    "from",
                    "up",
                    "about",
                    "into",
                    "over",
                    "after",
                    "and",
                    "or",
                    "but",
                    "not",
                    "so",
                    "if",
                    "it",
                    "its",
                    "this",
                    "that",
                    "these",
                    "those",
                    "i",
                    "you",
                    "he",
                    "she",
                    "we",
                    "they",
                    "me",
                    "my",
                    "your",
                    "his",
                    "her",
                    "our",
                    "their",
                    "what",
                    "which",
                    "who",
                    "whom",
                    "when",
                    "where",
                    "why",
                    "how",
                    "all",
                    "each",
                    "every",
                    "both",
                    "few",
                    "more",
                    "most",
                    "some",
                    "any",
                    "no",
                    "nor",
                    "too",
                    "very",
                    "just",
                    "also",
                    "as",
                    "than",
                    "then",
                    "now",
                }
                qt = {t.strip("?,.;:!\"'()[]{}-") for t in user_message.lower().split()} - {""}
                meaningful = qt - _stop
                if meaningful:
                    scored: list[tuple[int, str, str]] = []
                    for _, _, cand_title, cand_content in candidates:
                        ct = {t.strip("?,.;:!\"'()[]{}-") for t in cand_content.lower().split()} - {
                            ""
                        }
                        tt = {w for w in _re.split(r"[^a-z0-9]+", cand_title.lower()) if w}
                        exact_matched = meaningful & ct
                        title_matched = meaningful & tt
                        fuzzy_ct = ct - exact_matched
                        fuzzy_tt = tt - title_matched
                        extra = 0
                        for h in fuzzy_ct:
                            if len(h) < 3:
                                continue
                            for n in meaningful:
                                if len(n) >= 3 and h in n and n not in exact_matched:
                                    extra += 1
                                    break
                        for h in fuzzy_tt:
                            if len(h) < 3:
                                continue
                            for n in meaningful:
                                if len(n) >= 3 and h in n and n not in title_matched:
                                    extra += 1
                                    break
                        if len(exact_matched) + len(title_matched) + extra >= 2:
                            score = extra * 3 + len(exact_matched) * 2 + len(title_matched)
                            scored.append((score, cand_title, cand_content))
                    if scored:
                        scored.sort(key=lambda x: x[0], reverse=True)
                        best_title, best_content = scored[0][1], scored[0][2]
                        answer = f"[{best_title}] {best_content[:2000]}"

        if not answer:
            topics = [
                "machine learning",
                "deep learning architectures",
                "RAG techniques",
                "company overview (Next Ventures)",
                "climate change",
                "weather",
                "renewable energy",
                "database systems",
                "cybersecurity",
                "AI ethics",
                "calculator",
                "date/time",
                "weather forecasts",
            ]
            answer = (
                "I don't have information about that in my current knowledge base. "
                "I can help with topics like: "
                f"{', '.join(topics)}. "
                "Please ask about one of these topics."
            )
        return answer, {
            "prompt_tokens": sum(len(m.content) for m in messages) // 4,
            "completion_tokens": len(answer) // 4,
            "total_tokens": 0,
        }

    async def stream_text(
        self, messages: list[ChatMessage], *, model: str, max_tokens: int
    ) -> AsyncIterator[str]:
        answer, _ = await self.generate_text(messages, model=model, max_tokens=max_tokens)
        for token in answer.split():
            yield token + " "


class LLMFactory:
    @staticmethod
    def build(settings: AppSettings) -> LLMClient:
        provider = settings.default_llm_provider
        if provider == "google" and settings.google_api_key:
            return GoogleGenAIClient(
                api_key=settings.google_api_key,
                fallback_api_key=settings.google_api_key_fallback,
                fallback_api_key_2=settings.google_api_key_fallback_2,
            )
        if provider == "openrouter" and settings.openrouter_api_key:
            return LangChainChatClient(
                api_key=settings.openrouter_api_key,
                base_url=settings.openrouter_base_url.rstrip("/"),
            )
        if provider == "openai" and settings.openai_api_key:
            return LangChainChatClient(api_key=settings.openai_api_key)
        return EchoLLMClient()
