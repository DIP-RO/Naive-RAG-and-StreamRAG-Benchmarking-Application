from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import AppSettings, get_settings
from app.core.container import build_container
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware

logger = logging.getLogger(__name__)


def _init_langsmith(settings: AppSettings) -> None:
    if settings.langchain_api_key:
        os.environ.setdefault(
            "LANGCHAIN_TRACING_V2", "true" if settings.langchain_tracing_v2 else "false"
        )
        os.environ.setdefault("LANGCHAIN_API_KEY", settings.langchain_api_key)
        os.environ.setdefault("LANGCHAIN_PROJECT", settings.langchain_project)
        logger.info("langsmith_tracing_enabled project=%s", settings.langchain_project)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    _init_langsmith(settings)
    configure_logging(settings)
    container = await build_container(settings)
    app.state.container = container
    yield
    await container.close()


app = FastAPI(title="Applied AI Engineer Assessment", lifespan=lifespan)
settings = get_settings()
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix=settings.api_prefix)


def run() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
