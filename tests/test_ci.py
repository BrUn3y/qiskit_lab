"""Keep the CI interpreter matrix aligned with declared Python support."""
import json
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


def test_browser_smoke_is_separate_pinned_and_does_not_replace_tracking_coverage():
    workflow = yaml.safe_load((ROOT / ".github/workflows/container.yml").read_text())
    browser = workflow["jobs"]["report-browser"]
    assert browser["timeout-minutes"] == 10
    assert "strategy" not in browser
    assert not browser.get("continue-on-error")
    assert all(not step.get("continue-on-error") for step in browser["steps"])
    commands = [step.get("run", "") for step in browser["steps"]]
    assert "uv run --locked python tools/report-assets/create-fixtures.py" in commands
    assert "npm run test:browser" in commands
    assert any("playwright install --with-deps chromium" in command for command in commands)
    package = json.loads((ROOT / "tools/report-assets/package.json").read_text())
    lock = json.loads((ROOT / "tools/report-assets/package-lock.json").read_text())
    version = package["devDependencies"]["@playwright/test"]
    assert lock["packages"]["node_modules/@playwright/test"]["version"] == version
    native = yaml.safe_load((ROOT / ".github/workflows/dam.yml").read_text())["jobs"]["native-dam"]
    assert any(step.get("run") == "uv run --locked coverage report --include='*/job_tracking.py' --fail-under=100"
               for step in native["steps"])
