#!/usr/bin/env bash
# Remove the Rubric AppImage desktop registration.

BIN_DIR="$HOME/.local/bin"
ICON_BASE="$HOME/.local/share/icons/hicolor"
DESKTOP_DIR="$HOME/.local/share/applications"

echo "==> Removing AppImage and launcher"
rm -f "$BIN_DIR/Rubric.AppImage" "$BIN_DIR/rubric"

echo "==> Removing desktop entry"
rm -f "$DESKTOP_DIR/io.github.calstfrancis.rubric.desktop"

echo "==> Removing icons"
rm -f "$ICON_BASE/scalable/apps/io.github.calstfrancis.rubric.svg"
rm -f "$ICON_BASE/symbolic/apps/io.github.calstfrancis.rubric-symbolic.svg"

echo "==> Removing MIME type"
rm -f "$HOME/.local/share/mime/packages/rubric.xml"
if command -v update-mime-database &>/dev/null; then
    update-mime-database "$HOME/.local/share/mime" 2>/dev/null || true
fi

echo "==> Updating caches"
if command -v gtk4-update-icon-cache &>/dev/null; then
    gtk4-update-icon-cache -f -t "$ICON_BASE" 2>/dev/null || true
elif command -v gtk-update-icon-cache &>/dev/null; then
    gtk-update-icon-cache -f -t "$ICON_BASE" 2>/dev/null || true
fi
if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
fi

echo ""
echo "Done. Rubric AppImage unregistered."
