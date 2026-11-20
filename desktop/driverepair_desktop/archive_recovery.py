"""Extract intact members from damaged ZIP files without touching originals.

Requires a readable central directory and recoverable individual compressed
streams. ZIP's CRC32 is corruption detection, not cryptographic authenticity.
"""
from __future__ import annotations

import hashlib
import os
import re
import stat
import zipfile
from typing import Any
from typing import Any
import zlib

from .compat import binary_open_flags


def salvage_zip(archive: str, output_dir: str, *, max_files: int = 1000,
                max_file_mib: int = 128, max_total_mib: int = 1024) -> dict:
    if not 1 <= max_files <= 100000 or not 1 <= max_file_mib <= 2048 or not 1 <= max_total_mib <= 8192:
        raise ValueError('Invalid salvage resource limits')
    source = os.path.abspath(archive)
    target = os.path.abspath(output_dir)
    srcnorm = source.replace('\\', '/').lower()
    if srcnorm.startswith('/dev/') or srcnorm.startswith('//./') or srcnorm.startswith('//?/'):
        raise ValueError('Archive must be a regular file')
    if not stat.S_ISREG(os.lstat(source).st_mode):
        raise ValueError('Archive must be a regular non-symlink file')
    if os.path.exists(target):
        raise FileExistsError('Output directory must not already exist')
    recovered: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    total = 0
    # Validate ZIP central directory BEFORE making the destination.
    with zipfile.ZipFile(source, 'r') as zf:
        entries = [info for info in zf.infolist() if not info.is_dir()]
        os.mkdir(target, 0o700)
        for index, info in enumerate(entries, 1):
            if len(recovered) >= max_files:
                skipped.append({'entry_index': index, 'reason': 'max_files_limit'})
                break
            if (info.file_size > max_file_mib * 1024 * 1024 or
                    info.file_size > max_total_mib * 1024 * 1024 - total):
                skipped.append({'entry_index': index, 'reason': 'decompressed_size_limit'})
                continue
            # Never use archive-controlled directories or links as destinations.
            name = os.path.basename(info.filename.replace('\\', '/'))
            name = re.sub(r'[^A-Za-z0-9._-]', '_', name).strip('._')[:70] or 'member'
            dest_name = f'{index:05d}_{name}'
            dest_path = os.path.join(target, dest_name)
            bytes_written = 0
            digest = hashlib.sha256()
            fd = os.open(dest_path, binary_open_flags(os.O_WRONLY | os.O_CREAT | os.O_EXCL), 0o600)
            valid = False
            try:
                with os.fdopen(fd, 'wb') as destination:
                    try:
                        with zf.open(info, 'r') as source_file:
                            while True:
                                block = source_file.read(1024 * 1024)
                                if not block:
                                    break
                                bytes_written += len(block)
                                if bytes_written > max_file_mib * 1024 * 1024 or bytes_written + total > max_total_mib * 1024 * 1024:
                                    raise ValueError('Output size limit exceeded during decompression')
                                digest.update(block)
                                destination.write(block)
                        destination.flush()
                        os.fsync(destination.fileno())
                        valid = True
                    except (zipfile.BadZipFile, RuntimeError, EOFError, zlib.error, ValueError) as exc:
                        skipped.append({'entry_index': index, 'reason': f'invalid_or_unrecoverable_member:{type(exc).__name__}'})
            finally:
                if not valid and os.path.exists(dest_path):
                    os.unlink(dest_path)
            if valid:
                total += bytes_written
                recovered.append({'filename': dest_name, 'size_bytes': bytes_written,
                                  'sha256': digest.hexdigest(), 'zip_crc_valid': True})
    return {'status': 'completed' if not skipped else 'partial_archive_recovery',
            'recovered_files': recovered, 'skipped': skipped,
            'recovered_count': len(recovered), 'total_bytes': total,
            'notes': 'Recovers members only when ZIP directory and each member stream/CRC survive. '
                     'Names are sanitized; original archive unchanged.'}
