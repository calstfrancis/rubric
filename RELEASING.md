# Releasing Rubric

Releases are published to PyPI automatically via GitHub Actions when a version tag is pushed.

---

## Checklist

1. **Update `CHANGELOG.md`** — add a new `## X.Y.Z` section at the top with Added and Fixed entries.

2. **Bump the version** in `pyproject.toml`:

   ```toml
   version = "X.Y.Z"
   ```

3. **Commit the changes**:

   ```bash
   git add pyproject.toml CHANGELOG.md
   git commit -m "release X.Y.Z"
   ```

4. **Tag and push**:

   ```bash
   git tag vX.Y.Z
   git push && git push --tags
   ```

5. **Watch the workflow** — go to the repository's **Actions** tab on GitHub. The `Publish to PyPI` workflow triggers automatically on the tag push. It builds the wheel and source distribution, then uploads both to PyPI using trusted publisher (OIDC — no API token required).

6. **Verify on PyPI** — once the workflow completes, check that the new version appears at https://pypi.org/project/rubric-liturgy/.

---

## Versioning

Rubric uses `MAJOR.MINOR.PATCH` (e.g. `0.13.0`):

- **PATCH** — bug fixes, small improvements with no new features
- **MINOR** — new features that are backwards compatible
- **MAJOR** — significant changes or breaking changes (unlikely until 1.0)

---

## PyPI trusted publisher setup (one-time)

This was configured once. No action needed for routine releases. For reference, the trusted publisher on PyPI is configured as:

- **PyPI project**: `rubric-liturgy`
- **GitHub owner**: `calstfrancis`
- **Repository**: `rubric`
- **Workflow filename**: `publish.yml`
- **Environment name**: `release`

The matching GitHub environment (`release`) is configured under **Repository → Settings → Environments**.

---

## Troubleshooting

**Workflow fails at "Publish to PyPI"**

- Confirm the `release` environment exists in GitHub repository settings.
- Confirm the trusted publisher on PyPI matches the repository name, owner, workflow filename, and environment name exactly.
- If PyPI rejects the upload with a version conflict, the tag version already exists on PyPI — bump the version and re-tag.

**Build fails**

Run the build locally to reproduce:

```bash
pip install build
python3 -m build
```

Inspect `dist/` to confirm the wheel includes `rubric_package/data/`.
