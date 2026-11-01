"""Milestone 10C Phase 3 -- THREE candidate heading-classification designs,
evaluated side-by-side against `evaluation/m10c/heading_controls.json`.

**Evaluation-only. None of this is imported by, or wired into,
`src/gitscore`.** These are unapproved candidate designs being measured,
not a production change. See `docs/evaluation/MILESTONE_10C_SECTION_CLASSIFICATION.md`
Phase 3 for the full comparison writeup this module's numbers feed.

Each strategy exposes one function, `classify(line: str) -> HeadingCall`,
operating on ONE line of text in isolation (no document-level state) --
exactly the granularity `jobs/parsing/segmentation.py`'s heading-recognition
step itself operates at today. A `HeadingCall` never claims a scoring-
relevant necessity -- that is a separate, later pipeline step (`necessity.py`)
this module has nothing to do with.

Three independent designs, per Phase 3's brief:

- Strategy A (`classify_a`): expanded exact-match vocabulary, normalized.
  A direct generalization of TODAY's production design
  (`jobs/parsing/segmentation.py`'s `_HEADING_KIND` table) -- a bigger
  table, better Unicode/Markdown normalization, but still fundamentally a
  closed-world lookup. By construction it CANNOT distinguish "heading-
  shaped but not in my table" from "not a heading at all" -- both report
  `is_heading=False` -- which is exactly today's Root Cause 1/2
  precondition, just with a narrower blind spot.

- Strategy B (`classify_b`): a two-part design -- a structural
  "heading-shape" gate (short, title-cased/colon-terminated/Markdown/
  uppercase, not itself a bullet, not sentence-terminated) completely
  independent of word content, THEN an anchored root-word family
  classifier with an explicit precedence order over ties.

- Strategy C (`classify_c`): Strategy B's shape gate and family roots,
  PLUS an ambiguity-aware purpose output -- a line matching MORE THAN ONE
  family is reported as `AMBIGUOUS` with its candidate families listed,
  never silently forced into one winner by a fixed precedence order. (An
  earlier draft of this module ALSO reused `parser.py`'s
  `_TECHNICAL_LEAD_IN` pattern here as a heading-shape exclusion; tried
  in production and reverted after a real regression -- see `classify_c`'s
  own comment and the Milestone 10C design doc's completion addendum.)

Both B and C share one additional, implementation-discovered shape rule
(not in this module's original draft, added after the real production
regression suite caught it): plain title-case alone, with no colon/
ALL-CAPS/Markdown AND no matched family root, is too weak a signal to
call a line heading-shaped at all -- otherwise a single bare capitalized
word standing alone on its own line (e.g. "Python" in an un-bulleted,
one-item-per-line requirement list) is swallowed as a phantom heading.
"""
from __future__ import annotations

import re
import string
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Shared primitives (used by B and C; A uses its own separate normalizer).
# ---------------------------------------------------------------------------

_INVISIBLE_CHARS = re.compile(r"[​‌‍﻿]")
_MARKDOWN_LEADER = re.compile(r"^#{1,6}\s*")
_MARKDOWN_BOLD = re.compile(r"^\*\*(.*)\*\*$")
_BULLET_PREFIX = re.compile(r"^\s*(?:[-*•◦]|\d+[.)])\s+")

_TITLECASE_STOPWORDS = {"a", "an", "the", "of", "in", "on", "and", "or", "to", "for", "at", "by", "as"}


def _strip_decorations(raw_line: str) -> str:
    s = _INVISIBLE_CHARS.sub("", raw_line)
    s = s.strip()
    s = _MARKDOWN_LEADER.sub("", s)
    bold = _MARKDOWN_BOLD.match(s)
    if bold is not None:
        s = bold.group(1)
    s = re.sub(r"\s+", " ", s, flags=re.UNICODE).strip()
    return s


def _is_bulleted(raw_line: str) -> bool:
    return _BULLET_PREFIX.match(raw_line) is not None


def _first_alpha_upper(word: str) -> bool | None:
    for ch in word:
        if ch.isalpha():
            return ch.isupper()
    return None  # no alphabetic character in this "word" at all


def _is_titlecase(content_no_colon: str) -> bool:
    words = content_no_colon.split()
    if not words:
        return False
    for word in words:
        bare = word.lower().rstrip(string.punctuation)
        if bare in _TITLECASE_STOPWORDS:
            continue
        is_upper = _first_alpha_upper(word)
        if is_upper is False:
            return False
    return True


def _has_inline_colon_list(content: str) -> bool:
    """True when `content` contains a colon with non-empty text AFTER it
    on the same line, and that trailing text itself contains a comma --
    the explicit, generalizable shape of "Experience with: Python,
    JavaScript" / "Proficient in: React, Node.js, GraphQL" (Phase 3's
    named collision). A real section heading rendered with an internal
    colon essentially never also contains a comma-separated list after
    it -- this is a structural rule, not a per-phrase special case.
    """
    idx = content.find(":")
    if idx == -1:
        return False
    trailing = content[idx + 1:].strip()
    if not trailing:
        return False  # colon is the LAST character -- a different case
    return "," in trailing


def _heading_shape(raw_line: str, decorated: str, families: list[str]) -> bool:
    """Milestone 10C implementation fix (found via the real production
    regression suite, `tests/test_job_parser_segmentation.py::
    test_newline_separated_requirements_without_bullets`, after this
    module's first draft): plain title-case alone (no colon/ALL-CAPS/
    Markdown) is a WEAK signal -- a single bare capitalized word or short
    phrase is structurally indistinguishable from an ordinary one-item-
    per-line requirement/list value ("Python" on its own line under an
    open "Requirements:" section). `families` (already computed by the
    caller) must be non-empty to accept the weak signal alone; a STRONG
    signal (colon/ALL-CAPS/Markdown) needs no such corroboration. This
    mirrors `src/gitscore/jobs/parsing/segmentation.py::_classify_heading_line`
    exactly -- kept in sync after the production fix.
    """
    if _is_bulleted(raw_line):
        return False
    if not decorated:
        return False
    if re.search(r"[.!?]\s*$", decorated):
        return False  # sentence-terminal punctuation -- never a heading
    if _has_inline_colon_list(decorated):
        return False
    ends_with_bare_colon = decorated.endswith(":") and not _has_inline_colon_list(decorated)
    content_no_colon = decorated[:-1].strip() if decorated.endswith(":") else decorated
    word_count = len(content_no_colon.split())
    if word_count == 0 or word_count > 7:
        return False
    is_markdown_or_bold = decorated != raw_line.strip().lstrip("\t")  # decoration stripping actually changed something structural
    is_upper = any(c.isalpha() for c in content_no_colon) and all(
        (not c.isalpha()) or c.isupper() for c in content_no_colon
    )
    has_strong_shape_signal = bool(
        ends_with_bare_colon
        or is_upper
        or is_markdown_or_bold
        or raw_line.strip().startswith("#")
        or raw_line.strip().startswith("**")
    )
    is_plain_titlecase = _is_titlecase(content_no_colon)
    if not has_strong_shape_signal and not is_plain_titlecase:
        return False
    if not has_strong_shape_signal and not families:
        return False
    return True


# ---------------------------------------------------------------------------
# Family root patterns, shared by Strategy B and Strategy C.
# ---------------------------------------------------------------------------

_REQ_ROOT = re.compile(r"\brequir\w*\b|\bmust[- ]have\w*\b|\bmandatory\b", re.IGNORECASE)
_QUALIF_ROOT = re.compile(r"\bqualif\w*\b", re.IGNORECASE)
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
_NON_QUALIFICATION_ROOT = re.compile(
    r"^about\b|\bbenefit\w*\b|\bperk\w*\b|\bcompensation\b|\bsalary\b|"
    r"\bequal opportunity\b|\bhow to apply\b|\bapplication (?:process|instructions)\b|"
    r"\bdiversity\b|\baccommodation\b|\bworking arrangement\b|\bwhy join us\b|"
    r"\bour values\b|\bwho we are\b|\bwhat we offer\b|\bwhen you join our team\b",
    re.IGNORECASE,
)


def _matched_families(content: str) -> list[str]:
    has_req = bool(_REQ_ROOT.search(content))
    has_qualif = bool(_QUALIF_ROOT.search(content))
    has_pref = bool(_PREFERRED_ROOT.search(content))
    has_learn = bool(_LEARNING_ROOT.search(content))
    has_resp = bool(_RESPONSIBILITY_ROOT.search(content))
    has_nonqual = bool(_NON_QUALIFICATION_ROOT.search(content))

    required_fires = has_req or (has_qualif and not has_pref)
    families = []
    if required_fires:
        families.append("REQUIRED")
    if has_pref:
        families.append("PREFERRED")
    if has_learn:
        families.append("LEARNING")
    if has_resp:
        families.append("RESPONSIBILITY")
    if has_nonqual:
        families.append("NON_QUALIFICATION")
    return families


# ---------------------------------------------------------------------------
# HeadingCall result type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HeadingCall:
    is_heading: bool
    section: str | None  # one of the 6 section_values, "AMBIGUOUS", or None
    candidates: tuple[str, ...] = field(default_factory=tuple)  # populated only for AMBIGUOUS


# ---------------------------------------------------------------------------
# Strategy A -- expanded exact-match vocabulary, normalized.
# ---------------------------------------------------------------------------

_REQUIRED_A = {
    "requirements", "required qualifications", "qualifications", "minimum qualifications",
    "basic qualifications", "must have", "must haves", "required skills", "minimum requirements",
    "must-have skills", "must have skills", "technical skills",
}
_PREFERRED_A = {
    "preferred qualifications", "preferred skills", "preferred", "nice to have", "nice-to-have",
    "nice to haves", "bonus points", "bonus", "a plus",
}
_RESPONSIBILITY_A = {
    "responsibilities", "what you'll do", "what you will do", "the role", "duties",
    "key responsibilities", "job duties", "position responsibilities", "a day in this role",
    "duties and responsibilities",
}
_LEARNING_A = {
    "skills you will learn", "skills you'll learn", "what you will learn", "what you'll learn",
    "skills you'll gain", "learning opportunities", "growth opportunities",
}
_NON_QUALIFICATION_A = {
    "benefits", "perks", "about us", "about the company", "about the team", "compensation",
    "salary", "salary range", "what we offer", "equal opportunity employer", "how to apply",
    "our values", "who we are", "why join us", "diversity", "diversity and inclusion",
    "perks and benefits", "about soti", "about manulife", "about manulife and john hancock",
    "working arrangement", "application process", "application instructions",
    "when you join our team",
}

_FAMILY_TABLE_A: dict[str, str] = {}
for _phrase in _REQUIRED_A:
    _FAMILY_TABLE_A[_phrase] = "REQUIRED"
for _phrase in _PREFERRED_A:
    _FAMILY_TABLE_A[_phrase] = "PREFERRED"
for _phrase in _RESPONSIBILITY_A:
    _FAMILY_TABLE_A[_phrase] = "RESPONSIBILITY"
for _phrase in _LEARNING_A:
    _FAMILY_TABLE_A[_phrase] = "LEARNING"
for _phrase in _NON_QUALIFICATION_A:
    _FAMILY_TABLE_A[_phrase] = "NON_QUALIFICATION"


def _normalize_for_exact_match(raw_line: str) -> str:
    s = _INVISIBLE_CHARS.sub("", raw_line)
    s = s.strip()
    s = _MARKDOWN_LEADER.sub("", s)
    bold = _MARKDOWN_BOLD.match(s)
    if bold is not None:
        s = bold.group(1)
    s = re.sub(r"\s+", " ", s, flags=re.UNICODE).strip()
    if s.endswith(":"):
        s = s[:-1].strip()
    return s.lower()


def classify_a(raw_line: str) -> HeadingCall:
    """Strategy A -- deliberately NO notion of "heading-shaped but
    unrecognized": a normalized phrase either IS one of the (larger, but
    still closed) table's entries, or Strategy A reports `is_heading=False`
    -- indistinguishable from ordinary prose, exactly like today's
    production blind spot (M10A Root Cause 1/2's precondition), just with
    a narrower miss rate.
    """
    if _is_bulleted(raw_line):
        return HeadingCall(is_heading=False, section=None)
    normalized = _normalize_for_exact_match(raw_line)
    section = _FAMILY_TABLE_A.get(normalized)
    if section is None:
        return HeadingCall(is_heading=False, section=None)
    return HeadingCall(is_heading=True, section=section)


# ---------------------------------------------------------------------------
# Strategy B -- anchored pattern families, shape gate + fixed precedence.
# ---------------------------------------------------------------------------


def _content_no_colon(decorated: str) -> str:
    return decorated[:-1].strip() if decorated.endswith(":") else decorated


def classify_b(raw_line: str) -> HeadingCall:
    decorated = _strip_decorations(raw_line)
    content = _content_no_colon(decorated)
    families = _matched_families(content) if content else []
    if not _heading_shape(raw_line, decorated, families):
        return HeadingCall(is_heading=False, section=None)

    if not families:
        return HeadingCall(is_heading=True, section="UNKNOWN")
    # Fixed total-order precedence (M10A section 6.1's own proposal):
    # REQUIRED > PREFERRED > LEARNING > RESPONSIBILITY > NON_QUALIFICATION.
    for candidate in ("REQUIRED", "PREFERRED", "LEARNING", "RESPONSIBILITY", "NON_QUALIFICATION"):
        if candidate in families:
            return HeadingCall(is_heading=True, section=candidate)
    return HeadingCall(is_heading=True, section="UNKNOWN")  # unreachable in practice


# ---------------------------------------------------------------------------
# Strategy C -- B's shape gate/roots + honest ambiguity instead of forced
# precedence. Milestone 10C IMPLEMENTATION NOTE: an earlier draft of this
# function also excluded a bare, colon-terminated requirement-claim
# lead-in ("Experience with the following:") from heading consideration
# by reusing `parser.py`'s `_TECHNICAL_LEAD_IN` pattern. That exclusion
# was tried in production and REVERTED after
# `tests/test_m10b_section_state_safety.py::test_non_bulleted_colon_heading_still_resets_state`
# caught a real regression: such a line, inside an already-open
# recognized section, must still reset state to UNKNOWN (Milestone 10B's
# existing, tested behavior) -- excluding it from heading detection
# entirely let it fall through as an ordinary claim instead. Removed here
# too, so this module stays byte-for-byte behaviorally in sync with what
# actually shipped (`segmentation.py::_classify_heading_line`) -- see
# docs/evaluation/MILESTONE_10C_SECTION_CLASSIFICATION.md's completion
# addendum for the full account.
# ---------------------------------------------------------------------------


def classify_c(raw_line: str) -> HeadingCall:
    decorated = _strip_decorations(raw_line)
    content = _content_no_colon(decorated)
    families = _matched_families(content) if content else []
    if not _heading_shape(raw_line, decorated, families):
        return HeadingCall(is_heading=False, section=None)

    if not families:
        return HeadingCall(is_heading=True, section="UNKNOWN")
    if len(families) == 1:
        return HeadingCall(is_heading=True, section=families[0])
    # Strategy C's differentiator from B: a line matching MORE THAN ONE
    # family is reported as AMBIGUOUS with its candidates, never silently
    # collapsed to one via a fixed precedence order.
    return HeadingCall(is_heading=True, section="AMBIGUOUS", candidates=tuple(families))


STRATEGIES: dict[str, "callable"] = {
    "A_expanded_exact_match": classify_a,
    "B_anchored_patterns_precedence": classify_b,
    "C_structured_detection_plus_purpose": classify_c,
}
