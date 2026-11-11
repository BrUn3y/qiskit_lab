"""Source-circuit provenance and validation for distribution comparisons."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from qiskit import qasm3

from qiskit_lab.receipts import ReceiptValidationError, validate_receipt


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


def _read_distribution(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as error:
        raise ComparisonError("Cannot read comparison input; provide a readable UTF-8 JSON receipt.") from error
    try:
        validate_receipt(data, for_comparison=True)
    except ReceiptValidationError as error:
        raise ComparisonError(str(error)) from error
    counts = data.get("counts")
    if isinstance(counts, list) and len(counts) == 1:
        counts = counts[0]
    width = len(next(iter(counts)))
    metadata = data.get("comparison_metadata")
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
