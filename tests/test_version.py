"""Keep release metadata consistent with the public package version."""
import importlib.metadata
import tomllib
from pathlib import Path

from qiskit_lab import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_package_version_matches_manifest_and_installed_metadata():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    assert project["version"] == __version__
    assert importlib.metadata.version(project["name"]) == __version__
