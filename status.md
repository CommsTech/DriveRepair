**0.3.3b13 ENGINEERING CANDIDATE: PRIVATE TESTS ONLY.** Not a public physical-repair release.

# Status — 2026-11-02

## Product tip

- Synced `main` to `f0de381` (MSR GUID exact-match + portable CI fixture fixes)
- Working branch `feature/issues-164-172-dock-preflight` addresses Gitea #164–#167, #170–#172
- OpenClaw memory gateway unreachable from this host (Qdrant/Ollama/Honcho timeouts) — will retry write after hardware matrix

## Lab

- Patients in USB dock: SanDisk PhysicalDrive2 (E: DRTEST500), Seagate PhysicalDrive3 ST1000LM048
- Journals: RAM-only for write tests
- Matrix script: `D:\DriveRepairLab\...\prelease_dual_drive_matrix.ps1` (fast busy-lock probe)

## Gate before macOS

1. Elevated dual-drive CLI matrix PASS
2. Admin Qt GUI list/job/stop/results on both drives
3. No leftover exclusive volume locks / no runaway Python after jobs
4. Push reviewed fixes; close forge issues with PR links
