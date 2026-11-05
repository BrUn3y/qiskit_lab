# Qiskit Lab onboarding

Read `AGENTS.md` and `.agents/skills/qiskit-lab/SKILL.md`.
Steps are safe to repeat; never submit a hardware job during onboarding.

1. Run `scripts/dam/quantum onboarding` before the first chat reply. If it reports
   `needs_credentials`, open with: "To connect Qiskit Lab to IBM Quantum,
   configure your API key and, if available, your instance CRN."
   Explain the hidden entry step below and offer "Configure IBM Quantum" or
   "Continue with local simulation". Do not run or narrate algorithm demos before this
   invitation. Name the API-key environment variable `QISKIT_IBM_TOKEN` (alias
   `QISKIT_IBM_RUNTIME_APIKEY`) and the instance variable `QISKIT_IBM_INSTANCE`.
   Explain that the hidden setup saves an SDK account without requiring these
   variables. An export in a separate terminal does not configure the agent's
   other processes: environment variables must reach the actual tool process.
   Do not put an API-key text/password field in a DAM chat form:
   DAM includes even masked fields in the transcript. Never echo a pasted key.
2. If credentials are missing, ask the owner to open this agent's **Terminal**
   in DAM, `cd ~/work/qiskit-lab` (private CLI installation; for a catalog seed,
   use the checkout directory the platform briefing gives), and run:
   `uv run --locked python scripts/dam/configure-quantum.py`.
   The owner supplies the instance CRN and API key directly to a hidden prompt.
   Do not run that command with model tools, do not ask for the key in chat,
   and do not open credential files. Wait for the owner to finish.
3. If `onboarding` reports `ready`, reuse the verified account and skip the
   credential request. For `connection_error` or `no_backends`, explain the
   actual failure; do not treat it as a missing key or inspect the account file.
   Once the owner finishes configuration, verify with
   `scripts/dam/quantum doctor --online` and `backends`.
   Show accessible QPUs and the query time. If blocked by egress, name the
   missing IBM hostname and request a rule through the owner's DAM settings;
   never bypass the gateway. No accessible backends means setup is incomplete.
4. After the owner configures the account or chooses local simulation, run
   `bash scripts/dam/setup.sh` if needed. Explain that local Bell counts prove
   the simulator works, while IBM access needs its separate live check.
5. Present example prompts: Bell simulation; available IBM QPUs; QAOA Max-Cut
   on a five-node graph; submit a Bell circuit once to real IBM Quantum hardware.
   Mark onboarding complete only after the live connection check succeeds.
   Use DAM onboarding checklist/completion tools only if this session has them;
   a private CLI installation is a plain agent and has no starter-kit badge.
