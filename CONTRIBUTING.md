# Contributing

## Scope and setup

Qiskit Lab is a Python package, CLI, and DAM starter kit.
Read [AGENTS.md](AGENTS.md) and the
[Qiskit Lab skill](.agents/skills/qiskit-lab/SKILL.md) before changing execution
or hardware behavior. Offline development works from a local checkout. For owner
setup inside DAM, see [ONBOARDING.md](ONBOARDING.md). For proposed priorities and
small tasks, see the [roadmap](ROADMAP.md).

Use Git, Python 3.11-3.13, and [uv](https://docs.astral.sh/uv/). CI runs on Ubuntu
with Python 3.11, 3.12, and 3.13; other operating systems are not covered.
Create a branch from the current default branch and keep changes focused:

```sh
git clone https://github.com/BrUn3y/qiskit_lab.git
cd qiskit_lab
git switch -c docs/my-change
uv sync --locked
```

`uv.lock` pins runtime and development dependencies. Do not regenerate it for a
documentation-only change. Plain `pip install .` does not use that lockfile.
Node.js is used to rebuild bundled Carbon/font assets, run the report browser
smoke, or use the separate DAM CLI deployment fallback. The core Python checks
need only the locked Python environment.

## Offline validation

Run these from the repository root before editing and again after changes.
The test suite, lint, type check, offline diagnostics, and build also run in the
Ubuntu Python matrix. [DAM starter kit CI](.github/workflows/dam.yml)

```sh
uv run --locked python scripts/dam/qiskit_skills.py verify
uv run --locked python scripts/dam/skill_evaluations.py --check
uv run --locked pytest -q --cov --cov-report=term-missing --cov-report=xml:coverage.xml
uv run --locked coverage report --include='*/job_tracking.py' --fail-under=100
uv run --locked ruff check src tests scripts/dam
uv run --locked --group typing mypy
uv run --locked qiskit-lab doctor
uv build
bash -n scripts/dam/install.sh
bash -n scripts/dam/setup.sh
bash -n scripts/dam/quantum
```

Use `uv run --locked pytest -q` for quick iteration. The coverage command above
checks both lines and branches in `job_tracking.py`. The skill checks verify
bundled resources and deterministic integration. The shell syntax commands use
one path per invocation because Bash treats additional paths as script arguments.
The current CI invocation parses `install.sh` only.

On macOS, the default pytest temporary path can contain `/private/var/`, which
trips the submission tests' check for redacted text. If that happens, add
`--basetemp "$PWD/artifacts/pytest-tmp"` to the pytest command. Use a disposable
directory since pytest clears it on each run.

Tests use mocks for IBM services. Plain `doctor` inspects installed SDKs offline.
Mypy comes from the development-only `typing` group. `uv build` writes packages
to ignored `dist/`. Dependency installation and the first build may need network
access. Tests, diagnostics, and local simulations run without IBM credentials.

CI also installs the native kit into an isolated instruction home and checks
that an empty report queue skips the model. To reproduce without modifying your
real home instructions, use an unused output directory from the repository root.
Use a fresh checkout with no hardware receipts under `artifacts/dam/`; polling
an existing hardware receipt can contact IBM.

```sh
mkdir -p artifacts
KIT_HOME=$(mktemp -d "$PWD/artifacts/kit-home.XXXXXX")
bash scripts/dam/install.sh --home "$KIT_HOME"
bash "$KIT_HOME/.local/bin/qiskit-lab-dam" poll-jobs --precheck
```

The final command prints an empty `notifications` list and exits **1** to tell
DAM to skip the scheduled model. `install.sh` installs dependencies and entry
points in the isolated setup. This smoke check uses only the local wrapper.
`setup.sh` additionally runs a local Bell smoke test.

For optional native environments, run the profile-specific checks when changing
that integration. For runtime-image changes, see the container smoke commands.
Live IBM diagnostics, backend queries, and hardware jobs require configured IBM
access. Testing artifact publication inside DAM requires a DAM workspace.
These access-dependent checks are outside the offline contribution workflow.
[Optional capabilities](docs/optional-capabilities.md) ·
[Build smoke CI](.github/workflows/container.yml) ·
[IBM Quantum setup](README.md#connect-ibm-quantum-platform)

## Local report browser smoke

Run this optional local smoke when changing report markup, assets, or
interactions. The separate `report-browser` CI job uses the official Playwright
Ubuntu 24.04 container, pinned to the same version as the npm lockfile. It runs
one Chromium headless-shell worker at desktop and mobile sizes, with no retries.
It uses synthetic local HTML fixtures, blocks
external requests, and fails on page errors. It checks charts, independent
filters and modes, pagination, exact downloaded JSON/source bytes, embedded
images, terminal failures, and the JavaScript-disabled fallback. It does not
contact IBM, run QPU work, or verify agent behavior.
Controls and downloads use independent browser contexts and separate scenarios,
each retaining the same 30-second limit.
The native CHSH fixture also checks the versioned JSON download, confidence
bounds, independent seed metadata and per-configuration source downloads.

To reproduce with Node.js 20+ and the locked Python environment:

```sh
uv sync --locked
uv run --locked python tools/report-assets/create-fixtures.py
cd tools/report-assets
npm ci --ignore-scripts --no-audit --no-fund
# On supported Linux hosts that need system dependencies, run this first:
# npx --no-install playwright install-deps chromium
npx --no-install playwright install --only-shell chromium
npm run test:browser
```

Installation needs network access. Fixture generation and browser tests run
offline.
The CI image includes browser binaries and system dependencies, avoiding a
per-run apt installation within the unchanged ten-minute job budget.
Reports open directly from disk; no server or external assets are needed.
Generated fixtures, screenshots and failure traces stay under ignored
`artifacts/report-smoke/`. The browser dependency is development-only, pinned
in the existing asset-tool lockfile, and absent from the Python runtime image.
The browser job is separate from the Python 3.11-3.13 matrix and does not replace
its full job-tracking line/branch coverage gate. This is a targeted Chromium
smoke, not cross-browser coverage, visual snapshot approval or proof of IBM access.

## Add an experiment

1. **Define the scientific check.** Document the input and its supported bounds,
   state preparation or oracle, measurement basis and bit ordering, and an
   analytic result or a small independently computed classical reference. State
   which values are ideal predictions and which come from finite-shot samples.
   Give the tolerance or statistical assumptions that justify your acceptance
   check, and describe what the measurements can establish. For example,
   Bell-state counts in the computational basis check correlations in that basis
   and leave phase coherence untested.
2. **Implement the smallest usable interface.** Start with a public QASM fixture
   and `execute --qasm` when a single circuit is enough. For experiment-specific
   logic, put circuit construction and analysis in `src/qiskit_lab/`. If it
   needs a CLI command, validate arguments in `cli.py`, reuse the existing entry
   point and artifact conventions, and keep local execution the default. For
   multiple local measurement configurations, call `sample_configurations()`
   once with the complete set and retain its seed provenance. See the [CHSH
   circuit builder](src/qiskit_lab/chsh.py), [CLI](src/qiskit_lab/cli.py), and
   [sampling helper](src/qiskit_lab/sampling.py).
3. **Test the science and the entry point offline.** Compare a small case with
   the reference from step 1. Use fixed seeds or synthetic counts, check count
   support and observed shot totals, and use justified tolerances for sampled
   estimates. Assert scientific fields and invariants across runs in the locked
   environment. Run IDs, timestamps, and output paths can vary. Cover invalid
   inputs, and exercise the normal CLI path with temporary output and IBM calls
   mocked. See [CHSH tests](tests/test_chsh.py) and [documentation
   tests](tests/test_documentation.py).
4. **Save and validate the receipt.** Use the versioned envelope and the receipt
   type that matches the result. If a new type is needed, update the shared
   validator, compatibility tests, and contract together. For an execution
   result, record status, backend, explicit `hardware`, the appropriate run or
   job ID, and available counts. Capture inputs, requested shots, seeds, SDK
   versions, and circuit identity or measurement layout where applicable. Derive
   observed totals from counts and leave unavailable values absent. Validate with
   `validate_receipt`, preserve historical receipt support, and persist the
   scientific result before presentation. See the [receipt contract](docs/receipts.md)
   and [validator](src/qiskit_lab/receipts.py).
5. **Use the existing Carbon HTML report.** Follow the CLI's `finish_report`
   path for validation and persistence before rendering. Check that the returned
   `report_path` opens locally and displays the scientific values, provenance,
   and downloads that apply. Exercise offline regeneration with `report --input`
   and confirm the input survives. On a rendering failure, retain the receipt
   and surface `report_error`. The CLI returns artifact paths for a DAM agent
   to publish. See the [report generator](src/qiskit_lab/reports.py) and
   [report tests](tests/test_reports.py).
6. **Document a runnable example.** Add the command and a short explanation of
   the expected invariants, assumptions, output paths, and limitations to the
   README or linked documentation. Keep public fixtures under `docs/examples/`
   and generated artifacts under ignored `artifacts/`. Run every command you
   document from the repository root. See the [local quickstart](README.md#quick-start-local-simulation)
   and the [Bell QASM fixture](docs/examples/bell.qasm).

### Worked example with CHSH

Use the existing local CHSH experiment as a reference for multi-configuration
sampling, provenance, and reports. After setup, run from the repository root:

```sh
mkdir -p artifacts/contributor
uv run --locked qiskit-lab chsh --shots 1024 --seed 42 \
  --output-dir artifacts/contributor > artifacts/contributor/chsh.json
uv run --locked qiskit-lab report --input artifacts/contributor/chsh.json \
  --output-dir artifacts/contributor/reports
```

Check the JSON for `receipt_type: "chsh"`, `status: "DONE"`, `hardware: false`,
four distinct configuration seeds, and 4,096 observed shots across the four
settings. The default ideal reference is `2 sqrt(2)`. The sampled `chsh_value`
and its shot-noise interval depend on the observed counts. The experiment uses
ideal statevector sampling and the interval covers sampling uncertainty under
the stated independence and fixed-setting assumptions. Open the `report_path`
from the last command to inspect the four measurements and source downloads.
The copy records `report_source: imported_receipt_not_verified_online`.
See the [CHSH conventions and limits](README.md#run-a-local-chsh-experiment).

## Report a bug or propose a validation improvement

- For a bug, give the revision or release, OS, Python and SDK versions, exact
  commands, and the smallest public QASM, synthetic receipt, or fixture that
  reproduces it. Include expected and observed behavior, the exit code, and
  relevant safe CLI fields such as `error_category`, `next_step`, or
  `report_next_step`. The offline `qiskit-lab doctor` output can supply SDK
  versions. List which checks ran and where the reproduction stops.
- For a validation proposal, name one experiment and the claim under test.
  Describe the existing check, the evidence gap, the independent reference or
  invariant, and how a reviewer would reproduce the proposed check with a local
  circuit or synthetic counts. Include the expected tolerance and assumptions
  about shots and seeds where relevant. Scope the proposal to what the check
  would establish.
- Use public synthetic inputs and safe diagnostic excerpts in GitHub issues
  and PRs. Keep tokens, account files, `.env`, instance CRNs, private job IDs or
  receipts, private circuits or paths, and raw SDK request logs out of text and
  attachments. If an issue is hardware-specific, describe the failing stage and
  safe diagnostic fields, then use a mock or synthetic receipt where possible.
  Flag any access-dependent behavior you could only observe on hardware.

Start with the [bug report](https://github.com/BrUn3y/qiskit_lab/issues/new?template=bug_report.md)
or [validation proposal](https://github.com/BrUn3y/qiskit_lab/issues/new?template=validation_proposal.md)
template.

## Safety and review

- Keep code, comments, and documentation in English. Add focused tests for
  behavior changes and run every local example you change.
- Never put API keys, account files, `.env`, real job receipts, or private data
  in tests, logs, screenshots, or commits. Mock credentials only.
- Do not run onboarding, credential configuration, `doctor --online`, backend
  queries, or QPU submissions as part of offline validation. Do not deploy,
  publish, or create schedules while testing a documentation change.
- Hardware submission requires explicit owner authorization for one job.
  Preserve accepted job IDs; never automatically resubmit after a timeout.
- Preserve existing reports, owner files, credentials, and schedule settings.
  Avoid major dependency upgrades or unrelated generated-asset changes.
- Do not choose or change the project's license without the owner's approval.
  There is currently no project-level license; bundled third-party notices do
  not grant a license for the rest of the repository.

In your PR, describe the user-visible change, exact commands and results before
and after, and untested paths. Separate pre-existing or infrastructure failures
from regressions. Use a draft PR while required checks remain failing or
unverified. Do not claim that offline tests verify IBM access, DAM deployment,
container execution, or browser rendering.

For changes to runtime behavior, record compatibility and migration notes in
the PR and the relevant user documentation. Do not invent historical changelog
entries or increment the package version for documentation-only changes; the
maintainer controls releases.

For bundled-skill changes, follow [Skill Evaluations and Updates](docs/skills.md).
Keep upstream resources unmodified at their pinned revision. Generate updates
as external review proposals, then use a dedicated PR with complete resources,
licenses, provenance and hashes. An ordinary test pass is not an agent-behavior
evaluation; record actual prompts, tool reads, responses and reviewer judgments
separately, or explicitly report behavior evaluation as not run.
