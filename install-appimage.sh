#!/usr/bin/env bash
# Register Rubric AppImage with the system desktop.
# Run from the project directory after building with build-appimage.sh.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Find the AppImage
APPIMAGE="$(ls "$SCRIPT_DIR"/Rubric-*.AppImage 2>/dev/null | sort -V | tail -1)"
if [ -z "$APPIMAGE" ]; then
    echo "No Rubric AppImage found. Run build-appimage.sh first."
    exit 1
fi

BIN_DIR="$HOME/.local/bin"
ICON_BASE="$HOME/.local/share/icons/hicolor"
DESKTOP_DIR="$HOME/.local/share/applications"
MIME_DIR="$HOME/.local/share/mime/packages"

echo "==> Installing $(basename "$APPIMAGE")"
mkdir -p "$BIN_DIR"
cp "$APPIMAGE" "$BIN_DIR/Rubric.AppImage"
chmod +x "$BIN_DIR/Rubric.AppImage"
ln -sf "$BIN_DIR/Rubric.AppImage" "$BIN_DIR/rubric"

echo "==> Writing desktop entry"
mkdir -p "$DESKTOP_DIR"
sed "s|Exec=rubric|Exec=$BIN_DIR/Rubric.AppImage|g" \
    "$SCRIPT_DIR/io.github.calstfrancis.rubric.desktop" \
    > "$DESKTOP_DIR/io.github.calstfrancis.rubric.desktop"

echo "==> Installing icons"
mkdir -p "$ICON_BASE/scalable/apps" "$ICON_BASE/symbolic/apps"
cp "$SCRIPT_DIR/rubric.svg"          "$ICON_BASE/scalable/apps/io.github.calstfrancis.rubric.svg"
cp "$SCRIPT_DIR/rubric-symbolic.svg" "$ICON_BASE/symbolic/apps/io.github.calstfrancis.rubric-symbolic.svg"

if command -v gtk4-update-icon-cache &>/dev/null; then
    gtk4-update-icon-cache -f -t "$ICON_BASE" 2>/dev/null || true
elif command -v gtk-update-icon-cache &>/dev/null; then
    gtk-update-icon-cache -f -t "$ICON_BASE" 2>/dev/null || true
fi

echo "==> Registering .liturgy MIME type"
mkdir -p "$MIME_DIR"
cat > "$MIME_DIR/rubric.xml" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
  <mime-type type="application/x-liturgy">
    <comment>Rubric service file</comment>
    <glob pattern="*.liturgy"/>
  </mime-type>
</mime-info>
EOF
if command -v update-mime-database &>/dev/null; then
    update-mime-database "$HOME/.local/share/mime" 2>/dev/null || true
fi
if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
fi

echo ""
echo "Done. Rubric is registered."
echo "  Launch from terminal:  rubric"
echo "  Or search 'Rubric' in your app launcher."
echo ""
echo "  To uninstall: bash uninstall-appimage.sh"
