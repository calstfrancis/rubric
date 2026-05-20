# Rubric — Changelog

All notable changes are documented here, newest first.

---

## 0.12 — GitHub sync, planner, simple mode, redo, HTML export

### Added (this release)

- **First-launch wizard** — on first open, a full-screen modal offers three clear choices: *Start with today's lectionary* (pre-fills a standard Sunday order with RCL readings for today), *Blank service* (opens a clean document), or *Show me around* (opens the Help guide and tip strip). Completed flag is saved to config so the wizard does not repeat.
- **Lectionary seeding** — "Start with today's lectionary" builds a complete four-movement order (Gathering → Word → Response → Sending) with standard element names and injects the current week's RCL reading references directly into the relevant notes fields.
- **Quickstart tip strip** — a dismissible banner below the readings card cycles through six short tips covering core features. Advances with "Next tip →"; permanently dismissed with ✕. Dismissed state persists in config.
- **Liturgical calendar intelligence layer** (`observances.py`) — the readings card now shows relevant observances for the service date as a compact labelled row:
  - **Fixed dates** — 40+ dates including All Saints (Nov 1), Remembrance Day (Nov 11), Orange Shirt Day (Sep 30), Earth Day (Apr 22), World AIDS Day (Dec 1), International Women's Day (Mar 8), and more
  - **Date ranges** — Season of Creation (Sep 1–Oct 4), Pride Month (June), Week of Prayer for Christian Unity (Jan 18–25), 16 Days of Activism Against Gender-Based Violence (Nov 25–Dec 10)
  - **Computed / moveable observances** — Indigenous Sunday (Sunday nearest Jun 21), Earth Sunday (Sunday nearest Apr 22), Pride Sunday (last Sunday of June), Creation Sunday (first Sunday of September), Remembrance Sunday (Sunday nearest Nov 11), All Saints Sunday (Sunday nearest Nov 1), Canadian Thanksgiving (second Monday of October), World Day of Prayer (first Friday of March)
  - **Proximity scanning** — when the service date is a Sunday, observances falling Mon–Sat of the same week appear with a proximity tag (e.g. "this Wednesday")
  - **Type badges** — each observance is tagged and coloured by category: Feast, Saint, Ecumenical, Indigenous, Social Justice, Ecological, Pride, Remembrance, UCC
- **Two-row item toolbar** — the single scrolling strip is replaced by two clean rows: row 1 has Leader (expanding) and Bulletin toggle; row 2 has Scripture, Hymn (contextual, appears only for hymn-type elements), Snippet, and Responsive Reading.
- **"Leader notes" / "Bulletin text" tabs** — the notes panel tabs are renamed for clarity. Selecting any element automatically switches to "Leader notes" so scripture references injected from a loaded file are always visible immediately.

### Fixed

- **Bulletin preview "URL can't be shown"** — WebKit `load_html` was called with `"about:bulletin"` as the base URI; changed to `None`.
- **Scripture notes from loaded files not appearing** — the notes panel auto-switches to the Leader notes tab on item selection, so notes that were previously visible only after manually switching tabs now appear immediately.
- **Notes edits not exporting to xelatex** — same root cause as above; typing in the Bulletin text tab updated `bulletin_note` not `note`. Auto-switching to Leader notes on selection prevents the mismatch.
- **`_reset_state` note clear firing spurious `changed` signal** — buffer clears in `_reset_state` are now wrapped in the `_updating_note` guard.

### Added

- **Simple mode** (on by default) — hides LaTeX export buttons, GitHub sync, CSV export, snippets, responsive reading, and the LaTeX preamble preference from new users. Toggle in **Preferences → View → Simple mode**. All features remain fully accessible when turned off; keyboard shortcuts continue to work regardless.
- **Redo** (Ctrl+Shift+Z) — redo button added to the header bar beside undo. Any new action clears the redo stack.
- **HTML export** (hamburger menu → Export) — generates a clean, print-ready HTML file and opens it in the default browser. Use File → Print in the browser to produce a PDF without LaTeX. Handles scripture blocks, bold/italic markup, and section headings.
- **Bulletin export → HTML in simple mode** — in simple mode, Export Bulletin bypasses LaTeX entirely and opens an HTML bulletin in the browser. Includes church name, service details, order of service (bulletin-visible elements only), active announcements, staff list, mission statement, and accessibility note. Expired announcements are filtered automatically.
- **GitHub repository sync** — set up a local git repository from **Preferences → GitHub** and push/pull to GitHub with one click (⟳ toolbar button or Ctrl+Shift+G). Features:
  - Guided setup: browse to a folder, click Set up — creates `liturgy/`, `tex/`, `pdf/`, `bulletins/` subfolders, a LaTeX-aware `.gitignore`, and runs `git init`
  - Remote URL field + Connect button to link a GitHub repository
  - Pull button in Preferences for downloading changes from another machine
  - Automatic commit message from the service title and date — no typing required
  - First-push upstream tracking handled automatically
  - Friendly error messages for auth failures and missing remotes
- **Repository-aware default save paths** — when a GitHub repository is configured, Save As defaults to `repo/liturgy/`, Export LaTeX to `repo/tex/`, Export Bulletin (advanced mode) to `repo/bulletins/`, and compiled PDFs move automatically to `repo/pdf/` (service order) or `repo/bulletins/` (bulletin).
- **Service Planner** (hamburger menu → Service Planner, Ctrl+Shift+L) — scans the `liturgy/` folder and lists all `.liturgy` files grouped into Upcoming and Past, sorted by date, showing element count. Click any row to open that service. If no repository is configured, prompts to choose a folder. Refresh button to rescan.
- **Scripture translation selector** (Preferences → Scripture) — choose between:
  - **WEB** (World English Bible) — public domain, works with no setup
  - **KJV** (King James Version) — public domain
  - **ASV** (American Standard Version) — public domain
  - **ESV** — free API key from api.esv.org; ministry and bulletin use explicitly permitted
  - The Bible Viewer title and attribution line update to match the selected translation.

### Fixed

- **Bulletin compile error (memoir class)** — in simple mode, bulletin export no longer attempts LaTeX compilation at all, bypassing the `memoir` class requirement that caused silent failures on minimal TeX Live installations.
- **Bulletin compile error reporting** — `result.stderr` was never checked; both stdout and stderr are now combined when looking for xelatex error lines.
- **Bulletin PDF compile threading violation** — GTK calls in error paths now go through `GLib.idle_add`.
- `SyntaxWarning: invalid escape sequence '\s'` on launch — caused by `\sverse` in a non-raw docstring.
- Hymn title from Hymnary now correctly strips the book name prefix.
- Multi-line verse joining in `_passage_to_latex`.
- **Boilerplate text group in Bulletin prefs** — closure capture bug fixed.

---

## 0.11 — Bulletin export and lectionary tracker

### Added
- **Congregational bulletin export** (Ctrl+Shift+B) — generates a separate PDF for pew use from the same service file.
  - **Print / booklet** — `memoir` class, half-letter (5.5 × 8.5 in), fold for saddle-stitch
  - **Digital / screen** — `extarticle`, full letter, colour hyperlinks
- **Per-element bulletin toggle** — 📋 button marks each element shown or hidden in the bulletin independently of the leader copy
- **Bulletin preferences tab** — church name, address, service time, website, email, phone, welcome line, accessibility note, mission statement, staff/contact list, announcements with optional expiry dates
- **Lectionary year tracker** — persistent Year A/B/C and season indicator in the header
- **Per-Proper hymn suggestions** (Propers 4–29)
- **Hymn data moved to JSON** — `data/hymn_suggestions.json`
- **Inline Hymnary preview** — WebKit panel if available
- **Hymn suggestion injection** — right-click injects into selected element
- **GitHub Actions CI**

---

## 0.10 — Scripture layout, compile improvements, menu cleanup

### Added
- **Compile to PDF** button (Ctrl+Shift+P)
- **YouTube search** link beside hymn suggestion chips
- **Prayers of the People**, **Benediction**, **Lord's Prayer** snippets
- **Help/FAQ/What's New** in hamburger menu

---

## 0.9 — Space-saving UI and export improvements

### Added
- **Leader assignment** field per element
- **Responsive reading builder** (Ctrl+R)
- **Snippets library** (Ctrl+Shift+I)
- **Scripture search bar** in item toolbar
- **Hymn suggestions strip**
- **CSV export**
- **Git integration**
- **Two-column layout** per liturgical movement in LaTeX export

---

## 0.8 — Title popover and resizable notes

### Added
- Service title and date moved into header popover
- Resizable Notes/Content pane
- Quick LaTeX export button (Ctrl+E)
- Multiple named templates with chooser dialog
- Recent files submenu

---

## 0.7 — Weekday RCL and hymn lookup

### Added
- Weekday Sunday stepper
- Autosave every 3 minutes with recovery
- Duplicate service

---

## 0.6 — Tab view and section management

### Added
- Tab view toggle
- Tab right-click for Rename and Delete
- Drag-and-drop between tabs
- Note preview as row subtitle

---

## 0.5 — Bible viewer and hymn lookup

### Added
- Bible viewer with WEB text and LaTeX insert
- Hymn lookup from Hymnary.org
- Liturgical colour bar

---

## 0.4 — RCL date picker and preferences

### Added
- Calendar date picker, RCL readings card, liturgical colour
- Preferences window

---

## 0.3 — LaTeX export

### Added
- Full xelatex-compatible export (Junicode, geometry, titlesec)

---

## 0.2 — GTK4/libadwaita rewrite

Complete rewrite from PySide6 to GTK4 + libadwaita.

---

## 0.1 — Initial release

Basic service order builder with palette, drag-and-drop, notes, save/load, plain text export, undo.
