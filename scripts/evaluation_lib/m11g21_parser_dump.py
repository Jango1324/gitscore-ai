"""Milestone 11-G21 -- version-neutral parser/matcher/scoring dump (parser v13 or v14).

    python m11g21_parser_dump.py <repo_root> <out.json> [--private]

Runs the REAL parser, matcher, scoring v2 and API serializer of whatever checkout
`repo_root` is (a throwaway clone of the pinned v13 commit, or the v14 working
tree) over identical corpora and writes the outcomes. Input DATA that only exists
in the working tree (the G21 adversarial controls, private corpora) is read from
`M11G21_DATA_ROOT`. Private postings are summarised as INTEGER COUNTS only.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])
DATA_ROOT = Path(os.environ.get("M11G21_DATA_ROOT", str(ROOT)))
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts"), str(ROOT / "scripts" / "evaluation_lib")]

import m11g20_admission as adm  # noqa: E402
import m11g20_historical as hist  # noqa: E402
from evaluation_lib import end_to_end_eval  # noqa: E402
from evaluation_lib.loaders import list_candidate_names, load_candidate_fixture, load_job  # noqa: E402
from gitscore.api.serialization import serialize_job_analysis_result  # noqa: E402
from gitscore.application import JobAnalysisResult  # noqa: E402
from gitscore.assessment import SCORING_VERSION, assess_job  # noqa: E402
from gitscore.jobs.parsing.parser import JOB_DESCRIPTION_PARSER_VERSION, parse_job_description_with_diagnostics  # noqa: E402
from gitscore.matching import MATCHER_VERSION, match_job  # noqa: E402
from m11g15_or_scoring import candidate_profile  # noqa: E402


def _members(r) -> list[str]:
    return sorted(r.alternative_concept_ids) or ([r.concept_id] if r.concept_id else [])


def parse_view(text: str) -> dict:
    p = parse_job_description_with_diagnostics(text)
    return {"rows": [{"members": _members(r), "category": r.category, "necessity": r.necessity.value,
                      "span": [r.source_span.start, r.source_span.end],
                      "text_ok": text[r.source_span.start:r.source_span.end] == r.original_text}
                     for r in p.profile.requirements],
            "unparsed": [[u.source_span.start, u.source_span.end] for u in p.unparsed_claims],
            "unparsed_text_ok": all(text[u.source_span.start:u.source_span.end] == u.text for u in p.unparsed_claims)}


def score_view(profile, text: str) -> dict:
    p = parse_job_description_with_diagnostics(text)
    a = assess_job(match_job(profile, p.profile))
    resp = serialize_job_analysis_result(JobAnalysisResult(
        candidate_profile=profile, job_profile=p.profile, assessment=a, extractor_failures=(),
        unknown_dependency_names=(), unparsed_claims=p.unparsed_claims))
    ms = a.match_analysis.requirement_matches
    rows = []
    for m in ms:
        reason = a.alignment_exclusion_reason(m)
        rows.append({"span": [m.requirement.source_span.start, m.requirement.source_span.end],
                     "members": _members(m.requirement), "necessity": m.requirement.necessity.value,
                     "status": m.status.value, "counts": a.counts_toward_alignment(m),
                     "reason": None if reason is None else reason.value})
    return {"score": a.alignment_score, "assessable": a.assessable_count,
            "excluded": resp.assessment.excluded_from_alignment_count,
            "supported_counted": sum(1 for r in rows if r["counts"] and r["status"] == "supported"),
            "unparsed_claim_count": resp.assessment.unparsed_claim_count, "rows": rows}


def main() -> None:
    dump = {"parser_version": JOB_DESCRIPTION_PARSER_VERSION, "scoring_version": SCORING_VERSION,
            "matcher_version": MATCHER_VERSION}
    # G20 frozen controls + G21 adversarial controls, scored per unit by G20's own evaluator.
    adversarial = json.loads((DATA_ROOT / "evaluation/m11g21/adversarial_controls.json").read_text(encoding="utf-8"))
    sets = {"g20_dev": adm.load_controls("dev"), "g20_holdout": adm.load_controls("holdout"),
            "g21_adversarial": adversarial["controls"]}
    dump["controls"] = {}
    for name, controls in sets.items():
        results = [adm.evaluate_control(c, adm.POLICY_V13) for c in controls]
        dump["controls"][name] = {
            "aggregate": adm.aggregate(results),
            "units": [{"id": r["id"], "pair": r["pair"], **{k: u[k] for k in (
                "uid", "qual", "ambiguous", "gold_nec", "kind", "outcome", "row_necessities", "fabricated_concepts",
                "represented_tech", "attribution")}, "rows": [{k: x[k] for k in ("kind", "members", "necessity", "span")}
                                                              for x in u["rows"]]}
                      for r in results for u in r["units"]],
            "scoring": {r["id"]: r["scoring"] for r in results},
            "parse": {c["id"]: parse_view(c["text"]) for c in controls},
        }
    # G21 Option B pre-labelled negation-scope examples (exact expected rows), when present.
    ns_path = DATA_ROOT / "evaluation/m11g21/negation_scope_controls.json"
    if ns_path.exists() and not os.environ.get("M11G21_SKIP_NEGATION_SCOPE"):  # skipped when reproducing first v14
        def labels(text):
            out = []
            for r in parse_job_description_with_diagnostics(text).profile.requirements:
                members = _members(r)
                out.append(["|".join(members) if members else (r.category or ""), r.necessity.value])
            return sorted(out)
        dump["negation_scope"] = {c["id"]: {**parse_view(c["text"]), "labels": labels(c["text"])}
                                  for c in json.loads(ns_path.read_text(encoding="utf-8"))["controls"]}
    # Tracked historical corpora: parse view for every text (+ gold admission spans).
    # Identical input BYTES for both checkouts: a Windows clone checks text files out with
    # autocrlf, which would shift every span of a .txt posting and fake a v13/v14 difference.
    hist.ROOT = DATA_ROOT
    corp = hist.tracked_corpora()
    dump["corpora"] = {name: {iid: {**parse_view(text), "gold": gold} for iid, text, gold in items}
                       for name, items in corp.items()}
    # Scoring on real candidate fixtures.
    scoring = {}
    for name, rel, tkey in (("g15", "evaluation/m11g15/or_scoring_controls.json", "job_text"),
                            ("g18", "evaluation/m11g18/eligibility_controls.json", "job_text")):
        cs = json.loads((ROOT / rel).read_text(encoding="utf-8"))["controls"]
        scoring[name] = {f"{c['id']}/{k['name']}": score_view(candidate_profile(k["evidence"]), c[tkey])
                         for c in cs for k in c["candidates"]}
    g16 = json.loads((ROOT / "evaluation/m11g16/compound_logic_controls.json").read_text(encoding="utf-8"))["controls"]
    scoring["g16"] = {f"{c['id']}/{fx}": score_view(candidate_profile(f["evidence"]), c["text"])
                      for c in g16 for fx, f in c["expected"]["per_fixture"].items()}
    names = list_candidate_names()
    profiles: dict = {}
    for label, rel in (("8c:v1", "evaluation/gold/matrix.json"), ("8c:v1.1", "evaluation/gold_v1_1/matrix.json")):
        matrix = json.loads((ROOT / rel).read_text(encoding="utf-8"))
        need = {p["candidate"]: load_candidate_fixture(next(n for n in names if n.lower() == p["candidate"].lower()))
                for p in matrix["pairs"] if p["candidate"] not in profiles}
        profiles.update(end_to_end_eval.build_candidate_profiles(need))
        scoring[label] = {f"{p['candidate']}/{p['job_id']}": score_view(profiles[p["candidate"]],
                                                                         load_job(p["job_id"])["raw_text"])
                          for p in matrix["pairs"]}
    empty = candidate_profile([])
    scoring["m10"] = {p.stem: score_view(empty, p.read_bytes().decode("utf-8"))
                      for p in sorted((DATA_ROOT / "evaluation/m10/source").glob("*.txt"))}
    dump["scoring"] = scoring

    if "--private" in sys.argv:
        # hist.ROOT is already DATA_ROOT (read-only; private texts never leave this process)
        priv = {}
        for name, texts in hist.private_texts().items():
            agg = {"postings": len(texts)}
            per = []
            for t in texts:
                pv = parse_view(t)
                sv = score_view(empty, t)
                per.append((len(pv["rows"]), sum(r["necessity"] == "required" for r in pv["rows"]),
                            sum(r["necessity"] == "preferred" for r in pv["rows"]), len(pv["unparsed"]),
                            sv["assessable"]))
            for i, key in enumerate(("rows", "required_rows", "preferred_rows", "unparsed_claims", "denominator_rows")):
                agg[key] = sum(p[i] for p in per)
            agg["postings_with_no_eligible_requirement"] = sum(1 for p in per if p[4] == 0)
            agg["postings_with_no_rows"] = sum(1 for p in per if p[0] == 0)
            agg["per_posting"] = [list(p) for p in per]  # integer tuples only, positional (no ids)
            priv[name] = agg
        dump["private_unlabeled"] = priv
        labeled = hist.private_labeled_impact(())
        dump["private_labeled"] = {k: (v if k == "note" else {kk: vv for kk, vv in v.items() if kk != "v13"} |
                                       ({"live": v["v13"]} if isinstance(v, dict) and "v13" in v else {}))
                                   for k, v in labeled.items()}
    OUT.write_text(json.dumps(dump), encoding="utf-8")


if __name__ == "__main__":
    main()
