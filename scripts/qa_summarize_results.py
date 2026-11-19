#!/usr/bin/env python3
"""Summarize DriveRepair read-only scan outputs produced by hardware QA runs.

Windows PowerShell captures native-command banners into the redirected file, so
the JSON body is located by its first line that is exactly "{". Nothing here
touches a disk: it only reads result files.

Usage:
    python scripts/qa_summarize_results.py <results-dir> [--json]
"""
from __future__ import annotations

import glob
import json
import os
import sys


def load_scan(path: str) -> dict:
    with open(path, "rb") as handle:
        raw = handle.read()
    # PowerShell redirects with UTF-16LE by default; other shells write UTF-8.
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        text = raw.decode("utf-16", errors="replace")
    elif b"\x00" in raw[:64]:
        text = raw.decode("utf-16-le", errors="replace")
    else:
        text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        # PowerShell redirection can wrap the captured string in '[' ']' and
        # prefixes the whole block with native-command banners.
        if stripped in {"{", "[{"}:
            body = "\n".join(lines[index:]).strip()
            if body.startswith("["):
                body = body[1:].rstrip()
                if body.endswith("]"):
                    body = body[:-1]
            try:
                return json.loads(body)
            except ValueError:
                continue
    raise ValueError(f"no JSON object found in {path}")


def main(argv: list[str]) -> int:
    if not argv or argv[0].startswith("-"):
        print(__doc__.strip())
        return 2
    directory = argv[0]
    as_json = "--json" in argv
    paths = sorted(glob.glob(os.path.join(directory, "*.scan.json")))
    if not paths:
        print(f"No scan files in {directory}")
        return 2
    rows = []
    for path in paths:
        try:
            data = load_scan(path)
        except (OSError, ValueError) as exc:
            rows.append({"file": os.path.basename(path), "status": f"UNREADABLE: {exc}"})
            continue
        rows.append({
            "file": os.path.basename(path),
            "device": data.get("device") or data.get("device_path"),
            "status": data.get("status"),
            "mode": data.get("mode"),
            "attempted_mb": round((data.get("attempted_bytes") or 0) / 1048576, 1),
            "readable_mb": round((data.get("readable_bytes") or 0) / 1048576, 1),
            "read_error_chunks": data.get("read_error_chunks"),
            "slow_regions": data.get("slow_region_count"),
            "coverage_pct": data.get("surface_coverage_pct"),
            "elapsed_seconds": data.get("elapsed_seconds"),
        })
    if as_json:
        print(json.dumps(rows, indent=2))
    else:
        header = ("file", "status", "attempted_mb", "readable_mb", "errors",
                  "slow", "coverage_pct", "elapsed_seconds")
        print("  ".join(f"{name:>16s}" for name in header))
        for row in rows:
            print("  ".join(f"{str(row.get(name, '')):>16s}" for name in header))
        print("\nRead-only scans. Coverage is a sample fraction, not a health or "
              "capacity certificate.")
    return 0 if all(str(row.get("status", "")).startswith("completed") for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
