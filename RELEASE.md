# Rubric v0.14.3

First public release on PyPI. Install with:

```bash
pipx install --system-site-packages rubric-liturgy
```

Or: `pip install --user rubric-liturgy`

Requires GTK4 + libadwaita + python3-gobject (system packages). See the [README](https://github.com/calstfrancis/rubric#installation) for distro-specific instructions.

---

### What's new

**Past Liturgies archive** (Ctrl+Shift+H) — browse every service you've saved in a read-only viewer. Expand any service to read its full content with leader notes. Insert any past element's text into the current service with one click. Search by title, date, or content.

**Element Library** (Ctrl+Shift+K) — a searchable database of every element from every saved service. Filter by name, notes, or leader; insert into the current service with one click.

**Bulletin preview panel** — live bulletin preview as you edit. Simple mode shows HTML; advanced mode compiles a real PDF in the background. Quick-access gear icon for print/digital toggle and church name. Popout to a floating window.

**Liturgical observances** — the readings card now surfaces relevant observances for the service date: feasts, saints' days, ecumenical observances, Indigenous dates, social justice days, ecological seasons, and UCC commemorations — all colour-coded by category. Weekday observances falling within a Sunday's week appear with a proximity note.

**First-launch wizard** — on first open, choose between starting with today's lectionary (pre-fills a full four-movement order with RCL readings), a blank service, or a guided tour. Re-open any time from hamburger menu → Help → Welcome wizard.

**Simple mode** (on by default) — hides LaTeX, GitHub sync, CSV export, snippets, and responsive reading for a cleaner everyday experience. Toggle off in Preferences → View → Simple mode; all features and shortcuts remain available.

**Redo** (Ctrl+Shift+Z) — redo button added to the header bar.

**HTML export** — print-ready HTML service order and HTML bulletin export in simple mode (no LaTeX required).

**GitHub repository sync** — push and pull services to a GitHub repository with one click. Guided setup creates the folder structure and git repository automatically.

**Scripture translation selector** — choose WEB, KJV, ASV, or ESV in Preferences → Scripture.

**Service Planner** (Ctrl+Shift+L) — lists all services in your liturgy folder grouped into Upcoming and Past.

---

### Bug fixes

- Notes not appearing when opening a saved file
- Bulletin text not propagating to the preview panel
- Bulletin preview LaTeX escape artifacts (`\hspace` rendering as text)
- Bulletin preview "URL can't be shown" WebKit error
- Spurious `changed` signal on state reset
- Bulletin compile silently failing on minimal TeX Live installations
- Hymn title from Hymnary incorrectly including the book name prefix

---

### Full changelog

See [CHANGELOG.md](CHANGELOG.md).
