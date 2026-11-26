"""Milestone 11-G23 -- control-set evaluation and metrics (OFFLINE research only).

Unit outcomes come from G20's `m11g20_admission.evaluate_control` (unchanged; its segmentation is replaced by
the G23 replica through `m11g23_harness.active`). On top of G20's outcome classes this module adds the G23
strict measures: a qualification counts as RECOVERED only when every expected technology is represented, no
unexpected concept is emitted, and the necessity matches the gold label (or the gold necessity is `unknown`).
"""
from __future__ import annotations

import json
from collections import Counter

import m11g20_admission as adm
import m11g23_harness as hz
from m11g15_or_scoring import candidate_profile

from gitscore.assessment import assess_job
from gitscore.concepts.registry import default_registry
from gitscore.jobs.parsing.parser import parse_job_description_with_diagnostics
from gitscore.matching import match_job

SPLITS = {"dev": hz.REPO_ROOT / "evaluation/m11g23/controls_dev.json",
          "eval": hz.REPO_ROOT / "evaluation/m11g23/controls_eval.json"}
NONQUAL_CLASSES = {
    "duty": {"responsibility"},
    "employer": {"company", "product", "stack", "team_practice", "tech_discussion"},
    "benefits": {"benefits"},
    "process": {"process"},
    "personality": {"personality"},
    "negated_historical_learning": {"negation", "learning"},
}


def load(split: str) -> list[dict]:
    return json.loads(SPLITS[split].read_text(encoding="utf-8"))["controls"]


def _members(r) -> list[str]:
    return sorted(r.alternative_concept_ids) or ([r.concept_id] if r.concept_id else [])


def score_view(text: str, evidence: list[str]) -> dict:
    """Real parser -> matcher v1 -> scoring v2 for one control and one candidate evidence set."""
    p = parse_job_description_with_diagnostics(text)
    a = assess_job(match_job(candidate_profile(evidence), p.profile))
    rows = [{"span": [m.requirement.source_span.start, m.requirement.source_span.end],
             "members": _members(m.requirement), "necessity": m.requirement.necessity.value,
             "category": m.requirement.category, "status": m.status.value,
             "counts": a.counts_toward_alignment(m)} for m in a.match_analysis.requirement_matches]
    numerator = sum(1 for r in rows if r["counts"] and r["status"] == "supported")
    return {"score": a.alignment_score, "denominator": a.assessable_count, "numerator": numerator,
            "unparsed": len(p.unparsed_claims), "rows": rows}


def full_evidence(control: dict) -> list[str]:
    """Evidence for every registered concept the control names (the G20 'full' candidate, label-derived only so
    it is identical under every policy)."""
    registry = default_registry()
    return sorted({t for u in control["units"] for t in u["tech"] if registry.get(t) is not None})


def strict_unit(u: dict) -> dict:
    gold_tech = set(u["gold_tech"])
    represented = set(u["represented_tech"])
    nec_ok = u["gold_nec"] in ("unknown", None) or u["row_necessities"] == [u["gold_nec"]]
    if gold_tech:
        content_ok = represented == gold_tech and not u["fabricated_concepts"]
    else:
        content_ok = u["legit_row_count"] > 0 and not u["fabricated_concepts"]
    return {"recovered": bool(u["qual"] and not u["ambiguous"] and u["outcome"] == "represented"
                              and content_ok and nec_ok),
            "concept_ok": content_ok, "necessity_ok": nec_ok and bool(u["rows"])}


def run(split: str, policy) -> dict:
    controls = load(split)
    results, scores = [], {}
    with hz.active(policy):
        for c in controls:
            r = adm.evaluate_control(c, adm.POLICY_V13)
            for u in r["units"]:
                u["strict"] = strict_unit(u)
            results.append(r)
            scores[c["id"]] = {"none": score_view(c["text"], []), "full": score_view(c["text"], full_evidence(c))}
    return {"results": results, "scores": scores, "metrics": metrics(results, controls, scores)}


def metrics(results: list[dict], controls: list[dict], scores: dict) -> dict:
    fam = {c["id"]: c["family"] for c in controls}
    units = [(fam[r["id"]], u) for r in results for u in r["units"]]
    qual = [(f, u) for f, u in units if u["qual"] and not u["ambiguous"]]
    tech_qual = [(f, u) for f, u in qual if u["gold_tech"]]
    nonqual = [(f, u) for f, u in units if not u["qual"]]
    rec = [(f, u) for f, u in qual if u["strict"]["recovered"]]
    by_family: dict[str, dict] = {}
    for f in sorted({f for f, _ in units}):
        fq = [u for g, u in qual if g == f]
        fn = [u for g, u in nonqual if g == f]
        by_family[f] = {"qual_units": len(fq), "recovered": sum(1 for u in fq if u["strict"]["recovered"]),
                        "nonqual_units": len(fn), "false_admitted": sum(1 for u in fn if u["rows"])}
    false_by_class = {name: sum(1 for _, u in nonqual if u["kind"] in kinds and u["rows"])
                      for name, kinds in NONQUAL_CLASSES.items()}
    rows_all = [row for _, u in units for row in u["rows"]]
    represented = [u for _, u in qual if u["outcome"] == "represented"]
    nec_scored = [u for u in represented if u["gold_nec"] in ("required", "preferred")]
    full = [scores[c["id"]]["full"] for c in controls]
    return {
        "units": {"total": len(units), "qualification": len(qual), "technical_qualification": len(tech_qual),
                  "non_qualification": len(nonqual), "ambiguous": sum(1 for _, u in units if u["ambiguous"])},
        "1_recall_strict": {"recovered": len(rec), "of": len(qual),
                            "technical_recovered": sum(1 for _, u in tech_qual if u["strict"]["recovered"]),
                            "technical_of": len(tech_qual)},
        "1b_represented_any": sum(1 for _, u in qual if u["outcome"] == "represented"),
        "2_incorrect_admissions": {"units": sum(1 for _, u in nonqual if u["rows"]),
                                   "rows": sum(len(u["rows"]) for _, u in nonqual),
                                   "required_rows": sum(1 for _, u in nonqual for r in u["rows"]
                                                        if r["necessity"] == "required"),
                                   "unmapped_rows": sum(len(r["unmapped_rows"]) for r in results),
                                   "by_class": false_by_class},
        "3_concept_exact": {"units_concept_ok": sum(1 for _, u in qual if u["rows"] and u["strict"]["concept_ok"]),
                            "of_admitted_qual": sum(1 for _, u in qual if u["rows"]),
                            "fabricated_concepts": sum(len(u["fabricated_concepts"]) for _, u in units)},
        "4_necessity": {"correct": sum(1 for u in nec_scored if u["row_necessities"] == [u["gold_nec"]]),
                        "of": len(nec_scored),
                        "preferred_gold_marked_required": sum(1 for u in nec_scored if u["gold_nec"] == "preferred"
                                                              and "required" in u["row_necessities"]),
                        "required_gold_marked_preferred": sum(1 for u in nec_scored if u["gold_nec"] == "required"
                                                              and "preferred" in u["row_necessities"])},
        "7_span": {"rows": len(rows_all),
                   "within_unit": sum(1 for _, u in units for r in u["rows"]
                                      if u["start"] <= r["span"][0] and r["span"][1] <= u["end"])
                   if units and "start" in units[0][1] else None,
                   "units_span_exact": sum(1 for _, u in units if u["rows"] and u["span_exact"]),
                   "units_span_within": sum(1 for _, u in units if u["rows"] and u["span_within_unit"]),
                   "units_with_rows": sum(1 for _, u in units if u["rows"])},
        "outcomes": dict(Counter(u["outcome"] for _, u in units)),
        "by_family": by_family,
        "scoring_full_evidence": {
            "defined_scores": sum(1 for s in full if s["score"] is not None),
            "denominator_total": sum(s["denominator"] for s in full),
            "numerator_total": sum(s["numerator"] for s in full),
            "counted_non_technical_rows": sum(1 for s in full for r in s["rows"]
                                              if r["counts"] and not r["members"]),
        },
    }


def compare_scores(base: dict, other: dict) -> dict:
    """MatchStatus, numerator / denominator, score and undefined-score changes between two `run()` outputs."""
    out = Counter()
    changed_controls = []
    for cid, b in base["scores"].items():
        o = other["scores"][cid]
        for ev in ("none", "full"):
            bs, os_ = b[ev], o[ev]
            key = lambda r: (tuple(r["span"]), tuple(r["members"]))  # noqa: E731
            bm = {key(r): r for r in bs["rows"]}
            om = {key(r): r for r in os_["rows"]}
            for k in set(bm) | set(om):
                if k not in bm:
                    out[f"{ev}_rows_added"] += 1
                elif k not in om:
                    out[f"{ev}_rows_removed"] += 1
                elif bm[k]["status"] != om[k]["status"]:
                    out[f"{ev}_status_changed"] += 1
                elif bm[k]["necessity"] != om[k]["necessity"]:
                    out[f"{ev}_necessity_changed"] += 1
            if bs["score"] != os_["score"]:
                out[f"{ev}_score_changed"] += 1
                if ev == "full":
                    changed_controls.append(cid)
            if (bs["score"] is None) != (os_["score"] is None):
                out[f"{ev}_undefined_changed"] += 1
            out[f"{ev}_numerator_delta"] += os_["numerator"] - bs["numerator"]
            out[f"{ev}_denominator_delta"] += os_["denominator"] - bs["denominator"]
    return {**dict(sorted(out.items())), "full_score_changed_controls": sorted(changed_controls)}
