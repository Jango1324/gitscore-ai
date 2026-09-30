"""Milestone 6A -- job-requirement enums and schema version.

Mirrors evidence/types.py's shape (small ordinal/plain enums + one
schema-version constant), but nothing here is shared with or reused
from evidence/types.py: candidate-evidence confidence
(gitscore.evidence.types.ConfidenceLevel) answers "how sure are we this
observation is real"; the enums below answer different questions
entirely (how the job posting itself weighs a requirement, and how sure
a future parser was that it read the job text correctly). Reusing
ConfidenceLevel for either would blur two genuinely different concepts
under one name -- see ParserConfidence's docstring for the specific
contrast with ConfidenceLevel this milestone was told to avoid.

JOB_REQUIREMENT_SCHEMA_VERSION = 2

Bump JOB_REQUIREMENT_SCHEMA_VERSION whenever `JobRequirement` or
`JobRequirementProfile` (jobs/models.py, jobs/profile.py) change SHAPE
(a field added, removed, or retyped) -- mirroring
EVIDENCE_SCHEMA_VERSION's own policy (evidence/types.py). It does NOT
bump for adding a new member to one of the enums below (additive,
non-breaking, exactly like adding a new EvidenceType member does not
bump EVIDENCE_SCHEMA_VERSION either).

Bumped 1 -> 2 in Milestone 6B.1: `JobRequirement` gained
`alternative_concept_ids: tuple[str, ...] = ()` (a genuine SHAPE
change -- a new field) to represent a single logical requirement
satisfied by ANY ONE of several technical concepts ("Python or Go"),
replacing an initial Milestone 6B implementation that collapsed such a
claim into a non-technical placeholder with no schema change. See
`jobs/models.py`'s `JobRequirement` docstring and
`docs/CHANGELOG_DEV.md`'s Milestone 6B.1 entry for the full design
writeup and why the additive field is backward-compatible (every
Milestone 6A/6A.1/6B `JobRequirement` already had this field implicitly
at its default `()`).

This is a new, independent constant -- introducing it does not bump
EVIDENCE_SCHEMA_VERSION, CONCEPT_REGISTRY_VERSION,
REPOSITORY_RANKING_VERSION, SCORING_RUBRIC_VERSION, or DATASET_VERSION.
Nothing in this milestone changes candidate-evidence extraction, the
concept registry, repository ranking, or V1 scoring/dataset shape.
"""
from __future__ import annotations

from enum import Enum, IntEnum

JOB_REQUIREMENT_SCHEMA_VERSION = 2


class Necessity(str, Enum):
    """Does the job posting say this requirement is mandatory or a plus?

    Deliberately just two states (Milestone 6A instruction: "do not
    invent excessive granularity"). The earlier
    docs/design/MILESTONE_5A_JOB_MATCHING_DESIGN.md Part 9 draft proposed
    a four-state `requirement_type` ("required" / "preferred" /
    "responsibility" / "nice_to_have"); that draft was never implemented,
    and this milestone's actual instructions explicitly narrow it back
    down to two. A future parser mapping "nice to have" / "a plus" /
    "bonus" phrasing all lands on PREFERRED; anything stated as mandatory
    ("must have", "required", no qualifying language at all) lands on
    REQUIRED. `Importance` (below) is the separate axis for "but how much
    does this one actually matter" -- see its own docstring.
    """

    REQUIRED = "required"
    PREFERRED = "preferred"


class Importance(IntEnum):
    """How much this ONE requirement matters to the job, independent of
    whether it's REQUIRED or PREFERRED (Necessity, above).

    Ordinal, not a float weight -- Milestone 6A instruction: "Do NOT
    introduce fake-precision floating-point weights yet unless the
    existing 5A design strongly justifies them" (it doesn't; 5A Part 15.3
    only ever used illustrative placeholder floats it flagged as
    unresolved assumptions, never a claim precise enough to reproduce
    with an ordinal scale). `IntEnum` so "the most important requirement"
    is a plain `max()`, exactly like `ConfidenceLevel`.

    Necessity and Importance are independent axes on purpose -- a job can
    require both Git and Python (both `Necessity.REQUIRED`) while caring
    far more about Python (`Importance.HIGH`) than Git
    (`Importance.LOW`); collapsing them into one field would lose that
    distinction.
    """

    LOW = 1
    MEDIUM = 2
    HIGH = 3


class GithubObservability(IntEnum):
    """Can a GitHub account plausibly demonstrate this requirement at
    all -- independent of whether this specific candidate happens to
    show it.

    This is the field that keeps GitScore from ever implying "GitHub can
    verify everything in a job description" (Milestone 6A Part 4,
    directly): a requirement's necessity/importance to the job is a fact
    about the job; its observability is a fact about what kind of claim
    it even is. "5 years of professional experience" is exactly as
    REQUIRED and HIGH-importance as "Python" might be, yet the two must
    never be scored the same way -- that distinction lives here, not in
    Necessity or Importance.

    Ordinal (`IntEnum`, higher = more directly checkable from public
    GitHub activity) so a future matcher can threshold/sort on it the
    same way it does `ConfidenceLevel` -- but it is a DIFFERENT ordinal
    scale answering a different question, not a reuse of
    `ConfidenceLevel` (see this module's docstring).

    - `NOT_OBSERVABLE`: not the kind of claim GitHub evidence can speak
      to at all (years of professional experience, a degree, work
      authorization, communication skills).
    - `PARTIALLY_OBSERVABLE`: plausibly inferable from GitHub activity,
      but not reliably or completely (e.g. "experience designing
      distributed systems" -- architecture/scale of repositories might
      hint at it, but proves nothing conclusively).
    - `STRONGLY_OBSERVABLE`: a concrete technology/practice a repository
      can directly, concretely demonstrate (a language, framework,
      database, or tool -- "uses React", "experience with Docker").

    This module defines the representation only. The POLICY that decides
    which value a given raw requirement phrase should get is future
    parser work (explicitly out of scope for Milestone 6A).
    """

    NOT_OBSERVABLE = 1
    PARTIALLY_OBSERVABLE = 2
    STRONGLY_OBSERVABLE = 3


class ParserConfidence(IntEnum):
    """How sure a (future) parser was that it interpreted a piece of job
    text correctly -- NOT how sure GitScore is that a candidate-side
    observation is real.

    This is the field Milestone 6A Part 9 explicitly asked for as a
    SEPARATE small enum rather than a reuse of
    `gitscore.evidence.types.ConfidenceLevel`: `ConfidenceLevel` answers
    "how sure are we this candidate-side observation (a dependency-
    manifest line, a README mention) is real" -- a claim about GITHUB
    EVIDENCE. `ParserConfidence` answers "how sure are we we correctly
    interpreted THIS JOB-DESCRIPTION TEXT as a distinct, well-formed
    requirement" -- e.g. whether "experience with cloud platforms such
    as AWS or Azure" names AWS and Azure as independent requirements, as
    interchangeable alternatives, or merely as illustrative examples of
    "cloud platforms" in general. Reusing `ConfidenceLevel` here would
    make a job-parsing uncertainty read as if it were a claim about a
    candidate's GitHub activity, which it never is.

    Optional on `JobRequirement` (Milestone 6A ships no parser yet --
    every requirement in this milestone is hand-constructed, so there is
    nothing yet to be uncertain about; `None` means "not evaluated by any
    parser," not "certain").
    """

    LOW = 1
    MEDIUM = 2
    HIGH = 3
