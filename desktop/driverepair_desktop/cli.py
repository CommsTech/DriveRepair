"""DriveRepair desktop CLI. No scanning command can request a write handle."""

from __future__ import annotations

import argparse
import json
import os
import sys

from .devices import list_external_devices, select_external_device
from .scanner import ImageReader, open_device_readonly, scan_reader


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(
        prog="driverepair", description="Read-only external disk diagnostics without reboot")
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
    return cli


def run(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
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
    except (ValueError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Scan cancelled; no changes were made to the selected disk.", file=sys.stderr)
        return 130


def main() -> None:
    raise SystemExit(run())
