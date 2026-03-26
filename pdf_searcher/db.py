from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def _as_path(path: Path | str) -> Path:
    return path if isinstance(path, Path) else Path(path)


def _connect(path: Path | str) -> sqlite3.Connection:
    path = _as_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS saved_indexes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT NOT NULL,
            source TEXT NOT NULL,
            data TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    return conn


def save_index_to_db(index_data: dict, path: Path | str, label: str) -> int:
    conn = _connect(path)
    try:
        cursor = conn.execute(
            "INSERT INTO saved_indexes (label, source, data) VALUES (?, ?, ?)",
            (label, index_data.get("source", label), json.dumps(index_data, ensure_ascii=False)),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def load_index_from_db(path: Path | str, record_id: int) -> dict:
    conn = _connect(path)
    try:
        row = conn.execute(
            "SELECT data FROM saved_indexes WHERE id = ?",
            (record_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise ValueError(f"saved index not found: {record_id}")
    return json.loads(row["data"])


def get_saved_indexes(path: Path | str, limit: int = 50) -> list[dict]:
    conn = _connect(path)
    try:
        rows = conn.execute(
            """
            SELECT id, label, source, created_at
            FROM saved_indexes
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


def get_latest_saved_index(path: Path | str) -> dict | None:
    saved = get_saved_indexes(path, limit=1)
    return saved[0] if saved else None
