#!/bin/bash
# build-deb.sh — Build a Debian/Ubuntu .deb package for Rubric.
#
# Requires: ar, tar, gzip (standard on any Linux)
# Output:   rubric-liturgy_<version>_all.deb in the project directory
#
# Install the resulting .deb:
#   sudo dpkg -i rubric-liturgy_*.deb
#   sudo apt install ./rubric-liturgy_*.deb   (resolves deps automatically)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

VERSION="$(python3 -c "import re; print(re.search(r'APP_VERSION\s*=\s*[\"\'](.*?)[\"\']', open('rubric.py').read()).group(1))")"
NAME="rubric-liturgy"

echo "Building Rubric $VERSION deb package..."

WORK="$(mktemp -d)"
trap "rm -rf '$WORK'" EXIT

# ── Assemble filesystem tree ───────────────────────────────────────────────────
ROOT="$WORK/root"
APPDIR="$ROOT/usr/share/rubric"
mkdir -p "$APPDIR"
mkdir -p "$ROOT/usr/bin"
mkdir -p "$ROOT/usr/share/applications"
mkdir -p "$ROOT/usr/share/icons/hicolor/scalable/apps"
mkdir -p "$ROOT/usr/share/icons/hicolor/symbolic/apps"
mkdir -p "$ROOT/usr/share/metainfo"
mkdir -p "$ROOT/usr/share/mime/packages"
mkdir -p "$ROOT/usr/share/doc/$NAME"

# Python source files
cp rubric.py rcl_data.py observances.py "$APPDIR/"
for f in hymn_lookup.py hymn_suggestions.py bible_api.py snippets.py; do
    [ -f "$f" ] && cp "$f" "$APPDIR/"
done

# rubric_package
cp -r rubric_package "$APPDIR/"
find "$APPDIR/rubric_package" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find "$APPDIR/rubric_package" -name "*.pyc" -delete 2>/dev/null || true

# Documentation bundled in app dir
for f in HELP.md FAQ.md CHANGELOG.md; do
    [ -f "$f" ] && cp "$f" "$APPDIR/" || true
done
[ -f LICENSE ] && install -m 644 LICENSE "$ROOT/usr/share/doc/$NAME/copyright"

# Launcher script
cat > "$ROOT/usr/bin/rubric" << 'LAUNCHER'
#!/bin/bash
exec python3 /usr/share/rubric/rubric.py "$@"
LAUNCHER
chmod 755 "$ROOT/usr/bin/rubric"

# Desktop integration
cp io.github.calstfrancis.rubric.desktop "$ROOT/usr/share/applications/"
cp rubric.svg "$ROOT/usr/share/icons/hicolor/scalable/apps/rubric.svg"
cp rubric.svg "$ROOT/usr/share/icons/hicolor/scalable/apps/io.github.calstfrancis.rubric.svg"
cp rubric-symbolic.svg "$ROOT/usr/share/icons/hicolor/symbolic/apps/rubric-symbolic.svg"
cp rubric-symbolic.svg "$ROOT/usr/share/icons/hicolor/symbolic/apps/io.github.calstfrancis.rubric-symbolic.svg"
cp io.github.calstfrancis.rubric.metainfo.xml "$ROOT/usr/share/metainfo/"

cat > "$ROOT/usr/share/mime/packages/rubric.xml" << 'MIMEEOF'
<?xml version="1.0" encoding="UTF-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
  <mime-type type="application/x-liturgy">
    <comment>Rubric service file</comment>
    <glob pattern="*.liturgy"/>
  </mime-type>
</mime-info>
MIMEEOF

# ── Control archive ────────────────────────────────────────────────────────────
SIZE=$(du -sk "$ROOT" | cut -f1)
CTRLDIR="$WORK/control"
mkdir -p "$CTRLDIR"

cat > "$CTRLDIR/control" << EOF
Package: rubric-liturgy
Version: $VERSION
Section: misc
Priority: optional
Architecture: all
Installed-Size: $SIZE
Depends: python3 (>= 3.10), python3-gi, python3-gi-cairo, gir1.2-gtk-4.0, gir1.2-adw-1
Maintainer: Cal St. Francis <calstfrancis@gmail.com>
Homepage: https://github.com/calstfrancis/rubric
Description: GNOME worship service planning tool for UCC ministry
 Rubric is a GNOME-native worship service planning tool for United Church
 of Canada ministry. Integrates the Revised Common Lectionary, hymn lookup
 for Voices United, More Voices, and Let Us Sing, Bible passage retrieval,
 and HTML/PDF bulletin export.
 .
 Simple mode requires no LaTeX — plan, export HTML, print from browser.
 Advanced mode adds PDF compilation via xelatex and LaTeX export.
EOF

cat > "$CTRLDIR/postinst" << 'POSTINST'
#!/bin/sh
set -e
update-mime-database /usr/share/mime 2>/dev/null || true
update-desktop-database /usr/share/applications 2>/dev/null || true
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
fi
POSTINST
chmod 755 "$CTRLDIR/postinst"

cat > "$CTRLDIR/postrm" << 'POSTRM'
#!/bin/sh
set -e
update-mime-database /usr/share/mime 2>/dev/null || true
update-desktop-database /usr/share/applications 2>/dev/null || true
POSTRM
chmod 755 "$CTRLDIR/postrm"

tar czf "$WORK/control.tar.gz" --format=gnu -C "$CTRLDIR" .

# ── Data archive ───────────────────────────────────────────────────────────────
tar czf "$WORK/data.tar.gz" --format=gnu -C "$ROOT" .

# ── Assemble .deb (ar archive) ─────────────────────────────────────────────────
printf '2.0\n' > "$WORK/debian-binary"

OUTPUT="$SCRIPT_DIR/${NAME}_${VERSION}_all.deb"

# Write the ar archive with Python to guarantee correct format:
# - uid/gid = 0 (root) in ar headers, as dpkg-deb produces
# - no duplicate members (ar qc appends to existing files)
# - no extended symbol table entries
python3 - << PYEOF
import os, sys

members = [
    ('debian-binary', '$WORK/debian-binary'),
    ('control.tar.gz', '$WORK/control.tar.gz'),
    ('data.tar.gz', '$WORK/data.tar.gz'),
]

with open('$OUTPUT', 'wb') as out:
    out.write(b'!<arch>\n')
    for name, path in members:
        data = open(path, 'rb').read()
        size = len(data)
        # 60-byte ar member header (GNU ar / dpkg-deb format)
        header = (
            (name + '/').encode().ljust(16) +   # name, slash-terminated, space-padded
            b'0           ' +                    # mtime  (12 chars)
            b'0     ' +                          # uid=0  (6 chars)
            b'0     ' +                          # gid=0  (6 chars)
            b'100644  ' +                        # mode   (8 chars)
            str(size).encode().ljust(10) +       # size   (10 chars)
            b'\`\n'                              # magic  (2 chars)
        )
        out.write(header)
        out.write(data)
        if size % 2:
            out.write(b'\n')  # ar requires even-length members
PYEOF

echo ""
echo "Done: $(basename "$OUTPUT")  ($(du -sh "$OUTPUT" | cut -f1))"
echo ""
echo "Install:"
echo "  sudo dpkg -i $(basename "$OUTPUT")"
echo "  sudo apt install ./$(basename "$OUTPUT")   (resolves deps automatically)"
