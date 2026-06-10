from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .config import get_settings


@contextmanager
def connect() -> Iterator[psycopg.Connection]:
    connection = psycopg.connect(get_settings().database_url, row_factory=dict_row)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db() -> None:
    with connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ideas (
                id SERIAL PRIMARY KEY,
                author TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                tags JSONB NOT NULL DEFAULT '[]'::jsonb,
                analysis JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                processed_at TIMESTAMPTZ
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_ideas_status_created
            ON ideas (status, created_at DESC)
            """
        )


def serialize_idea(row: dict[str, Any]) -> dict[str, Any]:
    serialized = dict(row)
    for key in ("created_at", "processed_at"):
        value = serialized.get(key)
        if isinstance(value, datetime):
            serialized[key] = value.astimezone(timezone.utc).isoformat()
    return serialized


def create_idea(author: str, title: str, description: str) -> dict[str, Any]:
    with connect() as connection:
        row = connection.execute(
            """
            INSERT INTO ideas (author, title, description)
            VALUES (%s, %s, %s)
            RETURNING id, author, title, description, status, tags, analysis, created_at, processed_at
            """,
            (author, title, description),
        ).fetchone()
    return serialize_idea(row)


def list_ideas(limit: int = 30) -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT id, author, title, description, status, tags, analysis, created_at, processed_at
            FROM ideas
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (limit,),
        ).fetchall()
    return [serialize_idea(row) for row in rows]


def get_idea(idea_id: int) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT id, author, title, description, status, tags, analysis, created_at, processed_at
            FROM ideas
            WHERE id = %s
            """,
            (idea_id,),
        ).fetchone()
    return serialize_idea(row) if row else None


def update_status(idea_id: int, status: str) -> None:
    with connect() as connection:
        connection.execute(
            """
            UPDATE ideas
            SET status = %s
            WHERE id = %s
            """,
            (status, idea_id),
        )


def finish_idea(idea_id: int, tags: list[str], analysis: dict[str, Any]) -> None:
    with connect() as connection:
        connection.execute(
            """
            UPDATE ideas
            SET status = 'done',
                tags = %s,
                analysis = %s,
                processed_at = NOW()
            WHERE id = %s
            """,
            (Jsonb(tags), Jsonb(analysis), idea_id),
        )


def fail_idea(idea_id: int, message: str) -> None:
    with connect() as connection:
        connection.execute(
            """
            UPDATE ideas
            SET status = 'failed',
                analysis = %s,
                processed_at = NOW()
            WHERE id = %s
            """,
            (Jsonb({"erro": message}), idea_id),
        )


def idea_counts_by_status() -> dict[str, int]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT status, COUNT(*) AS total
            FROM ideas
            GROUP BY status
            """
        ).fetchall()
    return {row["status"]: row["total"] for row in rows}


def database_ping() -> bool:
    with connect() as connection:
        connection.execute("SELECT 1")
    return True
