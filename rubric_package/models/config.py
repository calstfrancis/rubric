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

DEFAULT_PREAMBLE = r"""\documentclass[12pt, letterpaper]{extarticle}
\usepackage{fontspec}
\setmainfont{Junicode}[UprightFont=*,BoldFont=*-Bold,ItalicFont=*-Italic,BoldItalicFont=*-BoldItalic]
\usepackage{geometry}
\geometry{top=1in,bottom=1in,left=0.5in,right=0.5in}
\usepackage{parskip,microtype,titlesec}
\usepackage{multicol}
\setlength{\columnsep}{1.5em}
% Elements: bold left-aligned with rule below
\titleformat{\section}{\normalsize\bfseries}{}{0em}{}[\titlerule]
\titlespacing*{\section}{0pt}{10pt}{4pt}
% Scripture block: suppresses parskip between verses, hanging indent.
% \sverse just emits text; the scripture environment handles all spacing/indent.
\newenvironment{scripture}{%
  \par\begingroup
  \setlength{\parskip}{0pt}%
  \setlength{\parindent}{-2.4em}%
  \leftskip=2.4em
}{%
  \par\endgroup\vspace{4pt}%
}
\newcommand{\sverse}[2]{\textsuperscript{#1}\quad #2\par}
\usepackage{hyperref}
\hypersetup{hidelinks}
"""

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
        self.preamble: str = DEFAULT_PREAMBLE
        self.templates: dict[str, list[dict]] = {}  # name -> items
        self.default_template: str = ""
        self.palette: list[dict] | None = None
        self.last_dir: str = str(Path.home())
        self.recent_files: list[str] = []
        self.use_tabs: bool = False
        self.last_seen_version: str = ""
        self.bulletin: dict[str, Any] = self._default_bulletin()
        self.github_repo: str = ""
        self._load()

    @staticmethod
    def _default_bulletin() -> dict[str, Any]:
        """Return default bulletin configuration."""
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
            "staff": [],          # [{"role": "Minister", "name": "...", "email": "..."}]
            "announcements":  [], # [{"text": "...", "expires": "YYYY-MM-DD" or ""}]
            "print_mode":     "booklet",   # "booklet" or "digital"
            "include_scripture": True,
            "include_announcements": True,
        }

    def _load(self) -> None:
        """Load configuration from disk."""
        if CONFIG_PATH.exists():
            try:
                d = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                self.preamble = d.get("preamble", DEFAULT_PREAMBLE)
                self.palette = d.get("palette", None)
                self.last_dir = d.get("last_dir", str(Path.home()))
                self.recent_files = d.get("recent_files", [])
                self.use_tabs = d.get("use_tabs", False)
                self.last_seen_version = d.get("last_seen_version", "")
                saved_bulletin = d.get("bulletin", {})
                self.bulletin = {**self._default_bulletin(), **saved_bulletin}
                self.github_repo = d.get("github_repo", "")
                self.default_template = d.get("default_template", "")
                self.templates = d.get("templates", {})
                # migrate old single template
                if not self.templates and d.get("template_items"):
                    self.templates["Default"] = d["template_items"]
                    self.default_template = "Default"
            except (json.JSONDecodeError, KeyError, TypeError):
                pass

    def add_recent(self, path: str) -> None:
        """Add a file to recent files list."""
        if path in self.recent_files:
            self.recent_files.remove(path)
        self.recent_files.insert(0, path)
        self.recent_files = self.recent_files[:10]

    def save(self) -> None:
        """Save configuration to disk."""
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        p: dict[str, Any] = {
            "preamble": self.preamble,
            "templates": self.templates,
            "default_template": self.default_template,
            "last_dir": self.last_dir,
            "recent_files": self.recent_files,
            "use_tabs": self.use_tabs,
            "last_seen_version": self.last_seen_version,
            "bulletin": self.bulletin,
            "github_repo": self.github_repo,
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
