"""Milestone 11-G19 -- version-neutral scoring dump (scoring v1 or v2).

    python m11g19_scoring_dump.py <repo_root> <out.json> [--private]

Runs the REAL parser, matcher, assessor AND API serializer of whatever
checkout `repo_root` is (a throwaway clone of HEAD = scoring v1, or the
working tree = scoring v2) over fixed corpora and writes the outcomes.
Fields that only exist under v2 (`counts_toward_alignment`,
`alignment_exclusion_reason`, `excluded_from_alignment_count`) are read
with `getattr(..., None)` so the same script runs on both. Private
postings (only with --private) are dumped WITHOUT any text: per-posting
row counts by status / exclusion reason only.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts"), str(ROOT / "scripts" / "evaluation_lib")]

from evaluation_lib import end_to_end_eval  # noqa: E402
from evaluation_lib.loaders import list_candidate_names, load_candidate_fixture, load_job  # noqa: E402
from gitscore.api.serialization import serialize_job_analysis_result  # noqa: E402
from gitscore.application import JobAnalysisResult  # noqa: E402
from gitscore.assessment import SCORING_VERSION, assess_job  # noqa: E402
from gitscore.jobs.parsing.parser import JOB_DESCRIPTION_PARSER_VERSION, parse_job_description_with_diagnostics  # noqa: E402
from gitscore.matching import MATCHER_VERSION, match_job  # noqa: E402
from m11g15_or_scoring import candidate_profile  # noqa: E402


def _row(r) -> dict:
    return {"text_len": len(r.text), "status": r.status, "necessity": r.necessity,
            "members": sorted(r.alternative_concept_ids) or ([r.concept_id] if r.concept_id else []),
            "matched": list(r.matched_concept_ids), "evidence": len(r.evidence),
            "interpretation_status": r.interpretation_status,
            "counts": getattr(r, "counts_toward_alignment", None),
            "reason": getattr(r, "alignment_exclusion_reason", None)}


def outcome(profile, parsed) -> dict:
    assessment = assess_job(match_job(profile, parsed.profile))
    resp = serialize_job_analysis_result(JobAnalysisResult(
        candidate_profile=profile, job_profile=parsed.profile, assessment=assessment, extractor_failures=(),
        unknown_dependency_names=(), unparsed_claims=parsed.unparsed_claims))
    rows = [_row(r) for g in ("supported", "not_observed", "not_assessable") for r in getattr(resp.requirements, g)]
    return {"score": resp.assessment.github_evidence_alignment,
            "assessable": resp.assessment.assessable_requirement_count,
            "excluded": getattr(resp.assessment, "excluded_from_alignment_count", None),
            "required": None if resp.required is None else [resp.required.supported, resp.required.assessable],
            "preferred": None if resp.preferred is None else [resp.preferred.supported, resp.preferred.assessable],
            "n_supported": len(resp.requirements.supported), "n_not_observed": len(resp.requirements.not_observed),
            "n_not_assessable": len(resp.requirements.not_assessable),
            "scoring_version": resp.versions.scoring, "rows": rows}


def main() -> None:
    dump = {"parser_version": JOB_DESCRIPTION_PARSER_VERSION, "scoring_version": SCORING_VERSION,
            "matcher_version": MATCHER_VERSION}
    g18 = json.loads((ROOT / "evaluation/m11g18/eligibility_controls.json").read_text(encoding="utf-8"))["controls"]
    dump["g18"] = {f"{c['id']}/{k['name']}": outcome(candidate_profile(k["evidence"]),
                                                    parse_job_description_with_diagnostics(c["job_text"]))
                   for c in g18 for k in c["candidates"]}
    g15 = json.loads((ROOT / "evaluation/m11g15/or_scoring_controls.json").read_text(encoding="utf-8"))["controls"]
    dump["g15"] = {f"{c['id']}/{k['name']}": outcome(candidate_profile(k["evidence"]),
                                                    parse_job_description_with_diagnostics(c["job_text"]))
                   for c in g15 for k in c["candidates"]}
    g16 = json.loads((ROOT / "evaluation/m11g16/compound_logic_controls.json").read_text(encoding="utf-8"))["controls"]
    dump["g16"] = {f"{c['id']}/{fx}": outcome(candidate_profile(f["evidence"]),
                                              parse_job_description_with_diagnostics(c["text"]))
                   for c in g16 for fx, f in c["expected"]["per_fixture"].items()}
    names = list_candidate_names()
    profiles = {}
    dump["8c"] = {}
    for label, rel in (("8c:v1", "evaluation/gold/matrix.json"), ("8c:v1.1", "evaluation/gold_v1_1/matrix.json")):
        matrix = json.loads((ROOT / rel).read_text(encoding="utf-8"))
        need = {p["candidate"]: load_candidate_fixture(next(n for n in names if n.lower() == p["candidate"].lower()))
                for p in matrix["pairs"] if p["candidate"] not in profiles}
        profiles.update(end_to_end_eval.build_candidate_profiles(need))
        dump["8c"][label] = {}
        for pair in matrix["pairs"]:
            job = load_job(pair["job_id"])
            parsed = parse_job_description_with_diagnostics(job["raw_text"], title=job.get("title"))
            dump["8c"][label][f"{pair['candidate']}/{pair['job_id']}"] = outcome(profiles[pair["candidate"]], parsed)
    empty = candidate_profile([])
    dump["m10"] = {p.stem: outcome(empty, parse_job_description_with_diagnostics(p.read_bytes().decode("utf-8")))
                   for p in sorted((ROOT / "evaluation/m10/source").glob("*.txt"))}
    if "--private" in sys.argv:
        private_root = Path(os.environ.get("M11G19_PRIVATE_ROOT", str(ROOT)))  # read-only; never copied
        dump["private"] = {}
        for name, rel in (("m11d", "evaluation/m11d/source"), ("m11f", "evaluation/m11f/source"),
                          ("m11g5", "evaluation/m11g5/source"), ("m11g9", "evaluation/m11g9/source")):
            src = private_root / rel
            if not src.is_dir():
                raise SystemExit(f"--private requested but {rel} is missing")
            posts = []
            for p in sorted(src.rglob("*.txt")):
                o = outcome(empty, parse_job_description_with_diagnostics(p.read_bytes().decode("utf-8")))
                posts.append({"assessable": o["assessable"], "excluded": o["excluded"],
                              "statuses": [r["status"] for r in o["rows"]],
                              "reasons": [r["reason"] for r in o["rows"]],
                              "technical": [bool(r["members"]) for r in o["rows"]]})
            dump["private"][name] = posts
    OUT.write_text(json.dumps(dump), encoding="utf-8")


if __name__ == "__main__":
    main()
