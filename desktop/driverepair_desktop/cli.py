"""DriveRepair desktop CLI.

Default recovery paths keep patient sources read-only. Experimental in-place
refresh commands can open a device for writing only after multiple explicit
destructive acknowledgements.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile

from .devices import (list_external_devices, select_external_device,
                      linux_all_devices, select_linux_any_disk)
from .scanner import ImageReader, open_device_readonly, scan_reader
from .benchmark import read_benchmark, compare_benchmarks
from .carving import carve_image
from .archive_recovery import salvage_zip
from .health import health_snapshot
from .recovery import rescue_reader
from .fat32_undelete import undelete_fat32, list_deleted_fat32
from .filesystem_repair import check_ext_image, repair_ext_image
from .verification import verify_images
from .media_refresh import (
    ImageReadWriter,
    JournalStore,
    assert_patient_idle_windows,
    assert_stable_identity,
    open_device_readwrite,
    refresh_media,
    require_destructive_acknowledgements,
)
from .power_guard import VolatilePowerGuard, PowerGuardError
from .refresh_display import RefreshDashboard
from .progress_events import ProgressEmitter
from .encryption import (
    encryption_guidance,
    require_plaintext_filesystem,
    scan_path_for_encryption,
)
from . import console_ui as cui
from .monitor import record_monitor_sample
from .tsk_recovery import list_deleted_tsk, recover_selected_tsk
from .forensics import image_evidence_manifest
from .filesystems import detect_filesystems, recover_image
from .sensors import SensorSuite


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(
        prog="driverepair", description="Disk diagnostics, image rescue and file recovery without reboot")
    sub = cli.add_subparsers(dest="command", required=True)
    listing = sub.add_parser("list", help="List externally attached whole disks")
    listing.add_argument("--json", action="store_true")
    all_disks = sub.add_parser("list-all-linux", help="READ-ONLY: show internal and external Linux whole disks for offline recovery")
    all_disks.add_argument("--json", action="store_true")
    planning = sub.add_parser("plan-system-recovery", help="READ-ONLY: validate offline internal disk and destination before rescue")
    planning.add_argument("--device", required=True, help="Linux whole-disk ID shown by list-all-linux")
    planning.add_argument("--output", required=True, help="New image file on separate mounted storage")
    planning.add_argument("--expect-fingerprint", required=True, help="Full 12-character identity hint from listing")
    planning.add_argument("--json", action="store_true")
    for name in ("scan", "scan-image"):
        cmd = sub.add_parser(name, help="Read-only scan of a selected external disk" if name == "scan"
                             else "Read-only test scan of a regular file image")
        target = cmd.add_mutually_exclusive_group(required=True)
        target.add_argument("--device" if name == "scan" else "--image", required=False)
        cmd.add_argument("--mode", choices=["triage", "sample", "full"], default="triage")
        cmd.add_argument("--samples", type=int, default=128,
                         help="Evenly spaced chunks in sample mode (default: 128)")
        cmd.add_argument("--chunk-mib", type=int, default=1, choices=[1, 2, 4, 8],
                         help="Read size in MiB (default: 1)")
        cmd.add_argument("--max-errors", type=int, default=16,
                         help="Stop after this many failing reads (default: 16)")
        cmd.add_argument("--ack-risk", action="store_true",
                         help="Required for full hardware scans; reading failing disks can worsen damage")
        cmd.add_argument("--json", action="store_true")
    for name in ("rescue-image", "rescue-external", "rescue-system"):
        cmd = sub.add_parser(name, help="Rescue readable sectors to a separate regular-file image")
        cmd.add_argument("--image" if name == "rescue-image" else "--device", required=True)
        cmd.add_argument("--output", required=True, help="New regular-file image path")
        cmd.add_argument("--resume", action="store_true", help="Resume a journaled recovery")
        if name == 'rescue-image':
            cmd.add_argument('--engine', choices=['python', 'rust'], default='python',
                             help='Rust engine is optional / image-only / requires a separately built core')
        cmd.add_argument("--retry-missing", action="store_true", help="Retry missing ranges after initial pass")
        cmd.add_argument("--multi-pass", action="store_true",
                         help="After first-pass rescue, automatically retry missing regions in smaller pieces")
        cmd.add_argument("--chunk-mib", type=int, choices=[1, 2, 4, 8], default=1)
        cmd.add_argument("--max-read-errors", type=int, default=4096)
        if name in {"rescue-external", "rescue-system"}:
            cmd.add_argument("--ack-risk", action="store_true", help="Accept read stress on failing media")
        if name == "rescue-system":
            cmd.add_argument("--expect-fingerprint", required=True,
                             help="12-character identity hint from list-all-linux")
            cmd.add_argument("--ack-offline-system", action="store_true",
                             help="Only after booting a trusted live OS; original system disk must be unmounted")
        cmd.add_argument("--json", action="store_true")
    for name in ("benchmark-image", "benchmark-external"):
        cmd = sub.add_parser(name, help="Measure read throughput and zone latency without writing")
        cmd.add_argument("--image" if name == "benchmark-image" else "--device", required=True)
        cmd.add_argument("--mode", choices=["sample", "full"], default="sample")
        cmd.add_argument("--samples", type=int, default=256)
        cmd.add_argument("--chunk-mib", type=int, choices=[1, 2, 4, 8], default=1)
        if name == "benchmark-external":
            cmd.add_argument("--ack-risk", action="store_true")
        cmd.add_argument("--json", action="store_true")
    cmd = sub.add_parser(
        "carve-image",
        help="Extract JPEG/PNG/MP4/PDF/Office signatures from a regular-file image",
    )
    cmd.add_argument("--image", required=True)
    cmd.add_argument("--output-dir", required=True)
    cmd.add_argument(
        "--formats", nargs="+",
        choices=["png", "jpeg", "mp4", "pdf", "ole", "doc", "xls", "docx", "xlsx"],
        default=["png", "jpeg"],
    )
    cmd.add_argument("--max-files", type=int, default=100)
    cmd.add_argument("--max-file-mib", type=int, default=32)
    cmd.add_argument("--allow-incomplete-image", action="store_true")
    cmd.add_argument("--ack-encrypted-volume", action="store_true",
                     help="Allow carving even if BitLocker/LUKS signatures are present (usually wrong)")
    cmd.add_argument("--json", action="store_true")
    cmd = sub.add_parser(
        "inspect-encryption",
        help="Detect BitLocker/LUKS signatures on an image (read-only; does not unlock)",
    )
    cmd.add_argument("--image", required=True)
    cmd.add_argument("--json", action="store_true")
    cmd = sub.add_parser('evidence-image', help='Read-only SHA-256 image hash and redacted evidence report')
    cmd.add_argument('--image', required=True)
    cmd.add_argument('--output', required=True, help='NEW JSON evidence manifest path')
    cmd.add_argument('--case-ref', default='', help='Optional non-identifying local case code')
    cmd.add_argument('--json', action='store_true')
    cmd = sub.add_parser('salvage-zip', help='Salvage intact CRC-verified ZIP members')
    cmd.add_argument('--archive', required=True)
    cmd.add_argument('--output-dir', required=True)
    cmd.add_argument('--max-files', type=int, default=1000)
    cmd.add_argument('--max-file-mib', type=int, default=128)
    cmd.add_argument('--max-total-mib', type=int, default=1024)
    cmd.add_argument('--json', action='store_true')
    cmd = sub.add_parser('monitor-external', help='Scheduled read-only SMART trend (optional sampled triage); NEVER auto-repairs')
    cmd.add_argument('--device', required=True)
    cmd.add_argument('--state', required=True, help='Private monitor history on healthy storage')
    cmd.add_argument('--expect-fingerprint', required=True, help='12-digit identity hint from list --json')
    cmd.add_argument('--triage', action='store_true', help='Include bounded sampled read check')
    cmd.add_argument('--ack-read-stress', action='store_true', help='Accept repeated reads of potentially failing disk')
    cmd.add_argument('--json', action='store_true')
    cmd = sub.add_parser('health', help='Read SMART/NVMe health using optional smartctl')
    cmd.add_argument('--device', required=True)
    cmd.add_argument('--json', action='store_true')
    cmd = sub.add_parser('compare-benchmarks', help='Compare two recorded read benchmarks')
    cmd.add_argument('--before', required=True)
    cmd.add_argument('--after', required=True)
    cmd.add_argument('--json', action='store_true')
    cmd = sub.add_parser('verify-images', help='Compare recovered image byte-for-byte with a stable source image')
    cmd.add_argument('--image', required=True, help='Original regular-file image')
    cmd.add_argument('--output', required=True, help='Image to verify')
    cmd.add_argument('--json', action='store_true')
    cmd = sub.add_parser('list-deleted-fat32', help='Preview deleted FAT32 files in an image without writing')
    cmd.add_argument('--image', required=True)
    cmd.add_argument('--max-candidates', type=int, default=10000)
    cmd.add_argument('--max-file-mib', type=int, default=128)
    cmd.add_argument('--allow-incomplete-image', action='store_true')
    cmd.add_argument('--ack-encrypted-volume', action='store_true')
    cmd.add_argument('--json', action='store_true')
    cmd = sub.add_parser('list-deleted-tsk', help='Preview deleted files using optional Sleuth Kit fls')
    cmd.add_argument('--image', required=True)
    cmd.add_argument('--offset-sectors', type=int, default=0)
    cmd.add_argument('--max-candidates', type=int, default=2000)
    cmd.add_argument('--json', action='store_true')
    cmd = sub.add_parser('recover-selected-tsk', help='Restore selected inode IDs using optional Sleuth Kit icat')
    cmd.add_argument('--image', required=True)
    cmd.add_argument('--output-dir', required=True)
    cmd.add_argument('--file-id', action='append', dest='file_ids', required=True)
    cmd.add_argument('--offset-sectors', type=int, default=0)
    cmd.add_argument('--max-file-mib', type=int, default=1024)
    cmd.add_argument('--json', action='store_true')
    cmd = sub.add_parser('undelete-fat32', help='Recover contiguous deleted files from FAT32 disk images')
    cmd.add_argument('--image', required=True)
    cmd.add_argument('--output-dir', required=True)
    cmd.add_argument('--max-files', type=int, default=100)
    cmd.add_argument('--max-file-mib', type=int, default=128)
    cmd.add_argument('--file-id', action='append', dest='file_ids', default=None,
                     help='Recover ONLY this catalog ID; may be specified multiple times')
    cmd.add_argument('--allow-incomplete-image', action='store_true')
    cmd.add_argument('--ack-encrypted-volume', action='store_true',
                     help='Allow undelete even if BitLocker/LUKS signatures are present (usually wrong)')
    cmd.add_argument('--json', action='store_true')
    cmd = sub.add_parser(
        'detect-filesystems',
        help='Identify FAT/NTFS/exFAT/ext/Btrfs/ZFS/APFS signatures on a disk image',
    )
    cmd.add_argument('--image', required=True)
    cmd.add_argument('--json', action='store_true')
    cmd = sub.add_parser(
        'recover-image',
        help='Unified recovery: FS undelete (FAT32/NTFS/exFAT) and/or RAW signature carve',
    )
    cmd.add_argument('--image', required=True)
    cmd.add_argument('--output-dir', required=True)
    cmd.add_argument('--mode', choices=['auto', 'filesystem', 'raw'], default='auto')
    cmd.add_argument('--max-files', type=int, default=100)
    cmd.add_argument('--max-file-mib', type=int, default=128)
    cmd.add_argument('--formats', nargs='+',
                     choices=['png', 'jpeg', 'mp4', 'pdf', 'ole', 'doc', 'xls', 'docx', 'xlsx'],
                     default=['png', 'jpeg', 'mp4', 'pdf', 'ole', 'docx', 'xlsx'])
    cmd.add_argument('--allow-incomplete-image', action='store_true')
    cmd.add_argument('--ack-encrypted-volume', action='store_true')
    cmd.add_argument('--json', action='store_true')
    cmd = sub.add_parser('check-ext-image', help='Read-only ext2/3/4 filesystem check using e2fsck -n')
    cmd.add_argument('--image', required=True)
    cmd.add_argument('--ack-encrypted-volume', action='store_true')
    cmd.add_argument('--json', action='store_true')
    cmd = sub.add_parser('repair-ext-image', help='Clone an ext filesystem image and repair ONLY the clone')
    cmd.add_argument('--image', required=True)
    cmd.add_argument('--output', required=True, help='New, nonexistent filesystem image copy')
    cmd.add_argument('--ack-repair', action='store_true', help='Required: agree that repair on a clone may lose damaged files')
    cmd.add_argument('--ack-encrypted-volume', action='store_true')
    cmd.add_argument('--json', action='store_true')
    for name, help_text in (
        ('refresh-image',
         'In-Place Media Refresh on a regular image (rolling journal; adaptive|full)'),
        ('refresh-external',
         'In-Place Media Refresh on an external disk (rolling journal; NOT a backup substitute)'),
        ('refresh-system',
         'EXPERIMENTAL: in-place refresh of an OFFLINE internal disk from Linux live USB'),
    ):
        cmd = sub.add_parser(name, help=help_text)
        cmd.add_argument('--image' if name == 'refresh-image' else '--device', required=True)
        cmd.add_argument('--journal', required=True,
                         help='Directory for the rolling journal; keep OFF the patient')
        cmd.add_argument('--mode', choices=['adaptive', 'full'], default='adaptive',
                         help='adaptive=refresh slow readable regions; full=whole surface (high risk)')
        cmd.add_argument('--journal-backend', choices=['hybrid', 'disk', 'memory', 'ramdisk'], default='disk',
                         help='disk=safest; ramdisk=Linux tmpfs plus verified live power, VOLATILE; '
                              'hybrid/memory=only synthetic images; process-local RAM is unsafe on raw drives')
        cmd.add_argument('--resume', action='store_true')
        cmd.add_argument('--chunk-mib', type=int, choices=[1, 2, 4, 8, 16, 32, 64], default=1)
        cmd.add_argument('--max-errors', type=int, default=4096)
        cmd.add_argument('--consistency-reads', type=int, default=2,
                         help='Identical reads required before journaling a region (min 2)')
        cmd.add_argument('--adaptive-samples', type=int, default=256)
        cmd.add_argument('--slow-multiplier', type=float, default=2.0,
                         help='Adaptive: refresh regions at/above median_latency * multiplier')
        cmd.add_argument('--auto-escalate', action=argparse.BooleanOptionalAction, default=True,
                         help='On slow/failed probes, automatically subdivide and retest (default: on)')
        cmd.add_argument('--no-verify', action='store_true', help='Skip post-write reread comparison')
        cmd.add_argument('--live-dashboard', action=argparse.BooleanOptionalAction, default=True,
                         help='Animated terminal dashboard during refresh (default: on)')
        cmd.add_argument('--progress-jsonl', action='store_true',
                         help='Emit throttled JSON progress lines on stderr for GUI consumers')
        cmd.add_argument('--after-run', choices=['keep', 'delete', 'ask'], default='ask',
                         help='Keep or delete the journal directory when the run finishes')
        cmd.add_argument('--ack-risk', action='store_true', help='Accept stress on failing media')
        cmd.add_argument('--ack-destructive', action='store_true', help='Accept patient-media writes')
        cmd.add_argument('--ack-no-backup', action='store_true',
                         help='Confirm proceeding without a full verified backup')
        cmd.add_argument('--ack-data-loss-risk', action='store_true',
                         help='Confirm understanding that in-place writes can destroy remaining recoverable data')
        if name in {'refresh-external', 'refresh-system'}:
            cmd.add_argument('--confirm-identity', help='12-character fingerprint shown by list --json')
            cmd.add_argument('--power-source', help='For volatile RAM: nut:UPSNAME (local USB NUT) or battery (Linux laptop)')
            cmd.add_argument('--ack-volatile-journal', action='store_true',
                             help='Accept complete original-sector journal loss on host crash/power failure')
            cmd.add_argument('--ack-dock-power-backed', action='store_true',
                             help='Confirm external USB dock is independently battery/UPS powered')
            cmd.add_argument('--ack-usb-bridge-risk', action='store_true',
                             help='Required for USB/dock patients: bridges may drop, hide SMART, or fake serials')
            cmd.add_argument('--ack-unvalidated-hardware', action='store_true',
                             help='Required: live hardware refresh is still unvalidated (sacrificial tests pending)')
            if name == 'refresh-system':
                cmd.add_argument('--ack-offline-system', action='store_true',
                                 help='Confirm the installed OS is NOT running: booted trusted Linux live USB')
        cmd.add_argument('--acoustic-watch', action='store_true',
                         help='Optional soft acoustic WATCH (needs sounddevice); not a wear meter')
        cmd.add_argument('--shock-guard', action='store_true',
                         help='Optional chassis IMU shock STOP (not platter wobble detection)')
        cmd.add_argument('--smart-deltas', action='store_true',
                         help='Record SMART counter deltas during the job as soft WATCH signals')
        cmd.add_argument('--json', action='store_true')
    cmd = sub.add_parser('ram-journal-check', help='Validate Linux RAM mount + local UPS/battery; READ-ONLY')
    cmd.add_argument('--journal', required=True, help='Proposed journal path under tmpfs/ramfs')
    cmd.add_argument('--power-source', required=True, help='nut:UPSNAME or battery')
    cmd.add_argument('--chunk-mib', type=int, choices=[1, 2, 4, 8, 16, 32, 64], default=8)
    cmd.add_argument('--json', action='store_true')
    sub.add_parser('gui', help='Launch the desktop graphical interface')
    return cli


def _source_image_token(path: str) -> tuple[str, int]:
    import hashlib
    import stat
    real = os.path.realpath(path)
    st = os.stat(path)
    if not stat.S_ISREG(st.st_mode):
        raise ValueError("Rescue source must be a regular file")
    fields = (real, st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns)
    return hashlib.sha256(repr(fields).encode()).hexdigest(), st.st_size


def _refresh_image_token(path: str) -> tuple[str, int]:
    """Immutable filesystem identity, intentionally excluding mutable mtime."""
    import hashlib
    import stat
    st = os.stat(path, follow_symlinks=False)
    if not stat.S_ISREG(st.st_mode):
        raise ValueError("Refresh patient must be a regular file")
    fields = (os.path.realpath(path), st.st_dev, st.st_ino, st.st_size)
    return hashlib.sha256(repr(fields).encode()).hexdigest(), st.st_size


def _validate_live_refresh_preflight(device, journal: str, *, ramdisk: bool = False) -> None:
    """Fail closed unless journal is on demonstrably separate storage."""
    if not device.serial:
        raise RuntimeError("Destructive refresh requires a stable hardware serial")
    if sys.platform == 'win32' and device.provenance != 'Get-Disk':
        raise RuntimeError('Live refresh requires verified Get-Disk discovery; legacy WMI inventory is read-only')
    if sys.platform.startswith("linux"):
        _verify_linux_patient_not_in_use(device)
        # The journal has not been created yet; inspect its nearest parent mount.
        check_path = os.path.join(os.path.dirname(os.path.abspath(journal)),
                                  "__driverepair_storage_check__")
        if not ramdisk:
            _separate_linux_destination(device, check_path)
        # RAM journal location validated with tmpfs+swap and power guard below.
    elif sys.platform == "win32":
        # Drive-letter destinations can be mapped to a disk number. Reject other
        # paths instead of guessing whether the journal shares the patient medium.
        import re
        import subprocess
        absolute = os.path.abspath(journal)
        drive, _ = os.path.splitdrive(absolute)
        if not re.fullmatch(r"[A-Za-z]:", drive):
            raise RuntimeError("Windows refresh journal must be on a separate local drive letter")
        number = int(device.path.rsplit("PhysicalDrive", 1)[-1])
        command = (
            f"(Get-Partition -DriveLetter '{drive[0]}' -ErrorAction Stop | "
            "Select-Object -ExpandProperty DiskNumber) | ConvertTo-Json -Compress"
        )
        completed = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive",
                                    "-Command", command], capture_output=True,
                                   check=True, timeout=25)
        target = json.loads(completed.stdout.decode("utf-8-sig"))
        if not isinstance(target, int):
            raise RuntimeError("Could not identify the journal's physical disk")
        if target == number:
            raise RuntimeError("Journal is stored on patient disk; refusing destructive refresh")
    else:
        raise RuntimeError("Raw refresh on this operating system is not validated")


def _parse_remote_mount(payload: dict, parent: str) -> bool:
    """A remote destination MUST be a real, non-root mount of a known type.

    findmnt JSON always uses Linux/POSIX paths. Keep POSIX semantics even when
    unit tests execute on Windows (os.path.realpath('/') becomes a drive root).
    """
    accepted = {"nfs", "nfs4", "cifs", "smb3", "fuse.sshfs"}
    rows = payload.get("filesystems", [])
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        return False
    row = rows[0]
    target, kind, source = row.get("target"), row.get("fstype"), row.get("source")
    if not all(isinstance(x, str) for x in (target, kind, source)):
        return False
    target_norm = target.replace("\\", "/").rstrip("/") or "/"
    parent_norm = parent.replace("\\", "/").rstrip("/") or "/"
    if kind.lower() not in accepted or target_norm == "/":
        return False
    under_target = parent_norm == target_norm or parent_norm.startswith(target_norm + "/")
    return under_target and bool(source.strip()) and not source.startswith("/dev/")


def _verified_linux_remote_destination(parent: str) -> bool:
    """Fail closed if findmnt is absent, ambiguous, or reports a local FS."""
    import subprocess
    try:
        run = subprocess.run(
            ['findmnt', '--json', '--target', parent, '--output', 'TARGET,SOURCE,FSTYPE'],
            capture_output=True, check=True, timeout=12)
        return _parse_remote_mount(json.loads(run.stdout.decode('utf-8')), parent)
    except (FileNotFoundError, OSError, subprocess.SubprocessError, ValueError, UnicodeError):
        return False


def _windows_mapped_network_root(drive_letter: str) -> str | None:
    """Return UNC root for a mapped drive letter, else None."""
    import subprocess
    letter = drive_letter.rstrip(":").upper()
    command = (
        f"$d = Get-PSDrive -Name '{letter}' -PSProvider FileSystem -ErrorAction Stop; "
        "if ($d.DisplayRoot -and ($d.DisplayRoot -match '^\\\\\\\\')) "
        "{ $d.DisplayRoot } else { '' }"
    )
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True, check=False, timeout=25,
    )
    if completed.returncode != 0:
        return None
    root = completed.stdout.decode("utf-8-sig", errors="replace").strip()
    return root or None


def _separate_windows_destination(device, output: str) -> None:
    """Require destination on another local disk number, or a verified SMB/UNC map."""
    import re
    import subprocess
    absolute = os.path.abspath(output)
    drive, _ = os.path.splitdrive(absolute)
    if not re.fullmatch(r"[A-Za-z]:", drive):
        raise RuntimeError("Windows rescue destination must be on a separate local drive letter")
    if "PhysicalDrive" not in device.path:
        raise RuntimeError("Windows live rescue requires a PhysicalDrive path")
    number = int(device.path.rsplit("PhysicalDrive", 1)[-1])
    command = (
        f"(Get-Partition -DriveLetter '{drive[0]}' -ErrorAction Stop | "
        "Select-Object -ExpandProperty DiskNumber) | ConvertTo-Json -Compress"
    )
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True, check=False, timeout=25,
    )
    if completed.returncode == 0:
        target = json.loads(completed.stdout.decode("utf-8-sig"))
        if not isinstance(target, int):
            raise RuntimeError("Could not identify the destination's physical disk")
        if target == number:
            raise RuntimeError("Destination is stored on patient disk; refusing live rescue")
        return
    # Mapped SMB/CIFS shares have no DiskNumber; accept only confirmed UNC DisplayRoot.
    unc = _windows_mapped_network_root(drive[0])
    if unc:
        return
    raise RuntimeError(
        "Cannot confirm Windows destination isolation (not a local partition and not a "
        "verified mapped network drive); refuse live rescue/monitor writes"
    )


def _separate_live_destination(device, output: str) -> None:
    """Platform-specific destination isolation for live-device rescue/monitor state."""
    if sys.platform.startswith("linux"):
        _separate_linux_destination(device, output)
    elif sys.platform == "win32":
        _separate_windows_destination(device, output)
    else:
        raise RuntimeError(
            "Live-device rescue destination isolation is not validated on this OS; "
            "use image rescue from an already-copied image"
        )


def _separate_linux_destination(device, output: str) -> None:
    """Require a mounted destination backed by a different Linux block device."""
    if not sys.platform.startswith('linux'):
        raise RuntimeError('Live-device rescue currently requires Linux destination isolation; '
                           'Windows and macOS support image rescue and scanning')
    if not device.path.startswith('/dev/'):
        raise RuntimeError('Invalid source device')
    parent = os.path.realpath(os.path.dirname(os.path.abspath(output)))
    major_minor = os.stat(parent).st_dev
    dest = os.path.realpath(f'/sys/dev/block/{os.major(major_minor)}:{os.minor(major_minor)}')
    source = os.path.realpath('/sys/class/block/' + os.path.basename(device.path))
    if not os.path.exists(dest) or not os.path.exists(source):
        # A deliberately mounted NFS/CIFS/SSHFS export is remote storage,
        # not a local /sys/dev/block device. Never accept an unrecognized
        # pseudo-filesystem (tmpfs, overlay, FUSE unknown) as an image target.
        if os.path.exists(source) and _verified_linux_remote_destination(parent):
            return
        raise RuntimeError('Cannot independently confirm destination physical ancestry or trusted network mount')
    checked = set()
    def overlapping(node: str) -> bool:
        node = os.path.realpath(node)
        if node in checked:
            return False
        checked.add(node)
        if node == source or node.startswith(source + os.sep):
            return True
        slaves = os.path.join(node, 'slaves')
        return os.path.isdir(slaves) and any(
            overlapping(os.path.join(slaves, x)) for x in os.listdir(slaves))
    if overlapping(dest):
        raise RuntimeError('Destination filesystem resides on patient disk; source writes forbidden')



def _verify_linux_patient_not_in_use(device) -> None:
    """Require stable serial plus no mounts/holders before live acquisition."""
    import subprocess
    if not device.serial:
        raise RuntimeError('Live rescue requires a hardware serial; USB bridge identity is ambiguous')
    if not sys.platform.startswith('linux'):
        raise RuntimeError('Linux-only live rescue preflight')
    result = subprocess.run(['lsblk', '--json', '-o', 'NAME,MOUNTPOINTS', device.path],
                            capture_output=True, check=True, timeout=15)
    records = json.loads(result.stdout.decode('utf-8')).get('blockdevices', [])
    if len(records) != 1:
        raise RuntimeError('Unexpected lsblk hierarchy for rescue patient')
    def mounted(entry):
        if any(p for p in entry.get('mountpoints') or []):
            return True
        return any(mounted(x) for x in entry.get('children') or [])
    if mounted(records[0]):
        raise RuntimeError('Refusing a mounted/active source; unmount all its filesystems')
    block = os.path.basename(device.path)
    holders = os.path.join('/sys/class/block', block, 'holders')
    if not os.path.isdir(holders):
        raise RuntimeError('Cannot inspect source holders')
    if os.listdir(holders):
        raise RuntimeError('Source belongs to an active device-mapper/RAID stack')
    # An unmounted partition can still be an active encrypted, RAID or LVM
    # *component*. Checking only the whole-disk holders misses that hazard.
    def check_child_holders(entry):
        name = entry.get('name')
        if not isinstance(name, str) or not name:
            raise RuntimeError('Cannot identify patient child partition')
        holder_path = os.path.join('/sys/class/block', name, 'holders')
        if not os.path.isdir(holder_path):
            raise RuntimeError(f'Cannot inspect active holders for {name}')
        if os.listdir(holder_path):
            raise RuntimeError(f'Patient device {name} is in use by a mapper/RAID/volume')
        for child in entry.get('children') or []:
            check_child_holders(child)
    check_child_holders(records[0])


def _run_extras(args) -> int:
    if args.command == 'monitor-external':
        selected = select_external_device(args.device)
        if selected.fingerprint[:12] != args.expect_fingerprint:
            raise RuntimeError('Drive identity confirmation changed')
        # The monitor writes history. NEVER allow that state file to
        # resolve to the patient disk, even if the patient is mounted.
        _separate_live_destination(selected, args.state)
        try:
            snapshot = health_snapshot(selected)
        except RuntimeError as exc:
            snapshot = {'status': 'unknown', 'reason': str(exc)}
        triage = None
        if args.triage:
            if not args.ack_read_stress:
                raise ValueError('--triage requires --ack-read-stress')
            reader = open_device_readonly(selected)
            try:
                triage = scan_reader(reader, size=selected.size_bytes, sector=selected.sector_size,
                                     mode='triage', samples=96, chunk=1024 * 1024)
            finally:
                reader.close()
        latest = select_external_device(args.device)
        if latest.fingerprint != selected.fingerprint:
            raise RuntimeError('Drive changed during monitoring; history not written')
        result = record_monitor_sample(args.state, fingerprint=selected.fingerprint,
                                       size_bytes=selected.size_bytes, health=snapshot, triage=triage)
    elif args.command == 'health':
        selected = select_external_device(args.device)
        latest = select_external_device(args.device)
        if latest.fingerprint != selected.fingerprint:
            raise RuntimeError('Patient device changed before SMART query')
        try:
            result = health_snapshot(selected)
        except RuntimeError as exc:
            # Missing smartctl / unknown SMART must stay UNKNOWN — never invent a pass.
            result = {
                'status': 'unknown',
                'device': selected.public(),
                'reason': str(exc),
                'notes': 'SMART unavailable. Install smartmontools (smartctl) for hardware counters. '
                         'Unknown is not a clean bill of health.',
            }
    elif args.command == 'rescue-image' and args.engine == 'rust':
        # The native engine is opt-in until independent OS builds and crash
        # recovery tests are complete. Never quietly switch journal formats.
        from .recovery import _safe_path
        src, out = os.path.realpath(args.image), _safe_path(args.output)
        _source_image_token(args.image)
        if os.path.exists(out) and os.path.samefile(src, out):
            raise ValueError('Source and destination image are the same file')
        executable = os.environ.get('DRIVEREPAIR_RUST_CORE') or shutil.which('driverepair-recovery-core')
        if not executable:
            raise RuntimeError('Rust core not installed. Build rust/recovery-core and set DRIVEREPAIR_RUST_CORE; '
                               'or choose --engine python for the tested legacy engine.')
        if args.retry_missing and not args.resume:
            raise ValueError('--retry-missing requires --resume')
        if args.multi_pass and args.retry_missing:
            raise ValueError('--multi-pass and --retry-missing cannot be combined')
        command = [executable, 'rescue-image', src, out, '--chunk-mib', str(args.chunk_mib)]
        if args.resume:
            command.append('--resume')
        result = subprocess.run(command, capture_output=True, text=True, timeout=None, check=False)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        if result.stdout:
            print(result.stdout)
        return result.returncode
    elif args.command == 'ram-journal-check':
        guard = VolatilePowerGuard(args.power_source, args.journal, args.chunk_mib * 1024 * 1024)
        try:
            verified = guard.check(force=True)
        except PowerGuardError as exc:
            raise RuntimeError(f'Volatile journal power/RAM preflight failed: {exc}') from exc
        result = {'operation': 'ram_journal_check',
                  **verified,
                  'status': 'power_and_ram_verified',
                  'note': 'This does not prove dock power, media health, or protection from host restart.'}
    elif args.command == 'compare-benchmarks':
        with open(args.before, encoding='utf-8') as f:
            before = json.load(f)
        with open(args.after, encoding='utf-8') as f:
            after = json.load(f)
        result = compare_benchmarks(before, after)
    elif args.command == 'evidence-image':
        result = image_evidence_manifest(args.image, args.output, case_ref=args.case_ref)
    elif args.command == 'salvage-zip':
        result = salvage_zip(args.archive, args.output_dir, max_files=args.max_files,
                             max_file_mib=args.max_file_mib, max_total_mib=args.max_total_mib)
    elif args.command == 'verify-images':
        result = verify_images(args.image, args.output)
    elif args.command == 'inspect-encryption':
        findings = scan_path_for_encryption(args.image)
        result = {
            "schema": 1,
            "operation": "inspect_encryption",
            "status": "completed",
            "image": args.image,
            "encrypted": bool(findings),
            "findings": [f.public() for f in findings],
            "guidance": encryption_guidance(findings),
        }
    elif args.command == 'list-deleted-tsk':
        result = list_deleted_tsk(args.image, offset_sectors=args.offset_sectors,
                                  max_candidates=args.max_candidates)
    elif args.command == 'recover-selected-tsk':
        result = recover_selected_tsk(args.image, args.output_dir, selected_ids=args.file_ids,
                                      offset_sectors=args.offset_sectors,
                                      max_file_mib=args.max_file_mib)
    elif args.command == 'list-deleted-fat32':
        enc = require_plaintext_filesystem(
            args.image, ack_encrypted_volume=args.ack_encrypted_volume,
            operation='FAT32 deleted-file preview',
        )
        result = list_deleted_fat32(args.image, max_candidates=args.max_candidates,
                                    max_file_mib=args.max_file_mib,
                                    allow_incomplete=args.allow_incomplete_image)
        if enc:
            result['encryption_warnings'] = [f.public() for f in enc]
    elif args.command == 'undelete-fat32':
        enc = require_plaintext_filesystem(
            args.image, ack_encrypted_volume=args.ack_encrypted_volume,
            operation="FAT32 undelete",
        )
        result = undelete_fat32(args.image, args.output_dir, max_files=args.max_files,
                                max_file_mib=args.max_file_mib,
                                allow_incomplete=args.allow_incomplete_image,
                                selected_ids=args.file_ids)
        if enc:
            result = {**result, "encryption_warnings": [f.public() for f in enc],
                      "guidance": encryption_guidance(enc)}
    elif args.command == 'detect-filesystems':
        detected = detect_filesystems(args.image)
        result = {
            "schema": 1,
            "operation": "detect_filesystems",
            "status": "completed",
            "image": args.image,
            "filesystems": [
                {"kind": d.kind, "offset": d.offset, "size_hint": d.size_hint,
                 "confidence": d.confidence, "notes": d.notes}
                for d in detected
            ],
        }
    elif args.command == 'recover-image':
        enc = require_plaintext_filesystem(
            args.image, ack_encrypted_volume=args.ack_encrypted_volume,
            operation="unified image recovery",
        )
        result = recover_image(
            args.image, args.output_dir, mode=args.mode, max_files=args.max_files,
            max_file_mib=args.max_file_mib, allow_incomplete=args.allow_incomplete_image,
            raw_formats=tuple(args.formats),
        )
        if enc:
            result = {**result, "encryption_warnings": [f.public() for f in enc],
                      "guidance": encryption_guidance(enc)}
    elif args.command == 'check-ext-image':
        enc = require_plaintext_filesystem(
            args.image, ack_encrypted_volume=args.ack_encrypted_volume,
            operation="ext filesystem check",
        )
        result = check_ext_image(args.image)
        if enc:
            result = {**result, "encryption_warnings": [f.public() for f in enc]}
    elif args.command == 'repair-ext-image':
        enc = require_plaintext_filesystem(
            args.image, ack_encrypted_volume=args.ack_encrypted_volume,
            operation="ext filesystem repair",
        )
        result = repair_ext_image(args.image, args.output, ack_repair=args.ack_repair)
        if enc:
            result = {**result, "encryption_warnings": [f.public() for f in enc]}
    elif args.command == 'carve-image':
        enc = require_plaintext_filesystem(
            args.image, ack_encrypted_volume=args.ack_encrypted_volume,
            operation="file carving",
        )
        result = carve_image(args.image, args.output_dir, formats=tuple(args.formats),
                             max_files=args.max_files, max_file_mib=args.max_file_mib,
                             allow_incomplete=args.allow_incomplete_image)
        if enc:
            result = {**result, "encryption_warnings": [f.public() for f in enc],
                      "guidance": encryption_guidance(enc)}
    elif args.command in {'refresh-image', 'refresh-external', 'refresh-system'}:
        is_device = args.command != 'refresh-image'
        is_system = args.command == 'refresh-system'
        if args.consistency_reads < 2:
            raise ValueError('--consistency-reads must be >= 2')
        if is_device and args.journal_backend not in {'disk', 'ramdisk'}:
            raise ValueError('Physical refresh supports only disk or explicitly verified ramdisk journaling')
        if is_device and args.no_verify:
            raise ValueError('Physical-device refresh cannot disable read-back verification')
        # Paint something immediately — device open / identity checks can take seconds.
        # ASCII ellipsis only (PowerShell cp1252 mojibake on Unicode …).
        if args.live_dashboard:
            print(
                f'[{time.strftime("%H:%M:%S")}] Preparing {args.mode} refresh '
                f'(journal={args.journal_backend}); opening patient...',
                file=sys.stderr, flush=True,
            )
        device_label = ""
        guard = None
        if is_device:
            if is_system:
                if not sys.platform.startswith('linux'):
                    raise RuntimeError('Offline system refresh requires a trusted Linux live environment')
                if not args.ack_offline_system:
                    raise ValueError('Offline system refresh requires --ack-offline-system')
                selected = select_linux_any_disk(args.device)
            else:
                selected = select_external_device(args.device)
            device_label = f"{selected.id}  {selected.model[:28]}  {cui.fmt_bytes(selected.size_bytes)}"
            require_destructive_acknowledgements(
                ack_risk=args.ack_risk,
                ack_destructive=args.ack_destructive,
                ack_no_backup=args.ack_no_backup,
                ack_data_loss_risk=args.ack_data_loss_risk,
                ack_usb_bridge_risk=getattr(args, 'ack_usb_bridge_risk', False),
                bus=selected.bus,
                ack_unvalidated_hardware=getattr(args, 'ack_unvalidated_hardware', False),
                require_unvalidated=True,
            )
            assert_patient_idle_windows(selected)
            if not args.confirm_identity or args.confirm_identity != selected.fingerprint[:12]:
                raise ValueError('Physical writes require --confirm-identity with the current list --json identity_hint')
            # Duplicate bridge serials can identify distinct drives; fail closed.
            inventory = linux_all_devices() if is_system else list_external_devices()
            for other in inventory:
                if other.id != selected.id and other.serial == selected.serial:
                    raise RuntimeError('Multiple disks report the same hardware serial; identity is ambiguous')
            if args.journal_backend == 'ramdisk':
                if not args.ack_volatile_journal:
                    raise ValueError('RAM journal requires --ack-volatile-journal')
                if (not is_system or selected.bus.lower() in {'usb', 'firewire', 'thunderbolt'}) and not args.ack_dock_power_backed:
                    raise ValueError('USB/dock RAM journal requires --ack-dock-power-backed')
                guard = VolatilePowerGuard(args.power_source or '', args.journal,
                                           args.chunk_mib * 1024 * 1024)
                try:
                    guard.check(force=True)
                except PowerGuardError as exc:
                    raise RuntimeError(
                        f'Volatile journal power/RAM preflight failed: {exc}'
                    ) from exc
            _validate_live_refresh_preflight(selected, args.journal,
                                             ramdisk=args.journal_backend == 'ramdisk')
            reread = (select_linux_any_disk(args.device) if is_system
                      else select_external_device(args.device))
            assert_stable_identity(selected, reread)
            if args.live_dashboard:
                print(
                    f'[{time.strftime("%H:%M:%S")}] Opening read/write handle on {selected.id}...',
                    file=sys.stderr, flush=True,
                )
            media = open_device_readwrite(selected)
            size, sector = selected.size_bytes, selected.sector_size
            source_token = selected.fingerprint
        else:
            require_destructive_acknowledgements(
                ack_risk=args.ack_risk,
                ack_destructive=args.ack_destructive,
                ack_no_backup=args.ack_no_backup,
                ack_data_loss_risk=args.ack_data_loss_risk,
                ack_usb_bridge_risk=True,
                bus='file',
                require_unvalidated=False,
            )
            source_token, size = _refresh_image_token(args.image)
            media = ImageReadWriter(args.image)
            sector = 512 if size % 512 == 0 else 1
        # BitLocker/LUKS: byte-identical refresh is OK; warn so operators do not
        # follow up with carving/repair against ciphertext.
        enc_path = args.device if is_device else args.image
        enc_findings: list = []
        if not is_device:
            try:
                enc_findings = scan_path_for_encryption(enc_path)
            except OSError:
                enc_findings = []
        if enc_findings:
            print(
                "NOTE: encryption signature(s) detected — refresh preserves ciphertext bytes only. "
                "Do NOT carve/undelete/repair this volume until unlocked. "
                + "; ".join(encryption_guidance(enc_findings)[:2]),
                file=sys.stderr, flush=True,
            )
        emitter = ProgressEmitter(enabled=bool(args.progress_jsonl), min_interval_s=0.1)
        # Live progress on stderr (TTY panel, line-mode for logs, optional JSONL for GUI).
        # Prefer a real in-place panel in interactive PowerShell / Windows Terminal.
        if args.live_dashboard and sys.stderr.isatty():
            os.environ.setdefault("DRIVEREPAIR_FORCE_TTY_DASHBOARD", "1")
        dashboard = RefreshDashboard(
            mode=args.mode, size=size, enabled=bool(args.live_dashboard),
            journal_backend=args.journal_backend, emitter=emitter,
            device_label=device_label,
        )
        dashboard.handle({
            "status": "starting", "force": True,
            "message": f"Patient open - starting {args.mode} refresh",
            "offset": 0,
        })
        try:
            # Banner only when not painting the full panel (avoid scrolling under the UI).
            if not (args.live_dashboard and dashboard._is_tty()):
                print(
                    f'DESTRUCTIVE In-Place Media Refresh ({args.mode}, journal={args.journal_backend}). '
                    'Rolling journal protects only the active region. '
                    'Unreadable/inconsistent sectors are skipped, not invented. '
                    'mechanical*=latency proxy (USB docks have no acoustic mic).',
                    file=sys.stderr, flush=True,
                )

            sensors = SensorSuite(
                acoustic=bool(getattr(args, 'acoustic_watch', False)),
                shock=bool(getattr(args, 'shock_guard', False)),
                smart_deltas=bool(getattr(args, 'smart_deltas', False)),
            )
            if sensors.smart and is_device:
                try:
                    snap = health_snapshot(selected)
                    from .monitor import _numbers
                    sensors.ingest_smart_counters(_numbers({'health': snap}))
                except Exception:
                    pass

            def identity_check() -> None:
                if is_device:
                    latest = (select_linux_any_disk(args.device) if is_system
                              else select_external_device(args.device))
                    assert_stable_identity(selected, latest)

            def pre_write() -> None:
                if guard:
                    guard.check()
                # Shock only on the write path — acoustic sampling is too slow for pre-write.
                if sensors.shock:
                    ev = sensors.shock.poll(offset_bytes=sensors.last_offset)
                    if ev:
                        sensors.events.append(ev)
                    if ev and ev.severity == 'stop':
                        raise RuntimeError(
                            'Shock STOP: chassis motion exceeded threshold; '
                            'journal retained. IMU is not platter metrology.'
                        )

            def check_progress(state):
                identity_check()
                offset = state.get('offset')
                if type(offset) is int:
                    sensors.note_offset(offset)
                for ev in sensors.poll(offset_bytes=offset if type(offset) is int else None):
                    if ev.severity == 'watch':
                        state = {
                            **state,
                            'health': {
                                **(state.get('health') or {}),
                                'mechanical': 'WATCH',
                            },
                            'message': ev.message,
                            'sensor_event': {
                                'kind': ev.kind, 'severity': ev.severity,
                                'offset_bytes': ev.offset_bytes,
                            },
                        }
                    elif ev.severity == 'stop':
                        raise RuntimeError(ev.message)
                dashboard.handle(state)

            result = refresh_media(
                media, size=size, sector=sector, source_token=source_token,
                journal=args.journal, chunk=args.chunk_mib * 1024 * 1024,
                mode=args.mode, verify=not args.no_verify, resume=args.resume,
                max_errors=args.max_errors, consistency_reads=args.consistency_reads,
                adaptive_samples=args.adaptive_samples, slow_multiplier=args.slow_multiplier,
                journal_backend=args.journal_backend, auto_escalate=args.auto_escalate,
                progress=check_progress, identity_check=identity_check,
                pre_write_check=pre_write,
            )
            result['sensors'] = sensors.public_summary()
            if not args.json:
                dashboard.finish(result)
        finally:
            media.close()
        if is_device:
            latest = (select_linux_any_disk(args.device) if is_system
                      else select_external_device(args.device))
            if latest.fingerprint != source_token:
                result['status'] = 'aborted_device_identity_changed'
        # Journal retention policy after a finished run.
        keep = args.after_run
        if keep == 'ask' and not args.json and sys.stdin.isatty():
            answer = input(f"Keep refresh journal at {args.journal}? [y/N]: ").strip().lower()
            keep = 'keep' if answer in {'y', 'yes'} else 'delete'
        elif keep == 'ask':
            keep = 'keep'
        result['journal_retained'] = keep == 'keep'
        # Only auto-delete after an exact clean completed run. Any abort/skip/interrupt
        # must keep region.bin/meta.json for resume and forensic inspection.
        if keep == 'delete' and result.get('status') == 'completed' and not result.get('transaction'):
            try:
                JournalStore(args.journal, args.journal_backend).cleanup()
                result['journal_deleted'] = True
            except OSError as exc:
                result['journal_deleted'] = False
                result['journal_delete_error'] = str(exc)
        elif keep == 'delete':
            result['journal_deleted'] = False
            result['journal_delete_skipped'] = (
                f"refused to delete journal while status={result.get('status')!r}"
            )
    else:
        is_device = args.command.endswith('-external') or args.command == 'rescue-system'
        if is_device:
            if not getattr(args, 'ack_risk', False):
                raise ValueError('Live-device operations require --ack-risk')
            if args.command == 'rescue-system':
                if not sys.platform.startswith('linux') or not args.ack_offline_system:
                    raise ValueError('rescue-system requires Linux live recovery and --ack-offline-system')
                selected = select_linux_any_disk(args.device)
                if selected.fingerprint[:12] != args.expect_fingerprint:
                    raise ValueError('Source identity fingerprint does not match the operator confirmation')
            else:
                selected = select_external_device(args.device)
            if args.command in {'rescue-external', 'rescue-system'}:
                if sys.platform.startswith('linux'):
                    _verify_linux_patient_not_in_use(selected)
                _separate_live_destination(selected, args.output)
            reread = (select_linux_any_disk(args.device) if args.command == 'rescue-system'
                      else select_external_device(args.device))
            if selected.fingerprint != reread.fingerprint:
                raise RuntimeError('Source identity changed before read')
            reader = open_device_readonly(selected)
            size, sector = selected.size_bytes, selected.sector_size
            source_token = selected.fingerprint
        else:
            source_token, size = _source_image_token(args.image)
            if args.command == 'rescue-image' and os.path.lexists(args.output):
                if os.path.samefile(args.image, args.output):
                    raise ValueError('Rescue source and destination are the same file')
            reader = ImageReader(args.image)
            sector = 512 if size % 512 == 0 else 1
        try:
            if args.command.startswith('rescue-'):
                if args.multi_pass and args.retry_missing:
                    raise ValueError('--multi-pass and --retry-missing cannot be combined')
                def check_progress(state):
                    if is_device:
                        latest = (select_linux_any_disk(args.device) if args.command == 'rescue-system'
                                  else select_external_device(args.device))
                        if latest.fingerprint != source_token:
                            raise RuntimeError('Patient device changed mid-recovery; job halted')
                result = rescue_reader(reader, size=size, sector=sector,
                                       output=args.output, source_token=source_token,
                                       chunk=args.chunk_mib * 1024 * 1024,
                                       max_failed_reads=args.max_read_errors,
                                       resume=args.resume, retry_missing=args.retry_missing,
                                       progress=check_progress)
                if args.multi_pass and result.get('status') == 'completed_with_missing_data':
                    # Revalidate device immediately before targeted retries.
                    check_progress(result)
                    result = rescue_reader(reader, size=size, sector=sector,
                                           output=args.output, source_token=source_token,
                                           chunk=args.chunk_mib * 1024 * 1024,
                                           max_failed_reads=args.max_read_errors,
                                           resume=True, retry_missing=True,
                                           progress=check_progress)
            else:
                result = read_benchmark(reader, size=size, sector=sector,
                                        mode=args.mode, samples=args.samples,
                                        chunk=args.chunk_mib * 1024 * 1024)
        finally:
            reader.close()
        if args.command.startswith('benchmark-'):
            result['source_fingerprint'] = source_token
            result['device_size_bytes'] = size
        if is_device:
            latest = (select_linux_any_disk(args.device) if args.command == 'rescue-system'
                      else select_external_device(args.device))
            if latest.fingerprint != source_token:
                result['status'] = 'aborted_device_identity_changed'
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps(result, indent=2))
    if args.command in {'refresh-image', 'refresh-external', 'refresh-system'}:
        return 0 if result.get('status') == 'completed' else 2
    return 0 if result.get('status') in {'completed', 'comparison_only', 'smart_passed_limited',
                                         'clean', 'corrected', 'corrected_reboot_flag', 'verified_byte_exact',
                                         'completed_with_skips_or_verify_failures',
                                         'power_and_ram_verified', 'baseline_recorded', 'no_new_signal_observed',
                                         # Honest soft outcomes (never invent a pass).
                                         'unknown', 'completed_with_missing_data'} else 2


def run(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == 'gui':
            from .gui import launch
            launch()
            return 0
        if args.command in {'plan-system-recovery'}:
            if not sys.platform.startswith('linux'):
                raise RuntimeError('Offline-system-drive recovery currently requires Linux')
            selected = select_linux_any_disk(args.device)
            if selected.fingerprint[:12] != args.expect_fingerprint:
                raise ValueError('Device identity fingerprint mismatch')
            _verify_linux_patient_not_in_use(selected)
            _separate_linux_destination(selected, args.output)
            parent = os.path.realpath(os.path.dirname(os.path.abspath(args.output)))
            if not os.path.isdir(parent) or os.path.lexists(args.output):
                raise RuntimeError('Destination parent must exist and output must be new')
            free = shutil.disk_usage(parent).free
            report = {'status': 'ready_for_read_only_rescue' if free >= selected.size_bytes
                      else 'insufficient_reported_free_space', 'device': selected.public(),
                      'required_bytes': selected.size_bytes, 'destination_free_bytes': free,
                      'notes': 'Preflight only, no imaging or patient writes. Remote quotas may not be reflected in free space. '
                               'Boot trusted live media first; do not run on an active system disk.'}
            print(json.dumps(report, indent=2))
            return 0 if free >= selected.size_bytes else 2
        if args.command in {'rescue-image', 'rescue-external', 'rescue-system', 'benchmark-image',
                            'benchmark-external', 'carve-image', 'salvage-zip',
                            'undelete-fat32', 'list-deleted-fat32',
                            'list-deleted-tsk', 'recover-selected-tsk',
                            'detect-filesystems', 'recover-image',
                            'verify-images', 'check-ext-image', 'repair-ext-image',
                            'compare-benchmarks', 'health', 'refresh-image', 'refresh-external', 'refresh-system',
                            'ram-journal-check', 'monitor-external', 'evidence-image',
                            'inspect-encryption'}:
            return _run_extras(args)
        if args.command in {"list", "list-all-linux"}:
            if args.command == 'list-all-linux':
                if not sys.platform.startswith('linux'):
                    raise RuntimeError('Internal disk inventory is Linux-only')
                devices = linux_all_devices()
            else:
                devices = list_external_devices()
            if args.json:
                print(json.dumps([device.public() for device in devices], indent=2))
            if not devices:
                print("No eligible whole disks detected.",
                      file=sys.stderr if args.json else sys.stdout)
            else:
                # Human table always on stderr when --json so operators can read it.
                out = sys.stderr if args.json else sys.stdout
                cui.enable_windows_vt()
                print(cui.paint("Whole disks (including internal)" if args.command == 'list-all-linux'
                                else "External whole disks", cui.BOLD, cui.CYAN, stream=out), file=out)
                print(f"{'ID':<28} {'SIZE':>10} {'BUS':<9} {'SERIAL':<10} {'VERIFY':<12} MODEL / LOCATION", file=out)
                print("-" * 108, file=out)
                for device in devices:
                    pub = device.public()
                    print(
                        f"{device.id:<28} {cui.fmt_bytes(device.size_bytes):>10} "
                        f"{device.bus:<9} {pub['serial_suffix']:<10} {pub['identity_hint']:<12} "
                        f"{device.model} / {pub['location']}",
                        file=out,
                    )
            return 0

        if args.command == "scan":
            if args.mode == "full" and not args.ack_risk:
                raise ValueError("Full physical-disk scans require --ack-risk; "
                                 "reading a failing drive can reduce its remaining life")
            device = select_external_device(args.device)
            identity = device.fingerprint
            # Re-query before opening, to detect renumbered/replaced devices.
            verified = select_external_device(args.device)
            if verified.fingerprint != identity:
                raise RuntimeError("Device identity changed; rescan external devices")
            size = device.size_bytes
            sector = device.sector_size
            context = {"device": device.public()}
            reader = open_device_readonly(device)
        else:
            image = os.path.abspath(args.image)
            reader = ImageReader(image)
            size = os.path.getsize(image)
            sector = 512 if size % 512 == 0 else 1
            context = {"image_test_file": os.path.basename(image)}

        try:
            print("READ-ONLY scan. This DOES NOT repair disks or verify data integrity.",
                  file=sys.stderr)
            def report(current: int, total: int) -> None:
                if current == total or current == 1 or current % max(1, total // 10) == 0:
                    pct = int(100 * current / max(1, total))
                    bar = cui.progress_bar(current, total, 20)
                    print(f"\rSCAN  {current}/{total} {pct:3d}% {bar}   ", end="",
                          file=sys.stderr, flush=True)
            result = scan_reader(reader, size=size, sector=sector,
                                 mode=args.mode, samples=args.samples,
                                 chunk=args.chunk_mib * 1024 * 1024,
                                 max_errors=args.max_errors, progress=report)
            print(file=sys.stderr)
        finally:
            reader.close()

        if args.command == "scan":
            # A changed/disappeared device after scan means we must not report success.
            try:
                end = select_external_device(args.device)
                if end.fingerprint != identity:
                    result["status"] = "aborted_device_identity_changed"
            except (RuntimeError, ValueError):
                result["status"] = "aborted_device_not_present_after_scan"
        result.update(context)
        # Human summary on stderr; machine JSON on stdout when requested.
        err_n = int(result.get("read_error_chunks") or 0)
        print(
            f"Scan {result['status']}: readable {cui.fmt_bytes(int(result['readable_bytes']))} / "
            f"attempted {cui.fmt_bytes(int(result['attempted_bytes']))}  "
            f"errors={err_n}  elapsed={float(result.get('elapsed_seconds') or 0):.1f}s",
            file=sys.stderr,
        )
        if result.get("mode") in {"sample", "triage"}:
            print("Sample scan only - untested regions may still have errors.", file=sys.stderr)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Status: {result['status']}; attempted {result['attempted_bytes']:,} bytes; "
                  f"readable {result['readable_bytes']:,}; read-error chunks "
                  f"{result['read_error_chunks']}")
        return 0 if result["status"] == "completed" else 2
    except (ValueError, RuntimeError, OSError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Operation interrupted. If this was media refresh, KEEP the recovery journal "
              "and inspect the transaction before resuming; the patient may have been written.", file=sys.stderr)
        return 130


def main() -> None:
    raise SystemExit(run())
