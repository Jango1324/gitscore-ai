"""Milestone 11-G22-R5 -- ATTRIBUTION-ONLY README evidence guards (OFFLINE research adapters).

Nothing here is imported by `src/gitscore`. The rules are the attribution rules of G22-R4's P3/P4, reused VERBATIM
from the hash-pinned `m11g22r4_policies` module (its compiled patterns and Markdown helpers), regrouped into
cumulative candidates and separated from everything that is not attribution:

  * NOT included: P1's ordinary-English homonym lexicon, P2's negation rule, P4's homonym overrides, any positive
    technical-noun requirement, blanket preposition rules, capitalisation-based acceptance, registry changes.
  * Included only: whether a mention is attributed to THIS repository's current use.

Every candidate DEFAULT-ACCEPTS and only rejects an occurrence (on top of readme:v4's own 8D.3 filter); production's
fall-through to the next occurrence / alias, one item per concept and MODERATE confidence are unchanged.

SCOPE: all README-safe aliases. Attribution is not alias-specific ("plan to add Kubernetes", "inspired by FastAPI"),
so -- unlike R4, which was restricted to the 11 ambiguous aliases by its gate G6 -- the R5 candidates apply to every
alias. `D_ambiguous_only` is the same rule set restricted to the 11 ambiguous aliases, for comparison only.

  A    third-party projects, documentation and external references: inspiration / comparison / port-of / clone-of /
       alternative-to / instead-of frames immediately before the alias (R4 _REF_BEFORE); "like <alias>" unless a
       claim-of-use verb opens the clause (R4 _LIKE_BEFORE + P4's like-override); documentation / notes / translation
       of another project (_DOC_BEFORE; "the <alias> documentation|community|..."); "<alias> ... maintained by
       another|a different ... team" (_OWNED_ELSEWHERE)
  B    A + bounded historical frames (R4 _HIST_BEFORE: originally / began life as / moved off|from / old|former|previous
       / until vN / first prototype used / no longer / used to)
  C    B + future / hypothetical frames (R4 _FUT_STRONG / _FUT_WEAK / _FUT_AFTER; unchecked task-list item)
  D    C + Markdown quote and section attribution: attributed blockquote, '[project](https://...) (<alias>)', linked
       list item under a bindings / ports / community / third-party heading (ATX or setext). Markdown rules never fire
       inside a fenced code block (a fence neither proves nor disproves use).
  D_S  research variant: D + a setext- and fence-aware heading index REPLACING production's ATX-only index inside
       the unchanged 8D.3 heading denylist (so "Development\\n-----" ends a preceding "## Related projects" section,
       and a setext "Related projects\\n====" section is recognised). Changes production's own heading verdicts.
  O    separate multi-occurrence finding, NOT attribution: an occurrence lying inside a longer alias match of another
       concept ("react" inside "React Native") is skipped so a later genuine occurrence can be selected (production
       selects it and then drops it in overlap resolution, losing the concept).

Design sets (all SEEN): G22-R, G22-R2, G22-R3 VAL-1/VAL-2, G22-R4 DEV and fresh (seen since R4), 8c fixtures, and
the R5 DEV controls. Frozen in `evaluation/m11g22r5/policy_design_freeze.json` BEFORE the R5 fresh set is opened.
"""
from __future__ import annotations

import contextlib
import re

import m11g22r2_policies as p2
import m11g22r4_policies as p4
from gitscore.concepts.matching import alias_pattern
from gitscore.concepts.registry import default_registry
from gitscore.evidence.extraction import readme as readme_mod
from gitscore.evidence.extraction import readme_context as rc

AMBIGUOUS = p4.AMBIGUOUS
_FENCE = re.compile(r"^```", re.M)


def in_fence(text: str, pos: int) -> bool:
    starts = [m.start() for m in _FENCE.finditer(text)]
    return any(starts[i] <= pos < starts[i + 1] for i in range(0, len(starts) - 1, 2))


# ---- A: third-party projects, documentation and external references -------------------------------------
def third_party_reason(text: str, start: int, end: int) -> str | None:
    sentence, s, e = p4._occurrence(text, start, end)
    before = sentence[:s]
    if p4._REF_BEFORE.search(before):
        return "A reference / comparison / port-of frame before"
    lm = p4._LIKE_BEFORE.search(before)
    if lm and not p4._USE_VERB_IN_CLAUSE.search(p4._clause_before(sentence, lm.start())):
        return "A 'like <alias>' reference (no claim-of-use verb in the clause)"
    if p4._DOC_BEFORE.search(before):
        return "A documentation / notes / translation of another project"
    if p4._DOC_THE_BEFORE.search(before) and p4._DOC_AFTER.match(sentence[e:]):
        return "A 'the <alias> documentation / community / ...' reference"
    if p4._OWNED_ELSEWHERE.match(sentence[e:]):
        return "A maintained / written by another party"
    return None


# ---- B: historical -------------------------------------------------------------------------------------
def historical_reason(text: str, start: int, end: int) -> str | None:
    sentence, s, _ = p4._occurrence(text, start, end)
    clause = p4._clause_before(sentence, s)
    for pat in p4._HIST_BEFORE:
        if pat.search(clause):
            return "B historical frame before"
    return None


# ---- C: future / hypothetical -----------------------------------------------------------------------------
# R4's _FUT_STRONG with ONE change made on R5 DEV: a TODO marker counts only with a colon ("TODO: add X"); R4's
# "to-?do:?" also matched the product noun in "A to-do list in one HTML file" (G22-R4 DEV dev-041, a genuine use).
_FUT_STRONG5 = re.compile(
    r"\b(?:plan(?:s|ned|ning)?\s+to|hop(?:e|es|ed|ing)\s+to|intend(?:s|ed)?\s+to|would\s+like\s+to|'d\s+like\s+to|"
    r"aim(?:s|ing)?\s+to|going\s+to|eventually|someday|some\s+day|one\s+day|in\s+the\s+future|(?:todo|to-do)\s*:|"
    r"wishlist\s*:|(?:will|would|could|might)\s+be\s+(?:ported|moved|rewritten|migrated|converted|reimplemented)\s+"
    r"(?:to|in))\s+(?:[\w'.+#-]+\s+){0,3}$", re.IGNORECASE)


def future_reason(text: str, start: int, end: int) -> str | None:
    sentence, s, e = p4._occurrence(text, start, end)
    if _FUT_STRONG5.search(p4._clause_before(sentence, s)) or p4._FUT_WEAK.search(sentence[:s]):
        return "C future / planned frame before"
    if p4._FUT_AFTER.match(sentence[e:]):
        return "C future / hypothetical frame after"
    if p4._TASK_OPEN.match(p4._line(text, start)[1]) and _PLANNING_HEADING.search(
            p4.enclosing_heading(text, start) or ""):
        return "C unchecked task-list item under a planning heading"
    return None


# Unchecked task items count as future only inside a planning section. Changed on 8c (seen design data): the R4 rule
# rejected jango1324/Mentoria's setup checklist ("- [ ] `supabase/schema.sql` has been run ...", heading "Database"),
# which is an instruction, not a plan.
_PLANNING_HEADING = re.compile(r"\b(?:roadmap|todo|to[ -]do|planned|plans|future|wishlist|ideas|next\s+steps|"
                               r"progress|backlog|upcoming)\b", re.IGNORECASE)


# ---- D: Markdown quote and section attribution ------------------------------------------------------------
_REF_LINK_PAREN = re.compile(r"\]\[([^\]\n]+)\]\s*\($")  # "[project][1] (" -- added on R5 DEV (libbar, dev-008)


def markdown_reason(text: str, start: int, end: int) -> str | None:
    if in_fence(text, start):
        return None
    if p4._attributed_blockquote(text, start):
        return "D attributed blockquote (third-party text)"
    if p4._LINKED_PAREN.search(text[max(0, start - 300):start]) and text[end:end + 1] == ")":
        return "D '[project](https://...) (<alias>)' annotates an external project"
    ref = _REF_LINK_PAREN.search(text[max(0, start - 300):start])
    if ref and text[end:end + 1] == ")" and re.search(r"^[ \t]*\[" + re.escape(ref.group(1)) + r"\]:[ \t]*<?https?://",
                                                       text, re.M | re.I):
        return "D '[project][ref] (<alias>)' annotates an external project (reference-style link)"
    if p4._third_party_list_item(text, start):
        return "D linked list item under a third-party / bindings heading"
    return None


LAYERS = {"A": (third_party_reason,), "B": (third_party_reason, historical_reason),
          "C": (third_party_reason, historical_reason, future_reason),
          "D": (third_party_reason, historical_reason, future_reason, markdown_reason)}


def explain(text: str, start: int, end: int, layer: str, ambiguous_only: bool = False) -> str | None:
    """Reason the candidate rejects this occurrence (beyond production's filter), or None."""
    if ambiguous_only and text[start:end].lower() not in AMBIGUOUS:
        return None
    for fn in LAYERS[layer]:
        why = fn(text, start, end)
        if why:
            return why
    return None


# ---- O: overlap-aware fall-through (multi-occurrence finding, not attribution) ------------------------------
_ALIASES = sorted({(a.lower(), c.concept_id) for c in default_registry().all_concepts()
                   for a in c.readme_safe_aliases()}, key=lambda x: -len(x[0]))
_CONCEPT_OF = {a: cid for a, cid in _ALIASES}


def overlap_reason(text: str, start: int, end: int) -> str | None:
    me = _CONCEPT_OF.get(text[start:end].lower())
    for alias, cid in _ALIASES:
        if len(alias) <= end - start or cid == me:
            continue
        lo = max(0, start - len(alias))
        for m in alias_pattern(alias).finditer(text, lo, min(len(text), end + len(alias))):
            if m.start() <= start and end <= m.end() and (m.start(), m.end()) != (start, end):
                return f"O inside the longer alias '{alias}' ({cid})"
    return None


# ---- policies ------------------------------------------------------------------------------------------------
def _rule(layer: str, ambiguous_only: bool = False):
    def rule(text: str, start: int, end: int) -> bool:
        return explain(text, start, end, layer, ambiguous_only) is not None
    return rule


A = p2.Policy("A_third_party", rule=_rule("A"), description="third-party projects / documentation / references")
B = p2.Policy("B_plus_historical", rule=_rule("B"), description="A + bounded historical frames")
C = p2.Policy("C_plus_future", rule=_rule("C"), description="B + future / hypothetical frames")
D = p2.Policy("D_plus_markdown", rule=_rule("D"), description="C + Markdown quote and section attribution")
D_S = p2.Policy("D_S_setext_sections", rule=_rule("D"),
                description="D + setext/fence-aware heading index replacing production's ATX-only index (research)")
D_AMB = p2.Policy("D_ambiguous_only", rule=_rule("D", ambiguous_only=True),
                  description="D restricted to the 11 ambiguous aliases (comparison only)")
O = p2.Policy("O_overlap_fallthrough", rule=lambda t, s, e: overlap_reason(t, s, e) is not None,
              description="NOT attribution: skip an occurrence inside a longer alias of another concept (finding)")
CANDIDATES = (A, B, C, D, D_S)
COMPARISON = (D_AMB, O)
LAYER = {A.name: "A", B.name: "B", C.name: "C", D.name: "D", D_S.name: "D", D_AMB.name: "D"}
SETEXT_POLICIES = frozenset({D_S.name})


class SetextContext:
    """Drop-in for production's ReadmeContext: ATX + setext headings, fenced-code aware (research only)."""

    def __init__(self, text: str) -> None:
        self._text = text

    def enclosing_heading(self, position: int) -> str | None:
        return p4.enclosing_heading(self._text, position)


def explain_policy(policy, text: str, start: int, end: int) -> str | None:
    if policy.name in LAYER:
        return explain(text, start, end, LAYER[policy.name], ambiguous_only=policy.name == D_AMB.name)
    if policy is O:
        return overlap_reason(text, start, end)
    return None


def production_rejects(policy, text: str, start: int, end: int) -> bool:
    ctx = SetextContext(text) if policy.name in SETEXT_POLICIES else rc.build_context(text)
    return rc.is_non_implementation_mention(text, start, end, ctx)


_ORIGINAL_APPLIED = p2.applied


@contextlib.contextmanager
def _applied5(policy):
    """p2.applied plus, for D_S, production's heading index swapped for the setext-aware one."""
    with _ORIGINAL_APPLIED(policy):
        if policy.name in SETEXT_POLICIES:
            saved = readme_mod.build_context
            readme_mod.build_context = SetextContext
            try:
                yield policy
            finally:
                readme_mod.build_context = saved
        else:
            yield policy


@contextlib.contextmanager
def mechanism():
    """Route every `p2.applied(...)` (harness, G22-R2 runners) through `_applied5` for the duration."""
    p2.applied = _applied5
    try:
        yield
    finally:
        p2.applied = _ORIGINAL_APPLIED
