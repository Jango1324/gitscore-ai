"""Milestone 6B Part 3 -- conservative requirement-claim segmentation.

Splits raw job-description text into `Claim`s: bounded, exact-offset
spans of text that are candidate requirement statements. This is
deliberately NOT natural-language understanding -- it is section-heading
recognition (a fixed, generic, non-role-specific table of common JD
structure words), bullet/line splitting, and a conservative sentence
splitter, plus one bounded heuristic gate for text outside any
recognized section. See `docs/ARCHITECTURE.md`'s Milestone 6B section
for the full policy write-up.

Pure and deterministic: same input text always produces the same
`Claim` tuple, in the same order, with no side effects.

**Milestone 10B -- `_SectionKind.UNKNOWN`, safe section-state handling.**
M10A (`docs/evaluation/MILESTONE_10A_REALWORLD_PARSING_FAILURES.md`)
found that `current_kind` was reassigned ONLY on an exact heading-table
match -- any other heading-shaped line (a real section boundary the
table simply doesn't recognize, e.g. "Working Arrangement:" or "When
you join our team:") fell through silently, leaving a stale REQUIRED or
PREFERRED kind to keep applying to everything after it, including
company bio, legal/EEO, and salary-disclosure prose. `UNKNOWN` fixes
this WITHOUT expanding the heading vocabulary and WITHOUT ever
defaulting unknown content to REQUIRED or PREFERRED (see
`docs/evaluation/MILESTONE_10B_SECTION_STATE_SAFETY.md` for the full
design review and the two empirically-required refinements below):

1. A line is treated as an unrecognized heading -- and resets
   `current_kind` to `UNKNOWN` -- only when it is colon-terminated,
   NOT bullet-prefixed, and `current_kind` was already a REAL
   recognized kind (`REQUIRED`/`PREFERRED`/`RESPONSIBILITY`/`SKIP`).
   Both conditions are load-bearing, confirmed by measurement against
   the real M10A posting corpus: (a) resetting from `current_kind is
   None` too (i.e. before ANY heading has ever been recognized) would
   change the separate, pre-existing, already-tested "no section at
   all -> default REQUIRED, heuristic-gated" Milestone 6B policy for no
   reason this milestone is meant to touch; (b) NOT exempting bulleted
   lines would misclassify a genuine bulleted list lead-in inside an
   already-open recognized section (e.g. "- Experience with the
   following:" under "Requirements:") as a new section boundary,
   demoting its own sub-bullets to bare diagnostics -- real section
   headings are never themselves bullet-prefixed.
2. `UNKNOWN` is admitted by the SAME existing `_looks_like_requirement`
   gate `None`/no-section-yet content already uses (never a new,
   second gate) -- see `in_recognized_section` below.
3. `UNKNOWN` never maps to a `Necessity` value in
   `_SECTION_NECESSITY_HINT` at all (that dict is unchanged); content
   under it that is admitted but carries no LOCAL REQUIRED/PREFERRED
   marker (`jobs/parsing/necessity.py`) gets `necessity_hint=None` and
   is preserved as a diagnostic (the existing `UnparsedClaim` shape,
   `jobs/parsing/parser.py`) rather than a scored `JobRequirement` --
   never silently assigned to REQUIRED or PREFERRED "because the enum
   only has two values."
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto

from gitscore.jobs.parsing.concepts import find_concept_mentions
from gitscore.jobs.types import Necessity


class _SectionKind(Enum):
    REQUIRED = auto()
    PREFERRED = auto()
    RESPONSIBILITY = auto()
    SKIP = auto()
    # Milestone 10B -- an unrecognized heading was encountered after a
    # real recognized section (see module docstring). Deliberately
    # absent from _SECTION_NECESSITY_HINT below: content under this
    # kind never gets a default necessity.
    UNKNOWN = auto()


# Generic JD structural conventions -- about DOCUMENT STRUCTURE, not about
# any technical domain, so this table applies equally to a backend,
# robotics, or FPGA posting without modification (Milestone 6B's "no
# role-specific parsing" requirement). A line matches a heading only when
# the ENTIRE line (after stripping one trailing colon) equals one of
# these phrases -- a heading sharing a line with content (rare in real
# postings) is a documented limitation, not silently mishandled: the line
# then falls through to ordinary claim handling under whatever section
# was previously open.
_REQUIRED_HEADINGS = {
    "requirements", "required qualifications", "qualifications",
    "minimum qualifications", "basic qualifications", "must have", "must haves",
}
_PREFERRED_HEADINGS = {
    "preferred qualifications", "preferred skills", "preferred", "nice to have",
    "nice-to-have", "nice to haves", "bonus points", "bonus", "a plus",
}
_RESPONSIBILITY_HEADINGS = {
    "responsibilities", "what you'll do", "what you will do", "the role", "duties",
    "key responsibilities",
}
_SKIP_HEADINGS = {
    "benefits", "perks", "about us", "about the company", "about the team",
    "compensation", "salary", "salary range", "what we offer",
    "equal opportunity employer", "how to apply", "our values", "who we are",
    "why join us", "diversity", "diversity and inclusion", "perks and benefits",
}

_HEADING_KIND: dict[str, _SectionKind] = {}
for _phrase in _REQUIRED_HEADINGS:
    _HEADING_KIND[_phrase] = _SectionKind.REQUIRED
for _phrase in _PREFERRED_HEADINGS:
    _HEADING_KIND[_phrase] = _SectionKind.PREFERRED
for _phrase in _RESPONSIBILITY_HEADINGS:
    _HEADING_KIND[_phrase] = _SectionKind.RESPONSIBILITY
for _phrase in _SKIP_HEADINGS:
    _HEADING_KIND[_phrase] = _SectionKind.SKIP

_SECTION_NECESSITY_HINT = {
    _SectionKind.REQUIRED: Necessity.REQUIRED,
    _SectionKind.PREFERRED: Necessity.PREFERRED,
    _SectionKind.RESPONSIBILITY: Necessity.REQUIRED,
}

_BULLET_PREFIX = re.compile(r"^\s*(?:[-*•◦]|\d+[.)])\s+")
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")

# A bounded, generic requirement-signal vocabulary -- structural/HR
# boilerplate words that show up across virtually every technical job
# posting regardless of domain, used ONLY to gate claims that appear
# OUTSIDE any recognized section (Part 3: "avoid obvious company/
# benefits/marketing prose where feasible"). Never role- or
# technology-specific.
_REQUIREMENT_SIGNAL = re.compile(
    r"\b(experience|proficien\w*|knowledge of|familiar\w*|degree|years?|"
    r"required|preferred|\bplus\b|responsib\w*|skills?|certificat\w*|"
    r"licensed?|eligible|authoriz\w*|mentor\w*)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Claim:
    """One candidate requirement span: exact text and its offsets into
    the ORIGINAL description (never reconstructed/approximate -- see
    Milestone 6B Part 11).

    `necessity_hint` is the section-derived default (REQUIRED/PREFERRED).
    Local wording in the claim's own text can still override it (see
    `jobs/parsing/necessity.py`). Milestone 10B: `None` when the claim
    was admitted under an `_SectionKind.UNKNOWN` section (an
    unrecognized heading following a real recognized one) -- a claim
    reaching this stage was already judged requirement-SHAPED, but its
    necessity is deliberately left unresolved rather than defaulted, so
    a downstream caller with no local marker in the claim's own text
    must treat it as a diagnostic, never a scored requirement (see
    `jobs/parsing/parser.py::_requirements_from_claim`).
    """

    text: str
    start: int
    end: int
    necessity_hint: Necessity | None


def _trim_span(piece: str, abs_offset: int) -> tuple[int, int] | None:
    lead = len(piece) - len(piece.lstrip())
    trail = len(piece) - len(piece.rstrip())
    start = abs_offset + lead
    end = abs_offset + len(piece) - trail
    if start >= end:
        return None
    return start, end


def _line_content_span(line: str, line_start: int) -> tuple[int, int] | None:
    marker = _BULLET_PREFIX.match(line)
    local_start = marker.end() if marker else 0
    return _trim_span(line[local_start:], line_start + local_start)


def _split_sentences(text: str, description: str, abs_start: int) -> list[tuple[int, int]]:
    content = description[abs_start:abs_start + len(text)]
    spans: list[tuple[int, int]] = []
    cursor = 0
    for match in _SENTENCE_BOUNDARY.finditer(content):
        span = _trim_span(content[cursor:match.start()], abs_start + cursor)
        if span is not None:
            spans.append(span)
        cursor = match.end()
    span = _trim_span(content[cursor:], abs_start + cursor)
    if span is not None:
        spans.append(span)
    return spans


def _looks_like_requirement(text: str) -> bool:
    if _REQUIREMENT_SIGNAL.search(text):
        return True
    return bool(find_concept_mentions(text))


def segment_description(description: str) -> tuple[Claim, ...]:
    """Split `description` into candidate requirement `Claim`s.

    Recognized section headings (Requirements/Qualifications/Preferred
    Qualifications/Nice to Have/Responsibilities/...) make every
    contained line/sentence a claim unconditionally; a "skip" section
    (Benefits/Perks/About Us/...) suppresses every claim until the next
    heading; text outside any recognized section is gated by
    `_looks_like_requirement` (a known technical-concept mention, or a
    small generic HR/requirement-vocabulary signal) so ordinary marketing
    prose is not treated as a requirement by default.

    Milestone 10B: an unrecognized, colon-terminated, non-bulleted
    heading-shaped line encountered while a REAL recognized section
    (REQUIRED/PREFERRED/RESPONSIBILITY/SKIP) is open resets state to
    `_SectionKind.UNKNOWN` instead of silently leaving the stale kind in
    effect for the rest of the document (see module docstring). `UNKNOWN`
    content is gated by the SAME `_looks_like_requirement` heuristic as
    "no section at all," and never receives a default necessity.
    """
    claims: list[Claim] = []
    current_kind: _SectionKind | None = None

    for line_match in re.finditer(r"[^\r\n]+", description):
        line = line_match.group()
        line_start = line_match.start()

        content_span = _line_content_span(line, line_start)
        if content_span is None:
            continue
        content_start, content_end = content_span
        content = description[content_start:content_end]

        heading_key = content.rstrip(":").strip().lower()
        if heading_key in _HEADING_KIND:
            current_kind = _HEADING_KIND[heading_key]
            continue

        # Milestone 10B -- an unrecognized heading-shaped line (colon-
        # terminated, not itself a bullet list item) breaks a currently
        # open REAL section instead of letting it silently keep applying.
        # Bullet-prefixed lines are exempted: a bulleted colon lead-in
        # ("- Experience with the following:") is a list item, never a
        # section boundary -- real headings are never bulleted. Only
        # fires when `current_kind` was already a real recognized kind;
        # `current_kind is None` (nothing recognized yet) is left alone,
        # preserving the separate, pre-existing Milestone 6B "no section
        # at all" default untouched.
        if (
            current_kind is not None
            and content.rstrip().endswith(":")
            and _BULLET_PREFIX.match(line) is None
        ):
            current_kind = _SectionKind.UNKNOWN
            continue

        if current_kind is _SectionKind.SKIP:
            continue

        necessity_hint: Necessity | None
        if current_kind is _SectionKind.UNKNOWN:
            necessity_hint = None
        else:
            necessity_hint = _SECTION_NECESSITY_HINT.get(current_kind, Necessity.REQUIRED)
        in_recognized_section = current_kind in (
            _SectionKind.REQUIRED, _SectionKind.PREFERRED, _SectionKind.RESPONSIBILITY,
        )

        for sent_start, sent_end in _split_sentences(content, description, content_start):
            sentence = description[sent_start:sent_end]
            if not in_recognized_section and not _looks_like_requirement(sentence):
                continue
            claims.append(Claim(text=sentence, start=sent_start, end=sent_end, necessity_hint=necessity_hint))

    return tuple(claims)
