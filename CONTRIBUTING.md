# Contributing

## Scope and setup

Qiskit Lab is a Python package, CLI, and DAM starter kit, not a hosted web app.
Read [AGENTS.md](AGENTS.md) and the
[Qiskit Lab skill](.agents/skills/qiskit-lab/SKILL.md) before changing execution
or hardware behavior. [ONBOARDING.md](ONBOARDING.md) describes owner setup inside
DAM; it is not required for offline tests.

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
Node.js is only required for rebuilding the bundled Carbon/font assets or for
the separate DAM CLI deployment fallback, not for Python development.

## Offline validation

Run these before editing to establish a baseline, then again after changes:

```sh
uv run --locked pytest -q
uv run --locked ruff check src tests scripts/dam
uv run --locked --group typing mypy
uv run --locked qiskit-lab doctor
uv build
bash -n scripts/dam/install.sh scripts/dam/setup.sh scripts/dam/quantum
```

These checks match the core steps in [CI](.github/workflows/dam.yml). Tests use
mocks for IBM services and must not require real credentials. `doctor` without
`--online` only inspects the installed SDK. Build output goes to ignored `dist/`;
`uv build` does not publish a package. Dependency installation and the first
build may need network access even though the tests and simulation are offline.
Type checking uses the development-only `typing` group, not runtime dependencies.

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

The final command intentionally exits **1** with an empty queue (skip), not 0.
This procedure does not register a platform schedule. `install.sh` installs
dependencies and entry points but
does not run demos; `setup.sh` additionally runs a local Bell smoke test.

The [README](README.md#quick-start-local-simulation) contains runnable local
examples. The [Bell QASM fixture](docs/examples/bell.qasm) and its receipt
comparison are covered by `tests/test_documentation.py`. Generated artifacts
belong under ignored `artifacts/`, not in commits. The terminal CLI prints JSON;
an agent publishes HTML artifacts separately through DAM tools.

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
