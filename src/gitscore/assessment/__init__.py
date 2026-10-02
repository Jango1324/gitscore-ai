"""Milestone 7B -- GitHub Evidence Alignment and structured assessment.

    JobMatchAnalysis (gitscore.matching, Milestone 7A)
            |
            v
      assess_job()  ->  JobAssessment
            |
    alignment_score, required/preferred SubscoreFacts,
    low_parser_confidence_count, supported/not_observed/not_assessable
    grouping helpers

This is the FIRST package to turn Milestone 7A's per-requirement
SUPPORTED/NOT_OBSERVED/NOT_ASSESSABLE verdicts into a single
human-facing number -- "GitHub Evidence Alignment": among the job
requirements GitHub evidence can meaningfully speak to, what percentage
are supported by evidence found in the candidate's analyzed GitHub
material. See `docs/design/MILESTONE_7B_SCORING_DESIGN.md` for the full
design rationale this package implements, and `docs/ARCHITECTURE.md`'s
Milestone 7B section for the as-built summary.

Explicitly OUT of scope here (deferred to later milestones):
- alternative-role discovery, role archetypes
- a learned/CatBoost scoring model
- recruiter labels, hire/reject recommendations
- persistence, API, UI
- LLM-generated explanation prose
- job-posting URL ingestion

What this package deliberately does NOT do to the score, each a
considered decision (see the design doc for the full "why" of each):
- does NOT weight by `Necessity` (REQUIRED/PREFERRED) -- exposed as
  separate `required`/`preferred` `SubscoreFacts` instead.
- does NOT weight by `Importance` -- remains readable per-requirement
  off `RequirementMatch.requirement`, never folded into the score.
- does NOT weight by `ParserConfidence` -- surfaced only as
  `low_parser_confidence_count`, informational metadata.
- does NOT weight by evidence `ConfidenceLevel` -- a SUPPORTED
  requirement counts as exactly one supported assessable requirement,
  regardless of WEAK/MODERATE/STRONG.
- does NOT compute a numeric repository-coverage percentage --
  `JobAssessment.match_analysis.coverage` remains the
  `RepositoryAnalysisCoverage` structured facts, unmodified.
- does NOT cap or floor the score when required requirements are
  unsupported -- the adversarial case (headline alignment looks strong
  despite 0 supported REQUIRED requirements) is resolved by making
  `required`/`preferred` `SubscoreFacts` mandatory co-display facts,
  never by silently discounting the headline number.
"""
from gitscore.assessment.engine import assess_job
from gitscore.assessment.models import JobAssessment, SubscoreFacts
from gitscore.assessment.types import SCORING_VERSION

__all__ = [
    "SCORING_VERSION",
    "JobAssessment",
    "SubscoreFacts",
    "assess_job",
]
