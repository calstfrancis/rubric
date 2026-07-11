# Rubric v0.19.0 "Open Door"

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

**Sign in with GitHub.** The setup wizard and Preferences → GitHub now lead with a "Sign in with GitHub" button (device-flow OAuth, the same approach as Zerkalo) instead of asking for a Personal Access Token. Once signed in, click Create to have Rubric create and connect a new repository automatically. The manual "paste a repository URL" + PAT flow is still available as a fallback for anyone who prefers it.

**More secure token storage.** The GitHub token is now stored in the system keyring (via libsecret), not in a config file.

---

### Full changelog

See [CHANGELOG.md](CHANGELOG.md).
