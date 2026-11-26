"""Milestone 11-G23 -- historical compatibility measurements (OFFLINE research only).

* `g6_g7_divergence(policy)`: the frozen G6 / G7 heading-kind labels and body labels versus what a policy's
  segmentation does. G6 deliberately labelled candidate-profile headings UNKNOWN (body necessity "UNKNOWN",
  reported but not scored), so a candidate-profile policy is EXPECTED to diverge there; every divergence is
  listed by control id and classified, and the frozen gold is never rewritten.
* `universal_parse_diff(policy)`: every job-like string in every TRACKED evaluation JSON file (and the
  tracked M10 source texts) parsed under P0 and under the policy; changed texts are counted per file.
* `diff_dumps(a, b)`: JSON-path differences between two `m11g23_dump_under_policy.py` dumps.
"""
from __future__ import annotations

import json
import subprocess
from collections import Counter

import m11g23_harness as hz

from gitscore.jobs.parsing import segmentation as seg
from gitscore.jobs.parsing.parser import parse_job_description_with_diagnostics

ROOT = hz.REPO_ROOT


def _doc_and_heading_kind(control: dict, policy) -> tuple[str, str]:
    lines = ([control["heading_line"]] if control["heading_line"] is not None else []) + list(control["body_lines"])
    doc = "\n".join(lines) + "\n"
    if control["heading_line"] is None:
        return doc, "NOT_A_HEADING"
    line = control["heading_line"]
    span = seg._line_content_span(line, 0)
    kind = None if span is None else policy.classify(line, line[span[0]:span[1]])[0]
    return doc, "NOT_A_HEADING" if kind is None else kind.name


def g6_g7_divergence(policy, p0) -> dict:
    out = {}
    for name, rel in (("g6", "evaluation/m11g6/heading_controls.json"), ("g7", "evaluation/m11g7/boundary_controls.json")):
        controls = json.loads((ROOT / rel).read_text(encoding="utf-8"))["controls"]
        heading_div, body_div = [], []
        for c in controls:
            doc, kind = _doc_and_heading_kind(c, policy)
            _, kind0 = _doc_and_heading_kind(c, p0)
            if kind != c["expected_heading_kind"]:
                heading_div.append({"id": c["id"], "gold": c["expected_heading_kind"], "p0": kind0, "policy": kind})
            with hz.active(policy):
                prof = parse_job_description_with_diagnostics(doc).profile
            for q in c.get("body_qualifications", []):
                s = doc.index(q["text"])
                rows = [r for r in prof.requirements if r.source_span.start < s + len(q["text"])
                        and r.source_span.end > s]
                nec = sorted({r.necessity.value.upper() for r in rows})
                gold = q["expected_necessity"]
                scored_expected = gold in ("REQUIRED", "PREFERRED")
                if (bool(rows) != scored_expected) or (rows and nec != [gold]):
                    body_div.append({"id": c["id"], "text_is_genuine_qualification": q["is_genuine_qualification"],
                                     "gold_necessity": gold, "policy_row_necessities": nec})
        out[name] = {"controls": len(controls), "heading_kind_divergences": heading_div,
                     "body_divergences": body_div}
    return out


def _tracked_texts() -> dict[str, list[str]]:
    files = subprocess.run(["git", "ls-files", "evaluation"], cwd=ROOT, capture_output=True, text=True,
                           check=True).stdout.split()
    out: dict[str, list[str]] = {}
    for f in files:
        if f.startswith("evaluation/m11g23/"):
            continue  # the G23 control sets are measured separately
        path = ROOT / f
        if f.endswith(".txt"):
            out[f] = [path.read_bytes().decode("utf-8")]
            continue
        if not f.endswith(".json"):
            continue
        texts: list[str] = []

        def walk(o):
            if isinstance(o, dict):
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
            elif isinstance(o, str) and "\n" in o and len(o) > 40:
                texts.append(o)
        try:
            walk(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if texts:
            out[f] = texts
    return out


def _parse_key(text: str):
    p = parse_job_description_with_diagnostics(text)
    rows = tuple(sorted((tuple(sorted(r.alternative_concept_ids)) or (r.concept_id or "",), r.category or "",
                         r.necessity.value,
                         r.source_span.start, r.source_span.end) for r in p.profile.requirements))
    unparsed = tuple((u.source_span.start, u.source_span.end) for u in p.unparsed_claims)
    return rows, unparsed


def universal_parse_diff(policy) -> dict:
    per_file = {}
    totals = Counter()
    for f, texts in sorted(_tracked_texts().items()):
        changed = rows_changed = 0
        for t in texts:
            if not t.strip():
                continue
            base = _parse_key(t)
            with hz.active(policy):
                new = _parse_key(t)
            totals["texts"] += 1
            if base != new:
                changed += 1
                rows_changed += int(base[0] != new[0])
        totals["files"] += 1
        if changed:
            per_file[f] = {"texts": len(texts), "changed": changed, "rows_changed": rows_changed}
            totals["changed_texts"] += changed
            totals["row_changed_texts"] += rows_changed
    return {"totals": dict(totals), "changed_files": per_file}


def diff_dumps(a, b, path: str = "") -> list[str]:
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b), key=str):
            out += diff_dumps(a.get(k), b.get(k), f"{path}/{k}")
        return out
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out += diff_dumps(x, y, f"{path}[{i}]")
        return out
    return [] if a == b else [path]
