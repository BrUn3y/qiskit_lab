---
title: Probabilistic Error Cancellation with Shaded Lightcones (PEC+SLC)
description: A modified PEC technique that uses Pauli propagation to bound each error's influence on the target observable, then mitigates only the errors that matter, lowering sampling overhead with zero or a controllable residual bias.

capability_id: pec-slc
name: "Probabilistic Error Cancellation with Shaded Lightcones (PEC+SLC)"
category: expectation-value-mitigation
short_description: Reduces PEC sampling overhead by bounding each error's influence on the observable and mitigating only the errors that matter, trading classical preprocessing for QPU shots and, optionally, a bounded residual bias.

primitive_estimator: false
primitive_sampler: false
primitive_executor: true
output_type: expectation-value
estimate_bias: reduced-bias

overhead_class: high
overhead_detail: "QPU sampling overhead (γ²) is lower than full PEC for the same circuit. In the IBM tutorial (20-qubit mirrored 1D Ising chain, 10 Trotter steps, ibm_kingston, bounds computed with 8 processes and a 60 s timeout that was deliberately reached), full PEC had γ² ≈ 163 and PEC+SLC ≈ 48 at a 10% residual-bias bound, a ~3.4× reduction; the values depend on the backend's calibration at run time. Errors outside the observable's lightcone are dropped with no added bias, so even bias_tolerance=0 gives a lower γ² than full PEC. Classical preprocessing (forward/backward bound computation) is substantial and scales with circuit size; more processes or a longer timeout give tighter bounds. Noise learning on the QPU (NoiseLearnerV3) is required."
requires_noise_learning: true
requires_hardware: true

resilience_level_activation: null
api_class: "qiskit_addon_slc.bounds.compute_local_scales"
api_guide: "https://quantum.cloud.ibm.com/docs/en/addons/qiskit-addon-slc"

use_when:
  - "Full PEC sampling overhead (γ²) is prohibitive for the target circuit but an unbiased or near-unbiased estimate is preferred over ZNE"
  - "Circuit has causal structure that limits the lightcone of the target observable (not all errors equally influence the result)"
  - "Observable is local (acts on a small subset of qubits) relative to circuit width"
  - "Sufficient classical compute is available for forward/backward bound computation (more CPU processes or a longer timeout yield tighter bounds and lower γ²)"
  - "A tunable bias-overhead trade-off is needed: bias_tolerance sets the residual-bias bound, from zero upward"
  - "A fixed sampling budget must not be exceeded: compute_local_scales can instead fill a sampling_cost_budget with the most impactful errors and report the resulting bias bound"
  - "Utility-scale circuits where standard PEC is impractical"

avoid_when:
  - "Circuit observable acts on the full circuit width (lightcone shading provides minimal benefit when all errors influence the observable)"
  - "Classical preprocessing time is a bottleneck (bound computation can be significant; layers not reached before the timeout get the trivial bound of 2)"
  - "Simple workflow is required; SLC involves multiple preprocessing steps and the directed execution model (QuantumProgram/Executor), not standard EstimatorV2 options"
  - "Team lacks access to sufficient classical compute (bound tightness and overhead reduction scale with CPU processes available)"
  - "Workflow must run on Windows (qiskit-addon-slc does not support Windows)"
  - "Installed qiskit-ibm-runtime is older than 0.47.0 (QuantumProgram and Executor are not available)"
  - "No hardware access: there is no meaningful simulator workflow, because the mitigation depends on noise rates learned on the QPU"

prerequisites:
  - "qiskit >= 2.2"
  - "qiskit-ibm-runtime >= 0.47.0 (QuantumProgram, Executor, NoiseLearnerV3)"
  - "qiskit-addon-slc >= 0.1 (pip install qiskit-addon-slc)"
  - "qiskit-addon-utils >= 0.3 (pip install qiskit-addon-utils)"
  - "samplomatic >= 0.13 (pip install samplomatic)"
  - "Linux or macOS (Windows is not supported)"
  - "Hardware backend"
  - "ISA circuit (transpiled to backend)"
  - "Circuit boxed with gate twirling (PEC needs the twirled Pauli noise it learns and inverts) and inject_noise_strategy='individual_modification', inject_noise_site='after' (the SLC bounds assume 'after'; site='before' is not supported). So circuits with fractional RZZ gates are effectively unsupported: twirling them needs twirling_group='local_pauli', and injecting noise after an RZZ layer fails when a noise Pauli doesn't commute with RZZ (see pec.md, \"Fractional gates\")"
  - "OMP_NUM_THREADS=1 environment variable set (prevents PySCF internal parallelism conflicts)"
  - "multiprocessing start method set to 'spawn' (required on UNIX to avoid itertools.starmap deadlock)"

compatible_with:
  - dynamical-decoupling
  - trex
  - postselection-non-markovian
incompatible_with:
  - pec

notes_composability: >
  SLC uses the Executor primitive (directed execution model) rather than
  EstimatorV2 options. The only required mitigation is PEC itself, with gate
  twirling from the boxing step. TREX (trex_factors from qiskit_addon_utils, using
  the measurement noise learned in the same NoiseLearnerV3 job) and post-selection
  on non-Markovian error checks (postselection-non-markovian) are optional additions
  that the IBM tutorial stacks on top.
  PEC+SLC is PEC on a chosen subset of error terms (local_scales -1 = mitigate,
  0 = ignore), so it replaces plain PEC rather than stacking with it. Stacking
  with gate-folding ZNE, PEA or PNA is undocumented and untested; all of them
  correct the same learned gate noise, so it would likely over-correct.

references:
  - "Eddins et al., Lightcone shading for classically accelerated quantum error mitigation, arXiv:2409.04401 (2024)"
  - "E. van den Berg et al., Nature Physics 19, 1116–1121 (2023), arXiv:2201.09866"
  - "Tran et al., Locality and error mitigation of quantum circuits, arXiv:2303.06496 (2023)"

related_docs:
  - title: "Shaded lightcones (SLC) addon"
    url: "https://quantum.cloud.ibm.com/docs/en/addons/qiskit-addon-slc"
    type: guide
  - title: "SLC quickstart"
    url: "https://quantum.cloud.ibm.com/docs/en/addons/qiskit-addon-slc/guides/quickstart"
    type: guide
  - title: "Tutorial: Probabilistic error cancellation with shaded lightcones"
    url: "https://quantum.cloud.ibm.com/docs/en/tutorials/pec-with-shaded-lightcones"
    type: tutorial
  - title: "Directed execution model"
    url: "https://quantum.cloud.ibm.com/docs/en/guides/directed-execution-model.md"
    type: guide
  - title: "Executor quickstart"
    url: "https://quantum.cloud.ibm.com/docs/en/guides/get-started-with-executor.md"
    type: guide
  - title: "Noise learning"
    url: "https://quantum.cloud.ibm.com/docs/en/guides/noise-learning.md"
    type: guide
  - title: "Samplomatic: qubit ordering convention"
    url: "https://quantum.cloud.ibm.com/docs/en/addons/samplomatic/guides/samplex-io#qubit-ordering-convention"
    type: guide
  - title: "Overview of noise management techniques"
    url: "https://quantum.cloud.ibm.com/docs/en/guides/error-mitigation-overview.md"
    type: guide
---

## Summary

PEC with Shaded Lightcones addresses the main practical limitation of Probabilistic Error Cancellation: its exponentially growing sampling overhead. PEC rescales the result by γ = exp(Σ 2λ) over every learned error rate λ, which multiplies the variance, and so the number of QPU executions, by γ². SLC first computes, for each error, a bound on how much that error can influence the target observable — its "shade." Errors outside the observable's causal lightcone get a shade of zero; leaving them unmitigated lowers γ² with no added bias. Errors inside the lightcone with small shades can also be left unmitigated, accepting a bounded residual bias in exchange for a further reduction in γ². `compute_local_scales` controls this trade-off in one of two ways: a `bias_tolerance` (the residual-bias bound to stay within) or a `sampling_cost_budget` (the γ² to fill with the most impactful errors). The classical preprocessing (forward/backward bound computation by Pauli propagation) is compute-intensive, and can run before noise learning, so it doesn't delay execution.

The only error mitigation SLC requires is PEC: gate twirling (set in the boxing step), noise learning, and anti-noise injection with γ rescaling. The IBM tutorial also stacks TREX readout correction and post-selection on non-Markovian error checks on top to improve its result further. Neither is part of SLC, and both are optional; post-selection has its own page, [`postselection-non-markovian`](./postselection-non-markovian.md).

## When to use

- Full PEC overhead is prohibitive for the circuit of interest. SLC is the natural upgrade path from standard PEC when the shot budget cannot support γ² at full precision.
- The target observable is local — it acts on a small subset of qubits relative to circuit width. Errors far from the observable's support have provably small influence and can be shaded out. The benefit increases as observable locality increases.
- Classical compute is available. Tighter bounds (lower γ²) come from more CPU processes or a longer timeout.
- A tunable accuracy-cost trade-off is needed, either as a bias bound (`bias_tolerance`) or as a fixed sampling budget (`sampling_cost_budget`).

## When not to use

- The observable acts on the full circuit width. If the lightcone covers all qubits, shading provides no selective exclusion and the overhead reduction is minimal.
- Simple workflow is a requirement. SLC involves circuit boxing with `samplomatic`, multi-step bound computation, a QPU noise learning phase, and the directed execution model. It is not a drop-in options setting on EstimatorV2.
- Classical preprocessing time is a hard constraint. Layers not reached within the timeout receive the trivial bound of 2. That is safe — the shades are upper bounds at every stage, so a timeout never underestimates an error's effect — but it limits the overhead reduction.
- The workflow must run on Windows, or without hardware access. The tutorial has no simulator example, because noise learning and anti-noise sampling only mean something on a real QPU.

## Trade-offs

| Dimension | Value |
|---|---|
| QPU sampling overhead (γ²) | Lower than full PEC. IBM tutorial (20-qubit mirrored Ising, ibm_kingston): ≈163 for full PEC vs ≈48 for PEC+SLC at a 10% residual-bias bound. Depends on calibration at run time |
| Classical preprocessing | Substantial (forward/backward bound computation); scales with circuit size; tighter with more processes or a longer timeout |
| Estimate bias | Tunable. Zero added bias when only errors outside the lightcone are dropped (`bias_tolerance=0`); a bounded residual bias above that |
| Learning phase | Yes: noise learning on QPU (`NoiseLearnerV3`). The same job also learns measurement noise, which is used only if TREX is added |
| Scales with circuit depth | γ² still grows with depth but more slowly than full PEC for local observables |
| Optional add-ons | TREX (readout correction in post-processing) and post-selection on non-Markovian error checks (see [`postselection-non-markovian`](./postselection-non-markovian.md); in the tutorial it kept ≈24% of shots in execution with the node strategy and ≥71% in noise learning). Neither is required for SLC |

## Configuration

Checked against qiskit 2.4.0, qiskit-ibm-runtime 0.50.0, qiskit-addon-slc 0.1.0, qiskit-addon-utils 0.4.0 and samplomatic 0.21.0. The classical steps (1, 3 and the `QuantumProgram` construction in 4) were run end to end on a small circuit with synthetic noise rates; steps 2 and 4's `executor.run` need hardware. For the full worked example, follow the [tutorial](https://quantum.cloud.ibm.com/docs/en/tutorials/pec-with-shaded-lightcones).

The code below shows the required PEC+SLC path. Lines marked `# optional` add TREX, as the tutorial does; leave them out for plain PEC+SLC. To add post-selection, follow [`postselection-non-markovian.md`](./postselection-non-markovian.md): add the checks to `template_circuit` in step 4, enable `bit_flip_checks` in step 2, and pass the mask as `postselect_mask` in step 5.

### 0. Environment

```python
from multiprocessing import set_start_method
set_start_method("spawn")      # prevents itertools.starmap deadlock on UNIX
# and set OMP_NUM_THREADS=1 before starting Python, to stop PySCF parallelizing internally
```

### 1. Box the circuit and compute bounds (classical, before noise learning)

```python
from qiskit_addon_utils.exp_vals.measurement_bases import get_measurement_bases
from samplomatic.transpiler import generate_boxing_pass_manager
from samplomatic.utils import find_unique_box_instructions
from qiskit_addon_slc.utils import generate_noise_model_paulis
from qiskit_addon_slc.bounds import (
    compute_forward_bounds, tighten_with_speed_limit, compute_backward_bounds, merge_bounds,
)

# Measurement bases for the observable; the reverser is used in post-processing
bases_virt, reverser_virt = get_measurement_bases(observable)

boxes_pm = generate_boxing_pass_manager(
    twirling_strategy="active",
    inject_noise_strategy="individual_modification",  # required: makes each InjectNoise uniquely identifiable
    inject_noise_site="after",                        # required: SLC bounds assume "after"; set it explicitly
    inject_noise_targets="gates",
    measure_annotations="all",
)
boxed_circuit = boxes_pm.run(isa_circuit)

# Unique two-qubit layers first, then the measurement box
unique_instructions = find_unique_box_instructions(
    boxed_circuit, normalize_annotations=None, undress_boxes=True
)

# The structure of the noise model NoiseLearnerV3 will fill in, known before learning
noise_model_paulis = generate_noise_model_paulis(unique_instructions, backend.coupling_map, boxed_circuit)

forward_bounds = compute_forward_bounds(
    boxed_circuit, noise_model_paulis, isa_observable,
    evolution_max_terms=1000,   # Pauli terms kept while propagating
    eigval_max_qubits=18,       # above this, fall back to the looser triangle-inequality bound
    atol=1e-8,
    num_processes=8,
    timeout=60,                 # layers not reached get the trivial bound of 2
)
forward_bounds = tighten_with_speed_limit(forward_bounds, boxed_circuit, noise_model_paulis, isa_observable)
backward_bounds = compute_backward_bounds(
    boxed_circuit, noise_model_paulis, evolution_max_terms=1000, num_processes=8, timeout=60,
)
```

`qiskit_addon_slc.visualization.draw_shaded_lightcone(boxed_circuit, bounds, noise_model_paulis, pauli_filter="X")` draws the bounds for inspection.

### 2. Learn the noise (QPU)

```python
from qiskit_ibm_runtime import NoiseLearnerV3

# Match the deepest learning depth to the circuit: layer_pair_depths count layer pairs,
# so the deepest value is half the two-qubit depth (measured on the pre-boxed ISA circuit)
max_pair_depth = isa_circuit.depth(lambda instr: instr.operation.num_qubits == 2) // 2
layer_pair_depths = sorted({d for d in [1, 2, 4, 8, 12, 16, 24, 32, 40, 48] if d < max_pair_depth} | {max_pair_depth})

noise_learner = NoiseLearnerV3(backend, {
    "num_randomizations": 64,
    "shots_per_randomization": 128,
    "layer_pair_depths": layer_pair_depths,
})
noise_learner_result = noise_learner.run(unique_instructions).result()

# Map each InjectNoise ref to its learned PauliLindbladMap
refs_2_plm = noise_learner_result.to_dict(unique_instructions, require_refs=False)
```

Run step 1 before learning, so execution follows the learning as closely as possible in time. The two can also run in parallel.

### 3. Choose which errors to mitigate (classical)

```python
import numpy as np
from qiskit_addon_slc.bounds import compute_local_scales
from qiskit_addon_slc.utils import map_modifier_ref_to_ref

merged_bounds = merge_bounds(boxed_circuit, forward_bounds, backward_bounds, refs_2_plm)

# Either stay within a residual-bias bound ...
local_scales, sampling_cost, residual_bias_bound = compute_local_scales(
    boxed_circuit, merged_bounds, refs_2_plm, sampling_cost_budget=np.inf, bias_tolerance=0.1,
)
# ... or fill a fixed sampling budget (gamma^2) and read off the resulting bias bound:
# compute_local_scales(boxed_circuit, merged_bounds, refs_2_plm, sampling_cost_budget=100)

id_map = map_modifier_ref_to_ref(boxed_circuit)
full_pec_cost = np.exp(2 * sum(np.sum(refs_2_plm[n].rates) for n in id_map.values())) ** 2
```

Sweeping `bias_tolerance` (for example 0 to 0.1) and plotting `sampling_cost` against `residual_bias_bound` shows the trade-off for this circuit before committing QPU time. `merge_bounds` can also be called before learning, with `{ref: None for ref in noise_model_paulis}` as the rates, for a preview that assumes uniform rates.

### 4. Build and run with anti-noise (QPU)

```python
import samplomatic
from qiskit_ibm_runtime import Executor, QuantumProgram

# Basis changes must be given in samplomatic's canonical qubit order, not the virtual order
meas_box = boxed_circuit.data[-1]
canonical_qubits = [i for i, q in enumerate(boxed_circuit.qubits) if q in meas_box.qubits]
p_2_v = {p: v for v, p in enumerate(isa_circuit.layout.final_index_layout())}
bases_canon = [
    np.array([b[p_2_v[canonical_qubits[c]]] for c in range(len(canonical_qubits))], dtype=np.uint8)
    for b in bases_virt
]

template_circuit, samplex = samplomatic.build(boxed_circuit)

program = QuantumProgram(shots=64, noise_maps=refs_2_plm)
inputs = {f"noise_scales.{ref}": -1.0 for ref in local_scales}  # -1 = anti-noise (0 = unmitigated)
inputs |= {"basis_changes": {"basis0": bases_canon[0]}}
inputs |= {"local_scales": local_scales}                         # omit for plain PEC
program.append_samplex_item(
    circuit=template_circuit,
    samplex=samplex,
    samplex_arguments=samplex.inputs().bind(**inputs).make_broadcastable(),
    shape=(4096,),       # number of randomizations
    chunk_size=256,
)
result = Executor(backend).run(program).result()[0]
```

Adding an unmitigated item (`noise_scales` 0, no `local_scales`) and a plain-PEC item (`noise_scales` -1, no `local_scales`) to the same `QuantumProgram` gives a direct comparison in one job, as the tutorial does.

### 5. Post-process (classical)

```python
from qiskit_addon_utils.exp_vals.expectation_values import executor_expectation_values
from qiskit_addon_utils.noise_management import gamma_from_noisy_boxes, trex_factors

# Required: rescale by the PEC+SLC gamma (omit local_scales for plain PEC)
gamma_slc = gamma_from_noisy_boxes(refs_2_plm, id_map, local_scales)

# optional: TREX. The measurement entry comes after the two-qubit layers in unique_instructions
measurement_noise_map = noise_learner_result[len(unique_instructions) - 1].to_pauli_lindblad_map()
trex_scale_factors = trex_factors(measurement_noise_map, reverser_virt)

expval = executor_expectation_values(
    result["meas"], reverser_virt, None, avg_axis=0,
    measurement_flips=result["measurement_flips.meas"],
    pauli_signs=result.get("pauli_signs"),
    gamma_factor=gamma_slc,
    postselect_mask=None,                 # or a mask from postselection-non-markovian.md
    rescale_factors=trex_scale_factors,   # optional: None without TREX
)
```

## Validation

There is no local way to run PEC+SLC: `NoiseLearnerV3` and anti-noise sampling need hardware, and Methods A–C in `verification.md` don't cover Executor workloads. Two classical checks are cheap and run before any QPU time:
- Run step 1 and inspect the shaded lightcones with `draw_shaded_lightcone`. Lightcones that cover the whole circuit mean little overhead reduction.
- After learning, sweep `bias_tolerance` in step 3 and compare `sampling_cost` with the full-PEC cost. That shows whether SLC buys enough over plain PEC before running the expensive execution.

## Composability

SLC uses the Executor primitive (directed execution model), not EstimatorV2 options. It replaces plain PEC rather than stacking with it: `local_scales` marks each PEC error term as mitigated (`-1`) or ignored (`0`), and the SLC quickstart treats `bias_tolerance=0` as the full-PEC baseline, so running both would invert the same terms twice. No IBM source covers stacking PEC+SLC with gate-folding ZNE, PEA or PNA. All of them correct the same learned gate noise, so the combination would likely over-correct; treat it as untested. The required stack is PEC with gate twirling, which is set in the boxing pass manager (`twirling_strategy`). Two optional additions can be stacked on top, as the tutorial does. One is TREX readout correction in post-processing via `trex_factors`, using the measurement noise learned by the same `NoiseLearnerV3` job. The other is post-selection on non-Markovian error checks ([`postselection-non-markovian`](./postselection-non-markovian.md)), which adds checks to the template circuit and the matching `bit_flip_checks` option in noise learning. The tutorial does not cover dynamical decoupling.

For standard PEC without overhead reduction, see [`pec`](./pec.md).
