# Rubric v0.17.2

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

**Shared layout** — the sidebar, order, notes, and preview panels now always share the window. No panel can push another off-screen or collapse it to zero. All dividers act as hard borders.

**Maximized on launch** — Rubric now opens maximized by default.

**Undo improvements** — toggling bulletin visibility, editing the leader field, changing duration, and inserting scripture from the Bible viewer are all now undoable.

**Safe file open** — opening a file no longer clears the current service before confirming the new file is valid. A corrupted file now leaves your current service intact.

**Tab mode fix** — adding elements in tab mode now inserts into the currently visible tab's section.

**Hymn toolbar fix** — the hymn mode toolbar no longer flickers or clears the search field when switching between elements.

---

### Full changelog

See [CHANGELOG.md](CHANGELOG.md).
