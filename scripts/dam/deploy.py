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
         "us-east.quantum.cloud.ibm.com", "eu-de.quantum.cloud.ibm.com")
BOOTSTRAP = """Trabaja en ~/work/qiskit-lab. Lee AGENTS.md y ONBOARDING.md.
Ejecuta scripts/dam/quantum onboarding. Si falta la cuenta, tu primera respuesta
debe pedir al usuario que configure su API key de IBM Quantum, mostrar el comando
de configuración con prompt oculto en su propia Terminal de DAM y ofrecer el
simulador local. No ejecutes demostraciones antes de esta invitación. No solicites
la clave como texto o formulario del chat, no leas credenciales ni ejecutes tú el
prompt oculto. Menciona QISKIT_IBM_TOKEN como variable de la API key, el alias
QISKIT_IBM_RUNTIME_APIKEY y QISKIT_IBM_INSTANCE para el CRN; el prompt oculto guarda
la cuenta del SDK y no requiere esas variables. Si la cuenta ya está verificada,
reutilízala. No envíes jobs a QPU.
"""
HOME_START = "<!-- qiskit-lab:instructions:start -->"
HOME_END = "<!-- qiskit-lab:instructions:end -->"
HOME_INSTRUCTIONS = f"""{HOME_START}
You are Qiskit Lab. Your project is ~/work/qiskit-lab.
At the beginning of EVERY new chat, before replying to its first user message,
read ~/work/qiskit-lab/AGENTS.md and ~/work/qiskit-lab/ONBOARDING.md, then run
~/work/qiskit-lab/scripts/dam/quantum onboarding.
If status is needs_credentials, your FIRST reply asks the owner to configure
their IBM Quantum API key and optional instance CRN, shows the returned command
for their own DAM Terminal with hidden input, and offers local simulation.
Name QISKIT_IBM_TOKEN as the API-key variable, QISKIT_IBM_RUNTIME_APIKEY as its
supported alias and QISKIT_IBM_INSTANCE for the CRN. Hidden setup saves the SDK
account instead, so setting environment variables is optional.
Do not collect the key in chat or a masked chat form; both enter the transcript.
Do not run algorithm demos before that invitation. If ready, reuse the verified
account without asking again. Explain a connection_error without reading secrets.
Never submit a hardware job during onboarding. Follow the user's language.
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
    if not (destination / "dam/uv.lock").exists():
        raise RuntimeError("Missing tracked DAM lockfile. Commit or stage the kit before deployment.")


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


def merge_home_instructions(existing):
    if (HOME_START in existing) != (HOME_END in existing):
        raise RuntimeError("Incomplete Qiskit Lab instructions block; preserving the home instructions unchanged.")
    existing = re.sub(re.escape(HOME_START) + r".*?" + re.escape(HOME_END), "", existing, flags=re.DOTALL)
    return existing.rstrip() + "\n\n" + HOME_INSTRUCTIONS + "\n"


def install_home_instructions(agent_id, temporary):
    # Preserve DAM and owner instructions outside our managed section. Do not
    # replace the workspace just to update the first-chat behavior.
    existing = run(["dam", "file", "get", agent_id, "AGENTS.md", "--stdout"])
    path = Path(temporary) / "home-AGENTS.md"
    path.write_text(merge_home_instructions(existing))
    run(["dam", "file", "put", agent_id, str(path), "AGENTS.md", "--overwrite"])


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--name", default="Qiskit Lab")
    cli.add_argument("--template", default="default")
    cli.add_argument("--provider", help="Existing DAM model provider; defaults to your preferred provider")
    cli.add_argument("--model", help="Optional model from dam agent models")
    cli.add_argument("--instance", help="Non-secret IBM Quantum instance CRN")
    cli.add_argument("--existing", action="store_true", help="Explicitly re-import code into an existing named agent")
    cli.add_argument("--no-run", action="store_true", help="Import and configure only; do not start onboarding")
    args = cli.parse_args()
    agents = run(["dam", "agent", "list", "--json"], as_json=True)
    matches = [agent for agent in agents if agent["name"] == args.name]
    if len(matches) > 1:
        raise RuntimeError("Agent name is ambiguous. Choose a unique name.")
    if matches and not args.existing:
        raise RuntimeError("Agent already exists. Use --existing only to deliberately update its qiskit-lab folder.")
    if not matches and args.existing:
        raise RuntimeError("--existing requires an agent that already exists.")
    # Validate the package before creating any platform resources.
    with tempfile.TemporaryDirectory(prefix="qiskit-lab-dam-") as temporary:
        package = Path(temporary) / "qiskit-lab"
        package.mkdir()
        copy_tracked(package)
        if matches:
            agent_id = matches[0]["id"]
        else:
            command = ["dam", "agent", "create", args.name, "--template", args.template,
                       "--description", "Qiskit Lab: Qiskit and IBM Quantum Platform", "--json"]
            if args.provider:
                command += ["--provider", args.provider]
            if args.instance:
                command += ["--env", "QISKIT_IBM_INSTANCE=" + args.instance]
            created = run(command, as_json=True)
            agent_id = created["id"]
        deployment = {"agent_id": agent_id, "name": args.name, "source_commit": run(["git", "rev-parse", "HEAD"])}
        state_path = ROOT / ".dam-deploy/deployment.json"
        state_path.parent.mkdir(exist_ok=True)
        state_path.write_text(json.dumps(deployment, indent=2) + "\n")
        print(f"Agent: {args.name} ({agent_id})", flush=True)
        run(["dam", "network", "apply-preset", agent_id, "--preset", "trusted", "--json"], as_json=True)
        rules = run(["dam", "network", "list", agent_id, "--json"], as_json=True)
        existing_hosts = {rule.get("host") for rule in rules if rule.get("verdict") == "allow"}
        for host in HOSTS:
            if host not in existing_hosts:
                print(f"Allow network: {host}", flush=True)
                run(["dam", "network", "create", agent_id, "--host", host, "--yes", "--json"], as_json=True)
        imported = import_when_ready(agent_id, package)
        print("Tracked project imported into ~/work/qiskit-lab.", flush=True)
        install_home_instructions(agent_id, temporary)
        deployment["import"] = imported
        state_path.write_text(json.dumps(deployment, indent=2) + "\n")
        deployment["model"] = configure_model(agent_id, args.model)
        if not args.no_run:
            prompt_file = Path(temporary) / "bootstrap.txt"
            prompt_file.write_text(BOOTSTRAP)
            deployment["onboarding"] = run(["dam", "run", agent_id, "--prompt-file", str(prompt_file),
                                            "--async", "--json"], as_json=True)
        state_path.write_text(json.dumps(deployment, indent=2) + "\n")
        print(json.dumps(deployment, indent=2))
        print(f"Open DAM and select {args.name}; or run: dam chat {agent_id}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        raise SystemExit(str(error)) from None
