"""Milestone 8C -- Layers C/D + end-to-end matrix: matcher and
assessment evaluation.

7A (`match_job`) and 7B (`assess_job`) already carry extensive dedicated
test suites (`tests/test_matching_*.py`, `tests/test_assessment_*.py`).
This module does not re-derive their correctness from scratch; it runs
the REAL, unmodified pipeline against THIS evaluation's own candidate
fixtures and job corpus, and:

1. Independently recomputes `alignment_score` from
   `match_analysis.supported_count`/`assessable_count` using the exact
   same half-up formula `assessment.models` uses, and compares against
   `JobAssessment.alignment_score` -- an ASSESSMENT_AGGREGATION_ERROR
   finding would mean the already-tested formula somehow disagrees with
   itself on real data, which existing unit tests do not cover (they use
   hand-built fixtures, never this corpus's real combinations).
2. Flags any `RequirementMatch.status == SUPPORTED` whose
   `matched_concept_ids` is NOT a subset of its requirement's own
   concept id(s) (a MATCHER_FALSE_POSITIVE/MATCHER_OR_ERROR signal) --
   also already guarded by `RequirementMatch.__post_init__`, so this is
   a redundant, defense-in-depth check specific to this corpus's data,
   not new matcher logic.
3. Records the qualitative candidate x job matrix (Milestone 8C Part 13)
   for the final report, WITHOUT computing or storing any numeric
   "true fit" ground truth (Part 14).
"""
from __future__ import annotations

from dataclasses import dataclass

from gitscore.assessment import assess_job
from gitscore.assessment.models import _round_half_up_percentage
from gitscore.jobs import parse_job_description
from gitscore.matching import match_job
from gitscore.matching.types import MatchStatus
from gitscore.pipeline.evidence import extract_candidate_evidence

from evaluation_lib.loaders import build_fake_client


@dataclass
class MatrixCell:
    candidate: str
    job_id: str
    expected_direction: str
    rationale: str
    alignment_score: int | None
    required: tuple[int, int] | None
    preferred: tuple[int, int] | None
    assessable_count: int
    supported_count: int
    not_observed_count: int
    not_assessable_count: int
    aggregation_matches: bool
    matcher_integrity_ok: bool


def _recompute_alignment(supported: int, assessable: int) -> int | None:
    if assessable == 0:
        return None
    return _round_half_up_percentage(supported, assessable)


def _matcher_integrity_ok(match_analysis) -> bool:
    for req_match in match_analysis.requirement_matches:
        if req_match.status != MatchStatus.SUPPORTED:
            continue
        requirement = req_match.requirement
        if requirement.is_alternative_group:
            allowed = set(requirement.alternative_concept_ids)
        elif requirement.concept_id is not None:
            allowed = {requirement.concept_id}
        else:
            allowed = set()
        if not set(req_match.matched_concept_ids) <= allowed:
            return False
    return True


def build_candidate_profiles(fixtures: dict[str, dict]) -> dict:
    profiles = {}
    for name, fixture in fixtures.items():
        client = build_fake_client(fixture)
        result = extract_candidate_evidence(name, client=client, top_n=fixture["top_n"])
        profiles[name] = result.profile
    return profiles


def evaluate_matrix(matrix: dict, candidate_profiles: dict, jobs: dict[str, dict]) -> list[MatrixCell]:
    cells = []
    for pair in matrix["pairs"]:
        candidate_name = pair["candidate"]
        job_id = pair["job_id"]
        profile = candidate_profiles[candidate_name]
        job = jobs[job_id]
        job_profile = parse_job_description(job["raw_text"], title=job.get("title"))

        match_analysis = match_job(profile, job_profile)
        assessment = assess_job(match_analysis)

        recomputed = _recompute_alignment(match_analysis.supported_count, assessment.assessable_count)
        cells.append(
            MatrixCell(
                candidate=candidate_name,
                job_id=job_id,
                expected_direction=pair["expected_direction"],
                rationale=pair["rationale"],
                alignment_score=assessment.alignment_score,
                required=(assessment.required.supported, assessment.required.assessable) if assessment.required else None,
                preferred=(assessment.preferred.supported, assessment.preferred.assessable) if assessment.preferred else None,
                assessable_count=assessment.assessable_count,
                supported_count=match_analysis.supported_count,
                not_observed_count=match_analysis.not_observed_count,
                not_assessable_count=match_analysis.not_assessable_count,
                aggregation_matches=(recomputed == assessment.alignment_score),
                matcher_integrity_ok=_matcher_integrity_ok(match_analysis),
            )
        )
    return cells


def aggregate_metrics(cells: list[MatrixCell]) -> dict:
    aggregation_errors = [c for c in cells if not c.aggregation_matches]
    matcher_errors = [c for c in cells if not c.matcher_integrity_ok]
    return {
        "pairs_evaluated": len(cells),
        "assessment_aggregation_errors": len(aggregation_errors),
        "matcher_integrity_errors": len(matcher_errors),
    }
