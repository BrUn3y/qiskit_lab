"""Reproducible sampling with a distinct random stream per configuration."""
from __future__ import annotations

import numpy as np
from qiskit.primitives import StatevectorSampler


def sample_configurations(circuits, *, shots=1024, seed=42):
    """Return counts and seed provenance for a complete local experiment.

    Call once with all measurement configurations. Reusing an integer seed in
    separate StatevectorSampler instances can couple identically distributed
    circuits. Spawn a separate deterministic stream for every configuration.
    """
    if type(shots) is not int or not 1 <= shots <= 100000:
        raise ValueError("Shots must be an integer between 1 and 100000.")
    if type(seed) is not int or seed < 0:
        raise ValueError("The simulation seed must be a nonnegative integer.")
    circuits = list(circuits)
    if not circuits or any(circuit.num_qubits > 20 for circuit in circuits):
        raise ValueError("Provide configurations with at most 20 qubits each.")
    if any(not any(item.operation.name == "measure" for item in circuit.data) for circuit in circuits):
        raise ValueError("Every configuration must include measurements.")
    children = np.random.SeedSequence(seed).spawn(len(circuits))
    # Four words retain each spawned stream's 128-bit seed rather than truncating it.
    seeds = [int.from_bytes(child.generate_state(4).astype('<u4').tobytes(), 'little') for child in children]
    counts = [
        StatevectorSampler(seed=child_seed).run([circuit], shots=shots).result()[0].join_data().get_counts()
        for circuit, child_seed in zip(circuits, seeds, strict=True)
    ]
    return counts, {"method": "numpy_seed_sequence_spawn", "root_seed": seed, "configuration_seeds": seeds}
