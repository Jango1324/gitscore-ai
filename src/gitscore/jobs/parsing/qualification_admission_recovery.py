"""Milestone 11-G4 -- offline-only claim-admission recovery.

**NOT wired into the live parser.** `segment_description()` itself is
byte-unchanged (confirmed by a dedicated test, exactly like every
other module in this offline series). This module is a NEW, additive
caller alongside it -- never a replacement, never a modification.

**Root cause (M11-G3 Phase 6, confirmed here):** `segmentation.py`'s
own `_looks_like_requirement()` admission gate -- consulted only for
content OUTSIDE a recognized `REQUIRED`/`PREFERRED`/`RESPONSIBILITY`
section (i.e. unsectioned text, a preamble before the document's own
later real headings, or content under an `UNKNOWN`/`LEARNING`
heading) -- recognizes a narrower vocabulary than
`competency_extraction.py`'s own `_QUALIFYING_INTENT_V2` gate. The
latter additionally recognizes bare `strong`/`solid`/`deep`/
`comfortable`, and the leading-qualifier words `understanding`/
`background`/`expertise`/`grounding`/`grasp` (not just `experience`/
`knowledge of`/`familiar*`/`proficien*`/`skills?`, which the two
vocabularies already share). A sentence like "Strong understanding of
distributed systems." therefore never becomes a `Claim` at all outside
a recognized section, even though the offline competency extractor
would correctly recognize it.

**Strategy chosen (Phase 3 of the design doc): Option B -- an
offline-only recovery pass, not Option A (widening
`segmentation.py`'s own vocabulary, which would require production
changes outside this milestone's authorized scope) or Option C (a
shared, context-aware admission policy both parsers import, a larger
architectural change for a future milestone to consider).** This
module mirrors `segment_description()`'s own per-line loop shape
EXACTLY, but reuses every one of its REAL, unmodified internal helpers
via import (`_SectionKind`, `_SECTION_NECESSITY_HINT`, `_BULLET_PREFIX`,
`_classify_heading_line`, `_looks_like_requirement`, `_ends_incomplete`,
`_is_paragraph_gap`, `_line_content_span`, `_split_sentences`) -- zero
duplicated REGEX or admission LOGIC, only the orchestration shape is
mirrored, specifically so this module can never silently drift out of
sync with how `segment_description()` itself classifies headings,
joins soft-wrapped lines, or splits sentences.

The ONLY new decision this module makes is the one substitution at the
heart of the fix: for a line whose `current_kind` is NOT a recognized
section, where `segment_description()` would have excluded it (fails
`_looks_like_requirement`), this module ALSO checks
`_QUALIFYING_INTENT_V2` -- the SAME real gate
`extract_competency_qualifications_v2` already requires before it will
recognize anything -- and recovers the line as an ADDITIONAL `Claim`
only if that wider gate passes. A line segment_description() ALREADY
admits (via `_looks_like_requirement`, or via being inside a
recognized section) is never touched, never re-admitted, never
duplicated.

Recovering a `Claim` is never the same as confidently accepting its
content: every recovered `Claim` is returned in EXACTLY the same shape
`segment_description()`'s own real `Claim`s have (same `text`/`start`/
`end`/`necessity_hint`/`section_kind` computation), so it flows through
every EXISTING, unmodified downstream safety check (negation, narrative,
responsibility-lead, M11-G1's OR-list safety, M11-G2's section-aware
necessity resolution, `project_qualification`'s own conservative
projection rules) completely unchanged.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from gitscore.jobs.parsing.competency_extraction import _QUALIFYING_INTENT_V2
from gitscore.jobs.parsing.segmentation import (
    _BULLET_PREFIX,
    _SECTION_NECESSITY_HINT,
    Claim,
    _SectionKind,
    _classify_heading_line,
    _ends_incomplete,
    _is_paragraph_gap,
    _line_content_span,
    _looks_like_requirement,
    _split_sentences,
)
from gitscore.jobs.types import Necessity

_LINE_PATTERN = re.compile(r"[^\r\n]+")


@dataclass(frozen=True)
class RecoveredClaim:
    """A `Claim` the real `segment_description()` did NOT produce,
    together with the one reason it exists: the admission gate that
    excluded it would not have excluded it under the wider,
    qualifying-intent-aware check this module adds. Carrying the
    reason (rather than just a bare `Claim`) keeps this module's own
    effect auditable/diagnosable -- never a silent, unexplained extra
    claim appearing from nowhere.
    """

    claim: Claim
    recovery_reason: str = "qualifying_intent_outside_looks_like_requirement"


def recover_unadmitted_qualification_claims(description: str) -> tuple[RecoveredClaim, ...]:
    """Every additional claim `segment_description(description)` did
    NOT produce, but would be admitted under `competency_extraction.py`'s
    own, already-approved `_QUALIFYING_INTENT_V2` gate -- restricted to
    EXACTLY the gap `segment_description()` itself leaves: content
    outside a recognized `REQUIRED`/`PREFERRED`/`RESPONSIBILITY` section
    (and never content under a `SKIP` section, mirroring
    `segment_description()`'s own unconditional suppression there).

    Deterministic and pure, like `segment_description()` itself: same
    input always produces the same output, no side effects, no call
    into `segment_description()` at all (this module independently
    re-walks the same line/heading structure using the SAME real
    helpers, rather than post-filtering that function's own return
    value, so it can correctly track `current_kind` across headings
    exactly as that function does).
    """
    recovered: list[RecoveredClaim] = []
    current_kind: _SectionKind | None = None

    line_matches = list(_LINE_PATTERN.finditer(description))
    i = 0
    while i < len(line_matches):
        line_match = line_matches[i]
        line = line_match.group()
        line_start = line_match.start()

        content_span = _line_content_span(line, line_start)
        if content_span is None:
            i += 1
            continue
        content_start, content_end = content_span
        content = description[content_start:content_end]

        classified = _classify_heading_line(line, content)
        if classified is not None:
            current_kind = classified
            i += 1
            continue

        if current_kind is _SectionKind.SKIP:
            i += 1
            continue

        in_recognized_section = current_kind in (
            _SectionKind.REQUIRED, _SectionKind.PREFERRED, _SectionKind.RESPONSIBILITY,
        )

        block_end = content_end
        j = i + 1
        while j < len(line_matches) and _ends_incomplete(description[content_start:block_end]):
            next_match = line_matches[j]
            next_line = next_match.group()
            next_span = _line_content_span(next_line, next_match.start())
            if next_span is None:
                break
            next_content_start, next_content_end = next_span
            if _BULLET_PREFIX.match(next_line) is not None:
                break
            next_content = description[next_content_start:next_content_end]
            if _classify_heading_line(next_line, next_content) is not None:
                break
            if _is_paragraph_gap(description, block_end, next_content_start):
                break
            block_end = next_content_end
            j += 1

        content = description[content_start:block_end]

        if current_kind in (_SectionKind.UNKNOWN, _SectionKind.LEARNING):
            necessity_hint: Necessity | None = None
        else:
            necessity_hint = _SECTION_NECESSITY_HINT.get(current_kind, Necessity.REQUIRED)
        section_kind_name = current_kind.name if current_kind is not None else None

        if not in_recognized_section:
            for sent_start, sent_end in _split_sentences(content, description, content_start):
                sentence = description[sent_start:sent_end]
                if _looks_like_requirement(sentence):
                    continue  # segment_description() already admits this -- never duplicated
                if not _QUALIFYING_INTENT_V2.search(sentence):
                    continue  # not qualification-shaped even under the wider gate
                recovered.append(
                    RecoveredClaim(
                        claim=Claim(
                            text=sentence,
                            start=sent_start,
                            end=sent_end,
                            necessity_hint=necessity_hint,
                            section_kind=section_kind_name,
                        )
                    )
                )

        i = j

    return tuple(recovered)
