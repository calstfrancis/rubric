#!/bin/bash
# Local Flatpak build and run for testing.
# Requires: flatpak-builder, org.gnome.Sdk//47, org.gnome.Platform//47
#
# First-time SDK setup:
#   flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
#   flatpak install flathub org.gnome.Sdk//47 org.gnome.Platform//47

set -e

MANIFEST="io.github.calstfrancis.rubric.yml"
BUILD_DIR=".flatpak-build"
APP_ID="io.github.calstfrancis.rubric"

echo "Building $APP_ID..."
flatpak-builder \
    --force-clean \
    --user \
    --install \
    "$BUILD_DIR" \
    "$MANIFEST"

echo ""
echo "Running $APP_ID..."
flatpak run --user "$APP_ID"
