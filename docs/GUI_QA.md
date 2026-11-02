# GUI acceptance and safety testing — 0.3.3b3

## Scope

This release fixes the unresponsive guided workflow buttons seen in the uploaded
Windows screenshot. This is a **desktop GUI hotfix**, not validation that a
physical drive or firmware can be safely repaired. The source image of the GUI
is the operator's report; actual fault reproduction used the uploaded source.

### Root cause and correction

`workflow_tab()` inserts a `container` into the `ttk.Notebook`, then inserts a
`page` inside a scrolling Tk Canvas. The former Start Here callbacks passed the
**page** to `notebook.select`, which Tk rejects because the page is not a direct
Notebook child: `_tkinter.TclError: ... is not managed by ...`.

Workflow choices now use stable names mapped to the registered Notebook
**containers**. All seven controls are invoked by tests on a real Tk window.
A global Tk callback exception handler also exposes unexpected failures in the
UI and Advanced log rather than only in an unseen console.

### Other confirmed issues corrected

- Empty progress cards and sector map crowded nearly all choices off a
  laptop-sized initial window. The dashboard now starts collapsed and is
  shown when recovery starts or when explicitly toggled.
- GUI child processes ran `python -m driverepair_desktop` even when the user
  opened a portable `.pyz`, where that module need not be installed. Portable
  jobs now reenter the same `.pyz` archive.
- Live external rescue was Linux-only in the GUI even though the CLI has
  guarded Windows raw-device support. The Windows action is exposed but **not
  hardware-qualified**; it retains read-only opening, destination isolation,
  permission checks and user risk confirmation.
- Child progress streams are explicitly UTF-8 and subprocess pipes are closed
  when their reader threads finish.
- The GUI cancels its scheduled event-loop polling on normal window close.
- Build script ZIPAPP version is aligned with desktop package version.

## Automated tests

Run from repository root:

```bash
# Tests of CLI, recovery-map integrity, synthetic images and mocked device access
cd desktop
python -m unittest discover -s tests -v

# On Linux with tkinter and Xvfb installed, test actual GUI widgets:
xvfb-run -a python -m unittest discover -s tests -p test_gui_workflows.py -v
cd ..

# Build PYZ and wheel from exact source (requires Python build tooling)
python scripts/build_desktop.py

# Verify child recovery from a portable GUI archive, on Linux with Xvfb:
cd desktop
DRIVEREPAIR_SMOKE_PYZ=../dist/DriveRepair-0.3.3b3.pyz \
  xvfb-run -a python -m unittest discover -s tests -p test_gui_workflows.py -v
```

All tests use synthetic regular files and stub out external disk enumeration.
They must not be used as evidence of validated physical disk repair.

## Windows manual QA (required before public beta)

On a nonproduction Windows computer (with a disposable USB drive):

1. Install Python 3.10+ including Tk, then run `python DriveRepair-0.3.3b3.pyz gui`.
2. Verify all seven **Start here** choices navigate to the matching tab; no
   silent exceptions. Try the actual tabs along the top as well.
3. Choose **My external drive is slow or failing**. Click **Refresh inventory**,
   verify displayed model, capacity, bus, masked serial and identity hint.
   Select the disposable disk row, then try **SMART** and **Quick scan**.
4. Without selecting a disk, Quick scan must return a clear input error.
5. Save a small synthetic image to local storage. Use **Image recovery** →
   **Rescue** with a different destination image. Confirm SHA-256 equality.
6. Test **Resume**, **Advanced details**, dashboard toggle, **Stop job**, and
   **Save report** with disposable synthetic images. Deliberately exercise
   invalid paths and low destination capacity.
7. Use an administrator-launched test instance before attempting a read-only
   live-device rescue, and verify source/destination physical-disk isolation.
   **No in-place refresh or repair on valuable disks.**
8. Test both a Python wheel installation and a portable PYZ invocation. No
   unrelated package install should be required for portable CLI imaging.

## macOS and Linux manual QA (required before public beta)

- macOS: verify Tk available, navigation, image rescue, disk inventory, SMART
  where supported; live raw disk rescue remains unsupported by this GUI.
- Linux: verify normal GUI, disk discovery, filesystem source restrictions,
  image rescue to a separate mounted target, and proper non-root input errors.
- On all platforms check 960×700 and 1180×820 windows, scroll behavior,
  keyboard navigation, readable buttons, Stop placement and error handling.

## Beta release limitations

- BIOS/UEFI booting, Rust recovery-core native build, Windows/macOS physical
  drive recovery, and in-place rewrite behavior are **not established** by
  these Tk tests.
- A successful OS read does not prove original data integrity.
- A clicked "Recover" button begins a job only once a device or image and a
  safe destination are selected; selecting a goal on Start Here only navigates
  to that workflow.
- Any public-benchmark superiority claim requires controlled, independent
  comparisons on sacrificial drives and fault-injected imaging workloads.
