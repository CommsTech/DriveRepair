# DriveRepair — engineering status and release gates

## Available now (experimental)

A read-only host OS scanner is available in `desktop/`. It can enumerate external whole disks and scan them without restarting the computer. Results indicate whether the OS returned the requested bytes, **not** whether those bytes are semantically correct or sectors were repaired. Only simulated-file tests and fixture-based device discovery were executed in this review environment.

## Not yet implemented or not proven

- Device health logs (SMART/NVMe), automatic rescue imaging, recovery mapfile and verified data reconstruction.
- Native host graphics, installable packages or signed distributions.
- Hardware-tested macOS/Windows raw physical reads, OS-specific privilege workflows and USB-controller variations.
- Certified BIOS/UEFI recovery workflow and independently verified low-level Rust hardware drivers.
- Real failing-drive reproducible benchmarks, independent release/security review.

## Required before public beta

1. Test Windows 10/11, macOS Intel/Apple Silicon and Linux on sacrificial **external** USB HDD/SSD/flash disks. Capture exact OS, privileges, bus/bridge, logical sector size and read behavior.
2. Verify that the host OS scan opens raw devices with **read-only** privileges and never sends a write, discard, erase or device-repair command.
3. Test unplug/replug (same and different drive), access failures, corrupt responses, non-512 logical sectors, filesystem activity and long latency.
4. Demonstrate sample mode clearly indicates partial coverage; do not equate read success with media health.
5. Boot-media creation scripts are hard-disabled (exit 2) pending safety gates. Do not re-enable without identity challenge + artifact preflight review.
6. Use standard safe recovery/imaging tools for actual rescue until the project provides independently validated equivalent safety.

Release state: **PRIVATE TEST ONLY.**
