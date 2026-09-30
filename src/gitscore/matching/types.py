"""Milestone 7A -- MatchStatus and the matcher's own version constant.

Not to be confused with `gitscore.concepts.matching` (Milestone 6B's
shared alias-boundary-regex primitive, `alias_pattern()`) -- that module
answers "does this alias appear in this free-form text"; this package
answers "does this candidate's GitHub evidence support this job
requirement." Unrelated layers that happen to share the word
"matching."

MATCHER_VERSION identifies the DECISION LOGIC in this package (which
statuses exist, what counts as sufficient evidence, how alternative
groups are resolved) -- independent of `JOB_REQUIREMENT_SCHEMA_VERSION`
(jobs/types.py, the shape of a JobRequirement), `EVIDENCE_SCHEMA_VERSION`
(evidence/types.py, the shape of Evidence/CandidateEvidenceProfile), and
`JOB_DESCRIPTION_PARSER_VERSION` (jobs/parsing/parser.py, how raw text
becomes a JobRequirementProfile). Bump it when this package's matching
RULES change in a way that could change a RequirementMatch's `status`
for the same two input profiles -- not when an unrelated schema changes.
"""
from __future__ import annotations

from enum import Enum

MATCHER_VERSION = "requirement_matcher:v1"


class MatchStatus(str, Enum):
    """The outcome of comparing ONE JobRequirement against a candidate's
    GitHub evidence.

    Three states, deliberately -- not the four/five-state drafts earlier
    design notes (docs/design/MILESTONE_5A_JOB_MATCHING_DESIGN.md Part
    16) once sketched:

    - `SUPPORTED`: the requirement names at least one technical concept
      (a single `concept_id`, or -- Milestone 6B.1 -- at least one entry
      in `alternative_concept_ids`) for which the candidate's
      `CandidateEvidenceProfile` has sufficient Evidence (see
      `matching.support.has_sufficient_evidence`).
    - `NOT_OBSERVED`: the requirement IS GitHub-observable and IS
      technical, but no sufficient evidence was found for it (or, for an
      alternative group, for ANY of its alternatives) in the analyzed
      evidence. This is a statement about the ANALYZED repositories, not
      about the candidate's real-world ability -- see
      `JobMatchAnalysis.coverage` / `RepositoryAnalysisCoverage` for the
      structured fact about how much of the candidate's account was even
      looked at. NEVER rendered (by a future 7B/UI layer) as "the
      candidate cannot do X" -- only as "not observed in the analyzed
      GitHub evidence."
    - `NOT_ASSESSABLE`: the requirement is not the kind of claim GitHub
      evidence can meaningfully speak to at all -- either
      `github_observability == NOT_OBSERVABLE` (years of professional
      experience, a degree, work authorization, generic soft skills), or
      the requirement has no technical-concept mapping whatsoever
      (`concept_id is None` and `alternative_concept_ids == ()` --
      Milestone 6A Part 6's non-technical requirements, and the
      Milestone 6B.1 "unsafe" alternative-group fallback,
      `category="alternative_requirement"`) so there is no structured
      evidence surface to check it against even when the job posting
      marks it `PARTIALLY_OBSERVABLE` (e.g. "leadership"). See
      `matching.engine.match_requirement`'s docstring for the exact
      decision table, and this package's `__init__` docstring / the
      Milestone 7A changelog entry for why `PARTIALLY_OBSERVABLE` is NOT
      simply treated as `STRONGLY_OBSERVABLE`. NEVER rendered as "the
      candidate failed this requirement."

    No `PARTIALLY_SUPPORTED`: considered and explicitly rejected for
    this milestone. The only ordinal signal the candidate-evidence model
    currently offers is `ConfidenceLevel` (WEAK/MODERATE/STRONG),
    documented (evidence/types.py) as confidence in the EVIDENCE CLAIM
    ITSELF ("how sure are we this observation is real"), never as
    candidate proficiency/skill depth or as a measure of "how much of
    this requirement" is satisfied -- there is no principled,
    deterministic way to read a fractional-support meaning out of it.
    For an alternative group, "some but not all alternatives supported"
    is not partial support either -- Milestone 6B.1's OR semantics mean
    ANY one supported alternative already fully satisfies the logical
    requirement (`RequirementMatch.matched_concept_ids` preserves WHICH
    alternatives matched for explanation purposes, but the `status` is
    still a plain `SUPPORTED`). If a future milestone introduces a real,
    deterministic partial-support signal (e.g. a distinct evidence tier
    that means "declared but never actually used"), this enum is the
    place to add it -- not before that signal exists.
    """

    SUPPORTED = "supported"
    NOT_OBSERVED = "not_observed"
    NOT_ASSESSABLE = "not_assessable"
