#!/bin/bash
# build-rpm.sh — Build an RPM package for Rubric.
#
# Requires: rpmbuild (zypper install rpm-build)
# Output:   rubric-liturgy-<version>-1.noarch.rpm in the project directory
#
# Install the resulting RPM:
#   openSUSE:  sudo zypper install ./rubric-liturgy-*.noarch.rpm
#   Fedora:    sudo dnf install ./rubric-liturgy-*.noarch.rpm

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

VERSION="$(python3 -c "import re; print(re.search(r'APP_VERSION\s*=\s*[\"\'](.*?)[\"\']', open('rubric.py').read()).group(1))")"
NAME="rubric-liturgy"
RELEASE=1
RPMBUILD="$HOME/rpmbuild"

echo "Building Rubric $VERSION RPM..."

# ── Prepare rpmbuild tree ──────────────────────────────────────────────────────
mkdir -p "$RPMBUILD"/{BUILD,RPMS,SOURCES,SPECS,SRPMS}

# ── Assemble source tree ───────────────────────────────────────────────────────
TARNAME="${NAME}-${VERSION}"
WORK="$(mktemp -d)"
trap "rm -rf '$WORK'" EXIT
SRCDIR="$WORK/$TARNAME"
mkdir "$SRCDIR"

cp rubric.py rcl_data.py observances.py "$SRCDIR/"
for f in hymn_lookup.py hymn_suggestions.py bible_api.py snippets.py; do
    [ -f "$f" ] && cp "$f" "$SRCDIR/"
done
cp -r rubric_package "$SRCDIR/"
find "$SRCDIR/rubric_package" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find "$SRCDIR/rubric_package" -name "*.pyc" -delete 2>/dev/null || true

# Typst binary — bundled in rubric_package/bin/ or copied from system
if [ -f "rubric_package/bin/typst" ]; then
    mkdir -p "$SRCDIR/rubric_package/bin"
    install -m 755 rubric_package/bin/typst "$SRCDIR/rubric_package/bin/typst"
elif command -v typst &>/dev/null; then
    mkdir -p "$SRCDIR/bin"
    install -m 755 "$(command -v typst)" "$SRCDIR/bin/typst"
fi

cp io.github.calstfrancis.rubric.desktop "$SRCDIR/"
cp io.github.calstfrancis.rubric.metainfo.xml "$SRCDIR/"
cp rubric.svg rubric-symbolic.svg "$SRCDIR/"
for f in HELP.md FAQ.md CHANGELOG.md LICENSE; do
    [ -f "$f" ] && cp "$f" "$SRCDIR/"
done

tar czf "$RPMBUILD/SOURCES/${TARNAME}.tar.gz" -C "$WORK" "$TARNAME"

# ── Write spec file ────────────────────────────────────────────────────────────
DATESTAMP="$(date +'%a %b %d %Y')"
cat > "$RPMBUILD/SPECS/rubric-liturgy.spec" << EOF
Name:           rubric-liturgy
Version:        $VERSION
Release:        $RELEASE%{?dist}
Summary:        GNOME worship service planning tool for UCC ministry
License:        GPL-3.0-or-later
URL:            https://github.com/calstfrancis/rubric
BuildArch:      noarch
Source0:        %{name}-%{version}.tar.gz

# openSUSE
%if 0%{?suse_version}
Requires:       python3 >= 3.10
Requires:       python3-gobject
Requires:       typelib-1_0-Adw-1
Requires:       typelib-1_0-Gtk-4_0
Requires:       typelib-1_0-WebKit-6_0
Requires:       git
%endif

# Fedora / RHEL / CentOS Stream
%if 0%{?fedora} || 0%{?rhel}
Requires:       python3 >= 3.10
Requires:       python3-gobject3
Requires:       gtk4
Requires:       libadwaita
Requires:       webkit2gtk4.1
Requires:       git
%endif

%description
Rubric is a GNOME-native worship service planning tool for United Church of
Canada ministry. It integrates the Revised Common Lectionary, hymn lookup for
Voices United, More Voices, and Let Us Sing, Bible passage retrieval, and
export options for bulletin production.

Plan service orders, look up RCL readings, find hymns, fetch Bible passages,
and export polished bulletins — HTML or PDF (compiled with the bundled Typst
typesetter, no LaTeX required). Includes rich text and raw Typst editing per
element, live PDF preview, and optional GitHub sync.

%prep
%setup -q

%install
install -d %{buildroot}/usr/share/rubric
install -d %{buildroot}/usr/bin
install -d %{buildroot}/usr/share/applications
install -d %{buildroot}/usr/share/icons/hicolor/scalable/apps
install -d %{buildroot}/usr/share/icons/hicolor/symbolic/apps
install -d %{buildroot}/usr/share/metainfo
install -d %{buildroot}/usr/share/mime/packages

# Python source files
install -m 644 rubric.py rcl_data.py observances.py %{buildroot}/usr/share/rubric/
for f in hymn_lookup.py hymn_suggestions.py bible_api.py snippets.py; do
    [ -f "\$f" ] && install -m 644 "\$f" %{buildroot}/usr/share/rubric/ || true
done

# rubric_package
cp -r rubric_package %{buildroot}/usr/share/rubric/
find %{buildroot}/usr/share/rubric/rubric_package -name "*.pyc" -delete 2>/dev/null || true
find %{buildroot}/usr/share/rubric/rubric_package -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Typst binary (bundled)
if [ -f rubric_package/bin/typst ]; then
    install -d %{buildroot}/usr/share/rubric/rubric_package/bin
    install -m 755 rubric_package/bin/typst %{buildroot}/usr/share/rubric/rubric_package/bin/typst
elif [ -f bin/typst ]; then
    install -d %{buildroot}/usr/share/rubric/bin
    install -m 755 bin/typst %{buildroot}/usr/share/rubric/bin/typst
fi

# Documentation bundled in app dir
for f in HELP.md FAQ.md CHANGELOG.md; do
    [ -f "\$f" ] && install -m 644 "\$f" %{buildroot}/usr/share/rubric/ || true
done

# Launcher script
printf '#!/bin/bash\nexec python3 /usr/share/rubric/rubric.py "\$@"\n' > %{buildroot}/usr/bin/rubric
chmod 755 %{buildroot}/usr/bin/rubric

# Desktop integration
install -m 644 io.github.calstfrancis.rubric.desktop %{buildroot}/usr/share/applications/
install -m 644 rubric.svg %{buildroot}/usr/share/icons/hicolor/scalable/apps/rubric.svg
install -m 644 rubric.svg %{buildroot}/usr/share/icons/hicolor/scalable/apps/io.github.calstfrancis.rubric.svg
install -m 644 rubric-symbolic.svg %{buildroot}/usr/share/icons/hicolor/symbolic/apps/rubric-symbolic.svg
install -m 644 rubric-symbolic.svg %{buildroot}/usr/share/icons/hicolor/symbolic/apps/io.github.calstfrancis.rubric-symbolic.svg
install -m 644 io.github.calstfrancis.rubric.metainfo.xml %{buildroot}/usr/share/metainfo/

printf '<?xml version="1.0" encoding="UTF-8"?>\n<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">\n  <mime-type type="application/x-liturgy">\n    <comment>Rubric service file</comment>\n    <glob pattern="*.liturgy"/>\n  </mime-type>\n</mime-info>\n' > %{buildroot}/usr/share/mime/packages/rubric.xml

%files
%license LICENSE
/usr/share/rubric/
/usr/bin/rubric
/usr/share/applications/io.github.calstfrancis.rubric.desktop
/usr/share/icons/hicolor/scalable/apps/rubric.svg
/usr/share/icons/hicolor/scalable/apps/io.github.calstfrancis.rubric.svg
/usr/share/icons/hicolor/symbolic/apps/rubric-symbolic.svg
/usr/share/icons/hicolor/symbolic/apps/io.github.calstfrancis.rubric-symbolic.svg
/usr/share/metainfo/io.github.calstfrancis.rubric.metainfo.xml
/usr/share/mime/packages/rubric.xml

%post
%if 0%{?suse_version}
%icon_theme_cache_post
%mime_database_post
%desktop_database_post
%else
/usr/bin/update-mime-database /usr/share/mime 2>/dev/null || :
/usr/bin/update-desktop-database /usr/share/applications 2>/dev/null || :
/usr/bin/gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || :
%endif

%postun
%if 0%{?suse_version}
%icon_theme_cache_postun
%mime_database_postun
%desktop_database_postun
%else
/usr/bin/update-mime-database /usr/share/mime 2>/dev/null || :
/usr/bin/update-desktop-database /usr/share/applications 2>/dev/null || :
/usr/bin/gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || :
%endif

%changelog
* $DATESTAMP Cal St. Francis <calstfrancis@gmail.com> - $VERSION-$RELEASE
- Version $VERSION; see CHANGELOG.md for full history
EOF

# ── Build ──────────────────────────────────────────────────────────────────────
rpmbuild -bb "$RPMBUILD/SPECS/rubric-liturgy.spec"

# ── Copy output to project directory ──────────────────────────────────────────
find "$RPMBUILD/RPMS" -name "${NAME}-${VERSION}*.rpm" -exec cp {} "$SCRIPT_DIR/" \;

echo ""
RPMFILE=$(find "$RPMBUILD/RPMS" -name "${NAME}-${VERSION}*.rpm" | head -1 | xargs basename)
echo "Done: $RPMFILE  ($(du -sh "$SCRIPT_DIR/$RPMFILE" | cut -f1))"
echo ""
echo "Install:"
echo "  openSUSE:  sudo zypper install ./$RPMFILE"
echo "  Fedora:    sudo dnf install ./$RPMFILE"
