"""
rcl_data.py — Revised Common Lectionary readings + liturgical calendar logic

Covers all three years (A/B/C) for:
  - Advent 1–4
  - Christmas 1–2
  - Epiphany (Baptism of the Lord through Transfiguration)
  - Ash Wednesday, Lent 1–6 (Palm/Passion Sunday)
  - Holy Thursday, Good Friday
  - Easter Sunday, Easter 2–7
  - Pentecost, Trinity Sunday
  - Proper 4–29 (Ordinary Time after Pentecost) — Semicontinuous OT track
  - Christ the King (= Proper 29)

OT/Psalm in Ordinary Time follows the Semicontinuous track (UCC default).
"""

from datetime import date, timedelta


# ── Liturgical colours ────────────────────────────────────────────────────────

COLOURS = {
    "Advent":       ("Purple",       "#6B21A8"),
    "Christmas":    ("White / Gold", "#B45309"),
    "Epiphany":     ("Green",        "#15803D"),
    "Baptism":      ("White / Gold", "#B45309"),
    "Transfiguration": ("White / Gold", "#B45309"),
    "Lent":         ("Purple",       "#6B21A8"),
    "Palm Sunday":  ("Scarlet",      "#B91C1C"),
    "Holy Thursday":("White / Gold", "#B45309"),
    "Good Friday":  ("Black",        "#111827"),
    "Easter":       ("White / Gold", "#B45309"),
    "Pentecost":    ("Red",          "#B91C1C"),
    "Trinity":      ("White / Gold", "#B45309"),
    "Ordinary":     ("Green",        "#15803D"),
    "Christ the King": ("White / Gold", "#B45309"),
}


# ── Readings database ─────────────────────────────────────────────────────────
# Key:   (year, sunday_id)   year in {'A','B','C'}, or 'ALL' for shared days
# Value: (ot, psalm, epistle, gospel)

READINGS: dict[tuple, tuple] = {

    # ===== ADVENT =====

    ("A", "Advent1"):  ("Isa 2:1–5",         "Ps 122",             "Rom 13:11–14",          "Matt 24:36–44"),
    ("A", "Advent2"):  ("Isa 11:1–10",        "Ps 72:1–7, 18–19",  "Rom 15:4–13",           "Matt 3:1–12"),
    ("A", "Advent3"):  ("Isa 35:1–10",        "Ps 146:5–10",       "Jas 5:7–10",            "Matt 11:2–11"),
    ("A", "Advent4"):  ("Isa 7:10–16",        "Ps 80:1–7, 17–19",  "Rom 1:1–7",             "Matt 1:18–25"),

    ("B", "Advent1"):  ("Isa 64:1–9",         "Ps 80:1–7, 17–19",  "1 Cor 1:3–9",           "Mark 13:24–37"),
    ("B", "Advent2"):  ("Isa 40:1–11",        "Ps 85:1–2, 8–13",   "2 Pet 3:8–15a",         "Mark 1:1–8"),
    ("B", "Advent3"):  ("Isa 61:1–4, 8–11",   "Ps 126",             "1 Thess 5:16–24",       "John 1:6–8, 19–28"),
    ("B", "Advent4"):  ("2 Sam 7:1–11, 16",   "Luke 1:47–55",       "Rom 16:25–27",          "Luke 1:26–38"),

    ("C", "Advent1"):  ("Jer 33:14–16",       "Ps 25:1–10",         "1 Thess 3:9–13",        "Luke 21:25–36"),
    ("C", "Advent2"):  ("Mal 3:1–4",          "Luke 1:68–79",       "Phil 1:3–11",           "Luke 3:1–6"),
    ("C", "Advent3"):  ("Zeph 3:14–20",       "Isa 12:2–6",         "Phil 4:4–7",            "Luke 3:7–18"),
    ("C", "Advent4"):  ("Mic 5:2–5a",         "Luke 1:47–55",       "Heb 10:5–10",           "Luke 1:39–45"),

    # ===== CHRISTMAS (shared across years) =====

    ("ALL", "Christmas1A"): ("Isa 63:7–9",          "Ps 148",   "Heb 2:10–18",      "Matt 2:13–23"),
    ("ALL", "Christmas1B"): ("Isa 61:10–62:3",       "Ps 148",   "Gal 4:4–7",        "Luke 2:22–40"),
    ("ALL", "Christmas1C"): ("1 Sam 2:18–20, 26",    "Ps 148",   "Col 3:12–17",      "Luke 2:41–52"),
    ("ALL", "Christmas2"):  ("Jer 31:7–14",          "Ps 147:12–20", "Eph 1:3–14",   "John 1:[1–9]10–18"),

    # ===== EPIPHANY =====

    ("A", "Epiphany1"): ("Isa 42:1–9",        "Ps 29",              "Acts 10:34–43",         "Matt 3:13–17"),
    ("B", "Epiphany1"): ("Gen 1:1–5",         "Ps 29",              "Acts 19:1–7",           "Mark 1:4–11"),
    ("C", "Epiphany1"): ("Isa 43:1–7",        "Ps 29",              "Acts 8:14–17",          "Luke 3:15–17, 21–22"),

    ("A", "Epiphany2"): ("Isa 49:1–7",        "Ps 40:1–11",         "1 Cor 1:1–9",           "John 1:29–42"),
    ("B", "Epiphany2"): ("1 Sam 3:1–10",      "Ps 139:1–6, 13–18",  "1 Cor 6:12–20",         "John 1:43–51"),
    ("C", "Epiphany2"): ("Isa 62:1–5",        "Ps 36:5–10",         "1 Cor 12:1–11",         "John 2:1–11"),

    ("A", "Epiphany3"): ("Isa 9:1–4",         "Ps 27:1, 4–9",       "1 Cor 1:10–18",         "Matt 4:12–23"),
    ("B", "Epiphany3"): ("Jon 3:1–5, 10",     "Ps 62:5–12",         "1 Cor 7:29–31",         "Mark 1:14–20"),
    ("C", "Epiphany3"): ("Neh 8:1–3, 5–6, 8–10", "Ps 19",          "1 Cor 12:12–31a",       "Luke 4:14–21"),

    ("A", "Epiphany4"): ("Mic 6:1–8",         "Ps 15",              "1 Cor 1:18–31",         "Matt 5:1–12"),
    ("B", "Epiphany4"): ("Deut 18:15–20",     "Ps 111",             "1 Cor 8:1–13",          "Mark 1:21–28"),
    ("C", "Epiphany4"): ("Jer 1:4–10",        "Ps 71:1–6",          "1 Cor 13:1–13",         "Luke 4:21–30"),

    ("A", "Epiphany5"): ("Isa 58:1–9a",       "Ps 112:1–9",         "1 Cor 2:1–12",          "Matt 5:13–20"),
    ("B", "Epiphany5"): ("Isa 40:21–31",      "Ps 147:1–11, 20c",   "1 Cor 9:16–23",         "Mark 1:29–39"),
    ("C", "Epiphany5"): ("Isa 6:1–8",         "Ps 138",             "1 Cor 15:1–11",         "Luke 5:1–11"),

    ("A", "Epiphany6"): ("Deut 30:15–20",     "Ps 119:1–8",         "1 Cor 3:1–9",           "Matt 5:21–37"),
    ("B", "Epiphany6"): ("2 Kgs 5:1–14",      "Ps 30",              "1 Cor 9:24–27",         "Mark 1:40–45"),
    ("C", "Epiphany6"): ("Jer 17:5–10",       "Ps 1",               "1 Cor 15:12–20",        "Luke 6:17–26"),

    ("A", "Epiphany7"): ("Lev 19:1–2, 9–18",  "Ps 119:33–40",       "1 Cor 3:10–11, 16–23",  "Matt 5:38–48"),
    ("B", "Epiphany7"): ("Isa 43:18–25",      "Ps 41",              "2 Cor 1:18–22",         "Mark 2:1–12"),
    ("C", "Epiphany7"): ("Gen 45:3–11, 15",   "Ps 37:1–11, 39–40",  "1 Cor 15:35–38, 42–50", "Luke 6:27–38"),

    ("A", "Epiphany8"): ("Isa 49:8–16a",      "Ps 131",             "1 Cor 4:1–5",           "Matt 6:24–34"),
    ("B", "Epiphany8"): ("Hos 2:14–20",       "Ps 103:1–13, 22",    "2 Cor 3:1–6",           "Mark 2:13–22"),
    ("C", "Epiphany8"): ("Isa 55:10–13",      "Ps 92:1–4, 12–15",   "1 Cor 15:51–58",        "Luke 6:39–49"),

    ("A", "Transfiguration"): ("Exod 24:12–18",  "Ps 2",   "2 Pet 1:16–21",   "Matt 17:1–9"),
    ("B", "Transfiguration"): ("2 Kgs 2:1–12",   "Ps 50:1–6", "2 Cor 4:3–6", "Mark 9:2–9"),
    ("C", "Transfiguration"): ("Exod 34:29–35",  "Ps 99",  "2 Cor 3:12–4:2",  "Luke 9:28–36"),

    # ===== LENT =====

    ("ALL", "AshWednesday"): ("Joel 2:1–2, 12–17", "Ps 51:1–17", "2 Cor 5:20b–6:10", "Matt 6:1–6, 16–21"),

    ("A", "Lent1"): ("Gen 2:15–17; 3:1–7",   "Ps 32",          "Rom 5:12–19",       "Matt 4:1–11"),
    ("B", "Lent1"): ("Gen 9:8–17",            "Ps 25:1–10",     "1 Pet 3:18–22",     "Mark 1:9–15"),
    ("C", "Lent1"): ("Deut 26:1–11",          "Ps 91:1–2, 9–16","Rom 10:8b–13",      "Luke 4:1–13"),

    ("A", "Lent2"): ("Gen 12:1–4a",           "Ps 121",         "Rom 4:1–5, 13–17",  "John 3:1–17"),
    ("B", "Lent2"): ("Gen 17:1–7, 15–16",     "Ps 22:23–31",    "Rom 4:13–25",       "Mark 8:31–38"),
    ("C", "Lent2"): ("Gen 15:1–12, 17–18",    "Ps 27",          "Phil 3:17–4:1",     "Luke 13:31–35"),

    ("A", "Lent3"): ("Exod 17:1–7",           "Ps 95",          "Rom 5:1–11",        "John 4:5–42"),
    ("B", "Lent3"): ("Exod 20:1–17",          "Ps 19",          "1 Cor 1:18–25",     "John 2:13–22"),
    ("C", "Lent3"): ("Isa 55:1–9",            "Ps 63:1–8",      "1 Cor 10:1–13",     "Luke 13:1–9"),

    ("A", "Lent4"): ("1 Sam 16:1–13",         "Ps 23",          "Eph 5:8–14",        "John 9:1–41"),
    ("B", "Lent4"): ("Num 21:4–9",            "Ps 107:1–3, 17–22", "Eph 2:1–10",    "John 3:14–21"),
    ("C", "Lent4"): ("Josh 5:9–12",           "Ps 32",          "2 Cor 5:16–21",     "Luke 15:1–3, 11b–32"),

    ("A", "Lent5"): ("Ezek 37:1–14",          "Ps 130",         "Rom 8:6–11",        "John 11:1–45"),
    ("B", "Lent5"): ("Jer 31:31–34",          "Ps 51:1–12",     "Heb 5:5–10",        "John 12:20–33"),
    ("C", "Lent5"): ("Isa 43:16–21",          "Ps 126",         "Phil 3:4b–14",      "John 12:1–8"),

    # Palm/Passion Sunday — Liturgy of the Palms shared; Passion gospel varies
    ("A", "PalmSunday"): ("Isa 50:4–9a",      "Ps 31:9–16",     "Phil 2:5–11",       "Matt 26:14–27:66"),
    ("B", "PalmSunday"): ("Isa 50:4–9a",      "Ps 31:9–16",     "Phil 2:5–11",       "Mark 14:1–15:47"),
    ("C", "PalmSunday"): ("Isa 50:4–9a",      "Ps 31:9–16",     "Phil 2:5–11",       "Luke 22:14–23:56"),

    ("ALL", "HolyThursday"): ("Exod 12:1–4, 11–14", "Ps 116:1–2, 12–19", "1 Cor 11:23–26", "John 13:1–17, 31b–35"),
    ("ALL", "GoodFriday"):   ("Isa 52:13–53:12",     "Ps 22",             "Heb 10:16–25",   "John 18:1–19:42"),

    # ===== EASTER =====

    ("A", "Easter"):  ("Acts 10:34–43",  "Ps 118:1–2, 14–24", "Col 3:1–4",       "John 20:1–18"),
    ("B", "Easter"):  ("Acts 10:34–43",  "Ps 118:1–2, 14–24", "1 Cor 15:1–11",   "John 20:1–18"),
    ("C", "Easter"):  ("Acts 10:34–43",  "Ps 118:1–2, 14–24", "1 Cor 15:19–26",  "John 20:1–18"),

    ("A", "Easter2"): ("Acts 2:14a, 22–32",  "Ps 16",          "1 Pet 1:3–9",     "John 20:19–31"),
    ("B", "Easter2"): ("Acts 4:32–35",        "Ps 133",         "1 John 1:1–2:2",  "John 20:19–31"),
    ("C", "Easter2"): ("Acts 5:27–32",        "Ps 118:14–29",   "Rev 1:4–8",       "John 20:19–31"),

    ("A", "Easter3"): ("Acts 2:14a, 36–41",   "Ps 116:1–4, 12–19", "1 Pet 1:17–23", "Luke 24:13–35"),
    ("B", "Easter3"): ("Acts 3:12–19",         "Ps 4",            "1 John 3:1–7",  "Luke 24:36b–48"),
    ("C", "Easter3"): ("Acts 9:1–6",           "Ps 30",           "Rev 5:11–14",   "John 21:1–19"),

    ("A", "Easter4"): ("Acts 2:42–47",         "Ps 23",           "1 Pet 2:19–25", "John 10:1–10"),
    ("B", "Easter4"): ("Acts 4:5–12",          "Ps 23",           "1 John 3:16–24","John 10:11–18"),
    ("C", "Easter4"): ("Acts 9:36–43",         "Ps 23",           "Rev 7:9–17",    "John 10:22–30"),

    ("A", "Easter5"): ("Acts 7:55–60",         "Ps 31:1–5, 15–16","1 Pet 2:2–10",  "John 14:1–14"),
    ("B", "Easter5"): ("Acts 8:26–40",         "Ps 22:25–31",     "1 John 4:7–21", "John 15:1–8"),
    ("C", "Easter5"): ("Acts 11:1–18",         "Ps 148",          "Rev 21:1–6",    "John 13:31–35"),

    ("A", "Easter6"): ("Acts 17:22–31",        "Ps 66:8–20",      "1 Pet 3:13–22", "John 14:15–21"),
    ("B", "Easter6"): ("Acts 10:44–48",        "Ps 98",           "1 John 5:1–6",  "John 15:9–17"),
    ("C", "Easter6"): ("Acts 16:9–15",         "Ps 67",           "Rev 21:10, 22–22:5", "John 14:23–29"),

    ("ALL", "Ascension"): ("Acts 1:1–11",      "Ps 47",           "Eph 1:15–23",   "Luke 24:44–53"),

    ("A", "Easter7"): ("Acts 1:6–14",          "Ps 68:1–10, 32–35", "1 Pet 4:12–14; 5:6–11", "John 17:1–11"),
    ("B", "Easter7"): ("Acts 1:15–17, 21–26",  "Ps 1",              "1 John 5:9–13",           "John 17:6–19"),
    ("C", "Easter7"): ("Acts 16:16–34",        "Ps 97",             "Rev 22:12–14, 16–17, 20–21", "John 17:20–26"),

    # ===== PENTECOST & AFTER =====

    ("A", "Pentecost"): ("Acts 2:1–21",        "Ps 104:24–34, 35b", "1 Cor 12:3b–13",  "John 20:19–23"),
    ("B", "Pentecost"): ("Acts 2:1–21",        "Ps 104:24–34, 35b", "Rom 8:22–27",     "John 15:26–27; 16:4b–15"),
    ("C", "Pentecost"): ("Acts 2:1–21",        "Ps 104:24–34, 35b", "Rom 8:14–17",     "John 14:8–17"),

    ("A", "Trinity"): ("Gen 1:1–2:4a",         "Ps 8",              "2 Cor 13:11–13",  "Matt 28:16–20"),
    ("B", "Trinity"): ("Isa 6:1–8",            "Ps 29",             "Rom 8:12–17",     "John 3:1–17"),
    ("C", "Trinity"): ("Prov 8:1–4, 22–31",    "Ps 8",              "Rom 5:1–5",       "John 16:12–15"),

    # ===== ORDINARY TIME — Propers 4–29 (Semicontinuous OT track) =====

    ("A", "Proper4"):  ("Gen 6:9–22; 7:24; 8:14–19",  "Ps 46",              "Rom 1:16–17; 3:22b–28",  "Matt 7:21–29"),
    ("B", "Proper4"):  ("1 Sam 3:1–10",                 "Ps 139:1–6, 13–18",  "2 Cor 4:5–12",           "Mark 2:23–3:6"),
    ("C", "Proper4"):  ("1 Kgs 18:20–21, 30–39",        "Ps 96",              "Gal 1:1–12",             "Luke 7:1–10"),

    ("A", "Proper5"):  ("Gen 12:1–9",                   "Ps 33:1–12",         "Rom 4:13–25",            "Matt 9:9–13, 18–26"),
    ("B", "Proper5"):  ("1 Sam 8:4–11, 16–20",          "Ps 138",             "2 Cor 4:13–5:1",         "Mark 3:20–35"),
    ("C", "Proper5"):  ("1 Kgs 17:8–16",                "Ps 146",             "Gal 1:11–24",            "Luke 7:11–17"),

    ("A", "Proper6"):  ("Gen 18:1–15",                  "Ps 116:1–2, 12–19",  "Rom 5:1–8",              "Matt 9:35–10:8"),
    ("B", "Proper6"):  ("1 Sam 15:34–16:13",            "Ps 20",              "2 Cor 5:6–10, 14–17",    "Mark 4:26–34"),
    ("C", "Proper6"):  ("1 Kgs 21:1–10, 15–21a",        "Ps 5:1–8",           "Gal 2:15–21",            "Luke 7:36–8:3"),

    ("A", "Proper7"):  ("Gen 21:8–21",                  "Ps 86:1–10, 16–17",  "Rom 6:1b–11",            "Matt 10:24–39"),
    ("B", "Proper7"):  ("1 Sam 17:32–49",               "Ps 9:9–20",          "2 Cor 6:1–13",           "Mark 4:35–41"),
    ("C", "Proper7"):  ("1 Kgs 19:1–4, 8–15a",          "Ps 42",              "Gal 3:23–29",            "Luke 8:26–39"),

    ("A", "Proper8"):  ("Gen 22:1–14",                  "Ps 13",              "Rom 6:12–23",            "Matt 10:40–42"),
    ("B", "Proper8"):  ("2 Sam 1:1, 17–27",             "Ps 130",             "2 Cor 8:7–15",           "Mark 5:21–43"),
    ("C", "Proper8"):  ("2 Kgs 2:1–2, 6–14",            "Ps 77:1–2, 11–20",   "Gal 5:1, 13–25",         "Luke 9:51–62"),

    ("A", "Proper9"):  ("Gen 24:34–38, 42–49, 58–67",   "Ps 45:10–17",        "Rom 7:15–25a",           "Matt 11:16–19, 25–30"),
    ("B", "Proper9"):  ("2 Sam 5:1–5, 9–10",            "Ps 48",              "2 Cor 12:2–10",          "Mark 6:1–13"),
    ("C", "Proper9"):  ("2 Kgs 5:1–14",                 "Ps 30",              "Gal 6:1–16",             "Luke 10:1–11, 16–20"),

    ("A", "Proper10"): ("Gen 25:19–34",                 "Ps 119:105–112",     "Rom 8:1–11",             "Matt 13:1–9, 18–23"),
    ("B", "Proper10"): ("2 Sam 6:1–5, 12b–19",          "Ps 24",              "Eph 1:3–14",             "Mark 6:14–29"),
    ("C", "Proper10"): ("Amos 7:7–17",                  "Ps 82",              "Col 1:1–14",             "Luke 10:25–37"),

    ("A", "Proper11"): ("Gen 28:10–19a",                "Ps 139:1–12, 23–24", "Rom 8:12–25",            "Matt 13:24–30, 36–43"),
    ("B", "Proper11"): ("2 Sam 7:1–14a",                "Ps 89:20–37",        "Eph 2:11–22",            "Mark 6:30–34, 53–56"),
    ("C", "Proper11"): ("Amos 8:1–12",                  "Ps 52",              "Col 1:15–28",            "Luke 10:38–42"),

    ("A", "Proper12"): ("Gen 29:15–28",                 "Ps 105:1–11, 45b",   "Rom 8:26–39",            "Matt 13:31–33, 44–52"),
    ("B", "Proper12"): ("2 Sam 11:1–15",                "Ps 14",              "Eph 3:14–21",            "John 6:1–21"),
    ("C", "Proper12"): ("Hos 1:2–10",                   "Ps 85",              "Col 2:6–15",             "Luke 11:1–13"),

    ("A", "Proper13"): ("Gen 32:22–31",                 "Ps 17:1–7, 15",      "Rom 9:1–5",              "Matt 14:13–21"),
    ("B", "Proper13"): ("2 Sam 11:26–12:13a",           "Ps 51:1–12",         "Eph 4:1–16",             "John 6:24–35"),
    ("C", "Proper13"): ("Hos 11:1–11",                  "Ps 107:1–9, 43",     "Col 3:1–11",             "Luke 12:13–21"),

    ("A", "Proper14"): ("Gen 37:1–4, 12–28",            "Ps 105:1–6, 16–22",  "Rom 10:5–15",            "Matt 14:22–33"),
    ("B", "Proper14"): ("2 Sam 18:5–9, 15, 31–33",      "Ps 130",             "Eph 4:25–5:2",           "John 6:35, 41–51"),
    ("C", "Proper14"): ("Isa 1:1, 10–20",               "Ps 50:1–8, 22–23",   "Heb 11:1–3, 8–16",       "Luke 12:32–40"),

    ("A", "Proper15"): ("Gen 45:1–15",                  "Ps 133",             "Rom 11:1–2a, 29–32",     "Matt 15:21–28"),
    ("B", "Proper15"): ("1 Kgs 2:10–12; 3:3–14",        "Ps 111",             "Eph 5:15–20",            "John 6:51–58"),
    ("C", "Proper15"): ("Isa 5:1–7",                    "Ps 80:1–2, 8–19",    "Heb 11:29–12:2",         "Luke 12:49–56"),

    ("A", "Proper16"): ("Exod 1:8–2:10",                "Ps 124",             "Rom 12:1–8",             "Matt 16:13–20"),
    ("B", "Proper16"): ("1 Kgs 8:1, 6, 10–11, 22–30",   "Ps 84",              "Eph 6:10–20",            "John 6:56–69"),
    ("C", "Proper16"): ("Isa 58:9b–14",                 "Ps 103:1–8",         "Heb 12:18–29",           "Luke 13:10–17"),

    ("A", "Proper17"): ("Exod 3:1–15",                  "Ps 105:1–6, 23–26",  "Rom 12:9–21",            "Matt 16:21–28"),
    ("B", "Proper17"): ("Song 2:8–13",                  "Ps 45:1–2, 6–9",     "Jas 1:17–27",            "Mark 7:1–8, 14–15, 21–23"),
    ("C", "Proper17"): ("Jer 2:4–13",                   "Ps 81:1, 10–16",     "Heb 13:1–8, 15–16",      "Luke 14:1, 7–14"),

    ("A", "Proper18"): ("Exod 12:1–14",                 "Ps 149",             "Rom 13:8–14",            "Matt 18:15–20"),
    ("B", "Proper18"): ("Prov 22:1–2, 8–9, 22–23",      "Ps 125",             "Jas 2:1–17",             "Mark 7:24–37"),
    ("C", "Proper18"): ("Jer 18:1–11",                  "Ps 139:1–6, 13–18",  "Phlm 1–21",             "Luke 14:25–33"),

    ("A", "Proper19"): ("Exod 14:19–31",                "Ps 114",             "Rom 14:1–12",            "Matt 18:21–35"),
    ("B", "Proper19"): ("Prov 1:20–33",                 "Ps 19",              "Jas 3:1–12",             "Mark 8:27–38"),
    ("C", "Proper19"): ("Jer 4:11–12, 22–28",           "Ps 14",              "1 Tim 1:12–17",          "Luke 15:1–10"),

    ("A", "Proper20"): ("Exod 16:2–15",                 "Ps 105:1–6, 37–45",  "Phil 1:21–30",           "Matt 20:1–16"),
    ("B", "Proper20"): ("Prov 31:10–31",                "Ps 1",               "Jas 3:13–4:3, 7–8a",    "Mark 9:30–37"),
    ("C", "Proper20"): ("Jer 8:18–9:1",                 "Ps 79:1–9",          "1 Tim 2:1–7",            "Luke 16:1–13"),

    ("A", "Proper21"): ("Exod 17:1–7",                  "Ps 78:1–4, 12–16",   "Phil 2:1–13",            "Matt 21:23–32"),
    ("B", "Proper21"): ("Esth 7:1–6, 9–10; 9:20–22",   "Ps 124",             "Jas 5:13–20",            "Mark 9:38–50"),
    ("C", "Proper21"): ("Jer 32:1–3a, 6–15",            "Ps 91:1–6, 14–16",   "1 Tim 6:6–19",           "Luke 16:19–31"),

    ("A", "Proper22"): ("Exod 20:1–4, 7–9, 12–20",      "Ps 19",              "Phil 3:4b–14",           "Matt 21:33–46"),
    ("B", "Proper22"): ("Job 1:1; 2:1–10",              "Ps 26",              "Heb 1:1–4; 2:5–12",      "Mark 10:2–16"),
    ("C", "Proper22"): ("Lam 1:1–6",                    "Ps 137",             "2 Tim 1:1–14",           "Luke 17:5–10"),

    ("A", "Proper23"): ("Exod 32:1–14",                 "Ps 106:1–6, 19–23",  "Phil 4:1–9",             "Matt 22:1–14"),
    ("B", "Proper23"): ("Job 23:1–9, 16–17",            "Ps 22:1–15",         "Heb 4:12–16",            "Mark 10:17–31"),
    ("C", "Proper23"): ("Jer 29:1, 4–7",                "Ps 66:1–12",         "2 Tim 2:8–15",           "Luke 17:11–19"),

    ("A", "Proper24"): ("Exod 33:12–23",                "Ps 99",              "1 Thess 1:1–10",         "Matt 22:15–22"),
    ("B", "Proper24"): ("Job 38:1–7",                   "Ps 104:1–9, 24, 35c","Heb 5:1–10",             "Mark 10:35–45"),
    ("C", "Proper24"): ("Jer 31:27–34",                 "Ps 119:97–104",      "2 Tim 3:14–4:5",         "Luke 18:1–8"),

    ("A", "Proper25"): ("Deut 34:1–12",                 "Ps 90:1–6, 13–17",   "1 Thess 2:1–8",          "Matt 22:34–46"),
    ("B", "Proper25"): ("Job 42:1–6, 10–17",            "Ps 34:1–8",          "Heb 7:23–28",            "Mark 10:46–52"),
    ("C", "Proper25"): ("Joel 2:23–32",                 "Ps 65",              "2 Tim 4:6–8, 16–18",     "Luke 18:9–14"),

    ("A", "Proper26"): ("Josh 3:7–17",                  "Ps 107:1–7, 33–37",  "1 Thess 2:9–13",         "Matt 23:1–12"),
    ("B", "Proper26"): ("Ruth 1:1–18",                  "Ps 146",             "Heb 9:11–14",            "Mark 12:28–34"),
    ("C", "Proper26"): ("Hab 1:1–4; 2:1–4",             "Ps 119:137–144",     "2 Thess 1:1–4, 11–12",   "Luke 19:1–10"),

    ("A", "Proper27"): ("Josh 24:1–3a, 14–25",          "Ps 78:1–7",          "1 Thess 4:13–18",        "Matt 25:1–13"),
    ("B", "Proper27"): ("Ruth 3:1–5; 4:13–17",          "Ps 127",             "Heb 9:24–28",            "Mark 12:38–44"),
    ("C", "Proper27"): ("Hag 1:15b–2:9",                "Ps 145:1–5, 17–21",  "2 Thess 2:1–5, 13–17",   "Luke 20:27–38"),

    ("A", "Proper28"): ("Judg 4:1–7",                   "Ps 123",             "1 Thess 5:1–11",         "Matt 25:14–30"),
    ("B", "Proper28"): ("1 Sam 1:4–20",                 "1 Sam 2:1–10",       "Heb 10:11–14, 19–25",    "Mark 13:1–8"),
    ("C", "Proper28"): ("Isa 65:17–25",                 "Isa 12",             "2 Thess 3:6–13",         "Luke 21:5–19"),

    # Proper 29 = Christ the King
    ("A", "Proper29"): ("Ezek 34:11–16, 20–24",         "Ps 95:1–7a",         "Eph 1:15–23",            "Matt 25:31–46"),
    ("B", "Proper29"): ("2 Sam 23:1–7",                 "Ps 132:1–12",        "Rev 1:4b–8",             "John 18:33–37"),
    ("C", "Proper29"): ("Jer 23:1–6",                   "Ps 46",              "Col 1:11–20",            "Luke 23:33–43"),
}


# ── Calendar computation ──────────────────────────────────────────────────────

def easter(year: int) -> date:
    """Compute Easter Sunday using the Anonymous Gregorian algorithm."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day   = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def advent_sunday(year: int) -> date:
    """First Sunday of Advent for a given civil year."""
    xmas = date(year, 12, 25)
    # days since last Sunday (0 = Sunday)
    days_since_sunday = (xmas.weekday() + 1) % 7
    last_sunday_before_xmas = xmas - timedelta(days=days_since_sunday)
    return last_sunday_before_xmas - timedelta(weeks=3)


def lectionary_year(d: date) -> str:
    """Return 'A', 'B', or 'C' for the lectionary year containing date d."""
    adv = advent_sunday(d.year)
    # If on or after Advent Sunday, we're in the new lectionary year
    base = d.year + 1 if d >= adv else d.year
    return ["A", "B", "C"][(base - 2023) % 3]


def _nearest_sunday(d: date) -> date:
    """Return the Sunday nearest to d (or d itself if Sunday)."""
    wd = (d.weekday() + 1) % 7  # 0 = Sunday
    if wd <= 3:
        return d - timedelta(days=wd)
    else:
        return d + timedelta(days=7 - wd)


def _sunday_on_or_before(d: date) -> date:
    wd = (d.weekday() + 1) % 7
    return d - timedelta(days=wd)


# Proper number from a date in Ordinary Time (after Pentecost)
# Propers are assigned to the Sunday nearest a given date.
# The date ranges below mark the CENTRE of each Proper's week.
_PROPER_CENTRES = [
    (4,  (5, 31)),
    (5,  (6,  7)),
    (6,  (6, 14)),
    (7,  (6, 21)),
    (8,  (6, 28)),
    (9,  (7,  5)),
    (10, (7, 12)),
    (11, (7, 19)),
    (12, (7, 26)),
    (13, (8,  2)),
    (14, (8,  9)),
    (15, (8, 16)),
    (16, (8, 23)),
    (17, (8, 30)),
    (18, (9,  6)),
    (19, (9, 13)),
    (20, (9, 20)),
    (21, (9, 27)),
    (22, (10,  4)),
    (23, (10, 11)),
    (24, (10, 18)),
    (25, (10, 25)),
    (26, (11,  1)),
    (27, (11,  8)),
    (28, (11, 15)),
    (29, (11, 22)),
]


def _proper_for_date(d: date) -> int | None:
    """Return Proper number (4–29) for a date in Ordinary Time, or None."""
    year = d.year
    best_proper = None
    best_diff = 999
    for proper_num, (mo, dy) in _PROPER_CENTRES:
        centre = date(year, mo, dy)
        diff = abs((d - centre).days)
        if diff < best_diff:
            best_diff = diff
            best_proper = proper_num
    # Propers only used after Trinity Sunday and before Advent
    return best_proper if best_diff <= 3 else None


def get_liturgical_info(d: date) -> dict:
    """
    Return liturgical information for a given date.

    Returns a dict with keys:
      season      (str)  — display name of liturgical season
      week        (str)  — e.g. "Advent 2", "Lent 4", "Proper 12"
      year        (str)  — 'A', 'B', or 'C'
      colour      (str)  — colour name
      colour_hex  (str)  — hex colour code
      ot          (str)  — OT reading
      psalm       (str)  — Psalm
      epistle     (str)  — Epistle / NT reading
      gospel      (str)  — Gospel
      found       (bool) — whether readings were found
    """
    year = d.year
    lec_year = lectionary_year(d)

    e = easter(year)
    prev_e = easter(year - 1)
    adv = advent_sunday(year)
    prev_adv = advent_sunday(year - 1)

    # Key dates
    ash_wed   = e - timedelta(days=46)
    palm_sun  = e - timedelta(days=7)
    holy_thu  = e - timedelta(days=3)
    good_fri  = e - timedelta(days=2)
    pentecost = e + timedelta(days=49)
    trinity   = pentecost + timedelta(days=7)
    christ_king = adv - timedelta(days=7)

    # Previous year dates for early-year reckoning
    prev_pentecost = prev_e + timedelta(days=49)
    prev_trinity   = prev_pentecost + timedelta(days=7)
    prev_christ_king = prev_adv - timedelta(days=7)

    def _lookup(key_year, sunday_id):
        r = READINGS.get((key_year, sunday_id)) or READINGS.get(("ALL", sunday_id))
        return r

    def _result(season_key, week_label, sunday_id, year_key=None):
        yk = year_key or lec_year
        r = _lookup(yk, sunday_id)
        colour_name, colour_hex = COLOURS.get(season_key, ("Green", "#15803D"))
        return {
            "season":     season_key,
            "week":       week_label,
            "year":       lec_year,
            "colour":     colour_name,
            "colour_hex": colour_hex,
            "ot":         r[0] if r else "—",
            "psalm":      r[1] if r else "—",
            "epistle":    r[2] if r else "—",
            "gospel":     r[3] if r else "—",
            "found":      r is not None,
        }

    # ── Special fixed days ────────────────────────────────────────────────────

    if d == good_fri:
        return _result("Good Friday", "Good Friday", "GoodFriday")
    if d == holy_thu:
        return _result("Holy Thursday", "Maundy Thursday", "HolyThursday")
    if d == ash_wed:
        return _result("Lent", "Ash Wednesday", "AshWednesday")

    # ── Advent ────────────────────────────────────────────────────────────────

    for week_num in range(1, 5):
        adv_sun = adv + timedelta(weeks=week_num - 1)
        if d == adv_sun:
            return _result("Advent", f"Advent {week_num}, Year {lec_year}",
                           f"Advent{week_num}")

    # Previous year's Advent 1–4 (for dates before current year's Advent)
    for week_num in range(1, 5):
        adv_sun = prev_adv + timedelta(weeks=week_num - 1)
        if d == adv_sun:
            prev_year = lectionary_year(d)
            return _result("Advent", f"Advent {week_num}, Year {prev_year}",
                           f"Advent{week_num}", prev_year)

    # ── Christmas ─────────────────────────────────────────────────────────────

    if date(year, 12, 25) <= d <= date(year, 12, 31):
        # Find which Sunday after Christmas
        xmas = date(year, 12, 25)
        if d == xmas:
            colour_name, colour_hex = COLOURS["Christmas"]
            return {
                "season": "Christmas", "week": "Christmas Day",
                "year": lec_year, "colour": colour_name, "colour_hex": colour_hex,
                "ot": "Isa 9:2–7", "psalm": "Ps 96",
                "epistle": "Titus 2:11–14", "gospel": "Luke 2:1–14",
                "found": True,
            }
        # Sunday after Christmas
        days_to_next_sun = (6 - d.weekday()) % 7
        next_sun = d + timedelta(days=days_to_next_sun)
        if next_sun.month == 12 and next_sun.day <= 31:
            year_suffix = {"A": "A", "B": "B", "C": "C"}[lec_year]
            return _result("Christmas", f"Christmas 1, Year {lec_year}",
                           f"Christmas1{year_suffix}")

    if date(year, 1, 1) <= d <= date(year, 1, 5):
        # Could be Christmas 2 (2nd Sunday after Christmas)
        if (d.weekday() + 1) % 7 == 0:  # It's a Sunday
            return _result("Christmas", "Christmas 2", "Christmas2")

    # ── Epiphany season ───────────────────────────────────────────────────────

    epiphany = date(year, 1, 6)

    if d == epiphany:
        colour_name, colour_hex = COLOURS["Christmas"]
        return {
            "season": "Epiphany", "week": "Epiphany (Jan 6)",
            "year": lec_year, "colour": colour_name, "colour_hex": colour_hex,
            "ot": "Isa 60:1–6", "psalm": "Ps 72:1–7, 10–14",
            "epistle": "Eph 3:1–12", "gospel": "Matt 2:1–12",
            "found": True,
        }

    if d == _nearest_sunday(epiphany):
        return _result("Baptism", f"Baptism of the Lord, Year {lec_year}", "Epiphany1")

    # Transfiguration = Sunday before Ash Wednesday
    transfig = _sunday_on_or_before(ash_wed - timedelta(days=1))
    if d == transfig:
        return _result("Transfiguration", f"Transfiguration, Year {lec_year}", "Transfiguration")

    if epiphany < d < ash_wed and (d.weekday() + 1) % 7 == 0:
        # Count Epiphany Sundays
        ep1 = _nearest_sunday(epiphany)
        weeks_after = (d - ep1).days // 7
        ep_num = weeks_after + 1
        if 1 <= ep_num <= 8:
            return _result("Epiphany", f"Epiphany {ep_num}, Year {lec_year}",
                           f"Epiphany{ep_num}")

    # ── Lent ──────────────────────────────────────────────────────────────────

    for lent_week in range(1, 7):
        lent_sun = palm_sun - timedelta(weeks=5 - (lent_week - 1))
        if lent_week == 6:
            lent_sun = palm_sun
        else:
            lent_sun = e - timedelta(weeks=7 - lent_week)
        if d == lent_sun:
            if lent_week == 6:
                return _result("Palm Sunday", f"Palm / Passion Sunday, Year {lec_year}", "PalmSunday")
            return _result("Lent", f"Lent {lent_week}, Year {lec_year}", f"Lent{lent_week}")

    # ── Easter ────────────────────────────────────────────────────────────────

    if d == e:
        return _result("Easter", f"Easter Sunday, Year {lec_year}", "Easter")

    for easter_week in range(2, 8):
        easter_sun = e + timedelta(weeks=easter_week - 1)
        if d == easter_sun:
            if easter_week == 7:
                return _result("Easter", f"Easter 7 (Ascension Sunday), Year {lec_year}", "Easter7")
            return _result("Easter", f"Easter {easter_week}, Year {lec_year}", f"Easter{easter_week}")

    ascension = e + timedelta(days=39)
    if d == ascension:
        return _result("Easter", "Ascension of the Lord", "Ascension")

    # ── Pentecost / Trinity / Ordinary Time ───────────────────────────────────

    if d == pentecost:
        return _result("Pentecost", f"Day of Pentecost, Year {lec_year}", "Pentecost")

    if d == trinity:
        return _result("Trinity", f"Trinity Sunday, Year {lec_year}", "Trinity")

    if d == christ_king:
        return _result("Christ the King", f"Reign of Christ / Christ the King, Year {lec_year}", "Proper29")

    # Ordinary Time after Pentecost
    if trinity < d < adv:
        proper = _proper_for_date(d)
        if proper:
            label = "Christ the King" if proper == 29 else f"Proper {proper}"
            sid = f"Proper{proper}"
            return _result("Ordinary", f"{label}, Year {lec_year}", sid)

    # Previous year's Ordinary Time (for dates Jan–May before current Lent)
    if prev_trinity <= d < ash_wed:
        proper = _proper_for_date(date(year - 1, d.month + (12 if d.month < 6 else 0), d.day)
                                   if d.month < 6 else d)
        prev_year = lectionary_year(d)
        if proper:
            return _result("Ordinary", f"Proper {proper}, Year {prev_year}",
                           f"Proper{proper}", prev_year)

    # Fallback
    colour_name, colour_hex = COLOURS["Ordinary"]
    return {
        "season": "Ordinary", "week": "Ordinary Time",
        "year": lec_year, "colour": colour_name, "colour_hex": colour_hex,
        "ot": "—", "psalm": "—", "epistle": "—", "gospel": "—",
        "found": False,
    }
