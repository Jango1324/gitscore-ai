"""Milestone 10E Phase 3 -- candidate narrative-vs-qualification classifiers.

Evaluation-only, additive, read-only against production code. Every
candidate below is a PROTOTYPE, never wired into `src/gitscore` -- this
milestone is evaluation-first design (see
`docs/evaluation/MILESTONE_10E_NARRATIVE_REQUIREMENT_SEMANTICS.md`), not
an implementation change. Mirrors the M10D precedent
(`scripts/evaluation_lib/alternative_classifiers.py`): reuse the EXISTING,
UNMODIFIED per-claim resolution primitives (`infer_necessity`,
`classify_alternative_claim`, `find_concept_mentions`,
`find_non_technical_match`, `find_experience_qualifier`,
`find_conservative_unknown_terms`, `observability_for_*`) -- only the
ELIGIBILITY question (should this claim be allowed to become a scored
`JobRequirement` at all, given WHERE it came from and WHAT it says) is
being prototyped here, never concept resolution or necessity-marker
precedence itself, both of which Phase 1 confirmed already work
correctly once a claim is admitted.

**The root problem, confirmed by direct trace (Phase 1/2):** today,
`segmentation.py`'s `Claim.necessity_hint` collapses several genuinely
different section-origin situations into the SAME signal.
`_SECTION_NECESSITY_HINT` maps `RESPONSIBILITY` to `Necessity.REQUIRED`
identically to a real `REQUIRED` section, and `current_kind is None`
(nothing recognized YET) is handled by `.get(current_kind,
Necessity.REQUIRED)`'s own default -- identically whether `None` means
"this whole posting has no headings at all" (correct to treat
heuristically, Milestone 6B's original, still-valid policy) or "this is
narrative prose preceding the SAME document's own later, real,
recognized sections" (SOTI's actual shape, where the default fabricates
a requirement). `jobs/parsing/parser.py::_requirements_from_claim` then
runs the SAME detector pipeline (alternative-group classification,
concept mentions, `non_technical.py` patterns) regardless of which of
these a claim's necessity_hint came from, so a `RESPONSIBILITY` bullet
that happens to match `non_technical.py`'s `collaborat*` pattern
(Manulife) or happens to NAME a technology at all (`m10e-d3`/`d4`,
"Develop backend services using Java") becomes a scored, REQUIRED
`JobRequirement` exactly as if the SAME sentence had appeared under a
real `Requirements:` heading.

Three candidates, per the mission brief's Phase 3:

- `candidate_a`: narrow, text-pattern-only exclusion. Recognizes a small,
  generic (never role-specific) set of LEARNING-narrative and
  COMPANY-narrative grammatical cues anywhere in a claim's own text, and
  suppresses JobRequirement construction (forces the necessity hint to
  `None`, the SAME "diagnostic only" outcome `UNKNOWN`/`LEARNING`
  sections already produce) whenever one fires AND the claim carries no
  local REQUIRED/PREFERRED marker of its own. Entirely independent of
  section origin -- does not know or care whether a claim came from a
  `RESPONSIBILITY` section, an unrecognized heading, or no section at
  all.
- `candidate_b`: section-origin-aware. Exposes the REAL `_SectionKind`
  per claim (not just the lossy `necessity_hint` derived from it) via a
  parallel segmenter (`segment_with_section_kind`, below) that reuses
  every one of `segmentation.py`'s existing private primitives
  unmodified. A claim is QUALIFICATION-ELIGIBLE (allowed through the
  unmodified detector pipeline) iff: (a) its own text carries a local
  REQUIRED/PREFERRED marker (`infer_necessity`'s existing, unconditional
  precedence -- unchanged), OR (b) its section is a genuine `REQUIRED`
  or `PREFERRED` heading, OR (c) `current_kind is None` AND the WHOLE
  document has NO recognized heading anywhere at all (preserves
  Milestone 6B's original heuristic-gated default for a genuinely
  unsectioned posting, byte-for-byte). Every other case
  (`RESPONSIBILITY`, `LEARNING`, `UNKNOWN`, or `None` as a PREAMBLE
  before the document's own later real sections) is NOT eligible by
  default -- routed to the exact same necessity=`None` diagnostic-only
  outcome `UNKNOWN`/`LEARNING` already produce today, unless (a) grants
  it anyway.
- `candidate_c`: `candidate_b`'s section-origin gate, PLUS
  `candidate_a`'s own grammatical-cue check applied as a SECOND,
  independent veto even inside an otherwise-eligible context (a real
  `REQUIRED`/`PREFERRED` section, or the (c) whole-document-unsectioned
  fallback) -- defense in depth against a learning/company-narrative
  sentence that happens to sit inside a real qualifications section
  (document-authoring noise Phase 2's category G/H anticipates), without
  ever overriding an explicit local marker (`candidate_a`'s own "no
  local marker" condition is preserved exactly).

**What NONE of these candidates touch:** concept resolution
(`find_concept_mentions`, `classify_alternative_claim`'s per-segment
logic), the matcher's `NOT_ASSESSABLE` decision table, dedup, or
`non_technical.py`'s category table itself. All three operate at exactly
ONE point -- the necessity hint fed into the UNCHANGED downstream
pipeline -- mirroring M10D's own discipline of prototyping only the
decision the milestone is actually about.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from gitscore.concepts.registry import default_registry
from gitscore.jobs.models import JobRequirement, SourceSpan
from gitscore.jobs.parsing.alternatives import classify_alternative_claim
from gitscore.jobs.parsing.concepts import find_concept_mentions, find_conservative_unknown_terms
from gitscore.jobs.parsing.experience import find_experience_qualifier
from gitscore.jobs.parsing.importance import infer_importance
from gitscore.jobs.parsing.necessity import _PREFERRED_MARKER, _REQUIRED_MARKER, infer_necessity
from gitscore.jobs.parsing.non_technical import find_non_technical_match
from gitscore.jobs.parsing.observability import observability_for_non_technical, observability_for_technical
from gitscore.jobs.parsing.parser import _unresolved_requirement_signal
from gitscore.jobs.parsing.segmentation import (
    _BULLET_PREFIX,
    _SECTION_NECESSITY_HINT,
    _classify_heading_line,
    _line_content_span,
    _looks_like_requirement,
    _SectionKind,
    _split_sentences,
    Claim,
)
from gitscore.jobs.types import Necessity

# ---------------------------------------------------------------------------
# Shared: a parallel segmenter that preserves the REAL `_SectionKind` label
# per claim (never just the lossy, already-collapsed `necessity_hint`).
# Reuses every one of segmentation.py's existing private primitives
# UNMODIFIED -- only the orchestration loop is duplicated, exactly to
# attach one extra label segment_description() itself has no reason to
# expose publicly (M10D's own precedent for this kind of evaluation-only
# duplication, `alternative_classifiers.py`'s own module docstring).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClaimWithOrigin:
    claim: Claim
    section_kind: str  # _SectionKind member name, or "NONE"


def segment_with_section_kind(description: str) -> tuple[ClaimWithOrigin, ...]:
    claims: list[ClaimWithOrigin] = []
    current_kind: _SectionKind | None = None

    for line_match in re.finditer(r"[^\r\n]+", description):
        line = line_match.group()
        line_start = line_match.start()

        content_span = _line_content_span(line, line_start)
        if content_span is None:
            continue
        content_start, content_end = content_span
        content = description[content_start:content_end]

        classified = _classify_heading_line(line, content)
        if classified is not None:
            current_kind = classified
            continue

        if current_kind is _SectionKind.SKIP:
            continue

        necessity_hint: Necessity | None
        if current_kind in (_SectionKind.UNKNOWN, _SectionKind.LEARNING):
            necessity_hint = None
        else:
            necessity_hint = _SECTION_NECESSITY_HINT.get(current_kind, Necessity.REQUIRED)
        in_recognized_section = current_kind in (
            _SectionKind.REQUIRED, _SectionKind.PREFERRED, _SectionKind.RESPONSIBILITY,
        )
        kind_name = current_kind.name if current_kind is not None else "NONE"

        for sent_start, sent_end in _split_sentences(content, description, content_start):
            sentence = description[sent_start:sent_end]
            if not in_recognized_section and not _looks_like_requirement(sentence):
                continue
            claim = Claim(text=sentence, start=sent_start, end=sent_end, necessity_hint=necessity_hint)
            claims.append(ClaimWithOrigin(claim=claim, section_kind=kind_name))

    return tuple(claims)


def document_has_any_recognized_heading(description: str) -> bool:
    """Milestone 10E -- the fact Candidate B/C's case (c) needs: does THIS
    document have a recognized heading ANYWHERE, distinguishing "no
    section at all" (trust the Milestone 6B heuristic default exactly as
    today) from "no section YET, but the document has real structure
    later" (SOTI's actual shape -- the default must not fabricate there).
    """
    for line_match in re.finditer(r"[^\r\n]+", description):
        line = line_match.group()
        line_start = line_match.start()
        content_span = _line_content_span(line, line_start)
        if content_span is None:
            continue
        content_start, content_end = content_span
        content = description[content_start:content_end]
        if _classify_heading_line(line, content) is not None:
            return True
    return False


# ---------------------------------------------------------------------------
# Candidate A -- narrow, text-pattern-only narrative exclusion.
# ---------------------------------------------------------------------------

# Generic (never role-specific) grammatical cues that a sentence is
# describing what the EMPLOYER will teach/expose the candidate to,
# phrased broadly enough to catch SOTI's own real wording ("the
# technologies you learn... range from... deepening your knowledge of
# databases by leveraging SQL") without being a role/technology-specific
# blocklist.
_LEARNING_NARRATIVE_CUE = re.compile(
    r"\byou(?:'ll| will) (?:learn|gain|have the opportunity to)\b|"
    r"\bthe (?:technologies|skills|tools) you(?:'ll| will)? learn\b|"
    r"\byou may (?:get an opportunity to )?learn\b|"
    r"\bdeepen(?:ing)? your knowledge\b|\bgain (?:an? )?(?:understanding|exposure)\b",
    re.IGNORECASE,
)

# Generic first-person-plural company/product narrative cues ("our
# product uses X", "we have used Y", "our engineers develop Z") -- never
# a specific company or technology name, so this stays a structural
# pattern, not a per-employer exception table.
_COMPANY_NARRATIVE_CUE = re.compile(
    r"\bour (?:product|platform|company|engineers?|team)\b[^.?!]*\b"
    r"(?:uses?|use|built|builds?|develops?|leverages?)\b|"
    r"\bwe(?:'ve| have)? (?:used|built|developed?|leverage[ds]?)\b",
    re.IGNORECASE,
)


def _has_local_marker(text: str) -> bool:
    return _REQUIRED_MARKER.search(text) is not None or _PREFERRED_MARKER.search(text) is not None


def candidate_a_hint(claim_text: str, original_hint: Necessity | None) -> Necessity | None:
    if _has_local_marker(claim_text):
        return original_hint
    if _LEARNING_NARRATIVE_CUE.search(claim_text) or _COMPANY_NARRATIVE_CUE.search(claim_text):
        return None
    return original_hint


# ---------------------------------------------------------------------------
# Candidate B -- section-origin-aware eligibility.
# ---------------------------------------------------------------------------


def candidate_b_hint(
    claim_text: str,
    original_hint: Necessity | None,
    section_kind: str,
    doc_has_heading: bool,
) -> Necessity | None:
    if _has_local_marker(claim_text):
        return original_hint
    if section_kind in ("REQUIRED", "PREFERRED"):
        return original_hint
    if section_kind == "NONE" and not doc_has_heading:
        return original_hint
    return None


# ---------------------------------------------------------------------------
# Candidate C -- Candidate B's gate, plus Candidate A's cue as a second,
# independent veto (never an override of an explicit local marker).
# ---------------------------------------------------------------------------


def candidate_c_hint(
    claim_text: str,
    original_hint: Necessity | None,
    section_kind: str,
    doc_has_heading: bool,
) -> Necessity | None:
    if _has_local_marker(claim_text):
        return original_hint
    gated = candidate_b_hint(claim_text, original_hint, section_kind, doc_has_heading)
    if gated is None:
        return None
    if _LEARNING_NARRATIVE_CUE.search(claim_text) or _COMPANY_NARRATIVE_CUE.search(claim_text):
        return None
    return gated


# ---------------------------------------------------------------------------
# Shared pipeline: identical to `parser.py::_requirements_from_claim`,
# reusing every detector UNCHANGED, parameterized only by WHICH necessity
# hint a given candidate (or the unmodified baseline) computed. This is
# the exact production function's logic, reproduced here ONLY so a
# candidate's hint can be substituted before necessity inference runs --
# `infer_necessity`, `classify_alternative_claim`, `find_concept_mentions`,
# `find_non_technical_match`, `find_experience_qualifier`,
# `find_conservative_unknown_terms`, `observability_for_*` are all called
# EXACTLY as `parser.py` calls them, unmodified.
# ---------------------------------------------------------------------------


def requirements_for_hint(claim: Claim, hint: Necessity | None, registry=None) -> list[JobRequirement]:
    registry = registry or default_registry()
    necessity = infer_necessity(claim.text, hint)
    if necessity is None:
        return []
    importance = infer_importance(claim.text, necessity)
    span = SourceSpan(claim.start, claim.end)

    alternative = classify_alternative_claim(claim.text, registry=registry)

    if alternative.kind == "technical":
        return [
            JobRequirement(
                original_text=claim.text,
                necessity=necessity,
                importance=importance,
                github_observability=observability_for_technical(),
                alternative_concept_ids=alternative.concept_ids,
                source_span=span,
            )
        ]

    if alternative.kind == "unsafe":
        return [
            JobRequirement(
                original_text=claim.text,
                necessity=necessity,
                importance=importance,
                github_observability=observability_for_non_technical("alternative_requirement"),
                concept_id=None,
                category="alternative_requirement",
                source_span=span,
            )
        ]

    requirements: list[JobRequirement] = []
    safe_mentions = find_concept_mentions(claim.text, registry=registry)
    seen_concept_ids: set[str] = set()
    for mention in safe_mentions:
        if mention.concept_id in seen_concept_ids:
            continue
        seen_concept_ids.add(mention.concept_id)
        concept = registry.get(mention.concept_id)
        requirements.append(
            JobRequirement(
                original_text=claim.text,
                necessity=necessity,
                importance=importance,
                github_observability=observability_for_technical(),
                concept_id=mention.concept_id,
                category=concept.category if concept is not None else None,
                source_span=span,
            )
        )

    for term in find_conservative_unknown_terms(claim.text, safe_mentions):
        from gitscore.concepts.registry import unresolved_concept_id

        concept_id = unresolved_concept_id(term)
        if concept_id in seen_concept_ids:
            continue
        seen_concept_ids.add(concept_id)
        requirements.append(
            JobRequirement(
                original_text=claim.text,
                necessity=necessity,
                importance=importance,
                github_observability=observability_for_technical(),
                concept_id=concept_id,
                category=None,
                source_span=span,
            )
        )

    if find_experience_qualifier(claim.text) is not None:
        requirements.append(
            JobRequirement(
                original_text=claim.text,
                necessity=necessity,
                importance=importance,
                github_observability=observability_for_non_technical("experience"),
                concept_id=None,
                category="experience",
                source_span=span,
            )
        )

    non_technical = find_non_technical_match(claim.text)
    if non_technical is not None:
        category, _ = non_technical
        requirements.append(
            JobRequirement(
                original_text=claim.text,
                necessity=necessity,
                importance=importance,
                github_observability=observability_for_non_technical(category),
                concept_id=None,
                category=category,
                source_span=span,
            )
        )

    if not requirements and _unresolved_requirement_signal(claim.text):
        requirements.append(
            JobRequirement(
                original_text=claim.text,
                necessity=necessity,
                importance=importance,
                github_observability=observability_for_non_technical("unresolved_requirement"),
                concept_id=None,
                category="unresolved_requirement",
                source_span=span,
            )
        )

    return requirements


@dataclass(frozen=True)
class CandidateOutcome:
    requirements: tuple[JobRequirement, ...]
    section_kind: str
    hint_used: Necessity | None


def run_candidate(description: str, candidate: str) -> tuple[CandidateOutcome, ...]:
    """Run `candidate` ('baseline' | 'a' | 'b' | 'c') over every claim
    `segment_with_section_kind` produces for `description`, returning one
    `CandidateOutcome` per claim.
    """
    registry = default_registry()
    doc_has_heading = document_has_any_recognized_heading(description)
    outcomes: list[CandidateOutcome] = []
    for origin in segment_with_section_kind(description):
        claim = origin.claim
        if candidate == "baseline":
            hint = claim.necessity_hint
        elif candidate == "a":
            hint = candidate_a_hint(claim.text, claim.necessity_hint)
        elif candidate == "b":
            hint = candidate_b_hint(claim.text, claim.necessity_hint, origin.section_kind, doc_has_heading)
        elif candidate == "c":
            hint = candidate_c_hint(claim.text, claim.necessity_hint, origin.section_kind, doc_has_heading)
        else:
            raise ValueError(candidate)
        reqs = tuple(requirements_for_hint(claim, hint, registry=registry))
        outcomes.append(CandidateOutcome(requirements=reqs, section_kind=origin.section_kind, hint_used=hint))
    return tuple(outcomes)
