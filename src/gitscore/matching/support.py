"""Milestone 7A -- the evidence-sufficiency policy.

Centralizes exactly ONE question, asked nowhere else: given a candidate's
`CandidateConceptSummary` for some concept, is there ENOUGH evidence to
call the requirement `SUPPORTED`? A single named, testable policy
constant instead of an ad hoc "if summary is not None" check scattered
through the matcher -- so a future milestone can tighten it (or a test
can pin it) without touching matching logic itself.

Decision: `MINIMUM_SUPPORTING_CONFIDENCE = ConfidenceLevel.WEAK` -- i.e.
the presence of ANY qualifying Evidence for a concept (any confidence
tier at all) is sufficient. This was a deliberate choice, not an
assumption that "any Evidence exists" automatically means supported:

1. `ConfidenceLevel` (evidence/types.py) answers "how sure are we this
   OBSERVATION is real," never candidate skill depth or proficiency --
   its own docstring warns against conflating it with either. Using it
   as a skill-depth gate here would repeat exactly the mistake that
   docstring calls out.
2. Every extractor already applies its OWN significance filter before
   producing Evidence at all -- e.g. `evidence/extraction/languages.py`
   only emits Evidence (WEAK or above) for a language at >= 5% of a
   repository's bytes; below that, no Evidence is created, full stop.
   A WEAK-confidence Evidence item is therefore not "maybe not real" --
   it is "genuinely present, just not this repository's dominant
   signal." Requiring MODERATE+ here would silently apply a SECOND,
   undocumented significance bar on top of each extractor's own,
   discarding real, already-filtered evidence for no principled reason.
3. `MatchStatus` (matching/types.py) deliberately has no
   `PARTIALLY_SUPPORTED` state. Treating WEAK evidence as insufficient
   would force it into `NOT_OBSERVED` -- misrepresenting "observed, but
   only weakly" as "not observed at all," the exact conflation Part 7 of
   this milestone's instructions warn against.

Kept as one named constant specifically so it CAN change later (e.g. if
real-world validation shows WEAK-only language evidence alone produces
too many false-positive matches) without redesigning
`matching.engine.match_requirement`.
"""
from __future__ import annotations

from gitscore.evidence.summary import CandidateConceptSummary
from gitscore.evidence.types import ConfidenceLevel

MINIMUM_SUPPORTING_CONFIDENCE = ConfidenceLevel.WEAK


def has_sufficient_evidence(summary: CandidateConceptSummary | None) -> bool:
    """True if `summary` carries enough evidence to call its concept
    SUPPORTED, per `MINIMUM_SUPPORTING_CONFIDENCE`.

    `None` (no CandidateConceptSummary at all for this concept --
    `CandidateEvidenceProfile.concept()`'s own "absence of evidence means
    absent key, never a zero-evidence summary object" contract) is
    always insufficient.
    """
    if summary is None:
        return False
    return summary.strongest_confidence >= MINIMUM_SUPPORTING_CONFIDENCE
