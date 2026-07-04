"""ServicesWindow — unified Services window: Planner, Element Library, and Past Liturgies tabs."""

from __future__ import annotations

import json
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Pango

from rcl_data import get_liturgical_info
from rubric_package.models.config import config
from rubric_package.models.service import ServiceItem
from rubric_package.utils.typst import strip_typst_plain


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
        today_btn = Gtk.Button(label="Today", tooltip_text="Jump to this Sunday (Ctrl+T)")
        today_btn.add_css_class("flat")
        today_btn.connect("clicked", lambda _: self._planner_jump_to_today())
        top.append(today_btn)
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
        self._planner_cal_scroll = cal_scroll
        self._planner_cal_box = Gtk.ListBox()
        self._planner_cal_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self._planner_cal_box.add_css_class("boxed-list")
        self._planner_cal_box.set_margin_start(12); self._planner_cal_box.set_margin_end(12)
        self._planner_cal_box.set_margin_top(8); self._planner_cal_box.set_margin_bottom(12)
        cal_scroll.set_child(self._planner_cal_box)
        self._planner_view_stack.add_named(cal_scroll, "calendar")
        self._planner_today_row: "Gtk.Widget | None" = None

        def on_view_toggle(btn):
            if btn.get_active():
                self._planner_view_stack.set_visible_child_name(
                    "list" if btn is self._planner_list_btn else "calendar")
        self._planner_list_btn.connect("toggled", on_view_toggle)
        self._planner_cal_btn.connect("toggled",  on_view_toggle)

        box.append(self._planner_view_stack)
        return box

    def _planner_jump_to_today(self):
        """Switch to calendar view and scroll to this Sunday's row."""
        self._planner_cal_btn.set_active(True)
        self._planner_view_stack.set_visible_child_name("calendar")
        row = getattr(self, "_planner_today_row", None)
        if row:
            GLib.idle_add(row.grab_focus)

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
                        json.dumps(data, indent=2, ensure_ascii=False),
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

            if sunday == last_sunday:
                self._planner_today_row = row

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
        outer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)

        sidebar_scroll = Gtk.ScrolledWindow()
        sidebar_scroll.set_size_request(170, -1)
        sidebar_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._arch_filter_list = Gtk.ListBox()
        self._arch_filter_list.add_css_class("navigation-sidebar")
        self._arch_filter_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._arch_filter_list.connect("row-selected", self._on_arch_filter_selected)
        sidebar_scroll.set_child(self._arch_filter_list)
        outer.append(sidebar_scroll)
        outer.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.set_hexpand(True)
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
        outer.append(box)

        self._arch_filter = ("all", None)
        self._populate_arch_filter_list()
        return outer

    def _populate_arch_filter_list(self):
        lb = self._arch_filter_list
        while lb.get_first_child(): lb.remove(lb.get_first_child())
        try:
            from rubric_package.db import service_meta_all_tags, service_meta_all_series
        except ImportError:
            service_meta_all_tags = service_meta_all_series = lambda: []

        def add_row(kind, value, label, icon=None):
            row = Gtk.ListBoxRow()
            rbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            rbox.set_margin_start(10); rbox.set_margin_end(10)
            rbox.set_margin_top(6); rbox.set_margin_bottom(6)
            if icon:
                rbox.append(Gtk.Image.new_from_icon_name(icon))
            lbl = Gtk.Label(label=label); lbl.set_xalign(0); lbl.set_hexpand(True)
            lbl.set_ellipsize(Pango.EllipsizeMode.END)
            rbox.append(lbl)
            row.set_child(rbox); row._filter = (kind, value)
            lb.append(row)
            return row

        def add_header(text):
            row = Gtk.ListBoxRow(); row.set_selectable(False); row.set_activatable(False)
            lbl = Gtk.Label(label=text); lbl.add_css_class("caption"); lbl.add_css_class("dim-label")
            lbl.set_xalign(0); lbl.set_margin_start(10); lbl.set_margin_top(10); lbl.set_margin_bottom(2)
            row.set_child(lbl); row._filter = None
            lb.append(row)

        first = add_row("all", None, "All services", "view-list-symbolic")
        add_row("pinned", None, "Pinned", "starred-symbolic")
        add_row("untagged", None, "Untagged", "window-close-symbolic")

        series = service_meta_all_series()
        if series:
            add_header("SERIES")
            for name, count in series:
                add_row("series", name, f"{name} ({count})")

        tags = service_meta_all_tags()
        if tags:
            add_header("TAGS")
            for name, count in tags:
                add_row("tag", name, f"{name} ({count})")

        lb.select_row(first)

    def _on_arch_filter_selected(self, _lb, row):
        if row is None or getattr(row, "_filter", None) is None:
            return
        self._arch_filter = row._filter
        self._arch_rebuild(self._arch_search)

    def _stable_tag_color(self, name: str) -> str:
        from rubric_package.utils.colors import SECTION_COLORS
        h = 0
        for b in name.encode("utf-8"):
            h = (h * 31 + b) & 0xFFFFFFFF
        return SECTION_COLORS[h % len(SECTION_COLORS)]

    def _make_pill(self, text: str) -> Gtk.Widget:
        color = self._stable_tag_color(text)
        lbl = Gtk.Label()
        lbl.set_markup(f'<span color="{color}">●</span> '
                        f'<span size="small">{GLib.markup_escape_text(text)}</span>')
        lbl.set_xalign(0)
        return lbl

    def _on_toggle_pin(self, path: str, pinned: bool):
        try:
            p = Path(path)
            data = json.loads(p.read_text(encoding="utf-8"))
            data["pinned"] = pinned
            p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            if self._main.current_file and str(Path(self._main.current_file)) == str(p):
                self._main.service_pinned = pinned
                if hasattr(self._main, "_pinned_toggle"):
                    self._main._pinned_toggle.set_active(pinned)
            from rubric_package.db import service_meta_update
            from rubric_package.utils.typst import notes_preview
            service_meta_update(str(p), data.get("title", ""), data.get("date", ""),
                                 list(data.get("tags", []) or []), data.get("series", "") or "",
                                 pinned, notes_preview(data.get("planning_notes", "")), p.stat().st_mtime)
        except Exception as e:
            self._show_toast(f"Couldn't update pin: {e}"); return
        self._populate_arch_filter_list()
        self._arch_rebuild(self._arch_search)

    def _arch_rebuild(self, query: str):
        self._arch_search = query
        while self._arch_list.get_first_child(): self._arch_list.remove(self._arch_list.get_first_child())

        try:
            from rubric_package.db import service_meta_all, element_for_service, element_services
        except ImportError:
            self._arch_list.append(self._status_row("Database not available")); return

        by_path = {s["path"]: s for s in service_meta_all()}
        for legacy in element_services(limit=500):
            by_path.setdefault(legacy["service_path"], {
                "path": legacy["service_path"], "title": legacy["service_title"],
                "date": legacy["service_date"], "tags": [], "series": "",
                "pinned": False, "notes_preview": "",
            })
        services = list(by_path.values())

        if not services:
            self._arch_list.append(self._status_row(
                "No services in library yet — save a service to add it here")); return

        kind, value = getattr(self, "_arch_filter", ("all", None))
        if kind == "pinned":
            services = [s for s in services if s.get("pinned")]
        elif kind == "untagged":
            services = [s for s in services if not s.get("tags")]
        elif kind == "series":
            services = [s for s in services if s.get("series") == value]
        elif kind == "tag":
            services = [s for s in services if value in (s.get("tags") or [])]

        # Show recently opened files at the top of the default, unfiltered view
        if not query and kind == "all":
            recent = [p for p in config.recent_files if Path(p).exists()]
            if recent:
                hdr = Gtk.ListBoxRow(); hdr.set_selectable(False); hdr.set_activatable(False)
                lbl = Gtk.Label(label="Recently opened"); lbl.add_css_class("caption")
                lbl.add_css_class("dim-label"); lbl.set_xalign(0)
                lbl.set_margin_start(12); lbl.set_margin_top(8); lbl.set_margin_bottom(4)
                hdr.set_child(lbl); self._arch_list.append(hdr)
                for rpath in recent[:8]:
                    p = Path(rpath)
                    row = Adw.ActionRow(title=p.stem, subtitle=str(p.parent))
                    row.set_activatable(True)
                    row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
                    row.connect("activated", lambda _r, _p=rpath: self._open_service(_p))
                    self._arch_list.append(row)
                self._arch_list.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        if query:
            filtered = []
            for svc in services:
                title  = (svc.get("title") or "").lower()
                date   = (svc.get("date") or "").lower()
                series_v = (svc.get("series") or "").lower()
                tags_v = " ".join(svc.get("tags") or []).lower()
                notes_v = (svc.get("notes_preview") or "").lower()
                if (query in title or query in date or query in series_v
                        or query in tags_v or query in notes_v):
                    filtered.append(svc)
                else:
                    elems = element_for_service(svc["path"])
                    if any(query in (e.get("name","")).lower() or query in (e.get("note","")).lower()
                           for e in elems):
                        filtered.append(svc)
            services = filtered
            if not services: self._arch_list.append(self._status_row("No matches found")); return

        services.sort(key=lambda s: s.get("date") or "", reverse=True)

        for svc in services:
            self._arch_list.append(self._arch_svc_row(svc))
            if svc["path"] in self._arch_expanded:
                self._arch_list.append(self._arch_afterservice_row(svc["path"]))
                try: elems = element_for_service(svc["path"])
                except Exception: elems = []
                cur_section = ""
                for elem in elems:
                    if elem.get("section") and elem["section"] != cur_section:
                        cur_section = elem["section"]
                        self._arch_list.append(self._arch_section_label(cur_section))
                    self._arch_list.append(self._arch_elem_row(elem))

    def _arch_svc_row(self, svc: dict) -> Gtk.ListBoxRow:
        path = svc["path"]; expanded = path in self._arch_expanded
        row = Gtk.ListBoxRow(); row._is_service = True; row._svc = svc
        row.set_activatable(True)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header.set_margin_start(12); header.set_margin_end(8)
        header.set_margin_top(10); header.set_margin_bottom(10)
        header.append(Gtk.Label(label="▼" if expanded else "▶", css_classes=["caption", "dim-label"]))

        pinned = bool(svc.get("pinned"))
        pin_btn = Gtk.ToggleButton(icon_name="starred-symbolic" if pinned else "non-starred-symbolic")
        pin_btn.set_active(pinned)
        pin_btn.add_css_class("flat"); pin_btn.set_valign(Gtk.Align.CENTER)
        pin_btn.set_tooltip_text("Pinned in library — click to unpin" if pinned else "Pin in library")
        pin_btn.connect("toggled", lambda b, p=path: self._on_toggle_pin(p, b.get_active()))
        header.append(pin_btn)

        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1); info.set_hexpand(True)
        title_lbl = Gtk.Label(label=svc.get("title") or Path(path).stem)
        title_lbl.set_xalign(0); title_lbl.add_css_class("heading"); title_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        info.append(title_lbl)
        date_lbl = Gtk.Label(label=svc.get("date") or "No date")
        date_lbl.set_xalign(0); date_lbl.add_css_class("caption"); date_lbl.add_css_class("dim-label")
        info.append(date_lbl)

        pills = ([svc["series"]] if svc.get("series") else []) + list(svc.get("tags") or [])
        if pills:
            pill_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            pill_row.set_margin_top(3)
            for text in pills:
                pill_row.append(self._make_pill(text))
            info.append(pill_row)

        if svc.get("notes_preview"):
            note_lbl = Gtk.Label(label=svc["notes_preview"])
            note_lbl.set_xalign(0); note_lbl.set_wrap(True)
            note_lbl.set_ellipsize(Pango.EllipsizeMode.END); note_lbl.set_lines(1)
            note_lbl.add_css_class("caption"); note_lbl.add_css_class("dim-label")
            note_lbl.set_margin_top(2)
            info.append(note_lbl)

        header.append(info)
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

    def _arch_afterservice_row(self, path: str) -> Gtk.ListBoxRow:
        """Attendance + debrief notes — filled in after Sunday, saved to the file."""
        row = Gtk.ListBoxRow(); row.set_activatable(False)
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception as e:
            lbl = Gtk.Label(label=f"Couldn't read file: {e}")
            lbl.set_margin_start(28); lbl.set_margin_top(6); lbl.set_margin_bottom(6)
            row.set_child(lbl); return row

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_margin_start(28); box.set_margin_end(12)
        box.set_margin_top(6); box.set_margin_bottom(10)

        hdr_lbl = Gtk.Label(label="After service"); hdr_lbl.add_css_class("heading")
        hdr_lbl.set_xalign(0); box.append(hdr_lbl)

        att_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        att_lbl = Gtk.Label(label="Attendance"); att_lbl.set_xalign(0); att_lbl.set_hexpand(True)
        att_row.append(att_lbl)
        att_adj = Gtk.Adjustment(value=data.get("attendance", 0), lower=0, upper=9999, step_increment=1)
        att_spin = Gtk.SpinButton(adjustment=att_adj, numeric=True)
        att_spin.set_width_chars(5); att_spin.set_valign(Gtk.Align.CENTER)
        att_row.append(att_spin)
        box.append(att_row)

        deb_lbl = Gtk.Label(label="Debrief notes"); deb_lbl.set_xalign(0)
        deb_lbl.add_css_class("caption"); deb_lbl.add_css_class("dim-label")
        deb_lbl.set_margin_top(2); box.append(deb_lbl)

        deb_scroll = Gtk.ScrolledWindow()
        deb_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        deb_scroll.set_min_content_height(64)
        deb_tv = Gtk.TextView(); deb_tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        deb_tv.add_css_class("card")
        deb_tv.set_top_margin(6); deb_tv.set_bottom_margin(6)
        deb_tv.set_left_margin(8); deb_tv.set_right_margin(8)
        deb_tv.get_buffer().set_text(data.get("debrief", ""), -1)
        deb_scroll.set_child(deb_tv)
        box.append(deb_scroll)

        save_btn = Gtk.Button(label="Save notes")
        save_btn.add_css_class("flat"); save_btn.set_halign(Gtk.Align.END)
        save_btn.connect("clicked", lambda _b, p=path, spin=att_spin, tv=deb_tv:
                          self._save_afterservice_notes(p, spin, tv))
        box.append(save_btn)

        row.set_child(box); return row

    def _save_afterservice_notes(self, path: str, spin: Gtk.SpinButton, tv: Gtk.TextView):
        try:
            p = Path(path)
            data = json.loads(p.read_text(encoding="utf-8"))
            data["attendance"] = int(spin.get_value())
            buf = tv.get_buffer(); s, e = buf.get_bounds()
            data["debrief"] = buf.get_text(s, e, False).strip()
            p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            if self._main.current_file and str(Path(self._main.current_file)) == str(p):
                self._main.service_attendance = data["attendance"]
                self._main.service_debrief = data["debrief"]
            self._show_toast("Notes saved")
        except Exception as e:
            self._show_toast(f"Save failed: {e}")

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
