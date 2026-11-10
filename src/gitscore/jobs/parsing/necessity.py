"""Milestone 6B Part 7 -- necessity inference.

Deterministic precedence: LOCAL wording in the claim's own text always
wins over the section-derived default (`Claim.necessity_hint`, from
`segmentation.py`) -- "Preferred Qualifications: ... Kubernetes is
required" (an unusual but possible real-world contradiction) resolves to
REQUIRED, matching what the sentence itself actually says. If a claim's
text contains BOTH a REQUIRED and a PREFERRED local marker (rare,
genuinely ambiguous phrasing), REQUIRED wins -- the conservative
direction: never under-state what the posting demands.

Milestone 10B: `necessity_hint` (and this function's return value)
widens to `Necessity | None` -- `None` represents
`_SectionKind.UNKNOWN` (segmentation.py), a claim admitted from text
following an unrecognized heading with no section-derived default to
fall back on. The precedence rule above is UNCHANGED: a local marker in
the claim's own text still wins first, regardless of the hint: even a
claim with `necessity_hint=None` resolves to a real `Necessity` if its
own text says "required" or "a plus." Only when NEITHER a local marker
fires NOR a real hint exists does this function return `None`, telling
`jobs/parsing/parser.py::_requirements_from_claim` to produce no scored
`JobRequirement` for it at all.

**Milestone 10E -- `resolve_necessity_hint()` (below), a NEW, separate
function.** `infer_necessity()` itself is UNCHANGED (same signature, same
two-marker precedence, still directly unit-tested as-is) -- this
milestone instead adds one new step BEFORE it: `jobs/parsing/parser.py`
now computes an "effective" hint via `resolve_necessity_hint()` and
passes THAT into this unchanged function, rather than `Claim.necessity_hint`
directly. `resolve_necessity_hint()` closes the exact gap M10A/M10E's
own real-posting traces found: `_SECTION_NECESSITY_HINT`
(segmentation.py) maps a genuine `REQUIRED` section AND an ordinary
`RESPONSIBILITY` bullet to the IDENTICAL `Necessity.REQUIRED` hint, and
maps `current_kind is None` to the same default REQUIRED whether that
means "this whole posting has no headings at all" (correct, the
original Milestone 6B policy) or "no section recognized YET, but the
document has real structure later" (SOTI's actual shape -- see
`docs/evaluation/MILESTONE_10E_NARRATIVE_REQUIREMENT_SEMANTICS.md` for
the full trace). `resolve_necessity_hint()` only ever NARROWS a hint
(to `None`) or passes it through unchanged -- it can never grant a
`Necessity` this function's own two-marker check would not have reached
anyway, which is what keeps every PREVIOUSLY-correct case (an explicit
local marker, a genuine `REQUIRED`/`PREFERRED` section, a genuinely
unsectioned posting) completely unaffected (confirmed via the Milestone
10E evaluation corpus and every pre-existing regression corpus named in
that milestone's own Phase 4 report).
"""
from __future__ import annotations

import re

from gitscore.jobs.parsing.narrative import contains_narrative_cue
from gitscore.jobs.types import Necessity

_REQUIRED_MARKER = re.compile(
    # Milestone 11-A2 -- every literal single-space word separator below
    # widened to `\s+` (see `narrative.py`'s own identical widening for
    # the full rationale: a reconstructed multi-physical-line `Claim`
    # can have an embedded newline at exactly the point a literal space
    # used to be). `\s+` still matches exactly one ASCII space, so every
    # existing, unwrapped case is unaffected.
    r"\brequired\b|\bmust\s+have\b|\bmust\s+be\b|\bmust\s+know\b|\bmandatory\b|"
    r"\bessential\b|\bneed\s+to\s+have\b",
    re.IGNORECASE,
)
_PREFERRED_MARKER = re.compile(
    r"\bpreferred\b|\bnice[-\s]to[-\s]have\b|\bnice\s+to\s+haves?\b|\ba\s+plus\b|\bbonus\b|"
    r"\bideally\b|\bwould\s+be\s+nice\b",
    re.IGNORECASE,
)

# Milestone 10E -- a claim's section is eligible to use its own
# section-derived default necessity hint without further question when
# it came from a genuine REQUIRED/PREFERRED qualifications section.
# RESPONSIBILITY/LEARNING/UNKNOWN are deliberately excluded here (see
# `resolve_necessity_hint`'s own docstring) -- a RESPONSIBILITY bullet's
# existing `Necessity.REQUIRED` hint (`_SECTION_NECESSITY_HINT`,
# segmentation.py) is NOT, by itself, evidence the bullet is a
# qualification rather than a duty description.
_SECTION_ORIGIN_ALWAYS_ELIGIBLE = frozenset({"REQUIRED", "PREFERRED"})

# Milestone 11-G21 -- vocabulary for `refine_necessity()` (below), also read by
# `qualification_intent.py`. Ported verbatim from G20's evaluated policy B1NR
# (G20's research adapter under scripts/evaluation_lib, incl. its post-hoc corrections).
_NEGATED_REQUIRED = re.compile(r"\bnot\s+(?:required|essential|mandatory)\b", re.IGNORECASE)
# G20 post-hoc correction 2: a concession is a PREFERRED statement, not a negation.
CONCESSIVE_NEGATION = re.compile(
    r"\b(?:while|although|though|even\s+if|whilst)\s+not\s+(?:required|essential|mandatory|necessary)\b",
    re.IGNORECASE,
)
APPRECIATIVE_TAIL = re.compile(
    r"\b(?:but|though|however)\b[^.;]*\b(?:appreciated|helpful|a\s+plus|welcome|nice|valued)\b|"
    r"\b(?:helpful|appreciated|a\s+plus)\b[^.;]*\bbut\s+not\b",
    re.IGNORECASE,
)
# Milestone 11-G21 (negation-scope correction): an explicitly negated necessity predicate
# ("X is not required"), and the ONE contrastive ellipsis it licenses -- a following clause, with
# its own subject, that ends in a bare copula ("...; strong Python skills are.") and therefore
# re-uses the negated predicate positively. Nothing else ever resolves an "X are" clause.
NEGATED_PREDICATE = re.compile(
    r"\b(?:is|are)\s+not\s+(required|essential|mandatory|necessary|needed|preferred)\b", re.IGNORECASE)
ELLIPTICAL_CONTRAST = re.compile(
    r"\b(?:is|are)\s+not\s+(required|essential|mandatory|necessary|needed|preferred)\b[^;]*?"
    r"(?:;|,\s*but\b)\s*(?!(?:not|never|also|though|although)\b)[^;,]*?\b(?:is|are)\s*[.!]?\s*$",
    re.IGNORECASE,
)
PREFERRED_EXTRA = re.compile(
    r"\bwould\s+be\s+(?:great|nice|helpful|ideal|an?\s+(?:advantage|asset|bonus))\b|"
    r"\b(?:is|are)\s+(?:helpful|beneficial|an?\s+(?:advantage|asset))\b|\bhelps\b|\bappreciated\b|\bdesirable\b",
    re.IGNORECASE,
)


def infer_necessity(claim_text: str, necessity_hint: Necessity | None) -> Necessity | None:
    if _REQUIRED_MARKER.search(claim_text):
        return Necessity.REQUIRED
    if _PREFERRED_MARKER.search(claim_text):
        return Necessity.PREFERRED
    return necessity_hint


def _has_local_marker(claim_text: str) -> bool:
    return _REQUIRED_MARKER.search(claim_text) is not None or _PREFERRED_MARKER.search(claim_text) is not None


def has_preference_cue(text: str) -> bool:
    """The existing preference vocabulary: PREFERRED markers, soft cues, appreciative tails."""
    return bool(_PREFERRED_MARKER.search(text) or PREFERRED_EXTRA.search(text) or APPRECIATIVE_TAIL.search(text))


def refine_necessity(claim_text: str, necessity: Necessity | None, *, full_text: str | None = None) -> Necessity | None:
    """Milestone 11-G21 -- narrows an ALREADY-INFERRED necessity; never promotes one.

    Called by `jobs/parsing/parser.py` AFTER `infer_necessity()`, which stays
    unchanged (the shadow competency path also calls it and is unaffected).

    * `None` stays `None` (UNKNOWN is never promoted to REQUIRED/PREFERRED).
    * A concession ("While not required, Rust experience is a plus") -> PREFERRED.
    * A negated required marker ("not required" / "not essential" / "not
      mandatory") with no other un-negated REQUIRED marker: PREFERRED when the
      claim also carries a preference cue ("... but appreciated", "helpful but not
      essential"), otherwise `None` -- a bare negation states no requirement.
    * REQUIRED plus a soft preference cue ("would be great", "is beneficial",
      "helps", "appreciated", "desirable", or an existing PREFERRED marker) and no
      un-negated REQUIRED marker -> PREFERRED. This corrects a section-inherited
      REQUIRED on locally softened wording.
    * Everything else is returned unchanged.

    G21 negation-scope correction: `claim_text` is the parser's SCOPED text (a negated clause
    that does not govern the qualification is blanked out by `qualification_intent`), so a
    negation is applied only to its own clause. `full_text` (the unscoped claim) is consulted
    for exactly one thing: a contrastive ellipsis ("A degree is not required; strong Python
    skills are.") resolves the elliptical clause to the negated clause's explicit predicate --
    REQUIRED for required/essential/mandatory/necessary/needed, PREFERRED for preferred. That
    is the explicit local predicate the clause re-uses, the same precedence `infer_necessity`
    gives any explicit local marker; a bare "X are" never resolves on its own.
    """
    if necessity is None:
        return None
    ellipsis = ELLIPTICAL_CONTRAST.search((full_text or claim_text).strip())
    if ellipsis is not None:
        return Necessity.PREFERRED if ellipsis.group(1).lower() == "preferred" else Necessity.REQUIRED
    text = claim_text.strip()
    if CONCESSIVE_NEGATION.search(text):
        return Necessity.PREFERRED
    negated = _NEGATED_REQUIRED.search(text) is not None
    unnegated_required = _REQUIRED_MARKER.search(_NEGATED_REQUIRED.sub(" ", text)) is not None
    preferred_cue = has_preference_cue(text)
    if negated and not unnegated_required:
        return Necessity.PREFERRED if preferred_cue else None
    if necessity == Necessity.REQUIRED and preferred_cue and not unnegated_required:
        return Necessity.PREFERRED
    return necessity


def resolve_necessity_hint(
    claim_text: str,
    necessity_hint: Necessity | None,
    *,
    section_kind: str | None,
    document_has_recognized_heading: bool,
) -> Necessity | None:
    """Milestone 10E -- the hint `jobs/parsing/parser.py` should pass
    into `infer_necessity()` ABOVE (never a replacement for it -- this
    function's own local-marker check exists only so this function's
    OWN eligibility decision can short-circuit early for a claim
    `infer_necessity` would resolve identically regardless of hint
    anyway; `infer_necessity` still runs afterward, unconditionally, and
    is the ONLY place a `Necessity` is actually produced).

    Three steps, in order -- see
    `docs/evaluation/MILESTONE_10E_NARRATIVE_REQUIREMENT_SEMANTICS.md`
    §5 for the full candidate comparison this design (Candidate C) is
    based on:

    1. An explicit local REQUIRED/PREFERRED marker in `claim_text`
       itself ALWAYS wins, unconditionally -- `necessity_hint` is
       returned unchanged (not re-derived here; `infer_necessity` will
       find the SAME marker next and resolve it the same way regardless
       of what is returned in this branch). This is what keeps every
       explicit qualification safe no matter where it appears: outside
       any Requirements section (`"Applicants must know Java."`), mixed
       into a RESPONSIBILITY bullet (`"...; Java experience is
       required."`), or phrased as a learning-aptitude trait
       (`"Willingness to learn new technologies is required."`, never
       confused with a LEARNING-narrative promise despite sharing the
       word "learn").
    2. Otherwise, SECTION-ORIGIN eligibility: a claim whose section is a
       genuine `REQUIRED`/`PREFERRED` heading, OR whose section is
       `None` (no heading recognized AT ALL, anywhere, in `claim_text`'s
       whole document -- `document_has_recognized_heading=False`,
       preserving the original Milestone 6B "no section at all" default
       byte-for-byte) keeps its existing hint. Every other origin
       (`RESPONSIBILITY`, `LEARNING`, `UNKNOWN`, or a `None` PREAMBLE
       before the SAME document's own later real sections --
       `document_has_recognized_heading=True`) is downgraded to `None`
       here -- the exact mechanism that fixes Manulife's "Collaborate
       with engineering and business teams..." responsibility bullet
       (today: `category='soft_skill'`, `necessity=REQUIRED`; after:
       routed to `UnparsedClaim` via `_requirements_from_claim`'s
       existing `necessity is None -> []` short-circuit, no new
       diagnostic type).
    3. Only for a claim that survived step 2 (section-eligible): an
       ADDITIONAL, independent veto against `contains_narrative_cue()`
       (`jobs/parsing/narrative.py`) -- a defense-in-depth check for a
       learning/company-narrative sentence that happens to sit inside an
       eligible context (a real Requirements section, or a genuinely
       unsectioned posting). This is the exact mechanism that fixes the
       real SOTI "Opportunity" paragraph when it precedes the document's
       own later `"Required skills:"` section (step 2 already excludes
       it there) AND, independently, a hypothetical fully-unsectioned
       posting whose entire content IS narrative (step 2 alone would
       keep it; step 3 removes it).
    """
    if _has_local_marker(claim_text):
        return necessity_hint

    section_eligible = section_kind in _SECTION_ORIGIN_ALWAYS_ELIGIBLE or (
        section_kind is None and not document_has_recognized_heading
    )
    if not section_eligible:
        return None

    if contains_narrative_cue(claim_text):
        return None

    return necessity_hint
