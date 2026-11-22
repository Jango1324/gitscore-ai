"""Milestone 11-G22-S1 -- real-pipeline comparison: readme:v4 (pinned) vs readme:v5 (setext heading boundaries).

    python scripts/evaluate_m11g22s1_setext_boundaries.py [--dump PATH]

Runs the REAL pipeline -- README extractor, evidence aggregation (`pipeline.evidence` / 8c end-to-end profiles),
matcher v1 and scoring v2 -- twice: under production readme:v5, and pinned to readme:v4 through
`scripts/evaluation_lib/readme_v4_pin.py` (production's own unchanged ATX-only heading index). It reports every
difference: README evidence items recovered / newly excluded / moved (provenance), MatchStatus, true / false SUPPORTED
on every labelled G22 control set, score numerator / denominator / value and undefined scores on the frozen 8c
matrices, and G19 capability.

`--dump PATH` instead writes the raw per-item measurements of the CURRENT environment (used once to cross-check the
pin against a disposable checkout of the previous HEAD, whose code is genuinely readme:v4).

Writes `evaluation/m11g22s1/setext_boundary_comparison.json` (public: synthetic controls and public 8c fixtures only).
No LLM, no network, no private data.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO_ROOT / "src"), str(REPO_ROOT / "scripts"), str(REPO_ROOT / "scripts" / "evaluation_lib")]

import m11g22r2_harness as h  # noqa: E402
import m11g22r2_policies as p2  # noqa: E402
from evaluation_lib import end_to_end_eval  # noqa: E402
from evaluation_lib.loaders import list_candidate_names, load_candidate_fixture, load_job  # noqa: E402
from gitscore.assessment import assess_job  # noqa: E402
from gitscore.concepts.registry import default_registry  # noqa: E402
from gitscore.evidence.capability import concept_capability  # noqa: E402
from gitscore.evidence.extraction import readme as readme_mod  # noqa: E402
from gitscore.jobs.parsing.parser import parse_job_description_with_diagnostics  # noqa: E402
from gitscore.matching import match_job  # noqa: E402

OUT = REPO_ROOT / "evaluation" / "m11g22s1"
LABELLED_SETS = {
    "g22r2_dev": "evaluation/m11g22r2/readme_context_controls_dev.json",
    "g22r2_eval": "evaluation/m11g22r2/readme_context_controls_eval.json",
    "g22r3_val1": "evaluation/m11g22r3/validation_controls_val1.json",
    "g22r3_val2": "evaluation/m11g22r3/validation_controls_val2.json",
    "g22r4_dev": "evaluation/m11g22r4/dev_controls.json",
    "g22r4_fresh": "evaluation/m11g22r4/fresh_validation_controls.json",
    "g22r5_dev": "evaluation/m11g22r5/dev_controls.json",
    "g22r5_fresh": "evaluation/m11g22r5/fresh_validation_controls.json",
}
G22R_SETS = ("evaluation/m11g22r/alias_evidence_controls_dev.json", "evaluation/m11g22r/alias_evidence_controls_eval.json")


def _pin():
    import readme_v4_pin
    return readme_v4_pin.pinned()


def _readme_items(text: str | None, owner: str = "o", repo: str = "r") -> dict:
    if not text:
        return {}
    return {e.concept_id: [e.raw_observation, e.extractor_version]
            for e in readme_mod.evidence_from_readme(owner, repo, text, "README.md")}


def _run_control(c: dict):
    try:
        r = h.run_control(c, p2.A)
        return {"outcome": r["outcome"], "status": r["probe_status"], "score": r["score"],
                "numerator": r["numerator"], "denominator": r["denominator"]}
    except ValueError:  # probe the job parser cannot resolve (G22-R5 DEV dev-022 'Go'): README items only
        return {"outcome": "unscoreable", "status": None, "score": None, "numerator": 0, "denominator": 0}


def measure() -> dict:
    """Per-item measurements of the README extractor / pipeline in the CURRENT environment."""
    reg = default_registry()
    out = {"extractor_version": readme_mod.EXTRACTOR_VERSION, "sets": {}, "g22r": {}, "fixtures_8c": {}, "matrix_8c": {}}
    for name, rel in LABELLED_SETS.items():
        path = REPO_ROOT / rel
        if not path.exists():
            continue
        rows = {}
        for c in json.loads(path.read_text(encoding="utf-8"))["controls"]:
            rows[c["id"]] = {"readme": {r["name"]: _readme_items(r["readme"], "o", r["name"]) for r in c["repos"]},
                             "probe": c["probe"], "label": c["concepts"].get(c["probe"]), **_run_control(c)}
        out["sets"][name] = rows
    for rel in G22R_SETS:
        for c in json.loads((REPO_ROOT / rel).read_text(encoding="utf-8"))["controls"]:
            out["g22r"][c["id"]] = {r["name"]: _readme_items(r["readme"], "o", r["name"]) for r in c["repos"]}
    profiles = end_to_end_eval.build_candidate_profiles({n: load_candidate_fixture(n) for n in list_candidate_names()})
    for n, prof in profiles.items():
        out["fixtures_8c"][n] = sorted([e.repository.name, e.evidence_type.value, e.concept_id, e.confidence.name,
                                        e.extractor_version, e.raw_observation, e.file_path] for e in prof.evidence)
    names = {n.lower(): n for n in list_candidate_names()}
    for label, rel in (("8c_v1", "evaluation/gold/matrix.json"), ("8c_v1_1", "evaluation/gold_v1_1/matrix.json")):
        for pair in json.loads((REPO_ROOT / rel).read_text(encoding="utf-8"))["pairs"]:
            a = assess_job(match_job(profiles[names[pair["candidate"].lower()]],
                                     parse_job_description_with_diagnostics(load_job(pair["job_id"])["raw_text"]).profile))
            ms = a.match_analysis.requirement_matches
            out["matrix_8c"][f"{label}:{pair['candidate']}/{pair['job_id']}"] = {
                "score": a.alignment_score, "denominator": a.assessable_count,
                "numerator": sum(1 for m in ms if m.status.value == "supported" and a.counts_toward_alignment(m)),
                "statuses": sorted([sorted(m.requirement.alternative_concept_ids)
                                    or ([m.requirement.concept_id] if m.requirement.concept_id else []),
                                    m.status.value] for m in ms)}
    out["capability"] = {c.concept_id: [concept_capability(c.concept_id).capability.value,
                                        sorted(x.value for x in concept_capability(c.concept_id).pathways)]
                         for c in reg.all_concepts()}
    return out


def _strip_version(items: dict) -> dict:
    return {cid: v[0] for cid, v in items.items()}


def compare(v4: dict, v5: dict) -> dict:
    sets = {}
    for name in v4["sets"]:
        recovered, excluded, moved, status, outcome = [], [], [], [], []
        for cid, a in v4["sets"][name].items():
            b = v5["sets"][name][cid]
            for repo in a["readme"]:
                x, y = _strip_version(a["readme"][repo]), _strip_version(b["readme"][repo])
                recovered += [[cid, repo, k] for k in y.keys() - x.keys()]
                excluded += [[cid, repo, k] for k in x.keys() - y.keys()]
                moved += [[cid, repo, k] for k in x.keys() & y.keys() if x[k] != y[k]]
            if a["status"] != b["status"]:
                status.append([cid, a["status"], b["status"]])
            if a["outcome"] != b["outcome"]:
                outcome.append([cid, a["probe"], a["label"], a["outcome"], b["outcome"]])
        sets[name] = {"controls": len(v4["sets"][name]), "readme_items_recovered": recovered,
                      "readme_items_newly_excluded": excluded, "provenance_moved": moved,
                      "match_status_changes": status, "outcome_changes": outcome,
                      "false_supported": [sum(1 for r in v4["sets"][name].values() if r["outcome"] == "false_supported"),
                                          sum(1 for r in v5["sets"][name].values() if r["outcome"] == "false_supported")],
                      "true_supported": [sum(1 for r in v4["sets"][name].values() if r["outcome"] == "true_supported"),
                                         sum(1 for r in v5["sets"][name].values() if r["outcome"] == "true_supported")]}
    g22r = {"changed_controls": sorted(cid for cid in v4["g22r"]
                                       if {r: _strip_version(i) for r, i in v4["g22r"][cid].items()}
                                       != {r: _strip_version(i) for r, i in v5["g22r"][cid].items()})}
    e4 = {n: {tuple(x[:3]): x for x in items} for n, items in v4["fixtures_8c"].items()}
    e5 = {n: {tuple(x[:3]): x for x in items} for n, items in v5["fixtures_8c"].items()}
    fixtures = {}
    for n in e4:
        added = sorted(e5[n].keys() - e4[n].keys())
        removed = sorted(e4[n].keys() - e5[n].keys())
        moved = sorted(k for k in e4[n].keys() & e5[n].keys() if e4[n][k][5:] != e5[n][k][5:])
        fixtures[n] = {"items": [len(e4[n]), len(e5[n])], "added": [list(k) for k in added],
                       "removed": [list(k) for k in removed], "provenance_moved": [list(k) for k in moved]}
    matrix = {k: {"v4": [a["numerator"], a["denominator"], a["score"]],
                  "v5": [v5["matrix_8c"][k]["numerator"], v5["matrix_8c"][k]["denominator"], v5["matrix_8c"][k]["score"]],
                  "status_changed": a["statuses"] != v5["matrix_8c"][k]["statuses"]}
              for k, a in v4["matrix_8c"].items()
              if (a["numerator"], a["denominator"], a["score"], a["statuses"]) !=
              (v5["matrix_8c"][k]["numerator"], v5["matrix_8c"][k]["denominator"], v5["matrix_8c"][k]["score"],
               v5["matrix_8c"][k]["statuses"])}
    return {
        "versions": {"before": v4["extractor_version"], "after": v5["extractor_version"]},
        "note": "real pipeline (README extractor, evidence aggregation, matcher v1, scoring v2); readme:v4 via "
                "readme_v4_pin (production's unchanged ATX-only heading index); public synthetic controls and public "
                "8c fixtures only; no LLM",
        "labelled_sets": sets,
        "g22r_controls": g22r,
        "fixtures_8c": fixtures,
        "matrix_8c_changes": matrix,
        "matrix_8c_pairs": len(v4["matrix_8c"]),
        "undefined_score_changes": sorted(k for k, a in v4["matrix_8c"].items()
                                          if (a["score"] is None) != (v5["matrix_8c"][k]["score"] is None)),
        "capability_identical": v4["capability"] == v5["capability"],
        "concepts": len(v4["capability"]),
    }


def main() -> None:
    if "--dump" in sys.argv:
        Path(sys.argv[sys.argv.index("--dump") + 1]).write_text(json.dumps(measure(), indent=1, ensure_ascii=False),
                                                                 encoding="utf-8")
        return
    if readme_mod.EXTRACTOR_VERSION != "readme:v5":
        raise SystemExit("G22-S1 compares readme:v4 (pinned) against production readme:v5")
    v5 = measure()
    with _pin():
        v4 = measure()
    report = compare(v4, v5)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "setext_boundary_comparison.json").write_bytes(
        (json.dumps(report, indent=1, ensure_ascii=False) + "\n").encode("utf-8"))
    for name, s in report["labelled_sets"].items():
        print(name.ljust(12), "recovered", len(s["readme_items_recovered"]), "excluded", len(s["readme_items_newly_excluded"]),
              "moved", len(s["provenance_moved"]), "status", len(s["match_status_changes"]), "FS", s["false_supported"],
              "trueSUP", s["true_supported"])
    print("g22r changed", report["g22r_controls"]["changed_controls"])
    print("8c", {n: v for n, v in report["fixtures_8c"].items() if v["added"] or v["removed"] or v["provenance_moved"]})
    print("8c matrix changes", report["matrix_8c_changes"], "undefined", report["undefined_score_changes"])
    print("capability identical", report["capability_identical"])


if __name__ == "__main__":
    main()
