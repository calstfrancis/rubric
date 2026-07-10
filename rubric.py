#!/usr/bin/env python3
"""
Rubric — GTK4 + libadwaita worship service order builder
Requires: sudo zypper install python3-gobject typelib-1_0-Adw-1 typelib-1_0-Gtk-4_0
"""

import sys, json, re, subprocess, shutil, threading, os
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib, GObject, Gdk, Pango

sys.path.insert(0, str(Path(__file__).parent))
from rcl_data import get_liturgical_info

# Import from refactored package
try:
    from rubric_package.models.config import (
        Config, MAX_UNDO, AUTOSAVE_SECS, CONFIG_PATH, AUTOSAVE_PATH, SECTIONS,
        config, get_palette, seed_all_dates as _seed_all_dates,
    )
    from rubric_package.models.service import ServiceItem, SectionDivider, entry_from_dict
    from rubric_package.utils.typst import (
        typst_escape, note_for_typst, linebreak_fix, escape_unmatched_brackets,
        passage_to_typst,
        strip_typst_for_html, strip_typst_plain, strip_leader_notes, TYPST_SHARED,
        format_typst_error,
    )
    from rubric_package.utils.colors import section_colour, hex_to_rgb, SECTION_COLORS
    from rubric_package.utils.helpers import (
        is_hymn_element, HYMN_KEYWORDS as _HYMN_KW, flatpak_git_prefix, git_credential_args,
    )
    from rubric_package import github_auth, secret_store
    from rubric_package.views import github_signin
    from rubric_package.views.element_content import ElementContentWidget
    from rubric_package.views.help_window import HelpWindow
    from rubric_package.views.preferences_window import PreferencesWindow
    from rubric_package.views.bulletin_prefs_window import BulletinPrefsWindow
    from rubric_package.views.bible_viewer import BibleViewer
    from rubric_package.views.services_window import ServicesWindow
    from rubric_package.views.dates_editor_window import DatesEditorWindow
    from rubric_package.views.observance_wiki_window import ObservanceWikiWindow
    from rubric_package.views.service_planning_notes_window import ServicePlanningNotesWindow
    from rubric_package.exporters.bulletin_exporter import BulletinExporter
    from rubric_package.preview.bulletin_preview import BulletinPreview
    from rubric_package.panels.preamble_panel import PreamblePanel
    from rubric_package.panels.hymn_lookup_panel import HymnLookupPanel
    from rubric_package.panels.order_panel import OrderPanel
    from rubric_package.panels.main_chrome import MainChrome
    from rubric_package.panels.palette_panel import PalettePanel
except ImportError as _pkg_err:
    print(f"Fatal: rubric_package not found — {_pkg_err}", file=sys.stderr)
    sys.exit(1)

# When running inside a flatpak sandbox, delegate git to the host system.
_GIT = flatpak_git_prefix()

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

APP_VERSION = "0.19.0-dev1"


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


# ── Main window ───────────────────────────────────────────────────────────────

class MainWindow(Adw.ApplicationWindow):
    def __init__(self, **kw):
        super().__init__(**kw)
        saved = config.get_window_size("main")
        if saved:
            width, height, maximized = saved
            self.set_default_size(width, height)
            if maximized:
                self.maximize()
        else:
            self.set_default_size(1000, 700)
            self.maximize()
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
        self.service_planning_notes: str = ""
        self.service_tags: list[str] = []
        self.service_series: str = ""
        self.service_pinned: bool = False

        _seed_all_dates()
        self._exporter = BulletinExporter(self)
        self._preview = BulletinPreview(self)
        self._preamble = PreamblePanel(self)
        self._hymn = HymnLookupPanel(self)
        self._order = OrderPanel(self)
        self._chrome = MainChrome(self)
        self._palette = PalettePanel(self)
        self._setup_actions(); self._chrome._build_ui(); self._apply_density(); self._update_title(); self._exporter._update_tex_btn()
        self.connect("destroy", self._on_main_destroy)
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
        if hasattr(self, "_simple_status_btn"):
            self._toggle_chip(self._simple_status_btn, simple)
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
        if hasattr(self, "_gost_status_btn"):
            self._toggle_chip(self._gost_status_btn, config.gost_mode)
        if config.gost_mode:
            self._gost_css.load_from_data(b"* { font-family: 'GOST type B'; }")
        else:
            self._gost_css.load_from_data(b"")

    def _toggle_chip(self, btn: Gtk.Widget, active: bool) -> None:
        """Add/remove the active-pill visual on a status bar toggle button."""
        if active:
            btn.add_css_class("mode-btn-active")
        else:
            btn.remove_css_class("mode-btn-active")

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
        if hasattr(self, "_compact_status_btn"):
            self._toggle_chip(self._compact_status_btn, config.compact_mode)

    def _on_dev_status_clicked(self, _btn):
        self._dev_mode = not getattr(self, "_dev_mode", False)
        self._apply_dev_mode()

    def _on_typst_edit_clicked(self, _btn):
        self._typst_edit_active = not self._typst_edit_active
        if self._typst_edit_active:
            self._typst_edit_lbl.set_markup("<b>Typst</b>")
        else:
            self._typst_edit_lbl.set_text("Typst")
        self._toggle_chip(self._typst_edit_btn, self._typst_edit_active)
        if hasattr(self, "_content_widget"):
            self._content_widget.set_typst_mode(self._typst_edit_active)

    def _apply_dev_mode(self):
        dev = getattr(self, "_dev_mode", False)
        if hasattr(self, "_dev_status_lbl"):
            if dev:
                self._dev_status_lbl.set_markup("<b>Dev</b>")
            else:
                self._dev_status_lbl.set_text("Dev")
        if hasattr(self, "_dev_status_btn"):
            self._toggle_chip(self._dev_status_btn, dev)
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
                typ_src = self._exporter._build_manuscript_typst()
            else:
                typ_src = self._exporter._build_bulletin_typst(digital=False)
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
            ("export-text",   self._exporter.export_text,       None),
            ("export-typst",       self._exporter.export_typst,          None),
            ("quick-export-typst", self._exporter.quick_export_typst,    "<Ctrl>e"),
            ("compile-pdf",        self._exporter.compile_typst_pdf,     "<Ctrl><Shift>p"),
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
            ("unlink-typ",         self._exporter._unlink_typ,           None),
            ("snippets",           self.open_snippets,          "<Ctrl><Shift>i"),
            ("scripture-search",   self.open_scripture_search,  "<Ctrl><Shift>f"),
            ("export-csv",         self.export_csv,             None),
            ("export-bulletin",    self._exporter.export_bulletin,        "<Ctrl><Shift>b"),
            ("export-html",        self._exporter.export_html,            None),
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
            ("toggle-bulletin-edit", self._preview._toggle_bulletin_edit, None),
            ("show-shortcuts",     self._show_shortcuts_window,         "<Ctrl>question"),
            ("duplicate-item",     self.duplicate_item,                 "<Ctrl><Shift>d"),
        ]:
            a = Gio.SimpleAction.new(name, None)
            a.connect("activate", lambda _a,_p,f=cb: f()); self.add_action(a)
            if accel: self.get_application().set_accels_for_action(f"win.{name}", [accel])
        ra = Gio.SimpleAction.new("open-recent-file", GLib.VariantType.new("s"))
        ra.connect("activate", lambda _a,p: self._confirm_discard(lambda path=p.get_string(): self._load_file(path)))
        self.add_action(ra)
        na = Gio.SimpleAction.new("noop", None); na.set_enabled(False); self.add_action(na)

    # ── UI ────────────────────────────────────────────────────────────────────
    # (Moved to MainChrome, rubric_package/panels/main_chrome.py — see refactor.md.)

    # ── Palette panel ─────────────────────────────────────────────────────────
    # (Moved to PalettePanel, rubric_package/panels/palette_panel.py — see refactor.md.)

    # ── Preamble panel toggle ─────────────────────────────────────────────────
    # (The template editor UI/state itself now lives in PreamblePanel,
    #  rubric_package/panels/preamble_panel.py; this status-bar click handler
    #  stayed here because it's really about switching _main_stack/_preview
    #  mode, not about editing template fields.)

    def _on_preamble_clicked(self, _btn):
        self._preamble_active = not self._preamble_active
        self._toggle_chip(self._preamble_btn, self._preamble_active)
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
                self._preview._toggle_preview_panel()
            else:
                self._preview._do_preview_update()
        else:
            self._preamble_lbl.set_text("Template")
            self._main_stack.set_visible_child_name("order")

    # ── Order panel ───────────────────────────────────────────────────────────
    # (Moved to OrderPanel, rubric_package/panels/order_panel.py — see refactor.md.)

    # ── Planning notes ────────────────────────────────────────────────────────

    def _build_planning_notes_area(self) -> Gtk.Box:
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Header bar: label + arrow indicator + pop-out button
        # The entire header is clickable (via GestureClick); the pop-out button is separate
        hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        hdr.set_margin_start(12); hdr.set_margin_end(6)
        hdr.set_margin_top(2); hdr.set_margin_bottom(2)
        hdr.add_css_class("notes-header")
        hdr.set_cursor(Gdk.Cursor.new_from_name("pointer"))

        lbl = Gtk.Label(label="Service Notes")
        lbl.add_css_class("caption"); lbl.add_css_class("dim-label")
        lbl.set_xalign(0); lbl.set_hexpand(True)
        hdr.append(lbl)

        arrow_img = Gtk.Image.new_from_icon_name("pan-down-symbolic")
        arrow_img.set_pixel_size(12); arrow_img.set_valign(Gtk.Align.CENTER)
        arrow_img.add_css_class("dim-label")
        arrow_img.set_margin_end(4)
        hdr.append(arrow_img)

        popout_btn = Gtk.Button(icon_name="window-new-symbolic",
                                tooltip_text="Open in pop-out window")
        popout_btn.add_css_class("flat"); popout_btn.add_css_class("circular")
        hdr.append(popout_btn)

        outer.append(hdr)

        # Revealer containing the text area
        rev = Gtk.Revealer()
        rev.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        rev.set_transition_duration(150)
        rev.set_reveal_child(False)
        self._planning_notes_revealer = rev

        tv_scroll = Gtk.ScrolledWindow()
        tv_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        tv_scroll.set_min_content_height(96)
        tv_scroll.set_max_content_height(240)

        self._planning_notes_buffer = Gtk.TextBuffer()
        self._planning_notes_buffer.connect("changed", self._on_planning_notes_changed)

        tv = Gtk.TextView(buffer=self._planning_notes_buffer)
        tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        tv.set_accepts_tab(False)
        tv.set_left_margin(12); tv.set_right_margin(12)
        tv.set_top_margin(6); tv.set_bottom_margin(6)
        tv.add_css_class("monospace")
        tv_scroll.set_child(tv)
        rev.set_child(tv_scroll)
        outer.append(rev)
        outer.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        def _toggle(_=None):
            revealed = not rev.get_reveal_child()
            rev.set_reveal_child(revealed)
            arrow_img.set_from_icon_name("pan-up-symbolic" if revealed else "pan-down-symbolic")

        hdr_click = Gtk.GestureClick()
        hdr_click.connect("released", lambda _g, _n, _x, _y: _toggle())
        hdr.add_controller(hdr_click)
        popout_btn.connect("clicked", lambda _: self._open_planning_notes_window())

        return outer

    def _on_planning_notes_changed(self, buf: Gtk.TextBuffer):
        if getattr(self, "_loading_notes", False):
            return
        text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
        self.service_planning_notes = text
        # Planning notes are not in the bulletin — don't trigger a preview redraw.
        self.modified = True
        self._update_title()
        self._update_save_state_chip()
        if self.current_file:
            if getattr(self, "_deferred_save_id", None):
                GLib.source_remove(self._deferred_save_id)
            self._deferred_save_id = GLib.timeout_add(15000, self._deferred_save)

    def _on_series_changed(self, entry: Gtk.Entry):
        self.service_series = entry.get_text().strip()
        self._mark_modified()

    def _on_tags_changed(self, entry: Gtk.Entry):
        self.service_tags = [t.strip() for t in entry.get_text().split(",") if t.strip()]
        self._mark_modified()

    def _on_pinned_toggled(self, switch: Gtk.Switch, _pspec):
        self.service_pinned = switch.get_active()
        self._mark_modified()

    def _open_planning_notes_window(self):
        win = ServicePlanningNotesWindow(
            buffer=self._planning_notes_buffer, transient_for=self)
        win.present()

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
        try:
            _cidx = SECTION_COLORS.index(colour)
            row.add_css_class(f"section-c{_cidx}")
        except ValueError:
            row.add_css_class("section-gray")
        # User-assigned icon takes priority; fall back to auto type icon
        user_icon = getattr(si, "icon", "")
        _ico_name = user_icon or _item_type_icon(si.name)
        if _ico_name:
            _ico = Gtk.Image(icon_name=_ico_name, pixel_size=14)
            _ico.add_css_class("dim-label"); _ico.set_valign(Gtk.Align.CENTER)
            _ico.set_margin_start(2)
            row.add_prefix(_ico)
        handle = Gtk.Label(label="⠿")
        handle.add_css_class("dim-label"); handle.add_css_class("drag-handle")
        handle.set_valign(Gtk.Align.CENTER)
        handle.set_cursor(Gdk.Cursor.new_from_name("grab"))
        row.add_suffix(handle)
        if not si.show_in_bulletin:
            row.set_opacity(0.45)
        elif getattr(si, "bulletin_heading_only", False):
            row.set_opacity(0.7)
        self._attach_dnd(row, global_idx); return row

    def _make_divider_row(self, div: SectionDivider, global_idx: int) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow(); row._entry = div
        bx = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        bx.set_margin_top(2); bx.set_margin_bottom(2)
        bx.add_css_class("divider-header")
        colour = _section_colour(div.title)
        # Left accent stripe in section colour
        r, g, b = _hex_to_rgb(colour)
        stripe = Gtk.DrawingArea(); stripe.set_size_request(6, -1)
        def _draw_stripe(_da, cr, _w, _h, _r=r, _g=g, _b=b):
            cr.set_source_rgb(_r, _g, _b); cr.paint()
        stripe.set_draw_func(_draw_stripe)
        stripe.set_valign(Gtk.Align.FILL)
        bx.append(stripe)
        handle = Gtk.Label(label="⠿")
        handle.add_css_class("dim-label"); handle.add_css_class("drag-handle")
        handle.set_valign(Gtk.Align.CENTER)
        handle.set_cursor(Gdk.Cursor.new_from_name("grab"))
        bx.append(handle)
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
            ph = Adw.StatusPage(title="Section is empty",
                description="Double-click an element in the palette to add it, or drag elements here.",
                icon_name="rubric-symbolic")
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
            self._palette._fill_palette_inner()
        else:
            self._palette._refresh_recently_used()
        GLib.idle_add(self.leader_entry.grab_focus)
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
        if not (0 <= idx < len(self.service_entries)): return
        entry = self.service_entries[idx]
        label = entry.title if entry.is_divider else entry.name
        self._push_undo()
        del self.service_entries[idx]; self._refresh_order_list(idx); self._mark_modified()
        toast = Adw.Toast.new(f'"{label}" removed')
        toast.set_timeout(6); toast.set_button_label("Undo")
        toast.connect("button-clicked", lambda _: self.undo())
        self._toast_overlay.add_toast(toast)

    # ── Order actions ─────────────────────────────────────────────────────────

    def remove_item(self):
        idx = self._selected_index()
        if idx < 0: return
        entry = self.service_entries[idx]
        label = entry.title if entry.is_divider else entry.name
        self._push_undo(); del self.service_entries[idx]; self._refresh_order_list(idx); self._mark_modified()
        toast = Adw.Toast.new(f'"{label}" removed')
        toast.set_timeout(6); toast.set_button_label("Undo")
        toast.connect("button-clicked", lambda _: self.undo())
        self._toast_overlay.add_toast(toast)

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
        GLib.idle_add(name_row.grab_focus)

    def duplicate_item(self):
        """Duplicate the currently selected element and insert it immediately after."""
        idx = self._selected_index()
        if idx < 0: return
        entry = self.service_entries[idx]
        if entry.is_divider:
            dup = SectionDivider(entry.title)
        else:
            dup = ServiceItem(entry.name, entry.section)
            for attr in ("content_typst", "leader", "rubric_note", "duration",
                         "show_in_bulletin", "bulletin_heading_only", "bulletin_summary", "icon"):
                if hasattr(entry, attr):
                    setattr(dup, attr, getattr(entry, attr))
        self._push_undo()
        self.service_entries.insert(idx + 1, dup)
        self._refresh_order_list(idx + 1)
        self._mark_modified()

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
        self._update_word_count()

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
        self._season_colour_hex = cx
        self.season_dot.set_markup(f'<span color="{cx}">●</span>')
        self.season_label.set_markup(f'<span color="{cx}">{GLib.markup_escape_text(info["week"])}</span>')
        self._colour_bar_rgb = _hex_to_rgb(cx); self._colour_bar.queue_draw(); self._order_season_strip.queue_draw()
        if hasattr(self, "_season_hdr_css"):
            r8, g8, b8 = (int(cx.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
            self._season_hdr_css.load_from_data(
                f".rubric-main-hdr {{ background-image: linear-gradient("
                f"to right, rgba({r8},{g8},{b8},0.15) 0%, transparent 70%); }}".encode())
            if hasattr(self, "_reading_chip_css"):
                self._reading_chip_css.load_from_data(
                    f"button.reading-chip {{ background: rgba({r8},{g8},{b8},0.10); }}".encode())

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
        """Rebuild the events popover button and content for date d."""
        btn = getattr(self, "_events_btn", None)
        lbl = getattr(self, "_events_btn_lbl", None)
        pop_box = getattr(self, "_events_popover_box", None)
        if btn is None:
            return

        if pop_box is not None:
            while pop_box.get_first_child():
                pop_box.remove(pop_box.get_first_child())

        try:
            from observances import get_observances, get_previous_observance, TYPES
        except ImportError:
            return

        import re as _re
        from datetime import timedelta

        def _strip_date_parens(name: str) -> str:
            return _re.sub(r'\s*\([A-Za-z]{3,9}\s+\d{1,2}\)\s*$', '', name).strip()

        cx = getattr(self, "_season_colour_hex", "#888780")
        season_text = self.season_label.get_text() if hasattr(self, "season_label") else ""

        # Update button label: coloured dot + season week name
        if lbl is not None:
            if season_text:
                lbl.set_markup(
                    f'<span color="{cx}">●</span> {GLib.markup_escape_text(season_text)}')
            else:
                lbl.set_markup(f'<span color="{cx}">●</span>')
        btn.set_visible(True)

        if pop_box is None:
            return

        # ── Season header ──────────────────────────────────────────────────────
        hdr_lbl = Gtk.Label()
        hdr_lbl.set_markup(
            f'<span color="{cx}"><b>●</b></span>  <b>{GLib.markup_escape_text(season_text)}</b>'
            if season_text else f'<span color="{cx}"><b>●</b></span>')
        hdr_lbl.set_xalign(0)
        pop_box.append(hdr_lbl)

        # ── Helper to build one event row ──────────────────────────────────────
        def _event_row(name: str, type_key: str, prox: str, past: bool,
                       wiki_name: str | None) -> Gtk.Widget:
            ti = TYPES.get(type_key, {})
            colour = ti.get("colour", "#888780")
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            row.set_margin_top(1); row.set_margin_bottom(1)
            dot = Gtk.Label()
            dot.set_markup(f'<span color="{colour}">{"○" if past else "●"}</span>')
            dot.set_valign(Gtk.Align.CENTER)
            row.append(dot)
            name_lbl = Gtk.Label(label=_strip_date_parens(name))
            name_lbl.set_xalign(0); name_lbl.set_hexpand(True)
            name_lbl.add_css_class("caption")
            if past:
                name_lbl.add_css_class("dim-label")
            row.append(name_lbl)
            if prox:
                prox_lbl = Gtk.Label(label=prox)
                prox_lbl.add_css_class("caption"); prox_lbl.add_css_class("dim-label")
                row.append(prox_lbl)
            if wiki_name:
                wrap = Gtk.Button()
                wrap.set_child(row); wrap.add_css_class("flat")
                wrap.set_tooltip_text(f"Open Wikipedia: {wiki_name}")
                wrap.connect("clicked", lambda _b, n=wiki_name: (
                    btn.get_popover().popdown() if btn.get_popover() else None,
                    self._open_observance_wiki(n)))
                return wrap
            return row

        # ── Liturgical events ──────────────────────────────────────────────────
        obs_list = get_observances(d)
        prev_obs = get_previous_observance(d)
        pop_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        if prev_obs:
            pop_box.append(_event_row(
                prev_obs["name"], prev_obs.get("type", ""),
                prev_obs.get("proximity", ""), past=True, wiki_name=prev_obs["name"]))
        for obs in obs_list[:6]:
            pop_box.append(_event_row(
                obs["name"], obs.get("type", ""),
                obs.get("proximity", ""), past=False, wiki_name=obs["name"]))

        # ── Justice / custom dates ─────────────────────────────────────────────
        _JUSTICE_TYPES = {"social_justice", "indigenous", "ecological", "pride"}

        justice_events: list[tuple] = []
        seen: set[tuple] = set()
        for delta in range(-30, 61):
            wd = d + timedelta(days=delta)
            key = (wd.month, wd.day)
            if key in seen:
                continue
            for e in config.all_dates:
                if (e.get("month") == wd.month and e.get("day") == wd.day
                        and e.get("type") in _JUSTICE_TYPES):
                    seen.add(key)
                    justice_events.append((wd, e))
                    break

        if justice_events:
            pop_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
            sec_lbl = Gtk.Label(label="Justice & Custom Dates")
            sec_lbl.add_css_class("caption"); sec_lbl.add_css_class("dim-label")
            sec_lbl.set_xalign(0); sec_lbl.set_margin_top(2); sec_lbl.set_margin_bottom(2)
            pop_box.append(sec_lbl)
            for wd, e in justice_events:
                pop_box.append(_event_row(
                    e["name"], e.get("type", ""),
                    wd.strftime("%-d %b"), past=(wd < d), wiki_name=None))

        # ── Edit dates button ──────────────────────────────────────────────────
        pop_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        edit_btn = Gtk.Button(label="Edit dates…")
        edit_btn.add_css_class("flat"); edit_btn.set_halign(Gtk.Align.END)
        edit_btn.set_margin_top(2)
        edit_btn.connect("clicked", lambda _: (
            btn.get_popover().popdown() if btn.get_popover() else None,
            self._open_dates_window()))
        pop_box.append(edit_btn)

    def _refresh_justice_row(self, d) -> None:
        """Redirect to unified events popover (called by external windows on date edits)."""
        self._refresh_observances_row(d)

    def _step_sunday(self, direction: int):
        """Move the readings display to the prev (-1) or next (+1) Sunday."""
        from datetime import timedelta
        if self._readings_sunday is None: return
        new_sun = self._readings_sunday + timedelta(weeks=direction)
        self._update_readings(self.selected_date, override_sunday=new_sun)

    # ── Window toggles, Typst plumbing & core document state ───────────────────
    # (Live preview UI/compile logic itself now lives in BulletinPreview,
    #  rubric_package/preview/bulletin_preview.py — these are what's left after
    #  that extraction: general window toggles, the Typst helpers shared with
    #  BulletinExporter/AV-sheet/leader's-order-PDF, and MainWindow's core
    #  document-state methods that every extracted class calls back into.)

    def _open_prefs_page(self, page_title: str):
        """Open Preferences and navigate to the named page."""
        a = self.lookup_action("preferences")
        if a:
            a.activate(None)

    def _open_sidebar(self):
        """Open the element palette sidebar if it isn't already open."""
        if not self._palette_visible:
            self._sidebar_btn.set_active(True)

    def _toggle_palette_sidebar(self, btn):
        if btn.get_active():
            self._palette_visible = True
            self._palette_paned.set_shrink_start_child(False)
            def _set_palette_pos():
                pos = getattr(self, "_pre_hide_palette_pos",
                              config.ui_panes.get("palette_paned", 290))
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
        if hasattr(self, "_focus_status_btn"):
            self._toggle_chip(self._focus_status_btn, active)
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

    def _copy_as_text(self):
        """Format service as clean plain text and copy to clipboard."""
        title = self.service_title_entry.get_text() or "Order of Service"
        date_str = self.selected_date.strftime("%-d %B %Y") if self.selected_date else ""
        parts = [title]
        if date_str:
            parts.append(date_str)
        parts.append("")
        for sec, items in self._exporter._grouped_entries():
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
            _spc = p.get("par_spacing", 0.65)
            parts.append(f'#set par(justify: false, spacing: {_spc:.2f}em, first-line-indent: 0pt)')
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

    def _mark_modified(self):
        self.modified = True
        self._update_title()
        self._preview._schedule_preview_update()
        self._update_save_state_chip()
        if self.current_file:
            if getattr(self, "_deferred_save_id", None):
                GLib.source_remove(self._deferred_save_id)
            self._deferred_save_id = GLib.timeout_add(15000, self._deferred_save)

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
        if getattr(self, "service_planning_notes", ""):
            d["planning_notes"] = self.service_planning_notes
        if getattr(self, "service_tags", None):
            d["tags"] = self.service_tags
        if getattr(self, "service_series", ""):
            d["series"] = self.service_series
        if getattr(self, "service_pinned", False):
            d["pinned"] = True
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
                                "Sign in once and Rubric handles the rest. You can skip this and connect later in Preferences.")
        sub3.set_wrap(True); sub3.set_justify(Gtk.Justification.CENTER)
        sub3.add_css_class("dim-label"); sub3.set_margin_bottom(10)
        p3.append(sub3)

        p3_status = Gtk.Label(label="")
        p3_status.add_css_class("caption"); p3_status.add_css_class("dim-label")
        p3_status.set_wrap(True); p3_status.set_margin_top(4)

        # ── Sign in ──
        signin_grp = Adw.PreferencesGroup()
        signin_row = Adw.ActionRow(title="Sign in with GitHub")
        signin_btn = Gtk.Button(label="Sign in", valign=Gtk.Align.CENTER)
        signin_btn.add_css_class("suggested-action")
        signin_row.add_suffix(signin_btn)
        signin_grp.add(signin_row)
        p3.append(signin_grp)

        # ── Connected state ──
        connected_grp = Adw.PreferencesGroup()
        connected_row = Adw.ActionRow(title="Connected as")
        disconnect_btn = Gtk.Button(label="Disconnect", valign=Gtk.Align.CENTER)
        disconnect_btn.add_css_class("flat")
        connected_row.add_suffix(disconnect_btn)
        connected_grp.add(connected_row)

        name_row = Adw.EntryRow(title="Repository name")
        connected_grp.add(name_row)
        private_row = Adw.SwitchRow(title="Private repository", active=True)
        connected_grp.add(private_row)
        create_row = Adw.ActionRow(title="Create a new repository on GitHub")
        create_btn = Gtk.Button(label="Create", valign=Gtk.Align.CENTER)
        create_btn.add_css_class("suggested-action")
        create_row.add_suffix(create_btn)
        connected_grp.add(create_row)
        p3.append(connected_grp)

        # ── Manual fallback ──
        manual_grp = Adw.PreferencesGroup(
            title="Or connect an existing repository manually",
        )
        gh_entry = Adw.EntryRow(title="GitHub repository URL (https://…)")
        gh_entry.set_text(config.github_repo and self._detect_github_remote() or "")
        manual_grp.add(gh_entry)
        connect_row = Adw.ActionRow(title="Save and connect")
        connect_btn = Gtk.Button(label="Connect", valign=Gtk.Align.CENTER)
        connect_row.add_suffix(connect_btn); manual_grp.add(connect_row)
        p3.append(manual_grp)

        p3.append(p3_status)

        def _set_remote(url: str) -> str | None:
            """Points the chosen folder's origin remote at url. Returns an error string, or None on success."""
            repo = config.github_repo
            if not repo:
                return "Set up a folder (step 1) first."
            try:
                chk = subprocess.run(_GIT + ["-C", repo, "remote", "get-url", "origin"],
                                     capture_output=True, text=True, timeout=5)
                cmd = _GIT + ["-C", repo, "remote", "set-url" if chk.returncode == 0 else "add", "origin", url]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                return None if r.returncode == 0 else r.stderr.strip()
            except Exception as e:
                return str(e)

        def _refresh_p3():
            token = secret_store.load_github_token()
            signin_grp.set_visible(not token)
            connected_grp.set_visible(bool(token))
            if token:
                connected_row.set_subtitle(f"@{config.github_username}" if config.github_username else "")
                default_name = Path(config.github_repo).name if config.github_repo else "liturgy"
                if not name_row.get_text():
                    name_row.set_text(default_name)
                remote = self._detect_github_remote()
                if remote:
                    p3_status.set_label(f"✓ Connected to {remote}")

        def _on_signin(_b):
            def on_connected(token, username):
                config.github_username = username
                config.save()
                p3_status.set_label(f"✓ Signed in as @{username}")
                _refresh_p3()
            github_signin.present(win, on_connected)
        signin_btn.connect("clicked", _on_signin)

        def _on_disconnect(_b):
            secret_store.delete_github_token()
            config.github_username = ""
            config.save()
            p3_status.set_label("Signed out.")
            _refresh_p3()
        disconnect_btn.connect("clicked", _on_disconnect)

        def _on_create(_b):
            if not config.github_repo:
                p3_status.set_label("Set up a folder (step 1) first."); return
            token = secret_store.load_github_token()
            if not token:
                p3_status.set_label("Sign in with GitHub first."); return
            name = name_row.get_text().strip() or "liturgy"
            private = private_row.get_active()
            create_btn.set_sensitive(False)
            p3_status.set_label(f"Creating {name}…")

            def run():
                try:
                    clone_url = github_auth.create_repo(token, name, private)
                except github_auth.GithubAuthError as e:
                    GLib.idle_add(lambda: (p3_status.set_label(f"Couldn't create repository: {e}"),
                                           create_btn.set_sensitive(True)))
                    return
                err = _set_remote(clone_url)

                def finish():
                    create_btn.set_sensitive(True)
                    if err:
                        p3_status.set_label(f"Repository created, but couldn't connect it: {err}")
                    else:
                        p3_status.set_label(f"✓ Created and connected: {clone_url}")
                GLib.idle_add(finish)
            threading.Thread(target=run, daemon=True).start()
        create_btn.connect("clicked", _on_create)

        def _on_connect3(_b):
            url = gh_entry.get_text().strip()
            if not url: p3_status.set_label("Paste your GitHub repository URL first."); return
            err = _set_remote(url)
            p3_status.set_label(f"Error: {err}" if err else f"✓ Connected to {url}")
        connect_btn.connect("clicked", _on_connect3)

        _refresh_p3()
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
                GLib.idle_add(self._open_sidebar)

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
            except Exception as e:
                toast = Adw.Toast.new(f"Autosave failed: {e}")
                toast.set_timeout(5)
                self._toast_overlay.add_toast(toast)
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
        if hasattr(self, "_events_btn"):
            self._events_btn.set_visible(False)
        self.current_file=None; self.typ_file=None; self.modified=False
        self._selected_global_idx=-1; self._update_title()
        self.service_bulletin_text = ""
        self.service_attendance = 0
        self.service_debrief = ""
        self.service_planning_notes = ""
        self.service_tags = []
        self.service_series = ""
        self.service_pinned = False
        if hasattr(self, "_tags_entry"):
            self._tags_entry.set_text("")
        if hasattr(self, "_series_entry"):
            self._series_entry.set_text("")
        if hasattr(self, "_pinned_toggle"):
            self._pinned_toggle.set_active(False)
        if hasattr(self, "_planning_notes_buffer"):
            self._loading_notes = True
            self._planning_notes_buffer.set_text("")
            self._loading_notes = False
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
                GLib.idle_add(self._open_sidebar)
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
                        GLib.idle_add(self._open_sidebar)

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
            self._exporter._update_tex_btn()
            self.service_bulletin_text = data.get("bulletin_text", "")
            self.service_attendance = data.get("attendance", 0)
            self.service_debrief    = data.get("debrief", "")
            self.service_planning_notes = data.get("planning_notes", "")
            if hasattr(self, "_planning_notes_buffer"):
                self._loading_notes = True
                self._planning_notes_buffer.set_text(self.service_planning_notes)
                self._loading_notes = False
            self.service_tags = list(data.get("tags", []) or [])
            self.service_series = data.get("series", "") or ""
            self.service_pinned = bool(data.get("pinned", False))
            if hasattr(self, "_tags_entry"):
                self._tags_entry.set_text(", ".join(self.service_tags))
            if hasattr(self, "_series_entry"):
                self._series_entry.set_text(self.service_series)
            if hasattr(self, "_pinned_toggle"):
                self._pinned_toggle.set_active(self.service_pinned)
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
            self._preview._schedule_preview_update(from_save=True)
            if getattr(self, "_close_after_save", False):
                self._close_after_save = False
                self.destroy()
        except Exception as e: self._error("Error saving",str(e))

    def _index_service(self, path: str, data: dict | None = None):
        """Index service elements and organizational metadata into the library DB
        (runs in background threads)."""
        try:
            from rubric_package.db import element_index_service as _eidx, service_meta_update as _smeta
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

        # Metadata upsert is a single small write — done synchronously (unlike the
        # element re-index above) so the Past Liturgies library reflects a just-saved
        # file immediately, with no race against a background thread finishing late.
        from rubric_package.utils.typst import notes_preview
        preview = notes_preview(data.get("planning_notes", ""))
        debrief_preview = notes_preview(data.get("debrief", ""))
        try:
            mtime = Path(path).stat().st_mtime
        except OSError:
            mtime = 0.0
        _smeta(path, title, date, list(data.get("tags", []) or []),
               data.get("series", "") or "", bool(data.get("pinned", False)),
               preview, mtime,
               attendance=int(data.get("attendance", 0) or 0),
               debrief_preview=debrief_preview)

    def _background_index_scan(self):
        """Scan repo liturgy folder and index any unindexed or stale services."""
        try:
            from rubric_package.db import (element_index_service as _eidx, element_services as _esvc,
                service_meta_update as _smeta, service_meta_all_mtimes as _smeta_mtimes,
                service_meta_prune as _smeta_prune, _open as _db_open)
        except ImportError:
            return
        from rubric_package.utils.typst import notes_preview
        folders = []
        liturgy_dir = self._repo_subdir("liturgy")
        if liturgy_dir and liturgy_dir.is_dir():
            folders.append(liturgy_dir)
        for folder in folders:
            already = {s["service_path"] for s in _esvc(limit=5000)}
            cached_mtimes = _smeta_mtimes()
            on_disk: set = set()
            con = _db_open()
            try:
                for p in folder.glob("**/*.liturgy"):
                    path_str = str(p); on_disk.add(path_str)
                    try:
                        mtime = p.stat().st_mtime
                        cached_mtime = cached_mtimes.get(path_str)
                        if cached_mtime is not None and abs(cached_mtime - mtime) < 0.01:
                            if path_str in already:
                                continue
                        data = json.loads(p.read_text(encoding="utf-8"))
                        title = data.get("title", ""); date = data.get("date", "")
                        if path_str not in already:
                            _eidx(path_str, title, date, data.get("items", []), _con=con)
                        preview = notes_preview(data.get("planning_notes", ""))
                        debrief_preview = notes_preview(data.get("debrief", ""))
                        _smeta(path_str, title, date, list(data.get("tags", []) or []),
                               data.get("series", "") or "", bool(data.get("pinned", False)),
                               preview, mtime,
                               attendance=int(data.get("attendance", 0) or 0),
                               debrief_preview=debrief_preview, _con=con)
                    except Exception:
                        pass
                con.commit()
            finally:
                con.close()
            _smeta_prune(on_disk)

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
        else:
            total = sum(e.duration for e in timed)
            self._time_bar.set_visible(True)
            TARGET = 75
            if total > TARGET:
                self._time_bar.set_markup(
                    f'<span color="#B91C1C">~{total} min total</span>'
                    f'<span color="#B91C1C" size="small">  ({total - TARGET} over)</span>')
            else:
                self._time_bar.set_markup(f'<span color="#15803D">~{total} min total</span>')
        self._update_word_count()

    def _update_word_count(self):
        """Recompute word count across all service items and update the status chip."""
        import re as _re
        total = 0
        for e in self.service_entries:
            if not isinstance(e, ServiceItem):
                continue
            text = strip_typst_plain(e.content_typst or "")
            # strip leader notes (not spoken by congregation)
            text = strip_leader_notes(text)
            words = _re.split(r'\s+', text.strip())
            total += sum(1 for w in words if w)
        if total < 10:
            self._word_count_lbl.set_visible(False)
        else:
            mins = max(1, round(total / 130))
            self._word_count_lbl.set_text(f"{total:,} words · ~{mins} min")
            self._word_count_lbl.set_visible(True)

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
            self._load_typst_preamble("manuscript"),
            '',
            TYPST_SHARED,
            '',
        ]
        parts += ['#align(center)[']
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
                parts.append(f'= {_typst_escape(entry.title)}')
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
                rubric = getattr(entry, "rubric_note", "")
                if rubric:
                    parts.append(f'#rubric-note[{_typst_escape(rubric)}]')
                    parts.append('')
                if entry.content_typst:
                    parts.append(f'#text(size: 0.9em)[\n{linebreak_fix(entry.content_typst)}\n]')
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
            self._toast_overlay.add_toast(done_toast)
            Gtk.show_uri(None, GLib.filename_to_uri(str(pdf), None), 0)

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
                "The easiest fix: open Preferences → GitHub and click Sign in with GitHub.\n\n"
                "Prefer a Personal Access Token (PAT) instead? Passwords no longer work:\n"
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

                with git_credential_args(secret_store.load_github_token()) as cred:
                    if has_remote:
                        pull_r = subprocess.run(
                            _GIT + ["-C", repo] + cred + ["pull", "--rebase"],
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

                    # ── Push ────────────────────────────────────────────────
                    push_r = subprocess.run(_GIT + ["-C", repo] + cred + ["push"],
                                            capture_output=True, text=True, timeout=30)
                    if push_r.returncode != 0:
                        err_low = (push_r.stderr or "").lower()
                        if "no upstream" in err_low or "set-upstream" in err_low or \
                           "set the upstream" in err_low:
                            push_r = subprocess.run(
                                _GIT + ["-C", repo] + cred + ["push", "--set-upstream", "origin", "HEAD"],
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
                with git_credential_args(secret_store.load_github_token()) as cred:
                    r = subprocess.run(_GIT + ["-C", repo] + cred + ["pull"],
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
            <child><object class='GtkShortcutsShortcut'><property name='accelerator'>&lt;ctrl&gt;&lt;shift&gt;d</property><property name='title'>Duplicate element</property></object></child>
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
            if r == "html":     self._exporter.export_html()
            elif r == "bulletin": self._exporter.export_bulletin()
            elif r == "minister": self.export_minister_pdf()
            elif r == "av":     self.export_av_sheet()
            elif r == "typst":  self._exporter.export_typst()
            elif r == "text":   self._exporter.export_text()
            elif r == "csv":    self.export_csv()
        dlg.connect("response", on_resp)
        dlg.present()

    def open_preferences(self, page: str | None = None):
        prefs = PreferencesWindow(transient_for=self, modal=True)
        if page == "dates" and hasattr(prefs, "_dates_page"):
            prefs.set_visible_page(prefs._dates_page)
        def on_destroy(_):
            self._palette._fill_palette_inner(); self._apply_tab_mode()
            if self.selected_date:
                self._refresh_justice_row(self.selected_date)
        prefs.connect("destroy", on_destroy); prefs.present()

    def _open_dates_window(self):
        win = DatesEditorWindow(main_win=self, transient_for=self)
        win.present()

    def _error(self, heading, body):
        dlg = Adw.MessageDialog(transient_for=self, heading=heading, body=body)
        dlg.add_response("ok","OK"); dlg.present()

    def _on_main_destroy(self, _widget):
        """Save pane positions so they're restored on next launch."""
        ui: dict = {}
        if hasattr(self, "_order_hpaned"):
            ui["order_hpaned"] = self._order_hpaned.get_position()
        # Palette: save the last visible width, not 0
        pre = getattr(self, "_pre_hide_palette_pos", None)
        if pre and pre > 10:
            ui["palette_paned"] = pre
        elif getattr(self, "_palette_visible", False) and hasattr(self, "_palette_paned"):
            ui["palette_paned"] = self._palette_paned.get_position()
        if getattr(self, "_preview_visible", False) and hasattr(self, "_preview_paned"):
            ui["preview_paned"] = self._preview_paned.get_position()
        elif config.ui_panes.get("preview_paned"):
            ui["preview_paned"] = config.ui_panes["preview_paned"]
        config.ui_panes = ui
        config.save_window_size("main", self.get_width(), self.get_height(), self.is_maximized())
        config.save()

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
        self._help_win = HelpWindow(main_window=self, app_version=APP_VERSION, start_tab=start_tab, transient_for=self)
        self._help_win.present()

    def open_bulletin_prefs(self):
        win = getattr(self, "_bulletin_prefs_win", None)
        if win and win.get_visible():
            win.present(); return
        self._bulletin_prefs_win = BulletinPrefsWindow(main_window=self, transient_for=self)
        self._bulletin_prefs_win.present()


# ── Application ───────────────────────────────────────────────────────────────

class LiturgyPlannerApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="io.github.calstfrancis.rubric", flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.connect("activate", self._on_activate)
        self._first_activate = True

    def _new_window(self, *_):
        MainWindow(application=self).present()

    def _on_activate(self, app):
        if self._first_activate:
            self._first_activate = False
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
.compact-mode .order-list row.activatable { min-height: 24px; }
.compact-mode .order-list row.activatable title { font-size: 0.8em; margin-top: 0; margin-bottom: 0; }
/* Status bar: slim height */
.toolbar { min-height: 18px; padding-top: 0; padding-bottom: 0; }
.toolbar button.flat { min-height: 0; padding-top: 1px; padding-bottom: 1px; }
/* Status bar separator */
.rubric-statusbar-sep { opacity: 0.25; }
/* Selected service order row: left accent bar */
.order-list row.activatable:selected { border-left: 3px solid @accent_color; }
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
headerbar button:not(.suggested-action) { min-width: 32px; min-height: 32px; padding: 4px; }
/* Drag handle: subtle at rest, visible on hover (grab cursor set in code) */
.order-list row .drag-handle { opacity: 0.3; transition: opacity 120ms; }
.order-list row:hover .drag-handle { opacity: 0.6; }
/* Section divider - full-width coloured header row */
.divider-header { background: alpha(@headerbar_shade_color, 0.06); min-height: 28px; }
/* Section colour left borders on element rows */
.section-c0 { border-left: 3px solid #1D9E75; }
.section-c1 { border-left: 3px solid #534AB7; }
.section-c2 { border-left: 3px solid #993C1D; }
.section-c3 { border-left: 3px solid #185FA5; }
.section-c4 { border-left: 3px solid #B45309; }
.section-c5 { border-left: 3px solid #6B21A8; }
.section-c6 { border-left: 3px solid #15803D; }
.section-c7 { border-left: 3px solid #B91C1C; }
.section-gray { border-left: 3px solid #888780; }
/* Active mode toggle chips */
.mode-btn-active { background: alpha(@accent_bg_color, 0.18); border-radius: 9999px; }
/* Metric pill chips (time bar, word count) */
.metric-pill { background: alpha(@headerbar_shade_color, 0.5); border-radius: 9999px; padding: 1px 7px; }
/* Planning notes header: pointer cursor + subtle hover */
.notes-header { border-radius: 4px; }
.notes-header:hover { background: alpha(@accent_bg_color, 0.06); }
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
            # Register app-level "New Window" action
            nw_action = Gio.SimpleAction.new("new-window", None)
            nw_action.connect("activate", self._new_window)
            self.add_action(nw_action)
            self.set_accels_for_action("app.new-window", ["<Ctrl><Shift>n"])
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
