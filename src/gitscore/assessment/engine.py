"""Milestone 7B -- the pure GitHub Evidence Alignment assessment entry point.

    JobMatchAnalysis (gitscore.matching, Milestone 7A)
            |
            v
      assess_job()  ->  JobAssessment

Pure and deterministic with respect to its one input: no GitHub API
calls, no network calls, no LLM, no database reads/writes, and no
re-matching (`match_job()`/`match_requirement()` are never called from
here -- every fact this package needs already lives on the
`JobMatchAnalysis` it's handed). Same `JobMatchAnalysis` in -> the same
`JobAssessment` out, every time.

See `assessment.models.JobAssessment` for what is actually computed
(`alignment_score`, `required`/`preferred` `SubscoreFacts`,
`low_parser_confidence_count`, and the supported/not_observed/
not_assessable grouping helpers) and
`docs/design/MILESTONE_7B_SCORING_DESIGN.md` for the full product
rationale behind each of those.
"""
from __future__ import annotations

from gitscore.assessment.models import JobAssessment
from gitscore.assessment.types import SCORING_VERSION
from gitscore.matching.models import JobMatchAnalysis


def assess_job(match_analysis: JobMatchAnalysis) -> JobAssessment:
    """Derive a `JobAssessment` from an already-computed `JobMatchAnalysis`.

    Every value `JobAssessment` exposes is a `@property` computed from
    `match_analysis` on access (see that class's docstring) -- this
    function's only job is to pair the analysis with the current
    `SCORING_VERSION` stamp, mirroring how `matching.engine.match_job()`
    stamps `MATCHER_VERSION` onto the `JobMatchAnalysis` it builds.
    """
    return JobAssessment(match_analysis=match_analysis, scoring_version=SCORING_VERSION)
