"""Configuration management for Rubric."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# ── Constants ─────────────────────────────────────────────────────────────────

MAX_UNDO = 50
AUTOSAVE_SECS = 180
CONFIG_PATH = Path.home() / ".config/rubric/config.json"
AUTOSAVE_PATH = Path.home() / ".local/share/rubric/autosave.liturgy"

SECTIONS = [
    ("Gathering", ["Prelude","Welcome","Land acknowledgement","Announcements",
                   "Call to worship","Opening hymn","Prayer of approach",
                   "Prayer of confession","Words of assurance","Gloria / sung response"]),
    ("Word",      ["Hebrew Bible reading","Psalm / sung psalm","Epistle reading",
                   "Gospel reading","Children's time","Hymn","Anthem / special music",
                   "Sermon / reflection","Silent reflection"]),
    ("Response",  ["Hymn","Affirmation of faith","Prayers of the people","Lord's prayer",
                   "Offering / dedication","Stewardship moment","Table liturgy","Communion"]),
    ("Sending",   ["Closing hymn","Commissioning","Benediction","Postlude"]),
]


class Config:
    """Application configuration manager."""

    def __init__(self) -> None:
        self.templates: dict[str, list[dict]] = {}
        self.default_template: str = ""
        self.palette: list[dict] | None = None
        self.last_dir: str = str(Path.home())
        self.recent_files: list[str] = []
        self.use_tabs: bool = False
        self.last_seen_version: str = ""
        self.bulletin: dict[str, Any] = self._default_bulletin()
        self.github_repo: str = ""
        self.first_launch_completed: bool = False
        self.quickstart_dismissed: bool = False
        self.recently_used: list[str] = []
        # Scripture
        self.bible_translation: str = "web"
        self.bible_api_key_esv: str = ""
        # UI modes
        self.simple_mode: bool = True
        self.compact_mode: bool = False
        self.gost_mode: bool = False
        # Advanced
        self.recurring_elements: list[str] = []
        self.element_defaults: dict[str, str] = {}
        self.preamble: dict[str, Any] = {}
        self.ui_panes: dict[str, int] = {}
        self.custom_dates: list[dict] = []  # legacy; migrated into all_dates on first run
        self.all_dates: list[dict] = []
        self._load()

    @staticmethod
    def _default_bulletin() -> dict[str, Any]:
        return {
            "church_name":    "Hope United Church",
            "address":        "",
            "service_time":   "10:30 am",
            "website":        "",
            "email":          "",
            "phone":          "",
            "mission":        "",
            "accessibility":  "All are welcome.",
            "welcome":        "A warm welcome is extended to all.",
            "staff": [],
            "announcements":  [],
            "print_mode":     "booklet",
            "include_scripture": True,
            "include_announcements": True,
            "cover_image": "",
            "cover_style": "full",
        }

    def _load(self) -> None:
        if CONFIG_PATH.exists():
            try:
                d = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                self.palette           = d.get("palette", None)
                self.last_dir          = d.get("last_dir", str(Path.home()))
                self.recent_files      = d.get("recent_files", [])
                self.use_tabs          = d.get("use_tabs", False)
                self.last_seen_version = d.get("last_seen_version", "")
                saved_bulletin = d.get("bulletin", {})
                self.bulletin = {**self._default_bulletin(), **saved_bulletin}
                self.github_repo       = d.get("github_repo", "")
                self.default_template  = d.get("default_template", "")
                self.templates         = d.get("templates", {})
                self.first_launch_completed = d.get("first_launch_completed", False)
                self.quickstart_dismissed   = d.get("quickstart_dismissed", False)
                self.recently_used     = d.get("recently_used", [])
                self.bible_translation = d.get("bible_translation", "web")
                self.bible_api_key_esv = d.get("bible_api_key_esv", "")
                self.simple_mode       = d.get("simple_mode", True)
                self.compact_mode      = d.get("compact_mode", False)
                self.gost_mode         = d.get("gost_mode", False)
                self.recurring_elements = d.get("recurring_elements", [])
                self.element_defaults  = d.get("element_defaults", {})
                self.preamble          = d.get("preamble", {})
                self.ui_panes          = d.get("ui_panes", {})
                self.custom_dates      = d.get("custom_dates", [])
                self.all_dates        = d.get("all_dates", [])
                # migrate old single template
                if not self.templates and d.get("template_items"):
                    self.templates["Default"] = d["template_items"]
                    self.default_template = "Default"
            except (json.JSONDecodeError, KeyError, TypeError):
                pass

    def add_recent(self, path: str) -> None:
        if path in self.recent_files:
            self.recent_files.remove(path)
        self.recent_files.insert(0, path)
        self.recent_files = self.recent_files[:10]

    def save(self) -> None:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        p: dict[str, Any] = {
            "templates":             self.templates,
            "default_template":      self.default_template,
            "last_dir":              self.last_dir,
            "recent_files":          self.recent_files,
            "use_tabs":              self.use_tabs,
            "last_seen_version":     self.last_seen_version,
            "bulletin":              self.bulletin,
            "github_repo":           self.github_repo,
            "first_launch_completed": self.first_launch_completed,
            "quickstart_dismissed":  self.quickstart_dismissed,
            "recently_used":         self.recently_used,
            "bible_translation":     self.bible_translation,
            "bible_api_key_esv":     self.bible_api_key_esv,
            "simple_mode":           self.simple_mode,
            "compact_mode":          self.compact_mode,
            "gost_mode":             self.gost_mode,
            "recurring_elements":    self.recurring_elements,
            "element_defaults":      self.element_defaults,
            "preamble":              self.preamble,
            "ui_panes":              self.ui_panes,
            "custom_dates":          self.custom_dates,
            "all_dates":             self.all_dates,
        }
        if self.palette is not None:
            p["palette"] = self.palette
        CONFIG_PATH.write_text(
            json.dumps(p, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )


# Global config instance
config = Config()


def get_palette() -> list[tuple[str, list[str]]]:
    """Return the current palette (custom or default)."""
    if config.palette:
        return [(d["section"], d["items"]) for d in config.palette]
    return SECTIONS


def seed_all_dates() -> None:
    """Populate config.all_dates from observances.py on first launch.
    Also migrates any legacy custom_dates entries."""
    if config.all_dates:
        return
    try:
        from observances import FIXED, RANGES
    except ImportError:
        return
    entries: list[dict] = []
    for (mm, dd), obs_list in sorted(FIXED.items()):
        for obs in obs_list:
            entries.append({"month": mm, "day": dd,
                            "name": obs["name"],
                            "type": obs.get("type", "civil")})
    for r in RANGES:
        entries.append({"month": r["start"][0], "day": r["start"][1],
                        "name": r["name"], "type": r["type"]})
    # Migrate legacy custom_dates
    _cat_map = {"justice": "social_justice", "religious": "feast"}
    for cd in config.custom_dates:
        t = _cat_map.get(cd.get("category", "justice"), "social_justice")
        entries.append({"month": cd.get("month", 1), "day": cd.get("day", 1),
                        "name": cd.get("name", ""), "type": t})
    config.all_dates = entries
    config.save()
