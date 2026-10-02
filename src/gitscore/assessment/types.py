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

SCORING_VERSION = "github_evidence_alignment:v1"
