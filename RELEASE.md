# Rubric v0.18.0 "Clean Lines"

Install via Flatpak:

```bash
flatpak remote-add --user calstfrancis \
  https://calstfrancis.github.io/flatpak/calstfrancis.flatpakrepo
flatpak install calstfrancis io.github.calstfrancis.rubric
```

Already installed? Update with:

```bash
flatpak update io.github.calstfrancis.rubric
```

---

### What's new

**The `rubric.py` monolith split is complete** — every standalone window, panel, and export pipeline has been extracted out of the original `MainWindow` God object into `rubric_package/`. `rubric.py` has gone from 11,363 lines to 4,461 (~61% smaller). This refactor also made a chunk of previously untestable logic unit-testable for the first time (`tests/test_panels.py`, 22 new tests), now wired into CI alongside the rest of the test suite.

**Autosave failures are no longer silent** — if autosave can't write (disk full, permissions, etc.), you now get a toast telling you, instead of losing work with no warning.

**HELP.md and FAQ.md stay in sync** — both are symlinked from the packaged copy back to the root file, so in-app Help/FAQ content can't drift out of date.

**Aesthetic polish pass** — fixed invalid CSS cursor declarations on drag handles and the planning-notes header (correct cursors now show on hover); raised the compact-mode row height floor for better click targets; improved drag-handle visibility at rest; unified empty-state placeholder copy across the service order list.

---

### Full changelog

See [CHANGELOG.md](CHANGELOG.md).
