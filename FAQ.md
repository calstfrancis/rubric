# Rubric — Frequently Asked Questions

## Simple Mode

**Q: What is Simple mode?**

Simple mode is the default experience for new users. It hides features that require LaTeX (PDF compilation, LaTeX export, responsive reading builder, snippets) and GitHub sync, keeping the interface focused on planning and writing. Bulletin export becomes an HTML file that opens in your browser — no TeX Live required.

Toggle it off any time in **Preferences → View → Simple mode**.

**Q: I turned off Simple mode. Where is everything?**

Close and reopen Preferences — new tabs appear for LaTeX preamble and Snippets. The toolbar gains the GitHub sync button and document/print icons. The hamburger menu expands with LaTeX export, CSV export, GitHub sync, snippets, and responsive reading options. All keyboard shortcuts continue to work regardless of mode.

**Q: I want to produce a proper print PDF for the bulletin. Do I need LaTeX?**

Yes, for the LaTeX-compiled PDF you need TeX Live + `memoir` package. In simple mode the bulletin exports as HTML — open it in your browser and use File → Print to produce a PDF. For most congregational use the HTML output is indistinguishable from the LaTeX version.

---

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

## Scripture Translations

**Q: Which translations are available?**

WEB (World English Bible), KJV (King James Version), ASV (American Standard Version), and ESV. WEB, KJV, and ASV are public domain and work with no setup. ESV requires a free API key from api.esv.org — ministry and bulletin use is explicitly permitted.

**Q: Can I use the NRSV?**

Not currently. The NRSV is under copyright and there is no clean public API for it. ESV is the closest licensed alternative with a free ministry-use API. If a usable NRSV endpoint becomes available, it will be added.

**Q: How do I set my ESV API key?**

Go to **Preferences → Scripture**, choose ESV from the dropdown, and paste your key into the API key field. Keys are available at api.esv.org — the free tier is sufficient for Rubric's use.

---

## Hymns

**Q: Right-clicking a hymn chip creates a new element instead of filling in the selected one.**

Make sure you have an element selected in the order list *before* right-clicking the chip. If nothing is selected, the fallback behaviour is to create a new "Hymn" element.

**Q: The hymn lookup returns the full book name in the title.**

Clear the hymn cache and re-fetch: `rm ~/.local/share/rubric/hymn_cache.json`. The title cleaning regex strips the book name prefix.

**Q: Hymnary says "not found" for a hymn I know exists.**

Hymnary's coverage is incomplete for LUS (Let Us Sing, 2022). Try the Hymnary website directly at hymnary.org. For VU and MV the coverage is generally good.

**Q: The suggestion chips show the same hymns every week in Ordinary Time.**

Update to the current version — Propers 4–29 now have specific suggestions based on each week's themes, blended with the season pool.

---

## Service Planner

**Q: How do I open the Service Planner?**

Hamburger menu → Service Planner, or Ctrl+Shift+L. If you have a GitHub repository configured, it scans the `liturgy/` subfolder automatically. Otherwise it asks you to choose a folder.

**Q: The planner doesn't show my files.**

Make sure your service files use the `.liturgy` extension and are in the folder the planner is pointed at. Click the Refresh button to rescan after adding or moving files.

**Q: The planner shows a file with the wrong date or title.**

The planner reads the `date` and `title` fields stored inside each `.liturgy` file — not the filename. Open the service, set the correct date in the title popover, and save it. The planner will reflect the update after a refresh.

---

## GitHub Sync

**Q: How do I set up GitHub sync?**

1. Create a new (empty) repository on GitHub — private is fine.
2. Open **Preferences → GitHub** in Rubric.
3. Click **Browse** and choose or create a local folder for the repository.
4. Click **Set up** — Rubric creates `liturgy/`, `tex/`, `pdf/`, `bulletins/` subfolders, a `.gitignore`, and runs `git init`.
5. Paste the GitHub remote URL into the Remote URL field and click **Connect**.
6. Click the **⟳** sync button in the toolbar (or Ctrl+Shift+G) to push for the first time.

**Q: The sync button gives an authentication error.**

GitHub no longer accepts passwords over HTTPS. Use a Personal Access Token (PAT) or set up SSH keys. For HTTPS: go to github.com → Settings → Developer settings → Personal access tokens. Use the token as your password when prompted, or store it with `git credential-store`.

**Q: I'm working on two computers. How do I pull changes from GitHub?**

Open **Preferences → GitHub** and click **Pull**. Or use the pull option from the hamburger menu. Always pull before editing on a different machine to avoid conflicts.

**Q: What gets committed when I push?**

The current service file (`.liturgy`) and its linked `.tex` file (if it exists) are staged and committed with the message `Service: Title – Date`. Then pushed to GitHub. The commit happens automatically — no commit message required.

**Q: Sync fails with "no upstream branch".**

This is handled automatically on first push. If it keeps appearing, check that your remote URL is set correctly in **Preferences → GitHub** and that you have at least one commit on the branch.

---

## LaTeX and PDF

**Q: I don't see the LaTeX export buttons.**

Simple mode is on (the default). Turn it off in **Preferences → View → Simple mode** to access LaTeX export, PDF compilation, and the LaTeX preamble editor.

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

**Q: Bulletin export gives a memoir class error.**

The print/booklet bulletin uses the `memoir` LaTeX class. Install it:
```bash
tlmgr install memoir
```
Or switch to simple mode — the HTML bulletin export requires no LaTeX at all.

**Q: Helper files (.log, .aux etc.) are piling up.**

They're cleaned automatically after a successful compile. If compilation fails they're left behind for diagnosis.

---

## Scripture (LaTeX formatting)

**Q: The scripture text is indented from the left margin.**

Go to **Preferences → LaTeX → Reset to default** to get the current preamble with the `{scripture}` environment. Then delete the old scripture from Notes/Content and re-fetch via the Bible Viewer.

**Q: Verse numbers and text run together without spacing.**

The `\sverse` macro uses `\quad` (one em) between the superscript and text. If you see no gap, you may have an old preamble — Reset to default.

**Q: The scripture is double-spaced between verses.**

The `{scripture}` environment sets `\parskip=0pt`. If you see gaps, the old `\begin{quotation}` format is still in Notes/Content. Open the `.liturgy` file — migration runs automatically — then re-export.

---

## Templates and Snippets

**Q: My old snippets are still showing after updating snippets.py.**

Delete the saved file to reset to defaults:
```bash
rm ~/.config/rubric/snippets.json
```

**Q: I saved a template but new services don't use it.**

Check that it's set as default in **Preferences → Templates** (look for the ★). With multiple templates you're asked which to use on New service.

**Q: I don't see the Snippets option in the menu.**

Snippets are hidden in simple mode. Turn off simple mode in **Preferences → View** to access them.

---

## Git (manual)

**Q: I want to use git manually without the GitHub sync feature.**

The hamburger menu's Git section (in advanced mode) offers a direct commit. Your `.liturgy` directory must already be a git repo (`git init`). The commit message is generated automatically from the service title and date.

**Q: "Not a git repository" error.**

The directory containing your `.liturgy` file must be inside a git repo. Run `git init` there, or move files into an existing repo.

---

## General

**Q: Where are my files?**

| File | Location |
|------|----------|
| Service files | Wherever you save them (`.liturgy`); defaults to `repo/liturgy/` if GitHub is configured |
| Config | `~/.config/rubric/config.json` |
| Snippets | `~/.config/rubric/snippets.json` |
| Hymn cache | `~/.local/share/rubric/hymn_cache.json` |
| Autosave | `~/.local/share/rubric/autosave.liturgy` |
| App code | `~/.local/share/rubric/` |
| Docs | `~/.local/share/rubric/HELP.md` etc. |

**Q: Can I undo and redo changes?**

Yes — Ctrl+Z to undo, Ctrl+Shift+Z to redo. The redo stack clears whenever you make a new change. Up to 50 undo steps are kept.
