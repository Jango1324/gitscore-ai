"""Milestone 11-G23 -- candidate-profile heading policies (OFFLINE research adapters).

Designed against the DEV controls (`evaluation/m11g23/controls_dev.json`) and the design-visible historical
corpora only. The EVAL controls are run once, after this file's SHA-256 is recorded in
`evaluation/m11g23/policy_design_freeze.json`. Nothing here is imported by `src/gitscore`.

  P0  production parser v15 (replica, no hooks)
  P1  additional candidate-profile heading recognition: a closed vocabulary of candidate-profile heading
      frames rescues a heading-shaped line from UNKNOWN (zero families) or from the `^about` SKIP root
      ("About you") and maps it to REQUIRED, or to PREFERRED when the heading itself signals optionality
  P2  P1 + section-aware structure: curly apostrophes normalised for every family, bare sentence-case
      candidate-profile heading lines, two-line (wrapped) candidate-profile headings, family-less attribute
      sub-headings inherit an open REQUIRED/PREFERRED section, list-section paragraph reset
  P3  P1 headings + the existing clause-local G21 qualification-intent decision as the section default:
      under a candidate-profile heading a claim gets the section's necessity only when G21 reads it as a
      qualification ('qual'); otherwise it is treated exactly like UNKNOWN-section content
  P4  narrow hybrid, defined after the DEV comparison: P1 + bare sentence-case candidate-profile lines +
      two-line candidate-profile headings + attribute sub-heading inheritance (SELECTED; see the design freeze)

Every vocabulary is a closed set of generic heading FRAMES ("about you", "what you bring", "the ideal
candidate"), never technology-, employer- or role-specific words. A rescue applies only where production
recognises NO family on the line (or only the `^about` SKIP root on "About you"), so every heading production
already classifies keeps its kind.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

import m11g23_harness as hz

from gitscore.jobs.parsing import segmentation as seg

K = seg._SectionKind
_I = re.IGNORECASE

_CURLY = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-"})


def _norm(text: str) -> str:
    return text.translate(_CURLY)


# Closed candidate-profile heading frames, anchored at the start of the (decoration-stripped) heading.
CP_HEADING = re.compile(
    r"^(?:"
    r"about\s+(?:you|yourself|the\s+candidate)"
    r"|who\s+you\s+are"
    r"|(?:who|what)\s+we(?:'re|\s+are)\s+looking\s+for|what\s+we\s+look\s+for"
    r"|(?:what|who)\s+we\s+(?:need|want)(?:\s+to\s+see|\s+from\s+you)?"
    r"|(?:what\s+|experience\s+)?you(?:'ll|\s+will)?\s+bring"
    r"|what\s+you(?:'ll|\s+will)?\s+need(?:\s+to\s+succeed)?"
    r"|(?:the\s+)?ideal\s+candidate"
    r"|your\s+(?:profile|background|skills|skill\s+set|experience|expertise|toolkit)"
    r"|you\s+(?:might|may)\s+be\s+a\s+(?:great\s+|good\s+)?fit(?:\s+if)?"
    r"|you(?:'ll|\s+will)\s+thrive(?:\s+here)?(?:\s+if)?"
    r"|is\s+this\s+you"
    r"|what\s+(?:makes|will\s+make)\s+you\s+successful|to\s+be\s+successful"
    r"|(?:the\s+)?skills\s+(?:and|&)\s+experience"
    r"|what\s+it\s+takes"
    r"|what\s+(?:would|will)\s+make\s+you\s+stand\s+out|even\s+better\s+if|it\s+would\s+be\s+great\s+if"
    r")\b", _I)
# A candidate-profile heading that itself signals something extra / optional -> PREFERRED.
CP_OPTIONAL = re.compile(r"\bstand\s+out\b|\beven\s+better\b|\bwould\s+be\s+great\b", _I)
# `^about\b` is the only SKIP root a candidate-profile heading may override ("About you", "About yourself").
_ABOUT_CANDIDATE = re.compile(r"^about\s+(?:you|yourself|the\s+candidate)\b", _I)

# Family-less attribute sub-headings ("Technical skills:", "Tools", "### Languages") that may inherit an open
# REQUIRED / PREFERRED section (P2). Employer-voiced sub-headings ("Our stack") never inherit.
INHERITABLE_SUBHEADING = re.compile(
    r"^(?:(?:technical|core|key|hard|soft)\s+)?(?:skills?|tools?|tooling|languages?|technologies|tech|"
    r"frameworks?|platforms?|databases?|experience|knowledge|education|certifications?)"
    r"(?:\s+(?:and|&)\s+(?:skills?|tools?|tooling|languages?|technologies|frameworks?|platforms?|experience|"
    r"knowledge|education|certifications?))?$", _I)


def _stripped(content: str) -> str:
    return _norm(seg._strip_heading_decoration(content)).rstrip(":").strip()


def candidate_profile_kind(content: str, prod_kind) -> K | None:
    """REQUIRED / PREFERRED when `content` is a candidate-profile heading production leaves UNKNOWN (no family)
    or SKIP only via `^about`; None otherwise."""
    text = _stripped(content)
    if not CP_HEADING.search(text):
        return None
    families = seg._matched_heading_families(text)
    if prod_kind is K.SKIP:
        if families != [K.SKIP] or not _ABOUT_CANDIDATE.search(text):
            return None
    elif prod_kind is K.UNKNOWN:
        if families:
            return None
    else:
        return None
    return K.PREFERRED if CP_OPTIONAL.search(text) else K.REQUIRED


@dataclass(frozen=True)
class Policy:
    name: str
    description: str
    cp_headings: bool = False
    normalize_curly_all: bool = False
    bare_cp_lines: bool = False
    wrapped_headings: bool = False
    inherit_subheadings: bool = False
    paragraph_reset: bool = False
    intent_gate: Callable | None = field(default=None, compare=False)

    # ---- hooks used by m11g23_harness ----------------------------------------------------------------------
    def classify(self, line: str, content: str):
        prod = seg._classify_heading_line(line, content)
        if not self.cp_headings:
            return prod, False
        if prod is None:
            if self.bare_cp_lines and _is_bare_cp_line(line, content):
                cp = candidate_profile_kind(content, K.UNKNOWN)
                if cp is not None:
                    return cp, True
            return None, False
        if prod in (K.UNKNOWN, K.SKIP):
            cp = candidate_profile_kind(content, prod)
            if cp is not None:
                return cp, True
            if self.normalize_curly_all and prod is K.UNKNOWN and _norm(content) != content:
                alt = seg._classify_heading_line(_norm(line), _norm(content))
                if alt is not None:
                    return alt, False
        return prod, False

    def classify_wrapped(self, line: str, content: str, next_line: str, combined: str):
        """A candidate-profile heading broken over two physical lines ("Who we're looking" / "for:")."""
        if seg._BULLET_PREFIX.match(line) or seg._BULLET_PREFIX.match(next_line):
            return None, False
        if re.search(r"[.!?,;:]\s*$", content) or len(combined.split()) > 14:
            return None, False
        if seg._classify_heading_line(next_line, next_line.strip()) is None and not combined.rstrip().endswith(":"):
            return None, False
        cp = candidate_profile_kind(combined, K.UNKNOWN)
        return (cp, True) if cp is not None else (None, False)

    def is_inheritable_subheading(self, content: str) -> bool:
        return bool(INHERITABLE_SUBHEADING.match(_stripped(content)))


def _is_bare_cp_line(line: str, content: str) -> bool:
    """A bare (no colon / Markdown / caps), sentence-case line that is ENTIRELY a candidate-profile heading frame
    ("About you", "What you'll bring") -- never a bullet, never ending in sentence punctuation, <= 7 words."""
    if seg._BULLET_PREFIX.match(line):
        return False
    text = _norm(content).strip()
    if not text or re.search(r"[.!?,;]\s*$", text) or len(text.split()) > 7:
        return False
    m = CP_HEADING.match(text)
    return m is not None and text[m.end():].strip() in ("", ":")


def _intent_gate(sentence: str, hint, kind_name):
    """P3: a candidate-profile section's default applies only to a sentence G21 reads as a qualification."""
    if hz.intent_role(sentence) == "qual":
        return hint, kind_name, True
    return None, "UNKNOWN", False


P0 = Policy("P0_v15", "production parser v15 (replica, no hooks)")
P1 = Policy("P1_cp_headings", "closed candidate-profile heading vocabulary -> REQUIRED (PREFERRED when the heading "
            "signals optionality); rescues only no-family UNKNOWN headings and the `^about` SKIP on 'About you'",
            cp_headings=True)
P2 = Policy("P2_section_aware", "P1 + curly normalisation for every family, bare sentence-case candidate-profile "
            "lines, two-line candidate-profile headings, attribute sub-heading inheritance in REQUIRED/PREFERRED "
            "sections, list-section paragraph reset",
            cp_headings=True, normalize_curly_all=True, bare_cp_lines=True, wrapped_headings=True,
            inherit_subheadings=True, paragraph_reset=True)
P3 = Policy("P3_cp_headings_intent", "P1 headings; under a candidate-profile heading the section default applies "
            "only to a sentence G21 classifies as a qualification, else UNKNOWN-section handling",
            cp_headings=True, intent_gate=_intent_gate)

P4 = Policy("P4_narrow_hybrid", "P2 restricted to the components with a measured DEV / historical benefit: P1 "
            "headings + bare sentence-case candidate-profile lines + two-line candidate-profile headings + attribute "
            "sub-heading inheritance. Drops P2's all-family curly normalisation and paragraph reset (no measured "
            "effect) and P3's intent gate (recall loss with no precision gain on DEV, G20 or private aggregates)",
            cp_headings=True, bare_cp_lines=True, wrapped_headings=True, inherit_subheadings=True)

POLICIES = (P0, P1, P2, P3, P4)
ALL_POLICIES = POLICIES
SELECTED = P4
