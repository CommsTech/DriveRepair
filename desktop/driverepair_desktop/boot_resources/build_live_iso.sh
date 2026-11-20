#!/usr/bin/env bash
# Builds a Debian-based DriveRepair live ISO. NEVER writes to physical disks.
# Needs a Debian trixie build host with live-build, debootstrap and root privileges.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-$REPO/dist-live}"
if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo 'ERROR: Debian live-build requires root in an isolated build VM.' >&2
  exit 2
fi
for tool in lb debootstrap sha256sum; do
  if ! command -v "$tool" >/dev/null; then
    echo "ERROR: missing $tool; on Debian install live-build debootstrap" >&2
    exit 2
  fi
done
if [[ "$(uname -m)" != x86_64 ]]; then
  echo 'ERROR: initial live image recipe targets x86_64 only.' >&2
  exit 2
fi
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"
if [[ "$OUT" == "$REPO" || "$OUT" == '/' ]]; then
  echo 'ERROR: use a dedicated destination folder' >&2
  exit 2
fi
WORK="$(mktemp -d "${TMPDIR:-/tmp}/driverepair-live.XXXXXXXX")"
printf 'Build workspace: %s\n' "$WORK"
cd "$WORK"
# Per Debian live-build: GRUB PC plus GRUB EFI on a hybrid ISO (build MUST
# subsequently be boot-tested on both BIOS and UEFI before release).
lb config --mode debian --distribution trixie --architecture amd64 \
  --binary-images iso-hybrid --bootloaders 'grub-pc grub-efi' \
  --memtest memtest86+ \
  --archive-areas 'main non-free-firmware' --apt-recommends false
mkdir -p config/package-lists \
  config/includes.chroot/opt/driverepair/desktop \
  config/includes.chroot/usr/local/bin \
  config/includes.chroot/usr/share/applications \
  config/includes.chroot/etc/systemd/system
cat > config/package-lists/driverepair.list.chroot <<'EOF'
python3
python3-pyside6.qtcore
python3-pyside6.qtgui
python3-pyside6.qtwidgets
smartmontools
memtest86+
stress-ng
stressapptest
gddrescue
testdisk
e2fsprogs
ntfs-3g
exfatprogs
cryptsetup
openssh-client
nfs-common
cifs-utils
network-manager
xfce4
lightdm
xserver-xorg
sudo
EOF
cp -R "$REPO/desktop/driverepair_desktop" config/includes.chroot/opt/driverepair/desktop/
find config/includes.chroot/opt/driverepair/desktop -type d -name '__pycache__' -prune -exec rm -rf '{}' +
cat > config/includes.chroot/usr/local/bin/driverepair <<'EOF'
#!/bin/sh
cd /opt/driverepair/desktop || exit 1
exec python3 -m driverepair_desktop "$@"
EOF
chmod 0755 config/includes.chroot/usr/local/bin/driverepair
cat > config/includes.chroot/usr/local/bin/driverepair-gui <<'EOF'
#!/bin/sh
exec /usr/local/bin/driverepair gui "$@"
EOF
chmod 0755 config/includes.chroot/usr/local/bin/driverepair-gui
# Memory test is a dedicated boot-menu choice; Linux-session diagnostics
# are manual and bounded. These do not touch patient storage devices.
cp -- "$REPO/scripts/driverepair-hardware-diagnostics.sh" \
   config/includes.chroot/usr/local/bin/driverepair-hardware-diagnostics
chmod 0755 config/includes.chroot/usr/local/bin/driverepair-hardware-diagnostics
cat > config/includes.chroot/usr/share/applications/driverepair-hardware-diagnostics.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=Hardware Diagnostics (CPU / RAM)
Comment=Bounded CPU and memory checks; does not repair storage
Exec=/usr/local/bin/driverepair-hardware-diagnostics
Terminal=true
Icon=utilities-system-monitor
Categories=System;Utility;
EOF
cat > config/includes.chroot/usr/share/applications/driverepair.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=DriveRepair
Comment=Offline recovery workstation; source is read-only by default
Exec=/usr/local/bin/driverepair-gui
Terminal=false
Icon=drive-harddisk
Categories=System;Utility;
EOF
# A live rescue environment should NOT automatically mount patient media.
# Manual mounting of separate network/USB destinations remains possible.
ln -s /dev/null config/includes.chroot/etc/systemd/system/udisks2.service
lb build
ISO="$(find . -maxdepth 1 -type f -name '*.iso' -print -quit)"
if [[ -z "$ISO" || ! -s "$ISO" ]]; then
  echo 'ERROR: live-build did not produce an ISO' >&2
  exit 1
fi
TARGET="$OUT/DriveRepair-Live-amd64-UNVERIFIED.iso"
if [[ -e "$TARGET" ]]; then
  echo 'ERROR: output ISO already exists; use a fresh destination directory' >&2
  exit 1
fi
cp -- "$ISO" "$TARGET"
# Verify the live kernel, initramfs, squashfs and both firmware boot entries.
# Byte-valid images that do not contain these components must never be shipped.
"$REPO/scripts/check_live_iso.sh" "$TARGET"
( cd "$OUT" && sha256sum -- "$(basename "$TARGET")" > "$(basename "$TARGET").sha256" )
echo "Built: $TARGET"
echo 'MANDATORY: BIOS+UEFI VM smoke tests, physical boot tests and write-safety checks before distribution.'
echo "Build workspace retained for provenance: $WORK"
