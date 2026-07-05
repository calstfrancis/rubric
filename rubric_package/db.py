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
from difflib import SequenceMatcher
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

CREATE TABLE IF NOT EXISTS service_meta (
    path            TEXT PRIMARY KEY,
    title           TEXT    NOT NULL DEFAULT '',
    date            TEXT    NOT NULL DEFAULT '',
    tags            TEXT    NOT NULL DEFAULT '',
    series          TEXT    NOT NULL DEFAULT '',
    pinned          INTEGER NOT NULL DEFAULT 0,
    notes_preview   TEXT    NOT NULL DEFAULT '',
    attendance      INTEGER NOT NULL DEFAULT 0,
    debrief_preview TEXT    NOT NULL DEFAULT '',
    mtime           REAL    NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_svcmeta_date   ON service_meta(date DESC);
CREATE INDEX IF NOT EXISTS idx_svcmeta_series ON service_meta(series);

CREATE TABLE IF NOT EXISTS element_catalog (
    name_key  TEXT PRIMARY KEY,
    name      TEXT NOT NULL DEFAULT '',
    tags      TEXT NOT NULL DEFAULT '',
    favorite  INTEGER NOT NULL DEFAULT 0,
    notes     TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_catalog_favorite ON element_catalog(favorite DESC);
"""


def _open() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout = 5000")
    return con


def _norm_key(name: str) -> str:
    """Normalize an element name to a stable lookup key (trim/lowercase/collapse whitespace)."""
    return " ".join((name or "").strip().lower().split())


def init_db() -> None:
    """Create tables and enable WAL mode. Call once at application startup."""
    con = _open()
    try:
        con.executescript(_SCHEMA)
        for stmt in (
            "ALTER TABLE service_meta ADD COLUMN attendance INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE service_meta ADD COLUMN debrief_preview TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE element_index ADD COLUMN name_key TEXT NOT NULL DEFAULT ''",
        ):
            try:
                con.execute(stmt)
            except sqlite3.OperationalError:
                pass  # column already exists
        con.execute("CREATE INDEX IF NOT EXISTS idx_elem_namekey ON element_index(name_key)")
        con.execute("UPDATE element_index SET name_key = lower(trim(name)) WHERE name_key = ''")
        con.execute(
            "INSERT OR IGNORE INTO element_catalog (name_key, name) "
            "SELECT name_key, name FROM element_index WHERE name_key != '' GROUP BY name_key"
        )
        con.commit()
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


# ── Service organization (tags, series, pinned, notes preview) ────────────────

def service_meta_update(
    path: str, title: str, date: str, tags: list[str], series: str,
    pinned: bool, notes_preview: str, mtime: float,
    attendance: int = 0, debrief_preview: str = "",
    _con: sqlite3.Connection | None = None,
) -> None:
    """Upsert a service's organizational metadata, cached from its .liturgy file.

    Pass `_con` to reuse an existing connection/transaction (e.g. during a
    bulk scan) instead of opening and committing a new one per call.
    """
    con = _con or _open()
    try:
        con.execute(
            "INSERT OR REPLACE INTO service_meta "
            "(path, title, date, tags, series, pinned, notes_preview, "
            " attendance, debrief_preview, mtime) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (path, title, date, ",".join(tags), series, int(pinned), notes_preview,
             int(attendance), debrief_preview, mtime),
        )
        if _con is None:
            con.commit()
    finally:
        if _con is None:
            con.close()


def service_meta_get(path: str) -> dict | None:
    """Return cached organizational metadata for a single service, or None."""
    con = _open()
    try:
        row = con.execute(
            "SELECT * FROM service_meta WHERE path = ?", (path,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["tags"] = [t for t in d["tags"].split(",") if t]
        d["pinned"] = bool(d["pinned"])
        return d
    finally:
        con.close()


def service_meta_all_mtimes() -> dict[str, float]:
    """Return {path: mtime} for every indexed service in a single query."""
    con = _open()
    try:
        return {
            r["path"]: r["mtime"]
            for r in con.execute("SELECT path, mtime FROM service_meta").fetchall()
        }
    finally:
        con.close()


def service_meta_all() -> list[dict]:
    """Return organizational metadata for every indexed service, newest first."""
    con = _open()
    try:
        rows = con.execute(
            "SELECT * FROM service_meta ORDER BY date DESC, title"
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["tags"] = [t for t in d["tags"].split(",") if t]
            d["pinned"] = bool(d["pinned"])
            out.append(d)
        return out
    finally:
        con.close()


def service_meta_prune(keep_paths: set[str]) -> None:
    """Delete service_meta entries for paths that no longer exist on disk."""
    con = _open()
    try:
        indexed = {r[0] for r in con.execute("SELECT path FROM service_meta").fetchall()}
        for stale in indexed - keep_paths:
            con.execute("DELETE FROM service_meta WHERE path = ?", (stale,))
        con.commit()
    finally:
        con.close()


def service_meta_all_tags() -> list[tuple[str, int]]:
    """Return (tag, count) for every distinct tag in use, most-used first."""
    con = _open()
    try:
        rows = con.execute("SELECT tags FROM service_meta WHERE tags != ''").fetchall()
        counts: dict[str, int] = {}
        for r in rows:
            for t in r["tags"].split(","):
                if t:
                    counts[t] = counts.get(t, 0) + 1
        return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].lower()))
    finally:
        con.close()


def service_meta_all_series() -> list[tuple[str, int]]:
    """Return (series, count) for every distinct series in use, alphabetical."""
    con = _open()
    try:
        rows = con.execute(
            "SELECT series, COUNT(*) AS n FROM service_meta "
            "WHERE series != '' GROUP BY series ORDER BY series COLLATE NOCASE"
        ).fetchall()
        return [(r["series"], r["n"]) for r in rows]
    finally:
        con.close()


def service_meta_paths_for_tag(tag: str) -> list[str]:
    """Return paths of every service tagged with the given tag (exact match)."""
    con = _open()
    try:
        rows = con.execute("SELECT path, tags FROM service_meta WHERE tags != ''").fetchall()
        return [r["path"] for r in rows if tag in r["tags"].split(",")]
    finally:
        con.close()


def service_meta_paths_for_series(series: str) -> list[str]:
    """Return paths of every service in the given series (exact match)."""
    con = _open()
    try:
        rows = con.execute(
            "SELECT path FROM service_meta WHERE series = ?", (series,)
        ).fetchall()
        return [r["path"] for r in rows]
    finally:
        con.close()


# ── Element library ───────────────────────────────────────────────────────────

def element_index_service(
    path: str, title: str, date: str, items: list[dict],
    _con: sqlite3.Connection | None = None,
) -> None:
    """Replace all indexed elements for a service path.

    Pass `_con` to reuse an existing connection/transaction (e.g. during a
    bulk scan) instead of opening and committing a new one per call.
    """
    con = _con or _open()
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
                rows.append((path, title, date, section, name, _norm_key(name),
                             item.get("leader", ""), note, bul))
        if rows:
            con.executemany(
                "INSERT INTO element_index "
                "(service_path, service_title, service_date, section, name, name_key, "
                " leader, note, bulletin_note) VALUES (?,?,?,?,?,?,?,?,?)",
                rows,
            )
            con.executemany(
                "INSERT OR IGNORE INTO element_catalog (name_key, name) VALUES (?, ?)",
                {(r[5], r[4]) for r in rows},
            )
        if _con is None:
            con.commit()
    finally:
        if _con is None:
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


# ── Element catalog (cross-service identity, tags, favorites) ─────────────────

def element_catalog_set_tags(name_key: str, tags: list[str]) -> None:
    """Set the tag list for a catalog element, keyed by its normalized name."""
    con = _open()
    try:
        con.execute(
            "UPDATE element_catalog SET tags = ? WHERE name_key = ?",
            (",".join(tags), name_key),
        )
        con.commit()
    finally:
        con.close()


def element_catalog_set_favorite(name_key: str, favorite: bool) -> None:
    """Mark or unmark a catalog element as a favorite."""
    con = _open()
    try:
        con.execute(
            "UPDATE element_catalog SET favorite = ? WHERE name_key = ?",
            (int(favorite), name_key),
        )
        con.commit()
    finally:
        con.close()


def element_catalog_set_notes(name_key: str, notes: str) -> None:
    """Set the curator notes for a catalog element."""
    con = _open()
    try:
        con.execute(
            "UPDATE element_catalog SET notes = ? WHERE name_key = ?",
            (notes, name_key),
        )
        con.commit()
    finally:
        con.close()


def element_catalog_all_tags() -> list[tuple[str, int]]:
    """Return (tag, count) for every distinct element tag in use, most-used first."""
    con = _open()
    try:
        rows = con.execute("SELECT tags FROM element_catalog WHERE tags != ''").fetchall()
        counts: dict[str, int] = {}
        for r in rows:
            for t in r["tags"].split(","):
                if t:
                    counts[t] = counts.get(t, 0) + 1
        return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].lower()))
    finally:
        con.close()


def element_catalog_keys_for_tag(tag: str) -> list[str]:
    """Return name_keys of every catalog element tagged with the given tag (exact match)."""
    con = _open()
    try:
        rows = con.execute("SELECT name_key, tags FROM element_catalog WHERE tags != ''").fetchall()
        return [r["name_key"] for r in rows if tag in r["tags"].split(",")]
    finally:
        con.close()


def element_library(
    query: str = "", tag: str | None = None, favorites_only: bool = False,
    sort: str = "frequency", limit: int = 300,
) -> list[dict]:
    """Return catalog elements aggregated with usage stats, filtered and sorted.

    `sort` is one of "frequency" (use_count desc), "recent" (last_used desc),
    or "alpha" (name).
    """
    con = _open()
    try:
        where = []
        params: list = []
        if query:
            where.append("c.name LIKE ?")
            params.append(f"%{query}%")
        if tag:
            where.append("(',' || c.tags || ',') LIKE ?")
            params.append(f"%,{tag},%")
        if favorites_only:
            where.append("c.favorite = 1")
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        order_sql = {
            "recent": "last_used DESC",
            "alpha": "c.name COLLATE NOCASE",
        }.get(sort, "use_count DESC")
        rows = con.execute(
            f"SELECT c.name_key, c.name, c.tags, c.favorite, c.notes, "
            f"COUNT(DISTINCT e.service_path) AS use_count, MAX(e.service_date) AS last_used "
            f"FROM element_catalog c LEFT JOIN element_index e ON e.name_key = c.name_key "
            f"{where_sql} "
            f"GROUP BY c.name_key ORDER BY c.favorite DESC, {order_sql} LIMIT ?",
            (*params, limit),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["tags"] = [t for t in d["tags"].split(",") if t]
            d["favorite"] = bool(d["favorite"])
            out.append(d)
        return out
    finally:
        con.close()


def element_instances(name_key: str, limit: int = 200) -> list[dict]:
    """Return every indexed instance of a catalog element, newest first."""
    con = _open()
    try:
        rows = con.execute(
            "SELECT * FROM element_index WHERE name_key = ? "
            "ORDER BY service_date DESC, id LIMIT ?",
            (name_key, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def element_catalog_find_duplicates(threshold: float = 0.82, limit: int = 30) -> list[dict]:
    """Return likely-duplicate pairs of catalog elements, ranked by similarity.

    Compares every pair of normalized name_keys with difflib's SequenceMatcher
    and keeps pairs scoring at or above `threshold`. O(n^2) over the catalog,
    which is fine at the scale of a single church's recurring elements (tens
    to low hundreds of distinct names).
    """
    entries = element_library(limit=100000)
    pairs = []
    for i in range(len(entries)):
        for j in range(i + 1, len(entries)):
            a, b = entries[i], entries[j]
            score = SequenceMatcher(None, a["name_key"], b["name_key"]).ratio()
            if score >= threshold:
                pairs.append({"a": a, "b": b, "score": score})
    pairs.sort(key=lambda p: -p["score"])
    return pairs[:limit]


def element_catalog_merge(keep_key: str, drop_key: str) -> None:
    """Merge one catalog element into another, reassigning all its history.

    Every `element_index` row pointing at `drop_key` is repointed to
    `keep_key`; tags and favorite status are unioned; `drop_key`'s catalog
    row is deleted. `keep_key`'s notes are only replaced if it had none.
    """
    if keep_key == drop_key:
        return
    con = _open()
    try:
        keep = con.execute(
            "SELECT * FROM element_catalog WHERE name_key = ?", (keep_key,)
        ).fetchone()
        drop = con.execute(
            "SELECT * FROM element_catalog WHERE name_key = ?", (drop_key,)
        ).fetchone()
        if keep is None or drop is None:
            return
        keep_tags = [t for t in keep["tags"].split(",") if t]
        drop_tags = [t for t in drop["tags"].split(",") if t]
        merged_tags = keep_tags + [t for t in drop_tags if t not in keep_tags]
        merged_favorite = int(bool(keep["favorite"]) or bool(drop["favorite"]))
        merged_notes = keep["notes"] or drop["notes"]
        con.execute(
            "UPDATE element_catalog SET tags = ?, favorite = ?, notes = ? WHERE name_key = ?",
            (",".join(merged_tags), merged_favorite, merged_notes, keep_key),
        )
        con.execute(
            "UPDATE element_index SET name_key = ? WHERE name_key = ?", (keep_key, drop_key)
        )
        con.execute("DELETE FROM element_catalog WHERE name_key = ?", (drop_key,))
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
