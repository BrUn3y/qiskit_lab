# Code Quality Checks

Run from the repository root with the locked environment:

```sh
uv sync --locked --group typing
uv run --locked pytest -q
uv run --locked ruff check src tests scripts/dam
uv run --locked --group typing mypy
uv build
```

The CI workflow runs both lint and type checks. The separate `typing` dependency
group installs mypy without adding it to runtime dependencies.

## Ruff

The Python 3.11 target matches the oldest supported interpreter. In addition to
syntax, import and undefined-name checks, these stable rule families are enabled
across application code, tests and DAM Python scripts:

| Family | Purpose | Adoption |
| --- | --- | --- |
| B | Bug-prone constructs | Explicit strict pairing for dashboard bars and circuit rows (B905). |
| UP | Python modernization | Compatible with Python 3.11; no initial findings on main. |
| SIM | Unnecessary control-flow complexity | No initial findings. |
| C4 | Unnecessary comprehension work | No initial findings. |
| PTH | Consistent pathlib usage | Existing code already uses pathlib; no initial findings. |

No unsafe auto-fixes or broad formatting changes are required. `BLE001` belongs
to **flake8-blind-except**, not B/flake8-bugbear. BLE is not enabled here. Existing
documented broad exception boundaries deliberately redact SDK error bodies or
preserve accepted jobs/results; their `noqa: BLE001` comments remain unchanged.

UP017 is deliberately excluded: `timezone.utc` is still supported, and an
alias-only rewrite adds no safety. This also keeps the independent job-tracking
tests in PR #2 compatible without modifying that PR's fixtures.

## Incremental Mypy

`mypy` checks every module in `src/qiskit_lab`, including bodies of unannotated
functions, against Python 3.11. It reports unused ignores and redundant casts.
The already annotated QAOA engine additionally rejects unannotated function
definitions and `Any` return values. Extend annotations module by module rather
than enabling strict mode across the entire application at once.

The installed Qiskit and IBM Runtime SDKs lack `py.typed` markers. Only their
module namespaces ignore missing type information. Other missing imports remain
errors; no local module or error category is globally ignored.

This is not full static coverage: most CLI/report/polling signatures are still
unannotated, SDK values can be `Any`, and mypy does not validate receipt JSON
schemas at runtime. Existing runtime validation and offline regression tests
remain necessary. Tests and deployment scripts are linted but are not yet mypy
targets. No live IBM connectivity is needed for these checks.
