"""Milestone 11-G23 -- POST-HOC diagnostics of the failed EVAL run (research only, NON-CONFIRMATORY).

    python scripts/evaluation_lib/m11g23_posthoc.py

Written AFTER the single frozen EVAL run failed acceptance gate G1. It changes no policy, label, gate or
selection, and runs only the FROZEN policies (P0 and the selected P4) to explain the shortfall. Nothing here may
be read as a validation of any policy: EVAL is now an exposed holdout. Writes
`evaluation/m11g23/eval_posthoc_diagnostics.json` (synthetic EVAL text only).
"""
from __future__ import annotations

import json
import re
from collections import Counter

import m11g23_eval as ev
import m11g23_harness as hz
import m11g23_policies as pol

from gitscore.jobs.parsing import segmentation as seg

OUT = hz.REPO_ROOT / "evaluation" / "m11g23" / "eval_posthoc_diagnostics.json"


def mechanism(u: dict) -> str:
    """Earliest stage that lost an unrecovered qualification unit under the frozen selected policy."""
    if u["gold_section"] in ("required", "preferred") and u["section_kind"] not in ("REQUIRED", "PREFERRED") \
            and not u["rows"]:
        return "heading_or_section"
    if u["outcome"] == "missed_entirely":
        return "not_admitted_unsectioned"
    if not u["strict"]["concept_ok"]:
        return "concept_or_vocabulary"
    return "necessity"


def heading_lines(control: dict) -> list[dict]:
    spans = {u["span"] for u in control["units"]}
    out = []
    for m in re.finditer(r"[^\r\n]+", control["text"]):
        line = m.group()
        body = seg._BULLET_PREFIX.sub("", line).strip()
        if not body or any(body in s or s in body for s in spans):
            continue
        span = seg._line_content_span(line, 0)
        content = line[span[0]:span[1]]
        k0 = seg._classify_heading_line(line, content)
        k4 = pol.SELECTED.classify(line, content)[0]
        out.append({"line": line, "p0": None if k0 is None else k0.name, "selected": None if k4 is None else k4.name})
    return out


def main() -> None:
    controls = {c["id"]: c for c in ev.load("eval")}
    r0, r4 = ev.run("eval", pol.P0), ev.run("eval", pol.SELECTED)
    lost, by_mech = [], Counter()
    heading_controls = set()
    for c0, c4 in zip(r0["results"], r4["results"]):
        for u0, u4 in zip(c0["units"], c4["units"]):
            if u4["qual"] and not u4["ambiguous"] and not u4["strict"]["recovered"]:
                mech = mechanism(u4)
                by_mech[mech] += 1
                if mech == "heading_or_section":
                    heading_controls.add(c4["id"])
                lost.append({"control": c4["id"], "family": c4["family"], "span": u4["span"], "mechanism": mech,
                             "section_kind": u4["section_kind"], "gold_section": u4["gold_section"],
                             "outcome": u4["outcome"], "gold_tech": u4["gold_tech"],
                             "represented_tech": u4["represented_tech"], "gold_nec": u4["gold_nec"],
                             "row_necessities": u4["row_necessities"]})
    fabricated = [{"control": c["id"], "span": u["span"], "fabricated": u["fabricated_concepts"]}
                  for c in r4["results"] for u in c["units"] if u["fabricated_concepts"]]
    out = {
        "status": "POST-HOC, NON-CONFIRMATORY: written after the single frozen EVAL run failed gate G1; EVAL is an "
                  "exposed holdout from here on. No policy, label, gate or selection was changed.",
        "selected_policy": pol.SELECTED.name,
        "unrecovered_qualification_units": len(lost),
        "by_mechanism": dict(sorted(by_mech.items())),
        "heading_attributable_upper_bound": {
            "note": "even a perfect heading policy could recover at most the heading_or_section units, and only if "
                    "their concepts and necessity are then also right",
            "p0_recovered": r0["metrics"]["1_recall_strict"]["recovered"],
            "selected_recovered": r4["metrics"]["1_recall_strict"]["recovered"],
            "of": r4["metrics"]["1_recall_strict"]["of"],
            "heading_or_section_units_still_lost": by_mech["heading_or_section"]},
        "headings_in_controls_with_heading_losses": {cid: heading_lines(controls[cid]) for cid in sorted(heading_controls)},
        "selected_policy_defect": {
            "erratum": "The frozen P4 never rescues a BARE sentence-case 'About you' line: `_is_bare_cp_line` accepts "
                       "it, but `candidate_profile_kind(content, UNKNOWN)` then rejects it because production's "
                       "`^about` root gives the line the SKIP family. DEV never exercised it (every DEV 'About you' "
                       "had a colon or Markdown). Recorded, NOT fixed: fixing it and re-running EVAL would be tuning "
                       "against an exposed holdout.",
            "eval_controls_with_bare_about_you": sorted(cid for cid, c in controls.items()
                                                        if "About you" in [ln.strip() for ln in c["text"].split("\n")]),
        },
        "fabricated_concepts_selected": fabricated,
        "lost_units": lost,
    }
    OUT.write_bytes((json.dumps(out, indent=1, ensure_ascii=False) + "\n").encode("utf-8"))
    print(f"wrote {OUT.relative_to(hz.REPO_ROOT)}: {len(lost)} lost units {dict(by_mech)}")


if __name__ == "__main__":
    main()
