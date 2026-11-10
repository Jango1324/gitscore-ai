"""Milestone 11-G20 -- candidate admission policies (OFFLINE research adapters).

Designed against the DEV controls and the design-visible historical corpora
(G15/G16/G18/M10D/M10E/G6/G7/8c/M10); the HELD-OUT controls were run only
after this file was frozen (`evaluation/m11g20/policy_design_freeze.json`).
Nothing here is imported by `src/gitscore`. Every policy plugs into
`m11g20_admission.parse()` hooks; row construction, alternative logic
(incl. G17 containment), necessity inference and dedup remain the REAL
production functions.

Design rule learned from the historical corpora: a claim is declined ONLY
on POSITIVE evidence of a non-qualification frame -- never merely for
lacking a qualification frame (the rejected A0 variant does that and
destroys genuine bare technology lists, e.g. M10D "Java, Python and/or Go").

All vocabularies are closed, generic grammatical frames (subject / verb /
attribute SHAPES common to any job posting), never technology-, employer-
or role-specific content words, and a STRONG candidate frame (or a local
necessity marker attached to a candidate-attribute phrase in the same
clause) always overrides a non-qualification frame.

  A0 REJECTED: require a positive qualification frame (unsectioned path)
  A  minimal veto: today's narrative-cue scope, closed non-qualification frames
  B  section-aware: frames in every section, local marker must sit in a
     qualification clause, duty-lead bullets in qualification sections,
     candidate-profile headings, list-section paragraph reset, necessity
  C  two-stage: stage 1 = B; stage 2 = concept recognition scoped to the
     qualifying clause(s) + generic-word / fragment guards
  S2 / H / N  single-component ablations
"""
from __future__ import annotations

import re

from m11g20_admission import Policy  # noqa: I001 -- also puts src/ on sys.path

from gitscore.concepts.registry import default_registry
from gitscore.jobs.parsing import segmentation as seg
from gitscore.jobs.parsing.competency_extraction import _RESPONSIBILITY_LEAD
from gitscore.jobs.parsing.concepts import find_concept_mentions
from gitscore.jobs.parsing.narrative import contains_narrative_cue
from gitscore.jobs.parsing.necessity import _PREFERRED_MARKER, _REQUIRED_MARKER, _has_local_marker
from gitscore.jobs.types import Necessity

_I = re.IGNORECASE

# ---- positive (candidate-qualification) frames ------------------------------------------------
# STRONG: the clause is explicitly about what the candidate has / must have.
STRONG_CANDIDATE = re.compile(
    r"\b(?:you|candidates?|applicants?)\s+(?:have|has|had|are|must|should|need|bring|possess|know|can)\b|"
    r"\byou(?:'ve|'re)\b|\b(?:ideal|successful)\s+candidate\b|"
    r"\b(?:looking\s+for|seeking)\s+(?:someone|a\s+candidate|candidates|an?\s+\w+\s+(?:engineer|developer))\b|"
    r"\bmust[- ]have\b|"
    r"\bwe\s+(?:require|expect|need|want|prefer)\s+(?:someone|you|candidates?|applicants?|engineers?|developers?|"
    r"\d+\+?\s*years?|(?:(?:strong|solid|deep|proven|hands-on)\s+)?(?:experience|knowledge|proficiency|familiarity|"
    r"expertise))\b|"
    r"\bwe(?:'re|\s+are)\s+(?:looking\s+for|seeking)\b|"
    r"\bwe(?:'d|\s+would)\s+(?:love|like)\s+(?:you|someone|candidates?)\s+to\s+have\b",
    _I,
)
# A necessity predicate that is not in production's marker vocabulary ("X is a must").
PREDICATE_MARKER = re.compile(
    r"\b(?:is|are)\s+(?:a\s+must|a\s+plus|an?\s+(?:advantage|asset|bonus)|helpful|beneficial|desirable|"
    r"preferred|required|essential|mandatory|necessary)\b", _I)
# WEAK: a candidate-attribute noun phrase (also appears in narrative, so on its own it never
# overrides an employer-subject / duty / learning / benefit frame).
WEAK_CANDIDATE = re.compile(
    r"\b(?:experience[ds]?|proficien\w*|knowledge|familiar\w*|expertise|expert|background|understanding|"
    r"exposure|fluen\w*|competen\w*|skills?|skilled|degree|bachelor'?s?|master'?s?|ph\.?d\.?|certifi\w*|"
    r"track\s+record)\b|\b(?:ability|able)\s+to\b|\bcomfortable\s+(?:with|in|using)\b|\b\d+\+?\s*years?\b",
    _I,
)

# ---- negative (non-qualification) frames ------------------------------------------------------
FUTURE_DUTY = re.compile(
    r"\byou(?:'ll|\s+will)\s+(?!need\b|have\b|bring\b|possess\b|be\s+expected\s+to\s+have\b|"
    r"be\s+(?:comfortable|proficient|fluent|familiar|experienced|skilled|an?\s+expert|able)\b)\w+", _I)
EMPLOYER_SUBJECT = re.compile(
    r"^(?:about\s+us\s*:\s*)?(?:at\s+[A-Z][\w&.-]*(?:\s+[A-Z][\w&.-]*)*,?\s+)?"
    r"(?:(?:many|most|all|some)\s+of\s+)?(?:we\b|we're\b|we've\b|our\b|us\b)|"
    r"^(?:the|this)\s+(?:team|company|platform|product|codebase|stack|organi[sz]ation|role\s+offers)\b"
    r"(?!\s+(?:requires?|needs?|expects?|seeks?|is\s+(?:looking|seeking)))", _I)
TECH_DISCUSSION_VERB = re.compile(
    r"^\W*(?:\S+\s+){0,2}?(?:is|are|was|were|has|have|had|remains?|powers?|runs?|drives?|handles?)\b", _I)
BENEFIT = re.compile(
    r"\b(?:is|are)\s+provided\b|\bstipend\b|\bbudget\s+for\b|\breimburse\w*\b|\ballowance\s+for\b|"
    r"\bwe\s+(?:provide|offer|cover)\b|\breceives?\s+an?\s+(?:\w+\s+){0,2}(?:stipend|budget|allowance)\b", _I)
PROCESS = re.compile(
    r"\binterview\w*\b|\bhiring\s+process\b|\bshortlisted\b|\btake-home\b|"
    r"\b(?:coding|pairing)\s+(?:session|challenge|exercise|test)\b|\b(?:short|online)\s+\w*\s*assessment\b", _I)
LEARNING = re.compile(
    r"\bchance\s+to\s+learn\b|\bopportunit\w*\s+to\s+(?:learn|grow)\b|\bget\s+to\s+learn\b|"
    r"\bbe\s+mentored\b|\bwill\s+mentor\s+you\b|\bnew\s+hires\b", _I)
NEGATION = re.compile(
    r"\bno\s+(?:prior\s+|previous\s+)?(?:experience|knowledge|background)\b[^.;]*\b(?:necessary|required|needed)\b|"
    r"\bnot\s+(?:required|necessary|needed|essential|mandatory)\b", _I)
APPRECIATIVE_TAIL = re.compile(
    r"\b(?:but|though|however)\b[^.;]*\b(?:appreciated|helpful|a\s+plus|welcome|nice|valued)\b|"
    r"\b(?:helpful|appreciated|a\s+plus)\b[^.;]*\bbut\s+not\b", _I)
TEAM_PRACTICE = re.compile(
    r"^(?:all|every|each)\s+(?:\w+\s+){0,2}(?:must|should|is|are)\s+(?:be\s+)?"
    r"(?:written|built|deployed|tested|reviewed|run|developed)\b", _I)
INLINE_NONQUAL_PREFIX = re.compile(
    r"^(?:about\s+(?:us|the\s+company|the\s+team)|who\s+we\s+are|our\s+(?:company|mission|story)|benefits|perks)\s*:",
    _I)
PREFERRED_EXTRA = re.compile(
    r"\bwould\s+be\s+(?:great|nice|helpful|ideal|an?\s+(?:advantage|asset|bonus))\b|"
    r"\b(?:is|are)\s+(?:helpful|beneficial|an?\s+(?:advantage|asset))\b|\bhelps\b|\bappreciated\b|\bdesirable\b", _I)
CANDIDATE_PROFILE_HEADING = re.compile(
    r"^(?:about\s+(?:you|the\s+candidate)|who\s+you\s+are|your\s+profile|what\s+you(?:'ll)?\s+bring|"
    r"what\s+we(?:'re|\s+are)?\s+(?:need|looking\s+for)(?:\s+from\s+you)?|you'?ll\s+thrive\s+(?:here\s+)?if|"
    r"(?:the\s+)?ideal\s+candidate|who\s+we(?:'re|\s+are)\s+looking\s+for|what\s+you(?:'ll)?\s+need)\b", _I)


def _starts_with_concept(text: str) -> bool:
    body = seg._BULLET_PREFIX.sub("", text).lstrip()
    mentions = find_concept_mentions(body)
    return bool(mentions) and mentions[0].start == 0


_CLAUSE_SPLIT = re.compile(r";|,\s*but\b|\s+but\s+", _I)


def clauses(text: str) -> list[str]:
    return [c.strip() for c in _CLAUSE_SPLIT.split(text.strip()) if c.strip()]


def frames(text: str) -> dict:
    t = seg._BULLET_PREFIX.sub("", text.strip())
    return {
        "strong": bool(STRONG_CANDIDATE.search(t)),
        "weak": bool(WEAK_CANDIDATE.search(t)),
        "marker": _has_local_marker(t) or (bool(PREDICATE_MARKER.search(t)) and not NEGATION.search(t)),
        "future_duty": bool(FUTURE_DUTY.search(t)),
        "employer": bool(EMPLOYER_SUBJECT.search(t)),
        "tech_subject": _starts_with_concept(t) and bool(TECH_DISCUSSION_VERB.search(t)),
        "benefit": bool(BENEFIT.search(t)),
        "process": bool(PROCESS.search(t)),
        "learning": bool(LEARNING.search(t)) or contains_narrative_cue(t),
        "negation": bool(NEGATION.search(t)) and not APPRECIATIVE_TAIL.search(t),
        "team_practice": bool(TEAM_PRACTICE.search(t)),
        "duty_lead": bool(_RESPONSIBILITY_LEAD.match(t)),
        "inline_nonqual_prefix": bool(INLINE_NONQUAL_PREFIX.search(t)),
    }


def clause_role(clause: str) -> tuple[str, str | None]:
    """'qual' | 'nonqual' | 'neutral' for ONE clause, plus the deciding frame.

    A non-qualification frame is overridden only by a STRONG candidate frame, or by a
    local necessity marker attached to a candidate-attribute phrase in the SAME clause."""
    f = frames(clause)
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


def claim_decision(text: str) -> tuple[str, str | None, list[tuple[str, str, str | None]]]:
    """Stage-1 claim decision from its clauses: ('qual' | 'nonqual' | 'neutral', reason, clause roles)."""
    whole = frames(text)
    roles = [(c, *clause_role(c)) for c in clauses(text)]
    if whole["inline_nonqual_prefix"]:
        return "nonqual", "inline_nonqual_prefix", roles
    if whole["negation"]:
        return "nonqual", "negation", roles
    if any(r == "qual" for _, r, _ in roles):
        return "qual", next(k for _, r, k in roles if r == "qual"), roles
    if any(r == "nonqual" for _, r, _ in roles):
        return "nonqual", next(k for _, r, k in roles if r == "nonqual"), roles
    return "neutral", None, roles


# ---- necessity component (B, C, N) ---------------------------------------------------------------
_NEGATED_REQUIRED = re.compile(r"\bnot\s+(?:required|essential|mandatory)\b", _I)


def necessity_fix(text: str, section_kind, prod: Necessity) -> Necessity | None:
    t = text.strip()
    negated = bool(_NEGATED_REQUIRED.search(t))
    stripped_required = bool(_REQUIRED_MARKER.search(_NEGATED_REQUIRED.sub(" ", t)))
    preferred_cue = bool(_PREFERRED_MARKER.search(t) or PREFERRED_EXTRA.search(t) or APPRECIATIVE_TAIL.search(t))
    if negated and not stripped_required:
        return Necessity.PREFERRED if preferred_cue else None
    if prod == Necessity.REQUIRED and preferred_cue and not stripped_required:
        return Necessity.PREFERRED
    return prod


# ---- heading component (B, C, H) -----------------------------------------------------------------
def heading_fix(line: str, content: str, prod_kind):
    if prod_kind in (seg._SectionKind.UNKNOWN, seg._SectionKind.SKIP):
        stripped = seg._strip_heading_decoration(content).rstrip(":").strip()
        if CANDIDATE_PROFILE_HEADING.search(stripped):
            return seg._SectionKind.REQUIRED
    return prod_kind


# ---- A0 (REJECTED variant, kept for the record) ---------------------------------------------------
def admit_a0(text, section_kind, doc_has_heading, hint):
    """Require a POSITIVE qualification frame on the unsectioned default-REQUIRED path."""
    if section_kind is None and not doc_has_heading and not _has_local_marker(text):
        f = frames(text)
        if not (f["strong"] or f["weak"]):
            return "decline", "no_qualification_intent"
    return "keep", None


# ---- Policy A: minimal ----------------------------------------------------------------------------
def admit_a(text, section_kind, doc_has_heading, hint):
    """Exactly the scope of today's narrative-cue veto (necessity.py step 3): no local marker,
    and a section-eligible origin (REQUIRED/PREFERRED section, or a heading-less document)."""
    eligible = section_kind in ("REQUIRED", "PREFERRED") or (section_kind is None and not doc_has_heading)
    if eligible and not _has_local_marker(text):
        decision, reason, _ = claim_decision(text)
        if decision == "nonqual":
            return "decline", reason
    return "keep", None


# ---- Policy B: section-aware ----------------------------------------------------------------------
def admit_b(text, section_kind, doc_has_heading, hint):
    decision, reason, _ = claim_decision(text)
    if decision == "nonqual":
        return "decline", reason
    if decision == "neutral" and section_kind in ("REQUIRED", "PREFERRED") and frames(text)["duty_lead"]:
        return "decline", "duty_lead_in_qualification_section"
    return "keep", None


# ---- Policy C stage 2: concept recognition --------------------------------------------------------
_ABSTRACT_SUFFIX = re.compile(r"^[a-z]+(?:ity|ness|ship|tion|sion|ment|ance|ence|ism)$")
_DISCOURSE_ADVERB_START = re.compile(r"^\W*([A-Za-z]+ly)\s*,")
_LEAD_IN_BEFORE = re.compile(r"\b(?:with|in|of|using|on|via|and|or)\s*$", _I)


def _generic_usage(text: str, start: int, end: int, display: str) -> bool:
    """A lowercase surface of a capitalised technology name used as an ordinary English
    verb / adjective: 'to react', 'to express', 'a swift learner', '<alias> quickly'."""
    surface = text[start:end]
    if surface != surface.lower() or display == display.lower():
        return False
    before = text[:start]
    if _LEAD_IN_BEFORE.search(before) or re.search(r",\s*$", before):
        return False
    return bool(re.search(r"\b(?:to|an?)\s*$", before, _I) or re.match(r"\s+[a-z]+ly\b", text[end:]))


def rows_stage2(text: str, rows: list) -> list:
    registry = default_registry()
    _, _, roles = claim_decision(text)
    qual_clauses = [c for c, r, _ in roles if r == "qual"]
    scope_to_qual = bool(qual_clauses) and any(r == "nonqual" for _, r, _ in roles)
    by_concept: dict[str, list] = {}
    for m in find_concept_mentions(text):
        by_concept.setdefault(m.concept_id, []).append(m)
    kept = []
    for r in rows:
        cid = r.concept_id
        if r.alternative_concept_ids or cid is None:
            kept.append(r)  # G17 alternative groups / placeholders and non-technical rows untouched
            continue
        if cid.startswith("unresolved:"):
            term = cid.split(":", 1)[1]
            adverb = _DISCOURSE_ADVERB_START.match(text.strip())
            if _ABSTRACT_SUFFIX.match(term) or (adverb and adverb.group(1).lower() == term):
                continue
            if scope_to_qual and not any(term.replace("_", " ") in c.lower() for c in qual_clauses):
                continue
            kept.append(r)
            continue
        concept = registry.get(cid)
        ms = by_concept.get(cid, [])
        if ms and concept is not None and all(_generic_usage(text, m.start, m.end, concept.display_name) for m in ms):
            continue
        if scope_to_qual and not any(m.concept_id == cid for c in qual_clauses for m in find_concept_mentions(c)):
            continue
        kept.append(r)
    return kept


POLICY_A0 = Policy("A0_require_intent_REJECTED", admit=admit_a0,
                   description="REJECTED: unsectioned path requires a positive qualification frame")
POLICY_A = Policy("A_minimal_veto", admit=admit_a,
                  description="today's narrative-cue veto scope (no local marker; REQUIRED/PREFERRED section or "
                              "heading-less document), widened from 2 narrative shapes to the closed "
                              "non-qualification frame set")
POLICY_B = Policy("B_section_aware", heading=heading_fix, paragraph_reset=True, admit=admit_b, necessity=necessity_fix,
                  description="frames in every section incl. RESPONSIBILITY/UNKNOWN; a local marker wins only inside "
                              "a candidate-attribute clause; duty-lead bullets in qualification sections; "
                              "candidate-profile headings; list-section paragraph reset; negated/soft necessity")
POLICY_C = Policy("C_two_stage", heading=heading_fix, paragraph_reset=True, admit=admit_b, necessity=necessity_fix,
                  rows=rows_stage2,
                  description="stage 1 = B's clause-level qualification-intent decision; stage 2 = concept "
                              "recognition scoped to qualifying clauses + generic-word / fragment guards")
POLICY_S2 = Policy("S2_stage2_only", rows=rows_stage2, description="ablation: C's stage 2 alone on v13")
POLICY_H = Policy("H_headings_only", heading=heading_fix, paragraph_reset=True,
                  description="ablation: heading + paragraph-reset components alone")
POLICY_N = Policy("N_necessity_only", necessity=necessity_fix, description="ablation: necessity component alone")

POLICY_B1 = Policy("B1_admission_only", admit=admit_b,
                   description="B's clause-level admission decision alone (no heading, reset or necessity change)")
POLICY_B1N = Policy("B1N_admission_and_necessity", admit=admit_b, necessity=necessity_fix,
                    description="B1 + negated/soft necessity")
POLICY_B1NS = Policy("B1NS_admission_necessity_stage2", admit=admit_b, necessity=necessity_fix, rows=rows_stage2,
                     description="B1N + C's stage 2 (C without the heading / paragraph-reset components)")

POLICIES = (POLICY_A0, POLICY_A, POLICY_B, POLICY_C, POLICY_S2, POLICY_H, POLICY_N, POLICY_B1, POLICY_B1N,
            POLICY_B1NS)
