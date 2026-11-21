#!/usr/bin/env python3
"""Read-only, sanitized Windows USB bridge diagnostic for hardware QA.

This is NOT a physical repair eligibility certificate or write authorization.
Only standard smartctl identity/health queries are sent; full serial numbers,
raw stdout/stderr, device WWNs and path-identifying JSON are not saved.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess


def windows_alias(device: str) -> str:
    match = re.fullmatch(r'windows:PhysicalDrive([0-9]{1,3})', device, re.IGNORECASE)
    if not match:
        raise ValueError('Expected windows:PhysicalDriveN (N in 0..999); not a path or volume')
    return '/dev/pd' + str(int(match.group(1)))


def _attempt(executable: str, alias: str, mode: str | None, run) -> dict:
    args = [executable, '-j', '-i', '-H']
    if mode:
        args += ['-d', mode]
    args.append(alias)
    try:
        completed = run(args, timeout=20, capture_output=True, check=False)
    except subprocess.TimeoutExpired:
        return {'mode': mode or 'auto', 'status': 'TIMEOUT', 'exit_code': None}
    except OSError:
        return {'mode': mode or 'auto', 'status': 'TOOL_FAILED', 'exit_code': None}
    try:
        raw = completed.stdout
        if isinstance(raw, bytes):
            raw = raw[:1024*1024].decode('utf-8', errors='replace')
        payload = json.loads(str(raw)[:1024*1024])
    except (TypeError, ValueError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    smart = payload.get('smartctl') if isinstance(payload.get('smartctl'), dict) else {}
    health = payload.get('smart_status') if isinstance(payload.get('smart_status'), dict) else {}
    device = payload.get('device') if isinstance(payload.get('device'), dict) else {}
    exit_bits = smart.get('exit_status')
    if type(exit_bits) is not int:
        exit_bits = completed.returncode
    output = {'mode': mode or 'auto', 'status': 'UNVERIFIED',
              'exit_code': int(completed.returncode),
              'exit_bits': int(exit_bits) if type(exit_bits) is int else None,
              'protocol': str(device.get('protocol') or 'unknown')[:32],
              'smart_passed': health.get('passed') if type(health.get('passed')) is bool else None,
              'rotation_rate_rpm': payload.get('rotation_rate') if type(payload.get('rotation_rate')) is int else None}
    identified = bool(output['protocol'] != 'unknown' and
                      (output['smart_passed'] is not None or output['rotation_rate_rpm'] is not None))
    if exit_bits is not None and (exit_bits & 3) == 0 and identified:
        output['status'] = 'PROBED_READ_ONLY'
    return output


def probe(device: str, *, executable: str = 'smartctl', run=subprocess.run) -> dict:
    alias = windows_alias(device)
    first = _attempt(executable, alias, None, run)
    attempts = [first]
    if first['status'] not in {'PROBED_READ_ONLY', 'TIMEOUT'}:
        attempts.append(_attempt(executable, alias, 'sat', run))
    return {'status': 'PROBED_READ_ONLY' if any(x['status']=='PROBED_READ_ONLY' for x in attempts) else 'UNVERIFIED',
            'device_alias': alias, 'read_only': True, 'authorizes_writes': False,
            'attempts': attempts, 'notice': ('Unknown/USB-bridged SMART is not a physical write permit. '
                'Use a stable verified rotational HDD, separate journal, and exclusive lock for manual testing.')}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', required=True, help='windows:PhysicalDriveN (not a Windows volume)')
    parser.add_argument('--smartctl', default='smartctl')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        result = probe(args.device, executable=args.smartctl)
    except ValueError as exc:
        parser.error(str(exc))
    if args.output.exists():
        parser.error('Output exists; choose a new file to avoid overwriting QA evidence')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, indent=2)
        handle.write('\n')
    print(f"SMART QA {result['device_alias']}: {result['status']} (no writes, no serials saved)")
    return 0 if result['status'] == 'PROBED_READ_ONLY' else 1


if __name__ == '__main__':
    raise SystemExit(main())
