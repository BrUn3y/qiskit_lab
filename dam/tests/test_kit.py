import importlib.util
import json
import sys
from pathlib import Path

import jsonschema
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


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
