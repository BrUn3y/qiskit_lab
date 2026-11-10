---
title: Dynamical Decoupling
description: Error suppression technique that inserts pulse sequences on idling qubits to cancel coherent errors from unwanted qubit interactions during idle time.

capability_id: dynamical-decoupling
name: "Dynamical Decoupling"
category: error-suppression
short_description: Inserts pulse sequences on idle qubits to suppress coherent errors from unwanted qubit coupling during circuit execution gaps.

primitive_estimator: true
primitive_sampler: true
primitive_executor: true
output_type: any
estimate_bias: not-applicable

overhead_class: low
overhead_detail: "Pre-processing only; no additional circuit executions. Slightly increases circuit duration due to inserted pulse sequences."
requires_noise_learning: false
requires_hardware: true

resilience_level_activation: null
api_class: "qiskit_ibm_runtime.options.DynamicalDecouplingOptions"
api_guide: "https://quantum.cloud.ibm.com/docs/en/api/qiskit-ibm-runtime/options-dynamical-decoupling-options.md"

use_when:
  - "Circuit contains idle periods where one or more qubits have no active operations"
  - "Coherent noise from qubit-qubit coupling during idle time is a known noise source"
  - "Running on IBM Quantum hardware"
  - "Circuit depth is moderate; not all qubits are continuously active throughout execution"
  - "Dynamic circuit where one or more qubits is going through lengthy measurement and classical operations while other qubits remain idle (insert the DD sequence manually, preferably with stretch; see prerequisites)"
  - "Idle windows are long relative to T2, so meaningful coherent dephasing accumulates during them (e.g. dynamic circuits with mid-circuit measurement, or long/sparse circuits where total duration is a non-negligible fraction of T2)"

avoid_when:
  - "Circuit is very dense and all qubits are active at nearly all times (no idle gaps to fill; added pulses may worsen results due to pulse imperfections)"
  - "Idle windows are very short relative to T2 (e.g. tens of ns vs. T2 of tens-to-hundreds of µs), so little coherent dephasing accumulates and the inserted pulses' own gate error and over-rotation can exceed the benefit — verify empirically, do not assume DD helps"
  - "Simulator-only workflow without pulse-level noise modeling (no effect)"

prerequisites:
  - "EstimatorV2, SamplerV2 or Executor primitive"
  - "For a dynamic circuit with conditional operations, the DD sequence is inserted manually, preferably with stretch: the SamplerV2 dynamical_decoupling option does not support such circuits, and Qiskit's PadDynamicalDecoupling pass fails on them (no duration for if_else)"
  - "Hardware backend"
  - "ISA circuit (transpiled to the target backend)"

compatible_with:
  - pauli-twirling
  - trex
  - zne-gate-folding
  - zne-pea
  - pec
  - m3
  - obp
  - pec-slc
  - pna

notes_composability: >
  Dynamical decoupling operates at the pulse schedule level before execution
  and is orthogonal to all expectation-value mitigation techniques. It is
  compatible with fractional gates, unlike gate twirling. Combine freely
  with TREX, ZNE, and PEC for Estimator workloads, or with Pauli twirling for Sampler.

references:
  - "Niu et al., Phys. Rev. Applied 20, 064027 (2023)"

related_docs:
  - title: "Error mitigation and suppression techniques: Dynamical decoupling"
    url: "https://quantum.cloud.ibm.com/docs/en/guides/error-mitigation-and-suppression-techniques.md#dynamical-decoupling"
    type: guide
  - title: "Overview of noise management techniques"
    url: "https://quantum.cloud.ibm.com/docs/en/guides/error-mitigation-overview.md"
    type: guide
  - title: "Configure noise management with Estimator"
    url: "https://quantum.cloud.ibm.com/docs/en/guides/estimator-noise-management.md"
    type: guide
  - title: "Configure noise management with Sampler"
    url: "https://quantum.cloud.ibm.com/docs/en/guides/sampler-noise-management.md"
    type: guide
  - title: "Combine error mitigation options with the Estimator primitive"
    url: "https://quantum.cloud.ibm.com/docs/en/tutorials/combine-error-mitigation-techniques.md"
    type: tutorial
  - title: "DynamicalDecouplingOptions API reference"
    url: "https://quantum.cloud.ibm.com/docs/en/api/qiskit-ibm-runtime/options-dynamical-decoupling-options.md"
    type: api-reference
  - title: "Specify Sampler options"
    url: "https://quantum.cloud.ibm.com/docs/en/guides/sampler-options.md"
    type: guide
  - title: "Specify Estimator options"
    url: "https://quantum.cloud.ibm.com/docs/en/guides/estimator-options.md"
    type: guide
  - title: "Create a pass manager for dynamical decoupling"
    url: "https://quantum.cloud.ibm.com/docs/en/guides/dynamical-decoupling-pass-manager.md"
    type: guide
  - title: "Deferred timing resolution using stretch"
    url: "https://quantum.cloud.ibm.com/docs/en/guides/stretch.md"
    type: guide
---

## Summary

Dynamical decoupling suppresses coherent errors that accumulate on qubits that sit idle during circuit execution. Hardware circuits are executed as sequences of microwave pulses, and during idle periods, unwanted qubit-qubit interactions cause coherent errors to accumulate. DD inserts pulse sequences (such as XX or XpXm) into idle time slots. Each inserted sequence is equivalent to an identity operation, but the physical pulses cancel coherent error accumulation. DD is a pre-processing technique; it adds no additional circuit executions.

## When to use

- The circuit has idle periods — at least one qubit is inactive while others are executing gates. This is common in circuits with limited connectivity or highly sequential structure.
- Coherent crosstalk between neighboring qubits during idle time is a suspected noise source on the target backend.
- The circuit density is moderate. Sparse or moderately dense circuits benefit most; very dense circuits leave no idle time for DD pulses.
- The idle windows are long enough relative to T2 for coherent dephasing to actually accumulate in them. Dynamic circuits (a qubit idles through another's mid-circuit measurement and feed-forward) are the strongest case; DD was designed with exactly that in mind.

## When not to use

- The circuit is very dense, meaning all qubits are active most of the time. In this case there are few or no idle gaps, DD pulses provide no benefit, and imperfect pulses can degrade results.
- When idle windows are much shorter than the qubit coherence time, the dephasing accumulated during those idle periods is minimal. In such cases, the additional errors introduced by the DD pulses themselves may exceed the reduction in idle-time dephasing. This is a genuine grey area — resolve it with the Validation section rather than assuming DD helps.
- Simulator-only workflow. DD has no effect on a simulator unless its noise model includes coherent idle errors on the scheduled idle windows (see Validation).

## Trade-offs

| Dimension | Value |
|---|---|
| Shot overhead | None (pre-processing only) |
| Circuit execution count | 1× |
| Estimate bias | Reduces coherent error bias; does not address stochastic gate errors |
| Learning phase | None |
| Sequence options | XX (default), XpXm, XY4 |
| Scales with circuit depth | Overhead is fixed; benefit depends on idle time available |

## Configuration

```python
# Client-side Estimator (qiskit-ibm-runtime >= 0.50.0); checked against 0.50.0.
from qiskit_ibm_runtime.executor_estimator import Estimator

estimator = Estimator(mode=backend)
estimator.options.dynamical_decoupling.enable = True
estimator.options.dynamical_decoupling.sequence_type = "XpXm"
```

Sequence type options (checked against 0.50.0, both client-side and server-side Estimator): `"XX"` (default), `"XpXm"`, `"XY4"`. Other values such as `"YpYm"` or `"XYXY"` raise a `ValidationError`. The best choice for a given circuit is backend- and circuit-dependent; `"XpXm"` is a common starting point for asymmetric noise. `XpXm` uses opposite-sign pulses, so a static pulse over-rotation cancels between the pair rather than accumulating as it does in `XX` — prefer it when pulse amplitude error is the dominant DD cost.

### With the Executor

The Executor has no DD option. Add DD with Qiskit's scheduling passes, as in the [DD pass manager guide](https://quantum.cloud.ibm.com/docs/en/guides/dynamical-decoupling-pass-manager.md). Checked against qiskit 2.4.0, samplomatic 0.21.0 and qiskit-mitigation 0.1.1.

**Apply DD after twirling.** The twirling gates change each qubit's timing, so DD must be scheduled on the circuit that already contains them: with samplomatic, the template circuit from `samplomatic.build`; with `qiskit-mitigation`, each program item's circuit after `prepare`. Padding the ISA circuit before boxing schedules DD against timing that twirling then changes.

```python
import samplomatic
from qiskit.circuit.library import XGate
from qiskit.transpiler import PassManager
from qiskit.transpiler.passes import ALAPScheduleAnalysis, PadDynamicalDecoupling

target = backend.target
dd_pm = PassManager([
    ALAPScheduleAnalysis(target=target),
    PadDynamicalDecoupling(target=target, dd_sequence=[XGate(), XGate()]),
])

# samplomatic: twirl first (boxing + build), then pad the template circuit
template_circuit, samplex = samplomatic.build(boxed_circuit)
template_circuit = dd_pm.run(template_circuit)

# qiskit-mitigation: pad each item circuit after prepare
program = task.prepare(isa_circuit, observables, parameters)
for item in program.items:
    item.circuit = dd_pm.run(item.circuit)
```

The padded template keeps samplomatic's barriers and parameters, so the samplex still binds; with noise off, its output distribution matches the unpadded template within shot noise. For a sequence with gates that are not in the target (for example `Y` in XY4), add their durations to the target and run `BasisTranslator` afterwards, as in the guide.

**Dynamic circuits.** `PadDynamicalDecoupling` fails on a circuit with conditional operations (`TranspilerError: Duration of if_else on qubits [...] is not found` on qiskit 2.4.0), and so does any automatic DD. Insert the sequence by hand instead, preferably with `stretch`: its duration is resolved at compile time, after the conditional block's duration is known. Two barriers bound the region the stretch fills. From the [stretch guide](https://quantum.cloud.ibm.com/docs/en/guides/stretch.md), an XX sequence on `q1` while `q0` runs a conditional block:

```python
from qiskit.circuit.classical import expr

circuit.barrier()
circuit.h(q0)
circuit.measure(q0, c0)
with circuit.if_test((c0, 1)) as else_:
    circuit.h(q0)
with else_:
    circuit.x(q0)

s = circuit.add_stretch("s")
circuit.delay(s, q1)
circuit.x(q1)
circuit.delay(expr.mul(s, 2), q1)
circuit.x(q1)
circuit.delay(s, q1)
circuit.barrier()
```

samplomatic twirling does not support dynamic circuits (its boxing pass manager rejects `if_else`, and `samplomatic.build` cannot propagate through it), so a dynamic circuit on the Executor gets stretch-based DD without samplomatic twirling. On a circuit samplomatic can twirl, stretch-based DD goes on the template circuit from `samplomatic.build`, after twirling: the padded template keeps its parameters and the `QuantumProgram` builds. Local simulators cannot run stretch delays (the local Executor and `AerSimulator` both reject them), so a stretch-padded program only runs on hardware.

Stretch support on IBM Quantum hardware is experimental, with constraints listed in the guide: at most one stretch per qubit set in a barrier region, a stretch used in only one barrier region, and expressions of the form `X*stretch + Y`.

## Validation

Whether DD helps a given circuit is often a grey area that the `use_when`/`avoid_when` conditions cannot settle from static context. Evaluate it in two steps; neither requires hardware.

**Step 1 — Measure the idle structure by scheduling the ISA circuit.** DD only acts on idle time, so first find out how much there is and how long the windows are. Schedule with an ALAP pass and pad the delays, using the target's real instruction durations:

```python
from qiskit.transpiler import PassManager
from qiskit.transpiler.passes import RemoveBarriers, ALAPScheduleAnalysis, PadDelay

def interior_idle_windows(isa_circuit, target):
    """Per-qubit idle windows between each qubit's first and last gate (seconds).

    Leading delays (under ALAP the qubit is still in |0>, where DD has nothing to
    protect) and the final measurement are excluded.
    """
    scheduled = PassManager([
        RemoveBarriers(),          # barriers have no duration; ALAP fails on them otherwise
        ALAPScheduleAnalysis(target=target),
        PadDelay(target=target),
    ]).run(isa_circuit)            # bind parameters first
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
    return windows, spans

windows, spans = interior_idle_windows(bound_isa_circuit, fake_backend.target)  # e.g. FakeKingston()
# idle fraction per qubit: sum(windows[q]) / spans[q]; compare window lengths against target.qubit_properties[q].t2
```

Summing every `Delay` in the scheduled circuit overstates the idle time DD can use: under ALAP, the delays before a qubit's first gate leave it in |0⟩, and the measurement adds a long tail at the end.

Report the idle *fraction* (is there room for DD at all — this tests the "very dense" `avoid_when`) **and** the idle *window duration vs. T2* (is there enough dephasing for DD to remove — this tests the "windows too short" `avoid_when`). High idle fraction with sub-µs windows against a 100 µs T2 means DD has gaps to fill but almost nothing to gain.

**Step 2 — Measure the actual benefit on a small density-matrix patch.** Use `verification.md`, Method B.

## Composability

DD is orthogonal to all expectation-value mitigation techniques (TREX, ZNE, PEC) and can be combined freely with any of them. It is also compatible with Pauli twirling on the Estimator, Sampler and Executor, and with fractional gates, which gate twirling, PEA and PEC are not. When DD is applied by hand, as on the Executor, apply it after twirling (see Configuration).

Automatic DD does not support dynamic circuits with conditional operations: neither the Sampler's `dynamical_decoupling` option nor Qiskit's `PadDynamicalDecoupling` pass handles them. Insert the DD sequence manually instead, preferably with `stretch`, since the duration of the classical feed-forward is unknown in advance (see Configuration). Through the Estimator or Sampler options, gate twirling is incompatible with stretches. On the Executor, samplomatic twirling does not support dynamic circuits at all; on circuits it can twirl, add stretch-based DD to the template circuit after twirling, as for any DD.
