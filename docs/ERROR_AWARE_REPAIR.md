# Quick / Full Repair when read errors occur (0.3.3b5)

**Purpose:** A scan that discovers bad sectors must not hide them or declare the disk fully repaired. An isolated media read error should not automatically disqualify every *other* repeatably readable sector from optional media refresh.

**Workflows:** In **Diagnose / Rescue**, choose a disk by model, capacity, and identity fingerprint, then choose **Quick repair** (sampled) or **Full repair** (sequential). The **Balanced** policy will investigate known read-error offsets with a strict read budget, split failed reads down toward the logical sector size, and require two identical reads before considering a region as a potential write candidate. The journaled writer then independently rereads/compares bytes, rewrites the same region, flushes and verifies readback. **Preserve** policy excludes previously error-bearing regions entirely and handles only safely readable slow regions.

**If the scanner reaches its error limit:** The scan stops further surface coverage to avoid unbounded stress. Balanced investigation is limited to already identified error locations, not unvisited disk areas. If some bytes can be read repeatably, those subregions can be refreshed. The result is always **PARTIAL** because the rest of the drive was not inspected. Do not mistake status 2 or a readback match for whole-drive health or restored file integrity.

**If bytes remain unreadable, fluctuate between reads, or cannot be attributed to a stable sector:** They remain **UNKNOWN** and are not overwritten. The GUI explains the next step (image rescue, hardware stabilization or a separate explicitly destructive sector reinitialization workflow). DriveRepair currently does **not** implement destructive reinitialization of unknown bytes on physical hardware.

**Write blockers remain:** sudden USB disconnect, access errors, changed device identity, mounted/in-use patient, actual critical SMART failure, thermal danger, or error locations that cannot be safely isolated. A SMART media warning or unavailable SMART data requires additional explicit risk consent. Lack of a backup makes the operation riskier; volatile RAM-only journaling offers no crash recovery.

**Correctness:** Two equal reads do not establish the original file contents were correct; a rewrite/readback match does not prove physical lifetime has been restored. Where a trustworthy checksum or redundant original exists, compare against it. Report **recovered bytes**, **readback-verified rewritten bytes**, **unreadable bytes** and **unscanned bytes** separately. Never color unscanned media as healthy.

**Testing:** Run `python -m unittest discover -s tests -v` from `desktop`, plus GUI testing on Tk/Xvfb or a real Windows workstation. All additions are tested with synthetic images/mock devices only. Do not run in-place repair on the sole copy of irreplaceable data; this release is not hardware qualified.
