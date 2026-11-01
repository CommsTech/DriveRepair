"""Minimal stdlib console helpers for readable Windows/macOS/Linux CLI UI.

ASCII-first. Optional ANSI colors when the host console supports VT sequences.
Never raises into the recovery path.
"""
from __future__ import annotations

import os
import sys


# ANSI (no purple/glow stack — industrial cyan/amber/green/red).
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
WHITE = "\033[37m"
BG = "\033[40m"


_vt_ready: bool | None = None


def enable_windows_vt() -> bool:
    """Turn on virtual-terminal processing for the process consoles (Win10+)."""
    global _vt_ready
    if _vt_ready is not None:
        return _vt_ready
    if os.name != "nt":
        _vt_ready = True
        return True
    try:
        import ctypes
        kernel = ctypes.windll.kernel32  # type: ignore[attr-defined]
        # STD_OUTPUT_HANDLE=-11, STD_ERROR_HANDLE=-12
        enabled = False
        for handle_id in (-11, -12):
            handle = kernel.GetStdHandle(handle_id)
            mode = ctypes.c_uint32()
            if not kernel.GetConsoleMode(handle, ctypes.byref(mode)):
                continue
            # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            # ENABLE_PROCESSED_OUTPUT = 0x0001
            new_mode = mode.value | 0x0004 | 0x0001
            if kernel.SetConsoleMode(handle, new_mode):
                enabled = True
        _vt_ready = enabled
        return enabled
    except Exception:
        _vt_ready = False
        return False


def color_enabled(stream=None) -> bool:
    forced = os.environ.get("DRIVEREPAIR_COLOR", "").strip().lower()
    if forced in {"0", "false", "no", "off"}:
        return False
    if forced in {"1", "true", "yes", "on"}:
        return True
    stream = stream or sys.stderr
    if not enable_windows_vt():
        # Still allow ANSI on non-Windows TTYs.
        if os.name == "nt":
            return False
    try:
        return bool(getattr(stream, "isatty", lambda: False)())
    except Exception:
        return False


def paint(text: str, *codes: str, stream=None) -> str:
    if not codes or not color_enabled(stream):
        return text
    return "".join(codes) + text + RESET


def fmt_bytes(n: int) -> str:
    for unit, size in (("TiB", 1024**4), ("GiB", 1024**3), ("MiB", 1024**2), ("KiB", 1024)):
        if n >= size:
            return f"{n / size:.2f} {unit}"
    return f"{n} B"


def fmt_secs(seconds: float | None) -> str:
    if seconds is None:
        return "--"
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    return f"{minutes}m{int(seconds % 60):02d}s"


def progress_bar(done: int, total: int, width: int = 24) -> str:
    total = max(1, total)
    filled = min(width, int(width * done / total))
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def health_compact(media: str, transport: str, mechanical: str) -> str:
    """Hide UNKNOWN noise until something is known."""
    parts = []
    for label, value in (("media", media), ("xfer", transport), ("mech*", mechanical)):
        if value and value != "UNKNOWN":
            parts.append(f"{label}={value}")
    return " ".join(parts) if parts else "health=collecting"


def map_legend() -> str:
    return ". pending   o ok   S slow   ! escalate   X error"
