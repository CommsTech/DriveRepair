"""Regression tests for telemetry and checkpoint durability during failures."""
from __future__ import annotations

import io
import json
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from driverepair_desktop.progress_events import ProgressEmitter
from driverepair_desktop.scan_checkpoint import ScanCheckpoint, load


def _events(stream):
    return [json.loads(line) for line in stream.getvalue().splitlines()]


def test_phase_change_flushes_read_evidence_before_completion():
    stream = io.StringIO()
    emitter = ProgressEmitter(True, stream=stream, min_interval_s=1000)
    with mock.patch('driverepair_desktop.progress_events.time.monotonic', return_value=1000):
        for index in range(3):
            emitter.emit({'phase':'SCANNING', 'offset': index * 512,
                          'read_length':512, 'failed': index == 1})
        emitter.emit({'phase':'DONE', 'status':'completed_with_read_errors'})
    events = _events(stream)
    assert events[-1]['phase'] == 'DONE'
    assert events[-1]['status'] == 'completed_with_read_errors'
    # Flushed reads keep the original scan phase and include every observation.
    scan_events = [event for event in events if event['phase'] == 'SCANNING']
    spans = [item for event in scan_events for item in event.get('observed_read_spans', [])]
    assert spans == [[0,512,False,False],[512,512,True,False],[1024,512,False,False]]
    assert 'observed_read_spans' not in events[-1]


def test_transient_sink_failure_does_not_discard_unsent_observations():
    class Sink(io.StringIO):
        attempts = 0
        def write(self, value):
            self.attempts += 1
            if self.attempts == 1:
                raise OSError('temporary broken pipe')
            return super().write(value)
    stream = Sink()
    emitter = ProgressEmitter(True, stream=stream, min_interval_s=1000)
    with mock.patch('driverepair_desktop.progress_events.time.monotonic', return_value=1000):
        emitter.emit({'phase':'SCANNING','offset':0,'read_length':512}, force=True)
        emitter.emit({'phase':'SCANNING','offset':512,'read_length':512}, force=True)
    assert stream.attempts == 2
    assert _events(stream)[0]['observed_read_spans'] == [[0,1024,False,False]]


def test_failed_checkpoint_is_retried_even_inside_throttle_interval():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)/'scan.json'
        check = ScanCheckpoint(path, source_token='source-test', size=4096,
                               sector=512, minimum_interval=600)
        state = {'position':1024, 'checked':1024, 'readable':1024,
                 'read_count':2, 'failures':0}
        with mock.patch('driverepair_desktop.scan_checkpoint.time.monotonic',
                        return_value=1000):
            with mock.patch('driverepair_desktop.scan_checkpoint.os.replace',
                            side_effect=OSError('simulated storage outage')):
                with pytest.raises(OSError, match='simulated'):
                    check.save(state)
            assert not path.exists()
            check.save(state)  # same clock value -- failed saves must never throttle
        assert load(path,source_token='source-test',size=4096,sector=512)['position']==1024
        assert not list(Path(directory).glob('*.pending-*'))
