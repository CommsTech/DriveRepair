# DriveRepair repeatable comparison protocol

## Competitor and technique baselines

- GNU ddrescue 1.30 (January 2026) implements copying, trimming, sweeping, scraping and retries; compare its restartable mapfile and recovery coverage, not merely raw MB/s: https://www.gnu.org/software/ddrescue/manual/ddrescue_manual.html
- The Sleuth Kit supports filesystem metadata inspection (`fls`/`icat`/`tsk_recover`). Measure selected-file restoration and correctness on NTFS/exFAT/ext/FAT with known originals: https://wiki.sleuthkit.org/TSK-Tool-Overview/
- Include a modern established imaging tool with direct AHCI/controller capability in a physical lab, if licensed and safe.
- NIST SP 800-88r2 (September 2025) is the relevant media sanitization program guidance; seven-pass rewriting alone is NOT a compliance certificate: https://csrc.nist.gov/pubs/sp/800/88/r2/final
- For hardware failure research, compare carefully with field SMART data, e.g. Backblaze (large production populations but not USB-dock/casual-user ground truth): https://www.backblaze.com/cloud-storage/resources/hard-drive-test-data

## Workloads

1. Clean verified reference images of various sizes, entropy, alignment and filesystems, including sparse synthetic >12TB virtual disks.
2. Controlled EIO, intermittent reads, slow reads, disconnect, short reads and destination-write failures (in virtual environments only).
3. FAT32 deleted contiguous vs fragmented; NTFS/exFAT/ext files with intact and overwritten metadata; ground-truth byte hashes for every file.
4. Real sacrificial HDDs and SSDs, including 512e/4Kn, USB bridges, CMR/SMR and different firmware versions, never personal/prod drives.
5. Power-cut and hot-unplug of sacrificial hardware during read and separate in-place-refresh runs. Require rollback evidence and inability to silently certify bad copies.
6. Cross-platform GUI interaction: selecting a drive by model/capacity/serial and selecting individual recoverable files with no wrong-disk action.

## Measures (per device, condition, and transport)

- **Accuracy:** bytes matching ground truth; file SHA-256 exact match; false positives, failed reads, unverifiable missing regions.
- **Safety:** writes to patient by workflow (zero for rescue); wrong-disk attempts, crash/power-loss journal integrity, unexpected identity changes.
- **Speed:** time to first useful copied file, time to 50%/95% verified data, throughput per phase, p95/p99 I/O latency, read amplification, memory use.
- **Resilience:** restart recovery after simulated/real disconnect, no false success, partial output clearly distinguished from valid data.
- **Usability:** human selection error rate, task completion rate and time, OS installation friction.

Repeat paired tests over equivalent initial media snapshots. Never run several destructive algorithms successively on the same already-changing faulty surface and declare the last winner. Distinguish performance from data-integrity results. Publish raw logs, versions, hardware, and negative results after privacy review. **No claim of faster, safer or higher recovery success until measured.**
