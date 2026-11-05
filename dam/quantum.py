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
import shutil
import sys
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from qiskit import QuantumCircuit, qasm2, qasm3
from qiskit.primitives import StatevectorSampler
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
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
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, default=str) + "\n")
    temporary.replace(path)


def artifact_dir(base):
    directory = Path(base) / (datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8])
    directory.mkdir(parents=True)
    return directory


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
    if args.backend and not args.hardware:
        raise UserError("--backend requires --hardware. Omit both for local simulation.")
    circuit = load_circuit(args)
    if not args.hardware and circuit.num_qubits > 20:
        raise UserError("Local statevector simulation is limited to 20 qubits.")
    directory = artifact_dir(args.output_dir)
    (directory / "circuit.qasm").write_text(qasm3.dumps(circuit))
    (directory / "circuit.txt").write_text(str(circuit.draw(output="text")) + "\n")
    receipt = {"run_id": directory.name, "created_at": now(), "shots": args.shots,
               "qubits": circuit.num_qubits, "hardware": args.hardware, "artifacts": str(directory)}
    if args.hardware:
        service = runtime_service()
        backend = (service.backend(args.backend) if args.backend else
                   service.least_busy(operational=True, simulator=False, min_num_qubits=circuit.num_qubits))
        if not backend.status().operational:
            raise UserError("The selected IBM Quantum backend is not operational.")
        if backend.num_qubits < circuit.num_qubits:
            raise UserError("The selected backend has too few qubits.")
        isa_circuit = generate_preset_pass_manager(backend=backend, optimization_level=1).run(circuit)
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
    from beeai_agents.execution_visualization import render_execution_dashboard

    image = render_execution_dashboard(circuit, receipt["counts"], backend_name=receipt["backend"],
                                       job_id=receipt["run_id"], shots=args.shots)
    try:
        shutil.copyfile(image, directory / "results.png")
    finally:
        image.unlink(missing_ok=True)
    receipt["dashboard_path"] = str(directory / "results.png")
    save_json(directory / "receipt.json", receipt)
    return receipt


def inspect_job(args):
    job = runtime_service().job(args.job_id)
    backend = job.backend()
    response = {"job_id": job.job_id(), "backend": backend.name, "status": str(job.status()), "queried_at": now()}
    if response["status"] == "DONE" or args.wait:
        try:
            response["counts"] = counts_from_result(job.result(timeout=args.wait or 30))
            response["status"] = str(job.status())
        except Exception as error:  # noqa: BLE001 - SDK failures must never expose credentials
            # The accepted job is still identified even after a timeout/failure.
            response["result_error"] = type(error).__name__
            response["next_step"] = "Query this same job ID again; do not resubmit the circuit."
    if args.output:
        save_json(args.output, response)
    return response


def qaoa(args):
    from beeai_agents.experiment_engine import run_maxcut_qaoa

    result = run_maxcut_qaoa(args.request, shots=args.shots)
    directory = artifact_dir(args.output_dir)
    try:
        shutil.copyfile(result.dashboard_path, directory / "qaoa.png")
    finally:
        result.dashboard_path.unlink(missing_ok=True)
    (directory / "optimized.qasm").write_text(result.qasm)
    response = asdict(result)
    response.pop("qasm")
    response.update(hardware=False, created_at=now(), dashboard_path=str(directory / "qaoa.png"),
                    qasm_path=str(directory / "optimized.qasm"), artifacts=str(directory))
    save_json(directory / "experiment.json", response)
    return response


def doctor(args):
    response = {"channel": "ibm_quantum_platform", "python": sys.version.split()[0],
                "versions": {package: importlib.metadata.version(package)
                             for package in ("qiskit", "qiskit-ibm-runtime", "numpy")},
                "credentials_in_environment": bool(os.environ.get("QISKIT_IBM_TOKEN") or
                                                   os.environ.get("QISKIT_IBM_RUNTIME_APIKEY")),
                "saved_account_file_exists": (Path.home() / ".qiskit/qiskit-ibm.json").exists()}
    if args.online:
        response["backends"] = [backend_summary(backend) for backend in runtime_service().backends(simulator=False)]
        response["connected"] = bool(response["backends"])
        if not response["connected"]:
            raise UserError("IBM accepted the account but no hardware backends are accessible; check the instance CRN.")
    return response


def inspect_backend(args):
    from beeai_agents.backend_visualization import render_backend_dashboard

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
    run.add_argument("--max-execution-time", type=bounded_integer(1, 10800), default=300)
    run.add_argument("--output-dir", type=Path, default=ROOT / "artifacts/dam")
    status = commands.add_parser("job", help="Query an existing job without resubmitting")
    status.add_argument("job_id")
    status.add_argument("--wait", type=bounded_integer(0, 300), default=0)
    status.add_argument("--output", type=Path)
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
        if args.command == "doctor":
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
