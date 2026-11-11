"""Versioned public receipts, with dependency-free validation of historical data."""
from __future__ import annotations

import math
import re

from qiskit_lab.chsh_reporting import prepare_chsh_report

SCHEMA_VERSION = 1
RECEIPT_TYPES = {"execution", "job", "qaoa", "chsh", "distribution"}
TERMINAL = {"DONE", "ERROR", "CANCELLED"}
STATUSES = TERMINAL | {
    "SUBMITTED", "INITIALIZING", "CREATING", "VALIDATING", "QUEUED", "RUNNING",
    "CANCEL_PENDING", "SUBMISSION_UNKNOWN", "NOT_SUBMITTED",
}
IMPORTED = "imported_receipt_not_verified_online"


class ReceiptValidationError(ValueError):
    """A safe, actionable error that never includes receipt values or SDK bodies."""


def validate_counts(counts):
    """Return the bit width of one positive, joint binary histogram."""
    if not isinstance(counts, dict) or not counts:
        raise ReceiptValidationError("Each file must contain positive counts from one circuit.")
    if any(type(value) is not int or value < 0 for value in counts.values()):
        raise ReceiptValidationError("Counts must be non-negative integers.")
    if sum(counts.values()) <= 0:
        raise ReceiptValidationError("Each file must contain positive counts from one circuit.")
    if any(not isinstance(state, str) or not re.fullmatch(r"[01]+", state) for state in counts):
        raise ReceiptValidationError("Count keys must be non-empty binary bitstrings without separators.")
    widths = {len(state) for state in counts}
    if len(widths) != 1:
        raise ReceiptValidationError("All count bitstrings in a receipt must have the same bit width.")
    return widths.pop()


def validate_comparison_metadata(metadata, width=None):
    """Validate the separately versioned source identity and joint register layout."""
    if (not isinstance(metadata, dict) or type(metadata.get("schema_version")) is not int
            or metadata["schema_version"] != 1
            or not isinstance(metadata.get("circuit_sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", metadata["circuit_sha256"])):
        raise ReceiptValidationError("Invalid or unsupported comparison metadata; regenerate the receipt.")
    num_clbits = metadata.get("num_clbits")
    registers = metadata.get("registers")
    measurements = metadata.get("measurements")
    if (type(num_clbits) is not int or num_clbits < 1
            or not isinstance(registers, list) or not registers or not isinstance(measurements, list)):
        raise ReceiptValidationError("Invalid measurement layout in comparison metadata.")
    names = set()
    bit_count = 0
    for register in registers:
        if (not isinstance(register, dict) or not isinstance(register.get("name"), str)
                or not register["name"] or register["name"] in names
                or not isinstance(register.get("clbits"), list) or not register["clbits"]
                or any(type(bit) is not int or not 0 <= bit < num_clbits for bit in register["clbits"])
                or len(set(register["clbits"])) != len(register["clbits"])):
            raise ReceiptValidationError("Invalid classical registers in comparison metadata.")
        names.add(register["name"])
        bit_count += len(register["clbits"])
    for measurement in measurements:
        if (not isinstance(measurement, list) or len(measurement) != 2
                or any(type(bit) is not int or bit < 0 for bit in measurement)
                or measurement[1] >= num_clbits):
            raise ReceiptValidationError("Invalid measured-bit mapping in comparison metadata.")
    if width is not None and bit_count != width:
        raise ReceiptValidationError("Count bit width does not match the recorded classical registers.")


def _nonempty_string(data, key):
    if not isinstance(data.get(key), str) or not data[key].strip():
        raise ReceiptValidationError(f"The {key} field must be a non-empty string; restore the public metadata.")


def _validate_context(data):
    historical = "schema_version" not in data
    if "hardware" in data and type(data["hardware"]) is not bool:
        raise ReceiptValidationError("The hardware field must be a boolean when provided.")
    for key in ("status", "backend", "run_id", "job_id"):
        if key in data and not (historical and data[key] is None):
            _nonempty_string(data, key)
    for key in ("shots", "qubits", "node_count"):
        if (key in data and not (historical and data[key] is None)
                and (type(data[key]) is not int or data[key] < 1)):
            raise ReceiptValidationError(f"The {key} field must be a positive integer.")
    if data.get("hardware") is False and "job_id" in data:
        raise ReceiptValidationError("A local simulation cannot claim an IBM job_id; correct hardware metadata.")
    if data.get("hardware") is True and data.get("backend") == "local_statevector_simulator":
        raise ReceiptValidationError("The local simulator cannot be labelled as IBM hardware.")
    if "metrics" in data and not isinstance(data["metrics"], dict):
        raise ReceiptValidationError("Job metrics must be a JSON object when provided.")
    if "optimization_trace" in data:
        trace = data["optimization_trace"]
        if (not isinstance(trace, (list, tuple)) or not trace
                or any(type(value) not in {int, float} or not math.isfinite(value) for value in trace)):
            raise ReceiptValidationError("QAOA optimization_trace must contain finite numeric expectations.")
    for key in ("gamma", "beta", "expected_cut", "exact_cut", "approximation_ratio", "best_cut"):
        if key in data and (type(data[key]) not in {int, float} or not math.isfinite(data[key])):
            raise ReceiptValidationError(f"QAOA {key} must be a finite number.")


def _validate_version(data):
    if "schema_version" not in data:
        if "receipt_type" in data:
            raise ReceiptValidationError("receipt_type requires schema_version; restore the receipt envelope.")
        return
    if type(data["schema_version"]) is not int or data["schema_version"] != SCHEMA_VERSION:
        raise ReceiptValidationError("Unsupported receipt schema_version; use a compatible Qiskit Lab release. "
                                     "Do not remove or relabel the version to bypass validation.")
    kind = data.get("receipt_type")
    if not isinstance(kind, str) or kind not in RECEIPT_TYPES:
        raise ReceiptValidationError("Schema 1 requires a supported receipt_type; consult docs/receipts.md.")
    if kind == "distribution":
        if "counts" not in data:
            raise ReceiptValidationError("A distribution receipt requires counts.")
        return
    for key in ("status", "backend"):
        _nonempty_string(data, key)
    if data["status"] not in STATUSES:
        raise ReceiptValidationError("Unsupported receipt status; use a compatible producer or restore metadata.")
    if "hardware" not in data:
        raise ReceiptValidationError("Schema 1 execution receipts require an explicit hardware boolean.")
    hardware = data["hardware"]
    if kind == "job" and hardware is not True:
        raise ReceiptValidationError("A job receipt must describe hardware.")
    if kind in {"execution", "qaoa"} and hardware is not False:
        raise ReceiptValidationError("Local execution and QAOA receipts must have hardware false.")
    if not hardware:
        _nonempty_string(data, "run_id")
    elif data["status"] not in {"SUBMISSION_UNKNOWN", "NOT_SUBMITTED"}:
        _nonempty_string(data, "job_id")
    else:
        _nonempty_string(data, "run_id")
    if kind == "chsh" and "correlators" not in data:
        raise ReceiptValidationError("A CHSH receipt requires four correlators.")
    if kind in {"execution", "qaoa"} and data["status"] == "DONE" and "counts" not in data:
        raise ReceiptValidationError("A completed local receipt requires counts; restore the scientific result.")
    if kind == "qaoa":
        for key in ("node_count", "edges", "gamma", "beta", "expected_cut", "exact_cut",
                    "approximation_ratio", "best_bitstring", "best_cut", "optimization_trace"):
            if key not in data:
                raise ReceiptValidationError(f"A QAOA receipt requires {key}; restore the experiment metadata.")


def _validate_qaoa(data, widths):
    if data.get("node_count") is None:
        return
    nodes = data["node_count"]
    if (any(width != nodes for width in widths)
            or (data.get("qubits") is not None and data["qubits"] != nodes)):
        raise ReceiptValidationError("QAOA node_count, qubits and count bit width must agree.")
    if "edges" in data:
        edges = data["edges"]
        if (not isinstance(edges, (list, tuple))
                or any(not isinstance(edge, (list, tuple)) or len(edge) != 2
                       or any(type(node) is not int or not 0 <= node < nodes for node in edge)
                       or edge[0] == edge[1] for edge in edges)):
            raise ReceiptValidationError("QAOA edges must reference two distinct nodes within node_count.")
    if "best_bitstring" in data:
        state = data["best_bitstring"]
        if not isinstance(state, str) or not re.fullmatch(r"[01]+", state) or len(state) != nodes:
            raise ReceiptValidationError("QAOA best_bitstring must be a binary state of node_count bits.")


def validate_receipt(data, *, for_report=False, for_comparison=False):
    """Validate in place, recomputing only CHSH summaries, never inventing metadata.

    An absent envelope is the historical compatibility path, not schema version 0.
    Missing historical context remains unavailable. Present fields still validate.
    """
    if not isinstance(data, dict):
        raise ReceiptValidationError("Each input must be a JSON object (a JSON receipt object).")
    _validate_context(data)
    _validate_version(data)
    if for_report and data.get("status") not in TERMINAL:
        raise ReceiptValidationError("A completion report requires a terminal job state.")
    if "correlators" in data:
        try:
            prepare_chsh_report(data)
        except ValueError as error:
            raise ReceiptValidationError(str(error)) from error
        if data.get("receipt_type") in {"execution", "qaoa", "distribution"}:
            raise ReceiptValidationError("CHSH configurations require receipt_type chsh or job.")
        for row in data["correlators"]:
            if "comparison_metadata" in row:
                validate_comparison_metadata(row["comparison_metadata"], validate_counts(row["counts"]))
    if "counts" in data:
        raw = data["counts"]
        publications = raw if isinstance(raw, list) else [raw]
        if not publications:
            raise ReceiptValidationError("Counts must contain at least one publication; omit unavailable counts.")
        widths = [validate_counts(counts) for counts in publications]
    else:
        publications, widths = [], []
    _validate_qaoa(data, widths)
    if "comparison_metadata" in data:
        metadata = data["comparison_metadata"]
        validate_comparison_metadata(metadata)
        for width in widths:
            validate_comparison_metadata(metadata, width)
        if data.get("qubits") is not None and any(pair[0] >= data["qubits"] for pair in metadata["measurements"]):
            raise ReceiptValidationError("Measured-qubit mapping exceeds the recorded source qubits.")
    if "correlators" in data and publications:
        rows = data["correlators"]
        if (len(publications) != len(rows)
                or any(any(counts.get(state, 0) != row["counts"].get(state, 0)
                           for state in counts.keys() | row["counts"].keys())
                       for counts, row in zip(publications, rows, strict=True))):
            raise ReceiptValidationError("Top-level counts and labelled CHSH configuration counts disagree.")
    if for_comparison and ("correlators" in data or len(publications) != 1):
        raise ReceiptValidationError("Each file must contain positive counts from one circuit.")
    if (for_report and data.get("status") == "DONE" and not publications
            and "correlators" not in data and data.get("result_error")):
        raise ReceiptValidationError("Job results are still unavailable; query the same job ID again, "
                                     "without resubmitting, before generating a completion report.")
    return data
