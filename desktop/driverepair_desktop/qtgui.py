"""DriveRepair Workstation (PySide6, optional).

The Qt process never opens patient media. All I/O is done by the existing
isolated CLI, whose safety checks are authoritative. This is a deliberately
small front-end, not an alternate disk-repair engine.
"""
from __future__ import annotations

import json
import math
from collections import deque
import os
from pathlib import Path

from .surface_map import SurfaceCoverage
from .release_policy import PUBLIC_BETA_IMAGE_ONLY, REPAIR_BETA_GUARDED
from .rates import choose_speed
from .workstation_ui import (
    WORKSPACES, can_start, operation_impact, operation_family, operator_summary,
    repair_presentation, drive_inspection_text,
)
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
    if event.get('workflow') == 'rescue':
        if str(event.get('phase', '')).upper() == 'RETRY':
            retry_total = int(event.get('retry_total_bytes') or 0)
            if retry_total > 0:
                remaining = min(retry_total, max(0, int(event.get('retry_remaining_bytes') or 0)))
                return 100.0 * (retry_total - remaining) / retry_total
        total = int(event.get('total_bytes') or 0)
        return max(0.0, min(100.0, 100.0 * int(event.get('processed_bytes') or 0) / total)) if total else 0.0
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
        # All selected writes may be finished, but independent postverification
        # and health comparison have not yet returned. Never show 100% here.
        return min(99.0, 75.0 + pct * 0.25)
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
        from PySide6.QtCore import Qt, QProcess, QTimer, QRectF, QPointF, QSettings, QUrl
        from PySide6.QtGui import QColor, QFont, QPainter, QKeySequence, QShortcut, QPen, QPainterPath, QLinearGradient, QDesktopServices
        from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
            QLabel, QPushButton, QFrame, QProgressBar, QComboBox, QLineEdit, QFileDialog,
            QPlainTextEdit, QMessageBox, QCheckBox, QToolButton, QScrollArea, QGridLayout,
            QDialog, QListWidget, QSizePolicy, QAbstractItemView, QInputDialog)
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

    # Same restrained workbench hierarchy as Repository Detective, adapted to
    # a storage appliance: dark navy surfaces, teal focus, meaningful warnings.
    C = {'bg':'#0c1420', 'sidebar':'#101b2a', 'panel':'#142133',
         'panel2':'#1b2b40', 'line':'#293c51', 'text':'#eff5fb',
         'muted':'#aebfd0', 'accent':'#40cfb5', 'green':'#40cfb5',
         'orange':'#f1b45e', 'red':'#f07e87', 'yellow':'#e6ca75'}
    css = f'''QWidget {{ background:{C['bg']}; color:{C['text']}; font-family:'Segoe UI',sans-serif; font-size:13px; }}
        QFrame#sidebar {{ background:{C['sidebar']}; border-right:1px solid {C['line']}; }}
        QFrame#card {{ background:{C['panel']}; border:1px solid {C['line']}; border-radius:14px; }}
        QFrame#statTile {{ background:#1a2d42; border:1px solid #29435c; border-radius:10px; }}
        QFrame#actionDock {{ background:{C['sidebar']}; border-top:1px solid {C['line']}; }}
        QScrollArea {{ border:0; }}
        QScrollBar:vertical {{ background:{C['bg']}; width:10px; }}
        QScrollBar::handle:vertical {{background:#344961; border-radius:5px;min-height:32px;}}
        QLabel {{ background:transparent; }}
        QLabel#muted {{ color:{C['muted']}; }}
        QLabel#heading {{ font-size:24px; font-weight:750; }}
        QLabel#metric {{ font-size:20px; font-weight:700; color:#f6fcff; }}
        QLabel#eyebrow {{ color:{C['muted']}; font-size:11px; font-weight:700; }}
        QLabel#section {{ font-size:16px; font-weight:700; }}
        QLabel#riskTag {{ color:{C['accent']}; background:#183b40; border:1px solid #285e60; border-radius:7px; padding:6px 10px; font-weight:700; }}
        QLabel#warningTag {{ color:{C['orange']}; background:#3b3028; border:1px solid #755239; border-radius:7px; padding:6px 10px; font-weight:700; }}
        QPushButton {{ background:{C['panel2']}; border:1px solid {C['line']}; padding:8px 12px; border-radius:7px; font-weight:650; }}
        QPushButton:hover {{ border:1px solid {C['accent']}; background:#24384b; }}
        QPushButton:focus, QComboBox:focus, QLineEdit:focus, QPlainTextEdit:focus {{ border:2px solid {C['accent']}; }}
        QPushButton:disabled {{ color:#8394a6; background:#1a2636; border-color:#2a3545; }}
        QPushButton#nav {{ text-align:left; padding:10px 13px; background:transparent; border:1px solid transparent; border-radius:7px; }}
        QPushButton#nav:hover {{ background:#1c3042; }}
        QPushButton#nav:checked {{ background:#204344; color:#95ffea; border-left:3px solid {C['accent']}; }}
        QPushButton#goal:checked {{ background:#204344; border:2px solid {C['accent']}; color:white; }}
        QPushButton#primary {{ background:#269b90; color:#ffffff; border:1px solid #42beae; font-weight:750; }}
        QPushButton#primary:hover {{ background:#2cb8a4; }}
        QPushButton#danger {{ background:#b94751; color:#ffffff; border:1px solid #ee8c91; font-weight:750; }}
        QPushButton#danger:hover {{ background:#d75962; }}
        QPushButton#danger:disabled {{ background:#372931; color:#a98b92; border-color:#574049; }}
        QCheckBox {{ spacing:10px; padding:6px 3px; font-weight:550; }}
        QCheckBox::indicator {{ width:20px; height:20px; border:2px solid #80a2bd; border-radius:4px; background:#0e1c2c; }}
        QCheckBox::indicator:checked {{ background:#28b79f; border:2px solid #a3f5e2; image:none; }}
        QCheckBox::indicator:disabled {{ border-color:#43576a; background:#1c2938; }}
        QPushButton#sponsor {{ color:#d5e3f5; background:#16263a; border:1px solid #3d5673; text-align:left; }}
        QPushButton#sponsor:hover {{ border:1px solid {C['accent']}; }}
        QComboBox,QLineEdit {{ background:{C['panel2']}; border:1px solid {C['line']}; padding:10px; border-radius:7px; }}
        QComboBox QAbstractItemView {{ background:{C['panel']}; color:{C['text']}; selection-background-color:#24584f; }}
        QProgressBar {{ height:8px; background:{C['panel2']}; border:0; border-radius:4px; }}
        QProgressBar::chunk {{ background:{C['accent']}; border-radius:4px; }}
        QPlainTextEdit {{ background:#0d1826; border:1px solid {C['line']}; border-radius:7px; color:#c6d7e9; }}
    '''

    def card(parent_layout, *, gap=8):
        pane = QFrame()
        pane.setObjectName('card')
        lay = QVBoxLayout(pane)
        lay.setContentsMargins(15,12,15,12)
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
            self.setMinimumHeight(190)
            self.coverage = SurfaceCoverage(cells=768)
            self.rescue_map = ''
            self.setMouseTracking(True)

        @property
        def total(self):
            return self.coverage.size

        def reset(self, size):
            self.rescue_map = ''
            self.coverage.reset(max(0, int(size or 0)))
            self.update()

        def ingest(self, event):
            if event.get('workflow') == 'rescue':
                size = int(event.get('total_bytes') or 0)
                if size and size != self.total:
                    self.reset(size)
                value = str(event.get('map') or '')
                if value and set(value) <= set('.?oX'):
                    self.rescue_map = value
                    self.update()
                return
            size = int(event.get('size') or self.total or 0)
            if size <= 0:
                return
            if size != self.total:
                self.reset(size)
            spans = event.get('observed_read_spans')
            if isinstance(spans, list):
                for item in spans[:512]:
                    if (isinstance(item, list) and len(item) == 4 and
                            type(item[0]) is int and type(item[1]) is int and
                            0 <= item[0] < size and 0 < item[1] <= size):
                        self.coverage.observe(item[0], item[1],
                            failed=bool(item[2]), slow=bool(item[3]))
            else:
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
            cols = 64
            rows = 12
            gap = 2
            width = max(3, (self.width() - gap * (cols - 1)) / cols)
            height = max(5, (self.height() - gap * (rows - 1)) / rows)
            p.setPen(Qt.NoPen)
            for index, cell in enumerate(self.coverage.cells):
                x = (index % cols) * (width + gap)
                y = (index // cols) * (height + gap)
                p.setBrush(QColor('#253951'))
                p.drawRoundedRect(QRectF(x, y, width, height), 2, 2)
                if self.rescue_map:
                    # Coarse journal summary; aggregate every represented glyph
                    # and prefer UNKNOWN over a false recovered-data claim.
                    glyphs = self.rescue_map
                    lo = index * len(glyphs) // len(self.coverage.cells)
                    hi = max(lo + 1, (index + 1) * len(glyphs) // len(self.coverage.cells))
                    sample = glyphs[lo:hi]
                    state = ('X' if 'X' in sample else '?' if '?' in sample else
                             'o' if all(g == 'o' for g in sample) else '.')
                    if state != '.':
                        p.setBrush(QColor({'X':'#ed6472', '?':'#eeaa52', 'o':'#36b794'}[state]))
                        p.drawRoundedRect(QRectF(x, y, width, height), 2, 2)
                    continue
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
            cols, rows, gap = 64, 12, 2
            width = max(3, (self.width() - gap * (cols - 1)) / cols)
            height = max(5, (self.height() - gap * (rows - 1)) / rows)
            col = int(event.position().x() // (width + gap))
            row = int(event.position().y() // (height + gap))
            if 0 <= col < 64 and 0 <= row < 12:
                if self.rescue_map:
                    self.setToolTip('Approximate rescue journal: green = copied from a readable source, '
                                    'red = unreadable source range, amber = partial work, dark = unprocessed. '
                                    'Copied bytes are not guaranteed to match original file checksums.')
                    return
                cell = self.coverage.cells[row * cols + col]
                self.setToolTip(f'Device offsets {cell.start:,}–{cell.end:,} bytes\n'
                                f'{cell.fraction:.1%} read successfully\n'
                                f'{cell.read_errors} failed requests; {cell.slow_reads} slow reads\n'
                                'Untested portions are not known to be healthy')
            super().mouseMoveEvent(event)

    class RateGraph(QWidget):
        """Lightweight local-only speed trend; measured transfer rates only.

        No chart library, service or device I/O. Points represent actual timed
        reports, not a prediction or the drive's rated interface bandwidth.
        """
        def __init__(self):
            super().__init__()
            self.setMinimumHeight(108)
            self.samples=deque(maxlen=180)
            self._last_sample_at=0.0
            self.setToolTip('Observed throughput over roughly the last 45 seconds. '
                'Retransfers, stalls, USB buffering and retries can affect the readings.')

        def clear(self):
            self.samples.clear()
            self._last_sample_at=0.0
            self.update()

        def ingest(self, value):
            try:
                speed=float(value)
            except (ValueError, TypeError, OverflowError):
                return
            if not math.isfinite(speed) or speed < 0:
                return
            now=time.monotonic()
            if now-self._last_sample_at < .4:
                return
            self.samples.append((now,speed))
            self._last_sample_at=now
            self.update()

        def paintEvent(self, _):
            painter=QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            rect=self.rect().adjusted(3,4,-4,-5)
            painter.setPen(QPen(QColor('#2d4055'), 1))
            for y in (.12,.50,.88):
                offset=rect.top()+rect.height()*y
                painter.drawLine(QPointF(rect.left(),offset),QPointF(rect.right(),offset))
            if not self.samples:
                painter.setPen(QColor('#99aec4'))
                painter.drawText(rect, Qt.AlignCenter, 'Measured throughput will appear here')
                painter.end()
                return
            end=max(t for t,_ in self.samples)
            start=end-45.0
            visible=[(t,v) for t,v in self.samples if t>=start]
            ymax=max(1.0,*(v for _,v in visible))
            path=QPainterPath()
            for i,(t,v) in enumerate(visible):
                x=rect.left()+max(0.,min(1.,(t-start)/45.))*rect.width()
                y=rect.bottom()-(v/ymax)*rect.height()*.88
                if i==0:
                    path.moveTo(x,y)
                else:
                    path.lineTo(x,y)
            if len(visible) > 1:
                area=QPainterPath(path)
                area.lineTo(rect.right(),rect.bottom())
                area.lineTo(rect.left(),rect.bottom())
                area.closeSubpath()
                grad=QLinearGradient(0,rect.top(),0,rect.bottom())
                grad.setColorAt(0,QColor(64,207,181,85))
                grad.setColorAt(1,QColor(64,207,181,0))
                painter.fillPath(area,grad)
            painter.setPen(QPen(QColor('#42e9d1'),2.4))
            painter.drawPath(path)
            painter.end()

    class ConditionGauge(QWidget):
        """A condition-indicator gauge, NOT a probability of survival."""
        def __init__(self):
            super().__init__()
            self.setMinimumSize(164,122)
            self.setMaximumWidth(205)
            self.score=None
            self.caption='NO SMART SCORE'
            self.setToolTip('Evidence-based condition indicator, not remaining life or an assurance of reliability.')

        def set_assessment(self, report):
            self.score=report.get('score') if isinstance(report,dict) else None
            self.caption=str(report.get('band') or 'UNKNOWN') if isinstance(report,dict) else 'UNKNOWN'
            self.update()

        def paintEvent(self, event):
            painter=QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            x,y=12,6
            diameter=min(self.width()-24,106)
            frame=QRectF(x,y,diameter,diameter)
            painter.setPen(QPen(QColor('#304b62'),10,Qt.SolidLine,Qt.RoundCap))
            painter.drawArc(frame, 210*16, -240*16)
            if type(self.score) in (int,float):
                value=max(0,min(100,float(self.score)))
                color=('#e96e7b' if value<35 else '#f5b85e' if value<85 else '#41dbc0')
                painter.setPen(QPen(QColor(color),10,Qt.SolidLine,Qt.RoundCap))
                painter.drawArc(frame,210*16,round(-240*16*value/100))
            painter.setPen(QColor('#f2f7fc'))
            font=painter.font()
            font.setBold(True)
            font.setPixelSize(30)
            painter.setFont(font)
            number='—' if self.score is None else str(self.score)
            painter.drawText(QRectF(x,y+24,diameter,48),Qt.AlignCenter,number)
            font.setPixelSize(10)
            painter.setFont(font)
            painter.setPen(QColor('#b3c9dc'))
            painter.drawText(QRectF(x,y+76,diameter,30),Qt.AlignCenter,self.caption)
            painter.end()

    class MediaPipeline(QWidget):
        """Compact vector workflow: classification, protected rescue, verification.

        These are decision stages, not a fabricated scan progress indicator.
        """
        def __init__(self):
            super().__init__()
            self.kind = 'unknown'
            self.eligible = False
            self.setMinimumHeight(58)
            self.setMaximumHeight(64)
            self.setToolTip('Media policy is advisory. Device identity, SMART and exclusive access are checked by the engine before physical writes.')

        def set_policy(self, kind, eligible=False):
            self.kind = str(kind or 'unknown').lower()
            self.eligible = bool(eligible)
            self.update()

        def paintEvent(self, _event):
            painter=QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            labels=('IDENTIFY MEDIA', 'IMAGE / RESCUE',
                    'TARGETED HDD' if self.eligible else 'VERIFY / REPORT')
            colors=('#7892b3','#40cfb5', '#e6b669' if self.eligible else '#7892b3')
            gap=8.0
            width=max(10.0,(self.width()-2*gap)/3)
            for index,(title,color) in enumerate(zip(labels,colors)):
                x=index*(width+gap)
                rect=QRectF(x,6,width,40)
                painter.setPen(QPen(QColor('#34506a'),1))
                painter.setBrush(QColor('#1a2c40'))
                painter.drawRoundedRect(rect,7,7)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(color))
                painter.drawRoundedRect(QRectF(x+7,15,4,22),2,2)
                painter.setPen(QColor('#f0f7fc'))
                font=painter.font()
                font.setPixelSize(10)
                font.setBold(True)
                painter.setFont(font)
                painter.drawText(QRectF(x+17,9,width-22,32), Qt.AlignVCenter | Qt.AlignLeft, title)
            painter.end()

    class Workstation(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle('DriveRepair | Recovery Workstation')
            self.resize(1410,860)
            self.setMinimumSize(920,640)
            self._pending = None
            self._mode = None
            self._buf = {'stdout':'','stderr':''}
            self._final_stdout = ''
            self._devices=[]
            self._job_args=[]
            self._last_job_kind=''
            self._last_job_result=None
            self._last_report_file=None
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
            self._batch_queue=[]
            self._batch_current=None
            self._batch_manifest=None
            self._batch_results=[]
            self._batch_running=False
            self._batch_sleep_prevented=False
            self._manufacturer_rated_hours={}
            self._last_health_snapshot=None
            self._health_by_device={}  # keyed by fingerprint; prevents cross-disk inference
            self._auto_probe_proc=None
            self._auto_probe_hint=None
            self._auto_probe_attempted=set()
            self._auto_probe_timer=QTimer(self)
            self._auto_probe_timer.setSingleShot(True)
            self._auto_probe_timer.setInterval(900)
            self._auto_probe_timer.timeout.connect(self.probe_selected_media)
            self._stall_terminated=False
            self._rescue_started_at=None
            self._rescue_sample=None
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
            shell=QWidget()
            shell_layout=QHBoxLayout(shell)
            shell_layout.setContentsMargins(0,0,0,0)
            shell_layout.setSpacing(0)
            self.setCentralWidget(shell)
            sidebar=QFrame()
            sidebar.setObjectName('sidebar')
            sidebar.setFixedWidth(214)
            nav=QVBoxLayout(sidebar)
            nav.setContentsMargins(13,19,13,15)
            nav.setSpacing(7)
            mark=QLabel('DR  /  DRIVE REPAIR')
            mark.setStyleSheet(f'font-weight:800; letter-spacing:1px; color:{C["accent"]}; font-size:15px;')
            nav.addWidget(mark)
            edition=QLabel('RECOVERY WORKSTATION')
            edition.setObjectName('eyebrow')
            nav.addWidget(edition)
            nav.addSpacing(18)
            nav_title=QLabel('WORKSPACES')
            nav_title.setObjectName('eyebrow')
            nav.addWidget(nav_title)
            self.nav_buttons={}
            for family, label, key in (
                ('check','01   Diagnose','scanquick'),
                ('recover','02   Rescue data','rescue'),
                ('fix','03   HDD maintenance','carequick')):
                b=QPushButton(label)
                b.setObjectName('nav')
                b.setCheckable(True)
                b.setAccessibleName(f'{family.title()} workspace')
                if family == 'fix' and PUBLIC_BETA_IMAGE_ONLY:
                    b.setEnabled(False)
                    b.setToolTip('Experimental in-place repairs are disabled in the public beta.')
                else:
                    b.clicked.connect(lambda _,k=key:self.select_goal(k))
                nav.addWidget(b)
                self.nav_buttons[family]=b
            nav.addSpacing(16)
            nav.addWidget(QLabel('TOOLS'))
            self.details_button=QPushButton('Expert log')
            self.details_button.setCheckable(True)
            self.details_button.setObjectName('nav')
            self.details_button.toggled.connect(self.show_details)
            nav.addWidget(self.details_button)
            self.legacy=QPushButton('Specialist tools')
            self.legacy.setObjectName('nav')
            self.legacy.clicked.connect(self.open_specialist_tools)
            nav.addWidget(self.legacy)
            self.device_tools_button=QPushButton('Hardware diagnostics')
            self.device_tools_button.setObjectName('nav')
            self.device_tools_button.setToolTip('Read-only device capabilities, firmware, sampled speed and failed-offset investigation')
            self.device_tools_button.clicked.connect(self.open_device_tools)
            nav.addWidget(self.device_tools_button)
            self._media_settings=QSettings('DriveRepair', 'RecoveryWorkstation')
            # The primary route is one USB creator, not three equally prominent tools.
            self.usb_flash_button=QPushButton('Create recovery USB')
            self.usb_flash_button.setObjectName('nav')
            self.usb_flash_button.setToolTip('Automatically selects an existing local DriveRepair ISO when available. Only a confirmed sacrificial USB is erased.')
            self.usb_flash_button.clicked.connect(self.flash_boot_usb)
            nav.addWidget(self.usb_flash_button)
            self.boot_button=QPushButton('Export ISO build kit')
            self.boot_button.setObjectName('nav')
            self.boot_button.setToolTip('Advanced: export Debian build instructions; the ZIP itself is NOT bootable.')
            self.boot_button.clicked.connect(self.export_boot_kit)
            self.iso_button=QPushButton('Build live ISO (Linux)')
            self.iso_button.setObjectName('nav')
            self.iso_button.setToolTip('Advanced: build an UNVERIFIED hybrid ISO on a Debian build machine.')
            self.iso_button.clicked.connect(self.build_iso)
            # Keep the expert actions accessible inside the creator rather than
            # consuming the navigation with build-kit/ISO/flash distinctions.
            self.sponsor_button=QPushButton('♡  Support DriveRepair')
            self.sponsor_button.setObjectName('sponsor')
            self.sponsor_button.setToolTip('Opens the same GitHub Sponsors profile as Repository Detective. No telemetry or network request until clicked.')
            self.sponsor_button.clicked.connect(lambda:QDesktopServices.openUrl(QUrl('https://github.com/sponsors/CommsTech')))

            self.flash_proc=None
            self.iso_proc=None
            self._iso_build_temp=None
            nav.addStretch()
            nav.addWidget(self.sponsor_button)
            channel=QLabel('IMAGE-FIRST PUBLIC BETA' if PUBLIC_BETA_IMAGE_ONLY
                           else 'GUIDED HDD REPAIR BETA' if REPAIR_BETA_GUARDED
                           else 'EXPERIMENTAL ENGINEERING')
            channel.setObjectName('eyebrow')
            channel.setWordWrap(True)
            nav.addWidget(channel)
            note=QLabel('Local processing  ·  No automatic uploads\nNo operation starts on selection')
            note.setObjectName('muted')
            note.setWordWrap(True)
            nav.addWidget(note)
            shell_layout.addWidget(sidebar)
            main_col=QWidget()
            main_col_layout=QVBoxLayout(main_col)
            main_col_layout.setContentsMargins(0,0,0,0)
            main_col_layout.setSpacing(0)
            shell_layout.addWidget(main_col,1)
            scroll=QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            main_col_layout.addWidget(scroll,1)
            central=QWidget()
            scroll.setWidget(central)
            root=QVBoxLayout(central)
            root.setContentsMargins(18,15,18,14)
            root.setSpacing(10)
            header=QHBoxLayout()
            root.addLayout(header)
            brand=QVBoxLayout()
            brand.setSpacing(6)
            self.page_eyebrow=QLabel('DRIVE WORKBENCH  /  DIAGNOSE')
            self.page_eyebrow.setObjectName('eyebrow')
            brand.addWidget(self.page_eyebrow)
            self.page_title=QLabel('Diagnose a drive')
            self.page_title.setObjectName('heading')
            brand.addWidget(self.page_title)
            self.page_intro=QLabel('Observe the media before deciding what to do next.')
            self.page_intro.setObjectName('muted')
            self.page_intro.setTextFormat(Qt.PlainText)
            self.page_intro.setWordWrap(True)
            brand.addWidget(self.page_intro)
            header.addLayout(brand,1)
            self.operation_impact=QLabel('READ-ONLY')
            self.operation_impact.setObjectName('riskTag')
            header.addWidget(self.operation_impact)
            self.help_button=help_icon('The UI reports observed evidence only. Accessible controls and read-only defaults do not bypass CLI safeguards.')
            header.addWidget(self.help_button)
            hero = card(root)
            status_row=QHBoxLayout()
            hero.addLayout(status_row)
            self.status=QLabel('Ready to inspect a drive')
            self.status.setObjectName('heading')
            self.status.setWordWrap(True)
            status_row.addWidget(self.status)
            status_row.addWidget(help_icon('Each phase reports only evidence actually observed. A readable block is not proof of correct files, and rewriting data does not restore physical lifespan.'))
            status_row.addStretch()
            self.help=QLabel('Select a drive → review its media strategy → run a safe operation.')
            self.help.setWordWrap(True)
            self.help.setObjectName('muted')
            self.help.setTextFormat(Qt.PlainText)
            hero.addWidget(self.help)
            self.progress=QProgressBar()
            self.progress.setRange(0,1000)
            self.progress.setValue(0)
            phase_row=QHBoxLayout()
            hero.addLayout(phase_row)
            self.phase_caption=QLabel('Current phase · no job')
            self.phase_caption.setObjectName('muted')
            phase_row.addWidget(self.phase_caption)
            self.phase_caption.hide()
            phase_row.addStretch()
            self.phase_progress=QProgressBar()
            self.phase_progress.setRange(0,1000)
            self.phase_progress.setValue(0)
            # One progress bar is enough. The current-phase percentage lives in
            # the first metric tile; duplicate bars implied false precision.
            self.phase_progress.hide()
            total_row=QHBoxLayout()
            hero.addLayout(total_row)
            self.total_caption=QLabel('Estimated guided-workflow progress · not media coverage')
            self.total_caption.setObjectName('muted')
            total_row.addWidget(self.total_caption)
            self.total_caption.hide()
            total_row.addStretch()
            self.overall_label=QLabel('—')
            total_row.addWidget(self.overall_label)
            self.overall_label.hide()
            hero.addWidget(self.progress)
            self.progress.hide()  # show only while a real job has evidence
            metrics=QGridLayout()
            metrics.setHorizontalSpacing(10)
            metrics.setVerticalSpacing(4)
            hero.addLayout(metrics)
            self.metric_labels={}
            self._has_job_evidence=False
            self.metric_headers={}
            self.metric_tiles={}
            for metric_index,(key,title) in enumerate([('done','CURRENT PHASE'),('read','DATA READ'),('rate','RECENT SPEED'),('avg','JOB AVERAGE'),('errors','READ ERRORS'),('eta','TIME LEFT')]):
                tile=QFrame()
                tile.setObjectName('statTile')
                area=QVBoxLayout(tile)
                area.setContentsMargins(11,7,11,7)
                area.setSpacing(2)
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
                # Five high-value metrics; job-average remains available in the tooltip.
                metrics.addWidget(tile, 0, {'done':0,'read':1,'rate':2,'errors':3,'eta':4,'avg':5}[key])
                tile.hide()  # no fake zero-value dashboard at idle
                self.metric_tiles[key]=tile
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
            tool_row=QHBoxLayout()
            drive_panel.addLayout(tool_row)
            self.inspect_button=QPushButton('Details ⓘ')
            self.inspect_button.setToolTip('Read-only OS information such as physical/logical sector size, queue limits, transport and firmware revision where available. It does NOT establish safe write permission.')
            self.inspect_button.clicked.connect(self.inspect_drive)
            tool_row.addWidget(self.inspect_button)
            self.refresh_button=QPushButton('Refresh')
            self.refresh_button.clicked.connect(self.refresh_devices)
            tool_row.addWidget(self.refresh_button)
            self.smart_check_button=QPushButton('Check HDD eligibility')
            self.smart_check_button.setToolTip('Read-only SMART / SATA passthrough identification. '
                'No repair or drive writes start here. Available in the Repair workspace.')
            self.smart_check_button.clicked.connect(lambda:self.probe_selected_media(force=True))
            tool_row.addWidget(self.smart_check_button)
            tool_row.addStretch()
            self.device_box=QComboBox()
            self.device_box.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            self.device_box.setMinimumContentsLength(14)
            self.device_box.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            drive_panel.addWidget(self.device_box)
            self.offline_devices=QCheckBox('Offline Linux: show internal disks for read-only rescue')
            self.offline_devices.setToolTip('Only when booted from a trusted, separate Linux recovery OS. '
                'The engine still requires unmounted source disks, a separate destination, and verified identity. '
                'Internal disks can never be queued for physical repair here.')
            self.offline_devices.setVisible(sys.platform=='linux')
            self.offline_devices.toggled.connect(lambda _:self.refresh_devices())
            drive_panel.addWidget(self.offline_devices)
            drive_panel.addWidget(help_icon('Check the model, capacity and serial suffix before starting. USB bridge numbers can change on reconnect. Physical writes always require renewed identity verification; read-only scans can resume using a stable media fingerprint.'))
            self.device_note=QLabel('The selected disk will be identified again before physical writes.')
            self.device_note.setWordWrap(True)
            self.device_note.setObjectName('muted')
            drive_panel.addWidget(self.device_note)
            self.smart_check_note=QLabel('Repair eligibility requires verified HDD media and SMART health. '
                'If the USB adapter hides them, use read-only rescue or direct SATA.')
            self.smart_check_note.setObjectName('muted')
            self.smart_check_note.setWordWrap(True)
            self.smart_check_note.hide()  # repair-specific guidance belongs in repair workspace
            drive_panel.addWidget(self.smart_check_note)
            self.repair_help=QPushButton('Why is repair unavailable?')
            self.repair_help.setToolTip('Explains the evidence required by the independent repair engine')
            self.repair_help.clicked.connect(self.explain_repair_eligibility)
            drive_panel.addWidget(self.repair_help)
            self.repair_help.hide()
            self.profile_note=QLabel('Identifying media…')
            self.profile_note.setWordWrap(True)
            self.profile_note.setObjectName('muted')
            self.profile_note.setTextFormat(Qt.PlainText)
            drive_panel.addWidget(self.profile_note)
            self.media_pipeline=MediaPipeline()
            drive_panel.addWidget(self.media_pipeline)
            self.device_box.currentIndexChanged.connect(self.update_drive_profile)
            self.drive_panel=drive_panel.parentWidget()
            workflow=card(left)
            title=QLabel('02  Choose a workflow')
            title.setStyleSheet('font-weight:700;font-size:15px')
            workflow.addWidget(title)
            advanced=QLabel('Select an operation. Nothing begins until you press Start.')
            advanced.setObjectName('muted')
            advanced.setWordWrap(True)
            workflow.addWidget(advanced)
            self.job_box=QComboBox()
            self.job_box.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            self.job_box.setMinimumContentsLength(14)
            self.job_box.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            self._jobs={
                'fix':[('Targeted HDD region repair','carequick'),
                       ('Full scan + targeted HDD repair','carefull'),
                       ('Resume journaled repair','careresume')],
                'recover':[('Rescue selected external drive to NEW image','rescue'),
                           ('Recover from existing disk image','rescueimage')],
                'check':[('Check disk health (read-only)','health'),
                         ('Verify USB capacity · write / restore spot test','capacity'),
                         ('Quick surface check (read-only)','scanquick'),
                         ('Full surface scan (read-only)','scanfull'),
                         ('Continue interrupted full scan','resume')],
            }
            self.job_box.currentIndexChanged.connect(self.choice_changed)
            workflow.addWidget(self.job_box)
            # Automatic intensity is an evidence-led plan, never a user-set
            # integer or a substitute for independent raw-write authorization.
            self.auto_plan_note=QLabel('Automatic maintenance plan · waiting for device evidence')
            self.auto_plan_note.setObjectName('muted')
            self.auto_plan_note.setWordWrap(True)
            self.auto_plan_note.setToolTip('DriveRepair chooses a bounded consistency budget. More reads are not automatically safer; it does not enable destructive writes.')
            workflow.addWidget(self.auto_plan_note)
            self.batch_button=QPushButton('Queue multiple drives for rescue  +')
            self.batch_button.setToolTip('Serial read-only imaging of multiple selected sources. Each destination is a unique NEW image on separate healthy storage.')
            self.batch_button.clicked.connect(self.queue_rescue)
            workflow.addWidget(self.batch_button)
            self.batch_status=QLabel('One drive at a time · independent recovery journals · no automatic physical rewrites')
            self.batch_status.setObjectName('muted')
            self.batch_status.setWordWrap(True)
            workflow.addWidget(self.batch_status)
            help_row=QHBoxLayout()
            workflow.addLayout(help_row)
            help_row.addWidget(help_icon('Repair: suitable HDDs only in the guarded beta, with SMART evidence, a separate journal and exclusive disk access. Rescue: new image. Diagnose: reads only.'))
            self.auto_resume=QCheckBox('Resume read-only full scan when the same USB drive reconnects')
            self.auto_resume.setChecked(True)
            self.auto_resume.setToolTip('Only a read-only full scan with a saved checkpoint can restart automatically. No in-place writes or RAM-only transactions restart after a disconnect.')
            help_row.addWidget(self.auto_resume,1)
            self.auto_pause=QCheckBox('Stop unresponsive read-only scan after 3 minutes')
            self.auto_pause.setChecked(True)
            self.auto_pause.setToolTip('Supervises the read-only child, not the kernel driver. A forced stop might not release a hung USB device. Never applied to physical writes.')
            workflow.addWidget(self.auto_pause)
            self.dest=QLineEdit()
            self.dest.setPlaceholderText('Choose an existing source image…')
            self.browse=QPushButton('Choose image…')
            self.browse.clicked.connect(self.pick_image)
            pathrow=QHBoxLayout()
            pathrow.addWidget(self.dest,1)
            pathrow.addWidget(self.browse)
            workflow.addLayout(pathrow)
            self.opts=QLabel('Media-aware strategy  •  Source writes require explicit approval  •  Local-only')
            self.opts.setObjectName('muted')
            workflow.addWidget(self.opts)
            right=QVBoxLayout()
            body.addLayout(right,3)
            # Qt must not stretch the left forms into tall, mostly-empty cards.
            self.drive_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
            workflow.parentWidget().setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
            left.addStretch(1)
            map_card=card(right)
            self.map_card=map_card.parentWidget()
            self.map_card.hide()  # don't present a vast empty evidence grid before the first scan
            map_head=QHBoxLayout()
            map_card.addLayout(map_head)
            map_title=QLabel('Evidence map  •  untested areas remain unknown')
            map_title.setStyleSheet('font-weight:700;font-size:15px')
            map_title.setWordWrap(True)
            map_head.addWidget(map_title)
            map_head.addWidget(help_icon('Each cell always represents the same fixed portion of the ENTIRE drive. Only the portion actually read fills green. Orange/red markers show slow or failed requests, not confirmed physical damage. Hover over a cell for its offsets and coverage.'))
            map_head.addStretch()
            self.map=ScanMap()
            map_card.addWidget(self.map)
            coverage_row=QHBoxLayout()
            self.coverage_label=QLabel('MEASURED COVERAGE  ·  0.00%')
            self.coverage_label.setObjectName('eyebrow')
            coverage_row.addWidget(self.coverage_label)
            coverage_row.addStretch()
            self.evidence_scope=QLabel('Untested is unknown')
            self.evidence_scope.setObjectName('muted')
            self.evidence_scope.setWordWrap(True)
            coverage_row.addWidget(self.evidence_scope)
            map_card.addLayout(coverage_row)
            legend=QLabel('<span style="color:#36b794">■</span> Readable     '
                          '<span style="color:#eeaa52">■</span> Slow     '
                          '<span style="color:#ed6472">■</span> Read error     '
                          '<span style="color:#253951">■</span> Untested')
            legend.setTextFormat(Qt.RichText)
            legend.setWordWrap(True)
            map_card.addWidget(legend)
            self.advice=QLabel('A green block means data could be read. It does not prove file integrity or long-term drive health.')
            self.advice.setWordWrap(True)
            self.advice.setObjectName('muted')
            map_card.addWidget(self.advice)
            trend_header=QHBoxLayout()
            map_card.addLayout(trend_header)
            trend_title=QLabel('OBSERVED THROUGHPUT  ·  LAST 45 SECONDS')
            trend_title.setObjectName('eyebrow')
            trend_header.addWidget(trend_title)
            trend_header.addStretch()
            self.speed_graph=RateGraph()
            map_card.addWidget(self.speed_graph)
            result_card=card(right)
            results_heading=QLabel('03  Results and next action')
            results_heading.setStyleSheet('font-size:15px;font-weight:700;')
            result_card.addWidget(results_heading)
            condition_row=QHBoxLayout()
            self.condition_gauge=ConditionGauge()
            # The big dial adds visual noise when there is no actual SMART
            # measurement. Reveal it only after a meaningful score exists.
            self.condition_gauge.setVisible(False)
            condition_row.addWidget(self.condition_gauge)
            condition_summary=QVBoxLayout()
            self.condition_title=QLabel('Drive condition · not measured')
            self.condition_title.setObjectName('section')
            self.condition_title.setWordWrap(True)
            condition_summary.addWidget(self.condition_title)
            self.condition_evidence=QLabel('Run Check disk health for SMART-based indicators. Unknown is not healthy.')
            self.condition_evidence.setWordWrap(True)
            self.condition_evidence.setObjectName('muted')
            condition_summary.addWidget(self.condition_evidence)
            condition_summary.addStretch()
            condition_row.addLayout(condition_summary,1)
            result_card.addLayout(condition_row)
            self.spec_button=QPushButton('Compare with documented service-hour rating…')
            self.spec_button.setVisible(False)  # power-on evidence needed first
            self.spec_button.setToolTip('Only supply a published model-specific operating-hour rating. Fleet MTBF is not a failure prediction.')
            self.spec_button.clicked.connect(self.enter_manufacturer_specs)
            result_card.addWidget(self.spec_button)
            self.result=QLabel('No job running')
            self.result.setTextFormat(Qt.PlainText)
            self.result.setWordWrap(True)
            self.result.setStyleSheet('font-size:16px;font-weight:700')
            result_card.addWidget(self.result)
            self.explain=QLabel('Recovery reports will show what is verified, unresolved, and untested.')
            self.explain.setTextFormat(Qt.PlainText)
            self.explain.setWordWrap(True)
            self.explain.setObjectName('muted')
            result_card.addWidget(self.explain)
            next_title=QLabel('RECOMMENDED NEXT STEP')
            next_title.setObjectName('eyebrow')
            result_card.addWidget(next_title)
            self.next_action=QLabel('Choose a workflow to see its next step.')
            self.next_action.setWordWrap(True)
            self.next_action.setTextFormat(Qt.PlainText)
            result_card.addWidget(self.next_action)
            report_row=QHBoxLayout()
            self.rescue_instead=QPushButton('Rescue to image instead')
            self.rescue_instead.setToolTip('Switch to read-only imaging of this selected drive; no source writes.')
            self.rescue_instead.clicked.connect(lambda:self.select_goal('rescue'))
            self.rescue_instead.setVisible(False)
            report_row.addWidget(self.rescue_instead)
            self.copy_summary_button=QPushButton('Copy operator summary')
            self.copy_summary_button.setEnabled(False)
            self.copy_summary_button.setToolTip('Copies only currently displayed local evidence. No data is sent anywhere.')
            self.copy_summary_button.clicked.connect(self.copy_summary)
            report_row.addStretch()
            self.detailed_report_button=QPushButton('View detailed report')
            self.detailed_report_button.setEnabled(False)
            self.detailed_report_button.setToolTip('Save a modern, completely local HTML evidence report. No data is uploaded.')
            self.detailed_report_button.clicked.connect(self.export_detailed_report)
            report_row.addWidget(self.detailed_report_button)
            report_row.addWidget(self.copy_summary_button)
            result_card.addLayout(report_row)
            # Actionable outcome precedes dense telemetry. The evidence map
            # remains available immediately below for operator drilldown.
            right.insertWidget(0, result_card.parentWidget())
            self.log=QPlainTextEdit()
            self.log.setReadOnly(True)
            self.log.setMaximumBlockCount(4000)
            self.log.setVisible(bool(debug_log_path))
            root.addWidget(self.log)
            # Persistent action dock: the Start/Stop controls remain visible even
            # while users inspect the map or scroll through diagnostics.
            dock=QFrame()
            dock.setObjectName('actionDock')
            dock_layout=QHBoxLayout(dock)
            dock_layout.setContentsMargins(24,12,24,12)
            dock_layout.setSpacing(12)
            readiness=QVBoxLayout()
            readiness.setSpacing(3)
            ready_label=QLabel('READY CHECK')
            ready_label.setObjectName('eyebrow')
            readiness.addWidget(ready_label)
            self.ready_note=QLabel('Select a source drive to continue.')
            self.ready_note.setWordWrap(True)
            readiness.addWidget(self.ready_note)
            dock_layout.addLayout(readiness,1)
            self.start=QPushButton('Start read-only diagnostics')
            self.start.setObjectName('primary')
            self.start.clicked.connect(self.start_job)
            self.start.setMinimumWidth(205)
            dock_layout.addWidget(self.start)
            self.stop=QPushButton('Stop')
            self.stop.setObjectName('danger')
            self.stop.setEnabled(False)
            self.stop.clicked.connect(self.stop_job)
            dock_layout.addWidget(self.stop)
            main_col_layout.addWidget(dock)
            # Native keyboard shortcuts, available without remote frameworks.
            for shortcut, target in [('Ctrl+1','scanquick'), ('Ctrl+2','rescue')]:
                key=QShortcut(QKeySequence(shortcut),self)
                key.activated.connect(lambda t=target:self.select_goal(t))
            if not PUBLIC_BETA_IMAGE_ONLY:
                key=QShortcut(QKeySequence('Ctrl+3'),self)
                key.activated.connect(lambda:self.select_goal('carequick'))
            key=QShortcut(QKeySequence('Ctrl+L'),self)
            key.activated.connect(lambda:self.details_button.setChecked(not self.details_button.isChecked()))
            key=QShortcut(QKeySequence('Ctrl+K'),self)
            key.activated.connect(self.quick_switch)
            self.device_box.currentIndexChanged.connect(self.update_action_state)
            self.dest.textChanged.connect(self.update_action_state)
            if debug_log_path is not None:
                self.log.appendPlainText(f'Debug tracking ON — {debug_log_path}')
                debug_trace(f'Debug tracking ON — {debug_log_path}\n')
                self.setWindowTitle(self.windowTitle() + ' [DEBUG]')
            self.select_goal('scanquick')
            QTimer.singleShot(100,self.refresh_devices)
        def explain_repair_eligibility(self):
            from .repair_readiness import ui_repair_readiness
            d=self.selected() or {}
            snap=self._health_by_device.get(d.get('identity_hint'))
            allowed, reason=ui_repair_readiness(d,'carequick',snapshot=snap)
            info=QMessageBox(self)
            info.setWindowTitle('HDD repair readiness')
            info.setIcon(QMessageBox.Information if allowed else QMessageBox.Warning)
            info.setText('HDD eligibility confirmed for UI preflight' if allowed
                         else 'DriveRepair cannot currently authorize a physical rewrite')
            info.setInformativeText(reason+'\n\nFor USB bridges, SMART passthrough depends on the adapter. '
                'Install smartmontools, try a known-compatible SAT bridge or direct SATA for a verified HDD. '
                'Windows HealthStatus and model labels do not independently authorize raw writes. '
                'You can always image readable data without changing the patient.')
            info.addButton('Understood',QMessageBox.AcceptRole)
            rescue=info.addButton('Rescue data',QMessageBox.ActionRole)
            info.exec()
            if info.clickedButton()==rescue:
                self.select_goal('rescue')

        def update_drive_profile(self, _index=None):
            d=self.selected()
            if not d:
                self.profile_note.setText('Choose a drive to determine the recovery strategy.')
                self.media_pipeline.set_policy('unknown',False)
                self._auto_probe_timer.stop()
                return
            from .media_profiles import identify_profile
            from .repair_strategy import advise
            key=d.get('identity_hint')
            snap=self._health_by_device.get(key) or {}
            try:
                profile=identify_profile(model=str(d.get('model') or ''),
                    bus=str(d.get('bus') or ''), sector=int(d.get('sector_size') or 512),
                    media_type=str(snap.get('reported_medium') or ''),
                    protocol=str(snap.get('device_protocol') or ''))
                decision=advise(model=str(d.get('model') or ''),
                    bus=str(d.get('bus') or ''), sector=int(d.get('sector_size') or 512),
                    snapshot=snap)
                title=profile.kind.upper().replace('_',' ') + ' · ' + profile.evidence
                if profile.workload == 'surveillance':
                    title+=' · NVR / surveillance workload (NOT a recording type)'
                self.profile_note.setText('Detected: ' + title + '\nSuggested: ' + profile.recovery_method)
                self.media_pipeline.set_policy(profile.kind,decision.can_attempt_hdd_refresh)
                if self.job_box.currentData() in {'carequick','carefull','careresume'}:
                    from .automatic_maintenance import choose_maintenance
                    plan=choose_maintenance(model=str(d.get('model') or ''),
                        bus=str(d.get('bus') or ''), snapshot=snap,
                        mode='full' if self.job_box.currentData()=='carefull' else 'quick')
                    self.auto_plan_note.setText(f'Automatic plan · {plan.title}. {plan.explanation}')
                self.profile_note.setToolTip('Classification: '+profile.confidence+'. '+
                    'USB is a transport, not a physical medium. '+profile.maintenance_note+
                    '\nRecommendation: '+decision.label+'; '+'; '.join(decision.reasons))
            except (ValueError,TypeError):
                self.profile_note.setText('Unverified drive geometry — read-only rescue recommended.')
                self.media_pipeline.set_policy('unknown',False)
            if (not snap and key not in self._auto_probe_attempted
                    and not (self.proc and self.proc.state()!=QProcess.NotRunning)):
                self._auto_probe_timer.start()
            self.update_action_state()

        def probe_selected_media(self, *, force=False):
            """Time-bounded SMART identification on an idle source, never a write gate.

            The CLI subprocess is isolated so an unresponsive bridge cannot hang
            the Qt event loop; if it fails, the profile remains UNKNOWN.
            """
            d=self.selected()
            if (not d or self._batch_running or (self.proc and self.proc.state()!=QProcess.NotRunning)
                    or (self._auto_probe_proc and self._auto_probe_proc.state()!=QProcess.NotRunning)):
                return
            key=d.get('identity_hint')
            if not key or (not force and (key in self._health_by_device or
                                         key in self._auto_probe_attempted)):
                return
            if force:
                self.smart_check_note.setText('Checking USB SMART / ATA identity read-only… '
                    'the drive is not being repaired or rewritten.')
            self._auto_probe_attempted.add(key)
            self._auto_probe_hint=key
            child=QProcess(self)
            self._auto_probe_proc=child
            child.setProgram(cli_prefix()[0])
            child.setArguments(cli_prefix()[1:]+['health','--device',d['id'],'--json'])
            child.finished.connect(lambda code,_status,c=child,k=key:self.media_probe_done(c,k,code))
            child.start()
            self.update_action_state()
            def bound_probe(c=child):
                if c.state()!=QProcess.NotRunning:
                    self.note_log('SMART identification timed out; preserving unknown media. No writes attempted.')
                    c.kill()
            QTimer.singleShot(22000,bound_probe)

        def media_probe_done(self, child, key, code):
            if child is not self._auto_probe_proc:
                return
            self._auto_probe_proc=None
            if code == 0:
                try:
                    report=json.loads(bytes(child.readAllStandardOutput()).decode('utf-8','replace'))
                except (ValueError,UnicodeError):
                    report=None
                if isinstance(report,dict) and report.get('status'):
                    self._health_by_device[key]=report
            if self.selected() and self.selected().get('identity_hint') == key:
                current=self._health_by_device.get(key)
                from .repair_readiness import ui_repair_readiness
                permitted, explanation = ui_repair_readiness(self.selected(), 'carequick',
                                                               snapshot=current)
                self.smart_check_note.setText(
                    'SMART/rotation check passed the UI eligibility stage; '
                    'device identity, locks and journal remain mandatory.' if permitted else
                    'HDD repair is not authorized: '+explanation)
                self.update_drive_profile()
            self.update_action_state()

        def select_goal(self, goal):
            if self.proc and self.proc.state()!=QProcess.NotRunning:
                return  # Navigation cannot silently re-target an active operation.
            family = operation_family(goal)
            for name, button in self.nav_buttons.items():
                button.setChecked(name == family)
            workspace=WORKSPACES[family]
            self.page_eyebrow.setText('DRIVE WORKBENCH  /  '+family.upper())
            self.page_title.setText(workspace.title)
            self.page_intro.setText(workspace.subtitle)
            self.next_action.setText(workspace.next_step)
            self.job_box.blockSignals(True)
            self.job_box.clear()
            for title, key in self._jobs[family]:
                self.job_box.addItem(title, key)
            for i in range(self.job_box.count()):
                if self.job_box.itemData(i) == goal:
                    self.job_box.setCurrentIndex(i)
                    break
            self.job_box.blockSignals(False)
            self.smart_check_note.setVisible(family=='fix')
            self.repair_help.setVisible(family=='fix')
            self.choice_changed()
        def check_stall(self):
            if (self.proc and self.proc.state()!=QProcess.NotRunning
                    and self._last_progress_at is not None
                    and time.monotonic()-self._last_progress_at>8):
                self.metric_labels['rate'].setText('Waiting on drive')
                elapsed=int(time.monotonic()-self._last_progress_at)
                if self._last_phase is None and elapsed < 30:
                    self.help.setText('Waiting for device and access preflight to return. '
                        'No scan or write has been confirmed yet.')
                    self.phase_caption.setText('Preflight pending · zero confirmed I/O')
                    return
                self.help.setText(f'Waiting {elapsed}s for the storage driver or USB device. '
                    'No new I/O result; the operation is NOT necessarily progressing. '
                    'Stop waits for a safe boundary and may not interrupt a blocked kernel request.')
                self.result.setText('Drive I/O stalled — investigation may be blocked inside Windows')
                self.explain.setText(f'Last request: byte offset {self._last_io_offset:,} · '
                    f'length {self._last_io_length:,} bytes · {elapsed}s without a result. '
                    'Check Expert details for the most recent observations.')
                self.metric_labels['eta'].setText('Unknown · stalled')
                self.phase_caption.setText('I/O pending · completion not confirmed')
                if (elapsed >= 180 and self.auto_pause.isChecked()
                        and self._last_job_kind in {'scanquick','scanfull','resume'}
                        and not self._stop_requested):
                    self.note_log('Read-only scan watchdog: no result in 180s. Requesting cooperative stop; '
                        'the Windows storage driver may still ignore cancellation.')
                    self._stall_terminated=True
                    self.stop_job()
                if (elapsed >= 240 and self._batch_running and self._batch_current
                        and self._last_job_kind == 'rescue' and not self._stall_terminated):
                    self._stall_terminated=True
                    self.batch_status.setText('One queued rescue timed out waiting on the storage driver. '
                        'Stopping its read-only worker; output is incomplete and must be checked before use.')
                    self.note_log('Queue watchdog: 240s with no progress; terminating isolated rescue process. '
                        'Do not treat an incomplete image or journal as a finished recovery.')
                    child=self.proc
                    child.terminate()
                    QTimer.singleShot(6000,lambda c=child:self._force_stalled_batch_child(c))
        def _force_stalled_batch_child(self, child):
            if self._stall_terminated and child.state()!=QProcess.NotRunning:
                self.note_log('Queue watchdog: read-only rescue subprocess did not exit; killing worker. '
                    'USB controller cancellation may still fail; verify output journal.')
                child.kill()

        def show_details(self, yes): self.log.setVisible(yes)
        def note_log(self, text: str) -> None:
            self.log.appendPlainText(text)
            debug_trace(text)
        def open_device_tools(self):
            """Read-only hardware tools; device IDs are revalidated by the child CLI."""
            from .device_tools import DEVICE_ACTIONS, device_tool_args
            d=self.selected()
            if not d:
                QMessageBox.information(self,'Select a drive','Choose a verified external whole disk first.')
                return
            if self.proc and self.proc.state()!=QProcess.NotRunning:
                QMessageBox.information(self,'Busy','Finish the current operation first.')
                return
            labels=[name for name,_,_ in DEVICE_ACTIONS]
            selected,ok=QInputDialog.getItem(self,'Read-only hardware diagnostics',
                                              'Select an expert operation:',labels,0,False)
            if not ok:
                return
            _,command,risk=DEVICE_ACTIONS[labels.index(selected)]
            offset=None
            letter=''
            if command=='probe-region':
                typed,accepted=QInputDialog.getText(self,'Failed region offset',
                    'Enter a byte offset from a previous scan report:')
                if not accepted:
                    return
                try:
                    offset=int(typed)
                except (TypeError,ValueError):
                    QMessageBox.warning(self,'Invalid offset','Enter a nonnegative byte offset.')
                    return
            if command=='optimize-volume':
                letter,accepted=QInputDialog.getText(self,'Advisory only',
                    'Volume drive letter (for read-only Windows optimization advice):')
                if not accepted:
                    return
            if risk:
                confirmed=QMessageBox.warning(self,'Additional read stress',
                    'This operation reads a potentially failing drive and may accelerate its failure. '
                    'If data matters, make a rescue image first. Continue read-only investigation?',
                    QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
                if confirmed!=QMessageBox.Yes:
                    return
            try:
                args=device_tool_args(command,device_id=d['id'],fingerprint=str(d.get('identity_hint') or ''),
                    offset=offset,volume_letter=letter,read_risk_approved=risk)
            except (ValueError,PermissionError) as exc:
                QMessageBox.warning(self,'Cannot start diagnostic',str(exc))
                return
            self._last_good_device=d
            self._last_job_kind='device_diagnostic'
            self._job_args=args
            self.run_command(args)

        def open_specialist_tools(self):
            """Qt-native specialist image/forensics toolbox; no Tk subprocess."""
            from .advanced_workflows import ACTIONS, build_specialist_command
            if self.proc and self.proc.state()!=QProcess.NotRunning:
                QMessageBox.information(self,'Job already active',
                    'Finish or safely stop the active job before launching a specialist operation.')
                return
            dlg=QDialog(self)
            dlg.setWindowTitle('DriveRepair · Specialist recovery tools')
            dlg.setMinimumSize(620,490)
            layout=QVBoxLayout(dlg)
            layout.setSpacing(9)
            heading=QLabel('Specialist recovery tools')
            heading.setObjectName('heading')
            layout.addWidget(heading)
            note=QLabel('Work on regular-file images and NEW outputs; patient disks remain unchanged. '
                        'The same CLI validation is applied after you start. Tools may require Sleuth Kit or e2fsprogs.')
            note.setObjectName('muted')
            note.setWordWrap(True)
            layout.addWidget(note)
            picker=QComboBox()
            for item in ACTIONS:
                picker.addItem(item.label)
            layout.addWidget(picker)
            description=QLabel()
            description.setWordWrap(True)
            description.setObjectName('muted')
            layout.addWidget(description)
            fields={}
            for name,label in [('source','Source image / archive'), ('output','NEW output file / folder'),
                               ('manifest','Trusted hash manifest'), ('reference','Known-good reference image'),
                               ('file_ids','File IDs (comma separated)')]:
                line=QHBoxLayout()
                field_label=QLabel(label)
                field_label.setMinimumWidth(185)
                line.addWidget(field_label)
                edit=QLineEdit()
                edit.setAccessibleName(label)
                edit.setPlaceholderText(label)
                line.addWidget(edit,1)
                browse=QPushButton('Browse…') if name!='file_ids' else None
                if browse:
                    def browse_for(n=name,e=edit):
                        if n=='output':
                            target,_=QFileDialog.getSaveFileName(dlg,'Choose NEW file or folder')
                            if not target:
                                target=QFileDialog.getExistingDirectory(dlg,'Select destination directory')
                        else:
                            target,_=QFileDialog.getOpenFileName(dlg,'Choose '+n)
                        if target:
                            e.setText(target)
                    browse.clicked.connect(browse_for)
                    line.addWidget(browse)
                layout.addLayout(line)
                fields[name]=(field_label,edit,browse)
            details=QLabel('The selected operation will run locally in DriveRepair’s separate worker process.')
            details.setWordWrap(True)
            details.setObjectName('muted')
            layout.addWidget(details)
            buttons=QHBoxLayout()
            launch_button=QPushButton('Run selected tool')
            launch_button.setObjectName('primary')
            cancel_button=QPushButton('Close')
            cancel_button.clicked.connect(dlg.reject)
            buttons.addStretch()
            buttons.addWidget(cancel_button)
            buttons.addWidget(launch_button)
            layout.addLayout(buttons)
            def changed(*_):
                item=ACTIONS[picker.currentIndex()]
                description.setText(item.description)
                fields['source'][0].setText(item.source_label)
                fields['output'][0].setText(item.output_label)
                for name,visible in [('output',bool(item.output_flag)),('manifest',item.manifest),
                                     ('reference',item.reference),('file_ids',item.file_ids)]:
                    for widget in fields[name]:
                        if widget:
                            widget.setVisible(visible)
            picker.currentIndexChanged.connect(changed)
            changed()
            def begin():
                item=ACTIONS[picker.currentIndex()]
                needs_approval=item.clone_change
                approved=False
                if needs_approval:
                    answer=QMessageBox.warning(dlg,'Modify only a NEW copy',
                        'This operation may change or discard data in a NEW output copy. '
                        'The original is read-only. If using reference data, verify both files '
                        'represent the exact same point in time. Proceed?',
                        QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
                    if answer!=QMessageBox.Yes:
                        return
                    text,ok=QInputDialog.getText(dlg,'Confirm recovery-copy modification',
                                                 'Type REPAIR COPY to proceed:')
                    if not ok or text!='REPAIR COPY':
                        return
                    approved=True
                try:
                    args=build_specialist_command(item,
                        source=fields['source'][1].text(),output=fields['output'][1].text(),
                        manifest=fields['manifest'][1].text(),reference=fields['reference'][1].text(),
                        file_ids=fields['file_ids'][1].text(),clone_approved=approved)
                except (ValueError,PermissionError,FileExistsError) as exc:
                    QMessageBox.warning(dlg,'Check the operation',str(exc))
                    return
                dlg.accept()
                self._last_job_kind='specialist'
                self._last_good_device=None
                self._job_args=args
                self.run_command(args)
            launch_button.clicked.connect(begin)
            dlg.exec()

        def pick_image(self):
            path,_=QFileDialog.getOpenFileName(self,'Select source disk image','','Disk images (*.img *.dd *.raw);;All files (*)')
            if path:
                self.dest.setText(path)
        def choice_changed(self):
            kind=self.job_box.currentData()
            is_image=kind=='rescueimage'
            self.dest.setVisible(is_image)
            self.browse.setVisible(is_image)
            self.drive_panel.setVisible(not is_image)
            self.auto_resume.setVisible(kind in {'scanfull','resume','carefull'})
            self.auto_pause.setVisible(kind in {'scanquick','scanfull','resume'})
            self.batch_button.setVisible(kind == 'rescue')
            self.batch_status.setVisible(kind == 'rescue')
            self.smart_check_button.setVisible(kind in {'carequick','carefull','careresume'})
            self.smart_check_note.setVisible(kind in {'carequick','carefull','careresume'})
            self.offline_devices.setVisible(sys.platform=='linux' and kind == 'rescue')
            if kind != 'rescue' and self.offline_devices.isChecked():
                self.offline_devices.blockSignals(True)
                self.offline_devices.setChecked(False)
                self.offline_devices.blockSignals(False)
                QTimer.singleShot(0,self.refresh_devices)
            hints={'health':'Reads SMART attributes where available; no physical writes.',
                   'capacity':'Authenticity spot check: temporary writes to selected USB regions, readback, and restoration. Requires full backup and durable separate-drive journal. Not a normal health scan.',
                   'scanquick':'Samples at least 10% of the entire drive with distributed random locations; no writes.',
                   'scanfull':'Reads the full address space, saving a resumable local checkpoint.',
                   'carequick':'Investigates slow regions; may rewrite only consistently readable targets after consent.',
                   'carefull':'Full scan and bounded repair. Writes require separate explicit approval.',
                   'careresume':'Reopens a previously durable journal on a separate healthy disk and verifies patient identity before resuming interrupted writes.',
                   'rescue':'Copy readable sectors directly from the selected EXTERNAL drive to a NEW image on another healthy disk. The patient is read-only.',
                   'rescueimage':'Copy data from an existing source image to a different NEW image. Neither source is overwritten.',
                   'resume':'Rechecks identity before continuing the saved read-only scan position.'}
            self.opts.setText(hints.get(kind,''))
            guided = kind in {'carequick','carefull','careresume'}
            for widget in (self.total_caption,self.overall_label,self.progress):
                widget.setVisible(guided)
            impact, impact_detail=operation_impact(kind)
            self.operation_impact.setObjectName('warningTag' if kind in {'carequick','carefull','careresume'} else 'riskTag')
            self.operation_impact.setText(impact)
            self.operation_impact.setToolTip(impact_detail)
            self.operation_impact.style().unpolish(self.operation_impact)
            self.operation_impact.style().polish(self.operation_impact)
            self.start.setText('Start '+('capacity spot test' if kind=='capacity' else
                                         'read-only rescue' if kind in {'rescue','rescueimage'} else
                                         'diagnostics' if kind in {'health','scanquick','scanfull','resume'} else
                                         'authorized repair'))
            if guided:
                from .automatic_maintenance import choose_maintenance
                d=self.selected() or {}
                auto=choose_maintenance(model=str(d.get('model') or ''),
                    bus=str(d.get('bus') or ''),
                    snapshot=self._health_by_device.get(d.get('identity_hint')),
                    mode='full' if kind=='carefull' else 'quick')
                self.auto_plan_note.setText(f'Automatic plan · {auto.title}. {auto.explanation}')
            self.update_action_state()
        def quick_switch(self):
            """Keyboard-searchable local workflow switcher, no remote indexes."""
            if self.proc and self.proc.state()!=QProcess.NotRunning:
                return
            choices=[('Diagnose · quick read-only check','scanquick'),
                     ('Diagnose · complete surface scan','scanfull'),
                     ('Diagnose · SMART health','health'),
                     ('Rescue · external drive to image','rescue'),
                     ('Rescue · existing disk image','rescueimage')]
            if not PUBLIC_BETA_IMAGE_ONLY:
                choices.append(('Repair · experimental targeted rewrite','carequick'))
                choices.append(('Validate · USB authenticity spot test (writes+restores)','capacity'))
            dialog=QDialog(self)
            dialog.setWindowTitle('Quick switch · Ctrl+K')
            dialog.resize(425,320)
            layout=QVBoxLayout(dialog)
            query=QLineEdit()
            query.setPlaceholderText('Filter operations…')
            layout.addWidget(query)
            items=QListWidget()
            for title,_ in choices:
                items.addItem(title)
            layout.addWidget(items)
            items.setCurrentRow(0)
            def filter_items(value):
                first=-1
                for i,(name,_) in enumerate(choices):
                    visible=value.casefold() in name.casefold()
                    items.item(i).setHidden(not visible)
                    if visible and first<0:
                        first=i
                if first>=0:
                    items.setCurrentRow(first)
            query.textChanged.connect(filter_items)
            query.returnPressed.connect(dialog.accept)
            items.itemActivated.connect(lambda _:dialog.accept())
            query.setFocus()
            if dialog.exec()==QDialog.Accepted:
                row=items.currentRow()
                if 0<=row<len(choices) and not items.item(row).isHidden():
                    self.select_goal(choices[row][1])

        def update_action_state(self, *_):
            kind=self.job_box.currentData()
            running=self._batch_running or bool(self.proc and self.proc.state()!=QProcess.NotRunning)
            enabled, advice=can_start(kind, device_selected=bool(self.selected()),
                image_exists=bool(self.dest.text().strip() and Path(self.dest.text().strip()).is_file()),
                running=running, public_beta=PUBLIC_BETA_IMAGE_ONLY)
            if enabled and kind in {'carequick','carefull','careresume'}:
                from .repair_readiness import ui_repair_readiness
                dev=self.selected() or {}
                snap=self._health_by_device.get(dev.get('identity_hint'))
                ready, reason = ui_repair_readiness(dev,kind,snapshot=snap)
                if not ready:
                    enabled=False
                    advice=reason
            if self._pending_resume:
                enabled=False
                advice='Waiting for verified USB reconnect. Cancel reconnect to choose another operation.'
            if kind=='capacity':
                if PUBLIC_BETA_IMAGE_ONLY:
                    enabled=False
                    advice='Capacity testing writes temporarily to patient USB regions and is unavailable in the read-only public beta.'
                elif enabled and (self.selected() or {}).get('bus','').lower()!='usb':
                    enabled=False
                    advice='Capacity spot testing requires a selected external USB disk.'
                elif enabled:
                    advice='High-risk write/restore test. Use only a backed-up, disposable USB; an unreliable controller can overwrite unrelated data.'
            self.start.setEnabled(enabled)
            # When a repair is ineligible, expose the non-destructive next step
            # without a cryptic failed worker run. No source write is performed.
            self.rescue_instead.setVisible(kind in {'carequick','carefull','careresume'}
                and bool(self.selected()) and not enabled and not running)
            self.ready_note.setText(advice)
            self.start.setToolTip(advice)
            self.device_box.setEnabled(not running)
            self.offline_devices.setEnabled(not running)
            self.job_box.setEnabled(not running)
            self.auto_plan_note.setVisible(kind in {'carequick','carefull','careresume'})
            self.browse.setEnabled(not running)
            self.batch_button.setEnabled(not running)
            self.boot_button.setEnabled(not running)
            self.iso_button.setEnabled(not running and not (self.iso_proc and self.iso_proc.state()!=QProcess.NotRunning)
                and not (self.flash_proc and self.flash_proc.state()!=QProcess.NotRunning))
            self.boot_button.setEnabled(not running and not (self.flash_proc and self.flash_proc.state()!=QProcess.NotRunning))
            self.usb_flash_button.setEnabled(not running and
                not (self.flash_proc and self.flash_proc.state()!=QProcess.NotRunning) and
                not (self.iso_proc and self.iso_proc.state()!=QProcess.NotRunning))
            for family, button in self.nav_buttons.items():
                button.setEnabled(not running and (family != 'fix' or not PUBLIC_BETA_IMAGE_ONLY))
            self.refresh_button.setEnabled(not running)
            self.inspect_button.setEnabled(not running)
            self.smart_check_button.setEnabled(not running and bool(self.selected()) and
                not (self._auto_probe_proc and self._auto_probe_proc.state()!=QProcess.NotRunning))

        def export_detailed_report(self):
            result=self._last_job_result
            if not isinstance(result,dict) or not result:
                QMessageBox.information(self,'No report yet','Run a diagnostic, rescue or capacity test first.')
                return
            preferred=self._last_report_file if self._last_job_kind=='capacity' else None
            if preferred and Path(preferred).is_file():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(preferred).resolve())))
                return
            suggested='DriveRepair-evidence-'+time.strftime('%Y%m%d-%H%M%S')+'.html'
            path,_=QFileDialog.getSaveFileName(self,'Export local visual evidence report',
                 suggested,'HTML reports (*.html)')
            if not path:
                return
            if not path.lower().endswith('.html'):
                path+='.html'
            try:
                from .drive_report import save_report
                regions=None
                # Surface cells are only coarse evidence aggregates, not
                # equivalent to 576 individually validated capacity spots.
                if self._last_job_kind not in {'capacity','rescue','rescueimage'}:
                    coverage=self.map.coverage
                    if coverage.size>0:
                        regions=[]
                        for cell in coverage.cells:
                            status=('read_error' if cell.read_errors else
                                    'slow' if cell.slow_reads else
                                    'readable' if cell.fraction>=0.999 else
                                    'sampled' if cell.fraction>0 else 'untested')
                            regions.append({'offset':cell.start,'length':cell.end-cell.start,
                                            'status':status,'read_fraction':round(cell.fraction,4)})
                save_report(path,result,device=self._last_good_device or {},scan_regions=regions)
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).resolve())))
            except (OSError,ValueError) as exc:
                QMessageBox.warning(self,'Could not export report',str(exc)[:300])

        def copy_summary(self):
            device=(None if self._last_job_kind == 'rescueimage' else
                    (self._last_good_device or self.selected()))
            copied=operator_summary(
                operation={'carefull':'Full scan + targeted HDD maintenance',
                           'carequick':'Targeted HDD maintenance',
                           'careresume':'Resume journaled HDD maintenance',
                           'scanquick':'Quick read-only scan',
                           'scanfull':'Full read-only scan',
                           'rescue':'Rescue physical drive to image',
                           'rescueimage':'Rescue an existing image'}.get(
                               self._last_job_kind, self.job_box.currentText()),
                device=device, result=self.result.text(), explanation=self.explain.text(),
                progress=self.metric_labels['done'].text(),
                errors=self.metric_labels['errors'].text(),
                observed_coverage=self.coverage_label.text().replace('MEASURED COVERAGE  ·  ',''))
            QApplication.clipboard().setText(copied)
            self.copy_summary_button.setText('Copied to clipboard')
            QTimer.singleShot(2500,lambda:self.copy_summary_button.setText('Copy operator summary'))

        def enter_manufacturer_specs(self):
            d=self._last_good_device or self.selected()
            if not d:
                QMessageBox.warning(self,'Select a drive','Select a specific drive first.')
                return
            hours,ok=QInputDialog.getInt(self,'Documented model rating',
                'Manufacturer-published service-hour limit for this exact model (NOT MTBF).\n'
                'Only enter a value from the model datasheet.',
                0,0,10000000,1000)
            if not ok or hours==0:
                return
            self._manufacturer_rated_hours[d.get('identity_hint')]=hours
            if self._last_health_snapshot:
                from .reliability_score import assess
                self.show_condition(assess(self._last_health_snapshot,
                    manufacturer_specs={'rated_power_on_hours':hours}))
            self.note_log('Operator entered a purported model datasheet rating. '
                'DriveRepair cannot independently verify it or predict drive lifespan.')

        def show_condition(self, report, *, previous=None):
            if not isinstance(report,dict):
                return
            self.condition_gauge.set_assessment(report)
            score=report.get('score')
            self.condition_gauge.setVisible(type(score) in (int,float))
            self.spec_button.setVisible(type(report.get('power_on_hours')) is int)
            confidence=report.get('confidence') or 'unknown'
            self.condition_title.setText('Condition index: ' +
                ('Unknown' if score is None else f"{score}/100 · {report.get('band','UNKNOWN')}") +
                f'  ({confidence} evidence)')
            reasons=report.get('reasons') or []
            statement='; '.join(str(t) for t in reasons[:3])
            hours=report.get('power_on_hours')
            if type(hours) is int:
                statement+=f' · {hours:,} power-on hours'
            if previous and previous.get('score') is not None and score is not None:
                statement+=f" · Before {previous['score']}/100 → after {score}/100"
            self.condition_evidence.setText(statement +
                '\nCondition scores reflect observed warning signs, NOT remaining life or repair success.')

        def flash_boot_usb(self):
            """Real USB write wizard. CLI rechecks identity and OS permissions.

            GUI selection is advisory only; no raw handle is opened here.
            """
            if ((self.proc and self.proc.state()!=QProcess.NotRunning) or self._batch_running
                    or (self.iso_proc and self.iso_proc.state()!=QProcess.NotRunning)
                    or (self.flash_proc and self.flash_proc.state()!=QProcess.NotRunning)):
                QMessageBox.warning(self,'Operation in progress',
                    'Finish the current operation before preparing USB recovery media.')
                return
            from .boot_validation import qualify_live_iso
            from .recovery_media_catalog import find_local_recovery_iso
            from .devices import list_external_devices
            image=find_local_recovery_iso(preferred=str(self._media_settings.value('last_iso') or ''))
            if image is None:
                # A source checkout/zipapp contains the ISO BUILD RECIPE but not
                # a boot-tested OS image. Never silently substitute a random ISO.
                choose=QMessageBox(self)
                choose.setWindowTitle('DriveRepair recovery image not installed')
                choose.setText('No structurally complete DriveRepair live ISO was found.')
                choose.setInformativeText('A complete DriveRepair live ISO (kernel, initramfs, squashfs and BIOS/UEFI entries) must be built or included with the release. A 32 MiB placeholder with ISO markers is not enough. '
                    'On Windows, export the build kit for a Debian build host. '
                    'If you already have a hybrid ISO, select it once; it will be preselected next time.')
                browse=choose.addButton('Use existing ISO…',QMessageBox.AcceptRole)
                build=choose.addButton('Build ISO (Linux)',QMessageBox.ActionRole)
                export=choose.addButton('Export build kit',QMessageBox.ActionRole)
                choose.addButton(QMessageBox.Cancel)
                choose.exec()
                choice=choose.clickedButton()
                if choice == build:
                    self.build_iso()
                    return
                if choice == export:
                    self.export_boot_kit()
                    return
                if choice != browse:
                    return
                iso,_=QFileDialog.getOpenFileName(self,'Select ISO-hybrid image (not build-kit ZIP)',
                    '','Hybrid ISO images (*.iso)')
                if not iso:
                    return
                try:
                    image=qualify_live_iso(iso)
                except (OSError,ValueError) as exc:
                    QMessageBox.warning(self,'Invalid ISO',str(exc))
                    return
                self._media_settings.setValue('last_iso',image['path'])
            try:

                targets=[d for d in list_external_devices() if d.bus.lower()=='usb'
                         and d.serial.strip() and d.size_bytes>=image['bytes']]
                if not targets:
                    raise RuntimeError('No verified USB whole disks with serial and enough space found. '
                        'Reconnect USB and refresh inventory. Internal disks are never offered.')
            except (OSError,ValueError,RuntimeError) as exc:
                QMessageBox.warning(self,'Cannot prepare USB flash',str(exc))
                return

            class FlashDialog(QDialog):
                def closeEvent(inner,event):
                    if self.flash_proc and self.flash_proc.state()!=QProcess.NotRunning:
                        QMessageBox.warning(inner,'Flash in progress',
                            'The USB is being written or verified. Request Stop and leave it connected '
                            'until the worker exits. A partial image is unusable.')
                        event.ignore()
                    else:
                        event.accept()
                def reject(inner):
                    if self.flash_proc and self.flash_proc.state()!=QProcess.NotRunning:
                        QMessageBox.warning(inner,'Flash in progress',
                            'Request Stop first, then wait for the worker to finish.')
                        return
                    super().reject()

            dlg=FlashDialog(self)
            dlg.setWindowTitle('Create DriveRepair USB recovery media')
            dlg.setMinimumWidth(560)
            lay=QVBoxLayout(dlg)
            title=QLabel('Create DriveRepair recovery USB')
            title.setObjectName('heading')
            lay.addWidget(title)
            caption=QLabel('This ERASES THE ENTIRE SELECTED USB DRIVE — all partitions and files. '
                'Bootability is NOT guaranteed until BIOS/UEFI tests succeed. '
                'Never choose a recovery patient or a USB disk holding the ISO.')
            caption.setWordWrap(True)
            lay.addWidget(caption)
            image_label=QLabel('LIVE CONTENTS CHECKED · BOOT UNVERIFIED  ·  '+Path(image['path']).name+'  ·  '+display_size(image['bytes']))
            image_label.setObjectName('section')
            image_label.setWordWrap(True)
            lay.addWidget(image_label)
            source_note=QLabel('Local image auto-selected. Kernel, root filesystem and BIOS/UEFI catalog checked; firmware boot unverified. '
                'Choose a different ISO below only if needed. The image still requires actual boot testing.')
            source_note.setObjectName('muted')
            source_note.setWordWrap(True)
            lay.addWidget(source_note)
            separation=QLabel('THIS TOOL CREATES BOOT MEDIA; it does not image or back up a patient drive. '
                'For data recovery, choose Rescue data in the main window.')
            separation.setObjectName('muted')
            separation.setWordWrap(True)
            lay.addWidget(separation)
            rescue_navigation=QPushButton('I want to image a disk instead → Rescue data')
            lay.addWidget(rescue_navigation)
            def switch_to_rescue():
                if not (self.flash_proc and self.flash_proc.state()!=QProcess.NotRunning):
                    dlg.accept()
                    self.select_goal('rescue')
            rescue_navigation.clicked.connect(switch_to_rescue)
            other=QPushButton('Choose a different ISO…')
            lay.addWidget(other)
            def change_image():
                new_path,_=QFileDialog.getOpenFileName(dlg,'Select different hybrid ISO', '', 'Hybrid ISO images (*.iso)')
                if not new_path:
                    return
                try:
                    new_image=qualify_live_iso(new_path)
                except (OSError,ValueError) as exc:
                    QMessageBox.warning(dlg,'Invalid ISO',str(exc))
                    return
                if new_image['bytes']>max(x.size_bytes for x in targets):
                    QMessageBox.warning(dlg,'ISO too large','No discovered USB target can contain this image.')
                    return
                image.update(new_image)
                self._media_settings.setValue('last_iso',new_image['path'])
                image_label.setText('LIVE CONTENTS CHECKED · BOOT UNVERIFIED  ·  '+Path(image['path']).name+'  ·  '+display_size(image['bytes']))
                # On a new image size, all target choices must be reevaluated.
                target_box.clear()
                target_box.addItem('Choose a USB drive (nothing selected)',None)
                for disk in targets:
                    if disk.size_bytes >= image['bytes']:
                        target_box.addItem(f'{disk.model}  ·  {display_size(disk.size_bytes)}  ·  '
                            f'{disk.id}  ·  serial …{disk.serial[-4:]}',disk.id)
                typed.clear()
                update_confirm()
            other.clicked.connect(change_image)
            lay.addWidget(QLabel('1 · Select the sacrificial USB device'))
            target_box=QComboBox()
            target_box.addItem('Choose a USB drive (nothing selected)',None)
            for dev in targets:
                target_box.addItem(f'{dev.model}  ·  {display_size(dev.size_bytes)}  ·  '
                    f'{dev.id}  ·  serial …{dev.serial[-4:]}',dev.id)
            lay.addWidget(target_box)
            lay.addWidget(QLabel('2 · Type the exact ERASE confirmation shown below'))
            expected=QLabel('Select a USB target to view confirmation')
            lay.addWidget(expected)
            typed=QLineEdit()
            typed.setPlaceholderText('ERASE windows:PhysicalDriveN or ERASE linux:/dev/sdX')
            lay.addWidget(typed)
            ack=QCheckBox('I understand: THIS USB DRIVE WILL BE ERASED PERMANENTLY')
            ack.setChecked(False)
            ack.setToolTip('This deliberate confirmation is never preselected. The source/recovery patient must not be the USB target.')
            ack.setMinimumHeight(36)
            ack.setAccessibleDescription('Destructive operation confirmation, unchecked until accepted by the operator')
            lay.addWidget(ack)
            state=QLabel('Step 1/3: Select a disposable USB drive. Nothing has been written.')
            state.setWordWrap(True)
            lay.addWidget(state)
            bar=QProgressBar()
            bar.setRange(0,1000)
            bar.setValue(0)
            lay.addWidget(bar)
            row=QHBoxLayout()
            flash=QPushButton('Create recovery USB · erase and verify')
            flash.setObjectName('danger')
            flash.setEnabled(False)
            stop=QPushButton('Request safe stop')
            stop.setEnabled(False)
            done=QPushButton('Close')
            done.clicked.connect(dlg.reject)
            row.addWidget(flash)
            row.addWidget(stop)
            row.addWidget(done)
            lay.addLayout(row)
            details=QPlainTextEdit()
            details.setReadOnly(True)
            details.setMaximumHeight(110)
            lay.addWidget(details)
            active={'id':None,'fingerprint':None,'verified':False,'output':''}
            byid={d.id:d for d in targets}
            def update_confirm(*_):
                did=target_box.currentData()
                dev=byid.get(did)
                active['id']=did
                active['fingerprint']=dev.fingerprint[:12] if dev else None
                expected.setText('ERASE '+did if did else 'Select a USB target to view confirmation')
                from .usb_flash import flash_confirmation_state
                ready, instruction=flash_confirmation_state(
                    device_selected=bool(dev), typed_confirmation=typed.text(),
                    expected_confirmation='ERASE '+did if did else '',
                    acknowledge_data_loss=ack.isChecked(),
                    worker_running=bool(self.flash_proc and self.flash_proc.state()!=QProcess.NotRunning))
                flash.setEnabled(ready)
                if not (self.flash_proc and self.flash_proc.state()!=QProcess.NotRunning):
                    state.setText(instruction + (' Nothing has been written.' if not ready else
                        ' A final confirmation is still required.'))
                flash.setToolTip(instruction)
            target_box.currentIndexChanged.connect(update_confirm)
            typed.textChanged.connect(update_confirm)
            ack.toggled.connect(update_confirm)

            def begin():
                did=active['id']
                if not did or not ack.isChecked() or typed.text()!=f'ERASE {did}':
                    return
                if QMessageBox.question(dlg,'Final confirmation — ERASE USB',
                    'PERMANENT DATA LOSS on '+did+'\n\n'
                    'DriveRepair will replace the entire USB partition table and boot sectors. '
                    'Only select a disposable USB drive, NEVER a patient. Continue?',
                    QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:
                    return
                flash.setEnabled(False)
                target_box.setEnabled(False)
                typed.setEnabled(False)
                ack.setEnabled(False)
                done.setEnabled(False)
                stop.setEnabled(True)
                details.clear()
                active['verified']=False
                child=QProcess(dlg)
                self.flash_proc=child
                cmd=cli_prefix()+['flash-usb','--iso',str(image['path']),
                    '--device',did,'--confirm-identity',active['fingerprint'],
                    '--confirm-erase','ERASE '+did,'--ack-data-loss']
                child.setProgram(cmd[0])
                child.setArguments(cmd[1:])
                pending={'stdout':''}
                def stdout_ready():
                    pending['stdout']+=bytes(child.readAllStandardOutput()).decode('utf-8','replace')
                    while '\n' in pending['stdout']:
                        line,pending['stdout']=pending['stdout'].split('\n',1)
                        try:
                            event=json.loads(line)
                        except (ValueError,TypeError):
                            details.appendPlainText(line[:350])
                            continue
                        phase=str(event.get('phase') or event.get('status') or '').upper()
                        if event.get('phase')=='DONE' and event.get('status')=='USB_FLASH_BYTE_VERIFIED_BOOT_UNTESTED':
                            active['verified']=True
                        total=int(event.get('total_bytes') or 0)
                        if total:
                            bar.setValue(max(0,min(1000,int(1000*int(event.get('processed_bytes') or 0)/total))))
                        if phase:
                            state.setText(phase+' · '+
                                (display_size(int(event.get('processed_bytes') or 0))+' / '+display_size(total)
                                 if total else str(event.get('status') or '')))
                        if phase in ('DONE','FAILED'):
                            details.appendPlainText(json.dumps(event,sort_keys=True)[:600])
                child.readyReadStandardOutput.connect(stdout_ready)
                def stderr_ready():
                    msg=bytes(child.readAllStandardError()).decode('utf-8','replace').strip()
                    if msg:
                        details.appendPlainText(msg[-700:])
                child.readyReadStandardError.connect(stderr_ready)
                def finished(code,status):
                    stdout_ready()
                    stderr_ready()
                    success=(code==0 and active['verified'])
                    state.setText('USB image byte-verified — BIOS/UEFI boot not tested' if success
                        else 'FLASH FAILED / INCOMPLETE — USB must NOT be used for recovery')
                    bar.setValue(1000 if success else bar.value())
                    details.appendPlainText('Exit code: '+str(code)+'. '
                        +('Verify BIOS and UEFI boot on sacrificial hardware.' if success else
                          'Target may contain a partially written image. Inspect the error; reflash fully.'))
                    self.flash_proc=None
                    done.setEnabled(True)
                    stop.setEnabled(False)
                    self.update_action_state()
                child.finished.connect(finished)
                self.update_action_state()
                child.start()
            flash.clicked.connect(begin)
            def request_stop():
                if self.flash_proc and self.flash_proc.state()!=QProcess.NotRunning:
                    self.flash_proc.write(b'STOP\n')
                    stop.setEnabled(False)
                    state.setText('Stop requested — waiting for current USB I/O boundary')
            stop.clicked.connect(request_stop)
            dlg.exec()

        def export_boot_kit(self):
            """Make the existing Linux ISO builder discoverable without writing a USB."""
            from .boot_media import export_build_kit
            repo=Path(__file__).resolve().parents[2]
            output,_=QFileDialog.getSaveFileName(self,'Export Linux live-ISO build kit',
                'DriveRepair-Live-Build-Kit.zip','ZIP archives (*.zip)')
            if not output:
                return
            try:
                info=export_build_kit(repo,output)
            except (OSError,ValueError) as exc:
                QMessageBox.warning(self,'Boot kit not created',str(exc))
                return
            QMessageBox.information(self,'Build kit ready — NOT an ISO',
                f"Created {info['path']}\n\n"
                'Extract on a clean Debian trixie x86-64 build VM. Read BOOT_KIT_INSTRUCTIONS.txt, '
                'build the ISO, then verify BIOS and UEFI boot and patient read-only behavior. '
                'The builder does not automatically write USB media.')

        def build_iso(self):
            """Opt-in Debian live-build job, no USB device writing.

            Prerequisites are deliberately strict because build failures must
            not be sold as distributable recovery media.
            """
            import shutil
            if sys.platform!='linux' or not hasattr(os,'geteuid') or os.geteuid()!=0:
                QMessageBox.information(self,'Build requires isolated Debian Linux VM',
                    'Build ISO requires a prepared Debian trixie x86-64 build environment with root '
                    'and live-build/debootstrap. On Windows, choose Bootable media builder to export '
                    'the complete build kit. No USB drive is written by either action.')
                return
            if not all(shutil.which(tool) for tool in ('lb','debootstrap','sha256sum')):
                QMessageBox.warning(self,'Missing Debian build tools',
                    'Install live-build, debootstrap, xorriso and prerequisites in a disposable Debian VM.')
                return
            script=Path(__file__).resolve().parents[2]/'scripts'/'build_live_iso.sh'
            if not script.is_file():
                import tempfile
                import zipfile
                from .boot_media import export_build_kit
                self._iso_build_temp=tempfile.TemporaryDirectory(prefix='driverepair-iso-kit-')
                temporary=Path(self._iso_build_temp.name)
                try:
                    kit=temporary/'builder.zip'
                    export_build_kit(None,kit)
                    with zipfile.ZipFile(kit) as z:
                        z.extractall(temporary)
                    script=temporary/'driverepair'/'scripts'/'build_live_iso.sh'
                except (OSError,ValueError,zipfile.BadZipFile) as exc:
                    self._iso_build_temp.cleanup()
                    self._iso_build_temp=None
                    QMessageBox.warning(self,'Builder unavailable',str(exc))
                    return
            folder=QFileDialog.getExistingDirectory(self,'Select EMPTY output directory on the build VM')
            if not folder:
                return
            if any(Path(folder).iterdir()):
                QMessageBox.warning(self,'Not an empty output folder','Choose an empty, dedicated output folder.')
                return
            approval=QMessageBox.question(self,'Build experimental ISO',
                'The Debian live-build recipe is NOT boot-verified. It downloads packages, uses root '
                'inside the isolated build VM and writes ONLY ordinary build files and ISO output. '
                'It does not write USB media. Continue?',
                QMessageBox.Yes | QMessageBox.No,QMessageBox.No)
            if approval!=QMessageBox.Yes:
                return
            self._iso_output_folder=Path(folder)
            self.iso_proc=QProcess(self)
            self.iso_proc.setProgram('bash')
            self.iso_proc.setArguments([str(script),str(Path(folder).resolve())])
            self.iso_proc.readyReadStandardOutput.connect(lambda:self.note_log(
                bytes(self.iso_proc.readAllStandardOutput()).decode('utf-8','replace')[-1200:]))
            self.iso_proc.readyReadStandardError.connect(lambda:self.note_log(
                bytes(self.iso_proc.readAllStandardError()).decode('utf-8','replace')[-1200:]))
            self.iso_proc.finished.connect(lambda code,status:self.iso_finished(code))
            self.details_button.setChecked(True)
            self.note_log('UNVERIFIED ISO build started. Wait for native tool completion and SHA-256 receipt.')
            self.iso_button.setEnabled(False)
            self.iso_proc.start()

        def iso_finished(self,code):
            if code == 0:
                from .recovery_media_catalog import find_local_recovery_iso
                image=find_local_recovery_iso(search_roots=[getattr(self,'_iso_output_folder',Path.cwd())])
                if image:
                    self._media_settings.setValue('last_iso',image['path'])
                    self.note_log('New local live image available to Create recovery USB: '+Path(image['path']).name)
            self.note_log('ISO builder exited with status '+str(code)+
                '. Both BIOS and UEFI boot tests are required before distribution.')
            self.iso_proc=None
            if self._iso_build_temp is not None:
                self._iso_build_temp.cleanup()
                self._iso_build_temp=None
            self.update_action_state()
            QMessageBox.information(self,'ISO builder finished' if code==0 else 'ISO build failed',
                'The builder exited with '+str(code)+'. Check Expert log and verify checksum, BIOS, '
                'UEFI, device enumeration, no-automount and read-only behavior. '
                'An ISO output is NOT a validated bootable recovery product.')

        def _keep_host_awake(self, enabled):
            """Best effort Windows OS system-sleep inhibition for an active queue."""
            if sys.platform != 'win32':
                return
            try:
                import ctypes
                kernel=ctypes.WinDLL('kernel32', use_last_error=True)
                kernel.SetThreadExecutionState.argtypes=[ctypes.c_uint32]
                kernel.SetThreadExecutionState.restype=ctypes.c_uint32
                # ES_CONTINUOUS | ES_SYSTEM_REQUIRED. Does not override lid,
                # forced sleep, shutdown, firmware or power-loss conditions.
                state=0x80000001 if enabled else 0x80000000
                prior=kernel.SetThreadExecutionState(state)
                self._batch_sleep_prevented=bool(enabled and prior)
                if enabled and not prior:
                    self.note_log('WARNING: could not inhibit Windows system sleep; unattended rescue may pause.')
            except (OSError,AttributeError):
                self.note_log('Windows sleep-inhibition unavailable; monitor system power policy.')

        def queue_rescue(self):
            """Require per-source selection and new destinations before unattended reads."""
            if self._batch_running or (self.proc and self.proc.state()!=QProcess.NotRunning):
                return
            if not self._devices:
                QMessageBox.warning(self,'No source drives','Refresh the device inventory first.')
                return
            dialog=QDialog(self)
            dialog.setWindowTitle('Queue read-only imaging — multiple drives')
            dialog.resize(650,430)
            layout=QVBoxLayout(dialog)
            layout.addWidget(QLabel('Select one or more source drives. Each will be reidentified by the engine.\n'
                'Images are created sequentially, never in parallel. No physical repair writes are queued.'))
            drive_list=QListWidget()
            drive_list.setSelectionMode(QAbstractItemView.MultiSelection)
            for d in self._devices:
                drive_list.addItem(f"{d.get('model','Unknown')}  ·  {display_size(d.get('size_bytes') or 0)}  "
                    f"·  {d.get('identity_hint','unknown')}")
            layout.addWidget(drive_list)
            accept=QPushButton('Continue with selected drives')
            accept.setObjectName('primary')
            accept.clicked.connect(dialog.accept)
            layout.addWidget(accept)
            if dialog.exec()!=QDialog.Accepted:
                return
            drives=[self._devices[i.row()] for i in drive_list.selectedIndexes()]
            if not drives:
                QMessageBox.warning(self,'No drives selected','Select at least one source drive.')
                return
            folder=QFileDialog.getExistingDirectory(self,'Select a folder on a DIFFERENT, healthy destination disk')
            if not folder:
                return
            from .unattended import plan_rescue_batch, batch_manifest_path, store_manifest
            try:
                jobs=plan_rescue_batch(drives,folder)
            except (ValueError, OSError) as exc:
                QMessageBox.warning(self,'Unsafe rescue plan',str(exc))
                return
            question=QMessageBox.question(self,'Authorize unattended READ-ONLY rescue',
                f'{len(jobs)} drives, {display_size(sum(j["size_bytes"] for j in jobs))} total source bytes.\n'
                f'Destination: {folder}\n\n'
                'Each output will be a NEW file. The engine checks device identity and destination ancestry '
                'before imaging. A drive failure does not authorize writes and the next selected drive '
                'will be attempted. Repeated read errors can stress failing media.\n\n'
                'You must personally verify that the destination is healthy separate physical storage. Proceed?',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if question!=QMessageBox.Yes:
                return
            manifest=batch_manifest_path(folder)
            try:
                store_manifest(manifest,jobs)
            except (OSError,ValueError) as exc:
                QMessageBox.warning(self,'Could not persist queue',str(exc))
                return
            self._batch_queue=jobs
            self._batch_results=[]
            self._batch_manifest=manifest
            self._batch_current=None
            self.select_goal('rescue')
            self._batch_running=True
            self._keep_host_awake(True)
            self._launch_next_batch()

        def _launch_next_batch(self):
            if not self._batch_running:
                return
            if not self._batch_queue:
                self._batch_running=False
                self._keep_host_awake(False)
                good=sum(x['status']=='COMPLETE' for x in self._batch_results)
                self.batch_status.setText(f'Batch finished: {good}/{len(self._batch_results)} image jobs returned success. '
                    'Inspect each .rescue.json journal for missing ranges.')
                self.result.setText('Batch finished · review each journal')
                self.stop.setEnabled(False)
                self.update_action_state()
                return
            self._batch_current=self._batch_queue.pop(0)
            job=self._batch_current
            matching=[d for d in self._devices if d.get('id')==job['device_id'] and
                      d.get('identity_hint')==job['fingerprint']]
            if len(matching)!=1:
                job['status']='SKIPPED_IDENTITY_CHANGED'
                self._batch_results.append(job)
                from .unattended import append_batch_event
                append_batch_event(self._batch_manifest,job)
                self._batch_current=None
                QTimer.singleShot(0,self._launch_next_batch)
                return
            d=matching[0]
            for i in range(self.device_box.count()):
                if (self.device_box.itemData(i) or {}).get('id')==job['device_id']:
                    self.device_box.setCurrentIndex(i)
                    break
            self._last_good_device=d
            self._last_job_kind='rescue'
            self.batch_status.setText(f'Imaging {len(self._batch_results)+1} of '
                f'{len(self._batch_results)+len(self._batch_queue)+1}: {job["model"]}\n'
                f'Output: {job["output"]}')
            args=['rescue-external','--device',job['device_id'],'--output',job['output'],
                '--ack-risk','--multi-pass','--progress-jsonl','--no-live-dashboard','--json']
            if sys.platform=='linux' and self.offline_devices.isChecked():
                args=['rescue-system','--device',job['device_id'],'--output',job['output'],
                    '--ack-risk','--ack-offline-system','--expect-fingerprint',job['fingerprint'],
                    '--multi-pass','--progress-jsonl','--no-live-dashboard','--json']
            self.run_command(args)

        def refresh_devices(self):
            if self.inventory_proc and self.inventory_proc.state()!=QProcess.NotRunning:
                return
            self.device_note.setText('Looking for external drives…')
            self.inventory_proc=QProcess(self)
            self.inventory_proc.setProgram(cli_prefix()[0])
            self.inventory_proc.setArguments(cli_prefix()[1:]+[
                'list-all-linux' if (sys.platform=='linux' and self.offline_devices.isChecked())
                else 'list','--json'])
            self.inventory_proc.finished.connect(self.inventory_done)
            self.inventory_proc.start()
        def inventory_done(self,code,_status):
            stdout=bytes(self.inventory_proc.readAllStandardOutput()).decode('utf-8','replace')
            stderr=bytes(self.inventory_proc.readAllStandardError()).decode('utf-8','replace')
            if code!=0:
                self.device_note.setText('Device discovery failed. Reconnect the USB dock and retry; never bypass identity checks.')
                self.note_log(stderr[:3000])
                self.update_action_state()
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
                description=(f"{d['model']}    •    {display_size(d['size_bytes'])}    "
                             f"•    {d['bus']}    •    {d.get('serial_suffix','')}")
                self.device_box.addItem(description,d)
                self.device_box.setItemData(self.device_box.count()-1, description, Qt.ToolTipRole)
            if prev:
                for i,d in enumerate(data):
                    if d.get('id')==prev.get('id') and d.get('identity_hint')==prev.get('identity_hint'):
                        self.device_box.setCurrentIndex(i)
                        break
            self.device_note.setText(f'{len(data)} whole disk(s) available (offline Linux)' if self.offline_devices.isChecked() else
                f'{len(data)} external drive(s) available. Fresh identity required before writes.')
            self.update_action_state()
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
            if (self.proc and self.proc.state()!=QProcess.NotRunning):
                QMessageBox.information(self,'Drive details',
                    'Finish the active operation before querying this USB device again. '
                    'Device details from inventory remain available in the selector.')
                return
            if getattr(self,'inspect_proc',None) and self.inspect_proc.state()!=QProcess.NotRunning:
                return
            self._inspect_device=dict(d)
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
            report={}
            if exit_code == 0:
                try:
                    report=json.loads(raw)
                except (ValueError,TypeError):
                    err='Storage driver returned invalid metadata'
            else:
                self.note_log('Optional host drive inspection failed: '+err[:1000])
            # Do not attribute a delayed USB response to another selected disk.
            identified=getattr(self,'_inspect_device',{})
            if self.selected() and identified.get('identity_hint') != self.selected().get('identity_hint'):
                self.note_log('Discarded stale inspection for a previously selected device.')
                return
            QMessageBox.information(self,'Drive details (read-only)',
                drive_inspection_text(identified,report,error=err.strip()[:220])[:4000])
        def start_job(self):
            self._auto_probe_timer.stop()
            if self._auto_probe_proc and self._auto_probe_proc.state()!=QProcess.NotRunning:
                self._auto_probe_proc.kill()  # bounded read-only SMART probe; do not compete with recovery
            self._pending_resume=None
            self._reconnect_timer.stop()
            if self.proc and self.proc.state()!=QProcess.NotRunning:
                return
            kind=self.job_box.currentData()
            if PUBLIC_BETA_IMAGE_ONLY and kind in {'carefull', 'carequick', 'careresume'}:
                QMessageBox.information(self, 'Public beta: image-first',
                    'In-place physical-drive writes are disabled in this build. '
                    'Select Check for a read-only scan, or Recover to a NEW image.')
                return
            d=self.selected()
            if kind in {'carequick','carefull','careresume'}:
                from .repair_readiness import ui_repair_readiness
                ready, reason = ui_repair_readiness(d,kind,
                    snapshot=self._health_by_device.get((d or {}).get('identity_hint')))
                if not ready:
                    QMessageBox.warning(self,'Drive is not eligible for physical writes',reason)
                    return
            if kind == 'capacity':
                if not d or str(d.get('bus','')).lower()!='usb' or PUBLIC_BETA_IMAGE_ONLY:
                    QMessageBox.warning(self,'External USB required',
                        'This write/restore test is restricted to backed-up external USB disks in guarded/engineering builds.')
                    return
                warning=QMessageBox.warning(self,'Capacity spot test — potential data loss',
                    'This is NOT a read-only test. DriveRepair temporarily overwrites small locations '
                    'and attempts to restore original bytes. An untrustworthy USB controller can alias '
                    'writes into OTHER locations which cannot be restored. Never test a recovery patient '
                    'or irreplaceable files; use only a disposable device with a verified backup.\n\n'
                    f'Selected: {d.get("model", "Unknown")} · {d.get("serial_suffix", "unknown")}\n'
                    'Continue only if all data has been backed up and you accept possible permanent loss.',
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if warning!=QMessageBox.Yes:
                    return
                token='TEST '+str(d.get('identity_hint',''))
                typed,accepted=QInputDialog.getText(self,'Confirm exact USB target',
                    f'Type exactly {token} to authorize the selected USB test:')
                if not accepted or typed!=token:
                    QMessageBox.warning(self,'Not authorized','Target confirmation did not match. No test was started.')
                    return
                parent=QFileDialog.getExistingDirectory(self,'Choose journal parent on a DIFFERENT healthy disk')
                if not parent:
                    return
                import secrets
                journal=os.path.join(parent,'DriveRepair-Capacity-'+secrets.token_hex(5))
                suggested='DriveRepair-capacity-'+time.strftime('%Y%m%d-%H%M%S')+'.html'
                report,_=QFileDialog.getSaveFileName(self,'Save detailed evidence report to healthy storage',
                    suggested,'HTML report (*.html)')
                if not report:
                    return
                if not report.lower().endswith('.html'):
                    report+='.html'
                if os.path.lexists(report):
                    QMessageBox.warning(self,'Existing report','Choose a NEW report path. Existing files are not overwritten.')
                    return
                args=['validate-usb-capacity','--device',d['id'],
                    '--confirm-identity',d['identity_hint'], '--confirm-test',token,
                    '--ack-data-loss','--ack-backed-up','--journal',journal,
                    '--samples','144','--report-html',report,'--cooperative-stop-stdin','--progress-jsonl','--json']
                self._last_report_file=report
            elif kind in {'rescue','rescueimage'}:
                if kind == 'rescue' and not d:
                    QMessageBox.warning(self,'Choose an external drive','Select the SOURCE drive to rescue first.')
                    return
                src=self.dest.text().strip() if kind == 'rescueimage' else ''
                if kind == 'rescueimage' and not Path(src).is_file():
                    QMessageBox.warning(self,'Source required','Select a readable source image.')
                    return
                out,_=QFileDialog.getSaveFileName(self,'NEW rescue image (choose another healthy drive)',
                                                 'recovered.img','Disk image (*.img);;All files (*)')
                if not out:
                    return
                if os.path.lexists(out) or os.path.lexists(out+'.rescue.json'):
                    QMessageBox.warning(self,'Existing recovery data','Choose a NEW image path; existing files and journals are never overwritten.')
                    return
                if kind == 'rescueimage':
                    if os.path.realpath(src) == os.path.realpath(out):
                        QMessageBox.warning(self,'Unsafe destination','Source and destination must be different.')
                        return
                    args=['rescue-image','--image',src,'--output',out]
                else:
                    question=QMessageBox.question(self,'Confirm image-first rescue',
                        f"Source: {d.get('model','Unknown')}  ({display_size(d.get('size_bytes') or 0)})\n"
                        f"Identity hint: {d.get('identity_hint','unknown')}\n"
                        f"Destination: {out}\n\n"
                        'This reads the selected failing drive and writes ONLY to the new destination image. '
                        'The destination must be on a SEPARATE, healthy physical disk. '
                        'A first pass is followed by bounded rereads of missing ranges; extra reads may '
                        'worsen a severely damaged drive. For irreplaceable data consider a recovery lab. Proceed?',
                        QMessageBox.Yes | QMessageBox.No)
                    if question != QMessageBox.Yes:
                        return
                    if sys.platform=='linux' and self.offline_devices.isChecked():
                        args=['rescue-system','--device',d['id'],'--output',out,'--ack-risk',
                            '--ack-offline-system','--expect-fingerprint',d['identity_hint']]
                    else:
                        args=['rescue-external','--device',d['id'],'--output',out,'--ack-risk']
                args+=['--multi-pass','--progress-jsonl','--no-live-dashboard','--json']
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
                        snap=self._health_by_device.get(d.get('identity_hint')) or {}
                        plan=tuned_scan(size=int(d['size_bytes']),sector=int(d['sector_size']),
                                        mode='quick',bus=str(d.get('bus') or ''),
                                        model=str(d.get('model') or ''),
                                        media_type=str(snap.get('reported_medium') or ''),
                                        protocol=str(snap.get('device_protocol') or ''))
                        args+=['--chunk-mib',str(plan['chunk']//(1024*1024)),
                               '--samples',str(plan['samples']),'--max-errors','10000',
                               '--compare-suspects','--randomize-samples']
                    if kind in ('scanfull','resume'):
                        snap=self._health_by_device.get(d.get('identity_hint')) or {}
                        from .guided_repair import tuned_scan
                        plan=tuned_scan(size=int(d['size_bytes']),sector=int(d['sector_size']),
                                        mode='full',bus=str(d.get('bus') or ''),
                                        model=str(d.get('model') or ''),
                                        media_type=str(snap.get('reported_medium') or ''),
                                        protocol=str(snap.get('device_protocol') or ''))
                        args+=['--chunk-mib',str(plan['chunk']//(1024*1024)),'--ack-risk']
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
                    # No silent consent: --ack-no-backup and media-warning flags
                    # must correspond to a deliberate operator decision.
                    consent=QMessageBox.question(self,'Confirm recovery and data-loss risk',
                        'A repair does NOT recover unreadable original bytes or restore the lifespan of failing hardware.\n\n'
                        'Have you rescued your important data to separate storage, or have you explicitly chosen '
                        'to accept the possibility of permanent data loss?\n\n'
                        'YES means I accept the risk and allow the application to continue to the final identity checks.',
                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                    if consent != QMessageBox.Yes:
                        return
                    warning_consent=QMessageBox.question(self,'SMART warning policy',
                        'If this drive reports reallocated, pending or uncorrectable sectors, '
                        'do you separately authorize attempting a small, journaled rewrite of '
                        'repeatably readable regions?\n\n'
                        'An unreadable sector is NEVER overwritten by this operation. '
                        'Choose No to block writes whenever SMART reports a media warning.',
                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                    media_warning_args=['--ack-media-warning'] if warning_consent == QMessageBox.Yes else []
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
                        volatile=(None if REPAIR_BETA_GUARDED else
                                  dialog.addButton('RAM-only — high risk',QMessageBox.DestructiveRole))
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
                        elif volatile is not None and selected_choice==volatile:
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
                    maint='auto'  # Freshly evaluated in the engine after live SMART identification
                    args=['care-external','--cooperative-stop-stdin','--device',dev,'--mode','full' if kind=='carefull' else 'quick',
                          '--maintenance-level',maint,
                          *journal_args,'--auto-lock-volumes','--confirm-identity',d['identity_hint'],
                          '--ack-risk','--ack-destructive','--ack-no-backup','--ack-data-loss-risk',
                          '--ack-usb-bridge-risk','--ack-unvalidated-hardware',
                          *media_warning_args,
                          '--progress-jsonl','--json']
                    if REPAIR_BETA_GUARDED:
                        args += ['--max-regions','16']
                    else:
                        # Engineering builds can explicitly investigate unknown health;
                        # a guarded release requires full smartctl evidence.
                        args += ['--ack-unknown-health']
                    if save_scan_map:
                        args+=['--scan-checkpoint','auto']
            self._last_good_device=(None if kind == 'rescueimage' else d)
            self._last_job_kind=kind
            self._job_args=args
            self.run_command(args)
        def reveal_job_evidence(self):
            if self._has_job_evidence:
                return
            self._has_job_evidence=True
            self.progress.show()
            self.phase_caption.show()
            self.total_caption.show()
            self.overall_label.show()
            for key,tile in self.metric_tiles.items():
                if key!='avg':
                    tile.show()
            self.map_card.show()

        def run_command(self,args):
            self.progress.setValue(0)
            self.phase_progress.setValue(0)
            self.overall_label.setText('0% estimated')
            self.total_caption.setText('Rescue pass progress · not proof of disk health'
                if self._last_job_kind in {'rescue','rescueimage'} else
                'Estimated whole-job progress · staged estimate, not disk coverage')
            self._stop_requested=False
            self._stall_terminated=False
            # Image rescue must never inherit the size of an unrelated drive
            # that happens to remain selected in the (hidden) drive picker.
            source_size=(0 if self._last_job_kind == 'rescueimage' else
                         int((self._last_good_device or self.selected() or {}).get('size_bytes') or 0))
            self.map.reset(source_size)
            self.speed_graph.clear()
            self.coverage_label.setText('MEASURED COVERAGE  ·  0.00%')
            self.evidence_scope.setText('Untested is unknown')
            self.result.setText('Running — monitoring the device')
            self.explain.setText('Unknown regions remain unknown until observed.')
            self.status.setText('Starting · validating device')
            self.help.setText('Identifying the selected device and checking access before reads. '
                'No media repair is claimed until readback verification completes.')
            self._buf={'stdout':'','stderr':''}
            self._final_stdout=''
            self._last_job_result=None
            self.detailed_report_button.setEnabled(False)
            self._scanned=0
            self._last_progress_at=time.monotonic()
            self._rescue_started_at=self._last_progress_at
            self._rescue_sample=None
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
            self.copy_summary_button.setEnabled(False)
            self.proc.start()
            self.update_action_state()
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
            self.reveal_job_evidence()
            self._last_progress_at=time.monotonic()
            if event.get('workflow') == 'rescue':
                return self.rescue_progress_event(event)
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
            self.metric_headers['read'].setText('SAMPLED LOCATIONS' if phase=='CAPACITY_TEST' else 'DATA REWRITTEN' if phase=='REFRESH' else 'DATA READ')
            self.metric_headers['errors'].setText('FAILED SPOTS' if phase=='CAPACITY_TEST' else 'READ ERRORS')
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
            self.metric_labels['done'].setText(f'{pct:.1f}% · {phase.lower()}')
            self.metric_labels['eta'].setText(format_eta(event.get('eta_seconds')))
            if event.get('attempted_bytes') is not None:
                self.metric_labels['read'].setText(display_size(event['attempted_bytes']))
            elif event.get('rewritten_bytes') is not None:
                self.metric_labels['read'].setText(display_size(event['rewritten_bytes']))
            if event.get('read_error_chunks') is not None:
                self.metric_labels['errors'].setText(str(event['read_error_chunks']))
            if event.get('speed_bps') is not None:
                self.metric_labels['rate'].setText(display_size(event['speed_bps'])+'/s')
                self.speed_graph.ingest(event['speed_bps'])
            else:
                probe_total=int(event.get('probe_total') or 0)
                probe_index=int(event.get('probe_index') or 0)
                # A job that finishes inside one rate-window sample has no
                # recent speed; show the measured average instead of a stale
                # "Measuring…" placeholder.
                shown,is_average=choose_speed(None,event.get('average_speed_bps'),
                                              finished=bool(probe_total) and probe_index>=probe_total)
                if shown:
                    self.metric_labels['rate'].setText(
                        display_size(shown)+('/s avg' if is_average else '/s'))
            if event.get('average_speed_bps') is not None:
                self.metric_labels['avg'].setText(display_size(event['average_speed_bps'])+'/s')
            if phase!='INVESTIGATING':
                self.help.setText(str(event.get('message') or 'Checking device…'))
            self.map.ingest(event)
            self.advice.setText(f'Full-drive map: {self.map.coverage.coverage_pct:.2f}% read successfully. '
                                'Colored stripes mark observations, not full-region certification.')
            self.coverage_label.setText(f'MEASURED COVERAGE  ·  {self.map.coverage.coverage_pct:.2f}%')
            self.evidence_scope.setText('Read coverage ≠ media health')
        def rescue_progress_event(self, event):
            self.reveal_job_evidence()
            phase=str(event.get('phase') or 'FORWARD').upper()
            self.status.setText('Rescuing readable data' if phase == 'FORWARD' else 'Retrying missing ranges')
            self.phase_caption.setText('First pass  •  save readable data' if phase == 'FORWARD'
                                       else 'Targeted retry  •  isolate unreadable sectors')
            pct=progress_percent(event)
            self.phase_progress.setValue(round(pct * 10))
            # Retry is separately presented, not incorrectly counted as 100%
            # complete merely because the entire source was visited once.
            self.progress.setValue(round(pct * 10))
            self.overall_label.setText(f'{pct:.1f}% of '+('retry pass' if phase == 'RETRY' else 'source visited'))
            self.metric_headers['read'].setText('SAVED TO IMAGE')
            self.metric_headers['errors'].setText('MISSING DATA')
            self.metric_labels['done'].setText(f'{pct:.1f}% · {phase.lower()}')
            self.metric_labels['read'].setText(display_size(event.get('recovered_bytes') or 0))
            self.metric_labels['errors'].setText(display_size(event.get('unreadable_bytes') or 0))
            now=time.monotonic()
            processed=int(event.get('processed_bytes') or 0)
            saved=int(event.get('recovered_bytes') or 0)
            elapsed=max(0.001, now - (self._rescue_started_at or now))
            self.metric_labels['avg'].setText(display_size(saved / elapsed)+'/s')
            prior=self._rescue_sample
            if prior and now - prior[0] >= 0.1 and prior[3] == phase:
                dt=now-prior[0]
                velocity=max(0.0, saved - prior[2]) / dt
                traversal=max(0.0, processed - prior[1]) / dt
                self.metric_labels['rate'].setText(display_size(velocity)+'/s')
                self.speed_graph.ingest(velocity)
                remaining=max(0, int(event.get('total_bytes') or 0) - processed)
                self.metric_labels['eta'].setText(
                    format_eta(remaining / traversal) if phase == 'FORWARD' and traversal > 0 else 'Unknown')
            else:
                self.metric_labels['rate'].setText('Measuring…')
                self.metric_labels['eta'].setText('Unknown' if phase == 'RETRY' else 'Estimating…')
            self._rescue_sample=(now, processed, saved, phase)
            self.map.ingest(event)
            self.help.setText('Recovery image is a working copy, not proof of restored source drive health. '
                              'Unrecovered bytes remain marked missing in the journal.')
            self.advice.setText('Green = source data saved to image; red = missing/failed ranges; '
                                'amber = partial work; dark = unprocessed. Map is approximate, not a file checksum.')
            self.coverage_label.setText('RESCUE MAP  ·  Approximate journal state')
            self.evidence_scope.setText('Copied bytes ≠ verified files')
            self.result.setText(f"{display_size(event.get('recovered_bytes') or 0)} rescued  •  "
                                f"{display_size(event.get('unreadable_bytes') or 0)} unresolved")
            self.explain.setText('The source drive is never written. Inspect the .rescue.json map '
                                 'before using the image; recovered bytes are not certified correct.')

        def job_done(self,exit_code,_status):
            self.consume('stdout')
            self.consume('stderr')
            user_stop_requested = self._stop_requested
            self.start.setEnabled(True)
            self.stop.setEnabled(False)
            self.metric_labels['eta'].setText('—')
            if self.metric_labels['rate'].text() == 'Waiting on drive':
                self.metric_labels['rate'].setText('—')
            self.help.setText('Worker exited. Only completed reads and verified transactions are evidence; '
                              'a stalled kernel request may still require reconnecting the device.')
            self.phase_caption.setText('Worker exited · final outcome shown below')
            self.proc=None
            self._stop_requested=False
            if exit_code==0 and self._final_stdout.strip():
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
            self._last_job_result=result if result else None
            self.detailed_report_button.setEnabled(bool(result))
            condition_report = result.get('condition_comparison') or {}
            key=(self._last_good_device or {}).get('identity_hint')
            if key and isinstance(result,dict):
                report=result.get('health_after') if isinstance(result.get('health_after'),dict) else result
                if isinstance(report.get('ata_selected_raw_attributes'),list) or isinstance(report.get('nvme'),dict):
                    self._health_by_device[key]=report
                    # During completion, the selected drive may have changed;
                    # only render observations under a matching fingerprint.
                    if self.selected() and self.selected().get('identity_hint') == key:
                        QTimer.singleShot(0,self.update_drive_profile)
            if isinstance(result.get('health_after'),dict):
                self._last_health_snapshot=result['health_after']
            elif isinstance(result.get('ata_selected_raw_attributes'),list) or isinstance(result.get('nvme'),dict):
                self._last_health_snapshot=result
            rating=self._manufacturer_rated_hours.get(
                (self._last_good_device or {}).get('identity_hint'))
            if rating and self._last_health_snapshot:
                from .reliability_score import assess
                before=result.get('health_before')
                self.show_condition(assess(self._last_health_snapshot,
                    manufacturer_specs={'rated_power_on_hours':rating}),
                    previous=assess(before,manufacturer_specs={'rated_power_on_hours':rating})
                    if isinstance(before,dict) else None)
            elif isinstance(condition_report,dict) and condition_report.get('after'):
                self.show_condition(condition_report['after'], previous=condition_report.get('before'))
            elif isinstance(result.get('condition_assessment'),dict):
                self.show_condition(result['condition_assessment'])
            text=str(result.get('status') or ('Completed' if exit_code==0 else 'Incomplete / attention needed'))
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
                if self._last_job_kind in ('rescue','rescueimage'):
                    missing=sum(length for _, length in result.get('missing_ranges', []))
                    self.result.setText(f"Data copied: {display_size(result.get('recovered_bytes') or 0)}")
                    self.explain.setText(f"Unresolved: {display_size(missing)}. "
                        'Source drive left unchanged. Review the rescue journal before using the image; '
                        'unreadable areas were NOT reconstructed or replaced with invented bytes.')
                elif self._last_job_kind in ('scanquick','scanfull','resume') or 'surface_coverage_pct' in result:
                    if status_code.startswith('completed_with_'):
                        self.result.setText(f'Scan complete with findings ({status_code})')
                    else:
                        self.result.setText('Scan complete — diagnosis only')
                    self.explain.setText(
                        f'Read-only diagnosis finished.{coverage_txt} '
                        'This is not Quick Repair and does not rewrite sectors. '
                        'A completed read is not proof of file integrity.')
                elif status_code == 'completed_targeted_refresh':
                    pv=result.get('postverification') or {}
                    completed=int((result.get('repair') or {}).get('rewritten_bytes') or 0)
                    self.result.setText(f'Journaled HDD repair complete · {display_size(completed)} rewritten')
                    self.explain.setText(
                        f"Independent prewrite-digest check: {pv.get('status','unavailable')}. "
                        'The source remains at risk: back up, monitor SMART and perform a long self-test. '
                        'A rewrite cannot restore worn hardware.')
                    self.next_action.setText('Verify important recovered files and schedule a SMART long test. Replace disks with recurring errors.')
                else:
                    self.result.setText('Job finished — review results')
                    self.explain.setText(
                        f'A completed read or readback match is not proof of file integrity or restored lifespan.'
                        f'{coverage_txt}')
            elif result.get('status') in {'repair_postverify_failed','repair_postverify_unavailable','repair_health_deteriorated'}:
                self.result.setText('Repair verification raised a media warning')
                self.explain.setText('A repeat read or SMART check indicates the drive cannot be treated as repaired. '
                    'Stop writes, rescue important files to healthy storage, and consider replacement.')
                self.next_action.setText('Rescue data; inspect the repair journal and verification report.')
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
                self.next_action.setText('Do not bypass Windows volume locks. Save a rescue image, '
                    'or use a separately verified offline Linux recovery environment to inspect the drive.')
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
            presentation=repair_presentation(result, exit_code=exit_code)
            if presentation and not user_stop_requested:
                self.result.setText(presentation.heading)
                self.explain.setText(presentation.explanation)
                self.status.setText(presentation.status_label)
                self.metric_headers['errors'].setText('FAILED READ ATTEMPTS')
                self.overall_label.setText('Planned steps ended · inspect findings')
                self.metric_labels['done'].setText('Steps finished · findings remain'
                    if presentation.complete_with_unresolved else 'Planned steps finished')
            
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
            if self._last_job_kind=='capacity':
                counters=result.get('counters') if isinstance(result.get('counters'),dict) else {}
                verified=int(counters.get('validated') or 0)
                requested=int(result.get('samples_planned') or 0)
                self.result.setText(('Spot test completed · sampled locations verified' if exit_code==0 else
                                     'Capacity integrity warnings · review test evidence'))
                self.explain.setText(f'{verified}/{requested} random-pattern sampled regions matched and were restored. '
                    'A passing spot test does NOT certify full USB capacity or exclude aliasing into other data. '
                    'Review the detailed report. Do not use a device with any mismatch for important files.')
                self.next_action.setText('Review the per-location report; on disposable storage consider a full-capacity '
                    'write-and-verify test before relying on the USB. Do not repeat on a recovery patient.')
                self.metric_labels['done'].setText(f'{verified} / {requested} sample passes')
                self.metric_labels['errors'].setText(str(max(0,requested-verified)))
            self.copy_summary_button.setEnabled(True)
            if self._last_job_kind=='capacity':
                pass  # keep capacity-specific advice
            elif self._pending_resume:
                self.next_action.setText('Reconnect the exact same drive for the saved read-only scan. Verify its identity first.')
            elif self._last_job_kind in ('rescue','rescueimage'):
                self.next_action.setText('Keep the source unchanged. Inspect the image journal for missing ranges and validate important recovered files.')
            elif result.get('status')=='repair_blocked_prewrite_access':
                self.next_action.setText('Keep the patient unchanged. Check Windows Administrator rights, '
                    'mounted/RAW partitions and the Expert log. Prefer offline rescue before further writes.')
            elif exit_code == 0:
                self.next_action.setText('Review measured coverage and error evidence. For important data, make a separate recovery image before any further intervention.')
            else:
                self.next_action.setText('Review the reported failure and Expert log before retrying. Do not bypass volume locks or identity verification.')
            if presentation and not user_stop_requested:
                self.next_action.setText(presentation.next_action)
            if self._batch_running and self._batch_current:
                finished=dict(self._batch_current)
                finished['status']='COMPLETE' if exit_code == 0 else ('STALLED_OR_INTERRUPTED' if self._stall_terminated else 'FAILED')
                finished['exit_code']=int(exit_code)
                self._batch_results.append(finished)
                self.batch_status.setText(f"{finished['model']} → {finished['status']}; "
                    f"{len(self._batch_queue)} jobs remaining. Check output journal for missing data.")
                from .unattended import append_batch_event
                append_batch_event(self._batch_manifest, finished)
                self._batch_current=None
                self._stall_terminated=False
                QTimer.singleShot(0,self._launch_next_batch)
            self.update_action_state()
        def closeEvent(self, event):
            if self.flash_proc and self.flash_proc.state()!=QProcess.NotRunning:
                QMessageBox.warning(self,'USB flash underway',
                    'Please wait for full image verification or request a safe stop. '
                    'A partially flashed USB is not bootable or reliable.')
                event.ignore()
                return
            if self.iso_proc and self.iso_proc.state()!=QProcess.NotRunning:
                QMessageBox.warning(self,'ISO build in progress',
                    'The experimental ISO builder is still running on this build VM. '
                    'Review Expert log before stopping a privileged build.')
                event.ignore()
                return
            if self.proc and self.proc.state()!=QProcess.NotRunning:
                if self._last_job_kind in ('carefull','carequick','careresume','capacity'):
                    answer=QMessageBox.question(self,'Physical write may be in progress',
                        'The active transaction cannot be forcibly interrupted safely. '
                        'Request a cooperative stop and keep DriveRepair open until the engine finishes?',
                        QMessageBox.Yes | QMessageBox.No)
                else:
                    answer=QMessageBox.question(self,'Job still running',
                        'Request Stop and wait for the job result before closing?',
                        QMessageBox.Yes | QMessageBox.No)
                if answer==QMessageBox.Yes:
                    self.stop_job()
                event.ignore()
                return
            event.accept()

        def stop_job(self):
            if self._batch_running:
                self._batch_queue.clear()
                self.batch_status.setText('Queued jobs cancelled; current read-only imaging continues to its journal boundary.')
                if self.proc and self.proc.state()!=QProcess.NotRunning:
                    self.result.setText('Queue cancelled · current rescue still running')
                    self.stop.setEnabled(False)
                    return
                self._batch_running=False
                self._keep_host_awake(False)
                self.update_action_state()
                return
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
            if self._last_job_kind in ('carefull','carequick','careresume','capacity'):
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
