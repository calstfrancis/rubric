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

### Step 2 — `BulletinPreview` (done, 2026-07-03)

Untangled the "Live bulletin preview" section into its two halves as planned. The genuine preview/compile logic (17 methods, ~625 lines) moved into `rubric_package/preview/bulletin_preview.py`; the ~90 lines of core document-state methods (`_mark_modified`, `_confirm_discard`, `_service_data`, `_update_title`, `_deferred_save`, `_refresh_cover_thumb`, `_update_save_state_chip`, `_start_unsaved_pulse`) stayed on `MainWindow`, exactly as identified. `MainWindow.__init__` now creates `self._preview = BulletinPreview(self)` right after `self._exporter = BulletinExporter(self)` (both must exist before `_setup_actions()`/`_build_ui()` run, since `_build_ui` calls `self._preview._build_preview_panel()` and the action table wires `self._preview._toggle_bulletin_edit`). 10 external call sites elsewhere in `MainWindow` (action table, button `.connect()`, and calls from `_mark_modified`, preamble-panel toggles, save-file flow) were updated from `self.<method>()` to `self._preview.<method>()`.

**The section header itself was misleading**: it also contained four general window-toggle methods (`_open_prefs_page`, `_open_sidebar`, `_toggle_palette_sidebar`, `_toggle_focus_mode`) and `_copy_as_text`, filed there by file proximity only — none of them touch preview or compile state. Left in place on `MainWindow` (not preview, not core document-state, just misfiled housekeeping — moving them wasn't in scope for this step). Renamed the stale `# ── Live bulletin preview ─` header to describe what's actually left there now.

**Three Typst helpers stayed on `MainWindow` despite living inside the same section**: `_find_typst`, `_typst_compile_cmd`, `_load_typst_preamble`. Confirmed via grep that all three are called not just from the (now-moved) preview code but also from `BulletinExporter` (already `self._main._find_typst()` etc.) *and* from the not-yet-extracted "AV sheet export" and "Leader's order PDF" sections. Moving them into `BulletinPreview` would have made those other two sections reach into the preview module for unrelated Typst plumbing — backwards for composition. They're cross-cutting infrastructure, not preview-specific, so they stay put until/unless a dedicated Typst-helpers extraction happens.

**One bare-self-as-argument bug, caught by the recipe exactly as predicted**: `_popout_preview` had `Adw.Window(title=title, transient_for=self)` — after the move `self` is the `BulletinPreview` instance, not a window, so this needed to become `transient_for=self._main`. Caught by the static bare-`self` grep *before* running anything (not by py_compile or construct-and-done), then confirmed fixed by asserting `win.get_transient_for() is main` in both the stub test and the real-`MainWindow` test.

`rubric.py`: 6,481 → 5,910 lines.

### Step 3 — `PreamblePanel` (done, 2026-07-03)

Extracted the "Preamble panel" section (document-template editor: font/margin/layout/heading fields, the four bulletin style presets, the system-font picker) into `rubric_package/panels/preamble_panel.py` — a new `rubric_package/panels/` subpackage for embedded editor panels, sibling to `views/` (standalone windows), `exporters/`, and `preview/`. 7 methods (~335 lines) moved: `_preamble_heading_typst`, `_on_preamble_changed`, `_apply_bulletin_preset`, `_rebuild_preamble_form`, `_get_system_fonts`, `_build_preamble_form`, `_build_preamble_panel`, plus the `_BULLETIN_PRESETS` class-level constant. `MainWindow.__init__` now creates `self._preamble = PreamblePanel(self)` alongside `self._exporter`/`self._preview`.

**`_on_preamble_clicked` stayed on `MainWindow`**, same reasoning as the window-toggle methods left behind in Step 2: it's a status-bar click handler that flips `_main_stack` to the "preamble" page and syncs `_preview_mode`/`_preview_visible` — it doesn't touch template fields, so it isn't preamble-panel logic even though it shares the section header. Left the widget attributes it reads (`_preamble_ms_btn`, `_preamble_btn`, `_preamble_lbl`, `_preamble_active`) as plain `MainWindow` attributes (assigned via `self._main.<attr>` from inside the moved methods), so this un-moved method needed zero changes.

**One cross-module external call site, in an already-extracted sibling**: `BulletinExporter` (`rubric_package/exporters/bulletin_exporter.py`, lines 823 and 1138) called `self._main._preamble_heading_typst(...)` directly — that had to become `self._main._preamble._preamble_heading_typst(...)` now that the method lives on `PreamblePanel` instead of `MainWindow`. A reminder that "external call site" checks must cover already-extracted modules, not just what's left in `rubric.py`.

No bare-self-as-argument bugs this time (the static grep came back clean — confirmed by construction, not by assumption).

`rubric.py`: 5,910 → 5,579 lines.

### Step 4 — `HymnLookupPanel` (done, 2026-07-03)

Extracted the entire "Hymn lookup" section into `rubric_package/panels/hymn_lookup_panel.py` — unlike Steps 2 and 3, *all six* methods moved (`_do_hymn_lookup`, `_save_manual_hymn`, `_build_hymn_search_popover`, `_on_hymn_search_changed`, `_on_theme_chip_clicked`, `_inject_hymn_line`, ~286 lines); nothing was left behind on `MainWindow` this time, because none of it was tangled with unrelated core state — the whole section is one cohesive feature (number-based Hymnary lookup with manual-entry fallback, local-cache title search, theme browsing, and injecting the result into the selected order item). `MainWindow.__init__` now creates `self._hymn = HymnLookupPanel(self)` alongside the other three helpers.

The guarded top-level imports for `hymn_lookup`/`hymn_suggestions` (optional sibling modules, same pattern as `hymn_lookup`'s WebKit-style try/except in the other extracted modules) were re-declared locally in the new module, per the established pattern — only the names actually used here (`lookup_hymn`, `parse_hymn_ref`, `search_hymns`, `get_theme_names`, `get_theme_hymns`) were carried over, not the full original list (`prefetch_hymnal`, `get_suggestions` stayed behind since nothing moved needs them).

**Two external call sites, both inside the still-unextracted, single-giant-method "Order panel" section** (`_build_order_panel`, where the hymn popover button is wired up): `self._build_hymn_search_popover()` → `self._hymn._build_hymn_search_popover()`, and the popover's `"show"` signal callback `self._on_hymn_search_changed(...)` → `self._hymn._on_hymn_search_changed(...)`. Both found by grepping the method names across the *whole* `rubric.py`, not just the section being extracted — same discipline as the cross-module fix in Step 3.

No bare-self-as-argument bugs (static grep clean). Verified with the full recipe, including one incidental confirmation of correct async routing: the stub test's call to `_do_hymn_lookup` went all the way through a real network round-trip to hymnary.org (via the real `hymn_lookup` module, not mocked) and the `on_result` closure correctly called back into `self._main.*` for `_push_undo`, `_content_widget.set_content`, and `_mark_modified`.

`rubric.py`: 5,579 → 5,295 lines.

### Step 5 — `OrderPanel` (done, 2026-07-03)

Extracted the "Order panel" section into `rubric_package/panels/order_panel.py` — the single monolithic `_build_order_panel` method (~389 lines), moved as one unit rather than pre-split into sub-methods. Decided against splitting first: the four prior extractions all moved *existing* method boundaries verbatim, never invented new ones; introducing `_build_readings_card`/`_build_order_pane`/`_build_item_toolbar` sub-methods here would have doubled the diff surface (restructuring *and* relocating in the same step) for no reuse benefit, since they'd have no other caller and would all land in the same new file regardless. Treated it exactly like the `HymnLookupPanel` step: one cohesive chunk, just bigger, with the method's existing internal `# ──` comment markers (Readings card, Quick-start banner, Planning notes, Horizontal split, Order pane left, Notes pane right, Item toolbar rows 1–2) preserved as-is as internal documentation of the seams. `MainWindow.__init__` now creates `self._order = OrderPanel(self)` alongside the other four helpers.

44 widget/state attributes get assigned inside this method (`readings_card`, `_order_hpaned`, `_view_stack`, `order_listbox`, `_content_widget`, `_hymn_search_pop`, `_theme_selected_btn`, and so on) — all landed on `self._main.<attr>`, none on the new `OrderPanel` instance itself, matching the established convention that widget/state ownership always stays on `MainWindow` even when the *building* code moves. This mattered concretely here: `HymnLookupPanel` (Step 4) already reads/writes `self._main._theme_selected_btn` and `self._main._hymn_search_pop` — both built inside this method — so keeping every assignment on `self._main` meant the two-way dependency between `OrderPanel` and `HymnLookupPanel` needed zero special-casing; it "just worked" because both sides were already targeting the same `MainWindow` attribute.

**One bare-self pitfall, of a new variety not seen in Steps 1–4**: a `hasattr(self, "_hymn_search_entry")` call (inside the popover's `"show"` callback) — the earlier bare-self grep pattern (`(?<![\w.])self(?!\.)(?!\w)`) matches this too (a bare `self` token as a `hasattr`/`getattr` argument, not just as a widget-constructor argument like `transient_for=self`), but this is a *plain attribute check* that needs `self._main` substituted, not a wrong-object-passed-to-a-constructor bug like the Step 2 case. Worth noting for future extractions: the bare-self grep catches two distinct failure shapes — (a) an object identity bug (wrong window passed as `transient_for=`/similar) and (b) a mechanical `self.` → `self._main.` transform that a naive dotted-attribute regex would miss because `hasattr(self, "x")`/`getattr(self, "x")` don't have a literal `self.` substring. Both need eyes-on fixing, not just grep-and-move-on.

Two already-established cross-module call sites (`self._hymn._build_hymn_search_popover()`, `self._hymn._on_hymn_search_changed(...)`, both already `self._hymn.`-qualified since Step 4) simply gained one more level of indirection: `self._main._hymn.<method>(...)`.

One external call site fixed in `rubric.py` (the only caller of `_build_order_panel`, in `_build_ui`): `self._build_order_panel()` → `self._order._build_order_panel()`.

Verified with the full recipe — compile, bare-self grep (one hit, fixed as above), and a real `MainWindow` construction via `Adw.Application` exercising: the widgets landing on `self._main` as expected, `add_divider()` through the real button-bar wiring, the suggestions-strip dismiss closure (confirmed `_sugg_dismissed` flips and the revealer hides), the hymn-popover cross-module wiring, and — since this method is only ever called once from deep inside real UI construction, a stub-based test would have had to reproduce nearly all of `MainWindow` anyway — a full `win.present()` + real GTK draw pass with no exceptions, confirming the `_draw_order_strip` closure's `self._main._colour_bar_rgb` reference resolves correctly under an actual paint cycle, not just at construction time.

`rubric.py`: 5,295 → 4,908 lines.

### Step 6 — `MainChrome` (done, 2026-07-03)

Extracted "UI general construction" — the single `_build_ui` method (~335 lines: header bar, status bar, and the top-level paned layout stitching together the palette/order/preamble/preview panels) — into `rubric_package/panels/main_chrome.py`. Unlike Steps 2–5, this method has no sibling methods and no nested-closure state to reason about beyond two small local helper functions (`_status_toggle_btn`, `_sb_sep`, neither touching `self`), so the transform was purely mechanical: every `self.` in the body became `self._main.`, with no bare method calls staying "self." for anything.

This one is a different flavour from the first five: it's not a discrete feature a user would name ("the preview panel", "the hymn lookup") — it's the orchestration code that builds `MainWindow`'s own chrome and wires the other panels together. Went ahead with the same extraction anyway, since the mechanical pattern holds regardless: even direct calls to `Gtk`/`Adw` methods *on the window itself* (e.g. `self.set_content(tv)`) become `self._main.set_content(tv)` cleanly, no different from any other attribute access.

**One import wrinkle, new to this step**: the status bar's version button reads the module-level `APP_VERSION` constant, which lives in `rubric.py` itself (not `rubric_package`) — importing it at the top of `main_chrome.py` would create a circular import (`rubric.py` imports `rubric_package.panels` at module-load time, before `APP_VERSION` is even defined at line ~128). Resolved with a local `from rubric import APP_VERSION` *inside* `_build_ui`, deferred until the method actually runs (long after `rubric.py` has finished importing) — same precedent as the existing local imports elsewhere in the codebase (`import cairo as _cairo` inside `_draw_order_strip`, `from rubric_package.utils.typst import parse_typst_errors` inside `_run_preview_compile`).

**A second bare-self variant, distinct from Step 5's `hasattr` case**: `self._preview_window_id = id(self)` — a bare `self` passed as a function argument (`id(...)`), same shape as Step 2's `transient_for=self` bug, not the `hasattr`/`getattr` pattern from Step 5. After the move this had to become `id(self._main)`, otherwise every window would get an id keyed to its (fresh-per-construction) `MainChrome` helper object rather than the actual `MainWindow` instance the comment says it's meant to identify. Fixed and confirmed via a real-`MainWindow` assertion (`win._preview_window_id == id(win)`).

Only one external call site existed (`_build_ui()` was only ever called once, from `MainWindow.__init__`) — updated to `self._chrome._build_ui()`. `MainWindow.__init__` now creates `self._chrome = MainChrome(self)` last in the composition-helper block, then calls `self._chrome._build_ui()` in place of the old `self._build_ui()`.

Verified with the full recipe — compile, bare-self grep (one hit, fixed as above), and a real `MainWindow` construction with `win.present()`: confirmed the header bar, status bar, and main stack all built correctly, exercised the title-entry → `_mark_modified` wiring, the chrome-wired preview-toggle button (crossing into `BulletinPreview`), and a status-bar mode toggle — all through the real signal-connected paths, not the extracted class in isolation.

`rubric.py`: 4,908 → 4,578 lines.

### Order of work

1. ~~**Exports**~~ — done, see above.
2. ~~**Live bulletin preview**~~ — done, see above.
3. ~~**Preamble panel**~~ — done, see above.
4. ~~**Hymn lookup**~~ — done, see above.
5. ~~**Order panel**~~ — done, see above.
6. ~~**UI general construction**~~ — done, see above.
7. Revisit remaining sections opportunistically — nothing left is especially large. File IO (293, `new_service`/`open_file`/`save_file`/`_write`/etc.) still looks like core document-state ownership rather than a separable feature, similar to why `_mark_modified`/`_service_data` stayed on `MainWindow` in Step 2 — worth a closer look before assuming it should move at all. Palette panel (`_build_palette_panel`, not yet measured precisely) is the next actual UI-panel-shaped candidate if further extraction is wanted.

### Verification bar for this phase

Same as Phase 1, plus the four-step recipe above (compile → instantiate → call every method against a realistic stub, explicitly grepping for bare-`self` tokens → construct the real owning class and call through it end-to-end). `python3 -m py_compile` and a bare instantiation aren't enough on their own for code this deep in the call graph. Two-for-two now on the bare-self grep catching a real bug before any test ran — treat it as mandatory, not optional, for every future composition-style extraction in this codebase.
