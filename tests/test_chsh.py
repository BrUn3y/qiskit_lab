"""End-to-end local CHSH execution, circuit provenance and independent sampling."""
import base64
import json
import math
import re
from datetime import datetime
from pathlib import Path
from runpy import run_path
from unittest.mock import Mock

import pytest
from qiskit import qasm3
from qiskit.quantum_info import Statevector

from qiskit_lab import cli, sampling
from qiskit_lab.chsh import MEASUREMENT_CONVENTION, build_chsh_configurations

LABELS = ["ab", "ab'", "a'b", "a'b'"]


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    service = Mock(side_effect=AssertionError("Local CHSH must never construct an IBM service"))
    sampler = Mock(side_effect=AssertionError("Local CHSH must never construct an IBM sampler"))
    monkeypatch.setattr(cli, "runtime_service", service)
    monkeypatch.setattr(cli, "SamplerV2", sampler)
    yield
    service.assert_not_called()
    sampler.assert_not_called()


def run_chsh(tmp_path, *options):
    return cli.chsh(cli.parser().parse_args(["chsh", "--output-dir", str(tmp_path), *options]))


@pytest.mark.parametrize("angles", [
    (0, math.pi / 4, math.pi / 8, 3 * math.pi / 8),
    (0, 0, 0, 0), (math.pi / 2, math.pi / 2, 0, 0),
    (-0.23, 0.91, 0.35, -0.78),
])
def test_circuits_measure_the_documented_observables(angles):
    circuits, rows = build_chsh_configurations(**dict(zip(
        ["alice_a", "alice_a_prime", "bob_b", "bob_b_prime"], angles, strict=True)))
    assert [row["label"] for row in rows] == LABELS
    assert [row["sign_in_chsh"] for row in rows] == [1, -1, 1, 1]
    for circuit, row in zip(circuits, rows, strict=True):
        assert circuit.name == row["label"]
        assert circuit.num_qubits == circuit.num_clbits == 2
        assert cli.comparison_metadata(circuit)["measurements"] == [[0, 0], [1, 1]]
        probabilities = Statevector.from_instruction(circuit.remove_final_measurements(inplace=False)).probabilities()
        parity = probabilities[0] + probabilities[3] - probabilities[1] - probabilities[2]
        assert parity == pytest.approx(row["theory"], abs=1e-14)
        assert parity == pytest.approx(math.cos(2 * (row["alice_angle_rad"] - row["bob_angle_rad"])))


@pytest.mark.parametrize("angle", [float("nan"), float("inf"), -float("inf"), 1e308, True, "zero"])
def test_invalid_settings_are_rejected_by_the_builder(angle):
    with pytest.raises(ValueError, match="finite radians"):
        build_chsh_configurations(alice_a=angle)


def test_default_command_samples_once_and_preserves_all_provenance(monkeypatch, tmp_path):
    sample = Mock(wraps=sampling.sample_configurations)
    monkeypatch.setattr(sampling, "sample_configurations", sample)
    result = run_chsh(tmp_path, "--shots", "8192")
    sample.assert_called_once()
    assert sample.call_args.kwargs == {"shots": 8192, "seed": 42}
    circuits = sample.call_args.args[0]
    assert len(circuits) == 4
    assert [row["label"] for row in result["correlators"]] == LABELS
    assert result["hardware"] is False
    assert result["schema_version"] == 1 and result["receipt_type"] == "chsh"
    assert "job_id" not in result and "report_source" not in result
    assert result["backend"] == "local_statevector_simulator"
    assert result["status"] == "DONE"
    assert result["state_preparation"] == "bell_phi_plus"
    assert result["measurement_convention"] == MEASUREMENT_CONVENTION
    assert result["noise_model"] == {"type": "ideal_statevector"}
    assert result["seed"] == result["sampling"]["root_seed"] == 42
    assert result["sampling"]["method"] == "numpy_seed_sequence_spawn"
    seeds = result["sampling"]["configuration_seeds"]
    assert len(seeds) == len(set(seeds)) == 4
    assert result["observed_shots"] == 32768
    assert result["observed_shots_per_configuration"] == [8192] * 4
    assert result["chsh_ideal"] == pytest.approx(2 * math.sqrt(2))
    assert result["chsh_value"] == pytest.approx(result["chsh_ideal"], abs=0.1)
    assert result["chsh_confidence_method"] == "hoeffding"
    assert result["chsh_confidence_level"] == 0.95
    assert result["statistically_supported_violation"] is True
    assert result["versions"].keys() == {"qiskit", "qiskit-ibm-runtime", "numpy"}
    assert datetime.fromisoformat(result["created_at"]) <= datetime.fromisoformat(result["completed_at"])
    assert result["duration_seconds"] >= 0
    for circuit, row, seed in zip(circuits, result["correlators"], seeds, strict=True):
        assert row["configuration_seed"] == seed
        assert sum(row["counts"].values()) == row["shots"] == 8192
        rebuilt = qasm3.loads(row["qasm"])
        assert rebuilt == circuit
        assert Path(row["qasm_path"]).read_text() == row["qasm"]
        assert Path(row["qiskit_path"]).read_text() == row["qiskit_source"]
        assert run_path(row["qiskit_path"])["circuit"] == circuit
        assert row["comparison_metadata"] == cli.comparison_metadata(rebuilt)
        assert row["circuit"] == cli.circuit_info(circuit)
        counts = row["counts"]
        assert row["correlator"] == (
            counts.get("00", 0) + counts.get("11", 0) - counts.get("01", 0) - counts.get("10", 0)) / 8192
    assert len({row["comparison_metadata"]["circuit_sha256"] for row in result["correlators"]}) == 4
    directory = Path(result["artifacts"])
    assert json.loads((directory / "receipt.json").read_text()) == result
    assert not list(tmp_path.rglob("job-notifications.json"))
    html = Path(result["report_path"]).read_text()
    assert f"<h1>{result['title']}</h1>" in html
    assert f"<title>{result['title']} | Qiskit Lab</title>" in html
    assert result["report_filename"] == f"{result['run_id']}-chsh-bell-inequality-experiment.html"
    assert "CHSH measurement correlators" in html
    assert "95% confidence interval for S (Hoeffding)" in html
    assert "under the stated sampling assumptions" in html
    assert html.count("data-publication=") == 4
    assert "Local simulation" in html
    assert "Noise-model prediction S" not in html
    assert "Recorded measurement convention" in html
    assert "cos(2 theta)" in html
    download = re.search(r'href="data:application/json;base64,([^"]+)"', html)
    downloaded = json.loads(base64.b64decode(download[1]))
    assert downloaded == result
    assert downloaded["schema_version"] == 1 and downloaded["receipt_type"] == "chsh"
    for index, row in enumerate(result["correlators"], start=1):
        match = re.search(
            rf'download="configuration-{index}.qasm"\s+href="data:text/plain;base64,([^"]+)"', html)
        assert base64.b64decode(match[1]).decode() == row["qasm"]
        match = re.search(
            rf'download="configuration-{index}.py"\s+href="data:text/plain;base64,([^"]+)"', html)
        assert base64.b64decode(match[1]).decode() == row["qiskit_source"]
    assert "A Qiskit Python script was not recorded" not in html


@pytest.mark.parametrize("seed", ["0", "42", str(2 ** 160)])
def test_same_inputs_reproduce_science_not_run_identifiers(tmp_path, seed):
    options = ("--seed", seed, "--shots", "64", "--alice-a=-0.23", "--alice-a-prime", "0.91",
               "--bob-b", "0.35", "--bob-b-prime=-0.78")
    left, right = run_chsh(tmp_path, *options), run_chsh(tmp_path, *options)
    assert left["run_id"] != right["run_id"]
    assert left["sampling"] == right["sampling"]
    assert left["chsh_value"] == right["chsh_value"]
    for a, b in zip(left["correlators"], right["correlators"], strict=True):
        for field in ("label", "sign_in_chsh", "alice_angle_rad", "bob_angle_rad", "configuration_seed",
                      "qasm", "qiskit_source", "comparison_metadata", "circuit", "counts", "theory",
                      "correlator", "uncertainty"):
            assert a[field] == b[field]


def test_identical_configurations_still_use_independent_streams(tmp_path):
    options = ("--shots", "4096", "--alice-a-prime", "0", "--bob-b", "0", "--bob-b-prime", "0")
    first = run_chsh(tmp_path, *options)
    second = run_chsh(tmp_path, *options, "--seed", "43")
    assert len({row["comparison_metadata"]["circuit_sha256"] for row in first["correlators"]}) == 1
    assert len({row["configuration_seed"] for row in first["correlators"]}) == 4
    assert len({tuple(sorted(row["counts"].items())) for row in first["correlators"]}) == 4
    assert first["sampling"] != second["sampling"]
    assert [row["counts"] for row in first["correlators"]] != [row["counts"] for row in second["correlators"]]


@pytest.mark.parametrize("options", [
    ["--shots", "0"], ["--shots", "100001"], ["--shots", "1.5"],
    ["--seed", "-1"], ["--seed", "1.5"], ["--seed", "text"],
    ["--hardware"], ["--backend", "ibm_test"], ["--noise", "0.1"],
])
def test_parser_rejects_invalid_or_unsupported_options(options, tmp_path):
    with pytest.raises(SystemExit) as error:
        cli.parser().parse_args(["chsh", "--output-dir", str(tmp_path), *options])
    assert error.value.code == 2
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("option", ["--alice-a=nan", "--alice-a-prime=inf", "--bob-b=-inf", "--bob-b-prime=1e308"])
def test_cli_validates_settings_before_sampling_or_artifacts(option, monkeypatch, tmp_path, capsys):
    sample = Mock(side_effect=AssertionError("Invalid settings must not be sampled"))
    monkeypatch.setattr(sampling, "sample_configurations", sample)
    assert cli.main(["chsh", option, "--output-dir", str(tmp_path)]) == 1
    assert "finite radians" in json.loads(capsys.readouterr().out)["error"]
    sample.assert_not_called()
    assert not list(tmp_path.iterdir())


def test_command_dispatch_and_custom_title(tmp_path, capsys):
    assert cli.main(["chsh", "--shots", "1", "--title", "Local CHSH test",
                     "--output-dir", str(tmp_path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["schema_version"] == 1 and result["receipt_type"] == "chsh"
    assert result["observed_shots"] == 4
    assert result["title"] == result["report_title"] == "Local CHSH test"
    assert result["report_filename"].endswith("-local-chsh-test.html")
    assert "<h1>Local CHSH test</h1>" in Path(result["report_path"]).read_text()


def test_native_small_sample_retains_observed_vs_supported_violation(monkeypatch, tmp_path):
    monkeypatch.setattr(sampling, "sample_configurations", lambda circuits, **kwargs: (
        [{"00": 1}, {"01": 1}, {"00": 1}, {"00": 1}],
        {"method": "synthetic_fixture", "root_seed": kwargs["seed"], "configuration_seeds": [1, 2, 3, 4]},
    ))
    result = run_chsh(tmp_path, "--shots", "1")
    assert result["chsh_value"] == 4
    assert result["observed_violation"] is True
    assert result["statistically_supported_violation"] is False
    assert result["chsh_confidence_interval"][0] < 2
    html = Path(result["report_path"]).read_text()
    assert "Observed |S| exceeds 2." in html
    assert "A violation is not statistically supported at this confidence level." in html
    assert "95% confidence interval for S (Hoeffding)" in html
    assert "Recorded measurement convention" in html


def test_science_is_saved_before_native_report_failure(monkeypatch, tmp_path):
    def fail_report(result, directory):
        saved = json.loads((directory / "receipt.json").read_text())
        assert saved == result
        assert saved["observed_shots"] == 128
        assert saved["chsh_value"] == result["chsh_value"]
        raise OSError("private-rendering-error")

    monkeypatch.setattr(cli, "write_report", fail_report)
    result = run_chsh(tmp_path, "--shots", "32")
    assert result["report_error"] == "OSError"
    assert "private-rendering-error" not in str(result)
    assert "report_path" not in result
    assert json.loads((Path(result["artifacts"]) / "receipt.json").read_text()) == result


def test_source_write_failure_prevents_sampling(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "save_qiskit_script", Mock(side_effect=OSError("cannot save source")))
    sample = Mock()
    monkeypatch.setattr(sampling, "sample_configurations", sample)
    with pytest.raises(OSError):
        run_chsh(tmp_path)
    sample.assert_not_called()


def test_receipt_can_be_reported_again_offline(tmp_path, capsys):
    result = run_chsh(tmp_path, "--shots", "64")
    path = Path(result["artifacts"]) / "receipt.json"
    original = path.read_bytes()
    assert cli.main(["report", "--input", str(path), "--output-dir", str(tmp_path / "regenerated")]) == 0
    imported = json.loads(capsys.readouterr().out)
    assert imported["correlators"] == result["correlators"]
    assert imported["sampling"] == result["sampling"]
    assert imported["measurement_convention"] == result["measurement_convention"]
    assert path.read_bytes() == original
    assert "Download configuration-4.qasm" in Path(imported["report_path"]).read_text()


@pytest.mark.parametrize("source", ["", None, 17, '</code><script>alert("unsafe")</script>'])
@pytest.mark.parametrize("key,extension", [("qasm", "qasm"), ("qiskit_source", "py")])
def test_optional_recorded_source_is_text_only_and_never_read_as_a_path(source, key, extension, tmp_path):
    from qiskit_lab.reports import write_report

    _, rows = build_chsh_configurations()
    for row in rows:
        row["counts"] = {"00": 1}
    rows[0][key] = source
    result = {"status": "DONE", "hardware": False, "correlators": rows}
    html = write_report(result, tmp_path).read_text()
    if isinstance(source, str) and source:
        assert source not in html
        assert "&lt;script&gt;" in html
        assert f"Download configuration-1.{extension}" in html
    else:
        assert f"Download configuration-1.{extension}" not in html


def test_upper_shot_limit_and_nonmaximal_settings(tmp_path):
    result = run_chsh(tmp_path, "--shots", "100000", "--alice-a-prime", "0", "--bob-b", "0", "--bob-b-prime", "0")
    assert result["chsh_ideal"] == result["chsh_value"] == 2
    assert result["observed_shots_per_configuration"] == [100000] * 4
    assert result["violated"] is False
