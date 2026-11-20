"""Regression coverage for zero-elision evidence and resume policy."""
import errno
from pathlib import Path

import pytest

from driverepair_desktop.recovery import rescue_reader, inspect_rescue_status

class Reader:
    def __init__(self, data, bad=()):
        self.data = data
        self.bad = tuple(bad)
    def read_at(self, start, length):
        if any(start <= i < start+length for i in self.bad):
            raise OSError(errno.EIO, 'failed read')
        return self.data[start:start+length]


def _rescue(image, data, **opts):
    return rescue_reader(Reader(data,opts.pop('bad',())), size=len(data), sector=512,
                         chunk=1024, output=str(image), source_token='same-source', **opts)


def test_verified_zero_elision_preserves_logical_bytes_and_journal(tmp_path):
    source = b'Z'*1024 + b'\0'*2048 + b'X'*1024
    image=tmp_path/'compact.img'
    result=_rescue(image,source,sparse_zeros=True)
    assert result['status']=='completed'
    assert result['zero_elided_bytes']==2048
    assert image.read_bytes()==source
    status=inspect_rescue_status(str(image))
    assert status['verified_zero_elided_bytes']==2048
    assert status['clean_rescue_complete']
    # On filesystems which support holes, the compact image should consume
    # less than a fully materialized image. Logical size never changes.
    assert image.stat().st_size==len(source)


def test_failed_read_not_misrepresented_as_verified_zero(tmp_path):
    source=b'\0'*4096
    image=tmp_path/'partial.img'
    result=_rescue(image,source,sparse_zeros=True,bad=[1024])
    assert result['status']=='completed_with_missing_data'
    assert result['zero_elided_bytes']==3072
    assert result['missing_ranges']==[[1024,1024]]
    status=inspect_rescue_status(str(image))
    assert not status['clean_rescue_complete']
    assert status['unreadable_bytes']==1024


def test_resume_requires_original_storage_policy(tmp_path):
    source=b'\0'*4096
    image=tmp_path/'resume.img'
    _rescue(image,source,sparse_zeros=True,max_chunks=1)
    with pytest.raises(RuntimeError,match='storage policy'):
        _rescue(image,source,resume=True,sparse_zeros=False)
    result=_rescue(image,source,resume=True,sparse_zeros=True)
    assert result['status']=='completed'
    assert image.read_bytes()==source


def test_non_sparse_original_mode_unchanged(tmp_path):
    source=b'\0'*1024 + b'A'*1024
    image=tmp_path/'exact.img'
    result=_rescue(image,source)
    assert result['zero_elided_bytes']==0
    assert not result['sparse_zeros']
    assert image.read_bytes()==source


def test_cli_space_saving_option_is_explicit():
    from driverepair_desktop.cli import parser
    a=parser().parse_args(['rescue-external','--device','windows:PhysicalDrive4',
                            '--output','fresh.img','--sparse-zeros','--ack-risk'])
    assert a.sparse_zeros is True
    exact=parser().parse_args(['rescue-image','--image','source.img','--output','fresh.img'])
    assert exact.sparse_zeros is False


def test_recovery_builder_detects_wsl_linux_device_node_limitation():
    from driverepair_desktop.windows_iso_build import _WSL_BUILD_SCRIPT
    assert 'mknod -m 600' in _WSL_BUILD_SCRIPT
    assert '/var/tmp/driverepair-wsl-build' in _WSL_BUILD_SCRIPT
    assert 'TMPDIR="$WORK" bash' in _WSL_BUILD_SCRIPT
    assert 'No ISO was made and no USB was written' in _WSL_BUILD_SCRIPT


def test_qt_reports_iso_progress_and_no_silent_chkdsk_redirection():
    code=(Path(__file__).resolve().parents[1]/'driverepair_desktop'/'qtgui.py').read_text(encoding='utf-8')
    assert 'def _iso_progress_begin(' in code
    assert 'setRange(0,0)' in code
    assert 'DriveRepair-iso-build.log' in code
    assert 'manual' in code.lower()
    assert "if route.action == 'filesystem':" in code
    assert 'HDD technique not applicable' in code
