# Rubric v0.17.4

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

**Accessibility and visual polish** — a significant update focused on making Rubric easier to use and nicer to look at.

- **Smart save** — a "● Unsaved" chip appears in the status bar when there are unsaved changes. When a file is open, changes auto-save 2 seconds after you stop typing. The chip pulses after 30 seconds to prompt a manual save.
- **Live preview** — a "Live" toggle in the preview panel shows an instant HTML bulletin without waiting for Typst to compile. Good for fast feedback or when Typst isn't installed.
- **Quick help overlay** — the `?` button in the header opens a popover describing each area of the screen in plain English.
- **Church name wizard step** — the first-launch wizard now asks for your church name upfront so bulletin headers are filled in from the very first service.
- **Section divider accent stripes** — each section divider shows a coloured left-border stripe in its liturgical colour (Gathering, Word, Response, Sending).
- **Seasonal header tint** — the main header picks up a subtle gradient from the current liturgical season colour.
- **Cover art thumbnail** — when a cover image is set in Settings, a small rounded thumbnail appears beside the service title.
- **Richer row subtitles** — service rows now show both leader and note preview (e.g. "All · In the beginning…").
- **Inline scripture preview** — if an element name is a Bible reference and the passage is cached, the first few words appear as a subtitle.
- **Empty-state shortcut** — the empty service placeholder includes a "Start with lectionary" button.
- **Friendly Typst errors** — compiler errors are translated into plain English.
- **Bug fix** — the What's New changelog was not showing in installed flatpak builds (symlink not followed by pip). Fixed by resolving it at build time.

---

### Full changelog

See [CHANGELOG.md](CHANGELOG.md).
