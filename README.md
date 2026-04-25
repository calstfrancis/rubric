# Rubric
[![Tests](https://github.com/calstfrancis/rubric/actions/workflows/tests.yml/badge.svg)](https://github.com/calstfrancis/rubric/actions/workflows/tests.yml)
A GNOME-native worship service planning tool for United Church of Canada ministry.

Rubric integrates the Revised Common Lectionary, hymn lookup for Voices United, More Voices, and Let Us Sing, Bible passage retrieval, and LaTeX export for professional bulletin production.

![Rubric screenshot](docs/screenshot.png)

---

## Features

- **RCL integration** — lectionary readings, liturgical colour, and season for any Sunday; weekday services default to the coming Sunday with a stepper
- **Lectionary year tracker** — persistent Year A/B/C and season indicator in the header
- **Hymn suggestions** — season and Proper-specific suggestions from VU, MV, and LUS; left-click to view on Hymnary.org, right-click to inject into the selected element
- **Hymn lookup** — type `VU 16` or `MV 120` to fetch the title from Hymnary.org
- **Bible viewer** — fetch World English Bible passages by reference; inserts formatted LaTeX with hanging verse-number indent
- **LaTeX export** — `extarticle`, two-column layout per liturgical movement, Junicode font, proper scripture environment
- **PDF compilation** — one-click xelatex compilation from within the app
- **Snippets library** — reusable liturgical texts (land acknowledgement, prayers of the people, lord's prayer, benediction, words of institution)
- **Responsive reading builder** — L:/P: syntax generates formatted LaTeX
- **Leader assignment** — per-element leader name exports as right-aligned italic in the section heading
- **Templates** — named service order templates with a chooser on new service
- **Tab view** — sections as notebook tabs with drag-and-drop between them
- **Git integration** — commit service files with a single button
- **CSV export** — for sharing with musicians and AV teams

---

## Requirements

- Python 3.10+
- GTK4 + libadwaita
- python3-gobject

```bash
sudo zypper install python3-gobject typelib-1_0-Adw-1 typelib-1_0-Gtk-4_0
```

For PDF compilation you also need TeX Live with xelatex. See [docs/texlive.md](docs/texlive.md) or the in-app TeX Live tab (Help → Welcome).

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
bible_api.py           World English Bible passage fetcher
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
- Bible text from the [World English Bible](https://worldenglish.bible/) (public domain)
- Built with [GTK4](https://gtk.org/) and [libadwaita](https://gnome.pages.gitlab.gnome.org/libadwaita/)

---

## License

GPL-3.0 — see [LICENSE](LICENSE)

---

*Developed at Atlantic School of Theology, Halifax, Nova Scotia.*
