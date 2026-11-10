"""Method C1 runner: compare mitigation configurations on the real circuit, statevector local mode.

Transpiles the researcher's actual (non-Clifford) circuit for a small fake backend, runs the
client-side Estimator (qiskit-ibm-runtime >= 0.50.0) in local testing mode once per
configuration, and scores each against ``StatevectorEstimator`` on the logical circuit.
See verification.md, Method C1.

Input is a ``RuntimeEncoder`` JSON file of ``(logical_circuit, logical_observable)``, or of
``(logical_circuit, logical_observable, parameter_values)`` with ``parameter_values`` of
shape ``(num_points, num_parameters)``. Without parameter values, ``--points`` random points
are drawn in ``[0, pi)``. Final measurements are removed before running::

    import json
    from qiskit_ibm_runtime import RuntimeEncoder
    with open("/tmp/em/logical.json", "w") as f:
        json.dump((circuit, hamiltonian), f, cls=RuntimeEncoder)

    python verify_c1.py /tmp/em/logical.json --backend FakeNairobiV2 \
        --configs rl0,trex,trex_twirl --precision 0.03 --workers 3

For a parameterized circuit (an optimizer loop), the table also reports Spearman rho
against the ideal values and whether the lowest-value point matches the ideal one; judge
mitigation in a loop by these, not only by MAE (SKILL.md Phase 1).

Configuration names and ``--fractional`` are as in ``verify_c2.py``. The noise comes from the small proxy
backend, so absolute errors don't carry over to the target device.
"""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from verify_c2 import configure_options, fake_backend, load_json, select_configs

MAX_STATEVECTOR_QUBITS = 30


def _load(path: str, num_points: int, seed: int):
    loaded = load_json(path)
    circuit, observable = loaded[0], loaded[1]
    circuit = circuit.remove_final_measurements(inplace=False)
    if circuit.num_parameters == 0:
        return circuit, observable, None
    if len(loaded) > 2 and loaded[2] is not None:
        values = np.asarray(loaded[2], dtype=float)
    else:
        values = np.random.default_rng(seed).uniform(0, np.pi, (num_points, circuit.num_parameters))
    return circuit, observable, values


def run_config(name, path, backend_name, precision, seed, noise_factors, num_points,
               optimization_level, fractional):
    from qiskit.transpiler import generate_preset_pass_manager
    from qiskit_ibm_runtime.executor_estimator import Estimator

    circuit, observable, values = _load(path, num_points, seed)
    backend = fake_backend(backend_name)
    isa = generate_preset_pass_manager(optimization_level=optimization_level, backend=backend,
                                       seed_transpiler=seed).run(circuit)
    pub = (isa, observable.apply_layout(isa.layout)) + ((values,) if values is not None else ())

    estimator = Estimator(mode=backend)
    estimator.options.default_precision = precision
    estimator.options.simulator.seed_simulator = seed
    configure_options(estimator.options, name, noise_factors, fractional)

    start = time.time()
    data = estimator.run([pub]).result()[0].data
    return {"name": name, "runtime_s": time.time() - start,
            "evs": np.atleast_1d(np.asarray(data.evs)).tolist()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("logical", help="RuntimeEncoder JSON of (circuit, observable[, parameter_values])")
    parser.add_argument("--backend", default="FakeNairobiV2", help="small fake backend class name")
    parser.add_argument("--configs", default="rl0,trex,trex_twirl")
    parser.add_argument("--fractional", action="store_true", help="workload uses fractional RZZ gates: twirl with group local_pauli (RX-only needs no flag)")
    parser.add_argument("--noise-factors", default="1,3,5")
    parser.add_argument("--precision", type=float, default=0.03)
    parser.add_argument("--points", type=int, default=12, help="random parameter points")
    parser.add_argument("--optimization-level", type=int, default=3)
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--out", default="c1_results.json")
    args = parser.parse_args()

    names = select_configs(parser, args.configs)
    width = fake_backend(args.backend).num_qubits
    if width > MAX_STATEVECTOR_QUBITS:
        parser.error(f"{args.backend} has {width} qubits; local mode simulates the whole "
                     f"backend, so use one with <= {MAX_STATEVECTOR_QUBITS} (or Method C2)")
    noise_factors = [float(x) for x in args.noise_factors.split(",")]

    from qiskit.primitives import StatevectorEstimator
    from scipy.stats import spearmanr

    circuit, observable, values = _load(args.logical, args.points, args.seed)
    ideal_pub = (circuit, observable) + ((values,) if values is not None else ())
    ideal = np.atleast_1d(np.asarray(StatevectorEstimator().run([ideal_pub]).result()[0].data.evs))

    # Configurations are independent, so run them side by side.
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            name: pool.submit(run_config, name, args.logical, args.backend, args.precision,
                              args.seed, noise_factors, args.points, args.optimization_level,
                              args.fractional)
            for name in names
        }
        results = [futures[name].result() for name in names]

    ranked = ideal.size > 2
    print(f"ideal range [{ideal.min():.3f}, {ideal.max():.3f}] over {ideal.size} point(s); "
          f"precision {args.precision}; backend {args.backend}")
    print("| config | MAE vs ideal | Spearman rho | argmin match | runtime (s) |")
    print("|---|---|---|---|---|")
    for res in results:
        evs = np.asarray(res["evs"])
        res["mae"] = float(np.mean(np.abs(evs - ideal)))
        if ranked:
            res["spearman"] = float(spearmanr(evs, ideal).statistic)
            res["argmin_match"] = bool(np.argmin(evs) == np.argmin(ideal))
        print(f"| {res['name']} | {res['mae']:.3f} | {res.get('spearman', float('nan')):.3f} | "
              f"{res.get('argmin_match', '-')} | {res['runtime_s']:.0f} |")
    with open(args.out, "w") as f:
        json.dump({"ideal": ideal.tolist(), "results": results}, f, indent=1)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
