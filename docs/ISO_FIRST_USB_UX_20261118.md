# Recovery USB and USB repair UX — 2026-11-18

## What was changed

- The Qt sidebar now offers one primary action: **Create recovery USB**. Advanced ISO builder and kit export are accessible when no ISO is installed (their CLI methods remain unchanged).
- The creator searches for a previously selected valid image, then searches only local `DriveRepair-Live*.iso` files beside the app, in `images/`, the repository's `dist-live/` and `dist/`, or the user-local DriveRepair `images` folder. Users can explicitly choose a different hybrid ISO. The last successful selection is saved as a local path and revalidated next time.
- If no real ISO is present, the UI says so and offers **Use existing ISO**, **Build ISO (Linux)**, or **Export build kit**. An ISO-building ZIP is *never* presented as a bootable image. No automatic external downloads or substitute Linux distributions.
- The source archive contains **no ready-to-flash ISO**. A release engineer must produce, independently verify, and bundle an actual DriveRepair live ISO for a true first-run select-USB-and-flash Windows experience. Store the built artifact named `DriveRepair-Live*.iso` in `images/` adjacent to the zipapp. Its checksum and BIOS/UEFI test receipts must be distributed separately. The app's ISO marker check is not a boot-test or cryptographic signature.
- USB flashing retains separate target selection, typed erasure confirmation, full-disk identity verification, exclusive locking and full readback checks. Existing repair patients are **never** allowed to be presumed safe USB flash targets.
- The evidence-map coverage aggregator now extends contiguous observed spans in O(1) for sequential reads while retaining exact union accounting for retries and out-of-order probes. This reduces UI-side bookkeeping; it does not accelerate slow drive hardware.
- The sidebar includes an opt-in GitHub Sponsors link to `https://github.com/sponsors/CommsTech`, matching Repository Detective. It does not make network requests until clicked. `.github/FUNDING.yml` configures the GitHub sponsor button.
- Physical repair with a disk that has **no reported hardware serial** is now blocked in the GUI *before* starting the expensive scan. Read-only Diagnose and Rescue remain available. Do not spoof an identity or bypass OS exclusive locks.

## Hardware qualification still needed

1. Build the ISO on an isolated Debian live-build machine; verify ISO hash, BIOS and UEFI boot, controller/storage enumeration, read-only patient defaults, and durable output mounting.
2. Place the tested ISO beside the Windows application as `images/DriveRepair-Live-amd64.iso`. Launch **Create recovery USB** and confirm it is preselected with no file-picker step.
3. Flash a **disposable USB** using an elevated account. Verify byte readback, test both boot modes and test interrupted writes. Never test on the failed patient disk.
4. Use a USB dock that exposes an authoritative disk serial and SMART to test guided repair; on bridges that hide serial or SMART, treat the result as a *capability limitation*, not a reason to bypass identity validation.
5. Reproduce blocked Windows USB reads and inspect Windows event logs/controller status; a stalled synchronous kernel read cannot be guaranteed to cancel. The GUI must never claim repair complete without a final verification report.
