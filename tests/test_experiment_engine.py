"""Scientific contracts for sampled QAOA solutions and classical validation."""
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from qiskit_lab import experiment_engine as engine


@pytest.mark.parametrize("observed,expected", [
    ({"00000": 1}, "00000"),
    ({"00001": 3, "00101": 1}, "00101"),
    ({"00101": 1, "01010": 2}, "01010"),
    ({"00101": 2, "01010": 2}, "00101"),
])
def test_best_solution_is_sampled_and_ranked_by_cut_then_frequency(observed, expected, monkeypatch, tmp_path):
    sampled = np.zeros(32, dtype=int)
    for state, count in observed.items():
        sampled[int(state, 2)] = count
    # Force a finite-shot outcome, including one that misses every exact optimum.
    monkeypatch.setattr(engine.np.random, "default_rng",
                        lambda seed: SimpleNamespace(multinomial=lambda shots, probabilities: sampled))
    dashboard = Mock(return_value=tmp_path / "unused.png")
    monkeypatch.setattr(engine, "_render_dashboard", dashboard)
    result = engine.run_maxcut_qaoa("5 nodes", shots=sum(observed.values()))
    assert result.counts == observed
    assert result.best_bitstring == expected
    assert result.best_bitstring in result.counts
    assert result.best_cut == engine.cut_value(int(expected, 2), result.edges)
    assert result.exact_cut == 4
    assert result.approximation_ratio == result.expected_cut / result.exact_cut
    assert dashboard.call_args.kwargs["best_bitstring"] == expected


@pytest.mark.parametrize("shots", [0, -1])
def test_qaoa_requires_an_observed_sample(shots):
    with pytest.raises(ValueError, match="at least one shot"):
        engine.run_maxcut_qaoa("5 nodes", shots=shots)


@pytest.mark.parametrize("description,expected", [
    ("4-node (3,0) (0,3) (2,1) (1,1)", (4, ((0, 3), (1, 2)))),
    ("2-node", (2, ((0, 1),))),
    ("3-node", (3, ((0, 1), (1, 2), (2, 0)))),
])
def test_graph_edges_remain_normalized_deduplicated_and_deterministic(description, expected):
    assert engine.parse_maxcut_graph(description) == expected


def test_graph_edges_outside_the_declared_nodes_are_rejected():
    with pytest.raises(ValueError, match="between 0 and 3"):
        engine.parse_maxcut_graph("4-node (0,4)")
