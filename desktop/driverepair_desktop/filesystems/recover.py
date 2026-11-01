"""Unified image recovery: filesystem undelete when possible, else RAW carve."""
from __future__ import annotations

import os
from typing import Any

from ..carving import carve_image
from ..fat32_undelete import undelete_fat32
from .detect import DetectedFilesystem, detect_filesystems
from .exfat import undelete_exfat
from .ntfs import undelete_ntfs

# Filesystems with an undelete backend in this tree.
FS_UNDELETE = {"fat32", "ntfs", "exfat"}
# Known but not yet filesystem-aware — RAW only with an explicit note.
FS_RAW_ONLY = {"btrfs", "zfs", "apfs", "ext", "fat16", "unknown"}

DEFAULT_RAW_FORMATS = ("png", "jpeg", "mp4", "pdf", "ole", "docx", "xlsx")


def _subdir(base: str, name: str) -> str:
    path = os.path.join(base, name)
    os.makedirs(path, mode=0o700, exist_ok=False)
    return path


def _run_fs(fs: DetectedFilesystem, image: str, out_dir: str, *,
            max_files: int, max_file_mib: int, allow_incomplete: bool) -> dict[str, Any]:
    if fs.kind == "fat32":
        # Existing FAT32 helper expects to create out_dir itself and finds its own volume.
        return undelete_fat32(
            image, out_dir, max_files=max_files, max_file_mib=max_file_mib,
            allow_incomplete=allow_incomplete,
        )
    if fs.kind == "ntfs":
        return undelete_ntfs(
            image, out_dir, partition_offset=fs.offset, max_files=max_files,
            max_file_mib=max_file_mib, allow_incomplete=allow_incomplete,
        )
    if fs.kind == "exfat":
        return undelete_exfat(
            image, out_dir, partition_offset=fs.offset, max_files=max_files,
            max_file_mib=max_file_mib, allow_incomplete=allow_incomplete,
        )
    raise ValueError(f"No undelete backend for {fs.kind}")


def recover_image(
    image: str,
    output_dir: str,
    *,
    mode: str = "auto",
    max_files: int = 100,
    max_file_mib: int = 128,
    allow_incomplete: bool = False,
    raw_formats: tuple[str, ...] = DEFAULT_RAW_FORMATS,
) -> dict[str, Any]:
    """Recover deleted/orphan files from a disk or volume image.

    Modes:
      - ``filesystem``: only FS-aware undelete (FAT32/NTFS/exFAT)
      - ``raw``: signature carving only
      - ``auto``: FS undelete for supported volumes, plus RAW carve; unsupported
        FS types (Btrfs/ZFS/APFS/ext/…) automatically use RAW
    """
    if mode not in {"auto", "filesystem", "raw"}:
        raise ValueError("mode must be auto, filesystem, or raw")
    source = os.path.abspath(image)
    target = os.path.abspath(output_dir)
    if source.replace("\\", "/").lower().startswith(("/dev/", "//./", "//?/")):
        raise ValueError("recover-image requires a regular image file, not a raw device")
    if not os.path.isfile(source):
        raise FileNotFoundError(source)
    if os.path.lexists(target):
        raise FileExistsError("Choose a new, nonexistent output directory")
    os.mkdir(target, mode=0o700)

    detected = detect_filesystems(source)
    results: dict[str, Any] = {
        "status": "completed",
        "mode": mode,
        "image": source,
        "output_dir": target,
        "detected_filesystems": [
            {"kind": d.kind, "offset": d.offset, "confidence": d.confidence, "notes": d.notes}
            for d in detected
        ],
        "filesystem_passes": [],
        "raw_pass": None,
        "notes": [],
    }

    if mode in {"auto", "filesystem"}:
        supported = [d for d in detected if d.kind in FS_UNDELETE]
        unsupported = [d for d in detected if d.kind in FS_RAW_ONLY or d.kind not in FS_UNDELETE]
        if mode == "filesystem" and not supported:
            kinds = ", ".join(sorted({d.kind for d in detected})) or "unknown"
            raise ValueError(
                f"No filesystem undelete backend for detected volume(s): {kinds}. "
                "Use --mode raw or --mode auto for signature carving."
            )
        for idx, fs in enumerate(supported):
            sub = os.path.join(target, f"fs_{idx}_{fs.kind}_{fs.offset}")
            try:
                pass_result = _run_fs(
                    fs, source, sub, max_files=max_files, max_file_mib=max_file_mib,
                    allow_incomplete=allow_incomplete,
                )
            except FileExistsError:
                raise
            except Exception as exc:  # noqa: BLE001 — collect per-volume failures
                results["filesystem_passes"].append({
                    "filesystem": fs.kind,
                    "partition_offset": fs.offset,
                    "status": "error",
                    "error": f"{type(exc).__name__}: {exc}",
                })
                continue
            results["filesystem_passes"].append(pass_result)
        for fs in unsupported:
            results["notes"].append(
                f"{fs.kind} at offset {fs.offset}: no FS-aware undelete yet; "
                "use RAW carve / imaging."
            )

    if mode in {"auto", "raw"}:
        raw_dir = os.path.join(target, "raw_carved")
        raw_result = carve_image(
            source, raw_dir, formats=raw_formats, max_files=max_files,
            max_file_mib=max_file_mib, allow_incomplete=allow_incomplete,
        )
        results["raw_pass"] = raw_result
        results["notes"].append(
            "RAW carving ignores filesystem metadata and may include live, deleted, "
            "or fragmented orphans. Plain .txt is not signature-carved."
        )

    recovered = sum(p.get("files_recovered", 0) for p in results["filesystem_passes"]
                    if isinstance(p, dict))
    carved = (results["raw_pass"] or {}).get("files_carved", 0)
    results["files_recovered_total"] = recovered + carved
    results["summary"] = (
        f"detected={len(detected)} fs_undelete_files={recovered} raw_carved={carved}"
    )
    return results
