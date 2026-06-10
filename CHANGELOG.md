# Rubric — Changelog

All notable changes are documented here, newest first.

---

## 0.17.1-dev — UX polish, season colour, focus mode fixes

### Changed
- YouTube icon is properly sized to YouTube logo proportions (wider than tall)
- Season colour now also applied to week name label and lectionary chip in readings card
- Status bar events spread further apart (larger gap around season dot)
- Scripture insert button labelled "Insert" — Typst not exposed to users
- Inserted scripture passages now display as readable text in the element editor (no raw Typst visible)
- Header bar icons use full-colour system theme variants
- Simple mode also hides GOST and Compact buttons

### Fixed
- Turning off focus mode no longer opens the sidebar if it was closed before focus mode was activated

---

## 0.17.0 — Rich text, snippets manager, rubric section, order panel polish

### Added
- **Rubric section** — a togglable private leader-instructions area above each element's text editor. Text appears red and italic in the manuscript; stripped entirely from the bulletin.
- **Snippets manager window** — the Snippet button opens a full management window with rich-text editing, tagging, and CRUD.
- **Responsive reading redesign** — the reading builder uses a structured row editor; toggled rows appear bold in the bulletin.
- **Element icon picker** — icon button in the element toolbar opens a popover with 30+ symbolic icons.

### Changed
- **Rich text only** — the raw Typst editor toggle has been removed. Content is always edited as rich text.
- **Vertical section tabs** — notebook tabs on the order panel are now left-side vertical tabs with text rotated bottom-to-top.
- **Season colour strip** — a 3px strip at the top of the order panel reflects the current liturgical season colour.
- **Section divider pill** — section divider rows are styled as a rounded pill with a section-coloured dot.
- **Scripture/leader ref as subtitle** — leader references (hymn numbers, scripture citations) appear as the dim subtitle in order list rows.
- **Drag handle fade** — drag handles are invisible at rest and fade in on row hover.
- **Status bar events** — centre shows the closest past and upcoming events with arrows; duplicate dates suppressed.
- **Hymn suggestion pills** — opaque accent colour, white text, no border.
- **Simple mode** — dev button, git status, and time bar hidden in simple mode.
- **Tab key inserts indent** in the element editor (converted to `#h(1.5em)` in Typst output).
- **Leader-note highlight colours** adapt to dark/light system theme.

### Fixed
- Compilation errors from user-entered Typst eliminated by removing raw Typst editor.
- Observance names with embedded date suffixes no longer duplicate the date.

---

## 0.16.0-rc5 — UX polish: wrapping pills, slimmer bar, icons

### Added
- **Suggestion pills wrap** — hymn suggestion strip now uses a flow layout; pills wrap to multiple rows so all suggestions are visible without horizontal scrolling. Full titles shown (no ellipsis), smaller `caption` font.
- **Element type icons** — small symbolic icons appear in service order rows: headphones for hymns/music, bookmark for scripture, body for prayer, text for sermon.
- **Reading chips turn green** after inserting a passage into the service — visual confirmation.
- **Calendar icon on date button** — clearer affordance for the date picker.
- **Liturgical season colour dot** in the status bar centre, next to observance chips.
- **Keyboard shortcuts overlay** — Ctrl+? opens a native GTK shortcuts window listing all key bindings.

### Changed
- **Status bar is slimmer** — reduced padding and margins throughout.

---

## 0.16.0-rc4 — More themes, pill titles only, dead-link fix

### Added
- **5 new hymn themes**: Grief & Lament, Stewardship & Creation Care, Eternal Life & Hope, Gathering & Opening, Courage & Discipleship. Now 24 themes, 280 hymn entries.

### Fixed
- **Dead link**: "I, the Lord of sea and sky" was tagged `MV 177` (wrong); corrected to `VU 509`.
- **Suggestion pills**: title only displayed — hymnal and number moved to tooltip and Hymnary popup. Cleaner and more scannable.

## 0.16.0-rc3 — Themes expanded, aesthetics, compact fix

### Added
- **19 curated hymn themes** (up from 14), sourced from hymnary.org topical index: Advent & Waiting, Christmas & Incarnation, Lent & Repentance, Easter & Resurrection, Pentecost & Holy Spirit, Trinity, Creation & Environment, Justice & Peace, God's Love & Grace, Jesus Christ, Communion & Eucharist, Baptism & Renewal, Community & Welcome, Praise & Worship, Prayer & Meditation, Healing & Comfort, Faith & Trust, Mission & Service, Hope. 228 total hymn entries (was 102).
- **Compact toggle in status bar** — bold when on, regular when off; consistent with SIMPLE/GOST/Focus.

### Changed
- **Suggestion strip**: title leads, hymn number is secondary (dim caption).
- **Compact view fixed and inverted** — now actually compresses row height; rows are spacious by default and shrink to 32 px minimum in compact mode.
- **Selected row accent** — left accent bar on the active service order row.
- **Observance chips** — pill shape in status bar centre.

## 0.16.0-rc2 — Hymn UI redesign

### Changed
- **Hymn toolbar consolidated** — the number entry, lookup button, By Title search, and By Theme search are now all inside a single "Hymn" button that opens a three-tab popover (Lookup / By Title / By Theme). The toolbar is much cleaner.
- **Theme search popover enlarged** — all 14 theme chips now display without scrolling; hymn result list is taller; selected chip uses a toggle style instead of a filled blue button.
- **Suggestion strip redesigned** — flat linked pills (ref bold + title dim + YouTube icon) replace the heavy card buttons; cleaner and consistent with the rest of the UI.
- **Compact mode fix** — compact view now actually reduces row height instead of adding margins.

## 0.16.0-rc1 — Theme search for hymns

### Added
- **Theme search** — new "By Theme" tab in the hymn search popover with 14 curated themes (Baptism, Communion, Community & Welcome, Creation & Environment, Faith & Trust, God's Love & Grace, Healing & Comfort, Holy Spirit, Jesus Christ, Justice & Peace, Mission & Service, Praise & Worship, Prayer & Meditation, Trinity). All entries drawn from VU, MV, and LUS. Click a chip to load hymns; click again to deselect. Click any hymn row to insert it, same as title search.

---

## 0.15.7 — Documentation update

### Changed
- **Documentation** — bundled Help and FAQ fully rewritten for Flatpak-only distribution: removed all references to pipx, pip, apt, zypper, dnf, system dependencies, LaTeX/xelatex, TeX Live, and conditional Typst/WebKit availability; all bundled dependencies are simply available

---

## 0.15.6 — Status bar, GOST Type B, observances, Focus/Git buttons

### Added
- **Status bar** — persistent bar across the bottom of the window (Zerkalo-style)
- **SIMPLE button** — replaces the header toggle; text button in the status bar (bold = on, dim = off)
- **GOST button** — new text button in the status bar; switches the entire GTK UI to GOST Type B engineering font. Font bundled and registered from the app data directory on first launch. Persists between sessions.
- **Focus button** — hides the palette and element list for distraction-free editing; status bar remains accessible. Bold when on.
- **Git button** — commits and pushes the current service to GitHub with one click; runs `pull --rebase` first to avoid conflicts
- **Observance chips** — feast days and liturgical commemorations for the service date now appear as clickable chips in the centre of the status bar (previously shown in the readings card)
- **Observance Wikipedia window** — clicking any chip opens a built-in window that loads the Wikipedia article for that observance (article text only; no sidebars, infoboxes, or navigation)
- **Version chip** — right end of the status bar shows the current version; clicking opens the changelog
- **Opens last file on launch** — Rubric now reopens the most recently saved file automatically on startup

### Changed
- **Hymn lookup** redesigned as a linked pill (text entry + search icon button)
- **Focus mode icon** updated to `eye-not-looking-symbolic` (cleaner BW icon)
- **Service planner icons** bumped from 14 → 18 px (more visible in the panel)
- **Documentation** updated to flatpak-only installation throughout

---

## 0.15.5 — Bug fixes and UX polish

### Fixed
- **ESV translation no longer silently falls back to WEB** — selecting ESV with no API key now shows a clear error message instead of returning World English Bible text without warning.
- **Bulletin `#hymnref` Typst syntax corrected** — hymn lines in the bulletin were emitted with content-block syntax (`[ref][_title_]`) instead of argument syntax (`"ref", [_title_]`), risking compile errors and double-italics.
- **Bulletin toggle opacity now works in tab view** — toggling the 📋 button now correctly dims the row in both flat-list and tabbed service views.
- **Bulletin save errors now surfaced** — disk-full or permissions errors when saving a bulletin `.typ` file are now shown in a dialog instead of being silently swallowed.
- **Hymn lookup injection is now undoable** — inserting a hymn title via the lookup bar now pushes an undo snapshot, so Ctrl+Z reverses it.
- **`compile_typst_pdf` no longer opens file dialog and shows a toast simultaneously** — Ctrl+Shift+P when no `.typ` file is linked now shows a clear instruction toast only.
- **Typst export now warns when service is unsaved** — exporting to `.typ` without a saved `.liturgy` file now shows a toast reminding you to save so the link persists.
- **Snippet button now hidden in Simple mode** — the Snippet button in the item toolbar was always visible; it now hides alongside the Responsive Reading button when Simple mode is on.
- **ESV API key takes effect immediately** — the key now saves on every keystroke in Preferences, so opening the Bible viewer without closing Preferences first uses the correct key.
- **Section delete dialog no longer says "cannot be undone"** — the dialog now correctly states that Undo (Ctrl+Z) is available before saving.

### Changed
- All remaining "LaTeX" labels updated to "Typst" (BibleViewer Insert button, simple-mode tooltip, quickstart tip, folder-picker descriptions).
- `is_special is False` antipattern replaced with `not is_special`.

---

## 0.15.4 — Delete key fix in writing space

### Fixed
- **Delete key now works in text fields** — pressing Delete in the element content editor now deletes the character to the right of the cursor as expected. Previously, a window-level accelerator consumed the keystroke before the text widget saw it. The binding has been moved to a key controller scoped to the service order list, so it only removes list items when the list itself has focus.

---

## 0.15.3 — Flatpak git sync fix

### Fixed
- **Flatpak: git sync now works** — `git` is not available in the GNOME Platform runtime. Rubric now uses `flatpak-spawn --host git` when running inside the sandbox, and requires `--talk-name=org.freedesktop.Flatpak` in finish-args. All git operations (commit, push, pull) now work from the flatpak.

---

## 0.15.2 — Flatpak typst fix

### Fixed
- **Flatpak: PDF preview and export now work** — the bundled Typst binary was installed to `/app/share/rubric/bin/typst` which is not on `$PATH` and was never found by `_find_typst()`. It is now installed to `/app/bin/typst` where `shutil.which` can locate it. All PDF compilation was silently failing in the flatpak build.

---

## 0.15.1 — Preview panel, heading hierarchy, and editing fixes

### Added
- **Manuscript preview** — the live preview panel now has a "Bulletin | Manuscript" toggle. Switching to Manuscript compiles the leader copy (full notes, leader-note blocks included) instead of the congregation bulletin. Bulletin edit mode is hidden when Manuscript is active.

### Fixed
- **Delete key no longer removes service elements while typing** — the Delete accelerator now checks whether a text widget (`GtkText`, `GtkTextView`, `GtkEntry`, `GtkSearchEntry`) has focus; if so, the key behaves as a normal delete character and does not remove the selected element.
- **Preview no longer jumps to top on every compile** — the HTML bulletin preview uses `sessionStorage` to save and restore the scroll position across reloads. The PDF preview writes to a stable fixed path (`~/.cache/rubric/preview_bulletin.pdf` / `preview_manuscript.pdf`) and calls `reload()` instead of `load_uri()` when the URI hasn't changed, preserving the viewer's scroll state.
- **Typst markup in element notes now renders correctly** — `_italic_`, `*bold*`, headings (`= …`, `== …`) and other Typst markup entered in the content editor were being escaped before insertion into the generated `.typ` file, producing literal `\_italic\_`. Content is now inserted verbatim (it is already stored as Typst). `#leader-note[…]` blocks are stripped from bulletin output but preserved in the manuscript.
- **Heading hierarchy corrected** — `TYPST_SHARED` previously had level 2 and 3 swapped relative to normal expectations. Now: `=` (level 1) → large centred bold small-caps section heading (1.3 em); `==` (level 2) → bold small-caps with thin rule below (element heading); `===` (level 3) → slightly smaller plain bold. Service section dividers (`= Gathering`) and item names (`== Prelude`) are generated at the appropriate levels in both the bulletin and manuscript. The HTML fallback also renders Typst heading syntax as styled HTML instead of literal `= text`.

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
