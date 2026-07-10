"""PreferencesWindow — Rubric's tabbed preferences dialog.

Covers view/layout options, templates, palette, snippets, scripture/hymn
settings, custom dates, and GitHub sync setup.
"""

from __future__ import annotations

import subprocess
import threading
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from rubric_package.models.config import config, get_palette, SECTIONS
from rubric_package.utils.helpers import flatpak_git_prefix, git_credential_args
from rubric_package import github_auth, secret_store
from rubric_package.views import github_signin

_GIT = flatpak_git_prefix()

try:
    from hymn_lookup import prefetch_hymnal
except ImportError:
    def prefetch_hymnal(book, on_progress=None, on_done=None): pass

try:
    from snippets import load_snippets, save_snippets
    _SNIP_OK = True
except ImportError:
    _SNIP_OK = False


class PreferencesWindow(Adw.PreferencesWindow):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.set_title("Preferences"); self.set_default_size(700,560); self.set_search_enabled(False)
        self._build_view()
        self._build_template(); self._build_palette()
        if _SNIP_OK and not config.simple_mode:
            self._build_snippets()
        self._build_github(); self._build_scripture()
        self._build_dates_page()
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
            except Exception: pass
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
                del_row = Adw.ActionRow(title=f"Delete “{tname}”",
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
            except Exception: pass
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
            except Exception: pass
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

    def _build_dates_page(self):
        """Preferences page: manage custom justice and religious dates."""
        _MONTH_NAMES = ["January","February","March","April","May","June",
                        "July","August","September","October","November","December"]

        page = Adw.PreferencesPage(title="Dates", icon_name="x-office-calendar-symbolic")
        self.add(page)
        self._dates_page = page
        self._dates_groups: list = []

        intro_grp = Adw.PreferencesGroup(
            title="Custom observances",
            description="Dates you add here appear in the justice/custom dates bar "
                        "below the main status bar, alongside the built-in Canadian "
                        "and social justice calendar. Built-in dates (e.g. National "
                        "Indigenous Peoples Day, World Refugee Day) are not editable "
                        "here — they live in observances.py."
        )
        page.add(intro_grp)
        self._dates_groups.append(intro_grp)

        self._refresh_dates_page()

    def _refresh_dates_page(self):
        """Rebuild the custom-dates list in the Dates page."""
        page = getattr(self, "_dates_page", None)
        if page is None:
            return

        _MONTH_NAMES = ["Jan","Feb","Mar","Apr","May","Jun",
                        "Jul","Aug","Sep","Oct","Nov","Dec"]
        _MONTH_FULL  = ["January","February","March","April","May","June",
                        "July","August","September","October","November","December"]

        # Remove all rebuilable groups (keep intro group at index 0)
        for grp in getattr(self, "_dates_groups", [])[1:]:
            try: page.remove(grp)
            except Exception: pass
        self._dates_groups = self._dates_groups[:1]

        for category, cat_title, cat_desc in [
            ("justice",
             "Social Justice & Canadian Observances",
             "Shown in the justice dates bar. Use this to add dates not in the "
             "built-in calendar — local events, diocesan days, etc."),
            ("religious",
             "Religious & Liturgical Dates",
             "Custom feast days, saints' days, or observances specific to your "
             "tradition. These also appear in the justice/custom dates bar."),
        ]:
            custom = [cd for cd in config.custom_dates if cd.get("category") == category]
            grp = Adw.PreferencesGroup(title=cat_title, description=cat_desc)
            page.add(grp); self._dates_groups.append(grp)

            if not custom:
                empty_row = Adw.ActionRow(title="No custom dates yet")
                empty_row.add_css_class("dim-label")
                grp.add(empty_row)

            for i, cd in enumerate(config.custom_dates):
                if cd.get("category") != category:
                    continue
                month = cd.get("month", 1); day = cd.get("day", 1)
                name = cd.get("name", "")
                try:
                    month_name = _MONTH_NAMES[month - 1]
                except (IndexError, TypeError):
                    month_name = str(month)
                row = Adw.ActionRow(title=name, subtitle=f"{month_name} {day}")
                del_btn = Gtk.Button(icon_name="user-trash-symbolic",
                                     valign=Gtk.Align.CENTER,
                                     tooltip_text="Remove this date")
                del_btn.add_css_class("flat")

                def _on_delete(_b, idx=i):
                    config.custom_dates.pop(idx)
                    config.save()
                    self._refresh_dates_page()
                    win = self.get_transient_for()
                    if win and hasattr(win, "_refresh_justice_row") and getattr(win, "selected_date", None):
                        win._refresh_justice_row(win.selected_date)

                del_btn.connect("clicked", _on_delete)
                row.add_suffix(del_btn)
                grp.add(row)

            # Add-date row for this category
            add_grp = Adw.PreferencesGroup(title=f'Add to “{cat_title}”')
            page.add(add_grp); self._dates_groups.append(add_grp)

            # Month row
            month_row = Adw.ActionRow(title="Month")
            month_spin = Gtk.SpinButton.new_with_range(1, 12, 1)
            month_spin.set_valign(Gtk.Align.CENTER)
            month_spin.set_tooltip_text("Month (1–12)")
            month_row.add_suffix(month_spin)
            add_grp.add(month_row)

            # Day row
            day_row = Adw.ActionRow(title="Day")
            day_spin = Gtk.SpinButton.new_with_range(1, 31, 1)
            day_spin.set_valign(Gtk.Align.CENTER)
            day_spin.set_tooltip_text("Day of month (1–31)")
            day_row.add_suffix(day_spin)
            add_grp.add(day_row)

            # Name row
            try:
                name_entry = Adw.EntryRow(title="Name")
                add_grp.add(name_entry)
                _get_name = lambda e=name_entry: e.get_text().strip()
                _clear_name = lambda e=name_entry: e.set_text("")
            except AttributeError:
                name_action = Adw.ActionRow(title="Name")
                name_field = Gtk.Entry(valign=Gtk.Align.CENTER)
                name_field.set_hexpand(True)
                name_action.add_suffix(name_field)
                add_grp.add(name_action)
                _get_name = lambda f=name_field: f.get_text().strip()
                _clear_name = lambda f=name_field: f.set_text("")

            add_btn_row = Adw.ActionRow(title="Add date")
            add_btn = Gtk.Button(label="Add", valign=Gtk.Align.CENTER)
            add_btn.add_css_class("suggested-action")
            add_btn_row.add_suffix(add_btn)
            add_grp.add(add_btn_row)

            def _on_add(_b, cat=category, ms=month_spin, ds=day_spin,
                        get_n=_get_name, clr_n=_clear_name):
                name = get_n()
                if not name:
                    return
                month = int(ms.get_value())
                day = int(ds.get_value())
                config.custom_dates.append({"month": month, "day": day,
                                            "name": name, "category": cat})
                config.save()
                clr_n()
                ms.set_value(1); ds.set_value(1)
                self._refresh_dates_page()
                win = self.get_transient_for()
                if win and hasattr(win, "_refresh_justice_row") and getattr(win, "selected_date", None):
                    win._refresh_justice_row(win.selected_date)

            add_btn.connect("clicked", _on_add)

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
        user_path = Path.home() / ".config/rubric/templates" / f"{fname}.typ"
        bundled   = Path(__file__).resolve().parent.parent / "templates" / f"{fname}.typ"

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

        # ── GitHub sign-in ────────────────────────────────────────────────
        signin_grp = Adw.PreferencesGroup(
            title="Connect to GitHub",
            description="Sign in once and Rubric handles repository creation and authentication for you.",
        )
        page.add(signin_grp)

        self._signin_row = Adw.ActionRow(title="Sign in with GitHub")
        self._signin_btn = Gtk.Button(label="Sign in", valign=Gtk.Align.CENTER)
        self._signin_btn.add_css_class("suggested-action")
        self._signin_btn.connect("clicked", self._on_github_signin)
        self._signin_row.add_suffix(self._signin_btn)
        signin_grp.add(self._signin_row)

        self._connected_row = Adw.ActionRow(title="Connected as")
        self._disconnect_btn = Gtk.Button(label="Disconnect", valign=Gtk.Align.CENTER)
        self._disconnect_btn.add_css_class("flat")
        self._disconnect_btn.connect("clicked", self._on_github_disconnect)
        self._connected_row.add_suffix(self._disconnect_btn)
        signin_grp.add(self._connected_row)

        self._repo_name_row = Adw.EntryRow(title="Repository name")
        signin_grp.add(self._repo_name_row)
        self._repo_private_row = Adw.SwitchRow(title="Private repository", active=True)
        signin_grp.add(self._repo_private_row)
        create_row = Adw.ActionRow(title="Create a new repository on GitHub")
        self._create_repo_btn = Gtk.Button(label="Create", valign=Gtk.Align.CENTER)
        self._create_repo_btn.add_css_class("suggested-action")
        self._create_repo_btn.connect("clicked", self._on_github_create_repo)
        create_row.add_suffix(self._create_repo_btn)
        signin_grp.add(create_row)

        # ── Manual fallback ───────────────────────────────────────────────
        remote_grp = Adw.PreferencesGroup(
            title="Or connect an existing repository manually",
            description="Paste the URL of your GitHub repository (e.g. https://github.com/yourname/liturgy).",
        )
        page.add(remote_grp)

        self._remote_entry = Adw.EntryRow(title="GitHub repository URL")
        self._remote_entry.set_text(self._detect_remote())
        remote_grp.add(self._remote_entry)

        connect_row = Adw.ActionRow(title="Save remote URL")
        connect_btn = Gtk.Button(label="Connect", valign=Gtk.Align.CENTER)
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
            ("1. Set up a folder above",       "Browse to an empty folder, then click Set up"),
            ("2. Sign in with GitHub",         "Click Sign in above and approve in your browser"),
            ("3. Create a repository",         'Pick a name (e.g. "liturgy") and click Create'),
            ("4. Click Push ⟳",                "Use the ⟳ button in the main toolbar to push files"),
        ]:
            r = Adw.ActionRow(title=title, subtitle=subtitle)
            r.set_sensitive(False)
            help_grp.add(r)

        self._refresh_github_signin()

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

    def _set_remote(self, url: str) -> str | None:
        """Points the configured folder's origin remote at url. Returns an error string, or None on success."""
        repo = config.github_repo
        if not repo:
            return "Set up a repository folder first."
        try:
            chk = subprocess.run(_GIT + ["-C", repo, "remote", "get-url", "origin"],
                                 capture_output=True, text=True, timeout=5)
            cmd = _GIT + ["-C", repo, "remote", "set-url" if chk.returncode == 0 else "add", "origin", url]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return None if r.returncode == 0 else r.stderr.strip()
        except Exception as e:
            return str(e)

    def _refresh_github_signin(self):
        token = secret_store.load_github_token()
        self._signin_row.set_visible(not token)
        for w in (self._connected_row, self._repo_name_row, self._repo_private_row):
            w.set_visible(bool(token))
        if token:
            self._connected_row.set_subtitle(f"@{config.github_username}" if config.github_username else "")
            default_name = Path(config.github_repo).name if config.github_repo else "liturgy"
            if not self._repo_name_row.get_text():
                self._repo_name_row.set_text(default_name)

    def _on_github_signin(self, _btn):
        def on_connected(token, username):
            config.github_username = username
            config.save()
            self._refresh_github_signin()
        github_signin.present(self, on_connected)

    def _on_github_disconnect(self, _btn):
        secret_store.delete_github_token()
        config.github_username = ""
        config.save()
        self._refresh_github_signin()

    def _on_github_create_repo(self, _btn):
        if not config.github_repo:
            dlg = Adw.MessageDialog(transient_for=self, heading="No folder selected",
                body="Browse to a folder and click Set up first.")
            dlg.add_response("ok", "OK"); dlg.present(); return
        token = secret_store.load_github_token()
        if not token:
            return
        name = self._repo_name_row.get_text().strip() or "liturgy"
        private = self._repo_private_row.get_active()
        self._create_repo_btn.set_sensitive(False)

        def run():
            try:
                clone_url = github_auth.create_repo(token, name, private)
            except github_auth.GithubAuthError as e:
                def fail():
                    self._create_repo_btn.set_sensitive(True)
                    dlg = Adw.MessageDialog(transient_for=self, heading="Couldn't create repository", body=str(e))
                    dlg.add_response("ok", "OK"); dlg.present()
                GLib.idle_add(fail)
                return
            err = self._set_remote(clone_url)

            def finish():
                self._create_repo_btn.set_sensitive(True)
                self._remote_entry.set_text(self._detect_remote())
                if err:
                    dlg = Adw.MessageDialog(transient_for=self, heading="Repository created, but couldn't connect it", body=err)
                else:
                    dlg = Adw.MessageDialog(transient_for=self, heading="Connected to GitHub",
                        body=f"Repository created and connected:\n{clone_url}\n\n"
                             "Use the ⟳ Push button in the main toolbar to upload your files.")
                dlg.add_response("ok", "OK"); dlg.present()
            GLib.idle_add(finish)
        threading.Thread(target=run, daemon=True).start()

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
                with git_credential_args(secret_store.load_github_token()) as cred:
                    r = subprocess.run(_GIT + ["-C", repo] + cred + ["pull"],
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
