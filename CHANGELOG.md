# Rubric — Changelog

All notable changes are documented here, newest first.

---

## 0.15.0 — Typst polish, packaging, and documentation

### Added
- **Typst syntax highlighting** — the Typst mode editor now uses GtkSourceView 5 (if installed) with a bundled `typst.lang` language definition covering headings, bold, italic, function calls, comments, math, labels, and all Rubric-specific keywords. Falls back to plain monospace editor if GtkSourceView is unavailable.
- **Preferences → Typst Files** — in-app editor for the four Typst preamble templates (`bulletin_print`, `bulletin_digital`, `manuscript`, `_shared`). Edit opens a GtkSourceView editor with Typst highlighting; Save override writes to `~/.config/rubric/templates/` (persists across upgrades); Reset to default removes the override.
- **Structured error messages** — `typst compile` stderr is now parsed into structured errors (message + file:line:col). All three compilation paths (bulletin, manuscript, preview) show a short human-readable message including the line number.
- **`mark_error_line()`** on `ElementContentWidget` — highlights the error line in Typst mode when GtkSourceView is available.
- **Typst binary bundled in packages** — `build-deb.sh` and `build-rpm.sh` now include the system `typst` binary at build time (`/usr/share/rubric/bin/typst`, `chmod 755`).

### Changed
- **`.gitignore`** — added Typst temp preview files (`rubric_preview_*.typ/pdf`) and `rubric_package/bin/` (bundled binary path, too large for git).
- **`metainfo.xml`** — removed all LaTeX references; updated feature list to describe Typst, rich text editor, and live preview.
- **`README.md`**, **`HELP.md`**, **`FAQ.md`** — LaTeX/xelatex references replaced with Typst throughout. Content editor (rich text + Typst mode toggle) documented. New Typst Templates section in HELP. New "Typst and PDF" FAQ section.
- **`install.sh`** — removed xelatex dependency check; added typst binary detection and chmod step.
- Version bumped to **0.15.0**.

---

## 0.14.8 — Sidebar, startup ordering, background hymn downloads

### Fixed
- **Sidebar no longer starts half-visible** — pane position was set before GTK had allocated the widget's size; deferred to first idle so it takes effect correctly.
- **Restore unsaved work dialog now appears after the changelog** — on first launch after an update, the autosave restore prompt was appearing simultaneously with (and fighting over) the What's New dialog. It now fires only after the changelog is dismissed.
- **Hymn downloads continue in background** — closing the setup wizard while a hymn title download is running no longer abandons it. Progress callbacks are safely guarded; a toast notification appears on the main window when the download finishes.
- **Hymn title scraping: og:title first** — Hymnary.org now renders page titles via JavaScript; the static `<title>` tag returns just "Hymnary.org". Switched to reading the `og:title` meta tag, which is set server-side, plus a more browser-like User-Agent. Also moved the rate-limit sleep to apply on every request (not only when a title is found).

---

## 0.14.7 — Compact view actually compact

### Fixed
- **Compact view now reduces row height** — the previous CSS was adding padding to divider rows (making them taller) while having no effect on service-item rows at all. Rewritten to correctly reduce `Adw.ActionRow` internal padding and shrink divider row margins.

---

## 0.14.6 — Clear pre-filled Scripture/Psalm, package dependencies

### Fixed
- **Scripture and Sung Psalm no longer pre-filled** — "Start with today's lectionary" was injecting the RCL reading references into the notes of the Scripture and Sung Psalm elements. Those fields now start empty so you can look up and insert the text yourself.

### Changed
- **`git` added as a package dependency** — the deb and RPM now declare `git` as a required dependency so GitHub sync works out of the box on a fresh install.
- **WebKit added as a package dependency** — `gir1.2-webkit2-4.1` (deb) and `typelib-1_0-WebKit-6_0` (RPM/openSUSE) are now required dependencies, ensuring the live bulletin preview panel is available without a separate install step.
- **hunspell / pandoc** — neither is used by Rubric; confirmed not added.

---

## 0.14.5 — Welcome wizard fixed, GitHub sync improved

### Fixed
- **Welcome wizard buttons dead** — `close-request` handler in the setup wizard returned a truthy integer (the `GLib.idle_add` callback ID) instead of `False`, telling GTK not to close the window. The dialog was permanently stuck — the X button did nothing and the app could not be quit. Fixed to always return `False`.
- **Double first-launch wizard** — when the setup wizard finished, the `_show_first_launch_wizard` callback was scheduled twice (once from `close-request`, once from `_close()`), stacking two modal windows. Removed the duplicate call.
- **Welcome choice rows unreliable** — the `activated` signal on `Adw.ActionRow` with `SelectionMode.NONE` was not consistently firing on click. Switched to `lb.connect("row-activated", …)` on the `Gtk.ListBox`, which is reliable in all libadwaita versions.

### Changed
- **GitHub sync: pull before push** — the sync button now pulls remote changes (with `--rebase`) before pushing, so two computers using the same repository don't get rejected pushes. If a genuine conflict exists, the rebase is aborted cleanly and a clear message explains what happened.
- **GitHub auth error now actionable** — authentication failures show step-by-step instructions for creating a Personal Access Token and storing credentials with `git credential.helper store`, instead of just pointing at a URL.

---

## 0.14.4 — deb and RPM packages

### Added
- **`build-deb.sh`** — builds a native Debian/Ubuntu `.deb` package for system-wide installation using only standard Linux tools (`ar`, `tar`, `gzip` — no dpkg-deb required). Installs the app to `/usr/share/rubric/`, the launcher to `/usr/bin/rubric`, and registers desktop integration (`.desktop` entry, icons, MIME type, AppStream metainfo). Includes post-install hooks to update the MIME database, desktop database, and icon cache. Depends on `python3-gi`, `gir1.2-gtk-4.0`, and `gir1.2-adw-1`.
- **`build-rpm.sh`** — builds a native `.rpm` package using `rpmbuild`. Generates a spec file with distro-conditional dependencies (openSUSE typelibs vs Fedora `gtk4`/`libadwaita`). Includes `%post`/`%postun` hooks using openSUSE RPM macros or plain `update-*` commands depending on the build host. Output RPM goes to the project directory ready to install with `zypper` or `dnf`.

---

## 0.14.3 — Simple mode switch label, in-app changelog, Help/FAQ available in all installs

### Changed
- **Simple switch label** — the Simple mode toggle in the header bar now shows a "Simple" label beside the switch for clarity.
- **In-app changelog always available** — the What's New tab in the Welcome wizard and the Help window now show the full changelog in pip/pipx/deb/rpm installs, not just git-clone installs.
- **Help and FAQ in all installs** — HELP.md, FAQ.md, and CHANGELOG.md are now bundled in the package data so they're available regardless of how Rubric is installed.

---

## 0.14.2 — PyPI release, Service archive, element library, bulletin preview, UX polish

### Added (this release)

- **Past Liturgies archive** (Ctrl+Shift+H) — dedicated browser window for all your saved services. Shows services newest-first; click any row to expand and read every element with its full leader notes. Notes are displayed in plain text (LaTeX stripped). Each service has an **Open in editor** button; each element has an **Insert** button to copy its text into the currently selected element. Search bar filters by service title, date, or element content.
- **Element Library** (Ctrl+Shift+K) — searchable library of every element from every saved service. Browse by service (click to expand) or type to filter by element name, notes, or leader. Insert any past element's notes into the current service with one click.
- **Bulletin preview panel** — a live preview panel (toggle in the header bar) shows the congregational bulletin as it will print. In simple mode shows HTML; in advanced mode with xelatex compiles a real PDF in the background with a spinner. A **⚙ gear icon** in the preview header offers quick access to print/digital mode and church name without opening the full preferences dialog. A **popout button** opens the preview in its own floating window.
- **Welcome wizard re-trigger** — hamburger menu → Help → **Welcome wizard…** re-opens the first-launch wizard at any time.
- **Recently-used palette section** — elements you've added appear in a "Recently used" group at the top of the palette for quick access. Tracks the 6 most recent.
- **Palette section expanders** — each section in the palette is collapsible. All sections expand automatically when you type in the search box.
- **Hymn cache status bar** — shows how many hymn titles are cached ("📚 N hymns cached") with a **Clear** button.
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

- **Notes not appearing when opening a saved file** — the root cause was a Python class identity mismatch: when the refactored package is present, service items loaded from files were being created as *package* `ServiceItem` instances, while `isinstance()` checks throughout the UI were testing against the *inline* `ServiceItem` class. The isinstance tests silently failed, causing the notes buffer to always be cleared instead of populated. Fixed by not overriding `_entry_from_dict` in the compatibility alias block.
- **Bulletin text not propagating to the preview** — the same isinstance mismatch prevented `_on_bulletin_notes_changed` from writing typed text back to the entry object, so the preview never reflected what was typed. Fixed as above.
- **Bulletin preview LaTeX escape artifacts** — `\hspace*{1em}as` was rendering as `1emas` because the generic argument-stripping regex ran before the spacing-command stripper. Fixed by pre-stripping `\hspace` and `\vspace` before the generic pass.
- **Bulletin preview "URL can't be shown"** — WebKit `load_html` was called with `"about:bulletin"` as the base URI; changed to `None`.
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
