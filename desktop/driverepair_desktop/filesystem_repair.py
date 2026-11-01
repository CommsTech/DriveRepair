"""Offline ext2/3/4 filesystem repair against a NEW COPY of a regular-file image.

No raw disk writing, no in-place source modification. Requires the established
`e2fsck` binary, which must be installed separately and is never downloaded.
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path


def _source_image(image: str) -> tuple[str, os.stat_result]:
    source = os.path.abspath(image)
    normalized = source.replace('\\', '/').lower()
    if normalized.startswith(('/dev/', '//./', '//?/', '/proc/', '/sys/')):
        raise ValueError('Only regular-file filesystem images are supported')
    st = os.lstat(source)
    if not stat.S_ISREG(st.st_mode):
        raise ValueError('Input must be a regular filesystem image, not a symlink/device')
    if st.st_size < 2048:
        raise ValueError('Image too small for ext filesystem')
    with open(source, 'rb') as f:
        f.seek(1080)
        signature = f.read(2)
    if signature != b'\x53\xef':
        raise ValueError('Not an ext2/3/4 filesystem volume image (whole partitioned disks are unsupported)')
    return source, st


def _e2fsck() -> str:
    tool = shutil.which('e2fsck')
    if not tool:
        raise RuntimeError('e2fsck is not installed; install e2fsprogs on a supported host')
    return tool


def _status(rc: int) -> str:
    if rc < 0 or rc & (4 | 8 | 16 | 32 | 128):
        return 'failed_or_uncorrected'
    if rc & 2:
        return 'corrected_reboot_flag'
    if rc & 1:
        return 'corrected'
    return 'clean'


def check_ext_image(image: str, *, timeout_seconds: int = 1800) -> dict:
    """Run e2fsck read-only. A dirty journal may make -n findings incomplete."""
    source, before = _source_image(image)
    if not 1 <= timeout_seconds <= 86400:
        raise ValueError('Invalid timeout')
    command = [_e2fsck(), '-f', '-n', source]
    try:
        result = subprocess.run(command, input=b'', stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=timeout_seconds, check=False)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError('Read-only filesystem check timed out') from exc
    after = os.lstat(source)
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise RuntimeError('Input filesystem image changed while being checked')
    return {'status': _status(result.returncode), 'mode': 'read_only_check',
            'exit_code': result.returncode, 'log': result.stdout.decode('utf-8', 'replace')[-12000:],
            'notes': 'e2fsck -n never writes repairs. A dirty journal can limit diagnostic accuracy.'}


def repair_ext_image(image: str, output: str, *, ack_repair: bool = False,
                     timeout_seconds: int = 3600) -> dict:
    """Clone image first, run e2fsck -y only on clone, preserve original.

    WARNING: filesystem repair may discard damaged file references even on a
    clone. Always retain the original image and the recovery map.
    """
    if not ack_repair:
        raise ValueError('Repair must be explicitly approved with --ack-repair')
    if not 1 <= timeout_seconds <= 86400:
        raise ValueError('Invalid timeout')
    source, before = _source_image(image)
    executable = _e2fsck()
    output = os.path.abspath(output)
    normalized = output.replace('\\', '/').lower()
    if normalized.startswith(('/dev/', '//./', '//?/', '/proc/', '/sys/')):
        raise ValueError('Repair target must be a new regular file, not a raw device')
    if os.path.realpath(source) == os.path.realpath(output):
        raise ValueError('Repair target cannot be the source image')
    report_path = output + '.repair.json'
    log_path = output + '.repair.log'
    if any(os.path.lexists(path) for path in (output, report_path, log_path)):
        raise FileExistsError('Destination image/report already exists; refusing overwrite')
    # Never follow an existing output symlink and never overwrite a prior result.
    nofollow = getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow | getattr(os, 'O_BINARY', 0), 0o600)
    try:
        with os.fdopen(fd, 'wb') as target, open(source, 'rb') as orig:
            shutil.copyfileobj(orig, target, length=1024 * 1024)
            target.flush()
            os.fsync(target.fileno())
        after = os.lstat(source)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
                after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
            raise RuntimeError('Source changed during cloning: clone is not a consistent snapshot')
        with open(log_path, 'xb') as log:
            try:
                result = subprocess.run([executable, '-f', '-y', output], stdin=subprocess.DEVNULL,
                                        stdout=log, stderr=subprocess.STDOUT,
                                        timeout=timeout_seconds, check=False)
                code = result.returncode
            except subprocess.TimeoutExpired:
                code = -1
                log.write(b'\nInterrupted: e2fsck timed out; repaired clone may be inconsistent.\n')
            log.flush()
            os.fsync(log.fileno())
        report = {
            'status': _status(code), 'mode': 'repair_copy_only',
            'exit_code': code, 'source': source, 'repaired_clone': output,
            'log_path': log_path, 'original_unchanged_by_tool': True,
            'notes': 'e2fsck was applied only to the newly cloned filesystem image. '
                     'A successful filesystem check does not validate file contents, '
                     'restore missing data or rejuvenate physical hardware.'
        }
        # New exclusive file, never overwrite another report.
        with open(report_path, 'x', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        return report
    except BaseException:
        # Never erase a partially modified clone: retain it for forensics.
        raise
