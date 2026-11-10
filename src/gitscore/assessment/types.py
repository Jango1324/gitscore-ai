"""Milestone 7B -- the assessment package's own version constant.

`SCORING_VERSION` identifies the DECISION LOGIC in this package (the
GitHub Evidence Alignment formula, the half-up rounding policy, which
necessity tiers produce a `SubscoreFacts`, what counts toward
`low_parser_confidence_count`) -- independent of `MATCHER_VERSION`
(matching/types.py, which per-requirement SUPPORTED/NOT_OBSERVED/
NOT_ASSESSABLE statuses Milestone 7A's matcher assigns),
`JOB_REQUIREMENT_SCHEMA_VERSION` (jobs/types.py, the shape of a
`JobRequirement`), `EVIDENCE_SCHEMA_VERSION` (evidence/types.py, the
shape of `Evidence`/`CandidateEvidenceProfile`), and
`JOB_DESCRIPTION_PARSER_VERSION` (jobs/parsing/parser.py, how raw text
becomes a `JobRequirementProfile`).

Milestone 7B changes none of those four: `assessment.engine.assess_job()`
consumes a `JobMatchAnalysis` exactly as Milestone 7A produces it, with
no new field required on `JobRequirement`, `CandidateEvidenceProfile`,
`RequirementMatch`, or `JobMatchAnalysis` to compute anything in this
package. Bump `SCORING_VERSION` when THIS package's scoring rules change
(the formula itself, the rounding policy, which statuses are excluded
from the denominator, which facts contribute to
`low_parser_confidence_count`) -- not when an unrelated schema changes.
"""
from __future__ import annotations

from enum import Enum

# v1 -> v2 (Milestone 11-G19): a requirement enters the numerator and
# denominator only if the matcher evaluated it AND every acceptable
# alternative has a declared GitHub evidence-assessment capability
# (`gitscore.evidence.capability`). Same formula and rounding; a smaller,
# candidate-independent eligible set. v1 results stay valid as v1 results.
SCORING_VERSION = "github_evidence_alignment:v2"


class AlignmentExclusionReason(str, Enum):
    """Why a requirement does NOT count toward the alignment score (v2).

    A stable, closed set -- serialized verbatim as
    `RequirementOut.alignment_exclusion_reason`; never free text, never
    model-generated. "Alternative" variants mean at least one acceptable
    alternative IS GitHub-assessable (a mixed OR group); "technology"
    variants mean none is. "Unresolved" means GitScore cannot determine
    whether evidence could exist (the conservative case);
    "without_evidence_pathway" means it is known that no extractor covers
    the concept.
    """

    NOT_ASSESSABLE = "not_assessable"
    UNRESOLVED_TECHNOLOGY = "unresolved_technology"
    UNRESOLVED_ALTERNATIVE = "unresolved_alternative"
    TECHNOLOGY_WITHOUT_EVIDENCE_PATHWAY = "technology_without_evidence_pathway"
    ALTERNATIVE_WITHOUT_EVIDENCE_PATHWAY = "alternative_without_evidence_pathway"
