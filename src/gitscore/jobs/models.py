"""Milestone 6A -- SourceSpan and JobRequirement: the job-side counterpart
to evidence/models.py's RepositoryIdentity and Evidence.

Domain model only -- no parser, no matcher, no scoring. See
docs/design/MILESTONE_5A_JOB_MATCHING_DESIGN.md Part 9 for the original
proposal this generalizes/narrows, and this package's module docstrings
for exactly where the final design deviates from that draft and why.
"""
from __future__ import annotations

from dataclasses import dataclass

from gitscore.concepts.registry import is_unresolved_concept_id, is_valid_concept_id
from gitscore.jobs.types import GithubObservability, Importance, Necessity, ParserConfidence


@dataclass(frozen=True)
class SourceSpan:
    """A character offset range into a JobRequirementProfile's `raw_text`.

    Deliberately just two ints -- Milestone 6A Part 8 explicitly warns
    against over-engineering source-document handling ("We are NOT
    implementing automatic span extraction yet"). `start`/`end` are
    validated for basic well-formedness here (non-negative, `end >
    start`); validating that a span actually falls WITHIN a particular
    document's bounds requires knowing that document's length, so that
    check lives on `JobRequirementProfile` instead (jobs/profile.py),
    not here.
    """

    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0:
            raise ValueError(f"SourceSpan.start must be >= 0, got {self.start}")
        if self.end <= self.start:
            raise ValueError(
                f"SourceSpan.end ({self.end}) must be greater than start ({self.start})"
            )


@dataclass(frozen=True)
class JobRequirement:
    """One distinct claim extracted from a job posting.

    Frozen and fully hashable (every field is itself hashable), mirroring
    `evidence.models.Evidence` -- a pool of JobRequirement can be
    compared/deduplicated structurally with a plain `set()` (see
    `jobs.profile.JobRequirementProfile`'s duplicate-rejection policy,
    which is intentionally the OPPOSITE of Evidence's silent-dedup
    policy -- see that module for why).

    ONE JobRequirement is ONE indivisible claim. This is the direct
    answer to Milestone 6A Part 1's warning example: "3+ years of
    experience building Python backend services" must never become a
    single JobRequirement with `concept_id="language.python"` --that
    would silently assert Python experience-years are GitHub-observable,
    which they are not. A future parser must instead emit TWO
    JobRequirement objects from that one sentence: one with
    `concept_id="language.python"` /
    `github_observability=STRONGLY_OBSERVABLE`, and one with
    `concept_id=None` (Part 6 -- a non-technical, non-concept
    requirement) / `github_observability=NOT_OBSERVABLE` describing the
    professional-experience claim. Both may legitimately share the same
    `original_text`/`source_span` (Milestone 6A tests demonstrate this
    split manually; no automatic splitting is implemented here).

    `concept_id` is `None` for a requirement that does not map to any
    technical concept at all (Part 6 -- "Bachelor's degree", "excellent
    communication", "eligible to work in Canada", "3+ years of
    professional experience"). When it IS a technical requirement,
    `concept_id` is either a real `TechnicalConcept.concept_id` (e.g.
    `"database.postgresql"`) or a deterministic
    `"unresolved:<term>"` id from
    `gitscore.concepts.registry.unresolved_concept_id()` -- the SAME
    unresolved-concept policy `evidence.models.Evidence` already uses
    (Milestone 5C Part 3), reused here rather than inventing a parallel
    "provisional:<slug>" scheme the way the 5A draft proposed: an
    arbitrary technology named in a job posting that isn't yet in the
    concept registry must be preserved, never discarded, and never
    silently promoted into a new canonical concept at runtime -- exactly
    the guarantee `unresolved:<term>` already provides.

    Milestone 6A.1: a non-`None` `concept_id` is exactly one of those two
    shapes -- never an arbitrary string. `__post_init__` enforces this
    with `concepts.registry.is_valid_concept_id()`, the SAME helper the
    candidate/evidence side would use (there is no second, job-specific
    concept-id validation rule anywhere in this package). This is
    VALIDATION of an already-produced id, not RESOLUTION: JobRequirement
    still never calls `resolve_concept()` itself, never turns a raw human
    term like `"Postgres"` into a concept id on its own, and never
    mutates the registry -- it only checks that whatever id a caller
    already produced is one of the two legitimate shapes.

    Milestone 6B.1 -- `alternative_concept_ids`: a THIRD state, for a
    single logical requirement satisfied by ANY ONE of several technical
    concepts ("Python or Go", "PostgreSQL, MySQL, or MongoDB"). Mutually
    exclusive with `concept_id` (exactly one of the two may be
    populated -- never both, never neither for a technical requirement).
    Each element is validated the SAME way a lone `concept_id` is
    (`is_valid_concept_id()` -- no second validation rule), must number
    at least two (a one-element "alternative" is meaningless -- use
    `concept_id` instead), and must contain no duplicates.
    `__post_init__` stores the tuple SORTED, not in whatever order the
    caller passed -- "Python or Go" and "Go or Python" are the same
    logical requirement (order is a fact about the SENTENCE, not about
    the set of options it describes), so canonicalizing the stored order
    makes them compare and hash equal automatically, without a custom
    `__eq__`/`__hash__` override. This is what lets
    `jobs/parsing/dedup.py` and `JobRequirementProfile`'s own
    exact-duplicate rejection (Milestone 6A) treat the two phrasings as
    identical for free.

    No `requirement_id`: like `Evidence`, this is a pure value object at
    this stage -- no persistence layer exists yet to need a synthetic
    identifier (Milestone 6A does not touch persistence).
    """

    original_text: str
    necessity: Necessity
    importance: Importance
    github_observability: GithubObservability
    concept_id: str | None = None
    alternative_concept_ids: tuple[str, ...] = ()
    category: str | None = None
    parser_confidence: ParserConfidence | None = None
    source_span: SourceSpan | None = None

    def __post_init__(self) -> None:
        if not self.original_text.strip():
            raise ValueError("JobRequirement.original_text must not be empty/whitespace-only")
        if self.concept_id is not None and not is_valid_concept_id(self.concept_id):
            raise ValueError(
                f"JobRequirement.concept_id {self.concept_id!r} is neither a registered "
                "TechnicalConcept id nor a valid 'unresolved:<term>' id -- pass None for a "
                "non-technical requirement instead (see Part 6), or resolve the raw term "
                "through concepts.registry.resolve_concept() first"
            )
        if self.category is not None and not self.category.strip():
            raise ValueError("JobRequirement.category must not be an empty/whitespace-only string")

        if self.alternative_concept_ids:
            if self.concept_id is not None:
                raise ValueError(
                    "JobRequirement cannot set both concept_id and alternative_concept_ids -- "
                    "a requirement is either ONE resolved concept or an alternative GROUP, never both"
                )
            if len(self.alternative_concept_ids) < 2:
                raise ValueError(
                    "JobRequirement.alternative_concept_ids must contain at least 2 entries -- "
                    "a single alternative is not a group; use concept_id instead"
                )
            if len(set(self.alternative_concept_ids)) != len(self.alternative_concept_ids):
                raise ValueError(
                    f"JobRequirement.alternative_concept_ids contains a duplicate: "
                    f"{self.alternative_concept_ids!r}"
                )
            for alt_id in self.alternative_concept_ids:
                if not is_valid_concept_id(alt_id):
                    raise ValueError(
                        f"JobRequirement.alternative_concept_ids entry {alt_id!r} is neither a "
                        "registered TechnicalConcept id nor a valid 'unresolved:<term>' id"
                    )
            # Canonical order: the SET of alternatives is the logical
            # requirement, not the order they were listed in the sentence.
            object.__setattr__(self, "alternative_concept_ids", tuple(sorted(self.alternative_concept_ids)))

    @property
    def is_technical(self) -> bool:
        """False for a requirement with no technical-concept mapping at
        all (Part 6 -- e.g. "3+ years professional experience").

        True for either a single resolved `concept_id` OR an
        `alternative_concept_ids` group (Milestone 6B.1) -- both are
        "this requirement is about a technology," just with a different
        cardinality of acceptable answers.
        """
        return self.concept_id is not None or bool(self.alternative_concept_ids)

    @property
    def is_alternative_group(self) -> bool:
        """True for a single logical requirement satisfied by ANY ONE of
        several technical concepts (Milestone 6B.1 Part 14) -- e.g.
        "Python or Go". Mutually exclusive with a populated `concept_id`.
        """
        return bool(self.alternative_concept_ids)

    @property
    def is_resolved_concept(self) -> bool:
        """True only for a SINGLE-concept technical requirement whose
        `concept_id` is a REAL registry concept, not an
        "unresolved:<term>" placeholder, not a non-technical
        (`concept_id=None`) requirement, and not an alternative group
        (see `is_alternative_group` / `has_unresolved_alternative` for
        that third case instead).

        Mirrors `Evidence.is_resolved`, split into two properties instead
        of one because JobRequirement has a third state (non-technical)
        Evidence never needs to represent.
        """
        return self.concept_id is not None and not is_unresolved_concept_id(self.concept_id)

    @property
    def is_unresolved_concept(self) -> bool:
        """True for a SINGLE-concept technical requirement naming
        something outside the current concept registry (an
        "unresolved:<term>" placeholder) -- never true for a
        non-technical requirement or an alternative group.
        """
        return self.concept_id is not None and is_unresolved_concept_id(self.concept_id)

    @property
    def has_unresolved_alternative(self) -> bool:
        """True if this is an alternative group (Milestone 6B.1) where
        AT LEAST ONE option is an "unresolved:<term>" placeholder rather
        than a real registered concept -- e.g. "Python or SomeNewRuntime".
        Always False for a non-alternative requirement.
        """
        return any(is_unresolved_concept_id(alt_id) for alt_id in self.alternative_concept_ids)
