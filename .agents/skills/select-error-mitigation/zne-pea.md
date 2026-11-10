---
title: Zero-Noise Extrapolation with Probabilistic Error Amplification (PEA)
description: ZNE variant that learns a twirled noise model of each entangling gate layer before execution, then uses the learned model for accurate probabilistic noise amplification rather than gate folding.

capability_id: zne-pea
name: "Zero-Noise Extrapolation with Probabilistic Error Amplification (PEA)"
category: expectation-value-mitigation
short_description: Learns the twirled noise model of each circuit layer before execution, then uses the learned model to amplify noise accurately at each noise factor for ZNE extrapolation.

primitive_estimator: true
primitive_sampler: false
primitive_executor: true
output_type: expectation-value
estimate_bias: reduced-bias

overhead_class: high
overhead_detail: "Noise learning phase (9 × num_randomizations × len(layer_pair_depths) circuits per unique layer) plus ZNE execution overhead (~3× shots at default noise_factors). Every unique layer is learned, so learning cost scales with the unique-layer count (SKILL.md Phase 1.5)."
requires_noise_learning: true
requires_hardware: true

resilience_level_activation: null
api_class: "qiskit_ibm_runtime.options.ZneOptions"
api_guide: "https://quantum.cloud.ibm.com/docs/en/guides/error-mitigation-and-suppression-techniques.md#pea"

use_when:
  - "Utility-scale circuits with large qubit count and/or significant circuit depth"
  - "Gate folding amplification is inaccurate for the target circuit (complex or non-uniform Pauli noise structure that digital folding cannot amplify faithfully)"
  - "More accurate noise amplification is needed than gate folding provides"
  - "Shot budget allows noise learning phase overhead in addition to ZNE execution overhead"
  - "Circuit layers repeat (few unique entangling layers, each learned once and reused across every repetition)"
  - "Target observables are local / low-weight (mitigation reliability is far higher for low-weight observables)"
  - "Total accumulated error is modest (mitigation accuracy is governed by qubit count × circuit time × per-layer error rate being small; PEA does not rescue arbitrarily large/deep/noisy circuits)"

avoid_when:
  - "Small or shallow circuits where the noise learning overhead exceeds the benefit (use ZNE with gate folding instead)"
  - "Circuit uses fractional RZZ gates on the Estimator (server-side or client-side): noise injection fails on RZZ there. The Executor with qiskit-mitigation works with twirling_group=\"local_pauli\" and inject_noise_site=\"before\" (relatively untested; see \"Fractional gates\"). Fractional RX gates are fine on the client-side Estimator and the Executor"
  - "Gate-folding ZNE is also enabled (pick one amplifier; incompatible)"
  - "PEC is also enabled in the same job (incompatible)"
  - "Time-sensitive execution where the noise learning delay is not acceptable"
  - "Backend noise drifts between the noise-learning phase and the amplified execution (TLS defects, Stark shifts, or calibration drift make the learned model stale and amplification unfaithful)"
  - "Target observables are high-weight / highly non-local (expectation values decay exponentially with weight and may not be reliably recoverable by extrapolation)"
  - "SamplerV2 primitive"

prerequisites:
  - "EstimatorV2 primitive, or the Executor primitive with qiskit-mitigation (pip install qiskit-mitigation)"
  - "Hardware backend"
  - "ISA circuit whose two-qubit gates are Clifford, or fractional RZZ on the Executor with twirling_group=\"local_pauli\" and inject_noise_site=\"before\"; fractional RX gates are allowed"
  - "Gate twirling is required (automatically enabled when amplifier='pea' is set)"

compatible_with:
  - dynamical-decoupling
  - trex
  - pauli-twirling
  - postselection-non-markovian
  - obp
incompatible_with:
  - zne-gate-folding
  - pec

notes_composability: >
  PEA requires gate twirling, which is automatically enabled when amplifier="pea"
  is set. Cannot be combined with gate-folding ZNE (they are both ZNE amplifiers;
  only one amplifier can be active) or with PEC. TREX is compatible and recommended
  as the measurement-error component of the stack.

references:
  - "Y. Kim et al., Nature 618, 500–505 (2023) — PEA demonstration: ZNE with probabilistic error amplification on 127 qubits (Trotterized 2D Ising)"
  - "E. van den Berg et al., Nature Physics 19, 1116–1121 (2023), arXiv:2201.09866 — sparse Pauli-Lindblad noise model + PEC; the learned model PEA amplifies"
  - "Y. Kim et al., Nature Physics 19, 752–759 (2023), arXiv:2108.09197 — ZNE precursor: establishes that digital noise amplification is unfaithful for realistic Pauli noise, motivating learned-model amplification"
  - "H. Liao et al., arXiv:2309.17368 — ML for practical quantum error mitigation; ML-QEM as a lower-overhead mimic of PEA/PEC"

related_docs:
  - title: "Error mitigation and suppression techniques: PEA"
    url: "https://quantum.cloud.ibm.com/docs/en/guides/error-mitigation-and-suppression-techniques.md#pea"
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
  - title: "Utility-scale PEA experiment tutorial"
    url: "https://quantum.cloud.ibm.com/docs/en/tutorials/probabilistic-error-amplification.md"
    type: tutorial
  - title: "ZneOptions API reference"
    url: "https://quantum.cloud.ibm.com/docs/en/api/qiskit-ibm-runtime/options-zne-options.md"
    type: api-reference
  - title: "LayerNoiseLearningOptions API reference"
    url: "https://quantum.cloud.ibm.com/docs/en/api/qiskit-ibm-runtime/options-layer-noise-learning-options.md"
    type: api-reference
  - title: "ResilienceOptionsV2 API reference"
    url: "https://quantum.cloud.ibm.com/docs/en/api/qiskit-ibm-runtime/options-resilience-options-v2.md"
    type: api-reference
  - title: "NoiseLearner API reference"
    url: "https://quantum.cloud.ibm.com/docs/en/api/qiskit-ibm-runtime/noise-learner.md"
    type: api-reference
---

## Summary

Probabilistic Error Amplification is a ZNE amplification technique that addresses the main limitation of gate folding: inaccurate noise amplification for complex circuits. PEA works in three stages. First, a learning phase runs circuits to reconstruct the twirled noise model of each unique layer of entangling gates in the target circuit (a separate `NoiseLearnerV3` job with the client-side Estimator; see Configuration). Second, the circuits are executed at each noise factor, where the noise in each entangling layer is amplified by probabilistically injecting single-qubit noise proportional to the learned noise model. Third, the expectation values at each noise factor are extrapolated to zero noise. Because PEA amplifies based on a learned model rather than repetition, it produces more accurate amplification for utility-scale circuits with complex noise. It was demonstrated in the "Evidence for the utility of quantum computing before fault tolerance" experiment (Kim et al., *Nature* 618, 2023) on **127 qubits** running a **Trotterized 2D transverse-field (kicked) Ising model** — up to 60 two-qubit-gate layers / 2,880 CNOTs — with results verified against exact and tensor-network simulation in the classically tractable regime. That workload (a repeating-layer 2D Ising Trotter circuit measuring magnetization) is essentially the canonical PEA use case, so a circuit of that family on current hardware is squarely in scope.

For why PEA amplifies from a learned model rather than by folding, and the assumptions that model makes (repeating Clifford layers, local sparse noise, no drift between learning and execution), see `references/pea-background.md`.

## When to use

- Utility-scale circuits (large qubit count, significant depth) where gate folding amplification is inaccurate. The inaccuracy of gate folding at scale is documented in the literature (see `references/pea-background.md`); PEA is the recommended alternative. IBM's own guidance is explicit: "For utility-scale experiments, PEA is often the best choice," because gate folding "provides an easy way to perform this amplification, but is potentially inaccurate and might lead to incorrect results," whereas PEA is "a more accurate approach to error amplification through noise learning." Treat *utility-scale + Estimator + shot budget for learning* as the default-PEA regime, and reserve gate folding for the small/shallow/cost-limited cases below.
- The circuit has repeating layers of entangling gates. PEA learns each unique layer, so circuits with few unique layers are learned efficiently, and the learning cost is amortized over every repetition of that layer.
- Target observables are local / low-weight. In the foundational experiments, "lower-weight observables display a superior accuracy," and the guidance is to "choose to mitigate observables that are less sensitive to noise, such as local observables." High-weight, non-local expectation values decay exponentially and are the hardest case for any extrapolation.
- The total accumulated error is modest. The Richardson-extrapolation error bound scales as `~O((N·T·λ)^(n+1))` (qubit count `N`, circuit time `T`, per-layer error rate `λ`), so mitigation quality "is expected to be limited by `N·T·λ` being a small number." PEA sharpens the amplification but does not lift this ceiling — a circuit whose `N·T·λ` is large will not be rescued.
- Shot budget is sufficient for the noise learning phase in addition to ZNE execution. The learning overhead is significant but amortized across all PUBs sharing the same layer structure.

## When not to use

- Small or shallow circuits. The noise learning phase has fixed overhead that is not justified for simple circuits; use ZNE with gate folding instead.
- Circuit uses fractional RZZ gates on the Estimator (see "Fractional gates" below; fractional RX is fine; RZZ works only on the Executor, with `twirling_group="local_pauli"` and `inject_noise_site="before"`).
- Gate-folding ZNE is already enabled (only one amplifier can be active).
- PEC is already enabled in the same job.
- Time-sensitive contexts where the preliminary learning phase delay is not acceptable.
- Backend noise is expected to drift between learning and execution. All learned-model amplification assumes the noise is stable from the moment it is characterized to the amplified runs — the analogue of the "time-invariant noise" assumption that pulse-stretch ZNE relies on. Kim et al. document TLS defects that "lead to fluctuations in coherence" and control-qubit Stark shifts of nearly 10 MHz across amplification settings that "can potentially violate assumptions on time invariant noise." If the device drifts on the timescale between the learning phase and the main run, the learned model is stale and the amplification is no longer faithful; re-learn, or fall back to a technique that does not depend on a persistent model.
- Observables are high-weight / highly non-local, for the accuracy reason above.

## Trade-offs

| Dimension | Value |
|---|---|
| Shot overhead | High: learning phase (9 × num_randomizations × len(layer_pair_depths) circuits per unique layer) + ZNE execution (~3× at default noise_factors) |
| Circuit execution count | Learning circuits + one per noise factor per PUB |
| Estimate bias | Reduced; more accurate than gate folding for utility-scale circuits; biased estimator |
| Learning phase | Yes (layer noise learning; about 1 minute of QPU time per unique layer at the default options, see SKILL.md Phase 1.5) |
| Scales with circuit depth | Learning overhead is per unique layer; execution overhead is fixed by noise_factors |

### Fractional gates

PEA works with fractional `rx` gates with any twirling group, because `rx` is a single-qubit gate and leaves the twirled entanglers unchanged. With fractional `rzz`, a non-Clifford entangler, the default group fails at build time with `BuildError: Non-Clifford and unbound fractional entanglers are only supported for Twirl with 'GroupMode LOCAL_PAULI'`. `local_pauli` twirling fixes the build, but PEA also injects noise after each layer by default. A sampled noise Pauli that doesn't commute with `rzz` can't be propagated through it, and sampling fails with `SamplexRuntimeError: Pauli values not in the commutant of 'rzz' cannot be propagated`. Whether a run hits this is random: it passed with small rates and few randomizations, and failed with realistic ones. So:
- **Executor (`qiskit-mitigation`):** pass `twirling_group="local_pauli"` and `inject_noise_site="before"` in the task's `custom_boxing_options`. This ran reliably.
- **Client-side Estimator:** `twirling.group = "local_pauli"` is not enough, and the Estimator options have no setting for the injection site. Treat PEA with `rzz` as unsupported there; move the workload to the Executor.
- **Server-side `EstimatorV2`:** no `group` option; unsupported.

Whether `NoiseLearnerV3` learns a model that matches `inject_noise_site="before"` is untested.

**Twirling with `rzz` is relatively untested.** The checks below confirm that the jobs build and run, not that the mitigation works: `local_pauli` twirls each `rzz` only with the Paulis that commute with it, so less of the noise is tailored into the Pauli channel that PEA and PEC assume. When recommending any technique that twirls `rzz`, warn the researcher in the output and suggest comparing against an unmitigated run before trusting the result.

Checked against qiskit-ibm-runtime 0.52.0, qiskit-mitigation 0.1.1 and samplomatic 0.21.0, on a 5-qubit `rx` + `cx` circuit on FakeManilaV2 with `rx` added to its target, and on a 4-qubit circuit with 4 `rzz` and 4 `cx` gates. PEA ran end to end with a hand-built `PauliLindbladMap` per unique layer (the `generate_random_pauli_lindblad_noise` pattern in the [PEC with TREX guide](https://quantum.cloud.ibm.com/docs/en/addons/qiskit-mitigation/guides/pec-with-trex)), passed as `resilience.layer_noise_model` on the Estimator and as `noise_maps` to the `qiskit-mitigation` task on an `AerSimulator` Executor. Replacing two `cx` with `rzz` failed on both with the default group. With `local_pauli`, the Estimator ran only when the noise model's rates were small (3e-3, 32 randomizations) and failed with the `SamplexRuntimeError` at higher rates (0.3) or 1024 randomizations; the Executor with `inject_noise_site="before"` ran at rate 0.3 and 1024 randomizations. A hand-built map checks only that the job builds and runs; it says nothing about how well the technique works, which needs a model learned on hardware.

## Configuration

```python
# Client-side Estimator (qiskit-ibm-runtime >= 0.50.0); checked against 0.50.0.
from qiskit_ibm_runtime.executor_estimator import Estimator

from qiskit_ibm_runtime import NoiseLearnerV3

estimator = Estimator(mode=backend)
# zne_mitigation must also be set to True; amplifier="pea" selects PEA
estimator.options.resilience.zne_mitigation = True
estimator.options.resilience.zne.amplifier = "pea"

# The client-side Estimator does not learn noise for PEA on its own: learn it in a
# separate NoiseLearnerV3 job and pass it in. Set the PEA options above first;
# find_unique_layers returns no layers otherwise.
layers = estimator.find_unique_layers(pubs)

learner = NoiseLearnerV3(backend)
learner.options.num_randomizations = 32
learner.options.shots_per_randomization = 128
learner.options.layer_pair_depths = [0, 1, 2, 4, 16, 32]
learner_result = learner.run(layers).result()

estimator.options.resilience.layer_noise_model = zip(layers, learner_result.to_pauli_lindblad_maps())
job = estimator.run(pubs)
```

Gate twirling is automatically enabled when `amplifier="pea"` is set. The default noise factors for PEA are `(1, 1.5, 2)`, narrower than the gate-folding defaults `(1, 3, 5)`, reflecting the more accurate amplification. PEA's amplification is exact in the learned model: to reach gain `G` it multiplies each layer's learned Pauli-Lindblad rates `λ` by `α = G − 1` (the map `e^{αL}`) and injects Pauli errors before the layer with probability `p = (1 − e^{−2(G−1)λ})/2`. This is why the factors sit close to 1 — the noise is amplified accurately from the model rather than by crudely repeating gates.

**Extrapolator note.** The foundational PEA experiment (Kim et al., *Nature* 618, 2023) used small gains — `G ∈ {1, 1.2, 1.6}` and `{1, 1.3, 1.6}` — with an **exponential** extrapolation, reporting "reduced bias from exponential extrapolation in comparison with linear extrapolation." So exponential is the intended default for PEA *when the fit is well-resolved*, not linear. The catch is stability: over such a narrow, low-gain grid an exponential fit can blow up near zero noise (values in the hundreds, or negative). The paper's remedy is to **iteratively downgrade the extrapolation model complexity** when the fit is not well resolved — i.e. fall back exponential → low-degree polynomial → linear rather than committing to linear up front. Provide the extrapolator as an ordered list (`["exponential", "linear"]`) so the runtime takes the first successful fit. When comparing PEA against gate folding empirically, use the fair-comparison protocol in `verification.md` ("Comparing ZNE amplifiers fairly"), which controls for the different grids.

### With the Executor (qiskit-mitigation)

Checked against qiskit-mitigation 0.1.1. `learned_noise` maps each `InjectNoise` reference to its learned `PauliLindbladMap`, for the layers `task.find_unique_layers(circuit, boxing_options)` returns with an `InjectNoise` annotation (not the measurement layer). The guide learns it with `qiskit-noise-learning`. Noise factors can be non-integer; the guide uses `[1, 2, 3]`, and the package default is `(1, 3, 5)`, not the Estimator's `(1, 1.5, 2)`. The injected noise is sampled once per randomization, so use many randomizations with few shots each. See the [PEA guide](https://quantum.cloud.ibm.com/docs/en/addons/qiskit-mitigation/guides/pea-with-noise-learning).

```python
from qiskit_ibm_runtime import Executor
from qiskit_mitigation import PEA

task = PEA()
program = task.prepare(
    circuit, observables, parameters,
    noise_maps=learned_noise, noise_factors=[1, 2, 3],
    num_randomizations=200, shots_per_randomization=16,
)
result = task.postprocess(Executor(backend).run(program).result(), extrapolator=["exponential", "linear"])
```

## Composability

PEA requires gate twirling (auto-enabled), and the requirement is structural, not incidental: twirling converts the arbitrary physical noise channel of each layer into a stochastic Pauli channel, "suppressing off-diagonal coherent error contributions." That Pauli channel is exactly the object the noise-learning phase reconstructs and the amplifier scales — without twirling there is no faithful learned model to amplify from. TREX is compatible and recommended as the measurement-error component. Cannot be combined with gate-folding ZNE (both are ZNE amplifiers; only one is active at a time) or with PEC. Stacking with PNA or PEC+SLC is undocumented: they correct the same learned gate noise, so the combination would likely over-correct and is untested. Dynamical decoupling is compatible and complementary — DD suppresses coherent idle-time errors that twirling alone leaves behind.

A noise model learned in a previous run can be reused by passing it again via `resilience.layer_noise_model`, which skips the learning job:

```python
estimator.options.resilience.layer_noise_model = zip(layers, previous_learner_result.to_pauli_lindblad_maps())
```

## Reducing PEA's cost

PEA's dominant cost is the per-layer noise-learning phase. Two levers within Runtime, plus one research direction:

- **Reuse the learned model.** The single most effective cost reduction when the same layer structure and backend recur: learn once, then pass `resilience.layer_noise_model` on subsequent jobs (above). Valid only while the noise has not drifted since learning (see the drift `avoid_when`) — reuse across a stable calibration window, re-learn after recalibration.
- **Learn only the layers that matter.** Every layer passed to `NoiseLearnerV3` is a separate learning experiment; compare the count from SKILL.md Phase 1.5 with the circuit's true number of distinct entangling layers.
