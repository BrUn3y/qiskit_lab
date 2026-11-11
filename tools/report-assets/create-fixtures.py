"""Generate synthetic native reports locally; never construct an IBM service."""
import argparse
import json
import shutil
from pathlib import Path

from qiskit import QuantumCircuit

from qiskit_lab import cli
from qiskit_lab.execution_visualization import render_execution_dashboard
from qiskit_lab.reports import write_report

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "artifacts" / "report-smoke" / "fixtures"


def main(output=OUTPUT):
    directory = output / "interactive"
    directory.mkdir(parents=True, exist_ok=True)
    source = "\n".join(f'# Synthetic source {index}: <source> & "quoted"' for index in range(24)) + "\n"
    qasm = "OPENQASM 3.0;\nqubit[2] q;\nh q[0];\ncx q[0], q[1];\n"
    (directory / "circuit.py").write_text(source, encoding="utf-8")
    (directory / "circuit.qasm").write_text(qasm, encoding="utf-8")
    circuit = QuantumCircuit(2)
    circuit.h(0)
    circuit.cx(0, 1)
    image = render_execution_dashboard(
        circuit, {"00": 3, "11": 1}, backend_name="synthetic_fixture", job_id="synthetic-fixture", shots=4,
    )
    try:
        shutil.copyfile(image, directory / "results.png")
    finally:
        image.unlink(missing_ok=True)
    data = {
        "status": "DONE", "hardware": False, "backend": "synthetic_fixture",
        "run_id": "synthetic-fixture", "title": "Synthetic report regression fixture",
        "counts": [{f"{index:06b}": 64 - index for index in range(64)}, {"00": 3, "11": 1}],
    }
    report = write_report(data, directory)
    manifest = {"interactive": str(report), "data": data, "source": source, "qasm": qasm}
    chsh = cli.chsh(cli.parser().parse_args([
        "chsh", "--shots", "64", "--title", "Synthetic CHSH regression fixture",
        "--output-dir", str(output / "chsh"),
    ]))
    manifest.update(chsh=chsh["report_path"], chsh_data=chsh)
    for status in ("ERROR", "CANCELLED"):
        manifest[status] = str(write_report(
            {"status": status, "hardware": True, "backend": "synthetic_fixture", "job_id": "synthetic-" + status},
            output / status,
        ))
    output.mkdir(parents=True, exist_ok=True)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"fixtures": str(output), "synthetic": True}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    main(parser.parse_args().output_dir.resolve())
