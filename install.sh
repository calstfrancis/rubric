#!/usr/bin/env bash
# Rubric — install script (git clone path)
# Installs the app, icons, and .desktop entry to ~/.local
# Run from the directory containing this script.
#
# For pipx/pip installs, use:  rubric-desktop-install

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$HOME/.local/share/rubric"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_BASE="$HOME/.local/share/icons/hicolor"

# ── Dependency check ──────────────────────────────────────────────────────────
echo "==> Checking dependencies…"
python3 -c "
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw
print('  GTK4 + libadwaita: OK')
" 2>/dev/null || {
    echo ""
    echo "  Dependencies not found. Install with:"
    echo "    sudo zypper install python3-gobject typelib-1_0-Adw-1 typelib-1_0-Gtk-4_0"
    echo "    (Ubuntu/Debian: sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1)"
    echo "    (Fedora:        sudo dnf install python3-gobject gtk4 libadwaita)"
    echo ""
    exit 1
}

# Typst (bundled binary preferred; system fallback)
if [ -f "$SCRIPT_DIR/rubric_package/bin/typst" ]; then
    echo "  typst: bundled (rubric_package/bin/typst)"
elif command -v typst &>/dev/null; then
    echo "  typst: $(command -v typst) — PDF compilation available"
else
    echo "  typst: not found — PDF compilation unavailable (HTML export works fine)"
fi

# ── App files ─────────────────────────────────────────────────────────────────
echo "==> Installing app to $APP_DIR"
mkdir -p "$APP_DIR"

cp "$SCRIPT_DIR/rubric.py"      "$APP_DIR/"
cp "$SCRIPT_DIR/rcl_data.py"    "$APP_DIR/"
cp "$SCRIPT_DIR/observances.py" "$APP_DIR/"

# rubric_package — models, utilities, data (required)
if [ -d "$SCRIPT_DIR/rubric_package" ]; then
    cp -r "$SCRIPT_DIR/rubric_package" "$APP_DIR/"
    find "$APP_DIR/rubric_package" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    find "$APP_DIR/rubric_package" -name "*.pyc" -delete 2>/dev/null || true
    # Restore typst binary executable bit if bundled
    if [ -f "$APP_DIR/rubric_package/bin/typst" ]; then
        chmod +x "$APP_DIR/rubric_package/bin/typst"
        echo "  typst binary: installed to $APP_DIR/rubric_package/bin/typst"
    fi
else
    echo "ERROR: rubric_package/ not found — cannot install." >&2
    exit 1
fi

# Optional root-level modules
for f in hymn_lookup.py hymn_suggestions.py bible_api.py snippets.py rubric_setup.py; do
    [ -f "$SCRIPT_DIR/$f" ] && cp "$SCRIPT_DIR/$f" "$APP_DIR/"
done

# Documentation
for f in HELP.md FAQ.md CHANGELOG.md; do
    [ -f "$SCRIPT_DIR/$f" ] && cp "$SCRIPT_DIR/$f" "$APP_DIR/"
done

# ── Launcher ──────────────────────────────────────────────────────────────────
echo "==> Creating launcher at $BIN_DIR/rubric"
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/rubric" << 'LAUNCHER'
#!/usr/bin/env bash
exec python3 "$HOME/.local/share/rubric/rubric.py" "$@"
LAUNCHER
chmod +x "$BIN_DIR/rubric"

# ── Icons ─────────────────────────────────────────────────────────────────────
echo "==> Installing icons"
mkdir -p "$ICON_BASE/scalable/apps" "$ICON_BASE/symbolic/apps"

# Copy from project root — both the short name (for .desktop Icon=) and the
# reverse-DNS name (for GNOME Shell panel matching by app-id)
cp "$SCRIPT_DIR/rubric.svg"          "$ICON_BASE/scalable/apps/rubric.svg"
cp "$SCRIPT_DIR/rubric.svg"          "$ICON_BASE/scalable/apps/io.github.calstfrancis.rubric.svg"
cp "$SCRIPT_DIR/rubric-symbolic.svg" "$ICON_BASE/symbolic/apps/rubric-symbolic.svg"
cp "$SCRIPT_DIR/rubric-symbolic.svg" "$ICON_BASE/symbolic/apps/io.github.calstfrancis.rubric-symbolic.svg"

if command -v gtk4-update-icon-cache &>/dev/null; then
    gtk4-update-icon-cache -f -t "$ICON_BASE"
elif command -v gtk-update-icon-cache &>/dev/null; then
    gtk-update-icon-cache -f -t "$ICON_BASE"
else
    echo "  (gtk-update-icon-cache not found — log out and back in if icon doesn't appear)"
fi

# ── Desktop entry ─────────────────────────────────────────────────────────────
echo "==> Writing .desktop entry"
mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_DIR/rubric.desktop" << EOF
[Desktop Entry]
Name=Rubric
GenericName=Worship Service Planner
Comment=Plan worship service orders with RCL readings
Exec=$BIN_DIR/rubric %f
Icon=io.github.calstfrancis.rubric
Terminal=false
Type=Application
Categories=Office;Education;
Keywords=worship;liturgy;service;church;UCC;lectionary;RCL;
StartupNotify=true
StartupWMClass=rubric
MimeType=application/x-liturgy;
EOF

# ── MIME type ─────────────────────────────────────────────────────────────────
mkdir -p "$HOME/.local/share/mime/packages"
cat > "$HOME/.local/share/mime/packages/rubric.xml" << 'MIMEEOF'
<?xml version="1.0" encoding="UTF-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
  <mime-type type="application/x-liturgy">
    <comment>Rubric service file</comment>
    <glob pattern="*.liturgy"/>
  </mime-type>
</mime-info>
MIMEEOF

command -v update-mime-database    &>/dev/null && update-mime-database    "$HOME/.local/share/mime" 2>/dev/null || true
command -v update-desktop-database &>/dev/null && update-desktop-database "$DESKTOP_DIR"            2>/dev/null || true

# ── PATH reminder ─────────────────────────────────────────────────────────────
if ! echo "$PATH" | grep -q "$BIN_DIR"; then
    echo ""
    echo "  NOTE: $BIN_DIR is not on your PATH."
    echo "  Add this to ~/.bashrc or ~/.zshrc:"
    echo '    export PATH="$HOME/.local/bin:$PATH"'
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "Done! Rubric is installed."
echo ""
echo "  Run from terminal:  rubric"
echo "  Or search:          Rubric   (in GNOME Shell, KRunner, etc.)"
echo ""
echo "  .liturgy files will open in the app automatically."
echo ""
echo "  To uninstall:  bash uninstall.sh"
