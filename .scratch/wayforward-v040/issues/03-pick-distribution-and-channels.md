# Pick distribution & release channels

Type: grilling
Status: resolved
Blocked by: —

## Question

Pick the primary install path and release channels.

## Answer

RESOLVED by owner (gateway-owner) 2026-11-21 + research [Distribution mechanism research](02-distribution-mechanism-research.md):

- **Requirement (owner)**: user just launches the application; all dependencies needed for full function install automatically.
- **Mechanism (research-backed hybrid)**: keep `driverepair-desktop` console-script (version 0.3.3b37 already in `desktop/pyproject.toml`) as the package; per-OS launcher/one-click entry that runs a consent-gated environment setup; extend `scripts/setup_host_environment.py` — verified report-only by default, editable-install only, and Windows/winget-only (no macOS/Linux smartctl branches) — into a real post-install dependency step covering all three OSes. Power-user fast path: PyPI + `pipx install driverepair-desktop` / `uv tool run`.
- **Rejected**: PyInstaller one-file binaries — routine Windows Defender false positives on unsigned builds; security-review opacity.
- **Channels (owner)**: Gitea releases primary, mirrored to GitHub.
