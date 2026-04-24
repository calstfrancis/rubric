# Rubric — Frequently Asked Questions

## Installation

**Q: The icon shows as a "W" or generic letter in the GNOME panel.**

Re-run `bash install.sh`. Icons are installed under both `rubric.svg` and `io.github.calstfrancis.rubric.svg`. Log out and back in if it persists.

**Q: I get "Dependencies missing" when running install.sh.**

```bash
python3 -c "import gi; gi.require_version('Gtk','4.0'); gi.require_version('Adw','1'); from gi.repository import Gtk, Adw; print('OK')"
```

If you see symbol errors, run `sudo zypper dup` to sync GLib/GTK4 versions.

**Q: I want the inline Hymnary preview but it opens in the browser instead.**

Install WebKit: `sudo zypper install python3-webkit2`. After installing, restart Rubric — it detects WebKit at launch.

---

## Readings and Lectionary

**Q: The lectionary year tracker in the header shows the wrong year.**

The RCL year changes on Advent Sunday (not January 1). If you're between Advent Sunday and December 31, the new year has already started. The tracker uses today's date via `get_liturgical_info`.

**Q: The readings card shows Sunday's readings but my service is on a Thursday.**

By design. The ← → stepper at the bottom of the readings card lets you navigate to the previous or next Sunday. For Thursday chapels, the default is the coming Sunday's readings.

**Q: The Bible Viewer says "Passage not found".**

The WEB API sometimes can't parse complex RCL references (e.g. `Ps 119:1-8, 22-24`). Try simplifying — `Ps 119` — or type the reference directly in the Scripture field in the item toolbar.

---

## Hymns

**Q: Right-clicking a hymn chip creates a new element instead of filling in the selected one.**

Make sure you have an element selected in the order list *before* right-clicking the chip. If nothing is selected, the fallback behaviour is to create a new "Hymn" element.

**Q: The hymn lookup returns the full book name in the title.**

Clear the hymn cache and re-fetch: `rm ~/.local/share/rubric/hymn_cache.json`. The title cleaning regex now strips the book name prefix.

**Q: Hymnary says "not found" for a hymn I know exists.**

Hymnary's coverage is incomplete for LUS (Let Us Sing, 2022). Try the Hymnary website directly at hymnary.org. For VU and MV the coverage is generally good.

**Q: The suggestion chips show the same hymns every week in Ordinary Time.**

Update to the current version — Propers 4–29 now have specific suggestions based on each week's themes, blended with the season pool.

---

## Scripture

**Q: The scripture text is indented from the left margin.**

Go to **Preferences → LaTeX → Reset to default** to get the current preamble with the `{scripture}` environment. Then delete the old scripture from Notes/Content and re-fetch via the Bible Viewer.

**Q: Verse numbers and text run together without spacing.**

The `\sverse` macro uses `\quad` (one em) between the superscript and text. If you see no gap, you may have an old preamble — Reset to default.

**Q: The scripture is double-spaced between verses.**

The `{scripture}` environment sets `\parskip=0pt`. If you see gaps, the old `\begin{quotation}` format is still in Notes/Content. Open the `.liturgy` file — migration runs automatically — then re-export.

---

## LaTeX and PDF

**Q: xelatex can't find Junicode.**

```bash
# Via tlmgr:
tlmgr install junicode
# Or via zypper:
sudo zypper install junicode-fonts
```

Or change `\setmainfont{Junicode}` in Preferences → LaTeX to any font you have (e.g. `Linux Libertine O`, `Gentium Plus`).

**Q: The PDF compile button is greyed out during compilation.**

It re-enables automatically when xelatex finishes. If it stays greyed out, xelatex may have hung — kill it from a terminal and restart the app.

**Q: xelatex not found.**

Add TeX Live to your PATH:
```bash
# Add to ~/.bashrc:
export PATH="$HOME/texlive/bin/x86_64-linux:$PATH"
```

**Q: Compilation fails with a multicol error.**

```bash
tlmgr install multicol
```

**Q: Helper files (.log, .aux etc.) are piling up.**

They're cleaned automatically after a successful compile. If compilation fails they're left behind for diagnosis.

---

## Templates and Snippets

**Q: My old snippets are still showing after updating snippets.py.**

Delete the saved file to reset to defaults:
```bash
rm ~/.config/rubric/snippets.json
```

**Q: I saved a template but new services don't use it.**

Check that it's set as default in **Preferences → Templates** (look for the ★). With multiple templates you're asked which to use on New service.

---

## Git

**Q: "Not a git repository" error.**

The directory containing your `.liturgy` file must be inside a git repo. Run `git init` there, or move files into an existing repo.

**Q: "Nothing to commit".**

No changes since the last commit. Make a change before committing.

---

## General

**Q: Where are my files?**

| File | Location |
|------|----------|
| Service files | Wherever you save them (`.liturgy`) |
| Config | `~/.config/rubric/config.json` |
| Snippets | `~/.config/rubric/snippets.json` |
| Hymn cache | `~/.local/share/rubric/hymn_cache.json` |
| Autosave | `~/.local/share/rubric/autosave.liturgy` |
| App code | `~/.local/share/rubric/` |
| Docs | `~/.local/share/rubric/HELP.md` etc. |
