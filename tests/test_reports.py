"""Reporting contracts: offline delivery, safe markup, and durable job tracking."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from qiskit_lab import cli
from qiskit_lab.job_tracking import poll_jobs
from qiskit_lab.reports import write_report


def test_self_contained_report_escapes_untrusted_job_data(tmp_path):
    malicious = '</script><script>alert("unsafe")</script>'
    data = {"status": "DONE", "hardware": True, "job_id": malicious, "backend": malicious,
            "counts": [{"00": 12, "11": 4}, {"01": 16}], "title": malicious}
    path = write_report(data, tmp_path)
    assert path.parent == tmp_path
    assert '/' not in path.name and '\\' not in path.name
    html = path.read_text()
    assert malicious not in html
    assert '&lt;script&gt;' in html
    assert html.count('data-publication=') == 2
    assert 'Shannon entropy 0.811 bits' in html
    assert 'data:font/woff2;base64,' in html
    assert 'data:application/json;base64,' in html
    assert 'https://1.www.s81c.com' not in html
    assert '<script src=' not in html
    assert 'IBM Carbon Design System' in html
    assert 'cds--data-table' in html
    assert 'No circuit was reconstructed' in html


def test_reports_require_a_terminal_status(tmp_path):
    with pytest.raises(ValueError, match='terminal'):
        write_report({"status": "RUNNING"}, tmp_path)
    assert not list(tmp_path.glob('*.html'))


def fake_job(monkeypatch, status="DONE"):
    job = Mock()
    job.job_id.return_value = "tracked-job"
    job.backend.return_value = SimpleNamespace(name="ibm_test")
    job.status.return_value = status
    job.metrics.return_value = {"timestamps": {"created": "2026-11-04T00:00:00Z", "finished": "2026-11-04T00:01:00Z"},
                                "usage": {"quantum_seconds": 1.25, "private": "do-not-export"},
                                "executions": 1, "private": "do-not-export"}
    monkeypatch.setattr(cli, 'runtime_service', lambda: SimpleNamespace(job=lambda _: job))
    monkeypatch.setattr(cli, 'counts_from_result', lambda _: [{"00": 30, "11": 34}])
    return job


def tracked_receipt(tmp_path):
    directory = tmp_path / 'accepted-run'
    cli.save_json(directory / 'receipt.json', {"hardware": True, "job_id": "tracked-job", "status": "SUBMITTED",
                                             "title": "Bell circuit",
                                             "shots": 64, "qubits": 2, "backend": "ibm_test", "artifacts": str(directory)})
    (directory / 'circuit.qasm').write_text('OPENQASM 3.0; qubit[2] q;')
    return directory


def test_completed_hardware_retains_receipt_and_renders_report(monkeypatch, tmp_path):
    job = fake_job(monkeypatch)
    directory = tracked_receipt(tmp_path)
    args = cli.parser().parse_args(['job', 'tracked-job', '--output-dir', str(tmp_path)])
    result = cli.inspect_job(args)
    assert Path(result['report_path']) == directory / 'tracked-job-bell-circuit.html'
    assert result['report_filename'] == 'tracked-job-bell-circuit.html'
    assert result['report_title'] == 'Bell circuit'
    assert result['shots'] == 64
    assert result['qubits'] == 2
    assert result['completed_at'] == '2026-11-04T00:01:00Z'
    assert result['metrics']['usage'] == {'quantum_seconds': 1.25}
    html = Path(result['report_path']).read_text()
    assert 'do-not-export' not in html
    assert 'Download circuit.qasm' in html
    assert json.loads((directory / 'receipt.json').read_text())['counts'] == [{'00': 30, '11': 34}]
    job.result.assert_called_once()


@pytest.mark.parametrize('status', ['ERROR', 'CANCELLED'])
def test_terminal_failure_reports_without_fabricated_counts(monkeypatch, tmp_path, status):
    job = fake_job(monkeypatch, status)
    args = cli.parser().parse_args(['job', 'tracked-job', '--wait', '1', '--output-dir', str(tmp_path)])
    result = cli.inspect_job(args)
    assert 'counts' not in result
    assert 'No measurement results' in Path(result['report_path']).read_text()
    job.result.assert_not_called()


def test_poller_retries_result_download_and_acknowledges_delivery(monkeypatch, tmp_path):
    job = fake_job(monkeypatch)
    directory = tracked_receipt(tmp_path)
    args = cli.parser().parse_args(['poll-jobs', '--output-dir', str(tmp_path)])
    job.result.side_effect = TimeoutError('sensitive SDK text')
    first = poll_jobs(args)
    assert first['notifications'] == []
    assert not list(directory.glob('*.html'))
    job.result.side_effect = None
    second = poll_jobs(args)
    assert second['notifications'][0]['job_id'] == 'tracked-job'
    assert (directory / 'tracked-job-bell-circuit.html').exists()
    assert second['notifications'][0]['report_filename'] == 'tracked-job-bell-circuit.html'
    assert second['notifications'][0]['report_title'] == 'Bell circuit'
    poll_jobs(args)  # Repeated ticks retain one notification until acknowledged.
    assert len(poll_jobs(args)['notifications']) == 1
    calls = job.result.call_count
    args.ack = ['tracked-job']
    assert poll_jobs(args)['notifications'] == []
    args.ack = []
    assert poll_jobs(args)['notifications'] == []
    assert job.result.call_count == calls
    assert 'sensitive SDK text' not in (directory / 'tracked-job-bell-circuit.html').read_text()


def test_notification_survives_report_written_before_poller_restart(monkeypatch, tmp_path):
    fake_job(monkeypatch)
    tracked_receipt(tmp_path)
    cli.inspect_job(cli.parser().parse_args(['job', 'tracked-job', '--output-dir', str(tmp_path)]))
    result = poll_jobs(cli.parser().parse_args(['poll-jobs', '--output-dir', str(tmp_path)]))
    assert len(result['notifications']) == 1


def test_legacy_report_migrates_offline_and_preserves_acknowledgement(monkeypatch, tmp_path):
    directory = tracked_receipt(tmp_path)
    receipt = json.loads((directory / 'receipt.json').read_text())
    receipt.update(status='DONE', counts=[{'00': 30, '11': 34}], report_path=str(directory / 'report.html'))
    cli.save_json(directory / 'receipt.json', receipt)
    (directory / 'report.html').write_text('Previously delivered report')
    cli.save_json(tmp_path / 'job-notifications.json', [{
        'event_id': 'tracked-job:DONE', 'job_id': 'tracked-job', 'status': 'DONE',
        'report_path': receipt['report_path'], 'acknowledged_at': '2026-11-04T00:02:00Z',
    }])
    service = Mock(side_effect=AssertionError('Cached report migration must not contact IBM'))
    monkeypatch.setattr(cli, 'runtime_service', service)
    result = poll_jobs(cli.parser().parse_args(['poll-jobs', '--output-dir', str(tmp_path)]))
    assert result['notifications'] == []
    updated = json.loads((directory / 'receipt.json').read_text())
    assert updated['counts'] == receipt['counts']
    assert Path(updated['report_path']).name == 'tracked-job-bell-circuit.html'
    assert Path(updated['report_path']).is_file()
    assert (directory / 'report.html').read_text() == 'Previously delivered report'
    entry = json.loads((tmp_path / 'job-notifications.json').read_text())[0]
    assert entry['report_path'] == updated['report_path']
    assert entry['acknowledged_at'] == '2026-11-04T00:02:00Z'
    service.assert_not_called()


def test_missing_named_report_is_retried_even_when_a_legacy_file_exists(monkeypatch, tmp_path):
    job = fake_job(monkeypatch)
    directory = tracked_receipt(tmp_path)
    receipt = json.loads((directory / 'receipt.json').read_text())
    receipt.update(status='DONE', report_path=str(directory / 'tracked-job-bell-circuit.html'))
    cli.save_json(directory / 'receipt.json', receipt)
    (directory / 'report.html').write_text('Legacy report')
    result = poll_jobs(cli.parser().parse_args(['poll-jobs', '--output-dir', str(tmp_path)]))
    assert Path(result['notifications'][0]['report_path']).is_file()
    job.result.assert_called_once()


@pytest.mark.parametrize('identifier,title', [
    ('../../outside', '../Bell / circuit'), ('job-1', 'é' * 300), ('<>', '!!!'),
])
def test_report_filename_is_bounded_and_stays_in_its_run_directory(tmp_path, identifier, title):
    path = write_report({'status': 'DONE', 'hardware': True, 'job_id': identifier, 'title': title}, tmp_path)
    assert path.parent == tmp_path
    assert len(path.name) < 180
    assert not path.name.startswith('.')
    assert all(char.isascii() and (char.isalnum() or char in '-.') for char in path.name)


def test_existing_job_accepts_an_explicit_circuit_description(monkeypatch, tmp_path):
    fake_job(monkeypatch)
    result = cli.inspect_job(cli.parser().parse_args([
        'job', 'tracked-job', '--title', 'Grover search circuit', '--output-dir', str(tmp_path)]))
    assert result['report_filename'] == 'tracked-job-grover-search-circuit.html'
    assert result['title'] == 'Grover search circuit'


def test_precheck_skips_model_when_no_job_completes(monkeypatch, tmp_path, capsys):
    job = fake_job(monkeypatch, 'RUNNING')
    tracked_receipt(tmp_path)
    assert cli.main(['poll-jobs', '--precheck', '--output-dir', str(tmp_path)]) == 1
    assert json.loads(capsys.readouterr().out)['notifications'] == []
    job.result.assert_not_called()


def test_report_render_failure_preserves_measurements(monkeypatch, tmp_path):
    fake_job(monkeypatch)
    directory = tracked_receipt(tmp_path)
    monkeypatch.setattr(cli, 'write_report', Mock(side_effect=OSError('private-path')))
    result = cli.inspect_job(cli.parser().parse_args(['job', 'tracked-job', '--output-dir', str(tmp_path)]))
    assert result['report_error'] == 'OSError'
    assert 'private-path' not in str(result)
    assert json.loads((directory / 'receipt.json').read_text())['counts'] == [{'00': 30, '11': 34}]


def test_unavailable_ids_do_not_starve_later_jobs(monkeypatch, tmp_path):
    job = fake_job(monkeypatch)
    job.job_id.return_value = 'job-10'

    def lookup(job_id):
        if job_id != 'job-10':
            raise ConnectionError('private-sdk-error')
        return job

    monkeypatch.setattr(cli, 'runtime_service', lambda: SimpleNamespace(job=lookup))
    for index in range(11):
        cli.save_json(tmp_path / f'run-{index:02d}' / 'receipt.json',
                      {'job_id': f'job-{index:02d}', 'hardware': True, 'status': 'SUBMITTED'})
    args = cli.parser().parse_args(['poll-jobs', '--output-dir', str(tmp_path)])
    assert len(poll_jobs(args)['errors']) == 10
    assert poll_jobs(args)['notifications'][0]['job_id'] == 'job-10'
