"""Validate CHSH receipts and derive reported statistics from observed counts."""
from __future__ import annotations

import math

LABELS = ("ab", "ab'", "a'b", "a'b'")
BITSTRINGS = {"00", "01", "10", "11"}
UNCERTAINTY_ASSUMPTION = (
    "Approximate one-sigma shot-noise standard errors assume independent shots within and across configurations. "
    "They exclude hardware drift, readout bias and other systematic errors. "
    "The normal approximation can be unreliable for small samples or correlators near +1 or -1."
)


def prepare_chsh_report(data):
    """Recompute estimates without treating rounded or stale summary fields as data.

    Equal histograms can occur by chance. Flag them for sampling review rather than
    claiming that count data alone establish the independence of random streams.
    """
    if "correlators" not in data:
        return
    source = data["correlators"]
    if not isinstance(source, list) or len(source) != 4 or any(not isinstance(row, dict) for row in source):
        raise ValueError("CHSH reporting requires four measurement configurations.")
    labels = [row.get("label") for row in source]
    if any(label not in LABELS for label in labels) or len(set(labels)) != 4:
        raise ValueError("CHSH configurations must be labelled ab, ab', a'b and a'b'.")
    if data.get("noise_model") is not None and not isinstance(data["noise_model"], dict):
        raise ValueError("The recorded CHSH noise model must be a JSON object.")
    rows = []
    for label in LABELS:
        row = next(row for row in source if row["label"] == label).copy()
        counts = row.get("counts")
        if (not isinstance(counts, dict) or not counts or not set(counts) <= BITSTRINGS
                or any(type(value) is not int or value < 0 for value in counts.values())):
            raise ValueError("CHSH counts must contain two-bit binary keys and nonnegative integer counts.")
        shots = sum(counts.values())
        if not shots:
            raise ValueError("Each CHSH configuration requires observed shots.")
        sign = row.get("sign_in_chsh")
        if type(sign) is not int or sign not in {-1, 1}:
            raise ValueError("Each CHSH configuration requires a sign of +1 or -1.")
        for key in ("alice_angle_rad", "bob_angle_rad", "theory"):
            value = row.get(key)
            if value is not None and (type(value) not in {int, float} or not math.isfinite(value)):
                raise ValueError("CHSH angles and theoretical correlators must be finite numbers.")
        estimate = (counts.get("00", 0) + counts.get("11", 0)
                    - counts.get("01", 0) - counts.get("10", 0)) / shots
        row.update(shots=shots, correlator=estimate, uncertainty=math.sqrt((1 - estimate ** 2) / shots))
        rows.append(row)
    if math.prod(row["sign_in_chsh"] for row in rows) != -1:
        raise ValueError("A CHSH expression must have an odd number of negative signs.")
    repeated = any(
        all(row["counts"].get(key, 0) == other["counts"].get(key, 0) for key in BITSTRINGS)
        for index, row in enumerate(rows) for other in rows[index + 1:]
    )
    estimate = sum(row["sign_in_chsh"] * row["correlator"] for row in rows)
    warnings = []
    if repeated:
        warnings.append(
            "Some configurations have identical count histograms. This can occur by chance; verify that "
            "simulation seeds were not reset to the same value across configurations. The combined standard "
            "error is conditional on independent sampling; counts alone cannot verify independence."
        )
    data.update(
        correlators=rows,
        chsh_value=estimate,
        chsh_uncertainty=math.sqrt(sum(row["uncertainty"] ** 2 for row in rows)),
        chsh_uncertainty_assumption=UNCERTAINTY_ASSUMPTION,
        sampling_warnings=warnings,
        classical_bound=2.0,
        tsirelson_bound=2 * math.sqrt(2),
        violated=abs(estimate) > 2,
        observed_shots=sum(row["shots"] for row in rows),
        observed_shots_per_configuration=[row["shots"] for row in rows],
    )
