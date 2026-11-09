"""Milestone 11-G17 -- version-neutral parse/match/assess dump.

    python m11g17_parse_dump.py <repo_root> <out.json> [--private]

Runs the REAL parser/matcher/assessor of whatever checkout `repo_root`
is (a throwaway v12 clone of HEAD, or the v13 working tree) over fixed
corpora and writes their outcomes. It reads the frozen G15/G16 controls
and 8c fixtures from `repo_root`. Private postings (only with --private)
are dumped WITHOUT any text: concept members, category and necessity only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts"), str(ROOT / "scripts" / "evaluation_lib")]

from evaluation_lib import end_to_end_eval  # noqa: E402
from evaluation_lib.loaders import list_candidate_names, load_candidate_fixture, load_job  # noqa: E402
from gitscore.assessment import assess_job  # noqa: E402
from gitscore.jobs.parsing.parser import JOB_DESCRIPTION_PARSER_VERSION, parse_job_description_with_diagnostics  # noqa: E402
from gitscore.matching import MatchStatus, match_job  # noqa: E402
from m11g15_or_scoring import candidate_profile  # noqa: E402


def rows_of(profile, text=None):
    out = []
    for r in profile.requirements:
        row = {"members": sorted(r.alternative_concept_ids) if r.alternative_concept_ids
               else ([r.concept_id] if r.concept_id else []),
               "category": r.category, "necessity": r.necessity.value}
        if text is not None:
            row["span_text"] = text[r.source_span.start:r.source_span.end] if r.source_span else None
            row["original_text"] = r.original_text
        out.append(row)
    return out


def outcome(profile, evidence):
    analysis = match_job(candidate_profile(evidence), profile)
    a = assess_job(analysis)
    scored = [m for m in analysis.requirement_matches if m.status != MatchStatus.NOT_ASSESSABLE]
    sup = [m for m in scored if m.status == MatchStatus.SUPPORTED]
    return {"statuses": [m.status.value for m in analysis.requirement_matches], "assessable": a.assessable_count,
            "supported": len(sup), "score": a.alignment_score,
            "claim_satisfied": bool(scored) and len(sup) == len(scored),
            "not_assessable": analysis.not_assessable_count}


def main() -> None:
    dump = {"parser_version": JOB_DESCRIPTION_PARSER_VERSION}
    g16 = json.loads((ROOT / "evaluation/m11g16/compound_logic_controls.json").read_text(encoding="utf-8"))["controls"]
    dump["g16"] = {}
    for c in g16:
        parsed = parse_job_description_with_diagnostics(c["text"])
        fx = c["expected"]["per_fixture"] or {"none": {"evidence": []}}
        dump["g16"][c["id"]] = {
            "rows": rows_of(parsed.profile, c["text"]),
            "unparsed": [{"text": u.text, "span": [u.source_span.start, u.source_span.end]}
                         for u in parsed.unparsed_claims],
            "fixtures": {n: outcome(parsed.profile, f["evidence"]) for n, f in fx.items()},
        }
    g15 = json.loads((ROOT / "evaluation/m11g15/or_scoring_controls.json").read_text(encoding="utf-8"))["controls"]
    dump["g15"] = {}
    for c in g15:
        parsed = parse_job_description_with_diagnostics(c["job_text"])
        dump["g15"][c["id"]] = {"rows": rows_of(parsed.profile),
                                "candidates": {k["name"]: outcome(parsed.profile, k["evidence"])
                                               for k in c["candidates"]}}
    names = list_candidate_names()
    dump["8c"] = {}
    profiles = {}
    for label, rel in (("8c:v1", "evaluation/gold/matrix.json"), ("8c:v1.1", "evaluation/gold_v1_1/matrix.json")):
        matrix = json.loads((ROOT / rel).read_text(encoding="utf-8"))
        need = {}
        for pair in matrix["pairs"]:
            if pair["candidate"] not in profiles:
                need[pair["candidate"]] = load_candidate_fixture(
                    next(n for n in names if n.lower() == pair["candidate"].lower()))
        profiles.update(end_to_end_eval.build_candidate_profiles(need))
        dump["8c"][label] = {}
        for pair in matrix["pairs"]:
            job = load_job(pair["job_id"])
            parsed = parse_job_description_with_diagnostics(job["raw_text"], title=job.get("title"))
            a = assess_job(match_job(profiles[pair["candidate"]], parsed.profile))
            dump["8c"][label][f"{pair['candidate']}/{pair['job_id']}"] = {
                "score": a.alignment_score, "assessable": a.assessable_count,
                "rows": len(parsed.profile.requirements), "unparsed": len(parsed.unparsed_claims)}
    dump["m10"] = {}
    for p in sorted((ROOT / "evaluation/m10/source").glob("*.txt")):
        text = p.read_bytes().decode("utf-8")
        parsed = parse_job_description_with_diagnostics(text)
        dump["m10"][p.stem] = {"rows": rows_of(parsed.profile), "unparsed": len(parsed.unparsed_claims)}
    if "--private" in sys.argv:
        import os
        private_root = Path(os.environ.get("M11G17_PRIVATE_ROOT", str(ROOT)))  # read-only; never copied
        dump["private"] = {}
        for name, rel in (("m11d", "evaluation/m11d/source"), ("m11f", "evaluation/m11f/source"),
                          ("m11g5", "evaluation/m11g5/source"), ("m11g9", "evaluation/m11g9/source")):
            src = private_root / rel
            if not src.is_dir():
                raise SystemExit(f"--private requested but {rel} is missing")
            dump["private"][name] = [
                {"rows": rows_of(parse_job_description_with_diagnostics(p.read_bytes().decode("utf-8")).profile),
                 "unparsed": len(parse_job_description_with_diagnostics(p.read_bytes().decode("utf-8")).unparsed_claims)}
                for p in sorted(src.rglob("*.txt"))]
    OUT.write_text(json.dumps(dump), encoding="utf-8")


if __name__ == "__main__":
    main()
