"""Deterministic QAOA Max-Cut experiments built with the Qiskit SDK."""

from __future__ import annotations

import math
import re
import tempfile
import uuid
from dataclasses import dataclass, replace
from pathlib import Path

import matplotlib
import numpy as np
from qiskit import QuantumCircuit
from qiskit.qasm3 import dumps as qasm3_dumps
from qiskit.quantum_info import Statevector

from qiskit_lab.errors import failure_context

matplotlib.use("Agg")
import matplotlib.pyplot as plt

_NODE_COUNT_PATTERN = re.compile(
    r"\b(\d+)\s*(?:-?node|nodos?|vertices|v[eé]rtices|qubits?)\b", re.IGNORECASE
)
_EDGE_PATTERN = re.compile(r"\(\s*(\d+)\s*[,;-]\s*(\d+)\s*\)")


@dataclass(frozen=True)
class QAOAExperimentResult:
    node_count: int
    edges: tuple[tuple[int, int], ...]
    gamma: float
    beta: float
    expected_cut: float
    exact_cut: int
    approximation_ratio: float
    best_bitstring: str
    best_cut: int
    counts: dict[str, int]
    optimization_trace: tuple[float, ...]
    qasm: str
    dashboard_path: Path | None = None
    dashboard_error: str | None = None


def parse_maxcut_graph(request: str) -> tuple[int, tuple[tuple[int, int], ...]]:
    """Parse a small graph or create a deterministic ring graph."""
    count_match = _NODE_COUNT_PATTERN.search(request)
    node_count = int(count_match.group(1)) if count_match else 5
    if not 2 <= node_count <= 8:
        raise ValueError("The development QAOA engine supports graphs from 2 to 8 nodes.")

    parsed_edges = {
        (min(int(left), int(right)), max(int(left), int(right)))
        for left, right in _EDGE_PATTERN.findall(request)
        if int(left) != int(right)
    }
    if parsed_edges:
        if any(node >= node_count for edge in parsed_edges for node in edge):
            raise ValueError(f"Every edge must reference nodes between 0 and {node_count - 1}.")
        edges = tuple(sorted(parsed_edges))
    elif node_count == 2:
        edges = ((0, 1),)
    else:
        edges = tuple((node, (node + 1) % node_count) for node in range(node_count))
    return node_count, edges


def cut_value(index: int, edges: tuple[tuple[int, int], ...]) -> int:
    return sum(((index >> left) & 1) != ((index >> right) & 1) for left, right in edges)


def _qaoa_circuit(
    node_count: int,
    edges: tuple[tuple[int, int], ...],
    gamma: float,
    beta: float,
    *,
    measurements: bool,
) -> QuantumCircuit:
    circuit = QuantumCircuit(node_count, node_count if measurements else 0)
    circuit.h(range(node_count))
    for left, right in edges:
        circuit.rzz(-gamma, left, right)
    for qubit in range(node_count):
        circuit.rx(2 * beta, qubit)
    if measurements:
        circuit.measure(range(node_count), range(node_count))
    return circuit


def _expectation(
    node_count: int,
    edges: tuple[tuple[int, int], ...],
    gamma: float,
    beta: float,
) -> tuple[float, np.ndarray]:
    state = Statevector.from_instruction(
        _qaoa_circuit(node_count, edges, gamma, beta, measurements=False)
    )
    probabilities = np.asarray(state.probabilities(), dtype=float)
    values = np.fromiter(
        (cut_value(index, edges) for index in range(2**node_count)),
        dtype=float,
        count=2**node_count,
    )
    return float(np.dot(probabilities, values)), probabilities


def _exact_solution(node_count: int, edges: tuple[tuple[int, int], ...]) -> tuple[int, str]:
    values = [cut_value(index, edges) for index in range(2**node_count)]
    best_index = max(range(len(values)), key=lambda index: (values[index], -index))
    return values[best_index], format(best_index, f"0{node_count}b")


def _render_dashboard(
    *,
    node_count: int,
    edges: tuple[tuple[int, int], ...],
    best_bitstring: str,
    counts: dict[str, int],
    expected_cut: float,
    exact_cut: int,
    approximation_ratio: float,
    trace: list[float],
) -> Path:
    figure = plt.figure(figsize=(16, 10), facecolor="#161616")
    grid = figure.add_gridspec(10, 12, left=0.05, right=0.97, top=0.90, bottom=0.08, hspace=1.15, wspace=1.1)
    graph_ax = figure.add_subplot(grid[2:9, :5])
    trace_ax = figure.add_subplot(grid[2:5, 6:])
    counts_ax = figure.add_subplot(grid[6:9, 6:])

    figure.text(0.05, 0.95, "HYBRID QUANTUM EXPERIMENT", color="#78a9ff", fontsize=11, weight="bold")
    figure.text(0.05, 0.905, "QAOA Max-Cut", color="#f4f4f4", fontsize=27, weight="bold")
    cards = (
        ("NODES", str(node_count)),
        ("EDGES", str(len(edges))),
        ("EXPECTED CUT", f"{expected_cut:.3f}"),
        ("EXACT CUT", str(exact_cut)),
        ("RATIO", f"{approximation_ratio:.1%}"),
    )
    for index, (label, value) in enumerate(cards):
        x = 0.42 + index * 0.115
        figure.text(x, 0.942, label, color="#8d8d8d", fontsize=8, weight="bold")
        figure.text(x, 0.905, value, color="#f4f4f4", fontsize=17)

    angles = np.linspace(0, 2 * math.pi, node_count, endpoint=False) + math.pi / 2
    positions = {node: (math.cos(angle), math.sin(angle)) for node, angle in enumerate(angles)}
    for left, right in edges:
        graph_ax.plot(
            [positions[left][0], positions[right][0]],
            [positions[left][1], positions[right][1]],
            color="#525252",
            linewidth=2.2,
            zorder=1,
        )
    for node, (x, y) in positions.items():
        bit = (int(best_bitstring, 2) >> node) & 1
        graph_ax.scatter(x, y, s=1150, color="#33b1ff" if bit == 0 else "#be95ff", edgecolors="#f4f4f4", linewidth=1.5, zorder=2)
        graph_ax.text(x, y, str(node), color="#161616", ha="center", va="center", fontsize=13, weight="bold", zorder=3)
    graph_ax.set_title(f"Best sampled partition  {best_bitstring}  •  cut {cut_value(int(best_bitstring, 2), edges)}", color="#f4f4f4", loc="left", pad=16)
    graph_ax.set_facecolor("#161616")
    graph_ax.set_aspect("equal")
    graph_ax.axis("off")

    trace_ax.plot(range(1, len(trace) + 1), trace, color="#42be65", linewidth=2)
    trace_ax.set_title("Grid-search convergence", color="#f4f4f4", loc="left")
    trace_ax.set_ylabel("Best expected cut", color="#c6c6c6")
    trace_ax.tick_params(colors="#a8a8a8")
    trace_ax.grid(color="#393939", linewidth=0.7)

    top_counts = sorted(counts.items(), key=lambda item: item[1], reverse=True)[:8]
    counts_ax.bar([state for state, _ in top_counts], [value for _, value in top_counts], color="#33b1ff")
    counts_ax.set_title("Top sampled solutions", color="#f4f4f4", loc="left")
    counts_ax.set_ylabel("Shots", color="#c6c6c6")
    counts_ax.tick_params(colors="#a8a8a8")
    counts_ax.grid(axis="y", color="#393939", linewidth=0.7)

    for axis in (trace_ax, counts_ax):
        axis.set_facecolor("#161616")
        for spine in axis.spines.values():
            spine.set_color("#525252")

    output_directory = Path(tempfile.gettempdir()) / "quantum_lab_pngs"
    output_directory.mkdir(parents=True, exist_ok=True)
    output_path = output_directory / f"qaoa_maxcut_{uuid.uuid4().hex[:8]}.png"
    figure.savefig(output_path, dpi=150, facecolor=figure.get_facecolor())
    plt.close(figure)
    return output_path


def render_qaoa_dashboard(result: QAOAExperimentResult) -> Path:
    """Render an already computed experiment without sampling or optimizing again."""
    with failure_context("rendering"):
        path = _render_dashboard(
            node_count=result.node_count,
            edges=result.edges,
            best_bitstring=result.best_bitstring,
            counts=result.counts,
            expected_cut=result.expected_cut,
            exact_cut=result.exact_cut,
            approximation_ratio=result.approximation_ratio,
            trace=list(result.optimization_trace),
        )
        if not path.is_file():
            raise FileNotFoundError("Dashboard renderer did not create a file.")
    return path


def run_maxcut_qaoa(
    request: str, *, shots: int = 1024, seed: int = 42, render_dashboard: bool = True,
) -> QAOAExperimentResult:
    """Optimize p=1 QAOA; callers saving receipts can defer presentation.

    The default still renders a dashboard, but a rendering failure returns the
    completed science with dashboard_error instead of discarding the result.
    """
    if shots < 1:
        raise ValueError("QAOA requires at least one shot.")
    with failure_context("local_input"):
        node_count, edges = parse_maxcut_graph(request)
    best_expectation = -1.0
    best_gamma = 0.0
    best_beta = 0.0
    best_probabilities: np.ndarray | None = None
    trace: list[float] = []

    for gamma in np.linspace(0.0, math.pi, 17):
        for beta in np.linspace(0.0, math.pi / 2, 13):
            expectation, probabilities = _expectation(node_count, edges, float(gamma), float(beta))
            if expectation > best_expectation:
                best_expectation = expectation
                best_gamma = float(gamma)
                best_beta = float(beta)
                best_probabilities = probabilities
            trace.append(best_expectation)

    assert best_probabilities is not None
    rng = np.random.default_rng(seed)
    sampled = rng.multinomial(shots, best_probabilities)
    counts = {
        format(index, f"0{node_count}b"): int(count)
        for index, count in enumerate(sampled)
        if count
    }
    # Rank observed solutions by cut, then frequency, then smallest bitstring.
    best_bitstring = max(
        counts,
        key=lambda state: (cut_value(int(state, 2), edges), counts[state], -int(state, 2)),
    )
    best_cut = cut_value(int(best_bitstring, 2), edges)
    exact_cut, _ = _exact_solution(node_count, edges)
    ratio = best_expectation / exact_cut if exact_cut else 1.0
    measured_circuit = _qaoa_circuit(node_count, edges, best_gamma, best_beta, measurements=True)
    from qiskit_lab.receipts import validate_counts

    validate_counts(counts)
    result = QAOAExperimentResult(
        node_count=node_count,
        edges=edges,
        gamma=best_gamma,
        beta=best_beta,
        expected_cut=best_expectation,
        exact_cut=exact_cut,
        approximation_ratio=ratio,
        best_bitstring=best_bitstring,
        best_cut=best_cut,
        counts=dict(sorted(counts.items(), key=lambda item: item[1], reverse=True)),
        optimization_trace=tuple(trace),
        qasm=qasm3_dumps(measured_circuit),
    )
    if not render_dashboard:
        return result
    try:
        return replace(result, dashboard_path=render_qaoa_dashboard(result))
    except Exception as error:  # noqa: BLE001 - Keep completed science available on presentation failure
        return replace(result, dashboard_error=type(error).__name__)
