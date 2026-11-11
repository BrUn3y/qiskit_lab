"""Regression coverage for imported CHSH hardware and simulation reports."""
import base64
import copy
import itertools
import json
import math
import re
from pathlib import Path
from unittest.mock import Mock

import pytest

from qiskit_lab import cli
from qiskit_lab.chsh_reporting import prepare_chsh_report
from qiskit_lab.reports import write_report


@pytest.fixture
def receipt():
    # Synthetic data with distinct histograms; no real IBM job data is used.
    pairs = [(400, 100), (125, 375), (350, 150), (425, 75)]
    return {
        "status": "DONE", "hardware": True, "backend": "ibm_test", "job_id": "test-chsh-job",
        "title": "CHSH Bell inequality experiment", "chsh_value": 99, "chsh_uncertainty": 99,
        "chsh_ideal": 2 * math.sqrt(2), "chsh_theory": 2 * math.sqrt(2),
        "noise_model": {"type": "real_hardware_noise", "parameter_p": None},
        "correlators": [
            {"label": label, "sign_in_chsh": sign, "counts": {"00": same, "11": same, "01": other, "10": other},
             "correlator": 99, "uncertainty": 99, "shots": 0,
             "alice_angle_rad": alice, "bob_angle_rad": bob}
            for (label, sign, alice, bob), (same, other) in zip([
                ("ab", 1, 0, math.pi / 8), ("ab'", -1, 0, 3 * math.pi / 8),
                ("a'b", 1, math.pi / 4, math.pi / 8), ("a'b'", 1, math.pi / 4, 3 * math.pi / 8),
            ], pairs, strict=True)
        ],
    }


def test_chsh_statistics_come_from_counts_not_stale_summaries(receipt):
    receipt.update(
        chsh_confidence_interval=[99, 99], chsh_confidence_level=0.1,
        chsh_confidence_method="stale", chsh_confidence_assumption="stale",
        observed_violation=False, statistically_supported_violation=False,
    )
    for row in receipt["correlators"]:
        row.update(confidence_interval=[99, 99], confidence_level=0.1, confidence_method="stale")
    prepare_chsh_report(receipt)
    assert [row["correlator"] for row in receipt["correlators"]] == pytest.approx([0.6, -0.5, 0.4, 0.7])
    assert receipt["chsh_value"] == pytest.approx(2.2)
    assert receipt["chsh_uncertainty"] == pytest.approx(math.sqrt(2.74 / 1000))
    assert receipt["observed_shots"] == 4000
    assert receipt["observed_shots_per_configuration"] == [1000] * 4
    assert receipt["sampling_warnings"] == []
    assert "independent shots within and across configurations" in receipt["chsh_uncertainty_assumption"]
    radius = math.sqrt(2 * math.log(40) * 4 / 1000)
    assert receipt["chsh_confidence_interval"] == pytest.approx([2.2 - radius, 2.2 + radius])
    assert receipt["chsh_confidence_level"] == 0.95
    assert receipt["chsh_confidence_method"] == "hoeffding"
    assert receipt["observed_violation"] is receipt["violated"] is True
    assert receipt["statistically_supported_violation"] is True
    assert receipt["chsh_settings_validation"] == "complete"
    assert "not a loophole-free Bell test" in receipt["chsh_confidence_assumption"]
    for row in receipt["correlators"]:
        assert row["confidence_level"] == 0.95
        assert row["confidence_method"] == "hoeffding"
        radius = math.sqrt(2 * math.log(40) / row["shots"])
        assert row["confidence_interval"] == pytest.approx([row["correlator"] - radius, row["correlator"] + radius])


def test_hardware_report_uses_job_id_observed_shots_and_ideal_reference(receipt, tmp_path):
    path = write_report(receipt, tmp_path)
    html = path.read_text()
    assert path.name == "test-chsh-job-chsh-bell-inequality-experiment.html"
    assert 'IBM Quantum hardware' in html
    assert 'Local simulation' not in html
    assert 'Job <code>test-chsh-job</code>' in html
    assert 'unknown' not in html
    assert 'Observed shots per configuration</p><strong>1,000</strong>' in html
    assert 'Observed shots</p><strong>4,000</strong>' in html
    assert 'S = +2.2000 ± 0.0523' in html
    assert 'Ideal theoretical S' in html
    assert 'Noise-model prediction S' not in html
    assert html.count('data-publication=') == 4
    download = re.search(r'href="data:application/json;base64,([^\"]+)"', html)
    downloaded = json.loads(base64.b64decode(download[1]))
    assert downloaded['chsh_value'] == pytest.approx(2.2)
    assert downloaded['observed_shots'] == 4000
    assert downloaded['statistically_supported_violation'] is True
    assert downloaded['chsh_confidence_interval'] == pytest.approx([2.028212, 2.371788], abs=1e-6)
    assert '95% confidence interval for S (Hoeffding): [+2.0282, +2.3718]' in html
    assert 'Statistically supported |S| > 2 under the stated sampling assumptions' in html
    assert 'not a loophole-free Bell test' in html


def test_unequal_shots_are_not_presented_as_a_single_per_configuration_total(receipt, tmp_path):
    receipt["shots"] = 2000  # Requested shots differ from the returned data.
    receipt["correlators"][0]["counts"] = {"00": 1, "11": 1}
    html = write_report(receipt, tmp_path).read_text()
    assert 'Observed shots per configuration</p><strong>Varies by configuration</strong>' in html
    assert 'Observed shots</p><strong>3,002</strong>' in html
    assert 'Requested shots per circuit</dt><dd>2000</dd>' in html


def test_simulation_noise_reference_and_repeated_histogram_warning(receipt, tmp_path):
    receipt.update(hardware=False, backend='local_statevector_simulator', run_id='test-simulation')
    receipt.pop('job_id')
    receipt['noise_model'] = {'type': 'single_qubit_depolarizing', 'parameter_p': 0.1}
    receipt['correlators'][2]['counts'] = receipt['correlators'][0]['counts'].copy()
    html = write_report(receipt, tmp_path).read_text()
    assert 'Local simulation' in html
    assert 'Run <code>test-simulation</code>' in html
    assert 'Noise-model prediction S' in html
    assert 'identical count histograms' in html
    assert 'counts alone cannot verify independence' in html
    assert 'Violation confirmed' not in html


def test_missing_execution_type_is_not_labelled_as_local_simulation(receipt, tmp_path):
    receipt.pop('hardware')
    receipt.pop('title')
    html = write_report(receipt, tmp_path).read_text()
    assert 'Execution type unavailable' in html
    assert 'Local simulation' not in html
    assert 'Local quantum experiment' not in html


def test_configuration_order_preserves_positional_seed_provenance(receipt):
    receipt['correlators'].reverse()
    labels = [row['label'] for row in receipt['correlators']]
    receipt['sampling'] = {'configuration_seeds': [101, 102, 103, 104]}
    prepare_chsh_report(receipt)
    assert [row['label'] for row in receipt['correlators']] == labels
    assert receipt['sampling']['configuration_seeds'] == [101, 102, 103, 104]
    assert receipt['chsh_value'] == pytest.approx(2.2)


@pytest.mark.parametrize('counts', [
    {}, {'00': 0}, {'00': -1}, {'00': 1.5}, {'00': True}, {'000': 1}, {'xx': 1}, None,
])
def test_invalid_counts_are_rejected_before_writing_a_report(receipt, tmp_path, counts):
    receipt['correlators'][0]['counts'] = counts
    with pytest.raises(ValueError, match='counts|observed shots'):
        write_report(receipt, tmp_path)
    assert not list(tmp_path.glob('*.html'))


@pytest.mark.parametrize('field,value,message', [
    ('label', 'ab\'', 'labelled'), ('sign_in_chsh', 0, 'sign'),
    ('sign_in_chsh', True, 'sign'), ('bob_angle_rad', float('nan'), 'finite'),
])
def test_malformed_settings_are_rejected(receipt, field, value, message):
    receipt['correlators'][0][field] = value
    with pytest.raises(ValueError, match=message):
        prepare_chsh_report(receipt)


def test_even_number_of_negative_signs_is_not_a_chsh_expression(receipt):
    receipt['correlators'][1]['sign_in_chsh'] = 1
    with pytest.raises(ValueError, match='odd number'):
        prepare_chsh_report(receipt)


def test_negative_chsh_violation_uses_absolute_value(receipt):
    for row in receipt['correlators']:
        row['sign_in_chsh'] *= -1
    prepare_chsh_report(receipt)
    assert receipt['chsh_value'] == pytest.approx(-2.2)
    assert receipt['violated'] is True
    assert receipt['observed_violation'] is True
    assert receipt['statistically_supported_violation'] is True
    assert receipt['chsh_confidence_interval'][1] < -2


@pytest.mark.parametrize("parity", [-1, 1])
@pytest.mark.parametrize("shots", [1, 2, 10, 1000])
def test_boundary_correlators_have_nonzero_confidence_width(receipt, parity, shots):
    for row in receipt["correlators"]:
        row["counts"] = {"00" if parity == 1 else "01": shots}
    prepare_chsh_report(receipt)
    for row in receipt["correlators"]:
        lower, upper = row["confidence_interval"]
        assert -1 <= lower < upper <= 1
        assert lower <= parity <= upper
        assert row["uncertainty"] == 0  # Historical standard error, not confidence.
    assert receipt["chsh_confidence_interval"][0] < receipt["chsh_value"]
    assert receipt["chsh_confidence_interval"][1] > receipt["chsh_value"]
    assert receipt["observed_violation"] is False
    assert receipt["statistically_supported_violation"] is False


@pytest.mark.parametrize("direction", [-1, 1])
def test_tiny_sample_observed_violation_is_not_statistical_support(receipt, tmp_path, direction):
    for row in receipt["correlators"]:
        row["counts"] = {"00" if direction * row["sign_in_chsh"] == 1 else "01": 1}
    html = write_report(receipt, tmp_path).read_text()
    assert receipt["chsh_value"] == direction * 4
    assert receipt["violated"] is receipt["observed_violation"] is True
    assert receipt["statistically_supported_violation"] is False
    assert all(row["confidence_interval"] == [-1, 1] for row in receipt["correlators"])
    assert "Observed |S| exceeds 2." in html
    assert "A violation is not statistically supported at this confidence level." in html
    assert "Statistically supported |S| > 2" not in html
    assert "not a loophole-free Bell test" in html


@pytest.mark.parametrize("direction", [-1, 1])
def test_large_boundary_samples_support_both_signs_without_tsirelson_clipping(receipt, direction):
    for row in receipt["correlators"]:
        row["counts"] = {"00" if direction * row["sign_in_chsh"] == 1 else "01": 1000}
    prepare_chsh_report(receipt)
    lower, upper = receipt["chsh_confidence_interval"]
    assert -4 <= lower < upper <= 4
    assert receipt["chsh_value"] == direction * 4
    assert receipt["statistically_supported_violation"] is True
    assert max(abs(lower), abs(upper)) == 4  # Do not impose quantum theory on observations.


def test_unequal_shots_use_all_four_inverse_sample_sizes(receipt):
    for row, shots in zip(receipt["correlators"], [1, 10, 100, 10000], strict=True):
        row["counts"] = {"00": shots}
    prepare_chsh_report(receipt)
    radius = math.sqrt(2 * math.log(40) * (1 + 0.1 + 0.01 + 0.0001))
    assert receipt["chsh_confidence_interval"] == pytest.approx([2 - radius, 4])
    assert receipt["statistically_supported_violation"] is False
    first_interval = receipt["chsh_confidence_interval"]
    receipt["correlators"].reverse()
    prepare_chsh_report(receipt)
    assert receipt["chsh_confidence_interval"] == pytest.approx(first_interval)


@pytest.mark.parametrize("probability", [0, 0.01, 0.1, 0.5, 0.9, 0.99, 1])
@pytest.mark.parametrize("shots", [1, 2, 5, 20])
def test_marginal_intervals_cover_at_least_95_percent_by_exact_enumeration(receipt, shots, probability):
    coverage = 0.0
    for same in range(shots + 1):
        for row in receipt["correlators"]:
            row["counts"] = {"00": same, "01": shots - same}
        prepare_chsh_report(receipt)
        lower, upper = receipt["correlators"][0]["confidence_interval"]
        if lower <= 2 * probability - 1 <= upper:
            coverage += math.comb(shots, same) * probability ** same * (1 - probability) ** (shots - same)
    assert coverage >= 0.95 - 1e-12


@pytest.mark.parametrize("means", [
    [0, 0, 0, 0], [0.5, -0.5, 0.5, 0.5], [-0.5, 0.5, -0.5, -0.5],
    [0.9, -0.9, 0.9, 0.9],
])
def test_s_coverage_and_false_support_by_exact_enumeration(receipt, means):
    # Exhaust all 5,040 count outcomes, weighting by their binomial probabilities.
    # This is deterministic coverage evidence, not a Monte Carlo claim.
    shots = [6, 7, 8, 9]
    probabilities = [(1 + mean) / 2 for mean in means]
    signs = [row["sign_in_chsh"] for row in receipt["correlators"]]
    true_s = sum(sign * mean for sign, mean in zip(signs, means, strict=True))
    coverage, support_probability = 0.0, 0.0
    for outcome in itertools.product(*(range(n + 1) for n in shots)):
        weight = 1.0
        for row, same, n, p in zip(receipt["correlators"], outcome, shots, probabilities, strict=True):
            row["counts"] = {"00": same, "01": n - same}
            weight *= math.comb(n, same) * p ** same * (1 - p) ** (n - same)
        prepare_chsh_report(receipt)
        lower, upper = receipt["chsh_confidence_interval"]
        if lower <= true_s <= upper:
            coverage += weight
        if receipt["statistically_supported_violation"]:
            support_probability += weight
    assert coverage >= 0.95 - 1e-12
    if abs(true_s) <= 2:
        assert support_probability <= 0.05 + 1e-12


@pytest.mark.parametrize("label,key,setting", [
    ("ab'", "alice_angle_rad", "a"), ("a'b'", "alice_angle_rad", "a'"),
    ("a'b", "bob_angle_rad", "b"), ("a'b'", "bob_angle_rad", "b'"),
])
def test_repeated_local_setting_conflicts_fail_before_artifact_creation(receipt, tmp_path, label, key, setting):
    row = next(row for row in receipt["correlators"] if row["label"] == label)
    row[key] += 0.01
    original = copy.deepcopy(receipt)
    with pytest.raises(ValueError, match=f"Inconsistent CHSH measurement setting {re.escape(setting)}:"):
        write_report(receipt, tmp_path / "reports")
    assert receipt == original
    assert not (tmp_path / "reports").exists()


def test_angle_tolerance_is_absolute_and_does_not_infer_periodicity(receipt):
    receipt["correlators"][1]["alice_angle_rad"] = 0.5e-9
    prepare_chsh_report(receipt)
    receipt["correlators"][1]["alice_angle_rad"] = 2e-9
    with pytest.raises(ValueError, match="Inconsistent"):
        prepare_chsh_report(receipt)
    receipt["correlators"][1]["alice_angle_rad"] = 2 * math.pi
    with pytest.raises(ValueError, match="Inconsistent"):
        prepare_chsh_report(receipt)
    receipt["correlators"][0]["alice_angle_rad"] = 1e8
    receipt["correlators"][1]["alice_angle_rad"] = 1e8 + 0.01
    with pytest.raises(ValueError, match="Inconsistent"):
        prepare_chsh_report(receipt)


@pytest.mark.parametrize("mode,status", [("missing", "unavailable"), ("null", "unavailable"), ("partial", "partial")])
def test_optional_angles_remain_compatible_and_are_not_invented(receipt, tmp_path, mode, status):
    for row in receipt["correlators"]:
        for key in ("alice_angle_rad", "bob_angle_rad"):
            if mode == "null":
                row[key] = None
            else:
                row.pop(key)
    if mode == "partial":
        receipt["correlators"][0]["alice_angle_rad"] = 0
    html = write_report(receipt, tmp_path).read_text()
    assert receipt["chsh_settings_validation"] == status
    assert "Not available" in html
    assert receipt["chsh_value"] == pytest.approx(2.2)
    assert all(row.get("bob_angle_rad") is None for row in receipt["correlators"])


def test_partial_angle_metadata_still_rejects_known_conflicts(receipt):
    for row in receipt["correlators"]:
        row.pop("bob_angle_rad")
    receipt["correlators"][1]["alice_angle_rad"] = 0.01
    with pytest.raises(ValueError, match="Inconsistent CHSH measurement setting a:"):
        prepare_chsh_report(receipt)


def test_repeated_preparation_is_idempotent_and_preserves_counts_and_provenance(receipt):
    receipt["sampling"] = {"seed": 42, "configuration_seeds": [101, 102, 103, 104]}
    original = copy.deepcopy(receipt)
    prepare_chsh_report(receipt)
    prepared = copy.deepcopy(receipt)
    prepare_chsh_report(receipt)
    assert receipt == prepared
    assert receipt["sampling"] == original["sampling"]
    for row, old in zip(receipt["correlators"], original["correlators"], strict=True):
        for key in ("label", "counts", "sign_in_chsh", "alice_angle_rad", "bob_angle_rad"):
            assert row[key] == old[key]


@pytest.mark.parametrize("source", [None, [], [{}, {}, {}, {}], [1, 2, 3, 4]])
def test_invalid_configuration_collections_are_rejected(receipt, source):
    receipt["correlators"] = source
    with pytest.raises(ValueError, match="four measurement|labelled"):
        prepare_chsh_report(receipt)


def test_invalid_noise_model_is_rejected(receipt):
    receipt["noise_model"] = "not an object"
    with pytest.raises(ValueError, match="JSON object"):
        prepare_chsh_report(receipt)


def test_report_command_regenerates_offline_and_preserves_the_input(receipt, tmp_path, monkeypatch, capsys):
    service = Mock(side_effect=AssertionError('Report regeneration must not contact IBM'))
    monkeypatch.setattr(cli, 'runtime_service', service)
    path = tmp_path / 'input.json'
    original = json.dumps(receipt)
    path.write_text(original)
    assert cli.main(['report', '--input', str(path), '--output-dir', str(tmp_path / 'reports')]) == 0
    result = json.loads(capsys.readouterr().out)
    html_path = Path(result['report_path'])
    assert html_path.is_file()
    assert result['chsh_value'] == pytest.approx(2.2)
    assert result['chsh_confidence_method'] == 'hoeffding'
    assert result['chsh_confidence_level'] == 0.95
    assert result['statistically_supported_violation'] is True
    assert result['report_source'] == 'imported_receipt_not_verified_online'
    assert json.loads((html_path.parent / 'report.json').read_text()) == result
    assert path.read_text() == original
    service.assert_not_called()


@pytest.mark.parametrize('text,message', [
    ('not json', 'valid public JSON'), ('[]', 'JSON object'),
    ('{"status":"RUNNING"}', 'terminal job state'),
    ('{"status":"DONE","hardware":"false"}', 'boolean'),
])
def test_report_command_rejects_invalid_input(tmp_path, capsys, text, message):
    path = tmp_path / 'invalid.json'
    path.write_text(text)
    assert cli.main(['report', '--input', str(path), '--output-dir', str(tmp_path / 'reports')]) == 1
    assert message in json.loads(capsys.readouterr().out)['error']
    assert not list(tmp_path.rglob('*.html'))
