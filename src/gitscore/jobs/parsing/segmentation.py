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

**Milestone 10C -- real-world heading recognition.** M10A
(`docs/evaluation/MILESTONE_10A_REALWORLD_PARSING_FAILURES.md`) found
that the heading table above required an ENTIRE line to equal one of a
small set of ~30 fixed phrases -- missing extremely common real-world
phrasing ("Required skills" vs. "Requirements," "Position
Responsibilities" vs. "Responsibilities," "About SOTI" vs. "About Us")
and lacking any category at all for a "what you will learn" section.
See `docs/evaluation/MILESTONE_10C_SECTION_CLASSIFICATION.md` for the
full evaluation-first design review (three candidate designs measured
against an independent 78-entry heading corpus) this change implements.

The exact-phrase tables are replaced by `_classify_heading_line()`: a
structural "is this line heading-shaped at all" gate -- short (<=7
words), not itself a bullet, never ending in sentence-terminal
punctuation, never a colon followed by an inline comma-separated list
(so "Experience with: Python, JavaScript" is never mistaken for a
heading), and either colon-terminated-with-nothing-after, Markdown
(`#`/`**`), ALL-CAPS, or title-cased -- entirely independent of word
content. A bare (no colon/Markdown/ALL-CAPS) title-cased line ALSO
requires at least one family root match to count as heading-shaped at
all -- a WEAK structural signal (plain title-case) alone is not enough,
confirmed necessary by this milestone's own regression suite: without
this requirement, a single bare capitalized word standing alone on its
own line (e.g. "Python" in an un-bulleted, one-item-per-line requirement
list) would be swallowed as a phantom heading. One measured consequence
of this same safety requirement: a bare, un-bulleted list lead-in with
NO family root at all ("Experience with the following:", "Knowledge
of:") still correctly classifies as `UNKNOWN` (colon-termination is a
STRONG signal, so the family-match requirement does not apply to it) --
preserving Milestone 10B's existing, tested "resets state away from
whatever was open, the line itself never becomes a claim" guarantee for
this exact shape, rather than the alternative (excluding it from heading
detection entirely) tried and reverted during implementation, which let
it fall through as an ordinary claim under a still-open recognized
section instead.

A line that passes the shape gate is then classified by anchored,
word-boundary-bounded ROOT WORDS into one of five families
(`REQUIRED`/`PREFERRED`/`RESPONSIBILITY`/new `LEARNING`/
`NON_QUALIFICATION`, the last reusing the existing `SKIP` kind) with
built-in collision exclusions (e.g. a bare `qualif*` root never fires
REQUIRED when a `preferr*` root is ALSO present on the same line, so
"Preferred Qualifications" resolves to PREFERRED, not REQUIRED). A line
matching more than one family, or matching none, maps to `UNKNOWN`
rather than being forced to one winner by a fixed precedence order (an
explicit, architecturally-approved choice -- see that design doc's
Phase 3/6 for the measured evidence this avoids a real, high-severity
misclassification a fixed-precedence design makes on a genuinely
compound heading like "Required Responsibilities").

`LEARNING` is a NEW `_SectionKind`, added specifically so it can
participate in the SAME "falls off a real recognized kind into UNKNOWN"
transition `REQUIRED`/`PREFERRED`/`RESPONSIBILITY`/`SKIP` already do
(Milestone 10B's existing trigger condition is already written as "was
`current_kind` not `None`," so `LEARNING` participates with zero
additional code) -- but, like `UNKNOWN`, `LEARNING` NEVER maps to a
`Necessity` value: "Learning opportunities should not automatically enter
scoring" (the M10C design brief's own guardrail) is enforced the exact
same way `UNKNOWN`'s non-scoring guarantee already is.

**Amendment to M10B's point 1 above.** M10B's original trigger only
reset `current_kind` to `UNKNOWN` when it was ALREADY a real recognized
kind, specifically to avoid a then-real regression (the old table's
"Required skills:" miss would otherwise ALSO have been caught by a
too-eager reset rule and demoted from its already-correct 6B fallback).
That circularity no longer applies: `_classify_heading_line()` now
recognizes `"Required skills:"` directly as `REQUIRED`, so there is
nothing left for an over-eager reset to demote. `_classify_heading_line()`
therefore classifies every heading-shaped line the SAME way regardless
of what `current_kind` was before -- including from `None` (no section
recognized yet): a line with a STRONG shape signal (colon/ALL-CAPS/
Markdown) or a family-root match is classified identically whether or
not anything was previously recognized. **Checked directly against the
real SOTI posting and found NOT to apply there**: its very first line,
`"Opportunity,"` is a single bare word with no colon/Markdown/ALL-CAPS
and no family-root match -- exactly the WEAK-signal-without-
corroboration shape the regression fix above excludes -- so it stays
`None` (ordinary content, `current_kind` stays `None`), and SOTI's one
confirmed false positive (a fabricated REQUIRED `(language.csharp,
language.sql)` alternative group from the "technologies you learn...
languages like C#, or... leveraging SQL..." narrative paragraph, M10A
Root Cause 4/5-adjacent) is UNCHANGED by this milestone -- confirmed by
direct re-run, `docs/evaluation/MILESTONE_10C_SECTION_CLASSIFICATION.md`'s
completion addendum. That false positive remains explicitly out of
scope (alternative-list semantics, reserved for M10D).

**No `JobRequirement`/`UnparsedClaim` schema change. No `Claim` field
change** (only the SET of lines that can become a heading, and which
`_SectionKind` a heading maps to, changed -- `Claim.necessity_hint`'s
type, `Claim.start`/`end` computation, and the existing M10B precedence
rules are all untouched).
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
    # Milestone 10C -- "Skills You Will Learn" / "What You Will Learn" /
    # "Learning Opportunities" (see module docstring). Like UNKNOWN,
    # deliberately absent from _SECTION_NECESSITY_HINT below.
    LEARNING = auto()
    # Milestone 10B -- an unrecognized heading was encountered after a
    # real recognized section (see module docstring). Deliberately
    # absent from _SECTION_NECESSITY_HINT below: content under this
    # kind never gets a default necessity.
    UNKNOWN = auto()


_SECTION_NECESSITY_HINT = {
    _SectionKind.REQUIRED: Necessity.REQUIRED,
    _SectionKind.PREFERRED: Necessity.PREFERRED,
    _SectionKind.RESPONSIBILITY: Necessity.REQUIRED,
}

_BULLET_PREFIX = re.compile(r"^\s*(?:[-*•◦]|\d+[.)])\s+")
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")

# ---------------------------------------------------------------------------
# Milestone 10C -- heading classification. Replaces the old exact-phrase
# tables entirely (every phrase they listed is also matched by one of the
# anchored root families below, confirmed both by inspection and by the
# full regression suite -- see docs/evaluation/MILESTONE_10C_SECTION_CLASSIFICATION.md
# Phase 3/6). "Strategy C" in that document's own terms: a structural
# shape gate fully independent of word content, then anchored root-word
# families, with a reused production heuristic as an exclusion and an
# honest UNKNOWN outcome for a line matching more than one family rather
# than a forced, fixed-precedence winner.
# ---------------------------------------------------------------------------

_INVISIBLE_CHARS = re.compile(r"[​‌‍﻿]")
_MARKDOWN_LEADER = re.compile(r"^#{1,6}\s*")
_MARKDOWN_BOLD = re.compile(r"^\*\*(.*)\*\*$")
_TITLECASE_STOPWORDS = frozenset(
    {"a", "an", "the", "of", "in", "on", "and", "or", "to", "for", "at", "by", "as"}
)

_REQUIRED_ROOT = re.compile(r"\brequir\w*\b|\bmust[- ]have\w*\b|\bmandatory\b", re.IGNORECASE)
_QUALIFICATION_ROOT = re.compile(r"\bqualif\w*\b", re.IGNORECASE)
_PREFERRED_ROOT = re.compile(
    r"\bpreferr\w*\b|\bnice[- ]to[- ]have\w*\b|\bbonus\w*\b|\ba plus\b", re.IGNORECASE
)
_LEARNING_ROOT = re.compile(
    r"\byou(?:'ll| will) (?:learn|gain)\b|\blearning opportunit\w*\b|"
    r"\bgrowth opportunit\w*\b|\bskills? you(?:'ll| will) (?:learn|gain)\b",
    re.IGNORECASE,
)
_RESPONSIBILITY_ROOT = re.compile(
    r"\brespons\w*\b|\bduties\b|\bduty\b|\bwhat you(?:'ll| will) do\b|"
    r"\bthe role\b|\bday in this role\b",
    re.IGNORECASE,
)
# NON_QUALIFICATION maps to the existing SKIP kind (identical runtime
# behavior: fully suppressed, zero claims, zero diagnostics) -- this is a
# vocabulary expansion of what SKIP recognizes, not a new section kind.
_NON_QUALIFICATION_ROOT = re.compile(
    r"^about\b|\bbenefit\w*\b|\bperk\w*\b|\bcompensation\b|\bsalary\b|"
    r"\bequal opportunity\b|\bhow to apply\b|\bapplication (?:process|instructions)\b|"
    r"\bdiversity\b|\baccommodation\b|\bworking arrangement\b|\bwhy join us\b|"
    r"\bour values\b|\bwho we are\b|\bwhat we offer\b|\bwhen you join our team\b",
    re.IGNORECASE,
)


def _strip_heading_decoration(content: str) -> str:
    """Zero-width/invisible characters, a Markdown ATX leader (`#`..`######`),
    or a Markdown bold wrapper (`**...**`) -- stripped for classification
    purposes ONLY. Never applied to a `Claim`'s stored text/offsets: a
    heading line never becomes a `Claim` in any case (see
    `segment_description`), so this has no interaction with source-span
    fidelity at all.
    """
    stripped = _INVISIBLE_CHARS.sub("", content)
    stripped = _MARKDOWN_LEADER.sub("", stripped)
    bold = _MARKDOWN_BOLD.match(stripped)
    if bold is not None:
        stripped = bold.group(1)
    return stripped.strip()


def _is_titlecase_heading(content_no_colon: str) -> bool:
    words = content_no_colon.split()
    if not words:
        return False
    for word in words:
        bare = word.lower().rstrip(".,;:")
        if bare in _TITLECASE_STOPWORDS:
            continue
        first_alpha = next((ch for ch in word if ch.isalpha()), None)
        if first_alpha is not None and not first_alpha.isupper():
            return False
    return True


def _has_inline_colon_list(content: str) -> bool:
    """True when `content` contains a colon with non-empty text AFTER it
    on the SAME line, and that trailing text itself contains a comma --
    the explicit shape of "Experience with: Python, JavaScript" /
    "Proficient in: React, Node.js, GraphQL". A real section heading
    rendered with an internal colon essentially never also contains a
    comma-separated list after it; this is a structural rule, not a
    per-phrase special case.
    """
    idx = content.find(":")
    if idx == -1:
        return False
    trailing = content[idx + 1:].strip()
    if not trailing:
        return False
    return "," in trailing


def _matched_heading_families(content: str) -> list[_SectionKind]:
    has_required = bool(_REQUIRED_ROOT.search(content))
    has_qualification = bool(_QUALIFICATION_ROOT.search(content))
    has_preferred = bool(_PREFERRED_ROOT.search(content))
    has_learning = bool(_LEARNING_ROOT.search(content))
    has_responsibility = bool(_RESPONSIBILITY_ROOT.search(content))
    has_non_qualification = bool(_NON_QUALIFICATION_ROOT.search(content))

    # A bare `qualif*` root never fires REQUIRED when a `preferr*` root is
    # ALSO present on the same line -- "Preferred Qualifications" must
    # resolve to PREFERRED, never REQUIRED (the collision this
    # milestone's evaluation corpus names explicitly).
    required_fires = has_required or (has_qualification and not has_preferred)

    families: list[_SectionKind] = []
    if required_fires:
        families.append(_SectionKind.REQUIRED)
    if has_preferred:
        families.append(_SectionKind.PREFERRED)
    if has_learning:
        families.append(_SectionKind.LEARNING)
    if has_responsibility:
        families.append(_SectionKind.RESPONSIBILITY)
    if has_non_qualification:
        families.append(_SectionKind.SKIP)
    return families


def _classify_heading_line(line: str, content: str) -> _SectionKind | None:
    """Is `line` (whose bullet-stripped, trimmed content is `content`) a
    recognized section heading, and if so which `_SectionKind`? Returns
    `None` for ordinary content -- not heading-shaped at all, handled
    identically to today regardless of `current_kind`.

    A line that IS heading-shaped but matches no family below, or
    matches MORE THAN ONE family, returns `_SectionKind.UNKNOWN` --
    never forced to a single family by a fixed precedence order (see
    module docstring).
    """
    if _BULLET_PREFIX.match(line) is not None:
        return None  # a bulleted line is a list item, never a heading

    decorated = _strip_heading_decoration(content)
    if not decorated:
        return None
    if re.search(r"[.!?]\s*$", decorated):
        return None  # sentence-terminal punctuation -- never a heading
    if _has_inline_colon_list(decorated):
        return None  # "Experience with: Python, JavaScript" -- a claim, not a heading

    ends_with_bare_colon = decorated.endswith(":")
    content_no_colon = decorated[:-1].strip() if ends_with_bare_colon else decorated
    word_count = len(content_no_colon.split())
    if word_count == 0 or word_count > 7:
        return None

    is_all_caps = any(ch.isalpha() for ch in content_no_colon) and all(
        (not ch.isalpha()) or ch.isupper() for ch in content_no_colon
    )
    is_markdown_or_bold = decorated != content.strip()
    # Colon-termination, ALL-CAPS, and Markdown are each a STRONG signal
    # on their own (consistent with M10B's already-shipped, already-
    # tested colon-heading-reset precedent). Plain title-case with none
    # of those is comparatively WEAK -- a single bare capitalized word or
    # short phrase is structurally indistinguishable from an ordinary
    # one-item-per-line requirement/list value ("Python" on its own line
    # under an already-open "Requirements:" section). A regression this
    # milestone's own suite caught: that EXACT shape (single bare
    # titlecase word, no colon, no family root) must never become a
    # phantom heading and swallow a real requirement list item.
    has_strong_shape_signal = ends_with_bare_colon or is_all_caps or is_markdown_or_bold
    is_plain_titlecase = _is_titlecase_heading(content_no_colon)
    if not has_strong_shape_signal and not is_plain_titlecase:
        return None

    families = _matched_heading_families(content_no_colon)

    # Plain title-case ALONE, with no family-root corroboration, is not
    # enough to call a line a heading at all -- the exact fix for the
    # regression noted above. This DOES mean a rare, family-root-less
    # generic catch-all heading ("Additional Information") with no
    # colon/Markdown/ALL-CAPS is also left unrecognized (`UNKNOWN`
    # content is not reachable for it); that is an accepted, measured
    # tradeoff -- see docs/evaluation/MILESTONE_10C_SECTION_CLASSIFICATION.md's
    # completion addendum -- in exchange for never swallowing a real,
    # bare, one-item-per-line requirement value.
    if not has_strong_shape_signal and not families:
        return None

    if len(families) == 1:
        return families[0]
    return _SectionKind.UNKNOWN


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

    Milestone 10C: heading recognition is `_classify_heading_line()` (see
    module docstring) -- a structural shape gate plus anchored root-word
    families, replacing the old small exact-phrase table. A heading-shaped
    line matching no family, or more than one family, classifies as
    `_SectionKind.UNKNOWN` directly (no separate "unrecognized heading"
    fallback check is needed any more: the classifier itself already
    produces `UNKNOWN` for that case). `UNKNOWN`/`LEARNING` content is
    gated by the SAME `_looks_like_requirement` heuristic as "no section
    at all," and never receives a default necessity.
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

        for sent_start, sent_end in _split_sentences(content, description, content_start):
            sentence = description[sent_start:sent_end]
            if not in_recognized_section and not _looks_like_requirement(sentence):
                continue
            claims.append(Claim(text=sentence, start=sent_start, end=sent_end, necessity_hint=necessity_hint))

    return tuple(claims)
