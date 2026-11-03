# Security Policy

## Supported versions

| Version | Security review |
|---|---|
| `main` / 0.3.3b13 + unreleased hardening (engineering source) | Best effort; **not authorized for unrestricted public physical repair** |

**Public distribution:** Use only the intentionally restricted `-public-beta.pyz` build from the reviewed checkout. Its CLI denies in-place image/physical-drive refresh/repair and native optimization execution. The legacy standard build and source tree retain experimental raw-write features. This policy is not a cryptographic control against a modified package.

## Product security posture

- Read-only scanner, Linux offline-system rescue, image rescue and hash/undelete
  workflows preserve patient source by using read-only handles and new output
  paths. Physical read stress can still accelerate a failing drive's loss.
- Linux `list` defaults to external-only whole disks; `list-all-linux` and
  `rescue-system` are explicitly separate, require source identity, no mounts
  or active holders, and separate destination storage. No Linux running-system
  disk rescue is allowed under this workflow.
- Linux network destinations only pass when a real NFS/NFS4/CIFS/SMB3/SSHFS
  mount is positively identified. Nonrecognized or live-root destinations
  fail closed.
- Experimental original-media refresh **can write patient sectors**; it is
  *not* yet qualified for public beta on valuable physical drives. A rolling
  journal is not an entire-disk backup, and a UPS does not eliminate its risk.
- **Volatile process-RAM-only repair** has no image, no saved preimage,
  no checkpoint and no crash-recovery capability. It is an explicitly opted-in
  LAST-RESORT mode. A partial write during application/OS/power failure may
  irreversibly damage previously readable file data. Windows raw writes still
  require an exclusive handle and locked/offline patient volumes. This option
  has only synthetic qualification, not a real USB-dock power-loss test.
- Old custom BIOS/UEFI bootloader crates are experimental; destructive USB
  provisioning scripts are hard-disabled. A Debian live-ISO build recipe
  exists but is not yet built/boot-verified.
- No cloud/account/telemetry is required. Do not send personal disk images,
  full serials, unredacted logs, file contents, or keys with bug reports.
- See `docs/FINAL_RELEASE_SECURITY_REVIEW.md` for the full outstanding
  security/hardware gates and evidence requirements.

## Reporting a vulnerability

Please open a **private security report** on the project forge (or email the maintainer listed in the repository) with:

- Affected commit SHA / tag
- OS and privilege level
- Steps to reproduce
- Impact (especially any path that can write, erase, or select the wrong disk)

Do **not** attach disk images that contain personal data.

We aim to acknowledge reports within 7 days and to publish fixes or mitigations for confirmed issues affecting the desktop read-only path.

### 0.3.3b7 opt-in local history and dependency setup

The optional anomaly map contains aligned byte offsets and classifications, not sectors, files or raw serials. It is stored with restricted local permissions in a profile data directory and never on the patient disk. It can only guide future **reads**, not write authorization. Volatile RAM-only jobs cannot save history. Smartmontools installation requires explicit user approval and calls the OS package manager by fixed package ID; no unreviewed download URL or automatic firmware update is used.
