"""BulletinPreview — live bulletin/manuscript preview panel for Rubric.

Owns the preview side-panel UI, the Typst-compile-to-PDF pipeline used for
live preview, the WebKit scroll-position dance around reloads, and the
bulletin-text edit toggle. Constructed with a reference to the MainWindow
instance it serves; reads and writes shared document/UI state (the preview
widgets, config.bulletin, service_entries, etc.) via that reference rather
than owning it, the same composition pattern used by BulletinExporter and
the GTK windows already extracted into rubric_package/views/.
"""

from __future__ import annotations

import subprocess
import threading
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

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

from rubric_package.models.config import config
from rubric_package.utils.typst import strip_typst_plain, format_typst_error


class BulletinPreview:
    """Owns the live preview panel UI and its Typst-compile pipeline."""

    def __init__(self, main_window):
        self._main = main_window

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
        self._main._preview_bulletin_btn = Gtk.ToggleButton(label="Bulletin")
        self._main._preview_bulletin_btn.set_active(True)
        self._main._preview_bulletin_btn.set_tooltip_text("Show congregation bulletin")
        self._main._preview_manuscript_btn = Gtk.ToggleButton(label="Manuscript")
        self._main._preview_manuscript_btn.set_group(self._main._preview_bulletin_btn)
        self._main._preview_manuscript_btn.set_tooltip_text("Show leader manuscript")

        def _on_preview_mode(btn, mode):
            if btn.get_active():
                self._main._preview_mode = mode
                self._main._preview_scroll_y = 0
                self._do_preview_update()

        self._main._preview_bulletin_btn.connect("toggled", _on_preview_mode, "bulletin")
        self._main._preview_manuscript_btn.connect("toggled", _on_preview_mode, "manuscript")
        mode_box.append(self._main._preview_bulletin_btn)
        mode_box.append(self._main._preview_manuscript_btn)
        hdr.append(mode_box)

        # Compile mode cycle (Auto / Save / Manual) — lives here rather than in a second toolbar
        _mode_labels = {"auto": "Auto", "on_save": "Save", "manual": "Manual"}
        _initial_label = _mode_labels.get(getattr(self._main, "_preview_update_mode", "on_save"), "Save")
        self._main._preview_mode_btn = Gtk.Button(label=_initial_label)
        self._main._preview_mode_btn.add_css_class("flat")
        self._main._preview_mode_btn.set_tooltip_text(
            "Preview compile mode: Auto (on every change) · Save (on file save) · Manual (compile button only)")

        def _on_preview_mode_cycle(_btn):
            _modes = ["auto", "on_save", "manual"]
            cur = getattr(self._main, "_preview_update_mode", "on_save")
            nxt = _modes[(_modes.index(cur) + 1) % len(_modes)]
            self._main._preview_update_mode = nxt
            self._main._preview_mode_btn.set_label(_mode_labels[nxt])

        self._main._preview_mode_btn.connect("clicked", _on_preview_mode_cycle)
        hdr.append(self._main._preview_mode_btn)

        # Compile button — always visible; essential in Save/Manual modes
        self._main._preview_compile_btn = Gtk.Button(icon_name="view-refresh-symbolic",
                                               tooltip_text="Compile preview now")
        self._main._preview_compile_btn.add_css_class("flat")
        self._main._preview_compile_btn.connect("clicked", lambda _: self._do_preview_update())
        hdr.append(self._main._preview_compile_btn)

        self._main._bulletin_edit_btn = Gtk.ToggleButton(icon_name="document-edit-symbolic",
                                                   tooltip_text="Edit bulletin text for this service")
        self._main._bulletin_edit_btn.add_css_class("flat")
        self._main._bulletin_edit_btn.connect("toggled", self._on_bulletin_edit_toggled)
        hdr.append(self._main._bulletin_edit_btn)

        gear_btn = Gtk.MenuButton(icon_name="emblem-system-symbolic")
        gear_btn.add_css_class("flat")
        gear_btn.set_tooltip_text("Preview options — format, church name, bulletin settings")
        gear_btn.set_popover(self._build_preview_gear_popover())
        hdr.append(gear_btn)

        # Compiling indicator (hidden until xelatex is running)
        self._main._preview_spinner = Gtk.Spinner()
        self._main._preview_spinner.set_visible(False)
        hdr.append(self._main._preview_spinner)
        self._main._preview_compiling_lbl = Gtk.Label(label="Compiling…")
        self._main._preview_compiling_lbl.add_css_class("dim-label")
        self._main._preview_compiling_lbl.add_css_class("caption")
        self._main._preview_compiling_lbl.set_visible(False)
        hdr.append(self._main._preview_compiling_lbl)

        # Print bulletin directly
        print_btn = Gtk.Button(icon_name="document-print-symbolic",
                               tooltip_text="Print bulletin…")
        print_btn.add_css_class("flat")
        print_btn.connect("clicked", lambda _: self._main._exporter._print_bulletin_webkit())
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

        self._main._preview_stack = Gtk.Stack()
        self._main._preview_stack.set_vexpand(True)
        self._main._preview_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._main._preview_stack.set_transition_duration(120)

        if _WEBKIT_OK:
            _ucm = _WebKit.UserContentManager()
            _pdf_toolbar_css = _WebKit.UserStyleSheet.new(
                # Compact WebKit's built-in PDF viewer toolbar so it fits the narrow
                # preview pane and doesn't overflow below its row. Also normalises
                # the font size so the page-number input matches the "of N" label.
                """
                #toolbar, .toolbar {
                    height: auto !important;
                    min-height: 0 !important;
                    padding: 2px 6px !important;
                    flex-wrap: nowrap !important;
                    box-sizing: border-box !important;
                    font-size: 13px !important;
                }
                .page-indicator, #page-indicator,
                input[type="number"], input[type="text"] {
                    font-size: 13px !important;
                    height: 22px !important;
                    padding: 1px 4px !important;
                    width: 3.2em !important;
                    box-sizing: border-box !important;
                }
                .page-count, #page-count {
                    font-size: 13px !important;
                    line-height: 22px !important;
                }
                """,
                _WebKit.UserContentInjectedFrames.ALL_FRAMES,
                _WebKit.UserStyleLevel.USER,
                None, None,
            )
            _ucm.add_style_sheet(_pdf_toolbar_css)
            self._main._preview_webview = _WebKit.WebView(user_content_manager=_ucm)
            self._main._preview_webview.set_vexpand(True)
            self._main._preview_webview.set_hexpand(True)
            self._main._preview_scroll_y = 0
            self._main._preview_webview.connect("load-changed", self._on_preview_load_changed)
            self._main._preview_stack.add_named(self._main._preview_webview, "preview")
        else:
            self._main._preview_webview = None
            status = Adw.StatusPage(
                title="WebKit not available",
                description="Install python3-webkit2gtk (or typelib-1_0-WebKit2-4_1) "
                            "to enable live bulletin preview.",
                icon_name="web-browser-symbolic",
            )
            status.set_vexpand(True)
            self._main._preview_stack.add_named(status, "preview")

        # Bulletin edit view
        edit_scroll = Gtk.ScrolledWindow()
        edit_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        edit_scroll.set_vexpand(True)
        self._main._bulletin_edit_view = Gtk.TextView()
        self._main._bulletin_edit_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._main._bulletin_edit_view.set_top_margin(12); self._main._bulletin_edit_view.set_bottom_margin(12)
        self._main._bulletin_edit_view.set_left_margin(14); self._main._bulletin_edit_view.set_right_margin(14)
        edit_scroll.set_child(self._main._bulletin_edit_view)
        edit_hint = Gtk.Label(
            label="Editing bulletin text — changes here override the auto-generated preview. "
                  "Click ✏ again to save and return to preview.")
        edit_hint.add_css_class("caption"); edit_hint.add_css_class("dim-label")
        edit_hint.set_wrap(True); edit_hint.set_margin_start(12); edit_hint.set_margin_end(12)
        edit_hint.set_margin_top(6)
        edit_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        edit_box.append(edit_hint); edit_box.append(edit_scroll)
        self._main._preview_stack.add_named(edit_box, "editor")

        box.append(self._main._preview_stack)

        # Dev mode: "Copy Typst" footer (hidden until Dev toggle is on)
        box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        self._main._preview_copy_typst_bar = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self._main._preview_copy_typst_bar.set_margin_start(8)
        self._main._preview_copy_typst_bar.set_margin_end(8)
        self._main._preview_copy_typst_bar.set_margin_top(4)
        self._main._preview_copy_typst_bar.set_margin_bottom(4)
        self._main._preview_copy_typst_bar.set_visible(False)
        _dev_lbl = Gtk.Label(label="Dev:")
        _dev_lbl.add_css_class("caption"); _dev_lbl.add_css_class("dim-label")
        self._main._preview_copy_typst_bar.append(_dev_lbl)
        _copy_typst_btn = Gtk.Button(label="Copy Typst")
        _copy_typst_btn.add_css_class("flat"); _copy_typst_btn.add_css_class("caption")
        _copy_typst_btn.connect("clicked", lambda _: self._main._dev_copy_typst())
        self._main._preview_copy_typst_bar.append(_copy_typst_btn)
        box.append(self._main._preview_copy_typst_bar)

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
                                                     self._main.open_bulletin_prefs()))
        box.append(full_prefs_btn)

        pop.set_child(box)
        return pop

    def _toggle_preview_panel(self, _btn=None):
        self._main._preview_visible = not self._main._preview_visible
        visible = self._main._preview_visible
        if hasattr(self._main, "_preview_lbl"):
            if visible:
                self._main._preview_lbl.set_markup("<b>Preview</b>")
            else:
                self._main._preview_lbl.set_text("Preview")
        self._main._preview_panel.set_visible(visible)
        if visible:
            if not self._main._preview_paned_positioned:
                self._main._preview_paned_positioned = True
                def _set_pos():
                    saved = config.ui_panes.get("preview_paned")
                    if saved:
                        self._main._preview_paned.set_position(saved)
                    else:
                        total = self._main._preview_paned.get_allocated_width()
                        pos = max(280, int(total * 0.50)) if total > 300 else 380
                        self._main._preview_paned.set_position(pos)
                    return False
                GLib.idle_add(_set_pos)
            self._start_scroll_poll()
            self._do_preview_update()
        else:
            self._stop_scroll_poll()
            if getattr(self._main, "_preview_pending_id", None) is not None:
                GLib.source_remove(self._main._preview_pending_id)
                self._main._preview_pending_id = None
            self._main._preview_compile_dirty = False

    def _on_bulletin_edit_toggled(self, btn):
        if btn.get_active():
            # Enter edit mode — populate editor if empty
            buf = self._main._bulletin_edit_view.get_buffer()
            s, e = buf.get_bounds()
            current = buf.get_text(s, e, False)
            if not current.strip():
                seed = getattr(self._main, "service_bulletin_text", "").strip()
                if not seed:
                    # Generate a plain-text seed from the auto-generated bulletin
                    seed = self._bulletin_as_plain_text()
                buf.set_text(seed, -1)
            self._main._preview_stack.set_visible_child_name("editor")
        else:
            # Exit edit mode — save editor content
            buf = self._main._bulletin_edit_view.get_buffer()
            s, e = buf.get_bounds()
            text = buf.get_text(s, e, False).strip()
            self._main.service_bulletin_text = text
            self._main._mark_modified()
            self._main._preview_stack.set_visible_child_name("preview")
            self._do_preview_update()

    def _toggle_bulletin_edit(self):
        if hasattr(self._main, "_bulletin_edit_btn"):
            self._main._bulletin_edit_btn.set_active(not self._main._bulletin_edit_btn.get_active())

    def _bulletin_as_plain_text(self) -> str:
        """Produce a plain-text draft of the bulletin for the editor seed."""
        title = self._main.service_title_entry.get_text() or "Order of Service"
        lines = [title, "=" * len(title)]
        for sec, items in self._main._exporter._grouped_entries():
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

    def _schedule_preview_update(self, from_save: bool = False):
        if not getattr(self._main, "_preview_visible", False):
            return
        mode = getattr(self._main, "_preview_update_mode", "auto")
        if mode == "manual":
            return
        if mode == "on_save" and not from_save:
            return
        if getattr(self._main, "_preview_compiling", False):
            # A compile is already running — mark dirty so it re-runs when done
            self._main._preview_compile_dirty = True
            return
        existing = getattr(self._main, "_preview_pending_id", None)
        if existing is not None:
            GLib.source_remove(existing)
        delay = 200 if from_save else 700
        self._main._preview_pending_id = GLib.timeout_add(delay, self._do_preview_update)

    def _do_preview_update(self):
        self._main._preview_pending_id = None
        if not getattr(self._main, "_preview_visible", False):
            return False
        mode = getattr(self._main, "_preview_mode", "bulletin")
        if mode == "bulletin" and hasattr(self._main, "_bulletin_edit_btn") and self._main._bulletin_edit_btn.get_active():
            return False
        if self._main._preview_webview is None:
            return False

        # Hide the bulletin edit button in manuscript mode
        if hasattr(self._main, "_bulletin_edit_btn"):
            self._main._bulletin_edit_btn.set_visible(mode == "bulletin")

        typst = self._main._find_typst()
        if typst:
            if getattr(self._main, "_preview_compiling", False):
                # Already compiling (direct call path) — mark dirty, don't poll
                self._main._preview_compile_dirty = True
                return False
            # Capture Typst source in main thread (GTK widget access required)
            try:
                if mode == "manuscript":
                    typ_src = self._main._exporter._build_manuscript_typst()
                else:
                    typ_src = self._main._exporter._build_bulletin_typst(digital=False)
            except Exception:
                return False
            # Snapshot scroll position now (compile takes seconds; callback fires well before reload)
            _wv = self._main._preview_webview
            if _wv is not None:
                def _snap(source, result, _):
                    try:
                        jr = source.evaluate_javascript_finish(result)
                        if jr is not None:
                            try:
                                self._main._preview_scroll_y = int(jr.get_js_value().to_double())
                            except AttributeError:
                                self._main._preview_scroll_y = int(jr.to_double())
                    except Exception:
                        pass
                try:
                    _wv.evaluate_javascript("window.scrollY", -1, None, None, None, _snap, None)
                except Exception:
                    pass
            self._main._preview_compiling = True
            self._main._preview_spinner.set_visible(True)
            self._main._preview_spinner.start()
            self._main._preview_compiling_lbl.set_visible(True)
            threading.Thread(
                target=self._run_preview_compile, args=(typ_src, typst),
                daemon=True,
            ).start()
            return False

        # Live mode or Typst not found — HTML fallback
        try:
            if mode == "manuscript":
                html = self._main._exporter._build_manuscript_html()
            else:
                html = self._main._exporter._build_bulletin_html()
            self._preview_save_scroll()
            self._main._preview_webview.load_html(html, None)
        except Exception:
            pass
        return False

    def _preview_pdf_path(self) -> Path:
        """Return the stable path used for the live preview PDF (unique per window)."""
        mode = getattr(self._main, "_preview_mode", "bulletin")
        win_id = getattr(self._main, "_preview_window_id", id(self._main))
        cache = Path(GLib.get_user_cache_dir()) / "rubric"
        cache.mkdir(parents=True, exist_ok=True)
        return cache / f"preview_{mode}_{win_id}.pdf"

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
            cmd = self._main._typst_compile_cmd(typst_bin, str(typ_path), str(pdf_path))
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
                    from rubric_package.utils.typst import parse_typst_errors as _pte2
                    _errs2 = _pte2(err)
                    short = format_typst_error(err)[:90]
                    _line2 = _errs2[0]["line"] if _errs2 else None
                    def _show_preview_err(msg=short, line=_line2):
                        _prefix2 = ""
                        if line:
                            _eidx2 = self._main._exporter._item_idx_from_error_line(line)
                            if 0 <= _eidx2 < len(self._main.service_entries):
                                _prefix2 = f"{self._main.service_entries[_eidx2].name}: "
                        self._main._show_toast(f"Preview error — {_prefix2}{msg}", timeout=4)
                    GLib.idle_add(_show_preview_err)
        except subprocess.TimeoutExpired:
            GLib.idle_add(self._preview_compile_done)
        except Exception:
            if typ_path:
                typ_path.unlink(missing_ok=True)
            GLib.idle_add(self._preview_compile_done)

    def _load_preview_pdf(self, pdf_path: str):
        self._main._preview_pdf_loaded = pdf_path
        self._preview_compile_done()
        if self._main._preview_webview:
            self._main._preview_reload_n = getattr(self._main, "_preview_reload_n", 0) + 1
            uri = f"file://{pdf_path}?_r={self._main._preview_reload_n}"
            self._preview_save_scroll()
            self._main._preview_webview.load_uri(uri)
        return False

    def _on_preview_load_changed(self, wv, event):
        if _WebKit and event == _WebKit.LoadEvent.FINISHED:
            y = self._main._preview_scroll_y
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
                GLib.timeout_add(30, _restore)

    def _start_scroll_poll(self):
        """Slow fallback poll (2 s) — the compile-start snapshot handles the real capture."""
        self._stop_scroll_poll()
        def _poll():
            wv = self._main._preview_webview
            if wv is None or not getattr(self._main, "_preview_visible", False):
                self._main._preview_scroll_poll_id = None
                return False
            if getattr(self._main, "_preview_compiling", False):
                return True  # skip while compile is in flight; snapshot handles it
            def _got(source, result, _):
                try:
                    js_result = source.evaluate_javascript_finish(result)
                    if js_result is not None:
                        try:
                            self._main._preview_scroll_y = int(js_result.get_js_value().to_double())
                        except AttributeError:
                            self._main._preview_scroll_y = int(js_result.to_double())
                except Exception:
                    pass
            try:
                wv.evaluate_javascript("window.scrollY", -1, None, None, None, _got, None)
            except Exception:
                pass
            return True
        self._main._preview_scroll_poll_id = GLib.timeout_add(2000, _poll)

    def _stop_scroll_poll(self):
        pid = getattr(self._main, "_preview_scroll_poll_id", None)
        if pid is not None:
            GLib.source_remove(pid)
            self._main._preview_scroll_poll_id = None

    def _preview_save_scroll(self):
        pass  # kept for call-site compatibility; polling handles this now

    def _preview_compile_done(self):
        self._main._preview_compiling = False
        self._main._preview_spinner.stop()
        self._main._preview_spinner.set_visible(False)
        self._main._preview_compiling_lbl.set_visible(False)
        if getattr(self._main, "_preview_compile_dirty", False) and getattr(self._main, "_preview_visible", False):
            self._main._preview_compile_dirty = False
            self._main._preview_pending_id = GLib.timeout_add(200, self._do_preview_update)
        return False

    def _popout_preview(self):
        """Open the current preview in a separate window."""
        if not _WEBKIT_OK:
            return
        mode = getattr(self._main, "_preview_mode", "bulletin")
        title = "Manuscript Preview" if mode == "manuscript" else "Bulletin Preview"
        win = Adw.Window(title=title, transient_for=self._main)
        win.set_default_size(720, 960)
        tv = Adw.ToolbarView()
        hdr = Adw.HeaderBar()
        tv.add_top_bar(hdr)
        wv = _WebKit.WebView()
        wv.set_vexpand(True); wv.set_hexpand(True)
        pdf_path = getattr(self._main, "_preview_pdf_loaded", None)
        if pdf_path and Path(pdf_path).exists():
            wv.load_uri(f"file://{pdf_path}")
        else:
            try:
                if mode == "manuscript":
                    wv.load_html(self._main._exporter._build_manuscript_html(), None)
                else:
                    wv.load_html(self._main._exporter._build_bulletin_html(), None)
            except Exception:
                pass
        tv.set_content(wv)
        win.set_content(tv)
        self._main._preview_popout_win = win  # prevent GC
        win.present()
