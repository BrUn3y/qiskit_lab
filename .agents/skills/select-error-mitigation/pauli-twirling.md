---
title: Pauli Twirling (gate twirling)
description: Noise-tailoring technique that converts arbitrary two-qubit gate noise into a Pauli channel by sandwiching gates with randomly chosen single-qubit Pauli operations.

capability_id: pauli-twirling
name: "Pauli Twirling (gate twirling)"
category: error-suppression
short_description: Converts arbitrary gate noise into a Pauli channel, reducing coherent noise accumulation and improving effectiveness of ZNE and PEC.

primitive_estimator: true
primitive_sampler: true
primitive_executor: true
output_type: any
estimate_bias: not-applicable

overhead_class: low
overhead_detail: "Requires running num_randomizations circuit instances (default: auto-set from shots). Total shots = num_randomizations × shots_per_randomization."
requires_noise_learning: false
requires_hardware: true

resilience_level_activation: null
api_class: "qiskit_ibm_runtime.options.TwirlingOptions"
api_guide: "https://quantum.cloud.ibm.com/docs/en/api/qiskit-ibm-runtime/options-twirling-options.md"

use_when:
  - "Coherent noise from two-qubit gates is a significant noise source on the target backend"
  - "Combining with ZNE or PEC, both of which assume or benefit from Pauli-channel noise"
  - "Circuit uses standard Clifford two-qubit gates (CNOT, ECR, CZ)"
  - "Estimator at resilience_level 2 (gate twirling is automatically enabled)"
  - "Sampler workflow where noise tailoring is beneficial before custom post-processing"

avoid_when:
  - "Circuit uses non-Clifford two-qubit gates (Pauli twirling is undefined for these)"
  - "Circuit uses fractional RZZ gates with the server-side EstimatorV2/SamplerV2, which can't twirl them. The client-side Estimator/Sampler and the Executor can, with twirling.group=\"local_pauli\" (relatively untested; see \"Fractional gates\")"
  - "Circuit uses fractional RX gates with the server-side EstimatorV2/SamplerV2 (qiskit-ibm-runtime < 0.50.0), which reject any fractional gate with gate twirling. The client-side Estimator/Sampler and the Executor (samplomatic) twirl RX-only fractional circuits"
  - "Circuit uses stretches and twirling is set through the Estimator or Sampler options (incompatible). With samplomatic on the Executor, stretches can be added to the template circuit after twirling"
  - "Executor workload with a dynamic circuit (mid-circuit measurement with conditional operations): samplomatic twirling does not support dynamic circuits"
  - "Measurement twirling with a circuit that uses the store instruction (incompatible)"
  - "Simulator without coherent noise (no benefit)"
  - "Circuit has many sequential entangling layers and the default strategy='active-accum' is used: it twirls every previously active qubit at every layer, and the added noisy gates can make results worse than no mitigation; use strategy='active' instead"

prerequisites:
  - "EstimatorV2, SamplerV2 or Executor primitive"
  - "Circuit uses only Clifford two-qubit gates, or fractional RZZ gates with twirling.group=\"local_pauli\" on the client-side Estimator/Sampler or the Executor (fractional RX single-qubit gates are allowed there with any group)"

compatible_with:
  - dynamical-decoupling
  - trex
  - zne-gate-folding
  - zne-pea
  - pec
  - m3
  - postselection-non-markovian
  - obp
incompatible_with:
  - stretches

notes_composability: >
  Gate twirling is a recommended companion to ZNE and PEC, which both perform
  better when gate noise is Pauli-channel structured. PEA (as a ZNE amplifier)
  requires gate twirling and enables it automatically when amplifier="pea" is set.
  Gate twirling is automatically enabled at Estimator resilience_level 2.

references:
  - "Hashim et al., Phys. Rev. Research 3, 013181 (2021)"
  - "Campbell, Phys. Rev. A 94, 052325 (2016)"

related_docs:
  - title: "Error mitigation and suppression techniques: Pauli twirling"
    url: "https://quantum.cloud.ibm.com/docs/en/guides/error-mitigation-and-suppression-techniques.md#pauli-twirling"
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
  - title: "TwirlingOptions API reference"
    url: "https://quantum.cloud.ibm.com/docs/en/api/qiskit-ibm-runtime/options-twirling-options.md"
    type: api-reference
---

## Summary

Pauli twirling is a noise-tailoring technique that converts arbitrary gate noise into a Pauli channel. It works by sandwiching each two-qubit gate with randomly chosen single-qubit Pauli gates so that the ideal gate operation is preserved, but the noise is averaged across the Pauli group. Because Pauli noise accumulates linearly with circuit depth (while coherent noise accumulates quadratically), twirling reduces the impact of coherent errors. It also improves the accuracy of ZNE and PEC, both of which assume Pauli-channel noise.

## When to use

- Coherent errors from two-qubit gates are a known noise source on the target backend — noise-tailoring them into a Pauli channel reduces quadratic accumulation to linear.
- Using ZNE or PEC: both techniques benefit from Pauli-channel noise structure, and twirling ensures this assumption holds in practice.
- Circuit uses standard Clifford two-qubit gates. The technique is only defined for operations in the Clifford group.
- For Estimator: gate twirling is automatically enabled at `resilience_level = 2`.

## When not to use

- Circuit uses non-Clifford two-qubit gates (twirling not defined for these gates).
- Circuit uses fractional RZZ gates with the server-side primitives. With the client-side primitives or the Executor, set `group="local_pauli"` (see below).
- Circuit uses fractional RX gates with the server-side `EstimatorV2`/`SamplerV2` (`qiskit-ibm-runtime < 0.50.0`).

### Fractional gates

The client-side Estimator and Sampler (`qiskit-ibm-runtime >= 0.50.0`) and the Executor (samplomatic) twirl circuits whose only fractional gates are `rx`, because `rx` is a single-qubit gate and doesn't change the twirled Clifford entanglers. A circuit with `rzz` fails at build time with the default twirling group: `BuildError: Non-Clifford and unbound fractional entanglers are only supported for Twirl with 'GroupMode LOCAL_PAULI'`. [`twirling.group="local_pauli"`](https://quantum.cloud.ibm.com/docs/en/api/qiskit-ibm-runtime/options-models-twirling-options#group) fixes it: it twirls each non-Clifford entangler with the Paulis that commute with it, and every other gate with the full Pauli group. On the Executor, pass `twirling_group="local_pauli"` to samplomatic's `generate_boxing_pass_manager` (or in a `qiskit-mitigation` task's `custom_boxing_options`). The server-side `EstimatorV2`/`SamplerV2` have no such option.

**Twirling with `rzz` is relatively untested.** The checks below confirm that the jobs build and run, not that the mitigation works: `local_pauli` twirls each `rzz` only with the Paulis that commute with it, so less of the noise is tailored into the Pauli channel that PEA and PEC assume. When recommending any technique that twirls `rzz`, warn the researcher in the output and suggest comparing against an unmitigated run before trusting the result.

Checked against qiskit-ibm-runtime 0.52.0, qiskit-mitigation 0.1.1 and samplomatic 0.21.0, on a 4-qubit circuit with 4 `rzz` and 4 `cx` gates (FakeManilaV2 with `rzz` and `rx` added to its target). With the default group, twirling, gate-folding ZNE, PEA and PEC all failed with the `BuildError` on the client-side Estimator, and `samplomatic.build` failed the same way. With `local_pauli`, twirling and gate-folding ZNE ran, and a noiseless twirled run matched the exact value (0.062 ± 0.009 against 0.065). PEA and PEC need more than this setting: their injected noise must commute with `rzz`, which on the Executor means `inject_noise_site="before"`, and which the client-side Estimator can't guarantee (see their "Fractional gates" sections).
- Simulator without coherent noise modeling (no benefit).
- There is less value when used in Sampler jobs, if there is no additional post-processing to reduce the erorr.

## Trade-offs

| Dimension | Value |
|---|---|
| Shot overhead | num_randomizations × shots_per_randomization (auto by default) |
| Circuit execution count | num_randomizations randomized instances |
| Estimate bias | Reduces coherent noise; converts to structured Pauli noise |
| Learning phase | None |
| Scales with circuit depth | Overhead is set by num_randomizations, not circuit depth |

## Configuration

```python
# Client-side Estimator (qiskit-ibm-runtime >= 0.50.0); checked against 0.50.0.
from qiskit_ibm_runtime.executor_estimator import Estimator

estimator = Estimator(mode=backend)
estimator.options.twirling.enable_gates = True
estimator.options.twirling.num_randomizations = 32
estimator.options.twirling.shots_per_randomization = 100
```

`strategy` controls which qubits are twirled in each layer:
- `"active-accum"` (default) — twirls all qubits that have appeared in gates up to the current layer
- `"active"` — twirls only qubits active in each individual layer
- `"active-circuit"` — twirls the union of all active qubits in the entire circuit
- `"all"` — twirls all qubits

The default `"active-accum"` adds Pauli gates on every qubit that has been active so far, at every layer. On a circuit whose entangling gates run one after another (for example `RealAmplitudes` with `entanglement="linear"`, a 99-layer CZ staircase at 100 qubits), those extra gates add enough noise to make results worse than no mitigation. `"active"` twirls only the qubits in each layer and avoids this. Check both strategies in local mode when the circuit has many sequential layers.

The strategy also changes how many unique layers PEA or PEC must learn when the first layers don't touch every qubit. On a 156-qubit heavy-hex Ising Trotter circuit with 3 coloring layers, `"active-accum"` gives 5 unique layers, because the first step's layers twirl fewer qubits, and `"all"` gives 3. With `qiskit-ibm-runtime >= 0.50.0`, check the count with `estimator.find_unique_layers(pubs)` after setting the PEA or PEC option.

### With the Executor

Checked against samplomatic 0.21.0 and qiskit-mitigation 0.1.1. Twirling is set when the circuit is boxed: samplomatic's boxing pass manager adds the twirl annotations, and `samplomatic.build` turns them into a template circuit and a samplex that draws the random Paulis. `qiskit-mitigation` tasks twirl by default, using the same boxing (pass `custom_boxing_options` to change it).

samplomatic twirling does not support dynamic circuits: the boxing pass manager rejects `if_else` (`TranspilerError: 'if_else' is not supported` in samplomatic 0.21.0), and so does every `qiskit-mitigation` task, since they box with it.

```python
import samplomatic
from samplomatic.transpiler import generate_boxing_pass_manager

boxed_circuit = generate_boxing_pass_manager(
    enable_gates=True,             # twirl two-qubit gate layers
    enable_measures=True,          # twirl measurements
    twirling_strategy="active",
).run(isa_circuit)
template_circuit, samplex = samplomatic.build(boxed_circuit)
```

samplomatic spells the strategies with underscores (`"active"`, `"active_accum"`, `"active_circuit"`, `"all"`) and defaults to `"active_circuit"`, unlike the Estimator's `"active-accum"`. The warning above about accumulating strategies on sequential circuits applies to `"active_accum"` too.

## Composability

Gate twirling is a prerequisite for PEA and is automatically enabled when `amplifier="pea"` is set. Strongly recommended alongside ZNE and PEC. Compatible with dynamical decoupling and TREX. When DD is added by hand (for example on the Executor), apply it after twirling; see `dynamical-decoupling.md`. Fractional RX gates work on the client-side Estimator/Sampler and the Executor, not on the server-side primitives. Fractional RZZ gates need `group="local_pauli"` on the same primitives (relatively untested), and PEA and PEC with RZZ also need the Executor (see their pages); other non-Clifford entanglers are not twirled. Incompatible with stretches when set through the Estimator or Sampler options; with samplomatic on the Executor, stretch-based DD can be added to the template circuit after twirling (see `dynamical-decoupling.md`). With the Estimator or Sampler options, gates inside conditional blocks of a dynamic circuit are not twirled, and measurement twirling applies only to terminal measurements. On the Executor, samplomatic twirling does not support dynamic circuits.
