**0.3.3b10 ENGINEERING CANDIDATE: PRIVATE TESTS ONLY.** Qt progress/map accuracy, >=10% Quick Check, native Windows read-only inspect, durable journal option. Physical write qualification remains open. See `docs/QT_UI_AND_HARDWARE_RELIABILITY_B10.md`.

# Status — 2026-11-02

PRIVATE TEST — **0.3.3b10** Qt accuracy + recovery continuity; Seagate ST1000LM048 = **SMR**.

## Product

- Version `0.3.3b10`: truthful Quick Scan % and byte-accurate surface map cells; Quick Check/Repair plan >=10% unique coverage; recent vs average speed + ETA; Drive Details / `inspect-storage` (Win32 read-only, not write auth); Fix/Recover/Check goal filters; durable journal option + resume modes
- Read-only firmware_inspect Rust trait (hints only — no vendor command transmitters)
- Admin Qt debug: `DRIVEREPAIR_GUI_DEBUG=1`

## Seagate ST1000LM048 1 TB (USB / SMR)

| Step | State |
|------|--------|
| Prior ~20% scan + USB disconnect | Identity recheck blocked writes (correct) |
| Get-Disk hangs | Use Drive Details / native inspect; PowerShell write-path still gated |
| Resume / durable journal validation | Pending sacrificial hardware |
| Public release | **Blocked** |

Lab: `D:\DriveRepairLab\seagate_st1000lm048_wipe_refresh_20261101\`
Artifacts: `docs/releases/0.3.3b10/`
