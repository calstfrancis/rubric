"""BulletinPrefsWindow — standalone bulletin settings window, auto-saves on every change."""

from __future__ import annotations

from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib

from rubric_package.models.config import config


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
        tv_a, btn_a, row_a = self._ann_widgets[idx_a]
        tv_b, btn_b, row_b = self._ann_widgets[idx_b]
        if not row_a.get_visible() or not row_b.get_visible():
            # Never swap into a deleted (hidden-but-not-removed) row.
            return

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
            if idx < 0:
                return
            j = idx + direction
            # Skip over deleted (hidden) rows to find the next visible neighbour.
            while 0 <= j < len(self._ann_widgets) and not self._ann_widgets[j][2].get_visible():
                j += direction
            if 0 <= j < len(self._ann_widgets):
                self._swap_announcements(idx, j)

        cal.connect("day-selected", on_day_selected)
        clear_date_btn.connect("clicked", on_clear_date)
        tv.get_buffer().connect("changed", lambda _b: self._save_announcements())
        up_btn.connect("clicked",   lambda _b: on_move(-1))
        down_btn.connect("clicked", lambda _b: on_move(+1))
        del_btn.connect("clicked",  lambda _b, w=widgets: (w[2].set_visible(False), self._save_announcements()))

        self._ann_grp.add(row)
        self._ann_widgets.append(widgets)
