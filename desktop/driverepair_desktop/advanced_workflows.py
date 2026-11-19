"""Qt specialist workflows backed by the same validated CLI as the recovery engine.

Only image/clone operations here: no bypass of physical media safety gates.
Each operation describes its required inputs and its effects. Never shell=True.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SpecialistAction:
    label: str
    command: str
    description: str
    source_label: str = 'Source image / archive'
    output_label: str = 'Output file or directory'
    output_flag: str = ''
    manifest: bool = False
    reference: bool = False
    file_ids: bool = False
    clone_change: bool = False

ACTIONS = (
    SpecialistAction('Inspect file systems', 'detect-filesystems', 'Read-only: identify partitions and filesystem signatures.'),
    SpecialistAction('Scan a disk image', 'scan-image', 'Read-only sample scan of a regular disk image.'),
    SpecialistAction('Check encryption', 'inspect-encryption', 'Read-only detection of encrypted volume signatures.'),
    SpecialistAction('Preview deleted FAT32 files', 'list-deleted-fat32', 'Read-only catalog; recover selected files in another operation.'),
    SpecialistAction('Preview deleted files (Sleuth Kit)', 'list-deleted-tsk', 'Read-only file catalog; requires Sleuth Kit.'),
    SpecialistAction('Recover deleted FAT32 files', 'undelete-fat32', 'Copies eligible deleted files to a NEW folder; source unchanged.', output_flag='--output-dir'),
    SpecialistAction('Recover selected files (Sleuth Kit)', 'recover-selected-tsk', 'Copies chosen filesystem IDs to a NEW folder; requires Sleuth Kit.', output_flag='--output-dir', file_ids=True),
    SpecialistAction('Automatic file recovery', 'recover-image', 'Filesystem-aware recovery and file signature carving to a NEW folder.', output_flag='--output-dir'),
    SpecialistAction('Carve photos and documents', 'carve-image', 'Finds supported signatures, saves recovered files to a NEW directory.', output_flag='--output-dir'),
    SpecialistAction('Repair a ZIP archive', 'salvage-zip', 'Extracts CRC-verified members to a NEW directory.', source_label='Damaged ZIP archive', output_flag='--output-dir'),
    SpecialistAction('Rescue an image', 'rescue-image', 'Copies readable bytes into a NEW image with a recovery journal.', output_flag='--output'),
    SpecialistAction('Resume an image rescue', 'rescue-image', 'Resumes an existing output and journal; source unchanged.', output_flag='--output'),
    SpecialistAction('Retry missing image regions', 'rescue-image', 'Attempts bounded retries for ranges missing from an existing rescue.', output_flag='--output'),
    SpecialistAction('Compare two images', 'verify-images', 'Read-only byte comparison of original and copied image.', output_flag='--output'),
    SpecialistAction('Create image hash baseline', 'integrity-baseline', 'Saves hashes of current bytes; NOT independent proof of original data.', output_flag='--output'),
    SpecialistAction('Audit image against baseline', 'integrity-audit', 'Read-only comparison against a PREVIOUSLY trusted manifest.', manifest=True),
    SpecialistAction('Restore from trusted reference', 'integrity-restore-copy', 'Copies hash-verified bytes from SAME-SNAPSHOT reference to a NEW image.', output_flag='--output', manifest=True, reference=True, clone_change=True),
    SpecialistAction('Generate forensic image evidence', 'evidence-image', 'Saves SHA-256 evidence report to a new file.', output_flag='--output'),
    SpecialistAction('Read-only ext filesystem check', 'check-ext-image', 'Runs e2fsck -n on an image; no writes.'),
    SpecialistAction('Repair a COPY of ext filesystem', 'repair-ext-image', 'Creates a new filesystem image, then repairs the COPY ONLY.', output_flag='--output', clone_change=True),
)


def build_specialist_command(action: SpecialistAction, *, source: str, output: str = '',
                             manifest: str = '', reference: str = '', file_ids: str = '',
                             clone_approved: bool = False) -> list[str]:
    if action not in ACTIONS:
        raise ValueError('Unrecognized specialist operation')
    src = source.strip()
    if not src or not Path(src).is_file():
        raise ValueError('Choose an existing source image or archive')
    args = [action.command, '--archive' if action.command == 'salvage-zip' else '--image', src]
    if action.output_flag:
        dest = output.strip()
        if not dest:
            raise ValueError('Choose a destination on separate, healthy storage')
        if Path(dest).resolve() == Path(src).resolve():
            raise ValueError('Output must not equal the source image')
        if action.command not in {'rescue-image'} or action.label == 'Rescue an image':
            if Path(dest).exists():
                raise FileExistsError('Choose a NEW output file/directory; do not overwrite existing evidence')
        else:
            if not Path(dest).is_file():
                raise ValueError('Resume/retry requires an EXISTING recovery image')
        args += [action.output_flag, dest]
    if action.manifest:
        if not manifest.strip() or not Path(manifest.strip()).is_file():
            raise ValueError('Select an existing, independently trusted hash manifest')
        args += ['--manifest', manifest.strip()]
    if action.reference:
        if not reference.strip() or not Path(reference.strip()).is_file():
            raise ValueError('Select an existing known-good reference image')
        if Path(reference).resolve() == Path(src).resolve():
            raise ValueError('A reference must be independent of the damaged image')
        args += ['--reference', reference.strip()]
    if action.file_ids:
        ids = [x.strip() for x in file_ids.split(',') if x.strip()]
        if not ids or len(ids) > 128 or any(len(x) > 64 or not all(c.isalnum() or c in ':_-.' for c in x) for x in ids):
            raise ValueError('Enter 1–128 catalog file IDs separated by commas; preview deleted files first')
        for item in ids:
            args += ['--file-id', item]
    if action.clone_change:
        if not clone_approved:
            raise PermissionError('Separate confirmation required to create and modify a recovery COPY')
        args += ['--ack-same-snapshot' if action.command == 'integrity-restore-copy' else '--ack-repair']
    if action.command == 'scan-image':
        args += ['--mode','sample']
    if action.command == 'rescue-image':
        args += ['--multi-pass'] if action.label == 'Rescue an image' else ['--resume']
        if action.label == 'Retry missing image regions':
            args += ['--retry-missing']
        args += ['--progress-jsonl', '--no-live-dashboard']
    return [*args, '--json']
