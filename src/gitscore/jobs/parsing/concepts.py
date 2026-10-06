"""Milestone 6B Parts 5/6 -- technical concept mention extraction from
free-form job-description prose.

Reuses the EXISTING concept registry exactly as-is (`resolve_concept()`'s
underlying alias index via `default_registry()`) -- no second,
parser-specific ontology. No mutation of the registry; no fuzzy
inference; no LLM.

Alias safety (Part 6): job-description prose is treated as the SAME
free-form-text risk class Milestone 5D.1 identified for README prose --
a short or ordinary-English alias ("go", "next", "js", "c", "ts") that is
perfectly safe as a structured value (a package.json key, a GitHub
language-stats name) produces false positives under boundary-only
matching against arbitrary sentences, and a job posting's requirement
bullets are still natural-language prose, not structured data. This
module therefore scans `concept.readme_safe_aliases()` -- the EXACT SAME
per-concept safe-alias set `evidence/extraction/readme.py` uses -- rather
than inventing a second, job-specific safety table. If real-world
validation (Milestone 6B Part 19) ever finds a job-description-specific
false positive that README validation did not (or vice versa), a
separate `job_unsafe_aliases` field could be added to `TechnicalConcept`
following the exact same data-driven pattern `readme_unsafe_aliases` set
-- not needed today, since no such divergence has been observed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from gitscore.concepts.matching import alias_pattern, select_longest_overlapping_matches
from gitscore.concepts.registry import default_registry

# Conservative unknown-technical-term policy (Part 5): promoting every
# unrecognized capitalized word to `unresolved:<term>` would flood a
# profile with noise ("Requirements", "Bachelor's", "Strong" are all
# capitalized but not technologies). Instead, an unrecognized term is
# preserved ONLY when it appears as one element of a comma/"and"-joined
# list that ALSO contains at least one term that DID resolve to a known
# concept -- a strong, structural, role-agnostic signal ("this sentence
# is enumerating technologies") that requires no per-word heuristics and
# generalizes to any domain.
_LIST_SPLIT = re.compile(r",|\band\b", re.IGNORECASE)
_LIST_ITEM_PREFIXES = re.compile(
    r"^(experience with|knowledge of|familiarity with|proficiency in|"
    r"expert[- ]level|expert in|advanced|proficient in|strong|solid|"
    r"using|with|in|and|or)\s+",
    re.IGNORECASE,
)

# Milestone 8D.1 -- the generic skill-context vocabulary
# `find_bare_short_alias_mentions` requires somewhere in the claim before
# it will accept a bare, otherwise-unsafe single-letter alias match (see
# that function's docstring for the full, bounded gating policy).
_BARE_ALIAS_CONTEXT_CUES = re.compile(
    r"\b(experience|programming|proficien\w*|language|development|developer|embedded|skills?)\b",
    re.IGNORECASE,
)
GENERIC_LIST_STOPWORDS = frozenset({
    "experience", "skills", "years", "tools", "technologies", "similar",
    "related", "environment", "systems", "software", "development", "etc",
    "field", "degree", "knowledge", "understanding", "background", "a plus",
})


def clean_list_fragment(fragment: str) -> str | None:
    """Strip common list-item prefixes/punctuation from `fragment` and
    return the plausible "core term", or `None` if it doesn't look like a
    single technology-shaped fragment at all (empty after cleaning, a
    generic filler word, or too many words to plausibly be one item).

    Shared by the conservative unknown-term policy (this module) and
    alternative-group classification (`alternatives.py`, Milestone 6B.1)
    so both apply the IDENTICAL shape heuristic -- one policy, not two
    independently-drifting copies.
    """
    stripped = _LIST_ITEM_PREFIXES.sub("", fragment.strip()).strip()
    stripped = stripped.rstrip(".,;:")
    if not stripped:
        return None
    if stripped.lower() in GENERIC_LIST_STOPWORDS:
        return None
    if len(stripped.split()) > 3:
        return None
    return stripped


def leading_token(fragment: str) -> str | None:
    """The first word of `fragment` after stripping the SAME list-item
    prefixes `clean_list_fragment` strips, or `None` if nothing is left.

    Milestone 8D.1 -- a narrower sibling of `clean_list_fragment` for
    `alternatives.py`'s OR-segment resolution: when a segment has TOO
    MANY trailing descriptive words to pass `clean_list_fragment`'s
    whole-fragment shape check (e.g. "Go for tooling development"), the
    technology name is still reliably the FIRST remaining word -- but
    unlike `clean_list_fragment`, this is intentionally never promoted to
    a NEW `unresolved:<term>` id by its caller; it is only ever used to
    retry a REAL registry lookup on just that one word (see
    `alternatives.py`'s `_resolve_segment`), since guessing a one-word
    slice of an arbitrary sentence is far too weak a signal to mint a
    brand-new unresolved concept from.
    """
    stripped = _LIST_ITEM_PREFIXES.sub("", fragment.strip()).strip()
    stripped = stripped.rstrip(".,;:")
    if not stripped:
        return None
    first = stripped.split()[0]
    if first.lower() in GENERIC_LIST_STOPWORDS:
        return None
    return first


@dataclass(frozen=True)
class ConceptMention:
    """One technical-concept mention found in a bounded piece of text.

    `start`/`end` are offsets into the TEXT PASSED IN (not necessarily
    the whole job description) -- the caller (jobs/parsing/parser.py) is
    responsible for translating these into absolute description offsets
    when it already knows the claim's own absolute start.
    """

    concept_id: str
    matched_alias: str
    start: int
    end: int


def find_concept_mentions(text: str, registry=None) -> tuple[ConceptMention, ...]:
    """Every known-registry concept mentioned in `text`, via each
    concept's `readme_safe_aliases()` -- ordered by position, one entry
    per (concept, position), so the SAME concept mentioned twice in one
    claim produces two mentions (`find_concept_mentions` is a low-level
    primitive; `jobs/parsing/parser.py` decides how many JobRequirement
    rows that becomes, e.g. one per distinct concept per claim).

    Milestone 8D.1: candidate matches from every concept/alias are
    collected FIRST and then passed through
    `concepts.matching.select_longest_overlapping_matches()` -- the
    shared "most-specific alias wins" filter -- before being returned, so
    a short alias that happens to sit inside a longer, more specific
    one's match (e.g. `framework.react`'s "react" inside
    `framework.react_native`'s "react native") never shadows it.
    """
    registry = registry or default_registry()
    candidates: list[tuple[int, int, ConceptMention]] = []
    for concept in registry.all_concepts():
        for alias in concept.readme_safe_aliases():
            for match in alias_pattern(alias).finditer(text):
                candidates.append(
                    (
                        match.start(),
                        match.end(),
                        ConceptMention(
                            concept_id=concept.concept_id,
                            matched_alias=alias,
                            start=match.start(),
                            end=match.end(),
                        ),
                    )
                )
    return tuple(select_longest_overlapping_matches(candidates))


def find_bare_short_alias_mentions(text: str, registry=None) -> tuple[ConceptMention, ...]:
    """Milestone 8D.1 -- a narrow, CASE-SENSITIVE, context-gated fallback
    for a registry concept whose alias is short enough that it has NO
    `readme_safe_aliases()` at all (today: only `language.c`'s bare "c" --
    see registry.py's comment on why it carries no safer alternative
    alias). This is the "narrower, context-aware allowance" the
    real-world evaluation recommended (Milestone 8C, Section 13 fix #1,
    the `torvalds`/`embedded_firmware_01` finding: "Strong C experience
    in embedded, resource-constrained environments" produced ZERO
    `JobRequirement` rows at all) rather than lifting the
    `readme_unsafe_aliases` restriction everywhere, which Milestone 5D.1
    added specifically BECAUSE unrestricted bare "c"/"go" matching
    produced real false positives.

    Deliberately bounded on three independent axes, all required at once:
      1. Only concepts with `readme_safe_aliases() == ()` are even
         considered (today, uniquely `language.c`) -- a concept with ANY
         safe alias already has a safe path and does not need this.
      2. Only a SINGLE-CHARACTER alias is considered -- bounds this to
         the one-letter-language problem Section 13 describes, not a
         general "relax unsafe aliases in job text" rule.
      3. The EXACT uppercase letter must appear (case-SENSITIVE,
         unlike every other matcher in this codebase) -- "a, b, or c"
         never matches; "Strong C experience" does. This alone rules out
         the overwhelming majority of ordinary lowercase-prose uses of
         the letter.
      4. A small, fixed, generic skill-context vocabulary word
         (experience/programming/proficient.../language/development/
         developer/embedded/skills) must ALSO appear somewhere in the
         SAME text -- mirroring the existing generic-vocabulary pattern
         `jobs/parsing/segmentation.py`'s `_REQUIREMENT_SIGNAL` and
         `jobs/parsing/alternatives.py`'s `_TRAILING_FILLER` already use,
         not a new kind of heuristic.

    Callers (`jobs/parsing/parser.py`) only consult this AFTER
    `find_concept_mentions` returns empty for the same text -- this is a
    last-resort fallback, never a competing/overriding match.
    """
    registry = registry or default_registry()
    if not _BARE_ALIAS_CONTEXT_CUES.search(text):
        return ()

    mentions: list[ConceptMention] = []
    for concept in registry.all_concepts():
        if concept.readme_safe_aliases():
            continue
        for alias in concept.aliases:
            if alias not in concept.readme_unsafe_aliases or len(alias) != 1:
                continue
            for match in re.finditer(r"(?<![A-Za-z0-9])" + re.escape(alias.upper()) + r"(?![A-Za-z0-9])", text):
                mentions.append(
                    ConceptMention(
                        concept_id=concept.concept_id,
                        matched_alias=alias,
                        start=match.start(),
                        end=match.end(),
                    )
                )
    mentions.sort(key=lambda m: (m.start, m.end))
    return tuple(mentions)


def find_conservative_unknown_terms(text: str, mentions: tuple[ConceptMention, ...]) -> tuple[str, ...]:
    """Unrecognized-but-list-adjacent technical terms in `text`.

    Only fires when `mentions` is non-empty (the claim already contains
    at least one CONFIRMED technology) -- otherwise returns `()`
    immediately, since an isolated unrecognized word with no confirming
    context is exactly the "ordinary prose" case Part 5 says must NOT be
    promoted to an unresolved concept. Each returned string is a raw term
    suitable for `gitscore.concepts.registry.unresolved_concept_id()` --
    this function never constructs the id itself, keeping the
    "unresolved:<term>" convention centralized in one place.

    Also requires an actual COMMA somewhere in `text` -- a genuine
    technology enumeration ("Python, Kubernetes, and Docker") reliably
    contains one; a bare "X and Y" with no comma is far more often a
    verb phrase or prose clause than a list ("Build and maintain ETL
    pipelines using Python", "Proficiency in Python for tooling and
    scripting" -- both real false positives observed in Milestone 6B's
    manual validation before this guard was added, promoting "Build" and
    "scripting" as if they were technologies). Requiring a comma is a
    conservative trade: it accepts missing a genuine comma-less
    technology list (a real but rarer phrasing) to avoid the much more
    common false-positive shape.
    """
    if not mentions or "," not in text:
        return ()

    covered = [(m.start, m.end) for m in mentions]

    def _is_covered(start: int, end: int) -> bool:
        return any(start < c_end and end > c_start for c_start, c_end in covered)

    terms: list[str] = []
    seen: set[str] = set()
    cursor = 0
    for part_match in _LIST_SPLIT.finditer(text):
        _consider_fragment(text[cursor:part_match.start()], cursor, _is_covered, terms, seen)
        cursor = part_match.end()
    _consider_fragment(text[cursor:], cursor, _is_covered, terms, seen)
    return tuple(terms)


def _consider_fragment(fragment: str, offset: int, is_covered, terms: list[str], seen: set[str]) -> None:
    stripped = clean_list_fragment(fragment)
    if stripped is None:
        return

    local_start = fragment.find(stripped)
    if local_start == -1:
        local_start = 0
    abs_start = offset + local_start
    abs_end = abs_start + len(stripped)

    if is_covered(abs_start, abs_end):
        return
    if stripped.lower() in seen:
        return

    seen.add(stripped.lower())
    terms.append(stripped)
