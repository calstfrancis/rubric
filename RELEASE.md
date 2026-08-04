# Rubric v0.20.0 "Plain Chant"

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

**Your writing is a document now, not markup.** The editor used to be a Typst editor wearing a rich-text costume, and anything it couldn't translate was shown to you verbatim — which is why services filled up with `#linebreak()` nobody typed. Content is stored as the document itself: paragraphs, headings, lists, leader notes, bold and italic. Typst is generated only when something is printed, so markup has nowhere to leak in from, and templates can decide how a service looks without any of that reaching the place you write.

**Saving can no longer lose a service.** Services and autosaves are written to a temporary file and renamed into place, so a crash, a power cut, or a full disk part-way through leaves the previous version completely intact. A successful save is also no longer reported as a failure when something unrelated — the library index, the preview — has a problem.

**The service order reads as a shape.** Each section carries a colour dot, its element count and its running time, with its elements grouped into a single card. Elements are one line each: a coloured cue, the title, a reference where there is one, and who leads it. The element palette and the preview panel are built to the same design.

**The window was rebuilt.** Four distinct surfaces instead of near-identical greys; the liturgical colour stated once rather than four times over; a menu reorganised along GNOME's guidelines with app-level items last; Services and save-to-GitHub as plain words in the status bar; and a System / Light / Dark theme choice plus an interface font setting under Preferences.

**Sync conflicts are resolved in the app.** If Push or Pull finds changes made on another computer, Rubric walks you through each conflicting file with a plain-language choice — Keep Mine, Keep Theirs, or Keep Both — instead of telling you to open a terminal.

---

### Upgrading

Services written by earlier versions migrate the first time you open and save them; no wording is lost. Once a service has been saved by this version, **older builds of Rubric will show its elements as empty** — the content is in the file, under a key they don't know to read. Keep a copy of anything you still need to open elsewhere.

---

### Full changelog

See [CHANGELOG.md](CHANGELOG.md).
