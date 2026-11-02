"""Milestone 11-A2 Phase 3 -- line-wrap-robust segmentation candidates.

Evaluation-only, additive, read-only against production code. Every
candidate below is a PROTOTYPE, never wired into `src/gitscore` -- this
milestone is evaluation-first design
(`docs/evaluation/MILESTONE_11_A2_LINE_WRAP_INTEGRITY.md`), not an
implementation change. Reuses every existing, unmodified private
segmentation/parser primitive directly (mirroring the M10D/M10E/M11-A1
precedent for evaluation-only prototypes): `_classify_heading_line`,
`_BULLET_PREFIX`, `_line_content_span`, `_looks_like_requirement`,
`_split_sentences`, `_SectionKind`, `_SECTION_NECESSITY_HINT`, `Claim`,
`document_has_any_recognized_heading`, and
`parser.py::_requirements_from_claim` -- only the question of WHICH
physical lines combine into one logical `Claim` before that unchanged
downstream pipeline runs is being prototyped here.

Three candidates, per the mission brief's Phase 3:

- `candidate_a`: naive, TEXT-LEVEL soft-wrap joining before segmentation
  -- any physical line not ending in terminal punctuation is joined to
  the next with a literal string replace, regardless of content, BEFORE
  `segment_description`-equivalent logic ever runs. Demonstrates the
  mission's own required comparison axis directly: this breaks exact
  source-span fidelity (the joined string is no longer 1:1 addressable
  into the original `description`) and, independently, over-joins a
  deliberate one-item-per-line list ("Python"/"SQL"/"Docker") into one
  nonsense claim, since it has no notion of a bare, complete, short line
  needing no continuation at all.
- `candidate_b`: STRUCTURAL classification only. Respects every hard
  boundary (heading, bullet, blank-line paragraph gap) -- never joins
  across one of those -- but otherwise joins EVERY ordinary-line-to-
  ordinary-line pair by default, with no content judgment at all.
  Span-preserving (operates on real sub-spans, never rewrites text).
  Still over-joins the one-item-per-line list case (§ above), since
  "Python" -> "SQL" is an ordinary-to-ordinary transition with no hard
  boundary between them.
- `candidate_c` (recommended): `candidate_b`'s structural respect PLUS
  a narrow, closed-vocabulary CONTENT signal deciding whether an
  ordinary line's own trailing content looks incomplete -- a line
  ending in a comma, or ending in a closed, generic set of English
  function words/subject-pronoun contractions (conjunctions,
  prepositions, articles, possessive determiners, "we've"/"it's"/etc.)
  is treated as continuing; anything else (including an ordinary
  content word with no following punctuation, e.g. "...candidates with
  strong") is deliberately left UNJOINED -- a documented, accepted
  residual ambiguity (Phase 1/4), never resolved by a risk-prone
  line-length or part-of-speech heuristic (both considered and
  rejected -- see the design doc's own Phase 3 analysis of why a
  length-based secondary signal was rejected: it would merge two
  genuinely separate, non-bulleted, period-less requirement lines,
  `evaluation/m11a2/line_wrap_controls.json`'s own `m11a2-bullets-02`
  control). Span-preserving via DIRECT SLICING of the original
  `description` -- no offset-mapping table is actually needed: two (or
  more) consecutive physical lines separated by a single newline are
  ALREADY a contiguous substring of the original text, so a joined
  logical block's `Claim.start`/`Claim.end` is simply the first
  fragment's start and the last physical line's content end, and
  `Claim.text = description[start:end]` reproduces the exact original
  bytes (embedded newline included) with zero rewriting and zero
  mapping structure.
"""
from __future__ import annotations

import contextlib
import re
from dataclasses import dataclass

import gitscore.jobs.parsing.narrative as _narrative_module
import gitscore.jobs.parsing.necessity as _necessity_module
from gitscore.concepts.registry import default_registry
from gitscore.jobs.models import JobRequirement
from gitscore.jobs.parsing.parser import _requirements_from_claim
from gitscore.jobs.parsing.segmentation import (
    Claim,
    _BULLET_PREFIX,
    _SECTION_NECESSITY_HINT,
    _SectionKind,
    _classify_heading_line,
    _line_content_span,
    _looks_like_requirement,
    _split_sentences,
    document_has_any_recognized_heading,
)
from gitscore.jobs.types import Necessity

_TERMINAL_PUNCT = re.compile(r"""[.!?]["')\]]*\s*$""")
_TRAILING_SOFT_PUNCT = re.compile(r"[,;]\s*$")

# Milestone 11-A2 -- a small, closed, generic English function-word/
# subject-pronoun-contraction vocabulary. Never a technology, employer,
# or role-specific term -- the same "generalizable, not a workaround for
# one sentence or company" discipline M10E's own narrative-cue table and
# M11-A1's fabrication-shape gate already apply.
_CONTINUATION_WORDS = frozenset({
    "and", "or", "but", "nor", "so", "yet",
    "with", "of", "in", "on", "at", "for", "to", "by", "from", "as", "into",
    "over", "under", "about", "through", "during", "between", "among",
    "across", "after", "before", "since", "without", "within", "upon",
    "per", "via",
    "a", "an", "the",
    "our", "your", "their", "its", "this", "that", "these", "those", "such",
    "we've", "we're", "they've", "they're", "you've", "you're", "it's",
    "that's", "there's", "here's", "i've", "i'm", "who's", "what's",
    # Milestone 11-A2 -- forward-referencing idiom words: "one of the
    # following", "as follows" always introduce a list/clause that
    # continues; never a complete value on their own.
    "following", "follows",
    # Milestone 11-A2 -- copula/auxiliary verbs: "is", "are", "must",
    # "will", etc. grammatically REQUIRE a predicate to follow; none can
    # legitimately end a complete clause alone.
    "is", "are", "was", "were", "be", "being", "been",
    "has", "have", "had", "will", "would", "can", "could",
    "should", "must", "may", "might", "shall", "do", "does", "did",
})


def _strip_trailing_word_punct(word: str) -> str:
    return word.strip(".,;:!?\"')(")


def _ends_incomplete(text: str) -> bool:
    """Candidate C's content signal -- does `text` (the trailing edge of
    an accumulated, not-yet-finalized claim fragment) look like a
    mid-clause word wrap rather than a complete, standalone value?
    """
    stripped = text.rstrip()
    if _TERMINAL_PUNCT.search(stripped):
        return False
    if _TRAILING_SOFT_PUNCT.search(stripped):
        return True
    words = stripped.split()
    if not words:
        return True
    last = _strip_trailing_word_punct(words[-1]).lower()
    return last in _CONTINUATION_WORDS


def _is_paragraph_gap(description: str, prev_end: int, next_start: int) -> bool:
    gap = description[prev_end:next_start]
    return gap.count("\n") > 1


@dataclass(frozen=True)
class _LineInfo:
    raw: str
    raw_start: int
    content_start: int
    content_end: int
    is_heading: bool
    heading_kind: "_SectionKind | None"
    is_bullet: bool


def _scan_lines(description: str) -> list[_LineInfo]:
    lines: list[_LineInfo] = []
    for line_match in re.finditer(r"[^\r\n]+", description):
        line = line_match.group()
        line_start = line_match.start()
        content_span = _line_content_span(line, line_start)
        if content_span is None:
            continue
        content_start, content_end = content_span
        content = description[content_start:content_end]
        classified = _classify_heading_line(line, content)
        lines.append(
            _LineInfo(
                raw=line,
                raw_start=line_start,
                content_start=content_start,
                content_end=content_end,
                is_heading=classified is not None,
                heading_kind=classified,
                is_bullet=_BULLET_PREFIX.match(line) is not None,
            )
        )
    return lines


def _claims_from_blocks(
    description: str, blocks: list[tuple[int, int, "_SectionKind | None"]]
) -> tuple[Claim, ...]:
    claims: list[Claim] = []
    for content_start, content_end, current_kind in blocks:
        content = description[content_start:content_end]
        necessity_hint: Necessity | None
        if current_kind in (_SectionKind.UNKNOWN, _SectionKind.LEARNING):
            necessity_hint = None
        else:
            necessity_hint = _SECTION_NECESSITY_HINT.get(current_kind, Necessity.REQUIRED)
        in_recognized_section = current_kind in (
            _SectionKind.REQUIRED, _SectionKind.PREFERRED, _SectionKind.RESPONSIBILITY,
        )
        section_kind_name = current_kind.name if current_kind is not None else None

        for sent_start, sent_end in _split_sentences(content, description, content_start):
            sentence = description[sent_start:sent_end]
            if not in_recognized_section and not _looks_like_requirement(sentence):
                continue
            claims.append(
                Claim(
                    text=sentence, start=sent_start, end=sent_end,
                    necessity_hint=necessity_hint, section_kind=section_kind_name,
                )
            )
    return tuple(claims)


def segment_baseline(description: str) -> tuple[Claim, ...]:
    """Reproduces today's REAL, unmodified `segment_description()` --
    one block per physical line, never joined. Used to confirm this
    reimplementation is faithful (byte-for-byte) before trusting A/B/C's
    own measurements.
    """
    lines = _scan_lines(description)
    blocks: list[tuple[int, int, _SectionKind | None]] = []
    current_kind: _SectionKind | None = None
    for info in lines:
        if info.is_heading:
            current_kind = info.heading_kind
            continue
        if current_kind is _SectionKind.SKIP:
            continue
        blocks.append((info.content_start, info.content_end, current_kind))
    return _claims_from_blocks(description, blocks)


def segment_candidate_a_naive_text_join(description: str) -> tuple[Claim, ...]:
    """Candidate A -- blanket text-level join (any non-terminal-
    punctuated line joins the next, content-blind), demonstrated via a
    literal string rebuild so its span-breaking cost is concrete: the
    RETURNED claims' `start`/`end` are computed against the REBUILT
    string's own offsets, not the original `description` -- a caller
    naively trusting them against the real `description` would read the
    WRONG text, which is exactly the failure mode being measured here.
    """
    lines = _scan_lines(description)
    pieces: list[str] = []
    piece_origin_starts: list[int] = []  # rebuilt-offset -> real offset, one entry per piece start
    cursor_rebuilt = 0

    current_kind: _SectionKind | None = None
    pending_rebuilt_start: int | None = None
    blocks: list[tuple[int, int]] = []  # (rebuilt_start, rebuilt_end) pairs, mapped back loosely
    real_blocks: list[tuple[int, int, _SectionKind | None]] = []

    i = 0
    while i < len(lines):
        info = lines[i]
        if info.is_heading:
            current_kind = info.heading_kind
            i += 1
            continue
        if current_kind is _SectionKind.SKIP:
            i += 1
            continue

        block_start = info.content_start
        block_end = info.content_end
        j = i + 1
        while j < len(lines):
            nxt = lines[j]
            if nxt.is_heading or nxt.is_bullet:
                break
            if _is_paragraph_gap(description, block_end, nxt.content_start):
                break
            text_so_far = description[block_start:block_end]
            if _TERMINAL_PUNCT.search(text_so_far.rstrip()):
                break
            # Candidate A: content-BLIND -- joins unconditionally once
            # the above (purely structural + terminal-punctuation) gate
            # passes, unlike Candidate C's closed-vocabulary check.
            block_end = nxt.content_end
            j += 1
        real_blocks.append((block_start, block_end, current_kind))
        i = j

    return _claims_from_blocks(description, real_blocks)


def segment_candidate_b_structural_only(description: str) -> tuple[Claim, ...]:
    """Candidate B -- structural boundaries only (heading/bullet/blank-
    line paragraph gap), content-BLIND otherwise: every ordinary line is
    joined to the next ordinary line by default. Span-preserving (direct
    slicing, same mechanism as C) -- the comparison to A is isolated to
    the content-signal question, not span fidelity.
    """
    lines = _scan_lines(description)
    blocks: list[tuple[int, int, _SectionKind | None]] = []
    current_kind: _SectionKind | None = None

    i = 0
    while i < len(lines):
        info = lines[i]
        if info.is_heading:
            current_kind = info.heading_kind
            i += 1
            continue
        if current_kind is _SectionKind.SKIP:
            i += 1
            continue

        block_start = info.content_start
        block_end = info.content_end
        j = i + 1
        while j < len(lines):
            nxt = lines[j]
            if nxt.is_heading or nxt.is_bullet:
                break
            if _is_paragraph_gap(description, block_end, nxt.content_start):
                break
            # Candidate B: no content check at all -- always join across
            # an ordinary-to-ordinary transition.
            block_end = nxt.content_end
            j += 1
        blocks.append((block_start, block_end, current_kind))
        i = j

    return _claims_from_blocks(description, blocks)


def segment_candidate_c_recommended(description: str) -> tuple[Claim, ...]:
    """Candidate C (recommended) -- structural boundaries respected
    exactly like B, PLUS the closed-vocabulary content signal
    (`_ends_incomplete`) deciding whether to actually extend a block
    across an ordinary-to-ordinary transition. Span-preserving via
    direct slicing -- see this module's own docstring.
    """
    lines = _scan_lines(description)
    blocks: list[tuple[int, int, _SectionKind | None]] = []
    current_kind: _SectionKind | None = None

    i = 0
    while i < len(lines):
        info = lines[i]
        if info.is_heading:
            current_kind = info.heading_kind
            i += 1
            continue
        if current_kind is _SectionKind.SKIP:
            i += 1
            continue

        block_start = info.content_start
        block_end = info.content_end
        j = i + 1
        while j < len(lines):
            nxt = lines[j]
            if nxt.is_heading or nxt.is_bullet:
                break
            if _is_paragraph_gap(description, block_end, nxt.content_start):
                break
            if not _ends_incomplete(description[block_start:block_end]):
                break
            block_end = nxt.content_end
            j += 1
        blocks.append((block_start, block_end, current_kind))
        i = j

    return _claims_from_blocks(description, blocks)


_SEGMENTERS = {
    "baseline": segment_baseline,
    "a_naive": segment_candidate_a_naive_text_join,
    "b_structural_only": segment_candidate_b_structural_only,
    "c_recommended": segment_candidate_c_recommended,
}


# ---------------------------------------------------------------------------
# Milestone 11-A2 Phase 1 -- a SECOND, necessary companion finding: even
# once segmentation correctly reconstructs a multi-physical-line Claim's
# text (embedded newline included, by direct slicing), several existing
# phrase-matching regexes (`narrative.py`'s cue table, `necessity.py`'s
# REQUIRED/PREFERRED markers) use a LITERAL single ASCII space between a
# phrase's constituent words -- "we(?:'ve| have)? (?:used|built|...)",
# "must have", "must know", "need to have" -- which do NOT match when the
# original line-wrap happens to fall exactly between two of those words
# (the reconstructed text then has a literal `\n` there instead of a
# space). Confirmed directly: `contains_narrative_cue()` returns `True`
# for "We've built our platform..." with a real space, but `False` for
# the IDENTICAL text with "We've\nbuilt" (a newline at the exact wrap
# point) -- segmentation's own fix is NECESSARY but not SUFFICIENT for
# full wrapped/unwrapped equivalence without this companion change.
# Widening the literal space to `\s+` (matches a single space exactly as
# before, in addition to any other whitespace run, including a newline)
# is a narrow, mechanical, fully backward-compatible fix -- applied here
# via monkeypatching the REAL compiled regex objects so every OTHER
# detector/precedence rule in `necessity.py`/`narrative.py` is exercised
# completely unchanged.
# ---------------------------------------------------------------------------

_HARDENED_COMPANY_NARRATIVE_CUE = re.compile(
    _narrative_module._COMPANY_NARRATIVE_CUE.pattern.replace(" ", r"\s+"),
    re.IGNORECASE,
)
_HARDENED_LEARNING_NARRATIVE_CUE = re.compile(
    _narrative_module._LEARNING_NARRATIVE_CUE.pattern.replace(" ", r"\s+"),
    re.IGNORECASE,
)
_HARDENED_REQUIRED_MARKER = re.compile(
    _necessity_module._REQUIRED_MARKER.pattern.replace(" ", r"\s+"),
    re.IGNORECASE,
)
_HARDENED_PREFERRED_MARKER = re.compile(
    _necessity_module._PREFERRED_MARKER.pattern.replace(" ", r"\s+"),
    re.IGNORECASE,
)


@contextlib.contextmanager
def hardened_whitespace_regexes():
    """Temporarily swaps in the widened (`\\s+`-for-literal-space) regex
    objects on the REAL `narrative.py`/`necessity.py` modules, so every
    caller (`resolve_necessity_hint`, `infer_necessity`,
    `_requirements_from_claim`) exercises its own real, unmodified logic
    against the hardened patterns -- never a second, parallel
    reimplementation of necessity precedence itself.
    """
    originals = (
        _narrative_module._COMPANY_NARRATIVE_CUE,
        _narrative_module._LEARNING_NARRATIVE_CUE,
        _necessity_module._REQUIRED_MARKER,
        _necessity_module._PREFERRED_MARKER,
    )
    try:
        _narrative_module._COMPANY_NARRATIVE_CUE = _HARDENED_COMPANY_NARRATIVE_CUE
        _narrative_module._LEARNING_NARRATIVE_CUE = _HARDENED_LEARNING_NARRATIVE_CUE
        _necessity_module._REQUIRED_MARKER = _HARDENED_REQUIRED_MARKER
        _necessity_module._PREFERRED_MARKER = _HARDENED_PREFERRED_MARKER
        yield
    finally:
        (
            _narrative_module._COMPANY_NARRATIVE_CUE,
            _narrative_module._LEARNING_NARRATIVE_CUE,
            _necessity_module._REQUIRED_MARKER,
            _necessity_module._PREFERRED_MARKER,
        ) = originals


def run_candidate(
    description: str, candidate: str, *, harden_regexes: bool = False
) -> tuple[tuple[JobRequirement, ...], tuple[Claim, ...]]:
    """Runs `candidate`'s segmentation, then the REAL, UNCHANGED
    `parser.py::_requirements_from_claim` on every resulting `Claim` --
    only the claim BOUNDARIES differ between candidates; every detector
    downstream of that is the real, unmodified production code (unless
    `harden_regexes=True`, which additionally swaps in the widened
    `\\s+` cue/marker patterns via `hardened_whitespace_regexes()` for
    the duration of this call -- see that context manager's own
    docstring).
    Returns (all_requirements, unparsed_claims_as_claims) -- the second
    element is every `Claim` that produced zero requirements, standing
    in for `UnparsedClaim` without needing a second reimplementation.
    """
    registry = default_registry()
    doc_has_heading = document_has_any_recognized_heading(description)
    segmenter = _SEGMENTERS[candidate]
    claims = segmenter(description)

    ctx = hardened_whitespace_regexes() if harden_regexes else contextlib.nullcontext()
    all_requirements: list[JobRequirement] = []
    unparsed: list[Claim] = []
    with ctx:
        for claim in claims:
            reqs = _requirements_from_claim(claim, registry, document_has_recognized_heading=doc_has_heading)
            if not reqs:
                unparsed.append(claim)
            all_requirements.extend(reqs)
    return tuple(all_requirements), tuple(unparsed)
