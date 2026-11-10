<!--
  GENERATED FILE — NOT CANONICAL. Do not edit, and do not rely on it.

  Produced from registry.yaml by scripts/render_table.py, for sharing
  with people outside this skill. It can lag the registry, and it
  flattens detail that the registry carries in full.

  If you are an agent working from this skill: read registry.yaml for
  the data and capabilities.md for the reasoning. Nothing here is absent
  from those, so there is no reason to read further.
-->

> **Generated export, not the source of truth.** Built from
> `registry.yaml`; read that for anything load-bearing.

# SQD eigensolver capability matrix

Verified against the repositories listed below on 2026-11-06.

## How to read this

Each engine has up to three layers, and a capability present in one is not
necessarily reachable from the next:

1. **Engine** — the C++ or binary core. What the code can compute at all.
2. **Python** — the wrapper or bindings. Not everything is wrapped, and a
   wrapper may compute something without returning it.
3. **Addon** — what survives `qiskit-addon-sqd`'s `sci_solver` interface
   inside `diagonalize_fermionic_hamiltonian`.

A cell shows one glyph when every layer agrees, and `engine / python / addon`
when they differ.

| Glyph | Meaning |
| --- | --- |
| ✅ | supported |
| ❌ | not supported |
| ᵏ | supported; the addon forwards no keywords, so bind the option at construction (`functools.partial`) |
| 🚫 | computed, then discarded before the caller sees it |
| ⛔ | the solver supports this; **this interface cannot reach it**. The glyph before ⛔ is what the layer above does. |
| ❔ | unknown |
| — | not applicable |
| ᵘ | unverified — carried over, not checked against a source |
| † | carries a caveat; see the notes |
| `126q — CI string` | a row that is not a yes/no question shows its value instead of a glyph |
| ✅ (≥1.7.1) | supported, and the version is the release that introduced it — older installs do not have it |
| 🚧 | exists only in unreleased code — treat as unavailable |
| ✅✅ | tested, or checked against an independent reference |
| ◐ | partial — works on some code paths and not others |
| 🧱 | scaffolding only — no working end-to-end path |
| ⚠ | has known defects; read the notes before relying on it |

**A ✅ means supported in the solver's latest release**, never in unreleased
code. Those baselines are:

- PySCF selected CI: `2.14.0`
- Dice (SHCI): `0.3.0`
- Selected Basis Diagonalization: `1.7.2`
- Fulqrum (CPU): `0.5.0`
- Fulqrum (GPU): _no release_

| Feature | PySCF selected CI | Dice (SHCI) | Selected Basis Diagonalization | Fulqrum (CPU) | Fulqrum (GPU) |
| --- | --- | --- | --- | --- | --- |
| 1- and 2-RDM | [✅](#cell-rdm-pyscf) | [✅ (≥0.3.0) / 🚫](#cell-rdm-dice) | [✅ / ✅ᵏ (≥1.7.1)](#cell-rdm-sbd) | [❌](#cell-rdm-fulqrum-cpu) | [🚧](#cell-rdm-fulqrum-gpu) |
| Spin penalty <S^2> | [✅ᵏ](#cell-spin-penalty-pyscf) | [✅ (≥0.3.0) / ✅ᵏ (≥0.3.0)](#cell-spin-penalty-dice) | [❌†](#cell-spin-penalty-sbd) | [✅ / ❌†](#cell-spin-penalty-fulqrum-cpu) | [❔ᵘ](#cell-spin-penalty-fulqrum-gpu) |
| Multiple roots | [❔ᵘ / ❌](#cell-multiple-roots-pyscf) | [✅ (≥0.3.0) / 🚧⛔](#cell-multiple-roots-dice) | ❌ | [✅✅⛔](#cell-multiple-roots-fulqrum-cpu) | [🚧](#cell-multiple-roots-fulqrum-gpu) |
| TPB (tensor product basis) | ✅ | ✅ (≥0.3.0) | [✅](#cell-tpb-sbd) | [✅](#cell-tpb-fulqrum-cpu) | [🚧](#cell-tpb-fulqrum-gpu) |
| GDB (generalized determinant basis) | ❌ | [❌](#cell-gdb-dice) | [✅ / ◐⚠ (≥1.7.1) / ✅⛔ (≥1.7.1)†](#cell-gdb-sbd) | [✅⛔ (≥0.5.0)](#cell-gdb-fulqrum-cpu) | [🚧](#cell-gdb-fulqrum-gpu) |
| GPU support | ❌ | ❌ | [✅ / ✅ᵏ](#cell-gpu-sbd) | — | [🚧†](#cell-gpu-fulqrum-gpu) |
| General subspace manipulation | ❌ | [❌](#cell-subspace-manipulation-dice) | ❌ | [✅](#cell-subspace-manipulation-fulqrum-cpu) | [◐⚠](#cell-subspace-manipulation-fulqrum-gpu) |
| Complex-valued Hamiltonians | [❌](#cell-complex-pyscf) | [❔ᵘ](#cell-complex-dice) | [◐⚠ / ❌†](#cell-complex-sbd) | [✅ (≥0.4.5)](#cell-complex-fulqrum-cpu) | [❌](#cell-complex-fulqrum-gpu) |
| MPI / multi-node | ❌ | [✅ᵏ (≥0.3.0)](#cell-mpi-dice) | [✅](#cell-mpi-sbd) | [❌](#cell-mpi-fulqrum-cpu) | [🚧](#cell-mpi-fulqrum-gpu) |
| Native Windows | [✅ (≥2.15.0)](#cell-windows-pyscf) | [❌](#cell-windows-dice) | [❌](#cell-windows-sbd) | [❌](#cell-windows-fulqrum-cpu) | [❌](#cell-windows-fulqrum-gpu) |
| Size ceiling | [126q — CI string†](#cell-size-ceiling-pyscf) | [128q — determinant†](#cell-size-ceiling-dice) | [none (CPU, Thrust)†](#cell-size-ceiling-sbd) | [none†](#cell-size-ceiling-fulqrum-cpu) | [🚧 128q — determinant†](#cell-size-ceiling-fulqrum-gpu) |
| Install cost | [wheels + conda](#cell-install-cost-pyscf) | [git + heavy build†](#cell-install-cost-dice) | [compiles; conda WIP](#cell-install-cost-sbd) | [compiles; conda WIP](#cell-install-cost-fulqrum-cpu) | [not distributed](#cell-install-cost-fulqrum-gpu) |
| Ships an addon adapter | [✅](#cell-addon-adapter-pyscf) | [✅ (≥0.3.0)](#cell-addon-adapter-dice) | [✅](#cell-addon-adapter-sbd) | [✅ (≥0.5.0)](#cell-addon-adapter-fulqrum-cpu) | [❌](#cell-addon-adapter-fulqrum-gpu) |

Cells are links: click a glyph for the reasoning and sources behind it.

**One interface limitation, several columns.** Fulqrum (CPU) and Selected Basis Diagonalization carry a ⛔ in this table for the same reason: `sci_solver` passes a pair of half-string lists whose Cartesian product spans the subspace, so a flat determinant list cannot be expressed whatever the solver supports. One upstream limitation — https://github.com/Qiskit/qiskit-addon-sqd/issues/389 — surfacing in each column, not independent solver deficiencies.

## Cell notes

One entry per cell that carries reasoning, linked from the matrix.

<a id="cell-rdm-pyscf"></a>

**1- and 2-RDM — PySCF selected CI**

make_rdm1/make_rdm2 are computed and passed to SCIResult.

Source: `qiskit_addon_sqd/fermion.py solve_sci`

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-rdm-dice"></a>

**1- and 2-RDM — Dice (SHCI)**

_engine_:

The addon requests all four — DoSpinRDM, DoRDM, DoSpinOneRDM, DoOneRDM — so Dice computes the RDMs and writes spin1RDM.*.txt.

Source: `dice_solver.py:594`

_python_:

_read_dice_outputs loads only spin1RDM.0.0.txt and keeps just the diagonal, to build orbital occupancies. SCIResult is constructed without rdm1 or rdm2, and nothing reads a 2-RDM file at all. The data exists on disk in the temp directory, which clean_temp_dir=True deletes by default.

**Workaround.** Pass clean_temp_dir=False and parse spin1RDM.*.txt yourself. Outside the addon's API.

Source: `dice_solver.py:455, :129, :132`

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-rdm-sbd"></a>

**1- and 2-RDM — Selected Basis Diagonalization**

_engine_:

_python_:

Requires do_rdm=1. assemble_rdms builds spin-summed rdm1/rdm2 from SBD's raw one_p_rdm/two_p_rdm and populates SCIResult. Confirmed present at the 1.7.1 tag, not only on main. The `since` is the release it was verified in, not necessarily the one that introduced it.

Source: `python/sbd_solver.py:465 assemble_rdms`

_addon_:

Reachable, and the only obstacle is one argument. RDMs are off by default (`int do_rdm = 0` in both the TPB and GDB cores) because the SQD loop needs the energy and amplitudes and nothing else, so paying for RDMs on every iteration would be waste. Set do_rdm through sbd_config, which is keyword-only, and the returned best SCIResult carries them. The standalone CLI takes the same setting as a flag (tpb/sbdiag.h:112).

**Workaround.** create_sbd_solver(sbd_config={'do_rdm': 1})

Source: `tpb/sbdiag.h:41, gdb/sbdiag.h:26`

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-rdm-fulqrum-cpu"></a>

**1- and 2-RDM — Fulqrum (CPU)**

No RDM code outside the GPU path, in either the Python or the C++ layer. Fulqrum gained RDMs on the GPU only, so a researcher who needs them for embedding or fragmentation and has no NVIDIA hardware does not get them here. The adapter populates SCIResult with energy, sci_state and orbital_occupancies only (fulqrum/addon_sqd_support.py:325), leaving rdm1 and rdm2 unset.

**Workaround.** fulqrum/test/rdm_oracle.py is a short, self-contained NumPy implementation of spin-resolved 1- and 2-RDMs over an arbitrary determinant list, in the PySCF `make_rdm12s(reorder=True)` convention. `rdm12s(alpha, beta, coeff, m, rank)` takes the uint64 keys and amplitudes a CPU eigenvector already provides. It sits under `test/` with no API stability, and is written for correctness rather than for production determinant counts, so offer it only to someone willing to maintain their own copy.

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-rdm-fulqrum-gpu"></a>

**1- and 2-RDM — Fulqrum (GPU)**

FullStrsHamiltonian.compute_rdms (`rank=1` or `2`, `spin_summed=`) is collective over the communicator and returns full host arrays on every rank. Return forms and tensor indices follow PySCF `make_rdm12s(reorder=True)` (hamiltonian.py:59), so an embedding workflow written against PySCF can consume them directly. Dedicated kernels under fulqrum/gpu/kernels/rdm/, not a host fallback.

**Verification.** Passed on a CUDA device. Gated out of CI, like the rest of the GPU suite: every GPU test requires `gpu_available()` and no runner in .github/workflows/ has a device.

**Workaround.** These RDMs do not reach diagonalize_fermionic_hamiltonian, since the GPU path ships no sci_solver adapter — the caller drives FullStrsHamiltonian directly.

Source: `fulqrum/gpu/full_strs/hamiltonian.py:704`

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-spin-penalty-pyscf"></a>

**Spin penalty <S^2> — PySCF selected CI**

_python_:

Source: `fci.addons.fix_spin_(myci, ss=spin_sq)`

_addon_:

**Workaround.** partial(solve_sci_batch, spin_sq=0.0)

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-spin-penalty-dice"></a>

**Spin penalty <S^2> — Dice (SHCI)**

_engine_:

_python_:

_write_input_files emits `spin {spin_sq}` into input.dat when spin_sq is not None, so it reaches the binary. Not signature-only.

Source: `dice_solver.py:573`

_addon_:

**Workaround.** partial(solve_sci_batch, spin_sq=0.0)

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-spin-penalty-sbd"></a>

**Spin penalty <S^2> — Selected Basis Diagonalization**

_engine_:

_python_: (accepted-but-ignored)

solve_sci accepts spin_sq for signature compatibility with qiskit_addon_sqd.fermion.solve_sci and does nothing with it; the docstring says "unused by SBD". A workflow that passes spin_sq and swaps PySCF for SBD loses spin penalization with no error, no warning, and exit code zero. The most dangerous substitution in this registry.

Source: `python/sbd_solver.py:75, docstring at :92`

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-spin-penalty-fulqrum-cpu"></a>

**Spin penalty <S^2> — Fulqrum (CPU)**

_python_: (no spin feature; caller builds the operator)

Nothing ships ready to use: Fulqrum has no S^2 operator and no spin_sq argument, so a caller builds the penalty themselves. FermionicOperator takes arbitrary `++--` terms and supports `+` and scalar `*`, so S^2 is expressible, and `H + c * S_sq` reaches SubspaceHamiltonian through extended_jw_transformation like any other operator. The mode ordering is the trap: integrals.hpp:58 puts alpha in modes 0..norb-1 and beta in norb..2*norb-1, so an S^2 written for the interleaved convention is silently a different operator. The reported eigenvalue also includes the penalty, making the physical energy `energy - c * <S^2>`.

**Verification.** No Fulqrum test covers a user-written spin penalty, so this rests on checks against PySCF rather than the package's own suite. A hand-built S^2 matched pyscf.fci.spin_op.contract_ss elementwise, and penalizing a stretched H4 chain selected the lowest state of the targeted spin at the PySCF FCI energy. Every check used the full determinant space; the truncated subspaces SQD actually runs on are untested.

Source: `fulqrum/core/fermi_operator.pyx:56, fulqrum/convert/src/integrals.hpp:58`

_addon_:

No blocked_by: there is no penalty in Fulqrum for the adapter to drop. It takes integrals rather than an operator and builds the operator itself, and the operator-accepting factory below it is private, so a caller holding `H + c * S_sq` has nowhere to put it. A `partial(..., spin_sq=0.0)` binding carried over from PySCF or Dice raises TypeError, since the adapter takes no such argument, as does passing spin_sq to the factory. Building Fulqrum's solver fresh and not mentioning spin_sq loses the penalty in silence, exactly as the SBD substitution does.

Source: `fulqrum/addon_sqd_support.py:42, :93`

Tracking: https://github.com/Qiskit/qiskit-addon-sqd/issues/312

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-spin-penalty-fulqrum-gpu"></a>

**Spin penalty <S^2> — Fulqrum (GPU)**

Nothing ships a penalty on either Fulqrum path, so this is the same question the fulqrum-cpu cell answers yes for: whether a caller-built S^2 is an operator the GPU accepts. Most of that reasoning carries over. S^2 is two-body, spin-conserving and real, which is the shape the GPU asks for, and it wants the block spin ordering Fulqrum already uses.
Unresolved: the cross-sector S+S- terms, which move one alpha and one beta. The GPU rejects term-group patterns it cannot plan — `unsupported_groups` in operator_check.pyx, with reasons including crosses_sectors and cross_sign_not_separable — and whether S^2's groups land in a supported tier depends on group tiering that was not traced. Build S^2 and call `unsupported_groups` to settle it.

Source: `fulqrum/gpu/distributed/operator_check.pyx`

Tracking: https://github.com/Qiskit/qiskit-addon-sqd/issues/312

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-multiple-roots-pyscf"></a>

**Multiple roots — PySCF selected CI**

_python_:

**kwargs forwards nroots to kernel_fixed_space, which accepts it, but solve_sci builds a single SCIResult from sci_vec, so more than one root probably does not survive the wrapper. Not tested.

_addon_:

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-multiple-roots-dice"></a>

**Multiple roots — Dice (SHCI)**

_engine_:

_python_:

_write_input_files emits `nroots {n_roots}`; solve_sci then returns one SCIResult per root as a list.

Source: `dice_solver.py:570, :117-131`

_addon_:

The loop expects list[SCIResult] with one entry per subspace and returns a single best SCIResult. A per-subspace list of roots does not fit that contract, so excited states have no representation in the loop's return.

**Workaround.** Call solve_sci directly on a fixed subspace, outside diagonalize_fermionic_hamiltonian. Gives up configuration recovery.

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-multiple-roots-fulqrum-cpu"></a>

**Multiple roots — Fulqrum (CPU)**

_python_:

eigsh(Hsub, k=n) — free, since the caller supplies the eigensolver, and neither scipy nor PRIMME caps k.

Source: `fulqrum/test/test_eigen.py:56-70, :169-196`

_addon_:

Not an eigensolver limit — scipy and PRIMME both do multiple roots, and a direct Fulqrum call gets them. Two separate obstacles in the addon path. The adapter calls the eigensolver with a literal k=1 and expands **eigensolver_kwargs after it, so `k` is not a pass-through knob: supplying it raises TypeError for a duplicate keyword rather than overriding (`tol` and the like do pass through). A custom `eigensolver=` callable sidesteps that, since it may ignore the k it is handed and solve for however many roots it likes. What it cannot sidestep is the result shape: `_solve_one` keeps eigenvalues[0] and eigenvectors[:, 0] and builds one SCIResult, and the loop returns a single best result, so extra roots are computed and discarded. So a wrapper can retarget *which* root comes back — a different `which`, an interior root — but cannot return several.

Source: `fulqrum/addon_sqd_support.py:304,325`

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-multiple-roots-fulqrum-gpu"></a>

**Multiple roots — Fulqrum (GPU)**

PRIMME; --ncv controls the basis size and hence VRAM pressure.

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-tpb-sbd"></a>

**TPB (tensor product basis) — Selected Basis Diagonalization**

_engine_:

_python_:

The mature path, and the one the qiskit-addon-sqd integration uses.

Source: `sbd.tpb_diag`

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-tpb-fulqrum-cpu"></a>

**TPB (tensor product basis) — Fulqrum (CPU)**

Subspace's half-string mode takes a `(alpha_strings, beta_strings)` pair and forms the Cartesian product internally. Full-string mode takes explicit bitstrings instead, so the CPU path does both shapes — see the gdb row.

Source: `fulqrum/core/subspace.pyx:110-120`

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-tpb-fulqrum-gpu"></a>

**TPB (tensor product basis) — Fulqrum (GPU)**

Supported, and not the only shape — see the gdb row for the explicit-determinant path.

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-gdb-dice"></a>

**GDB (generalized determinant basis) — Dice (SHCI)**

_engine_:

The subspace entry point takes no general determinant list. It reads AlphaDets.bin and forms the Cartesian product of that list with *itself* — `Dets.resize(nAlphaDets*nAlphaDets)`, then occAlpha[i] for the alpha occupations and occAlpha[j] for the beta — so the subspace is a product basis, and one that additionally assumes the alpha and beta lists are identical. The block is hardcoded under `if (true)`, reads 5 bytes per string, and takes nalpha = nelec/2, so unequal spin populations are not expressible either.
BetaDets.bin is never read anywhere on the branch, although the addon writes it (dice_solver.py:625). A caller who supplies different alpha and beta lists gets the alpha list squared, with no error.
qiskit-addon-sqd#389 names Dice among the packages supporting general subspaces. That is contradicted here for the path the addon drives; it may refer to SHCI's own iterative determinant selection, which is Dice choosing a determinant set rather than the caller supplying one.

**Verification.** Read from upstream sanshar/Dice at origin/Riken, which matches the addon's fork pin on DetLen = 2 but was not diffed against caleb-johnson/Dice commit-for-commit. Read, not run.

Source: `SHCI/SHCI.cpp:289-341 (Riken branch)`

Tracking: https://github.com/Qiskit/qiskit-addon-sqd/issues/389

_python_:

Nothing in the wrapper writes a general determinant list, and the engine could not consume one if it did.

**No workaround.**

Tracking: https://github.com/Qiskit/qiskit-addon-sqd/issues/389

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-gdb-sbd"></a>

**GDB (generalized determinant basis) — Selected Basis Diagonalization**

_engine_:

Source: `vendor/sbd-upstream/apps/chemistry_gdb_selected_basis_diagonalization/`

_python_: (experimental)

Davidson only — there are no Lanczos kernels under gdb/, and gdb_diag rejects TPB's methods 2 and 3. Newer and less tested than the TPB path.

Known issues:

- Newer and less tested than the TPB path; the API is still evolving as upstream SBD does.
- Davidson only — no Lanczos kernels exist under gdb/, and gdb_diag rejects TPB's methods 2 and 3.

Source: `python/__init__.py:748 gdb_diag`

_addon_:

Two independent reasons. create_sbd_solver wraps solve_sci_batch, which calls tpb_diag only, so gdb_diag is unreachable from it. And the shapes cannot meet: sci_solver receives ci_strings as (strings_a, strings_b), a product basis, while gdb_diag takes a flat list of full determinants. The interface cannot express a GDB subspace, so no amount of argument binding reaches it.

**No workaround.**

Source: `python/sbd_solver.py:804 create_sbd_solver`

Tracking: https://github.com/Qiskit/qiskit-addon-sqd/issues/389

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-gdb-fulqrum-cpu"></a>

**GDB (generalized determinant basis) — Fulqrum (CPU)**

_python_:

Subspace has two input modes, and the length decides which. A length-2 list is half-string mode: Fulqrum sorts each list and takes the Cartesian product, which is TPB. A length-1 list is full-string mode, where the supplied full bit-strings are used as is with no product taken — that is a GDB subspace. So GDB is reachable, but only by constructing the Subspace yourself.

Source: `fulqrum/core/subspace.pyx:42`

_addon_:

The 0.5.0 adapter builds its Subspace from a length-2 list of alpha and beta half-strings, so it takes the Cartesian product and the subspace is TPB. This is the same interface limitation that blocks SBD here, not a second independent gap: sci_solver receives ci_strings as (strings_a, strings_b), and no argument binding makes a pair of half-string lists into a flat determinant list. Fulqrum appears in qiskit-addon-sqd#389 as a package whose engine supports general subspaces, which is true of the package and not of this path — do not read that issue as saying GDB reaches the loop today.

**Workaround.** Drive Fulqrum directly: build `fq.Subspace([full_strings])` in full-string mode and call the eigensolver yourself. Gives up configuration recovery.

Source: `fulqrum/addon_sqd_support.py:285`

Tracking: https://github.com/Qiskit/qiskit-addon-sqd/issues/389

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-gdb-fulqrum-gpu"></a>

**GDB (generalized determinant basis) — Fulqrum (GPU)**

FullStrsHamiltonian takes an explicit uint64 `(n, 2)` array of alpha/beta determinant pairs, and "the determinant set need not be a complete tensor-product subspace". The subspace must still have equal sector widths of 1 to 64 orbitals per spin, fixed per-sector electron counts, and block spin ordering with alpha in the low bits.

**Verification.** Passed on a CUDA device, and gated out of CI like the rest of the GPU suite.

Source: `fulqrum/gpu/full_strs/hamiltonian.py:41`

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-gpu-sbd"></a>

**GPU support — Selected Basis Diagonalization**

_engine_:

NVIDIA via Thrust/CUDA; NVIDIA or AMD via OpenMP offload (partial).

_python_:

TPB runs on all three backends. GDB has Thrust kernels only, so GDB on a GPU is NVIDIA-only and falls back to the host under 'gpu-omp'.

_addon_:

**Workaround.** create_sbd_solver(device_config=...)

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-gpu-fulqrum-gpu"></a>

**GPU support — Fulqrum (GPU)**

(NVIDIA only)

CUDA throughout — nvcc, cuBLAS, cuSPARSE. No HIP or ROCm path exists.

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-subspace-manipulation-dice"></a>

**General subspace manipulation — Dice (SHCI)**

Opaque binary driven by file-based I/O; no matvec is exposed.

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-subspace-manipulation-fulqrum-cpu"></a>

**General subspace manipulation — Fulqrum (CPU)**

SubspaceHamiltonian is a SciPy LinearOperator with a public matvec, so the matrix-vector product is directly accessible.

Source: `fulqrum/core/linear_operator.py`

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-subspace-manipulation-fulqrum-gpu"></a>

**General subspace manipulation — Fulqrum (GPU)**

GPU-resident matvec, reachable as a public `matvec(x)` on FullStrsHamiltonian (NumPy in, NumPy out; CuPy in, CuPy out) and as `_matvec` on the distributed operators, which advertise `supports_device_matvec`.

Known issues:

- Real type-2 operators only, so a general-operator use case — the reason to want matvec access at all — is not covered on GPU.

Source: `fulqrum/gpu/full_strs/hamiltonian.py:714`

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-complex-pyscf"></a>

**Complex-valued Hamiltonians — PySCF selected CI**

selected_ci is real-symmetric. No complex branch anywhere in the module: no dtype=complex, no .real/.imag handling, and a search for `complex` returns nothing. Every dtype= is int64/int32 for determinant strings and link indices; h1e and eri reach the C extensions as double.

Source: `pyscf/fci/selected_ci.py`

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-complex-dice"></a>

**Complex-valued Hamiltonians — Dice (SHCI)**

Not investigated. Dice is an SHCI code for real molecular Hamiltonians; the addon writes an FCIDUMP, which is real-valued in its common form. Treat as unsupported until someone checks.

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-complex-sbd"></a>

**Complex-valued Hamiltonians — Selected Basis Diagonalization**

_engine_: (CAOP only; chemistry real-only)

Split verdict, and the split is by model rather than by layer. For the chemistry paths SQD actually uses — TPB and GDB — complex is absent at every layer, and the headline answer for an SQD researcher is no. The CAOP model is where complex support is real: `caop::diag` is `template <typename ElemT>` (caop/basic/sbdiag.h:248) while `tpb::diag` is a plain non-template function (tpb/sbdiag.h:157), so the templating that makes complex possible covers CAOP and stops short of TPB. CAOP reaches Python only on main — `caop_diag_from_files` appears in no released tag through 1.7.2 — and the addon has no CAOP path at all, so nothing about it is reachable from diagonalize_fermionic_hamiltonian.
The framework and solver layers beneath are genuinely complex-Hermitian-correct, not merely templated: the inner product conjugates the bra (zdotc convention, framework/dm_vector.h:40), the Davidson subspace fill uses the Hermitian form H[ib+nb*jb] = Conjugate(H[jb+nb*ib]) across tpb, gdb, caop and thrust variants, MatHeev dispatches to zheev_/cheev_, MatQr to zungqr_/cungqr_ (unitary, not orgqr), and a repo-wide grep for the complex-incorrect symmetric fill returns zero hits. The chemistry entry points are where it breaks down — see known_issues.

Known issues:

- TPB cannot be complex at all. sbd::tpb::diag is declared `void diag(const MPI_Comm &` with no template header (tpb/sbdiag.h:157) and hardwires double through its body and RDM outputs, so the flagship path is real-only even though everything beneath it (davidson.h, mult.h, lanczos.h) is already complex-ready. A plumbing gap, not a math gap.
- The _UHFCPLX integral mode is silently wrong. makeintegrals.h:68 has a correct 4-fold-symmetry complex branch, but integrals.h only branches on _UHF, so _UHFCPLX falls through to 8-fold real-symmetry storage whose index map aliases <ij|kl> with <kl|ij>. Writing 1+0.5i reads back as 1-0.5i — the imaginary sign flips — and it compiles without a warning. The macro appears in exactly one place in the repo, so it is effectively vestigial.
- FCIDUMP cannot carry complex integrals. The parser reads one double per line (fcidump.h:69, :201) and the container is typed tuple<double,int,int,int,int>, so there is no on-disk route for complex integrals whatever ElemT is.
- caop::diag and gdb::diag take `double & energy` even when ElemT is complex, resolving via GetReal(E). Harmless for genuinely Hermitian input, but a non-Hermitian input fails quietly rather than loudly.

**Verification.** Nothing tests complex. No CI anywhere in the repo; tests/ is driven by hand-written Makefiles and is not registered with CMake/CTest, so SBD_COMPLEX never reaches the test build. test_inner_product.cc — the test that would catch a conjugation error — is double-only, and with real inputs Conjugate is the identity. Zero occurrences of std::complex under tests/. SBD_COMPLEX defaults OFF and no CMakePresets.json preset enables it, so the complex configuration is rarely compiled. The Hermitian correctness above is correct-by-inspection plus a syntax-only compile, not correct-by-verification.

Source: `references/sbd-complex-hamiltonian-support.md — assessment of r-ccs-cms/sbd main @ 21f73b4, 2026-08-25. Claude-authored, sourced to file and line, not maintainer-reviewed; see that file's provenance note.`

_python_:

Nothing in python/ mentions complex, and the bindings wrap tpb_diag and gdb_diag. Two separate reasons it could not work anyway: TPB is not templated on the element type at all, and the FCIDUMP route the bindings use to hand integrals to SBD cannot carry complex values. So this is not a thin wrapper gap — reaching complex from Python needs the chemistry entry points fixed upstream first.
CAOP, the one model whose engine code is complex-capable, is not a way around this. Its Python entry point `caop_diag_from_files` exists only on main and in no released tag through 1.7.2, it is gated on a `__sbd_has_caop__` backend attribute, and the SQD addon has no CAOP path, so it is not reachable through diagonalize_fermionic_hamiltonian however it is installed.

**No workaround.**

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-complex-fulqrum-cpu"></a>

**Complex-valued Hamiltonians — Fulqrum (CPU)**

A real kernel, not dtype plumbing. matvec takes the Cython fused type double_or_complex[::1], and the C++ templates omp_matvec[complex] and omp_matvec2[complex] are both instantiated. Fused types compile one specialization per type, so a genuine complex kernel exists. Confirmed present at the 0.4.5 release tag.

Graded `supported` rather than `verified`: the kernel plainly exists and the operator dtype tracks it, but no test exercising a complex Hamiltonian end to end was identified. Promote to `verified` on finding one.

Source: `fulqrum/core/spmv.pyx:210, :249, :280`

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-complex-fulqrum-gpu"></a>

**Complex-valued Hamiltonians — Fulqrum (GPU)**

Raises NotImplementedError — "TileGPUResidentHamiltonian currently supports real-valued operators only" — on a complex hsub. The full-string path is float64 throughout and describes itself as a real type-2 operator, so no GPU entry point accepts complex. The previous citation (:216) now lands on unrelated key-packing code.

Source: `fulqrum/gpu/distributed/dist_matvec_tile_resident.py:383`

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-mpi-dice"></a>

**MPI / multi-node — Dice (SHCI)**

_python_:

Invoked through mpirun; mpirun_options is passed straight through. The bridge spawns its own ranks per diagonalization, so the calling program must NOT itself run under mpirun — see execution_models.solver_spawns_mpirun.

Source: `dice_solver.py:523 _call_dice`

_addon_:

**Workaround.** partial(solve_sci_batch, mpirun_options='-n 8')

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-mpi-sbd"></a>

**MPI / multi-node — Selected Basis Diagonalization**

_engine_:

_python_:

_addon_:

No workaround needed. solve_sci_batch takes mpi_comm=None and resolves it to MPI.COMM_WORLD, and its first five parameters are exactly the addon's positional signature. So `sci_solver=sbd.solve_sci_batch` under `mpirun -n N python my_program.py` already spreads every diagonalization across all N ranks, and create_sbd_solver() with no arguments does the same by passing mpi_comm=None straight through. Pass mpi_comm= only to use a sub-communicator — an option, not a remedy for a gap.
Unlike Dice, this is collective: the whole program runs under one mpirun and the loop calls the solver from every rank. Supported by the addon since 0.13.0, so it is available in the 0.14.0 baseline. See execution_models.collective_spmd for how to launch it.

Source: `python/sbd_solver.py:508, :115-117, :804`

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-mpi-fulqrum-cpu"></a>

**MPI / multi-node — Fulqrum (CPU)**

Shared-memory threading: the CPU engine parallelizes with OpenMP (`#pragma omp parallel` throughout fulqrum/core/src/) and requires OpenMP 3.0+ (docs/install.rst:41). Nothing in the CPU tree imports mpi4py or touches a communicator — every such import is under fulqrum/gpu/. So it scales up a node by threads and not across nodes; a multi-node run means the GPU path, or another solver.

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-mpi-fulqrum-gpu"></a>

**MPI / multi-node — Fulqrum (GPU)**

Scales across GPUs by MPI rank, one GPU per rank, with NCCL, CUDA-aware MPI, host-MPI or in-process backends selectable per operator (fulqrum/gpu/distributed/backends/). Multi-node is the 2D-tile path. The NotImplementedError on `len(gpu_ids) > 1` bounds what one rank drives, not how many GPUs a job uses.

Source: `fulqrum/gpu/distributed/dist_matvec_tile_resident.py:402`

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-windows-pyscf"></a>

**Native Windows — PySCF selected CI**

Needs two floors: pyscf>=2.15.0 for the win_amd64 wheel, and qiskit-addon-sqd>=0.14.1, which dropped the `sys_platform != "win32"` marker on its pyscf dependency. An older addon installs on Windows with no solver, which presents as a missing-solver error rather than a platform one.

Source: `pyscf 2.15.0 wheel metadata; qiskit-addon-sqd 0.14.1 pyproject.toml`

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-windows-dice"></a>

**Native Windows — Dice (SHCI)**

Not distributed on any platform; the build path is Linux-only.

**No workaround.**

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-windows-sbd"></a>

**Native Windows — Selected Basis Diagonalization**

Linux and macOS classifiers only. Unsupported by omission rather than refused, but nothing upstream tracks it, so there is nothing to wait for.

**Workaround.** WSL or a Linux container.

Source: `pyproject.toml:17-18`

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-windows-fulqrum-cpu"></a>

**Native Windows — Fulqrum (CPU)**

Ruled out in the 0.5.0 docs: "no plan to do so". Settled, so do not route a Windows user here pending a future release.

**Workaround.** WSL or a Linux container.

Source: `docs/install.rst:91-94`

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-windows-fulqrum-gpu"></a>

**Native Windows — Fulqrum (GPU)**

Inherits the CPU package's non-support; also not distributed.

**No workaround.**

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-size-ceiling-pyscf"></a>

**Size ceiling — PySCF selected CI**

(hard; not tunable)

126 qubits (63 spatial orbitals). One CI string per signed int64, so bit 63 is the sign bit and unusable — hence 63 rather than 64. Raises NotImplementedError rather than degrading, and is not tunable: it is the width of the integer type, not a parameter.

Source: `pyscf/fci/cistring.py:265, :289, :346`

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-size-ceiling-dice"></a>

**Size ceiling — Dice (SHCI)**

(hard; recompile to change)

128 qubits (64 spatial orbitals). A determinant is a fixed two-word array (`DetLen = 2`), giving 2 x 64 spin orbitals. Tunable only by editing DetLen and recompiling, which build.sh does not expose. This is the fork the addon builds; upstream sets DetLen = 6.

Source: `SHCI/global.h:32, SHCI/Determinants.h:177`

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-size-ceiling-sbd"></a>

**Size ceiling — Selected Basis Diagonalization**

(gpu-omp caps; see note)

No hard limit on CPU — determinants are runtime-sized vectors, so memory binds. Thrust (`device='gpu'`) is uncapped too: both limit checks sit inside `#ifdef USE_OMP_OFFLOAD`, so only an OpenMP-offload build reaches them. The cap is therefore specific to `device='gpu-omp'`, which in practice means AMD — on NVIDIA a researcher who hits it can switch to Thrust and the ceiling is gone. Independently of backend, past 63 spatial orbitals needs sbd-eigensolver>=1.7.2; earlier versions overflow int64 converting the result back.

Source: `tpb/sbdiag.h:221-234, python/sbd_solver.py:739`

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-size-ceiling-fulqrum-cpu"></a>

**Size ceiling — Fulqrum (CPU)**

(memory-bound)

No hard limit; memory is the real bound. The only enforced ceiling is width_t being uint16_t, so 65535 qubits. A prefilter changes representation above 128 qubits, which costs wasted work rather than correctness.

Source: `fulqrum/core/src/constants.hpp:22`

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-size-ceiling-fulqrum-gpu"></a>

**Size ceiling — Fulqrum (GPU)**

(hard; kernel rewrite to change)

128 qubits total, 64 per spin species (64 spatial orbitals), raised as "the GPU operator supports 1 to 64 {name} qubits". Checked on every entry point — :2470, :2819 and aabb_parents.py:49 repeat it, and the full-string path states the same rule (fulqrum/gpu/full_strs/hamiltonian.py:35) — so a different operator is not a way around it. Half-strings are scalar unsigned long long in the kernels, making this a representational limit, tunable only by rewriting them.
The CPU path has no hard ceiling at this width, so the same system can run on CPU and be rejected here.

Source: `fulqrum/gpu/distributed/dist_matvec_tile_resident.py:1489`

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-install-cost-pyscf"></a>

**Install cost — PySCF selected CI**

The only solver installable without a toolchain. One py3-none-<platform> wheel per platform covers every Python version, and conda-forge carries it (per-Python there, so a new Python release can reach it later).

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-install-cost-dice"></a>

**Install cost — Dice (SHCI)**

(no conda)

The heaviest in the set and not distributed: the PyPI name is a 0.0.0.dev0 reservation. Needs a C++ toolchain, MPI, HDF5, Rust, and Boost compiled from source by build.sh. x86_64 Ubuntu 22.04/24.04 only.

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-install-cost-sbd"></a>

**Install cost — Selected Basis Diagonalization**

Sdist only, so pip compiles on the host and the backends you get depend on the toolchain the build finds. A conda-forge recipe is under review, which would make this the first non-PySCF solver installable without a local build.

Tracking: https://github.com/conda-forge/staged-recipes/pull/35125

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-install-cost-fulqrum-cpu"></a>

**Install cost — Fulqrum (CPU)**

Sdist only — pip compiles the Cython extensions on the host. A conda-forge recipe is in review at staged-recipes#35533. PRIMME is not on conda-forge either (staged-recipes#35091), so a conda install would start out with scipy's eigsh as the only eigensolver from the channel.

Tracking: https://github.com/conda-forge/staged-recipes/pull/35533

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-install-cost-fulqrum-gpu"></a>

**Install cost — Fulqrum (GPU)**

Not on PyPI or conda-forge. Needs a CUDA toolkit, Open MPI with a matching mpi4py, and ILP64 OpenBLAS — the BLAS inside NumPy/SciPy wheels will not do.

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-addon-adapter-pyscf"></a>

**Ships an addon adapter — PySCF selected CI**

The addon's default; ships in the same package as the loop.

Source: `qiskit_addon_sqd/fermion.py solve_sci_batch`

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-addon-adapter-dice"></a>

**Ships an addon adapter — Dice (SHCI)**

The bridge package presents Dice to the loop. Building it is the cost here, not writing the adapter.

Source: `qiskit_addon_dice_solver solve_sci_batch`

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-addon-adapter-sbd"></a>

**Ships an addon adapter — Selected Basis Diagonalization**

create_sbd_solver returns a callable for sci_solver=, and is also how every keyword-only option (RDMs, device, MPI comm) gets bound.

Source: `python/sbd_solver.py:804 create_sbd_solver`

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-addon-adapter-fulqrum-cpu"></a>

**Ships an addon adapter — Fulqrum (CPU)**

`sci_solver_from_integrals` — pass its return value straight to diagonalize_fermionic_hamiltonian. Requires fulqrum>=0.5.0; earlier releases had no adapter and the caller wrote it. Install as `qiskit-addon-sqd[fulqrum]`, which also brings PRIMME. Fulqrum still supplies no eigensolver: the factory takes `eigensolver=` and defaults to scipy's eigsh.

Source: `fulqrum/addon_sqd_support.py:42`

[Back to the matrix](#sqd-eigensolver-capability-matrix)

<a id="cell-addon-adapter-fulqrum-gpu"></a>

**Ships an addon adapter — Fulqrum (GPU)**

Not distributed, so there is nothing to adapt.

[Back to the matrix](#sqd-eigensolver-capability-matrix)

## Where capability is lost between layers

Each entry below is a place where an engine or wrapper can do something
that the next layer up cannot reach.

### Dice (SHCI) — 1- and 2-RDM (lost at the python layer)

**computed but discarded** — not fixable through the API.

_read_dice_outputs loads only spin1RDM.0.0.txt and keeps just the diagonal, to build orbital occupancies. SCIResult is constructed without rdm1 or rdm2, and nothing reads a 2-RDM file at all. The data exists on disk in the temp directory, which clean_temp_dir=True deletes by default.

Source: `dice_solver.py:455, :129, :132`

Workaround: Pass clean_temp_dir=False and parse spin1RDM.*.txt yourself. Outside the addon's API.

### Selected Basis Diagonalization — 1- and 2-RDM (lost at the addon layer)

**option not forwarded** — fixable with functools.partial.

Reachable, and the only obstacle is one argument. RDMs are off by default (`int do_rdm = 0` in both the TPB and GDB cores) because the SQD loop needs the energy and amplitudes and nothing else, so paying for RDMs on every iteration would be waste. Set do_rdm through sbd_config, which is keyword-only, and the returned best SCIResult carries them. The standalone CLI takes the same setting as a flag (tpb/sbdiag.h:112).

Source: `tpb/sbdiag.h:41, gdb/sbdiag.h:26`

Workaround: create_sbd_solver(sbd_config={'do_rdm': 1})

### PySCF selected CI — Spin penalty <S^2> (lost at the addon layer)

**option not forwarded** — fixable with functools.partial.

Workaround: partial(solve_sci_batch, spin_sq=0.0)

### Dice (SHCI) — Spin penalty <S^2> (lost at the addon layer)

**option not forwarded** — fixable with functools.partial.

Workaround: partial(solve_sci_batch, spin_sq=0.0)

### PySCF selected CI — Multiple roots (lost at the addon layer)

**cannot survive the loop** — call the solver directly.

### Dice (SHCI) — Multiple roots (lost at the addon layer)

**cannot survive the loop** — call the solver directly.

The loop expects list[SCIResult] with one entry per subspace and returns a single best SCIResult. A per-subspace list of roots does not fit that contract, so excited states have no representation in the loop's return.

Workaround: Call solve_sci directly on a fixed subspace, outside diagonalize_fermionic_hamiltonian. Gives up configuration recovery.

### Fulqrum (CPU) — Multiple roots (lost at the addon layer)

**cannot survive the loop** — call the solver directly.

Not an eigensolver limit — scipy and PRIMME both do multiple roots, and a direct Fulqrum call gets them. Two separate obstacles in the addon path. The adapter calls the eigensolver with a literal k=1 and expands **eigensolver_kwargs after it, so `k` is not a pass-through knob: supplying it raises TypeError for a duplicate keyword rather than overriding (`tol` and the like do pass through). A custom `eigensolver=` callable sidesteps that, since it may ignore the k it is handed and solve for however many roots it likes. What it cannot sidestep is the result shape: `_solve_one` keeps eigenvalues[0] and eigenvectors[:, 0] and builds one SCIResult, and the loop returns a single best result, so extra roots are computed and discarded. So a wrapper can retarget *which* root comes back — a different `which`, an interior root — but cannot return several.

Source: `fulqrum/addon_sqd_support.py:304,325`

### Dice (SHCI) — GDB (generalized determinant basis) (lost at the python layer)

**absent from the bindings** — use the engine directly.

Nothing in the wrapper writes a general determinant list, and the engine could not consume one if it did.

Tracking: https://github.com/Qiskit/qiskit-addon-sqd/issues/389

**No workaround.**

### Selected Basis Diagonalization — GDB (generalized determinant basis) (lost at the addon layer)

**interface cannot express it** — not fixable without an interface change.

Two independent reasons. create_sbd_solver wraps solve_sci_batch, which calls tpb_diag only, so gdb_diag is unreachable from it. And the shapes cannot meet: sci_solver receives ci_strings as (strings_a, strings_b), a product basis, while gdb_diag takes a flat list of full determinants. The interface cannot express a GDB subspace, so no amount of argument binding reaches it.

Source: `python/sbd_solver.py:804 create_sbd_solver`

Tracking: https://github.com/Qiskit/qiskit-addon-sqd/issues/389

**No workaround.**

### Fulqrum (CPU) — GDB (generalized determinant basis) (lost at the addon layer)

**interface cannot express it** — not fixable without an interface change.

The 0.5.0 adapter builds its Subspace from a length-2 list of alpha and beta half-strings, so it takes the Cartesian product and the subspace is TPB. This is the same interface limitation that blocks SBD here, not a second independent gap: sci_solver receives ci_strings as (strings_a, strings_b), and no argument binding makes a pair of half-string lists into a flat determinant list. Fulqrum appears in qiskit-addon-sqd#389 as a package whose engine supports general subspaces, which is true of the package and not of this path — do not read that issue as saying GDB reaches the loop today.

Source: `fulqrum/addon_sqd_support.py:285`

Tracking: https://github.com/Qiskit/qiskit-addon-sqd/issues/389

Workaround: Drive Fulqrum directly: build `fq.Subspace([full_strings])` in full-string mode and call the eigensolver yourself. Gives up configuration recovery.

### Selected Basis Diagonalization — GPU support (lost at the addon layer)

**option not forwarded** — fixable with functools.partial.

Workaround: create_sbd_solver(device_config=...)

### Selected Basis Diagonalization — Complex-valued Hamiltonians (lost at the python layer)

**absent from the bindings** — use the engine directly.

Nothing in python/ mentions complex, and the bindings wrap tpb_diag and gdb_diag. Two separate reasons it could not work anyway: TPB is not templated on the element type at all, and the FCIDUMP route the bindings use to hand integrals to SBD cannot carry complex values. So this is not a thin wrapper gap — reaching complex from Python needs the chemistry entry points fixed upstream first.
CAOP, the one model whose engine code is complex-capable, is not a way around this. Its Python entry point `caop_diag_from_files` exists only on main and in no released tag through 1.7.2, it is gated on a `__sbd_has_caop__` backend attribute, and the SQD addon has no CAOP path, so it is not reachable through diagonalize_fermionic_hamiltonian however it is installed.

**No workaround.**

### Dice (SHCI) — MPI / multi-node (lost at the addon layer)

**option not forwarded** — fixable with functools.partial.

Workaround: partial(solve_sci_batch, mpirun_options='-n 8')

## How the parallelism is launched

Two incompatible models. Which one a solver uses decides how the
researcher starts their program, and it is not a capability either
one is missing.

### solver spawns mpirun

Applies to: `dice`

Launch: `python my_program.py — NOT under mpirun`

The calling program runs as a single ordinary process, outside any MPI environment, and the solver launches its own workers. The qiskit-addon-dice-solver bridge shells out through mpirun on every diagonalization (dice_solver.py:523 _call_dice), with mpirun_options passed straight through.

**Tradeoffs.** Works in a notebook and needs no MPI-aware setup, which is why the HPC guide keeps it for interactive work — and the reason this model survives rather than being superseded. Costs: a process launch per diagonalization, and the ranks exist only for the duration of each call, so nothing is reused across iterations. Running the program itself under mpirun is wrong here and will not do what the researcher expects.

### collective spmd

Applies to: `sbd`

Launch: `mpirun -n <N> python my_program.py`

The whole Python process runs under one launcher — `mpirun -n 128 python my_program.py` — and diagonalize_fermionic_hamiltonian is called collectively from every rank. The sci_solver step is the only collective operation: all ranks participate in it, so the solver can spread one diagonalization across every process, while preparing CI strings, processing results and checking convergence happen on the control process alone. The return value is broadcast, so it is the same on every rank. sbd.solve_sci takes mpi_comm and defaults to MPI.COMM_WORLD (python/sbd_solver.py:76, :115-117).

**Tradeoffs.** The direction the ecosystem is moving, and what the upstream HPC guide recommends: it composes with job schedulers and other parallel software, and scales to large process counts. One MPI setup for the whole run rather than one per diagonalization. Costs: every rank must reach the collective call with arguments that agree, and the program has to be launched under MPI — see `rules_out_notebooks`.

**Rules out notebooks.** A Jupyter notebook cannot use this model. The kernel is one process started by the notebook server, not by mpirun, so there is nothing to run collectively; `mpirun -n N python my_program.py` has no notebook equivalent.
So treat notebook use as a selection criterion rather than a preference: if the researcher needs to work in a notebook, the collective model is out, whatever else recommends it. That rules out SBD's MPI path and leaves either a single-process SBD run or a solver that spawns its own ranks. Interactive development in a notebook followed by a batch script for production is a reasonable split, and worth suggesting when someone wants both.

**Notes.** A collective solver may also split the ranks into groups and diagonalize several subspaces at once, since every subspace of an iteration arrives in one sci_solver call. The addon does not divide the processes and nothing in its interface describes them, so that is the solver's own concern.

**Addon support.** Added in qiskit-addon-sqd 0.13.0 (releasenotes/notes/0.13/ spmd-support-214a17c1c745a761.yaml). diagonalize_fermionic_hamiltonian is the only API that may be called collectively; everything else must be called from the control process alone. The helpers live in qiskit_addon_sqd.processes — is_mpi_execution, process_index, process_count, is_control_process, broadcast, barrier.

⚠ The default PySCF sci_solver is not distributed, so collective mode is only useful with a solver that is. Pairing SPMD launch with the default solver gains nothing.

Source: `qiskit_addon_sqd/fermion.py — diagonalize_fermionic_hamiltonian Note`

Guide: <https://quantum.cloud.ibm.com/docs/addons/qiskit-addon-sqd/guides/hpc-acceleration> — The upstream HPC acceleration guide: both execution models, why SPMD is recommended, which APIs are collective, and the threading and error-handling expectations. The page to send a cluster user to.

## The `sci_solver` interface

These constraints explain most of the addon-layer losses above.

### positional call

diagonalize_fermionic_hamiltonian calls the solver as sci_solver(ci_strings, one_body_tensor, two_body_tensor, norb, nelec) — five positional arguments, no keywords forwarded. Every solver option in this registry is keyword-only, so none is reachable without binding it first.

Source: `qiskit_addon_sqd/fermion.py:780`

Workaround: `sci_solver = partial(solve_sci_batch, spin_sq=0.0)`

### consumed result fields

The loop reads energy, orbital_occupancies, sci_state and carryover from each SCIResult. It never reads rdm1 or rdm2, and diagonalize_fermionic_hamiltonian returns only the single best SCIResult. RDMs therefore reach the researcher only on that one object, and only if the solver populated them.

Source: `qiskit_addon_sqd/fermion.py:_process_sci_results`

### subspace shape

ci_strings is a pair (strings_a, strings_b) whose Cartesian product spans the subspace. The interface cannot express a flat list of full determinants, so a GDB subspace has no representation in it. The restriction is inherited from PySCF. SBD and Fulqrum both support general subspaces below the addon, which can represent a state of interest with far fewer configurations, so for them this interface is what stands in the way. Dice does not — see the gdb/dice cell, which corrects the solver list in the tracking issue.

Tracking: https://github.com/Qiskit/qiskit-addon-sqd/issues/389

## Solvers

### PySCF selected CI (`pyscf`)

- Engine: PySCF fci.selected_ci
- Python: qiskit_addon_sqd.fermion.solve_sci
- Latest release: `2.14.0`
- Build: plain `pip install`
- The default solver in `qiskit-addon-sqd`.
- PyPI: `pyscf` 2.15.0 — wheels, no toolchain needed
- Wheel platforms: linux-x86_64, linux-aarch64, macos-x86_64, macos-arm64, windows-x86_64
- conda-forge: available (2.14.0)

**PyPI.** Five py3-none-<platform> wheels, so one wheel per platform covers every Python version, and pip install needs no toolchain on any of them. The win_amd64 wheel arrived in 2.15.0, which also declares `Operating System :: Microsoft :: Windows`, so PySCF is the only solver in this registry installable on native Windows and needs 2.15.0 or newer to be. The packaging facts here were read from 2.15.0 metadata; the code citations in this cell (the orbital ceiling, the cistring.py lines) were verified against baseline_releases.pyscf 2.14.0 and not re-checked since.

**conda-forge.** win-64 builds are available, so native Windows works on this channel too. Unlike PyPI these are per-Python rather than one wheel per platform, so a new Python release can reach conda-forge later.

**Limits.** 126 qubits (63 spatial orbitals), and the ceiling is hard: PySCF raises NotImplementedError rather than degrading. CI strings are packed one per signed numpy int64, so bit 63 is the sign bit and unusable, leaving 63 spatial orbitals. Enforced at a dozen sites in pyscf/fci/cistring.py — `norb >= 64` raises at cistring.py:346, 367, 384, 411 and 446, and the string-generating paths raise "System with 64 orbitals or more" at cistring.py:265 and 289. Not tunable: the limit is the width of the integer type the representation is built on, not a parameter. Source pin: meta.sources.pyscf.

**Notes.** The default solver, shipped in the same package as the loop, so the only layer-3 friction is keyword binding. The loop itself (qiskit-addon-sqd 0.14.0) is also on conda-forge, so a pure-PySCF SQD workflow installs entirely from conda-forge. qiskit-addon-sqd 0.14.1 dropped the `sys_platform != "win32"` marker from its pyscf dependency, so the addon now requires pyscf on every platform; 0.14.0 and earlier made it conditional, which is why a Windows install of the addon used to come up without a solver.

**Documentation.**

- <https://pyscf.org/user/ci.html> — Configuration interaction user guide, including the selected-CI solver this path uses.
- <https://pyscf.org/> — Documentation root, for everything upstream of the solver.
- <https://qiskit.github.io/qiskit-addon-sqd/> — The SQD addon's own documentation, which is where `solve_sci` and `diagonalize_fermionic_hamiltonian` are documented. Relevant to every solver here, not only PySCF.

### Dice (SHCI) (`dice`)

- Engine: Dice SHCI binary (caleb-johnson fork, built by build.sh)
- Python: qiskit_addon_dice_solver.solve_sci
- Latest release: `0.3.0`
- Build: heavy — see below
- PyPI: `qiskit-addon-dice-solver` 0.0.0.dev0 — name placeholder, not installable
- conda-forge: not available

**Packaging.** The PyPI name exists but holds only a 0.0.0.dev0 name reservation, so `pip install qiskit-addon-dice-solver` does not give a working package. Install from a git checkout after build.sh compiles Boost and the Dice fork. Treat this as not distributed.

**What the pieces are.** Two separable pieces, and most of this column's losses are at the seam. Dice itself is a mature standalone SHCI code. qiskit-addon-dice-solver is a Python/addon bridge over it: it writes input.dat plus the determinant files, shells out to the binary through mpirun, and parses the output back into an SCIResult. It implements no diagonalization of its own.
So when a capability is missing here, say which piece is missing it. The RDMs are the worked example — the engine computes them and the bridge drops them on the way back, which is a different fact from "Dice cannot do RDMs" and points at a different workaround.

**Release status.** Tagged 0.1.0 (2024-09), 0.2.0 (2025-01) and 0.3.0 (2025-03) on GitHub, but never published to PyPI — the PyPI name holds only a 0.0.0.dev0 placeholder. So "released" here means a git tag to check out, not something pip can fetch.
0.3.0 exposes solve_dice, solve_fermion and solve_hci. The solve_sci entry point — the one that plugs into diagonalize_fermionic_hamiltonian as an sci_solver — and its n_roots argument exist only on main, 24 commits past the tag. Cells below distinguish the two.
Recommend main over any tag for this solver. Installation is a git checkout plus build.sh regardless, so a tag offers none of the usual benefits — no wheel, no resolver guarantee — and the latest tag predates the interface that makes Dice work with the addon. This is a deliberate exception to the general preference for released versions, and it holds only because nothing here is distributed.

**Build requirements.** C++ toolchain, MPI, HDF5, a Rust toolchain for the Python package, and Boost 1.85.0 compiled from source by build.sh, which also clones and makes the Dice fork. x86_64 with Ubuntu 22.04 or 24.04; Fedora is unsupported and build.sh hardcodes a Debian HDF5 path.

**Engine-only capability.** Full SHCI — multi-iteration selection, perturbative corrections, RDM output. The addon pins Dice to a single Davidson pass by setting a maximal select_cutoff, so none of that is reachable from Python.

**Limits.** 128 qubits (64 spatial orbitals), hard. A determinant is a fixed array of two 64-bit words — `const int DetLen = 2` in SHCI/global.h:32, used as `long repr[DetLen]` in SHCI/Determinants.h:177 — giving 2 x 64 = 128 spin orbitals, which is 128 qubits. The half-determinant class HalfDet uses `repr[DetLen / 2]` (Determinants.h:72), one word per spin species. Tunable only by editing DetLen and recompiling the engine, which the addon's build.sh does not expose. Note this is a property of the fork the addon builds, not of Dice generally: upstream sanshar/Dice sets DetLen = 6. An earlier revision of this registry recorded "128 orbitals, from 16-byte determinant addresses", which was wrong in both unit and mechanism. Source pin: meta.sources.dice-fork.

**Documentation.**

- <https://qiskit.github.io/qiskit-addon-dice-solver/> — Documentation for qiskit-addon-dice-solver, the Python/addon bridge that drives the Dice binary and presents it to the SQD addon. Covers supported platforms, the build.sh installation sequence and the bridge's limitations. The place to look for anything about getting Dice to talk to the loop, as opposed to what the SHCI engine itself can do.
  - ⚠ Documents 0.3.0, so its API reference lists only solve_fermion and solve_hci. `solve_sci` — the entry point that plugs into diagonalize_fermionic_hamiltonian — and `n_roots` are main-only and appear nowhere on this site. A researcher reading it will conclude there is no sci_solver interface. Say so when citing it.
Its Limitations section also states the size ceiling as "128 or fewer orbitals" from 16-byte determinant addresses. This registry's `limits` block corrects both the unit and the mechanism: `DetLen = 2` gives 128 qubits, which is 64 spatial orbitals. Use this registry's figure.
- <https://sanshar.github.io/Dice/> — Upstream Dice documentation — the SHCI algorithm, input keywords and benchmarks. Describes full SHCI, most of which the addon pins out, so read it for the engine rather than for what the wrapper exposes.

### Selected Basis Diagonalization (`sbd`)

- Engine: SBD C++ core and CLI apps
- Python: sbd.solve_sci / sbd.gdb_diag
- Latest release: `1.7.2`
- Build: compiles C++ on install
- PyPI: `sbd-eigensolver` 1.7.2 — source build, toolchain needed
- conda-forge: **in progress** — https://github.com/conda-forge/staged-recipes/pull/35125

**python API.** `sbd.solve_sci / sbd.gdb_diag` — pybind11 bindings. Installed from PyPI as an sdist, so pip compiles the extension modules on the host.

**c++ API (header-only).** `#include <sbd/...> — dozens of headers under include/sbd/` — Header-only. No compiled library to build or link: CMake declares add_library(sbd_headers INTERFACE) and include/ holds no .cc/.cpp sources. Consuming it from C++ means adding an include path, which is a much lighter integration than the Python route's source build suggests. The CLI apps under apps/ are separate programs built on these headers, and CAOP exists only there.

**Packaging.** Source distribution only — zero wheels published, so pip compiles the extension modules on the install machine and the backends you get depend on the toolchain the build finds. The README says as much. A conda-forge recipe is under review in staged-recipes#35125, which would make this the first non-PySCF solver installable without a local build.

**Build requirements.** Compiles C++ on install; MPI; optional NVHPC or OpenMP-offload toolchains for the GPU backends. No published wheels.

**Engine-only capability.** CAOP (creation/annihilation operator) diagonalization, in vendor/sbd-upstream/apps/caop_selected_basis_diagonalization/. Not wrapped.

**Limits.** Depends on the backend, and the varying axis is CPU vs. GPU rather than
TPB vs. GDB.

**CPU:** no hard limit. Determinants are nested `std::vector<size_t>`,
sized at runtime by `det_vector::init_elem_size` (tpb/sbdiag.h:219), so
width grows with the system and memory is what binds.

**GPU (Thrust, `device='gpu'`):** no hard limit either. Both checks
below are compiled only `#ifdef USE_OMP_OFFLOAD`, so a Thrust build
never reaches them and behaves like the CPU path.

**GPU (OpenMP offload, `device='gpu-omp'`, `USE_OMP_OFFLOAD` builds):**
256 spin orbitals / 128 spatial orbitals, hard. Two fixed-size macros
apply, both at chemistry/basic/omp_offload.h:14-15, and the tighter one
binds.

Because Thrust is uncapped, this ceiling is in practice an AMD
constraint: `gpu-omp` is the only GPU path for AMD, while an NVIDIA user
can switch to `device='gpu'` instead of recompiling. Raising it for AMD
means editing the macro and also adjusting the Python package's
setup.py, so it is not purely an upstream C++ change.
`SBD_MAX_SPINORBITALS = 256` caps spin orbitals directly, checked as
`2*norbs > SBD_MAX_SPINORBITALS` at tpb/sbdiag.h:230.
`SBD_MAX_DETSIZE = 16` caps the packed determinant at 16 words, checked
at tpb/sbdiag.h:225. Words hold `bit_length` bits rather than 64, so at
the default `bit_length` of 20 that second macro permits of order a few
hundred spin orbitals — the spin-orbital cap is what a researcher
actually hits. Raising `bit_length` loosens the determinant-size
constraint and never the spin-orbital one. Both are tunable by editing
the macros and recompiling.

Treat 256 as "of order a few hundred": it is a compile-time constant
someone may well have bumped, so read the macros in the tree being used
rather than quoting this figure.

**The abort exits zero.** Both checks call
`MPI_Abort(MPI_COMM_WORLD, 0)`, so the job prints a diagnostic and
terminates with a success status. A batch script, a `make` recipe or a
`subprocess.check_call` therefore reads an over-cap run as having
succeeded, and the researcher sees a missing result rather than a
failure. Tell anyone sizing a `gpu-omp` run to check the output rather
than the exit code.

Both conditions are also guarded by `mpi_rank == 0`, so only rank 0
evaluates them while other ranks continue into the fixed-size arrays the
macros protect. Reported upstream as
https://github.com/r-ccs-cms/sbd/issues/115, which also covers the
exit-zero status.

**Caveat: these checks are unreleased.** They entered the C++ core in
commit d814f68, which is on no tag, and HEAD sits 366 commits past
v1.3.0 — a build from a released tag has no such guard.

The guards live only in tpb/sbdiag.h and apply only to the OpenMP-offload
backend. They are absent from gdb/sbdiag.h, but that is not a gap: no
file under chemistry/gdb/ references USE_OMP_OFFLOAD at all, so GDB has
no OpenMP-offload path and never reaches the fixed-size arrays the macros
protect. GDB's GPU support is the Thrust backend (`device='gpu'`,
gdb/*_thrust.h), which uses its own representation. The Python wrapper
does document `device='gpu-omp'` for gdb_diag and dispatches to
`backend.gdb_diag`, so what such a call does is a question about the
bindings rather than about these limits — untested here.

**All backends:** `bit_length` must stay <= 63. `bitadvance()` in
framework/bit_manipulation.h computes `(1 << bit_length) - 1` on a 64-bit
`size_t`, so 64 is undefined behavior; in practice the shift is masked to
zero and the mask collapses. The Python wrapper documents this and
defaults to 20 (`SBD_DEFAULT_BIT_LENGTH`, python/sbd_solver.py:41).

**Python layer:** past 63 spatial orbitals needs
`sbd-eigensolver>=1.7.2`, whatever the backend allows. Earlier versions
overflow int64 converting the result back, so `solve_sci` raises
OverflowError at 64 orbitals and hangs instead under MPI
(`_ci_string_dtype`, python/sbd_solver.py:739). Below 64 orbitals the
version makes no difference.

Source pins: meta.sources.sbd-core, meta.sources.sbd-python.

**Notes.** device= selects 'cpu', 'gpu' (Thrust/CUDA, NVIDIA only) or 'gpu-omp' (OpenMP offload, NVIDIA or AMD) per call. Every backend the toolchain supports builds into one install.

**Documentation.**

- <https://qiskit.github.io/sbd-eigensolver-python/> — The Python bindings' documentation: the backend table (cpu, gpu, gpu-omp), the TPB-vs-GDB discussion, the `sci_solver` integration snippet with DeviceConfig and sbd_config, and the API reference. The best single page to hand someone choosing SBD.
- <https://github.com/r-ccs-cms/sbd> — The upstream C++ core, a different repository from the Python package. Where the CLI apps and CAOP live, and what the engine-layer cells and limit macros are read from.

### Fulqrum (CPU) (`fulqrum-cpu`)

- Engine: Fulqrum Cython/C++ core
- Python: fulqrum.SubspaceHamiltonian + an eigensolver the caller chooses
- Latest release: `0.5.0`
- Build: compiles C++ on install
- `sci_solver`: Since 0.5.0, via `fulqrum.addon_sqd_support.sci_solver_from_integrals` (fulqrum/addon_sqd_support.py:42) — pass its return value straight to `diagonalize_fermionic_hamiltonian(..., sci_solver=...)`. Install as `pip install "qiskit-addon-sqd[fulqrum]"`. On 0.4.5 and earlier there was no adapter and the caller wrote it, so state `fulqrum>=0.5.0` — the addon's extra only requires >=0.4.4, which an older pin satisfies without the adapter. The extra also installs PRIMME. Fulqrum still is not an eigensolver: the factory takes an `eigensolver=` argument and defaults to `scipy.sparse.linalg.eigsh`.
- PyPI: `fulqrum` 0.5.0 — source build, toolchain needed
- conda-forge: **in progress** — https://github.com/conda-forge/staged-recipes/pull/35533

**Packaging.** Source distribution only — no wheels — so pip compiles the Cython extensions on the host. A conda-forge recipe is in review at staged-recipes#35533. Its PRIMME tests are excluded because PRIMME is not on conda-forge yet; that recipe is staged-recipes#35091.

**Not an eigensolver.** Fulqrum is not an eigensolver. It builds the subspace Hamiltonian and implements the sparse matrix-vector product; the caller supplies the eigensolver and iterates. Describing it as an eigensolver misstates what the package does and obscures why it is on this list, so state the split when introducing it.
This is about the division of labour, not about integration effort. Since 0.5.0 Fulqrum ships the SQD addon adapter itself, so the split costs an `eigensolver=` argument rather than writing glue code.
Two eigensolvers are in routine use against it, and the choice is a real one:

  scipy  scipy.sparse.linalg.eigsh (ARPACK). Already a hard dependency,
         so nothing to install. What every page of the hosted docs and
         both tutorials use. The default recommendation.
  primme Optional dependency, minimum 3.2.3, listed under Optional in
         docs/install.rst. Generally better performance, and what the
         repository's own benchmarks use throughout
         (benchmarks/test/test_h2o_full.py:64,
         test_ch4_dimer_1e6.py:55, both with
         method="PRIMME_DEFAULT_MIN_MATVECS"). Covered by
         fulqrum/test/test_primme.py in both matrix-free and
         csr-fast modes.

So: scipy for an easy install, PRIMME for performance. The hosted docs name only scipy, so PRIMME has to be mentioned rather than looked up. This registry holds no head-to-head timing, so do not quote a speedup figure — say PRIMME generally performs better and leave it there.
Both consume the same object, so switching is a one-line change and not a re-integration. Three input routes, per the docs: Hsub itself (matrix-free, least memory, slowest), to_csr_linearoperator(), and to_csr_linearoperator_fast() (about 2x the memory, and the one the docs say to try first).

**Build requirements.** Compiles C++ (Boost headers vendored, OpenMP 3+).

**Limits.** No hard limit; memory is the real bound. Nothing rejects a wide subspace. The only enforced ceiling is width_t being uint16_t, so 65535 qubits (fulqrum/core/src/constants.hpp:22), checked per term by _validate_indices.
One width-dependent taper, and it is in the off-diagonal paths rather than the diagonal precompute. The paired-group prefilter keys each half-string into a uint64: at width <= 128 qubits total, half_key packs the half exactly; above that a multi-word hash takes over (`half_fits_in_word = width <= 2 * BITS_PER_BLOCK`, fulqrum/core/src/type2_group_table.hpp:500, dispatched at :445, with split_point = width / 2 at :498). The key only gates whether a candidate is looked up (type2_prefilter_pairs, :877 and :892), so a hash collision costs wasted work and never a wrong result. The same threshold governs matvec2.hpp, csr2.hpp and csrlike_builder2.hpp, which share the dispatch.
The diagonal precompute has no width threshold at all. compute_diag_vector_fast is selected by operator structure, not size: fast_diag_compatible tests type == 2, is_diagonal, a term count of W*(W+1)/2 and all-'1' projectors (fulqrum/core/src/diag.hpp:93). Both it and compute_diag_vector take the same boost::dynamic_bitset rows, and `_disable_fast_diag` (fulqrum/core/spmv.pyx:146) is a manual override rather than a size gate.
The 64-qubits-per-spin-species figure belongs to the GPU path, not here: see the fulqrum-gpu limits block, where half-strings are scalar unsigned long long and the builders reject more than 64 orbitals per sector. The two ceilings have different widths and different mechanisms, so do not merge them. Source pin: meta.sources.fulqrum.

**Notes.** Decouples operator construction from eigensolving: builds a SubspaceHamiltonian that behaves as a SciPy LinearOperator and leaves the eigensolver to the caller — scipy's eigsh or PRIMME, per `not_an_eigensolver`. Multiple roots and general subspace manipulation both follow from that design. Using it inside diagonalize_fermionic_hamiltonian means writing the adapter yourself; the N2 tutorial in `docs` is the closest worked example.

**Paper.** A generalized framework for quantum subspace diagonalization — Paul D. Nation, Abdullah Ash Saki, Hwajung Kang, [arXiv:2603.18731](https://arxiv.org/abs/2603.18731)

The citation the project asks for, and the source for Fulqrum's design rather than merely a reference to drop in a bibliography. It is where three claims in this registry come from: the extended operator alphabet (projection and ladder operators beyond the Pauli set) that lets one code base cover both fermionic and spin systems; bit-set encoding of bit-strings, which is the mechanism behind the "no hard limit" in `limits`; and the deliberate separation of subspace construction from eigensolving, which is why the caller supplies the eigensolver.
The paper does not name Fulqrum — it describes the framework the package implements. Cite it as the paper behind Fulqrum's approach, not as a paper about the package.
Reports reduced memory and runtime against prior approaches, "in some cases by an order of magnitude or more". Quote that as the paper's claim rather than as this registry's finding; nothing here reproduces it.

Citation requested at https://qiskit.github.io/fulqrum/citing.html.

**Documentation.**

- <https://qiskit.github.io/fulqrum/subspace_hamiltonians.html> — How to get eigenvalues out of a SubspaceHamiltonian: the three input routes, the LinearOperator subclassing that makes matrix-free mode work, and interpret_vector for reading an eigenvector back as bit-strings. The page to read before writing the adapter.
- <https://qiskit.github.io/fulqrum/tutorials/n2_full_sqd_loop.html> — A full SQD loop on N2 written against Fulqrum — the closest thing to a worked example of the adapter a researcher would otherwise write from scratch. Also shows seeding v0 from the Hamiltonian diagonal.
- <https://qiskit.github.io/fulqrum/install.html> — Dependencies, including PRIMME under Optional, and the note that clang outperforms gcc for this code.
- <https://qiskit.github.io/fulqrum/> — Documentation root — user guide, tutorials and API reference.

### Fulqrum (GPU) (`fulqrum-gpu`)

- Engine: Fulqrum CUDA kernels (fulqrum/gpu/kernels)
- Python: fulqrum.gpu.*Hamiltonian + distributed_primme_eigsh
- Latest release: none
- Build: compiles C++ and CUDA on install
- Not an `sci_solver`: using it inside the loop means writing the adapter.
- PyPI: not distributed
- conda-forge: not available

**Packaging.** Not distributed. The `fulqrum` sdist on PyPI is the CPU package and carries none of the CUDA paths; the GPU build is a source build from the branch with FQ_BUILD_GPU=1.

**Not an eigensolver.** Same split as the CPU package: it supplies the GPU-resident matrix-vector product, not the eigensolver. The distributed path is built around PRIMME rather than leaving the choice open, so --ncv is the knob that controls basis size and VRAM pressure. PRIMME is used with Fulqrum's own patches, eight of them under patches/primme/, so this is a patched PRIMME rather than the packaged one.

**Release status.** Nothing published; every claim here describes unreleased code. The branch, its declared version and the floor to ask for once it ships are in meta.sources.fulqrum-gpu.

**Build requirements.** The CPU requirements plus a CUDA toolkit (nvcc, cuBLAS, cuSPARSE, cudart) and FQ_BUILD_GPU=1. Also Open MPI with a matching mpi4py, and OpenBLAS ILP64 with `_64_`-suffixed symbols — GPU_INSTALL.md states that ordinary LP64 BLAS and the private libraries inside NumPy and SciPy wheels are not acceptable substitutes. A driver or a CuPy wheel alone does not supply the toolchain. The reference stack is CUDA 13.3, CuPy 14.1, mpi4py 4.1, OpenBLAS ILP64 0.3.34, on H100 (sm_90).

**Limits.** 128 qubits total, 64 per spin species (64 spatial orbitals), hard. Enforced in Python rather than in the kernels: "the GPU operator supports 1 to 64 {name} qubits", raised per sector at fulqrum/gpu/distributed/dist_matvec_tile_resident.py:1489, with further `2 <= n <= 64` checks at :2470 and :2819 and in fulqrum/gpu/distributed/aabb_parents.py:49. The full-string path states the same rule (fulqrum/gpu/full_strs/hamiltonian.py:35). The mechanism is representational — half-strings are scalar unsigned long long in the kernels — so it is tunable only by rewriting them for multi-word half-strings, not by a recompile.
The CPU path has no hard ceiling at this width; it switches its half-string prefilter to a multi-word hash and keeps going. So the same system can run on CPU and be rejected outright on GPU. Source pin: meta.sources.fulqrum-gpu.

**Notes.** Four operators, all reached through `fulqrum.gpu`: GPUHamiltonian for a single device, TileGPUResidentHamiltonian and DistributedMPIGPUHamiltonian for distributed runs, and FullStrsHamiltonian for an explicit determinant set. Narrower than the CPU path in two ways: real type-2 operators only, and 64 orbitals per spin sector. Multi-GPU is by MPI rank, so `len(gpu_ids) > 1` bounds one rank to one GPU and is not a single-GPU limit.
Well tested, but the whole GPU suite needs a CUDA device and no CI runner has one, so it passes where someone runs it rather than on every commit. What establishes each capability is in that cell's `verified_by`.

## Supported, but do not trust blindly

Capability that exists without being dependable. These may still be the
right choice — but a researcher should know what they are taking on, and
a passing smoke test proves little when support is path-dependent.

### Selected Basis Diagonalization — GDB (generalized determinant basis) (python layer)

◐ **partial** — works on some code paths and not others.

Davidson only — there are no Lanczos kernels under gdb/, and gdb_diag rejects TPB's methods 2 and 3. Newer and less tested than the TPB path.

Known issues:

- Newer and less tested than the TPB path; the API is still evolving as upstream SBD does.
- Davidson only — no Lanczos kernels exist under gdb/, and gdb_diag rejects TPB's methods 2 and 3.

Source: `python/__init__.py:748 gdb_diag`

### Fulqrum (GPU) — General subspace manipulation (python layer)

◐ **partial** — works on some code paths and not others.

GPU-resident matvec, reachable as a public `matvec(x)` on FullStrsHamiltonian (NumPy in, NumPy out; CuPy in, CuPy out) and as `_matvec` on the distributed operators, which advertise `supports_device_matvec`.

Known issues:

- Real type-2 operators only, so a general-operator use case — the reason to want matvec access at all — is not covered on GPU.

Source: `fulqrum/gpu/full_strs/hamiltonian.py:714`

### Selected Basis Diagonalization — Complex-valued Hamiltonians (engine layer)

◐ **partial** — works on some code paths and not others.

Split verdict, and the split is by model rather than by layer. For the chemistry paths SQD actually uses — TPB and GDB — complex is absent at every layer, and the headline answer for an SQD researcher is no. The CAOP model is where complex support is real: `caop::diag` is `template <typename ElemT>` (caop/basic/sbdiag.h:248) while `tpb::diag` is a plain non-template function (tpb/sbdiag.h:157), so the templating that makes complex possible covers CAOP and stops short of TPB. CAOP reaches Python only on main — `caop_diag_from_files` appears in no released tag through 1.7.2 — and the addon has no CAOP path at all, so nothing about it is reachable from diagonalize_fermionic_hamiltonian.
The framework and solver layers beneath are genuinely complex-Hermitian-correct, not merely templated: the inner product conjugates the bra (zdotc convention, framework/dm_vector.h:40), the Davidson subspace fill uses the Hermitian form H[ib+nb*jb] = Conjugate(H[jb+nb*ib]) across tpb, gdb, caop and thrust variants, MatHeev dispatches to zheev_/cheev_, MatQr to zungqr_/cungqr_ (unitary, not orgqr), and a repo-wide grep for the complex-incorrect symmetric fill returns zero hits. The chemistry entry points are where it breaks down — see known_issues.

Known issues:

- TPB cannot be complex at all. sbd::tpb::diag is declared `void diag(const MPI_Comm &` with no template header (tpb/sbdiag.h:157) and hardwires double through its body and RDM outputs, so the flagship path is real-only even though everything beneath it (davidson.h, mult.h, lanczos.h) is already complex-ready. A plumbing gap, not a math gap.
- The _UHFCPLX integral mode is silently wrong. makeintegrals.h:68 has a correct 4-fold-symmetry complex branch, but integrals.h only branches on _UHF, so _UHFCPLX falls through to 8-fold real-symmetry storage whose index map aliases <ij|kl> with <kl|ij>. Writing 1+0.5i reads back as 1-0.5i — the imaginary sign flips — and it compiles without a warning. The macro appears in exactly one place in the repo, so it is effectively vestigial.
- FCIDUMP cannot carry complex integrals. The parser reads one double per line (fcidump.h:69, :201) and the container is typed tuple<double,int,int,int,int>, so there is no on-disk route for complex integrals whatever ElemT is.
- caop::diag and gdb::diag take `double & energy` even when ElemT is complex, resolving via GetReal(E). Harmless for genuinely Hermitian input, but a non-Hermitian input fails quietly rather than loudly.

**Verification.** Nothing tests complex. No CI anywhere in the repo; tests/ is driven by hand-written Makefiles and is not registered with CMake/CTest, so SBD_COMPLEX never reaches the test build. test_inner_product.cc — the test that would catch a conjugation error — is double-only, and with real inputs Conjugate is the identity. Zero occurrences of std::complex under tests/. SBD_COMPLEX defaults OFF and no CMakePresets.json preset enables it, so the complex configuration is rarely compiled. The Hermitian correctness above is correct-by-inspection plus a syntax-only compile, not correct-by-verification.

Full assessment: [`references/sbd-complex-hamiltonian-support.md`](references/sbd-complex-hamiltonian-support.md)

Source: `references/sbd-complex-hamiltonian-support.md — assessment of r-ccs-cms/sbd main @ 21f73b4, 2026-08-25. Claude-authored, sourced to file and line, not maintainer-reviewed; see that file's provenance note.`

## Packaging

A researcher on a conda-managed stack cannot drop a source-compiled C++
extension into it without care, so this dimension can decide the choice on
its own.

The question is not whether a package is on PyPI, but whether installing it
needs a compiler.

| Solver | PyPI | `pip install` | Needs a toolchain? | conda-forge |
| --- | --- | --- | --- | --- |
| PySCF selected CI | `pyscf` | ✅ wheels | no | ✅ 2.14.0 |
| Dice (SHCI) | `qiskit-addon-dice-solver` | ❌ placeholder only | — | ❌ |
| Selected Basis Diagonalization | `sbd-eigensolver` | ⚠️ source build | **yes** | ⚠️ in progress ([PR](https://github.com/conda-forge/staged-recipes/pull/35125)) |
| Fulqrum (CPU) | `fulqrum` | ⚠️ source build | **yes** | ⚠️ in progress ([PR](https://github.com/conda-forge/staged-recipes/pull/35533)) |
| Fulqrum (GPU) | ❌ | — | — | ❌ |

A source build is not merely slower. For `sbd-eigensolver` the backends you
end up with depend on the toolchain the build finds, so two machines running
the same pip command can get different GPU support.

## Tracked upstream

Gaps with a known issue or pull request. Check these before trusting a
`no` above — the state may have moved since this file was generated.

- https://github.com/Qiskit/qiskit-addon-sqd/issues/312
  - Fulqrum (CPU) / Spin penalty <S^2> (addon)
  - Fulqrum (GPU) / Spin penalty <S^2> (python)
- https://github.com/Qiskit/qiskit-addon-sqd/issues/389
  - Dice (SHCI) / GDB (generalized determinant basis) (engine)
  - Dice (SHCI) / GDB (generalized determinant basis) (python)
  - Selected Basis Diagonalization / GDB (generalized determinant basis) (addon)
  - Fulqrum (CPU) / GDB (generalized determinant basis) (addon)
  - interface: subspace shape
- https://github.com/conda-forge/staged-recipes/pull/35125
  - Selected Basis Diagonalization / Install cost (python)
  - Selected Basis Diagonalization — conda-forge packaging
- https://github.com/conda-forge/staged-recipes/pull/35533
  - Fulqrum (CPU) / Install cost (python)
  - Fulqrum (CPU) — conda-forge packaging

## Unverified cells

Carried over from the source table and not checked against any source:

- Fulqrum (GPU) / Spin penalty <S^2> (python)
- PySCF selected CI / Multiple roots (python)
- Dice (SHCI) / Complex-valued Hamiltonians (python)

## Verified against

- `qiskit-addon-sqd` — `github.com/Qiskit/qiskit-addon-sqd`
- `qiskit-addon-dice-solver` — `github.com/Qiskit/qiskit-addon-dice-solver`
- `dice` — `github.com/caleb-johnson/Dice (the fork build.sh clones; upstream is sanshar/Dice)`
- `sbd-eigensolver-python` — `github.com/Qiskit/sbd-eigensolver-python`
- `sbd-upstream` — `github.com/r-ccs-cms/sbd`
- `fulqrum` — `github.com/Qiskit/fulqrum (qiskit-community/fulqrum redirects here)`
- `fulqrum-gpu` — `github.com/Qiskit/fulqrum, v1.0.0-rc branch`

## Source pins

Claims citing a `file:line` are keyed to one of these, so they can be checked against the exact code they were read from. Line numbers drift between revisions; these pins do not.

| key | kind | pin | where |
| --- | --- | --- | --- |
| `pyscf` | release | `2.14.0` | installed package |
| `dice-fork` | commit | `3198db1f8e0066489d173d30a52bc21967969a0f` | github.com/caleb-johnson/Dice (branch `Riken`) |
| `sbd-core` | commit | `95bf45a5be9ffd977fac7b0aaa359833caf3401a (v1.3.0-366-g95bf45a)` | github.com/r-ccs-cms/sbd (branch `main`) |
| `sbd-python` | release | `1.7.2` | github.com/Qiskit/sbd-eigensolver-python |
| `fulqrum` | release | `0.5.0` | github.com/Qiskit/fulqrum |
| `fulqrum-gpu` | commit | `2e2d66e` | github.com/Qiskit/fulqrum (branch `v1.0.0-rc`) |

**`pyscf`.** Inspected from an installed 2.14.0 wheel, which matches baseline_releases.pyscf. Line numbers are stable for a released version.

**`dice-fork`.** The fork build.sh clones, not upstream sanshar/Dice. build.sh clones without --branch, so it takes this repository's default branch, which is Riken rather than master. The distinction matters for the determinant width: this fork sets DetLen = 2, upstream sets 6. Cite this fork for any Dice capability the addon exposes.

**`sbd-core`.** The C++ core, a different repository from the sbd-eigensolver Python package that baseline_releases tracks. HEAD is 366 commits past the newest tag, so the GPU-OMP limit macros are unreleased code — see the `unreleased` note in the sbd limits block.

**`sbd-python`.** Citations verified present at tag 1.7.2, matching baseline_releases.sbd-eigensolver. Every SBD citation was re-checked by symbol at this tag, not just carried forward.

**`fulqrum`.** The public CPU package, which baseline_releases.fulqrum tracks. Citations verified at tag 0.5.0. The repository moved from qiskit-community to the Qiskit org; the old URL redirects.

**`fulqrum-gpu`.** The GPU module, public on the v1.0.0-rc branch as one commit on top of the 0.5.0 tag.
The branch declares `__version__ = "1.0.0"`, so `fulqrum>=1.0.0` is the floor that means "has the GPU module". It is a release candidate: no tag, nothing on PyPI, so the fulqrum-gpu cells stay `unreleased: true` and the floor is what to state once it ships.

