#!/usr/bin/env bash
# capture-screenshots.sh — capture a fresh screenshot of Rubric against demo data
#
# Launches the app from source under a throwaway $HOME (so it never touches
# Cal's real config/data or opens any real liturgy), inside an isolated Xvfb
# display forced via GDK_BACKEND=x11 (GTK4 otherwise prefers the real Wayland
# session and would render on the actual desktop). Waits for the window to
# render, screenshots just the window, and overwrites screenshots/rubric-main.png.
#
# Requires: Xvfb, ImageMagick (magick), python3-gi/gtk4/libadwaita (same deps
# as running Rubric normally).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

DEMO_HOME=$(mktemp -d /tmp/rubric-demo-home.XXXXXX)
OUT="screenshots/rubric-main.png"
OUT_DARK="screenshots/rubric-main-dark.png"

cleanup() {
  [[ -n "${APP_PID:-}" ]] && kill "$APP_PID" 2>/dev/null || true
  [[ -n "${XVFB_PID:-}" ]] && kill "$XVFB_PID" 2>/dev/null || true
  rm -rf "$DEMO_HOME"
}
trap cleanup EXIT

APP_VERSION=$(grep '^APP_VERSION' rubric.py | head -1 | sed 's/APP_VERSION = "\(.*\)"/\1/')

echo "==> Seeding demo config in $DEMO_HOME"
mkdir -p "$DEMO_HOME/.config/rubric" "$DEMO_HOME/.local/share/rubric"
cp screenshots/demo.liturgy "$DEMO_HOME/demo.liturgy"
cat > "$DEMO_HOME/.config/rubric/config.json" <<JSON
{
  "recent_files": ["$DEMO_HOME/demo.liturgy"],
  "first_launch_completed": true,
  "quickstart_dismissed": true,
  "last_seen_version": "$APP_VERSION",
  "simple_mode": true
}
JSON

# Isolated Xvfb display, well clear of any real display number in use.
DISPLAY_NUM=220
while [[ -e "/tmp/.X${DISPLAY_NUM}-lock" ]]; do
  DISPLAY_NUM=$((DISPLAY_NUM + 1))
done

echo "==> Starting isolated Xvfb on :$DISPLAY_NUM"
Xvfb ":$DISPLAY_NUM" -screen 0 1280x800x24 &
XVFB_PID=$!
sleep 2

# Capture the app once per colour scheme. libadwaita normally resolves
# light/dark from the desktop's settings portal, which on this machine always
# reports light. ADW_DISABLE_PORTAL=1 makes libadwaita read the GSettings
# color-scheme key instead, and GSETTINGS_BACKEND=keyfile feeds it a value we
# write into the throwaway config — forcing either scheme deterministically.
# XDG_CONFIG_HOME is redirected into the throwaway home *only for the child* so
# that keyfile never lands in Cal's real ~/.config; Rubric resolves its own
# config via Path.home(), so this doesn't change where it reads config.json.
#
# GDK_BACKEND=x11 + unsetting WAYLAND_DISPLAY is required: GTK4 prefers Wayland
# by default, which would otherwise connect to the real desktop session and
# render there instead of into the isolated Xvfb display.
capture_scheme() {
  local scheme="$1" out="$2"
  mkdir -p "$DEMO_HOME/.config/glib-2.0/settings"
  cat > "$DEMO_HOME/.config/glib-2.0/settings/keyfile" <<KEYFILE
[org/gnome/desktop/interface]
color-scheme='$scheme'
KEYFILE

  echo "==> Launching Rubric ($scheme) against demo data inside the isolated display"
  env -u WAYLAND_DISPLAY GDK_BACKEND=x11 HOME="$DEMO_HOME" XDG_CONFIG_HOME="$DEMO_HOME/.config" \
    ADW_DISABLE_PORTAL=1 GSETTINGS_BACKEND=keyfile DISPLAY=":$DISPLAY_NUM" python3 rubric.py &
  APP_PID=$!

  echo "==> Waiting for window to render"
  sleep 10

  echo "==> Capturing and cropping to the app window -> $out"
  DISPLAY=":$DISPLAY_NUM" magick x:root -crop 1000x700+0+0 +repage "$out"

  kill "$APP_PID" 2>/dev/null || true
  wait "$APP_PID" 2>/dev/null || true
  APP_PID=
}

capture_scheme default     "$OUT"
capture_scheme prefer-dark "$OUT_DARK"

echo "Done. Wrote $OUT and $OUT_DARK"

# Publish web-ready copies into the personal website repo, one PNG + WebP per
# scheme, named as the site expects (<slug>.png/.webp + <slug>-dark.png/.webp).
# The capture crop already matches the site's image dimensions, so this is a
# straight convert+copy — no resize. Override the destination with
# WEBSITE_DIR=/path ./capture-screenshots.sh; if it doesn't exist the export is
# skipped with a note rather than failing. The website is a separate repo —
# commit and push it there yourself after reviewing the refreshed images.
SLUG="rubric"
WEBSITE_DIR="${WEBSITE_DIR:-$(dirname "$SCRIPT_DIR")/calstfrancis.github.io}"
if [[ -d "$WEBSITE_DIR" ]]; then
  echo "==> Publishing web images to $WEBSITE_DIR"
  cp "$OUT"      "$WEBSITE_DIR/$SLUG.png"
  cp "$OUT_DARK" "$WEBSITE_DIR/$SLUG-dark.png"
  magick "$OUT"      -quality 80 "$WEBSITE_DIR/$SLUG.webp"
  magick "$OUT_DARK" -quality 80 "$WEBSITE_DIR/$SLUG-dark.webp"
  echo "    wrote $SLUG.{png,webp} and $SLUG-dark.{png,webp}"
else
  echo "NOTE: website dir not found ($WEBSITE_DIR) — skipping web export."
fi
