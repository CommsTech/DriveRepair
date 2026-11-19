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
import time
from typing import Callable

from .devices import Device

# A bounded, ordered list of smartmontools device types worth trying for USB
# bridges. Order matters: plain SAT first (cheapest, most common), then the
# vendor-specific passthroughs. Unknown types are simply skipped by smartctl.
USB_DEVICE_TYPES = ('sat', 'sat,12', 'sntjmicron', 'sntasmedia',
                    'sntrealtek', 'usbjmicron', 'usbjmicron,0')
MAX_EXTRA_DEVICE_PROBES = 5
EXTRA_PROBE_TIMEOUT_SECONDS = 5
SMART_LOG_TIMEOUT_SECONDS = 5
ATA_ATTRIBUTE_LIMIT = 64
SMART_LOG_ENTRY_LIMIT = 5
PROBE_BUDGET_SECONDS = 25.0


def _decode_json(proc) -> dict | None:
    try:
        parsed = json.loads(proc.stdout.decode('utf-8-sig'))
    except (ValueError, UnicodeError, AttributeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _usable_ata_view(raw: dict | None) -> bool:
    """A passthrough result must positively identify an ATA device."""
    if not isinstance(raw, dict):
        return False
    protocol = str((raw.get('device') or {}).get('protocol') or '').lower()
    return 'ata' in protocol


def _smart_logs(run: Callable[..., subprocess.CompletedProcess], executable: str,
                path: str, deadline: float) -> dict:
    """Read-only self-test and error log summary; never starts a test.

    These logs add no device wear: smartctl only reads the controller's
    existing records. Failures are reported as unavailable, never invented.
    """
    out = {'selftest': None, 'error_log': None, 'available': False}
    for label, flag in (('selftest', 'selftest'), ('error_log', 'error')):
        remaining = deadline - time.monotonic()
        if remaining <= 0.5:
            out[label] = {'available': False, 'reason': 'probe budget exhausted'}
            continue
        try:
            proc = run([executable, '--json', '-l', flag, path],
                       capture_output=True,
                       timeout=min(SMART_LOG_TIMEOUT_SECONDS, remaining),
                       check=False)
            raw = _decode_json(proc)
            if raw is None or proc.returncode & 0x07:
                out[label] = {'available': False, 'reason': 'log unavailable'}
                continue
            if label == 'selftest':
                table = raw.get('ata_smart_self_test_log') or {}
                standard = (table.get('standard') or {})
                entries = standard.get('table') or []
                out[label] = {
                    'available': True,
                    'count': standard.get('count'),
                    'last': [{k: item.get(k) for k in
                              ('type', 'status', 'remaining_percent',
                               'lifetime_hours', 'number')}
                             for item in entries[:SMART_LOG_ENTRY_LIMIT]],
                }
            else:
                table = raw.get('ata_smart_error_log') or {}
                summary = table.get('summary') or {}
                out[label] = {
                    'available': True,
                    'count': summary.get('count'),
                    'last': [{k: item.get(k) for k in
                              ('error_number', 'lifetime_hours', 'status')}
                             for item in (summary.get('table') or [])[:SMART_LOG_ENTRY_LIMIT]],
                }
            out['available'] = True
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            out[label] = {'available': False, 'reason': 'log query failed'}
    return out

def health_snapshot(device: Device,
                    run: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> dict:
    from .dependencies import smartctl_path
    # Execute only the path that was actually resolved and (on Windows) checked
    # against the staged manifest. Falling back to a bare 'smartctl' name would
    # let a planted executable supply the SMART evidence that feeds repair
    # authorization, and would re-resolve PATH after the check.
    executable = smartctl_path()
    if not executable:
        raise RuntimeError('SMART support requires smartctl (smartmontools), not installed')
    cmd = [executable, '--json', '--all', device.path]
    deadline = time.monotonic() + PROBE_BUDGET_SECONDS
    try:
        proc = run(cmd, capture_output=True, timeout=12, check=False)
    except FileNotFoundError as exc:
        raise RuntimeError('SMART support requires smartctl (smartmontools), not installed') from exc
    except subprocess.TimeoutExpired as exc:
        # NEVER retry a hung USB device with another passthrough command.
        raise RuntimeError('SMART query timed out; device health unknown') from exc
    # A USB bridge can return an error or non-JSON text on auto probing even
    # when ATA SAT pass-through works. Parse opportunistically, then try ONE
    # bounded, read-only SAT query if it is safe to do so.
    try:
        parsed = json.loads(proc.stdout.decode('utf-8-sig'))
        parsed_ok = isinstance(parsed, dict)
        raw = parsed if parsed_ok else {}
    except (ValueError, UnicodeError, AttributeError):
        parsed_ok = False
        raw = {}
    source = 'smartctl_auto'
    device_protocol = str((raw.get('device') or {}).get('protocol') or '').lower()
    failure_reported = bool(proc.returncode & (0x08 | 0x10)) or (raw.get('smart_status') or {}).get('passed') is False
    # Do not conceal an existing SMART media failure with a second, potentially
    # optimistic response. Do not send ATA commands to positively NVMe devices.
    needs_rotation = type(raw.get('rotation_rate')) is not int
    if (device.bus.lower() in {'usb', 'thunderbolt', 'firewire'}
            and needs_rotation and not failure_reported
            and 'nvme' not in device_protocol
            and not raw.get('nvme_smart_health_information_log')
            # Do not replace a detailed ATA SMART table, including pending
            # or reallocated sector warnings, with a second less complete view.
            and not (raw.get('ata_smart_attributes') or {}).get('table')):
        # Try a small, ordered set of bridge device types. Each attempt is
        # bounded and the total probe budget is capped, so a sick bridge sees a
        # few short commands at most - never a retry storm.
        extra_probes = 0
        for device_type in USB_DEVICE_TYPES:
            if extra_probes >= MAX_EXTRA_DEVICE_PROBES:
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0.5:
                break
            extra_probes += 1
            try:
                sat = run([cmd[0], '--json', '--all', '-d', device_type, device.path],
                          capture_output=True,
                          timeout=min(EXTRA_PROBE_TIMEOUT_SECONDS, remaining),
                          check=False)
                sat_raw = _decode_json(sat)
                if (sat_raw is not None and not (sat.returncode & 0x07)
                        and type(sat_raw.get('rotation_rate')) is int
                        and _usable_ata_view(sat_raw)):
                    # The result must positively identify an ATA device and
                    # report physical rotation. A mere model name is not evidence.
                    proc, raw = sat, sat_raw
                    source = ('smartctl_sat_passthrough' if device_type == 'sat'
                              else f'smartctl_{device_type}_passthrough')
                    break
            except (FileNotFoundError, subprocess.TimeoutExpired, ValueError,
                    UnicodeError, AttributeError, OSError):
                continue
    if not parsed_ok and source != 'smartctl_sat_passthrough':
        raise RuntimeError('SMART query returned invalid JSON; '
                           'USB SAT passthrough was unavailable or inconclusive')
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
    # NVMe behind USB can have a USB bus yet report an NVMe health log.
    nvme_identified = 'nvme' in protocol or bool(nvme)
    reported_medium = ('ssd' if nvme_identified or type(rpm) is int and rpm == 0
                       else 'hdd' if type(rpm) is int and rpm > 0 else 'unknown')
    temp = raw.get('temperature') or {}
    ata = raw.get('ata_smart_attributes') or {}
    # Keep the whole read-only attribute table (bounded), including the
    # normalised VALUE/WORST/THRESH that vendor tools show, plus the raw
    # counter. The 7-counter subset is retained for existing scoring.
    ata_attributes = []
    for item in (ata.get('table') or [])[:ATA_ATTRIBUTE_LIMIT]:
        if type(item.get('id')) is not int:
            continue
        ata_attributes.append({
            'id': item.get('id'),
            'name': item.get('name'),
            'value': item.get('value'),
            'worst': item.get('worst'),
            'thresh': item.get('thresh'),
            'when_failed': item.get('when_failed'),
            'failing_now': item.get('when_failed') not in (None, '-', ''),
            'raw_value': (item.get('raw') or {}).get('value'),
            'raw_string': (item.get('raw') or {}).get('string'),
        })
    selected_ids = {5, 9, 187, 188, 197, 198, 199}
    attrs = [{'id': entry['id'], 'name': entry['name'],
              'raw_value': entry['raw_value']}
             for entry in ata_attributes if entry['id'] in selected_ids]
    # Only read the logs when the primary probe was conclusive and healthy, and
    # the device speaks ATA. A device already reporting failure (or an NVMe
    # device, whose health log already carries the error counters) must not be
    # sent further commands: that is how a marginal bridge turns into a stall.
    if not parsed_ok:
        smart_logs = {'available': False, 'reason': 'primary probe returned no JSON'}
    elif failure_reported:
        smart_logs = {'available': False,
                      'reason': 'skipped: controller already reports failure'}
    elif nvme_identified:
        smart_logs = {'available': False,
                      'reason': 'skipped: NVMe health log already reports error counters'}
    else:
        smart_logs = _smart_logs(run, cmd[0], device.path, deadline)
    result = {
        'status': status,
        'source': source,
        'device': device.public(),
        'smartctl_exit_status': proc.returncode,
        'smart_status_passed': passed if isinstance(passed, bool) else None,
        'reported_medium': reported_medium,
        'device_protocol': 'nvme' if nvme_identified else protocol or 'unknown',
        'rotation_rate_rpm': rpm if type(rpm) is int and rpm > 0 else None,
        'temperature_c': temp.get('current'),
        'nvme': {k: nvme.get(k) for k in ('percentage_used', 'media_errors',
                 'num_err_log_entries', 'unsafe_shutdowns', 'critical_warning', 'power_on_hours',
                 'available_spare', 'available_spare_threshold', 'temperature')
                 if k in nvme},
        'ata_selected_raw_attributes': attrs,
        'ata_attributes': ata_attributes,
        'ata_attribute_count': len(ata_attributes),
        'smart_logs': smart_logs,
        'notes': 'Read-only SMART health snapshot. Raw ATA counters are manufacturer-specific. '
                 'SMART pass does not rule out media defects or future failure. '
                 'Self-test and error logs are read, never started. '
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