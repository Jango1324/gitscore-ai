"""Milestone 11-G16 -- compound AND/OR requirement-logic evaluation.

    python scripts/evaluate_m11g16_compound_logic.py [--private-corpora]

Offline, deterministic, no LLM, no network, no production change (fix
options are installed in memory only, see `m11g16_compound_logic.install`).

Outputs:
* `evaluation/m11g16/compound_logic_report.json` -- frozen synthetic
  controls under production and each option; per-family false-SUPPORTED
  counts; frozen 8c:v1/v1.1 matrices re-scored per option (counterfactual);
  structure-change counts over TRACKED corpora. Reproducible from
  committed files.
* `evaluation/m11g16/private_impact_aggregates.json` -- only with
  `--private-corpora`: counts over the private M11-D/F/G5/G9 postings
  (fails loudly if absent). No posting text or file name is written.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO_ROOT / "src"), str(REPO_ROOT / "scripts"), str(REPO_ROOT / "scripts" / "evaluation_lib")]

import m11g16_compound_logic as sim  # noqa: E402
from evaluation_lib import end_to_end_eval  # noqa: E402
from evaluation_lib.loaders import list_candidate_names, load_candidate_fixture, load_job  # noqa: E402
from gitscore.assessment import assess_job  # noqa: E402
from gitscore.matching import match_job  # noqa: E402

REPORT_PATH = REPO_ROOT / "evaluation" / "m11g16" / "compound_logic_report.json"
PRIVATE_PATH = REPO_ROOT / "evaluation" / "m11g16" / "private_impact_aggregates.json"
MATRICES = {"8c:v1": REPO_ROOT / "evaluation" / "gold" / "matrix.json",
            "8c:v1.1": REPO_ROOT / "evaluation" / "gold_v1_1" / "matrix.json"}
PRIVATE_SOURCES = {"m11d": "evaluation/m11d/source", "m11f": "evaluation/m11f/source",
                   "m11g5": "evaluation/m11g5/source", "m11g9": "evaluation/m11g9/source"}


def _signature(profile) -> list:
    return [(sim.row_members(r), r.necessity.value, r.category) for r in profile.requirements]


def structure_changes(texts: list[str]) -> dict:
    out = {"texts": len(texts)}
    base = [_signature(sim.parse(t, "production")) for t in texts]
    for mode in sim.MODES[1:]:
        sigs = [_signature(sim.parse(t, mode)) for t in texts]
        out[mode] = {
            "texts_with_changed_rows": sum(1 for a, b in zip(base, sigs) if a != b),
            "rows_production": sum(len(s) for s in base),
            "rows_option": sum(len(s) for s in sigs),
        }
    return out


def rescore_matrices() -> dict:
    names = list_candidate_names()
    profiles: dict = {}
    out = {}
    for label, path in MATRICES.items():
        matrix = json.loads(path.read_text(encoding="utf-8"))
        fixtures = {}
        for pair in matrix["pairs"]:
            match = next(n for n in names if n.lower() == pair["candidate"].lower())
            fixtures[pair["candidate"]] = load_candidate_fixture(match)
        profiles.update(end_to_end_eval.build_candidate_profiles({k: v for k, v in fixtures.items()
                                                                  if k not in profiles}))
        pairs = []
        for pair in matrix["pairs"]:
            job = load_job(pair["job_id"])
            scores = {}
            for mode in sim.MODES:
                jp = sim.parse(job["raw_text"], mode)
                a = assess_job(match_job(profiles[pair["candidate"]], jp))
                scores[mode] = {"score": a.alignment_score, "assessable": a.assessable_count}
            pairs.append({"candidate": pair["candidate"], "job_id": pair["job_id"], "scores": scores})
        out[label] = {
            "pairs_evaluated": len(pairs), "pairs": pairs,
            "pairs_changed_vs_production": {m: [f"{p['candidate']}/{p['job_id']}" for p in pairs
                                                if p["scores"][m] != p["scores"]["production"]]
                                            for m in sim.MODES[1:]},
        }
    return out


def tracked_corpora() -> dict:
    jobs = [load_job(p.stem)["raw_text"] for p in sorted((REPO_ROOT / "evaluation" / "jobs").glob("*.json"))]
    m10 = [p.read_bytes().decode("utf-8") for p in sorted((REPO_ROOT / "evaluation" / "m10" / "source").glob("*.txt"))]
    g13 = [c["job_text"] for c in json.loads((REPO_ROOT / "evaluation" / "m11g13" / "generalization_controls.json")
                                             .read_text(encoding="utf-8"))["controls"] if c["kind"] == "or_contract"]
    g15 = [c["job_text"] for c in json.loads((REPO_ROOT / "evaluation" / "m11g15" / "or_scoring_controls.json")
                                             .read_text(encoding="utf-8"))["controls"]]
    return {"evaluation_jobs_8c_corpus": structure_changes(jobs), "m10_tracked_sources": structure_changes(m10),
            "g13_or_contract_controls": structure_changes(g13), "g15_or_scoring_controls": structure_changes(g15)}


def run() -> dict:
    report = sim.run()
    data = sim.load_frozen_controls()
    fam = Counter()
    for item in report["metrics"]["production"]["1_false_supported_claim_level"]["ids"]:
        cid = item.split("/")[0]
        fam[next(c["family"] for c in data["controls"] if c["id"] == cid)] += 1
    report["production_false_supported_by_family"] = dict(sorted(fam.items()))
    report["frozen_8c_matrices_counterfactual"] = rescore_matrices()
    report["tracked_corpus_structure_changes"] = tracked_corpora()
    return report


def main() -> None:
    report = run()
    REPORT_PATH.write_bytes((json.dumps(report, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    for k in report["metrics"]["production"]:
        print(k.ljust(46), " | ".join(f"{report['metrics'][m][k]['count']}/{report['metrics'][m][k]['denominator']}"
                                       for m in sim.MODES))
    print("production false SUPPORTED by family:", report["production_false_supported_by_family"])
    for label, m in report["frozen_8c_matrices_counterfactual"].items():
        print(label, {k: len(v) for k, v in m["pairs_changed_vs_production"].items()})
    for name, c in report["tracked_corpus_structure_changes"].items():
        print(name, c)
    if "--private-corpora" in sys.argv:
        missing = [d for d in PRIVATE_SOURCES.values() if not (REPO_ROOT / d).is_dir()]
        if missing:
            raise SystemExit("--private-corpora requested but private sources are missing: " + ", ".join(missing))
        private = {"note": "previously inspected private postings -- not independent; counts only",
                   **{k: structure_changes([p.read_bytes().decode("utf-8")
                                            for p in sorted((REPO_ROOT / d).rglob("*.txt"))])
                      for k, d in PRIVATE_SOURCES.items()}}
        PRIVATE_PATH.write_bytes((json.dumps(private, indent=2) + "\n").encode("utf-8"))
        for k, v in private.items():
            if k != "note":
                print("[private]", k, v)
    print(f"wrote {REPORT_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
