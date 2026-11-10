"""Method C2 runner: compare mitigation configurations in stabilizer local mode.

Runs the client-side Estimator (qiskit-ibm-runtime >= 0.50.0) in local testing mode on a
Clifford stand-in, once per configuration, and scores each against the exact ideal value.
See verification.md, Method C2.

Step 1 (main session, during SKILL.md Phase 1.5): save the Clifford PUBs once, so the
signal-strength check and this runner use the same circuit::

    import json
    from qiskit_ibm_runtime import RuntimeEncoder
    from qiskit_ibm_runtime.debug_tools import Neat
    cpubs = Neat(fake_backend).to_clifford([(isa_circuit, isa_observables)])
    with open("/tmp/em/cpubs.json", "w") as f:
        json.dump(cpubs, f, cls=RuntimeEncoder)

Step 2::

    python verify_c2.py /tmp/em/cpubs.json --backend FakeKingston \
        --configs rl0,trex,trex_twirl,zne --workers 4 --out /tmp/em/c2.json

Configurations (each changes one technique on top of the previous one):
    rl0                no mitigation, no twirling
    trex               TREX (measurement mitigation + measurement twirling)
    trex_twirl         TREX + gate twirling, strategy "active-accum" (default)
    trex_twirl_active  TREX + gate twirling, strategy "active"
    zne                TREX + gate twirling ("active-accum") + gate-folding ZNE
    zne_notwirl        TREX + gate-folding ZNE, no gate twirling (the server-side fractional-RZZ stack)

With --fractional, the gate-twirled configurations use twirling group "local_pauli", the only
group that twirls fractional RZZ gates (relatively untested; see pauli-twirling.md, "Fractional
gates"). Leave it off for a circuit whose only fractional gates are RX: the default group twirls
those.

The noise model is the fake backend's calibration snapshot with thermal relaxation removed
(the stabilizer method rejects its Kraus channels). It has no coherent error, so gate
twirling's benefit against coherent error is not measurable here; only its cost shows.
"""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

CONFIGS = ("rl0", "trex", "trex_twirl", "trex_twirl_active", "zne", "zne_notwirl")
GATE_TWIRLED = {"trex_twirl", "trex_twirl_active", "zne"}


def fake_backend(name: str):
    from qiskit_ibm_runtime import fake_provider

    return getattr(fake_provider, name)()


def save_json(obj, path: str) -> None:
    """Write circuits, observables or PUBs with ``RuntimeEncoder`` (guides/save-jobs)."""
    from qiskit_ibm_runtime import RuntimeEncoder

    with open(path, "w") as f:
        json.dump(obj, f, cls=RuntimeEncoder)


def load_json(path: str):
    from qiskit_ibm_runtime import RuntimeDecoder

    with open(path) as f:
        return json.load(f, cls=RuntimeDecoder)


def load_estimator_pubs(path: str) -> list:
    """``RuntimeEncoder`` writes each ``EstimatorPub`` as a plain list; coerce it back."""
    from qiskit.primitives.containers.estimator_pub import EstimatorPub

    return [EstimatorPub.coerce(tuple(pub)) for pub in load_json(path)]


def select_configs(parser: argparse.ArgumentParser, configs: str) -> list[str]:
    """Parse ``--configs``."""
    names = [n.strip() for n in configs.split(",") if n.strip()]
    unknown = set(names) - set(CONFIGS)
    if unknown:
        parser.error(f"unknown configs {sorted(unknown)}; choose from {CONFIGS}")
    return list(dict.fromkeys(names))


def configure_options(options, name: str, noise_factors: list[float], fractional: bool = False) -> None:
    # Build every configuration up from resilience level 0, so only the technique
    # under test changes between runs.
    options.resilience_level = 0
    options.resilience.measure_mitigation = name != "rl0"
    options.twirling.enable_measure = name != "rl0"
    options.twirling.enable_gates = name in GATE_TWIRLED
    if name in GATE_TWIRLED:
        options.twirling.strategy = "active" if name == "trex_twirl_active" else "active-accum"
        if fractional:
            # Only "local_pauli" twirls fractional RZZ gates.
            options.twirling.group = "local_pauli"
    options.resilience.zne_mitigation = name.startswith("zne")
    if name.startswith("zne"):
        options.resilience.zne.amplifier = "gate_folding"
        options.resilience.zne.noise_factors = noise_factors
        # One run gives both fits; evs_extrapolated has one row per extrapolator.
        options.resilience.zne.extrapolator = ["exponential", "linear"]


def run_config(
    name: str,
    pubs_path: str,
    backend_name: str,
    precision: float,
    seed: int,
    noise_factors: list[float],
    fractional: bool,
) -> dict:
    from qiskit_aer import AerSimulator
    from qiskit_aer.noise import NoiseModel
    from qiskit_ibm_runtime.executor_estimator import Estimator

    backend = fake_backend(backend_name)
    cpubs = load_estimator_pubs(pubs_path)
    pubs = [(pub.circuit, pub.observables, pub.parameter_values) for pub in cpubs]

    noise_model = NoiseModel.from_backend(backend, thermal_relaxation=False)
    mode = AerSimulator.from_backend(backend, method="stabilizer", noise_model=noise_model)
    estimator = Estimator(mode=mode)
    estimator.options.default_precision = precision
    estimator.options.simulator.seed_simulator = seed
    configure_options(estimator.options, name, noise_factors, fractional)

    start = time.time()
    result = estimator.run(pubs).result()
    out = {"name": name, "runtime_s": time.time() - start, "pubs": []}
    for pub_result in result:
        data = pub_result.data
        entry = {
            "evs": np.asarray(data.evs).tolist(),
            "stds": np.asarray(data.stds).tolist(),
        }
        if hasattr(data, "evs_noise_factors"):
            entry["evs_noise_factors"] = np.asarray(data.evs_noise_factors).tolist()
            # Last axis is [0, *noise_factors]; the axis before it is the extrapolator.
            extrapolated = np.asarray(data.evs_extrapolated)
            entry["exponential"] = extrapolated[..., 0, 0].tolist()
            entry["linear"] = extrapolated[..., 1, 0].tolist()
        out["pubs"].append(entry)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pubs", help="RuntimeEncoder JSON of Clifford PUBs from Neat(backend).to_clifford")
    parser.add_argument("--backend", default="FakeKingston", help="fake backend class name")
    parser.add_argument("--configs", default="rl0,trex,trex_twirl,zne")
    parser.add_argument("--fractional", action="store_true", help="workload uses fractional RZZ gates: twirl with group local_pauli (RX-only needs no flag)")
    parser.add_argument("--noise-factors", default="1,3,5")
    parser.add_argument("--precision", type=float, default=0.02)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--out", default="c2_results.json")
    args = parser.parse_args()

    names = select_configs(parser, args.configs)
    noise_factors = [float(x) for x in args.noise_factors.split(",")]

    from qiskit_ibm_runtime.debug_tools import Neat

    cpubs = load_estimator_pubs(args.pubs)
    ideal = [np.asarray(r.vals) for r in Neat(fake_backend(args.backend)).ideal_sim(cpubs)]
    if all(np.allclose(v, 0) for v in ideal):
        print("WARNING: every ideal value is 0; the stand-in measures only shot noise "
              "(verification.md, 'Checking a Clifford stand-in').")

    # Configurations are independent, so run them side by side.
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            name: pool.submit(run_config, name, args.pubs, args.backend, args.precision,
                              args.seed, noise_factors, args.fractional)
            for name in names
        }
        results = [futures[name].result() for name in names]

    print("| config | pub | ev | std | MAE vs ideal | runtime (s) |")
    print("|---|---|---|---|---|---|")
    for res in results:
        for i, entry in enumerate(res["pubs"]):
            mae = float(np.mean(np.abs(np.asarray(entry["evs"]) - ideal[i])))
            entry["mae"] = mae
            print(f"| {res['name']} | {i} | {np.round(entry['evs'], 3).tolist()} | "
                  f"{np.round(entry['stds'], 3).tolist()} | {mae:.3f} | {res['runtime_s']:.0f} |")
            if "evs_noise_factors" in entry:
                print(f"|   per factor {noise_factors} | {i} | "
                      f"{np.round(entry['evs_noise_factors'], 3).tolist()} | exp "
                      f"{np.round(entry['exponential'], 3).tolist()} | linear "
                      f"{np.round(entry['linear'], 3).tolist()} | |")
    with open(args.out, "w") as f:
        json.dump({"ideal": [v.tolist() for v in ideal], "noise_factors": noise_factors,
                   "results": results}, f, indent=1)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
