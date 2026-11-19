"""Find a LOCAL DriveRepair live image for the USB creator.

Never download or substitute a generic Linux ISO. Only known DriveRepair
filenames are automatically chosen; an operator may explicitly browse for a
third-party hybrid ISO, which remains clearly marked as custom/unverified.
Image discovery is read-only. The flash CLI independently validates every image.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import Iterable

from .boot_validation import qualify_live_iso

ISO_GLOB = 'DriveRepair-Live*.iso'


def local_image_roots(*, executable: str | None = None,
                      repository: str | Path | None = None) -> list[Path]:
    """Search the sidecar, build-output and installed-image directories."""
    binary = Path(executable or sys.argv[0]).resolve().parent
    root = Path(repository).resolve() if repository is not None else Path(__file__).resolve().parents[2]
    if sys.platform == 'win32':
        data = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData' / 'Local')))
    else:
        data = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local' / 'share')))
    return [binary, binary / 'images', root / 'dist-live', root / 'dist',
            data / 'DriveRepair' / 'images']


def find_local_recovery_iso(*, preferred: str | None = None,
                            search_roots: Iterable[Path] | None = None) -> dict | None:
    """Choose the most recently built local DriveRepair ISO; never guess a URL.

    Explicitly selected paths have priority, then DriveRepair-named images only.
    Paths are independently revalidated by flash-usb before destructive I/O.
    """
    candidates: list[Path] = []
    if preferred and preferred.strip():
        candidates.append(Path(preferred))
    for directory in search_roots if search_roots is not None else local_image_roots():
        try:
            if directory.is_dir():
                candidates.extend(sorted(directory.glob(ISO_GLOB),
                                         key=lambda p: p.stat().st_mtime_ns if p.is_file() else 0,
                                         reverse=True))
        except OSError:
            continue
    seen: set[str] = set()
    for candidate in candidates:
        identifier = os.path.normcase(str(candidate.absolute()))
        if identifier in seen:
            continue
        seen.add(identifier)
        try:
            result = qualify_live_iso(candidate)
            result['selection'] = 'previously_selected' if preferred and candidate == Path(preferred) else 'local_driverepair_image'
            return result
        except (OSError, ValueError):
            continue
    return None
