# DriveRepair 0.3.3b24 — Native Windows media fallback and safety QA

## Purpose

This upgrade adds an alternate **read-only identification source** when smartctl and USB
SAT commands fail. Windows exposes device properties by `IOCTL_STORAGE_QUERY_PROPERTY`.
The seek-penalty and TRIM descriptors are **driver/bridge claims**, not proof of full ATA
IDENTIFY or SMART health. A positive read result does not prove reusable media.

## Windows test matrix (NOT performed in this container)

1. **Seagate ST1000LM048, USB-SAT compatible dock:** Compare smartctl rotation and the
   Windows independent seek/TRIM values, descriptor model, serial and exact byte size.
   Verify the displayed evidence source is SMART when it succeeds.
2. **Same Seagate, SMART-incompatible dock:** Check whether Windows native properties
   are available. Confirm all required factors agree; if any are absent, confirm the
   engine refuses physical writes and offers rescue. If they corroborate, verify that
   UI explicitly asks for acceptance of UNKNOWN health and that declining performs zero
   writes. Do not assume USB bridges correctly report seek or TRIM.
3. **SanDisk SDSSDH3 USB SSD:** HDD maintenance must remain blocked even if the USB
   adapter erroneously advertises seek penalty or no TRIM.
4. **Generic 4 GB USB flash device:** must not pass HDD readiness when the driver
   reports questionable seek/TRIM values or generic media model.
5. **Disconnect and reconnect:** ensure the inventory fingerprint, full media identity,
   mounted volumes, journal path and exclusive access are rechecked before each write.
6. **Windows HealthStatus failure/warning:** a warning must not be overwritten by an
   optimistic native ID. Review counters with original vendor tools when possible.
7. **Interrupt native query:** hardware timeout in a child must not freeze the Qt UI;
   unknown remains unknown and no write is authorized.
8. **Guarded beta tests only, disposable HDD with fully rescued data:** test a small
   journaled batch and independently verify original bytes after closing writer;
   inspect SMART if available after reconnect, and re-scan separately. Repeated errors
   still indicate unreliable media; do not represent an improved life expectancy.
9. **WSL setup:** on Windows without Debian, explicitly approve setup, verify installer
   status, initial Debian configuration and restart guidance; build ISO; independently
   boot-test UEFI and BIOS on test hardware; flash only disposable USB.

## Evidence required for physical writes

- A unique, stable physical device identity; OS whole-disk external and not system disk.
- Either SMART rotational/HDD evidence with health observations, or strict corroboration
  by native Windows device descriptor, seek penalty, no TRIM, matching size and serial,
  plus recognized OEM HDD model patterns (still potentially spoofed by USB hardware).
- If SMART health is unknown: owner gives separate explicit unknown-health approval;
  critical health warnings still block the experimental pathway.
- Independent journal on a separate healthy disk, true exclusive locks, consistent
  source byte rereads and post-write readback with digest checks.
- No SSD/NVMe/flash HDD-style refresh, no auto erasure, no claiming recovered unreadable
  sectors, no automatic trust or lifespan claim.

## Build limitations

This update was synthetically tested on Linux. Windows DeviceIoControl responses, actual
HDD rewrite, USB bridge error handling, WSL Debian installation, and recovery ISO BIOS/UEFI
boot **must be validated by a Windows hardware-enabled operator**.
