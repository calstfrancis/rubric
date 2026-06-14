#!/usr/bin/env python3
"""
Rubric — GTK4 + libadwaita worship service order builder
Requires: sudo zypper install python3-gobject typelib-1_0-Adw-1 typelib-1_0-Gtk-4_0
"""

import sys, json, re, subprocess, shutil, threading, os
from pathlib import Path

# When running inside a flatpak sandbox, delegate git to the host system.
_GIT = ["flatpak-spawn", "--host", "git"] if Path("/.flatpak-info").exists() else ["git"]

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib, GObject, Gdk, Pango

sys.path.insert(0, str(Path(__file__).parent))
from rcl_data import get_liturgical_info

# Import from refactored package
try:
    from rubric_package.models.config import Config, MAX_UNDO, AUTOSAVE_SECS, CONFIG_PATH, AUTOSAVE_PATH, SECTIONS
    from rubric_package.models.service import ServiceItem, SectionDivider, entry_from_dict
    from rubric_package.utils.typst import (
        typst_escape, note_for_typst, linebreak_fix, passage_to_typst,
        strip_typst_for_html, strip_typst_plain, strip_leader_notes, TYPST_SHARED,
        format_typst_error,
    )
    from rubric_package.utils.colors import section_colour, hex_to_rgb
    from rubric_package.utils.helpers import is_hymn_element, HYMN_KEYWORDS as _HYMN_KW
    from rubric_package.views.element_content import ElementContentWidget
except ImportError as _pkg_err:
    print(f"Fatal: rubric_package not found — {_pkg_err}", file=sys.stderr)
    sys.exit(1)

_typst_escape           = typst_escape
_note_for_typst         = note_for_typst
_passage_to_typst       = passage_to_typst
_section_colour         = section_colour
_hex_to_rgb             = hex_to_rgb
_is_hymn_element        = is_hymn_element
_entry_from_dict        = entry_from_dict

def _item_type_icon(name: str) -> str | None:
    n = name.lower()
    if any(w in n for w in ("hymn","song","anthem","music","prelude","postlude","choir","sung","psalm")):
        return "audio-headphones-symbolic"
    if any(w in n for w in ("scripture","reading","epistle","gospel","bible")):
        return "user-bookmarks-symbolic"
    if any(w in n for w in ("prayer","blessing","benediction","invocation","intercession","litany")):
        return "emoji-body-symbolic"
    if any(w in n for w in ("sermon","message","homily","reflection")):
        return "format-text-rich-symbolic"
    return None

try:
    from hymn_lookup import lookup_hymn, parse_hymn_ref, search_hymns, prefetch_hymnal
    _HYMN_OK = True
except ImportError:
    _HYMN_OK = False
    def search_hymns(q): return []
    def prefetch_hymnal(book, on_progress=None, on_done=None): pass

try:
    from bible_api import fetch_passage
    _BIBLE_OK = True
except ImportError:
    _BIBLE_OK = False

try:
    from hymn_suggestions import (
        get_suggestions as _get_hymn_suggestions,
        get_theme_names as _get_theme_names,
        get_theme_hymns as _get_theme_hymns,
    )
    _SUGG_OK = True
except (ImportError, FileNotFoundError):
    _SUGG_OK = False
    def _get_theme_names(): return []
    def _get_theme_hymns(t): return []

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


# ── Config ────────────────────────────────────────────────────────────────────

APP_VERSION = "0.17.5-dev18"


config = Config()

# Default UCC Sunday service template — injected on first use if no templates exist
_UCC_DEFAULT_TEMPLATE: list[dict] = [
    {"type": "divider", "title": "Gathering"},
    {"type": "item", "name": "Prelude",                    "section": "Gathering", "note": "", "leader": "", "show_in_bulletin": True, "bulletin_note": ""},
    {"type": "item", "name": "Welcome & Announcements",    "section": "Gathering", "note": "", "leader": "", "show_in_bulletin": True, "bulletin_note": ""},
    {"type": "item", "name": "Land Acknowledgement",       "section": "Gathering", "note": "", "leader": "", "show_in_bulletin": True, "bulletin_note": ""},
    {"type": "item", "name": "Birthday & Anniversary Prayer", "section": "Gathering", "note": "", "leader": "", "show_in_bulletin": True, "bulletin_note": ""},
    {"type": "item", "name": "Christ Candle",              "section": "Gathering", "note": "", "leader": "", "show_in_bulletin": True, "bulletin_note": ""},
    {"type": "item", "name": "Opening Hymn",               "section": "Gathering", "note": "", "leader": "All", "show_in_bulletin": True, "bulletin_note": ""},
    {"type": "item", "name": "Call to Worship",            "section": "Gathering", "note": "", "leader": "", "show_in_bulletin": True, "bulletin_note": ""},
    {"type": "item", "name": "Opening Prayer",             "section": "Gathering", "note": "", "leader": "", "show_in_bulletin": True, "bulletin_note": ""},
    {"type": "item", "name": "Second Hymn",                "section": "Gathering", "note": "", "leader": "All", "show_in_bulletin": True, "bulletin_note": ""},
    {"type": "divider", "title": "Word"},
    {"type": "item", "name": "Scripture",                  "section": "Word",      "note": "", "leader": "", "show_in_bulletin": True, "bulletin_note": ""},
    {"type": "item", "name": "Sung Psalm",                 "section": "Word",      "note": "", "leader": "All", "show_in_bulletin": True, "bulletin_note": ""},
    {"type": "item", "name": "Ministry of Music",          "section": "Word",      "note": "", "leader": "", "show_in_bulletin": True, "bulletin_note": ""},
    {"type": "item", "name": "Growing in Faith",           "section": "Word",      "note": "", "leader": "", "show_in_bulletin": True, "bulletin_note": ""},
    {"type": "item", "name": "Sermon / Message",           "section": "Word",      "note": "", "leader": "", "show_in_bulletin": True, "bulletin_note": ""},
    {"type": "item", "name": "Practice",                   "section": "Word",      "note": "", "leader": "All", "show_in_bulletin": True, "bulletin_note": ""},
    {"type": "item", "name": "Hymn",                       "section": "Word",      "note": "", "leader": "All", "show_in_bulletin": True, "bulletin_note": ""},
    {"type": "divider", "title": "Response"},
    {"type": "item", "name": "Prayers of the People",      "section": "Response",  "note": "", "leader": "", "show_in_bulletin": True, "bulletin_note": ""},
    {"type": "item", "name": "Lord's Prayer",              "section": "Response",  "note": "", "leader": "All", "show_in_bulletin": True, "bulletin_note": ""},
    {"type": "item", "name": "Presentation of Our Offering", "section": "Response","note": "", "leader": "", "show_in_bulletin": True, "bulletin_note": ""},
    {"type": "item", "name": "Offertory",                  "section": "Response",  "note": "", "leader": "", "show_in_bulletin": True, "bulletin_note": ""},
    {"type": "item", "name": "Sung Response",              "section": "Response",  "note": "", "leader": "All", "show_in_bulletin": True, "bulletin_note": ""},
    {"type": "item", "name": "Prayer of Dedication",       "section": "Response",  "note": "", "leader": "", "show_in_bulletin": True, "bulletin_note": ""},
    {"type": "divider", "title": "Sending"},
    {"type": "item", "name": "Rainbow Candle",             "section": "Sending",   "note": "", "leader": "", "show_in_bulletin": True, "bulletin_note": ""},
    {"type": "item", "name": "Closing Hymn",               "section": "Sending",   "note": "", "leader": "All", "show_in_bulletin": True, "bulletin_note": ""},
    {"type": "item", "name": "Commissioning",              "section": "Sending",   "note": "", "leader": "", "show_in_bulletin": True, "bulletin_note": ""},
]

if not config.templates:
    config.templates["UCC Sunday"] = _UCC_DEFAULT_TEMPLATE
    config.default_template = "UCC Sunday"
    config.save()


def get_palette() -> list[tuple[str, list[str]]]:
    if config.palette: return [(d["section"], d["items"]) for d in config.palette]
    return SECTIONS


# ── Data model ────────────────────────────────────────────────────────────────



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
        ins = Gtk.Button(label="Insert"); ins.add_css_class("suggested-action")
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
            typst = _passage_to_typst(self._ref, self._text, self._translation)
            self._on_insert_cb(typst)
        self.close()


# ── Bulletin Preferences ─────────────────────────────────────────────────────

class BulletinPrefsWindow(Adw.Window):
    """Standalone bulletin settings window — auto-saves on every change."""

    def __init__(self, main_window=None, **kw):
        super().__init__(title="Bulletin Settings", default_width=600, default_height=700, **kw)
        self._main = main_window
        self.set_modal(False)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        hdr = Adw.HeaderBar()
        hdr.set_show_end_title_buttons(True)
        box.append(hdr)

        page = Adw.PreferencesPage()
        page.set_vexpand(True)

        # ── Church information ────────────────────────────────────────────
        info_grp = Adw.PreferencesGroup(title="Church information")
        page.add(info_grp)

        def _entry(key, title):
            row = Adw.EntryRow(title=title)
            row.set_text(config.bulletin.get(key, ""))
            def on_changed(r, k=key):
                config.bulletin[k] = r.get_text()
                config.save()
                if self._main: self._main._schedule_preview_update()
            row.connect("changed", on_changed)
            info_grp.add(row)
            return row

        _entry("church_name",  "Church name")
        _entry("address",      "Address")
        _entry("service_time", "Service time")
        _entry("website",      "Website")
        _entry("email",        "Email")
        _entry("phone",        "Phone")

        # ── Format ────────────────────────────────────────────────────────
        fmt_grp = Adw.PreferencesGroup(title="Default bulletin format")
        page.add(fmt_grp)

        fmt_row = Adw.ActionRow(title="Format",
            subtitle="Print/booklet: half-letter folded · Digital/screen: full letter")
        toggle_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        toggle_box.add_css_class("linked"); toggle_box.set_valign(Gtk.Align.CENTER)
        print_btn   = Gtk.ToggleButton(label="Print")
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
                if self._main: self._main._schedule_preview_update()
        print_btn.connect("toggled",   lambda b: on_mode(b, False))
        digital_btn.connect("toggled", lambda b: on_mode(b, True))
        toggle_box.append(print_btn); toggle_box.append(digital_btn)
        fmt_row.add_suffix(toggle_box); fmt_grp.add(fmt_row)

        cover_style_row = Adw.ActionRow(
            title="Title page style",
            subtitle="Full: dedicated cover page · Compact: short header at top of first page")
        cs_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        cs_box.add_css_class("linked"); cs_box.set_valign(Gtk.Align.CENTER)
        cs_full_btn = Gtk.ToggleButton(label="Full page")
        cs_compact_btn = Gtk.ToggleButton(label="Compact")
        cs_compact_btn.set_group(cs_full_btn)
        if config.bulletin.get("cover_style", "full") == "compact":
            cs_compact_btn.set_active(True)
        else:
            cs_full_btn.set_active(True)
        def on_cover_style(btn, style):
            if btn.get_active():
                config.bulletin["cover_style"] = style
                config.save()
                if self._main: self._main._schedule_preview_update()
        cs_full_btn.connect("toggled",    lambda b: on_cover_style(b, "full"))
        cs_compact_btn.connect("toggled", lambda b: on_cover_style(b, "compact"))
        cs_box.append(cs_full_btn); cs_box.append(cs_compact_btn)
        cover_style_row.add_suffix(cs_box); fmt_grp.add(cover_style_row)

        # ── Boilerplate text ──────────────────────────────────────────────
        text_grp = Adw.PreferencesGroup(title="Boilerplate text")
        page.add(text_grp)

        def _text_entry(key, title):
            row = Adw.EntryRow(title=title)
            row.set_text(config.bulletin.get(key, ""))
            def on_changed(r, k=key):
                config.bulletin[k] = r.get_text()
                config.save()
                if self._main: self._main._schedule_preview_update()
            row.connect("changed", on_changed)
            text_grp.add(row)

        _text_entry("welcome",       "Welcome line")
        _text_entry("accessibility", "Accessibility note")

        mission_row = Adw.ActionRow(title="Mission statement")
        text_grp.add(mission_row)
        ms_scroll = Gtk.ScrolledWindow()
        ms_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        ms_scroll.set_min_content_height(56); ms_scroll.add_css_class("card")
        ms_scroll.set_margin_start(12); ms_scroll.set_margin_end(12)
        ms_scroll.set_margin_bottom(8)
        ms_tv = Gtk.TextView(); ms_tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        ms_tv.set_top_margin(6); ms_tv.set_bottom_margin(6)
        ms_tv.set_left_margin(8); ms_tv.set_right_margin(8)
        ms_tv.get_buffer().set_text(config.bulletin.get("mission", ""), -1)
        def on_mission_changed(buf):
            s, e = buf.get_bounds()
            config.bulletin["mission"] = buf.get_text(s, e, False)
            config.save()
            if self._main: self._main._schedule_preview_update()
        ms_tv.get_buffer().connect("changed", on_mission_changed)
        ms_scroll.set_child(ms_tv)
        text_grp.add(ms_scroll)

        # ── Cover image ───────────────────────────────────────────────────────
        cover_grp = Adw.PreferencesGroup(title="Cover image",
            description="Optional image shown at the top of the bulletin (print and digital). "
                        "Use a PNG or JPEG file.")
        page.add(cover_grp)

        cover_row = Adw.ActionRow(title="Image file",
            subtitle=config.bulletin.get("cover_image", "") or "None selected")
        self._cover_row = cover_row

        def _clear_cover(_btn):
            config.bulletin["cover_image"] = ""
            config.save()
            cover_row.set_subtitle("None selected")
            if self._main:
                self._main._schedule_preview_update()
                self._main._refresh_cover_thumb()

        def _pick_cover(_btn):
            dlg = Gtk.FileDialog(title="Choose cover image")
            ff = Gtk.FileFilter(); ff.set_name("Images (PNG, JPEG)")
            ff.add_mime_type("image/png"); ff.add_mime_type("image/jpeg")
            filters = Gio.ListStore.new(Gtk.FileFilter)
            filters.append(ff); dlg.set_filters(filters)
            def _done(d, res):
                try:
                    f = d.open_finish(res)
                except GLib.Error:
                    return
                path = f.get_path()
                config.bulletin["cover_image"] = path
                config.save()
                cover_row.set_subtitle(Path(path).name)
                if self._main:
                    self._main._schedule_preview_update()
                    self._main._refresh_cover_thumb()
            dlg.open(self, None, _done)

        pick_btn = Gtk.Button(label="Choose…", valign=Gtk.Align.CENTER)
        pick_btn.add_css_class("flat")
        pick_btn.connect("clicked", _pick_cover)
        clear_btn = Gtk.Button(icon_name="edit-clear-symbolic", valign=Gtk.Align.CENTER,
                               tooltip_text="Remove cover image")
        clear_btn.add_css_class("flat")
        clear_btn.connect("clicked", _clear_cover)
        cover_row.add_suffix(pick_btn); cover_row.add_suffix(clear_btn)
        cover_grp.add(cover_row)

        # ── Staff list ────────────────────────────────────────────────────
        self._staff_grp = Adw.PreferencesGroup(title="Staff / contact list",
            description="Appears in the back of the bulletin")
        page.add(self._staff_grp)
        self._staff_widgets: list[tuple] = []

        for member in config.bulletin.get("staff", []):
            self._add_staff_row(member.get("role",""), member.get("name",""), member.get("email",""))

        add_btn = Gtk.Button(label="Add person", valign=Gtk.Align.CENTER)
        add_btn.add_css_class("flat")
        add_btn.connect("clicked", lambda _: self._add_staff_row("", "", ""))
        add_row = Adw.ActionRow(title="Staff member")
        add_row.add_suffix(add_btn); self._staff_grp.add(add_row)

        # ── Announcements ─────────────────────────────────────────────────
        self._ann_grp = Adw.PreferencesGroup(title="Announcements",
            description="Appears in the bulletin. Set an expiry date (YYYY-MM-DD) to auto-remove.")
        page.add(self._ann_grp)
        self._ann_widgets: list[tuple] = []

        for ann in config.bulletin.get("announcements", []):
            self._add_announcement(ann.get("text",""), ann.get("expires",""))

        add_ann_btn = Gtk.Button(label="Add announcement", valign=Gtk.Align.CENTER)
        add_ann_btn.add_css_class("flat")
        add_ann_btn.connect("clicked", lambda _: self._add_announcement("", ""))
        add_ann_row = Adw.ActionRow(title="Announcement")
        add_ann_row.add_suffix(add_ann_btn); self._ann_grp.add(add_ann_row)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_child(page)
        box.append(scroll)
        self.set_content(box)

    def _save_staff(self):
        config.bulletin["staff"] = [
            {"role": r.get_text().strip(), "name": n.get_text().strip(), "email": em.get_text().strip()}
            for r, n, em, row in self._staff_widgets
            if row.get_visible() and r.get_text().strip()
        ]
        config.save()
        if self._main: self._main._schedule_preview_update()

    def _add_staff_row(self, role, name, email):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box.set_margin_top(4); box.set_margin_bottom(4)
        box.set_margin_start(4); box.set_margin_end(4)

        role_e = Gtk.Entry(); role_e.set_placeholder_text("Role"); role_e.set_hexpand(True); role_e.set_text(role)
        name_e = Gtk.Entry(); name_e.set_placeholder_text("Name"); name_e.set_hexpand(True); name_e.set_text(name)
        em_e   = Gtk.Entry(); em_e.set_placeholder_text("Email (optional)"); em_e.set_hexpand(True); em_e.set_text(email)

        widgets = [role_e, name_e, em_e, None]

        def on_field_changed(_e, w=widgets):
            self._save_staff()

        role_e.connect("changed", on_field_changed)
        name_e.connect("changed", on_field_changed)
        em_e.connect("changed",   on_field_changed)

        del_btn = Gtk.Button(icon_name="list-remove-symbolic"); del_btn.add_css_class("flat")
        del_btn.connect("clicked", lambda _b, w=widgets: (w[3].set_visible(False), self._save_staff()))

        box.append(role_e); box.append(name_e); box.append(em_e); box.append(del_btn)
        row = Adw.ActionRow(); row.set_child(box)
        widgets[3] = row
        self._staff_grp.add(row)
        self._staff_widgets.append((role_e, name_e, em_e, row))

    def _save_announcements(self):
        config.bulletin["announcements"] = []
        for tv, exp_btn, row in self._ann_widgets:
            if not row.get_visible(): continue
            buf = tv.get_buffer(); s, e = buf.get_bounds()
            text = buf.get_text(s, e, False).strip()
            if text:
                config.bulletin["announcements"].append(
                    {"text": text, "expires": exp_btn._expires_val})
        config.save()
        if self._main: self._main._schedule_preview_update()

    def _swap_announcements(self, idx_a, idx_b):
        """Swap content between two announcement rows (for reorder)."""
        if idx_a < 0 or idx_b < 0 or idx_a >= len(self._ann_widgets) or idx_b >= len(self._ann_widgets):
            return
        tv_a, btn_a, _ = self._ann_widgets[idx_a]
        tv_b, btn_b, _ = self._ann_widgets[idx_b]

        buf_a = tv_a.get_buffer(); s, e = buf_a.get_bounds(); text_a = buf_a.get_text(s, e, False)
        buf_b = tv_b.get_buffer(); s, e = buf_b.get_bounds(); text_b = buf_b.get_text(s, e, False)
        buf_a.set_text(text_b, -1); buf_b.set_text(text_a, -1)

        exp_a, exp_b = btn_a._expires_val, btn_b._expires_val
        btn_a._expires_val = exp_b; btn_a.set_label(exp_b or "No expiry")
        btn_b._expires_val = exp_a; btn_b.set_label(exp_a or "No expiry")

        self._save_announcements()

    def _add_announcement(self, text, expires):
        from datetime import date as _date
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_top(4); box.set_margin_bottom(4)
        box.set_margin_start(4); box.set_margin_end(4)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_height(72); scroll.add_css_class("card")
        tv = Gtk.TextView(); tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        tv.set_top_margin(6); tv.set_bottom_margin(6)
        tv.set_left_margin(8); tv.set_right_margin(8)
        tv.get_buffer().set_text(text, -1)
        scroll.set_child(tv); box.append(scroll)

        # Bottom bar: expiry date picker + reorder + delete
        bottom = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        exp_lbl = Gtk.Label(label="Expires:"); exp_lbl.add_css_class("caption")
        exp_lbl.add_css_class("dim-label"); bottom.append(exp_lbl)

        # Calendar popover for date selection
        cal_pop = Gtk.Popover()
        cal_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        cal_inner.set_margin_top(8); cal_inner.set_margin_bottom(8)
        cal_inner.set_margin_start(8); cal_inner.set_margin_end(8)
        cal = Gtk.Calendar()
        if expires:
            try:
                d = _date.fromisoformat(expires)
                cal.select_day(GLib.DateTime.new_local(d.year, d.month, d.day, 0, 0, 0))
            except Exception:
                pass
        cal_inner.append(cal)
        clear_date_btn = Gtk.Button(label="No expiry"); clear_date_btn.add_css_class("flat")
        cal_inner.append(clear_date_btn)
        cal_pop.set_child(cal_inner)

        btn_label = expires if expires else "No expiry"
        exp_btn = Gtk.MenuButton(label=btn_label, popover=cal_pop)
        exp_btn.add_css_class("flat")
        exp_btn._expires_val = expires
        bottom.append(exp_btn)

        sp = Gtk.Box(); sp.set_hexpand(True); bottom.append(sp)

        # Move up / move down
        up_btn = Gtk.Button(icon_name="go-up-symbolic"); up_btn.add_css_class("flat")
        down_btn = Gtk.Button(icon_name="go-down-symbolic"); down_btn.add_css_class("flat")
        bottom.append(up_btn); bottom.append(down_btn)

        del_btn = Gtk.Button(icon_name="list-remove-symbolic"); del_btn.add_css_class("flat")
        del_btn.add_css_class("destructive-action"); bottom.append(del_btn)
        box.append(bottom)

        row = Adw.ActionRow(); row.set_child(box)
        widgets = (tv, exp_btn, row)

        def on_day_selected(_cal, b=exp_btn):
            dt = _cal.get_date()
            val = f"{dt.get_year():04d}-{dt.get_month():02d}-{dt.get_day_of_month():02d}"
            b._expires_val = val; b.set_label(val)
            cal_pop.popdown(); self._save_announcements()

        def on_clear_date(_b, b=exp_btn):
            b._expires_val = ""; b.set_label("No expiry")
            cal_pop.popdown(); self._save_announcements()

        def on_move(direction, w=widgets):
            idx = next((i for i,x in enumerate(self._ann_widgets) if x is w), -1)
            self._swap_announcements(idx, idx + direction)

        cal.connect("day-selected", on_day_selected)
        clear_date_btn.connect("clicked", on_clear_date)
        tv.get_buffer().connect("changed", lambda _b: self._save_announcements())
        up_btn.connect("clicked",   lambda _b: on_move(-1))
        down_btn.connect("clicked", lambda _b: on_move(+1))
        del_btn.connect("clicked",  lambda _b, w=widgets: (w[2].set_visible(False), self._save_announcements()))

        self._ann_grp.add(row)
        self._ann_widgets.append(widgets)


# ── Preferences ───────────────────────────────────────────────────────────────

class PreferencesWindow(Adw.PreferencesWindow):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.set_title("Preferences"); self.set_default_size(700,560); self.set_search_enabled(False)
        self._build_view()
        self._build_template(); self._build_palette()
        if _SNIP_OK and not config.simple_mode:
            self._build_snippets()
        self._build_github(); self._build_scripture()
        # self._build_typst_files()  # hidden — use Template panel instead
        self.connect("close-request", self._on_close)

    def _build_view(self):
        page = Adw.PreferencesPage(title="View", icon_name="view-grid-symbolic"); self.add(page)

        # ── Simple mode ───────────────────────────────────────────────────
        mode_grp = Adw.PreferencesGroup(
            title="Feature level",
            description="Simple mode hides Typst export, GitHub sync, CSV export, "
                        "snippets, and other advanced features. You can turn it off "
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

        # ── Density ───────────────────────────────────────────────────────
        dens_grp = Adw.PreferencesGroup(title="Density",
            description="Compact view reduces row height for larger services on small screens.")
        page.add(dens_grp)
        try:
            self._compact_row = Adw.SwitchRow(title="Compact view",
                                              subtitle="Smaller rows in the order list and palette")
            self._compact_row.set_active(config.compact_mode)
            dens_grp.add(self._compact_row)
        except AttributeError:
            row = Adw.ActionRow(title="Compact view",
                                subtitle="Smaller rows in the order list and palette")
            self._compact_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
            self._compact_switch.set_active(config.compact_mode)
            row.add_suffix(self._compact_switch); row.set_activatable_widget(self._compact_switch)
            dens_grp.add(row); self._compact_row = None

        # ── Recurring elements ─────────────────────────────────────────────
        rec_grp = Adw.PreferencesGroup(title="Recurring elements",
            description="These element names are added automatically to every new service "
                        "if not already present.")
        page.add(rec_grp)
        self._recurring_rows: list[tuple] = []
        for name in config.recurring_elements:
            self._add_recurring_row(rec_grp, name)
        add_rec_row = Adw.ActionRow(title="Add recurring element")
        add_rec_entry = Gtk.Entry(placeholder_text="Element name", hexpand=True,
                                  valign=Gtk.Align.CENTER)
        add_rec_btn = Gtk.Button(icon_name="list-add-symbolic", valign=Gtk.Align.CENTER)
        add_rec_btn.add_css_class("flat")
        def _do_add_recurring(_btn, entry=add_rec_entry, grp=rec_grp):
            name = entry.get_text().strip()
            if name:
                self._add_recurring_row(grp, name)
                entry.set_text("")
        add_rec_btn.connect("clicked", _do_add_recurring)
        add_rec_entry.connect("activate", _do_add_recurring)
        add_rec_row.add_suffix(add_rec_entry); add_rec_row.add_suffix(add_rec_btn)
        rec_grp.add(add_rec_row)
        self._recurring_group = rec_grp

        # ── Element defaults ──────────────────────────────────────────────
        def_grp = Adw.PreferencesGroup(title="Element defaults",
            description="Default note content auto-filled when an element is added by name. "
                        "Useful for recurring prayers, responses, or instructions.")
        page.add(def_grp)
        self._element_default_rows: list[tuple] = []  # (name_entry, note_entry, row)

        for ename, enote in config.element_defaults.items():
            self._add_element_default_row(def_grp, ename, enote)

        add_def_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6,
                              margin_top=4, margin_bottom=4, margin_start=4, margin_end=4)
        add_def_name = Gtk.Entry(placeholder_text="Element name", hexpand=True)
        add_def_note = Gtk.Entry(placeholder_text="Default note content", hexpand=True)
        add_def_btn  = Gtk.Button(icon_name="list-add-symbolic", valign=Gtk.Align.CENTER)
        add_def_btn.add_css_class("flat")
        def _do_add_default(_btn=None, grp=def_grp):
            name = add_def_name.get_text().strip()
            note = add_def_note.get_text().strip()
            if name:
                self._add_element_default_row(grp, name, note)
                add_def_name.set_text(""); add_def_note.set_text("")
        add_def_btn.connect("clicked", _do_add_default)
        add_def_name.connect("activate", _do_add_default)
        add_def_note.connect("activate", _do_add_default)
        add_def_box.append(add_def_name); add_def_box.append(add_def_note)
        add_def_box.append(add_def_btn)
        add_def_row = Adw.ActionRow(title="Add default"); add_def_row.set_child(add_def_box)
        def_grp.add(add_def_row)
        self._element_defaults_group = def_grp

    def _add_recurring_row(self, grp, name: str):
        row = Adw.ActionRow(title=name)
        del_btn = Gtk.Button(icon_name="list-remove-symbolic", valign=Gtk.Align.CENTER)
        del_btn.add_css_class("flat")
        def _del(btn, r=row, n=name):
            grp.remove(r)
            self._recurring_rows = [(rr, nn) for rr, nn in self._recurring_rows if rr is not r]
        del_btn.connect("clicked", _del)
        row.add_suffix(del_btn)
        grp.add(row)
        self._recurring_rows.append((row, name))

    def _add_element_default_row(self, grp, name: str, note: str):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6,
                      margin_top=4, margin_bottom=4, margin_start=4, margin_end=4)
        name_e = Gtk.Entry(placeholder_text="Element name", hexpand=True); name_e.set_text(name)
        note_e = Gtk.Entry(placeholder_text="Default note", hexpand=True); note_e.set_text(note)
        widgets: list = [name_e, note_e, None]  # row set below
        del_btn = Gtk.Button(icon_name="list-remove-symbolic", valign=Gtk.Align.CENTER)
        del_btn.add_css_class("flat")
        def _del(_b, w=widgets):
            w[2].set_visible(False)
            self._element_default_rows = [(ne, noe, r) for ne, noe, r in self._element_default_rows if r is not w[2]]
        del_btn.connect("clicked", _del)
        box.append(name_e); box.append(note_e); box.append(del_btn)
        row = Adw.ActionRow(); row.set_child(box)
        widgets[2] = row
        grp.add(row)
        self._element_default_rows.append((name_e, note_e, row))

    def _compact_mode_active(self) -> bool:
        if hasattr(self, "_compact_row") and self._compact_row:
            return self._compact_row.get_active()
        return self._compact_switch.get_active() if hasattr(self, "_compact_switch") else False

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

    def _on_close(self, _):
        builtin = [{"section":s,"items":list(i)} for s,i in SECTIONS]
        config.palette = self._pal if self._pal != builtin else None
        config.use_tabs = self._tabs_active()
        config.simple_mode = self._simple_mode_active()
        config.compact_mode = self._compact_mode_active()
        if hasattr(self, "_recurring_rows"):
            config.recurring_elements = [n for _r, n in self._recurring_rows]
        if hasattr(self, "_element_default_rows"):
            config.element_defaults = {
                ne.get_text().strip(): noe.get_text().strip()
                for ne, noe, r in self._element_default_rows
                if r.get_visible() and ne.get_text().strip()
            }
        win = self.get_transient_for()
        if win and hasattr(win, "_apply_simple_mode"):
            win._apply_simple_mode()
        if win and hasattr(win, "_apply_density"):
            win._apply_density()

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
        self._esv_key_row.connect("changed", lambda r: setattr(config, "bible_api_key_esv", r.get_text().strip()))
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

        # ── Hymn database ──────────────────────────────────────────────────
        try:
            from rubric_package.db import hymn_count as _hcount
            _n = _hcount()
        except Exception:
            _n = 0

        hymn_grp = Adw.PreferencesGroup(
            title="Hymn title database",
            description="Pre-download all VU/MV/LUS titles so lookup works offline and search works immediately.")
        page.add(hymn_grp)

        self._hymn_dl_status = Gtk.Label(label=f"{_n} titles cached")
        self._hymn_dl_status.add_css_class("dim-label"); self._hymn_dl_status.add_css_class("caption")
        self._hymn_dl_status.set_xalign(0)
        self._hymn_dl_bar = Gtk.ProgressBar(); self._hymn_dl_bar.set_visible(False)
        self._hymn_dl_bar.set_show_text(True)

        status_row = Adw.ActionRow(title="Cached titles")
        status_row.add_suffix(self._hymn_dl_status)
        hymn_grp.add(status_row)
        hymn_grp.add(self._hymn_dl_bar)

        for book, label, max_n in [("VU", "Voices United (VU)", 961),
                                    ("MV", "More Voices (MV)",   217),
                                    ("LUS","Let Us Sing (LUS)",  150)]:
            btn = Gtk.Button(label=f"Download {label}", valign=Gtk.Align.CENTER)
            btn.add_css_class("flat")
            btn.connect("clicked", lambda _b, bk=book, mn=max_n: self._start_hymn_prefetch(bk, mn))
            row = Adw.ActionRow(title=f"Download {label}")
            row.add_suffix(btn); hymn_grp.add(row)

    def _start_hymn_prefetch(self, book: str, max_n: int):
        self._hymn_dl_bar.set_visible(True)
        self._hymn_dl_bar.set_fraction(0)
        self._hymn_dl_status.set_text(f"Downloading {book}…")

        def on_progress(n, total):
            self._hymn_dl_bar.set_fraction(n / total)
            self._hymn_dl_bar.set_text(f"{book} {n}/{total}")
            return False

        def on_done(added):
            self._hymn_dl_bar.set_visible(False)
            try:
                from rubric_package.db import hymn_count as _hcount
                n = _hcount()
            except Exception:
                n = added
            self._hymn_dl_status.set_text(f"{n} titles cached — {added} new from {book}")
            return False

        prefetch_hymnal(book, on_progress=on_progress, on_done=on_done)

    def _build_typst_files(self):
        """Preferences page: view and edit the bundled Typst template files."""
        page = Adw.PreferencesPage(title="Typst Files", icon_name="text-x-generic-symbolic")
        self.add(page)

        _TEMPLATES = [
            ("bulletin_print",   "Bulletin — print/booklet",  "Half-letter (5.5×8.5in), fold for saddle-stitch"),
            ("bulletin_digital", "Bulletin — digital/screen", "Full letter, colour hyperlinks"),
            ("manuscript",       "Manuscript",                "Leader copy, full-letter"),
            ("_shared",          "Shared functions",          "Rubric function definitions included in all documents"),
        ]

        info_grp = Adw.PreferencesGroup(
            title="Typst preamble templates",
            description="User overrides go in ~/.config/rubric/templates/. "
                        "Edit a template here to create an override; Reset restores the bundled default.",
        )
        page.add(info_grp)

        for fname, label, subtitle in _TEMPLATES:
            row = Adw.ActionRow(title=label, subtitle=subtitle)
            edit_btn = Gtk.Button(label="Edit…", valign=Gtk.Align.CENTER)
            edit_btn.add_css_class("flat")
            edit_btn.connect("clicked", lambda _b, fn=fname, lbl=label: self._open_typst_template_editor(fn, lbl))
            row.add_suffix(edit_btn)
            info_grp.add(row)

    def _open_typst_template_editor(self, fname: str, label: str):
        """Open an in-app editor for a .typ template file."""
        import shutil as _shutil
        user_path = Path.home() / ".config/rubric/templates" / f"{fname}.typ"
        bundled   = Path(__file__).parent / "rubric_package" / "templates" / f"{fname}.typ"

        # Read user override, or bundled default
        if user_path.exists():
            text = user_path.read_text(encoding="utf-8")
            is_override = True
        elif bundled.exists():
            text = bundled.read_text(encoding="utf-8")
            is_override = False
        else:
            text = ""
            is_override = False

        # ── Dialog ────────────────────────────────────────────────────────────
        win = Adw.Window(transient_for=self, modal=True, title=f"Edit: {label}")
        win.set_default_size(680, 520)
        tv = Adw.ToolbarView()
        hdr = Adw.HeaderBar()
        hdr.set_show_end_title_buttons(False)

        # Status label (shows override vs bundled)
        _loc = "User override (~/.config/rubric/templates/)" if is_override else "Bundled default (read-only copy)"
        status_lbl = Gtk.Label(label=_loc)
        status_lbl.add_css_class("caption"); status_lbl.add_css_class("dim-label")

        cancel_btn = Gtk.Button(label="Cancel"); cancel_btn.add_css_class("flat")
        cancel_btn.connect("clicked", lambda _: win.close())
        save_btn = Gtk.Button(label="Save override"); save_btn.add_css_class("suggested-action")
        reset_btn = Gtk.Button(label="Reset to default"); reset_btn.add_css_class("destructive-action")
        reset_btn.set_visible(is_override)

        hdr.pack_start(cancel_btn)
        hdr.pack_end(save_btn)
        hdr.pack_end(reset_btn)
        tv.add_top_bar(hdr)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        vbox.set_margin_top(4); vbox.set_margin_bottom(8)
        vbox.set_margin_start(12); vbox.set_margin_end(12)
        vbox.append(status_lbl)

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.set_vexpand(True)

        # Try GtkSourceView for syntax highlighting
        try:
            gi.require_version("GtkSource", "5")
            from gi.repository import GtkSource as _GS
            from rubric_package.views.element_content import _get_typst_language, _init_source_language_manager
            _init_source_language_manager()
            src_buf = _GS.Buffer()
            lang = _get_typst_language()
            if lang:
                src_buf.set_language(lang)
            sm = _GS.StyleSchemeManager.get_default()
            scheme = sm.get_scheme("classic") or sm.get_scheme("tango")
            if scheme:
                src_buf.set_style_scheme(scheme)
            src_buf.set_highlight_syntax(True)
            src_buf.set_text(text, -1)
            editor = _GS.View.new_with_buffer(src_buf)
            editor.set_show_line_numbers(True)
            editor.set_tab_width(2)
            _buf = src_buf
        except Exception:
            editor = Gtk.TextView()
            _buf = editor.get_buffer()
            _buf.set_text(text, -1)

        editor.set_wrap_mode(Gtk.WrapMode.NONE)
        editor.add_css_class("monospace")
        editor.set_top_margin(8); editor.set_bottom_margin(8)
        editor.set_left_margin(10); editor.set_right_margin(10)
        sw.set_child(editor)
        vbox.append(sw)
        tv.set_content(vbox)
        win.set_content(tv)

        def _save(_b):
            s, e = _buf.get_bounds()
            content = _buf.get_text(s, e, False)
            user_path.parent.mkdir(parents=True, exist_ok=True)
            user_path.write_text(content, encoding="utf-8")
            status_lbl.set_text("User override (~/.config/rubric/templates/)")
            reset_btn.set_visible(True)

        def _reset(_b):
            if bundled.exists():
                bundled_text = bundled.read_text(encoding="utf-8")
                try:
                    user_path.unlink()
                except FileNotFoundError:
                    pass
                _buf.set_text(bundled_text, -1)
                status_lbl.set_text("Bundled default (read-only copy)")
                reset_btn.set_visible(False)

        save_btn.connect("clicked", _save)
        reset_btn.connect("clicked", _reset)
        win.present()

    def _build_github(self):
        page = Adw.PreferencesPage(title="GitHub", icon_name="network-server-symbolic")
        self.add(page)

        # ── Setup wizard shortcut ──────────────────────────────────────────
        wizard_grp = Adw.PreferencesGroup(
            title="First-time setup",
            description="Run the setup wizard to configure your folder, download hymn titles, and connect to GitHub."
        )
        page.add(wizard_grp)
        wizard_row = Adw.ActionRow(title="Initialize Rubric",
                                   subtitle="Walk through folder, hymn download, and GitHub setup")
        wizard_btn = Gtk.Button(label="Run wizard", valign=Gtk.Align.CENTER)
        wizard_btn.add_css_class("suggested-action")
        def _run_wizard(_b):
            main = self.get_transient_for()
            self.close()
            if main and hasattr(main, "_show_setup_wizard"):
                GLib.idle_add(main._show_setup_wizard)
        wizard_btn.connect("clicked", _run_wizard)
        wizard_row.add_suffix(wizard_btn)
        wizard_grp.add(wizard_row)

        # ── Repository folder ──────────────────────────────────────────────
        loc_grp = Adw.PreferencesGroup(
            title="Repository folder",
            description="A folder on this computer that is (or will become) a git repository. "
                        "Rubric will save liturgy files, Typst exports, and PDFs in subfolders here."
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
                _GIT + ["-C", repo, "remote", "get-url", "origin"],
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
                    "*.log\n"
                    "*.toc\n*.lof\n*.lot\n*.dvi\n*.maf\n*.mtc\n*.mtc0\n",
                    encoding="utf-8"
                )
            except OSError as e:
                errors.append(str(e))

        try:
            r = subprocess.run(_GIT + ["-C", repo, "init"],
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
            check = subprocess.run(_GIT + ["-C", repo, "remote", "get-url", "origin"],
                                   capture_output=True, text=True, timeout=5)
            cmd = _GIT + ["-C", repo, "remote",
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
                r = subprocess.run(_GIT + ["-C", repo, "pull"],
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
        super().__init__(**kw); self.set_default_size(1000,700); self.maximize()
        self.service_entries: list = []
        self._undo_stack: list[list[dict]] = []
        self._redo_stack: list[list[dict]] = []
        self.current_file: str|None = None
        self.typ_file: str|None = None
        self.modified = False; self._updating_note = False; self._leader_undo_pushed = False
        self.selected_date = None; self._selected_global_idx = -1
        self._current_readings: dict[str,str] = {}
        self._tab_listboxes: list[tuple] = []
        self._tab_ctx_div: SectionDivider | None = None
        self._colour_bar_rgb = (0.12,0.62,0.46)
        self._compiling_toast: Adw.Toast | None = None

        self._setup_actions(); self._build_ui(); self._apply_density(); self._update_title(); self._update_tex_btn()
        # Seed from default template on first launch
        items = config.templates.get(config.default_template,
                next(iter(config.templates.values()), None))
        if items:
            for d in items:
                self.service_entries.append(_entry_from_dict(d))
            self._refresh_order_list()
        GLib.timeout_add_seconds(AUTOSAVE_SECS, self._do_autosave)
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

    def _on_simple_status_clicked(self, _btn):
        config.simple_mode = not config.simple_mode
        config.save()
        self._apply_simple_mode()

    def _on_gost_status_clicked(self, _btn):
        config.gost_mode = not config.gost_mode
        config.save()
        self._apply_gost_mode()

    def _apply_simple_mode(self, skip_btn_sync: bool = False):
        simple = config.simple_mode
        if hasattr(self, "_simple_status_lbl"):
            if simple:
                self._simple_status_lbl.set_markup("<b>SIMPLE</b>")
            else:
                self._simple_status_lbl.set_text("SIMPLE")
        if hasattr(self, "_dev_status_btn"):
            self._dev_status_btn.set_visible(not simple)
        if hasattr(self, "_gost_status_btn"):
            self._gost_status_btn.set_visible(not simple)
        if hasattr(self, "_compact_status_btn"):
            self._compact_status_btn.set_visible(not simple)
        if hasattr(self, "_preamble_btn"):
            self._preamble_btn.set_visible(not simple)
        if hasattr(self, "_git_btn"):
            self._git_btn.set_visible(not simple)
        if hasattr(self, "_time_bar"):
            if simple:
                self._time_bar.set_visible(False)
            else:
                self._update_time_total()
        self._refresh_menu()

    def _apply_gost_mode(self):
        if hasattr(self, "_gost_status_lbl"):
            if config.gost_mode:
                self._gost_status_lbl.set_markup("<b>GOST</b>")
            else:
                self._gost_status_lbl.set_text("GOST")
        if config.gost_mode:
            self._gost_css.load_from_data(b"* { font-family: 'GOST type B'; }")
        else:
            self._gost_css.load_from_data(b"")

    def _on_compact_status_clicked(self, _btn):
        config.compact_mode = not config.compact_mode
        config.save()
        self._apply_density()

    def _apply_density(self):
        if config.compact_mode:
            self.add_css_class("compact-mode")
        else:
            self.remove_css_class("compact-mode")
        if hasattr(self, "_compact_status_lbl"):
            if config.compact_mode:
                self._compact_status_lbl.set_markup("<b>Compact</b>")
            else:
                self._compact_status_lbl.set_text("Compact")

    def _on_dev_status_clicked(self, _btn):
        self._dev_mode = not getattr(self, "_dev_mode", False)
        self._apply_dev_mode()

    def _on_typst_edit_clicked(self, _btn):
        self._typst_edit_active = not self._typst_edit_active
        if self._typst_edit_active:
            self._typst_edit_lbl.set_markup("<b>Typst</b>")
        else:
            self._typst_edit_lbl.set_text("Typst")
        if hasattr(self, "_content_widget"):
            self._content_widget.set_typst_mode(self._typst_edit_active)

    def _apply_dev_mode(self):
        dev = getattr(self, "_dev_mode", False)
        if hasattr(self, "_dev_status_lbl"):
            if dev:
                self._dev_status_lbl.set_markup("<b>Dev</b>")
            else:
                self._dev_status_lbl.set_text("Dev")
        if hasattr(self, "_preview_copy_typst_bar"):
            self._preview_copy_typst_bar.set_visible(dev)
        if hasattr(self, "_typst_edit_btn"):
            self._typst_edit_btn.set_visible(dev)
            if not dev and self._typst_edit_active:
                # Turn off typst mode when dev mode is disabled
                self._typst_edit_active = False
                self._typst_edit_lbl.set_text("Typst")
                if hasattr(self, "_content_widget"):
                    self._content_widget.set_typst_mode(False)

    def _dev_copy_typst(self):
        """Copy the current preview's Typst source to clipboard (Dev mode)."""
        mode = getattr(self, "_preview_mode", "bulletin")
        try:
            if mode == "manuscript":
                typ_src = self._build_manuscript_typst()
            else:
                typ_src = self._build_bulletin_typst(digital=False)
            display = Gdk.Display.get_default()
            if display:
                display.get_clipboard().set(typ_src)
            self._show_toast("Typst source copied to clipboard", timeout=2)
        except Exception as e:
            self._show_toast(f"Error: {e}", timeout=3)

    def _refresh_menu(self):
        simple = config.simple_mode
        menu = Gio.Menu()
        menu.append("Preferences", "win.preferences")
        menu.append("Bulletin settings…", "win.open-bulletin-prefs")
        menu.append("Duplicate service", "win.duplicate")
        if not simple:
            menu.append("Save order as template…", "win.save-template")
        menu.append("Save as…", "win.save-as")

        file_sec = Gio.Menu()
        file_sec.append("Export as…", "win.export-as")
        file_sec.append("Copy service as text", "win.copy-as-text")
        file_sec.append("Services…", "win.open-services")
        menu.append_section(None, file_sec)

        if config.github_repo and not simple:
            git_sec = Gio.Menu()
            git_sec.append("Push to GitHub (Ctrl+Shift+G)", "win.git-push")
            git_sec.append("Pull from GitHub", "win.git-pull")
            menu.append_section("GitHub Sync", git_sec)

        if not simple:
            adv_sec = Gio.Menu()
            adv_sec.append("Snippets (Ctrl+Shift+I)", "win.snippets")
            menu.append_section("Advanced", adv_sec)

        menu.append("Help…", "win.open-help")
        menu.append("Welcome wizard…", "win.show-wizard")
        menu.append_submenu("Recent files", self._recent_sec)

        self._menu_btn.set_menu_model(menu)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _setup_actions(self):
        for name, cb, accel in [
            ("new",           self.new_service,      "<Ctrl>n"),
            ("open",          self.open_file,         "<Ctrl>o"),
            ("save",          self.save_file,         "<Ctrl>s"),
            ("save-as",       self.save_file_as,      "<Ctrl><Shift>s"),
            ("export-text",   self.export_text,       None),
            ("export-typst",       self.export_typst,          None),
            ("quick-export-typst", self.quick_export_typst,    "<Ctrl>e"),
            ("compile-pdf",        self.compile_typst_pdf,     "<Ctrl><Shift>p"),
            ("save-template", self.save_as_template,  None),
            ("duplicate",     self.duplicate_service, None),
            ("add-custom",    self.add_custom,        "<Ctrl><Shift>n"),
            ("add-divider",   self.add_divider,       "<Ctrl>d"),
            ("move-up",       self.move_up,           "<Ctrl>Up"),
            ("move-down",     self.move_down,         "<Ctrl>Down"),
            ("remove-item",   self.remove_item,       None),
            ("undo",          self.undo,              "<Ctrl>z"),
            ("redo",          self.redo,              "<Ctrl><Shift>z"),
            ("preferences",   self.open_preferences,  "<Ctrl>comma"),
            ("clear-recent",       self._clear_recent,      None),
            ("tab-rename",         self._tab_rename_action, None),
            ("tab-delete",         self._tab_delete_action, None),
            ("unlink-typ",         self._unlink_typ,           None),
            ("snippets",           self.open_snippets,          "<Ctrl><Shift>i"),
            ("scripture-search",   self.open_scripture_search,  "<Ctrl><Shift>f"),
            ("export-csv",         self.export_csv,             None),
            ("export-bulletin",    self.export_bulletin,        "<Ctrl><Shift>b"),
            ("export-html",        self.export_html,            None),
            ("open-planner",       self.open_planner,           "<Ctrl><Shift>l"),
            ("git-push",           self.git_push,               "<Ctrl><Shift>g"),
            ("git-pull",           self.git_pull,               None),
            ("show-help",          lambda: self.open_help("help"),       "F1"),
            ("show-faq",           lambda: self.open_help("faq"),        None),
            ("show-changelog",     lambda: self.open_help("changelog"),  None),
            ("show-wizard",        lambda: self._show_setup_wizard(),      None),
            ("open-bulletin-prefs", self.open_bulletin_prefs,              None),
            ("open-services",      self.open_services,                    None),
            ("open-library",       self.open_library,                     "<Ctrl><Shift>k"),
            ("open-archive",       self.open_archive,                     "<Ctrl><Shift>h"),
            ("open-help",          self.open_help,                        None),
            ("show-about",         self.show_about,                       None),
            ("export-as",          self.export_as,                      None),
            ("export-av-sheet",    self.export_av_sheet,                None),
            ("export-minister-pdf", self.export_minister_pdf,           None),
            ("focus-mode",         self._toggle_focus_mode,             None),
            ("copy-as-text",       self._copy_as_text,                  "<Ctrl><Shift>t"),
            ("toggle-bulletin-edit", self._toggle_bulletin_edit,        None),
            ("show-shortcuts",     self._show_shortcuts_window,         "<Ctrl>question"),
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
        hdr.add_css_class("rubric-main-hdr")
        self._season_hdr_css = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), self._season_hdr_css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        # Palette sidebar toggle — all the way at the left
        self._sidebar_btn = Gtk.ToggleButton(icon_name="sidebar-show",
                                             tooltip_text="Show/hide elements panel")
        self._sidebar_btn.set_active(True)
        self._sidebar_btn.add_css_class("flat")
        self._sidebar_btn.connect("toggled", self._toggle_palette_sidebar)
        hdr.pack_start(self._sidebar_btn)

        # New + Open as a linked pill
        doc_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        doc_box.add_css_class("linked")
        for icon, tip, cb in [("document-new", "New service (Ctrl+N)", self.new_service),
                               ("document-open", "Open… (Ctrl+O)", self.open_file)]:
            b = Gtk.Button(icon_name=icon, tooltip_text=tip)
            b.connect("clicked", lambda _, f=cb: f())
            doc_box.append(b)
        hdr.pack_start(doc_box)

        # Undo + Redo as a linked pill
        edit_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        edit_box.add_css_class("linked")
        self.undo_btn = Gtk.Button(icon_name="edit-undo", tooltip_text="Undo (Ctrl+Z)")
        self.undo_btn.connect("clicked", lambda _: self.undo()); self.undo_btn.set_sensitive(False)
        self.redo_btn = Gtk.Button(icon_name="edit-redo", tooltip_text="Redo (Ctrl+Shift+Z)")
        self.redo_btn.connect("clicked", lambda _: self.redo()); self.redo_btn.set_sensitive(False)
        edit_box.append(self.undo_btn); edit_box.append(self.redo_btn)
        hdr.pack_start(edit_box)

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
        self.service_title_entry.set_size_request(180, -1)
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
        _date_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        _date_ico = Gtk.Image(icon_name="x-office-calendar-symbolic")
        _date_ico.add_css_class("dim-label"); _date_box.append(_date_ico)
        self._date_label_widget = Gtk.Label(label="No date selected")
        self._date_label_widget.set_ellipsize(Pango.EllipsizeMode.END); _date_box.append(self._date_label_widget)
        self.date_button = Gtk.MenuButton(popover=cal_pop)
        self.date_button.set_child(_date_box)
        self.date_button.set_hexpand(True); date_row.append(self.date_button)
        clr = Gtk.Button(icon_name="edit-clear-symbolic", tooltip_text="Clear date")
        clr.add_css_class("flat"); clr.connect("clicked", self._on_clear_date); date_row.append(clr)
        pop_box.append(date_row)

        # Lectionary year/season — in popover, not the header bar
        lect_sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        lect_sep.set_margin_top(4); pop_box.append(lect_sep)
        self._lect_label = Gtk.Label()
        self._lect_label.add_css_class("caption"); self._lect_label.add_css_class("dim-label")
        self._lect_label.set_xalign(0); self._lect_label.set_margin_top(2)
        pop_box.append(self._lect_label)

        info_pop = Gtk.Popover(); info_pop.set_child(pop_box)
        info_pop.set_has_arrow(False); info_pop.set_position(Gtk.PositionType.BOTTOM)

        title_btn = Gtk.MenuButton(popover=info_pop)
        title_btn.add_css_class("flat"); title_btn.set_child(self.title_widget)
        hdr.set_title_widget(title_btn)
        self.selected_date = None

        # Cover art thumbnail — shown when a cover image is configured
        self._cover_thumb = Gtk.Image()
        self._cover_thumb.set_pixel_size(28)
        self._cover_thumb.add_css_class("cover-thumb")
        self._cover_thumb.set_visible(False)
        self._cover_thumb.set_tooltip_text("Cover image — change in Settings → Bulletin")
        hdr.pack_start(self._cover_thumb)
        self._refresh_cover_thumb()

        sb = Gtk.Button(icon_name="document-save", tooltip_text="Save (Ctrl+S)")
        sb.add_css_class("suggested-action"); sb.connect("clicked", lambda _: self.save_file()); hdr.pack_end(sb)

        # Advanced-mode buttons — kept as instance vars for sensitivity/tooltip code
        # but not packed into the header. Use keyboard shortcuts or the hamburger menu.
        self.push_btn = Gtk.Button(icon_name="emblem-synchronizing-symbolic",
                                   tooltip_text="Push to GitHub (Ctrl+Shift+G)")
        self.push_btn.connect("clicked", lambda _: self.git_push())

        self.tex_btn = Gtk.Button(icon_name="emblem-documents-symbolic",
                                  tooltip_text="Export to Typst (Ctrl+E)")
        self.tex_btn.connect("clicked", lambda _: self.quick_export_typst())

        self.pdf_btn = Gtk.Button(icon_name="document-print-symbolic",
                                  tooltip_text="Compile to PDF via Typst (Ctrl+Shift+P)")
        self.pdf_btn.connect("clicked", lambda _: self.compile_typst_pdf())

        self._update_lect_label()
        GLib.timeout_add_seconds(86400, self._update_lect_label)
        self._recent_sec = Gio.Menu()
        self._rebuild_recent_menu()
        self._menu_btn = Gtk.MenuButton(icon_name="open-menu-symbolic", tooltip_text="Menu")
        hdr.pack_end(self._menu_btn)
        self._refresh_menu()

        _help_btn = Gtk.Button(icon_name="help-contents-symbolic",
                               tooltip_text="Quick help — what each part of the screen does")
        _help_btn.add_css_class("flat")
        _help_btn.connect("clicked", self._show_ui_help_popover)
        self._help_header_btn = _help_btn
        hdr.pack_end(_help_btn)

        self._preview_visible = False
        self._preview_scroll_poll_id = None
        self._preview_pending_id = None
        self._preview_mode = "bulletin"
        self._preview_paned_positioned = False
        self._preview_lbl = Gtk.Label(label="Preview")
        self._preview_lbl.set_use_markup(True)
        self._preview_btn = Gtk.Button(tooltip_text="Toggle live preview")
        self._preview_btn.set_child(self._preview_lbl)
        self._preview_btn.add_css_class("flat")
        self._preview_btn.connect("clicked", self._toggle_preview_panel)
        hdr.pack_end(self._preview_btn)

        tv = Adw.ToolbarView(); tv.add_top_bar(hdr)

        # ── Status bar ────────────────────────────────────────────────────────
        status_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        status_bar.add_css_class("toolbar")

        def _status_toggle_btn(label_text, tooltip):
            lbl = Gtk.Label(); lbl.add_css_class("caption"); lbl.set_use_markup(True)
            lbl.set_margin_top(1); lbl.set_margin_bottom(1)
            lbl.set_text(label_text)
            btn = Gtk.Button(); btn.set_child(lbl); btn.add_css_class("flat")
            btn.set_tooltip_text(tooltip); btn.set_margin_start(1); btn.set_margin_end(1)
            return btn, lbl

        def _sb_sep():
            s = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
            s.add_css_class("rubric-statusbar-sep")
            s.set_margin_start(3); s.set_margin_end(3)
            s.set_margin_top(3); s.set_margin_bottom(3)
            return s

        # Left group — aligned left, no separators
        _left_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        _left_box.set_halign(Gtk.Align.START)
        _left_box.set_margin_start(2)

        self._simple_status_btn, self._simple_status_lbl = _status_toggle_btn(
            "SIMPLE", "Simple mode — hides export, GitHub sync and other advanced options. Good for first-time use.")
        self._simple_status_btn.connect("clicked", self._on_simple_status_clicked)
        _left_box.append(self._simple_status_btn)

        self._gost_status_btn, self._gost_status_lbl = _status_toggle_btn(
            "GOST", "Switch UI font to GOST Type B — a Cyrillic engineering typeface. Toggle off to return to the system font.")
        self._gost_status_btn.connect("clicked", self._on_gost_status_clicked)
        _left_box.append(self._gost_status_btn)

        self._compact_status_btn, self._compact_status_lbl = _status_toggle_btn(
            "Compact", "Compact view — reduces spacing between service elements so more fit on screen at once")
        self._compact_status_btn.connect("clicked", self._on_compact_status_clicked)
        _left_box.append(self._compact_status_btn)

        self._dev_status_btn, self._dev_status_lbl = _status_toggle_btn(
            "Dev", "Developer mode — shows a 'Copy Typst source' button in the preview panel for debugging bulletin layout")
        self._dev_status_btn.connect("clicked", self._on_dev_status_clicked)
        self._dev_mode = False
        _left_box.append(self._dev_status_btn)

        self._typst_edit_btn, self._typst_edit_lbl = _status_toggle_btn(
            "Typst", "Switch the content editor to raw Typst source mode")
        self._typst_edit_btn.connect("clicked", self._on_typst_edit_clicked)
        self._typst_edit_btn.set_visible(False)
        self._typst_edit_active = False
        _left_box.append(self._typst_edit_btn)

        self._preamble_btn, self._preamble_lbl = _status_toggle_btn(
            "Template", "Document template — set fonts, margins, and layout for generated PDFs")
        self._preamble_btn.connect("clicked", self._on_preamble_clicked)
        self._preamble_active = False
        _left_box.append(self._preamble_btn)

        status_bar.append(_left_box)

        # Centre: prev event · season dot · next event — spread apart
        _left_spacer = Gtk.Box(); _left_spacer.set_hexpand(True)
        status_bar.append(_left_spacer)
        _centre_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        _centre_box.set_halign(Gtk.Align.CENTER)
        # Previous event
        self._prev_obs_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        _centre_box.append(self._prev_obs_box)
        # Season dot with wider margins to spread the two event listings
        self._sb_season_dot = Gtk.Label(label="●")
        self._sb_season_dot.add_css_class("caption"); self._sb_season_dot.add_css_class("dim-label")
        self._sb_season_dot.set_margin_start(36); self._sb_season_dot.set_margin_end(36)
        self._sb_season_dot.set_visible(False)
        _centre_box.append(self._sb_season_dot)
        # Next/upcoming event
        self._obs_status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        _centre_box.append(self._obs_status_box)
        status_bar.append(_centre_box)
        _right_spacer = Gtk.Box(); _right_spacer.set_hexpand(True)
        status_bar.append(_right_spacer)

        # Right group — aligned right, no separators
        _right_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        _right_box.set_halign(Gtk.Align.END)
        _right_box.set_margin_end(2)

        # Save-state chip — shows "● Unsaved" when modified, hidden when saved
        self._save_state_lbl = Gtk.Label()
        self._save_state_lbl.add_css_class("caption")
        self._save_state_lbl.set_margin_start(4); self._save_state_lbl.set_margin_end(6)
        self._save_state_lbl.set_visible(False)
        self._save_state_lbl.set_tooltip_text("Unsaved changes — press Ctrl+S to save")
        _right_box.append(self._save_state_lbl)

        self._focus_status_btn, self._focus_status_lbl = _status_toggle_btn(
            "Focus", "Focus mode — hides the element palette and list so you can concentrate on the notes editor")
        self._focus_status_btn.connect("clicked", lambda _: self._toggle_focus_mode())
        _right_box.append(self._focus_status_btn)

        _git_btn = Gtk.Button(label="Git")
        _git_btn.add_css_class("flat"); _git_btn.add_css_class("caption")
        _git_btn_lbl = _git_btn.get_child()
        if _git_btn_lbl:
            _git_btn_lbl.set_margin_top(1); _git_btn_lbl.set_margin_bottom(1)
        _git_btn.set_tooltip_text("Commit and push to GitHub (Ctrl+Shift+G) — pull --rebase first")
        _git_btn.set_margin_start(1); _git_btn.set_margin_end(1)
        _git_btn.connect("clicked", lambda _: self.git_push())
        self._git_btn = _git_btn
        _right_box.append(_git_btn)

        ver_btn = Gtk.Button(label=f"v{APP_VERSION}")
        ver_btn.add_css_class("flat"); ver_btn.add_css_class("dim-label"); ver_btn.add_css_class("caption")
        ver_btn.set_margin_end(4); ver_btn.set_tooltip_text("View changelog")
        ver_btn.connect("clicked", lambda _: self.open_help("changelog"))
        _right_box.append(ver_btn)

        status_bar.append(_right_box)

        tv.add_bottom_bar(status_bar)

        # GOST CSS provider (priority above application so it overrides theme fonts)
        self._gost_css = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), self._gost_css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)

        self._toast_overlay = Adw.ToastOverlay()

        # Outer paned: palette | content
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_shrink_start_child(False); paned.set_shrink_end_child(False)
        paned.set_start_child(self._build_palette_panel())
        self._palette_paned = paned
        self._palette_visible = True
        GLib.idle_add(lambda: paned.set_position(290))

        # Main stack: order panel or preamble editor
        self._main_stack = Gtk.Stack()
        self._main_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._main_stack.set_transition_duration(120)
        self._main_stack.add_named(self._build_order_panel(), "order")
        self._main_stack.add_named(self._build_preamble_panel(), "preamble")

        # Inner paned: order/preamble stack | bulletin preview (preview hidden by default)
        self._preview_panel = self._build_preview_panel()
        self._preview_panel.set_visible(False)
        self._preview_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self._preview_paned.set_shrink_start_child(False)
        self._preview_paned.set_shrink_end_child(False)
        self._preview_paned.set_start_child(self._main_stack)
        self._preview_paned.set_end_child(self._preview_panel)
        paned.set_end_child(self._preview_paned)

        self._toast_overlay.set_child(paned)
        tv.set_content(self._toast_overlay)
        self.set_content(tv)
        self._apply_simple_mode()
        self._apply_gost_mode()

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
                row = Adw.ActionRow(title=GLib.markup_escape_text(rname)); row.set_activatable(True)
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
                row = Adw.ActionRow(title=GLib.markup_escape_text(iname)); row.set_activatable(True)
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
            row = Adw.ActionRow(title=GLib.markup_escape_text(rname)); row.set_activatable(True)
            row._item_name = rname; row._section_name = self._section_for_item(rname)
            lb.append(row)

    # ── Preamble panel ────────────────────────────────────────────────────────

    def _on_preamble_clicked(self, _btn):
        self._preamble_active = not self._preamble_active
        if self._preamble_active:
            self._preamble_lbl.set_markup("<b>Template</b>")
            self._main_stack.set_visible_child_name("preamble")
            # Sync preview mode to whichever sub-toggle is active
            active_key = (
                "manuscript" if getattr(self, "_preamble_ms_btn", None)
                and self._preamble_ms_btn.get_active()
                else "bulletin"
            )
            self._preview_mode = active_key
            if hasattr(self, "_preview_manuscript_btn"):
                if active_key == "manuscript":
                    self._preview_manuscript_btn.set_active(True)
                else:
                    self._preview_bulletin_btn.set_active(True)
            if not self._preview_visible:
                self._toggle_preview_panel()
            else:
                self._do_preview_update()
        else:
            self._preamble_lbl.set_text("Template")
            self._main_stack.set_visible_child_name("order")

    def _preamble_heading_typst(self, key: str) -> str:
        """Return Typst #show heading override for the given template key, or '' for default."""
        style = config.preamble.get(key, {}).get("heading_style", "bold-smallcaps-rule")
        if style == "bold-smallcaps-rule":
            return ""  # Default — already in TYPST_SHARED
        if style == "bold-smallcaps":
            body = "text(weight: \"bold\", smallcaps(it.body))"
        elif style == "bold":
            body = "text(weight: \"bold\", it.body)"
        else:
            body = "it.body"
        return (
            "#show heading.where(level: 2): it => {\n"
            "  v(10pt)\n"
            f"  {body}\n"
            "  v(4pt, weak: true)\n"
            "}"
        )

    def _on_preamble_changed(self, key: str, field: str, value) -> None:
        if key not in config.preamble:
            config.preamble[key] = {}
        config.preamble[key][field] = value
        config.save()
        self._schedule_preview_update()

    _BULLETIN_PRESETS = [
        (
            "Classic",
            "Two columns · small-caps headings with rule · 11 pt\n"
            "Traditional, formal — suits most congregations",
            {
                "font": "", "size": 11.0,
                "margin_top": 0.65, "margin_bottom": 0.65,
                "margin_left": 0.6,  "margin_right": 0.6,
                "columns": 2, "heading_style": "bold-smallcaps-rule",
            },
        ),
        (
            "Contemporary",
            "Two columns · clean bold headings · 10.5 pt\n"
            "Modern, welcoming — less ornate than Classic",
            {
                "font": "", "size": 10.5,
                "margin_top": 0.55, "margin_bottom": 0.55,
                "margin_left": 0.5,  "margin_right": 0.5,
                "columns": 2, "heading_style": "bold",
            },
        ),
        (
            "Large Print",
            "Single column · bold small-caps headings · 14 pt\n"
            "Accessible — clear for low-vision readers",
            {
                "font": "", "size": 14.0,
                "margin_top": 0.6,  "margin_bottom": 0.6,
                "margin_left": 0.65, "margin_right": 0.65,
                "columns": 1, "heading_style": "bold-smallcaps",
            },
        ),
        (
            "Compact",
            "Two columns · plain headings · 9.5 pt · tight margins\n"
            "Fits long services on fewer pages",
            {
                "font": "", "size": 9.5,
                "margin_top": 0.5,  "margin_bottom": 0.5,
                "margin_left": 0.45, "margin_right": 0.45,
                "columns": 2, "heading_style": "plain",
            },
        ),
    ]

    def _apply_bulletin_preset(self, preset: dict) -> None:
        config.preamble["bulletin"] = dict(preset)
        config.save()
        self._rebuild_preamble_form("bulletin")
        self._do_preview_update()

    def _rebuild_preamble_form(self, key: str) -> None:
        old = self._preamble_form_stack.get_child_by_name(key)
        if old:
            self._preamble_form_stack.remove(old)
        new_form = self._build_preamble_form(key)
        self._preamble_form_stack.add_named(new_form, key)
        self._preamble_form_stack.set_visible_child_name(key)

    @staticmethod
    def _get_system_fonts() -> list[str]:
        try:
            from gi.repository import PangoCairo
            fm = PangoCairo.font_map_get_default()
            return sorted(f.get_name() for f in fm.list_families())
        except Exception:
            return []

    def _build_preamble_form(self, key: str) -> Gtk.Widget:
        """Scrollable preference form for manuscript or bulletin template settings."""
        _MS_DEF = {
            "font": "", "size": 11.0,
            "margin_top": 1.0, "margin_bottom": 1.0,
            "margin_left": 0.7, "margin_right": 0.7,
            "heading_style": "bold-smallcaps-rule",
            "columns": 2,
        }
        _BUL_DEF = {
            "font": "", "size": 11.0,
            "margin_top": 0.7, "margin_bottom": 0.7,
            "margin_left": 0.6, "margin_right": 0.6,
            "heading_style": "bold-smallcaps-rule",
            "columns": 2,
        }
        defaults = _MS_DEF if key == "manuscript" else _BUL_DEF
        p = config.preamble.get(key, {})

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        page = Adw.PreferencesPage()
        page.set_vexpand(True)

        # ── Style presets (bulletin only) ─────────────────────────────────────
        if key == "bulletin":
            preset_grp = Adw.PreferencesGroup(
                title="Style presets",
                description="Apply a starting point — you can fine-tune below")
            page.add(preset_grp)
            for p_name, p_desc, p_vals in self._BULLETIN_PRESETS:
                row = Adw.ActionRow(title=p_name, subtitle=p_desc.replace("\n", " · "))
                btn = Gtk.Button(label="Apply", valign=Gtk.Align.CENTER)
                btn.add_css_class("flat")
                btn.connect("clicked", lambda _b, v=p_vals: self._apply_bulletin_preset(v))
                row.add_suffix(btn)
                preset_grp.add(row)

        # ── Typography ────────────────────────────────────────────────────────
        typo_grp = Adw.PreferencesGroup(title="Typography")
        page.add(typo_grp)

        # Font family — dropdown of system fonts
        system_fonts = self._get_system_fonts()
        font_names = ["Default"] + system_fonts
        font_model = Gtk.StringList.new(font_names)
        font_row = Adw.ComboRow(title="Font family", model=font_model)
        font_row.set_enable_search(True)
        font_row.set_expression(
            Gtk.PropertyExpression.new(Gtk.StringObject, None, "string"))
        current_font = p.get("font", defaults["font"])
        try:
            font_row.set_selected(system_fonts.index(current_font) + 1 if current_font else 0)
        except ValueError:
            font_row.set_selected(0)

        def _on_font_selected(row, _prop):
            sel = row.get_selected()
            self._on_preamble_changed(key, "font", "" if sel == 0 else font_names[sel])

        font_row.connect("notify::selected", _on_font_selected)
        typo_grp.add(font_row)

        size_adj = Gtk.Adjustment(
            value=p.get("size", defaults["size"]),
            lower=6, upper=36, step_increment=0.5)
        size_row = Adw.SpinRow(adjustment=size_adj, digits=1, title="Font size (pt)")
        size_row.connect("notify::value",
                         lambda r, _p: self._on_preamble_changed(key, "size", r.get_value()))
        typo_grp.add(size_row)

        # ── Margins ───────────────────────────────────────────────────────────
        margin_grp = Adw.PreferencesGroup(title="Margins (inches)")
        page.add(margin_grp)

        for field, label in (
            ("margin_top",    "Top"),
            ("margin_bottom", "Bottom"),
            ("margin_left",   "Left"),
            ("margin_right",  "Right"),
        ):
            adj = Gtk.Adjustment(
                value=p.get(field, defaults[field]),
                lower=0.0, upper=4.0, step_increment=0.05)
            row = Adw.SpinRow(adjustment=adj, digits=2, title=label)
            row.connect("notify::value",
                        lambda r, _p, f=field: self._on_preamble_changed(key, f, r.get_value()))
            margin_grp.add(row)

        # ── Layout ────────────────────────────────────────────────────────────
        layout_grp = Adw.PreferencesGroup(title="Layout")
        page.add(layout_grp)

        col_row = Adw.SwitchRow(title="Two-column layout",
                                subtitle="Service order flows in two columns per section")
        col_row.set_active(p.get("columns", defaults["columns"]) >= 2)
        col_row.connect("notify::active",
                        lambda r, _p: self._on_preamble_changed(
                            key, "columns", 2 if r.get_active() else 1))
        layout_grp.add(col_row)

        # ── Headings ──────────────────────────────────────────────────────────
        hdg_grp = Adw.PreferencesGroup(title="Headings")
        page.add(hdg_grp)

        _HDG_LABELS = [
            "Bold small-caps + rule",
            "Bold small-caps",
            "Bold",
            "Plain",
        ]
        _HDG_KEYS = ["bold-smallcaps-rule", "bold-smallcaps", "bold", "plain"]
        hdg_model = Gtk.StringList.new(_HDG_LABELS)
        hdg_row = Adw.ComboRow(title="Element heading style", model=hdg_model)
        current_style = p.get("heading_style", defaults["heading_style"])
        try:
            hdg_row.set_selected(_HDG_KEYS.index(current_style))
        except ValueError:
            hdg_row.set_selected(0)

        def _on_hdg_selected(row, _prop):
            self._on_preamble_changed(key, "heading_style",
                                      _HDG_KEYS[row.get_selected()])

        hdg_row.connect("notify::selected", _on_hdg_selected)
        hdg_grp.add(hdg_row)

        scroll.set_child(page)
        return scroll

    def _build_preamble_panel(self) -> Gtk.Box:
        """Build the document template editor panel (font, margins, etc.)."""
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        hdr.set_margin_start(12); hdr.set_margin_end(12)
        hdr.set_margin_top(10); hdr.set_margin_bottom(8)

        hdr_lbl = Gtk.Label(label="Document Template")
        hdr_lbl.add_css_class("title-4")
        hdr_lbl.set_hexpand(True); hdr_lbl.set_xalign(0)
        hdr.append(hdr_lbl)

        self._preamble_ms_btn = Gtk.ToggleButton(label="Manuscript")
        self._preamble_ms_btn.set_active(True)
        self._preamble_ms_btn.add_css_class("flat")
        self._preamble_bul_btn = Gtk.ToggleButton(label="Bulletin")
        self._preamble_bul_btn.set_group(self._preamble_ms_btn)
        self._preamble_bul_btn.add_css_class("flat")
        toggle_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        toggle_box.add_css_class("linked")
        toggle_box.append(self._preamble_ms_btn)
        toggle_box.append(self._preamble_bul_btn)
        hdr.append(toggle_box)
        outer.append(hdr)
        outer.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        self._preamble_form_stack = Gtk.Stack()
        self._preamble_form_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._preamble_form_stack.set_transition_duration(100)
        self._preamble_form_stack.set_vexpand(True)
        self._preamble_form_stack.add_named(self._build_preamble_form("manuscript"), "manuscript")
        self._preamble_form_stack.add_named(self._build_preamble_form("bulletin"), "bulletin")
        outer.append(self._preamble_form_stack)

        def _on_type_toggled(btn):
            if btn.get_active():
                mode = "manuscript" if btn == self._preamble_ms_btn else "bulletin"
                self._preamble_form_stack.set_visible_child_name(mode)
                # Mirror in the preview so font/margin changes are immediately visible
                self._preview_mode = mode
                self._preview_scroll_y = 0
                if hasattr(self, "_preview_manuscript_btn"):
                    if mode == "manuscript":
                        self._preview_manuscript_btn.set_active(True)
                    else:
                        self._preview_bulletin_btn.set_active(True)
                self._do_preview_update()

        self._preamble_ms_btn.connect("toggled", _on_type_toggled)
        self._preamble_bul_btn.connect("toggled", _on_type_toggled)

        return outer

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

        # Reading chips — compact pill buttons, right-aligned
        self._reading_rows: dict[str, Gtk.Button] = {}
        self._reading_labels = {"ot": "First Reading", "psalm": "Psalm",
                                 "epistle": "Epistle",  "gospel": "Gospel"}
        self._reading_abbrs  = {"ot": "OT", "psalm": "Ps", "epistle": "Ep", "gospel": "Gos"}
        chips_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        chips_box.set_hexpand(True); chips_box.set_halign(Gtk.Align.END)
        for key in ("ot", "psalm", "epistle", "gospel"):
            btn = Gtk.Button(label=self._reading_abbrs[key])
            btn.add_css_class("pill"); btn.add_css_class("flat")
            btn.set_sensitive(False)
            btn.set_tooltip_text(self._reading_labels[key])
            btn.connect("clicked", lambda _b, k=key: self._on_reading_clicked(k))
            chips_box.append(btn)
            self._reading_rows[key] = btn
        rcl_row.append(chips_box)
        self.readings_card.append(rcl_row)

        # Observances now shown in the status bar centre — no in-card row needed

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
        self._order_hpaned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self._order_hpaned.set_shrink_start_child(False); self._order_hpaned.set_shrink_end_child(True)
        self._order_hpaned.set_position(220); self._order_hpaned.set_vexpand(True)

        # ── Order pane (left) ─────────────────────────────────────────────────
        order_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        order_box.set_size_request(160, -1)

        self._view_stack = Gtk.Stack(); self._view_stack.set_vexpand(True)

        self._flat_scroll = Gtk.ScrolledWindow()
        self._flat_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._flat_scroll.set_margin_start(12); self._flat_scroll.set_margin_end(12)
        self._flat_scroll.set_margin_top(8); self._flat_scroll.set_margin_bottom(6)
        self.order_listbox = Gtk.ListBox()
        self.order_listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.order_listbox.add_css_class("boxed-list")
        self.order_listbox.add_css_class("order-list")
        self.order_listbox.connect("row-selected", self._on_flat_row_selected)
        _list_key = Gtk.EventControllerKey()
        _list_key.connect("key-pressed", lambda ctrl, keyval, *_:
            (self.remove_item(), True)[1]
            if keyval == Gdk.KEY_Delete else False)
        self.order_listbox.add_controller(_list_key)
        placeholder = Adw.StatusPage(title="Service is empty",
            description="Double-click an element in the palette to add it, or drag elements here.",
            icon_name="rubric-symbolic")
        placeholder.set_vexpand(True)
        _new_svc_btn = Gtk.Button(label="Start with lectionary")
        _new_svc_btn.add_css_class("suggested-action")
        _new_svc_btn.set_halign(Gtk.Align.CENTER)
        _new_svc_btn.connect("clicked", lambda _: self._seed_lectionary_service_today())
        placeholder.set_child(_new_svc_btn)
        self.order_listbox.set_placeholder(placeholder)
        self._flat_scroll.set_child(self.order_listbox)
        self._view_stack.add_named(self._flat_scroll, "list")

        self._notebook = Gtk.Notebook()
        self._notebook.set_show_border(False); self._notebook.set_vexpand(True)
        self._notebook.set_scrollable(True)
        self._notebook.set_tab_pos(Gtk.PositionType.LEFT)
        self._notebook.set_margin_start(0); self._notebook.set_margin_end(8)
        self._notebook.set_margin_top(8); self._notebook.set_margin_bottom(6)
        self._view_stack.add_named(self._notebook, "tabs")

        self._view_stack.set_visible_child_name("tabs" if config.use_tabs else "list")

        # Season colour strip — 5px gradient bar at top of order panel
        self._order_season_strip = Gtk.DrawingArea()
        self._order_season_strip.set_size_request(-1, 5)
        def _draw_order_strip(_da, cr, w, _h):
            import cairo as _cairo
            r, g, b = self._colour_bar_rgb
            try:
                pat = _cairo.LinearGradient(0, 0, w, 0)
                pat.add_color_stop_rgba(0.0, r, g, b, 0.9)
                pat.add_color_stop_rgba(0.6, r, g, b, 0.65)
                pat.add_color_stop_rgba(1.0, r, g, b, 0.2)
                cr.set_source(pat)
            except Exception:
                cr.set_source_rgb(r, g, b)
            cr.paint()
        self._order_season_strip.set_draw_func(_draw_order_strip)
        order_box.append(self._order_season_strip)
        order_box.append(self._view_stack)

        # Time total bar
        self._time_bar = Gtk.Label()
        self._time_bar.set_xalign(1.0)
        self._time_bar.set_margin_start(12); self._time_bar.set_margin_end(12)
        self._time_bar.set_margin_top(2); self._time_bar.set_margin_bottom(0)
        self._time_bar.add_css_class("dim-label")
        self._time_bar.set_visible(False)
        order_box.append(self._time_bar)

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
        self._order_box = order_box
        self._order_hpaned.set_start_child(order_box)

        # ── Notes pane (right) ────────────────────────────────────────────────
        notes_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Focus mode banner — shown in F11 focus mode, hidden otherwise
        self._focus_banner = Gtk.Revealer()
        self._focus_banner.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self._focus_banner.set_transition_duration(180)
        focus_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        focus_bar.set_margin_start(12); focus_bar.set_margin_end(8)
        focus_bar.set_margin_top(6); focus_bar.set_margin_bottom(6)
        self._focus_elem_lbl = Gtk.Label()
        self._focus_elem_lbl.add_css_class("heading")
        self._focus_elem_lbl.set_hexpand(True); self._focus_elem_lbl.set_xalign(0)
        focus_bar.append(self._focus_elem_lbl)
        exit_focus_btn = Gtk.Button(label="Exit focus mode")
        exit_focus_btn.add_css_class("flat")
        exit_focus_btn.connect("clicked", lambda _: self._toggle_focus_mode())
        focus_bar.append(exit_focus_btn)
        self._focus_banner.set_child(focus_bar)
        self._focus_banner.set_reveal_child(False)
        notes_box.append(self._focus_banner)

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

        dur_lbl = Gtk.Label(label="min"); dur_lbl.add_css_class("dim-label")
        dur_lbl.set_margin_start(6); row1.append(dur_lbl)
        dur_adj = Gtk.Adjustment(value=0, lower=0, upper=120, step_increment=1)
        self.duration_spin = Gtk.SpinButton(adjustment=dur_adj, numeric=True)
        self.duration_spin.set_width_chars(3)
        self.duration_spin.set_tooltip_text("Estimated duration in minutes (0 = unset)")
        self.duration_spin.connect("value-changed", self._on_duration_changed)
        row1.append(self.duration_spin)

        self._bulletin_heading_lbl = Gtk.Label(label="Bulletin")
        self._bulletin_heading_lbl.set_use_markup(True)
        self.bulletin_toggle = Gtk.Button(
            tooltip_text="Bulletin heading only — element title appears in the bulletin, body text omitted")
        self.bulletin_toggle.set_child(self._bulletin_heading_lbl)
        self.bulletin_toggle.add_css_class("flat")
        self._bulletin_heading_only_active = False
        self.bulletin_toggle.connect("clicked", self._on_bulletin_toggled)
        row1.append(self.bulletin_toggle)

        self.bulletin_summary_entry = Gtk.Entry()
        self.bulletin_summary_entry.set_placeholder_text("bulletin note…")
        self.bulletin_summary_entry.set_width_chars(18)
        self.bulletin_summary_entry.set_tooltip_text(
            "Short line shown in the bulletin instead of the full content. "
            "Leave empty to show full content.")
        self.bulletin_summary_entry.connect("changed", self._on_bulletin_summary_changed)
        row1.append(self.bulletin_summary_entry)

        icon_btn = Gtk.MenuButton(icon_name="preferences-desktop-wallpaper-symbolic",
                                  tooltip_text="Set icon for this element")
        icon_btn.add_css_class("flat")
        icon_btn.set_popover(self._build_icon_picker_popover())
        self._icon_menu_btn = icon_btn
        row1.append(icon_btn)
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

        # Hymn sub-segment — single button opens unified lookup/search popover
        sep_hymn = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        sep_hymn.set_margin_start(6); sep_hymn.set_margin_end(6); row2.append(sep_hymn)

        self._theme_selected_btn = None
        self._hymn_search_pop = self._build_hymn_search_popover()
        self._hymn_search_pop.connect("show", lambda _: self._on_hymn_search_changed(
            self._hymn_search_entry.get_text().strip() if hasattr(self, "_hymn_search_entry") else ""))
        hymn_menu_btn = Gtk.MenuButton(label="Hymn",
                                       tooltip_text="Look up or search hymns",
                                       popover=self._hymn_search_pop)
        hymn_menu_btn.add_css_class("flat")
        self._hymn_toolbar_widgets = [sep_hymn, hymn_menu_btn]
        row2.append(hymn_menu_btn)

        # Action buttons
        sep_act = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        sep_act.set_margin_start(6); sep_act.set_margin_end(2); row2.append(sep_act)
        self._snip_btn = Gtk.Button(label="Snippet", tooltip_text="Insert snippet (Ctrl+Shift+I)")
        self._snip_btn.add_css_class("flat")
        self._snip_btn.connect("clicked", lambda _: self.open_snippets()); row2.append(self._snip_btn)
        self._hymn_mode_btn = Gtk.ToggleButton(label="Hymn",
                                               tooltip_text="Toggle hymn search and suggestions for this element")
        self._hymn_mode_btn.add_css_class("flat")
        self._hymn_mode_btn.connect("toggled", self._on_hymn_mode_toggled)
        row2.append(self._hymn_mode_btn)
        itb_rows.append(row2)

        self.item_toolbar_revealer.set_child(itb_rows)
        notes_box.append(self.item_toolbar_revealer)
        self.hymn_revealer = self.item_toolbar_revealer
        self.leader_revealer = self.item_toolbar_revealer

        # Unified content editor (replaces the old 3-tab Leader/Bulletin/Prep stack)
        self._content_widget = ElementContentWidget()
        self._content_widget.set_vexpand(True)
        self._content_widget.set_on_changed(self._on_content_typst_changed)
        self._content_widget.set_on_rubric_changed(self._on_rubric_note_changed)
        notes_box.append(self._content_widget)

        # Scripture reference detection banner
        self._scripture_detect_rev = Gtk.Revealer()
        self._scripture_detect_rev.set_transition_type(Gtk.RevealerTransitionType.SLIDE_UP)
        self._scripture_detect_rev.set_transition_duration(150)
        sd_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        sd_bar.set_margin_start(12); sd_bar.set_margin_end(12)
        sd_bar.set_margin_top(4); sd_bar.set_margin_bottom(4)
        self._scripture_detect_lbl = Gtk.Label()
        self._scripture_detect_lbl.add_css_class("caption")
        self._scripture_detect_lbl.set_hexpand(True); self._scripture_detect_lbl.set_xalign(0)
        sd_bar.append(self._scripture_detect_lbl)
        self._scripture_fetch_btn = Gtk.Button(label="Fetch text")
        self._scripture_fetch_btn.add_css_class("flat"); self._scripture_fetch_btn.add_css_class("accent")
        self._scripture_fetch_btn.connect("clicked", self._on_scripture_banner_fetch)
        sd_bar.append(self._scripture_fetch_btn)
        sd_dismiss = Gtk.Button(icon_name="window-close-symbolic")
        sd_dismiss.add_css_class("flat")
        sd_dismiss.connect("clicked", lambda _: self._scripture_detect_rev.set_reveal_child(False))
        sd_bar.append(sd_dismiss)
        self._scripture_detect_rev.set_child(sd_bar)
        notes_box.append(self._scripture_detect_rev)

        self._order_hpaned.set_end_child(notes_box)
        box.append(self._order_hpaned)

        # Hymn suggestions strip — full width across order + notes panes
        self.sugg_revealer = Gtk.Revealer()
        self.sugg_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_UP)
        self.sugg_revealer.set_transition_duration(200)
        self._sugg_dismissed = False
        sugg_outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        sugg_outer.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        sugg_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self._sugg_chips_box = Gtk.FlowBox()
        self._sugg_chips_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self._sugg_chips_box.set_max_children_per_line(50)
        self._sugg_chips_box.set_min_children_per_line(1)
        self._sugg_chips_box.set_column_spacing(4); self._sugg_chips_box.set_row_spacing(4)
        self._sugg_chips_box.set_margin_start(10); self._sugg_chips_box.set_margin_end(6)
        self._sugg_chips_box.set_margin_bottom(6); self._sugg_chips_box.set_margin_top(6)
        self._sugg_chips_box.set_hexpand(True)
        sugg_close_btn = Gtk.Button(icon_name="window-close-symbolic",
                                    tooltip_text="Dismiss suggestions",
                                    valign=Gtk.Align.CENTER)
        sugg_close_btn.add_css_class("flat")
        sugg_close_btn.set_margin_end(6)
        def _dismiss_suggestions(_btn):
            self._sugg_dismissed = True
            self.sugg_revealer.set_reveal_child(False)
        sugg_close_btn.connect("clicked", _dismiss_suggestions)
        sugg_row.append(self._sugg_chips_box)
        sugg_row.append(sugg_close_btn)
        sugg_outer.append(sugg_row)
        self.sugg_revealer.set_child(sugg_outer)
        box.append(self.sugg_revealer)

        return box

    # ── Colour bar ────────────────────────────────────────────────────────────

    def _draw_colour_bar(self, _da, cr, _w, _h):
        r,g,b = self._colour_bar_rgb; cr.set_source_rgb(r,g,b); cr.paint()

    # ── Row factories ─────────────────────────────────────────────────────────

    def _make_item_row(self, si: ServiceItem, global_idx: int) -> Adw.ActionRow:
        preview = self._note_preview(si.content_typst) or self._scripture_inline_preview(si.name)
        if si.leader and preview:
            subtitle_text = f"{si.leader} · {preview}"
        else:
            subtitle_text = si.leader or preview
        row = Adw.ActionRow(title=GLib.markup_escape_text(si.name), subtitle=GLib.markup_escape_text(subtitle_text))
        row.set_subtitle_lines(1); row._entry = si
        colour = _section_colour(si.section)
        dot = Gtk.Label(); dot.set_markup(f'<span color="{colour}">⬤</span>'); dot.set_valign(Gtk.Align.CENTER)
        row.add_prefix(dot)
        # User-assigned icon takes priority; fall back to auto type icon
        user_icon = getattr(si, "icon", "")
        _ico_name = user_icon or _item_type_icon(si.name)
        if _ico_name:
            _ico = Gtk.Image(icon_name=_ico_name, pixel_size=14)
            _ico.add_css_class("dim-label"); _ico.set_valign(Gtk.Align.CENTER)
            _ico.set_margin_start(2)
            row.add_prefix(_ico)
        handle = Gtk.Label(label="⠿"); handle.add_css_class("dim-label"); handle.add_css_class("drag-handle"); handle.set_valign(Gtk.Align.CENTER)
        row.add_suffix(handle)
        if not si.show_in_bulletin:
            row.set_opacity(0.45)
        elif getattr(si, "bulletin_heading_only", False):
            row.set_opacity(0.7)
        self._attach_dnd(row, global_idx); return row

    def _make_divider_row(self, div: SectionDivider, global_idx: int) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow(); row._entry = div
        bx = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        bx.set_margin_top(4); bx.set_margin_bottom(4); bx.set_margin_start(8); bx.set_margin_end(8)
        bx.add_css_class("divider-pill")
        colour = _section_colour(div.title)
        # Left accent stripe in section colour
        r, g, b = _hex_to_rgb(colour)
        stripe = Gtk.DrawingArea(); stripe.set_size_request(4, -1)
        def _draw_stripe(_da, cr, _w, _h, _r=r, _g=g, _b=b):
            cr.set_source_rgb(_r, _g, _b); cr.paint()
        stripe.set_draw_func(_draw_stripe)
        stripe.set_valign(Gtk.Align.FILL)
        bx.append(stripe)
        dot = Gtk.Label(); dot.set_markup(f'<span color="{colour}">⬤</span>'); dot.set_valign(Gtk.Align.CENTER); bx.append(dot)
        handle = Gtk.Label(label="⠿"); handle.add_css_class("dim-label"); handle.add_css_class("drag-handle"); handle.set_valign(Gtk.Align.CENTER); bx.append(handle)
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
            row.remove_css_class("drop-target")
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
        """Tab label: rotated DrawingArea so text reads bottom-to-top with correct layout size."""
        import math
        from gi.repository import PangoCairo

        text = div.title if div else "Service"

        da = Gtk.DrawingArea()
        da.add_css_class("rubric-vtab")

        # Estimate pixel extents: ~10px per char at 13pt, ~17px tall
        est_w = max(55, len(text) * 10)
        est_h = 17
        # DrawingArea size request: width = text height + padding, height = text width + padding
        da.set_size_request(est_h + 10, est_w + 14)

        def draw(widget, cr, w, h, t=text):
            style = widget.get_style_context()
            color = style.get_color()
            cr.set_source_rgba(color.red, color.green, color.blue, color.alpha)
            layout = widget.create_pango_layout(t)
            fd = Pango.FontDescription.from_string("13")
            layout.set_font_description(fd)
            _ink, log = layout.get_pixel_extents()
            tw, th = log.width, log.height
            cr.save()
            cr.translate(w / 2.0, h / 2.0)
            cr.rotate(-math.pi / 2.0)   # 90 deg CCW => bottom-to-top
            cr.translate(-tw / 2.0, -th / 2.0)
            PangoCairo.show_layout(cr, layout)
            cr.restore()

        da.set_draw_func(draw)

        if div is not None:
            gesture = Gtk.GestureClick()
            gesture.set_button(3)
            def on_right_click(_g, _n, _x, _y, d=div, widget=da):
                menu = Gio.Menu()
                menu.append("Rename...", "win.tab-rename")
                menu.append("Delete section...", "win.tab-delete")
                popover = Gtk.PopoverMenu.new_from_model(menu)
                popover.set_parent(widget)
                self._tab_ctx_div = d
                popover.popup()
            gesture.connect("pressed", on_right_click)
            da.add_controller(gesture)

        return da

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
        self._update_time_total()

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
        self._leader_undo_pushed = False
        if row and hasattr(row,"_entry") and isinstance(row._entry, ServiceItem):
            si = row._entry
            try: self._selected_global_idx = self.service_entries.index(si)
            except ValueError: self._selected_global_idx = -1
            self._content_widget.set_content(si.content_typst)
            self._content_widget.set_rubric_note(getattr(si, "rubric_note", ""))
            # Show the combined toolbar
            self.item_toolbar_revealer.set_reveal_child(True)
            self.leader_entry.set_text(si.leader)
            # Bulletin heading-only toggle — update label without triggering handler
            _bho = getattr(si, "bulletin_heading_only", False)
            self._bulletin_heading_only_active = _bho
            if _bho:
                self._bulletin_heading_lbl.set_markup("<b>Bulletin</b>")
            else:
                self._bulletin_heading_lbl.set_text("Bulletin")
            self.duration_spin.set_value(getattr(si, "duration", 0))
            self.bulletin_summary_entry.set_text(getattr(si, "bulletin_summary", ""))
            # Set hymn toggle and sync visibility directly (handler blocked by _updating_note)
            is_hymn = _HYMN_OK and _is_hymn_element(si.name)
            self._hymn_mode_btn.set_active(is_hymn)
            for w in self._hymn_toolbar_widgets: w.set_visible(is_hymn)
            if is_hymn:
                self._sugg_dismissed = False
            self.sugg_revealer.set_reveal_child(
                is_hymn and getattr(self, "_hymn_suggestions_available", False))
            # Update focus mode banner
            if getattr(self, "_focus_mode", False):
                self._focus_elem_lbl.set_text(si.name)
        else:
            self._selected_global_idx = -1
            self._content_widget.set_content("")
            self.item_toolbar_revealer.set_reveal_child(False)
            self.leader_entry.set_text("")
            self.duration_spin.set_value(0)
            self.bulletin_summary_entry.set_text("")
            self._hymn_mode_btn.set_active(False)
            for w in self._hymn_toolbar_widgets: w.set_visible(False)
            self.sugg_revealer.set_reveal_child(False)
        self._updating_note = False

    # ── Palette actions ───────────────────────────────────────────────────────

    def _on_palette_row_activated(self, _lb, row):
        item = ServiceItem(row._item_name, row._section_name)
        default_note = config.element_defaults.get(row._item_name, "")
        if default_note and not item.content_typst:
            item.content_typst = default_note
        self._push_undo(); self._add_entry(item)
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
        if idx < 0 and config.use_tabs:
            # No item selected — insert at end of currently visible tab's section
            page = self._notebook.get_current_page()
            if 0 <= page < len(self._tab_listboxes):
                section_div, _lb = self._tab_listboxes[page]
                ins = len(self.service_entries)
                in_section = section_div is None
                for i, e in enumerate(self.service_entries):
                    if e.is_divider:
                        if e is section_div:
                            in_section = True; ins = i + 1
                        elif in_section:
                            ins = i; break
                    elif in_section:
                        ins = i + 1
                self.service_entries.insert(ins, entry)
                self._refresh_order_list(select_index=ins)
                self._mark_modified()
                return
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
        win = Adw.Window(transient_for=self, modal=True)
        win.set_title("Add custom element")
        win.set_default_size(360, -1)
        tv = Adw.ToolbarView()
        hdr = Adw.HeaderBar(); tv.add_top_bar(hdr)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.set_margin_top(12); outer.set_margin_bottom(12)
        outer.set_margin_start(16); outer.set_margin_end(16)

        grp = Adw.PreferencesGroup()
        name_row = Adw.EntryRow(title="Element name")
        grp.add(name_row)

        # Inline suggestion list — shown when ≥2 chars match library entries
        sugg_list = Gtk.ListBox()
        sugg_list.set_selection_mode(Gtk.SelectionMode.NONE)
        sugg_list.add_css_class("boxed-list")
        sugg_list.set_margin_start(0); sugg_list.set_margin_end(0)
        sugg_revealer = Gtk.Revealer()
        sugg_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        sugg_revealer.set_child(sugg_list)
        outer.append(sugg_revealer)

        def _refresh_suggestions(entry):
            prefix = entry.get_text().strip()
            while sugg_list.get_first_child():
                sugg_list.remove(sugg_list.get_first_child())
            if len(prefix) < 2:
                sugg_revealer.set_reveal_child(False); return
            try:
                from rubric_package.db import element_suggestions as _esugg
                matches = _esugg(prefix)
            except Exception:
                sugg_revealer.set_reveal_child(False); return
            if not matches:
                sugg_revealer.set_reveal_child(False); return
            for m in matches:
                r = Gtk.ListBoxRow(); r._sugg_name = m["name"]
                lbl_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
                lbl_box.set_margin_start(12); lbl_box.set_margin_end(12)
                lbl_box.set_margin_top(6); lbl_box.set_margin_bottom(6)
                nl = Gtk.Label(label=m["name"]); nl.set_hexpand(True); nl.set_xalign(0)
                lbl_box.append(nl)
                cl = Gtk.Label(label=f"{m['use_count']}×")
                cl.add_css_class("caption"); cl.add_css_class("dim-label")
                lbl_box.append(cl)
                r.set_child(lbl_box); sugg_list.append(r)
            sugg_revealer.set_reveal_child(True)

        def _on_sugg_activated(_lb, row):
            name_row.set_text(row._sugg_name)
            sugg_revealer.set_reveal_child(False)

        name_row.connect("changed", _refresh_suggestions)
        sugg_list.connect("row-activated", _on_sugg_activated)

        section_row = Adw.ComboRow(title="Palette section")
        pal = get_palette()
        section_row.set_model(Gtk.StringList.new([s for s, _ in pal]))
        section_row.set_expression(
            Gtk.PropertyExpression.new(Gtk.StringObject, None, "string"))
        grp.add(section_row)
        outer.append(grp)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_margin_top(16)
        sp = Gtk.Box(); sp.set_hexpand(True); btn_row.append(sp)
        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda _: win.close())
        btn_row.append(cancel_btn)
        add_btn = Gtk.Button(label="Add")
        add_btn.add_css_class("suggested-action")

        def on_add(_b):
            nm = name_row.get_text().strip()
            pal2 = get_palette()
            sec = pal2[section_row.get_selected()][0] if pal2 else ""
            if nm:
                self._push_undo(); self._add_entry(ServiceItem(nm, sec))
            win.close()

        add_btn.connect("clicked", on_add)
        name_row.connect("entry-activated", lambda _: on_add(None))
        btn_row.append(add_btn)
        outer.append(btn_row)

        tv.set_content(outer); win.set_content(tv); win.present()

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
        focus = self.get_focus()
        if isinstance(focus, Gtk.TextView):
            buf = focus.get_buffer()
            if buf.get_can_undo():
                buf.undo()
            return
        if not self._undo_stack: return
        self._redo_stack.append([e.to_dict() for e in self.service_entries])
        self.redo_btn.set_sensitive(True)
        self.service_entries = [_entry_from_dict(d) for d in self._undo_stack.pop()]
        self._refresh_order_list(); self.undo_btn.set_sensitive(bool(self._undo_stack)); self._mark_modified()

    def redo(self):
        focus = self.get_focus()
        if isinstance(focus, Gtk.TextView):
            buf = focus.get_buffer()
            if buf.get_can_redo():
                buf.redo()
            return
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
        prefix, number = result
        self.hymn_status.set_label("Looking up…")
        if hasattr(self, "_hymn_manual_box"):
            self._hymn_manual_box.set_visible(False)
            self._hymn_manual_entry.set_text("")
        def on_result(title, error):
            if error:
                self.hymn_status.set_label(f"Couldn't fetch — enter the title manually:")
                self._hymn_manual_box.set_visible(True)
                self._hymn_manual_entry.grab_focus()
                self._hymn_manual_ref = (prefix, number)
                return
            # Short format: "VU 16 — O Come, O Come, Emmanuel"
            short_ref = f"{prefix.upper()} {number}"
            hymn_line = f"{short_ref} — {title}"
            self.hymn_status.set_label(hymn_line)
            idx = self._selected_index()
            if not (0 <= idx < len(self.service_entries)): return
            entry = self.service_entries[idx]
            if not isinstance(entry, ServiceItem): return
            self._push_undo()
            entry.content_typst = (hymn_line + "\n" + entry.content_typst
                                   if entry.content_typst else hymn_line)
            self._content_widget.set_content(entry.content_typst)
            row = self._find_row_for_index(idx)
            if isinstance(row, Adw.ActionRow):
                preview = self._note_preview(entry.content_typst) or self._scripture_inline_preview(entry.name)
                sub = f"{entry.leader} · {preview}" if entry.leader and preview else (entry.leader or preview)
                row.set_subtitle(sub)
            self._mark_modified()
        lookup_hymn(prefix, number, on_result)

    def _save_manual_hymn(self):
        title = self._hymn_manual_entry.get_text().strip()
        if not title:
            return
        ref = getattr(self, "_hymn_manual_ref", None)
        if not ref:
            return
        prefix, number = ref
        key = f"{prefix}{number}"
        try:
            from rubric_package.db import hymn_set as _hset
            _hset(key, title)
        except Exception:
            pass
        short_ref = f"{prefix} {number}"
        hymn_line = f"{short_ref} — {title}"
        self.hymn_status.set_label(hymn_line)
        self._hymn_manual_box.set_visible(False)
        self._hymn_manual_entry.set_text("")
        idx = self._selected_index()
        if not (0 <= idx < len(self.service_entries)):
            return
        entry = self.service_entries[idx]
        if not isinstance(entry, ServiceItem):
            return
        self._push_undo()
        entry.content_typst = (hymn_line + "\n" + entry.content_typst
                               if entry.content_typst else hymn_line)
        self._content_widget.set_content(entry.content_typst)
        row = self._find_row_for_index(idx)
        if isinstance(row, Adw.ActionRow):
            preview = self._note_preview(entry.content_typst) or self._scripture_inline_preview(entry.name)
            sub = f"{entry.leader} · {preview}" if entry.leader and preview else (entry.leader or preview)
            row.set_subtitle(sub)
        self._mark_modified()

    def _build_hymn_search_popover(self) -> Gtk.Popover:
        pop = Gtk.Popover()
        pop.set_has_arrow(False)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.set_size_request(460, -1)

        # ── Tab switcher ──────────────────────────────────────────────────────
        stack = Gtk.Stack()
        stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        stack.set_transition_duration(150)
        switcher = Gtk.StackSwitcher()
        switcher.set_stack(stack)
        switcher.set_halign(Gtk.Align.CENTER)
        switcher.set_margin_top(8)
        switcher.set_margin_bottom(4)
        outer.append(switcher)
        outer.append(stack)

        # ── Lookup page (number-based) ─────────────────────────────────────────
        lookup_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        lookup_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        lookup_row.set_margin_top(10); lookup_row.set_margin_bottom(6)
        lookup_row.set_margin_start(10); lookup_row.set_margin_end(10)

        self.hymn_entry = Gtk.Entry()
        self.hymn_entry.set_placeholder_text("VU 16")
        self.hymn_entry.set_width_chars(9)
        self.hymn_entry.set_hexpand(True)
        self.hymn_entry.connect("activate", lambda _: self._do_hymn_lookup())
        lookup_row.append(self.hymn_entry)

        lookup_btn = Gtk.Button(label="Look up")
        lookup_btn.add_css_class("suggested-action")
        lookup_btn.connect("clicked", lambda _: self._do_hymn_lookup())
        lookup_row.append(lookup_btn)
        lookup_page.append(lookup_row)

        self.hymn_status = Gtk.Label()
        self.hymn_status.add_css_class("dim-label"); self.hymn_status.add_css_class("caption")
        self.hymn_status.set_wrap(True); self.hymn_status.set_xalign(0)
        self.hymn_status.set_margin_start(10); self.hymn_status.set_margin_end(10)
        self.hymn_status.set_margin_bottom(4)
        lookup_page.append(self.hymn_status)

        # Manual title entry — shown when lookup fails or user wants to add directly
        manual_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        manual_box.set_margin_start(10); manual_box.set_margin_end(10)
        manual_box.set_margin_bottom(10)
        manual_box.set_visible(False)
        self._hymn_manual_box = manual_box

        self._hymn_manual_entry = Gtk.Entry()
        self._hymn_manual_entry.set_placeholder_text("Enter title from your hymnal…")
        self._hymn_manual_entry.set_hexpand(True)
        self._hymn_manual_entry.connect("activate", lambda _: self._save_manual_hymn())
        manual_box.append(self._hymn_manual_entry)

        save_btn = Gtk.Button(label="Save")
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", lambda _: self._save_manual_hymn())
        manual_box.append(save_btn)
        lookup_page.append(manual_box)

        stack.add_titled(lookup_page, "lookup", "Lookup")

        # ── By Title page ─────────────────────────────────────────────────────
        title_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        se = Gtk.SearchEntry()
        se.set_placeholder_text("Search hymn titles…")
        se.set_margin_top(4); se.set_margin_bottom(6)
        se.set_margin_start(8); se.set_margin_end(8)
        title_page.append(se)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_height(200); scroll.set_max_content_height(340)
        self._hymn_search_list = Gtk.ListBox()
        self._hymn_search_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self._hymn_search_list.add_css_class("boxed-list")
        self._hymn_search_list.set_margin_start(8); self._hymn_search_list.set_margin_end(8)
        self._hymn_search_list.set_margin_bottom(4)
        scroll.set_child(self._hymn_search_list)
        title_page.append(scroll)

        hint = Gtk.Label(label="Searches your local hymn cache. Use the Lookup tab to fetch and cache individual hymns by number.")
        hint.add_css_class("caption"); hint.add_css_class("dim-label")
        hint.set_wrap(True); hint.set_xalign(0)
        hint.set_margin_start(8); hint.set_margin_end(8); hint.set_margin_bottom(8)
        title_page.append(hint)

        stack.add_titled(title_page, "search", "By Title")

        # ── By Theme page ─────────────────────────────────────────────────────
        theme_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Flow of theme chips — no scroll, let it expand naturally
        self._theme_flow = Gtk.FlowBox()
        self._theme_flow.set_max_children_per_line(3)
        self._theme_flow.set_min_children_per_line(2)
        self._theme_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self._theme_flow.set_homogeneous(True)
        self._theme_flow.set_row_spacing(4); self._theme_flow.set_column_spacing(4)
        self._theme_flow.set_margin_start(8); self._theme_flow.set_margin_end(8)
        self._theme_flow.set_margin_top(8); self._theme_flow.set_margin_bottom(6)
        for name in _get_theme_names():
            btn = Gtk.ToggleButton(label=name)
            btn.add_css_class("flat")
            btn.connect("toggled", lambda b, t=name: self._on_theme_chip_clicked(b, t))
            self._theme_flow.append(btn)
        theme_page.append(self._theme_flow)

        theme_page.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # Hymns for selected theme
        theme_scroll = Gtk.ScrolledWindow()
        theme_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        theme_scroll.set_min_content_height(180); theme_scroll.set_max_content_height(320)
        self._theme_hymn_list = Gtk.ListBox()
        self._theme_hymn_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self._theme_hymn_list.add_css_class("boxed-list")
        self._theme_hymn_list.set_margin_start(8); self._theme_hymn_list.set_margin_end(8)
        self._theme_hymn_list.set_margin_top(6); self._theme_hymn_list.set_margin_bottom(8)

        # Placeholder row (shown until a theme is selected)
        self._theme_placeholder = Gtk.ListBoxRow()
        self._theme_placeholder.set_activatable(False)
        ph_lbl = Gtk.Label(label="Select a theme above")
        ph_lbl.add_css_class("dim-label"); ph_lbl.add_css_class("caption")
        ph_lbl.set_margin_top(16); ph_lbl.set_margin_bottom(16)
        self._theme_placeholder.set_child(ph_lbl)
        self._theme_hymn_list.append(self._theme_placeholder)

        theme_scroll.set_child(self._theme_hymn_list)
        theme_page.append(theme_scroll)

        stack.add_titled(theme_page, "themes", "By Theme")

        self._hymn_search_entry = se
        se.connect("search-changed", lambda e: self._on_hymn_search_changed(e.get_text().strip()))
        pop.set_child(outer)
        return pop

    def _on_hymn_search_changed(self, query: str):
        while self._hymn_search_list.get_first_child():
            self._hymn_search_list.remove(self._hymn_search_list.get_first_child())
        results = search_hymns(query) if len(query) >= 2 else search_hymns("")
        if not results:
            row = Gtk.ListBoxRow(); row.set_activatable(False)
            lbl = Gtk.Label(label="No hymns cached yet — use the Lookup tab to fetch by number")
            lbl.add_css_class("dim-label"); lbl.add_css_class("caption")
            lbl.set_margin_top(8); lbl.set_margin_bottom(8)
            row.set_child(lbl); self._hymn_search_list.append(row)
            return
        for r in results:
            ref = f"{r['book']} {r['number']}"
            line = f"{ref} — {r['title']}"
            row = Adw.ActionRow(title=r["title"], subtitle=ref)
            row.set_activatable(True)
            row.connect("activated", lambda _r, l=line: self._inject_hymn_line(l))
            self._hymn_search_list.append(row)

    def _on_theme_chip_clicked(self, btn: Gtk.ToggleButton, theme: str):
        if not btn.get_active():
            # Being untoggled — clear list
            self._theme_selected_btn = None
            while self._theme_hymn_list.get_first_child():
                self._theme_hymn_list.remove(self._theme_hymn_list.get_first_child())
            self._theme_hymn_list.append(self._theme_placeholder)
            return

        # Untoggle previous selection
        if self._theme_selected_btn and self._theme_selected_btn is not btn:
            self._theme_selected_btn.set_active(False)
        self._theme_selected_btn = btn

        while self._theme_hymn_list.get_first_child():
            self._theme_hymn_list.remove(self._theme_hymn_list.get_first_child())

        hymns = _get_theme_hymns(theme)
        if not hymns:
            row = Gtk.ListBoxRow(); row.set_activatable(False)
            lbl = Gtk.Label(label="No hymns found for this theme")
            lbl.add_css_class("dim-label"); lbl.add_css_class("caption")
            lbl.set_margin_top(8); lbl.set_margin_bottom(8)
            row.set_child(lbl); self._theme_hymn_list.append(row)
            return
        for prefix, number, title in hymns:
            ref = f"{prefix} {number}"
            line = f"{ref} — {title}"
            row = Adw.ActionRow(title=title, subtitle=ref)
            row.set_activatable(True)
            row.connect("activated", lambda _r, l=line: self._inject_hymn_line(l))
            self._theme_hymn_list.append(row)

    def _inject_hymn_line(self, hymn_line: str):
        self._hymn_search_pop.popdown()
        idx = self._selected_index()
        if not (0 <= idx < len(self.service_entries)): return
        entry = self.service_entries[idx]
        if not isinstance(entry, ServiceItem): return
        entry.content_typst = (hymn_line + "\n" + entry.content_typst
                               if entry.content_typst else hymn_line)
        self._content_widget.set_content(entry.content_typst)
        row = self._find_row_for_index(idx)
        if isinstance(row, Adw.ActionRow):
            row.set_subtitle(self._note_preview(entry.content_typst))
        self._mark_modified()

    # ── Bible viewer ──────────────────────────────────────────────────────────

    def _on_reading_clicked(self, key):
        ref = self._current_readings.get(key,"")
        if not ref or ref=="—": return
        def _insert(text, k=key):
            self._on_bible_insert(text)
            self._mark_reading_inserted(k)
        BibleViewer(ref, _insert, translation=config.bible_translation, esv_key=config.bible_api_key_esv, transient_for=self).present()

    def _mark_reading_inserted(self, key: str):
        if not hasattr(self, "_inserted_readings"):
            self._inserted_readings: set[str] = set()
        self._inserted_readings.add(key)
        btn = self._reading_rows.get(key)
        if btn:
            btn.add_css_class("success")

    def _on_bible_insert(self, text):
        idx = self._selected_index()
        if not (0 <= idx < len(self.service_entries)): return
        entry = self.service_entries[idx]
        if not isinstance(entry, ServiceItem): return
        self._push_undo()
        sep = "\n\n" if entry.content_typst else ""
        entry.content_typst = entry.content_typst + sep + text
        self._content_widget.set_content(entry.content_typst)
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

    _BIBLE_REF_RE = re.compile(
        r'\b((?:[1-3]\s*)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(\d+:\d+(?:[–\-]\d+)?)\b'
    )

    def _scripture_inline_preview(self, name: str) -> str:
        """Return a short verse snippet if the element name is a Bible reference and it's cached."""
        m = self._BIBLE_REF_RE.search(name)
        if not m:
            return ""
        ref = f"{m.group(1)} {m.group(2)}"
        try:
            from rubric_package.db import bible_get as _bg
            translation = getattr(config, "bible_translation", "web")
            text = _bg(f"{translation}:{ref}")
            if not text:
                return ""
            plain = strip_typst_plain(text) if text.startswith('#') else text
            words = plain.split()
            return '"' + ' '.join(words[:8]) + ('…"' if len(words) > 8 else '"')
        except Exception:
            return ""

    def _note_preview(self, note: str) -> str:
        if not note:
            return ""
        first_line = strip_typst_plain(note).split('\n')[0].strip()
        words = first_line.split()
        return ' '.join(words[:5]) + ('…' if len(words) > 5 else '')

    def _on_content_typst_changed(self, content: str):
        """Called by ElementContentWidget when the user edits content."""
        if self._updating_note:
            return
        idx = self._selected_index()
        if not (0 <= idx < len(self.service_entries)):
            return
        entry = self.service_entries[idx]
        if not isinstance(entry, ServiceItem):
            return
        entry.content_typst = content
        row = self._find_row_for_index(idx)
        if isinstance(row, Adw.ActionRow):
            preview = self._note_preview(content) or self._scripture_inline_preview(entry.name)
            sub = f"{entry.leader} · {preview}" if entry.leader and preview else (entry.leader or preview)
            row.set_subtitle(sub)
        self._mark_modified()
        self._detect_scripture_ref(content)

    def _on_rubric_note_changed(self, text: str):
        """Called by ElementContentWidget when the rubric note is edited."""
        if self._updating_note:
            return
        idx = self._selected_index()
        if not (0 <= idx < len(self.service_entries)):
            return
        entry = self.service_entries[idx]
        if not isinstance(entry, ServiceItem):
            return
        entry.rubric_note = text
        self._mark_modified()

    # ── Icon picker ───────────────────────────────────────────────────────────

    _ELEMENT_ICONS = [
        # Music & worship
        "audio-headphones-symbolic",      # Hymn / music
        "audio-x-generic-symbolic",       # Anthem
        "media-playback-start-symbolic",  # Prelude / postlude
        # Scripture & word
        "user-bookmarks-symbolic",        # Scripture reading
        "accessories-text-editor-symbolic",  # Sermon / message
        "format-text-rich-symbolic",      # Homily
        # Prayer & liturgy
        "emoji-body-symbolic",            # Prayer / blessing
        "emblem-important-symbolic",      # Commissioning
        "emblem-default-symbolic",        # Benediction
        # Sacraments & rites
        "starred-symbolic",               # Special occasion
        "object-select-symbolic",         # Affirmation
        "appointment-symbolic",           # Lord's Supper
        # People & community
        "system-users-symbolic",          # Land acknowledgement
        "contact-new-symbolic",           # Welcome
        "preferences-desktop-personal-symbolic",  # Children's time
        # Offering & response
        "emblem-money-symbolic",          # Offering
        "view-list-symbolic",             # Announcements
        # Misc
        "weather-clear-symbolic",         # Rainbow candle
        "go-home-symbolic",               # Gathering
        "view-fullscreen-symbolic",       # Sending
        "edit-find-symbolic",             # Scripture search
        "help-about-symbolic",            # Info
        "dialog-information-symbolic",    # Notice
        "go-up-symbolic",                 # Opening
        "go-down-symbolic",               # Closing
        "media-record-symbolic",          # Practice
        "appointment-new-symbolic",       # New appointment
        "clock-symbolic",                 # Timed element
        "flag-symbolic",                  # Special flag
    ]

    def _build_icon_picker_popover(self) -> Gtk.Popover:
        pop = Gtk.Popover()
        pop.set_has_arrow(True)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        outer.set_margin_top(8); outer.set_margin_bottom(8)
        outer.set_margin_start(8); outer.set_margin_end(8)

        lbl = Gtk.Label(label="Element icon")
        lbl.add_css_class("heading"); lbl.set_xalign(0)
        outer.append(lbl)

        grid = Gtk.FlowBox()
        grid.set_selection_mode(Gtk.SelectionMode.NONE)
        grid.set_max_children_per_line(8)
        grid.set_column_spacing(2); grid.set_row_spacing(2)

        # None option (clear icon)
        clear_btn = Gtk.Button(label="—", tooltip_text="No icon (use auto-detect)")
        clear_btn.add_css_class("flat")
        def on_clear(_b):
            idx = self._selected_index()
            if 0 <= idx < len(self.service_entries):
                si = self.service_entries[idx]
                if isinstance(si, ServiceItem):
                    si.icon = ""
                    self._refresh_order_list(idx)
                    self._mark_modified()
            pop.popdown()
        clear_btn.connect("clicked", on_clear)
        grid.append(clear_btn)

        for ico in self._ELEMENT_ICONS:
            btn = Gtk.Button(tooltip_text=ico)
            btn.add_css_class("flat")
            img = Gtk.Image(icon_name=ico, pixel_size=18)
            btn.set_child(img)
            def on_ico(_b, icon=ico):
                idx = self._selected_index()
                if 0 <= idx < len(self.service_entries):
                    si = self.service_entries[idx]
                    if isinstance(si, ServiceItem):
                        si.icon = icon
                        self._refresh_order_list(idx)
                        self._mark_modified()
                pop.popdown()
            btn.connect("clicked", on_ico)
            grid.append(btn)

        outer.append(grid)
        pop.set_child(outer)
        return pop

    def _detect_scripture_ref(self, text: str):
        """Show inline banner if a scripture reference is found in the note."""
        if not hasattr(self, "_scripture_detect_rev"):
            return
        # Only detect if content is short (i.e. a typed reference, not a full passage)
        if len(text.strip()) > 120 or text.strip().startswith('#scripture'):
            self._scripture_detect_rev.set_reveal_child(False)
            return
        m = re.search(
            r'\b((?:[1-3]\s*)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(\d+:\d+(?:[–\-]\d+)?)\b',
            text.strip()
        )
        if m:
            ref = f"{m.group(1)} {m.group(2)}"
            self._scripture_detect_lbl.set_text(f"Scripture detected: {ref}")
            self._scripture_fetch_btn._detected_ref = ref
            self._scripture_detect_rev.set_reveal_child(True)
        else:
            self._scripture_detect_rev.set_reveal_child(False)

    def _on_scripture_banner_fetch(self, btn):
        ref = getattr(btn, "_detected_ref", None)
        if not ref:
            return
        self._scripture_detect_rev.set_reveal_child(False)
        win = BibleViewer(ref, self._on_bible_insert,
                          translation=config.bible_translation,
                          esv_key=config.bible_api_key_esv,
                          transient_for=self)
        win.present()


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
                f'<span color="{colour}">●  Year {year} · {season}</span>'
            )
            self._lect_label.set_tooltip_text(
                f"Today: {info['week']} — RCL Year {year}"
            )
        except Exception:
            self._lect_label.set_text("")
        return True  # keep the daily timer running

    def _set_date_label(self, text: str):
        if hasattr(self, "_date_label_widget"):
            self._date_label_widget.set_text(text)

    def _on_calendar_day_selected(self, cal):
        gd = cal.get_date()
        from datetime import date as pydate
        d = pydate(gd.get_year(), gd.get_month(), gd.get_day_of_month())
        self.selected_date = d; self._set_date_label(d.strftime("%-d %B %Y"))
        self._update_readings(d); self._mark_modified()

    def _on_clear_date(self, _):
        self.selected_date = None; self._set_date_label("No date selected")
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
            show_stepper = bool(override_sunday) or (not is_sunday and not is_special)
        else:
            # Weekday: jump to next Sunday by default
            days_until_sunday = (6 - weekday) % 7 or 7
            next_sunday = d + timedelta(days=days_until_sunday)
            self._readings_sunday = next_sunday
            info = get_liturgical_info(next_sunday)
            show_stepper = True

        self._current_readings = {k: info[k] for k in ("ot","psalm","epistle","gospel")}
        self.readings_card.set_visible(True)
        self.year_badge.set_label(f"Year {info['year']}")
        cx = info["colour_hex"]
        self.season_dot.set_markup(f'<span color="{cx}">●</span>')
        self.season_label.set_markup(f'<span color="{cx}">{GLib.markup_escape_text(info["week"])}</span>')
        self._colour_bar_rgb = _hex_to_rgb(cx); self._colour_bar.queue_draw(); self._order_season_strip.queue_draw()
        if hasattr(self, "_season_hdr_css"):
            r8, g8, b8 = (int(cx.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
            self._season_hdr_css.load_from_data(
                f".rubric-main-hdr {{ background-image: linear-gradient("
                f"to right, rgba({r8},{g8},{b8},0.09) 0%, transparent 55%); }}".encode())
        if hasattr(self, "_sb_season_dot"):
            self._sb_season_dot.set_markup(f'<span color="{cx}">●</span>')
            self._sb_season_dot.set_visible(True)

        # Stepper
        self._sunday_step_box.set_visible(show_stepper)
        if show_stepper and self._readings_sunday:
            self._sunday_lbl.set_label(
                f"Readings for {self._readings_sunday.strftime('%-d %b %Y (Sunday)')}"
            )

        self._inserted_readings: set[str] = set()
        for key, btn in self._reading_rows.items():
            ref = info[key]
            full_name = self._reading_labels.get(key, key)
            abbr = self._reading_abbrs.get(key, key)
            btn.remove_css_class("success")
            if ref and ref != "—":
                btn.set_label(ref); btn.set_sensitive(True)
                btn.set_tooltip_text(f"{full_name}: {ref}")
            else:
                btn.set_label(abbr); btn.set_sensitive(False)
                btn.set_tooltip_text(full_name)

        # Update hymn suggestions for this week
        self._update_hymn_suggestions(info["week"], info["season"])

        # Update observances row
        self._refresh_observances_row(self._readings_sunday or d)

    def _refresh_observances_row(self, d) -> None:
        """Rebuild the observances chips in the status bar centre."""
        next_box = getattr(self, "_obs_status_box", None)
        prev_box = getattr(self, "_prev_obs_box", None)
        if next_box is None:
            return
        for box in (next_box, prev_box):
            if box:
                while box.get_first_child():
                    box.remove(box.get_first_child())
        try:
            from observances import get_observances, get_previous_observance, TYPES
        except ImportError:
            return

        import re as _re

        def _strip_date_parens(name: str) -> str:
            """Remove trailing (Mon Day) or (Mon DD) date suffixes from name."""
            return _re.sub(r'\s*\([A-Za-z]{3,9}\s+\d{1,2}\)\s*$', '', name).strip()

        def _make_obs_chip(obs: dict, arrow: str, box: Gtk.Box) -> None:
            ti = TYPES.get(obs.get("type", ""), {})
            colour = ti.get("colour", "#6B7280")
            tlabel = ti.get("label", "")
            prox = obs.get("proximity", "")
            # Strip redundant inline date from name if we already have a proximity label
            display_name = _strip_date_parens(obs["name"]) if prox else obs["name"]
            markup = ""
            if arrow == "←":
                markup = f'<span alpha="60%">← </span>'
            if tlabel:
                markup += f'<span color="{colour}"><b>{GLib.markup_escape_text(tlabel)}</b></span> '
            markup += GLib.markup_escape_text(display_name)
            if prox:
                markup += f' <span alpha="60%">{GLib.markup_escape_text(prox)}</span>'
            if arrow == "→":
                markup += ' <span alpha="60%">→</span>'
            chip_lbl = Gtk.Label(); chip_lbl.set_markup(markup)
            chip_lbl.add_css_class("caption")
            chip_btn = Gtk.Button(); chip_btn.set_child(chip_lbl)
            chip_btn.add_css_class("flat"); chip_btn.add_css_class("pill")
            chip_btn.add_css_class("obs-chip")
            chip_btn.set_tooltip_text(f"Open Wikipedia: {obs['name']}")
            chip_btn.connect("clicked", lambda _b, n=obs["name"]: self._open_observance_wiki(n))
            box.append(chip_btn)

        # Next/upcoming event: first observance with proximity field, or first without
        obs_list = get_observances(d)
        next_obs = None
        for obs in obs_list:
            if obs.get("proximity"):
                next_obs = obs
                break
        if next_obs is None and obs_list:
            next_obs = obs_list[0]
        if next_obs and next_box:
            _make_obs_chip(next_obs, "→", next_box)

        # Previous event: most recent observance before d
        if prev_box:
            prev_obs = get_previous_observance(d)
            if prev_obs:
                _make_obs_chip(prev_obs, "←", prev_box)

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

        # Preview panel header
        hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        hdr.set_margin_start(6); hdr.set_margin_end(6)
        hdr.set_margin_top(6); hdr.set_margin_bottom(6)

        lbl = Gtk.Label(label="Preview")
        lbl.add_css_class("heading"); lbl.set_hexpand(True); lbl.set_xalign(0)
        hdr.append(lbl)

        # Bulletin / Manuscript toggle
        mode_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        mode_box.add_css_class("linked")
        self._preview_bulletin_btn = Gtk.ToggleButton(label="Bulletin")
        self._preview_bulletin_btn.set_active(True)
        self._preview_bulletin_btn.set_tooltip_text("Show congregation bulletin")
        self._preview_manuscript_btn = Gtk.ToggleButton(label="Manuscript")
        self._preview_manuscript_btn.set_group(self._preview_bulletin_btn)
        self._preview_manuscript_btn.set_tooltip_text("Show leader manuscript")

        def _on_preview_mode(btn, mode):
            if btn.get_active():
                self._preview_mode = mode
                self._preview_scroll_y = 0
                self._do_preview_update()

        self._preview_bulletin_btn.connect("toggled", _on_preview_mode, "bulletin")
        self._preview_manuscript_btn.connect("toggled", _on_preview_mode, "manuscript")
        mode_box.append(self._preview_bulletin_btn)
        mode_box.append(self._preview_manuscript_btn)
        hdr.append(mode_box)

        # Live toggle — forces instant HTML preview (no Typst compile)
        self._preview_live_btn = Gtk.ToggleButton(label="Live")
        self._preview_live_btn.set_tooltip_text(
            "Live mode — instant HTML preview that updates as you type, without waiting for Typst to compile")
        self._preview_live_btn.add_css_class("flat")
        self._preview_live_mode = False

        def _on_live_toggled(btn):
            self._preview_live_mode = btn.get_active()
            self._do_preview_update()

        self._preview_live_btn.connect("toggled", _on_live_toggled)
        hdr.append(self._preview_live_btn)

        self._bulletin_edit_btn = Gtk.ToggleButton(icon_name="document-edit-symbolic",
                                                   tooltip_text="Edit bulletin text for this service")
        self._bulletin_edit_btn.add_css_class("flat")
        self._bulletin_edit_btn.connect("toggled", self._on_bulletin_edit_toggled)
        hdr.append(self._bulletin_edit_btn)

        gear_btn = Gtk.MenuButton(icon_name="emblem-system-symbolic")
        gear_btn.add_css_class("flat")
        gear_btn.set_tooltip_text("Preview options — format, church name, bulletin settings")
        gear_btn.set_popover(self._build_preview_gear_popover())
        hdr.append(gear_btn)

        # Compiling indicator (hidden until xelatex is running)
        self._preview_spinner = Gtk.Spinner()
        self._preview_spinner.set_visible(False)
        hdr.append(self._preview_spinner)
        self._preview_compiling_lbl = Gtk.Label(label="Compiling…")
        self._preview_compiling_lbl.add_css_class("dim-label")
        self._preview_compiling_lbl.add_css_class("caption")
        self._preview_compiling_lbl.set_visible(False)
        hdr.append(self._preview_compiling_lbl)

        # Print bulletin directly
        print_btn = Gtk.Button(icon_name="document-print-symbolic",
                               tooltip_text="Print bulletin…")
        print_btn.add_css_class("flat")
        print_btn.connect("clicked", lambda _: self._print_bulletin_webkit())
        hdr.append(print_btn)

        # Popout into separate window
        popout_btn = Gtk.Button(icon_name="view-restore-symbolic",
                                tooltip_text="Open in separate window")
        popout_btn.add_css_class("flat")
        popout_btn.connect("clicked", lambda _: self._popout_preview())
        hdr.append(popout_btn)

        box.append(hdr)
        box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        box.add_css_class("preview-pane")

        self._preview_stack = Gtk.Stack()
        self._preview_stack.set_vexpand(True)
        self._preview_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._preview_stack.set_transition_duration(120)

        if _WEBKIT_OK:
            self._preview_webview = _WebKit.WebView()
            self._preview_webview.set_vexpand(True)
            self._preview_webview.set_hexpand(True)
            self._preview_scroll_y = 0
            self._preview_webview.connect("load-changed", self._on_preview_load_changed)
            self._preview_stack.add_named(self._preview_webview, "preview")
        else:
            self._preview_webview = None
            status = Adw.StatusPage(
                title="WebKit not available",
                description="Install python3-webkit2gtk (or typelib-1_0-WebKit2-4_1) "
                            "to enable live bulletin preview.",
                icon_name="web-browser-symbolic",
            )
            status.set_vexpand(True)
            self._preview_stack.add_named(status, "preview")

        # Bulletin edit view
        edit_scroll = Gtk.ScrolledWindow()
        edit_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        edit_scroll.set_vexpand(True)
        self._bulletin_edit_view = Gtk.TextView()
        self._bulletin_edit_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._bulletin_edit_view.set_top_margin(12); self._bulletin_edit_view.set_bottom_margin(12)
        self._bulletin_edit_view.set_left_margin(14); self._bulletin_edit_view.set_right_margin(14)
        edit_scroll.set_child(self._bulletin_edit_view)
        edit_hint = Gtk.Label(
            label="Editing bulletin text — changes here override the auto-generated preview. "
                  "Click ✏ again to save and return to preview.")
        edit_hint.add_css_class("caption"); edit_hint.add_css_class("dim-label")
        edit_hint.set_wrap(True); edit_hint.set_margin_start(12); edit_hint.set_margin_end(12)
        edit_hint.set_margin_top(6)
        edit_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        edit_box.append(edit_hint); edit_box.append(edit_scroll)
        self._preview_stack.add_named(edit_box, "editor")

        box.append(self._preview_stack)

        # Dev mode: "Copy Typst" footer (hidden until Dev toggle is on)
        box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        self._preview_copy_typst_bar = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self._preview_copy_typst_bar.set_margin_start(8)
        self._preview_copy_typst_bar.set_margin_end(8)
        self._preview_copy_typst_bar.set_margin_top(4)
        self._preview_copy_typst_bar.set_margin_bottom(4)
        self._preview_copy_typst_bar.set_visible(False)
        _dev_lbl = Gtk.Label(label="Dev:")
        _dev_lbl.add_css_class("caption"); _dev_lbl.add_css_class("dim-label")
        self._preview_copy_typst_bar.append(_dev_lbl)
        _copy_typst_btn = Gtk.Button(label="Copy Typst")
        _copy_typst_btn.add_css_class("flat"); _copy_typst_btn.add_css_class("caption")
        _copy_typst_btn.connect("clicked", lambda _: self._dev_copy_typst())
        self._preview_copy_typst_bar.append(_copy_typst_btn)
        box.append(self._preview_copy_typst_bar)

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
            config.save()
            self._schedule_preview_update()

        cn_entry.connect("changed", on_cn_changed)
        box.append(cn_entry)

        full_prefs_btn = Gtk.Button(label="Bulletin settings…")
        full_prefs_btn.add_css_class("flat"); full_prefs_btn.set_margin_top(4)
        full_prefs_btn.connect("clicked", lambda _: (pop.popdown(),
                                                     self.open_bulletin_prefs()))
        box.append(full_prefs_btn)

        pop.set_child(box)
        return pop

    def _open_prefs_page(self, page_title: str):
        """Open Preferences and navigate to the named page."""
        a = self.lookup_action("preferences")
        if a:
            a.activate(None)

    def _toggle_palette_sidebar(self, btn):
        if btn.get_active():
            self._palette_visible = True
            self._palette_paned.set_shrink_start_child(False)
            def _set_palette_pos():
                pos = getattr(self, "_pre_hide_palette_pos", 290)
                self._palette_paned.set_position(pos)
                return False
            GLib.idle_add(_set_palette_pos)
        else:
            self._pre_hide_palette_pos = self._palette_paned.get_position()
            self._palette_visible = False
            self._palette_paned.set_shrink_start_child(True)
            self._palette_paned.set_position(0)

    def _toggle_focus_mode(self, *_):
        if not hasattr(self, "_order_hpaned"):
            return  # UI not fully built yet
        self._focus_mode = not getattr(self, "_focus_mode", False)
        active = self._focus_mode
        if hasattr(self, "_focus_status_lbl"):
            if active:
                self._focus_status_lbl.set_markup("<b>Focus</b>")
            else:
                self._focus_status_lbl.set_text("Focus")
        if active:
            self._pre_focus_palette_pos = self._palette_paned.get_position()
            self._pre_focus_order_pos  = self._order_hpaned.get_position()
            self._pre_focus_sidebar_visible = self._palette_visible
            self._palette_paned.set_shrink_start_child(True)
            self._palette_paned.set_position(0)
            self._sidebar_btn.set_active(False)
            self._order_hpaned.set_shrink_start_child(True)
            self._order_hpaned.set_position(0)
            idx = self._selected_index()
            if 0 <= idx < len(self.service_entries):
                entry = self.service_entries[idx]
                if isinstance(entry, ServiceItem):
                    self._focus_elem_lbl.set_text(entry.name)
                else:
                    self._focus_elem_lbl.set_text("")
            self._focus_banner.set_reveal_child(True)
        else:
            self._focus_banner.set_reveal_child(False)
            self._order_hpaned.set_shrink_start_child(False)
            self._order_hpaned.set_position(getattr(self, "_pre_focus_order_pos", 260))
            if getattr(self, "_pre_focus_sidebar_visible", True):
                self._palette_paned.set_shrink_start_child(False)
                self._palette_paned.set_position(getattr(self, "_pre_focus_palette_pos", 290))
                self._sidebar_btn.set_active(True)
            else:
                self._palette_paned.set_position(0)

    def _toggle_preview_panel(self, _btn=None):
        self._preview_visible = not self._preview_visible
        visible = self._preview_visible
        if hasattr(self, "_preview_lbl"):
            if visible:
                self._preview_lbl.set_markup("<b>Preview</b>")
            else:
                self._preview_lbl.set_text("Preview")
        self._preview_panel.set_visible(visible)
        if visible:
            if not self._preview_paned_positioned:
                self._preview_paned_positioned = True
                def _set_pos():
                    total = self._preview_paned.get_allocated_width()
                    pos = max(280, int(total * 0.50)) if total > 300 else 380
                    self._preview_paned.set_position(pos)
                    return False
                GLib.idle_add(_set_pos)
            self._start_scroll_poll()
            self._do_preview_update()
        else:
            self._stop_scroll_poll()
            if getattr(self, "_preview_pending_id", None) is not None:
                GLib.source_remove(self._preview_pending_id)
                self._preview_pending_id = None

    def _on_bulletin_edit_toggled(self, btn):
        if btn.get_active():
            # Enter edit mode — populate editor if empty
            buf = self._bulletin_edit_view.get_buffer()
            s, e = buf.get_bounds()
            current = buf.get_text(s, e, False)
            if not current.strip():
                seed = getattr(self, "service_bulletin_text", "").strip()
                if not seed:
                    # Generate a plain-text seed from the auto-generated bulletin
                    seed = self._bulletin_as_plain_text()
                buf.set_text(seed, -1)
            self._preview_stack.set_visible_child_name("editor")
        else:
            # Exit edit mode — save editor content
            buf = self._bulletin_edit_view.get_buffer()
            s, e = buf.get_bounds()
            text = buf.get_text(s, e, False).strip()
            self.service_bulletin_text = text
            self._mark_modified()
            self._preview_stack.set_visible_child_name("preview")
            self._do_preview_update()

    def _toggle_bulletin_edit(self):
        if hasattr(self, "_bulletin_edit_btn"):
            self._bulletin_edit_btn.set_active(not self._bulletin_edit_btn.get_active())

    def _bulletin_as_plain_text(self) -> str:
        """Produce a plain-text draft of the bulletin for the editor seed."""
        title = self.service_title_entry.get_text() or "Order of Service"
        lines = [title, "=" * len(title)]
        for sec, items in self._grouped_entries():
            if not items and sec is None:
                continue
            lines.append("")
            if sec:
                lines.append(sec.upper())
                lines.append("-" * len(sec))
            for si in items:
                if not si.show_in_bulletin:
                    continue
                lines.append(si.name)
                body = strip_typst_plain(si.content_typst).strip() if si.content_typst else ""
                if body:
                    for bline in body.splitlines():
                        if bline.strip():
                            lines.append("  " + bline.strip())
        return "\n".join(lines)

    def _copy_as_text(self):
        """Format service as clean plain text and copy to clipboard."""
        title = self.service_title_entry.get_text() or "Order of Service"
        date_str = self.selected_date.strftime("%-d %B %Y") if self.selected_date else ""
        parts = [title]
        if date_str:
            parts.append(date_str)
        parts.append("")
        for sec, items in self._grouped_entries():
            if not items and sec is None:
                continue
            if sec:
                parts.append(sec.upper())
            for si in items:
                line = f"  • {si.name}"
                if si.leader:
                    line += f"  ({si.leader})"
                parts.append(line)
                note = strip_typst_plain(si.content_typst).strip() if si.content_typst else ""
                if note:
                    first = note.split('\n')[0].strip()
                    if first:
                        parts.append(f"    {first}")
            parts.append("")
        text = "\n".join(parts).strip()
        self.get_clipboard().set(text)
        self._show_toast("Service copied as plain text")

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
        mode = getattr(self, "_preview_mode", "bulletin")
        if mode == "bulletin" and hasattr(self, "_bulletin_edit_btn") and self._bulletin_edit_btn.get_active():
            return False
        if self._preview_webview is None:
            return False

        # Hide the bulletin edit button in manuscript mode
        if hasattr(self, "_bulletin_edit_btn"):
            self._bulletin_edit_btn.set_visible(mode == "bulletin")

        typst = self._find_typst()
        live_mode = getattr(self, "_preview_live_mode", False)
        if typst and not live_mode:
            if getattr(self, "_preview_compiling", False):
                # Compile in progress — reschedule so we pick up latest settings
                self._preview_pending_id = GLib.timeout_add(500, self._do_preview_update)
                return False
            # Capture Typst source in main thread (GTK widget access required)
            try:
                if mode == "manuscript":
                    typ_src = self._build_manuscript_typst()
                else:
                    typ_src = self._build_bulletin_typst(digital=False)
            except Exception:
                return False
            # Snapshot scroll position now (compile takes seconds; callback fires well before reload)
            _wv = self._preview_webview
            if _wv is not None:
                def _snap(source, result, _):
                    try:
                        jr = source.evaluate_javascript_finish(result)
                        if jr is not None:
                            try:
                                self._preview_scroll_y = int(jr.get_js_value().to_double())
                            except AttributeError:
                                self._preview_scroll_y = int(jr.to_double())
                    except Exception:
                        pass
                try:
                    _wv.evaluate_javascript("window.scrollY", -1, None, None, None, _snap, None)
                except Exception:
                    pass
            self._preview_compiling = True
            self._preview_spinner.set_visible(True)
            self._preview_spinner.start()
            self._preview_compiling_lbl.set_visible(True)
            threading.Thread(
                target=self._run_preview_compile, args=(typ_src, typst),
                daemon=True,
            ).start()
            return False

        # Live mode or Typst not found — HTML fallback
        try:
            if mode == "manuscript":
                html = self._build_manuscript_html()
            else:
                html = self._build_bulletin_html()
            self._preview_save_scroll()
            self._preview_webview.load_html(html, None)
        except Exception:
            pass
        return False

    def _preview_pdf_path(self) -> Path:
        """Return the stable path used for the live preview PDF."""
        mode = getattr(self, "_preview_mode", "bulletin")
        cache = Path(GLib.get_user_cache_dir()) / "rubric"
        cache.mkdir(parents=True, exist_ok=True)
        return cache / f"preview_{mode}.pdf"

    def _run_preview_compile(self, typ_src: str, typst_bin: str) -> None:
        """Background thread: compile bulletin Typst to PDF for live preview."""
        import tempfile as _tf
        typ_path = None
        try:
            with _tf.NamedTemporaryFile(
                suffix=".typ", delete=False, mode="w", encoding="utf-8",
                prefix="rubric_preview_",
            ) as f:
                f.write(typ_src)
                typ_path = Path(f.name)
            pdf_path = self._preview_pdf_path()
            cmd = self._typst_compile_cmd(typst_bin, str(typ_path), str(pdf_path))
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True, text=True, timeout=60,
                    encoding="utf-8", errors="replace",
                )
            finally:
                typ_path.unlink(missing_ok=True)
            if result.returncode == 0 and pdf_path.exists():
                GLib.idle_add(self._load_preview_pdf, str(pdf_path))
            else:
                err = (result.stderr or result.stdout or "").strip()
                GLib.idle_add(self._preview_compile_done)
                if err:
                    short = format_typst_error(err)[:100]
                    GLib.idle_add(lambda msg=short: self._show_toast(f"Preview: {msg}", timeout=4))
        except subprocess.TimeoutExpired:
            GLib.idle_add(self._preview_compile_done)
        except Exception:
            if typ_path:
                typ_path.unlink(missing_ok=True)
            GLib.idle_add(self._preview_compile_done)

    @staticmethod
    def _typst_compile_cmd(typst_bin: str, src: str, dst: str, extra: list[str] | None = None) -> list[str]:
        """Build a typst compile command with font-path arguments for common font locations."""
        cmd = [typst_bin, "compile"]
        for _fp in [
            "/run/host/fonts",
            "/run/host/usr/share/fonts",
            "/usr/share/fonts",
            "/usr/local/share/fonts",
            str(Path.home() / ".fonts"),
            str(Path.home() / ".local/share/fonts"),
        ]:
            if Path(_fp).is_dir():
                cmd += ["--font-path", _fp]
        if extra:
            cmd += extra
        cmd += [src, dst]
        return cmd

    def _find_typst(self) -> str | None:
        """Return path to the typst binary, or None."""
        # Check bundled binary first
        for candidate in [
            Path(__file__).parent / "rubric_package" / "bin" / "typst",
            Path("/usr/share/rubric/bin/typst"),
            Path.home() / ".local/share/rubric/bin/typst",
        ]:
            if candidate.exists():
                return str(candidate)
        return shutil.which("typst")

    def _load_typst_preamble(self, name: str) -> str:
        """Return a Typst document preamble.

        Priority: GUI preamble config → user template override → bundled template.
        """
        preamble_key = "manuscript" if name == "manuscript" else "bulletin"
        p = config.preamble.get(preamble_key)
        if p:
            ms = (name == "manuscript")
            mt = p.get("margin_top",    1.0 if ms else 0.7)
            mb = p.get("margin_bottom", 1.0 if ms else 0.7)
            ml = p.get("margin_left",   0.7 if ms else 0.6)
            mr = p.get("margin_right",  0.7 if ms else 0.6)
            sz = p.get("size", 11)
            font = p.get("font", "").strip()
            parts: list[str] = []
            if name == "manuscript":
                parts.append(
                    f'#set page(paper: "us-letter", '
                    f'margin: (top: {mt}in, bottom: {mb}in, left: {ml}in, right: {mr}in), '
                    f'numbering: "1")')
            elif name == "bulletin_print":
                parts.append(
                    f'#set page(width: 5.5in, height: 8.5in, '
                    f'margin: (top: {mt}in, bottom: {mb}in, left: {ml}in, right: {mr}in))')
            elif name == "bulletin_digital":
                parts.append(
                    f'#set page(paper: "us-letter", '
                    f'margin: (top: {mt}in, bottom: {mb}in, left: {ml}in, right: {mr}in))')
            text_args = [f'size: {sz}pt']
            if font:
                text_args.append(f'font: "{font}"')
            parts.append(f'#set text({", ".join(text_args)})')
            parts.append('#set par(justify: false)')
            if name == "manuscript":
                parts.append('#set par(spacing: 0.5em, first-line-indent: 0pt)')
            if name == "bulletin_digital":
                parts.append('#show link: it => text(fill: rgb("1e3a6e"), it)')
            return '\n'.join(parts)

        user_path = Path.home() / ".config/rubric/templates" / f"{name}.typ"
        if user_path.exists():
            return user_path.read_text(encoding="utf-8").strip()
        bundled = Path(__file__).parent / "rubric_package" / "templates" / f"{name}.typ"
        if bundled.exists():
            return bundled.read_text(encoding="utf-8").strip()
        # Hardcoded fallback
        _fallbacks: dict[str, str] = {
            "bulletin_print": (
                '#set page(width: 5.5in, height: 8.5in, margin: (x: 0.6in, y: 0.7in))\n'
                '#set text(size: 11pt)\n#set par(justify: false)'
            ),
            "bulletin_digital": (
                '#set page(paper: "us-letter", margin: 1in)\n'
                '#set text(size: 12pt)\n#set par(justify: false)\n'
                '#show link: it => text(fill: rgb("1e3a6e"), it)'
            ),
            "manuscript": (
                '#set page(paper: "us-letter",'
                ' margin: (top: 1in, bottom: 1in, left: 0.7in, right: 0.7in), numbering: "1")\n'
                '#set text(size: 11pt)\n'
                '#set par(justify: false, spacing: 0.5em, first-line-indent: 0pt)'
            ),
        }
        return _fallbacks.get(name, "")

    def _load_preview_pdf(self, pdf_path: str):
        self._preview_pdf_loaded = pdf_path
        self._preview_compile_done()
        if self._preview_webview:
            uri = f"file://{pdf_path}"
            current = (self._preview_webview.get_uri() or "").split("?")[0].split("#")[0]
            self._preview_save_scroll()
            if current == uri:
                self._preview_webview.reload()
            else:
                self._preview_webview.load_uri(uri)
        return False

    def _on_preview_load_changed(self, wv, event):
        if _WebKit and event == _WebKit.LoadEvent.FINISHED:
            y = self._preview_scroll_y
            if y > 0:
                def _restore(wv=wv, y=y):
                    js = f"window.scrollTo(0, {y});"
                    try:
                        wv.evaluate_javascript(js, -1, None, None, None, None, None)
                    except (AttributeError, TypeError):
                        try:
                            wv.run_javascript(js, None, None, None)
                        except Exception:
                            pass
                    return False
                GLib.timeout_add(120, _restore)

    def _start_scroll_poll(self):
        """Slow fallback poll (2 s) — the compile-start snapshot handles the real capture."""
        self._stop_scroll_poll()
        def _poll():
            wv = self._preview_webview
            if wv is None or not getattr(self, "_preview_visible", False):
                self._preview_scroll_poll_id = None
                return False
            if getattr(self, "_preview_compiling", False):
                return True  # skip while compile is in flight; snapshot handles it
            def _got(source, result, _):
                try:
                    js_result = source.evaluate_javascript_finish(result)
                    if js_result is not None:
                        try:
                            self._preview_scroll_y = int(js_result.get_js_value().to_double())
                        except AttributeError:
                            self._preview_scroll_y = int(js_result.to_double())
                except Exception:
                    pass
            try:
                wv.evaluate_javascript("window.scrollY", -1, None, None, None, _got, None)
            except Exception:
                pass
            return True
        self._preview_scroll_poll_id = GLib.timeout_add(2000, _poll)

    def _stop_scroll_poll(self):
        pid = getattr(self, "_preview_scroll_poll_id", None)
        if pid is not None:
            GLib.source_remove(pid)
            self._preview_scroll_poll_id = None

    def _preview_save_scroll(self):
        pass  # kept for call-site compatibility; polling handles this now

    def _preview_compile_done(self):
        self._preview_compiling = False
        self._preview_spinner.stop()
        self._preview_spinner.set_visible(False)
        self._preview_compiling_lbl.set_visible(False)
        return False

    def _popout_preview(self):
        """Open the current preview in a separate window."""
        if not _WEBKIT_OK:
            return
        mode = getattr(self, "_preview_mode", "bulletin")
        title = "Manuscript Preview" if mode == "manuscript" else "Bulletin Preview"
        win = Adw.Window(title=title, transient_for=self)
        win.set_default_size(720, 960)
        tv = Adw.ToolbarView()
        hdr = Adw.HeaderBar()
        tv.add_top_bar(hdr)
        wv = _WebKit.WebView()
        wv.set_vexpand(True); wv.set_hexpand(True)
        pdf_path = getattr(self, "_preview_pdf_loaded", None)
        if pdf_path and Path(pdf_path).exists():
            wv.load_uri(f"file://{pdf_path}")
        else:
            try:
                if mode == "manuscript":
                    wv.load_html(self._build_manuscript_html(), None)
                else:
                    wv.load_html(self._build_bulletin_html(), None)
            except Exception:
                pass
        tv.set_content(wv)
        win.set_content(tv)
        self._preview_popout_win = win  # prevent GC
        win.present()

    def _mark_modified(self):
        self.modified = True
        self._update_title()
        self._schedule_preview_update()
        self._update_save_state_chip()
        if self.current_file:
            if getattr(self, "_deferred_save_id", None):
                GLib.source_remove(self._deferred_save_id)
            self._deferred_save_id = GLib.timeout_add(2000, self._deferred_save)

    def _refresh_cover_thumb(self):
        if not hasattr(self, "_cover_thumb"):
            return
        path = config.bulletin.get("cover_image", "").strip()
        if path and Path(path).is_file():
            try:
                from gi.repository import GdkPixbuf
                pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, 28, 28, True)
                self._cover_thumb.set_from_pixbuf(pb)
                self._cover_thumb.set_visible(True)
                return
            except Exception:
                pass
        self._cover_thumb.set_visible(False)

    def _update_save_state_chip(self):
        if not hasattr(self, "_save_state_lbl"):
            return
        if self.modified:
            self._save_state_lbl.set_markup("<span foreground='#e5a50a'>● Unsaved</span>")
            self._save_state_lbl.set_visible(True)
            # Start pulse animation after 30s of being unsaved
            if not getattr(self, "_unsaved_pulse_id", None):
                self._unsaved_pulse_id = GLib.timeout_add_seconds(30, self._start_unsaved_pulse)
        else:
            self._save_state_lbl.set_visible(False)
            self._save_state_lbl.remove_css_class("unsaved-pulse")
            if getattr(self, "_unsaved_pulse_id", None):
                GLib.source_remove(self._unsaved_pulse_id)
                self._unsaved_pulse_id = None

    def _start_unsaved_pulse(self):
        self._unsaved_pulse_id = None
        if self.modified and hasattr(self, "_save_state_lbl"):
            self._save_state_lbl.add_css_class("unsaved-pulse")
        return False

    def _deferred_save(self):
        self._deferred_save_id = None
        if self.modified and self.current_file:
            self._write(self.current_file)
        return False

    def _update_title(self):
        svc = self.service_title_entry.get_text() or "New service"
        if self.selected_date:
            subtitle = self.selected_date.strftime("%-d %B %Y") + (" •" if self.modified else "")
        else:
            subtitle = svc + (" •" if self.modified else "")
        self.title_widget.set_title(
            Path(self.current_file).stem if self.current_file else svc)
        self.title_widget.set_subtitle(subtitle)
        self.set_title(f"{svc} — Rubric" if svc != "New service" else "Rubric")

    def _service_data(self):
        d = {"title": self.service_title_entry.get_text(),
             "date":  self.selected_date.isoformat() if self.selected_date else None,
             "items": [e.to_dict() for e in self.service_entries]}
        if self.typ_file:
            d["typ_file"] = self.typ_file
        if getattr(self, "service_bulletin_text", ""):
            d["bulletin_text"] = self.service_bulletin_text
        if getattr(self, "service_attendance", 0):
            d["attendance"] = self.service_attendance
        if getattr(self, "service_debrief", ""):
            d["debrief"] = self.service_debrief
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
            self._show_setup_wizard(on_done=self._show_first_launch_wizard)
            GLib.idle_add(self._check_autosave)
        elif config.last_seen_version != APP_VERSION:
            self._show_welcome(is_new_version=bool(config.last_seen_version),
                               on_done=self._check_autosave)
        else:
            GLib.idle_add(self._check_autosave)
        return False

    # ── Setup wizard ─────────────────────────────────────────────────────────

    def _show_setup_wizard(self, on_done=None):
        """Multi-step initialization wizard: folder setup → hymn downloads → GitHub."""
        win = Adw.Window(transient_for=self, modal=True)
        win.set_title("Set Up Rubric")
        win.set_default_size(520, 0)
        win.set_resizable(False)

        tv = Adw.ToolbarView()
        hdr = Adw.HeaderBar(); hdr.set_show_end_title_buttons(False)
        step_lbl = Gtk.Label(); step_lbl.add_css_class("caption"); step_lbl.add_css_class("dim-label")
        hdr.set_title_widget(step_lbl)
        tv.add_top_bar(hdr)
        win.set_content(tv)

        stack = Gtk.Stack()
        stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        stack.set_transition_duration(200)

        # ── Step 1: Folder ────────────────────────────────────────────────────
        p1 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        p1.set_margin_start(24); p1.set_margin_end(24)
        p1.set_margin_top(20); p1.set_margin_bottom(20)

        icon1 = Gtk.Image(icon_name="folder-symbolic"); icon1.set_pixel_size(48); icon1.set_margin_bottom(6)
        p1.append(icon1)
        lbl1 = Gtk.Label(label="Choose a folder for your files")
        lbl1.add_css_class("title-2"); lbl1.set_margin_bottom(2)
        p1.append(lbl1)
        sub1 = Gtk.Label(label="Rubric will store your liturgy files, Typst exports, and PDFs here.\n"
                                "Choose an empty folder — it will become your liturgy repository.")
        sub1.set_wrap(True); sub1.set_justify(Gtk.Justification.CENTER)
        sub1.add_css_class("dim-label"); sub1.set_margin_bottom(10)
        p1.append(sub1)

        folder_grp = Adw.PreferencesGroup()
        p1_path_row = Adw.ActionRow(title="Folder", subtitle=config.github_repo or "Not chosen yet")
        browse1_btn = Gtk.Button(label="Browse…", valign=Gtk.Align.CENTER)
        browse1_btn.add_css_class("flat")
        p1_path_row.add_suffix(browse1_btn)
        folder_grp.add(p1_path_row)
        setup1_row = Adw.ActionRow(title="Create subfolders & initialise git",
                                   subtitle="Creates liturgy/, tex/, pdf/, bulletins/ inside chosen folder")
        setup1_btn = Gtk.Button(label="Set up", valign=Gtk.Align.CENTER)
        setup1_btn.add_css_class("suggested-action")
        setup1_row.add_suffix(setup1_btn)
        folder_grp.add(setup1_row)
        p1.append(folder_grp)

        p1_status = Gtk.Label(label="")
        p1_status.add_css_class("caption"); p1_status.add_css_class("dim-label")
        p1_status.set_wrap(True); p1_status.set_margin_top(4)
        p1.append(p1_status)
        stack.add_named(p1, "folder")

        def _on_browse1(_b):
            dlg = Gtk.FileDialog(title="Choose folder for liturgy files")
            dlg.select_folder(win, None, _on_folder_chosen)
        def _on_folder_chosen(dlg, result):
            try: f = dlg.select_folder_finish(result)
            except GLib.Error: return
            config.github_repo = f.get_path(); config.save()
            p1_path_row.set_subtitle(config.github_repo)
            p1_status.set_label(f"Folder: {config.github_repo}")
        def _on_setup1(_b):
            if not config.github_repo:
                p1_status.set_label("Please choose a folder first."); return
            from pathlib import Path as _P
            rp = _P(config.github_repo); errors = []
            for sub in ("liturgy", "tex", "pdf", "bulletins"):
                try: (rp / sub).mkdir(parents=True, exist_ok=True)
                except OSError as e: errors.append(str(e))
            gi_path = rp / ".gitignore"
            if not gi_path.exists():
                try: gi_path.write_text("*.log\n", encoding="utf-8")
                except OSError as e: errors.append(str(e))
            try:
                r = subprocess.run(_GIT + ["-C", str(rp), "init"], capture_output=True, text=True, timeout=10)
                if r.returncode != 0: errors.append(r.stderr.strip())
            except Exception as e: errors.append(str(e))
            if errors: p1_status.set_label("Errors: " + "; ".join(errors))
            else: p1_status.set_label("✓ Folder ready — subfolders and git initialised")
        browse1_btn.connect("clicked", _on_browse1)
        setup1_btn.connect("clicked", _on_setup1)

        # ── Step 2: Hymn downloads ─────────────────────────────────────────────
        p2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        p2.set_margin_start(24); p2.set_margin_end(24)
        p2.set_margin_top(20); p2.set_margin_bottom(20)

        icon2 = Gtk.Image(icon_name="audio-x-generic-symbolic"); icon2.set_pixel_size(48); icon2.set_margin_bottom(6)
        p2.append(icon2)
        lbl2 = Gtk.Label(label="Download hymn titles (optional)")
        lbl2.add_css_class("title-2"); lbl2.set_margin_bottom(2)
        p2.append(lbl2)
        sub2 = Gtk.Label(label="Cache hymn titles from Hymnary.org for faster offline lookup.\n"
                                "This downloads titles only — no audio. You can skip this and do it later in Preferences.")
        sub2.set_wrap(True); sub2.set_justify(Gtk.Justification.CENTER)
        sub2.add_css_class("dim-label"); sub2.set_margin_bottom(10)
        p2.append(sub2)

        hymn_grp = Adw.PreferencesGroup()
        p2_dl_bar = Gtk.ProgressBar(); p2_dl_bar.set_visible(False)
        p2_dl_status = Gtk.Label(label=""); p2_dl_status.add_css_class("caption"); p2_dl_status.add_css_class("dim-label")
        _wizard_open = [True]   # flipped to False when wizard closes

        for bk, bk_label, max_n in [("VU","Voices United (VU)",961),("MV","More Voices (MV)",217),("LUS","Let Us Sing (LUS)",150)]:
            dl_row = Adw.ActionRow(title=f"Download {bk_label}")
            dl_btn = Gtk.Button(label="Download", valign=Gtk.Align.CENTER); dl_btn.add_css_class("flat")
            def _start_dl(_b, book=bk, btn=dl_btn):
                btn.set_sensitive(False)
                if _wizard_open[0]:
                    p2_dl_bar.set_visible(True); p2_dl_bar.set_fraction(0)
                    p2_dl_status.set_label(f"Downloading {book}… (continues in background if you close)")
                def _prog(done, total):
                    if _wizard_open[0]:
                        p2_dl_bar.set_fraction(done / total)
                        p2_dl_bar.set_text(f"{book} {done}/{total}")
                    return False
                def _done(added):
                    if _wizard_open[0]:
                        p2_dl_bar.set_visible(False)
                        p2_dl_status.set_label(f"✓ {added} titles cached from {book}")
                    msg = (f"✓ {added} {book} hymn titles downloaded"
                           if added else f"{book} download complete — check your network if titles are missing")
                    self._show_toast(msg, timeout=6)
                    return False
                prefetch_hymnal(book, on_progress=_prog, on_done=_done)
            dl_btn.connect("clicked", _start_dl)
            dl_row.add_suffix(dl_btn); hymn_grp.add(dl_row)
        p2.append(hymn_grp)
        p2.append(p2_dl_bar); p2.append(p2_dl_status)
        stack.add_named(p2, "hymns")

        # ── Step 3: GitHub ────────────────────────────────────────────────────
        p3 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        p3.set_margin_start(24); p3.set_margin_end(24)
        p3.set_margin_top(20); p3.set_margin_bottom(20)

        icon3 = Gtk.Image(icon_name="network-server-symbolic"); icon3.set_pixel_size(48); icon3.set_margin_bottom(6)
        p3.append(icon3)
        lbl3 = Gtk.Label(label="Connect to GitHub (optional)")
        lbl3.add_css_class("title-2"); lbl3.set_margin_bottom(2)
        p3.append(lbl3)
        sub3 = Gtk.Label(label="Back up and sync your liturgy files with a private GitHub repository.\n"
                                "Create a free account at github.com, then paste your repository URL below. You can skip this and connect later in Preferences.")
        sub3.set_wrap(True); sub3.set_justify(Gtk.Justification.CENTER)
        sub3.add_css_class("dim-label"); sub3.set_margin_bottom(10)
        p3.append(sub3)

        gh_grp = Adw.PreferencesGroup()
        gh_entry = Adw.EntryRow(title="GitHub repository URL (https://…)")
        gh_entry.set_text(config.github_repo and self._detect_github_remote() or "")
        gh_grp.add(gh_entry)
        connect_row = Adw.ActionRow(title="Save and connect")
        connect_btn = Gtk.Button(label="Connect", valign=Gtk.Align.CENTER); connect_btn.add_css_class("suggested-action")
        connect_row.add_suffix(connect_btn); gh_grp.add(connect_row)
        p3.append(gh_grp)
        p3_status = Gtk.Label(label="")
        p3_status.add_css_class("caption"); p3_status.add_css_class("dim-label")
        p3_status.set_wrap(True); p3_status.set_margin_top(4)
        p3.append(p3_status)

        def _on_connect3(_b):
            repo = config.github_repo; url = gh_entry.get_text().strip()
            if not repo: p3_status.set_label("Set up a folder (step 1) first."); return
            if not url: p3_status.set_label("Paste your GitHub repository URL first."); return
            try:
                chk = subprocess.run(_GIT + ["-C",repo,"remote","get-url","origin"], capture_output=True, text=True, timeout=5)
                cmd = _GIT + ["-C",repo,"remote","set-url" if chk.returncode==0 else "add","origin",url]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if r.returncode != 0: p3_status.set_label(f"Error: {r.stderr.strip()}")
                else: p3_status.set_label(f"✓ Connected to {url}")
            except Exception as e: p3_status.set_label(str(e))
        connect_btn.connect("clicked", _on_connect3)
        stack.add_named(p3, "github")

        # ── Navigation bar ────────────────────────────────────────────────────
        pages = ["folder", "hymns", "github"]
        page_titles = ["Step 1 of 3 — Folder", "Step 2 of 3 — Hymn Titles", "Step 3 of 3 — GitHub"]
        _cur = [0]

        nav = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        nav.set_margin_start(24); nav.set_margin_end(24)
        nav.set_margin_top(8); nav.set_margin_bottom(20)
        skip_btn = Gtk.Button(label="Skip"); skip_btn.add_css_class("flat")
        back_btn = Gtk.Button(label="← Back"); back_btn.add_css_class("flat"); back_btn.set_sensitive(False)
        sp = Gtk.Box(); sp.set_hexpand(True)
        next_btn = Gtk.Button(label="Next →"); next_btn.add_css_class("suggested-action")
        nav.append(skip_btn); nav.append(back_btn); nav.append(sp); nav.append(next_btn)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.append(stack); outer.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)); outer.append(nav)
        tv.set_content(outer)

        def _go(idx):
            _cur[0] = idx
            stack.set_visible_child_name(pages[idx])
            step_lbl.set_label(page_titles[idx])
            back_btn.set_sensitive(idx > 0)
            next_btn.set_label("Done" if idx == len(pages) - 1 else "Next →")

        def _on_next(_b):
            if _cur[0] < len(pages) - 1: _go(_cur[0] + 1)
            else: _close()
        def _on_back(_b):
            if _cur[0] > 0: _go(_cur[0] - 1)
        def _on_skip(_b):
            if _cur[0] < len(pages) - 1: _go(_cur[0] + 1)
            else: _close()
        def _close():
            win.close()  # close-request handler schedules on_done

        def _on_wizard_close(_w):
            _wizard_open[0] = False
            if on_done:
                GLib.idle_add(on_done)
            return False  # always allow close

        next_btn.connect("clicked", _on_next)
        back_btn.connect("clicked", _on_back)
        skip_btn.connect("clicked", _on_skip)
        win.connect("close-request", _on_wizard_close)
        _go(0)
        win.present()

    def _detect_github_remote(self) -> str:
        repo = config.github_repo
        if not repo: return ""
        try:
            r = subprocess.run(_GIT + ["-C",repo,"remote","get-url","origin"], capture_output=True, text=True, timeout=5)
            return r.stdout.strip() if r.returncode == 0 else ""
        except Exception: return ""

    # ── Quick-start banner ────────────────────────────────────────────────────

    _QUICKSTART_TIPS = [
        "Double-click any element in the left palette to add it to your service order.",
        "Click the window title to set your service date — RCL readings load automatically.",
        "Select an element to reveal the item toolbar: leader name, scripture, hymn lookup.",
        "Type in the Notes area to add content for each element. Leader notes go to the PDF; "
            "Bulletin text appears in the congregational bulletin.",
        "Save (Ctrl+S) often. Use Menu → Save as template to reuse this order every week.",
        "Ctrl+E exports to Typst; Ctrl+Shift+P compiles a PDF. "
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

    # ── UI help overlay ───────────────────────────────────────────────────────

    def _show_ui_help_popover(self, _btn=None):
        _AREAS = [
            ("sidebar-show", "Element palette (left panel)",
             "Drag elements from here into your service order — hymns, prayers, scripture, and more."),
            ("view-list-symbolic", "Service order (centre)",
             "Your running order. Click any row to edit its name, notes, or bulletin text. "
             "Drag rows to reorder. Dividers create labelled sections (e.g. Gathering, Offering)."),
            ("document-edit-symbolic", "Notes editor (right)",
             "Write leader notes, liturgical text, or scripture here. "
             "Supports Typst markup: *bold*, _italic_, #scripture[…]."),
            ("web-browser-symbolic", "Preview panel",
             "Live bulletin or manuscript preview. Bulletin mode compiles a PDF via Typst. "
             "Live mode shows an instant HTML version while you type."),
            ("view-more-horizontal-symbolic", "Status bar (bottom)",
             "SIMPLE hides advanced features. Compact tightens spacing. "
             "Dev shows Typst source. Focus hides the palette. "
             "The ● Unsaved chip appears when you have unsaved changes."),
            ("preferences-system-symbolic", "Menu (top-right ☰)",
             "Settings, bulletin options, GitHub sync, scripture lookup, snippets, and the changelog."),
        ]
        pop = Gtk.Popover()
        pop.set_has_arrow(True)
        pop.set_position(Gtk.PositionType.BOTTOM)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.set_margin_top(12); outer.set_margin_bottom(12)
        outer.set_margin_start(4); outer.set_margin_end(4)
        outer.set_size_request(320, -1)
        hdr_lbl = Gtk.Label(label="What's on screen")
        hdr_lbl.add_css_class("heading"); hdr_lbl.set_xalign(0)
        hdr_lbl.set_margin_start(8); hdr_lbl.set_margin_bottom(6)
        outer.append(hdr_lbl)
        for icon, title, desc in _AREAS:
            row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            row_box.set_margin_start(4); row_box.set_margin_end(4)
            row_box.set_margin_top(4); row_box.set_margin_bottom(4)
            ico = Gtk.Image(icon_name=icon); ico.set_pixel_size(20)
            ico.set_valign(Gtk.Align.START); ico.set_margin_top(2)
            row_box.append(ico)
            text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            t_lbl = Gtk.Label(label=title); t_lbl.add_css_class("body"); t_lbl.set_xalign(0)
            d_lbl = Gtk.Label(label=desc); d_lbl.add_css_class("caption"); d_lbl.add_css_class("dim-label")
            d_lbl.set_xalign(0); d_lbl.set_wrap(True); d_lbl.set_max_width_chars(40)
            text_box.append(t_lbl); text_box.append(d_lbl)
            row_box.append(text_box)
            outer.append(row_box)
            outer.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        more_btn = Gtk.Button(label="Open full help…")
        more_btn.add_css_class("flat"); more_btn.set_margin_top(4)
        more_btn.connect("clicked", lambda _: (pop.popdown(), self.open_help("help")))
        outer.append(more_btn)
        pop.set_child(outer)
        pop.set_parent(self._help_header_btn)
        pop.popup()

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

        # Scrollable content wrapper
        scroll = Gtk.ScrolledWindow()
        scroll.set_propagate_natural_height(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        tv.set_content(scroll)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.set_margin_start(24); outer.set_margin_end(24)
        outer.set_margin_top(20); outer.set_margin_bottom(24)
        scroll.set_child(outer)

        # ── Step 1: church name (only if not set yet) ─────────────────────────
        needs_church_name = not config.bulletin.get("church_name", "").strip()

        def _show_choice_step():
            # Clear outer and rebuild for step 2
            while True:
                child = outer.get_first_child()
                if child is None:
                    break
                outer.remove(child)
            _build_choice_step()

        def _build_church_step():
            hero_icon = Gtk.Image(icon_name="rubric-symbolic")
            hero_icon.set_pixel_size(48); hero_icon.set_margin_bottom(10)
            outer.append(hero_icon)
            title_lbl = Gtk.Label(label="Welcome to Rubric")
            title_lbl.add_css_class("title-1"); title_lbl.set_margin_bottom(4)
            outer.append(title_lbl)
            sub_lbl = Gtk.Label(label="First, what's the name of your church or community?")
            sub_lbl.add_css_class("dim-label"); sub_lbl.set_margin_bottom(20)
            outer.append(sub_lbl)

            name_lb = Gtk.ListBox(); name_lb.add_css_class("boxed-list")
            name_lb.set_selection_mode(Gtk.SelectionMode.NONE)
            name_row = Adw.EntryRow(title="Church name")
            name_row.set_text(config.bulletin.get("church_name", ""))
            name_lb.append(name_row)
            outer.append(name_lb)

            hint = Gtk.Label(label="This appears on printed bulletins. You can change it any time in Settings.")
            hint.add_css_class("caption"); hint.add_css_class("dim-label")
            hint.set_wrap(True); hint.set_xalign(0); hint.set_margin_top(6); hint.set_margin_bottom(16)
            outer.append(hint)

            next_btn = Gtk.Button(label="Continue →")
            next_btn.add_css_class("suggested-action")
            next_btn.set_halign(Gtk.Align.END)
            outer.append(next_btn)

            def _on_next(_b):
                name = name_row.get_text().strip()
                if name:
                    config.bulletin["church_name"] = name
                    config.save()
                _show_choice_step()

            next_btn.connect("clicked", _on_next)
            name_row.connect("apply", lambda _: _on_next(None))

        def _build_choice_step():
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

            lb = Gtk.ListBox()
            lb.set_selection_mode(Gtk.SelectionMode.NONE)
            lb.add_css_class("boxed-list")
            outer.append(lb)

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

            skip_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            skip_row.set_margin_top(14)
            sp = Gtk.Box(); sp.set_hexpand(True); skip_row.append(sp)
            skip_btn = Gtk.Button(label="Skip for now")
            skip_btn.add_css_class("flat"); skip_row.append(skip_btn)
            sp2 = Gtk.Box(); sp2.set_hexpand(True); skip_row.append(sp2)
            outer.append(skip_row)

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

            def _on_row_activated(_lb, row):
                if row is lect_row:  _finish("lect")
                elif row is blank_row: _finish("blank")
                elif row is tour_row:  _finish("tour")
            lb.connect("row-activated", _on_row_activated)
            skip_btn.connect("clicked", lambda _: _finish("blank"))
            win.connect("close-request", lambda _w: _finish("blank") or False)

        if needs_church_name:
            _build_church_step()
        else:
            _build_choice_step()
        win.present()

    # ── Lectionary service seeding ────────────────────────────────────────────

    def _seed_lectionary_service(self, today, info: dict):
        """Reset state and pre-fill the UCC Sunday order using today's RCL readings."""
        self._reset_state()

        # Set date
        self.selected_date = today
        self._set_date_label(today.strftime("%-d %B %Y"))

        # Service title = liturgical week label
        week = info.get("week", "")
        if week:
            self.service_title_entry.set_text(week)

        def _si(name, section, note="", leader=""):
            return ServiceItem(name, section, note=note, leader=leader)

        def _ref(key):
            v = info.get(key, "")
            return v if v and v != "—" else ""

        items = [
            SectionDivider("Gathering"),
            _si("Prelude",                      "Gathering"),
            _si("Welcome & Announcements",       "Gathering"),
            _si("Land Acknowledgement",          "Gathering"),
            _si("Birthday & Anniversary Prayer", "Gathering"),
            _si("Christ Candle",                 "Gathering"),
            _si("Opening Hymn",                  "Gathering", leader="All"),
            _si("Call to Worship",               "Gathering"),
            _si("Opening Prayer",                "Gathering"),
            _si("Second Hymn",                   "Gathering", leader="All"),
            SectionDivider("Word"),
            _si("Scripture",       "Word"),
            _si("Sung Psalm",      "Word", leader="All"),
            _si("Ministry of Music",  "Word"),
            _si("Growing in Faith",   "Word"),
            _si("Sermon / Message",   "Word"),
            _si("Practice",           "Word", leader="All"),
            _si("Hymn",               "Word", leader="All"),
            SectionDivider("Response"),
            _si("Prayers of the People",      "Response"),
            _si("Lord's Prayer",              "Response", leader="All"),
            _si("Presentation of Our Offering","Response"),
            _si("Offertory",                   "Response"),
            _si("Sung Response",               "Response", leader="All"),
            _si("Prayer of Dedication",        "Response"),
            SectionDivider("Sending"),
            _si("Rainbow Candle",    "Sending"),
            _si("Closing Hymn",      "Sending", leader="All"),
            _si("Commissioning",     "Sending"),
        ]

        for item in items:
            self.service_entries.append(item)

        self._refresh_order_list()
        self._update_readings(today)
        self.modified = False          # seeded service starts clean
        self._update_title()
        self._show_toast(f"Service pre-filled for {week or today.strftime('%-d %B %Y')}",
                         timeout=5)

    def _seed_lectionary_service_today(self):
        from datetime import date as _pydate
        today = _pydate.today()
        try:
            info = get_liturgical_info(today)
        except Exception:
            info = {}
        self._seed_lectionary_service(today, info)

    def _show_welcome(self, is_new_version: bool = False, on_done=None):
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
            "Scripture lookup, Hymn number lookup (VU/MV/LUS), and Snippets.\n\n"
            "**Hymn suggestions** — when a date is set, suggested hymns appear below the "
            "order list. Left-click to view on Hymnary.org; right-click to inject into the "
            "selected element.\n\n"
            "**Export** — click the document icon (Ctrl+E) to export to Typst. "
            "Click the print icon (Ctrl+Shift+P) to compile to PDF via typst.\n\n"
            "## First steps\n\n"
            "- Open **Preferences** (Ctrl+,) to customise the palette and snippets\n"
            "- Set a date and browse the RCL readings card\n"
            "- Build a service order and save it as a **template** for future use\n"
        )

        def _find_doc(name: str) -> Path | None:
            p = Path(__file__).parent / name
            if p.exists():
                return p
            try:
                import rubric_package as _rp
                p2 = Path(_rp.__file__).parent / "data" / name
                if p2.exists():
                    return p2
            except ImportError:
                pass
            return None

        _cl = _find_doc("CHANGELOG.md")
        whats_new = (_cl.read_text(encoding="utf-8") if _cl
                     else "# What's New\n\nNo changelog available.")

        typst_text = (
            "# Installing Typst\n\n"
            "Rubric exports to Typst (`.typ`) and compiles to PDF. "
            "Typst is bundled with Rubric — no separate install needed.\n\n"
            "If you need to install or update typst manually:\n\n"
            "## Option A — cargo\n\n"
            "```\n"
            "cargo install typst-cli\n"
            "```\n\n"
            "## Option B — package manager\n\n"
            "```\n"
            "# openSUSE\n"
            "sudo zypper install typst\n\n"
            "# Debian/Ubuntu (24.04+)\n"
            "sudo apt install typst\n\n"
            "# Arch\n"
            "sudo pacman -S typst\n"
            "```\n\n"
            "## Verify\n\n"
            "```\n"
            "typst --version\n"
            "```\n"
        )

        tabs.append_page(_text_page(welcome_text), Gtk.Label(label="Welcome"))
        tabs.append_page(_text_page(whats_new),    Gtk.Label(label="What's New"))
        tabs.append_page(_text_page(typst_text),   Gtk.Label(label="Typst"))
        tabs.set_current_page(1 if is_new_version else 0)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.append(tabs)
        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_margin_start(16); btn_row.set_margin_end(16)
        btn_row.set_margin_top(8); btn_row.set_margin_bottom(14)
        sp = Gtk.Box(); sp.set_hexpand(True); btn_row.append(sp)
        close_btn = Gtk.Button(label="Get started" if not is_new_version else "Let's go")
        close_btn.add_css_class("suggested-action")
        def _on_win_close(_w):
            config.last_seen_version = APP_VERSION
            config.save()
            if on_done:
                GLib.idle_add(on_done)
            return False
        close_btn.connect("clicked", lambda _: win.close())
        win.connect("close-request", _on_win_close)
        btn_row.append(close_btn)
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
        if AUTOSAVE_PATH.exists():
            dlg = Adw.MessageDialog(transient_for=self, heading="Restore unsaved work?",
                                    body="An autosave was found from a previous session. Restore it?")
            dlg.add_response("discard","Discard"); dlg.add_response("restore","Restore")
            dlg.set_response_appearance("restore", Adw.ResponseAppearance.SUGGESTED); dlg.set_default_response("restore")
            def on_resp(d,r):
                if r=="restore": self._load_file(str(AUTOSAVE_PATH), mark_unsaved=True)
                else:
                    self._clear_autosave()
                    self._open_last_file()
            dlg.connect("response", on_resp); dlg.present()
        else:
            self._open_last_file()
        return False

    def _open_last_file(self):
        for path in config.recent_files:
            if Path(path).exists():
                self._load_file(path)
                break

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
        self._content_widget.set_content("")
        self._clear_order_list(); self.selected_date=None; self._set_date_label("No date selected")
        self.readings_card.set_visible(False); self._current_readings={}
        for _box_attr in ("_obs_status_box", "_prev_obs_box"):
            b = getattr(self, _box_attr, None)
            if b:
                while b.get_first_child():
                    b.remove(b.get_first_child())
        self.current_file=None; self.typ_file=None; self.modified=False
        self._selected_global_idx=-1; self._update_title()
        self.service_bulletin_text = ""
        self.service_attendance = 0
        self.service_debrief = ""
        if hasattr(self, "_bulletin_edit_btn") and self._bulletin_edit_btn.get_active():
            self._bulletin_edit_btn.set_active(False)
        if getattr(self, "_preview_webview", None):
            self._preview_webview.load_html("", None)

    def _apply_template(self, items: list[dict]):
        """Load template items into the current (already-reset) service."""
        for d in items:
            e = _entry_from_dict(d)
            self.service_entries.append(e)
        self._add_recurring_elements()
        self._refresh_order_list()

    def _add_recurring_elements(self):
        """Append any recurring elements not already present in the service."""
        if not config.recurring_elements:
            return
        existing_names = {e.name.strip().lower() for e in self.service_entries
                          if isinstance(e, ServiceItem)}
        for name in config.recurring_elements:
            if name.strip().lower() not in existing_names:
                item = ServiceItem(name, "")
                default_note = config.element_defaults.get(name, "")
                if default_note:
                    item.content_typst = default_note
                self.service_entries.append(item)

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
                    self._add_recurring_elements()
                    self._refresh_order_list()
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
                    if r == "ok":
                        if blank_sw.get_active():
                            self._add_recurring_elements()
                            self._refresh_order_list()
                        else:
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
            new_entries = [_entry_from_dict(d) for d in data.get("items",[])]
            self._reset_state(); self.service_title_entry.set_text(data.get("title",""))
            self.service_entries.extend(new_entries)
            self._refresh_order_list()
            saved_date = data.get("date")
            if saved_date:
                from datetime import date as pydate
                try:
                    self.selected_date = pydate.fromisoformat(saved_date)
                    self._set_date_label(self.selected_date.strftime("%-d %B %Y"))
                    self._update_readings(self.selected_date)
                except ValueError: pass
            # Restore linked .typ path if present and file still exists
            saved_tex = data.get("typ_file") or data.get("tex_file")
            if saved_tex and Path(saved_tex).exists():
                self.typ_file = saved_tex
            self._update_tex_btn()
            self.service_bulletin_text = data.get("bulletin_text", "")
            self.service_attendance = data.get("attendance", 0)
            self.service_debrief    = data.get("debrief", "")
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

    def _suggest_filename(self) -> str:
        """Build a smart filename from the selected date and liturgical info."""
        if self.selected_date:
            try:
                info = get_liturgical_info(self.selected_date)
                week = info.get("week", "")
                yr = self.selected_date.year
                if week:
                    clean = re.sub(r"[^\w\s\-]", "", week).strip()
                    clean = re.sub(r"\s+", " ", clean)
                    return f"{clean} {yr}.liturgy"
            except Exception:
                pass
        title = self.service_title_entry.get_text().strip()
        if title:
            clean = re.sub(r"[^\w\s\-]", "", title).strip()
            return f"{clean}.liturgy"
        return "service.liturgy"

    def save_file_as(self):
        liturgy_dir = self._repo_subdir("liturgy")
        initial = str(liturgy_dir) if liturgy_dir else config.last_dir
        dlg = Gtk.FileDialog(title="Save service", initial_name=self._suggest_filename())
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
            self._update_save_state_chip()
            if getattr(self, "_deferred_save_id", None):
                GLib.source_remove(self._deferred_save_id); self._deferred_save_id = None
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
            body="This will remove the section divider and all its elements. Use Undo (Ctrl+Z) to reverse before saving.",
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
        """Export congregational bulletin — multi-target dialog."""
        if config.simple_mode:
            self._export_bulletin_html()
            return
        self._show_export_dialog()

    def _show_export_dialog(self) -> None:
        """Multi-target export dialog with checkboxes for all output formats."""
        win = Adw.Window(transient_for=self, modal=True, title="Export")
        win.set_default_size(380, 0)
        win.set_resizable(False)

        tv = Adw.ToolbarView()
        hdr = Adw.HeaderBar()
        hdr.set_show_end_title_buttons(False)
        tv.add_top_bar(hdr)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_start(20); box.set_margin_end(20)
        box.set_margin_top(12); box.set_margin_bottom(20)

        grp = Adw.PreferencesGroup(title="Select outputs")

        def _make_row(title: str, subtitle: str, active: bool) -> Gtk.CheckButton:
            cb = Gtk.CheckButton()
            cb.set_active(active)
            row = Adw.ActionRow(title=title, subtitle=subtitle)
            row.add_suffix(cb)
            row.set_activatable_widget(cb)
            grp.add(row)
            return cb

        cb_print   = _make_row("Bulletin — Print",   "half-letter booklet, compile to PDF", True)
        cb_digital = _make_row("Bulletin — Digital", "full letter with hyperlinks",          False)
        cb_ms      = _make_row("Manuscript",          "leader copy with all notes",           False)
        cb_html    = _make_row("HTML",                "web or email, opens in browser",       False)
        box.append(grp)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        sp = Gtk.Box(); sp.set_hexpand(True); btn_row.append(sp)
        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.add_css_class("flat")
        cancel_btn.connect("clicked", lambda _: win.close())
        btn_row.append(cancel_btn)
        export_btn = Gtk.Button(label="Export")
        export_btn.add_css_class("suggested-action")

        def _on_export(_b: Gtk.Button) -> None:
            win.close()
            if cb_print.get_active():   self._export_bulletin_file(digital=False)
            if cb_digital.get_active(): self._export_bulletin_file(digital=True)
            if cb_ms.get_active():      self.quick_export_typst()
            if cb_html.get_active():    self._export_bulletin_html_typst()

        export_btn.connect("clicked", _on_export)
        btn_row.append(export_btn)
        box.append(btn_row)

        tv.set_content(box)
        win.present()

    def _export_bulletin_html_typst(self) -> None:
        """Export bulletin as HTML, using typst compile --format html (0.13+) or fallback."""
        typst = self._find_typst()
        if not typst:
            self.export_html()
            return

        import tempfile as _tf
        try:
            typ_src = self._build_bulletin_typst(digital=True)
        except Exception:
            self._export_bulletin_html()
            return

        def run() -> None:
            # Version check runs in the background thread so it never blocks the main loop.
            html_supported = False
            try:
                ver_result = subprocess.run(
                    [typst, "--version"], capture_output=True, text=True, timeout=5,
                )
                m = re.search(r"(\d+)\.(\d+)", ver_result.stdout)
                if m:
                    html_supported = (int(m.group(1)), int(m.group(2))) >= (0, 13)
            except Exception:
                pass

            if not html_supported:
                GLib.idle_add(self._export_bulletin_html)
                return

            try:
                with _tf.NamedTemporaryFile(
                    suffix=".typ", delete=False, mode="w", encoding="utf-8",
                    prefix="rubric_html_",
                ) as f:
                    f.write(typ_src)
                    typ_path = Path(f.name)
                html_path = typ_path.with_suffix(".html")
                result = subprocess.run(
                    self._typst_compile_cmd(
                        typst, str(typ_path), str(html_path),
                        extra=["--format", "html"],
                    ),
                    capture_output=True, text=True, timeout=60,
                    encoding="utf-8", errors="replace",
                )
                if result.returncode == 0 and html_path.exists():
                    GLib.idle_add(
                        lambda: Gtk.show_uri(None, html_path.as_uri(), 0))
                    GLib.idle_add(lambda: self._show_toast(
                        "Opened in browser — use File → Print to save", timeout=6))
                else:
                    GLib.idle_add(self._export_bulletin_html)
            except Exception:
                GLib.idle_add(self._export_bulletin_html)

        threading.Thread(target=run, daemon=True).start()

    def _build_bulletin_html(self) -> str:
        """Build and return the bulletin as an HTML string."""
        import re as _re
        from datetime import date as _date

        # Use manual bulletin override if set
        override = getattr(self, "service_bulletin_text", "").strip()
        if override:
            escaped = _re.sub(r'&', '&amp;', override)
            escaped = _re.sub(r'<', '&lt;', escaped)
            paragraphs = "".join(
                f"<p>{line}</p>" if line.strip() else "<br>"
                for line in escaped.splitlines()
            )
            return (
                "<!DOCTYPE html><html><head>"
                "<meta charset='utf-8'>"
                "<style>body{font-family:serif;max-width:680px;margin:2em auto;"
                "padding:0 1em;line-height:1.6}p{margin:0.2em 0}</style>"
                "</head><body>" + paragraphs + "</body></html>"
            )

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

        strip_latex = strip_typst_for_html

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

        scroll_script = (
            "<script>"
            "document.addEventListener('DOMContentLoaded',function(){"
            "var k='rubric_scroll_y';"
            "var s=sessionStorage.getItem(k);"
            "if(s)window.scrollTo(0,parseInt(s,10));"
            "window.addEventListener('scroll',function(){"
            "sessionStorage.setItem(k,window.scrollY);});"
            "});"
            "</script>"
        )

        lines = [
            "<!DOCTYPE html><html lang='en'>",
            f"<head><meta charset='utf-8'><title>{esc(church)} – {esc(title)}</title>",
            f"<style>{css}</style>{scroll_script}</head><body>",
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

        cover_img = b.get("cover_image", "").strip()
        if cover_img and Path(cover_img).is_file():
            img_uri = GLib.filename_to_uri(cover_img, None)
            lines.append(
                f"<div style='text-align:center;margin:12px 0'>"
                f"<img src='{img_uri}' alt='Cover image' "
                f"style='max-width:100%;max-height:220px;object-fit:contain'>"
                f"</div>"
            )

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
                if si.content_typst:
                    clean = strip_latex(si.content_typst)
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

    def _build_manuscript_html(self) -> str:
        """Build a simple HTML preview of the leader manuscript (fallback for no typst)."""
        def esc(s):
            return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

        title    = self.service_title_entry.get_text() or "Order of Service"
        date_str = self.selected_date.strftime("%-d %B %Y") if self.selected_date else ""

        css = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: Georgia, serif; font-size: 11pt; color: #111;
       max-width: 7in; margin: 0 auto; padding: 0.6in 0.5in; }
.title { font-size: 15pt; font-weight: bold; text-align: center; margin-bottom: 4px; }
.date  { font-size: 11pt; font-style: italic; text-align: center; color: #555; margin-bottom: 16px; }
hr     { border: none; border-top: 1px solid #bbb; margin: 12px 0; }
h2     { font-size: 12pt; font-weight: bold; font-variant: small-caps; text-align: center;
         margin: 18px 0 6px; border-top: 1px solid #ccc; padding-top: 10px; }
.el-name { font-weight: bold; font-variant: small-caps; font-size: 11pt;
            border-bottom: 0.5px solid #bbb; margin: 10px 0 2px; padding-bottom: 2px; }
.leader { font-style: italic; color: #555; font-size: 9.5pt; margin-left: 5px; }
.note   { font-size: 10pt; margin: 4px 0 0 0; line-height: 1.6; white-space: pre-wrap; }
.leader-note, .rubric-note { display: block; background: #fff0f0;
               border-left: 3px solid #b91c1c; padding: 5px 8px; border-radius: 0 3px 3px 0;
               font-size: 9.5pt; font-style: italic; color: #b91c1c; margin: 4px 0; }
"""
        scroll_script = (
            "<script>"
            "document.addEventListener('DOMContentLoaded',function(){"
            "var k='rubric_scroll_y_ms';"
            "var s=sessionStorage.getItem(k);"
            "if(s)window.scrollTo(0,parseInt(s,10));"
            "window.addEventListener('scroll',function(){"
            "sessionStorage.setItem(k,window.scrollY);});"
            "});"
            "</script>"
        )

        lines = [
            "<!DOCTYPE html><html lang='en'>",
            f"<head><meta charset='utf-8'><title>Manuscript – {esc(title)}</title>",
            f"<style>{css}</style>{scroll_script}</head><body>",
            f"<div class='title'>{esc(title)}</div>",
        ]
        if date_str:
            lines.append(f"<div class='date'>{esc(date_str)}</div>")
        lines.append("<hr>")

        for sec, items in self._grouped_entries():
            if sec:
                lines.append(f"<h2>{esc(sec)}</h2>")
            for si in items:
                if not isinstance(si, ServiceItem):
                    continue
                leader_html = (f"<span class='leader'>({esc(si.leader)})</span>"
                               if si.leader else "")
                lines.append(f"<div class='el-name'>{esc(si.name)}{leader_html}</div>")
                rubric = getattr(si, "rubric_note", "").strip()
                if rubric:
                    lines.append(f"<span class='rubric-note'>{esc(rubric)}</span>")
                if si.content_typst:
                    clean = strip_typst_for_html(si.content_typst, manuscript=True)
                    lines.append(f"<div class='note'>{clean.replace(chr(10), '<br>')}</div>")

        lines.append("</body></html>")
        return "\n".join(lines)

    def _export_bulletin_html(self):
        """Simple-mode bulletin: print via WebKit if available, else open in browser."""
        if _WEBKIT_OK:
            self._print_bulletin_webkit()
        else:
            import tempfile
            html = self._build_bulletin_html()
            with tempfile.NamedTemporaryFile(
                    mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
                f.write(html)
                tmp = f.name
            Gtk.show_uri(None, GLib.filename_to_uri(tmp, None), 0)
            self._show_toast("Bulletin opened in browser — use File → Print to print", timeout=6)

    def _print_bulletin_webkit(self):
        """Print the bulletin HTML directly using WebKit's print dialog."""
        try:
            html = self._build_bulletin_html()
        except Exception:
            return
        wv = _WebKit.WebView()
        wv.load_html(html, None)
        self._print_webview = wv  # keep reference alive
        def on_load(view, event):
            if event == _WebKit.LoadEvent.FINISHED:
                op = _WebKit.PrintOperation.new(view)
                op.run_dialog(self)
        wv.connect("load-changed", on_load)

    def _export_bulletin_file(self, digital: bool):
        title = self.service_title_entry.get_text() or "bulletin"
        date_str = self.selected_date.strftime("%Y-%m-%d") if self.selected_date else "undated"
        church = config.bulletin.get("church_name", "").replace(" ", "_") or "Bulletin"
        suffix = "digital" if digital else "print"
        default_name = f"{church}_{date_str}_{suffix}.typ"
        bul_dir = self._repo_subdir("bulletins")
        typ_dir = self._repo_subdir("typ")
        initial = str(bul_dir) if bul_dir else (str(typ_dir) if typ_dir else config.last_dir)
        dlg = Gtk.FileDialog(title="Save bulletin as…", initial_name=default_name)
        dlg.set_initial_folder(Gio.File.new_for_path(initial))
        filters = Gio.ListStore.new(Gtk.FileFilter)
        f = Gtk.FileFilter(); f.set_name("Typst (*.typ)"); f.add_pattern("*.typ")
        filters.append(f); dlg.set_filters(filters)
        dlg.save(self, None, lambda d, r, dig=digital: self._on_bulletin_save(d, r, dig))

    def _on_bulletin_save(self, dlg, result, digital: bool):
        try:
            f = dlg.save_finish(result)
        except Exception:
            return  # User cancelled
        path = f.get_path()
        config.last_dir = str(Path(path).parent)
        try:
            typ_src = self._build_bulletin_typst(digital=digital)
        except Exception as e:
            self._error("Could not generate bulletin", str(e))
            return
        try:
            Path(path).write_text(typ_src, encoding="utf-8")
        except Exception as e:
            self._error("Could not save bulletin", str(e))
            return
        self._show_toast(f"Bulletin saved: {Path(path).name}")
        self._compile_bulletin_typst(path)

    def _compile_bulletin_typst(self, typ_path_str: str):
        """Compile bulletin .typ to PDF in background thread, then open it."""
        typ_path = Path(typ_path_str)
        typst = self._find_typst()
        if not typst:
            self._show_toast("Bulletin saved — install typst to compile to PDF", timeout=6)
            return

        pdf_path = typ_path.with_suffix(".pdf")
        # Capture toast locally — _compiling_toast is shared with the manuscript
        # compile path, so if both run simultaneously the shared ref would be wrong.
        _toast = Adw.Toast.new("Compiling bulletin…")
        _toast.set_timeout(0)
        self._toast_overlay.add_toast(_toast)

        def run():
            try:
                result = subprocess.run(
                    self._typst_compile_cmd(typst, str(typ_path), str(pdf_path)),
                    capture_output=True, text=True, timeout=60,
                    encoding="utf-8", errors="replace",
                )
                GLib.idle_add(self._on_bulletin_compiled, result, typ_path, pdf_path, _toast)
            except subprocess.TimeoutExpired:
                def _on_timeout(t=_toast):
                    try: t.dismiss()
                    except Exception: pass
                    self._show_toast("Bulletin compile timed out.", 8)
                GLib.idle_add(_on_timeout)
            except Exception as e:
                def _on_error(msg=str(e), t=_toast):
                    try: t.dismiss()
                    except Exception: pass
                    self._show_toast(f"Bulletin compile error: {msg}", 8)
                GLib.idle_add(_on_error)

        threading.Thread(target=run, daemon=True).start()

    def _on_bulletin_compiled(self, result, typ_path: Path, pdf_path: Path,
                              _toast: "Adw.Toast | None" = None):
        try: (_toast or self._compiling_toast).dismiss()
        except Exception: pass

        if result.returncode != 0:
            err = (result.stderr or result.stdout or "").strip()
            msg = format_typst_error(err) if err else "typst error"
            self._show_toast(f"Bulletin compile failed: {msg[:100]}", timeout=10)
            return

        dest_dir = self._repo_subdir("bulletins")
        if dest_dir and pdf_path.exists():
            dest = dest_dir / pdf_path.name
            try:
                shutil.move(str(pdf_path), str(dest))
                pdf_path = dest
            except OSError:
                pass
        if pdf_path.exists():
            toast = Adw.Toast.new(f"✓ {pdf_path.name}")
            toast.set_timeout(6)
            toast.set_button_label("Send by email…")
            toast.connect("button-clicked", lambda _: self._show_send_bulletin_dialog(pdf_path))
            self._toast_overlay.add_toast(toast)
            if config.github_repo:
                pub_toast = Adw.Toast.new("Publish bulletin to web?")
                pub_toast.set_timeout(10)
                pub_toast.set_button_label("Publish…")
                pub_toast.connect("button-clicked", lambda _, p=pdf_path: self._publish_bulletin_to_web(p))
                self._toast_overlay.add_toast(pub_toast)
            Gtk.show_uri(None, pdf_path.as_uri(), 0)
        else:
            self._show_toast("Compiled — PDF not found.", timeout=6)

    def _publish_bulletin_to_web(self, pdf_path: Path):
        """Copy the bulletin PDF to the repo's bulletins/ folder, regenerate the index, and push."""
        repo = config.github_repo
        if not repo:
            self._show_toast("Set up a GitHub repo in Preferences first"); return
        bulletins_dir = Path(repo) / "bulletins"
        try:
            bulletins_dir.mkdir(exist_ok=True)
        except OSError as e:
            self._show_toast(f"Could not create bulletins/ folder: {e}"); return

        dest = bulletins_dir / pdf_path.name
        if pdf_path.resolve() != dest.resolve() and pdf_path.exists():
            try:
                shutil.copy2(str(pdf_path), str(dest))
            except OSError as e:
                self._show_toast(f"Could not copy PDF: {e}"); return

        self._generate_bulletins_index(bulletins_dir)
        self._show_toast("Pushing bulletin to GitHub…", timeout=30)

        def run():
            try:
                date_str = dest.stem
                subprocess.run(
                    _GIT + ["-C", repo, "add", "bulletins/"],
                    check=True, capture_output=True, timeout=30)
                subprocess.run(
                    _GIT + ["-C", repo, "commit", "-m", f"Bulletin {date_str}"],
                    check=True, capture_output=True, timeout=30)
                subprocess.run(
                    _GIT + ["-C", repo, "push"],
                    check=True, capture_output=True, timeout=60)
                url = self._github_pages_url("bulletins/")
                msg = f"Published! {url}" if url else "Published to GitHub!"
                GLib.idle_add(lambda: self._show_toast(msg, timeout=12) or False)
            except subprocess.CalledProcessError as e:
                err = (e.stderr or b"").decode(errors="replace").strip()[:120]
                GLib.idle_add(lambda: self._show_toast(f"Publish failed: {err}", timeout=10) or False)
            except Exception as exc:
                GLib.idle_add(lambda: self._show_toast(f"Publish failed: {exc}", timeout=10) or False)

        threading.Thread(target=run, daemon=True).start()

    def _generate_bulletins_index(self, bulletins_dir: Path):
        """Write bulletins/index.html listing all PDFs, newest first."""
        pdfs = sorted(bulletins_dir.glob("*.pdf"), key=lambda p: p.stem, reverse=True)
        church = config.bulletin.get("church_name", "") or "Bulletins"
        rows = "".join(
            f'      <li><a href="{p.name}">{p.stem.replace("_", " ")}</a></li>\n'
            for p in pdfs
        )
        html = (
            f'<!DOCTYPE html>\n<html lang="en">\n<head>\n'
            f'<meta charset="UTF-8">\n'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            f'<title>{church}</title>\n'
            f'<style>body{{font-family:Georgia,serif;max-width:600px;margin:40px auto;padding:0 20px}}'
            f'h1{{font-size:1.4em}}ul{{list-style:none;padding:0}}li{{margin:.5em 0}}'
            f'a{{color:#333;text-decoration:none;border-bottom:1px solid #ccc}}'
            f'a:hover{{border-color:#333}}</style>\n</head>\n<body>\n'
            f'<h1>{church}</h1>\n<ul>\n{rows}</ul>\n</body>\n</html>\n'
        )
        (bulletins_dir / "index.html").write_text(html, encoding="utf-8")

    def _github_pages_url(self, subpath: str = "") -> str:
        """Derive a GitHub Pages URL from the repo's git remote."""
        import re
        remote = self._detect_github_remote()
        if not remote:
            return ""
        m = re.search(r'github\.com[:/]([^/]+)/([^/\.]+)', remote)
        if not m:
            return ""
        user, repo = m.group(1), m.group(2).rstrip(".git")
        return f"https://{user}.github.io/{repo}/{subpath}"

    def _show_send_bulletin_dialog(self, pdf_path=None):
        """Show a helper dialog for emailing the bulletin."""
        import urllib.parse
        b = config.bulletin
        church_email = b.get("email", "").strip()
        svc_title = self.service_title_entry.get_text().strip() or "Order of Service"
        date_str = self.selected_date.strftime("%-d %B %Y") if self.selected_date else ""
        default_subject = f"Sunday Bulletin — {svc_title}" + (f" ({date_str})" if date_str else "")

        win = Adw.Window(transient_for=self, modal=True, title="Send Bulletin by Email")
        win.set_default_size(440, 0); win.set_resizable(False)
        tv = Adw.ToolbarView()
        hdr = Adw.HeaderBar(); hdr.set_show_end_title_buttons(False)
        tv.add_top_bar(hdr); win.set_content(tv)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.set_margin_start(20); box.set_margin_end(20)
        box.set_margin_top(16); box.set_margin_bottom(20)

        grp = Adw.PreferencesGroup()
        to_row = Adw.EntryRow(title="To")
        to_row.set_text(church_email)
        subject_row = Adw.EntryRow(title="Subject")
        subject_row.set_text(default_subject)
        grp.add(to_row); grp.add(subject_row)
        box.append(grp)

        if pdf_path and pdf_path.exists():
            file_lbl = Gtk.Label(label=f"Attachment: {pdf_path.name}")
            file_lbl.add_css_class("caption"); file_lbl.add_css_class("dim-label")
            file_lbl.set_xalign(0)
            box.append(file_lbl)
            note = Gtk.Label(label="Your mail client will open — attach the PDF manually from the folder that opens.")
            note.set_wrap(True); note.add_css_class("dim-label"); note.set_xalign(0)
            box.append(note)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        if pdf_path and pdf_path.exists():
            folder_btn = Gtk.Button(label="Show PDF folder")
            folder_btn.add_css_class("flat")
            folder_btn.connect("clicked", lambda _: Gtk.show_uri(None, pdf_path.parent.as_uri(), 0))
            btn_row.append(folder_btn)
        sp = Gtk.Box(); sp.set_hexpand(True); btn_row.append(sp)
        cancel_btn = Gtk.Button(label="Cancel"); cancel_btn.add_css_class("flat")
        cancel_btn.connect("clicked", lambda _: win.close())
        btn_row.append(cancel_btn)
        open_btn = Gtk.Button(label="Open mail client")
        open_btn.add_css_class("suggested-action")
        def _open_mail(_b):
            to = to_row.get_text().strip()
            subj = urllib.parse.quote(subject_row.get_text().strip())
            mailto = f"mailto:{to}?subject={subj}"
            Gtk.show_uri(None, mailto, 0)
            win.close()
        open_btn.connect("clicked", _open_mail)
        btn_row.append(open_btn)
        box.append(btn_row)

        tv.set_content(box)
        win.present()

    def _build_bulletin_typst(self, digital: bool = False) -> str:
        """Build complete Typst source for the congregational bulletin.

        Print mode: half-letter (5.5×8.5 in), fold for booklet.
        Digital mode: full letter, hyperlinks.
        """
        from datetime import date as pydate
        b = config.bulletin
        church   = _typst_escape(b.get("church_name", ""))
        address  = _typst_escape(b.get("address", ""))
        svc_time = _typst_escape(b.get("service_time", ""))
        website  = b.get("website", "").strip()
        email    = b.get("email", "").strip()
        phone    = _typst_escape(b.get("phone", ""))
        mission  = _typst_escape(b.get("mission", ""))
        welcome  = _typst_escape(b.get("welcome", ""))
        access   = _typst_escape(b.get("accessibility", ""))
        title    = _typst_escape(self.service_title_entry.get_text() or "Order of Service")
        date_str = _typst_escape(
            self.selected_date.strftime("%-d %B %Y") if self.selected_date else "")

        template_name = "bulletin_digital" if digital else "bulletin_print"
        _bul_cols = config.preamble.get("bulletin", {}).get("columns", 2)
        _hdg_override = self._preamble_heading_typst("bulletin")
        parts: list[str] = [
            "// Congregational Bulletin — generated by Rubric",
            self._load_typst_preamble(template_name),
            '',
            TYPST_SHARED,
            '',
        ]
        if _hdg_override:
            parts += [_hdg_override, '']

        # ── Cover page / compact header ───────────────────────────────────────
        cover_style = b.get("cover_style", "full")
        cover_img = b.get("cover_image", "").strip()
        if cover_style == "compact":
            # Compact: small centred block at the top of page 1, no page break
            parts.append('#align(center)[')
            parts.append(f'  #text(size: 1.2em, weight: "bold")[#smallcaps[{church}]]')
            if address or svc_time:
                detail = " · ".join(filter(None, [address, svc_time]))
                parts.append(f'  #linebreak()#text(size: 0.8em)[{detail}]')
            parts.append(f'  #linebreak()#v(0.3em)#text(size: 1.1em, weight: "bold")[{title}]')
            if date_str:
                parts.append(f'  #linebreak()#text(size: 0.9em)[{date_str}]')
            parts += [']', '#v(0.6em)', '#line(length: 100%, stroke: 0.5pt)', '#v(0.4em)', '']
        else:
            # Full title page
            parts.append('#v(1.5cm)')
            parts.append('#align(center)[')
            if cover_img and Path(cover_img).is_file():
                safe = cover_img.replace("\\", "/")
                parts.append(
                    f'  #image("{safe}", width: 70%, height: 5cm, fit: "contain")')
                parts.append('  #v(0.6em)')
            parts.append(f'  #text(size: 1.5em, weight: "bold")[#smallcaps[{church}]]')
            parts.append('  #linebreak()')
            if address:
                parts.append(f'  #text(size: 0.85em)[{address}]')
                parts.append('  #linebreak()')
            parts.append(f'  #text(size: 0.85em)[{svc_time}]')
            parts.append('  #v(2cm)')
            parts.append(f'  #text(size: 1.5em, weight: "bold")[{title}]')
            parts.append('  #linebreak()')
            if date_str:
                parts.append(f'  #text(size: 1.2em)[{date_str}]')
                parts.append('  #linebreak()')
            if website or email or phone:
                parts.append('  #v(1cm)')
                parts.append('  #text(size: 0.85em)[')
                if website:
                    w_esc = _typst_escape(website)
                    if digital:
                        parts.append(
                            f'    #link("https://{website}")[{w_esc}] #linebreak()')
                    else:
                        parts.append(f'    {w_esc} #linebreak()')
                if email:
                    e_esc = _typst_escape(email)
                    if digital:
                        parts.append(
                            f'    #link("mailto:{email}")[{e_esc}] #linebreak()')
                    else:
                        parts.append(f'    {e_esc} #linebreak()')
                if phone:
                    parts.append(f'    {phone} #linebreak()')
                parts.append('  ]')
            if welcome:
                parts += ['  #v(1cm)', f'  #emph[{welcome}]']
            parts += [']', '#pagebreak()', '']

        # ── Service order ─────────────────────────────────────────────────────
        # Two-pass: group by section, then render with balanced columns.
        _bul_sections: list[tuple[str | None, list]] = []
        _cur_title: str | None = None
        _cur_items: list = []
        for _entry in self.service_entries:
            if isinstance(_entry, SectionDivider):
                _bul_sections.append((_cur_title, _cur_items))
                _cur_title = _entry.title
                _cur_items = []
            elif isinstance(_entry, ServiceItem) and _entry.show_in_bulletin:
                _cur_items.append(_entry)
        _bul_sections.append((_cur_title, _cur_items))

        def _render_bul_item(si: "ServiceItem", target: list) -> None:
            target += ['', f'== {_typst_escape(si.name)}', '']
            if getattr(si, "bulletin_heading_only", False):
                return
            _summary = getattr(si, "bulletin_summary", "")
            if _summary:
                target.append(linebreak_fix(_summary))
                return
            _name_lower = si.name.lower()
            _is_hymn = any(k in _name_lower
                           for k in ("hymn", "psalm", "sung", "song", "anthem", "gloria"))
            _content = si.content_typst
            if _is_hymn and _content:
                _hm = re.match(
                    r'^((?:VU|MV|LUS|TLUS|MWS)\s+\d+)\s*[—–-]?\s*(.*)',
                    _content, re.DOTALL)
                if _hm:
                    _ref  = _typst_escape(_hm.group(1).strip())
                    _rest = _typst_escape(
                        _hm.group(2).strip().split("\n")[0]) if _hm.group(2).strip() else ""
                    if _rest:
                        target.append(f'#hymnref("{_ref}", [_{_rest}_])')
                    else:
                        target.append(f'*{_ref}*')
                else:
                    target.append(linebreak_fix(strip_leader_notes(_content)))
            elif _content:
                target.append(linebreak_fix(strip_leader_notes(_content)))

        for _sec_title, _sec_items in _bul_sections:
            if _sec_title is not None:
                parts += [f'= {_typst_escape(_sec_title)}', '']
            if not _sec_items:
                continue
            if _bul_cols >= 2 and len(_sec_items) > 1:
                def _bul_weight(si: "ServiceItem") -> float:
                    base = 1.5
                    if getattr(si, "bulletin_heading_only", False):
                        return base
                    _summ = getattr(si, "bulletin_summary", "")
                    if _summ:
                        base += len(_summ) / 100.0
                    elif si.content_typst:
                        base += len(strip_leader_notes(si.content_typst)) / 100.0
                    return base
                _weights = [_bul_weight(si) for si in _sec_items]
                _total = sum(_weights)
                _cum = 0.0
                _mid = (len(_sec_items) + 1) // 2
                for _i, _w in enumerate(_weights):
                    _cum += _w
                    if _cum >= _total / 2.0:
                        _mid = _i + 1
                        break
                _left: list[str] = []
                _right: list[str] = []
                for _si in _sec_items[:_mid]:
                    _render_bul_item(_si, _left)
                for _si in _sec_items[_mid:]:
                    _render_bul_item(_si, _right)
                parts += [
                    f'#grid(columns: (1fr, 1fr), gutter: 0.5em, align: top, [',
                    '\n'.join(_left),
                    '], [',
                    '\n'.join(_right),
                    '])',
                    '',
                ]
            else:
                for _si in _sec_items:
                    _render_bul_item(_si, parts)

        # ── Acknowledgements block ────────────────────────────────────────────
        staff = b.get("staff", [])
        _congregation_leaders = {"all", "congregation", "everyone", "all:"}
        leaders: dict[str, list[str]] = {}
        for entry in self.service_entries:
            if (isinstance(entry, ServiceItem) and entry.leader and entry.show_in_bulletin
                    and entry.leader.strip().lower() not in _congregation_leaders):
                leaders.setdefault(entry.leader, []).append(entry.name)

        if staff or leaders:
            parts += [
                '#v(12pt)',
                '#align(center, line(length: 40%, stroke: 0.4pt))',
                '#align(center)[#text(size: 0.85em)[',
            ]
            for member in staff:
                role = _typst_escape(member.get("role", ""))
                name = _typst_escape(member.get("name", ""))
                em   = member.get("email", "")
                if digital and em:
                    parts.append(
                        f'  #emph[{role}:] #link("mailto:{em}")[{name}] #linebreak()')
                else:
                    parts.append(f'  #emph[{role}:] {name} #linebreak()')
            for person, roles in leaders.items():
                parts.append(
                    f'  {_typst_escape(person)} '
                    f'(#emph[{_typst_escape(", ".join(roles))}]) #linebreak()')
            parts += [']]', '']

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
                parts += [
                    '#pagebreak()',
                    '#align(center, text(size: 1.2em, weight: "bold")[#smallcaps[Announcements]])',
                    '#v(4pt)',
                    '',
                ]
                for ann in active:
                    parts.append(_note_for_typst(ann))
                    parts.append('#v(6pt)')

        # ── Back page: mission, contact, accessibility ────────────────────────
        if mission or access or email or website:
            parts += ['#pagebreak()', '#v(1fr)', '#align(center)[']
            if mission:
                parts.append(f'  #emph[#text(size: 0.9em)[{mission}]]')
                parts.append('  #linebreak()')
            if website or email or phone:
                parts.append('  #text(size: 0.85em)[')
                if website:
                    parts.append(f'    {_typst_escape(website)} #linebreak()')
                if email:
                    parts.append(f'    {_typst_escape(email)} #linebreak()')
                if phone:
                    parts.append(f'    {phone} #linebreak()')
                parts.append('  ]')
            if access:
                if mission or website or email or phone:
                    parts.append('  #linebreak()')
                parts.append(f'  #text(size: 0.9em)[{access}]')
            parts += [']', '#v(1fr)']

        return "\n".join(parts) + "\n"

    def export_html(self):
        title = self.service_title_entry.get_text() or "Order of Service"
        date_str = self.selected_date.strftime("%-d %B %Y") if self.selected_date else ""

        import tempfile, re as _re

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
                if si.content_typst:
                    clean = strip_typst_for_html(si.content_typst)
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
                _ct = strip_typst_plain(si.content_typst) if si.content_typst else ""
                if _ct: line += f"  \u2014  {_ct.split(chr(10))[0]}"
                lines.append(line)
        try:
            with open(path,"w",encoding="utf-8") as fp: fp.write("\n".join(lines))
        except Exception as e: self._error("Export error",str(e))

    def _update_tex_btn(self):
        """Update the Typst button tooltip to reflect current link state."""
        if self.typ_file:
            name = Path(self.typ_file).name
            self.tex_btn.set_tooltip_text(
                f"Export to {name} (Ctrl+E)\nRight-click to change file"
            )
        else:
            self.tex_btn.set_tooltip_text(
                "Export to Typst… (Ctrl+E)\nChoose a file to link"
            )

    def _build_manuscript_typst(self) -> str:
        """Build Typst source for the service order / leader manuscript."""
        _ms_cols = config.preamble.get("manuscript", {}).get("columns", 2)
        _ms_hdg_override = self._preamble_heading_typst("manuscript")
        parts = [
            "// Leader Manuscript — generated by Rubric",
            self._load_typst_preamble("manuscript"),
            '',
            TYPST_SHARED,
            '',
        ]
        if _ms_hdg_override:
            parts += [_ms_hdg_override, '']

        groups = [(sec, items) for sec, items in self._grouped_entries() if items]

        def _render_ms_item(si: "ServiceItem", target: list) -> None:
            leader_str = (
                f' #text(size: 0.85em, style: "italic")[(_{_typst_escape(si.leader)}_)]'
                if si.leader else "")
            target.append(f'== {_typst_escape(si.name)}{leader_str}')
            rubric = getattr(si, "rubric_note", "")
            if rubric:
                target.append(f'#rubric-note[{_typst_escape(rubric)}]')
            if si.content_typst:
                target.append(linebreak_fix(si.content_typst))
            target.append('')

        def _ms_weight(si: "ServiceItem") -> float:
            w = 2.0  # heading + spacing
            if si.content_typst:
                w += len(si.content_typst) / 80.0
            return w

        def _ms_split(items: list) -> int:
            weights = [_ms_weight(si) for si in items]
            total = sum(weights)
            cumulative = 0.0
            for i, w in enumerate(weights):
                cumulative += w
                if cumulative >= total / 2.0:
                    return i + 1
            return (len(items) + 1) // 2

        for sec, items in groups:
            if sec:
                parts += [f'= {_typst_escape(sec)}', '']

            if _ms_cols >= 2 and len(items) > 1 and sec is not None:
                mid = _ms_split(items)
                _left: list[str] = []
                _right: list[str] = []
                for si in items[:mid]:
                    _render_ms_item(si, _left)
                for si in items[mid:]:
                    _render_ms_item(si, _right)
                parts += [
                    '#grid(columns: (1fr, 1fr), gutter: 1em, align: top, [',
                    '\n'.join(_left),
                    '], [',
                    '\n'.join(_right),
                    '])',
                    '',
                ]
            else:
                for si in items:
                    _render_ms_item(si, parts)

        return "\n".join(parts) + "\n"

    def _write_typst(self, path: str):
        """Write manuscript Typst to path, record as linked file, save the .liturgy."""
        try:
            Path(path).write_text(self._build_manuscript_typst(), encoding="utf-8")
            self.typ_file = path
            self._update_tex_btn()
            if self.current_file:
                with open(self.current_file, "w", encoding="utf-8") as f:
                    json.dump(self._service_data(), f, indent=2, ensure_ascii=False)
            else:
                self._show_toast("Typst exported — save your service (Ctrl+S) to persist the link.", timeout=5)
        except Exception as e:
            self._error("Export error", str(e))

    def quick_export_typst(self):
        """One-click export: write directly if linked, else ask for a file."""
        if self.typ_file:
            self._write_typst(self.typ_file)
        else:
            self.export_typst()

    def compile_typst_pdf(self):
        """Export to .typ then compile with typst, open the resulting PDF."""
        if not self.typ_file:
            self._show_toast("Export to Typst first (Ctrl+E), then compile again.", timeout=5)
            return

        self._write_typst(self.typ_file)
        typ_path = Path(self.typ_file)
        pdf_path = typ_path.with_suffix(".pdf")

        typst = self._find_typst()
        if not typst:
            self._show_toast("typst not found — install typst or add it to PATH", timeout=8)
            return

        _ms_toast = Adw.Toast.new("Compiling PDF…")
        _ms_toast.set_timeout(0)
        self._toast_overlay.add_toast(_ms_toast)
        self._compiling_toast = _ms_toast
        self.pdf_btn.set_sensitive(False)

        def run_typst():
            try:
                result = subprocess.run(
                    self._typst_compile_cmd(typst, str(typ_path), str(pdf_path)),
                    capture_output=True, text=True, timeout=60,
                    encoding="utf-8", errors="replace",
                )
                GLib.idle_add(self._on_compile_done, result, typ_path, pdf_path, _ms_toast)
            except subprocess.TimeoutExpired:
                GLib.idle_add(self._on_compile_error, "typst timed out after 60 seconds.", _ms_toast)
            except Exception as e:
                GLib.idle_add(self._on_compile_error, str(e), _ms_toast)

        threading.Thread(target=run_typst, daemon=True).start()

    def _on_compile_done(self, result, typ_path: Path, pdf_path: Path,
                         _toast: "Adw.Toast | None" = None):
        self.pdf_btn.set_sensitive(True)
        try: (_toast or self._compiling_toast).dismiss()
        except Exception: pass

        if result.returncode != 0:
            err = (result.stderr or result.stdout or "").strip()
            msg = format_typst_error(err) if err else "typst error"
            self._show_toast(f"Compilation failed: {msg[:100]}", timeout=10)
            return

        pdf_dir = self._repo_subdir("pdf")
        if pdf_dir and pdf_path.exists():
            dest = pdf_dir / pdf_path.name
            try:
                shutil.move(str(pdf_path), str(dest))
                pdf_path = dest
            except OSError:
                pass
        if pdf_path.exists():
            toast = Adw.Toast.new(f"✓ {pdf_path.name}")
            toast.set_timeout(6)
            toast.set_button_label("Send by email…")
            toast.connect("button-clicked", lambda _: self._show_send_bulletin_dialog(pdf_path))
            self._toast_overlay.add_toast(toast)
            Gtk.show_uri(None, pdf_path.as_uri(), 0)
        else:
            self._show_toast("Compiled but PDF not found.", timeout=6)

    def _on_compile_error(self, message: str, _toast: "Adw.Toast | None" = None):
        self.pdf_btn.set_sensitive(True)
        try: (_toast or self._compiling_toast).dismiss()
        except Exception: pass
        self._show_toast(f"Compile error: {message[:80]}", timeout=10)

    def _unlink_typ(self):
        self.typ_file = None
        self._update_tex_btn()

    def export_typst(self):
        """Full file-chooser export for the manuscript Typst file."""
        typ_dir = self._repo_subdir("typ")
        if self.current_file:
            default = Path(self.current_file).stem + ".typ"
        else:
            title   = self.service_title_entry.get_text() or "service"
            default = title.replace(" ", "_").lower() + ".typ"
        folder = str(typ_dir) if typ_dir else (
            str(Path(self.current_file).parent) if self.current_file else config.last_dir
        )
        dlg = Gtk.FileDialog(title="Export Typst", initial_name=default)
        dlg.set_initial_folder(Gio.File.new_for_path(folder))
        filters = Gio.ListStore.new(Gtk.FileFilter)
        f = Gtk.FileFilter(); f.set_name("Typst files (*.typ)"); f.add_pattern("*.typ")
        filters.append(f); dlg.set_filters(filters)
        dlg.save(self, None, self._on_export_typst_response)

    def _on_export_typst_response(self, dlg, result):
        try: f = dlg.save_finish(result)
        except GLib.Error: return
        path = f.get_path()
        if not path.endswith(".typ"): path += ".typ"
        self._write_typst(path)

    # ── Leader ────────────────────────────────────────────────────────────────

    def _on_leader_changed(self, entry):
        if self._updating_note: return
        idx = self._selected_index()
        if not (0 <= idx < len(self.service_entries)): return
        entry_obj = self.service_entries[idx]
        if not isinstance(entry_obj, ServiceItem): return
        if not getattr(self, "_leader_undo_pushed", False):
            self._push_undo()
            self._leader_undo_pushed = True
        entry_obj.leader = entry.get_text()
        row = self._find_row_for_index(idx)
        if isinstance(row, Adw.ActionRow):
            row.set_subtitle(entry_obj.leader if entry_obj.leader
                             else self._note_preview(entry_obj.content_typst))
        self._mark_modified()

    def _on_bulletin_toggled(self, _btn):
        if self._updating_note: return
        idx = self._selected_index()
        if not (0 <= idx < len(self.service_entries)): return
        e = self.service_entries[idx]
        if not isinstance(e, ServiceItem): return
        self._push_undo()
        self._bulletin_heading_only_active = not self._bulletin_heading_only_active
        e.bulletin_heading_only = self._bulletin_heading_only_active
        if self._bulletin_heading_only_active:
            self._bulletin_heading_lbl.set_markup("<b>Bulletin</b>")
        else:
            self._bulletin_heading_lbl.set_text("Bulletin")
        row = self._find_row_for_index(idx)
        if row:
            if not e.show_in_bulletin:
                row.set_opacity(0.45)
            elif e.bulletin_heading_only:
                row.set_opacity(0.7)
            else:
                row.set_opacity(1.0)
        self._mark_modified()

    def _on_bulletin_summary_changed(self, entry):
        if self._updating_note: return
        idx = self._selected_index()
        if not (0 <= idx < len(self.service_entries)): return
        e = self.service_entries[idx]
        if not isinstance(e, ServiceItem): return
        e.bulletin_summary = entry.get_text()
        self._mark_modified()

    def _on_duration_changed(self, spin):
        if self._updating_note: return
        idx = self._selected_index()
        if not (0 <= idx < len(self.service_entries)): return
        e = self.service_entries[idx]
        if not isinstance(e, ServiceItem): return
        self._push_undo()
        e.duration = int(spin.get_value())
        self._update_time_total()
        self._mark_modified()

    def _update_time_total(self):
        items = [e for e in self.service_entries if isinstance(e, ServiceItem)]
        timed = [e for e in items if getattr(e, "duration", 0) > 0]
        if not timed:
            self._time_bar.set_visible(False)
            return
        total = sum(e.duration for e in timed)
        self._time_bar.set_visible(True)
        # Simple over-time warning: assume ~75 min typical service
        TARGET = 75
        if total > TARGET:
            self._time_bar.set_markup(
                f'<span color="#B91C1C">~{total} min total</span>'
                f'<span color="#B91C1C" size="small">  ({total - TARGET} over)</span>')
        else:
            self._time_bar.set_markup(f'<span color="#15803D">~{total} min total</span>')

    # ── Hymn suggestions ──────────────────────────────────────────────────────

    def _update_hymn_suggestions(self, week: str, season: str):
        """Rebuild the suggestions chip strip for the current RCL week."""
        while (c := self._sugg_chips_box.get_first_child()):
            self._sugg_chips_box.remove(c)

        if not _SUGG_OK:
            self._hymn_suggestions_available = False
            self.sugg_revealer.set_reveal_child(False)
            return

        suggestions = _get_hymn_suggestions(week, season)
        if not suggestions:
            self._hymn_suggestions_available = False
            self.sugg_revealer.set_reveal_child(False)
            return

        import urllib.parse
        from hymn_lookup import HYMNALS
        _yt_svg = Path(__file__).parent / "data" / "youtube.svg"
        if not _yt_svg.exists():
            try:
                import rubric_package as _rp
                _yt_svg = Path(_rp.__file__).parent / "data" / "youtube.svg"
            except Exception:
                _yt_svg = None
        try:
            from gi.repository import GdkPixbuf
            _yt_pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(_yt_svg), 18, 13, True) if _yt_svg and _yt_svg.exists() else None
        except Exception:
            _yt_pb = None

        for prefix, number, title in suggestions:
            pill = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            pill.add_css_class("linked"); pill.add_css_class("sugg-pill")

            # Main chip: title only — number shown in tooltip and Hymnary popup
            chip = Gtk.Button()
            chip.add_css_class("flat")
            chip.set_tooltip_text(f"{prefix} {number} — {title}\nClick to open on Hymnary  ·  Right-click to add to service")
            title_lbl = Gtk.Label(label=title)
            title_lbl.set_margin_start(6); title_lbl.set_margin_end(4)
            title_lbl.set_wrap(False)
            title_lbl.set_max_width_chars(22)
            title_lbl.set_ellipsize(Pango.EllipsizeMode.END)  # PANGO_ELLIPSIZE_END
            chip.set_child(title_lbl)

            hymnal_id = HYMNALS.get(prefix, (prefix, ""))[0]
            hymnary_url = f"https://hymnary.org/hymn/{hymnal_id}/{number}"
            hymn_label = f"{prefix} {number} — {title}"
            if _WEBKIT_OK:
                chip.connect("clicked", lambda _b, u=hymnary_url, lbl=hymn_label:
                             self._show_hymnary_preview(u, lbl))
            else:
                chip.connect("clicked", lambda _b, u=hymnary_url: Gtk.show_uri(None, u, 0))

            rg = Gtk.GestureClick(); rg.set_button(3)
            def on_right(_g, _n, _x, _y, p=prefix, n=number, t=title):
                self._add_hymn_from_suggestion(p, n, t)
            rg.connect("pressed", on_right)
            chip.add_controller(rg)
            pill.append(chip)

            # YouTube button — right side of linked pill; white rect + accent-coloured play arrow
            yt_query = urllib.parse.quote(f"{prefix} {number} {title}")
            yt_url = f"https://www.youtube.com/results?search_query={yt_query}"
            yt_btn = Gtk.Button(tooltip_text=f"Search YouTube: {prefix} {number}")
            yt_btn.add_css_class("flat")
            import math as _math
            _yt_da = Gtk.DrawingArea(); _yt_da.set_size_request(26, 18)
            def _draw_yt(_da, cr, w, h):
                r = 3.5
                cr.new_path()
                cr.arc(r, r, r, _math.pi, -_math.pi / 2)
                cr.arc(w - r, r, r, -_math.pi / 2, 0)
                cr.arc(w - r, h - r, r, 0, _math.pi / 2)
                cr.arc(r, h - r, r, _math.pi / 2, _math.pi)
                cr.close_path()
                cr.set_source_rgb(1, 1, 1)
                cr.fill()
                try:
                    from gi.repository import Adw as _Adw
                    _sm = _Adw.StyleManager.get_default()
                    _rgba = _sm.get_accent_color().to_rgba(_sm.get_dark())
                    cr.set_source_rgba(_rgba.red, _rgba.green, _rgba.blue, _rgba.alpha)
                except Exception:
                    cr.set_source_rgb(0.11, 0.44, 0.85)
                mx, my = w * 0.36, h * 0.25
                cr.move_to(mx, my)
                cr.line_to(mx, h - my)
                cr.line_to(w - mx * 0.55, h * 0.5)
                cr.close_path()
                cr.fill()
            _yt_da.set_draw_func(_draw_yt)
            yt_btn.set_child(_yt_da)
            yt_btn.connect("clicked", lambda _b, u=yt_url: Gtk.show_uri(None, u, 0))
            pill.append(yt_btn)

            self._sugg_chips_box.append(pill)

        self._hymn_suggestions_available = True
        self.sugg_revealer.set_reveal_child(
            not getattr(self, "_sugg_dismissed", False)
            and getattr(self, "_hymn_mode_btn", None) is not None
            and self._hymn_mode_btn.get_active()
        )

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
                # Prepend to content — hymn ref goes at the top
                entry.content_typst = ref + ("\n" + entry.content_typst
                                             if entry.content_typst else "")
                self._content_widget.set_content(entry.content_typst)
                row = self._find_row_for_index(idx)
                if isinstance(row, Adw.ActionRow):
                    row.set_subtitle(self._note_preview(entry.content_typst))
                self._mark_modified()
                return
        # Nothing selected — create a new Hymn element as fallback
        self._push_undo()
        si = ServiceItem("Hymn", list(self._palette_listboxes.keys())[0] if self._palette_listboxes else "")
        si.content_typst = ref
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

    def _on_hymn_mode_toggled(self, btn):
        if self._updating_note: return
        active = btn.get_active()
        for w in self._hymn_toolbar_widgets:
            w.set_visible(active)
        self.sugg_revealer.set_reveal_child(
            active and getattr(self, "_hymn_suggestions_available", False)
        )
        if active:
            if hasattr(self, "hymn_status"): self.hymn_status.set_label("")
            if hasattr(self, "hymn_entry"): self.hymn_entry.set_text("")

    # ── AV sheet export ───────────────────────────────────────────────────────

    def export_av_sheet(self):
        if self.current_file:
            default = Path(self.current_file).stem + "_av_sheet.html"
            folder  = str(Path(self.current_file).parent)
        else:
            default = "av_sheet.html"; folder = config.last_dir
        dlg = Gtk.FileDialog(title="Export AV sheet", initial_name=default)
        dlg.set_initial_folder(Gio.File.new_for_path(folder))
        filters = Gio.ListStore.new(Gtk.FileFilter)
        f = Gtk.FileFilter(); f.set_name("HTML files (*.html)"); f.add_pattern("*.html")
        filters.append(f); dlg.set_filters(filters)
        dlg.save(self, None, self._on_export_av_response)

    def _on_export_av_response(self, dlg, result):
        try: f = dlg.save_finish(result)
        except GLib.Error: return
        path = f.get_path()
        if not path.endswith(".html"): path += ".html"

        title    = self.service_title_entry.get_text() or "Order of Service"
        date_str = self.selected_date.strftime("%-d %B %Y") if self.selected_date else ""
        church   = config.bulletin.get("church_name", "")

        css = """
body { font-family: Arial, sans-serif; font-size: 11pt; margin: 1cm auto;
       max-width: 9in; color: #000; }
h1 { font-size: 14pt; margin-bottom: 2px; }
.meta { font-size: 10pt; color: #555; margin-bottom: 14px; }
table { border-collapse: collapse; width: 100%; }
th { background: #222; color: #fff; padding: 6px 10px; text-align: left; font-size: 10pt; }
td { padding: 5px 10px; vertical-align: top; font-size: 10pt; border-bottom: 1px solid #ddd; }
tr.section-row td { background: #e8e8e8; font-weight: bold; font-variant: small-caps;
                    letter-spacing: 0.05em; padding: 4px 10px; }
.hymn { font-weight: bold; color: #1a5276; }
@media print { body { margin: 0; } @page { margin: 0.6in; } }
"""

        def esc(s): return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

        def hymn_ref(note: str) -> str:
            m = re.match(r'^((?:VU|MV|LUS|TLUS|MWS)\s+\d+)', note.strip())
            return m.group(1) if m else ""

        def slide_text(note: str) -> str:
            lines = note.strip().splitlines()
            out = []
            for line in lines:
                line = re.sub(r'\\[a-zA-Z]+\*?\{([^}]*)\}', r'\1', line)
                line = re.sub(r'\\[a-zA-Z]+\*?\s*', '', line).strip()
                if line and not re.match(r'^(?:VU|MV|LUS|TLUS|MWS)\s+\d+', line):
                    out.append(line)
            return " / ".join(out[:3]) + ("…" if len(out) > 3 else "")

        rows = [
            "<!DOCTYPE html><html lang='en'>",
            "<head><meta charset='utf-8'>",
            f"<title>AV Sheet – {esc(title)}</title>",
            f"<style>{css}</style></head><body>",
            f"<h1>{esc(church + ' — ' if church else '')}{esc(title)}</h1>",
            f"<div class='meta'>{esc(date_str)} &nbsp;·&nbsp; AV / Projection operator sheet</div>",
            "<table>",
            "<thead><tr><th>Section</th><th>Element</th><th>Leader</th>"
            "<th>Hymn ref</th><th>Slide / note</th></tr></thead>",
            "<tbody>",
        ]

        current_section = ""
        for entry in self.service_entries:
            if isinstance(entry, SectionDivider):
                current_section = entry.title
                rows.append(
                    f"<tr class='section-row'><td colspan='5'>{esc(current_section)}</td></tr>"
                )
            elif isinstance(entry, ServiceItem):
                note_src = entry.content_typst
                rows.append(
                    f"<tr><td>{esc(current_section)}</td>"
                    f"<td><strong>{esc(entry.name)}</strong></td>"
                    f"<td>{esc(entry.leader)}</td>"
                    f"<td class='hymn'>{esc(hymn_ref(note_src))}</td>"
                    f"<td>{esc(slide_text(note_src))}</td></tr>"
                )

        rows += ["</tbody></table>", "</body></html>"]

        try:
            Path(path).write_text("\n".join(rows), encoding="utf-8")
            toast = Adw.Toast.new(f"AV sheet saved")
            toast.set_timeout(4)
            toast.set_button_label("Open")
            toast.connect("button-clicked",
                          lambda _: Gtk.show_uri(None, GLib.filename_to_uri(path, None), 0))
            self._toast_overlay.add_toast(toast)
        except Exception as e:
            self._error("AV sheet export error", str(e))

    # ── Leader's order PDF ────────────────────────────────────────────────────

    def export_minister_pdf(self):
        if self.current_file:
            default = Path(self.current_file).stem + "_leader.pdf"
            folder  = str(Path(self.current_file).parent)
        else:
            default = "leader_order.pdf"; folder = config.last_dir
        dlg = Gtk.FileDialog(title="Export leader's order PDF", initial_name=default)
        dlg.set_initial_folder(Gio.File.new_for_path(folder))
        filters = Gio.ListStore.new(Gtk.FileFilter)
        f = Gtk.FileFilter(); f.set_name("PDF files (*.pdf)"); f.add_pattern("*.pdf")
        filters.append(f); dlg.set_filters(filters)
        dlg.save(self, None, self._on_export_minister_response)

    def _on_export_minister_response(self, dlg, result):
        try: f = dlg.save_finish(result)
        except GLib.Error: return
        path = Path(f.get_path())
        if path.suffix.lower() != ".pdf":
            path = path.with_suffix(".pdf")
        typ_path = path.with_suffix(".typ")
        src = self._build_minister_typst()
        try:
            typ_path.write_text(src, encoding="utf-8")
        except Exception as e:
            self._error("Export error", str(e)); return
        self._compile_minister_typst(typ_path, path)

    def _build_minister_typst(self) -> str:
        """Build Typst source for the leader/minister's order with prep notes."""
        title  = _typst_escape(self.service_title_entry.get_text() or "Order of Service")
        date_str = _typst_escape(
            self.selected_date.strftime("%-d %B %Y") if self.selected_date else "")
        church = _typst_escape(config.bulletin.get("church_name", ""))

        parts = [
            "// Leader's Order — generated by Rubric",
            '#set page(paper: "us-letter",'
            ' margin: (top: 0.75in, bottom: 0.75in, left: 0.7in, right: 0.7in))',
            '#set text(size: 10pt)',
            '#set par(justify: false)',
            '',
            TYPST_SHARED,
            '',
            '#align(center)[',
        ]
        if church:
            parts.append(f'  #text(size: 1.2em, weight: "bold")[#smallcaps[{church}]]')
            parts.append('  #linebreak()')
        parts += [
            f'  #text(size: 1.4em, weight: "bold")[{title}]',
            '  #linebreak()',
        ]
        if date_str:
            parts.append(f'  {date_str}')
        parts += [
            ']',
            '#v(6pt)',
            '#line(length: 100%, stroke: 0.5pt)',
            '#v(8pt)',
            '#columns(2)[',
            '',
        ]

        for entry in self.service_entries:
            if isinstance(entry, SectionDivider):
                if entry.title in ("Word", "Response", "Sending"):
                    parts.append('#colbreak()')
                parts.append(f'=== {_typst_escape(entry.title)}')
                parts.append('')
            elif isinstance(entry, ServiceItem):
                leader_str = (
                    f' #text(size: 0.85em, style: "italic")[(_{_typst_escape(entry.leader)}_)]'
                    if entry.leader else "")
                dur = getattr(entry, "duration", 0)
                dur_str = (
                    f' #h(1fr) #text(size: 0.8em, fill: luma(120))[{dur}min]'
                    if dur else "")
                parts.append(f'*{_typst_escape(entry.name)}*{leader_str}{dur_str}')
                parts.append('')
                if entry.content_typst:
                    parts.append(f'#text(size: 0.9em)[{entry.content_typst}]')
                    parts.append('')
                parts.append('#v(4pt)')
                parts.append('')

        parts.append(']')
        return "\n".join(parts) + "\n"

    def _compile_minister_typst(self, typ_path: Path, pdf_path: Path):
        typst = self._find_typst()
        if not typst:
            self._show_toast("Typst saved — install typst to compile to PDF", 6); return

        toast = Adw.Toast.new("Compiling leader's order…")
        toast.set_timeout(0)
        self._toast_overlay.add_toast(toast)

        def run():
            try:
                result = subprocess.run(
                    self._typst_compile_cmd(typst, str(typ_path), str(pdf_path)),
                    capture_output=True, text=True, timeout=60,
                    encoding="utf-8", errors="replace",
                )
                GLib.idle_add(_done, result, toast, pdf_path)
            except Exception as e:
                GLib.idle_add(lambda msg=str(e): (
                    toast.dismiss(), self._show_toast(f"Compile error: {msg}", 8)))

        def _done(result, t, pdf):
            try: t.dismiss()
            except Exception: pass
            if result.returncode != 0:
                self._show_toast("Leader's order compile failed", 8); return
            done_toast = Adw.Toast.new(f"✓ {pdf.name}")
            done_toast.set_timeout(6)
            done_toast.set_button_label("Open")
            done_toast.connect("button-clicked",
                lambda _: Gtk.show_uri(None, GLib.filename_to_uri(str(pdf), None), 0))
            self._toast_overlay.add_toast(done_toast)

        threading.Thread(target=run, daemon=True).start()

    # ── Snippets ──────────────────────────────────────────────────────────────

    def open_snippets(self):
        if not _SNIP_OK:
            self._error("Snippets unavailable", "snippets.py not found.")
            return
        self._open_snippets_manager()

    def _open_snippets_manager(self, insert_on_activate: bool = True):
        """Full snippets manager: list, rich-text editor, tagging, CRUD."""
        snippets: list[dict] = load_snippets()

        win = Adw.Window(transient_for=self, modal=False)
        win.set_title("Snippets"); win.set_default_size(860, 640)

        tv = Adw.ToolbarView()
        hdr = Adw.HeaderBar()

        # New snippet button
        new_btn = Gtk.Button(icon_name="list-add-symbolic", tooltip_text="New snippet")
        new_btn.add_css_class("flat"); hdr.pack_start(new_btn)

        # Delete button
        del_btn = Gtk.Button(icon_name="list-remove-symbolic", tooltip_text="Delete snippet")
        del_btn.add_css_class("flat"); del_btn.set_sensitive(False); hdr.pack_start(del_btn)

        tv.add_top_bar(hdr)

        # ── Main split: list on left, editor on right ──────────────────────
        split = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        split.set_position(270)

        # ── Left: tag filter + snippet list ───────────────────────────────
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Tag filter chips
        tag_scroll = Gtk.ScrolledWindow()
        tag_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        tag_scroll.set_min_content_height(32)
        tag_flow = Gtk.FlowBox()
        tag_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        tag_flow.set_max_children_per_line(20)
        tag_flow.set_column_spacing(4); tag_flow.set_row_spacing(2)
        tag_flow.set_margin_start(8); tag_flow.set_margin_end(8)
        tag_flow.set_margin_top(4); tag_flow.set_margin_bottom(4)
        tag_scroll.set_child(tag_flow)
        left_box.append(tag_scroll)
        left_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # Snippet list
        list_scroll = Gtk.ScrolledWindow()
        list_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        list_scroll.set_vexpand(True)
        lb = Gtk.ListBox(); lb.set_selection_mode(Gtk.SelectionMode.SINGLE)
        lb.add_css_class("navigation-sidebar")
        list_scroll.set_child(lb)
        left_box.append(list_scroll)
        split.set_start_child(left_box)

        # ── Right: editor panel ────────────────────────────────────────────
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Name row
        name_entry = Gtk.Entry()
        name_entry.set_placeholder_text("Snippet name")
        name_entry.add_css_class("title-2")
        name_entry.set_margin_start(12); name_entry.set_margin_end(12)
        name_entry.set_margin_top(10); name_entry.set_margin_bottom(4)
        right_box.append(name_entry)

        # Tags row
        tags_entry = Gtk.Entry()
        tags_entry.set_placeholder_text("Tags (comma-separated, e.g. gathering, prayer)")
        tags_entry.add_css_class("caption")
        tags_entry.set_margin_start(12); tags_entry.set_margin_end(12)
        tags_entry.set_margin_bottom(6)
        right_box.append(tags_entry)

        right_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # Rich text editor
        from rubric_package.views.element_content import ElementContentWidget
        editor_widget = ElementContentWidget()
        editor_widget.set_vexpand(True)
        right_box.append(editor_widget)

        right_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # Bottom bar: save + insert
        bottom = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bottom.set_margin_start(12); bottom.set_margin_end(12)
        bottom.set_margin_top(8); bottom.set_margin_bottom(10)
        save_btn = Gtk.Button(label="Save")
        save_btn.add_css_class("flat")
        save_btn.set_sensitive(False)
        sp = Gtk.Box(); sp.set_hexpand(True); bottom.append(save_btn); bottom.append(sp)
        insert_btn = Gtk.Button(label="Insert into element")
        insert_btn.add_css_class("suggested-action")
        insert_btn.set_sensitive(False)
        bottom.append(insert_btn)
        right_box.append(bottom)

        split.set_end_child(right_box)
        tv.set_content(split); win.set_content(tv)

        # ── State ──────────────────────────────────────────────────────────
        _selected_idx: list[int] = [-1]
        _active_tag: list[str] = [""]  # "" = all

        def _get_all_tags() -> list[str]:
            tags: set[str] = set()
            for s in snippets:
                for t in s.get("tags", []):
                    tags.add(t.strip())
            return sorted(tags)

        def _rebuild_tag_filter():
            while tag_flow.get_first_child():
                tag_flow.remove(tag_flow.get_first_child())
            all_btn2 = Gtk.ToggleButton(label="All")
            all_btn2.add_css_class("pill"); all_btn2.add_css_class("flat")
            all_btn2.set_active(_active_tag[0] == "")
            def on_all(b):
                if b.get_active():
                    _active_tag[0] = ""; _rebuild_list()
            all_btn2.connect("toggled", on_all)
            tag_flow.append(all_btn2)
            for t in _get_all_tags():
                tb = Gtk.ToggleButton(label=t)
                tb.add_css_class("pill"); tb.add_css_class("flat")
                tb.set_active(_active_tag[0] == t)
                def on_tag(b, tag=t):
                    if b.get_active():
                        _active_tag[0] = tag; _rebuild_list()
                tb.connect("toggled", on_tag)
                tag_flow.append(tb)

        def _rebuild_list():
            while lb.get_first_child():
                lb.remove(lb.get_first_child())
            active_tag = _active_tag[0]
            for i, snip in enumerate(snippets):
                tags = snip.get("tags", [])
                if active_tag and active_tag not in tags:
                    continue
                row = Gtk.ListBoxRow(); row._snip_idx = i
                row_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                row_box.set_margin_start(8); row_box.set_margin_end(8)
                row_box.set_margin_top(6); row_box.set_margin_bottom(6)
                name_lbl = Gtk.Label(label=snip["name"])
                name_lbl.set_xalign(0); name_lbl.set_ellipsize(Pango.EllipsizeMode.END)  # PANGO_ELLIPSIZE_END
                name_lbl.add_css_class("body")
                row_box.append(name_lbl)
                if tags:
                    tag_lbl = Gtk.Label(label=", ".join(tags[:3]))
                    tag_lbl.set_xalign(0); tag_lbl.add_css_class("caption")
                    tag_lbl.add_css_class("dim-label")
                    row_box.append(tag_lbl)
                row.set_child(row_box); lb.append(row)
            # Re-select if possible
            if _selected_idx[0] >= 0:
                for child in _iter_listbox(lb):
                    if child._snip_idx == _selected_idx[0]:
                        lb.select_row(child); break

        def _iter_listbox(lb):
            row = lb.get_first_child()
            while row:
                yield row
                row = row.get_next_sibling()

        def _load_snippet(idx: int):
            _selected_idx[0] = idx
            snip = snippets[idx]
            name_entry.set_text(snip["name"])
            tags_entry.set_text(", ".join(snip.get("tags", [])))
            editor_widget.set_content(snip.get("content", ""))
            save_btn.set_sensitive(True)
            del_btn.set_sensitive(True)
            insert_btn.set_sensitive(True)

        def _save_current():
            idx = _selected_idx[0]
            if idx < 0: return
            snip = snippets[idx]
            snip["name"] = name_entry.get_text().strip() or snip["name"]
            raw_tags = tags_entry.get_text()
            snip["tags"] = [t.strip() for t in raw_tags.split(",") if t.strip()]
            snip["content"] = editor_widget.get_content()
            save_snippets(snippets)
            _rebuild_tag_filter()
            _rebuild_list()

        def on_row_selected(_lb, row):
            if row and hasattr(row, "_snip_idx"):
                _save_current()  # auto-save prev
                _load_snippet(row._snip_idx)

        lb.connect("row-selected", on_row_selected)

        def on_new(_b):
            _save_current()
            new_snip = {"name": "New snippet", "content": "", "tags": []}
            snippets.append(new_snip)
            save_snippets(snippets)
            _rebuild_tag_filter(); _rebuild_list()
            _load_snippet(len(snippets) - 1)
            # Select last row
            last = None
            for child in _iter_listbox(lb):
                last = child
            if last: lb.select_row(last); name_entry.grab_focus(); name_entry.select_region(0, -1)

        new_btn.connect("clicked", on_new)

        def on_delete(_b):
            idx = _selected_idx[0]
            if idx < 0: return
            snippets.pop(idx)
            save_snippets(snippets)
            _selected_idx[0] = -1
            save_btn.set_sensitive(False); del_btn.set_sensitive(False)
            insert_btn.set_sensitive(False)
            name_entry.set_text(""); tags_entry.set_text(""); editor_widget.clear()
            _rebuild_tag_filter(); _rebuild_list()

        del_btn.connect("clicked", on_delete)
        save_btn.connect("clicked", lambda _: _save_current())

        def on_insert(_b):
            idx = _selected_idx[0]
            if idx < 0: return
            _save_current()
            self._on_bible_insert(snippets[idx].get("content", ""))
            win.close()

        insert_btn.connect("clicked", on_insert)

        editor_widget.set_on_changed(lambda _: save_btn.set_sensitive(True))

        _rebuild_tag_filter(); _rebuild_list()

        # Auto-select first snippet if any
        first_row = lb.get_first_child()
        if first_row and hasattr(first_row, "_snip_idx"):
            lb.select_row(first_row)
            _load_snippet(first_row._snip_idx)

        win.present()

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
                # Detect hymn ref: first line of content that matches VU/MV/LUS pattern
                hymn_ref = ""
                _plain = strip_typst_plain(entry.content_typst) if entry.content_typst else ""
                if _plain:
                    m = re.match(r'^(VU|MV|LUS)\s+\d+[^$]*', _plain.split('\n')[0])
                    if m: hymn_ref = m.group(0)[:40]
                note_preview = ""
                if _plain:
                    first = _plain.split('\n')[0]
                    if not first.startswith(("VU ", "MV ", "LUS ")):
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

            _AUTH_HELP = (
                "GitHub requires a Personal Access Token (PAT) — passwords no longer work.\n\n"
                "To create one:\n"
                "1. Go to github.com → Settings → Developer settings\n"
                "   → Personal access tokens → Fine-grained tokens\n"
                "2. Generate a new token with Contents: Read and Write\n"
                "   permission for your repository\n"
                "3. Copy the token\n\n"
                "To save it so you're not asked again, run in a terminal:\n"
                "   git config --global credential.helper store\n"
                "Then push once — enter your GitHub username and the token\n"
                "as the password when prompted."
            )

            try:
                # ── Stage and commit local changes ──────────────────────────
                add_r = subprocess.run(_GIT + ["-C", repo, "add", "-A"],
                                       capture_output=True, text=True, timeout=10)
                if add_r.returncode != 0:
                    GLib.idle_add(abort, "Sync failed",
                                  add_r.stderr.strip() or "git add failed")
                    return

                status_r = subprocess.run(_GIT + ["-C", repo, "status", "--porcelain"],
                                          capture_output=True, text=True, timeout=5)
                if status_r.stdout.strip():
                    commit_r = subprocess.run(_GIT + ["-C", repo, "commit", "-m", msg],
                                              capture_output=True, text=True, timeout=15)
                    if commit_r.returncode != 0:
                        out = (commit_r.stderr or commit_r.stdout or "").strip()
                        GLib.idle_add(abort, "Sync failed (commit)", out)
                        return

                # ── Pull remote changes before pushing ──────────────────────
                has_remote = subprocess.run(
                    _GIT + ["-C", repo, "remote"],
                    capture_output=True, text=True, timeout=5
                ).stdout.strip()

                if has_remote:
                    pull_r = subprocess.run(
                        _GIT + ["-C", repo, "pull", "--rebase"],
                        capture_output=True, text=True, timeout=60
                    )
                    if pull_r.returncode != 0:
                        pull_out = (pull_r.stdout + pull_r.stderr).strip()
                        pull_low = pull_out.lower()
                        # Abort a broken rebase so the repo isn't left mid-rebase
                        subprocess.run(_GIT + ["-C", repo, "rebase", "--abort"],
                                       capture_output=True, timeout=10)
                        if "permission denied" in pull_low or "authentication" in pull_low:
                            GLib.idle_add(abort, "Authentication failed", _AUTH_HELP)
                        elif "conflict" in pull_low or "merge conflict" in pull_low:
                            GLib.idle_add(abort, "Sync conflict",
                                "Another computer has made changes that conflict with yours.\n\n"
                                "Open a terminal in your repository folder and run:\n"
                                "  git status\n"
                                "to see which files conflict, then resolve them manually.")
                        elif "no tracking" in pull_low or "no such ref" in pull_low \
                                or pull_out == "":
                            pass  # no upstream yet — first push will set it
                        else:
                            GLib.idle_add(abort, "Pull failed before push", pull_out[:400])
                            return

                # ── Push ────────────────────────────────────────────────────
                push_r = subprocess.run(_GIT + ["-C", repo, "push"],
                                        capture_output=True, text=True, timeout=30)
                if push_r.returncode != 0:
                    err_low = (push_r.stderr or "").lower()
                    if "no upstream" in err_low or "set-upstream" in err_low or \
                       "set the upstream" in err_low:
                        push_r = subprocess.run(
                            _GIT + ["-C", repo, "push", "--set-upstream", "origin", "HEAD"],
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
                        elif "Permission denied" in err or "Authentication failed" in err \
                                or "authentication" in err.lower():
                            self._error("Authentication failed", _AUTH_HELP)
                        else:
                            self._error("Push failed", err[:400])
                    else:
                        self._show_toast("✓ Synced to GitHub", timeout=4)

                GLib.idle_add(finish)

            except subprocess.TimeoutExpired:
                GLib.idle_add(abort, "Sync timed out — check your network connection.")
            except FileNotFoundError:
                GLib.idle_add(abort, "git not found", "Install git: sudo zypper install git")
            except Exception as e:
                GLib.idle_add(abort, "Sync error", str(e))

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
                r = subprocess.run(_GIT + ["-C", repo, "pull"],
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

    def _show_shortcuts_window(self):
        xml = """<?xml version='1.0' encoding='UTF-8'?>
<interface>
  <object class='GtkShortcutsWindow' id='sw'>
    <property name='modal'>True</property>
    <child>
      <object class='GtkShortcutsSection'>
        <property name='title'>Shortcuts</property>
        <child>
          <object class='GtkShortcutsGroup'>
            <property name='title'>File</property>
            <child><object class='GtkShortcutsShortcut'><property name='accelerator'>&lt;ctrl&gt;n</property><property name='title'>New service</property></object></child>
            <child><object class='GtkShortcutsShortcut'><property name='accelerator'>&lt;ctrl&gt;o</property><property name='title'>Open service</property></object></child>
            <child><object class='GtkShortcutsShortcut'><property name='accelerator'>&lt;ctrl&gt;s</property><property name='title'>Save</property></object></child>
            <child><object class='GtkShortcutsShortcut'><property name='accelerator'>&lt;ctrl&gt;&lt;shift&gt;s</property><property name='title'>Save as…</property></object></child>
            <child><object class='GtkShortcutsShortcut'><property name='accelerator'>&lt;ctrl&gt;&lt;shift&gt;l</property><property name='title'>Service planner</property></object></child>
          </object>
        </child>
        <child>
          <object class='GtkShortcutsGroup'>
            <property name='title'>Editing</property>
            <child><object class='GtkShortcutsShortcut'><property name='accelerator'>&lt;ctrl&gt;z</property><property name='title'>Undo</property></object></child>
            <child><object class='GtkShortcutsShortcut'><property name='accelerator'>&lt;ctrl&gt;&lt;shift&gt;z</property><property name='title'>Redo</property></object></child>
            <child><object class='GtkShortcutsShortcut'><property name='accelerator'>&lt;ctrl&gt;&lt;shift&gt;n</property><property name='title'>Add custom element</property></object></child>
            <child><object class='GtkShortcutsShortcut'><property name='accelerator'>&lt;ctrl&gt;d</property><property name='title'>Add section divider</property></object></child>
            <child><object class='GtkShortcutsShortcut'><property name='accelerator'>&lt;ctrl&gt;Up</property><property name='title'>Move element up</property></object></child>
            <child><object class='GtkShortcutsShortcut'><property name='accelerator'>&lt;ctrl&gt;Down</property><property name='title'>Move element down</property></object></child>
          </object>
        </child>
        <child>
          <object class='GtkShortcutsGroup'>
            <property name='title'>Tools</property>
            <child><object class='GtkShortcutsShortcut'><property name='accelerator'>&lt;ctrl&gt;&lt;shift&gt;f</property><property name='title'>Scripture search</property></object></child>
            <child><object class='GtkShortcutsShortcut'><property name='accelerator'>&lt;ctrl&gt;&lt;shift&gt;i</property><property name='title'>Snippets library</property></object></child>
            <child><object class='GtkShortcutsShortcut'><property name='accelerator'>&lt;ctrl&gt;&lt;shift&gt;k</property><property name='title'>Services library</property></object></child>
          </object>
        </child>
        <child>
          <object class='GtkShortcutsGroup'>
            <property name='title'>Export</property>
            <child><object class='GtkShortcutsShortcut'><property name='accelerator'>&lt;ctrl&gt;e</property><property name='title'>Quick export to Typst</property></object></child>
            <child><object class='GtkShortcutsShortcut'><property name='accelerator'>&lt;ctrl&gt;&lt;shift&gt;p</property><property name='title'>Compile PDF</property></object></child>
            <child><object class='GtkShortcutsShortcut'><property name='accelerator'>&lt;ctrl&gt;&lt;shift&gt;b</property><property name='title'>Export bulletin (HTML)</property></object></child>
            <child><object class='GtkShortcutsShortcut'><property name='accelerator'>&lt;ctrl&gt;&lt;shift&gt;g</property><property name='title'>Git commit and push</property></object></child>
          </object>
        </child>
        <child>
          <object class='GtkShortcutsGroup'>
            <property name='title'>Help</property>
            <child><object class='GtkShortcutsShortcut'><property name='accelerator'>F1</property><property name='title'>Help</property></object></child>
            <child><object class='GtkShortcutsShortcut'><property name='accelerator'>&lt;ctrl&gt;question</property><property name='title'>Keyboard shortcuts</property></object></child>
            <child><object class='GtkShortcutsShortcut'><property name='accelerator'>&lt;ctrl&gt;comma</property><property name='title'>Preferences</property></object></child>
          </object>
        </child>
      </object>
    </child>
  </object>
</interface>"""
        b = Gtk.Builder.new_from_string(xml, -1)
        sw = b.get_object("sw")
        sw.set_transient_for(self)
        sw.present()

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
        dlg.add_response("cancel",    "Cancel")
        dlg.add_response("html",      "HTML  (print from browser)")
        dlg.add_response("bulletin",  "Bulletin PDF")
        dlg.add_response("minister",  "Leader's order PDF")
        dlg.add_response("av",        "AV team sheet")
        if not simple:
            dlg.add_response("typst", "Typst")
            dlg.add_response("text",  "Plain text")
            dlg.add_response("csv",   "CSV")
        dlg.set_response_appearance("html",      Adw.ResponseAppearance.SUGGESTED)
        dlg.set_response_appearance("bulletin",  Adw.ResponseAppearance.SUGGESTED)
        dlg.set_response_appearance("minister",  Adw.ResponseAppearance.SUGGESTED)
        def on_resp(d, r):
            if r == "html":     self.export_html()
            elif r == "bulletin": self.export_bulletin()
            elif r == "minister": self.export_minister_pdf()
            elif r == "av":     self.export_av_sheet()
            elif r == "typst":  self.export_typst()
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

    def open_services(self, start_tab: str = "planner"):
        win = getattr(self, "_services_win", None)
        if win and win.get_visible():
            win.switch_tab(start_tab); win.present(); return
        self._services_win = ServicesWindow(main_window=self, start_tab=start_tab, transient_for=self)
        self._services_win.present()

    def open_planner(self): self.open_services("planner")
    def open_library(self): self.open_services("library")
    def open_archive(self): self.open_services("archive")

    def _open_observance_wiki(self, name: str):
        win = ObservanceWikiWindow(name=name, transient_for=self)
        win.present()

    def open_help(self, start_tab: str = "help"):
        win = getattr(self, "_help_win", None)
        if win and win.get_visible():
            win.switch_tab(start_tab); win.present(); return
        self._help_win = HelpWindow(main_window=self, start_tab=start_tab, transient_for=self)
        self._help_win.present()

    def open_bulletin_prefs(self):
        win = getattr(self, "_bulletin_prefs_win", None)
        if win and win.get_visible():
            win.present(); return
        self._bulletin_prefs_win = BulletinPrefsWindow(main_window=self, transient_for=self)
        self._bulletin_prefs_win.present()


# ── Services Window (Planner + Library + Archive) ────────────────────────────

class ServicesWindow(Adw.Window):
    """Unified Services window — Planner, Library, and Archive in one tabbed view."""

    _TAB_IDX = {"planner": 0, "library": 1, "archive": 2}

    def __init__(self, main_window, start_tab: str = "planner", **kw):
        super().__init__(title="Services", default_width=700, default_height=720, **kw)
        self._main = main_window
        self.set_modal(False)
        self._planner_folder: "Path | None" = None
        self._lib_search = ""; self._lib_expanded: set = set(); self._lib_selected = None
        self._lib_rebuilding = False; self._lib_mode = "services"
        self._arch_search = ""; self._arch_expanded: set = set()

        tv = Adw.ToolbarView()
        hdr = Adw.HeaderBar()
        tv.add_top_bar(hdr)

        self._nb = Gtk.Notebook()
        self._nb.set_show_border(False); self._nb.set_vexpand(True)
        self._nb.append_page(self._build_planner_tab(), Gtk.Label(label="Service Planner"))
        self._nb.append_page(self._build_library_tab(), Gtk.Label(label="Element Library"))
        self._nb.append_page(self._build_archive_tab(), Gtk.Label(label="Past Liturgies"))
        self._nb.set_current_page(self._TAB_IDX.get(start_tab, 0))

        tv.set_content(self._nb)
        self.set_content(tv)
        GLib.idle_add(self._load_all)

    def switch_tab(self, name: str):
        self._nb.set_current_page(self._TAB_IDX.get(name, 0))

    # ── Planner tab ───────────────────────────────────────────────────────────

    def _build_planner_tab(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        top.set_margin_start(12); top.set_margin_end(12)
        top.set_margin_top(10); top.set_margin_bottom(8)
        self._planner_folder_lbl = Gtk.Label()
        self._planner_folder_lbl.add_css_class("caption")
        self._planner_folder_lbl.add_css_class("dim-label")
        self._planner_folder_lbl.set_hexpand(True); self._planner_folder_lbl.set_xalign(0)
        self._planner_folder_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        top.append(self._planner_folder_lbl)
        choose_btn = Gtk.Button(label="Folder…"); choose_btn.add_css_class("flat")
        choose_btn.connect("clicked", self._on_choose_folder); top.append(choose_btn)
        refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text="Refresh")
        refresh_btn.connect("clicked", lambda _: self._load_planner()); top.append(refresh_btn)

        # View toggle: List | Calendar
        view_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        view_box.add_css_class("linked")
        self._planner_list_btn = Gtk.ToggleButton(label="List")
        self._planner_cal_btn  = Gtk.ToggleButton(label="Calendar")
        self._planner_cal_btn.set_group(self._planner_list_btn)
        self._planner_list_btn.set_active(True)
        view_box.append(self._planner_list_btn); view_box.append(self._planner_cal_btn)
        top.append(view_box)
        box.append(top)
        box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        self._planner_view_stack = Gtk.Stack()
        self._planner_view_stack.set_vexpand(True)

        # List view
        scroll = Gtk.ScrolledWindow(); scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._planner_list = Gtk.ListBox()
        self._planner_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self._planner_list.add_css_class("boxed-list")
        self._planner_list.set_margin_start(12); self._planner_list.set_margin_end(12)
        self._planner_list.set_margin_top(8); self._planner_list.set_margin_bottom(12)
        scroll.set_child(self._planner_list)
        self._planner_view_stack.add_named(scroll, "list")

        # Calendar view
        cal_scroll = Gtk.ScrolledWindow(); cal_scroll.set_vexpand(True)
        cal_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._planner_cal_box = Gtk.ListBox()
        self._planner_cal_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self._planner_cal_box.add_css_class("boxed-list")
        self._planner_cal_box.set_margin_start(12); self._planner_cal_box.set_margin_end(12)
        self._planner_cal_box.set_margin_top(8); self._planner_cal_box.set_margin_bottom(12)
        cal_scroll.set_child(self._planner_cal_box)
        self._planner_view_stack.add_named(cal_scroll, "calendar")

        def on_view_toggle(btn):
            if btn.get_active():
                self._planner_view_stack.set_visible_child_name(
                    "list" if btn is self._planner_list_btn else "calendar")
        self._planner_list_btn.connect("toggled", on_view_toggle)
        self._planner_cal_btn.connect("toggled",  on_view_toggle)

        box.append(self._planner_view_stack)
        return box

    def _init_planner_folder(self):
        repo = config.github_repo
        if repo:
            folder = Path(repo) / "liturgy"
            if folder.is_dir():
                self._planner_folder = folder
                self._planner_folder_lbl.set_text(str(folder)); return
        self._planner_folder_lbl.set_text("No folder — use 'Folder…' or set up GitHub in Preferences")

    def _on_choose_folder(self, _):
        dlg = Gtk.FileDialog(title="Choose folder containing .liturgy files")
        def on_chosen(d, r):
            try:
                f = d.select_folder_finish(r)
                self._planner_folder = Path(f.get_path())
                self._planner_folder_lbl.set_text(str(self._planner_folder))
                self._load_planner()
            except GLib.Error:
                pass
        dlg.select_folder(self, None, on_chosen)

    def _load_planner(self):
        while self._planner_list.get_first_child():
            self._planner_list.remove(self._planner_list.get_first_child())
        if not self._planner_folder or not self._planner_folder.is_dir():
            self._planner_list.append(self._status_row("No folder selected")); return

        from datetime import date as _date
        today = _date.today()
        try:
            from rubric_package.db import (service_index_update, service_index_get_mtime,
                service_index_all, service_index_prune)
            _db = True
        except ImportError:
            _db = False

        services = []; on_disk: set = set()
        for p in self._planner_folder.glob("*.liturgy"):
            path_str = str(p); on_disk.add(path_str)
            try:
                mtime = p.stat().st_mtime
                cached = service_index_get_mtime(path_str) if _db else None
                if _db and cached is not None and abs(cached - mtime) < 0.01: continue
                d = json.loads(p.read_text(encoding="utf-8"))
                if _db:
                    service_index_update(path_str, d.get("title","") or p.stem, d.get("date",""),
                        len([i for i in d.get("items",[]) if i.get("type") != "divider"]), mtime)
            except Exception:
                pass

        if _db and on_disk:
            service_index_prune(on_disk)
            for r in service_index_all():
                if r["path"] not in on_disk: continue
                try: sd = _date.fromisoformat(r["date"]) if r["date"] else None
                except ValueError: sd = None
                services.append((sd, r["title"] or Path(r["path"]).stem, r["item_count"], Path(r["path"])))
        elif not _db:
            for p in self._planner_folder.glob("*.liturgy"):
                try:
                    d = json.loads(p.read_text(encoding="utf-8"))
                    try: sd = _date.fromisoformat(d.get("date","")) if d.get("date") else None
                    except ValueError: sd = None
                    services.append((sd, d.get("title","") or p.stem,
                        len([i for i in d.get("items",[]) if i.get("type") != "divider"]), p))
                except Exception: pass

        if not services:
            self._planner_list.append(self._status_row(f"No .liturgy files in {self._planner_folder}")); return

        upcoming = sorted([(d,t,c,p) for d,t,c,p in services if d and d >= today], key=lambda x: x[0])
        past     = sorted([(d,t,c,p) for d,t,c,p in services if not d or d < today],
                          key=lambda x: x[0] or _date.min, reverse=True)

        def _sep(label):
            lbl = Gtk.Label(label=label); lbl.add_css_class("heading"); lbl.add_css_class("dim-label")
            lbl.set_xalign(0); lbl.set_margin_start(4); lbl.set_margin_top(12); lbl.set_margin_bottom(2)
            r = Gtk.ListBoxRow(); r.set_activatable(False); r.set_child(lbl)
            self._planner_list.append(r)

        if upcoming: _sep("Upcoming")
        for sd, title, count, path in upcoming:
            row = Adw.ActionRow(title=title, subtitle=f"{sd.strftime('%-d %B %Y')}  ·  {count} elements")
            row.set_activatable(True); row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
            row.connect("activated", lambda _r, p=str(path): self._open_service(p))
            self._planner_list.append(row)
        if past: _sep("Past services")
        for sd, title, count, path in past:
            date_label = sd.strftime("%-d %B %Y") if sd else "No date"
            row = Adw.ActionRow(title=title, subtitle=f"{date_label}  ·  {count} elements")
            row.set_activatable(True); row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
            row.connect("activated", lambda _r, p=str(path): self._open_service(p))
            self._planner_list.append(row)

        # Store for calendar view
        self._planner_services = services
        self._load_planner_calendar(services, today)

    def _plan_sunday(self, sunday):
        """Show a dialog to create a new .liturgy file for an unplanned Sunday."""
        folder = self._planner_folder
        if not folder:
            self._show_toast("No folder selected"); return

        try:
            info = get_liturgical_info(sunday)
            default_title = info.get("week", sunday.strftime("%-d %B %Y"))
        except Exception:
            default_title = sunday.strftime("%-d %B %Y")

        dlg = Adw.Window(transient_for=self, modal=True)
        dlg.set_title(f"Plan {sunday.strftime('%-d %B %Y')}")
        dlg.set_default_size(400, -1)
        tv = Adw.ToolbarView()
        tv.add_top_bar(Adw.HeaderBar())

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.set_margin_top(16); outer.set_margin_bottom(16)
        outer.set_margin_start(16); outer.set_margin_end(16)

        grp = Adw.PreferencesGroup()
        title_row = Adw.EntryRow(title="Service title")
        title_row.set_text(default_title)
        grp.add(title_row)

        # Build source list: "Default template", "Blank", then past services
        source_labels = ["Default template", "Blank service"]
        try:
            from rubric_package.db import element_services as _esvc
            past_svcs = _esvc(limit=30)
        except Exception:
            past_svcs = []
        for svc in past_svcs:
            stem = Path(svc["service_path"]).stem
            label = f"Copy structure: {svc.get('service_title') or stem}"
            if svc.get("service_date"):
                label += f"  ({svc['service_date']})"
            source_labels.append(label)

        source_row = Adw.ComboRow(title="Start from")
        source_row.set_model(Gtk.StringList.new(source_labels))
        source_row.set_expression(Gtk.PropertyExpression.new(Gtk.StringObject, None, "string"))
        grp.add(source_row)
        outer.append(grp)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_margin_top(16)
        sp = Gtk.Box(); sp.set_hexpand(True); btn_row.append(sp)
        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda _: dlg.close())
        btn_row.append(cancel_btn)
        create_btn = Gtk.Button(label="Create & Open")
        create_btn.add_css_class("suggested-action")

        def on_create(_b):
            title  = title_row.get_text().strip() or default_title
            idx    = source_row.get_selected()
            items  = []

            if idx == 0:
                # Default template
                tmpl = config.templates.get(
                    config.default_template,
                    next(iter(config.templates.values()), None))
                if tmpl:
                    for d in tmpl:
                        item = dict(d)
                        item["note"] = ""; item["bulletin_note"] = ""; item["content_typst"] = ""
                        items.append(item)
            elif idx >= 2 and past_svcs and (idx - 2) < len(past_svcs):
                # Copy element structure (names/sections only) from a past service
                svc = past_svcs[idx - 2]
                try:
                    from rubric_package.db import element_for_service as _ef
                    cur_sec = ""
                    for e in _ef(svc["service_path"]):
                        sec = e.get("section", "")
                        if sec and sec != cur_sec:
                            items.append({"type": "divider", "title": sec})
                            cur_sec = sec
                        items.append({"type": "item", "name": e.get("name", ""),
                                      "section": sec, "leader": e.get("leader", ""),
                                      "note": "", "bulletin_note": "", "content_typst": "",
                                      "show_in_bulletin": True, "duration": 0})
                except Exception:
                    pass
            # idx == 1 → blank, items stays []

            data = {"title": title, "date": sunday.isoformat(), "items": items}
            path = folder / f"{sunday.isoformat()}.liturgy"
            if not path.exists():
                try:
                    path.write_text(
                        __import__("json").dumps(data, indent=2, ensure_ascii=False),
                        encoding="utf-8")
                except Exception as exc:
                    self._show_toast(f"Could not create file: {exc}")
                    dlg.close(); return
            dlg.close()
            self._open_service(str(path))
            GLib.timeout_add(300, lambda: (self._load_planner(), False)[1])

        create_btn.connect("clicked", on_create)
        title_row.connect("entry-activated", lambda _: on_create(None))
        btn_row.append(create_btn)
        outer.append(btn_row)

        tv.set_content(outer); dlg.set_content(tv); dlg.present()

    def _load_planner_calendar(self, services, today):
        """Populate the calendar view: 4 past Sundays + 8 upcoming Sundays."""
        from datetime import date as _date, timedelta
        while self._planner_cal_box.get_first_child():
            self._planner_cal_box.remove(self._planner_cal_box.get_first_child())

        # Build a lookup: ISO date string → (title, count, path)
        by_date = {}
        for sd, title, count, path in services:
            if sd:
                by_date[sd.isoformat()] = (title, count, path)

        # Collect Sundays: last 4 + next 8
        days_since_sunday = (today.weekday() + 1) % 7
        last_sunday = today - timedelta(days=days_since_sunday)
        sundays = [last_sunday - timedelta(weeks=i) for i in range(3, 0, -1)]
        sundays += [last_sunday + timedelta(weeks=i) for i in range(0, 9)]

        try:
            _lect_ok = True
        except Exception:
            _lect_ok = False

        for sunday in sundays:
            iso = sunday.isoformat()
            is_past = sunday < today
            has_service = iso in by_date

            try:
                info = get_liturgical_info(sunday)
                week_str = info.get("week", "")
                colour   = info.get("colour_hex", "#888888")
            except Exception:
                week_str = ""; colour = "#888888"

            date_lbl = sunday.strftime("%-d %B %Y")
            if sunday == last_sunday:
                date_lbl = "This Sunday — " + date_lbl

            if has_service:
                svc_title, svc_count, svc_path = by_date[iso]
                subtitle = f"{week_str}  ·  {svc_count} elements"
                row = Adw.ActionRow(title=svc_title or date_lbl, subtitle=subtitle)
                row.set_activatable(True)
                row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
                row.connect("activated", lambda _r, p=str(svc_path): self._open_service(p))
            else:
                subtitle = week_str or date_lbl
                row = Adw.ActionRow(title=date_lbl if not week_str else date_lbl,
                                    subtitle=subtitle)
                row.set_activatable(False)
                if not is_past and self._planner_folder:
                    plan_btn = Gtk.Button(label="Plan…")
                    plan_btn.add_css_class("flat")
                    plan_btn.set_valign(Gtk.Align.CENTER)
                    plan_btn.connect("clicked", lambda _b, s=sunday: self._plan_sunday(s))
                    row.add_suffix(plan_btn)
                else:
                    not_planned = Gtk.Label(label="Not planned")
                    not_planned.add_css_class("dim-label"); not_planned.add_css_class("caption")
                    row.add_suffix(not_planned)

            # Colour dot for liturgical season
            dot = Gtk.Label()
            dot.set_markup(f'<span color="{colour}" size="x-large">●</span>')
            dot.set_valign(Gtk.Align.CENTER)
            dot.set_margin_end(4)
            row.add_prefix(dot)

            if is_past and not has_service:
                row.add_css_class("dim-label")

            self._planner_cal_box.append(row)

    # ── Library tab ───────────────────────────────────────────────────────────

    def _build_library_tab(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        top.set_margin_start(12); top.set_margin_end(12); top.set_margin_top(10); top.set_margin_bottom(6)
        se = Gtk.SearchEntry(); se.set_placeholder_text("Search elements…"); se.set_hexpand(True)
        se.connect("search-changed", lambda e: self._lib_rebuild(e.get_text().strip()))
        top.append(se)

        mode_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        mode_box.add_css_class("linked")
        self._lib_btn_svc  = Gtk.ToggleButton(label="By service")
        self._lib_btn_freq = Gtk.ToggleButton(label="Most used")
        self._lib_btn_freq.set_group(self._lib_btn_svc)
        self._lib_btn_svc.set_active(True)
        mode_box.append(self._lib_btn_svc); mode_box.append(self._lib_btn_freq)
        top.append(mode_box)

        def on_mode_toggle(btn):
            if not btn.get_active(): return
            self._lib_mode = "freq" if btn is self._lib_btn_freq else "services"
            self._lib_rebuild(se.get_text().strip())
        self._lib_btn_svc.connect("toggled", on_mode_toggle)
        self._lib_btn_freq.connect("toggled", on_mode_toggle)

        box.append(top); box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        self._lib_insert_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._lib_insert_bar.set_margin_start(12); self._lib_insert_bar.set_margin_end(12)
        self._lib_insert_bar.set_margin_top(6); self._lib_insert_bar.set_margin_bottom(6)
        self._lib_insert_bar.set_visible(False)
        self._lib_insert_lbl = Gtk.Label(); self._lib_insert_lbl.set_hexpand(True)
        self._lib_insert_lbl.set_xalign(0); self._lib_insert_lbl.add_css_class("caption")
        self._lib_insert_bar.append(self._lib_insert_lbl)
        ins_btn = Gtk.Button(label="Insert into selected element"); ins_btn.add_css_class("suggested-action")
        ins_btn.connect("clicked", self._on_lib_insert); self._lib_insert_bar.append(ins_btn)
        box.append(self._lib_insert_bar)

        scroll = Gtk.ScrolledWindow(); scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._lib_list = Gtk.ListBox(); self._lib_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._lib_list.add_css_class("boxed-list")
        self._lib_list.set_margin_start(12); self._lib_list.set_margin_end(12)
        self._lib_list.set_margin_top(8); self._lib_list.set_margin_bottom(12)
        self._lib_list.connect("row-selected", self._on_lib_row_selected)
        scroll.set_child(self._lib_list); box.append(scroll)
        return box

    def _lib_rebuild(self, query: str = ""):
        self._lib_rebuilding = True
        self._lib_search = query
        while self._lib_list.get_first_child(): self._lib_list.remove(self._lib_list.get_first_child())
        self._lib_selected = None; self._lib_insert_bar.set_visible(False)
        try:
            from rubric_package.db import (element_search, element_services,
                                            element_for_service, element_name_stats)
        except ImportError:
            self._lib_list.append(self._status_row("Database not available"))
            self._lib_rebuilding = False; return

        if self._lib_mode == "freq":
            rows = element_name_stats(query, limit=120)
            if not rows:
                self._lib_list.append(self._status_row("No elements indexed yet"))
            else:
                for r in rows: self._lib_list.append(self._lib_freq_row(r))
            self._lib_rebuilding = False; return

        if query:
            rows = element_search(query)
            if not rows:
                self._lib_list.append(self._status_row("No matches found"))
                self._lib_rebuilding = False; return
            for r in rows: self._lib_list.append(self._lib_elem_row(r))
        else:
            services = element_services()
            if not services:
                self._lib_list.append(self._status_row(
                    "No services indexed yet — save a service to add it to the library"))
                self._lib_rebuilding = False; return
            for svc in services:
                self._lib_list.append(self._lib_svc_row(svc))
                if svc["service_path"] in self._lib_expanded:
                    for elem in element_for_service(svc["service_path"]):
                        self._lib_list.append(self._lib_elem_row(elem, indented=True))
        self._lib_rebuilding = False

    def _lib_svc_row(self, svc: dict) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow(); row._is_service = True; row._service_path = svc["service_path"]
        expanded = svc["service_path"] in self._lib_expanded
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_margin_start(12); box.set_margin_end(8); box.set_margin_top(8); box.set_margin_bottom(8)
        box.append(Gtk.Label(label="▼" if expanded else "▶", css_classes=["caption", "dim-label"]))
        title_lbl = Gtk.Label(label=svc.get("service_title") or Path(svc["service_path"]).stem)
        title_lbl.set_hexpand(True); title_lbl.set_xalign(0); box.append(title_lbl)
        if svc.get("service_date"):
            box.append(Gtk.Label(label=svc["service_date"], css_classes=["caption", "dim-label"]))
        row.set_child(box); return row

    def _lib_elem_row(self, r: dict, indented: bool = False) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow(); row._element = r; row._is_service = False
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_margin_start(32 if indented else 12); box.set_margin_end(12)
        box.set_margin_top(6); box.set_margin_bottom(6)
        name_lbl = Gtk.Label(label=r.get("name", "(unnamed)"))
        name_lbl.set_xalign(0); box.append(name_lbl)
        note = (r.get("note") or "").strip()
        if note:
            preview = note[:120].replace("\n", " ") + ("…" if len(note) > 120 else "")
            note_lbl = Gtk.Label(label=preview)
            note_lbl.set_xalign(0); note_lbl.add_css_class("caption"); note_lbl.add_css_class("dim-label")
            note_lbl.set_wrap(True); note_lbl.set_lines(2); note_lbl.set_ellipsize(Pango.EllipsizeMode.END)
            box.append(note_lbl)
        if not indented and r.get("service_title"):
            svc_lbl = Gtk.Label(label=f'{r["service_title"]}  ·  {r.get("service_date","") or ""}')
            svc_lbl.set_xalign(0); svc_lbl.add_css_class("caption"); svc_lbl.add_css_class("dim-label")
            box.append(svc_lbl)
        row.set_child(box); return row

    def _lib_freq_row(self, r: dict) -> Gtk.ListBoxRow:
        """Row for the 'Most used' frequency view."""
        row = Gtk.ListBoxRow(); row._is_service = False; row._element = {}
        row.set_activatable(False)
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_margin_start(12); box.set_margin_end(12)
        box.set_margin_top(8); box.set_margin_bottom(8)
        name_lbl = Gtk.Label(label=r.get("name", "(unnamed)"))
        name_lbl.set_hexpand(True); name_lbl.set_xalign(0)
        box.append(name_lbl)
        use_count = r.get("use_count", 0)
        last_used = r.get("last_used", "") or ""
        badge_text = f"{use_count}×"
        badge = Gtk.Label(label=badge_text)
        badge.add_css_class("caption"); badge.add_css_class("dim-label")
        badge.set_valign(Gtk.Align.CENTER)
        box.append(badge)
        if last_used:
            try:
                from datetime import date as _date, timedelta
                ld = _date.fromisoformat(last_used)
                weeks = ((_date.today() - ld).days) // 7
                when = f"{weeks}w ago" if weeks > 0 else "this week"
            except Exception:
                when = last_used
            when_lbl = Gtk.Label(label=when)
            when_lbl.add_css_class("caption"); when_lbl.add_css_class("dim-label")
            when_lbl.set_valign(Gtk.Align.CENTER)
            box.append(when_lbl)
        row.set_child(box); return row

    def _on_lib_row_selected(self, _lb, row):
        if self._lib_rebuilding: return
        if row is None: self._lib_selected = None; self._lib_insert_bar.set_visible(False); return
        if getattr(row, "_is_service", False):
            path = row._service_path
            if path in self._lib_expanded: self._lib_expanded.discard(path)
            else: self._lib_expanded.add(path)
            self._lib_rebuild(self._lib_search); return
        elem = getattr(row, "_element", None)
        if not elem or not (elem.get("note") or elem.get("bulletin_note")):
            self._lib_insert_bar.set_visible(False); return
        self._lib_selected = elem
        self._lib_insert_lbl.set_label(f'"{elem.get("name","element")}" · {len(elem.get("note",""))} chars')
        self._lib_insert_bar.set_visible(True)

    def _on_lib_insert(self, _):
        if not self._lib_selected: return
        self._do_insert(self._lib_selected.get("note") or self._lib_selected.get("bulletin_note") or "",
                        self._lib_selected.get("name", "element"))

    # ── Archive tab ───────────────────────────────────────────────────────────

    def _build_archive_tab(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        se = Gtk.SearchEntry(); se.set_placeholder_text("Search past services…")
        se.set_margin_start(12); se.set_margin_end(12); se.set_margin_top(10); se.set_margin_bottom(6)
        se.connect("search-changed", lambda e: self._arch_rebuild(e.get_text().strip().lower()))
        box.append(se); box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        scroll = Gtk.ScrolledWindow(); scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._arch_list = Gtk.ListBox(); self._arch_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self._arch_list.add_css_class("boxed-list")
        self._arch_list.set_margin_start(12); self._arch_list.set_margin_end(12)
        self._arch_list.set_margin_top(8); self._arch_list.set_margin_bottom(12)
        scroll.set_child(self._arch_list); box.append(scroll)
        return box

    def _arch_rebuild(self, query: str):
        self._arch_search = query
        while self._arch_list.get_first_child(): self._arch_list.remove(self._arch_list.get_first_child())
        try:
            from rubric_package.db import element_services, element_for_service
        except ImportError:
            self._arch_list.append(self._status_row("Database not available")); return

        services = element_services(limit=500)
        if not services:
            self._arch_list.append(self._status_row(
                "No services in library yet — save a service to add it here")); return

        if query:
            filtered = []
            for svc in services:
                title = (svc.get("service_title") or "").lower()
                date  = (svc.get("service_date") or "").lower()
                if query in title or query in date:
                    filtered.append(svc)
                else:
                    elems = element_for_service(svc["service_path"])
                    if any(query in (e.get("name","")).lower() or query in (e.get("note","")).lower()
                           for e in elems):
                        filtered.append(svc)
            services = filtered
            if not services: self._arch_list.append(self._status_row("No matches found")); return

        for svc in services:
            self._arch_list.append(self._arch_svc_row(svc))
            if svc["service_path"] in self._arch_expanded:
                try: elems = element_for_service(svc["service_path"])
                except Exception: elems = []
                cur_section = ""
                for elem in elems:
                    if elem.get("section") and elem["section"] != cur_section:
                        cur_section = elem["section"]
                        self._arch_list.append(self._arch_section_label(cur_section))
                    self._arch_list.append(self._arch_elem_row(elem))

    def _arch_svc_row(self, svc: dict) -> Gtk.ListBoxRow:
        path = svc["service_path"]; expanded = path in self._arch_expanded
        row = Gtk.ListBoxRow(); row._is_service = True; row._svc = svc
        row.set_activatable(True)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header.set_margin_start(12); header.set_margin_end(8)
        header.set_margin_top(10); header.set_margin_bottom(10)
        header.append(Gtk.Label(label="▼" if expanded else "▶", css_classes=["caption", "dim-label"]))
        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1); info.set_hexpand(True)
        title_lbl = Gtk.Label(label=svc.get("service_title") or Path(path).stem)
        title_lbl.set_xalign(0); title_lbl.add_css_class("heading"); title_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        info.append(title_lbl)
        date_lbl = Gtk.Label(label=svc.get("service_date") or "No date")
        date_lbl.set_xalign(0); date_lbl.add_css_class("caption"); date_lbl.add_css_class("dim-label")
        info.append(date_lbl); header.append(info)
        open_btn = Gtk.Button(label="Open in editor"); open_btn.add_css_class("flat")
        open_btn.set_valign(Gtk.Align.CENTER)
        open_btn.connect("clicked", lambda _b, p=path: self._open_service(p))
        header.append(open_btn); outer.append(header); row.set_child(outer)
        def on_activate(_r, p=path):
            if p in self._arch_expanded: self._arch_expanded.discard(p)
            else: self._arch_expanded.add(p)
            GLib.idle_add(self._arch_rebuild, self._arch_search)
        row.connect("activate", on_activate)
        return row

    def _arch_section_label(self, section: str) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow(); row.set_activatable(False)
        lbl = Gtk.Label(label=section); lbl.set_xalign(0)
        lbl.add_css_class("caption"); lbl.add_css_class("dim-label"); lbl.add_css_class("heading")
        lbl.set_margin_start(28); lbl.set_margin_end(12)
        lbl.set_margin_top(8); lbl.set_margin_bottom(2)
        row.set_child(lbl); return row

    def _arch_elem_row(self, elem: dict) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow(); row.set_activatable(False); row._element = elem
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_start(28); box.set_margin_end(12)
        box.set_margin_top(6); box.set_margin_bottom(6)
        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        name_lbl = Gtk.Label(label=elem.get("name",""))
        name_lbl.set_xalign(0); name_lbl.add_css_class("body"); name_lbl.set_hexpand(True)
        top.append(name_lbl)
        if elem.get("leader"):
            top.append(Gtk.Label(label=elem["leader"], css_classes=["caption", "dim-label"]))
        note_raw = (elem.get("bulletin_note") or elem.get("note") or "").strip()
        if note_raw:
            ins_btn = Gtk.Button(label="Insert"); ins_btn.add_css_class("flat")
            ins_btn.set_valign(Gtk.Align.CENTER)
            ins_btn.connect("clicked", lambda _b, e=elem: self._do_insert(
                e.get("note") or e.get("bulletin_note") or "", e.get("name","element")))
            top.append(ins_btn)
        box.append(top)
        if note_raw:
            clean = self._strip_latex(note_raw)
            if clean:
                note_lbl = Gtk.Label(label=clean); note_lbl.set_xalign(0)
                note_lbl.set_wrap(True); note_lbl.add_css_class("caption"); note_lbl.set_selectable(True)
                box.append(note_lbl)
        row.set_child(box); return row

    # ── Shared helpers ────────────────────────────────────────────────────────

    def _load_all(self, *_):
        self._init_planner_folder(); self._load_planner()
        self._lib_rebuild(""); self._arch_rebuild("")
        return False

    def _open_service(self, path: str):
        self._main._confirm_discard(lambda p=path: self._main._load_file(p))

    def _do_insert(self, note: str, name: str):
        win = self._main
        idx = win._selected_global_idx
        if idx < 0 or idx >= len(win.service_entries):
            self._show_toast("Select an element in the service order first"); return
        entry = win.service_entries[idx]
        if not isinstance(entry, ServiceItem):
            self._show_toast("Select an element (not a section header)"); return
        entry.content_typst = note
        win._content_widget.set_content(note)
        win._mark_modified()
        self._show_toast(f'Inserted into "{entry.name}"')

    def _strip_latex(self, text: str) -> str:
        return strip_typst_plain(text)

    def _status_row(self, msg: str) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow(); row.set_activatable(False)
        lbl = Gtk.Label(label=msg); lbl.add_css_class("dim-label")
        lbl.set_margin_top(20); lbl.set_margin_bottom(20)
        lbl.set_margin_start(12); lbl.set_margin_end(12)
        lbl.set_wrap(True); row.set_child(lbl); return row

    def _show_toast(self, msg: str):
        toast = Adw.Toast.new(msg); toast.set_timeout(3)
        try: self._main._toast_overlay.add_toast(toast)
        except Exception: pass


# ── Help Window ───────────────────────────────────────────────────────────────

class HelpWindow(Adw.Window):
    """Tabbed help window — Help, FAQ, What's New, About."""

    _TAB_IDX = {"help": 0, "faq": 1, "changelog": 2, "about": 3}

    def __init__(self, main_window, start_tab: str = "help", **kw):
        super().__init__(title="Help — Rubric", default_width=720, default_height=620, **kw)
        self._main = main_window
        self.set_modal(False)

        tv = Adw.ToolbarView()
        hdr = Adw.HeaderBar()
        tv.add_top_bar(hdr)

        self._nb = Gtk.Notebook()
        self._nb.set_show_border(False); self._nb.set_vexpand(True)

        self._nb.append_page(self._doc_page(self._find_doc("HELP.md")),      Gtk.Label(label="Help"))
        self._nb.append_page(self._doc_page(self._find_doc("FAQ.md")),       Gtk.Label(label="FAQ"))
        self._nb.append_page(self._doc_page(self._find_doc("CHANGELOG.md")), Gtk.Label(label="What's New"))
        self._nb.append_page(self._about_page(),                        Gtk.Label(label="About"))
        self._nb.set_current_page(self._TAB_IDX.get(start_tab, 0))

        tv.set_content(self._nb)
        self.set_content(tv)

    def switch_tab(self, name: str):
        self._nb.set_current_page(self._TAB_IDX.get(name, 0))

    @staticmethod
    def _find_doc(name: str) -> Path | None:
        p = Path(__file__).parent / name
        if p.exists():
            return p
        try:
            import rubric_package as _rp
            p2 = Path(_rp.__file__).parent / "data" / name
            if p2.exists():
                return p2
        except ImportError:
            pass
        return None

    def _doc_page(self, path: Path | None) -> Gtk.Widget:
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        tv = Gtk.TextView(); tv.set_editable(False); tv.set_cursor_visible(False)
        tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        tv.set_top_margin(16); tv.set_bottom_margin(16)
        tv.set_left_margin(20); tv.set_right_margin(20)
        buf = tv.get_buffer()
        buf.create_tag("h1", weight=700, scale=1.4, pixels_above_lines=12, pixels_below_lines=4)
        buf.create_tag("h2", weight=700, scale=1.15, pixels_above_lines=10, pixels_below_lines=2)
        buf.create_tag("h3", weight=700, scale=1.0,  pixels_above_lines=8,  pixels_below_lines=2)
        buf.create_tag("bold",   weight=700)
        buf.create_tag("code",   family="monospace", background="#f0f0f0")
        buf.create_tag("hr",     strikethrough=True, foreground="#888888")
        buf.create_tag("bullet", left_margin=24)
        if path is None or not path.exists():
            buf.set_text("Documentation not found.", -1)
            scroll.set_child(tv); return scroll
        it = buf.get_end_iter(); in_code = False
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.rstrip()
            if line.startswith("```"):
                in_code = not in_code; buf.insert(it, "\n"); continue
            if in_code:
                buf.insert_with_tags_by_name(it, line + "\n", "code"); continue
            if re.match(r'^---+$', line):
                buf.insert_with_tags_by_name(it, "─" * 40 + "\n", "hr"); continue
            m = re.match(r'^(#{1,3})\s+(.*)', line)
            if m:
                buf.insert_with_tags_by_name(it, m.group(2) + "\n", ["h1","h2","h3"][min(len(m.group(1))-1,2)]); continue
            m = re.match(r'^[-*]\s+(.*)', line)
            if m:
                buf.insert_with_tags_by_name(it, "  • " + m.group(1) + "\n", "bullet"); continue
            if re.match(r'^\|[-| :]+\|$', line): continue
            if line.startswith("|"):
                buf.insert_with_tags_by_name(it, line + "\n", "code"); continue
            if not line: buf.insert(it, "\n"); continue
            for part in re.split(r'(\*\*[^*]+\*\*|`[^`]+`)', line):
                if part.startswith("**") and part.endswith("**"):
                    buf.insert_with_tags_by_name(it, part[2:-2], "bold")
                elif part.startswith("`") and part.endswith("`"):
                    buf.insert_with_tags_by_name(it, part[1:-1], "code")
                else:
                    buf.insert(it, part)
            buf.insert(it, "\n")
        scroll.set_child(tv)
        return scroll

    def _about_page(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_top(40); box.set_margin_bottom(40)
        box.set_margin_start(40); box.set_margin_end(40)
        box.set_valign(Gtk.Align.CENTER)
        icon = Gtk.Image(icon_name="io.github.calstfrancis.rubric"); icon.set_pixel_size(64)
        box.append(icon)
        box.append(Gtk.Label(label="Rubric", css_classes=["title-1"]))
        ver = APP_VERSION
        box.append(Gtk.Label(label=f"Version {ver}", css_classes=["dim-label"]))
        box.append(Gtk.Label(label="Worship service planning for United Church of Canada ministry",
                             css_classes=["body"]))
        box.append(Gtk.Label(label="© Cal St Francis · GPL-3.0",
                             css_classes=["caption", "dim-label"]))
        gh_btn = Gtk.Button(label="GitHub — calstfrancis/rubric")
        gh_btn.add_css_class("flat"); gh_btn.set_halign(Gtk.Align.CENTER)
        gh_btn.connect("clicked", lambda _: Gtk.show_uri(self, "https://github.com/calstfrancis/rubric", 0))
        box.append(gh_btn)
        scroll = Gtk.ScrolledWindow(); scroll.set_vexpand(True)
        scroll.set_child(box); return scroll


# ── Service Planner ───────────────────────────────────────────────────────────

class PlannerWindow(Adw.Window):
    def __init__(self, folder: Path, main_window, **kw):
        super().__init__(**kw)
        self._folder = folder
        self._main = main_window
        self.set_title("Service Planner")
        self.set_default_size(920, 640)
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

        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_position(320)

        # Left: service list
        self._list = Gtk.ListBox()
        self._list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._list.add_css_class("boxed-list")
        self._list.set_margin_start(12); self._list.set_margin_end(12)
        self._list.set_margin_top(12); self._list.set_margin_bottom(12)
        self._list.connect("row-selected", self._on_row_selected)
        left_scroll = Gtk.ScrolledWindow(); left_scroll.set_vexpand(True)
        left_scroll.set_size_request(260, -1)
        left_scroll.set_child(self._list)
        paned.set_start_child(left_scroll)
        paned.set_shrink_start_child(False)

        # Right: detail panel
        self._detail_scroll = Gtk.ScrolledWindow(); self._detail_scroll.set_vexpand(True)
        self._detail_scroll.set_size_request(400, -1)
        self._detail_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._detail_box.set_vexpand(True)
        self._detail_scroll.set_child(self._detail_box)
        paned.set_end_child(self._detail_scroll)
        paned.set_shrink_end_child(False)

        self._toast_overlay = Adw.ToastOverlay()
        self._toast_overlay.set_child(paned)
        tv.set_content(self._toast_overlay)
        self.set_content(tv)
        self._show_detail_placeholder()
        self._load()

    def _show_toast(self, msg: str, timeout: int = 3):
        t = Adw.Toast.new(msg); t.set_timeout(timeout)
        self._toast_overlay.add_toast(t)

    def _collect_services(self):
        """Return list of (date, title, item_count, path) from folder."""
        from datetime import date as _date
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
                try: mtime = p.stat().st_mtime
                except OSError: continue
                cached_mtime = service_index_get_mtime(path_str) if _db_index else None
                if _db_index and cached_mtime is not None and abs(cached_mtime - mtime) < 0.01:
                    continue
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

        if _db_index and on_disk:
            service_index_prune(on_disk)
            for row in service_index_all():
                if row["path"] not in on_disk: continue
                p = Path(row["path"]); date_str = row["date"]
                try: svc_date = _date.fromisoformat(date_str) if date_str else None
                except ValueError: svc_date = None
                services.append((svc_date, row["title"] or p.stem, row["item_count"], p))
        elif not _db_index:
            try:
                for p in self._folder.glob("*.liturgy"):
                    try:
                        d = json.loads(p.read_text(encoding="utf-8"))
                        title = d.get("title", "") or p.stem
                        date_str = d.get("date", "")
                        item_count = len([i for i in d.get("items", []) if i.get("type") != "divider"])
                        try: svc_date = _date.fromisoformat(date_str) if date_str else None
                        except ValueError: svc_date = None
                        services.append((svc_date, title, item_count, p))
                    except Exception: pass
            except Exception: pass
        return services

    def _load(self):
        while self._list.get_first_child():
            self._list.remove(self._list.get_first_child())

        from datetime import date as _date, timedelta as _td
        today = _date.today()
        # Next Sunday
        days_to_sun = (6 - today.weekday()) % 7 or 7
        next_sun = today + _td(days=days_to_sun)

        services = self._collect_services()
        # Build date → (title, count, path) lookup
        by_date: dict[_date, tuple] = {}
        for svc_date, title, count, path in services:
            if svc_date: by_date[svc_date] = (title, count, path)

        def _add_sep(label):
            lbl = Gtk.Label(label=label)
            lbl.add_css_class("heading"); lbl.add_css_class("dim-label")
            lbl.set_xalign(0); lbl.set_margin_start(4)
            lbl.set_margin_top(10); lbl.set_margin_bottom(2)
            row = Gtk.ListBoxRow(); row.set_activatable(False)
            row.set_child(lbl); self._list.append(row)

        def _add_row(svc_date, title, subtitle, path, planned, colour_hex="#15803D"):
            row = Adw.ActionRow(title=title, subtitle=subtitle)
            row.set_activatable(True)
            # Liturgical season colour dot
            dot = Gtk.Label()
            dot.set_markup(f'<span color="{colour_hex}">●</span>')
            dot.set_valign(Gtk.Align.CENTER)
            dot.set_margin_end(4)
            row.add_prefix(dot)
            icon = Gtk.Image.new_from_icon_name(
                "emblem-ok-symbolic" if planned else "list-add-symbolic")
            icon.set_pixel_size(18)
            icon.add_css_class("success" if planned else "dim-label")
            row.add_prefix(icon)
            row._svc_date = svc_date
            row._svc_path = path
            self._list.append(row)

        # Upcoming Sundays — next 8 weeks
        _add_sep("Upcoming Sundays")
        for w in range(8):
            sun = next_sun + _td(weeks=w)
            try:
                info = get_liturgical_info(sun)
                week_lbl = info.get("week", sun.strftime("%-d %B %Y"))
                colour_hex = info.get("colour_hex", "#15803D")
            except Exception:
                week_lbl = sun.strftime("%-d %B %Y")
                colour_hex = "#15803D"
            if sun in by_date:
                title, count, path = by_date[sun]
                sub = f"{sun.strftime('%-d %b %Y')}  ·  {count} elements"
                _add_row(sun, title, sub, path, planned=True, colour_hex=colour_hex)
            else:
                _add_row(sun, sun.strftime("%-d %B %Y"), week_lbl, None,
                         planned=False, colour_hex=colour_hex)

        # Past services (files only)
        past = sorted([(d, t, c, p) for d, t, c, p in services
                       if d and d < today], key=lambda x: x[0], reverse=True)
        undated = [(d, t, c, p) for d, t, c, p in services if not d]
        if past or undated:
            _add_sep("Past services")
            for svc_date, title, count, path in past[:20]:
                sub = f"{svc_date.strftime('%-d %b %Y')}  ·  {count} elements"
                try:
                    past_colour = get_liturgical_info(svc_date).get("colour_hex", "#15803D")
                except Exception:
                    past_colour = "#15803D"
                _add_row(svc_date, title, sub, path, planned=True, colour_hex=past_colour)
            for _, title, count, path in undated:
                _add_row(None, title, f"No date  ·  {count} elements", path, planned=True)

    def _show_detail_placeholder(self):
        while self._detail_box.get_first_child():
            self._detail_box.remove(self._detail_box.get_first_child())
        lbl = Gtk.Label(label="Select a Sunday on the left to see its details")
        lbl.add_css_class("dim-label"); lbl.set_vexpand(True); lbl.set_valign(Gtk.Align.CENTER)
        self._detail_box.append(lbl)

    def _on_row_selected(self, _lb, row):
        if row is None or not hasattr(row, "_svc_date"):
            self._show_detail_placeholder(); return
        self._show_detail(getattr(row, "_svc_date", None), getattr(row, "_svc_path", None))

    def _show_detail(self, svc_date, path):
        while self._detail_box.get_first_child():
            self._detail_box.remove(self._detail_box.get_first_child())

        from datetime import date as _date
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_start(20); box.set_margin_end(20)
        box.set_margin_top(16); box.set_margin_bottom(16)
        box.set_vexpand(True)

        # Liturgical info
        if svc_date:
            try:
                info = get_liturgical_info(svc_date)
                colour_hex = info.get("colour_hex", "#15803D")
                week = info.get("week", "")
                colour_name = info.get("colour", "")
                ot = info.get("ot", "—"); psalm = info.get("psalm", "—")
                epistle = info.get("epistle", "—"); gospel = info.get("gospel", "—")
            except Exception:
                info = {}; colour_hex = "#15803D"; week = ""; colour_name = ""
                ot = psalm = epistle = gospel = "—"

            date_lbl = Gtk.Label()
            date_lbl.set_markup(
                f'<span color="{colour_hex}">●</span>  '
                f'<b>{svc_date.strftime("%-d %B %Y")}</b>')
            date_lbl.add_css_class("title-2"); date_lbl.set_xalign(0)
            box.append(date_lbl)

            if week:
                meta_lbl = Gtk.Label(label=f"{week}" + (f"  ·  {colour_name}" if colour_name else ""))
                meta_lbl.add_css_class("dim-label"); meta_lbl.set_xalign(0)
                box.append(meta_lbl)

            # Readings grid
            rd_grp = Adw.PreferencesGroup(title="RCL Readings")
            for label, val in [("OT", ot), ("Psalm", psalm), ("Epistle", epistle), ("Gospel", gospel)]:
                if val and val != "—":
                    r = Adw.ActionRow(title=label, subtitle=val)
                    r.set_activatable(False); rd_grp.add(r)
            box.append(rd_grp)
        else:
            date_lbl = Gtk.Label(label="No date")
            date_lbl.add_css_class("title-2"); date_lbl.set_xalign(0)
            box.append(date_lbl)

        box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # Service contents or create button
        if path and Path(path).exists():
            try:
                d = json.loads(Path(path).read_text(encoding="utf-8"))
                items = [i for i in d.get("items", []) if i.get("type") != "divider"]
                svc_title = d.get("title", Path(path).stem)

                title_lbl = Gtk.Label(label=svc_title)
                title_lbl.add_css_class("heading"); title_lbl.set_xalign(0)
                box.append(title_lbl)

                items_grp = Adw.PreferencesGroup()
                for it in items[:24]:
                    note = (it.get("bulletin_note") or it.get("note") or "").strip()
                    r = Adw.ActionRow(title=GLib.markup_escape_text(it.get("name", "")),
                                      subtitle=GLib.markup_escape_text(note[:60]) if note else "")
                    r.set_activatable(False); items_grp.add(r)
                if len(items) > 24:
                    extra = Adw.ActionRow(title=f"… and {len(items)-24} more elements")
                    extra.set_activatable(False); items_grp.add(extra)
                box.append(items_grp)

                open_btn = Gtk.Button(label="Open in editor")
                open_btn.add_css_class("suggested-action")
                open_btn.connect("clicked", lambda _, p=path: (self._open(Path(p)), self.close()))
                box.append(open_btn)

                # ── After-service notes (attendance + debrief) ────────────────
                box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL,
                                         margin_top=8, margin_bottom=4))
                after_grp = Adw.PreferencesGroup(title="After service",
                    description="Filled in after Sunday — saved directly to this file.")
                box.append(after_grp)

                att_row = Adw.ActionRow(title="Attendance")
                att_adj = Gtk.Adjustment(
                    value=d.get("attendance", 0), lower=0, upper=9999, step_increment=1)
                att_spin = Gtk.SpinButton(adjustment=att_adj, numeric=True)
                att_spin.set_width_chars(5); att_spin.set_valign(Gtk.Align.CENTER)
                att_row.add_suffix(att_spin); after_grp.add(att_row)

                debrief_lbl = Gtk.Label(label="Notes")
                debrief_lbl.add_css_class("heading"); debrief_lbl.set_xalign(0)
                debrief_lbl.set_margin_start(4); debrief_lbl.set_margin_top(6)
                after_grp.add(debrief_lbl)

                deb_scroll = Gtk.ScrolledWindow()
                deb_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
                deb_scroll.set_min_content_height(72)
                deb_tv = Gtk.TextView(); deb_tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
                deb_tv.add_css_class("card")
                deb_tv.set_top_margin(6); deb_tv.set_bottom_margin(6)
                deb_tv.set_left_margin(8); deb_tv.set_right_margin(8)
                deb_tv.get_buffer().set_text(d.get("debrief", ""), -1)
                deb_scroll.set_child(deb_tv)
                after_grp.add(deb_scroll)

                def _save_after_notes(_btn, p=path, spin=att_spin, tv=deb_tv):
                    try:
                        data_patch = json.loads(Path(p).read_text(encoding="utf-8"))
                        data_patch["attendance"] = int(spin.get_value())
                        buf = tv.get_buffer(); s, e = buf.get_bounds()
                        data_patch["debrief"] = buf.get_text(s, e, False).strip()
                        Path(p).write_text(
                            json.dumps(data_patch, indent=2, ensure_ascii=False),
                            encoding="utf-8")
                        # Sync to main window if this file is open there
                        mw = self._main
                        if mw.current_file and Path(mw.current_file) == Path(p):
                            mw.service_attendance = data_patch["attendance"]
                            mw.service_debrief    = data_patch["debrief"]
                        self._show_toast("Notes saved")
                    except Exception as ex:
                        self._show_toast(f"Save failed: {ex}")

                save_btn = Gtk.Button(label="Save notes")
                save_btn.add_css_class("flat"); save_btn.set_halign(Gtk.Align.END)
                save_btn.connect("clicked", _save_after_notes)
                after_grp.add(save_btn)

            except Exception as e:
                box.append(Gtk.Label(label=f"Error reading file: {e}"))
        else:
            no_lbl = Gtk.Label(label="No service planned for this Sunday yet.")
            no_lbl.add_css_class("dim-label"); no_lbl.set_xalign(0)
            box.append(no_lbl)

            if svc_date:
                create_btn = Gtk.Button(label="Create service for this Sunday")
                create_btn.add_css_class("suggested-action")
                def _create(_b, d=svc_date):
                    self._main._confirm_discard(lambda: self._create_for_date(d))
                create_btn.connect("clicked", _create)
                box.append(create_btn)

        self._detail_box.append(box)

    def _create_for_date(self, svc_date):
        try: info = get_liturgical_info(svc_date)
        except Exception: info = {}
        self._main._seed_lectionary_service(svc_date, info)
        self.close()

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
            note_lbl.set_wrap(True); note_lbl.set_lines(2); note_lbl.set_ellipsize(Pango.EllipsizeMode.END)
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
        entry.content_typst = note
        win._content_widget.set_content(note)
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
        return strip_typst_plain(text)

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
        title_lbl.set_ellipsize(Pango.EllipsizeMode.END); info.append(title_lbl)
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
        entry.content_typst = note
        win._content_widget.set_content(note)
        win._mark_modified()
        self._show_toast(f'Inserted into "{entry.name}"')

    def _show_toast(self, msg: str):
        toast = Adw.Toast.new(msg); toast.set_timeout(3)
        try:
            self._main._toast_overlay.add_toast(toast)
        except Exception:
            pass


# ── Observance Wikipedia Window ───────────────────────────────────────────────

class ObservanceWikiWindow(Adw.Window):
    """Shows the Wikipedia article for a liturgical observance."""

    _CSS = b"""
body { font-family: sans-serif; font-size: 15px; line-height: 1.7;
       max-width: 680px; margin: 2em auto; padding: 0 1.5em;
       color: #1a1a1a; background: #fff; }
h1 { font-size: 1.6em; margin-bottom: 0.2em; }
h2 { font-size: 1.2em; margin-top: 1.4em; border-bottom: 1px solid #e0e0e0; padding-bottom: 0.2em; }
h3 { font-size: 1.05em; }
p  { margin: 0.7em 0; }
a  { color: #1a6bb5; }
figure, .mw-editsection, .mw-indicators, .noprint,
.navbox, .infobox, .reflist, .references, sup.reference,
.mw-references-wrap { display: none !important; }
img { max-width: 100%; height: auto; border-radius: 4px; }
"""

    def __init__(self, name: str, **kw):
        super().__init__(title=name, default_width=740, default_height=680, **kw)
        self.set_modal(False)

        tv = Adw.ToolbarView()
        hdr = Adw.HeaderBar()
        hdr.set_title_widget(Adw.WindowTitle(title=name, subtitle="Wikipedia"))
        tv.add_top_bar(hdr)

        if _WebKit is not None:
            self._wv = _WebKit.WebView()
            self._wv.set_vexpand(True); self._wv.set_hexpand(True)
            # Inject CSS after page loads
            self._wv.connect("load-changed", self._on_load_changed)
            tv.set_content(self._wv)
            self._fetch_article(name)
        else:
            sp = Adw.StatusPage(title="WebKit not available",
                                description="Install python3-webkit2gtk to view Wikipedia articles.",
                                icon_name="web-browser-symbolic")
            open_btn = Gtk.Button(label="Open in browser")
            open_btn.add_css_class("suggested-action")
            import urllib.parse as _up
            clean_name = re.sub(r'\s+\([A-Za-z]{3,9}\s+\d{1,2}\)\s*$', '', name).strip()
            article = self._WIKI_TITLES.get(clean_name) or self._WIKI_TITLES.get(name)
            article_slug = article if article else _up.quote(clean_name.replace(" ", "_"))
            url = f"https://en.m.wikipedia.org/wiki/{article_slug}"
            open_btn.connect("clicked", lambda _: Gio.AppInfo.launch_default_for_uri(url, None))
            sp.set_child(open_btn)
            tv.set_content(sp)

        self.set_content(tv)

    # Mapping from observance display name to Wikipedia article title.
    # Names not listed here are cleaned and used directly.
    _WIKI_TITLES: dict[str, str] = {
        "Epiphany of the Lord": "Epiphany_(holiday)",
        "Presentation of Christ (Candlemas)": "Candlemas",
        "Transfiguration of the Lord (Aug 6)": "Transfiguration_of_Jesus",
        "Mary, Mother of Our Lord": "Mary,_mother_of_Jesus",
        "Birth of John the Baptist": "Nativity_of_John_the_Baptist",
        "Feast of Peter and Paul": "Feast_of_Saints_Peter_and_Paul",
        "St Michael and All Angels (Michaelmas)": "Michaelmas",
        "Holy Innocents": "Massacre_of_the_Innocents",
        "All Hallows' Eve": "Halloween",
        "St Francis of Assisi / Season of Creation ends": "Francis_of_Assisi",
        "Season of Creation begins": "Season_of_Creation",
        "Season of Creation": "Season_of_Creation",
        "Season of Creation ends": "Season_of_Creation",
        "World Day of Prayer for the Care of Creation": "World_Day_of_Prayer_for_the_Care_of_Creation",
        "Week of Prayer for Christian Unity begins": "Week_of_Prayer_for_Christian_Unity",
        "Week of Prayer for Christian Unity ends (St Paul)": "Week_of_Prayer_for_Christian_Unity",
        "Week of Prayer for Christian Unity": "Week_of_Prayer_for_Christian_Unity",
        "National Day for Truth and Reconciliation (Canada)": "National_Day_for_Truth_and_Reconciliation",
        "National Day of Awareness for Missing and Murdered Indigenous Women and Girls (Canada)": "National_Inquiry_into_Missing_and_Murdered_Indigenous_Women_and_Girls",
        "National Day of Remembrance (Montréal Massacre)": "École_Polytechnique_massacre",
        "International Day for the Elimination of Racial Discrimination": "International_Day_for_the_Elimination_of_Racial_Discrimination",
        "International Day for the Elimination of Violence Against Women": "International_Day_for_the_Elimination_of_Violence_against_Women",
        "International Day for the Eradication of Poverty": "International_Day_for_the_Eradication_of_Poverty",
        "International Day of Innocent Children Victims of Aggression": "International_Day_of_Innocent_Children_Victims_of_Aggression",
        "International Day of Persons with Disabilities": "International_Day_of_Persons_with_Disabilities",
        "International Day of Peace": "International_Day_of_Peace",
        "International Day of the World's Indigenous Peoples": "International_Day_of_the_World%27s_Indigenous_Peoples",
        "International Women's Day": "International_Women%27s_Day",
        "16 Days of Activism Against Gender-Based Violence": "16_Days_of_Activism_against_Gender-Based_Violence",
        "Transgender Day of Remembrance": "Transgender_Day_of_Remembrance",
        "Pride Month": "Pride_Month",
        "Indigenous Sunday (UCC)": "Indigenous_Sunday",
        "Earth Sunday": "Earth_Day",
        "Pride Sunday": "Pride_Sunday",
        "Creation Sunday": "Season_of_Creation",
        "Remembrance Sunday": "Remembrance_Sunday",
        "All Saints Sunday": "All_Saints%27_Day",
        "Canadian Thanksgiving": "Thanksgiving_(Canada)",
        "Martin Luther King Jr. Day": "Martin_Luther_King_Jr._Day",
        "World Day of Prayer": "World_Day_of_Prayer",
        "St Joseph": "Joseph,_father_of_Jesus",
        "Annunciation of the Lord": "Annunciation",
        "St Nicholas Day": "Saint_Nicholas_Day",
        "St Stephen / Boxing Day": "Boxing_Day",
        "St John the Apostle": "John_the_Apostle",
        "St Benedict of Nursia": "Benedict_of_Nursia",
        "St Luke": "Luke_the_Evangelist",
        "Saints Cyril and Methodius": "Saints_Cyril_and_Methodius",
        "St Vincent de Paul": "Vincent_de_Paul",
        "World Tourism Day / St Vincent de Paul": "Vincent_de_Paul",
        "New Year's Day": "New_Year%27s_Day",
        "Holy Name of Jesus": "Holy_Name_of_Jesus",
        "Reformation Day": "Reformation_Day",
        "Remembrance Day (Canada)": "Remembrance_Day",
        "World AIDS Day": "World_AIDS_Day",
        "World Food Day": "World_Food_Day",
        "World Environment Day": "World_Environment_Day",
        "World Refugee Day": "World_Refugee_Day",
        "World Animal Day": "World_Animal_Day",
        "Coming Out Day": "National_Coming_Out_Day",
        "Earth Day": "Earth_Day",
        "Christmas Day": "Christmas",
    }

    def _fetch_article(self, name: str):
        import threading, urllib.request, urllib.parse, urllib.error
        # Look up canonical article title, stripping proximity suffixes like " (Mon Jun 21)"
        clean = re.sub(r'\s+\([A-Za-z]{3,9}\s+\d{1,2}\)\s*$', '', name).strip()
        article = self._WIKI_TITLES.get(clean) or self._WIKI_TITLES.get(name)
        if article:
            encoded = article  # already URL-encoded in the dict where needed
        else:
            encoded = urllib.parse.quote(clean.replace(" ", "_"))
        url = f"https://en.wikipedia.org/api/rest_v1/page/html/{encoded}"

        def fetch():
            try:
                req = urllib.request.Request(url, headers={
                    "User-Agent": "Rubric/1.0 (liturgy planner; contact calstfrancis@gmail.com)",
                    "Accept": "text/html"
                })
                with urllib.request.urlopen(req, timeout=15) as r:
                    html = r.read().decode("utf-8")
                css_tag = f"<style>{self._CSS.decode()}</style>"
                # Inject CSS into <head>
                if "<head>" in html:
                    html = html.replace("<head>", f"<head>{css_tag}", 1)
                else:
                    html = css_tag + html
                GLib.idle_add(self._wv.load_html, html, f"https://en.wikipedia.org/wiki/{encoded}")
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    GLib.idle_add(self._wv.load_uri,
                                  f"https://en.m.wikipedia.org/wiki/Special:Search?search={urllib.parse.quote(clean)}")
                else:
                    GLib.idle_add(self._show_error, f"HTTP {e.code}")
            except Exception as ex:
                GLib.idle_add(self._show_error, str(ex))

        threading.Thread(target=fetch, daemon=True).start()

    def _on_load_changed(self, wv, event):
        if _WebKit and event == _WebKit.LoadEvent.FINISHED:
            # Hide mobile header/footer via JS
            js = ("var s=document.createElement('style');"
                  "s.textContent='.header-container,.mw-footer,.mw-mf-page-center>div:not(#content){display:none}';"
                  "document.head.appendChild(s);")
            try:
                wv.evaluate_javascript(js, -1, None, None, None, None, None)
            except Exception:
                try:
                    wv.run_javascript(js, None, None, None)
                except Exception:
                    pass

    def _show_error(self, msg: str):
        sp = Adw.StatusPage(title="Could not load article", description=msg,
                            icon_name="network-error-symbolic")
        tv = self.get_content()
        if tv:
            tv.set_content(sp)


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
        _ensure_gost_font()
        css = Gtk.CssProvider()
        css.load_from_data(b"""
/* Default (non-compact): give rows comfortable breathing room */
row.activatable { min-height: 52px; }
row.activatable > box { padding-top: 10px; padding-bottom: 10px; }
/* Compact mode: very tight rows */
.compact-mode row.activatable { min-height: 22px; }
.compact-mode row.activatable > box { padding-top: 1px; padding-bottom: 1px; }
.compact-mode row.activatable title { font-size: 0.8em; }
.compact-mode row.activatable subtitle { font-size: 0.7em; }
.compact-mode .order-list row.activatable { min-height: 20px; }
.compact-mode .order-list row.activatable title { font-size: 0.8em; margin-top: 0; margin-bottom: 0; }
/* Status bar: slim height */
.toolbar { min-height: 18px; padding-top: 0; padding-bottom: 0; }
.toolbar button.flat { min-height: 0; padding-top: 1px; padding-bottom: 1px; }
/* Status bar separator */
.rubric-statusbar-sep { opacity: 0.25; }
/* Selected service order row: left accent bar */
.order-list row.activatable:selected { border-left: 3px solid @accent_color; }
/* Observance chips in status bar */
.obs-chip { padding-left: 4px; padding-right: 4px; padding-top: 0; padding-bottom: 0; }
/* Reading chip: inserted into service */
button.success { color: @success_color; }
/* Suggestion strip flowbox children: no selection highlight */
flowboxchild { background: transparent; padding: 0; }
/* Suggestion pills: opaque accent colour, white text, no border */
.sugg-pill button {
  background: @accent_bg_color;
  color: @accent_fg_color;
  border: none;
  box-shadow: none;
}
.sugg-pill button:hover { background: mix(@accent_bg_color, black, 0.12); }
.sugg-pill button:first-child { border-right: none; border-radius: 9999px 0 0 9999px; }
.sugg-pill button:last-child { border-left: none; border-radius: 0 9999px 9999px 0; }
.sugg-pill button:only-child { border-radius: 9999px; }
/* Rubric note editor: reddish tint */
.rubric-note-editor { background: alpha(red, 0.04); color: @error_color; font-style: italic; }
/* Vertical section tab strip */
notebook > header.left { background: transparent; border-right: 1px solid alpha(@borders, 0.4); }
notebook > header.left tab { padding: 4px 2px; min-height: 0; }
notebook > header.left tab:checked { background: alpha(@accent_bg_color, 0.15); border-right: 2px solid @accent_color; }
/* Header bar buttons: square, not tall */
headerbar button { min-width: 32px; min-height: 32px; padding: 4px; }
headerbar button.suggested-action { min-width: 32px; min-height: 32px; padding: 4px; }
/* Drag handle: subtle at rest, visible on hover, grab cursor */
.order-list row .drag-handle { opacity: 0.18; transition: opacity 120ms; cursor: grab; }
.order-list row:hover .drag-handle { opacity: 0.6; }
/* Section divider pill */
.divider-pill { background: alpha(@accent_bg_color, 0.08); border-radius: 6px; padding: 2px 4px; }
/* Unsaved chip: pulse animation after 30s */
@keyframes rubric-unsaved-pulse {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.35; }
}
.unsaved-pulse { animation: rubric-unsaved-pulse 1.6s ease-in-out infinite; }
/* Preview pane: warm off-white page background */
.preview-pane { background-color: #fafaf8; }
/* Cover art thumbnail: rounded corners */
.cover-thumb { border-radius: 4px; }
""")
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        MainWindow(application=app).present()

def _ensure_gost_font():
    """Copy the bundled GOST Type B font to the user font dir and refresh fc cache."""
    import shutil
    import subprocess
    import threading
    font_src = Path(__file__).parent / "rubric_package" / "data" / "fonts" / "gosttypeb.ttf"
    if not font_src.exists():
        return
    font_dir = Path.home() / ".local" / "share" / "rubric" / "fonts"
    font_dst = font_dir / "gosttypeb.ttf"
    if not font_dst.exists():
        try:
            font_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(font_src, font_dst)
            def _cache():
                try:
                    subprocess.run(["fc-cache", "-f", str(font_dir)],
                                   capture_output=True, timeout=10)
                except Exception:
                    pass
            threading.Thread(target=_cache, daemon=True).start()
        except Exception:
            pass


def _ensure_desktop_integration():
    desktop = Path.home() / ".local/share/applications/rubric.desktop"
    if not desktop.exists():
        import threading
        def _run():
            try:
                import rubric_setup
                rubric_setup.main()
            except Exception:
                pass
        threading.Thread(target=_run, daemon=True).start()


def main():
    GLib.set_prgname("rubric")
    GLib.set_application_name("Rubric")
    _ensure_desktop_integration()
    sys.exit(LiturgyPlannerApp().run(sys.argv))

if __name__ == "__main__":
    main()
