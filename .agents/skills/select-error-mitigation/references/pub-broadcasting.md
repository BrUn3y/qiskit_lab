# PUB broadcasting for Estimator scaffolds

Read this when a code scaffold combines several observables with several parameter points in one Estimator PUB.

Coerce the actual PUB, `qiskit.primitives.containers.EstimatorPub.coerce((circuit, observables, params))`, and confirm the resulting `.shape` is what you claim.

- **Parameter axis.** A `BindingsArray` built from a `parameter_values` array of shape `(k, 1)` has broadcast shape `(k,)`. The trailing axis is the parameter count, not a broadcast axis.
- **Mismatched shapes.** Because of that, an observable array of shape `(m,)` does not broadcast against `(k,)` parameters.
  - For a `(k, m)` result from `m` observables and `k` parameter points, reshape the parameters to `(k, 1, 1)`.
  - Alternatively, give the observables shape `(m, 1)` to get an `(m, k)` result.
- **Building observable arrays.** For many-qubit observables, use `np.empty(m, dtype=object)` with element assignment, or a nested list such as `[[obs] for obs in observables]`. Don't use `np.array([...])`: it tries to turn each `SparsePauliOp` into a dense matrix and fails beyond about a dozen qubits.
- **Grouping commuting observables.** Putting mutually commuting observables (for example, all single-qubit ⟨Z⟩) into one PUB this way is the main structural optimization for a magnetization-style sweep. It replaces *m* single-observable PUBs with one.
