#!/usr/bin/env python3
"""
Rubric — GTK4 + libadwaita worship service order builder
Requires: sudo zypper install python3-gobject typelib-1_0-Adw-1 typelib-1_0-Gtk-4_0
"""

import sys, json, re, subprocess, shutil, threading
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib, GObject, Gdk

sys.path.insert(0, str(Path(__file__).parent))
from rcl_data import get_liturgical_info

# Import from refactored package
try:
    from rubric_package.models.config import Config, config, MAX_UNDO, AUTOSAVE_SECS, CONFIG_PATH, AUTOSAVE_PATH, DEFAULT_PREAMBLE, SECTIONS, get_palette
    from rubric_package.models.service import ServiceItem, SectionDivider, entry_from_dict
    from rubric_package.utils.latex import latex_escape, note_for_latex, passage_to_latex, migrate_scripture_note
    from rubric_package.utils.colors import section_colour, hex_to_rgb
    from rubric_package.utils.helpers import is_hymn_element, HYMN_KEYWORDS as _HYMN_KW
    _PACKAGE_OK = True
except ImportError:
    _PACKAGE_OK = False

try:
    from hymn_lookup import lookup_hymn, parse_hymn_ref
    _HYMN_OK = True
except ImportError:
    _HYMN_OK = False

try:
    from bible_api import fetch_passage
    _BIBLE_OK = True
except ImportError:
    _BIBLE_OK = False

try:
    from hymn_suggestions import get_suggestions as _get_hymn_suggestions
    _SUGG_OK = True
except (ImportError, FileNotFoundError):
    _SUGG_OK = False

try:
    from snippets import load_snippets, save_snippets
    _SNIP_OK = True
except ImportError:
    _SNIP_OK = False

# Optional WebKit for inline Hymnary preview
_WEBKIT_OK = False
try:
    gi.require_version("WebKit", "6.0")
    from gi.repository import WebKit as _WebKit
    _WEBKIT_OK = True
except Exception:
    try:
        gi.require_version("WebKit2", "4.1")
        from gi.repository import WebKit2 as _WebKit
        _WEBKIT_OK = True
    except Exception:
        try:
            gi.require_version("WebKit2", "4.0")
            from gi.repository import WebKit2 as _WebKit
            _WEBKIT_OK = True
        except Exception:
            _WebKit = None

# Define constants locally if package import failed
if not _PACKAGE_OK:
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
    _HYMN_KW = {"hymn","psalm","sung","song","music","anthem","gloria"}


# ── Config ────────────────────────────────────────────────────────────────────

APP_VERSION = "0.12"

class Config:
    def __init__(self):
        self.preamble           = DEFAULT_PREAMBLE
        self.templates          : dict[str, list[dict]] = {}  # name -> items
        self.default_template   : str = ""
        self.palette            : list[dict] | None = None
        self.last_dir           = str(Path.home())
        self.recent_files       : list[str] = []
        self.use_tabs           = False
        self.last_seen_version  : str = ""
        self.bulletin           : dict = self._default_bulletin()
        self.github_repo        : str = ""
        self.bible_translation  : str = "web"
        self.bible_api_key_esv  : str = ""
        self.simple_mode            : bool = True
        self.first_launch_completed : bool = False
        self.quickstart_dismissed   : bool = False
        self.recently_used          : list[str] = []
        self._load()

    # backward-compat: old "template_items" key becomes template named "Default"
    @staticmethod
    def _default_bulletin() -> dict:
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

    def _load(self):
        if CONFIG_PATH.exists():
            try:
                d = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                self.preamble         = d.get("preamble",         DEFAULT_PREAMBLE)
                self.palette          = d.get("palette",          None)
                self.last_dir         = d.get("last_dir",         str(Path.home()))
                self.recent_files     = d.get("recent_files",     [])
                self.use_tabs          = d.get("use_tabs",           False)
                self.last_seen_version = d.get("last_seen_version",  "")
                saved_bulletin = d.get("bulletin", {})
                self.bulletin = {**self._default_bulletin(), **saved_bulletin}
                self.github_repo      = d.get("github_repo",      "")
                self.default_template = d.get("default_template", "")
                self.templates        = d.get("templates",        {})
                self.bible_translation = d.get("bible_translation", "web")
                self.bible_api_key_esv = d.get("bible_api_key_esv", "")
                self.simple_mode             = d.get("simple_mode", True)
                self.first_launch_completed  = d.get("first_launch_completed", False)
                self.quickstart_dismissed    = d.get("quickstart_dismissed", False)
                self.recently_used           = d.get("recently_used", [])
                # migrate old single template
                if not self.templates and d.get("template_items"):
                    self.templates["Default"] = d["template_items"]
                    self.default_template = "Default"
            except Exception:
                pass

    def add_recent(self, path: str):
        if path in self.recent_files: self.recent_files.remove(path)
        self.recent_files.insert(0, path)
        self.recent_files = self.recent_files[:10]

    def save(self):
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        p: dict = {
            "preamble":         self.preamble,
            "templates":        self.templates,
            "default_template": self.default_template,
            "last_dir":         self.last_dir,
            "recent_files":     self.recent_files,
            "use_tabs":           self.use_tabs,
            "last_seen_version":  self.last_seen_version,
            "bulletin":           self.bulletin,
            "github_repo":        self.github_repo,
            "bible_translation":  self.bible_translation,
            "bible_api_key_esv":  self.bible_api_key_esv,
            "simple_mode":            self.simple_mode,
            "first_launch_completed": self.first_launch_completed,
            "quickstart_dismissed":   self.quickstart_dismissed,
            "recently_used":          self.recently_used,
        }
        if self.palette is not None: p["palette"] = self.palette
        CONFIG_PATH.write_text(json.dumps(p, indent=2, ensure_ascii=False), encoding="utf-8")

config = Config()


def get_palette() -> list[tuple[str, list[str]]]:
    if config.palette: return [(d["section"], d["items"]) for d in config.palette]
    return SECTIONS


# ── Data model ────────────────────────────────────────────────────────────────

class SectionDivider:
    is_divider = True
    def __init__(self, title="New section"): self.title = title
    def to_dict(self): return {"type":"divider","title":self.title}
    @classmethod
    def from_dict(cls, d): return cls(d.get("title","Section"))

class ServiceItem:
    is_divider = False
    def __init__(self, name, section, note="", leader="",
                 show_in_bulletin=True, bulletin_note=""):
        self.name = name; self.section = section
        self.note = note; self.leader = leader
        self.show_in_bulletin = show_in_bulletin  # whether element appears in bulletin
        self.bulletin_note = bulletin_note         # congregation-facing text (overrides note)
    def to_dict(self):
        return {"type": "item", "name": self.name, "section": self.section,
                "note": self.note, "leader": self.leader,
                "show_in_bulletin": self.show_in_bulletin,
                "bulletin_note": self.bulletin_note}
    @classmethod
    def from_dict(cls, d):
        return cls(d["name"], d.get("section", ""), d.get("note", ""),
                   d.get("leader", ""),
                   d.get("show_in_bulletin", True),
                   d.get("bulletin_note", ""))

def _entry_from_dict(d):
    return SectionDivider.from_dict(d) if d.get("type")=="divider" else ServiceItem.from_dict(d)

def _latex_escape(t):
    for c,e in [("\\","\\textbackslash{}"),("&","\\&"),("%","\\%"),("$","\\$"),
                ("#","\\#"),("_","\\_"),("{","\\{"),("}","\\}"),
                ("~","\\textasciitilde{}"),("^","\\textasciicircum{}")]:
        t = t.replace(c, e)
    return t

def _note_for_latex(n):
    if not n: return ""
    return n if any(l.strip().startswith("\\") for l in n.splitlines()) else _latex_escape(n)


def _passage_to_latex(reference: str, text: str, translation: str = "web") -> str:
    r"""
    Convert Bible verse text to LaTeX inside a {scripture} environment.
    The API sometimes splits a single verse across multiple lines;
    we join all lines until the next numbered verse into one \sverse call.
    """
    lines = text.strip().splitlines()

    # First pass: group lines into (verse_num, full_text) pairs
    verses = []   # list of (vnum_str, text_str)
    current_num = None
    current_parts = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        m = re.match(r'^(\d+)\s*(.*)', line)
        if m:
            # Save previous verse if any
            if current_num is not None:
                verses.append((current_num, " ".join(current_parts)))
            current_num = m.group(1)
            current_parts = [m.group(2).strip()] if m.group(2).strip() else []
        else:
            # Continuation of the current verse
            if current_num is not None:
                current_parts.append(line)
            # else: text before any verse number -- ignore

    # Flush last verse
    if current_num is not None:
        verses.append((current_num, " ".join(current_parts)))

    latex_lines = []
    for vnum, vtext in verses:
        latex_lines.append(f"\\sverse{{{vnum}}}{{{_latex_escape(vtext)}}}")

    ref_escaped = _latex_escape(reference)
    trl_label = translation.upper()
    body = "\n".join(latex_lines)
    return (
        f"% {ref_escaped} ({trl_label})\n"
        f"{{\\small\\textit{{{ref_escaped} ({trl_label})}}}}\n"
        f"\\begin{{scripture}}\n"
        f"{body}\n"
        f"\\end{{scripture}}"
    )

def _migrate_scripture_note(note):
    if r'\begin{quotation}' not in note:
        return note
    lines = note.splitlines()
    pre, verses, post = [], [], []
    ref_line = ""
    in_q = False
    after_q = False
    for line in lines:
        s = line.strip()
        if s == r'\begin{quotation}':  in_q = True;  continue
        if s == r'\end{quotation}':    in_q = False; after_q = True; continue
        if after_q:                    post.append(line); continue
        if not in_q:                   pre.append(line); continue
        if not s: continue
        if s.startswith(r'\textit{') or s.startswith('% '):
            m = re.search(r'\\textit\{\\small ([^}]+)\}', s)
            ref_line = "{\\small\\textit{" + m.group(1) + "}}" if m else s
            continue
        m = re.match(r'\\noindent\\textsuperscript\{(\d+)\}(.+)', s)
        if m:
            verses.append("\\sverse{" + m.group(1) + "}{" + m.group(2).strip() + "}")
            continue
        if verses: verses[-1] = verses[-1] + " " + s
        else: verses.append(s + r'\par')
    result = "\n".join(pre).rstrip()
    if ref_line: result += ("\n" if result else "") + ref_line
    if verses:
        result += "\n\\begin{scripture}\n" + "\n".join(verses) + "\n\\end{scripture}"
    if post: result += "\n" + "\n".join(post)
    return result


def _section_colour(section):
    pal = get_palette(); secs = [s for s,_ in pal]
    cols = ["#1D9E75","#534AB7","#993C1D","#185FA5","#B45309","#6B21A8","#15803D","#B91C1C"]
    try: return cols[secs.index(section) % len(cols)]
    except ValueError: return "#888780"

def _hex_to_rgb(h):
    h = h.lstrip("#")
    return int(h[0:2],16)/255, int(h[2:4],16)/255, int(h[4:6],16)/255

def _is_hymn_element(name): return any(k in name.lower() for k in _HYMN_KW)


# ── Backward compatibility aliases ────────────────────────────────────────────

# If package is available, create underscore aliases for existing code
# Note: _entry_from_dict is NOT overridden here — it must use the inline
# ServiceItem/SectionDivider classes so that isinstance() checks elsewhere match.
if _PACKAGE_OK:
    _latex_escape = latex_escape
    _note_for_latex = note_for_latex
    _passage_to_latex = passage_to_latex
    _migrate_scripture_note = migrate_scripture_note
    _section_colour = section_colour
    _hex_to_rgb = hex_to_rgb


# ── Bible viewer ──────────────────────────────────────────────────────────────

class BibleViewer(Adw.Window):
    def __init__(self, reference, on_insert_cb, translation="web", esv_key="", **kw):
        super().__init__(**kw)
        self._translation = translation
        from bible_api import TRANSLATION_LABELS
        trl_label = TRANSLATION_LABELS.get(translation, translation.upper())
        self.set_title(f"{reference}  ·  {translation.upper()}"); self.set_default_size(520,460); self.set_modal(True)
        self._on_insert_cb = on_insert_cb; self._text = ""; self._ref = reference
        self._verses: list[dict] = []   # raw verse dicts from API
        tv = Adw.ToolbarView(); tv.add_top_bar(Adw.HeaderBar()); self.set_content(tv)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._status = Adw.StatusPage(title="Loading…", icon_name="content-loading-symbolic")
        self._status.set_vexpand(True); outer.append(self._status)
        self._scroll = Gtk.ScrolledWindow()
        self._scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._scroll.set_vexpand(True); self._scroll.set_visible(False)
        self._scroll.set_margin_start(16); self._scroll.set_margin_end(16)
        self._scroll.set_margin_top(12); self._scroll.set_margin_bottom(6)
        self._tv = Gtk.TextView()
        self._tv.set_editable(False); self._tv.set_cursor_visible(False)
        self._tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR); self._tv.add_css_class("card")
        self._tv.set_top_margin(10); self._tv.set_bottom_margin(10)
        self._tv.set_left_margin(12); self._tv.set_right_margin(12)
        self._scroll.set_child(self._tv); outer.append(self._scroll)
        self._bot = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._bot.set_margin_start(16); self._bot.set_margin_end(16)
        self._bot.set_margin_top(4); self._bot.set_margin_bottom(14); self._bot.set_visible(False)
        attr = Gtk.Label(label=trl_label)
        attr.add_css_class("caption"); attr.add_css_class("dim-label")
        attr.set_hexpand(True); attr.set_xalign(0); self._bot.append(attr)
        ins = Gtk.Button(label="Insert as LaTeX"); ins.add_css_class("suggested-action")
        ins.connect("clicked", self._on_insert); self._bot.append(ins); outer.append(self._bot)
        tv.set_content(outer)
        if _BIBLE_OK: fetch_passage(reference, self._on_fetched, translation=translation, esv_key=esv_key)
        else: self._status.set_title("Unavailable"); self._status.set_description("bible_api.py not found")

    def _on_fetched(self, text, error):
        if error:
            self._status.set_title("Could not load passage"); self._status.set_description(error)
            self._status.set_icon_name("network-error-symbolic")
        else:
            self._text = text; self._tv.get_buffer().set_text(text, -1)
            self._status.set_visible(False); self._scroll.set_visible(True); self._bot.set_visible(True)

    def _on_insert(self, _):
        if self._on_insert_cb and self._text:
            latex = _passage_to_latex(self._ref, self._text, self._translation)
            self._on_insert_cb(latex)
        self.close()


# ── Preferences ───────────────────────────────────────────────────────────────

class PreferencesWindow(Adw.PreferencesWindow):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.set_title("Preferences"); self.set_default_size(700,560); self.set_search_enabled(False)
        self._build_view()
        if not config.simple_mode:
            self._build_latex()
        self._build_template(); self._build_palette()
        if _SNIP_OK and not config.simple_mode:
            self._build_snippets()
        self._build_bulletin(); self._build_github(); self._build_scripture()
        self.connect("close-request", self._on_close)

    def _build_latex(self):
        page = Adw.PreferencesPage(title="LaTeX", icon_name="text-x-generic-symbolic"); self.add(page)
        grp = Adw.PreferencesGroup(title="LaTeX preamble",
            description="Everything before \\begin{document}. Export adds begin/end automatically.")
        page.add(grp)
        scroll = Gtk.ScrolledWindow(); scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_height(280); scroll.add_css_class("card")
        scroll.set_margin_top(4); scroll.set_margin_bottom(4)
        self._preamble_view = Gtk.TextView(); self._preamble_view.set_monospace(True)
        self._preamble_view.set_wrap_mode(Gtk.WrapMode.NONE)
        self._preamble_view.set_top_margin(10); self._preamble_view.set_bottom_margin(10)
        self._preamble_view.set_left_margin(12); self._preamble_view.set_right_margin(12)
        self._preamble_view.get_buffer().set_text(config.preamble, -1)
        scroll.set_child(self._preamble_view); grp.add(scroll)
        rg = Adw.PreferencesGroup(); page.add(rg)
        rr = Adw.ActionRow(title="Reset to default", subtitle="Restore built-in Junicode/XeLaTeX preamble")
        rb = Gtk.Button(label="Reset", valign=Gtk.Align.CENTER); rb.add_css_class("destructive-action")
        rb.connect("clicked", lambda _: self._preamble_view.get_buffer().set_text(DEFAULT_PREAMBLE,-1))
        rr.add_suffix(rb); rr.set_activatable_widget(rb); rg.add(rr)

    def _build_view(self):
        page = Adw.PreferencesPage(title="View", icon_name="view-grid-symbolic"); self.add(page)

        # ── Simple mode ───────────────────────────────────────────────────
        mode_grp = Adw.PreferencesGroup(
            title="Feature level",
            description="Simple mode hides LaTeX export, GitHub sync, CSV export, "
                        "snippets, and other technical features. You can turn it off "
                        "whenever you're ready to explore more."
        )
        page.add(mode_grp)
        try:
            self._simple_row = Adw.SwitchRow(
                title="Simple mode",
                subtitle="Show only the essential features for building a service"
            )
            self._simple_row.set_active(config.simple_mode)
            mode_grp.add(self._simple_row)
        except AttributeError:
            row = Adw.ActionRow(title="Simple mode",
                                subtitle="Show only the essential features for building a service")
            self._simple_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
            self._simple_switch.set_active(config.simple_mode)
            row.add_suffix(self._simple_switch); row.set_activatable_widget(self._simple_switch)
            mode_grp.add(row); self._simple_row = None

        # ── Layout ────────────────────────────────────────────────────────
        grp = Adw.PreferencesGroup(title="Service order layout",
            description="Tab view groups items by section divider. "
                        "Switching modes preserves all data.")
        page.add(grp)
        try:
            self._tabs_row = Adw.SwitchRow(title="Tab view",
                                           subtitle="Show sections as tabs instead of one long list")
            self._tabs_row.set_active(config.use_tabs)
            grp.add(self._tabs_row)
        except AttributeError:
            row = Adw.ActionRow(title="Tab view",
                                subtitle="Show sections as tabs instead of one long list")
            self._tabs_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
            self._tabs_switch.set_active(config.use_tabs)
            row.add_suffix(self._tabs_switch); row.set_activatable_widget(self._tabs_switch)
            grp.add(row); self._tabs_row = None

    def _simple_mode_active(self) -> bool:
        if hasattr(self, "_simple_row") and self._simple_row:
            return self._simple_row.get_active()
        return self._simple_switch.get_active()

    def _tabs_active(self):
        if hasattr(self, "_tabs_row") and self._tabs_row:
            return self._tabs_row.get_active()
        return self._tabs_switch.get_active()

    def _build_template(self):
        self._tmpl_page = Adw.PreferencesPage(title="Templates", icon_name="document-new-symbolic")
        self.add(self._tmpl_page)
        self._tmpl_groups: list = []
        self._refresh_templates()

    def _refresh_templates(self):
        for g in self._tmpl_groups:
            try: self._tmpl_page.remove(g)
            except: pass
        self._tmpl_groups.clear()

        if config.templates:
            for tname, items in list(config.templates.items()):
                is_default = (tname == config.default_template)
                grp = Adw.PreferencesGroup(title=tname + (" ★" if is_default else ""))

                # Set as default button
                if not is_default:
                    def_btn = Gtk.Button(label="Set as default", valign=Gtk.Align.CENTER)
                    def_btn.add_css_class("flat")
                    def_btn.connect("clicked", lambda _b, n=tname: self._set_default_template(n))
                    grp.set_header_suffix(def_btn)

                # Item list (preview, read-only)
                count = len(items)
                dividers = sum(1 for i in items if i.get("type") == "divider")
                summary = Adw.ActionRow(
                    title=f"{count} entries" if not dividers else f"{count - dividers} elements, {dividers} dividers",
                    subtitle=", ".join(i.get("name", i.get("title", "")) for i in items[:4] if i.get("type") != "divider") +
                             ("…" if sum(1 for i in items if i.get("type") != "divider") > 4 else "")
                )
                grp.add(summary)

                # Delete button row
                del_grp = Adw.PreferencesGroup()
                del_row = Adw.ActionRow(title=f"Delete \u201c{tname}\u201d",
                                        subtitle="Cannot be undone")
                del_btn = Gtk.Button(label="Delete", valign=Gtk.Align.CENTER)
                del_btn.add_css_class("destructive-action")
                del_btn.connect("clicked", lambda _b, n=tname: self._delete_template(n))
                del_row.add_suffix(del_btn); del_row.set_activatable_widget(del_btn)
                del_grp.add(del_row)

                self._tmpl_page.add(grp); self._tmpl_groups.append(grp)
                self._tmpl_page.add(del_grp); self._tmpl_groups.append(del_grp)
        else:
            empty_grp = Adw.PreferencesGroup(title="No templates saved")
            empty_row = Adw.ActionRow(
                title="Build a service order and choose",
                subtitle='"Save order as template…" from the menu'
            )
            empty_row.set_sensitive(False); empty_grp.add(empty_row)
            self._tmpl_page.add(empty_grp); self._tmpl_groups.append(empty_grp)

    def _set_default_template(self, name: str):
        config.default_template = name; config.save(); self._refresh_templates()

    def _delete_template(self, name: str):
        if name in config.templates: del config.templates[name]
        if config.default_template == name:
            config.default_template = next(iter(config.templates), "")
        config.save(); self._refresh_templates()

    def _build_palette(self):
        self._pal_page = Adw.PreferencesPage(title="Palette", icon_name="view-list-symbolic"); self.add(self._pal_page)
        self._pal = [{"section":s,"items":list(i)} for s,i in get_palette()]
        self._pal_grps = []; self._refresh_pal()

    def _refresh_pal(self):
        for g in self._pal_grps:
            try: self._pal_page.remove(g)
            except: pass
        self._pal_grps.clear()
        for sd in self._pal:
            grp = Adw.PreferencesGroup(title=sd["section"])
            rb = Gtk.Button(label="Remove section", valign=Gtk.Align.CENTER)
            rb.add_css_class("destructive-action"); rb.add_css_class("flat")
            rb.connect("clicked", lambda _,s=sd: (self._pal.__setitem__(slice(None), [x for x in self._pal if x is not s]), self._refresh_pal()))
            grp.set_header_suffix(rb)
            for n in sd["items"]:
                row = Adw.ActionRow(title=n)
                db = Gtk.Button(icon_name="list-remove-symbolic", tooltip_text=f"Remove '{n}'", valign=Gtk.Align.CENTER)
                db.add_css_class("flat"); db.connect("clicked", lambda _,s=sd,i=n: (s["items"].__delitem__(s["items"].index(i)), self._refresh_pal()))
                row.add_suffix(db); grp.add(row)
            ae = Adw.EntryRow(title="Add element…"); ae.set_show_apply_button(True)
            ae.connect("apply", lambda r,s=sd: (s["items"].append(r.get_text().strip()) if r.get_text().strip() and r.get_text().strip() not in s["items"] else None, r.set_text(""), self._refresh_pal()))
            grp.add(ae); self._pal_page.add(grp); self._pal_grps.append(grp)
        nsg = Adw.PreferencesGroup(title="Add new section")
        nse = Adw.EntryRow(title="Section name…"); nse.set_show_apply_button(True)
        nse.connect("apply", lambda r: (self._pal.append({"section":r.get_text().strip(),"items":[]}) if r.get_text().strip() and not any(s["section"]==r.get_text().strip() for s in self._pal) else None, r.set_text(""), self._refresh_pal()))
        nsg.add(nse); self._pal_page.add(nsg); self._pal_grps.append(nsg)
        rsg = Adw.PreferencesGroup()
        rsr = Adw.ActionRow(title="Reset palette to defaults", subtitle="Restore built-in liturgical elements")
        rst = Gtk.Button(label="Reset", valign=Gtk.Align.CENTER); rst.add_css_class("destructive-action")
        rst.connect("clicked", lambda _: (self._pal.__setitem__(slice(None), [{"section":s,"items":list(i)} for s,i in SECTIONS]), setattr(config,"palette",None), config.save(), self._refresh_pal()))
        rsr.add_suffix(rst); rsr.set_activatable_widget(rst); rsg.add(rsr)
        self._pal_page.add(rsg); self._pal_grps.append(rsg)

    def _build_snippets(self):
        self._snip_page = Adw.PreferencesPage(title="Snippets", icon_name="format-text-bold-symbolic")
        self.add(self._snip_page)
        self._snippets = load_snippets()
        self._snip_groups: list = []
        self._refresh_snippets_prefs()

    def _refresh_snippets_prefs(self):
        for g in self._snip_groups:
            try: self._snip_page.remove(g)
            except: pass
        self._snip_groups.clear()

        for i, snip in enumerate(self._snippets):
            grp = Adw.PreferencesGroup(title=snip["name"])
            # Delete button
            del_btn = Gtk.Button(label="Delete", valign=Gtk.Align.CENTER)
            del_btn.add_css_class("destructive-action"); del_btn.add_css_class("flat")
            del_btn.connect("clicked", lambda _b, idx=i: self._delete_snippet(idx))
            grp.set_header_suffix(del_btn)
            # Preview row
            preview = snip["content"].replace("\n"," ")[:80]+("…" if len(snip["content"])>80 else "")
            row = Adw.ActionRow(title=preview); row.set_subtitle_lines(2); grp.add(row)
            self._snip_page.add(grp); self._snip_groups.append(grp)

        # Add new snippet group
        add_grp = Adw.PreferencesGroup(title="Add new snippet")
        name_entry = Adw.EntryRow(title="Snippet name"); add_grp.add(name_entry)
        content_scroll = Gtk.ScrolledWindow()
        content_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        content_scroll.set_min_content_height(80); content_scroll.add_css_class("card")
        content_scroll.set_margin_top(4); content_scroll.set_margin_bottom(4)
        content_tv = Gtk.TextView(); content_tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        content_tv.set_top_margin(8); content_tv.set_bottom_margin(8)
        content_tv.set_left_margin(10); content_tv.set_right_margin(10)
        content_scroll.set_child(content_tv); add_grp.add(content_scroll)
        save_btn_row = Adw.ActionRow(title="Save snippet")
        save_btn = Gtk.Button(label="Save", valign=Gtk.Align.CENTER); save_btn.add_css_class("suggested-action")
        def on_save(_b):
            name = name_entry.get_text().strip()
            buf = content_tv.get_buffer(); s,e = buf.get_bounds()
            content = buf.get_text(s,e,False).strip()
            if name and content:
                self._snippets.append({"name": name, "content": content})
                save_snippets(self._snippets); self._refresh_snippets_prefs()
        save_btn.connect("clicked", on_save)
        save_btn_row.add_suffix(save_btn); save_btn_row.set_activatable_widget(save_btn)
        add_grp.add(save_btn_row)
        self._snip_page.add(add_grp); self._snip_groups.append(add_grp)

    def _delete_snippet(self, idx: int):
        if 0 <= idx < len(self._snippets):
            del self._snippets[idx]
            save_snippets(self._snippets); self._refresh_snippets_prefs()

    def _build_bulletin(self):
        """Bulletin preferences tab — church info, staff, announcements."""
        page = Adw.PreferencesPage(title="Bulletin", icon_name="document-print-symbolic")
        self.add(page)

        # Church info
        info_grp = Adw.PreferencesGroup(title="Church information")
        page.add(info_grp)
        b = config.bulletin
        self._bul_entries = {}

        def _entry_row(key, title, grp=None, subtitle=""):
            row = Adw.EntryRow(title=title)
            if subtitle: row.set_subtitle(subtitle)
            row.set_text(b.get(key, ""))
            (grp or info_grp).add(row)
            self._bul_entries[key] = row

        _entry_row("church_name",  "Church name")
        _entry_row("address",      "Address")
        _entry_row("service_time", "Service time")
        _entry_row("website",      "Website")
        _entry_row("email",        "Email")
        _entry_row("phone",        "Phone")

        # Boilerplate text
        text_grp = Adw.PreferencesGroup(title="Boilerplate text")
        page.add(text_grp)
        _entry_row("welcome",       "Welcome line",       grp=text_grp)
        _entry_row("accessibility", "Accessibility note", grp=text_grp)

        def _text_row(key, title):
            scroll = Gtk.ScrolledWindow()
            scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            scroll.set_min_content_height(60); scroll.add_css_class("card")
            scroll.set_margin_top(4); scroll.set_margin_bottom(4)
            tv = Gtk.TextView(); tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
            tv.set_top_margin(6); tv.set_bottom_margin(6)
            tv.set_left_margin(8); tv.set_right_margin(8)
            tv.get_buffer().set_text(b.get(key, ""), -1)
            scroll.set_child(tv); text_grp.add(scroll)
            self._bul_entries[key] = tv

        _text_row("mission", "Mission statement")

        # Staff list
        self._staff_grp = Adw.PreferencesGroup(title="Staff / contact list",
            description="Appears in the acknowledgements block at the back of the bulletin")
        page.add(self._staff_grp)
        self._staff_rows = []
        self._bul_staff_widgets = []
        for member in b.get("staff", []):
            self._add_staff_row(member.get("role",""), member.get("name",""), member.get("email",""))
        add_staff_row = Adw.ActionRow(title="Add staff member")
        add_btn = Gtk.Button(label="Add", valign=Gtk.Align.CENTER)
        add_btn.add_css_class("flat")
        add_btn.connect("clicked", lambda _: self._add_staff_row("", "", ""))
        add_staff_row.add_suffix(add_btn)
        self._staff_grp.add(add_staff_row)

        # Announcements
        self._ann_grp = Adw.PreferencesGroup(title="Announcements",
            description="Each announcement can have an optional expiry date (YYYY-MM-DD)")
        page.add(self._ann_grp)
        self._bul_ann_widgets = []
        for ann in b.get("announcements", []):
            self._add_announcement_row(ann.get("text",""), ann.get("expires",""))
        add_ann_row = Adw.ActionRow(title="Add announcement")
        add_ann_btn = Gtk.Button(label="Add", valign=Gtk.Align.CENTER)
        add_ann_btn.add_css_class("flat")
        add_ann_btn.connect("clicked", lambda _: self._add_announcement_row("", ""))
        add_ann_row.add_suffix(add_ann_btn)
        self._ann_grp.add(add_ann_row)

    def _add_staff_row(self, role, name, email):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_margin_top(4); box.set_margin_bottom(4)
        box.set_margin_start(4); box.set_margin_end(4)

        role_e = Gtk.Entry(); role_e.set_placeholder_text("Role")
        role_e.set_hexpand(True); role_e.set_text(role)
        name_e = Gtk.Entry(); name_e.set_placeholder_text("Name")
        name_e.set_hexpand(True); name_e.set_text(name)
        email_e = Gtk.Entry(); email_e.set_placeholder_text("Email (optional)")
        email_e.set_hexpand(True); email_e.set_text(email)

        del_btn = Gtk.Button(icon_name="list-remove-symbolic")
        del_btn.add_css_class("flat")
        widgets = [role_e, name_e, email_e, None]  # row filled in below
        del_btn.connect("clicked", lambda _b, w=widgets: self._remove_staff_row(w))

        box.append(role_e); box.append(name_e); box.append(email_e); box.append(del_btn)
        row = Adw.ActionRow(); row.set_child(box)
        widgets[3] = row  # fill in the ActionRow reference
        self._staff_grp.add(row)
        self._bul_staff_widgets.append((role_e, name_e, email_e, row))

    def _remove_staff_row(self, widgets):
        role_e, name_e, email_e, row = widgets
        self._bul_staff_widgets = [w for w in self._bul_staff_widgets if w[0] is not role_e]
        if row:
            row.set_visible(False)

    def _add_announcement_row(self, text, expires):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_top(4); box.set_margin_bottom(4)
        box.set_margin_start(4); box.set_margin_end(4)

        # Text area
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_height(50); scroll.add_css_class("card")
        tv = Gtk.TextView(); tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        tv.set_top_margin(6); tv.set_bottom_margin(6)
        tv.set_left_margin(8); tv.set_right_margin(8)
        tv.get_buffer().set_text(text, -1)
        scroll.set_child(tv); box.append(scroll)

        # Expires row
        exp_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        exp_lbl = Gtk.Label(label="Expires (YYYY-MM-DD, or blank):")
        exp_lbl.add_css_class("caption"); exp_lbl.set_xalign(0)
        exp_e = Gtk.Entry(); exp_e.set_text(expires); exp_e.set_width_chars(14)
        del_btn = Gtk.Button(icon_name="list-remove-symbolic")
        del_btn.add_css_class("flat")
        exp_box.append(exp_lbl); exp_box.append(exp_e)
        sp = Gtk.Box(); sp.set_hexpand(True); exp_box.append(sp)
        exp_box.append(del_btn)
        box.append(exp_box)

        row = Adw.ActionRow(); row.set_child(box)
        widgets = (tv, exp_e, row)
        del_btn.connect("clicked", lambda _b, w=widgets: w[2].set_visible(False))
        self._ann_grp.add(row)
        self._bul_ann_widgets.append((tv, exp_e, row))

    def _on_close(self, _):
        if hasattr(self, "_preamble_view"):
            buf = self._preamble_view.get_buffer(); s,e = buf.get_bounds()
            config.preamble = buf.get_text(s,e,False)
        builtin = [{"section":s,"items":list(i)} for s,i in SECTIONS]
        config.palette = self._pal if self._pal != builtin else None
        config.use_tabs = self._tabs_active()
        config.simple_mode = self._simple_mode_active()
        win = self.get_transient_for()
        if win and hasattr(win, "_apply_simple_mode"):
            win._apply_simple_mode()

        # Save bulletin config
        b = config.bulletin
        for key, widget in self._bul_entries.items():
            if isinstance(widget, Gtk.TextView):
                buf = widget.get_buffer(); s2,e2 = buf.get_bounds()
                b[key] = buf.get_text(s2,e2,False)
            else:
                b[key] = widget.get_text()
        b["staff"] = [
            {"role": r.get_text(), "name": n.get_text(), "email": em.get_text()}
            for r, n, em, row in self._bul_staff_widgets
            if row.get_visible() and r.get_text().strip()
        ]
        b["announcements"] = []
        for tv, exp_e, row in self._bul_ann_widgets:
            if not row.get_visible(): continue
            buf = tv.get_buffer(); s2,e2 = buf.get_bounds()
            text = buf.get_text(s2,e2,False).strip()
            if text:
                b["announcements"].append({"text": text, "expires": exp_e.get_text().strip()})

        # Save scripture settings
        if hasattr(self, "_scripture_combo"):
            idx = self._scripture_combo.get_selected()
            config.bible_translation = self._scripture_trl_keys[idx] if idx < len(self._scripture_trl_keys) else "web"
        if hasattr(self, "_esv_key_row"):
            config.bible_api_key_esv = self._esv_key_row.get_text().strip()

        config.save(); return False

    def _build_scripture(self):
        from bible_api import TRANSLATION_LABELS
        page = Adw.PreferencesPage(title="Scripture", icon_name="x-office-document-symbolic")
        self.add(page)

        grp = Adw.PreferencesGroup(title="Bible translation",
            description="Used when fetching passages via Scripture lookup and RCL reading buttons.")
        page.add(grp)

        trl_keys = list(TRANSLATION_LABELS.keys())
        trl_display = list(TRANSLATION_LABELS.values())

        combo_row = Adw.ComboRow(title="Translation")
        model = Gtk.StringList()
        for label in trl_display:
            model.append(label)
        combo_row.set_model(model)
        current_trl = config.bible_translation if config.bible_translation in trl_keys else "web"
        combo_row.set_selected(trl_keys.index(current_trl) if current_trl in trl_keys else 0)
        grp.add(combo_row)
        self._scripture_combo = combo_row
        self._scripture_trl_keys = trl_keys

        esv_grp = Adw.PreferencesGroup(title="ESV API key",
            description="Required only for the ESV translation. Get a free key at api.esv.org (ministry use).")
        page.add(esv_grp)

        self._esv_key_row = Adw.EntryRow(title="ESV API key")
        self._esv_key_row.set_text(config.bible_api_key_esv)
        esv_grp.add(self._esv_key_row)

        note_row = Adw.ActionRow(title="api.esv.org",
            subtitle="Sign up for a free ministry API key at api.esv.org")
        note_row.set_sensitive(False)
        esv_grp.add(note_row)

        # Show/hide ESV key section based on selection
        def on_trl_changed(combo, _pspec):
            idx = combo.get_selected()
            key = trl_keys[idx] if idx < len(trl_keys) else "web"
            esv_grp.set_visible(key == "esv")

        combo_row.connect("notify::selected", on_trl_changed)
        # Set initial visibility
        esv_grp.set_visible(current_trl == "esv")

    def _build_github(self):
        page = Adw.PreferencesPage(title="GitHub", icon_name="network-server-symbolic")
        self.add(page)

        # ── Repository folder ──────────────────────────────────────────────
        loc_grp = Adw.PreferencesGroup(
            title="Repository folder",
            description="A folder on this computer that is (or will become) a git repository. "
                        "Rubric will save liturgy files, LaTeX, and PDFs in subfolders here."
        )
        page.add(loc_grp)

        self._repo_row = Adw.ActionRow(title="Folder")
        self._repo_row.set_subtitle(config.github_repo or "Not configured")
        browse_btn = Gtk.Button(label="Browse…", valign=Gtk.Align.CENTER)
        browse_btn.add_css_class("flat")
        browse_btn.connect("clicked", self._on_repo_browse)
        self._repo_row.add_suffix(browse_btn)
        loc_grp.add(self._repo_row)

        # ── New repository setup ───────────────────────────────────────────
        setup_grp = Adw.PreferencesGroup(
            title="New repository",
            description="Creates liturgy/, tex/, and pdf/ subfolders and initialises git in the selected folder."
        )
        page.add(setup_grp)

        setup_row = Adw.ActionRow(
            title="Set up selected folder as a repository",
            subtitle="Run this once after choosing a folder above"
        )
        setup_btn = Gtk.Button(label="Set up", valign=Gtk.Align.CENTER)
        setup_btn.add_css_class("suggested-action")
        setup_btn.connect("clicked", self._on_repo_setup)
        setup_row.add_suffix(setup_btn)
        setup_grp.add(setup_row)

        # ── GitHub remote ──────────────────────────────────────────────────
        remote_grp = Adw.PreferencesGroup(
            title="Connect to GitHub",
            description="Paste the URL of your GitHub repository (e.g. https://github.com/yourname/liturgy). "
                        "Create a free private repository at github.com first."
        )
        page.add(remote_grp)

        self._remote_entry = Adw.EntryRow(title="GitHub repository URL")
        self._remote_entry.set_text(self._detect_remote())
        remote_grp.add(self._remote_entry)

        connect_row = Adw.ActionRow(title="Save remote URL")
        connect_btn = Gtk.Button(label="Connect", valign=Gtk.Align.CENTER)
        connect_btn.add_css_class("suggested-action")
        connect_btn.connect("clicked", self._on_remote_connect)
        connect_row.add_suffix(connect_btn)
        remote_grp.add(connect_row)

        # ── Pull ───────────────────────────────────────────────────────────
        pull_grp = Adw.PreferencesGroup(
            title="Pull from GitHub",
            description="Download changes from GitHub — use when you have worked on another machine or a collaborator has pushed changes."
        )
        page.add(pull_grp)

        pull_row = Adw.ActionRow(title="Pull latest changes")
        pull_btn = Gtk.Button(label="Pull", valign=Gtk.Align.CENTER)
        pull_btn.connect("clicked", self._on_prefs_pull)
        pull_row.add_suffix(pull_btn)
        pull_grp.add(pull_row)

        # ── Getting-started guide ──────────────────────────────────────────
        help_grp = Adw.PreferencesGroup(title="Getting started — new users")
        page.add(help_grp)
        for title, subtitle in [
            ("1. Create a GitHub account",    "Free at github.com"),
            ("2. Create a private repository",'Name it something like "liturgy" and tick Private'),
            ("3. Set up a folder above",       "Browse to an empty folder, then click Set up"),
            ("4. Paste the repository URL",    "Copy from the green Code button → HTTPS tab on GitHub"),
            ("5. Click Connect, then Push ⟳",  "Use the ⟳ button in the main toolbar to push files"),
        ]:
            r = Adw.ActionRow(title=title, subtitle=subtitle)
            r.set_sensitive(False)
            help_grp.add(r)

    def _detect_remote(self) -> str:
        repo = config.github_repo
        if not repo:
            return ""
        try:
            r = subprocess.run(
                ["git", "-C", repo, "remote", "get-url", "origin"],
                capture_output=True, text=True, timeout=5
            )
            return r.stdout.strip() if r.returncode == 0 else ""
        except Exception:
            return ""

    def _on_repo_browse(self, _btn):
        dlg = Gtk.FileDialog(title="Choose repository folder")
        dlg.select_folder(self, None, self._on_repo_folder_chosen)

    def _on_repo_folder_chosen(self, dlg, result):
        try:
            f = dlg.select_folder_finish(result)
        except GLib.Error:
            return
        config.github_repo = f.get_path()
        config.save()
        self._repo_row.set_subtitle(config.github_repo)
        self._remote_entry.set_text(self._detect_remote())

    def _on_repo_setup(self, _btn):
        repo = config.github_repo
        if not repo:
            dlg = Adw.MessageDialog(transient_for=self, heading="No folder selected",
                body="Browse to a folder first, then click Set up.")
            dlg.add_response("ok", "OK"); dlg.present(); return

        repo_path = Path(repo)
        errors = []
        for subdir in ("liturgy", "tex", "pdf", "bulletins"):
            try:
                (repo_path / subdir).mkdir(parents=True, exist_ok=True)
            except OSError as e:
                errors.append(str(e))

        gitignore = repo_path / ".gitignore"
        if not gitignore.exists():
            try:
                gitignore.write_text(
                    "# LaTeX build artefacts\n"
                    "*.aux\n*.log\n*.out\n*.fls\n*.fdb_latexmk\n*.synctex.gz\n"
                    "*.toc\n*.lof\n*.lot\n*.dvi\n*.maf\n*.mtc\n*.mtc0\n",
                    encoding="utf-8"
                )
            except OSError as e:
                errors.append(str(e))

        try:
            r = subprocess.run(["git", "-C", repo, "init"],
                               capture_output=True, text=True, timeout=10)
            if r.returncode != 0:
                errors.append(r.stderr.strip())
        except Exception as e:
            errors.append(str(e))

        if errors:
            dlg = Adw.MessageDialog(transient_for=self, heading="Setup error",
                body="\n".join(errors))
            dlg.add_response("ok", "OK"); dlg.present()
        else:
            dlg = Adw.MessageDialog(
                transient_for=self,
                heading="Repository ready",
                body=f"Created liturgy/, tex/, pdf/, and bulletins/ folders in:\n{repo}\n\n"
                     "Next: create a private repository on github.com, copy its URL, "
                     "and paste it in the field below."
            )
            dlg.add_response("ok", "OK"); dlg.present()

    def _on_remote_connect(self, _btn):
        repo = config.github_repo
        url  = self._remote_entry.get_text().strip()
        if not repo:
            dlg = Adw.MessageDialog(transient_for=self, heading="No repository configured",
                body="Set up a folder first.")
            dlg.add_response("ok", "OK"); dlg.present(); return
        if not url:
            dlg = Adw.MessageDialog(transient_for=self, heading="No URL entered",
                body="Paste your GitHub repository URL in the field above.")
            dlg.add_response("ok", "OK"); dlg.present(); return
        try:
            check = subprocess.run(["git", "-C", repo, "remote", "get-url", "origin"],
                                   capture_output=True, text=True, timeout=5)
            cmd = ["git", "-C", repo, "remote",
                   "set-url" if check.returncode == 0 else "add",
                   "origin", url]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        except Exception as e:
            dlg = Adw.MessageDialog(transient_for=self, heading="Error", body=str(e))
            dlg.add_response("ok", "OK"); dlg.present(); return

        if r.returncode != 0:
            dlg = Adw.MessageDialog(transient_for=self, heading="Could not connect",
                body=r.stderr.strip() or "Unknown error")
            dlg.add_response("ok", "OK"); dlg.present()
        else:
            dlg = Adw.MessageDialog(
                transient_for=self,
                heading="Connected to GitHub",
                body=f"Remote set to:\n{url}\n\n"
                     "Use the ⟳ Push button in the main toolbar to upload your files."
            )
            dlg.add_response("ok", "OK"); dlg.present()

    def _on_prefs_pull(self, _btn):
        repo = config.github_repo
        if not repo:
            dlg = Adw.MessageDialog(transient_for=self, heading="No repository configured",
                body="Set up a folder and connect to GitHub first.")
            dlg.add_response("ok", "OK"); dlg.present(); return

        progress = Adw.MessageDialog(transient_for=self,
            heading="Pulling from GitHub…", body="Please wait.")
        progress.present()

        def run():
            try:
                r = subprocess.run(["git", "-C", repo, "pull"],
                                   capture_output=True, text=True, timeout=60)
                def on_done():
                    progress.destroy()
                    if r.returncode != 0:
                        err = (r.stderr or r.stdout or "Unknown error").strip()
                        d = Adw.MessageDialog(transient_for=self, heading="Pull failed", body=err[:400])
                        d.add_response("ok", "OK"); d.present()
                    else:
                        out = r.stdout.strip() or "Already up to date."
                        d = Adw.MessageDialog(transient_for=self, heading="Pull complete", body=out[:400])
                        d.add_response("ok", "OK"); d.present()
                GLib.idle_add(on_done)
            except Exception as e:
                def on_err():
                    progress.destroy()
                    d = Adw.MessageDialog(transient_for=self, heading="Pull error", body=str(e))
                    d.add_response("ok", "OK"); d.present()
                GLib.idle_add(on_err)

        threading.Thread(target=run, daemon=True).start()


# ── Main window ───────────────────────────────────────────────────────────────

class MainWindow(Adw.ApplicationWindow):
    def __init__(self, **kw):
        super().__init__(**kw); self.set_default_size(1000,700)
        self.service_entries: list = []
        self._undo_stack: list[list[dict]] = []
        self._redo_stack: list[list[dict]] = []
        self.current_file: str|None = None
        self.tex_file: str|None = None
        self.modified = False; self._updating_note = False
        self.selected_date = None; self._selected_global_idx = -1
        self._current_readings: dict[str,str] = {}
        self._tab_listboxes: list[tuple] = []
        self._tab_ctx_div: SectionDivider | None = None
        self._colour_bar_rgb = (0.12,0.62,0.46)
        self._compiling_toast: Adw.Toast | None = None

        self._setup_actions(); self._build_ui(); self._update_title(); self._update_tex_btn()
        # Seed from default template on first launch
        items = config.templates.get(config.default_template,
                next(iter(config.templates.values()), None))
        if items:
            for d in items:
                self.service_entries.append(_entry_from_dict(d))
            self._refresh_order_list()
        GLib.timeout_add_seconds(AUTOSAVE_SECS, self._do_autosave)
        GLib.idle_add(self._check_autosave)
        GLib.idle_add(self._check_welcome)
        threading.Thread(target=self._background_index_scan, daemon=True).start()

    # ── Repo helpers ──────────────────────────────────────────────────────────

    def _repo_subdir(self, subdir: str):
        """Return Path to {github_repo}/{subdir}/ if it exists, else None."""
        if config.github_repo:
            p = Path(config.github_repo) / subdir
            if p.is_dir():
                return p
        return None

    # ── Simple mode ───────────────────────────────────────────────────────────

    def _apply_simple_mode(self):
        simple = config.simple_mode
        self.push_btn.set_visible(not simple)
        self.tex_btn.set_visible(not simple)
        self.pdf_btn.set_visible(not simple)
        if hasattr(self, "_rr_btn"):
            self._rr_btn.set_visible(not simple)
        self._refresh_menu()

    def _refresh_menu(self):
        simple = config.simple_mode
        menu = Gio.Menu()
        menu.append("Preferences", "win.preferences")
        menu.append("Duplicate service", "win.duplicate")
        if not simple:
            menu.append("Save order as template…", "win.save-template")
        menu.append("Save as…", "win.save-as")

        export_sec = Gio.Menu()
        export_sec.append("Export as…", "win.export-as")
        menu.append_section("Export", export_sec)

        menu.append("Service Planner… (Ctrl+Shift+L)", "win.open-planner")
        menu.append("Element Library… (Ctrl+Shift+K)", "win.open-library")
        menu.append("Past Liturgies… (Ctrl+Shift+H)", "win.open-archive")

        if not simple:
            git_sec = Gio.Menu()
            git_sec.append("Push to GitHub (Ctrl+Shift+G)", "win.git-push")
            git_sec.append("Pull from GitHub", "win.git-pull")
            menu.append_section("GitHub Sync", git_sec)

        if not simple:
            adv_sec = Gio.Menu()
            adv_sec.append("Responsive reading… (Ctrl+R)", "win.responsive-reading")
            adv_sec.append("Snippets… (Ctrl+Shift+I)", "win.snippets")
            menu.append_section("Advanced", adv_sec)

        help_sec = Gio.Menu()
        help_sec.append("Help (F1)", "win.show-help")
        help_sec.append("FAQ", "win.show-faq")
        help_sec.append("What's New", "win.show-changelog")
        help_sec.append("Welcome wizard…", "win.show-wizard")
        help_sec.append("About Rubric", "win.show-about")
        menu.append_section("Help", help_sec)
        menu.append_section("Recent files", self._recent_sec)

        self._menu_btn.set_menu_model(menu)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _setup_actions(self):
        for name, cb, accel in [
            ("new",           self.new_service,      "<Ctrl>n"),
            ("open",          self.open_file,         "<Ctrl>o"),
            ("save",          self.save_file,         "<Ctrl>s"),
            ("save-as",       self.save_file_as,      "<Ctrl><Shift>s"),
            ("export-text",   self.export_text,       None),
            ("export-latex",       self.export_latex,          None),
            ("quick-export-latex", self.quick_export_latex,    "<Ctrl>e"),
            ("compile-pdf",        self.compile_pdf,           "<Ctrl><Shift>p"),
            ("save-template", self.save_as_template,  None),
            ("duplicate",     self.duplicate_service, None),
            ("add-custom",    self.add_custom,        "<Ctrl><Shift>n"),
            ("add-divider",   self.add_divider,       "<Ctrl>d"),
            ("move-up",       self.move_up,           "<Ctrl>Up"),
            ("move-down",     self.move_down,         "<Ctrl>Down"),
            ("remove-item",   self.remove_item,       "Delete"),
            ("undo",          self.undo,              "<Ctrl>z"),
            ("redo",          self.redo,              "<Ctrl><Shift>z"),
            ("preferences",   self.open_preferences,  "<Ctrl>comma"),
            ("clear-recent",       self._clear_recent,      None),
            ("tab-rename",         self._tab_rename_action, None),
            ("tab-delete",         self._tab_delete_action, None),
            ("unlink-tex",         self._unlink_tex,           None),
            ("responsive-reading", self.open_responsive_reading,"<Ctrl>r"),
            ("snippets",           self.open_snippets,          "<Ctrl><Shift>i"),
            ("scripture-search",   self.open_scripture_search,  "<Ctrl><Shift>f"),
            ("export-csv",         self.export_csv,             None),
            ("export-bulletin",    self.export_bulletin,        "<Ctrl><Shift>b"),
            ("export-html",        self.export_html,            None),
            ("open-planner",       self.open_planner,           "<Ctrl><Shift>l"),
            ("git-push",           self.git_push,               "<Ctrl><Shift>g"),
            ("git-pull",           self.git_pull,               None),
            ("show-help",          lambda: self._show_doc("HELP"),       "F1"),
            ("show-faq",           lambda: self._show_doc("FAQ"),        None),
            ("show-changelog",     lambda: self._show_doc("CHANGELOG"),  None),
            ("show-wizard",        self._show_first_launch_wizard,        None),
            ("open-library",       self.open_library,                     "<Ctrl><Shift>k"),
            ("open-archive",       self.open_archive,                     "<Ctrl><Shift>h"),
            ("show-about",         self.show_about,                       None),
            ("export-as",          self.export_as,                      None),
        ]:
            a = Gio.SimpleAction.new(name, None)
            a.connect("activate", lambda _a,_p,f=cb: f()); self.add_action(a)
            if accel: self.get_application().set_accels_for_action(f"win.{name}", [accel])
        ra = Gio.SimpleAction.new("open-recent-file", GLib.VariantType.new("s"))
        ra.connect("activate", lambda _a,p: self._confirm_discard(lambda path=p.get_string(): self._load_file(path)))
        self.add_action(ra)
        na = Gio.SimpleAction.new("noop", None); na.set_enabled(False); self.add_action(na)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        hdr = Adw.HeaderBar()
        for icon,tip,cb in [("document-new-symbolic","New service (Ctrl+N)",self.new_service),
                             ("document-open-symbolic","Open… (Ctrl+O)",self.open_file)]:
            b = Gtk.Button(icon_name=icon, tooltip_text=tip); b.connect("clicked", lambda _,f=cb: f()); hdr.pack_start(b)
        self.undo_btn = Gtk.Button(icon_name="edit-undo-symbolic", tooltip_text="Undo (Ctrl+Z)")
        self.undo_btn.connect("clicked", lambda _: self.undo()); self.undo_btn.set_sensitive(False); hdr.pack_start(self.undo_btn)
        self.redo_btn = Gtk.Button(icon_name="edit-redo-symbolic", tooltip_text="Redo (Ctrl+Shift+Z)")
        self.redo_btn.connect("clicked", lambda _: self.redo()); self.redo_btn.set_sensitive(False); hdr.pack_start(self.redo_btn)

        # Title widget lives inside a MenuButton so clicking it opens the service info popover
        self.title_widget = Adw.WindowTitle(title="Rubric", subtitle="New service")

        # Popover contents: title entry + date picker
        pop_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        pop_box.set_margin_top(14); pop_box.set_margin_bottom(14)
        pop_box.set_margin_start(16); pop_box.set_margin_end(16)

        tl = Gtk.Label(label="Service title"); tl.add_css_class("heading"); tl.set_xalign(0)
        pop_box.append(tl)
        self.service_title_entry = Gtk.Entry()
        self.service_title_entry.set_placeholder_text("Title, date, or occasion…")
        self.service_title_entry.set_size_request(280, -1)
        self.service_title_entry.connect("changed", lambda _: self._mark_modified())
        pop_box.append(self.service_title_entry)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL); pop_box.append(sep)

        dl = Gtk.Label(label="Date"); dl.add_css_class("heading"); dl.set_xalign(0)
        pop_box.append(dl)
        cal_pop = Gtk.Popover(); cal_pop.set_has_arrow(True)
        self.calendar = Gtk.Calendar()
        self.calendar.set_margin_top(8); self.calendar.set_margin_bottom(8)
        self.calendar.set_margin_start(8); self.calendar.set_margin_end(8)
        self.calendar.connect("day-selected", self._on_calendar_day_selected)
        cal_pop.set_child(self.calendar)
        date_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.date_button = Gtk.MenuButton(label="No date selected", popover=cal_pop)
        self.date_button.set_hexpand(True); date_row.append(self.date_button)
        clr = Gtk.Button(icon_name="edit-clear-symbolic", tooltip_text="Clear date")
        clr.add_css_class("flat"); clr.connect("clicked", self._on_clear_date); date_row.append(clr)
        pop_box.append(date_row)

        info_pop = Gtk.Popover(); info_pop.set_child(pop_box)
        info_pop.set_has_arrow(False); info_pop.set_position(Gtk.PositionType.BOTTOM)

        title_btn = Gtk.MenuButton(popover=info_pop)
        title_btn.add_css_class("flat"); title_btn.set_child(self.title_widget)
        hdr.set_title_widget(title_btn)
        self.selected_date = None

        sb = Gtk.Button(icon_name="document-save-symbolic", tooltip_text="Save (Ctrl+S)")
        sb.add_css_class("suggested-action"); sb.connect("clicked", lambda _: self.save_file()); hdr.pack_end(sb)

        self.push_btn = Gtk.Button(icon_name="emblem-synchronizing-symbolic",
                                   tooltip_text="Push to GitHub (Ctrl+Shift+G)")
        self.push_btn.connect("clicked", lambda _: self.git_push())
        hdr.pack_end(self.push_btn)

        self.tex_btn = Gtk.Button(icon_name="emblem-documents-symbolic",
                                  tooltip_text="Export to LaTeX (Ctrl+E)")
        self.tex_btn.connect("clicked", lambda _: self.quick_export_latex())

        # Right-click → change linked file or unlink
        tex_gesture = Gtk.GestureClick(); tex_gesture.set_button(3)
        def on_tex_right(_g, _n, _x, _y):
            tex_menu = Gio.Menu()
            if self.tex_file:
                tex_menu.append(f"Linked: {Path(self.tex_file).name}", "win.noop")
                tex_menu.append("Change linked file…", "win.export-latex")
                tex_menu.append("Unlink .tex file",    "win.unlink-tex")
            else:
                tex_menu.append("No linked file", "win.noop")
                tex_menu.append("Choose file to link…", "win.export-latex")
            pop = Gtk.PopoverMenu.new_from_model(tex_menu)
            pop.set_parent(self.tex_btn); pop.popup()
        tex_gesture.connect("pressed", on_tex_right)
        self.tex_btn.add_controller(tex_gesture)
        hdr.pack_end(self.tex_btn)

        self.pdf_btn = Gtk.Button(icon_name="document-print-symbolic",
                                  tooltip_text="Compile to PDF via xelatex (Ctrl+Shift+P)")
        self.pdf_btn.connect("clicked", lambda _: self.compile_pdf())
        hdr.pack_end(self.pdf_btn)

        # Lectionary year tracker — shows current RCL year and season, updates daily
        self._lect_label = Gtk.Label()
        self._lect_label.add_css_class("caption")
        self._lect_label.add_css_class("dim-label")
        self._lect_label.set_margin_start(4); self._lect_label.set_margin_end(4)
        self._lect_label.set_valign(Gtk.Align.CENTER)
        hdr.pack_end(self._lect_label)
        self._update_lect_label()
        # Refresh at midnight (86400 seconds)
        GLib.timeout_add_seconds(86400, self._update_lect_label)
        self._recent_sec = Gio.Menu()
        self._rebuild_recent_menu()
        self._menu_btn = Gtk.MenuButton(icon_name="open-menu-symbolic", tooltip_text="Menu")
        hdr.pack_end(self._menu_btn)
        self._refresh_menu()
        # Bulletin preview toggle button (header bar, end side)
        self._preview_visible = False
        self._preview_pending_id = None
        self._preview_btn = Gtk.ToggleButton(icon_name="document-print-preview-symbolic",
                                             tooltip_text="Toggle live bulletin preview")
        self._preview_btn.connect("toggled", self._toggle_preview_panel)
        hdr.pack_end(self._preview_btn)

        tv = Adw.ToolbarView(); tv.add_top_bar(hdr)
        self._toast_overlay = Adw.ToastOverlay()

        # Outer paned: palette | content
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_shrink_start_child(False); paned.set_shrink_end_child(False); paned.set_position(290)
        paned.set_start_child(self._build_palette_panel())

        # Inner paned: order panel | bulletin preview (preview hidden by default)
        self._preview_panel = self._build_preview_panel()
        self._preview_panel.set_visible(False)
        self._preview_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self._preview_paned.set_shrink_start_child(False)
        self._preview_paned.set_shrink_end_child(False)
        self._preview_paned.set_start_child(self._build_order_panel())
        self._preview_paned.set_end_child(self._preview_panel)
        paned.set_end_child(self._preview_paned)

        self._toast_overlay.set_child(paned)
        tv.set_content(self._toast_overlay)
        self.set_content(tv)
        self._apply_simple_mode()

    # ── Palette panel ─────────────────────────────────────────────────────────

    def _build_palette_panel(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL); box.set_size_request(230,-1)
        # Search entry
        self._palette_search = Gtk.SearchEntry()
        self._palette_search.set_placeholder_text("Search elements…")
        self._palette_search.set_margin_start(12); self._palette_search.set_margin_end(12)
        self._palette_search.set_margin_top(8); self._palette_search.set_margin_bottom(2)
        self._palette_search.connect("search-changed", self._on_palette_search_changed)
        box.append(self._palette_search)

        # Hymn cache indicator
        cache_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        cache_bar.set_margin_start(12); cache_bar.set_margin_end(12)
        cache_bar.set_margin_bottom(4)
        try:
            from rubric_package.db import hymn_count as _hcount
            _n = _hcount()
        except Exception:
            _n = 0
        self._hymn_cache_lbl = Gtk.Label(label=f"📚 {_n} hymns cached")
        self._hymn_cache_lbl.add_css_class("caption")
        self._hymn_cache_lbl.add_css_class("dim-label")
        self._hymn_cache_lbl.set_hexpand(True); self._hymn_cache_lbl.set_xalign(0)
        cache_bar.append(self._hymn_cache_lbl)
        clear_btn = Gtk.Button(label="Clear")
        clear_btn.add_css_class("flat"); clear_btn.add_css_class("caption")
        clear_btn.connect("clicked", self._on_hymn_cache_clear)
        cache_bar.append(clear_btn)
        box.append(cache_bar)

        scroll = Gtk.ScrolledWindow(); scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC); scroll.set_vexpand(True)
        self._palette_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._palette_inner.set_margin_top(4); self._palette_inner.set_margin_bottom(8)
        self._palette_listboxes: dict[str,Gtk.ListBox] = {}
        self._palette_expanders: list[Gtk.Expander] = []
        self._fill_palette_inner()
        scroll.set_child(self._palette_inner); box.append(scroll)
        return box

    def _on_hymn_cache_clear(self, _btn):
        try:
            from rubric_package.db import hymn_clear, hymn_count as _hcount
            hymn_clear()
            self._hymn_cache_lbl.set_label(f"📚 {_hcount()} hymns cached")
        except Exception:
            pass

    def _on_palette_search_changed(self, entry):
        text = entry.get_text().lower().strip()
        if text:
            for exp in self._palette_expanders:
                exp.set_expanded(True)
        for lb in self._palette_listboxes.values():
            if text:
                lb.set_filter_func(
                    lambda row, t=text: hasattr(row, '_item_name') and t in row._item_name.lower())
            else:
                lb.set_filter_func(None)
            lb.invalidate_filter()

    def _section_for_item(self, name: str) -> str:
        for sname, items in get_palette():
            if name in items:
                return sname
        return ""

    def _fill_palette_inner(self):
        while True:
            c = self._palette_inner.get_first_child()
            if c is None: break
            self._palette_inner.remove(c)
        self._palette_listboxes.clear()
        self._palette_expanders.clear()

        # Recently used section
        if config.recently_used:
            rec_lbl = Gtk.Label(label="Recent")
            rec_lbl.add_css_class("caption"); rec_lbl.add_css_class("dim-label")
            rec_lbl.set_xalign(0)
            rec_lbl.set_margin_start(12); rec_lbl.set_margin_end(12)
            rec_lbl.set_margin_top(8); rec_lbl.set_margin_bottom(2)
            self._palette_inner.append(rec_lbl)
            rec_lb = Gtk.ListBox(); rec_lb.set_selection_mode(Gtk.SelectionMode.SINGLE)
            rec_lb.add_css_class("boxed-list")
            rec_lb.set_margin_start(12); rec_lb.set_margin_end(12); rec_lb.set_margin_bottom(4)
            rec_lb.connect("row-activated", self._on_palette_row_activated)
            for rname in config.recently_used[:6]:
                row = Adw.ActionRow(title=rname); row.set_activatable(True)
                row._item_name = rname; row._section_name = self._section_for_item(rname)
                rec_lb.append(row)
            self._palette_inner.append(rec_lb)
            self._palette_listboxes["__recent__"] = rec_lb
            self._palette_inner.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # Sections with expanders (first expanded, rest collapsed)
        for i, (sname, items) in enumerate(get_palette()):
            exp = Gtk.Expander(label=sname)
            exp.set_margin_start(12); exp.set_margin_end(12)
            exp.set_margin_top(8); exp.set_margin_bottom(2)
            exp.set_expanded(i == 0)
            lb = Gtk.ListBox(); lb.set_selection_mode(Gtk.SelectionMode.SINGLE)
            lb.add_css_class("boxed-list"); lb.set_margin_bottom(4)
            lb.connect("row-activated", self._on_palette_row_activated)
            for iname in items:
                row = Adw.ActionRow(title=iname); row.set_activatable(True)
                row._item_name = iname; row._section_name = sname; lb.append(row)
            exp.set_child(lb)
            self._palette_inner.append(exp)
            self._palette_listboxes[sname] = lb
            self._palette_expanders.append(exp)

    def _refresh_recently_used(self):
        lb = self._palette_listboxes.get("__recent__")
        if lb is None:
            self._fill_palette_inner(); return
        while lb.get_first_child():
            lb.remove(lb.get_first_child())
        for rname in config.recently_used[:6]:
            row = Adw.ActionRow(title=rname); row.set_activatable(True)
            row._item_name = rname; row._section_name = self._section_for_item(rname)
            lb.append(row)

    # ── Order panel ───────────────────────────────────────────────────────────

    def _build_order_panel(self):
        # Outer box holds everything
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # ── Readings card (date-dependent, shown when date is set) ────────────
        self.readings_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.readings_card.set_margin_start(12); self.readings_card.set_margin_end(12)
        self.readings_card.set_margin_top(6); self.readings_card.set_margin_bottom(6)
        self.readings_card.add_css_class("card"); self.readings_card.set_visible(False)

        self._colour_bar = Gtk.DrawingArea()
        self._colour_bar.set_size_request(-1, 8)
        self._colour_bar.set_draw_func(self._draw_colour_bar)
        self.readings_card.append(self._colour_bar)

        # Single row: ● Season  Year  |  First Reading · Psalm · Epistle · Gospel
        rcl_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        rcl_row.set_margin_start(8); rcl_row.set_margin_end(8)
        rcl_row.set_margin_top(5); rcl_row.set_margin_bottom(5)

        # Season info (left side, fixed width so reading buttons get the rest)
        season_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        season_box.set_size_request(160, -1)
        self.season_dot = Gtk.Label(label="●"); self.season_dot.add_css_class("caption"); season_box.append(self.season_dot)
        self.season_label = Gtk.Label(); self.season_label.set_xalign(0)
        self.season_label.add_css_class("caption"); season_box.append(self.season_label)
        self.year_badge = Gtk.Label()  # kept for data, not displayed
        rcl_row.append(season_box)

        # Small vertical separator
        vsep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        vsep.set_margin_start(4); vsep.set_margin_end(4); rcl_row.append(vsep)

        # Reading buttons (right side, equal-width columns)
        self._reading_rows: dict[str, Gtk.Button] = {}
        for i, (key, label) in enumerate([("ot","First Reading"),("psalm","Psalm"),
                                           ("epistle","Epistle"),("gospel","Gospel")]):
            if i > 0:
                sep = Gtk.Label(label="·"); sep.add_css_class("dim-label")
                sep.set_margin_start(2); sep.set_margin_end(2); rcl_row.append(sep)
            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            col.set_hexpand(True)
            lbl = Gtk.Label(label=label); lbl.add_css_class("caption"); lbl.add_css_class("dim-label")
            lbl.set_xalign(0.5); col.append(lbl)
            btn = Gtk.Button(label="—"); btn.add_css_class("flat")
            btn.connect("clicked", lambda _b, k=key: self._on_reading_clicked(k))
            col.append(btn); rcl_row.append(col)
            self._reading_rows[key] = btn
        self.readings_card.append(rcl_row)

        # Observances row — chips for feasts, saints, justice days, ecological seasons
        self._obs_sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self._obs_sep.set_visible(False)
        self.readings_card.append(self._obs_sep)
        self._obs_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self._obs_row.set_margin_start(8); self._obs_row.set_margin_end(8)
        self._obs_row.set_margin_top(3); self._obs_row.set_margin_bottom(4)
        self._obs_row.set_visible(False)
        self._obs_inner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self._obs_inner.set_hexpand(True)
        self._obs_row.append(self._obs_inner)
        self.readings_card.append(self._obs_row)

        # Weekday notice + Sunday stepper (shown when selected date is not Sunday/special)
        self._sunday_stepper = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._sunday_stepper.set_margin_start(8); self._sunday_stepper.set_margin_end(8)
        self._sunday_stepper.set_margin_top(0); self._sunday_stepper.set_margin_bottom(6)
        self._sunday_stepper.set_visible(False)
        self._sunday_stepper.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        sep2 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.readings_card.append(sep2)
        self._sunday_sep = sep2

        step_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        step_box.set_margin_start(8); step_box.set_margin_end(8)
        step_box.set_margin_top(4); step_box.set_margin_bottom(6)
        step_box.set_visible(False)

        prev_btn = Gtk.Button(icon_name="go-previous-symbolic", tooltip_text="Previous Sunday")
        prev_btn.add_css_class("flat"); prev_btn.set_valign(Gtk.Align.CENTER)
        prev_btn.connect("clicked", lambda _: self._step_sunday(-1))
        step_box.append(prev_btn)

        self._sunday_lbl = Gtk.Label()
        self._sunday_lbl.add_css_class("caption"); self._sunday_lbl.add_css_class("dim-label")
        self._sunday_lbl.set_hexpand(True); self._sunday_lbl.set_xalign(0.5)
        step_box.append(self._sunday_lbl)

        next_btn = Gtk.Button(icon_name="go-next-symbolic", tooltip_text="Next Sunday")
        next_btn.add_css_class("flat"); next_btn.set_valign(Gtk.Align.CENTER)
        next_btn.connect("clicked", lambda _: self._step_sunday(1))
        step_box.append(next_btn)

        self.readings_card.append(step_box)
        self._sunday_step_box = step_box
        self._readings_sunday: "date | None" = None  # the Sunday whose readings are shown

        box.append(self.readings_card)
        self._current_readings = {}

        # ── Quick-start banner (hidden until first launch wizard activates it) ─
        box.append(self._build_quickstart_banner())

        # ── Horizontal split: order pane (left) | notes pane (right) ─────────
        hpaned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        hpaned.set_shrink_start_child(False); hpaned.set_shrink_end_child(False)
        hpaned.set_position(260); hpaned.set_vexpand(True)

        # ── Order pane (left) ─────────────────────────────────────────────────
        order_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        self._view_stack = Gtk.Stack(); self._view_stack.set_vexpand(True)

        self._flat_scroll = Gtk.ScrolledWindow()
        self._flat_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._flat_scroll.set_margin_start(12); self._flat_scroll.set_margin_end(12)
        self._flat_scroll.set_margin_top(8); self._flat_scroll.set_margin_bottom(6)
        self.order_listbox = Gtk.ListBox()
        self.order_listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.order_listbox.add_css_class("boxed-list")
        self.order_listbox.connect("row-selected", self._on_flat_row_selected)
        placeholder = Adw.StatusPage(title="No elements yet",
            description="Double-click an element in the palette to add it.",
            icon_name="rubric-symbolic")
        placeholder.set_vexpand(True); self.order_listbox.set_placeholder(placeholder)
        self._flat_scroll.set_child(self.order_listbox)
        self._view_stack.add_named(self._flat_scroll, "list")

        self._notebook = Gtk.Notebook()
        self._notebook.set_show_border(False); self._notebook.set_vexpand(True)
        self._notebook.set_margin_start(8); self._notebook.set_margin_end(8)
        self._notebook.set_margin_top(8); self._notebook.set_margin_bottom(6)
        self._view_stack.add_named(self._notebook, "tabs")

        self._view_stack.set_visible_child_name("tabs" if config.use_tabs else "list")
        order_box.append(self._view_stack)

        # Order pane button bar
        bb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        bb.set_margin_start(8); bb.set_margin_end(8); bb.set_margin_top(4); bb.set_margin_bottom(8)
        add_elem_btn = Gtk.Button(label="Element", tooltip_text="Add custom element (Ctrl+Shift+N)")
        add_elem_btn.add_css_class("flat")
        add_elem_btn.connect("clicked", lambda _: self.add_custom()); bb.append(add_elem_btn)
        add_sec_btn = Gtk.Button(label="Section", tooltip_text="Add section divider (Ctrl+D)")
        add_sec_btn.add_css_class("flat")
        add_sec_btn.connect("clicked", lambda _: self.add_divider()); bb.append(add_sec_btn)
        sp = Gtk.Box(); sp.set_hexpand(True); bb.append(sp)
        for icon, tip, cb in [("go-up-symbolic","Move up (Ctrl+↑)",self.move_up),
                               ("go-down-symbolic","Move down (Ctrl+↓)",self.move_down)]:
            b = Gtk.Button(icon_name=icon, tooltip_text=tip); b.add_css_class("flat")
            b.connect("clicked", lambda _, f=cb: f()); bb.append(b)
        rm = Gtk.Button(icon_name="list-remove-symbolic", tooltip_text="Remove selected (Delete)")
        rm.add_css_class("destructive-action"); rm.connect("clicked", lambda _: self.remove_item()); bb.append(rm)
        order_box.append(bb)
        hpaned.set_start_child(order_box)

        # ── Notes pane (right) ────────────────────────────────────────────────
        notes_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        notes_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # ── Combined single-line item toolbar (revealed when item is selected) ─
        self.item_toolbar_revealer = Gtk.Revealer()
        self.item_toolbar_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self.item_toolbar_revealer.set_transition_duration(150)

        # ── Row 1: Leader name + Bulletin toggle (primary, always-visible) ──
        itb_rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        row1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row1.set_margin_start(12); row1.set_margin_end(12)
        row1.set_margin_top(8); row1.set_margin_bottom(4)

        ldr_lbl = Gtk.Label(label="Leader"); ldr_lbl.add_css_class("dim-label")
        row1.append(ldr_lbl)
        self.leader_entry = Gtk.Entry()
        self.leader_entry.set_placeholder_text("Name or role")
        self.leader_entry.set_hexpand(True)
        self.leader_entry.connect("changed", self._on_leader_changed)
        row1.append(self.leader_entry)

        self.bulletin_toggle = Gtk.ToggleButton(label="Bulletin")
        self.bulletin_toggle.set_tooltip_text("Include in congregational bulletin")
        self.bulletin_toggle.add_css_class("flat")
        self.bulletin_toggle.set_active(True)
        self.bulletin_toggle.connect("toggled", self._on_bulletin_toggled)
        row1.append(self.bulletin_toggle)
        itb_rows.append(row1)

        # ── Row 2: Scripture · Hymn (contextual) · Snippets / Reading ────
        row2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        row2.set_margin_start(12); row2.set_margin_end(12)
        row2.set_margin_top(0); row2.set_margin_bottom(8)

        scr_lbl = Gtk.Label(label="Scripture"); scr_lbl.add_css_class("dim-label")
        scr_lbl.set_margin_end(4); row2.append(scr_lbl)
        self.scripture_entry = Gtk.Entry()
        self.scripture_entry.set_placeholder_text("Ps 23")
        self.scripture_entry.set_width_chars(10)
        self.scripture_entry.connect("activate", lambda _: self._do_scripture_search())
        row2.append(self.scripture_entry)
        ss_fetch = Gtk.Button(icon_name="system-search-symbolic", tooltip_text="Fetch passage (Enter)")
        ss_fetch.add_css_class("flat")
        ss_fetch.connect("clicked", lambda _: self._do_scripture_search())
        row2.append(ss_fetch)

        # Hymn sub-segment — only shown for hymn-type elements
        sep_hymn = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        sep_hymn.set_margin_start(6); sep_hymn.set_margin_end(6); row2.append(sep_hymn)
        hl = Gtk.Label(label="Hymn"); hl.add_css_class("dim-label")
        hl.set_margin_end(4); row2.append(hl)
        self.hymn_entry = Gtk.Entry()
        self.hymn_entry.set_placeholder_text("VU 16")
        self.hymn_entry.set_width_chars(8)
        self.hymn_entry.connect("activate", lambda _: self._do_hymn_lookup())
        row2.append(self.hymn_entry)
        hlb = Gtk.Button(label="↵", tooltip_text="Look up hymn (Enter)")
        hlb.add_css_class("flat")
        hlb.connect("clicked", lambda _: self._do_hymn_lookup()); row2.append(hlb)
        self.hymn_status = Gtk.Label(); self.hymn_status.add_css_class("dim-label")
        self.hymn_status.set_max_width_chars(20); self.hymn_status.set_ellipsize(3)
        self.hymn_status.set_hexpand(True)
        row2.append(self.hymn_status)
        self._hymn_toolbar_widgets = [sep_hymn, hl, self.hymn_entry, hlb, self.hymn_status]

        # Action buttons
        sep_act = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        sep_act.set_margin_start(6); sep_act.set_margin_end(2); row2.append(sep_act)
        snip_btn = Gtk.Button(label="Snippet", tooltip_text="Insert snippet (Ctrl+Shift+I)")
        snip_btn.add_css_class("flat")
        snip_btn.connect("clicked", lambda _: self.open_snippets()); row2.append(snip_btn)
        self._rr_btn = Gtk.Button(label="Reading", tooltip_text="Responsive reading builder (Ctrl+R)")
        self._rr_btn.add_css_class("flat")
        self._rr_btn.connect("clicked", lambda _: self.open_responsive_reading()); row2.append(self._rr_btn)
        itb_rows.append(row2)

        self.item_toolbar_revealer.set_child(itb_rows)
        notes_box.append(self.item_toolbar_revealer)
        self.hymn_revealer = self.item_toolbar_revealer
        self.leader_revealer = self.item_toolbar_revealer

        # Notes header: tab switcher (Leader / Bulletin content)
        notes_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        notes_header.set_margin_start(12); notes_header.set_margin_end(12)
        notes_header.set_margin_top(4); notes_header.set_margin_bottom(2)
        tab_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        self._leader_tab_btn = Gtk.ToggleButton(label="Leader notes")
        self._leader_tab_btn.add_css_class("flat"); self._leader_tab_btn.set_active(True)
        self._bulletin_tab_btn = Gtk.ToggleButton(label="Bulletin text")
        self._bulletin_tab_btn.add_css_class("flat")
        self._bulletin_tab_btn.set_group(self._leader_tab_btn)
        def on_leader_tab(btn):
            if btn.get_active(): self._notes_stack.set_visible_child_name("leader")
        def on_bulletin_tab(btn):
            if btn.get_active(): self._notes_stack.set_visible_child_name("bulletin")
        self._leader_tab_btn.connect("toggled", on_leader_tab)
        self._bulletin_tab_btn.connect("toggled", on_bulletin_tab)
        tab_box.append(self._leader_tab_btn); tab_box.append(self._bulletin_tab_btn)
        notes_header.append(tab_box)
        notes_box.append(notes_header)
        notes_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # Notes stack: Leader tab (leader notes) and Bulletin tab (bulletin_note)
        self._notes_stack = Gtk.Stack(); self._notes_stack.set_vexpand(True)
        self._notes_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)

        ns = Gtk.ScrolledWindow()
        ns.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC); ns.set_vexpand(True)
        ns.set_margin_start(12); ns.set_margin_end(12); ns.set_margin_top(8); ns.set_margin_bottom(8)
        self.notes_view = Gtk.TextView(); self.notes_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.notes_view.add_css_class("card")
        self.notes_view.set_top_margin(8); self.notes_view.set_bottom_margin(8)
        self.notes_view.set_left_margin(10); self.notes_view.set_right_margin(10)
        self.notes_view.get_buffer().connect("changed", self._on_notes_changed)
        ns.set_child(self.notes_view)
        self._notes_stack.add_named(ns, "leader")

        bns = Gtk.ScrolledWindow()
        bns.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC); bns.set_vexpand(True)
        bns.set_margin_start(12); bns.set_margin_end(12); bns.set_margin_top(8); bns.set_margin_bottom(8)
        self.bulletin_notes_view = Gtk.TextView()
        self.bulletin_notes_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.bulletin_notes_view.add_css_class("card")
        self.bulletin_notes_view.set_top_margin(8); self.bulletin_notes_view.set_bottom_margin(8)
        self.bulletin_notes_view.set_left_margin(10); self.bulletin_notes_view.set_right_margin(10)
        self.bulletin_notes_view.get_buffer().connect("changed", self._on_bulletin_notes_changed)
        bns.set_child(self.bulletin_notes_view)
        self._notes_stack.add_named(bns, "bulletin")

        notes_box.append(self._notes_stack)

        hpaned.set_end_child(notes_box)
        box.append(hpaned)

        # Hymn suggestions strip — full width across order + notes panes
        self.sugg_revealer = Gtk.Revealer()
        self.sugg_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_UP)
        self.sugg_revealer.set_transition_duration(200)
        sugg_outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        sugg_outer.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        self._sugg_chips_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self._sugg_chips_box.set_margin_start(10); self._sugg_chips_box.set_margin_end(10)
        self._sugg_chips_box.set_margin_bottom(6); self._sugg_chips_box.set_margin_top(6)
        sugg_scroll = Gtk.ScrolledWindow()
        sugg_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        sugg_scroll.set_min_content_height(40)
        sugg_scroll.set_child(self._sugg_chips_box)
        sugg_outer.append(sugg_scroll)
        self.sugg_revealer.set_child(sugg_outer)
        box.append(self.sugg_revealer)

        return box

    # ── Colour bar ────────────────────────────────────────────────────────────

    def _draw_colour_bar(self, _da, cr, _w, _h):
        r,g,b = self._colour_bar_rgb; cr.set_source_rgb(r,g,b); cr.paint()

    # ── Row factories ─────────────────────────────────────────────────────────

    def _make_item_row(self, si: ServiceItem, global_idx: int) -> Adw.ActionRow:
        # Build a short preview: first 4-5 words of the first line of note
        preview = ""
        if si.note:
            first_line = si.note.strip().split('\n')[0].strip()
            # Strip leading LaTeX commands for display
            if first_line.startswith('\\'):
                first_line = re.sub(r'\\[a-zA-Z]+\*?\{([^}]*)\}', r'\1', first_line)
                first_line = re.sub(r'\\[a-zA-Z]+\*?\s*', '', first_line).strip()
            words = first_line.split()
            preview = ' '.join(words[:5]) + ('…' if len(words) > 5 else '')
        row = Adw.ActionRow(title=si.name, subtitle=preview)
        row.set_subtitle_lines(1); row._entry = si
        colour = _section_colour(si.section)
        dot = Gtk.Label(); dot.set_markup(f'<span color="{colour}">⬤</span>'); dot.set_valign(Gtk.Align.CENTER)
        row.add_prefix(dot)
        handle = Gtk.Label(label="⠿"); handle.add_css_class("dim-label"); handle.set_valign(Gtk.Align.CENTER)
        row.add_suffix(handle)
        self._attach_dnd(row, global_idx); return row

    def _make_divider_row(self, div: SectionDivider, global_idx: int) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow(); row._entry = div
        bx = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bx.set_margin_top(8); bx.set_margin_bottom(8); bx.set_margin_start(10); bx.set_margin_end(10)
        handle = Gtk.Label(label="⠿"); handle.add_css_class("dim-label"); handle.set_valign(Gtk.Align.CENTER); bx.append(handle)
        tl = Gtk.EditableLabel(text=div.title); tl.set_hexpand(True); tl.add_css_class("heading")
        tl.connect("changed", lambda w,d=div: (setattr(d,"title",w.get_text().strip()), self._mark_modified()) if w.get_text().strip() and w.get_text().strip()!=d.title else None)
        bx.append(tl)
        db = Gtk.Button(icon_name="list-remove-symbolic", tooltip_text="Remove divider", valign=Gtk.Align.CENTER)
        db.add_css_class("flat"); db.connect("clicked", lambda _,i=global_idx: self._remove_at(i)); bx.append(db)
        row.set_child(bx); self._attach_dnd(row, global_idx); return row

    def _make_row(self, entry, global_idx):
        return self._make_divider_row(entry, global_idx) if entry.is_divider else self._make_item_row(entry, global_idx)

    def _attach_dnd(self, row, idx):
        drag = Gtk.DragSource(); drag.set_actions(Gdk.DragAction.MOVE)
        def on_prepare(_s, _x, _y, i=idx):
            v = GObject.Value(); v.init(GObject.TYPE_INT); v.set_int(i); return Gdk.ContentProvider.new_for_value(v)
        drag.connect("prepare", on_prepare)
        drag.connect("drag-begin", lambda s,_d: s.set_icon(Gtk.WidgetPaintable.new(row),0,0))
        row.add_controller(drag)
        drop = Gtk.DropTarget.new(GObject.TYPE_INT, Gdk.DragAction.MOVE)
        def on_drop(_t, value, _x, _y, dest=idx):
            if value != dest: self._push_undo(); self._move_entry(value, dest)
            return True
        drop.connect("drop", on_drop)
        drop.connect("enter", lambda _t,_x,_y: (row.add_css_class("drop-target"), Gdk.DragAction.MOVE)[1])
        drop.connect("leave", lambda _t: row.remove_css_class("drop-target"))
        row.add_controller(drop)

    # ── Sections helper ───────────────────────────────────────────────────────

    def _get_sections(self) -> list[tuple]:
        """Return [(divider|None, [ServiceItem, …])] preserving order."""
        secs = []; cur_div = None; cur_items = []
        for e in self.service_entries:
            if e.is_divider:
                if cur_items or cur_div is not None: secs.append((cur_div, cur_items))
                cur_div = e; cur_items = []
            else: cur_items.append(e)
        secs.append((cur_div, cur_items))
        if secs and secs[0] == (None, []): secs.pop(0)
        return secs

    # ── Refresh logic ─────────────────────────────────────────────────────────

    def _clear_flat(self):
        while True:
            r = self.order_listbox.get_row_at_index(0)
            if r is None: break
            self.order_listbox.remove(r)

    def _refresh_flat(self, select_index=-1):
        self._clear_flat()
        for i,e in enumerate(self.service_entries): self.order_listbox.append(self._make_row(e,i))
        if select_index >= 0 and self.service_entries:
            r = self.order_listbox.get_row_at_index(min(select_index, len(self.service_entries)-1))
            if r: self.order_listbox.select_row(r)

    def _make_tab_label(self, div: SectionDivider | None, page_idx_fn) -> Gtk.Widget:
        """Tab label: plain text, right-click for rename/delete."""
        if div is None:
            lbl = Gtk.Label(label="Service")
            lbl.add_css_class("heading")
            return lbl

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        lbl = Gtk.Label(label=div.title)
        lbl.add_css_class("heading")
        box.append(lbl)

        # Right-click gesture for context menu
        gesture = Gtk.GestureClick()
        gesture.set_button(3)  # right button

        def on_right_click(_g, _n, _x, _y, d=div, l=lbl):
            menu = Gio.Menu()
            menu.append("Rename…",  f"win.tab-rename")
            menu.append("Delete section…", f"win.tab-delete")
            popover = Gtk.PopoverMenu.new_from_model(menu)
            popover.set_parent(l)
            # Store which divider is being targeted
            self._tab_ctx_div = d
            self._tab_ctx_lbl = l
            popover.popup()

        gesture.connect("pressed", on_right_click)
        box.add_controller(gesture)
        box.show()
        return box

    def _delete_section(self, div: SectionDivider):
        """Remove the divider and all its items."""
        try: div_idx = self.service_entries.index(div)
        except ValueError: return
        self._push_undo()
        to_remove = [div_idx]
        i = div_idx + 1
        while i < len(self.service_entries):
            if self.service_entries[i].is_divider: break
            to_remove.append(i); i += 1
        for idx in reversed(to_remove): del self.service_entries[idx]
        self._refresh_order_list(); self._mark_modified()

    def _refresh_tabs(self, select_index=-1):
        while self._notebook.get_n_pages() > 0: self._notebook.remove_page(0)
        self._tab_listboxes.clear()
        secs = self._get_sections()
        if not secs: return
        for div, items in secs:
            tab_title = div.title if div else "Service"
            scroll = Gtk.ScrolledWindow(); scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            scroll.set_vexpand(True)
            lb = Gtk.ListBox(); lb.set_selection_mode(Gtk.SelectionMode.SINGLE); lb.add_css_class("boxed-list")
            lb.set_margin_start(16); lb.set_margin_end(16); lb.set_margin_top(12); lb.set_margin_bottom(12)
            lb.connect("row-selected", lambda _lb,row,d=div,i=items: self._on_tab_row_selected(row))
            ph = Adw.StatusPage(title="Empty section", description='Add elements from the palette or drag them here')
            ph.set_vexpand(True); lb.set_placeholder(ph)
            for item in items:
                g_idx = self.service_entries.index(item)
                lb.append(self._make_item_row(item, g_idx))
            scroll.set_child(lb); self._tab_listboxes.append((div, lb))
            # Cross-tab drop target on the scroll widget
            tab_drop = Gtk.DropTarget.new(GObject.TYPE_INT, Gdk.DragAction.MOVE)
            def on_cross_drop(_t, value, _x, _y, sec_div=div, sec_items=list(items)):
                if not (0 <= value < len(self.service_entries)): return False
                dragged = self.service_entries[value]; self._push_undo()
                self.service_entries.pop(value)
                if sec_items:
                    try: last_idx = next(i for i,e in enumerate(self.service_entries) if e is sec_items[-1])
                    except StopIteration: last_idx = -1
                    ins = last_idx+1 if last_idx >= 0 else len(self.service_entries)
                elif sec_div:
                    try: div_idx = next(i for i,e in enumerate(self.service_entries) if e is sec_div)
                    except StopIteration: div_idx = 0
                    ins = div_idx+1
                else: ins = 0
                self.service_entries.insert(ins, dragged); self._refresh_order_list(); self._mark_modified(); return True
            tab_drop.connect("drop", on_cross_drop); scroll.add_controller(tab_drop)
            # Editable tab label with delete button
            page_num_ref = [0]  # will be updated after append_page
            tab_lbl = self._make_tab_label(div, lambda: page_num_ref[0])
            page_num = self._notebook.append_page(scroll, tab_lbl)
            page_num_ref[0] = page_num
        # Select appropriate tab and row
        if select_index >= 0 and self.service_entries:
            sidx = min(select_index, len(self.service_entries)-1)
            entry = self.service_entries[sidx]
            if isinstance(entry, ServiceItem):
                for page_num, (div, lb) in enumerate(self._tab_listboxes):
                    i = 0
                    while True:
                        r = lb.get_row_at_index(i)
                        if r is None: break
                        if hasattr(r, "_entry") and r._entry is entry:
                            self._notebook.set_current_page(page_num)
                            lb.select_row(r)
                            break
                        i += 1

    def _clear_order_list(self):
        self._clear_flat()
        while self._notebook.get_n_pages() > 0: self._notebook.remove_page(0)
        self._tab_listboxes.clear()

    def _refresh_order_list(self, select_index=-1):
        if config.use_tabs:
            self._view_stack.set_visible_child_name("tabs"); self._refresh_tabs(select_index)
        else:
            self._view_stack.set_visible_child_name("list"); self._refresh_flat(select_index)

    def _apply_tab_mode(self):
        """Called after preferences close to apply tab mode change."""
        self._refresh_order_list(self._selected_global_idx)

    # ── Selection ─────────────────────────────────────────────────────────────

    def _selected_index(self) -> int:
        if config.use_tabs: return self._selected_global_idx
        r = self.order_listbox.get_selected_row(); return r.get_index() if r else -1

    def _on_flat_row_selected(self, _lb, row):
        self._handle_selection(row)

    def _on_tab_row_selected(self, row):
        self._handle_selection(row)

    def _handle_selection(self, row):
        self._updating_note = True
        buf = self.notes_view.get_buffer()
        buf_bul = self.bulletin_notes_view.get_buffer()
        if row and hasattr(row,"_entry") and isinstance(row._entry, ServiceItem):
            si = row._entry
            try: self._selected_global_idx = self.service_entries.index(si)
            except ValueError: self._selected_global_idx = -1
            buf.set_text(si.note, -1)
            buf_bul.set_text(si.bulletin_note, -1)
            # Always land on Leader tab so the user sees the leader notes
            self._leader_tab_btn.set_active(True)
            # Show the combined toolbar
            self.item_toolbar_revealer.set_reveal_child(True)
            self.leader_entry.set_text(si.leader)
            # Bulletin toggle — set state without triggering handler
            self.bulletin_toggle.set_active(si.show_in_bulletin)
            # Show/hide hymn segment based on element type
            is_hymn = _HYMN_OK and _is_hymn_element(si.name)
            for w in self._hymn_toolbar_widgets: w.set_visible(is_hymn)
            if is_hymn: self.hymn_status.set_label(""); self.hymn_entry.set_text("")
        else:
            self._selected_global_idx = -1
            buf.set_text("", -1)
            buf_bul.set_text("", -1)
            self.item_toolbar_revealer.set_reveal_child(False)
            self.leader_entry.set_text("")
        self._updating_note = False

    # ── Palette actions ───────────────────────────────────────────────────────

    def _on_palette_row_activated(self, _lb, row):
        self._push_undo(); self._add_entry(ServiceItem(row._item_name, row._section_name))
        name = row._item_name
        was_empty = not config.recently_used
        if name in config.recently_used:
            config.recently_used.remove(name)
        config.recently_used.insert(0, name)
        config.recently_used = config.recently_used[:6]
        config.save()
        if was_empty:
            self._fill_palette_inner()
        else:
            self._refresh_recently_used()
    def _add_selected_palette_item(self):
        for lb in self._palette_listboxes.values():
            r = lb.get_selected_row()
            if r: self._push_undo(); self._add_entry(ServiceItem(r._item_name, r._section_name)); return

    # ── Entry management ──────────────────────────────────────────────────────

    def _add_entry(self, entry):
        idx = self._selected_index()
        if idx >= 0:
            ins = idx+1; self.service_entries.insert(ins, entry); self._refresh_order_list(select_index=ins)
        else:
            self.service_entries.append(entry)
            if config.use_tabs: self._refresh_order_list(len(self.service_entries)-1)
            else:
                row = self._make_row(entry, len(self.service_entries)-1)
                self.order_listbox.append(row); self.order_listbox.select_row(row)
        self._mark_modified()

    def _move_entry(self, from_idx, to_idx):
        e = self.service_entries.pop(from_idx)
        ins = max(0, min(to_idx if to_idx < from_idx else to_idx-1, len(self.service_entries)))
        self.service_entries.insert(ins, e); self._refresh_order_list(ins); self._mark_modified()

    def _remove_at(self, idx):
        self._push_undo()
        if 0 <= idx < len(self.service_entries): del self.service_entries[idx]; self._refresh_order_list(idx); self._mark_modified()

    # ── Order actions ─────────────────────────────────────────────────────────

    def remove_item(self):
        idx = self._selected_index()
        if idx < 0: return
        self._push_undo(); del self.service_entries[idx]; self._refresh_order_list(idx); self._mark_modified()

    def move_up(self):
        idx = self._selected_index()
        if idx <= 0: return
        self._push_undo(); self.service_entries[idx],self.service_entries[idx-1] = self.service_entries[idx-1],self.service_entries[idx]
        self._refresh_order_list(idx-1); self._mark_modified()

    def move_down(self):
        idx = self._selected_index()
        if idx < 0 or idx >= len(self.service_entries)-1: return
        self._push_undo(); self.service_entries[idx],self.service_entries[idx+1] = self.service_entries[idx+1],self.service_entries[idx]
        self._refresh_order_list(idx+1); self._mark_modified()

    def add_divider(self): self._push_undo(); self._add_entry(SectionDivider("New section"))

    def add_custom(self):
        dlg = Adw.MessageDialog(transient_for=self, heading="Add custom element")
        bx = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8); bx.set_margin_top(6)
        nr = Adw.EntryRow(title="Element name"); bx.append(nr)
        sr = Adw.ComboRow(title="Palette section (for colour)")
        m = Gtk.StringList()
        for s,_ in get_palette(): m.append(s)
        sr.set_model(m); bx.append(sr); dlg.set_extra_child(bx)
        dlg.add_response("cancel","Cancel"); dlg.add_response("add","Add")
        dlg.set_response_appearance("add", Adw.ResponseAppearance.SUGGESTED); dlg.set_default_response("add")
        def on_resp(d,r):
            if r=="add":
                name = nr.get_text().strip(); pal = get_palette()
                section = pal[sr.get_selected()][0] if pal else ""
                if name: self._push_undo(); self._add_entry(ServiceItem(name, section))
        dlg.connect("response", on_resp); dlg.present()

    def duplicate_service(self):
        entries = [_entry_from_dict(e.to_dict()) for e in self.service_entries]
        title = self.service_title_entry.get_text()
        def do_dup():
            self._reset_state(); self.service_title_entry.set_text(f"{title} — Copy" if title else "Copy")
            self.service_entries = entries; self._refresh_order_list(); self.modified=True; self._update_title()
        self._confirm_discard(do_dup)

    # ── Undo ──────────────────────────────────────────────────────────────────

    def _push_undo(self):
        self._undo_stack.append([e.to_dict() for e in self.service_entries])
        if len(self._undo_stack) > MAX_UNDO: self._undo_stack.pop(0)
        self.undo_btn.set_sensitive(True)
        self._redo_stack.clear(); self.redo_btn.set_sensitive(False)

    def undo(self):
        if not self._undo_stack: return
        self._redo_stack.append([e.to_dict() for e in self.service_entries])
        self.redo_btn.set_sensitive(True)
        self.service_entries = [_entry_from_dict(d) for d in self._undo_stack.pop()]
        self._refresh_order_list(); self.undo_btn.set_sensitive(bool(self._undo_stack)); self._mark_modified()

    def redo(self):
        if not self._redo_stack: return
        self._undo_stack.append([e.to_dict() for e in self.service_entries])
        self.undo_btn.set_sensitive(True)
        self.service_entries = [_entry_from_dict(d) for d in self._redo_stack.pop()]
        self._refresh_order_list(); self.redo_btn.set_sensitive(bool(self._redo_stack)); self._mark_modified()

    # ── Hymn lookup ───────────────────────────────────────────────────────────

    def _do_hymn_lookup(self):
        if not _HYMN_OK: self.hymn_status.set_label("hymn_lookup.py not found"); return
        text = self.hymn_entry.get_text().strip()
        if not text: return
        result = parse_hymn_ref(text)
        if not result: self.hymn_status.set_label("Format: VU 16  MV 120  LUS 5"); return
        prefix, number = result; self.hymn_status.set_label("Looking up…")
        def on_result(title, error):
            if error: self.hymn_status.set_label(error); return
            # Short format: "VU 16 — O Come, O Come, Emmanuel"
            short_ref = f"{prefix.upper()} {number}"
            hymn_line = f"{short_ref} — {title}"
            self.hymn_status.set_label(hymn_line)
            idx = self._selected_index()
            if not (0 <= idx < len(self.service_entries)): return
            entry = self.service_entries[idx]
            if not isinstance(entry, ServiceItem): return
            entry.note = (hymn_line+"\n"+entry.note if entry.note else hymn_line)
            self._updating_note = True; self.notes_view.get_buffer().set_text(entry.note,-1); self._updating_note = False
            row = self._find_row_for_index(idx)
            if isinstance(row, Adw.ActionRow): row.set_subtitle(self._note_preview(entry.note))
            self._mark_modified()
        lookup_hymn(prefix, number, on_result)

    # ── Bible viewer ──────────────────────────────────────────────────────────

    def _on_reading_clicked(self, key):
        ref = self._current_readings.get(key,"")
        if not ref or ref=="—": return
        BibleViewer(ref, self._on_bible_insert, translation=config.bible_translation, esv_key=config.bible_api_key_esv, transient_for=self).present()

    def _on_bible_insert(self, text):
        idx = self._selected_index()
        if not (0 <= idx < len(self.service_entries)): return
        entry = self.service_entries[idx]
        if not isinstance(entry, ServiceItem): return
        sep = "\n\n" if entry.note else ""
        entry.note = entry.note + sep + text
        self._updating_note = True
        self.notes_view.get_buffer().set_text(entry.note, -1)
        self._updating_note = False
        self._mark_modified()

    # ── Notes ─────────────────────────────────────────────────────────────────

    def _find_row_for_index(self, idx: int):
        """Return the UI row widget for a given entry index, in either flat or tab view."""
        if not config.use_tabs:
            return self.order_listbox.get_row_at_index(idx)
        entry = self.service_entries[idx] if 0 <= idx < len(self.service_entries) else None
        if entry is None:
            return None
        for _div, lb in self._tab_listboxes:
            i = 0
            while True:
                r = lb.get_row_at_index(i)
                if r is None: break
                if hasattr(r, "_entry") and r._entry is entry:
                    return r
                i += 1
        return None

    def _note_preview(self, note: str) -> str:
        if not note: return ""
        first_line = note.strip().split('\n')[0].strip()
        if first_line.startswith('\\'):
            first_line = re.sub(r'\\[a-zA-Z]+\*?\{([^}]*)\}', r'\1', first_line)
            first_line = re.sub(r'\\[a-zA-Z]+\*?\s*', '', first_line).strip()
        words = first_line.split()
        return ' '.join(words[:5]) + ('…' if len(words) > 5 else '')

    def _on_notes_changed(self, buf):
        if self._updating_note: return
        idx = self._selected_index()
        if not (0 <= idx < len(self.service_entries)): return
        entry = self.service_entries[idx]
        if not isinstance(entry, ServiceItem): return
        s, e = buf.get_bounds(); entry.note = buf.get_text(s, e, False)
        row = self._find_row_for_index(idx)
        if isinstance(row, Adw.ActionRow):
            row.set_subtitle(self._note_preview(entry.note))
        self._mark_modified()

    def _on_bulletin_notes_changed(self, buf):
        if self._updating_note: return
        idx = self._selected_index()
        if not (0 <= idx < len(self.service_entries)): return
        entry = self.service_entries[idx]
        if not isinstance(entry, ServiceItem): return
        s, e = buf.get_bounds()
        entry.bulletin_note = buf.get_text(s, e, False)
        self._mark_modified()

    # ── Calendar / readings ───────────────────────────────────────────────────

    def _update_lect_label(self):
        """Update the header lectionary year/season label based on today's date."""
        from datetime import date as pydate
        try:
            info = get_liturgical_info(pydate.today())
            year  = info["year"]    # 'A', 'B', or 'C'
            season = info["season"]
            colour = info["colour_hex"]
            # Compact: coloured dot + "Year A · Advent"
            self._lect_label.set_markup(
                f'<span color="{colour}">●</span> '
                f'<span>Year {year} · {season}</span>'
            )
            self._lect_label.set_tooltip_text(
                f"Today: {info['week']} — RCL Year {year}"
            )
        except Exception:
            self._lect_label.set_text("")
        return True  # keep the daily timer running

    def _on_calendar_day_selected(self, cal):
        gd = cal.get_date()
        from datetime import date as pydate
        d = pydate(gd.get_year(), gd.get_month(), gd.get_day_of_month())
        self.selected_date = d; self.date_button.set_label(d.strftime("%-d %B %Y"))
        self._update_readings(d); self._mark_modified()

    def _on_clear_date(self, _):
        self.selected_date = None; self.date_button.set_label("No date selected")
        self.readings_card.set_visible(False); self._mark_modified()

    def _update_readings(self, d, override_sunday=None):
        """
        Show RCL readings for date d.
        For weekdays, default to the *next* Sunday's readings with a stepper.
        override_sunday: force a specific Sunday date (used by stepper buttons).
        """
        from datetime import date as pydate, timedelta

        # Determine whether d is a liturgically significant day itself
        weekday = d.weekday()  # 0=Mon … 6=Sun
        is_sunday = weekday == 6

        # Special fixed weekday feasts we can look up directly
        _SPECIAL = {"AshWednesday", "HolyThursday", "GoodFriday", "Ascension"}
        info_direct = get_liturgical_info(d)
        is_special = any(k in info_direct.get("week", "") for k in
                         ["Ash Wednesday", "Maundy Thursday", "Good Friday", "Ascension"])

        if is_sunday or is_special or override_sunday is not None:
            reading_date = override_sunday if override_sunday else d
            info = get_liturgical_info(reading_date)
            self._readings_sunday = reading_date
            show_stepper = bool(override_sunday) or (not is_sunday and is_special is False)
        else:
            # Weekday: jump to next Sunday by default
            days_until_sunday = (6 - weekday) % 7 or 7
            next_sunday = d + timedelta(days=days_until_sunday)
            self._readings_sunday = next_sunday
            info = get_liturgical_info(next_sunday)
            show_stepper = True

        self._current_readings = {k: info[k] for k in ("ot","psalm","epistle","gospel")}
        self.readings_card.set_visible(True)
        self.season_label.set_label(info["week"]); self.year_badge.set_label(f"Year {info['year']}")
        self.season_dot.set_markup(f'<span color="{info["colour_hex"]}">●</span>')
        self._colour_bar_rgb = _hex_to_rgb(info["colour_hex"]); self._colour_bar.queue_draw()

        # Stepper
        self._sunday_step_box.set_visible(show_stepper)
        if show_stepper and self._readings_sunday:
            self._sunday_lbl.set_label(
                f"Readings for {self._readings_sunday.strftime('%-d %b %Y (Sunday)')}"
            )

        for key, btn in self._reading_rows.items():
            ref = info[key]; btn.set_label(ref if ref and ref != "—" else "—")
            btn.set_sensitive(bool(ref and ref != "—"))
            btn.set_tooltip_text(f"Read {ref} (WEB)" if ref and ref != "—" else "")

        # Update hymn suggestions for this week
        self._update_hymn_suggestions(info["week"], info["season"])

        # Update observances row
        self._refresh_observances_row(self._readings_sunday or d)

    def _refresh_observances_row(self, d) -> None:
        """Rebuild the observances row for the given date."""
        try:
            from observances import get_observances, TYPES
        except ImportError:
            return
        obs_list = get_observances(d)
        while True:
            ch = self._obs_inner.get_first_child()
            if ch is None: break
            self._obs_inner.remove(ch)
        if not obs_list:
            self._obs_sep.set_visible(False)
            self._obs_row.set_visible(False)
            return
        self._obs_sep.set_visible(True)
        self._obs_row.set_visible(True)
        parts = []
        for obs in obs_list:
            ti = TYPES.get(obs.get("type", ""), {})
            colour = ti.get("colour", "#6B7280")
            tlabel = ti.get("label", "")
            name = GLib.markup_escape_text(obs["name"])
            if obs.get("proximity"):
                name += f" <span alpha='70%'>({GLib.markup_escape_text(obs['proximity'])})</span>"
            if tlabel:
                parts.append(f'<span color="{colour}"><b>{GLib.markup_escape_text(tlabel)}</b></span> {name}')
            else:
                parts.append(name)
        lbl = Gtk.Label()
        lbl.set_markup("   ·   ".join(parts))
        lbl.add_css_class("caption")
        lbl.set_wrap(True)
        lbl.set_xalign(0)
        self._obs_inner.append(lbl)

    def _step_sunday(self, direction: int):
        """Move the readings display to the prev (-1) or next (+1) Sunday."""
        from datetime import timedelta
        if self._readings_sunday is None: return
        new_sun = self._readings_sunday + timedelta(weeks=direction)
        self._update_readings(self.selected_date, override_sunday=new_sun)

    # ── State ─────────────────────────────────────────────────────────────────

    # ── Live bulletin preview ─────────────────────────────────────────────────

    def _build_preview_panel(self) -> Gtk.Box:
        """Return the bulletin preview side-panel (WebKit or fallback status page)."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.set_size_request(320, -1)

        # Header
        hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        hdr.set_margin_start(10); hdr.set_margin_end(6)
        hdr.set_margin_top(6); hdr.set_margin_bottom(6)
        lbl = Gtk.Label(label="Bulletin Preview")
        lbl.add_css_class("heading"); lbl.set_hexpand(True); lbl.set_xalign(0)
        hdr.append(lbl)

        # Compiling indicator (hidden until xelatex is running)
        self._preview_spinner = Gtk.Spinner()
        self._preview_spinner.set_visible(False)
        hdr.append(self._preview_spinner)
        self._preview_compiling_lbl = Gtk.Label(label="Compiling…")
        self._preview_compiling_lbl.add_css_class("dim-label")
        self._preview_compiling_lbl.add_css_class("caption")
        self._preview_compiling_lbl.set_visible(False)
        hdr.append(self._preview_compiling_lbl)

        # Export options gear (print/digital mode + quick church name)
        gear_btn = Gtk.MenuButton(icon_name="emblem-system-symbolic",
                                  tooltip_text="Preview options")
        gear_btn.add_css_class("flat")
        gear_btn.set_popover(self._build_preview_gear_popover())
        hdr.append(gear_btn)

        # Popout into separate window
        popout_btn = Gtk.Button(icon_name="view-restore-symbolic",
                                tooltip_text="Open in separate window")
        popout_btn.add_css_class("flat")
        popout_btn.connect("clicked", lambda _: self._popout_preview())
        hdr.append(popout_btn)

        box.append(hdr)
        box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        if _WEBKIT_OK:
            self._preview_webview = _WebKit.WebView()
            self._preview_webview.set_vexpand(True)
            self._preview_webview.set_hexpand(True)
            box.append(self._preview_webview)
        else:
            self._preview_webview = None
            status = Adw.StatusPage(
                title="WebKit not available",
                description="Install python3-webkit2gtk (or typelib-1_0-WebKit2-4_1) "
                            "to enable live bulletin preview.",
                icon_name="web-browser-symbolic",
            )
            status.set_vexpand(True)
            box.append(status)

        return box

    def _build_preview_gear_popover(self) -> Gtk.Popover:
        """Small popover for print/digital mode toggle and quick church name edit."""
        pop = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_margin_top(12); box.set_margin_bottom(12)
        box.set_margin_start(12); box.set_margin_end(12)

        fmt_lbl = Gtk.Label(label="Preview format")
        fmt_lbl.add_css_class("caption"); fmt_lbl.add_css_class("dim-label")
        fmt_lbl.set_xalign(0)
        box.append(fmt_lbl)

        toggle_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        toggle_box.add_css_class("linked")
        print_btn  = Gtk.ToggleButton(label="Print")
        digital_btn = Gtk.ToggleButton(label="Digital")
        digital_btn.set_group(print_btn)
        if config.bulletin.get("print_mode", "booklet") == "digital":
            digital_btn.set_active(True)
        else:
            print_btn.set_active(True)

        def on_mode(btn, is_digital):
            if btn.get_active():
                config.bulletin["print_mode"] = "digital" if is_digital else "booklet"
                config.save()
                self._schedule_preview_update()

        print_btn.connect("toggled",  lambda b: on_mode(b, False))
        digital_btn.connect("toggled", lambda b: on_mode(b, True))
        toggle_box.append(print_btn); toggle_box.append(digital_btn)
        box.append(toggle_box)

        cn_lbl = Gtk.Label(label="Church name")
        cn_lbl.add_css_class("caption"); cn_lbl.add_css_class("dim-label")
        cn_lbl.set_xalign(0); cn_lbl.set_margin_top(4)
        box.append(cn_lbl)

        cn_entry = Gtk.Entry()
        cn_entry.set_text(config.bulletin.get("church_name", ""))
        cn_entry.set_placeholder_text("Church name")

        def on_cn_changed(e):
            config.bulletin["church_name"] = e.get_text()
            self._schedule_preview_update()

        cn_entry.connect("changed", on_cn_changed)
        box.append(cn_entry)

        full_prefs_btn = Gtk.Button(label="Bulletin preferences…")
        full_prefs_btn.add_css_class("flat"); full_prefs_btn.set_margin_top(4)
        full_prefs_btn.connect("clicked", lambda _: (pop.popdown(),
                                                     self._open_prefs_page("Bulletin")))
        box.append(full_prefs_btn)

        pop.set_child(box)
        return pop

    def _open_prefs_page(self, page_title: str):
        """Open Preferences and navigate to the named page."""
        a = self.lookup_action("preferences")
        if a:
            a.activate(None)

    def _toggle_preview_panel(self, btn):
        visible = btn.get_active()
        self._preview_panel.set_visible(visible)
        self._preview_visible = visible
        if visible:
            # Position the pane so preview gets ~40% of content width
            total = self._preview_paned.get_allocated_width()
            pos = max(400, int(total * 0.6)) if total > 200 else 600
            self._preview_paned.set_position(pos)
            self._do_preview_update()
        else:
            if getattr(self, "_preview_pending_id", None) is not None:
                GLib.source_remove(self._preview_pending_id)
                self._preview_pending_id = None

    def _schedule_preview_update(self):
        if not getattr(self, "_preview_visible", False):
            return
        existing = getattr(self, "_preview_pending_id", None)
        if existing is not None:
            GLib.source_remove(existing)
        self._preview_pending_id = GLib.timeout_add(700, self._do_preview_update)

    def _do_preview_update(self):
        self._preview_pending_id = None
        if not getattr(self, "_preview_visible", False):
            return False
        if self._preview_webview is None:
            return False
        if getattr(self, "_preview_compiling", False):
            return False  # Don't queue another compile while one is running
        if not config.simple_mode and self._find_xelatex():
            self._compile_preview_pdf()
        else:
            try:
                html = self._build_bulletin_html()
                self._preview_webview.load_html(html, None)
            except Exception:
                pass
        return False

    def _find_xelatex(self) -> str | None:
        """Return path to xelatex, or None."""
        x = shutil.which("xelatex")
        if x:
            return x
        for candidate in [
            Path.home() / "texlive/bin/x86_64-linux/xelatex",
            Path("/usr/local/texlive/2024/bin/x86_64-linux/xelatex"),
            Path("/usr/local/texlive/2023/bin/x86_64-linux/xelatex"),
        ]:
            if candidate.exists():
                return str(candidate)
        return None

    def _compile_preview_pdf(self):
        """Build bulletin TeX, compile in background, load the PDF in the preview."""
        import tempfile
        xelatex = self._find_xelatex()
        if not xelatex:
            return

        try:
            digital = config.bulletin.get("print_mode", "booklet") == "digital"
            lines = self._build_bulletin_latex(digital=digital)
            tex_src = "\n".join(lines)
        except Exception:
            return

        if not getattr(self, "_preview_pdf_dir", None):
            self._preview_pdf_dir = tempfile.mkdtemp(prefix="rubric-preview-")

        tex_path = Path(self._preview_pdf_dir) / "preview.tex"
        try:
            tex_path.write_text(tex_src, encoding="utf-8")
        except Exception:
            return

        self._preview_compiling = True
        self._preview_spinner.set_visible(True)
        self._preview_spinner.start()
        self._preview_compiling_lbl.set_visible(True)

        def run():
            try:
                subprocess.run(
                    [xelatex, "-interaction=nonstopmode", "-halt-on-error",
                     "preview.tex"],
                    cwd=self._preview_pdf_dir,
                    capture_output=True, text=True, timeout=60,
                    encoding="utf-8", errors="replace",
                )
                pdf = Path(self._preview_pdf_dir) / "preview.pdf"
                if pdf.exists():
                    GLib.idle_add(self._load_preview_pdf, str(pdf))
                else:
                    GLib.idle_add(self._preview_compile_done)
            except Exception:
                GLib.idle_add(self._preview_compile_done)

        threading.Thread(target=run, daemon=True).start()

    def _load_preview_pdf(self, pdf_path: str):
        self._preview_pdf_path = pdf_path
        self._preview_compile_done()
        if self._preview_webview:
            self._preview_webview.load_uri(f"file://{pdf_path}")
        return False

    def _preview_compile_done(self):
        self._preview_compiling = False
        self._preview_spinner.stop()
        self._preview_spinner.set_visible(False)
        self._preview_compiling_lbl.set_visible(False)
        return False

    def _popout_preview(self):
        """Open the current bulletin preview in a separate window."""
        if not _WEBKIT_OK:
            return
        win = Adw.Window(title="Bulletin Preview", transient_for=self)
        win.set_default_size(720, 960)
        wv = _WebKit.WebView()
        wv.set_vexpand(True); wv.set_hexpand(True)
        pdf_path = getattr(self, "_preview_pdf_path", None)
        if pdf_path and Path(pdf_path).exists():
            wv.load_uri(f"file://{pdf_path}")
        else:
            try:
                wv.load_html(self._build_bulletin_html(), None)
            except Exception:
                pass
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.set_vexpand(True); box.append(wv)
        win.set_content(box)
        self._preview_popout_win = win  # prevent GC
        win.present()

    def _mark_modified(self): self.modified=True; self._update_title(); self._schedule_preview_update()

    def _update_title(self):
        svc = self.service_title_entry.get_text() or "New service"
        if self.selected_date:
            subtitle = self.selected_date.strftime("%-d %B %Y") + (" •" if self.modified else "")
        else:
            subtitle = svc + (" •" if self.modified else "")
        self.title_widget.set_title(
            Path(self.current_file).stem if self.current_file else svc)
        self.title_widget.set_subtitle(subtitle)

    def _service_data(self):
        d = {"title": self.service_title_entry.get_text(),
             "date":  self.selected_date.isoformat() if self.selected_date else None,
             "items": [e.to_dict() for e in self.service_entries]}
        if self.tex_file:
            d["tex_file"] = self.tex_file
        return d

    def _confirm_discard(self, proceed):
        if not self.modified: proceed(); return
        dlg = Adw.MessageDialog(transient_for=self, heading="Unsaved changes", body="Discard unsaved changes?")
        dlg.add_response("cancel","Cancel"); dlg.add_response("discard","Discard")
        dlg.set_response_appearance("discard", Adw.ResponseAppearance.DESTRUCTIVE)
        dlg.connect("response", lambda d,r: proceed() if r=="discard" else None); dlg.present()

    # ── Autosave ──────────────────────────────────────────────────────────────

    def _check_welcome(self) -> bool:
        if not config.first_launch_completed:
            self._show_first_launch_wizard()
        elif config.last_seen_version != APP_VERSION:
            self._show_welcome(is_new_version=bool(config.last_seen_version))
        return False

    # ── Quick-start banner ────────────────────────────────────────────────────

    _QUICKSTART_TIPS = [
        "Double-click any element in the left palette to add it to your service order.",
        "Click the window title to set your service date — RCL readings load automatically.",
        "Select an element to reveal the item toolbar: leader name, scripture, hymn lookup.",
        "Type in the Notes area to add content for each element. Leader notes go to the PDF; "
            "Bulletin text appears in the congregational bulletin.",
        "Save (Ctrl+S) often. Use Menu → Save as template to reuse this order every week.",
        "Ctrl+E exports to LaTeX; Ctrl+Shift+P compiles a PDF. "
            "Open Preferences (Ctrl+,) to customise your palette and bulletin.",
    ]

    def _build_quickstart_banner(self) -> Gtk.Revealer:
        self._quickstart_tip_idx = 0
        self._quickstart_revealer = Gtk.Revealer()
        self._quickstart_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self._quickstart_revealer.set_transition_duration(200)
        self._quickstart_revealer.set_reveal_child(False)

        banner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        banner.set_margin_start(12); banner.set_margin_end(12)
        banner.set_margin_top(6); banner.set_margin_bottom(6)
        banner.add_css_class("card")

        hint_icon = Gtk.Image(icon_name="dialog-information-symbolic")
        hint_icon.add_css_class("dim-label"); banner.append(hint_icon)

        self._quickstart_lbl = Gtk.Label(label=self._QUICKSTART_TIPS[0])
        self._quickstart_lbl.add_css_class("caption")
        self._quickstart_lbl.set_wrap(True); self._quickstart_lbl.set_xalign(0)
        self._quickstart_lbl.set_hexpand(True)
        banner.append(self._quickstart_lbl)

        self._quickstart_next_btn = Gtk.Button(label="Next →")
        self._quickstart_next_btn.add_css_class("flat")
        self._quickstart_next_btn.add_css_class("caption")
        self._quickstart_next_btn.connect("clicked", self._on_quickstart_next)
        banner.append(self._quickstart_next_btn)

        dismiss_btn = Gtk.Button(icon_name="window-close-symbolic",
                                 tooltip_text="Dismiss tips")
        dismiss_btn.add_css_class("flat")
        dismiss_btn.connect("clicked", lambda _: self._dismiss_quickstart())
        banner.append(dismiss_btn)

        self._quickstart_revealer.set_child(banner)
        return self._quickstart_revealer

    def _show_quickstart_banner(self):
        if not config.quickstart_dismissed:
            self._quickstart_tip_idx = 0
            self._quickstart_lbl.set_label(self._QUICKSTART_TIPS[0])
            self._quickstart_next_btn.set_label("Next →")
            self._quickstart_revealer.set_reveal_child(True)

    def _on_quickstart_next(self, _btn):
        self._quickstart_tip_idx += 1
        if self._quickstart_tip_idx >= len(self._QUICKSTART_TIPS):
            self._dismiss_quickstart(); return
        self._quickstart_lbl.set_label(self._QUICKSTART_TIPS[self._quickstart_tip_idx])
        if self._quickstart_tip_idx == len(self._QUICKSTART_TIPS) - 1:
            self._quickstart_next_btn.set_label("Done ✓")

    def _dismiss_quickstart(self):
        self._quickstart_revealer.set_reveal_child(False)
        config.quickstart_dismissed = True
        config.save()

    # ── First-launch wizard ───────────────────────────────────────────────────

    def _show_first_launch_wizard(self):
        from datetime import date as pydate
        today = pydate.today()
        try:
            info = get_liturgical_info(today)
            # If today is a weekday, step to next Sunday for the subtitle
            from datetime import timedelta
            if today.weekday() != 6:
                days = (6 - today.weekday()) % 7 or 7
                info = get_liturgical_info(today + timedelta(days=days))
            week_label = info.get("week", "this Sunday's readings")
        except Exception:
            info = {}; week_label = "this Sunday's readings"

        win = Adw.Window(transient_for=self, modal=True)
        win.set_title("Welcome to Rubric")
        win.set_default_size(500, 0)
        win.set_resizable(False)
        tv = Adw.ToolbarView()
        hdr = Adw.HeaderBar(); hdr.set_show_end_title_buttons(False)
        win.set_content(tv); tv.add_top_bar(hdr)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.set_margin_start(24); outer.set_margin_end(24)
        outer.set_margin_top(20); outer.set_margin_bottom(24)

        # Hero
        hero_icon = Gtk.Image(icon_name="rubric-symbolic")
        hero_icon.set_pixel_size(48); hero_icon.set_margin_bottom(10)
        outer.append(hero_icon)
        title_lbl = Gtk.Label(label="Welcome to Rubric")
        title_lbl.add_css_class("title-1"); title_lbl.set_margin_bottom(4)
        outer.append(title_lbl)
        sub_lbl = Gtk.Label(label="How would you like to start today's service?")
        sub_lbl.add_css_class("dim-label"); sub_lbl.set_margin_bottom(20)
        outer.append(sub_lbl)

        # Choice cards
        lb = Gtk.ListBox()
        lb.set_selection_mode(Gtk.SelectionMode.NONE)
        lb.add_css_class("boxed-list")

        def _choice_row(icon_name, title_text, subtitle_text):
            row = Adw.ActionRow(title=title_text, subtitle=subtitle_text)
            row.set_activatable(True)
            img = Gtk.Image(icon_name=icon_name); img.set_pixel_size(28)
            row.add_prefix(img)
            row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
            lb.append(row); return row

        lect_subtitle = f"{week_label} — readings and standard order pre-filled"
        lect_row   = _choice_row("x-office-calendar-symbolic",
                                  "Start with today's lectionary", lect_subtitle)
        blank_row  = _choice_row("document-new-symbolic",
                                  "Blank service",
                                  "Build your order from scratch")
        tour_row   = _choice_row("help-about-symbolic",
                                  "Show me around",
                                  "Open the quick-start guide and tip strip")
        outer.append(lb)

        skip_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        skip_row.set_margin_top(14)
        sp = Gtk.Box(); sp.set_hexpand(True); skip_row.append(sp)
        skip_btn = Gtk.Button(label="Skip for now")
        skip_btn.add_css_class("flat"); skip_row.append(skip_btn)
        sp2 = Gtk.Box(); sp2.set_hexpand(True); skip_row.append(sp2)
        outer.append(skip_row)

        tv.set_content(outer)

        def _finish(choice: str):
            config.first_launch_completed = True
            config.last_seen_version = APP_VERSION
            config.save()
            win.close()
            if choice == "lect":
                self._seed_lectionary_service(today, info)
                self._show_quickstart_banner()
            elif choice == "tour":
                self._show_welcome(is_new_version=False)
                self._show_quickstart_banner()
            else:
                self._show_quickstart_banner()

        lect_row.connect("activated",  lambda _: _finish("lect"))
        blank_row.connect("activated", lambda _: _finish("blank"))
        tour_row.connect("activated",  lambda _: _finish("tour"))
        skip_btn.connect("clicked",    lambda _: _finish("blank"))
        win.present()

    # ── Lectionary service seeding ────────────────────────────────────────────

    def _seed_lectionary_service(self, today, info: dict):
        """Reset state and pre-fill a standard Sunday order using today's RCL readings."""
        self._reset_state()

        # Set date
        self.selected_date = today
        self.date_button.set_label(today.strftime("%-d %B %Y"))

        # Service title = liturgical week label
        week = info.get("week", "")
        if week:
            self.service_title_entry.set_text(week)

        def _si(name, section, note=""):
            return ServiceItem(name, section, note=note)

        def _ref(key):
            v = info.get(key, "")
            return v if v and v != "—" else ""

        items = [
            SectionDivider("Gathering"),
            _si("Prelude",              "Gathering"),
            _si("Welcome",              "Gathering"),
            _si("Land acknowledgement", "Gathering"),
            _si("Call to worship",      "Gathering"),
            _si("Opening hymn",         "Gathering"),
            _si("Prayer of approach",   "Gathering"),
            SectionDivider("Word"),
        ]
        for name, key in [("Hebrew Bible reading", "ot"),
                           ("Psalm / sung psalm",   "psalm"),
                           ("Epistle reading",       "epistle"),
                           ("Gospel reading",        "gospel")]:
            ref = _ref(key)
            items.append(_si(name, "Word", note=ref))
        items += [
            _si("Sermon / reflection",  "Word"),
            SectionDivider("Response"),
            _si("Hymn",                 "Response"),
            _si("Prayers of the people","Response"),
            _si("Lord's prayer",        "Response"),
            _si("Offering / dedication","Response"),
            SectionDivider("Sending"),
            _si("Closing hymn",         "Sending"),
            _si("Benediction",          "Sending"),
            _si("Postlude",             "Sending"),
        ]

        for item in items:
            self.service_entries.append(item)

        self._refresh_order_list()
        self._update_readings(today)
        self.modified = False          # seeded service starts clean
        self._update_title()
        self._show_toast(f"Service pre-filled for {week or today.strftime('%-d %B %Y')}",
                         timeout=5)

    def _show_welcome(self, is_new_version: bool = False):
        win = Adw.Window(transient_for=self, modal=True)
        win.set_title("Welcome to Rubric")
        win.set_default_size(680, 560)
        tv = Adw.ToolbarView()
        hdr = Adw.HeaderBar()
        win.set_content(tv); tv.add_top_bar(hdr)

        tabs = Gtk.Notebook()
        tabs.set_show_border(False)
        tabs.set_vexpand(True)

        def _text_page(content: str) -> Gtk.ScrolledWindow:
            scroll = Gtk.ScrolledWindow()
            scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            scroll.set_vexpand(True)
            tv2 = Gtk.TextView()
            tv2.set_editable(False); tv2.set_cursor_visible(False)
            tv2.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
            tv2.set_top_margin(16); tv2.set_bottom_margin(16)
            tv2.set_left_margin(22); tv2.set_right_margin(22)
            buf = tv2.get_buffer()
            buf.create_tag("h1", weight=700, scale=1.4, pixels_above_lines=10, pixels_below_lines=4)
            buf.create_tag("h2", weight=700, scale=1.15, pixels_above_lines=8, pixels_below_lines=2)
            buf.create_tag("bold", weight=700)
            buf.create_tag("code", family="monospace", background="#f0f0f0")
            buf.create_tag("bullet", left_margin=24)
            it = buf.get_end_iter()
            in_code = False
            for raw in content.splitlines():
                line = raw.rstrip()
                if line.startswith("```"):
                    in_code = not in_code; buf.insert(it, "\n"); continue
                if in_code:
                    buf.insert_with_tags_by_name(it, line + "\n", "code"); continue
                if not line:
                    buf.insert(it, "\n"); continue
                m = re.match(r'^(#{1,2})\s+(.*)', line)
                if m:
                    tag = "h1" if len(m.group(1)) == 1 else "h2"
                    buf.insert_with_tags_by_name(it, m.group(2) + "\n", tag); continue
                m = re.match(r'^[-*]\s+(.*)', line)
                if m:
                    buf.insert_with_tags_by_name(it, "  • " + m.group(1) + "\n", "bullet"); continue
                parts = re.split(r'(\*\*[^*]+\*\*|`[^`]+`)', line)
                for p in parts:
                    if p.startswith("**") and p.endswith("**"):
                        buf.insert_with_tags_by_name(it, p[2:-2], "bold")
                    elif p.startswith("`") and p.endswith("`"):
                        buf.insert_with_tags_by_name(it, p[1:-1], "code")
                    else:
                        buf.insert(it, p)
                buf.insert(it, "\n")
            scroll.set_child(tv2)
            return scroll

        welcome_text = (
            "# Welcome to Rubric\n\n"
            "Rubric is a worship service planning tool for United Church of Canada "
            "ministry, built for GNOME on Linux.\n\n"
            "## Getting started\n\n"
            "**Set your service date** — click the window title in the header bar to open the "
            "service info popover. The app shows RCL readings, liturgical colour, and hymn "
            "suggestions for that Sunday.\n\n"
            "**Build your order** — double-click any element in the left palette to add it. "
            "Drag the ⠿ handle to reorder. Use ＋ Divider to separate movements "
            "(Gathering, Word, Response, Sending).\n\n"
            "**Add content** — select any element to see the item toolbar: Leader name, "
            "Scripture lookup, Hymn number lookup (VU/MV/LUS), Snippets (✂), and "
            "Responsive Reading builder (℟).\n\n"
            "**Hymn suggestions** — when a date is set, suggested hymns appear below the "
            "order list. Left-click to view on Hymnary.org; right-click to inject into the "
            "selected element.\n\n"
            "**Export** — click the document icon (Ctrl+E) to export to LaTeX. "
            "Click the print icon (Ctrl+Shift+P) to compile to PDF via xelatex.\n\n"
            "## First steps\n\n"
            "- Open **Preferences** (Ctrl+,) to customise the palette, preamble, and snippets\n"
            "- Set a date and browse the RCL readings card\n"
            "- Build a service order and save it as a **template** for future use\n"
            "- See the **TeX Live** tab if you want to compile PDFs directly from the app\n"
        )

        app_dir = Path(__file__).parent
        changelog_path = app_dir / "CHANGELOG.md"
        whats_new = (changelog_path.read_text(encoding="utf-8")
                     if changelog_path.exists()
                     else "# What's New\n\nSee CHANGELOG.md for the full history.")

        texlive_text = (
            "# Installing TeX Live\n\n"
            "Rubric exports to LaTeX and compiles to PDF using xelatex. "
            "You need TeX Live for PDF compilation.\n\n"
            "## Option A — tlmgr (recommended)\n\n"
            "```\n"
            "wget https://mirror.ctan.org/systems/texlive/tlnet/install-tl-unx.tar.gz\n"
            "tar -xzf install-tl-unx.tar.gz && cd install-tl-*\n"
            "sudo perl install-tl\n"
            "```\n\n"
            "Choose **Basic scheme**, then install required packages:\n\n"
            "```\n"
            "tlmgr install xetex fontspec geometry parskip microtype titlesec multicol enumitem hyperref memoir junicode\n"
            "```\n\n"
            "Add to `~/.bashrc`:\n\n"
            "```\n"
            "export PATH=\"$HOME/texlive/bin/x86_64-linux:$PATH\"\n"
            "```\n\n"
            "## Option B — zypper (openSUSE Tumbleweed)\n\n"
            "```\n"
            "sudo zypper install texlive-xetex texlive-fontspec texlive-geometry texlive-parskip texlive-microtype texlive-titlesec texlive-multicol texlive-enumitem texlive-hyperref texlive-memoir\n"
            "sudo zypper install junicode-fonts\n"
            "```\n\n"
            "## Verify\n\n"
            "```\n"
            "xelatex --version\n"
            "```\n\n"
            "## Using a different font\n\n"
            "Open **Preferences → LaTeX** and change `\\setmainfont{Junicode}` to any "
            "installed font, e.g. `Linux Libertine O`, `Gentium Plus`, `TeX Gyre Pagella`.\n"
        )

        tabs.append_page(_text_page(welcome_text), Gtk.Label(label="Welcome"))
        tabs.append_page(_text_page(whats_new),    Gtk.Label(label="What's New"))
        tabs.append_page(_text_page(texlive_text), Gtk.Label(label="TeX Live"))
        tabs.set_current_page(1 if is_new_version else 0)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.append(tabs)
        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_margin_start(16); btn_row.set_margin_end(16)
        btn_row.set_margin_top(8); btn_row.set_margin_bottom(14)
        sp = Gtk.Box(); sp.set_hexpand(True); btn_row.append(sp)
        close_btn = Gtk.Button(label="Get started" if not is_new_version else "Let's go")
        close_btn.add_css_class("suggested-action")
        def on_close(_):
            config.last_seen_version = APP_VERSION
            config.save()
            win.close()
        close_btn.connect("clicked", on_close); btn_row.append(close_btn)
        outer.append(btn_row)
        tv.set_content(outer)
        win.present()

    def _do_autosave(self):
        if self.modified and self.service_entries:
            try:
                AUTOSAVE_PATH.parent.mkdir(parents=True, exist_ok=True)
                d = self._service_data(); d["_autosave"]=True
                AUTOSAVE_PATH.write_text(json.dumps(d,indent=2,ensure_ascii=False),encoding="utf-8")
            except: pass
        return True

    def _check_autosave(self):
        if not AUTOSAVE_PATH.exists(): return False
        dlg = Adw.MessageDialog(transient_for=self, heading="Restore unsaved work?",
                                body="An autosave was found from a previous session. Restore it?")
        dlg.add_response("discard","Discard"); dlg.add_response("restore","Restore")
        dlg.set_response_appearance("restore", Adw.ResponseAppearance.SUGGESTED); dlg.set_default_response("restore")
        def on_resp(d,r):
            if r=="restore": self._load_file(str(AUTOSAVE_PATH), mark_unsaved=True)
            else: self._clear_autosave()
        dlg.connect("response", on_resp); dlg.present(); return False

    def _clear_autosave(self): AUTOSAVE_PATH.unlink(missing_ok=True)

    # ── File IO ───────────────────────────────────────────────────────────────

    def save_as_template(self):
        if not self.service_entries:
            self._error("No elements", "Add some elements to the service order first.")
            return
        dlg = Adw.MessageDialog(transient_for=self, heading="Save as template")
        bx = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8); bx.set_margin_top(6)
        name_row = Adw.EntryRow(title="Template name")
        name_row.set_text(self.service_title_entry.get_text() or "Default")
        bx.append(name_row)

        # Checkbox: set as default
        set_default_row = Adw.ActionRow(title="Set as default template",
                                        subtitle="Used automatically for new services")
        set_default_sw = Gtk.Switch(valign=Gtk.Align.CENTER)
        set_default_sw.set_active(not bool(config.templates))  # default on if first template
        set_default_row.add_suffix(set_default_sw)
        set_default_row.set_activatable_widget(set_default_sw)
        bx.append(set_default_row)

        dividers = sum(1 for e in self.service_entries if e.is_divider)
        total = len(self.service_entries)
        desc = (f"{total} entries ({dividers} dividers + {total-dividers} elements)"
                if dividers else f"{total} elements")
        info = Gtk.Label(label=f"{desc}  ·  Notes/Content saved  ·  Date not saved")
        info.add_css_class("caption"); info.add_css_class("dim-label"); info.set_xalign(0)
        bx.append(info)

        dlg.set_extra_child(bx)
        dlg.add_response("cancel", "Cancel")
        dlg.add_response("save", "Save template")
        dlg.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
        dlg.set_default_response("save")

        def on_resp(d, r):
            if r == "save":
                name = name_row.get_text().strip() or "Default"
                config.templates[name] = [e.to_dict() for e in self.service_entries]
                if set_default_sw.get_active() or not config.default_template:
                    config.default_template = name
                config.save()

        dlg.connect("response", on_resp); dlg.present()

    def _reset_state(self):
        self.service_entries.clear(); self._undo_stack.clear(); self.undo_btn.set_sensitive(False)
        self._redo_stack.clear(); self.redo_btn.set_sensitive(False)
        self.service_title_entry.set_text("")
        self._updating_note = True
        self.notes_view.get_buffer().set_text("", -1)
        self.bulletin_notes_view.get_buffer().set_text("", -1)
        self._updating_note = False
        self._clear_order_list(); self.selected_date=None; self.date_button.set_label("No date selected")
        self.readings_card.set_visible(False); self._current_readings={}
        self._obs_sep.set_visible(False); self._obs_row.set_visible(False)
        self.current_file=None; self.tex_file=None; self.modified=False
        self._selected_global_idx=-1; self._update_title()

    def _apply_template(self, items: list[dict]):
        """Load template items into the current (already-reset) service."""
        for d in items:
            e = _entry_from_dict(d)
            self.service_entries.append(e)
        self._refresh_order_list()

    def new_service(self):
        def do_new():
            self._reset_state()
            if len(config.templates) <= 1:
                # Zero or one template — just apply it silently
                items = config.templates.get(config.default_template, 
                        next(iter(config.templates.values()), None))
                if items:
                    self._apply_template(items)
            else:
                # Multiple templates — ask which one
                dlg = Adw.MessageDialog(transient_for=self, heading="Choose a template")
                bx = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
                bx.set_margin_top(6)
                combo = Adw.ComboRow(title="Template")
                model = Gtk.StringList()
                names = list(config.templates.keys())
                for n in names: model.append(n)
                combo.set_model(model)
                # Pre-select default
                if config.default_template in names:
                    combo.set_selected(names.index(config.default_template))
                bx.append(combo)
                blank_row = Adw.ActionRow(title="Start blank", subtitle="No template")
                blank_sw = Gtk.CheckButton(valign=Gtk.Align.CENTER)
                blank_row.add_suffix(blank_sw); blank_row.set_activatable_widget(blank_sw)
                bx.append(blank_row)
                dlg.set_extra_child(bx)
                dlg.add_response("cancel", "Cancel")
                dlg.add_response("ok",     "New service")
                dlg.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
                dlg.set_default_response("ok")

                def on_resp(d, r):
                    if r == "ok" and not blank_sw.get_active():
                        name = names[combo.get_selected()]
                        items = config.templates.get(name, [])
                        if items:
                            self._apply_template(items)

                dlg.connect("response", on_resp); dlg.present()

        self._confirm_discard(do_new)

    def open_file(self):
        def do_open():
            dlg = Gtk.FileDialog(title="Open service")
            liturgy_dir = self._repo_subdir("liturgy")
            initial = str(liturgy_dir) if liturgy_dir else config.last_dir
            dlg.set_initial_folder(Gio.File.new_for_path(initial))
            filters = Gio.ListStore.new(Gtk.FileFilter); f = Gtk.FileFilter()
            f.set_name("Liturgy files (*.liturgy, *.json)"); f.add_pattern("*.liturgy"); f.add_pattern("*.json")
            filters.append(f); dlg.set_filters(filters)
            dlg.open(self, None, self._on_open_response)
        self._confirm_discard(do_open)

    def _on_open_response(self, dlg, result):
        try: f = dlg.open_finish(result)
        except GLib.Error: return
        self._load_file(f.get_path())

    def _load_file(self, path, mark_unsaved=False):
        try:
            with open(path,encoding="utf-8") as fp: data = json.load(fp)
            self._reset_state(); self.service_title_entry.set_text(data.get("title",""))
            for d in data.get("items",[]):
                entry = _entry_from_dict(d)
                # Migrate old \begin{quotation}...\end{quotation} scripture format
                if isinstance(entry, ServiceItem) and entry.note:
                    entry.note = _migrate_scripture_note(entry.note)
                self.service_entries.append(entry)
            self._refresh_order_list()
            saved_date = data.get("date")
            if saved_date:
                from datetime import date as pydate
                try:
                    self.selected_date = pydate.fromisoformat(saved_date)
                    self.date_button.set_label(self.selected_date.strftime("%-d %B %Y"))
                    self._update_readings(self.selected_date)
                except ValueError: pass
            # Restore linked .tex path if present and file still exists
            saved_tex = data.get("tex_file")
            if saved_tex and Path(saved_tex).exists():
                self.tex_file = saved_tex
            self._update_tex_btn()
            if mark_unsaved: self.current_file=None; self.modified=True
            else:
                self.current_file=path; self.modified=False
                config.last_dir=str(Path(path).parent); config.add_recent(path); config.save(); self._rebuild_recent_menu()
                self._index_service(path, data)
            self._update_title()
        except Exception as e: self._error("Error opening file",str(e))

    def save_file(self):
        if self.current_file: self._write(self.current_file)
        else: self.save_file_as()

    def save_file_as(self):
        liturgy_dir = self._repo_subdir("liturgy")
        initial = str(liturgy_dir) if liturgy_dir else config.last_dir
        dlg = Gtk.FileDialog(title="Save service", initial_name="service.liturgy")
        dlg.set_initial_folder(Gio.File.new_for_path(initial))
        filters = Gio.ListStore.new(Gtk.FileFilter); f = Gtk.FileFilter()
        f.set_name("Liturgy files (*.liturgy)"); f.add_pattern("*.liturgy"); filters.append(f); dlg.set_filters(filters)
        dlg.save(self, None, self._on_save_as_response)

    def _on_save_as_response(self, dlg, result):
        try: f = dlg.save_finish(result)
        except GLib.Error: return
        path = f.get_path()
        if not path.endswith(".liturgy"): path += ".liturgy"
        self.current_file = path; self._write(path)

    def _write(self, path):
        try:
            data = self._service_data()
            with open(path,"w",encoding="utf-8") as f: json.dump(data,f,indent=2,ensure_ascii=False)
            self.modified=False; self._update_title(); self._clear_autosave()
            config.last_dir=str(Path(path).parent); config.add_recent(path); config.save(); self._rebuild_recent_menu()
            self._index_service(path, data)
            if getattr(self, "_close_after_save", False):
                self._close_after_save = False
                self.destroy()
        except Exception as e: self._error("Error saving",str(e))

    def _index_service(self, path: str, data: dict | None = None):
        """Index service elements into the library DB (runs in background thread)."""
        try:
            from rubric_package.db import element_index_service as _eidx
        except ImportError:
            return
        if data is None:
            try:
                import json as _json
                data = _json.loads(Path(path).read_text(encoding="utf-8"))
            except Exception:
                return
        title = data.get("title", "")
        date  = data.get("date", "")
        items = data.get("items", [])
        threading.Thread(
            target=_eidx, args=(path, title, date, items), daemon=True
        ).start()

    def _background_index_scan(self):
        """Scan repo liturgy folder and index any unindexed or stale services."""
        try:
            from rubric_package.db import element_index_service as _eidx, element_services as _esvc
        except ImportError:
            return
        folders = []
        liturgy_dir = self._repo_subdir("liturgy")
        if liturgy_dir and liturgy_dir.is_dir():
            folders.append(liturgy_dir)
        for folder in folders:
            already = {s["service_path"] for s in _esvc(limit=5000)}
            for p in folder.glob("**/*.liturgy"):
                path_str = str(p)
                if path_str in already:
                    continue
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    _eidx(path_str, data.get("title",""), data.get("date",""), data.get("items",[]))
                except Exception:
                    pass

    # ── Recent files ──────────────────────────────────────────────────────────

    def _rebuild_recent_menu(self):
        self._recent_sec.remove_all()
        existing = [p for p in config.recent_files if Path(p).exists()]
        if existing:
            for path in existing:
                item = Gio.MenuItem.new(Path(path).name, None)
                item.set_action_and_target_value("win.open-recent-file", GLib.Variant.new_string(path))
                self._recent_sec.append_item(item)
            self._recent_sec.append("Clear recent files","win.clear-recent")
        else: self._recent_sec.append("No recent files","win.noop")

    def _clear_recent(self): config.recent_files=[]; config.save(); self._rebuild_recent_menu()

    def _tab_rename_action(self):
        div = getattr(self, "_tab_ctx_div", None)
        if not div: return
        dlg = Adw.MessageDialog(transient_for=self, heading="Rename section")
        entry = Adw.EntryRow(title="Section name")
        entry.set_text(div.title)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.set_margin_top(6); box.append(entry)
        dlg.set_extra_child(box)
        dlg.add_response("cancel", "Cancel")
        dlg.add_response("rename", "Rename")
        dlg.set_response_appearance("rename", Adw.ResponseAppearance.SUGGESTED)
        dlg.set_default_response("rename")
        def on_resp(d, r):
            if r == "rename":
                new_name = entry.get_text().strip()
                if new_name and new_name != div.title:
                    div.title = new_name
                    self._refresh_order_list(); self._mark_modified()
        dlg.connect("response", on_resp); dlg.present()

    def _tab_delete_action(self):
        div = getattr(self, "_tab_ctx_div", None)
        if not div: return
        dlg = Adw.MessageDialog(
            transient_for=self,
            heading=f"Delete \u201c{div.title}\u201d?",
            body="This will remove the section divider and all its elements. This cannot be undone after saving.",
        )
        dlg.add_response("cancel", "Cancel")
        dlg.add_response("delete", "Delete section")
        dlg.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dlg.connect("response", lambda d, r: self._delete_section(div) if r == "delete" else None)
        dlg.present()

    # ── Exports ───────────────────────────────────────────────────────────────

    def _grouped_entries(self):
        cur_t=None; cur_i=[]
        for e in self.service_entries:
            if e.is_divider:
                if cur_i or cur_t is not None: yield cur_t,cur_i
                cur_t=e.title; cur_i=[]
            else: cur_i.append(e)
        yield cur_t,cur_i

    def export_bulletin(self):
        """Export congregational bulletin."""
        if config.simple_mode:
            self._export_bulletin_html()
            return
        dlg = Adw.MessageDialog(
            transient_for=self,
            heading="Export Bulletin",
            body="Choose bulletin format:"
        )
        dlg.add_response("cancel",  "Cancel")
        dlg.add_response("print",   "Print (booklet)")
        dlg.add_response("digital", "Digital (screen PDF)")
        dlg.set_response_appearance("print",   Adw.ResponseAppearance.SUGGESTED)
        dlg.set_response_appearance("digital", Adw.ResponseAppearance.SUGGESTED)
        def on_resp(d, r):
            if r == "print":   self._export_bulletin_file(digital=False)
            elif r == "digital": self._export_bulletin_file(digital=True)
        dlg.connect("response", on_resp)
        dlg.present()

    def _build_bulletin_html(self) -> str:
        """Build and return the bulletin as an HTML string.

        Called by both the export action (open in browser) and the live preview panel.
        """
        import re as _re
        from datetime import date as _date

        b = config.bulletin
        church   = b.get("church_name", "")
        address  = b.get("address", "")
        svc_time = b.get("service_time", "")
        website  = b.get("website", "")
        email    = b.get("email", "")
        phone    = b.get("phone", "")
        mission  = b.get("mission", "").strip()
        welcome  = b.get("welcome", "").strip()
        access   = b.get("accessibility", "").strip()
        staff    = b.get("staff", [])

        title    = self.service_title_entry.get_text() or "Order of Service"
        date_str = self.selected_date.strftime("%-d %B %Y") if self.selected_date else ""

        today = _date.today()
        announcements = []
        for ann in b.get("announcements", []):
            exp = ann.get("expires", "")
            if exp:
                try:
                    if _date.fromisoformat(exp) < today:
                        continue
                except ValueError:
                    pass
            text = ann.get("text", "").strip()
            if text:
                announcements.append(text)

        def strip_latex(text):
            text = _re.sub(r'\\begin\{scripture\}(.*?)\\end\{scripture\}',
                lambda m: _re.sub(r'\\sverse\{(\d+)\}\{([^}]+)\}',
                    r'<sup>\1</sup>\2 ', m.group(1).strip()),
                text, flags=_re.DOTALL)
            text = _re.sub(r'\\textbf\{([^}]*)\}', r'<strong>\1</strong>', text)
            text = _re.sub(r'\\textit\{([^}]*)\}', r'<em>\1</em>', text)
            text = _re.sub(r'\\emph\{([^}]*)\}', r'<em>\1</em>', text)
            # Strip spacing/structural commands entirely (don't emit their argument)
            text = _re.sub(r'\\(?:hspace|vspace)\*?\{[^}]*\}', '', text)
            text = _re.sub(
                r'\\(?:noindent|newline|newpage|pagebreak|clearpage|par'
                r'|medskip|bigskip|smallskip|linebreak|centering)\b\s*',
                ' ', text)
            # Generic commands with one braced arg: emit the arg content
            text = _re.sub(r'\\[a-zA-Z]+\*?\{([^}]*)\}', r'\1', text)
            # Remaining bare commands
            text = _re.sub(r'\\[a-zA-Z]+\*?\s*', '', text)
            return text.strip()

        css = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: Georgia, 'Times New Roman', serif; font-size: 11pt;
       color: #111; max-width: 7in; margin: 0 auto; padding: 0.6in 0.5in; }
.church-name { font-size: 18pt; font-variant: small-caps; letter-spacing: 0.05em;
               text-align: center; margin-bottom: 4px; }
.church-sub  { font-size: 9.5pt; text-align: center; color: #444; line-height: 1.6; }
.title       { font-size: 15pt; font-weight: bold; text-align: center;
               margin: 18px 0 2px; }
.date        { font-size: 11pt; font-style: italic; text-align: center;
               color: #555; margin-bottom: 16px; }
hr           { border: none; border-top: 1px solid #bbb; margin: 12px 0; }
h2           { font-size: 10.5pt; font-variant: small-caps; letter-spacing: 0.08em;
               text-align: center; margin: 16px 0 6px; }
.el          { margin-bottom: 8px; }
.el-name     { font-weight: bold; font-size: 10.5pt; }
.leader      { font-style: italic; color: #555; font-size: 9.5pt; margin-left: 5px; }
.note        { font-size: 10pt; margin: 2px 0 0 12px; line-height: 1.55; }
.ann-head    { font-weight: bold; font-variant: small-caps; margin: 4px 0; }
.ann-item    { font-size: 10pt; margin-bottom: 5px; padding-left: 10px; }
.back        { margin-top: 20px; font-size: 9.5pt; color: #444; line-height: 1.6; }
.staff-item  { margin-bottom: 1px; }
.mission     { font-style: italic; margin-top: 8px; }
@media print { body { padding: 0; } @page { margin: 0.75in; } }
"""

        def esc(s):
            return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

        lines = [
            "<!DOCTYPE html><html lang='en'>",
            f"<head><meta charset='utf-8'><title>{esc(church)} – {esc(title)}</title>",
            f"<style>{css}</style></head><body>",
        ]

        if church:
            lines.append(f"<div class='church-name'>{esc(church)}</div>")
        sub_parts = [p for p in [address, svc_time] if p]
        if sub_parts:
            lines.append(f"<div class='church-sub'>{esc(' • '.join(sub_parts))}</div>")
        contact = [p for p in [website, email, phone] if p]
        if contact:
            lines.append(f"<div class='church-sub'>{esc(' • '.join(contact))}</div>")
        if welcome:
            lines.append(f"<div class='church-sub' style='margin-top:6px;font-style:italic'>{esc(welcome)}</div>")

        lines.append(f"<div class='title'>{esc(title)}</div>")
        if date_str:
            lines.append(f"<div class='date'>{esc(date_str)}</div>")
        lines.append("<hr>")

        for sec, items in self._grouped_entries():
            visible = [si for si in items
                       if isinstance(si, ServiceItem) and si.show_in_bulletin]
            if not visible and sec is None:
                continue
            if sec:
                lines.append(f"<h2>{esc(sec)}</h2>")
            for si in visible:
                leader_html = (f"<span class='leader'>({esc(si.leader)})</span>"
                               if si.leader else "")
                lines.append(f"<div class='el'>"
                             f"<div class='el-name'>{esc(si.name)}{leader_html}</div>")
                note_src = si.bulletin_note if si.bulletin_note else si.note
                if note_src:
                    clean = strip_latex(note_src)
                    lines.append(f"<div class='note'>"
                                 f"{clean.replace(chr(10), '<br>')}</div>")
                lines.append("</div>")

        if announcements:
            lines.append("<hr><div class='ann-head'>Announcements</div>")
            for ann in announcements:
                lines.append(f"<div class='ann-item'>{esc(ann)}</div>")

        back = []
        if staff:
            for m in staff:
                role = m.get("role", "").strip()
                name = m.get("name", "").strip()
                if role or name:
                    em = m.get("email", "").strip()
                    em_str = f" &lt;{esc(em)}&gt;" if em else ""
                    back.append(f"<div class='staff-item'>"
                                f"<strong>{esc(role)}</strong>: {esc(name)}{em_str}</div>")
        if mission:
            back.append(f"<div class='mission'>{esc(mission)}</div>")
        if access:
            back.append(f"<div>{esc(access)}</div>")
        if back:
            lines.append("<hr><div class='back'>" + "\n".join(back) + "</div>")

        lines.append("</body></html>")
        return "\n".join(lines)

    def _export_bulletin_html(self):
        """Simple-mode bulletin: build HTML and open in browser for printing."""
        import tempfile
        html = self._build_bulletin_html()
        with tempfile.NamedTemporaryFile(
                mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write(html)
            tmp = f.name
        Gtk.show_uri(None, GLib.filename_to_uri(tmp, None), 0)
        self._show_toast("Bulletin opened in browser — use File → Print to print", timeout=6)

    def _export_bulletin_file(self, digital: bool):
        title = self.service_title_entry.get_text() or "bulletin"
        date_str = self.selected_date.strftime("%Y-%m-%d") if self.selected_date else "undated"
        church = config.bulletin.get("church_name", "").replace(" ", "_") or "Bulletin"
        suffix = "digital" if digital else "print"
        default_name = f"{church}_{date_str}_{suffix}.tex"
        bul_dir = self._repo_subdir("bulletins")
        tex_dir = self._repo_subdir("tex")
        initial = str(bul_dir) if bul_dir else (str(tex_dir) if tex_dir else config.last_dir)
        dlg = Gtk.FileDialog(title="Save bulletin as…", initial_name=default_name)
        dlg.set_initial_folder(Gio.File.new_for_path(initial))
        filters = Gio.ListStore.new(Gtk.FileFilter)
        f = Gtk.FileFilter(); f.set_name("LaTeX (*.tex)"); f.add_pattern("*.tex")
        filters.append(f); dlg.set_filters(filters)
        dlg.save(self, None, lambda d, r, dig=digital: self._on_bulletin_save(d, r, dig))

    def _on_bulletin_save(self, dlg, result, digital: bool):
        try:
            f = dlg.save_finish(result)
        except Exception:
            return
        path = f.get_path()
        config.last_dir = str(Path(path).parent)
        lines = self._build_bulletin_latex(digital=digital)
        Path(path).write_text("\n".join(lines), encoding="utf-8")
        self._show_toast(f"Bulletin saved: {Path(path).name}")
        self._compile_bulletin_pdf(path)

    def _compile_bulletin_pdf(self, tex_path_str: str):
        """Compile bulletin tex to PDF in background thread, then open it."""
        tex_path = Path(tex_path_str)
        xelatex = shutil.which("xelatex")
        if not xelatex:
            for candidate in [
                Path.home() / "texlive/bin/x86_64-linux/xelatex",
                Path("/usr/local/texlive/2024/bin/x86_64-linux/xelatex"),
                Path("/usr/local/texlive/2023/bin/x86_64-linux/xelatex"),
            ]:
                if candidate.exists(): xelatex = str(candidate); break

        if not xelatex:
            self._show_toast("Bulletin saved — install xelatex to compile to PDF", timeout=6)
            return

        self._compiling_toast = Adw.Toast.new("Compiling bulletin…")
        self._compiling_toast.set_timeout(0)
        self._toast_overlay.add_toast(self._compiling_toast)

        def run():
            try:
                result = subprocess.run(
                    [xelatex, "-interaction=nonstopmode", "-halt-on-error", tex_path.name],
                    cwd=str(tex_path.parent),
                    capture_output=True, text=True, timeout=60,
                    encoding="utf-8", errors="replace",
                )
                GLib.idle_add(self._on_bulletin_compiled, result, tex_path)
            except subprocess.TimeoutExpired:
                def _on_timeout():
                    try: self._compiling_toast.dismiss()
                    except Exception: pass
                    self._show_toast("Bulletin compile timed out.", 8)
                GLib.idle_add(_on_timeout)
            except Exception as e:
                def _on_error(msg=str(e)):
                    try: self._compiling_toast.dismiss()
                    except Exception: pass
                    self._show_toast(f"Bulletin compile error: {msg}", 8)
                GLib.idle_add(_on_error)

        threading.Thread(target=run, daemon=True).start()

    def _on_bulletin_compiled(self, result, tex_path: Path):
        try: self._compiling_toast.dismiss()
        except Exception: pass

        if result.returncode != 0:
            combined = (result.stdout or "") + (result.stderr or "")
            log_lines = combined.splitlines()
            errors = [l for l in log_lines if l.startswith("!") or "Error" in l]
            msg = " — ".join(errors[-2:]) if errors else "xelatex error (check .log file)"
            self._show_toast(f"Bulletin compile failed: {msg[:80]}", timeout=10)
            return

        for ext in (".log", ".aux", ".out", ".dvi", ".synctex.gz",
                    ".toc", ".lof", ".lot", ".fls", ".fdb_latexmk",
                    ".maf", ".mtc", ".mtc0"):
            try: tex_path.with_suffix(ext).unlink(missing_ok=True)
            except OSError: pass

        pdf = tex_path.with_suffix(".pdf")
        pdf_dir = self._repo_subdir("bulletins")
        if pdf_dir and pdf.exists():
            dest = pdf_dir / pdf.name
            try:
                shutil.move(str(pdf), str(dest))
                pdf = dest
            except OSError:
                pass
        if pdf.exists():
            self._show_toast(f"✓ {pdf.name}", timeout=4)
            Gtk.show_uri(None, pdf.as_uri(), 0)
        else:
            self._show_toast("Compiled — PDF not found.", timeout=6)

    def _build_bulletin_latex(self, digital: bool = False) -> list[str]:
        """Build complete LaTeX for the congregational bulletin.

        Print mode: memoir class, half-letter (5.5x8.5in), fold for booklet.
        Digital mode: extarticle, full letter, colour hyperlinks.
        """
        from datetime import date as pydate
        b = config.bulletin
        church   = _latex_escape(b.get("church_name", ""))
        address  = _latex_escape(b.get("address", ""))
        svc_time = _latex_escape(b.get("service_time", ""))
        website  = _latex_escape(b.get("website", ""))
        email    = _latex_escape(b.get("email", ""))
        phone    = _latex_escape(b.get("phone", ""))
        mission  = _latex_escape(b.get("mission", ""))
        welcome  = _latex_escape(b.get("welcome", ""))
        access   = _latex_escape(b.get("accessibility", ""))
        title    = _latex_escape(self.service_title_entry.get_text() or "Order of Service")
        date_str = (self.selected_date.strftime("%-d %B %Y")
                    if self.selected_date else "")

        if digital:
            # Full letter, colour hyperlinks, extarticle
            lines = [
                r"\documentclass[12pt,letterpaper]{extarticle}",
                r"\usepackage{fontspec}",
                r"\setmainfont{Junicode}[UprightFont=*,BoldFont=*-Bold,"
                r"ItalicFont=*-Italic,BoldItalicFont=*-BoldItalic]",
                r"\usepackage{geometry}",
                r"\geometry{top=1in,bottom=1in,left=1in,right=1in}",
                r"\usepackage{parskip,microtype,titlesec,multicol}",
                r"\usepackage[dvipsnames]{xcolor}",
                r"\usepackage{hyperref}",
                r"\hypersetup{colorlinks=true,linkcolor=MidnightBlue,urlcolor=MidnightBlue}",
                r"",
                r"% Section headings: centred small-caps",
                r"\titleformat{\section}{\normalsize\scshape\centering}{}{0em}{}",
                r"\titlespacing*{\section}{0pt}{10pt}{4pt}",
                r"",
            ]
        else:
            # Half-letter booklet via memoir (no titlesec, no geometry pkg)
            lines = [
                r"\documentclass[12pt,oneside]{memoir}",
                r"\usepackage{fontspec}",
                r"\setmainfont{Junicode}[UprightFont=*,BoldFont=*-Bold,"
                r"ItalicFont=*-Italic,BoldItalicFont=*-BoldItalic]",
                r"\usepackage{parskip,microtype,multicol}",
                r"\usepackage[dvipsnames]{xcolor}",
                r"\usepackage{hyperref}",
                r"\hypersetup{hidelinks}",
                r"",
                r"% Memoir layout: half-letter, fold for saddle-stitch booklet",
                r"\setstocksize{8.5in}{5.5in}",
                r"\settrimmedsize{\stockheight}{\stockwidth}{*}",
                r"\setlrmarginsandblock{0.6in}{0.6in}{*}",
                r"\setulmarginsandblock{0.6in}{0.7in}{*}",
                r"\checkandfixthelayout",
                r"",
                r"% Section headings via memoir (not titlesec)",
                r"\setsecheadstyle{\normalsize\scshape\centering}",
                r"\setbeforesecskip{10pt}",
                r"\setaftersecskip{4pt}",
                r"",
            ]

        # Shared commands for both modes
        lines += [
            r"% Movement headings (Gathering, Word, Response, Sending)",
            r"\newcommand{\movement}[1]{%",
            r"  \vspace{8pt}%",
            r"  \begin{center}{\large\bfseries\scshape #1}\end{center}%",
            r"  \vspace{4pt}%",
            r"}",
            r"",
            r"% Hymn: bold reference + italic title",
            r"\newcommand{\hymnref}[2]{\textbf{#1}\enspace #2}",
            r"",
            r"% Responsive reading: both Leader and People in bold",
            r"\newcommand{\ldr}[1]{\textbf{#1}\\}",
            r"\newcommand{\ppl}[1]{\textbf{#1}\\}",
            r"",
            r"% Scripture environment: verse number + hanging indent",
            r"\newenvironment{scripture}{%",
            r"  \par\begingroup\setlength{\parskip}{0pt}%",
            r"  \setlength{\parindent}{-2.4em}\leftskip=2.4em",
            r"}{\par\endgroup\vspace{4pt}}",
            r"\newcommand{\sverse}[2]{\textsuperscript{#1}\quad #2\par}",
            r"",
        ]
        lines += [r"\begin{document}", r"\pagestyle{empty}", r""]

        # ── Cover page ────────────────────────────────────────────────────────
        lines += [
            r"\begin{center}",
            r"\vspace*{1.5cm}",
            r"{\Large\bfseries\scshape " + church + r"}\\[0.4em]",
        ]
        if address:
            lines.append(r"{\small " + address + r"}\\[0.2em]")
        lines += [
            r"{\small " + svc_time + r"}\\[2cm]",
            r"{\LARGE\bfseries " + title + r"}\\[0.6em]",
            r"{\large " + date_str + r"}\\[2cm]",
        ]
        if website or email or phone:
            lines.append(r"{\small")
            if website:
                if digital:
                    lines.append(r"\href{https://" + b.get("website","") + r"}{" + website + r"}\\")
                else:
                    lines.append(website + r"\\")
            if email:
                if digital:
                    lines.append(r"\href{mailto:" + b.get("email","") + r"}{" + email + r"}\\")
                else:
                    lines.append(email + r"\\")
            if phone:
                lines.append(phone + r"\\")
            lines.append(r"}")
        if welcome:
            lines += [r"\\[1cm]", r"\textit{" + welcome + r"}"]
        lines += [r"\end{center}", r"\newpage", r""]

        # ── Service order ─────────────────────────────────────────────────────
        current_section = None
        in_multicols = False

        for entry in self.service_entries:
            if isinstance(entry, SectionDivider):
                if in_multicols:
                    lines += [r"\end{multicols}", ""]
                    in_multicols = False
                current_section = entry.title
                lines += [
                    r"\vspace{8pt}",
                    r"\movement{" + _latex_escape(entry.title) + r"}",
                    r"\begin{multicols}{2}",
                    "",
                ]
                in_multicols = True
                continue

            if not isinstance(entry, ServiceItem) or not entry.show_in_bulletin:
                continue

            lines += ["", r"\section*{" + _latex_escape(entry.name) + "}"]

            # Hymn reference — always show in bulletin as bold reference + title
            name_lower = entry.name.lower()
            is_hymn = any(k in name_lower for k in ("hymn","psalm","sung","song","anthem","gloria"))

            # Determine what content to show
            content = entry.bulletin_note if entry.bulletin_note else entry.note

            if is_hymn and content:
                # Bold the hymn reference (VU 145, MV 79, etc.)
                m = re.match(r'^((?:VU|MV|LUS|TLUS|MWS)\s+\d+)\s*[—–-]?\s*(.*)', content, re.DOTALL)
                if m:
                    ref  = _latex_escape(m.group(1).strip())
                    rest = _latex_escape(m.group(2).strip().split("\n")[0]) if m.group(2).strip() else ""
                    if rest:
                        lines.append(r"\hymnref{" + ref + r"}{\textit{``" + rest + r"''}}")
                    else:
                        lines.append(r"\textbf{" + ref + r"}")
                else:
                    lines.append(_note_for_latex(content))
            elif content:
                # Check if it's a responsive reading
                if r"\ldr{" in content or r"\ppl{" in content or r"\begin{verse}" in content:
                    lines.append(content)
                elif any(l.strip().startswith("\\") for l in content.splitlines()):
                    lines.append(content)
                else:
                    lines.append(_latex_escape(content))

        if in_multicols:
            lines += ["", r"\end{multicols}"]

        # ── Acknowledgements block ────────────────────────────────────────────
        staff = b.get("staff", [])
        # Also harvest leader assignments from the service
        leaders: dict[str, list[str]] = {}
        for entry in self.service_entries:
            if isinstance(entry, ServiceItem) and entry.leader and entry.show_in_bulletin:
                leaders.setdefault(entry.leader, []).append(entry.name)

        if staff or leaders:
            lines += [
                r"\vspace{12pt}",
                r"\begin{center}\rule{0.4\linewidth}{0.4pt}\end{center}",
                r"\begin{center}{\small",
            ]
            for member in staff:
                role = _latex_escape(member.get("role", ""))
                name = _latex_escape(member.get("name", ""))
                em   = member.get("email", "")
                if digital and em:
                    lines.append(r"\textit{" + role + r":} \href{mailto:" + em + r"}{" + name + r"}\\")
                else:
                    lines.append(r"\textit{" + role + r":} " + name + r"\\")
            for person, roles in leaders.items():
                lines.append(_latex_escape(person) + r" (\textit{" +
                             _latex_escape(", ".join(roles)) + r"})\\")
            lines += [r"}\end{center}", ""]

        # ── Announcements ─────────────────────────────────────────────────────
        if b.get("include_announcements", True):
            today = pydate.today()
            active = []
            for ann in b.get("announcements", []):
                exp = ann.get("expires", "")
                if exp:
                    try:
                        from datetime import datetime
                        if datetime.strptime(exp, "%Y-%m-%d").date() < today:
                            continue
                    except ValueError:
                        pass
                active.append(ann.get("text", "").strip())
            if active:
                lines += [
                    r"\newpage",
                    r"\begin{center}{\large\bfseries\scshape Announcements}\end{center}",
                    r"\vspace{4pt}",
                    "",
                ]
                for ann in active:
                    if any(l.strip().startswith("\\") for l in ann.splitlines()):
                        lines.append(ann)
                    else:
                        lines.append(_latex_escape(ann))
                    lines.append(r"\vspace{6pt}")

        # ── Back page: mission + contact ──────────────────────────────────────
        if mission or access or email or website:
            lines += [
                r"\newpage",
                r"\begin{center}",
                r"\vspace*{\fill}",
            ]
            if mission:
                lines += [
                    r"{\small\textit{" + mission + r"}}\\[0.8em]",
                ]
            if access:
                lines += [r"{\small " + access + r"}\\[0.4em]"]
            if website or email or phone:
                lines.append(r"{\small ")
                if website: lines.append(website + r"\\")
                if email:   lines.append(email + r"\\")
                if phone:   lines.append(phone + r"\\")
                lines.append(r"}")
            lines += [r"\vspace*{\fill}", r"\end{center}", ""]

        lines += [r"\end{document}", ""]
        return lines

    def export_html(self):
        title = self.service_title_entry.get_text() or "Order of Service"
        date_str = self.selected_date.strftime("%-d %B %Y") if self.selected_date else ""

        import tempfile, re as _re

        def strip_latex(text: str) -> str:
            """Remove common LaTeX markup for HTML display."""
            text = _re.sub(r'\\begin\{scripture\}(.*?)\\end\{scripture\}', lambda m: m.group(1), text, flags=_re.DOTALL)
            text = _re.sub(r'\\sverse\{(\d+)\}\{([^}]*)\}', r'<sup>\1</sup>&nbsp;\2', text)
            text = _re.sub(r'\\textbf\{([^}]*)\}', r'<strong>\1</strong>', text)
            text = _re.sub(r'\\textit\{([^}]*)\}', r'<em>\1</em>', text)
            text = _re.sub(r'\\emph\{([^}]*)\}', r'<em>\1</em>', text)
            text = _re.sub(r'\\[a-zA-Z]+\*?\{([^}]*)\}', r'\1', text)
            text = _re.sub(r'\\[a-zA-Z]+\*?\s*', '', text)
            return text.strip()

        css = """
    body { font-family: Georgia, 'Times New Roman', serif; max-width: 700px; margin: 0 auto; padding: 1.5em; color: #111; }
    h1 { font-size: 1.6em; text-align: center; margin-bottom: 0.1em; }
    .date { text-align: center; color: #555; font-style: italic; margin-bottom: 2em; }
    h2 { font-size: 1.1em; font-variant: small-caps; letter-spacing: 0.08em; border-bottom: 1px solid #999; padding-bottom: 2px; margin-top: 2em; margin-bottom: 0.5em; }
    .element { margin-bottom: 0.8em; }
    .element-name { font-weight: bold; }
    .leader { font-style: italic; color: #444; margin-left: 0.5em; font-size: 0.9em; }
    .note { margin-top: 0.2em; margin-left: 1em; color: #333; font-size: 0.95em; line-height: 1.5; }
    .verse-num { vertical-align: super; font-size: 0.75em; margin-right: 0.2em; }
    @media print {
      body { padding: 0; }
      h2 { page-break-after: avoid; }
      .element { page-break-inside: avoid; }
    }
    """

        def _esc_title(s: str) -> str:
            return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        lines = [
            "<!DOCTYPE html>",
            "<html lang='en'><head><meta charset='utf-8'>",
            f"<title>{_esc_title(title)}</title>",
            f"<style>{css}</style>",
            "</head><body>",
            f"<h1>{_esc_title(title)}</h1>",
        ]
        if date_str:
            lines.append(f"<p class='date'>{date_str}</p>")

        def _esc(s: str) -> str:
            return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        for sec, items in self._grouped_entries():
            if not items and sec is None:
                continue
            if sec:
                lines.append(f"<h2>{_esc(sec)}</h2>")
            for si in items:
                leader_html = f"<span class='leader'>({_esc(si.leader)})</span>" if si.leader else ""
                lines.append(f"<div class='element'>")
                lines.append(f"<div class='element-name'>{_esc(si.name)}{leader_html}</div>")
                if si.note:
                    note = si.note
                    note_html = _re.sub(r'\\begin\{scripture\}(.*?)\\end\{scripture\}',
                        lambda m: "<div class='note'>" + _re.sub(r'\\sverse\{(\d+)\}\{([^}]+)\}',
                            r"<sup class='verse-num'>\1</sup>\2 ", m.group(1).strip()) + "</div>",
                        note, flags=_re.DOTALL)
                    if note_html == note:
                        clean = strip_latex(note)
                        note_lines = clean.split('\n')
                        note_html = "<div class='note'>" + "<br>".join(note_lines) + "</div>"
                    lines.append(note_html)
                lines.append("</div>")

        lines += ["</body></html>"]
        html = "\n".join(lines)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write(html)
            tmp_path = f.name

        Gtk.show_uri(None, GLib.filename_to_uri(tmp_path, None), 0)
        self._show_toast("Opened in browser — use File → Print to save as PDF", timeout=6)

    def export_text(self):
        dlg = Gtk.FileDialog(title="Export plain text", initial_name="service.txt")
        dlg.set_initial_folder(Gio.File.new_for_path(config.last_dir))
        filters = Gio.ListStore.new(Gtk.FileFilter); f = Gtk.FileFilter(); f.set_name("Text files (*.txt)"); f.add_pattern("*.txt")
        filters.append(f); dlg.set_filters(filters); dlg.save(self, None, self._on_export_text_response)

    def _on_export_text_response(self, dlg, result):
        try: f = dlg.save_finish(result)
        except GLib.Error: return
        path = f.get_path(); title = self.service_title_entry.get_text() or "Order of service"
        lines = [title,"="*len(title)]
        for sec,items in self._grouped_entries():
            if not items and sec is None: continue
            lines.append(""); lines.append(sec.upper() if sec else "")
            for si in items:
                line = f"  \u2022 {si.name}"
                if si.note: line += f"  \u2014  {si.note.split(chr(10))[0]}"
                lines.append(line)
        try:
            with open(path,"w",encoding="utf-8") as fp: fp.write("\n".join(lines))
        except Exception as e: self._error("Export error",str(e))

    def _update_tex_btn(self):
        """Update the TeX button tooltip to reflect current link state."""
        if self.tex_file:
            name = Path(self.tex_file).name
            self.tex_btn.set_tooltip_text(
                f"Export to {name} (Ctrl+E)\nRight-click to change file"
            )
        else:
            self.tex_btn.set_tooltip_text(
                "Export to LaTeX… (Ctrl+E)\nChoose a file to link"
            )

    def _build_latex_lines(self) -> list[str]:
        """Build the full list of LaTeX lines for the current service."""
        title    = self.service_title_entry.get_text() or "Order of Service"
        date_str = self.selected_date.strftime("%-d %B %Y") if self.selected_date else ""
        lines = [
            config.preamble.rstrip(), "",
            f"\\title{{{_latex_escape(title)}}}",
            f"\\date{{{_latex_escape(date_str)}}}",
            "",
            "\\begin{document}",
            "\\maketitle",
            "\\thispagestyle{empty}",
        ]

        groups = list(self._grouped_entries())
        # Filter to non-empty groups only
        groups = [(sec, items) for sec, items in groups if items]

        in_multicols = False

        for g_idx, (sec, items) in enumerate(groups):
            lines.append("")

            if sec:
                # Close any open multicols environment before starting new part
                if in_multicols:
                    lines.append("\\end{multicols}")
                    in_multicols = False

                esc = _latex_escape(sec)
                lines.append("\\newpage")
                # Full-width centred part title — no rule, just spacing
                lines.append("{\\centering\\large\\bfseries\\scshape " + esc + "\\par}")
                lines.append("\\vspace{8pt}")
                # Open two-column environment for the part's content
                lines.append("\\begin{multicols}{2}")
                in_multicols = True

            for si in items:
                lines.append("")
                # Element heading — bold with rule below (from \titleformat), right-aligned leader
                if si.leader:
                    lines.append(
                        f"\\section*{{{_latex_escape(si.name)}"
                        f"\\hfill{{\\small\\normalfont\\textit{{{_latex_escape(si.leader)}}}}}}}"
                    )
                else:
                    lines.append(f"\\section*{{{_latex_escape(si.name)}}}")
                if si.note: lines.append(_note_for_latex(si.note))

        # Close trailing multicols if open
        if in_multicols:
            lines.append("")
            lines.append("\\end{multicols}")

        lines += ["", "\\end{document}", ""]
        return lines

    def _write_latex(self, path: str):
        """Write LaTeX to path, record as linked file, save the .liturgy."""
        try:
            with open(path, "w", encoding="utf-8") as fp:
                fp.write("\n".join(self._build_latex_lines()))
            self.tex_file = path
            self._update_tex_btn()
            # Persist the link — save the .liturgy if it has a path
            if self.current_file:
                with open(self.current_file, "w", encoding="utf-8") as f:
                    json.dump(self._service_data(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            self._error("Export error", str(e))

    def quick_export_latex(self):
        """One-click export: write directly if linked, else ask for a file."""
        if self.tex_file:
            self._write_latex(self.tex_file)
        else:
            self.export_latex()

    def compile_pdf(self):
        """Export to .tex then compile with xelatex, open the resulting PDF."""
        if not self.tex_file:
            self.export_latex()
            self._show_toast("Link a .tex file first, then compile again.", timeout=5)
            return

        self._write_latex(self.tex_file)
        tex_path = Path(self.tex_file)
        tex_dir  = str(tex_path.parent)
        tex_name = tex_path.name

        xelatex = shutil.which("xelatex")
        if not xelatex:
            for candidate in [
                Path.home() / "texlive/bin/x86_64-linux/xelatex",
                Path("/usr/local/texlive/2024/bin/x86_64-linux/xelatex"),
                Path("/usr/local/texlive/2023/bin/x86_64-linux/xelatex"),
            ]:
                if candidate.exists(): xelatex = str(candidate); break

        if not xelatex:
            self._show_toast("xelatex not found — add TeX Live to PATH", timeout=8)
            return

        # Show persistent "Compiling…" toast (timeout=0 keeps it until replaced)
        self._compiling_toast = Adw.Toast.new("Compiling PDF…")
        self._compiling_toast.set_timeout(0)
        self._toast_overlay.add_toast(self._compiling_toast)
        self.pdf_btn.set_sensitive(False)

        def run_xelatex():
            try:
                result = subprocess.run(
                    [xelatex, "-interaction=nonstopmode", "-halt-on-error", tex_name],
                    cwd=tex_dir, capture_output=True, text=True, timeout=60,
                    encoding="utf-8", errors="replace",
                )
                GLib.idle_add(self._on_compile_done, result, tex_path)
            except subprocess.TimeoutExpired:
                GLib.idle_add(self._on_compile_error, "xelatex timed out after 60 seconds.")
            except Exception as e:
                GLib.idle_add(self._on_compile_error, str(e))

        threading.Thread(target=run_xelatex, daemon=True).start()

    def _on_compile_done(self, result, tex_path: Path):
        self.pdf_btn.set_sensitive(True)
        # Dismiss the "Compiling…" toast
        try: self._compiling_toast.dismiss()
        except Exception: pass

        if result.returncode != 0:
            combined = (result.stdout or "") + (result.stderr or "")
            log_lines = combined.splitlines()
            errors = [l for l in log_lines if l.startswith("!") or "Error" in l]
            msg = " — ".join(errors[-2:]) if errors else "xelatex error (check .log file)"
            self._show_toast(f"Compilation failed: {msg[:80]}", timeout=10)
            return

        # Clean up helper files
        for ext in (".log",".aux",".out",".dvi",".synctex.gz",
                    ".toc",".lof",".lot",".fls",".fdb_latexmk"):
            try: tex_path.with_suffix(ext).unlink(missing_ok=True)
            except OSError: pass

        pdf_path = tex_path.with_suffix(".pdf")
        pdf_dir = self._repo_subdir("pdf")
        if pdf_dir and pdf_path.exists():
            dest = pdf_dir / pdf_path.name
            try:
                shutil.move(str(pdf_path), str(dest))
                pdf_path = dest
            except OSError:
                pass
        if pdf_path.exists():
            self._show_toast(f"✓ {pdf_path.name}", timeout=4)
            Gtk.show_uri(None, pdf_path.as_uri(), 0)
        else:
            self._show_toast("Compiled but PDF not found.", timeout=6)

    def _on_compile_error(self, message: str):
        self.pdf_btn.set_sensitive(True)
        try: self._compiling_toast.dismiss()
        except Exception: pass
        self._show_toast(f"Compile error: {message[:80]}", timeout=10)

    def _unlink_tex(self):
        self.tex_file = None
        self._update_tex_btn()

    def export_latex(self):
        """Full file-chooser export (also called by quick_export when no link exists)."""
        tex_dir = self._repo_subdir("tex")
        if self.current_file:
            default = Path(self.current_file).stem + ".tex"
        else:
            title   = self.service_title_entry.get_text() or "service"
            default = title.replace(" ", "_").lower() + ".tex"
        folder = str(tex_dir) if tex_dir else (
            str(Path(self.current_file).parent) if self.current_file else config.last_dir
        )
        dlg = Gtk.FileDialog(title="Export LaTeX", initial_name=default)
        dlg.set_initial_folder(Gio.File.new_for_path(folder))
        filters = Gio.ListStore.new(Gtk.FileFilter)
        f = Gtk.FileFilter(); f.set_name("TeX files (*.tex)"); f.add_pattern("*.tex")
        filters.append(f); dlg.set_filters(filters)
        dlg.save(self, None, self._on_export_latex_response)

    def _on_export_latex_response(self, dlg, result):
        try: f = dlg.save_finish(result)
        except GLib.Error: return
        path = f.get_path()
        if not path.endswith(".tex"): path += ".tex"
        self._write_latex(path)

    # ── Leader ────────────────────────────────────────────────────────────────

    def _on_leader_changed(self, entry):
        if self._updating_note: return
        idx = self._selected_index()
        if not (0 <= idx < len(self.service_entries)): return
        entry_obj = self.service_entries[idx]
        if not isinstance(entry_obj, ServiceItem): return
        entry_obj.leader = entry.get_text()
        self._mark_modified()

    def _on_bulletin_toggled(self, btn):
        if self._updating_note: return
        idx = self._selected_index()
        if not (0 <= idx < len(self.service_entries)): return
        e = self.service_entries[idx]
        if not isinstance(e, ServiceItem): return
        e.show_in_bulletin = btn.get_active()
        row = self.order_listbox.get_row_at_index(idx) if not config.use_tabs else None
        if row:
            row.set_opacity(1.0 if btn.get_active() else 0.45)
        self._mark_modified()

    # ── Hymn suggestions ──────────────────────────────────────────────────────

    def _update_hymn_suggestions(self, week: str, season: str):
        """Rebuild the suggestions chip strip for the current RCL week."""
        # Clear existing chips
        while True:
            c = self._sugg_chips_box.get_first_child()
            if c is None: break
            self._sugg_chips_box.remove(c)

        if not _SUGG_OK:
            self.sugg_revealer.set_reveal_child(False)
            return

        suggestions = _get_hymn_suggestions(week, season)
        if not suggestions:
            self.sugg_revealer.set_reveal_child(False)
            return

        for prefix, number, title in suggestions:
            # Wrap chip + YT button in a small box
            chip_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)

            chip = Gtk.Button()
            chip.set_tooltip_text(f"Open {prefix} {number} on Hymnary  ·  Right-click to add to selected element")
            chip_lbl = Gtk.Label()
            chip_lbl.set_markup(
                f'<span weight="bold">{prefix} {number}</span>'
                f'\n<span size="small">{GLib.markup_escape_text(title[:28])}{"…" if len(title)>28 else ""}</span>'
            )
            chip_lbl.set_justify(Gtk.Justification.CENTER)
            chip.set_child(chip_lbl)
            chip.add_css_class("card")

            # Left click → inline Hymnary preview (WebKit) or browser fallback
            from hymn_lookup import HYMNALS
            hymnal_id = HYMNALS.get(prefix, (prefix, ""))[0]
            hymnary_url = f"https://hymnary.org/hymn/{hymnal_id}/{number}"
            hymn_label = f"{prefix} {number} — {title}"
            if _WEBKIT_OK:
                chip.connect("clicked", lambda _b, u=hymnary_url, lbl=hymn_label:
                             self._show_hymnary_preview(u, lbl))
            else:
                chip.connect("clicked", lambda _b, u=hymnary_url: Gtk.show_uri(None, u, 0))

            # Right click → add to service
            rg = Gtk.GestureClick(); rg.set_button(3)
            def on_right(_g, _n, _x, _y, p=prefix, n=number, t=title):
                self._add_hymn_from_suggestion(p, n, t)
            rg.connect("pressed", on_right)
            chip.add_controller(rg)
            chip_box.append(chip)

            # YouTube search button
            import urllib.parse
            yt_query = urllib.parse.quote(f"{prefix} {number} {title}")
            yt_url = f"https://www.youtube.com/results?search_query={yt_query}"
            yt_btn = Gtk.Button(label="▶", tooltip_text=f"Search YouTube: {prefix} {number}")
            yt_btn.add_css_class("flat")
            yt_btn.set_valign(Gtk.Align.CENTER)
            yt_btn.connect("clicked", lambda _b, u=yt_url: Gtk.show_uri(None, u, 0))
            chip_box.append(yt_btn)

            self._sugg_chips_box.append(chip_box)

        self.sugg_revealer.set_reveal_child(True)

    def _show_hymnary_preview(self, url: str, title: str):
        """Open an inline WebKit window showing the Hymnary page."""
        win = Adw.Window(transient_for=self, modal=False)
        win.set_title(title)
        win.set_default_size(780, 620)
        tv = Adw.ToolbarView()
        hdr = Adw.HeaderBar()
        # Open in browser button
        ext_btn = Gtk.Button(icon_name="web-browser-symbolic",
                             tooltip_text="Open in browser")
        ext_btn.add_css_class("flat")
        ext_btn.connect("clicked", lambda _: Gtk.show_uri(None, url, 0))
        hdr.pack_end(ext_btn)
        tv.add_top_bar(hdr)
        try:
            webview = _WebKit.WebView()
            webview.load_uri(url)
            webview.set_vexpand(True)
            tv.set_content(webview)
        except Exception as e:
            fallback = Adw.StatusPage(title="WebKit unavailable",
                                      description=str(e),
                                      icon_name="web-browser-symbolic")
            tv.set_content(fallback)
            Gtk.show_uri(None, url, 0)
        win.set_content(tv)
        win.present()

    def _add_hymn_from_suggestion(self, prefix: str, number: int, title: str):
        """
        Inject hymn reference into the currently selected element's Notes/Content.
        If no element is selected, fall back to creating a new Hymn element.
        """
        ref = f"{prefix} {number} — {title}"
        idx = self._selected_index()
        if 0 <= idx < len(self.service_entries):
            entry = self.service_entries[idx]
            if isinstance(entry, ServiceItem):
                self._push_undo()
                # Prepend to notes — hymn ref goes at the top
                entry.note = ref + ("\n" + entry.note if entry.note else "")
                self._updating_note = True
                self.notes_view.get_buffer().set_text(entry.note, -1)
                self._updating_note = False
                row = self._find_row_for_index(idx)
                if isinstance(row, Adw.ActionRow):
                    row.set_subtitle(self._note_preview(entry.note))
                self._mark_modified()
                return
        # Nothing selected — create a new Hymn element as fallback
        self._push_undo()
        si = ServiceItem("Hymn", list(self._palette_listboxes.keys())[0] if self._palette_listboxes else "")
        si.note = ref
        self._add_entry(si)

    # ── Scripture search ──────────────────────────────────────────────────────

    def _do_scripture_search(self):
        ref = self.scripture_entry.get_text().strip()
        if not ref: return
        if not _BIBLE_OK:
            self._error("Bible lookup unavailable", "bible_api.py not found.")
            return
        BibleViewer(ref, self._on_bible_insert, translation=config.bible_translation, esv_key=config.bible_api_key_esv, transient_for=self).present()
        self.scripture_entry.set_text("")

    def open_scripture_search(self):
        """Focus the scripture search entry."""
        self.scripture_entry.grab_focus()

    # ── Responsive reading builder ────────────────────────────────────────────

    def open_responsive_reading(self):
        dlg = Adw.Window(transient_for=self, modal=True)
        dlg.set_title("Responsive Reading Builder")
        dlg.set_default_size(560, 480)

        tv = Adw.ToolbarView()
        hdr = Adw.HeaderBar()
        tv.add_top_bar(hdr)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Instructions
        instr = Gtk.Label(
            label="Type one line per entry. Prefix with L: for Leader, P: for People.\n"
                  "Lines without prefix alternate Leader / People."
        )
        instr.add_css_class("caption"); instr.add_css_class("dim-label")
        instr.set_wrap(True); instr.set_xalign(0)
        instr.set_margin_start(16); instr.set_margin_end(16)
        instr.set_margin_top(12); instr.set_margin_bottom(8)
        outer.append(instr)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        scroll.set_margin_start(16); scroll.set_margin_end(16); scroll.set_margin_bottom(8)
        editor = Gtk.TextView(); editor.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        editor.add_css_class("card"); editor.set_monospace(True)
        editor.set_top_margin(8); editor.set_bottom_margin(8)
        editor.set_left_margin(10); editor.set_right_margin(10)
        buf = editor.get_buffer()
        buf.set_text(
            "L: The Lord is my shepherd;\n"
            "P: I shall not want.\n"
            "L: He makes me lie down in green pastures;\n"
            "P: He leads me beside still waters.", -1
        )
        scroll.set_child(editor); outer.append(scroll)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_margin_start(16); btn_row.set_margin_end(16); btn_row.set_margin_bottom(14)
        sp = Gtk.Box(); sp.set_hexpand(True); btn_row.append(sp)
        cancel_btn = Gtk.Button(label="Cancel"); cancel_btn.connect("clicked", lambda _: dlg.close())
        btn_row.append(cancel_btn)
        insert_btn = Gtk.Button(label="Insert as LaTeX"); insert_btn.add_css_class("suggested-action")

        def on_insert(_b):
            s, e = buf.get_bounds()
            raw = buf.get_text(s, e, False)
            latex = self._build_responsive_latex(raw)
            self._on_bible_insert(latex)
            dlg.close()

        insert_btn.connect("clicked", on_insert); btn_row.append(insert_btn)
        outer.append(btn_row)
        tv.set_content(outer); dlg.set_content(tv); dlg.present()

    def _build_responsive_latex(self, raw: str) -> str:
        """Convert L: / P: annotated text to LaTeX verse environment."""
        lines = raw.strip().splitlines()
        latex_lines = [
            "% Responsive reading",
            "\\begin{verse}",
        ]
        auto_leader = True  # alternating mode when no prefix
        for line in lines:
            line = line.strip()
            if not line: continue
            if line.lower().startswith("l:"):
                text = _latex_escape(line[2:].strip())
                latex_lines.append(f"\\textbf{{Leader:}} {text}\\\\")
                auto_leader = False
            elif line.lower().startswith("p:"):
                text = _latex_escape(line[2:].strip())
                latex_lines.append(f"\\textit{{People:}} {text}\\\\")
                auto_leader = True
            else:
                text = _latex_escape(line)
                if auto_leader:
                    latex_lines.append(f"\\textbf{{Leader:}} {text}\\\\")
                else:
                    latex_lines.append(f"\\textit{{People:}} {text}\\\\")
                auto_leader = not auto_leader
        latex_lines.append("\\end{verse}")
        return "\n".join(latex_lines)

    # ── Snippets ──────────────────────────────────────────────────────────────

    def open_snippets(self):
        if not _SNIP_OK:
            self._error("Snippets unavailable", "snippets.py not found.")
            return
        snippets = load_snippets()
        if not snippets:
            self._error("No snippets", "No snippets saved yet. Add them in Preferences → Snippets.")
            return

        dlg = Adw.Window(transient_for=self, modal=True)
        dlg.set_title("Insert Snippet"); dlg.set_default_size(440, 400)
        tv = Adw.ToolbarView(); hdr = Adw.HeaderBar(); tv.add_top_bar(hdr)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True); scroll.set_margin_start(16); scroll.set_margin_end(16)
        scroll.set_margin_top(12); scroll.set_margin_bottom(12)
        lb = Gtk.ListBox(); lb.set_selection_mode(Gtk.SelectionMode.SINGLE)
        lb.add_css_class("boxed-list")

        for snip in snippets:
            row = Adw.ActionRow(title=snip["name"])
            preview = snip["content"].replace("\n", " ")[:60] + ("…" if len(snip["content"]) > 60 else "")
            row.set_subtitle(preview); row.set_activatable(True)
            row._snip_content = snip["content"]
            lb.append(row)

        def on_activated(_lb, row):
            self._on_bible_insert(row._snip_content)
            dlg.close()

        lb.connect("row-activated", on_activated)
        scroll.set_child(lb); outer.append(scroll)
        tv.set_content(outer); dlg.set_content(tv); dlg.present()

    # ── CSV export ────────────────────────────────────────────────────────────

    def export_csv(self):
        if self.current_file:
            default = Path(self.current_file).stem + ".csv"
            folder  = str(Path(self.current_file).parent)
        else:
            default = "service.csv"; folder = config.last_dir
        dlg = Gtk.FileDialog(title="Export CSV", initial_name=default)
        dlg.set_initial_folder(Gio.File.new_for_path(folder))
        filters = Gio.ListStore.new(Gtk.FileFilter)
        f = Gtk.FileFilter(); f.set_name("CSV files (*.csv)"); f.add_pattern("*.csv")
        filters.append(f); dlg.set_filters(filters)
        dlg.save(self, None, self._on_export_csv_response)

    def _on_export_csv_response(self, dlg, result):
        try: f = dlg.save_finish(result)
        except GLib.Error: return
        import csv
        path = f.get_path()
        if not path.endswith(".csv"): path += ".csv"

        # Build rows with current section divider context
        rows = []
        current_section = ""
        for entry in self.service_entries:
            if entry.is_divider:
                current_section = entry.title
            else:
                # Detect hymn ref: first line of note that matches VU/MV/LUS pattern
                hymn_ref = ""
                if entry.note:
                    m = re.match(r'^(VU|MV|LUS)\s+\d+[^$]*', entry.note.split('\n')[0])
                    if m: hymn_ref = m.group(0)[:40]
                # Note preview: first line, not the hymn ref, stripped of LaTeX
                note_preview = ""
                if entry.note:
                    first = entry.note.split('\n')[0]
                    if not first.startswith(("VU ","MV ","LUS ")):
                        first = re.sub(r'\\[a-zA-Z]+\*?\{([^}]*)\}', r'\1', first)
                        first = re.sub(r'\\[a-zA-Z]+\*?\s*', '', first).strip()
                        note_preview = first[:60]
                rows.append([current_section, entry.name, entry.leader, hymn_ref, note_preview])

        try:
            with open(path, "w", newline="", encoding="utf-8") as fp:
                writer = csv.writer(fp)
                writer.writerow(["Section", "Element", "Leader", "Hymn", "Notes preview"])
                writer.writerows(rows)
        except Exception as e:
            self._error("CSV export error", str(e))

    # ── Git / GitHub integration ──────────────────────────────────────────────

    def git_push(self):
        repo = config.github_repo
        if not repo:
            self._show_toast("Set up a GitHub repository in Preferences → GitHub first.", timeout=6)
            return

        if self.current_file:
            self.save_file()

        from datetime import date as _date
        title    = self.service_title_entry.get_text() or "service"
        date_str = self.selected_date.strftime("%-d %B %Y") if self.selected_date else \
                   _date.today().strftime("%-d %B %Y")
        msg = f"Service: {title} – {date_str}"

        push_toast = Adw.Toast.new("Pushing to GitHub…")
        push_toast.set_timeout(0)
        self._toast_overlay.add_toast(push_toast)
        self.push_btn.set_sensitive(False)

        def run():
            def abort(heading, body=""):
                push_toast.dismiss()
                self.push_btn.set_sensitive(True)
                if body:
                    self._error(heading, body)
                else:
                    self._show_toast(heading, timeout=6)

            try:
                add_r = subprocess.run(["git", "-C", repo, "add", "-A"],
                                       capture_output=True, text=True, timeout=10)
                if add_r.returncode != 0:
                    GLib.idle_add(abort, "Push failed",
                                  add_r.stderr.strip() or "git add failed")
                    return

                status_r = subprocess.run(["git", "-C", repo, "status", "--porcelain"],
                                          capture_output=True, text=True, timeout=5)
                if status_r.stdout.strip():
                    commit_r = subprocess.run(["git", "-C", repo, "commit", "-m", msg],
                                              capture_output=True, text=True, timeout=15)
                    if commit_r.returncode != 0:
                        out = (commit_r.stderr or commit_r.stdout or "").strip()
                        GLib.idle_add(abort, "Push failed (commit)", out)
                        return

                push_r = subprocess.run(["git", "-C", repo, "push"],
                                        capture_output=True, text=True, timeout=30)
                if push_r.returncode != 0:
                    err_low = (push_r.stderr or "").lower()
                    if "no upstream" in err_low or "set-upstream" in err_low or \
                       "set the upstream" in err_low:
                        push_r = subprocess.run(
                            ["git", "-C", repo, "push", "--set-upstream", "origin", "HEAD"],
                            capture_output=True, text=True, timeout=30
                        )

                def finish():
                    push_toast.dismiss()
                    self.push_btn.set_sensitive(True)
                    if push_r.returncode != 0:
                        err = (push_r.stderr or push_r.stdout or "Unknown error").strip()
                        if "Repository not found" in err:
                            self._error("Push failed",
                                "Repository not found on GitHub.\n\n"
                                "Check the URL in Preferences → GitHub.")
                        elif "Permission denied" in err or "Authentication failed" in err:
                            self._error("Push failed",
                                "Authentication failed.\n\n"
                                "Make sure you have SSH keys set up, or use a GitHub\n"
                                "personal access token.\n\nSee: github.com/settings/keys")
                        else:
                            self._error("Push failed", err[:400])
                    else:
                        self._show_toast("✓ Pushed to GitHub", timeout=4)

                GLib.idle_add(finish)

            except subprocess.TimeoutExpired:
                GLib.idle_add(abort, "Push timed out — check your network connection.")
            except FileNotFoundError:
                GLib.idle_add(abort, "git not found", "Install git: sudo zypper install git")
            except Exception as e:
                GLib.idle_add(abort, "Push error", str(e))

        threading.Thread(target=run, daemon=True).start()

    def git_pull(self):
        repo = config.github_repo
        if not repo:
            self._show_toast("Set up a GitHub repository in Preferences → GitHub first.", timeout=6)
            return

        pull_toast = Adw.Toast.new("Pulling from GitHub…")
        pull_toast.set_timeout(0)
        self._toast_overlay.add_toast(pull_toast)

        def run():
            try:
                r = subprocess.run(["git", "-C", repo, "pull"],
                                   capture_output=True, text=True, timeout=60)
                def on_done():
                    pull_toast.dismiss()
                    if r.returncode != 0:
                        err = (r.stderr or r.stdout or "Unknown error").strip()
                        self._error("Pull failed", err[:400])
                    else:
                        out = r.stdout.strip() or "Already up to date."
                        self._show_toast(f"✓ {out[:80]}", timeout=5)
                GLib.idle_add(on_done)
            except subprocess.TimeoutExpired:
                def _on_timeout():
                    pull_toast.dismiss()
                    self._show_toast("Pull timed out.", timeout=6)
                GLib.idle_add(_on_timeout)
            except FileNotFoundError:
                def _on_no_git():
                    pull_toast.dismiss()
                    self._error("git not found", "Install git: sudo zypper install git")
                GLib.idle_add(_on_no_git)
            except Exception as e:
                def _on_pull_err(msg=str(e)):
                    pull_toast.dismiss()
                    self._error("Pull error", msg)
                GLib.idle_add(_on_pull_err)

        threading.Thread(target=run, daemon=True).start()


    def _show_toast(self, message: str, timeout: int = 3):
        """Show a brief toast notification at the bottom of the window."""
        toast = Adw.Toast.new(message)
        toast.set_timeout(timeout)
        self._toast_overlay.add_toast(toast)

    # ── Preferences ───────────────────────────────────────────────────────────

    def _show_doc(self, which: str):
        """Show HELP, FAQ, or CHANGELOG in a scrollable popup with basic formatting."""
        titles    = {"HELP": "Rubric — Help",
                     "FAQ":  "Rubric — FAQ",
                     "CHANGELOG": "What's New"}
        filenames = {"HELP": "HELP.md", "FAQ": "FAQ.md", "CHANGELOG": "CHANGELOG.md"}

        app_dir  = Path(__file__).parent
        doc_path = app_dir / filenames.get(which, "HELP.md")
        if not doc_path.exists():
            self._error("File not found", str(doc_path)); return

        win = Adw.Window(transient_for=self, modal=False)
        win.set_title(titles.get(which, "Help")); win.set_default_size(700, 580)
        tv = Adw.ToolbarView(); hdr = Adw.HeaderBar(); tv.add_top_bar(hdr)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)

        text_view = Gtk.TextView()
        text_view.set_editable(False); text_view.set_cursor_visible(False)
        text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        text_view.set_top_margin(16); text_view.set_bottom_margin(16)
        text_view.set_left_margin(20); text_view.set_right_margin(20)

        buf = text_view.get_buffer()

        # Define tags
        h1 = buf.create_tag("h1", weight=700, scale=1.4, pixels_above_lines=12, pixels_below_lines=4)
        h2 = buf.create_tag("h2", weight=700, scale=1.15, pixels_above_lines=10, pixels_below_lines=2)
        h3 = buf.create_tag("h3", weight=700, scale=1.0,  pixels_above_lines=8,  pixels_below_lines=2)
        buf.create_tag("bold",    weight=700)
        buf.create_tag("code",    family="monospace", background="#f0f0f0")
        buf.create_tag("hr",      strikethrough=True, foreground="#888888")
        buf.create_tag("bullet",  left_margin=24)

        lines = doc_path.read_text(encoding="utf-8").splitlines()
        it = buf.get_end_iter()

        in_code_block = False
        for raw in lines:
            line = raw.rstrip()

            # Fenced code block
            if line.startswith("```"):
                in_code_block = not in_code_block
                buf.insert(it, "\n")
                continue

            if in_code_block:
                buf.insert_with_tags_by_name(it, line + "\n", "code")
                continue

            # Horizontal rule
            if re.match(r'^---+$', line):
                buf.insert_with_tags_by_name(it, "─" * 40 + "\n", "hr")
                continue

            # Headings
            m = re.match(r'^(#{1,3})\s+(.*)', line)
            if m:
                level = len(m.group(1)); text = m.group(2)
                tag = ["h1","h2","h3"][min(level-1, 2)]
                buf.insert_with_tags_by_name(it, text + "\n", tag)
                continue

            # Bullet points
            m = re.match(r'^[-*]\s+(.*)', line)
            if m:
                buf.insert_with_tags_by_name(it, "  • " + m.group(1) + "\n", "bullet")
                continue

            # Table separator rows (|---|---|) — skip
            if re.match(r'^\|[-| :]+\|$', line):
                continue
            # Table rows — render as monospaced
            if line.startswith("|"):
                buf.insert_with_tags_by_name(it, line + "\n", "code")
                continue

            # Blank line
            if not line:
                buf.insert(it, "\n"); continue

            # Inline: process **bold** and `code` spans
            parts = re.split(r'(\*\*[^*]+\*\*|`[^`]+`)', line)
            for part in parts:
                if part.startswith("**") and part.endswith("**"):
                    buf.insert_with_tags_by_name(it, part[2:-2], "bold")
                elif part.startswith("`") and part.endswith("`"):
                    buf.insert_with_tags_by_name(it, part[1:-1], "code")
                else:
                    buf.insert(it, part)
            buf.insert(it, "\n")

        scroll.set_child(text_view)
        tv.set_content(scroll)
        win.set_content(tv)
        win.present()

    def show_about(self):
        about = Adw.AboutWindow(transient_for=self)
        about.set_application_name("Rubric")
        about.set_application_icon("io.github.calstfrancis.rubric")
        about.set_version(APP_VERSION)
        about.set_comments("Worship service planning with RCL integration\nfor United Church of Canada ministry.")
        about.set_developers(["Cal St Francis https://calstfrancis.github.io"])
        about.set_license_type(Gtk.License.GPL_3_0)
        about.set_website("https://github.com/calstfrancis/rubric")
        about.set_issue_url("https://github.com/calstfrancis/rubric/issues")
        about.present()

    def export_as(self):
        simple = config.simple_mode
        dlg = Adw.MessageDialog(
            transient_for=self,
            heading="Export as…",
            body="Choose a format to export to:"
        )
        dlg.add_response("cancel",   "Cancel")
        dlg.add_response("html",     "HTML  (print from browser)")
        dlg.add_response("bulletin", "Bulletin")
        if not simple:
            dlg.add_response("latex", "LaTeX")
            dlg.add_response("text",  "Plain text")
            dlg.add_response("csv",   "CSV")
        dlg.set_response_appearance("html",     Adw.ResponseAppearance.SUGGESTED)
        dlg.set_response_appearance("bulletin", Adw.ResponseAppearance.SUGGESTED)
        def on_resp(d, r):
            if r == "html":     self.export_html()
            elif r == "bulletin": self.export_bulletin()
            elif r == "latex":  self.export_latex()
            elif r == "text":   self.export_text()
            elif r == "csv":    self.export_csv()
        dlg.connect("response", on_resp)
        dlg.present()

    def open_preferences(self):
        prefs = PreferencesWindow(transient_for=self, modal=True)
        def on_destroy(_):
            self._fill_palette_inner(); self._apply_tab_mode()
        prefs.connect("destroy", on_destroy); prefs.present()

    def _error(self, heading, body):
        dlg = Adw.MessageDialog(transient_for=self, heading=heading, body=body)
        dlg.add_response("ok","OK"); dlg.present()

    def do_close_request(self):
        if not self.modified: return False
        dlg = Adw.MessageDialog(transient_for=self, heading="Save before closing?", body="Your service has unsaved changes.")
        dlg.add_response("discard","Discard"); dlg.add_response("cancel","Cancel"); dlg.add_response("save","Save")
        dlg.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
        dlg.set_response_appearance("discard", Adw.ResponseAppearance.DESTRUCTIVE); dlg.set_default_response("save")
        def on_resp(d,r):
            if r=="save":
                if self.current_file:
                    self.save_file(); self.destroy()
                else:
                    # save_file_as opens an async dialog; let _write do the destroy
                    self._close_after_save = True
                    self.save_file_as()
            elif r=="discard": self.destroy()
        dlg.connect("response", on_resp); dlg.present(); return True

    def open_planner(self):
        folder = self._repo_subdir("liturgy")
        if not folder:
            dlg = Gtk.FileDialog(title="Choose folder containing .liturgy files")
            def on_chosen(d, r):
                try:
                    f = d.select_folder_finish(r)
                    PlannerWindow(folder=Path(f.get_path()), main_window=self, transient_for=self).present()
                except GLib.Error:
                    pass
            dlg.select_folder(self, None, on_chosen)
        else:
            PlannerWindow(folder=folder, main_window=self, transient_for=self).present()

    def open_library(self):
        win = getattr(self, "_library_win", None)
        if win and win.get_visible():
            win.present(); return
        self._library_win = LibraryWindow(main_window=self, transient_for=self)
        self._library_win.present()

    def open_archive(self):
        win = getattr(self, "_archive_win", None)
        if win and win.get_visible():
            win.present(); return
        self._archive_win = ArchiveWindow(main_window=self, transient_for=self)
        self._archive_win.present()


# ── Service Planner ───────────────────────────────────────────────────────────

class PlannerWindow(Adw.Window):
    def __init__(self, folder: Path, main_window, **kw):
        super().__init__(**kw)
        self._folder = folder
        self._main = main_window
        self.set_title("Service Planner")
        self.set_default_size(560, 600)
        self.set_modal(False)

        tv = Adw.ToolbarView()
        hdr = Adw.HeaderBar()
        tv.add_top_bar(hdr)

        refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text="Refresh")
        refresh_btn.connect("clicked", lambda _: self._load())
        hdr.pack_end(refresh_btn)

        new_btn = Gtk.Button(label="New service…")
        new_btn.add_css_class("suggested-action")
        new_btn.connect("clicked", self._on_new)
        hdr.pack_start(new_btn)

        self._list = Gtk.ListBox()
        self._list.set_selection_mode(Gtk.SelectionMode.NONE)
        self._list.add_css_class("boxed-list")
        self._list.set_margin_start(16); self._list.set_margin_end(16)
        self._list.set_margin_top(16); self._list.set_margin_bottom(16)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_child(self._list)
        tv.set_content(scroll)
        self.set_content(tv)

        self._load()

    def _load(self):
        while True:
            child = self._list.get_first_child()
            if child is None: break
            self._list.remove(child)

        from datetime import date as _date
        import os
        today = _date.today()

        try:
            from rubric_package.db import (
                service_index_update, service_index_get_mtime,
                service_index_all, service_index_prune,
            )
            _db_index = True
        except ImportError:
            _db_index = False

        services = []
        on_disk: set[str] = set()
        try:
            for p in self._folder.glob("*.liturgy"):
                path_str = str(p)
                on_disk.add(path_str)
                try:
                    mtime = p.stat().st_mtime
                except OSError:
                    continue

                cached_mtime = service_index_get_mtime(path_str) if _db_index else None
                if _db_index and cached_mtime is not None and abs(cached_mtime - mtime) < 0.01:
                    # Cache hit — no need to read the file
                    continue

                # Cache miss: read the file and update the index
                try:
                    d = json.loads(p.read_text(encoding="utf-8"))
                    title = d.get("title", "") or p.stem
                    date_str = d.get("date", "")
                    item_count = len([i for i in d.get("items", []) if i.get("type") != "divider"])
                    if _db_index:
                        service_index_update(path_str, title, date_str, item_count, mtime)
                except Exception:
                    pass
        except Exception:
            pass

        # Build service list from the index (covers both hits and newly updated entries)
        if _db_index and on_disk:
            service_index_prune(on_disk)
            for row in service_index_all():
                if row["path"] not in on_disk:
                    continue
                p = Path(row["path"])
                date_str = row["date"]
                try:
                    svc_date = _date.fromisoformat(date_str) if date_str else None
                except ValueError:
                    svc_date = None
                services.append((svc_date, row["title"] or p.stem, row["item_count"], p))
        elif not _db_index:
            # Fallback: re-read all files without index
            try:
                for p in self._folder.glob("*.liturgy"):
                    try:
                        d = json.loads(p.read_text(encoding="utf-8"))
                        title = d.get("title", "") or p.stem
                        date_str = d.get("date", "")
                        item_count = len([i for i in d.get("items", []) if i.get("type") != "divider"])
                        try:
                            svc_date = _date.fromisoformat(date_str) if date_str else None
                        except ValueError:
                            svc_date = None
                        services.append((svc_date, title, item_count, p))
                    except Exception:
                        pass
            except Exception:
                pass

        upcoming = sorted([(d, t, c, p) for d, t, c, p in services if d and d >= today], key=lambda x: x[0])
        past = sorted([(d, t, c, p) for d, t, c, p in services if not d or d < today], key=lambda x: (x[0] or _date.min), reverse=True)

        if not services:
            row = Adw.ActionRow(title="No services found",
                subtitle=f"Save .liturgy files to {self._folder} to see them here")
            row.set_sensitive(False)
            self._list.append(row)
            return

        def add_separator(label):
            lbl = Gtk.Label(label=label)
            lbl.add_css_class("heading"); lbl.add_css_class("dim-label")
            lbl.set_xalign(0); lbl.set_margin_start(4)
            lbl.set_margin_top(12); lbl.set_margin_bottom(2)
            row = Gtk.ListBoxRow(); row.set_activatable(False)
            row.set_child(lbl); self._list.append(row)

        if upcoming:
            add_separator("Upcoming")
            for svc_date, title, count, path in upcoming:
                date_label = svc_date.strftime("%-d %B %Y") if svc_date else "No date"
                row = Adw.ActionRow(title=title, subtitle=f"{date_label}  ·  {count} elements")
                row.set_activatable(True)
                row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
                row.connect("activated", lambda _r, p=path: self._open(p))
                self._list.append(row)

        if past:
            add_separator("Past services")
            for svc_date, title, count, path in past:
                date_label = svc_date.strftime("%-d %B %Y") if svc_date else "No date"
                row = Adw.ActionRow(title=title, subtitle=f"{date_label}  ·  {count} elements")
                row.set_activatable(True)
                row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
                row.connect("activated", lambda _r, p=path: self._open(p))
                self._list.append(row)

    def _open(self, path: Path):
        self._main._confirm_discard(lambda p=path: self._main._load_file(str(p)))

    def _on_new(self, _btn):
        dlg = Adw.MessageDialog(transient_for=self,
            heading="New service",
            body="This will open a blank service in the main window.")
        dlg.add_response("cancel", "Cancel")
        dlg.add_response("new", "New service")
        dlg.set_response_appearance("new", Adw.ResponseAppearance.SUGGESTED)
        dlg.connect("response", lambda d, r: self._main.new_service() if r == "new" else None)
        dlg.present()


# ── Element Library ───────────────────────────────────────────────────────────

class LibraryWindow(Adw.Window):
    """Searchable library of every element from every saved service."""

    def __init__(self, main_window, **kw):
        super().__init__(title="Element Library", default_width=560, default_height=700, **kw)
        self._main = main_window
        self._search_text = ""
        self._expanded: set[str] = set()

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Header bar
        hdr = Adw.HeaderBar()
        hdr.set_show_end_title_buttons(True)
        self._search_entry = Gtk.SearchEntry()
        self._search_entry.set_placeholder_text("Search elements…")
        self._search_entry.set_hexpand(True)
        self._search_entry.connect("search-changed", self._on_search)
        hdr.set_title_widget(self._search_entry)
        box.append(hdr)

        # Insert button (shown when something is selected)
        self._insert_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._insert_bar.set_margin_start(12); self._insert_bar.set_margin_end(12)
        self._insert_bar.set_margin_top(6); self._insert_bar.set_margin_bottom(6)
        self._insert_bar.set_visible(False)
        self._insert_label = Gtk.Label()
        self._insert_label.set_hexpand(True); self._insert_label.set_xalign(0)
        self._insert_label.add_css_class("caption")
        self._insert_bar.append(self._insert_label)
        insert_btn = Gtk.Button(label="Insert into selected element")
        insert_btn.add_css_class("suggested-action")
        insert_btn.connect("clicked", self._on_insert)
        self._insert_bar.append(insert_btn)
        box.append(self._insert_bar)
        box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._list_box = Gtk.ListBox()
        self._list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._list_box.add_css_class("boxed-list")
        self._list_box.set_margin_start(12); self._list_box.set_margin_end(12)
        self._list_box.set_margin_top(8); self._list_box.set_margin_bottom(12)
        self._list_box.connect("row-selected", self._on_row_selected)
        scroll.set_child(self._list_box)
        box.append(scroll)

        self.set_content(box)
        self._selected_element: dict | None = None
        GLib.idle_add(self._populate)

    def _populate(self, *_):
        self._rebuild(self._search_text)
        return False

    def _on_search(self, entry):
        self._search_text = entry.get_text().strip()
        self._rebuild(self._search_text)

    def _rebuild(self, query: str):
        # Clear list
        while self._list_box.get_first_child():
            self._list_box.remove(self._list_box.get_first_child())
        self._selected_element = None
        self._insert_bar.set_visible(False)

        try:
            from rubric_package.db import element_search, element_services, element_for_service
        except ImportError:
            self._list_box.append(self._status_row("Database not available"))
            return

        if query:
            rows = element_search(query)
            if not rows:
                self._list_box.append(self._status_row("No matches found"))
                return
            for r in rows:
                self._list_box.append(self._element_row(r))
        else:
            services = element_services()
            if not services:
                self._list_box.append(self._status_row(
                    "No services indexed yet — save a service to add it to the library"))
                return
            for svc in services:
                self._list_box.append(self._service_header_row(svc))
                if svc["service_path"] in self._expanded:
                    for elem in element_for_service(svc["service_path"]):
                        self._list_box.append(self._element_row(elem, indented=True))

    def _service_header_row(self, svc: dict) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row._is_service = True
        row._service_path = svc["service_path"]
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_margin_start(12); box.set_margin_end(8)
        box.set_margin_top(8); box.set_margin_bottom(8)

        arrow = Gtk.Label(label="▶" if svc["service_path"] not in self._expanded else "▼")
        arrow.add_css_class("dim-label"); arrow.add_css_class("caption")
        box.append(arrow)

        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        info.set_hexpand(True)
        title_lbl = Gtk.Label(label=svc["service_title"] or Path(svc["service_path"]).stem)
        title_lbl.set_xalign(0); title_lbl.add_css_class("heading")
        info.append(title_lbl)
        sub = Gtk.Label(label=f'{svc["service_date"] or "no date"}  ·  {svc["n"]} elements')
        sub.set_xalign(0); sub.add_css_class("caption"); sub.add_css_class("dim-label")
        info.append(sub)
        box.append(info)

        row._arrow_lbl = arrow
        row.set_child(box)
        return row

    def _element_row(self, elem: dict, indented: bool = False) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row._is_service = False
        row._element = elem
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        ms = 28 if indented else 12
        box.set_margin_start(ms); box.set_margin_end(12)
        box.set_margin_top(6); box.set_margin_bottom(6)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        name_lbl = Gtk.Label(label=elem["name"])
        name_lbl.set_xalign(0); name_lbl.add_css_class("body")
        header.append(name_lbl)
        if elem.get("section"):
            sec_lbl = Gtk.Label(label=elem["section"])
            sec_lbl.add_css_class("caption"); sec_lbl.add_css_class("dim-label")
            header.append(sec_lbl)
        box.append(header)

        note = (elem.get("note") or "").strip()
        if note:
            preview = note[:120].replace("\n", " ") + ("…" if len(note) > 120 else "")
            note_lbl = Gtk.Label(label=preview)
            note_lbl.set_xalign(0); note_lbl.add_css_class("caption")
            note_lbl.set_wrap(True); note_lbl.set_lines(2); note_lbl.set_ellipsize(3)
            box.append(note_lbl)

        if not indented and elem.get("service_title"):
            svc_lbl = Gtk.Label(label=f'{elem["service_title"]}  ·  {elem["service_date"] or ""}')
            svc_lbl.set_xalign(0); svc_lbl.add_css_class("caption"); svc_lbl.add_css_class("dim-label")
            box.append(svc_lbl)

        row.set_child(box)
        return row

    def _status_row(self, msg: str) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow(); row._is_service = False; row._element = None
        lbl = Gtk.Label(label=msg)
        lbl.set_margin_top(16); lbl.set_margin_bottom(16)
        lbl.add_css_class("dim-label"); lbl.set_wrap(True)
        row.set_child(lbl); return row

    def _on_row_selected(self, _lb, row):
        if row is None:
            self._insert_bar.set_visible(False); return
        if getattr(row, "_is_service", False):
            # Toggle expand/collapse
            path = row._service_path
            if path in self._expanded:
                self._expanded.discard(path)
            else:
                self._expanded.add(path)
            GLib.idle_add(self._rebuild, self._search_text)
            return
        elem = getattr(row, "_element", None)
        if not elem or not (elem.get("note") or elem.get("bulletin_note")):
            self._insert_bar.set_visible(False); return
        self._selected_element = elem
        self._insert_label.set_label(f'"{elem["name"]}" · {len(elem.get("note",""))} chars')
        self._insert_bar.set_visible(True)

    def _on_insert(self, _btn):
        elem = self._selected_element
        if not elem:
            return
        note = elem.get("note") or elem.get("bulletin_note") or ""
        win = self._main
        # Find selected service item and set its note
        idx = win._selected_global_idx
        if idx < 0 or idx >= len(win.service_entries):
            self._show_toast("Select an element in the service order first")
            return
        entry = win.service_entries[idx]
        if not isinstance(entry, ServiceItem):
            self._show_toast("Select an element (not a section header)")
            return
        win._updating_note = True
        entry.note = note
        win.notes_view.get_buffer().set_text(note, -1)
        win._leader_tab_btn.set_active(True)
        win._updating_note = False
        win._mark_modified()
        self._show_toast(f'Inserted into “{entry.name}”')

    def _show_toast(self, msg: str):
        toast = Adw.Toast.new(msg); toast.set_timeout(3)
        # We don't have a toast overlay in this window, so use main window's
        try:
            self._main._toast_overlay.add_toast(toast)
        except Exception:
            pass


# ── Past Liturgies Archive ────────────────────────────────────────────────────

class ArchiveWindow(Adw.Window):
    """Full-service reader for past liturgies. Shows elements with complete notes."""

    def __init__(self, main_window, **kw):
        super().__init__(title="Past Liturgies", default_width=680, default_height=740, **kw)
        self._main = main_window
        self._expanded: set[str] = set()
        self._search_text = ""

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        hdr = Adw.HeaderBar()
        hdr.set_show_end_title_buttons(True)
        self._search_entry = Gtk.SearchEntry()
        self._search_entry.set_placeholder_text("Search past services…")
        self._search_entry.set_hexpand(True)
        self._search_entry.connect("search-changed", self._on_search)
        hdr.set_title_widget(self._search_entry)
        box.append(hdr)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._list_box = Gtk.ListBox()
        self._list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self._list_box.add_css_class("boxed-list")
        self._list_box.set_margin_start(12); self._list_box.set_margin_end(12)
        self._list_box.set_margin_top(8); self._list_box.set_margin_bottom(12)
        scroll.set_child(self._list_box)
        box.append(scroll)

        self.set_content(box)
        GLib.idle_add(self._populate)

    def _populate(self, *_):
        self._rebuild(self._search_text)
        return False

    def _on_search(self, entry):
        self._search_text = entry.get_text().strip().lower()
        self._rebuild(self._search_text)

    def _strip_latex(self, text: str) -> str:
        import re as _re
        text = _re.sub(r'\\begin\{scripture\}(.*?)\\end\{scripture\}',
            lambda m: _re.sub(r'\\sverse\{(\d+)\}\{([^}]*)\}', r'\1 \2 ', m.group(1).strip()),
            text, flags=_re.DOTALL)
        text = _re.sub(r'\\(?:textbf|textit|emph|small)\{([^}]*)\}', r'\1', text)
        text = _re.sub(r'\\(?:hspace|vspace)\*?\{[^}]*\}', '', text)
        text = _re.sub(r'\\[a-zA-Z]+\*?\{([^}]*)\}', r'\1', text)
        text = _re.sub(r'\\[a-zA-Z@]+\*?', '', text)
        text = _re.sub(r'\{|\}', '', text)
        text = _re.sub(r'%[^\n]*', '', text)
        return text.strip()

    def _rebuild(self, query: str):
        while self._list_box.get_first_child():
            self._list_box.remove(self._list_box.get_first_child())

        try:
            from rubric_package.db import element_services, element_for_service
        except ImportError:
            self._list_box.append(self._status_row("Database not available"))
            return

        services = element_services(limit=500)
        if not services:
            self._list_box.append(self._status_row(
                "No services in library yet — save a service to add it here"))
            return

        # Filter by query (match against service title, date, or element content)
        if query:
            filtered = []
            for svc in services:
                title = (svc.get("service_title") or "").lower()
                date = (svc.get("service_date") or "").lower()
                if query in title or query in date:
                    filtered.append(svc)
                else:
                    elems = element_for_service(svc["service_path"])
                    if any(query in (e.get("name","")).lower() or
                           query in (e.get("note","")).lower() or
                           query in (e.get("leader","")).lower()
                           for e in elems):
                        filtered.append(svc)
            services = filtered
            if not services:
                self._list_box.append(self._status_row("No matches found"))
                return

        for svc in services:
            self._list_box.append(self._service_row(svc))
            if svc["service_path"] in self._expanded:
                try:
                    from rubric_package.db import element_for_service as _efs
                    elems = _efs(svc["service_path"])
                except ImportError:
                    elems = []
                cur_section = ""
                for elem in elems:
                    if elem.get("section") and elem["section"] != cur_section:
                        cur_section = elem["section"]
                        self._list_box.append(self._section_label_row(cur_section))
                    self._list_box.append(self._element_row(elem))

    def _service_row(self, svc: dict) -> Gtk.ListBoxRow:
        path = svc["service_path"]
        is_open = path in self._expanded

        row = Gtk.ListBoxRow()
        row._is_service = True
        row._service_path = path
        row._svc = svc
        row.set_activatable(True)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header.set_margin_start(12); header.set_margin_end(8)
        header.set_margin_top(10); header.set_margin_bottom(10)

        arrow = Gtk.Label(label="▼" if is_open else "▶")
        arrow.add_css_class("caption"); arrow.add_css_class("dim-label")
        row._arrow_lbl = arrow
        header.append(arrow)

        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        info.set_hexpand(True)
        title = svc.get("service_title") or Path(path).stem
        title_lbl = Gtk.Label(label=title)
        title_lbl.set_xalign(0); title_lbl.add_css_class("heading")
        title_lbl.set_ellipsize(3); info.append(title_lbl)
        date_lbl = Gtk.Label(label=svc.get("service_date") or "No date")
        date_lbl.set_xalign(0); date_lbl.add_css_class("caption")
        date_lbl.add_css_class("dim-label"); info.append(date_lbl)
        header.append(info)

        open_btn = Gtk.Button(label="Open in editor")
        open_btn.add_css_class("flat"); open_btn.set_valign(Gtk.Align.CENTER)
        open_btn.connect("clicked", lambda _b, p=path: self._open_service(p))
        header.append(open_btn)

        outer.append(header)
        row.set_child(outer)

        def on_activate(_row, p=path, r=row):
            if p in self._expanded:
                self._expanded.discard(p)
            else:
                self._expanded.add(p)
            GLib.idle_add(self._rebuild, self._search_text)

        row.connect("activate", on_activate)
        return row

    def _section_label_row(self, section: str) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow(); row.set_activatable(False)
        lbl = Gtk.Label(label=section)
        lbl.set_xalign(0); lbl.add_css_class("caption")
        lbl.add_css_class("dim-label"); lbl.add_css_class("heading")
        lbl.set_margin_start(28); lbl.set_margin_end(12)
        lbl.set_margin_top(8); lbl.set_margin_bottom(2)
        row.set_child(lbl); return row

    def _element_row(self, elem: dict) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row.set_activatable(False)
        row._element = elem

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_start(28); box.set_margin_end(12)
        box.set_margin_top(6); box.set_margin_bottom(6)

        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        name_lbl = Gtk.Label(label=elem.get("name", ""))
        name_lbl.set_xalign(0); name_lbl.add_css_class("body")
        name_lbl.set_hexpand(True); top.append(name_lbl)
        if elem.get("leader"):
            ldr_lbl = Gtk.Label(label=elem["leader"])
            ldr_lbl.add_css_class("caption"); ldr_lbl.add_css_class("dim-label")
            top.append(ldr_lbl)

        note_raw = (elem.get("bulletin_note") or elem.get("note") or "").strip()
        if note_raw:
            insert_btn = Gtk.Button(label="Insert")
            insert_btn.add_css_class("flat"); insert_btn.set_valign(Gtk.Align.CENTER)
            insert_btn.connect("clicked", lambda _b, e=elem: self._on_insert(e))
            top.append(insert_btn)

        box.append(top)

        if note_raw:
            clean = self._strip_latex(note_raw)
            if clean:
                note_lbl = Gtk.Label(label=clean)
                note_lbl.set_xalign(0); note_lbl.set_wrap(True)
                note_lbl.add_css_class("caption"); note_lbl.set_selectable(True)
                box.append(note_lbl)

        row.set_child(box)
        return row

    def _status_row(self, msg: str) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow(); row.set_activatable(False)
        lbl = Gtk.Label(label=msg)
        lbl.set_margin_top(20); lbl.set_margin_bottom(20)
        lbl.add_css_class("dim-label"); lbl.set_wrap(True)
        row.set_child(lbl); return row

    def _open_service(self, path: str):
        self._main._confirm_discard(lambda p=path: self._main._load_file(p))

    def _on_insert(self, elem: dict):
        note = elem.get("note") or elem.get("bulletin_note") or ""
        win = self._main
        idx = win._selected_global_idx
        if idx < 0 or idx >= len(win.service_entries):
            self._show_toast("Select an element in the service order first")
            return
        entry = win.service_entries[idx]
        if not isinstance(entry, ServiceItem):
            self._show_toast("Select an element (not a section header)")
            return
        win._updating_note = True
        entry.note = note
        win.notes_view.get_buffer().set_text(note, -1)
        win._leader_tab_btn.set_active(True)
        win._updating_note = False
        win._mark_modified()
        self._show_toast(f'Inserted into "{entry.name}"')

    def _show_toast(self, msg: str):
        toast = Adw.Toast.new(msg); toast.set_timeout(3)
        try:
            self._main._toast_overlay.add_toast(toast)
        except Exception:
            pass


# ── Application ───────────────────────────────────────────────────────────────

class LiturgyPlannerApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="io.github.calstfrancis.rubric", flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.connect("activate", self._on_activate)

    def _on_activate(self, app):
        try:
            from rubric_package.db import init_db, migrate_from_json
            init_db()
            migrate_from_json()
        except Exception:
            pass
        MainWindow(application=app).present()

def main():
    GLib.set_prgname("rubric")
    GLib.set_application_name("Rubric")
    sys.exit(LiturgyPlannerApp().run(sys.argv))

if __name__ == "__main__":
    main()
