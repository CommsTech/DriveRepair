"""DriveRepair Recovery Workstation — modern, low-overhead desktop presentation.

Recovery I/O stays in the CLI engine. This GUI only renders throttled progress
events (~10 Hz max) and never opens patient devices itself. Cross-platform via
stdlib Tk (Windows / macOS / Linux). Visual language: industrial dark console —
not DOS blue, not marketing purple.
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path


# Industrial dark palette (high-contrast status colors, no purple/glow stack).
C = {
    "bg": "#0f1419",
    "panel": "#171d25",
    "panel2": "#1c2430",
    "border": "#2a3544",
    "text": "#e8eef5",
    "muted": "#8b9aab",
    "accent": "#3d8fd1",
    "ok": "#3fa76a",
    "warn": "#d4a017",
    "fail": "#d14949",
    "slow": "#c47a20",
    "pending": "#243041",
    "current": "#5eb0ef",
}


def launch() -> None:
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, simpledialog, ttk
    except ImportError as exc:
        raise RuntimeError("Tk is unavailable. Install the OS Python tkinter package") from exc

    try:
        root = tk.Tk()
    except tk.TclError as exc:
        raise RuntimeError("No desktop display available. Use the DriveRepair CLI instead") from exc

    root.title("DriveRepair Recovery Workstation")
    root.geometry("1180x820")
    root.minsize(960, 700)
    root.configure(bg=C["bg"])

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure(".", background=C["bg"], foreground=C["text"], fieldbackground=C["panel2"])
    style.configure("TFrame", background=C["bg"])
    style.configure("Card.TFrame", background=C["panel"])
    style.configure("TLabel", background=C["bg"], foreground=C["text"])
    style.configure("Muted.TLabel", background=C["bg"], foreground=C["muted"])
    style.configure("Card.TLabel", background=C["panel"], foreground=C["text"])
    style.configure("Title.TLabel", background=C["bg"], foreground=C["text"], font=("Segoe UI", 22, "bold"))
    style.configure("TButton", background=C["panel2"], foreground=C["text"], padding=6)
    style.map("TButton", background=[("active", C["border"])])
    style.configure("Accent.TButton", background=C["accent"], foreground="#061018")
    style.configure("TNotebook", background=C["bg"], borderwidth=0)
    style.configure("TNotebook.Tab", background=C["panel2"], foreground=C["muted"], padding=(14, 8))
    style.map("TNotebook.Tab", background=[("selected", C["panel"])], foreground=[("selected", C["text"])])
    style.configure("Treeview", background=C["panel2"], fieldbackground=C["panel2"],
                    foreground=C["text"], borderwidth=0, rowheight=26)
    style.configure("Treeview.Heading", background=C["panel"], foreground=C["muted"])
    style.configure("Horizontal.TProgressbar", troughcolor=C["panel2"], background=C["accent"])

    q: queue.Queue[tuple[str, object]] = queue.Queue()
    process: subprocess.Popen[str] | None = None
    busy = False
    map_width, map_height = 64, 18
    map_cells = ["."] * (map_width * map_height)
    map_dirty = True
    last_map_draw = 0.0
    stats = {
        "phase": "IDLE",
        "pct": 0.0,
        "offset": 0,
        "size": 0,
        "latency_ms": None,
        "median_ms": None,
        "rewritten": 0,
        "verified": 0,
        "message": "Ready",
        "health": {"media": "OK", "transport": "OK", "mechanical": "OK"},
        "started": None,
    }

    selected = tk.StringVar(value="No external drive selected")
    inventory = {}  # Snapshot used only for DISPLAY; CLI rediscovers and verifies before writes.
    image = tk.StringVar()
    dest_file = tk.StringVar()
    dest_dir = tk.StringVar()
    journal_dir = tk.StringVar(value=str(Path.home() / "DriveRepairJournal"))
    status = tk.StringVar(value="Recovery engine idle — presentation layer only draws throttled progress")
    phase_var = tk.StringVar(value="IDLE")
    health_var = tk.StringVar(value="media OK · transport OK · mechanical* OK")
    metric_var = tk.StringVar(value="—")
    msg_var = tk.StringVar(value="Select a workflow. Disk I/O runs in a child process.")

    shell = ttk.Frame(root, padding=16)
    shell.pack(fill="both", expand=True)

    header = ttk.Frame(shell)
    header.pack(fill="x")
    ttk.Label(header, text="DriveRepair", style="Title.TLabel").pack(side="left")
    ttk.Label(header, text="  Recovery Workstation", style="Muted.TLabel").pack(side="left", pady=(10, 0))
    ttk.Label(header, text="90% recovery · 10% presentation · cross-platform",
              style="Muted.TLabel").pack(side="right", pady=(12, 0))

    # Live ops strip
    ops = tk.Frame(shell, bg=C["panel"], highlightbackground=C["border"], highlightthickness=1)
    ops.pack(fill="x", pady=(14, 10), ipady=8, ipadx=8)
    left = tk.Frame(ops, bg=C["panel"])
    left.pack(side="left", fill="both", expand=True, padx=10, pady=6)
    tk.Label(left, textvariable=phase_var, bg=C["panel"], fg=C["accent"],
             font=("Segoe UI Semibold", 14)).pack(anchor="w")
    tk.Label(left, textvariable=msg_var, bg=C["panel"], fg=C["text"],
             font=("Segoe UI", 10)).pack(anchor="w", pady=(2, 0))
    tk.Label(left, textvariable=health_var, bg=C["panel"], fg=C["muted"],
             font=("Segoe UI", 9)).pack(anchor="w", pady=(4, 0))
    right = tk.Frame(ops, bg=C["panel"])
    right.pack(side="right", padx=10, pady=6)
    tk.Label(right, textvariable=metric_var, bg=C["panel"], fg=C["text"],
             font=("Consolas", 11), justify="right").pack(anchor="e")
    pbar = ttk.Progressbar(ops, mode="determinate", maximum=1000)
    pbar.pack(fill="x", padx=10, pady=(0, 8))

    # Sector map
    map_frame = tk.Frame(shell, bg=C["panel"], highlightbackground=C["border"], highlightthickness=1)
    map_frame.pack(fill="both", expand=False, pady=(0, 10))
    tk.Label(map_frame, text="Surface activity map  ·  . pending   o ok   S slow   ! escalate   X error",
             bg=C["panel"], fg=C["muted"], font=("Segoe UI", 9)).pack(anchor="w", padx=10, pady=(8, 2))
    canvas = tk.Canvas(map_frame, height=170, bg=C["panel2"], highlightthickness=0)
    canvas.pack(fill="x", padx=10, pady=(0, 10))

    color_for = {".": C["pending"], "o": C["ok"], "S": C["slow"], "!": C["warn"], "X": C["fail"]}

    def redraw_map(force: bool = False) -> None:
        nonlocal map_dirty, last_map_draw
        now = time.monotonic()
        if not force and (not map_dirty or now - last_map_draw < 0.15):
            return
        map_dirty = False
        last_map_draw = now
        canvas.delete("all")
        w = max(canvas.winfo_width(), 40)
        h = max(canvas.winfo_height(), 40)
        cw, ch = w / map_width, h / map_height
        for y in range(map_height):
            for x in range(map_width):
                sym = map_cells[y * map_width + x]
                canvas.create_rectangle(
                    x * cw, y * ch, (x + 1) * cw - 1, (y + 1) * ch - 1,
                    fill=color_for.get(sym, C["pending"]), outline="",
                )

    def mark_map(offset: int, size: int, symbol: str) -> None:
        nonlocal map_dirty
        if size <= 0:
            return
        idx = min(len(map_cells) - 1, int(offset * len(map_cells) / size))
        rank = {".": 0, "o": 1, "S": 2, "!": 3, "X": 4}
        if rank.get(symbol, 0) >= rank.get(map_cells[idx], 0):
            map_cells[idx] = symbol
            map_dirty = True

    def reset_map() -> None:
        nonlocal map_dirty
        for i in range(len(map_cells)):
            map_cells[i] = "."
        map_dirty = True
        redraw_map(force=True)

    notebook = ttk.Notebook(shell)
    notebook.pack(fill="both", expand=True)
    tab_drive = ttk.Frame(notebook, padding=12)
    tab_image = ttk.Frame(notebook, padding=12)
    tab_refresh = ttk.Frame(notebook, padding=12)
    tab_fs = ttk.Frame(notebook, padding=12)
    notebook.add(tab_drive, text=" Diagnose / Rescue ")
    notebook.add(tab_image, text=" Image recovery ")
    notebook.add(tab_refresh, text=" In-place refresh ")
    notebook.add(tab_fs, text=" Clone repair ")

    log_holder = tk.Frame(shell, bg=C["panel"], highlightbackground=C["border"], highlightthickness=1)
    log_holder.pack(fill="both", expand=True, pady=(10, 0))
    tk.Label(log_holder, text="Operation log", bg=C["panel"], fg=C["muted"],
             font=("Segoe UI", 9)).pack(anchor="w", padx=8, pady=(6, 0))
    log = tk.Text(log_holder, height=8, wrap="word", state="disabled",
                  bg=C["panel2"], fg=C["text"], insertbackground=C["text"],
                  font=("Consolas", 9), relief="flat", borderwidth=0)
    log.pack(fill="both", expand=True, padx=8, pady=6)

    def write(text: str) -> None:
        log.configure(state="normal")
        log.insert("end", text)
        log.see("end")
        log.configure(state="disabled")

    def require(var: tk.StringVar, name: str) -> str:
        value = var.get().strip()
        if not value:
            raise ValueError(f"Select a {name} first.")
        return value

    def row(parent, title: str, var: tk.StringVar, picker=None) -> None:
        line = ttk.Frame(parent)
        line.pack(fill="x", pady=4)
        ttk.Label(line, text=title, width=22).pack(side="left")
        ttk.Entry(line, textvariable=var).pack(side="left", fill="x", expand=True, padx=4)
        if picker:
            ttk.Button(line, text="Browse…", command=picker).pack(side="left")

    def pick_file():
        chosen = filedialog.askopenfilename(title="Select source image / archive")
        if chosen:
            image.set(chosen)

    def pick_output():
        chosen = filedialog.asksaveasfilename(title="Choose a NEW destination image",
                                              defaultextension=".img")
        if chosen:
            dest_file.set(chosen)

    def pick_dir():
        chosen = filedialog.askdirectory(title="Choose parent folder for recovered files")
        if chosen:
            dest_dir.set(os.path.join(chosen, "recovered_files"))

    def pick_journal():
        chosen = filedialog.askdirectory(title="Choose a healthy, separate parent disk for journal")
        if chosen:
            journal_dir.set(os.path.join(chosen, "driverepair-journal-new"))

    def apply_progress(event: dict) -> None:
        nonlocal map_dirty
        phase = str(event.get("phase") or stats["phase"])
        stats["phase"] = phase
        phase_var.set(phase)
        stats["message"] = str(event.get("message") or stats["message"])
        msg_var.set(stats["message"])
        stats["offset"] = int(event.get("offset") or 0)
        stats["size"] = int(event.get("size") or stats["size"] or 0)
        if event.get("latency_ms") is not None:
            stats["latency_ms"] = event["latency_ms"]
        if event.get("median_ms") is not None:
            stats["median_ms"] = event["median_ms"]
        stats["rewritten"] = int(event.get("rewritten_bytes") or stats["rewritten"])
        stats["verified"] = int(event.get("verified_bytes") or stats["verified"])
        health = event.get("health") or stats["health"]
        stats["health"] = health
        health_var.set(
            f"media {health.get('media', '?')} · transport {health.get('transport', '?')} · "
            f"mechanical* {health.get('mechanical', '?')}  (*latency proxy; no acoustic mic)"
        )
        # Percent from probe or refresh indices.
        pi, pt = int(event.get("probe_index") or 0), int(event.get("probe_total") or 0)
        ri, rt = int(event.get("refresh_index") or 0), int(event.get("refresh_total") or 0)
        if phase == "PROBE" and pt:
            pct = 100.0 * pi / pt
        elif rt:
            pct = 100.0 * ri / rt
        else:
            pct = stats["pct"]
        stats["pct"] = pct
        pbar["value"] = max(0, min(1000, int(pct * 10)))
        lat = stats["latency_ms"]
        med = stats["median_ms"]
        metric_var.set(
            f"{pct:5.1f}% done\n"
            f"lat {('—' if lat is None else f'{lat:.0f} ms'):>8}   med {('—' if med is None else f'{med:.0f} ms'):>8}\n"
            f"rewritten {stats['rewritten'] / (1024 * 1024):.2f} MiB"
        )
        symbol = "o"
        if event.get("failed"):
            symbol = "X"
        elif phase == "ESCALATE":
            symbol = "!"
        elif lat is not None and med is not None and lat >= max(med * 2, 1):
            symbol = "S"
        if stats["size"]:
            mark_map(stats["offset"], stats["size"], symbol)
        compact = event.get("map")
        if isinstance(compact, str) and compact:
            for i, ch in enumerate(compact):
                idx = min(len(map_cells) - 1, int(i * len(map_cells) / max(1, len(compact))))
                map_cells[idx] = ch if ch in color_for else map_cells[idx]
            map_dirty = True

    def start(args: list[str], title: str, *, risky: bool = False, destructive: bool = False) -> None:
        nonlocal process, busy
        if busy:
            messagebox.showwarning("Busy", "A job is already active.")
            return
        if risky and not messagebox.askyesno(
            "Read risk",
            "This reads a physical drive. Unstable hardware can worsen or disconnect. Continue?",
        ):
            return
        if destructive:
            if not messagebox.askyesno(
                "Destructive acknowledgement",
                "In-place refresh WRITES the patient disk. A crash or USB failure may permanently "
                "destroy recoverable data. A rolling journal is NOT a backup. Continue?",
            ):
                return
            selected_id = chosen_device()
            typed = simpledialog.askstring(
                "Confirm destructive target",
                f"Type the exact selected device ID to authorize writes:\n{selected_id}",
                parent=root,
            )
            if typed != selected_id:
                messagebox.showerror("Not authorized", "Device ID confirmation did not match; no write started.")
                return
        command = [sys.executable, "-m", "driverepair_desktop", *args]
        write(f"\n=== {title} ===\n")
        status.set(f"Running: {title}")
        phase_var.set("STARTING")
        msg_var.set(title)
        stats["started"] = time.monotonic()
        reset_map()
        busy = True
        cancel_button.configure(state="normal")

        def worker() -> None:
            nonlocal process
            try:
                child = subprocess.Popen(
                    command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, bufsize=1,
                )
                process = child

                def pump(stream, kind: str) -> None:
                    assert stream is not None
                    for line in stream:
                        q.put((kind, line))

                threading.Thread(target=pump, args=(child.stdout, "stdout"), daemon=True).start()
                threading.Thread(target=pump, args=(child.stderr, "stderr"), daemon=True).start()
                code = child.wait()
                q.put(("done", (title, code)))
            except (OSError, ValueError) as exc:
                q.put(("stdout", f"Unable to start: {exc}\n"))
                q.put(("done", (title, -1)))

        threading.Thread(target=worker, daemon=True).start()

    def cancel() -> None:
        if process is not None and process.poll() is None:
            if messagebox.askyesno("Cancel", "Stop the active job?"):
                process.terminate()
                status.set("Cancellation requested")

    # --- Diagnose / rescue tab ---
    ttk.Label(tab_drive, text="External whole disks only. Prefer image rescue before any in-place work.",
              style="Muted.TLabel", wraplength=900).pack(anchor="w")
    tree = ttk.Treeview(tab_drive, show="headings",
                        columns=("id", "model", "size", "bus", "serial", "location", "verify"), height=6)
    for key, width in [("id", 190), ("model", 180), ("size", 110), ("bus", 65), ("serial", 90),
                       ("location", 135), ("verify", 115)]:
        tree.heading(key, text=key.upper())
        tree.column(key, width=width, stretch=(key == "model"))
    tree.pack(fill="x", pady=8)
    tree.bind("<<TreeviewSelect>>", lambda e: selected.set(
        tree.selection()[0] if tree.selection() else "No external drive selected"))
    ttk.Label(tab_drive, textvariable=selected).pack(anchor="w")

    def refresh_devices() -> None:
        if busy:
            messagebox.showwarning("Busy", "Finish the current job first.")
            return

        def worker():
            try:
                from .devices import list_external_devices
                q.put(("devices", list_external_devices()))
            except (OSError, ValueError, RuntimeError) as exc:
                q.put(("stdout", f"Discovery failed: {exc}\n"))

        threading.Thread(target=worker, daemon=True).start()
        status.set("Discovering external disks…")

    def chosen_device() -> str:
        value = selected.get()
        if not value.startswith(("linux:", "windows:", "macos:")):
            raise ValueError("Select an external drive from the inventory.")
        return value

    def device_action(kind: str) -> None:
        try:
            dev = chosen_device()
            if kind == "health":
                start(["health", "--device", dev, "--json"], "SMART health")
            elif kind == "sample":
                start(["scan", "--device", dev, "--mode", "sample", "--json"], "Quick scan", risky=True)
            elif kind == "full":
                start(["scan", "--device", dev, "--mode", "full", "--ack-risk", "--json"],
                      "Full scan", risky=True)
            elif kind == "benchmark":
                start(["benchmark-external", "--device", dev, "--ack-risk", "--json"],
                      "Benchmark", risky=True)
            elif kind == "rescue":
                if not sys.platform.startswith("linux"):
                    raise ValueError("Direct external rescue is Linux-only in this build.")
                out = require(dest_file, "new image destination")
                start(["rescue-external", "--device", dev, "--output", out, "--ack-risk", "--json"],
                      "External rescue", risky=True)
        except ValueError as exc:
            messagebox.showerror("Input", str(exc))

    bf = ttk.Frame(tab_drive)
    bf.pack(anchor="w", pady=8)
    ttk.Button(bf, text="Refresh inventory", command=refresh_devices).pack(side="left", padx=(0, 6))
    for label, kind in [("SMART", "health"), ("Quick scan", "sample"), ("Full scan", "full"),
                        ("Benchmark", "benchmark"), ("Rescue (Linux)", "rescue")]:
        ttk.Button(bf, text=label, command=lambda k=kind: device_action(k)).pack(side="left", padx=(0, 6))
    row(tab_drive, "Rescue image output", dest_file, pick_output)

    # --- Image recovery ---
    ttk.Label(tab_image, text="Read regular files only. Outputs are always new paths.",
              style="Muted.TLabel").pack(anchor="w")
    row(tab_image, "Source image / ZIP", image, pick_file)
    row(tab_image, "New image output", dest_file, pick_output)
    row(tab_image, "New recovery directory", dest_dir, pick_dir)

    def image_action(kind: str) -> None:
        try:
            src = require(image, "source image")
            if kind == "scan":
                start(["scan-image", "--image", src, "--mode", "sample", "--json"], "Scan image")
            elif kind == "rescue":
                start(["rescue-image", "--image", src, "--output", require(dest_file, "output"),
                       "--json"], "Rescue image")
            elif kind == "verify":
                start(["verify-images", "--image", src,
                       "--output", require(dest_file, "rescued image"), "--json"], "Verify images")
            elif kind == "carve":
                start(["carve-image", "--image", src,
                       "--output-dir", require(dest_dir, "directory"), "--json"], "Carve photos")
            elif kind == "undelete":
                start(["undelete-fat32", "--image", src,
                       "--output-dir", require(dest_dir, "directory"), "--json"], "FAT32 undelete")
            elif kind == "zip":
                start(["salvage-zip", "--archive", src,
                       "--output-dir", require(dest_dir, "directory"), "--json"], "Salvage ZIP")
        except ValueError as exc:
            messagebox.showerror("Input", str(exc))

    ib = ttk.Frame(tab_image)
    ib.pack(anchor="w", pady=8)
    for label, kind in [("Scan", "scan"), ("Rescue", "rescue"), ("Verify", "verify"),
                        ("Carve", "carve"), ("FAT32 undelete", "undelete"), ("ZIP salvage", "zip")]:
        ttk.Button(ib, text=label, command=lambda k=kind: image_action(k)).pack(side="left", padx=(0, 6))

    # --- In-place refresh ---
    ttk.Label(
        tab_refresh,
        text="Dedicated In-Place Media Refresh. Rolling journal on healthy storage. "
             "Adaptive rewrite of consistently readable regions only; never a substitute for backup.",
        style="Muted.TLabel", wraplength=920,
    ).pack(anchor="w")
    row(tab_refresh, "Journal directory", journal_dir, pick_journal)
    mode_var = tk.StringVar(value="adaptive")
    backend_var = tk.StringVar(value="disk")
    power_var = tk.StringVar(value="")
    after_var = tk.StringVar(value="ask")
    samples_var = tk.StringVar(value="128")
    chunk_var = tk.StringVar(value="8")
    opts = ttk.Frame(tab_refresh)
    opts.pack(fill="x", pady=6)
    ttk.Label(opts, text="Mode").pack(side="left")
    ttk.Combobox(opts, textvariable=mode_var, values=["adaptive", "full"], width=10,
                 state="readonly").pack(side="left", padx=6)
    ttk.Label(opts, text="Journal").pack(side="left", padx=(12, 0))
    ttk.Combobox(opts, textvariable=backend_var, values=["disk", "ramdisk"], width=10,
                 state="readonly").pack(side="left", padx=6)
    ttk.Label(opts, text="After").pack(side="left", padx=(12, 0))
    ttk.Combobox(opts, textvariable=after_var, values=["ask", "keep", "delete"], width=8,
                 state="readonly").pack(side="left", padx=6)
    ttk.Label(opts, text="Chunk (MiB)").pack(side="left", padx=(12, 0))
    ttk.Combobox(opts, textvariable=chunk_var, values=["1", "4", "8", "16", "32", "64"],
                 width=4, state="readonly").pack(side="left", padx=6)
    ttk.Label(opts, text="Samples").pack(side="left", padx=(12, 0))
    ttk.Entry(opts, textvariable=samples_var, width=6).pack(side="left", padx=6)

    row(tab_refresh, "RAM power source (nut:UPSNAME or battery)", power_var)
    ttk.Label(tab_refresh, text="RAM mode is Linux-only and VOLATILE even with UPS. "
              "Use a tmpfs/ramfs mount with swap disabled; both host and dock need battery backup.",
              style="Muted.TLabel", wraplength=920).pack(anchor="w")

    def run_refresh() -> None:
        try:
            dev = chosen_device()
            journal = require(journal_dir, "journal directory")
            samples = max(8, min(4096, int(samples_var.get())))
            args = [
                "refresh-external", "--device", dev, "--journal", journal,
                "--mode", mode_var.get(), "--journal-backend", backend_var.get(),
                "--adaptive-samples", str(samples), "--after-run", after_var.get(),
                "--chunk-mib", chunk_var.get(),
                # GUI owns the map/health UI — disable TTY panel, keep JSONL only.
                "--no-live-dashboard", "--progress-jsonl",
                "--ack-risk", "--ack-destructive", "--ack-no-backup", "--ack-data-loss-risk",
                "--ack-usb-bridge-risk", "--ack-unvalidated-hardware", "--json",
            ]
            if dev not in inventory:
                raise ValueError('Rescan device inventory before attempting patient writes')
            args.extend(["--confirm-identity", inventory[dev].fingerprint[:12]])
            if backend_var.get() == 'ramdisk':
                if not messagebox.askyesno('VOLATILE RAM JOURNAL',
                        'Host restart, RAM loss or dock failure can permanently damage the disk. '
                        'Do you accept this risk and confirm BOTH laptop/UPS and dock are powered?'):
                    return
                args.extend(['--power-source', require(power_var, 'UPS/battery telemetry'),
                             '--ack-volatile-journal', '--ack-dock-power-backed'])
            stats["size"] = 0
            # Best-effort size from tree selection text is unknown; engine events fill it.
            start(args, f"In-place refresh ({mode_var.get()})", risky=True, destructive=True)
        except ValueError as exc:
            messagebox.showerror("Input", str(exc))
        except Exception as exc:  # noqa: BLE001 — show sample parse errors
            messagebox.showerror("Input", str(exc))

    ttk.Button(tab_refresh, text="Start Adaptive / Full refresh", style="Accent.TButton",
               command=run_refresh).pack(anchor="w", pady=10)
    ttk.Label(
        tab_refresh,
        text="Windows requires an Administrator session for physical writes. "
             "mechanical* is inferred from latency/errors — USB docks do not expose acoustic sensors.",
        style="Muted.TLabel", wraplength=920,
    ).pack(anchor="w")

    # --- Clone FS repair ---
    ttk.Label(tab_fs, text="Filesystem repair only on a NEW clone. Original stays read-only.",
              style="Muted.TLabel").pack(anchor="w")
    row(tab_fs, "Original ext image", image, pick_file)
    row(tab_fs, "New repaired copy", dest_file, pick_output)

    def inspect_ext() -> None:
        try:
            start(["check-ext-image", "--image", require(image, "ext image"), "--json"], "ext check")
        except ValueError as exc:
            messagebox.showerror("Input", str(exc))

    def repair_ext() -> None:
        try:
            src, out = require(image, "ext image"), require(dest_file, "destination")
            if not messagebox.askyesno("Confirm", "Repair may discard corrupt references on the COPY only."):
                return
            if simpledialog.askstring("Approval", "Type REPAIR COPY:") != "REPAIR COPY":
                return
            start(["repair-ext-image", "--image", src, "--output", out, "--ack-repair", "--json"],
                  "Repair ext clone")
        except ValueError as exc:
            messagebox.showerror("Input", str(exc))

    fb = ttk.Frame(tab_fs)
    fb.pack(anchor="w", pady=8)
    ttk.Button(fb, text="Read-only check", command=inspect_ext).pack(side="left", padx=(0, 6))
    ttk.Button(fb, text="Repair NEW copy", command=repair_ext).pack(side="left")

    statusbar = ttk.Frame(shell)
    statusbar.pack(fill="x", pady=(8, 0))
    ttk.Label(statusbar, textvariable=status).pack(side="left", fill="x", expand=True)
    cancel_button = ttk.Button(statusbar, text="Cancel job", command=cancel, state="disabled")
    cancel_button.pack(side="right")

    def poll() -> None:
        nonlocal process, busy
        try:
            while True:
                kind, value = q.get_nowait()
                if kind == "stdout":
                    write(str(value))
                elif kind == "stderr":
                    line = str(value).rstrip("\n")
                    if line.startswith("{"):
                        try:
                            event = json.loads(line)
                            if event.get("type") == "progress":
                                apply_progress(event)
                                continue
                        except json.JSONDecodeError:
                            pass
                    if line.strip():
                        write(line + "\n")
                elif kind == "devices":
                    inventory.clear()
                    inventory.update({d.id: d for d in value})
                    selected.set("No external drive selected")
                    for item in tree.get_children():
                        tree.delete(item)
                    for device in value:
                        public = device.public()
                        tree.insert("", "end", iid=device.id, values=(
                            device.id, device.model, f"{device.size_bytes / 10**9:.2f} GB",
                            device.bus, public["serial_suffix"],
                            public["location"], public["identity_hint"],
                        ))
                        if stats["size"] == 0 and tree.selection() == ():
                            pass
                    status.set(f"Found {len(value)} external whole disk(s)")
                elif kind == "done":
                    title, code = value
                    process = None
                    busy = False
                    cancel_button.configure(state="disabled")
                    phase_var.set("DONE" if code == 0 else f"EXIT {code}")
                    status.set(f"{title}: {'finished' if code == 0 else f'exited {code}'}")
                    write(f"--- Finished: exit code {code} ---\n")
                    redraw_map(force=True)
        except queue.Empty:
            pass
        redraw_map()
        root.after(100, poll)

    def on_close() -> None:
        if process is not None and process.poll() is None:
            if not messagebox.askyesno("Active job", "Cancel the running job and exit?"):
                return
            process.terminate()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    canvas.bind("<Configure>", lambda e: redraw_map(force=True))
    poll()
    refresh_devices()
    root.mainloop()
