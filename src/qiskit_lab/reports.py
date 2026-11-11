"""Offline IBM Carbon reports built only from explicit, public job data.

No remote scripts, credential files, environment dumps, or SDK account objects
are read. Report data comes from the CLI's curated scientific receipt.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import re
import unicodedata
import uuid
from datetime import UTC, datetime
from html import escape
from importlib.resources import files
from pathlib import Path
from urllib.parse import quote

from qiskit_lab.chsh_reporting import prepare_chsh_report

CARBON_VERSION = "1.119.0"


def _asset(name):
    return files("qiskit_lab").joinpath("assets", name).read_text(encoding="utf-8")


def _json(value):
    return json.dumps(value, indent=2, default=str, ensure_ascii=True)


def _download(label, filename, content, mime="application/json"):
    encoded = base64.b64encode(content.encode()).decode()
    return (f'<a class="cds--btn cds--btn--tertiary cds--btn--sm" download="{escape(filename)}" '
            f'href="data:{mime};base64,{encoded}">{escape(label)} <span aria-hidden="true">↓</span></a>')


def _display(value):
    if value is None:
        return "Not available"
    if isinstance(value, (dict, list, tuple)):
        return _json(value)
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def _code_source(title, content, identifier, description):
    """Use native disclosure controls so source previews also work offline without JS."""
    lines = content.splitlines()
    label = escape(title)
    code = f'<pre class="source-code" aria-label="{label}"><code>{escape(content)}</code></pre>'
    if len(lines) > 15:
        preview = escape('\n'.join(lines[:15]))
        code = f'''<div class="code-viewer"><details class="code-toggle">
        <summary class="cds--btn cds--btn--tertiary cds--btn--sm">
        <span class="expand-code">Expand all {len(lines)} lines</span>
        <span class="collapse-code">Show first 15 lines</span><span class="sr-only"> of {label}</span></summary>
        {code}</details><pre class="code-preview" aria-label="{label}, first 15 lines"><code>{preview}</code></pre></div>'''
    return (f'<section class="code-source" id="{identifier}"><h3>{label}</h3>'
            f'<p class="muted">{escape(description)}</p>{code}</section>')


def _details(data, labels):
    return '<dl class="facts">' + "".join(
        f'<div><dt>{escape(label)}</dt><dd>{escape(_display(data[key]))}</dd></div>'
        for key, label in labels if key in data
    ) + '</dl>'


def _chart(counts, index):
    rows = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))[:16]
    total = sum(counts.values())
    height = max(130, len(rows) * 32 + 38)
    parts = [f'<svg viewBox="0 0 800 {height}" role="img" aria-labelledby="chart-title-{index}" '
             f'class="distribution"><title id="chart-title-{index}">Measurement probabilities, publication {index + 1}'
             '</title><line x1="150" y1="8" x2="150" y2="' + str(height - 25) + '" class="axis"/>']
    for row, (state, count) in enumerate(rows):
        y = row * 32 + 12
        probability = count / total if total else 0
        short = state if len(state) <= 18 else state[:7] + "…" + state[-7:]
        parts.append(f'<text x="134" y="{y + 17}" text-anchor="end">{escape(short)}</text>'
                     f'<rect x="151" y="{y}" width="{probability * 530:.3f}" height="24" class="bar">'
                     f'<title>{escape(state)}: {count:,} shots ({probability:.2%})</title></rect>'
                     f'<text x="{min(700, 161 + probability * 530):.3f}" y="{y + 17}">{probability:.2%}</text>')
    parts.append(f'<text x="150" y="{height - 4}" class="axis-label">Probability · top 16 observed states</text></svg>')
    return "".join(parts)


def _publication(counts, index):
    total = sum(counts.values())
    entropy = -sum((v / total) * math.log2(v / total) for v in counts.values() if v) if total else 0
    rows = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    table = "".join(f'<tr><td><code>{escape(s)}</code></td><td>{v:,}</td><td>{v / total:.4%}</td></tr>'
                    for s, v in rows[:50]) if total else ""
    return f'''<section class="publication" data-publication="{index}">
      <div class="section-heading"><div><p class="eyebrow">Measurement results · publication {index + 1}</p>
      <h2>Observed distribution</h2><p class="muted">{total:,} measured shots · {len(counts):,} observed states ·
      Shannon entropy {entropy:.3f} bits</p></div>
      <div class="controls enhancement"><label class="cds--label" for="mode-{index}">Chart value</label>
      <select id="mode-{index}" class="cds--select-input chart-mode"><option value="probability">Probability</option>
      <option value="counts">Counts</option></select></div></div>
      <div class="chart">{_chart(counts, index)}</div>
      <p class="muted caption">Bitstrings preserve joint measurement-register correlations. Bars show up to 16 states;
      the full distribution is included in the JSON download.</p>
      <div class="table-toolbar enhancement"><label class="cds--label" for="search-{index}">Filter bitstrings</label>
      <input class="cds--text-input state-filter" id="search-{index}" type="search" placeholder="Search an observed state">
      </div><div class="table-scroll"><table class="cds--data-table cds--data-table--md">
      <caption class="sr-only">All observed measurement states for publication {index + 1}</caption>
      <thead><tr><th scope="col">Bitstring</th><th scope="col">Counts</th><th scope="col">Probability</th></tr></thead>
      <tbody>{table}</tbody></table></div>
      <div class="pagination enhancement"><span class="page-info" aria-live="polite"></span><div>
      <button class="cds--btn cds--btn--ghost cds--btn--sm previous" type="button">Previous</button>
      <button class="cds--btn cds--btn--ghost cds--btn--sm next" type="button">Next</button></div></div>
      <noscript><p>Showing the first 50 states. Download JSON for all results.</p></noscript></section>'''


def _optimization(data):
    if "optimization_trace" not in data:
        return ""
    trace = data["optimization_trace"]
    maximum = max([float(data.get("exact_cut", 0)), *trace, 1])
    points = " ".join(f"{60 + i * 680 / max(1, len(trace) - 1):.2f},{220 - v / maximum * 180:.2f}"
                      for i, v in enumerate(trace))
    return f'''<section class="panel"><p class="eyebrow">Optimization · QAOA Max-Cut</p><h2>Convergence and validation</h2>
    <p class="muted">Best statevector expectation across {len(trace)} parameter evaluations. This is a local p=1 experiment.</p>
    <svg class="trace" viewBox="0 0 800 260" role="img" aria-label="Best expected cut during optimization">
    <line x1="60" y1="220" x2="740" y2="220" class="axis"/>
    <line x1="60" y1="40" x2="60" y2="220" class="axis"/>
    <text x="48" y="46" text-anchor="end">{maximum:g}</text><text x="48" y="224" text-anchor="end">0</text>
    <polyline points="{points}" fill="none" stroke="#78a9ff" stroke-width="2"/>
    <text x="60" y="249">Evaluation 1</text><text x="740" y="249" text-anchor="end">Evaluation {len(trace)}</text></svg>
    {_details(data, [('node_count', 'Graph nodes'), ('edges', 'Graph edges'), ('gamma', 'Optimized gamma'),
                    ('beta', 'Optimized beta'), ('expected_cut', 'Statevector expected cut'),
                    ('exact_cut', 'Exact classical optimum'), ('approximation_ratio', 'Expectation / exact optimum'),
                    ('best_bitstring', 'Best sampled solution'), ('best_cut', 'Best sampled cut')])}</section>'''


def _chsh(data):
    if "correlators" not in data:
        return ""
    rows = []
    terms = []
    for index, row in enumerate(data["correlators"]):
        label = escape(row["label"])
        sign = row["sign_in_chsh"]
        terms.append(("− " if sign < 0 else ("+ " if index else "")) + f"E({label})")
        angles = [f"{math.degrees(row[key]):.1f}°" if row.get(key) is not None else "Not available"
                  for key in ("alice_angle_rad", "bob_angle_rad")]
        theory = f'{row["theory"]:+.4f}' if row.get("theory") is not None else "Not available"
        rows.append(f'<tr><td>{label}</td><td>{angles[0]}</td><td>{angles[1]}</td><td>{sign:+d}</td>'
                    f'<td>{row["correlator"]:+.4f} ± {row["uncertainty"]:.4f}</td><td>{theory}</td>'
                    f'<td>{row["shots"]:,}</td></tr>')
    warnings = ''.join(f'<p class="muted">{escape(warning)}</p>' for warning in data["sampling_warnings"])
    labels = [("chsh_ideal", "Ideal theoretical S"), ("classical_bound", "Classical bound |S|"),
              ("tsirelson_bound", "Quantum maximum |S|")]
    model = data.get("noise_model") or {}
    if model.get("type") == "single_qubit_depolarizing" and data.get("hardware") is False:
        labels.append(("chsh_theory", "Noise-model prediction S"))
    labels.append(("measurement_convention", "Recorded measurement convention"))
    comparison = "Estimated |S| exceeds 2." if data["violated"] else "Estimated |S| does not exceed 2."
    return f'''<section class="panel"><p class="eyebrow">Bell inequality analysis</p><h2>CHSH measurement correlators</h2>
    <p>Recomputed from observed counts: <strong>S = {data['chsh_value']:+.4f} ± {data['chsh_uncertainty']:.4f}</strong>.
    {comparison}</p><p class="muted">Independent-shot standard error, ±1σ. {escape(data['chsh_uncertainty_assumption'])}</p>
    {warnings}<p>Sign convention: S = {' '.join(terms)}</p>
    <p class="muted">E = (N00 + N11 − N01 − N10) / N. Angles use the convention recorded by the experiment.</p>
    <div class="table-scroll"><table class="cds--data-table cds--data-table--md">
    <caption class="sr-only">CHSH correlations and observed shots by configuration</caption>
    <thead><tr><th scope="col">Config</th><th scope="col">Alice θ</th><th scope="col">Bob θ</th>
    <th scope="col">Sign</th><th scope="col">E ± σ</th><th scope="col">Recorded theoretical E</th>
    <th scope="col">Observed shots</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
    {_details(data, labels)}{_details(model, [('type', 'Recorded noise model'), ('parameter_p', 'Noise parameter p')])}
    <p class="muted">Ideal theory is a reference, not a calibrated prediction of hardware noise.
    Imported receipts are not independently verified with IBM.</p></section>'''


def _report_title(data):
    if data.get("title"):
        return str(data["title"])
    if "correlators" in data:
        return "CHSH Bell inequality experiment"
    if data.get("hardware") is True:
        return "IBM Quantum execution"
    return "Local quantum experiment" if data.get("hardware") is False else "Quantum experiment"


def report_filename(data, directory):
    """Identify a report by its recorded job/run and circuit, without unsafe paths."""
    def slug(value, fallback, limit=80):
        text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
        return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")[:limit].rstrip("-") or fallback

    identifier = data.get("job_id") or data.get("run_id") or Path(directory).name
    title = _report_title(data)
    return f"{slug(identifier, 'run')}-{slug(str(title).lower(), 'quantum-circuit')}.html"


def write_report(data, directory):
    """Write a standalone report atomically; only terminal runs receive reports."""
    if data.get("status") not in {"DONE", "ERROR", "CANCELLED"}:
        raise ValueError("A completion report requires a terminal job state.")
    if "hardware" in data and type(data["hardware"]) is not bool:
        raise ValueError("The hardware field must be a boolean when provided.")
    prepare_chsh_report(data)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / report_filename(data, directory)
    title = _report_title(data)
    data.update(report_path=str(path), report_filename=path.name, report_title=title)
    raw = ([row["counts"] for row in data["correlators"]] if "correlators" in data else data.get("counts", []))
    counts = [raw] if isinstance(raw, dict) else raw
    measured = sum(sum(publication.values()) for publication in counts)
    state_count = sum(len(publication) for publication in counts)
    job_id = str(data.get("job_id") or data.get("run_id") or directory.name)
    hardware = data.get("hardware")
    execution_label = ("IBM Quantum hardware" if hardware is True else
                       "Local simulation" if hardware is False else "Execution type unavailable")
    displayed_id = _display(data.get("job_id")) if hardware is True else job_id
    summary = (f'<div><p>Observed shots</p><strong>{measured:,}</strong></div>'
               f'<div><p>Circuit qubits</p><strong>{escape(_display(data.get("qubits")))}</strong></div>'
               f'<div><p>Circuit depth</p><strong>{escape(_display(data.get("depth")))}</strong></div>'
               f'<div><p>Observed states</p><strong>{state_count:,}</strong></div>')
    if "correlators" in data:
        shot_counts = set(data["observed_shots_per_configuration"])
        value = f"{next(iter(shot_counts)):,}" if len(shot_counts) == 1 else "Varies by configuration"
        summary = (f'<div><p>CHSH value S</p><strong>{data["chsh_value"]:+.4f}</strong></div>'
                   f'<div><p>Independent-shot standard error ±1σ</p><strong>{data["chsh_uncertainty"]:.4f}</strong></div>'
                   f'<div><p>Observed shots per configuration</p><strong>{value}</strong></div>'
                   f'<div><p>Observed shots</p><strong>{measured:,}</strong></div>')
    status = data["status"]
    generated = datetime.now(UTC).isoformat()
    downloads = _download("Download result JSON", f"{path.stem}-results.json", _json(data))
    source_sections = []
    recorded_sources = set()
    for filename, label, description in (
        ("circuit.py", "Qiskit Python script",
         "Generated script that rebuilds the recorded circuit using Qiskit. It does not submit a job; "
         "it is not the original author's Python source."),
        ("circuit.qasm", "OpenQASM source", "Recorded circuit before hardware transpilation or local execution."),
        ("optimized.qasm", "Optimized OpenQASM source", "Optimized QAOA circuit used for local sampling."),
        ("isa-circuit.qasm", "Transpiled OpenQASM for hardware",
         "Backend ISA circuit saved before submission to IBM Quantum."),
    ):
        source = directory / filename
        if source.is_file() and not source.is_symlink():
            content = source.read_text(encoding="utf-8")
            downloads += _download("Download " + filename, filename, content, "text/plain")
            source_sections.append(_code_source(label, content, filename.replace('.', '-'), description))
            recorded_sources.add(filename)
    for index, row in enumerate(data.get("correlators", []), start=1):
        for key, extension, source_title, description in (
            ("qasm", "qasm", "OpenQASM", "Recorded measurement circuit for this CHSH configuration."),
            ("qiskit_source", "py", "Qiskit Python script",
             "Recorded reconstruction for this configuration; not the original author's Python source."),
        ):
            source = row.get(key)
            if isinstance(source, str) and source:
                filename = f"configuration-{index}.{extension}"
                label = f"{source_title} - configuration {row['label']}"
                downloads += _download("Download " + filename, filename, source, "text/plain")
                source_sections.append(_code_source(label, source, f"configuration-{index}-{extension}", description))
                recorded_sources.add(f"circuit.{extension}")
    circuit_text_path = directory / "circuit.txt"
    circuit_text = (circuit_text_path.read_text(encoding="utf-8")
                    if circuit_text_path.is_file() and not circuit_text_path.is_symlink() else "")
    circuit_section = '<p class="muted">The source circuit is unavailable for this job. No circuit was reconstructed.</p>'
    if source_sections or circuit_text:
        circuit_section = (f'<pre class="circuit" aria-label="Quantum circuit">{escape(circuit_text)}</pre>' if circuit_text else "")
        circuit_section += ''.join(source_sections)
        if "circuit.py" not in recorded_sources:
            circuit_section += '<p class="muted">A Qiskit Python script was not recorded for this job.</p>'
    dashboard = ""
    # Only known images in this run directory can be embedded.
    for filename in ("results.png", "qaoa.png"):
        image = directory / filename
        if image.is_file() and not image.is_symlink():
            encoded = base64.b64encode(image.read_bytes()).decode()
            dashboard = (f'<details class="panel"><summary>Scientific dashboard</summary>'
                         f'<img class="dashboard" alt="Circuit and scientific results dashboard" '
                         f'src="data:image/png;base64,{encoded}"></details>')
            break
    publications = "".join(_publication(c, i) for i, c in enumerate(counts))
    if not publications:
        publications = ('<section class="panel"><h2>No measurement results</h2>'
                        '<p>This job ended without available counts. No measurement values have been inferred.</p></section>')
    metrics = _details(data.get("metrics", {}), [("timestamps", "IBM job timestamps (UTC)"),
                       ("usage", "IBM reported usage"), ("executions", "Executions")])
    status_label = {"DONE": "Completed", "ERROR": "Failed", "CANCELLED": "Cancelled"}[status]
    provenance = ('<p class="muted caption">Generated offline from an imported receipt. '
                  'Job authenticity and status were not verified with IBM.</p>'
                  if data.get("report_source") == "imported_receipt_not_verified_online" else "")
    ibm_link = (f'<a class="cds--link" href="https://quantum.cloud.ibm.com/jobs/{quote(job_id, safe="")}" '
                'target="_blank" rel="noopener noreferrer">Open in IBM Quantum ↗</a>') if hardware else ""
    script_data = _json(counts).replace('&', r'\u0026').replace('<', r'\u003c').replace('>', r'\u003e')
    body = f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <meta name="referrer" content="no-referrer">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline';
    script-src 'unsafe-inline'; img-src data:; font-src data:; base-uri 'none'; form-action 'none'">
    <title>{escape(title)} | Qiskit Lab</title>
    <style>{_asset('fonts.css')}\n{_asset('carbon.css')}\n{_asset('report.css')}</style></head><body>
    <a href="#main" class="skip-link">Skip to report</a>
    <header class="app-header"><span>IBM Quantum <span class="brand-divider">/</span> <strong>Qiskit Lab</strong></span>
    <span class="header-note">Execution report</span></header>
    <main id="main"><section class="hero"><div class="hero-top"><p class="eyebrow">Quantum laboratory / Run report</p>
    <span class="cds--tag cds--tag--{'green' if status == 'DONE' else 'red'}">{status_label}</span></div>
    <h1>{escape(title)}</h1><p class="subtitle">{execution_label}
    <span aria-hidden="true"> · </span> {escape(str(data.get('backend', 'Not available')))}</p>
    <p class="run-id">{'Job' if hardware else 'Run'} <code>{escape(displayed_id)}</code></p>
    <div class="downloads">{downloads}</div></section>
    <section class="metrics" aria-label="Run summary">
    {summary}</section>
    {_chsh(data)}<div class="report-grid"><div class="results">{publications}</div>
    <aside class="panel execution"><p class="eyebrow">Execution context</p><h2>Job details</h2>
    {_details(data, [('status', 'Runtime status'), ('backend', 'Backend'), ('shots', 'Requested shots per circuit'),
        ('created_at', 'Submitted / started (UTC)'), ('completed_at', 'Completed (UTC)'), ('queried_at', 'Last queried (UTC)'),
        ('duration_seconds', 'Local elapsed seconds'), ('max_execution_time', 'QPU execution limit (seconds)'),
        ('isa_qubits', 'ISA circuit qubits'), ('isa_depth', 'ISA circuit depth'), ('gate_counts', 'Source gate counts'),
        ('isa_gate_counts', 'ISA gate counts'), ('seed', 'Simulation seed'), ('versions', 'SDK versions')])}
    {provenance}
    {metrics}{ibm_link}<p class="muted caption">Missing fields are unavailable from this receipt or IBM.
    Observed shots describe returned counts, separately from requested shots. QPU usage is not a cost estimate.</p></aside></div>
    {_optimization(data)}<section class="panel"><p class="eyebrow">Reproducibility</p><h2>Circuit and source</h2>
    {circuit_section}</section>{dashboard}
    <section class="panel"><details><summary>Complete recorded job data</summary><pre>{escape(_json(data))}</pre></details></section>
    <details class="panel"><summary>Design and font licenses</summary>
    <pre>{escape(_asset('CARBON-LICENSE'))}</pre><pre>{escape(_asset('PLEX-LICENSE'))}</pre></details>
    <footer><span>Qiskit Lab · IBM Carbon Design System · @carbon/styles {CARBON_VERSION}</span>
    <span>Generated {escape(generated)} · UTC</span><p>Self-contained report. Styles, charts, results and available images
    are embedded; opening this file makes no external requests.</p></footer></main>
    <script type="application/json" id="report-data">{script_data}</script>
    <script>{_asset('report.js')}</script></body></html>'''
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(body, encoding="utf-8")
    temporary.replace(path)
    return path


def job_directory(base, job_id):
    """Stable filesystem-safe directory even for an externally supplied job ID."""
    return Path(base) / "jobs" / hashlib.sha256(job_id.encode()).hexdigest()[:24]
