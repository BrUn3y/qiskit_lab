#!/usr/bin/env python3
"""Deploy a committed private checkout using only the public DAM CLI.

No GitHub connection is required: only reviewed, tracked working-tree files are
copied. Local account files, .env files, .git and run artifacts are never sent.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOSTS = ("pypi.org", "files.pythonhosted.org", "github.com", "release-assets.githubusercontent.com",
         "iam.cloud.ibm.com", "resource-controller.cloud.ibm.com", "quantum.cloud.ibm.com",
         "us-east.quantum.cloud.ibm.com", "eu-de.quantum.cloud.ibm.com")
BOOTSTRAP = """Trabaja en ~/work/quantum-lab. Lee AGENTS.md, CLAUDE.md y ONBOARDING.md.
Sigue el onboarding: ejecuta bash scripts/dam/setup.sh, prueba Bell, Grover,
Deutsch–Jozsa y QAOA Max-Cut local de cinco nodos. Después prueba
scripts/dam/quantum doctor --online. No envíes ningún job a hardware durante el
onboarding. No leas archivos de credenciales ni variables secretas. Si falta la
cuenta IBM Quantum, muestra al usuario el comando de configuración para que él
lo ejecute en su propia Terminal de DAM, con prompt oculto. No lo ejecutes tú.
Reporta en español los resultados reales, rutas de artefactos y el paso pendiente.
"""


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


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--name", default="quantum-lab")
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
        raise RuntimeError("Agent already exists. Use --existing only to deliberately update its quantum-lab folder.")
    if not matches and args.existing:
        raise RuntimeError("--existing requires an agent that already exists.")
    # Validate the package before creating any platform resources.
    with tempfile.TemporaryDirectory(prefix="quantum-lab-dam-") as temporary:
        package = Path(temporary) / "quantum-lab"
        package.mkdir()
        copy_tracked(package)
        if matches:
            agent_id = matches[0]["id"]
        else:
            command = ["dam", "agent", "create", args.name, "--template", args.template,
                       "--description", "Quantum Lab: Qiskit and IBM Quantum Platform", "--json"]
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
        imported = run(["dam", "import", agent_id, str(package), "--yes", "--json"], as_json=True)
        print("Tracked project imported into ~/work/quantum-lab.", flush=True)
        deployment["import"] = imported
        if args.model:
            run(["dam", "agent", "update", agent_id, "--model", args.model, "--json"], as_json=True)
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
