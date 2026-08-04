# -*- coding: utf-8 -*-
"""轻量 SQLite：分析历史记录"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from .config import DATA_DIR

DB_PATH = DATA_DIR / "app.db"


def _conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS reports (
        id TEXT PRIMARY KEY,
        kind TEXT,
        teacher TEXT,
        student TEXT,
        class_type TEXT,
        score REAL,
        full REAL,
        meta TEXT,
        created_at TEXT
    )""")
    return conn


def add_report(rid: str, kind: str, teacher: str, student: str, class_type: str,
               score: float, full: float, meta: dict):
    conn = _conn()
    conn.execute(
        "INSERT OR REPLACE INTO reports (id, kind, teacher, student, class_type, score, full, meta, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (rid, kind, teacher, student, class_type, score, full, json.dumps(meta, ensure_ascii=False),
         datetime.now().strftime("%Y-%m-%d %H:%M")),
    )
    conn.commit()
    conn.close()


def list_reports(kind: str | None = None, limit: int = 50) -> list[dict]:
    conn = _conn()
    if kind:
        rows = conn.execute("SELECT * FROM reports WHERE kind=? ORDER BY created_at DESC LIMIT ?", (kind, limit)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM reports ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_report(rid: str) -> dict | None:
    conn = _conn()
    row = conn.execute("SELECT * FROM reports WHERE id=?", (rid,)).fetchone()
    conn.close()
    return dict(row) if row else None
