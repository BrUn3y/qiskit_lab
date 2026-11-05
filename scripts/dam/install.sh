#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
command -v uv >/dev/null || { echo 'Install uv first: https://docs.astral.sh/uv/getting-started/installation/' >&2; exit 1; }
uv sync --locked --project "$project_root" --no-dev
uv run --locked --no-dev --project "$project_root" python "$project_root/scripts/dam/bootstrap.py" "$@"
"$project_root/scripts/dam/quantum" doctor
