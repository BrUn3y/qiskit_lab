from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from qiskit import QuantumCircuit, qasm3
from qiskit.providers.fake_provider import GenericBackendV2
from qiskit_ibm_runtime.options import SamplerOptions

from qiskit_lab import cli as quantum


@pytest.fixture
def offline(monkeypatch):
    service = Mock(side_effect=AssertionError("Offline paths must not contact IBM"))
    monkeypatch.setattr(quantum, "runtime_service", service)
    return service


@pytest.mark.parametrize("example,expected", [
    ("bell", {"00", "11"}), ("ghz", {"000", "111"}),
    ("grover", {"11"}), ("deutsch-jozsa", {"01"}),
])
def test_algorithms_execute_offline(example, expected, tmp_path, offline):
    args = quantum.parser().parse_args(["execute", "--example", example, "--shots", "256", "--output-dir", str(tmp_path)])
    result = quantum.execute(args)
    assert set(result["counts"]) == expected
    assert sum(result["counts"].values()) == 256
    assert result["hardware"] is False
    assert "job_id" not in result
    assert (Path(result["artifacts"]) / "receipt.json").exists()
    assert Path(result["report_path"]).exists()
    assert not offline.called


@pytest.mark.parametrize("version", [2, 3])
def test_qasm_loading_and_measurements(version, tmp_path, offline):
    circuit = QuantumCircuit(2)
    circuit.x(0)
    text = quantum.qasm2.dumps(circuit) if version == 2 else qasm3.dumps(circuit)
    path = tmp_path / "input.qasm"
    path.write_text(text)
    args = quantum.parser().parse_args(["execute", "--qasm", str(path), "--output-dir", str(tmp_path)])
    assert quantum.execute(args)["counts"] == {"01": 1024}


def test_multiple_measurement_registers_preserve_correlations(tmp_path, offline):
    path = tmp_path / "registers.qasm"
    path.write_text('OPENQASM 2.0; include "qelib1.inc"; qreg q[2]; creg a[1]; creg b[1]; '
                    'h q[0]; cx q[0],q[1]; measure q[0] -> a[0]; measure q[1] -> b[0];')
    args = quantum.parser().parse_args(["execute", "--qasm", str(path), "--output-dir", str(tmp_path)])
    result = quantum.execute(args)
    assert set(result["counts"]) == {"00", "11"}
    assert sum(result["counts"].values()) == 1024


def test_backend_cannot_silently_select_hardware(tmp_path, offline):
    args = quantum.parser().parse_args(["execute", "--example", "bell", "--backend", "ibm_test"])
    with pytest.raises(quantum.UserError, match="requires --hardware"):
        quantum.execute(args)
    assert not offline.called


@pytest.mark.parametrize("shots", ["0", "-1", "100001"])
def test_invalid_shots_rejected(shots):
    with pytest.raises(SystemExit):
        quantum.parser().parse_args(["execute", "--example", "bell", "--shots", shots])


def test_qpu_transpiles_submits_once_and_saves_receipt(monkeypatch, tmp_path):
    backend = GenericBackendV2(3, seed=42)
    backend.status = lambda: SimpleNamespace(operational=True)
    service = Mock()
    service.least_busy.return_value = backend
    monkeypatch.setattr(quantum, "runtime_service", lambda: service)
    job = Mock()
    job.job_id.return_value = "real-accepted-job-id"
    sampler = Mock()
    sampler.run.return_value = job
    constructor = Mock(return_value=sampler)
    monkeypatch.setattr(quantum, "SamplerV2", constructor)
    args = quantum.parser().parse_args(["execute", "--example", "bell", "--hardware", "--output-dir", str(tmp_path)])
    result = quantum.execute(args)
    assert result["job_id"] == "real-accepted-job-id"
    assert result["status"] == "SUBMITTED"
    assert "counts" not in result
    sampler.run.assert_called_once()
    job.result.assert_not_called()
    job.status.assert_not_called()
    service.least_busy.assert_called_once_with(operational=True, simulator=False, min_num_qubits=2)
    options = constructor.call_args.kwargs["options"]
    assert SamplerOptions(**options).max_execution_time == 300
    circuit = sampler.run.call_args.args[0][0]
    assert circuit.layout is not None
    assert (Path(result["artifacts"]) / "receipt.json").exists()


def test_uncertain_submission_is_never_retried(monkeypatch, tmp_path):
    backend = GenericBackendV2(3, seed=42)
    backend.status = lambda: SimpleNamespace(operational=True)
    service = Mock()
    service.backend.return_value = backend
    monkeypatch.setattr(quantum, "runtime_service", lambda: service)
    sampler = Mock()
    sampler.run.side_effect = ConnectionError("response lost after submission")
    monkeypatch.setattr(quantum, "SamplerV2", Mock(return_value=sampler))
    args = quantum.parser().parse_args(["execute", "--example", "bell", "--hardware", "--backend", "ibm_test",
                                        "--output-dir", str(tmp_path)])
    with pytest.raises(ConnectionError):
        quantum.execute(args)
    sampler.run.assert_called_once()


def test_job_timeout_keeps_existing_id(monkeypatch, tmp_path):
    job = Mock()
    job.job_id.return_value = "existing-job"
    job.backend.return_value = SimpleNamespace(name="ibm_test")
    job.status.return_value = "RUNNING"
    job.result.side_effect = TimeoutError("must not show raw SDK messages")
    service = Mock()
    service.job.return_value = job
    monkeypatch.setattr(quantum, "runtime_service", lambda: service)
    response = quantum.inspect_job(quantum.parser().parse_args([
        "job", "existing-job", "--wait", "1", "--output-dir", str(tmp_path)]))
    assert response["job_id"] == "existing-job"
    assert response["result_error"] == "TimeoutError"
    assert "must not show" not in str(response)
    service.job.assert_called_once_with("existing-job")


def test_safe_cli_error_never_prints_sdk_message(monkeypatch, capsys):
    monkeypatch.setattr(quantum, "runtime_service", Mock(side_effect=RuntimeError("fake-sensitive-request-body")))
    assert quantum.main(["backends"]) == 1
    assert "fake-sensitive" not in capsys.readouterr().out


def test_qaoa_reuses_original_engine_offline(tmp_path, offline):
    args = quantum.parser().parse_args(["qaoa", "--request", "QAOA Max-Cut on a 5-node graph", "--shots", "256",
                                        "--output-dir", str(tmp_path)])
    response = quantum.qaoa(args)
    assert response["exact_cut"] == 4
    assert response["approximation_ratio"] > .9
    assert sum(response["counts"].values()) == 256
    assert Path(response["dashboard_path"]).exists()
    assert Path(response["qasm_path"]).exists()
    assert Path(response["report_path"]).exists()
    circuit = qasm3.loads(Path(response["qasm_path"]).read_text())
    assert circuit.num_qubits == 5
    assert not offline.called


def test_qiskit_engine_imports_as_an_installed_package(tmp_path):
    import subprocess
    import sys

    code = "from qiskit_lab.experiment_engine import parse_maxcut_graph; assert parse_maxcut_graph('5 nodes')[0] == 5"
    subprocess.run([sys.executable, "-c", code], cwd=tmp_path, check=True, capture_output=True)


def test_comparison_normalizes_different_shot_totals(tmp_path):
    left, right = tmp_path / "left.json", tmp_path / "right.json"
    quantum.save_json(left, {"counts": {"00": 50, "11": 50}})
    quantum.save_json(right, {"counts": [{"00": 150, "11": 50}]})
    args = quantum.parser().parse_args(["compare", "--left", str(left), "--right", str(right)])
    result = quantum.compare(args)
    assert result["left_shots"] == 100
    assert result["right_shots"] == 200
    assert result["total_variation_distance"] == .25


def test_first_chat_requests_setup_without_reading_credentials(monkeypatch, tmp_path, offline):
    monkeypatch.delenv("QISKIT_IBM_TOKEN", raising=False)
    monkeypatch.delenv("QISKIT_IBM_RUNTIME_APIKEY", raising=False)
    monkeypatch.setattr(quantum.Path, "home", lambda: tmp_path)
    response = quantum.onboarding()
    assert response["status"] == "needs_credentials"
    assert response["credential_entry"] == "hidden_terminal_prompt"
    assert response["api_key_env"] == "QISKIT_IBM_TOKEN"
    assert response["api_key_env_alias"] == "QISKIT_IBM_RUNTIME_APIKEY"
    assert response["instance_env"] == "QISKIT_IBM_INSTANCE"
    assert "API key" in response["message"]
    assert "configure-quantum.py" in response["setup_command"]
    assert not response["hardware_ready"]
    offline.assert_not_called()


def test_first_chat_reuses_verified_account_without_requesting_key(monkeypatch, tmp_path):
    monkeypatch.delenv("QISKIT_IBM_TOKEN", raising=False)
    monkeypatch.delenv("QISKIT_IBM_RUNTIME_APIKEY", raising=False)
    monkeypatch.setattr(quantum.Path, "home", lambda: tmp_path)
    account = tmp_path / ".qiskit/qiskit-ibm.json"
    account.parent.mkdir()
    # Deliberately invalid JSON proves the guard does not read the file itself.
    account.write_text("not-readable-as-an-sdk-account")
    backend = SimpleNamespace(name="ibm_test", num_qubits=3,
                              status=lambda: SimpleNamespace(operational=True, pending_jobs=0, status_msg="active"))
    service = Mock()
    service.backends.return_value = [backend]
    monkeypatch.setattr(quantum, "runtime_service", lambda: service)
    response = quantum.onboarding()
    assert response["status"] == "ready"
    assert response["hardware_ready"]
    assert "setup_command" not in response
    service.backends.assert_called_once_with(simulator=False)


def test_first_chat_distinguishes_connection_error_from_missing_account(monkeypatch, tmp_path):
    monkeypatch.delenv("QISKIT_IBM_TOKEN", raising=False)
    monkeypatch.delenv("QISKIT_IBM_RUNTIME_APIKEY", raising=False)
    monkeypatch.setattr(quantum.Path, "home", lambda: tmp_path)
    account = tmp_path / ".qiskit/qiskit-ibm.json"
    account.parent.mkdir()
    account.touch()
    monkeypatch.setattr(quantum, "runtime_service", Mock(side_effect=ConnectionError("private-request-body")))
    response = quantum.onboarding()
    assert response["status"] == "connection_error"
    assert response["error"] == "ConnectionError"
    assert "private-request-body" not in str(response)


def test_first_chat_requests_key_when_sdk_created_an_empty_account_file(monkeypatch, tmp_path):
    monkeypatch.delenv("QISKIT_IBM_TOKEN", raising=False)
    monkeypatch.delenv("QISKIT_IBM_RUNTIME_APIKEY", raising=False)
    monkeypatch.setattr(quantum.Path, "home", lambda: tmp_path)
    account = tmp_path / ".qiskit/qiskit-ibm.json"
    account.parent.mkdir()
    account.write_text("{}")
    monkeypatch.setattr(quantum, "runtime_service", Mock(side_effect=quantum.AccountNotFoundError("no account")))
    response = quantum.onboarding()
    assert response["status"] == "needs_credentials"
    assert response["api_key_env"] == "QISKIT_IBM_TOKEN"
