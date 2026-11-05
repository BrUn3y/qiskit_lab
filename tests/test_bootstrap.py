import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def bootstrap(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts/dam"))
    spec = importlib.util.spec_from_file_location("dam_bootstrap", ROOT / "scripts/dam/bootstrap.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_native_install_preserves_owner_rules_and_routes_an_arbitrary_checkout(bootstrap, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    (home / "AGENTS.md").write_text("# Owner agent rules\nKeep these notes.\n")
    (home / "AGENTS.md").chmod(0o600)
    (home / "CLAUDE.md").write_text("# Owner Claude rules\nKeep this style.\n")
    project = tmp_path / "a checkout's directory"
    quantum = project / "scripts/dam/quantum"
    quantum.parent.mkdir(parents=True)
    quantum.write_text('#!/usr/bin/env bash\nprintf "routed\\n%s\\n" "$@"\n')
    result = bootstrap.install(home, project)
    agent_rules = (home / "AGENTS.md").read_text()
    claude_rules = (home / "CLAUDE.md").read_text()
    assert "Keep these notes." in agent_rules
    assert "Keep this style." in claude_rules
    assert "~/work/qiskit-lab" not in agent_rules
    assert "@AGENTS.md" in claude_rules.splitlines()
    assert (home / "AGENTS.md").stat().st_mode & 0o777 == 0o600
    command = subprocess.run(["bash", result["command_path"], "doctor"], cwd=tmp_path,
                             text=True, capture_output=True, check=True)
    assert command.stdout.splitlines() == ["routed", "doctor"]
    assert not (project / "artifacts").exists()
    bootstrap.install(home, project)
    assert (home / "AGENTS.md").read_text() == agent_rules
    assert (home / "CLAUDE.md").read_text() == claude_rules


def test_native_install_checks_both_documents_before_overwriting_either(bootstrap, tmp_path):
    (tmp_path / "AGENTS.md").write_text("Owner rules\n")
    (tmp_path / "CLAUDE.md").write_text("<!-- qiskit-lab:instructions:start -->")
    with pytest.raises(RuntimeError, match="Incomplete"):
        bootstrap.install(tmp_path, ROOT)
    assert (tmp_path / "AGENTS.md").read_text() == "Owner rules\n"
    assert not (tmp_path / ".local/bin/qiskit-lab-dam").exists()


def test_native_install_does_not_follow_instruction_symlinks(bootstrap, tmp_path):
    owner = tmp_path / "owner.md"
    owner.write_text("Owner document")
    (tmp_path / "AGENTS.md").symlink_to(owner)
    with pytest.raises(RuntimeError, match="symlink"):
        bootstrap.install(tmp_path, ROOT)
    assert owner.read_text() == "Owner document"


def test_bootstrap_command_needs_no_dam_cli_or_quantum_account(tmp_path):
    result = subprocess.run([sys.executable, str(ROOT / "scripts/dam/bootstrap.py"), "--home", str(tmp_path)],
                            cwd=tmp_path, text=True, capture_output=True, check=True)
    assert "command_path" in result.stdout
    assert not (tmp_path / "artifacts").exists()
    assert not (tmp_path / ".qiskit").exists()
