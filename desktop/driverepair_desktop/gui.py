"""Standard-library desktop interface to the DriveRepair CLI.

The GUI deliberately delegates operations to the same CLI used by tests and
scripts. Every operation is a foreground child process with explicit cancel;
no GUI widget writes to a device or bypasses CLI safety preflights.
"""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
from pathlib import Path


def launch() -> None:
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, simpledialog, ttk
    except ImportError as exc:
        raise RuntimeError('Tk is unavailable. Install the operating-system Python tkinter package') from exc

    try:
        root = tk.Tk()
    except tk.TclError as exc:
        raise RuntimeError('No desktop display available. Use the DriveRepair CLI instead') from exc

    root.title('DriveRepair — Recovery Workstation (Experimental)')
    root.geometry('1000x790')
    root.minsize(780, 620)
    root.option_add('*Font', 'TkDefaultFont')

    q: queue.Queue[tuple[str, object]] = queue.Queue()
    process: subprocess.Popen[str] | None = None
    busy = False
    device_ids: list[str] = []
    selected = tk.StringVar(value='No external drive selected')
    image = tk.StringVar()
    dest_file = tk.StringVar()
    dest_dir = tk.StringVar()
    status = tk.StringVar(value='Ready — source disks are never opened for writing by desktop recovery.')

    frame = ttk.Frame(root, padding=12)
    frame.pack(fill='both', expand=True)
    ttk.Label(frame, text='DriveRepair', font=('TkDefaultFont', 20, 'bold')).pack(anchor='w')
    ttk.Label(frame, text='Diagnostics · Image rescue · Deleted-file recovery · Filesystem repair on a COPY',
              foreground='#566171').pack(anchor='w', pady=(3, 9))
    notebook = ttk.Notebook(frame)
    notebook.pack(fill='both', expand=True)
    drives = ttk.Frame(notebook, padding=12)
    recovery = ttk.Frame(notebook, padding=12)
    maintenance = ttk.Frame(notebook, padding=12)
    notebook.add(drives, text='External drives')
    notebook.add(recovery, text='Recover files / images')
    notebook.add(maintenance, text='Repair a filesystem copy')

    def row(parent, title: str, var: tk.StringVar, picker) -> None:
        line = ttk.Frame(parent)
        line.pack(fill='x', pady=5)
        ttk.Label(line, text=title, width=23).pack(side='left')
        ttk.Entry(line, textvariable=var).pack(side='left', fill='x', expand=True, padx=4)
        ttk.Button(line, text='Browse…', command=picker).pack(side='left')

    def pick_file():
        chosen = filedialog.askopenfilename(title='Select source image / archive')
        if chosen:
            image.set(chosen)

    def pick_output():
        chosen = filedialog.asksaveasfilename(title='Choose a NEW destination image',
                                               defaultextension='.img')
        if chosen:
            dest_file.set(chosen)

    def pick_dir():
        chosen = filedialog.askdirectory(title='Choose the parent folder for recovered files')
        if chosen:
            dest_dir.set(os.path.join(chosen, 'recovered_files'))

    log_holder = ttk.LabelFrame(frame, text='Operation log (saved outputs are never overwritten)', padding=8)
    log_holder.pack(side='bottom', fill='both', expand=True, pady=(10, 0))
    log = tk.Text(log_holder, height=10, wrap='word', state='disabled', font=('TkFixedFont', 10))
    scroll = ttk.Scrollbar(log_holder, orient='vertical', command=log.yview)
    log.configure(yscrollcommand=scroll.set)
    log.pack(side='left', fill='both', expand=True)
    scroll.pack(side='right', fill='y')

    def write(text: str) -> None:
        log.configure(state='normal')
        log.insert('end', text)
        log.see('end')
        log.configure(state='disabled')

    def require(var: tk.StringVar, name: str) -> str:
        value = var.get().strip()
        if not value:
            raise ValueError(f'Select a {name} first.')
        return value

    def start(args: list[str], title: str, *, risky: bool = False) -> None:
        nonlocal process, busy
        if busy:
            messagebox.showwarning('Busy', 'A job is already active. Cancel or complete it first.')
            return
        if risky and not messagebox.askyesno('Read risk acknowledgement',
                    'This operation reads a physical drive. Reading unstable hardware can worsen '
                    'damage or cause it to disconnect. No source writes will be requested. Continue?'):
            return
        command = [sys.executable, '-m', 'driverepair_desktop', *args]
        write(f'\n--- {title} ---\nCommand: {sys.executable} -m driverepair_desktop ' +
              ' '.join('<path>' if os.sep in value and value != os.sep else value for value in args) + '\n')
        status.set(f'Running: {title}')
        busy = True
        cancel_button.configure(state='normal')

        def worker() -> None:
            nonlocal process
            try:
                child = subprocess.Popen(command, stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT, text=True, bufsize=1)
                process = child
                assert child.stdout is not None
                for line in child.stdout:
                    q.put(('text', line))
                code = child.wait()
                q.put(('done', (title, code)))
            except (OSError, ValueError) as exc:
                q.put(('text', f'Unable to start: {exc}\n'))
                q.put(('done', (title, -1)))
        threading.Thread(target=worker, daemon=True).start()

    def cancel() -> None:
        if process is not None and process.poll() is None:
            if messagebox.askyesno('Cancel active job',
                     'Stop this process? A rescue map may be resumable; a filesystem copy under '
                     'repair may be inconsistent. The original remains unchanged by the tool.'):
                process.terminate()
                status.set('Cancellation requested')

    statusbar = ttk.Frame(frame)
    statusbar.pack(side='bottom', fill='x', pady=(7, 0))
    ttk.Label(statusbar, textvariable=status).pack(side='left', fill='x', expand=True)
    cancel_button = ttk.Button(statusbar, text='Cancel active job', command=cancel, state='disabled')
    cancel_button.pack(side='right')

    # External drive tab
    ttk.Label(drives, text='Only external WHOLE disks are eligible. Never choose a valuable failing '
              'drive for benchmarking before rescuing its data.', wraplength=860).pack(anchor='w', pady=(0, 8))
    tree = ttk.Treeview(drives, show='headings', columns=('id', 'model', 'size', 'bus', 'serial'), height=6)
    for key, width in [('id', 210), ('model', 250), ('size', 125), ('bus', 80), ('serial', 90)]:
        tree.heading(key, text=key.title())
        tree.column(key, width=width, stretch=(key == 'model'))
    tree.pack(fill='x')
    tree.bind('<<TreeviewSelect>>', lambda event: selected.set(tree.selection()[0]
                 if tree.selection() else 'No external drive selected'))
    ttk.Label(drives, textvariable=selected).pack(anchor='w', pady=6)

    def refresh():
        if busy:
            messagebox.showwarning('Busy', 'Complete the current job before refreshing devices.')
            return
        def worker():
            try:
                from .devices import list_external_devices
                q.put(('devices', list_external_devices()))
            except (OSError, ValueError, RuntimeError) as exc:
                q.put(('text', f'External disk discovery failed: {exc}\n'))
        threading.Thread(target=worker, daemon=True).start()
        status.set('Discovering attached external disks…')

    ttk.Button(drives, text='Refresh external drives', command=refresh).pack(anchor='w', pady=5)
    buttons = ttk.Frame(drives)
    buttons.pack(anchor='w', pady=5)

    def chosen_device():
        value = selected.get()
        if not value.startswith(('linux:', 'windows:', 'macos:')):
            raise ValueError('Select an external drive from the inventory.')
        return value

    def device_action(kind: str):
        try:
            dev = chosen_device()
            if kind == 'health':
                start(['health', '--device', dev, '--json'], 'SMART health')
            elif kind == 'sample':
                start(['scan', '--device', dev, '--mode', 'sample', '--json'], 'Quick drive scan', risky=True)
            elif kind == 'full':
                start(['scan', '--device', dev, '--mode', 'full', '--ack-risk', '--json'], 'Full surface scan', risky=True)
            elif kind == 'benchmark':
                start(['benchmark-external', '--device', dev, '--ack-risk', '--json'], 'External read benchmark', risky=True)
            elif kind == 'rescue':
                if not sys.platform.startswith('linux'):
                    raise ValueError('Direct external-drive rescue is only supported on Linux in this build.')
                out = require(dest_file, 'new image destination')
                start(['rescue-external', '--device', dev, '--output', out,
                       '--ack-risk', '--json'], 'External drive rescue', risky=True)
        except ValueError as exc:
            messagebox.showerror('Select required input', str(exc))

    for label, kind in [('SMART health', 'health'), ('Quick scan', 'sample'),
                        ('Full scan', 'full'), ('Read benchmark', 'benchmark'),
                        ('Rescue to image (Linux)', 'rescue')]:
        ttk.Button(buttons, text=label, command=lambda k=kind: device_action(k)).pack(side='left', padx=(0, 6))
    ttk.Label(drives, text='Rescue output image (different physical disk; Linux only):').pack(anchor='w', pady=(15, 0))
    row(drives, 'New image output', dest_file, pick_output)
    ttk.Label(drives, text='On Windows/macOS, use this desktop application for scanning, imaging-tool '
              'imports, and image-based recovery; direct-device rescue is not verified.',
              wraplength=860).pack(anchor='w', pady=8)

    # Image and archive recovery tab
    ttk.Label(recovery, text='All operations below read a regular image or archive and write to '
              'a NEW output. Never use the failing source disk for outputs.', wraplength=860).pack(anchor='w')
    row(recovery, 'Source image / ZIP', image, pick_file)
    row(recovery, 'New image output', dest_file, pick_output)
    row(recovery, 'New recovery directory', dest_dir, pick_dir)
    options = ttk.LabelFrame(recovery, text='Image rescue and analysis', padding=8)
    options.pack(fill='x', pady=5)
    fb = ttk.Frame(options)
    fb.pack(anchor='w')
    def image_action(kind: str):
        try:
            src = require(image, 'source image')
            if kind == 'scan':
                start(['scan-image', '--image', src, '--mode', 'sample', '--json'], 'Scan image')
            elif kind == 'benchmark':
                start(['benchmark-image', '--image', src, '--json'], 'Benchmark image')
            elif kind in ('rescue', 'resume', 'retry'):
                out = require(dest_file, 'new image output')
                args = ['rescue-image', '--image', src, '--output', out, '--json']
                if kind in ('resume', 'retry'):
                    args.append('--resume')
                if kind == 'retry':
                    args.append('--retry-missing')
                start(args, 'Rescue image' if kind == 'rescue' else 'Resume/Retry image rescue')
            elif kind == 'verify':
                start(['verify-images', '--image', src, '--output', require(dest_file, 'rescued output image'),
                       '--json'], 'Compare images byte for byte')
            elif kind == 'carve':
                start(['carve-image', '--image', src, '--output-dir', require(dest_dir, 'new directory'),
                       '--json'], 'Carve JPEG / PNG')
            elif kind == 'undelete':
                start(['undelete-fat32', '--image', src, '--output-dir', require(dest_dir, 'new directory'),
                       '--json'], 'FAT32 deleted-file recovery')
            elif kind == 'zip':
                start(['salvage-zip', '--archive', src, '--output-dir', require(dest_dir, 'new directory'),
                       '--json'], 'Recover intact ZIP members')
        except ValueError as exc:
            messagebox.showerror('Input needed', str(exc))
    for label, kind in [('Scan image', 'scan'), ('Benchmark image', 'benchmark'),
                        ('Rescue', 'rescue'), ('Resume', 'resume'), ('Retry missing', 'retry'),
                        ('Verify bytes', 'verify')]:
        ttk.Button(fb, text=label, command=lambda k=kind: image_action(k)).pack(side='left', padx=(0, 6))
    f2 = ttk.Frame(options)
    f2.pack(anchor='w', pady=(7, 0))
    for label, kind in [('Carve photos', 'carve'), ('FAT32 undelete', 'undelete'),
                        ('Salvage ZIP', 'zip')]:
        ttk.Button(f2, text=label, command=lambda k=kind: image_action(k)).pack(side='left', padx=(0, 6))
    ttk.Label(recovery, text='FAT32 undelete retrieves only contiguous, currently unallocated '
              'clusters. Filenames are partial; extracted content is NOT verified. Carving may find '
              'live or fragmented files. Consult the JSON results and rescue journal.',
              wraplength=860).pack(anchor='w', pady=8)

    # Filesystem repairs (original always read-only; repair modifies cloned output).
    ttk.Label(maintenance, text='A true repair operation can discard damaged metadata or files. '
              'DriveRepair only runs filesystem repair on a NEW CLONE of an ext2/3/4 image. '
              'It does not currently perform hardware repair or restore physical wear.',
              wraplength=850).pack(anchor='w', pady=(0, 8))
    row(maintenance, 'Original ext image', image, pick_file)
    row(maintenance, 'New repaired copy', dest_file, pick_output)
    def inspect():
        try:
            start(['check-ext-image', '--image', require(image, 'ext image'), '--json'], 'Read-only ext check')
        except ValueError as exc:
            messagebox.showerror('Input needed', str(exc))
    def repair():
        try:
            src, out = require(image, 'ext image'), require(dest_file, 'new destination')
            if not messagebox.askyesno('Confirm image-copy repair',
                       'This may discard corrupt file references from the NEW COPY. '
                       'The original image will not be written by this tool. Continue?'):
                return
            confirmation = simpledialog.askstring('Explicit approval',
                        'Type REPAIR COPY to create a new image and run e2fsck -y on that copy:')
            if confirmation != 'REPAIR COPY':
                return
            start(['repair-ext-image', '--image', src, '--output', out,
                   '--ack-repair', '--json'], 'Repair ext filesystem CLONE')
        except ValueError as exc:
            messagebox.showerror('Input needed', str(exc))
    actions = ttk.Frame(maintenance)
    actions.pack(anchor='w', pady=8)
    ttk.Button(actions, text='Read-only ext check', command=inspect).pack(side='left', padx=(0, 8))
    ttk.Button(actions, text='Repair a NEW ext image copy', command=repair).pack(side='left')
    ttk.Label(maintenance, text='Requires e2fsprogs (e2fsck) installed on the host. '
              'A filesystem image must begin with the ext superblock: a whole partitioned disk image '
              'is not accepted. File metadata repair is not proof of correct original contents.',
              wraplength=850).pack(anchor='w', pady=8)

    def poll():
        nonlocal process, busy
        try:
            while True:
                kind, value = q.get_nowait()
                if kind == 'text':
                    write(str(value))
                elif kind == 'devices':
                    selected.set('No external drive selected')
                    for item in tree.get_children():
                        tree.delete(item)
                    for device in value:
                        public = device.public()
                        tree.insert('', 'end', iid=device.id, values=(
                            device.id, device.model, f'{device.size_bytes / 10**9:.2f} GB',
                            device.bus, public['serial_suffix']))
                    status.set(f'Found {len(value)} eligible external whole disk(s)')
                elif kind == 'done':
                    title, code = value
                    process = None
                    busy = False
                    cancel_button.configure(state='disabled')
                    status.set(f'{title}: ' + ('finished' if code == 0 else f'exited {code} — inspect log'))
                    write(f'--- Finished: exit code {code} ---\n')
        except queue.Empty:
            pass
        root.after(120, poll)

    def on_close():
        if process is not None and process.poll() is None:
            if not messagebox.askyesno('Active recovery job',
                                      'A job is still running. Cancel it and exit?'):
                return
            process.terminate()
        root.destroy()

    root.protocol('WM_DELETE_WINDOW', on_close)
    poll()
    refresh()
    root.mainloop()
