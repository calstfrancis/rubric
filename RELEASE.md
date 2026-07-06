# Rubric v0.18.1 "Common Thread"

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

**The Element Library is now a real catalog, not just a service-grouped list.** "By Element" is the default view: every recurring element (Welcome, Prayers of the People, sermons, hymns…) has a stable identity across services, a use-count/last-used badge, and a content-preview snippet showing the first several words of its most recent instance — so two entries both named "Hymn" are distinguishable without expanding either one.

**Tag, favorite, and annotate elements.** Tag any element (communion, youth, Advent…), star favorites to pin them to the top regardless of sort order, and leave a curator note ("always pair with the announcements slide") via the per-row "Edit tags & notes…" button.

**Find and merge near-duplicate elements.** A new "Find near-duplicate elements…" dialog flags likely duplicates (e.g. "Offertory" vs "Offeratory") by text similarity, shows a content preview from each side, and merges one into the other in a click — combining tags, favorite status, and notes, and repointing all past instances to the kept name.

**Past Liturgies gets properly organized.** Services can now carry a Series, free-form Tags, and a Pinned flag, all editable from the title popover. The library tab gained a real sidebar (All / Pinned / Untagged, plus per-series and per-tag filters with counts), sort options, bulk actions (tag/series/pin several services at once), and a Manage Tags & Series dialog with rename-everywhere. Attendance and debrief notes are back after going missing in the monolith cleanup.

**Smaller fixes**: window sizes are now remembered between sessions; the preview panel toolbar is no longer unreadable in dark mode; startup on installs with a large service history is noticeably faster (the background library scan no longer opens a fresh database connection per historical file).

---

### Full changelog

See [CHANGELOG.md](CHANGELOG.md).
