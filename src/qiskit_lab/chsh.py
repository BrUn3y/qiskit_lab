"""Local Bell-state CHSH configurations with an explicit measurement convention."""
from __future__ import annotations

import math

from qiskit import QuantumCircuit

MEASUREMENT_CONVENTION = (
    "Bell state Phi+ = (|00> + |11>)/sqrt(2). Alice is qubit 0, Bob is qubit 1; "
    "bitstrings are Bob-Alice (c[1]c[0]). Each angle theta is in radians and defines "
    "M(theta) = cos(2 theta) Z + sin(2 theta) X, measured with RY(-2 theta) then Z. "
    "Bit 0 means outcome +1 and bit 1 means -1. Ideal E(a,b) = cos(2(a-b)). "
    "S = E(ab) - E(ab') + E(a'b) + E(a'b')."
)


def build_chsh_configurations(*, alice_a=0.0, alice_a_prime=math.pi / 4,
                             bob_b=math.pi / 8, bob_b_prime=3 * math.pi / 8):
    """Return four measured circuits and their aligned public settings."""
    angles = (alice_a, alice_a_prime, bob_b, bob_b_prime)
    if any(type(angle) not in {int, float} or not math.isfinite(angle)
           or not math.isfinite(2 * angle) for angle in angles):
        raise ValueError("Measurement angles and their doubled rotations must be finite radians.")
    circuits, settings = [], []
    for label, sign, alice, bob in (
        ("ab", 1, alice_a, bob_b), ("ab'", -1, alice_a, bob_b_prime),
        ("a'b", 1, alice_a_prime, bob_b), ("a'b'", 1, alice_a_prime, bob_b_prime),
    ):
        circuit = QuantumCircuit(2, 2, name=label)
        circuit.h(0)
        circuit.cx(0, 1)
        circuit.ry(-2 * alice, 0)
        circuit.ry(-2 * bob, 1)
        circuit.measure([0, 1], [0, 1])
        circuits.append(circuit)
        # The product form also avoids overflowing a-b for large finite angles.
        theory = math.cos(2 * alice) * math.cos(2 * bob) + math.sin(2 * alice) * math.sin(2 * bob)
        settings.append({"label": label, "sign_in_chsh": sign, "alice_angle_rad": alice,
                         "bob_angle_rad": bob, "theory": theory})
    return circuits, settings
