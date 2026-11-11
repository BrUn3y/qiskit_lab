"""Deterministic read-only polling, receipt boundaries, and notification recovery."""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, PropertyMock

import pytest

from qiskit_lab import cli, job_tracking

NOW = "2026-11-09T06:00:00+00:00"


@pytest.fixture(autouse=True)
def no_real_ibm(monkeypatch):
    service = Mock(side_effect=AssertionError("Tests must not create a real IBM service"))
    sampler = Mock(side_effect=AssertionError("Polling must never submit a job"))
    monkeypatch.setattr(cli, "QiskitRuntimeService", service)
    monkeypatch.setattr(cli, "SamplerV2", sampler)
    monkeypatch.setattr(cli, "now", lambda: NOW)
    yield
    service.assert_not_called()
    sampler.assert_not_called()


def receipt(base, job_id="tracked-job", **updates):
    value = {"hardware": True, "job_id": job_id, "status": "SUBMITTED", "backend": "ibm_test",
             "title": "Bell circuit", "shots": 64, "created_at": "2026-11-08T00:00:00+00:00", **updates}
    path = base / job_id / "receipt.json"
    cli.save_json(path, value)
    return path


def poll_args(base, *extra):
    return cli.parser().parse_args(["poll-jobs", "--output-dir", str(base), *extra])


def sdk_job(monkeypatch, status):
    job = Mock()
    job.job_id.return_value = "tracked-job"
    job.backend.return_value = SimpleNamespace(name="ibm_test")
    job.status.return_value = status
    job.creation_date = datetime(2026, 11, 8, tzinfo=timezone.utc)
    job.metrics.return_value = {}
    publication = SimpleNamespace(join_data=lambda: SimpleNamespace(get_counts=lambda: {"00": 32, "11": 32}))
    job.result.return_value = [publication]
    service = Mock()
    service.job.return_value = job
    monkeypatch.setattr(cli, "runtime_service", lambda: service)
    return job, service


def test_receipts_missing_base_and_unknown_job(tmp_path):
    assert job_tracking.receipts(tmp_path / "absent") == []
    receipt(tmp_path)
    assert job_tracking.find_receipt(tmp_path, "unknown") == (None, {})
    directory, value = job_tracking.find_receipt(tmp_path, "tracked-job")
    assert directory == tmp_path / "tracked-job"
    assert value["job_id"] == "tracked-job"


@pytest.mark.parametrize("text", ["not JSON", "[]", "null", "42", '{}',
                                  '{"hardware": false, "job_id": "local"}', '{"hardware": true}'])
def test_receipts_ignore_malformed_or_untracked_files(tmp_path, text):
    (tmp_path / "receipt.json").write_text(text)
    valid = receipt(tmp_path)
    assert [path for path, _ in job_tracking.receipts(tmp_path)] == [valid]


def test_receipts_ignore_unreadable_files(monkeypatch, tmp_path):
    unreadable = receipt(tmp_path, "unreadable")
    valid = receipt(tmp_path)
    read_text = Path.read_text

    def read(path, *args, **kwargs):
        if path == unreadable:
            raise PermissionError("private filesystem information")
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read)
    assert [path for path, _ in job_tracking.receipts(tmp_path)] == [valid]


def test_receipts_skip_symlinks_outside_the_artifact_directory(tmp_path):
    outside = receipt(tmp_path / "outside")
    base = tmp_path / "artifacts"
    valid = receipt(base)
    (base / "receipt.json").symlink_to(outside)
    (base / "linked-directory").symlink_to(outside.parent, target_is_directory=True)
    assert [path for path, _ in job_tracking.receipts(base)] == [valid]


def test_job_metadata_allowlists_only_scalar_timing_and_usage_fields():
    created = datetime(2026, 11, 8, tzinfo=timezone.utc)
    job = Mock(creation_date=created)
    job.metrics.return_value = {
        "timestamps": {"created": created.isoformat(), "running": {"private": "hidden"},
                       "finished": NOW, "private": "hidden"},
        "usage": {"quantum_seconds": 1.25, "seconds": 2, "private": "hidden"},
        "executions": 1, "options": {"private": "hidden"},
    }
    assert job_tracking.job_metadata(job) == {
        "created_at": created.isoformat(), "completed_at": NOW,
        "metrics": {"timestamps": {"created": created.isoformat(), "finished": NOW},
                    "usage": {"quantum_seconds": 1.25, "seconds": 2}, "executions": 1},
    }


@pytest.mark.parametrize("metrics,expected", [
    (None, {}), ([], {}), ({}, {"metrics": {}}),
    ({"timestamps": [], "usage": None, "executions": "private"}, {"metrics": {}}),
    ({"timestamps": {"finished": ""}}, {"metrics": {"timestamps": {"finished": ""}}}),
])
def test_optional_metadata_ignores_unexpected_sdk_shapes(metrics, expected):
    job = Mock(creation_date=None)
    job.metrics.return_value = metrics
    assert job_tracking.job_metadata(job) == expected


def test_optional_metadata_failures_do_not_hide_results_or_leak_messages():
    job = Mock()
    type(job).creation_date = PropertyMock(side_effect=RuntimeError("private request"))
    job.metrics.side_effect = ConnectionError("private request")
    assert job_tracking.job_metadata(job) == {}


@pytest.mark.parametrize("status", ["DONE", "ERROR", "CANCELLED"])
def test_terminal_poll_is_durable_idempotent_and_acknowledged_offline(monkeypatch, tmp_path, capsys, status):
    job, service = sdk_job(monkeypatch, status)
    path = receipt(tmp_path)
    command = ["poll-jobs", "--precheck", "--output-dir", str(tmp_path)]
    assert cli.main(command) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["checked"] == 1
    assert first["errors"] == []
    event, = first["notifications"]
    assert event["event_id"] == f"tracked-job:{status}"
    assert event["status"] == status
    assert event["report_filename"] == "tracked-job-bell-circuit.html"
    assert Path(event["report_path"]).is_file()
    saved = json.loads(path.read_text())
    if status == "DONE":
        assert saved["counts"] == [{"00": 32, "11": 32}]
        job.result.assert_called_once_with(timeout=30)
    else:
        assert "counts" not in saved
        job.result.assert_not_called()
    assert cli.main(command) == 0
    assert json.loads(capsys.readouterr().out) == {**first, "checked": 0}
    acknowledged = job_tracking.poll_jobs(poll_args(tmp_path, "--ack", "tracked-job"))
    assert acknowledged == {"notifications": [], "errors": []}
    assert cli.main(command) == 1
    assert json.loads(capsys.readouterr().out) == {"checked": 0, "notifications": [], "errors": []}
    queue = json.loads((tmp_path / "job-notifications.json").read_text())
    assert len(queue) == 1
    assert queue[0]["acknowledged_at"] == NOW
    service.job.assert_called_once_with("tracked-job")


@pytest.mark.parametrize("status", ["QUEUED", "RUNNING", "VALIDATING"])
def test_nonterminal_poll_never_waits_for_results_or_notifies(monkeypatch, tmp_path, status):
    job, service = sdk_job(monkeypatch, status)
    path = receipt(tmp_path, poll_error="ConnectionError", poll_error_category="ibm", poll_next_step="old guidance")
    result = job_tracking.poll_jobs(poll_args(tmp_path))
    assert result == {"checked": 1, "notifications": [], "errors": []}
    saved = json.loads(path.read_text())
    assert saved["status"] == status
    assert saved["queried_at"] == NOW
    assert "poll_error" not in saved
    assert "poll_error_category" not in saved
    assert "poll_next_step" not in saved
    assert "report_path" not in saved
    assert not list(tmp_path.rglob("*.html"))
    job.result.assert_not_called()
    service.job.assert_called_once_with("tracked-job")


def test_download_failure_is_redacted_persisted_and_retried_with_a_bounded_timeout(monkeypatch, tmp_path):
    job, service = sdk_job(monkeypatch, "DONE")
    path = receipt(tmp_path)
    result = job.result.return_value
    job.result.side_effect = [TimeoutError("private IBM request"), result]
    first = job_tracking.poll_jobs(poll_args(tmp_path))
    assert first == {"checked": 1, "notifications": [], "errors": []}
    saved = json.loads(path.read_text())
    assert saved["job_id"] == "tracked-job"
    assert saved["result_error"] == "TimeoutError"
    assert saved["result_error_category"] == "ibm"
    assert "same job ID" in saved["next_step"]
    assert "counts" not in saved
    assert "private IBM request" not in path.read_text()
    assert not list(tmp_path.rglob("*.html"))
    second = job_tracking.poll_jobs(poll_args(tmp_path))
    assert second["errors"] == []
    assert len(second["notifications"]) == 1
    saved = json.loads(path.read_text())
    assert "result_error" not in saved
    assert "result_error_category" not in saved
    assert "next_step" not in saved
    assert saved["counts"] == [{"00": 32, "11": 32}]
    assert job.result.call_count == service.job.call_count == 2
    assert all(call.kwargs == {"timeout": 30} for call in job.result.call_args_list)


def test_render_failure_preserves_counts_and_is_retried_before_notification(monkeypatch, tmp_path):
    job, _ = sdk_job(monkeypatch, "DONE")
    path = receipt(tmp_path)
    render = cli.write_report
    monkeypatch.setattr(cli, "write_report", Mock(side_effect=OSError("private path")))
    assert job_tracking.poll_jobs(poll_args(tmp_path))["notifications"] == []
    saved = json.loads(path.read_text())
    assert saved["report_error"] == "OSError"
    assert saved["report_error_category"] == "filesystem"
    assert "permissions" in saved["report_next_step"]
    assert saved["counts"] == [{"00": 32, "11": 32}]
    assert "private path" not in path.read_text()
    monkeypatch.setattr(cli, "write_report", render)
    result = job_tracking.poll_jobs(poll_args(tmp_path))
    assert result["errors"] == []
    assert len(result["notifications"]) == 1
    assert "report_error" not in json.loads(path.read_text())
    assert job.result.call_count == 2


def test_failed_query_is_redacted_rotated_and_does_not_block_a_healthy_job(monkeypatch, tmp_path):
    job, service = sdk_job(monkeypatch, "DONE")
    failed = receipt(tmp_path, "failed-job")
    receipt(tmp_path)

    def lookup(job_id):
        if job_id == "failed-job":
            raise ConnectionError("private IBM request")
        return job

    service.job.side_effect = lookup
    result = job_tracking.poll_jobs(poll_args(tmp_path))
    assert result["checked"] == 2
    error, = result["errors"]
    assert error["job_id"] == "failed-job"
    assert error["error"] == "ConnectionError"
    assert error["error_category"] == "ibm"
    assert "network access" in error["next_step"]
    assert [entry["job_id"] for entry in result["notifications"]] == ["tracked-job"]
    saved = json.loads(failed.read_text())
    assert saved["queried_at"] == NOW
    assert saved["poll_error"] == "ConnectionError"
    assert "private IBM request" not in str(result) + failed.read_text()


def test_poll_limit_rotates_successful_nonterminal_queries_without_starvation(monkeypatch, tmp_path):
    seen = []

    def inspect(args):
        assert args.wait == 0
        assert args.output is None
        assert args.output_dir == tmp_path
        seen.append(args.job_id)
        path = tmp_path / args.job_id / "receipt.json"
        saved = json.loads(path.read_text())
        saved.update(status="RUNNING", queried_at=NOW)
        cli.save_json(path, saved)
        return saved

    monkeypatch.setattr(cli, "inspect_job", inspect)
    for index in range(12):
        receipt(tmp_path, f"job-{index:02d}")
    first = job_tracking.poll_jobs(poll_args(tmp_path))
    assert first == {"checked": 10, "notifications": [], "errors": []}
    assert seen == [f"job-{index:02d}" for index in range(10)]
    seen.clear()
    assert job_tracking.poll_jobs(poll_args(tmp_path))["checked"] == 10
    assert seen[:2] == ["job-10", "job-11"]
    assert len(set(seen)) == 10


def test_ack_recovers_a_manually_delivered_terminal_report_without_querying_ibm(tmp_path):
    path = receipt(tmp_path, status="CANCELLED")
    saved = json.loads(path.read_text())
    cli.finish_report(saved, path.parent, "receipt.json")
    for _ in range(2):
        assert job_tracking.poll_jobs(poll_args(tmp_path, "--ack", "tracked-job")) == {
            "notifications": [], "errors": [],
        }
    queue = json.loads((tmp_path / "job-notifications.json").read_text())
    entry, = queue
    assert entry == {"event_id": "tracked-job:CANCELLED", "job_id": "tracked-job", "status": "CANCELLED",
                     "report_path": saved["report_path"], "created_at": NOW, "acknowledged_at": NOW}
    assert job_tracking.poll_jobs(poll_args(tmp_path))["notifications"] == []


def test_ack_does_not_acknowledge_other_or_unfinished_jobs(tmp_path):
    receipt(tmp_path, "running", report_path="not-a-terminal-report.html")
    receipt(tmp_path, "missing-report", status="DONE")
    other = {"event_id": "other:DONE", "job_id": "other", "status": "DONE", "report_path": "other.html"}
    cli.save_json(tmp_path / "job-notifications.json", [other])
    result = job_tracking.poll_jobs(poll_args(tmp_path, "--ack", "running", "--ack", "missing-report", "--ack", "unknown"))
    assert result == {"notifications": [other], "errors": []}
    assert json.loads((tmp_path / "job-notifications.json").read_text()) == [other]


def test_corrupt_queue_fails_safely_without_querying_ibm(tmp_path, capsys):
    receipt(tmp_path)
    queue = tmp_path / "job-notifications.json"
    queue.write_text('{"private invalid queue')
    assert cli.main(["poll-jobs", "--output-dir", str(tmp_path)]) == 1
    response = json.loads(capsys.readouterr().out)
    assert response["error"] == "JSONDecodeError"
    assert "private invalid queue" not in str(response)
    assert queue.read_text() == '{"private invalid queue'


def test_poll_waits_for_another_process_to_release_the_queue_lock(tmp_path):
    import fcntl

    script = """
import json
import sys
from qiskit_lab import cli, job_tracking

def no_ibm():
    raise AssertionError("An empty queue must not contact IBM")

cli.runtime_service = no_ibm
args = cli.parser().parse_args(["poll-jobs", "--output-dir", sys.argv[1]])
print("ready", flush=True)
print(json.dumps(job_tracking.poll_jobs(args)), flush=True)
"""
    with (tmp_path / ".job-poll.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        process = subprocess.Popen([sys.executable, "-c", script, str(tmp_path)],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            assert process.stdout.readline().strip() == "ready"
            with pytest.raises(subprocess.TimeoutExpired):
                process.communicate(timeout=0.2)
            assert not (tmp_path / "job-notifications.json").exists()
            fcntl.flock(lock, fcntl.LOCK_UN)
            output, error = process.communicate(timeout=15)
            assert process.returncode == 0, error
            assert json.loads(output) == {"checked": 0, "notifications": [], "errors": []}
            assert json.loads((tmp_path / "job-notifications.json").read_text()) == []
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)
