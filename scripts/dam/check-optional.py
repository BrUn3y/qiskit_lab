#!/usr/bin/env python3
"""Small offline native-library checks; run inside the chosen optional environment."""
from __future__ import annotations

import argparse
import importlib.metadata
import json

import numpy as np


def check_sqd():
    from qiskit_addon_sqd.fermion import solve_sci

    # Full (one alpha, one beta) sector of two noninteracting spatial orbitals.
    strings = np.array([1, 2], dtype=np.int64)
    result = solve_sci((strings, strings), np.diag([-1.0, 0.5]), np.zeros((2, 2, 2, 2)), 2, (1, 1))
    np.testing.assert_allclose(result.energy, -2.0, atol=1e-10, rtol=0)
    assert result.sci_state is not None
    np.testing.assert_allclose(result.sci_state.spin_square(), 0.0, atol=1e-10, rtol=0)


def check_fermionic():
    from qiskit_fermions.circuit import FermionicCircuit
    from qiskit_fermions.operators import FermionOperator, ann, cre

    # The canonical anticommutation relation exercises the compiled extension.
    annihilate = FermionOperator.from_terms([([ann(0)], 1.0)])
    create = FermionOperator.from_terms([([cre(0)], 1.0)])
    identity = FermionOperator.from_terms([([], 1.0)])
    assert (annihilate @ create + create @ annihilate).normal_ordered().simplify().equiv(identity)
    assert len(FermionicCircuit(4).modes) == 4


def check_fermionic_sim():
    import ffsim
    from qiskit_fermions.circuit import FermionicCircuit
    from qiskit_fermions.circuit.library import Evolution
    from qiskit_fermions.operators import FermionOperator, ann, cre

    # Block-spin: alpha modes 0,1, beta modes 2,3. No molecular data or hardware.
    hamiltonian = FermionOperator.from_terms([([cre(0), ann(1)], 0.5), ([cre(1), ann(0)], 0.5)])
    circuit = FermionicCircuit(4)
    circuit.append(Evolution(4, hamiltonian, time=1.0), circuit.modes)
    reference = ffsim.hartree_fock_state(2, (1, 1))
    state = ffsim.apply_unitary(reference, circuit, norb=2, nelec=(1, 1))
    np.testing.assert_allclose(np.linalg.norm(state), 1.0, atol=1e-10, rtol=0)
    np.testing.assert_allclose(abs(np.vdot(reference, state)) ** 2, np.cos(0.5) ** 2, atol=1e-10, rtol=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=["sqd", "fermionic", "fermionic-sim"])
    args = parser.parse_args()
    from qiskit_lab.capabilities import PROFILES

    print(json.dumps({"versions": {name: importlib.metadata.version(name) for name in PROFILES[args.profile]}}),
          flush=True)
    if args.profile == "sqd":
        check_sqd()
    else:
        check_fermionic()
        if args.profile == "fermionic-sim":
            check_fermionic_sim()
    print(json.dumps({"profile": args.profile, "offline_native_smoke": "passed", "hardware": False}))


if __name__ == "__main__":
    main()
