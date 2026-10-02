"""Milestone 7B -- SubscoreFacts and JobAssessment.

The result of deriving a GitHub Evidence Alignment score and its
required/preferred submetrics from an already-computed Milestone 7A
`JobMatchAnalysis`. Plain, frozen value objects -- no SQLAlchemy, no
persistence, mirroring every other domain-model package in this
codebase (matching/models.py, jobs/models.py, evidence/profile.py).

This module performs NO matching, NO parsing, and NO GitHub/API calls,
and introduces NO weighting of Necessity/Importance/ParserConfidence/
ConfidenceLevel into the score -- see
docs/design/MILESTONE_7B_SCORING_DESIGN.md (and docs/ARCHITECTURE.md's
Milestone 7B section) for the full rationale behind every decision
below. Every derived value on `JobAssessment` is a `@property` computed
directly from the retained `match_analysis`, never a separately stored
field that could drift out of sync with it -- the same "derive, never
duplicate" discipline `JobMatchAnalysis` itself already applies to its
own `supported_count`/`not_observed_count`/`not_assessable_count`. This
also makes several invariants true BY CONSTRUCTION rather than
something to separately re-validate: `alignment_score is None` can never
disagree with `assessable_count == 0` if one is always computed from the
other, every time it is read.
"""
from __future__ import annotations

from dataclasses import dataclass

from gitscore.jobs.types import Necessity, ParserConfidence
from gitscore.matching.models import JobMatchAnalysis, RequirementMatch
from gitscore.matching.types import MatchStatus


def _round_half_up_percentage(numerator: int, denominator: int) -> int:
    """Round `100 * numerator / denominator` to the nearest integer,
    ties rounding UP (conventional half-up), using exact integer
    arithmetic only -- never a float.

    Python's builtin `round()` uses round-half-to-even ("banker's
    rounding"): `round(62.5) == 62` but `round(63.5) == 64` -- the exact
    same distance from either neighbor rounds differently purely
    depending on whether the lower integer happens to be even. For a
    human-facing percentage there is no product reason "62.5% supported"
    should round differently from "63.5% supported" -- that parity-
    dependent flip would be a surprising, unexplainable implementation
    artifact in a report meant to be read literally. Conventional
    half-up rounding is used instead (`docs/design/
    MILESTONE_7B_SCORING_DESIGN.md` Part 14), implemented via pure
    integer arithmetic (`(2*numerator*100 + denominator) //
    (2*denominator)`, the integer identity for `floor(x + 0.5)`) rather
    than `round(numerator / denominator * 100)`, which would reintroduce
    float-precision risk for no benefit.

    Example: numerator=5, denominator=8 -> 500/8 = 62.5 -> rounds to 63
    (not `round()`'s 62). numerator=29, denominator=40 -> 2900/40 = 72.5
    -> rounds to 73 (not `round()`'s 72).

    `denominator` must be >= 1 -- the sole caller (`JobAssessment.
    alignment_score`) only invokes this once `assessable_count > 0` has
    already been established.
    """
    return (2 * 100 * numerator + denominator) // (2 * denominator)


def _assessable_matches(matches: tuple[RequirementMatch, ...]) -> tuple[RequirementMatch, ...]:
    """SUPPORTED + NOT_OBSERVED matches -- the requirements GitHub
    evidence could meaningfully speak to, regardless of necessity.
    Excludes NOT_ASSESSABLE (`docs/design/MILESTONE_7B_SCORING_DESIGN.md`
    Part 3). The ONE definition of "assessable" used everywhere in this
    module -- `assessable_count`, `low_parser_confidence_count`, and
    `_subscore_for` all filter through this same function rather than
    each re-deriving "status != NOT_ASSESSABLE" independently.
    """
    return tuple(m for m in matches if m.status != MatchStatus.NOT_ASSESSABLE)


def _subscore_for(
    matches: tuple[RequirementMatch, ...], necessity: Necessity
) -> SubscoreFacts | None:
    tier_assessable = [m for m in _assessable_matches(matches) if m.requirement.necessity == necessity]
    if not tier_assessable:
        return None
    supported = sum(1 for m in tier_assessable if m.status == MatchStatus.SUPPORTED)
    return SubscoreFacts(supported=supported, assessable=len(tier_assessable))


@dataclass(frozen=True)
class SubscoreFacts:
    """How many of one necessity tier's ASSESSABLE requirements
    (`SUPPORTED` or `NOT_OBSERVED` -- never `NOT_ASSESSABLE`) are
    `SUPPORTED`.

    Deliberately a plain "X of Y" count pair, not a percentage -- see
    `docs/design/MILESTONE_7B_SCORING_DESIGN.md` Part 4: a second
    derived ratio here would invite exactly the "which number is the
    real one" confusion that `JobAssessment.alignment_score` -- the ONLY
    percentage this milestone produces -- is meant to avoid.
    `required`/`preferred` subscores exist to CONTEXTUALIZE that single
    percentage (most importantly, to make the Part 12 adversarial case
    self-correcting the instant both numbers are read together), not to
    compute a second, competing one.

    `assessable` must be >= 1: a necessity tier with ZERO assessable
    requirements is represented by `None` on `JobAssessment.required`/
    `.preferred` (Edge Cases D/E), never by `SubscoreFacts(0, 0)` --
    `(0, 0)` would be indistinguishable from "this tier was assessed and
    genuinely nothing was supported," which is a different fact from
    "this tier was never assessable in the first place."
    """

    supported: int
    assessable: int

    def __post_init__(self) -> None:
        if self.assessable < 1:
            raise ValueError(
                f"SubscoreFacts.assessable must be >= 1, got {self.assessable!r} -- "
                "a necessity tier with zero assessable requirements must be represented "
                "by None on JobAssessment.required/.preferred, not SubscoreFacts(0, 0)"
            )
        if self.supported < 0:
            raise ValueError(f"SubscoreFacts.supported must be >= 0, got {self.supported!r}")
        if self.supported > self.assessable:
            raise ValueError(
                f"SubscoreFacts.supported ({self.supported}) cannot exceed "
                f"assessable ({self.assessable})"
            )


@dataclass(frozen=True)
class JobAssessment:
    """GitHub Evidence Alignment and its required/preferred submetrics,
    derived entirely from an already-computed Milestone 7A
    `JobMatchAnalysis` -- see `docs/design/MILESTONE_7B_SCORING_DESIGN.md`
    for the full product definition this class implements.

    `match_analysis` is retained BY REFERENCE (not copied, not
    re-matched) so every property below can be derived from it on
    demand -- `alignment_score`, `assessable_count`, `required`,
    `preferred`, and `low_parser_confidence_count` are all `@property`,
    never stored fields, mirroring the exact discipline
    `JobMatchAnalysis` itself already applies to `supported_count`/
    `not_observed_count`/`not_assessable_count`.

    Deliberately NO `coverage_note`/presentation string of any kind
    (Milestone 7B.0's own review correction): repository-coverage facts
    remain exactly `match_analysis.coverage`
    (`evidence.profile.RepositoryAnalysisCoverage`) -- not duplicated,
    not re-derived into a percentage, not paired with generated prose. A
    future UI/API layer renders "15 of 80 repositories... highest-ranked
    repositories prioritized" FROM those structured facts; this class
    does not pre-render it.

    Deliberately NO per-requirement `importance`/`parser_confidence`
    duplication either: both remain readable from each
    `RequirementMatch.requirement` via the grouping helpers below -- this
    class only adds the one NEW aggregate (`low_parser_confidence_count`)
    `JobMatchAnalysis` has no equivalent for.
    """

    match_analysis: JobMatchAnalysis
    scoring_version: str

    def __post_init__(self) -> None:
        if not self.scoring_version.strip():
            raise ValueError("JobAssessment.scoring_version must not be empty/whitespace-only")

    @property
    def assessable_count(self) -> int:
        """SUPPORTED + NOT_OBSERVED requirement count -- see
        `docs/design/MILESTONE_7B_SCORING_DESIGN.md` Part 3 for why
        NOT_ASSESSABLE is excluded from this denominator.
        """
        return len(_assessable_matches(self.match_analysis.requirement_matches))

    @property
    def alignment_score(self) -> int | None:
        """GitHub Evidence Alignment: among the assessable requirements,
        the percentage SUPPORTED, half-up rounded to the nearest integer
        (`_round_half_up_percentage`).

        `None` -- never `0` -- when `assessable_count == 0` (Edge Cases
        A/G): a job description with no GitHub-assessable requirements
        has no alignment to report, which is a materially different fact
        from "zero alignment observed."
        """
        assessable = self.assessable_count
        if assessable == 0:
            return None
        return _round_half_up_percentage(self.match_analysis.supported_count, assessable)

    @property
    def required(self) -> SubscoreFacts | None:
        """"X of Y REQUIRED requirements supported," among REQUIRED
        requirements that are assessable. `None` if no REQUIRED
        requirement is assessable (Edge Case D) -- never
        `SubscoreFacts(0, 0)` (see that class's docstring).

        Deliberately NOT combined with `alignment_score` into a weighted
        number -- `docs/design/MILESTONE_7B_SCORING_DESIGN.md` Parts
        4/12: this fact exists specifically so a reader can see "0 of 2
        required supported" standing next to a seemingly-strong headline
        score, rather than that fact being silently absorbed into one
        number via a cap, floor, or weight.
        """
        return _subscore_for(self.match_analysis.requirement_matches, Necessity.REQUIRED)

    @property
    def preferred(self) -> SubscoreFacts | None:
        """Same as `required`, for PREFERRED requirements (Edge Case E)."""
        return _subscore_for(self.match_analysis.requirement_matches, Necessity.PREFERRED)

    @property
    def low_parser_confidence_count(self) -> int:
        """Count of ASSESSABLE requirements (SUPPORTED or NOT_OBSERVED)
        whose `requirement.parser_confidence == ParserConfidence.LOW`.

        Informational metadata only -- NEVER affects `alignment_score`
        (`docs/design/MILESTONE_7B_SCORING_DESIGN.md` Part 6:
        `ParserConfidence` measures confidence in GitScore's own reading
        of the job text, not candidate evidence). Scoped to assessable
        requirements only: a NOT_ASSESSABLE requirement parsed with LOW
        confidence doesn't change anything about how GitHub evidence was
        read for it, so counting it here would mix "the parser was
        unsure how to read this sentence" with "this claim was never
        checkable against GitHub evidence in the first place" -- two
        unrelated facts (Edge Case J). `parser_confidence is None`
        ("not evaluated by any parser," `jobs.types.ParserConfidence`'s
        own documented meaning) does NOT count as LOW -- fabricating
        uncertainty where none was actually recorded would be worse than
        reporting none.
        """
        return sum(
            1
            for m in _assessable_matches(self.match_analysis.requirement_matches)
            if m.requirement.parser_confidence == ParserConfidence.LOW
        )

    def supported_matches(self) -> tuple[RequirementMatch, ...]:
        """SUPPORTED requirement matches, in `match_analysis`'s own
        order -- "Supported by GitHub evidence"
        (`docs/design/MILESTONE_7B_SCORING_DESIGN.md` §11).
        """
        return self.match_analysis.matches_with_status(MatchStatus.SUPPORTED)

    def not_observed_matches(self) -> tuple[RequirementMatch, ...]:
        """NOT_OBSERVED requirement matches -- "Not observed in analyzed
        GitHub evidence." NEVER rendered by any caller of this method as
        "the candidate lacks this skill."
        """
        return self.match_analysis.matches_with_status(MatchStatus.NOT_OBSERVED)

    def not_assessable_matches(self) -> tuple[RequirementMatch, ...]:
        """NOT_ASSESSABLE requirement matches -- "Not assessable from
        GitHub." NEVER rendered by any caller of this method as "the
        candidate failed this requirement."
        """
        return self.match_analysis.matches_with_status(MatchStatus.NOT_ASSESSABLE)
