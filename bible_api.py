"""
bible_api.py — Asynchronous Bible passage fetcher.

Supports:
  - WEB (World English Bible)     via bible-api.com  (public domain)
  - KJV (King James Version)      via bible-api.com  (public domain)
  - ASV (American Standard)       via bible-api.com  (public domain)
  - ESV (English Standard)        via api.esv.org    (free API key required)
"""

import threading
import urllib.request
import urllib.error
import urllib.parse
import json
import re

try:
    import gi
    gi.require_version("GLib", "2.0")
    from gi.repository import GLib as _GLib

    def _idle_add(fn, *args):
        _GLib.idle_add(fn, *args)
except (ImportError, ValueError):
    def _idle_add(fn, *args):
        fn(*args)

try:
    from rubric_package.db import bible_get as _bible_get, bible_set as _bible_set
    _CACHE_OK = True
except ImportError:
    _CACHE_OK = False

ESV_API = "https://api.esv.org/v3/passage/text/"

BIBLE_API_TRANSLATIONS = {"web": "web", "kjv": "kjv", "asv": "asv"}

TRANSLATION_LABELS = {
    "web": "World English Bible (Public Domain)",
    "kjv": "King James Version (Public Domain)",
    "asv": "American Standard Version (Public Domain)",
    "esv": "English Standard Version (ESV API key required)",
}

# RCL abbreviation → full book name accepted by bible-api.com
BOOK_MAP: dict[str, str] = {
    "Gen": "Genesis",          "Exod": "Exodus",          "Lev": "Leviticus",
    "Num": "Numbers",          "Deut": "Deuteronomy",     "Josh": "Joshua",
    "Judg": "Judges",          "Ruth": "Ruth",
    "1 Sam": "1 Samuel",       "2 Sam": "2 Samuel",
    "1 Kgs": "1 Kings",        "2 Kgs": "2 Kings",
    "1 Chr": "1 Chronicles",   "2 Chr": "2 Chronicles",
    "Ezra": "Ezra",            "Neh": "Nehemiah",          "Esth": "Esther",
    "Job": "Job",              "Ps": "Psalms",             "Prov": "Proverbs",
    "Eccl": "Ecclesiastes",    "Song": "Song of Solomon",
    "Isa": "Isaiah",           "Jer": "Jeremiah",          "Lam": "Lamentations",
    "Ezek": "Ezekiel",         "Dan": "Daniel",
    "Hos": "Hosea",            "Joel": "Joel",             "Amos": "Amos",
    "Obad": "Obadiah",         "Jon": "Jonah",             "Mic": "Micah",
    "Nah": "Nahum",            "Hab": "Habakkuk",          "Zeph": "Zephaniah",
    "Hag": "Haggai",           "Zech": "Zechariah",        "Mal": "Malachi",
    "Matt": "Matthew",         "Mark": "Mark",
    "Luke": "Luke",            "John": "John",             "Acts": "Acts",
    "Rom": "Romans",           "1 Cor": "1 Corinthians",   "2 Cor": "2 Corinthians",
    "Gal": "Galatians",        "Eph": "Ephesians",         "Phil": "Philippians",
    "Col": "Colossians",       "1 Thess": "1 Thessalonians","2 Thess": "2 Thessalonians",
    "1 Tim": "1 Timothy",      "2 Tim": "2 Timothy",
    "Titus": "Titus",          "Phlm": "Philemon",         "Heb": "Hebrews",
    "Jas": "James",            "1 Pet": "1 Peter",         "2 Pet": "2 Peter",
    "1 John": "1 John",        "2 John": "2 John",         "3 John": "3 John",
    "Jude": "Jude",            "Rev": "Revelation",
}


def clean_reference(ref: str) -> str:
    """
    Simplify an RCL reference string for bible-api.com.
    Takes the first contiguous range, strips letter suffixes, etc.
    """
    # Remove square brackets (optional portions): [1–9]10–18 → 10–18
    ref = re.sub(r'\[([^\]]*)\]', '', ref)
    # Take first segment before semicolon
    ref = ref.split(";")[0].strip()
    # Take first segment before comma ("Joel 2:1–2, 12–17" → "Joel 2:1–2")
    ref = ref.split(",")[0].strip()
    # Remove letter suffixes: 14a → 14
    ref = re.sub(r'(\d+)[a-zA-Z]\b', r'\1', ref)
    # Replace em/en dashes with ASCII hyphens
    ref = ref.replace('–', '-').replace('—', '-')
    # Replace non-breaking spaces
    ref = ref.replace('\xa0', ' ').strip()
    return ref


def map_book(ref: str) -> str:
    """Replace abbreviated book name with full name for the API."""
    # Sort longest-first so "1 Sam" matches before "Sam"
    for abbr, full in sorted(BOOK_MAP.items(), key=lambda x: -len(x[0])):
        if ref.startswith(abbr + " ") or ref.startswith(abbr + ":") or ref == abbr:
            return full + ref[len(abbr):]
    return ref


def fetch_passage(reference: str, callback, translation: str = "web", esv_key: str = ""):
    """
    Asynchronously fetch a Bible passage.

    callback(text: str | None, error: str | None) is called on
    the GLib main loop when the result is ready.

    translation: one of "web", "kjv", "asv", "esv"
    esv_key: required when translation == "esv"
    """
    def fetch():
        cleaned = clean_reference(reference)
        cache_key = f"{translation}:{cleaned}"

        if _CACHE_OK:
            cached = _bible_get(cache_key)
            if cached:
                _idle_add(callback, cached, None)
                return

        if translation == "esv":
            if not esv_key:
                _idle_add(callback, None,
                          "ESV API key not set — add it in Preferences → Scripture")
                return
            _fetch_esv(cleaned, callback, esv_key, cache_key if _CACHE_OK else None)
            return

        # Fall back to bible-api.com for web/kjv/asv
        trl = BIBLE_API_TRANSLATIONS.get(translation, "web")
        full_ref = map_book(cleaned)
        url = ("https://bible-api.com/" + urllib.parse.quote(full_ref) + f"?translation={trl}")

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 LiturgyPlanner/1.0"},
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            if "error" in data:
                _idle_add(callback, None, data["error"]); return

            verses = data.get("verses", [])
            if verses:
                parts = [f"{v.get('verse','')} {v.get('text','').strip()}" for v in verses]
                passage = "\n".join(parts)
            else:
                passage = data.get("text", "").strip()

            if not passage:
                _idle_add(callback, None, "No text returned"); return

            if _CACHE_OK:
                _bible_set(cache_key, passage)
            _idle_add(callback, passage, None)

        except urllib.error.HTTPError as e:
            _idle_add(callback, None, f"HTTP error {e.code}" if e.code != 404
                          else f"Passage not found: {cleaned}")
        except Exception as e:
            _idle_add(callback, None, f"Network error: {type(e).__name__}")

    threading.Thread(target=fetch, daemon=True).start()


def _fetch_esv(reference: str, callback, key: str, cache_key: str | None = None):
    params = urllib.parse.urlencode({
        "q": reference,
        "include-verse-numbers": "true",
        "include-footnotes": "false",
        "include-headings": "false",
        "include-copyright": "false",
        "include-short-copyright": "false",
        "indent-paragraphs": "0",
        "indent-poetry": "false",
    })
    url = f"{ESV_API}?{params}"
    try:
        req = urllib.request.Request(url, headers={
            "Authorization": f"Token {key}",
            "User-Agent": "Mozilla/5.0 LiturgyPlanner/1.0"
        })
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        passages = data.get("passages", [])
        if not passages:
            _idle_add(callback, None, "No text returned for this reference"); return
        text = passages[0].strip()
        # Format into verse-per-line using [1] [2] markers
        text = re.sub(r'\[(\d+)\]', lambda m: f"\n{m.group(1)} ", text)
        text = re.sub(r'\n+', '\n', text).strip()
        if cache_key and _CACHE_OK:
            _bible_set(cache_key, text)
        _idle_add(callback, text, None)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            _idle_add(callback, None, "Invalid ESV API key — check Preferences → Scripture")
        else:
            _idle_add(callback, None, f"ESV API error {e.code}")
    except Exception as e:
        _idle_add(callback, None, f"Network error: {type(e).__name__}")
