# Rubric v0.21.0 "Sure Keep"

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

**Backups now happen on their own.** Once a folder is connected to GitHub, Rubric saves and backs it up automatically every so often while you work, and once more on the way out if anything's still unsent — so backing up no longer depends on remembering the Backup button. It's quiet by design: a failure, including a real sync conflict, shows a toast suggesting the toolbar button rather than a popup, and it never blocks quitting for more than a few seconds.

**Error messages can be copied now.** Every notice and error dialog — a sync failure, a setup error — has a Copy button next to OK, so the message can be pasted into a bug report instead of retyped from a screenshot.

**Hymns work entirely offline.** Rubric no longer talks to Hymnary.org at all — that site now blocks automated requests outright, so every lookup was failing. Rubric ships with 877 Voices United titles bundled in; lookup and search work instantly, on any machine, with no network.

**The bulletin prints what you wrote.** Leader notes — private instructions like "pause here" meant only for whoever is presiding — had been leaking into the congregation's printed bulletin since 0.20.0. Bold, italic, headings and bullet lists, which had been silently flattened in the bulletin, keep their formatting again, and text containing `@`, `*`, `~`, or `<...>` no longer gets misread as markup or dropped by the preview.

**New elements can be created from the sidebar**, with a **+** button beside the palette search, instead of a trip through Preferences.

**Plain language throughout setup and sync.** "Repository," "remote," "clone" — terms that meant nothing to a non-technical user — are now described in terms of what they do: "online copy," "address," "back up." Covers the setup wizard, Preferences → GitHub, and every sync message.

---

### Full changelog

See [CHANGELOG.md](CHANGELOG.md).
