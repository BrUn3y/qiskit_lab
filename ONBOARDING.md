# Quantum Lab onboarding

Read `AGENTS.md` and `.agents/skills/quantum-lab/SKILL.md`.
Steps are safe to repeat; never submit a hardware job during onboarding.

1. Install dependencies and run the local Bell smoke test:
   `bash scripts/dam/setup.sh`. Explain that local counts prove the simulator
   works, while IBM Quantum access still needs a live check.
2. Run `scripts/dam/quantum doctor --online`. If it succeeds and returns
   accessible backends, reuse the existing SDK account. Do not inspect it.
3. If credentials are missing, ask the owner to open this agent's **Terminal**
   in DAM, `cd ~/work/quantum-lab` (private CLI installation; for a catalog seed,
   use the checkout directory the platform briefing gives), and run:
   `uv run --locked --project dam python scripts/dam/configure-quantum.py`.
   The owner supplies the instance CRN and API key directly to a hidden prompt.
   Do not run that command with model tools, do not ask for the key in chat,
   and do not open credential files. Wait for the owner to finish.
4. Verify with `scripts/dam/quantum doctor --online` and `backends`.
   Show accessible QPUs and the query time. If blocked by egress, name the
   missing IBM hostname and request a rule through the owner's DAM settings;
   never bypass the gateway. No accessible backends means setup is incomplete.
5. Present example prompts: Bell simulation; available IBM QPUs; QAOA Max-Cut
   on a five-node graph; submit a Bell circuit once to real IBM Quantum hardware.
   Mark onboarding complete only after the live connection check succeeds.
   Use DAM onboarding checklist/completion tools only if this session has them;
   a private CLI installation is a plain agent and has no starter-kit badge.
