# Architecture decision — product runtime

## Decision

Ship **DriveRepair Desktop**: a Python 3.10+ standard-library CLI that uses the host OS storage stack for discovery and read-only I/O.

Keep homemade BIOS/UEFI loaders and raw ATA/AHCI/NVMe driver prototypes in-tree as **experimental / unshipped**.

## Why

1. Host OS drivers already handle USB bridges, NVMe, and permissions better than unfinished custom stacks.
2. Read-only diagnostics can be delivered without a reboot workflow.
3. Fail-closed Rust stubs prevent false-success “repair” APIs from shipping by accident.
4. Imaging/rescue can later wrap mature tools (with clear licensing) instead of inventing unverified write paths.

## Consequences

- Public docs market the desktop scanner, not firmware repair.
- USB provisioning scripts remain hard-disabled until identity + artifact preflight exists.
- Competitive marketing claims are out of scope for this architecture.
