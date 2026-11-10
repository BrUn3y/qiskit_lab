# Empirical verification methods (SKILL.md Phase 4.5)

Read this file only when Phase 4.5a finds a grey area. It explains how to run each of the four verification methods. Using the wrong method gives a confident but meaningless answer, so choose by *what kind of error* the technique acts on, by circuit size, and by the installed `qiskit-ibm-runtime` version (SKILL.md Phase 0). The method table in SKILL.md Step 4.5b says which method to use.

Run every method as a subagent (Agent tool) or as a background command, not as a foreground step that blocks other work. Simulation output and circuit dumps would otherwise fill the main conversation's context. When a runner script covers the method (`verify_c1.py`, `verify_c2.py`), a background Bash command is faster than a subagent, since the script already prints only the summary table; use the waiting time for the Phase 5 option-path checks. Give the subagent a self-contained prompt, and ask it to return only a short summary: which configuration won, the error metric for each, and caveats. The exception is anything that uses the researcher's IBM credentials (see "Noise-model freshness" below): run that in the main session.

---

## Method A — custom emulation on NEAT's Clifford circuit

**Use for:** PEA and PEC on EstimatorV2 workloads in any version, and TREX or gate-folding ZNE when `qiskit-ibm-runtime < 0.50.0` (Method C explains why; SKILL.md Step 4.5b has the routing).

NEAT (`qiskit_ibm_runtime.debug_tools.Neat`) applies no mitigation. It supplies three things:
- a Clifford version of the circuit (`to_clifford`)
- exact ideal values (`ideal_sim`)
- a Pauli noise model built from the backend's calibration (`noise_model`), and noisy values under it (`noisy_sim`)

Those are useful in every version for a signal-strength check (SKILL.md Phase 1.5): compare `noisy_sim` with `ideal_sim` to see how much of each observable survives the noise.

Method A is a custom emulation built on top of them. Noisy expectation values come from the noise model, and the technique under test is modeled by hand: gate folding by repeating gates, and PEA by scaling the learned error rates (see `zne-pea.md` for the amplification formula). Say this in the output, and never describe the result as "a NEAT simulation of PEA". The noise model is per-gate depolarizing, which is the one case where gate folding amplifies faithfully, so Method A favours folding over PEA. Report the comparison with that caveat.

The subagent prompt must contain:
- The ISA circuit(s) that will actually run, or exact instructions to rebuild them (original circuit, pass manager, backend, layout).
- The observables as `SparsePauliOp`, mapped to the same layout.
- The backend. For a real backend, use its fake counterpart (e.g. `FakeTorino` for `ibm_torino`).
- The [NEAT documentation](https://quantum.cloud.ibm.com/docs/en/guides/debug-qiskit-runtime-jobs.md).
- The required caveat: the Clifford circuit is a structural stand-in (same two-qubit gates, depth and observables, but not the original computation). It answers gate- and readout-error questions only, and validates nothing that depends on what the original circuit computes.

**Comparing ZNE amplifiers fairly.**
- **Running each side.** With `>= 0.50.0`, run gate folding through Method C2 and emulate only PEA, using the same Clifford circuit and the same noise model for both. With `< 0.50.0`, emulate both.
- **Extrapolators.** Change only the amplifier, and report each on a **common extrapolator as well as its own native one**: *baseline / folding-linear / folding-exp / PEA-linear / PEA-exp*. Their default noise-factor grids differ: folding uses `(1, 3, 5)` and PEA uses `(1, 1.5, 2)`. A wide grid supports a stable exponential fit, while a narrow grid can make it blow up (values in the hundreds, or negative). Comparing each only on its default extrapolator measures the grid instead of the amplifier.
- **Noise learning.** A faithful PEA emulation must model the noise-learning phase. Amplify from a *perturbed* copy of the learned rates (a few percent relative error per Pauli term, averaged over several learning seeds), not from the true channel. PEA that learns its noise for free looks unrealistically good.
- **Gains and fit.** Use PEA's small gains (e.g. `[1, 1.2, 1.6]` as in Kim et al., or the default `(1, 1.5, 2)`), scaling the learned rates with the formula in `zne-pea.md`; not integer repetitions. Extrapolate exponential-first with a fallback to linear, as on hardware.

---

## Method B — small-patch density-matrix simulation

**Use for:** error suppression, above all **dynamical decoupling**, and any coherent-error question. Methods A and C are both blind to DD. NEAT's noise is a stochastic Pauli channel, which DD conjugation leaves unchanged, and the coherent dephasing DD actually cancels can't be represented as a stabilizer. The fake-backend Aer model used by Method C is also purely incoherent (depolarizing plus thermal relaxation). Either one reports DD as "no effect" or "slightly harmful", which reflects the noise model, not DD.

A full-size run is neither possible (density-matrix cost grows as ~2^n, which caps out around two dozen qubits) nor needed, because the question is local. Have the subagent run a `method="density_matrix"` `AerSimulator` on a **small representative patch**, for example a 6-qubit line from the target backend's real coupling map.
- **Which patch.** Pick qubits whose idle windows are representative, including the longest windows in the full circuit (from the dynamical-decoupling page, Validation step 1). A workload of 6 qubits or fewer can be simulated whole, at its real layout.
- **Building the patch circuit.** Take the full circuit's schedule restricted to the patch qubits, keeping every gate and Delay in order, and replace each two-qubit gate to a qubit outside the patch with a Delay of the same duration. This keeps the real idle windows; a patch rebuilt from scratch does not have them.

The noise model must contain the error DD acts on, or the test shows nothing:
- **Coherence:** per-qubit T1/T2 from the fake backend `target`.
- **Idle windows:** schedule the patch (`RemoveBarriers`, then `ALAPScheduleAnalysis` + `PadDelay` with the target), and expand each scheduled `Delay` into the idle model. Do not guess idle durations.
- **Coherent component:** a static per-qubit detuning `RZ(δ·τ)` over each idle window, plus thermal relaxation on idles.
- **DD's own cost:** give the inserted X-pulses their own thermal error and a small static amplitude over-rotation `ε`. Model `XpXm` as `X(π+ε)` followed by `X(−(π+ε))`, so the pair cancels `ε`, while `XX` accumulates `2ε`.
- **Sweep δ** from backend-realistic (1–10 kHz) up to exaggerated (~300 kHz), comparing no-DD / XX / XpXm by MAE against the exact ideal.
  - A faithful patch shows DD's MAE staying roughly flat across δ, and gives the crossover δ above which DD is net-positive.
  - The verdict depends on whether that crossover is below or above realistic drift for this backend.
  - Which of `XX` and `XpXm` does better depends on the circuit, so compare both.
- **Parameter points.** Evaluate at parameter values where the observables respond to Z rotations. At Clifford points such as `θ = π/2`, the ideal state can be insensitive to detuning, and DD shows no effect there.

---

## Method C — local testing mode with mitigation applied

**Requires `qiskit-ibm-runtime >= 0.50.0`.** Check with `importlib.metadata.version("qiskit-ibm-runtime")`. On an older version, use Method A instead and recommend upgrading (SKILL.md Phase 0).

**Use for:** TREX, ZNE with gate folding, twirling, and comparing resilience levels, on **EstimatorV2 or SamplerV2** workloads. Do not use it for PEA or PEC: noise learning is not supported in local mode (`NoiseLearnerV3` raises an error there), so use Method A. Do not use it for DD either; use Method B.

From 0.50.0, the client-side primitives (`qiskit_ibm_runtime.executor_estimator.Estimator`, `qiskit_ibm_runtime.executor_sampler.Sampler`) run in [local testing mode](https://quantum.cloud.ibm.com/docs/en/guides/local-testing-mode.md) when `mode` is a fake backend or `AerSimulator`. In that mode they **apply the mitigation and suppression options locally**. For example, `resilience.measure_mitigation = True` really runs TREX. The server-side `qiskit_ibm_runtime.EstimatorV2`/`SamplerV2`, and every version before 0.50.0, ignore every option except shots in local mode, so a with-vs-without comparison through them shows no difference.

The subagent builds the client-side primitive with one of the `mode` choices below. It runs once per candidate configuration, changing only the technique under test, and scores each run against a noiseless reference: MAE for Estimator, or Hellinger / total-variation distance for Sampler.

**Width.** Transpiling to a backend widens the circuit to the backend's full qubit count, and a bug in 0.50.0 then **adds a measurement on every qubit**. So the simulated width is always the *backend's* width, whatever the circuit's. Which simulation method you pick decides whether that is a problem.

### C1 — statevector (real circuit, small backend only)

`mode=FakeManilaV2()` (or another small `Fake*V2`). This runs the researcher's actual, non-Clifford circuit. The reference is `StatevectorEstimator` / `StatevectorSampler` on the logical circuit.
- Statevector simulation tops out around **~30 qubits**, and that limit applies to the backend's **total** qubit count. TREX learning circuits and ZNE noise-scaled copies run at the same width.
- A 2-qubit circuit transpiled for the 156-qubit `FakeKingston` is simulated as 156 qubits and fails with memory or broadcast errors. Never use C1 with a large backend (`FakeKingston`, `FakeTorino`, `FakeFez`, …). Transpile the workload for the small backend instead.
- **Runner script (Estimator).** `scripts/verify_c1.py` takes a `RuntimeEncoder` JSON file of the *logical* circuit and observable (optionally with parameter points), transpiles for the small backend and runs the chosen configurations in parallel. For a parameterized circuit it reports Spearman ρ and whether the lowest-value point matches the ideal one, the measures SKILL.md Phase 1 asks for in optimizer loops. It refuses backends over 30 qubits.
- C1 runs the real circuit with the real technique, so it carries neither a Clifford-stand-in nor an emulation caveat. But the noise comes from a small proxy device, so the absolute error numbers don't carry over to the target.

### C2 — stabilizer (Clifford circuit, any backend width)

Stabilizer simulation scales to full device width, but the circuit must be Clifford. Convert the ISA PUBs first with `Neat(backend).to_clifford(pubs)` or the `ConvertISAToClifford` pass. A non-Clifford circuit fails on this method.
- **Noiseless:** `mode=AerSimulator(method="stabilizer")`. Transpile against the target fake backend and use this run as the ideal reference, or compute the ideal values exactly from the stabilizer state.
- **Noisy:** `mode=AerSimulator.from_backend(FakeManilaV2(), method="stabilizer")`. This uses that fake backend's calibration data.
- **Large backends:** their noise model contains non-Pauli thermal-relaxation (Kraus) channels, which the stabilizer method rejects ("Noise model contains invalid instructions {kraus}"). Drop thermal relaxation: `AerSimulator.from_backend(fb, method="stabilizer", noise_model=NoiseModel.from_backend(fb, thermal_relaxation=False))`. That keeps the gate depolarizing and readout errors.
- **Runner script (Estimator).** `scripts/verify_c2.py` takes the Clifford PUBs (`RuntimeEncoder` JSON) from SKILL.md Phase 1.5 and a fake backend name. It runs the chosen configurations in parallel processes and prints a table of value, std and MAE against the exact ideal, including per-noise-factor values and linear and exponential fits for ZNE. Its docstring lists the configurations; `--fractional` drops gate twirling; pass it only for fractional RZZ gates, since the client-side Estimator twirls RX-only fractional circuits. Give the subagent the command line rather than asking it to write its own scripts.
- C2 can use the researcher's *real target* fake backend, or its live calibration (see below), instead of a proxy device. Like Method A, it answers gate- and readout-error questions only, not anything about what the original circuit computes.

### Cost and repeats

Local runs with mitigation are slow at utility scale. Measured on 0.50.0 with a 156-qubit, 1,056-CZ Clifford circuit on `FakeKingston` noise:

| Configuration | Time per run |
|---|---|
| RL0, precision 0.01 | ~108 s |
| TREX + gate twirling | ~150 s |
| Gate-folding ZNE, factors (1, 3, 5) | over 13 min |

- Estimate the total runtime before launching, and tell the researcher if it exceeds ~15 minutes.
- Use 1 repeat and precision 0.02 by default; the spread between repeats is small compared with the differences between techniques.
- When repeats are needed, use well-separated seeds. Consecutive seeds give near-identical noisy stabilizer runs.
- Get linear and exponential fits from one ZNE run's per-noise-factor values, rather than a separate run per extrapolator.
- Run configurations in parallel (`verify_c2.py --workers`). Aer already uses several threads per run, so wall time is about that of the slowest configuration, not the sum. Measured with a 20-qubit, 380-CZ circuit on `FakeKingston`: RL0, TREX and gate-folding ZNE together took 2 min 23 s.
- Local RL2 runs often report a standard deviation of `inf`. Do not use it for error bars.

---

## Method D — local Executor run with qiskit-mitigation

**Use for:** TREX, gate-folding ZNE, PEA and PEC on Executor workloads built with `qiskit-mitigation`. For PEA or PEC on an Estimator workload it is an alternative to Method A: it runs `qiskit-mitigation`'s PEA/PEC implementation (not the Estimator's) instead of a hand-written emulation. Checked with qiskit-ibm-runtime 0.51.0.dev, qiskit-mitigation 0.1.1 and samplomatic 0.21.0.

The `qiskit-mitigation` guides ([gate folding](https://quantum.cloud.ibm.com/docs/en/addons/qiskit-mitigation/guides/gate-folding-with-custom-extrapolation), [PEA](https://quantum.cloud.ibm.com/docs/en/addons/qiskit-mitigation/guides/pea-with-noise-learning), [PEC with TREX](https://quantum.cloud.ibm.com/docs/en/addons/qiskit-mitigation/guides/pec-with-trex)) run their programs this way:
- **Simulator.** `Executor(AerSimulator(), options={"simulator": {"layer_noise_model": layer_noise_model}})`, where `layer_noise_model` is a list of `(layer, PauliLindbladMap)` pairs for the layers `find_combined_unique_layers([circuit], custom_boxing_options=...)` returns. Use `AerSimulator(method="stabilizer")` for a Clifford circuit at full width; the default method runs the real circuit at small width.
- **Boxing.** Pass `custom_boxing_options` with `"add_tags": "unique_box"` to `prepare`, so the simulator can map the noise model onto the boxes.
- **Simulation flag.** Set `program._semantic_role = "simulation"` before `executor.run(program)`, as the guides do (a private attribute).
- **Measurement boxes.** Leave them out of `layer_noise_model`. A noise entry on a box that mixes gates and measurements raises `TypeError: Unsupported box type`.
- **Readout noise.** `layer_noise_model` adds gate-layer noise only. Without injected readout noise TREX has nothing to correct; the PEC guide injects it with `qiskit-noise-learning`'s `InsertNoisePass`.
- **Noise learning for PEA/PEC.** The guides learn the noise with `qiskit-noise-learning`, whose `NoiseLearner` runs on its own `AerExecutor`, since it is not compatible with the Executor in local mode. Passing the injected noise model in as the "learned" one skips learning error, so PEA and PEC look better than they would after real learning (see Method A, "Noise learning").

On a 4-qubit mirrored Ising circuit (12 CZ layers) with a random Pauli-Lindblad model, all four techniques ran in about 3 s together. Gate folding cut the MAE from 0.15 to under 0.01, and PEA and PEC (with the true noise passed as learned) to 0.02–0.05.

---

## Syntax check for PEA and PEC on the Estimator (hand-built noise map)

`NoiseLearnerV3` does not run in local mode, so a client-side Estimator with `pea` or `pec_mitigation` refuses to run locally (`PEA/PEC mitigation requires a noise model`). To check that a PEA or PEC configuration builds and runs (option paths, fractional `rx` vs `rzz`, the twirling strategy), give it a hand-built model instead:

```python
import numpy as np
from qiskit.quantum_info import PauliLindbladMap, pauli_basis

def random_layer_map(layer, eplg=3e-3, seed=1):
    """Random weight-1/2 Pauli-Lindblad rates on a layer's two-qubit edges.

    Pattern of generate_random_pauli_lindblad_noise in the qiskit-mitigation PEC with TREX guide.
    """
    body = layer.operation.body
    edges = [tuple(body.find_bit(q).index for q in inst.qubits)
             for inst in body.data if inst.operation.num_qubits == 2]
    paulis = [p for p in pauli_basis(2) if np.sum(p.x + p.z)]
    rates = np.random.default_rng(seed).random(len(paulis)) * eplg / len(paulis)
    return PauliLindbladMap.from_sparse_list(
        [(p.to_label(), e, r) for p, r in zip(paulis, rates) for e in edges],
        num_qubits=len(layer.qubits))

estimator.options.resilience.pec_mitigation = True  # or zne_mitigation + zne.amplifier = "pea"
layers = estimator.find_unique_layers(pubs)          # after setting the PEA/PEC option
estimator.options.resilience.layer_noise_model = [(l, random_layer_map(l)) for l in layers]
estimator.run(pubs).result()
```

For an Executor workload, pass the same maps as `noise_maps` to the `qiskit-mitigation` task, keyed by each layer's `InjectNoise` reference (Method D).

**This is a syntax check only.** The values it returns say nothing about how well PEA or PEC works on the workload: the rates are random, and the simulator's own noise is not the model being inverted or amplified. Report it as "builds and runs", never as an accuracy result. Use a small fake backend such as FakeManilaV2, since local Estimator runs on 128-qubit and larger fake backends are slow, with `rx` added to its target when checking fractional gates. Checked against qiskit-ibm-runtime 0.52.0 and qiskit-mitigation 0.1.1.

---

## Checking a Clifford stand-in (Methods A and C2)

Before trusting a Clifford stand-in, check that its ideal values are not all zero. A stand-in whose observables are all ideally 0 measures only shot noise, and every technique looks harmful on it.
- Depth-1 QAOA on a triangle-free graph (including heavy-hex) gives ⟨ZZ⟩ = 0 at every Clifford angle.
- Rounding near-zero starting parameters gives the all-zero circuit, which is nontrivial only for Z-type observables.

If the observables carry no signal, add stabilizer observables of the Clifford circuit (ideal value ±1) and report on those, or choose a different rounding that gives a mix of nonzero ideal values.

---

## Noise-model freshness (Methods A, B and C2)

A `Fake*` backend ships a **one-time calibration snapshot that can be months stale**. You can use current calibration without spending hardware time: `AerSimulator.from_backend(service.backend("ibm_kingston"))`, or `Neat(service.backend(...))`, fetches live calibration and builds the noise model locally, with no queue and no shots.

This needs an authenticated `QiskitRuntimeService`, which reads the researcher's saved IBM token:
- Ask the researcher before doing it.
- Do the fetch, and any simulation that uses it, in the main session. Auto mode blocks credential use by subagents, and blocks passing the fetched calibration to a subagent that was denied. An approval relayed through an agent message does not count.
- Results written under `/tmp` may need a Read permission rule for the main session to read them back.

Otherwise, fall back to the fake backend and note that its calibration may be stale.

If the **qiskit-ibm-runtime MCP server** is connected:
- `get_backend_calibration_tool` returns current T1/T2 and error rates. Use it to report drift from the `Fake*` snapshot, or to source realistic values for Method B.
- `find_optimal_qubit_chains_tool` / `get_coupling_map_tool` can pick the Method B patch qubits.

For C2 on a large live backend, build the noise model with `NoiseModel.from_backend(service.backend(...), thermal_relaxation=False)`, as in C2 above.

These tools return calibration *data*, not a noise model. They need account setup (`setup_ibm_quantum_account_tool`) and may be unavailable in headless runs, so treat them as an aid, not a dependency.
