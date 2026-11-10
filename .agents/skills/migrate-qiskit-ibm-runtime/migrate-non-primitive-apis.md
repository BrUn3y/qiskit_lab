# Migrate IBM Quantum Compute Service APIs

`qiskit-ibm-runtime` is the client SDK used to communicate with the IBM Quantum Compute Service. Most of its migration attention goes to the primitives, but plenty has changed
*around* them, such as how you authenticate and how you look up a backend.

This guide collects those changes. Each section says what changed, in which release, and what to
write instead.

The primitives themselves have their own guides:

- [Migrate from the V1 primitives to client-side Sampler and Estimator](migrate-v1-to-client-side-primitives.md)
  — if your code still uses `quasi_dists`, `.values`, or the parallel-list `run()`.
- [Migrate from server-side to client-side Sampler and Estimator](https://quantum.cloud.ibm.com/docs/guides/migrate-to-client-side-primitives)
  — if you already use the V2 interface and want the Executor-backed implementation.
- [Migrate older SamplerV2 and EstimatorV2 option forms](migrate-older-v2-primitives.md)
  — if you pass a flat options dict or `optimization_level`.

## Do you need this guide?

You do if any of the following appear in your code:

- `QiskitRuntimeService(auth=...)`, `channel="ibm_quantum"`, or a `channel_strategy=` argument.
- `service.get_backend(...)`, or a bare `service.backend()` with no backend name.
- `service.runtime` — for example `service.runtime.backends()`.
- `backend.run(...)`, or reads of the old `Result` object (`result.get_counts()`).
- A primitive, `Session`, or `Batch` constructed with `backend=`, `session=`, `service=`, or a
  backend **name string** instead of a backend object.
- `service.open(...)`, `backend.open_session(...)`, or `backend.close_session()`.
- A primitive given a `mode=` backend from inside an open `Session` or `Batch` context manager.
- `job.stream_results(...)`, `job.interim_results(...)`, or a `callback=` expecting interim data.
- `service.upload_program(...)`, `service.run(program_id=...)`, `RuntimeProgram`, or
  `RuntimeOptions`.
- `job.program_id`, a comparison against qiskit's `JobStatus` enum, `job.queue_info()`,
  `job.queue_usage()`, or `service.check_pending_jobs()`.
- `backend.max_shots`, `backend.max_experiments`, `backend.max_circuits`, or `backend.defaults()`.
- A retired cloud simulator: `ibmq_qasm_simulator`, `simulator_statevector`, `simulator_mps`,
  `simulator_stabilizer`, or `simulator_extended_stabilizer`.
- `qiskit.pulse`, a `ScheduleBlock`, `circuit.add_calibration(...)`, or an `RXCalibrationBuilder` /
  `RZXCalibrationBuilder` pass.
- A V1 fake backend (`FakeManila`, the old `FakeProvider`), or pulse-level access
  (`PulseDefaults`, `backend.drive_channel(...)`).
- `.generators` / `.rates` read from a noise-learner result, or a `post_selection` option on
  `NoiseLearnerV3`.

## What this guide covers

| Area | What changed | Section |
| ---- | ------------ | ------- |
| Service | `auth=` → `channel=`; the `ibm_quantum` channel is gone | [Account setup](#account-setup-auth--channel-and-the-ibm_quantum-channel-sunset) |
| Service | `channel_strategy="q-ctrl"` moved to a Qiskit Function | [The `channel_strategy` parameter](#the-channel_strategy-q-ctrl-parameter) |
| Service | `service.runtime` removed | [The `runtime` attribute](#the-qiskitruntimeserviceruntime-attribute) |
| Execution | `backend=` / `session=` / name strings → `mode=` | [Execution binding](#execution-binding-backend--session--mode) |
| Execution | `Session.from_id()` lost `backend`; `service` is required | [`Session.from_id()`](#sessionfrom_id-no-backend-and-service-is-required) |
| Execution | `service.open()` and `backend.open_session()` removed | [Opening a session](#opening-a-session-serviceopen-and-backendopen_session) |
| Execution | A primitive inside a session must use the session's backend | [One backend per session](#one-backend-per-session) |
| Execution | `backend.run()` removed | [Running circuits](#running-circuits-backendrun--the-v2-primitives) |
| Execution | Streaming and interim-result callbacks removed | [Result streaming](#result-streaming-and-interim-result-callbacks) |
| Execution | Pulse gates rejected by the service since Feb 2025 | [Pulse gates](#pulse-gates-are-no-longer-supported) |
| Execution | Pulse-level access removed | [Pulse-level access](#pulse-level-access) |
| Programs | Custom runtime programs removed | [Custom runtime programs](#custom-runtime-programs) |
| Programs | `RuntimeOptions` deprecated | [The `RuntimeOptions` class](#the-runtimeoptions-class) |
| Jobs | `RuntimeJob` → `RuntimeJobV2`; `status()` returns a string | [Job objects](#job-objects-runtimejob--runtimejobv2-and-program_id--primitive_id) |
| Jobs | Queue introspection helpers removed | [Queue and job-management helpers](#queue-and-job-management-helpers) |
| Jobs | Noise-learner `.generators` / `.rates` moved behind `.error` | [Noise-learner results](#noise-learner-results-generators--rates--error) |
| Options | `NoiseLearnerV3`'s `post_selection` renamed | [Noise learning](#noise-learning-post_selection--bit_flip_checkspost_circuit) |
| Backend | `get_backend()` removed; `name` is now required | [Backend lookup](#backend-lookup-get_backend--backendname) |
| Backend | `max_shots` / `max_experiments` / `max_circuits` gone | [Backend limits](#backend-limits-max_shots-max_experiments-max_circuits) |
| Backend | Cloud simulators retired; simulate locally | [Cloud simulators](#cloud-simulators-are-retired-simulate-locally-run-on-a-qpu) |
| Backend | V1 fake backends removed | [Fake V1 backends](#fake-v1-backends-and-fakeprovider) |

---

## Account setup: `auth=` → `channel=` and the `ibm_quantum` channel sunset

The account and authentication surface on `QiskitRuntimeService` (and on `save_account`,
`saved_accounts`, and `delete_account`) changed twice:

- The `auth=` keyword was replaced by `channel=` in **0.3.0**.
- The `channel="ibm_quantum"` value — the classic IBM Quantum Experience — was deprecated across the
  0.30.0 → 0.41.0 window and **removed by 0.42.0**. The classic platform itself was retired; work
  now runs on the IBM Quantum Platform on IBM Cloud.

| # | Incompatible change | Migration action |
| - | ------------------- | ---------------- |
| 1 | `QiskitRuntimeService(auth=...)` / `save_account(auth=...)` | Rename `auth=` to `channel=`. The accepted values are unchanged at this step. |
| 2 | `channel="ibm_quantum"` (including in `save_account`) | Switch to `channel="ibm_quantum_platform"`. `channel="ibm_cloud"` also still works as an alias for the cloud platform. This is more than a string swap: your **token** and **instance** (a CRN, rather than the classic `hub/group/project`) are usually different on the cloud platform, so have your cloud credentials to hand before you edit. |
| 3 | A saved account created against the classic channel | Re-save it. An entry in `~/.qiskit/qiskit-ibm.json` pinned to `ibm_quantum` keeps a token that the cloud platform will not accept — re-run `save_account` with your cloud token and instance rather than editing the channel string in place. |

The current setup pattern:

```python
from qiskit_ibm_runtime import QiskitRuntimeService

# One-time save; writes ~/.qiskit/qiskit-ibm.json
QiskitRuntimeService.save_account(
    channel="ibm_quantum_platform",   # not "ibm_quantum"
    token="<YOUR_API_KEY>",
    instance="<YOUR_CRN_OR_INSTANCE>",
    overwrite=True,
)

service = QiskitRuntimeService()      # loads the saved account
```

If your code is V1-era, note that the
[V1 primitives guide](migrate-v1-to-client-side-primitives.md) also covers `auth=` as part of
modernizing older primitive code. It is the same edit — make it once.

References:

- [Install and authenticate](https://quantum.cloud.ibm.com/docs/guides/hello-world#install-and-authenticate)
- [`QiskitRuntimeService` API reference](https://quantum.cloud.ibm.com/docs/api/qiskit-ibm-runtime/qiskit-runtime-service)

---

## Backend lookup: `get_backend()` → `backend(name)`

`QiskitRuntimeService.get_backend(...)` was deprecated in **0.24.0** and **removed in 0.30.0**; the
method is now `backend(name)`. In the same release, `name` became **required**, so a bare
`backend()` no longer returns "the first available backend." Backend selection is now always
explicit — either you name the backend or you choose one programmatically.

| # | Incompatible change | Migration action |
| - | ------------------- | ---------------- |
| 1 | `service.get_backend("ibm_kingston")` | Rename the method: `service.backend("ibm_kingston")`. Same argument, same return type. |
| 2 | `service.get_backend()` or `service.backend()` with no name | Decide how the backend should be chosen. Name it explicitly, or let the service pick: `service.least_busy(operational=True, simulator=False)`. There is no implicit first backend to fall back on. |

References:

- [`QiskitRuntimeService.backend`](https://quantum.cloud.ibm.com/docs/api/qiskit-ibm-runtime/qiskit-runtime-service#backend)
- [`QiskitRuntimeService.least_busy`](https://quantum.cloud.ibm.com/docs/api/qiskit-ibm-runtime/qiskit-runtime-service#least_busy)

---

## The `QiskitRuntimeService.runtime` attribute

`QiskitRuntimeService.runtime` was deprecated in **0.18.0** and **removed in 0.22.0**. It only ever
existed for consistency with the older `qiskit-ibm-provider` syntax, where the runtime service was
reached through a provider attribute. On `QiskitRuntimeService` it returned the service itself, so
`service.runtime.backend(...)` and `service.backend(...)` were the same call.

| # | Incompatible change | Migration action |
| - | ------------------- | ---------------- |
| 1 | `service.runtime.<anything>`, such as `service.runtime.backends()` | Drop `.runtime` and call the service directly: `service.backends()`. Nothing else changes — the attribute returned the same object you called it on. |

References:

- [`QiskitRuntimeService` API reference](https://quantum.cloud.ibm.com/docs/api/qiskit-ibm-runtime/qiskit-runtime-service)
- [IBM Quantum Compute client release notes](https://quantum.cloud.ibm.com/docs/api/qiskit-ibm-runtime/release-notes)
  (0.18.0 deprecation; 0.22.0 removal)

---

## Execution binding: `backend=` / `session=` → `mode=`

How you tell a primitive *where* to run was consolidated into a single argument:

- The Sampler/Estimator `backend=` and `session=` constructor arguments were deprecated in
  **0.24.0** and **removed in 0.30.0** in favor of one **`mode=`** argument that accepts a
  `Backend`, `Session`, or `Batch`. The primitive's `.session` property became `.mode`.
- Passing a backend **name string** (as the mode, or into `Session` / `Batch`) and the `service=`
  parameter of `Session` / `Batch` were **removed in 0.34.0**. Pass the backend **object** instead.
- `QiskitRuntimeService.run()` / `Session.run()` — the low-level program-invocation entry point —
  became a private `_run()` in **0.30.0**. In practice this only shows up in custom-program code;
  see [Custom runtime programs](#custom-runtime-programs).

A primitive constructor now takes `(mode, options)`, and `mode` must be a real object:

```python
# Deprecated / removed forms
sampler = SamplerV2(backend=backend)
sampler = SamplerV2(session=session)
sampler = SamplerV2(mode="ibm_torino")     # backend-name string

# Current form
service = QiskitRuntimeService()
backend = service.backend("ibm_torino")    # resolve the name yourself if that is all you have
sampler = SamplerV2(mode=backend)          # or mode=session / mode=batch
```

| # | Incompatible change | Migration action |
| - | ------------------- | ---------------- |
| 1 | `Sampler(backend=...)` / `Estimator(session=...)` | Rename the keyword to `mode=`; the value is unchanged. Check that you are editing a *primitive* constructor — `generate_preset_pass_manager(backend=...)` keeps its `backend=` argument. |
| 2 | `sampler.session` | Rename to `sampler.mode`. |
| 3 | A backend **name string** as the target: `Session(backend="ibm_torino")`, `Batch("ibm_torino")`, `SamplerV2("ibm_torino")` | Resolve the name to an object first: `service.backend("ibm_torino")`. You need a `QiskitRuntimeService` in scope. |
| 4 | `Session(service=..., backend=...)` / `Batch(service=...)` | Drop `service=` — a session or batch takes its service from the backend object you pass it. |
| 5 | `service.run(...)` / `session.run(...)` | This was the custom-program entry point and is now private. Porting the call is the real work; see [Custom runtime programs](#custom-runtime-programs). |

References:

- [Execution modes](https://quantum.cloud.ibm.com/docs/guides/execution-modes)
- [IBM Quantum Compute client release notes](https://quantum.cloud.ibm.com/docs/api/qiskit-ibm-runtime/release-notes)
  (0.24.0 / 0.26.0 deprecations; 0.30.0 / 0.34.0 removals)

---

## `Session.from_id()`: no `backend`, and `service` is required

`Session.from_id()` rebuilds a `Session` from a stored session id. Its **`backend` parameter** was
deprecated in 0.15.0 and **removed in 0.23.0.** — a session is bound to a single backend, so naming one again on
reconstruction meant nothing. The signature is now:

```python
Session.from_id(session_id, service, use_fractional_gates=False, calibration_id=None)
```

**`service` was not always required.** It only became a required positional parameter in **0.28.0**. So if you are reading
code written against an older release, `Session.from_id("abc123")` with no `service` was valid then.

| # | Incompatible change | Migration action |
| - | ------------------- | ---------------- |
| 1 | `Session.from_id(session_id, service, backend=...)`, or a backend passed positionally | Drop the backend argument and keep `session_id` and `service`. |
| 2 | `Session.from_id(session_id)` with no `service` | Pass a `QiskitRuntimeService` as the second argument — normally the one already constructed elsewhere in the same file. |

References:

- [`Session.from_id`](https://quantum.cloud.ibm.com/docs/api/qiskit-ibm-runtime/session#from_id)
- [IBM Quantum Compute client release notes](https://quantum.cloud.ibm.com/docs/api/qiskit-ibm-runtime/release-notes)
  (0.15.0 deprecation and breaking change; 0.15.1 revert; 0.23.0 warning; 0.28.0 `service` required)

---

## Opening a session: `service.open()` and `backend.open_session()`

Both predate the `Session` class, and each opened a session for an execution path that no longer
exists:

- `QiskitRuntimeService.open()` — signature `open(program_id, inputs, options=None)` — opened a
  session for a **custom program** and returned a `RuntimeSession`. It was **removed in 0.9.4**.
- `IBMBackend.open_session()` and `IBMBackend.close_session()` opened and closed a session for
  **`backend.run()`** execution. They were deprecated in **0.23** as "`backend.run()` and related
  sessions methods", and **removed in 0.35.0** along with `backend.run()` itself.

The replacement for both is the `Session` class driving a V2 primitive:

```python
# Removed forms
session = service.open(program_id="sampler", inputs=...)   # removed in 0.9.4
session = backend.open_session()                           # removed in 0.35.0
...
backend.close_session()

# Current form
from qiskit_ibm_runtime import Session
from qiskit_ibm_runtime.executor_sampler import Sampler

with Session(backend) as session:
    sampler = Sampler(mode=session)
    job = sampler.run([isa_circuit])
# leaving the with block closes the session; session.close() does it explicitly
```

Closing used to be reachable from the primitive too: the V1 `Sampler` and `Estimator` had their own
`close()` method, dropped in the same 0.9.4 cleanup as `service.open()`. The replacement is the
`session.close()` above — see
[the V1 primitives guide](migrate-v1-to-client-side-primitives.md#older-v1-syntax-you-may-need-to-modernize-first)
if your code still calls it.

| # | Incompatible change | Migration action |
| - | ------------------- | ---------------- |
| 1 | `service.open(program_id=..., inputs=...)` | Open a `Session` and run a V2 primitive in it. The custom program the call pointed at needs porting too — see [Custom runtime programs](#custom-runtime-programs). |
| 2 | `backend.open_session()` / `backend.close_session()` | Wrap the backend in a `Session` and pass it to the primitive as `mode=`. The session closes when the `with` block exits, or call `session.close()` yourself. The `backend.run()` calls inside it move to the primitive as well — see [Running circuits](#running-circuits-backendrun--the-v2-primitives). |

References:

- [`Session` API reference](https://quantum.cloud.ibm.com/docs/api/qiskit-ibm-runtime/session)
- [Execution modes](https://quantum.cloud.ibm.com/docs/guides/execution-modes)
- [IBM Quantum Compute client release notes](https://quantum.cloud.ibm.com/docs/api/qiskit-ibm-runtime/release-notes)
  (0.9.4 removal of `open()`; 0.23 deprecation and 0.35.0 removal of the backend session methods)

---

## One backend per session

Since **0.34.0**, a primitive created inside an open `Session` or `Batch` context manager runs
**inside that session** — even if you pass a backend as `mode=`. If the backend you pass is not the
session's backend, the primitive raises `ValueError`:

```python
with Session(backend_a) as session:
    sampler = SamplerV2(mode=backend_b)   # ValueError since 0.34.0
```

> The backend passed in to the primitive is different from the session backend. Please check which
> backend you intend to use or leave the mode parameter empty to use the session backend.

Before 0.34.0 the same code ran quietly in job mode against `backend_b`, ignoring the enclosing
session. So this is worth a look even if you never saw an error: code written against an older
release may have been running outside the session you thought it was in.

| # | Incompatible change | Migration action |
| - | ------------------- | ---------------- |
| 1 | A primitive constructed with `mode=<backend>` inside a `Session` / `Batch` context manager, where that backend is not the session's | Decide which you meant. To run in the session, pass `mode=session` or leave `mode` out entirely. To run against a different backend in job mode, move the primitive outside the `with` block. |
| 2 | The session's own backend passed as `mode=<backend>` inside the context manager | This still works, but logs a warning that the job will run inside the session rather than in job mode. Pass `mode=session`, or omit `mode`, to say what you mean. |

References:

- [Execution modes](https://quantum.cloud.ibm.com/docs/guides/execution-modes)
- [IBM Quantum Compute client release notes](https://quantum.cloud.ibm.com/docs/api/qiskit-ibm-runtime/release-notes)
  (0.34.0)

---

## Running circuits: `backend.run()` → the V2 primitives

Support for the `backend.run()` execution interface was **removed in 0.35.0**. Circuits now run
through the V2 primitives. This is a structural change rather than a rename: the inputs
(primitive unified blocs, or PUBs), the options, and the result objects are all different, and
circuits must be transpiled to the backend's instruction set (ISA) before you submit them.

| # | Incompatible change | Migration action |
| - | ------------------- | ---------------- |
| 1 | `job = backend.run(circuits, shots=...)` for bitstring/counts output | Move to `SamplerV2`. Transpile to an ISA circuit for the target backend, pass it as a PUB, and read counts from the result data. |
| 2 | `backend.run(...)` used to build expectation values by hand from counts | Move to `EstimatorV2` and let it do the estimation: pass `SparsePauliOp` observables in the PUB, laid out to match the transpiled circuit. |
| 3 | Reads of the old `Result` object (`result.get_counts()`, `result.get_memory()`) | Switch to primitive result access — for Sampler, `result[0].data.<register>.get_counts()`. |

Because the destination is the primitives, continue with the
[V1 primitives guide](migrate-v1-to-client-side-primitives.md) once your calls are expressed as
`SamplerV2` / `EstimatorV2`: it covers ISA circuits, the options tree, `mode=`, and result access in
full.

References:

- [Introduction to primitives](https://quantum.cloud.ibm.com/docs/guides/primitives)
- [Transpile with pass managers](https://quantum.cloud.ibm.com/docs/guides/transpile-with-pass-managers)

---

## Result streaming and interim-result callbacks

Live result streaming was withdrawn in stages: `RuntimeJob.interim_results()` and
`stream_results()` were deprecated in **0.25.0**, the streaming endpoints and methods were removed
by **0.32.0**, and the remaining websocket code plus the `callback` environment option were removed
in **0.38.0**. There is **no streaming replacement** — you poll the job instead.

| # | Incompatible change | Migration action |
| - | ------------------- | ---------------- |
| 1 | `job.stream_results(callback)` / `job.interim_results(...)` | Remove the call. If you streamed to show progress, poll `job.status()` in a loop and call `job.result()` when it is done. There is no interim-results feed. |
| 2 | A `callback=` (or `user_callback`) expecting websocket interim data | Remove the callback wiring and move the logic to after `job.result()` returns, or into a status-polling loop. |
| 3 | Code that branches on interim versus final payloads | Only final results exist now; collapse the branch. |

This removes a capability rather than replacing one. If you depended on interim results for
long-running jobs, expect to restructure how progress is reported.

References:

- [IBM Quantum Compute client release notes](https://quantum.cloud.ibm.com/docs/api/qiskit-ibm-runtime/release-notes)
  (0.25.0 deprecation; 0.32.0 and 0.38.0 removals)
- [IBM Quantum Compute Service changelog](https://quantum.cloud.ibm.com/docs/guides/changelog-quantum-compute-service)

---

## Custom runtime programs

The custom-program APIs — `QiskitRuntimeService.upload_program`, `pprint_programs`,
`delete_program`, `program(s)`, and the `RuntimeProgram` class — were **removed in 0.16.0**. There
is no drop-in replacement in `qiskit-ibm-runtime`. Server-side code of your own now belongs in
**Qiskit Serverless**, and workloads that used a thin custom program are usually
better served by calling the V2 primitives directly from the client.

| # | Incompatible change | Migration action |
| - | ------------------- | ---------------- |
| 1 | `service.upload_program(...)`, `service.delete_program(...)`, `service.pprint_programs()` | These no longer exist. Start from what the program actually did — rows 2 and 3 cover the two common answers. |
| 2 | `service.run(program_id=..., inputs=...)` where the program was a thin Sampler/Estimator wrapper | Call the V2 primitive directly from your own code. |
| 3 | A non-trivial custom program (a multi-step server-side workflow) | Port it to Qiskit Serverless. This is a project-level rewrite, not a code edit — budget for it accordingly. |

References:

- [Port code to Qiskit Serverless](https://quantum.cloud.ibm.com/docs/guides/serverless-port-code)
- [Introduction to IBM Quantum primitives](https://quantum.cloud.ibm.com/docs/guides/qiskit-runtime-primitives)

---

## The `RuntimeOptions` class

`RuntimeOptions` was **deprecated in 0.43** and has not yet been removed. It only ever configured a
**custom-program** invocation — `backend`, `image`, `log_level`, `job_tags`, and
`max_execution_time` passed into `QiskitRuntimeService.run(program_id=..., options=RuntimeOptions(...))`.
With custom programs gone, so is its purpose.

It is **not** the primitive options tree (`OptionsV2`, `SamplerOptions`, `EstimatorOptions`, …).
The two are unrelated despite the similar name.

| # | Incompatible change | Migration action |
| - | ------------------- | ---------------- |
| 1 | `RuntimeOptions(...)` passed to `service.run(program_id=..., options=...)` | The whole call is what needs migrating, not the options object — see [Custom runtime programs](#custom-runtime-programs). `RuntimeOptions` disappears along with it. |
| 2 | `RuntimeOptions(backend=...)` used only to choose a backend | That choice now lives in the primitive's `mode=`. Drop `RuntimeOptions` and pass the backend object as `mode=`. |
| 3 | `RuntimeOptions` carrying `log_level`, `job_tags`, or `max_execution_time` | These move onto the primitive's options tree where an equivalent exists — for example `options.environment.job_tags` and `options.max_execution_time`. Check each field against the current options reference rather than assuming a 1:1 mapping. |

References:

- [`RuntimeOptions` API reference](https://quantum.cloud.ibm.com/docs/api/qiskit-ibm-runtime/options-runtime-options)
- [Introduction to options](https://quantum.cloud.ibm.com/docs/guides/runtime-options-overview)

---

## Job objects: `RuntimeJob` → `RuntimeJobV2` and `program_id` → `primitive_id`

Two changes to the object a primitive hands back:

- The `RuntimeJob` class was deprecated in **0.38.0** and **removed in 0.42.0**. Every primitive now
  returns **`RuntimeJobV2`**. The difference that actually breaks code: `RuntimeJobV2.status()`
  returns a **string** — `"DONE"`, `"RUNNING"`, `"ERROR"`, `"QUEUED"` — not qiskit's `JobStatus`
  enum.
- `RuntimeJob.program_id` was renamed to **`primitive_id`** (deprecated 0.24.0, removed 0.30.0).

```python
# Before
from qiskit.providers.jobstatus import JobStatus
if job.status() is JobStatus.DONE:
    ...

# After
if job.status() == "DONE":
    ...
```

| # | Incompatible change | Migration action |
| - | ------------------- | ---------------- |
| 1 | `job.status() is JobStatus.DONE` / `== JobStatus.RUNNING` | Compare against the string: `job.status() == "DONE"`. Drop the `JobStatus` import if nothing else uses it. Watch for `is` comparisons — against a string they silently evaluate false rather than raising. |
| 2 | `from qiskit_ibm_runtime import RuntimeJob`, or a `RuntimeJob` type hint or `isinstance` check | Use `RuntimeJobV2`. |
| 3 | `job.program_id` | Rename to `job.primitive_id`. |

The *value* `primitive_id` returns also depends on which implementation ran the job: server-side
jobs report `sampler` / `estimator`, while client-side (Executor-backed) jobs report `executor`. If
you branch on the value, see the
[server-side to client-side guide](https://quantum.cloud.ibm.com/docs/guides/migrate-to-client-side-primitives) — that is a separate change
from this rename.

References:

- [`RuntimeJobV2` API reference](https://quantum.cloud.ibm.com/docs/api/qiskit-ibm-runtime/runtime-job-v2)
- [IBM Quantum Compute client release notes](https://quantum.cloud.ibm.com/docs/api/qiskit-ibm-runtime/release-notes)
  (0.38.0 deprecation and 0.42.0 removal of `RuntimeJob`; 0.24.0 / 0.30.0 for `program_id`)

---

## Queue and job-management helpers

Queue introspection went away as the service moved to the new IBM Quantum Platform and to the `RuntimeJobV2` job class:

- `QiskitRuntimeService.check_pending_jobs()` was **removed in 0.42.0**.
- `RuntimeJob.queue_position()` was no longer supported in `RuntimeJobV2`.
- `RuntimeJob.queue_info()` was no longer supported in `RuntimeJobV2`.

`delete_job()` is fine, despite appearances: it was removed in 0.42.0 but **reintroduced in 0.45.0**.

| # | Incompatible change | Migration action |
| - | ------------------- | ---------------- |
| 1 | `service.check_pending_jobs()` | Removed with no drop-in. If you gated submissions on the pending count, drop the check and handle job limits when you hit them, or track the jobs you submitted yourself. |
| 2 | `job.queue_position()` | Remove it. The new platform no longer reports queue position.|
| 3 | `job.queue_info()` | Remove it. The closest signal available is `job.status() == "QUEUED"`, which tells you the job is queued but not its position or an estimated start. `usage()`, `usage_estimation()`, and `metrics()` are not substitutes — they report QPU usage, not queue position. |

If your code showed users a queue position or ETA, that feature has no equivalent in the client API.

References:

- [`RuntimeJobV2` API reference](https://quantum.cloud.ibm.com/docs/api/qiskit-ibm-runtime/runtime-job-v2)

---

## Noise-learner results: `.generators` / `.rates` → `.error`

Two related changes to noise-learner results:

- `NoiseLearnerResult` and its per-layer `LayerError` elements lost their `.generators` and
  `.rates` properties — **removed in 0.36.0**. Each layer now exposes an **`.error`** property (a
  `PauliLindbladError`), and that object carries `.generators` and `.rates`. The numbers are
  unchanged; only the path to them is longer.
- `NoiseLearnerResult`, `LayerError`, and `PauliLindbladError` **moved to the
  `qiskit_ibm_runtime.results` package in 0.48.0**. The old
  `qiskit_ibm_runtime.utils.noise_learner_result` path still resolves but emits a
  `DeprecationWarning`.

A `NoiseLearnerResult` holds `data` (a sequence of `LayerError`) and `metadata`, so the generators
and rates are read per layer:

```python
# Before
for layer in result.data:
    print(layer.generators, layer.rates)

# After
for layer in result.data:
    print(layer.error.generators, layer.error.rates)
```

| # | Incompatible change | Migration action |
| - | ------------------- | ---------------- |
| 1 | `result.data[i].generators` / `.rates` on a `LayerError` | Insert `.error`: `result.data[i].error.generators`. |
| 2 | `result.generators` / `result.rates` on the `NoiseLearnerResult` itself | There is no single top-level replacement — the result has no `.error`. Iterate `result.data` and read `layer.error.generators` per layer. |
| 3 | `from qiskit_ibm_runtime.utils.noise_learner_result import ...` | Import from `qiskit_ibm_runtime.results` instead. |

**Do not over-apply this.** `.generators` and `.rates` are still correct **on** a
`PauliLindbladError` — that is, on `layer.error`. If the code already reads
`layer.error.generators`, it is current; only add `.error` where the object is a `LayerError` or a
`NoiseLearnerResult`.

References:

- [`qiskit_ibm_runtime.results`](https://quantum.cloud.ibm.com/docs/api/qiskit-ibm-runtime/results)
- [IBM Quantum Compute client release notes](https://quantum.cloud.ibm.com/docs/api/qiskit-ibm-runtime/release-notes)
  (0.36.0 removal of `generators` / `rates`; 0.48.0 package move)
- [Noise learning helper](https://quantum.cloud.ibm.com/docs/guides/noise-learning)

---

## Noise learning: `post_selection` → `bit_flip_checks.post_circuit`

`NoiseLearnerV3`'s `post_selection` option was **deprecated in 0.49.0** and **renamed** — not
removed — to `bit_flip_checks.post_circuit`. The two subtrees are structurally identical, both
carrying `enable`, `x_pulse_type`, and `strategy`, so this is a field-for-field path change with no
effect on behavior.

This change was made to introduce a new `bit_flip_checks.pre_circuit` option that
applies pre-circuit bit-flip checks to the results of noise learning circuits.

This option exists only on `NoiseLearnerV3Options` (used by `NoiseLearnerV3`), not
`NoiseLearnerOptions` (used by `NoiseLearner`).

`NoiseLearner` only works with the legacy server-side primitives, and `NoiseLearnerV3`
only works with Executor or client-side primitives (introduced in qiskit-ibm-runtime 0.50.0). See [Migrate from `NoiseLearner` to `NoiseLearnerV3`](https://quantum.cloud.ibm.com/docs/guides/migrate-to-noise-learner-v3) for information on whether you should migrate.


```python
# Deprecated
options.post_selection.enable       = True
options.post_selection.x_pulse_type = "..."
options.post_selection.strategy     = "..."

# Current
options.bit_flip_checks.post_circuit.enable       = True
options.bit_flip_checks.post_circuit.x_pulse_type = "..."
options.bit_flip_checks.post_circuit.strategy     = "..."
```

| # | Incompatible change | Migration action |
| - | ------------------- | ---------------- |
| 1 | `options.post_selection.<field>`, or `NoiseLearnerV3Options(post_selection=...)` | Move each field to `options.bit_flip_checks.post_circuit.<field>`. The three fields map 1:1 and the behavior is the same. |

References:

- [Noise learning](https://quantum.cloud.ibm.com/docs/guides/noise-learning#noiselearnerv3)
- [`NoiseLearnerV3` API reference](https://quantum.cloud.ibm.com/docs/api/qiskit-ibm-runtime/noise-learner-v3-noise-learner-v3)

---

## Backend limits: `max_shots`, `max_experiments`, `max_circuits`

The `IBMBackend` attributes `max_shots`, `max_experiments`, and `max_circuits` were
**deprecated in 0.37.0**. `max_shots` and `max_experiments` were then **removed in 0.41.0**, and
`max_circuits` now returns `None`.

These used to report submission maximums, and that is no longer how job limits work. These fields are neither relevant nor enforced, and there is no replacement
backend attribute. Shot and circuit counts are governed by account and plan **job limits** instead.

| # | Incompatible change | Migration action |
| - | ------------------- | ---------------- |
| 1 | `backend.max_shots` — often `shots = backend.max_shots` feeding a primitive's `default_shots` | Choose an explicit shot count. `SamplerV2`'s default is `4096`. The real ceiling is a job limit, not a backend field: at most **10 million executions** (circuits × shots) per Sampler job. With Pauli twirling enabled, `num_randomizations` × `shots_per_randomization` sets the total instead. |
| 2 | `backend.max_experiments` | Remove the reference. There is no per-job circuit-count maximum to read back. |
| 3 | `backend.max_circuits` / `backend.max_circuits()` | Remove the reference rather than branching on it — it returns `None`, so any comparison against it will misbehave. |

Because these were *value reads*, there is no mechanical substitution: picking the right explicit
value is a decision about your workload. Check the job-limits guide for the constraints that do
apply.

References:

- [Job limits](https://quantum.cloud.ibm.com/docs/guides/job-limits)
- [IBM Quantum Compute client release notes](https://quantum.cloud.ibm.com/docs/api/qiskit-ibm-runtime/release-notes)
  (0.37.0 deprecation; 0.41.0 removal)

---

## Cloud simulators are retired: simulate locally, run on a QPU

IBM Quantum cloud simulators were **retired on 15 May 2024**. The backend names no longer resolve —
`service.backend(sim_name)` raises `QiskitBackendNotFoundError` if `sim_name` is one of
`ibmq_qasm_simulator`, `simulator_statevector`, `simulator_mps`, `simulator_stabilizer`, or
`simulator_extended_stabilizer`. Simulation now happens on
your own machine.

With `qiskit-ibm-runtime` 0.22.0 or later, you can use [local testing mode](https://quantum.cloud.ibm.com/docs/guides/local-testing-mode) to replace cloud simulators. To begin, specify one of the fake backends in `qiskit_ibm_runtime.fake_provider` or specify a Qiskit Aer backend when instantiating a primitive or a session.

Since a primitive can take a backend object representing either a simulator or a real QPU, we suggest you put both paths in the code: simulate locally now, with the
real QPU one uncomment away for when you are ready to spend QPU time:

```python
from qiskit_ibm_runtime import QiskitRuntimeService
from qiskit_ibm_runtime.executor_sampler import Sampler
from qiskit_ibm_runtime.fake_provider import FakeKingston

service = QiskitRuntimeService()

# Local simulation — runs now, costs no QPU time.
backend = FakeKingston()

# Real QPU — comment out the line above and uncomment this line when you are ready.
# backend = service.backend("ibm_kingston")

sampler = SamplerV2(mode=backend)   # identical either way
```

Picking the fake backend that matches the QPU you intend to use (`FakeKingston` for `ibm_kingston`, and so on) gives you the same qubit count, coupling map, and representative noise model but might fail execution if your local machine doesn't have enough memory for large-scale simulation. You can instead pick a smaller fake backend or use a Clifford simulator. See [Local testing mode](https://quantum.cloud.ibm.com/docs/guides/local-testing-mode) for more information.

| # | Incompatible change | Migration action |
| - | ------------------- | ---------------- |
| 1 | `service.backend("ibmq_qasm_simulator")`, or any other retired simulator name | The name is gone. Replace it with a local simulator and add the real-QPU lines commented out, as above. |
| 2 | `service.backends(simulator=True)`, or code that filtered the backend list for a simulator | There are no cloud simulators left to filter for. Choose a local simulator explicitly instead of discovering one. |
| 3 | A workload that used the cloud simulator for **scale** rather than for a device's noise | A fake backend carries a real QPU's qubit count and noise model, which is the wrong tool for a large ideal run. Use `AerSimulator`, or stabilizer simulation for Clifford circuits at scale. |

Since `qiskit-ibm-runtime` 0.50.0, the client-side primitives also apply your error suppression and
mitigation options in local mode, so those code paths really run instead of being skipped. That is
also extra simulation work — each noise factor and twirling randomization is another circuit to
simulate — so if you are only checking that the code runs, a small fake backend or a noiseless Aer
backend gets you there far more cheaply than a full-size device.

The calibration data of a fake backend is a one-time snapshot of its real counterpart, and QPU noise
drifts, so you should not treat local runs as a prediction of hardware results.

Local testing mode requires `qiskit-ibm-runtime` **0.22.0 or later**; error suppression and
mitigation in local mode require **0.50.0 or later** with the client-side primitives.

References:

- [Migrate to local simulators](https://quantum.cloud.ibm.com/docs/guides/local-simulators)
- [Local testing mode](https://quantum.cloud.ibm.com/docs/guides/local-testing-mode)
- [`fake_provider`](https://quantum.cloud.ibm.com/docs/api/qiskit-ibm-runtime/fake-provider)

---

## Fake V1 backends and `FakeProvider`

The `BackendV1`-based fake backends and the old `FakeProvider` were replaced by the V2 fake backends
and `FakeProviderForBackendV2`, with the remaining V1 classes **removed across 0.31.0 → 0.33.0**.

The `qiskit_ibm_runtime.fake_provider` package itself is current, so importing from it is not a
problem — what matters is whether you name a V1 class or the V1 provider.

| # | Incompatible change | Migration action |
| - | ------------------- | ---------------- |
| 1 | `from qiskit_ibm_runtime.fake_provider import FakeProvider` | Use `FakeProviderForBackendV2`. |
| 2 | A V1 fake backend class — the non-`V2` variants, such as `FakeManila` | Use its V2 twin (`FakeManilaV2`), or fetch it from `FakeProviderForBackendV2()`. |
| 3 | `backend.run()` on a fake V1 backend | `BackendV1.run()` is gone. Run the V2 fake backend through a primitive: `SamplerV2(mode=FakeManilaV2())`. See [Running circuits](#running-circuits-backendrun--the-v2-primitives). |

```python
# Before
from qiskit_ibm_runtime.fake_provider import FakeProvider, FakeManila

# After
from qiskit_ibm_runtime.fake_provider import FakeProviderForBackendV2, FakeManilaV2
```

References:

- [`fake_provider` module](https://quantum.cloud.ibm.com/docs/api/qiskit-ibm-runtime/fake-provider)
- [`FakeProviderForBackendV2`](https://quantum.cloud.ibm.com/docs/api/qiskit-ibm-runtime/fake-provider-fake-provider-for-backend-v2)

---

## The `channel_strategy` (Q-CTRL) parameter

The `channel_strategy` parameter on `QiskitRuntimeService` — notably
`channel_strategy="q-ctrl"`, the integrated Q-CTRL performance management strategy — was **removed
in 0.32.0**. Q-CTRL performance management is now delivered as a **Qiskit Function** (Q-CTRL Fire
Opal Performance Management) rather than as a service channel strategy.

| # | Incompatible change | Migration action |
| - | ------------------- | ---------------- |
| 1 | `QiskitRuntimeService(..., channel_strategy=...)` with any value other than `"q-ctrl"` (such as `"default"`) | Delete the keyword. Default behavior is unchanged. |
| 2 | `channel_strategy="q-ctrl"` | Delete the keyword, then decide whether you still want Q-CTRL performance management. If you do, move to the Fire Opal Performance Management Qiskit Function, whose own Sampler and Estimator replace what the channel strategy used to do. This changes how your workload runs, so treat it as a rework rather than a keyword removal. |

References:

- [Performance Management, a Qiskit Function by Q-CTRL Fire Opal](https://quantum.cloud.ibm.com/docs/guides/q-ctrl-performance-management)
- [IBM Quantum Compute client release notes](https://quantum.cloud.ibm.com/docs/api/qiskit-ibm-runtime/release-notes)
  (0.30.0 deprecation; 0.32.0 removal)

---

## Pulse gates are no longer supported

On **3 February 2025** pulse-level control was removed from all IBM Quantum processors: the service no
longer accepts jobs that contain **pulse gates** — custom pulse calibrations attached to a circuit. Additionally, the `qiskit.pulse` module was deprecated in Qiskit SDK 1.3
and **removed in Qiskit SDK 2.0**, along with `QuantumCircuit.add_calibration` and the
calibration-builder transpiler passes.

The most common use-case of pulse-level control was to build custom pulse schedules that modify the `ECR` or `RX` pulses to directly execute single- and two-qubit rotations. You can now accomplish this using **fractional gates** (RZZ and RX), which are built into the instruction set architecture (ISA).

Request fractional gates when you get the backend:

```python
# Arbitrary-angle RZZ / RX as ISA instructions, no calibration of your own
backend = service.backend("ibm_kingston", use_fractional_gates=True)

# also available when letting the service choose
backend = service.least_busy(operational=True, simulator=False, use_fractional_gates=True)
```

| # | Incompatible change | Migration action |
| - | ------------------- | ---------------- |
| 1 | `import qiskit.pulse`, `pulse.builder`, or a `ScheduleBlock` | Gone from both the service and the SDK. If the schedule implemented a single- or two-qubit rotation, express it with fractional gates. Anything else — custom pulse shapes, pulse-level characterization — has no drop-in replacement. |
| 2 | `circuit.add_calibration(...)` attaching a pulse gate | The method no longer exists and the service would reject the circuit anyway. Use the fractional gate for that rotation. |
| 3 | `RXCalibrationBuilder`, `RZXCalibrationBuilder`, or `RZXCalibrationBuilderNoEcho` in a pass manager | Remove the pass. Its purpose was to attach the calibration that fractional gates make unnecessary. |
| 4 | An experiment that genuinely needs pulse-level control | This is a redesign, not an edit: Qiskit Dynamics is the remaining route, and it has no API in common with what you are replacing. Scope it as its own piece of work. |

**None of this is a mechanical rewrite.** Fractional gates cover the simple rotation cases; beyond
those, only you can judge whether the experiment survives the move. Expect to review every match by
hand rather than accepting a diff.

The removal of the pulse *API surface* from `qiskit-ibm-runtime` — `backend.defaults()`,
`PulseBackendConfiguration`, and the channel accessors — is covered separately in
[Pulse-level access](#pulse-level-access).

References:

- [Migrate from Qiskit Pulse to fractional gates](https://quantum.cloud.ibm.com/docs/guides/pulse-migration)
- [Fractional gates](https://quantum.cloud.ibm.com/docs/guides/fractional-gates)
- [IBM Quantum Compute Service changelog](https://quantum.cloud.ibm.com/docs/guides/changelog-quantum-compute-service)
  (3 February 2025)

---

## Pulse-level access

Pulse-level access was removed from `qiskit-ibm-runtime` alongside the Qiskit 2.0 migration, because
pulse support was removed from Qiskit itself. There is **no replacement**.

- `PulseBackendConfiguration` and `PulseDefaults` were **removed in 0.37.0**. Backends now return a
  `QasmBackendConfiguration`, and a backend's `Target` is built without pulse defaults.
- The `IBMBackend` channel accessors — `drive_channel()`, `control_channel()`, `measure_channel()`,
  `acquire_channel()` — were removed with pulse support.
- `IBMBackend.defaults()` (and `FakeBackendV2.defaults()`) was **deprecated in 0.38.0** and
  **removed in 0.41.0**.

| # | Incompatible change | Migration action |
| - | ------------------- | ---------------- |
| 1 | `backend.defaults()` / `fake_backend.defaults()` | Remove the call. There is no pulse-defaults object to read, and the target no longer needs one. |
| 2 | `PulseBackendConfiguration` / `PulseDefaults` imports or type references | Remove them. Backend configurations are `QasmBackendConfiguration` now, so code branching on pulse configuration has nothing to branch on. |
| 3 | `backend.drive_channel(...)`, `control_channel`, `measure_channel`, `acquire_channel` | Pulse channels do not exist. Code that built pulse schedules against them has to be re-expressed at the circuit and gate level. |

If your work genuinely depended on pulse-level control, this is a redesign rather than a migration —
and for some experiments the capability is simply no longer available through Qiskit. For submitting
pulse gates and the fractional-gate replacement, see
[Pulse gates are no longer supported](#pulse-gates-are-no-longer-supported).

References:

- [Qiskit 2.0 migration guide](https://quantum.cloud.ibm.com/docs/migration-guides/qiskit-2.0)
- [IBM Quantum Compute client release notes](https://quantum.cloud.ibm.com/docs/api/qiskit-ibm-runtime/release-notes)
  (0.37.0 Qiskit 2.0 pulse removal; 0.38.0 deprecation and 0.41.0 removal of `defaults()`)

---

## Related migrations

- **Primitives.** [V1 → client-side primitives](migrate-v1-to-client-side-primitives.md),
  [server-side → client-side](https://quantum.cloud.ibm.com/docs/guides/migrate-to-client-side-primitives), and
  [older V2 option forms](migrate-older-v2-primitives.md).
- **Qiskit itself.** Several changes here follow from Qiskit 2.0 (pulse removal in particular); see
  the [Qiskit 2.0 migration guide](https://quantum.cloud.ibm.com/docs/migration-guides/qiskit-2.0).

## References

- [IBM Quantum Compute client release notes](https://quantum.cloud.ibm.com/docs/api/qiskit-ibm-runtime/release-notes)
- [IBM Quantum Compute Service changelog](https://quantum.cloud.ibm.com/docs/guides/changelog-quantum-compute-service)
- [`QiskitRuntimeService` API reference](https://quantum.cloud.ibm.com/docs/api/qiskit-ibm-runtime/qiskit-runtime-service)
- [Execution modes](https://quantum.cloud.ibm.com/docs/guides/execution-modes)
- [Job limits](https://quantum.cloud.ibm.com/docs/guides/job-limits)
- [Introduction to primitives](https://quantum.cloud.ibm.com/docs/guides/primitives)
