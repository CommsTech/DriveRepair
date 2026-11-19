# DriveRepair manufacturer model catalog

DriveRepair ships an **offline, curated, source-attributed** database at `desktop/driverepair_desktop/data/drive_models.json`. Schema version 1 currently covers **four records**: three Seagate SMR part numbers and SanDisk Ultra 3D SSD model family. It is **not** comprehensive, does not phone home and does not update itself.

## Evidence acquisition and safety

1. Manufacturer specification or datasheet provides **nominal model properties** (SMR/CMR, device class, rated RPM and marketed capacity). Every catalog record retains its manufacturer source URL.
2. Device discovery and direct OS protocol queries attempt to collect **live identity and capabilities**. SMART/ATA/SAT/NVMe logs, when available, provide per-device health observations. The USB bridge may hide or alter this information.
3. Scan/recovery readings supply **observed errors, latency, repeatability and recovered bytes**. These must never be confused with model specifications.
4. Catalog matching selects conservative **read strategy** only. A model match or recording-technology label is *not* an authorization to write a physical disk. Live identity confirmation, health/risk assessment, exclusive access, durable journal and explicit consent remain independent requirements.

### Updating the catalog

Contributions must include exact OEM model and variant matching rules, source URL, source date/revision if known, evidence scope and regression tests. Reject unverifiable crowdsourced recording claims and broad family extrapolation. Update records by reviewed release changes; never silently download internet data or treat the smartmontools `drivedb.h` SMART decoding presets as a manufacturer-verified recording-technology catalog.

The catalog is stored as JSON within the application package, works offline and is included in both `.pyz` channels and the Python wheel.
