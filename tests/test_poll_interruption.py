"""Real process interruption at notification persistence, using cached reports."""
import json
import signal
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from qiskit_lab import cli, job_tracking


@pytest.mark.parametrize("after_promotion", [False, True])
def test_terminated_poller_recovers_once_without_losing_prior_acknowledgements(
    monkeypatch, tmp_path, after_promotion,
):
    saved = {"hardware": True, "job_id": "cached-job", "backend": "synthetic",
             "status": "DONE", "counts": {"00": 3, "11": 1}}
    directory = tmp_path / "run"
    cli.finish_report(saved, directory, "receipt.json")
    report = Path(saved["report_path"])
    receipt_before, report_before = (directory / "receipt.json").read_bytes(), report.read_bytes()
    delivered = {"event_id": "delivered:DONE", "job_id": "delivered", "status": "DONE",
                 "report_path": "already-delivered.html", "acknowledged_at": "2026-01-02T00:00:00Z"}
    queue = tmp_path / "job-notifications.json"
    cli.save_json(queue, [delivered])
    script = """
import os, signal, sys
from pathlib import Path
from qiskit_lab import cli, job_tracking

def forbidden(*args, **kwargs):
    raise AssertionError("Restart must not query IBM or submit a job")

cli.runtime_service = cli.QiskitRuntimeService = cli.SamplerV2 = forbidden
promote = Path.replace
queue = Path(sys.argv[1]) / "job-notifications.json"
after = sys.argv[2] == "True"
def terminate(source, target):
    if Path(target) == queue:
        if after:
            promote(source, target)
        os.kill(os.getpid(), signal.SIGTERM)
    return promote(source, target)
Path.replace = terminate
job_tracking.poll_jobs(cli.parser().parse_args(["poll-jobs", "--output-dir", sys.argv[1]]))
raise AssertionError("The injected termination boundary was not reached")
"""
    process = subprocess.run([sys.executable, "-c", script, str(tmp_path), str(after_promotion)],
                             capture_output=True, text=True, timeout=30)
    assert process.returncode == -signal.SIGTERM, process.stderr
    assert process.stdout == ""
    persisted = json.loads(queue.read_text())
    assert persisted[0] == delivered
    assert len(persisted) == (2 if after_promotion else 1)
    service = Mock(side_effect=AssertionError("Cached recovery must remain offline"))
    monkeypatch.setattr(cli, "runtime_service", service)
    args = cli.parser().parse_args(["poll-jobs", "--output-dir", str(tmp_path)])
    recovered = job_tracking.poll_jobs(args)
    assert recovered["errors"] == [] and recovered["checked"] == 0
    event, = recovered["notifications"]
    assert event["event_id"] == "cached-job:DONE"
    assert event["report_path"] == str(report)
    assert "acknowledged_at" not in event
    assert job_tracking.poll_jobs(args)["notifications"] == [event]
    assert json.loads(queue.read_text())[0] == delivered
    assert len(json.loads(queue.read_text())) == 2
    assert (directory / "receipt.json").read_bytes() == receipt_before
    assert report.read_bytes() == report_before
    args.ack = ["cached-job"]
    assert job_tracking.poll_jobs(args)["notifications"] == []
    service.assert_not_called()
