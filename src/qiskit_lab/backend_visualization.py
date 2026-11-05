"""Generate a visual IBM Quantum backend summary without Graphviz."""

from __future__ import annotations

import os
import re
import statistics
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import rustworkx as rx
from matplotlib.colors import Normalize


def _qubit_values(properties, name: str) -> list[float]:
    return [
        float(parameter.value)
        for qubit in (getattr(properties, "qubits", []) or [])
        for parameter in qubit
        if getattr(parameter, "name", "") == name
    ]


def _two_qubit_errors(properties) -> list[float]:
    return [
        float(parameter.value)
        for gate in (getattr(properties, "gates", []) or [])
        if len(getattr(gate, "qubits", [])) == 2
        for parameter in (getattr(gate, "parameters", []) or [])
        if getattr(parameter, "name", "") == "gate_error"
    ]


def _median(values: list[float], suffix: str = "", precision: int = 3) -> str:
    return f"{statistics.median(values):.{precision}f}{suffix}" if values else "N/A"


def render_backend_dashboard(backend) -> str:
    """Render topology, readout error, and current health to a temporary PNG."""
    status = backend.status()
    try:
        properties = backend.properties()
    except Exception:
        properties = None

    coupling_map = getattr(backend, "coupling_map", None)
    if coupling_map is None:
        raise ValueError(f"Backend {backend.name} does not expose a coupling map")

    graph = coupling_map.graph.to_undirected(multigraph=False)
    if not graph.edge_list():
        raise ValueError(f"Backend {backend.name} does not expose a coupling map")
    positions = rx.spring_layout(graph, seed=42, num_iter=250)
    nodes = list(graph.node_indices())
    readout_errors = _qubit_values(properties, "readout_error")
    node_errors = [readout_errors[index] if index < len(readout_errors) else 0.0 for index in nodes]

    figure = plt.figure(figsize=(16, 9), facecolor="#161616")
    grid = figure.add_gridspec(1, 2, width_ratios=(0.30, 0.70), wspace=0.04)
    summary = figure.add_subplot(grid[0, 0])
    topology = figure.add_subplot(grid[0, 1])
    for axis in (summary, topology):
        axis.set_facecolor("#161616")
        axis.axis("off")

    operational = bool(getattr(status, "operational", False))
    summary.text(0.04, 0.94, "IBM QUANTUM", color="#78a9ff", fontsize=11, fontweight="bold")
    summary.text(0.04, 0.87, backend.name, color="#f4f4f4", fontsize=25, fontweight="bold")
    summary.text(
        0.04,
        0.81,
        "● OPERATIONAL" if operational else "● NOT OPERATIONAL",
        color="#42be65" if operational else "#fa4d56",
        fontsize=12,
        fontweight="bold",
    )

    metrics = (
        ("Qubits", f"{getattr(backend, 'num_qubits', len(nodes)):,}"),
        ("Jobs in queue", f"{getattr(status, 'pending_jobs', 0):,}"),
        ("Couplings", f"{len(graph.edge_list()):,}"),
        ("Median readout error", _median(readout_errors, precision=4)),
        ("Median 2-qubit error", _median(_two_qubit_errors(properties), precision=4)),
        ("Median T1", _median(_qubit_values(properties, "T1"), " μs", 1)),
        ("Median T2", _median(_qubit_values(properties, "T2"), " μs", 1)),
    )
    vertical_position = 0.71
    for label, value in metrics:
        summary.text(0.04, vertical_position, label.upper(), color="#8d8d8d", fontsize=9, fontweight="bold")
        summary.text(0.04, vertical_position - 0.045, value, color="#f4f4f4", fontsize=17)
        vertical_position -= 0.09

    calibration = getattr(properties, "last_update_date", None)
    calibration_text = calibration.isoformat(timespec="minutes") if calibration else "Unavailable"
    summary.text(0.04, 0.045, f"Calibration: {calibration_text}", color="#8d8d8d", fontsize=8)

    for source, target in graph.edge_list():
        source_x, source_y = positions[source]
        target_x, target_y = positions[target]
        topology.plot(
            [source_x, target_x],
            [source_y, target_y],
            color="#525252",
            linewidth=1.15,
            alpha=0.9,
            zorder=1,
        )

    maximum_error = max(node_errors, default=1.0) or 1.0
    scatter = topology.scatter(
        [positions[index][0] for index in nodes],
        [positions[index][1] for index in nodes],
        s=55 if len(nodes) < 80 else 36,
        c=node_errors,
        cmap="coolwarm",
        norm=Normalize(vmin=0, vmax=maximum_error),
        edgecolors="#d0e2ff",
        linewidths=0.55,
        zorder=2,
    )
    if len(nodes) <= 32:
        for index in nodes:
            x_position, y_position = positions[index]
            topology.text(
                x_position,
                y_position,
                str(index),
                color="#f4f4f4",
                fontsize=6,
                ha="center",
                va="center",
            )

    topology.set_title("Connectivity topology", color="#f4f4f4", fontsize=18, loc="left", pad=18)
    color_bar = figure.colorbar(scatter, ax=topology, orientation="horizontal", fraction=0.04, pad=0.04, aspect=45)
    color_bar.set_label("Readout assignment error", color="#c6c6c6", fontsize=9)
    color_bar.ax.tick_params(colors="#8d8d8d", labelsize=8)
    color_bar.outline.set_edgecolor("#525252")

    queried_at = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    figure.text(0.985, 0.018, f"Queried locally • {queried_at}", color="#6f6f6f", fontsize=8, ha="right")

    output_directory = Path(tempfile.gettempdir()) / "quantum_lab_pngs"
    output_directory.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", backend.name)
    output_path = output_directory / f"{safe_name}_backend_{uuid.uuid4().hex[:8]}.png"
    figure.savefig(output_path, dpi=135, bbox_inches="tight", facecolor=figure.get_facecolor())
    plt.close(figure)
    return os.fspath(output_path)

