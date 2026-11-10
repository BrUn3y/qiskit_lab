---
title: Probabilistic Error Cancellation (PEC)
description: Returns an unbiased estimate of the expectation value by expressing the ideal circuit output as a linear combination of noisy circuits, at the cost of exponential shot overhead scaling with circuit depth.

capability_id: pec
name: "Probabilistic Error Cancellation (PEC)"
category: expectation-value-mitigation
short_description: Returns an unbiased expectation value estimate by sampling from a quasi-probability distribution of noisy circuit instances that together reconstruct the ideal circuit output.

primitive_estimator: true
primitive_sampler: false
primitive_executor: true
output_type: expectation-value
estimate_bias: unbiased

overhead_class: exponential
overhead_detail: "Sampling overhead scales as γ², where γ (the quasi-probability overhead) scales exponentially with circuit depth. Default max_overhead cap is 100; exceeding the cap reduces result precision rather than increasing shots. As a practical reference point, circuit volume around depth 12 on 50 qubits (~300 two-qubit gates) is close to the current state of the art for full PEC."
requires_noise_learning: true
requires_hardware: true

resilience_level_activation: null
api_class: "qiskit_ibm_runtime.options.PecOptions"
api_guide: "https://quantum.cloud.ibm.com/docs/en/guides/error-mitigation-and-suppression-techniques.md#pec"

use_when:
  - "An unbiased expectation value estimate is required (PEC is the only technique that returns an unbiased result)"
  - "Circuit depth is moderate; sampling overhead γ² is manageable within the shot budget (depth ~12 on 50 qubits, ~300 two-qubit gates, is close to the current practical ceiling)"
  - "High accuracy is the primary goal and shot budget can accommodate exponential overhead"
  - "Research context where bias elimination is a hard requirement"
  - "Mitigation must remain valid for arbitrary observables and circuit parameters — PEC's sampling cost does not depend on observable weight or circuit parameterization, unlike PEC+SLC, PNA, or OBP, which require observable-specific classical preprocessing"
  - "Many observables will be evaluated against the same circuit — PEC's cost is independent of observable count, whereas per-observable classical preprocessing (PEC+SLC, PNA, OBP) scales with it"

avoid_when:
  - "Circuit depth is large; γ² grows exponentially with depth and can exceed practical shot budgets"
  - "Shot budget is limited; PEC requires significantly more shots than ZNE for the same circuit"
  - "Gate-folding ZNE or PEA is already enabled in the same job (incompatible)"
  - "Circuit uses fractional RZZ gates on the Estimator (server-side or client-side): noise injection fails on RZZ there. The Executor with qiskit-mitigation works with twirling_group=\"local_pauli\" and inject_noise_site=\"before\" (relatively untested; see \"Fractional gates\"). Fractional RX gates are fine on the client-side Estimator and the Executor"
  - "SamplerV2 primitive"
  - "max_overhead cap will be hit; exceeding the cap silently reduces precision rather than increasing job cost"
  - "Device noise is not well described by a sparse, geometrically-local Pauli-Lindblad model (significant long-range or weight-≥3 correlated noise), which biases the learned inversion"

prerequisites:
  - "EstimatorV2 primitive, or the Executor primitive with qiskit-mitigation (pip install qiskit-mitigation)"
  - "Hardware backend"
  - "ISA circuit whose two-qubit gates are Clifford, or fractional RZZ on the Executor with twirling_group=\"local_pauli\" and inject_noise_site=\"before\"; fractional RX gates are allowed"
  - "Shot budget large enough to achieve target precision given expected γ²"

compatible_with:
  - dynamical-decoupling
  - trex
  - pauli-twirling
  - postselection-non-markovian
  - obp
incompatible_with:
  - zne-gate-folding
  - zne-pea
  - pec-slc

notes_composability: >
  PEC cannot be combined with any ZNE variant (gate folding or PEA) in the same job.
  Pauli twirling is compatible and recommended; PEC performs better when gate noise
  is Pauli-channel structured. TREX is compatible as the measurement-error component.
  Dynamical decoupling is compatible.

references:
  - "K. Temme et al., Physical Review Letters 119, 180509 (2017)"
  - "E. van den Berg et al., Nature Physics 19, 1116–1121 (2023), arXiv:2201.09866 (sparse Pauli-Lindblad model + PEC)"

related_docs:
  - title: "Error mitigation and suppression techniques: PEC"
    url: "https://quantum.cloud.ibm.com/docs/en/guides/error-mitigation-and-suppression-techniques.md#pec"
    type: guide
  - title: "Noise learning"
    url: "https://quantum.cloud.ibm.com/docs/en/guides/noise-learning.md"
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
  - title: "PecOptions API reference"
    url: "https://quantum.cloud.ibm.com/docs/en/api/qiskit-ibm-runtime/options-pec-options.md"
    type: api-reference
  - title: "ResilienceOptionsV2 API reference"
    url: "https://quantum.cloud.ibm.com/docs/en/api/qiskit-ibm-runtime/options-resilience-options-v2.md"
    type: api-reference
---

## Summary

Probabilistic Error Cancellation expresses the output of the ideal target circuit as a linear combination of noisy circuits that are implementable on hardware:

```
O_ideal = Σᵢ ηᵢ · O_noisy,i
```

The ideal expectation value is recovered by executing randomly sampled noisy circuit instances according to the quasi-probability distribution defined by the coefficients ηᵢ. Because some coefficients are negative, the distribution is quasi-probabilistic; the result is still unbiased, but the sampling overhead scales with γ = Σᵢ |ηᵢ|, which grows exponentially with circuit depth. The overhead on the number of shots required is proportional to γ². PEC requires a noise model. The legacy server-side Estimator learned it automatically; the client-side Estimator (qiskit-ibm-runtime >= 0.50.0) needs it learned in a separate `NoiseLearnerV3` job (see Configuration). Unlike ZNE, PEC returns an unbiased estimate — but this guarantee comes at a significantly higher cost.

The unbiasedness guarantee is conditional on the learned noise model being faithful. Runtime PEC learns the same **sparse Pauli-Lindblad model** as PEA (van den Berg et al., Nat. Phys. 19, 2023): a Pauli channel whose generators are the weight-1 Paulis and the weight-2 Paulis on **coupling-map-adjacent** qubit pairs, assuming gate noise "can be expected to have limited range and therefore be negligible beyond some local neighborhood." Twirling is what makes this hold — it converts each layer's physical channel into the Pauli channel the model represents and inverts. Where the real device carries significant **long-range or weight-≥3 correlated noise** outside that generator set, the model cannot represent it and the "unbiased" inversion picks up a model-mismatch bias; the technique's own error bound assumes the channel is representable by the model's Pauli set. This is why PEC is paired with Pauli twirling and applied to layers of self-inverse two-qubit Clifford gates, where the assumption is most defensible.

## When to use

- An unbiased expectation value estimate is a hard requirement. PEC is the only built-in Runtime technique that returns an unbiased result.
- Circuit depth is moderate and γ² remains within a practical shot budget. For shallow circuits, PEC's overhead is manageable. As a reference point, depth ~12 on 50 qubits (~300 two-qubit gates) is close to the current practical ceiling for full PEC.
- Research applications where bias elimination is more important than shot efficiency.
- The workload needs to stay valid across arbitrary observables and circuit parameters, or needs to evaluate many observables against the same circuit. PEC's sampling cost is independent of observable weight and observable count, unlike techniques that build an observable-specific classical artifact (PEC+SLC, PNA, OBP).

## When not to use

- Deep circuits. γ scales exponentially with depth, and γ² can easily exceed practical shot budgets past roughly depth 12 on 50 qubits (~300 two-qubit gates). For utility-scale circuits, ZNE (with gate folding or PEA) is the standard approach, or PEC+SLC (see `pec-slc.md`) if remaining closer to unbiased matters and classical compute is available.
- Limited shot budget. PEC requires substantially more shots than ZNE to achieve the same precision target.
- The `max_overhead` cap will be hit. When γ² exceeds `max_overhead` (default: 100), the service limits the overhead rather than increasing the shot count, which silently reduces result precision rather than explicitly failing. If the cap will be binding, evaluate whether ZNE is more appropriate.
- Gate-folding ZNE or PEA is enabled in the same job.
- Circuit uses fractional RZZ gates on the Estimator (see "Fractional gates" below; fractional RX is fine; RZZ works only on the Executor, with `twirling_group="local_pauli"` and `inject_noise_site="before"`).
- Only a small, fixed set of observables is needed and some tunable bias is acceptable. PEC+SLC applies an accuracy budget to reduce sampling overhead in this case at lower classical cost than treating every observable generically.

## Trade-offs

| Dimension | Value |
|---|---|
| Shot overhead | γ², where γ scales exponentially with circuit depth |
| Circuit execution count | Many noisy circuit instances drawn from quasi-probability distribution |
| Estimate bias | Unbiased (guaranteed zero-bias with respect to gate errors and the noise model) |
| Learning phase | Yes (Pauli–Lindblad noise model learning, similar to PEA; about 1 minute of QPU time per unique layer at the default options, see SKILL.md Phase 1.5) |
| Scales with circuit depth | Exponential overhead; practical only for moderate-depth circuits |

### Fractional gates

PEC works with fractional `rx` gates with any twirling group, because `rx` is a single-qubit gate and leaves the twirled entanglers unchanged. With fractional `rzz`, a non-Clifford entangler, the default group fails at build time with `BuildError: Non-Clifford and unbound fractional entanglers are only supported for Twirl with 'GroupMode LOCAL_PAULI'`. `local_pauli` twirling fixes the build, but PEC also injects noise after each layer by default. A sampled noise Pauli that doesn't commute with `rzz` can't be propagated through it, and sampling fails with `SamplexRuntimeError: Pauli values not in the commutant of 'rzz' cannot be propagated`. Whether a run hits this is random: it passed with small rates and few randomizations, and failed with realistic ones. So:
- **Executor (`qiskit-mitigation`):** pass `twirling_group="local_pauli"` and `inject_noise_site="before"` in the task's `custom_boxing_options`. This ran reliably.
- **Client-side Estimator:** `twirling.group = "local_pauli"` is not enough, and the Estimator options have no setting for the injection site. Treat PEC with `rzz` as unsupported there; move the workload to the Executor.
- **Server-side `EstimatorV2`:** no `group` option; unsupported.

Whether `NoiseLearnerV3` learns a model that matches `inject_noise_site="before"` is untested.

**Twirling with `rzz` is relatively untested.** The checks below confirm that the jobs build and run, not that the mitigation works: `local_pauli` twirls each `rzz` only with the Paulis that commute with it, so less of the noise is tailored into the Pauli channel that PEA and PEC assume. When recommending any technique that twirls `rzz`, warn the researcher in the output and suggest comparing against an unmitigated run before trusting the result.

Checked against qiskit-ibm-runtime 0.52.0, qiskit-mitigation 0.1.1 and samplomatic 0.21.0, on a 5-qubit `rx` + `cx` circuit on FakeManilaV2 with `rx` added to its target, and on a 4-qubit circuit with 4 `rzz` and 4 `cx` gates. PEC ran end to end with a hand-built `PauliLindbladMap` per unique layer (the `generate_random_pauli_lindblad_noise` pattern in the [PEC with TREX guide](https://quantum.cloud.ibm.com/docs/en/addons/qiskit-mitigation/guides/pec-with-trex)), passed as `resilience.layer_noise_model` on the Estimator and as `noise_maps` to the `qiskit-mitigation` task on an `AerSimulator` Executor. Replacing two `cx` with `rzz` failed on both with the default group. With `local_pauli`, the Estimator ran only when the noise model's rates were small (3e-3, 32 randomizations) and failed with the `SamplexRuntimeError` at higher rates (0.3) or 1024 randomizations; the Executor with `inject_noise_site="before"` ran at rate 0.3 and 1024 randomizations. A hand-built map checks only that the job builds and runs; it says nothing about how well the technique works, which needs a model learned on hardware.

## Configuration

```python
# Client-side Estimator (qiskit-ibm-runtime >= 0.50.0); checked against 0.50.0.
from qiskit_ibm_runtime.executor_estimator import Estimator

from qiskit_ibm_runtime import NoiseLearnerV3

estimator = Estimator(mode=backend)
estimator.options.resilience.pec_mitigation = True
estimator.options.resilience.pec.max_overhead = 100  # default; limits sampling overhead

# The client-side Estimator does not learn noise for PEC on its own: learn it in a
# separate NoiseLearnerV3 job and pass it in. Set pec_mitigation first;
# find_unique_layers returns no layers otherwise.
layers = estimator.find_unique_layers(pubs)
learner_result = NoiseLearnerV3(backend).run(layers).result()
estimator.options.resilience.layer_noise_model = zip(layers, learner_result.to_pauli_lindblad_maps())
job = estimator.run(pubs)
```

The `max_overhead` option caps the sampling overhead. If γ² exceeds this value, the precision target is relaxed rather than the shot count increased. Setting `max_overhead = None` removes the cap. Pauli twirling is recommended alongside PEC to ensure Pauli-channel noise structure:

```python
estimator.options.twirling.enable_gates = True
```

### With the Executor (qiskit-mitigation)

Checked against qiskit-mitigation 0.1.1. `learned_noise` maps each `InjectNoise` reference to its learned `PauliLindbladMap`, for the layers `task.find_unique_layers(circuit, boxing_options)` returns with an `InjectNoise` annotation (not the measurement layer). The guide learns it with `qiskit-noise-learning`. By default the number of randomizations is scaled by about γ² (`scale_randomizations_by_gamma=True`), capped by `max_sampling_overhead`; read `task.gamma` after `prepare` to check the overhead before running. Pass `trex=TREX()` to stack TREX, as in the [PEC with TREX guide](https://quantum.cloud.ibm.com/docs/en/addons/qiskit-mitigation/guides/pec-with-trex).

```python
from qiskit_ibm_runtime import Executor
from qiskit_mitigation import PEC

task = PEC()
program = task.prepare(
    circuit, observables, parameters,
    noise_maps=learned_noise, noise_gain=0, max_sampling_overhead=100,
    num_randomizations=200, shots_per_randomization=16,
)
print(f"sampling overhead ~{task.gamma ** 2:.1f}")
result = task.postprocess(Executor(backend).run(program).result())
```

## Composability

PEC cannot be combined with any ZNE variant (gate-folding or PEA) in the same job. Pauli twirling is compatible and recommended (PEC's noise model assumes Pauli-channel noise). TREX is compatible as the measurement-error component. Dynamical decoupling is compatible. For utility-scale circuits where PEC overhead is prohibitive, ZNE with PEA is the recommended alternative, or PEC+SLC (`pec-slc.md`) if a near-unbiased estimate is still preferred and classical compute is available to compute lightcone bounds. PEC+SLC replaces PEC rather than stacking with it. Stacking PEC with PNA is undocumented and would likely over-correct, since both invert the same learned noise.
