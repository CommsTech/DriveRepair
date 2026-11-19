"""Read-only drive health snapshot via an optional smartctl installation.

Unknown must remain unknown. SMART PASSED is not a clean bill of health.
Hardware information is summarized with serial numbers omitted.
When smartctl is missing on Windows, a coarse Get-Disk/Get-PhysicalDisk
HealthStatus fallback may be used — it is NOT a substitute for SMART attributes.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from typing import Callable

from .devices import Device


def health_snapshot(device: Device,
                    run: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> dict:
    from .dependencies import smartctl_path
    cmd = [smartctl_path() or 'smartctl', '--json', '--all', device.path]
    try:
        proc = run(cmd, capture_output=True, timeout=30, check=False)
    except FileNotFoundError as exc:
        raise RuntimeError('SMART support requires smartctl (smartmontools), not installed') from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError('SMART query timed out; device health unknown') from exc
    try:
        raw = json.loads(proc.stdout.decode('utf-8-sig'))
    except (ValueError, UnicodeError, AttributeError) as exc:
        raise RuntimeError('smartctl did not provide valid JSON; device health unknown') from exc
    if not isinstance(raw, dict):
        raise RuntimeError('Unexpected smartctl JSON structure')
    # CLI command, open/identity and SMART command failures invalidate the snapshot.
    # Other smartctl bits describe actual health concerns and must be retained.
    if proc.returncode & 0x07:
        raise RuntimeError(f'SMART probe failed (status bits {proc.returncode & 0x07}); health unknown')
    passed = (raw.get('smart_status') or {}).get('passed')
    status = ('failure_reported' if proc.returncode & (0x08 | 0x10) or passed is False
              else 'smart_passed_limited' if passed is True
              else 'unknown')
    nvme = raw.get('nvme_smart_health_information_log') or {}
    rpm = raw.get('rotation_rate')
    protocol = str((raw.get('device') or {}).get('protocol') or '').lower()
    reported_medium = ('ssd' if 'nvme' in protocol or type(rpm) is int and rpm == 0
                       else 'hdd' if type(rpm) is int and rpm > 0 else 'unknown')
    temp = raw.get('temperature') or {}
    ata = raw.get('ata_smart_attributes') or {}
    attrs = []
    for item in ata.get('table', []):
        if item.get('id') not in {5, 9, 187, 188, 197, 198, 199}:
            continue
        attrs.append({'id': item.get('id'), 'name': item.get('name'),
                      'raw_value': (item.get('raw') or {}).get('value')})
    result = {
        'status': status,
        'device': device.public(),
        'smartctl_exit_status': proc.returncode,
        'smart_status_passed': passed if isinstance(passed, bool) else None,
        'reported_medium': reported_medium,
        'rotation_rate_rpm': rpm if type(rpm) is int and rpm > 0 else None,
        'temperature_c': temp.get('current'),
        'nvme': {k: nvme.get(k) for k in ('percentage_used', 'media_errors',
                 'num_err_log_entries', 'unsafe_shutdowns', 'critical_warning', 'power_on_hours',
                 'available_spare', 'available_spare_threshold', 'temperature')
                 if k in nvme},
        'ata_selected_raw_attributes': attrs,
        'notes': 'Read-only SMART health snapshot. Raw ATA counters are manufacturer-specific. '
                 'SMART pass does not rule out media defects or future failure. '
                 'No self-test, erase, remap, refresh, or repair was started.',
    }
    from .reliability_score import assess
    result['condition_assessment'] = assess(result)
    return result


def windows_storage_health(device: Device,
                           run: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> dict | None:
    """Coarse Windows Storage health when smartctl is unavailable.

    Uses Get-Disk / Get-PhysicalDisk HealthStatus only. USB bridges often mask
    or fake serials; this is weaker than SMART attribute counters.
    """
    if not sys.platform.startswith('win'):
        return None
    match = re.search(r'PhysicalDrive(\d+)$', device.path.replace('/', '\\'), re.I)
    if not match:
        return None
    number = match.group(1)
    script = (
        f"$d = Get-Disk -Number {number} -ErrorAction Stop; "
        "$p = @(Get-PhysicalDisk -ErrorAction SilentlyContinue | "
        "Where-Object { $_.DeviceId -eq [string]$d.Number -or $_.FriendlyName -eq $d.FriendlyName })"
        "[0]; "
        "[pscustomobject]@{ disk_health=[string]$d.HealthStatus; "
        "disk_operational=[string]$d.OperationalStatus; "
        "physical_health=if($p){[string]$p.HealthStatus}else{'Unknown'}; "
        "physical_operational=if($p){[string]$p.OperationalStatus}else{'Unknown'} } "
        "| ConvertTo-Json -Compress"
    )
    try:
        proc = run(
            ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', script],
            capture_output=True, timeout=25, check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0 or not proc.stdout:
        return None
    try:
        raw = json.loads(proc.stdout.decode('utf-8-sig'))
    except (ValueError, UnicodeError):
        return None
    if not isinstance(raw, dict):
        return None
    labels = ' '.join(
        str(raw.get(k) or '') for k in (
            'disk_health', 'physical_health', 'disk_operational', 'physical_operational'
        )
    ).lower()
    if any(token in labels for token in ('unhealthy', 'fail', 'lost communication')):
        status = 'failure_reported'
    elif any(token in labels for token in ('warning', 'degraded', 'predictive')):
        status = 'windows_health_warning'
    elif 'healthy' in labels or labels.strip() in {'ok online', 'healthy ok', 'healthy online'}:
        status = 'windows_health_limited'
    elif 'healthy' in (str(raw.get('disk_health') or '') + str(raw.get('physical_health') or '')).lower():
        status = 'windows_health_limited'
    else:
        status = 'unknown'
    return {
        'status': status,
        'device': device.public(),
        'source': 'windows_storage_healthstatus',
        'windows_storage': raw,
        'smartctl_exit_status': None,
        'smart_status_passed': None,
        'reported_medium': 'unknown',
        'temperature_c': None,
        'nvme': {},
        'ata_selected_raw_attributes': [],
        'notes': (
            'Windows HealthStatus only (Get-Disk/Get-PhysicalDisk). '
            'Not SMART attributes; USB docks may mask real media counters. '
            'Install smartmontools (smartctl) for stronger evidence. '
            'No self-test, erase, remap, refresh, or repair was started.'
        ),
    }


def try_health_snapshot(device: Device,
                        run: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> dict | None:
    """Best-effort SMART probe, then Windows storage health fallback."""
    try:
        return health_snapshot(device, run=run)
    except RuntimeError:
        return windows_storage_health(device, run=run)


def media_from_smart(snapshot: dict | None) -> str:
    """Map a SMART snapshot to media OK|WARN|FAIL|UNKNOWN without inventing certainty."""
    if not snapshot:
        return "UNKNOWN"
    status = snapshot.get("status")
    if status == "failure_reported":
        return "FAIL"
    if status == "windows_health_warning":
        return "WARN"
    if status == "windows_health_limited":
        # Windows Storage HealthStatus lacks SMART attributes. Even when it says
        # 'Healthy', do not imply the medium passed an actual media-health check.
        return "UNKNOWN"
    attrs = {
        int(item.get("id")): item.get("raw_value")
        for item in (snapshot.get("ata_selected_raw_attributes") or [])
        if item.get("id") is not None
    }
    # 5 reallocated, 187 reported UNC, 197 current pending, 198 offline UNC.
    wear = [attrs.get(i) for i in (5, 187, 197, 198)]
    if any(isinstance(v, (int, float)) and v > 0 for v in wear):
        return "WARN"
    nvme = snapshot.get("nvme") or {}
    if isinstance(nvme.get("media_errors"), (int, float)) and nvme["media_errors"] > 0:
        return "WARN"
    if isinstance(nvme.get("critical_warning"), (int, float)) and nvme["critical_warning"]:
        return "FAIL"
    if status == "smart_passed_limited":
        return "OK"
    return "UNKNOWN"


def transport_from_smart(snapshot: dict | None) -> str:
    if not snapshot:
        return "UNKNOWN"
    attrs = {
        int(item.get("id")): item.get("raw_value")
        for item in (snapshot.get("ata_selected_raw_attributes") or [])
        if item.get("id") is not None
    }
    # 199 UltraDMA CRC — common USB/SATA transport noise signal.
    crc = attrs.get(199)
    if isinstance(crc, (int, float)) and crc > 0:
        return "WARN"
    return "UNKNOWN"


class ScanHealthTracker:
    """Sticky media/transport/mechanical state for live scan progress.

    Mechanical is a latency proxy. Media/transport prefer SMART when present and
    otherwise stay UNKNOWN unless reads prove a hard failure/disconnect.
    Metrics never authorize in-place refresh by themselves.
    """

    def __init__(self, *, bus: str = "", smart: dict | None = None) -> None:
        self.bus = (bus or "").lower()
        self.smart = smart
        self.media = media_from_smart(smart)
        self.transport = transport_from_smart(smart)
        self.mechanical = "UNKNOWN"
        self.read_errors = 0
        self.ok_reads = 0
        self.slow_events = 0
        self.disconnects = 0
        self.last_latency_ms: float | None = None
        self.last_median_ms: float | None = None

    def observe(self, *, latency_ms: float | None, median_ms: float | None,
                failed: bool, disconnect: bool = False) -> dict:
        if latency_ms is not None:
            self.last_latency_ms = float(latency_ms)
        if median_ms is not None:
            self.last_median_ms = float(median_ms)
        if disconnect:
            self.disconnects += 1
            self.transport = "FAIL"
            self.mechanical = "FAIL"
        elif failed:
            self.read_errors += 1
            if self.media in {"UNKNOWN", "OK"}:
                self.media = "WARN"
            # EIO alone does not identify a failing head or USB transport.
            # Those are separate diagnoses, not mathematical consequences of
            # one (or several) unreadable reads.
            if self.mechanical not in {"FAIL", "WATCH"}:
                self.mechanical = "WATCH"
        else:
            self.ok_reads += 1
            if self.transport == "UNKNOWN" and self.ok_reads >= 8:
                # Sustained successful reads: transport path is at least working now.
                self.transport = "OK"
            if (latency_ms is not None and median_ms is not None
                    and latency_ms >= max(float(median_ms) * 4, 50.0)):
                self.slow_events += 1
                if self.mechanical != "FAIL":
                    self.mechanical = "WATCH"
            elif latency_ms is not None and self.mechanical != "FAIL":
                if self.mechanical != "WATCH":
                    self.mechanical = "OK"
        return self.public()

    def public(self) -> dict:
        return {
            "media": self.media,
            "transport": self.transport,
            "mechanical": self.mechanical,
        }

    def repair_readiness(self) -> dict:
        blockers: list[str] = []
        if self.last_median_ms is None or self.ok_reads < 16:
            blockers.append("insufficient latency samples for mechanical baseline")
        if self.media == "UNKNOWN":
            blockers.append("media health unknown (SMART unavailable/inconclusive on this path)")
        if self.media == "FAIL":
            blockers.append("media FAIL — prefer image rescue; do not in-place refresh")
        if self.transport == "FAIL":
            blockers.append("transport FAIL — stabilize USB/dock before any write workflow")
        if self.mechanical == "FAIL":
            blockers.append("device disconnected/critical instability — abort write workflows")
        if self.mechanical == "WATCH":
            blockers.append("mechanical WATCH (slow regions) — refresh may stress media further")
        status = ("blocked" if blockers
                  else "metrics_present_not_a_repair_authorization")
        return {
            "status": status,
            "blockers": blockers,
            "samples_ok": self.ok_reads,
            "samples_failed": self.read_errors,
            "slow_events": self.slow_events,
            "smart_status": None if not self.smart else self.smart.get("status"),
            "notes": (
                "These metrics support triage only. In-place refresh still requires explicit "
                "destructive acknowledgements and never claims restored lifespan."
            ),
        }