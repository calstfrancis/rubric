"""HymnLookupPanel — hymn number lookup, title/theme search, and injection for Rubric.

Owns the unified hymn lookup/search popover: number-based lookup against
Rubric's own hymn database, adding a title the database doesn't have yet, the
title search, theme-based browsing, and injecting a chosen hymn line into the
currently selected service item. Constructed with a reference to the
MainWindow instance it serves, the same composition pattern used by
BulletinExporter, BulletinPreview, and PreamblePanel.

Lookup is a local database read, so it is synchronous. It used to be an async
request to Hymnary.org, which meant the target element had to be captured when
the lookup was fired and re-checked when the reply arrived, in case the user
had selected something else or deleted it in the meantime. None of that is
needed now — the title is on screen before the click finishes.
"""

from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

from rubric_package.models.service import ServiceItem

try:
    from hymn_lookup import (
        lookup_hymn, parse_hymn_ref, search_hymns, remember_hymn,
        is_in_range, hymn_range, hymnal_name,
    )
    _HYMN_OK = True
except ImportError:
    _HYMN_OK = False
    def search_hymns(q): return []

try:
    from hymn_suggestions import (
        get_theme_names as _get_theme_names,
        get_theme_hymns as _get_theme_hymns,
    )
except (ImportError, FileNotFoundError):
    def _get_theme_names(): return []
    def _get_theme_hymns(t): return []


class HymnLookupPanel:
    """Owns the hymn lookup/search/theme popover and injecting results into the order."""

    def __init__(self, main_window):
        self._main = main_window

    def _do_hymn_lookup(self):
        if not _HYMN_OK:
            self._main.hymn_status.set_label("hymn_lookup.py not found")
            return
        text = self._main.hymn_entry.get_text().strip()
        if not text:
            return
        result = parse_hymn_ref(text)
        if not result:
            self._main.hymn_status.set_label("Format: VU 16  MV 120  LUS 5")
            self._hide_manual_entry()
            return
        prefix, number = result
        if not is_in_range(prefix, number):
            top = hymn_range(prefix)
            self._main.hymn_status.set_label(
                f"{hymnal_name(prefix)} only goes up to {top}")
            self._hide_manual_entry()
            return

        title = lookup_hymn(prefix, number)
        if title is None:
            # Not an error — Rubric simply doesn't have this one yet. Typing it
            # in is the way titles get added now that there is nothing to fetch
            # from, and it is kept for good.
            self._main.hymn_status.set_label(
                f"{prefix} {number} isn't in the hymn database yet — add its title:")
            self._main._hymn_manual_box.set_visible(True)
            self._main._hymn_manual_entry.grab_focus()
            self._main._hymn_manual_ref = (prefix, number)
            return

        self._hide_manual_entry()
        hymn_line = f"{prefix} {number} — {title}"
        self._main.hymn_status.set_label(hymn_line)
        self._insert_hymn_into_selection(hymn_line)

    def _hide_manual_entry(self):
        if hasattr(self._main, "_hymn_manual_box"):
            self._main._hymn_manual_box.set_visible(False)
            self._main._hymn_manual_entry.set_text("")

    def _save_manual_hymn(self):
        title = self._main._hymn_manual_entry.get_text().strip()
        if not title:
            return
        ref = getattr(self._main, "_hymn_manual_ref", None)
        if not ref:
            return
        prefix, number = ref
        # Stored before it is inserted, so the title survives even if no element
        # is selected to receive it — and shows up in the By Title search after.
        remember_hymn(prefix, number, title)
        hymn_line = f"{prefix} {number} — {title}"
        self._main.hymn_status.set_label(hymn_line)
        self._hide_manual_entry()
        self._insert_hymn_into_selection(hymn_line)

    def _insert_hymn_into_selection(self, hymn_line: str):
        """Prepend a hymn line to the selected element, if one is selected."""
        idx = self._main._selected_index()
        if not (0 <= idx < len(self._main.service_entries)):
            return
        entry = self._main.service_entries[idx]
        if not isinstance(entry, ServiceItem):
            return
        self._main._push_undo()
        entry.prepend_text(hymn_line)
        self._main._content_widget.set_blocks(entry.content)
        row = self._main._find_row_for_index(idx)
        if isinstance(row, Adw.ActionRow):
            preview = (self._main._note_preview(entry.content_plain)
                       or self._main._scripture_inline_preview(entry.name))
            sub = (f"{entry.leader} · {preview}" if entry.leader and preview
                   else (entry.leader or preview))
            row.set_subtitle(sub)
        self._main._mark_modified()

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

        self._main.hymn_entry = Gtk.Entry()
        self._main.hymn_entry.set_placeholder_text("VU 16")
        self._main.hymn_entry.set_width_chars(9)
        self._main.hymn_entry.set_hexpand(True)
        self._main.hymn_entry.connect("activate", lambda _: self._do_hymn_lookup())
        lookup_row.append(self._main.hymn_entry)

        lookup_btn = Gtk.Button(label="Look up")
        lookup_btn.add_css_class("suggested-action")
        lookup_btn.connect("clicked", lambda _: self._do_hymn_lookup())
        lookup_row.append(lookup_btn)
        lookup_page.append(lookup_row)

        self._main.hymn_status = Gtk.Label()
        self._main.hymn_status.add_css_class("dim-label"); self._main.hymn_status.add_css_class("caption")
        self._main.hymn_status.set_wrap(True); self._main.hymn_status.set_xalign(0)
        self._main.hymn_status.set_margin_start(10); self._main.hymn_status.set_margin_end(10)
        self._main.hymn_status.set_margin_bottom(4)
        lookup_page.append(self._main.hymn_status)

        # Manual title entry — shown when lookup fails or user wants to add directly
        manual_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        manual_box.set_margin_start(10); manual_box.set_margin_end(10)
        manual_box.set_margin_bottom(10)
        manual_box.set_visible(False)
        self._main._hymn_manual_box = manual_box

        self._main._hymn_manual_entry = Gtk.Entry()
        self._main._hymn_manual_entry.set_placeholder_text("Enter title from your hymnal…")
        self._main._hymn_manual_entry.set_hexpand(True)
        self._main._hymn_manual_entry.connect("activate", lambda _: self._save_manual_hymn())
        manual_box.append(self._main._hymn_manual_entry)

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
        self._main._hymn_search_list = Gtk.ListBox()
        self._main._hymn_search_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self._main._hymn_search_list.add_css_class("boxed-list")
        self._main._hymn_search_list.set_margin_start(8); self._main._hymn_search_list.set_margin_end(8)
        self._main._hymn_search_list.set_margin_bottom(4)
        scroll.set_child(self._main._hymn_search_list)
        title_page.append(scroll)

        hint = Gtk.Label(label="Searches the hymn database that ships with Rubric, plus any titles you have added. Use the Lookup tab to add one it doesn't have.")
        hint.add_css_class("caption"); hint.add_css_class("dim-label")
        hint.set_wrap(True); hint.set_xalign(0)
        hint.set_margin_start(8); hint.set_margin_end(8); hint.set_margin_bottom(8)
        title_page.append(hint)

        stack.add_titled(title_page, "search", "By Title")

        # ── By Theme page ─────────────────────────────────────────────────────
        theme_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Flow of theme chips — no scroll, let it expand naturally
        self._main._theme_flow = Gtk.FlowBox()
        self._main._theme_flow.set_max_children_per_line(3)
        self._main._theme_flow.set_min_children_per_line(2)
        self._main._theme_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self._main._theme_flow.set_homogeneous(True)
        self._main._theme_flow.set_row_spacing(4); self._main._theme_flow.set_column_spacing(4)
        self._main._theme_flow.set_margin_start(8); self._main._theme_flow.set_margin_end(8)
        self._main._theme_flow.set_margin_top(8); self._main._theme_flow.set_margin_bottom(6)
        for name in _get_theme_names():
            btn = Gtk.ToggleButton(label=name)
            btn.add_css_class("flat")
            btn.connect("toggled", lambda b, t=name: self._on_theme_chip_clicked(b, t))
            self._main._theme_flow.append(btn)
        theme_page.append(self._main._theme_flow)

        theme_page.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # Hymns for selected theme
        theme_scroll = Gtk.ScrolledWindow()
        theme_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        theme_scroll.set_min_content_height(180); theme_scroll.set_max_content_height(320)
        self._main._theme_hymn_list = Gtk.ListBox()
        self._main._theme_hymn_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self._main._theme_hymn_list.add_css_class("boxed-list")
        self._main._theme_hymn_list.set_margin_start(8); self._main._theme_hymn_list.set_margin_end(8)
        self._main._theme_hymn_list.set_margin_top(6); self._main._theme_hymn_list.set_margin_bottom(8)

        # Placeholder row (shown until a theme is selected)
        self._main._theme_placeholder = Gtk.ListBoxRow()
        self._main._theme_placeholder.set_activatable(False)
        ph_lbl = Gtk.Label(label="Select a theme above")
        ph_lbl.add_css_class("dim-label"); ph_lbl.add_css_class("caption")
        ph_lbl.set_margin_top(16); ph_lbl.set_margin_bottom(16)
        self._main._theme_placeholder.set_child(ph_lbl)
        self._main._theme_hymn_list.append(self._main._theme_placeholder)

        theme_scroll.set_child(self._main._theme_hymn_list)
        theme_page.append(theme_scroll)

        stack.add_titled(theme_page, "themes", "By Theme")

        self._main._hymn_search_entry = se
        se.connect("search-changed", lambda e: self._on_hymn_search_changed(e.get_text().strip()))
        pop.set_child(outer)
        return pop

    def _on_hymn_search_changed(self, query: str):
        while self._main._hymn_search_list.get_first_child():
            self._main._hymn_search_list.remove(self._main._hymn_search_list.get_first_child())
        results = search_hymns(query) if len(query) >= 2 else search_hymns("")
        if not results:
            row = Gtk.ListBoxRow(); row.set_activatable(False)
            lbl = Gtk.Label(label="No matching hymns — use the Lookup tab to add one by number")
            lbl.add_css_class("dim-label"); lbl.add_css_class("caption")
            lbl.set_margin_top(8); lbl.set_margin_bottom(8)
            row.set_child(lbl); self._main._hymn_search_list.append(row)
            return
        for r in results:
            ref = f"{r['book']} {r['number']}"
            line = f"{ref} — {r['title']}"
            row = Adw.ActionRow(title=r["title"], subtitle=ref)
            row.set_activatable(True)
            row.connect("activated", lambda _r, l=line: self._inject_hymn_line(l))
            self._main._hymn_search_list.append(row)

    def _on_theme_chip_clicked(self, btn: Gtk.ToggleButton, theme: str):
        if not btn.get_active():
            # Being untoggled — clear list
            self._main._theme_selected_btn = None
            while self._main._theme_hymn_list.get_first_child():
                self._main._theme_hymn_list.remove(self._main._theme_hymn_list.get_first_child())
            self._main._theme_hymn_list.append(self._main._theme_placeholder)
            return

        # Untoggle previous selection
        if self._main._theme_selected_btn and self._main._theme_selected_btn is not btn:
            self._main._theme_selected_btn.set_active(False)
        self._main._theme_selected_btn = btn

        while self._main._theme_hymn_list.get_first_child():
            self._main._theme_hymn_list.remove(self._main._theme_hymn_list.get_first_child())

        hymns = _get_theme_hymns(theme)
        if not hymns:
            row = Gtk.ListBoxRow(); row.set_activatable(False)
            lbl = Gtk.Label(label="No hymns found for this theme")
            lbl.add_css_class("dim-label"); lbl.add_css_class("caption")
            lbl.set_margin_top(8); lbl.set_margin_bottom(8)
            row.set_child(lbl); self._main._theme_hymn_list.append(row)
            return
        for prefix, number, title in hymns:
            ref = f"{prefix} {number}"
            line = f"{ref} — {title}"
            row = Adw.ActionRow(title=title, subtitle=ref)
            row.set_activatable(True)
            row.connect("activated", lambda _r, l=line: self._inject_hymn_line(l))
            self._main._theme_hymn_list.append(row)

    def _inject_hymn_line(self, hymn_line: str):
        """Add a hymn picked from the By Title or By Theme lists."""
        self._main._hymn_search_pop.popdown()
        # Shares _insert_hymn_into_selection with the Lookup tab, so all three
        # routes push undo and refresh the row the same way. This one used to
        # have its own copy that skipped the undo stack.
        self._insert_hymn_into_selection(hymn_line)
