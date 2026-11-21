"""Keep release-source bundles small without dropping executable source assets."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import zipfile

import pytest


REPO = Path(__file__).resolve().parents[2]
TOOL = REPO / 'scripts' / 'create_clean_source_archive.py'


def _loader():
    spec = importlib.util.spec_from_file_location('clean_source_archive', TOOL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_clean_source_archive_includes_essential_runtime_sources():
    tool = _loader()
    with tempfile.TemporaryDirectory() as folder:
        dest = Path(folder) / 'source.zip'
        summary = tool.build_archive(REPO, dest)
        assert summary['files'] > 200
        with zipfile.ZipFile(dest) as z:
            names = set(z.namelist())
            assert {'driverepair/README.md', 'driverepair/Cargo.toml',
                    'driverepair/desktop/driverepair_desktop/qtgui.py',
                    'driverepair/desktop/driverepair_desktop/data/drive_models.json',
                    'driverepair/scripts/build_live_iso.sh',
                    'driverepair/desktop/tests/test_scanner.py'} <= names
            assert not any('/target/' in n or '__pycache__' in n or n.endswith('.zip')
                           for n in names)
        with pytest.raises(FileExistsError):
            tool.build_archive(REPO, dest)


def test_refuse_to_package_inside_the_repo():
    tool = _loader()
    with pytest.raises(ValueError, match='outside the repository'):
        tool.build_archive(REPO, REPO / 'would_recurse.zip')


def test_git_worktree_pointer_is_never_shipped():
    """A worktree has a *file* named .git; it must not expose the gitdir path."""
    tool = _loader()
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        (root / '.git').write_text('gitdir: /sensitive/checkout/paths\n')
        (root / 'README.md').write_text('synthetic')
        shipped = [str(relative) for _, relative in tool.source_members(root)]
        assert 'README.md' in shipped
        assert '.git' not in shipped
