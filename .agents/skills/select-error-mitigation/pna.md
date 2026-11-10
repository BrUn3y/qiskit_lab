---
title: Propagated Noise Absorption (PNA)
description: Mitigates gate errors in expectation value estimation by classically propagating the inverse of a learned Pauli-Lindblad noise channel through the observable using Pauli propagation, producing a noise-mitigating observable that is measured directly on hardware.

capability_id: pna
name: "Propagated Noise Absorption (PNA)"
category: expectation-value-mitigation
short_description: Absorbs the inverse of a learned gate noise channel into the measured observable via classical Pauli propagation, eliminating QPU sampling overhead at the cost of a more complex observable and bounded residual bias from truncation.

primitive_estimator: false
primitive_sampler: false
primitive_executor: true
output_type: expectation-value
estimate_bias: reduced-bias

overhead_class: medium
overhead_detail: "No QPU sampling overhead factor (γ²) — mitigation is entirely classical post-processing. Classical cost is substantial: Pauli propagation scales as O(2^N) terms where N is the number of Pauli rotation gates, truncated via max_err_terms and max_obs_terms. Shot count increases with the number of Pauli terms in the noise-mitigating observable (O̊). Noise learning on QPU (NoiseLearnerV3) is required before the main execution. Residual bias from truncation depends on max_err_terms and max_obs_terms settings."
requires_noise_learning: true
requires_hardware: true

resilience_level_activation: null
api_class: "qiskit_addon_pna.generate_noise_mitigating_observable"
api_guide: "https://qiskit.github.io/qiskit-addon-pna/"

use_when:
  - "Estimating expectation values of Pauli observables affected by 2-qubit gate noise on hardware"
  - "QPU sampling overhead (γ²) from PEC or PEC+SLC is prohibitive, and a purely classical mitigation of the noise channel is acceptable"
  - "The observable is local or sparse — a compact noise-mitigating observable O̊ can be produced by truncating small-coefficient terms without large accuracy loss"
  - "Pauli rotation gate depth (N) is moderate — classical propagation cost grows as O(2^N) in the worst case before truncation"
  - "A noise model has been or can be learned via NoiseLearnerV3 before the main circuit execution"
  - "Access to the Executor primitive (directed execution model) is available"
  - "Combining with TREX to address both gate and readout noise"
  - "Circuit topology is not a limiting factor — unlike TEM, PNA's classical cost is independent of problem topology (1D, 2D, or hardware-efficient mapping); cost is instead driven by gate count and observable size"
  - "Circuit is close to Clifford (few non-Clifford gates) — the noise-mitigating observable grows with fewer terms because operator entanglement does not grow, lowering both classical propagation cost and the number of measurement bases needed on hardware"

avoid_when:
  - "Circuit has very deep Pauli rotation stacks (large N), making classical propagation cost prohibitive even with aggressive truncation"
  - "Observable acts densely on many qubits and the noise-mitigating observable would require an impractically large number of measured terms (large max_obs_terms needed to retain accuracy)"
  - "Simple workflow is required; PNA involves circuit boxing with samplomatic, noise learning, Pauli propagation preprocessing, and the directed Executor execution model"
  - "An unbiased estimate is required; PNA introduces bounded but nonzero bias from truncation of the propagated observable and the anti-noise generators"
  - "The noise model is stale (more than ~4 hours old) and cannot be refreshed before execution"
  - "Circuit has many non-Clifford gates and classical propagation is already struggling (slow, or truncation error budgets are being exhausted) — consider ZNE-PEA (`zne-pea.md`) instead, since its cost does not depend on circuit magic"
  - "Many distinct observables need mitigation against the same circuit — the noise-mitigating observable is built per observable, so preprocessing cost scales with the number of observables; PEC (`pec.md`) is cheaper to keep generic across a large or changing observable set"

prerequisites:
  - "qiskit-addon-pna installed (pip install qiskit-addon-pna)"
  - "samplomatic installed (for circuit boxing pass manager and build)"
  - "qiskit-addon-utils installed (for post-processing utilities)"
  - "ISA circuit transpiled to the target backend"
  - "Circuit boxed with InjectNoise and Twirl annotations via samplomatic generate_boxing_pass_manager"
  - "Noise model learned via NoiseLearnerV3 and associated with circuit boxes as PauliLindbladMap objects"
  - "Hardware backend supporting the Executor primitive"
  - "generate_noise_mitigating_observable called within an if __name__ == '__main__' guard when using num_processes > 1"

compatible_with:
  - dynamical-decoupling
  - trex
  - postselection-non-markovian
incompatible_with: []

notes_composability: >
  PNA uses the Executor primitive (directed execution model) rather than
  EstimatorV2 options. TREX-style readout correction is the standard
  complement: learned measurement noise is applied as a post-processing
  rescaling via trex_factors from qiskit_addon_utils. Dynamical decoupling
  can be applied to the ISA circuit before boxing. The IBM docs document PNA
  only with TREX and post-selection. Stacking it with gate-folding ZNE, PEA, PEC
  or PEC+SLC is untested: all of them correct the same learned gate noise, so
  applying two to the same layers would likely over-correct.

references:
  - "Andrew Eddins et al., 'Computing noise-canceling observables via Pauli propagation', arXiv:2606.20441 [quant-ph] (2025)"
  - "Ewout van den Berg et al., 'Probabilistic error cancellation with sparse Pauli-Lindblad models on noisy quantum processors', arXiv:2201.09866 [quant-ph]"
  - "Sergei Filippov et al., 'Scalable tensor-network error mitigation for near-term quantum computing', arXiv:2307.11740 [quant-ph]"

related_docs:
  - title: "PNA addon documentation"
    url: "https://qiskit.github.io/qiskit-addon-pna/"
    type: external
  - title: "PNA tutorial: Improving expectation values with propagated noise absorption"
    url: "https://qiskit.github.io/qiskit-addon-pna/tutorials/01_generate_noise_mitigating_observable.html"
    type: tutorial
  - title: "Directed execution model"
    url: "https://quantum.cloud.ibm.com/docs/en/guides/directed-execution-model.md"
    type: guide
  - title: "Executor quickstart"
    url: "https://quantum.cloud.ibm.com/docs/en/guides/get-started-with-executor.md"
    type: guide
  - title: "Overview of noise management techniques"
    url: "https://quantum.cloud.ibm.com/docs/en/guides/error-mitigation-overview.md"
    type: guide
---

## Summary

Propagated Noise Absorption (PNA) mitigates 2-qubit gate errors by classically computing a noise-mitigating observable O̊ that encodes the inverse of the learned gate noise channel. Starting from each entangling layer, each Pauli anti-noise generator from the inverse Pauli-Lindblad noise channel is propagated forward through the remaining circuit and applied to the original observable. The result, O̊, is a modified observable that when measured against the noisy output state has the effect of canceling the learned gate noise. Unlike PEC, which implements the inverse noise channel by sampling it on the QPU, PNA implements it entirely as a classical pre-processing step — eliminating the QPU sampling overhead factor γ² at the cost of a more complex observable and bounded residual bias from truncation.

There are two sources of truncation bias: terms with small coefficients are dropped from each evolved anti-noise generator (controlled by `max_err_terms`), and terms are dropped from the growing noise-mitigating observable as it is built up (controlled by `max_obs_terms`). A third practical truncation applies when selecting how many terms from O̊ to actually measure on the QPU — measuring only the largest-coefficient terms trades some accuracy for a reduction in the number of required measurement bases.

How quickly O_tilde grows is not generally predictable analytically — it depends on the interplay of circuit magic, gate count, and observable structure. In practice, growth is determined empirically by running the propagation and inspecting the resulting term count before committing to QPU execution; circuits closer to Clifford tend to grow more slowly because operator entanglement does not grow, and cost is otherwise independent of problem topology (1D, 2D, or hardware-efficient mapping).

## When to use

PNA is the technique to consider when PEC or PEC+SLC sampling overhead is prohibitive and the circuit's Pauli structure allows for an efficient classical propagation. It is best suited to circuits with moderate Pauli rotation depth (the propagation cost grows exponentially in the number of Pauli rotation gates before truncation controls it) and to observables that are sparse enough that the noise-mitigating observable remains tractable with reasonable `max_obs_terms`. The technique pairs naturally with TREX: PNA addresses gate noise while TREX addresses readout noise, and the tutorial demonstrates this combination as the standard workflow.

PNA fits the directed execution model — circuit boxing with `samplomatic`, noise learning with `NoiseLearnerV3`, and execution via the `Executor` primitive — so it is appropriate when that workflow infrastructure is in place. It is not accessible through the standard EstimatorV2 resilience level interface.

Circuit topology does not directly determine feasibility: PNA's classical cost is independent of whether the circuit maps to a 1D, 2D, or hardware-efficient topology, unlike tensor-network approaches (TEM), which are largely restricted to 1D. Circuits close to Clifford are also a good fit, since operator entanglement does not grow during propagation, keeping O_tilde smaller and classical cost lower than for high-magic circuits.

## When not to use

Do not use PNA when an unbiased estimate is a hard requirement; truncation introduces bounded but nonzero bias, and it does not have a parameter equivalent to `bias_tolerance=0` that recovers an exact result. If the circuit has very deep Pauli rotation stacks and the observable is dense, the classical preprocessing can become the bottleneck and truncation error may be too large to be useful — in that regime, consider whether a tensor-network-based approach (TEM) or a ZNE variant is more appropriate. In particular, if classical propagation is struggling because the circuit has many non-Clifford gates, ZNE-PEA (`zne-pea.md`) is worth trying instead, since its cost does not depend on circuit magic.

Avoid PNA when workflow simplicity is a constraint. The full pipeline requires circuit boxing, noise learning, Pauli propagation preprocessing (potentially multi-process), observable transformation, and execution via Executor with a `QuantumProgram`. It is not a drop-in option on an existing EstimatorV2 job.

## Trade-offs

| Dimension | Value |
|---|---|
| Shot overhead | No γ² sampling overhead factor; shot count increases with the number of Pauli terms measured in O̊ |
| Circuit execution count | Single execution pass (after noise learning); no noise amplification circuits needed |
| Estimate bias | Reduced-bias; residual bias bounded by truncation in max_err_terms and max_obs_terms |
| Learning phase | Yes — NoiseLearnerV3 noise learning on QPU required before main execution |
| Scales with circuit depth | Classical propagation cost grows as O(2^N) (N = Pauli rotation count) before truncation; controlled by max_err_terms |
| Classical preprocessing | Substantial — multiprocessing Pauli propagation; scales with circuit size and available CPU cores |

## Configuration

```python
if __name__ == "__main__":
    from qiskit_addon_pna import generate_noise_mitigating_observable

    obs_tilde = generate_noise_mitigating_observable(
        boxed_circuit,
        isa_observable,
        refs_to_noise_model_map,
        max_err_terms=10_000,
        max_obs_terms=10_000,
        num_processes=8,
        search_step=8,
    )
```

`boxed_circuit` is an ISA circuit boxed with `InjectNoise` annotations via `samplomatic.transpiler.generate_boxing_pass_manager`. `refs_to_noise_model_map` is a `dict[str, PauliLindbladMap]` mapping each `InjectNoise` reference ID to its learned noise model. `obs_tilde` is a `SparsePauliOp` — the noise-mitigating observable to measure.

The function must be called in a `__name__ == "__main__"` guard when `num_processes > 1`, because it uses Python `multiprocessing`. After generating `obs_tilde`, select the largest-coefficient terms to measure, then execute via `Executor` using a `QuantumProgram` built from `samplomatic.build(boxed_circuit)`.

## Composability

PNA uses the Executor primitive and is incompatible with the EstimatorV2 options interface. The PNA tutorial and API docs combine it only with TREX and post-selection. No IBM source covers stacking it with gate-folding ZNE, PEA, PEC or PEC+SLC, all of which now also run on the Executor. They all correct the same learned gate noise, so applying PNA and one of them to the same layers would likely over-correct; treat any such combination as untested. SKILL.md Step 4c picks a single gate-error technique, so the skill does not stack them.

TREX is the natural complement for readout noise: after executing via Executor, apply `trex_factors` from `qiskit_addon_utils.noise_management` to rescale the expectation values using the learned measurement noise model. Dynamical decoupling can be applied to the ISA circuit before boxing, and is compatible at the circuit level.

Post-selection on non-Markovian error checks ([`postselection-non-markovian`](./postselection-non-markovian.md)) is commonly used alongside PNA in the full workflow to discard non-Markovian shots, as demonstrated in the tutorial.

Anecdotally, PNA's QPU cost can be lower than ZNE-PEA's in some regimes, since PNA carries no noise-amplification shot overhead — but this comparison is workload-dependent and has not been quantified here; treat it as a hypothesis to validate empirically rather than a decision rule.
