#!/usr/bin/env python3
# This code is a part of Qiskit.
#
# (C) Copyright IBM 2026.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
"""Render registry.yaml as a human-readable markdown document.

The registry is the source of truth. This produces the shareable export for
documentation: a feature matrix, then per-cell notes explaining every place a
capability is lost between layers.

    python scripts/render_table.py            # write capabilities-table.md
    python scripts/render_table.py --check    # validate only, no output
    python scripts/render_table.py --stdout   # print instead of writing
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent.parent
REGISTRY = HERE / "registry.yaml"
DEFAULT_OUT = HERE / "capabilities-table.md"

LAYERS = ("engine", "python", "addon")

# Rendered glyphs. "partial" and "not-returned" are distinct from plain yes/no,
# and from each other: binding a keyword argument and losing data unrecoverably
# are different costs to the researcher. EDITING_THIS_SKILL.md says why that
# matters.
GLYPH = {
    "yes": "✅",
    "no": "❌",
    # Reached only by a `partial` cell with no blocker -- genuinely incomplete
    # support.
    "partial": "⚠️",
    "not-returned": "🚫",
    "unclear": "❔",
    "unknown": "❔",
    "n/a": "—",
}

# What `pip install <name>` actually does. The practical split is whether a
# toolchain is needed, so the renderer groups these accordingly.
PYPI_INSTALL = {
    "pure-python": ("pure Python", "no toolchain needed"),
    "wheels": ("wheels", "no toolchain needed"),
    "wheels-partial": ("partial wheels", "toolchain needed on uncovered platforms"),
    "compiles": ("source build", "toolchain needed"),
    "placeholder": ("name placeholder", "not installable"),
    "none": ("not on PyPI", "not installable"),
}

# How far a capability can be trusted, weakest to strongest. "It exists" and
# "it is correct" are different claims, and only the top two are safe to
# recommend without a caveat.
MATURITY = {
    "plumbing": ("🧱", "scaffolding only — no working end-to-end path"),
    "partial": ("◐", "works on some code paths and not others"),
    "supported": ("✅", "present and documented, no known defects"),
    "verified": ("✅✅", "exercised by tests or checked against a reference"),
}
MATURITY_ORDER = ["plumbing", "partial", "supported", "verified"]
TRUSTWORTHY = {"supported", "verified"}

# Blockers a researcher cannot argue with. A layer carrying one of these, over
# a layer that does support the capability, is reporting "the solver does this,
# this interface cannot reach it" -- so the glyph shows the support and marks it
# unreachable, rather than reading as though the solver lacked the feature.
# `keyword-only` is absent deliberately: binding one argument reaches it, which
# is what ᵏ says.
UNREACHABLE = ("type-mismatch", "loop-contract", "not-wrapped")
BLOCKED_GLYPH = "⛔"

# `keyword-only` is frequently the API's design rather than a defect: the option
# exists and works, and the addon forwards no keywords, so the caller binds it
# at construction. These render as the supporting layer's glyph plus ᵏ, so the
# column reads "supported, bind the argument".
BINDABLE = ("keyword-only",)
BINDABLE_GLYPH = "ᵏ"

# Why a layer loses a capability, and whether the researcher can get it back.
BLOCKED_BY = {
    "keyword-only": ("option not forwarded", "fixable with functools.partial"),
    "not-returned": ("computed but discarded", "not fixable through the API"),
    "not-wrapped": ("absent from the bindings", "use the engine directly"),
    "type-mismatch": ("interface cannot express it", "not fixable without an interface change"),
    "loop-contract": ("cannot survive the loop", "call the solver directly"),
}


def load(path: Path = REGISTRY) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def cells_by_key(reg: dict) -> dict[tuple[str, str], dict]:
    out = {}
    for cell in reg["matrix"]:
        key = (cell["feature"], cell["solver"])
        if key in out:
            raise ValueError(f"duplicate matrix entry for {key}")
        out[key] = cell
    return out


def _walk_strings(node, path="registry"):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _walk_strings(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk_strings(v, f"{path}[{i}]")
    elif isinstance(node, str):
        yield path, node


def validate(reg: dict) -> list[str]:
    """Return a list of problems. Empty means the registry is coherent."""
    problems = []

    # A path on one person's disk is meaningless to every other reader. Cite the
    # upstream repo, or a file vendored under references/.
    for where, text in _walk_strings(reg):
        if "/home/" in text:
            problems.append(f"{where} contains a machine-local path: {text[:60]!r}")
        for token in text.split():
            cleaned = token.strip("`,;\"'()")
            if cleaned.startswith("~/"):
                problems.append(
                    f"{where} cites a home-relative path {cleaned!r} — use the "
                    "upstream repository or a references/ file"
                )
        if "references/" in text:
            for token in text.split():
                cleaned = token.strip("`,;\"'()")
                if cleaned.startswith("references/") and not (HERE / cleaned).exists():
                    problems.append(f"{where} cites missing reference {cleaned!r}")
    never_released = {
        s["id"] for s in reg["solvers"] if s.get("latest_release") in (None, "none")
    }
    solver_ids = {s["id"] for s in reg["solvers"]}
    feature_ids = {f["id"] for f in reg["features"]}
    seen = set()

    for cell in reg["matrix"]:
        key = (cell["feature"], cell["solver"])
        if cell["solver"] not in solver_ids:
            problems.append(f"unknown solver {cell['solver']!r} in {key}")
        if cell["feature"] not in feature_ids:
            problems.append(f"unknown feature {cell['feature']!r} in {key}")
        if key in seen:
            problems.append(f"duplicate entry {key}")
        seen.add(key)

        if not any(layer in cell for layer in LAYERS):
            problems.append(f"{key} declares no layer")

        for layer in LAYERS:
            spec = cell.get(layer)
            if spec is None:
                continue
            if "value" not in spec:
                problems.append(f"{key}.{layer} has no value")
                continue
            if spec["value"] not in GLYPH:
                problems.append(f"{key}.{layer} has unknown value {spec['value']!r}")
            conf = spec.get("confidence")
            if conf not in ("verified", "unverified", None):
                problems.append(f"{key}.{layer} has unknown confidence {conf!r}")
            if conf == "verified" and spec["value"] in ("unknown", "unclear"):
                problems.append(f"{key}.{layer} is verified but has value {spec['value']!r}")
            blocked = spec.get("blocked_by")
            if blocked is not None and blocked not in BLOCKED_BY:
                problems.append(f"{key}.{layer} has unknown blocked_by {blocked!r}")
            # A bindable blocker on a `yes` is the truthful combination: the
            # capability is supported and the caller passes the argument. Only
            # a blocker that actually withholds the capability conflicts with
            # a yes.
            if blocked and blocked not in BINDABLE and spec["value"] == "yes":
                problems.append(f"{key}.{layer} is blocked_by but still yes")
            disp = spec.get("display")
            if disp is not None and not isinstance(disp, str):
                problems.append(f"{key}.{layer} display is not a string: {disp!r}")
            if disp is not None and len(disp) > 40:
                problems.append(
                    f"{key}.{layer} display is {len(disp)} chars — too wide for a "
                    "table cell; move the detail to `detail`"
                )
            track = spec.get("tracking")
            if track is not None and not str(track).startswith("https://"):
                problems.append(f"{key}.{layer} tracking is not a URL: {track!r}")
            # An unverified cell must say what is unknown and what would
            # settle it. Without that it is indistinguishable from a verified
            # finding in the table, and a bare value nobody sourced tends to
            # outlive whatever made it plausible.
            if conf == "unverified" and not (
                spec.get("detail") or spec.get("verification_status")
            ):
                problems.append(
                    f"{key}.{layer} is unverified but carries no `detail` — say "
                    "what is unknown and what would resolve it"
                )
            # An unreleased capability in a project that HAS releases should say
            # which version is expected. A project with no releases at all has
            # no version to name, so `since` is not required there.
            if (
                spec.get("unreleased")
                and spec["value"] == "yes"
                and not spec.get("since")
                and cell["solver"] not in never_released
            ):
                problems.append(
                    f"{key}.{layer} is unreleased yes in a released project but "
                    "names no expected `since` version"
                )
            mat = spec.get("maturity")
            if mat is not None and mat not in MATURITY:
                problems.append(f"{key}.{layer} has unknown maturity {mat!r}")
            if mat == "absent":
                problems.append(
                    f"{key}.{layer} has maturity 'absent' — use value: \"no\" instead"
                )
            if spec.get("known_issues") and mat in TRUSTWORTHY:
                problems.append(
                    f"{key}.{layer} lists known_issues but claims maturity {mat!r}"
                )
            if mat == "verified" and not spec.get("verified_by"):
                problems.append(
                    f"{key}.{layer} claims maturity 'verified' but no verified_by "
                    "says what establishes it"
                )
            # `value: partial` means "reachable, with a caveat". When that caveat
            # is a workaround (blocked_by), the remedy is the explanation. When
            # there is no blocked_by, partial means the support itself is
            # incomplete, and that needs a maturity grade.
            if spec["value"] == "partial" and mat is None and not spec.get("blocked_by"):
                problems.append(
                    f"{key}.{layer} is partial with neither a blocked_by nor a "
                    "maturity — say whether it needs a workaround or is incomplete"
                )
            if spec.get("since") and spec["value"] not in ("yes", "partial"):
                problems.append(
                    f"{key}.{layer} has `since` but value is {spec['value']!r} — "
                    "a since only makes sense for supported capability"
                )

    for cell in reg["matrix"]:
        if cell["solver"] not in never_released:
            continue
        for layer in LAYERS:
            spec = cell.get(layer)
            if spec and spec.get("value") == "yes" and not spec.get("unreleased"):
                problems.append(
                    f"({cell['feature']!r}, {cell['solver']!r}).{layer} is a plain "
                    "yes but the solver has no release — mark it unreleased: true"
                )

    for solver in reg["solvers"]:
        if "latest_release" not in solver:
            problems.append(
                f"solver {solver['id']!r} has no latest_release — a bare yes has "
                "no meaning without a stated baseline"
            )
        pkg = solver.get("packaging")
        if pkg is None:
            problems.append(f"solver {solver['id']!r} has no packaging block")
            continue
        cf = pkg.get("conda_forge")
        if cf not in ("available", "in-progress", "none"):
            problems.append(f"solver {solver['id']!r} has unknown conda_forge {cf!r}")
        inst = pkg.get("pypi_install")
        if inst is None:
            problems.append(f"solver {solver['id']!r} has no pypi_install")
        elif inst not in PYPI_INSTALL:
            problems.append(f"solver {solver['id']!r} has unknown pypi_install {inst!r}")
        has_name = bool(pkg.get("pypi")) and pkg.get("pypi") != "none"
        if inst in ("pure-python", "wheels", "wheels-partial", "compiles") and not has_name:
            problems.append(
                f"solver {solver['id']!r} is pypi_install={inst!r} but names no PyPI distribution"
            )
        if inst == "wheels-partial" and not pkg.get("pypi_detail"):
            problems.append(
                f"solver {solver['id']!r} has partial wheels but no pypi_detail "
                "saying which platforms are covered"
            )
        if cf == "in-progress" and not pkg.get("tracking"):
            problems.append(
                f"solver {solver['id']!r} is conda_forge in-progress with no tracking link"
            )

        for i, d in enumerate(solver.get("docs") or []):
            where = f"solver {solver['id']!r} docs[{i}]"
            if not d.get("url"):
                problems.append(f"{where} has no url")
            elif not d["url"].startswith("https://"):
                problems.append(f"{where} url is not https: {d['url']!r}")
            if not d.get("what"):
                problems.append(
                    f"{where} has no `what` — a bare link does not say which "
                    "question the page answers"
                )
        paper = solver.get("paper")
        if paper is not None:
            for required in ("title", "url", "describes"):
                if not paper.get(required):
                    problems.append(
                        f"solver {solver['id']!r} paper has no {required!r}"
                    )

    # Coverage: every solver should say something about every feature.
    for feature in feature_ids:
        for solver in solver_ids:
            if (feature, solver) not in seen:
                problems.append(f"no entry for feature {feature!r} / solver {solver!r}")

    return problems


def effective(cell: dict, layer: str) -> dict | None:
    """The spec at `layer`, inheriting from the layer above when absent."""
    for candidate in LAYERS[: LAYERS.index(layer) + 1][::-1]:
        if candidate in cell:
            return cell[candidate]
    return None


# Fields that make a cell worth linking to. A reader who clicks a glyph wants
# the reasoning behind it, and for a plain verified cell that reasoning was
# previously unreachable from the table.
NOTE_FIELDS = ("detail", "detail_maturity", "caveat", "source", "workaround",
               "tracking", "known_issues", "verification_status")


def has_notes(cell: dict | None) -> bool:
    if cell is None:
        return False
    return any(
        spec.get(f)
        for layer in LAYERS
        if (spec := cell.get(layer)) is not None
        for f in NOTE_FIELDS
    )


def anchor_for(feature: str, solver: str) -> str:
    return f"cell-{feature}-{solver}"


def render_row(cell: dict | None) -> str:
    """One matrix cell: glyphs per layer, collapsed when the layers agree."""
    if cell is None:
        return "·"
    specs = [(layer, cell.get(layer)) for layer in LAYERS]
    present = [(layer, s) for layer, s in specs if s is not None]
    if not present:
        return "·"

    values = [s["value"] for _, s in present]
    uniform = len(set(values)) == 1

    def lend(spec):
        """A supporting layer's spec, stripped of what describes only itself.

        `verified` says the capability was tested and carries over. `partial`
        and `plumbing` grade that layer's own implementation, as do its
        known_issues, so they must not ride along into a higher layer's glyph.
        """
        out = dict(spec)
        out.pop("known_issues", None)
        if out.get("maturity") in ("partial", "plumbing"):
            out.pop("maturity", None)
        return out

    def mark(spec, supported_above=None):
        # When an unreachable blocker sits over a layer that does support the
        # capability, render that layer's glyph and mark it blocked. A bare ❌
        # would put the gap in the solver's column when it belongs to the
        # interface.
        blocker = spec.get("blocked_by")
        if (blocker in UNREACHABLE or blocker in BINDABLE) and supported_above is not None:
            if blocker in UNREACHABLE and spec["value"] == "partial":
                pass  # fall through: a partial layer renders its own glyph
            else:
                mark_glyph = BLOCKED_GLYPH if blocker in UNREACHABLE else BINDABLE_GLYPH
                lent = mark(lend(supported_above))
                # Keep the blocker next to the glyph it qualifies, ahead of a
                # trailing "(≥x.y.z)", so every cell puts the version last.
                m = re.search(r" \(≥[^)]*\)$", lent)
                if m:
                    return lent[: m.start()] + mark_glyph + m.group(0)
                return lent + mark_glyph
        # A row that is not a yes/no question renders its own value: "126
        # qubits" answers the reader's question where ✅ would not. Everything
        # else — maturity, unreleased, unverified — still applies on top.
        if spec.get("display"):
            g = spec["display"]
            if spec.get("unreleased"):
                g = f"🚧 {g}"
            if spec.get("confidence") == "unverified":
                g += "ᵘ"
            return g
        # A version in place of a checkmark answers "will my install do this?",
        # which is what the reader actually wants to know.
        # A `since` is the release that introduced support, so it reads as a
        # floor: the glyph answers "is this supported?" and the parenthesised
        # version answers "will my install have it?". A bare version in place
        # of the glyph left the first question to be inferred, and did not say
        # whether it was a floor or an exact release.
        since = spec.get("since")
        version = f" (≥{since})" if since and since[0].isdigit() else ""
        mat = spec.get("maturity")
        show_version = bool(version)
        if spec.get("unreleased"):
            # 🚧 already says unreleased; a version after it would read as a
            # release that exists.
            g = "🚧"
        elif mat in ("plumbing", "partial"):
            # Maturity dominates the glyph here: a bare ✅ would overstate it.
            g = MATURITY[mat][0]
            show_version = show_version and spec["value"] == "yes"
        elif mat == "verified":
            g = MATURITY["verified"][0]
        elif spec["value"] == "yes":
            g = GLYPH["yes"]
        else:
            g = GLYPH.get(spec["value"], "?")
            show_version = False
        if spec.get("confidence") == "unverified":
            g += "ᵘ"
        if spec.get("known_issues"):
            g += "⚠"
        # After the marks, so ◐⚠ and ✅⛔ stay adjacent and the version reads as
        # a trailing qualifier on the whole cell.
        if show_version:
            g += version
        return g

    # The nearest layer above each one that actually supports the capability.
    # A blocked layer renders that layer's glyph, so the reader sees what the
    # solver does alongside the mark saying this interface cannot reach it.
    def supporter(index):
        for _, prior in reversed(present[:index]):
            if prior["value"] == "yes" and prior.get("maturity") != "plumbing":
                return prior
        return None

    glyphs = [mark(s, supporter(i)) for i, (_, s) in enumerate(present)]
    # A lent glyph already carries the layer below it, so "✅✅ / ✅✅⛔" repeats
    # itself. Drop any glyph that the next one extends.
    def base(g):
        """The glyph without its trailing version, for comparison."""
        return re.sub(r" \(≥[^)]*\)$", "", g)

    def extends(later, earlier):
        """Whether `later` is `earlier` plus a mark, ignoring the version."""
        a, b = base(later), base(earlier)
        return a != b and a.startswith(b)

    kept = [
        g
        for i, g in enumerate(glyphs)
        if i == len(glyphs) - 1 or not extends(glyphs[i + 1], g)
    ]
    out = kept[0] if len(set(kept)) == 1 else " / ".join(kept)
    if any(s.get("caveat") for _, s in present):
        out += "†"
    return out


def render(reg: dict) -> str:
    cells = cells_by_key(reg)
    solvers = reg["solvers"]
    features = reg["features"]
    L: list[str] = []
    w = L.append

    # Addressed to whoever opens this file, human or model. A generated file
    # that looks authoritative is worse than one that says it is not: an agent
    # browsing the skill directory will find this table, and reading a stale
    # copy of the data is a real failure mode. Say so in the file itself rather
    # than relying on an instruction elsewhere to be obeyed.
    w("<!--")
    w("  GENERATED FILE — NOT CANONICAL. Do not edit, and do not rely on it.")
    w("")
    w("  Produced from registry.yaml by scripts/render_table.py, for sharing")
    w("  with people outside this skill. It can lag the registry, and it")
    w("  flattens detail that the registry carries in full.")
    w("")
    w("  If you are an agent working from this skill: read registry.yaml for")
    w("  the data and capabilities.md for the reasoning. Nothing here is absent")
    w("  from those, so there is no reason to read further.")
    w("-->")
    w("")
    w("> **Generated export, not the source of truth.** Built from")
    w("> `registry.yaml`; read that for anything load-bearing.")
    w("")
    w("# SQD eigensolver capability matrix")
    w("")
    meta = reg.get("meta", {})
    if meta.get("verified_on"):
        w(f"Verified against the repositories listed below on {meta['verified_on']}.")
        w("")

    w("## How to read this")
    w("")
    w("Each engine has up to three layers, and a capability present in one is not")
    w("necessarily reachable from the next:")
    w("")
    w("1. **Engine** — the C++ or binary core. What the code can compute at all.")
    w("2. **Python** — the wrapper or bindings. Not everything is wrapped, and a")
    w("   wrapper may compute something without returning it.")
    w("3. **Addon** — what survives `qiskit-addon-sqd`'s `sci_solver` interface")
    w("   inside `diagonalize_fermionic_hamiltonian`.")
    w("")
    w("A cell shows one glyph when every layer agrees, and `engine / python / addon`")
    w("when they differ.")
    w("")
    w("| Glyph | Meaning |")
    w("| --- | --- |")
    w("| ✅ | supported |")
    w("| ❌ | not supported |")
    w("| ᵏ | supported; the addon forwards no keywords, so bind the option at "
      "construction (`functools.partial`) |")
    w("| 🚫 | computed, then discarded before the caller sees it |")
    w("| ⛔ | the solver supports this; **this interface cannot reach it**. The "
      "glyph before ⛔ is what the layer above does. |")
    w("| ❔ | unknown |")
    w("| — | not applicable |")
    w("| ᵘ | unverified — carried over, not checked against a source |")
    w("| † | carries a caveat; see the notes |")
    w("| `126q — CI string` | a row that is not a yes/no question shows its "
      "value instead of a glyph |")
    w("| ✅ (≥1.7.1) | supported, and the version is the release that "
      "introduced it — older installs do not have it |")
    w("| 🚧 | exists only in unreleased code — treat as unavailable |")
    w("| ✅✅ | tested, or checked against an independent reference |")
    w("| ◐ | partial — works on some code paths and not others |")
    w("| 🧱 | scaffolding only — no working end-to-end path |")
    w("| ⚠ | has known defects; read the notes before relying on it |")
    w("")
    w("**A ✅ means supported in the solver's latest release**, never in unreleased")
    w("code. Those baselines are:")
    w("")
    for s_ in solvers:
        rel = s_.get("latest_release")
        shown = f"`{rel}`" if rel and rel != "none" else "_no release_"
        w(f"- {s_['name']}: {shown}")
    w("")

    # ── Matrix ──
    head = "| Feature | " + " | ".join(s["name"] for s in solvers) + " |"
    w(head)
    w("| --- | " + " | ".join("---" for _ in solvers) + " |")
    for feat in features:
        row = [feat["name"]]
        for solver in solvers:
            cell = cells.get((feat["id"], solver["id"]))
            glyph = render_row(cell)
            # Make the glyph a link to its own note, so the reasoning behind a
            # cell is one click away rather than buried in a prose section.
            if has_notes(cell):
                glyph = f"[{glyph}](#{anchor_for(feat['id'], solver['id'])})"
            row.append(glyph)
        w("| " + " | ".join(row) + " |")
    w("")
    w("Cells are links: click a glyph for the reasoning and sources behind it.")
    w("")

    # One upstream interface limitation can darken cells in several solver
    # columns, and a reader comparing columns reads that as several independent
    # solver deficiencies. Name the shared cause next to the matrix, not only
    # in the tracking section a thousand lines below. Derived from the registry
    # so it cannot drift from the cells it describes.
    shared = {}
    for cell in reg["matrix"]:
        for layer in LAYERS:
            spec = cell.get(layer)
            if spec and spec.get("blocked_by") == "type-mismatch":
                shared.setdefault(spec.get("tracking"), set()).add(cell["solver"])
    for link, blocked_ids in sorted(shared.items(), key=lambda kv: (kv[0] or "")):
        if len(blocked_ids) < 2:
            continue
        names = sorted(
            next(s["name"] for s in reg["solvers"] if s["id"] == sid)
            for sid in blocked_ids
        )
        joined = (
            " and ".join(names)
            if len(names) == 2
            else ", ".join(names[:-1]) + f", and {names[-1]}"
        )
        w(
            f"**One interface limitation, several columns.** {joined} carry a ⛔ "
            "in this table for the same reason: `sci_solver` passes a pair of "
            "half-string lists whose Cartesian product spans the subspace, so a "
            "flat determinant list cannot be expressed whatever the solver "
            "supports. One upstream limitation"
            + (f" — {link} — " if link else " ")
            + "surfacing in each column, not independent solver deficiencies."
        )
        w("")

    # ── Per-cell notes, the link targets for the matrix above ──
    # Every cell carrying any reasoning gets an entry, including plain verified
    # ones. Those used to render as a bare glyph with their `detail` dropped,
    # which lost exactly the part a reader needs to act on the cell.
    w("## Cell notes")
    w("")
    w("One entry per cell that carries reasoning, linked from the matrix.")
    w("")
    for feat in features:
        for solver in solvers:
            cell = cells.get((feat["id"], solver["id"]))
            if not has_notes(cell):
                continue
            w(f'<a id="{anchor_for(feat["id"], solver["id"])}"></a>')
            w("")
            w(f"**{feat['name']} — {solver['name']}**")
            w("")
            for layer in LAYERS:
                spec = cell.get(layer)
                if spec is None:
                    continue
                bits = []
                if len(LAYERS) > 1 and sum(1 for L in LAYERS if L in cell) > 1:
                    bits.append(f"_{layer}_:")
                if spec.get("caveat"):
                    bits.append(f"({spec['caveat']})")
                if bits:
                    w(" ".join(bits))
                    w("")
                for field in ("detail", "detail_maturity"):
                    if spec.get(field):
                        w(spec[field].strip())
                        w("")
                if spec.get("known_issues"):
                    w("Known issues:")
                    w("")
                    for issue in spec["known_issues"]:
                        w(f"- {issue.strip()}")
                    w("")
                if spec.get("verification_status"):
                    w(f"**Verification.** {spec['verification_status'].strip()}")
                    w("")
                wa = spec.get("workaround")
                if wa == "none":
                    w("**No workaround.**")
                    w("")
                elif wa:
                    w(f"**Workaround.** {wa.strip()}")
                    w("")
                if spec.get("source"):
                    w(f"Source: `{spec['source'].strip()}`")
                    w("")
                if spec.get("tracking"):
                    w(f"Tracking: {spec['tracking']}")
                    w("")
            w("[Back to the matrix](#sqd-eigensolver-capability-matrix)")
            w("")

    # ── Why the layers differ ──
    losses = []
    for feat in features:
        for solver in solvers:
            cell = cells.get((feat["id"], solver["id"]))
            if not cell:
                continue
            for layer in LAYERS:
                spec = cell.get(layer)
                if spec and spec.get("blocked_by"):
                    losses.append((feat, solver, layer, spec))

    if losses:
        w("## Where capability is lost between layers")
        w("")
        w("Each entry below is a place where an engine or wrapper can do something")
        w("that the next layer up cannot reach.")
        w("")
        for feat, solver, layer, spec in losses:
            label, fixability = BLOCKED_BY[spec["blocked_by"]]
            w(f"### {solver['name']} — {feat['name']} (lost at the {layer} layer)")
            w("")
            w(f"**{label}** — {fixability}.")
            w("")
            if spec.get("detail"):
                w(spec["detail"].strip())
                w("")
            if spec.get("source"):
                w(f"Source: `{spec['source']}`")
                w("")
            if spec.get("tracking"):
                w(f"Tracking: {spec['tracking']}")
                w("")
            wa = spec.get("workaround")
            if wa == "none":
                w("**No workaround.**")
                w("")
            elif wa:
                w(f"Workaround: {wa.strip()}")
                w("")

    # ── Execution models ──
    em = reg.get("execution_models") or {}
    if em:
        w("## How the parallelism is launched")
        w("")
        w("Two incompatible models. Which one a solver uses decides how the")
        w("researcher starts their program, and it is not a capability either")
        w("one is missing.")
        w("")
        for name, body in em.items():
            if name == "docs":
                continue
            w(f"### {name.replace('_', ' ')}")
            w("")
            if body.get("solvers"):
                w(f"Applies to: {', '.join('`' + x + '`' for x in body['solvers'])}")
                w("")
            if body.get("launch"):
                w(f"Launch: `{body['launch']}`")
                w("")
            for field, title in (
                ("detail", None),
                ("detail_tradeoffs", "Tradeoffs"),
                ("rules_out_notebooks", "Rules out notebooks"),
                ("notes", "Notes"),
            ):
                if body.get(field):
                    text = body[field].strip()
                    w(f"**{title}.** {text}" if title else text)
                    w("")
            sup = body.get("addon_support") or {}
            if sup:
                if sup.get("detail"):
                    w(f"**Addon support.** {sup['detail'].strip()}")
                    w("")
                if sup.get("caveat"):
                    w(f"⚠ {sup['caveat'].strip()}")
                    w("")
                if sup.get("source"):
                    w(f"Source: `{sup['source']}`")
                    w("")
        for d in em.get("docs") or []:
            w(f"Guide: <{d['url']}> — {d.get('what', '').strip()}")
            w("")

    # ── Interface constraints ──
    ic = reg.get("interface_constraints") or {}
    if ic:
        w("## The `sci_solver` interface")
        w("")
        w("These constraints explain most of the addon-layer losses above.")
        w("")
        for name, body in ic.items():
            w(f"### {name.replace('_', ' ')}")
            w("")
            if body.get("detail"):
                w(body["detail"].strip())
                w("")
            if body.get("source"):
                w(f"Source: `{body['source']}`")
                w("")
            if body.get("tracking"):
                w(f"Tracking: {body['tracking']}")
                w("")
            if body.get("workaround"):
                w(f"Workaround: `{body['workaround']}`")
                w("")

    # ── Solvers ──
    w("## Solvers")
    w("")
    BUILD = {
        "pip": "plain `pip install`",
        "compiles-cpp": "compiles C++ on install",
        "compiles-cuda": "compiles C++ and CUDA on install",
        "heavy": "heavy — see below",
    }
    for s in solvers:
        w(f"### {s['name']} (`{s['id']}`)")
        w("")
        w(f"- Engine: {s.get('engine', '—')}")
        w(f"- Python: {s.get('python', '—')}")
        rel = s.get("latest_release")
        w(f"- Latest release: {'`' + rel + '`' if rel and rel != 'none' else 'none'}")
        w(f"- Build: {BUILD.get(s.get('build'), s.get('build', 'unknown'))}")
        if s.get("is_sci_solver") is False:
            w("- Not an `sci_solver`: using it inside the loop means writing the adapter.")
        elif s.get("is_sci_solver_detail"):
            w(f"- `sci_solver`: {s['is_sci_solver_detail'].strip()}")
        if s.get("is_default"):
            w("- The default solver in `qiskit-addon-sqd`.")
        pkg = s.get("packaging") or {}
        CF = {
            "available": "available",
            "in-progress": "**in progress**",
            "none": "not available",
        }
        pypi = pkg.get("pypi")
        inst = pkg.get("pypi_install", "none")
        label, toolchain = PYPI_INSTALL.get(inst, (inst, "?"))
        if pypi and pypi != "none":
            ver = f" {pkg['pypi_version']}" if pkg.get("pypi_version") else ""
            w(f"- PyPI: `{pypi}`{ver} — {label}, {toolchain}")
        else:
            w("- PyPI: not distributed")
        if pkg.get("pypi_platforms"):
            w(f"- Wheel platforms: {', '.join(pkg['pypi_platforms'])}")
        cf_line = CF.get(pkg.get("conda_forge"), "unknown")
        if pkg.get("conda_forge_version"):
            cf_line += f" ({pkg['conda_forge_version']})"
        if pkg.get("tracking"):
            cf_line += f" — {pkg['tracking']}"
        w(f"- conda-forge: {cf_line}")
        w("")
        for api in s.get("apis") or []:
            tag = " (header-only)" if api.get("header_only") else ""
            w(f"**{api['language']} API{tag}.** `{api['surface']}` — "
              f"{api.get('detail', '').strip()}")
            w("")
        if pkg.get("pypi_detail"):
            w(f"**PyPI.** {pkg['pypi_detail'].strip()}")
            w("")
        if pkg.get("conda_forge_detail"):
            w(f"**conda-forge.** {pkg['conda_forge_detail'].strip()}")
            w("")
        if pkg.get("detail"):
            w(f"**Packaging.** {pkg['detail'].strip()}")
            w("")
        for field, title in (
            ("role", "What the pieces are"),
            ("not_an_eigensolver", "Not an eigensolver"),
            ("latest_release_detail", "Release status"),
            ("build_detail", "Build requirements"),
            ("engine_only", "Engine-only capability"),
            ("limits", "Limits"),
            ("notes", "Notes"),
        ):
            if s.get(field):
                w(f"**{title}.** {s[field].strip()}")
                w("")
        paper = s.get("paper")
        if paper:
            cite = paper.get("title", "")
            if paper.get("authors"):
                cite += f" — {paper['authors']}"
            if paper.get("arxiv"):
                cite += f", [arXiv:{paper['arxiv']}]({paper.get('url', '')})"
            w(f"**Paper.** {cite}")
            w("")
            if paper.get("describes"):
                w(paper["describes"].strip())
                w("")
            if paper.get("citing_page"):
                w(f"Citation requested at {paper['citing_page']}.")
                w("")
        docs = s.get("docs")
        if docs:
            w("**Documentation.**")
            w("")
            for d in docs:
                w(f"- <{d['url']}> — {d.get('what', '').strip()}")
                if d.get("stale"):
                    w(f"  - ⚠ {d['stale'].strip()}")
            w("")

    # ── Trust ──
    caveated = []
    for feat in features:
        for solver in solvers:
            cell = cells.get((feat["id"], solver["id"]))
            if not cell:
                continue
            for layer in LAYERS:
                spec = cell.get(layer)
                if not spec:
                    continue
                if spec.get("maturity") in ("plumbing", "partial") or spec.get("known_issues"):
                    caveated.append((feat, solver, layer, spec))

    if caveated:
        w("## Supported, but do not trust blindly")
        w("")
        w("Capability that exists without being dependable. These may still be the")
        w("right choice — but a researcher should know what they are taking on, and")
        w("a passing smoke test proves little when support is path-dependent.")
        w("")
        for feat, solver, layer, spec in caveated:
            mat = spec.get("maturity")
            w(f"### {solver['name']} — {feat['name']} ({layer} layer)")
            w("")
            if mat:
                glyph, meaning = MATURITY[mat]
                w(f"{glyph} **{mat}** — {meaning}.")
                w("")
            for field in ("detail", "detail_maturity"):
                if spec.get(field):
                    w(spec[field].strip())
                    w("")
            if spec.get("known_issues"):
                w("Known issues:")
                w("")
                for issue in spec["known_issues"]:
                    w(f"- {issue.strip()}")
                w("")
            if spec.get("verification_status"):
                w(f"**Verification.** {spec['verification_status'].strip()}")
                w("")
            if spec.get("reference"):
                w(f"Full assessment: [`{spec['reference']}`]({spec['reference']})")
                w("")
            if spec.get("source"):
                w(f"Source: `{spec['source'].strip()}`")
                w("")

    # ── Packaging ──
    w("## Packaging")
    w("")
    w("A researcher on a conda-managed stack cannot drop a source-compiled C++")
    w("extension into it without care, so this dimension can decide the choice on")
    w("its own.")
    w("")
    w("The question is not whether a package is on PyPI, but whether installing it")
    w("needs a compiler.")
    w("")
    w("| Solver | PyPI | `pip install` | Needs a toolchain? | conda-forge |")
    w("| --- | --- | --- | --- | --- |")
    CF_SHORT = {"available": "✅", "in-progress": "⚠️ in progress", "none": "❌"}
    INST_SHORT = {
        "pure-python": "✅ pure Python",
        "wheels": "✅ wheels",
        "wheels-partial": "⚠️ partial wheels",
        "compiles": "⚠️ source build",
        "placeholder": "❌ placeholder only",
        "none": "—",
    }
    NEEDS = {
        "pure-python": "no",
        "wheels": "no",
        "wheels-partial": "**on some platforms**",
        "compiles": "**yes**",
        "placeholder": "—",
        "none": "—",
    }
    for s_ in solvers:
        pkg = s_.get("packaging") or {}
        pypi = pkg.get("pypi")
        pypi_cell = f"`{pypi}`" if pypi and pypi != "none" else "❌"
        inst = pkg.get("pypi_install", "none")
        cf = CF_SHORT.get(pkg.get("conda_forge"), "❔")
        if pkg.get("conda_forge_version"):
            cf += f" {pkg['conda_forge_version']}"
        if pkg.get("tracking"):
            cf += f" ([PR]({pkg['tracking']}))"
        w(
            f"| {s_['name']} | {pypi_cell} | {INST_SHORT.get(inst, inst)} "
            f"| {NEEDS.get(inst, '?')} | {cf} |"
        )
    w("")
    w("A source build is not merely slower. For `sbd-eigensolver` the backends you")
    w("end up with depend on the toolchain the build finds, so two machines running")
    w("the same pip command can get different GPU support.")
    w("")

    # ── Open upstream work ──
    tracked: list[tuple[str, str]] = []
    for feat in features:
        for solver in solvers:
            cell = cells.get((feat["id"], solver["id"]))
            if not cell:
                continue
            for layer in LAYERS:
                spec = cell.get(layer)
                if spec and spec.get("tracking"):
                    tracked.append(
                        (f"{solver['name']} / {feat['name']} ({layer})", spec["tracking"])
                    )
    for name, body in (reg.get("interface_constraints") or {}).items():
        if body.get("tracking"):
            tracked.append((f"interface: {name.replace('_', ' ')}", body["tracking"]))
    for s_ in solvers:
        pkg = s_.get("packaging") or {}
        if pkg.get("tracking"):
            tracked.append((f"{s_['name']} — conda-forge packaging", pkg["tracking"]))

    if tracked:
        w("## Tracked upstream")
        w("")
        w("Gaps with a known issue or pull request. Check these before trusting a")
        w("`no` above — the state may have moved since this file was generated.")
        w("")
        seen_links: dict[str, list[str]] = {}
        for name, link in tracked:
            seen_links.setdefault(link, []).append(name)
        for link, names in seen_links.items():
            w(f"- {link}")
            for n in names:
                w(f"  - {n}")
        w("")

    # ── Unverified ──
    unver = []
    for feat in features:
        for solver in solvers:
            cell = cells.get((feat["id"], solver["id"]))
            if not cell:
                continue
            for layer in LAYERS:
                spec = cell.get(layer)
                if spec and spec.get("confidence") == "unverified":
                    unver.append(f"{solver['name']} / {feat['name']} ({layer})")
    w("## Unverified cells")
    w("")
    if unver:
        w("Carried over from the source table and not checked against any source:")
        w("")
        for item in unver:
            w(f"- {item}")
    else:
        w("None.")
    w("")

    if meta.get("verified_against"):
        w("## Verified against")
        w("")
        for name, path in meta["verified_against"].items():
            w(f"- `{name}` — `{path}`")
        w("")

    if meta.get("sources"):
        w("## Source pins")
        w("")
        w(
            "Claims citing a `file:line` are keyed to one of these, so they can "
            "be checked against the exact code they were read from. Line numbers "
            "drift between revisions; these pins do not."
        )
        w("")
        w("| key | kind | pin | where |")
        w("| --- | --- | --- | --- |")
        for key, src in meta["sources"].items():
            kind = src.get("kind", "")
            pin = src.get("pin", "")
            if src.get("describe"):
                pin = f"{pin} ({src['describe']})"
            if src.get("repo"):
                where = src["repo"].replace("https://", "")
                if src.get("branch"):
                    where = f"{where} (branch `{src['branch']}`)"
            else:
                where = "installed package"
            pin_md = f"`{pin}`" if pin else ""
            w(f"| `{key}` | {kind} | {pin_md} | {where} |")
        w("")
        for key, src in meta["sources"].items():
            if src.get("note"):
                w(f"**`{key}`.** {src['note'].strip()}")
                w("")

    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="validate only")
    ap.add_argument("--stdout", action="store_true", help="print instead of writing")
    ap.add_argument("-o", "--output", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    reg = load()
    problems = validate(reg)
    if problems:
        print(f"registry.yaml: {len(problems)} problem(s)", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print("registry.yaml: ok", file=sys.stderr)
    if args.check:
        return 0

    text = render(reg)
    if args.stdout:
        print(text, end="")
    else:
        args.output.write_text(text)
        print(f"wrote {args.output.relative_to(HERE)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
