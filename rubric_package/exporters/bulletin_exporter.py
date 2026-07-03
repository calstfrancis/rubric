"""BulletinExporter — Typst generation, compilation, and export/publish flows for Rubric.

Owns the bulletin and manuscript document-building pipeline: HTML/Typst source
generation, typst compilation, PDF export, publishing bulletins to a GitHub
Pages site, and the various export dialogs. Constructed with a reference to the
MainWindow instance it serves; reads and writes shared document state
(service_entries, selected_date, config.bulletin, the toast overlay, etc.) via
that reference rather than owning it, the same composition pattern used by the
GTK windows already extracted into rubric_package/views/.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import threading
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib

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
from rubric_package.models.service import ServiceItem, SectionDivider
from rubric_package.utils.helpers import flatpak_git_prefix
from rubric_package.utils.typst import (
    typst_escape as _typst_escape,
    note_for_typst as _note_for_typst,
    linebreak_fix,
    escape_unmatched_brackets,
    strip_typst_for_html,
    strip_typst_plain,
    strip_leader_notes,
    TYPST_SHARED,
    format_typst_error,
)

_GIT = flatpak_git_prefix()


def _log_compile_error(cmd: list, returncode: int, stderr: str, stdout: str) -> None:
    """Write full typst compile error details to ~/.cache/rubric/compile-error.log."""
    import datetime
    log_dir = Path.home() / ".cache" / "rubric"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "compile-error.log"
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    lines = [
        f"=== {ts} ===",
        f"cmd: {' '.join(cmd)}",
        f"exit: {returncode}",
        "stderr:",
        stderr or "(empty)",
        "stdout:",
        stdout or "(empty)",
        "",
    ]
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write('\n'.join(lines) + '\n')
    except OSError:
        pass
    print('\n'.join(lines), flush=True)


class BulletinExporter:
    """Owns bulletin/manuscript Typst generation, compilation, and export/publish flows."""

    def __init__(self, main_window):
        self._main = main_window

    def _grouped_entries(self):
        cur_t=None; cur_i=[]
        for e in self._main.service_entries:
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
        win = Adw.Window(transient_for=self._main, modal=True, title="Export")
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
        win.set_content(tv)
        win.present()

    def _export_bulletin_html_typst(self) -> None:
        """Export bulletin as HTML, using typst compile --format html (0.13+) or fallback."""
        typst = self._main._find_typst()
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
                cache_dir = Path(GLib.get_user_cache_dir()) / "rubric"
                cache_dir.mkdir(parents=True, exist_ok=True)
                html_path = cache_dir / "bulletin.html"
                result = subprocess.run(
                    self._main._typst_compile_cmd(
                        typst, str(typ_path), str(html_path),
                        extra=["--format", "html"],
                    ),
                    capture_output=True, text=True, timeout=60,
                    encoding="utf-8", errors="replace",
                )
                if result.returncode == 0 and html_path.exists():
                    GLib.idle_add(
                        lambda: Gtk.show_uri(None, html_path.as_uri(), 0))
                    GLib.idle_add(lambda: self._main._show_toast(
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
        override = getattr(self._main, "service_bulletin_text", "").strip()
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

        title    = self._main.service_title_entry.get_text() or "Order of Service"
        date_str = self._main.selected_date.strftime("%-d %B %Y") if self._main.selected_date else ""

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

        _bul_cols = config.preamble.get("bulletin", {}).get("columns", 2)

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
.cols-table  { width: 100%; border-collapse: collapse; }
.col-l       { width: 50%; vertical-align: top; padding-right: 12px; }
.col-r       { width: 50%; vertical-align: top; padding-left: 12px;
               border-left: 1px solid #ddd; }
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

        # Build all service-order groups as HTML fragments, then lay out in columns.
        def _group_html(sec, items):
            parts = []
            visible = [si for si in items
                       if isinstance(si, ServiceItem) and si.show_in_bulletin]
            if not visible and sec is None:
                return ""
            if sec:
                parts.append(f"<h2>{esc(sec)}</h2>")
            for si in visible:
                leader_html = (f"<span class='leader'>({esc(si.leader)})</span>"
                               if si.leader else "")
                parts.append(f"<div class='el'>"
                             f"<div class='el-name'>{esc(si.name)}{leader_html}</div>")
                if si.content_typst:
                    clean = strip_latex(si.content_typst)
                    parts.append(f"<div class='note'>"
                                 f"{clean.replace(chr(10), '<br>')}</div>")
                parts.append("</div>")
            return "".join(parts)

        groups = [_group_html(sec, items) for sec, items in self._grouped_entries()]
        groups = [g for g in groups if g]

        if _bul_cols >= 2 and groups:
            mid = (len(groups) + 1) // 2
            left_html  = "".join(groups[:mid])
            right_html = "".join(groups[mid:])
            lines.append(
                f"<table class='cols-table'><tr>"
                f"<td class='col-l'>{left_html}</td>"
                f"<td class='col-r'>{right_html}</td>"
                f"</tr></table>"
            )
        else:
            lines.append("".join(groups))

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

        title    = self._main.service_title_entry.get_text() or "Order of Service"
        date_str = self._main.selected_date.strftime("%-d %B %Y") if self._main.selected_date else ""

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
            html = self._build_bulletin_html()
            cache_dir = Path(GLib.get_user_cache_dir()) / "rubric"
            cache_dir.mkdir(parents=True, exist_ok=True)
            html_path = cache_dir / "bulletin.html"
            html_path.write_text(html, encoding="utf-8")
            Gtk.show_uri(None, html_path.as_uri(), 0)
            self._main._show_toast("Bulletin opened in browser — use File → Print to print", timeout=6)

    def _print_bulletin_webkit(self):
        """Print the compiled Typst PDF via Poppler, or fall back to HTML."""
        pdf_path = self._main._preview_pdf_path()
        if pdf_path.exists():
            self._print_pdf_poppler(pdf_path)
            return
        # No compiled PDF yet — fall back to HTML
        try:
            mode = getattr(self._main, "_preview_mode", "bulletin")
            html = self._build_manuscript_html() if mode == "manuscript" else self._build_bulletin_html()
        except Exception:
            return
        wv = _WebKit.WebView()
        wv.load_html(html, None)
        self._print_webview = wv  # keep reference alive
        def on_load(view, event):
            if event == _WebKit.LoadEvent.FINISHED:
                op = _WebKit.PrintOperation.new(view)
                op.run_dialog(self._main)
        wv.connect("load-changed", on_load)

    def _print_pdf_poppler(self, pdf_path: Path) -> None:
        """Render each page of a PDF via Poppler into a GtkPrintOperation."""
        try:
            import gi as _gi
            _gi.require_version("Poppler", "0.18")
            from gi.repository import Poppler as _Poppler
            doc = _Poppler.Document.new_from_file(pdf_path.as_uri())
        except Exception:
            return
        n_pages = doc.get_n_pages()
        if n_pages == 0:
            return

        op = Gtk.PrintOperation()
        op.set_n_pages(n_pages)
        op.set_use_full_page(True)
        op.set_unit(Gtk.Unit.POINTS)

        def on_draw_page(_op, ctx, page_num):
            page = doc.get_page(page_num)
            pw, ph = page.get_size()
            cr = ctx.get_cairo_context()
            # Scale to fill the print context, preserving aspect ratio
            cw, ch = ctx.get_width(), ctx.get_height()
            scale = min(cw / pw, ch / ph) if pw and ph else 1.0
            cr.scale(scale, scale)
            page.render_for_printing(cr)

        op.connect("draw-page", on_draw_page)
        try:
            op.run(Gtk.PrintOperationAction.PRINT_DIALOG, self._main)
        except Exception:
            pass

    def _export_bulletin_file(self, digital: bool):
        title = self._main.service_title_entry.get_text() or "bulletin"
        date_str = self._main.selected_date.strftime("%Y-%m-%d") if self._main.selected_date else "undated"
        church = config.bulletin.get("church_name", "").replace(" ", "_") or "Bulletin"
        suffix = "digital" if digital else "print"
        default_name = f"{church}_{date_str}_{suffix}.typ"
        bul_dir = self._main._repo_subdir("bulletins")
        typ_dir = self._main._repo_subdir("typ")
        initial = str(bul_dir) if bul_dir else (str(typ_dir) if typ_dir else config.last_dir)
        dlg = Gtk.FileDialog(title="Save bulletin as…", initial_name=default_name)
        dlg.set_initial_folder(Gio.File.new_for_path(initial))
        filters = Gio.ListStore.new(Gtk.FileFilter)
        f = Gtk.FileFilter(); f.set_name("Typst (*.typ)"); f.add_pattern("*.typ")
        filters.append(f); dlg.set_filters(filters)
        dlg.save(self._main, None, lambda d, r, dig=digital: self._on_bulletin_save(d, r, dig))

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
            self._main._error("Could not generate bulletin", str(e))
            return
        try:
            Path(path).write_text(typ_src, encoding="utf-8")
        except Exception as e:
            self._main._error("Could not save bulletin", str(e))
            return
        self._compile_bulletin_typst(path)

    def _compile_bulletin_typst(self, typ_path_str: str):
        """Compile bulletin .typ to PDF in background thread, then open it."""
        typ_path = Path(typ_path_str)
        typst = self._main._find_typst()
        if not typst:
            self._main._show_toast("Bulletin saved — install typst to compile to PDF", timeout=6)
            return

        pdf_path = typ_path.with_suffix(".pdf")
        # Capture toast locally — _compiling_toast is shared with the manuscript
        # compile path, so if both run simultaneously the shared ref would be wrong.
        _toast = Adw.Toast.new(f"Compiling {typ_path.name}…")
        _toast.set_timeout(0)
        self._main._toast_overlay.add_toast(_toast)

        def run():
            try:
                result = subprocess.run(
                    self._main._typst_compile_cmd(typst, str(typ_path), str(pdf_path)),
                    capture_output=True, text=True, timeout=60,
                    encoding="utf-8", errors="replace",
                )
                GLib.idle_add(self._on_bulletin_compiled, result, typ_path, pdf_path, _toast)
            except subprocess.TimeoutExpired:
                def _on_timeout(t=_toast):
                    try: t.dismiss()
                    except Exception: pass
                    self._main._show_toast("Bulletin compile timed out.", 8)
                GLib.idle_add(_on_timeout)
            except Exception as e:
                def _on_error(msg=str(e), t=_toast):
                    try: t.dismiss()
                    except Exception: pass
                    self._main._show_toast(f"Bulletin compile error: {msg}", 8)
                GLib.idle_add(_on_error)

        threading.Thread(target=run, daemon=True).start()

    def _on_bulletin_compiled(self, result, typ_path: Path, pdf_path: Path,
                              _toast: "Adw.Toast | None" = None):
        try: (_toast or self._main._compiling_toast).dismiss()
        except Exception: pass

        if result.returncode != 0:
            err = (result.stderr or result.stdout or "").strip()
            msg = format_typst_error(err) if err else "typst error"
            self._main._show_toast(f"Bulletin compile failed: {msg[:100]}", timeout=10)
            return

        dest_dir = self._main._repo_subdir("bulletins")
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
            self._main._toast_overlay.add_toast(toast)
            if config.github_repo:
                pub_toast = Adw.Toast.new("Publish bulletin to web?")
                pub_toast.set_timeout(10)
                pub_toast.set_button_label("Publish…")
                pub_toast.connect("button-clicked", lambda _, p=pdf_path: self._publish_bulletin_to_web(p))
                self._main._toast_overlay.add_toast(pub_toast)
            Gtk.show_uri(None, pdf_path.as_uri(), 0)
        else:
            self._main._show_toast("Compiled — PDF not found.", timeout=6)

    def _publish_bulletin_to_web(self, pdf_path: Path):
        """Copy the bulletin PDF to the repo's bulletins/ folder, regenerate the index, and push."""
        repo = config.github_repo
        if not repo:
            self._main._show_toast("Set up a GitHub repo in Preferences first"); return
        bulletins_dir = Path(repo) / "bulletins"
        try:
            bulletins_dir.mkdir(exist_ok=True)
        except OSError as e:
            self._main._show_toast(f"Could not create bulletins/ folder: {e}"); return

        dest = bulletins_dir / pdf_path.name
        if pdf_path.resolve() != dest.resolve() and pdf_path.exists():
            try:
                shutil.copy2(str(pdf_path), str(dest))
            except OSError as e:
                self._main._show_toast(f"Could not copy PDF: {e}"); return

        self._generate_bulletins_index(bulletins_dir)
        self._main._show_toast("Pushing bulletin to GitHub…", timeout=30)

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
                GLib.idle_add(lambda: self._main._show_toast(msg, timeout=12) or False)
            except subprocess.CalledProcessError as e:
                err = (e.stderr or b"").decode(errors="replace").strip()[:120]
                GLib.idle_add(lambda: self._main._show_toast(f"Publish failed: {err}", timeout=10) or False)
            except Exception as exc:
                GLib.idle_add(lambda: self._main._show_toast(f"Publish failed: {exc}", timeout=10) or False)

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
        remote = self._main._detect_github_remote()
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
        svc_title = self._main.service_title_entry.get_text().strip() or "Order of Service"
        date_str = self._main.selected_date.strftime("%-d %B %Y") if self._main.selected_date else ""
        default_subject = f"Sunday Bulletin — {svc_title}" + (f" ({date_str})" if date_str else "")

        win = Adw.Window(transient_for=self._main, modal=True, title="Send Bulletin by Email")
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
        title    = _typst_escape(self._main.service_title_entry.get_text() or "Order of Service")
        date_str = _typst_escape(
            self._main.selected_date.strftime("%-d %B %Y") if self._main.selected_date else "")

        template_name = "bulletin_digital" if digital else "bulletin_print"
        _bul_cols = config.preamble.get("bulletin", {}).get("columns", 2)
        _hdg_override = self._main._preamble._preamble_heading_typst("bulletin")
        parts: list[str] = [
            "// Congregational Bulletin — generated by Rubric",
            self._main._load_typst_preamble(template_name),
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
        for _entry in self._main.service_entries:
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

        # Collect all service-order content into one list so that section
        # headings flow inside the columns block rather than breaking out of it.
        _bul_gutter = config.preamble.get("bulletin", {}).get("gutter", 0.5)
        _all_bul_items: list[str] = []
        for _sec_title, _sec_items in _bul_sections:
            if _sec_title is not None:
                _all_bul_items += [f'= {_typst_escape(_sec_title)}', '']
            for _si in _sec_items:
                _render_bul_item(_si, _all_bul_items)

        if _bul_cols >= 2:
            parts += [
                f'#columns(2, gutter: {_bul_gutter}em)[',
                '\n'.join(_all_bul_items),
                ']',
                '',
            ]
        else:
            parts += _all_bul_items + ['']

        # ── Acknowledgements block ────────────────────────────────────────────
        staff = b.get("staff", [])
        _congregation_leaders = {"all", "congregation", "everyone", "all:"}
        leaders: dict[str, list[str]] = {}
        for entry in self._main.service_entries:
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
        title = self._main.service_title_entry.get_text() or "Order of Service"
        date_str = self._main.selected_date.strftime("%-d %B %Y") if self._main.selected_date else ""


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

        cache_dir = Path(GLib.get_user_cache_dir()) / "rubric"
        cache_dir.mkdir(parents=True, exist_ok=True)
        html_path = cache_dir / "bulletin.html"
        html_path.write_text(html, encoding="utf-8")

        Gtk.show_uri(None, html_path.as_uri(), 0)
        self._main._show_toast("Opened in browser — use File → Print to save as PDF", timeout=6)

    def export_text(self):
        dlg = Gtk.FileDialog(title="Export plain text", initial_name="service.txt")
        dlg.set_initial_folder(Gio.File.new_for_path(config.last_dir))
        filters = Gio.ListStore.new(Gtk.FileFilter); f = Gtk.FileFilter(); f.set_name("Text files (*.txt)"); f.add_pattern("*.txt")
        filters.append(f); dlg.set_filters(filters); dlg.save(self._main, None, self._on_export_text_response)

    def _on_export_text_response(self, dlg, result):
        try: f = dlg.save_finish(result)
        except GLib.Error: return
        path = f.get_path(); title = self._main.service_title_entry.get_text() or "Order of service"
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
        except Exception as e: self._main._error("Export error",str(e))

    def _update_tex_btn(self):
        """Update the Typst button tooltip to reflect current link state."""
        if self._main.typ_file:
            name = Path(self._main.typ_file).name
            self._main.tex_btn.set_tooltip_text(
                f"Export to {name} (Ctrl+E)\nRight-click to change file"
            )
        else:
            self._main.tex_btn.set_tooltip_text(
                "Export to Typst… (Ctrl+E)\nChoose a file to link"
            )

    def _build_manuscript_typst(self) -> str:
        """Build Typst source for the service order / leader manuscript."""
        _ms_cols = config.preamble.get("manuscript", {}).get("columns", 2)
        _ms_hdg_override = self._main._preamble._preamble_heading_typst("manuscript")
        parts = [
            "// Leader Manuscript — generated by Rubric",
            self._main._load_typst_preamble("manuscript"),
            '',
            TYPST_SHARED,
            '',
        ]
        if _ms_hdg_override:
            parts += [_ms_hdg_override, '']

        _ms_show_header = config.preamble.get("manuscript", {}).get("show_header", True)
        if _ms_show_header:
            _ms_church = _typst_escape(config.bulletin.get("church_name", "").strip())
            _ms_title  = _typst_escape(self._main.service_title_entry.get_text().strip() or "Order of Service")
            _ms_date   = _typst_escape(
                self._main.selected_date.strftime("%-d %B %Y") if self._main.selected_date else "")
            parts.append('#align(center)[')
            if _ms_church:
                parts.append(f'  #text(weight: "bold")[#smallcaps[{_ms_church}]]')
                parts.append('  #linebreak()')
            parts.append(f'  #text(size: 1.2em, weight: "bold")[{_ms_title}]')
            if _ms_date:
                parts.append(f'  #linebreak()#text(size: 0.9em)[{_ms_date}]')
            parts += [']', '#v(0.3em)', '#line(length: 100%, stroke: 0.4pt + luma(160))', '#v(0.5em)', '']

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
                target.append(linebreak_fix(escape_unmatched_brackets(si.content_typst)))
            target.append('')

        # Track which Typst line each service item starts on for compile-error attribution.
        preamble_src = "\n".join(parts)
        _cur_line = preamble_src.count('\n') + 2  # +1 for join newline, +1 for 1-based
        self._ms_item_line_map: dict[int, int] = {}  # start_line → service_entries index

        _all_ms_items: list[str] = []
        for sec, items in groups:
            if sec:
                _all_ms_items += [f'= {_typst_escape(sec)}', '']
                _cur_line += 2
            for si in items:
                try:
                    _global_idx = self._main.service_entries.index(si)
                except ValueError:
                    _global_idx = -1
                self._ms_item_line_map[_cur_line] = _global_idx
                _before = len(_all_ms_items)
                _render_ms_item(si, _all_ms_items)
                for _s in _all_ms_items[_before:]:
                    _cur_line += _s.count('\n') + 1

        if _ms_cols >= 2:
            _ms_gutter = config.preamble.get("manuscript", {}).get("gutter", 1.0)
            parts += [
                f'#columns(2, gutter: {_ms_gutter}em)[',
                '\n'.join(_all_ms_items),
                ']',
                '',
            ]
        else:
            parts += _all_ms_items + ['']

        return "\n".join(parts) + "\n"

    def _item_idx_from_error_line(self, line_no: int) -> int:
        """Return service_entries index for the item whose Typst block contains line_no."""
        m = getattr(self, "_ms_item_line_map", {})
        if not m:
            return -1
        best_idx, best_line = -1, -1
        for start, idx in m.items():
            if start <= line_no and start > best_line:
                best_idx, best_line = idx, start
        return best_idx

    def _write_typst(self, path: str) -> bool:
        """Write manuscript Typst to path, record as linked file, save the .liturgy.

        Returns True on success, False if generation or write failed.
        """
        try:
            Path(path).write_text(self._build_manuscript_typst(), encoding="utf-8")
            self._main.typ_file = path
            self._update_tex_btn()
            if self._main.current_file:
                with open(self._main.current_file, "w", encoding="utf-8") as f:
                    json.dump(self._main._service_data(), f, indent=2, ensure_ascii=False)
            else:
                self._main._show_toast("Typst exported — save your service (Ctrl+S) to persist the link.", timeout=5)
            return True
        except Exception as e:
            self._main._error("Export error", str(e))
            return False

    def quick_export_typst(self):
        """One-click export: write directly if linked, else ask for a file."""
        if self._main.typ_file:
            self._write_typst(self._main.typ_file)
        else:
            self.export_typst()

    def _choose_typst_then_compile(self):
        """Open a file-chooser, link the chosen .typ path, then compile."""
        typ_dir = self._main._repo_subdir("typ")
        if self._main.current_file:
            default = Path(self._main.current_file).stem + ".typ"
            folder  = str(typ_dir or Path(self._main.current_file).parent)
        else:
            title   = self._main.service_title_entry.get_text() or "service"
            default = title.replace(" ", "_").lower() + ".typ"
            folder  = config.last_dir
        dlg = Gtk.FileDialog(title="Choose file for leader's notes")
        dlg.set_initial_name(default)
        dlg.set_initial_folder(Gio.File.new_for_path(folder))
        filters = Gio.ListStore.new(Gtk.FileFilter)
        f = Gtk.FileFilter(); f.set_name("Typst files (*.typ)"); f.add_pattern("*.typ")
        filters.append(f); dlg.set_filters(filters)
        dlg.save(self._main, None, self._on_choose_typst_then_compile)

    def _on_choose_typst_then_compile(self, dlg, result):
        try: f = dlg.save_finish(result)
        except GLib.Error: return
        path = f.get_path()
        if not path.endswith(".typ"): path += ".typ"
        if self._write_typst(path):
            self._run_typst_compile()

    def compile_typst_pdf(self):
        """Export to .typ then compile with typst, open the resulting PDF."""
        if not self._main.typ_file:
            self._choose_typst_then_compile()
            return
        if not self._write_typst(self._main.typ_file):
            return
        self._run_typst_compile()

    def _run_typst_compile(self):
        """Compile the linked .typ file to PDF and open the result. Caller must ensure typ_file is set."""
        typ_path = Path(self._main.typ_file)
        pdf_path = typ_path.with_suffix(".pdf")

        typst = self._main._find_typst()
        if not typst:
            self._main._show_toast("typst not found — install typst or add it to PATH", timeout=8)
            return

        _ms_toast = Adw.Toast.new("Compiling PDF…")
        _ms_toast.set_timeout(0)
        self._main._toast_overlay.add_toast(_ms_toast)
        self._main._compiling_toast = _ms_toast
        self._main.pdf_btn.set_sensitive(False)

        def run_typst():
            try:
                cmd = self._main._typst_compile_cmd(typst, str(typ_path), str(pdf_path))
                result = subprocess.run(
                    cmd,
                    capture_output=True, text=True, timeout=60,
                    encoding="utf-8", errors="replace",
                )
                if result.returncode != 0:
                    _log_compile_error(cmd, result.returncode, result.stderr, result.stdout)
                GLib.idle_add(self._on_compile_done, result, typ_path, pdf_path, _ms_toast)
            except subprocess.TimeoutExpired:
                GLib.idle_add(self._on_compile_error, "typst timed out after 60 seconds.", _ms_toast)
            except Exception as e:
                GLib.idle_add(self._on_compile_error, str(e), _ms_toast)

        threading.Thread(target=run_typst, daemon=True).start()

    def _on_compile_done(self, result, typ_path: Path, pdf_path: Path,
                         _toast: "Adw.Toast | None" = None):
        self._main.pdf_btn.set_sensitive(True)
        try: (_toast or self._main._compiling_toast).dismiss()
        except Exception: pass

        if result.returncode != 0:
            err = (result.stderr or result.stdout or "").strip()
            from rubric_package.utils.typst import parse_typst_errors as _pte
            _errs = _pte(err) if err else []
            msg = format_typst_error(err) if err else "typst error"
            _line = _errs[0]["line"] if _errs else None
            _prefix = ""
            if _line:
                _eidx = self._item_idx_from_error_line(_line)
                if 0 <= _eidx < len(self._main.service_entries):
                    _prefix = f"{self._main.service_entries[_eidx].name}: "
            self._main._show_toast(
                f"Compile error — {_prefix}{msg[:100]} (see ~/.cache/rubric/compile-error.log)",
                timeout=15,
            )
            return

        pdf_dir = self._main._repo_subdir("pdf")
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
            self._main._toast_overlay.add_toast(toast)
            Gtk.show_uri(None, pdf_path.as_uri(), 0)
        else:
            self._main._show_toast("Compiled but PDF not found.", timeout=6)

    def _on_compile_error(self, message: str, _toast: "Adw.Toast | None" = None):
        self._main.pdf_btn.set_sensitive(True)
        try: (_toast or self._main._compiling_toast).dismiss()
        except Exception: pass
        self._main._show_toast(f"Compile error: {message[:80]}", timeout=10)

    def _unlink_typ(self):
        self._main.typ_file = None
        self._update_tex_btn()

    def export_typst(self):
        """Full file-chooser export for the manuscript Typst file."""
        typ_dir = self._main._repo_subdir("typ")
        if self._main.current_file:
            default = Path(self._main.current_file).stem + ".typ"
        else:
            title   = self._main.service_title_entry.get_text() or "service"
            default = title.replace(" ", "_").lower() + ".typ"
        folder = str(typ_dir) if typ_dir else (
            str(Path(self._main.current_file).parent) if self._main.current_file else config.last_dir
        )
        dlg = Gtk.FileDialog(title="Export Typst", initial_name=default)
        dlg.set_initial_folder(Gio.File.new_for_path(folder))
        filters = Gio.ListStore.new(Gtk.FileFilter)
        f = Gtk.FileFilter(); f.set_name("Typst files (*.typ)"); f.add_pattern("*.typ")
        filters.append(f); dlg.set_filters(filters)
        dlg.save(self._main, None, self._on_export_typst_response)

    def _on_export_typst_response(self, dlg, result):
        try: f = dlg.save_finish(result)
        except GLib.Error: return
        path = f.get_path()
        if not path.endswith(".typ"): path += ".typ"
        self._write_typst(path)

