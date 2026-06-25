# Rubric — Changelog

All notable changes are documented here, newest first.

---

## [0.17.8] "Still Water" — Print quality, layout fidelity, and persistent settings

### Added

- **Multi-window support** — a new-window button (⧉) in the header bar and `Ctrl+Shift+N` open a second independent window in the same process. Useful for comparing services side-by-side.
- **Live Typst preview** — a side-by-side preview panel compiles the service to PDF via Typst and renders it live. Compile mode (Auto / Save / Manual) is a cycle button in the justice bar; a ⟳ button in the preview header forces an immediate compile. Defaults to Save mode.
- **Compact title header for manuscript** — toggle in manuscript Layout settings to show a centred church name / title / date header with a thin rule above the body text.
- **Pane widths remembered across sessions** — the order list / notes split, the element palette width, and the preview panel width are restored on next launch.
- **Rubric area is now drag-to-resize** — the leader instructions panel is a draggable pane divider rather than a fixed-height box.

### Changed

- **Preview compile mode button in justice bar** — Auto/Save/Manual is a single cycle button on the right side of the justice dates bar, keeping the preview header clean.
- **Deferred autosave extended to 15 s** — prevents Save mode from recompiling on every keystroke during active editing.

### Fixed

- **Print button now sends the Typst-compiled PDF to the printer** — uses Poppler to render each page into a `GtkPrintOperation`, preserving fonts, columns, and layout. Falls back to HTML (with table-based 2-column layout) if no compiled PDF exists yet. Previously printing via WebKit's PDF plugin produced solid black rectangles.
- **Element headings no longer orphan at the bottom of a column** — `block(above:, below:, sticky: true)` using Typst's block-level spacing parameters prevents headings from being stranded at the bottom of a column without any following content.
- **Section headings flow inside the two-column block** — section headings no longer sit outside `#columns()`, eliminating implicit column breaks at every section boundary.
- **No horizontal rule above section headings.**
- **Leader's order PDF now matches the manuscript preview** — uses the full manuscript preamble (margins, font, size, paragraph spacing) instead of hardcoded values. Section headings correctly use level-1 Typst headings, matching the style and size seen in the preview.
- **Leader's order PDF includes rubric notes** — red-italic leader instruction blocks now appear in the exported PDF.
- **Print button respects the active preview mode** — printing while the manuscript preview is open prints the manuscript, not the bulletin.
- **Font picker shows only fonts Typst can actually use** — the picker now queries `typst fonts` so variable-font axis entries from fontconfig (which Typst ignores) are excluded.
- **Preview no longer busy-polls during compilation** — a dirty flag replaces the 500 ms poll loop; the next compile is scheduled 200 ms after the current one finishes.
- **Multiple windows no longer share a preview PDF file** — each window writes to its own `preview_<mode>_<window-id>.pdf`.

---

## [0.17.7] "Tended Ground" — Service notes, justice bar, unified dates editor

### Added

- **Service Notes** — a collapsible text area above the service order for theology, metaphors, movement notes, or any pre-service reflection. Not included in the bulletin or manuscript. A pop-out button opens the same notes in a floating window that shares the same text buffer, so edits stay in sync — useful on a second monitor or alongside the order panel.
- **Justice / observances second status bar row** — a bar above the main status bar surfaces upcoming and recent social justice, indigenous, ecological, and pride observances. Past and future events appear as coloured chips. A calendar icon opens the dates editor.

### Changed

- **All dates are now editable in one spreadsheet** — built-in observances (formerly read-only) are merged with custom dates into a single unified list. Every row is editable: Month, Day, Name, and Type (all 10 observance types). Rows can be deleted individually or reset to defaults. On first launch the list is seeded from the built-in calendar; any legacy custom dates are migrated automatically.
- **Bar order** — the justice bar sits above the main status bar, keeping the main status bar at the very bottom.

### Fixed

- **Save icon blue accent removed** — the toolbar Save button no longer uses the suggested-action (blue) style.
- **Preview flicker / scroll jitter reduced** — scroll-position restore fires after 30 ms instead of 120 ms; PDF preview updates use `load_uri` with a cache-buster instead of `reload()`.

---

## 0.17.6 "Open Flow" — Use regular multicolumn in Typst export

### Changed

- **Two-column bulletin and manuscript exports now use regular multicolumn flow** — the previous implementation split items into left/right halves using a character-weight heuristic and inserted an explicit `#colbreak()`. This is removed; Typst now flows all content naturally through `#columns(2)`.

---

## 0.17.5 — Fix leader's order compile; fix HTML export; auto-open PDFs

### Fixed

- **"Leader's order compile failed" on every service with text content** — `_build_minister_typst` produced `\]` at the end of any content block whose text ended with a line-break marker (`\`). In Typst markup mode, `\]` is an escaped literal `]` (not a block closer), leaving the `#text` block unclosed and consuming the `]` meant to close `#columns(2)[...]`. Fixed by applying `linebreak_fix` (converts `\` → `#linebreak()`) and putting the closing `]` on its own line.
- **Unmatched `]` in content could close the outer `#columns` block** — a bare `]` in liturgy text (e.g. choral notation like `[All:]`) could prematurely terminate the enclosing `#columns(2)[...]` block and cause a compile error. The manuscript builder now escapes any `]` that has no matching `[`.
- **"Could not show link, launch failed" on HTML export** — all three HTML export paths wrote to a sandboxed `/tmp` location inaccessible to the system browser. They now write to `~/.var/app/.../cache/rubric/bulletin.html` (home directory, accessible to external processes).
- **Compile button required a prior manual Typst export** — if no `.typ` file was linked, "Compile PDF" showed an error toast. It now auto-derives and writes the `.typ` file automatically.
- **Compile proceeded with stale `.typ` file when write failed** — if writing the Typst source threw an exception, the old on-disk file was compiled unchanged. The compile step now aborts on write failure.

### Changed

- **Leader's order PDF and compiled PDFs open automatically** — after a successful compile the PDF opens in the system viewer immediately, without requiring an extra button click.
- **Compile errors are logged** — the full typst command, exit code, stderr, and stdout are written to `~/.cache/rubric/compile-error.log` on every failure for easier diagnosis.

---

## 0.17.5-dev23 — Ask for file when compiling without a linked Typst file

### Fixed

- **Compile with no linked file could silently write to an unexpected path** — when no `.typ` file was linked to a service, the compile button auto-derived a path (`<stem>_leader.typ`) that differed from the default used by the export button (`<stem>.typ`), causing confusion about where the output went. Now, when no file is linked, the compile button opens the same file-chooser dialog as the export button, so the user explicitly picks the file before writing and compiling.

---

## 0.17.5-dev22 — Compile PDF without requiring prior Typst export

### Fixed

- **"Compile PDF" button required a prior manual export** — if the service file had no linked `.typ` file (either a fresh service or one saved before the `typ_file` field was introduced), clicking "Compile PDF" showed a "Export to Typst first" toast and did nothing. Now `compile_typst_pdf` auto-derives a `.typ` path alongside the service file (or in the repo `typ/` directory) and writes it automatically, so the compile button always works in one click.

---

## 0.17.5-dev21 — Fix compile aborting on stale Typst file

### Fixed

- **Compile proceeds with stale `.typ` file when write fails** — if `_write_typst` threw an exception (e.g. bad path, permissions error), `compile_typst_pdf` continued and compiled the old on-disk `.typ` file unchanged. Old `.typ` files generated by early Rubric versions used a `\]` pattern to close content blocks; Typst treats `\]` as an escaped literal `]`, leaving the block unclosed ("unclosed delimiter" errors). `_write_typst` now returns True/False and `compile_typst_pdf` aborts on failure rather than compiling a potentially stale file.

---

## 0.17.5-dev20 — Fix export dialog, column layout, spacing preferences, sidebar behaviour

### Fixed

- **Export dialog white box** — the `Adw.ToolbarView` was fully constructed but never attached to the `Adw.Window` (`set_content()` was never called). The window rendered as an empty white rectangle with no close button, requiring Rubric to be killed from the terminal. Fixed by calling `win.set_content(tv)` before `win.present()`.
- **Column text carrying over across pages** — the manuscript and bulletin used `#grid(columns: (1fr, 1fr))` which creates fixed-height boxes that can overflow independently across page breaks. Switched to `#columns(2)[...#colbreak()...]` which keeps column content within each page section and respects page boundaries naturally.

### Added

- **Column gutter preference** — a new "Column gutter" spin row in the Layout pane of the preamble/preferences panel controls the space between columns (in em units, default 0.5 for bulletin, 1.0 for manuscript).
- **Paragraph spacing preference** — a new "Paragraph spacing" spin row in the Typography pane controls the spacing between paragraphs (em units, default 0.65).

### Changed

- **Sidebar starts closed** — the element palette sidebar now starts closed by default. It opens automatically on first launch and when starting a new service plan, so new users are guided to it without it cluttering every session.

---

## 0.17.5-dev19 — Fix bulletin toast queue race (hang persists fix)

### Fixed

- **"Compiling…" toast still hung** — the root cause was a libadwaita toast queue race: "Bulletin saved" (3s timeout) was added first, then "Compiling bulletin…" was queued behind it. If typst finished before the 3-second toast cleared, `dismiss()` was called on a toast still in the queue. Libadwaita does not reliably remove a queued-but-not-yet-shown toast on `dismiss()`, so the toast appeared afterwards with its dismiss already consumed — hanging forever. Fix: removed the separate "Bulletin saved" toast so the compile toast goes directly to active. The "Compiling filename.typ…" toast text now serves as confirmation of the save, and the success "✓ filename.pdf" toast confirms the compile.

---

## 0.17.5-dev18 — Fix bulletin PDF export hang

### Fixed

- **"Compiling bulletin…" toast never dismisses** — each compile path now captures its toast in a closure at creation time instead of storing it in `self._compiling_toast`. Previously, if print and digital were both checked (or if a manuscript compile ran concurrently), the second assignment would overwrite the first; when the first compile finished it dismissed the wrong toast, leaving the original "Compiling bulletin…" visible forever.
- **HTML export blocks main thread** — `_export_bulletin_html_typst` was calling `subprocess.run([typst, "--version"])` synchronously on the main thread before starting the background compile. This froze the UI (and the print file dialog) for up to 5 seconds whenever HTML was selected alongside other outputs. The version check now runs inside the background thread.

---

## 0.17.5-dev17 — Bulletin summary field for hymns and scripture

### Added

- **Bulletin summary field** — each service item now has a short "bulletin note" text entry in the toolbar (next to the Bulletin heading toggle). When set, that text appears in the bulletin instead of the full content. This lets you keep detailed manuscript notes in the content area while showing only a hymn reference (e.g. `VU 123 — O God Our Help`) or scripture reference (e.g. `John 3:16–21`) in the bulletin — without needing to wrap manuscript content in `#leader-note[...]`. Leave it empty to use existing behaviour (full content, or heading only if the toggle is active).

---

## 0.17.5-dev16 — Fix export failure on old-format service files

### Fixed

- **Export/compile failure on old service files** — service files created before the Typst migration (using the old `note` / LaTeX format) could produce invalid Typst output, causing compilation to fail with an "unclosed delimiter" error. The issue was that raw LaTeX commands (e.g. `\subsection*{Preamble}`, `\begin{scripture}`) were embedded verbatim in the Typst source; in Typst markup mode, `*` opens a bold span so `\subsection*{...}` causes a parse error. Old LaTeX content is now stripped to plain text during migration so it renders cleanly without breaking compilation.
- **Silent bulletin generation errors** — if `_build_bulletin_typst()` raised an exception, it was silently swallowed by the GTK dialog callback and the user saw nothing. Errors during bulletin generation now show an error dialog.

---

## 0.17.5-dev15 — Balanced columns for manuscript and bulletin

### Changed

- **Manuscript: grid-balanced columns** — the manuscript now uses `#grid(columns: (1fr, 1fr))` for section content instead of `#columns(2)`. Items are placed side-by-side rather than flowing text between columns, giving true balanced layout.
- **Content-weighted column split** — both the manuscript and bulletin now split items between left and right columns based on estimated content height (item count × base height + content length), not raw item count. This keeps visually heavy items (long prayers, scripture) from overloading one column.
- **`linebreak_fix` now applies to all lines** — the `#linebreak()` conversion for trailing `\\` now applies even to lines that start with inline Typst calls (e.g. `#h(1.5em)text \\`). Previously these lines were skipped, leaving literal backslashes in the output.

---

## 0.17.5-dev14 — Fix backslash line breaks in bulletin and manuscript

### Fixed

- **Trailing `\` rendered as literal backslash** — in Typst markup, a lone `\` at end of a line is a literal backslash character, not a forced line break. Rubric now converts trailing `\` on plain-text content lines to `#linebreak()` when generating the Typst source, so responsive readings, prayers, and other line-broken liturgy text displays correctly in both the manuscript and bulletin.
- **Spurious blank line before accessibility note** — the back page `#linebreak()` separator before the accessibility note is now only emitted when there is preceding content (mission statement, contact info) above it. Previously it created an empty leading line when the accessibility note was the only back-page content.

---

## 0.17.5-dev13 — Manuscript formatting improvements

### Added

- **Page numbers on manuscript** — leader copy now shows page numbers in the footer.

### Fixed

- **Backslash line breaks** — trailing `\` on lines in liturgy content is now preserved as a Typst forced line break rather than being escaped to a literal backslash character.
- **Space above first element after section heading** — section headings now have a larger non-weak bottom margin (12 pt vs. 6 pt weak) so the first element in each section has visible breathing room.
- **Rule above section headings** — a thin horizontal rule now appears above each section heading (`GATHERING`, `WORD`, etc.), providing a clear visual break between major sections.
- **More space before section headings** — top margin before section headings increased from 16 pt to 24 pt, giving more breathing room after title-page content and between sections.
- **Reduced inter-paragraph spacing** — paragraph spacing in the manuscript set to 0.5 em (previously default ~0.65 em+), reducing the "full line gap" between stanzas.
- **First-line indent removed** — `first-line-indent: 0pt` is now explicit in the manuscript preamble to prevent any Typst-version-dependent indentation on content paragraphs.

---

## 0.17.5-dev12 — Balanced columns, undo fix, scroll fix, window fit

### Added

- **Balanced bulletin columns** — bulletin sections now use a `#grid(columns: (1fr, 1fr))` with items split evenly by count, so both columns always fill to the same depth.

### Fixed

- **Undo/redo in notes editor** — Ctrl+Z / Ctrl+Shift+Z now delegates to the notes text buffer when the editor is focused, so text edits undo correctly; when the service list is focused, undo/redo works on the service order as before.
- **Preview jiggle while scrolling** — scroll-position polling reduced from 400 ms to 2 s (with compile suppression during polls). A one-shot snapshot is taken at the start of each compile so the correct position is always restored without continuous polling.
- **Font search filters correctly** — the font family ComboRow now has its expression set to the string property, so typing in the search box actually filters the list.
- **Unsaved indicator moved left of Focus** — "● Unsaved" chip now appears to the left of the Focus button.
- **Window fits 1200 px / 110% screen** — reduced minimum widths (title entry 280→180 px, order-list pane 260→220 px) so the window no longer overflows when both sidebar and preview are open.
- **CI release workflow** — release `.deb`/`.rpm` workflow now only triggers on clean version tags (`v1.2.3`), not dev tags (`v1.2.3-dev4`), fixing spurious CI failures.

---

## 0.17.5-dev11 — Section pagebreak removed, bulletin polish

### Fixed

- **No pagebreak before sections** — manuscript sections (Gathering, Word, Response, Sending) no longer force a page break; they flow continuously.
- **"All (Lord's Prayer)" removed from acknowledgements** — generic congregation-direction labels are excluded from the named-leader block at the end of the bulletin.
- **Accessibility note at end of back page** — appears after contact info on the back page, no dedicated page.

---

## 0.17.5-dev10 — Font discovery, bulletin fixes

### Fixed

- **Font family now applies** — all Typst compile invocations now pass `--font-path` for common system font directories (`/usr/share/fonts`, `/run/host/fonts`, `~/.local/share/fonts`, etc.). This fixes the issue where the bundled Typst binary couldn't locate system fonts inside the Flatpak sandbox, causing it to silently fall back to its built-in font.
- **"All (Lord's Prayer)" no longer appears in acknowledgements** — generic assembly-direction leader labels ("All", "Congregation", "Everyone") are now excluded from the acknowledgements block at the end of the bulletin. Only named people appear there.
- **Accessibility note placement** — the accessibility note now appears at the bottom of the back page (after contact info), on the same page as the mission statement, without a spurious extra page break.

---

## 0.17.5-dev9 — Bulletin style presets, preview and font fixes

### Added

- **Bulletin style presets** — the Template → Bulletin form now has four one-click style presets at the top:
  - **Classic** — two columns, bold small-caps + rule headings, 11 pt. Traditional, formal.
  - **Contemporary** — two columns, clean bold headings, 10.5 pt. Modern, welcoming.
  - **Large Print** — single column, bold small-caps headings, 14 pt. Accessible for low-vision readers.
  - **Compact** — two columns, plain headings, 9.5 pt, tight margins. Fits long services on fewer pages.
  - Each preset applies all layout settings at once; individual fields remain editable afterwards.

### Fixed

- **Font size now applies correctly** — changing template settings while a compile was in progress caused the HTML fallback (hardcoded 11 pt) to display instead of the correct PDF. The update is now rescheduled until the compile finishes, so every change gets compiled.
- **Preview scroll preservation** — scroll position is now polled every 400 ms while the preview is open, so the position is always current when a PDF reloads. A 120 ms post-load delay lets the PDF renderer settle before the scroll is restored.
- **Template panel → preview sync** — opening the Template panel now immediately switches the preview to manuscript or bulletin mode based on the active sub-toggle.

---

## 0.17.5-dev8 — Template panel sync, heading spacing, UX polish

### Added

- **Compact title page option** — Settings → Bulletin → "Title page style" lets you choose between a full cover page and a compact church-name/title/date header at the top of page 1 (no page break).
- **Dismiss button for hymn suggestions** — an × button on the hymn suggestions strip lets you close it. The strip reappears automatically when you navigate to a new hymn element.

### Fixed

- **Template panel font/margin preview now works** — the Template sub-toggle (Manuscript / Bulletin) now syncs with the preview mode, so changes to manuscript settings are immediately reflected in the manuscript preview and vice versa.
- **Preview pane no longer jumps** — the preview paned divider position is now set only once on first reveal and never touched again; users can drag it wherever they like without it being reset.
- **Heading spacing** — section (`=`), element (`==`), and sub-heading (`===`) headings now have reliable non-collapsing space above them (16 pt / 10 pt / 7 pt) so headings are clearly separated from preceding content.

---

## 0.17.5-dev7 — Template panel improvements, scroll preservation

### Added

- **Font family dropdown** — the Template panel now shows a searchable dropdown of all system/user fonts (via PangoCairo). The previously missing font picker is now functional.
- **Heading style and columns settings** — Template panel now includes a heading style selector (bold + small-caps + rule, bold + small-caps, bold, plain) and a columns toggle for both manuscript and bulletin layouts.
- **Live preview in Template panel** — opening the Template panel now automatically shows the preview pane so font, margin, and heading changes are immediately visible.
- **Columns support in manuscript** — the manuscript `#columns(N)` is now driven by the Template panel setting rather than hardcoded to 2; setting columns to 1 removes the columns wrapper entirely.
- **Multicolumn toggle for bulletin** — bulletin columns is now a simple on/off toggle (2 columns vs 1) in the Template panel.

### Fixed

- **Preview no longer jumps to top on recompile** — the preview panel saves scroll position before each PDF/HTML reload and restores it after the page finishes loading.

### Changed

- **"Preamble" renamed to "Template"** — the status bar button and panel header now say "Template" instead of "Preamble". Internal identifiers are unchanged.
- **Typst Files section hidden in Settings** — the raw Typst template file list is hidden; use the Template panel instead.

---

## 0.17.5-dev6 — Preamble panel, Bulletin heading-only, styling fixes

### Added

- **Preamble panel** — a "Preamble" toggle in the status bar opens a document settings editor (font family, font size, margins for manuscript and bulletin). Settings are stored in config and used when generating PDFs, overriding the bundled template files.
- **Bulletin heading-only toggle** — the "Bulletin" button in the element toolbar now marks an element as *heading only*: the element title appears in the congregation bulletin but the body text is omitted. Rows in the order list dim slightly (0.7 opacity) when heading-only is active. The toggle is bold when on, regular when off — consistent with other status bar controls.

### Fixed

- **Leader note Typst output** — highlighted text tagged as a leader note no longer appends a trailing ` \` before the closing `]`, which caused a Typst compilation error (`\]` escapes the bracket). Multi-line leader notes still preserve line breaks for all lines except the last.

### Changed

- **Preview button** — moved from a ToggleButton (with active-state highlight) to a flat button. Bold when the preview panel is open, regular when closed — same pattern as the status bar toggles.
- **Responsive reading** — the builder dialog and toolbar button have been removed. Responsive readings can be formatted with Bold.
- **Bulletin toggle semantics** — the per-element Bulletin toggle previously hid items from the bulletin entirely; it now marks items as heading-only (always in bulletin, body text omitted).

---

## 0.17.5-dev5 — Typst source editor toggle (Dev mode)

### Added

- **Typst editor toggle** — a "Typst" button appears in the status bar when Dev mode is on. Clicking it switches the content editor from rich text to raw Typst source (with syntax highlighting if GtkSourceView has a typst/markdown language). Switching back commits the raw source to the rich editor. Changes in either mode fire through to the live preview.

---

## 0.17.5-dev4 — Leader notes and rubric visible in manuscript preview

### Fixed

- **Manuscript HTML preview now shows leader notes and rubric notes** — `#leader-note[…]` blocks in the content and the separate rubric note field both render as red italic blocks in the manuscript view (live HTML preview mode). They remain completely stripped from the bulletin preview as before.

---

## 0.17.5-dev3 — Hymn manual entry fallback; By Title shows all cached hymns

### Fixed / Added

- **Manual hymn entry** — when a lookup fails (Hymnary.org blocked), a title field appears inline. Type the title from your physical hymnal and press Save — it's cached locally and inserted just like a successful lookup.
- **By Title tab shows all cached hymns on open** — no longer requires typing 2+ characters; all 113+ cached hymns are visible immediately when the popover opens.
- **HTML entities decoded in hymn search** — cached titles with `&#039;` etc. now display correctly in search results.

---

## 0.17.5-dev2 — Fix hymn lookup: Wayback Machine fallback for Hymnary.org blocks

### Fixed

- **Hymn lookup blocked by Hymnary.org** — Hymnary.org now returns HTTP 403 for all programmatic access (TLS fingerprinting + IP policy). Rubric now falls back to the Wayback Machine (archive.org) when Hymnary.org blocks the request. The Wayback Machine has full cached copies of all VU/MV/LUS hymn pages and allows programmatic access. Lookups work transparently; results are cached locally so each hymn is only fetched once.
- **Hymn title HTML entities** — titles stored in cache (and newly fetched) now have HTML entities decoded (`&#039;` → `'`, `&amp;` → `&`, etc.). Existing cached entries are decoded automatically at read time — no cache purge needed.
- **Hymn title extraction robustness** — added JSON-LD structured data as a second extraction method and relaxed the og:title regex.
- **Hymn row subtitle** — after inserting a hymn via lookup, the service row subtitle now correctly shows the leader and note preview in `Leader · Note` format, matching other rows.

---

## 0.17.4 — Accessibility improvements, beautification, smart save, live preview

### Added

- **Smart save** — a "● Unsaved" chip appears in the status bar whenever there are unsaved changes. When a file is already open, changes are automatically saved 2 seconds after you stop typing. The chip clears on save.
- **Live preview mode** — a "Live" toggle button in the preview panel bypasses Typst compilation and shows an instant HTML preview as you type. Useful when Typst isn't installed or for fast feedback.
- **Quick help overlay** — a `?` button in the header opens a popover that describes each area of the screen in plain English (palette, service order, notes editor, preview panel, status bar, menu).
- **Church name wizard step** — the first-launch wizard now asks for your church name before the service-type choice, so bulletin headers are populated from the first service.
- **Plan this Sunday** — unplanned calendar rows now show a "Plan…" button that opens a dialog to create a new service file; choose default template, blank, or copy element structure from any past service.
- **Publish bulletin to web** — after compiling a bulletin PDF, a second toast offers "Publish…"; Rubric copies the PDF to `bulletins/` in the GitHub repo, generates an `index.html`, commits, and pushes. The URL (`username.github.io/repo/bulletins/`) is shown in a toast.
- **Most used elements view** — the Element Library tab now has a "Most used" / "By service" toggle. "Most used" shows every element name ranked by how many distinct services it has appeared in, with an age stamp ("3w ago").
- **Element name suggestions** — the Add Custom Element dialog now shows an inline suggestion list as you type (≥2 characters), drawn from the element library and ranked by frequency.
- **Friendly Typst errors** — compilation errors are translated into plain English (e.g. "An opening `{` was never closed").

- **Section divider accent stripe** — each section divider (Gathering, Word, etc.) now shows a 4px left-border stripe in its liturgical colour, making sections easier to scan at a glance.
- **Seasonal header tint** — the main header bar picks up a subtle gradient tint from the current liturgical season colour.
- **Season strip gradient** — the 5px season colour bar at the top of the service order fades left-to-right for a softer look.
- **Cover art thumbnail** — when a cover image is set in Settings, a 28px rounded thumbnail appears in the header beside the service title.
- **Row subtitle shows both leader and note** — service rows now show `Leader · note preview` when both are set, instead of only one.
- **Drag handles always visible** — the ⠿ reorder handle is now faintly visible at rest (not hidden until hover), with a `grab` cursor.
- **Inline scripture preview** — if an element name is a Bible reference and that passage is cached (e.g. from a prior lookup), the first 8 words of the verse appear as a subtitle on the row.
- **Empty-state "Start with lectionary" button** — the empty service placeholder now includes a shortcut button to pre-fill today's lectionary order.
- **Unsaved pulse animation** — the "● Unsaved" chip pulses after 30 seconds of unsaved changes, prompting a save.
- **Preview pane warm background** — the preview panel uses a warm off-white background (#fafaf8) to feel more page-like.

### Changed

- Status bar tooltips rewritten to plain English — all five status buttons (SIMPLE, GOST, Compact, Dev, Focus) now have descriptive tooltips explaining what they do.

---

## 0.17.3 — Notes panel can compress for preview

### Fixed
- Notes panel no longer has a hard minimum width — it can compress horizontally so the preview panel always fits on screen

---

## 0.17.2 — Layout sharing fix, maximize on start

### Fixed
- Sidebar, order, notes, and preview now always share the window: no panel can push another off-screen or collapse it to zero. All dividers act as hard borders within the window.
- Adding elements in tab mode now always inserts into the currently visible tab's section, not the last tab
- Toggling bulletin visibility, editing the leader field, and changing duration are now undoable
- Scripture inserted from the Bible viewer is now undoable
- Editing the leader field now updates the order row subtitle live
- Preview compile no longer leaks a `.typ` temp file in `/tmp` on every compile
- Opening a file no longer wipes the current service state before confirming the new file is valid — a corrupted or unparseable file now leaves the current service intact
- Hymn mode toolbar no longer flickers or clears the search field when switching between elements
- Drop-target highlight on rows is now always removed when a drag is dropped (not just when cancelled)

### Changed
- `Pango.EllipsizeMode.END` replaces the magic number `3` throughout

---

## 0.17.1 — UX polish, season colour, focus mode fixes, hymn toggle

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

### Added
- **Hymn toggle** — a "Hymn" toggle button appears next to "Responsive" in every element toolbar. Activating it shows the hymn search and suggestions for any element, not just those named "Hymn"

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
