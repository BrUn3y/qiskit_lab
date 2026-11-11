"""Read-only IBM job polling with durable, acknowledged report notifications."""
from __future__ import annotations

import fcntl
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from qiskit_lab.errors import error_response

TERMINAL = {"DONE", "ERROR", "CANCELLED"}


def receipts(base):
    """Read only application-owned receipts, never SDK accounts or arbitrary files."""
    base = Path(base)
    if not base.exists():
        return []
    result = []
    for path in sorted(base.rglob("receipt.json")):
        if path.is_symlink() or not path.resolve().is_relative_to(base.resolve()):
            continue
        try:
            value = json.loads(path.read_text())
            if isinstance(value, dict) and value.get("hardware") and value.get("job_id"):
                result.append((path, value))
        except (OSError, ValueError):
            continue
    return result


def find_receipt(base, job_id):
    for path, receipt in receipts(base):
        if receipt["job_id"] == job_id:
            return path.parent, receipt
    return None, {}


def job_metadata(job):
    """Allowlist IBM timing/usage fields; do not serialize SDK objects or options."""
    result: dict[str, object] = {}
    try:
        created = job.creation_date
        if isinstance(created, datetime):
            result["created_at"] = created.isoformat()
    except Exception:  # noqa: BLE001 - Optional SDK metadata must not hide results
        pass
    try:
        metrics = job.metrics()
        if isinstance(metrics, dict):
            cleaned = {}
            for key, fields in [("timestamps", ("created", "running", "finished")),
                                ("usage", ("quantum_seconds", "seconds"))]:
                values = metrics.get(key)
                if isinstance(values, dict):
                    cleaned[key] = {k: values[k] for k in fields if k in values
                                    and isinstance(values[k], (str, int, float))}
            if isinstance(metrics.get("executions"), (int, float)):
                cleaned["executions"] = metrics["executions"]
            result["metrics"] = cleaned
            finished = cleaned.get("timestamps", {}).get("finished")
            if finished:
                result["completed_at"] = finished
    except Exception:  # noqa: BLE001 - Metadata errors do not disclose SDK request bodies
        pass
    return result


def poll_jobs(args):
    from qiskit_lab.cli import finish_report, inspect_job, now, save_json
    from qiskit_lab.reports import report_filename

    base = Path(args.output_dir)
    base.mkdir(parents=True, exist_ok=True)
    # Locks serialize precheck/manual polling and acknowledgements. Nothing is
    # acknowledged until the DAM agent has actually presented the report link.
    with (base / ".job-poll.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        queue_path = base / "job-notifications.json"
        queue = json.loads(queue_path.read_text()) if queue_path.exists() else []
        if args.ack:
            for _, receipt in receipts(base):
                if (receipt["job_id"] in args.ack and receipt.get("report_path")
                        and receipt.get("status") in TERMINAL
                        and not any(e["job_id"] == receipt["job_id"] for e in queue)):
                    queue.append({"event_id": receipt["job_id"] + ":" + receipt["status"],
                                  "job_id": receipt["job_id"], "status": receipt["status"],
                                  "report_path": receipt["report_path"], "created_at": now()})
            for entry in queue:
                if entry["job_id"] in args.ack:
                    entry["acknowledged_at"] = now()
            save_json(queue_path, queue)
            return {"notifications": [e for e in queue if not e.get("acknowledged_at")], "errors": []}
        errors = []
        tracked = receipts(base)
        # Rotate by oldest query so a busy workspace does not starve later jobs.
        tracked.sort(key=lambda pair: pair[1].get("queried_at", pair[1].get("created_at", "")))
        checked = 0
        for path, receipt in tracked:
            report = path.parent / Path(str(receipt.get("report_path", ""))).name
            has_report = (receipt.get("report_path") and report.is_file() and not report.is_symlink()
                          and not receipt.get("report_error"))
            completed = receipt.get("status") in TERMINAL and has_report
            if not completed and checked >= 10:
                break
            try:
                if completed:
                    response = receipt
                    if report.name != report_filename(receipt, path.parent):
                        # Migrate cached results offline; never query or resubmit a completed job for a filename.
                        response = finish_report(receipt, path.parent, "receipt.json")
                else:
                    checked += 1
                    response = inspect_job(SimpleNamespace(job_id=receipt["job_id"], wait=0, output=None, output_dir=base))
                if response.get("status") in TERMINAL and response.get("report_path") and not response.get("report_error"):
                    event_id = response["job_id"] + ":" + response["status"]
                    details = {"job_id": response["job_id"], "status": response["status"],
                               "backend": response["backend"], "report_path": response["report_path"],
                               "report_filename": Path(response["report_path"]).name,
                               "report_title": response.get("report_title", response.get("title", "IBM Quantum execution"))}
                    entry = next((entry for entry in queue if entry["event_id"] == event_id), None)
                    if entry is None:
                        queue.append({"event_id": event_id, **details, "created_at": now()})
                    else:
                        entry.update(details)
            except Exception as error:  # noqa: BLE001 - Preserve the job for another read-only query
                diagnostic = error_response(error, default="ibm")
                errors.append({"job_id": receipt["job_id"], **diagnostic})
                # Rotate failed queries too: stale/unavailable IDs must not
                # permanently block jobs beyond the ten-query batch limit.
                current = json.loads(path.read_text())
                current.update(queried_at=now(), poll_error=diagnostic["error"],
                               poll_error_category=diagnostic["error_category"], poll_next_step=diagnostic["next_step"])
                save_json(path, current)
        save_json(queue_path, queue)
        return {"checked": checked, "notifications": [e for e in queue if not e.get("acknowledged_at")], "errors": errors}
