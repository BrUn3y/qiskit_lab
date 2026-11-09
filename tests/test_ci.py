"""Keep the CI interpreter matrix aligned with declared Python support."""
import tomllib
from pathlib import Path

import yaml
from packaging.specifiers import SpecifierSet

ROOT = Path(__file__).resolve().parents[1]


def test_ci_covers_all_declared_python_minor_versions():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    supported = SpecifierSet(project["project"]["requires-python"])
    workflow = yaml.safe_load((ROOT / ".github/workflows/dam.yml").read_text())
    job = workflow["jobs"]["native-dam"]
    versions = job["strategy"]["matrix"]["python-version"]
    expected = {f"3.{minor}" for minor in range(8, 20) if f"3.{minor}" in supported}
    assert set(versions) == expected
    assert len(versions) == len(expected)
    setup, = [step for step in job["steps"] if step.get("uses", "").startswith("astral-sh/setup-uv@")]
    assert setup["with"]["python-version"] == "${{ matrix.python-version }}"
    assert job["strategy"]["fail-fast"] is False
