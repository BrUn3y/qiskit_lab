"""Durable submission intent and IBM-read-only ambiguous-submission recovery."""
from __future__ import annotations

import fcntl
import json
import os
import uuid
from contextlib import contextmanager
from pathlib import Path

from qiskit_lab.errors import failure_context

PROJECT_TAG = "qiskit-lab-dam"
RUN_TAG_PREFIX = "qiskit-lab-run-"
INTENT_FILE = "submission-intent.json"
UNKNOWN_NEXT_STEP = (
    "Submission may have been accepted. Use recover-submission with this run_id and the same "
    "--output-dir and IBM instance to locate existing jobs. Do not resubmit automatically."
)


class SubmissionError(Exception):
    """A safe public response, including recovery information, for the CLI."""

    def __init__(self, response):
        super().__init__("Hardware submission needs attention; no automatic retry.")
        self.response = response


class RecoveryError(ValueError):
    """An actionable local recovery error without SDK request bodies."""


def save_durable(path, value):
    """Atomically persist public tracking data before crossing the IBM boundary."""
    path = Path(path)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, default=str)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
        # Flush newly created artifact directories too, including their entries
        # in ancestors when --output-dir did not previously exist.
        directory = path.resolve().parent
        for parent in (directory, *directory.parents):
            descriptor = os.open(parent, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    finally:
        temporary.unlink(missing_ok=True)


def persist_tracking(directory, receipt):
    # Keep an independent durable journal: a later receipt/report write failure
    # must not erase the accepted ID. Attempt both files even if one write fails.
    errors = []
    for name in (INTENT_FILE, "receipt.json"):
        try:
            save_durable(directory / name, receipt)
        except OSError as error:
            errors.append(error)
    if errors:
        raise errors[0]


@contextmanager
def submission_lock(directory):
    with (directory / ".submission.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RecoveryError("This run is still in use. Retry read-only recovery after it finishes.") from error
        yield


def prepare_intent(receipt):
    from qiskit_lab.cli import now

    identifier = uuid.uuid4().hex
    receipt.update(status="SUBMISSION_UNKNOWN", submission_outcome="unknown",
                   submission={"id": identifier, "intent_at": now(), "state": "pending",
                               "job_tags": [PROJECT_TAG, RUN_TAG_PREFIX + identifier]},
                   next_step=UNKNOWN_NEXT_STEP)


def accept(receipt, job_id):
    from qiskit_lab.cli import now

    if not isinstance(job_id, str) or not job_id.strip():
        raise RecoveryError("IBM did not return a usable job ID. Recover this run; do not resubmit.")
    receipt.update(job_id=job_id, status="SUBMITTED", submission_outcome="accepted")
    receipt["submission"].update(state="accepted", accepted_at=now())
    receipt["submission"].pop("error", None)
    receipt.pop("next_step", None)


def persist_accepted(directory, receipt):
    try:
        persist_tracking(directory, receipt)
    except OSError as error:
        raise SubmissionError({**receipt, "error": type(error).__name__,
                               "next_step": "IBM returned this accepted job ID. Preserve it and recover this run "
                                            "to repair local tracking. Query the same ID; do not resubmit."}) from error


def submit_once(sampler, circuit, receipt, directory):
    """Persist intent, submit exactly once, and track the accepted ID before queries."""
    with submission_lock(directory):
        if any((directory / name).exists() or (directory / name).is_symlink()
               for name in (INTENT_FILE, "receipt.json")):
            raise RecoveryError("This run already has submission tracking. Use recover-submission; "
                                "never replay a saved intent.")
        try:
            persist_tracking(directory, receipt)
        except OSError as error:
            raise SubmissionError({**receipt, "error": type(error).__name__, "status": "NOT_SUBMITTED",
                                   "submission_outcome": "not_attempted",
                                   "next_step": "Cannot persist submission intent. Fix local storage before submitting."}
                                  ) from error
        try:
            with failure_context("ibm", submission_attempted=True):
                job = sampler.run([circuit], shots=receipt["shots"])
                accept(receipt, job.job_id())
        except Exception as error:  # noqa: BLE001 - Never retry or expose SDK exception bodies
            receipt["submission"]["error"] = type(error).__name__
            response = {**receipt, "error": type(error).__name__}
            try:
                persist_tracking(directory, receipt)
            except OSError as persistence_error:
                response["persistence_error"] = type(persistence_error).__name__
            raise SubmissionError(response) from error
        persist_accepted(directory, receipt)
        return receipt


def read_record(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise RecoveryError("Cannot read public submission tracking JSON. Restore it before recovery.") from error
    if not isinstance(value, dict):
        raise RecoveryError("Submission tracking must be a JSON object.")
    return value


def find_intent(base, run_id):
    found = []
    for path in sorted(base.rglob(INTENT_FILE)):
        if path.is_symlink() or not path.resolve().is_relative_to(base.resolve()):
            continue
        try:
            value = read_record(path)
        except RecoveryError:
            continue
        if value.get("run_id") == run_id:
            found.append(path)
    if len(found) != 1:
        raise RecoveryError("Expected exactly one saved submission intent for this run_id in --output-dir. "
                            "Legacy runs have no unique tag; inspect existing project-tagged jobs manually.")
    return found[0]


def validate_intent(receipt):
    submission = receipt.get("submission")
    identifier = submission.get("id") if isinstance(submission, dict) else None
    if (receipt.get("hardware") is not True or not isinstance(receipt.get("backend"), str)
            or not receipt["backend"] or not isinstance(identifier, str) or len(identifier) != 32
            or any(char not in "0123456789abcdef" for char in identifier)
            or submission.get("job_tags") != [PROJECT_TAG, RUN_TAG_PREFIX + identifier]):
        raise RecoveryError("The saved intent has invalid hardware, backend or unique run-tag metadata.")


def recover_submission(args):
    """Locate existing jobs only; never construct a sampler, run, cancel, or retag."""
    from qiskit_lab.cli import now, runtime_service

    base = Path(args.output_dir)
    path = find_intent(base, args.run_id)
    directory = path.parent
    # Match the poller's lock while repairing receipts; do not overwrite a report
    # or race an acknowledgement. A live submitter owns the per-run lock.
    with (base / ".job-poll.lock").open("a") as poll_lock, submission_lock(directory):
        fcntl.flock(poll_lock, fcntl.LOCK_EX)
        intent = read_record(path)
        validate_intent(intent)
        receipt_path = directory / "receipt.json"
        if receipt_path.is_symlink():
            raise RecoveryError("Refusing to recover into a symlink receipt.")
        receipt = read_record(receipt_path) if receipt_path.exists() else intent.copy()
        validate_intent(receipt)
        if (intent.get("run_id") != args.run_id or receipt.get("run_id") != args.run_id
                or receipt["submission"]["id"] != intent["submission"]["id"]
                or receipt.get("backend") != intent["backend"]):
            raise RecoveryError("The receipt and intent disagree. Preserve both and resolve the tracking conflict.")
        known_id = receipt.get("job_id") or intent.get("job_id")
        if receipt.get("job_id") and intent.get("job_id") and receipt["job_id"] != intent["job_id"]:
            raise RecoveryError("The receipt and intent contain different job IDs. Do not select one automatically.")
        if known_id:
            if not isinstance(known_id, str) or not known_id.strip():
                raise RecoveryError("The saved job ID is invalid. Restore tracking before querying IBM.")
            if not receipt.get("job_id"):
                accept(receipt, known_id)
                persist_accepted(directory, receipt)
            return {**receipt, "recovery_status": "already_tracked",
                    "next_step": "Query this existing job ID or poll-jobs; do not resubmit."}
        try:
            # Two matches suffice to detect ambiguity; no first-match selection,
            # pending-state filter, time window, or incomplete single-page scan.
            with failure_context("ibm"):
                jobs = runtime_service().jobs(limit=2, backend_name=intent["backend"],
                                              job_tags=intent["submission"]["job_tags"])
                matches = [job.job_id() for job in jobs]
                if any(not isinstance(job_id, str) or not job_id.strip() for job_id in matches):
                    raise RecoveryError("IBM returned an unusable matching job ID.")
        except Exception as error:  # noqa: BLE001 - An unavailable query is not evidence of no job
            raise SubmissionError({**receipt, "error": type(error).__name__, "recovery_status": "query_error",
                                   "next_step": UNKNOWN_NEXT_STEP}) from error
        recovery = {"queried_at": now(), "matches": matches, "match_limit": 2,
                    "recovery_status": "no_match" if not matches else "recovered" if len(matches) == 1 else "ambiguous"}
        if len(matches) == 1:
            accept(receipt, matches[0])
            persist_accepted(directory, receipt)
            recovery["next_step"] = "Query this existing job ID or poll-jobs; do not resubmit."
        elif not matches:
            recovery["next_step"] = ("No matching job is visible in the active IBM instance yet. This is not proof "
                                     "that submission failed. Repeat read-only recovery later with the original "
                                     "instance; do not resubmit automatically.")
        else:
            recovery["next_step"] = ("At least two jobs match this unique run tag. Inspect these existing IDs; "
                                     "no job was selected. Do not resubmit.")
        try:
            save_durable(directory / "submission-recovery.json", recovery)
        except OSError as error:
            raise SubmissionError({**receipt, **recovery, "error": type(error).__name__,
                                   "persistence_error": type(error).__name__}) from error
        return {**receipt, **recovery}
