"""Failure boundaries of actual renderers, rather than stubbed HTML writers."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import matplotlib.pyplot as plt
import pytest
from matplotlib.figure import Figure
from qiskit import QuantumCircuit
from qiskit.transpiler import CouplingMap

from qiskit_lab import backend_visualization, execution_visualization
from qiskit_lab.reports import write_report


@pytest.mark.parametrize("kind", ["backend", "execution"])
@pytest.mark.parametrize("failure", [OSError, KeyboardInterrupt])
@pytest.mark.parametrize("stage", ["directory", "save"])
def test_png_save_failure_or_interruption_releases_its_figure(monkeypatch, tmp_path, kind, failure, stage):
    module = backend_visualization if kind == "backend" else execution_visualization
    monkeypatch.setattr(module.tempfile, "gettempdir", lambda: str(tmp_path))
    error = failure("synthetic rendering interruption")
    if stage == "save":
        monkeypatch.setattr(Figure, "savefig", Mock(side_effect=error))
    else:
        monkeypatch.setattr(Path, "mkdir", Mock(side_effect=error))
    unrelated = plt.figure()
    before = plt.get_fignums()
    try:
        with pytest.raises(failure) as caught:
            if kind == "backend":
                device = SimpleNamespace(
                    name="synthetic", num_qubits=2, coupling_map=CouplingMap.from_line(2),
                    properties=lambda: None, status=lambda: SimpleNamespace(operational=True),
                )
                module.render_backend_dashboard(device)
            else:
                module.render_execution_dashboard(
                    QuantumCircuit(2), {"00": 3, "11": 1}, backend_name="synthetic", job_id="fixture", shots=4,
                )
        assert caught.value is error
        assert plt.get_fignums() == before
    finally:
        for number in set(plt.get_fignums()) - set(before):
            plt.close(number)
        plt.close(unrelated)


@pytest.mark.parametrize("failure", [OSError, KeyboardInterrupt])
def test_failed_html_promotion_preserves_the_previous_report_and_can_be_retried(monkeypatch, tmp_path, failure):
    data = {"status": "DONE", "hardware": False, "run_id": "fixture", "counts": {"0": 3, "1": 1}}
    path = write_report(data.copy(), tmp_path)
    original = path.read_bytes()
    promote = Path.replace
    error = failure("synthetic promotion failure")

    def fail(source, target):
        if Path(target) == path:
            raise error
        return promote(source, target)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "replace", fail)
        with pytest.raises(failure) as caught:
            write_report({**data, "counts": {"0": 1, "1": 3}}, tmp_path)
        assert caught.value is error
        assert path.read_bytes() == original
    assert write_report(data.copy(), tmp_path) == path
    assert "Measurement probabilities" in path.read_text()


def test_report_does_not_embed_or_download_symlinked_sources_or_images(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    directory = tmp_path / "report"
    directory.mkdir()
    for name in ("circuit.py", "circuit.qasm", "optimized.qasm", "isa-circuit.qasm", "circuit.txt", "results.png", "qaoa.png"):
        source = outside / name
        source.write_text("outside-private-content")
        (directory / name).symlink_to(source)
    html = write_report({"status": "DONE", "hardware": False}, directory).read_text()
    assert "outside-private-content" not in html
    assert "data:image/png" not in html
    assert html.count(' download=') == 1
    assert "No circuit was reconstructed" in html
