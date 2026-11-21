# Wayfinder map — DriveRepair way-forward to v0.4.0

_label: wayfinder:map_

## Destination

(DRAFT — locked by ticket [Audience & destination lock](issues/01-audience-and-destination-lock.md).)
DriveRepair v0.4.0: a new user on Windows, macOS, or Linux goes from clone/download to a correct, read-only diagnostic run in one command; a release artifact is published; the adoption-quality bar holds — no dead code, no stray TODOs, tests validate behavior, independent agent review passes.

## Notes

- Domain: cross-platform drive diagnostics/rescue (Python ≥3.10, optional Qt GUI, writes fail closed).
- Primary remote: `https://git.commsnet.org/commstech/DriveRepair.git` (Gitea, current tip `7cd03b2`). Gitea API unavailable to agents → this map uses the local-markdown tracker in-repo.
- Skills every session: `engineering-workflow` (grilling, `references/grilling.md`), `codecraft-pro` gate before any landing.
- Standing preferences: never bypass safety gates; tests must assert behavior, not line existence; cross-OS truth is proven by running suites on the Windows node (Alienware17R3) and macOS node (Melissa's iMac), not by assumption.
- Bookkeeping: research subagents resolve their own ticket files; the charting session appends Decisions-so-far pointers when they report. No two agents edit `map.md` at once.

## Decisions so far

- (none yet)

## Not yet specified

- Code-signing / macOS Gatekeeper notarization story for distributed binaries.
- Version policy and changelog discipline for releases.
- CI auto-publish pipeline on tagged releases (Gitea Actions → release artifacts / PyPI).
- Whether the Qt GUI ships in the default install or as an optional extra.
- README / first-run experience rewrite once the install path exists.
- GitHub mirror and release channel auth (owner input required).

## Out of scope

- Household PhysicalDrive3 elevated SMART/validation work (ops track, not this effort).
- Native macOS USB write support — paused by owner preference pending the distribution decision (flagged as `task_bfdd842f`).
