---
title: Post-selection with non-Markovian error checks
description: Adds bit-flip checks with a slow X pulse before and after the circuit, on the measured qubits and their neighbours, then discards the shots in which a check failed, removing shots affected by non-Markovian noise.

capability_id: postselection-non-markovian
name: "Post-selection with non-Markovian error checks"
category: post-selection
short_description: Adds slow-X-pulse bit-flip checks before and after the circuit on measured and spectator qubits, then keeps only the shots that pass, removing samples corrupted by non-Markovian noise.

primitive_estimator: false
primitive_sampler: true
primitive_executor: true
output_type: any
estimate_bias: reduced-bias

overhead_class: high
overhead_detail: "No extra circuits, but discarded shots: the shot overhead is 1 / (kept fraction), which depends on the strategy and circuit width. In the IBM guide (20-qubit mirrored 1D Ising, 6 Trotter steps, 7 spectators, ibm_kingston, 100,000 shots), edge-based checks kept 3.8–27.5% of shots and node-based checks 0.03–2.3%; the best result (pre=node + post=node) kept 28 shots. In the PEC+SLC tutorial (20 qubits, post-circuit node strategy) about 24% were kept. Each check also adds a slow X pulse, an X and a measurement per checked qubit, which lengthens the circuit."
requires_noise_learning: false
requires_hardware: true

resilience_level_activation: null
api_class: "qiskit_mitigation.postselection.PostSelector"
api_guide: "https://quantum.cloud.ibm.com/docs/en/addons/qiskit-mitigation/guides/postselection-with-non-markovian-error-checks"

use_when:
  - "Non-Markovian error sources (for example two-level-system defects) intermittently corrupt shots on the target backend"
  - "Output comes from per-shot bitstrings: Executor, or the client-side Sampler"
  - "The shot budget can absorb discarding most shots (edge strategy: roughly 4–25× more shots; node strategy: 40× or more)"
  - "Results show shot-to-shot outliers or drift that Markovian mitigation (TREX, ZNE, PEC) does not remove"
  - "Stacking on an Executor workflow (PEC+SLC, PNA) that already post-processes per-shot data and accepts a post-selection mask"
  - "Stacking on ZNE (gate folding or PEA) or PEC run through qiskit-mitigation on the Executor, with the expectation values recomputed through executor_expectation_values"
  - "Dynamic circuit (mid-circuit measurements, if_else): the checks and PostSelector handle the extra classical registers"

avoid_when:
  - "Workload must stay on the Estimator primitive (it returns expectation values, not per-shot bits). An Estimator workload that can move to the Executor or the client-side Sampler is not excluded"
  - "Backend target has neither xslow nor rx (rx requires use_fractional_gates=True)"
  - "Shot budget cannot absorb the discarded shots"
  - "No hardware access: simulators have no non-Markovian noise, so nothing meaningful is filtered"
  - "Checks would be added without post-selecting on them (the added pulses and measurements make the raw result worse)"
  - "Circuit has no terminal measurements (checks are placed only on qubits that end in a measurement, plus their spectators)"

prerequisites:
  - "qiskit-mitigation >= 0.1 (pip install qiskit-mitigation)"
  - "qiskit-ibm-runtime >= 0.47.0 for the Executor; >= 0.49.0 to apply checks during NoiseLearnerV3 learning (bit_flip_checks)"
  - "The chosen x_pulse_type in the backend target: 'xslow' (no fractional gates needed), or 'rx' (needs service.backend(name, use_fractional_gates=True))"
  - "ISA circuit with terminal measurements"
  - "Re-transpile after adding the checks (generate_preset_pass_manager(optimization_level=0)), as the guide does"
  - "Per-shot results as a {register name: bool array} mapping (Executor results already are; convert Sampler BitArrays with to_bool_array(order='little'))"

compatible_with:
  - trex
  - pauli-twirling
  - zne-gate-folding
  - zne-pea
  - pec
  - pec-slc
  - pna
incompatible_with: []

notes_composability: >
  Post-selection filters shots after execution, so it stacks with techniques that
  post-process per-shot data. The PEC+SLC and PNA tutorials pass its mask to
  executor_expectation_values (postselect_mask). With qiskit-mitigation's ZNE, PEA
  and PEC tasks, task.postprocess takes no mask, so recompute the expectation values
  through executor_expectation_values instead. On the Executor, add the checks
  to the template circuit from samplomatic.build, after twirling; a noiseless run
  of a twirled template with checks keeps every shot. NoiseLearnerV3 can apply the
  same checks to its learning circuits (options.bit_flip_checks), so the learned
  noise model also excludes non-Markovian shots.

references:
  - "IBM Quantum guide: Postselection with non-Markovian error checks (qiskit-mitigation)"

related_docs:
  - title: "Postselection with non-Markovian error checks"
    url: "https://quantum.cloud.ibm.com/docs/en/addons/qiskit-mitigation/guides/postselection-with-non-markovian-error-checks"
    type: guide
  - title: "Tutorial: Probabilistic error cancellation with shaded lightcones (stacks post-selection on PEC+SLC)"
    url: "https://quantum.cloud.ibm.com/docs/en/tutorials/pec-with-shaded-lightcones"
    type: tutorial
  - title: "Fractional gates"
    url: "https://quantum.cloud.ibm.com/docs/en/guides/fractional-gates"
    type: guide
  - title: "Directed execution model"
    url: "https://quantum.cloud.ibm.com/docs/en/guides/directed-execution-model.md"
    type: guide
---

## Summary

A non-Markovian error check tests whether a qubit is currently affected by a non-Markovian error source. It applies a slow (narrowband) X pulse, then a regular X, then a measurement. Without such noise the qubit returns to |0⟩, so a measured 1 marks the shot as unreliable. The narrowband pulse is either `xslow` or a chain of N `rx(π/N)` gates. A pre-circuit check runs at the start; a post-circuit check flips each terminal measurement's outcome after it is read. The checks can also go on *spectator* qubits, idle qubits adjacent to the circuit's qubits, for more coverage. After execution, `PostSelector` builds a mask that keeps only the shots that pass. The **node** strategy requires every qubit to pass. The **edge** strategy requires at least one qubit of every coupled pair to pass, so it keeps more shots.

This page covers only post-selection on non-Markovian error checks. Other kinds of post-selection, such as on symmetries or conserved quantities, are not covered.

## When to use

- Non-Markovian noise is a plausible error source on the target backend: shot-to-shot outliers, or drift that Markovian mitigation does not remove.
- The output is per-shot bitstrings, from the Executor or the client-side Sampler. Expectation values can then be computed from the kept shots, as the guide does.
- The shot budget can absorb the discarded shots. Run with all four checks in place; the strategy can then be chosen during post-processing without rerunning.
- The workload already runs on the Executor with per-shot post-processing (PEC+SLC, PNA), where the mask goes straight into `executor_expectation_values`.
- The workload uses ZNE, PEA or PEC through `qiskit-mitigation` on the Executor. The mask then needs an extra post-processing step (see Composability).
- The circuit is dynamic. The passes add a pre and post check register for every measured register, mid-circuit ones included, and leave `if_else` blocks in place.

## When not to use

- The Estimator primitive. It returns expectation values, not per-shot bits, and its circuits have no terminal measurements to check. Use the Executor, or the Sampler with a hand-written expectation value.
- A backend whose target has neither `xslow` nor `rx`. The checks work on every IBM processor family; the `qiskit-mitigation` 0.1.1 pass docstrings, which say Heron only, are outdated. Each check needs one narrowband X pulse: `xslow` needs no fractional gates, and `rx` needs `use_fractional_gates=True`. With `x_pulse_type="rx"` but no `rx` in the target, the transpiler decomposes each `rx` into `rz`/`sx` gates, so the check is no longer one narrowband pulse.
- A small shot budget. In the guide the best estimate kept 28 of 100,000 shots, and some strategies, such as post-only edge, did no better than the raw circuit.
- Adding checks without post-selecting on them. In the guide that gave the worst result (0.521 against 0.579 raw, exact 1.0), because the added pulses and measurements lengthen the circuit.
- No hardware access. Simulators have no non-Markovian noise.

## Trade-offs

| Dimension | Value |
|---|---|
| Shot overhead | 1 / kept fraction. Guide (20 qubits, 7 spectators): edge 3.8–27.5% kept, node 0.03–2.3% kept. Falls with the number of checked qubits |
| Circuit execution count | 1× (checks are added to the same circuit) |
| Estimate bias | Reduced, when the discarded shots are the corrupted ones. Guide: raw 0.579, pre=node 0.603, pre=node + post=node 0.639 (exact 1.0) |
| Learning phase | None |
| Scales with circuit depth | Check cost is fixed per qubit; the kept fraction falls with width and run time |

## Configuration

Checked against qiskit 2.4.0, qiskit-ibm-runtime 0.51.0.dev, qiskit-mitigation 0.1.1 and samplomatic 0.21.0. The passes, `PostSelector` and both result paths below were run on FakeKingston, with `rx` added to its target, through `AerSimulator`. No fake backend includes `xslow`, so the transpiler can't synthesize it locally (`HighLevelSynthesis is unable to synthesize "xslow"`). Only `rx` checks were run.

### 1. Add the checks

```python
from qiskit.transpiler import PassManager, generate_preset_pass_manager
from qiskit_mitigation.postselection.passes import (
    AddPreCircuitNonMarkovianErrorChecks,
    AddPostCircuitNonMarkovianErrorChecks,
    AddSpectatorPreCircuitNonMarkovianErrorChecks,
    AddSpectatorPostCircuitNonMarkovianErrorChecks,
)

# x_pulse_type="rx" needs service.backend("ibm_kingston", use_fractional_gates=True); "xslow" (the default) does not
# Add all four so any strategy can be chosen in post-processing.
checked = PassManager([
    AddPreCircuitNonMarkovianErrorChecks(x_pulse_type="rx"),
    AddSpectatorPreCircuitNonMarkovianErrorChecks(backend.coupling_map, x_pulse_type="rx"),
    AddPostCircuitNonMarkovianErrorChecks(x_pulse_type="rx"),
    AddSpectatorPostCircuitNonMarkovianErrorChecks(backend.coupling_map, x_pulse_type="rx"),
]).run(isa_circuit)
checked_isa = generate_preset_pass_manager(optimization_level=0, backend=backend).run(checked)
# cregs: meas, meas_pre, spec_pre, meas_ps, spec, spec_ps
```

On the Executor with samplomatic, run the same `PassManager` on the template from `samplomatic.build(boxed_circuit)`, then transpile it at `optimization_level=0`. The checks then sit outside the twirled boxes.

### 2. Run and post-select

```python
from qiskit_ibm_runtime import Executor
from samplomatic.quantum_program import QuantumProgram
from qiskit_mitigation.postselection import PostSelector

program = QuantumProgram(shots=100_000)
program.append_circuit_item(checked_isa)
bits = Executor(backend).run(program).result()[0]   # {creg name: bool ndarray}

selector = PostSelector.from_circuit(checked_isa, backend.coupling_map)
keep = selector.compute_mask(bits, "node", mode="both")   # strategy "node" | "edge"; mode "pre" | "post" | "both"
# Pre and post can use different strategies:
# keep = selector.compute_mask(bits, "node", mode="pre") & selector.compute_mask(bits, "edge", mode="post")
kept_meas = bits["meas"][keep]
```

With the client-side Sampler (`qiskit_ibm_runtime.executor_sampler.Sampler`), first convert the `DataBin`; `compute_mask` does not accept it directly:

```python
data = sampler.run([checked_isa]).result()[0].data
bits = {name: data[name].to_bool_array(order="little") for name in data.keys()}
```

`order="little"` gives the same bit order as the Executor's arrays. For a samplex item, the mask has shape `(randomizations, shots)`. That is the shape `executor_expectation_values(..., postselect_mask=keep)` expects.

### 3. Checks during noise learning (Executor workflows)

`NoiseLearnerV3` can apply the same checks to its learning circuits. That way the learned noise model is post-selected the same way as the main circuit:

```python
NoiseLearnerV3(backend, {"bit_flip_checks": {
    "pre_circuit": {"enable": False},
    "post_circuit": {"enable": True, "strategy": "edge", "x_pulse_type": "rx"},
}})
```

`bit_flip_checks` was added in qiskit-ibm-runtime 0.49.0 and replaces `post_selection`, which was deprecated in that release and is rejected in 0.51.0.dev. `post_selection` could add checks only at the end of the learning circuits; `bit_flip_checks` can add them at the start (`pre_circuit`), the end (`post_circuit`), or both. The option model was validated locally; `NoiseLearnerV3` itself does not run in local mode.

## Validation

There is no local check of the benefit: Aer noise models are Markovian. Under FakeKingston noise, a 3-qubit circuit with `rx` checks kept 55% of shots with node pre+post and 98% with edge. That reflects only readout and gate errors on the check pulses, so filtering on it means nothing for this technique. A local run is still useful as a plumbing check. Without noise, every shot must pass every check, including on a twirled samplomatic template; if any fail, the checks are wired wrongly.

On hardware, run with all four checks and compare strategies on the same data, as in the guide. Compare each strategy's estimate with its kept fraction, and include the raw circuit run without checks in the same program. A strategy is worth using only if it beats that raw circuit at an affordable kept fraction. Where possible, use a circuit with a known answer (a mirror circuit) for the comparison.

**Dynamic circuits.** On a 3-qubit circuit with a mid-circuit measurement and an `if_else`, the four passes added `mid_pre` and `mid_ps` alongside `meas_pre` and `meas_ps`, kept the `if_else`, and every shot passed in a noiseless client-side Sampler run. Note that on the Executor, samplomatic boxing rejects dynamic circuits (SKILL.md Step 4a), so a dynamic circuit there uses post-selection without twirling or `qiskit-mitigation` tasks.

## Composability

Post-selection removes shots before the expectation value or distribution is formed, so it stacks with any technique that post-processes per-shot data. Documented stacks:
- **PEC+SLC:** the tutorial post-selects on the spectator and post-circuit checks and passes the mask to `executor_expectation_values`.
- **PNA:** the tutorial post-selects the same way.
- **TREX:** applied as rescale factors on the post-selected result, in the same `executor_expectation_values` call.
- **Twirling:** gate and measurement twirling are compatible. A noiseless run of a twirled template with checks keeps every shot.
- **ZNE (gate folding or PEA) and PEC through `qiskit-mitigation`:** compatible, but `task.postprocess` takes no post-selection mask. Add the checks to each program item's template circuit after `task.prepare`, build the mask with `PostSelector`, and compute the expectation values with `executor_expectation_values(..., postselect_mask=mask)`. For ZNE, do this per noise factor and then extrapolate; for PEC, also pass the PEC signs and gamma, as the PEC+SLC page does.

```python
from qiskit_mitigation import MitigationTask
from qiskit_mitigation.utils.expectation_values import executor_expectation_values

task = MitigationTask()                      # or GateFolding / PEA / PEC
program = task.prepare(isa_circuit, observables, parameters)
item = program.items[0]
item.circuit = generate_preset_pass_manager(optimization_level=0, backend=backend).run(
    checks_pm.run(item.circuit))             # checks_pm: the PassManager from step 1
result = Executor(backend).run(program).result()[0]

mask = PostSelector.from_circuit(item.circuit, backend.coupling_map).compute_mask(result, "node", mode="both")
evs = executor_expectation_values(
    result["_meas"], (observables, task.meas_bases), meas_basis_axis=1, avg_axis=0,
    measurement_flips=result.get("measurement_flips._meas"),
    postselect_mask=mask,
)
```

  `qiskit-mitigation` measures into its own `_meas` register, so the checks add `_meas_pre` and `_meas_ps`. Checked with a plain `MitigationTask` on a noiseless 5-qubit fake backend: every shot passed, and the masked value matched `task.postprocess`. The ZNE, PEA and PEC variants were not run.

On the client-side Sampler, a noiseless local run with `enable_gates` and `enable_measure` also kept every shot. `rx` checks need a fractional-gate backend. The client-side Sampler and samplomatic twirl RX-only fractional circuits (`pauli-twirling.md`, "Fractional gates"), but the `rx` check pairing with twirling was not run, so check it on hardware. With Sampler gate twirling, use `xslow` checks, which need no fractional gates. On the Executor, the checks are added after samplomatic's twirling, so they are not twirled. Combinations with M3 or dynamical decoupling are untested and undocumented.
