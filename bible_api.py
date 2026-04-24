"""
bible_api.py — Asynchronous Bible passage fetcher via bible-api.com (WEB translation)

The World English Bible is in the public domain.
API: https://bible-api.com/{reference}?translation=web
"""

import threading
import urllib.request
import urllib.error
import urllib.parse
import json
import re

import gi
gi.require_version("GLib", "2.0")
from gi.repository import GLib

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
    ref = ref.replace('\u2013', '-').replace('\u2014', '-')
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


def fetch_passage(reference: str, callback):
    """
    Asynchronously fetch a Bible passage (World English Bible).

    callback(text: str | None, error: str | None) is called on
    the GLib main loop when the result is ready.
    """
    def fetch():
        cleaned = clean_reference(reference)
        full_ref = map_book(cleaned)
        url = ("https://bible-api.com/"
               + urllib.parse.quote(full_ref)
               + "?translation=web")

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 LiturgyPlanner/1.0"},
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            if "error" in data:
                GLib.idle_add(callback, None, data["error"])
                return

            verses = data.get("verses", [])
            if verses:
                parts = []
                for v in verses:
                    vnum = v.get("verse", "")
                    text = v.get("text", "").strip()
                    parts.append(f"{vnum}\u2003{text}")
                passage = "\n".join(parts)
            else:
                passage = data.get("text", "").strip()

            if not passage:
                GLib.idle_add(callback, None, "No text returned for this reference")
                return

            GLib.idle_add(callback, passage, None)

        except urllib.error.HTTPError as e:
            if e.code == 404:
                GLib.idle_add(callback, None,
                              f"Passage not found: {cleaned}")
            else:
                GLib.idle_add(callback, None, f"HTTP error {e.code}")
        except Exception as e:
            GLib.idle_add(callback, None,
                          f"Network error: {type(e).__name__}")

    threading.Thread(target=fetch, daemon=True).start()
