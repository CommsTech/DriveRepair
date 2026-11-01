#!/usr/bin/env bash
# Read-only structural validation. Does NOT prove that the kernel boots.
set -euo pipefail
ISO="${1:?Usage: check_live_iso.sh DriveRepair-Live-amd64-UNVERIFIED.iso}"
[[ -f "$ISO" ]] || { echo 'ISO not found' >&2; exit 2; }
command -v xorriso >/dev/null || { echo 'xorriso required for ISO catalog inspection' >&2; exit 2; }
CATALOG="$(xorriso -indev "$ISO" -report_el_torito plain 2>&1)"
printf '%s\n' "$CATALOG"
if ! grep -Eqi 'BIOS|x86.*PC' <<< "$CATALOG"; then
  echo 'BIOS El Torito entry not demonstrated' >&2; exit 1
fi
if ! grep -Eqi 'UEFI|EFI' <<< "$CATALOG"; then
  echo 'UEFI El Torito entry not demonstrated' >&2; exit 1
fi
echo 'Structural BIOS+UEFI catalog entries detected; booting still NOT_PROVEN.'
