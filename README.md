# Rubric

[![Tests](https://github.com/calstfrancis/rubric/actions/workflows/tests.yml/badge.svg)](https://github.com/calstfrancis/rubric/actions/workflows/tests.yml)

A GNOME-native worship service planning tool for United Church of Canada ministry.

Rubric integrates the Revised Common Lectionary, hymn lookup for Voices United, More Voices, and Let Us Sing, Bible passage retrieval, and export options for bulletin production.

---

## Features

- **Simple mode** (on by default) — keeps the interface focused for everyday planning. Toggle with the **SIMPLE** button in the status bar or in **Preferences → View**.
- **GOST Type B font** — toggle the engineering-style monoline font globally with the **GOST** button in the status bar
- **Focus mode** — hide the palette and element list for distraction-free editing (**Focus** button in the status bar)
- **Observance chips** — feast days and commemorations appear in the centre of the status bar as clickable chips; click any to open a Wikipedia article window
- **Git push** — commit and push the current service to GitHub with the **Git** button in the status bar
- **RCL integration** — lectionary readings, liturgical colour, and season for any Sunday; weekday services default to the coming Sunday with a stepper
- **Lectionary year tracker** — persistent Year A/B/C and season indicator in the header, updated daily
- **Hymn suggestions** — season and Proper-specific suggestions (Propers 4–29) from VU, MV, and LUS; left-click to view on Hymnary.org, right-click to inject into the selected element
- **Hymn lookup** — type `VU 16` or `MV 120` to fetch the title from Hymnary.org; inline Hymnary preview with WebKit (bundled)
- **Bible viewer** — fetch passages in WEB, KJV, ASV, or ESV (ESV requires a free API key from api.esv.org)
- **HTML export** — generates a clean, print-ready HTML file and opens it in the browser
- **Bulletin PDF export** — compiled with the bundled [Typst](https://typst.app/) typesetter; no LaTeX required
  - **Print (booklet)** — half-letter (5.5 × 8.5 in), fold for saddle-stitch
  - **Digital (screen PDF)** — full letter, colour hyperlinks
- **Rich text editor** — per-element formatting toolbar (bold, italic, headings, lists, leader notes) with a Typst toggle for raw source editing; both modes store the same Typst content
- **Live PDF preview** — bulletin compiles in the background as you edit
- **Per-element bulletin toggle** — marks each element shown or hidden in the bulletin independently of the leader copy
- **Bulletin preferences** — church name, address, service time, website, email, phone, welcome line, accessibility note, mission statement, staff/contact list, and announcements — all in **Preferences → Bulletin**
- **Announcement expiry** — each announcement carries an optional `YYYY-MM-DD` expiry date; expired announcements are omitted automatically
- **Past Liturgies archive** — browse every saved service in a read-only viewer; insert any past element's text into the current service with one click
- **Element Library** — searchable database of every element from every saved service
- **Bulletin preview panel** — live preview of the congregational bulletin as you edit; popout to a floating window
- **Service Planner** — scans the `liturgy/` folder and lists all services grouped into Upcoming and Past
- **GitHub repository sync** — push/pull services to a GitHub repository with one click
- **Repository-aware save paths** — Save As, Typst export, and bulletin export default to the right subfolder when a repository is configured
- **Scripture translation selector** — choose WEB, KJV, ASV, or ESV in **Preferences → Scripture**
- **Undo / Redo** — Ctrl+Z and Ctrl+Shift+Z
- **Snippets library** — reusable liturgical texts (advanced mode)
- **Responsive reading builder** — L:/P: syntax for formatted call-and-response text (advanced mode)
- **CSV export** — for sharing with musicians and AV teams (advanced mode)

---

## Installation

Rubric is distributed as a Flatpak via a self-hosted repository.

### Add the repository

```bash
flatpak remote-add --user calstfrancis \
  https://calstfrancis.github.io/flatpak/calstfrancis.flatpakrepo
```

### Install

```bash
flatpak install calstfrancis io.github.calstfrancis.rubric
```

### Update

```bash
flatpak update io.github.calstfrancis.rubric
```

### Uninstall

```bash
flatpak uninstall io.github.calstfrancis.rubric
```

---

## Usage

Launch from GNOME Shell or your desktop application launcher. On first launch, a welcome wizard offers three starting points: today's lectionary, a blank service, or a guided tour. Rubric remembers the last open file and reopens it automatically on subsequent launches.

---

## File format

Service files use the `.liturgy` extension (JSON). They store the service title, date, and ordered elements. Each element carries a `content_typst` field with Typst markup for both leader notes and bulletin text.

---

## Running tests

Backend/data-layer tests (no GTK required):

```bash
python3 -m unittest test_rcl_data test_bible_api -v
python3 -m unittest discover -s tests -v
```

The `tests/` package also includes `test_panels.py`, covering the composition-pattern
classes extracted from `MainWindow` (`BulletinExporter`, `BulletinPreview`,
`PreamblePanel`, `HymnLookupPanel`, `OrderPanel`, `PalettePanel`) against lightweight
stub windows. Those tests need GTK4/libadwaita's Python bindings (`python3-gi`,
`gir1.2-gtk-4.0`, `gir1.2-adw-1`) and are skipped automatically if unavailable —
CI runs them in a separate job that installs those packages.

---

## Project structure

```
rubric.py              Main application
rcl_data.py            RCL lectionary database and calendar logic
hymn_lookup.py         Hymnary.org title fetcher (VU, MV, LUS)
hymn_suggestions.py    Season and Proper-specific hymn suggestions
bible_api.py           Bible passage fetcher (WEB, KJV, ASV, ESV)
snippets.py            Default liturgical text snippets
observances.py         Liturgical calendar and observances intelligence
rubric_package/        Packaged models, utils, exporters, and data
HELP.md                User guide
FAQ.md                 Frequently asked questions
CHANGELOG.md           Version history
RELEASE.md             Release notes for the current version
```

---

## Contributing

Contributions welcome — bug reports, hymn suggestion additions, and UCC-specific liturgical content especially so.

Please open an issue before starting significant work.

---

## Acknowledgements

- Lectionary data from the [Revised Common Lectionary](https://lectionary.library.vanderbilt.edu/)
- Hymn data from [Hymnary.org](https://hymnary.org/)
- Bible text from the [World English Bible](https://worldenglish.bible/) (public domain), [King James Version](https://www.kingjamesbibleonline.org/) (public domain), [American Standard Version](https://www.biblegateway.com/versions/American-Standard-Version-ASV-Bible/) (public domain), and [ESV](https://api.esv.org/) (free ministry API)
- Built with [GTK4](https://gtk.org/) and [libadwaita](https://gnome.pages.gitlab.gnome.org/libadwaita/)

---

## License

GPL-3.0 — see [LICENSE](LICENSE)

---

*Developed at Atlantic School of Theology, Halifax, Nova Scotia.*
