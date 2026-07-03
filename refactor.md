# Rubric monolith refactor

Tracks the ongoing effort to shrink `rubric.py` out of its monolithic state. Strangler pattern throughout — small, verified steps, not a big-bang rewrite (a prior full package-split attempt stalled, leaving `rubric_package/` half-populated).

## Phase 1 — window extraction (complete, 2026-07-03)

Every standalone `Adw.Window`/`Adw.PreferencesWindow` subclass in `rubric.py` has been either deleted (confirmed dead) or moved into `rubric_package/views/`.

**Deleted (dead code, never instantiated — superseded by `ServicesWindow`'s tabs):**
- `ArchiveWindow` (229 lines)
- `LibraryWindow` (211 lines)
- `PlannerWindow` (373 lines) — held the only UI for per-service attendance/debrief-note editing, but that UI was already unreachable. Deliberately not preserved; that editing feature returns later as part of a planned Rubric "library" feature modeled on Zerkalo's, not resurrected from this code.

**Extracted into `rubric_package/views/`:**
- `HelpWindow`
- `PreferencesWindow` (~990 lines)
- `BulletinPrefsWindow` (~355 lines)
- `BibleViewer` (~50 lines)
- `ServicesWindow` (~750 lines — unified Planner/Library/Archive tabs, the thing that made the three deleted windows dead)
- `DatesEditorWindow` (~245 lines)
- `ObservanceWikiWindow` (~180 lines)
- `ServicePlanningNotesWindow` (~23 lines)

**Two real bugs fixed along the way:**
1. `rubric.py` had its own local `config = Config()` and `get_palette()`, duplicating identical dead copies already sitting in `rubric_package/models/config.py`. Two live `Config` instances existed in memory; only one was ever used. Consolidated to a single shared singleton.
2. Dropped one dead local variable (`_lect_ok`, set but never read) found while moving `ServicesWindow._load_planner_calendar`.

**Patterns established:**
- Grep `ClassName(` across the *whole repo* before assuming a class is dead, and read the full body — `PlannerWindow` looked dead like its siblings but had a hidden non-duplicated feature.
- Config-adjacent module-level functions (`get_palette()`, `seed_all_dates()`) belong in `rubric_package/models/config.py` next to `config`.
- Repo-root sibling modules (`snippets.py`, `hymn_lookup.py`, `bible_api.py`, WebKit/WebKit2) get their guarded-import block *re-declared locally* in each extracted module, rather than imported back from `rubric.py` (would create a circular import).
- Verify with more than `python3 -m py_compile`: `Adw.init()` then instantiate the moved class directly (`python3.11`, has PyGObject). For classes that defer work via `GLib.idle_add`, pass a stub `main_window` and manually pump `GLib.MainContext.default().iteration(False)` so deferred callbacks actually run.

**Result:** `rubric.py` went from 11,363 → 7,807 lines (~31% smaller). What's left is almost entirely `MainWindow` (~7,400 of ~7,800 lines) plus the small `LiturgyPlannerApp` wrapper.

## Phase 2 — splitting `MainWindow` (in progress)

`MainWindow` can't be moved wholesale like the window classes in Phase 1 — it's too large and too central. The approach is composition: pull cohesive chunks of functionality out into plain helper classes under a new `rubric_package/` subpackage, each taking `main_window` in its constructor and duck-typing into it (same pattern the Phase 1 windows already use via `self._main`). `MainWindow` keeps thin call sites or delegates directly to the helper. This is not a mixin-based split — mixins would still couple everything to `self` and wouldn't actually separate anything.

### Step 1 — `BulletinExporter` (done, 2026-07-03)

Extracted the full 1,303-line **Exports** section into `rubric_package/exporters/bulletin_exporter.py` (landed in an empty `rubric_package/exporters/` stub package left over from the earlier stalled refactor — now finally used). `MainWindow.__init__` creates `self._exporter = BulletinExporter(self)` before `_setup_actions()` runs; 15 methods that had external callers elsewhere in `MainWindow` (mostly the live-preview compile path, action/button wiring, and the `export_as` format-picker dialog) now get called as `self._exporter.<method>()` instead of `self.<method>()`. Also relocated `_log_compile_error()` (a module-level function only this code used) into the new module, and dropped the file-scope Typst alias variables (`_typst_escape` etc.) that existed only to serve this section.

`rubric.py`: 7,807 → 6,481 lines (the single biggest cut of the whole refactor, Phase 1 included).

**Important lesson — the mechanical `self.` → `self._main.` transform has a blind spot**: it only catches `self.attr` patterns. Bare `self` passed as an argument — `Adw.Window(transient_for=self, ...)`, `WebKit.PrintOperation.run_dialog(self)`, `Gtk.PrintOperation.run(action, self)`, `GtkFileDialog.save(self, None, callback)` — doesn't match that regex at all, so those 6 call sites kept passing the *exporter object itself* as the parent window instead of `self._main`. `python3 -m py_compile` and even a bare instantiation smoke test don't catch this class of bug — it only surfaces when the method that builds the dialog actually *runs*. Caught by building a fake `main_window` stub and calling every export method directly, which raised `TypeError: argument parent: Expected Gtk.Window, but got BulletinExporter` — then fixed and confirmed via a full `Adw.Application` + real `MainWindow` construction.

**Verification recipe for future composition-style extractions** (methods moving out of a class that's still referenced by the class they came from), in order of strength:
1. `python3 -m py_compile` — catches syntax errors only.
2. Instantiate the moved class directly (with a stub `main_window`) — catches missing imports/attributes at construction time.
3. **Call every moved method against a realistic stub** (not just construct-and-done) — catches wrong self-vs-self._main routing in method bodies, including bare-`self`-as-argument cases the regex misses. Grep for bare `self` tokens specifically (`(?<![\w.])self(?!\.)(?!\w)`) as a static check before even running anything — a line-based grep that excludes whole lines containing `self.attr` will miss cases where both patterns appear on the same line (learned the hard way — `dlg.save(self, None, self._on_x)` has both).
4. Where feasible, construct the *real* owning class (here, a real `MainWindow` via `Adw.Application`) and call through the real delegation path, not just the extracted class in isolation.

### Section map (by internal `# ── Section ──` comment markers, ~37 total)

Sizes in lines, largest first:

| Section | Lines | Notes |
|---|---:|---|
| Exports | 1,303 | Bulletin/manuscript HTML + Typst building, compiling, exporting, publishing to web. Clean — no ambiguous state-management methods mixed in. |
| Live bulletin preview | 856 | **Not clean** — see below. |
| Order panel | 392 | Service order list UI |
| Preamble panel | 365 | |
| UI (general construction) | 335 | |
| File IO | 293 | |
| Preferences (dialog-opening methods) | ~292 | Just `open_*`/`_show_doc` wrappers around already-extracted windows — thin, low priority |
| Hymn lookup | 286 | |
| Lectionary service seeding | 256 | |
| Snippets | 250 | |
| Calendar / readings | 249 | |
| Setup wizard | 235 | |
| Git / GitHub integration | 184 | |
| Hymn suggestions | 162 | |
| Simple mode | 158 | |
| First-launch wizard | 157 | |
| Refresh logic | 150 | |
| Order actions | 144 | |
| Icon picker | 125 | |
| Palette panel | 124 | |
| Leader's order PDF | 122 | |
| AV sheet export | 98 | |
| Leader | 97 | |
| Planning notes | 87 | |
| Notes | 81 | |
| *(20+ more sections, all under 80 lines each)* | | |

### The "Live bulletin preview" wrinkle

This section mixes two unrelated things:
- **Genuine preview/compile logic** (~600 lines): `_build_preview_panel`, `_build_preview_gear_popover`, `_toggle_preview_panel`, `_toggle_bulletin_edit`, `_schedule_preview_update`, `_do_preview_update`, `_run_preview_compile`, `_typst_compile_cmd`, `_find_typst`, `_load_typst_preamble`, `_load_preview_pdf`, `_on_preview_load_changed`, scroll-sync (`_start_scroll_poll`/`_stop_scroll_poll`/`_preview_save_scroll`), `_preview_compile_done`, `_popout_preview`.
- **Core document-state methods** (~200 lines) that must stay on `MainWindow` regardless of what else moves, because every already-extracted view class calls them via `self._main.*`: `_mark_modified`, `_confirm_discard`, `_service_data`, `_update_title`, `_deferred_save`, `_refresh_cover_thumb`, `_update_save_state_chip`, `_start_unsaved_pulse`.

These got filed under one comment header by file proximity, not by logic. Splitting this section requires method-by-method triage, not a block move — plan this properly before starting it.

### Order of work

1. ~~**Exports**~~ — done, see above.
2. **Next**: untangle "Live bulletin preview" into its two halves; extract the genuine preview/compile ~600 lines into e.g. `rubric_package/preview/bulletin_preview.py`; leave the ~200 lines of core document-state methods (`_mark_modified`, `_confirm_discard`, `_service_data`, `_update_title`, `_deferred_save`, `_refresh_cover_thumb`, `_update_save_state_chip`, `_start_unsaved_pulse`) on `MainWindow`. Note: the extracted preview module will itself need to call into `MainWindow` for those state methods (`self._main._mark_modified()` etc.) — same composition pattern as `BulletinExporter`, and it will also call into `BulletinExporter` for `_build_bulletin_html`/`_build_bulletin_typst`/etc. (`self._main._exporter.<method>()`), since preview reuses the document-building logic that already moved.
3. Revisit remaining sections opportunistically — none of the rest are large enough to be urgent on their own.

### Verification bar for this phase

Same as Phase 1, plus the four-step recipe above (compile → instantiate → call every method against a realistic stub, explicitly grepping for bare-`self` tokens → construct the real owning class and call through it end-to-end). `python3 -m py_compile` and a bare instantiation aren't enough on their own for code this deep in the call graph.
