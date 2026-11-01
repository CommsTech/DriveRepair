# Desktop scripts

Operator lab/PowerShell helpers for private USB-dock testing are **not** shipped in this repository.
Use the DriveRepair CLI / GUI directly:

```text
python -m driverepair_desktop list --json
python -m driverepair_desktop rescue-status --output IMAGE --json
python -m driverepair_desktop gui
```

Destructive refresh requires explicit CLI acknowledgements; do not automate patient writes from unchecked wrappers.
