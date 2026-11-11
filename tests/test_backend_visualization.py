"""Public backend dashboards with synthetic calibration and no IBM connection."""
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import pytest
from matplotlib.figure import Figure
from matplotlib.text import Text
from qiskit.transpiler import CouplingMap

from qiskit_lab import backend_visualization as visualization
from qiskit_lab import cli


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    service = Mock(side_effect=AssertionError("No real IBM service"))
    sampler = Mock(side_effect=AssertionError("Backend inspection must not submit jobs"))
    monkeypatch.setattr(cli, "QiskitRuntimeService", service)
    monkeypatch.setattr(cli, "SamplerV2", sampler)
    monkeypatch.setattr(cli, "runtime_service", service)
    yield
    service.assert_not_called()
    sampler.assert_not_called()


def backend(*, operational=True, qubits=4):
    def parameter(name, value):
        return SimpleNamespace(name=name, value=value)

    properties = SimpleNamespace(
        qubits=[[parameter("readout_error", value), parameter("T1", 100), parameter("T2", 80)]
                for value in (0.01, 0.02, 0.03, 0.04)],
        gates=[SimpleNamespace(qubits=[0, 1], parameters=[parameter("gate_error", 0.005)]),
               SimpleNamespace(qubits=[1], parameters=[parameter("gate_error", 0.9)])],
        last_update_date=datetime(2026, 1, 2, 3, 4, tzinfo=timezone.utc),
    )
    return SimpleNamespace(
        name="../../ibm synthetic", num_qubits=qubits, operation_names=["x", "cx", "measure"],
        coupling_map=CouplingMap.from_line(qubits),
        status=lambda: SimpleNamespace(operational=operational, pending_jobs=7, status_msg="synthetic"),
        properties=Mock(return_value=properties),
    )


@pytest.mark.parametrize("calibration,operational,qubits", [
    ("complete", True, 4), ("empty", False, 4), ("missing", True, 33), ("error", False, 4),
])
def test_backend_png_has_real_topology_health_and_available_calibration(
    monkeypatch, tmp_path, calibration, operational, qubits,
):
    device = backend(operational=operational, qubits=qubits)
    if calibration == "empty":
        device.properties.return_value = SimpleNamespace(qubits=[], gates=[])
    elif calibration == "missing":
        device.properties.return_value = None
    elif calibration == "error":
        device.properties.side_effect = RuntimeError("private SDK details")
    monkeypatch.setattr(visualization.tempfile, "gettempdir", lambda: str(tmp_path))
    save = Figure.savefig
    labels = []

    def capture(figure, *args, **kwargs):
        labels.extend(item.get_text() for item in figure.findobj(Text))
        return save(figure, *args, **kwargs)

    monkeypatch.setattr(Figure, "savefig", capture)
    before = plt.get_fignums()
    path = Path(visualization.render_backend_dashboard(device))
    assert path.parent == tmp_path / "quantum_lab_pngs"
    assert path.name.startswith("______ibm_synthetic_backend_")
    assert path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    pixels = mpimg.imread(path)
    assert pixels.shape[0] > 900 and pixels.shape[1] > 1600
    assert pixels[:, :, :3].std() > 0.05
    assert device.name in labels
    assert "Connectivity topology" in labels
    assert "Readout assignment error" in labels
    assert "7" in labels
    assert str(qubits) in labels
    health, = [label for label in labels if "OPERATIONAL" in label]
    assert health == ("\u25cf OPERATIONAL" if operational else "\u25cf NOT OPERATIONAL")
    if calibration == "complete":
        for value in ("0.0250", "0.0050", "100.0", "80.0", "Calibration: 2026-01-02T03:04+00:00"):
            assert any(value in label for label in labels)
    else:
        assert labels.count("N/A") == 4
        assert "Calibration: Unavailable" in labels
    assert "private SDK details" not in "\n".join(labels)
    assert plt.get_fignums() == before


@pytest.mark.parametrize("coupling", [None, CouplingMap()])
def test_missing_connectivity_is_explicit_without_creating_an_image(monkeypatch, tmp_path, coupling):
    device = backend()
    device.coupling_map = coupling
    monkeypatch.setattr(visualization.tempfile, "gettempdir", lambda: str(tmp_path))
    before = plt.get_fignums()
    with pytest.raises(ValueError, match="coupling map"):
        visualization.render_backend_dashboard(device)
    assert not list(tmp_path.rglob("*.png"))
    assert plt.get_fignums() == before


@pytest.mark.parametrize("dashboard", [False, True])
def test_backend_cli_returns_saved_artifacts_only_when_requested(monkeypatch, tmp_path, capsys, dashboard):
    device = backend()
    service = Mock()
    service.backend.return_value = device
    monkeypatch.setattr(cli, "runtime_service", lambda: service)
    monkeypatch.setattr(visualization.tempfile, "gettempdir", lambda: str(tmp_path / "temporary"))
    output = tmp_path / "artifacts"
    options = ["--dashboard"] if dashboard else []
    assert cli.main(["backend", "synthetic", "--output-dir", str(output), *options]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["operations"] == ["cx", "measure", "x"]
    assert result["qubits"] == 4 and result["pending_jobs"] == 7
    assert result["coupling_map"] == [list(edge) for edge in device.coupling_map.get_edges()]
    assert datetime.fromisoformat(result["queried_at"])
    service.backend.assert_called_once_with("synthetic")
    if dashboard:
        image = Path(result["dashboard_path"])
        assert image.name == "backend.png" and image.is_file()
        assert image.read_bytes().startswith(b"\x89PNG")
        assert json.loads((image.parent / "backend.json").read_text()) == result
        assert not list((tmp_path / "temporary").rglob("*.png"))
    else:
        assert "dashboard_path" not in result
        assert not output.exists()
        device.properties.assert_not_called()
