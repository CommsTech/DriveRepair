# Journal-backed rescue progress and Windows lab safety

**Status:** 0.3.3b2 experimental hotfix. No authorization to write patient media.

## Why an image can look full before rescue finishes

A rescue image may be created as a *sparse/preallocated regular file* with its entire final **logical length**. Windows Explorer's **Size** can show the drive's full capacity while only a small fraction has been copied. **Size on disk** may be different and grows as real sectors are written. Neither value independently establishes recovery progress or byte correctness.

DriveRepair's committed `IMAGE.rescue.json` state is authoritative for rescue progress. The state is updated only after output writes are flushed and committed; a crash may cause one bounded chunk to be reread. The map can still be incomplete or untrusted if the source/device is wrong, the map has been externally modified, or the underlying destination storage lies. It does **not** verify original file-level checksums.

## Check progress safely, without attaching a device

From `desktop/`:

```powershell
python -m driverepair_desktop rescue-status --output 'D:\Recovery\patient.img' --json
```

Interpret the results:

- `cursor_bytes` and `percent_processed`: first-pass processing position, not proof of good sectors.
- `recovered_bytes`: bytes received from OS reads and committed to the output.
- `unreadable_bytes`: areas read attempts could not currently obtain.
- `unprocessed_bytes`: areas not reached by the first pass.
- `first_pass_complete`: does **not** imply all data was copied.
- `clean_rescue_complete`: the durable map says the full first pass completed without missing bytes, and is marked `completed`; does **not** prove that files were free of silent corruption.

Exit code `0` means `clean_rescue_complete=true`; exit code `2` means incomplete/unclean or an error. These status semantics intentionally differ from the initial rescue command, whose partial-result code can be treated as a soft outcome.

A tiny `IMAGE.rescue.lock` sidecar records the OS-level recovery lock target. Its presence alone does not mean a stale job; the kernel automatically releases the lock on process exit. Do not run old DriveRepair versions against the same image in parallel.

Keep the `.rescue.json` sidecar with its image. **Never delete the image, map, or sole surviving copies to recover disk space while a rescue is underway.**

## Resume correctly

1. Stop or finish the existing DriveRepair job before starting another; never run two writers against the same output/map.
2. Inspect `rescue-status` and device identity. Do not infer progress from the image length.
3. For an incomplete first pass, use the **Rescue > Resume** GUI action or `rescue-external --resume` with the **same drive, output, chunk size and identity**.
4. After the full first pass, use **Retry gaps** only if the map reports missing regions. Retrying may stress a failing drive.
5. Validate recovered file content on a *copy* before treating the result as a verified backup.

For the Windows lab, `resume_samsung_rescue_then_continue.ps1` now **requires** the operator to name the patient and destination explicitly and will refuse to run if an existing DriveRepair recovery process is detected. It displays PowerShell progress based on structured CLI events instead of streaming raw `RESCUE cursor=...` text.

The `watch_and_continue_samsung_lab.ps1` filename is retained for compatibility, but it is now **read-only status monitoring**. It will not resume, repair, refresh, or delete anything automatically. `run_elevated_samsung_pm841_lab.ps1` also requires explicit inputs and no longer invokes in-place refresh.

Example (after separately verifying the disk's identity and destination):

```powershell
.\scripts\watch_and_continue_samsung_lab.ps1 -LabRoot 'D:\RecoveryLab' -Once
# For explicit manual resume, use an administrator PowerShell:
.\scripts\resume_samsung_rescue_then_continue.ps1 -Device 'windows:PhysicalDrive2' -LabRoot 'D:\RecoveryLab'
```

The `PhysicalDrive2` string above is an **example only**, not an identification method. Device numbers can change when USB docks reconnect. Confirm the target model, capacity, serial/fingerprint and bus every time.

## Why old logs still print raw RESCUE lines

The current CLI contains the compact dashboard and JSONL progress protocol. A pre-existing Python process, older wheel, cloned workspace, or old PowerShell test script can still produce `RESCUE cursor=...`. Verify the installed module location:

```powershell
python -c "import driverepair_desktop.cli as cli; print(cli.__file__)"
```

Launch the **new graphical interface** for normal operation:

```powershell
python -m driverepair_desktop gui
```

A brief cursor repeat after restarting may be normal: the last flushed data block could have been written before its final recovery-map transaction. Only the durable map inspection can show what has been committed. Repeatedly decreasing committed `cursor_bytes` across consecutive reads of the *same journal* is abnormal and should halt further activity.

## No chained destructive maintenance

The lab scripts intentionally **do not call `refresh-external` or any patient-writing command**. Recovery is read-only against the patient and writes only to a separate destination image. In-place maintenance/rejuvenation is a completely separate, explicitly authorized workflow with risks that a rolling journal or UPS does not eliminate. **Never make refresh an automatic next step after imaging, especially if any sectors were unreadable.**

## Validation limits

The Python status command and synthetic disk/image tests were run on Linux. Windows PowerShell behavior and live-drive operations were not executed in this environment. Carry out syntax checks and offline end-to-end tests on Windows before using the updated lab scripts. Native BIOS/UEFI boot testing and real USB hardware interruption tests remain outstanding.
