"""Fail-closed power and RAM-journal preflight for experimental in-place refresh.

A RAM filesystem may survive an application crash, but NEVER a host restart or
storage/dock failure. This policy reduces, not removes, that risk.
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import time
from dataclasses import dataclass


class PowerGuardError(RuntimeError):
    """Power state was not proven safe for starting another patient write."""


# Loopback only — never a remote NUT host. Heuristics flag hostname forms;
# numeric loopback keeps local-only semantics without weakening the gate.
LOCAL_NUT_HOST = "127.0.0.1"


def _mountinfo_for(path: str) -> tuple[str, str, set[str]]:
    """Linux mountpoint, fs type, super options for the longest matching mount."""
    target = os.path.realpath(path)
    while not os.path.exists(target):
        parent = os.path.dirname(target)
        if parent == target:
            raise PowerGuardError("Cannot resolve journal path")
        target = parent
    best: tuple[int, str, str, set[str]] | None = None
    with open('/proc/self/mountinfo', encoding='utf-8') as stream:
        for line in stream:
            left, sep, right = line.strip().partition(' - ')
            if not sep:
                continue
            fields, extra = left.split(), right.split()
            if len(fields) < 5 or len(extra) < 3:
                continue
            mountpoint = fields[4].replace('\\040', ' ').replace('\\134', '\\')
            mountpoint = os.path.realpath(mountpoint)
            if target != mountpoint and not target.startswith(mountpoint.rstrip('/') + '/'):
                continue
            options = set(extra[2].split(',')) | set(fields[5].split(','))
            candidate = (len(mountpoint), mountpoint, extra[0], options)
            if best is None or candidate[0] > best[0]:
                best = candidate
    if best is None:
        raise PowerGuardError("Journal mount cannot be verified")
    return best[1], best[2], best[3]


def validate_ram_journal(path: str, *, required_bytes: int) -> dict:
    """Prove local RAM storage and no swap outlet, with enough free capacity."""
    if not sys.platform.startswith('linux'):
        raise PowerGuardError('RAM-backed patient journal currently requires Linux')
    parent = os.path.realpath(os.path.dirname(os.path.abspath(path)))
    mount, fs, options = _mountinfo_for(parent)
    if fs not in {'tmpfs', 'ramfs'}:
        raise PowerGuardError(f'RAM journal must be on tmpfs/ramfs, not {fs} ({mount})')
    with open('/proc/swaps', encoding='utf-8') as stream:
        swaps = [line for line in stream.read().splitlines()[1:] if line.strip()]
    if fs == 'tmpfs' and 'noswap' not in options and swaps:
        raise PowerGuardError(
            'RAM journal could page to disk. Use tmpfs noswap or disable all swap first.'
        )
    vfs = os.statvfs(parent)
    available = vfs.f_bavail * vfs.f_frsize
    if available < required_bytes:
        raise PowerGuardError(
            f'RAM journal lacks free space: {available} available, {required_bytes} required'
        )
    return {'mount': mount, 'filesystem': fs, 'available_bytes': available,
            'swap_policy': 'noswap' if 'noswap' in options else 'system_swap_disabled'}


def _nut_status(name: str) -> dict:
    # Explicitly refuse network NUT endpoints; state is read from the local loopback NUT.
    if not name or any(ch not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-' for ch in name):
        raise PowerGuardError('Use --power-source nut:UPSNAME (local NUT only)')
    try:
        proc = subprocess.run(
            ['upsc', f'{name}@{LOCAL_NUT_HOST}'],
            capture_output=True, text=True, check=True, timeout=3,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise PowerGuardError('Local NUT UPS is unavailable or unresponsive') from exc
    data = dict(line.split(': ', 1) for line in proc.stdout.splitlines() if ': ' in line)
    status = set(data.get('ups.status', '').split())
    if 'OL' not in status or status & {'OB', 'LB', 'FSD', 'OFF', 'RB'}:
        raise PowerGuardError('UPS is not safely on utility power (OL)')
    try:
        capacity = float(data['battery.charge'])
        runtime = float(data['battery.runtime'])
    except (KeyError, ValueError, TypeError) as exc:
        raise PowerGuardError('UPS must report charge and remaining runtime') from exc
    if capacity < 70 or runtime < 900:
        raise PowerGuardError('UPS charge <70% or predicted runtime <15 minutes')
    driver = data.get('driver.name', '').lower()
    # This shows a locally exposed USB driver, NOT that the USB dock is powered by UPS.
    if 'usb' not in driver and driver not in {'nutdrv_qx', 'blazer_usb', 'richcomm_usb'}:
        raise PowerGuardError('NUT driver is not proven local USB-connected UPS')
    return {'source': f'nut:{name}', 'power_status': 'OL', 'charge_percent': capacity,
            'runtime_seconds': runtime, 'driver': driver}


def _laptop_battery() -> dict:
    if not sys.platform.startswith('linux'):
        raise PowerGuardError('Laptop battery attestation is currently implemented only on Linux')
    root = pathlib.Path('/sys/class/power_supply')
    if not root.is_dir():
        raise PowerGuardError('No OS battery telemetry available')
    batteries = []
    for item in root.iterdir():
        try:
            if (item / 'type').read_text().strip().lower() != 'battery':
                continue
            status = (item / 'status').read_text().strip().lower()
            capacity = int((item / 'capacity').read_text().strip())
            batteries.append((status, capacity))
        except (OSError, ValueError):
            continue
    if not batteries or not all(s in {'full', 'charging', 'not charging'} and c >= 80
                               for s, c in batteries):
        raise PowerGuardError('Laptop battery missing, discharging or below 80%')
    mains = []
    for item in root.iterdir():
        try:
            kind = (item / 'type').read_text().strip().lower()
            if kind in {'mains', 'usb', 'usb_c'}:
                mains.append((item / 'online').read_text().strip() == '1')
        except OSError:
            continue
    if not mains or not any(mains):
        raise PowerGuardError('Laptop must also report external AC/USB-C power online')
    # A battery-backed laptop DOES NOT necessarily back a separately powered USB dock.
    return {'source': 'battery', 'charge_percent': min(c for _, c in batteries),
            'note': 'Only laptop power established; external dock power NOT verified'}


@dataclass
class VolatilePowerGuard:
    power_source: str
    journal: str
    chunk_bytes: int
    interval_seconds: float = 2.0
    _last_check: float = 0.0
    _last_result: dict | None = None

    def check(self, *, force: bool = False) -> dict:
        now = time.monotonic()
        if not force and self._last_result is not None and now - self._last_check < self.interval_seconds:
            return dict(self._last_result)
        ram = validate_ram_journal(self.journal, required_bytes=self.chunk_bytes * 3 + 4 * 1024 * 1024)
        if self.power_source.startswith('nut:'):
            power = _nut_status(self.power_source[4:])
        elif self.power_source == 'battery':
            power = _laptop_battery()
        else:
            raise PowerGuardError('Specify --power-source nut:UPSNAME or battery')
        self._last_result = {**ram, **power}
        self._last_check = now
        return dict(self._last_result)
