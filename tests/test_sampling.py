"""Independent seeded sampling for experiments with multiple configurations."""
import pytest
from qiskit import ClassicalRegister, QuantumCircuit

from qiskit_lab.sampling import sample_configurations


def measured_superposition():
    circuit = QuantumCircuit(2)
    circuit.h([0, 1])
    circuit.measure_all()
    return circuit


def test_equal_distributions_use_distinct_reproducible_samples():
    circuit = measured_superposition()
    circuits = [circuit] * 4
    counts, sampling = sample_configurations(circuits, shots=8192, seed=42)
    repeated_counts, repeated_sampling = sample_configurations(circuits, shots=8192, seed=42)
    assert counts == repeated_counts
    assert sampling == repeated_sampling
    assert len(set(sampling['configuration_seeds'])) == 4
    assert len({tuple(sorted(histogram.items())) for histogram in counts}) == 4
    assert all(sum(histogram.values()) == 8192 for histogram in counts)
    assert all(set(histogram) == {'00', '01', '10', '11'} for histogram in counts)
    changed_counts, _ = sample_configurations(circuits, shots=8192, seed=43)
    assert changed_counts != counts


def test_sampling_preserves_joint_register_correlations():
    circuit = QuantumCircuit(2)
    circuit.h(0)
    circuit.cx(0, 1)
    left, right = ClassicalRegister(1, 'left'), ClassicalRegister(1, 'right')
    circuit.add_register(left, right)
    circuit.measure(0, left[0])
    circuit.measure(1, right[0])
    counts, _ = sample_configurations([circuit], shots=256)
    assert set(counts[0]) == {'00', '11'}
    assert sum(counts[0].values()) == 256


@pytest.mark.parametrize('kwargs', [{'shots': 0}, {'shots': True}, {'shots': 1.5}, {'seed': -1}, {'seed': True}])
def test_sampling_rejects_invalid_parameters(kwargs):
    with pytest.raises(ValueError):
        sample_configurations([measured_superposition()], **kwargs)


def test_sampling_rejects_missing_measurements_and_oversized_circuits():
    for circuits in ([], [QuantumCircuit(2)], [QuantumCircuit(21)]):
        with pytest.raises(ValueError):
            sample_configurations(circuits)
