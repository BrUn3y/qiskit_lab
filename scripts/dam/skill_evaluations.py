#!/usr/bin/env python3
"""Check deterministic case/resource integration or emit a blinded evaluation prompt.

This does not invoke a model, select skills from user text, or grade agent behavior.
PyYAML is an existing development dependency, not a runtime requirement.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import yaml
from qiskit_skills import ROOT, bundle_path, read_bundle

CORPUS = "evals/skills/cases.json"


def resource(root, path):
    file = bundle_path(root, path)
    content = file.read_bytes()
    return {"path": file.relative_to(root).as_posix(), "sha256": hashlib.sha256(content).hexdigest()}


def check_cases(root):
    manifest = read_bundle(root)
    corpus = json.loads((root / CORPUS).read_text(encoding="utf-8"))
    if corpus["schema_version"] != 1 or corpus["upstream_revision"] != manifest["revision"]:
        raise ValueError("Review the cases against the candidate upstream revision")
    if not isinstance(corpus["safety_context"], str) or not corpus["safety_context"].strip():
        raise ValueError("Missing evaluation safety context")
    names = {skill["name"] for skill in manifest["skills"]} | {"qiskit-lab"}
    instructions = (root / "AGENTS.md").read_text(encoding="utf-8")
    for skill in manifest["skills"]:
        if skill["path"] + "/SKILL.md" not in instructions:
            raise ValueError("Official skill missing from project routing instructions")
        frontmatter = bundle_path(root, skill["path"] + "/SKILL.md").read_text(encoding="utf-8").split("---", 2)
        metadata = yaml.safe_load(frontmatter[1])
        if metadata["name"] != skill["name"] or not metadata["description"]:
            raise ValueError("Skill discovery metadata does not match manifest")
    ids, covered, results = set(), set(), []
    for case in corpus["cases"]:
        if not case["id"] or case["id"] in ids:
            raise ValueError("Missing or duplicate case ID")
        ids.add(case["id"])
        if not isinstance(case["prompt"], str) or not case["prompt"].strip():
            raise ValueError("Empty case prompt")
        selected = set(case["expected_skills"])
        if not selected or not selected <= names or len(selected) != len(case["expected_skills"]):
            raise ValueError("Unknown, empty or duplicate expected skill")
        covered.update(selected)
        if not case["resources"] or not case["rubric"] or not all(
            isinstance(item, str) and item.strip() for item in case["rubric"]
        ):
            raise ValueError("A case needs resources and a human-review rubric")
        reads = [resource(root, f".agents/skills/{name}/SKILL.md") for name in sorted(selected)]
        for request in case["resources"]:
            reads.append(resource(root, request["path"]))
            if "heading" in request:
                lines = bundle_path(root, request["path"]).read_text(encoding="utf-8").splitlines()
                if not any(line == request["heading"] or line.startswith(request["heading"] + " ") for line in lines):
                    raise ValueError(f"Referenced section missing: {request['path']}")
        external = []
        for check in case["registry_checks"]:
            resource(root, check["path"])
            registry = yaml.safe_load(bundle_path(root, check["path"]).read_text(encoding="utf-8"))
            matches = [entry for entry in registry[check["collection"]]
                       if all(entry.get(key) == value for key, value in check["match"].items())]
            if len(matches) != 1:
                raise ValueError("Registry selector must identify exactly one entry")
            for field, expected in check["links"].items():
                actual = matches[0]
                for key in field.split("."):
                    actual = actual[key]
                if actual != expected:
                    raise ValueError("Registry resource pointer changed; review the case")
                if actual.startswith("https://"):
                    external.append({"url": actual, "access": "not_attempted_offline"})
                else:
                    path = actual if actual.startswith((".agents/", ".claude/")) else (
                        str(Path(check["path"]).parent / actual)
                    )
                    reads.append(resource(root, path))
        results.append({"id": case["id"], "resources": reads, "external_resources": external})
    if covered != names:
        raise ValueError("Corpus must cover every bundled skill and the project negative control")
    return {
        "kind": "deterministic_resource_integration", "upstream_revision": manifest["revision"],
        "cases": results, "agent_behavior_evaluations_run": 0,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true")
    action.add_argument("--case", help="Emit only safety context and user task, without expected skills or rubric")
    args = parser.parse_args(argv)
    if args.check:
        print(json.dumps(check_cases(args.root), indent=2))
    else:
        corpus = json.loads((args.root / CORPUS).read_text(encoding="utf-8"))
        matches = [case for case in corpus["cases"] if case["id"] == args.case]
        if len(matches) != 1:
            parser.error("Unknown or duplicate case ID")
        print(corpus["safety_context"] + "\n\n" + matches[0]["prompt"])
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError, yaml.YAMLError) as error:
        raise SystemExit(f"Evaluation integration failed ({type(error).__name__}); review corpus and resources.") from None
