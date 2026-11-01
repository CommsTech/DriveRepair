"""DriveRepair desktop CLI.

Default recovery paths keep patient sources read-only. Experimental in-place
refresh commands can open a device for writing only after multiple explicit
destructive acknowledgements.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import zipfile

from .devices import list_external_devices, select_external_device
from .scanner import ImageReader, open_device_readonly, scan_reader
from .benchmark import read_benchmark, compare_benchmarks
from .carving import carve_image
from .archive_recovery import salvage_zip
from .health import health_snapshot
from .recovery import rescue_reader
from .fat32_undelete import undelete_fat32
from .filesystem_repair import check_ext_image, repair_ext_image
from .verification import verify_images
from .media_refresh import (
    ImageReadWriter,
    assert_patient_idle_windows,
    assert_stable_identity,
    open_device_readwrite,
    refresh_media,
    require_destructive_acknowledgements,
)



def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(
        prog="driverepair", description="Disk diagnostics, image rescue and file recovery without reboot")
    sub = cli.add_subparsers(dest="command", required=True)
    listing = sub.add_parser("list", help="List externally attached whole disks")
    listing.add_argument("--json", action="store_true")
    for name in ("scan", "scan-image"):
        cmd = sub.add_parser(name, help="Read-only scan of a selected external disk" if name == "scan"
                             else "Read-only test scan of a regular file image")
        target = cmd.add_mutually_exclusive_group(required=True)
        target.add_argument("--device" if name == "scan" else "--image", required=False)
        cmd.add_argument("--mode", choices=["sample", "full"], default="sample")
        cmd.add_argument("--samples", type=int, default=128,
                         help="Evenly spaced chunks in sample mode (default: 128)")
        cmd.add_argument("--chunk-mib", type=int, default=1, choices=[1, 2, 4, 8],
                         help="Read size in MiB (default: 1)")
        cmd.add_argument("--max-errors", type=int, default=16,
                         help="Stop after this many failing reads (default: 16)")
        cmd.add_argument("--ack-risk", action="store_true",
                         help="Required for full hardware scans; reading failing disks can worsen damage")
        cmd.add_argument("--json", action="store_true")
    for name in ("rescue-image", "rescue-external"):
        cmd = sub.add_parser(name, help="Rescue readable sectors to a separate regular-file image")
        cmd.add_argument("--image" if name == "rescue-image" else "--device", required=True)
        cmd.add_argument("--output", required=True, help="New regular-file image path")
        cmd.add_argument("--resume", action="store_true", help="Resume a journaled recovery")
        cmd.add_argument("--retry-missing", action="store_true", help="Retry missing ranges after initial pass")
        cmd.add_argument("--chunk-mib", type=int, choices=[1, 2, 4, 8], default=1)
        cmd.add_argument("--max-read-errors", type=int, default=4096)
        if name == "rescue-external":
            cmd.add_argument("--ack-risk", action="store_true", help="Accept read stress on failing media")
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
    cmd = sub.add_parser("carve-image", help="Extract intact JPEG/PNG signatures from a regular-file image")
    cmd.add_argument("--image", required=True)
    cmd.add_argument("--output-dir", required=True)
    cmd.add_argument("--formats", nargs="+", choices=["png", "jpeg"], default=["png", "jpeg"])
    cmd.add_argument("--max-files", type=int, default=100)
    cmd.add_argument("--max-file-mib", type=int, default=32)
    cmd.add_argument("--allow-incomplete-image", action="store_true")
    cmd.add_argument("--json", action="store_true")
    cmd = sub.add_parser('salvage-zip', help='Salvage intact CRC-verified ZIP members')
    cmd.add_argument('--archive', required=True)
    cmd.add_argument('--output-dir', required=True)
    cmd.add_argument('--max-files', type=int, default=1000)
    cmd.add_argument('--max-file-mib', type=int, default=128)
    cmd.add_argument('--max-total-mib', type=int, default=1024)
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
    cmd = sub.add_parser('undelete-fat32', help='Recover contiguous deleted files from FAT32 disk images')
    cmd.add_argument('--image', required=True)
    cmd.add_argument('--output-dir', required=True)
    cmd.add_argument('--max-files', type=int, default=100)
    cmd.add_argument('--max-file-mib', type=int, default=128)
    cmd.add_argument('--allow-incomplete-image', action='store_true')
    cmd.add_argument('--json', action='store_true')
    cmd = sub.add_parser('check-ext-image', help='Read-only ext2/3/4 filesystem check using e2fsck -n')
    cmd.add_argument('--image', required=True)
    cmd.add_argument('--json', action='store_true')
    cmd = sub.add_parser('repair-ext-image', help='Clone an ext filesystem image and repair ONLY the clone')
    cmd.add_argument('--image', required=True)
    cmd.add_argument('--output', required=True, help='New, nonexistent filesystem image copy')
    cmd.add_argument('--ack-repair', action='store_true', help='Required: agree that repair on a clone may lose damaged files')
    cmd.add_argument('--json', action='store_true')
    for name, help_text in (
        ('refresh-image',
         'In-Place Media Refresh on a regular image (rolling journal; adaptive|full)'),
        ('refresh-external',
         'In-Place Media Refresh on an external disk (rolling journal; NOT a backup substitute)'),
    ):
        cmd = sub.add_parser(name, help=help_text)
        cmd.add_argument('--image' if name == 'refresh-image' else '--device', required=True)
        cmd.add_argument('--journal', required=True,
                         help='Directory for the rolling journal (meta.json + region.bin); keep OFF the patient')
        cmd.add_argument('--mode', choices=['adaptive', 'full'], default='adaptive',
                         help='adaptive=refresh slow readable regions; full=whole surface (high risk)')
        cmd.add_argument('--resume', action='store_true')
        cmd.add_argument('--chunk-mib', type=int, choices=[1, 2, 4, 8], default=1)
        cmd.add_argument('--max-errors', type=int, default=4096)
        cmd.add_argument('--consistency-reads', type=int, default=2,
                         help='Identical reads required before journaling a region (min 2)')
        cmd.add_argument('--adaptive-samples', type=int, default=256)
        cmd.add_argument('--slow-multiplier', type=float, default=2.0,
                         help='Adaptive: refresh regions at/above median_latency * multiplier')
        cmd.add_argument('--no-verify', action='store_true', help='Skip post-write reread comparison')
        cmd.add_argument('--ack-risk', action='store_true', help='Accept stress on failing media')
        cmd.add_argument('--ack-destructive', action='store_true', help='Accept patient-media writes')
        cmd.add_argument('--ack-no-backup', action='store_true',
                         help='Confirm proceeding without a full verified backup')
        cmd.add_argument('--ack-data-loss-risk', action='store_true',
                         help='Confirm understanding that in-place writes can destroy remaining recoverable data')
        if name == 'refresh-external':
            cmd.add_argument('--ack-usb-bridge-risk', action='store_true',
                             help='Required for USB/dock patients: bridges may drop, hide SMART, or fake serials')
            cmd.add_argument('--ack-unvalidated-hardware', action='store_true',
                             help='Required: live hardware refresh is still unvalidated (sacrificial tests pending)')
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
        raise RuntimeError('Cannot independently confirm destination block-device ancestry')
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


def _run_extras(args) -> int:
    if args.command == 'health':
        selected = select_external_device(args.device)
        latest = select_external_device(args.device)
        if latest.fingerprint != selected.fingerprint:
            raise RuntimeError('Patient device changed before SMART query')
        result = health_snapshot(selected)
    elif args.command == 'compare-benchmarks':
        with open(args.before, encoding='utf-8') as f:
            before = json.load(f)
        with open(args.after, encoding='utf-8') as f:
            after = json.load(f)
        result = compare_benchmarks(before, after)
    elif args.command == 'salvage-zip':
        result = salvage_zip(args.archive, args.output_dir, max_files=args.max_files,
                             max_file_mib=args.max_file_mib, max_total_mib=args.max_total_mib)
    elif args.command == 'verify-images':
        result = verify_images(args.image, args.output)
    elif args.command == 'undelete-fat32':
        result = undelete_fat32(args.image, args.output_dir, max_files=args.max_files,
                                max_file_mib=args.max_file_mib,
                                allow_incomplete=args.allow_incomplete_image)
    elif args.command == 'check-ext-image':
        result = check_ext_image(args.image)
    elif args.command == 'repair-ext-image':
        result = repair_ext_image(args.image, args.output, ack_repair=args.ack_repair)
    elif args.command == 'carve-image':
        result = carve_image(args.image, args.output_dir, formats=tuple(args.formats),
                             max_files=args.max_files, max_file_mib=args.max_file_mib,
                             allow_incomplete=args.allow_incomplete_image)
    elif args.command in {'refresh-image', 'refresh-external'}:
        is_device = args.command == 'refresh-external'
        if args.consistency_reads < 2:
            raise ValueError('--consistency-reads must be >= 2')
        if is_device:
            selected = select_external_device(args.device)
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
            reread = select_external_device(args.device)
            assert_stable_identity(selected, reread)
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
            source_token, size = _source_image_token(args.image)
            media = ImageReadWriter(args.image)
            sector = 512 if size % 512 == 0 else 1
        try:
            if not args.json:
                print(
                    f'DESTRUCTIVE In-Place Media Refresh ({args.mode}). '
                    'Rolling journal protects only the active region. '
                    'Unreadable/inconsistent sectors are skipped, not invented.',
                    file=sys.stderr,
                )

            def identity_check() -> None:
                if is_device:
                    latest = select_external_device(args.device)
                    assert_stable_identity(selected, latest)

            def check_progress(state):
                identity_check()
                if args.json:
                    return
                if state.get('status') == 'probing' and state.get('message'):
                    print(state['message'], file=sys.stderr)
                    return
                cursor = int(state.get('cursor') or 0)
                rewritten = int(state.get('rewritten_bytes') or 0)
                if rewritten and rewritten % (8 * 1024 * 1024) < int(state.get('chunk') or 1):
                    print(f"Refresh rewritten {rewritten:,} bytes mode={args.mode}", file=sys.stderr)
                elif args.mode == 'full' and cursor % (64 * 1024 * 1024) < int(state.get('chunk') or 1):
                    print(f"Refresh cursor {cursor:,}/{size:,} mode={args.mode}", file=sys.stderr)

            result = refresh_media(
                media, size=size, sector=sector, source_token=source_token,
                journal=args.journal, chunk=args.chunk_mib * 1024 * 1024,
                mode=args.mode, verify=not args.no_verify, resume=args.resume,
                max_errors=args.max_errors, consistency_reads=args.consistency_reads,
                adaptive_samples=args.adaptive_samples, slow_multiplier=args.slow_multiplier,
                progress=check_progress, identity_check=identity_check,
            )
        finally:
            media.close()
        if is_device:
            latest = select_external_device(args.device)
            if latest.fingerprint != source_token:
                result['status'] = 'aborted_device_identity_changed'
    else:
        is_device = args.command.endswith('-external')
        if is_device:
            if not getattr(args, 'ack_risk', False):
                raise ValueError('Live-device operations require --ack-risk')
            selected = select_external_device(args.device)
            if args.command == 'rescue-external':
                _verify_linux_patient_not_in_use(selected)
                _separate_linux_destination(selected, args.output)
            reread = select_external_device(args.device)
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
                def check_progress(state):
                    if is_device:
                        latest = select_external_device(args.device)
                        if latest.fingerprint != source_token:
                            raise RuntimeError('Patient device changed mid-recovery; job halted')
                result = rescue_reader(reader, size=size, sector=sector,
                                       output=args.output, source_token=source_token,
                                       chunk=args.chunk_mib * 1024 * 1024,
                                       max_failed_reads=args.max_read_errors,
                                       resume=args.resume, retry_missing=args.retry_missing,
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
            latest = select_external_device(args.device)
            if latest.fingerprint != source_token:
                result['status'] = 'aborted_device_identity_changed'
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps(result, indent=2))
    return 0 if result.get('status') in {'completed', 'comparison_only', 'smart_passed_limited',
                                         'clean', 'corrected', 'corrected_reboot_flag', 'verified_byte_exact',
                                         'completed_with_skips_or_verify_failures'} else 2


def run(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == 'gui':
            from .gui import launch
            launch()
            return 0
        if args.command in {'rescue-image', 'rescue-external', 'benchmark-image',
                            'benchmark-external', 'carve-image', 'salvage-zip',
                            'undelete-fat32', 'verify-images', 'check-ext-image', 'repair-ext-image',
                            'compare-benchmarks', 'health', 'refresh-image', 'refresh-external'}:
            return _run_extras(args)
        if args.command == "list":
            devices = list_external_devices()
            if args.json:
                print(json.dumps([device.public() for device in devices], indent=2))
            elif not devices:
                print("No eligible external whole disks detected. Internal disks are excluded.")
            else:
                for device in devices:
                    print(f"{device.id} | {device.model} | {device.size_bytes:,} bytes "
                          f"| {device.bus} | sector {device.sector_size} bytes | "
                          f"serial {device.public()['serial_suffix']}")
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
            if not args.json:
                print("READ-ONLY scan. This DOES NOT repair disks or verify data integrity.",
                      file=sys.stderr)
            def report(current: int, total: int) -> None:
                if not args.json and (current == total or current == 1 or
                                     current % max(1, total // 10) == 0):
                    print(f"Scanning: {current}/{total} chunks", file=sys.stderr)
            result = scan_reader(reader, size=size, sector=sector,
                                 mode=args.mode, samples=args.samples,
                                 chunk=args.chunk_mib * 1024 * 1024,
                                 max_errors=args.max_errors, progress=report)
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
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Status: {result['status']}; attempted {result['attempted_bytes']:,} bytes; "
                  f"readable {result['readable_bytes']:,}; read-error chunks "
                  f"{result['read_error_chunks']}")
            if result["mode"] == "sample":
                print("Sample scan only — untested regions may have errors.")
        return 0 if result["status"] == "completed" else 2
    except (ValueError, RuntimeError, OSError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Scan cancelled; no changes were made to the selected disk.", file=sys.stderr)
        return 130


def main() -> None:
    raise SystemExit(run())
