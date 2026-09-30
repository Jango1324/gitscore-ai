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

    `necessity_hint` is the section-derived default (REQUIRED/PREFERRED),
    always populated (a claim reaching this stage was already judged
    requirement-shaped) -- local wording in the claim's own text can
    still override it (see `jobs/parsing/necessity.py`).
    """

    text: str
    start: int
    end: int
    necessity_hint: Necessity


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

        if current_kind is _SectionKind.SKIP:
            continue

        necessity_hint = _SECTION_NECESSITY_HINT.get(current_kind, Necessity.REQUIRED)
        in_recognized_section = current_kind is not None

        for sent_start, sent_end in _split_sentences(content, description, content_start):
            sentence = description[sent_start:sent_end]
            if not in_recognized_section and not _looks_like_requirement(sentence):
                continue
            claims.append(Claim(text=sentence, start=sent_start, end=sent_end, necessity_hint=necessity_hint))

    return tuple(claims)
