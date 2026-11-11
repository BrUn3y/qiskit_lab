# Skill Evaluations and Updates

The four official skills are pinned, complete upstream copies. Their source,
revision, license and Git blob hashes live in
[qiskit-skills.json](../.agents/qiskit-skills.json). Project routing is in
[AGENTS.md](../AGENTS.md); the project-owned `qiskit-lab` skill remains separate.
Do not edit upstream instructions to adjust project policy.

## Two Different Checks

**Deterministic integration** checks the routing/discovery contract, reads actual
resources, follows selected registry pointers, resolves historical `.claude`
paths, and verifies inventory, section availability and hashes. It neither
selects a skill from natural language nor invokes or grades a model. A changed
pointer, missing nested resource, wrong revision or modified blob fails the check.
External links are recorded as `not_attempted_offline`, not verified accessible.

```sh
uv sync --locked --group typing
uv run --locked python scripts/dam/qiskit_skills.py verify
uv run --locked python scripts/dam/skill_evaluations.py --check
uv run --locked pytest -q tests/test_skill_workflow.py tests/test_kit.py
```

The existing development-only PyYAML parses registries. No runtime dependency,
optional scientific package, model provider, IBM account or service is needed.
CI runs these deterministic checks, including the real tracked-file deployment
export and source archive. These are not live deployment tests.

**Agent-behavior evaluation** requires an actual agent run and independent
review of its transcript and work product. Merely finding words in a response,
asserting a hand-authored expected skill, or showing that a file exists does not
prove the agent selected, read, understood or correctly used that skill.
The repository supplies cases and rubrics, not a claimed model benchmark.
No behavior evaluation is run by pytest or either maintenance command.

## Representative Cases

[cases.json](../evals/skills/cases.json) ties the following cases to a specific
upstream revision. Expectations are review criteria, not a keyword classifier.

| Case | Expected Guidance | Review Focus |
| --- | --- | --- |
| `migration-job-status` | Migration | String statuses, removed queue information, local guide |
| `migration-unavailable-guide` | Migration | External primary guide unavailable; no guessed migration |
| `mitigation-sampler-readout` | Mitigation | TREX versus Sampler/M3, calibration and optional dependencies |
| `mitigation-pub-broadcasting` | Mitigation | Referenced PUB shapes; syntax versus accuracy |
| `sqd-spin-and-rdms` | SQD | Addon layer, ignored spin penalty, dropped RDMs |
| `sqd-complex-support` | SQD | Nested reference, chemistry limitations, provenance caveats |
| `fermionic-encoding` | Fermionic | Occupations, parity, routing, independent small checks |
| `fermionic-sqd-handoff` | Fermionic and SQD | Boundary data, multi-root versus recovery-loop output |
| `local-bell-negative-control` | Project only | Avoid unrelated skills from incidental words |

Historical `.claude/skills/<name>/...` pointers resolve to
`.agents/skills/<name>/...` only for the bundled local paths. A path relative to
a skill is resolved within that skill directory. An external primary URL stays
external; a local companion must not silently replace it. The fermionic skill
contains guidance and external documentation routes, not a missing local
registry. The SQD generated table is packaged intact but is not authoritative
over its registry and prose notes.

## Running a Behavior Review

Run this only when an owner authorizes an evaluation harness/model and budget.
No subagent, provider call or autonomous evaluation schedule is created here.

1. Use a fresh disposable checkout for each case/run. Record project commit,
   corpus SHA-256, upstream revision, full model identifier, harness/version,
   generation settings, seed when supported, timestamp and tool/network policy.
   Use synthetic inputs only and block IBM/service/account/credential access.
   Under the cases' explicit offline context, skip onboarding and do not install,
   submit, deploy, merge or publish. These restrictions override general startup
   or upstream execution suggestions.
2. Give the agent the normal project discovery surface and only the emitted
   task, not expected skills, registry checks or rubric. Keep answer keys outside
   its readable checkout, remove `evals/` in that disposable copy and deny access
   to other runs. Save the exact emitted prompt before doing so:

   ```sh
   uv run --locked python scripts/dam/skill_evaluations.py --case sqd-complex-support
   ```

3. Capture the complete prompt, ordered tool calls, actual file-read results
   (paths and content hashes), response, patches and executed checks. A request
   to read a file is not evidence the read succeeded. Preserve tool failures and
   unavailable docs. Do not give the agent extra skill hints mid-run.
4. An independent human reviewer checks selection against the actual task,
   successful access to the entry point and relevant resources, grounded use of
   their contents, scientific/API correctness, safety and honest limits.
   Use each case's rubric semantically; accept justified equivalent approaches.
   Mark each criterion `pass`, `fail` or `not_observed`, citing transcript
   events/lines and explaining the judgment. A missing transcript cannot pass.
5. Store results outside tracked source, for example under ignored `artifacts/`.
   Record reviewer identity/date and all exclusions. Use this minimum record:

   ```json
   {
     "case_id": "sqd-complex-support",
     "status": "not_run",
     "project_commit": null,
     "upstream_revision": null,
     "corpus_sha256": null,
     "model": null,
     "harness_version": null,
     "settings": null,
     "started_at": null,
     "transcript_path": null,
     "transcript_sha256": null,
     "resource_read_evidence": [],
     "reviewer": null,
     "criterion_verdicts": [],
     "limitations": []
   }
   ```

6. Report case-level outcomes, observed failures and exact denominators.
   Repeat cases across fresh runs when measuring reliability; record the repeat
   count, do not silently discard failed runs. A small corpus is not a universal
   model capability score. A model-as-judge, if separately authorized, is advisory
   and must not replace the human resource/correctness review. Agent access logs
   establish reads, not understanding by themselves.

## Review-Only Updates

No upstream update is necessary to test or demonstrate this process.
Synthetic local Git fixtures exercise it offline. The tool does not fetch,
run upstream scripts, modify a checkout, apply a proposal, commit, push, deploy
or merge. The default project and upstream pinned content stay untouched.

For an intentional future update, first obtain the official Qiskit/skills
repository through the approved GitHub connection and independently review its
origin and chosen commit. The tool consumes local Git objects; it cannot
authenticate the origin of an arbitrary local repository. Do not pass a branch,
tag or abbreviated hash. Verify a full 40-character commit ID before proposing.
Use Git with `--no-lazy-fetch` support (checked here with Git 2.47.3): missing
objects in a partial clone must fail, not silently trigger a network fetch.

```sh
# Example paths only; UPSTREAM_SHA is an explicitly reviewed full commit SHA.
python scripts/dam/qiskit_skills.py propose \
  --source /absolute/path/to/Qiskit-skills \
  --revision "$UPSTREAM_SHA" \
  --output /absolute/path/outside-both-checkouts/skill-proposal
```

The output must not already exist or overlap either input checkout. It contains:

- Complete selected skill directories, including nested data, guides, helper
  scripts and per-skill attribution, taken from committed objects rather than
  potentially dirty working files. Unsupported symlinks/submodules fail closed.
- The recorded root license and attribution files, plus new root files or
  complete directories named `LICENSE*`, `NOTICE*`, `COPYING*` or `COPYRIGHT*`.
  Removal of a recorded root
  attribution file stops the proposal for explicit review rather than dropping it.
- Updated revision/source metadata, Git blob SHA-1, SHA-256 and executable mode
  for every copied file. The old manifest schema remains readable. Added,
  changed or removed license/copyright files (including nested ones) cause a
  `REVIEW-REQUIRED` license identifier, not an unreviewed assertion of the
  previous license.
- A generated project attribution notice and deterministic `proposal.json`
  listing added, removed and changed files, licensing/attribution-review state and
  `agent_behavior_evaluation: not_run`. Identical inputs produce identical output
  bytes. The proposal is assembled and verified before its directory appears.

Inspect the file changes as well as the report:

```sh
python scripts/dam/qiskit_skills.py --root /absolute/path/to/skill-proposal verify
git diff --no-index -- .agents/skills /absolute/path/to/skill-proposal/.agents/skills
git diff --no-index -- .agents/qiskit-skills.json /absolute/path/to/skill-proposal/.agents/qiskit-skills.json
```

`git diff --no-index` exits 1 when differences exist; that is not an execution
failure. Do not run upstream helpers merely because they arrived in the proposal.
Review instruction changes, external reference changes, supported SDK versions,
all licenses/NOTICE files and deployment implications. Directory-complete copying
does not prove that new references outside the selected directories are bundled:
review newly introduced cross-skill/shared/external dependencies explicitly.

After explicit reviewer approval, use a separate update branch/worktree. Replace
the selected directories completely, including removals, and transfer the reviewed
license/attribution files, manifest and generated notice together. Never overlay
only SKILL.md or silently update a deployed copy. Preserve project-owned skills
and unrelated owner files. Re-review cases against the candidate revision and
deliberately update `upstream_revision`; integration checks refuse a stale corpus.
Retain any existing upstream whitespace rather than reformatting it.

Run the full checks required by CONTRIBUTING/CI, plus deterministic resource
checks, tracked-export/source-archive inventory tests and separately authorized
behavior reviews. Open a focused PR with old/new revisions, change report,
license review, actual command/results, compatibility, behavior-evaluation status
and limitations. Use a draft when verification is incomplete. No tool here
approves or applies an update; merging and deployment require owner decisions.

## Packaging Boundaries

The native starter kit seeds the tracked checkout and advertises `.agents/skills`.
The private CLI export includes tracked nested resources, maintenance scripts and
cases; tests exercise that exporter locally without deploying. A source archive
includes the same maintenance resources. The runtime wheel and execution-only
Docker image continue to contain the application, not an agent skill-discovery
environment. Do not claim they advertise skills or change that packaging boundary
just to run an evaluation.
