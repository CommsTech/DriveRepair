# Status — 2026-11-01

PRIVATE TEST ONLY. DriveRepair **0.2.1** adds experimental gated in-place refresh.

- Unit tests expanded for media refresh (image path)
- `refresh-external` available after multi-ack; USB dock patients require `--ack-usb-bridge-risk`
- physical validation of refresh: NOT DONE
- does NOT claim wear reversal; unread sectors are skipped, not invented
- Rust boot environment: experimental, not verified
