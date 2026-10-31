# Contributing

Thanks for helping improve DriveRepair.

## Scope

The supported product is the **desktop read-only scanner** (`desktop/`). Changes that add source-disk writes, silent device selection, or false “Healthy” / “Repaired” claims will be rejected.

Experimental Rust/firmware work belongs under `src/` and must remain fail-closed until independently tested.

## Development setup

### Desktop scanner

- Python 3.10+
- No third-party packages required for the scanner or unit tests

```bash
cd desktop
python3 -m unittest discover -s tests -v
```

### Rust library

- Recent stable Rust toolchain

```bash
cargo test --features "std,alloc" --lib
cargo clippy --features "std,alloc" --lib -- -D warnings
cargo fmt --check
```

## Pull requests

1. Keep changes focused and documented.
2. Add or update tests for behavior changes.
3. Do not re-enable USB wipe/provision scripts without a reviewed safety design.
4. Do not introduce competitor trademarks or proprietary reverse-engineering materials into the tree.
5. Update `CHANGELOG.md` and relevant docs when user-visible behavior changes.

## Code of conduct

Be respectful. Do not request or share dumps of proprietary binaries. Do not run experimental write paths against other people’s disks.
