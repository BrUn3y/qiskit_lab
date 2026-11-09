import importlib.metadata
import subprocess
import sys
import textwrap
import tomllib
from pathlib import Path

import pytest
import yaml
from packaging.requirements import Requirement
from packaging.version import Version
from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister, qasm2, qasm3

from qiskit_lab.comparison import comparison_metadata

ROOT = Path(__file__).resolve().parents[1]


def test_qasm3_importer_remains_a_required_runtime_dependency():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    requirements = {requirement.name: requirement for requirement in map(Requirement, project["dependencies"])}
    importer = requirements["qiskit-qasm3-import"]
    assert not importer.marker
    assert Version(importlib.metadata.version(importer.name)) in importer.specifier
    installed = {Requirement(value).name for value in importlib.metadata.requires("qiskit-lab")}
    assert importer.name in installed


@pytest.mark.parametrize("api", [qasm2, qasm3], ids=["qasm2", "qasm3"])
def test_qasm_roundtrip_preserves_separate_registers_and_identity(api, tmp_path):
    circuit = QuantumCircuit(QuantumRegister(2, "q"), ClassicalRegister(1, "a"), ClassicalRegister(1, "b"))
    circuit.h(0)
    circuit.cx(0, 1)
    circuit.measure(0, 0)
    circuit.measure(1, 1)
    path = tmp_path / "registers.qasm"
    with path.open("w") as stream:
        api.dump(circuit, stream)
    for rebuilt in (api.loads(path.read_text()), api.load(path)):
        assert rebuilt == circuit
        assert [(register.name, register.size) for register in rebuilt.cregs] == [("a", 1), ("b", 1)]
        assert comparison_metadata(rebuilt) == comparison_metadata(circuit)


def test_qasm3_public_loader_needs_importer_in_a_fresh_process():
    # A fresh interpreter avoids Qiskit's cached optional-dependency availability.
    probe = textwrap.dedent("""
        import importlib.abc
        import sys

        class WithoutImporter(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname == "qiskit_qasm3_import" or fullname.startswith("qiskit_qasm3_import."):
                    raise ModuleNotFoundError(fullname, name=fullname)
                return None

        sys.meta_path.insert(0, WithoutImporter())
        from qiskit import QuantumCircuit, qasm3
        from qiskit.exceptions import MissingOptionalLibraryError

        circuit = QuantumCircuit(1)
        circuit.h(0)
        source = qasm3.dumps(circuit)
        assert source.startswith("OPENQASM 3")
        try:
            qasm3.loads(source)
        except MissingOptionalLibraryError as error:
            assert "qiskit_qasm3_import" in str(error)
        else:
            raise AssertionError("QASM3 import unexpectedly worked without the importer")
    """)
    result = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


def test_dependabot_covers_lockfile_actions_and_container_without_major_updates():
    config = yaml.safe_load((ROOT / ".github/dependabot.yml").read_text())
    assert config["version"] == 2
    updates = {update["package-ecosystem"]: update for update in config["updates"]}
    assert set(updates) == {"uv", "docker", "npm", "github-actions"}
    for ecosystem, update in updates.items():
        assert update["directory"] == ("/tools/report-assets" if ecosystem == "npm" else "/")
        assert update["schedule"]["interval"] == "weekly"
        assert update["open-pull-requests-limit"] <= 3
        assert {"dependency-name": "*", "update-types": ["version-update:semver-major"]} in update["ignore"]
    for name in ("python", "ghcr.io/astral-sh/uv"):
        assert {"dependency-name": name, "update-types": ["version-update:semver-minor"]} in updates["docker"]["ignore"]


def test_uv_image_is_visible_to_docker_dependency_updates():
    lines = (ROOT / "Dockerfile").read_text().splitlines()
    uv_stage = next(line.split() for line in lines if line.startswith("FROM ghcr.io/astral-sh/uv:"))
    image = uv_stage[1]
    assert not Version(image.rsplit(":", 1)[1]).is_prerelease
    assert uv_stage[2:] == ["AS", "uv"]
    assert "COPY --from=uv /uv /usr/local/bin/uv" in lines
    assert "RUN uv sync --locked --no-dev --no-editable" in lines
