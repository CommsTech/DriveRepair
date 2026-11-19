"""Bounded, read-only hardware inspection operations for the Qt workstation."""
from __future__ import annotations

DEVICE_ACTIONS = (
    ('Drive firmware and model', 'firmware-info', False),
    ('Read-only device capabilities', 'inspect-storage', False),
    ('Sample read benchmark', 'benchmark-external', True),
    ('Investigate failed byte offset', 'probe-region', True),
    ('Windows volume optimization advice (no execution)', 'optimize-volume', False),
)


def device_tool_args(command: str, *, device_id: str, fingerprint: str = '',
                     offset: int | None = None, volume_letter: str = '',
                     read_risk_approved: bool = False) -> list[str]:
    match = next((item for item in DEVICE_ACTIONS if item[1] == command), None)
    if match is None or not device_id or not isinstance(device_id,str):
        raise ValueError('Choose a recognized external whole disk and tool')
    if match[2] and not read_risk_approved:
        raise PermissionError('Explicit approval of additional read stress required')
    args=[command,'--device',device_id]
    if command=='benchmark-external':
        args += ['--mode','sample','--ack-risk']
    elif command=='probe-region':
        if not fingerprint or len(fingerprint)!=12 or not isinstance(offset,int) or offset<0:
            raise ValueError('A prior scan byte offset and exact device fingerprint are required')
        args += ['--offset',str(offset),'--length','1048576','--max-reads','16',
                 '--confirm-identity',fingerprint,'--ack-read-stress']
    elif command=='optimize-volume':
        if len(volume_letter)!=1 or not volume_letter.isalpha():
            raise ValueError('Enter the verified volume drive letter (single character)')
        args+=['--letter',volume_letter.upper()]
        # Deliberately NO --execute. Advisory only.
    return args+['--json']
