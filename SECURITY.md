# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| `main` / `0.0.x` experimental | Yes (best-effort) |

## Product security posture

DriveRepair’s **supported** interface is the `desktop/` read-only scanner:

- Opens candidate disks with **read-only** OS APIs / flags
- Refuses internal, boot, and system disks by conservative discovery filters
- Requires an exact discovered device ID (no raw path injection for `scan`)
- Does not format, wipe, TRIM, or write to the source disk

Experimental Rust / firmware paths under `src/boot/` and disabled USB scripts are **not** supported for production use. Destructive provisioning scripts refuse to run (`exit 2`).

## Reporting a vulnerability

Please open a **private security report** on the project forge (or email the maintainer listed in the repository) with:

- Affected commit SHA / tag
- OS and privilege level
- Steps to reproduce
- Impact (especially any path that can write, erase, or select the wrong disk)

Do **not** attach disk images that contain personal data.

We aim to acknowledge reports within 7 days and to publish fixes or mitigations for confirmed issues affecting the desktop read-only path.
