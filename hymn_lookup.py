"""
hymn_lookup.py — Asynchronous hymn title lookup via Hymnary.org

Supported hymnals:
  VU  — Voices United (United Church of Canada, 1996)
  MV  — More Voices (United Church of Canada, 2007)
  LUS — Let Us Sing! (United Church of Canada supplement)

Results are cached in the Rubric SQLite database (~/.local/share/rubric/rubric.db).

Network requests use curl (via subprocess) rather than Python's urllib to avoid
TLS fingerprint blocking that Hymnary.org applies to non-browser HTTP stacks.
Inside a Flatpak sandbox, requests are routed through flatpak-spawn --host curl.
"""

import html as _html
import subprocess
import threading
import time
import re
from pathlib import Path

import gi
gi.require_version("GLib", "2.0")
from gi.repository import GLib

try:
    from rubric_package.db import hymn_get, hymn_set, hymn_search as _hymn_search
    _DB_OK = True
except ImportError:
    _DB_OK = False
    def _hymn_search(q, limit=30): return []

# Use flatpak-spawn --host when running inside the sandbox
_IS_FLATPAK = Path("/.flatpak-info").exists()
_CURL = ["flatpak-spawn", "--host", "curl"] if _IS_FLATPAK else ["curl"]

_CURL_HEADERS = [
    "-H", "User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "-H", "Accept-Language: en-US,en;q=0.9",
]

# Hymnary.org book identifiers
HYMNALS: dict[str, tuple[str, str]] = {
    "VU":  ("VU1996",   "Voices United"),
    "MV":  ("MV2007",   "More Voices"),
    "LUS": ("LUS2022",  "Let Us Sing"),
}


def _curl_get(url: str, extra_headers: list[str] | None = None) -> tuple[str | None, int]:
    """Run curl and return (body, http_code). http_code=0 on curl failure."""
    headers = _CURL_HEADERS + (extra_headers or [])
    cmd = _CURL + [
        "--silent", "--max-time", "20", "--location",
        "--write-out", "\n__HTTP_CODE__%{http_code}",
        *headers, url,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        return None, 0
    if result.returncode != 0:
        return None, 0
    body, _, code_str = result.stdout.rpartition("\n__HTTP_CODE__")
    code = int(code_str.strip()) if code_str.strip().isdigit() else 0
    return body, code


def _wayback_url(url: str) -> str | None:
    """Return the most recent Wayback Machine snapshot URL for url, or None."""
    api = (
        "http://archive.org/wayback/available?url="
        + url.replace("https://", "").replace("http://", "")
    )
    body, code = _curl_get(api, extra_headers=["-H", "Accept: application/json"])
    if not body or code not in (200, 0):
        return None
    m = re.search(r'"url"\s*:\s*"(https?://web\.archive\.org/web/[^"]+)"', body)
    return m.group(1) if m else None


def _fetch_url(url: str) -> tuple[str | None, str | None]:
    """Fetch a Hymnary.org page, falling back to Wayback Machine on 403.
    Returns (html_text, error_message)."""
    body, code = _curl_get(url)
    if code == 200 and body:
        return body, None
    if code == 404:
        return None, "404"

    # 403 or any block — try Wayback Machine archive
    wayback = _wayback_url(url)
    if wayback:
        body, code = _curl_get(wayback)
        if code == 200 and body:
            return body, None

    if code == 403:
        return None, "HTTP 403 — Hymnary.org blocked the request"
    return None, f"HTTP {code}" if code else "Network error"


def _extract_hymn_title(html_text: str) -> str:
    """Extract and clean the hymn title from a Hymnary.org page."""
    title = ""

    # 1. og:title meta tag — most reliable, set server-side
    og = re.search(
        r'<meta\s[^>]*property=["\']og:title["\']\s*[^>]*content=["\']([^"\']+)["\']'
        r'|<meta\s[^>]*content=["\']([^"\']+)["\']\s*[^>]*property=["\']og:title["\']',
        html_text, re.IGNORECASE)
    if og:
        title = (og.group(1) or og.group(2) or "").strip()
        clean = re.match(r'^.*?\d+\.\s+(.+)$', title)
        if clean:
            title = clean.group(1).strip()

    # 2. JSON-LD structured data
    if not title:
        jld = re.search(r'"name"\s*:\s*"([^"]{3,120})"', html_text)
        if jld:
            title = jld.group(1).strip()

    # 3. <title> tag fallback
    if not title:
        t = re.search(r"<title[^>]*>([^<]+)</title>", html_text, re.IGNORECASE)
        if t:
            raw = t.group(1).strip().split("|")[0].strip()
            clean = re.match(r'^.*?\d+\.\s+(.+)$', raw)
            title = clean.group(1).strip() if clean else raw

    return _html.unescape(title)


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
        html_text, err = _fetch_url(url)
        if err == "404":
            GLib.idle_add(callback, None, f"#{number} not found in {hymnal_name}")
            return
        if err:
            GLib.idle_add(callback, None, err)
            return

        title = _extract_hymn_title(html_text)
        if not title or "hymnary" in title.lower() or len(title) <= 2:
            try:
                import tempfile, os
                dbg = os.path.join(tempfile.gettempdir(), "rubric_hymn_debug.html")
                with open(dbg, "w", encoding="utf-8") as fh:
                    fh.write(html_text[:8192])
            except Exception:
                pass
            GLib.idle_add(callback, None,
                          f"#{number} not found in {hymnal_name} (debug: /tmp/rubric_hymn_debug.html)")
            return

        if _DB_OK:
            hymn_set(key, title)
        GLib.idle_add(callback, title, None)

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
            html_text, err = _fetch_url(url)
            if not err and html_text:
                title = _extract_hymn_title(html_text)
                if title and "hymnary" not in title.lower() and len(title) > 2:
                    if _DB_OK:
                        hymn_set(key, title)
                    added += 1
            time.sleep(0.4)
            if on_progress:
                GLib.idle_add(on_progress, n, max_n)
        if on_done:
            GLib.idle_add(on_done, added)

    threading.Thread(target=run, daemon=True).start()
