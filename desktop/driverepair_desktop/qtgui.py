"""DriveRepair Workstation (PySide6, optional).

The Qt process never opens patient media. All I/O is done by the existing
isolated CLI, whose safety checks are authoritative. This is a deliberately
small front-end, not an alternate disk-repair engine.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
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


def _qt_debug_log_path() -> Path | None:
    """Optional durable mirror for Qt workstation diagnostics (Admin debug sessions)."""
    flag = os.environ.get('DRIVEREPAIR_GUI_DEBUG', '').strip().lower()
    if flag not in {'1', 'true', 'yes', 'on'}:
        return None
    stamp = time.strftime('%Y%m%dT%H%M%S')
    candidates = [
        Path(os.environ['DRIVEREPAIR_GUI_DEBUG_LOG']) if os.environ.get('DRIVEREPAIR_GUI_DEBUG_LOG') else None,
        Path(r'D:\DriveRepairLab\seagate_st1000lm048_wipe_refresh_20261101') / f'gui_debug_{stamp}.log',
        Path.home() / 'DriveRepairLab' / f'gui_debug_{stamp}.log',
        Path(os.environ.get('TEMP', '.')) / f'DriveRepair_gui_debug_{stamp}.log',
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
                )
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
            QPlainTextEdit, QMessageBox, QCheckBox, QScrollArea)
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
        pane = QFrame(); pane.setObjectName('card')
        lay = QVBoxLayout(pane); lay.setContentsMargins(18,16,18,16);lay.setSpacing(gap)
        parent_layout.addWidget(pane)
        return lay

    class ScanMap(QWidget):
        def __init__(self):
            super().__init__(); self.setMinimumHeight(130)
            self.bins = ['unknown'] * 384
            self.total = 0
        def reset(self, size):
            self.total = int(size or 0); self.bins = ['unknown'] * 384; self.update()
        def ingest(self, event):
            size = int(event.get('size') or self.total or 0)
            if size < 1: return
            self.total = size
            offset = int(event.get('offset') or 0)
            length = int(event.get('read_length') or event.get('length') or 0)
            if length < 1: return
            first = max(0, min(len(self.bins)-1, offset * len(self.bins)//size))
            last = max(first, min(len(self.bins)-1, (offset+length-1)*len(self.bins)//size))
            state = 'error' if event.get('failed') else 'slow' if (event.get('latency_ms') or 0) > max(500, (event.get('median_ms') or 0)*4) else 'good'
            for i in range(first, last+1):
                # Preserve error evidence; later successful reads are not proof of no damage.
                if self.bins[i] != 'error' or state == 'error': self.bins[i] = state
            self.update()
        def paintEvent(self, _):
            p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
            colors = {'unknown':'#253951','good':'#36b794','slow':'#eeaa52','error':'#ed6472'}
            cols=48; rows=8; gap=3
            w=max(3,(self.width()-gap*(cols-1))/cols); h=max(5,(self.height()-gap*(rows-1))/rows)
            p.setPen(Qt.NoPen)
            for i, val in enumerate(self.bins):
                x=(i%cols)*(w+gap); y=(i//cols)*(h+gap)
                p.setBrush(QColor(colors[val])); p.drawRoundedRect(QRectF(x,y,w,h),2.5,2.5)
            p.end()

    class Workstation(QMainWindow):
        def __init__(self):
            super().__init__();self.setWindowTitle('DriveRepair | Recovery Workstation')
            self.resize(1210,850); self.setMinimumSize(850,640)
            self._pending = None; self._mode = None; self._buf = {'stdout':'','stderr':''};self._final_stdout = ''
            self._devices=[]; self._job_args=[]; self._last_job_kind='';self._last_good_device=None
            self._scanned=0
            self._last_progress_at=None
            self._heartbeat=QTimer(self);self._heartbeat.setInterval(1000)
            self._heartbeat.timeout.connect(self.check_stall);self._heartbeat.start()
            self.proc = None; self.inventory_proc = None
            self.setStyleSheet(css)
            central=QWidget();self.setCentralWidget(central)
            root=QVBoxLayout(central);root.setContentsMargins(22,18,22,16);root.setSpacing(14)
            header=QHBoxLayout(); root.addLayout(header)
            brand=QVBoxLayout();label=QLabel('DriveRepair');label.setObjectName('heading');brand.addWidget(label)
            sub=QLabel('RECOVERY WORKSTATION  •  PRIVATE BY DESIGN');sub.setObjectName('eyebrow');brand.addWidget(sub)
            header.addLayout(brand);header.addStretch()
            self.details_button=QPushButton('Expert details');self.details_button.setCheckable(True)
            self.details_button.toggled.connect(self.show_details);header.addWidget(self.details_button)
            self.legacy=QPushButton('Legacy tools');self.legacy.clicked.connect(self.open_legacy);header.addWidget(self.legacy)
            hero = card(root)
            self.status=QLabel('Ready to help');self.status.setObjectName('heading');hero.addWidget(self.status)
            self.help=QLabel('Choose a drive and what you need to do. Nothing starts until you press Start.')
            self.help.setWordWrap(True);self.help.setObjectName('muted');hero.addWidget(self.help)
            self.progress=QProgressBar();self.progress.setRange(0,1000);self.progress.setValue(0);hero.addWidget(self.progress)
            metrics=QHBoxLayout();hero.addLayout(metrics)
            self.metric_labels={}
            for key,title in [('done','PROGRESS'),('read','DATA READ'),('rate','RECENT SPEED'),('avg','JOB AVERAGE'),('errors','READ ERRORS')]:
                area=QVBoxLayout();m=QLabel(title);m.setObjectName('eyebrow');area.addWidget(m)
                v=QLabel('—');v.setObjectName('metric');area.addWidget(v);metrics.addLayout(area,1)
                self.metric_labels[key]=v
            body=QHBoxLayout();root.addLayout(body,1)
            left=QVBoxLayout();body.addLayout(left,2)
            l=card(left)
            pick=QHBoxLayout();l.addLayout(pick)
            ttl=QLabel('01  Select a drive');ttl.setStyleSheet('font-weight:700;font-size:15px');pick.addWidget(ttl)
            pick.addStretch();btn=QPushButton('Refresh drives');btn.clicked.connect(self.refresh_devices);pick.addWidget(btn)
            self.device_box=QComboBox();l.addWidget(self.device_box)
            self.device_note=QLabel('The selected disk will be identified again before physical writes.')
            self.device_note.setWordWrap(True);self.device_note.setObjectName('muted');l.addWidget(self.device_note)
            workflow=card(left)
            title=QLabel('02  Choose a goal');title.setStyleSheet('font-weight:700;font-size:15px');workflow.addWidget(title)
            goals=QHBoxLayout();workflow.addLayout(goals)
            for title,goal in [('Fix my drive','carequick'),('Recover files','rescue'),('Check drive','scanquick')]:
                b=QPushButton(title)
                b.clicked.connect(lambda _,g=goal:self.select_goal(g))
                goals.addWidget(b)
            advanced=QLabel('Or choose a specific operation:');advanced.setObjectName('muted');workflow.addWidget(advanced)
            self.job_box=QComboBox()
            for caption,kind in [('Check disk health (read-only)','health'),('Quick surface check (read-only)','scanquick'),
                                 ('Full surface scan (read-only)','scanfull'),('Quick targeted repair (experimental)','carequick'),
                                 ('Full scan + targeted repair (experimental)','carefull'),
                                 ('Rescue image / recover files','rescue'),('Continue interrupted full scan','resume')]:
                self.job_box.addItem(caption,kind)
            self.job_box.currentIndexChanged.connect(self.choice_changed);workflow.addWidget(self.job_box)
            self.dest=QLineEdit(); self.dest.setPlaceholderText('Choose an existing source image…')
            self.browse=QPushButton('Choose image…');self.browse.clicked.connect(self.pick_image)
            pathrow=QHBoxLayout();pathrow.addWidget(self.dest,1);pathrow.addWidget(self.browse);workflow.addLayout(pathrow)
            self.opts=QLabel('Automatic settings  •  Read-only by default  •  No uploads')
            self.opts.setObjectName('muted');workflow.addWidget(self.opts)
            act=QHBoxLayout();workflow.addLayout(act)
            self.start=QPushButton('Start selected job');self.start.setObjectName('primary');self.start.clicked.connect(self.start_job);act.addWidget(self.start,1)
            self.stop=QPushButton('Stop');self.stop.setObjectName('danger');self.stop.setEnabled(False)
            self.stop.clicked.connect(self.stop_job);act.addWidget(self.stop)
            right=QVBoxLayout();body.addLayout(right,3)
            map_card=card(right)
            map_title=QLabel('Surface activity');map_title.setStyleSheet('font-weight:700;font-size:15px');map_card.addWidget(map_title)
            self.map=ScanMap();map_card.addWidget(self.map)
            legend=QLabel('<span style="color:#36b794">■</span> Readable     '
                          '<span style="color:#eeaa52">■</span> Slow     '
                          '<span style="color:#ed6472">■</span> Read error     '
                          '<span style="color:#253951">■</span> Untested')
            legend.setTextFormat(Qt.RichText);map_card.addWidget(legend)
            self.advice=QLabel('A green block means data could be read. It does not prove file integrity or long-term drive health.')
            self.advice.setWordWrap(True);self.advice.setObjectName('muted');map_card.addWidget(self.advice)
            result_card=card(right)
            self.result=QLabel('No job running');self.result.setStyleSheet('font-size:16px;font-weight:700');result_card.addWidget(self.result)
            self.explain=QLabel('Recovery reports will show what is verified, unresolved, and untested.')
            self.explain.setWordWrap(True);self.explain.setObjectName('muted');result_card.addWidget(self.explain)
            self.log=QPlainTextEdit();self.log.setReadOnly(True);self.log.setMaximumBlockCount(4000)
            self.log.setVisible(bool(debug_log_path));root.addWidget(self.log)
            if debug_log_path is not None:
                self.log.appendPlainText(f'Debug tracking ON — {debug_log_path}')
                debug_trace(f'Debug tracking ON — {debug_log_path}\n')
                self.setWindowTitle(self.windowTitle() + ' [DEBUG]')
            self.select_goal('scanquick')
            QTimer.singleShot(100,self.refresh_devices)
        def select_goal(self, goal):
            for i in range(self.job_box.count()):
                if self.job_box.itemData(i)==goal:
                    self.job_box.setCurrentIndex(i);break
            self.choice_changed()
        def check_stall(self):
            if (self.proc and self.proc.state()!=QProcess.NotRunning
                    and self._last_progress_at is not None
                    and time.monotonic()-self._last_progress_at>8):
                self.metric_labels['rate'].setText('Waiting on drive')
                self.help.setText('No progress event recently. The drive or OS may be retrying I/O; Stop is not instant.')
        def show_details(self, yes): self.log.setVisible(yes)
        def note_log(self, text: str) -> None:
            self.log.appendPlainText(text)
            debug_trace(text)
        def open_legacy(self):
            QMessageBox.information(self,'Legacy toolkit','For advanced file-system, forensic, firmware-information and refresh tools, run:  python -m driverepair_desktop gui-legacy  (the existing Tk interface).')
        def pick_image(self):
            path,_=QFileDialog.getOpenFileName(self,'Select source disk image','','Disk images (*.img *.dd *.raw);;All files (*)')
            if path:self.dest.setText(path)
        def choice_changed(self):
            kind=self.job_box.currentData();is_image=kind=='rescue'
            self.dest.setVisible(is_image);self.browse.setVisible(is_image)
            hints={'health':'Reads SMART attributes where available; no physical writes.',
                   'scanquick':'Samples the disk to locate suspicious areas without writes.',
                   'scanfull':'Reads the full address space, saving a resumable local checkpoint.',
                   'carequick':'Investigates slow regions; may rewrite only consistently readable targets after consent.',
                   'carefull':'Full scan and bounded repair. Writes require separate explicit approval.',
                   'rescue':'Rescue data from an existing image to a new file, leaving the original unchanged.',
                   'resume':'Rechecks identity before continuing the saved read-only scan position.'}
            self.opts.setText(hints.get(kind,''))
        def refresh_devices(self):
            if self.inventory_proc and self.inventory_proc.state()!=QProcess.NotRunning:return
            self.device_note.setText('Looking for external drives…')
            self.inventory_proc=QProcess(self)
            self.inventory_proc.setProgram(cli_prefix()[0]);self.inventory_proc.setArguments(cli_prefix()[1:]+['list','--json'])
            self.inventory_proc.finished.connect(self.inventory_done);self.inventory_proc.start()
        def inventory_done(self,code,_status):
            stdout=bytes(self.inventory_proc.readAllStandardOutput()).decode('utf-8','replace')
            stderr=bytes(self.inventory_proc.readAllStandardError()).decode('utf-8','replace')
            if code!=0:
                self.device_note.setText('Device discovery failed. Reconnect the USB dock and retry; never bypass identity checks.')
                self.note_log(stderr[:3000]);return
            try: data=json.loads(stdout)
            except (ValueError,TypeError):
                self.device_note.setText('Could not interpret drive inventory');return
            prev=self.device_box.currentData()
            self.device_box.clear();self._devices=data
            for d in data:
                self.device_box.addItem(f"{d['model']}    •    {display_size(d['size_bytes'])}    •    {d['bus']}    •    {d.get('serial_suffix','')}",d)
            if prev:
                for i,d in enumerate(data):
                    if d.get('id')==prev.get('id') and d.get('identity_hint')==prev.get('identity_hint'):
                        self.device_box.setCurrentIndex(i);break
            self.device_note.setText(f'{len(data)} external drive(s) available. Exact identity rechecked before writes.')
        def selected(self):return self.device_box.currentData()
        def start_job(self):
            if self.proc and self.proc.state()!=QProcess.NotRunning:return
            kind=self.job_box.currentData(); d=self.selected()
            if kind=='rescue':
                src=self.dest.text().strip()
                if not Path(src).is_file():QMessageBox.warning(self,'Source required','Select a readable source image.');return
                out,_=QFileDialog.getSaveFileName(self,'New recovery image (must not exist)','recovered.img','Disk image (*.img);;All files (*)')
                if not out:return
                if os.path.exists(out):QMessageBox.warning(self,'Destination exists','Choose a new file; no existing image will be overwritten.');return
                args=['rescue-image','--image',src,'--output',out,'--multi-pass','--progress-jsonl','--no-live-dashboard','--json']
            else:
                if not d:QMessageBox.warning(self,'Choose a drive','Connect a drive and select it first.');return
                dev=d['id']
                if kind=='health':args=['health','--device',dev,'--json']
                elif kind in {'scanquick','scanfull','resume'}:
                    args=['scan','--device',dev,'--mode','full' if kind in ('scanfull','resume') else 'triage',
                          '--progress-jsonl','--json']
                    if kind in ('scanfull','resume'):args+=['--ack-risk']
                    if kind=='resume':args+=['--resume-scan']
                else:
                    answer=QMessageBox.question(self,'Experimental physical writes',
                        'DriveRepair can permanently damage data on a failing drive.\n\n'
                        'Only consistently readable regions are eligible. A RAM-only write has no crash recovery.\n\n'
                        'Would you like to review an explicit device confirmation?',
                        QMessageBox.Yes | QMessageBox.No)
                    if answer!=QMessageBox.Yes:return
                    from PySide6.QtWidgets import QInputDialog
                    typed,ok=QInputDialog.getText(self,'Confirm target disk',
                        f"Type this disk fingerprint to allow in-place writes:  {d['identity_hint']}")
                    if not ok or typed.strip()!=d['identity_hint']:
                        QMessageBox.warning(self,'Not authorized','Fingerprint did not match. No job started.');return
                    confirm=QMessageBox.warning(self,'Volatile memory risk',
                        'Continue with NO backup and RAM-only journal? Power loss, USB resets or a crash can permanently destroy the active region. '
                        'This is a controlled experimental mode, not a guaranteed repair.',
                        QMessageBox.Yes | QMessageBox.No)
                    if confirm!=QMessageBox.Yes:return
                    save_scan_map = False
                    if kind == 'carefull':
                        save_scan_map = QMessageBox.question(
                            self,'Resume after USB disconnect',
                            'Save a small, private read-only scan checkpoint locally? '
                            'It contains byte positions and error locations, never sector contents. '
                            'This is separate from the RAM-only write journal and lets a scan continue after reconnect.',
                            QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes
                    args=['care-external','--device',dev,'--mode','full' if kind=='carefull' else 'quick',
                          '--journal-backend','memory','--ack-volatile-journal','--confirm-identity',d['identity_hint'],
                          '--ack-risk','--ack-destructive','--ack-no-backup','--ack-data-loss-risk',
                          '--ack-usb-bridge-risk','--ack-unvalidated-hardware','--ack-unknown-health',
                          '--progress-jsonl','--json']
                    if save_scan_map: args+=['--scan-checkpoint','auto']
            self._last_good_device=d
            self._last_job_kind=kind;self._job_args=args
            self.run_command(args)
        def run_command(self,args):
            self.progress.setValue(0);self.map.reset(int((self.selected() or {}).get('size_bytes') or 0))
            self.result.setText('Running — monitoring the device');self.explain.setText('Unknown regions remain unknown until observed.')
            self.status.setText('Working…');self.help.setText('Read-only where possible; no results are inferred from the progress bar.')
            self._buf={'stdout':'','stderr':''};self._final_stdout='';self._scanned=0
            self._last_progress_at=time.monotonic()
            self.proc=QProcess(self);self.proc.setProgram(cli_prefix()[0]);self.proc.setArguments(cli_prefix()[1:]+args)
            self.proc.readyReadStandardError.connect(lambda:self.consume('stderr'))
            self.proc.readyReadStandardOutput.connect(lambda:self.consume('stdout'))
            self.proc.finished.connect(self.job_done)
            self.start.setEnabled(False);self.stop.setEnabled(True);self.proc.start()
        def consume(self,channel):
            if not self.proc:return
            data=bytes(self.proc.readAllStandardError() if channel=='stderr' else self.proc.readAllStandardOutput()).decode('utf-8','replace')
            if channel == 'stdout':
                self._final_stdout += data
                return
            self._buf[channel]+=data
            while '\n' in self._buf[channel]:
                line,self._buf[channel]=self._buf[channel].split('\n',1)
                try:obj=json.loads(line)
                except (ValueError,TypeError):
                    if line:self.note_log(line[:1200]);continue
                if isinstance(obj,dict) and obj.get('type')=='progress':self.progress_event(obj)
                else:self._pending=obj
        def progress_event(self,event):
            self._last_progress_at=time.monotonic()
            self.status.setText(str(event.get('phase') or 'WORKING').replace('_',' ').title())
            size=int(event.get('size') or self.map.total or 0)
            cursor=int(event.get('scan_position_bytes') or event.get('offset') or 0)
            idx=event.get('probe_index');total=event.get('probe_total')
            if idx is not None and total and str(event.get('scan_mode','')) in ('triage','sample'):
                pct=max(0,min(100,float(idx)/float(total)))
            else:
                pct=100.0*cursor/size if size else 0.0
            self.progress.setValue(max(0,min(1000,round(10*pct))))
            self.metric_labels['done'].setText(f'{pct:.1f}%')
            if event.get('attempted_bytes') is not None:
                self.metric_labels['read'].setText(display_size(event['attempted_bytes']))
            elif event.get('rewritten_bytes') is not None:
                self.metric_labels['read'].setText(display_size(event['rewritten_bytes']))
            if event.get('read_error_chunks') is not None:self.metric_labels['errors'].setText(str(event['read_error_chunks']))
            if event.get('speed_bps') is not None:self.metric_labels['rate'].setText(display_size(event['speed_bps'])+'/s')
            if event.get('average_speed_bps') is not None:self.metric_labels['avg'].setText(display_size(event['average_speed_bps'])+'/s')
            self.help.setText(str(event.get('message') or 'Checking device…'))
            self.map.ingest(event)
        def job_done(self,exit_code,_status):
            self.consume('stdout');self.consume('stderr')
            self.start.setEnabled(True);self.stop.setEnabled(False)
            self.proc=None
            try:
                result=json.loads(self._final_stdout)
            except (ValueError,TypeError):
                result=self._pending if isinstance(self._pending,dict) else {}
                if self._final_stdout.strip():self.note_log(self._final_stdout[-3000:])
            if not isinstance(result,dict):result={}
            text=str(result.get('status') or ('Completed' if exit_code==0 else 'Stopped / failed'))
            self.status.setText(text.replace('_',' ').title())
            if exit_code==0:
                self.result.setText('Job finished — review results')
                self.explain.setText('A completed read or readback match is not proof of file integrity or restored lifespan.')
            elif 'device' in text or 'identity' in text or 'access' in text or 'discon' in text or result.get('scan',{}).get('status')=='aborted_device_or_access_error':
                self.result.setText('Drive connection interrupted')
                self.explain.setText('Reconnect the same drive, refresh the list, and select “Continue interrupted full scan”. Reverification is mandatory; no write restarts automatically.')
            else:
                self.result.setText(f'Stopped / attention needed  ({exit_code})')
                self.explain.setText('Open Expert details for the specific error. No health claim is made.')
            if result.get('scan_checkpoint'):
                self.note_log('Scan checkpoint: '+str(result['scan_checkpoint']))
            if 'read_error_chunks' in result:self.metric_labels['errors'].setText(str(result['read_error_chunks']))
        def closeEvent(self, event):
            if self.proc and self.proc.state()!=QProcess.NotRunning:
                if self._last_job_kind in ('carefull','carequick'):
                    QMessageBox.warning(self,'Write in progress',
                        'Please keep DriveRepair open during the in-place transaction. '
                        'The engine does not yet support verified cooperative write cancellation.')
                    event.ignore()
                    return
                answer=QMessageBox.question(self,'Scan in progress',
                    'Stop the read-only job and close the workstation?',
                    QMessageBox.Yes | QMessageBox.No)
                if answer!=QMessageBox.Yes:
                    event.ignore();return
                self.proc.terminate()
                if not self.proc.waitForFinished(2500):
                    self.proc.kill();self.proc.waitForFinished(1000)
            event.accept()

        def stop_job(self):
            if not self.proc or self.proc.state()==QProcess.NotRunning:return
            if self._last_job_kind in ('carefull','carequick'):
                QMessageBox.warning(self,'Do not interrupt a write',
                    'Stopping a physical write mid-transaction can destroy data. The engine has no verified cooperative stop protocol yet. '
                    'This interface will not forcibly terminate the active write. Disconnect only if necessary to protect hardware.')
                return
            self.proc.terminate()
            self.result.setText('Stopping — waiting for process exit')
    app=QApplication.instance() or QApplication(sys.argv)
    win=Workstation();win.show()
    if os.environ.get('DRIVEREPAIR_QT_SMOKE') == '1':
        QTimer.singleShot(850, app.quit)
    return app.exec()


if __name__ == '__main__':
    sys.exit(launch())
