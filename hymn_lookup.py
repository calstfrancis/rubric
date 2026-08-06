"""
hymn_lookup.py — Hymn title lookup from Rubric's own database.

Supported hymnals:
  VU  — Voices United (United Church of Canada, 1996)
  MV  — More Voices (United Church of Canada, 2007)
  LUS — Let Us Sing! (United Church of Canada supplement)

Titles live in the Rubric SQLite database (~/.local/share/rubric/rubric.db) and
are seeded on first run from the list that ships with the app
(rubric_package/data/hymn_titles.json).

There is no network here. Rubric used to fetch titles from Hymnary.org, first
with urllib and then with curl and browser headers to get past its TLS
fingerprinting. Hymnary now answers with a JavaScript bot-protection challenge
that no desktop app can pass, so every lookup failed and the bulk download
worked through an entire hymnal — some 1,900 requests for Voices United — to
add nothing at all. Reading only from the database means lookup is instant,
works offline, and behaves the same on every machine.

A title Rubric does not have is added by typing it in once. It is stored beside
the bundled titles, is searchable from then on, and is never overwritten.
"""

import re

try:
    from rubric_package.db import (
        hymn_get, hymn_set, hymn_search as _hymn_search,
    )
    _DB_OK = True
except ImportError:
    _DB_OK = False

    def hymn_get(key): return None

    def hymn_set(key, title): pass

    def _hymn_search(q, limit=100): return []


# Hymnal code → full name, for messages and labels.
HYMNALS: dict[str, str] = {
    "VU":  "Voices United",
    "MV":  "More Voices",
    "LUS": "Let Us Sing",
}

# Highest hymn number in each book, used to reject impossible references before
# they reach the database.
_BOOK_MAX = {"VU": 961, "MV": 217, "LUS": 150}


def hymnal_name(prefix: str) -> str:
    """Full name of a hymnal code, or the code itself if unknown."""
    return HYMNALS.get(prefix.upper(), prefix)


def hymn_range(prefix: str) -> int | None:
    """Highest valid hymn number for a book, or None if the book is unknown."""
    return _BOOK_MAX.get(prefix.upper())


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


def is_in_range(prefix: str, number: int) -> bool:
    """Whether number could exist in that hymnal at all."""
    top = hymn_range(prefix)
    if top is None:
        return False
    try:
        number = int(number)
    except (TypeError, ValueError):
        return False
    return 1 <= number <= top


def lookup_hymn(prefix: str, number: int) -> str | None:
    """Return the stored title for a hymn, or None if Rubric doesn't have it.

    Synchronous: this is a single indexed read from a local database, so there
    is nothing to wait for. It used to run on a background thread and call back
    on the GLib main loop because it was a network request.
    """
    if not _DB_OK:
        return None
    return hymn_get(f"{prefix.upper()}{number}")


def remember_hymn(prefix: str, number: int, title: str) -> bool:
    """Store a title the user supplied. Returns False if it wasn't saved."""
    title = (title or "").strip()
    if not _DB_OK or not title or not is_in_range(prefix, number):
        return False
    hymn_set(f"{prefix.upper()}{number}", title)
    return True


def search_hymns(query: str) -> list[dict]:
    """Search stored hymn titles by keyword. Returns [{book, number, title}]."""
    out = []
    for r in _hymn_search(query):
        key = r["key"]
        # Longest prefix first, so a book whose code starts with another book's
        # code can never be misread.
        for prefix in sorted(HYMNALS, key=len, reverse=True):
            if key.startswith(prefix):
                num = key[len(prefix):]
                out.append({"book": prefix,
                            "number": int(num) if num.isdigit() else num,
                            "title": r["title"]})
                break
    return out
