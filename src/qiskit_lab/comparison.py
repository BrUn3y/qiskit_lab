"""Source-circuit provenance and validation for distribution comparisons."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from qiskit import qasm3


class ComparisonError(ValueError):
    """An actionable comparison error containing no input file contents."""


def comparison_metadata(circuit):
    """Identify the logical source circuit, before any hardware transpilation.

    One QASM import/export normalizes generated gate definitions so a saved
    circuit can be reused as input without changing its identity. This is a
    source identity check, not a proof of equivalence between different circuits.
    """
    source = qasm3.dumps(qasm3.loads(qasm3.dumps(circuit)))
    return {
        "schema_version": 1,
        "circuit_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "num_clbits": circuit.num_clbits,
        "registers": [{"name": register.name,
                       "clbits": [circuit.find_bit(bit).index for bit in register]}
                      for register in circuit.cregs],
        "measurements": [[circuit.find_bit(item.qubits[0]).index, circuit.find_bit(item.clbits[0]).index]
                         for item in circuit.data if item.operation.name == "measure"],
    }


def _validate_metadata(metadata, width):
    if (not isinstance(metadata, dict) or type(metadata.get("schema_version")) is not int
            or metadata["schema_version"] != 1
            or not isinstance(metadata.get("circuit_sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", metadata["circuit_sha256"])):
        raise ComparisonError("Invalid or unsupported comparison metadata; regenerate the receipt.")
    num_clbits = metadata.get("num_clbits")
    registers = metadata.get("registers")
    measurements = metadata.get("measurements")
    if (type(num_clbits) is not int or num_clbits < 1
            or not isinstance(registers, list) or not registers or not isinstance(measurements, list)):
        raise ComparisonError("Invalid measurement layout in comparison metadata.")
    names = set()
    bit_count = 0
    for register in registers:
        if (not isinstance(register, dict) or not isinstance(register.get("name"), str)
                or not register["name"] or register["name"] in names
                or not isinstance(register.get("clbits"), list) or not register["clbits"]
                or any(type(bit) is not int or not 0 <= bit < num_clbits for bit in register["clbits"])):
            raise ComparisonError("Invalid classical registers in comparison metadata.")
        names.add(register["name"])
        bit_count += len(register["clbits"])
    for measurement in measurements:
        if (not isinstance(measurement, list) or len(measurement) != 2
                or any(type(bit) is not int or bit < 0 for bit in measurement)
                or measurement[1] >= num_clbits):
            raise ComparisonError("Invalid measured-bit mapping in comparison metadata.")
    if bit_count != width:
        raise ComparisonError("Count bit width does not match the recorded classical registers.")


def _read_distribution(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as error:
        raise ComparisonError("Cannot read comparison input; provide a readable UTF-8 JSON receipt.") from error
    if not isinstance(data, dict):
        raise ComparisonError("Each comparison input must be a JSON receipt object.")
    counts = data.get("counts")
    if isinstance(counts, list) and len(counts) == 1:
        counts = counts[0]
    if not isinstance(counts, dict) or not counts:
        raise ComparisonError("Each file must contain positive counts from one circuit.")
    if any(type(value) is not int or value < 0 for value in counts.values()):
        raise ComparisonError("Counts must be non-negative integers.")
    if sum(counts.values()) <= 0:
        raise ComparisonError("Each file must contain positive counts from one circuit.")
    if any(not re.fullmatch(r"[01]+", state) for state in counts):
        raise ComparisonError("Count keys must be non-empty binary bitstrings without separators.")
    widths = {len(state) for state in counts}
    if len(widths) != 1:
        raise ComparisonError("All count bitstrings in a receipt must have the same bit width.")
    width = widths.pop()
    metadata = data.get("comparison_metadata")
    if "comparison_metadata" in data:
        _validate_metadata(metadata, width)
    return counts, width, metadata


def compare_receipts(left_path, right_path, *, allow_unverified=False):
    left, left_width, left_metadata = _read_distribution(left_path)
    right, right_width, right_metadata = _read_distribution(right_path)
    if left_width != right_width:
        raise ComparisonError("Cannot compare distributions with different bit widths.")
    verified = left_metadata is not None and right_metadata is not None
    if verified:
        for field, description in [("num_clbits", "Classical bit layouts"),
                                   ("registers", "Classical register order or bit mapping"),
                                   ("measurements", "Measured qubits or classical bit mapping"),
                                   ("circuit_sha256", "Source circuit identities")]:
            if left_metadata[field] != right_metadata[field]:
                raise ComparisonError(f"{description} differ; compare the same circuit and measurement order.")
    elif not allow_unverified:
        raise ComparisonError("Circuit identity and measurement order cannot be verified: comparison metadata is "
                              "missing. Use --allow-unverified only for an intentional legacy comparison.")
    left_total, right_total = sum(left.values()), sum(right.values())
    states = sorted(left.keys() | right.keys())
    response = {
        "left_shots": left_total,
        "right_shots": right_total,
        "compatibility": {"verified": verified, "bit_width": left_width},
        "total_variation_distance": sum(abs(left.get(s, 0) / left_total - right.get(s, 0) / right_total)
                                        for s in states) / 2,
        "probabilities": {s: {"left": left.get(s, 0) / left_total, "right": right.get(s, 0) / right_total}
                          for s in states},
    }
    if verified:
        response["compatibility"]["circuit_sha256"] = left_metadata["circuit_sha256"]
    else:
        response["warnings"] = ["Comparison is unverified: circuit identity and measurement order are not "
                                "available in both receipts."]
    return response
