#!/bin/bash
# Build Rubric.AppImage
# Requires: appimagetool (download from https://github.com/AppImage/appimagetool/releases)
#
#   wget -O appimagetool https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
#   chmod +x appimagetool

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APPDIR="$SCRIPT_DIR/AppDir"
VERSION="$(python3 -c "import re; print(re.search(r'APP_VERSION\s*=\s*[\"\'](.*?)[\"\']', open('rubric.py').read()).group(1))")"

echo "Building Rubric $VERSION AppImage..."

# Populate AppDir/usr/share/rubric/
DEST="$APPDIR/usr/share/rubric"
mkdir -p "$DEST"
cp rubric.py bible_api.py hymn_lookup.py hymn_suggestions.py rcl_data.py snippets.py "$DEST/"
cp -r data "$DEST/"
cp -r rubric_package "$DEST/"
for f in HELP.md FAQ.md CHANGELOG.md; do
    [ -f "$SCRIPT_DIR/$f" ] && cp "$SCRIPT_DIR/$f" "$DEST/"
done

# Desktop file (AppImage spec requires one at root and in usr/share/applications)
cp io.github.calstfrancis.rubric.desktop "$APPDIR/"
mkdir -p "$APPDIR/usr/share/applications"
cp io.github.calstfrancis.rubric.desktop "$APPDIR/usr/share/applications/"

# Icons (AppImage spec requires icon at root named <AppId>.<ext>)
cp rubric.svg "$APPDIR/io.github.calstfrancis.rubric.svg"
mkdir -p "$APPDIR/usr/share/icons/hicolor/scalable/apps"
cp rubric.svg "$APPDIR/usr/share/icons/hicolor/scalable/apps/io.github.calstfrancis.rubric.svg"
mkdir -p "$APPDIR/usr/share/icons/hicolor/symbolic/apps"
cp rubric-symbolic.svg "$APPDIR/usr/share/icons/hicolor/symbolic/apps/io.github.calstfrancis.rubric-symbolic.svg"

# Metainfo
mkdir -p "$APPDIR/usr/share/metainfo"
cp io.github.calstfrancis.rubric.metainfo.xml "$APPDIR/usr/share/metainfo/"

echo "AppDir ready. Running appimagetool..."

OUTPUT="Rubric-$VERSION-x86_64.AppImage"

if command -v appimagetool >/dev/null 2>&1; then
    APPIMAGETOOL="appimagetool"
elif [ -f "$SCRIPT_DIR/appimagetool" ]; then
    APPIMAGETOOL="$SCRIPT_DIR/appimagetool"
else
    echo "appimagetool not found. Download it:"
    echo "  wget -O appimagetool https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
    echo "  chmod +x appimagetool"
    exit 1
fi

APPIMAGE_EXTRACT_AND_RUN=1 "$APPIMAGETOOL" "$APPDIR" "$OUTPUT"
echo ""
echo "Done: $OUTPUT"
