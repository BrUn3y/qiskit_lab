"""Completed scientific receipts survive independent presentation failures."""
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from qiskit_lab import cli, execution_visualization, experiment_engine


def run_command(command, output):
    options = ["--example", "bell"] if command == "execute" else ["--request", "2-node"]
    return cli.parser().parse_args([command, *options, "--shots", "32", "--output-dir", str(output)])


def saved_result(output, command):
    filename = "receipt.json" if command == "execute" else "experiment.json"
    path, = output.glob(f"*/{filename}")
    return path, json.loads(path.read_text())


def assert_science(data, command):
    assert data["status"] == "DONE"
    assert data["hardware"] is False
    assert data["backend"] == "local_statevector_simulator"
    assert data["shots"] == sum(data["counts"].values()) == 32
    assert data["seed"] == 42
    assert data["completed_at"]
    assert data["duration_seconds"] >= 0
    assert data["comparison_metadata"]
    assert data["versions"]
    directory = Path(data["artifacts"])
    assert data["run_id"] == directory.name
    assert Path(data["qiskit_path"]).is_file()
    assert (directory / ("circuit.qasm" if command == "execute" else "optimized.qasm")).is_file()
    if command == "qaoa":
        assert data["exact_cut"] == 1
        assert data["best_bitstring"] in data["counts"]
        assert data["best_cut"] == experiment_engine.cut_value(int(data["best_bitstring"], 2), data["edges"])
        assert len(data["optimization_trace"]) == 221
        assert data["approximation_ratio"] == data["expected_cut"] / data["exact_cut"]


def patch_renderer(monkeypatch, command, render):
    module = execution_visualization if command == "execute" else experiment_engine
    name = "render_execution_dashboard" if command == "execute" else "_render_dashboard"
    monkeypatch.setattr(module, name, render)


@pytest.mark.parametrize("command", ["execute", "qaoa"])
@pytest.mark.parametrize("failure", ["render", "missing", "copy", "replace", "cleanup"])
@pytest.mark.parametrize("html_failure", [False, True])
def test_science_is_durable_before_presentation_and_failures_are_independent(
    monkeypatch, tmp_path, command, failure, html_failure,
):
    output = tmp_path / "results"
    image = tmp_path / "temporary.png"
    service = Mock(side_effect=AssertionError("Presentation recovery must not query IBM"))
    monkeypatch.setattr(cli, "runtime_service", service)

    def render(*args, **kwargs):
        _, saved = saved_result(output, command)
        assert_science(saved, command)
        assert "dashboard_path" not in saved
        assert "report_path" not in saved
        if failure == "render":
            raise RuntimeError("private-rendering-message")
        if failure != "missing":
            image.write_bytes(b"rendered-dashboard")
        return image

    patch_renderer(monkeypatch, command, render)
    if failure == "copy":
        def copy(source, destination):
            Path(destination).write_bytes(b"partial-png")
            raise OSError("private-copy-message")

        monkeypatch.setattr(cli.shutil, "copyfile", copy)
    if failure == "replace":
        replace = Path.replace

        def replace_png(path, destination):
            if Path(destination).suffix == ".png":
                raise OSError("private-replace-message")
            return replace(path, destination)

        monkeypatch.setattr(Path, "replace", replace_png)
    if failure == "cleanup":
        unlink = Path.unlink

        def cleanup(path, *args, **kwargs):
            if path == image:
                raise PermissionError("private-cleanup-message")
            return unlink(path, *args, **kwargs)

        monkeypatch.setattr(Path, "unlink", cleanup)
    if html_failure:
        def failed_html(data, directory):
            # The real renderer sets these fields before its final atomic write.
            data.update(report_path=str(directory / "missing.html"),
                        report_filename="missing.html", report_title="Missing report")
            raise ValueError("private-html-message")

        monkeypatch.setattr(cli, "write_report", failed_html)

    result = getattr(cli, command)(run_command(command, output))
    path, saved = saved_result(output, command)
    assert saved == json.loads(json.dumps(result))
    assert_science(saved, command)
    expected_error = {"render": "RuntimeError", "missing": "FileNotFoundError",
                      "cleanup": "PermissionError"}.get(failure, "OSError")
    assert result["dashboard_error"] == expected_error
    assert "private-" not in path.read_text()
    if failure == "cleanup":
        assert Path(result["dashboard_path"]).read_bytes() == b"rendered-dashboard"
        assert image.is_file()
    else:
        assert "dashboard_path" not in result
        assert not list(path.parent.glob("*.png"))
        assert not image.exists()
    assert not list(path.parent.glob(".*.tmp"))
    if html_failure:
        assert result["report_error"] == "ValueError"
        assert not {"report_path", "report_filename", "report_title"} & result.keys()
    else:
        assert "report_error" not in result
        assert Path(result["report_path"]).is_file()
        if failure != "cleanup":
            assert "data:image/png;base64," not in Path(result["report_path"]).read_text()
    service.assert_not_called()


@pytest.mark.parametrize("command", ["execute", "qaoa"])
def test_abrupt_rendering_interruption_leaves_completed_receipt(monkeypatch, tmp_path, command):
    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt

    patch_renderer(monkeypatch, command, interrupt)
    with pytest.raises(KeyboardInterrupt):
        getattr(cli, command)(run_command(command, tmp_path))
    _, saved = saved_result(tmp_path, command)
    assert_science(saved, command)
    assert "dashboard_path" not in saved
    assert "report_path" not in saved


@pytest.mark.parametrize("command", ["execute", "qaoa"])
def test_success_retains_real_png_and_report_fields(monkeypatch, tmp_path, command):
    image = tmp_path / "temporary.png"

    def render(*args, **kwargs):
        _, saved = saved_result(tmp_path, command)
        assert_science(saved, command)
        image.write_bytes(b"rendered-dashboard")
        return image

    patch_renderer(monkeypatch, command, render)
    result = getattr(cli, command)(run_command(command, tmp_path))
    _, saved = saved_result(tmp_path, command)
    assert json.loads(json.dumps(result)) == saved
    assert_science(result, command)
    assert Path(result["dashboard_path"]).read_bytes() == b"rendered-dashboard"
    assert Path(result["dashboard_path"]).name == ("results.png" if command == "execute" else "qaoa.png")
    assert Path(result["report_path"]).is_file()
    assert Path(result["report_path"]).name == result["report_filename"]
    assert result["report_title"] == result["title"]
    assert "dashboard_error" not in result
    assert "report_error" not in result
    assert not image.exists()
