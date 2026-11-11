"""Validate CHSH receipts and derive reported statistics from observed counts."""
from __future__ import annotations

import math

LABELS = ("ab", "ab'", "a'b", "a'b'")
BITSTRINGS = {"00", "01", "10", "11"}
CONFIDENCE_LEVEL = 0.95
ANGLE_TOLERANCE_RAD = 1e-9
UNCERTAINTY_ASSUMPTION = (
    "Approximate one-sigma shot-noise standard errors assume independent shots within and across configurations. "
    "They exclude hardware drift, readout bias and other systematic errors. "
    "The normal approximation can be unreliable for small samples or correlators near +1 or -1."
)
CONFIDENCE_ASSUMPTION = (
    "Two-sided 95% Hoeffding confidence intervals are conservative finite-sample shot-noise bounds, "
    "not normal approximations. They assume independent shots within and across configurations, "
    "a fixed outcome distribution per configuration, and shot counts, settings and CHSH signs chosen "
    "before observing outcomes (no optional stopping or post-selection). Each correlator interval has "
    "individual 95% coverage; they are not a simultaneous confidence region. The S interval is derived "
    "directly from all shots, not from adding correlator interval endpoints. They exclude hardware drift, "
    "readout bias and other systematic errors. CHSH interpretation assumes the same local observable is "
    "reused wherever its label repeats; only available angles can be checked. "
    "Counts and angle metadata cannot establish independence, "
    "locality, fair sampling or freedom of setting choice. This is not a loophole-free Bell test."
)


def _hoeffding_interval(estimate: float, inverse_shots: float, bound: float) -> list[float]:
    """Invert P(|estimate - mean| >= t) <= 2 exp(-t^2 / (2 sum_i 1/n_i)).

    Each signed parity shot contributes +/-1/n_i to the estimator. Its range
    width is 2/n_i, so the sum of squared widths is 4 sum_i 1/n_i.
    """
    radius = math.sqrt(2 * math.log(2 / (1 - CONFIDENCE_LEVEL)) * inverse_shots)
    return [max(-bound, estimate - radius), min(bound, estimate + radius)]


def _validate_measurement_settings(rows):
    settings: dict[str, float] = {}
    available = 0
    for row in rows:
        # The label identifies local settings, independently of source row order.
        alice, bob = {
            "ab": ("a", "b"), "ab'": ("a", "b'"),
            "a'b": ("a'", "b"), "a'b'": ("a'", "b'"),
        }[row["label"]]
        for key, setting in (("alice_angle_rad", alice), ("bob_angle_rad", bob)):
            angle = row.get(key)
            if angle is None:
                continue
            available += 1
            if setting in settings and not math.isclose(
                angle, settings[setting], rel_tol=0, abs_tol=ANGLE_TOLERANCE_RAD
            ):
                raise ValueError(
                    f"Inconsistent CHSH measurement setting {setting}: repeated {key} values "
                    f"must agree within {ANGLE_TOLERANCE_RAD:g} rad in the recorded convention."
                )
            settings[setting] = angle
    return "complete" if available == 8 else "partial" if available else "unavailable"


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
    # Preserve order so positional seed provenance and source circuits stay aligned.
    for original in source:
        row = original.copy()
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
        row.update(
            shots=shots, correlator=estimate, uncertainty=math.sqrt((1 - estimate ** 2) / shots),
            confidence_interval=_hoeffding_interval(estimate, 1 / shots, 1),
            confidence_level=CONFIDENCE_LEVEL, confidence_method="hoeffding",
        )
        rows.append(row)
    if math.prod(row["sign_in_chsh"] for row in rows) != -1:
        raise ValueError("A CHSH expression must have an odd number of negative signs.")
    settings_validation = _validate_measurement_settings(rows)
    repeated = any(
        all(row["counts"].get(key, 0) == other["counts"].get(key, 0) for key in BITSTRINGS)
        for index, row in enumerate(rows) for other in rows[index + 1:]
    )
    estimate = sum(row["sign_in_chsh"] * row["correlator"] for row in rows)
    interval = _hoeffding_interval(estimate, sum(1 / row["shots"] for row in rows), 4)
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
        chsh_confidence_interval=interval,
        chsh_confidence_level=CONFIDENCE_LEVEL,
        chsh_confidence_method="hoeffding",
        chsh_confidence_assumption=CONFIDENCE_ASSUMPTION,
        chsh_settings_validation=settings_validation,
        sampling_warnings=warnings,
        classical_bound=2.0,
        tsirelson_bound=2 * math.sqrt(2),
        violated=abs(estimate) > 2,
        observed_violation=abs(estimate) > 2,
        statistically_supported_violation=interval[0] > 2 or interval[1] < -2,
        observed_shots=sum(row["shots"] for row in rows),
        observed_shots_per_configuration=[row["shots"] for row in rows],
    )
