# Rubric v0.17.5

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

**Bug-fix release** — several long-standing Typst compile failures and a broken HTML export are resolved.

- **Leader's order compile fixed** — the "Leader's order compile failed" toast appeared on any service element whose text ended with a line-break marker. The trailing `\` produced `\]` in the generated Typst, which is an escaped bracket rather than a block closer, leaving the content block unclosed. Fixed.
- **Stray `]` in content no longer breaks compile** — a bare `]` in liturgy text (e.g. `[All:]` choral notation) could prematurely close the surrounding `#columns` block. Unmatched brackets are now escaped before insertion.
- **HTML export works again** — "Could not show link, launch failed" appeared because the HTML was written to a sandboxed `/tmp` location the browser could not reach. The file now goes to the cache directory in the home folder.
- **Compile button no longer requires a prior export** — if no `.typ` file was linked to the service, the compile button now writes it automatically.
- **PDFs open automatically** — after a successful compile the PDF opens in the system viewer immediately.
- **Compile errors logged** — full typst output is written to `~/.cache/rubric/compile-error.log` on failure.

---

### Full changelog

See [CHANGELOG.md](CHANGELOG.md).
