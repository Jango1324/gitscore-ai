"""Milestone 11-G18 -- observability-aware score eligibility: runner.

    python scripts/evaluate_m11g18_scoring_eligibility.py [--private-corpora]

Evaluation-only. Runs the real v13 parser, matcher and assessor; policies
are simulated on the real `RequirementMatch` results (see
`scripts/evaluation_lib/m11g18_eligibility.py`). Historical frozen
reports and gold are READ, never written.

Writes (publication-safe: synthetic controls, tracked fixtures, counts):
* `evaluation/m11g18/eligibility_report.json` -- G18 + G15 corpora,
  registry capability table, G16/G17 compound controls, frozen 8c
  matrices, M10 rows.
* with `--private-corpora`: `evaluation/m11g18/private_eligibility_aggregates.json`
  (integer counts only; no posting text, file name or id).
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (REPO_ROOT / "src", REPO_ROOT / "scripts", REPO_ROOT / "scripts" / "evaluation_lib"):
    sys.path.insert(0, str(_p))

import m11g18_eligibility as el  # noqa: E402
from evaluation_lib import end_to_end_eval  # noqa: E402
from evaluation_lib.loaders import list_candidate_names, load_candidate_fixture, load_job  # noqa: E402
from gitscore.jobs.parsing.parser import JOB_DESCRIPTION_PARSER_VERSION, parse_job_description_with_diagnostics  # noqa: E402
from gitscore.matching import match_job  # noqa: E402
from m11g15_or_scoring import candidate_profile  # noqa: E402

OUT_DIR = REPO_ROOT / "evaluation" / "m11g18"
SCOREABLE = ("A_production", "B_prefix_exclusion", "C_capability_declared", "C_capability_oracle",
             "D_parser_fallback", "E_asymmetric_rejected")


def _policy_scores(analysis) -> dict:
    out = {}
    for policy in SCOREABLE:
        rows = [el.policy_row(policy, m) for m in analysis.requirement_matches]
        out[policy] = {**el.score_rows(rows),
                       "claim_satisfied": any(r["counted"] for r in rows)
                       and all(r["status"] == el.SUPPORTED for r in rows if r["counted"])}
    return out


def compound_controls() -> dict:
    """G16/G17's 58 frozen compound controls x evidence fixtures, under v13."""
    controls = json.loads((REPO_ROOT / "evaluation/m11g16/compound_logic_controls.json").read_text(
        encoding="utf-8"))["controls"]
    per = {}
    false_sup = {p: [] for p in SCOREABLE}
    changed = {p: [] for p in SCOREABLE}
    for c in controls:
        profile = parse_job_description_with_diagnostics(c["text"]).profile
        for fx, exp in c["expected"]["per_fixture"].items():
            s = _policy_scores(match_job(candidate_profile(exp["evidence"]), profile))
            per[f"{c['id']}/{fx}"] = {p: {k: s[p][k] for k in ("score", "supported", "eligible")} for p in SCOREABLE}
            for p in SCOREABLE:
                if s[p]["claim_satisfied"] and exp["gold_truth"] != "T":
                    false_sup[p].append(f"{c['id']}/{fx}")
                if (s[p]["score"], s[p]["eligible"]) != (s["A_production"]["score"], s["A_production"]["eligible"]):
                    changed[p].append(f"{c['id']}/{fx}")
    return {"fixture_outcomes": len(per),
            "false_supported": {p: {"count": len(v), "ids": v} for p, v in false_sup.items()},
            "outcomes_changed_vs_production": {p: len(v) for p, v in changed.items()},
            "changed_ids": {p: v for p, v in changed.items() if v}}


def frozen_8c() -> dict:
    names = list_candidate_names()
    out, profiles = {}, {}
    for label, rel in (("8c:v1", "evaluation/gold/matrix.json"), ("8c:v1.1", "evaluation/gold_v1_1/matrix.json")):
        matrix = json.loads((REPO_ROOT / rel).read_text(encoding="utf-8"))
        need = {p["candidate"]: load_candidate_fixture(next(n for n in names if n.lower() == p["candidate"].lower()))
                for p in matrix["pairs"] if p["candidate"] not in profiles}
        profiles.update(end_to_end_eval.build_candidate_profiles(need))
        pairs = {}
        for pair in matrix["pairs"]:
            job = load_job(pair["job_id"])
            parsed = parse_job_description_with_diagnostics(job["raw_text"], title=job.get("title"))
            analysis = match_job(profiles[pair["candidate"]], parsed.profile)
            s = _policy_scores(analysis)
            pairs[f"{pair['candidate']}/{pair['job_id']}"] = {
                p: {k: s[p][k] for k in ("score", "supported", "eligible")} for p in SCOREABLE}
            pairs[f"{pair['candidate']}/{pair['job_id']}"]["excluded_rows"] = sorted(
                f"{el.requirement_eligibility(m.requirement)[1]}" for m in analysis.requirement_matches
                if m.status.value != el.NOT_ASSESSABLE and not el.requirement_eligibility(m.requirement)[0])
        out[label] = {
            "pairs": pairs,
            "pairs_changed_vs_production": {p: sorted(k for k, v in pairs.items()
                                                      if (v[p]["score"], v[p]["eligible"])
                                                      != (v["A_production"]["score"], v["A_production"]["eligible"]))
                                            for p in SCOREABLE if p != "A_production"},
        }
    return out


def row_reasons(texts: list[str]) -> dict:
    reasons = Counter()
    technical = evaluable_excluded = 0
    for text in texts:
        for r in parse_job_description_with_diagnostics(text).profile.requirements:
            ok, why = el.requirement_eligibility(r)
            reasons[why.split(":")[0]] += 1
            if el.requirement_members(r):
                technical += 1
                if not ok:
                    evaluable_excluded += 1
    return {"rows_by_eligibility_reason": dict(sorted(reasons.items())), "technical_rows": technical,
            "technical_rows_excluded_by_capability_contract": evaluable_excluded}


def m10_rows() -> dict:
    return {p.stem: row_reasons([p.read_bytes().decode("utf-8")])
            for p in sorted((REPO_ROOT / "evaluation/m10/source").glob("*.txt"))}


def private_aggregates() -> dict:
    out = {"note": "previously inspected private postings -- not independent; integer counts only"}
    for name, rel in (("m11d", "evaluation/m11d/source"), ("m11f", "evaluation/m11f/source"),
                      ("m11g5", "evaluation/m11g5/source"), ("m11g9", "evaluation/m11g9/source")):
        src = REPO_ROOT / rel
        if not src.is_dir():
            raise SystemExit(f"--private-corpora requested but {rel} is missing")
        files = sorted(src.rglob("*.txt"))
        agg = row_reasons([p.read_bytes().decode("utf-8") for p in files])
        out[name] = {"postings": len(files), **agg}
    return out


def _summary(metrics: dict) -> dict:
    return {p: {k: v["count"] for k, v in m.items() if isinstance(v, dict) and "count" in v}
            for p, m in metrics.items()}


def run() -> dict:
    g18 = el.load_frozen_controls()["controls"]
    g15 = el.load_g15_controls()
    r18, r15 = el.run_corpus(g18), el.run_corpus(g15)
    return {
        "parser_version": JOB_DESCRIPTION_PARSER_VERSION,
        "note": "policies simulated on real production RequirementMatch results; every changed score is "
                "counterfactual. Historical reports and gold are read-only inputs.",
        "registry_capability": el.registry_capability_table(),
        "b_equals_c_declared": {"g18": el.b_equals_c_declared(r18["results"]),
                                "g15": el.b_equals_c_declared(r15["results"])},
        "g18_controls": {"metrics_summary": _summary(r18["metrics"]), "metrics": r18["metrics"],
                         "results": r18["results"]},
        "g15_controls": {"metrics_summary": _summary(r15["metrics"]), "metrics": r15["metrics"],
                         "results": r15["results"]},
        "g16_g17_compound_controls": compound_controls(),
        "frozen_8c": frozen_8c(),
        "m10_soti_manulife": m10_rows(),
    }


def main() -> None:
    report = run()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "eligibility_report.json").write_bytes((json.dumps(report, indent=2) + "\n").encode("utf-8"))
    for corpus in ("g18_controls", "g15_controls"):
        print(corpus)
        for p, m in report[corpus]["metrics_summary"].items():
            print(" ", p.ljust(24), m)
    print("B == C_declared:", report["b_equals_c_declared"])
    cc = report["g16_g17_compound_controls"]
    print("G16/G17 false SUPPORTED:", {p: v["count"] for p, v in cc["false_supported"].items()},
          "changed:", cc["outcomes_changed_vs_production"])
    for label, m in report["frozen_8c"].items():
        print(label, {p: len(v) for p, v in m["pairs_changed_vs_production"].items()})
    print("M10:", report["m10_soti_manulife"])
    if "--private-corpora" in sys.argv:
        agg = private_aggregates()
        (OUT_DIR / "private_eligibility_aggregates.json").write_bytes((json.dumps(agg, indent=2) + "\n").encode("utf-8"))
        for k, v in agg.items():
            if k != "note":
                print("[private]", k, v)


if __name__ == "__main__":
    main()
