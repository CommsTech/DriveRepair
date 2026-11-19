# Offline Windows SMART component

This directory is a deployment slot for `smartctl.exe` from the **upstream
smartmontools** project. DriveRepair includes read-only ATA/SAT/NVMe SMART
integration, but cannot manufacture missing controller passthrough capabilities.

To ship SMART as a standard part of a Windows release, obtain the authentic
smartmontools Windows executable from the official upstream release, verify the
publisher-signed archive, stage it using `scripts/vendor_smartctl.py`, and
include the companion `dist/tools/smartmontools` directory alongside the
DriveRepair `.pyz` launcher. The launcher checks SHA-256 on every discovery.

**A local SHA-256 file is an integrity check, not an upstream signature.**
Verify the original distribution independently and comply with smartmontools'
GPL source/license distribution obligations. No arbitrary code is fetched or
executed during DriveRepair's recovery or repair workflow.
