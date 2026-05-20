"""
observances.py — Liturgical calendar intelligence layer for Rubric

Covers:
  - Fixed-date feasts and saints
  - Ecumenical observances (Week of Prayer for Christian Unity, World Day of Prayer)
  - Social justice commemorations (Canadian and international)
  - Indigenous observances (UCC context: National Indigenous Peoples Day, Orange Shirt Day)
  - Ecological seasons (Season of Creation Sep 1–Oct 4, Earth Day)
  - Pride observances
  - UCC-specific emphases
  - Remembrance and civil days (Canadian)

get_observances(d) returns a list of observance dicts for date d.
When d is a Sunday, the week ahead (Mon–Sat) is also scanned for proximity alerts.
"""

from datetime import date, timedelta


# ── Type catalogue ─────────────────────────────────────────────────────────────
# Each type has a display label and a suggested accent colour (RGBA hex).

TYPES: dict[str, dict] = {
    "feast":          {"label": "Feast",        "colour": "#A16207"},
    "saint":          {"label": "Saint",        "colour": "#7C3AED"},
    "ecumenical":     {"label": "Ecumenical",   "colour": "#0369A1"},
    "indigenous":     {"label": "Indigenous",   "colour": "#C2410C"},
    "social_justice": {"label": "Justice",      "colour": "#B91C1C"},
    "ecological":     {"label": "Creation",     "colour": "#15803D"},
    "pride":          {"label": "Pride",        "colour": "#7C3AED"},
    "remembrance":    {"label": "Remembrance",  "colour": "#374151"},
    "ucc":            {"label": "UCC",          "colour": "#1D4ED8"},
}


# ── Fixed-date observances ─────────────────────────────────────────────────────
# Key: (month, day)
# Value: list of dicts with at minimum "name" and "type".

FIXED: dict[tuple[int, int], list[dict]] = {

    # January
    (1, 1):  [{"name": "New Year's Day",                        "type": "civil"},
              {"name": "Holy Name of Jesus",                     "type": "feast"}],
    (1, 6):  [{"name": "Epiphany of the Lord",                  "type": "feast"}],
    (1, 18): [{"name": "Week of Prayer for Christian Unity begins",  "type": "ecumenical"}],
    (1, 25): [{"name": "Week of Prayer for Christian Unity ends (St Paul)", "type": "ecumenical"}],

    # February
    (2, 2):  [{"name": "Presentation of Christ (Candlemas)",    "type": "feast"}],
    (2, 14): [{"name": "Saints Cyril and Methodius",            "type": "saint"}],

    # March
    (3, 8):  [{"name": "International Women's Day",             "type": "social_justice"}],
    (3, 19): [{"name": "St Joseph",                             "type": "saint"}],
    (3, 21): [{"name": "International Day for the Elimination of Racial Discrimination",
                                                                 "type": "social_justice"}],
    (3, 25): [{"name": "Annunciation of the Lord",              "type": "feast"}],

    # April
    (4, 22): [{"name": "Earth Day",                             "type": "ecological"}],

    # May
    (5, 5):  [{"name": "National Day of Awareness for Missing and Murdered Indigenous Women and Girls (Canada)",
                                                                 "type": "indigenous"}],

    # June
    (6, 4):  [{"name": "International Day of Innocent Children Victims of Aggression",
                                                                 "type": "social_justice"}],
    (6, 5):  [{"name": "World Environment Day",                 "type": "ecological"}],
    (6, 20): [{"name": "World Refugee Day",                     "type": "social_justice"}],
    (6, 21): [{"name": "National Indigenous Peoples Day (Canada)",  "type": "indigenous"}],
    (6, 24): [{"name": "Birth of John the Baptist",             "type": "feast"}],
    (6, 29): [{"name": "Feast of Peter and Paul",               "type": "saint"}],

    # July
    (7, 11): [{"name": "St Benedict of Nursia",                 "type": "saint"}],

    # August
    (8, 6):  [{"name": "Transfiguration of the Lord (Aug 6)",   "type": "feast"}],
    (8, 9):  [{"name": "International Day of the World's Indigenous Peoples",
                                                                 "type": "indigenous"}],
    (8, 15): [{"name": "Mary, Mother of Our Lord",              "type": "feast"}],

    # September
    (9, 1):  [{"name": "World Day of Prayer for the Care of Creation",  "type": "ecological"},
              {"name": "Season of Creation begins",             "type": "ecological"}],
    (9, 21): [{"name": "International Day of Peace",            "type": "social_justice"}],
    (9, 27): [{"name": "World Tourism Day / St Vincent de Paul","type": "saint"}],
    (9, 29): [{"name": "St Michael and All Angels (Michaelmas)", "type": "feast"}],
    (9, 30): [{"name": "National Day for Truth and Reconciliation (Canada)",
                                                                 "type": "indigenous"},
              {"name": "Orange Shirt Day",                      "type": "indigenous"}],

    # October
    (10, 4):  [{"name": "St Francis of Assisi / Season of Creation ends",
                                                                 "type": "ecological"},
               {"name": "World Animal Day",                     "type": "ecological"}],
    (10, 11): [{"name": "Coming Out Day",                       "type": "pride"}],
    (10, 16): [{"name": "World Food Day",                       "type": "social_justice"}],
    (10, 17): [{"name": "International Day for the Eradication of Poverty",
                                                                 "type": "social_justice"}],
    (10, 18): [{"name": "St Luke",                              "type": "saint"}],
    (10, 31): [{"name": "Reformation Day",                      "type": "ecumenical"},
               {"name": "All Hallows' Eve",                     "type": "feast"}],

    # November
    (11, 1):  [{"name": "All Saints' Day",                      "type": "feast"}],
    (11, 2):  [{"name": "All Souls' Day / Día de los Muertos",  "type": "feast"}],
    (11, 11): [{"name": "Remembrance Day (Canada)",             "type": "remembrance"}],
    (11, 20): [{"name": "Transgender Day of Remembrance",       "type": "pride"}],
    (11, 25): [{"name": "International Day for the Elimination of Violence Against Women",
                                                                 "type": "social_justice"}],

    # December
    (12, 1):  [{"name": "World AIDS Day",                       "type": "social_justice"}],
    (12, 3):  [{"name": "International Day of Persons with Disabilities",
                                                                 "type": "social_justice"}],
    (12, 6):  [{"name": "St Nicholas Day",                      "type": "saint"},
               {"name": "National Day of Remembrance (Montréal Massacre)",
                                                                 "type": "remembrance"}],
    (12, 10): [{"name": "Human Rights Day",                     "type": "social_justice"}],
    (12, 25): [{"name": "Christmas Day",                        "type": "feast"}],
    (12, 26): [{"name": "St Stephen / Boxing Day",              "type": "saint"}],
    (12, 27): [{"name": "St John the Apostle",                  "type": "saint"}],
    (12, 28): [{"name": "Holy Innocents",                       "type": "feast"}],
}


# ── Date-range observances ─────────────────────────────────────────────────────
# Each entry has "name", "type", "start" (month, day), "end" (month, day).
# Ranges are evaluated within the same civil year.

RANGES: list[dict] = [
    {
        "name": "Week of Prayer for Christian Unity",
        "type": "ecumenical",
        "start": (1, 18), "end": (1, 25),
    },
    {
        "name": "Season of Creation",
        "type": "ecological",
        "start": (9, 1), "end": (10, 4),
    },
    {
        "name": "Pride Month",
        "type": "pride",
        "start": (6, 1), "end": (6, 30),
    },
    {
        "name": "16 Days of Activism Against Gender-Based Violence",
        "type": "social_justice",
        "start": (11, 25), "end": (12, 10),
    },
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """Return the nth occurrence (1-based) of weekday (0=Mon…6=Sun) in month/year."""
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + (n - 1) * 7)


def _last_weekday(year: int, month: int, weekday: int) -> date:
    """Return the last occurrence of weekday in month/year."""
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    last_day = next_month - timedelta(days=1)
    offset = (last_day.weekday() - weekday) % 7
    return last_day - timedelta(days=offset)


def _nearest_sunday(d: date) -> date:
    wd = (d.weekday() + 1) % 7  # 0 = Sunday
    if wd <= 3:
        return d - timedelta(days=wd)
    return d + timedelta(days=7 - wd)


def _is_sunday(d: date) -> bool:
    return d.weekday() == 6


# ── Computed (dynamic) observances ────────────────────────────────────────────

def _computed_observances(d: date) -> list[dict]:
    """Return observances for date d that require calendar arithmetic."""
    year = d.year
    results = []

    # World Day of Prayer — first Friday of March (ecumenical women's observance)
    wdp = _nth_weekday(year, 3, 4, 1)  # first Friday
    if d == wdp:
        results.append({"name": "World Day of Prayer", "type": "ecumenical"})

    # Martin Luther King Jr. Day — third Monday of January (US; widely recognized)
    mlk = _nth_weekday(year, 1, 0, 3)  # third Monday
    if d == mlk:
        results.append({"name": "Martin Luther King Jr. Day", "type": "social_justice"})

    # Canadian Thanksgiving — second Monday of October
    cth = _nth_weekday(year, 10, 0, 2)
    if d == cth:
        results.append({"name": "Canadian Thanksgiving", "type": "civil"})

    # Indigenous Sunday (UCC) — Sunday nearest National Indigenous Peoples Day (Jun 21)
    jun21 = date(year, 6, 21)
    indigenous_sun = _nearest_sunday(jun21)
    if _is_sunday(d) and d == indigenous_sun:
        results.append({"name": "Indigenous Sunday (UCC)", "type": "indigenous"})

    # Earth Sunday — Sunday nearest Earth Day (Apr 22)
    apr22 = date(year, 4, 22)
    earth_sun = _nearest_sunday(apr22)
    if _is_sunday(d) and d == earth_sun:
        results.append({"name": "Earth Sunday", "type": "ecological"})

    # Pride Sunday — last Sunday of June (for affirming congregations)
    pride_sun = _last_weekday(year, 6, 6)  # last Sunday
    if _is_sunday(d) and d == pride_sun:
        results.append({"name": "Pride Sunday", "type": "pride"})

    # Creation Sunday — first Sunday of September
    creation_sun = _nth_weekday(year, 9, 6, 1)  # first Sunday
    if _is_sunday(d) and d == creation_sun:
        results.append({"name": "Creation Sunday", "type": "ecological"})

    # Remembrance Sunday — Sunday nearest November 11
    nov11 = date(year, 11, 11)
    rem_sun = _nearest_sunday(nov11)
    if _is_sunday(d) and d == rem_sun:
        results.append({"name": "Remembrance Sunday", "type": "remembrance"})

    # All Saints Sunday — Sunday nearest November 1
    nov1 = date(year, 11, 1)
    saints_sun = _nearest_sunday(nov1)
    if _is_sunday(d) and d == saints_sun:
        results.append({"name": "All Saints Sunday", "type": "feast"})

    # Reign of Christ / Christ the King (last Sunday before Advent) handled in RCL;
    # no duplication needed here.

    return results


# ── Main API ──────────────────────────────────────────────────────────────────

def get_observances(d: date) -> list[dict]:
    """
    Return all observances relevant to date d.

    If d is a Sunday, also includes observances falling Mon–Sat of that week,
    tagged with a "proximity" key (e.g., "Orange Shirt Day (Mon Sep 30)") so
    the UI can surface upcoming observances for service planning.
    """
    results: list[dict] = []
    seen: set[str] = set()  # deduplicate by name

    def _add(obs: dict, proximity: str | None = None) -> None:
        key = obs["name"]
        if key in seen:
            return
        seen.add(key)
        if proximity:
            results.append(dict(obs, proximity=proximity))
        else:
            results.append(dict(obs))

    # ── 1. Exact-date fixed observances ──────────────────────────────────────
    for obs in FIXED.get((d.month, d.day), []):
        _add(obs)

    # ── 2. Date ranges that include d ────────────────────────────────────────
    for r in RANGES:
        start = date(d.year, r["start"][0], r["start"][1])
        end   = date(d.year, r["end"][0],   r["end"][1])
        if start <= d <= end:
            _add({"name": r["name"], "type": r["type"]})

    # ── 3. Computed observances for d ────────────────────────────────────────
    for obs in _computed_observances(d):
        _add(obs)

    # ── 4. Coming-this-week scan (Sundays only) ───────────────────────────────
    if _is_sunday(d):
        for offset in range(1, 7):
            wd = d + timedelta(days=offset)
            day_name = wd.strftime("%-d %b")
            week_label = wd.strftime("%a")
            for obs in FIXED.get((wd.month, wd.day), []):
                _add(obs, proximity=f"{week_label} {day_name}")
            # Range boundaries that START during this week
            for r in RANGES:
                start = date(wd.year, r["start"][0], r["start"][1])
                if start == wd:
                    _add({"name": r["name"], "type": r["type"]},
                         proximity=f"{week_label} {day_name}")

    return results
