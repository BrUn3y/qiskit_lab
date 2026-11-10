---
title: Zero-Noise Extrapolation with gate folding
description: Estimates the zero-noise expectation value by running circuits at amplified noise levels using gate folding, then extrapolating the results to zero noise.

capability_id: zne-gate-folding
name: "Zero-Noise Extrapolation with gate folding"
category: expectation-value-mitigation
short_description: Amplifies noise by repeating two-qubit gates and their inverses, then extrapolates across noise levels to estimate the zero-noise expectation value.

primitive_estimator: true
primitive_sampler: false
primitive_executor: true
output_type: expectation-value
estimate_bias: reduced-bias

overhead_class: medium
overhead_detail: "~3× shot overhead at default noise_factors=(1, 3, 5). Overhead scales linearly with the number of noise factors."
requires_noise_learning: false
requires_hardware: true

resilience_level_activation: 2
api_class: "qiskit_ibm_runtime.options.ZneOptions"
api_guide: "https://quantum.cloud.ibm.com/docs/en/guides/error-mitigation-and-suppression-techniques.md#zne"

use_when:
  - "Estimating Pauli observable expectation values on hardware, with EstimatorV2 or the Executor"
  - "Noise scales predictably with circuit depth (gate folding assumption holds)"
  - "Circuit's two-qubit gates are Clifford gates that folding amplifies (CZ, ECR, CX, CY, SWAP); fractional RX gates elsewhere in the circuit are fine"
  - "Shot budget allows approximately 3× overhead at default settings"
  - "A biased but improved estimate is acceptable (ZNE is not guaranteed zero-bias)"
  - "Circuit scale is moderate; gate folding is appropriate up to utility-scale when PEA overhead is not justified"

avoid_when:
  - "Most of the two-qubit error comes from fractional RZZ gates: folding only folds CZ, ECR, CX, CY and SWAP, so RZZ noise is not amplified and the extrapolation under-corrects"
  - "Utility-scale circuits with complex noise structure where gate folding amplification is inaccurate (use ZNE+PEA instead)"
  - "An unbiased estimate is required (use PEC instead)"
  - "PEC is also enabled in the same job (incompatible)"
  - "PEA is also enabled as the ZNE amplifier (pick one amplifier; incompatible)"
  - "Little of the observable's signal survives the unmitigated circuit (high-weight observables on a deep circuit): the folded circuits at noise factors 3 and 5 retain almost none, and the extrapolation is unstable and can be worse than TREX alone"
  - "SamplerV2 primitive"

prerequisites:
  - "EstimatorV2 primitive, or the Executor primitive with qiskit-mitigation (pip install qiskit-mitigation)"
  - "Hardware backend"
  - "With any fractional gates on the server-side EstimatorV2 (< 0.50.0): gate twirling disabled (`twirling.enable_gates = False`), because it doesn't support them and resilience_level 2 turns it on. On the client-side Estimator or the Executor, fractional RX gates twirl with any group, and fractional RZZ gates need `twirling.group = \"local_pauli\"` (relatively untested; see pauli-twirling.md, \"Fractional gates\")"

compatible_with:
  - dynamical-decoupling
  - pauli-twirling
  - trex
  - postselection-non-markovian
  - obp
incompatible_with:
  - zne-pea
  - pec

notes_composability: >
  ZNE with gate folding is included at resilience_level 2 alongside TREX and gate
  twirling. Gate twirling is recommended as a companion because ZNE performs better
  with Pauli-channel noise. Cannot be used in the same job as PEC or PEA.
  Gate folding works with fractional gates. On the client-side Estimator and the
  Executor, gate twirling works with fractional RX gates, and with RZZ when
  twirling.group is "local_pauli" (relatively untested). On the server-side
  EstimatorV2 it works with neither; set the options explicitly and leave gate
  twirling off (see pauli-twirling.md, "Fractional gates").

references:
  - "Z. Cai, npj Quantum Inf 7, 80 (2021)"

related_docs:
  - title: "Error mitigation and suppression techniques: ZNE"
    url: "https://quantum.cloud.ibm.com/docs/en/guides/error-mitigation-and-suppression-techniques.md#zne"
    type: guide
  - title: "Overview of noise management techniques"
    url: "https://quantum.cloud.ibm.com/docs/en/guides/error-mitigation-overview.md"
    type: guide
  - title: "Configure noise management with Estimator"
    url: "https://quantum.cloud.ibm.com/docs/en/guides/estimator-noise-management.md"
    type: guide
  - title: "Specify Estimator options"
    url: "https://quantum.cloud.ibm.com/docs/en/guides/estimator-options.md"
    type: guide
  - title: "Combine error mitigation options with the Estimator primitive"
    url: "https://quantum.cloud.ibm.com/docs/en/tutorials/combine-error-mitigation-techniques.md"
    type: tutorial
  - title: "ZneOptions API reference"
    url: "https://quantum.cloud.ibm.com/docs/en/api/qiskit-ibm-runtime/options-zne-options.md"
    type: api-reference
  - title: "ResilienceOptionsV2 API reference"
    url: "https://quantum.cloud.ibm.com/docs/en/api/qiskit-ibm-runtime/options-resilience-options-v2.md"
    type: api-reference
  - title: "Visualize ZNE expectation values"
    url: "https://quantum.cloud.ibm.com/docs/en/api/qiskit-ibm-runtime/visualization-draw-zne-evs.md"
    type: api-reference
  - title: "Visualize ZNE extrapolators"
    url: "https://quantum.cloud.ibm.com/docs/en/api/qiskit-ibm-runtime/visualization-draw-zne-extrapolators.md"
    type: api-reference
---

## Summary

Zero-noise extrapolation (ZNE) estimates the ideal expectation value of an observable by running the circuit at multiple amplified noise levels and extrapolating to the zero-noise limit. With gate folding, noise is amplified by replacing two-qubit gates with equivalent longer sequences: for example, a unitary U is replaced by U·U†·U, which tripling the noise at that gate. The circuit is executed at each specified noise factor (by default 1, 3, and 5), and the expectation values are fit to a functional form (exponential by default) and extrapolated to noise factor 0. ZNE reduces bias from gate errors but does not produce an unbiased estimate; it is not guaranteed to reach zero-bias. Only CZ, ECR, CX, CY and SWAP gates are folded, so circuits with fractional gates can still use it: fractional RX and RZZ gates are left as they are.

## When to use

- Noise on the target backend scales predictably with circuit depth, which is generally true for IBM Quantum hardware when gate folding is used.
- The circuit's two-qubit gates are Clifford gates that folding amplifies (CZ, ECR, CX, CY, SWAP). Fractional RX gates elsewhere in the circuit don't prevent folding.
- A moderately improved, biased estimate is sufficient. ZNE typically reduces bias significantly and is cost-effective at ~3× overhead with default settings.
- Gate twirling is also enabled (recommended): ZNE is more accurate when gate noise is Pauli-channel structured.

## When not to use

- Most of the two-qubit error comes from fractional RZZ gates. They are not folded, so their noise is not amplified and the extrapolation under-corrects.
- Utility-scale circuits (large qubit count, deep layers) where gate folding amplification may be inaccurate due to complex noise structure. In this case, PEA provides more accurate amplification via noise learning.
- An unbiased estimate is required for the application (use PEC instead).
- PEC or PEA is already enabled in the same job.

## Trade-offs

| Dimension | Value |
|---|---|
| Shot overhead | ~3× at default noise_factors=(1, 3, 5); scales linearly with number of noise factors |
| Circuit execution count | One per noise factor (3 by default) |
| Estimate bias | Reduced but not eliminated; biased estimator |
| Learning phase | None |
| Scales with circuit depth | Amplification accuracy may degrade for very deep circuits; switch to PEA for utility-scale |

## Configuration

```python
# Client-side Estimator (qiskit-ibm-runtime >= 0.50.0); checked against 0.50.0.
from qiskit_ibm_runtime.executor_estimator import Estimator

# Option 1: resilience_level (recommended; enables ZNE + TREX + gate twirling)
estimator = Estimator(mode=backend, options={"resilience_level": 2})

# Option 2: explicit
estimator = Estimator(mode=backend)
estimator.options.resilience.zne_mitigation = True
estimator.options.resilience.zne.noise_factors = [1, 3, 5]
estimator.options.resilience.zne.extrapolator = "exponential"

# Option 3: circuit with fractional RZZ gates (backend loaded with use_fractional_gates=True).
# resilience_level 2 turns on gate twirling, which fails on RZZ with the default group;
# "local_pauli" twirls RZZ (relatively untested). With only fractional RX gates, the
# default group twirls them, so resilience_level 2 works unchanged.
estimator = Estimator(mode=backend, options={"resilience_level": 2})
estimator.options.twirling.group = "local_pauli"
# On the server-side EstimatorV2, which has no group option, turn twirling off instead:
# estimator.options.twirling.enable_gates = False
```

Only CZ, ECR, CX, CY and SWAP gates are folded. Fractional RX and RZZ gates pass through unchanged, so their noise stays at noise factor 1 in every folded circuit.

IBM's feature-compatibility table says gate folding might not work when the circuit uses custom gates. For such a circuit, run the folded job in local mode on a fake backend first (`scripts/verify_c1.py` or `verify_c2.py` with the `zne` configuration) to confirm it builds and returns sensible per-noise-factor values.

**Extrapolator options** (single value or ordered list; first successful fit is used):
`"exponential"` (default), `"linear"`, `"double_exponential"`, `"polynomial_degree_1"` through `"polynomial_degree_7"`, `"fallback"` (returns lowest-noise-factor raw value without fitting).

**Amplifier options** (this page: gate folding variants):
- `"gate_folding"` (default) — gates chosen randomly from the circuit
- `"gate_folding_front"` — gates chosen from the topological front of the circuit
- `"gate_folding_back"` — gates chosen from the topological back of the circuit

### With the Executor (qiskit-mitigation)

Checked against qiskit-mitigation 0.1.1. `GateFolding` folds whole layers (the layer, its inverse, the layer again) and twirls by default. `postprocess` tries the extrapolators in order and returns the first physically valid one; `"fallback"` returns the lowest-noise-factor value, and `"custom"` with `custom_fit` takes a user fitting function. Post-processing can be repeated with other extrapolators without re-running. See the [gate folding guide](https://quantum.cloud.ibm.com/docs/en/addons/qiskit-mitigation/guides/gate-folding-with-custom-extrapolation).

```python
from qiskit_ibm_runtime import Executor
from qiskit_mitigation import GateFolding

task = GateFolding()
program = task.prepare(circuit, observables, parameters, noise_factors=[1, 3, 5])
result = task.postprocess(Executor(backend).run(program).result(), extrapolator=["exponential", "linear"])
```

## Choosing between gate folding and PEA

Gate folding vs. PEA is the classic grey area for a utility-scale Estimator stack (both are ZNE amplifiers; only one can be active). The decision matrix leans on `use_when`/`avoid_when` — folding for cost, PEA for amplification accuracy at scale. When the choice is close, verify it empirically using the fair-comparison protocol in `verification.md` ("Comparing ZNE amplifiers fairly"), which controls for the different extrapolation grids. When PEA and folding reach a similar error, folding is the cheaper choice (no noise-learning phase), which is usually decisive for a cost-effective goal.

## Composability

ZNE with gate folding is compatible with TREX (recommended: TREX handles readout errors, ZNE handles gate errors) and with dynamical decoupling. Gate twirling is recommended alongside ZNE to ensure Pauli-channel noise structure. Cannot be used with PEC or PEA in the same job. Stacking with PNA or PEC+SLC is undocumented: they correct the same learned gate noise, so the combination would likely over-correct and is untested. Gate folding works with fractional gates, but gate twirling does not, so with fractional gates turn gate twirling off (Configuration, Option 3). For utility-scale workloads where gate folding amplification is inaccurate, switch the amplifier to `"pea"` (see the `zne-pea` capability page).
