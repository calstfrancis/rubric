# Rubric v0.17.1

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

**Hymn toggle** — every element now has a "Hymn" toggle button in its toolbar. Tap it to activate hymn search and suggestions for any element, not just those named "Hymn".

**Scripture display** — inserted scripture passages now show as readable indented text in the element editor. No raw Typst code visible to users.

**Focus mode fix** — turning off focus mode no longer forces the sidebar open if it was already hidden.

**Season colour** — the liturgical season colour is now applied to the week name label and the lectionary chip in the date popover, in addition to the colour strip and dot.

---

### Full changelog

See [CHANGELOG.md](CHANGELOG.md).
