"""Deterministic resource/update integration, not model behavior evaluation."""
import copy
import importlib.util
import json
import shutil
import subprocess
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts/dam" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def tools(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts/dam"))
    return load_script("qiskit_skills"), load_script("skill_evaluations")


@pytest.fixture
def bundle(tmp_path):
    destination = tmp_path / "bundle"
    shutil.copytree(ROOT / ".agents", destination / ".agents")
    shutil.copytree(ROOT / "evals", destination / "evals")
    shutil.copy2(ROOT / "AGENTS.md", destination / "AGENTS.md")
    return destination


def git(source, *args):
    return subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "-C", str(source), *args],
        capture_output=True, check=True, text=True,
    ).stdout.strip()


def commit(source):
    git(source, "add", ".")
    git(source, "-c", "user.name=Offline Fixture", "-c", "user.email=fixture@example.invalid",
        "commit", "-qm", "Synthetic upstream fixture")
    return git(source, "rev-parse", "HEAD")


@pytest.fixture
def upstream(tmp_path, tools):
    maintenance, _ = tools
    source = tmp_path / "upstream"
    source.mkdir()
    manifest = maintenance.read_bundle(ROOT)
    for local, entry in manifest["files"].items():
        target = source / entry["upstream_path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / local).read_bytes())
    git(source, "init", "-q")
    commit(source)
    return source


def snapshot(root):
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*") if path.is_file() and ".git" not in path.parts}


def test_object_reader_disables_lazy_network_fetch_and_replacement_refs(tools, monkeypatch, tmp_path):
    maintenance, _ = tools
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        assert kwargs == {"check": True, "capture_output": True}
        return subprocess.CompletedProcess(command, 0, stdout=b"fixture object")

    monkeypatch.setattr(maintenance.subprocess, "run", run)
    assert maintenance.git(tmp_path, "cat-file", "blob", "0" * 40) == b"fixture object"
    assert calls == [["git", "--no-lazy-fetch", "--no-replace-objects", "-C", str(tmp_path),
                      "cat-file", "blob", "0" * 40]]


def test_all_representative_cases_resolve_pinned_resources_without_behavior_claims(tools):
    _, evaluations = tools
    report = evaluations.check_cases(ROOT)
    assert report["kind"] == "deterministic_resource_integration"
    assert report["agent_behavior_evaluations_run"] == 0
    assert len(report["cases"]) == 9
    assert all(row["resources"] for row in report["cases"])
    external = next(case for case in report["cases"] if case["id"] == "migration-unavailable-guide")
    assert external["external_resources"][0]["access"] == "not_attempted_offline"
    assert all(not read["path"].startswith(".claude") for case in report["cases"] for read in case["resources"])
    assert all(len(read["sha256"]) == 64 for case in report["cases"] for read in case["resources"])


@pytest.mark.parametrize("case_id", [
    "migration-job-status", "migration-unavailable-guide", "mitigation-sampler-readout",
    "mitigation-pub-broadcasting", "sqd-spin-and-rdms", "sqd-complex-support",
    "fermionic-encoding", "fermionic-sqd-handoff", "local-bell-negative-control",
])
def test_blinded_prompts_do_not_include_expected_routes_or_grading(tools, capsys, case_id):
    _, evaluations = tools
    corpus = json.loads((ROOT / evaluations.CORPUS).read_text())
    case = next(row for row in corpus["cases"] if row["id"] == case_id)
    assert evaluations.main(["--case", case_id]) == 0
    assert capsys.readouterr().out == corpus["safety_context"] + "\n\n" + case["prompt"] + "\n"


def test_unknown_case_does_not_run_or_grade_anything(tools):
    with pytest.raises(SystemExit) as error:
        tools[1].main(["--case", "absent"])
    assert error.value.code == 2


@pytest.mark.parametrize("mutation", [
    "revision", "duplicate", "skill", "heading", "pointer", "empty", "coverage",
    "safety", "prompt", "selector", "routing",
])
def test_corpus_drift_fails_actionably(tools, bundle, mutation):
    _, evaluations = tools
    path = bundle / evaluations.CORPUS
    data = json.loads(path.read_text())
    case = data["cases"][0]
    if mutation == "revision":
        data["upstream_revision"] = "0" * 40
    elif mutation == "duplicate":
        data["cases"].append(copy.deepcopy(case))
    elif mutation == "skill":
        case["expected_skills"] = ["unbundled"]
    elif mutation == "heading":
        case["resources"][1]["heading"] = "## Missing section"
    elif mutation == "pointer":
        case["registry_checks"][0]["links"]["guide"] = "missing.md"
    elif mutation == "empty":
        case["rubric"] = []
    elif mutation == "safety":
        data["safety_context"] = ""
    elif mutation == "prompt":
        case["prompt"] = ""
    elif mutation == "selector":
        case["registry_checks"][0]["match"] = {"id": "missing-entry"}
    elif mutation == "routing":
        (bundle / "AGENTS.md").write_text("No bundled routing instructions")
    else:
        data["cases"] = [case]
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        evaluations.check_cases(bundle)


@pytest.mark.parametrize("relative", [
    "../escape", "/absolute", ".agents/skills/../escape", ".agents//skills/foo",
    ".agents/skills/foo\\bar", ".env", ".qiskit/account.json",
])
def test_resource_paths_cannot_escape_the_skill_bundle(tools, relative):
    with pytest.raises(ValueError):
        tools[0].bundle_path(ROOT, relative)


def test_resource_resolution_refuses_symlink_ancestors(tools, bundle, tmp_path):
    link = tmp_path / "linked"
    link.mkdir()
    (link / ".agents").symlink_to(bundle / ".agents", target_is_directory=True)
    with pytest.raises(ValueError, match="Symlink"):
        tools[0].bundle_path(link, ".agents/skills/select-error-mitigation/registry.yaml")


@pytest.mark.parametrize("damage", ["repository", "duplicate", "license", "source", "attribution"])
def test_invalid_manifest_metadata_does_not_become_a_proposal(tools, bundle, damage):
    maintenance, _ = tools
    path = bundle / maintenance.MANIFEST
    manifest = json.loads(path.read_text())
    if damage == "repository":
        manifest["repository"] = "https://example.invalid/not-upstream"
    elif damage == "duplicate":
        manifest["skills"].append(copy.deepcopy(manifest["skills"][0]))
    elif damage == "license":
        manifest["license_path"] = ".agents/skills/missing"
    elif damage == "source":
        manifest["files"][".agents/skills/select-sqd-eigensolver/registry.yaml"]["upstream_path"] = "wrong.yaml"
    else:
        manifest["files"][".agents/skills/unexpected.txt"] = {
            "upstream_path": "unexpected.txt", "git_blob_sha1": "0" * 40,
        }
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        maintenance.read_bundle(bundle)


@pytest.mark.parametrize("damage", ["missing", "extra", "changed", "symlink", "manifest-symlink", "mapping"])
def test_complete_inventory_and_integrity_fail_closed(tools, bundle, tmp_path, damage):
    maintenance, _ = tools
    path = bundle / ".agents/skills/select-error-mitigation/references/pub-broadcasting.md"
    if damage == "missing":
        path.unlink()
    elif damage == "extra":
        path.with_name("unrecorded.md").write_text("Extra resource")
    elif damage == "changed":
        path.write_text("Unexpected modification")
    elif damage == "symlink":
        path.unlink()
        path.symlink_to(ROOT / ".agents/skills/select-error-mitigation/references/pub-broadcasting.md")
    elif damage == "manifest-symlink":
        manifest = bundle / maintenance.MANIFEST
        manifest.unlink()
        manifest.symlink_to(ROOT / maintenance.MANIFEST)
    else:
        manifest = bundle / maintenance.MANIFEST
        data = json.loads(manifest.read_text())
        data["skills"][0]["upstream_path"] = "../wrong"
        manifest.write_text(json.dumps(data))
    with pytest.raises((ValueError, FileNotFoundError)):
        maintenance.read_bundle(bundle)


def test_proposal_is_repeatable_complete_and_does_not_apply_or_execute_upstream(
    tools, bundle, upstream, tmp_path, monkeypatch,
):
    maintenance, _ = tools
    calls, real_git = [], maintenance.git

    def read_objects(source, *args):
        calls.append(args[0])
        assert args[0] in {"rev-parse", "ls-tree", "cat-file"}
        return real_git(source, *args)

    monkeypatch.setattr(maintenance, "git", read_objects)
    marker = tmp_path / "must-not-exist"
    script = upstream / "skills/select-sqd-eigensolver/scripts/new-helper.py"
    script.write_text(f"from pathlib import Path\nPath({str(marker)!r}).touch()\n")
    script.chmod(0o755)
    nested = upstream / "skills/select-sqd-eigensolver/data/deep/reference.bin"
    nested.parent.mkdir(parents=True)
    nested.write_bytes(b"\0\xfffull resource\n")
    (upstream / "NOTICE").write_text("Synthetic contributor notice\n")
    removed = upstream / "skills/select-sqd-eigensolver/capabilities-table.md"
    removed.unlink()
    revision = commit(upstream)
    # A dirty checkout must not leak into a proposal pinned to committed objects.
    nested.write_bytes(b"uncommitted replacement")
    before, source_before = snapshot(bundle), snapshot(upstream)
    first, second = tmp_path / "first", tmp_path / "second"
    report = maintenance.propose(bundle, upstream, revision, first)
    assert maintenance.propose(bundle, upstream, revision, second) == report
    assert snapshot(first) == snapshot(second)
    assert snapshot(bundle) == before
    assert snapshot(upstream) == source_before
    assert not marker.exists()
    manifest = maintenance.read_bundle(first)
    assert manifest["revision"] == revision
    assert report["review_only"] is True
    assert report["agent_behavior_evaluation"] == "not_run"
    assert report["attribution_review_required"] is True
    assert ".agents/skills/select-sqd-eigensolver/capabilities-table.md" in report["removed"]
    resource = ".agents/skills/select-sqd-eigensolver/data/deep/reference.bin"
    assert resource in report["added"]
    assert (first / resource).read_bytes() == b"\0\xfffull resource\n"
    helper = ".agents/skills/select-sqd-eigensolver/scripts/new-helper.py"
    assert manifest["files"][helper]["git_mode"] == "100755"
    assert (first / helper).stat().st_mode & 0o111
    assert (first / ".agents/skills/QISKIT-SKILLS-UPSTREAM-NOTICE").read_text() == "Synthetic contributor notice\n"
    assert (first / maintenance.NOTICE).read_text().count(revision) == 1
    assert set(calls) == {"rev-parse", "ls-tree", "cat-file"}
    for metadata in manifest["files"].values():
        assert len(metadata["sha256"]) == 64
        assert git(upstream, "rev-parse", f"{revision}:{metadata['upstream_path']}") == metadata["git_blob_sha1"]


def test_same_content_revision_is_a_valid_review_proposal_without_update(tools, bundle, upstream, tmp_path):
    maintenance, _ = tools
    report = maintenance.propose(bundle, upstream, git(upstream, "rev-parse", "HEAD"), tmp_path / "same")
    assert report["added"] == report["removed"] == report["changed"] == []
    assert report["license_review_required"] is False
    assert maintenance.read_bundle(bundle)["revision"] != report["to_revision"]


def test_license_changes_are_preserved_but_require_explicit_review(tools, bundle, upstream, tmp_path):
    maintenance, _ = tools
    (upstream / "LICENSE.txt").write_text("Synthetic changed licensing terms\n")
    revision = commit(upstream)
    output = tmp_path / "license-proposal"
    report = maintenance.propose(bundle, upstream, revision, output)
    assert report["license_review_required"] is True
    assert maintenance.read_bundle(output)["license"] == "REVIEW-REQUIRED"
    assert (output / ".agents/skills/QISKIT-SKILLS-LICENSE.txt").read_text() == "Synthetic changed licensing terms\n"
    assert maintenance.read_bundle(bundle)["license"] == "Apache-2.0"


def test_additional_nested_license_is_preserved_and_flagged(tools, bundle, upstream, tmp_path):
    maintenance, _ = tools
    (upstream / "skills/select-sqd-eigensolver/LICENSE-extra").write_text("Synthetic extra terms\n")
    output = tmp_path / "additional-license"
    report = maintenance.propose(bundle, upstream, commit(upstream), output)
    assert report["license_review_required"] is True
    assert report["attribution_review_required"] is True
    assert (output / ".agents/skills/select-sqd-eigensolver/LICENSE-extra").read_text() == "Synthetic extra terms\n"


def test_root_license_directories_are_copied_completely_not_silently_omitted(tools, bundle, upstream, tmp_path):
    maintenance, _ = tools
    legal = upstream / "LICENSES/third-party/terms.txt"
    legal.parent.mkdir(parents=True)
    legal.write_bytes(b"Complete synthetic third-party licensing terms\n")
    output = tmp_path / "root-licenses"
    report = maintenance.propose(bundle, upstream, commit(upstream), output)
    local = ".agents/skills/QISKIT-SKILLS-UPSTREAM-LICENSES/third-party/terms.txt"
    assert (output / local).read_bytes() == legal.read_bytes()
    assert report["license_review_required"] is True
    assert maintenance.read_bundle(output)["files"][local]["upstream_path"] == "LICENSES/third-party/terms.txt"


def test_maintenance_cli_emits_verified_review_only_proposal(tools, bundle, upstream, tmp_path, capsys):
    maintenance, _ = tools
    output = tmp_path / "cli"
    assert maintenance.main([
        "--root", str(bundle), "propose", "--source", str(upstream),
        "--revision", git(upstream, "rev-parse", "HEAD"), "--output", str(output),
    ]) == 0
    assert json.loads(capsys.readouterr().out)["review_only"] is True
    assert maintenance.main(["--root", str(output), "verify"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["agent_behavior"] == "not_evaluated"
    assert result["files"] == 35


@pytest.mark.parametrize("damage", ["entry", "license", "symlink", "notice"])
def test_incomplete_or_unsupported_upstream_leaves_no_proposal(tools, bundle, upstream, tmp_path, damage):
    maintenance, _ = tools
    if damage == "entry":
        (upstream / "skills/select-sqd-eigensolver/SKILL.md").unlink()
    elif damage == "license":
        (upstream / "LICENSE.txt").unlink()
    elif damage == "symlink":
        (upstream / "skills/select-sqd-eigensolver/unsafe").symlink_to("/outside")
    else:
        manifest = bundle / maintenance.MANIFEST
        data = json.loads(manifest.read_text())
        notice = bundle / ".agents/skills/QISKIT-SKILLS-UPSTREAM-NOTICE"
        notice.write_bytes(b"Required attribution")
        data["files"][notice.relative_to(bundle).as_posix()] = {
            "upstream_path": "NOTICE", "git_blob_sha1": maintenance.blob_hash(notice.read_bytes()),
        }
        manifest.write_text(json.dumps(data))
    revision = git(upstream, "rev-parse", "HEAD") if damage == "notice" else commit(upstream)
    output = tmp_path / "incomplete"
    before = snapshot(bundle)
    with pytest.raises(ValueError):
        maintenance.propose(bundle, upstream, revision, output)
    assert not output.exists()
    assert snapshot(bundle) == before


def test_output_created_during_preparation_is_not_overwritten(tools, bundle, upstream, tmp_path, monkeypatch):
    maintenance, _ = tools
    output = tmp_path / "raced-output"
    real_read = maintenance.read_bundle

    def validate(root):
        result = real_read(root)
        if root != bundle:
            output.mkdir()
            (output / "owner.txt").write_text("Preserve concurrent output")
        return result

    monkeypatch.setattr(maintenance, "read_bundle", validate)
    with pytest.raises(FileExistsError):
        maintenance.propose(bundle, upstream, git(upstream, "rev-parse", "HEAD"), output)
    assert snapshot(output) == {"owner.txt": b"Preserve concurrent output"}


def test_failed_resource_write_leaves_inputs_and_output_unchanged(tools, bundle, upstream, tmp_path, monkeypatch):
    maintenance, _ = tools
    original = Path.write_bytes
    before = snapshot(bundle)

    def fail(path, content):
        if ".qiskit-skills-" in str(path):
            raise OSError("Synthetic storage failure")
        return original(path, content)

    monkeypatch.setattr(Path, "write_bytes", fail)
    output = tmp_path / "write-failure"
    with pytest.raises(OSError, match="Synthetic"):
        maintenance.propose(bundle, upstream, git(upstream, "rev-parse", "HEAD"), output)
    assert not output.exists()
    assert snapshot(bundle) == before


def test_failed_promotion_removes_only_its_own_empty_reservation(tools, bundle, upstream, tmp_path, monkeypatch):
    maintenance, _ = tools
    output = tmp_path / "promotion-failure"
    before = snapshot(bundle)

    def fail(path, target):
        assert target == output
        raise OSError("Synthetic rename failure")

    monkeypatch.setattr(Path, "rename", fail)
    with pytest.raises(OSError, match="Synthetic rename"):
        maintenance.propose(bundle, upstream, git(upstream, "rev-parse", "HEAD"), output)
    assert not output.exists()
    assert snapshot(bundle) == before


def test_tag_object_and_corrupted_object_are_not_accepted(tools, bundle, upstream, tmp_path, monkeypatch):
    maintenance, _ = tools
    git(upstream, "-c", "user.name=Offline Fixture", "-c", "user.email=fixture@example.invalid",
        "tag", "-a", "fixture", "-m", "Annotated tag fixture")
    with pytest.raises(ValueError, match="commit"):
        maintenance.propose(bundle, upstream, git(upstream, "rev-parse", "fixture"), tmp_path / "tag")
    real_git = maintenance.git

    def corrupted(source, *args):
        return b"corrupted object bytes" if args[0] == "cat-file" else real_git(source, *args)

    monkeypatch.setattr(maintenance, "git", corrupted)
    output = tmp_path / "corrupted"
    with pytest.raises(ValueError, match="object hash"):
        maintenance.propose(bundle, upstream, git(upstream, "rev-parse", "HEAD"), output)
    assert not output.exists()


def test_check_cli_reports_only_deterministic_integration(tools, capsys):
    assert tools[1].main(["--check"]) == 0
    assert json.loads(capsys.readouterr().out)["agent_behavior_evaluations_run"] == 0


@pytest.mark.parametrize("destination", ["project", "upstream", "parent", "existing"])
def test_proposal_never_overwrites_checkouts_or_existing_output(tools, bundle, upstream, tmp_path, destination):
    maintenance, _ = tools
    paths = {"project": bundle / "new", "upstream": upstream / "new", "parent": tmp_path,
             "existing": tmp_path / "existing"}
    if destination == "existing":
        paths[destination].mkdir()
        (paths[destination] / "owner.txt").write_text("Keep me")
    before = snapshot(tmp_path)
    with pytest.raises(ValueError):
        maintenance.propose(bundle, upstream, git(upstream, "rev-parse", "HEAD"), paths[destination])
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("revision", ["HEAD", "main", "--all", "a" * 39, "A" * 40])
def test_revision_must_be_explicit_full_commit(tools, bundle, upstream, tmp_path, revision):
    with pytest.raises(ValueError):
        tools[0].propose(bundle, upstream, revision, tmp_path / "bad-revision")


def test_candidate_sha256_and_modes_are_verified(tools, bundle, upstream, tmp_path):
    maintenance, _ = tools
    output = tmp_path / "candidate"
    maintenance.propose(bundle, upstream, git(upstream, "rev-parse", "HEAD"), output)
    manifest_path = output / maintenance.MANIFEST
    data = json.loads(manifest_path.read_text())
    entry = next(iter(data["files"].values()))
    original = entry["sha256"]
    entry["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="SHA-256"):
        maintenance.read_bundle(output)
    entry["sha256"] = original
    entry["git_mode"] = "100755"
    manifest_path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="mode"):
        maintenance.read_bundle(output)


def test_actual_tracked_export_includes_cases_tools_and_every_resource(tools, tmp_path):
    maintenance, evaluations = tools
    deploy = load_script("deploy")
    destination = tmp_path / "export"
    destination.mkdir()
    deploy.copy_tracked(destination)
    assert maintenance.read_bundle(destination) == maintenance.read_bundle(ROOT)
    assert evaluations.check_cases(destination) == evaluations.check_cases(ROOT)
    for relative in ("scripts/dam/qiskit_skills.py", "scripts/dam/skill_evaluations.py", "docs/skills.md"):
        assert (destination / relative).read_bytes() == (ROOT / relative).read_bytes()


def test_sdist_contains_the_evaluation_and_maintenance_workflow(tmp_path):
    # Build once from the actual tracked source, not a hand-built file list.
    subprocess.run(["uv", "build", "--sdist", "--out-dir", str(tmp_path)], cwd=ROOT,
                   check=True, capture_output=True)
    archive, = tmp_path.glob("*.tar.gz")
    with tarfile.open(archive) as package:
        members = {name.split("/", 1)[1] for name in package.getnames() if "/" in name}
    assert {"evals/skills/cases.json", "docs/skills.md", "scripts/dam/qiskit_skills.py",
            "scripts/dam/skill_evaluations.py"} <= members
    manifest = json.loads((ROOT / ".agents/qiskit-skills.json").read_text())
    assert set(manifest["files"]) <= members
