"""Milestone 11-C Phase 4 -- offline technical-competency extraction
prototype (Path B).

**NOT wired into the live parser.** Nothing in `parser.py`/
`segmentation.py`/`necessity.py`/`narrative.py` imports this module --
confirmed by a dedicated test, exactly like `qualification.py` and
`qualification_adapter.py` before it. This module CONSUMES an
already-segmented claim's text and span (the same shape
`jobs.parsing.segmentation.Claim` already produces) and PRODUCES
`Qualification` objects (Milestone 11-B Stage 1) -- it never calls
`segment_description()` itself, never calls `_requirements_from_claim`,
and is never called by either.

See `docs/evaluation/MILESTONE_11_C_COMPETENCY_EXTRACTION.md` for the
full evaluation-first comparison (Option A/B/C) this module implements
the winner of (Option C: bounded competency vocabulary + contextual
qualification classification + conservative validation) -- measured
against `evaluation/m11c/competency_extraction_controls.json`,
`scripts/evaluate_m11c_competency_extraction.py`.

**This module NEVER claims recall it has not measured, and NEVER
fabricates a value a contract has no safe field for** -- see
`_UNREPRESENTABLE_OR_GROUP` below for the one case this milestone
found where `Qualification`'s own Stage-1 model (`NormalizedReference`)
has no field to hold a required state at all (an alternative GROUP of
competency tags, as opposed to one of: a single competency tag, a
single registry concept, or a registry-concept GROUP) -- that case is
explicitly DECLINED, never silently reduced to a `competency_tag=None`
`Qualification` that would quietly discard which options were named.

**Never treats a technology mention as proof of a broader competency**
(Phase 5's own explicit requirement) -- this module's own vocabulary
(`COMPETENCY_VOCABULARY`-equivalent, see
`_COMPETENCY_PATTERNS` below) matches COMPETENCY LANGUAGE ("concurrency",
"distributed systems", "circuit theory", ...) only; it never reads
`concept_id`/`alternative_concept_ids` from any existing `JobRequirement`
or technology mention, and has no code path that could promote a
technology match into a competency claim.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from gitscore.jobs.models import SourceSpan
from gitscore.jobs.parsing.competency_aliases import ACTIVE_ALIAS_PATTERNS, AliasRelation
from gitscore.jobs.parsing.narrative import contains_narrative_cue
from gitscore.jobs.parsing.necessity import infer_necessity
from gitscore.jobs.parsing.qualification import (
    LogicalComposition,
    NormalizedReference,
    Qualification,
    QualificationKind,
)
from gitscore.jobs.types import GithubObservability, ParserConfidence

# ---------------------------------------------------------------------------
# Bounded competency vocabulary -- mirrors
# `scripts/evaluation_lib/m11c_competency_prototypes.py::COMPETENCY_VOCABULARY`
# exactly (duplicated, not imported: that module is evaluation-only
# tooling under `scripts/`, never a packaged production dependency).
# A small, curated table of (tag, pattern) pairs, the SAME closed,
# generic, non-employer-specific design `non_technical.py` already
# uses -- not a registry; `tag` is a free competency slug, never
# promoted to `JobRequirement.concept_id`.
# ---------------------------------------------------------------------------

_COMPETENCY_PATTERNS: tuple[tuple[str, "re.Pattern[str]"], ...] = (
    ("algorithms-data-structures", re.compile(
        r"\balgorithms?\s+and\s+data\s+structures?\b|\balgorithmic\s+(?:problem[-\s]solving|complexity)\b|"
        r"\bbig[-\s]o\s+analysis\b|\bdata\s+structures?\s+and\s+algorithms?\b", re.IGNORECASE)),
    ("concurrency", re.compile(
        r"\bconcurrency\b|\brace\s+conditions?\b|\block[-\s]free\b|\bmultithreading\b|"
        r"\bconcurrent\s+programming\b", re.IGNORECASE)),
    ("distributed-systems", re.compile(
        r"\bdistributed\s+systems?\b|\bconsensus\s+algorithms?\b|\bfault\s+tolerance\b", re.IGNORECASE)),
    ("system-design", re.compile(
        r"\bsystem\s+architecture\b|\bsystem\s+design\b|\bscalable\s+system\b|\bdistributed\s+architecture\b",
        re.IGNORECASE)),
    ("performance-optimization", re.compile(
        r"\bperformance[-\s]critical\b|\boptimizing\s+performance\b|\bperformance\s+optimization\b|"
        r"\bdebug(?:ging)?\s+and\s+optimiz\w+\b", re.IGNORECASE)),
    ("os-networking", re.compile(
        r"\boperating\s+systems?\s+internals\b|\btcp/ip\s+networking\b|\bprocess\s+scheduling\b|"
        r"\bnetworking\s+fundamentals\b|\boperating\s+systems?\b", re.IGNORECASE)),
    ("database-design", re.compile(
        r"\bdatabase\s+design\b|\brelational\s+schemas?\b|\bindexing\s+strategies\b|\bdatabase\s+internals\b",
        re.IGNORECASE)),
    ("ml-fundamentals", re.compile(
        r"\bml\s+fundamentals\b|\bmachine\s+learning\s+fundamentals\b|\boverfitting\b|\bregularization\b|"
        r"\bbias[-\s]variance\b|\bbasic\s+statistics\b", re.IGNORECASE)),
    ("gpu-parallel-computing", re.compile(
        r"\bgpu\s+programming\b|\bparallel\s+computing\b|\bhigh[-\s]performance\s+computing\b", re.IGNORECASE)),
    ("signal-processing", re.compile(
        r"\b(?:digital\s+)?signal\s+processing\b|\bffts?\b|\bfilter\s+design\b", re.IGNORECASE)),
    ("circuit-theory", re.compile(r"\bcircuit\s+theory\b|\banalog\s+electronics\b", re.IGNORECASE)),
    ("embedded-systems-design", re.compile(
        r"\bembedded\s+systems?\b|\bfirmware\b|\bresource[-\s]constrained\s+embedded\b", re.IGNORECASE)),
    ("control-systems", re.compile(
        r"\bcontrol\s+systems?\s+theory\b|\bpid\b|\bstate[-\s]space\s+methods?\b|\bcontrol\s+systems?\b",
        re.IGNORECASE)),
    ("computer-vision", re.compile(
        r"\bcomputer\s+vision\b|\bobject\s+detection\b|\bimage\s+segmentation\b", re.IGNORECASE)),
    ("cybersecurity-threat-modeling", re.compile(
        r"\bthreat\s+modeling\b|\battack\s+vectors?\b|\bsecure\s+coding\b|\bcybersecurity\b", re.IGNORECASE)),
    ("digital-logic", re.compile(r"\bdigital\s+logic(?:\s+design)?\b|\bboolean\s+algebra\b", re.IGNORECASE)),
    ("quantum-computing", re.compile(
        r"\bquantum\s+circuit\s+design\b|\bqubit\s+error\s+correction\b|\bquantum\s+computing\b",
        re.IGNORECASE)),
)

# Milestone 11-C Phase 4/Stage 2A Phase 4 -- the "third observability
# table" that document's own Phase 4 found missing (keyed by
# competency_tag, never by category or concept mention). A policy
# LOOKUP, not an evidence DETECTOR: it never inspects any repository or
# dependency; it only answers "is this KIND of claim even plausibly
# checkable from GitHub activity at all" -- the same question
# `observability.py`'s own existing tables already answer for technical
# concepts and non-technical categories. Mirrors that module's own
# "a single constant/small table, never scattered conditionals" design.
_COMPETENCY_OBSERVABILITY: dict[str, GithubObservability] = {
    "algorithms-data-structures": GithubObservability.PARTIALLY_OBSERVABLE,
    "concurrency": GithubObservability.PARTIALLY_OBSERVABLE,
    "distributed-systems": GithubObservability.PARTIALLY_OBSERVABLE,
    "system-design": GithubObservability.PARTIALLY_OBSERVABLE,
    "performance-optimization": GithubObservability.PARTIALLY_OBSERVABLE,
    "os-networking": GithubObservability.PARTIALLY_OBSERVABLE,
    "database-design": GithubObservability.PARTIALLY_OBSERVABLE,
    "ml-fundamentals": GithubObservability.NOT_OBSERVABLE,
    "gpu-parallel-computing": GithubObservability.PARTIALLY_OBSERVABLE,
    "signal-processing": GithubObservability.PARTIALLY_OBSERVABLE,
    "circuit-theory": GithubObservability.NOT_OBSERVABLE,
    "embedded-systems-design": GithubObservability.PARTIALLY_OBSERVABLE,
    "control-systems": GithubObservability.PARTIALLY_OBSERVABLE,
    "computer-vision": GithubObservability.PARTIALLY_OBSERVABLE,
    "cybersecurity-threat-modeling": GithubObservability.PARTIALLY_OBSERVABLE,
    "digital-logic": GithubObservability.PARTIALLY_OBSERVABLE,
    "quantum-computing": GithubObservability.NOT_OBSERVABLE,
}
_DEFAULT_COMPETENCY_OBSERVABILITY = GithubObservability.PARTIALLY_OBSERVABLE

# ---------------------------------------------------------------------------
# Sentence-role / qualification-cue signals -- Option C's own additions
# over Option B, each bounded and generic, never modifying the existing
# production modules they reuse (`necessity.py`, `narrative.py`).
# ---------------------------------------------------------------------------

_RESPONSIBILITY_LEAD = re.compile(
    r"^[\s\-*]*\b(?:design(?:\s+and)?|implement|build|develop|debug(?:\s+and)?|optimize|collaborate|"
    r"maintain|own|lead|drive|write|create|architect)\b",
    re.IGNORECASE,
)

_BROADER_NARRATIVE_SUBJECT = re.compile(
    r"\b(?:our\s+(?:team|engineers?|engineering\s+team)|we'?re\s+a\b|we\s+are\s+a\b|the\s+team)\b",
    re.IGNORECASE,
)

_NEGATION_PATTERNS: tuple["re.Pattern[str]", ...] = (
    re.compile(r"\bno\s+(?:prior\s+)?(?:experience|knowledge|background)\s+with\b.{0,60}\b(?:is\s+)?(?:necessary|required|needed)\b", re.IGNORECASE),
    re.compile(r"\bnot\s+required\b", re.IGNORECASE),
    re.compile(r"\bno\s+need\s+(?:to|for)\b", re.IGNORECASE),
)

_APPLICABILITY_CUE = re.compile(r"\bunless\b|\bif\s+the\s+role\s+requires\b|\bif\s+applicable\b", re.IGNORECASE)
_EXHAUSTIVE_CUE = re.compile(r"\bone\s+of\s+the\s+following\b", re.IGNORECASE)
_ILLUSTRATIVE_CUE = re.compile(r"\bsuch\s+as\b|\be\.g\.,?\b", re.IGNORECASE)
_AND_WORD = re.compile(r"\band\b", re.IGNORECASE)
_OR_WORD = re.compile(r"\bor\b", re.IGNORECASE)
_MIXED_SHAPE = re.compile(r"\band\b.{0,40}\beither\b.{0,80}\bor\b", re.IGNORECASE)


def find_competency_mentions(text: str) -> list[str]:
    """Every DISTINCT competency tag whose pattern matches `text`, in
    vocabulary order."""
    return [tag for tag, pattern in _COMPETENCY_PATTERNS if pattern.search(text)]


def _applicability_condition(text: str) -> str | None:
    match = _APPLICABILITY_CUE.search(text)
    if match is None:
        return None
    clause = text[match.start() :].strip().rstrip(".")
    return clause or None


@dataclass(frozen=True)
class DeclinedExtraction:
    """Returned (never silently swallowed) when this module recognizes
    a shape it deliberately does NOT extract -- either a rejection
    (narrative/responsibility/negation -- not an applicant qualification
    at all) or a MISSING-CONTRACT case (`reason="missing_contract"`):
    `Qualification`'s own `NormalizedReference` has no field to hold an
    alternative GROUP of competency tags (as opposed to one registered
    concept, one competency tag, or a GROUP of registered concepts) --
    see this module's own docstring. Declining here, rather than
    constructing a `Qualification` with `normalized_reference=None`,
    is the difference between an honest gap and a silent one: the
    latter would discard which specific competency options the
    sentence named, with no way for a caller to recover that the loss
    even happened.
    """

    reason: str
    detail: str


def extract_competency_qualifications(
    text: str, span: SourceSpan
) -> tuple[Qualification, ...] | DeclinedExtraction:
    """The one public entry point. Returns a (possibly multi-element,
    for a genuine AND-of-distinct-areas sentence) tuple of
    `Qualification` objects, or a `DeclinedExtraction` explaining why
    none could be safely produced -- NEVER an empty tuple standing in
    for "nothing to say" (that would be indistinguishable from "this
    text has no competency language at all," a different fact a caller
    may want to tell apart from "this text had competency language but
    was conservatively rejected").
    """
    tags = find_competency_mentions(text)
    if not tags:
        return DeclinedExtraction(reason="no_competency_language", detail="no vocabulary term matched")

    if any(pattern.search(text) for pattern in _NEGATION_PATTERNS):
        return DeclinedExtraction(reason="negation", detail="explicit negation of the requirement")
    if contains_narrative_cue(text) or _BROADER_NARRATIVE_SUBJECT.search(text):
        return DeclinedExtraction(reason="narrative_cue", detail="company/product or learning-opportunity narrative shape")
    if _RESPONSIBILITY_LEAD.match(text.strip()):
        return DeclinedExtraction(reason="responsibility_lead", detail="sentence opens with a bare imperative duty verb")

    necessity = infer_necessity(text, None)
    applicability = _applicability_condition(text)
    has_and = _AND_WORD.search(text) is not None
    has_or = _OR_WORD.search(text) is not None
    exhaustive = _EXHAUSTIVE_CUE.search(text) is not None
    illustrative = _ILLUSTRATIVE_CUE.search(text) is not None

    if len(tags) == 1:
        qualification = Qualification(
            qualification_kind=QualificationKind.TECHNICAL_COMPETENCY,
            source_text=text,
            source_span=span,
            necessity=necessity,
            applicability_condition=applicability,
            logical_composition=LogicalComposition.SINGLE,
            normalized_reference=NormalizedReference(competency_tag=tags[0]),
            github_observability=_COMPETENCY_OBSERVABILITY.get(tags[0], _DEFAULT_COMPETENCY_OBSERVABILITY),
        )
        return (qualification,)

    # Multiple DISTINCT competency tags found.
    if has_or and not has_and and (exhaustive or illustrative or True):
        # An alternative GROUP of competency tags -- `NormalizedReference`
        # has a field for a group of REGISTRY concepts
        # (`alternative_concept_ids`) and a field for ONE unregistered
        # competency tag (`competency_tag`), but no field at all for a
        # group of MULTIPLE unregistered competency tags. Declined, not
        # invented -- see `DeclinedExtraction`'s own docstring.
        return DeclinedExtraction(
            reason="missing_contract",
            detail=(
                f"an alternative group of {len(tags)} competency tags {tags!r} has no safe "
                "NormalizedReference representation -- it supports alternative_concept_ids "
                "(registered concepts only) or a single competency_tag, never a GROUP of "
                "competency tags. Representing this would require a new field on Qualification's "
                "NormalizedReference (e.g. alternative_competency_tags), which is a Stage-1 model "
                "change outside this milestone's approval -- not added here."
            ),
        )

    if has_and and has_or and _MIXED_SHAPE.search(text):
        qualification = Qualification(
            qualification_kind=QualificationKind.TECHNICAL_COMPETENCY,
            source_text=text,
            source_span=span,
            necessity=necessity,
            applicability_condition=applicability,
            logical_composition=LogicalComposition.MIXED_UNSUPPORTED,
            normalized_reference=None,
            github_observability=_COMPETENCY_OBSERVABILITY.get(tags[0], _DEFAULT_COMPETENCY_OBSERVABILITY),
        )
        return (qualification,)

    # A genuine AND of distinct, independently-named competency areas
    # (e.g. "concurrency, distributed systems, and database design") --
    # each tag is SAFELY representable on its own, so this splits into
    # N sibling Qualification objects, each SINGLE, mirroring Milestone
    # 6A/10E/11-B's own established "one sentence, multiple qualification
    # objects" precedent -- never one lossy, conflated row.
    return tuple(
        Qualification(
            qualification_kind=QualificationKind.TECHNICAL_COMPETENCY,
            source_text=text,
            source_span=span,
            necessity=necessity,
            applicability_condition=applicability,
            logical_composition=LogicalComposition.AND,
            normalized_reference=NormalizedReference(competency_tag=tag),
            github_observability=_COMPETENCY_OBSERVABILITY.get(tag, _DEFAULT_COMPETENCY_OBSERVABILITY),
        )
        for tag in tags
    )


# ===========================================================================
# Milestone 11-E -- v2: a backward-compatible, paraphrase-tolerant EXTENSION.
#
# `extract_competency_qualifications()` above (v1, M11-C) is completely
# UNCHANGED by everything below -- confirmed by re-running M11-C's own
# development harness byte-identically. v2 is a SEPARATE function,
# reusing v1's exact-phrase vocabulary, every rejection filter, and every
# safety rule (missing-contract decline, MIXED_UNSUPPORTED detection,
# necessity/applicability handling, AND-splitting into siblings) --
# the ONLY thing v2 changes is HOW a competency tag is recognized:
# v1 requires an exact canonical phrase; v2 ALSO recognizes the bounded,
# auditable `competency_aliases` table, matched against a STEMMED copy
# of the text (tolerating plurals/`-ing`/`-ic` suffix variation without
# resorting to unordered bag-of-words matching -- see
# `docs/evaluation/MILESTONE_11_E_PARAPHRASE_EXTRACTION.md`'s own Phase 3
# comparison for why this, Option C, was chosen over a naive bigger
# phrase list (Option A, 62/64 recall on the Phase 2 dev corpus, zero
# grammatical tolerance) or bag-of-words keyword overlap (Option B,
# 31/64 recall, worse precision too).
# ===========================================================================

_QUALIFYING_INTENT_V2 = re.compile(
    r"\b(?:experience|knowledge|understanding|familiarity|proficiency|skills?|background|expertise|grounding|grasp)\s+"
    r"(?:with|of|in|building|optimizing|debugging)\b|\bstrong\b|\bsolid\b|\bdeep\b|\bcomfortable\b|"
    r"\b(?:is|are)\s+(?:required|preferred|necessary|a\s+plus)\b",
    re.IGNORECASE,
)
"""A bounded, auditable qualification-INTENT gate -- v2's own additional
precision guard beyond v1's exact-phrase matching, since the alias
table's looser (stemmed) matching needs a stronger signal that the
sentence is actually MAKING a qualification claim, not just containing
competency-adjacent words somewhere. Covers the two dominant real-world
sentence shapes a bounded qualifying-lead-in check must handle -- a
LEADING qualifier ("experience with X") and the equally common
TRAILING shape ("X experience is required") -- both confirmed present
in this milestone's own Phase 2/3 comparison, not assumed."""

_WORD_TOKEN_V2 = re.compile(r"(?<!\\)[a-zA-Z][a-zA-Z0-9]*")


def _stem_v2(word: str) -> str:
    """The SAME small, fixed suffix-stripping rule set verified during
    this milestone's own Phase 3 comparison -- never context-dependent,
    never a dictionary lookup, never a statistical model. Only strips a
    suffix when the remainder stays >=4 characters, so short/ambiguous
    words (and short all-caps acronyms like "RTOS") are left alone."""
    for suffix, replacement in (("ically", ""), ("ization", "ize"), ("izations", "ize"),
                                 ("ications", "ic"), ("ations", ""), ("ation", ""),
                                 ("ical", ""), ("ing", ""), ("ies", "y"), ("ic", ""), ("s", "")):
        if word.endswith(suffix) and len(word) - len(suffix) + len(replacement) >= 4:
            return word[: -len(suffix)] + replacement
    return word


def _stem_token_v2(match: "re.Match[str]") -> str:
    return _stem_v2(match.group(0).lower())


def _stemmed_text_v2(text: str) -> str:
    """Stems each word IN PLACE (via substitution, not extract-and-rejoin)
    so non-alphanumeric separators within a phrase (e.g. the `&` in
    `DS&A`) survive identically to how `_stem_pattern_source_v2` already
    preserves them on the pattern side -- confirmed, during this
    milestone's own test-writing, that extracting words and rejoining
    them with plain spaces silently DROPS such separators, breaking any
    alias whose own trigger phrase contains one (`DS&A` stemmed to
    `ds a` on the text side but stayed `DS&A` on the pattern side,
    never matching). Both sides now go through the identical
    substitution-based path."""
    return _WORD_TOKEN_V2.sub(_stem_token_v2, text.lower())


def _stem_pattern_source_v2(raw_pattern: str) -> str:
    return _WORD_TOKEN_V2.sub(_stem_token_v2, raw_pattern)


_STEMMED_COMPETENCY_PATTERNS_V2: tuple[tuple[str, "re.Pattern[str]"], ...] = tuple(
    (tag, re.compile(_stem_pattern_source_v2(pattern.pattern), re.IGNORECASE)) for tag, pattern in _COMPETENCY_PATTERNS
)
_STEMMED_ACTIVE_ALIAS_PATTERNS_V2: tuple[tuple[str, "re.Pattern[str]", AliasRelation], ...] = tuple(
    (tag, re.compile(_stem_pattern_source_v2(pattern.pattern), re.IGNORECASE), relation)
    for tag, pattern, relation in ACTIVE_ALIAS_PATTERNS
)

_RELATION_CONFIDENCE: dict[AliasRelation, ParserConfidence] = {
    AliasRelation.SEMANTICALLY_EQUIVALENT: ParserConfidence.HIGH,
    AliasRelation.NARROWER_OR_MORE_SPECIFIC: ParserConfidence.MEDIUM,
}


def find_competency_mentions_v2(text: str) -> dict[str, AliasRelation]:
    """Every DISTINCT competency tag found via EITHER the exact canonical
    vocabulary OR the bounded alias table, matched against STEMMED text
    on both sides -- mapping tag -> the STRONGEST relation found for it
    (`SEMANTICALLY_EQUIVALENT` beats `NARROWER_OR_MORE_SPECIFIC` if a
    sentence somehow matches both for the same tag). Requires
    `_QUALIFYING_INTENT_V2` to match somewhere in `text` first -- returns
    `{}` immediately otherwise, exactly like v1's own `not tags` case.
    `RELATED_ONLY`/`UNKNOWN` aliases are never consulted here at all
    (excluded at import time in `competency_aliases.py`), so this
    function cannot promote an explicitly-rejected adjacent term into a
    tag no matter how the text is phrased.
    """
    if not _QUALIFYING_INTENT_V2.search(text):
        return {}
    stemmed = _stemmed_text_v2(text)
    found: dict[str, AliasRelation] = {}
    for tag, pattern in _STEMMED_COMPETENCY_PATTERNS_V2:
        if pattern.search(stemmed):
            found[tag] = AliasRelation.SEMANTICALLY_EQUIVALENT
    for tag, pattern, relation in _STEMMED_ACTIVE_ALIAS_PATTERNS_V2:
        if pattern.search(stemmed):
            if tag not in found or relation == AliasRelation.SEMANTICALLY_EQUIVALENT:
                found[tag] = relation
    return found


def extract_competency_qualifications_v2(
    text: str, span: SourceSpan
) -> tuple[Qualification, ...] | DeclinedExtraction:
    """The paraphrase-tolerant sibling of `extract_competency_qualifications()`
    (v1). Identical rejection/necessity/structural logic throughout --
    only `find_competency_mentions_v2()` (stemmed canonical+alias
    matching) replaces v1's exact-phrase-only `find_competency_mentions()`.
    Each produced `Qualification.interpretation_certainty` reflects the
    STRENGTH of the match that produced it (`HIGH` for an exact/
    canonical/semantically-equivalent hit, `MEDIUM` for a
    narrower-or-more-specific one) -- reusing the EXISTING, Stage-1-
    approved `ParserConfidence` field, never a new one, and never
    silently treating a narrower match as equally certain as an exact
    one.
    """
    tag_relations = find_competency_mentions_v2(text)
    if not tag_relations:
        return DeclinedExtraction(reason="no_competency_language", detail="no vocabulary or alias term matched")

    if any(pattern.search(text) for pattern in _NEGATION_PATTERNS):
        return DeclinedExtraction(reason="negation", detail="explicit negation of the requirement")
    if contains_narrative_cue(text) or _BROADER_NARRATIVE_SUBJECT.search(text):
        return DeclinedExtraction(reason="narrative_cue", detail="company/product or learning-opportunity narrative shape")
    if _RESPONSIBILITY_LEAD.match(text.strip()):
        return DeclinedExtraction(reason="responsibility_lead", detail="sentence opens with a bare imperative duty verb")

    tags = list(tag_relations.keys())
    necessity = infer_necessity(text, None)
    applicability = _applicability_condition(text)
    has_and = _AND_WORD.search(text) is not None
    has_or = _OR_WORD.search(text) is not None
    exhaustive = _EXHAUSTIVE_CUE.search(text) is not None
    illustrative = _ILLUSTRATIVE_CUE.search(text) is not None

    def _confidence_for(tag: str) -> ParserConfidence:
        return _RELATION_CONFIDENCE[tag_relations[tag]]

    if len(tags) == 1:
        qualification = Qualification(
            qualification_kind=QualificationKind.TECHNICAL_COMPETENCY,
            source_text=text,
            source_span=span,
            necessity=necessity,
            applicability_condition=applicability,
            interpretation_certainty=_confidence_for(tags[0]),
            logical_composition=LogicalComposition.SINGLE,
            normalized_reference=NormalizedReference(competency_tag=tags[0]),
            github_observability=_COMPETENCY_OBSERVABILITY.get(tags[0], _DEFAULT_COMPETENCY_OBSERVABILITY),
        )
        return (qualification,)

    if has_or and not has_and and (exhaustive or illustrative or True):
        return DeclinedExtraction(
            reason="missing_contract",
            detail=(
                f"an alternative group of {len(tags)} competency tags {tags!r} has no safe "
                "NormalizedReference representation -- same missing-contract gap v1 found, "
                "unchanged by v2's own broader matching"
            ),
        )

    if has_and and has_or and _MIXED_SHAPE.search(text):
        qualification = Qualification(
            qualification_kind=QualificationKind.TECHNICAL_COMPETENCY,
            source_text=text,
            source_span=span,
            necessity=necessity,
            applicability_condition=applicability,
            interpretation_certainty=_confidence_for(tags[0]),
            logical_composition=LogicalComposition.MIXED_UNSUPPORTED,
            normalized_reference=None,
            github_observability=_COMPETENCY_OBSERVABILITY.get(tags[0], _DEFAULT_COMPETENCY_OBSERVABILITY),
        )
        return (qualification,)

    return tuple(
        Qualification(
            qualification_kind=QualificationKind.TECHNICAL_COMPETENCY,
            source_text=text,
            source_span=span,
            necessity=necessity,
            applicability_condition=applicability,
            interpretation_certainty=_confidence_for(tag),
            logical_composition=LogicalComposition.AND,
            normalized_reference=NormalizedReference(competency_tag=tag),
            github_observability=_COMPETENCY_OBSERVABILITY.get(tag, _DEFAULT_COMPETENCY_OBSERVABILITY),
        )
        for tag in tags
    )
