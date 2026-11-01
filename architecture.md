# Architecture notes — recovery expansion

Desktop CLI (`desktop/driverepair_desktop`) is the supported recovery surface. Source devices are opened read-only; all writes create new regular files or extraction directories.

Key modules: `recovery.py` (image/external rescue + journal), `benchmark.py`, `carving.py`, `archive_recovery.py`, `health.py`, `compat.py` (Windows binary I/O / portable pwrite).

Linux `rescue-external` requires risk acknowledgment, unmounted external source with stable serial, and destination on a separately verified block device. Windows/macOS image workflows are supported; live external rescue remains Linux-only.

Rust BIOS/UEFI under `src/` is historical and not the desktop recovery engine. Media refresh remains research-only (`docs/MEDIA_REFRESH_RESEARCH.md`).
