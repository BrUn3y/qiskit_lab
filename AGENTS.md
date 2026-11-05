# Qiskit Lab on DAM

This checkout is the private DAM edition of BrUn3y/quantum_lab_agent.
Read `.agents/skills/qiskit-lab/SKILL.md` before doing quantum work.
For initial setup follow `ONBOARDING.md`. `CLAUDE.md` points here too.

Use DAM's current model/harness for reasoning and circuit development. Use
`scripts/dam/quantum` for execution and live IBM queries. No local Ollama,
BeeAI, Agent Stack service or five A2A servers are needed for this native path.
The original five agents remain in `src/beeai_agents` for the legacy deployment.
Reuse the original `experiment_engine.py` for QAOA; do not invent results.

The user authorizes hardware by requesting real hardware/IBM Quantum execution.
Then submit once with `--hardware`, preserve and return the job ID, backend,
shots and artifact paths. The default is local simulation. A named IBM backend
also requires `--hardware`; never silently spend QPU time. Never retry a failed
submission automatically: it might already have reached IBM. Query the IBM
Quantum dashboard for jobs tagged `qiskit-lab-dam` before a user-requested retry.
The execution-time option limits QPU execution per job, not cost or queue time.

Never read, print, copy, commit or upload `.env`, `.qiskit`, SDK account files,
keys or credentials. Do not run the hidden credential setup through a model
tool or ask for credentials in chat. The owner must run it in their own Terminal.
Only the Python application/SDK consumes credentials at runtime. Do not enable
SDK HTTP debug logging. Use `doctor --online` to verify access, without exposing
credentials. Do not report a working IBM connection based only on an offline test.

Save outputs below `artifacts/dam/`. Return local artifact links supported by
DAM, not Agent Stack canvas markers. Jobs may outlive an agent's session:
inspect the existing ID with `quantum job`, without creating a replacement.
Report backend-query timestamps and separate simulated from hardware results.

Validation: `uv run --locked --project dam pytest dam/tests -q` and
`uv run --locked --project dam ruff check dam scripts/dam`.
