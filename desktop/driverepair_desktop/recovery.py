"""Image-first, restartable data rescue. Patient sources are opened read-only.

The output is a sparse regular file; its holes are NOT valid recovered data.
Only the journal can distinguish known-good *reads* from unreadable ranges.
No host raw-device writes are performed by this module.
"""
from __future__ import annotations

import errno
from contextlib import contextmanager
import json
import os
import stat
import time
from typing import Callable

from .compat import binary_open_flags, pwrite
from .scanner import Reader

_FATAL = {errno.ENODEV, errno.EBADF, errno.EPERM, errno.EACCES,
          errno.ENOENT, errno.EINVAL, errno.ENXIO}


def _safe_path(path: str) -> str:
    path = os.path.abspath(path)
    value = path.replace('\\', '/').lower()
    if value.startswith('/dev/') or value.startswith('//./') or value.startswith('//?/'):
        raise ValueError('Raw device destination forbidden: use a regular file image')
    if os.path.realpath(os.path.dirname(path)).replace('\\', '/').startswith('/dev/'):
        raise ValueError('Output directory is under /dev')
    return path


def _state_save(path: str, state: dict) -> None:
    """Persist through a same-directory temporary file and atomic rename."""
    temp = path + '.pending'
    flags = binary_open_flags(os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    if os.path.lexists(temp):
        # A stale pending journal is not authoritative after a crash.
        if not stat.S_ISREG(os.lstat(temp).st_mode):
            raise RuntimeError('Unexpected non-regular pending journal')
        os.unlink(temp)
    fd = os.open(temp, flags, 0o600)
    try:
        b = (json.dumps(state, sort_keys=True, indent=2) + '\n').encode('utf-8')
        _write_all(fd, b)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(temp, path)
    if os.name == 'posix':
        dirfd = os.open(os.path.dirname(path), os.O_RDONLY)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)


def _write_all(fd: int, data: bytes, offset: int | None = None) -> None:
    pos = 0
    while pos < len(data):
        if offset is not None:
            n = pwrite(fd, data[pos:], offset + pos)
        else:
            n = os.write(fd, data[pos:])
        if n <= 0:
            raise OSError(errno.EIO, 'Output write made no progress')
        pos += n


def _windows_sparse_resize(fd: int, size: int) -> None:
    """Mark sparse and set EOF without zero-filling the logical range.

    Python's ``os.ftruncate`` + ``os.fsync`` on NTFS can still advance Valid
    Data Length across a multi-terabyte image (minutes to hours) even after
    FSCTL_SET_SPARSE. That blocks ``--max-chunks`` lab bounds because the
    journal is not created until sizing finishes. Use SetFilePointerEx +
    SetEndOfFile and skip a full-file fsync after the initial sparse extend.
    """
    import ctypes
    import msvcrt
    from ctypes import wintypes

    FSCTL_SET_SPARSE = 0x000900C4
    handle = msvcrt.get_osfhandle(fd)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.DeviceIoControl.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
        ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
    ]
    kernel.DeviceIoControl.restype = wintypes.BOOL
    kernel.SetFilePointerEx.argtypes = [
        wintypes.HANDLE, ctypes.c_longlong, ctypes.POINTER(ctypes.c_longlong), wintypes.DWORD,
    ]
    kernel.SetFilePointerEx.restype = wintypes.BOOL
    kernel.SetEndOfFile.argtypes = [wintypes.HANDLE]
    kernel.SetEndOfFile.restype = wintypes.BOOL
    returned = wintypes.DWORD(0)
    if not kernel.DeviceIoControl(handle, FSCTL_SET_SPARSE, None, 0, None, 0,
                                  ctypes.byref(returned), None):
        raise OSError(ctypes.get_last_error(), 'FSCTL_SET_SPARSE failed for rescue image')
    new_pos = ctypes.c_longlong(0)
    if not kernel.SetFilePointerEx(handle, ctypes.c_longlong(size),
                                   ctypes.byref(new_pos), 0):
        raise OSError(ctypes.get_last_error(), 'SetFilePointerEx failed for rescue image')
    if not kernel.SetEndOfFile(handle):
        raise OSError(ctypes.get_last_error(), 'SetEndOfFile failed for rescue image')


def _open_output(path: str, size: int, resume: bool) -> int:
    nofollow = getattr(os, 'O_NOFOLLOW', 0)
    if resume:
        fd = os.open(path, binary_open_flags(os.O_WRONLY | nofollow))
    else:
        fd = os.open(path, binary_open_flags(os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow), 0o600)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise ValueError('Destination must be a regular file, not a device')
        if resume and st.st_size != size:
            raise RuntimeError('Destination image size changed; refusing resume')
        if not resume:
            if os.name == 'nt':
                _windows_sparse_resize(fd, size)
            else:
                os.ftruncate(fd, size)
                os.fsync(fd)
        return fd
    except BaseException:
        os.close(fd)
        raise


@contextmanager
def _rescue_writer_lock(output: str):
    """One recovery writer per image/map, released even after process death.

    Lock the stable sidecar file rather than a renamed journal. Its presence is
    not a stale-lock signal; only the *OS lock* determines ownership. Leave the
    tiny sidecar in place to avoid unlink/recreate inode races.
    """
    path = _safe_path(output) + '.rescue.lock'
    if os.path.lexists(path) and not stat.S_ISREG(os.lstat(path).st_mode):
        raise ValueError('Unexpected non-regular rescue lock file')
    flags = os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(path, binary_open_flags(flags), 0o600)
    acquired = False
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('Rescue lock target must be a regular file')
        if os.name == 'nt':
            import msvcrt
            if os.fstat(fd).st_size == 0:
                os.write(fd, b'\0')
                os.fsync(fd)
            os.lseek(fd, 0, os.SEEK_SET)
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RuntimeError('Recovery already running for this image/map') from exc
        else:
            import fcntl
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (OSError, BlockingIOError) as exc:
                raise RuntimeError('Recovery already running for this image/map') from exc
        acquired = True
        yield
    finally:
        if acquired:
            if os.name == 'nt':
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _merge_ranges(ranges: list[list[int]]) -> list[list[int]]:
    result: list[list[int]] = []
    for start, length in sorted(ranges):
        if length <= 0:
            continue
        if result and start <= result[-1][0] + result[-1][1]:
            end = max(result[-1][0] + result[-1][1], start + length)
            result[-1][1] = end - result[-1][0]
        else:
            result.append([start, length])
    return result



def _validate_state(state: dict) -> None:
    try:
        size, sector, cursor = (state[k] for k in ('size', 'sector', 'cursor'))
        if (not all(type(x) is int for x in (size, sector, cursor)) or
                size <= 0 or sector <= 0 or not 0 <= cursor <= size or
                cursor % sector):
            raise ValueError('Invalid recovery cursor')
        missing = state.get('missing_ranges', [])
        pending = state.get('retry_pending_ranges', [])
        if len(missing) + len(pending) > 250000:
            raise ValueError('Recovery map too large for safe operation')
        all_ranges = []
        for ranges in (missing, pending):
            for r in ranges:
                if (not isinstance(r, list) or len(r) != 2 or
                        any(type(n) is not int for n in r) or
                        r[0] < 0 or r[1] <= 0 or r[0] % sector or r[1] % sector or
                        r[0] + r[1] > cursor):
                    raise ValueError('Invalid missing-sector map range')
                all_ranges.append(r)
        ordered = sorted(all_ranges)
        if any(a[0] + a[1] > b[0] for a, b in zip(ordered, ordered[1:])):
            raise ValueError('Overlapping missing-sector map entries')
        if state.get('recovered_bytes') != cursor - sum(n for _, n in ordered):
            raise ValueError('Recovery map byte accounting inconsistent')
    except (KeyError, TypeError, OverflowError) as exc:
        raise ValueError('Malformed recovery map') from exc

def inspect_rescue_status(output: str) -> dict:
    """Read authoritative journal progress; image *length* is not progress.

    A sparse/preallocated image can report its final size before a single byte
    is rescued. This method is read-only and makes no integrity-certification
    claim about the bytes read from the patient disk.
    """
    output = _safe_path(output)
    journal = output + '.rescue.json'
    journal_stat = os.lstat(journal)
    if not stat.S_ISREG(journal_stat.st_mode):
        raise ValueError('Recovery map must be a regular file, not a link/device')
    with open(journal, encoding='utf-8') as handle:
        state = json.load(handle)
    _validate_state(state)
    if state.get('output') != output or state.get('schema') != 1:
        raise RuntimeError('Recovery map references a different image or unsupported schema')
    image_stat = os.stat(output, follow_symlinks=False)
    if not stat.S_ISREG(image_stat.st_mode) or image_stat.st_size != state['size']:
        raise RuntimeError('Image is missing, not a regular file, or has changed size')
    missing = sum(length for _, length in state['missing_ranges'])
    pending = sum(length for _, length in state.get('retry_pending_ranges', []))
    unprocessed = state['size'] - state['cursor']
    clean = (state['status'] == 'completed' and not missing and not pending
             and not unprocessed and state['recovered_bytes'] == state['size'])
    return {
        'schema': 1,
        'operation': 'rescue_status',
        'status': state.get('status', 'unknown'),
        'output': output,
        'logical_image_size_bytes': image_stat.st_size,
        'source_size_bytes': state['size'],
        'cursor_bytes': state['cursor'],
        'recovered_bytes': state['recovered_bytes'],
        'unprocessed_bytes': unprocessed,
        'unreadable_bytes': missing + pending,
        'missing_regions': len(state['missing_ranges']) + len(state.get('retry_pending_ranges', [])),
        'failed_read_attempts': state.get('failed_read_attempts', 0),
        'first_pass_complete': unprocessed == 0,
        'clean_rescue_complete': clean,
        'percent_processed': round(100 * state['cursor'] / state['size'], 3),
        'notes': ('Journal-backed progress, not image-file length. '
                  'Recovered bytes are OS-read bytes, not independently checksum-verified file contents.'),
    }


def _rescue_reader_locked(reader: Reader, *, size: int, sector: int, output: str,
                  source_token: str, chunk: int = 1024 * 1024,
                  max_failed_reads: int = 4096,
                  resume: bool = False, retry_missing: bool = False,
                  progress: Callable[[dict], None] | None = None,
                  max_chunks: int | None = None) -> dict:
    """Rescue readable data to image; no writes to reader/source.

    Recovered means OS returned all requested bytes, not that bytes match
    original file checksums. Persist output *before* recording its recovery.
    """
    if (size <= 0 or sector <= 0 or size % sector or chunk < sector or
            chunk % sector or chunk > 64 * 1024 * 1024 or
            not 1 <= max_failed_reads <= 100000 or not source_token):
        raise ValueError('Invalid size, alignment, chunk, source token or failure budget')
    output = _safe_path(output)
    journal = output + '.rescue.json'
    if os.path.realpath(journal) == os.path.realpath(output):
        raise ValueError('Output overlaps journal')
    if retry_missing and not resume:
        raise ValueError('Retry missing requires --resume')
    if resume:
        if not stat.S_ISREG(os.lstat(journal).st_mode):
            raise ValueError('Recovery journal is not a regular file')
        with open(journal, 'r', encoding='utf-8') as f:
            state = json.load(f)
        expected = dict(schema=1, size=size, sector=sector, chunk=chunk,
                        source_token=source_token, output=output)
        if any(state.get(k) != v for k, v in expected.items()):
            raise RuntimeError('Recovery source/destination identity or parameters changed')
        _validate_state(state)
        if retry_missing and state['cursor'] != size:
            raise RuntimeError('Complete the first pass before retrying missing regions')
    else:
        if os.path.lexists(journal) or os.path.lexists(output):
            raise FileExistsError('Recovery output/journal already exists; use --resume')
        state = dict(schema=1, size=size, sector=sector, chunk=chunk,
                     source_token=source_token, output=output,
                     cursor=0, recovered_bytes=0, missing_ranges=[],
                     failed_read_attempts=0, status='in_progress')
    fd = _open_output(output, size, resume)
    attempts = 0
    try:
        if not resume:
            _state_save(journal, state)
        if retry_missing:
            if 'retry_pending_ranges' not in state:
                state['retry_pending_ranges'] = state['missing_ranges']
                state['missing_ranges'] = []
                state['status'] = 'retry_in_progress'
                _state_save(journal, state)
            work = [tuple(item) for item in state['retry_pending_ranges']]
        else:
            if state.get('retry_pending_ranges'):
                raise RuntimeError('Interrupted retry pass; resume with --retry-missing')
            work = ((p, min(chunk, size - p)) for p in range(state['cursor'], size, chunk))
        processed = 0
        for offset, length in work:
            new_missing: list[list[int]] = []
            segments: list[tuple[int, bytes]] = []
            def recover(start: int, n: int) -> None:
                nonlocal attempts
                try:
                    got = reader.read_at(start, n)
                    if len(got) == n:
                        segments.append((start, got))
                        return
                    raise OSError(errno.EIO, f'short read: {len(got)} of {n}')
                except OSError as exc:
                    if exc.errno in _FATAL:
                        raise
                    attempts += 1
                    if attempts + state['failed_read_attempts'] > max_failed_reads:
                        raise RuntimeError('Read error limit exceeded; progress journal preserved')
                    # Fast first pass: intentionally no sleep/backoff — burning
                    # patient lifetime isolating every bad sector is worse than
                    # marking the chunk unknown and finishing readable regions.
                    # Targeted --retry-missing does binary-split isolation with a
                    # short backoff so USB bridges can settle between halves.
                    if not retry_missing or n <= sector:
                        new_missing.append([start, n])
                        return
                    half = ((n // sector) // 2) * sector
                    if half <= 0:
                        half = sector
                    time.sleep(0.005)
                    recover(start, half)
                    time.sleep(0.005)
                    recover(start + half, n - half)
            recover(offset, length)
            for start, data in segments:
                _write_all(fd, data, start)
            # fsync destination must complete before advancing durable map.
            os.fsync(fd)
            previous_missing = state['missing_ranges']
            if retry_missing:
                # Journal pending-range removal only after data is durable.
                if not state['retry_pending_ranges'] or state['retry_pending_ranges'][0] != [offset, length]:
                    raise RuntimeError('Retry journal changed unexpectedly')
                state['retry_pending_ranges'].pop(0)
                state['missing_ranges'] = _merge_ranges(previous_missing + new_missing)
            else:
                state['cursor'] = offset + length
                state['missing_ranges'] = _merge_ranges(previous_missing + new_missing)
            state['recovered_bytes'] += sum(len(data) for _, data in segments)
            state['failed_read_attempts'] += attempts
            attempts = 0
            state['status'] = 'in_progress'
            _validate_state(state)
            _state_save(journal, state)
            processed += 1
            if progress:
                progress(dict(state))
            if max_chunks is not None and processed >= max_chunks:
                break
        if retry_missing and state.get('retry_pending_ranges'):
            state['status'] = 'retry_in_progress'
        elif state['cursor'] == size:
            state['status'] = 'completed_with_missing_data' if state['missing_ranges'] else 'completed'
            state.pop('retry_pending_ranges', None)
        _validate_state(state)
        _state_save(journal, state)
        return dict(state)
    finally:
        os.close(fd)


def rescue_reader(reader: Reader, *, size: int, sector: int, output: str,
                  source_token: str, chunk: int = 1024 * 1024,
                  max_failed_reads: int = 4096,
                  resume: bool = False, retry_missing: bool = False,
                  progress: Callable[[dict], None] | None = None,
                  max_chunks: int | None = None) -> dict:
    """Rescue with exclusive OS lock to prevent concurrent output/map writers."""
    with _rescue_writer_lock(output):
        return _rescue_reader_locked(
            reader, size=size, sector=sector, output=output,
            source_token=source_token, chunk=chunk,
            max_failed_reads=max_failed_reads, resume=resume,
            retry_missing=retry_missing, progress=progress,
            max_chunks=max_chunks,
        )
