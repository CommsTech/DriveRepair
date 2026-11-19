"""Read-only structural qualification for a flashable DriveRepair Debian live ISO.

This is a *preflight*, NOT a proof that BIOS, UEFI or Secure Boot succeeds.
An ISO9660 volume and a valid MBR signature are insufficient: small placeholder
images can contain those markers and still boot to a blank screen.
"""
from __future__ import annotations

from pathlib import Path
import os
import re
import stat

SECTOR = 2048
MAX_DIRECTORY_BYTES = 2 * 1024 * 1024
MAX_DIRS = 1024


def _read_at(handle, offset: int, length: int, size: int) -> bytes:
    if offset < 0 or length < 0 or offset + length > size:
        raise ValueError('ISO references data beyond the end of the file')
    handle.seek(offset)
    result = handle.read(length)
    if len(result) != length:
        raise ValueError('Truncated ISO metadata')
    return result


def _iso_files(handle, pvd: bytes, size: int) -> set[str]:
    """Traverse bounded ISO9660 directory records (no extraction or execution)."""
    record = pvd[156:190]
    if len(record) < 34 or record[0] < 34:
        raise ValueError('ISO9660 root directory record missing')
    root = (int.from_bytes(record[2:6], 'little'), int.from_bytes(record[10:14], 'little'))
    pending = [('', *root, 0)]
    visited = set()
    names: set[str] = set()
    while pending:
        prefix, lba, length, depth = pending.pop()
        if (lba, length) in visited:
            continue
        visited.add((lba, length))
        if len(visited) > MAX_DIRS or depth > 7 or length > MAX_DIRECTORY_BYTES:
            raise ValueError('ISO directory tree exceeds safety limits')
        data = _read_at(handle, lba * SECTOR, length, size)
        pos = 0
        while pos < len(data):
            n = data[pos]
            if n == 0:
                pos = ((pos // SECTOR) + 1) * SECTOR
                continue
            if n < 34 or pos + n > len(data):
                raise ValueError('Malformed ISO9660 directory record')
            rec = data[pos:pos+n]
            pos += n
            name_len = rec[32]
            name = rec[33:33+name_len]
            if name in (b'\0', b'\1'):
                continue
            decoded = name.decode('ascii', errors='replace').split(';', 1)[0].rstrip('.').lower()
            if not decoded or decoded in ('.', '..'):
                continue
            location = prefix + '/' + decoded if prefix else decoded
            names.add(location)
            if rec[25] & 2:
                pending.append((location, int.from_bytes(rec[2:6], 'little'),
                                int.from_bytes(rec[10:14], 'little'), depth + 1))
    return names


def _eltorito_platforms(handle, size: int) -> tuple[bool, bool]:
    """Read the El Torito boot catalog; no reliance on external executables."""
    catalog_lba = None
    for sector in range(17, 64):
        desc = _read_at(handle, sector * SECTOR, SECTOR, size)
        if desc[1:6] != b'CD001':
            break
        if desc[0] == 0:
            marker = desc[7:39].decode('ascii', errors='ignore').rstrip('\x00 ')
            if marker.startswith('EL TORITO SPECIFICATION'):
                catalog_lba = int.from_bytes(desc[71:75], 'little')
                break
        if desc[0] == 255:
            break
    if not catalog_lba:
        return False, False
    catalog = _read_at(handle, catalog_lba * SECTOR, SECTOR, size)
    if catalog[0] != 1 or catalog[30:32] != b'\x55\xaa':
        return False, False
    # Validation entry checksum is zero modulo 65536 over its 16 words.
    if sum(int.from_bytes(catalog[x:x+2], 'little') for x in range(0, 32, 2)) % 65536:
        return False, False
    bios = False
    efi = False
    platform = catalog[1]
    for entry_at in range(32, len(catalog), 32):
        record = catalog[entry_at:entry_at+32]
        if record[0] in (0x90, 0x91):  # section header, platform ID
            platform = record[1]
        elif record[0] == 0x88 and int.from_bytes(record[8:12], 'little'):
            if platform == 0: bios = True
            if platform == 0xef: efi = True
    return bios, efi


def qualify_live_iso(source: str | os.PathLike[str]) -> dict:
    """Reject fake/placeholder ISOs before presenting or attempting physical flash.

    Checks ISO9660 filesystem, live kernel/initramfs/rootfs, BIOS+UEFI El Torito,
    and an actual hybrid partition record. Boot still MUST be tested in a VM.
    """
    path = Path(source)
    if path.suffix.lower() != '.iso' or path.is_symlink() or not path.is_file():
        raise ValueError('Select a regular .iso file (not a symlink or device)')
    with path.open('rb') as handle:
        st = os.fstat(handle.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_size < 128 * 1024:
            raise ValueError('Recovery ISO missing or too small')
        mbr = _read_at(handle, 0, 512, st.st_size)
        if mbr[510:512] != b'\x55\xaa' or not any(mbr[446+i*16+4] for i in range(4)):
            raise ValueError('Not a hybrid disk image: bootable MBR partition record missing')
        pvd = _read_at(handle, 16 * SECTOR, SECTOR, st.st_size)
        if pvd[:7] != b'\x01CD001\x01':
            raise ValueError('ISO9660 primary volume descriptor missing')
        files = _iso_files(handle, pvd, st.st_size)
        kernel = any(re.search(r'(^|/)(vmlinuz[^/]*|linux)$', p) for p in files)
        initrd = any(re.search(r'(^|/)(initrd[^/]*|initramfs[^/]*)$', p) for p in files)
        rootfs = any(p.endswith(('.squashfs', '.squashfs.img')) for p in files)
        bios, efi = _eltorito_platforms(handle, st.st_size)
    missing = []
    if not kernel: missing.append('Linux kernel (vmlinuz)')
    if not initrd: missing.append('initramfs')
    if not rootfs: missing.append('live compressed root filesystem (squashfs)')
    if not bios: missing.append('BIOS boot catalog entry')
    if not efi: missing.append('UEFI boot catalog entry')
    if missing:
        raise ValueError('Not a usable DriveRepair recovery ISO: missing ' + ', '.join(missing) +
                         '. Do not flash this placeholder; build and boot-test the Debian live image.')
    return {'path': str(path.resolve()), 'bytes': st.st_size,
            'status': 'LIVE_CONTENTS_AND_BOOT_ENTRIES_PRESENT_BOOT_UNTESTED',
            'bios_catalog': bios, 'uefi_catalog': efi,
            'live_components': ['kernel', 'initramfs', 'squashfs'],
            'note': 'Structural preflight only; real BIOS/UEFI boot remains unverified'}
