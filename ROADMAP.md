# Qiskit Lab roadmap

This roadmap describes the current `main` branch and proposes an order for
future work. Issue discussions can change the order and scope.

## Available today

- **Local execution.** Run the Bell, GHZ, Grover, and Deutsch–Jozsa examples or
  a measured OpenQASM circuit. Native CHSH runs four seeded measurement
  configurations on an ideal statevector simulator. [Local quickstart](README.md#quick-start-local-simulation) ·
  [CHSH workflow](README.md#run-a-local-chsh-experiment)
- **Receipts and reports.** Save circuit sources and versioned results, compare
  distributions for compatible circuits, and regenerate self-contained Carbon
  HTML from saved public receipts offline. [Receipt contract](docs/receipts.md) ·
  [Receipt comparison](README.md#openqasm-and-receipt-comparison)
- **IBM Quantum and DAM.** A configured IBM account can inspect accessible
  backends, explicitly submit a job, and recover or track existing submissions.
  A DAM workspace adds artifact delivery and scheduled tracking. [IBM Quantum setup](README.md#connect-ibm-quantum-platform) ·
  [DAM onboarding](ONBOARDING.md)

## Experimental QAOA

Local Max-Cut supports depth `p=1` on graphs with 2–8 nodes, with deterministic
parameter search and an exact classical optimum for comparison. The result
records the best sampled cut and the statevector expectation separately.
[Local examples](README.md#local-examples) ·
[QAOA implementation](src/qiskit_lab/experiment_engine.py)

## Proposed order

1. **Make the first local run easy to reproduce.** Review the Bell quickstart
   on a clean checkout and verify what a new user should see. Use a public local
   example for the short DAM walkthrough. [First-time experience](https://github.com/BrUn3y/qiskit_lab/issues/27) ·
   [Demo](https://github.com/BrUn3y/qiskit_lab/issues/28)
2. **Strengthen experiment evidence.** Document the reference expectations,
   reproducible procedures, and scientific limits for the existing experiments.
   Review them independently and add focused offline checks for confirmed gaps.
   [Experiment validation](https://github.com/BrUn3y/qiskit_lab/issues/29)
3. **Clarify hardware setup and recovery.** Make the pre-submission and
   recovery paths easier to follow. Use mocks and public synthetic receipts to
   check the guidance. [Hardware guidance](https://github.com/BrUn3y/qiskit_lab/issues/30)

## Ideas under consideration

- Publish a technical introduction and seek focused feedback when the demo and
  reproducibility evidence are ready for review. [Technical introduction](https://github.com/BrUn3y/qiskit_lab/issues/32)
- Evaluate a broader QAOA scope if a proposal includes a reproducible benchmark,
  resource bounds, and an independent baseline for judging results.

## Starter tasks

Each task can be reviewed independently using the locked offline workflow.
[Contributor guide](CONTRIBUTING.md)

### Check README-relative file links offline

- **Deliverable.** Add one pytest check for local Markdown links and image paths
  in the root README. Resolve paths relative to `README.md`. Limit the check to
  file existence, ignoring remote URLs and fragments.
- **Files.** [README](README.md) and [documentation tests](tests/test_documentation.py).
- **Acceptance.** `uv run --locked pytest -q tests/test_documentation.py` passes
  on the current README without network or a new dependency. A temporary missing
  relative target fails with the offending path. External URLs and fragment-only
  links are skipped.

### Check all three DAM shell entry points in CI

- **Deliverable.** Update the DAM workflow's syntax step to run `bash -n` once
  each for `install.sh`, `setup.sh`, and `quantum`. Update the guide's note about
  the current CI invocation.
- **Files.** [DAM workflow](.github/workflows/dam.yml),
  [offline validation guide](CONTRIBUTING.md#offline-validation), and
  [DAM scripts](scripts/dam/).
- **Acceptance.** The syntax step passes on the tracked scripts and fails when
  any one of the three contains a syntax error in a disposable copy. The step
  runs offline and parses the scripts without executing them.
