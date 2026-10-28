"""SQLite persistence: documents (ledger + review queue) and an event log."""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from .config import DB_PATH

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY,
  filename TEXT NOT NULL,
  stored_path TEXT,
  file_hash TEXT,
  status TEXT NOT NULL,
  kind TEXT,
  data_json TEXT,
  original_json TEXT,
  category TEXT,
  category_source TEXT,
  issues_json TEXT,
  confidence REAL,
  provider TEXT,
  model TEXT,
  attempts INTEGER,
  latency_ms INTEGER,
  tokens_in INTEGER,
  tokens_out INTEGER,
  cost_usd REAL,
  trace_json TEXT,
  edited_fields TEXT,
  reviewer_note TEXT,
  created_at TEXT,
  reviewed_at TEXT
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT, doc_id TEXT, level TEXT, step TEXT, message TEXT
);
"""

JSON_COLS = {"data_json": "data", "original_json": "original", "issues_json": "issues",
             "trace_json": "trace", "edited_fields": "edited_fields"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: Path | str = DB_PATH):
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def _row(self, r: sqlite3.Row | None) -> dict | None:
        if r is None:
            return None
        d = dict(r)
        for col, key in JSON_COLS.items():
            raw = d.pop(col, None)
            d[key] = json.loads(raw) if raw else None
        return d

    def save(self, rec: dict) -> None:
        row = dict(rec)
        for col, key in JSON_COLS.items():
            if key in row:
                row[col] = json.dumps(row.pop(key)) if row.get(key) is not None else None
        cols = ", ".join(row)
        qs = ", ".join("?" for _ in row)
        with _lock:
            self.conn.execute(f"INSERT OR REPLACE INTO documents ({cols}) VALUES ({qs})", list(row.values()))
            self.conn.commit()

    def update(self, doc_id: str, **fields) -> None:
        for col, key in JSON_COLS.items():
            if key in fields:
                fields[col] = json.dumps(fields.pop(key))
        sets = ", ".join(f"{k} = ?" for k in fields)
        with _lock:
            self.conn.execute(f"UPDATE documents SET {sets} WHERE id = ?", [*fields.values(), doc_id])
            self.conn.commit()

    def get(self, doc_id: str) -> dict | None:
        return self._row(self.conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone())

    def list(self, statuses: list[str] | None = None, limit: int = 500) -> list[dict]:
        if statuses:
            q = f"SELECT * FROM documents WHERE status IN ({','.join('?' * len(statuses))}) ORDER BY created_at DESC LIMIT ?"
            rows = self.conn.execute(q, [*statuses, limit]).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM documents ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [self._row(r) for r in rows]

    def delete(self, doc_id: str) -> None:
        with _lock:
            self.conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            self.conn.commit()

    def reset(self) -> None:
        with _lock:
            self.conn.execute("DELETE FROM documents")
            self.conn.execute("DELETE FROM events")
            self.conn.commit()

    # ---- events ---------------------------------------------------------
    def log(self, doc_id: str | None, level: str, step: str, message: str) -> None:
        with _lock:
            self.conn.execute("INSERT INTO events (ts, doc_id, level, step, message) VALUES (?,?,?,?,?)",
                              (now(), doc_id, level, step, message))
            self.conn.commit()

    def events(self, limit: int = 300) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]
