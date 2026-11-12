"""Milestone 11-G22-R3 -- revised README context guard (OFFLINE research adapter; the readme:v5 candidate).

Nothing here is imported by `src/gitscore`. Uses G22-R2's `applied()` mechanism (wraps the production per-occurrence
filter `readme.is_non_implementation_mention`), so the alias table, overlap resolution, fall-through to the next
occurrence / alias, one item per concept per repository and MODERATE confidence are all unmodified production code.

  R3   G22-R2 policy D's precision components, UNCHANGED (per-alias technical collocates, code / heading / version /
       claim-of-use frame / registry list sibling, explicit non-use frames), with two scope / recall changes:

       1. Scope: the guard applies ONLY to the 11 reviewed README-ambiguous aliases. D applied its non-use frames to
          every alias; Phase 5 requires non-ambiguous alias behaviour to stay exactly readme:v4.
       2. Recall: three STRUCTURAL technical cues for an ambiguous alias (no blanket "with" / "in" / "on" / "of" /
          "and" / "using" lead-ins):
          a. the alias's own collocate, or its plural, as the head noun IMMEDIATELY after the alias ("Flask apps");
             the sentence-window collocate check itself is D's, unchanged (a plural-tolerant window admitted "free of
             rust ... tools" on G22-R2 / G22-R controls during design and was withdrawn);
          b. a software-artifact head noun immediately after the alias, optionally after a version ("a Rust library",
             "Swift client", "a Java 17 library"), or "<library|framework|plugin|...> for <alias>" ("web framework for
             Python", "extension for Flask");
          c. a major-version token immediately after the alias ("Java 17+", "React 18"); dotted versions and version
             comparators were already cues.

Design timeline: D ran unchanged on the fresh VAL-1 set (separately authored) and lost 10/36 genuine README use
items. R3 was then designed on the SEEN sets only -- G22-R2 DEV/EVAL, G22-R DEV/EVAL and VAL-1 after its D run (VAL-1
is therefore a design set for R3, not validation). R3 is frozen, with pre-declared acceptance criteria, in
`evaluation/m11g22r3/policy_design_freeze.json` BEFORE the reserve VAL-2 set is run by anything.
"""
from __future__ import annotations

import re

import m11g22r2_policies as p2

AMBIGUOUS = p2.AMBIGUOUS  # the 11 reviewed README-ambiguous aliases (G22-R / G22-R2), unchanged
_I = re.IGNORECASE

_SOFTWARE_HEAD = (r"(?:librar(?:y|ies)|packages?|modules?|sdks?|clients?|servers?|implementations?|frameworks?|"
                  r"plugins?|extensions?|codebases?|runtimes?|compilers?|interpreters?|cli|binar(?:y|ies)|crates?|"
                  r"toolkits?)")
_HEAD_AFTER = re.compile(r"^[ \t]+(?:v?\d+(?:\.\d+)*\+?[ \t]+)?" + _SOFTWARE_HEAD + r"\b", _I)
_HEAD_FOR_BEFORE = re.compile(r"\b(?:librar(?:y|ies)|frameworks?|plugins?|extensions?|middleware|sdks?|packages?|"
                              r"modules?|toolkits?)\s+for\s+$", _I)
_MAJOR_VERSION_AFTER = re.compile(r"^[ \t]+v?\d{1,2}\+?(?=$|[\s,;:)!?]|\.(?:\s|$))")
_NEXT_WORD = re.compile(r"^[ \t]+(?:v?\d+(?:\.\d+)*\+?[ \t]+)?([A-Za-z][A-Za-z.-]*)")


def _collocate_head_after(sentence: str, s: int, e: int) -> bool:
    m = _NEXT_WORD.match(sentence[e:])
    if not m:
        return False
    word = m.group(1).lower().rstrip(".")
    colloc = p2.COLLOCATES.get(sentence[s:e].lower(), set())
    return word in colloc or (word.endswith("s") and word[:-1] in colloc)


def technical_cue(text: str, start: int, end: int) -> bool:
    if p2.strong_structural_cue(text, start, end):
        return True
    sentence, s, e = p2._occurrence(text, start, end)
    if p2._token_window(sentence, s, e) & p2.COLLOCATES.get(sentence[s:e].lower(), set()):
        return True  # D's collocate rule, unchanged
    if _collocate_head_after(sentence, s, e):
        return True
    after, before = sentence[e:], sentence[:s]
    if _HEAD_AFTER.match(after) or _HEAD_FOR_BEFORE.search(before) or _MAJOR_VERSION_AFTER.match(after):
        return True
    return p2._registry_list_sibling(sentence, s, e)


def rule_r3(text: str, start: int, end: int) -> bool:
    """True = reject this occurrence (in addition to readme:v4's 8D.3 filter)."""
    if not p2._ambiguous(text, start, end):
        return False  # non-ambiguous aliases: readme:v4 behaviour exactly
    return p2.nonuse_frame(text, start, end) or not technical_cue(text, start, end)


R3 = p2.Policy("R3_context_guard", rule=rule_r3,
               description="D's precision components scoped to the 11 ambiguous aliases + structural recall cues "
                           "(collocate head noun incl. plural, software head noun / '<library> for', major version)")
