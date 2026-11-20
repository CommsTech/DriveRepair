#!/usr/bin/env bash
# DriveRepair live environment: voluntary non-disk CPU/RAM checks.
# Memory test from the boot menu (Memtest86+) is more comprehensive.
set -euo pipefail
printf '%s\n' 'DriveRepair • CPU & memory diagnostics (LIVE ISO)' \
  'These are diagnostics, NOT repairs. Stop if the computer overheats.' \
  'No patient disks are read or modified by this script.' ''
printf '\nHardware summary\n'
command -v lscpu >/dev/null && lscpu | grep -E '^(Architecture|Model name|CPU\(s\)|Thread\(s\)|Core\(s\)):' || true
command -v free >/dev/null && free -h || true
printf '\n1) CPU verification (2 min, bounded workers)\n2) RAM stress (2 min, up to 20%% of RAM)\n3) Exit\n'
read -r -p 'Select an optional test [1/2/3]: ' answer || exit 0
case "$answer" in
  1)
    command -v stress-ng >/dev/null || { echo 'stress-ng missing'; exit 2; }
    read -r -p 'This will load the CPU. Type RUN to proceed: ' confirm
    [[ "$confirm" == RUN ]] || exit 0
    cores="$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 2)"
    [[ "$cores" =~ ^[0-9]+$ ]] || cores=2
    (( cores > 4 )) && cores=4
    (( cores < 1 )) && cores=1
    exec stress-ng --cpu "$cores" --verify --timeout 120s --metrics-brief
    ;;
  2)
    command -v stress-ng >/dev/null || { echo 'stress-ng missing'; exit 2; }
    read -r -p 'This tests some AVAILABLE memory, not all RAM. Type RUN to proceed: ' confirm
    [[ "$confirm" == RUN ]] || exit 0
    exec stress-ng --vm 1 --vm-bytes 20% --verify --timeout 120s --metrics-brief
    ;;
  3|'') exit 0 ;;
  *) echo 'Unknown selection; no test started'; exit 2 ;;
esac
