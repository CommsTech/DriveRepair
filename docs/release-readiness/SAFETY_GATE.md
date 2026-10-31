# Safety gate

## Desktop scanner (supported)

| Rule | Enforcement |
|---|---|
| Read-only source access | `O_RDONLY` / `GENERIC_READ` only |
| External whole disks by default | OS discovery filters (removable/external, whole disk, non-boot) |
| Exact device ID required | `scan` rejects bare paths not returned by `list` |
| Identity revalidation | Before and after scan |
| Full scan acknowledgement | `--ack-risk` required for `--mode full` |
| No repair language on success | Results describe readability / OS errors |

## Experimental Rust library

| Rule | Enforcement |
|---|---|
| Unimplemented I/O | `Err(Unsupported)` — never fake `Ok(())` |
| Default access | Read-only (`allow_writes: false`) |
| Empty SMART | `Unknown`, never `Healthy` |
| Successful read outcome | `ReadOk`, never `Repaired` |
| USB wipe scripts | Immediate `exit 2` |

## Mandatory invariant

**Zero intentional writes to the patient/source disk** on the supported desktop path.
