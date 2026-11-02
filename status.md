**0.3.3b9 ENGINEERING PREVIEW: PRIVATE TESTS ONLY.** Optional Qt workstation, read-only scan checkpoint/resume, rolling recent-window speed. Physical write qualification remains open. See `docs/QT_WORKSTATION_AND_SCAN_RESUME.md`.

# Status — 2026-11-02

PRIVATE TEST — **0.3.3b9** Qt workstation + interrupted-scan resume; Seagate ST1000LM048 remains **SMR** sacrificial gate.

## Product

- Version `0.3.3b9`: default `gui` prefers PySide6 when installed; `gui-legacy` keeps Tk; `--resume-scan` / scan checkpoints (offsets only, identity-checked)
- Rolling recent-window `speed_bps` (+ `average_speed_bps`); WinError 433 (device gone) vs 1117 (I/O)
- Prior evidence: ~20% adaptive full scan then USB disappear / `repair_blocked_identity_recheck` — correct no-write outcome
- Admin debug: `DRIVEREPAIR_GUI_DEBUG=1` mirrors Tk and Qt logs under DriveRepairLab

## Seagate ST1000LM048 1 TB (USB / SMR)

| Step | State |
|------|--------|
| Adaptive full scan | Partial (~20%); disconnect/timeouts observed |
| Resume after reconnect | Ready to validate with `--resume-scan` / Qt Resume |
| Public release | **Blocked** |

Lab: `D:\DriveRepairLab\seagate_st1000lm048_wipe_refresh_20261101\`
Artifacts: `docs/releases/0.3.3b9/`
