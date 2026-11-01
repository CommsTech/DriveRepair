# Scheduled read-only drive monitoring

**Monitoring does not authorize automatic refresh, remapping, or writing.** Rewriting suspect sectors without a protected original copy can erase the only recoverable bytes.

```sh
python3 -m driverepair_desktop list --json
# Use the device ID and current 12-hex identity_hint displayed above.
python3 -m driverepair_desktop monitor-external \
  --device linux:/dev/sdX --expect-fingerprint 12HEXCHARS \
  --state /healthy-disk/driverepair-monitor.json --json
# Optional, only during idle time, and with explicit acknowledgement:
python3 -m driverepair_desktop monitor-external \
  --device linux:/dev/sdX --expect-fingerprint 12HEXCHARS \
  --state /healthy-disk/driverepair-monitor.json --triage --ack-read-stress --json
```

Run from your OS scheduler (Task Scheduler, launchd or systemd timer) as a dedicated least-privilege user with the minimum read permissions required. Choose a low-frequency interval (for example weekly SMART trend checks, with sampled reads less often only if needed). Never embed administrator passwords in scheduled command lines.

**USB docks:** the OS device number may change on reconnect. Identity mismatch must fail closed; create a new monitor job only after visibly verifying model/size/serial/location. The monitor history is on healthy separate storage. SMART via USB may be unavailable or misleading; status `unknown` is not a pass.

Alerts: health counters 5, 187, 197, 198 and NVMe media errors/critical warnings changing; sampled read errors; slow areas that should be retested under controlled conditions; device disappearance. An individual SMART counter is not a universally calibrated failure predictor. Temperature, caching, competing workloads and USB bridge behavior skew speed measurements.

**Never schedule `refresh-external`, erasure, firmware flashing, filesystem repair, or direct writes automatically.** Schedule warnings, not irreversible corrective action.
