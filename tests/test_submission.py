"""Submission crash recovery with exclusively synthetic IBM services."""
import fcntl
import inspect
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from qiskit.providers.fake_provider import GenericBackendV2
from qiskit_ibm_runtime import QiskitRuntimeService
from qiskit_ibm_runtime.options import SamplerOptions

from qiskit_lab import cli, job_tracking, submission


@pytest.fixture(autouse=True)
def no_real_ibm(monkeypatch):
    service = Mock(side_effect=AssertionError("A real IBM service is forbidden"))
    sampler = Mock(side_effect=AssertionError("Recovery must not construct a sampler"))
    monkeypatch.setattr(cli, "QiskitRuntimeService", service)
    monkeypatch.setattr(cli, "runtime_service", service)
    monkeypatch.setattr(cli, "SamplerV2", sampler)
    yield
    service.assert_not_called()
    sampler.assert_not_called()


def saved_intent(base, run_id="test-run"):
    directory = base / run_id
    directory.mkdir(parents=True)
    value = {"run_id": run_id, "hardware": True, "backend": "ibm_test", "shots": 64,
             "title": "Bell circuit", "artifacts": str(directory)}
    submission.prepare_intent(value)
    submission.persist_tracking(directory, value)
    return directory, value


def recovery_args(base, run_id="test-run"):
    return cli.parser().parse_args(["recover-submission", run_id, "--output-dir", str(base)])


def mocked_jobs(monkeypatch, ids):
    jobs = [Mock(job_id=Mock(return_value=identifier)) for identifier in ids]
    service = Mock(spec=["jobs"])
    service.jobs.return_value = jobs
    monkeypatch.setattr(cli, "runtime_service", Mock(return_value=service))
    return service, jobs


def hardware(monkeypatch, base):
    backend = GenericBackendV2(3, seed=42)
    backend.status = lambda: SimpleNamespace(operational=True)
    service = Mock(spec=["backend"])
    service.backend.return_value = backend
    monkeypatch.setattr(cli, "runtime_service", lambda: service)
    job = Mock(job_id=Mock(return_value="accepted-id"))
    sampler = Mock(run=Mock(return_value=job))
    constructor = Mock(return_value=sampler)
    monkeypatch.setattr(cli, "SamplerV2", constructor)
    args = cli.parser().parse_args(["execute", "--example", "bell", "--hardware", "--backend", "ibm_test",
                                   "--shots", "64", "--output-dir", str(base)])
    return args, sampler, constructor, job


def test_intent_and_tags_exist_before_single_submission(monkeypatch, tmp_path):
    args, sampler, constructor, job = hardware(monkeypatch, tmp_path)

    def run(circuits, *, shots):
        directory = next(tmp_path.iterdir())
        saved = json.loads((directory / submission.INTENT_FILE).read_text())
        assert saved == json.loads((directory / "receipt.json").read_text())
        assert saved["backend"] == constructor.call_args.kwargs["mode"].name
        assert saved["shots"] == shots == 64
        assert saved["run_id"] == directory.name
        assert saved["status"] == "SUBMISSION_UNKNOWN"
        assert saved["submission_outcome"] == "unknown"
        assert saved["submission"]["state"] == "pending"
        assert saved["submission"]["intent_at"]
        assert saved["comparison_metadata"]["circuit_sha256"]
        assert saved["versions"]["qiskit-ibm-runtime"]
        assert (directory / "isa-circuit.qasm").is_file()
        tags = saved["submission"]["job_tags"]
        assert tags == SamplerOptions(**constructor.call_args.kwargs["options"]).environment.job_tags
        assert tags == [submission.PROJECT_TAG, submission.RUN_TAG_PREFIX + saved["submission"]["id"]]
        assert len(saved["submission"]["id"]) == 32
        assert len(circuits) == 1
        return job

    sampler.run.side_effect = run
    response = cli.execute(args)
    sampler.run.assert_called_once()
    job.status.assert_not_called()
    job.result.assert_not_called()
    directory = Path(response["artifacts"])
    assert response == json.loads((directory / "receipt.json").read_text())
    assert response == json.loads((directory / submission.INTENT_FILE).read_text())
    assert response["job_id"] == "accepted-id"
    assert response["status"] == "SUBMITTED"
    assert response["submission"]["state"] == "accepted"
    assert response["submission"]["accepted_at"]
    assert "next_step" not in response
    assert job_tracking.find_receipt(tmp_path, "accepted-id")[0] == directory


def test_identical_submissions_have_distinct_run_ids_and_tags(monkeypatch, tmp_path):
    args, sampler, _, _ = hardware(monkeypatch, tmp_path)
    left = cli.execute(args)
    right = cli.execute(args)
    assert left["run_id"] != right["run_id"]
    assert left["submission"]["id"] != right["submission"]["id"]
    assert left["submission"]["job_tags"][1] != right["submission"]["job_tags"][1]
    assert sampler.run.call_count == 2  # Two explicit requests; never an automatic retry.


@pytest.mark.parametrize("existing_name", [submission.INTENT_FILE, "receipt.json", "broken_symlink"])
def test_saved_intent_cannot_be_replayed(tmp_path, existing_name):
    directory, intent = saved_intent(tmp_path)
    for name in (submission.INTENT_FILE, "receipt.json"):
        (directory / name).unlink()
    if existing_name == "broken_symlink":
        (directory / submission.INTENT_FILE).symlink_to(tmp_path / "absent")
    else:
        submission.save_durable(directory / existing_name, intent)
    before = {path: path.read_bytes() for path in directory.glob("*.json") if path.is_file()}
    sampler = Mock()
    with pytest.raises(submission.RecoveryError, match="never replay"):
        submission.submit_once(sampler, object(), intent, directory)
    sampler.run.assert_not_called()
    assert {path: path.read_bytes() for path in directory.glob("*.json") if path.is_file()} == before


@pytest.mark.parametrize("failure", [ConnectionError, TimeoutError, RuntimeError])
def test_lost_response_remains_unknown_and_cli_returns_recovery_context(monkeypatch, tmp_path, capsys, failure):
    _, sampler, _, _ = hardware(monkeypatch, tmp_path)
    sampler.run.side_effect = failure("private SDK request and token")
    assert cli.main(["execute", "--example", "bell", "--hardware", "--backend", "ibm_test",
                     "--output-dir", str(tmp_path)]) == 1
    text = capsys.readouterr().out
    response = json.loads(text)
    sampler.run.assert_called_once()
    assert response["error"] == failure.__name__
    assert response["status"] == "SUBMISSION_UNKNOWN"
    assert response["submission_outcome"] == "unknown"
    assert "recover-submission" in response["next_step"]
    assert "Do not resubmit" in response["next_step"]
    assert "private SDK" not in text
    directory = Path(response["artifacts"])
    saved = json.loads((directory / submission.INTENT_FILE).read_text())
    assert saved["submission"]["error"] == failure.__name__
    assert "job_id" not in saved
    assert job_tracking.receipts(tmp_path) == []


def test_process_interruption_leaves_recoverable_intent(monkeypatch, tmp_path):
    args, sampler, _, _ = hardware(monkeypatch, tmp_path)
    sampler.run.side_effect = KeyboardInterrupt
    with pytest.raises(KeyboardInterrupt):
        cli.execute(args)
    directory = next(tmp_path.iterdir())
    value = json.loads((directory / submission.INTENT_FILE).read_text())
    assert value["submission_outcome"] == "unknown"
    service, _ = mocked_jobs(monkeypatch, ["accepted-before-interruption"])
    response = submission.recover_submission(recovery_args(tmp_path, value["run_id"]))
    assert response["job_id"] == "accepted-before-interruption"
    assert response["recovery_status"] == "recovered"
    sampler.run.assert_called_once()
    service.jobs.assert_called_once()


def test_abrupt_process_exit_can_be_recovered_in_a_new_process_context(monkeypatch, tmp_path):
    script = """
import os, sys
from pathlib import Path
from qiskit_lab import submission
from unittest.mock import Mock
directory = Path(sys.argv[1]) / "crashed-run"
directory.mkdir()
receipt = {"run_id": "crashed-run", "hardware": True, "backend": "ibm_test", "shots": 64}
submission.prepare_intent(receipt)
sampler = Mock()
sampler.run.side_effect = lambda *args, **kwargs: os._exit(17)
submission.submit_once(sampler, object(), receipt, directory)
"""
    process = subprocess.run([sys.executable, "-c", script, str(tmp_path)],
                             capture_output=True, text=True, timeout=15)
    assert process.returncode == 17, process.stderr
    intent = json.loads((tmp_path / "crashed-run" / submission.INTENT_FILE).read_text())
    assert intent["submission_outcome"] == "unknown"
    service, _ = mocked_jobs(monkeypatch, ["accepted-before-crash"])
    response = submission.recover_submission(recovery_args(tmp_path, "crashed-run"))
    assert response["job_id"] == "accepted-before-crash"
    assert job_tracking.find_receipt(tmp_path, "accepted-before-crash")[0] == tmp_path / "crashed-run"
    service.jobs.assert_called_once()


@pytest.mark.parametrize("name", [submission.INTENT_FILE, "receipt.json"])
def test_unwritable_intent_prevents_submission(monkeypatch, tmp_path, name):
    args, sampler, _, _ = hardware(monkeypatch, tmp_path)
    save = submission.save_durable

    def fail(path, value):
        if path.name == name:
            raise OSError("private filesystem path")
        save(path, value)

    monkeypatch.setattr(submission, "save_durable", fail)
    with pytest.raises(submission.SubmissionError) as error:
        cli.execute(args)
    assert error.value.response["submission_outcome"] == "not_attempted"
    assert error.value.response["status"] == "NOT_SUBMITTED"
    assert "private filesystem" not in str(error.value.response)
    sampler.run.assert_not_called()


@pytest.mark.parametrize("name", [submission.INTENT_FILE, "receipt.json"])
def test_accepted_id_survives_a_tracking_file_failure(monkeypatch, tmp_path, name):
    args, sampler, _, _ = hardware(monkeypatch, tmp_path)
    save = submission.save_durable

    def fail(path, value):
        if path.name == name and value.get("job_id"):
            raise OSError("private filesystem path")
        save(path, value)

    monkeypatch.setattr(submission, "save_durable", fail)
    with pytest.raises(submission.SubmissionError) as error:
        cli.execute(args)
    response = error.value.response
    assert response["job_id"] == "accepted-id"
    assert response["submission_outcome"] == "accepted"
    assert "do not resubmit" in response["next_step"]
    directory = Path(response["artifacts"])
    surviving_name = "receipt.json" if name == submission.INTENT_FILE else submission.INTENT_FILE
    assert json.loads((directory / surviving_name).read_text())["job_id"] == "accepted-id"
    sampler.run.assert_called_once()
    monkeypatch.setattr(submission, "save_durable", save)
    service, _ = mocked_jobs(monkeypatch, [])
    recovered = submission.recover_submission(recovery_args(tmp_path, response["run_id"]))
    assert recovered["job_id"] == "accepted-id"
    assert recovered["recovery_status"] == "already_tracked"
    assert job_tracking.find_receipt(tmp_path, "accepted-id")[0] == directory
    service.jobs.assert_not_called()


def test_lost_response_plus_persistence_failure_preserves_original_intent(monkeypatch, tmp_path):
    args, sampler, _, _ = hardware(monkeypatch, tmp_path)
    save = submission.save_durable

    def run(*args, **kwargs):
        monkeypatch.setattr(submission, "save_durable", Mock(side_effect=OSError("private path")))
        raise ConnectionError("private IBM request")

    sampler.run.side_effect = run
    with pytest.raises(submission.SubmissionError) as error:
        cli.execute(args)
    assert error.value.response["error"] == "ConnectionError"
    assert error.value.response["persistence_error"] == "OSError"
    assert error.value.response["submission_outcome"] == "unknown"
    assert "private" not in str(error.value.response)
    assert json.loads(next(tmp_path.rglob(submission.INTENT_FILE)).read_text())["submission"]["state"] == "pending"
    monkeypatch.setattr(submission, "save_durable", save)
    sampler.run.assert_called_once()


@pytest.mark.parametrize("job_id", [None, "", " ", 42])
def test_missing_job_id_is_ambiguous_not_a_failed_submission(monkeypatch, tmp_path, job_id):
    args, sampler, _, job = hardware(monkeypatch, tmp_path)
    job.job_id.return_value = job_id
    with pytest.raises(submission.SubmissionError) as error:
        cli.execute(args)
    assert error.value.response["submission_outcome"] == "unknown"
    assert "job_id" not in error.value.response
    sampler.run.assert_called_once()


def test_job_id_lookup_failure_is_also_recoverable(monkeypatch, tmp_path):
    args, sampler, _, job = hardware(monkeypatch, tmp_path)
    job.job_id.side_effect = ConnectionError("private SDK request")
    with pytest.raises(submission.SubmissionError) as error:
        cli.execute(args)
    assert error.value.response["submission_outcome"] == "unknown"
    sampler.run.assert_called_once()


@pytest.mark.parametrize("ids,expected", [([], "no_match"), (["found-id"], "recovered"),
                                        (["first-id", "second-id"], "ambiguous")])
def test_recovery_handles_zero_one_and_multiple_without_submitting(monkeypatch, tmp_path, ids, expected, capsys):
    directory, intent = saved_intent(tmp_path)
    service, jobs = mocked_jobs(monkeypatch, ids)
    assert cli.main(["recover-submission", "test-run", "--output-dir", str(tmp_path)]) == 0
    response = json.loads(capsys.readouterr().out)
    assert response["recovery_status"] == expected
    assert response["matches"] == ids
    assert response["match_limit"] == 2
    service.jobs.assert_called_once_with(limit=2, backend_name="ibm_test",
                                         job_tags=intent["submission"]["job_tags"])
    # The job-list filter covers every status, not only pending or terminal jobs.
    for job in jobs:
        job.status.assert_not_called()
        job.result.assert_not_called()
        job.cancel.assert_not_called()
        job.update_tags.assert_not_called()
    saved = json.loads((directory / "receipt.json").read_text())
    assert json.loads((directory / "submission-recovery.json").read_text())["matches"] == ids
    if len(ids) == 1:
        assert saved["job_id"] == "found-id"
        assert saved["status"] == "SUBMITTED"
        assert job_tracking.find_receipt(tmp_path, "found-id")[0] == directory
        assert submission.recover_submission(recovery_args(tmp_path))["recovery_status"] == "already_tracked"
        service.jobs.assert_called_once()
    else:
        assert "job_id" not in saved
        assert saved["submission_outcome"] == "unknown"
        assert job_tracking.receipts(tmp_path) == []
        assert "not proof" in response["next_step"] if not ids else "At least two" in response["next_step"]


def test_zero_matches_can_later_recover_a_visible_job(monkeypatch, tmp_path):
    saved_intent(tmp_path)
    service, jobs = mocked_jobs(monkeypatch, ["eventually-visible"])
    service.jobs.side_effect = [[], jobs]
    assert submission.recover_submission(recovery_args(tmp_path))["recovery_status"] == "no_match"
    assert submission.recover_submission(recovery_args(tmp_path))["job_id"] == "eventually-visible"
    assert service.jobs.call_count == 2


def test_recovered_job_flows_into_existing_reports_and_unacknowledged_notifications(monkeypatch, tmp_path):
    directory, _ = saved_intent(tmp_path)
    service = Mock(spec=["jobs", "job"])
    job = Mock(job_id=Mock(return_value="found-id"))
    service.jobs.return_value = [job]
    service.job.return_value = job
    job.backend.return_value = SimpleNamespace(name="ibm_test")
    job.status.return_value = "DONE"
    job.creation_date = None
    job.metrics.return_value = {}
    job.result.return_value = [
        SimpleNamespace(join_data=lambda: SimpleNamespace(get_counts=lambda: {"00": 32, "11": 32}))]
    monkeypatch.setattr(cli, "runtime_service", lambda: service)
    assert submission.recover_submission(recovery_args(tmp_path))["job_id"] == "found-id"
    poll = cli.parser().parse_args(["poll-jobs", "--output-dir", str(tmp_path)])
    result = job_tracking.poll_jobs(poll)
    assert result["errors"] == []
    notification, = result["notifications"]
    assert notification["job_id"] == "found-id"
    assert "acknowledged_at" not in notification
    assert Path(notification["report_path"]).is_file()
    saved = (directory / "receipt.json").read_bytes()
    response = submission.recover_submission(recovery_args(tmp_path))
    assert response["status"] == "DONE"
    assert response["counts"] == [{"00": 32, "11": 32}]
    assert (directory / "receipt.json").read_bytes() == saved
    assert job_tracking.poll_jobs(poll)["notifications"] == result["notifications"]
    service.jobs.assert_called_once()
    service.job.assert_called_once_with("found-id")
    job.result.assert_called_once_with(timeout=30)


@pytest.mark.parametrize("failure", [ConnectionError, TimeoutError])
def test_query_failure_is_not_zero_matches_and_redacts_errors(monkeypatch, tmp_path, capsys, failure):
    directory, _ = saved_intent(tmp_path)
    before = (directory / "receipt.json").read_bytes()
    service, _ = mocked_jobs(monkeypatch, [])
    service.jobs.side_effect = failure("private request body")
    assert cli.main(["recover-submission", "test-run", "--output-dir", str(tmp_path)]) == 1
    text = capsys.readouterr().out
    response = json.loads(text)
    assert response["recovery_status"] == "query_error"
    assert response["submission_outcome"] == "unknown"
    assert response["error"] == failure.__name__
    assert "matches" not in response
    assert "private" not in text
    assert (directory / "receipt.json").read_bytes() == before


def test_recovery_rejects_unusable_job_ids_without_erasing_intent(monkeypatch, tmp_path):
    directory, _ = saved_intent(tmp_path)
    mocked_jobs(monkeypatch, [None])
    with pytest.raises(submission.SubmissionError) as error:
        submission.recover_submission(recovery_args(tmp_path))
    assert error.value.response["recovery_status"] == "query_error"
    assert "job_id" not in json.loads((directory / "receipt.json").read_text())


def test_already_tracked_terminal_receipt_and_notifications_are_unchanged(tmp_path):
    directory, intent = saved_intent(tmp_path)
    submission.accept(intent, "accepted-id")
    submission.persist_tracking(directory, intent)
    intent.update(status="DONE", counts=[{"00": 32, "11": 32}], report_path="existing.html")
    cli.save_json(directory / "receipt.json", intent)
    cli.save_json(tmp_path / "job-notifications.json", [{"job_id": "accepted-id", "acknowledged_at": "delivered"}])
    before = {path: path.read_bytes() for path in tmp_path.rglob("*.json")}
    response = submission.recover_submission(recovery_args(tmp_path))
    assert response["status"] == "DONE"
    assert response["counts"] == [{"00": 32, "11": 32}]
    assert response["recovery_status"] == "already_tracked"
    assert {path: path.read_bytes() for path in tmp_path.rglob("*.json")} == before


def test_recovery_reconstructs_a_missing_receipt_after_interrupted_initial_write(monkeypatch, tmp_path):
    directory, _ = saved_intent(tmp_path)
    (directory / "receipt.json").unlink()
    mocked_jobs(monkeypatch, ["found-id"])
    assert submission.recover_submission(recovery_args(tmp_path))["job_id"] == "found-id"
    assert job_tracking.find_receipt(tmp_path, "found-id")[0] == directory


def test_missing_or_legacy_intent_never_queries_ibm(tmp_path):
    cli.save_json(tmp_path / "legacy" / "receipt.json", {"hardware": True, "run_id": "legacy", "status": "SUBMITTED"})
    with pytest.raises(submission.RecoveryError, match="Legacy"):
        submission.recover_submission(recovery_args(tmp_path, "legacy"))
    with pytest.raises(submission.RecoveryError, match="exactly one"):
        submission.recover_submission(recovery_args(tmp_path / "absent"))


@pytest.mark.parametrize("text", ["not JSON", "[]", "null"])
def test_malformed_intent_is_not_used(tmp_path, text):
    directory, _ = saved_intent(tmp_path)
    (directory / submission.INTENT_FILE).write_text(text)
    with pytest.raises(submission.RecoveryError, match="exactly one"):
        submission.recover_submission(recovery_args(tmp_path))


def test_duplicate_run_ids_are_not_selected_automatically(tmp_path):
    _, intent = saved_intent(tmp_path)
    duplicate = tmp_path / "duplicate"
    duplicate.mkdir()
    submission.save_durable(duplicate / submission.INTENT_FILE, intent)
    with pytest.raises(submission.RecoveryError, match="exactly one"):
        submission.recover_submission(recovery_args(tmp_path))


def test_unrelated_intent_is_not_selected(monkeypatch, tmp_path):
    saved_intent(tmp_path, "unrelated-run")
    saved_intent(tmp_path)
    service, _ = mocked_jobs(monkeypatch, ["matching-id"])
    response = submission.recover_submission(recovery_args(tmp_path))
    assert response["run_id"] == "test-run"
    assert response["job_id"] == "matching-id"
    service.jobs.assert_called_once()


def test_symlink_intents_and_outside_directories_are_ignored(tmp_path):
    directory, _ = saved_intent(tmp_path / "outside")
    base = tmp_path / "base"
    base.mkdir()
    (base / submission.INTENT_FILE).symlink_to(directory / submission.INTENT_FILE)
    (base / "linked").symlink_to(directory, target_is_directory=True)
    with pytest.raises(submission.RecoveryError, match="exactly one"):
        submission.recover_submission(recovery_args(base))


def test_symlink_receipt_is_not_overwritten(tmp_path):
    directory, _ = saved_intent(tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_text("do not change")
    (directory / "receipt.json").unlink()
    (directory / "receipt.json").symlink_to(outside)
    with pytest.raises(submission.RecoveryError, match="symlink"):
        submission.recover_submission(recovery_args(tmp_path))
    assert outside.read_text() == "do not change"


@pytest.mark.parametrize("update", [
    {"hardware": False}, {"backend": None}, {"backend": ""}, {"submission": None},
    {"submission": {"id": "not-an-id"}}, {"submission": {"id": "z" * 32}},
    {"submission": {"id": "a" * 32, "job_tags": [submission.PROJECT_TAG]}},
])
def test_invalid_intent_metadata_fails_before_query(tmp_path, update):
    directory, intent = saved_intent(tmp_path)
    intent.update(update)
    submission.save_durable(directory / submission.INTENT_FILE, intent)
    with pytest.raises(submission.RecoveryError, match="invalid"):
        submission.recover_submission(recovery_args(tmp_path))


@pytest.mark.parametrize("update", [
    {"run_id": "another-run"}, {"backend": "ibm_other"},
])
def test_conflicting_receipt_metadata_is_not_overwritten(tmp_path, update):
    directory, intent = saved_intent(tmp_path)
    intent.update(update)
    cli.save_json(directory / "receipt.json", intent)
    with pytest.raises(submission.RecoveryError, match="disagree"):
        submission.recover_submission(recovery_args(tmp_path))


def test_conflicting_accepted_ids_are_never_replaced(tmp_path):
    directory, intent = saved_intent(tmp_path)
    submission.accept(intent, "first-id")
    submission.persist_tracking(directory, intent)
    intent["job_id"] = "second-id"
    cli.save_json(directory / "receipt.json", intent)
    with pytest.raises(submission.RecoveryError, match="different job IDs"):
        submission.recover_submission(recovery_args(tmp_path))


def test_corrupt_receipt_is_not_overwritten(tmp_path, capsys):
    directory, _ = saved_intent(tmp_path)
    (directory / "receipt.json").write_text("private corrupt JSON")
    assert cli.main(["recover-submission", "test-run", "--output-dir", str(tmp_path)]) == 1
    assert "Restore" in capsys.readouterr().out
    assert (directory / "receipt.json").read_text() == "private corrupt JSON"


@pytest.mark.parametrize("value", [None, [], {"id": "a" * 32}])
def test_invalid_receipt_submission_metadata_is_rejected(tmp_path, value):
    directory, intent = saved_intent(tmp_path)
    intent["submission"] = value
    cli.save_json(directory / "receipt.json", intent)
    with pytest.raises(submission.RecoveryError, match="invalid"):
        submission.recover_submission(recovery_args(tmp_path))


def test_valid_but_different_receipt_tag_is_rejected(tmp_path):
    directory, intent = saved_intent(tmp_path)
    submission.prepare_intent(intent)
    cli.save_json(directory / "receipt.json", intent)
    with pytest.raises(submission.RecoveryError, match="disagree"):
        submission.recover_submission(recovery_args(tmp_path))


def test_invalid_known_job_id_is_not_queried(tmp_path):
    directory, intent = saved_intent(tmp_path)
    intent["job_id"] = 42
    submission.persist_tracking(directory, intent)
    with pytest.raises(submission.RecoveryError, match="job ID is invalid"):
        submission.recover_submission(recovery_args(tmp_path))


def test_recovered_id_remains_visible_when_local_persistence_fails(monkeypatch, tmp_path):
    saved_intent(tmp_path)
    service, _ = mocked_jobs(monkeypatch, ["found-id"])
    monkeypatch.setattr(submission, "save_durable", Mock(side_effect=OSError("private path")))
    with pytest.raises(submission.SubmissionError) as error:
        submission.recover_submission(recovery_args(tmp_path))
    assert error.value.response["job_id"] == "found-id"
    assert error.value.response["submission_outcome"] == "accepted"
    assert "private path" not in str(error.value.response)
    service.jobs.assert_called_once()


@pytest.mark.parametrize("ids", [[], ["found-id"], ["first-id", "second-id"]])
def test_recovery_log_failure_preserves_the_query_outcome(monkeypatch, tmp_path, ids):
    directory, _ = saved_intent(tmp_path)
    mocked_jobs(monkeypatch, ids)
    save = submission.save_durable

    def fail(path, value):
        if path.name == "submission-recovery.json":
            raise OSError("private path")
        save(path, value)

    monkeypatch.setattr(submission, "save_durable", fail)
    with pytest.raises(submission.SubmissionError) as error:
        submission.recover_submission(recovery_args(tmp_path))
    assert error.value.response["matches"] == ids
    assert error.value.response["persistence_error"] == "OSError"
    assert "private path" not in str(error.value.response)
    if len(ids) == 1:
        assert error.value.response["job_id"] == "found-id"
        assert json.loads((directory / "receipt.json").read_text())["job_id"] == "found-id"
    else:
        assert error.value.response["submission_outcome"] == "unknown"


def test_recovery_refuses_an_active_submission(tmp_path):
    directory, _ = saved_intent(tmp_path)
    with submission.submission_lock(directory), pytest.raises(submission.RecoveryError, match="still in use"):
        submission.recover_submission(recovery_args(tmp_path))


def test_recovery_serializes_with_the_notification_poller(tmp_path):
    directory, intent = saved_intent(tmp_path)
    submission.accept(intent, "accepted-id")
    submission.persist_tracking(directory, intent)
    script = """
import json, sys
from qiskit_lab import cli, submission
cli.runtime_service = lambda: (_ for _ in ()).throw(AssertionError("No IBM"))
print("ready", flush=True)
args = cli.parser().parse_args(["recover-submission", "test-run", "--output-dir", sys.argv[1]])
print(json.dumps(submission.recover_submission(args)), flush=True)
"""
    with (tmp_path / ".job-poll.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        process = subprocess.Popen([sys.executable, "-c", script, str(tmp_path)],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            assert process.stdout.readline().strip() == "ready"
            with pytest.raises(subprocess.TimeoutExpired):
                process.communicate(timeout=0.2)
            fcntl.flock(lock, fcntl.LOCK_UN)
            output, error = process.communicate(timeout=15)
            assert process.returncode == 0, error
            assert json.loads(output)["job_id"] == "accepted-id"
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)


def test_durable_writes_sync_file_before_replace_and_directory_after(monkeypatch, tmp_path):
    events = []
    sync = os.fsync
    replace = Path.replace

    def fsync(descriptor):
        events.append("sync")
        sync(descriptor)

    def promote(path, target):
        events.append("replace")
        return replace(path, target)

    monkeypatch.setattr(submission.os, "fsync", fsync)
    monkeypatch.setattr(Path, "replace", promote)
    submission.save_durable(tmp_path / "public.json", {"ok": True})
    assert events == ["sync", "replace", *(["sync"] * (len(tmp_path.resolve().parents) + 1))]
    assert json.loads((tmp_path / "public.json").read_text()) == {"ok": True}
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("failure_at", ["file_sync", "replace", "directory_sync"])
def test_atomic_write_failure_never_truncates_old_tracking_and_cleans_temporary_files(monkeypatch, tmp_path, failure_at):
    path = tmp_path / "public.json"
    submission.save_durable(path, {"old": True})
    sync = os.fsync
    calls = 0

    def fsync(descriptor):
        nonlocal calls
        calls += 1
        if calls == (1 if failure_at == "file_sync" else 2):
            raise OSError("injected sync failure")
        sync(descriptor)

    if failure_at == "replace":
        monkeypatch.setattr(Path, "replace", Mock(side_effect=OSError("injected promotion failure")))
    else:
        monkeypatch.setattr(submission.os, "fsync", fsync)
    with pytest.raises(OSError):
        submission.save_durable(path, {"new": True})
    assert json.loads(path.read_text()) == ({"new": True} if failure_at == "directory_sync" else {"old": True})
    assert not list(tmp_path.glob("*.tmp"))


def test_installed_sdk_supports_the_read_only_filter_and_run_tags():
    parameters = inspect.signature(QiskitRuntimeService.jobs).parameters
    assert {"limit", "backend_name", "job_tags"} <= parameters.keys()
    assert parameters["pending"].default is None
    tags = [submission.PROJECT_TAG, submission.RUN_TAG_PREFIX + "a" * 32]
    assert SamplerOptions(environment={"job_tags": tags}).environment.job_tags == tags
