# Qiskit Lab onboarding

For a native kit, the platform seeds this repository into the agent's work
directory at the kit's resolved commit and runs `bash scripts/dam/install.sh`
before this conversation. The installer installs the locked SDKs and home
instruction entry points. It does not run a circuit, open credentials, or submit
IBM jobs. The private CLI fallback imports its checkout and installs the SDKs
through the command wrapper; it has no platform kit onboarding gate.

Use the checkout identified in the platform briefing. Do not assume a repository
basename or `~/work/qiskit-lab`: that path belongs to the separate private CLI
deployment. If the platform's checkout is missing or installation failed, report
the failure and stop; do not clone, fetch, delete files, or create a replacement.
Read `AGENTS.md` and `.agents/skills/qiskit-lab/SKILL.md` in the existing checkout.

1. Run `scripts/dam/quantum onboarding` before the first visible reply, using
   tool calls only. Begin the reply with "Hello!". A `ready` account needs no
   new key; address the owner's request directly. Explain `connection_error`
   and `no_backends` without inspecting account files or requesting keys in chat.
2. If the status is `needs_credentials`, invite the owner to choose **Configure
   IBM Quantum** or **Continue with local simulation** before running demos.
   Show the returned `setup_command`: it contains the actual checkout path.
   The owner must run it themselves in this agent's DAM **Terminal**. Never
   invoke `configure-quantum.py` with model tools.
3. Explain that `QISKIT_IBM_TOKEN` is the API-key environment variable,
   `QISKIT_IBM_RUNTIME_APIKEY` is its supported alias, and `QISKIT_IBM_INSTANCE`
   holds the instance CRN. Hidden Terminal setup saves an SDK account, so these
   variables are optional. Exports in another terminal do not configure the
   agent's other processes. Never collect keys in chat or chat forms, including
   masked fields: DAM records them in the transcript.
4. When the owner confirms Terminal setup is finished, run
   `scripts/dam/quantum doctor --online`. Report the accessible QPUs and the
   returned UTC query time. An offline installation check or simulation does
   not establish live IBM connectivity. If access fails, keep IBM setup pending
   and explain the safe error; never inspect credential files or bypass egress.
5. If the owner explicitly chooses local simulation, honor that choice without
   requiring an IBM account. Run requested simulations only after that choice,
   return each Carbon `report_path`, and identify the local simulator. Real
   hardware always requires a separate explicit request authorizing one job.

When the platform exposes onboarding tools, use `set_onboarding_checklist` only
for actions or decisions the owner must supply: their choice of local simulation
or IBM access, and completing hidden Terminal setup if they choose IBM. Do not
list package installation, connection checks, schedule creation or other agent
work as owner steps. Tick supplied steps with `complete_onboarding_step`.

Call `mark_onboarding_complete` only after a live IBM check succeeds, or after
the owner explicitly chooses local simulation and the installed offline tools
are available. The latter completes local setup without claiming IBM access.
Leave onboarding pending if the owner has not chosen a mode or IBM setup is
still unresolved. Do not invent onboarding tools on a plain CLI-created agent.

For native kits, the platform already creates the report schedule from `kit.yaml`;
the private CLI deployer creates its equivalent. Do not create a duplicate or
enable a schedule the owner disabled or skipped. Native recurring
schedules remain held until onboarding completes. The precheck uses the installed
`~/.local/bin/qiskit-lab-dam` wrapper, checks accepted job IDs only, and wakes the
model only for undelivered reports. It never submits hardware work.

Once setup is complete, suggest Bell simulation, available IBM QPUs when
connected, or five-node QAOA Max-Cut. Explain that hardware execution is optional
and that every completed run receives a downloadable Carbon HTML report.
