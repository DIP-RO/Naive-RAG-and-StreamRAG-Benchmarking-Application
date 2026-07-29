from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import aiosqlite

from app.models.schemas import ChatMessage


@dataclass(slots=True)
class ConversationSummary:
    conversation_id: str
    summary: str
    updated_at: str


class ConversationStore:
    """SQLite-backed conversation history and summary store."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

    async def initialize(self) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tool_name TEXT,
                    metadata TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_summaries (
                    conversation_id TEXT PRIMARY KEY,
                    summary TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await db.commit()

    async def append(self, conversation_id: str, message: ChatMessage) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                INSERT INTO conversation_messages (conversation_id, role, content, tool_name, metadata)
                VALUES (?, ?, ?, ?, ?)
                """,
                (conversation_id, message.role, message.content, message.tool_name, json.dumps(message.metadata)),
            )
            await db.commit()

    async def fetch_history(self, conversation_id: str, limit: int = 30) -> list[ChatMessage]:
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                """
                SELECT role, content, tool_name, metadata
                FROM conversation_messages
                WHERE conversation_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (conversation_id, limit),
            )
            rows = await cursor.fetchall()
        return [
            ChatMessage(
                role=row[0],
                content=row[1],
                tool_name=row[2],
                metadata=json.loads(row[3]),
            )
            for row in reversed(rows)
        ]

    async def store_summary(self, conversation_id: str, summary: str) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                INSERT INTO conversation_summaries (conversation_id, summary, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(conversation_id) DO UPDATE SET
                    summary = excluded.summary,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (conversation_id, summary),
            )
            await db.commit()

    async def get_summary(self, conversation_id: str) -> ConversationSummary | None:
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "SELECT conversation_id, summary, updated_at FROM conversation_summaries WHERE conversation_id = ?",
                (conversation_id,),
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        return ConversationSummary(conversation_id=row[0], summary=row[1], updated_at=row[2])
