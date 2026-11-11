#!/usr/bin/env python3
"""Verify pinned resources or prepare an offline, review-only upstream proposal."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ".agents/qiskit-skills.json"
NOTICE = ".agents/skills/QISKIT-SKILLS-NOTICE.md"
REPOSITORY = "https://github.com/Qiskit/skills"
ATTRIBUTION_NAMES = ("LICENSE", "NOTICE", "COPYING", "COPYRIGHT")


def relative_path(value):
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or path.as_posix() != value or "\\" in value:
        raise ValueError(f"Unsafe relative resource path: {value}")
    return path


def bundle_path(root, value):
    """Resolve upstream's historical .claude prefix without editing its bytes."""
    if value.startswith(".claude/skills/"):
        value = ".agents/skills/" + value.removeprefix(".claude/skills/")
    path = relative_path(value)
    if path.parts[:2] != (".agents", "skills"):
        raise ValueError("Resources must be under .agents/skills")
    target = root
    for part in path.parts:
        target = target / part
        if target.is_symlink():
            raise ValueError(f"Symlink resource is not supported: {value}")
    return target


def blob_hash(content):
    return hashlib.sha1(f"blob {len(content)}\0".encode() + content, usedforsecurity=False).hexdigest()


def read_bundle(root):
    manifest_path = root / MANIFEST
    if manifest_path.is_symlink() or manifest_path.parent.is_symlink():
        raise ValueError("Manifest must not be a symlink")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["repository"] != REPOSITORY or not re.fullmatch("[0-9a-f]{40}", manifest["revision"]):
        raise ValueError("Expected the official repository and a full SHA-1 revision")
    names = set()
    for skill in manifest["skills"]:
        name = skill["name"]
        if not re.fullmatch("[a-z0-9]+(?:-[a-z0-9]+)*", name) or name in names:
            raise ValueError("Invalid or duplicate skill name")
        names.add(name)
        if skill["path"] != f".agents/skills/{name}" or skill["upstream_path"] != f"skills/{name}":
            raise ValueError("Unexpected skill source/destination mapping")
        folder = bundle_path(root, skill["path"])
        actual = set()
        for file in folder.rglob("*"):
            if file.is_symlink():
                raise ValueError("Symlink in bundled skill")
            if file.is_file():
                actual.add(file.relative_to(root).as_posix())
        expected = {file for file in manifest["files"] if file.startswith(skill["path"] + "/")}
        if not expected or actual != expected or skill["path"] + "/SKILL.md" not in expected:
            raise ValueError(f"Incomplete resource inventory: {name}")
    if not names or manifest["license_path"] not in manifest["files"]:
        raise ValueError("Missing skills or upstream license")
    for local, metadata in manifest["files"].items():
        path = bundle_path(root, local)
        upstream = relative_path(metadata["upstream_path"])
        owner = next((skill for skill in manifest["skills"] if local.startswith(skill["path"] + "/")), None)
        if owner:
            expected_source = owner["upstream_path"] + local.removeprefix(owner["path"])
            if upstream.as_posix() != expected_source:
                raise ValueError("Resource source mapping mismatch")
        elif not (
            (path.parent == root / ".agents/skills"
             and path.name.startswith("QISKIT-SKILLS-") and len(upstream.parts) == 1)
            or (upstream.parts[0].upper().startswith(ATTRIBUTION_NAMES)
                and local == ".agents/skills/QISKIT-SKILLS-UPSTREAM-" + upstream.as_posix())
        ):
            raise ValueError("Unexpected root attribution resource")
        content = path.read_bytes()
        if blob_hash(content) != metadata["git_blob_sha1"]:
            raise ValueError(f"Git blob hash mismatch: {local}")
        if "sha256" in metadata and hashlib.sha256(content).hexdigest() != metadata["sha256"]:
            raise ValueError(f"SHA-256 mismatch: {local}")
        if "git_mode" in metadata:
            mode = "100755" if path.stat().st_mode & 0o111 else "100644"
            if mode != metadata["git_mode"]:
                raise ValueError(f"File mode mismatch: {local}")
    return manifest


def git(source, *args):
    # Read objects only: no fetch, checkout, hooks, filters, or upstream execution.
    return subprocess.run(
        ["git", "--no-lazy-fetch", "--no-replace-objects", "-C", str(source), *args],
        check=True, capture_output=True,
    ).stdout


def propose(root, source, revision, output):
    current = read_bundle(root)
    if not re.fullmatch("[0-9a-f]{40}", revision):
        raise ValueError("Use an explicit full commit SHA, not a branch or tag")
    resolved = git(source, "rev-parse", "--verify", revision + "^{commit}").decode().strip()
    if resolved != revision:
        raise ValueError("Revision must identify a commit, not a tag object")
    output = output.absolute()
    for checkout in (root.resolve(), source.resolve()):
        if output.resolve().is_relative_to(checkout) or checkout.is_relative_to(output.resolve()):
            raise ValueError("Proposal must be outside both the project and upstream checkout")
    if output.exists() or output.is_symlink():
        raise ValueError("Proposal output already exists; choose a new directory")
    tree = {}
    for record in git(source, "ls-tree", "-rz", "--full-tree", revision).split(b"\0"):
        if record:
            header, raw_path = record.split(b"\t", 1)
            mode, kind, oid = header.decode().split()
            name = raw_path.decode("utf-8")
            relative_path(name)
            tree[name] = (mode, kind, oid)
    mappings = {}
    for skill in current["skills"]:
        prefix = skill["upstream_path"] + "/"
        selected = [name for name in tree if name.startswith(prefix)]
        if skill["upstream_path"] + "/SKILL.md" not in selected:
            raise ValueError(f"Upstream skill entry point missing: {skill['name']}")
        for name in selected:
            mappings[skill["path"] + "/" + name.removeprefix(prefix)] = name
    license_source = current["files"][current["license_path"]]["upstream_path"]
    if license_source not in tree:
        raise ValueError("Upstream license missing; explicit licensing review required")
    # Preserve root legal files/directories as well as every recorded attribution.
    for local, metadata in current["files"].items():
        if not local.startswith(tuple(skill["path"] + "/" for skill in current["skills"])):
            mappings[local] = metadata["upstream_path"]
    for name in tree:
        if PurePosixPath(name).parts[0].upper().startswith(ATTRIBUTION_NAMES) and name not in mappings.values():
            mappings[f".agents/skills/QISKIT-SKILLS-UPSTREAM-{name}"] = name
    contents = {}
    candidate = copy.deepcopy(current)
    candidate["revision"] = revision
    candidate["files"] = {}
    for local, upstream in sorted(mappings.items()):
        bundle_path(root, local)
        if upstream not in tree:
            raise ValueError(f"Recorded attribution disappeared upstream: {upstream}")
        mode, kind, oid = tree[upstream]
        if kind != "blob" or mode not in {"100644", "100755"}:
            raise ValueError(f"Unsupported upstream resource mode/type: {upstream}")
        content = git(source, "cat-file", "blob", oid)
        if blob_hash(content) != oid:
            raise ValueError(f"Upstream object hash mismatch: {upstream}")
        contents[local] = content
        candidate["files"][local] = {
            "upstream_path": upstream, "git_blob_sha1": oid,
            "sha256": hashlib.sha256(content).hexdigest(), "git_mode": mode,
        }
    old, new = current["files"], candidate["files"]

    def old_mode(name):
        return old[name].get("git_mode") or ("100755" if (root / name).stat().st_mode & 0o111 else "100644")

    added, removed = sorted(new.keys() - old.keys()), sorted(old.keys() - new.keys())
    changed = sorted(name for name in old.keys() & new.keys()
                     if old[name]["git_blob_sha1"] != new[name]["git_blob_sha1"] or old_mode(name) != new[name]["git_mode"])
    changed_sources = [new[name]["upstream_path"] if name in new else old[name]["upstream_path"]
                       for name in added + removed + changed]
    license_changed = any(any(part.upper().startswith(("LICENSE", "COPYING", "COPYRIGHT"))
                              for part in PurePosixPath(name).parts)
                          for name in changed_sources)
    attribution_changed = license_changed or any(
        any(part.upper().startswith("NOTICE") for part in PurePosixPath(name).parts) for name in changed_sources
    )
    if license_changed:
        candidate["license"] = "REVIEW-REQUIRED"
    report = {
        "review_only": True, "repository": REPOSITORY,
        "from_revision": current["revision"], "to_revision": revision,
        "license_review_required": license_changed,
        "attribution_review_required": attribution_changed,
        "added": added, "removed": removed, "changed": changed,
        "agent_behavior_evaluation": "not_run",
    }
    attribution = "\n".join(f"- `{local}` from `{upstream}`" for local, upstream in sorted(mappings.items())
                           if not upstream.startswith("skills/"))
    notice = (
        "# Official Qiskit AI Skills\n\n"
        f"Source: <{REPOSITORY}>\n\nRevision: `{revision}`\n\n"
        "Complete, unmodified selected skill directories and upstream attribution files.\n"
        f"License identifier: `{candidate['license']}`; review licensing before approval.\n\n"
        f"{attribution}\n\nSource paths, Git blob hashes, SHA-256 and modes: `../qiskit-skills.json`.\n"
        "The project-specific qiskit-lab skill is separate. This proposal is not applied or deployed.\n"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    # Publish a complete proposal only; failures leave the requested output absent.
    with tempfile.TemporaryDirectory(prefix=".qiskit-skills-", dir=output.parent) as temporary:
        staged = Path(temporary) / "proposal"
        staged.mkdir()
        for local, content in contents.items():
            destination = staged / local
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
            destination.chmod(int(candidate["files"][local]["git_mode"], 8) & 0o777)
        (staged / MANIFEST).write_text(json.dumps(candidate, indent=2) + "\n", encoding="utf-8")
        (staged / NOTICE).write_text(notice, encoding="utf-8")
        (staged / "proposal.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        read_bundle(staged)
        output.mkdir()
        try:
            staged.rename(output)
        except OSError:
            output.rmdir()
            raise
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("verify", help="Check the complete pinned inventory and hashes offline")
    proposal = commands.add_parser("propose", help="Write a new external review directory; never apply it")
    proposal.add_argument("--source", type=Path, required=True, help="Already available local upstream Git repository")
    proposal.add_argument("--revision", required=True, help="Reviewed full 40-character commit SHA")
    proposal.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "verify":
        manifest = read_bundle(args.root)
        result = {"revision": manifest["revision"], "files": len(manifest["files"]), "agent_behavior": "not_evaluated"}
    else:
        result = propose(args.root, args.source, args.revision, args.output)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"Skill maintenance failed ({type(error).__name__}); check paths, manifest and revision.") from None
