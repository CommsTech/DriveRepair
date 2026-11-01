# Status — 2026-11-01

PRIVATE TEST ONLY — **0.3.1b1** final engineering cycle candidate.

## Applied

- Linux offline recovery: `list-all-linux`, `plan-system-recovery`, `rescue-system` with identity + offline acks
- Internal disks excluded from ordinary `list`; NFS/CIFS/SSHFS destinations accepted when mounted
- First-observation SMART media/pending alerts (no false clean baseline)
- GUI offline recovery walkthrough; health strip starts UNKNOWN
- Debian live-build recipe scripts (ISO not built/boot-tested here)
- Prior 0.3.0b1 soft indicators + multi-FS recovery retained

## Validation

- Desktop unit suite run after apply (see latest test log)
- Artifact SHA-256 matched the engineering report for patch/pyz/whl
- Not unrestricted public beta: no real USB power-loss, ISO boot, or native Windows/macOS raw-drive matrix
