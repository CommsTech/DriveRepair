#!/usr/bin/env bash
# Structural preflight; cannot certify actual boot or secure-boot compatibility.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ISO="${1:?Usage: check_live_iso.sh /path/DriveRepair-Live-amd64.iso}"
[[ -f "$ISO" ]] || { echo 'ERROR: ISO not found' >&2; exit 2; }
PYTHONPATH="$REPO/desktop${PYTHONPATH:+:$PYTHONPATH}" python3 - "$ISO" <<'PY'
import sys, json
from driverepair_desktop.boot_validation import qualify_live_iso
try:
    print(json.dumps(qualify_live_iso(sys.argv[1]),indent=2))
except (OSError,ValueError) as exc:
    print('NOT A USABLE RECOVERY IMAGE:',str(exc),file=sys.stderr)
    sys.exit(2)
PY
if ! command -v xorriso >/dev/null 2>&1; then
  echo 'ERROR: xorriso is required to inspect the built boot menu' >&2
  exit 3
fi
{
  xorriso -indev "$ISO" -report_el_torito plain 2>&1
  # Inspect the ACTUAL ISO boot menu, not just the source template. Never
  # certify a boot product whose menu was discarded by the build system.
  MENU_DIR="$(mktemp -d)"
  trap 'rm -rf -- "$MENU_DIR"' EXIT
  if ! xorriso -osirrox on -indev "$ISO" -extract /boot/grub/grub.cfg "$MENU_DIR/grub.cfg" >/dev/null 2>&1; then
    echo 'ERROR: built ISO has no readable DriveRepair GRUB menu' >&2; exit 3
  fi
  grep -Fq 'DriveRepair - Start recovery workstation' "$MENU_DIR/grub.cfg" || {
    echo 'ERROR: built ISO boot menu is not customized for DriveRepair' >&2; exit 3;
  }
  grep -Fq 'DriveRepair - Compatibility graphics' "$MENU_DIR/grub.cfg" || {
    echo 'ERROR: built ISO has no compatibility graphics boot entry' >&2; exit 3;
  }
  if grep -Eq '@(KERNEL_LIVE|INITRD_LIVE|LB_BOOTAPPEND_LIVE)@' "$MENU_DIR/grub.cfg"; then
    echo 'ERROR: live-build did not resolve DriveRepair GRUB kernel placeholders' >&2; exit 3
  fi
}
echo 'ISO contents + extracted GRUB menu passed. UEFI boot-menu appearance still requires VM/hardware testing.'
echo 'REQUIRED: boot in a disposable BIOS VM and UEFI VM, then test on a sacrificial USB.'
echo 'Without these boots, the ISO remains UNVERIFIED.'
