"""
hymn_suggestions.py — Curated hymn suggestions for VU, MV, and LUS.

Hymn data lives in data/hymn_suggestions.json so it can be edited
without touching Python code. Each entry is [prefix, number, title].

To add or edit hymns, open data/hymn_suggestions.json and edit the
relevant season, proper, or week_override section.
"""

import json
import re
from pathlib import Path

_DATA_FILE = Path(__file__).parent / "data" / "hymn_suggestions.json"
_cache: dict | None = None


def _load() -> dict:
    """Load hymn data from JSON, caching after first load."""
    global _cache
    if _cache is None:
        if not _DATA_FILE.exists():
            raise FileNotFoundError(f"Hymn suggestions data not found: {_DATA_FILE}")
        with open(_DATA_FILE, encoding="utf-8") as f:
            raw = json.load(f)
        # Convert [prefix, number, title] lists to (prefix, number, title) tuples
        _cache = {
            "seasons": {
                k: [tuple(h) for h in v]
                for k, v in raw.get("seasons", {}).items()
            },
            "week_overrides": {
                k: [tuple(h) for h in v]
                for k, v in raw.get("week_overrides", {}).items()
            },
            "propers": {
                int(k): [tuple(h) for h in v]
                for k, v in raw.get("propers", {}).items()
            },
        }
    return _cache


def get_suggestions(week: str, season: str) -> list[tuple[str, int, str]]:
    """
    Return a list of (prefix, number, title) hymn suggestions
    for the given RCL week string and season.

    Priority:
    1. Specific week override (major Sundays, Advent weeks, etc.)
    2. Proper-specific suggestions for Ordinary Time (Propers 4-29)
    3. Season-level suggestions
    Returns at most 8 hymns.
    """
    data = _load()

    # 1. Check week overrides — key must appear in the week string
    for key, hymns in data["week_overrides"].items():
        if key.lower() in week.lower():
            return list(hymns[:8])

    # 2. Proper-specific (Ordinary Time)
    m = re.search(r"Proper\s+(\d+)", week, re.IGNORECASE)
    if m:
        proper_num = int(m.group(1))
        proper_hymns = data["propers"].get(proper_num, [])
        if proper_hymns:
            # Blend proper-specific with season pool for variety
            season_pool = data["seasons"].get("Ordinary", [])
            combined = list(proper_hymns)
            for h in season_pool:
                if h not in combined:
                    combined.append(h)
                if len(combined) >= 8:
                    break
            return combined[:8]

    # 3. Season fallback
    hymns = data["seasons"].get(season, data["seasons"].get("Ordinary", []))
    return list(hymns[:8])
