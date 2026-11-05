#!/usr/bin/env python3
"""Deploy a committed private checkout using only the public DAM CLI.

No GitHub connection is required: only reviewed, tracked working-tree files are
copied. Local account files, .env files, .git and run artifacts are never sent.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOSTS = ("pypi.org", "files.pythonhosted.org", "github.com", "release-assets.githubusercontent.com",
         "iam.cloud.ibm.com", "resource-controller.cloud.ibm.com", "quantum.cloud.ibm.com",
         "api.global-search-tagging.cloud.ibm.com", "globalcatalog.cloud.ibm.com",
         "us-east.quantum.cloud.ibm.com", "eu-de.quantum.cloud.ibm.com")
BOOTSTRAP = """Work in ~/work/qiskit-lab. Read AGENTS.md and ONBOARDING.md.
Use tool calls only until your first visible reply. Do not announce startup checks
or say that you will run them silently. Your first visible words must be "Hello!".
Run scripts/dam/quantum onboarding. If the account is missing, your first reply
must ask the owner to configure the IBM Quantum API key, show the hidden-prompt
setup command for their own DAM Terminal, and offer local simulation.
Do not run demos before that invitation. Do not collect the key as chat text or
in a chat form, read credentials, or run the hidden prompt yourself.
Name QISKIT_IBM_TOKEN as the API-key variable, QISKIT_IBM_RUNTIME_APIKEY as its
supported alias and QISKIT_IBM_INSTANCE for the CRN. Hidden setup saves an SDK
account and does not require those variables. Reuse an account already verified.
Do not submit QPU jobs. All replies and documentation must be in English.
"""
HOME_START = "<!-- qiskit-lab:instructions:start -->"
HOME_END = "<!-- qiskit-lab:instructions:end -->"
REPORT_SCHEDULE_NAME = "Qiskit Lab job reports"
REPORT_PRECHECK = "cd ~/work/qiskit-lab && bash scripts/dam/quantum poll-jobs --precheck"
REPORT_TASK = """Work in ~/work/qiskit-lab. This is scheduled completion reporting, not onboarding.
Read AGENTS.md and the project skill. Run bash scripts/dam/quantum poll-jobs.
For each pending notification, automatically publish the existing Carbon HTML
report as a rendered DAM artifact using create_artifact, or
create_artifact_upload_url and its returned upload instructions for large files.
Use report_filename and content type text/html. Present the artifact link and a
supported workspace file link with the job ID, backend and final state.
Never wait for the owner to request a visualization. If publishing fails, disclose
it, preserve the file and leave that notification unacknowledged.
After presenting each link, acknowledge only that ID with
bash scripts/dam/quantum poll-jobs --ack JOB_ID. Never acknowledge an undelivered
report. If there are only errors, explain the safe error class and keep tracking.
Never submit, retry, cancel or modify an IBM job. Never read credentials.
Use English. Do not run unrelated demos or scans of user files.
"""
HOME_INSTRUCTIONS = f"""{HOME_START}
You are Qiskit Lab. Your project is ~/work/qiskit-lab.
At the beginning of EVERY new chat, before replying to its first user message,
read ~/work/qiskit-lab/AGENTS.md and ~/work/qiskit-lab/ONBOARDING.md, then run
~/work/qiskit-lab/scripts/dam/quantum onboarding.
Before your first visible reply, use tool calls only. Do not send progress
commentary, narrate file reads, announce startup checks, or say that you will
run them silently. Your first visible words must be "Hello!", followed by the
owner's next action or a direct response to their actual request.
If status is needs_credentials, your FIRST reply asks the owner to configure
their IBM Quantum API key and optional instance CRN, shows the returned command
for their own DAM Terminal with hidden input, and offers local simulation.
Name QISKIT_IBM_TOKEN as the API-key variable, QISKIT_IBM_RUNTIME_APIKEY as its
supported alias and QISKIT_IBM_INSTANCE for the CRN. Hidden setup saves the SDK
account instead, so setting environment variables is optional.
Do not collect the key in chat or a masked chat form; both enter the transcript.
Do not run algorithm demos before that invitation. If ready, reuse the verified
account without asking again. Explain a connection_error without reading secrets.
Never submit a hardware job during onboarding. Always respond in English.
Every completed simulation, experiment and hardware job must have a Carbon HTML
report named with its job/run ID and circuit description. Automatically display
report_path as a rendered DAM artifact in the same response using create_artifact,
or create_artifact_upload_url and its returned upload instructions for large files.
Use report_filename and content type text/html, and present the artifact link and
a supported workspace file link. Never wait for a visualization request. If
publication fails or its tools are unavailable, disclose that, preserve the report
and keep any scheduled notification unacknowledged. Pending hardware jobs
are checked by the Qiskit Lab job reports schedule; never resubmit them.
Scheduled completion reporting skips first-chat onboarding and follows its task.
{HOME_END}"""
HOME_CLAUDE_INSTRUCTIONS = f"""{HOME_START}
@AGENTS.md
{HOME_END}"""


def run(arguments, *, as_json=False):
    completed = subprocess.run(arguments, cwd=ROOT, text=True, capture_output=True, check=False)
    if completed.returncode:
        raise RuntimeError(f"{arguments[0]} {arguments[1]} failed: {completed.stderr.strip()}")
    return json.loads(completed.stdout) if as_json else completed.stdout.strip()


def copy_tracked(destination):
    # Copy reviewed current files, including staged additions, without .git.
    files = run(["git", "ls-files", "-z"]).split("\0")
    for relative in filter(None, files):
        path = Path(relative)
        if any(part in {".git", ".qiskit", ".venv", "artifacts", "secrets", "credentials"} for part in path.parts):
            raise RuntimeError(f"Refusing tracked sensitive/runtime directory: {relative}")
        if (path.name.startswith(".env") and path.name != ".env.example") or path.suffix in {".pem", ".key", ".p12"}:
            raise RuntimeError(f"Refusing tracked credential file: {relative}")
        source = ROOT / path
        if source.is_symlink():
            continue
        if source.is_file():
            target = destination / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    if not (destination / "uv.lock").exists():
        raise RuntimeError("Missing tracked Qiskit lockfile. Commit or stage the kit before deployment.")


def configure_model(agent_id, requested_model=None):
    if requested_model:
        run(["dam", "agent", "update", agent_id, "--model", requested_model, "--json"], as_json=True)
        return requested_model
    agent = run(["dam", "agent", "get", agent_id, "--json"], as_json=True)
    current = (agent.get("models", {}).get("defaults", {}).get("chat") or {}).get("model")
    if current:
        return current
    catalog = run(["dam", "agent", "models", agent_id, "--json"], as_json=True)
    models = [model["name"] for provider in catalog.get("providers", []) for model in provider.get("models", [])]
    if len(models) != 1:
        raise RuntimeError("DAM has no default model. List dam agent models and rerun --existing --model ALIAS/MODEL; "
                           "if the provider is unavailable, select a working --provider when creating a new agent.")
    run(["dam", "agent", "update", agent_id, "--model", models[0], "--json"], as_json=True)
    print(f"Default model: {models[0]}", flush=True)
    return models[0]


def import_when_ready(agent_id, package):
    # Egress changes roll DAM's gateway. Re-importing identical code is safe;
    # this retry is unrelated to, and never used for, IBM hardware submissions.
    for attempt in range(3):
        try:
            return run(["dam", "import", agent_id, str(package), "--yes", "--json"], as_json=True)
        except RuntimeError as error:
            if "instance unreachable" not in str(error) or attempt == 2:
                raise
            print("DAM gateway is restarting; retrying the code import in 5 seconds.", flush=True)
            time.sleep(5)


def update_existing(agent_id, package):
    """Overwrite only packaged source files; never replace a workspace directory."""
    files = sorted(path for path in package.rglob("*") if path.is_file())
    for index, path in enumerate(files, 1):
        relative = path.relative_to(package).as_posix()
        print(f"Update source [{index}/{len(files)}]: {relative}", flush=True)
        run(["dam", "file", "put", agent_id, str(path), f"work/qiskit-lab/{relative}", "--overwrite"])
    return {"mode": "source-files-only", "files_updated": len(files), "preserves_existing_files": True}


def select_agent(agents, name, agent_id, existing):
    if agent_id and not existing:
        raise RuntimeError("--agent requires --existing; it never creates a replacement agent.")
    matches = [agent for agent in agents if agent.get("id") == agent_id] if agent_id else [
        agent for agent in agents if agent["name"] == name]
    if len(matches) > 1:
        raise RuntimeError("Agent name is ambiguous. Use --existing --agent AGENT_ID to target it explicitly.")
    if matches and not existing:
        raise RuntimeError("Agent already exists. Use --existing only to deliberately update its qiskit-lab folder.")
    if not matches and existing:
        raise RuntimeError("--existing requires an agent that already exists; check --agent or --name.")
    return matches[0] if matches else None


def merge_home_instructions(existing, instructions=HOME_INSTRUCTIONS):
    if (HOME_START in existing) != (HOME_END in existing):
        raise RuntimeError("Incomplete Qiskit Lab instructions block; preserving the home instructions unchanged.")
    existing = re.sub(re.escape(HOME_START) + r".*?" + re.escape(HOME_END), "", existing, flags=re.DOTALL)
    return existing.rstrip() + "\n\n" + instructions + "\n"


def install_home_instructions(agent_id, temporary):
    # Preserve DAM and owner instructions outside our managed section. Do not
    # replace the workspace just to update the first-chat behavior.
    for name, instructions in [("AGENTS.md", HOME_INSTRUCTIONS), ("CLAUDE.md", HOME_CLAUDE_INSTRUCTIONS)]:
        try:
            existing = run(["dam", "file", "get", agent_id, name, "--stdout"])
        except RuntimeError as error:
            if f"not found: {name}" not in str(error):
                raise
            existing = ""
        path = Path(temporary) / f"home-{name}"
        path.write_text(merge_home_instructions(existing, instructions))
        run(["dam", "file", "put", agent_id, str(path), name, "--overwrite"])


def configure_report_schedule(agent_id):
    schedules = run(["dam", "schedule", "list", agent_id, "--json"], as_json=True)
    matches = [schedule for schedule in schedules if schedule.get("name") == REPORT_SCHEDULE_NAME]
    if len(matches) > 1:
        raise RuntimeError("Multiple completion-report schedules found; keep one active schedule in DAM.")
    if matches:
        schedule = matches[0]
        if (schedule.get("task") == REPORT_TASK and schedule.get("precheck") == REPORT_PRECHECK
                and schedule.get("sessionMode") == "fresh"):
            return schedule
        # Refresh managed reporting instructions without changing the owner's
        # enabled state, recurrence, timezone, model or quiet hours.
        return run(["dam", "schedule", "update", schedule["id"], "--task", REPORT_TASK,
                    "--precheck", REPORT_PRECHECK, "--session-mode", "fresh", "--json"], as_json=True)
    return run(["dam", "schedule", "create", agent_id, "--name", REPORT_SCHEDULE_NAME,
                "--every", "2m", "--session-mode", "fresh", "--precheck", REPORT_PRECHECK,
                "--task", REPORT_TASK, "--json"], as_json=True)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--name", default="Qiskit Lab")
    cli.add_argument("--template", default="default")
    cli.add_argument("--provider", help="Existing DAM model provider; defaults to your preferred provider")
    cli.add_argument("--model", help="Optional model from dam agent models")
    cli.add_argument("--instance", help="Non-secret IBM Quantum instance CRN")
    cli.add_argument("--existing", action="store_true", help="Update source files while preserving existing workspace data")
    cli.add_argument("--agent", help="Exact existing DAM agent ID; requires --existing")
    cli.add_argument("--dry-run", action="store_true", help="Validate source and show the target without changing DAM")
    cli.add_argument("--no-run", action="store_true", help="Import and configure only; do not start onboarding")
    args = cli.parse_args()
    agents = run(["dam", "agent", "list", "--json"], as_json=True)
    agent = select_agent(agents, args.name, args.agent, args.existing)
    # Validate the package before creating any platform resources.
    with tempfile.TemporaryDirectory(prefix="qiskit-lab-dam-") as temporary:
        package = Path(temporary) / "qiskit-lab"
        package.mkdir()
        copy_tracked(package)
        name = agent["name"] if agent else args.name
        if args.dry_run:
            print(json.dumps({"dry_run": True, "agent_id": agent["id"] if agent else None, "name": name,
                              "mode": "source-files-only" if agent else "new-agent",
                              "files": sorted(path.relative_to(package).as_posix()
                                              for path in package.rglob("*") if path.is_file())}, indent=2))
            return 0
        if agent:
            agent_id = agent["id"]
        else:
            command = ["dam", "agent", "create", args.name, "--template", args.template,
                       "--description", "Qiskit Lab: Qiskit and IBM Quantum Platform", "--json"]
            if args.provider:
                command += ["--provider", args.provider]
            if args.instance:
                command += ["--env", "QISKIT_IBM_INSTANCE=" + args.instance]
            created = run(command, as_json=True)
            agent_id = created["id"]
        deployment = {"agent_id": agent_id, "name": name, "source_commit": run(["git", "rev-parse", "HEAD"])}
        state_path = ROOT / ".dam-deploy/deployment.json"
        state_path.parent.mkdir(exist_ok=True)
        state_path.write_text(json.dumps(deployment, indent=2) + "\n")
        print(f"Agent: {name} ({agent_id})", flush=True)
        if not agent:
            run(["dam", "network", "apply-preset", agent_id, "--preset", "trusted", "--json"], as_json=True)
        rules = run(["dam", "network", "list", agent_id, "--json"], as_json=True)
        existing_hosts = {rule.get("host") for rule in rules if rule.get("verdict") == "allow"}
        for host in HOSTS:
            if host not in existing_hosts:
                print(f"Allow network: {host}", flush=True)
                run(["dam", "network", "create", agent_id, "--host", host, "--yes", "--json"], as_json=True)
        imported = update_existing(agent_id, package) if agent else import_when_ready(agent_id, package)
        print("Tracked source installed in ~/work/qiskit-lab; existing workspace data preserved.", flush=True)
        install_home_instructions(agent_id, temporary)
        deployment["import"] = imported
        state_path.write_text(json.dumps(deployment, indent=2) + "\n")
        deployment["model"] = configure_model(agent_id, args.model)
        deployment["report_schedule"] = configure_report_schedule(agent_id)
        if not args.no_run:
            prompt_file = Path(temporary) / "bootstrap.txt"
            prompt_file.write_text(BOOTSTRAP)
            deployment["onboarding"] = run(["dam", "run", agent_id, "--prompt-file", str(prompt_file),
                                            "--async", "--json"], as_json=True)
        state_path.write_text(json.dumps(deployment, indent=2) + "\n")
        print(json.dumps(deployment, indent=2))
        print(f"Open DAM and select {name}; or run: dam chat {agent_id}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        raise SystemExit(str(error)) from None
