"""Read-only cold-storage file fixity checks for intermittently connected drives.

A SHA-256 manifest is small compared with a second drive image, but cannot
reconstruct lost bytes and cannot tell if the original baseline was healthy.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
from pathlib import Path, PurePosixPath
import stat
from datetime import datetime, timezone
from typing import Callable

SCHEMA = 'driverepair.cold-storage.v1'
MAX_MANIFEST_BYTES = 128 * 1024 * 1024
MAX_FILES = 2_000_000
MAX_DETAILS = 2000
_READ_SIZE = 1024 * 1024


def _when() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _root(directory: str) -> Path:
    path = Path(directory).resolve(strict=True)
    if not path.is_dir():
        raise ValueError('Select a directory, not a raw disk, file, or image')
    return path


def _new_output(path: str, root: Path) -> Path:
    output = Path(path).absolute()
    if output.exists() or output.is_symlink():
        raise FileExistsError('Result already exists; keep old baselines and use a NEW filename')
    if not output.parent.is_dir() or output.parent.is_symlink():
        raise ValueError('Select an existing, non-symlinked output directory')
    parent = output.parent.resolve(strict=True)
    if parent == root or root in parent.parents:
        raise ValueError('Store manifests and reports OUTSIDE the protected archive directory')
    return parent / output.name


def _regular_nofollow(path: Path):
    before = path.lstat()
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
        raise OSError('Symbolic links and non-regular files are not checked')
    if getattr(before, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0):
        raise OSError('Windows reparse-point files are not followed')
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(path, flags)
    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode):
            raise OSError('Not a regular file')
        identity = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        if (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns) != identity:
            raise OSError('File changed during opening')
        h = hashlib.sha256()
        with os.fdopen(fd, 'rb', closefd=False) as f:
            while True:
                data = f.read(_READ_SIZE)
                if not data:
                    break
                h.update(data)
        after = os.fstat(fd)
        if (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) != identity:
            raise OSError('File changed during hashing')
        return opened.st_size, h.hexdigest()
    finally:
        os.close(fd)


def _valid_relative(name: str) -> bool:
    if not isinstance(name, str) or not name or '\\' in name or '\x00' in name:
        return False
    p = PurePosixPath(name)
    return (not p.is_absolute() and len(p.parts) > 0
            and all(x not in {'.', '..', ''} for x in p.parts)
            and p.as_posix() == name and ':' not in p.parts[0])


def _walk(root: Path, *, issues: list[dict]):
    def onerror(exc):
        issues.append({'path': str(getattr(exc, 'filename', '?')), 'reason': type(exc).__name__})

    for base, dirs, files in os.walk(root, topdown=True, followlinks=False, onerror=onerror):
        basepath = Path(base)
        safe_dirs = []
        for name in sorted(dirs):
            entry = basepath / name
            try:
                st = entry.lstat()
                if stat.S_ISLNK(st.st_mode) or getattr(st, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0):
                    issues.append({'path': entry.relative_to(root).as_posix(), 'reason': 'directory_link_skipped'})
                elif stat.S_ISDIR(st.st_mode):
                    safe_dirs.append(name)
                else:
                    issues.append({'path': entry.relative_to(root).as_posix(), 'reason': 'not_a_directory'})
            except OSError as exc:
                issues.append({'path': entry.relative_to(root).as_posix(), 'reason': type(exc).__name__})
        dirs[:] = safe_dirs
        for name in sorted(files):
            entry = basepath / name
            rel = entry.relative_to(root).as_posix()
            if not _valid_relative(rel):
                issues.append({'path': rel, 'reason': 'invalid_relative_path'})
                continue
            try:
                st = entry.lstat()
                if not stat.S_ISREG(st.st_mode) or getattr(st, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0):
                    issues.append({'path': rel, 'reason': 'link_or_special_file_skipped'})
                    continue
            except OSError as exc:
                issues.append({'path': rel, 'reason': type(exc).__name__})
                continue
            yield rel, entry


def _atomic_new(path: Path, content: bytes):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0), 0o600)
    try:
        with os.fdopen(fd, 'wb', closefd=False) as out:
            out.write(content)
            out.flush()
        os.fsync(fd)
    except BaseException:
        os.close(fd)
        path.unlink(missing_ok=True)
        raise
    else:
        os.close(fd)
    if os.name == 'posix':
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)


def _notify(callback: Callable | None, count: int, path: str, total: int | None = None):
    if callback and (count == 1 or count % 25 == 0 or (total is not None and count == total)):
        callback({'files_processed': count, 'files_total': total, 'current_file': path})


def create_baseline(directory: str, output: str, *, progress: Callable | None = None) -> dict:
    """Build a NEW, immutable baseline outside the archive; refuses incomplete scans."""
    root = _root(directory)
    outfile = _new_output(output, root)
    issues: list[dict] = []
    entries = []
    size_total = 0
    for rel, path in _walk(root, issues=issues):
        if len(entries) >= MAX_FILES:
            raise ValueError('Archive contains too many files for this manifest format')
        try:
            size, digest = _regular_nofollow(path)
        except (OSError, PermissionError) as exc:
            issues.append({'path': rel, 'reason': type(exc).__name__})
            continue
        entries.append({'path': rel, 'size_bytes': size, 'sha256': digest})
        size_total += size
        _notify(progress, len(entries), rel)
    # Cannot stamp an incomplete archive as a verified baseline.
    if issues:
        raise RuntimeError(f'Baseline not written: {len(issues)} files, links or folders could not be checked. '
                           f'First issue: {issues[0]["path"]} ({issues[0]["reason"]}).')
    if not entries:
        raise ValueError('No ordinary files to baseline')
    manifest = {'schema': SCHEMA, 'algorithm': 'sha256', 'created_utc': _when(),
                'label': root.name, 'trust': 'UNATTESTED_BASELINE',
                'file_count': len(entries), 'total_bytes': size_total, 'files': entries,
                'notes': 'Records bytes found today, not proof that they were originally correct. '
                         'Keep this baseline on another disk and retain old versions after additions.'}
    content = (json.dumps(manifest, sort_keys=True, separators=(',', ':'), ensure_ascii=True)+'\n').encode('utf-8')
    if len(content) > MAX_MANIFEST_BYTES:
        raise ValueError('Manifest exceeds size limit')
    _atomic_new(outfile, content)
    return {'status': 'baseline_created_unattested', 'manifest': str(outfile),
            'files_baselined': len(entries), 'bytes_hashed': size_total,
            'manifest_bytes': len(content), 'created_utc': manifest['created_utc'],
            'notes': manifest['notes']}


def _read_manifest(path: str) -> dict:
    p = Path(path)
    st = p.lstat()
    if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_MANIFEST_BYTES:
        raise ValueError('Manifest must be a regular file within the size limit')
    data = p.read_bytes()
    if len(data) > MAX_MANIFEST_BYTES:
        raise ValueError('Manifest too large')
    doc = json.loads(data)
    if (not isinstance(doc, dict) or doc.get('schema') != SCHEMA
            or doc.get('algorithm') != 'sha256'):
        raise ValueError('Unrecognized cold-storage manifest')
    entries = doc.get('files')
    if not isinstance(entries, list) or len(entries) > MAX_FILES or len(entries) != doc.get('file_count'):
        raise ValueError('Invalid manifest file count')
    seen = set()
    for e in entries:
        if not isinstance(e, dict) or not _valid_relative(e.get('path')):
            raise ValueError('Unsafe path in manifest')
        if (type(e.get('size_bytes')) is not int or e['size_bytes'] < 0 or
                not isinstance(e.get('sha256'), str) or len(e['sha256']) != 64 or
                any(c not in '0123456789abcdef' for c in e['sha256']) or e['path'] in seen):
            raise ValueError('Corrupt or duplicate manifest entry')
        seen.add(e['path'])
    return doc


def audit_archive(directory: str, manifest: str, *, progress: Callable | None = None) -> dict:
    root = _root(directory)
    baseline = _read_manifest(manifest)
    old = {e['path']: e for e in baseline['files']}
    changed, missing, added, unreadable = [], [], [], []
    seen = set()
    checked = verified_bytes = 0
    walk_issues: list[dict] = []
    for rel, path in _walk(root, issues=walk_issues):
        if rel not in old:
            added.append(rel)
            continue
        seen.add(rel)
        expected = old[rel]
        try:
            size, digest = _regular_nofollow(path)
        except (OSError, PermissionError) as exc:
            unreadable.append({'path': rel, 'reason': type(exc).__name__})
            continue
        checked += 1
        if size != expected['size_bytes'] or digest != expected['sha256']:
            changed.append({'path': rel, 'expected_size': expected['size_bytes'],
                            'observed_size': size, 'expected_sha256': expected['sha256'],
                            'observed_sha256': digest})
        else:
            verified_bytes += size
        _notify(progress, checked, rel, len(old))
    missing = sorted(set(old) - seen)
    # An inaccessible folder may contain original files. Never call those truly missing.
    if walk_issues:
        unreadable.extend(walk_issues)
    if changed or missing or unreadable:
        status = 'integrity_alert'
    elif added:
        status = 'new_files_found'
    else:
        status = 'matches_baseline'
    return {'status': status, 'baseline_created_utc': baseline.get('created_utc'),
            'baseline_label': baseline.get('label'), 'manifest': str(Path(manifest).absolute()),
            'files_expected': len(old), 'files_compared': checked,
            'verified_bytes': verified_bytes, 'files_unchanged': checked-len(changed),
            'files_changed': len(changed), 'files_missing': len(missing),
            'files_new': len(added), 'files_unreadable_or_skipped': len(unreadable),
            'changed': changed[:MAX_DETAILS], 'missing': missing[:MAX_DETAILS],
            'new': added[:MAX_DETAILS], 'unreadable_or_skipped': unreadable[:MAX_DETAILS],
            'details_truncated': any(len(x)>MAX_DETAILS for x in (changed, missing, added, unreadable)),
            'checked_utc': _when(),
            'notes': 'File hashes prove agreement with this baseline, not authenticity of the baseline. '
                     'Changes may be intentional. A hash cannot repair damaged files. '
                     'If any folders were unreadable, some files may be missing from the audit.'}


def write_html_report(result: dict, output: str, root: str) -> str:
    """Create an offline report outside the archive. Does not edit files or baseline."""
    path = _new_output(output, _root(root))
    status = result['status']
    verdict = ('Matching baseline' if status == 'matches_baseline' else
               'New files to baseline' if status == 'new_files_found' else 'Attention required')
    status_color = '#31cab5' if status == 'matches_baseline' else '#f0b35e'
    details=[]
    for key,title in (('changed','Changed files'),('missing','Missing files'),
                      ('unreadable_or_skipped','Unreadable / skipped'),('new','New files')):
        val=result.get(key, [])
        if not val:
            continue
        rows=''.join('<li>'+html.escape(x if isinstance(x,str) else str(x.get('path','?')))
                     +'</li>' for x in val)
        details.append(f'<section><h2>{html.escape(title)}</h2><ul>{rows}</ul></section>')
    cards=''.join(f'<article><small>{html.escape(title)}</small><strong>{int(result.get(field,0)):,}</strong></article>'
                  for field,title in [('files_unchanged','Unchanged'),('files_changed','Changed'),
                                      ('files_missing','Missing'),('files_new','New'),
                                      ('files_unreadable_or_skipped','Unreadable')])
    document=f'''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>DriveRepair | Cold Storage Integrity</title><style>
*{{box-sizing:border-box}}body{{font:15px Segoe UI,Arial,sans-serif; background:#0c1420;color:#edf5fa;margin:0}}
main{{max-width:1150px;margin:30px auto;padding:20px}}header,section{{background:#152337;border:1px solid #2d4258;border-radius:14px;padding:22px;margin-bottom:16px}}
h1{{margin:5px 0 12px;font-size:29px}}.eyebrow{{color:#39ccb6;letter-spacing:2px;font-weight:750}}.verdict{{font-size:20px;color:{status_color};font-weight:700}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:16px 0}}article{{border:1px solid #324a63;border-radius:9px;padding:16px;background:#1a2d42}}
article small{{display:block;color:#b3c8d9}}article strong{{font-size:26px;display:block;margin-top:6px}}li{{padding:5px;overflow-wrap:anywhere}}
p{{line-height:1.6;color:#c6d8e7}}code{{color:#a5efdf}}@media print{{body{{color:#101822;background:white}}header,section,article{{background:white;color:#101822}}p{{color:#101822}}}}
</style></head><body><main><header><div class="eyebrow">DR / DRIVE REPAIR</div><h1>Cold Storage Integrity</h1><div class="verdict">{html.escape(verdict)}</div>
<p>Compared against a SHA-256 baseline created {html.escape(str(result.get('baseline_created_utc') or 'unknown'))}. Run: {html.escape(str(result.get('checked_utc') or 'unknown'))}.</p></header>
<div class="grid">{cards}</div><section><h2>What this means</h2><p>{html.escape(result.get('notes',''))}</p>
<p>This is a file-content verification, not a full physical-media test. Review intentional changes before creating a new baseline. Retain a separate backup of irreplaceable files.</p></section>{''.join(details)}
</main></body></html>'''
    _atomic_new(path, document.encode('utf-8'))
    return str(path)
