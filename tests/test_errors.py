"""Observable, offline diagnostic and redaction contracts."""
import importlib.metadata
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from qiskit.providers.fake_provider import GenericBackendV2

from qiskit_lab import cli
from qiskit_lab.errors import NEXT_STEPS, SUBMISSION_WARNING, UserError, error_response, failure_context

PRIVATE = "PRIVATE_TOKEN request_body={api_key:secret} Authorization: Bearer secret"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    service = Mock(side_effect=AssertionError("Unexpected IBM access"))
    monkeypatch.setattr(cli, "runtime_service", service)
    return service


def output(capsys, category, *, error=None):
    captured = capsys.readouterr()
    assert captured.err == ""
    assert PRIVATE not in captured.out
    assert "Traceback" not in captured.out
    result = json.loads(captured.out)
    assert result["error_category"] == category
    assert result["next_step"]
    if category not in {"ibm", "dependency", "internal"}:
        assert "credentials" not in result["next_step"]
    if error:
        assert result["error"] == error
    return result


@pytest.mark.parametrize("exception,category", [
    (ValueError, "local_input"), (UnicodeError, "local_input"),
    (FileNotFoundError, "filesystem"), (PermissionError, "filesystem"), (OSError, "filesystem"),
    (ImportError, "dependency"), (ModuleNotFoundError, "dependency"),
    (importlib.metadata.PackageNotFoundError, "dependency"), (RuntimeError, "internal"),
])
def test_fallback_never_reads_exception_messages(exception, category):
    class PrivateError(exception):
        def __str__(self):
            raise AssertionError("Diagnostics must not stringify untrusted exceptions")

    result = error_response(PrivateError(PRIVATE))
    assert result == {"error": "PrivateError", "error_category": category, "next_step": NEXT_STEPS[category]}


@pytest.mark.parametrize("exception", [ValueError, OSError, ConnectionError, PermissionError])
def test_explicit_ibm_context_takes_precedence_over_builtin_inheritance(exception):
    error = exception(PRIVATE)
    with pytest.raises(exception) as raised, failure_context("ibm"):
        raise error
    assert raised.value is error
    assert error_response(error)["error_category"] == "ibm"


def test_nested_context_preserves_the_more_specific_operation():
    error = RuntimeError(PRIVATE)
    with pytest.raises(RuntimeError), failure_context("local_execution"), failure_context("rendering"):
        raise error
    assert error_response(error)["error_category"] == "rendering"
    assert error_response(UserError("Public guidance", category="unknown"))["error_category"] == "internal"
    assert error_response(UserError("Public guidance", next_step="Correct the input."))["next_step"] == "Correct the input."


@pytest.mark.parametrize("command", [
    ["execute", "--example", "bell", "--shots", PRIVATE],
    ["execute", "--example", PRIVATE], [PRIVATE], ["--unknown", PRIVATE],
])
def test_argument_errors_preserve_exit_two_without_echoing_private_input(command, capsys):
    with pytest.raises(SystemExit) as raised:
        cli.main(command)
    assert raised.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert PRIVATE not in captured.err
    assert "Invalid command options" in captured.err
    assert "--help" in captured.err


def test_missing_qasm_is_filesystem_not_ibm(tmp_path, capsys, offline):
    assert cli.main(["execute", "--qasm", str(tmp_path / "missing.qasm")]) == 1
    output(capsys, "filesystem", error="FileNotFoundError")
    offline.assert_not_called()


@pytest.mark.parametrize("contents", [b"\xff", PRIVATE.encode()])
def test_invalid_qasm_is_local_input(tmp_path, contents, capsys, offline):
    path = tmp_path / "private.qasm"
    path.write_bytes(contents)
    assert cli.main(["execute", "--qasm", str(path), "--hardware"]) == 1
    result = output(capsys, "local_input")
    assert SUBMISSION_WARNING not in result["next_step"]
    offline.assert_not_called()


def test_invalid_qaoa_graph_is_local_input(tmp_path, capsys):
    assert cli.main(["qaoa", "--request", "QAOA on a 9-node graph", "--output-dir", str(tmp_path)]) == 1
    output(capsys, "local_input", error="ValueError")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("command", ["execute", "qaoa"])
def test_output_path_is_not_a_directory(command, tmp_path, capsys):
    blocked = tmp_path / "blocked"
    blocked.write_text(PRIVATE)
    options = ["--example", "bell"] if command == "execute" else ["--request", "2-node graph"]
    assert cli.main([command, *options, "--output-dir", str(blocked)]) == 1
    output(capsys, "filesystem")
    assert blocked.read_text() == PRIVATE


@pytest.mark.parametrize("exception,category", [
    (RuntimeError, "rendering"), (ValueError, "rendering"), (PermissionError, "filesystem"),
    (ModuleNotFoundError, "dependency"),
])
def test_execution_rendering_failures_have_relevant_actions(monkeypatch, tmp_path, capsys, exception, category):
    from qiskit_lab import execution_visualization

    monkeypatch.setattr(execution_visualization, "render_execution_dashboard", Mock(side_effect=exception(PRIVATE)))
    assert cli.main(["execute", "--example", "bell", "--shots", "1", "--output-dir", str(tmp_path)]) == 1
    output(capsys, category, error=exception.__name__)


def test_local_sampler_failure_is_not_ibm(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "StatevectorSampler", Mock(side_effect=RuntimeError(PRIVATE)))
    assert cli.main(["execute", "--example", "bell", "--output-dir", str(tmp_path)]) == 1
    output(capsys, "local_execution")


@pytest.mark.parametrize("exception,category", [(RuntimeError, "rendering"), (ImportError, "dependency")])
def test_qaoa_renderer_is_not_mistaken_for_input(monkeypatch, tmp_path, capsys, exception, category):
    from qiskit_lab import experiment_engine

    monkeypatch.setattr(experiment_engine, "_render_dashboard", Mock(side_effect=exception(PRIVATE)))
    assert cli.main(["qaoa", "--request", "2-node graph", "--output-dir", str(tmp_path)]) == 1
    output(capsys, category)


@pytest.mark.parametrize("command,contents,category", [
    ("report", None, "filesystem"), ("report", PRIVATE, "local_input"),
    ("report", "\ufffd", "local_input"), ("report", "[]", "local_input"),
    ("compare", None, "filesystem"), ("compare", PRIVATE, "local_input"),
])
def test_public_receipt_read_failures(command, contents, category, tmp_path, capsys, offline):
    path = tmp_path / "input.json"
    if contents is not None:
        path.write_text(contents, encoding="utf-8")
    options = ["--input", str(path)] if command == "report" else ["--left", str(path), "--right", str(path)]
    assert cli.main([command, *options]) == 1
    output(capsys, category)
    offline.assert_not_called()


def test_report_writer_value_error_is_not_exposed_as_a_safe_user_message(monkeypatch, tmp_path, capsys):
    path = tmp_path / "input.json"
    path.write_text('{"status":"DONE","hardware":false,"counts":{"0":1}}')
    monkeypatch.setattr(cli, "write_report", Mock(side_effect=ValueError(PRIVATE)))
    assert cli.main(["report", "--input", str(path), "--output-dir", str(tmp_path / "reports")]) == 1
    output(capsys, "rendering", error="ValueError")


def test_invalid_chsh_receipt_has_controlled_local_guidance(tmp_path, capsys):
    path = tmp_path / "input.json"
    path.write_text(json.dumps({"status": "DONE", "correlators": [PRIVATE]}))
    assert cli.main(["report", "--input", str(path), "--output-dir", str(tmp_path / "reports")]) == 1
    output(capsys, "local_input")
    assert not (tmp_path / "reports").exists()


@pytest.mark.parametrize("exception,category", [
    (RuntimeError, "rendering"), (PermissionError, "filesystem"), (ImportError, "dependency"),
])
def test_report_error_is_recoverable_actionable_and_cleared(monkeypatch, tmp_path, exception, category):
    response = {"status": "DONE", "hardware": False, "counts": {"0": 1}}
    writer = cli.write_report
    monkeypatch.setattr(cli, "write_report", Mock(side_effect=exception(PRIVATE)))
    assert cli.finish_report(response, tmp_path, "receipt.json") is response
    assert response["report_error"] == exception.__name__
    assert response["report_error_category"] == category
    assert response["report_next_step"] == NEXT_STEPS[category]
    assert PRIVATE not in (tmp_path / "receipt.json").read_text()
    monkeypatch.setattr(cli, "write_report", writer)
    cli.finish_report(response, tmp_path, "receipt.json")
    assert Path(response["report_path"]).is_file()
    assert not {"report_error", "report_error_category", "report_next_step"} & response.keys()


@pytest.mark.parametrize("command", [["backends"], ["backend", "ibm_test"], ["job", "test-job"]])
@pytest.mark.parametrize("exception", [ConnectionError, ValueError, PermissionError])
def test_ibm_queries_are_contextual_even_for_builtin_exceptions(command, exception, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "runtime_service", Mock(side_effect=exception(PRIVATE)))
    options = [] if command == ["backends"] else ["--output-dir", str(tmp_path)]
    assert cli.main([*command, *options]) == 1
    result = output(capsys, "ibm", error=exception.__name__)
    assert SUBMISSION_WARNING not in result["next_step"]


def hardware(monkeypatch):
    backend = GenericBackendV2(3, seed=42)
    backend.status = lambda: SimpleNamespace(operational=True)
    service = Mock()
    service.backend.return_value = backend
    monkeypatch.setattr(cli, "runtime_service", lambda: service)
    sampler = Mock()
    monkeypatch.setattr(cli, "SamplerV2", Mock(return_value=sampler))
    return sampler


@pytest.mark.parametrize("exception", [ConnectionError, ValueError, PermissionError, ImportError])
def test_ambiguous_submission_warning_survives_all_failure_categories(monkeypatch, tmp_path, capsys, exception):
    sampler = hardware(monkeypatch)
    sampler.run.side_effect = exception(PRIVATE)
    assert cli.main(["execute", "--example", "bell", "--hardware", "--backend", "ibm_test",
                     "--output-dir", str(tmp_path)]) == 1
    result = output(capsys, "dependency" if exception is ImportError else "ibm")
    assert SUBMISSION_WARNING in result["next_step"]
    sampler.run.assert_called_once()


def test_accepted_job_storage_failure_warns_without_resubmission(monkeypatch, tmp_path, capsys):
    sampler = hardware(monkeypatch)
    sampler.run.return_value.job_id.return_value = "accepted-test-job"
    monkeypatch.setattr(cli, "save_json", Mock(side_effect=PermissionError(PRIVATE)))
    assert cli.main(["execute", "--example", "bell", "--hardware", "--backend", "ibm_test",
                     "--output-dir", str(tmp_path)]) == 1
    result = output(capsys, "filesystem")
    assert SUBMISSION_WARNING in result["next_step"]
    sampler.run.assert_called_once()


@pytest.mark.parametrize("operational,qubits,action", [
    (False, 3, "operational"), (True, 1, "enough qubits"),
])
def test_backend_selection_guidance_does_not_suggest_a_submission_occurred(
    monkeypatch, tmp_path, capsys, operational, qubits, action,
):
    service = Mock()
    service.backend.return_value = SimpleNamespace(
        num_qubits=qubits, status=lambda: SimpleNamespace(operational=operational))
    monkeypatch.setattr(cli, "runtime_service", lambda: service)
    sampler = Mock()
    monkeypatch.setattr(cli, "SamplerV2", sampler)
    assert cli.main(["execute", "--example", "bell", "--hardware", "--backend", "ibm_test",
                     "--output-dir", str(tmp_path)]) == 1
    result = output(capsys, "ibm")
    assert action in result["next_step"]
    assert SUBMISSION_WARNING not in result["next_step"]
    sampler.assert_not_called()


@pytest.mark.parametrize("exception,category", [
    (PermissionError, "ibm"), (ValueError, "ibm"), (ImportError, "dependency"),
])
def test_result_download_failure_preserves_id_and_relevant_action(
    monkeypatch, tmp_path, exception, category,
):
    job = Mock()
    job.job_id.return_value = "accepted-test-job"
    job.backend.return_value = SimpleNamespace(name="ibm_test")
    job.status.return_value = "DONE"
    job.result.side_effect = exception(PRIVATE)
    service = Mock()
    service.job.return_value = job
    monkeypatch.setattr(cli, "runtime_service", lambda: service)
    response = cli.inspect_job(cli.parser().parse_args([
        "job", "accepted-test-job", "--output-dir", str(tmp_path)]))
    assert response["job_id"] == "accepted-test-job"
    assert response["result_error_category"] == category
    assert NEXT_STEPS[category] in response["next_step"]
    assert "same job ID" in response["next_step"]
    assert "do not resubmit" in response["next_step"]
    assert PRIVATE not in json.dumps(response)
    assert not list(tmp_path.rglob("*.html"))


@pytest.mark.parametrize("exception,category", [
    (PermissionError, "filesystem"), (ConnectionError, "ibm"), (ImportError, "dependency"),
])
def test_poll_retains_relevant_safe_action_without_acknowledging(
    monkeypatch, tmp_path, capsys, exception, category,
):
    from qiskit_lab import job_tracking

    directory = tmp_path / "run"
    directory.mkdir()
    receipt = directory / "receipt.json"
    receipt.write_text('{"job_id":"accepted-test-job","backend":"ibm_test","hardware":true,"status":"RUNNING"}')
    monkeypatch.setattr(cli, "inspect_job", Mock(side_effect=exception(PRIVATE)))
    args = cli.parser().parse_args(["poll-jobs", "--output-dir", str(tmp_path)])
    response = job_tracking.poll_jobs(args)
    assert response["notifications"] == []
    diagnostic, = response["errors"]
    assert diagnostic["error_category"] == category
    saved = json.loads(receipt.read_text())
    assert saved["poll_error_category"] == category
    assert saved["poll_next_step"] == diagnostic["next_step"]
    assert PRIVATE not in json.dumps(response) + receipt.read_text()
    assert cli.main(["poll-jobs", "--precheck", "--output-dir", str(tmp_path)]) == 1
    assert json.loads(capsys.readouterr().out)["errors"][0]["error_category"] == category


def test_qasm_import_dependency_failure_is_not_relabelled_as_invalid_input(monkeypatch, tmp_path, capsys):
    path = tmp_path / "input.qasm"
    path.write_text("OPENQASM 3.0;")
    monkeypatch.setattr(cli.qasm3, "loads", Mock(side_effect=ImportError(PRIVATE)))
    assert cli.main(["execute", "--qasm", str(path)]) == 1
    output(capsys, "dependency")


def test_successful_import_clears_obsolete_report_diagnostics(tmp_path, capsys):
    path = tmp_path / "input.json"
    original = {"status": "DONE", "hardware": False, "counts": {"0": 1},
                "report_error": "OSError", "report_error_category": "filesystem", "report_next_step": "old"}
    path.write_text(json.dumps(original))
    assert cli.main(["report", "--input", str(path), "--output-dir", str(tmp_path / "reports")]) == 0
    result = json.loads(capsys.readouterr().out)
    assert not {"report_error", "report_error_category", "report_next_step"} & result.keys()
    assert json.loads(path.read_text()) == original


def test_backend_renderer_failure_is_not_ibm(monkeypatch, tmp_path, capsys):
    from qiskit_lab import backend_visualization

    backend = SimpleNamespace(name="ibm_test", num_qubits=3, operation_names=[], coupling_map=None,
                              status=lambda: SimpleNamespace(operational=True, pending_jobs=0, status_msg="active"))
    service = Mock()
    service.backend.return_value = backend
    monkeypatch.setattr(cli, "runtime_service", lambda: service)
    monkeypatch.setattr(backend_visualization, "render_backend_dashboard", Mock(side_effect=RuntimeError(PRIVATE)))
    assert cli.main(["backend", "ibm_test", "--dashboard", "--output-dir", str(tmp_path)]) == 1
    output(capsys, "rendering")
    assert not list(tmp_path.rglob("backend.json"))


@pytest.mark.parametrize("module", ["qiskit", "qiskit_ibm_runtime", "qiskit_lab.comparison"])
def test_missing_startup_dependency_has_safe_json_in_a_fresh_process(module, tmp_path):
    script = """
import builtins
import sys
original = builtins.__import__
def missing(name, *args, **kwargs):
    if name == sys.argv[1]:
        raise ModuleNotFoundError(sys.argv[2])
    return original(name, *args, **kwargs)
builtins.__import__ = missing
from qiskit_lab.cli import main
raise SystemExit(main(["execute", "--example", "bell"]))
"""
    process = subprocess.run([sys.executable, "-c", script, module, PRIVATE], cwd=tmp_path,
                             capture_output=True, text=True, timeout=30)
    assert process.returncode == 1
    assert process.stderr == ""
    assert PRIVATE not in process.stdout
    result = json.loads(process.stdout)
    assert result == {"error": "ModuleNotFoundError", "error_category": "dependency",
                      "next_step": NEXT_STEPS["dependency"]}
