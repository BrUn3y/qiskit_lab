"""Exercise histogram pairing and circuit chunk boundaries without IBM access."""
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import pytest
from qiskit import QuantumCircuit

from qiskit_lab import execution_visualization as visualization


@pytest.mark.parametrize("operation_count,expected_chunks", [(0, [0]), (12, [12]), (13, [12, 1]), (37, [12, 12, 12])])
def test_dashboard_preserves_histogram_labels_and_circuit_chunks(
    monkeypatch, tmp_path, operation_count, expected_chunks,
):
    monkeypatch.setattr(visualization.tempfile, "gettempdir", lambda: str(tmp_path))
    circuit = QuantumCircuit(2)
    for _ in range(operation_count):
        circuit.x(0)
    counts = {"00": 3, "11": 5}
    figures_before = plt.get_fignums()
    chunks = []
    draw_circuit = visualization._draw_circuit

    def draw(ax, circuit, instructions):
        chunks.append(len(instructions))
        draw_circuit(ax, circuit, instructions)

    labels = []
    text = visualization.plt.Axes.text

    def record_text(ax, x, y, s, *args, **kwargs):
        if "\n" in str(s):
            labels.append((y, s))
        return text(ax, x, y, s, *args, **kwargs)

    monkeypatch.setattr(visualization, "_draw_circuit", draw)
    monkeypatch.setattr(visualization.plt.Axes, "text", record_text)
    path = visualization.render_execution_dashboard(
        circuit, counts, backend_name="local_simulator", job_id="local-test", shots=8,
    )
    assert path.parent == tmp_path / "quantum_lab_pngs"
    assert path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    pixels = mpimg.imread(path)
    assert pixels.shape == (1800, 2400, 4)
    assert pixels[:, :, :3].std() > 0.05
    assert labels == [(5, "5\n62.5%"), (3, "3\n37.5%")]
    assert chunks == expected_chunks
    assert plt.get_fignums() == figures_before
