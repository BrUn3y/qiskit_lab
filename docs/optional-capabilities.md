# Optional SQD and Fermionic Environments

The base `pyproject.toml`, `uv.lock`, DAM wrapper and container remain lightweight:
none installs SQD, PySCF, JAX, qiskit-fermions or ffsim. Bundling an official skill
does not install its packages. Do not `uv pip install` optional packages into the
base `.venv`: `scripts/dam/quantum` runs `uv run --locked --no-dev` and synchronizes
that environment, which can remove packages absent from its lock.

## Select Only the Required Profile

`environments/optional/` is a separate, non-workspace uv project with its own
committed `uv.lock` (including transitive versions, wheel URLs and hashes). It
installs the current checkout of qiskit-lab as an editable local dependency.
It supports the same Python 3.11-3.13 range and pins Qiskit 2.6.2 to match the
base SDK and the qiskit-fermions 0.4.1 ABI requirement, `qiskit>=2.5,<2.7`.
The base's direct runtime packages and SciPy are also constrained to their root
lock versions. Other optional-environment transitives are determined by its own
lock, not by the root lock. Run commands from the repository root:

| Profile | Direct pinned packages | Scope |
| --- | --- | --- |
| `sqd` | qiskit-addon-sqd 0.14.1, PySCF 2.15.0 | Default CPU selected-CI solver for a small SQD workflow. |
| `fermionic` | qiskit-fermions 0.4.1 | Operators, encodings and circuits, without ffsim simulation. |
| `fermionic-sim` | qiskit-fermions[ffsim] 0.4.1, ffsim 0.0.86, PySCF 2.15.0 | Fixed-particle-number fermionic simulation and small exact checks. |

For example, install and verify only SQD:

```sh
uv sync --locked --project environments/optional --python 3.12 --extra sqd
uv run --locked --project environments/optional --extra sqd qiskit-lab doctor --capability sqd
uv run --locked --project environments/optional --extra sqd python scripts/dam/check-optional.py sqd
```

Or install only fermionic operators/circuits:

```sh
uv sync --locked --project environments/optional --python 3.12 --extra fermionic
uv run --locked --project environments/optional --extra fermionic qiskit-lab doctor --capability fermionic
uv run --locked --project environments/optional --extra fermionic python scripts/dam/check-optional.py fermionic
```

For fermionic simulation, replace every `--extra fermionic` above with
`--extra fermionic-sim`, and each trailing profile with `fermionic-sim`.
To combine SQD and simulation, pass `--extra sqd --extra fermionic-sim` to
**every** sync/run. Extras are not remembered across commands: omitting one on
the next `uv run` may remove its packages. Do not use `scripts/dam/quantum`
to execute an optional script: it deliberately selects the root project.
Use `uv run --locked --project environments/optional --extra PROFILE python YOUR_SCRIPT.py`.

By default the separate environment lives at `environments/optional/.venv/`.
Do not point `UV_PROJECT_ENVIRONMENT` at the base `.venv`. If this variable is
already set by a development tool, unset it before these commands, or assign a
different absolute environment path for the optional project. Neither the
root wrapper nor an optional command should share that path.
The first install needs package-index access; after the wheels are cached, add
uv's `--offline` to refuse all installer network access.

## What Doctor Establishes

Default `doctor` is offline and credential-free. It reads distribution metadata
in **its own interpreter**, not other virtual environments. It neither imports
the optional packages, scans account files, reads credential environment
variables, installs anything nor constructs an IBM service. Existing credential
presence fields are retained as JSON `null`, with `credential_check:
"not_performed"`; they no longer imply a credential probe. Only explicit
`--online` requests a live backend query, using the existing SDK path.

`optional_capabilities` reports `missing`, `version_mismatch`, `metadata_error`,
`unsupported_platform` or `installed`. `installed` means the documented direct
package versions are present, **not** that every native library, transitive
dependency or scientific workflow has been validated. Different versions may
work, but are not the reproducible recipe verified here. A normal base `doctor`
exits 0 even when optional packages are missing. With one or more
`--capability PROFILE` arguments it exits 1 unless all requested profiles have
their pinned metadata installed on a documented platform.

Run the explicit offline smoke script to exercise the native libraries. It
prints package versions before doing any calculation, then checks:

- `sqd`: PySCF selected CI on two noninteracting spatial orbitals, against
  the analytic ground energy -2 and singlet spin.
- `fermionic`: compiled fermionic anticommutation and circuit construction.
- `fermionic-sim`: the above plus a four-mode block-spin hopping circuit through
  ffsim, against the analytic survival probability `cos(0.5)**2`.

These are installation checks on synthetic models, not production simulations,
benchmarks, QPU access checks or proofs of scientific correctness at scale.
They never construct an IBM service. No credentials are required.

## Platform Limits

The wheel-only recipes target CPython 3.11-3.13 on 64-bit Linux with glibc >=2.28
(x86_64/aarch64), macOS (arm64; x86_64 except `fermionic-sim`), and Windows x86_64.
macOS OS-version minima and transitive wheel availability are enforced by uv,
not comprehensively inferred by doctor. Only Linux x86_64 is exercised in this
repository's optional smoke CI; other targets are packaging-compatible recipes,
not claims of executed cross-platform verification.

The project forbids source builds of qiskit-fermions, ffsim, PySCF and jaxlib.
An unavailable wheel fails installation rather than silently compiling a
machine-specific library. Intel macOS has no ffsim 0.0.86 wheel; native ARM64
Windows, 32-bit platforms and musl Linux are not covered. Use a compatible
Linux host/container or WSL Linux target, not a source-build workaround in the
base environment. Doctor's platform check is conservative recipe guidance,
not a package-index or native-loader test.

The pinned official fermionic skill says native Windows ffsim is unavailable.
That statement predates the ffsim 0.0.86 `win_amd64` wheel and its upstream
Windows wheel-test configuration. These project-owned instructions describe
the inspected package pins; the official skill, license, revision and hashes
remain unchanged. PySCF's Windows wheel requires >=2.15.0; SQD >=0.14.1 removes
its former non-Windows solver dependency marker. These recipes pin both.

## Solver Boundaries and Maintenance

This supplies one reproducible CPU SQD starting point, not every solver.
It does not install SBD, Dice, Fulqrum, PRIMME, CUDA extras, MPI or Pyomo.
Use the bundled SQD registry and capability notes before selecting a different
solver; source builds, launch models and solver interfaces need their own
reviewed environment. Fulqrum supplies a matrix-vector product, not an
eigensolver. The registry's advanced solver/GPU claims are not reverified by
this installation check.

Package requirements and wheel targets were inspected on November 11, 2026:

- [qiskit-fermions 0.4.1 metadata](https://pypi.org/pypi/qiskit-fermions/0.4.1/json),
  [install guide](https://github.com/Qiskit/qiskit-fermions/blob/0.4.1/docs/install-py.rst),
  and [ffsim protocol guide](https://github.com/Qiskit/qiskit-fermions/blob/0.4.1/docs/guides/ffsim.rst).
- [SQD 0.14.1 metadata](https://pypi.org/pypi/qiskit-addon-sqd/0.14.1/json)
  and [PySCF 2.15.0 metadata](https://pypi.org/pypi/pyscf/2.15.0/json).
- [ffsim 0.0.86 metadata](https://pypi.org/pypi/ffsim/0.0.86/json)
  and [upstream wheel-test configuration](https://github.com/qiskit-community/ffsim/blob/v0.0.86/pyproject.toml).

To update, review new package requirements/wheels and the relevant official
skills, change only the optional project's pins plus the matching doctor
profile constants, and run `uv lock --project environments/optional`. Review
that lock diff, repeat all chosen-profile native smokes on supported Python
versions, then run the base test/build/container checks. Commit both optional
files. Never run an unreviewed broad root-lock upgrade to fix an optional
resolver error. Updating bundled official skills is a separate reviewed change.

No deployment changes are needed. The native DAM tracked-source export includes
this project, documentation and smoke script; its installer still syncs only the
base. The base wheel/container intentionally do not contain the optional lock
or third-party optional packages. Use a full source checkout for these recipes.
