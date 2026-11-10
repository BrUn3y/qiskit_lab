# Reference: complex Hermitian Hamiltonian support in SBD

**What this is.** An assessment of `r-ccs-cms/sbd`, branch `main` at commit
`21f73b4`, dated 2026-08-25. Reproduced here because the registry's
`complex` / `sbd` cell rests on it.

**Provenance and how much to trust it.** Written by a Claude Code session
reading the SBD source, not by an SBD maintainer and not reviewed by one. Its
claims are sourced to file and line, and the `_UHFCPLX` aliasing bug was
confirmed by a standalone numerical reproduction — so the specific findings are
checkable. But the correctness verdicts on the numerical core rest on code
inspection plus a syntax-only compile, which the report says itself. Treat it as
a well-sourced lead to verify, not as an authority.

**Staleness.** Pinned to one commit on a repository this skill does not track.
Re-check against current `main` before relying on it. The findings most likely
to have changed are the three blockers, any of which may have been fixed.

---

## Verdict

**Partly.** The numerical core (framework + solvers) is genuinely
complex-Hermitian-correct. The chemistry entry points are not: the flagship TPB
driver cannot be instantiated as complex, the one complex-specific integral mode
is silently broken, and the FCIDUMP reader cannot carry complex integrals.

## What genuinely works

The framework and solver layers are correctly *Hermitian*, not merely templated
on an element type:

| Concern | Status | Evidence |
| --- | --- | --- |
| Inner product conjugates the bra | correct | `Conjugate(X[is]) * Y[is]` — `framework/dm_vector.h:40` (the `zdotc` convention) |
| Davidson subspace matrix fill | correct | `H[ib+nb*jb] = Conjugate(H[jb+nb*ib])` — `tpb/davidson.h:256,508,764`; also gdb, caop, and thrust variants |
| Dense eigensolver | correct | `MatHeev` dispatches to `zheev_`/`cheev_`, real eigenvalue output — `hp_numeric.h:482-560` |
| QR / orthogonalization | correct | `MatQr` dispatches to `zungqr_`/`cungqr_` (unitary, not `orgqr`) |
| Norms | correct | `SquaredNorm` overloaded as `re*re + im*im` — `framework/type_def.h:48-50` |
| MPI datatype | correct | `MPI_CXX_DOUBLE_COMPLEX` registered — `framework/type_def.h:61` |
| Lanczos tridiagonal | correct | Stored **real**, which is legitimate for Hermitian H: the diagonal `<v\|H\|v>` is real and the off-diagonal comes from a norm — `tpb/lanczos.h:78-107` |

A repo-wide grep for the *symmetric* (complex-incorrect) fill
`H[ib+nb*jb] = H[jb+nb*ib]` returns **zero hits**.

`Hij` also uses the correct bra/ket index order (`I1.Value(a,i)`,
`I2.Value(a,i,j,j)`), so it is not accidentally relying on real symmetry.

`gdb` and `caop` have real complex build paths — `using ElemType =
std::complex<double>` behind `#ifdef _COMPLEX`, wired to
`option(SBD_COMPLEX ... OFF)` at `CMakeLists.txt:32,74`.

### Compile-verified, not just inspected

Both of these instantiate cleanly under
`mpicxx -std=c++17 -fopenmp -fsyntax-only`:

```cpp
template std::complex<double> sbd::Hij<std::complex<double>>(...);
template void sbd::SetupIntegrals<std::complex<double>>(...);
```

## Blockers

### 1. The TPB path cannot be complex at all

`sbd::tpb::diag` is **not a template** — `tpb/sbdiag.h:139`:

```cpp
void diag(const MPI_Comm & comm,
          const SBD & sbd_data,
          ...
          double & energy,
          std::vector<double> & density,
          ...
          std::vector<std::vector<double>> & one_p_rdm,
          std::vector<std::vector<double>> & two_p_rdm) {
```

`double` is hardwired through the body as well — `double I0;
sbd::oneInt<double> I1; sbd::twoInt<double> I2;` (`tpb/sbdiag.h:185-187`),
`std::vector<double> W` (`:286`), `MultTPBThrust<double>` (`:336`),
`std::vector<double> hii` (`:370,376,497,500`).

Correspondingly `apps/chemistry_tpb_selected_basis_diagonalization/main.cc` has
no `_COMPLEX` guard at all.

This matters because TPB is the flagship path per `CLAUDE.md`, and everything
*beneath* `diag` (`tpb/davidson.h`, `tpb/mult.h`, `tpb/lanczos.h`) is already
complex-ready. It is a plumbing gap, not a math gap.

### 2. `_UHFCPLX` is broken and fails silently

`makeintegrals.h:68` has a complex-aware branch that applies the correct
**4-fold** symmetry with `Conjugate`:

```cpp
I2(i-1,j-1,k-1,l-1) = ElemT(value);
I2(k-1,l-1,i-1,j-1) = ElemT(value);
I2(j-1,i-1,l-1,k-1) = Conjugate(ElemT(value));
I2(l-1,k-1,j-1,i-1) = Conjugate(ElemT(value));
```

But `integrals.h` only branches on `_UHF`, never on `_UHFCPLX`. So under
`_UHFCPLX` you get the **8-fold real-symmetry** storage class, whose index map
folds `<ij|kl>` and `<kl|ij>` into a single slot — `integrals.h:91-99`:

```cpp
int a = std::max(ij,kl);
int b = std::min(ij,kl);
return store[a*(a+1)/2+b];
```

Reproduced numerically: writing `v = 1+0.5i` and its conjugate partner puts both
in the *same* slot, and the value reads back as `1-0.5i`.

```
after writes, I2(0,1,0,0) = (1,-0.5)  (expected (1,0.5))
conjugate partner I2(1,0,0,0) = (1,-0.5)  (expected (1,-0.5))
same slot? YES - ALIASED
```

The imaginary part gets its sign flipped, and **it compiles without a warning**
(`-D_UHFCPLX -fsyntax-only` exits 0).

Note also that `_UHFCPLX` appears in **exactly one place** in the whole repo
(that single `#elif`), so it is effectively vestigial.

### 3. FCIDUMP cannot carry complex integrals

The parser reads one `double` per line — `fcidump.h:69`, and identically in
`deserializeFCIDump` at `:201`:

```cpp
double value;
int i, j, k, l;
ss >> value >> i >> j >> k >> l;
```

and the container is typed `std::vector<std::tuple<double,int,int,int,int>>`
(`fcidump.h:25`). There is no on-disk route for complex integrals regardless of
`ElemT`.

## Verification status

Nothing tests complex.

- No `.github/` directory; no CI config anywhere in the repo.
- `tests/` is driven by hand-written Makefiles and is **not** registered with
  CMake/CTest — no `enable_testing()`, no `add_test`, no
  `add_subdirectory(tests)`. So `SBD_COMPLEX` never reaches the test build.
- `tests/functionality/test_inner_product.cc` — precisely the test that would
  catch a conjugation error — is `double`-only, and with real inputs
  `Conjugate` is the identity.
- Zero occurrences of `std::complex` under `tests/`.
- `SBD_COMPLEX` defaults OFF and **no** `CMakePresets.json` preset enables it
  (presets: macos-cpu, linux-cpu, fugaku-llvm, craype-thrust, nvhpc-thrust,
  omp5-nvidia, omp5-amd), so the complex configuration is likely rarely
  compiled.

The Hermitian correctness above is therefore **correct-by-inspection (plus a
syntax-only compile), not correct-by-verification.**

## Suggested order of work

Cheapest and highest-value first:

1. Add a complex `InnerProduct` / Davidson test. Cheap, and it validates the
   whole conjugation chain that is currently unexercised.
2. Fix `integrals.h` to branch on `_UHFCPLX` with 4-fold symmetry, **or** delete
   the dead macro. Leaving a silently-wrong mode in place is the worst option.
3. Extend the FCIDUMP reader to an optional second (imaginary) column.
4. Templatize `tpb/sbdiag.h` on `ElemT` if the TPB path needs complex support.

### Minor wart, worth noting either way

`caop::diag` and `gdb::diag` take `double & energy` even when `ElemT` is
complex, resolving it via `energy = GetReal(E)` (`caop/basic/sbdiag.h:258`,
`:322`). Harmless for genuinely Hermitian input, but it discards the imaginary
part silently rather than asserting it is negligible — so a non-Hermitian input
would fail quietly instead of loudly.

## Caveat on method

A full configure-and-link of `-DSBD_COMPLEX=ON` was not possible on this
machine: CMake's `find_package(MPI)` fails at `CMakeLists.txt:51` despite
OpenMPI being installed. All compile checks above were therefore
`-fsyntax-only` against the headers via
`the system mpicxx`. The `_UHFCPLX` aliasing bug was confirmed
separately by a standalone reproduction of the `integrals.h` index map, which
does not depend on MPI.
