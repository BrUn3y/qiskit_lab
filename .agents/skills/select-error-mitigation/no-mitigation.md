---
title: No mitigation (baseline)
description: Baseline configuration with all error mitigation and suppression disabled.

capability_id: no-mitigation
name: "No mitigation (baseline)"
category: baseline
short_description: Run circuits on hardware with no error mitigation or suppression applied.

primitive_estimator: true
primitive_sampler: true
primitive_executor: true
output_type: any
estimate_bias: not-applicable

overhead_class: none
overhead_detail: "No additional circuits or shots required."
requires_noise_learning: false
requires_hardware: false

resilience_level_activation: 0
api_class: "qiskit_ibm_runtime.options.EstimatorOptions"
api_guide: "https://quantum.cloud.ibm.com/docs/en/guides/estimator-noise-management.md#resilience"

use_when:
  - "Researching or benchmarking raw hardware noise"
  - "Implementing custom error mitigation outside of Qiskit Runtime"
  - "Running on a statevector or density matrix simulator with no noise model"
  - "Establishing a baseline to measure the effect of a mitigation technique"

avoid_when:
  - "Running on hardware where expectation value accuracy is required"
  - "Readout errors are non-trivial and expectation values are the output"

prerequisites:
  - "EstimatorV2, SamplerV2 or Executor primitive"

compatible_with:
  - any
incompatible_with: []

references: []

related_docs:
  - title: "Overview of noise management techniques"
    url: "https://quantum.cloud.ibm.com/docs/en/guides/error-mitigation-overview.md"
    type: guide
  - title: "Configure noise management with Estimator"
    url: "https://quantum.cloud.ibm.com/docs/en/guides/estimator-noise-management.md"
    type: guide
  - title: "Specify Estimator options"
    url: "https://quantum.cloud.ibm.com/docs/en/guides/estimator-options.md"
    type: guide
  - title: "EstimatorOptions API reference"
    url: "https://quantum.cloud.ibm.com/docs/en/api/qiskit-ibm-runtime/options-estimator-options.md"
    type: api-reference
---

## Summary

Setting `resilience_level = 0` disables all error mitigation and suppression built into Qiskit Runtime. Circuits are executed on hardware as submitted, with no additional calibration circuits, twirling, or post-processing. This is the appropriate configuration when raw hardware results are needed for research, when implementing a custom mitigation strategy, or when establishing an unmitigated baseline for comparison.

## When to use

- You are benchmarking raw hardware performance or studying noise characteristics directly.
- You are implementing custom error mitigation outside of the Qiskit Runtime options framework.
- You are running a noise-free simulation and runtime defaults (such as TREX calibration) would add unnecessary overhead.
- You need an unmitigated baseline to quantify the effect of a specific mitigation technique.

## When not to use

- Any hardware workload where expectation value accuracy is the goal. Readout errors and gate errors are present on all IBM Quantum hardware; even minimal mitigation (TREX at resilience level 1) significantly improves results at low cost.

## Trade-offs

| Dimension | Value |
|---|---|
| Shot overhead | None |
| Circuit execution count | 1× |
| Estimate bias | Full hardware bias (no correction) |
| Learning phase | None |
| Scales with circuit depth | N/A |

## Configuration

```python
# Client-side Estimator (qiskit-ibm-runtime >= 0.50.0); checked against 0.50.0.
from qiskit_ibm_runtime.executor_estimator import Estimator

estimator = Estimator(mode=backend)
estimator.options.resilience_level = 0
```

## Composability

With `resilience_level = 0`, all techniques are disabled. Individual techniques can be re-enabled on top of this setting using explicit option overrides (for example, `estimator.options.resilience.measure_mitigation = True`). Note that any explicitly set option takes precedence over the resilience level default.
