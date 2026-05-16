# Rubric
[![Tests](https://github.com/calstfrancis/rubric/actions/workflows/tests.yml/badge.svg)](https://github.com/calstfrancis/rubric/actions/workflows/tests.yml)
A GNOME-native worship service planning tool for United Church of Canada ministry.

Rubric integrates the Revised Common Lectionary, hymn lookup for Voices United, More Voices, and Let Us Sing, Bible passage retrieval, and export options for bulletin production.

![Rubric screenshot](docs/screenshot.png)

---

## Features

- **Simple mode** (on by default) — hides LaTeX, GitHub sync, CSV export, snippets, responsive reading, and the LaTeX preamble preference. All features remain accessible when turned off. Toggle in **Preferences → View → Simple mode**.
- **RCL integration** — lectionary readings, liturgical colour, and season for any Sunday; weekday services default to the coming Sunday with a stepper
- **Lectionary year tracker** — persistent Year A/B/C and season indicator in the header, updated daily
- **Hymn suggestions** — season and Proper-specific suggestions (Propers 4–29) from VU, MV, and LUS; left-click to view on Hymnary.org, right-click to inject into the selected element
- **Hymn lookup** — type `VU 16` or `MV 120` to fetch the title from Hymnary.org; optional inline Hymnary preview via WebKit
- **Bible viewer** — fetch passages in WEB, KJV, ASV, or ESV (ESV requires a free API key from api.esv.org)
- **HTML export** — generates a clean, print-ready HTML file and opens it in the browser; use File → Print for a PDF without LaTeX
- **Congregational bulletin export**
  - **Simple mode** — HTML bulletin opens in the browser (no LaTeX required)
  - **Advanced mode** — LaTeX-compiled PDF for print or digital
    - **Print (booklet)** — `memoir` class, half-letter (5.5 × 8.5 in), fold for saddle-stitch
    - **Digital (screen PDF)** — `extarticle`, full letter, colour hyperlinks
- **Per-element bulletin toggle** — the 📋 button marks each element shown or hidden in the bulletin independently of the leader copy
- **Bulletin preferences** — church name, address, service time, website, email, phone, welcome line, accessibility note, mission statement, staff/contact list, and announcements — all in **Preferences → Bulletin**
- **Announcement expiry** — each announcement carries an optional `YYYY-MM-DD` expiry date; expired announcements are omitted automatically
- **Service Planner** — scans the `liturgy/` folder (or any folder) and lists all services grouped into Upcoming and Past, sorted by date. Click any row to open that service.
- **GitHub repository sync** — set up a local git repository from **Preferences → GitHub** and push/pull to GitHub with one click. Creates `liturgy/`, `tex/`, `pdf/`, `bulletins/` subfolders automatically.
- **Repository-aware save paths** — when a GitHub repository is configured, Save As defaults to `repo/liturgy/`, Export LaTeX to `repo/tex/`, bulletin export to `repo/bulletins/`, and compiled PDFs move automatically to `repo/pdf/` or `repo/bulletins/`.
- **Scripture translation selector** — choose WEB, KJV, ASV, or ESV in **Preferences → Scripture**
- **Undo / Redo** — Ctrl+Z and Ctrl+Shift+Z
- **LaTeX export** — `extarticle`, two-column layout per liturgical movement, Junicode font, proper scripture environment (advanced mode)
- **PDF compilation** — one-click xelatex compilation from within the app (advanced mode)
- **Snippets library** — reusable liturgical texts (advanced mode)
- **Responsive reading builder** — L:/P: syntax generates formatted LaTeX (advanced mode)
- **Leader assignment** — per-element leader name exports as right-aligned italic in the section heading
- **Templates** — named service order templates with a chooser on new service
- **Tab view** — sections as notebook tabs with drag-and-drop between them
- **CSV export** — for sharing with musicians and AV teams (advanced mode)
- **GitHub Actions CI** — automated test run on every push

---

## Requirements

- Python 3.10+
- GTK4 + libadwaita
- python3-gobject

```bash
sudo zypper install python3-gobject typelib-1_0-Adw-1 typelib-1_0-Gtk-4_0
```

LaTeX (xelatex + Junicode + `memoir` package) is only needed for PDF compilation and the advanced bulletin export. In simple mode, HTML export covers all bulletin and service order needs with no TeX Live required. See [docs/texlive.md](docs/texlive.md) or the in-app TeX Live tab (Help → Welcome) if you want PDF output.

---

## Installation

```bash
git clone https://github.com/calstfrancis/rubric.git
cd rubric
bash install.sh
```

The install script:
- Copies app files to `~/.local/share/rubric/`
- Creates a launcher at `~/.local/bin/rubric`
- Installs the desktop entry and icons
- Registers the `.liturgy` MIME type

---

## Usage

Run from the terminal:

```bash
rubric
```

Or search for **Rubric** in GNOME Shell / KRunner.

On first launch, a welcome dialog explains the main features and provides TeX Live installation instructions.

---

## File format

Service files use the `.liturgy` extension (JSON). They store the service title, date, ordered elements with notes and leader assignments, and the path to the linked `.tex` export file.

---

## Running tests

```bash
# From the rubric directory:
python3 -m unittest test_rcl_data test_bible_api -v

# Or individually:
python3 -m unittest test_rcl_data -v   # RCL date calculations
python3 -m unittest test_bible_api -v  # Bible reference cleaning
```

```
rubric.py              Main application
rcl_data.py            RCL lectionary database and calendar logic
hymn_lookup.py         Hymnary.org title fetcher (VU, MV, LUS)
hymn_suggestions.py    Season and Proper-specific hymn suggestions
bible_api.py           Bible passage fetcher (WEB, KJV, ASV, ESV)
snippets.py            Default liturgical text snippets
install.sh             Installation script
test_rcl_data.py       Tests for RCL date calculations
test_bible_api.py      Tests for Bible reference cleaning
HELP.md                User guide
FAQ.md                 Frequently asked questions
CHANGELOG.md           Version history
docs/texlive.md        TeX Live installation guide
```

---

## Contributing

Rubric is a young project. Contributions welcome — bug reports, hymn suggestion additions, and UCC-specific liturgical content especially so.

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
