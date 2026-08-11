"""PreferencesWindow — Rubric's tabbed preferences dialog.

Covers view/layout options, recurring elements and element defaults, templates,
palette, scripture/hymn settings, snippets, and GitHub sync setup.

Custom observances are *not* here: they are edited in DatesEditorWindow, opened
from "Edit dates…" in the liturgical events popover. This window used to carry a
Dates page that wrote to the legacy ``config.custom_dates`` key, which nothing
has read since dates moved to ``config.all_dates`` — every date added through it
was silently discarded.
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
from rubric_package.utils.helpers import flatpak_git_prefix, git_credential_args, git_no_sign_args
from rubric_package.utils.dialogs import notice
from rubric_package.utils.git_conflicts import (
    list_conflicted_files, abort_merge, resolve_conflicts_interactive,
)
from rubric_package import github_auth, secret_store
from rubric_package.views import github_signin

_GIT = flatpak_git_prefix()

try:
    from snippets import load_snippets, save_snippets
    _SNIP_OK = True
except ImportError:
    _SNIP_OK = False


def _esc(text: str) -> str:
    """Escape user text bound for an Adw row title/subtitle.

    Those properties are parsed as Pango markup, so an element or template name
    containing "&" (e.g. "Welcome & Announcements") renders as nothing at all
    plus a GTK markup warning. Every name in this window comes from the user.
    """
    return GLib.markup_escape_text(text or "")


class PreferencesWindow(Adw.PreferencesWindow):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.set_title("Preferences"); self.set_default_size(700, 560)
        # Seven pages is more than a glance can scan — let people type for a row.
        self.set_search_enabled(True)
        self._build_view()
        self._build_elements()
        self._build_template(); self._build_palette()
        self._build_scripture()
        if _SNIP_OK and not config.simple_mode:
            self._try_build_snippets()
        self._build_github()
        if self._simple_row:
            self._simple_row.connect("notify::active", self._on_simple_mode_toggled)
        else:
            self._simple_switch.connect("notify::active", self._on_simple_mode_toggled)
        self.connect("close-request", self._on_close)

    def _on_simple_mode_toggled(self, _widget, _pspec):
        # Simple mode applies the moment it is switched, rather than waiting for
        # _on_close to write it: leaving it until close meant a Simple toggle
        # made from the status bar while this window was open got silently
        # reverted by the stale switch state saved here.
        active = self._simple_mode_active()
        if config.simple_mode != active:
            win = self.get_transient_for()
            if win is not None and hasattr(win, "_on_simple_status_clicked"):
                win._on_simple_status_clicked(None)
            else:
                config.simple_mode = active
                config.save()
        # Turning Simple mode off should reveal the advanced view toggles and
        # the Snippets page immediately, not just after a close and reopen.
        # Visibility first: building the Snippets page touches the snippet
        # database, and a failure there must not leave this page half-updated.
        self._sync_advanced_visibility()
        if _SNIP_OK and not active and not hasattr(self, "_snip_page"):
            self._try_build_snippets()

    def _try_build_snippets(self):
        """Add the Snippets page, tolerating an unreadable snippet store.

        Building it opens the snippet database. If that fails the page simply
        stays absent — it must not take the rest of Preferences down with it.
        """
        try:
            self._build_snippets()
        except Exception:
            pass

    def _build_view(self):
        page = Adw.PreferencesPage(title="View", icon_name="view-grid-symbolic"); self.add(page)

        def _main():
            return self.get_transient_for()

        # -- Feature level -------------------------------------------------
        # Simple mode leads the page: it decides what the rest of this page --
        # and most of the app -- even shows.
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

        # -- Appearance ----------------------------------------------------
        # Theme lives here as well as in the menu's Appearance submenu: the menu
        # is where you reach for it mid-edit, this is where you look when you
        # have gone hunting through settings for it.
        appear_grp = Adw.PreferencesGroup(title="Appearance")
        page.add(appear_grp)

        theme_row = Adw.ComboRow(
            title="Theme",
            subtitle="System follows your desktop's light/dark setting")
        theme_model = Gtk.StringList()
        for lbl in ("System", "Light", "Dark"):
            theme_model.append(lbl)
        theme_row.set_model(theme_model)
        _theme_keys = ["system", "light", "dark"]
        theme_row.set_selected(_theme_keys.index(config.theme)
                               if config.theme in _theme_keys else 0)

        def _on_theme_row(row, _pspec):
            choice = _theme_keys[row.get_selected()]
            if choice == config.theme:
                return
            w = _main()
            if w is None or not hasattr(w, "_set_theme"):
                return
            w._set_theme(choice)
            # Keep the menu's radio group in step with this combo.
            act = w.lookup_action("theme")
            if act is not None:
                act.set_state(GLib.Variant("s", choice))
        theme_row.connect("notify::selected", _on_theme_row)
        appear_grp.add(theme_row)

        # -- Layout --------------------------------------------------------
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

        # -- Advanced ------------------------------------------------------
        # Built unconditionally and hidden while Simple mode is on, rather than
        # skipped at construction. Building them conditionally meant switching
        # Simple mode off here left them absent until Preferences was closed and
        # reopened -- and since neither has a status-bar button any more, that
        # was the only route to them at all.
        self._adv_grp = Adw.PreferencesGroup(
            title="Advanced",
            description="Shown when Simple mode is off.")
        page.add(self._adv_grp)

        def _switch_row(grp, title, subtitle, initial, on_change):
            if hasattr(Adw, "SwitchRow"):
                row = Adw.SwitchRow(title=title, subtitle=subtitle)
                row.set_active(initial)
                row.connect("notify::active", lambda r, _p: on_change(r.get_active()))
            else:
                row = Adw.ActionRow(title=title, subtitle=subtitle)
                sw = Gtk.Switch(valign=Gtk.Align.CENTER)
                sw.set_active(initial)
                sw.connect("notify::active", lambda w, _p: on_change(w.get_active()))
                row.add_suffix(sw); row.set_activatable_widget(sw)
            grp.add(row)
            return row

        def _set_gost(active):
            if config.gost_mode != active:
                w = _main()
                if w is not None:
                    w._on_gost_status_clicked(None)

        def _set_dev(active):
            if config.dev_mode != active:
                w = _main()
                if w is not None:
                    w._on_dev_status_clicked(None)

        _switch_row(self._adv_grp, "GOST interface font",
                    "A Cyrillic engineering typeface, in place of the system font",
                    config.gost_mode, _set_gost)
        _switch_row(self._adv_grp, "Developer mode",
                    "Adds a “Copy Typst source” button to the preview panel, "
                    "and a Typst source toggle to the status bar",
                    config.dev_mode, _set_dev)

        # -- Interface font ------------------------------------------------
        font_grp = Adw.PreferencesGroup(
            title="Interface font",
            description="Leave empty to follow the system font. "
                        "Give a family and optional size, e.g. “URW Palladio L 12”.")
        page.add(font_grp)
        font_row = Adw.EntryRow(title="Font") if hasattr(Adw, "EntryRow") else None
        if font_row is not None:
            font_row.set_text(config.ui_font)

            def _on_font_changed(row):
                config.ui_font = row.get_text().strip()
                config.save()
                win = self.get_transient_for()
                if win is not None and hasattr(win, "_apply_gost_mode"):
                    win._apply_gost_mode()
            font_row.connect("changed", _on_font_changed)
            font_grp.add(font_row)

        self._sync_advanced_visibility()

    def _sync_advanced_visibility(self):
        """Show the advanced view toggles only while Simple mode is off."""
        if hasattr(self, "_adv_grp"):
            self._adv_grp.set_visible(not self._simple_mode_active())

    def _build_elements(self):
        """Preferences page: recurring elements and per-element default notes.

        These are about what goes *into* a service, not how it is displayed, so
        they get their own page rather than sitting at the bottom of View.
        """
        page = Adw.PreferencesPage(title="Elements", icon_name="view-list-symbolic")
        self.add(page)

        # -- Recurring elements ---------------------------------------------
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

        # -- Element defaults ------------------------------------------------
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
        row = Adw.ActionRow(title=_esc(name))
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
                grp = Adw.PreferencesGroup(title=_esc(tname) + (" ★" if is_default else ""))

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
                    subtitle=", ".join(_esc(i.get("name", i.get("title", ""))) for i in items[:4] if i.get("type") != "divider") +
                             ("…" if sum(1 for i in items if i.get("type") != "divider") > 4 else "")
                )
                grp.add(summary)

                # Delete button row
                del_grp = Adw.PreferencesGroup()
                del_row = Adw.ActionRow(title=f"Delete “{_esc(tname)}”",
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
            grp = Adw.PreferencesGroup(title=_esc(sd["section"]))
            rb = Gtk.Button(label="Remove section", valign=Gtk.Align.CENTER)
            rb.add_css_class("destructive-action"); rb.add_css_class("flat")
            rb.connect("clicked", lambda _,s=sd: (self._pal.__setitem__(slice(None), [x for x in self._pal if x is not s]), self._refresh_pal()))
            grp.set_header_suffix(rb)
            for n in sd["items"]:
                row = Adw.ActionRow(title=_esc(n))
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
            grp = Adw.PreferencesGroup(title=_esc(snip["name"]))
            # Delete button
            del_btn = Gtk.Button(label="Delete", valign=Gtk.Align.CENTER)
            del_btn.add_css_class("destructive-action"); del_btn.add_css_class("flat")
            del_btn.connect("clicked", lambda _b, idx=i: self._delete_snippet(idx))
            grp.set_header_suffix(del_btn)
            # Preview row
            preview = snip["content"].replace("\n"," ")[:80]+("…" if len(snip["content"])>80 else "")
            row = Adw.ActionRow(title=_esc(preview)); row.set_subtitle_lines(2); grp.add(row)
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
        # Simple mode is deliberately not written here — it applies live in
        # _on_simple_mode_toggled. Writing cached switch state on close is what
        # let this window silently undo a toggle made elsewhere while it was up.
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
            from rubric_package.db import hymn_count as _hcount, hymn_bundled_count
            _n = _hcount()
            _bundled = hymn_bundled_count()
        except Exception:
            _n = 0
            _bundled = 0

        # No download buttons: Rubric reads hymn titles from its own database and
        # never goes to the network for them. It used to fetch from Hymnary.org,
        # which now answers automated requests with a bot-protection challenge,
        # so every lookup failed and a "download" worked through a whole hymnal
        # to add nothing. Titles ship with the app; missing ones are typed in
        # once from the Lookup tab and kept.
        hymn_grp = Adw.PreferencesGroup(
            title="Hymn title database",
            description=(
                f"Rubric includes {_bundled} hymn titles, so lookup and title search "
                "work offline. To add one it doesn't have, look up its number in the "
                "hymn panel and type the title in — it is saved for good."
            ) if _bundled else (
                "Hymn titles are stored locally. Add them from the hymn panel's "
                "Lookup tab."
            ))
        page.add(hymn_grp)

        self._hymn_dl_status = Gtk.Label(label=f"{_n} titles stored")
        self._hymn_dl_status.add_css_class("dim-label"); self._hymn_dl_status.add_css_class("caption")
        self._hymn_dl_status.set_xalign(0)

        status_row = Adw.ActionRow(title="Stored titles")
        status_row.add_suffix(self._hymn_dl_status)
        _clear_btn = Gtk.Button(label="Reset", valign=Gtk.Align.CENTER)
        _clear_btn.add_css_class("flat")
        _clear_btn.connect("clicked", self._on_hymn_cache_clear)
        status_row.add_suffix(_clear_btn)
        hymn_grp.add(status_row)

    def _on_hymn_cache_clear(self, _btn):
        """Confirm first — the database holds hand-typed titles too."""
        dlg = Adw.MessageDialog(
            transient_for=self,
            heading="Reset the hymn title database?",
            body="This deletes every stored title, including any you typed in "
                 "yourself. The titles that ship with Rubric come back the next "
                 "time it starts.")
        dlg.add_response("cancel", "Cancel")
        dlg.add_response("clear", "Reset")
        dlg.set_response_appearance("clear", Adw.ResponseAppearance.DESTRUCTIVE)
        dlg.set_default_response("cancel")
        dlg.set_close_response("cancel")

        def on_resp(_d, r):
            if r != "clear":
                return
            try:
                from rubric_package.db import (
                    hymn_clear, hymn_seed_bundled, hymn_count as _hc,
                )
                hymn_clear()
                # Restore the bundled titles straight away rather than making the
                # user restart to get back to a working search.
                hymn_seed_bundled()
                n = _hc()
            except Exception:
                n = 0
            self._hymn_dl_status.set_text(f"{n} titles stored")
        dlg.connect("response", on_resp)
        dlg.present()

    def _build_github(self):
        page = Adw.PreferencesPage(title="GitHub", icon_name="network-server-symbolic")
        self.add(page)

        # ── Setup wizard shortcut ──────────────────────────────────────────
        wizard_grp = Adw.PreferencesGroup(
            title="First-time setup",
            description="Run the setup wizard to configure your folder, download hymn titles, and connect to GitHub."
        )
        page.add(wizard_grp)
        wizard_row = Adw.ActionRow(title="Set Up Rubric",
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

        # ── Local folder ─────────────────────────────────────────────────
        loc_grp = Adw.PreferencesGroup(
            title="Local Folder",
            description="The folder on this computer where Rubric keeps your files — this is what gets "
                        "backed up online. Liturgy files, Typst exports, and PDFs are saved in subfolders here."
        )
        page.add(loc_grp)

        self._repo_row = Adw.ActionRow(title="Folder")
        self._repo_row.set_subtitle(config.github_repo or "Not configured")
        browse_btn = Gtk.Button(label="Browse…", valign=Gtk.Align.CENTER)
        browse_btn.add_css_class("flat")
        browse_btn.connect("clicked", self._on_repo_browse)
        self._repo_row.add_suffix(browse_btn)
        loc_grp.add(self._repo_row)

        # ── Start backing this up ───────────────────────────────────────────
        setup_grp = Adw.PreferencesGroup(
            title="Start Backing This Up",
            description="Turns the folder above into something Rubric can save versions of and back up online."
        )
        page.add(setup_grp)

        setup_row = Adw.ActionRow(
            title="Set up the selected folder",
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
            description="Sign in once and Rubric handles creating your online copy and staying connected.",
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

        self._repo_name_row = Adw.EntryRow(title="What to call it online")
        signin_grp.add(self._repo_name_row)
        self._repo_private_row = Adw.SwitchRow(
            title="Private", subtitle="Only you can see it", active=True)
        signin_grp.add(self._repo_private_row)
        create_row = Adw.ActionRow(title="Create the online copy")
        self._create_repo_btn = Gtk.Button(label="Create", valign=Gtk.Align.CENTER)
        self._create_repo_btn.add_css_class("suggested-action")
        self._create_repo_btn.connect("clicked", self._on_github_create_repo)
        create_row.add_suffix(self._create_repo_btn)
        signin_grp.add(create_row)

        # ── Manual fallback ───────────────────────────────────────────────
        remote_grp = Adw.PreferencesGroup(
            title="Or Use an Online Copy You Already Have",
            description="Paste its address (e.g. https://github.com/yourname/liturgy).",
        )
        page.add(remote_grp)

        self._remote_entry = Adw.EntryRow(title="Address")
        self._remote_entry.set_text(self._detect_remote())
        remote_grp.add(self._remote_entry)

        connect_row = Adw.ActionRow(title="Save")
        connect_btn = Gtk.Button(label="Connect", valign=Gtk.Align.CENTER)
        connect_btn.connect("clicked", self._on_remote_connect)
        connect_row.add_suffix(connect_btn)
        remote_grp.add(connect_row)

        # ── Pull ───────────────────────────────────────────────────────────
        pull_grp = Adw.PreferencesGroup(
            title="Get the Latest Version",
            description="Downloads the latest version from your online copy — use this if you worked on "
                        "another computer, or someone else made changes."
        )
        page.add(pull_grp)

        pull_row = Adw.ActionRow(title="Get latest changes")
        pull_btn = Gtk.Button(label="Get Latest", valign=Gtk.Align.CENTER)
        pull_btn.connect("clicked", self._on_prefs_pull)
        pull_row.add_suffix(pull_btn)
        pull_grp.add(pull_row)

        # ── Getting-started guide ──────────────────────────────────────────
        help_grp = Adw.PreferencesGroup(title="Getting started — new users")
        page.add(help_grp)
        for title, subtitle in [
            ("1. Set up a folder above",       "Browse to an empty folder, then click Set up"),
            ("2. Sign in with GitHub",         "Click Sign in above and approve in your browser"),
            ("3. Create your online copy",     'Pick a name (e.g. "liturgy") and click Create'),
            ("4. Click Back Up ⟳",             "Use the ⟳ button in the main toolbar to save and back up your files"),
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
            return "Set up a folder first."
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
            notice(self, "No folder chosen", "Choose a folder above and click Set up first.")
            return
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
                    notice(self, "Couldn't create your online copy", str(e))
                GLib.idle_add(fail)
                return
            err = self._set_remote(clone_url)

            def finish():
                self._create_repo_btn.set_sensitive(True)
                self._remote_entry.set_text(self._detect_remote())
                if err:
                    notice(self, "Created online, but couldn't connect it here", err)
                else:
                    notice(self, "Connected to GitHub",
                        f"Your online copy is ready:\n{clone_url}\n\n"
                        "Use the ⟳ button in the main toolbar to back up your files.")
            GLib.idle_add(finish)
        threading.Thread(target=run, daemon=True).start()

    def _on_repo_browse(self, _btn):
        dlg = Gtk.FileDialog(title="Choose a folder")
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
            notice(self, "No folder chosen", "Browse to a folder first, then click Set up.")
            return

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
            notice(self, "Couldn't set up that folder", "\n".join(errors))
        else:
            notice(self, "Folder ready",
                f"Created liturgy/, tex/, pdf/, and bulletins/ folders in:\n{repo}\n\n"
                "Next: on github.com, create a new repository (keep it private), "
                "copy its address, and paste it in the field below.")

    def _on_remote_connect(self, _btn):
        repo = config.github_repo
        url  = self._remote_entry.get_text().strip()
        if not repo:
            notice(self, "No folder set up yet", "Set up a folder first.")
            return
        if not url:
            notice(self, "No address entered", "Paste its address in the field above.")
            return
        try:
            check = subprocess.run(_GIT + ["-C", repo, "remote", "get-url", "origin"],
                                   capture_output=True, text=True, timeout=5)
            cmd = _GIT + ["-C", repo, "remote",
                   "set-url" if check.returncode == 0 else "add",
                   "origin", url]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        except Exception as e:
            notice(self, "Error", str(e))
            return

        if r.returncode != 0:
            notice(self, "Could not connect", r.stderr.strip() or "Unknown error")
        else:
            notice(self, "Connected to GitHub",
                f"Now backing up to:\n{url}\n\n"
                "Use the ⟳ button in the main toolbar to back up your files.")

    def _on_prefs_pull(self, _btn):
        repo = config.github_repo
        if not repo:
            notice(self, "No folder set up yet", "Set up a folder and connect to GitHub first.")
            return

        progress = Adw.MessageDialog(transient_for=self,
            heading="Getting the latest version…", body="Please wait.")
        progress.present()

        def on_conflicts_resolved(success: bool):
            notice(self, "Done" if success else "Cancelled",
                   "Conflicts resolved." if success else "No changes were made.")

        def run():
            try:
                with git_credential_args(secret_store.load_github_token()) as cred:
                    r = subprocess.run(
                        _GIT + ["-C", repo] + cred + git_no_sign_args() + ["pull"],
                        capture_output=True, text=True, timeout=60)
                if r.returncode != 0 and list_conflicted_files(repo):
                    def start_resolution():
                        progress.destroy()
                        resolve_conflicts_interactive(self, repo, on_conflicts_resolved)
                    GLib.idle_add(start_resolution)
                    return

                def on_done():
                    progress.destroy()
                    if r.returncode != 0:
                        abort_merge(repo)
                        err = (r.stderr or r.stdout or "Unknown error").strip()
                        notice(self, "Couldn't get the latest version", err[:400])
                    else:
                        out = r.stdout.strip() or "Already up to date."
                        notice(self, "Done", out[:400])
                GLib.idle_add(on_done)
            except Exception as e:
                def on_err():
                    progress.destroy()
                    notice(self, "Couldn't get the latest version", str(e))
                GLib.idle_add(on_err)

        threading.Thread(target=run, daemon=True).start()
