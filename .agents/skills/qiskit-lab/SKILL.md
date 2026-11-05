---
name: qiskit-lab
description: Develop quantum circuits, simulate algorithms, inspect IBM Quantum backends, submit explicitly requested QPU jobs, retrieve results, and run QAOA Max-Cut experiments from DAM.
---

Work from the repository root. Run `bash scripts/dam/setup.sh` once.
Use `scripts/dam/quantum --help` for available commands; stdout is JSON.

## Workflow

1. **Develop:** explain or generate Qiskit/OpenQASM for the user's algorithm.
   For custom circuits write OpenQASM 2 or 3 to a workspace file and use `--qasm`.
   Bind parameters and include measurements; the loader adds them if missing.
   Qiskit Python can be developed as a normal script, then exported with
   `qiskit.qasm3.dumps(qc)` to feed the execution tool.
2. **Check:** `scripts/dam/quantum doctor`; use `doctor --online` to verify IBM
   access. `backends` and `backend ibm_NAME` are live hardware queries.
   `backend ibm_NAME --dashboard` reuses the original topology/health PNG renderer.
3. **Simulate:** `scripts/dam/quantum execute --example bell --shots 1024`.
   Examples: `bell`, `ghz --qubits 5`, `grover` (2 qubits, marked state 11),
   `deutsch-jozsa --qubits 3` (balanced oracle; 2 input qubits + ancilla).
   Or `execute --qasm path/to/circuit.qasm --shots 1024`.
4. **Execute on QPU only when requested:**
   `scripts/dam/quantum execute --qasm path/to/circuit.qasm --hardware --shots 1024`.
   Optional `--backend ibm_NAME`; otherwise select an accessible operational
   least-busy QPU with enough qubits. Transpile to its ISA and submit once
   using IBM Runtime SamplerV2. Return the accepted job ID immediately.
5. **Inspect:** `scripts/dam/quantum job JOB_ID` retrieves status and, when done,
   joint bit counts. `--wait 60` waits briefly for an existing job, and
   `--output artifacts/dam/job.json` saves it. A timeout is not a new submission.
6. **Experiment:** `scripts/dam/quantum qaoa --request 'QAOA Max-Cut on a 5-node graph'`.
   This runs the original deterministic p=1 engine (2–8 nodes), optimizes locally,
   compares with the exact classical optimum and produces a PNG, JSON and QASM.
   For a requested hardware comparison, submit the returned `qasm_path` once
   with `--hardware`. Compare normalized counts and cut values after it finishes;
   clearly identify the classical optimum, statevector expectation and noisy
   hardware observations. Do not claim general VQE/QAOA optimizers are implemented.
7. **Compare distributions:** `scripts/dam/quantum compare --left LOCAL_RECEIPT.json
   --right HARDWARE_JOB.json` normalizes different shot counts and reports total
   variation distance. Both files must describe the same measured circuit/register order.

## IBM setup

At the start of a new chat run `scripts/dam/quantum onboarding`. If it returns
`needs_credentials`, your first reply asks the owner to configure their IBM
Quantum API key and CRN, shows the command below, and offers local simulation
until setup is complete. If `ready`, reuse the account without asking again.
For connection errors, explain the failure; never inspect credential files.
In the first setup invitation name `QISKIT_IBM_TOKEN` for the API key,
`QISKIT_IBM_RUNTIME_APIKEY` as its supported alias, and `QISKIT_IBM_INSTANCE`
for the instance CRN. Hidden setup saves an SDK account, so variables are optional.
Variables must reach the tool's process; an export in another terminal alone
does not configure subsequent chat tools.

Never request an API key in chat. Show the user this command to run themselves
in DAM's browser Terminal, from the project root:

```sh
uv run --locked --project dam python scripts/dam/configure-quantum.py
```

It prompts for the instance CRN and a hidden API key, verifies backend access,
and saves an SDK account with restricted file permissions. Then run
`scripts/dam/quantum doctor --online`. If connection fails, report the failure
and keep the connection step pending. Never inspect the saved account file.
DAM custom-header env credentials are placeholders; they cannot provide the
actual API key in the IBM IAM form body, so do not substitute that mechanism.
DAM chat password fields also reach the transcript in plain text; do not use
them to collect keys. If a key is pasted into a conversation, do not echo,
persist or transfer it; guide the owner to replace it through the hidden prompt.

## Reporting

Match the user's language. Cite actual tool output. Include backend, shots,
job ID (hardware only), observed status, UTC timestamp and artifact paths.
Explain queue delays and allow later job inspection. Never fabricate a QPU,
job, measurement result, or successful connection. Do not log raw SDK errors
that may contain request bodies; the CLI reports safe exception class names.
