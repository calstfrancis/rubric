"""OrderPanel — service-order editing UI for Rubric.

Owns the readings card, the order/notes horizontal split (listbox/notebook
view stack, button bar, focus banner), the combined per-item toolbar
(leader/duration/bulletin/icon row + scripture/hymn/snippet row), and the
hymn-suggestions strip. Constructed with a reference to the MainWindow
instance it serves, the same composition pattern used by BulletinExporter,
BulletinPreview, PreamblePanel, and HymnLookupPanel.
"""

from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gdk

from rubric_package.models.config import config
from rubric_package.views.element_content import ElementContentWidget


class OrderPanel:
    """Builds and owns the service order + notes editing panel."""

    def __init__(self, main_window):
        self._main = main_window

    def _build_order_panel(self):
        # Outer box holds everything
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # ── Readings card (date-dependent, shown when date is set) ────────────
        self._main.readings_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._main.readings_card.set_margin_start(12); self._main.readings_card.set_margin_end(12)
        self._main.readings_card.set_margin_top(6); self._main.readings_card.set_margin_bottom(6)
        self._main.readings_card.add_css_class("card"); self._main.readings_card.set_visible(False)

        self._main._colour_bar = Gtk.DrawingArea()
        self._main._colour_bar.set_size_request(-1, 8)
        self._main._colour_bar.set_draw_func(self._main._draw_colour_bar)
        self._main.readings_card.append(self._main._colour_bar)

        # Single row: ● Season  Year  |  First Reading · Psalm · Epistle · Gospel
        rcl_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        rcl_row.set_margin_start(8); rcl_row.set_margin_end(8)
        rcl_row.set_margin_top(5); rcl_row.set_margin_bottom(5)

        # Season info (left side, fixed width so reading buttons get the rest)
        season_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        season_box.set_size_request(160, -1)
        self._main.season_dot = Gtk.Label(label="●"); self._main.season_dot.add_css_class("caption"); season_box.append(self._main.season_dot)
        self._main.season_label = Gtk.Label(); self._main.season_label.set_xalign(0)
        self._main.season_label.add_css_class("caption"); season_box.append(self._main.season_label)
        self._main.year_badge = Gtk.Label()  # kept for data, not displayed
        rcl_row.append(season_box)

        # Small vertical separator
        vsep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        vsep.set_margin_start(4); vsep.set_margin_end(4); rcl_row.append(vsep)

        # Reading chips — compact pill buttons, right-aligned
        self._main._reading_rows: dict[str, Gtk.Button] = {}
        self._main._reading_labels = {"ot": "First Reading", "psalm": "Psalm",
                                 "epistle": "Epistle",  "gospel": "Gospel"}
        self._main._reading_abbrs  = {"ot": "OT", "psalm": "Ps", "epistle": "Ep", "gospel": "Gos"}
        chips_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        chips_box.set_hexpand(True); chips_box.set_halign(Gtk.Align.END)
        for key in ("ot", "psalm", "epistle", "gospel"):
            btn = Gtk.Button(label=self._main._reading_abbrs[key])
            btn.add_css_class("pill"); btn.add_css_class("flat"); btn.add_css_class("reading-chip")
            btn.set_sensitive(False)
            btn.set_tooltip_text(self._main._reading_labels[key])
            btn.connect("clicked", lambda _b, k=key: self._main._on_reading_clicked(k))
            chips_box.append(btn)
            self._main._reading_rows[key] = btn
        rcl_row.append(chips_box)
        self._main.readings_card.append(rcl_row)

        # Observances now shown in the status bar centre — no in-card row needed

        # Weekday notice + Sunday stepper (shown when selected date is not Sunday/special)
        self._main._sunday_stepper = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._main._sunday_stepper.set_margin_start(8); self._main._sunday_stepper.set_margin_end(8)
        self._main._sunday_stepper.set_margin_top(0); self._main._sunday_stepper.set_margin_bottom(6)
        self._main._sunday_stepper.set_visible(False)
        self._main._sunday_stepper.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        sep2 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self._main.readings_card.append(sep2)
        self._main._sunday_sep = sep2

        step_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        step_box.set_margin_start(8); step_box.set_margin_end(8)
        step_box.set_margin_top(4); step_box.set_margin_bottom(6)
        step_box.set_visible(False)

        prev_btn = Gtk.Button(icon_name="go-previous-symbolic", tooltip_text="Previous Sunday")
        prev_btn.add_css_class("flat"); prev_btn.set_valign(Gtk.Align.CENTER)
        prev_btn.connect("clicked", lambda _: self._main._step_sunday(-1))
        step_box.append(prev_btn)

        self._main._sunday_lbl = Gtk.Label()
        self._main._sunday_lbl.add_css_class("caption"); self._main._sunday_lbl.add_css_class("dim-label")
        self._main._sunday_lbl.set_hexpand(True); self._main._sunday_lbl.set_xalign(0.5)
        step_box.append(self._main._sunday_lbl)

        next_btn = Gtk.Button(icon_name="go-next-symbolic", tooltip_text="Next Sunday")
        next_btn.add_css_class("flat"); next_btn.set_valign(Gtk.Align.CENTER)
        next_btn.connect("clicked", lambda _: self._main._step_sunday(1))
        step_box.append(next_btn)

        self._main.readings_card.append(step_box)
        self._main._sunday_step_box = step_box
        self._main._readings_sunday: "date | None" = None  # the Sunday whose readings are shown

        box.append(self._main.readings_card)
        self._main._current_readings = {}

        # ── Quick-start banner (hidden until first launch wizard activates it) ─
        box.append(self._main._build_quickstart_banner())

        # ── Planning notes (theology / metaphors / movement) ──────────────────
        box.append(self._main._build_planning_notes_area())

        # ── Horizontal split: order pane (left) | notes pane (right) ─────────
        self._main._order_hpaned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self._main._order_hpaned.set_shrink_start_child(False); self._main._order_hpaned.set_shrink_end_child(True)
        self._main._order_hpaned.set_position(config.ui_panes.get("order_hpaned", 220))
        self._main._order_hpaned.set_vexpand(True)

        # ── Order pane (left) ─────────────────────────────────────────────────
        order_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        order_box.set_size_request(160, -1)

        self._main._view_stack = Gtk.Stack(); self._main._view_stack.set_vexpand(True)

        self._main._flat_scroll = Gtk.ScrolledWindow()
        self._main._flat_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._main._flat_scroll.set_margin_start(12); self._main._flat_scroll.set_margin_end(12)
        self._main._flat_scroll.set_margin_top(8); self._main._flat_scroll.set_margin_bottom(6)
        self._main.order_listbox = Gtk.ListBox()
        self._main.order_listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._main.order_listbox.add_css_class("boxed-list")
        self._main.order_listbox.add_css_class("order-list")
        self._main.order_listbox.connect("row-selected", self._main._on_flat_row_selected)
        _list_key = Gtk.EventControllerKey()
        _list_key.connect("key-pressed", lambda ctrl, keyval, *_:
            (self._main.remove_item(), True)[1]
            if keyval == Gdk.KEY_Delete else False)
        self._main.order_listbox.add_controller(_list_key)
        placeholder = Adw.StatusPage(title="Service is empty",
            description="Double-click an element in the palette to add it, or drag elements here.",
            icon_name="rubric-symbolic")
        placeholder.set_vexpand(True)
        _new_svc_btn = Gtk.Button(label="Start with lectionary")
        _new_svc_btn.add_css_class("suggested-action")
        _new_svc_btn.set_halign(Gtk.Align.CENTER)
        _new_svc_btn.connect("clicked", lambda _: self._main._seed_lectionary_service_today())
        placeholder.set_child(_new_svc_btn)
        self._main.order_listbox.set_placeholder(placeholder)
        self._main._flat_scroll.set_child(self._main.order_listbox)
        self._main._view_stack.add_named(self._main._flat_scroll, "list")

        self._main._notebook = Gtk.Notebook()
        self._main._notebook.set_show_border(False); self._main._notebook.set_vexpand(True)
        self._main._notebook.set_scrollable(True)
        self._main._notebook.set_tab_pos(Gtk.PositionType.LEFT)
        self._main._notebook.set_margin_start(0); self._main._notebook.set_margin_end(8)
        self._main._notebook.set_margin_top(8); self._main._notebook.set_margin_bottom(6)
        self._main._view_stack.add_named(self._main._notebook, "tabs")

        self._main._view_stack.set_visible_child_name("tabs" if config.use_tabs else "list")

        # Season colour strip — 5px gradient bar at top of order panel
        self._main._order_season_strip = Gtk.DrawingArea()
        self._main._order_season_strip.set_size_request(-1, 5)
        def _draw_order_strip(_da, cr, w, _h):
            import cairo as _cairo
            r, g, b = self._main._colour_bar_rgb
            try:
                pat = _cairo.LinearGradient(0, 0, w, 0)
                pat.add_color_stop_rgba(0.0, r, g, b, 0.9)
                pat.add_color_stop_rgba(0.6, r, g, b, 0.65)
                pat.add_color_stop_rgba(1.0, r, g, b, 0.2)
                cr.set_source(pat)
            except Exception:
                cr.set_source_rgb(r, g, b)
            cr.paint()
        self._main._order_season_strip.set_draw_func(_draw_order_strip)
        order_box.append(self._main._order_season_strip)
        order_box.append(self._main._view_stack)

        # Time total bar
        self._main._time_bar = Gtk.Label()
        self._main._time_bar.set_xalign(1.0)
        self._main._time_bar.set_margin_start(12); self._main._time_bar.set_margin_end(12)
        self._main._time_bar.set_margin_top(2); self._main._time_bar.set_margin_bottom(0)
        self._main._time_bar.add_css_class("caption")
        self._main._time_bar.add_css_class("metric-pill")
        self._main._time_bar.set_visible(False)
        order_box.append(self._main._time_bar)

        # Order pane button bar
        bb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        bb.set_margin_start(8); bb.set_margin_end(8); bb.set_margin_top(4); bb.set_margin_bottom(8)
        add_elem_btn = Gtk.Button(label="Element", tooltip_text="Add custom element (Ctrl+Shift+N)")
        add_elem_btn.add_css_class("flat")
        add_elem_btn.connect("clicked", lambda _: self._main.add_custom()); bb.append(add_elem_btn)
        add_sec_btn = Gtk.Button(label="Section", tooltip_text="Add section divider (Ctrl+D)")
        add_sec_btn.add_css_class("flat")
        add_sec_btn.connect("clicked", lambda _: self._main.add_divider()); bb.append(add_sec_btn)
        sp = Gtk.Box(); sp.set_hexpand(True); bb.append(sp)
        for icon, tip, cb in [("go-up-symbolic","Move up (Ctrl+↑)",self._main.move_up),
                               ("go-down-symbolic","Move down (Ctrl+↓)",self._main.move_down)]:
            b = Gtk.Button(icon_name=icon, tooltip_text=tip); b.add_css_class("flat")
            b.connect("clicked", lambda _, f=cb: f()); bb.append(b)
        rm = Gtk.Button(icon_name="list-remove-symbolic", tooltip_text="Remove selected (Delete)")
        rm.add_css_class("destructive-action"); rm.connect("clicked", lambda _: self._main.remove_item()); bb.append(rm)
        order_box.append(bb)
        self._main._order_box = order_box
        self._main._order_hpaned.set_start_child(order_box)

        # ── Notes pane (right) ────────────────────────────────────────────────
        notes_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Focus mode banner — shown in F11 focus mode, hidden otherwise
        self._main._focus_banner = Gtk.Revealer()
        self._main._focus_banner.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self._main._focus_banner.set_transition_duration(180)
        focus_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        focus_bar.set_margin_start(12); focus_bar.set_margin_end(8)
        focus_bar.set_margin_top(6); focus_bar.set_margin_bottom(6)
        self._main._focus_elem_lbl = Gtk.Label()
        self._main._focus_elem_lbl.add_css_class("heading")
        self._main._focus_elem_lbl.set_hexpand(True); self._main._focus_elem_lbl.set_xalign(0)
        focus_bar.append(self._main._focus_elem_lbl)
        exit_focus_btn = Gtk.Button(label="Exit focus mode")
        exit_focus_btn.add_css_class("flat")
        exit_focus_btn.connect("clicked", lambda _: self._main._toggle_focus_mode())
        focus_bar.append(exit_focus_btn)
        self._main._focus_banner.set_child(focus_bar)
        self._main._focus_banner.set_reveal_child(False)
        notes_box.append(self._main._focus_banner)

        notes_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # ── Combined single-line item toolbar (revealed when item is selected) ─
        self._main.item_toolbar_revealer = Gtk.Revealer()
        self._main.item_toolbar_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self._main.item_toolbar_revealer.set_transition_duration(150)

        # ── Row 1: Leader name + Bulletin toggle (primary, always-visible) ──
        itb_rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        row1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row1.set_margin_start(12); row1.set_margin_end(12)
        row1.set_margin_top(8); row1.set_margin_bottom(4)

        ldr_lbl = Gtk.Label(label="Leader"); ldr_lbl.add_css_class("dim-label")
        row1.append(ldr_lbl)
        self._main.leader_entry = Gtk.Entry()
        self._main.leader_entry.set_placeholder_text("Name or role")
        self._main.leader_entry.set_hexpand(True)
        self._main.leader_entry.connect("changed", self._main._on_leader_changed)
        row1.append(self._main.leader_entry)

        dur_lbl = Gtk.Label(label="min"); dur_lbl.add_css_class("dim-label")
        dur_lbl.set_margin_start(6); row1.append(dur_lbl)
        dur_adj = Gtk.Adjustment(value=0, lower=0, upper=120, step_increment=1)
        self._main.duration_spin = Gtk.SpinButton(adjustment=dur_adj, numeric=True)
        self._main.duration_spin.set_width_chars(3)
        self._main.duration_spin.set_tooltip_text("Estimated duration in minutes (0 = unset)")
        self._main.duration_spin.connect("value-changed", self._main._on_duration_changed)
        row1.append(self._main.duration_spin)

        self._main._bulletin_heading_lbl = Gtk.Label(label="Bulletin")
        self._main._bulletin_heading_lbl.set_use_markup(True)
        self._main.bulletin_toggle = Gtk.Button(
            tooltip_text="Bulletin heading only — element title appears in the bulletin, body text omitted")
        self._main.bulletin_toggle.set_child(self._main._bulletin_heading_lbl)
        self._main.bulletin_toggle.add_css_class("flat")
        self._main._bulletin_heading_only_active = False
        self._main.bulletin_toggle.connect("clicked", self._main._on_bulletin_toggled)
        row1.append(self._main.bulletin_toggle)

        self._main.bulletin_summary_entry = Gtk.Entry()
        self._main.bulletin_summary_entry.set_placeholder_text("bulletin note…")
        self._main.bulletin_summary_entry.set_width_chars(18)
        self._main.bulletin_summary_entry.set_tooltip_text(
            "Short line shown in the bulletin instead of the full content. "
            "Leave empty to show full content.")
        self._main.bulletin_summary_entry.connect("changed", self._main._on_bulletin_summary_changed)
        row1.append(self._main.bulletin_summary_entry)

        icon_btn = Gtk.MenuButton(icon_name="preferences-desktop-wallpaper-symbolic",
                                  tooltip_text="Set icon for this element")
        icon_btn.add_css_class("flat")
        icon_btn.set_popover(self._main._build_icon_picker_popover())
        self._main._icon_menu_btn = icon_btn
        row1.append(icon_btn)
        itb_rows.append(row1)

        # ── Row 2: Scripture · Hymn (contextual) · Snippets / Reading ────
        row2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        row2.set_margin_start(12); row2.set_margin_end(12)
        row2.set_margin_top(0); row2.set_margin_bottom(8)

        scr_lbl = Gtk.Label(label="Scripture"); scr_lbl.add_css_class("dim-label")
        scr_lbl.set_margin_end(4); row2.append(scr_lbl)
        self._main.scripture_entry = Gtk.Entry()
        self._main.scripture_entry.set_placeholder_text("Ps 23")
        self._main.scripture_entry.set_width_chars(10)
        self._main.scripture_entry.connect("activate", lambda _: self._main._do_scripture_search())
        row2.append(self._main.scripture_entry)
        ss_fetch = Gtk.Button(icon_name="system-search-symbolic", tooltip_text="Fetch passage (Enter)")
        ss_fetch.add_css_class("flat")
        ss_fetch.connect("clicked", lambda _: self._main._do_scripture_search())
        row2.append(ss_fetch)

        # Hymn sub-segment — single button opens unified lookup/search popover
        sep_hymn = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        sep_hymn.set_margin_start(6); sep_hymn.set_margin_end(6); row2.append(sep_hymn)

        self._main._theme_selected_btn = None
        self._main._hymn_search_pop = self._main._hymn._build_hymn_search_popover()
        self._main._hymn_search_pop.connect("show", lambda _: self._main._hymn._on_hymn_search_changed(
            self._main._hymn_search_entry.get_text().strip() if hasattr(self._main, "_hymn_search_entry") else ""))
        hymn_menu_btn = Gtk.MenuButton(label="Hymn",
                                       tooltip_text="Look up or search hymns",
                                       popover=self._main._hymn_search_pop)
        hymn_menu_btn.add_css_class("flat")
        self._main._hymn_toolbar_widgets = [sep_hymn, hymn_menu_btn]
        row2.append(hymn_menu_btn)

        # Action buttons
        sep_act = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        sep_act.set_margin_start(6); sep_act.set_margin_end(2); row2.append(sep_act)
        self._main._snip_btn = Gtk.Button(label="Snippet", tooltip_text="Insert snippet (Ctrl+Shift+I)")
        self._main._snip_btn.add_css_class("flat")
        self._main._snip_btn.connect("clicked", lambda _: self._main.open_snippets()); row2.append(self._main._snip_btn)
        self._main._hymn_mode_btn = Gtk.ToggleButton(label="Hymn",
                                               tooltip_text="Toggle hymn search and suggestions for this element")
        self._main._hymn_mode_btn.add_css_class("flat")
        self._main._hymn_mode_btn.connect("toggled", self._main._on_hymn_mode_toggled)
        row2.append(self._main._hymn_mode_btn)
        itb_rows.append(row2)

        self._main.item_toolbar_revealer.set_child(itb_rows)
        notes_box.append(self._main.item_toolbar_revealer)
        self._main.hymn_revealer = self._main.item_toolbar_revealer
        self._main.leader_revealer = self._main.item_toolbar_revealer

        # Unified content editor (replaces the old 3-tab Leader/Bulletin/Prep stack)
        self._main._content_widget = ElementContentWidget()
        self._main._content_widget.set_vexpand(True)
        self._main._content_widget.set_on_changed(self._main._on_content_typst_changed)
        self._main._content_widget.set_on_rubric_changed(self._main._on_rubric_note_changed)
        notes_box.append(self._main._content_widget)

        # Scripture reference detection banner
        self._main._scripture_detect_rev = Gtk.Revealer()
        self._main._scripture_detect_rev.set_transition_type(Gtk.RevealerTransitionType.SLIDE_UP)
        self._main._scripture_detect_rev.set_transition_duration(150)
        sd_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        sd_bar.set_margin_start(12); sd_bar.set_margin_end(12)
        sd_bar.set_margin_top(4); sd_bar.set_margin_bottom(4)
        self._main._scripture_detect_lbl = Gtk.Label()
        self._main._scripture_detect_lbl.add_css_class("caption")
        self._main._scripture_detect_lbl.set_hexpand(True); self._main._scripture_detect_lbl.set_xalign(0)
        sd_bar.append(self._main._scripture_detect_lbl)
        self._main._scripture_fetch_btn = Gtk.Button(label="Fetch text")
        self._main._scripture_fetch_btn.add_css_class("flat"); self._main._scripture_fetch_btn.add_css_class("accent")
        self._main._scripture_fetch_btn.connect("clicked", self._main._on_scripture_banner_fetch)
        sd_bar.append(self._main._scripture_fetch_btn)
        sd_dismiss = Gtk.Button(icon_name="window-close-symbolic")
        sd_dismiss.add_css_class("flat")
        sd_dismiss.connect("clicked", lambda _: self._main._scripture_detect_rev.set_reveal_child(False))
        sd_bar.append(sd_dismiss)
        self._main._scripture_detect_rev.set_child(sd_bar)
        notes_box.append(self._main._scripture_detect_rev)

        self._main._order_hpaned.set_end_child(notes_box)
        box.append(self._main._order_hpaned)

        # Hymn suggestions strip — full width across order + notes panes
        self._main.sugg_revealer = Gtk.Revealer()
        self._main.sugg_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_UP)
        self._main.sugg_revealer.set_transition_duration(200)
        self._main._sugg_dismissed = False
        sugg_outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        sugg_outer.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        sugg_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self._main._sugg_chips_box = Gtk.FlowBox()
        self._main._sugg_chips_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self._main._sugg_chips_box.set_max_children_per_line(50)
        self._main._sugg_chips_box.set_min_children_per_line(1)
        self._main._sugg_chips_box.set_column_spacing(4); self._main._sugg_chips_box.set_row_spacing(4)
        self._main._sugg_chips_box.set_margin_start(10); self._main._sugg_chips_box.set_margin_end(6)
        self._main._sugg_chips_box.set_margin_bottom(6); self._main._sugg_chips_box.set_margin_top(6)
        self._main._sugg_chips_box.set_hexpand(True)
        sugg_close_btn = Gtk.Button(icon_name="window-close-symbolic",
                                    tooltip_text="Dismiss suggestions",
                                    valign=Gtk.Align.CENTER)
        sugg_close_btn.add_css_class("flat")
        sugg_close_btn.set_margin_end(6)
        def _dismiss_suggestions(_btn):
            self._main._sugg_dismissed = True
            self._main.sugg_revealer.set_reveal_child(False)
        sugg_close_btn.connect("clicked", _dismiss_suggestions)
        sugg_row.append(self._main._sugg_chips_box)
        sugg_row.append(sugg_close_btn)
        sugg_outer.append(sugg_row)
        self._main.sugg_revealer.set_child(sugg_outer)
        box.append(self._main.sugg_revealer)

        return box
