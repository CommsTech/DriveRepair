"""Read-only hash acquisition and minimal privacy-preserving evidence manifests.

A hash proves the byte sequence observed; it does NOT establish that a
software acquisition used a hardware write blocker or preserved every sector.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import stat
from datetime import datetime, timezone



def image_evidence_manifest(image: str, output: str, *, case_ref: str = '') -> dict:
    if case_ref and not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', case_ref):
        raise ValueError('Case reference must be 1-64 safe characters')
    original = image.replace('\\', '/').lower()
    if original.startswith(('/dev/', '//./', '//?/')):
        raise ValueError('Evidence hashing supports only regular image files')
    if not stat.S_ISREG(os.lstat(image).st_mode):
        raise ValueError('Evidence source must be a regular non-symlink file')
    if os.path.lexists(output):
        raise FileExistsError('Evidence manifest must be a new path')
    source = os.path.realpath(image)
    if os.path.realpath(output) == source:
        raise ValueError('Cannot overwrite source')
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0)
    fd = os.open(image, flags)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError('Image changed during open')
        digest = hashlib.sha256()
        total = 0
        while True:
            data = os.read(fd, 4 * 1024 * 1024)
            if not data:
                break
            digest.update(data)
            total += len(data)
        after = os.fstat(fd)
        if (before.st_size != total or after.st_size != before.st_size or
                after.st_mtime_ns != before.st_mtime_ns or after.st_ino != before.st_ino):
            raise RuntimeError('Source changed during hashing; manifest NOT generated')
    finally:
        os.close(fd)
    result = {
        'schema': 1, 'status': 'completed', 'operation': 'hash_image_evidence',
        'case_reference': case_ref or None,
        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'source_size_bytes': total, 'source_sha256': digest.hexdigest(),
        'host_os': platform.system(),
        'path_redacted': True,
        'chain_of_custody': 'NOT_CERTIFIED',
        'warnings': [
            'Hash represents bytes returned by the OS at acquisition time; cannot prove historic contents.',
            'This report alone does not prove hardware write blocking, unmodified source, or legal chain of custody.',
            'Unrecoverable source sectors require separate recovery-map evidence.',
        ],
    }
    flags = (os.O_WRONLY | os.O_CREAT | os.O_EXCL |
             getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0))
    out_fd = os.open(output, flags, 0o600)
    try:
        with os.fdopen(out_fd, 'w', encoding='utf-8') as out:
            json.dump(result, out, sort_keys=True, indent=2)
            out.write('\n')
            out.flush()
            os.fsync(out.fileno())
    except BaseException:
        try:
            os.unlink(output)
        except OSError:
            pass
        raise
    return result
