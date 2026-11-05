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
file reads or internal protocols. Before the first visible reply, use tool calls
only: do not send progress commentary, announce checks, or say that you will run
them silently. The first visible words must be "Hello!", followed by the owner's
next action or a direct response to their request. If it reports `needs_credentials`, the first
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
QAOA Max-Cut, PNG visualizations, and automatic Carbon HTML reports. Never invent results.

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

Every completed simulation, QAOA experiment, and terminal IBM job must produce
`report.html` using the bundled official IBM Carbon Design System styles. The
CLI returns `report_path`; always give the owner a supported DAM workspace file
link to that report. Keep code, reports and responses in English. If `report_error`
is returned, disclose it and preserve the results; do not claim a report exists.
Queued/running jobs do not have final reports. Do not wait indefinitely in chat.
The installer creates a two-minute `Qiskit Lab job reports` schedule. Its precheck
runs `poll-jobs --precheck`: this queries already accepted IDs, writes reports at
DONE/ERROR/CANCELLED, and wakes the model only for unacknowledged notifications.
It never submits QPU work. Run `scripts/dam/quantum poll-jobs` to retrieve pending
notifications. Present each report link before `poll-jobs --ack JOB_ID`; never
acknowledge undelivered reports. After manually delivering a hardware report,
also acknowledge that job ID to avoid a later duplicate notification. Scheduled
reporting is maintenance, not a first-time onboarding conversation.

Save outputs under `artifacts/dam/` and return supported DAM file links. Query
existing job IDs after a timeout or new session instead of submitting replacements.
Report live query timestamps and distinguish simulated from hardware results.

Validation: `uv run --locked pytest -q`,
`uv run --locked ruff check src tests scripts/dam`, and `uv build`.
