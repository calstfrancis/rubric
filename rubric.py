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
except ImportError:
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

APP_VERSION = "0.11"

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
                self.default_template = d.get("default_template", "")
                self.templates        = d.get("templates",        {})
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


def _passage_to_latex(reference: str, text: str) -> str:
    r"""
    Convert WEB verse text to LaTeX inside a {scripture} environment.
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
    body = "\n".join(latex_lines)
    return (
        f"% {ref_escaped} (WEB)\n"
        f"{{\\small\\textit{{{ref_escaped} (WEB)}}}}\n"
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
if _PACKAGE_OK:
    _entry_from_dict = entry_from_dict
    _latex_escape = latex_escape
    _note_for_latex = note_for_latex
    _passage_to_latex = passage_to_latex
    _migrate_scripture_note = migrate_scripture_note
    _section_colour = section_colour
    _hex_to_rgb = hex_to_rgb


# ── Bible viewer ──────────────────────────────────────────────────────────────

class BibleViewer(Adw.Window):
    def __init__(self, reference, on_insert_cb, **kw):
        super().__init__(**kw)
        self.set_title(f"{reference}  ·  WEB"); self.set_default_size(520,460); self.set_modal(True)
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
        attr = Gtk.Label(label="World English Bible (Public Domain)")
        attr.add_css_class("caption"); attr.add_css_class("dim-label")
        attr.set_hexpand(True); attr.set_xalign(0); self._bot.append(attr)
        ins = Gtk.Button(label="Insert as LaTeX"); ins.add_css_class("suggested-action")
        ins.connect("clicked", self._on_insert); self._bot.append(ins); outer.append(self._bot)
        tv.set_content(outer)
        if _BIBLE_OK: fetch_passage(reference, self._on_fetched)
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
            latex = _passage_to_latex(self._ref, self._text)
            self._on_insert_cb(latex)
        self.close()


# ── Preferences ───────────────────────────────────────────────────────────────

class PreferencesWindow(Adw.PreferencesWindow):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.set_title("Preferences"); self.set_default_size(700,560); self.set_search_enabled(False)
        self._build_latex(); self._build_view(); self._build_template(); self._build_palette()
        if _SNIP_OK: self._build_snippets()
        self._build_bulletin()
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
            # Older libadwaita fallback
            row = Adw.ActionRow(title="Tab view",
                                subtitle="Show sections as tabs instead of one long list")
            self._tabs_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
            self._tabs_switch.set_active(config.use_tabs)
            row.add_suffix(self._tabs_switch); row.set_activatable_widget(self._tabs_switch)
            grp.add(row); self._tabs_row = None

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
        widgets = (role_e, name_e, email_e, box)
        del_btn.connect("clicked", lambda _b, w=widgets: self._remove_staff_row(w))

        box.append(role_e); box.append(name_e); box.append(email_e); box.append(del_btn)
        row = Adw.ActionRow(); row.set_child(box)
        self._staff_grp.add(row)
        self._bul_staff_widgets.append((role_e, name_e, email_e, row))

    def _remove_staff_row(self, widgets):
        role_e, name_e, email_e, box = widgets
        self._bul_staff_widgets = [w for w in self._bul_staff_widgets if w[0] is not role_e]
        # Remove from group — mark as invisible (can't easily remove from PreferencesGroup)
        box.get_parent().set_visible(False)

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
        buf = self._preamble_view.get_buffer(); s,e = buf.get_bounds()
        config.preamble = buf.get_text(s,e,False)
        builtin = [{"section":s,"items":list(i)} for s,i in SECTIONS]
        config.palette = self._pal if self._pal != builtin else None
        config.use_tabs = self._tabs_active()

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

        config.save(); return False


# ── Main window ───────────────────────────────────────────────────────────────

class MainWindow(Adw.ApplicationWindow):
    def __init__(self, **kw):
        super().__init__(**kw); self.set_default_size(1000,700)
        self.service_entries: list = []
        self._undo_stack: list[list[dict]] = []
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
            ("git-commit",         self.git_commit,             "<Ctrl><Shift>g"),
            ("show-help",          lambda: self._show_doc("HELP"),      "F1"),
            ("show-faq",           lambda: self._show_doc("FAQ"),       None),
            ("show-changelog",     lambda: self._show_doc("CHANGELOG"), None),
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
        menu = Gio.Menu()
        menu.append("Preferences",            "win.preferences")
        menu.append("Duplicate service",       "win.duplicate")
        menu.append("Save order as template…", "win.save-template")
        menu.append("Save as…",               "win.save-as")

        # Export submenu
        export_sec = Gio.Menu()
        export_sec.append("Export LaTeX…",      "win.export-latex")
        export_sec.append("Export plain text…", "win.export-text")
        export_sec.append("Export CSV…",        "win.export-csv")
        export_sec.append("Export Bulletin…",   "win.export-bulletin")
        menu.append_section("Export", export_sec)

        # menu.append("Commit to git", "win.git-commit")  # hidden until stable
        help_sec = Gio.Menu()
        help_sec.append("Help (F1)",   "win.show-help")
        help_sec.append("FAQ",         "win.show-faq")
        help_sec.append("What's New",  "win.show-changelog")
        menu.append_section("Help", help_sec)
        self._recent_sec = Gio.Menu(); menu.append_section("Recent files", self._recent_sec)
        self._rebuild_recent_menu()
        hdr.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic", tooltip_text="Menu", menu_model=menu))
        tv = Adw.ToolbarView(); tv.add_top_bar(hdr)
        self._toast_overlay = Adw.ToastOverlay()
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_shrink_start_child(False); paned.set_shrink_end_child(False); paned.set_position(290)
        paned.set_start_child(self._build_palette_panel())
        paned.set_end_child(self._build_order_panel())
        self._toast_overlay.set_child(paned)
        tv.set_content(self._toast_overlay)
        self.set_content(tv)

    # ── Palette panel ─────────────────────────────────────────────────────────

    def _build_palette_panel(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL); box.set_size_request(230,-1)
        scroll = Gtk.ScrolledWindow(); scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC); scroll.set_vexpand(True)
        self._palette_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._palette_inner.set_margin_top(8); self._palette_inner.set_margin_bottom(8)
        self._palette_listboxes: dict[str,Gtk.ListBox] = {}; self._fill_palette_inner()
        scroll.set_child(self._palette_inner); box.append(scroll)
        ab = Gtk.Button(label="Add to service ↓")
        ab.set_margin_start(14); ab.set_margin_end(14); ab.set_margin_top(8); ab.set_margin_bottom(12)
        ab.connect("clicked", lambda _: self._add_selected_palette_item()); box.append(ab)
        return box

    def _fill_palette_inner(self):
        while True:
            c = self._palette_inner.get_first_child()
            if c is None: break
            self._palette_inner.remove(c)
        self._palette_listboxes.clear()
        for sname, items in get_palette():
            lbl = Gtk.Label(label=sname); lbl.add_css_class("heading"); lbl.set_xalign(0)
            lbl.set_margin_start(14); lbl.set_margin_end(14); lbl.set_margin_top(14); lbl.set_margin_bottom(4)
            self._palette_inner.append(lbl)
            lb = Gtk.ListBox(); lb.set_selection_mode(Gtk.SelectionMode.SINGLE)
            lb.add_css_class("boxed-list"); lb.set_margin_start(14); lb.set_margin_end(14); lb.set_margin_bottom(4)
            lb.connect("row-activated", self._on_palette_row_activated)
            for iname in items:
                row = Adw.ActionRow(title=iname); row.set_activatable(True)
                row._item_name=iname; row._section_name=sname; lb.append(row)
            self._palette_inner.append(lb); self._palette_listboxes[sname] = lb

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

        # ── View stack (list / tabs) — upper pane ─────────────────────────────
        upper = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

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
        upper.append(self._view_stack)

        # Button bar
        bb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        bb.set_margin_start(12); bb.set_margin_end(12); bb.set_margin_top(4); bb.set_margin_bottom(8)
        for icon,tip,cb in [("go-up-symbolic","Move up (Ctrl+↑)",self.move_up),
                             ("go-down-symbolic","Move down (Ctrl+↓)",self.move_down)]:
            b = Gtk.Button(icon_name=icon, tooltip_text=tip); b.connect("clicked", lambda _,f=cb: f()); bb.append(b)
        rm = Gtk.Button(icon_name="list-remove-symbolic", tooltip_text="Remove selected (Delete)")
        rm.add_css_class("destructive-action"); rm.connect("clicked", lambda _: self.remove_item()); bb.append(rm)
        sp = Gtk.Box(); sp.set_hexpand(True); bb.append(sp)
        for label,tip,cb in [("＋ Divider","Add section divider (Ctrl+D)",self.add_divider),
                              ("＋ Custom…","Add custom element (Ctrl+Shift+N)",self.add_custom)]:
            b = Gtk.Button(label=label, tooltip_text=tip); b.connect("clicked", lambda _,f=cb: f()); bb.append(b)
        upper.append(bb)

        # Hymn suggestions strip (revealed when a date is set)
        self.sugg_revealer = Gtk.Revealer()
        self.sugg_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self.sugg_revealer.set_transition_duration(200)
        sugg_outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        sugg_outer.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        self._sugg_chips_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self._sugg_chips_box.set_margin_start(10); self._sugg_chips_box.set_margin_end(10)
        self._sugg_chips_box.set_margin_bottom(6); self._sugg_chips_box.set_margin_top(6)
        sugg_scroll = Gtk.ScrolledWindow()
        sugg_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        sugg_scroll.set_min_content_height(36)
        sugg_scroll.set_child(self._sugg_chips_box)
        sugg_outer.append(sugg_scroll)
        self.sugg_revealer.set_child(sugg_outer)
        upper.append(self.sugg_revealer)

        # ── Lower pane: combined toolbar + notes ──────────────────────────────
        lower = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        lower.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # ── Combined single-line item toolbar (revealed when item is selected) ─
        # Layout: Leader: [entry] | Scripture: [entry] [🔍] | Hymn: [entry] [Look up] [status]
        self.item_toolbar_revealer = Gtk.Revealer()
        self.item_toolbar_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self.item_toolbar_revealer.set_transition_duration(150)

        itb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        itb.set_margin_start(12); itb.set_margin_end(12)
        itb.set_margin_top(6); itb.set_margin_bottom(6)

        # Leader segment
        ll = Gtk.Label(label="Leader:"); ll.add_css_class("dim-label")
        ll.set_margin_end(4); itb.append(ll)
        self.leader_entry = Gtk.Entry()
        self.leader_entry.set_placeholder_text("Name or role")
        self.leader_entry.set_width_chars(12)
        self.leader_entry.connect("changed", self._on_leader_changed)
        itb.append(self.leader_entry)

        sep1 = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        sep1.set_margin_start(8); sep1.set_margin_end(8); itb.append(sep1)

        # Scripture segment
        sl = Gtk.Label(label="Scripture:"); sl.add_css_class("dim-label")
        sl.set_margin_end(4); itb.append(sl)
        self.scripture_entry = Gtk.Entry()
        self.scripture_entry.set_placeholder_text("e.g. Ps 23")
        self.scripture_entry.set_width_chars(12)
        self.scripture_entry.connect("activate", lambda _: self._do_scripture_search())
        itb.append(self.scripture_entry)
        ss_fetch = Gtk.Button(icon_name="system-search-symbolic", tooltip_text="Fetch passage")
        ss_fetch.add_css_class("flat"); ss_fetch.set_margin_start(2)
        ss_fetch.connect("clicked", lambda _: self._do_scripture_search())
        itb.append(ss_fetch)

        # Hymn segment (only shown for hymn-type elements — controlled via opacity/sensitive)
        sep2 = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        sep2.set_margin_start(8); sep2.set_margin_end(8); itb.append(sep2)
        hl = Gtk.Label(label="Hymn #:"); hl.add_css_class("dim-label")
        hl.set_margin_end(4); itb.append(hl)
        self.hymn_entry = Gtk.Entry()
        self.hymn_entry.set_placeholder_text("VU 16 / MV 120")
        self.hymn_entry.set_width_chars(10)
        self.hymn_entry.connect("activate", lambda _: self._do_hymn_lookup())
        itb.append(self.hymn_entry)
        hlb = Gtk.Button(label="↵", tooltip_text="Look up hymn")
        hlb.add_css_class("flat"); hlb.set_margin_start(2)
        hlb.connect("clicked", lambda _: self._do_hymn_lookup()); itb.append(hlb)
        self.hymn_status = Gtk.Label(); self.hymn_status.add_css_class("dim-label")
        self.hymn_status.set_max_width_chars(18); self.hymn_status.set_ellipsize(3)
        self.hymn_status.set_margin_start(4)
        # Store refs to hymn segment widgets to show/hide them
        self._hymn_toolbar_widgets = [sep2, hl, self.hymn_entry, hlb, self.hymn_status]
        itb.append(self.hymn_status)

        # Snippets and Responsive reading — right end of toolbar
        sep3 = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        sep3.set_margin_start(8); sep3.set_margin_end(4); itb.append(sep3)
        snip_btn = Gtk.Button(label="✂", tooltip_text="Insert snippet (Ctrl+Shift+I)")
        snip_btn.add_css_class("flat"); snip_btn.set_margin_end(2)
        snip_btn.connect("clicked", lambda _: self.open_snippets()); itb.append(snip_btn)
        rr_btn = Gtk.Button(label="℟", tooltip_text="Responsive reading builder (Ctrl+R)")
        rr_btn.add_css_class("flat")
        rr_btn.connect("clicked", lambda _: self.open_responsive_reading()); itb.append(rr_btn)

        # Bulletin separator + toggle
        sep4 = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        sep4.set_margin_start(8); sep4.set_margin_end(4); itb.append(sep4)
        self.bulletin_toggle = Gtk.ToggleButton(label="📋")
        self.bulletin_toggle.set_tooltip_text("Include in congregational bulletin")
        self.bulletin_toggle.add_css_class("flat")
        self.bulletin_toggle.set_active(True)
        self.bulletin_toggle.connect("toggled", self._on_bulletin_toggled)
        itb.append(self.bulletin_toggle)

        self.item_toolbar_revealer.set_child(itb)
        lower.append(self.item_toolbar_revealer)
        self.hymn_revealer = self.item_toolbar_revealer
        self.leader_revealer = self.item_toolbar_revealer

        # Notes text view — fills the lower pane
        ns = Gtk.ScrolledWindow()
        ns.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        ns.set_vexpand(True)
        ns.set_margin_start(12); ns.set_margin_end(12); ns.set_margin_bottom(10)
        self.notes_view = Gtk.TextView(); self.notes_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.notes_view.add_css_class("card")
        self.notes_view.set_top_margin(8); self.notes_view.set_bottom_margin(8)
        self.notes_view.set_left_margin(10); self.notes_view.set_right_margin(10)
        self.notes_view.set_sensitive(False)
        self.notes_view.get_buffer().connect("changed", self._on_notes_changed)
        ns.set_child(self.notes_view); lower.append(ns)

        # ── Vertical Paned: upper=list, lower=notes ───────────────────────────
        vpaned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        vpaned.set_shrink_start_child(False)
        vpaned.set_shrink_end_child(False)
        vpaned.set_resize_start_child(True)
        vpaned.set_resize_end_child(False)
        vpaned.set_position(380)   # default split — list gets most space
        vpaned.set_start_child(upper)
        vpaned.set_end_child(lower)
        vpaned.set_vexpand(True)
        box.append(vpaned)

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
        if row and hasattr(row,"_entry") and isinstance(row._entry, ServiceItem):
            si = row._entry
            try: self._selected_global_idx = self.service_entries.index(si)
            except ValueError: self._selected_global_idx = -1
            buf.set_text(si.note, -1); self.notes_view.set_sensitive(True)
            # Show the combined toolbar
            self.item_toolbar_revealer.set_reveal_child(True)
            self.leader_entry.set_text(si.leader)
            # Bulletin toggle — set state without triggering handler
            self._updating_note = True
            self.bulletin_toggle.set_active(si.show_in_bulletin)
            self._updating_note = False
            # Show/hide hymn segment based on element type
            is_hymn = _HYMN_OK and _is_hymn_element(si.name)
            for w in self._hymn_toolbar_widgets: w.set_visible(is_hymn)
            if is_hymn: self.hymn_status.set_label(""); self.hymn_entry.set_text("")
        else:
            self._selected_global_idx = -1
            buf.set_text("", -1); self.notes_view.set_sensitive(False)
            self.item_toolbar_revealer.set_reveal_child(False)
            self.leader_entry.set_text("")
        self._updating_note = False

    # ── Palette actions ───────────────────────────────────────────────────────

    def _on_palette_row_activated(self, _lb, row): self._push_undo(); self._add_entry(ServiceItem(row._item_name, row._section_name))
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

    def undo(self):
        if not self._undo_stack: return
        self.service_entries = [_entry_from_dict(d) for d in self._undo_stack.pop()]
        self._refresh_order_list(); self.undo_btn.set_sensitive(bool(self._undo_stack)); self._mark_modified()

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
            row = self.order_listbox.get_row_at_index(idx) if not config.use_tabs else None
            if isinstance(row, Adw.ActionRow): row.set_subtitle(self._note_preview(entry.note))
            self._mark_modified()
        lookup_hymn(prefix, number, on_result)

    # ── Bible viewer ──────────────────────────────────────────────────────────

    def _on_reading_clicked(self, key):
        ref = self._current_readings.get(key,"")
        if not ref or ref=="—": return
        BibleViewer(ref, self._on_bible_insert, transient_for=self).present()

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
        # Update subtitle preview on the active row
        row = self.order_listbox.get_row_at_index(idx) if not config.use_tabs else None
        if isinstance(row, Adw.ActionRow):
            row.set_subtitle(self._note_preview(entry.note))
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

    def _step_sunday(self, direction: int):
        """Move the readings display to the prev (-1) or next (+1) Sunday."""
        from datetime import timedelta
        if self._readings_sunday is None: return
        new_sun = self._readings_sunday + timedelta(weeks=direction)
        self._update_readings(self.selected_date, override_sunday=new_sun)

    # ── State ─────────────────────────────────────────────────────────────────

    def _mark_modified(self): self.modified=True; self._update_title()

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
        if config.last_seen_version != APP_VERSION:
            self._show_welcome(is_new_version=bool(config.last_seen_version))
        return False

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
        self.service_title_entry.set_text(""); self.notes_view.get_buffer().set_text("", -1)
        self._clear_order_list(); self.selected_date=None; self.date_button.set_label("No date selected")
        self.readings_card.set_visible(False); self._current_readings={}
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
            dlg.set_initial_folder(Gio.File.new_for_path(config.last_dir))
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
            self._update_title()
        except Exception as e: self._error("Error opening file",str(e))

    def save_file(self):
        if self.current_file: self._write(self.current_file)
        else: self.save_file_as()

    def save_file_as(self):
        dlg = Gtk.FileDialog(title="Save service", initial_name="service.liturgy")
        dlg.set_initial_folder(Gio.File.new_for_path(config.last_dir))
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
            with open(path,"w",encoding="utf-8") as f: json.dump(self._service_data(),f,indent=2,ensure_ascii=False)
            self.modified=False; self._update_title(); self._clear_autosave()
            config.last_dir=str(Path(path).parent); config.add_recent(path); config.save(); self._rebuild_recent_menu()
        except Exception as e: self._error("Error saving",str(e))

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
        """Export congregational bulletin — prompts for print or digital mode."""
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

    def _export_bulletin_file(self, digital: bool):
        title = self.service_title_entry.get_text() or "bulletin"
        date_str = self.selected_date.strftime("%Y-%m-%d") if self.selected_date else "undated"
        church = config.bulletin.get("church_name", "").replace(" ", "_") or "Bulletin"
        suffix = "digital" if digital else "print"
        default_name = f"{church}_{date_str}_{suffix}.tex"
        dlg = Gtk.FileDialog(title="Save bulletin as…", initial_name=default_name)
        dlg.set_initial_folder(Gio.File.new_for_path(config.last_dir))
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
        # Suggest a sensible default name derived from the .liturgy file or title
        if self.current_file:
            default = Path(self.current_file).stem + ".tex"
            folder  = str(Path(self.current_file).parent)
        else:
            title   = self.service_title_entry.get_text() or "service"
            default = title.replace(" ", "_").lower() + ".tex"
            folder  = config.last_dir
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
                # Update row subtitle preview
                row = self.order_listbox.get_row_at_index(idx) if not config.use_tabs else None
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
        BibleViewer(ref, self._on_bible_insert, transient_for=self).present()
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
            "\\textbf{Leader:}\\\\",
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

    # ── Git integration ───────────────────────────────────────────────────────

    def git_commit(self):
        if not self.current_file:
            self._error("Not saved", "Save the service file before committing to git.")
            return
        path = Path(self.current_file)
        repo_dir = str(path.parent)
        filename  = path.name
        title = self.service_title_entry.get_text() or filename
        date_str  = self.selected_date.strftime("%-d %B %Y") if self.selected_date else ""
        msg = f"Service: {title}" + (f" — {date_str}" if date_str else "")

        try:
            # Find the actual git repo root
            root_result = subprocess.run(
                ["git", "-C", repo_dir, "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, timeout=5
            )
            if root_result.returncode != 0:
                self._error("Not a git repository",
                            f"{repo_dir} is not inside a git repository.\n\n"
                            "Run 'git init' in that directory first.")
                return

            repo_root = root_result.stdout.strip()

            # Show confirmation dialog with repo location before committing
            dlg = Adw.MessageDialog(
                transient_for=self,
                heading="Commit to git?",
                body=f"Repository: {repo_root}\n\nCommit message:\n{msg}"
            )
            dlg.add_response("cancel", "Cancel")
            dlg.add_response("commit", "Commit")
            dlg.set_response_appearance("commit", Adw.ResponseAppearance.SUGGESTED)
            dlg.set_default_response("commit")

            def on_resp(d, r):
                if r != "commit":
                    return
                try:
                    # Use absolute paths for git add — works regardless of repo root depth
                    add = subprocess.run(
                        ["git", "add", str(path.resolve())],
                        capture_output=True, text=True, timeout=10
                    )
                    if add.returncode != 0:
                        self._error("git add failed", add.stderr.strip()); return
                    if self.tex_file:
                        subprocess.run(
                            ["git", "add", str(Path(self.tex_file).resolve())],
                            capture_output=True, text=True, timeout=10
                        )
                    commit = subprocess.run(
                        ["git", "-C", repo_root, "commit", "-m", msg],
                        capture_output=True, text=True, timeout=15
                    )
                    if commit.returncode != 0:
                        out = commit.stdout.strip() + commit.stderr.strip()
                        if "nothing to commit" in out:
                            self._show_toast("Nothing new to commit.")
                        else:
                            self._error("git commit failed", out)
                        return
                    short = commit.stdout.strip().splitlines()[0] if commit.stdout else "Committed."
                    self._show_toast(short)
                except Exception as e:
                    self._error("git error", str(e))

            dlg.connect("response", on_resp)
            dlg.present()

        except FileNotFoundError:
            self._error("git not found", "Install git: sudo zypper install git")
        except subprocess.TimeoutExpired:
            self._error("git timed out", "The git operation took too long.")
        except Exception as e:
            self._error("git error", str(e))


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
            if r=="save": self.save_file(); self.destroy()
            elif r=="discard": self.destroy()
        dlg.connect("response", on_resp); dlg.present(); return True


# ── Application ───────────────────────────────────────────────────────────────

class LiturgyPlannerApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="io.github.calstfrancis.rubric", flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.connect("activate", lambda app: MainWindow(application=app).present())

def main():
    GLib.set_prgname("rubric")
    GLib.set_application_name("Rubric")
    sys.exit(LiturgyPlannerApp().run(sys.argv))

if __name__ == "__main__":
    main()
