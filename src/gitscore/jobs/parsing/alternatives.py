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

**Milestone 10D -- alternative-requirement semantics (two additive
fixes, both evaluation-derived, see
`docs/evaluation/MILESTONE_10D_ALTERNATIVE_SEMANTICS.md` for the full
corpus/candidate comparison this design is based on):**

1. **Root Cause 4 -- an explicit ANY-of lead-in with NO literal "or"
   at all** (the real Manulife posting: "Experience with at least one
   programming language (e.g., Java, Python, Go, JavaScript)" --
   `contains_alternative_marker()` never fires, so the pre-10D parser
   never even attempted group detection, instead minting one
   independent REQUIRED row per matched language). `_ANY_OF_TRIGGER`
   recognizes six lead-in phrases ("one or more of," "at least one,"
   "any one of," "one of the following," "any of," "either of" --
   "at least one" deliberately bare, no required trailing "of," to
   match Manulife's own wording) anywhere in the claim, independent of
   `contains_alternative_marker()`. Once found, `_find_any_of_list_region()`
   locates the actual list that follows it -- a parenthetical example
   clause ("(e.g., ...)"/"such as ..."/"for example ..."), else a
   colon-introduced list, else the bare remainder -- and resolves THAT
   region through the exact same `_classify_segment_list()` (below)
   the ordinary "or"-path already used, never new concept-matching
   logic. Checked FIRST in `classify_alternative_claim()`, before the
   ordinary bare-"or" path, so the trigger's own list region is judged
   on its own, not re-mixed with unrelated "or"s/commas elsewhere in
   the same claim.
2. **Root Cause 5 -- idiom-blind "or" splitting** (SOTI's "one or more
   of the following programming languages: ..." -- the literal "or"
   inside the filler idiom "one or more" was previously split like an
   ordinary list separator, producing a garbage leading segment).
   `_IDIOM_OR_MORE` protects any `"<number-word/digit> or more"` span
   from `_split_alternative_segments()`'s own bare-"or" split --
   narrowly scoped to this one idiom shape, never a general "or"
   blocklist. This also doubles as Candidate A's safety net whenever
   the new trigger-phrase table (above) does not fire at all (e.g. an
   idiom appearing somewhere other than as a recognized lead-in).

A THIRD, previously-undermechanized fabrication path was found and
closed as part of this same milestone, inside `_resolve_segment()`
itself (not new to the trigger/idiom work above, and affecting the
ORDINARY bare-"or" path too): its `clean_list_fragment`-escalation
branch used to promote an unresolved term to `unresolved:<term>`
UNCONDITIONALLY once `clean_list_fragment` accepted it, with no shape
check at all -- unlike the sibling ALL-UNRESOLVED-group rescue inside
`classify_alternative_claim()`, which already gated on
`looks_like_specific_technology_name`. A short, generic filler word
surviving idiom-blind splitting (e.g. "one" in "one or more," or the
garbled "more of: C") was short enough to pass `clean_list_fragment`'s
plain <=3-word/stopword check and got promoted into an otherwise-real
alternative group as a fabricated id (`unresolved:one`,
`unresolved:more_of:_c`) -- confirmed reproducible on a differently
punctuated "one or more of" sentence one punctuation choice away from
SOTI's own. `_resolve_segment()` now requires
`looks_like_specific_technology_name` before accepting this escalation
too, closing the gap for every caller, not just the new trigger path.
Confirmed non-regressing against every previously-correct alternative-
group case (frozen `general_swe_01` gold, the full M9B/M10A/M10C
corpora, and the existing manual examples in `tests/test_job_parser.py`)
because this branch's shape-less promotions were ALREADY excluded from
`any_confirmed`/`all_shaped` by the caller's own pre-existing safety
net -- this change only moves that exclusion one step earlier, inside
`_resolve_segment()` itself, never changing a case that previously
survived into a `technical` result.

`JOB_DESCRIPTION_PARSER_VERSION` bumps `v6` -> `v7` accordingly
(`jobs/parsing/parser.py`).

**Explicitly deferred, NOT implemented here (Root Cause 6, newly
identified, see the design doc §1.5/§6.3):** a MIXED AND/OR shape
("Python or Java and SQL") is still silently flattened into one
over-permissive ANY-of-3 group today -- fixing this needs genuine
AND/OR precedence detection, not a single fixed split point, and is
reserved for a future, separately-scoped and separately-approved
milestone. No schema/matcher/scoring change was made or is believed
necessary for either fix above or for a future Root Cause 6 fix (a
MIXED requirement is already representable today as one
`alternative_concept_ids` group plus one ordinary single-`concept_id`
row, exactly mirroring how "Docker and Kubernetes" already becomes two
independent rows).

**Milestone 11-G17 -- Root Cause 6 CONTAINED (not decomposed).** A
`technical` result whose claim is structurally mixed AND/OR
(`is_structurally_mixed()`, below) is returned as `unsafe` instead, so
the parser's existing 6B.1 fallback produces a non-scoreable
`alternative_requirement` placeholder (NOT_ASSESSABLE, never in the
alignment denominator, original text/span/necessity kept) rather than a
flat OR group that one alternative could satisfy while a mandatory
conjunct is missing. This is Option D exactly as evaluated in
`docs/evaluation/MILESTONE_11_G16_COMPOUND_REQUIREMENT_LOGIC.md`; mixed
claims are deliberately NOT decomposed into several rows (Option C, not
approved). Known residuals the detector cannot see: a mixed-kind comma
list with no conjunction ("Python, Docker or Kubernetes") and a segment
whose second concept is unrecognised (bare "Go" in prose).
`JOB_DESCRIPTION_PARSER_VERSION` bumps `v12` -> `v13`.

**Milestone 11-G22-Q -- canonical alias equivalence.** An OR whose every
alternative is only a different registry alias of the SAME canonical
concept ("Kubernetes or k8s", "Go or Golang", "Postgres or PostgreSQL")
is not a choice between technologies, yet `_classify_segment_list` saw
fewer than two distinct ids and returned `unsafe` -- a non-assessable
placeholder for a requirement that names exactly one concept.
`equivalent_alias_concept_id()` (below) establishes the equivalence from
existing canonical identity only, and `classify_alternative_claim()` then
returns `not_technical` for that one case, so the parser's ordinary
single-concept path builds ONE `concept_id` row (span, text and necessity
are computed by the parser exactly as before). Only an `unsafe` result
is ever converted; a `technical` group (genuine alternatives, including
"Kubernetes or k8s or Docker", already deduplicated) and every G17
structurally mixed claim are untouched. No new alias, no relation edge
(parent/related), and no candidate evidence is ever consulted.
`JOB_DESCRIPTION_PARSER_VERSION` bumps `v14` -> `v15`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from gitscore.concepts.registry import default_registry, resolve_concept, unresolved_concept_id
from gitscore.jobs.parsing.concepts import (
    clean_list_fragment,
    find_concept_mentions,
    find_conservative_unknown_terms,
    leading_token,
    looks_like_specific_technology_name,
)

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


# Milestone 10D Root Cause 5 -- the ONE idiom `_split_alternative_segments`
# must never read as a list-separator "or": "<number-word/digit> or
# more" ("one or more of the following programming languages: ...").
# Deliberately narrow (never a general "or" blocklist) -- see this
# module's docstring.
_IDIOM_OR_MORE = re.compile(
    r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+or\s+more\b",
    re.IGNORECASE,
)


def _idiom_protected_spans(text: str) -> list[tuple[int, int]]:
    return [match.span() for match in _IDIOM_OR_MORE.finditer(text)]


def _split_alternative_segments(text: str) -> list[str]:
    """"Python or Go" -> ["Python", "Go"]; "PostgreSQL, MySQL, or
    MongoDB" -> ["PostgreSQL", "MySQL", "MongoDB"] (the Oxford-comma
    enumeration is handled by additionally splitting each "or"-divided
    part on commas).

    Milestone 10D: a bare "or" that falls inside an `_IDIOM_OR_MORE`
    match (e.g. the "or" in "one or more") is never treated as a list
    separator -- found via `finditer` + a protected-span exclusion
    rather than the simpler `_ALTERNATIVE_MARKER.split()` this function
    used before, specifically so that exclusion is possible.
    """
    protected = _idiom_protected_spans(text)

    def _is_protected(position: int) -> bool:
        return any(start <= position < end for start, end in protected)

    pieces: list[str] = []
    cursor = 0
    for match in _ALTERNATIVE_MARKER.finditer(text):
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
        # Milestone 10D: an escalated term that failed to resolve
        # against the registry is promoted to a conservative
        # `unresolved:<term>` placeholder ONLY when it also looks like
        # ONE specific named technology (shape, never meaning) -- the
        # SAME `looks_like_specific_technology_name` gate the sibling
        # ALL-UNRESOLVED-group rescue in `classify_alternative_claim()`
        # already applies. Closes a fabrication path where a short,
        # generic filler word surviving idiom-blind splitting ("one,"
        # the garbled "more of: C") was previously promoted
        # unconditionally -- see this module's own docstring.
        if looks_like_specific_technology_name(core_term):
            return (unresolved_concept_id(core_term),)
        return None

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


def _shaped_term(segment: str, *, allow_leading_token: bool) -> str | None:
    """Milestone 9A -- the segment's core term for the ALL-UNRESOLVED
    OR-group rescue below, or `None` if there isn't a plausible one.

    Tries the same two-step escalation `_resolve_segment` already uses
    (whole-fragment `clean_list_fragment`, then -- only if that fails on
    an over-long fragment, e.g. "Simulink for controls simulation" --
    `leading_token`'s single-leading-word extraction, gated by
    `allow_leading_token`). Unlike `_resolve_segment`'s own
    `leading_token` branch, this does NOT require the term to already be
    a real registry concept: it only answers "is there a plausible
    specific-technology-shaped term here at all" (checked by the caller
    via `looks_like_specific_technology_name`) -- never a resolution
    decision by itself.

    `allow_leading_token` MUST be `False` for the OR-list's FIRST segment
    (see `classify_alternative_claim`): ordinary English capitalizes the
    first word of a sentence/claim regardless of whether it names a
    technology ("Security certification such as OSCP" -- "Security" is
    capitalized only because it starts the claim, not because it is a
    product name), so `leading_token`'s raw, unstripped first word is
    NOT a trustworthy shape signal there. A later segment's leading word
    (right after an "or"/comma, e.g. "Simulink" in "...MATLAB or
    Simulink for controls simulation") has no such sentence-initial
    capitalization rule working against it -- genuine capitalization
    there IS a real signal.
    """
    term = clean_list_fragment(segment)
    if term is not None:
        return term
    if not allow_leading_token:
        return None
    return leading_token(segment)


def _classify_segment_list(segments: list[str], registry) -> AlternativeClaim | None:
    """The shared per-segment resolution loop both the ordinary bare-
    "or" path and Milestone 10D's explicit ANY-of trigger path (below)
    use identically -- extracted from `classify_alternative_claim()`'s
    original body so the trigger path reuses this EXACT logic rather
    than a second, independently-drifting copy. Returns `None` when
    there are fewer than two segments at all (not a list) -- the
    caller decides what that means for ITS OWN fallback.
    """
    if len(segments) < 2:
        return None

    any_confirmed = False
    unsafe = False
    all_shaped = True
    ordered_ids: list[str] = []
    seen_ids: set[str] = set()

    for index, segment in enumerate(segments):
        segment_ids = _resolve_segment(segment, registry)
        shaped_term = _shaped_term(segment, allow_leading_token=index > 0)
        segment_shaped = shaped_term is not None and looks_like_specific_technology_name(shaped_term)

        if segment_ids is None:
            if not segment_shaped:
                unsafe = True
                all_shaped = False
                continue
            # Milestone 9A: `_resolve_segment` gave up on this segment
            # (its own leading_token escalation only accepts a REAL
            # registry match), but the segment is still unambiguously
            # shaped like ONE specific named technology -- safe to
            # promote to an unresolved placeholder in this narrower
            # rescue, used only when every OTHER segment in the list is
            # ALSO either a real concept or shaped this way (see the
            # `all_shaped`/`any_confirmed` check below).
            segment_ids = (unresolved_concept_id(shaped_term),)
        elif not segment_shaped:
            all_shaped = False

        for concept_id in segment_ids:
            if not concept_id.startswith("unresolved:"):
                any_confirmed = True
            if concept_id not in seen_ids:
                seen_ids.add(concept_id)
                ordered_ids.append(concept_id)

    if not any_confirmed and not all_shaped:
        # Nothing in this OR-list is a REAL registered concept, AND at
        # least one segment either failed to resolve at all or isn't
        # shaped like a specific named technology (Milestone 9A) -- not
        # enough evidence this is a technology enumeration at all (e.g.
        # "Bachelor's degree ... or a related field", "control systems
        # or state estimation" -- both correctly stay `not_technical`,
        # see docs/evaluation/MILESTONE_9A_REQUIREMENT_PRESERVATION.md).
        # Let the normal per-claim pipeline handle it instead.
        return AlternativeClaim(kind="not_technical")
    if unsafe or len(ordered_ids) < 2:
        return AlternativeClaim(kind="unsafe")
    return AlternativeClaim(kind="technical", concept_ids=tuple(sorted(ordered_ids)))


# Milestone 10D Root Cause 4 -- explicit ANY-of lead-in phrases,
# checked independently of a literal "or." "at least one" is
# deliberately bare (no required trailing "of") to match the real
# Manulife posting's own wording ("Experience with at least one
# programming language (e.g., ...)"). Safety against this broadened,
# bare trigger comes entirely from requiring an ACTUAL list structure
# to follow it (`_find_any_of_list_region`) and from
# `_classify_segment_list`'s own existing shape/resolution
# requirements -- never from the trigger phrase's specificity alone
# (confirmed via `evaluation/m10d/alternative_controls.json`'s
# category-E/F negative controls, e.g. "at least one year of
# experience with Python" must never become a multi-way group).
_ANY_OF_TRIGGER = re.compile(
    r"\b(?:one or more of|at least one|any one of|one of the following|any of|either of)\b",
    re.IGNORECASE,
)
_PARENTHETICAL_EXAMPLE_LIST = re.compile(r"\(\s*(?:e\.g\.,?|such as|for example)\s*([^)]+)\)", re.IGNORECASE)
_LIST_AFTER_COLON = re.compile(r":\s*(.+)$", re.DOTALL)
_LEADING_CONNECTOR = re.compile(r"^\s*(?:of\s+)?(?:the\s+following\s*:?\s*)?", re.IGNORECASE)


def _find_any_of_list_region(text: str, trigger_end: int) -> str | None:
    """The text Root Cause 4's trigger path should treat as "the
    enumerated list," searched from `trigger_end` onward -- a
    parenthetical example clause, else a colon-introduced list, else
    the bare remainder (leading connector stripped) if non-empty.
    Returns `None` only when the remainder is empty or has no list
    structure left at all after stripping (a bare idiom with nothing
    to enumerate, e.g. "One or more of the following" on its own).
    """
    remainder = text[trigger_end:]
    parenthetical = _PARENTHETICAL_EXAMPLE_LIST.search(remainder)
    if parenthetical is not None:
        return parenthetical.group(1)
    colon_list = _LIST_AFTER_COLON.search(remainder)
    if colon_list is not None:
        return colon_list.group(1)
    stripped = _LEADING_CONNECTOR.sub("", remainder).strip()
    return stripped or None


def _classify_any_of_trigger(text: str, registry) -> AlternativeClaim | None:
    """Milestone 10D Root Cause 4. Returns `None` whenever this trigger
    path cannot responsibly commit to an outcome -- no trigger phrase
    found, no list-shaped region follows one, or the list region
    itself resolves to `not_technical` (fewer than two real/shaped
    segments) -- in every such case the caller falls through to the
    ordinary bare-"or" path on the FULL original text unchanged. Only
    a `technical` or `unsafe` result from the trigger's OWN, narrower
    list region is returned directly: once a confirmed technical
    context exists there, that is the correct, final (conservative if
    necessary) answer -- never silently re-tried against a different,
    wider segmentation.
    """
    trigger = _ANY_OF_TRIGGER.search(text)
    if trigger is None:
        return None
    list_region = _find_any_of_list_region(text, trigger.end())
    if list_region is None:
        return None
    segments = _split_alternative_segments(list_region)
    result = _classify_segment_list(segments, registry)
    if result is None or result.kind == "not_technical":
        return None
    return result


# Milestone 11-G17 -- structural signals that a claim combines AND and OR
# (Option D as evaluated in M11-G16). Each is structural, never a bare
# keyword anywhere in the claim: a cardinality of two or more ("at least
# two of"), an explicit all-of/both lead-in, or a comma item that BEGINS
# with a conjunction (", and Python").
_MIXED_AT_LEAST_TWO = re.compile(r"\bat\s+least\s+(?:two|three|four|five|[2-9])\b", re.IGNORECASE)
_MIXED_ALL_OF_LEAD_IN = re.compile(r"\b(?:both|all\s+of)\b", re.IGNORECASE)
_MIXED_CONJUNCTION_ITEM = re.compile(r",\s*(?:and|as\s+well\s+as|plus|along\s+with)\b", re.IGNORECASE)


def is_structurally_mixed(text: str, registry=None) -> bool:
    """Milestone 11-G17 -- True when a claim that would otherwise become
    ONE flat OR group actually mixes AND with OR, so a flat group would
    let a single alternative satisfy a requirement whose mandatory
    conjunct is missing. Detected only from structure: a k>=2-of / both /
    all-of lead-in, a conjunction-led comma item, or an OR segment that
    itself resolves to two or more distinct concepts ("Java and SQL",
    "Kubernetes; Python")."""
    if _MIXED_AT_LEAST_TWO.search(text) or _MIXED_ALL_OF_LEAD_IN.search(text) \
            or _MIXED_CONJUNCTION_ITEM.search(text):
        return True
    registry = registry or default_registry()
    for segment in _split_alternative_segments(text):
        segment_ids = _resolve_segment(segment, registry)
        if segment_ids is not None and len(set(segment_ids)) >= 2:
            return True
    return False


def _contain_mixed(result: AlternativeClaim, text: str, registry) -> AlternativeClaim:
    """Milestone 11-G17 -- a `technical` (flat OR) result for a
    structurally mixed claim is returned as `unsafe`, routing it to the
    parser's existing non-scoreable fallback instead of a flat OR group.
    Every other result passes through unchanged."""
    if result.kind == "technical" and is_structurally_mixed(text, registry):
        return AlternativeClaim(kind="unsafe")
    return result


def equivalent_alias_concept_id(text: str, registry=None) -> str | None:
    """Milestone 11-G22-Q -- the ONE canonical concept id every OR
    alternative of `text` is an alias of, or `None` when that cannot be
    established. All of the following must hold:

    1. the claim has a literal "or" and is NOT structurally mixed
       (G17's `is_structurally_mixed` is checked first and always wins);
    2. it splits into >= 2 alternatives, each of which is a bare list item
       (`clean_list_fragment` accepts it -- an alternative carrying prose,
       e.g. "react quickly to incidents", "Go for backend services", is
       never equated);
    3. each alternative resolves INDEPENDENTLY, through the existing
       `_resolve_segment`, to exactly one REGISTERED concept (never an
       `unresolved:` id), and that id is the same for all of them;
    4. each alternative's cleaned term is, IN ITS ENTIRETY, a registry
       alias of that concept (`resolve_concept`). An alias merely embedded
       in a longer name is not enough: "Docker Compose" contains "Docker"
       but is a different tool, so "Docker or Docker Compose" stays a
       genuine alternative (likewise "shell scripting" is not an alias);
    5. the full-claim scan the parser's single-concept path will run finds
       that concept and nothing else (no other mention, no conservative
       unknown term) -- so the resulting requirement is exactly one row
       for this id.

    Identity is the registry id itself: parent/related edges and
    similarity are never consulted, and no candidate evidence is read.
    """
    registry = registry or default_registry()
    if not contains_alternative_marker(text) or is_structurally_mixed(text, registry):
        return None
    segments = _split_alternative_segments(text)
    if len(segments) < 2:
        return None
    canonical: str | None = None
    for segment in segments:
        core_term = clean_list_fragment(segment)
        if core_term is None:
            return None
        resolved = _resolve_segment(segment, registry)
        if resolved is None or len(resolved) != 1 or registry.get(resolved[0]) is None:
            return None
        whole_alias = resolve_concept(core_term, registry=registry)
        if not whole_alias.matched or whole_alias.concept_id != resolved[0]:
            return None
        if canonical is None:
            canonical = resolved[0]
        elif resolved[0] != canonical:
            return None
    mentions = find_concept_mentions(text, registry=registry)
    if {m.concept_id for m in mentions} != {canonical} or find_conservative_unknown_terms(text, mentions):
        return None
    return canonical


def classify_alternative_claim(text: str, registry=None) -> AlternativeClaim:
    registry = registry or default_registry()
    result = _classify_alternative_structure(text, registry)
    # Milestone 11-G22-Q -- an `unsafe` result whose alternatives are all
    # aliases of one canonical concept is routed to the ordinary
    # single-concept path. Nothing else is converted.
    if result.kind == "unsafe" and equivalent_alias_concept_id(text, registry) is not None:
        return AlternativeClaim(kind="not_technical")
    return result


def _classify_alternative_structure(text: str, registry) -> AlternativeClaim:
    """The v14 classification (unchanged): 10D trigger path, ordinary
    bare-"or" path, G17 mixed containment."""
    # Milestone 10D -- Root Cause 4's explicit ANY-of trigger path is
    # tried FIRST: it has no literal-"or" requirement at all, and its
    # own list region must be judged on its own, not re-mixed with
    # unrelated "or"s/commas elsewhere in the same claim (exactly
    # SOTI's and Manulife's real sentences).
    trigger_result = _classify_any_of_trigger(text, registry)
    if trigger_result is not None:
        return _contain_mixed(trigger_result, text, registry)

    if not contains_alternative_marker(text):
        return AlternativeClaim(kind="not_technical")

    segments = _split_alternative_segments(text)
    result = _classify_segment_list(segments, registry)
    if result is None:
        return AlternativeClaim(kind="not_technical")
    return _contain_mixed(result, text, registry)
