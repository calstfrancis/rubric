# Rubric v0.17.8 "Still Water"

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

**Print from the compiled PDF** — the print button now sends the Typst-compiled PDF directly to the print dialog via Poppler, preserving fonts, columns, and exact layout. Previously printing went through WebKit's HTML renderer and produced black rectangles or missing columns.

**Leader's order export matches the preview** — the leader's order PDF now uses the full manuscript preamble (margins, font, size, paragraph spacing, heading style), so the exported PDF looks the same as the manuscript preview. Section headings are also correctly sized.

**Layout settings persist** — the order list / notes split, the element palette width, and the preview panel width are all remembered across sessions and restored on next launch.

**Drag-to-resize rubric area** — the leader instructions field is now a draggable pane rather than a fixed-height box.

**Live preview with compile modes** — the side-by-side Typst preview now defaults to "Save" mode (compile on Ctrl+S or autosave) instead of auto-compile on every keystroke, reducing background CPU usage. Auto and Manual modes are still available via the cycle button in the justice bar.

**Multi-window support** — open a second service window with ⧉ in the header bar or Ctrl+Shift+N.

---

### Full changelog

See [CHANGELOG.md](CHANGELOG.md).
