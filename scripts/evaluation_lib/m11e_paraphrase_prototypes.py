"""Milestone 11-E Phase 3 -- three paraphrase-tolerant competency-matching
strategy prototypes, compared against
`evaluation/m11e/paraphrase_development_controls.json` BEFORE any
strategy is chosen for Phase 4.

Evaluation-only. Reuses the SAME bounded canonical vocabulary M11-C's
own `competency_extraction.py` already ships (duplicated here, not
imported, exactly like that module's own relationship to the
scripts/-side M11-C prototype it was compared against) plus the new,
auditable `gitscore.jobs.parsing.competency_aliases` table.
"""
from __future__ import annotations

import re

from gitscore.jobs.parsing.competency_aliases import ACTIVE_ALIAS_PATTERNS, AliasRelation, EXCLUDED_ALIAS_PATTERNS

# The same 17-tag canonical vocabulary M11-C shipped, duplicated here
# for comparison purposes only (never imported into production code).
CANONICAL_PATTERNS: tuple[tuple[str, "re.Pattern[str]"], ...] = (
    ("algorithms-data-structures", re.compile(
        r"\balgorithms?\s+and\s+data\s+structures?\b|\balgorithmic\s+(?:problem[-\s]solving|complexity)\b|"
        r"\bbig[-\s]o\s+analysis\b|\bdata\s+structures?\s+and\s+algorithms?\b", re.IGNORECASE)),
    ("concurrency", re.compile(
        r"\bconcurrency\b|\brace\s+conditions?\b|\block[-\s]free\b|\bmultithreading\b|"
        r"\bconcurrent\s+programming\b", re.IGNORECASE)),
    ("distributed-systems", re.compile(
        r"\bdistributed\s+systems?\b|\bconsensus\s+algorithms?\b|\bfault\s+tolerance\b", re.IGNORECASE)),
    ("system-design", re.compile(
        r"\bsystem\s+architecture\b|\bsystem\s+design\b|\bscalable\s+system\b|\bdistributed\s+architecture\b",
        re.IGNORECASE)),
    ("performance-optimization", re.compile(
        r"\bperformance[-\s]critical\b|\boptimizing\s+performance\b|\bperformance\s+optimization\b|"
        r"\bdebug(?:ging)?\s+and\s+optimiz\w+\b", re.IGNORECASE)),
    ("os-networking", re.compile(
        r"\boperating\s+systems?\s+internals\b|\btcp/ip\s+networking\b|\bprocess\s+scheduling\b|"
        r"\bnetworking\s+fundamentals\b|\boperating\s+systems?\b", re.IGNORECASE)),
    ("database-design", re.compile(
        r"\bdatabase\s+design\b|\brelational\s+schemas?\b|\bindexing\s+strategies\b|\bdatabase\s+internals\b",
        re.IGNORECASE)),
    ("ml-fundamentals", re.compile(
        r"\bml\s+fundamentals\b|\bmachine\s+learning\s+fundamentals\b|\boverfitting\b|\bregularization\b|"
        r"\bbias[-\s]variance\b|\bbasic\s+statistics\b", re.IGNORECASE)),
    ("gpu-parallel-computing", re.compile(
        r"\bgpu\s+programming\b|\bparallel\s+computing\b|\bhigh[-\s]performance\s+computing\b", re.IGNORECASE)),
    ("signal-processing", re.compile(
        r"\b(?:digital\s+)?signal\s+processing\b|\bffts?\b|\bfilter\s+design\b", re.IGNORECASE)),
    ("circuit-theory", re.compile(r"\bcircuit\s+theory\b|\banalog\s+electronics\b", re.IGNORECASE)),
    ("embedded-systems-design", re.compile(
        r"\bembedded\s+systems?\b|\bfirmware\b|\bresource[-\s]constrained\s+embedded\b", re.IGNORECASE)),
    ("control-systems", re.compile(
        r"\bcontrol\s+systems?\s+theory\b|\bpid\b|\bstate[-\s]space\s+methods?\b|\bcontrol\s+systems?\b",
        re.IGNORECASE)),
    ("computer-vision", re.compile(
        r"\bcomputer\s+vision\b|\bobject\s+detection\b|\bimage\s+segmentation\b", re.IGNORECASE)),
    ("cybersecurity-threat-modeling", re.compile(
        r"\bthreat\s+modeling\b|\battack\s+vectors?\b|\bsecure\s+coding\b|\bcybersecurity\b", re.IGNORECASE)),
    ("digital-logic", re.compile(r"\bdigital\s+logic(?:\s+design)?\b|\bboolean\s+algebra\b", re.IGNORECASE)),
    ("quantum-computing", re.compile(
        r"\bquantum\s+circuit\s+design\b|\bqubit\s+error\s+correction\b|\bquantum\s+computing\b",
        re.IGNORECASE)),
)

_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "with", "of", "in", "is", "are", "to", "for", "on", "at",
    "experience", "strong", "solid", "deep", "skills", "skill", "background", "knowledge",
    "understanding", "familiarity", "proficiency", "required", "preferred", "plus",
})


_WORD_TOKEN = re.compile(r"(?<!\\)[a-zA-Z][a-zA-Z0-9]*")
"""Excludes a letter immediately preceded by a literal backslash --
without this, tokenizing a regex PATTERN SOURCE string (not prose
text) merges the `b` of a `\\b` word-boundary anchor into the
following word (`\\bRTOS` -> the single bogus token `bRTOS`),
corrupting its stem. Confirmed as a real bug during this milestone's
own Phase 3 comparison run (`RTOS` stemmed to `rto` via the merged
5-letter token `brtos`, breaking the embedded-systems-design alias
match) -- fixed here, not left as a disclosed limitation, since it is
a straightforward tokenization defect, not a tradeoff."""


def _words(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z][a-zA-Z0-9]*", text.lower())


def _stem(word: str) -> str:
    """ONE small, fixed, deterministic suffix-stripping rule set --
    never context-dependent, never a dictionary lookup, never a
    statistical model. Only strips a suffix when the remainder is
    still >=4 characters, so short/ambiguous words are left alone."""
    for suffix, replacement in (("ically", ""), ("ization", "ize"), ("izations", "ize"),
                                 ("ications", "ic"), ("ations", ""), ("ation", ""),
                                 ("ical", ""), ("ing", ""), ("ies", "y"), ("ic", ""), ("s", "")):
        if word.endswith(suffix) and len(word) - len(suffix) + len(replacement) >= 4:
            return word[: -len(suffix)] + replacement
    return word


def _stemmed_text(text: str) -> str:
    return " ".join(_stem(w) for w in _words(text))


# Pre-stem every canonical/alias phrase ONCE, at import time, and
# compile a stemmed-text regex per tag -- the SAME phrase-structure
# matching Option A uses, just run against stemmed text on both sides.
def _stem_pattern_source(raw_pattern: str) -> str:
    # Patterns are literal alternations of \b-bounded phrases; stem each
    # literal word token inside them, leave regex metacharacters alone.
    def _stem_token(match: "re.Match[str]") -> str:
        return _stem(match.group(0).lower())

    return _WORD_TOKEN.sub(_stem_token, raw_pattern)


STEMMED_CANONICAL_PATTERNS: tuple[tuple[str, "re.Pattern[str]"], ...] = tuple(
    (tag, re.compile(_stem_pattern_source(pattern.pattern), re.IGNORECASE)) for tag, pattern in CANONICAL_PATTERNS
)
STEMMED_ACTIVE_ALIAS_PATTERNS: tuple[tuple[str, "re.Pattern[str]", AliasRelation], ...] = tuple(
    (tag, re.compile(_stem_pattern_source(pattern.pattern), re.IGNORECASE), relation)
    for tag, pattern, relation in ACTIVE_ALIAS_PATTERNS
)

_QUALIFYING_LEAD_IN = re.compile(
    # Two genuinely distinct real-world qualification-intent SHAPES,
    # either one sufficient on its own:
    # (1) a leading qualifier phrase ("experience with X", "familiar with X")
    r"\b(?:experience|knowledge|understanding|familiarity|proficiency|skills?|background|expertise|grounding|grasp)\s+"
    r"(?:with|of|in|building|optimizing|debugging)\b|\bstrong\b|\bsolid\b|\bdeep\b|\bcomfortable\b|"
    # (2) the equally common TRAILING shape ("<noun phrase> experience/
    # skills/knowledge/background is required/preferred/a plus/necessary")
    # -- confirmed missing from an earlier version of this pattern by this
    # milestone's own Phase 3 comparison run (4 of Option C's own false
    # negatives were exactly this shape: "Kernel development experience
    # is preferred.", "RTOS development experience is required.", ...).
    r"\b(?:is|are)\s+(?:required|preferred|necessary|a\s+plus)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Option A -- controlled semantic aliases: canonical phrases PLUS the new,
# curated, bounded alias table (SEMANTICALLY_EQUIVALENT +
# NARROWER_OR_MORE_SPECIFIC only) -- still exact-phrase matching, no
# stemming, no bag-of-words.
# ---------------------------------------------------------------------------

def match_option_a(text: str) -> list[tuple[str, AliasRelation]]:
    matches: list[tuple[str, AliasRelation]] = []
    for tag, pattern in CANONICAL_PATTERNS:
        if pattern.search(text):
            matches.append((tag, AliasRelation.SEMANTICALLY_EQUIVALENT))  # canonical counts as equivalent-confidence
    for tag, pattern, relation in ACTIVE_ALIAS_PATTERNS:
        if pattern.search(text):
            matches.append((tag, relation))
    return matches


# ---------------------------------------------------------------------------
# Option B -- contextual phrase interpretation: unordered keyword-overlap
# scoring per tag (bag-of-words), tolerant of any grammatical variation
# but blind to phrase STRUCTURE -- the deliberately looser candidate.
# ---------------------------------------------------------------------------

def _tag_keyword_sets() -> dict[str, set[str]]:
    keywords: dict[str, set[str]] = {}
    for tag, pattern in CANONICAL_PATTERNS:
        words = set(_stem(w) for w in re.findall(r"[a-zA-Z]+", pattern.pattern) if w.lower() not in _STOPWORDS and len(w) > 2)
        keywords.setdefault(tag, set()).update(words)
    for tag, pattern, _relation in ACTIVE_ALIAS_PATTERNS:
        words = set(_stem(w) for w in re.findall(r"[a-zA-Z]+", pattern.pattern) if w.lower() not in _STOPWORDS and len(w) > 2)
        keywords.setdefault(tag, set()).update(words)
    return keywords


_TAG_KEYWORDS = _tag_keyword_sets()


def match_option_b(text: str) -> list[tuple[str, AliasRelation]]:
    text_words = set(_stem(w) for w in _words(text) if w not in _STOPWORDS)
    matches: list[tuple[str, AliasRelation]] = []
    for tag, keywords in _TAG_KEYWORDS.items():
        overlap = text_words & keywords
        if len(overlap) >= 2:
            matches.append((tag, AliasRelation.SEMANTICALLY_EQUIVALENT))
    return matches


# ---------------------------------------------------------------------------
# Option C -- compositional deterministic matching: the SAME canonical +
# active-alias PHRASES as Option A, but matched against STEMMED text
# (both sides stemmed identically), so grammatical variation (plurals,
# "-ing"/"-ic" suffixes) is tolerated WITHOUT losing phrase structure or
# word order the way Option B's bag-of-words does. Requires a qualifying
# lead-in structure to be present somewhere in the sentence as an
# additional, bounded precision guard.
# ---------------------------------------------------------------------------

def match_option_c(text: str) -> list[tuple[str, AliasRelation]]:
    if not _QUALIFYING_LEAD_IN.search(text):
        return []
    stemmed = _stemmed_text(text)
    matches: list[tuple[str, AliasRelation]] = []
    for tag, pattern in STEMMED_CANONICAL_PATTERNS:
        if pattern.search(stemmed):
            matches.append((tag, AliasRelation.SEMANTICALLY_EQUIVALENT))
    for tag, pattern, relation in STEMMED_ACTIVE_ALIAS_PATTERNS:
        if pattern.search(stemmed):
            matches.append((tag, relation))
    return matches


STRATEGIES = {"option_a": match_option_a, "option_b": match_option_b, "option_c": match_option_c}
