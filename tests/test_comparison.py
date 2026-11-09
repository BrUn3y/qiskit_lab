"""Distribution comparisons must establish compatible circuits and bit order."""
import copy
import json

import pytest
from qiskit import ClassicalRegister, QuantumCircuit, qasm3

from qiskit_lab import cli
from qiskit_lab.comparison import ComparisonError, compare_receipts, comparison_metadata
from qiskit_lab.experiment_engine import _qaoa_circuit


def write_pair(tmp_path, left, right):
    paths = tmp_path / "left.json", tmp_path / "right.json"
    for path, data in zip(paths, (left, right), strict=True):
        path.write_text(json.dumps(data), encoding="utf-8")
    return paths


@pytest.fixture
def receipt():
    return {"counts": {"00": 50, "11": 50},
            "comparison_metadata": comparison_metadata(cli.example_circuit("bell"))}


@pytest.mark.parametrize("circuit", [
    cli.example_circuit("bell"),
    _qaoa_circuit(3, ((0, 1), (1, 2)), .4, .2, measurements=True),
])
def test_identity_survives_saving_and_loading_qasm(circuit):
    metadata = comparison_metadata(circuit)
    rebuilt = qasm3.loads(qasm3.dumps(circuit))
    assert comparison_metadata(rebuilt) == metadata


def test_same_circuit_from_different_qasm_versions_has_the_same_identity():
    circuit = cli.example_circuit("bell")
    assert comparison_metadata(cli.qasm2.loads(cli.qasm2.dumps(circuit))) == comparison_metadata(circuit)


def test_custom_gate_identity_is_stable_across_independent_loads_and_saved_reuse():
    source = ('OPENQASM 3; include "stdgates.inc"; gate custom(theta) a { rx(theta) a; } '
              'qubit[2] q; bit[2] c; custom(0.3) q[0]; custom(0.7) q[1]; c = measure q;')
    circuit = qasm3.loads(source)
    metadata = comparison_metadata(circuit)
    assert comparison_metadata(qasm3.loads(source)) == metadata
    assert comparison_metadata(qasm3.loads(qasm3.dumps(circuit))) == metadata


def test_partial_measurement_uses_classical_width_and_allows_disjoint_samples(tmp_path):
    circuit = cli.example_circuit("deutsch-jozsa", qubits=3)
    metadata = comparison_metadata(circuit)
    left = {"counts": {"00": 10}, "comparison_metadata": metadata}
    right = {"counts": {"01": 20}, "comparison_metadata": metadata}
    result = compare_receipts(*write_pair(tmp_path, left, right))
    assert result["compatibility"]["verified"]
    assert result["compatibility"]["bit_width"] == 2
    assert result["total_variation_distance"] == 1


@pytest.mark.parametrize("allow_unverified", [False, True])
@pytest.mark.parametrize("change,message", [
    ("circuit", "Source circuit identities differ"),
    ("measurement", "Measured qubits or classical bit mapping differ"),
    ("register", "Classical register order or bit mapping differ"),
])
def test_known_incompatibilities_cannot_be_overridden(tmp_path, receipt, change, message, allow_unverified):
    circuit = cli.example_circuit("bell")
    if change == "circuit":
        circuit.x(0)
    elif change == "measurement":
        circuit = circuit.remove_final_measurements(inplace=False)
        circuit.add_register(ClassicalRegister(2, "meas"))
        circuit.measure([0, 1], [1, 0])
    else:
        circuit = QuantumCircuit(2)
        circuit.add_register(ClassicalRegister(2, "other"))
        circuit.h(0)
        circuit.cx(0, 1)
        circuit.measure([0, 1], [0, 1])
    other = {"counts": receipt["counts"], "comparison_metadata": comparison_metadata(circuit)}
    with pytest.raises(ComparisonError, match=message):
        compare_receipts(*write_pair(tmp_path, receipt, other), allow_unverified=allow_unverified)


def test_reordered_classical_registers_are_rejected(tmp_path):
    circuits = []
    for names in [("a", "b"), ("b", "a")]:
        circuit = QuantumCircuit(2)
        registers = {name: ClassicalRegister(1, name) for name in names}
        circuit.add_register(*registers.values())
        circuit.measure(0, registers["a"][0])
        circuit.measure(1, registers["b"][0])
        circuits.append(circuit)
    data = [{"counts": {"00": 10}, "comparison_metadata": comparison_metadata(circuit)} for circuit in circuits]
    with pytest.raises(ComparisonError, match="register order"):
        compare_receipts(*write_pair(tmp_path, *data))


@pytest.mark.parametrize("allow_unverified", [False, True])
def test_different_widths_are_rejected_even_without_metadata(tmp_path, allow_unverified):
    paths = write_pair(tmp_path, {"counts": {"00": 100}}, {"counts": {"000": 100}})
    with pytest.raises(ComparisonError, match="different bit widths"):
        compare_receipts(*paths, allow_unverified=allow_unverified)


@pytest.mark.parametrize("counts,message", [
    ({}, "positive counts"), ({"00": 0}, "positive counts"),
    ({"00": -1}, "non-negative integers"), ({"00": 1.5}, "non-negative integers"),
    ({"00": "1"}, "non-negative integers"), ({"00": True}, "non-negative integers"),
    ({"": 1}, "binary bitstrings"), ({"02": 1}, "binary bitstrings"),
    ({"0 0": 1}, "binary bitstrings"), ({"00": 1, "1": 1}, "same bit width"),
    ([{"00": 1}, {"00": 1}], "one circuit"),
])
def test_invalid_counts_are_rejected_before_arithmetic(tmp_path, receipt, counts, message):
    other = {**receipt, "counts": counts}
    with pytest.raises(ComparisonError, match=message):
        compare_receipts(*write_pair(tmp_path, receipt, other), allow_unverified=True)


@pytest.mark.parametrize("both_missing", [False, True])
def test_missing_metadata_requires_explicit_opt_in_and_returns_warning(tmp_path, receipt, both_missing):
    legacy = {"counts": receipt["counts"]}
    paths = write_pair(tmp_path, legacy if both_missing else receipt, legacy)
    with pytest.raises(ComparisonError, match="--allow-unverified"):
        compare_receipts(*paths)
    result = compare_receipts(*paths, allow_unverified=True)
    assert result["compatibility"] == {"verified": False, "bit_width": 2}
    assert result["warnings"]
    assert result["total_variation_distance"] == 0


@pytest.mark.parametrize("metadata", [None, {}, {"schema_version": 2}, "invalid"])
def test_malformed_metadata_is_not_treated_as_a_legacy_receipt(tmp_path, receipt, metadata):
    other = {**receipt, "comparison_metadata": metadata}
    with pytest.raises(ComparisonError, match="comparison metadata"):
        compare_receipts(*write_pair(tmp_path, receipt, other), allow_unverified=True)


@pytest.mark.parametrize("field,value,message", [
    ("num_clbits", 0, "measurement layout"),
    ("registers", [{"name": "meas", "clbits": [0]}], "bit width"),
    ("registers", [{"name": "meas", "clbits": [0, 2]}], "classical registers"),
    ("measurements", [[0, 2]], "measured-bit mapping"),
])
def test_invalid_layout_is_rejected(tmp_path, receipt, field, value, message):
    other = copy.deepcopy(receipt)
    other["comparison_metadata"][field] = value
    with pytest.raises(ComparisonError, match=message):
        compare_receipts(*write_pair(tmp_path, receipt, other), allow_unverified=True)


@pytest.mark.parametrize("data", [[], None, "invalid"])
def test_input_must_be_a_receipt_object(tmp_path, receipt, data):
    with pytest.raises(ComparisonError, match="JSON receipt object"):
        compare_receipts(*write_pair(tmp_path, receipt, data))


def test_compare_cli_reports_legacy_errors_and_saves_opted_in_output(tmp_path, capsys):
    left, right = write_pair(tmp_path, {"counts": {"00": 5}}, {"counts": {"00": 10}})
    output = tmp_path / "comparison.json"
    args = ["compare", "--left", str(left), "--right", str(right), "--output", str(output)]
    assert cli.main(args) == 1
    assert "--allow-unverified" in json.loads(capsys.readouterr().out)["error"]
    assert not output.exists()
    assert cli.main([*args, "--allow-unverified"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result == json.loads(output.read_text())
    assert not result["compatibility"]["verified"]


def test_invalid_json_has_an_actionable_error_without_file_contents(tmp_path, receipt):
    paths = write_pair(tmp_path, receipt, receipt)
    paths[1].write_text("private-invalid-json")
    with pytest.raises(ComparisonError, match="UTF-8 JSON receipt") as caught:
        compare_receipts(*paths)
    assert "private-invalid-json" not in str(caught.value)
