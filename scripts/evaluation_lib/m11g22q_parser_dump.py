"""Milestone 11-G22-Q -- version-neutral parser/matcher/scoring dump (parser v14 or v15).

    python m11g22q_parser_dump.py <repo_root> <out.json> [--private]

Runs inside whatever checkout `repo_root` is (a throwaway clone of the pinned v14
commit, or the v15 working tree) and writes:

  * everything G21's dump (`m11g21_parser_dump.py`, reused unchanged) records: G20/G21
    control sets, G21 negation-scope controls, the tracked historical corpora (G6, G7,
    G15, G16, G18, M10D, M10E, 8c jobs, M10 SOTI/Manulife), scoring on the G15/G16/G18
    fixtures, the frozen 8c v1/v1.1 matrices and M10, and (--private) counts-only
    private aggregates;
  * the G22 DEV/EVAL concept controls through G22's own harness (BASE = the live parser);
  * G22's fixture scoring views (G16 claim-level false SUPPORTED definition);
  * the G13 OR-contract controls (parse + scoring with their declared evidence);
  * M10E-g3 and M10E row-existence (G22's own functions);
  * (--private) G22's counts-only private concept view.

Real parser, matcher, scoring v2 and API serializer only; nothing is simulated.
Input DATA is read from `M11G21_DATA_ROOT` where G21's dump does so. Private
postings never leave this process: only integer counts are written.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import m11g21_parser_dump as base  # noqa: E402  (sets sys.path to <repo_root>/src, scripts, evaluation_lib)

import evaluate_m11g22_concept_precision as g22  # noqa: E402
import m11g22_concepts as h  # noqa: E402
import m11g22_policies as pol  # noqa: E402
from m11g15_or_scoring import candidate_profile  # noqa: E402

import gitscore  # noqa: E402

ROOT, OUT = base.ROOT, base.OUT


def _evidence_view(profile, text: str) -> dict:
    """Matcher evidence on every requirement (counted or not): attached evidence items and matched ids."""
    from gitscore.jobs.parsing.parser import parse_job_description_with_diagnostics
    from gitscore.matching import match_job
    ms = match_job(profile, parse_job_description_with_diagnostics(text).profile).requirement_matches
    return {"evidence_items": sum(len(m.supporting_evidence) for m in ms),
            "matched_concepts": sorted(c for m in ms for c in m.matched_concept_ids)}


def _g22_control(r: dict) -> dict:
    return {k: r[k] for k in ("produced", "placeholders", "unparsed_claims", "exact", "taxonomy", "false_registered",
                              "fabricated_unresolved", "recalled_ids")}


def main() -> None:
    assert Path(gitscore.__file__).resolve().is_relative_to(ROOT / "src"), gitscore.__file__
    base.main()  # writes the G21-style dump to OUT
    dump = json.loads(OUT.read_text(encoding="utf-8"))
    dump["gitscore_imported_from_repo_root"] = True

    dump["g22_controls"] = {}
    for split in ("dev", "eval"):
        results, agg = h.run_split(split, pol.BASE)
        dump["g22_controls"][split] = {"aggregate": agg, "controls": {r["id"]: _g22_control(r) for r in results}}

    dump["g22_scoring"] = {name: [[fid, gold, {**g22._score_view(profile, text, pol.BASE),
                                                **_evidence_view(profile, text)}]
                                  for fid, profile, text, gold in items]
                           for name, items in g22.scoring_inputs().items()}

    g13 = json.loads((ROOT / "evaluation/m11g13/generalization_controls.json").read_text(encoding="utf-8"))
    dump["g13_or_contract"] = {
        c["id"]: {**base.parse_view(c["job_text"]),
                  "score": base.score_view(candidate_profile(c["candidate_evidence_concepts"]), c["job_text"])}
        for c in g13["controls"] if c["kind"] == "or_contract"}

    dump["m10e_g3"] = g22.m10e_g3()
    dump["m10e_row_existence_mismatches"] = g22.m10e_row_existence(pol.BASE)

    if "--private" in sys.argv:
        # G22's private_counts() reads the (untracked) private postings from ITS checkout root; a pinned
        # clone has none, so point it at the data root exactly as G21's dump does (read-only).
        g22.REPO_ROOT = base.DATA_ROOT
        dump["g22_private"] = {name: {k: (v if k != "_per" else [list(x) for x in v]) for k, v in agg.items()}
                               for name, agg in g22.private_counts(pol.BASE).items()}
    OUT.write_text(json.dumps(dump), encoding="utf-8")


if __name__ == "__main__":
    main()
