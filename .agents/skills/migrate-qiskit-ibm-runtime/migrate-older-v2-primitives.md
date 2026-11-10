# Migrate older SamplerV2 and EstimatorV2 option forms

This guide brings **older IBM Quantum `SamplerV2` / `EstimatorV2` code** — roughly the
`qiskit-ibm-runtime` 0.24–0.32 window — up to the current server-side V2 shape. The
primitive interfaces (`run()`, PUBs, result objects) are unchanged; what changed is **how
you express options**.

If your eventual goal is the new **client-side** primitives introduced in `qiskit-ibm-runtime` version 0.50.0, do this migration first. The
client-side constructor rejects the older option forms outright, so normalizing them is a
prerequisite for (or the first step of) that move. The final hop — server-side V2 to
client-side V2 — is covered by
[Migrate from server-side to client-side Sampler and Estimator](https://quantum.cloud.ibm.com/docs/guides/migrate-to-client-side-primitives), which reads
this guide as a companion.

## Do you need this guide?

You do if any of the following appear in your code:

- A primitive constructed with a **flat** options dict, such as specifying
  `SamplerV2(mode=backend, options={"enable_gates": True})` to enable gate twirling.
- Use of `optimization_level`, such as `EstimatorV2(..., options={"optimization_level": ...})`, or
  `estimator.options.optimization_level = ...`.
- A `ValidationError` / unexpected-key error on construction after upgrading
  `qiskit-ibm-runtime`, pointing to an option you have set for years.

If your options are already grouped into categories (e.g. `options={"twirling": {"enable_gates": True}}` or `options.twirling.enable_gates = True`), and you don't use the `optimization_level` option, then it is not necessary to read this guide.

## Background

IBM Quantum V2 primitives shipped with an options surface that was refined over the following
releases. Two early forms were removed before the client-side split:

- **The flat options dict.** Early V2 primitives accepted a single flat mapping of option
  names, for example `options={"log_level": "DEBUG"}`. That form was replaced by a **nested tree**
  whose top-level keys group options by categories. Support of the flat dictionary format was **removed in 0.30.0**.
- **`EstimatorV2`'s `optimization_level` option.** This option was removed in 0.32.0. V2 primitives no longer transpile your circuits, so a transpilation
  optimization level doesn't belong on the primitives — that control lives on the
  pass manager. (`SamplerV2` never had this option, so a
  `SamplerOptions(optimization_level=...)` is simply invalid and gets the same treatment.)

## Summary of incompatible changes

| # | Incompatible change | Migration action |
| - | ------------------- | ---------------- |
| 1 | Flat options dictionary (e.g. `options={"log_level": ...}`)is no longer supported. | Move each key under the correct options group. See [Move a flat options dict into the nested tree](#move-a-flat-options-dict-into-the-nested-tree). |
| 2 | `optimization_level` option is no longer supported. | Remove it and set `optimization_level` on `generate_preset_pass_manager(...)`; feed the resulting ISA circuit to the primitive. See [Move optimization_level to the pass manager](#move-optimization_level-to-the-pass-manager). |

## Move a flat options dict into the nested tree

Every option now lives either at the top level of the tree or inside a group named for the
execution stage it controls. The change is mechanical: keep the value, find the key's home.

```python
# Removed flat form
sampler = SamplerV2(mode=backend, options={"log_level": "DEBUG"})

# Nested tree
sampler = SamplerV2(mode=backend, options={"environment": {"log_level": "DEBUG"}})
```

Refer to [Specify Estimator options](https://quantum.cloud.ibm.com/docs/guides/estimator-options#available-options) and [Specify Sampler options](https://quantum.cloud.ibm.com/docs/guides/sampler-options#available-options) documentation for a summary table of each primitive's options structure.

### Three equivalent ways to set the same options

Once the keys are nested, you can pass them at construction, assign them attribute-style
(which gives you autocomplete), or bulk-update them:

```python
# 1. At construction
estimator = EstimatorV2(mode=backend, options={
  "default_precision": 0.01,
  "resilience": {"zne_mitigation": True}
  }
)

# 2. Attribute assignment after construction
estimator.options.default_precision = 0.01
estimator.options.resilience.zne_mitigation = True

# 3. Bulk update
estimator.options.update(
    default_precision=0.01,
    resilience={"zne_mitigation": True},
)
```

If you build typed options objects (`SamplerOptions` / `EstimatorOptions`) rather than plain
dicts, the same nesting applies — construct the group objects, or pass nested dicts for the
groups.

## Move `optimization_level` to the pass manager

There is no drop-in replacement on the primitive, because the primitive no longer transpiles.
Set the level where transpilation actually happens, then hand the primitive the resulting ISA circuit:

**Before:**

```python
# Removed on the primitive
estimator = EstimatorV2(mode=backend, options={"optimization_level": 3})
```

**After:**
```python
# Set it on the pass manager instead; the primitive consumes the ISA circuit
pm = generate_preset_pass_manager(backend=backend, optimization_level=3)
isa_circuit = pm.run(circuit)
isa_observable = observable.apply_layout(isa_circuit.layout)

estimator = EstimatorV2(mode=backend)
job = estimator.run([(isa_circuit, isa_observable)])
```

Two things to watch when you make this move:

- **Observables must be laid out to match the transpiled circuit.** If the PUB carries a
  `SparsePauliOp`, apply the layout: `isa_observable = observable.apply_layout(isa_circuit.layout)`.
- **Results can shift.** A different optimization level produces a different physical circuit,
  so this is not a purely cosmetic edit — it is worth re-running a small reference job if you
  depend on comparability with earlier results.

## Related migrations you may also need

**Binding the backend.** Older V2 code often also passes `backend=` or `session=` to the
constructor, or a backend **name string** rather than a backend object. Converting those to
`mode=` is a separate older-form fixup, documented in the the `execution-mode` section of
[`migrate-non-primitive-apis.md`](migrate-non-primitive-apis.md).

**Going client-side.** After this guide, continue with
[Migrate from server-side to client-side Sampler and Estimator](https://quantum.cloud.ibm.com/docs/guides/migrate-to-client-side-primitives) for the
Executor-backed `SamplerV2` / `EstimatorV2`.

**Coming from V1 primitives.** If your code still uses V1 (`quasi_dists`, `.values`, parallel-list `run()`), start at
[`migrate-v1-to-client-side-primitives.md`](migrate-v1-to-client-side-primitives.md) instead —
it covers the interface change, and points back here for option forms.

## References

- [Specify Sampler options](https://quantum.cloud.ibm.com/docs/guides/sampler-options)
- [Specify Estimator options](https://quantum.cloud.ibm.com/docs/guides/estimator-options)
- [Introduction to options (precedence and how to set them)](https://quantum.cloud.ibm.com/docs/guides/runtime-options-overview)
- [`SamplerOptions` API reference](https://quantum.cloud.ibm.com/docs/api/qiskit-ibm-runtime/options-sampler-options)
- [`EstimatorOptions` API reference](https://quantum.cloud.ibm.com/docs/api/qiskit-ibm-runtime/options-estimator-options)
- [Transpile with pass managers](https://quantum.cloud.ibm.com/docs/guides/transpile-with-pass-managers)
- [IBM Quantum Compute client release notes](https://quantum.cloud.ibm.com/docs/api/qiskit-ibm-runtime/release-notes)
