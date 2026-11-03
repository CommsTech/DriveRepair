"""DriveRepair Workstation (PySide6, optional).

The Qt process never opens patient media. All I/O is done by the existing
isolated CLI, whose safety checks are authoritative. This is a deliberately
small front-end, not an alternate disk-repair engine.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .surface_map import SurfaceCoverage
import sys
import time


def cli_prefix() -> list[str]:
    if sys.argv and str(sys.argv[0]).lower().endswith('.pyz'):
        return [sys.executable, os.path.abspath(sys.argv[0])]
    return [sys.executable, '-m', 'driverepair_desktop']


def display_size(value: int | float) -> str:
    value = float(value)
    for unit in ('B', 'KiB', 'MiB', 'GiB', 'TiB'):
        if abs(value) < 1024 or unit == 'TiB':
            return f'{value:,.2f} {unit}' if unit != 'B' else f'{value:,.0f} B'
        value /= 1024
    return '—'


def format_eta(value) -> str:
    if value is None:
        return 'Calculating…'
    try:
        remaining = max(0, float(value))
    except (ValueError, TypeError, OverflowError):
        return 'Calculating…'
    if remaining > 86400 * 365:
        return 'Unknown'
    seconds = round(remaining)
    hours, rem = divmod(seconds, 3600)
    mins, secs = divmod(rem, 60)
    return f'{hours}h {mins:02d}m' if hours else f'{mins}m {secs:02d}s'


def progress_percent(event: dict, disk_size: int = 0) -> float:
    """Completion of *current operation*, distinct from unique device coverage.

    A quick scan's 100% means all planned sample probes, NOT all LBAs.
    A refresh's 100% means all approved write transactions, NOT full-drive repair.
    """
    for done_key,total_key in (('refresh_index','refresh_total'), ('probe_index','probe_total')):
        if event.get(done_key) is not None and event.get(total_key):
            return max(0.0, min(100.0, 100.0 * float(event[done_key]) / float(event[total_key])))
    size = int(event.get('size') or disk_size or 0)
    if size <= 0:
        return 0.0
    cursor = int(event.get('scan_position_bytes') or event.get('offset') or 0)
    return max(0.0, min(100.0, 100.0 * cursor / size))




def estimated_job_percent(event: dict, *, guided: bool) -> float:
    """CONSERVATIVE phase-weighted estimate, not certified work completion.

    The number of repair candidates is unknown until scanning finishes; phase
    weights are only a presentation estimate. Never label it as verified coverage.
    """
    phase = str(event.get('phase') or '').upper()
    pct = progress_percent(event, int(event.get('size') or 0))
    if not guided:
        return pct
    if phase in {'SCANNING', 'TRIAGE'}:
        return pct * 0.60
    if phase == 'INVESTIGATING':
        reads = max(0, int(event.get('investigation_reads') or 0))
        total = max(1, int(event.get('investigation_total') or 1))
        return 60.0 + min(1, reads / total) * 15.0
    if phase == 'REFRESH':
        return 75.0 + pct * 0.25
    return 0.0

def _restrict_qt_debug_log_access(path: Path) -> None:
    """Best-effort local privacy; chmod on POSIX only — Windows ACLs not claimed."""
    try:
        if os.name == 'posix':
            os.chmod(path, 0o600)
            if path.parent.exists():
                os.chmod(path.parent, 0o700)
    except OSError:
        pass


def _qt_debug_log_path() -> Path | None:
    """Optional local mirror for Qt workstation diagnostics (opt-in debug sessions).

    Uses DRIVEREPAIR_GUI_DEBUG_LOG or a temp DriveRepair/debug directory — never a
    hard-coded lab path. Logs may include device/I/O details; operator-managed retention.
    """
    import tempfile
    flag = os.environ.get('DRIVEREPAIR_GUI_DEBUG', '').strip().lower()
    if flag not in {'1', 'true', 'yes', 'on'}:
        return None
    stamp = time.strftime('%Y%m%dT%H%M%S')
    candidates = [
        Path(os.environ['DRIVEREPAIR_GUI_DEBUG_LOG']) if os.environ.get('DRIVEREPAIR_GUI_DEBUG_LOG') else None,
        Path(tempfile.gettempdir()) / 'DriveRepair' / 'debug' / f'gui_debug_{stamp}.log',
    ]
    for path in candidates:
        if path is None:
            continue
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('a', encoding='utf-8') as handle:
                handle.write(
                    f'# DriveRepair Qt GUI debug start {time.strftime("%Y-%m-%dT%H:%M:%S")}\n'
                    f'# pid={os.getpid()} python={sys.executable}\n'
                    f'# argv={sys.argv!r}\n'
                    f'# retention=operator-managed local file; unset DRIVEREPAIR_GUI_DEBUG to stop\n'
                )
            _restrict_qt_debug_log_access(path)
            print(f'[DriveRepair DEBUG] Qt logging to {path}', flush=True)
            return path
        except OSError:
            continue
    return None


def launch():
    try:
        from PySide6.QtCore import Qt, QProcess, QTimer, QRectF
        from PySide6.QtGui import QColor, QFont, QPainter
        from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
            QLabel, QPushButton, QFrame, QProgressBar, QComboBox, QLineEdit, QFileDialog,
            QPlainTextEdit, QMessageBox, QCheckBox, QToolButton)
    except ImportError as exc:
        raise RuntimeError('Qt workstation requires the optional PySide6 package: python -m pip install PySide6') from exc

    debug_log_path = _qt_debug_log_path()

    def debug_trace(text: str) -> None:
        if debug_log_path is None:
            return
        line = text if text.endswith('\n') else text + '\n'
        try:
            with debug_log_path.open('a', encoding='utf-8') as handle:
                handle.write(line)
            print(line, end='', flush=True)
        except OSError:
            pass

    C = {'bg':'#0a111e','panel':'#111c2d','panel2':'#17263b','line':'#283a54',
         'text':'#eef4ff','muted':'#9ab0c8','accent':'#4d9fff','green':'#32ba9e',
         'orange':'#f7a749','red':'#f46e7c','yellow':'#e9ca60'}
    css = f'''QWidget {{ background:{C['bg']};color:{C['text']}; font-family:'Segoe UI','Inter',sans-serif; font-size:13px; }}
        QFrame#card {{ background:{C['panel']}; border:1px solid {C['line']}; border-radius:15px; }}
        QLabel#muted {{ color:{C['muted']}; }}
        QLabel#heading {{ font-size:23px; font-weight:750; }}
        QLabel#metric {{ font-size:23px; font-weight:700; }}
        QLabel#eyebrow {{ color:{C['muted']}; font-size:11px; font-weight:700; }}
        QPushButton {{ background:{C['panel2']}; border:1px solid {C['line']}; padding:12px 17px; border-radius:9px; font-weight:650; }}
        QPushButton:hover {{border:1px solid {C['accent']}; background:#203450;}}
        QPushButton:disabled {{color:#708399;}}
        QPushButton#primary {{background:#2e7be6; color:white; border:0;}}
        QPushButton#primary:hover {{background:#4295ff;}}
        QPushButton#danger {{background:#743742;border:1px solid #a95f67;}}
        QComboBox,QLineEdit {{background:{C['panel2']};border:1px solid {C['line']}; padding:11px;border-radius:8px;}}
        QComboBox QAbstractItemView {{background:{C['panel']}; color:{C['text']};}}
        QProgressBar {{height:9px; background:{C['panel2']};border:0;border-radius:4px;}}
        QProgressBar::chunk {{background:{C['accent']};border-radius:4px;}}
        QPlainTextEdit {{background:#0d1727;border:1px solid {C['line']};border-radius:8px; color:#adbed8;}}
    '''

    def card(parent_layout, *, gap=8):
        pane = QFrame()
        pane.setObjectName('card')
        lay = QVBoxLayout(pane)
        lay.setContentsMargins(18,16,18,16)
        lay.setSpacing(gap)
        parent_layout.addWidget(pane)
        return lay

    def help_icon(message: str) -> QToolButton:
        info = QToolButton()
        info.setText('ⓘ')
        info.setToolTip(message)
        info.setAccessibleName('More information')
        info.setCursor(Qt.WhatsThisCursor)
        info.setStyleSheet('QToolButton {color:#8bbce9; background:transparent; border:0; '
                           'font-size:17px; padding:2px;} QToolButton:hover {color:white;}')
        # Click also opens the full description, useful for keyboard/touch users.
        info.clicked.connect(lambda: QMessageBox.information(info, 'About this setting', message))
        return info

    class ScanMap(QWidget):
        """Fixed full-drive map; sparse samples never paint whole cells healthy."""
        def __init__(self):
            super().__init__()
            self.setMinimumHeight(130)
            self.coverage = SurfaceCoverage()
            self.setMouseTracking(True)

        @property
        def total(self):
            return self.coverage.size

        def reset(self, size):
            self.coverage.reset(max(0, int(size or 0)))
            self.update()

        def ingest(self, event):
            size = int(event.get('size') or self.total or 0)
            if size <= 0:
                return
            if size != self.total:
                self.reset(size)
            offset = int(event.get('offset') or 0)
            length = int(event.get('read_length') or event.get('length') or 0)
            if length <= 0:
                return
            slow = ((event.get('latency_ms') or 0) >
                    max(500, (event.get('median_ms') or 0) * 4))
            self.coverage.observe(offset, length, failed=bool(event.get('failed')),
                                  slow=slow)
            self.update()

        def paintEvent(self, _):
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)
            cols = 48
            rows = 8
            gap = 3
            width = max(3, (self.width() - gap * (cols - 1)) / cols)
            height = max(5, (self.height() - gap * (rows - 1)) / rows)
            p.setPen(Qt.NoPen)
            for index, cell in enumerate(self.coverage.cells):
                x = (index % cols) * (width + gap)
                y = (index // cols) * (height + gap)
                p.setBrush(QColor('#253951'))
                p.drawRoundedRect(QRectF(x, y, width, height), 2, 2)
                if cell.fraction > 0:
                    # Fill from bottom: e.g. 10% of a cell stays 90% unknown.
                    h = max(1.0, height * cell.fraction)
                    p.setBrush(QColor('#36b794'))
                    p.drawRoundedRect(QRectF(x, y + height - h, width, h), 1.5, 1.5)
                if cell.slow_reads:
                    p.setBrush(QColor('#eeaa52'))
                    p.drawRect(QRectF(x, y + 2, width, 2.5))
                if cell.read_errors:
                    # Failure is a *marker*, not a full-cell bad-sector verdict.
                    p.setBrush(QColor('#ed6472'))
                    p.drawRect(QRectF(x, y, width, 2.5))
            p.end()

        def mouseMoveEvent(self, event):
            cols, gap = 48, 3
            width = max(3, (self.width() - gap * (cols - 1)) / cols)
            height = max(5, (self.height() - gap * 7) / 8)
            col = int(event.position().x() // (width + gap))
            row = int(event.position().y() // (height + gap))
            if 0 <= col < 48 and 0 <= row < 8:
                cell = self.coverage.cells[row * cols + col]
                self.setToolTip(f'Device offsets {cell.start:,}–{cell.end:,} bytes\n'
                                f'{cell.fraction:.1%} read successfully\n'
                                f'{cell.read_errors} failed requests; {cell.slow_reads} slow reads\n'
                                'Untested portions are not known to be healthy')
            super().mouseMoveEvent(event)

    class Workstation(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle('DriveRepair | Recovery Workstation')
            self.resize(1210,850)
            self.setMinimumSize(850,640)
            self._pending = None
            self._mode = None
            self._buf = {'stdout':'','stderr':''}
            self._final_stdout = ''
            self._devices=[]
            self._job_args=[]
            self._last_job_kind=''
            self._last_good_device=None
            self._scanned=0
            self._pending_resume=None
            self._resume_poll_count=0
            self._last_progress_at=None
            self._last_phase=None
            self._last_debug_event_at=0.0
            self._last_io_offset=0
            self._last_io_length=0
            self._stop_requested=False
            self._heartbeat=QTimer(self)
            self._heartbeat.setInterval(1000)
            self._heartbeat.timeout.connect(self.check_stall)
            self._heartbeat.start()
            self._reconnect_timer=QTimer(self)
            self._reconnect_timer.setInterval(12000)
            self._reconnect_timer.timeout.connect(self.refresh_devices)
            self.proc = None
            self.inventory_proc = None
            self.setStyleSheet(css)
            central=QWidget()
            self.setCentralWidget(central)
            root=QVBoxLayout(central)
            root.setContentsMargins(22,18,22,16)
            root.setSpacing(14)
            header=QHBoxLayout()
            root.addLayout(header)
            brand=QVBoxLayout()
            label=QLabel('DriveRepair')
            label.setObjectName('heading')
            brand.addWidget(label)
            sub=QLabel('RECOVERY WORKSTATION  •  PRIVATE BY DESIGN')
            sub.setObjectName('eyebrow')
            brand.addWidget(sub)
            header.addLayout(brand)
            header.addStretch()
            self.details_button=QPushButton('Expert details')
            self.details_button.setCheckable(True)
            self.details_button.toggled.connect(self.show_details)
            header.addWidget(self.details_button)
            self.legacy=QPushButton('Legacy tools')
            self.legacy.clicked.connect(self.open_legacy)
            header.addWidget(self.legacy)
            hero = card(root)
            status_row=QHBoxLayout()
            hero.addLayout(status_row)
            self.status=QLabel('Ready to help')
            self.status.setObjectName('heading')
            status_row.addWidget(self.status)
            status_row.addWidget(help_icon('Each phase reports only evidence actually observed. A readable block is not proof of correct files, and rewriting data does not restore physical lifespan.'))
            status_row.addStretch()
            self.help=QLabel('Choose a drive and what you need to do. Nothing starts until you press Start.')
            self.help.setWordWrap(True)
            self.help.setObjectName('muted')
            hero.addWidget(self.help)
            self.progress=QProgressBar()
            self.progress.setRange(0,1000)
            self.progress.setValue(0)
            phase_row=QHBoxLayout()
            hero.addLayout(phase_row)
            self.phase_caption=QLabel('Current phase · no job')
            self.phase_caption.setObjectName('muted')
            phase_row.addWidget(self.phase_caption)
            phase_row.addStretch()
            self.phase_progress=QProgressBar()
            self.phase_progress.setRange(0,1000)
            self.phase_progress.setValue(0)
            hero.addWidget(self.phase_progress)
            total_row=QHBoxLayout()
            hero.addLayout(total_row)
            self.total_caption=QLabel('Estimated whole-job progress · staged estimate, not disk coverage')
            self.total_caption.setObjectName('muted')
            total_row.addWidget(self.total_caption)
            total_row.addStretch()
            self.overall_label=QLabel('—')
            total_row.addWidget(self.overall_label)
            hero.addWidget(self.progress)
            metrics=QHBoxLayout()
            hero.addLayout(metrics)
            self.metric_labels={}
            self.metric_headers={}
            for key,title in [('done','PROGRESS'),('read','DATA READ'),('rate','RECENT SPEED'),('avg','JOB AVERAGE'),('errors','READ ERRORS'),('eta','TIME LEFT')]:
                area=QVBoxLayout()
                m=QLabel(title)
                m.setObjectName('eyebrow')
                descriptions={'done':'Percent of planned scan work. Quick Scan samples 10% of the drive; this is not full-device coverage.',
                              'read':'Bytes actually requested from the source. Retries may count again; not always unique media coverage.',
                              'rate':'Recent transfer speed over the last five seconds. If stalled, this changes to Waiting on drive.',
                              'avg':'Total bytes attempted divided by elapsed job time. It is not the instantaneous speed.',
                              'errors':'Failed read requests. A failed request may span many sectors; this is not a count of physically defective sectors.',
                              'eta':'Estimate based on the current scan pass. It can change sharply on a failing drive and does not include future repair time.'}
                m.setToolTip(descriptions[key])
                area.addWidget(m)
                self.metric_headers[key]=m
                v=QLabel('—')
                v.setObjectName('metric')
                area.addWidget(v)
                metrics.addLayout(area,1)
                self.metric_labels[key]=v
            body=QHBoxLayout()
            root.addLayout(body,1)
            left=QVBoxLayout()
            body.addLayout(left,2)
            drive_panel=card(left)
            pick=QHBoxLayout()
            drive_panel.addLayout(pick)
            ttl=QLabel('01  Select a drive')
            ttl.setStyleSheet('font-weight:700;font-size:15px')
            pick.addWidget(ttl)
            pick.addStretch()
            self.inspect_button=QPushButton('Drive details ⓘ')
            self.inspect_button.setToolTip('Read-only OS information such as physical/logical sector size, queue limits, transport and firmware revision where available. It does NOT establish safe write permission.')
            self.inspect_button.clicked.connect(self.inspect_drive)
            pick.addWidget(self.inspect_button)
            btn=QPushButton('Refresh drives')
            btn.clicked.connect(self.refresh_devices)
            pick.addWidget(btn)
            self.device_box=QComboBox()
            drive_panel.addWidget(self.device_box)
            drive_panel.addWidget(help_icon('Check the model, capacity and serial suffix before starting. USB bridge numbers can change on reconnect. Physical writes always require renewed identity verification; read-only scans can resume using a stable media fingerprint.'))
            self.device_note=QLabel('The selected disk will be identified again before physical writes.')
            self.device_note.setWordWrap(True)
            self.device_note.setObjectName('muted')
            drive_panel.addWidget(self.device_note)
            self.profile_note=QLabel('Drive strategy: awaiting device identification')
            self.profile_note.setWordWrap(True)
            self.profile_note.setObjectName('muted')
            drive_panel.addWidget(self.profile_note)
            self.device_box.currentIndexChanged.connect(self.update_drive_profile)
            workflow=card(left)
            title=QLabel('02  Choose a goal')
            title.setStyleSheet('font-weight:700;font-size:15px')
            workflow.addWidget(title)
            goals=QHBoxLayout()
            workflow.addLayout(goals)
            for title,goal in [('Fix my drive','carequick'),('Recover files','rescue'),('Check drive','scanquick')]:
                b=QPushButton(title)
                b.clicked.connect(lambda _,g=goal:self.select_goal(g))
                goals.addWidget(b)
            advanced=QLabel('Or choose a specific operation:')
            advanced.setObjectName('muted')
            workflow.addWidget(advanced)
            self.job_box=QComboBox()
            self._jobs={
                'fix':[('Quick targeted repair (experimental)','carequick'),
                       ('Full scan + targeted repair (experimental)','carefull'),
                       ('Resume an interrupted journaled repair','careresume')],
                'recover':[('Rescue image / recover files','rescue')],
                'check':[('Check disk health (read-only)','health'),
                         ('Quick surface check (read-only)','scanquick'),
                         ('Full surface scan (read-only)','scanfull'),
                         ('Continue interrupted full scan','resume')],
            }
            self.job_box.currentIndexChanged.connect(self.choice_changed)
            workflow.addWidget(self.job_box)
            help_row=QHBoxLayout()
            workflow.addLayout(help_row)
            help_row.addWidget(help_icon('Fix: attempts verified writes only to repeatably readable weak regions after authorization. Recover: copies data to a separate image. Check: reads without writing. Use the goal buttons to show relevant operations.'))
            self.auto_resume=QCheckBox('Resume read-only full scan when the same USB drive reconnects')
            self.auto_resume.setChecked(True)
            self.auto_resume.setToolTip('Only a read-only full scan with a saved checkpoint can restart automatically. No in-place writes or RAM-only transactions restart after a disconnect.')
            help_row.addWidget(self.auto_resume,1)
            self.dest=QLineEdit()
            self.dest.setPlaceholderText('Choose an existing source image…')
            self.browse=QPushButton('Choose image…')
            self.browse.clicked.connect(self.pick_image)
            pathrow=QHBoxLayout()
            pathrow.addWidget(self.dest,1)
            pathrow.addWidget(self.browse)
            workflow.addLayout(pathrow)
            self.opts=QLabel('Automatic settings  •  Read-only by default  •  No uploads')
            self.opts.setObjectName('muted')
            workflow.addWidget(self.opts)
            act=QHBoxLayout()
            workflow.addLayout(act)
            self.start=QPushButton('Start selected job')
            self.start.setObjectName('primary')
            self.start.clicked.connect(self.start_job)
            act.addWidget(self.start,1)
            self.stop=QPushButton('Stop')
            self.stop.setObjectName('danger')
            self.stop.setEnabled(False)
            self.stop.clicked.connect(self.stop_job)
            act.addWidget(self.stop)
            right=QVBoxLayout()
            body.addLayout(right,3)
            map_card=card(right)
            map_head=QHBoxLayout()
            map_card.addLayout(map_head)
            map_title=QLabel('Full-drive surface coverage')
            map_title.setStyleSheet('font-weight:700;font-size:15px')
            map_head.addWidget(map_title)
            map_head.addWidget(help_icon('Each cell always represents the same fixed portion of the ENTIRE drive. Only the portion actually read fills green. Orange/red markers show slow or failed requests, not confirmed physical damage. Hover over a cell for its offsets and coverage.'))
            map_head.addStretch()
            self.map=ScanMap()
            map_card.addWidget(self.map)
            legend=QLabel('<span style="color:#36b794">■</span> Readable     '
                          '<span style="color:#eeaa52">■</span> Slow     '
                          '<span style="color:#ed6472">■</span> Read error     '
                          '<span style="color:#253951">■</span> Untested')
            legend.setTextFormat(Qt.RichText)
            map_card.addWidget(legend)
            self.advice=QLabel('A green block means data could be read. It does not prove file integrity or long-term drive health.')
            self.advice.setWordWrap(True)
            self.advice.setObjectName('muted')
            map_card.addWidget(self.advice)
            result_card=card(right)
            self.result=QLabel('No job running')
            self.result.setStyleSheet('font-size:16px;font-weight:700')
            result_card.addWidget(self.result)
            self.explain=QLabel('Recovery reports will show what is verified, unresolved, and untested.')
            self.explain.setWordWrap(True)
            self.explain.setObjectName('muted')
            result_card.addWidget(self.explain)
            self.log=QPlainTextEdit()
            self.log.setReadOnly(True)
            self.log.setMaximumBlockCount(4000)
            self.log.setVisible(bool(debug_log_path))
            root.addWidget(self.log)
            if debug_log_path is not None:
                self.log.appendPlainText(f'Debug tracking ON — {debug_log_path}')
                debug_trace(f'Debug tracking ON — {debug_log_path}\n')
                self.setWindowTitle(self.windowTitle() + ' [DEBUG]')
            self.select_goal('scanquick')
            QTimer.singleShot(100,self.refresh_devices)
        def update_drive_profile(self, _index=None):
            d=self.selected()
            if not d:
                self.profile_note.setText('Drive strategy: waiting for a selected device')
                return
            from .media_profiles import identify_profile
            try:
                profile=identify_profile(model=str(d.get('model') or ''),
                    bus=str(d.get('bus') or ''), sector=int(d.get('sector_size') or 512))
                self.profile_note.setText(
                    f'Drive strategy: {profile.kind.upper()} · {profile.evidence}. '
                    f'{profile.maintenance_note}')
                self.profile_note.setToolTip('Advisory profile only. USB bridges may obscure physical media. '
                    'No profile authorizes write or certifies health.')
            except (ValueError,TypeError):
                self.profile_note.setText('Drive strategy: unverified geometry — read-only until resolved')

        def select_goal(self, goal):
            family = ('fix' if goal.startswith('care') else
                      'recover' if goal == 'rescue' else 'check')
            self.job_box.blockSignals(True)
            self.job_box.clear()
            for title, key in self._jobs[family]:
                self.job_box.addItem(title, key)
            for i in range(self.job_box.count()):
                if self.job_box.itemData(i) == goal:
                    self.job_box.setCurrentIndex(i)
                    break
            self.job_box.blockSignals(False)
            self.choice_changed()
        def check_stall(self):
            if (self.proc and self.proc.state()!=QProcess.NotRunning
                    and self._last_progress_at is not None
                    and time.monotonic()-self._last_progress_at>8):
                self.metric_labels['rate'].setText('Waiting on drive')
                elapsed=int(time.monotonic()-self._last_progress_at)
                self.help.setText(f'Waiting {elapsed}s for the storage driver or USB device. '
                    'No new I/O result; the operation is NOT necessarily progressing. '
                    'Stop waits for a safe boundary and may not interrupt a blocked kernel request.')
                self.result.setText('Drive I/O stalled — investigation may be blocked inside Windows')
                self.explain.setText(f'Last request: byte offset {self._last_io_offset:,} · '
                    f'length {self._last_io_length:,} bytes · {elapsed}s without a result. '
                    'Check Expert details for the most recent observations.')
        def show_details(self, yes): self.log.setVisible(yes)
        def note_log(self, text: str) -> None:
            self.log.appendPlainText(text)
            debug_trace(text)
        def open_legacy(self):
            QMessageBox.information(self,'Legacy toolkit','For advanced file-system, forensic, firmware-information and refresh tools, run:  python -m driverepair_desktop gui-legacy  (the existing Tk interface).')
        def pick_image(self):
            path,_=QFileDialog.getOpenFileName(self,'Select source disk image','','Disk images (*.img *.dd *.raw);;All files (*)')
            if path:
                self.dest.setText(path)
        def choice_changed(self):
            kind=self.job_box.currentData()
            is_image=kind=='rescue'
            self.dest.setVisible(is_image)
            self.browse.setVisible(is_image)
            self.auto_resume.setVisible(kind in {'scanfull','resume','carefull'})
            hints={'health':'Reads SMART attributes where available; no physical writes.',
                   'scanquick':'Samples at least 10% of the entire drive with distributed random locations; no writes.',
                   'scanfull':'Reads the full address space, saving a resumable local checkpoint.',
                   'carequick':'Investigates slow regions; may rewrite only consistently readable targets after consent.',
                   'carefull':'Full scan and bounded repair. Writes require separate explicit approval.',
                   'careresume':'Reopens a previously durable journal on a separate healthy disk and verifies patient identity before resuming interrupted writes.',
                   'rescue':'Rescue data from an existing image to a new file, leaving the original unchanged.',
                   'resume':'Rechecks identity before continuing the saved read-only scan position.'}
            self.opts.setText(hints.get(kind,''))
        def refresh_devices(self):
            if self.inventory_proc and self.inventory_proc.state()!=QProcess.NotRunning:
                return
            self.device_note.setText('Looking for external drives…')
            self.inventory_proc=QProcess(self)
            self.inventory_proc.setProgram(cli_prefix()[0])
            self.inventory_proc.setArguments(cli_prefix()[1:]+['list','--json'])
            self.inventory_proc.finished.connect(self.inventory_done)
            self.inventory_proc.start()
        def inventory_done(self,code,_status):
            stdout=bytes(self.inventory_proc.readAllStandardOutput()).decode('utf-8','replace')
            stderr=bytes(self.inventory_proc.readAllStandardError()).decode('utf-8','replace')
            if code!=0:
                self.device_note.setText('Device discovery failed. Reconnect the USB dock and retry; never bypass identity checks.')
                self.note_log(stderr[:3000])
                return
            try:
                data=json.loads(stdout)
            except (ValueError,TypeError):
                self.device_note.setText('Could not interpret drive inventory')
                return
            prev=self.device_box.currentData()
            self.device_box.clear()
            self._devices=data
            for d in data:
                self.device_box.addItem(f"{d['model']}    •    {display_size(d['size_bytes'])}    •    {d['bus']}    •    {d.get('serial_suffix','')}",d)
            if prev:
                for i,d in enumerate(data):
                    if d.get('id')==prev.get('id') and d.get('identity_hint')==prev.get('identity_hint'):
                        self.device_box.setCurrentIndex(i)
                        break
            self.device_note.setText(f'{len(data)} external drive(s) available. Fresh identity required before writes.')
            pending=self._pending_resume
            if pending and self.auto_resume.isChecked() and not (self.proc and self.proc.state()!=QProcess.NotRunning):
                matches=[dev for dev in data if dev.get('resume_hint') and
                         dev.get('resume_hint')==pending['resume_hint'] and
                         dev.get('size_bytes')==pending['size_bytes']]
                if len(matches)==1:
                    self._pending_resume=None
                    self._reconnect_timer.stop()
                    self.stop.setEnabled(False)
                    self._last_job_kind='resume'
                    self._last_good_device=matches[0]
                    self.result.setText('Same drive detected — resuming read-only scan')
                    self.run_command(['scan','--device',matches[0]['id'],'--mode','full',
                                      '--ack-risk','--resume-scan','--scan-checkpoint',pending['checkpoint'],
                                      '--progress-jsonl','--cooperative-stop-stdin','--json'])
                elif len(matches)>1:
                    self._reconnect_timer.stop()
                    self.result.setText('Ambiguous disk identities — manual verification required')
        def selected(self):return self.device_box.currentData()
        def inspect_drive(self):
            d=self.selected()
            if not d:
                QMessageBox.information(self,'Drive details','Select a drive first.')
                return
            self.inspect_proc=QProcess(self)
            self.inspect_proc.setProgram(cli_prefix()[0])
            self.inspect_proc.setArguments(cli_prefix()[1:]+['inspect-storage','--device',d['id'],'--json'])
            self.inspect_proc.finished.connect(self.inspect_done)
            self.inspect_proc.start()
            def bounded_inspection():
                if self.inspect_proc and self.inspect_proc.state()!=QProcess.NotRunning:
                    self.inspect_proc.kill()
                    self.result.setText('OS drive inspection timed out')
                    self.explain.setText('Windows/USB driver may be unresponsive. This is not proof of damaged sectors.')
            QTimer.singleShot(9000,bounded_inspection)
        def inspect_done(self,exit_code,_status):
            if not getattr(self,'inspect_proc',None):
                return
            raw=bytes(self.inspect_proc.readAllStandardOutput()).decode('utf-8','replace')
            err=bytes(self.inspect_proc.readAllStandardError()).decode('utf-8','replace')
            if exit_code:
                self.note_log('Host drive inspection unavailable: '+err[:1000])
                QMessageBox.warning(self,'Drive details unavailable',
                    'The operating system could not supply drive information right now. '
                    'No disk writes were attempted.')
                return
            try:
                info=json.loads(raw)
            except (ValueError,TypeError):
                info={}
            lines=[f'{key.replace("_"," ").title()}: {value}'
                   for key,value in info.items() if value is not None and key!='notes']
            lines.append(str(info.get('notes') or 'Unverified host metadata'))
            QMessageBox.information(self,'Drive details (read-only)','\n'.join(lines)[:4000])
        def start_job(self):
            self._pending_resume=None
            self._reconnect_timer.stop()
            if self.proc and self.proc.state()!=QProcess.NotRunning:
                return
            kind=self.job_box.currentData()
            d=self.selected()
            if kind=='rescue':
                src=self.dest.text().strip()
                if not Path(src).is_file():
                    QMessageBox.warning(self,'Source required','Select a readable source image.')
                    return
                out,_=QFileDialog.getSaveFileName(self,'New recovery image (must not exist)','recovered.img','Disk image (*.img);;All files (*)')
                if not out:
                    return
                if os.path.exists(out):
                    QMessageBox.warning(self,'Destination exists','Choose a new file; no existing image will be overwritten.')
                    return
                args=['rescue-image','--image',src,'--output',out,'--multi-pass','--progress-jsonl','--no-live-dashboard','--json']
            else:
                if not d:
                    QMessageBox.warning(self,'Choose a drive','Connect a drive and select it first.')
                    return
                dev=d['id']
                if kind=='health':
                    args=['health','--device',dev,'--json']
                elif kind in {'scanquick','scanfull','resume'}:
                    if kind=='scanquick':
                        from .media_profiles import format_quick_preflight
                        pre=QMessageBox.question(
                            self,'Quick surface check preflight',
                            format_quick_preflight(int(d.get('size_bytes') or 0)) +
                            '\n\nRead-only diagnosis — not Quick Repair. Continue?',
                            QMessageBox.Yes | QMessageBox.No)
                        if pre!=QMessageBox.Yes:
                            return
                    args=['scan','--device',dev,'--mode','full' if kind in ('scanfull','resume') else 'triage',
                          '--progress-jsonl','--cooperative-stop-stdin','--json']
                    if kind=='scanquick':
                        from .guided_repair import tuned_scan
                        plan=tuned_scan(size=int(d['size_bytes']),sector=int(d['sector_size']),
                                        mode='quick',bus=str(d.get('bus') or ''),
                                        model=str(d.get('model') or ''))
                        args+=['--chunk-mib',str(plan['chunk']//(1024*1024)),
                               '--samples',str(plan['samples']),'--max-errors','10000',
                               '--compare-suspects','--randomize-samples']
                    if kind in ('scanfull','resume'):
                        args+=['--ack-risk']
                    if kind=='resume':
                        args+=['--resume-scan']
                else:
                    if kind=='carequick':
                        from .media_profiles import format_quick_preflight
                        pre=QMessageBox.question(
                            self,'Quick Repair preflight',
                            format_quick_preflight(int(d.get('size_bytes') or 0)) +
                            '\n\nQuick Repair may rewrite slow-but-readable regions after exclusive volume lock. Continue?',
                            QMessageBox.Yes | QMessageBox.No)
                        if pre!=QMessageBox.Yes:
                            return
                    answer=QMessageBox.question(self,'Experimental physical writes',
                        'DriveRepair can permanently damage data on a failing drive.\n\n'
                        'Only consistently readable regions are eligible. A RAM-only write has no crash recovery.\n\n'
                        'For an external drive with a Windows letter, DriveRepair attempts an exclusive '
                        'lock and temporary dismount before the surface check when auto-lock is enabled, '
                        'and again immediately before any rewrite, only if no files are in use. '
                        'It will not forcibly close applications or remove the drive letter permanently.\n\n'
                        'Continue to device confirmation?',
                        QMessageBox.Yes | QMessageBox.No)
                    if answer!=QMessageBox.Yes:
                        return
                    from PySide6.QtWidgets import QInputDialog
                    typed,ok=QInputDialog.getText(self,'Confirm target disk',
                        f"Type this disk fingerprint to allow in-place writes:  {d['identity_hint']}")
                    if not ok or typed.strip()!=d['identity_hint']:
                        QMessageBox.warning(self,'Not authorized','Fingerprint did not match. No job started.')
                        return
                    journal_args=[]
                    if kind=='careresume':
                        location=QFileDialog.getExistingDirectory(self,'Select the EXACT existing DriveRepair repair journal folder (not a recovery image)')
                        if not location:
                            return
                        if not os.path.isfile(os.path.join(location,'meta.json')):
                            QMessageBox.warning(self,'Journal not found','Select a repair journal containing meta.json. The selected patient is not being written.')
                            return
                        proceed=QMessageBox.warning(self,'Resume a physical rewrite',
                            'This resumes ONLY the transaction queue recorded in the chosen journal. '
                            'Device identity and separate journal storage will be reverified. '
                            'No new scan, new write targets, or firmware operations are authorized. Continue?',
                            QMessageBox.Yes | QMessageBox.No)
                        if proceed!=QMessageBox.Yes:
                            return
                        journal_args=['--journal-backend','disk','--journal',location,'--resume']
                    else:
                        dialog=QMessageBox(self)
                        dialog.setWindowTitle('Choose repair safety')
                        dialog.setText('Where should DriveRepair protect the original bytes during a rewrite?')
                        dialog.setInformativeText('A small durable journal on another healthy drive makes a torn transaction potentially recoverable. RAM-only creates no file but cannot recover an interrupted write after memory is lost.')
                        durable=dialog.addButton('Use separate-drive journal (recommended)',QMessageBox.AcceptRole)
                        volatile=dialog.addButton('RAM-only — high risk',QMessageBox.DestructiveRole)
                        dialog.addButton(QMessageBox.Cancel)
                        dialog.exec()
                        selected_choice=dialog.clickedButton()
                        if selected_choice==durable:
                            parent=QFileDialog.getExistingDirectory(self,'Choose journal parent folder on a DIFFERENT healthy drive')
                            if not parent:
                                return
                            location=os.path.join(parent,'DriveRepairJournal-'+d['identity_hint'])
                            if os.path.exists(location):
                                QMessageBox.warning(self,'Journal already exists',
                                    'An existing journal may contain recoverable patient data. Do not overwrite it. '
                                    'Use Resume interrupted repair or select a new empty parent folder.')
                                return
                            journal_args=['--journal-backend','disk','--journal',location]
                        elif selected_choice==volatile:
                            confirm=QMessageBox.warning(self,'Volatile memory risk',
                                'Continue with NO backup and RAM-only journal? Power loss, USB resets or a crash can permanently destroy the active region. '
                                'Interrupted RAM-only writes cannot be resumed. This is an experimental mode.',
                                QMessageBox.Yes | QMessageBox.No)
                            if confirm!=QMessageBox.Yes:
                                return
                            journal_args=['--journal-backend','memory','--ack-volatile-journal','--ack-dock-power-backed']
                        else:
                            return
                    save_scan_map=False
                    if kind=='carefull':
                        save_scan_map = QMessageBox.question(
                            self,'Resume scanning after USB disconnect',
                            'Save a small, private read-only scan checkpoint locally? '
                            'This stores offsets and observations, not recovered sector bytes.',
                            QMessageBox.Yes | QMessageBox.No)==QMessageBox.Yes
                    args=['care-external','--cooperative-stop-stdin','--device',dev,'--mode','full' if kind=='carefull' else 'quick',
                          *journal_args,'--auto-lock-volumes','--confirm-identity',d['identity_hint'],
                          '--ack-risk','--ack-destructive','--ack-no-backup','--ack-data-loss-risk',
                          '--ack-usb-bridge-risk','--ack-unvalidated-hardware','--ack-unknown-health',
                          '--progress-jsonl','--json']
                    if save_scan_map:
                        args+=['--scan-checkpoint','auto']
            self._last_good_device=d
            self._last_job_kind=kind
            self._job_args=args
            self.run_command(args)
        def run_command(self,args):
            self.progress.setValue(0)
            self.phase_progress.setValue(0)
            self.overall_label.setText('0% estimated')
            self._stop_requested=False
            self.map.reset(int((self.selected() or {}).get('size_bytes') or 0))
            self.result.setText('Running — monitoring the device')
            self.explain.setText('Unknown regions remain unknown until observed.')
            self.status.setText('Working…')
            self.help.setText('Read-only where possible; no results are inferred from the progress bar.')
            self._buf={'stdout':'','stderr':''}
            self._final_stdout=''
            self._scanned=0
            self._last_progress_at=time.monotonic()
            self._last_phase=None
            self._last_debug_event_at=0.0
            self._last_io_offset=0
            self._last_io_length=0
            self._last_error=None
            self.proc=QProcess(self)
            self.proc.setProgram(cli_prefix()[0])
            self.proc.setArguments(cli_prefix()[1:]+args)
            self.proc.readyReadStandardError.connect(lambda:self.consume('stderr'))
            self.proc.readyReadStandardOutput.connect(lambda:self.consume('stdout'))
            self.proc.finished.connect(self.job_done)
            self.stop.setText('Stop')
            self.start.setEnabled(False)
            self.stop.setEnabled(True)
            self.proc.start()
        def consume(self,channel):
            if not self.proc:
                return
            data=bytes(self.proc.readAllStandardError() if channel=='stderr' else self.proc.readAllStandardOutput()).decode('utf-8','replace')
            if channel == 'stdout':
                self._final_stdout += data
                return
            self._buf[channel]+=data
            while '\n' in self._buf[channel]:
                line,self._buf[channel]=self._buf[channel].split('\n',1)
                try:
                    obj=json.loads(line)
                except (ValueError,TypeError):
                    if line:
                        self.note_log(line[:1200])
                        if line.startswith('Error:'):
                            self._last_error=line[6:].strip()[:600]
                    continue
                if isinstance(obj,dict) and obj.get('type')=='progress':
                    self.progress_event(obj)
                else:
                    self._pending=obj
        def progress_event(self,event):
            self._last_progress_at=time.monotonic()
            self._last_io_offset=int(event.get('offset') or 0)
            self._last_io_length=int(event.get('read_length') or 0)
            # Trace actionable telemetry, not just final errors. Throttle logs
            # independently of the 10Hz GUI updates to avoid filling disks.
            if debug_log_path and (self._last_progress_at-self._last_debug_event_at>=4 or
                                   str(event.get('phase'))!=self._last_phase):
                fields={k:event.get(k) for k in
                    ('phase','offset','read_length','investigation_state',
                     'investigation_reads','investigation_total','read_error_chunks',
                     'attempted_bytes','rewritten_bytes','verified_bytes',
                     'speed_bps','eta_seconds') if event.get(k) is not None}
                debug_trace('IO_TELEMETRY '+json.dumps(fields,sort_keys=True)+'\n')
                self._last_debug_event_at=self._last_progress_at
            self.status.setText(str(event.get('phase') or 'WORKING').replace('_',' ').title())
            phase=str(event.get('phase') or 'WORKING').upper()
            if phase != self._last_phase:
                self._last_phase=phase
                self.metric_labels['rate'].setText('Measuring…')
                self.metric_labels['avg'].setText('Measuring…')
            self.metric_headers['read'].setText('DATA REWRITTEN' if phase=='REFRESH' else 'DATA READ')
            phase_number={'SCANNING':1, 'INVESTIGATING':2, 'REFRESH':3}.get(phase)
            self.phase_caption.setText(
                f'Phase {phase_number} of up to 3 · {phase.title()}' if phase_number and
                self._last_job_kind.startswith('care') else f'Current phase · {phase.title()}')
            size=int(event.get('size') or self.map.total or 0)
            pct=progress_percent(event,size)
            if phase=='INVESTIGATING':
                reads=int(event.get('investigation_reads') or 0)
                limit=max(1,int(event.get('investigation_total') or 1))
                pct=min(100.0,100*reads/limit)
                self.help.setText(f'Bounded investigation · {reads} of {limit} maximum read attempts. '
                    'A single Windows I/O may still block longer than the soft time limit.')
            self.phase_progress.setValue(max(0,min(1000,round(10*pct))))
            overall=estimated_job_percent(event,guided=self._last_job_kind.startswith('care'))
            self.progress.setValue(max(0,min(1000,round(10*overall))))
            self.overall_label.setText(f'{overall:.1f}% estimated' if self._last_job_kind.startswith('care')
                                      else f'{overall:.1f}% of current job')
            self.metric_labels['done'].setText(f'{pct:.1f}%')
            self.metric_labels['eta'].setText(format_eta(event.get('eta_seconds')))
            if event.get('attempted_bytes') is not None:
                self.metric_labels['read'].setText(display_size(event['attempted_bytes']))
            elif event.get('rewritten_bytes') is not None:
                self.metric_labels['read'].setText(display_size(event['rewritten_bytes']))
            if event.get('read_error_chunks') is not None:
                self.metric_labels['errors'].setText(str(event['read_error_chunks']))
            if event.get('speed_bps') is not None:
                self.metric_labels['rate'].setText(display_size(event['speed_bps'])+'/s')
            if event.get('average_speed_bps') is not None:
                self.metric_labels['avg'].setText(display_size(event['average_speed_bps'])+'/s')
            if phase!='INVESTIGATING':
                self.help.setText(str(event.get('message') or 'Checking device…'))
            self.map.ingest(event)
            self.advice.setText(f'Full-drive map: {self.map.coverage.coverage_pct:.2f}% read successfully. '
                                'Colored stripes mark observations, not full-region certification.')
        def job_done(self,exit_code,_status):
            self.consume('stdout')
            self.consume('stderr')
            user_stop_requested = self._stop_requested
            self.start.setEnabled(True)
            self.stop.setEnabled(False)
            self.metric_labels['eta'].setText('—')
            self.proc=None
            self._stop_requested=False
            if exit_code==0:
                self.progress.setValue(1000)
                self.phase_progress.setValue(1000)
                self.overall_label.setText('100% of planned job · review findings')
            try:
                result=json.loads(self._final_stdout)
            except (ValueError,TypeError):
                result=self._pending if isinstance(self._pending,dict) else {}
                if self._final_stdout.strip():
                    self.note_log(self._final_stdout[-3000:])
            if not isinstance(result,dict):
                result={}
            text=str(result.get('status') or ('Completed' if exit_code==0 else 'Stopped / failed'))
            self.status.setText(text.replace('_',' ').title())
            if user_stop_requested and exit_code!=0:
                self.result.setText('Stopped by operator — incomplete scan')
                self.explain.setText('The requested stop has ended the child process. '
                    'Previously observed errors are retained in the log; unscanned ranges remain unknown. '
                    'A forced stop does not prove the pending Windows read completed.')
            elif exit_code==0:
                coverage=result.get('surface_coverage_pct')
                if coverage is None and isinstance(result.get('scan'), dict):
                    coverage=result['scan'].get('surface_coverage_pct')
                coverage_txt=(f' Measured coverage ≈ {float(coverage):.1f}%.'
                              if isinstance(coverage,(int,float)) else '')
                status_code=str(result.get('status') or '')
                if self._last_job_kind in ('scanquick','scanfull','resume') or 'surface_coverage_pct' in result:
                    if status_code.startswith('completed_with_'):
                        self.result.setText(f'Scan complete with findings ({status_code})')
                    else:
                        self.result.setText('Scan complete — diagnosis only')
                    self.explain.setText(
                        f'Read-only diagnosis finished.{coverage_txt} '
                        'This is not Quick Repair and does not rewrite sectors. '
                        'A completed read is not proof of file integrity.')
                else:
                    self.result.setText('Job finished — review results')
                    self.explain.setText(
                        f'A completed read or readback match is not proof of file integrity or restored lifespan.'
                        f'{coverage_txt}')
            elif result.get('status') == 'repair_blocked_prewrite_access':
                self.result.setText('Scan preserved — Windows blocked physical repair')
                self.explain.setText(str(result.get('error') or 'No lockable volume handle')[:280] +
                    ' · No in-place writes were performed. Read-only rescue is still available. '
                    'Do not bypass exclusive access on a RAW or unknown partition.')
                scan = result.get('scan') if isinstance(result.get('scan'), dict) else {}
                if scan.get('readable_bytes') is not None:
                    self.metric_labels['read'].setText(display_size(scan['readable_bytes']))
                if scan.get('read_error_chunks') is not None:
                    self.metric_labels['errors'].setText(str(scan['read_error_chunks']))
            elif 'device' in text or 'identity' in text or 'access' in text or 'discon' in text or result.get('scan',{}).get('status')=='aborted_device_or_access_error':
                self.result.setText('Drive connection interrupted')
                self.explain.setText('Reconnect the same drive, refresh the list, and select “Continue interrupted full scan”. Reverification is mandatory; no write restarts automatically.')
            else:
                self.result.setText(f'Stopped / attention needed  ({exit_code})')
                error = getattr(self, '_last_error', None)
                if error and ('volume is in use' in error.lower() or
                              'cannot open patient volume' in error.lower()):
                    self.result.setText('Close files on the selected drive')
                    self.explain.setText('DriveRepair could not safely lock the volume. Close File Explorer, backup, '
                                         'antivirus and other programs using the drive, then retry. '
                                         'No forceful dismount was attempted.')
                else:
                    self.explain.setText(error or 'Open Expert details for the specific error. No health claim is made.')
            scan_report=result.get('scan') if isinstance(result.get('scan'),dict) else {}
            scan_checkpoint=result.get('scan_checkpoint') or scan_report.get('scan_checkpoint')
            if scan_checkpoint:
                self.note_log('Scan checkpoint: '+str(scan_checkpoint))
            scan_state=result.get('status')
            scan_interrupted=(scan_state=='aborted_device_or_access_error' or
                              scan_report.get('status')=='aborted_device_or_access_error')
            if (exit_code != 0 and self.auto_resume.isChecked()
                    and self._last_job_kind in ('scanfull','resume','carefull')
                    and isinstance(scan_checkpoint,str)
                    and scan_interrupted and not result.get('repair')):
                previous=self._last_good_device or {}
                if previous.get('resume_hint'):
                    self._pending_resume={'resume_hint':previous['resume_hint'],
                                          'size_bytes':previous.get('size_bytes'),
                                          'checkpoint':scan_checkpoint}
                    self.result.setText('Waiting for the same USB drive to reconnect')
                    self.explain.setText('Read-only resume is armed. No write automatically resumes. '
                                         'Press Cancel reconnect to stop watching.')
                    self.stop.setText('Cancel reconnect')
                    self.stop.setEnabled(True)
                    self._reconnect_timer.start()
            if 'read_error_chunks' in result:
                self.metric_labels['errors'].setText(str(result['read_error_chunks']))
        def closeEvent(self, event):
            if self.proc and self.proc.state()!=QProcess.NotRunning:
                if self._last_job_kind in ('carefull','carequick','careresume'):
                    QMessageBox.warning(self,'Write in progress',
                        'Please keep DriveRepair open during the in-place transaction. '
                        'The engine does not yet support verified cooperative write cancellation.')
                    event.ignore()
                    return
                answer=QMessageBox.question(self,'Scan in progress',
                    'Stop the read-only job and close the workstation?',
                    QMessageBox.Yes | QMessageBox.No)
                if answer!=QMessageBox.Yes:
                    event.ignore()
                    return
                if self._last_job_kind in ('carefull','carequick','careresume'):
                    self.proc.write(b'STOP\n')
                    event.ignore()
                    self.result.setText('Stop requested — waiting for safe transaction boundary')
                    return
                self.proc.terminate()
                if not self.proc.waitForFinished(2500):
                    self.proc.kill()
                    self.proc.waitForFinished(1000)
            event.accept()

        def stop_job(self):
            if self._pending_resume:
                self._pending_resume=None
                self._reconnect_timer.stop()
                self.stop.setEnabled(False)
                self.stop.setText('Stop')
                self.result.setText('Automatic reconnect cancelled')
                return
            if not self.proc or self.proc.state()==QProcess.NotRunning:
                return
            if self._stop_requested:
                return
            self._stop_requested=True
            if self._last_job_kind in ('carefull','carequick','careresume'):
                self.proc.write(b'STOP\n')
                self.result.setText('Stop requested — waiting for safe transaction boundary')
                self.explain.setText('No write is interrupted mid-transaction. A blocked Windows read '
                    'cannot be forced to finish; do not disconnect while a rewrite is active.')
            elif self._last_job_kind in ('scanquick','scanfull','resume'):
                self.proc.write(b'STOP\n')
                self.result.setText('Stop requested — waiting for the active read to finish')
                self.explain.setText('No additional scan reads are scheduled after STOP is acknowledged. '
                    'If Windows never returns the active I/O, DriveRepair will escalate to process termination.')
                QTimer.singleShot(8000,self._escalate_read_only_stop)
            else:
                self.proc.terminate()
                QTimer.singleShot(6000,self._finish_read_only_stop)
                self.result.setText('Stopping read-only operation…')
            self.stop.setEnabled(False)

        def _escalate_read_only_stop(self):
            if (self._stop_requested and self.proc and
                    self.proc.state()!=QProcess.NotRunning and
                    self._last_job_kind in ('scanquick','scanfull','resume')):
                self.result.setText('Windows I/O still blocked — requesting process termination')
                self.note_log('Cooperative read-only STOP was not acknowledged in 8 seconds; '
                              'requesting subprocess termination, not disk power cycling.')
                self.proc.terminate()
                QTimer.singleShot(6000,self._finish_read_only_stop)

        def _finish_read_only_stop(self):
            if (self._stop_requested and self.proc and
                    self.proc.state()!=QProcess.NotRunning and
                    self._last_job_kind not in ('carefull','carequick','careresume')):
                self.note_log('Read-only subprocess did not exit after termination; forcing exit. The last kernel I/O result is UNKNOWN.')
                self.proc.kill()
    app=QApplication.instance() or QApplication(sys.argv)
    app.setFont(QFont('Segoe UI', 10))
    win=Workstation()
    win.show()
    if os.environ.get('DRIVEREPAIR_QT_SMOKE') == '1':
        QTimer.singleShot(850, app.quit)
    return app.exec()


if __name__ == '__main__':
    sys.exit(launch())
