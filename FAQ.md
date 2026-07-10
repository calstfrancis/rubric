# Rubric — Frequently Asked Questions

## Installation

**Q: How do I install Rubric?**

Rubric is distributed as a Flatpak. Add the repository and install:

```bash
flatpak remote-add --user calstfrancis \
  https://calstfrancis.github.io/flatpak/calstfrancis.flatpakrepo

flatpak install calstfrancis io.github.calstfrancis.rubric
```

**Q: How do I update to a new version?**

```bash
flatpak update io.github.calstfrancis.rubric
```

**Q: How do I uninstall?**

```bash
flatpak uninstall io.github.calstfrancis.rubric
```

User data (config, saved services, hymn cache) stays in `~/.config/rubric/` and `~/.local/share/rubric/`. Delete those folders if you want a clean slate.

**Q: Does Rubric need GTK4 or any system libraries installed separately?**

No. Flatpak bundles all dependencies in a sandbox. GTK4, libadwaita, Python, and all libraries are included.

**Q: I want the inline Hymnary preview but it opens in the browser instead.**

WebKit is bundled in the Flatpak and should work automatically. If the preview opens in the browser anyway, try relaunching Rubric.

---

## Simple Mode

**Q: What is Simple mode?**

Simple mode is the default experience. It hides GitHub sync, CSV export, snippets, and responsive reading builder, keeping the interface focused on planning and writing. PDF and HTML bulletin export are available in both modes.

Toggle it with the **SIMPLE** button in the status bar at the bottom of the window, or in **Preferences → View → Simple mode**.

**Q: I turned off Simple mode. Where is everything?**

The toolbar gains the GitHub sync button and document/print icons. The hamburger menu expands with CSV export, GitHub sync, snippets, and responsive reading options. All keyboard shortcuts continue to work regardless of mode.

---

## Status Bar

**Q: What are the buttons at the bottom of the window?**

The status bar (bottom of the window) contains:

| Button | Function |
|--------|---------|
| SIMPLE | Toggle Simple mode (bold = on) |
| GOST | Toggle GOST Type B engineering font globally (bold = on) |
| *Observance chips* (centre) | Feast days and commemorations for the service date — click to open Wikipedia |
| Focus | Hide the palette and element list for distraction-free editing (bold = on) |
| Git | Commit and push the current service to GitHub |
| v0.x.x | Version — click to open the changelog |

**Q: What is the GOST Type B font?**

GOST Type B is a Soviet engineering standard monoline lettering font. Toggling it applies the font to the entire Rubric interface. It is bundled and requires no separate installation.

**Q: What are the observance chips in the centre of the status bar?**

When a service date is set, Rubric checks for feasts, commemorations, and seasonal observances relevant to that date. They appear as small labelled chips. Click any chip to open a Wikipedia article about that observance in a built-in window (article text only, no sidebars).

**Q: The observance Wikipedia window is blank or shows an error.**

Rubric uses the Wikipedia REST API to load the article. If you have no internet connection, or Wikipedia is unreachable, an error page is shown instead with a button to open the article in your browser.

---

## Typst and PDF

**Q: Can I use custom Typst markup in my element content?**

Yes. Toggle any element to **Typst mode** (the **Typst** button at the top right of the content editor). You can enter any valid Typst, including functions not in Rubric's supported subset. The full Typst source is passed through to the compiled document unchanged. Just note that the rich-text editor can only display the subset it knows about — if you switch back to rich text, unsupported constructs appear as literal text (no data loss).

**Q: Where are the Typst template files?**

Bundled templates live inside the application package (read-only). Go to **Preferences → Typst Files**, click **Edit…** on any template, and **Save override** to create an editable copy at `~/.config/rubric/templates/<name>.typ`. Rubric checks that folder on every compile, so your changes persist across upgrades. Click **Reset to default** to remove an override.

**Q: The four template names are bulletin_print, bulletin_digital, manuscript, and _shared. What does _shared contain?**

`_shared.typ` defines Rubric's custom Typst functions: `#movement` (section heading), `#sverse` (verse with superscript number), `#scripture` (indented scripture block), `#leader-note` (grey box for leader-only notes), `#ldr` and `#ppl` (bold leader/people lines for responsive readings). Every generated document includes these automatically — you can redefine them in `_shared` to change how they look globally.

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

1. Open **Preferences → GitHub** in Rubric.
2. Click **Browse** and choose or create a local folder for the repository, then click **Set up** — Rubric creates `liturgy/`, `tex/`, `pdf/`, `bulletins/` subfolders, a `.gitignore`, and runs `git init`.
3. Click **Sign in with GitHub** and approve the request that opens in your browser.
4. Pick a repository name (private by default) and click **Create** — Rubric creates it on GitHub and connects it for you. Already have a repository? Use the manual **connect an existing repository** option below instead.
5. Click the **Git** button in the status bar (or Ctrl+Shift+G) to push for the first time.

**Q: The Git button gives an authentication error.**

If you've signed in with GitHub in Preferences, this shouldn't happen — try signing in again from **Preferences → GitHub**. If you're using the manual connection option instead, GitHub no longer accepts passwords over HTTPS: use a Personal Access Token (PAT) or set up SSH keys. For HTTPS: go to github.com → Settings → Developer settings → Personal access tokens. Use the token as your password when prompted, or store it with `git credential-store`.

**Q: I'm working on two computers. How do I pull changes from GitHub?**

Open **Preferences → GitHub** and click **Pull**. Always pull before editing on a different machine to avoid conflicts.

**Q: What gets committed when I push?**

The current service file (`.liturgy`) is staged and committed with the message `Service: Title – Date`, then pushed. The commit happens automatically — no commit message required.

**Q: Sync fails with "no upstream branch".**

This is handled automatically on first push. If it keeps appearing, check that your remote URL is set correctly in **Preferences → GitHub** and that you have at least one commit on the branch.

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

Snippets are hidden in simple mode. Turn off simple mode (SIMPLE button in the status bar, or **Preferences → View**) to access them.

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

**Q: Can I undo and redo changes?**

Yes — Ctrl+Z to undo, Ctrl+Shift+Z to redo. The redo stack clears whenever you make a new change. Up to 50 undo steps are kept.

**Q: Rubric didn't open my last file on launch.**

Rubric automatically opens the most recently saved file. If that file has been moved or deleted, it falls back to a blank service. You can also use **File → Open Recent** to find it.
