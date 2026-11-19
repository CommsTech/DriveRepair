"""DriveRepair capacity-authenticity spot checks.

Distinct from read-only surface scanning and from a full-capacity test. Each
selected location is saved to a durable separate-device rolling journal before
any temporary write, verified, then restored and independently re-read.

WARNING: a dishonest controller can alias writes into an *unselected* region;
restoring only selected regions cannot undo that unknown damage. A sudden power
loss or uncooperative USB bridge can also defeat restoration. Physical use is
therefore explicitly opt-in, engineering/guarded only, after a full backup, and
never an automatic action on recovery patients.
"""
from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path
import secrets
import stat
import statistics
import threading
import time
from typing import Callable

from .compat import binary_open_flags, pwrite
from .media_refresh import JournalStore

SCHEMA = 1
TEST_BYTES = 4096
MAX_SAMPLES = 576


def planned_locations(size: int, sector: int, *, samples: int = 144,
                      skip_edges: int = 16 * 1024 * 1024) -> list[int]:
    """Distribute unique, aligned spots across declared space; avoid metadata edges.

    Guarding the first/last 16 MiB reduces, but does not eliminate, the risk of
    corrupting filesystem metadata or existing files. Never claim it does.
    """
    if (type(size) is not int or type(sector) is not int or sector not in
            (512, 1024, 2048, 4096) or type(samples) is not int or
            not 2 <= samples <= MAX_SAMPLES or size <= 0 or size % sector):
        raise ValueError('Invalid capacity, logical sector or sample count')
    block = max(TEST_BYTES, sector)
    start = ((skip_edges + sector - 1) // sector) * sector
    end = ((size - skip_edges - block) // sector) * sector
    if end < start or (end - start)//block + 1 < samples:
        raise ValueError('Not enough capacity for safe, distinct sampled regions')
    spots = [((start + (end-start)*i//(samples-1))//block)*block for i in range(samples)]
    # Alignment floor can collide for small sizes; always fail closed.
    if len(set(spots)) != samples or spots[0] < start-block or spots[-1]+block > size-skip_edges:
        raise ValueError('Cannot space all validation regions uniquely')
    return spots


def latency_stats(values: list[float]) -> dict | None:
    if not values:
        return None
    avg = statistics.fmean(values)
    stddev = statistics.pstdev(values)
    return {'samples':len(values), 'min_ms':round(min(values),4),
            'max_ms':round(max(values),4), 'mean_ms':round(avg,4),
            'median_ms':round(statistics.median(values),4),
            'stddev_ms':round(stddev,4),
            'coefficient_of_variation':round(stddev/avg,4) if avg else None,
            'total_ms':round(sum(values),4)}


def _read(media, off, count):
    result = media.read_at(off, count)
    if len(result) != count:
        raise OSError(f'Short read at byte {off}: {len(result)} of {count}')
    return result


def _write(media, off, data):
    count = media.write_at(off, data)
    if count != len(data):
        raise OSError(f'Short write at byte {off}: {count} of {len(data)}')
    media.flush()


def _record_tx(store: JournalStore, meta: dict, state: str) -> None:
    meta['state'] = state
    store.save_meta(meta)


def restore_pending(media, journal_dir: str | Path, *, source_token: str,
                    size: int, sector: int) -> dict:
    """Recover original from an interrupted test before ANY new writes.

    A corrupt/mismatched journal never writes. Caller must have independently
    reopened and exclusively locked the exact same source device.
    """
    from json import load
    path = Path(journal_dir)
    if path.is_symlink() or (path/'region.bin').is_symlink():
        raise PermissionError('Capacity journal must not be a symlink')
    meta_path = path/'meta.json'
    if not meta_path.is_file() or meta_path.is_symlink():
        raise ValueError('No valid pending validation journal found')
    with meta_path.open('r',encoding='utf-8') as f:
        meta=load(f)
    if (meta.get('schema') != SCHEMA or meta.get('operation') != 'capacity_authenticity' or
        meta.get('source_token') != source_token or meta.get('size') != size or
        meta.get('sector') != sector or meta.get('state') not in
        {'SAVED','WRITE_PENDING','RESTORE_PENDING','RESTORE_FAILED'}):
        raise PermissionError('Journal identity or state mismatch; refusing source writes')
    offset=meta.get('offset')
    count=meta.get('length')
    if (type(offset) is not int or type(count) is not int or offset < 0 or
        count <= 0 or count > 4096 or offset%sector or count%sector or offset+count>size):
        raise ValueError('Invalid journal region')
    store=JournalStore(str(path),'disk')
    data=store.load_region(count,meta['original_sha256'])
    _write(media,offset,data)
    if _read(media,offset,count)!=data or _read(media,offset,count)!=data:
        _record_tx(store,meta,'RESTORE_FAILED')
        raise OSError('Original data was NOT restored and verified; retain the journal')
    _record_tx(store,meta,'RESTORED')
    store.clear_region()
    return {'status':'ORIGINAL_RESTORED_VERIFIED','offset':offset,'bytes':count}


def validate_spots(media, *, size: int, sector: int, source_token: str,
                   journal_dir: str | Path, samples: int=144,
                   skip_edges: int=16*1024*1024,
                   stop_requested: Callable[[],bool] | None=None,
                   progress: Callable[[dict],None] | None=None) -> dict:
    """A limited reversible-write spot test, NOT an all-sector health test.

    The caller owns physical device identity, volume locking, separate journal
    disk verification, human authorization and the media handle. Does not run
    on physical media automatically. On restore failure the original journal
    remains and every further test write stops.
    """
    offsets=planned_locations(size,sector,samples=samples,skip_edges=skip_edges)
    if Path(journal_dir).is_symlink():
        raise PermissionError('Capacity journal must not be a symlink')
    store=JournalStore(str(journal_dir),'disk')
    store.prepare_new()
    counters={'validated':0,'mismatch':0,'read_error':0,'write_error':0,
              'unstable_original':0,'restoration_error':0,'untested':0}
    records=[]; read_times=[]; write_times=[]
    emit=progress or (lambda event:None)
    for i,offset in enumerate(offsets):
        if stop_requested is not None and stop_requested():
            counters['untested']=len(offsets)-i
            break
        before=time.perf_counter()
        try:
            original=_read(media,offset,TEST_BYTES)
            if _read(media,offset,TEST_BYTES)!=original:
                raise ValueError('Original read is unstable; not safe to write')
            read_times.append((time.perf_counter()-before)*500.0)
        except (OSError,ValueError) as exc:
            outcome='unstable_original' if isinstance(exc,ValueError) else 'read_error'
            counters[outcome]+=1
            records.append({'index':i,'offset':offset,'length':TEST_BYTES,'status':outcome,
                            'error_type':type(exc).__name__})
            emit({'phase':'CAPACITY_TEST','index':i+1,'total':len(offsets),'status':outcome})
            continue
        meta={'schema':SCHEMA,'operation':'capacity_authenticity','source_token':source_token,
              'size':size,'sector':sector,'offset':offset,'length':TEST_BYTES,
              'original_sha256':hashlib.sha256(original).hexdigest()}
        # Persist preimage BEFORE marking even a possible write. If staging fails,
        # fail without touching the patient.
        store.save_region(original)
        _record_tx(store,meta,'SAVED')
        probe=secrets.token_bytes(TEST_BYTES)
        status='write_error'
        restore_ok=False
        try:
            _record_tx(store,meta,'WRITE_PENDING')
            t=time.perf_counter()
            _write(media,offset,probe)
            write_times.append((time.perf_counter()-t)*1000.0)
            _record_tx(store,meta,'RESTORE_PENDING')
            t=time.perf_counter()
            check=_read(media,offset,TEST_BYTES)
            read_times.append((time.perf_counter()-t)*1000.0)
            status='validated' if check==probe else 'mismatch'
        except OSError:
            status='write_error'
        finally:
            # Even a failed write can have partially changed the region.
            try:
                _record_tx(store,meta,'RESTORE_PENDING')
                _write(media,offset,original)
                restore_ok=(_read(media,offset,TEST_BYTES)==original and
                            _read(media,offset,TEST_BYTES)==original)
            except (OSError,RuntimeError):
                restore_ok=False
            if not restore_ok:
                _record_tx(store,meta,'RESTORE_FAILED')
                counters['restoration_error']+=1
                records.append({'index':i,'offset':offset,'length':TEST_BYTES,
                                'status':'restoration_error','probe_status':status})
                # DO NOT delete journal, do not continue testing.
                raise OSError('CRITICAL: original data restoration not verified. Stop using the drive; '
                              f'preserve journal at {journal_dir}.')
            _record_tx(store,meta,'RESTORED')
            store.clear_region()
        counters[status]+=1
        records.append({'index':i,'offset':offset,'length':TEST_BYTES,'status':status,
                        'original_restored_and_verified':True})
        emit({'phase':'CAPACITY_TEST','index':i+1,'total':len(offsets),'status':status,
              'offset':offset})
    # Only the saved sample points are evidence. A high validated offset is
    # NOT a lower bound on valid capacity; holes and aliasing can exist.
    valid=[r['offset'] for r in records if r['status']=='validated']
    status=('STOPPED_INCOMPLETE' if counters['untested'] else
            'SAMPLED_REGIONS_VERIFIED' if counters['validated']==samples else
            'CAPACITY_INTEGRITY_WARNINGS')
    return {'schema':1,'test_kind':'capacity_spot_write_restore', 'status':status,
            'declared_bytes':size,'samples_planned':len(offsets),
            'samples_completed':len(records),'sample_bytes':TEST_BYTES,
            'counters':counters,'highest_verified_offset':max(valid) if valid else None,
            'verified_regions':counters['validated'],
            'read_latency':latency_stats(read_times),
            'write_latency':latency_stats(write_times), 'regions':records,
            'notes':['These spots do NOT certify all intervening sectors or true writable capacity.',
                     'A dishonest controller can alias writes into unselected data even if tested spots restore.',
                     'No source data is claimed recovered or drive lifetime extended.']}


class RegularImageWriter:
    """Regular-file fixture only. No symlinks, devices or sparse creation."""
    def __init__(self,path: str):
        p=Path(path)
        if p.is_symlink() or not p.is_file():
            raise ValueError('Select a regular existing image, not a symlink or physical device')
        # O_BINARY is mandatory on Windows: without it, 0x0A/0x1A in probe
        # patterns are mangled and os.read can return short results.
        flags = binary_open_flags(os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0))
        fd=os.open(p, flags)
        try:
            st=os.fstat(fd)
            if not stat.S_ISREG(st.st_mode) or st.st_size<TEST_BYTES:
                raise ValueError('Image must be a nonempty regular file')
        except BaseException:
            os.close(fd)
            raise
        self.fd=fd
        self._lock=threading.Lock()
        self.size=st.st_size
        self.token=hashlib.sha256(repr((os.path.realpath(path),st.st_dev,st.st_ino,st.st_size)).encode()).hexdigest()
    def read_at(self,off:int,n:int)->bytes:
        reader = getattr(os, 'pread', None)
        if callable(reader):
            return reader(self.fd, n, off)
        # Python on Windows does not expose os.pread. Serialized seek/read with
        # a full-length loop matches ImageReadWriter / rescue I/O behavior.
        with self._lock:
            os.lseek(self.fd,off,os.SEEK_SET)
            chunks: list[bytes] = []
            remaining = n
            while remaining:
                part = os.read(self.fd, remaining)
                if not part:
                    break
                chunks.append(part)
                remaining -= len(part)
            return b''.join(chunks)
    def write_at(self,off:int,data:bytes)->int:
        # Use the shared positional writer (os.pwrite or locked seek+write).
        with self._lock:
            return pwrite(self.fd, data, off)
    def flush(self)->None:os.fsync(self.fd)
    def close(self)->None:os.close(self.fd)
