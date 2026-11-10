# Editing the select-sqd-eigensolver skill

Not part of the invoked prompt. `SKILL.md` is what Claude Code receives; this
file is for whoever edits it next, human or agent. It carries the decisions that
are expensive to rediscover and the registry's cell format.

## Every claim must change a researcher's decision

The test for the three files in the answering path — `SKILL.md`,
`registry.yaml` and `capabilities.md`. A fact earns its place there when a
researcher choosing or integrating a solver would act differently for knowing
it. Everything else is context spent on every invocation.

What this rules out, all of which has been written into this skill and taken
back out:

- **Registry archaeology.** "An earlier revision said half-strs mode was
  required" tells a researcher nothing about whether the GPU path takes an
  explicit determinant set today. It is worse than dead weight: it states a
  superseded capability claim in the same breath as the true one, and a model
  under context pressure can surface the wrong half.
- **Change magnitude.** File counts, line counts, diff stats. These describe
  the work that produced a capability, not the capability.
- **Maintainer process.** How to pin a citation, which field to prefer, what to
  re-verify. That is this file's job.
- **Restating a convention at the reader.** A cell graded `plumbing` does not
  also need a sentence explaining what `plumbing` means; the ladder below
  defines it once.

This generalizes "keep only history a researcher would act on", which this file
used to state for version history alone. The failure mode is subtler than
padding: each of these reads as diligence, so review does not flag it, and the
registry grows until the model spends its context on provenance instead of
capability.

### When a backward-looking note does earn its place

One exception, and it has a sharp test: **keep it when the wrong value is still
reachable somewhere a reader will look.** Then the note is a guard against
being "corrected" back, not a chronicle.

The Dice `limits` block is the case to copy. Its ceiling is 128 qubits from
`DetLen = 2`, while the upstream documentation still publishes "128 or fewer
orbitals" from 16-byte determinant addresses — wrong in both unit and
mechanism. A reader who checks those docs will find the wrong figure, so the
cell says so explicitly and keeps the correction from being undone.

Earlier revisions of this registry are not such a place. Nobody consults them,
so a note about what a cell used to say is a chronicle; cut it. The difference
is whether the wrong value is live somewhere outside this file.

### One fact, one home

A fact belongs in exactly one place, and the other places cite it. The usual
home is the source pin for anything about provenance or versions, the cell for
anything about a capability, and `capabilities.md` for reasoning that spans
cells.

The pull to break this is specific and worth naming, because "do not repeat
yourself" does not describe it. **When a fact explains why a field has the
value it does, there is a pull to restate the fact inside that field rather
than point at it.** Each restatement then reads as self-contained
documentation, which is exactly why it survives review: nothing about it looks
like padding.

The worked example. Fulqrum's GPU module declared 0.5.0 while sitting past the
0.5.0 tag, so no version pin separated it from the released CPU package. That
one fact was written into four places — the source pin, the solver's
`latest_release_detail`, the release-baseline discussion in `capabilities.md`,
and that file's Fulqrum GPU section — because each field had a reason to
explain itself. Then the branch bumped to 1.0.0 and all four went false
together, and the first sweep to fix them found three.

So the cost is not length, it is that a fact in four places goes stale in four
places and a grep over one file looks clean. Before writing a fact, search for
it; if it is already somewhere, cite that place instead.

## Advising, not elimination

The first version was constraint satisfaction: a checkbox list of features, then
elimination, then a verdict. It failed in use. A researcher checked three boxes
and was told no eigensolver met them, which is both true and useless.
Elimination over a feature matrix converges on the empty set exactly when
requirements get interesting, which is when someone needs help. Registry
accuracy cannot fix this; the architecture produces it.

So the skill advises instead of deciding. The output is a researcher who
understands their options and what each costs, not a winner. **If you are
tempted to restore a scoring or elimination pass, re-read this section.**

"Nothing fits" is never the whole answer. Probe whether a requirement is softer
than stated, then rank the near-misses by what each gives up.

## Decisions encoded in SKILL.md

Each of these looks arbitrary without its reason, and each has been regressed or
nearly regressed once.

**PySCF is step 0, not a recommendation.** The addon starts everyone there, so
most people arrive having already hit its limits and recommending it back is a
non-answer. Two exceptions: their constraints point there anyway, or they are on
Windows, where it is now the only option.

Don't phrase this as a quotable line — the model repeats those verbatim at
researchers as a verdict. Make their own numbers do the work: what 36 orbitals
costs them in PySCF, not "most people have outgrown PySCF."

**Windows has exactly one answer: PySCF, at `pyscf>=2.15.0` with
`qiskit-addon-sqd>=0.14.1`.** This reversed once — earlier releases had no
Windows wheel and the addon marked its pyscf dependency non-Windows — so the
skill used to say, correctly, that no solver ran on Windows. Do not re-flatten
it to that; check the packaging cells. SBD and Fulqrum still do not run on
Windows, so that half of the old claim holds.

**Version history is a special case of the rule above.** It earns its place
when it tells someone what to install or explains a failure they could be
hitting — "needs 2.15.0 or newer" is worth saying, since a stale pin is a real
failure mode. Release-race trivia and channel skew ("one minor behind PyPI",
"conda-forge got there first") are not: they go stale on the next upload and
change nobody's choice. Prefer a floor ("2.15.0 or newer") to a snapshot
("latest is 2.15.0"); a floor stays true.

**Prefer a solver that scales by changing execution mode over one that needs a
different solver later.** SBD's per-call `device=` and Fulqrum's CPU-to-GPU path
both let a workflow grow without a rewrite. No cell in the feature matrix
expresses this, so it is lost if nobody writes it down.

**Install cost is a preference, not a filter.** An earlier version eliminated
solvers the researcher could not compile. That is wrong for a working
researcher: fewer moving parts means less to go wrong, it works on a colleague's
machine, and it survives an environment rebuild. Bias toward the easier install
and let the bias weaken as they show willingness to compile — usually visible
when they mention a cluster, a module system, or a toolchain.

**Science before hardware, unless the user leads with hardware.** Mixing them in
one breath invites the researcher to pre-compromise their science against
hardware they assume they are stuck with. When resources are unstated, answer
across ranges and then ask: say something useful before asking for more input.

**Capability can depend on where a package was installed from**, not only on the
code. See the open question below.

## Audience calibration

Readers span quantum chemists who have never run MPI and HPC people who have
never done chemistry. The jargon ladder:

- Safe for anyone doing SQD: orbitals, determinants, subspace, Hamiltonian.
- Expand on first use: TPB, GDB, SCI, RDM.
- Assume only with evidence they have been in the addon's code: `sci_solver`,
  FCIDUMP, `ci_strings`, carryover.

Briefly defining a term costs little; an unexplained one can lose the reader.

## Open question: the install route changes the answer

A capability can be present in the code and absent from a particular install,
because the channel determines what the build could link against. Worked
example, verified 2026-10-28:

- SBD's NVIDIA Thrust GPU backend requires NVIDIA HPC SDK (`nvc++`) to build
  (INSTALL.md:23).
- conda-forge has `cuda-nvcc` but no `nvhpc` / `nvc++` package.
- So an SBD installed from conda-forge cannot have the Thrust GPU path, while
  the same version built from source on a machine with NVHPC can.

The registry has one `gpu` cell per solver. That answers "does the code support
GPUs" when the researcher needs "will my install support GPUs."

This gets more pressing once `sbd-eigensolver` and `fulqrum` land on
conda-forge, since researchers will then have a real choice between a conda
install and a source build. Options, undecided: a `channel` axis alongside the
engine/python/addon layers (most faithful, most structure); a per-solver note on
which capabilities are channel-dependent (cheaper, less precise); or a Phase-5
output question (least structure, relies on the model remembering). Discuss
before implementing — the SBD case is real today, but whether other cells are
channel-dependent has not been surveyed.

## Citations into fast-moving code

Three citations into Fulqrum's GPU module have died in restructurings while the
128-qubit figure they were attached to stayed correct every time. Where a
module is still moving, prefer a citation that survives a file move: quote the
error message or name the symbol, and treat a bare `file:line` as the weakest
form. The same reasoning as preferring a mechanism to a number, one level down.

## Files

| File | Role |
| --- | --- |
| `SKILL.md` | the invoked prompt |
| `registry.yaml` | source of truth for every capability claim |
| `capabilities.md` | reasoning that does not fit in a cell, plus field reports |
| `capabilities-table.md` | generated export for sharing; do not hand-edit |
| `scripts/render_table.py` | generates the table from the registry |
| `EDITING_THIS_SKILL.md` | this file |

Keep this file out of the invocation path. Everything here costs context at
answering time if it migrates into `SKILL.md` or the registry, and none of it
helps answer a researcher's question.

## Registry cell format

### Three layers

Each engine has up to three layers, and capability is lost at each boundary:

- `engine` — the C++ / binary core. What the code can compute at all.
- `python` — the wrapper or bindings. Not everything is wrapped, and a wrapper
  may compute something without returning it.
- `addon` — what survives `qiskit-addon-sqd`'s `sci_solver` interface inside
  `diagonalize_fermionic_hamiltonian`.

A layer may be omitted when it does not exist (PySCF has no separate engine
layer worth distinguishing) or when it is identical to the layer above. The
renderer and the skill both treat an omitted layer as inheriting.

### Cell fields

| Field | Meaning |
| --- | --- |
| `value` | `"yes"` \| `"no"` \| `partial` \| `not-returned` \| `unclear` \| `unknown` \| `n/a`. **Quote `"yes"`/`"no"`** — bare `yes`/`no` are YAML booleans and the validator rejects them. |
| `maturity` | how much the support can be trusted; see below. A plain `"yes"` with no maturity means `supported`. Anything shakier MUST say so. |
| `confidence` | `verified` \| `unverified` |
| `source` | `file:line`, function, or doc reference backing a verified value |
| `caveat` | short qualifier that does not change the value (e.g. experimental) |
| `blocked_by` | why a layer loses the capability; see below |
| `detail` | prose explanation, shown in the generated table's notes |
| `workaround` | how the researcher gets it anyway; `none` when there is no way |
| `tracking` | upstream issue or PR for a gap. Use it on anything unsupported, so a reader can check the current state rather than trusting `verified_on`. |
| `since` | the release that introduced support |
| `display` | replaces the glyph in the rendered table, for a row that is not a yes/no question (`size-ceiling`, `install-cost`). Keep it under 40 chars; the validator enforces that. `value` is still required and still drives validation. |
| `unreleased` | `true` when the capability exists only in unreleased code. Requires `since` to name the expected version, or omit if unknown. |

### Versioning

A bare `value: "yes"` means supported in the solver's latest release, which
`solvers[].latest_release` records. That is the baseline: never mark a capability
`yes` on the strength of unreleased code.

Prefer `since` to a bare yes wherever the introducing release is known. It
answers "will my installed version do this?", which a checkbox cannot, and it
lets the registry describe a pre-release honestly.

A `since` renders as `✅ (≥1.7.1)`, after any other mark, so the glyph answers
"is this supported?" and the version answers "will my install have it?". A
`since` whose value does not start with a digit is a placeholder naming no tag,
like `unreleased-main`, and is not shown — 🚧 has already said as much.

```yaml
value: "yes"                              # supported in the latest release
value: "yes", since: 1.6.0                # and introduced in 1.6.0
value: "yes", since: 1.8.0, unreleased: true   # merged, not shipped —
                                          # treat as unavailable when recommending
value: "no"                               # not supported in the latest release
```

### Maturity

"Does it exist" and "can I trust it" are different questions. A capability can
be present, compile, run, return a number, and still be wrong on some paths. The
ladder, weakest to strongest:

- `absent` — not implemented. Use `value: "no"` instead.
- `plumbing` — types and scaffolding exist, no working end-to-end path. Someone
  reading the source would see support a user cannot reach.
- `partial` — works on some code paths and not others. Record which in `detail`,
  and `known_issues` where they are known to be wrong. This is the level that
  most needs a warning: it fails selectively, so a passing smoke test proves
  little.
- `supported` — present, documented, no known defects. The default for "yes".
- `verified` — exercised by tests, or confirmed against an independent
  reference. Cite what in `verified_by`.

Only `supported` and `verified` are safe to recommend without a caveat.
`partial` and `plumbing` must be reported to the researcher even when they are
the only option — especially then, since they may still be the right choice.

Related fields: `known_issues` (list of specific defects, each a short string),
`verified_by` (what establishes `verified`), and `verification_status` (what is
and is not exercised by tests — distinct from `known_issues`, since "no test
covers this" is not a defect, but it does mean a claim rests on inspection
rather than evidence; record it whenever correctness was established by reading
code rather than running it).

### `blocked_by`

The skill reasons over this, because the remedy differs per kind.

| Value | Meaning |
| --- | --- |
| `keyword-only` | the option exists but `sci_solver` forwards no keywords. Fixable with `functools.partial`. |
| `not-returned` | computed but dropped before the caller sees it. Not fixable through the API. |
| `not-wrapped` | exists in the engine, absent from the bindings. |
| `type-mismatch` | the interface cannot express the input or output shape. Not fixable without an interface change. |
| `loop-contract` | the value cannot survive the configuration-recovery loop's one-result-per-subspace contract. |

A layer blocked by `type-mismatch`, `loop-contract` or `not-wrapped`, sitting
over a layer that supports the capability, renders that layer's glyph plus ⛔
rather than ❌. The solver does the thing; this interface cannot reach it, and a
bare ❌ files the gap under the solver's name. The renderer derives this by
looking up the layers, so a cell keeps `value: "no"` and no registry edit is
needed. `keyword-only` is excluded, since binding one argument reaches it, and
so is `not-returned`, where the data is computed and lost rather than merely
unreachable.

**A blocker is not automatically a defect, and the glyph must not imply one.**
`keyword-only` renders as the supported glyph plus ᵏ, because the option exists,
works, and is often keyword-only by design — the caller binds it at
construction. `not-returned` renders 🚫, because the data is computed and lost.
Those are different facts. They once shared ⚠️, which overstated
`keyword-only` as a defect: the cell read as a complaint against the wrapper
rather than a note about argument forwarding. If you add a `blocked_by` kind,
give it an unused glyph and say in the legend what the researcher would
actually have to do.

For the same reason a `keyword-only` cell asserts `value: "yes"`, not `partial`.
SBD's GPU support and Dice's MPI are supported, not partially supported; the
addon just forwards no keywords. `partial` is for support that is genuinely
incomplete, and the validator allows a bindable blocker on a yes while still
rejecting one that withholds the capability.

Say why a default is what it is. SBD's RDMs are off because the SQD loop does
not need them, so that cell reports a bound argument rather than a gap.

### Limits

`limits` on a solver block records the largest system the solver will accept. It
is prose rather than a number because the facts are not uniform: the varying
axis is the compute backend for SBD and Fulqrum, the determinant representation
for PySCF and Dice, and absent entirely for a solver whose containers grow
dynamically.

Every `limits` block MUST:

1. **State the unit explicitly** — "qubits" or "spatial orbitals", never a bare
   number. One spatial orbital is two spin orbitals, which equal two qubits
   under Jordan-Wigner, so an unlabeled figure is ambiguous by a factor of two.
   Prefer qubits, since that is what a researcher sizing a circuit counts, and
   give spatial orbitals in parentheses.
2. **Give the mechanism** that imposes the limit. The mechanism outlives the
   number: a reader who knows the ceiling comes from a fixed-width determinant
   word can predict what a recompile changes.
3. **Cite the enforcement site** as `file:line`, keyed to an entry in
   `meta.sources` so the claim is pinned to a commit or release and stays
   checkable. A limit nobody can verify will be argued with.
4. **Say whether the limit is tunable, and at what cost.** A recompile-tunable
   macro and a hard representational ceiling are different facts for someone
   planning a large run.

Distinguish a *hard* limit, which rejects the input, from a *performance cliff*,
where a fast path disables and a slower one takes over. Both belong here;
conflating them does not.

"No hard limit" is a legitimate value, and it is not the same as "unlimited" —
memory still binds. Say which, and do not invent a number to fill the field.
