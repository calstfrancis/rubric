#!/bin/bash
# Build Rubric self-extracting AppImage.
#
# The output is a shell script with a tar.gz payload appended — no FUSE,
# no AppImageLauncher interception, no special tools needed to run it.
# Works on any Linux with bash, python3, and GTK4 + libadwaita.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VERSION="$(python3 -c "import re; print(re.search(r'APP_VERSION\s*=\s*[\"\'](.*?)[\"\']', open('rubric.py').read()).group(1))")"
OUTPUT="$SCRIPT_DIR/Rubric-$VERSION-x86_64.AppImage"
WORK="$(mktemp -d)"
trap "rm -rf '$WORK'" EXIT

echo "Building Rubric $VERSION AppImage..."

# ── Assemble payload directory ─────────────────────────────────────────────────
PAYLOAD="$WORK/payload"
APP="$PAYLOAD/usr/share/rubric"
mkdir -p "$APP"

cp rubric.py bible_api.py hymn_lookup.py hymn_suggestions.py rcl_data.py snippets.py observances.py "$APP/"

# rubric_package — strip __pycache__ so bundled .pyc files don't conflict
# with the Python version on the target machine
cp -r rubric_package "$APP/"
find "$APP/rubric_package" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find "$APP/rubric_package" -name "*.pyc" -delete 2>/dev/null || true

for f in HELP.md FAQ.md CHANGELOG.md; do
    [ -f "$SCRIPT_DIR/$f" ] && cp "$SCRIPT_DIR/$f" "$APP/"
done

mkdir -p "$PAYLOAD/usr/share/applications"
cp io.github.calstfrancis.rubric.desktop "$PAYLOAD/usr/share/applications/"

mkdir -p "$PAYLOAD/usr/share/icons/hicolor/scalable/apps"
cp rubric.svg "$PAYLOAD/usr/share/icons/hicolor/scalable/apps/io.github.calstfrancis.rubric.svg"
mkdir -p "$PAYLOAD/usr/share/icons/hicolor/symbolic/apps"
cp rubric-symbolic.svg "$PAYLOAD/usr/share/icons/hicolor/symbolic/apps/io.github.calstfrancis.rubric-symbolic.svg"

mkdir -p "$PAYLOAD/usr/share/metainfo"
cp io.github.calstfrancis.rubric.metainfo.xml "$PAYLOAD/usr/share/metainfo/"

cp AppDir/AppRun "$PAYLOAD/AppRun"
chmod +x "$PAYLOAD/AppRun"

# ── Pack payload ───────────────────────────────────────────────────────────────
echo "Packing payload..."
tar czf "$WORK/payload.tar.gz" -C "$PAYLOAD" .

# ── Write launcher header ──────────────────────────────────────────────────────
cat > "$WORK/header.sh" << 'HEADER'
#!/bin/sh
# Rubric AppImage — self-extracting, no FUSE required
TMPDIR=$(mktemp -d /tmp/rubric-XXXXXX)
cleanup() { rm -rf "$TMPDIR"; }
trap cleanup EXIT INT TERM HUP
SKIP=$(awk '/^__PAYLOAD__/{print NR+1;exit}' "$0")
tail -n +"$SKIP" "$0" | tar xz -C "$TMPDIR" 2>/dev/null
exec "$TMPDIR/AppRun" "$@"
exit 1
__PAYLOAD__
HEADER

# ── Assemble ───────────────────────────────────────────────────────────────────
cat "$WORK/header.sh" "$WORK/payload.tar.gz" > "$OUTPUT"
chmod +x "$OUTPUT"

echo ""
echo "Done: $(basename "$OUTPUT")  ($(du -sh "$OUTPUT" | cut -f1))"
