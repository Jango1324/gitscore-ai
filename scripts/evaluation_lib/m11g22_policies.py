"""Milestone 11-G22 -- candidate concept-recognition policies (OFFLINE research adapters).

Nothing here is imported by `src/gitscore`. A policy is applied with `applied(policy)`, a
context manager that temporarily rebinds a few names inside the REAL production parser
modules, in-process, and restores them on exit. Everything else -- segmentation, G21
qualification admission, necessity, G17 alternative containment, dedup, the matcher and
scoring v2 -- is the unmodified production code.

Intervention points (the same ones a production change would use):

  * concept text   -- `parser.decide_qualification_intent` is wrapped so the decision's
                      `scoped_text` (G21's length-preserving detector text) additionally
                      blanks the spans a policy rejects. Admission (`admit/role/frame`) is
                      never changed, so G21 behaviour is untouched by construction.
  * unknown terms  -- `parser.find_conservative_unknown_terms` is wrapped with a fragment gate.
  * alias mentions -- `parser.find_concept_mentions` / `alternatives.find_concept_mentions`
                      are wrapped only to ADD the case-sensitive, cue-gated "Go" mention (G).
  * equivalence    -- `parser.classify_alternative_claim` is wrapped: an "unsafe" OR claim
                      whose every segment resolves to one and the same registry concept is
                      routed to the ordinary single-concept path (Q).

Design set: the G22 DEV controls plus the G20 research record (its stage-2 guards are
re-used verbatim where noted). The EVAL controls were authored by the same researcher
before this file was written, so EVAL is only weakly held out; this file is frozen
(`evaluation/m11g22/policy_design_freeze.json`) before EVAL is run.

  BASE  live parser v14, nothing patched
  A     G20 generic-usage guard: a LOWERCASE surface of a capitalised registry name in a
        verb/adjective frame ("to react", "a swift", "react quickly") -- no alias metadata
  B     reviewed alias-ambiguity metadata (7 bare aliases whose lowercase form is an ordinary
        English word in workplace prose) + a POSITIVE technical cue required for those only
  G     cue-gated recognition of capitalised "Go" (registry marks "go" prose-unsafe)
  C     unresolved-fragment validation: lowercase abstract-noun fragments, fragments the
        existing non-technical detector classifies, and a claim-initial discourse adverb
        ("Alternatively, ...") never become `unresolved:<term>` (G20 S2U gate)
  Q     alias equivalence: "Go or Golang" -> one language.go row instead of a placeholder
  D     C + Q + A   (smallest combined design; no new metadata)
  E     clause-scoped recognition (G21 units): concepts only from qualification units --
        studied for M10E-g3, NOT a G22 candidate (clause-level design is out of scope)
"""
from __future__ import annotations

import contextlib
import dataclasses
import re
from dataclasses import dataclass, field

from gitscore.concepts.registry import default_registry
from gitscore.jobs.parsing import alternatives as alt_mod
from gitscore.jobs.parsing import parser as parser_mod
from gitscore.jobs.parsing import qualification_intent as qi
from gitscore.jobs.parsing.alternatives import AlternativeClaim, _resolve_segment, _split_alternative_segments
from gitscore.jobs.parsing.concepts import ConceptMention, find_concept_mentions
from gitscore.jobs.parsing.non_technical import find_non_technical_match

_I = re.IGNORECASE
_REG = default_registry()

# ---- A: G20 stage-2 generic-usage guard (verbatim from m11g20_policies._generic_usage) ----------
_LEAD_IN_BEFORE = re.compile(r"\b(?:with|in|of|using|on|via|and|or)\s*$", _I)


def generic_usage(text: str, start: int, end: int, display: str) -> bool:
    surface = text[start:end]
    if surface != surface.lower() or display == display.lower():
        return False
    before = text[:start]
    if _LEAD_IN_BEFORE.search(before) or re.search(r",\s*$", before):
        return False
    return bool(re.search(r"\b(?:to|an?)\s*$", before, _I) or re.match(r"\s+[a-z]+ly\b", text[end:]))


def spans_a(text: str) -> list[tuple[int, int]]:
    out = []
    for m in find_concept_mentions(text):
        concept = _REG.get(m.concept_id)
        if concept is not None and generic_usage(text, m.start, m.end, concept.display_name):
            out.append((m.start, m.end))
    return out


# ---- B: reviewed ambiguity metadata + positive technical cue ------------------------------------
# Review criterion (applied once to every bare-word registry alias): the alias's lowercase form is
# an ordinary English verb / adjective / noun with a non-technical sense that plausibly occurs in
# workplace prose. Python / Java / Flask / pandas were judged rare in job prose (animal / coffee /
# lab glass) and are NOT flagged. "go" / "next" / "js" / "ts" / "c" are already prose-unsafe.
AMBIGUOUS_ALIASES = frozenset({"react", "express", "swift", "rust", "ruby", "shell", "torch"})
# Head nouns: the existing production skill-context vocabulary (`concepts._BARE_ALIAS_CONTEXT_CUES`)
# plus code-artifact nouns needed by the DEV set ("shell scripts").
_HEAD_NOUN_AFTER = re.compile(
    r"^[\s-]*(?:experience|programming|proficien\w*|language|development|developers?|embedded|skills?|"
    r"scripts?|scripting|code|framework|library)\b", _I)
_SEPARATOR_ONLY = re.compile(r"^[\s,/&]*(?:and/or|and|or)?[\s,/&]*$", _I)


def _claim_initial(text: str, start: int) -> bool:
    return not re.search(r"\w", text[:start])


def _has_cue(text: str, m: ConceptMention, others: list[ConceptMention]) -> bool:
    surface = text[m.start:m.end]
    if surface != surface.lower() and not _claim_initial(text, m.start):
        return True  # technical casing mid-sentence ("in Swift", "with React")
    if not re.search(r"\w", text[:m.start] + text[m.end:].strip(" .;:!")):
        return True  # the alias IS the whole claim
    if _LEAD_IN_BEFORE.search(text[:m.start]) and surface == surface.lower():
        return True  # lowercase after a technical lead-in ("experience with react")
    if _HEAD_NOUN_AFTER.match(text[m.end:]):
        return True  # "Swift experience", "shell scripts"
    for o in others:
        between = text[m.end:o.start] if o.start >= m.end else text[o.end:m.start]
        if _SEPARATOR_ONLY.match(between):
            return True  # list sibling of another registry mention
    return False


def spans_b(text: str) -> list[tuple[int, int]]:
    ms = list(find_concept_mentions(text))
    out = []
    for m in ms:
        if m.matched_alias.lower() in AMBIGUOUS_ALIASES and not _has_cue(text, m, [o for o in ms if o is not m]):
            out.append((m.start, m.end))
    return out


# ---- G: cue-gated capitalised "Go" ---------------------------------------------------------------
_GO = re.compile(r"(?<![A-Za-z0-9])Go(?![A-Za-z0-9])")


def go_mentions(text: str) -> list[ConceptMention]:
    """Cue-confirmed "Go" mentions, cues evaluated on `text` itself (call with the CLAIM)."""
    base = list(find_concept_mentions(text))
    out = []
    for g in _GO.finditer(text):
        if any(b.start < g.end() and g.start() < b.end for b in base):
            continue
        m = ConceptMention("language.go", "go", g.start(), g.end())
        lead = _LEAD_IN_BEFORE.search(text[:g.start()]) is not None
        if lead or _HEAD_NOUN_AFTER.match(text[g.end():]) or any(
                _SEPARATOR_ONLY.match(text[g.end():o.start] if o.start >= g.end() else text[o.end:g.start()])
                for o in base):
            if not text[g.end():].startswith("-"):  # "Go-getter"
                out.append(m)
    return out


# ---- C: unresolved-fragment validation (G20 S2U gate, applied to the surface form) ---------------
_ABSTRACT_SUFFIX = re.compile(r"^[a-z]+(?:ity|ness|ship|tion|sion|ment|ance|ence|ism)$")
_DISCOURSE_ADVERB_START = re.compile(r"^\W*([A-Za-z]+ly)\s*,")


def fragment_rejected(term: str) -> bool:
    if " " in term:
        return False  # multi-word fragments already pass M11-A1's shape gate
    return bool(_ABSTRACT_SUFFIX.match(term)) or find_non_technical_match(term) is not None


def spans_c(text: str) -> list[tuple[int, int]]:
    m = _DISCOURSE_ADVERB_START.match(text)
    return [m.span(1)] if m else []


# ---- E: clause-scoped recognition (study only) ----------------------------------------------------
def spans_e(text: str) -> list[tuple[int, int]]:
    units = qi._analyse(text)
    if not any(role == "qual" for _, _, role, _ in units):
        return []
    return [(s, e) for s, e, role, _ in units if role == "nonqual"]


# ---- Q: alias equivalence --------------------------------------------------------------------------
def equivalent_single_concept(text: str) -> str | None:
    if not alt_mod.contains_alternative_marker(text):
        return None
    ids = set()
    for seg in _split_alternative_segments(text):
        resolved = _resolve_segment(seg, _REG)
        if resolved is None:
            return None
        ids.update(resolved)
    if len(ids) == 1 and not next(iter(ids)).startswith("unresolved:"):
        return next(iter(ids))
    return None


# ---- policy plumbing -------------------------------------------------------------------------------
@dataclass(frozen=True)
class Policy:
    name: str
    span_rules: tuple = ()
    fragment_gate: bool = False
    go: bool = False
    equivalence: bool = False
    description: str = ""
    components: tuple[str, ...] = field(default_factory=tuple)


def _blank(text: str, spans) -> str:
    chars = list(text)
    for a, b in spans:
        chars[a:b] = " " * (b - a)
    return "".join(chars)


_CURRENT_CLAIM: list[str] = []  # the claim being parsed (set by the decision wrapper)


def go_mentions_in(text: str) -> list[ConceptMention]:
    """POST-FREEZE SIMULATION FIX (see policy_design_freeze.json `post_hoc_changes`): G's cues are
    defined on the CLAIM. `alternatives` calls the mention scan on OR *segments* ("Go and either
    Docker"), which loses claim-level context ("Python or Go"); so cue-confirmed Go positions are
    computed on the current claim and mapped onto `text` when `text` is a slice of that claim."""
    if _CURRENT_CLAIM and text != _CURRENT_CLAIM[0] and text in _CURRENT_CLAIM[0]:
        offset = _CURRENT_CLAIM[0].index(text)
        return [ConceptMention(m.concept_id, m.matched_alias, m.start - offset, m.end - offset)
                for m in go_mentions(_CURRENT_CLAIM[0]) if offset <= m.start and m.end <= offset + len(text)]
    return go_mentions(text)


@contextlib.contextmanager
def applied(policy: Policy):
    saved = {(parser_mod, n): getattr(parser_mod, n) for n in (
        "decide_qualification_intent", "find_conservative_unknown_terms", "find_concept_mentions",
        "classify_alternative_claim")}
    saved[(alt_mod, "find_concept_mentions")] = alt_mod.find_concept_mentions
    orig_decide = saved[(parser_mod, "decide_qualification_intent")]
    orig_unknown = saved[(parser_mod, "find_conservative_unknown_terms")]
    orig_classify = saved[(parser_mod, "classify_alternative_claim")]

    def decide(text, section_kind):
        d = orig_decide(text, section_kind)
        _CURRENT_CLAIM[:] = [d.scoped_text or text]
        if not d.admit or not policy.span_rules:
            return d
        base = d.scoped_text or text
        spans = [s for rule in policy.span_rules for s in rule(base)]
        if spans:
            _CURRENT_CLAIM[:] = [_blank(base, spans)]
            return dataclasses.replace(d, scoped_text=_CURRENT_CLAIM[0])
        return d

    def unknown(text, mentions):
        terms = orig_unknown(text, mentions)
        return tuple(t for t in terms if not fragment_rejected(t)) if policy.fragment_gate else terms

    def mentions_with_go(text, registry=None):
        found = list(find_concept_mentions(text, registry=registry))
        found += go_mentions_in(text)
        return tuple(sorted(found, key=lambda m: (m.start, m.end)))

    def classify(text, registry=None):
        result = orig_classify(text, registry=registry)
        if policy.equivalence and result.kind == "unsafe" and equivalent_single_concept(text):
            return AlternativeClaim(kind="not_technical")
        return result

    try:
        parser_mod.decide_qualification_intent = decide
        parser_mod.find_conservative_unknown_terms = unknown
        parser_mod.classify_alternative_claim = classify
        if policy.go:
            parser_mod.find_concept_mentions = mentions_with_go
            alt_mod.find_concept_mentions = mentions_with_go
        yield policy
    finally:
        for (mod, name), value in saved.items():
            setattr(mod, name, value)
        _CURRENT_CLAIM.clear()


BASE = Policy("BASE", description="live parser v14 (nothing patched)")
A = Policy("A_generic_usage", span_rules=(spans_a,), components=("A",),
           description="G20 generic-usage guard: lowercase surface of a capitalised registry name in a verb/adjective "
                       "frame; no alias metadata")
B = Policy("B_ambiguous_alias_cue", span_rules=(spans_b,), components=("B",),
           description="reviewed ambiguity metadata (7 aliases) + positive technical cue required for those only")
G = Policy("G_go_cue", go=True, components=("G",),
           description="cue-gated recognition of capitalised 'Go' (lead-in / head noun / registry list sibling)")
BG = Policy("BG_context_aware", span_rules=(spans_b,), go=True, components=("B", "G"),
            description="Option B as specified: context-aware alias recognition = B + G")
C = Policy("C_unresolved_validation", span_rules=(spans_c,), fragment_gate=True, components=("C",),
           description="unresolved-fragment validation (abstract-noun / non-technical fragment gate + claim-initial "
                       "discourse adverb), registry recognition untouched")
Q = Policy("Q_equivalence", equivalence=True, components=("Q",),
           description="alias equivalence: an OR whose every segment resolves to one registry concept -> one row")
D = Policy("D_combined_small", span_rules=(spans_a, spans_c), fragment_gate=True, equivalence=True,
           components=("A", "C", "Q"), description="C + Q + A (no new metadata)")
DB = Policy("DB_combined_with_metadata", span_rules=(spans_b, spans_c), fragment_gate=True, equivalence=True,
            components=("B", "C", "Q"), description="C + Q + B (with the reviewed ambiguity metadata)")
E = Policy("E_clause_scope_STUDY", span_rules=(spans_e,), components=("E",),
           description="STUDY ONLY: concepts only from G21 qualification units (clause-level; out of G22 scope)")

POLICIES = (BASE, A, B, G, BG, C, Q, D, DB, E)
