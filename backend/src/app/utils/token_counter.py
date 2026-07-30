from __future__ import annotations

from functools import lru_cache

try:
    import tiktoken
except Exception:  # noqa: BLE001  # pragma: no cover - optional dependency
    tiktoken = None


@lru_cache(maxsize=8)
def _encoding(model: str):
    if tiktoken is None:
        return None
    try:
        return tiktoken.encoding_for_model(model)
    except Exception:  # noqa: BLE001
        return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str, model: str = "gpt-4.1") -> int:
    """Approximate token count with an exact path when tiktoken is installed."""

    encoding = _encoding(model)
    if encoding is None:
        return max(1, len(text) // 4)
    return len(encoding.encode(text))


def count_messages(messages: list[str], model: str = "gpt-4.1") -> int:
    return sum(count_tokens(message, model=model) for message in messages)
