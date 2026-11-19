"""Cross-platform helpers for binary file I/O.

Windows defaults text-mode translation for os.open unless O_BINARY is set.
Recovery/carving/image paths must always use binary mode.
"""
from __future__ import annotations

import errno
import os
import time


def binary_open_flags(flags: int) -> int:
    """OR in O_BINARY on platforms that define it (Windows)."""
    return flags | getattr(os, "O_BINARY", 0) | getattr(os, "O_CLOEXEC", 0)


def pwrite(fd: int, data: bytes, offset: int) -> int:
    """Positional write with a portable fallback when os.pwrite is absent."""
    # Use callable(), not hasattr(): tests (and some hosts) may set os.pwrite
    # to None while leaving the attribute present.
    writer = getattr(os, "pwrite", None)
    if callable(writer):
        return writer(fd, data, offset)
    os.lseek(fd, offset, os.SEEK_SET)
    return os.write(fd, data)


def replace_with_retry(temp: str, path: str, *, attempts: int = 10) -> None:
    """``os.replace`` with brief retries for Windows share/AV locks (WinError 5/32)."""
    delay = 0.01
    last: OSError | None = None
    for _ in range(max(1, attempts)):
        try:
            os.replace(temp, path)
            return
        except OSError as exc:
            last = exc
            winerror = getattr(exc, "winerror", None)
            if winerror not in {5, 32} and exc.errno not in {
                errno.EACCES, errno.EPERM, errno.EBUSY, errno.EEXIST,
            }:
                raise
            time.sleep(delay)
            delay = min(delay * 1.6, 0.15)
    assert last is not None
    raise last
