"""Milestone 6B.1 -- structured alternative/OR requirement detection.

**Supersedes Milestone 6B's Option A.** 6B initially represented an
alternative-shaped claim ("Python or Go") as one conservative,
non-technical `JobRequirement` (`concept_id=None`,
`category="alternative_requirement"`) with NO structured concepts at
all -- correct about never misrepresenting OR as AND, but it threw away
exactly the information a future matcher needs (`supported(Python) OR
supported(Go)`), forcing the matcher to re-parse `original_text` itself.
That was a genuine gap, not a matter of taste: the parser owns text
interpretation; the matcher must consume structured semantics. Milestone
6B.1 fixes this with `JobRequirement.alternative_concept_ids` (see that
field's docstring, `jobs/models.py`) -- this module is what POPULATES
it.

**Three possible outcomes for a claim**, returned as an `AlternativeClaim`:

- `kind="not_technical"` -- no standalone "or" at all, OR an "or" whose
  segments contain NO recognizable technology anywhere (e.g. "Bachelor's
  degree ... or a related field", "3+ years experience or equivalent
  education"). The caller must run the claim through the NORMAL
  per-claim pipeline (concept mentions, experience qualifier,
  non-technical patterns) exactly as if no "or" were present at all --
  this is what stops "or" alone from ever manufacturing a fake technical
  alternative group out of ordinary HR boilerplate.
- `kind="technical"`, `concept_ids` populated (>= 2, sorted, deduped) --
  every alternative was safely represented, either as a real registered
  concept or a conservatively-promoted `unresolved:<term>`. The caller
  builds ONE `JobRequirement` with `alternative_concept_ids=concept_ids`.
- `kind="unsafe"` -- at least one segment IS confirmed technical context
  (a sibling segment resolved) but at least one OTHER segment could not
  be safely represented (failed the same shape/stopword check
  `find_conservative_unknown_terms` already uses) or fewer than two
  distinct concepts survived. The caller falls back to the OLD Milestone
  6B non-technical placeholder (`category="alternative_requirement"`,
  `concept_id=None`) rather than either silently dropping an alternative
  or recklessly inventing one -- "do not manufacture unresolved IDs
  recklessly" wins over forcing a clean structured group.

Per-segment resolution is a TWO-STEP escalation, not a single lookup:
1. `find_concept_mentions()` (Milestone 6B, prose-SAFE aliases only) --
   handles a longer segment where a known concept is embedded in
   surrounding words ("experience deploying models to AWS").
2. Only if step 1 finds nothing: clean the segment down to its core term
   (`concepts.clean_list_fragment()`) and try `resolve_concept()` against
   the FULL alias set (not just prose-safe aliases). This is a
   deliberate, narrow escalation: a segment produced by splitting on a
   confirmed "X or Y" enumeration -- where at least one sibling already
   resolved -- is closer to an isolated, structured token (like a
   package.json key) than to arbitrary free prose, which is exactly the
   context Milestone 5D.1's alias-safety restriction was never meant to
   apply to. This is what lets "Go" in "Python or Go" resolve to the
   real `language.go` concept (bare "go" is `readme_unsafe` for FREE-FORM
   prose scanning, §18.4, but this is not that) instead of falling back
   to `unresolved:go`. If step 2 also fails, the cleaned term is either
   promoted to `unresolved:<term>` (shape check passes) or the segment is
   marked unsafe (shape check fails).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from gitscore.concepts.registry import default_registry, resolve_concept, unresolved_concept_id
from gitscore.jobs.parsing.concepts import clean_list_fragment, find_concept_mentions, leading_token

_ALTERNATIVE_MARKER = re.compile(r"(?<![A-Za-z0-9])or(?![A-Za-z0-9])", re.IGNORECASE)

# The trailing necessity/filler clause of a claim like "Go required" or
# "Go experience" or "ROCm preferred" (the LAST OR-segment of "Python or
# Go required" / "Python or Go experience" / "CUDA or ROCm preferred") is
# not part of that alternative's NAME -- stripped here so segment
# resolution sees "Go"/"ROCm", not "Go required"/"Go experience"/"ROCm
# preferred". Necessity/importance are computed separately, from the
# FULL claim text (necessity.py/importance.py) -- this stripping only
# cleans the segment used for CONCEPT resolution. Applied repeatedly
# (`_strip_trailing_filler`) since more than one such word can stack
# ("Go experience required").
_TRAILING_FILLER = re.compile(
    r"\s*(?:is\s+)?(?:required|mandatory|essential|preferred|experience|skills?|"
    r"knowledge|proficiency|programming)\.?\s*$",
    re.IGNORECASE,
)


def _strip_trailing_filler(segment: str) -> str:
    previous, current = None, segment
    while previous != current:
        previous = current
        current = _TRAILING_FILLER.sub("", current).strip()
    return current


def contains_alternative_marker(text: str) -> bool:
    return _ALTERNATIVE_MARKER.search(text) is not None


def _split_alternative_segments(text: str) -> list[str]:
    """"Python or Go" -> ["Python", "Go"]; "PostgreSQL, MySQL, or
    MongoDB" -> ["PostgreSQL", "MySQL", "MongoDB"] (the Oxford-comma
    enumeration is handled by additionally splitting each "or"-divided
    part on commas).
    """
    segments: list[str] = []
    for part in _ALTERNATIVE_MARKER.split(text):
        for piece in part.split(","):
            piece = _strip_trailing_filler(piece.strip())
            if piece:
                segments.append(piece)
    return segments


@dataclass(frozen=True)
class AlternativeClaim:
    kind: str  # "not_technical" | "technical" | "unsafe"
    concept_ids: tuple[str, ...] = field(default_factory=tuple)


def _resolve_segment(segment: str, registry) -> tuple[str, ...] | None:
    """The concept id(s) this OR-segment contributes, or `None` if the
    segment could not be safely represented at all (fails even the
    conservative shape check) -- distinct from "resolved to nothing yet
    promotable," which returns an `unresolved:<term>` id, not `None`.
    """
    mentions = find_concept_mentions(segment, registry=registry)
    if mentions:
        return tuple(sorted({m.concept_id for m in mentions}))

    core_term = clean_list_fragment(segment)
    if core_term is not None:
        escalated = resolve_concept(core_term, registry=registry)
        if escalated.matched:
            return (escalated.concept_id,)
        return (unresolved_concept_id(core_term),)

    # Milestone 8D.1: `clean_list_fragment` failed its whole-fragment
    # shape check (too many trailing descriptive words -- e.g. "Go for
    # tooling development"). Retry against just the FIRST remaining word
    # alone. Only a REAL registry hit is accepted here -- unlike the
    # branch above, a failed lookup never promotes an `unresolved:<term>`
    # id from a one-word slice of an arbitrary sentence (see
    # `leading_token`'s docstring for why that would be too weak a
    # signal to mint a new unresolved concept from).
    leading = leading_token(segment)
    if leading is not None:
        escalated = resolve_concept(leading, registry=registry)
        if escalated.matched:
            return (escalated.concept_id,)

    return None


def classify_alternative_claim(text: str, registry=None) -> AlternativeClaim:
    if not contains_alternative_marker(text):
        return AlternativeClaim(kind="not_technical")

    registry = registry or default_registry()
    segments = _split_alternative_segments(text)
    if len(segments) < 2:
        return AlternativeClaim(kind="not_technical")

    any_confirmed = False
    unsafe = False
    ordered_ids: list[str] = []
    seen_ids: set[str] = set()

    for segment in segments:
        segment_ids = _resolve_segment(segment, registry)
        if segment_ids is None:
            unsafe = True
            continue

        for concept_id in segment_ids:
            if not concept_id.startswith("unresolved:"):
                any_confirmed = True
            if concept_id not in seen_ids:
                seen_ids.add(concept_id)
                ordered_ids.append(concept_id)

    if not any_confirmed:
        # Nothing in this OR-list is a REAL registered concept -- not
        # enough evidence this is a technology enumeration at all (e.g.
        # "Bachelor's degree ... or a related field"). Let the normal
        # per-claim pipeline handle it instead.
        return AlternativeClaim(kind="not_technical")
    if unsafe or len(ordered_ids) < 2:
        return AlternativeClaim(kind="unsafe")
    return AlternativeClaim(kind="technical", concept_ids=tuple(sorted(ordered_ids)))
