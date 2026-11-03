"""Milestone 11-C Phase 3 -- three competency-extraction strategy
prototypes, compared against `evaluation/m11c/competency_extraction_controls.json`
BEFORE any strategy is chosen for Phase 4.

Evaluation-only. Nothing here is imported by `src/gitscore/jobs/parsing/`'s
own production modules. Reuses EXISTING, already-tested production
logic wherever applicable (`infer_necessity`, `contains_narrative_cue`)
rather than re-deriving it, per this project's own "do not duplicate
logic" principle -- new logic here is confined to what genuinely does
not exist yet (competency-term recognition, sentence-role rejection
beyond the two existing narrative cues, negation, applicability-
condition detection).

Each `extract_*(text, section_context)` function returns a tuple of
`CompetencyExtractionResult` -- zero or more per input sentence (a
sentence can yield zero when it is rejected as non-qualification,
or multiple when siblings are split).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from gitscore.jobs.parsing.narrative import contains_narrative_cue
from gitscore.jobs.parsing.necessity import infer_necessity

# ---------------------------------------------------------------------------
# Bounded competency vocabulary -- a small, curated table of (tag, pattern)
# pairs, mirroring non_technical.py's own existing design precedent
# EXACTLY (a closed, generic, non-employer-specific phrase table, never a
# role-specific parser). Not a registry; `tag` is a free competency slug,
# never promoted to a JobRequirement.concept_id (Qualification's own
# NormalizedReference.competency_tag exists for exactly this reason).
# ---------------------------------------------------------------------------

COMPETENCY_VOCABULARY: tuple[tuple[str, "re.Pattern[str]"], ...] = (
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


def find_competency_mentions(text: str) -> list[str]:
    """Every DISTINCT competency tag whose pattern matches `text`, in
    vocabulary order (not sentence order -- this prototype layer never
    needs span-level ordering, only set membership)."""
    return [tag for tag, pattern in COMPETENCY_VOCABULARY if pattern.search(text)]


# ---------------------------------------------------------------------------
# Shared structural signals -- new to this milestone, each bounded and
# generic (never employer/role-specific), reused by Options B and C.
# ---------------------------------------------------------------------------

_RESPONSIBILITY_LEAD = re.compile(
    r"^[\s\-*]*\b(?:design(?:\s+and)?|implement|build|develop|debug(?:\s+and)?|optimize|collaborate|"
    r"maintain|own|lead|drive|write|create|architect)\b",
    re.IGNORECASE,
)
"""A sentence OPENING with a bare imperative verb (after stripping any
bullet marker) -- the same grammatical shape `non_technical.py`'s own
precedent uses for a closed, generic structural signal. Matches a
RESPONSIBILITY/duty bullet ("Design and implement...", "Debug and
optimize...") -- never a claim about what the APPLICANT must already
have, which instead opens with "Experience with", "Strong
understanding of", "Candidates must", "You should", etc."""

_BROADER_NARRATIVE_SUBJECT = re.compile(
    r"\b(?:our\s+(?:team|engineers?|engineering\s+team)|we'?re\s+a\b|we\s+are\s+a\b|the\s+team)\b",
    re.IGNORECASE,
)
"""A BROADER, bounded company-narrative subject heuristic -- new in this
prototype, never added to `jobs/parsing/narrative.py` itself.
`contains_narrative_cue()` (the EXISTING, production `narrative.py`
function) only recognizes a narrower grammatical shape tuned to M10E's
own historical fixtures (confirmed: it does NOT match "Our engineering
team has... built..." or "We're a small team solving..." -- measured
directly against this milestone's own corpus, not assumed). This
pattern is deliberately a SEPARATE, ADDITIVE signal -- generic across
any employer, naming no product/company/technology -- used only by
Option C below, never modifying existing production code."""

_NEGATION_PATTERNS: tuple["re.Pattern[str]", ...] = (
    re.compile(r"\bno\s+(?:prior\s+)?(?:experience|knowledge|background)\s+with\b.{0,60}\b(?:is\s+)?(?:necessary|required|needed)\b", re.IGNORECASE),
    re.compile(r"\bnot\s+required\b", re.IGNORECASE),
    re.compile(r"\bno\s+need\s+(?:to|for)\b", re.IGNORECASE),
)
"""Explicit negation of a requirement -- new in this prototype. Bounded
to a few closed grammatical shapes, never a general 'contains the word
no' scan (which would false-suppress far too much, e.g. 'no later
than', 'no fewer than')."""

_APPLICABILITY_CUE = re.compile(r"\bunless\b|\bif\s+the\s+role\s+requires\b|\bif\s+applicable\b", re.IGNORECASE)
"""A material conditional clause -- new in this prototype. Deliberately
narrow (mirrors M11-B's own `applicability_condition` dimension, which
this prototype populates but `project_qualification()`'s own EXISTING,
unmodified safety rule routes to UnparsedClaim regardless)."""

_EXHAUSTIVE_CUE = re.compile(r"\bone\s+of\s+the\s+following\b", re.IGNORECASE)
_ILLUSTRATIVE_CUE = re.compile(r"\bsuch\s+as\b|\be\.g\.,?\b", re.IGNORECASE)
_OR_ANY_CUE = re.compile(r"\bor\b", re.IGNORECASE)


@dataclass(frozen=True)
class CompetencyExtractionResult:
    is_applicant_qualification: bool
    qualification_kind_guess: str | None = None
    competency_tags: tuple[str, ...] = ()
    necessity_guess: str | None = None  # "REQUIRED" | "PREFERRED" | None
    logical_composition_guess: str = "single"
    applicability_condition_present: bool = False
    rejection_reason: str | None = None


def _local_necessity(text: str) -> str | None:
    """Reuses the EXISTING, unmodified `infer_necessity()` with a `None`
    hint -- since a `None` hint only ever surfaces if neither the
    REQUIRED nor PREFERRED local-marker regex fires, this call isolates
    exactly the LOCAL-marker signal `infer_necessity` already
    implements, without re-deriving those two regexes a second time."""
    necessity = infer_necessity(text, None)
    return necessity.value.upper() if necessity is not None else None


def _logical_composition_for(tags: list[str], text: str) -> str:
    if len(tags) <= 1:
        return "single"
    if _EXHAUSTIVE_CUE.search(text) or _ILLUSTRATIVE_CUE.search(text) or (
        _OR_ANY_CUE.search(text) and " and " not in text.lower()
    ):
        return "or_any"
    if " and " in text.lower() and _OR_ANY_CUE.search(text):
        # an AND of an OR-group -- the one genuinely MIXED shape this
        # prototype can detect structurally (M10D Root Cause 6's own
        # "and ... either X or Y" shape).
        if re.search(r"\band\b.{0,40}\beither\b.{0,80}\bor\b", text, re.IGNORECASE):
            return "mixed_unsupported"
    return "and"


# ---------------------------------------------------------------------------
# Option A -- expanded deterministic keyword/phrase recognition.
# Deliberately NAIVE: fires on ANY competency-vocabulary match plus a
# local necessity marker, with NO sentence-role awareness at all --
# measures the real cost of skipping narrative/responsibility/learning
# rejection entirely.
# ---------------------------------------------------------------------------

def extract_option_a(text: str, section_context: str | None = None) -> tuple[CompetencyExtractionResult, ...]:
    tags = find_competency_mentions(text)
    if not tags:
        return ()
    necessity = _local_necessity(text)
    return (
        CompetencyExtractionResult(
            is_applicant_qualification=True,
            qualification_kind_guess="technical_competency",
            competency_tags=tuple(tags),
            necessity_guess=necessity,
            logical_composition_guess=_logical_composition_for(tags, text),
        ),
    )


# ---------------------------------------------------------------------------
# Option B -- structured extraction using EXISTING linguistic-context
# infrastructure (local necessity marker, the EXISTING narrative-cue
# detector) plus a bounded responsibility-lead check and negation
# rejection, all new to this milestone but NOT additionally conservative
# the way Option C is below.
# ---------------------------------------------------------------------------

def extract_option_b(text: str, section_context: str | None = None) -> tuple[CompetencyExtractionResult, ...]:
    tags = find_competency_mentions(text)
    if not tags:
        return ()

    if any(pattern.search(text) for pattern in _NEGATION_PATTERNS):
        return (CompetencyExtractionResult(is_applicant_qualification=False, rejection_reason="negation"),)
    if contains_narrative_cue(text):
        return (CompetencyExtractionResult(is_applicant_qualification=False, rejection_reason="narrative_cue"),)
    if _RESPONSIBILITY_LEAD.match(text.strip()):
        return (CompetencyExtractionResult(is_applicant_qualification=False, rejection_reason="responsibility_lead"),)

    necessity = _local_necessity(text)
    applicability = _APPLICABILITY_CUE.search(text) is not None
    return (
        CompetencyExtractionResult(
            is_applicant_qualification=True,
            qualification_kind_guess="technical_competency",
            competency_tags=tuple(tags),
            necessity_guess=necessity,
            logical_composition_guess=_logical_composition_for(tags, text),
            applicability_condition_present=applicability,
        ),
    )


# ---------------------------------------------------------------------------
# Option C -- the Option B pipeline PLUS the broader, bounded
# company-narrative heuristic (new, additive, never modifying
# narrative.py), and a stricter ambiguous-necessity rule: when NO local
# marker fires and no section-derived hint is available (section_context
# is None/unspecified here), prefer declining to a diagnostic rather
# than guessing REQUIRED.
# ---------------------------------------------------------------------------

def extract_option_c(text: str, section_context: str | None = None) -> tuple[CompetencyExtractionResult, ...]:
    tags = find_competency_mentions(text)
    if not tags:
        return ()

    if any(pattern.search(text) for pattern in _NEGATION_PATTERNS):
        return (CompetencyExtractionResult(is_applicant_qualification=False, rejection_reason="negation"),)
    if contains_narrative_cue(text) or _BROADER_NARRATIVE_SUBJECT.search(text):
        return (CompetencyExtractionResult(is_applicant_qualification=False, rejection_reason="narrative_cue"),)
    if _RESPONSIBILITY_LEAD.match(text.strip()):
        return (CompetencyExtractionResult(is_applicant_qualification=False, rejection_reason="responsibility_lead"),)

    necessity = _local_necessity(text)
    applicability = _APPLICABILITY_CUE.search(text) is not None
    return (
        CompetencyExtractionResult(
            is_applicant_qualification=True,
            qualification_kind_guess="technical_competency",
            competency_tags=tuple(tags),
            necessity_guess=necessity,
            logical_composition_guess=_logical_composition_for(tags, text),
            applicability_condition_present=applicability,
        ),
    )


STRATEGIES: dict[str, "callable"] = {
    "option_a": extract_option_a,
    "option_b": extract_option_b,
    "option_c": extract_option_c,
}
