# Error Mitigation Capability Schema Specification

This file documents the frontmatter schema for all capability definition pages in
this directory. It is an internal reference for contributors and for the capability
selection agent; it is not published to the docs site.

---

## Purpose

Each `.md` file in this directory represents one error mitigation or suppression
capability. The frontmatter encodes structured, machine-readable selection metadata.
The body provides human-readable explanations and verified code examples.

An AI agent can enumerate all capabilities via `registry.yaml`, retrieve individual
pages by `capability_id`, and extract the decision matrix from the structured
frontmatter fields. The body prose is intended to be cited as justification for
a recommendation, not parsed for selection logic.

---

## Required frontmatter fields

### Identification

| Field | Type | Description |
|---|---|---|
| `capability_id` | string | Unique kebab-case slug (matches filename) |
| `name` | string | Display name |
| `category` | enum | See allowed values below |
| `short_description` | string | One sentence, mechanism-first, no marketing language |

**Allowed `category` values:**
- `baseline` — no mitigation (reference point)
- `error-suppression` — reduces noise before/during execution; works on both primitives
- `expectation-value-mitigation` — expectation-value mitigation; built into EstimatorV2, and available for the Executor through `qiskit-mitigation` where the page sets `primitive_executor: true`
- `sampling-mitigation` — post-processing for SamplerV2 only
- `post-selection` — discards shots that fail a check; needs per-shot results (Sampler or Executor)

---

### Primitive support

| Field | Type | Description |
|---|---|---|
| `primitive_estimator` | bool | Works with EstimatorV2 |
| `primitive_sampler` | bool | Works with SamplerV2 |
| `primitive_executor` | bool | Works with the Executor primitive (directed execution model) |

The **Executor primitive** (`qiskit_ibm_runtime.Executor`) is a distinct Qiskit Runtime primitive currently in beta. Unlike Estimator and Sampler, it has no built-in error suppression or mitigation — all mitigation is expressed explicitly via circuit annotations (`samplomatic`) and post-processing. It takes a `(template circuit, samplex)` pair via `QuantumProgram`, generates and binds parameter values on the server side, and returns raw `QuantumProgramResult` objects. Capabilities that set `primitive_executor: true` require the `samplomatic` package and follow the [directed execution model](/docs/guides/directed-execution-model) workflow rather than the standard options interface. See also: `NoiseLearnerV3` (used instead of `NoiseLearner` in directed execution model workflows). The `qiskit-mitigation` package builds Executor programs for TREX, gate-folding ZNE, PEA and PEC (`MitigationTask`, `TREX`, `GateFolding`, `PEA`, `PEC`); a capability page that supports this sets `primitive_executor: true`, and the registry lists the package as `executor_package`.

**Registry `primitive` list values:** `estimator`, `sampler`, `executor`

---

### Result properties

| Field | Type | Description |
|---|---|---|
| `output_type` | enum | `expectation-value`, `bitstring-distribution`, or `any` |
| `estimate_bias` | enum | See allowed values below |

**Allowed `estimate_bias` values:**
- `unbiased` — returns an unbiased expectation value estimate (e.g., PEC)
- `reduced-bias` — reduces but does not eliminate bias (e.g., ZNE, TREX)
- `not-applicable` — suppression technique or baseline; does not directly estimate

---

### Cost model

| Field | Type | Description |
|---|---|---|
| `overhead_class` | enum | `none`, `low`, `medium`, `high`, `exponential` |
| `overhead_detail` | string | Human-readable overhead description |
| `requires_noise_learning` | bool | Whether a learning phase runs before the main circuit |
| `requires_hardware` | bool | `false` means works on noise-free simulators |

**`overhead_class` definitions:**
- `none` — no additional shots or circuits
- `low` — small number of calibration circuits; linear overhead
- `medium` — ~3× shot overhead at default settings
- `high` — significant overhead (noise learning + multiple amplified runs, or discarding most shots, as in post-selection)
- `exponential` — overhead scales exponentially with circuit depth/γ

---

### Activation

| Field | Type | Description |
|---|---|---|
| `resilience_level_activation` | int or null | Resilience level that enables this technique; `null` = manual only |
| `api_class` | string | Fully qualified Python class name for the relevant options |
| `api_guide` | string | Doc path to the API reference or guide section |

---

### Selection criteria (INDEXED by agent)

These fields must be written as discrete, matchable conditions — complete statements
a reader could evaluate as true or false given a specific workload context. Avoid
narrative sentences with embedded caveats; those belong in the body prose.

| Field | Type | Description |
|---|---|---|
| `use_when` | list[string] | Conditions under which this technique is appropriate |
| `avoid_when` | list[string] | Contraindications — when this technique should not be used |
| `prerequisites` | list[string] | Required preconditions (primitive, circuit type, backend) |

---

### Composability (INDEXED by agent)

| Field | Type | Description |
|---|---|---|
| `compatible_with` | list[capability_id] | Capabilities that work alongside this one |
| `incompatible_with` | list[capability_id] | Capabilities that cannot be used in the same job |
| `notes_composability` | string | Optional prose note on composability nuances |

**Source of truth for incompatibilities:** the feature-compatibility section for the primitive: [Estimator](https://quantum.cloud.ibm.com/docs/en/guides/estimator-options.md#feature-compatibility) or [Sampler](https://quantum.cloud.ibm.com/docs/en/guides/sampler-options.md#feature-compatibility).

---

### References

| Field | Type | Description |
|---|---|---|
| `references` | list[string] | Academic references supporting the technique |

---

## Body sections (required order)

1. `## Summary` — 2–4 sentence mechanism description, written to be citable
2. `## When to use` — prose expansion of `use_when` conditions with context
3. `## When not to use` — prose expansion of `avoid_when` with explanation
4. `## Trade-offs` — structured table (see template below)
5. `## Configuration` — minimal code example using real API surface, checked against a named `qiskit-ibm-runtime` version. The selection agent treats it as a pointer to the options involved and takes the exact syntax from the current Estimator/Sampler API reference, so keep the example short and state the version it was checked against.
6. `## Validation` *(optional)* — how to empirically confirm this technique helps a given workload before committing to it, when the `use_when`/`avoid_when` conditions leave a genuine grey area. Name the correct verification method (NEAT gate-error proxy vs. small density-matrix patch vs. local testing mode with mitigation applied, `qiskit-ibm-runtime >= 0.50.0` — see `verification.md`) and any way a naive check would mislead for this technique. Include this section for techniques whose benefit is strongly workload-dependent (e.g. dynamical decoupling, the ZNE amplifier choice); omit it where the decision matrix is decisive.
7. `## Composability` — prose note on what works with what and why

---

## Trade-offs table template

| Dimension | Value |
|---|---|
| Shot overhead | |
| Circuit execution count | |
| Estimate bias | |
| Learning phase | |
| Scales with circuit depth | |

---

## Naming conventions

- `capability_id` must match the filename (without `.md`): `zne-gate-folding.md` → `zne-gate-folding`
- Use specific capability IDs for ZNE variants: `zne-gate-folding` and `zne-pea` are distinct entries
- `incompatible_with` references in-docs capabilities only; hardware features like
  `fractional-gates`, `fractional-rzz` (RZZ only; fractional RX is allowed) and `stretches`
  are referenced by their common names. Fractional RZZ is not listed as incompatible with
  gate twirling, PEA or PEC, since the client-side primitives and the Executor twirl it with
  `twirling.group="local_pauli"` (PEA and PEC only on the Executor); the remaining
  restrictions are in each page's `avoid_when`

---

## Adding a new capability

1. Copy the schema template into a new `{capability_id}.md` file
2. Fill all required fields; leave optional fields as `null` if not applicable
3. Add an entry to `registry.yaml`
4. Verify all `compatible_with` and `incompatible_with` references exist in the registry
5. Verify all code examples against the actual API before merging
