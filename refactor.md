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

1. **Exports** (this session) — biggest win, lowest risk, no untangling required.
2. Untangle "Live bulletin preview" into its two halves; extract the genuine preview/compile ~600 lines; leave the ~200 lines of state methods on `MainWindow`.
3. Revisit remaining sections opportunistically — none of the rest are large enough to be urgent on their own.

### Verification bar for this phase

Same as Phase 1, plus: since the extracted helper will be *called by* `MainWindow` (not the reverse), also run the actual app (or as close to it as headless testing allows) to exercise an end-to-end export, not just construct the object. `python3 -m py_compile` and a bare instantiation aren't enough on their own for code this deep in the call graph.
