#!/bin/bash
# Build Rubric.AppImage
# Uses mksquashfs + AppImage runtime directly — no appimagetool, no AppImageLauncher issues.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APPDIR="$SCRIPT_DIR/AppDir"
VERSION="$(python3 -c "import re; print(re.search(r'APP_VERSION\s*=\s*[\"\'](.*?)[\"\']', open('rubric.py').read()).group(1))")"
OUTPUT="$SCRIPT_DIR/Rubric-$VERSION-x86_64.AppImage"
RUNTIME="$SCRIPT_DIR/.appimage-runtime-x86_64"
RUNTIME_URL="https://github.com/AppImage/type2-runtime/releases/download/continuous/runtime-x86_64"

echo "Building Rubric $VERSION AppImage..."

# ── Populate AppDir ────────────────────────────────────────────────────────────
DEST="$APPDIR/usr/share/rubric"
mkdir -p "$DEST"
cp rubric.py bible_api.py hymn_lookup.py hymn_suggestions.py rcl_data.py snippets.py "$DEST/"
cp -r data "$DEST/"
cp -r rubric_package "$DEST/"
for f in HELP.md FAQ.md CHANGELOG.md; do
    [ -f "$SCRIPT_DIR/$f" ] && cp "$SCRIPT_DIR/$f" "$DEST/"
done

cp io.github.calstfrancis.rubric.desktop "$APPDIR/"
mkdir -p "$APPDIR/usr/share/applications"
cp io.github.calstfrancis.rubric.desktop "$APPDIR/usr/share/applications/"

cp rubric.svg "$APPDIR/io.github.calstfrancis.rubric.svg"
mkdir -p "$APPDIR/usr/share/icons/hicolor/scalable/apps"
cp rubric.svg "$APPDIR/usr/share/icons/hicolor/scalable/apps/io.github.calstfrancis.rubric.svg"
mkdir -p "$APPDIR/usr/share/icons/hicolor/symbolic/apps"
cp rubric-symbolic.svg "$APPDIR/usr/share/icons/hicolor/symbolic/apps/io.github.calstfrancis.rubric-symbolic.svg"

mkdir -p "$APPDIR/usr/share/metainfo"
cp io.github.calstfrancis.rubric.metainfo.xml "$APPDIR/usr/share/metainfo/"

# ── Download AppImage runtime (cached) ────────────────────────────────────────
if [ ! -f "$RUNTIME" ]; then
    echo "Downloading AppImage runtime..."
    wget -q --show-progress -O "$RUNTIME" "$RUNTIME_URL"
fi

# ── Pack squashfs + prepend runtime ───────────────────────────────────────────
echo "Packing squashfs..."
SQUASHFS="$(mktemp /tmp/rubric-XXXXXX.squashfs)"
mksquashfs "$APPDIR" "$SQUASHFS" -root-owned -noappend -comp zstd -quiet

echo "Assembling AppImage..."
cat "$RUNTIME" "$SQUASHFS" > "$OUTPUT"
chmod +x "$OUTPUT"
rm "$SQUASHFS"

echo ""
echo "Done: $(basename "$OUTPUT")"
