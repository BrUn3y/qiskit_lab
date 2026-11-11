"""Offline diagnostics and optional-environment contracts; no optional imports."""
import importlib.metadata
import json
import tomllib
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml
from packaging.requirements import Requirement

from qiskit_lab import capabilities, cli

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def pinned(monkeypatch):
    versions = {name: version for profile in capabilities.PROFILES.values() for name, version in profile.items()}
    versions.update({"qiskit-ibm-runtime": "0.51.0", "numpy": "2.4.1"})

    def version(name):
        if name not in versions:
            raise importlib.metadata.PackageNotFoundError(name)
        return versions[name]

    monkeypatch.setattr(capabilities.importlib.metadata, "version", version)
    monkeypatch.setattr(capabilities.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(capabilities.platform, "libc_ver", lambda: ("glibc", "2.36"))
    monkeypatch.setattr(capabilities.sys, "platform", "linux")
    monkeypatch.setattr(capabilities.sys, "version_info", (3, 12, 0))
    return versions


def test_offline_doctor_does_not_probe_credentials_home_or_service(monkeypatch, pinned):
    def forbidden(*args, **kwargs):
        pytest.fail("Offline diagnostics attempted a credential, account, or IBM operation")

    args = cli.parser().parse_args(["doctor"])
    monkeypatch.setattr(cli.Path, "home", forbidden)
    monkeypatch.setattr(cli.os.environ, "get", forbidden)
    monkeypatch.setattr(cli, "runtime_service", forbidden)
    result = cli.doctor(args)
    assert result["credentials_in_environment"] is None
    assert result["saved_account_file_exists"] is None
    assert result["credential_check"] == "not_performed"
    assert "connected" not in result and "queried_at" not in result
    assert set(result["optional_capabilities"]) == set(capabilities.PROFILES)
    for profile in result["optional_capabilities"].values():
        assert profile["status"] == "installed"
        assert profile["check"] == "distribution_metadata_only"
        assert profile["runtime_verified"] is False


@pytest.mark.parametrize("profile", capabilities.PROFILES)
def test_requested_pinned_profile_passes_without_importing_optional_code(pinned, capsys, profile):
    assert cli.main(["doctor", "--capability", profile]) == 0
    result = json.loads(capsys.readouterr().out)
    assert list(result["optional_capabilities"]) == [profile]


@pytest.mark.parametrize("profile,package", [
    ("sqd", "pyscf"), ("sqd", "qiskit-addon-sqd"),
    ("fermionic", "qiskit-fermions"), ("fermionic-sim", "ffsim"),
])
def test_missing_requested_capability_is_actionable_but_default_doctor_succeeds(pinned, capsys, profile, package):
    del pinned[package]
    assert cli.main(["doctor", "--capability", profile]) == 1
    result = json.loads(capsys.readouterr().out)["optional_capabilities"][profile]
    assert result["status"] == "missing"
    assert result["packages"][package]["version"] is None
    assert "isolated" in result["next_step"]
    assert cli.main(["doctor"]) == 0


def test_multiple_requested_profiles_and_version_mismatch(pinned, capsys):
    pinned["ffsim"] = "0.0.1"
    assert cli.main(["doctor", "--capability", "fermionic", "--capability", "fermionic-sim"]) == 1
    result = json.loads(capsys.readouterr().out)["optional_capabilities"]
    assert result["fermionic"]["status"] == "installed"
    assert result["fermionic-sim"]["status"] == "version_mismatch"
    assert result["fermionic-sim"]["packages"]["ffsim"]["version"] == "0.0.1"


def test_metadata_failure_is_redacted(monkeypatch, pinned):
    original = capabilities.importlib.metadata.version

    def version(name):
        if name == "ffsim":
            raise ValueError("private-path-and-request-data")
        return original(name)

    monkeypatch.setattr(capabilities.importlib.metadata, "version", version)
    result = capabilities.optional_capabilities(["fermionic-sim"])
    assert result["fermionic-sim"]["status"] == "metadata_error"
    assert "private-path" not in json.dumps(result)


@pytest.mark.parametrize("system,machine,profile,supported", [
    ("linux", "x86_64", "sqd", True), ("linux", "aarch64", "fermionic-sim", True),
    ("linux", "i686", "sqd", False), ("darwin", "arm64", "fermionic-sim", True),
    ("darwin", "x86_64", "fermionic", True), ("darwin", "x86_64", "fermionic-sim", False),
    ("win32", "AMD64", "sqd", True), ("win32", "AMD64", "fermionic-sim", True),
    ("win32", "ARM64", "fermionic", False), ("freebsd", "x86_64", "sqd", False),
])
def test_wheel_recipe_targets(monkeypatch, pinned, system, machine, profile, supported):
    monkeypatch.setattr(capabilities.sys, "platform", system)
    monkeypatch.setattr(capabilities.platform, "machine", lambda: machine)
    result = capabilities.optional_capabilities([profile])[profile]
    assert result["recipe_platform_supported"] is supported
    assert result["status"] == ("installed" if supported else "unsupported_platform")


@pytest.mark.parametrize("libc,version", [("musl", "1.2"), ("glibc", "2.27"), ("", ""), ("glibc", "bad")])
def test_unsupported_linux_native_library_baseline(monkeypatch, pinned, libc, version):
    monkeypatch.setattr(capabilities.platform, "libc_ver", lambda: (libc, version))
    assert not capabilities.recipe_platform_supported("fermionic")


@pytest.mark.parametrize("version", [(3, 10), (3, 14)])
def test_unsupported_python_is_not_reported_ready(monkeypatch, pinned, version):
    monkeypatch.setattr(capabilities.sys, "version_info", version)
    assert capabilities.optional_capabilities(["sqd"])["sqd"]["status"] == "unsupported_platform"


def test_unknown_profile_is_a_parser_error():
    with pytest.raises(SystemExit) as error:
        cli.parser().parse_args(["doctor", "--capability", "all-solvers"])
    assert error.value.code == 2


def test_online_doctor_still_uses_only_explicit_mocked_service(monkeypatch, pinned):
    service = Mock()
    service.backends.return_value = [Mock(name="backend")]
    monkeypatch.setattr(cli, "runtime_service", lambda: service)
    monkeypatch.setattr(cli, "backend_summary", lambda backend: {"name": "synthetic"})
    result = cli.doctor(cli.parser().parse_args(["doctor", "--online"]))
    assert result["connected"] and result["queried_at"]
    service.backends.assert_called_once_with(simulator=False)
    service.backends.return_value = []
    with pytest.raises(cli.UserError, match="no hardware backends"):
        cli.doctor(cli.parser().parse_args(["doctor", "--online"]))


def test_optional_environment_matches_doctor_and_preserves_base_contract():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    optional = tomllib.loads((ROOT / "environments/optional/pyproject.toml").read_text())
    base_lock = tomllib.loads((ROOT / "uv.lock").read_text())
    lock = tomllib.loads((ROOT / "environments/optional/uv.lock").read_text())
    assert optional["project"]["requires-python"] == project["project"]["requires-python"]
    assert optional["tool"]["uv"]["sources"]["qiskit-lab"] == {"path": "../..", "editable": True}
    assert optional["tool"]["uv"]["package"] is False
    base_names = {item["name"] for item in base_lock["package"]}
    assert not base_names & {"qiskit-fermions", "ffsim", "pyscf", "qiskit-addon-sqd", "jax", "jaxlib"}
    assert "optional-dependencies" not in project["project"]
    locked = {item["name"]: item["version"] for item in lock["package"]}
    constraints = [Requirement(value) for value in optional["tool"]["uv"]["constraint-dependencies"]]
    base_versions = {item["name"]: item["version"] for item in base_lock["package"]}
    assert all(base_versions[item.name] in item.specifier for item in constraints)
    for profile, expected in capabilities.PROFILES.items():
        requirements = [Requirement(value) for value in optional["project"]["optional-dependencies"][profile]]
        requirements += [item for item in constraints if item.name == "qiskit"]
        assert {item.name: str(next(iter(item.specifier))).removeprefix("==") for item in requirements} == expected
        assert all(locked[name] == version for name, version in expected.items())
    assert set(optional["tool"]["uv"]["no-build-package"]) == {"qiskit-fermions", "ffsim", "pyscf", "jaxlib"}
    assert not set(locked) & {"sbd-eigensolver", "fulqrum", "primme", "qiskit-nature", "pyomo"}


def test_optional_ci_keeps_profile_and_python_isolation():
    workflow = yaml.safe_load((ROOT / ".github/workflows/optional.yml").read_text())
    job = workflow["jobs"]["optional"]
    assert set(job["strategy"]["matrix"]["profile"]) == set(capabilities.PROFILES)
    assert job["strategy"]["matrix"]["python-version"] == ["3.11", "3.12", "3.13"]
    assert job["strategy"]["fail-fast"] is False
    commands = [step["run"] for step in job["steps"] if "run" in step]
    assert all("--locked" in command and "--project environments/optional" in command
               and '--extra "${{ matrix.profile }}"' in command for command in commands)
    assert all("--offline" in command for command in commands if "uv run" in command)
    assert not any("doctor --online" in command for command in commands)
