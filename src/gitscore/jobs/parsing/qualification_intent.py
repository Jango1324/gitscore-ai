"""Milestone 11-G21 -- qualification-intent admission guard (B1NR).

Before G21 the live parser never decided whether a claim states a CANDIDATE
QUALIFICATION. A claim was admitted from section context plus vocabulary (any
registry concept, any HR word) and its necessity came from section context plus
marker words, so company narrative ("We use Python, Terraform and Docker"),
duties ("You will build REST APIs in Python") and technology discussion
("Kubernetes adoption has grown rapidly") became scored REQUIRED rows. See
docs/evaluation/MILESTONE_11_G20_FALSE_QUALIFICATION_ADMISSION.md (root causes
R1/R2) and docs/evaluation/MILESTONE_11_G21_QUALIFICATION_INTENT_GUARD.md.

`decide_qualification_intent()` is the production port of G20's evaluated policy
B1NR admission decision (G20's research adapter `admit_b` under scripts/evaluation_lib,
with G20's two documented post-hoc frame corrections). It is
deterministic, pure, and reads ONLY the claim text and its section kind -- never
candidate evidence, never the concept registry beyond concept recognition.

Design rule (measured in G20): a claim is declined ONLY on POSITIVE evidence of a
non-qualification frame, never merely for lacking a qualification frame -- the
rejected alternative ("require positive intent") destroyed genuine bare
technology lists such as "Java, Python and/or Go".

Frames are closed, generic, grammatical SHAPES (subject / verb / attribute), never
technology-, employer- or role-specific content words. A STRONG candidate frame
("you must have", "candidates should", "we are looking for"), or a necessity
marker attached to a candidate-attribute phrase in the SAME clause ("experience
with Python is required"), always overrides a non-qualification frame. Clauses
are split on ";" and ", but".

Negation is CLAUSE-LOCAL (G21 negation-scope correction): a subjectless "but"-
continuation ("... but not essential", "... but desirable") joins the clause it
completes; a unit that negates a requirement without optionality is blanked out
(length-preserving) of the text the parser analyses whenever another unit is a
qualification, and declines the claim otherwise. The only ellipsis recognised is a
contrast after an explicitly negated predicate ("A degree is not required; strong
Python skills are."). Known limitations: necessity is still decided per claim
("Java is required; Python is preferred" -> both REQUIRED); "No prior <tech>
experience is necessary" is outside the negation vocabulary.

Known, documented limitation (G20 held-out h003): a duty phrased with a strong
candidate subject ("You must be on call ... for our AWS infrastructure") is still
admitted -- "you must" is the same shape as "you must have".

A declined claim is returned by the parser as zero requirements, i.e. through the
EXISTING `UnparsedClaim` diagnostic (text + exact source span). No new type, no
public schema change.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from gitscore.jobs.parsing.concepts import find_concept_mentions
from gitscore.jobs.parsing.narrative import contains_narrative_cue
from gitscore.jobs.parsing.necessity import (
    APPRECIATIVE_TAIL,
    CONCESSIVE_NEGATION,
    NEGATED_PREDICATE,
    _has_local_marker,
    has_preference_cue,
)
from gitscore.jobs.parsing.segmentation import _BULLET_PREFIX

_I = re.IGNORECASE

# ---- positive (candidate-qualification) frames ---------------------------------------------------
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
# A necessity predicate outside the production marker vocabulary ("X is a must").
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

# ---- negative (non-qualification) frames ---------------------------------------------------------
FUTURE_DUTY = re.compile(
    r"\byou(?:'ll|\s+will)\s+(?!need\b|have\b|bring\b|possess\b|be\s+expected\s+to\s+have\b|"
    r"be\s+(?:comfortable|proficient|fluent|familiar|experienced|skilled|an?\s+expert|able)\b)\w+", _I)
# G20 post-hoc correction 1: the pronoun part is case-SENSITIVE, so the country abbreviation
# "US" ("US work authorization is required") is never read as the employer pronoun "us".
EMPLOYER_SUBJECT = re.compile(
    r"^(?i:about\s+us\s*:\s*)?(?:(?i:at)\s+[A-Z][\w&.-]*(?:\s+[A-Z][\w&.-]*)*,?\s+)?"
    r"(?:(?i:many|most|all|some)\s+of\s+)?(?:[Ww]e\b|[Ww]e're\b|[Ww]e've\b|[Oo]ur\b|us\b)|"
    r"^(?i:(?:the|this)\s+(?:team|company|platform|product|codebase|stack|organi[sz]ation|role\s+offers)\b"
    r"(?!\s+(?:requires?|needs?|expects?|seeks?|is\s+(?:looking|seeking))))")
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
TEAM_PRACTICE = re.compile(
    r"^(?:all|every|each)\s+(?:\w+\s+){0,2}(?:must|should|is|are)\s+(?:be\s+)?"
    r"(?:written|built|deployed|tested|reviewed|run|developed)\b", _I)
INLINE_NONQUAL_PREFIX = re.compile(
    r"^(?:about\s+(?:us|the\s+company|the\s+team)|who\s+we\s+are|our\s+(?:company|mission|story)|benefits|perks)\s*:",
    _I)
# Imperative duty verb opening a bullet. A byte-identical copy of the shadow path's
# `competency_extraction._RESPONSIBILITY_LEAD` (G20 used that object): importing it here would
# create an import cycle (competency_extraction -> qualification -> parser). A test pins the two
# patterns equal so they cannot drift.
RESPONSIBILITY_LEAD = re.compile(
    r"^[\s\-*]*\b(?:design(?:\s+and)?|implement|build|develop|debug(?:\s+and)?|optimize|collaborate|"
    r"maintain|own|lead|drive|write|create|architect)\b",
    re.IGNORECASE,
)

_CLAUSE_SPLIT = re.compile(r";|,\s*but\b|\s+but\s+", _I)

# G21 negation-scope correction -- a clause introduced by "but" that has NO subject of its own
# ("... but not essential", "... but desirable", "..., but appreciated") completes the clause
# before it, so the two form one UNIT. A ";" always starts a new unit.
_SUBJECTLESS_CONTINUATION = re.compile(
    r"^(?:not|never|also|though|although|appreciated|helpful|welcome|valued|desirable|preferred|"
    r"beneficial|optional|ideally|a\s+(?:plus|bonus)|nice\s+to\s+have)\b", _I)
# A unit with its own subject that ends in a bare copula ("strong Python skills are.").
_ELLIPTICAL_TAIL = re.compile(r"\b(?:is|are)\s*[.!]?\s*$", _I)

_NONQUAL_FRAME_ORDER = ("employer", "future_duty", "learning", "benefit", "team_practice")


@dataclass(frozen=True)
class QualificationIntentDecision:
    """Internal decision record (never part of any public schema).

    `admit` False -> the parser returns no requirement for the claim (UnparsedClaim).
    `role` is 'qual' | 'nonqual' | 'neutral'; `frame` names the deciding frame.
    `scoped_text` (G21 negation-scope correction) is the claim text with every NEGATED unit
    blanked out by spaces (same length, so offsets are unchanged) when another unit carries the
    qualification; `None` when nothing is negated. The parser analyses the scoped text but always
    keeps the ORIGINAL claim text and span as the requirement's provenance."""

    admit: bool
    role: str
    frame: str | None
    scoped_text: str | None = None


def _starts_with_concept(text: str) -> bool:
    body = _BULLET_PREFIX.sub("", text).lstrip()
    mentions = find_concept_mentions(body)
    return bool(mentions) and mentions[0].start == 0


def clauses(text: str) -> list[str]:
    return [c.strip() for c in _CLAUSE_SPLIT.split(text.strip()) if c.strip()]


def frames(text: str) -> dict[str, bool]:
    t = _BULLET_PREFIX.sub("", text.strip())
    concessive = CONCESSIVE_NEGATION.search(t) is not None
    return {
        "strong": bool(STRONG_CANDIDATE.search(t)),
        "weak": bool(WEAK_CANDIDATE.search(t)),
        # G20 post-hoc correction 2: a concession ("while not required, X is a plus") is itself
        # a (preferred) necessity statement, not a negation.
        "marker": concessive or _has_local_marker(t) or (
            bool(PREDICATE_MARKER.search(t)) and not NEGATION.search(t)),
        "future_duty": bool(FUTURE_DUTY.search(t)),
        "employer": bool(EMPLOYER_SUBJECT.search(t)),
        "tech_subject": _starts_with_concept(t) and bool(TECH_DISCUSSION_VERB.search(t)),
        "benefit": bool(BENEFIT.search(t)),
        "process": bool(PROCESS.search(t)),
        "learning": bool(LEARNING.search(t)) or contains_narrative_cue(t),
        "negation": (not concessive) and bool(NEGATION.search(t)) and not APPRECIATIVE_TAIL.search(t),
        "team_practice": bool(TEAM_PRACTICE.search(t)),
        "duty_lead": bool(RESPONSIBILITY_LEAD.match(t)),
        "inline_nonqual_prefix": bool(INLINE_NONQUAL_PREFIX.search(t)),
    }


def _role_from_frames(f: dict[str, bool]) -> tuple[str, str | None]:
    if f["strong"] or (f["marker"] and f["weak"]):
        return "qual", "strong" if f["strong"] else "marker+attribute"
    for key in _NONQUAL_FRAME_ORDER:
        if f[key]:
            return "nonqual", key
    if f["process"] and not f["weak"]:
        return "nonqual", "process"
    if f["tech_subject"] and not (f["weak"] or f["marker"]):
        return "nonqual", "tech_subject"
    if f["weak"] or f["marker"]:
        return "qual", "weak" if f["weak"] else "marker"
    return "neutral", None


def clause_role(clause: str) -> tuple[str, str | None]:
    """'qual' | 'nonqual' | 'neutral' for ONE clause, plus the deciding frame."""
    return _role_from_frames(frames(clause))


def _units(text: str) -> list[tuple[int, int, bool]]:
    """(start, end, merged) spans of the claim's units: clauses split on ";" / ", but" / " but ",
    with a subjectless "but"-continuation merged into the clause it completes."""
    spans: list[tuple[int, int, str | None]] = []
    cursor, sep = 0, None
    for m in _CLAUSE_SPLIT.finditer(text):
        spans.append((cursor, m.start(), sep))
        cursor, sep = m.end(), m.group()
    spans.append((cursor, len(text), sep))
    units: list[tuple[int, int, bool]] = []
    for s, e, before in spans:
        piece = text[s:e]
        lead, trail = len(piece) - len(piece.lstrip()), len(piece) - len(piece.rstrip())
        s, e = s + lead, e - trail
        if s >= e:
            continue
        if units and before is not None and ";" not in before and _SUBJECTLESS_CONTINUATION.match(text[s:e]):
            units[-1] = (units[-1][0], e, True)
        else:
            units.append((s, e, False))
    return units


def _analyse(text: str) -> list[tuple[int, int, str, str | None]]:
    """Per unit: (start, end, role, frame), role in 'qual' | 'nonqual' | 'neutral' | 'negated'.

    A unit is NEGATED when it contains a requirement negation that is not optionality --
    optionality being a concession, an appreciative tail, or a merged preference continuation
    ("preferred but not essential"). A negation never reaches past its own unit."""
    out: list[tuple[int, int, str, str | None]] = []
    prev_negated_predicate = False
    for s, e, merged in _units(text):
        unit = text[s:e]
        f = frames(unit)
        preference = merged and has_preference_cue(unit)
        optional = (CONCESSIVE_NEGATION.search(unit) is not None or APPRECIATIVE_TAIL.search(unit) is not None
                    or preference)
        if NEGATION.search(unit) and not optional:
            out.append((s, e, "negated", "negation"))
            prev_negated_predicate = NEGATED_PREDICATE.search(unit) is not None
            continue
        if preference:
            f["marker"] = True  # "X is preferred but not essential", "X is optional but desirable"
        if prev_negated_predicate and not merged and _ELLIPTICAL_TAIL.search(unit):
            f["marker"] = True  # contrastive ellipsis: "A is not required; B are."
        role, frame = _role_from_frames(f)
        out.append((s, e, role, frame))
        prev_negated_predicate = False
    return out


def _decide(text: str) -> tuple[str, str | None, str | None]:
    if frames(text)["inline_nonqual_prefix"]:
        return "nonqual", "inline_nonqual_prefix", None
    units = _analyse(text)
    quals = [u for u in units if u[2] == "qual"]
    if quals:
        negated = [(a, b) for a, b, role, _ in units if role == "negated"]
        scoped = None
        if negated:
            chars = list(text)
            for a, b in negated:
                chars[a:b] = " " * (b - a)
            scoped = "".join(chars)
        return "qual", quals[0][3], scoped
    for role in ("negated", "nonqual"):
        for _, _, r, frame in units:
            if r == role:
                return "nonqual", frame, None
    return "neutral", None, None


def claim_role(text: str) -> tuple[str, str | None]:
    """Claim-level role. An inline non-qualification prefix ("About us: ...") governs the whole
    claim. Negation is CLAUSE-LOCAL (G21 negation-scope correction): any qualification unit makes
    the claim a qualification (negated units are masked out of its analysis); else a negated unit
    declines it; else any non-qualification unit declines it."""
    role, frame, _ = _decide(text)
    return role, frame


def decide_qualification_intent(text: str, section_kind: str | None) -> QualificationIntentDecision:
    """Admit or decline one claim. `section_kind` is the segmentation section-kind name
    ('REQUIRED' / 'PREFERRED' / 'RESPONSIBILITY' / 'LEARNING' / 'UNKNOWN' / None)."""
    role, frame, scoped = _decide(text)
    if role == "nonqual":
        return QualificationIntentDecision(False, role, frame)
    if role == "neutral" and section_kind in ("REQUIRED", "PREFERRED") and frames(text)["duty_lead"]:
        return QualificationIntentDecision(False, role, "duty_lead_in_qualification_section")
    return QualificationIntentDecision(True, role, frame, scoped)
