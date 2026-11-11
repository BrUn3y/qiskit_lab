"""The browser smoke uses the native renderer and inspectable synthetic data."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_browser_fixture_command_is_local_and_produces_complete_native_reports(tmp_path):
    script = """
import runpy, sys
import qiskit_ibm_runtime
def forbidden(*args, **kwargs):
    raise AssertionError("Synthetic fixtures must never construct an IBM service or sampler")
qiskit_ibm_runtime.QiskitRuntimeService = qiskit_ibm_runtime.SamplerV2 = forbidden
sys.argv = [sys.argv[1], "--output-dir", sys.argv[2]]
runpy.run_path(sys.argv[0], run_name="__main__")
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(ROOT / "tools/report-assets/create-fixtures.py"), str(tmp_path)],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"fixtures": str(tmp_path), "synthetic": True}
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["data"]["hardware"] is False
    assert len(manifest["data"]["counts"][0]) == 64
    assert len(manifest["data"]["counts"]) == 2
    assert Path(manifest["interactive"]).is_relative_to(tmp_path)
    html = Path(manifest["interactive"]).read_text()
    assert html.count("data-publication=") == 2
    assert "data:image/png;base64," in html
    assert "Synthetic report regression fixture" in html
    for status in ("ERROR", "CANCELLED"):
        html = Path(manifest[status]).read_text()
        assert "No measurement results" in html
        assert "data-publication=" not in html
