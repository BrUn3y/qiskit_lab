---
title: Operator Backpropagation (OBP)
description: Propagates a Pauli observable backward through trailing circuit gates classically, producing a shallower circuit at the cost of a larger observable with more measurement bases.

capability_id: obp
name: "Operator Backpropagation (OBP)"
category: expectation-value-mitigation
short_description: Reduces circuit depth by absorbing trailing gates into the observable classically, trading observable size (and thus shot count) for shallower QPU execution.

primitive_estimator: true
primitive_sampler: false
primitive_executor: false
output_type: expectation-value
estimate_bias: reduced-bias

overhead_class: medium
overhead_detail: "Shot overhead grows with observable size: each absorbed gate can split Pauli terms, increasing the number of qubit-wise commuting groups (measurement bases) that must be executed on hardware. Growth is bounded by operator_budget and truncation_error_budget; for near-Clifford circuits the growth is manageable, but for high-magic circuits the observable can grow exponentially with a fixed truncation error budget."
requires_noise_learning: false
requires_hardware: false

resilience_level_activation: null
api_class: "qiskit_addon_obp.backpropagate"
api_guide: "https://qiskit.github.io/qiskit-addon-obp/"

use_when:
  - "Circuit depth is the limiting factor and reducing QPU gate count is worth an increase in observable complexity (more measurement bases)"
  - "The circuit is near-Clifford: gates are predominantly from the Clifford group, with only a small fraction of non-Clifford (high-magic) gates"
  - "The target observable is a Pauli or sparse sum of Paulis acting on a small number of qubits relative to the circuit width"
  - "Classical simulation cost is acceptable: backpropagation is performed offline before QPU submission"
  - "An error bound on the truncated expectation value is needed: OBP provides a computable upper bound on truncation error via TruncationErrorBudget"
  - "The circuit can be partitioned into gate-type slices (e.g., Trotter circuits with repeated layer structure)"

avoid_when:
  - "The circuit is high-magic (many non-Clifford gates): terms added to the observable during backpropagation have large coefficients, causing truncation error to accumulate quickly and limiting depth savings — if classical backpropagation is already struggling for this reason, consider ZNE-PEA (`zne-pea.md`) instead, since its cost does not depend on circuit magic"
  - "The target observable already spans most or all qubits: there is limited room to grow before all measurement bases are exhausted"
  - "A fixed-depth reduction guarantee is required: backpropagation halts when the operator budget is exceeded, which may be after few slices depending on circuit structure"
  - "The workflow requires a standard EstimatorV2 options interface: OBP is a preprocessing step that modifies the circuit and observable before execution, not a runtime option"
  - "Many distinct observables need to be evaluated against the same circuit — backpropagation and truncation are performed per observable, so preprocessing cost scales with the number of observables; PEC (`pec.md`) is cheaper to keep generic across a large or changing observable set"

prerequisites:
  - "qiskit-addon-obp installed (pip install qiskit-addon-obp)"
  - "qiskit-addon-utils installed for circuit slicing (pip install qiskit-addon-utils)"
  - "Circuit sliced into QuantumCircuit partitions (each slice must span all qubits)"
  - "Observable expressed as a SparsePauliOp"

compatible_with:
  - dynamical-decoupling
  - pauli-twirling
  - trex
  - zne-gate-folding
  - zne-pea
  - pec
incompatible_with: []

notes_composability: >
  OBP is a preprocessing step that modifies the circuit and observable before
  submission to any primitive. The reduced-depth circuit and expanded observable
  can be submitted to EstimatorV2 with any combination of Runtime error mitigation
  options (ZNE, PEC, TREX, twirling, dynamical decoupling). OBP is not an
  EstimatorV2 option and does not conflict with any Runtime-native technique.
  When composing with ZNE or PEC, noise learning and overhead are computed against
  the reduced circuit, not the original.

references:
  - "B. Fuller et al., 'Improved quantum computation using operator backpropagation,' npj Quantum Inf. 12, 51 (2026). arXiv:2502.01897"

related_docs:
  - title: "OBP quickstart guide"
    url: "https://qiskit.github.io/qiskit-addon-obp/guides/quickstart.html"
    type: guide
  - title: "Truncate Pauli terms during backpropagation"
    url: "https://qiskit.github.io/qiskit-addon-obp/guides/truncate-operator-terms.html"
    type: guide
  - title: "Bound error using Lp-norms"
    url: "https://qiskit.github.io/qiskit-addon-obp/guides/bound-error-using-p-norm.html"
    type: guide
  - title: "Simulate circuits with OBP"
    url: "https://qiskit.github.io/qiskit-addon-obp/guides/simulating-circuits-with-obp.html"
    type: guide
  - title: "OBP tutorial: operator backpropagation"
    url: "https://quantum.cloud.ibm.com/docs/tutorials/operator-back-propagation.md"
    type: tutorial
  - title: "qiskit-addon-obp documentation"
    url: "https://qiskit.github.io/qiskit-addon-obp/"
    type: external
---

## Summary

Operator backpropagation (OBP) reduces circuit depth by propagating a Pauli observable backward through trailing circuit gates classically. Given an expectation value ⟨ψ|U†OU|ψ⟩, OBP peels gate layers off U and conjugates O by them offline, producing a shallower circuit U' and an expanded observable O' such that ⟨ψ|U'†O'U'|ψ⟩ gives the same result. The cost is that each absorbed gate can expand a single Pauli term into multiple terms, so the observable grows — in the worst case exponentially — increasing the number of measurement bases (qubit-wise commuting groups) that must be executed on hardware. For near-Clifford circuits, the observable growth is typically manageable because low-magic gates generate small terms; for high-magic circuits the growth can be rapid. Terms with small coefficients can be truncated during backpropagation to control observable size, at the cost of a bounded error in the final expectation value.

The package implements OBP via Clifford perturbation theory. The overhead incurred when propagating through a gate is determined by its non-Cliffordness, which provides better efficiency than tensor-network methods for circuits with moderate magic. Two complementary stopping controls are provided: `OperatorBudget` caps observable size (number of Pauli terms or qubit-wise commuting groups), and `TruncationErrorBudget` controls how much truncation error can be incurred while discarding small-coefficient terms.

## When to use

Use OBP when circuit depth is the bottleneck and you can tolerate an increase in the number of measurement bases needed to evaluate the observable. The technique is most effective for near-Clifford circuits — time-evolution circuits under Pauli Hamiltonians, Trotter circuits with small Trotter steps, and variational circuits with shallow non-Clifford layers are typical targets. OBP is a good fit when the target observable is local (acts on few qubits), because the observable has more room to grow before hitting the measurement-base budget. It also applies to cases where a controlled, certifiable error bound on the expectation value is needed: `TruncationErrorBudget` provides a computable upper bound on the introduced error. OBP requires no noise learning and no QPU calibration data; the preprocessing is entirely classical.

## When not to use

Avoid OBP when the circuit contains many non-Clifford gates (high magic). In this regime, even a few backpropagated slices can introduce large-coefficient Pauli terms that quickly exhaust the truncation error budget, and depth savings before that point may be minimal — if classical backpropagation is struggling for this reason, ZNE-PEA (`zne-pea.md`) is worth trying instead, since its cost does not depend on circuit magic. Similarly, if the target observable already spans most qubits, the expanded observable will fill all available measurement bases after few absorbed slices. OBP is not a drop-in option on EstimatorV2 — it requires explicitly slicing the circuit, running the backpropagation function, and submitting the modified circuit and observable. Workflows that require a stable, unchanged circuit (for noise characterization on the exact circuit, for example) should treat OBP with care, since the reduced circuit has different gate structure than the original.

How quickly the observable grows during backpropagation is not generally predictable analytically ahead of time — it depends on the interplay of circuit magic, gate structure, and observable support. In practice, growth is determined empirically: run backpropagation, inspect the per-slice Pauli and QWC-group counts via `OBPMetadata`, and use the visualization helpers to decide whether to continue before committing to QPU execution.

## Trade-offs

| Dimension | Value |
|---|---|
| Shot overhead | Increases with observable size; proportional to the number of qubit-wise commuting groups in the backpropagated observable |
| Circuit execution count | Increases (one execution per QWC group of the expanded observable) |
| Estimate bias | Reduced-bias: truncation introduces a bounded error whose magnitude is tracked by TruncationErrorBudget; exact (no truncation) is also possible |
| Learning phase | None: no noise model or calibration data required |
| Scales with circuit depth | Depth reduction depends on circuit magic; effective for near-Clifford circuits, limited for high-magic circuits |

## Configuration

```python
from qiskit.quantum_info import SparsePauliOp
from qiskit_addon_obp import backpropagate
from qiskit_addon_obp.utils.simplify import OperatorBudget
from qiskit_addon_obp.utils.truncating import setup_budget
from qiskit_addon_utils.slicing import combine_slices, slice_by_gate_types

# Slice the circuit by gate type; each slice must span all qubits
slices = slice_by_gate_types(circuit)
observable = SparsePauliOp("IIIIIIIIIZ")

# Cap the observable at 8 qubit-wise commuting groups
operator_budget = OperatorBudget(max_qwc_groups=8)

# Allow up to 0.001 truncation error per slice
truncation_error_budget = setup_budget(max_error_per_slice=0.001)

bp_obs, remaining_slices, metadata = backpropagate(
    observable,
    slices,
    operator_budget=operator_budget,
    truncation_error_budget=truncation_error_budget,
)

reduced_circuit = combine_slices(remaining_slices)
# Submit reduced_circuit and bp_obs to any EstimatorV2-compatible primitive
```

The `metadata` return value is an `OBPMetadata` instance that records per-slice Pauli counts, QWC-group counts, and accumulated truncation error. Visualization helpers (`plot_accumulated_error`, `plot_num_qwc_groups`, `plot_slice_errors`, `plot_left_over_error_budget`) in `qiskit_addon_obp.utils.visualization` can be used to tune the budgets before committing QPU time.

## Composability

OBP produces a reduced circuit and an expanded observable before any QPU submission. Both can be handed directly to EstimatorV2 with any combination of Runtime error mitigation options — ZNE (gate folding or PEA), PEC, TREX, Pauli twirling, and dynamical decoupling are all compatible because they operate on whatever circuit and observable are submitted. There is no conflict with Runtime-native techniques. When composing with noise-learning methods (ZNE-PEA, PEC), note that noise characterization and overhead estimates will be computed against the reduced circuit, which differs from the original in gate count and structure.
