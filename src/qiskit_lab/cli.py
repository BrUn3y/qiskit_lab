"""Qiskit Lab's framework-independent command line tools for DAM.

All stdout is JSON. Credentials are consumed by the IBM SDK, never emitted.
Hardware submission is explicit and is never automatically retried.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import logging
import os
import re
import shlex
import shutil
import sys
import time
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from qiskit import QuantumCircuit, qasm2, qasm3
from qiskit.primitives import StatevectorSampler
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2
from qiskit_ibm_runtime.accounts.exceptions import AccountNotFoundError

from qiskit_lab.reports import write_report

ROOT = Path.cwd()
logging.getLogger("qiskit_ibm_runtime").setLevel(logging.CRITICAL)


class UserError(Exception):
    """An actionable error safe to display to the user."""


def runtime_service():
    # In DAM use the SDK account saved by the user in the hidden setup prompt.
    # Environment credentials are supported for local/CI use; do not log them.
    options = {"channel": "ibm_quantum_platform"}
    token = os.environ.get("QISKIT_IBM_TOKEN") or os.environ.get("QISKIT_IBM_RUNTIME_APIKEY")
    if token:
        options["token"] = token
    instance = os.environ.get("QISKIT_IBM_INSTANCE") or os.environ.get("QISKIT_IBM_RUNTIME_INSTANCE")
    if instance:
        options["instance"] = instance
    return QiskitRuntimeService(**options)


def now():
    return datetime.now(UTC).isoformat()


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(value, indent=2, default=str) + "\n")
    temporary.replace(path)


def artifact_dir(base):
    directory = Path(base) / (datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8])
    directory.mkdir(parents=True)
    return directory


def circuit_info(circuit):
    return {"qubits": circuit.num_qubits, "depth": circuit.depth(),
            "gate_counts": dict(circuit.count_ops())}


def save_qiskit_script(directory, source):
    """Record a standalone reconstruction script without any submission code."""
    script = (
        '"""Generated Qiskit script for the recorded circuit.\n\n'
        'Rebuilds the circuit from OpenQASM 3 without submitting a job.\n'
        'This is a generated reconstruction, not the original author\'s Python source.\n'
        '"""\n'
        'from qiskit import qasm3\n\n'
        'OPENQASM_SOURCE = (\n'
        + ''.join(f'    {line!r}\n' for line in source.splitlines(keepends=True))
        + ')\n\n'
        'circuit = qasm3.loads(OPENQASM_SOURCE)\n\n'
        'if __name__ == "__main__":\n'
        '    print(circuit.draw(output="text"))\n'
    )
    path = directory / "circuit.py"
    path.write_text(script, encoding="utf-8")
    return str(path)


def sdk_versions():
    return {package: importlib.metadata.version(package) for package in ("qiskit", "qiskit-ibm-runtime")}


def finish_report(response, directory, filename):
    # Persist scientific results even if presentation generation fails.
    response.pop("report_error", None)
    save_json(directory / filename, response)
    try:
        write_report(response, directory)
    except Exception as error:  # noqa: BLE001 - Report failures must never lose accepted job/results
        response["report_error"] = type(error).__name__
    save_json(directory / filename, response)
    return response


def example_circuit(name, qubits=3):
    if name == "bell":
        circuit = QuantumCircuit(2)
        circuit.h(0)
        circuit.cx(0, 1)
    elif name == "ghz":
        circuit = QuantumCircuit(qubits)
        circuit.h(0)
        for index in range(1, qubits):
            circuit.cx(0, index)
    elif name == "grover":
        # Two-qubit Grover search with marked state 11; one iteration is exact.
        circuit = QuantumCircuit(2)
        circuit.h([0, 1])
        circuit.cz(0, 1)
        circuit.h([0, 1])
        circuit.x([0, 1])
        circuit.cz(0, 1)
        circuit.x([0, 1])
        circuit.h([0, 1])
    elif name == "deutsch-jozsa":
        # Balanced f(x)=x_0, with qubits-1 input qubits and one ancilla.
        circuit = QuantumCircuit(qubits, qubits - 1)
        circuit.x(qubits - 1)
        circuit.h(range(qubits))
        circuit.cx(0, qubits - 1)
        circuit.h(range(qubits - 1))
        circuit.measure(range(qubits - 1), range(qubits - 1))
        return circuit
    else:
        raise UserError("Unknown example.")
    circuit.measure_all()
    return circuit


def load_circuit(args):
    if args.example:
        return example_circuit(args.example, args.qubits)
    source = Path(args.qasm).read_text()
    try:
        circuit = qasm3.loads(source) if re.search(r"^\s*OPENQASM\s+3", source, re.MULTILINE) else qasm2.loads(source)
    except Exception as error:
        raise UserError("Invalid or unsupported OpenQASM circuit; use OpenQASM 2 or 3.") from error
    if circuit.num_parameters:
        raise UserError("Bind all circuit parameters before execution.")
    if not any(item.operation.name == "measure" for item in circuit.data):
        circuit.measure_all()
    return circuit


def counts_from_result(result):
    # join_data preserves correlations when a circuit has several registers.
    return [publication.join_data().get_counts() for publication in result]


def backend_summary(backend):
    status = backend.status()
    return {"name": backend.name, "qubits": backend.num_qubits,
            "operational": status.operational, "pending_jobs": status.pending_jobs,
            "status": status.status_msg}


def execute(args):
    started = time.monotonic()
    if args.backend and not args.hardware:
        raise UserError("--backend requires --hardware. Omit both for local simulation.")
    circuit = load_circuit(args)
    if not args.hardware and circuit.num_qubits > 20:
        raise UserError("Local statevector simulation is limited to 20 qubits.")
    directory = artifact_dir(args.output_dir)
    source = qasm3.dumps(circuit)
    (directory / "circuit.qasm").write_text(source, encoding="utf-8")
    qiskit_path = save_qiskit_script(directory, source)
    (directory / "circuit.txt").write_text(str(circuit.draw(output="text")) + "\n")
    receipt = {"run_id": directory.name, "created_at": now(), "shots": args.shots,
               "qubits": circuit.num_qubits, "hardware": args.hardware, "artifacts": str(directory),
               "qiskit_path": qiskit_path}
    title = getattr(args, "title", None) or (
        args.example.replace("-", " ").title() + " circuit" if args.example
        else args.qasm.stem.replace("_", " ").replace("-", " ") + " circuit")
    receipt.update(circuit_info(circuit), versions=sdk_versions(), title=title)
    if args.hardware:
        service = runtime_service()
        backend = (service.backend(args.backend) if args.backend else
                   service.least_busy(operational=True, simulator=False, min_num_qubits=circuit.num_qubits))
        if not backend.status().operational:
            raise UserError("The selected IBM Quantum backend is not operational.")
        if backend.num_qubits < circuit.num_qubits:
            raise UserError("The selected backend has too few qubits.")
        isa_circuit = generate_preset_pass_manager(backend=backend, optimization_level=1).run(circuit)
        (directory / "isa-circuit.qasm").write_text(qasm3.dumps(isa_circuit))
        receipt.update(isa_qubits=isa_circuit.num_qubits, isa_depth=isa_circuit.depth(),
                       isa_gate_counts=dict(isa_circuit.count_ops()), max_execution_time=args.max_execution_time)
        sampler = SamplerV2(mode=backend, options={"max_execution_time": args.max_execution_time,
                                                  "environment": {"job_tags": ["qiskit-lab-dam"]}})
        # Never retry run(): a network error may occur after IBM accepted a job.
        job = sampler.run([isa_circuit], shots=args.shots)
        receipt.update(backend=backend.name, job_id=job.job_id(), status="SUBMITTED")
        # Persist the accepted job immediately, before any status/result requests.
        save_json(directory / "receipt.json", receipt)
        return receipt
    result = StatevectorSampler(seed=42).run([circuit], shots=args.shots).result()
    receipt.update(backend="local_statevector_simulator", status="DONE", counts=counts_from_result(result)[0])
    from qiskit_lab.execution_visualization import render_execution_dashboard

    image = render_execution_dashboard(circuit, receipt["counts"], backend_name=receipt["backend"],
                                       job_id=receipt["run_id"], shots=args.shots)
    try:
        shutil.copyfile(image, directory / "results.png")
    finally:
        image.unlink(missing_ok=True)
    receipt["dashboard_path"] = str(directory / "results.png")
    receipt.update(completed_at=now(), duration_seconds=round(time.monotonic() - started, 6), seed=42)
    return finish_report(receipt, directory, "receipt.json")


def inspect_job(args):
    from qiskit_lab.job_tracking import find_receipt, job_metadata
    from qiskit_lab.reports import job_directory

    base = getattr(args, "output_dir", ROOT / "artifacts/dam")
    directory, response = find_receipt(base, args.job_id)
    directory = directory or job_directory(base, args.job_id)
    if getattr(args, "title", None):
        response["title"] = args.title
    job = runtime_service().job(args.job_id)
    backend = job.backend()
    response.update(job_id=job.job_id(), backend=backend.name, status=str(job.status()), queried_at=now(),
                    hardware=True, artifacts=str(directory))
    response.pop("poll_error", None)
    if response["status"] == "DONE" or (args.wait and response["status"] not in {"ERROR", "CANCELLED"}):
        try:
            response["counts"] = counts_from_result(job.result(timeout=args.wait or 30))
            response["status"] = str(job.status())
            response.pop("result_error", None)
            response.pop("next_step", None)
        except Exception as error:  # noqa: BLE001 - SDK failures must never expose credentials
            # The accepted job is still identified even after a timeout/failure.
            response["result_error"] = type(error).__name__
            response["next_step"] = "Query this same job ID again; do not resubmit the circuit."
    if response["status"] in {"DONE", "ERROR", "CANCELLED"}:
        response.update(job_metadata(job))
        # A failed result download is retryable; do not publish an empty success report.
        if response["status"] != "DONE" or "counts" in response:
            finish_report(response, directory, "receipt.json")
        else:
            save_json(directory / "receipt.json", response)
    else:
        save_json(directory / "receipt.json", response)
    if args.output:
        save_json(args.output, response)
    return response


def qaoa(args):
    started = time.monotonic()
    started_at = now()
    from qiskit_lab.experiment_engine import run_maxcut_qaoa

    result = run_maxcut_qaoa(args.request, shots=args.shots)
    directory = artifact_dir(args.output_dir)
    try:
        shutil.copyfile(result.dashboard_path, directory / "qaoa.png")
    finally:
        result.dashboard_path.unlink(missing_ok=True)
    (directory / "optimized.qasm").write_text(result.qasm)
    qiskit_path = save_qiskit_script(directory, result.qasm)
    response = asdict(result)
    response.pop("qasm")
    response.update(hardware=False, created_at=started_at, dashboard_path=str(directory / "qaoa.png"),
                    qasm_path=str(directory / "optimized.qasm"), qiskit_path=qiskit_path, artifacts=str(directory))
    circuit = qasm3.loads(result.qasm)
    (directory / "circuit.txt").write_text(str(circuit.draw(output="text")) + "\n")
    response.update(circuit_info(circuit), status="DONE", shots=args.shots, seed=42,
                    title="QAOA Max-Cut experiment", backend="local_statevector_simulator", versions=sdk_versions(),
                    run_id=directory.name, completed_at=now(), duration_seconds=round(time.monotonic() - started, 6))
    return finish_report(response, directory, "experiment.json")


def doctor(args):
    response = {"channel": "ibm_quantum_platform", "python": sys.version.split()[0],
                "versions": {package: importlib.metadata.version(package)
                             for package in ("qiskit", "qiskit-ibm-runtime", "numpy")},
                "credentials_in_environment": bool(os.environ.get("QISKIT_IBM_TOKEN") or
                                                   os.environ.get("QISKIT_IBM_RUNTIME_APIKEY")),
                "saved_account_file_exists": (Path.home() / ".qiskit/qiskit-ibm.json").exists()}
    if args.online:
        response["backends"] = [backend_summary(backend) for backend in runtime_service().backends(simulator=False)]
        response["queried_at"] = now()
        response["connected"] = bool(response["backends"])
        if not response["connected"]:
            raise UserError("IBM accepted the account but no hardware backends are accessible; check the instance CRN.")
    return response


def onboarding():
    """Describe the first-chat connection step without opening credential files."""
    setup = f"cd {shlex.quote(str(Path.cwd()))} && uv run --locked python scripts/dam/configure-quantum.py"
    request = {"status": "needs_credentials", "channel": "ibm_quantum_platform",
                "message": "To connect Qiskit Lab to IBM Quantum, configure your API key and, if available, "
                           "your instance CRN. Do not paste the key into chat: open this agent's Terminal "
                           "and run the setup command. For environment configuration, use QISKIT_IBM_TOKEN "
                           "for the API key (QISKIT_IBM_RUNTIME_APIKEY is also supported), and "
                           "QISKIT_IBM_INSTANCE for the CRN. You can also continue with local simulation.",
                "setup_command": setup, "credential_entry": "hidden_terminal_prompt", "hardware_ready": False,
                "api_key_env": "QISKIT_IBM_TOKEN", "api_key_env_alias": "QISKIT_IBM_RUNTIME_APIKEY",
                "instance_env": "QISKIT_IBM_INSTANCE"}
    available = bool(os.environ.get("QISKIT_IBM_TOKEN") or os.environ.get("QISKIT_IBM_RUNTIME_APIKEY"))
    available = available or (Path.home() / ".qiskit/qiskit-ibm.json").exists()
    if not available:
        return request
    try:
        backends = [backend_summary(backend) for backend in runtime_service().backends(simulator=False)]
    except AccountNotFoundError:
        # IBM's SDK can create an empty account file before an account is saved.
        # File existence alone must not imply that the owner configured a key.
        return request
    except Exception as error:  # noqa: BLE001 - Return safe SDK error classes without request bodies
        return {"status": "connection_error", "channel": "ibm_quantum_platform",
                "error": type(error).__name__, "hardware_ready": False,
                "message": "An account is configured, but the connection could not be verified. "
                           "Check the credentials, instance and network; do not paste keys into chat.",
                "setup_command": setup}
    return {"status": "ready" if backends else "no_backends", "channel": "ibm_quantum_platform",
            "hardware_ready": bool(backends), "backends": backends, "queried_at": now()}


def inspect_backend(args):
    from qiskit_lab.backend_visualization import render_backend_dashboard

    backend = runtime_service().backend(args.name)
    response = backend_summary(backend)
    response.update(queried_at=now(), operations=sorted(backend.operation_names),
                    coupling_map=list(backend.coupling_map.get_edges()) if backend.coupling_map else [])
    if args.dashboard:
        directory = artifact_dir(args.output_dir)
        image = Path(render_backend_dashboard(backend))
        try:
            shutil.copyfile(image, directory / "backend.png")
        finally:
            image.unlink(missing_ok=True)
        response["dashboard_path"] = str(directory / "backend.png")
        save_json(directory / "backend.json", response)
    return response


def compare(args):
    def read_counts(path):
        data = json.loads(Path(path).read_text())
        counts = data.get("counts")
        if isinstance(counts, list) and len(counts) == 1:
            counts = counts[0]
        if not isinstance(counts, dict) or not counts or sum(counts.values()) <= 0:
            raise UserError("Each file must contain positive counts from one circuit.")
        if any(not isinstance(value, int) or value < 0 for value in counts.values()):
            raise UserError("Counts must be non-negative integers.")
        return counts

    left, right = read_counts(args.left), read_counts(args.right)
    left_total, right_total = sum(left.values()), sum(right.values())
    states = sorted(left.keys() | right.keys())
    response = {"left_shots": left_total, "right_shots": right_total,
                "total_variation_distance": sum(abs(left.get(s, 0) / left_total - right.get(s, 0) / right_total)
                                                for s in states) / 2,
                "probabilities": {s: {"left": left.get(s, 0) / left_total, "right": right.get(s, 0) / right_total}
                                  for s in states}}
    if args.output:
        save_json(args.output, response)
    return response


def bounded_integer(minimum, maximum):
    def parse(value):
        number = int(value)
        if not minimum <= number <= maximum:
            raise argparse.ArgumentTypeError(f"Value must be between {minimum} and {maximum}.")
        return number
    return parse


def parser():
    cli = argparse.ArgumentParser(description=__doc__)
    commands = cli.add_subparsers(dest="command", required=True)
    commands.add_parser("onboarding", help="Check whether the first chat needs IBM Quantum configuration")
    check = commands.add_parser("doctor", help="Check packages and optionally IBM connectivity")
    check.add_argument("--online", action="store_true")
    commands.add_parser("backends", help="List accessible live IBM hardware")
    detail = commands.add_parser("backend", help="Inspect a live backend")
    detail.add_argument("name")
    detail.add_argument("--dashboard", action="store_true")
    detail.add_argument("--output-dir", type=Path, default=ROOT / "artifacts/dam")
    run = commands.add_parser("execute", help="Simulate, or explicitly submit one fresh QPU job")
    source = run.add_mutually_exclusive_group(required=True)
    source.add_argument("--qasm", type=Path)
    source.add_argument("--example", choices=["bell", "ghz", "grover", "deutsch-jozsa"])
    run.add_argument("--qubits", type=bounded_integer(2, 20), default=3)
    run.add_argument("--shots", type=bounded_integer(1, 100000), default=1024)
    run.add_argument("--hardware", action="store_true")
    run.add_argument("--backend")
    run.add_argument("--title", help="Circuit description for the HTML report title and filename")
    run.add_argument("--max-execution-time", type=bounded_integer(1, 10800), default=300)
    run.add_argument("--output-dir", type=Path, default=ROOT / "artifacts/dam")
    status = commands.add_parser("job", help="Query an existing job without resubmitting")
    status.add_argument("job_id")
    status.add_argument("--title", help="Known circuit description for this existing job's HTML report")
    status.add_argument("--wait", type=bounded_integer(0, 300), default=0)
    status.add_argument("--output", type=Path)
    status.add_argument("--output-dir", type=Path, default=ROOT / "artifacts/dam")
    poll = commands.add_parser("poll-jobs", help="Check tracked jobs and generate Carbon HTML on completion")
    poll.add_argument("--output-dir", type=Path, default=ROOT / "artifacts/dam")
    poll.add_argument("--precheck", action="store_true", help="Exit 1 when no report notifications are pending")
    poll.add_argument("--ack", action="append", default=[], metavar="JOB_ID", help="Acknowledge a delivered report")
    experiment = commands.add_parser("qaoa", help="Optimize and validate Max-Cut locally (2–8 nodes)")
    experiment.add_argument("--request", default="QAOA Max-Cut on a 5-node graph")
    experiment.add_argument("--shots", type=bounded_integer(1, 100000), default=1024)
    experiment.add_argument("--output-dir", type=Path, default=ROOT / "artifacts/dam")
    comparison = commands.add_parser("compare", help="Compare saved simulator/hardware count distributions")
    comparison.add_argument("--left", type=Path, required=True)
    comparison.add_argument("--right", type=Path, required=True)
    comparison.add_argument("--output", type=Path)
    return cli


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "onboarding":
            result = onboarding()
        elif args.command == "doctor":
            result = doctor(args)
        elif args.command == "backends":
            result = {"queried_at": now(), "backends": [backend_summary(b) for b in runtime_service().backends(simulator=False)]}
        elif args.command == "backend":
            result = inspect_backend(args)
        elif args.command == "execute":
            result = execute(args)
        elif args.command == "job":
            result = inspect_job(args)
        elif args.command == "qaoa":
            result = qaoa(args)
        elif args.command == "poll-jobs":
            from qiskit_lab.job_tracking import poll_jobs

            result = poll_jobs(args)
            print(json.dumps(result, indent=2, default=str))
            return 1 if args.precheck and not result["notifications"] else 0
        else:
            result = compare(args)
        print(json.dumps(result, indent=2, default=str))
        return 0
    except UserError as error:
        print(json.dumps({"error": str(error)}))
    except Exception as error:  # noqa: BLE001 - CLI boundary redacts SDK request bodies
        # SDK exception messages can contain request bodies or credentials.
        print(json.dumps({"error": type(error).__name__, "next_step":
                          "Check inputs, IBM Quantum credentials, instance CRN and DAM egress. "
                          "If a hardware submission was attempted, inspect IBM jobs tagged qiskit-lab-dam "
                          "before trying again."}))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
