import importlib.util
import json
import sys
from pathlib import Path

import jsonschema
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def deploy():
    spec = importlib.util.spec_from_file_location("dam_deploy", ROOT / "scripts/dam/deploy.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_kit_matches_official_schema_and_bootstrap_files_exist():
    schema = json.loads((ROOT / "dam/kit.schema.json").read_text())
    kit = yaml.safe_load((ROOT / "kit.yaml").read_text())
    jsonschema.Draft202012Validator(schema).validate(kit)
    assert kit["seed"] == {"self": True, "into": "work"}
    assert (ROOT / "ONBOARDING.md").exists()
    assert (ROOT / kit["bundledSkills"]["path"] / "qiskit-lab/SKILL.md").exists()
    assert not kit.get("schedules")
    assert not kit.get("env")


def test_deployer_network_rules_match_manifest():
    spec = importlib.util.spec_from_file_location("dam_deploy", ROOT / "scripts/dam/deploy.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    kit = yaml.safe_load((ROOT / "kit.yaml").read_text())
    assert set(module.HOSTS) == {rule["host"] for rule in kit["egressRules"]}


def test_first_chat_instructions_preserve_owner_text_and_are_idempotent():
    spec = importlib.util.spec_from_file_location("dam_deploy_home", ROOT / "scripts/dam/deploy.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original = "# My DAM instructions\nPreserve my project notes.\n"
    result = module.merge_home_instructions(original)
    assert original.strip() in result
    assert "quantum onboarding" in result
    assert result == module.merge_home_instructions(result)
    assert result.count(module.HOME_START) == 1
    with pytest.raises(RuntimeError, match="Incomplete"):
        module.merge_home_instructions(original + module.HOME_START)


def test_update_preserves_remote_results_and_environment(deploy, monkeypatch, tmp_path):
    package = tmp_path / "package"
    package.mkdir()
    (package / "AGENTS.md").write_text("Updated instructions")
    (package / "src").mkdir()
    (package / "src/cli.py").write_text("Updated source")
    remote = tmp_path / "remote"
    preserved = ["artifacts/dam/run/report.html", ".venv/pyvenv.cfg", "owner-notes.md"]
    for name in preserved + ["src/cli.py"]:
        path = remote / "work/qiskit-lab" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("Existing data")

    def put(arguments):
        assert arguments[:4] == ["dam", "file", "put", "agent-target"]
        assert arguments[-1] == "--overwrite"
        destination = remote / arguments[5]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(Path(arguments[4]).read_bytes())

    monkeypatch.setattr(deploy, "run", put)
    result = deploy.update_existing("agent-target", package)
    assert result["files_updated"] == 2
    assert (remote / "work/qiskit-lab/src/cli.py").read_text() == "Updated source"
    for name in preserved:
        assert (remote / "work/qiskit-lab" / name).read_text() == "Existing data"


def test_exact_agent_id_resolves_duplicate_names_without_creating_an_agent(deploy):
    agents = [{"id": "agent-one", "name": "Qiskit Lab"}, {"id": "agent-two", "name": "Qiskit Lab"}]
    assert deploy.select_agent(agents, "Qiskit Lab", "agent-two", True) == agents[1]
    with pytest.raises(RuntimeError, match="ambiguous"):
        deploy.select_agent(agents, "Qiskit Lab", None, True)
    with pytest.raises(RuntimeError, match="requires --existing"):
        deploy.select_agent(agents, "Qiskit Lab", "agent-two", False)
    with pytest.raises(RuntimeError, match="already exists"):
        deploy.select_agent(agents, "Qiskit Lab", "agent-missing", True)


def test_dry_run_validates_package_without_changing_dam(deploy, monkeypatch, tmp_path, capsys):
    calls = []

    def run(arguments, *, as_json=False):
        calls.append(arguments)
        if arguments == ["dam", "agent", "list", "--json"]:
            return [{"id": "agent-target", "name": "Owner's Lab"}]
        if arguments == ["git", "ls-files", "-z"]:
            return "uv.lock\0AGENTS.md\0"
        pytest.fail(f"Dry run attempted an unexpected action: {arguments}")

    monkeypatch.setattr(deploy, "run", run)
    monkeypatch.setattr(deploy, "ROOT", tmp_path)
    (tmp_path / "uv.lock").write_text("Lockfile")
    (tmp_path / "AGENTS.md").write_text("Instructions")
    monkeypatch.setattr(sys, "argv", ["deploy.py", "--existing", "--agent", "agent-target", "--dry-run"])
    assert deploy.main() == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["agent_id"] == "agent-target"
    assert plan["name"] == "Owner's Lab"
    assert plan["files"] == ["AGENTS.md", "uv.lock"]
    assert not (tmp_path / ".dam-deploy").exists()
    assert len(calls) == 2


def test_schedule_upgrade_preserves_owner_settings(deploy, monkeypatch):
    from unittest.mock import Mock

    original = {"id": "sched-existing", "name": deploy.REPORT_SCHEDULE_NAME,
                "task": "Old instructions", "enabled": False, "rrule": "FREQ=HOURLY;INTERVAL=1"}
    run = Mock(side_effect=[[original], {**original, "task": deploy.REPORT_TASK}])
    monkeypatch.setattr(deploy, "run", run)
    result = deploy.configure_report_schedule("agent-target")
    assert result["id"] == "sched-existing"
    assert not result["enabled"]
    update = run.call_args.args[0]
    assert update[:4] == ["dam", "schedule", "update", "sched-existing"]
    assert "--every" not in update
    assert "--model" not in update
    assert "--timezone" not in update
    assert update[update.index("--precheck") + 1] == deploy.REPORT_PRECHECK


def test_current_schedule_is_not_rewritten(deploy, monkeypatch):
    from unittest.mock import Mock

    original = {"id": "sched-existing", "name": deploy.REPORT_SCHEDULE_NAME,
                "task": deploy.REPORT_TASK, "precheck": deploy.REPORT_PRECHECK, "sessionMode": "fresh"}
    run = Mock(return_value=[original])
    monkeypatch.setattr(deploy, "run", run)
    assert deploy.configure_report_schedule("agent-target") == original
    run.assert_called_once_with(["dam", "schedule", "list", "agent-target", "--json"], as_json=True)


def test_existing_deployment_uses_file_updates_and_preserves_network_rules(deploy, monkeypatch, tmp_path):
    from unittest.mock import Mock

    def run(arguments, *, as_json=False):
        if arguments == ["dam", "agent", "list", "--json"]:
            return [{"id": "agent-target", "name": "Owner's Lab"}]
        if arguments == ["git", "ls-files", "-z"]:
            return "uv.lock\0"
        if arguments == ["git", "rev-parse", "HEAD"]:
            return "source-commit"
        if arguments == ["dam", "network", "list", "agent-target", "--json"]:
            return [{"host": host, "verdict": "allow"} for host in deploy.HOSTS]
        pytest.fail(f"Existing deployment attempted an unexpected action: {arguments}")

    monkeypatch.setattr(deploy, "ROOT", tmp_path)
    (tmp_path / "uv.lock").write_text("Lockfile")
    monkeypatch.setattr(deploy, "run", run)
    update = Mock(return_value={"files_updated": 1})
    monkeypatch.setattr(deploy, "update_existing", update)
    monkeypatch.setattr(deploy, "install_home_instructions", Mock())
    monkeypatch.setattr(deploy, "configure_model", Mock(return_value="owner/model"))
    monkeypatch.setattr(deploy, "configure_report_schedule", Mock(return_value={"id": "sched-existing"}))
    monkeypatch.setattr(sys, "argv", ["deploy.py", "--existing", "--agent", "agent-target", "--no-run"])
    assert deploy.main() == 0
    update.assert_called_once()
    assert update.call_args.args[0] == "agent-target"
    state = json.loads((tmp_path / ".dam-deploy/deployment.json").read_text())
    assert state["agent_id"] == "agent-target"
    assert state["name"] == "Owner's Lab"
    assert "onboarding" not in state
