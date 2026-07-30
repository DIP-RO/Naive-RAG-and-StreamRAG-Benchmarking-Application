from __future__ import annotations

from contextvars import ContextVar
from uuid import uuid4

request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def new_request_id() -> str:
    return str(uuid4())
