"""Export a standalone Debian live-ISO *build kit* from source or zipapp.

Creates ordinary ZIP files only. No raw-device access or boot certification.
Bundled recipe files permit the GUI button to work in a standalone .pyz.
"""
from __future__ import annotations

from importlib import resources
from pathlib import Path
import os
import zipfile


_INSTRUCTIONS = '''EXPERIMENTAL / UNVERIFIED BOOT MEDIA

On Debian Linux OR Windows with a Debian WSL distribution:
  Windows: in DriveRepair select Create recovery USB → Build on this computer
  (requires WSL and Debian; WSL builder installs missing Debian build tools).

Manual clean Debian trixie x86-64 build VM:
  sudo apt install live-build debootstrap xorriso
  cd driverepair
  sudo bash scripts/build_live_iso.sh /path/to/fresh/output
  bash scripts/check_live_iso.sh /path/to/fresh/output/*.iso

The builder writes only ordinary files/ISO output. A separate flash-usb command
and Qt Flash bootable USB action can DESTRUCTIVELY write an ISO-hybrid to a
confirmed sacrificial USB disk, followed by full byte readback verification.
BIOS/UEFI VM and real hardware boot tests are MANDATORY before distribution.
Never target patient disks when building or subsequently flashing media.
Refer to docs/BOOT_RECOVERY.md for restrictions.
'''


def export_build_kit(repo: str | Path | None, output: str | Path) -> dict:
    root = Path(repo).resolve() if repo is not None else None
    target = Path(output).resolve()
    if target.exists() or target.is_symlink():
        raise FileExistsError('Select a new build-kit ZIP path; existing files are never overwritten')
    from_checkout = bool(root is not None and
        (root / 'scripts' / 'build_live_iso.sh').is_file() and
        (root / 'desktop' / 'driverepair_desktop' / '__main__.py').is_file())
    if from_checkout and target.is_relative_to(root):
        raise ValueError('Save the build kit OUTSIDE the source checkout')
    target.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, 'O_BINARY', 0)
    fd = os.open(target, flags, 0o600)
    os.close(fd)
    count = 0
    try:
        with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as z:
            if from_checkout:
                members = [root / 'scripts' / 'build_live_iso.sh',
                    root / 'scripts' / 'check_live_iso.sh',
                    root / 'docs' / 'BOOT_RECOVERY.md', root / 'README.md']
                members.extend(sorted((root / 'desktop' / 'driverepair_desktop').glob('*.py')))
                members.extend(sorted((root / 'desktop' / 'driverepair_desktop' / 'filesystems').glob('*.py')))
                for path in members:
                    z.write(path, 'driverepair/' + path.relative_to(root).as_posix())
                    count += 1
            else:
                # importlib.resources works with Python zipapps and installed
                # package trees; no temp extraction or network connection.
                pkg = resources.files('driverepair_desktop')
                for name in ('build_live_iso.sh','check_live_iso.sh','BOOT_RECOVERY.md','README.md'):
                    member = pkg.joinpath('boot_resources',name)
                    if not member.is_file():
                        raise ValueError('Boot-media assets missing from application package')
                    dst = ('scripts/' if name.endswith('.sh') else
                           'docs/' if name == 'BOOT_RECOVERY.md' else '') + name
                    z.writestr('driverepair/' + dst, member.read_bytes())
                    count += 1
                for folder in ('','filesystems'):
                    source = pkg if not folder else pkg.joinpath(folder)
                    for item in sorted(source.iterdir(), key=lambda t:t.name):
                        if item.is_file() and item.name.endswith('.py'):
                            loc = f'desktop/driverepair_desktop/{folder + "/" if folder else ""}{item.name}'
                            z.writestr('driverepair/' + loc, item.read_bytes())
                            count += 1
            z.writestr('driverepair/BOOT_KIT_INSTRUCTIONS.txt',_INSTRUCTIONS)
            count += 1
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return {'status':'UNVERIFIED_BUILD_KIT_CREATED','path':str(target),
            'files':count,'notes':'Builder kit only; NOT a verified bootable ISO.'}
