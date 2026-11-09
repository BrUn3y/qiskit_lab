import json
from pathlib import Path
from unittest.mock import Mock

from qiskit_lab import cli

ROOT = Path(__file__).resolve().parents[1]


def test_documented_qasm_and_local_receipt_comparison(monkeypatch, tmp_path, capsys):
    service = Mock(side_effect=AssertionError("Documentation examples must not contact IBM"))
    monkeypatch.setattr(cli, "runtime_service", service)
    receipts = []
    for shots in (256, 1024):
        assert cli.main([
            "execute", "--qasm", str(ROOT / "docs/examples/bell.qasm"),
            "--shots", str(shots), "--output-dir", str(tmp_path),
        ]) == 0
        result = json.loads(capsys.readouterr().out)
        assert result["hardware"] is False
        assert result["backend"] == "local_statevector_simulator"
        assert result["status"] == "DONE"
        assert set(result["counts"]) == {"00", "11"}
        assert sum(result["counts"].values()) == shots
        assert "report_error" not in result
        assert Path(result["report_path"]).is_file()
        path = tmp_path / f"local-{shots}.json"
        path.write_text(json.dumps(result))
        receipts.append(str(path))

    assert cli.main(["compare", "--left", receipts[0], "--right", receipts[1]]) == 0
    comparison = json.loads(capsys.readouterr().out)
    assert comparison["compatibility"]["verified"] is True
    assert comparison["left_shots"] == 256
    assert comparison["right_shots"] == 1024
    assert 0 <= comparison["total_variation_distance"] <= 1
    service.assert_not_called()
