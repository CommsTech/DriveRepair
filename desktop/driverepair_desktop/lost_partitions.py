"""Read-only discovery of plausible lost or orphaned partitions.

Scans MBR, primary GPT, backup GPT, and aligned boot-signature probes.
Never modifies the patient. Candidates are hypotheses for imaging/TestDisk —
not automatic partition-table writes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import struct
from typing import Any, Callable


NTFS_OEM = b'NTFS    '
EXFAT_OEM = b'EXFAT   '
FAT32_OEM = b'FAT32   '
FAT16_OEM = b'FAT16   '
FAT12_OEM = b'FAT12   '
GPT_SIGNATURE = b'EFI PART'


@dataclass(frozen=True)
class PartitionCandidate:
    source: str
    offset_bytes: int
    size_bytes: int | None
    filesystem_hint: str
    confidence: str
    note: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _fs_hint_from_boot(sector: bytes) -> str | None:
    if len(sector) < 512:
        return None
    oem = sector[3:11]
    if oem == NTFS_OEM:
        return 'ntfs'
    if oem == EXFAT_OEM:
        return 'exfat'
    if oem in {FAT32_OEM, FAT16_OEM, FAT12_OEM}:
        return 'fat'
    # Some FAT volumes leave OEM blank but still look like BPB with 0x55AA.
    if sector[510:512] == b'\x55\xaa' and sector[11:13] in {b'\x00\x02', b'\x00\x08', b'\x00\x04'}:
        return 'fat_possible'
    return None


def _parse_mbr(sector: bytes, sector_size: int) -> list[PartitionCandidate]:
    if len(sector) < 512 or sector[510:512] != b'\x55\xaa':
        return []
    found: list[PartitionCandidate] = []
    for index in range(4):
        entry = sector[446 + index * 16:446 + (index + 1) * 16]
        if len(entry) < 16 or entry[4] == 0:
            continue
        lba = struct.unpack_from('<I', entry, 8)[0]
        sectors = struct.unpack_from('<I', entry, 12)[0]
        if lba == 0 or sectors == 0:
            continue
        found.append(PartitionCandidate(
            source=f'mbr_slot_{index}',
            offset_bytes=lba * sector_size,
            size_bytes=sectors * sector_size,
            filesystem_hint='unknown',
            confidence='table',
            note=f'MBR type 0x{entry[4]:02x}',
        ))
    return found


def _parse_gpt_header(header: bytes, sector_size: int) -> dict[str, int] | None:
    if len(header) < 92 or header[0:8] != GPT_SIGNATURE:
        return None
    revision, header_size = struct.unpack_from('<II', header, 8)
    if header_size < 92:
        return None
    current_lba, backup_lba = struct.unpack_from('<QQ', header, 24)
    first_usable, last_usable = struct.unpack_from('<QQ', header, 40)
    entry_lba = struct.unpack_from('<Q', header, 72)[0]
    entry_count, entry_size = struct.unpack_from('<II', header, 80)
    if entry_count <= 0 or entry_size < 128 or entry_count > 128:
        return None
    return {
        'revision': revision,
        'current_lba': current_lba,
        'backup_lba': backup_lba,
        'first_usable': first_usable,
        'last_usable': last_usable,
        'entry_lba': entry_lba,
        'entry_count': entry_count,
        'entry_size': entry_size,
        'sector_size': sector_size,
    }


def _parse_gpt_entries(blob: bytes, meta: dict[str, int], *, source: str) -> list[PartitionCandidate]:
    found: list[PartitionCandidate] = []
    entry_size = meta['entry_size']
    sector_size = meta['sector_size']
    for index in range(meta['entry_count']):
        start = index * entry_size
        entry = blob[start:start + entry_size]
        if len(entry) < 128:
            break
        if entry[0:16] == b'\x00' * 16:
            continue
        first_lba, last_lba = struct.unpack_from('<QQ', entry, 32)
        if last_lba < first_lba:
            continue
        size = (last_lba - first_lba + 1) * sector_size
        found.append(PartitionCandidate(
            source=f'{source}_entry_{index}',
            offset_bytes=first_lba * sector_size,
            size_bytes=size,
            filesystem_hint='unknown',
            confidence='table',
            note='GPT partition entry',
        ))
    return found


def _probe_signatures(read_at: Callable[[int, int], bytes], size: int, sector_size: int,
                      *, max_probes: int = 64) -> list[PartitionCandidate]:
    """Probe common alignments for filesystem boot signatures outside known tables."""
    if size < sector_size * 4 or sector_size <= 0:
        return []
    # Common first-partition starts and 1 MiB alignments across the first 256 MiB.
    candidates_offsets = {sector_size, 63 * sector_size, 2048 * sector_size, 1024 * 1024}
    step = 1024 * 1024
    limit = min(size, 256 * 1024 * 1024)
    offset = 0
    while offset < limit and len(candidates_offsets) < max_probes * 2:
        candidates_offsets.add(offset)
        offset += step
    found: list[PartitionCandidate] = []
    seen: set[int] = set()
    for off in sorted(candidates_offsets):
        if off in seen or off + sector_size > size or off % sector_size:
            continue
        seen.add(off)
        try:
            sector = read_at(off, sector_size)
        except OSError:
            continue
        hint = _fs_hint_from_boot(sector)
        if not hint:
            continue
        found.append(PartitionCandidate(
            source='boot_signature_probe',
            offset_bytes=off,
            size_bytes=None,
            filesystem_hint=hint,
            confidence='signature',
            note='Filesystem boot signature found; size unknown until table reconstruction.',
        ))
        if len(found) >= max_probes:
            break
    return found


def scan_lost_partitions(read_at: Callable[[int, int], bytes], *,
                         size_bytes: int, sector_size: int = 512) -> dict[str, Any]:
    """Return table-backed and signature-based partition hypotheses (read-only)."""
    if size_bytes <= 0 or sector_size <= 0 or size_bytes % sector_size:
        raise ValueError('Invalid geometry for partition scan')
    mbr = read_at(0, sector_size)
    table: list[PartitionCandidate] = []
    table.extend(_parse_mbr(mbr, sector_size))

    gpt_meta = None
    # Protective MBR usually places GPT at LBA 1.
    try:
        primary = read_at(sector_size, sector_size)
        gpt_meta = _parse_gpt_header(primary, sector_size)
        if gpt_meta:
            entry_bytes = gpt_meta['entry_count'] * gpt_meta['entry_size']
            entries = read_at(gpt_meta['entry_lba'] * sector_size, entry_bytes)
            table.extend(_parse_gpt_entries(entries, gpt_meta, source='gpt_primary'))
    except OSError:
        pass

    # Backup GPT header lives in the last usable LBA.
    try:
        backup_off = size_bytes - sector_size
        backup = read_at(backup_off, sector_size)
        backup_meta = _parse_gpt_header(backup, sector_size)
        if backup_meta:
            entry_bytes = backup_meta['entry_count'] * backup_meta['entry_size']
            entries = read_at(backup_meta['entry_lba'] * sector_size, entry_bytes)
            table.extend(_parse_gpt_entries(entries, backup_meta, source='gpt_backup'))
            if gpt_meta is None:
                gpt_meta = backup_meta
    except OSError:
        pass

    known_offsets = {item.offset_bytes for item in table}
    # Enrich table entries with boot hints when readable.
    enriched: list[PartitionCandidate] = []
    for item in table:
        hint = item.filesystem_hint
        try:
            boot = read_at(item.offset_bytes, sector_size)
            detected = _fs_hint_from_boot(boot)
            if detected:
                hint = detected
        except OSError:
            pass
        enriched.append(PartitionCandidate(
            source=item.source, offset_bytes=item.offset_bytes, size_bytes=item.size_bytes,
            filesystem_hint=hint, confidence=item.confidence, note=item.note,
        ))

    signatures = [
        item for item in _probe_signatures(read_at, size_bytes, sector_size)
        if item.offset_bytes not in known_offsets
    ]

    all_candidates = enriched + signatures
    return {
        'status': 'lost_partition_scan_completed',
        'patient_writes': 0,
        'geometry': {'size_bytes': size_bytes, 'sector_size': sector_size},
        'gpt_present': gpt_meta is not None,
        'mbr_present': bool(mbr[510:512] == b'\x55\xaa') if len(mbr) >= 512 else False,
        'candidates': [item.as_dict() for item in all_candidates],
        'table_backed': len(enriched),
        'signature_only': len(signatures),
        'message': ('Read-only partition hypotheses only. DriveRepair does not rewrite '
                    'partition tables from this scan. Image the disk, then use TestDisk '
                    'or a specialist tool before any structural write.'),
    }
