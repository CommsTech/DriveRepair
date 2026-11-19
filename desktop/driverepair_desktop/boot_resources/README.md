# DriveRepair live USB build kit

This ZIP contains the **source and build recipe** for an experimental Debian live ISO. It is **not** a bootable disk image and must not be flashed as if it were an ISO.

## Build on a prepared Debian x86-64 host

```bash
sudo apt install live-build debootstrap xorriso
sudo bash scripts/build_live_iso.sh /path/to/empty-output
bash scripts/check_live_iso.sh /path/to/empty-output/*.iso
```

This produces an experimental hybrid ISO. `check_live_iso.sh` now rejects marker-only/placeholder images without the live kernel, initramfs, squashfs, BIOS and UEFI boot-catalog entries. Validate its provenance and ability to boot BIOS/UEFI in a disposable VM and on sacrificial USB hardware before distributing it. The desktop **Create recovery USB** wizard then flashes an already-built ISO to a chosen disposable USB disk; it *permanently destroys* that disk's contents. Never select a patient disk. Written ISO byte verification is not BIOS/UEFI boot certification.

After booting a trusted recovery OS, use read-only rescue to image failing drives onto separate healthy storage. A disk's failure to pass SMART, connect reliably, or return sector data is not fixed by booting a live environment.

For complete instructions and limitations see `docs/BOOT_RECOVERY.md` and the main DriveRepair repository README.
