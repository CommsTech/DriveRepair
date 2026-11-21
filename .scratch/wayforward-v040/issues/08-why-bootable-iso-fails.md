# Why the bootable ISO fails

Type: research
Status: open
Blocked by: —

## Question

Owner reports the bootable ISO does not work. Audit `scripts/build_live_iso.sh`, `scripts/check_live_iso.sh`, `scripts/smoke_live_iso.py` and any ISO docs; rebuild the ISO in this worktree; verify its boot structure (El Torito/UEFI, bootloader, kernel/initramfs presence) as far as possible without hardware; identify breakage (build output validity, boot config, missing components, documentation-vs-reality drift); propose a fix plan with pass criteria (a rebuild passing the existing smoke/check scripts plus a documented hardware boot recipe). Read-only on the workspace; no host ISO media writes.
