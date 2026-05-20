"""
SQLite persistence layer for Rubric.

Tables:
  hymn_cache    — title lookups keyed by "VU16", "MV42", etc.
  snippets      — named text snippets in display order
  service_index — cached .liturgy file metadata for fast Service Planner loading

The .liturgy service files remain as JSON on disk (portable, git-friendly).
The index stores each file's mtime so stale entries are re-read automatically.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DB_PATH = Path.home() / ".local/share/rubric" / "rubric.db"

_SCHEMA = """\
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS hymn_cache (
    key   TEXT PRIMARY KEY,
    title TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS snippets (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    content    TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS service_index (
    path       TEXT PRIMARY KEY,
    title      TEXT NOT NULL DEFAULT '',
    date       TEXT NOT NULL DEFAULT '',
    item_count INTEGER NOT NULL DEFAULT 0,
    mtime      REAL  NOT NULL DEFAULT 0
);
"""


def _open() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    """Create tables and enable WAL mode. Call once at application startup."""
    con = _open()
    try:
        con.executescript(_SCHEMA)
    finally:
        con.close()


# ── Hymn cache ────────────────────────────────────────────────────────────────

def hymn_get(key: str) -> str | None:
    """Return a cached hymn title for key (e.g. 'VU16'), or None if not cached."""
    con = _open()
    try:
        row = con.execute("SELECT title FROM hymn_cache WHERE key = ?", (key,)).fetchone()
        return row["title"] if row else None
    finally:
        con.close()


def hymn_set(key: str, title: str) -> None:
    """Store a hymn title in the cache."""
    con = _open()
    try:
        con.execute(
            "INSERT OR REPLACE INTO hymn_cache (key, title) VALUES (?, ?)", (key, title)
        )
        con.commit()
    finally:
        con.close()


def hymn_count() -> int:
    """Return the number of cached hymn lookups."""
    con = _open()
    try:
        return con.execute("SELECT COUNT(*) FROM hymn_cache").fetchone()[0]
    finally:
        con.close()


def hymn_clear() -> None:
    """Delete all cached hymn lookups."""
    con = _open()
    try:
        con.execute("DELETE FROM hymn_cache")
        con.commit()
    finally:
        con.close()


# ── Snippets ──────────────────────────────────────────────────────────────────

def snippets_load() -> list[dict]:
    """Return all snippets ordered by sort_order."""
    con = _open()
    try:
        rows = con.execute(
            "SELECT name, content FROM snippets ORDER BY sort_order, id"
        ).fetchall()
        return [{"name": r["name"], "content": r["content"]} for r in rows]
    finally:
        con.close()


def snippets_save(snippets: list[dict]) -> None:
    """Replace all snippets with the given list (order is preserved)."""
    con = _open()
    try:
        con.execute("DELETE FROM snippets")
        con.executemany(
            "INSERT INTO snippets (name, content, sort_order) VALUES (?, ?, ?)",
            [(s["name"], s["content"], i) for i, s in enumerate(snippets)],
        )
        con.commit()
    finally:
        con.close()


def snippets_has_data() -> bool:
    con = _open()
    try:
        return con.execute("SELECT COUNT(*) AS n FROM snippets").fetchone()["n"] > 0
    finally:
        con.close()


# ── Service index ─────────────────────────────────────────────────────────────

def service_index_update(
    path: str, title: str, date: str, item_count: int, mtime: float
) -> None:
    """Upsert a service file's cached metadata."""
    con = _open()
    try:
        con.execute(
            "INSERT OR REPLACE INTO service_index "
            "(path, title, date, item_count, mtime) VALUES (?, ?, ?, ?, ?)",
            (path, title, date, item_count, mtime),
        )
        con.commit()
    finally:
        con.close()


def service_index_get_mtime(path: str) -> float | None:
    """Return the cached mtime for a path, or None if not indexed."""
    con = _open()
    try:
        row = con.execute(
            "SELECT mtime FROM service_index WHERE path = ?", (path,)
        ).fetchone()
        return row["mtime"] if row else None
    finally:
        con.close()


def service_index_all() -> list[dict]:
    """Return all indexed service metadata."""
    con = _open()
    try:
        return [
            dict(r)
            for r in con.execute(
                "SELECT path, title, date, item_count FROM service_index"
            ).fetchall()
        ]
    finally:
        con.close()


def service_index_prune(keep_paths: set[str]) -> None:
    """Delete index entries for paths that no longer exist on disk."""
    con = _open()
    try:
        indexed = {
            r[0]
            for r in con.execute("SELECT path FROM service_index").fetchall()
        }
        for stale in indexed - keep_paths:
            con.execute("DELETE FROM service_index WHERE path = ?", (stale,))
        con.commit()
    finally:
        con.close()


# ── One-time migration from legacy JSON files ─────────────────────────────────

def migrate_from_json() -> None:
    """
    Import data from the old JSON files on first run. Safe to call on every
    startup — silently skips tables that already contain rows.
    """
    _migrate_hymn_cache()
    _migrate_snippets()


def _migrate_hymn_cache() -> None:
    cache_path = Path.home() / ".local/share/rubric/hymn_cache.json"
    if not cache_path.exists():
        return
    con = _open()
    try:
        if con.execute("SELECT COUNT(*) AS n FROM hymn_cache").fetchone()["n"] > 0:
            return
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data:
            con.executemany(
                "INSERT OR IGNORE INTO hymn_cache (key, title) VALUES (?, ?)",
                data.items(),
            )
            con.commit()
    except Exception:
        pass
    finally:
        con.close()


def _migrate_snippets() -> None:
    snippets_path = Path.home() / ".config/rubric/snippets.json"
    if not snippets_path.exists():
        return
    con = _open()
    try:
        if con.execute("SELECT COUNT(*) AS n FROM snippets").fetchone()["n"] > 0:
            return
        data = json.loads(snippets_path.read_text(encoding="utf-8"))
        if isinstance(data, list) and data:
            con.executemany(
                "INSERT INTO snippets (name, content, sort_order) VALUES (?, ?, ?)",
                [(s["name"], s["content"], i) for i, s in enumerate(data)],
            )
            con.commit()
    except Exception:
        pass
    finally:
        con.close()
