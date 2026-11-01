# Recover a failed OS drive when the computer has only one internal disk

**Status: EXPERIMENTAL Linux live-mode imaging, not a production-certified restore workflow.**
No app can preserve a full disk image without separately available capacity. The
rescue USB hosts the operating environment, not the recovered image. If there is
no destination, recover priority files to a healthy smaller external drive or NAS,
not back onto the patient.

## Beginner workflow

1. Stop booting the failing operating system and do not run in-place refresh,
   operating-system repair or repeated full scans. Unusual noises/disconnects
   warrant professional assessment. A full-image rescue is often safer than
   repeated attempts to repair a failing disk.
2. On a separate healthy computer, create a **trusted, signature/checksum-verified
   Linux live USB**. The project also provides a Debian `live-build` recipe in
   `scripts/build_live_iso.sh`, but that recipe's output is **NOT certified to
   boot BIOS or UEFI** until both paths pass actual VM and physical boot tests.
3. Boot the broken computer using the live USB, not the installed OS. Make sure
   the patient disk is not mounted, encrypted-open, or used by RAID/LVM. Do not
   confuse the small boot USB with the internal target disk.
4. Provide **separate healthy destination space**: mount a verified NFS/CIFS/SSHFS
   NAS share, or connect a large enough second external disk. If using an image
   output, prefer a whole-file destination with enough free space. A filesystem
   showing 12 TB free may still have NAS quotas, network instability or limits.
5. Start DriveRepair in the live OS and select **Recover OS drive**. Confirm the
   target by *model + capacity + masked serial + bus + ID fingerprint*.
6. Run **Check destination**, then **Rescue to image**. Only begin if identity,
   source-idle state, storage ancestry and capacity checks succeed. The source is
   opened **read-only**; the output and journal go to healthy storage. A device
   disconnect, failed write, short read or insufficient space must stop the job.
7. If interrupted, **keep the output and `.rescue.json` journal** and resume with
   the same options once the source and destination are safe. Incomplete regions
   remain marked unknown. Do not call partial images verified.
8. Use the image as evidence; recover selected files from the image, repair a
   *new copy* of the filesystem, or restore the image to an appropriate
   replacement disk after verifying compatibility and required backup copies.

### CLI (Linux only, explicitly offline)

```sh
# On trusted live USB, after mounting a separate healthy NAS or USB destination:
driveRepair='python3 -m driverepair_desktop'
$driveRepair list-all-linux --json

# Copy the exact linux:/dev/... ID and identity_hint FROM THE NEW LIST.
# This is a dry-run: it NEVER touches or modifies the source disk.
$driveRepair plan-system-recovery --device linux:/dev/sdX \
  --expect-fingerprint 12HEXCHARS --output /mnt/healthy-storage/recovered.img --json

# Explicit live-boot confirmation and read stress acknowledgment.
$driveRepair rescue-system --device linux:/dev/sdX \
  --expect-fingerprint 12HEXCHARS --output /mnt/healthy-storage/recovered.img \
  --ack-risk --ack-offline-system --multi-pass --json

# To resume, recheck the ID and rerun with --resume; do not use --multi-pass
# while an interrupted retry pass already exists (use --retry-missing).
```

An internal disk is intentionally **not** shown in the ordinary `list` command;
`list-all-linux` is a separate expert mode. Internal-disk rescue is rejected if
Linux finds a mounted filesystem or an active kernel holder. It does not work on
Windows/macOS in this build. The output must be on a separately identified local
block device or a **recognized NFS, NFS4, CIFS/SMB or SSHFS mount**. Ambiguous
pseudo-filesystems, unmounted directories and tmpfs are rejected.

### What this does NOT establish

- That any BIOS/UEFI ISO has actually booted, or that a raw USB bridge will
  survive power loss/hot unplug.
- That a drive with a positive SMART result is healthy.
- That file contents are correct without an independent checksum/known-good copy.
- That `lsblk` is tamperproof: malicious firmware, compromised OS or duplicated
  bridge serials can still misidentify devices.
- That a network share is backed by a different physical failure domain; it is
  treated as separate host storage based on an explicitly recognized mount.

## Building the experimental DriveRepair Live ISO

On a **separate, trusted Debian trixie x86-64 build VM**:

```sh
sudo apt-get install live-build debootstrap
sudo ./scripts/build_live_iso.sh /path/to/new-build-output
# Structural check only:
./scripts/check_live_iso.sh /path/to/new-build-output/DriveRepair-Live-amd64-UNVERIFIED.iso
```

The script uses Debian live-build, an iso-hybrid image and both GRUB-PC and
GRUB-EFI bootloaders. It bundles Python/Tk, DriveRepair's desktop source,
smartmontools, ddrescue, The Sleuth Kit's testdisk package, and NAS mount tools.
It masks automatic `udisks2` mounting; destinations must be mounted manually.
It never writes a USB or disk. **The resulting ISO name contains UNVERIFIED
until BIOS, UEFI, NVMe/SATA/USB, Wi-Fi/network, mount-safety and crash/restore
hardware tests have passed.** Secure Boot is not independently established.
The old custom firmware loaders remain experimental.
