"""Milestone 11-G15 -- mixed-observability OR scoring integrity evaluation.

    python scripts/evaluate_m11g15_or_scoring.py [--private-corpora]

Offline, deterministic, no LLM, no network, no production change.

Outputs:
* `evaluation/m11g15/or_scoring_report.json` -- frozen synthetic controls
  through the real parser/matcher/assessor (policy A) and simulated
  policies B-D, plus the frozen 8c:v1 / 8c:v1.1 matrix re-scored under
  every policy. Reproducible from committed files.
* `evaluation/m11g15/structure_frequency.json` -- how often each affected
  OR structure occurs in the live parser v12's output, as AGGREGATE COUNTS
  only. Tracked corpora always; the private M11-D/F/G5/G9 postings only
  with the explicit `--private-corpora` flag (fails loudly if absent). No
  posting text or file name is ever written.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO_ROOT / "src"), str(REPO_ROOT / "scripts"), str(REPO_ROOT / "scripts" / "evaluation_lib")]

import m11g15_or_scoring as orsc  # noqa: E402
from evaluation_lib import end_to_end_eval  # noqa: E402
from evaluation_lib.loaders import list_candidate_names, load_candidate_fixture, load_job  # noqa: E402
from gitscore.concepts.registry import is_unresolved_concept_id  # noqa: E402
from gitscore.jobs.parsing.parser import parse_job_description  # noqa: E402
from gitscore.matching import match_job  # noqa: E402

REPORT_PATH = REPO_ROOT / "evaluation" / "m11g15" / "or_scoring_report.json"
FREQ_PATH = REPO_ROOT / "evaluation" / "m11g15" / "structure_frequency.json"
MATRICES = {"8c:v1": REPO_ROOT / "evaluation" / "gold" / "matrix.json",
            "8c:v1.1": REPO_ROOT / "evaluation" / "gold_v1_1" / "matrix.json"}
PRIVATE_SOURCES = {"m11d": "evaluation/m11d/source", "m11f": "evaluation/m11f/source",
                   "m11g5": "evaluation/m11g5/source", "m11g9": "evaluation/m11g9/source"}


def rescore_matrices() -> dict:
    out = {}
    names = list_candidate_names()
    profile_cache: dict = {}
    for label, path in MATRICES.items():
        matrix = json.loads(path.read_text(encoding="utf-8"))
        fixtures = {}
        for pair in matrix["pairs"]:
            match = next(n for n in names if n.lower() == pair["candidate"].lower())
            fixtures[pair["candidate"]] = load_candidate_fixture(match)
        missing = {k: v for k, v in fixtures.items() if k not in profile_cache}
        profile_cache.update(end_to_end_eval.build_candidate_profiles(missing))
        pairs = []
        for pair in matrix["pairs"]:
            job = load_job(pair["job_id"])
            jp = parse_job_description(job["raw_text"], title=job.get("title"))
            analysis = match_job(profile_cache[pair["candidate"]], jp)
            scores = {}
            for policy in orsc.POLICIES:
                sc, sup, ass = orsc.score([orsc.policy_status(policy, m)[0] for m in analysis.requirement_matches])
                scores[policy] = {"score": sc, "supported": sup, "assessable": ass}
            # Attribution only (not a candidate policy): policy B applied to OR groups alone.
            sc, sup, ass = orsc.score([
                orsc.policy_status("B_exclude_unresolved_groups", m)[0] if m.requirement.alternative_concept_ids
                else m.status.value for m in analysis.requirement_matches])
            pairs.append({
                "candidate": pair["candidate"], "job_id": pair["job_id"],
                "or_groups_with_unresolved_member": sum(
                    bool(r.alternative_concept_ids) and orsc.has_unresolved(r) for r in jp.requirements),
                "single_unresolved_concept_rows": sum(
                    bool(r.concept_id) and orsc.has_unresolved(r) for r in jp.requirements),
                "scores": scores,
                "attribution_B_applied_to_or_groups_only": {"score": sc, "supported": sup, "assessable": ass},
            })
        changed = {p: [f"{x['candidate']}/{x['job_id']}" for x in pairs
                       if x["scores"][p]["score"] != x["scores"]["A_production"]["score"]] for p in orsc.POLICIES[1:]}
        or_only = [f"{x['candidate']}/{x['job_id']}" for x in pairs
                   if x["attribution_B_applied_to_or_groups_only"]["score"] != x["scores"]["A_production"]["score"]]
        out[label] = {"pairs_evaluated": len(pairs), "pairs": pairs,
                      "pairs_with_changed_alignment_vs_production": {p: {"count": len(v), "ids": v}
                                                                      for p, v in changed.items()},
                      "pairs_changed_by_or_groups_alone": {"count": len(or_only), "ids": or_only}}
    return out


_AND_MARKER = re.compile(r"\band\b|,\s*and\b", re.IGNORECASE)


def _structure_counts(texts: list[str]) -> dict:
    c = {"postings": len(texts), "rows": 0, "technical_rows": 0, "or_groups": 0,
         "or_groups_all_registry": 0, "or_groups_with_unresolved_member": 0,
         "or_groups_mixed_registry_and_unresolved": 0, "or_groups_all_unresolved": 0,
         "or_groups_possible_and_or_mixing": 0, "unsafe_alternative_fallback_rows": 0,
         "unresolved_requirement_fallback_rows": 0, "single_unresolved_concept_rows": 0}
    for text in texts:
        for r in parse_job_description(text).requirements:
            c["rows"] += 1
            ids = orsc.row_concepts(r)
            if ids:
                c["technical_rows"] += 1
            if r.category == "alternative_requirement":
                c["unsafe_alternative_fallback_rows"] += 1
            if r.category == "unresolved_requirement":
                c["unresolved_requirement_fallback_rows"] += 1
            if r.concept_id and is_unresolved_concept_id(r.concept_id):
                c["single_unresolved_concept_rows"] += 1
            if r.alternative_concept_ids:
                c["or_groups"] += 1
                unresolved = [i for i in ids if is_unresolved_concept_id(i)]
                if not unresolved:
                    c["or_groups_all_registry"] += 1
                else:
                    c["or_groups_with_unresolved_member"] += 1
                    c["or_groups_mixed_registry_and_unresolved" if len(unresolved) < len(ids)
                      else "or_groups_all_unresolved"] += 1
                if r.source_span is not None and _AND_MARKER.search(text[r.source_span.start:r.source_span.end]):
                    c["or_groups_possible_and_or_mixing"] += 1
    return c


def structure_frequency(private: bool) -> dict:
    tracked = {
        "evaluation_jobs_8c_corpus": [load_job(p.stem)["raw_text"]
                                      for p in sorted((REPO_ROOT / "evaluation" / "jobs").glob("*.json"))],
        "m10_tracked_sources": [p.read_bytes().decode("utf-8")
                                for p in sorted((REPO_ROOT / "evaluation" / "m10" / "source").glob("*.txt"))],
    }
    out = {"note": "aggregate counts of live parser v12 output; 'or_groups_possible_and_or_mixing' is a lexical "
                   "flag (an 'and' inside the OR group's source span), not a confirmed flattening",
           "tracked": {k: _structure_counts(v) for k, v in tracked.items()}}
    if private:
        missing = [d for d in PRIVATE_SOURCES.values() if not (REPO_ROOT / d).is_dir()]
        if missing:
            raise SystemExit("--private-corpora requested but private sources are missing: " + ", ".join(missing))
        out["private_inspected_not_independent"] = {
            k: _structure_counts([p.read_bytes().decode("utf-8") for p in sorted((REPO_ROOT / d).rglob("*.txt"))])
            for k, d in PRIVATE_SOURCES.items()
        }
    return out


def run() -> dict:
    report = orsc.run()
    report["frozen_8c_matrices"] = rescore_matrices()
    return report


def main() -> None:
    report = run()
    REPORT_PATH.write_bytes((json.dumps(report, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    for p, m in report["metrics"].items():
        print(f"== {p}")
        for k, v in m.items():
            if isinstance(v, dict) and "count" in v:
                print(f"  {k}: {v['count']}/{v['denominator']}")
    print("score changes vs production (synthetic):",
          {p: v["count"] for p, v in report["7_score_changes_vs_production"].items()})
    for label, m in report["frozen_8c_matrices"].items():
        print(label, "pairs:", m["pairs_evaluated"], "| changed vs production:",
              {p: v["count"] for p, v in m["pairs_with_changed_alignment_vs_production"].items()},
              "| changed by OR groups alone:", m["pairs_changed_by_or_groups_alone"]["count"],
              "| pairs with unresolved OR group:", sum(1 for x in m["pairs"] if x["or_groups_with_unresolved_member"]),
              "| pairs with single unresolved row:", sum(1 for x in m["pairs"] if x["single_unresolved_concept_rows"]))
    freq = structure_frequency("--private-corpora" in sys.argv)
    FREQ_PATH.write_bytes((json.dumps(freq, indent=2) + "\n").encode("utf-8"))
    for group, sets in freq.items():
        if isinstance(sets, dict):
            for name, c in sets.items():
                print(f"[{group}] {name}: {c}")
    print(f"wrote {REPORT_PATH.relative_to(REPO_ROOT)} and {FREQ_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
