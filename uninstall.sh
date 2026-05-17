#!/usr/bin/env bash
# Rubric — uninstall script (removes the install.sh-based installation)

APP_DIR="$HOME/.local/share/rubric"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_BASE="$HOME/.local/share/icons/hicolor"

echo "==> Removing app files"
rm -rf "$APP_DIR"

echo "==> Removing launcher"
rm -f "$BIN_DIR/rubric"

echo "==> Removing desktop entry"
rm -f "$DESKTOP_DIR/rubric.desktop"

echo "==> Removing icons"
rm -f "$ICON_BASE/scalable/apps/rubric.svg"
rm -f "$ICON_BASE/scalable/apps/io.github.calstfrancis.rubric.svg"
rm -f "$ICON_BASE/symbolic/apps/rubric-symbolic.svg"
rm -f "$ICON_BASE/symbolic/apps/io.github.calstfrancis.rubric-symbolic.svg"

echo "==> Removing MIME type"
rm -f "$HOME/.local/share/mime/packages/rubric.xml"
if command -v update-mime-database &>/dev/null; then
    update-mime-database "$HOME/.local/share/mime" 2>/dev/null || true
fi

echo "==> Updating icon cache"
if command -v gtk4-update-icon-cache &>/dev/null; then
    gtk4-update-icon-cache -f -t "$ICON_BASE" 2>/dev/null || true
elif command -v gtk-update-icon-cache &>/dev/null; then
    gtk-update-icon-cache -f -t "$ICON_BASE" 2>/dev/null || true
fi

echo "==> Updating desktop database"
if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
fi

echo ""
echo "Done. Rubric has been uninstalled."
