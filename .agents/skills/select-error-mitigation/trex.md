---
title: Twirled Readout Error eXtinction (TREX)
description: Mitigates readout errors in Pauli observable expectation value estimation using twirled measurement sequences and calibration circuits to learn and remove measurement-induced bias.

capability_id: trex
name: "Twirled Readout Error eXtinction (TREX)"
category: expectation-value-mitigation
short_description: Removes measurement-error-induced bias from expectation values by diagonalizing the readout-error transfer matrix via measurement twirling and calibration.

primitive_estimator: true
primitive_sampler: false
primitive_executor: true
output_type: expectation-value
estimate_bias: reduced-bias

overhead_class: low
overhead_detail: "Small number of calibration circuits to learn the readout-error rescaling term, plus measurement twirling overhead (num_randomizations × shots_per_randomization)."
requires_noise_learning: true
requires_hardware: true

resilience_level_activation: 1
api_class: "qiskit_ibm_runtime.options.MeasureNoiseLearningOptions"
api_guide: "https://quantum.cloud.ibm.com/docs/en/guides/error-mitigation-and-suppression-techniques.md#trex"

use_when:
  - "Estimating Pauli observable expectation values on hardware, with EstimatorV2 or the Executor"
  - "Readout (measurement) errors are a known noise source (always present on IBM Quantum hardware)"
  - "Minimal overhead is a priority; TREX is the lowest-cost mitigation technique available"
  - "Used as part of resilience_level 1 (default) or resilience_level 2"
  - "Combining with ZNE or PEC as the measurement-error component of a multi-technique strategy"
  - "Observables have high Pauli weight (readout errors compound with weight, so TREX removes more bias as weight grows)"

avoid_when:
  - "SamplerV2 primitive (TREX does not apply to sampling outputs; use M3 instead)"
  - "resilience_level = 0 research context requiring raw hardware results"
  - "Simulator without a readout noise model (no calibration benefit)"

prerequisites:
  - "EstimatorV2 primitive, or the Executor primitive with qiskit-mitigation (pip install qiskit-mitigation)"
  - "Hardware backend or simulator with a readout noise model"

compatible_with:
  - dynamical-decoupling
  - pauli-twirling
  - zne-gate-folding
  - zne-pea
  - pec
  - pec-slc
  - pna
  - postselection-non-markovian
  - obp
incompatible_with: []

notes_composability: >
  TREX is included in resilience_level 1 (default) and resilience_level 2.
  It handles the measurement-error component of the mitigation stack; ZNE and PEC
  address gate errors. There are no known incompatibilities with other Estimator
  techniques.

references:
  - "van den Berg et al., Phys. Rev. A 105, 032620 (2022)"

related_docs:
  - title: "Error mitigation and suppression techniques: TREX"
    url: "https://quantum.cloud.ibm.com/docs/en/guides/error-mitigation-and-suppression-techniques.md#trex"
    type: guide
  - title: "Overview of noise management techniques"
    url: "https://quantum.cloud.ibm.com/docs/en/guides/error-mitigation-overview.md"
    type: guide
  - title: "Configure noise management with Estimator"
    url: "https://quantum.cloud.ibm.com/docs/en/guides/estimator-noise-management.md"
    type: guide
  - title: "Combine error mitigation options with the Estimator primitive"
    url: "https://quantum.cloud.ibm.com/docs/en/tutorials/combine-error-mitigation-techniques.md"
    type: tutorial
  - title: "ResilienceOptionsV2 API reference"
    url: "https://quantum.cloud.ibm.com/docs/en/api/qiskit-ibm-runtime/options-resilience-options-v2.md"
    type: api-reference
  - title: "MeasureNoiseLearningOptions API reference"
    url: "https://quantum.cloud.ibm.com/docs/en/api/qiskit-ibm-runtime/options-measure-noise-learning-options.md"
    type: api-reference
---

## Summary

TREX mitigates the effect of measurement errors on Pauli observable expectation values. It works by randomly substituting each measurement gate with a sequence consisting of a Pauli X gate, a measurement, and a classical bit flip. This sequence is equivalent to a plain measurement when there are no errors, but in the presence of readout noise it has the effect of diagonalizing the readout-error transfer matrix. A rescaling term is learned from calibration circuits initialized in the zero state. The learned term allows the service to remove the readout-error-induced bias from the estimated expectation value. The technique is designed specifically for Pauli observables. EstimatorV2 applies it through built-in options; with the Executor primitive, `qiskit-mitigation` provides it as a task.

## When to use

- Readout errors are present on the target backend, which is true for all IBM Quantum hardware. TREX is the standard baseline mitigation at minimal cost.
- The goal is to estimate Pauli observable expectation values, with EstimatorV2 or with the Executor and `qiskit-mitigation`.
- Low overhead is required. TREX is the default at `resilience_level = 1` and adds only a small number of calibration circuits alongside the main execution.
- As part of a multi-technique strategy: TREX handles the measurement-error component, while ZNE or PEC handle gate errors.

## When not to use

- SamplerV2 primitive. TREX is defined for expectation value estimation only. For readout error mitigation on sampling outputs, use M3.
- `resilience_level = 0` contexts where raw hardware results are explicitly needed.
- Noise-free simulators where there is no readout noise to calibrate against.

## Trade-offs

| Dimension | Value |
|---|---|
| Shot overhead | Low; calibration circuits are small relative to the main job |
| Circuit execution count | 1× main + calibration circuits (brief learning phase) |
| Estimate bias | Removes readout-error-induced bias; gate error bias is not addressed |
| Learning phase | Yes (short: zero-state calibration circuits) |
| Scales with circuit depth | No; overhead is dominated by the calibration set, not circuit depth |

## Configuration

```python
# Client-side Estimator (qiskit-ibm-runtime >= 0.50.0); checked against 0.50.0.
from qiskit_ibm_runtime.executor_estimator import Estimator

# Option 1: resilience_level (recommended; TREX is the default at level 1)
estimator = Estimator(mode=backend, options={"resilience_level": 1})

# Option 2: explicit
estimator = Estimator(mode=backend)
estimator.options.resilience.measure_mitigation = True
estimator.options.resilience.measure_noise_learning.num_randomizations = 32
```

`measure_noise_learning.shots_per_randomization` is not supported by the client-side Estimator (it raises a `ValidationError` on 0.50.0); one shot count applies to every circuit in the job.

### With the Executor (qiskit-mitigation)

Checked against qiskit-mitigation 0.1.1. `TREX` attaches to any `qiskit-mitigation` task, which adds measurement twirling; `trex.prepare` then adds the TREX calibration circuit, so the readout noise is learned in the same job as the mitigated circuit. See the [PEC with TREX guide](https://quantum.cloud.ibm.com/docs/en/addons/qiskit-mitigation/guides/pec-with-trex).

```python
from qiskit_ibm_runtime import Executor
from qiskit_mitigation import MitigationTask, TREX

trex = TREX()
task = MitigationTask()
program = task.prepare(circuit, observables, parameters, trex=trex)
program = trex.prepare(num_randomizations=300, quantum_program=program)  # adds the calibration circuit
result = task.postprocess(Executor(backend).run(program).result())
```

## Composability

TREX is compatible with all other Estimator mitigation techniques and is recommended as the baseline measurement-error component in any multi-technique strategy. It is automatically included in `resilience_level = 1` and `resilience_level = 2`. There are no incompatibilities with other Qiskit Runtime options. In a circuit with mid-circuit measurements, TREX still mitigates the terminal measurements, but not the mid-circuit ones, because the measurement twirling it relies on applies only to terminal measurements.
