"""Prepare an explicit, isolated Debian-WSL live ISO build from Windows.

Only builds ordinary files. Never chooses, formats, or writes a USB disk.
Requires an *existing* Debian WSL distribution; no implicit installation or
privilege escalation is performed by the preparation function. The caller
must obtain user consent before starting the root WSL build process.
"""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import zipfile
import re


class WSLPrerequisiteError(RuntimeError):
    """Distinguish a truly missing distro from a broken/stalled WSL service."""

    def __init__(self, message: str, *, missing_distro: bool = False):
        super().__init__(message)
        self.missing_distro = missing_distro


def _standard_wsl_mount(value: str) -> str | None:
    """Convert a local Windows drive path using WSL's documented default mount.

    Pure string conversion deliberately does NOT start the Debian VM from the
    Qt GUI thread. The actual asynchronous build verifies that the directory
    exists in WSL, and refuses custom automount roots with an actionable error.
    """
    match = re.fullmatch(r'([A-Za-z]):[\\/](.*)', value)
    if not match:
        return None
    segments = re.split(r'[\\/]+', match.group(2))
    if any(part in ('.', '..') for part in segments):
        raise ValueError('Unsafe Windows staging path')
    return '/mnt/' + match.group(1).lower() + '/' + '/'.join(part for part in segments if part)


def wsl_path(path: str | Path, *, runner=subprocess.run) -> str:
    """Convert a local build path without starting WSL merely for path math."""
    value = str(Path(path).resolve()) if sys.platform == 'win32' else str(path)
    if sys.platform == 'win32':
        mapped = _standard_wsl_mount(value)
        if not mapped:
            raise WSLPrerequisiteError('Only local drive-letter paths under the default '
                'WSL /mnt/<drive>/ mount are supported for ISO builds. UNC paths and '
                'custom WSL automount locations must be built in a Debian VM.')
        return mapped
    # Non-Windows compatibility for existing portable unit tests.
    done = runner(['wsl.exe', '-d', 'Debian', '--exec', 'wslpath', '-u', value],
                  capture_output=True, text=True, timeout=15, check=False)
    if done.returncode or not str(done.stdout).strip().startswith('/'):
        raise RuntimeError('Debian WSL could not resolve the Windows build path: '
                           + str(getattr(done, 'stderr', '') or '').strip()[:220])
    return str(done.stdout).strip()


def require_debian_wsl(*, runner=subprocess.run) -> None:
    if sys.platform != 'win32':
        raise RuntimeError('Debian WSL ISO building is only for Windows hosts')
    try:
        done = runner(['wsl.exe', '--list', '--quiet'], capture_output=True,
                      timeout=18, check=False)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise WSLPrerequisiteError('WSL inventory is unavailable or timed out. Debian may already '
            'be installed: check `wsl --list --verbose` and launch Debian once to finish first-run '
            'setup. Do not reinstall over an existing distro; no USB was written.') from exc
    # Windows WSL may output UTF-16LE (even without an explicit encoding flag).
    content = done.stdout if isinstance(done.stdout, bytes) else str(done.stdout).encode()
    decoded = content.decode('utf-16-le', 'ignore') if b'\x00' in content else content.decode('utf-8', 'ignore')
    if done.returncode:
        raise WSLPrerequisiteError('Cannot read WSL distribution inventory. Check `wsl --list '
            '--verbose` and initialize any existing Debian install before retrying. Do not '
            'reinstall blindly; no USB was written.')
    if 'Debian' not in [line.strip().strip('\x00') for line in decoded.splitlines()]:
        raise WSLPrerequisiteError('Debian WSL distribution not installed. Run '
            '`wsl --install -d Debian` in an elevated terminal if no Debian distro exists.',
            missing_distro=True)


# This static shell script copies the checkout to native WSL storage before
# running live-build. Building directly on /mnt/c may break Unix permissions,
# device nodes, symlinks and filesystem assumptions of debootstrap.
_WSL_BUILD_SCRIPT = r'''set -euo pipefail
SOURCE_DIR="$1"
OUTPUT_DIR="$2"
if [[ -z "$SOURCE_DIR" || -z "$OUTPUT_DIR" || "$OUTPUT_DIR" == / ]]; then
  echo 'Unsafe WSL build arguments' >&2; exit 2
fi
if [[ "$(id -u)" != 0 ]]; then echo 'Debian WSL root required' >&2; exit 2; fi
if [[ ! -d "$SOURCE_DIR/driverepair" || ! -d "$OUTPUT_DIR" ]]; then
  echo 'Staging/output not accessible in Debian WSL. Confirm /mnt/<drive>/ automount '
  echo 'or build in a Debian VM. No ISO and no USB were written.' >&2
  exit 3
fi
# The chroot must be built on the WSL distribution's native Linux filesystem.
# Some WSL installations mount /tmp on a filesystem where mknod is denied.
# Put both staging and the nested live-build TMPDIR under /var/tmp instead.
WORK="$(mktemp -d /var/tmp/driverepair-wsl-build.XXXXXXXX)"
if ! mknod -m 600 "$WORK/test-dev-null" c 1 3 2>/dev/null; then
  echo 'ERROR: WSL build filesystem cannot create Linux device nodes.' >&2
  echo 'Use Debian WSL2 with a native Linux /var/tmp filesystem or a Debian VM.' >&2
  echo 'No ISO was made and no USB was written.' >&2
  exit 6
fi
rm -f "$WORK/test-dev-null"
if ! command -v lb >/dev/null || ! command -v debootstrap >/dev/null || ! command -v xorriso >/dev/null || ! command -v python3 >/dev/null; then
  echo 'Installing Debian live-build prerequisites in isolated WSL distro (approved by operator).' >&2
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends live-build debootstrap xorriso python3
fi
trap 'echo "Build workspace retained for review: $WORK"' EXIT
cp -a -- "$SOURCE_DIR/driverepair" "$WORK/driverepair"
mkdir -- "$WORK/output"
TMPDIR="$WORK" bash "$WORK/driverepair/scripts/build_live_iso.sh" "$WORK/output"
shopt -s nullglob
artifacts=("$WORK/output"/*.iso "$WORK/output"/*.sha256)
if (( ${#artifacts[@]} < 2 )); then echo 'ISO or checksum missing' >&2; exit 4; fi
for entry in "${artifacts[@]}"; do
  name="${entry##*/}"
  if [[ -e "$OUTPUT_DIR/$name" ]]; then echo 'Refusing to overwrite existing ISO: '$name >&2; exit 5; fi
done
cp -- "${artifacts[@]}" "$OUTPUT_DIR/"
echo 'STRUCTURAL ISO VALIDATION PASSED. BIOS/UEFI actual boot remains unverified.'
'''


def prepare_wsl_build(repo: str | Path | None, staging: str | Path, destination: str | Path,
                      *, runner=subprocess.run) -> tuple[list[str], dict]:
    """Create kit and WSL invocation. Destination must already exist and be empty."""
    from .boot_media import export_build_kit
    stage = Path(staging).resolve()
    dest = Path(destination).resolve()
    if not dest.is_dir() or any(dest.iterdir()):
        raise ValueError('Select an empty existing destination folder (no files may be overwritten)')
    if stage == dest or dest.is_relative_to(stage):
        raise ValueError('Build staging directory and output destination must be separate')
    stage.mkdir(parents=True, exist_ok=True)
    kit = stage / 'driverepair-build.zip'
    if kit.exists():
        raise ValueError('Choose a fresh build staging directory')
    export_build_kit(repo, kit)
    with zipfile.ZipFile(kit) as z:
        for item in z.infolist():
            # Archive is authored by DriveRepair; still enforce containment.
            parts = Path(item.filename).parts
            if not parts or parts[0] != 'driverepair' or '..' in parts or item.filename.startswith('/'):
                raise ValueError('Unsafe build-kit member')
        z.extractall(stage)
    stage_wsl = wsl_path(stage, runner=runner)
    out_wsl = wsl_path(dest, runner=runner)
    args = ['wsl.exe', '-d', 'Debian', '-u', 'root', '--exec',
            'bash', '-c', _WSL_BUILD_SCRIPT, 'driverepair-wsl-build', stage_wsl, out_wsl]
    return args, {'staging': str(stage), 'destination': str(dest), 'debian_root': True,
                  'downloads': False, 'writes_physical_media': False}
