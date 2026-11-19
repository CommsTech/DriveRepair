# The old bootloader-only ISO builder created images with no recovery OS.
# It is intentionally disabled: a firmware EFI binary is NOT a bootable rescue system.
Write-Error "Removed unsafe bootloader-only ISO workflow. Build a Debian DriveRepair live ISO with scripts/build_live_iso.sh on a Debian build host, then validate its contents and BIOS/UEFI boot."
exit 2
