# Wayfinder map — DriveRepair way-forward to v0.4.0

_label: wayfinder:map_

## Destination

(Locked by owner, 2026-11-21, in [Audience & destination lock](issues/01-audience-and-destination-lock.md).)
DriveRepair becomes a public HDD restore/recover/repair tool for technical AND non-technical users, in the category of SpinRite, Victoria, and similar HD repair tools. First milestone: ONE OS — Windows — working properly end-to-end: disk check (works today) plus repair that actually runs, a bootable ISO that boots, automatic dependency install on launch, and a professional UI that graphically displays the technical work. Then broaden to macOS/Linux (end state: all OSes). Releases: Gitea, mirrored to GitHub.

## Notes

- Domain: cross-platform drive diagnostics/rescue (Python ≥3.10, Qt GUI, writes fail closed; SpinRite/Victoria comparators).
- Primary remote: `https://git.commsnet.org/commstech/DriveRepair.git` (Gitea, current tip `7cd03b2`). Gitea API unavailable to agents → this map uses the local-markdown tracker in-repo.
- Skills every session: `engineering-workflow` (grilling, `references/grilling.md`), `codecraft-pro` gate before any landing.
- Standing preferences: never bypass safety gates; tests must assert behavior, not line existence; cross-OS truth is proven by running suites on the Windows node (Alienware17R3) and macOS node (Melissa's iMac), not by assumption.
- Bookkeeping: research subagents resolve their own ticket files; the charting session appends Decisions-so-far pointers when they report. No two agents edit `map.md` at once.

## Decisions so far

- [Audience & destination lock](issues/01-audience-and-destination-lock.md): public OSS for technical + non-technical users; Windows end-to-end first, then all OSes; scan-only-works and broken repair/ISO/UI named honestly.
- [Distribution mechanism research](issues/02-distribution-mechanism-research.md): PyPI console-script + pipx/uv fast path; per-OS consent-gated launcher extending `setup_host_environment.py` (verified report-only, editable-install only, Windows/winget-only today); no PyInstaller binaries (Defender false positives).
- [Pick distribution & release channels](issues/03-pick-distribution-and-channels.md): user launches the app and dependencies install automatically (consent-gated); Gitea releases primary, GitHub mirror.
- [Quality bar & scope cut](issues/04-quality-bar-and-scope-cut.md): behavioral-test audit, dead-code/TODO zero, independent review, CI-enforced formatting; one OS at a time, others pause first.

## Not yet specified

- Code-signing / Windows Smartscreen & macOS Gatekeeper story for distributed artifacts.
- Version policy and changelog discipline for releases.
- CI auto-publish pipeline on tagged releases (Gitea Actions → Gitea release → GitHub mirror).
- Block-map/SMART-gauge graphics technology choice for the new UI (hangs off ticket 09).
- README / first-run experience rewrite once the one-launch install path exists.

## Out of scope

- Household PhysicalDrive3 elevated SMART/validation work (ops track, not this effort).
- Native macOS USB write support — paused by owner preference pending the distribution decision (flagged as `task_bfdd842f`).
