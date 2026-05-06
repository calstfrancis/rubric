# Rubric — Changelog

All notable changes are documented here, newest first.

---

## Unreleased (v0.12)

### Added
- **Congregational bulletin export** (Ctrl+Shift+B) — generates a separate PDF for pew use from the same service file.
  - **Print / booklet** — `memoir` class, half-letter (5.5 × 8.5 in), designed to fold for saddle-stitch. Cover page with church name and service details; order of service in two-column layout; acknowledgements block with staff names and leader assignments; announcements page; back page with mission statement and contact info.
  - **Digital / screen** — `extarticle`, full letter, colour hyperlinks via `xcolor`/`hyperref`.
- **Per-element bulletin toggle** — the 📋 button on the item toolbar marks each element as shown or hidden in the congregational bulletin independently of the leader copy. Hidden elements are visually dimmed in the order list.
- **Bulletin preferences tab** in Preferences — church name, address, service time, website, email, phone; welcome line; accessibility note; mission statement (multi-line); staff/contact list (role, name, optional email for digital links); announcements list.
- **Announcement expiry** — each announcement accepts an optional `YYYY-MM-DD` expiry date; outdated announcements are silently omitted when the bulletin is generated.
- **Lectionary year tracker** in the header bar — a small coloured dot and "Year A · Advent" label showing today's RCL year and season at all times. Updates at midnight. Tooltip shows the full week name.
- **Per-Proper hymn suggestions** (Propers 4–29) — Ordinary Time now returns hymns specific to each Proper's themes rather than generic suggestions. Blends with the season pool for variety.
- **Hymn data moved to JSON** — `data/hymn_suggestions.json` replaces the hard-coded Python dict; easier to extend without touching source code.
- **Inline Hymnary preview** — if `python3-webkit2` (or WebKit 6.0) is installed, clicking a hymn suggestion chip opens an inline browser panel rather than switching to an external browser. Falls back to the system browser if WebKit is not available.
- **Hymn suggestion injection** — right-clicking a suggestion chip now injects the hymn reference into the *selected element's* Notes/Content instead of creating a new element.
- **GitHub Actions CI** — automated `python3 -m unittest` run on every push and pull request.

### Fixed
- **Bulletin PDF compile threading violation** — `_compiling_toast.dismiss()` was called directly from the background thread on timeout/exception, which could crash silently and prevent the error toast from appearing. All GTK calls in error paths now go through `GLib.idle_add`.
- **Bulletin compile error reporting** — `result.stderr` was never checked; both stdout and stderr are now combined when looking for xelatex error lines, so "File 'memoir.cls' not found" and similar errors surface correctly.
- **`memoir` missing from install instructions** — the in-app TeX Live tab and README omitted `memoir` from both the `tlmgr` and `zypper` install commands; this was the most likely cause of the bulletin compile producing no PDF.
- `SyntaxWarning: invalid escape sequence '\s'` on launch — caused by `\sverse` in a non-raw docstring. Fixed by making the docstring a raw string (`r"""`).
- Hymn title from Hymnary now correctly strips the book name prefix. "Voices United: The Hymn and Worship Book... 16. Mary, woman of the promise" → "Mary, woman of the promise".
- Multi-line verse joining in `_passage_to_latex` — the WEB API returns some verses split across multiple lines; these are now joined into a single `\sverse` call so continuation lines wrap correctly.
- **Boilerplate text group in Bulletin prefs** — "Welcome line" and "Accessibility note" were being added to the Church information group instead of Boilerplate text due to a closure capture bug in `_build_bulletin`.
- Removed dead `pdf_path` variable in `_on_bulletin_save` (computed but never used).
- All inline `import re`, `import subprocess`, `import shutil`, `import threading` calls moved to top-level imports.

---

## 0.10 — Scripture layout, compile improvements, menu cleanup

### Added
- **Compile to PDF** button (print icon, Ctrl+Shift+P) — xelatex in background thread, toast-only feedback ("Compiling PDF…" stays until done, then "✓ filename.pdf"). No dialogs to dismiss.
- **YouTube search** link (▶) beside each hymn suggestion chip.
- **Prayers of the People** snippet with full preamble/praise/lament/asks/intercession/silence/inclusion structure.
- **Benediction** and **Lord's Prayer (traditional poetic)** snippets from actual service text.
- **Help/FAQ/What's New** in hamburger menu — rendered Markdown with heading sizes, bold, code spans, horizontal rules.

### Fixed
- Scripture `{scripture}` environment: `\setlength{\parskip}{0pt}` suppresses inter-verse spacing; `\leftskip=2.4em` + `\parindent=-2.4em` gives hanging indent (verse number flush-left, continuation lines indented 2.4em).
- `\sverse{N}{text}` macro — simple `\textsuperscript{#1}\quad #2\par`, all indent logic in the environment.
- Compile toasts replace all dialogs — no more overlapping windows.
- Hamburger menu reorganised: Export section (LaTeX, plain text, CSV), Help section.

---

## 0.9 — Space-saving UI and export improvements

### Added
- **Leader assignment** field per element — right-aligned italic name in `\section*` heading on export.
- **Responsive reading builder** (Ctrl+R / ℟ button) — L:/P: syntax generates LaTeX with bold/italic speaker labels.
- **Snippets library** (Ctrl+Shift+I / ✂ button) with default liturgical texts. Managed in Preferences → Snippets tab.
- **Scripture search bar** in item toolbar — fetch any Bible reference directly.
- **Hymn suggestions strip** — season/week-appropriate VU/MV/LUS suggestions appear when a date is set. Left-click → Hymnary, right-click → inject into selected element.
- **CSV export** — Section, Element, Leader, Hymn ref, Notes preview.
- **Git integration** (Ctrl+Shift+G) — stages and commits `.liturgy` and linked `.tex` file.
- **Two-column layout** per liturgical movement in LaTeX export using `multicol`.
- Parts (`\newpage` + centred heading) — no rule; sections (`\section*`) keep `\titlerule`.
- Date passed to `\date{}` in LaTeX export.
- `extarticle` document class, margins 0.5in left/right.

### Changed
- Season/year/dot and RCL reading buttons condensed into one row.
- Year badge removed (duplicated in week string).
- Leader, Scripture, Hymn lookup merged into single item toolbar. Snippets and Responsive buttons in same toolbar.
- "Notes / Content" label removed.
- "Suggested hymns" label removed from suggestion strip.

---

## 0.8 — Title popover and resizable notes

### Added
- **Service title and date** moved into header popover — click the window title to open.
- **Resizable Notes/Content pane** via vertical `GtkPaned`.
- **Quick LaTeX export button** (Ctrl+E) — one-click to linked file; right-click to change/unlink.
- `tex_file` path stored in `.liturgy` JSON and restored on open.
- **Multiple templates** — named, with chooser dialog. Old single-template config migrated.
- **Recent files** submenu (last 10).

### Fixed
- "Error opening file: must be number, not str" — `TextBuffer.set_text("", "")` → `set_text("", -1)`.

---

## 0.7 — Weekday RCL and hymn lookup

### Added
- **Weekday Sunday stepper** — weekday dates show next Sunday's readings with ← → navigation.
- **Autosave** every 3 minutes with recovery on next launch.
- **Duplicate service** in hamburger menu.

### Fixed
- Tab view selection loop, template not loading at startup.

---

## 0.6 — Tab view and section management

### Added
- **Tab view** toggle (Preferences → View).
- Tab right-click for Rename and Delete section.
- Drag-and-drop between tabs.
- Note preview (first 5 words) as row subtitle.

---

## 0.5 — Bible viewer and hymn lookup

### Added
- **Bible viewer** — fetches WEB text, "Insert as LaTeX" adds `{scripture}` block.
- **Hymn lookup** — `VU 16` fetches title from Hymnary, cached locally.
- **Liturgical colour bar** using Cairo DrawingArea.

---

## 0.4 — RCL date picker and preferences

### Added
- Calendar date picker, RCL readings card, liturgical colour.
- `Adw.PreferencesWindow` with LaTeX, Template, Palette tabs.

---

## 0.3 — LaTeX export

### Added
- Full `xelatex`-compatible export (Junicode, geometry, titlesec).
- Notes/Content passed through as raw LaTeX or escaped plain text.

---

## 0.2 — GTK4/libadwaita rewrite

Complete rewrite from PySide6 to GTK4 + libadwaita.

---

## 0.1 — Initial release

Basic service order builder with palette, drag-and-drop, notes, save/load, plain text export, undo.
