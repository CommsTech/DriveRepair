"""Deliberate, image-to-WHOLE-USB flashing. Never accepts a patient repair target.

Only ISO-hybrid images, positively enumerated USB whole disks, per-session
identity confirmations and independent full readback verification are accepted.
No raw writes are performed while preparing/preflighting the plan.

A partial flash is destructive and has no rollback: errors are NEVER successes.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from typing import Callable

from .devices import (Device, select_external_device, assert_windows_external_write_gate)
from .media_refresh import assert_stable_identity

CHUNK_BYTES = 1024 * 1024
MAGIC = b'CD001'


def inspect_hybrid_iso(source: str | os.PathLike[str]) -> dict:
    """Minimal non-destructive ISO-hybrid gate, NOT firmware boot proof."""
    path = Path(source)
    if path.suffix.lower() != '.iso' or not path.is_file() or path.is_symlink():
        raise ValueError('Select an existing regular .iso image, not a symlink or device')
    with path.open('rb') as file:
        st = os.fstat(file.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_size < 65536:
            raise ValueError('ISO file is missing or too small')
        beginning = file.read(512)
        file.seek(16 * 2048 + 1)
        magic = file.read(5)
        if beginning[510:512] != b'\x55\xaa' or magic != MAGIC:
            raise ValueError('ISO-hybrid MBR/ISO9660 markers missing. Refusing a raw USB flash')
    return {'path': str(path.resolve()), 'bytes': st.st_size,
            'status': 'HYBRID_MARKERS_PRESENT_BOOT_UNVERIFIED'}


def validate_target(device: Device, image_size: int, *, expect_fingerprint: str,
                    typed_confirmation: str) -> None:
    if not (device.bus.strip().lower() == 'usb' and device.id and device.serial.strip()):
        raise PermissionError('USB flashing requires an external USB disk with a hardware serial')
    if device.sector_size not in (512, 1024, 2048, 4096):
        raise PermissionError('USB logical sector geometry is unsupported')
    if device.size_bytes < image_size or image_size <= 0:
        raise ValueError('ISO does not fit on selected USB disk')
    if device.fingerprint[:12] != expect_fingerprint:
        raise PermissionError('Selected USB identity has changed; refresh and reselect')
    if typed_confirmation != f'ERASE {device.id}':
        raise PermissionError(f'Type exactly ERASE {device.id} to acknowledge permanent USB erasure')
    if sys.platform == 'win32':
        if not re.fullmatch(r'windows:PhysicalDrive\d+', device.id):
            raise PermissionError('Refusing nonphysical Windows target')
        assert_windows_external_write_gate(device)
    elif sys.platform.startswith('linux'):
        if not re.fullmatch(r'/dev/(sd[a-z]+|nvme\d+n\d+|mmcblk\d+)',device.path):
            raise PermissionError('Refusing an unrecognized Linux block device path')
    else:
        raise RuntimeError('Native USB flashing currently supports Windows and Linux only')


def _source_elsewhere(device: Device, iso: str) -> None:
    """Fail closed if the ISO is on the selected USB disk or source unknown."""
    if sys.platform == 'win32':
        drive = os.path.splitdrive(os.path.abspath(iso))[0]
        if not re.fullmatch(r'[A-Za-z]:',drive):
            raise RuntimeError('ISO must reside on a local drive letter, separate from USB')
        number = int(device.id.rsplit('PhysicalDrive',1)[-1])
        command = (f"(Get-Partition -DriveLetter '{drive[0]}' -ErrorAction Stop | "
                   'Select-Object -ExpandProperty DiskNumber) | ConvertTo-Json -Compress')
        result = subprocess.run(['powershell.exe','-NoProfile','-NonInteractive',
                                 '-Command', command], capture_output=True,timeout=15,check=True)
        selected = json.loads(result.stdout.decode('utf-8-sig'))
        if type(selected) is not int:
            raise RuntimeError('Cannot establish ISO source disk identity')
        if selected == number:
            raise PermissionError('ISO resides on the USB target; refusing self-destruction')
    elif sys.platform.startswith('linux'):
        result = subprocess.run(['findmnt','--json','--target',iso,'--output','SOURCE'],
                                capture_output=True,timeout=12,check=True)
        volumes = json.loads(result.stdout).get('filesystems') or []
        if len(volumes) != 1 or not isinstance(volumes[0].get('source'),str):
            raise RuntimeError('Cannot establish ISO source filesystem')
        source = volumes[0]['source'].split('[',1)[0]
        if source.startswith('/dev/'):
            from os.path import realpath
            # Check the entire selected disk and its children, without string
            # prefix collisions such as /dev/sdb versus /dev/sdb2.
            result = subprocess.run(['lsblk','--json','--output','PATH',device.path],
                                    capture_output=True,timeout=12,check=True)
            disks = json.loads(result.stdout).get('blockdevices') or []
            def children(node):
                yield node.get('path')
                for c in node.get('children') or []:
                    yield from children(c)
            if len(disks)!=1 or any(realpath(source)==realpath(x) for x in children(disks[0]) if x):
                raise PermissionError('ISO source and USB target may be the same disk')
        # Network and overlay filesystem is acceptable only because target
        # mount/holder verification below additionally rejects active target.


def _linux_target_idle(device: Device) -> None:
    if os.geteuid() != 0:
        raise PermissionError('Raw USB flashing on Linux requires root')
    result = subprocess.run(['lsblk','--json','--output','NAME,PATH,TYPE,TRAN,MOUNTPOINTS',device.path],
                            capture_output=True,timeout=15,check=True)
    roots = json.loads(result.stdout).get('blockdevices') or []
    if len(roots) != 1 or roots[0].get('type')!='disk' or roots[0].get('path')!=device.path:
        raise RuntimeError('USB disk hierarchy changed')
    def visit(node):
        name = node.get('name')
        if not name or not re.fullmatch(r'[a-zA-Z0-9._+-]+',name):
            raise RuntimeError('Unexpected USB device/partition identity')
        if any(node.get('mountpoints') or []):
            raise RuntimeError('USB has mounted partitions; unmount before flashing')
        holders=Path('/sys/class/block')/name/'holders'
        if not holders.is_dir() or any(holders.iterdir()):
            raise RuntimeError('USB has unknown or active holders; refusing flash')
        for c in node.get('children') or []:
            visit(c)
    visit(roots[0])


def _open_target(device: Device):
    if sys.platform == 'win32':
        from .media_refresh import WindowsReadWriter
        writer = WindowsReadWriter(device, defer_raw_open=True, usb_boot_flash=True)
        try:
            writer.lock_volumes(int(device.id.rsplit('PhysicalDrive',1)[-1]), allow_mounted=True)
            # Revalidate the OS's authoritative boot/system and serial gate
            # AFTER filesystem locks, before opening a destructive handle.
            assert_windows_external_write_gate(device)
            writer.open_raw()
            return writer
        except BaseException:
            writer.close()
            raise
    _linux_target_idle(device)
    fd = os.open(device.path, os.O_RDWR | getattr(os,'O_EXCL',0) | getattr(os,'O_SYNC',0)
                 | getattr(os,'O_CLOEXEC',0))
    try:
        st=os.fstat(fd)
        if not stat.S_ISBLK(st.st_mode) or st.st_rdev != os.stat(device.path).st_rdev:
            raise RuntimeError('USB target changed during exclusive open')
    except BaseException:
        os.close(fd)
        raise
    class LinuxWriter:
        def read_at(self, offset, n): return os.pread(fd,n,offset)
        def write_at(self, offset, data): return os.pwrite(fd,data,offset)
        def flush(self): os.fsync(fd)
        def close(self): os.close(fd)
    return LinuxWriter()


def flash_usb_iso(iso: str, device_id: str, *, expect_fingerprint: str,
                  typed_confirmation: str, acknowledge_data_loss: bool,
                  progress: Callable[[dict],None] | None=None,
                  should_stop: Callable[[],bool] | None=None,
                  selected_device: Device | None=None,
                  device_lookup: Callable[[str],Device]=select_external_device,
                  target_opener: Callable[[Device],object]=_open_target) -> dict:
    """Write and independently read back the image. No automatic retry of writes.

    Device injection exists for synthetic tests; live CLI always uses OS inventory.
    """
    if acknowledge_data_loss is not True:
        raise PermissionError('Explicit permanent-data-loss acknowledgement required')
    image = inspect_hybrid_iso(iso)
    device = selected_device if selected_device is not None else device_lookup(device_id)
    if device.id != device_id:
        raise RuntimeError('Selected device identifier changed')
    validate_target(device,image['bytes'],expect_fingerprint=expect_fingerprint,
                    typed_confirmation=typed_confirmation)
    _source_elsewhere(device,image['path'])
    # For actual jobs, independently re-enumerate immediately before access.
    if selected_device is None:
        assert_stable_identity(device,device_lookup(device_id))
    emit=progress if progress is not None else lambda event: None
    padded=((image['bytes']+device.sector_size-1)//device.sector_size)*device.sector_size
    # Restrict the image to a stable regular-file descriptor throughout the job.
    with open(image['path'],'rb',buffering=0) as source:
        st=os.fstat(source.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_size!=image['bytes']:
            raise RuntimeError('ISO changed since inspection')
        writer=target_opener(device)
        written_bytes=0
        source_hash=hashlib.sha256()
        try:
            emit({'phase':'WRITING','processed_bytes':0,'total_bytes':image['bytes'],
                  'status':'DESTRUCTIVE_USB_FLASH_IN_PROGRESS'})
            while True:
                if should_stop is not None and should_stop():
                    raise InterruptedError('USB flash stopped at a write boundary; image is incomplete')
                buf=source.read(CHUNK_BYTES)
                if not buf:
                    break
                source_hash.update(buf)
                is_last = source.tell()==image['bytes']
                block=buf+(b'\0'*((-len(buf))%device.sector_size)) if is_last else buf
                if len(block)%device.sector_size:
                    raise RuntimeError('ISO read produced unaligned transfer')
                count=writer.write_at(written_bytes,block)
                if count!=len(block):
                    raise OSError('Short physical USB write; USB contents are incomplete')
                written_bytes+=count
                emit({'phase':'WRITING','processed_bytes':min(written_bytes,image['bytes']),
                      'total_bytes':image['bytes'], 'status':'IN_PROGRESS'})
            if written_bytes!=padded:
                raise RuntimeError('ISO transfer length mismatch')
            writer.flush()
            if (os.fstat(source.fileno()).st_size!=st.st_size or
                    os.fstat(source.fileno()).st_mtime_ns!=st.st_mtime_ns):
                raise RuntimeError('ISO source changed during USB flash; contents untrusted')
            # Reader is reopened from start; compare exact ISO bytes (including
            # padded final sector), with strong digest and full readback.
            h=hashlib.sha256()
            verified=0
            while verified < written_bytes:
                if should_stop is not None and should_stop():
                    raise InterruptedError('USB verification stopped; image remains unverified')
                n=min(CHUNK_BYTES,written_bytes-verified)
                raw=writer.read_at(verified,n)
                if len(raw)!=n:
                    raise OSError('Short readback. USB flash NOT verified')
                relevant=min(n,image['bytes']-verified)
                if relevant>0:
                    h.update(raw[:relevant])
                if relevant<n and raw[relevant:]!=b'\0'*(n-relevant):
                    raise OSError('USB flash padding changed on readback')
                verified+=n
                emit({'phase':'VERIFYING','processed_bytes':min(verified,image['bytes']),
                      'total_bytes':image['bytes'],'status':'VERIFYING'})
            # Recheck the source against the bytes actually written, not only
            # against a digest of a potentially changing source stream.
            source.seek(0)
            fresh=hashlib.sha256()
            while True:
                part=source.read(CHUNK_BYTES)
                if not part: break
                fresh.update(part)
            if (h.digest()!=source_hash.digest() or fresh.digest()!=source_hash.digest()):
                raise OSError('USB readback SHA-256 does not match source ISO')
            result={'status':'USB_FLASH_BYTE_VERIFIED_BOOT_UNTESTED',
                    'target_id':device.id, 'image_bytes':image['bytes'],
                    'written_bytes':written_bytes,'sha256':h.hexdigest(),
                    'note':'Disk bootability must be verified on actual BIOS/UEFI hardware'}
            emit({'phase':'DONE','processed_bytes':image['bytes'],
                  'total_bytes':image['bytes'], 'status':result['status'],
                  'sha256':result['sha256']})
            return result
        except BaseException as exc:
            emit({'phase':'FAILED','processed_bytes':min(written_bytes,image['bytes']),
                  'total_bytes':image['bytes'], 'status':'USB_CONTENTS_UNVERIFIED',
                  'error':type(exc).__name__, 'warning':'Partial flash is destructive; reflash before using USB'})
            raise
        finally:
            writer.close()
