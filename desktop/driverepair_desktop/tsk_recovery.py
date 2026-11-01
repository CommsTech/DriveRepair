"""Optional filesystem-aware deleted-file preview/extraction using The Sleuth Kit.

Python only orchestrates known local binaries; TSK handles filesystem parsing.
Never uses a shell; never writes source images. Recovered bytes are UNVERIFIED.
Supported formats depend on the installed TSK build, not our marketing claims.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

_DELETE_RE = re.compile(r'^\s*r/[a-z-]+\s+\*\s+(\d+(?:-\d+)*):\s*(.*?)\s*$')


def _check_image(path: str) -> str:
    displayed = path.replace('\\', '/').lower()
    if displayed.startswith(('/dev/', '//./', '//?/')):
        raise ValueError('Only regular-file images, not physical devices')
    if not stat.S_ISREG(os.lstat(path).st_mode):
        raise ValueError('Source must be an ordinary regular file, not symlink')
    return os.path.realpath(path)


def _find_tool(name: str) -> str:
    tool = shutil.which(name)
    if not tool:
        raise RuntimeError(f'{name} is required for filesystem-aware recovery; install The Sleuth Kit')
    return tool


def list_deleted_tsk(image: str, *, offset_sectors: int = 0,
                     max_candidates: int = 2000) -> dict:
    """Find deleted FILE metadata entries without opening output paths."""
    if not 0 <= offset_sectors <= (1 << 48) or not 1 <= max_candidates <= 10000:
        raise ValueError('Invalid offset or file catalog bound')
    image = _check_image(image)
    fls = _find_tool('fls')
    args = [fls, '-r', '-d', '-p', '-o', str(offset_sectors), image]
    # Stream instead of capture_output: a 12 TB disk could have millions of
    # directory entries. Truncate at max_candidates, without allocating them all.
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            text=True, encoding='utf-8', errors='replace')
    candidates = []
    truncated = False
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            match = _DELETE_RE.match(line)
            if not match:
                continue
            inode, name = match.groups()
            candidate_id = hashlib.sha256(
                f'{image}\0{offset_sectors}\0{inode}\0{name}'.encode('utf-8')).hexdigest()[:20]
            candidates.append({
                'id': candidate_id, 'name_hint': name[:240],
                'inode': inode, 'eligible': True,
                'reason': 'metadata_entry_present_UNVERIFIED',
                'size_bytes': None,
                'confidence': 'UNVERIFIED_deleted_inode_may_be_reallocated',
            })
            if len(candidates) >= max_candidates:
                truncated = True
                proc.kill()
                break
        proc.stdout.close()
        rc = proc.wait(timeout=120)
    except BaseException:
        proc.kill()
        proc.wait()
        raise
    if rc != 0 and not truncated:
        raise RuntimeError(f'fls failed with exit status {rc}; unsupported, corrupt or encrypted filesystem')
    return {'status': 'completed', 'backend': 'sleuthkit', 'offset_sectors': offset_sectors,
            'candidates': candidates, 'candidates_found': len(candidates),
            'eligible_count': len(candidates), 'truncated': truncated,
            'notes': 'Metadata present does NOT prove the file is still intact. '
                     'Names and inode IDs may have been reused. Output must be validated.'}


def recover_selected_tsk(image: str, output_dir: str, *, selected_ids: list[str],
                         offset_sectors: int = 0, max_file_mib: int = 1024) -> dict:
    if not selected_ids or len(selected_ids) > 1000 or len(set(selected_ids)) != len(selected_ids) or \
       any(not re.fullmatch(r'[0-9a-f]{20}', i) for i in selected_ids):
        raise ValueError('Select 1..1000 distinct valid catalog IDs')
    if not 1 <= max_file_mib <= 4096:
        raise ValueError('Maximum file size outside supported range')
    image = _check_image(image)
    output = Path(output_dir).absolute()
    if os.path.lexists(output):
        raise FileExistsError('Choose a new destination folder')
    # Validate the entire selection against a fresh read of source metadata
    # before creating output files. Truncated listings are rejected for unknown IDs.
    latest = list_deleted_tsk(image, offset_sectors=offset_sectors, max_candidates=10000)
    known = {c['id']: c for c in latest['candidates']}
    if any(i not in known for i in selected_ids):
        raise ValueError('Selected file metadata no longer present or catalog cap exceeded; preview again')
    icat = _find_tool('icat')
    output.mkdir(mode=0o700)
    results = []
    for n, selection_id in enumerate(selected_ids, 1):
        candidate = known[selection_id]
        dest = output / f'recovered_{n:05d}_inode_{candidate["inode"].replace("-", "_")}.bin'
        proc = subprocess.Popen([icat, '-r', '-o', str(offset_sectors), image, candidate['inode']],
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        total = 0
        hasher = hashlib.sha256()
        try:
            assert proc.stdout is not None
            fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                         getattr(os, 'O_BINARY', 0), 0o600)
            with os.fdopen(fd, 'wb') as output_file:
                while True:
                    data = proc.stdout.read(1024 * 1024)
                    if not data:
                        break
                    total += len(data)
                    if total > max_file_mib * 1024 * 1024:
                        raise ValueError('File recovery exceeds allowed size')
                    output_file.write(data)
                    hasher.update(data)
                output_file.flush()
                os.fsync(output_file.fileno())
            proc.stdout.close()
            rc = proc.wait(timeout=60)
            if rc != 0:
                raise RuntimeError(f'icat failed on inode {candidate["inode"]} with status {rc}')
        except BaseException:
            proc.kill()
            proc.wait()
            if dest.exists():
                dest.unlink()
            raise
        results.append({'id': selection_id, 'filename': dest.name,
                        'name_hint': candidate['name_hint'], 'size_bytes': total,
                        'sha256': hasher.hexdigest(),
                        'confidence': 'UNVERIFIED_filesystem_metadata_recovery'})
    return {'status': 'completed', 'backend': 'sleuthkit', 'files_recovered': len(results),
            'files': results, 'notes': 'Selectively recovered from IMAGE into new files only. '
            'Not cryptographically authenticated to original content; verify independently.'}
