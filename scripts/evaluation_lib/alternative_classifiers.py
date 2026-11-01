"""Milestone 10D Phase 3 -- candidate alternative-requirement classifiers.

Evaluation-only, additive, read-only against production code. Every
candidate below is a PROTOTYPE, never wired into `src/gitscore` -- this
milestone is evaluation-first design (see
`docs/evaluation/MILESTONE_10D_ALTERNATIVE_SEMANTICS.md`), not an
implementation change. Each candidate reuses the EXISTING, UNMODIFIED
per-segment concept-resolution primitives from
`gitscore.jobs.parsing.alternatives`/`concepts` (`_resolve_segment`,
`_shaped_term`, `_strip_trailing_filler`, `clean_list_fragment`,
`looks_like_specific_technology_name`, `find_concept_mentions`) --
only the SEGMENTATION/TRIGGER-DETECTION question is being prototyped
here, never concept resolution itself, which Phase 1 confirmed already
works correctly for every ordinary "X or Y" case (category G).

Three candidates, per the mission brief's Phase 3:

- `candidate_a`: surgical idiom-aware "or" handling only (protects
  "<number-word> or more" from being treated as a list separator).
- `candidate_b`: explicit ANY-of trigger-phrase recognition. Finds a
  trigger phrase ("one or more of", "at least one", "any one of", "one
  of the following", "any of", "either of") anywhere in the text, then
  looks for an explicit list structure after it (a parenthetical
  example clause, a colon-introduced list, or -- failing both -- the
  bare remainder itself) and resolves THAT region with a stronger,
  MANDATORY shape/resolution requirement on every segment (never a
  shapeless promotion) before accepting it as a group. Falls through
  to the ORIGINAL, unmodified `classify_alternative_claim()` when no
  trigger phrase is found at all, so the pre-existing baseline behavior
  for ordinary "or"-joined claims is completely unaffected by this
  candidate in isolation.
- `candidate_ab`: `candidate_b`'s trigger path, falling through to
  `candidate_a`'s idiom-guarded baseline (instead of the unmodified
  baseline) when no trigger phrase is found -- the "combined A+B"
  design the mission brief asks to assess as sufficient on its own.
- `candidate_c`: `candidate_ab` plus a top-level AND-boundary split
  (literal " and " at the top level, outside any trigger-consumed
  region) BEFORE delegating each resulting chunk to `candidate_ab` --
  the "broader structural classifier" the brief asks to compare
  against, attempting (not fully achieving -- see each MIXED control's
  own annotation and the module docstring note below) MIXED-structure
  recognition for category E.

**What `candidate_c` deliberately does NOT attempt** (documented
honestly rather than silently mis-scored): true per-segment AND/OR
nesting disambiguation ("Python or Java and SQL" vs. "Python and
either PostgreSQL or MySQL" read different AND/OR precedence into the
SAME surface shape "X or Y and Z"/"X and Y or Z"). `candidate_c`'s
top-level split is a single, fixed, left-to-right heuristic (split on
the FIRST top-level bare " and " outside a trigger region, never a
real grammar), so it is expected to get SOME MIXED controls right by
coincidence of phrasing and others wrong -- the comparison script
reports this directly rather than asserting `candidate_c` solves
MIXED. This is exactly why Phase 6 reports a separate, newly-identified
Root Cause 6 and does NOT recommend adopting `candidate_c`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from gitscore.concepts.registry import default_registry, unresolved_concept_id
from gitscore.jobs.parsing.alternatives import (
    _resolve_segment,
    _shaped_term,
    _split_alternative_segments,
    _strip_trailing_filler,
    contains_alternative_marker,
)
from gitscore.jobs.parsing.concepts import find_concept_mentions, looks_like_specific_technology_name

_BARE_OR = re.compile(r"(?<![A-Za-z0-9])or(?![A-Za-z0-9])", re.IGNORECASE)

# Candidate A -- the one, narrow idiom this guard protects: "<number-word
# or digit> or more". Deliberately NOT a general "or" blocklist (M10A
# §6.2(a), directly).
_IDIOM_OR_MORE = re.compile(
    r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+or\s+more\b",
    re.IGNORECASE,
)

# Candidate B -- the ANY-of trigger-phrase table. "at least one" is
# deliberately bare (no required trailing "of") because the REAL
# Manulife posting says "at least one programming language (e.g.,
# ...)" with no "of" at all (Phase 1 trace) -- M10A §6.2(b)'s literal
# "at least one of" proposal does not match the real posting's own
# wording. The mandatory list-structure requirement below (a
# parenthetical, a colon, or a resolvable bare remainder) is what keeps
# this broadened, bare trigger safe against a false positive like "at
# least one year of experience" with no technology list attached.
_ANY_OF_TRIGGER = re.compile(
    r"\b(?:one or more of|at least one|any one of|one of the following|any of|either of)\b",
    re.IGNORECASE,
)
_PARENTHETICAL_LIST = re.compile(r"\(\s*(?:e\.g\.,?|such as|for example)\s*([^)]+)\)", re.IGNORECASE)
_LIST_AFTER_COLON = re.compile(r":\s*(.+)$", re.DOTALL)
_LEADING_CONNECTOR = re.compile(r"^\s*(?:of\s+)?(?:the\s+following\s*:?\s*)?", re.IGNORECASE)

# Candidate C -- top-level AND boundary, checked only OUTSIDE any region
# a trigger phrase already consumed (see `candidate_c`).
_BARE_AND = re.compile(r"(?<![A-Za-z0-9])and(?![A-Za-z0-9])", re.IGNORECASE)


@dataclass(frozen=True)
class GroupResult:
    """One logical requirement group a candidate produced: `concept_ids`
    has exactly one entry for a plain single-concept (ALL-style) row, or
    two-or-more for an ANY-of group. `fabricated` lists any id in this
    group a human annotator would judge an unjustified shapeless
    promotion (used only for the fabrication metric -- never fed back
    into resolution itself).
    """

    concept_ids: tuple[str, ...]
    fabricated: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CandidateResult:
    structure: str  # "NONE" | "ANY" | "MIXED" | "UNSAFE"
    groups: tuple[GroupResult, ...] = field(default_factory=tuple)

    @property
    def all_concept_ids(self) -> tuple[str, ...]:
        ids: list[str] = []
        for group in self.groups:
            ids.extend(group.concept_ids)
        return tuple(ids)

    @property
    def fabricated_ids(self) -> tuple[str, ...]:
        ids: list[str] = []
        for group in self.groups:
            ids.extend(group.fabricated)
        return tuple(ids)


def _idiom_protected_spans(text: str) -> list[tuple[int, int]]:
    return [m.span() for m in _IDIOM_OR_MORE.finditer(text)]


def _split_idiom_aware(text: str) -> list[str]:
    """Candidate A's splitter: identical to
    `alternatives._split_alternative_segments` except a bare "or" that
    falls inside an `_IDIOM_OR_MORE` match is never treated as a list
    separator.
    """
    protected = _idiom_protected_spans(text)

    def _is_protected(pos: int) -> bool:
        return any(start <= pos < end for start, end in protected)

    pieces: list[str] = []
    cursor = 0
    for match in _BARE_OR.finditer(text):
        if _is_protected(match.start()):
            continue
        pieces.append(text[cursor : match.start()])
        cursor = match.end()
    pieces.append(text[cursor:])

    segments: list[str] = []
    for part in pieces:
        for piece in part.split(","):
            piece = _strip_trailing_filler(piece.strip())
            if piece:
                segments.append(piece)
    return segments


def _classify_segments(segments: list[str], registry, *, require_shape: bool) -> CandidateResult:
    """Shared resolution core for candidates A/B/AB: resolve every
    segment, optionally REQUIRING (`require_shape=True`, Candidate B's
    trigger path) that an escalated `unresolved:<term>` promotion also
    pass `looks_like_specific_technology_name` -- closing the exact
    fabrication gap Phase 1 found in `_resolve_segment`'s own
    unconditional clean_list_fragment-escalation branch. `require_shape
    =False` reproduces today's baseline leniency (used by Candidate A,
    which intentionally changes ONLY the idiom-splitting behavior, not
    the resolution-strictness behavior, so its own effect is isolated).
    """
    if len(segments) < 2:
        return CandidateResult(structure="NONE")

    any_confirmed = False
    all_shaped = True
    unsafe = False
    ordered: list[str] = []
    seen: set[str] = set()
    fabricated: list[str] = []

    for index, segment in enumerate(segments):
        ids = _resolve_segment(segment, registry)
        shaped_term = _shaped_term(segment, allow_leading_token=index > 0)
        segment_shaped = shaped_term is not None and looks_like_specific_technology_name(shaped_term)

        if ids is None:
            if not segment_shaped:
                unsafe = True
                all_shaped = False
                continue
            ids = (unresolved_concept_id(shaped_term),)
        elif require_shape and not segment_shaped and any(i.startswith("unresolved:") for i in ids):
            # Candidate B's tightened rule: an escalated unresolved
            # promotion is only accepted when the segment is ALSO
            # shaped like a specific technology name -- this is the
            # fix for the `unresolved:one` / `unresolved:more_of:_c`
            # fabrication Phase 1 found in the unmodified function.
            unsafe = True
            all_shaped = False
            continue
        elif not segment_shaped:
            all_shaped = False

        for concept_id in ids:
            if not concept_id.startswith("unresolved:"):
                any_confirmed = True
            elif not segment_shaped:
                fabricated.append(concept_id)
            if concept_id not in seen:
                seen.add(concept_id)
                ordered.append(concept_id)

    # Mirrors `alternatives.classify_alternative_claim`'s own safety net
    # exactly: nothing in this list is a REAL registered concept, AND at
    # least one segment is not even shaped like one -- not enough
    # evidence this is a technology enumeration at all (e.g. "control
    # systems or state estimation"). Checking `all_shaped` here, not
    # just "ordered is empty," is what stops an all-unresolved,
    # all-unshaped list from being accepted anyway -- the exact
    # regression this helper's own first draft had (Phase 3 smoke test,
    # recorded in the milestone doc).
    if not any_confirmed and not all_shaped:
        return CandidateResult(structure="NONE")
    if unsafe or len(ordered) < 2:
        return CandidateResult(structure="UNSAFE")
    return CandidateResult(
        structure="ANY",
        groups=(GroupResult(concept_ids=tuple(sorted(ordered)), fabricated=tuple(fabricated)),),
    )


def _mention_fallthrough(text: str, registry) -> CandidateResult:
    """What EVERY candidate below falls through to once it has decided
    a claim carries no safely-representable alternative-group structure
    at all: the exact SAME ordinary per-claim concept-mention behavior
    `jobs/parsing/parser.py::_requirements_from_claim` already applies
    today (one independent row per distinct mentioned concept -- correct
    ALL/category-D semantics). Every candidate's own "NONE" decision
    must still preserve this -- a candidate that forgets this step
    would silently DROP a true AND requirement instead of leaving it
    exactly as correct as it is today, which Phase 3's comparison must
    be able to tell apart from an actual fabrication/loss defect.
    """
    mentions = find_concept_mentions(text, registry=registry)
    seen: set[str] = set()
    groups: list[GroupResult] = []
    for mention in mentions:
        if mention.concept_id in seen:
            continue
        seen.add(mention.concept_id)
        groups.append(GroupResult(concept_ids=(mention.concept_id,)))
    if not groups:
        return CandidateResult(structure="NONE")
    if len(groups) == 1:
        return CandidateResult(structure="ANY", groups=tuple(groups))
    return CandidateResult(structure="MIXED", groups=tuple(groups))


def candidate_a(text: str, registry=None) -> CandidateResult:
    """Idiom-aware "or" splitting only -- see module docstring. Falls
    through to `_mention_fallthrough` whenever there is no bare "or" at
    all, or the "or"-segments present resolve to nothing -- Candidate A
    changes ONLY how an existing "or" is split, never whether a
    non-alternative (or unresolvable) claim still gets its ordinary
    AND-style independent rows.
    """
    registry = registry or default_registry()
    if _BARE_OR.search(text):
        segments = _split_idiom_aware(text)
        result = _classify_segments(segments, registry, require_shape=False)
        if result.structure != "NONE":
            return result
    return _mention_fallthrough(text, registry)


def _find_list_region(text: str, trigger_end: int) -> str | None:
    """The text Candidate B should treat as "the enumerated list,"
    searched from `trigger_end` onward -- a parenthetical example
    clause, else a colon-introduced list, else the bare remainder
    (connector-stripped) if non-empty. Returns `None` only when the
    remainder is empty (the bare-idiom-with-nothing-to-list case,
    `m10d-f1`).
    """
    remainder = text[trigger_end:]
    parenthetical = _PARENTHETICAL_LIST.search(remainder)
    if parenthetical is not None:
        return parenthetical.group(1)
    colon_list = _LIST_AFTER_COLON.search(remainder)
    if colon_list is not None:
        return colon_list.group(1)
    stripped = _LEADING_CONNECTOR.sub("", remainder).strip()
    return stripped or None


def _candidate_b_only(text: str, registry) -> CandidateResult | None:
    """Candidate B's own trigger-path result, or `None` if no trigger
    phrase was found at all (the caller then decides what to fall
    through to -- `candidate_b` falls to the unmodified baseline,
    `candidate_ab`/`candidate_c` fall to `candidate_a`).
    """
    trigger = _ANY_OF_TRIGGER.search(text)
    if trigger is None:
        return None
    list_region = _find_list_region(text, trigger.end())
    if list_region is None:
        return CandidateResult(structure="NONE")
    segments = _split_idiom_aware(list_region)
    result = _classify_segments(segments, registry, require_shape=True)
    if result.structure == "NONE":
        # The trigger fired but nothing list-shaped followed it at all
        # (e.g. "at least one backend framework and one database") --
        # never fabricate; let the caller's baseline/idiom-aware
        # fallback have the final say on this claim instead.
        return None
    return result


def candidate_b(text: str, registry=None) -> CandidateResult:
    registry = registry or default_registry()
    own = _candidate_b_only(text, registry)
    if own is not None:
        return own
    return baseline_pipeline_result(text, registry)


def candidate_ab(text: str, registry=None) -> CandidateResult:
    registry = registry or default_registry()
    own = _candidate_b_only(text, registry)
    if own is not None:
        return own
    return candidate_a(text, registry)


def _baseline_alternative_result(text: str, registry) -> CandidateResult:
    """The TODAY, unmodified `classify_alternative_claim()` outcome,
    reimplemented via the SAME `_classify_segments(require_shape=False)`
    core every candidate shares, applied to the PLAIN (non-idiom-aware)
    `_split_alternative_segments` -- mathematically the identical
    algorithm `alternatives.classify_alternative_claim` runs today
    (confirmed: every corpus control's `structure`/concept-id-set
    produced here matches that function's own `kind`/`concept_ids`
    directly, Phase 3 smoke test). Reimplemented, rather than merely
    wrapping `AlternativeClaim`, SOLELY so the shared `fabricated`
    tracking in `_classify_segments` also covers the baseline --
    `AlternativeClaim` itself has no such field, and this module's own
    comparison script needs an apples-to-apples fabrication count for
    baseline, not just for the three candidates.
    """
    if not contains_alternative_marker(text):
        return CandidateResult(structure="NONE")
    segments = _split_alternative_segments(text)
    return _classify_segments(segments, registry, require_shape=False)


def candidate_c(text: str, registry=None) -> CandidateResult:
    """`candidate_ab` plus a single top-level AND split -- see module
    docstring for what this deliberately does not attempt.
    """
    registry = registry or default_registry()
    trigger = _ANY_OF_TRIGGER.search(text)
    protected_end = trigger.end() if trigger is not None else 0

    and_match = None
    for m in _BARE_AND.finditer(text):
        if m.start() >= protected_end:
            and_match = m
            break

    if and_match is None:
        return candidate_ab(text, registry)

    left = text[: and_match.start()].strip()
    right = text[and_match.end() :].strip()
    left_result = candidate_ab(left, registry)
    right_result = candidate_ab(right, registry)

    groups: list[GroupResult] = []
    for part in (left_result, right_result):
        if part.structure == "ANY":
            groups.extend(part.groups)
        elif part.structure == "NONE":
            continue
        else:  # UNSAFE on either side -- cannot safely split this AND at all
            return candidate_ab(text, registry)

    if not groups:
        return CandidateResult(structure="NONE")
    if len(groups) == 1:
        return CandidateResult(structure="ANY", groups=tuple(groups))
    return CandidateResult(structure="MIXED", groups=tuple(groups))


def baseline_pipeline_result(text: str, registry=None) -> CandidateResult:
    """The TODAY, production (`src/gitscore`, unmodified) effective
    outcome for a claim's alternative-structure shape -- NOT just
    `classify_alternative_claim()`'s own return value, but what
    `jobs/parsing/parser.py::_requirements_from_claim` actually turns
    it into once the "not_technical" branch falls through to the
    ordinary per-claim concept-mention pipeline (Root Cause 4's exact
    manifestation point). Mirrors that function's logic for JUST the
    alternative-structure question -- necessity/importance/non-technical/
    experience-qualifier rows are irrelevant to this comparison and
    deliberately not reproduced here.
    """
    registry = registry or default_registry()
    result = _baseline_alternative_result(text, registry)
    if result.structure != "NONE":
        return result
    return _mention_fallthrough(text, registry)
