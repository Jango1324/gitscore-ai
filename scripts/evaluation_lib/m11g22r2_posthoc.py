"""Milestone 11-G22-R2 -- POST-HOC policy variant (written AFTER the EVAL run; NOT validated).

Not part of `policy_design_freeze.json`. Written after EVAL and the G22-R/8c comparison showed that C and D lose
genuine prepositional mentions ("diffing in Rust", "trained with torch", "analysis ... with pandas").

  D2   D + G22-R policy B's constrained lowercase-or-capitalised lead-ins ("with" / "in" / "using" / "on" / "via"
       immediately before an ambiguous alias count as a technical cue; "of" / "and" / "or" never do)

EVAL, the G22-R controls and the 8c fixtures all informed D2, so its numbers on them are NOT validation. The
difficult-case probes include the trap D2 cannot resolve ("Photos taken in Java.").
"""
from __future__ import annotations

import re

import m11g22r2_policies as p2

_LEAD = re.compile(r"\b(?:with|in|using|on|via)\s+$", re.IGNORECASE)


def rule_d2(text: str, start: int, end: int) -> bool:
    if p2.nonuse_frame(text, start, end):
        return True
    if not p2._ambiguous(text, start, end):
        return False
    sentence, s, _ = p2._occurrence(text, start, end)
    return not (p2.cue_c(text, start, end) or _LEAD.search(sentence[:s]))


D2 = p2.Policy("D2_posthoc_d_plus_lead_ins", rule=rule_d2,
               description="POST-HOC (after EVAL): D + with/in/using/on/via lead-ins; not validated")
POSTHOC = (D2,)
