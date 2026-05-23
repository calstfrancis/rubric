"""
hymn_lookup.py — Asynchronous hymn title lookup via Hymnary.org

Supported hymnals:
  VU  — Voices United (United Church of Canada, 1996)
  MV  — More Voices (United Church of Canada, 2007)
  LUS — Let Us Sing! (United Church of Canada supplement)

Results are cached in the Rubric SQLite database (~/.local/share/rubric/rubric.db).
"""

import threading
import time
import urllib.request
import urllib.error
import re

import gi
gi.require_version("GLib", "2.0")
from gi.repository import GLib

try:
    from rubric_package.db import hymn_get, hymn_set, hymn_search as _hymn_search
    _DB_OK = True
except ImportError:
    _DB_OK = False
    def _hymn_search(q, limit=30): return []

# Hymnary.org book identifiers
HYMNALS: dict[str, tuple[str, str]] = {
    "VU":  ("VU1996",   "Voices United"),
    "MV":  ("MV2007",   "More Voices"),
    "LUS": ("LUS2022",  "Let Us Sing"),
}


def parse_hymn_ref(text: str) -> tuple[str, int] | None:
    """
    Parse a hymn reference like 'VU 16', 'mv120', 'LUS 5'.
    Returns (prefix_upper, number) or None.
    """
    m = re.match(r'^\s*([A-Za-z]+)\s*(\d+)\s*$', text.strip())
    if not m:
        return None
    prefix = m.group(1).upper()
    number = int(m.group(2))
    if prefix not in HYMNALS:
        return None
    return prefix, number


def lookup_hymn(prefix: str, number: int, callback):
    """
    Asynchronously look up a hymn title on Hymnary.org.

    callback(title: str | None, error: str | None) is called on the
    GLib main loop when the result is ready.
    """
    def fetch():
        key = f"{prefix}{number}"

        if _DB_OK:
            cached = hymn_get(key)
            if cached is not None:
                GLib.idle_add(callback, cached, None)
                return

        hymnal_id, hymnal_name = HYMNALS.get(prefix, (None, None))
        if not hymnal_id:
            GLib.idle_add(callback, None, f"Unknown hymnal '{prefix}'")
            return

        url = f"https://hymnary.org/hymn/{hymnal_id}/{number}"
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 LiturgyPlanner/1.0"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="replace")

            # Hymnary page titles look like:
            # "Voices United: The Hymn... 16. Mary, woman of the promise | Hymnary.org"
            # or just "O Come, O Come, Emmanuel | Hymnary.org"
            m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
            if m:
                raw = m.group(1).strip()
                title = raw.split("|")[0].strip()
                # Strip leading book name + number: "Book Name 16. Actual Title" -> "Actual Title"
                clean = re.match(r'^.*?\d+\.\s+(.+)$', title)
                if clean:
                    title = clean.group(1).strip()
                if title and "hymnary" not in title.lower() and len(title) > 2:
                    if _DB_OK:
                        hymn_set(key, title)
                    GLib.idle_add(callback, title, None)
                    return

            GLib.idle_add(callback, None, f"#{number} not found in {hymnal_name}")

        except urllib.error.HTTPError as e:
            if e.code == 404:
                GLib.idle_add(callback, None,
                              f"#{number} not found in {hymnal_name}")
            else:
                GLib.idle_add(callback, None, f"HTTP error {e.code}")
        except Exception as e:
            GLib.idle_add(callback, None, f"Network error: {type(e).__name__}")

    threading.Thread(target=fetch, daemon=True).start()


def search_hymns(query: str) -> list[dict]:
    """Search cached hymn titles by keyword. Returns [{book, number, title}]."""
    results = _hymn_search(query)
    out = []
    for r in results:
        key = r["key"]
        for prefix in HYMNALS:
            if key.startswith(prefix):
                out.append({"book": prefix, "number": key[len(prefix):], "title": r["title"]})
                break
    return out


# Maximum hymn numbers per book (Hymnary-based)
_BOOK_MAX = {"VU": 961, "MV": 217, "LUS": 150}


def prefetch_hymnal(book: str, on_progress=None, on_done=None):
    """Background-fetch all hymn titles for one book and cache them.

    on_progress(n, total) — called on GLib main thread after each hymn
    on_done(n_added)      — called when the fetch is complete
    """
    book = book.upper()
    max_n = _BOOK_MAX.get(book, 200)
    hymnal_id = HYMNALS.get(book, (None, None))[0]
    if not hymnal_id:
        if on_done:
            GLib.idle_add(on_done, 0)
        return

    def run():
        added = 0
        for n in range(1, max_n + 1):
            key = f"{book}{n}"
            if _DB_OK and hymn_get(key) is not None:
                if on_progress:
                    GLib.idle_add(on_progress, n, max_n)
                continue
            url = f"https://hymnary.org/hymn/{hymnal_id}/{n}"
            try:
                req = urllib.request.Request(
                    url, headers={"User-Agent": "Mozilla/5.0 LiturgyPlanner/1.0"}
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    html = resp.read().decode("utf-8", errors="replace")
                m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
                if m:
                    raw = m.group(1).strip()
                    title = raw.split("|")[0].strip()
                    clean = re.match(r"^.*?\d+\.\s+(.+)$", title)
                    if clean:
                        title = clean.group(1).strip()
                    hymnal_name = HYMNALS[book][1]
                    if title and "hymnary" not in title.lower() and len(title) > 2:
                        if _DB_OK:
                            hymn_set(key, title)
                        added += 1
                        time.sleep(0.25)
            except Exception:
                pass
            if on_progress:
                GLib.idle_add(on_progress, n, max_n)
        if on_done:
            GLib.idle_add(on_done, added)

    threading.Thread(target=run, daemon=True).start()
