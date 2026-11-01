# Security Policy

## Supported versions

| Version | Security review |
|---|---|
| `main` / 0.3.1b1 engineering candidate | Best effort; **not authorized for unrestricted public physical repair** |

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
