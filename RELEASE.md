# Rubric v0.17.6

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

**Multicolumn fix** — two-column bulletin and manuscript exports now flow content naturally through Typst's `#columns()` instead of using a manual character-weight heuristic to pre-split items into left and right halves.

---

### Full changelog

See [CHANGELOG.md](CHANGELOG.md).
