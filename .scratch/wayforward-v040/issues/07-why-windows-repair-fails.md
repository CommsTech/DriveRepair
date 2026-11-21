# Why Windows repair fails

Type: research
Status: open
Blocked by: —

## Question

Owner reports repair fails to run on a Windows computer (disk check works). Existing evidence: a non-elevated preflight got `WinError 5` and failed closed; the elevated path has never been validated. Determine what actually breaks: (1) audit the repair entry path end-to-end for Windows (privilege check, elevation/self-relaunch behavior, SMART gating `smart_passed_limited` — repair is gated on OS health plus limited-pass SMART, and without smartctl on this host that gate may always refuse); (2) reproduce on the Windows node (Alienware17R3) via the paired-windows-node-exec skill, read-only first; (3) classify every failure mode as privilege-only, dependency-only (missing smartctl/evidence), or code defect; (4) propose the smallest fix or flow change per mode. Elevated interactive runs remain owner-gated; the researcher may not bypass any safety gate.
