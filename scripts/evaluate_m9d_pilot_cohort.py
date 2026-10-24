"""Milestone 9D -- Phase 1/2 pilot cohort runner.

Evaluation-only. Reads only `evaluation/fixtures/` (offline, no GitHub
calls) and the existing `evaluation/jobs/` corpus. Calls the REAL,
unmodified production pipeline (`extract_candidate_evidence`,
`parse_job_description`, `match_job`, `assess_job`) -- the exact same
composition `gitscore.application.job_fit.analyze_job_fit()` uses for
job-independent retrieval. Does not modify any existing evaluation
script, fixture, or frozen gold file. Not wired into any other harness.

Six of the eight pairs below are already in `evaluation/gold/matrix.json`
(re-run here, not re-annotated); two (devops_cloud_01, sre_platform_01)
are new pairs added for Milestone 9D's own pilot-cohort scenario
coverage (DevOps/platform role; job with substantial non-GitHub-
assessable requirements) and are NOT added to the frozen matrix file.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from gitscore.assessment import assess_job
from gitscore.jobs.parsing.parser import parse_job_description_with_diagnostics
from gitscore.matching import match_job
from gitscore.pipeline.evidence import extract_candidate_evidence

from evaluation_lib.loaders import build_fake_client, load_candidate_fixture, load_job

PAIRS = [
    ("torvalds", "systems_cpp_01", "strong_observable_alignment"),
    ("torvalds", "data_science_01", "weak_observable_alignment"),
    ("Jango1324", "embedded_firmware_01", "embedded_firmware_role"),
    ("karpathy", "computer_vision_01", "ml_computer_vision_role"),
    ("sindresorhus", "frontend_01", "frontend_mobile_role"),
    ("sindresorhus", "devops_cloud_01", "devops_platform_role__NEW_PAIR"),
    ("Jango1324", "general_swe_01", "limited_github_evidence"),
    ("torvalds", "sre_platform_01", "substantial_non_assessable_requirements__NEW_PAIR"),
]


def run_pair(candidate_name: str, job_id: str):
    fixture = load_candidate_fixture(candidate_name)
    client = build_fake_client(fixture)
    evidence_result = extract_candidate_evidence(candidate_name, client=client, top_n=fixture["top_n"])
    profile = evidence_result.profile

    job = load_job(job_id)
    parsed = parse_job_description_with_diagnostics(job["raw_text"], title=job.get("title"))
    job_profile = parsed.profile

    match_analysis = match_job(profile, job_profile)
    assessment = assess_job(match_analysis)

    per_requirement = []
    for rm in match_analysis.requirement_matches:
        req = rm.requirement
        evidence_detail = [
            {
                "repo": ev.repository.name,
                "evidence_type": ev.evidence_type.value,
                "concept_id": ev.concept_id,
                "confidence": ev.confidence.value,
                "raw_observation": ev.raw_observation,
                "file_path": ev.file_path,
            }
            for ev in rm.supporting_evidence
        ]
        per_requirement.append({
            "text": req.original_text,
            "necessity": req.necessity.value,
            "category": req.category,
            "concept_id": req.concept_id,
            "alternative_concept_ids": list(req.alternative_concept_ids) if req.alternative_concept_ids else None,
            "status": rm.status.value,
            "matched_concept_ids": list(rm.matched_concept_ids),
            "supporting_evidence": evidence_detail,
        })

    unparsed_claims = [{"text": c.text} for c in parsed.unparsed_claims]

    return {
        "candidate": candidate_name,
        "job_id": job_id,
        "job_title": job.get("title"),
        "discovered_count": profile.coverage.discovered_count,
        "analyzed_count": profile.coverage.analyzed_count,
        "is_complete": profile.coverage.is_complete,
        "alignment_score": assessment.alignment_score,
        "required": [assessment.required.supported, assessment.required.assessable] if assessment.required else None,
        "preferred": [assessment.preferred.supported, assessment.preferred.assessable] if assessment.preferred else None,
        "assessable_count": assessment.assessable_count,
        "supported_count": match_analysis.supported_count,
        "not_observed_count": match_analysis.not_observed_count,
        "not_assessable_count": match_analysis.not_assessable_count,
        "low_parser_confidence_count": assessment.low_parser_confidence_count,
        "requirements": per_requirement,
        "unparsed_claims": unparsed_claims,
    }


def main() -> int:
    results = []
    for candidate_name, job_id, scenario in PAIRS:
        cell = run_pair(candidate_name, job_id)
        cell["scenario"] = scenario
        results.append(cell)

    out_path = REPO_ROOT / "evaluation" / "reports" / "m9d_pilot_cohort_report.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    for cell in results:
        print(f"\n=== {cell['scenario']}: {cell['candidate']} x {cell['job_id']} ===")
        print(f"  title: {cell['job_title']}")
        print(f"  coverage: analyzed={cell['analyzed_count']}/{cell['discovered_count']} complete={cell['is_complete']}")
        print(f"  alignment_score={cell['alignment_score']} required={cell['required']} preferred={cell['preferred']}")
        print(f"  supported={cell['supported_count']} not_observed={cell['not_observed_count']} not_assessable={cell['not_assessable_count']} low_conf={cell['low_parser_confidence_count']}")
        for r in cell["requirements"]:
            concept = r["concept_id"] or r["alternative_concept_ids"] or f"category={r['category']}"
            print(f"    [{r['status']:>13}] ({r['necessity']}) {concept} :: {r['text'][:80]}")
            for ev in r["supporting_evidence"]:
                print(f"        <- {ev['repo']} ({ev['evidence_type']}, {ev['confidence']}): {ev['raw_observation'][:70]!r}")
        if cell["unparsed_claims"]:
            print("  UNPARSED CLAIMS (zero JobRequirement rows produced):")
            for c in cell["unparsed_claims"]:
                print(f"    - {c['text']!r}")

    print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
