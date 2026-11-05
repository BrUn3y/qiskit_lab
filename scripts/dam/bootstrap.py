#!/usr/bin/env python3
"""Install checkout-relative DAM entry points without accessing IBM accounts."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import shlex
import tempfile
from pathlib import Path

from deploy import HOME_CLAUDE_INSTRUCTIONS, HOME_INSTRUCTIONS, merge_home_instructions


def atomic_write(path, content, mode=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(content)
        if mode is not None:
            temporary.chmod(mode)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def install(home, project):
    home.mkdir(parents=True, exist_ok=True)
    instructions = HOME_INSTRUCTIONS.replace("~/work/qiskit-lab", shlex.quote(str(project)))
    with (home / ".qiskit-lab-bootstrap.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        updates = []
        for name, block in [("AGENTS.md", instructions), ("CLAUDE.md", HOME_CLAUDE_INSTRUCTIONS)]:
            path = home / name
            if path.is_symlink():
                raise RuntimeError(f"Refusing to replace a symlink instruction file: {name}")
            existing = path.read_text() if path.exists() else ""
            # Validate both documents before writing either one.
            updates.append((path, merge_home_instructions(existing, block), path.stat().st_mode & 0o777
                            if path.exists() else 0o644))
        for path, content, mode in updates:
            atomic_write(path, content, mode)
        wrapper = home / ".local/bin/qiskit-lab-dam"
        command = shlex.quote(str(project / "scripts/dam/quantum"))
        atomic_write(wrapper, f'#!/usr/bin/env bash\nset -euo pipefail\nexec bash {command} "$@"\n', 0o755)
    return {"project_root": str(project), "home": str(home), "command_path": str(wrapper)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=Path.home(), help="Agent home; defaults to the current user's home")
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[2]
    print(json.dumps(install(args.home.resolve(), project), indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
