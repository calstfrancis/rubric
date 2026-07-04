"""MainChrome — top-level window chrome for Rubric.

Owns `MainWindow`'s header bar (document actions, undo/redo, title/date
popover, cover thumbnail, preview toggle), the status bar (mode toggles,
liturgical-events popover, word-count/save-state chips, git/version buttons),
and the top-level paned layout that stitches together the already-extracted
panels (palette, order, preamble, preview). Constructed with a reference to
the MainWindow instance it serves, the same composition pattern used by
BulletinExporter, BulletinPreview, PreamblePanel, HymnLookupPanel, and
OrderPanel.
"""

from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib, Gdk, Pango


class MainChrome:
    """Builds and owns MainWindow's header bar, status bar, and root layout."""

    def __init__(self, main_window):
        self._main = main_window

    def _build_ui(self):
        from rubric import APP_VERSION

        hdr = Adw.HeaderBar()
        hdr.add_css_class("rubric-main-hdr")
        self._main._season_hdr_css = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), self._main._season_hdr_css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        # Palette sidebar toggle — all the way at the left
        self._main._sidebar_btn = Gtk.ToggleButton(icon_name="sidebar-show",
                                             tooltip_text="Show/hide elements panel")
        self._main._sidebar_btn.set_active(False)
        self._main._sidebar_btn.add_css_class("flat")
        self._main._sidebar_btn.connect("toggled", self._main._toggle_palette_sidebar)
        hdr.pack_start(self._main._sidebar_btn)

        # New + Open as a linked pill
        doc_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        doc_box.add_css_class("linked")
        for icon, tip, cb in [("document-new", "New service (Ctrl+N)", self._main.new_service),
                               ("document-open", "Open… (Ctrl+O)", self._main.open_file)]:
            b = Gtk.Button(icon_name=icon, tooltip_text=tip)
            b.connect("clicked", lambda _, f=cb: f())
            doc_box.append(b)
        hdr.pack_start(doc_box)

        # New Window button
        nw_btn = Gtk.Button(icon_name="window-new-symbolic",
                            tooltip_text="New window (Ctrl+Shift+N)")
        nw_btn.add_css_class("flat")
        nw_btn.set_action_name("app.new-window")
        hdr.pack_start(nw_btn)

        # Undo + Redo as a linked pill
        edit_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        edit_box.add_css_class("linked")
        self._main.undo_btn = Gtk.Button(icon_name="edit-undo", tooltip_text="Undo (Ctrl+Z)")
        self._main.undo_btn.connect("clicked", lambda _: self._main.undo()); self._main.undo_btn.set_sensitive(False)
        self._main.redo_btn = Gtk.Button(icon_name="edit-redo", tooltip_text="Redo (Ctrl+Shift+Z)")
        self._main.redo_btn.connect("clicked", lambda _: self._main.redo()); self._main.redo_btn.set_sensitive(False)
        edit_box.append(self._main.undo_btn); edit_box.append(self._main.redo_btn)
        hdr.pack_start(edit_box)

        # Title widget lives inside a MenuButton so clicking it opens the service info popover
        self._main.title_widget = Adw.WindowTitle(title="Rubric", subtitle="New service")

        # Popover contents: title entry + date picker
        pop_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        pop_box.set_margin_top(14); pop_box.set_margin_bottom(14)
        pop_box.set_margin_start(16); pop_box.set_margin_end(16)

        tl = Gtk.Label(label="Service title"); tl.add_css_class("heading"); tl.set_xalign(0)
        pop_box.append(tl)
        self._main.service_title_entry = Gtk.Entry()
        self._main.service_title_entry.set_placeholder_text("Title, date, or occasion…")
        self._main.service_title_entry.set_size_request(180, -1)
        self._main.service_title_entry.connect("changed", lambda _: self._main._mark_modified())
        pop_box.append(self._main.service_title_entry)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL); pop_box.append(sep)

        dl = Gtk.Label(label="Date"); dl.add_css_class("heading"); dl.set_xalign(0)
        pop_box.append(dl)
        cal_pop = Gtk.Popover(); cal_pop.set_has_arrow(True)
        self._main.calendar = Gtk.Calendar()
        self._main.calendar.set_margin_top(8); self._main.calendar.set_margin_bottom(8)
        self._main.calendar.set_margin_start(8); self._main.calendar.set_margin_end(8)
        self._main.calendar.connect("day-selected", self._main._on_calendar_day_selected)
        cal_pop.set_child(self._main.calendar)
        date_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        _date_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        _date_ico = Gtk.Image(icon_name="x-office-calendar-symbolic")
        _date_ico.add_css_class("dim-label"); _date_box.append(_date_ico)
        self._main._date_label_widget = Gtk.Label(label="No date selected")
        self._main._date_label_widget.set_ellipsize(Pango.EllipsizeMode.END); _date_box.append(self._main._date_label_widget)
        self._main.date_button = Gtk.MenuButton(popover=cal_pop)
        self._main.date_button.set_child(_date_box)
        self._main.date_button.set_hexpand(True); date_row.append(self._main.date_button)
        clr = Gtk.Button(icon_name="edit-clear-symbolic", tooltip_text="Clear date")
        clr.add_css_class("flat"); clr.connect("clicked", self._main._on_clear_date); date_row.append(clr)
        pop_box.append(date_row)

        # Lectionary year/season — in popover, not the header bar
        lect_sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        lect_sep.set_margin_top(4); pop_box.append(lect_sep)
        self._main._lect_label = Gtk.Label()
        self._main._lect_label.add_css_class("caption"); self._main._lect_label.add_css_class("dim-label")
        self._main._lect_label.set_xalign(0); self._main._lect_label.set_margin_top(2)
        pop_box.append(self._main._lect_label)

        # Organization — series, tags, pinned (surfaced in the Past Liturgies library)
        org_sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        org_sep.set_margin_top(4); pop_box.append(org_sep)

        series_lbl = Gtk.Label(label="Series"); series_lbl.add_css_class("heading"); series_lbl.set_xalign(0)
        series_lbl.set_margin_top(4); pop_box.append(series_lbl)
        self._main._series_entry = Gtk.Entry()
        self._main._series_entry.set_placeholder_text("e.g. Advent 2026")
        self._main._series_entry.connect("changed", self._main._on_series_changed)
        pop_box.append(self._main._series_entry)

        tags_lbl = Gtk.Label(label="Tags"); tags_lbl.add_css_class("heading"); tags_lbl.set_xalign(0)
        tags_lbl.set_margin_top(6); pop_box.append(tags_lbl)
        self._main._tags_entry = Gtk.Entry()
        self._main._tags_entry.set_placeholder_text("communion, guest preacher, …")
        self._main._tags_entry.connect("changed", self._main._on_tags_changed)
        pop_box.append(self._main._tags_entry)

        pin_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        pin_row.set_margin_top(8)
        pin_lbl = Gtk.Label(label="Pinned in library"); pin_lbl.set_xalign(0); pin_lbl.set_hexpand(True)
        pin_row.append(pin_lbl)
        self._main._pinned_toggle = Gtk.Switch(valign=Gtk.Align.CENTER)
        self._main._pinned_toggle.connect("notify::active", self._main._on_pinned_toggled)
        pin_row.append(self._main._pinned_toggle)
        pop_box.append(pin_row)

        info_pop = Gtk.Popover(); info_pop.set_child(pop_box)
        info_pop.set_has_arrow(False); info_pop.set_position(Gtk.PositionType.BOTTOM)

        title_btn = Gtk.MenuButton(popover=info_pop)
        title_btn.add_css_class("flat"); title_btn.set_child(self._main.title_widget)
        hdr.set_title_widget(title_btn)
        self._main.selected_date = None

        # Cover art thumbnail — shown when a cover image is configured
        self._main._cover_thumb = Gtk.Image()
        self._main._cover_thumb.set_pixel_size(28)
        self._main._cover_thumb.add_css_class("cover-thumb")
        self._main._cover_thumb.set_visible(False)
        self._main._cover_thumb.set_tooltip_text("Cover image — change in Settings → Bulletin")
        hdr.pack_start(self._main._cover_thumb)
        self._main._refresh_cover_thumb()

        sb = Gtk.Button(icon_name="document-save", tooltip_text="Save (Ctrl+S)")
        sb.add_css_class("flat"); sb.connect("clicked", lambda _: self._main.save_file()); hdr.pack_end(sb)

        # Advanced-mode buttons — kept as instance vars for sensitivity/tooltip code
        # but not packed into the header. Use keyboard shortcuts or the hamburger menu.
        self._main.push_btn = Gtk.Button(icon_name="emblem-synchronizing-symbolic",
                                   tooltip_text="Push to GitHub (Ctrl+Shift+G)")
        self._main.push_btn.connect("clicked", lambda _: self._main.git_push())

        self._main.tex_btn = Gtk.Button(icon_name="emblem-documents-symbolic",
                                  tooltip_text="Export to Typst (Ctrl+E)")
        self._main.tex_btn.connect("clicked", lambda _: self._main._exporter.quick_export_typst())

        self._main.pdf_btn = Gtk.Button(icon_name="document-print-symbolic",
                                  tooltip_text="Compile to PDF via Typst (Ctrl+Shift+P)")
        self._main.pdf_btn.connect("clicked", lambda _: self._main._exporter.compile_typst_pdf())

        self._main._update_lect_label()
        GLib.timeout_add_seconds(86400, self._main._update_lect_label)
        self._main._recent_sec = Gio.Menu()
        self._main._rebuild_recent_menu()
        self._main._menu_btn = Gtk.MenuButton(icon_name="open-menu-symbolic", tooltip_text="Menu")
        hdr.pack_end(self._main._menu_btn)
        self._main._refresh_menu()

        _help_btn = Gtk.Button(icon_name="help-contents-symbolic",
                               tooltip_text="Quick help — what each part of the screen does")
        _help_btn.add_css_class("flat")
        _help_btn.connect("clicked", self._main._show_ui_help_popover)
        self._main._help_header_btn = _help_btn
        hdr.pack_end(_help_btn)

        self._main._preview_visible = False
        self._main._preview_scroll_poll_id = None
        self._main._preview_pending_id = None
        self._main._preview_compile_dirty = False  # new compile needed after current finishes
        self._main._preview_window_id = id(self._main)   # unique per-window for PDF path
        self._main._preview_mode = "bulletin"
        self._main._preview_update_mode = "on_save"  # "auto" | "on_save" | "manual"
        self._main._preview_paned_positioned = False
        self._main._preview_lbl = Gtk.Label(label="Preview")
        self._main._preview_lbl.set_use_markup(True)
        self._main._preview_btn = Gtk.Button(tooltip_text="Toggle live preview")
        self._main._preview_btn.set_child(self._main._preview_lbl)
        self._main._preview_btn.add_css_class("flat")
        self._main._preview_btn.connect("clicked", self._main._preview._toggle_preview_panel)
        hdr.pack_end(self._main._preview_btn)

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

        self._main._simple_status_btn, self._main._simple_status_lbl = _status_toggle_btn(
            "SIMPLE", "Simple mode — hides export, GitHub sync and other advanced options. Good for first-time use.")
        self._main._simple_status_btn.connect("clicked", self._main._on_simple_status_clicked)
        _left_box.append(self._main._simple_status_btn)

        self._main._gost_status_btn, self._main._gost_status_lbl = _status_toggle_btn(
            "GOST", "Switch UI font to GOST Type B — a Cyrillic engineering typeface. Toggle off to return to the system font.")
        self._main._gost_status_btn.connect("clicked", self._main._on_gost_status_clicked)
        _left_box.append(self._main._gost_status_btn)

        self._main._compact_status_btn, self._main._compact_status_lbl = _status_toggle_btn(
            "Compact", "Compact view — reduces spacing between service elements so more fit on screen at once")
        self._main._compact_status_btn.connect("clicked", self._main._on_compact_status_clicked)
        _left_box.append(self._main._compact_status_btn)

        self._main._dev_status_btn, self._main._dev_status_lbl = _status_toggle_btn(
            "Dev", "Developer mode — shows a 'Copy Typst source' button in the preview panel for debugging bulletin layout")
        self._main._dev_status_btn.connect("clicked", self._main._on_dev_status_clicked)
        self._main._dev_mode = False
        _left_box.append(self._main._dev_status_btn)

        self._main._typst_edit_btn, self._main._typst_edit_lbl = _status_toggle_btn(
            "Typst", "Switch the content editor to raw Typst source mode")
        self._main._typst_edit_btn.connect("clicked", self._main._on_typst_edit_clicked)
        self._main._typst_edit_btn.set_visible(False)
        self._main._typst_edit_active = False
        _left_box.append(self._main._typst_edit_btn)

        self._main._preamble_btn, self._main._preamble_lbl = _status_toggle_btn(
            "Template", "Document template — set fonts, margins, and layout for generated PDFs")
        self._main._preamble_btn.connect("clicked", self._main._on_preamble_clicked)
        self._main._preamble_active = False
        _left_box.append(self._main._preamble_btn)

        status_bar.append(_left_box)

        # Centre: single events popover button (replaces prev/dot/next layout)
        _left_spacer = Gtk.Box(); _left_spacer.set_hexpand(True)
        status_bar.append(_left_spacer)

        self._main._events_btn_lbl = Gtk.Label()
        self._main._events_btn_lbl.add_css_class("caption")
        self._main._events_popover_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self._main._events_popover_box.set_margin_start(10); self._main._events_popover_box.set_margin_end(10)
        self._main._events_popover_box.set_margin_top(8); self._main._events_popover_box.set_margin_bottom(8)
        self._main._events_popover_box.set_size_request(280, -1)
        _evpop = Gtk.Popover()
        _evpop.set_child(self._main._events_popover_box)
        self._main._events_btn = Gtk.MenuButton()
        self._main._events_btn.set_child(self._main._events_btn_lbl)
        self._main._events_btn.set_popover(_evpop)
        self._main._events_btn.add_css_class("flat")
        self._main._events_btn.set_visible(False)
        status_bar.append(self._main._events_btn)

        _right_spacer = Gtk.Box(); _right_spacer.set_hexpand(True)
        status_bar.append(_right_spacer)

        # Right group — aligned right, no separators
        _right_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        _right_box.set_halign(Gtk.Align.END)
        _right_box.set_margin_end(2)

        # Word count chip — updates as content changes
        self._main._word_count_lbl = Gtk.Label()
        self._main._word_count_lbl.add_css_class("caption")
        self._main._word_count_lbl.add_css_class("metric-pill")
        self._main._word_count_lbl.set_margin_start(4); self._main._word_count_lbl.set_margin_end(6)
        self._main._word_count_lbl.set_visible(False)
        self._main._word_count_lbl.set_tooltip_text("Approximate spoken word count and reading time")
        _right_box.append(self._main._word_count_lbl)

        # Save-state chip — shows "● Unsaved" when modified, hidden when saved
        self._main._save_state_lbl = Gtk.Label()
        self._main._save_state_lbl.add_css_class("caption")
        self._main._save_state_lbl.set_margin_start(4); self._main._save_state_lbl.set_margin_end(6)
        self._main._save_state_lbl.set_visible(False)
        self._main._save_state_lbl.set_tooltip_text("Unsaved changes — press Ctrl+S to save")
        _right_box.append(self._main._save_state_lbl)

        self._main._focus_status_btn, self._main._focus_status_lbl = _status_toggle_btn(
            "Focus", "Focus mode — hides the element palette and list so you can concentrate on the notes editor")
        self._main._focus_status_btn.connect("clicked", lambda _: self._main._toggle_focus_mode())
        _right_box.append(self._main._focus_status_btn)

        _git_btn = Gtk.Button(label="Git")
        _git_btn.add_css_class("flat"); _git_btn.add_css_class("caption")
        _git_btn_lbl = _git_btn.get_child()
        if _git_btn_lbl:
            _git_btn_lbl.set_margin_top(1); _git_btn_lbl.set_margin_bottom(1)
        _git_btn.set_tooltip_text("Commit and push to GitHub (Ctrl+Shift+G) — pull --rebase first")
        _git_btn.set_margin_start(1); _git_btn.set_margin_end(1)
        _git_btn.connect("clicked", lambda _: self._main.git_push())
        self._main._git_btn = _git_btn
        _right_box.append(_git_btn)

        ver_btn = Gtk.Button(label=f"v{APP_VERSION}")
        ver_btn.add_css_class("flat"); ver_btn.add_css_class("dim-label"); ver_btn.add_css_class("caption")
        ver_btn.set_margin_end(4); ver_btn.set_tooltip_text("View changelog")
        ver_btn.connect("clicked", lambda _: self._main.open_help("changelog"))
        _right_box.append(ver_btn)

        status_bar.append(_right_box)

        tv.add_bottom_bar(status_bar)

        # GOST CSS provider (priority above application so it overrides theme fonts)
        self._main._gost_css = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), self._main._gost_css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)

        self._main._toast_overlay = Adw.ToastOverlay()

        # Outer paned: palette | content
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_shrink_start_child(True); paned.set_shrink_end_child(False)
        paned.set_start_child(self._main._palette._build_palette_panel())
        self._main._palette_paned = paned
        self._main._palette_visible = False
        GLib.idle_add(lambda: paned.set_position(0))

        # Main stack: order panel or preamble editor
        self._main._main_stack = Gtk.Stack()
        self._main._main_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._main._main_stack.set_transition_duration(120)
        self._main._main_stack.add_named(self._main._order._build_order_panel(), "order")
        self._main._main_stack.add_named(self._main._preamble._build_preamble_panel(), "preamble")

        # Inner paned: order/preamble stack | bulletin preview (preview hidden by default)
        self._main._preview_panel = self._main._preview._build_preview_panel()
        self._main._preview_panel.set_visible(False)
        self._main._preview_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self._main._preview_paned.set_shrink_start_child(False)
        self._main._preview_paned.set_shrink_end_child(False)
        self._main._preview_paned.set_start_child(self._main._main_stack)
        self._main._preview_paned.set_end_child(self._main._preview_panel)
        paned.set_end_child(self._main._preview_paned)

        self._main._toast_overlay.set_child(paned)
        tv.set_content(self._main._toast_overlay)
        self._main.set_content(tv)

        # Per-season reading chip tint — updated whenever the liturgical date changes
        self._main._reading_chip_css = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), self._main._reading_chip_css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self._main._apply_simple_mode()
        self._main._apply_gost_mode()
