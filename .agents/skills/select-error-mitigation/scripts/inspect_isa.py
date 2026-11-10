"""Phase 1.5 inspection: structure, fractional gates, idle time and signal of an ISA circuit.

Reports in one call what SKILL.md Phase 1.5 asks for, so no per-workload script is needed,
including the estimated QPU time per technique (guides/estimate-job-run-time).

Input is a ``RuntimeEncoder`` JSON file of a list of ``(isa_circuit, isa_observable)`` tuples, transpiled for the
fake backend named with ``--backend``. ``isa_observable`` may be ``None`` when the workload
is Sampler-only::

    import json
    from qiskit_ibm_runtime import RuntimeEncoder
    with open("/tmp/em/isa.json", "w") as f:
        json.dump([(isa_circuit, isa_observable)], f, cls=RuntimeEncoder)

    python inspect_isa.py /tmp/em/isa.json --backend FakeKingston --neat --save-cpubs /tmp/em/cpubs.json

Parameterized circuits are bound to ``--param-value`` for the idle-time schedule and for
NEAT. With ``--neat``, the Clifford PUBs are saved the same way for ``verify_c2.py`` when
``--save-cpubs`` is given.
"""

from __future__ import annotations

import argparse
import math
from collections import Counter

import numpy as np
from qiskit.converters import circuit_to_dag
from qiskit.transpiler import PassManager, generate_preset_pass_manager
from qiskit.transpiler.passes import ALAPScheduleAnalysis, PadDelay, RemoveBarriers

from verify_c2 import fake_backend, load_json, save_json

FRACTIONAL = {"rx", "rzz"}
SUB_JOB_OVERHEAD = 2.0  # seconds per sub-job (guides/estimate-job-run-time)
LEARNING_PER_LAYER = 60.0  # seconds of QPU time per unique layer, NoiseLearnerV3 defaults


def count_unique_2q_layers(isa_circuit) -> int:
    layers = set()
    for layer in circuit_to_dag(isa_circuit).layers():
        pairs = frozenset(
            tuple(sorted(isa_circuit.find_bit(q).index for q in node.qargs))
            for node in layer["graph"].op_nodes() if node.op.num_qubits == 2)
        if pairs:
            layers.add(pairs)
    return len(layers)


def execution_seconds(isa_circuit, backend, rep_delay=None, init_qubits=True) -> float:
    """``rep_delay + INIT + <circuit length>`` for one shot (guides/estimate-job-run-time).

    An Estimator ISA circuit has no measurements yet, so they are added before timing.
    """
    if not any(inst.operation.name == "measure" for inst in isa_circuit.data):
        isa_circuit = isa_circuit.measure_active(inplace=False)
    scheduled = generate_preset_pass_manager(
        target=backend.target, optimization_level=0, scheduling_method="alap").run(isa_circuit)
    rep_delay = backend.default_rep_delay if rep_delay is None else rep_delay
    init = backend.target["reset"][(0,)].duration if init_qubits else 0.0
    return scheduled.estimate_duration(backend.target) + init + rep_delay


def report_qpu_time(isa_circuit, observable, backend, shots, rep_delay, num_layers) -> None:
    """QPU time per parameter point: ``2 s + <seconds per shot> * shots * <num circuits>``.

    Excludes the calibration circuits TREX adds, so it is a lower bound for TREX.
    """
    per_shot = execution_seconds(isa_circuit, backend, rep_delay)
    # Estimator runs one circuit per qubit-wise commuting group of the observable.
    groups = len(observable.group_commuting(qubit_wise=True)) if observable is not None else 1
    run = per_shot * shots * groups
    # Gate folding at noise factors (1, 3, 5) runs three circuits. rep_delay and INIT
    # dominate the per-shot time, so folding barely lengthens each shot.
    zne = 3 * run
    learning = num_layers * LEARNING_PER_LAYER
    print(f"  estimated QPU time per parameter point ({shots} shots x {groups} circuits, "
          f"{per_shot * 1e6:.0f} us per shot):")
    print(f"    no mitigation / TREX / twirling: ~{math.ceil(SUB_JOB_OVERHEAD + run)} s")
    print(f"    ZNE gate folding (1, 3, 5): ~{math.ceil(SUB_JOB_OVERHEAD + zne)} s")
    print(f"    ZNE PEA (1, 1.5, 2): ~{math.ceil(SUB_JOB_OVERHEAD + zne)} s "
          f"+ {learning / 60:.0f} min noise learning (once per unique-layer set)")
    print(f"    PEC: ~{math.ceil(run)} s x gamma^2 (up to max_overhead, default 100: "
          f"~{math.ceil(SUB_JOB_OVERHEAD + 100 * run)} s) + {learning / 60:.0f} min noise learning")


def interior_idle_windows(isa_circuit, target):
    """Per-qubit idle windows between each qubit's first and last gate (seconds).

    Same method as dynamical-decoupling.md, Validation step 1.
    """
    scheduled = PassManager([
        RemoveBarriers(),
        ALAPScheduleAnalysis(target=target),
        PadDelay(target=target),
    ]).run(isa_circuit)
    active = set(isa_circuit.layout.final_index_layout()) if isa_circuit.layout else set(range(isa_circuit.num_qubits))
    seq = {q: [] for q in active}
    for inst in scheduled.data:
        name = inst.operation.name
        qargs = tuple(scheduled.find_bit(q).index for q in inst.qubits)
        if name == "delay":
            dur = inst.operation.duration * target.dt
        else:
            props = target[name].get(qargs) if name in target.operation_names else None
            dur = (props.duration or 0.0) if props is not None else 0.0
        for q in qargs:
            if q in seq:
                seq[q].append((name, dur))
    windows, spans = {}, {}
    for q, ops in seq.items():
        while ops and ops[0][0] == "delay":
            ops.pop(0)
        while ops and ops[-1][0] in ("measure", "delay"):
            ops.pop()
        windows[q] = [d for n, d in ops if n == "delay"]
        spans[q] = sum(d for _, d in ops)
    return windows, spans, scheduled.duration * target.dt


def inspect(isa_circuit, observable, backend, param_value: float, run_neat: bool,
            shots: int, rep_delay: float | None):
    target = backend.target
    ops = isa_circuit.count_ops()
    print(f"  ops: {dict(ops)}")

    fractional = sorted(FRACTIONAL & set(ops))
    if fractional:
        print(f"  FRACTIONAL GATES: {fractional}. Check each capability page's avoid_when "
              "(SKILL.md Phase 4a).")

    # Lower bound on two-qubit depth if every two-qubit gate commuted: the largest number
    # of two-qubit gates on any one qubit. A depth far above it means gates that could run
    # in parallel are serialized, e.g. commuting ZZ terms applied in edge-list order.
    per_qubit = Counter()
    for inst in isa_circuit.data:
        if inst.operation.num_qubits == 2:
            for q in inst.qubits:
                per_qubit[isa_circuit.find_bit(q).index] += 1
    depth_2q = isa_circuit.depth(lambda i: i.operation.num_qubits == 2)
    bound = max(per_qubit.values(), default=0)
    num_layers = count_unique_2q_layers(isa_circuit)
    print(f"  two-qubit gates: {sum(per_qubit.values()) // 2}, depth {depth_2q}, "
          f"max per qubit {bound}, unique layers {num_layers} "
          f"(~{num_layers} min of PEA/PEC noise learning)")
    if bound and depth_2q > 2 * bound:
        print(f"  STRUCTURE: two-qubit depth is {depth_2q / bound:.1f}x the per-qubit gate count. "
              "If the terms commute, reorder them (for example by edge coloring) before "
              "choosing mitigation.")

    bound_circuit = isa_circuit.assign_parameters([param_value] * isa_circuit.num_parameters) \
        if isa_circuit.num_parameters else isa_circuit
    windows, spans, duration = interior_idle_windows(bound_circuit, target)
    fractions = [sum(windows[q]) / spans[q] for q in windows if spans[q]]
    all_windows = [d for q in windows for d in windows[q]]
    t2 = np.median([target.qubit_properties[q].t2 for q in windows
                    if target.qubit_properties[q].t2])
    print(f"  duration {duration * 1e6:.2f} us; idle fraction median {np.median(fractions):.3f}, "
          f"max {max(fractions):.3f}")
    if all_windows:
        print(f"  idle windows: median {np.median(all_windows) * 1e9:.0f} ns, "
              f"max {max(all_windows) * 1e9:.0f} ns; median T2 {t2 * 1e6:.0f} us "
              f"(max window / T2 = {max(all_windows) / t2:.3f})")
    report_qpu_time(bound_circuit, observable, backend, shots, rep_delay, num_layers)

    if run_neat and observable is not None:
        from qiskit_ibm_runtime.debug_tools import Neat

        neat = Neat(backend)
        pub = (bound_circuit, observable)
        cpubs = neat.to_clifford([pub])
        ideal = np.asarray(neat.ideal_sim(cpubs)[0].vals)
        noisy = np.asarray(neat.noisy_sim(cpubs, seed_simulator=1234, precision=0.01)[0].vals)
        print(f"  NEAT Clifford stand-in: ideal {np.round(ideal, 3).tolist()}, "
              f"noisy {np.round(noisy, 3).tolist()}")
        # A ratio against an ideal value this close to 0 is dominated by the 0.01 shot noise.
        scale = float(np.sum(np.abs(observable.coeffs)))
        if np.all(np.abs(ideal) < 0.1 * scale):
            print("  NEAT: ideal value is near 0 on the stand-in, so the surviving fraction is "
                  "not meaningful. Try another --param-value, or add stabilizer observables "
                  "(verification.md, 'Checking a Clifford stand-in').")
        else:
            print(f"  NEAT: fraction surviving {np.round(noisy / ideal, 3).tolist()}")
        return cpubs
    return []


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pubs", help="RuntimeEncoder JSON of [(isa_circuit, isa_observable or None), ...]")
    parser.add_argument("--backend", default="FakeKingston", help="fake backend class name")
    parser.add_argument("--param-value", type=float, default=0.3,
                        help="value bound to every parameter for scheduling and NEAT")
    parser.add_argument("--neat", action="store_true", help="run the NEAT signal-strength check")
    parser.add_argument("--save-cpubs", help="JSON path for the Clifford PUBs (needs --neat)")
    parser.add_argument("--shots", type=int, default=4096,
                        help="shots per circuit for the QPU-time estimate; for an Estimator, "
                             "about 1 / precision**2 (4096 at the default precision 0.015625)")
    parser.add_argument("--rep-delay", type=float,
                        help="rep_delay in seconds (default: backend.default_rep_delay)")
    args = parser.parse_args()

    backend = fake_backend(args.backend)
    pubs = load_json(args.pubs)
    cpubs = []
    for i, (isa_circuit, observable) in enumerate(pubs):
        print(f"[pub {i}] {isa_circuit.num_qubits}-qubit ISA circuit on {args.backend}")
        cpubs += inspect(isa_circuit, observable, backend, args.param_value, args.neat,
                         args.shots, args.rep_delay)
    if args.save_cpubs and cpubs:
        save_json(cpubs, args.save_cpubs)
        print(f"wrote {args.save_cpubs}")


if __name__ == "__main__":
    main()
