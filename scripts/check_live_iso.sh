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
if command -v xorriso >/dev/null 2>&1; then
  xorriso -indev "$ISO" -report_el_torito plain 2>&1
fi
echo 'Structure passed. REQUIRED: boot in a disposable BIOS VM and UEFI VM, then test on a sacrificial USB.'
echo 'Without these boots, the ISO remains UNVERIFIED.'
