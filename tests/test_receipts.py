"""Shared receipt contracts, historical compatibility, and offline trust boundaries."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from qiskit_lab import cli, job_tracking
from qiskit_lab.comparison import ComparisonError, compare_receipts, comparison_metadata
from qiskit_lab.receipts import IMPORTED, ReceiptValidationError, validate_counts, validate_receipt
from qiskit_lab.reports import write_report


@pytest.fixture(autouse=True)
def no_ibm(monkeypatch):
    service = Mock(side_effect=AssertionError("No live IBM access"))
    sampler = Mock(side_effect=AssertionError("No hardware submissions"))
    monkeypatch.setattr(cli, "runtime_service", service)
    monkeypatch.setattr(cli, "SamplerV2", sampler)
    yield
    service.assert_not_called()
    sampler.assert_not_called()


def local(**updates):
    return {"schema_version": 1, "receipt_type": "execution", "hardware": False,
            "status": "DONE", "backend": "local_statevector_simulator",
            "run_id": "synthetic-local", "counts": {"00": 3, "11": 5}, **updates}


def hardware(**updates):
    return {"schema_version": 1, "receipt_type": "job", "hardware": True,
            "status": "SUBMITTED", "backend": "ibm_test", "job_id": "synthetic-job", **updates}


def chsh(**updates):
    data = local(receipt_type="chsh", correlators=[
        {"label": label, "counts": {"00": 8}, "sign_in_chsh": sign}
        for label, sign in zip(("ab", "ab'", "a'b", "a'b'"), (1, -1, 1, 1), strict=True)
    ], **updates)
    data.pop("counts")
    return data


def qaoa(**updates):
    return local(receipt_type="qaoa", node_count=2, qubits=2, edges=[[0, 1]],
                 gamma=0.5, beta=0.3, expected_cut=0.8, exact_cut=1,
                 approximation_ratio=0.8, best_bitstring="11", best_cut=0,
                 optimization_trace=[0.4, 0.8], **updates)


@pytest.mark.parametrize("value", [
    {}, {"counts": {"0": 2}}, {"counts": [{"0": 2}]},
    {"status": "DONE"}, {"hardware": True, "status": "ERROR"},
    {"hardware": True, "status": "CANCELLED", "job_id": "old"},
    {"status": "DONE", "backend": None, "run_id": None, "shots": None, "qubits": None},
    local(), hardware(), chsh(), qaoa(),
    {"schema_version": 1, "receipt_type": "distribution", "counts": {"0": 3}},
])
def test_historical_and_versioned_variants_remain_valid_without_invented_context(value):
    original = copy.deepcopy(value)
    assert validate_receipt(value) is value
    if "correlators" not in value:
        assert value == original
    assert ("schema_version" in value) == ("schema_version" in original)


@pytest.mark.parametrize("version", [None, 0, 2, -1, "1", True, 1.0, {}, []])
@pytest.mark.parametrize("consumer", ["report", "compare", "tracking"])
def test_unknown_versions_never_fall_back_to_legacy_or_create_output(tmp_path, version, consumer):
    data = hardware(status="DONE", counts={"00": 1}, schema_version=version)
    path = tmp_path / "inputs" / "receipt.json"
    cli.save_json(path, data)
    original = path.read_bytes()
    output = tmp_path / "output"
    with pytest.raises((ReceiptValidationError, ComparisonError), match="schema_version"):
        if consumer == "report":
            write_report(data, output)
        elif consumer == "compare":
            compare_receipts(path, path, allow_unverified=True)
        else:
            job_tracking.receipts(path.parent)
    assert not output.exists()
    assert path.read_bytes() == original


@pytest.mark.parametrize("counts", [
    None, {}, [], [None], [{}], {"00": 0}, {"00": -1}, {"00": True},
    {"00": 1.5}, {"00": "1"}, {"0x1": 2}, {"": 2}, {"0 1": 2}, {"00": 1, "1": 1},
])
def test_invalid_counts_fail_consistently_before_any_artifact(tmp_path, counts):
    data = local(counts=counts)
    source = tmp_path / "source.json"
    cli.save_json(source, data)
    for action in (
        lambda: validate_receipt(data),
        lambda: write_report(data, tmp_path / "report"),
        lambda: cli.finish_report(data, tmp_path / "finish", "receipt.json"),
        lambda: compare_receipts(source, source, allow_unverified=True),
    ):
        with pytest.raises((ReceiptValidationError, ComparisonError)):
            action()
    assert not (tmp_path / "report").exists()
    assert not (tmp_path / "finish").exists()


@pytest.mark.parametrize("updates,message", [
    ({"schema_version": 1, "receipt_type": None}, "receipt_type"),
    ({"receipt_type": []}, "receipt_type"),
    ({"status": "UNKNOWN"}, "status"),
    ({"status": []}, "status"),
    ({"hardware": "false"}, "boolean"),
    ({"job_id": "fake"}, "job_id"),
    ({"run_id": ""}, "run_id"),
    ({"backend": None}, "backend"),
    ({"shots": True}, "shots"),
    ({"shots": 0}, "shots"),
    ({"qubits": -1}, "qubits"),
    ({"metrics": []}, "metrics"),
    ({"optimization_trace": []}, "optimization_trace"),
    ({"optimization_trace": [float("nan")]}, "finite"),
    ({"optimization_trace": [True]}, "finite"),
    ({"gamma": float("inf")}, "finite"),
    ({"receipt_type": "job"}, "hardware"),
    ({"receipt_type": "chsh"}, "correlators"),
])
def test_inconsistent_metadata_is_actionable_without_echoing_values(updates, message):
    with pytest.raises(ReceiptValidationError, match=message):
        validate_receipt(local(**updates))


@pytest.mark.parametrize("missing", ["status", "backend", "hardware", "run_id", "counts"])
def test_versioned_local_required_fields_are_not_silently_inferred(missing):
    data = local()
    data.pop(missing)
    with pytest.raises(ReceiptValidationError, match=missing):
        validate_receipt(data)


@pytest.mark.parametrize("status", ["DONE", "ERROR", "CANCELLED"])
@pytest.mark.parametrize("versioned", [False, True])
def test_terminal_hardware_without_counts_is_a_valid_unavailable_result(tmp_path, status, versioned):
    data = hardware(status=status)
    if not versioned:
        data.pop("schema_version")
        data.pop("receipt_type")
    path = write_report(data, tmp_path / status)
    assert "No measurement results" in path.read_text()
    assert "counts" not in data


def test_done_pending_result_download_remains_trackable_but_not_reportable(tmp_path):
    data = hardware(status="DONE", result_error="TimeoutError")
    assert validate_receipt(data) == data
    with pytest.raises(ReceiptValidationError, match="same job ID"):
        write_report(data, tmp_path / "report")
    assert not (tmp_path / "report").exists()


@pytest.mark.parametrize("status", ["SUBMISSION_UNKNOWN", "NOT_SUBMITTED"])
def test_submission_intents_need_no_job_id_and_preserve_public_recovery_metadata(status):
    data = hardware(status=status, run_id="saved-run", submission_outcome="unknown",
                    submission={"id": "f" * 32, "state": "pending", "job_tags": ["project", "unique"]})
    data.pop("job_id")
    assert validate_receipt(data) == data
    data.pop("run_id")
    with pytest.raises(ReceiptValidationError, match="run_id"):
        validate_receipt(data)


def test_known_layout_mismatch_fails_for_report_and_comparison(tmp_path):
    data = local(comparison_metadata=comparison_metadata(cli.example_circuit("bell")), counts={"0": 3})
    with pytest.raises(ReceiptValidationError, match="bit width"):
        write_report(data, tmp_path / "report")
    assert not (tmp_path / "report").exists()


@pytest.mark.parametrize("updates,message", [
    ({"node_count": 3}, "must agree"), ({"qubits": 3}, "must agree"),
    ({"edges": [[0, 2]]}, "edges"), ({"edges": [[0, 0]]}, "edges"),
    ({"edges": [[True, 1]]}, "edges"), ({"edges": None}, "edges"),
    ({"best_bitstring": "0"}, "best_bitstring"), ({"best_bitstring": 1}, "best_bitstring"),
])
def test_qaoa_metadata_matches_the_actual_graph_and_counts(updates, message):
    data = qaoa()
    data.update(updates)
    with pytest.raises(ReceiptValidationError, match=message):
        validate_receipt(data)


def test_versioned_qaoa_requires_optimization_metadata():
    data = qaoa()
    data.pop("optimization_trace")
    with pytest.raises(ReceiptValidationError, match="optimization_trace"):
        validate_receipt(data)


def test_chsh_rows_validate_their_own_source_identity_and_preserve_seeds():
    data = chsh(sampling={"configuration_seeds": [101, 102, 103, 104]})
    for row in data["correlators"]:
        row["comparison_metadata"] = comparison_metadata(cli.example_circuit("bell"))
    validate_receipt(data)
    assert data["chsh_value"] == 2
    assert data["sampling"]["configuration_seeds"] == [101, 102, 103, 104]
    data["correlators"][0]["comparison_metadata"]["schema_version"] = 99
    with pytest.raises(ReceiptValidationError, match="comparison metadata"):
        validate_receipt(data)


def test_chsh_redundant_counts_must_agree_with_labelled_configurations():
    data = chsh()
    data["counts"] = [row["counts"].copy() for row in data["correlators"]]
    validate_receipt(data)
    data["counts"][0]["01"] = 0
    validate_receipt(data)
    data["counts"][0]["00"] = 7
    with pytest.raises(ReceiptValidationError, match="disagree"):
        validate_receipt(data)
    data["counts"] = {"00": 8}
    with pytest.raises(ReceiptValidationError, match="disagree"):
        validate_receipt(data)


def test_measured_qubit_indices_match_known_source_qubits():
    data = local(qubits=1, comparison_metadata=comparison_metadata(cli.example_circuit("bell")))
    with pytest.raises(ReceiptValidationError, match="source qubits"):
        validate_receipt(data)


def test_invalid_chsh_cli_import_creates_no_output_directory(tmp_path, capsys):
    data = chsh()
    data["correlators"][0]["counts"] = {"00": True}
    path = tmp_path / "input.json"
    cli.save_json(path, data)
    original = path.read_bytes()
    output = tmp_path / "output"
    assert cli.main(["report", "--input", str(path), "--output-dir", str(output)]) == 1
    assert "counts" in json.loads(capsys.readouterr().out)["error"]
    assert not output.exists()
    assert path.read_bytes() == original


@pytest.mark.parametrize("data", [local(), hardware(status="DONE", counts={"00": 2}), chsh(), qaoa()])
def test_import_is_never_online_verification_and_preserves_input(tmp_path, capsys, data):
    path = tmp_path / "input.json"
    cli.save_json(path, data)
    original = path.read_bytes()
    assert cli.main(["report", "--input", str(path), "--output-dir", str(tmp_path / "output")]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["report_source"] == IMPORTED
    assert result["schema_version"] == 1
    assert "not verified with IBM" in Path(result["report_path"]).read_text()
    assert path.read_bytes() == original
    # Even a copied import named receipt.json is not enrolled for implicit online polling.
    cli.save_json(tmp_path / "tracking" / "receipt.json", result)
    assert job_tracking.receipts(tmp_path / "tracking") == []


def test_invalid_tracking_is_preserved_reported_and_does_not_block_other_jobs(tmp_path, monkeypatch):
    invalid = hardware(status="DONE", counts={"00": -1})
    valid = hardware(job_id="healthy", status="CANCELLED")
    bad_path = tmp_path / "bad" / "receipt.json"
    cli.save_json(bad_path, invalid)
    original = bad_path.read_bytes()
    cli.save_json(tmp_path / "good" / "receipt.json", valid)
    cli.finish_report(valid, tmp_path / "good", "receipt.json")
    inspect = Mock(side_effect=AssertionError("Cached reports must not query IBM"))
    monkeypatch.setattr(cli, "inspect_job", inspect)
    args = cli.parser().parse_args(["poll-jobs", "--output-dir", str(tmp_path)])
    result = job_tracking.poll_jobs(args)
    assert [event["job_id"] for event in result["notifications"]] == ["healthy"]
    assert result["errors"][0]["error"] == "ReceiptValidationError"
    assert result["errors"][0]["error_category"] == "local_input"
    assert "non-negative" in result["errors"][0]["next_step"]
    assert bad_path.read_bytes() == original
    assert not list(bad_path.parent.glob("*.html"))
    assert job_tracking.find_receipt(tmp_path, "healthy")[1]["job_id"] == "healthy"
    assert job_tracking.find_receipt(tmp_path, "absent") == (None, {})
    with pytest.raises(ReceiptValidationError, match="non-negative"):
        job_tracking.find_receipt(tmp_path, "synthetic-job")
    args.ack = ["healthy"]
    acknowledged = job_tracking.poll_jobs(args)
    assert acknowledged["notifications"] == []
    assert acknowledged["errors"] == result["errors"]
    inspect.assert_not_called()


def test_new_local_producer_emits_versioned_receipt(tmp_path, capsys):
    assert cli.main(["execute", "--example", "bell", "--shots", "8", "--output-dir", str(tmp_path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["schema_version"] == 1
    assert result["receipt_type"] == "execution"
    assert validate_receipt(result) == result


def test_new_job_observation_emits_versioned_receipt_without_fabricating_counts(tmp_path, monkeypatch):
    job = Mock()
    job.job_id.return_value = "synthetic-job"
    job.backend.return_value = SimpleNamespace(name="ibm_test")
    job.status.return_value = "CANCELLED"
    job.creation_date = None
    job.metrics.return_value = {}
    monkeypatch.setattr(cli, "runtime_service", lambda: SimpleNamespace(job=lambda _: job))
    result = cli.inspect_job(cli.parser().parse_args(["job", "synthetic-job", "--output-dir", str(tmp_path)]))
    assert result["schema_version"] == 1
    assert result["receipt_type"] == "job"
    assert "report_source" not in result
    assert "counts" not in result
    job.result.assert_not_called()


def test_validation_is_independent_of_sdk_services_and_handles_non_string_count_keys():
    assert validate_counts({"0": 1}) == 1
    with pytest.raises(ReceiptValidationError, match="binary"):
        validate_counts({1: 2})


@pytest.mark.parametrize("data,message", [
    ({"receipt_type": "job"}, "schema_version"),
    ({"schema_version": 1, "receipt_type": "distribution"}, "counts"),
    (hardware(backend="local_statevector_simulator"), "local simulator"),
    (hardware(receipt_type="execution"), "hardware false"),
    ({"schema_version": 1, "receipt_type": "job", "hardware": True,
      "status": "DONE", "backend": "ibm_test"}, "job_id"),
    (local(correlators=chsh()["correlators"]), "receipt_type chsh"),
])
def test_missing_or_inconsistent_variant_envelopes(data, message):
    with pytest.raises(ReceiptValidationError, match=message):
        validate_receipt(data)


def test_legacy_unknown_context_and_multiple_job_publications_preserve_their_meaning(tmp_path):
    data = {"status": "DONE", "backend": None, "shots": None, "qubits": None, "run_id": None,
            "counts": [{"0": 1}, {"001": 2}]}
    path = write_report(data, tmp_path)
    assert path.read_text().count("data-publication=") == 2
    assert "Execution type unavailable" in path.read_text()
    assert "schema_version" not in data
    assert data["qubits"] is None
    # A backend name can also describe the noise model being simulated; it is not online evidence.
    validate_receipt(local(backend="ibm_test"))
    validate_receipt({"node_count": 2, "counts": {"00": 1}})
    validate_receipt({"node_count": None, "qubits": None})


def test_invalid_local_samples_never_reach_the_png_renderer(tmp_path, monkeypatch, capsys):
    from qiskit_lab import execution_visualization

    monkeypatch.setattr(cli, "counts_from_result", lambda _: [{"00": -1}])
    render = Mock(side_effect=AssertionError("Invalid data must not render"))
    monkeypatch.setattr(execution_visualization, "render_execution_dashboard", render)
    assert cli.main(["execute", "--example", "bell", "--shots", "8", "--output-dir", str(tmp_path)]) == 1
    assert "non-negative" in json.loads(capsys.readouterr().out)["error"]
    assert not list(tmp_path.rglob("*.png"))
    assert not list(tmp_path.rglob("receipt.json"))
    render.assert_not_called()


def test_invalid_qaoa_metadata_never_copies_or_publishes_a_result(tmp_path, monkeypatch):
    from dataclasses import replace

    from qiskit_lab import experiment_engine

    result = experiment_engine.run_maxcut_qaoa("2-node", shots=8)
    try:
        monkeypatch.setattr(experiment_engine, "run_maxcut_qaoa",
                            lambda *args, **kwargs: replace(result, optimization_trace=(float("nan"),)))
        args = cli.parser().parse_args(["qaoa", "--output-dir", str(tmp_path / "output")])
        with pytest.raises(ReceiptValidationError, match="finite"):
            cli.qaoa(args)
        assert not list((tmp_path / "output").rglob("*.png"))
        assert not list((tmp_path / "output").rglob("experiment.json"))
        assert not list((tmp_path / "output").rglob("*.html"))
    finally:
        result.dashboard_path.unlink(missing_ok=True)


def test_new_qaoa_producer_emits_the_experiment_variant(tmp_path, capsys):
    assert cli.main(["qaoa", "--request", "2-node", "--shots", "8", "--output-dir", str(tmp_path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["schema_version"] == 1
    assert result["receipt_type"] == "qaoa"
    assert sum(result["counts"].values()) == 8
    assert validate_receipt(result) == result


@pytest.mark.parametrize("through_cli", [False, True])
def test_hardware_validation_cannot_discard_an_accepted_id(tmp_path, monkeypatch, capsys, through_cli):
    backend = SimpleNamespace(name="ibm_test", num_qubits=2, status=lambda: SimpleNamespace(operational=True))
    monkeypatch.setattr(cli, "runtime_service", lambda: SimpleNamespace(backend=lambda _: backend))
    monkeypatch.setattr(cli, "generate_preset_pass_manager",
                        lambda **kwargs: SimpleNamespace(run=lambda circuit: circuit))
    calls = []

    def sampler(**kwargs):
        def run(circuits, shots):
            intent, = tmp_path.rglob("submission-intent.json")
            assert json.loads(intent.read_text())["status"] == "SUBMISSION_UNKNOWN"
            calls.append(shots)
            return SimpleNamespace(job_id=lambda: "accepted-job")
        return SimpleNamespace(run=run)

    monkeypatch.setattr(cli, "SamplerV2", sampler)
    validate = cli.validate_receipt

    def validate_after_acceptance(data, **kwargs):
        if data.get("status") == "SUBMITTED":
            saved = list(tmp_path.rglob("receipt.json"))
            assert len(saved) == 1
            assert json.loads(saved[0].read_text())["job_id"] == "accepted-job"
            raise ReceiptValidationError("Injected post-response validation failure")
        return validate(data, **kwargs)

    monkeypatch.setattr(cli, "validate_receipt", validate_after_acceptance)
    argv = ["execute", "--example", "bell", "--hardware", "--backend", "ibm_test",
            "--shots", "8", "--output-dir", str(tmp_path)]
    if through_cli:
        assert cli.main(argv) == 1
        response = json.loads(capsys.readouterr().out)
    else:
        with pytest.raises(cli.SubmissionError) as caught:
            cli.execute(cli.parser().parse_args(argv))
        response = caught.value.response
    assert response["job_id"] == "accepted-job"
    assert response["submission_outcome"] == "accepted"
    assert response["error"] == "ReceiptValidationError"
    assert "do not resubmit" in response["next_step"]
    intent, = tmp_path.rglob("submission-intent.json")
    assert json.loads(intent.read_text())["job_id"] == "accepted-job"
    assert calls == [8]
