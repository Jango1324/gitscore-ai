"""Milestone 11-G9 Phase 3 -- offline competency-extractor v3 PROTOTYPE.

**EVALUATION-ONLY. Lives entirely under `scripts/evaluation_lib/`, never
under `src/gitscore/`.** Nothing in the live parser or in
`src/gitscore/jobs/parsing/competency_extraction.py` (v1/v2) imports or
is imported by this module -- confirmed by a dedicated test
(`tests/test_m11g9_v3_feasibility.py::test_v3_is_not_imported_by_production_or_by_v1_v2`).
v1 and v2 are completely byte-unchanged by this milestone.

## What v3 changes relative to v2

v3 reuses EVERY existing v2 primitive unchanged (`_QUALIFYING_INTENT_V2`,
`_stemmed_text_v2`, `_NEGATION_PATTERNS`, `_RESPONSIBILITY_LEAD`,
`_BROADER_NARRATIVE_SUBJECT`, `contains_narrative_cue`,
`_split_alternative_segments_v2`, `infer_necessity`/
`resolve_necessity_hint`, `LogicalComposition`, `NormalizedReference`,
`Qualification`, `DeclinedExtraction`) and v2's exact control flow
(negation -> narrative -> responsibility-lead -> OR-list structural
safety -> single/AND-split) -- the ONLY thing v3 changes is the
VOCABULARY/ALIAS TABLE itself, via two bounded additions, each directly
traceable to a specific M11-G9 Phase 1/2 corpus finding (never a blanket
"add every technology noun" expansion -- the milestone's own explicit
restriction):

1. **3 new top-level concepts** (`_V3_NEW_CONCEPTS`), each justified by
   RECURRING evidence across >=2 independently-sourced M11-G9 postings
   (see `docs/evaluation/MILESTONE_11_G9_COMPETENCY_V3_FEASIBILITY.md`
   Phase 2 for the full audit):
   - `generative-ai-agentic-systems` (5 of 14 postings: Extreme Networks,
     Basis, Board Intelligence, Simbe Robotics, PointClickCare)
   - `cloud-infrastructure-devops` (PointClickCare, Extreme Networks)
   - `data-engineering-pipelines` (Vida Health, Firework, Extreme
     Networks)
   Candidates found in only ONE posting (identity/authorization-OAuth,
   SRE-ops, robotics-middleware/ROS, realtime-ML-serving) are explicitly
   NOT promoted here -- noted in Phase 2 as insufficiently recurring
   within this bounded corpus, not fabricated into tags on single-posting
   evidence.

2. **4 targeted missing-alias-phrasing fixes for EXISTING tags**, each
   tied to one specific annotated miss (never a general loosening of
   match strength):
   - embedded-systems-design: `RTOS environments/experience` (product-
     name-based phrasing distinct from the existing literal "RTOS
     development" alias) and `developing (software for) bare metal`
     (verb-first paraphrase of "bare-metal programming")
   - signal-processing: `designed/designing filters` (verb-first
     paraphrase of the canonical "filter design")
   - database-design: `data modeling` / `dimensional modeling`

## What v3 deliberately does NOT do

Every "risky_related" case identified during annotation is deliberately
LEFT UNALIASED, not defended against with new exclusion machinery --
declining-by-absence is the same mechanism v1/v2 already rely on for
every other EXCLUDED/unknown case:
- "incident management" is NOT aliased to cybersecurity-threat-modeling
  (conflates SRE/production-ops incident handling with security incident
  response -- a different discipline despite the shared English word).
- "cost optimization" / "cloud cost optimization" is NOT aliased to
  performance-optimization (FinOps, not a performance claim).
- "AI/ML workload exposure" (operational) is NOT aliased to
  ml-fundamentals (operating ML infra is not ML theory).
- generic "networking background" is NOT aliased to os-networking (too
  broad/ambiguous a phrase to safely disambiguate from non-technical
  "networking").
- "embedded systems" as an ML-model DEPLOYMENT TARGET (Simbe Robotics)
  is NOT additionally tagged embedded-systems-design beyond whatever v2
  already does -- v3 makes no attempt to distinguish deployment-target
  mentions from firmware-engineering-discipline mentions; this is an
  explicitly flagged RESIDUAL conflation risk v3 does not resolve (see
  the milestone doc's own Phase 4 precision analysis), not a solved one.

v3 makes NO LLM or external API calls, performs NO live integration,
and uses the SAME closed-vocabulary regex/stemming strategy v1/v2 use --
only the vocabulary table itself is larger.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from gitscore.jobs.models import SourceSpan
from gitscore.jobs.parsing.competency_aliases import AliasRelation
from gitscore.jobs.parsing.competency_extraction import (
    _AND_WORD,
    _APPLICABILITY_CUE,
    _BROADER_NARRATIVE_SUBJECT,
    _EQUIVALENT_SUBSTITUTE_V2,
    _EXHAUSTIVE_CUE,
    _ILLUSTRATIVE_CUE,
    _NEGATION_PATTERNS,
    _OR_LIST_FINAL_ITEM_V2,
    _OR_WORD,
    _QUALIFYING_INTENT_V2,
    _RESPONSIBILITY_LEAD,
    _STEMMED_ACTIVE_ALIAS_PATTERNS_V2,
    _STEMMED_COMPETENCY_PATTERNS_V2,
    _applicability_condition,
    _stem_pattern_source_v2,
    _stemmed_text_v2,
    DeclinedExtraction,
)
from gitscore.jobs.parsing.narrative import contains_narrative_cue
from gitscore.jobs.parsing.necessity import infer_necessity, resolve_necessity_hint
from gitscore.jobs.parsing.qualification import (
    LogicalComposition,
    NormalizedReference,
    Qualification,
    QualificationKind,
)
from gitscore.jobs.parsing.segmentation import _SECTION_NECESSITY_HINT, _SectionKind
from gitscore.jobs.types import GithubObservability, ParserConfidence

# ---------------------------------------------------------------------------
# M11-G9 Phase 2 -- 3 new top-level concepts (bounded, recurrence-justified).
# A separate table from the EXISTING 17-tag `_COMPETENCY_PATTERNS` -- kept
# distinct so a reviewer can see exactly what this milestone ADDS without
# re-reading the unmodified existing table.
# ---------------------------------------------------------------------------

_V3_NEW_CONCEPTS: tuple[tuple[str, "re.Pattern[str]"], ...] = (
    ("generative-ai-agentic-systems", re.compile(
        r"\bgenerative\s+ai\b|\bagentic\s+(?:system|program|coding|workflow)\w*\b|"
        r"\bllm[-\s]?(?:assisted|based)\b|\bai[-\s]coding\s+tools?\b", re.IGNORECASE)),
    ("cloud-infrastructure-devops", re.compile(
        r"\binfrastructure[-\s]as[-\s]code\b|\bci\/cd\s+pipelines?\b|"
        r"\bcloud[-\s]native\s+(?:architecture|infrastructure)\b|\bgitops\b", re.IGNORECASE)),
    ("data-engineering-pipelines", re.compile(
        r"\bdata\s+pipelines?\b|\betl\/elt\b|\bdata\s+warehousing\b|\bdata\s+ingestion\b",
        re.IGNORECASE)),
)

_V3_NEW_CONCEPT_OBSERVABILITY: dict[str, GithubObservability] = {
    "generative-ai-agentic-systems": GithubObservability.PARTIALLY_OBSERVABLE,
    "cloud-infrastructure-devops": GithubObservability.STRONGLY_OBSERVABLE,
    "data-engineering-pipelines": GithubObservability.STRONGLY_OBSERVABLE,
}

# ---------------------------------------------------------------------------
# M11-G9 Phase 2 -- 4 targeted missing-alias-phrasing fixes for EXISTING
# tags. Each entry below is additive to (never a replacement of) the real
# `ACTIVE_ALIAS_PATTERNS` from `competency_aliases.py`, which v3 still
# consults in full.
# ---------------------------------------------------------------------------

_V3_ADDITIONAL_ALIASES: tuple[tuple[str, "re.Pattern[str]", AliasRelation], ...] = (
    ("embedded-systems-design", re.compile(r"\bRTOS\s+(?:environments?|experience|development)\b", re.IGNORECASE), AliasRelation.SEMANTICALLY_EQUIVALENT),
    ("embedded-systems-design", re.compile(r"\bdeveloping\s+(?:software\s+)?for\s+bare[-\s]metal\b", re.IGNORECASE), AliasRelation.NARROWER_OR_MORE_SPECIFIC),
    ("signal-processing", re.compile(r"\bdesign(?:ed|ing)\s+filters?\b", re.IGNORECASE), AliasRelation.SEMANTICALLY_EQUIVALENT),
    ("database-design", re.compile(r"\bdata\s+model(?:ing|ling)\b|\bdimensional\s+model(?:ing|ling)\b", re.IGNORECASE), AliasRelation.NARROWER_OR_MORE_SPECIFIC),
)

_V3_NEW_CONCEPTS_STEMMED: tuple[tuple[str, "re.Pattern[str]"], ...] = tuple(
    (tag, re.compile(_stem_pattern_source_v2(pattern.pattern), re.IGNORECASE)) for tag, pattern in _V3_NEW_CONCEPTS
)
_V3_ADDITIONAL_ALIASES_STEMMED: tuple[tuple[str, "re.Pattern[str]", AliasRelation], ...] = tuple(
    (tag, re.compile(_stem_pattern_source_v2(pattern.pattern), re.IGNORECASE), relation)
    for tag, pattern, relation in _V3_ADDITIONAL_ALIASES
)

_RELATION_CONFIDENCE_V3: dict[AliasRelation, ParserConfidence] = {
    AliasRelation.SEMANTICALLY_EQUIVALENT: ParserConfidence.HIGH,
    AliasRelation.NARROWER_OR_MORE_SPECIFIC: ParserConfidence.MEDIUM,
}


def _competency_observability_v3(tag: str) -> GithubObservability:
    from gitscore.jobs.parsing.competency_extraction import _COMPETENCY_OBSERVABILITY, _DEFAULT_COMPETENCY_OBSERVABILITY
    if tag in _V3_NEW_CONCEPT_OBSERVABILITY:
        return _V3_NEW_CONCEPT_OBSERVABILITY[tag]
    return _COMPETENCY_OBSERVABILITY.get(tag, _DEFAULT_COMPETENCY_OBSERVABILITY)


def find_competency_mentions_v3(text: str) -> dict[str, AliasRelation]:
    """Identical gating/matching strategy to `find_competency_mentions_v2`
    (same qualifying-intent gate, same stemmed-text matching), but
    additionally consults `_V3_NEW_CONCEPTS_STEMMED` and
    `_V3_ADDITIONAL_ALIASES_STEMMED` alongside the real, unmodified v2
    tables. A tag found via `_V3_NEW_CONCEPTS_STEMMED` is recorded with
    `AliasRelation.SEMANTICALLY_EQUIVALENT` (it IS the canonical phrase
    for that new concept, by construction)."""
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
    for tag, pattern in _V3_NEW_CONCEPTS_STEMMED:
        if pattern.search(stemmed):
            found[tag] = AliasRelation.SEMANTICALLY_EQUIVALENT
    for tag, pattern, relation in _V3_ADDITIONAL_ALIASES_STEMMED:
        if pattern.search(stemmed):
            if tag not in found or relation == AliasRelation.SEMANTICALLY_EQUIVALENT:
                found[tag] = relation
    return found


def _segment_competency_tags_v3(segment: str) -> set[str]:
    stemmed = _stemmed_text_v2(segment)
    found: set[str] = set()
    for tag, pattern in _STEMMED_COMPETENCY_PATTERNS_V2:
        if pattern.search(stemmed):
            found.add(tag)
    for tag, pattern, _relation in _STEMMED_ACTIVE_ALIAS_PATTERNS_V2:
        if pattern.search(stemmed):
            found.add(tag)
    for tag, pattern in _V3_NEW_CONCEPTS_STEMMED:
        if pattern.search(stemmed):
            found.add(tag)
    for tag, pattern, _relation in _V3_ADDITIONAL_ALIASES_STEMMED:
        if pattern.search(stemmed):
            found.add(tag)
    return found


def _split_alternative_segments_v3(text: str) -> list[str] | None:
    """Byte-identical logic to v2's `_split_alternative_segments_v2`
    (duplicated, not imported, only because the real one is module-private
    and this module intentionally never edits v1/v2's own source)."""
    if not _OR_WORD.search(text):
        return None
    pieces = [p.strip() for p in re.split(r"[,;]", text) if p.strip()]
    if len(pieces) < 2:
        match = re.search(r"\bor\b", text, re.IGNORECASE)
        if match is None:
            return None
        before, after = text[: match.start()].strip(), text[match.end():].strip()
        if not before or not after:
            return None
        if _EQUIVALENT_SUBSTITUTE_V2.match(after):
            return None
        return [before, after]
    last_match = _OR_LIST_FINAL_ITEM_V2.match(pieces[-1])
    if last_match is None:
        return None
    last_remainder = last_match.group(1).strip()
    if not last_remainder or _EQUIVALENT_SUBSTITUTE_V2.match(last_remainder):
        return None
    pieces[-1] = last_remainder
    return pieces


def _claim_necessity_hint_for_section_v3(section_kind: str | None) -> "object":
    from gitscore.jobs.types import Necessity
    if section_kind is None:
        return Necessity.REQUIRED
    kind = _SectionKind[section_kind]
    if kind in (_SectionKind.UNKNOWN, _SectionKind.LEARNING):
        return None
    return _SECTION_NECESSITY_HINT.get(kind, Necessity.REQUIRED)


def extract_competency_qualifications_v3(
    text: str,
    span: SourceSpan,
    *,
    section_kind: str | None = None,
    document_has_recognized_heading: bool = False,
    has_section_context: bool = False,
) -> tuple[Qualification, ...] | DeclinedExtraction:
    """v3: v2's exact control flow (see module docstring), with the
    expanded vocabulary above substituted in at the matching step only."""
    tag_relations = find_competency_mentions_v3(text)
    if not tag_relations:
        return DeclinedExtraction(reason="no_competency_language", detail="no vocabulary or alias term matched (v3 vocabulary)")

    if any(pattern.search(text) for pattern in _NEGATION_PATTERNS):
        return DeclinedExtraction(reason="negation", detail="explicit negation of the requirement")
    if contains_narrative_cue(text) or _BROADER_NARRATIVE_SUBJECT.search(text):
        return DeclinedExtraction(reason="narrative_cue", detail="company/product or learning-opportunity narrative shape")
    if _RESPONSIBILITY_LEAD.match(text.strip()):
        return DeclinedExtraction(reason="responsibility_lead", detail="sentence opens with a bare imperative duty verb")

    tags = list(tag_relations.keys())
    if has_section_context:
        effective_hint = resolve_necessity_hint(
            text,
            _claim_necessity_hint_for_section_v3(section_kind),
            section_kind=section_kind,
            document_has_recognized_heading=document_has_recognized_heading,
        )
        necessity = infer_necessity(text, effective_hint)
    else:
        necessity = infer_necessity(text, None)
    applicability = _applicability_condition(text)
    has_and = _AND_WORD.search(text) is not None
    has_or = _OR_WORD.search(text) is not None
    exhaustive = _EXHAUSTIVE_CUE.search(text) is not None
    illustrative = _ILLUSTRATIVE_CUE.search(text) is not None

    def _confidence_for(tag: str) -> ParserConfidence:
        return _RELATION_CONFIDENCE_V3[tag_relations[tag]]

    if has_or and not has_and:
        segments = _split_alternative_segments_v3(text)
        if segments is not None and len(segments) >= 2:
            segment_tag_sets = [_segment_competency_tags_v3(seg) for seg in segments]
            all_segment_tags: set[str] = set()
            for s in segment_tag_sets:
                all_segment_tags |= s
            has_unmatched_segment = any(not s for s in segment_tag_sets)
            if has_unmatched_segment or len(all_segment_tags) > 1:
                return DeclinedExtraction(
                    reason="missing_contract",
                    detail=(
                        f"an alternative list of {len(segments)} segments names at least one "
                        f"unmatched alternative, or spans multiple competency tags "
                        f"{sorted(all_segment_tags)!r} -- no safe NormalizedReference "
                        "representation exists for a GROUP of alternatives (v3 vocabulary)."
                    ),
                    source_text=text,
                    source_span=span,
                    recognized_tags=tuple(sorted(all_segment_tags)),
                )

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
            github_observability=_competency_observability_v3(tags[0]),
        )
        return (qualification,)

    if has_or and not has_and and (exhaustive or illustrative or True):
        return DeclinedExtraction(
            reason="missing_contract",
            detail=(
                f"an alternative group of {len(tags)} competency tags {tags!r} has no safe "
                "NormalizedReference representation (v3 vocabulary, same missing-contract gap "
                "v1/v2 found)."
            ),
            source_text=text,
            source_span=span,
            recognized_tags=tuple(tags),
        )

    _MIXED_SHAPE_V3 = re.compile(r"\band\b.{0,40}\beither\b.{0,80}\bor\b", re.IGNORECASE)
    if has_and and has_or and _MIXED_SHAPE_V3.search(text):
        qualification = Qualification(
            qualification_kind=QualificationKind.TECHNICAL_COMPETENCY,
            source_text=text,
            source_span=span,
            necessity=necessity,
            applicability_condition=applicability,
            interpretation_certainty=_confidence_for(tags[0]),
            logical_composition=LogicalComposition.MIXED_UNSUPPORTED,
            normalized_reference=None,
            github_observability=_competency_observability_v3(tags[0]),
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
            github_observability=_competency_observability_v3(tag),
        )
        for tag in tags
    )
