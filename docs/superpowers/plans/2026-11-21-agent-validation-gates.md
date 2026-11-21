# DriveRepair agent validation gates implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Make real-hardware verification, firmware boot tests, Windows GUI behavior, source provenance, and agent handoffs visibly separate from synthetic successes.

**Architecture:** Reuse existing Python unittest/pytest and Gitea pipelines. Add opt-in Windows and Linux QEMU qualification workflows without breaking the currently supported Ubuntu CI runner. Keep patient-disk operations disabled in all automated tests; an explicit evidence gate prevents promoting an unverified release.

**Tech Stack:** Python 3.11, shell, PowerShell, PySide6, Gitea Actions, QEMU/OVMF (only on qualified runners).

**Spec:** 2026-11-21 DriveRepair retrospective, plus `docs/QA_2026-11-20_HP_BOOT_WINDOWS_DOCK.md` and `docs/release-readiness/TEST_EVIDENCE.md`.

## Global constraints

- Never use a physical block-device target in automated CI tests.
- No missing runner/tool result can be reported as PASS.
- Keep SSD/NVMe/HDD write authorization independent of UI navigation and diagnostic scores.
- Preserve current Ubuntu CI jobs; native Windows runner qualification is explicit/opt-in until a runner exists.
- ISO build and structural validation do not equal a successful boot.

## Review focus

- UEFI menu differs from BIOS: both menus must be installed and independently booted.
- Failed QEMU boot / missing OVMF: gate reports FAIL or NOT_PROVEN, never PASS.
- SSD selected in repair UI: HDD method remains blocked, no fallback CHKDSK starts.
- Unidentified Windows USB bridge: read-only diagnostic evidence remains distinct from write permit.
- Unqualified release metadata: promotion requires matching SHA, source revision and independent evidence.

### Task 1: Release hygiene and packaging

- [ ] Write failing tests for version mismatch and stale README examples.
- [ ] Add `scripts/check_release_hygiene.py`, correct active status/docs, extend pre-push and CI checks.
- [ ] Add archive manifest/source cleanliness check reusing `create_clean_source_archive.py`.

### Task 2: ISO BIOS/UEFI boot verification

- [ ] Write failing tests for paired bootloader source and QEMU command safety.
- [ ] Configure both GRUB BIOS/EFI menu sources; add a VM-only live readiness marker.
- [ ] Add real QEMU/OVMF BIOS+UEFI runner and opt-in qualification workflow.

### Task 3: Windows UI and hardware evidence

- [ ] Add Qt (real widget) SSD/HDD route tests for Windows and non-Windows hosts.
- [ ] Add opt-in native Windows CI workflow (requires Windows runner).
- [ ] Add read-only, sanitized smartctl USB bridge probe for QA and tests.

### Task 4: Score calibration, release promotion, agent navigation

- [ ] Write tests forbidding unknown vendor ATA raw counter 187 from imposing unsupported numerical penalties.
- [ ] Correct score and explanations while preserving independent hard media gates.
- [ ] Add promotion evidence gate with named mandatory categories and SHA/commit binding; test rejection paths.
- [ ] Add short `AGENTS.md`, `CODING_STANDARDS.md`, and documented runner/how-to instructions.

### Task 5: Verification and delivery

- [ ] Run full Python suite and available shell/static tests; report missing platform checks accurately.
- [ ] Create clean reproducible source ZIP and `git diff --binary` patch from the supplied archive.
- [ ] Validate patch with `git apply --check`, archive manifest, SHA256, and independent source extraction tests.
