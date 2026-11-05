# DAM manifest schemas

`kit.schema.json` and `catalog.schema.json` are unmodified generated schemas
from [dam-agents/dam-starter-kits](https://github.com/dam-agents/dam-starter-kits)
at commit `1af3d3ff6b944c643b5edc35e0d357cc9d159af5`.
The upstream platform contract generates them; do not edit them by hand.

The repository's `kit.yaml` is the definition kit. It uses `seed.self: true`
without a separate ref so DAM installs the code from the commit it resolved.
The root `catalog.yaml` supplies the repository entry for a standalone catalog
or a later curated-catalog contribution. Neither file publishes the kit or
changes the repository's visibility.

Run `uv run --locked pytest -q tests/test_kit.py` to validate both manifests
against these schemas and check bootstrap, scheduling and source paths.
The full CI also installs the kit with an isolated instruction home and verifies
that an empty report queue exits with the schedule's skip code without a model.

To refresh the snapshots, select and review an upstream commit, download both
schema files from that exact commit, update the provenance above, then run the
full test, Ruff and build checks. Keep the copies identical to upstream.
