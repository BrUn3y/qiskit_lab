"""Regression coverage for imported CHSH hardware and simulation reports."""
import base64
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
    prepare_chsh_report(receipt)
    assert [row["correlator"] for row in receipt["correlators"]] == pytest.approx([0.6, -0.5, 0.4, 0.7])
    assert receipt["chsh_value"] == pytest.approx(2.2)
    assert receipt["chsh_uncertainty"] == pytest.approx(math.sqrt(2.74 / 1000))
    assert receipt["observed_shots"] == 4000
    assert receipt["observed_shots_per_configuration"] == [1000] * 4
    assert receipt["sampling_warnings"] == []
    assert "independent shots within and across configurations" in receipt["chsh_uncertainty_assumption"]


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
