"""Preflight hints for the GUI; the independent CLI remains authoritative.

A USB bridge hiding the disk serial is not an authorization to weaken physical
write identity checks. Reject early before a lengthy scan falsely implies that
repair will follow.
"""
from __future__ import annotations


def ui_repair_readiness(device: dict | None, operation: str) -> tuple[bool, str]:
    if operation not in {'carequick', 'carefull', 'careresume'}:
        return True, ''
    if not device:
        return False, 'Select a physical drive before requesting a repair.'
    suffix = str(device.get('serial_suffix') or '').strip().lower()
    if not suffix or suffix in {'unavailable', 'unknown', 'none', 'null', 'n/a'}:
        return False, ('Repair unavailable: the USB bridge did not report a stable hardware serial. '
                       'Use Diagnose or Rescue Data; for physical repair, connect through a bridge '
                       'that exposes the hardware serial (or direct SATA), then Refresh. '
                       'Never invent a serial or override the identity gate.')
    if str(device.get('bus') or '').lower() not in {'usb', '1394', 'thunderbolt', 'firewire', 'sd', 'mmc'}:
        return False, 'Physical write target is not a positively identified external drive.'
    return True, 'Hardware serial reported. SMART, exclusive access and journal checks still apply.'
