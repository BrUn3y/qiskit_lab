# SQD eigensolver notes

Prose companion to `registry.yaml`, which is the source of truth for the feature
matrix. Read the registry for per-cell data; read this for the reasoning that
does not fit in a cell.

`capabilities-table.md` is generated from the registry by
`scripts/render_table.py` — the shareable export for documentation, and not
canonical. Do not hand-edit it, and do not cite it: it can lag the registry and
it drops detail. Its header says as much, so an agent that stumbles on it is
told immediately.

## Choosing an integration path

There are four ways to drive an eigensolver, and the right one depends on the
researcher's constraints rather than on a fixed ranking.

**Through the SQD addon** (`sci_solver` on
`diagonalize_fermionic_hamiltonian`). The default recommendation when it fits.
Gives configuration recovery, batching and convergence handling for free.
Costs: keyword-only options need `functools.partial`, RDMs survive only on the
single returned result, and excited states do not fit at all.

**Python, calling the wrapper directly** on a fixed subspace. The right answer
when the researcher wants excited states, needs a GDB subspace through SBD or
Fulqrum, or is not running a configuration-recovery loop in the first place. They give up
the loop and write their own iteration if they want one.

**The engine CLI.** SBD's CAOP and Dice's full SHCI exist nowhere else. File-based
I/O, no Python integration. A legitimate answer when the capability only exists
there, and the honest answer when the researcher's constraints rule out the
Python paths.

**Linking the engine into C++.** Rare, but real: someone building a solver into
an existing C++ code wants the engine layer and none of the Python. Fulqrum
decouples operator construction from eigensolving, which makes it the natural
fit; SBD ships C++ headers and apps. Ask rather than assume the researcher wants
Python.

Do not treat these as a fallback chain. A researcher who says up front that they
are writing C++ should not be walked through the addon first.

## The `sci_solver` interface is the main source of surprise

Three constraints, all recorded under `interface_constraints` in the registry:

1. The call is five positional arguments with no keywords forwarded
   (`fermion.py:780`), so every solver option needs binding first.
2. The loop consumes `energy`, `orbital_occupancies`, `sci_state` and
   `carryover`. It never reads `rdm1`/`rdm2`, and returns one best `SCIResult`.
3. `ci_strings` is a pair whose Cartesian product spans the subspace, so a flat
   determinant list — a GDB subspace — has no representation.

Constraint 1 is a nuisance with a one-line fix. Constraints 2 and 3 are real
expressiveness limits: no argument binding reaches past them.

## Failures that look like successes

The registry's `blocked_by` field distinguishes these, and the distinction is
what the skill reasons over:

- **`sbd-python` accepts `spin_sq` and ignores it.** The run completes, returns
  a plausible energy, and exits zero with no spin penalization. Nothing warns.
  Any workflow swapping PySCF for SBD while passing `spin_sq` is affected.
- **Dice computes RDMs and discards them.** The binary writes
  `spin1RDM.*.txt`; the wrapper reads only the diagonal for occupancies and
  leaves `SCIResult.rdm1`/`rdm2` unset. `clean_temp_dir=True` then deletes the
  files. Recoverable only by parsing them outside the API.
- **Keyword-only options silently absent.** Passing `spin_sq` to
  `diagonalize_fermionic_hamiltonian` does not reach the solver, because the
  loop never forwards it. Same observable behavior as the SBD case, different
  cause.

## Two ways to get MPI parallelism

Not a feature either solver lacks — both are parallel — but the distinction
decides how the researcher launches their program, so it belongs near the top
of any cluster conversation. Recorded under `execution_models` in the registry.

**The solver spawns its own ranks.** `qiskit-addon-dice-solver` shells out
through `mpirun` on each diagonalization, passing `mpirun_options` straight
through. The calling program is a single ordinary process and must not itself
run under `mpirun`. This needs no MPI-aware setup and works in a notebook,
which is why the upstream guide keeps it for interactive work. The cost is a
process launch per diagonalization, with ranks that do not outlive the call.

**The whole process runs under one launcher.** `mpirun -n 128 python
my_program.py`, with `diagonalize_fermionic_hamiltonian` invoked collectively
from every rank. The addon has supported this since 0.13.0, so it is in the
0.14.0 baseline.

This costs no argument binding, which is worth saying because every other SBD
option does. `solve_sci_batch` takes `mpi_comm` and defaults to
`MPI.COMM_WORLD`, and its first five parameters are the addon's positional
signature, so `sci_solver=sbd.solve_sci_batch` is already collective under
`mpirun`. Pass `mpi_comm=` only for a sub-communicator.

Within that mode, only the `sci_solver` step is collective: every rank
participates, so one diagonalization can spread across all of them, while
preparing CI strings, processing results and checking convergence run on the
control process alone. The return value is broadcast, so every rank sees the
same answer. `qiskit_addon_sqd.processes` provides the helpers —
`is_mpi_execution`, `process_index`, `process_count`, `is_control_process`,
`broadcast`, `barrier`. A collective solver may also divide the ranks into
groups and diagonalize several subspaces at once, since all of an iteration's
subspaces arrive in one call; the addon does not divide them and nothing in its
interface describes them.

This second model is what the upstream HPC guide recommends, because it
composes with job schedulers and other parallel software and scales to large
process counts. One caveat worth stating: the default PySCF solver is not
distributed, so launching under MPI without a distributed solver buys nothing.

**A Jupyter notebook rules the collective model out.** The kernel is one
process started by the notebook server, not by `mpirun`, so there is nothing to
run collectively and no notebook equivalent of the launch command. That makes
notebook use a selection criterion rather than a preference: it eliminates
SBD's MPI path regardless of what else recommends it, leaving a single-process
SBD run or a solver that spawns its own ranks. It is also why the
mpirun-spawning model persists rather than being superseded. Developing in a
notebook and running production under a batch script is a reasonable split.

The guide is at
[quantum.cloud.ibm.com/docs/addons/qiskit-addon-sqd/guides/hpc-acceleration](https://quantum.cloud.ibm.com/docs/addons/qiskit-addon-sqd/guides/hpc-acceleration),
and it is the right page to send a cluster user to.

## Fulqrum is shaped differently from the others

Fulqrum is not an eigensolver. It builds a `SubspaceHamiltonian` that behaves
as a SciPy `LinearOperator` — implementing the sparse matrix-vector product —
and leaves the eigensolver to the caller.
Getting that the wrong way round misstates what the package does and hides why
the rest of its column looks the way it does. Three consequences:

- Multiple roots come free (`eigsh(k=n)`).
- Complex Hamiltonians come free on CPU; the kernel is genuinely complex, via a
  Cython fused type instantiating `omp_matvec[complex]`.
- "General subspace manipulation" follows from the design rather than being a
  separate feature.

Using it inside the SQD loop no longer means writing the adapter: from 0.5.0
`fulqrum.addon_sqd_support.sci_solver_from_integrals` returns an `sci_solver`
to pass straight to `diagonalize_fermionic_hamiltonian`. That path takes the
lowest root only and carries no spin penalty, so two of the freedoms above are
freedoms of calling Fulqrum directly. Neither Fulqrum repo has any RDM code.

### Which eigensolver to pair with it

Two are in routine use, and they trade install cost against performance.

`scipy.sparse.linalg.eigsh` is already a hard dependency, so it needs no
install, and it is what the hosted documentation and both tutorials use
throughout. PRIMME is an optional dependency (minimum 3.2.3, listed under
Optional in `docs/install.rst`) and generally performs better; it is what
Fulqrum's own benchmarks run, consistently with
`method="PRIMME_DEFAULT_MIN_MATVECS"`, and `fulqrum/test/test_primme.py`
covers it in both matrix-free and csr-fast modes.

No head-to-head timing is recorded here, so the honest statement is that PRIMME
generally performs better — not a factor.

The hosted docs name only scipy, so PRIMME is something a researcher has to be
told about rather than something they will find. Both take the same object, so
switching is one line, which makes "start on scipy, move to PRIMME if the
diagonalization dominates" a reasonable thing to suggest.

There are also three ways to hand the operator over, per the docs: `Hsub`
itself (matrix-free, least memory, slowest), `to_csr_linearoperator()`, and
`to_csr_linearoperator_fast()` (roughly twice the memory, and the one the docs
say to try first).

### The paper

The project asks to be cited as *A generalized framework for quantum subspace
diagonalization*, Nation, Ash Saki and Kang,
[arXiv:2603.18731](https://arxiv.org/abs/2603.18731).

It is worth reading rather than merely citing, because it is the source for
three things this registry asserts: the extended operator alphabet (projection
and ladder operators beyond the Pauli set) that lets one code base cover
fermionic and spin systems, the bit-set encoding that is the mechanism behind
Fulqrum's "no hard limit" on width, and the deliberate separation of subspace
construction from eigensolving.

The paper does not name Fulqrum. It describes the framework the package
implements, so cite it as the paper behind the approach rather than as a paper
about the package. Its claim of memory and runtime gains "in some cases by an
order of magnitude or more" is the paper's, not a finding reproduced here.

The GPU path is narrower than the CPU path, and not a drop-in accelerator: 128
qubits, chemistry Hamiltonians only (enforced, not documented-only), TPB
subspaces only, and `NotImplementedError` on complex Hamiltonians. A CPU
workflow using complex Hamiltonians or GDB does not move to GPU by switching
the Hamiltonian class.

The 128-qubit figure deserves care, because the same width behaves differently
on the two paths. On the GPU it is a hard limit: the CUDA half-string is a
single 64-bit word per spin species, so the kernels reject anything wider. On
the CPU the same width only costs speed — a fast packed path disables and a
generic bitset path takes over. A system that runs on the CPU can therefore
fail outright on the GPU at unchanged size, which is the opposite of what
"accelerator" suggests. See the `limits` blocks in `registry.yaml` for the
enforcement sites and their source pins.

## Field reports: judgment that is not in the code

Everything above is read from source or documentation. This section is not: it
is distilled from conversations with researchers using these solvers on real
problems. Keep it separate for that reason, and keep it here — these are
considerations for *ranking* options, never claims about what a solver does. A
capability claim belongs in the registry with a citation, or nowhere.

Each report carries the date of the conversation it came from, so its age is
visible at the point of use rather than only in the note below. Where a report
is dated twice, it came up independently in two conversations — which is itself
a reason to weight it more heavily than a single mention.

**Staleness.** The conversations behind this section date from 2025-12-12 and
2026-04-08, and Fulqrum in particular has had substantial performance work
since. Treat the mechanisms below as durable and any remembered performance
figure as expired. Where a report rested on measured numbers, those numbers are
deliberately not recorded: quoting a year-old benchmark as current is the
failure this registry's release baselines exist to prevent.

### Dense versus sparse decides whether Fulqrum's CSR route is affordable

*Reported 2025-12-12.*

Materializing a dense subspace Hamiltonian in CSR costs what dense storage
costs, plus index overhead — there is no sparsity to exploit. Sparse
Hamiltonians are where the representation pays off, and that is a property of
the representation rather than of any release.

The part a researcher will not see coming is that sparsity depends on the basis
they end up in, not the problem they started with. A lattice Hamiltonian from
DFT — hopping integrals plus density-density repulsion — is sparse. Rotating to
the natural orbital basis to build a LUCJ circuit destroys that sparsity, and
dense Hamiltonians in the molecular basis are ordinary in chemistry. So a
workflow can be sparse where the Hamiltonian is built and dense where it is
diagonalized. SKQD does not involve that rotation.

Worth raising when someone describes their Hamiltonian as sparse: ask what basis
it is sparse in, and whether anything downstream rotates it.

### Qubit operators point to Fulqrum; electronic structure points to SBD or Dice

*Reported 2025-12-12 and 2026-04-08.*

A routing heuristic, not a capability boundary. Fulqrum may well suit electronic
structure, and nothing in the registry contradicts that. What the heuristic
tracks is where each package's worked examples, idioms and maintainer attention
sit today.

In practice the Fulqrum path for qubit operators runs: build a
`FermionicOp`, map to qubits (Jordan-Wigner), project onto the sampled
bit-strings, hand the CSR operator to an eigensolver. That route carries no
alpha/beta determinant split, so it suits spinless or complex-coefficient
problems that the electronic-structure solvers cannot express. For open-shell
electronic structure, SBD and Dice are where the examples are.

### Documentation and worked examples are a selection criterion

*Reported 2026-04-08.*

Researchers adopt a solver by starting from its tutorial, so example coverage is
a real cost in the same way compile burden is. PySCF is the benchmark here:
enough examples, showing enough ways to use the functionality, that adapting it
to a new codebase is straightforward.

This is the one axis on which PySCF wins for reasons other than install ease, so
it is worth holding alongside the "most people have outgrown PySCF" framing in
SKILL.md. Both are true. A researcher who has outgrown PySCF's scale has still
not outgrown its documentation, and the solver they move to will cost them time
that the feature matrix does not show.

## A checkmark means the latest release

The convention across the registry: a bare `value: "yes"` means supported in the
solver's **latest release**, never in unreleased code. Each solver records its
`latest_release`, and those baselines are what a checkmark is measured against.

Prefer `since:` to a bare yes whenever the introducing release is known. It
answers the question a reader actually has — "will my installed version do
this?" — which a checkbox cannot. It also lets the registry describe pre-release
work honestly: `since: 1.8.0` with `unreleased: true` says the capability is
merged but not shipped, so it should not be recommended yet.

"Released" and "installable from a package index" are not the same thing, and
Dice is why the distinction matters. It has GitHub tags 0.1.0, 0.2.0 and 0.3.0
but no PyPI distribution — the PyPI name holds a `0.0.0.dev0` placeholder — so
its releases are things to check out, not things to pip install. Its cells cite
`since: 0.3.0` where the capability is in that tag.

Dice also shows why a release baseline has to be per-capability rather than
per-solver. `solve_sci` and `n_roots`, the interface that plugs into the addon,
exist only on `main` past 0.3.0, so those cells stay `unreleased` while the
rest of the column is `0.3.0`.

Fulqrum's GPU module has nothing published at all, so every claim about it
describes unreleased code. It also shows why a declared version is not a
release: the branch declares a version ahead of the released CPU package,
which gives the registry a floor to state once something ships but licenses
nothing today. The registry marks those cells `unreleased: true` and the
generated table shows 🚧 rather than a checkmark.
The validator enforces the convention from both ends: a plain yes for a solver
with no release is an error, and an unreleased yes in a project that *does*
release must name the version it is expected in.

Watch for a checkout running ahead of its tags. Fulqrum development checkouts
report a version with no corresponding tag, so a capability read from that
working tree may not exist in anything a researcher can install. Pin a claim to
the release it was confirmed against — the `since:` fields do this — rather than
to whatever the working tree reports.

## Support has levels, not a checkbox

A capability can be present in the code, compile, run, return a number, and
still be wrong on some paths. So `maturity` is a separate axis from
`confidence`: one says how well this registry knows the fact, the other says how
far the capability itself can be trusted.

The ladder, weakest to strongest: `plumbing` (scaffolding, no reachable path),
`partial` (works on some code paths and not others), `supported` (present,
documented, no known defects), `verified` (tested or checked against a
reference). Only the top two are safe to recommend without a caveat, and
`verified` requires a `verified_by` saying what establishes it.

`partial` is the level that most needs a warning, because it fails
*selectively*. A researcher's first run can succeed and prove nothing about the
path they will hit next week.

SBD's complex support is the worked example, and
`references/sbd-complex-hamiltonian-support.md` is the full assessment behind
that cell. The split it found: the numerical core is genuinely
complex-Hermitian-correct — conjugating inner product, Hermitian Davidson fill,
`zheev_`/`zungqr_` dispatch — while the chemistry entry points are not. TPB is
not templated on the element type, the `_UHFCPLX` integral mode silently aliases
`<ij|kl>` with `<kl|ij>` and flips the imaginary sign, and FCIDUMP cannot carry
complex integrals at all. Hence `partial` with four `known_issues`, and a
`verification_status` recording that nothing tests complex anywhere in the repo.

That cell also shows why the Python layer is `❌` for a stronger reason than
"not wrapped": with TPB real-only and FCIDUMP real-only, bindings alone could
not expose complex. The fix is upstream, so `workaround: none`.

`partial` averages over two different answers. CAOP is the complex-capable
one: `caop::diag` carries a
`template <typename ElemT>` header that `tpb::diag` does not. For the
chemistry paths SQD runs on, TPB and GDB, complex is absent at every layer.
And CAOP does not rescue an SQD workflow — its Python entry point is on main
only, in no released tag, and the addon has no CAOP path — so the headline for
a researcher asking about complex SQD is a plain no, with CAOP worth a sentence
only if they are doing model Hamiltonians outside the addon.

Read that reference before relying on SBD for anything complex, and note its
provenance — Claude-authored against one commit, sourced to file and line, not
maintainer-reviewed.

Grading honestly cuts both ways. Fulqrum's complex matvec is `supported`, not
`verified` — the kernel plainly exists, but no end-to-end test for a complex
Hamiltonian was identified, so the stronger claim is not available.

## Unreleased capability is still worth mentioning

An unreleased capability cannot be the recommendation. It can still be exactly
what a blocked researcher needs to hear about. When something matches their
constraint but has not shipped, say so under its own heading: that the work
exists, how to get it today, and what to follow. The failure mode to avoid is
silence, not enthusiasm — and equally, folding it into the main recommendation
as though it were installable.

### Fulqrum's GPU path, read 2026-11-06

Unreleased: the GPU module is public on the `v1.0.0-rc` branch, which declares
1.0.0 against the released CPU package's 0.5.0. It is a release candidate —
no tag, nothing on PyPI.

What it does, for someone weighing it against SBD's GPU backends. Explicit
determinant sets work, not just tensor-product subspaces: `FullStrsHamiltonian`
takes a uint64 `(n, 2)` array of alpha/beta pairs. RDMs of order 1 and 2 are
available through `compute_rdms`, following PySCF `make_rdm12s(reorder=True)`,
so embedding code written against PySCF can consume them unchanged.

What bounds it: real type-2 operators only, 64 orbitals per spin sector, NVIDIA
only, and no `sci_solver` adapter — `addon_sqd_support.py` carries no GPU
reference, so nothing here reaches `diagonalize_fermionic_hamiltonian` without
the caller writing glue. Multi-GPU is by MPI rank; the NotImplementedError on
`len(gpu_ids) > 1` bounds one rank to one GPU rather than capping a job at one
GPU, and quoting it without that distinction understates the package by the
size of the cluster.

**A strong test suite can still be absent from CI.** The GPU cells are graded
`verified` on real validation — see their `verified_by` — but every GPU test
needs a CUDA device and no CI runner has one. So the suite passes where
someone runs it, not on every commit. Tell a researcher both halves: the
validation is good, and nothing re-checks it automatically, so running it on
their own hardware is worth the hour.

## Packaging is a filter of its own

"Is it on PyPI" is the wrong question. What matters is whether `pip install`
needs a compiler, and that splits these solvers cleanly:

- **PySCF** publishes `py3-none-<platform>` wheels for linux-x86_64,
  linux-aarch64, macos-x86_64, macos-arm64 and, since 2.15.0, windows-x86_64.
  One wheel per platform covers every Python version, so pip needs no toolchain
  anywhere PySCF supports. It is the only solver here that runs on native
  Windows, and requires 2.15.0 or newer there.
- **`sbd-eigensolver`** and **`fulqrum`** publish an sdist and zero wheels.
  `pip install` compiles on the host. For SBD this also decides
  *functionality*: the backends you end up with depend on the toolchain the
  build finds, so the same pip command on two machines can yield different GPU
  support.
- **`qiskit-addon-dice-solver`** holds the PyPI name at `0.0.0.dev0` — a
  reservation, not a release. Treat Dice as not distributed and install from a
  git checkout after `build.sh`.
- **`fulqrum-gpu`** is not on PyPI at all. The public `fulqrum` package is the
  CPU one and does not carry the CUDA paths.

On conda-forge, only PySCF and `qiskit-addon-sqd` itself are available today, so
a pure-PySCF SQD workflow installs entirely from conda-forge, on Windows as well
as Linux and macOS.
Recipes are in review for
[`sbd-eigensolver`](https://github.com/conda-forge/staged-recipes/pull/35125)
and [`fulqrum`](https://github.com/conda-forge/staged-recipes/pull/35533).
PRIMME is not on conda-forge either
([staged-recipes#35091](https://github.com/conda-forge/staged-recipes/pull/35091)),
so a conda install of Fulqrum would reach only scipy's eigsh from the channel —
which costs performance rather than capability, since PRIMME is where Fulqrum's
own benchmarks go.

Ask about both dimensions explicitly. They are independent of each other and of
build cost: a researcher may have a full toolchain and still need everything to
come from conda-forge for environment-management reasons.

## Record tracking links for anything unsupported

When a gap has a known upstream issue or PR, put it in the cell's `tracking`
field. The generated export groups these under "Tracked upstream" so a reader
can check the current state rather than trusting `meta.verified_on`.

The one that matters most right now is
[qiskit-addon-sqd#389](https://github.com/Qiskit/qiskit-addon-sqd/issues/389),
which tracks support for general non-Cartesian-product subspaces. It is the
upstream home of the `type-mismatch` that blocks GDB through the addon. Worth
reading for the framing: the product-subspace assumption is inherited from
PySCF, so one interface limitation surfaces in several cells rather than
several independent solver gaps.

Check the issue's solver list against the registry rather than quoting it. It
says Dice, Fulqrum and SBD all support general subspaces, and it describes what
a package can do rather than what the loop can reach, so it is quotable in
support of two wrong readings.

SBD and Fulqrum do support GDB below the addon, and neither reaches it through
`sci_solver`. Fulqrum is the sharper case: its `Subspace` takes a flat
determinant list in full-string mode, while its 0.5.0 adapter passes alpha and
beta half-strings and takes the Cartesian product.

Dice does not support it at all on the path the addon drives. The subspace
entry point reads `AlphaDets.bin` and squares that list — `occAlpha[i]` for
alpha, `occAlpha[j]` for beta — so the subspace is a product basis of one list
with itself, and `BetaDets.bin` is never read although the addon writes it. The
issue's mention probably refers to SHCI's own iterative determinant selection,
which is Dice choosing a determinant set rather than the caller supplying one.

Every solver here is TPB-only through the addon today.

## A solver may have more than one API, with different costs

Install cost is usually quoted for Python, which misrepresents every other way
of consuming a solver. SBD is the case that matters here: from Python it is a
PyPI sdist, so pip compiles the extension modules on the host; from C++ it is
**header-only** — dozens of headers under `include/sbd/`, no `.cc`/`.cpp`
sources there, and CMake declaring `add_library(sbd_headers INTERFACE)`. There
is nothing to build or link, so dropping it into an existing C++ codebase is a
much lighter integration than "pip compiles C++" suggests.

The registry records this per solver in an `apis` block. Check it before
summarizing a solver's install story, especially in a comparison table where a
single cell implies a single answer.

This also bears on who the advice is for. A researcher integrating an
eigensolver into existing simulation code in C++ is rare but real, and for them
the usual ranking inverts: the header-only route is the easy one.

## Build cost separates these as much as features do

In increasing order: `pyscf` is a plain pip install; `sbd` and `fulqrum-cpu`
compile C++; `fulqrum-gpu` adds a CUDA toolkit; `dice` needs a C++ toolchain,
MPI, HDF5, a Rust toolchain, and Boost compiled from source by its own
`build.sh`, on x86_64 Ubuntu only.

This is a hard filter, not a footnote. A researcher who cannot build Boost from
source cannot use Dice however well its features match. Fedora users should note
that `build.sh` hardcodes a Debian HDF5 path and that OpenMPI needs
`module load mpi/openmpi-x86_64`.

## Hosted documentation, and where it is wrong

Every solver carries a `docs` list in the registry. Each entry says what that
page answers, so the skill can link the page that addresses the question
instead of a landing page.

Two of them contradict this registry, which matters because a researcher will
believe the official documentation over an agent:

- **qiskit-addon-dice-solver's site documents 0.3.0.** Its API reference lists
  `solve_fermion` and `solve_hci` only. `solve_sci` and `n_roots` — the
  interface that makes Dice usable with the addon — are `main`-only and appear
  nowhere on the site. Someone reading it concludes there is no `sci_solver`
  interface at all.
- **The same site states the size ceiling as "128 or fewer orbitals" from
  16-byte determinant addresses.** That is the wording this registry corrects:
  the mechanism is `DetLen = 2` and the ceiling is 128 qubits, which is 64
  spatial orbitals. Do not repeat the upstream figure.

## Papers

Record a paper only where the project asks for one. Fulqrum is the case today:
the `citing.html` page names
[arXiv:2603.18731](https://arxiv.org/abs/2603.18731), and the registry's
`paper.describes` records which of Fulqrum's design claims that paper is the
source for. See the Fulqrum section above.

Dice's documentation cites three upstream SHCI papers (arXiv 1610.06660,
1606.07453 and 2405.05068) for the algorithm rather than for the wrapper. Those
describe the method, so they answer "how does SHCI work", not "what does this
package expose".

## Vendored references

`references/` holds documents the registry's cells depend on, vendored because
the originals lived only in local checkouts. Each carries a provenance note
saying who wrote it, what commit it assessed, and how far to trust it.

Never cite a path that exists only on one machine. Cite the vendored copy, or
the upstream repository and commit.

Currently: `sbd-complex-hamiltonian-support.md`.

## Maintaining the registry

Run `python scripts/render_table.py --check` after editing. It validates the
layer/value/confidence vocabulary, rejects a `blocked_by` on a `yes` cell, flags
any solver/feature pair with no entry, requires a `latest_release` per solver,
rejects a plain `yes` for a solver that has no release, requires a `since` on
unreleased capability in a project that does have releases, requires every
`docs` entry to be an https URL with a `what`, and requires a `paper` to carry
a title, url and `describes`.

Check the hosted `docs` links when re-verifying. A link that has rotted is
worse than no link, and upstream documentation drifts out of agreement with
this registry without warning — when it does, record the disagreement in that
entry's `stale` field rather than silently preferring one side.

When verifying a capability, check it against the **release tag**, not the
working tree — `git show <tag>:<path>` is the quick way. Record the tag in
`since`.

Quote `"yes"` and `"no"` in `value:` fields. Bare `yes`/`no` are YAML booleans.

When a solver's capability changes, update the registry and regenerate; do not
edit `capabilities-table.md`. Bump `meta.verified_on` when re-verifying against
the repositories.
