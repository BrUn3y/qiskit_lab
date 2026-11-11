"""Controlled diagnostics without inspecting exception messages or SDK bodies."""
from __future__ import annotations

import importlib.metadata
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

NEXT_STEPS = {
    "local_input": "Check the command options and public input file format; correct the input before retrying.",
    "filesystem": "Check input readability, output and temporary directory permissions, and free disk space. "
                  "Preserve existing receipts before retrying.",
    "rendering": "Check plotting/report dependencies and output or temporary directory access. "
                 "Regenerate HTML from a saved receipt with report --input; do not resubmit a job for a visualization.",
    "dependency": "Restore the locked environment with uv sync --locked. "
                  "Use the documented separate environment for optional workflows; do not change IBM credentials.",
    "ibm": "Check IBM Quantum service availability, network access, and instance/backend access. "
           "Verify configuration through the supported setup flow without sharing keys or SDK request bodies.",
    "local_execution": "Check the circuit and local simulator limits. "
                       "Restore the locked environment with uv sync --locked if the problem persists.",
    "internal": "Preserve existing receipts and report the command and safe error category to the maintainer; "
                "do not include credentials, request payloads, or SDK exception bodies.",
}
SUBMISSION_WARNING = (
    "A hardware submission may already have been accepted. Inspect existing IBM jobs tagged qiskit-lab-dam "
    "before trying again; do not automatically resubmit."
)


class UserError(Exception):
    """Only application-authored, public messages may be displayed verbatim."""

    def __init__(self, message: str, *, category: str = "local_input", next_step: str | None = None):
        super().__init__(message)
        self.category = category
        self.next_step = next_step


@dataclass(frozen=True)
class FailureContext:
    category: str
    submission_attempted: bool = False


@contextmanager
def failure_context(category: str, *, submission_attempted: bool = False) -> Iterator[None]:
    """Annotate, but do not replace, exceptions from an operation we own."""
    try:
        yield
    except Exception as error:
        if not isinstance(getattr(error, "_qiskit_lab_failure", None), FailureContext):
            error._qiskit_lab_failure = FailureContext(category, submission_attempted)  # type: ignore[attr-defined]
        raise


def error_response(error: Exception, *, default: str = "internal") -> dict[str, str]:
    context = getattr(error, "_qiskit_lab_failure", None)
    category = context.category if isinstance(context, FailureContext) else default
    if isinstance(error, UserError):
        category = error.category
    elif isinstance(error, (ImportError, importlib.metadata.PackageNotFoundError)):
        category = "dependency"
    elif category != "ibm" or not isinstance(context, FailureContext):
        if isinstance(error, OSError) and not (category == "ibm" and isinstance(error, (ConnectionError, TimeoutError))):
            category = "filesystem"
        elif isinstance(error, (ValueError, UnicodeError)) and category not in {"rendering", "local_execution"}:
            category = "local_input"
    if category not in NEXT_STEPS:
        category = "internal"
    next_step = error.next_step if isinstance(error, UserError) and error.next_step else NEXT_STEPS[category]
    if isinstance(context, FailureContext) and context.submission_attempted:
        next_step += " " + SUBMISSION_WARNING
    return {"error": str(error) if isinstance(error, UserError) else type(error).__name__,
            "error_category": category, "next_step": next_step}
