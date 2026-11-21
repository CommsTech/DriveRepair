#!/usr/bin/env python3
"""Create a compact, reproducible DriveRepair *source* ZIP (not a binary release).

Source packages include Python/Rust source, tests, model data, boot recipes and
text documentation. They exclude Rust build caches, Python caches and nested
historical release binaries that otherwise dwarf the actual repository.

This does not delete checkout files and must not be used as a signed release
artifact without separate provenance/signature and hardware qualification.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import zipfile

EXCLUDED_DIRECTORIES = frozenset({
    '.git', '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache',
    '.tox', '.venv', 'venv', 'target', 'dist', 'dist-live', 'build',
    '.agent-temp',
    # Local reverse-engineering / vendor tool trees (often gitignored); never
    # ship a multi-GB Ghidra install inside a "clean source" review ZIP.
    'tools', 'ghidra', 'r2', 'radare2',
})
EXCLUDED_EXTENSIONS = frozenset({
    '.zip', '.pyz', '.whl', '.iso', '.img', '.exe', '.dll', '.so', '.dylib',
    '.rlib', '.rmeta', '.o', '.a', '.pdb', '.pyc', '.pyo', '.efi', '.log',
})
EXCLUDED_FILENAMES = frozenset({'.git', '.coverage', 'coverage.xml', 'Thumbs.db', '.DS_Store'})


def source_members(root: Path):
    for path in sorted(root.rglob('*')):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root)
        if (any(part in EXCLUDED_DIRECTORIES for part in relative.parts[:-1])
                or path.suffix.casefold() in EXCLUDED_EXTENSIONS
                or path.name in EXCLUDED_FILENAMES):
            continue
        yield path, relative


def build_archive(root: Path, output: Path) -> dict:
    root = root.resolve()
    output = output.resolve()
    if not (root / 'Cargo.toml').is_file() or not (root / 'desktop' / 'pyproject.toml').is_file():
        raise ValueError('Expected DriveRepair repository root with Cargo.toml and desktop/pyproject.toml')
    if output.is_relative_to(root):
        raise ValueError('Write source archives outside the repository to avoid recursive packaging')
    if output.exists() or output.is_symlink():
        raise FileExistsError('Source archive already exists; refusing overwrite')
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    total = 0
    try:
        with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for file_path, relative in source_members(root):
                # Deliberately stable metadata for reproducible source reviews.
                info = zipfile.ZipInfo('driverepair/' + relative.as_posix(),
                                       date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = ((0o755 if file_path.stat().st_mode & 0o111 else 0o644) << 16)
                data = file_path.read_bytes()
                archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED,
                                 compresslevel=9)
                count += 1
                total += len(data)
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    return {'files': count, 'source_bytes': total, 'archive_bytes': output.stat().st_size}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    info = build_archive(args.root, args.output)
    print(f"Packaged {info['files']} source files; "
          f"{info['source_bytes']:,} -> {info['archive_bytes']:,} bytes")


if __name__ == '__main__':
    main()
