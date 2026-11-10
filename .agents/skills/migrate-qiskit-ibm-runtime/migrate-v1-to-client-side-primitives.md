# Migrate from the V1 primitives to client-side V2 Sampler and Estimator

This guide walks you through migrating code that still uses the original **V1 primitives** —
`Sampler` and `Estimator` with the pre-PUB interface — all the way to the new **client-side**
(Executor-backed) `SamplerV2` / `EstimatorV2` introduced in `qiskit-ibm-runtime` version 0.50.0. It covers the
**IBM Quantum** V1 primitives only. If
your code uses the Qiskit reference implementation of V1 primitives
(`from qiskit.primitives import Sampler, Estimator`), refer to the
[Primitives Features](https://quantum.cloud.ibm.com/docs/api/qiskit/release-notes/1.0#primitives-features) section in the Qiskit 1.0 release notes.

This migration is a **two-part jump**, and both parts happen
together:

1. **The interface changes (V1 → V2).** The old parallel-list `run(circuits, observables,
   parameter_values)` call gives way to the PUB-based `run([...])` interface; results change
   shape (`quasi_dists` / `.values` become `PubResult` data); the flat `Options` object becomes
   an options *tree*; and circuits must be transpiled to the backend's ISA before you submit
   them. This guide documents that part in full.
2. **The implementation changes (server-side → client-side).** Your destination is the same
   client-side V2 primitive that a server-side V2 user migrates to, so this path **inherits
   every change** in the companion guide, *[Migrate from server-side to client-side
   primitives][companion]*. Those changes are summarized under
   [Client-side destination changes](#client-side-destination-changes) and covered in full
   there — this guide does not repeat them.

If your code already uses the V2 interface (PUBs and the options tree) and you only need to
switch from the server-side to the client-side implementation, reach for the companion guide
instead — this one is for code still written against the V1 interface.

## Overview

`Sampler` and `Estimator` are primitive *interfaces* defined in Qiskit. Their first generation —
the **V1 primitives** — took several equal-length lists (circuits, observables, parameter values), zipped them together internally, returned bespoke result objects (quasi-distributions for
Sampler, expectation values for Estimator), and were configured through a single flat `Options`
object. The primitives also transpiled your circuits for you.

The **V2 primitives** reorganize that interface around the **primitive unified bloc (PUB)**: a
single circuit together with the observables (Estimator only) and parameter-value sets to evaluate
on it. Grouping the inputs this way lets you specify sweeps over parameter values and observables
far more efficiently. Results are returned per PUB, and options live in a typed tree.

In addition to the interface changes, IBM Quantum's implementation of V2 primitives also receives a few updates:

- To reduce the total job execution time, V2 primitives only accept circuits and observables expressed in the instructions the target QPU (quantum processing unit) supports — known as instruction set architecture (ISA) circuits and observables.

- `SamplerV2` is pared back to its core task: sampling the output registers of a circuit. It returns
the raw per-shot measurements (no quasi-probability weights), separated by the output register
names the circuit defines.

- `EstimatorV2` keeps `resilience_level` as the single knob for how much error resilience to apply,
and adds the flexibility to turn individual error mitigation and suppression methods on or off and
tune them to your needs.

Starting in `qiskit-ibm-runtime` 0.50.0, `SamplerV2` and `EstimatorV2` are themselves
re-implemented on the **client side** on top of the Executor primitive, giving you a white-box
view of what runs. That release also **deprecates** the server-side `SamplerV2` / `EstimatorV2`
classes in favor of the client-side ones, so they are the destination to target.

This guide takes you from the V1 interface directly to those client-side V2 primitives.

> **This guide covers the IBM Quantum Compute (formerly Qiskit
> Runtime) primitives only** — its client-side destination and the error mitigation and
> suppression features are specific to IBM Quantum Compute. If you are migrating implementations from other vendors, use their specific guides.

## Is your code still on V1?

Since `qiskit-ibm-runtime` 0.28.0, the top-level `Sampler` / `Estimator` names already resolve to
the **V2** primitives, and `Options` resolves to `OptionsV2` — the original V1 classes are gone, because IBM Quantum Compute Service no longer supports them.
An import line alone therefore won't tell you whether the code you're reading was written against
V1. The reliable signals are the V1 *behaviors*:

- `run()` is called with **parallel lists** — `run([circuit] * n, [obs...], [vals...])` — rather
  than a list of PUB tuples.
- The code reads `result.quasi_dists` (V1 Sampler) or `result.values` (V1 Estimator).
- A flat `Options()` object is configured with `options.resilience_level = ...` /
  `options.optimization_level = ...`, or the primitive is tuned with `primitive.set_options(...)`.
- Observables are passed without being laid out onto an ISA circuit, or circuits are submitted
  that were never transpiled to the target.

If you recognize these patterns, the sections below walk you through updating each one.

## Older V1 syntax you may need to modernize first

The V1 primitives were introduced back in `qiskit-ibm-runtime` 0.2.0, and their own interface
changed substantially before settling into the `run(circuits, observables, parameter_values)`
shape that the rest of this guide assumes. If the code you're migrating predates that shape,
normalize these legacy forms **first** — each one maps onto the modern V1 shape, and then the
sections below carry it the rest of the way to client-side V2.

| Legacy form (introduced → removed) | What to do |
| ---------------------------------- | ---------- |
| `IBMSampler` / `IBMEstimator` factory classes — `IBMSampler(service=..., backend=...)` returning a callable factory (0.2.0 → removed in 0.5.0 / 0.6.0) | Replace with `Sampler` / `Estimator`, which this guide then migrates to `SamplerV2` / `EstimatorV2`. |
| `IBMRuntimeService` (renamed in 0.4.0 → removed in 0.6.0) | Use `QiskitRuntimeService`. |
| `auth=` on the service constructor (replaced by `channel=` in 0.3.0) | Use `channel=`. On a current runtime, prefer `channel="ibm_quantum_platform"` — the old `channel="ibm_quantum"` value was removed in 0.42.0, and while `channel="ibm_cloud"` still works, `ibm_quantum_platform` is the preferred value. |
| Inputs passed to the **constructor** and the primitive used as a **context manager** — `with Estimator(circuits=[qc], observables=..., parameters=..., service=...) as estimator:` (deprecated 0.7.0rc1 → removed 0.9.4) | Move circuits / observables / parameter values out of the constructor and into `run()` (then into PUBs, per [From parallel lists to PUBs](#from-parallel-lists-to-pubs-the-run-interface)). Drop `service=` — it no longer exists. |
| `sampler.close()` / `estimator.close()` to close the session (deprecated 0.7 → removed 0.9.4) | Close the session itself: `session.close()`, or let a `with Session(...) as session:` block close it on exit. The primitive's `close()` only ever called `self._session.close()`, so this is a change of receiver, not of behavior. No V2 primitive has a `close()` method. |
| Calling the primitive object **directly** with integer index inputs — `estimator(circuit_indices=[0], observable_indices=[0], parameter_values=...)` (indices deprecated 0.5.0 → removed 0.15.0; the direct call was superseded by `.run()`) | Call `.run(...)` and pass the circuit / observable **objects**, not indices into a pre-registered list. |
| Reading `job.job_id` / `job.backend` as **attributes** on the returned job — these were properties in early releases, then deprecated and removed as attributes in 0.9.2 | Call them as **methods**: `job.job_id()` and `job.backend()`. |
| `skip_transpilation=` or `transpilation_settings=` as **constructor arguments** (`skip_transpilation` moved to `options.transpilation` in 0.7.0rc1 → removed 0.9.4; `transpilation_settings` removed in 0.7.0rc1) | V2 does not transpile at all, so there is nothing to skip or configure — remove them and transpile the circuit yourself (see [Transpilation](#transpilation-isa-circuits-are-required)). |
| `resilience_settings=` constructor argument (removed in 0.7.0rc1) | Configure error resilience through the V2 `options.resilience` tree instead (see [Options](#options-from-the-options-object-to-the-options-tree)). |
| `max_time=` constructor argument (removed in 0.7.0rc1) | Set the maximum time on the execution mode you pass as `mode=`, not on the primitive — for example `Session(backend=backend, max_time="2h")` (or `Batch(...)`). |
| First constructor argument being `session` (changed to `backend` in 0.11.0), a positional/`session=` **backend name**, or `options={"backend": "ibm..."}` | Bind execution with `mode=<backend object>` instead (see [Bind the backend with `mode=`](#bind-the-backend-with-mode)). |

Once these are normalized, the code is in the "modern V1" shape and the sections below complete
the migration.

## Update your imports

Import the client-side implementations from their dedicated modules, and drop the V1 `Options`
import — you no longer construct a single flat `Options` object (see
[Options](#options-from-the-options-object-to-the-options-tree) for what replaces it):

```python
# V1
from qiskit_ibm_runtime import Sampler, Estimator, Options

# Client-side V2
from qiskit_ibm_runtime.executor_sampler import Sampler
from qiskit_ibm_runtime.executor_estimator import Estimator
```

Avoid `from qiskit_ibm_runtime import SamplerV2, EstimatorV2` for now. Today that top-level form
resolves to the *server-side* V2 implementation, not the client-side one. It will resolve to the
client-side implementation in a future release, at which point the explicit module imports above
become optional.

## Bind the backend with `mode=`

V1 bound execution through the `backend=` or `session=` constructor arguments (or a positional
backend). Client-side V2 takes a single `mode=` argument, which accepts a `Backend`, `Session`,
or `Batch`:

```python
# V1
estimator = Estimator(backend=backend, options=options)
# inside a session:  estimator = Estimator(session=session, options=options)

# Client-side V2
estimator = EstimatorV2(mode=backend, options=options)
# inside a batch/session:  estimator = EstimatorV2(mode=batch)
```

Two things to watch for:

- **`backend=` and `session=` are gone entirely.** The client-side constructor takes only `mode` and `options`. Move the backend, session, or batch into `mode`.
- **A backend *name* string is no longer accepted.** V1 let you pass `backend="ibm_torino"` and
  resolved the name against your default account. `mode=` requires an actual backend object, so
  fetch it from the service first:

  ```python
  # V1 — a backend name string was resolved for you
  sampler = Sampler(backend="ibm_torino")

  # Client-side V2 — pass the backend object
  service = QiskitRuntimeService()
  backend = service.backend("ibm_torino")
  sampler = SamplerV2(mode=backend)
  ```

## From parallel lists to PUBs (the `run()` interface)

This is the heart of the migration. V1 took several equal-length lists and zipped them together;
V2 takes a list of **primitive unified blocs (PUBs)**, where each PUB is a tuple of **one**
circuit plus the data broadcast onto it, and each PUB produces one result.

- **Sampler PUB:** `(circuit, parameter_values, shots)` — `parameter_values` and `shots` are
  optional.
- **Estimator PUB:** `(circuit, observables, parameter_values, precision)` —
  `parameter_values` and `precision` are optional.

If you previously specifies multiple copies of the same circuit, or the same `circuit_indices` (if on older format), they can now be consolidated into a single PUB.

Observables and parameter values in a PBU are combine according to
[NumPy broadcasting rules](https://numpy.org/doc/stable/user/basics.broadcasting.html). You can
also pass `shots` (Sampler) or `precision` (Estimator) once to `run()` to apply it to every PUB.

The examples below show the same computations expressed in both interfaces.

### Sampler

```python
# V1: one circuit, three parameter sets
job = sampler.run([circuit] * 3, [vals1, vals2, vals3])

# Client-side V2: one PUB carrying the circuit and all three parameter sets
job = sampler.run([(isa_circuit, [vals1, vals2, vals3])])
```

```python
# V1: two circuits, one shared parameter set
job = sampler.run([circuit1, circuit2], [vals1] * 2)

# Client-side V2: one PUB per circuit
job = sampler.run([(isa_circuit1, vals1), (isa_circuit2, vals1)])
```

### Estimator

```python
# V1: one circuit, four observables
job = estimator.run([circuit] * 4, [obs1, obs2, obs3, obs4])

# Client-side V2: one PUB carrying the circuit and all four observables
job = estimator.run([(isa_circuit, [obs1, obs2, obs3, obs4])])
```

When you want to combine observables and parameter sets as an outer product, reshape them so that
broadcasting produces the grid you're after. For example, observables of shape `(4, 1)` combined
with parameter sets of shape `(1, 6)` give a `(4, 6)` result:

```python
reshaped_ops = np.fromiter(isa_observables, dtype=object).reshape((4, 1))
job = estimator.run([(isa_circuit, reshaped_ops, parameter_sets)])   # parameter_sets shape (1, 6) → (6,)
evs = job.result()[0].data.evs   # shape (4, 6)
```

### Options specified in run()

V1 primitive also let you override arbitrary options per call by passing them as keyword arguments
to `run()`. V2
`run()` accepts **only** `shots` (Sampler) or `precision` (Estimator); set everything else on the
primitive's `options` before you submit:

```python
# V1 - arbitrary options specified in run()
estimator.run(..., shots=2048)
estimator.run(..., resilience_level=1)

# Client-side V2 — use primitive's options
estimator.options.default_shots = 2048
estimator.options.resilience_level = 1
estimator.run(...)
```

Not all V1 options map directly to V2 options. See [Changes to available options](#changes-to-available-options)
section for a summary table.


## Observables must be `SparsePauliOp`, laid out per PUB (Estimator only)

Each Estimator PUB needs a `SparsePauliOp` (or a compatible operator) that has been laid out onto
the **same ISA circuit** used in that PUB. Lay observables out with `apply_layout` against the
transpiled circuit's `layout`:

```python
from qiskit.quantum_info import SparsePauliOp

observable = SparsePauliOp.from_list([("ZZ", 1), ("XX", 0.5)])
isa_obs = observable.apply_layout(isa_circuit.layout)   # match the circuit in the PUB
job = estimator.run([(isa_circuit, isa_obs)])
```

## Options: from the `Options` object to the options tree

### Changes to how options are set

V2 replaces V1's single flat `Options` object with a **per-primitive, typed options object**:
[`SamplerOptions`](https://quantum.cloud.ibm.com/docs/api/qiskit-ibm-runtime/options-sampler-options) for `SamplerV2` and [`EstimatorOptions`](https://quantum.cloud.ibm.com/docs/api/qiskit-ibm-runtime/options-estimator-options) for `EstimatorV2`.

V2 options can be specified when initializing a primitive, passed in either as an instance of the options class or a dictionary.
After initialization, options can be set as attributes (for example, `options.twirling.enable_gates`) to take advantage of auto-complete, or use the update() method to make bulk updates.

```python
# V1
options = Options()
options.resilience_level = 2
options.optimization_level = 1
estimator = Estimator(backend=backend, options=options)
estimator.set_options(shots=4000)
```
```python
# Client-side V2
from qiskit_ibm_runtime.executor_estimator import Estimator
from qiskit_ibm_runtime.options_models import EstimatorOptions

# Specifying options when initializing a primitive
# ... as a dictionary
estimator = EstimatorV2(mode=backend, options={"resilience_level": 2})
# ... or as attributes
options = EstimatorOptions()
options.resilience.zne_mitigation = True
options.resilience.zne.noise_factors = [1, 3, 5]
estimator = Estimator(mode=backend, options=options)

# Updating options after initialization
# ... as attributes
estimator.options.default_shots = 4000
# ... or via buik updates
estimator.options.update(
    default_precision=0.02, resilience={"zne_mitigation": True}
)
```

### Changes to available options

A few V1 options change meaning or disappear entirely. Work through this checklist:

| V1 option / behavior | Client-side V2 |
| -------------------- | -------------- |
| Flat `Options` object + `set_options()` | The single shared `Options` object and `set_options()` are gone. Configure the primitive's own options (`SamplerOptions` / `EstimatorOptions`) through the tree, an `options={...}` dictionary, or `.options.update(...)`. |
| `optimization_level` | Not supported — V2 does not transpile. Transpile the circuit yourself (see [Transpilation](#transpilation-isa-circuits-are-required)). |
| The rest of the `transpilation` group — `skip_transpilation`, `initial_layout`, `layout_method`, `routing_method`, `approximation_degree` | Removed along with `optimization_level` — V2 has no `transpilation` options at all. Control layout, routing, and translation through your own `generate_preset_pass_manager(...)` / `PassManager` (see [Transpilation](#transpilation-isa-circuits-are-required)). |
| `execution.shots` | Sampler: set `options.default_shots` or pass `run(pubs, shots=...)`. Estimator: the number of shots is based on the target precision, which is set with `options.default_precision` or `run(pubs, precision=...)`; `options.default_shots` is also available. `options.execution.init_qubits` is unchanged. |
| `resilience_level` on **Sampler** | Not supported — Sampler returns raw samples with no post-processing. Remove it and apply any readout handling yourself, such as the [mthree](https://github.com/Qiskit/qiskit-addon-mthree) measurement mitigation. |
| `resilience_level = 3` on **Estimator** (PEC) | Not supported as a level. Set `options.resilience.pec_mitigation = True` **and** perform explicit noise learning — see [Client-side destination changes](#client-side-destination-changes). |
| `resilience_level` 0–2 on **Estimator** | Supported. You can also toggle individual methods (`options.resilience.measure_mitigation`, `options.resilience.zne_mitigation`, and so on). |
| `ResilienceOptions` (`noise_factors`, `noise_amplifier`, and `extrapolator`) | V1 Estimator only supports ZNE as the gate-level error mitigation method, so these options map to [`ZneOptions`](https://quantum.cloud.ibm.com/docs/api/qiskit-ibm-runtime/options-zne-options) in V2 Estimator. <br> For the `noise_amplifier` to `zne.amplifier` mapping, `TwoQubitAmplifier`, `LocalFoldingAmplifier`, and `CxAmplifier` are close to `gate_folding`. There is no equivalnet option for `GlobalFoldingAmplifier`.  <br> For the `extrapolator` to `zne.extrapolator` mapping, `LinearExtrapolator` maps to `linear`; <br> `QuadraticExtrapolator` maps to `polynomial_degree_2`; <br> `CubicExtrapolator` maps to `polynomial_degree_3`; `QuarticExtrapolator` maps to `polynomial_degree_4` |

Refer to [Introduction to options](https://quantum.cloud.ibm.com/docs/guides/runtime-options-overview) for more information.

## Results: from `.quasi_dists` / `.values` to `PubResult` data

V2 primitives continue to return samples (Sampler) and expectation values (Estimator). But the job results are now returned as a [`PrimitiveResult`](https://quantum.cloud.ibm.com/docs/api/qiskit/qiskit.primitives.PrimitiveResult) container object.
The `PrimitiveResult` contains an iterable list of [`PubResult`](https://quantum.cloud.ibm.com/docs/api/qiskit/qiskit.primitives.PubResult) objects, one for each input PUB and are indexed positionally.

Each `PubResult` possess both a `data` and a `metadata` attribute. The `data` attribute is a customized [`DataBin`](https://quantum.cloud.ibm.com/docs/api/qiskit/qiskit.primitives.DataBin) that contains  the actual measurement values (samples or expectation values).

- **Sampler.** V1 returned `result.quasi_dists` (quasi-probability distributions). V2 returns per-shot bitstrings, organized by the
  circuit's **classical register name**. The convenience method `get_counts()` returns a dictionary mapping bitstrings to the number of times that they occurred:

  ```python
  # This returns the histogram of measurements from
  # the classical resigter "meas" for the first PUB
  counts = job.result()[0].data.meas.get_counts()
  ```

  `meas` is the default register name produced by `measure_all()`. If you created named classical
  registers, use those names instead (you can find them with `circuit.cregs`) — for example,
  `job.result()[0].data.alpha.get_counts()`.

  If you relied on the old V1 quasi-distribution shape, you can reconstruct it by dividing the
  counts by the shot count:

  ```python
  v1_format = [
      {int(bitstring, 2): count / shots for bitstring, count in pub.data.meas.get_counts().items()}
      for pub in job.result()
  ]
  ```

- **Estimator.** V1 returned `result.values`. V2's `PubResult` data carries both the expectation values and their standard errors:

  ```python
  pub_result = job.result()[0]
  evs = pub_result.data.evs
  stds = pub_result.data.stds     # V1 exposed variance in metadata instead
  ```

## Transpilation: ISA circuits are required

V2 primitives execute only circuits and observables that already conform to the target QPU's
Instruction Set Architecture (ISA) — they do **not** perform layout, routing, or translation on
your behalf. Transpile before you submit, and lay observables out against the transpiled circuit:

```python
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager

pm = generate_preset_pass_manager(optimization_level=1, backend=backend)
isa_circuit = pm.run(circuit)
isa_obs = observable.apply_layout(isa_circuit.layout)   # Estimator
```

This is also why the V1 `optimization_level` option no longer applies: you now set the
optimization level on the pass manager, as shown above.

## Job status

The V2 `run()` returns a `RuntimeJobV2`, whose `status()` returns a **string** (for example,
`"RUNNING"` or `"DONE"`) rather than the `JobStatus` enum V1 returned. Update any code that
compares against the enum:

```python
# V1
from qiskit.providers.jobstatus import JobStatus
running = job.status() is JobStatus.RUNNING

# V2
running = job.status() == "RUNNING"
```

## Full examples

### Sampler example (parameterized circuit)

```python
import numpy as np
from qiskit.circuit.library import RealAmplitudes
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit_ibm_runtime import QiskitRuntimeService
from qiskit_ibm_runtime.executor_sampler import Sampler  # client-side V2 Sampler

circuit = RealAmplitudes(num_qubits=5, reps=2)
circuit.measure_all()

rng = np.random.default_rng(1234)
parameter_values = [rng.uniform(-np.pi, np.pi, size=circuit.num_parameters) for _ in range(3)]

service = QiskitRuntimeService()
backend = service.least_busy(operational=True, simulator=False)

pm = generate_preset_pass_manager(optimization_level=1, backend=backend)
isa_circuit = pm.run(circuit)

sampler = SamplerV2(mode=backend)
job = sampler.run([(isa_circuit, parameter_values)])
print(job.result()[0].data.meas.get_counts())
```

### Sampler example (multiple circuits in a job)

```python
import numpy as np
from qiskit.circuit.library import IQP
from qiskit.quantum_info import random_hermitian
from qiskit_ibm_runtime import QiskitRuntimeService
from qiskit_ibm_runtime.executor_sampler import Sampler

service = QiskitRuntimeService()
backend = service.least_busy(operational=True, simulator=False)

rng = np.random.default_rng()
mats = [np.real(random_hermitian(5, seed=rng)) for _ in range(3)]
circuits = [IQP(mat) for mat in mats]
for circuit in circuits:
   circuit.measure_all()

pm = generate_preset_pass_manager(backend=backend, optimization_level=1)
isa_circuits = pm.run(circuits)

sampler = Sampler(backend)
# Turn on dynamical decoupling with sequence XpXm.
sampler.options.dynamical_decoupling.enable = True
sampler.options.dynamical_decoupling.sequence_type = "XpXm"

job = sampler.run(isa_circuits)
result = job.result()

for idx, pub_result in enumerate(result):
   print(f" > Counts for pub {idx}: {pub_result.data.meas.get_counts()}")
```

### Sampler example (multiple output registers)

```python
from qiskit import ClassicalRegister, QuantumRegister, QuantumCircuit
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit_ibm_runtime import QiskitRuntimeService
from qiskit_ibm_runtime.executor_sampler import Sampler


alpha = ClassicalRegister(5, "alpha")
beta = ClassicalRegister(7, "beta")
qreg = QuantumRegister(12)

circuit = QuantumCircuit(qreg, alpha, beta)
circuit.h(0)
circuit.measure(qreg[:5], alpha)
circuit.measure(qreg[5:], beta)

service = QiskitRuntimeService()
backend = service.least_busy(operational=True, simulator=False)

pm = generate_preset_pass_manager(backend=backend, optimization_level=1)
isa_circuit = pm.run(circuit)

sampler = Sampler(backend)
job = sampler.run([isa_circuit])
result = job.result()

# Get results for the first (and only) PUB
pub_result = result[0]
print(f" >> Counts for the alpha output register: "
f"{pub_result.data.alpha.get_counts()}")
print(f" >> Counts for the beta output register: "
f"{pub_result.data.beta.get_counts()}")
```

### Estimator example (parameterized circuit)

```python
import numpy as np
from qiskit.circuit import QuantumCircuit, Parameter
from qiskit.quantum_info import SparsePauliOp
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit_ibm_runtime import QiskitRuntimeService
from qiskit_ibm_runtime.executor_estimator import EstimatorV2

theta = Parameter("θ")
circuit = QuantumCircuit(2)
circuit.h(0)
circuit.cx(0, 1)
circuit.ry(theta, 0)

phases = [[ph] for ph in np.linspace(0, 2 * np.pi, 21)]
ops = [SparsePauliOp.from_list([(p, 1)]) for p in ("ZZ", "ZX", "XZ", "XX")]

service = QiskitRuntimeService()
backend = service.least_busy(operational=True, simulator=False)

pm = generate_preset_pass_manager(optimization_level=1, backend=backend)
isa_circuit = pm.run(circuit)
isa_ops = np.fromiter(
    (op.apply_layout(isa_circuit.layout) for op in ops), dtype=object
).reshape((4, 1))

estimator = EstimatorV2(mode=backend, options={"default_shots": int(1e4)})
job = estimator.run([(isa_circuit, isa_ops, phases)])
pub_result = job.result()[0]
print(pub_result.data.evs)    # shape (4, 21)
print(pub_result.data.stds)
```

### Estimator example (with noise learning)

```python
from qiskit.circuit import QuantumCircuit
from qiskit.quantum_info import SparsePauliOp
from qiskit.quantum_info import PauliLindbladMap
from qiskit.transpiler import generate_preset_pass_manager

from qiskit_ibm_runtime import NoiseLearnerV3, QiskitRuntimeService
from qiskit_ibm_runtime.executor_estimator import Estimator

# Create the circuit and observable
circuit = QuantumCircuit(2)
circuit.cx(0, 1)
circuit.measure_all()
observable = SparsePauliOp("ZZ")

service = QiskitRuntimeService()
backend = service.least_busy(operational=True, simulator=False)

# Transpile to target ISA
preset_pass_manager = generate_preset_pass_manager(backend=backend, optimization_level=0)
isa_circuit = preset_pass_manager.run(circuit)
isa_observable = observable.apply_layout(isa_circuit.layout)

pubs = [(isa_circuit, isa_observable)]

estimator = Estimator(backend)
estimator.options.resilience.pec_mitigation = True

# Identify the unique layers to learn.
layers = estimator.find_unique_layers(pubs)

# Learn the noise model for those layers (runs as a separate job).
learner = NoiseLearnerV3(backend)
learner_job = learner.run(layers)
learner_result = learner_job.result()

# Convert results to Pauli-Lindblad noise maps.
pauli_lindblad_maps = learner_result.to_pauli_lindblad_maps()

# Assign the learned noise maps so PEA/PEC uses them.
estimator.options.resilience.layer_noise_model = zip(layers, pauli_lindblad_maps)

# Now execute the target PUBs.
job = estimator.run(pubs)
pub_result = job.result()[0]
print(pub_result.data.evs)
print(pub_result.data.stds)
```

## Client-side destination changes

Because your destination is the client-side (Executor-backed) V2 primitive, this migration
**also inherits every change** described in the companion guide,
*[Migrate from server-side to client-side primitives][companion]*. Once you've updated the
interface using the sections above, work through that guide's two incompatible-changes tables
(one for Sampler, one for Estimator) as well. In brief, they cover:

- The underlying primitive is now **Executor**: the IBM Quantum Platform UI and `job.primitive_id`
  show `executor`, and `job.inputs` returns Executor inputs.
- More processing happens on the client side, so `run()` and `result()` can take longer — enable
  INFO logging to follow the progress.
- Result-metadata data types are restricted to `str` / `float` / `int` / `bool` and lists or
  dictionaries of those.
- Some input validation has moved server-side and now raises `RuntimeError` rather than
  `IBMInputValueError`.
- **There is no more implicit noise learning for PEA and PEC.** If you enable `pec_mitigation` or
  `pea_mitigation` (including the V1 `resilience_level = 3` → PEC case above), you must learn the
  noise model explicitly with `NoiseLearnerV3` and assign
  `options.resilience.layer_noise_model`. TREX measurement-noise learning still works as before.
- `MeasureNoiseLearningOptions.shots_per_randomization` and the `seed_estimator` option have been
  removed.
- Mixed shot values (Sampler) or precision values (Estimator) in a single job are no longer
  supported — split into one job per value, optionally under a `Batch`.

## References

- [Migrate from server-side to client-side primitives][companion] — the companion guide; its
  client-side changes apply here too
- [Directed execution model][dem]
- [Primitive inputs and outputs (PUBs)](https://quantum.cloud.ibm.com/docs/guides/primitive-input-output#pubs)
- [Estimator inputs and outputs](https://quantum.cloud.ibm.com/docs/guides/estimator-input-output) / [Specify Estimator options](https://quantum.cloud.ibm.com/docs/guides/estimator-options)
- [Sampler inputs and outputs](https://quantum.cloud.ibm.com/docs/guides/sampler-input-output) / [Specify Sampler options](https://quantum.cloud.ibm.com/docs/guides/sampler-options)
- [Transpile circuits](https://quantum.cloud.ibm.com/docs/guides/transpile)

[companion]: https://quantum.cloud.ibm.com/docs/guides/migrate-to-client-side-primitives
[dem]: https://quantum.cloud.ibm.com/docs/guides/directed-execution-model
