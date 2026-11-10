"""Milestone 11-G20 -- POST-HOC corrected policy variants.

`m11g20_policies.py` is frozen (`evaluation/m11g20/policy_design_freeze.json`).
After the freeze, the first run over the label-backed private postings
exposed two frame DEFECTS (diagnosed by frame name only; no text is
recorded anywhere):

1. `EMPLOYER_SUBJECT` is case-insensitive, so a sentence opening with the country
   abbreviation "US" (synthetic analogue: "US work authorization is required.")
   matched the pronoun "us" -> a genuine legal
   qualification was declined.
2. A concessive negation (synthetic analogue: "Although not required, Rust
   experience is a plus.") was read as an outright negation -> a genuine PREFERRED
   qualification was declined.

The corrected variants below differ from the frozen ones ONLY in those two
frames. Their results are POST-HOC: the private sets that revealed the
defects can no longer be called unseen for them, and the report labels them
so. Nothing here is imported by `src/gitscore`.
"""
from __future__ import annotations

import re

import m11g20_policies as fp
from m11g20_admission import Policy

_I = re.IGNORECASE

# 1. pronoun part is case-SENSITIVE (We/we/Our/our/us), the rest stays case-insensitive.
EMPLOYER_SUBJECT_FIXED = re.compile(
    r"^(?i:about\s+us\s*:\s*)?(?:(?i:at)\s+[A-Z][\w&.-]*(?:\s+[A-Z][\w&.-]*)*,?\s+)?"
    r"(?:(?i:many|most|all|some)\s+of\s+)?(?:[Ww]e\b|[Ww]e're\b|[Ww]e've\b|[Oo]ur\b|us\b)|"
    r"^(?i:(?:the|this)\s+(?:team|company|platform|product|codebase|stack|organi[sz]ation|role\s+offers)\b"
    r"(?!\s+(?:requires?|needs?|expects?|seeks?|is\s+(?:looking|seeking))))")
# 2. concessive negation is not a negation.
CONCESSIVE_NEGATION = re.compile(
    r"\b(?:while|although|though|even\s+if|whilst)\s+not\s+(?:required|essential|mandatory|necessary)\b", _I)


def frames_fixed(text: str) -> dict:
    f = fp.frames(text)
    t = fp.seg._BULLET_PREFIX.sub("", text.strip())
    f["employer"] = bool(EMPLOYER_SUBJECT_FIXED.search(t))
    if CONCESSIVE_NEGATION.search(t):
        f["negation"] = False
        f["marker"] = f["marker"] or True  # the concession is itself a (preferred) necessity statement
    return f


def clause_role_fixed(clause: str):
    f = frames_fixed(clause)
    if f["strong"] or (f["marker"] and f["weak"]):
        return "qual", "strong" if f["strong"] else "marker+attribute"
    for key in ("employer", "future_duty", "learning", "benefit", "team_practice"):
        if f[key]:
            return "nonqual", key
    if f["process"] and not f["weak"]:
        return "nonqual", "process"
    if f["tech_subject"] and not (f["weak"] or f["marker"]):
        return "nonqual", "tech_subject"
    if f["weak"] or f["marker"]:
        return "qual", "weak" if f["weak"] else "marker"
    return "neutral", None


def claim_decision_fixed(text: str):
    whole = frames_fixed(text)
    roles = [(c, *clause_role_fixed(c)) for c in fp.clauses(text)]
    if whole["inline_nonqual_prefix"]:
        return "nonqual", "inline_nonqual_prefix", roles
    if whole["negation"]:
        return "nonqual", "negation", roles
    if any(r == "qual" for _, r, _ in roles):
        return "qual", next(k for _, r, k in roles if r == "qual"), roles
    if any(r == "nonqual" for _, r, _ in roles):
        return "nonqual", next(k for _, r, k in roles if r == "nonqual"), roles
    return "neutral", None, roles


def admit_b_fixed(text, section_kind, doc_has_heading, hint):
    decision, reason, _ = claim_decision_fixed(text)
    if decision == "nonqual":
        return "decline", reason
    if decision == "neutral" and section_kind in ("REQUIRED", "PREFERRED") and frames_fixed(text)["duty_lead"]:
        return "decline", "duty_lead_in_qualification_section"
    return "keep", None


def necessity_fix_fixed(text, section_kind, prod):
    if CONCESSIVE_NEGATION.search(text):
        return fp.Necessity.PREFERRED
    return fp.necessity_fix(text, section_kind, prod)


POLICY_B1R = Policy("B1R_admission_only_posthoc", admit=admit_b_fixed,
                    description="POST-HOC: B1 with the two frame defects corrected")
POLICY_B1NR = Policy("B1NR_admission_necessity_posthoc", admit=admit_b_fixed, necessity=necessity_fix_fixed,
                     description="POST-HOC: B1N with the two frame defects corrected")
POLICY_CR = Policy("CR_two_stage_posthoc", heading=fp.heading_fix, paragraph_reset=True, admit=admit_b_fixed,
                   necessity=necessity_fix_fixed, rows=fp.rows_stage2,
                   description="POST-HOC: C with the two frame defects corrected")

POSTHOC_POLICIES = (POLICY_B1R, POLICY_B1NR, POLICY_CR)


def rows_stage2_unscoped(text: str, rows: list) -> list:
    """Ablation of the frozen stage 2 WITHOUT clause scoping (generic-word usage and
    abstract-noun / discourse-adverb fragment guards only)."""
    registry = fp.default_registry()
    by_concept: dict[str, list] = {}
    for m in fp.find_concept_mentions(text):
        by_concept.setdefault(m.concept_id, []).append(m)
    kept = []
    for r in rows:
        cid = r.concept_id
        if r.alternative_concept_ids or cid is None:
            kept.append(r)
            continue
        if cid.startswith("unresolved:"):
            term = cid.split(":", 1)[1]
            adverb = fp._DISCOURSE_ADVERB_START.match(text.strip())
            if fp._ABSTRACT_SUFFIX.match(term) or (adverb and adverb.group(1).lower() == term):
                continue
            kept.append(r)
            continue
        concept = registry.get(cid)
        ms = by_concept.get(cid, [])
        if ms and concept is not None and all(fp._generic_usage(text, m.start, m.end, concept.display_name) for m in ms):
            continue
        kept.append(r)
    return kept


POLICY_S2U = Policy("S2U_stage2_unscoped_ablation", rows=rows_stage2_unscoped,
                    description="ablation: frozen stage-2 guards without clause scoping, on v13")
POSTHOC_POLICIES = (POLICY_B1R, POLICY_B1NR, POLICY_CR, POLICY_S2U)
