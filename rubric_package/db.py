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

import html as _html
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

CREATE TABLE IF NOT EXISTS bible_cache (
    key  TEXT PRIMARY KEY,
    text TEXT NOT NULL
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

CREATE TABLE IF NOT EXISTS element_index (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    service_path    TEXT    NOT NULL,
    service_title   TEXT    NOT NULL DEFAULT '',
    service_date    TEXT    NOT NULL DEFAULT '',
    section         TEXT    NOT NULL DEFAULT '',
    name            TEXT    NOT NULL DEFAULT '',
    leader          TEXT    NOT NULL DEFAULT '',
    note            TEXT    NOT NULL DEFAULT '',
    bulletin_note   TEXT    NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_elem_service ON element_index(service_path);
CREATE INDEX IF NOT EXISTS idx_elem_date    ON element_index(service_date DESC);
CREATE INDEX IF NOT EXISTS idx_elem_name    ON element_index(name);
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
        return _html.unescape(row["title"]) if row else None
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


def hymn_search(query: str, limit: int = 30) -> list[dict]:
    """Return cached hymns whose title or key contains query."""
    con = _open()
    try:
        q = f"%{query}%"
        rows = con.execute(
            "SELECT key, title FROM hymn_cache WHERE title LIKE ? OR key LIKE ? "
            "ORDER BY key LIMIT ?",
            (q, q, limit),
        ).fetchall()
        return [{"key": r["key"], "title": _html.unescape(r["title"])} for r in rows]
    finally:
        con.close()


# ── Bible cache ───────────────────────────────────────────────────────────────

def bible_get(key: str) -> str | None:
    """Return a cached passage text, or None if not cached. Key: 'translation:reference'."""
    con = _open()
    try:
        row = con.execute("SELECT text FROM bible_cache WHERE key = ?", (key,)).fetchone()
        return row["text"] if row else None
    finally:
        con.close()


def bible_set(key: str, text: str) -> None:
    """Store a passage in the cache."""
    con = _open()
    try:
        con.execute(
            "INSERT OR REPLACE INTO bible_cache (key, text) VALUES (?, ?)", (key, text)
        )
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


# ── Element library ───────────────────────────────────────────────────────────

def element_index_service(path: str, title: str, date: str, items: list[dict]) -> None:
    """Replace all indexed elements for a service path."""
    con = _open()
    try:
        con.execute("DELETE FROM element_index WHERE service_path = ?", (path,))
        section = ""
        rows = []
        for item in items:
            if item.get("type") == "divider":
                section = item.get("title", "")
            elif item.get("type") == "item":
                note = (item.get("note") or "").strip()
                bul  = (item.get("bulletin_note") or "").strip()
                name = (item.get("name") or "").strip()
                if not name:
                    continue
                rows.append((path, title, date, section, name,
                             item.get("leader", ""), note, bul))
        if rows:
            con.executemany(
                "INSERT INTO element_index "
                "(service_path, service_title, service_date, section, name, "
                " leader, note, bulletin_note) VALUES (?,?,?,?,?,?,?,?)",
                rows,
            )
        con.commit()
    finally:
        con.close()


def element_search(query: str, limit: int = 80) -> list[dict]:
    """Return elements whose name or note contains query, newest first."""
    con = _open()
    try:
        q = f"%{query}%"
        rows = con.execute(
            "SELECT * FROM element_index "
            "WHERE name LIKE ? OR note LIKE ? OR leader LIKE ? "
            "ORDER BY service_date DESC, id LIMIT ?",
            (q, q, q, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def element_services(limit: int = 200) -> list[dict]:
    """Return distinct services that have indexed elements, newest first."""
    con = _open()
    try:
        rows = con.execute(
            "SELECT service_path, service_title, service_date, COUNT(*) AS n "
            "FROM element_index "
            "GROUP BY service_path "
            "ORDER BY service_date DESC, service_title LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def element_for_service(path: str) -> list[dict]:
    """Return all elements for a given service path, in order."""
    con = _open()
    try:
        rows = con.execute(
            "SELECT * FROM element_index WHERE service_path = ? ORDER BY id",
            (path,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def element_prune(keep_paths: set[str]) -> None:
    """Remove element index entries for services no longer on disk."""
    con = _open()
    try:
        indexed = {r[0] for r in con.execute(
            "SELECT DISTINCT service_path FROM element_index").fetchall()}
        for stale in indexed - keep_paths:
            con.execute("DELETE FROM element_index WHERE service_path = ?", (stale,))
        con.commit()
    finally:
        con.close()


def element_name_stats(query: str = "", limit: int = 100) -> list[dict]:
    """Return distinct element names with cross-service usage counts, sorted by frequency."""
    con = _open()
    try:
        if query:
            q = f"%{query}%"
            rows = con.execute(
                "SELECT name, COUNT(DISTINCT service_path) AS use_count, "
                "MAX(service_date) AS last_used "
                "FROM element_index WHERE name LIKE ? "
                "GROUP BY name ORDER BY use_count DESC, last_used DESC LIMIT ?",
                (q, limit),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT name, COUNT(DISTINCT service_path) AS use_count, "
                "MAX(service_date) AS last_used "
                "FROM element_index "
                "GROUP BY name ORDER BY use_count DESC, last_used DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def element_suggestions(prefix: str, limit: int = 8) -> list[dict]:
    """Return element names starting with prefix, ranked by cross-service frequency."""
    con = _open()
    try:
        q = f"{prefix}%"
        rows = con.execute(
            "SELECT name, COUNT(DISTINCT service_path) AS use_count "
            "FROM element_index WHERE name LIKE ? "
            "GROUP BY name ORDER BY use_count DESC LIMIT ?",
            (q, limit),
        ).fetchall()
        return [dict(r) for r in rows]
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
