import importlib.util
import json
import sys
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_kit_matches_official_schema_and_bootstrap_files_exist():
    schema = json.loads((ROOT / "dam/kit.schema.json").read_text())
    kit = yaml.safe_load((ROOT / "kit.yaml").read_text())
    jsonschema.Draft202012Validator(schema).validate(kit)
    assert kit["seed"] == {"self": True, "into": "work"}
    assert (ROOT / "ONBOARDING.md").exists()
    assert (ROOT / kit["bundledSkills"]["path"] / "quantum-lab/SKILL.md").exists()
    assert not kit.get("schedules")
    assert not kit.get("env")


def test_deployer_network_rules_match_manifest():
    spec = importlib.util.spec_from_file_location("dam_deploy", ROOT / "scripts/dam/deploy.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    kit = yaml.safe_load((ROOT / "kit.yaml").read_text())
    assert set(module.HOSTS) == {rule["host"] for rule in kit["egressRules"]}
