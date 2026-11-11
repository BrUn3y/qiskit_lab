# Public Receipt Contract

New `execute`, `qaoa` and `job` results use a top-level `schema_version: 1`.
This version is independent of the package version and of the existing nested
`comparison_metadata.schema_version: 1`. The shared runtime implementation is
`qiskit_lab.receipts.validate_receipt`; it uses only the standard library and
the existing CHSH statistics helper. No JSON Schema package is required at runtime.

## Version 1

Every versioned receipt has a `receipt_type`:

| Type | Meaning | Required context |
| --- | --- | --- |
| `execution` | One local circuit | `status`, `backend`, `hardware: false`, `run_id`; counts at DONE |
| `qaoa` | Local Max-Cut experiment | Local execution context, counts at DONE, graph/optimization fields below |
| `job` | IBM job observation or saved submission intent | `status`, `backend`, `hardware: true`, `job_id`, except unknown/not-attempted intents use `run_id` |
| `chsh` | Four labelled measurement configurations | `status`, `backend`, explicit `hardware`, appropriate job/run ID, four `correlators` |
| `distribution` | A saved count distribution for comparison | `counts`; no invented execution context |

Supported statuses are SUBMITTED, INITIALIZING, CREATING, VALIDATING, QUEUED,
RUNNING, CANCEL_PENDING, DONE, ERROR, CANCELLED, SUBMISSION_UNKNOWN and
NOT_SUBMITTED. The final two retain the distinction between an ambiguous
submission and one not attempted. Receipt validation never submits, retries,
recovers or queries a job. This contract supports saved intent metadata but
does not itself implement submission recovery.

Versioned QAOA requires `node_count`, `edges`, `gamma`, `beta`, `expected_cut`,
`exact_cut`, `approximation_ratio`, `best_bitstring`, `best_cut`, and
`optimization_trace`. Counts, node count and recorded qubits must agree;
edges must use distinct in-range nodes, and optimization values must be finite.
This is structural/scientific-input validation, not independent verification
of the optimizer or of the supplied theoretical expectations.

Counts can be one mapping or an ordered nonempty list of publication mappings.
Each histogram has nonempty binary keys of equal width, nonnegative **JSON
integers**, and a positive observed total. Booleans, floats, negative values,
separators and empty/all-zero histograms are rejected. Omit `counts` when they
are unavailable; do not invent an empty distribution. Multi-publication job
results retain their order and may have different widths if no common layout
is supplied. Comparison still requires exactly one circuit per file.

Requested `shots` must be a positive integer when present. It is not required
to equal returned counts: requested and observed shots are different quantities.
Reported CHSH estimates and observed shot totals are always recomputed from the
four count histograms; optional angles, seed provenance, source identities and
row order remain intact. When top-level counts duplicate the CHSH rows, they
must agree in that same order. A supplied source-circuit identity must have a
supported nested version, a SHA-256 digest and valid register/measurement
mapping matching the returned count width. Unknown extension fields are retained,
not interpreted as evidence or promises of future schema compatibility.

## Historical Compatibility

A receipt **without** the top-level `schema_version` is historical. No version
zero is inferred, missing context is never invented, and present scientific
fields still validate. Historical null optional backend/ID/shot/qubit fields
remain unavailable, not zero or fabricated metadata. Existing count-only comparison inputs, local receipts,
`experiment.json`, hardware counts dictionaries/publication lists, saved
submission intents and labelled CHSH receipts remain supported. A nested
comparison version does not version the enclosing receipt.

Offline report regeneration preserves the input bytes and its original envelope
(including absence of an envelope). It writes a new report and JSON copy, not
an in-place migration. Legacy cached report renaming also remains offline and
retains notification acknowledgements. A fresh online `job` observation writes
the versioned job envelope without inventing missing circuit/shot metadata.
Do not add a version/type to a historical file unless it satisfies that type's
required fields. No bulk rewrite is required.

An explicit unknown, null, boolean, noninteger or unsupported version is an
error, **not** an invitation to use historical mode. Use a producer/consumer
supporting that version; never delete or relabel it just to bypass validation.
`--allow-unverified` only allows absent circuit identity for intentional legacy
comparisons, not malformed counts, metadata or unsupported versions.

## Missing Results and Trust

ERROR/CANCELLED jobs and historical terminal jobs may legitimately have no
counts. They retain their status and render "No measurement results" with no
fabricated samples. A DONE job whose result download failed remains trackable
without counts so later read-only polls can retry. It must not generate a success
report or notification while `result_error` marks those missing results.

`report --input` always marks the output
`report_source: imported_receipt_not_verified_online`, regardless of the input's
recorded job ID or timestamps. Schema validation and comparison's
`compatibility.verified` establish neither job authenticity nor current IBM
status. The latter checks recorded circuit identity/measurement order only.
Imports are excluded from implicit job polling, even if copied to `receipt.json`.
Only an explicit online query of an existing ID can observe IBM status; no
offline test or imported claim proves connectivity. No such query is needed
for importing, comparing or rendering a receipt.

The same validator runs before report output directories/files, before local
count dashboards and on tracked job candidates. Hardware submission context is
validated before submission; any returned accepted job ID is still saved
immediately before post-response validation, never lost to a new validation gate.
That tracking write is not a claim that a malformed SDK response is valid.
Invalid tracked receipts are left unchanged, reported with a safe next action,
and do not prevent healthy jobs from being polled/notified. Explicit lookup of
an invalid saved job fails before contacting IBM. Notification event IDs,
durability, retries, acknowledgment requirements and the ten-job rotation
remain unchanged. Corrupt/unreadable JSON and untracked files retain the
existing discovery behavior; the queue is not silently repaired.
