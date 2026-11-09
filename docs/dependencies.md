# Dependencies and Container Checks

## QASM import is a runtime requirement

Keep `qiskit-qasm3-import` in the required runtime dependencies. Qiskit 2.x
provides QASM3 export, but its public `qiskit.qasm3.loads` and `load` functions
still delegate import to that separate package. The application uses those APIs
for custom circuits, QAOA receipts and canonical circuit comparison, including
circuits originally supplied as QASM2.

This was checked with Qiskit 2.6.1 and 2.6.2 in isolated environments without the
importer: `dumps` succeeded and `loads` raised `MissingOptionalLibraryError`.
Regression tests exercise the real file/string APIs with the installed importer
and a fresh interpreter with the import blocked. No IBM service or QPU is needed.

## Compatible updates

Use targeted updates, rather than resolving every transitive dependency:

```sh
uv lock --upgrade-package qiskit==2.6.2 --upgrade-package numpy==2.4.6 \
  --upgrade-package matplotlib==3.11.2 --upgrade-package ruff==0.17.4
uv sync --locked
uv pip check
uv run --locked pytest -q
uv run --locked ruff check src tests scripts/dam
uv build
```

These are patch updates within the existing declared ranges. IBM Runtime and the
QASM importer are unchanged. Security-related transitive upgrades belong to the
separate security review; do not replace its lockfile with this branch's version
when integrating both PRs. Regenerate the lockfile with the combined changes and
run the checks again.

The Docker image uses uv 0.13.7, a patch update from 0.13.6. Its named `FROM`
stage makes the uv image visible to Dependabot's Docker parser, which examines
`FROM` instructions rather than external-image `COPY --from` instructions.
The project is installed non-editably with `--locked --no-dev --no-editable`.

## Dependabot

`.github/dependabot.yml` requests weekly updates for `uv` (both `pyproject.toml`
and `uv.lock`), `docker`, `github-actions`, and `npm` in `tools/report-assets`
(the private Carbon/Plex asset builder). There is no second `pip` updater
for the same manifest. Compatible Python/action/asset updates are grouped, each
ecosystem has a three-PR limit, and major version updates require manual review.
Python and uv container images also exclude minor version updates, preserving
Python 3.12 and uv 0.13 until deliberately reviewed. This does not enable
auto-merge or change repository-level security settings.

Dependabot only starts using this configuration once it reaches the default
branch. Configuration tests are not proof of a successful hosted updater run.
GitHub's support table currently lists the uv 0.11 updater; successful
regeneration of this lockfile by the hosted updater must still be checked.

Primary references:

- [GitHub ecosystem support](https://docs.github.com/en/code-security/reference/supply-chain-security/supported-ecosystems-and-repositories)
- [Dependabot Docker parser](https://github.com/dependabot/dependabot-core/blob/main/docker/lib/dependabot/docker/file_parser.rb)
- [uv Docker integration](https://docs.astral.sh/uv/guides/integration/docker/)
- [uv 0.13.7 release notes](https://github.com/astral-sh/uv/releases/tag/0.13.7)

## Container verification

The separate `Build smoke` workflow builds but never pushes an image. It
checks the default CLI, offline diagnostics, non-root execution, a writable
workspace, the installed package rather than an editable source path, absence
of pytest/Ruff, and QASM2/QASM3 round trips with separate measurement registers.
Runtime containers have networking disabled and receive no credentials.
An independent job runs `npm ci --ignore-scripts --no-audit --no-fund` and
`npm run build` for the report assets. It does not publish packages or commit
regenerated CSS, fonts or license files.

Locally:

```sh
docker build --tag qiskit-lab:local .
docker run --rm --network none qiskit-lab:local
docker run --rm --network none qiskit-lab:local doctor
```

The Python lock fixes dependency versions and artifact hashes, not the entire
image. `python:3.12-slim` and the uv version tag are not digest-pinned, the
isolated Hatchling build requirements are not in `uv.lock`, and no bit-identical
image or wheel claim is made. Cross-platform builds and registry publication
are outside these checks.
