# DriveRepair USB capacity-integrity spot testing

## What it tests

A counterfeit or defective USB flash drive can advertise more addressable space than its controller can actually store. DriveRepair samples a set of locations distributed over the claimed address space, temporarily writes 4 KiB of unpredictable test data, reads it back and attempts to restore its original contents. The original 4 KiB is saved first in a durable transaction journal on **a separate, healthy physical disk**. The result distinguishes successful sampled verification, read failures, write failures, mismatches, unstable original reads and failed restoration.

The default is **144 sampled spots**. Additional CLI counts 72, 288 and 576 are available. By default the first and last 16 MiB are excluded to reduce risk to common disk metadata, **not** to guarantee file safety. The drive may lie about locations, remap addresses or alias different addresses to the same physical flash memory. A test that passes all samples cannot certify every byte or even a guaranteed minimum usable capacity; read-after-write from a counterfeit device can mislead.

## Critical safety limitation

**This is a destructive-risk test and should never be run on a data-recovery patient or any device containing irreplaceable data.** A malicious or broken controller can redirect a test write to an *untested* location, corrupting material the journal cannot identify or restore. The operating system, USB bridge, driver or power loss can also prevent restoration. A journal is a recovery aid, not an assurance that source data survives. A backup must be independently verified before using the test, even though the program attempts restoration. The public image-first beta disables this hardware test.

## Novice workflow

1. Select a disposable USB device with an independently verified backup; check the exact device fingerprint.
2. In the Qt workstation choose **Diagnose → Verify USB capacity**. Review the written risk explanation and type the target-specific confirmation.
3. Choose an empty journal location on a **different healthy physical disk**, and a new HTML report destination.
4. Start the test. Leave the USB connected and avoid writes from other applications. Stop is cooperative between locations, not an immediate cancellation of blocked kernel calls.
5. Open **View detailed report**. Green means a sampled region verified its temporary data and original restoration; red/orange indicates issues. Treat any abnormality as a reason not to trust the device.

## Technical and lab workflow

The `validate-image-capacity` command exercises the same engine on an existing disposable regular-file image. It changes and restores that **image**, never the contents of a physical patient device. Example:

```bash
python -m driverepair_desktop validate-image-capacity --image disposable.img --journal /another-disk/drive-test-journal --samples 144 --report-html /another-disk/drive-test.html --json
```

Guarded/engineering builds additionally expose `validate-usb-capacity` requiring a verified external USB selection, exact device fingerprint, `TEST <fingerprint>` confirmation, backup and data-loss acknowledgements, exclusive access and a durable journal on physically distinct storage. Run `--help` for the full set of flags. `--restore-only` exists for interrupted USB journal recovery and must match the device identity, size and sector geometry.

If restoration is not verified, **stop**. Preserve the journal and seek specialist help rather than re-running a test. Never format, initialize, or stress a device after a failed restore.

## Report interpretation

- **Declared capacity:** what the device advertises, not proven writable space.
- **Highest validated offset:** one sampled address only; not a contiguous validated range.
- **Observed read coverage:** measured *read* addresses; not a byte-integrity certificate.
- **Latency statistics:** small sampled operations with median, extrema, standard deviation and coefficient of variation, not full-drive speed or life expectancy.
- **Unvisited locations:** explicitly unknown.

This work was informed by the **level of evidence** in [GRC's ValiDrive Report](https://www.grc.com/validrive/the-report.htm) but uses DriveRepair's own workflows, visuals, terminology and cautious safety rules. It is not a claim of identical algorithms or certification.

## Legacy GUI disposition

The old Tk workstation contains specialist actions not yet fully present in Qt (e.g., deletion preview/recovery and several filesystem/clone operations). It remains until those actions are ported, tested and removed from any dependencies. Feature loss is not acceptable in a removal-only refactor.
