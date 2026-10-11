"""Milestone 8D.3 -- README evidence attribution context filtering.

Root cause this module fixes (`karpathy/llm.c` -> `language.cpp`, the
milestone's driving example): `evidence/extraction/readme.py`'s alias
matcher is a pure word-boundary text search over the ENTIRE README --
it has no notion of *where* in the document a mention sits. `llm.c`'s
real README has a "## notable forks" section that is a bullet list of
OTHER people's separate, externally-linked repositories (one C# port,
one C++/CUDA port, one Go port, ...), each describing ITS OWN tech
stack, not `llm.c`'s. "C++" appears there three times -- genuinely
present text, but never a claim that `llm.c` itself uses C++ (GitHub's
own language stats agree: C++ is ~3.5% of `llm.c`'s bytes, below the
5% significance floor `extraction/languages.py` already applies). This
is a provenance problem, not a matching-correctness problem: the alias
match itself is correct, the ATTRIBUTION of that match to the
repository's own technology stack is not.

This module adds two independent, deterministic, bounded signals that
`readme.py` uses to decide whether a textually-correct alias match is
still safe to attribute to the repository, WITHOUT any fuzzy inference,
embeddings, or LLM involvement -- plain structural/lexical checks only,
same spirit as `concepts/registry.py`'s existing `readme_unsafe_aliases`
(a per-ALIAS denylist); this is a per-CONTEXT denylist instead:

1. **Section heading** (`NON_IMPLEMENTATION_SECTION_HEADINGS`): a match
   falling under a markdown heading conventionally used for OTHER
   people's/projects' work (forks, related projects, acknowledgements,
   references, ...) is never attributed. This directly fixes the
   `llm.c` case and generalizes to any concept, not just C++ -- e.g. it
   also suppresses the "Related" sections ubiquitous across
   `sindresorhus`'s own small-library READMEs, which link to the
   AUTHOR'S other packages, not evidence of this one's tech stack.

2. **Local adjacency cues** (`_PRECEDING_EXCLUSION_CUES` /
   `_FOLLOWING_EXCLUSION_CUES`): a small, curated, DIRECTIONAL set of
   negation/future-intent phrases checked in a bounded window
   immediately before or after the match -- e.g. "does not use X"
   (explicit non-use, observed in `karpathy/nanochat`'s real README) or
   "X is on the roadmap" (future intent without implementation, observed
   in a real `Jango1324` fixture README). This is intentionally a LOCAL
   adjacency check, not a whole-sentence scan: a whole-sentence cue scan
   was evaluated and rejected (see docs/evaluation/
   MILESTONE_8D3_EVIDENCE_ATTRIBUTION.md's precision/recall tradeoff
   section) because generic comparison cues like "instead of"/"rather
   than" are directionally ambiguous at sentence scope -- "built in
   Python instead of C" would wrongly suppress the genuine, affirmed
   Python mention if "instead of" anywhere in the sentence were enough.
   Restricting to a bounded window immediately adjacent to the match
   keeps the directionality unambiguous: "unlike" (or "does not use",
   etc.) immediately BEFORE a match reliably negates that specific
   match; "is on the roadmap" immediately AFTER a match reliably defers
   that specific match. Comparison cues ("instead of", "rather than",
   "versus", "compared to") are deliberately NOT included for this
   reason -- a documented, intentional scope boundary, not an oversight.

Both signals are structural/lexical only: no part-of-speech tagging, no
dependency parsing, no semantic similarity, no per-technology
special-casing. `readme.py` is the only caller; nothing else imports
this module.
"""
from __future__ import annotations

import re

from gitscore.concepts.matching import alias_pattern

# Conventional README section headings used to list OTHER repositories'
# or people's work rather than this repository's own technology stack.
# Normalized (lowercased, markdown emphasis/trailing punctuation
# stripped, whitespace collapsed) before comparison -- see
# `_normalize_heading`.
#
# Directly observed in real fixture READMEs (evaluation/fixtures/):
#   "notable forks"   -- karpathy/llm.c, karpathy/llama2.c
#   "related"         -- many sindresorhus/* repos (links to the
#                         author's OTHER packages)
#   "acknowledgements" -- karpathy/nanochat, karpathy/nanoGPT
#   "references"      -- karpathy/minGPT
# The remaining entries are the same README convention generalized, not
# technology-specific: a bounded, curated set, not an open-ended list.
NON_IMPLEMENTATION_SECTION_HEADINGS = frozenset(
    {
        "notable forks",
        "forks",
        "related",
        "related projects",
        "related work",
        "see also",
        "alternatives",
        "similar projects",
        "inspired by",
        "acknowledgements",
        "acknowledgments",
        "credits",
        "references",
    }
)

# Checked in the bounded window immediately BEFORE a match. A cue here
# means whatever immediately follows is being described as explicitly
# NOT used, or not yet used, by this repository.
_PRECEDING_EXCLUSION_CUES = frozenset(
    {
        "unlike",
        "doesn't use",
        "does not use",
        "don't use",
        "do not use",
        "no longer use",
        "no longer uses",
        "no longer supports",
        "never uses",
        "never used",
        "without using",
        "not currently support",
        "not implemented in",
        "not implemented using",
        "plan to support",
        "plans to support",
        "planning to support",
        "intend to support",
        "intends to support",
        "will support",
        "will add support for",
        "future support for",
    }
)

# Checked in the bounded window immediately AFTER a match. A cue here
# means the match itself is being described as not-yet-implemented.
_FOLLOWING_EXCLUSION_CUES = frozenset(
    {
        "is planned",
        "is on the roadmap",
        "support is planned",
        "coming soon",
        "is not yet supported",
        "is not supported",
        "is not implemented",
        "is not used",
    }
)

# How far to look immediately before/after a match for an adjacency cue.
# Deliberately small and fixed -- a bounded window, not a sentence
# parser -- so the check stays local and directional (see module
# docstring for why whole-sentence scanning was rejected).
_ADJACENCY_RADIUS = 60

_HEADING_LINE = re.compile(r"^#{1,6}\s+(.*)$", re.MULTILINE)
_CODE_FENCE_LINE = re.compile(r"^```", re.MULTILINE)


def _normalize_heading(raw: str) -> str:
    cleaned = re.sub(r"[`*_]+", "", raw)
    cleaned = cleaned.strip().rstrip(":").strip().lower()
    return re.sub(r"\s+", " ", cleaned)


def _code_fence_spans(text: str) -> list[tuple[int, int]]:
    """Start/end offsets of every fenced code block (```...```).

    An odd trailing fence (malformed/unclosed README) is ignored rather
    than treating the rest of the document as one giant code block --
    defensive, not a correctness claim about malformed markdown.
    """
    fence_starts = [m.start() for m in _CODE_FENCE_LINE.finditer(text)]
    return [(fence_starts[i], fence_starts[i + 1]) for i in range(0, len(fence_starts) - 1, 2)]


def _heading_spans(text: str) -> list[tuple[int, str]]:
    """`(offset, normalized_heading_text)` for every ATX heading in
    `text`, in document order, excluding any heading-shaped line that
    falls inside a fenced code block (e.g. a shell comment like
    `# do this` inside a ```bash block is not a markdown heading).
    """
    fence_spans = _code_fence_spans(text)

    def _in_fence(offset: int) -> bool:
        return any(start <= offset < end for start, end in fence_spans)

    return [
        (match.start(), _normalize_heading(match.group(1)))
        for match in _HEADING_LINE.finditer(text)
        if not _in_fence(match.start())
    ]


class ReadmeContext:
    """Precomputed structural index over one README's text.

    Built once per `evidence_from_readme()` call and reused for every
    alias occurrence checked against it -- heading/code-fence scanning
    is O(README length), not O(occurrences x README length).
    """

    def __init__(self, text: str) -> None:
        self._headings = _heading_spans(text)

    def enclosing_heading(self, position: int) -> str | None:
        """The normalized text of the nearest heading at or before
        `position`, or `None` if `position` precedes every heading."""
        enclosing: str | None = None
        for start, normalized in self._headings:
            if start > position:
                break
            enclosing = normalized
        return enclosing


def build_context(text: str) -> ReadmeContext:
    return ReadmeContext(text)


def is_non_implementation_mention(text: str, start: int, end: int, context: ReadmeContext) -> bool:
    """True if the `text[start:end]` match should NOT be attributed to
    the repository as evidence -- see module docstring for the two
    signals checked.
    """
    heading = context.enclosing_heading(start)
    if heading is not None and heading in NON_IMPLEMENTATION_SECTION_HEADINGS:
        return True

    preceding = text[max(0, start - _ADJACENCY_RADIUS) : start]
    if any(alias_pattern(cue).search(preceding) for cue in _PRECEDING_EXCLUSION_CUES):
        return True

    following = text[end : end + _ADJACENCY_RADIUS]
    if any(alias_pattern(cue).search(following) for cue in _FOLLOWING_EXCLUSION_CUES):
        return True

    return False
