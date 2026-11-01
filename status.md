# Status — 2026-11-01

PRIVATE TEST ONLY — **0.2.4** live Adaptive Refresh UX + hybrid journal.

## UX / engine

- Live stderr dashboard (TTY full panel; redirected logs use line-mode so probes never look stalled)
- Health indicators: media / transport / mechanical* (latency proxy — no acoustic mic on USB docks)
- `--auto-escalate` deeper sub-probes on slow/failed zones
- `--journal-backend hybrid` (default): region bytes in RAM; `--after-run keep|delete|ask`

## Latest 12 TB USB live notes

- Elevated Adaptive runs succeed (sampled regions rewritten+verified)
- Non-admin still correctly refused with Administrator guidance
- Journal delete-after-run verified on live pass
