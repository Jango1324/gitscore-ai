"""Milestone 7A -- the deterministic requirement-matching engine.

    CandidateEvidenceProfile (gitscore.evidence)
            +
    JobRequirementProfile (gitscore.jobs)
            |
            v
    match_job()  ->  JobMatchAnalysis
            |
    one RequirementMatch per JobRequirement

This is the FIRST package that consumes both the candidate-evidence
domain model (Milestone 5C/5D) and the job-requirement domain model
(Milestone 6A/6B/6B.1) together. It answers, per requirement: "what does
this candidate's analyzed GitHub evidence say about this specific job
requirement" -- nothing more.

Explicitly OUT of scope here (deferred to Milestone 7B and later, see
docs/ARCHITECTURE.md's Milestone 7A section):
- an overall 0-100 job-fit score, or any weighted aggregation
- final strengths/gaps lists or hire/reject prose
- alternative-role discovery, role archetypes
- persistence, API, UI, CatBoost, LLM, job-posting URL ingestion

Two facts this package's status semantics protect, repeated because
getting them backwards is the single most damaging mistake this product
could make:

- `MatchStatus.NOT_OBSERVED` != "the candidate lacks this skill." It
  means "no sufficient evidence for this concept was found in the
  GitHub evidence GitScore actually analyzed" -- see
  `JobMatchAnalysis.coverage` for the structured fact about how much of
  the candidate's account that even was.
- `MatchStatus.NOT_ASSESSABLE` != "the candidate failed this
  requirement." It means "this claim is not the kind of thing GitHub
  evidence can meaningfully speak to" (years of professional experience,
  a degree, work authorization, generic soft skills, or a job-posting
  claim GitHub could only ever PARTIALLY speak to and for which no
  concrete technical concept was extracted at all).

See `matching.types.MatchStatus` for the full three-state enum (and why
there is no `PARTIALLY_SUPPORTED`), `matching.engine` for the exact
per-requirement decision rules (including the `PARTIALLY_OBSERVABLE`
table), and `matching.support` for the evidence-sufficiency policy.
"""
from gitscore.matching.engine import match_job, match_requirement
from gitscore.matching.models import JobMatchAnalysis, RequirementMatch
from gitscore.matching.support import MINIMUM_SUPPORTING_CONFIDENCE, has_sufficient_evidence
from gitscore.matching.types import MATCHER_VERSION, MatchStatus

__all__ = [
    "MATCHER_VERSION",
    "MINIMUM_SUPPORTING_CONFIDENCE",
    "JobMatchAnalysis",
    "MatchStatus",
    "RequirementMatch",
    "has_sufficient_evidence",
    "match_job",
    "match_requirement",
]
