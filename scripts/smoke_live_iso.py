#!/usr/bin/env python3
"""Boot a DriveRepair live ISO in isolated BIOS/UEFI QEMU VMs, no hard disks.

PASS means the live guest reached XFCE and started the DriveRepair GUI process,
then emitted a QEMU-only marker over its serial port. It does NOT qualify USB
hardware, Secure Boot, or physical laptop compatibility. No patient storage is
attached to these machines. Never accept a device/block special file as an ISO.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import time

READY = 'DRIVEREPAIR_LIVE_READY:GUI_STARTED'


def make_qemu_command(firmware: str, iso: str, serial: str, *,
                      ovmf_code: str | None = None, ovmf_vars: str | None = None) -> list[str]:
    if firmware not in {'bios', 'uefi'}:
        raise ValueError('firmware must be bios or uefi')
    args = ['qemu-system-x86_64', '-nodefaults', '-machine', 'pc',
            '-m', '2048', '-smp', '2', '-vga', 'std', '-display', 'none',
            '-nic', 'none', '-no-reboot', '-boot', 'order=d',
            '-serial', 'file:' + str(serial), '-cdrom', str(iso)]
    if firmware == 'uefi':
        if not ovmf_code or not ovmf_vars:
            raise ValueError('UEFI requires OVMF code and separate temporary variables')
        args.extend(['-drive', 'if=pflash,format=raw,unit=0,readonly=on,file=' + str(ovmf_code),
                     '-drive', 'if=pflash,format=raw,unit=1,file=' + str(ovmf_vars)])
    return args


def _ovmf_files() -> tuple[Path, Path] | None:
    candidates = [('OVMF_CODE_4M.fd', 'OVMF_VARS_4M.fd'),
                  ('OVMF_CODE.fd', 'OVMF_VARS.fd')]
    for folder in ('/usr/share/OVMF', '/usr/share/ovmf/x64'):
        for code, variables in candidates:
            paths = Path(folder) / code, Path(folder) / variables
            if all(path.is_file() for path in paths):
                return paths
    return None


def _hash(path: Path) -> str:
    st = path.lstat()
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
        raise OSError(f'ISO path must be an ordinary file, not a special file: {path}')
    with path.open('rb') as handle:
        checksum = hashlib.sha256()
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            checksum.update(chunk)
        return checksum.hexdigest()


def _run_metadata() -> dict:
    """Capture CI identity when present; omit host home paths."""
    keys = ('GITHUB_RUN_ID', 'GITHUB_SHA', 'GITHUB_WORKFLOW', 'GITHUB_REF',
            'RUNNER_NAME', 'RUNNER_OS', 'RUNNER_ARCH')
    return {key.lower(): os.environ[key] for key in keys if os.environ.get(key)}


def boot_once(firmware: str, iso: Path, output: Path, timeout: int) -> dict:
    serial = output / f'{firmware}.serial.log'
    if not shutil.which('qemu-system-x86_64'):
        return {'status': 'NOT_PROVEN', 'reason': 'qemu-system-x86_64 unavailable'}
    with tempfile.TemporaryDirectory(prefix='driverepair-ovmf-') as temporary:
        kwargs = {}
        if firmware == 'uefi':
            files = _ovmf_files()
            if files is None:
                return {'status': 'NOT_PROVEN', 'reason': 'OVMF firmware files unavailable'}
            code, original_vars = files
            vars_copy = Path(temporary) / 'OVMF_VARS.fd'
            shutil.copyfile(original_vars, vars_copy)
            kwargs = {'ovmf_code': str(code), 'ovmf_vars': str(vars_copy)}
        cmd = make_qemu_command(firmware, str(iso), str(serial), **kwargs)
        start = time.monotonic()
        error_file = output / f'{firmware}.qemu.err'
        stderr_handle = error_file.open('wb')
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.DEVNULL, stderr=stderr_handle)
        except OSError as exc:
            stderr_handle.close()
            return {'status': 'NOT_PROVEN', 'reason': f'QEMU start failed: {exc}'}
        result = {'status': 'FAIL', 'reason': 'no guest GUI-ready marker received'}
        try:
            while time.monotonic() - start < timeout:
                if serial.is_file():
                    # Read a bounded tail only; never ingest unbounded guest logs.
                    with serial.open('rb') as handle:
                        handle.seek(max(0, serial.stat().st_size - 65536))
                        snapshot = handle.read().decode('utf-8', errors='replace')
                    if READY in snapshot:
                        result = {'status': 'PASS', 'reason': 'guest GUI process confirmed over serial'}
                        break
                    if 'DRIVEREPAIR_LIVE_FAIL:' in snapshot:
                        result = {'status': 'FAIL', 'reason': 'guest reported boot or GUI startup failure'}
                        break
                if proc.poll() is not None:
                    result = {'status': 'FAIL', 'reason': f'QEMU exited early (code {proc.returncode})'}
                    break
                time.sleep(1)
            else:
                result = {'status': 'FAIL', 'reason': f'boot timeout ({timeout}s)'}
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
            stderr_handle.close()
            if result['status'] != 'PASS' and error_file.is_file():
                with error_file.open('rb') as handle:
                    handle.seek(max(0, error_file.stat().st_size - 4096))
                    error_output = handle.read().decode('utf-8', errors='replace').strip()
                if error_output:
                    result['qemu_stderr_excerpt'] = error_output[-1500:]
        result['serial_log'] = str(serial)
        result['elapsed_seconds'] = round(time.monotonic() - start, 1)
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iso', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--timeout-seconds', type=int, default=240)
    parser.add_argument('--firmware', choices=['bios', 'uefi', 'both'], default='both')
    args = parser.parse_args()
    iso = args.iso.resolve()
    if not iso.is_file() or not stat.S_ISREG(iso.stat().st_mode) or not iso.name.lower().endswith('.iso'):
        parser.error('--iso must be an existing ordinary ISO file (not a raw/block device)')
    if args.timeout_seconds < 30:
        parser.error('boot time limit must be at least 30 seconds')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    modes = ('bios', 'uefi') if args.firmware == 'both' else (args.firmware,)
    result = {'iso': iso.name, 'iso_sha256': _hash(iso),
              'run_metadata': _run_metadata(),
              'tests': {mode: boot_once(mode, iso, output, args.timeout_seconds) for mode in modes}}
    (output / 'vm_boot_evidence.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    (output / 'run_metadata.json').write_text(json.dumps(result['run_metadata'], indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
    return 0 if all(entry['status'] == 'PASS' for entry in result['tests'].values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
