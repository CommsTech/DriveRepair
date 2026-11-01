"""Cross-platform helpers for binary file I/O.

Windows defaults text-mode translation for os.open unless O_BINARY is set.
Recovery/carving/image paths must always use binary mode.
"""
from __future__ import annotations

import os


def binary_open_flags(flags: int) -> int:
    """OR in O_BINARY on platforms that define it (Windows)."""
    return flags | getattr(os, "O_BINARY", 0) | getattr(os, "O_CLOEXEC", 0)


def pwrite(fd: int, data: bytes, offset: int) -> int:
    """Positional write with a portable fallback when os.pwrite is absent."""
    if hasattr(os, "pwrite"):
        return os.pwrite(fd, data, offset)
    os.lseek(fd, offset, os.SEEK_SET)
    return os.write(fd, data)
