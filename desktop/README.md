# DriveRepair desktop

DriveRepair's desktop application provides a guided **Diagnose → Rescue → Verify / eligible HDD repair** workflow. For complete installation, safety boundaries, drive-type policy, boot-media instructions and troubleshooting, start with the [project README](../README.md).

## Develop and launch

```bash
cd desktop
python -m pip install -e ".[qt]"
python -m driverepair_desktop qt-gui
```

Use `python -m driverepair_desktop gui` to allow the Tk fallback. CLI commands are listed with `python -m driverepair_desktop --help`. You can run synthetic tests with `python -m unittest discover -s tests` from this directory.

### Distribution

From the repository root, build an **image-first public beta** using `python scripts/build_desktop.py --public-beta --no-wheel`, or a separate **guided HDD repair beta** using `--repair-beta --no-wheel`. A zipapp does not bundle PySide6. These builds are Python artifacts, not signed Windows installers. Physical repair eligibility still requires strong identity/SMART evidence, a separate journal and exclusive device access.

Previous desktop release notes and implementation details are preserved in [desktop engineering history](../docs/README_DESKTOP_ENGINEERING_HISTORY.md). Feature changes belong in [CHANGELOG.md](../CHANGELOG.md), not this setup guide.
