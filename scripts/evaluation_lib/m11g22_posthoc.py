"""Milestone 11-G22 -- POST-HOC policy variants (research only; NOT design-validated).

Written AFTER the EVAL run, to address the recall costs the frozen design measured:
  * B's cue set lost "React knowledge is welcome..." (G21-n10, head noun 'knowledge' missing)
    and "Ruby and Rails experience." (EVAL e09, claim-initial alias whose list sibling is an
    unregistered capitalised name).
  * C's discourse-adverb gate lost "Plotly, Dash, and Python." (EVAL e43).
Every set that informed these variants (DEV, EVAL, G21 negation scope) is therefore no longer
held out for them; their numbers are reported separately as post-hoc and must not be read as
validation.

  B2   B + head nouns 'knowledge|expertise' + a capitalised alias directly joined by
       ','/'and'/'or' to a capitalised word counts as a list-sibling cue
  C2   C, but a claim-initial '-ly,' word is only treated as a discourse adverb when the
       claim is NOT a pure list of single capitalised tokens
  DB2  C2 + Q + B2
  D2   C2 + Q + A
"""
from __future__ import annotations

import re

import m11g22_policies as pol
from gitscore.jobs.parsing.concepts import find_concept_mentions

_HEAD_NOUN_AFTER_2 = re.compile(pol._HEAD_NOUN_AFTER.pattern.replace("library)", "library|knowledge|expertise)"),
                                re.IGNORECASE)
_CAP_SIBLING = re.compile(r"^\s*(?:,|and|or|/|&)\s*[A-Z][A-Za-z0-9.+#-]*\b")
_LIST_SPLIT = re.compile(r",|\band\b|\bor\b", re.IGNORECASE)


def _has_cue_2(text: str, m, others) -> bool:
    if pol._has_cue(text, m, others):
        return True
    surface = text[m.start:m.end]
    if _HEAD_NOUN_AFTER_2.match(text[m.end:]):
        return True
    return surface != surface.lower() and bool(_CAP_SIBLING.match(text[m.end:]))


def spans_b2(text: str) -> list[tuple[int, int]]:
    ms = list(find_concept_mentions(text))
    return [(m.start, m.end) for m in ms
            if m.matched_alias.lower() in pol.AMBIGUOUS_ALIASES and not _has_cue_2(text, m, [o for o in ms if o is not m])]


def _pure_capitalised_list(text: str) -> bool:
    items = [x.strip(" .;:") for x in _LIST_SPLIT.split(text) if x.strip(" .;:")]
    return len(items) >= 2 and all(len(x.split()) == 1 and x[:1].isupper() for x in items)


def spans_c2(text: str) -> list[tuple[int, int]]:
    return [] if _pure_capitalised_list(text) else pol.spans_c(text)


B2 = pol.Policy("POSTHOC_B2", span_rules=(spans_b2,), components=("B2",),
                description="POST-HOC: B + head nouns knowledge/expertise + capitalised-sibling cue")
C2 = pol.Policy("POSTHOC_C2", span_rules=(spans_c2,), fragment_gate=True, components=("C2",),
                description="POST-HOC: C, adverb gate skipped for a pure list of single capitalised tokens")
D2 = pol.Policy("POSTHOC_D2", span_rules=(pol.spans_a, spans_c2), fragment_gate=True, equivalence=True,
                components=("A", "C2", "Q"), description="POST-HOC: C2 + Q + A")
DB2 = pol.Policy("POSTHOC_DB2", span_rules=(spans_b2, spans_c2), fragment_gate=True, equivalence=True,
                 components=("B2", "C2", "Q"), description="POST-HOC: C2 + Q + B2")

POSTHOC = (B2, C2, D2, DB2)
