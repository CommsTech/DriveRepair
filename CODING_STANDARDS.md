# DriveRepair reviewer standards (judgment-based)

The reviewer reads this file **after implementation** and inspects the diff;
implementation agents should start from the short `AGENTS.md` instead.
Mechanical version, packaging, lint, syntax, and test checks belong in CI.

1. **Truthful outcomes:** A successful command, sample read, SMART response,
   byte comparison, and verified file recovery are distinct outcomes. UI text,
   progress, confidence, metrics, and release notes must name the evidence they
   actually possess. A high score is not a survival percentage.
2. **Platform consistency:** Compare a new operator path across Qt, CLI,
   engine, and boot/live workstation. A hidden fallback must never substitute
   filesystem repair for an explicitly selected HDD method or vice versa.
3. **Safety and reversibility:** On-device writes require identity, eligible
   physical medium, authorization, exclusive access, separate durable journal,
   cancellation behavior, and independent postwrite evidence. UI gating is
   never sufficient. SSD/NVMe/flash never enter generic magnetic rewrite.
4. **Hardware-specific uncertainty:** Model names and uncalibrated vendor
   SMART raw values may drive caution, not quantified reliability claims or
   write authorization. Bridge limitations must be distinguished from parser
   failures, permissions errors, and actual disk defects.
5. **Agent handoff evidence:** If a test needs Windows, actual BIOS/UEFI VMs,
   sacrificial hardware, or a real HP laptop, mark NOT_PROVEN until it runs.
   Verify source revision/ISO hash and preserve evidence; review any new risk
   to family photos and user drives before a public claim.

Historical references live in docs/; active release pointers are
`status.md` and `docs/RELEASE_STATUS.md` (checked by CI).
