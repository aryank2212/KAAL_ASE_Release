#!/bin/sh
# Build kaal-ase_<version>_all.deb from the repository. Usage: packaging/deb/build.sh <version> [outdir]
set -eu
VER="${1:?version}"; OUT="${2:-dist}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; STAGE="$(mktemp -d)"; trap 'rm -rf "$STAGE"' EXIT
install -d "$STAGE/DEBIAN" "$STAGE/opt/kaal-ase" "$STAGE/usr/bin" "$STAGE/usr/lib/systemd/system" "$STAGE/etc/kaal-ase" "$STAGE/usr/share/doc/kaal-ase"
cp -r "$ROOT/services/api/app" "$STAGE/opt/kaal-ase/app"
find "$STAGE/opt/kaal-ase/app" -name '__pycache__' -type d -prune -exec rm -rf {} +
install -m644 "$ROOT/services/api/requirements-core.txt" "$STAGE/opt/kaal-ase/requirements-core.txt"
sed 's#^T="${KAAL_TOOLS_DIR:-$HOME/.kaal/tools}"#T="${KAAL_TOOLS_DIR:-/var/lib/kaal-ase/tools}"#' "$ROOT/scripts/install_optional_tools.sh" > "$STAGE/opt/kaal-ase/install-optional-tools.sh"
chmod 755 "$STAGE/opt/kaal-ase/install-optional-tools.sh"
install -m755 "$ROOT/packaging/common/kaal-ase.sh" "$STAGE/usr/bin/kaal-ase"
install -m755 "$ROOT/scripts/kaal-model.py" "$STAGE/usr/bin/kaal-model"
install -m644 "$ROOT/packaging/common/kaal-ase.service" "$STAGE/usr/lib/systemd/system/kaal-ase.service"
install -m644 "$ROOT/packaging/common/kaal-ase.env" "$STAGE/etc/kaal-ase/kaal-ase.env"
install -m644 "$ROOT/CHANGELOG.md" "$STAGE/usr/share/doc/kaal-ase/changelog"
install -m644 "$ROOT/docs/osint-connectors.md" "$STAGE/usr/share/doc/kaal-ase/osint-connectors.md"
echo /etc/kaal-ase/kaal-ase.env > "$STAGE/DEBIAN/conffiles"
SIZE=$(du -sk "$STAGE/opt" "$STAGE/usr" "$STAGE/etc" | awk '{s+=$1} END {print s}')
cat > "$STAGE/DEBIAN/control" <<CTL
Package: kaal-ase
Version: $VER
Section: utils
Priority: optional
Architecture: all
Installed-Size: $SIZE
Depends: python3 (>= 3.10), python3-venv, python3-pip, ca-certificates, libimage-exiftool-perl
Recommends: systemd
Maintainer: RedClove <mail.redclove@gmail.com>
Homepage: https://github.com/aryank2212/KAAL_ASE_Release
Description: KAAL ASE OSINT API and console
 Guardrailed public-source OSINT connectors (domains, usernames, imagery,
 flights, ships, metadata) with an analyst review workflow, an audit trail and a
 web console. Uses a remote Ollama or LM Studio host for models. The Python
 environment is created on install and needs internet access once.
CTL
install -m755 "$ROOT/packaging/deb/postinst" "$STAGE/DEBIAN/postinst"
install -m755 "$ROOT/packaging/deb/prerm" "$STAGE/DEBIAN/prerm"
install -m755 "$ROOT/packaging/deb/postrm" "$STAGE/DEBIAN/postrm"
chmod 755 "$STAGE"
find "$STAGE/opt" "$STAGE/usr" "$STAGE/etc" -type d -exec chmod 755 {} +
find "$STAGE/opt/kaal-ase/app" -type f -exec chmod 644 {} +
mkdir -p "$OUT"
dpkg-deb --root-owner-group --build "$STAGE" "$OUT/kaal-ase_${VER}_all.deb" >/dev/null
echo "$OUT/kaal-ase_${VER}_all.deb"
