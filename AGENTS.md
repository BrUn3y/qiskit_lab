# Qiskit Lab on DAM

Use English for all code, comments, documentation and agent responses.
This project is a native Python package built on the Qiskit SDK. Installation of
`qiskit` and `qiskit-ibm-runtime` is mandatory: run `uv sync --locked` before use,
or `bash scripts/dam/setup.sh` for installation plus a Bell smoke test.
The command wrapper also ensures the locked environment is installed.
Read `.agents/skills/qiskit-lab/SKILL.md` before quantum work. For first-time
configuration, follow `ONBOARDING.md`. `CLAUDE.md` points here too.

At the beginning of every new chat, run `scripts/dam/quantum onboarding` before
answering the first user message. Perform startup checks silently; do not narrate
file reads or internal protocols. Begin the visible reply with a greeting and
the action the owner needs to take. If it reports `needs_credentials`, the first
reply must ask the owner to configure the IBM Quantum API key, show the returned
setup command for their own DAM Terminal, and offer local simulation.
Name `QISKIT_IBM_TOKEN`, its supported alias `QISKIT_IBM_RUNTIME_APIKEY`, and the
instance variable `QISKIT_IBM_INSTANCE`. Hidden setup saves an SDK account instead,
so variables are optional. Do not run demos before this first setup invitation.
Never collect the key as chat text or in a masked chat form: these enter the DAM
transcript. Reuse a `ready` account without asking for its key again. Explain
`connection_error` and `no_backends` without inspecting credentials.

Use DAM's model/harness for reasoning and circuit development. Use
`scripts/dam/quantum` or `uv run --locked qiskit-lab` for execution and live queries.
All quantum operations use Qiskit directly. The package is `src/qiskit_lab`;
it includes circuit execution, backend inspection, job retrieval, deterministic
QAOA Max-Cut, and PNG visualizations. Never invent results.

A request for real IBM Quantum hardware authorizes one submission. Use
`--hardware`, preserve and return the job ID, backend, shots and artifact paths.
Simulation is the default. A named backend also requires `--hardware`.
Never retry hardware submission automatically: it may already have reached IBM.
Inspect jobs tagged `qiskit-lab-dam` before a user-requested retry. The execution
limit controls QPU execution time per job, not cost or queue time.

Never read, print, copy, commit or upload credentials, `.env`, `.qiskit`, SDK
account files or keys. Never run the hidden credential prompt with model tools.
The owner runs it directly in their Terminal. Only the application/IBM SDK uses
credentials at runtime. Keep SDK HTTP debug logging disabled. Use
`doctor --online` to verify live access; offline tests do not prove connectivity.

Save outputs under `artifacts/dam/` and return supported DAM file links. Query
existing job IDs after a timeout or new session instead of submitting replacements.
Report live query timestamps and distinguish simulated from hardware results.

Validation: `uv run --locked pytest -q`,
`uv run --locked ruff check src tests scripts/dam`, and `uv build`.
