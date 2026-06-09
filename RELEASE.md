# Rubric v0.15.6

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

**Status bar and UI polish** — a persistent status bar replaces toolbar toggles with text buttons, adds new features, and reduces visual noise:

- **SIMPLE button** — toggle Simple mode directly from the status bar (bold = on); was in Preferences only
- **GOST button** — toggles GOST Type B engineering font globally (bold = on); bundled TTF, no separate install
- **Observance chips** (centre) — feast days and liturgical commemorations for the service date now appear as clickable chips in the middle of the status bar; click any chip to open a built-in Wikipedia window showing the article text
- **Focus button** — hides the palette and element list for distraction-free editing; status bar always remains accessible
- **Git button** — commit and push the current service to GitHub in one click (pull --rebase first)
- **Version chip** (right) — shows the current version; click to open the changelog
- **Last file on startup** — Rubric now reopens the most recently saved file automatically
- **Hymn lookup** redesigned as a linked pill (entry + search button)

---

### Full changelog

See [CHANGELOG.md](CHANGELOG.md).
