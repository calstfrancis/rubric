# Rubric v0.15.5

Install with pipx (recommended):

```bash
pipx install --system-site-packages rubric-liturgy
```

Or download a native package below (see Assets).

---

### What's new

**Bug fixes and UX polish** — this release fixes several issues found in a comprehensive code audit:

- **ESV translation** no longer silently falls back to WEB when no API key is set — now shows a clear error.
- **Bulletin hymn export** Typst syntax corrected (could cause compile errors in some Typst versions).
- **Bulletin toggle** opacity feedback now works in tabbed view as well as flat-list view.
- **Bulletin save errors** (disk full, permissions) now shown in a dialog instead of silently failing.
- **Hymn lookup** injection is now undoable with Ctrl+Z.
- **Ctrl+Shift+P** (compile PDF) no longer opens a file dialog and shows a toast at the same time.
- **Snippet button** now correctly hidden in Simple mode.
- **ESV API key** saves live in Preferences — no need to close and reopen.
- **Section delete dialog** now correctly states that Undo is available.
- All remaining "LaTeX" labels updated to "Typst" throughout the UI.

---

### Full changelog

See [CHANGELOG.md](CHANGELOG.md).
