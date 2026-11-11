"""Milestone 11-G22-R -- candidate ambiguous-alias policies (OFFLINE research adapters).

Nothing here is imported by `src/gitscore`. `applied(policy)` temporarily rebinds names inside
the REAL production modules, in-process, and restores them on exit:

  * job side      -- G22's own adapter (`m11g22_policies.applied`) with G22's policy A or B;
  * README side   -- `evidence.extraction.readme.is_non_implementation_mention` (the existing
                     per-occurrence attribution filter, 8D.3) is wrapped so a policy may reject
                     MORE occurrences. Every other part of the extractor (alias table, overlap
                     resolution, fall-through to the next occurrence/alias, one item per concept,
                     MODERATE confidence) is the unmodified production code;
  * study R       -- not an extractor change: README evidence for a concept with no non-README
                     corroboration anywhere in the candidate's evidence is dropped before the
                     profile is matched. This CHANGES what SUPPORTED means (matcher / evidence
                     contract) and is measured only to answer the README-only sufficiency question.

  BASE  production v15 / readme:v4, nothing patched
  A     job side only: G22 A (G20 generic-usage guard, no alias metadata)
  B     README side only: the same generic-usage predicate applied to README occurrences
  C     shared rule: A on job text + B on README text
  D     per-alias metadata, separate policies: job = G22 B (7 reviewed aliases + technical cue);
        README = 11 reviewed aliases (G22's 7 + python, java, flask, pandas) require a README-specific
        technical corroboration cue
  R     study only: README-only evidence is not sufficient on its own (semantic change)
  DR    D + R (study only)

Design set: DEV. EVAL is run only after `evaluation/m11g22r/policy_design_freeze.json` records
this file's hash.
"""
from __future__ import annotations

import contextlib
import re
from dataclasses import dataclass

import m11g22_policies as g22pol
from gitscore.concepts.registry import default_registry
from gitscore.evidence.extraction import readme as readme_mod
from gitscore.jobs.parsing.concepts import ConceptMention, find_concept_mentions

_REG = default_registry()
_ALIAS_TO_CONCEPT = {a.lower(): c for c in _REG.all_concepts() for a in c.readme_safe_aliases()}
AMBIGUOUS_ALIASES = g22pol.AMBIGUOUS_ALIASES  # the SAME reviewed list G22 froze (react express swift rust ruby shell torch)
# README prose is a different source: G22 judged python / java / flask / pandas rare in JOB prose (snake / coffee /
# lab glass / animal), but project READMEs describe pets, cafes, labs and zoos. Reviewed on DEV (d08-d10) before the
# policy design freeze: the README list adds exactly these four registry aliases; the job list stays G22's seven.
README_AMBIGUOUS_ALIASES = AMBIGUOUS_ALIASES | frozenset({"python", "java", "flask", "pandas"})


def _concept_for(text: str, start: int, end: int):
    return _ALIAS_TO_CONCEPT.get(text[start:end].lower())


# ---- B: generic-usage predicate on README occurrences -----------------------------------------
def readme_generic_usage(text: str, start: int, end: int) -> bool:
    concept = _concept_for(text, start, end)
    return concept is not None and g22pol.generic_usage(text, start, end, concept.display_name)


# ---- D: README-specific corroboration for reviewed ambiguous aliases --------------------------
_SENTENCE_BREAK = re.compile(r"(?:[.!?](?=\s)|\n)")
_INSTALL_OR_VERSION = re.compile(r"^\s*(?:[<>=~!]=?|==)\s*\d|^\s*\d+(?:\.\d+)+", re.I)
# README claim-of-use frames immediately before the alias ("uses flask", "built with react", "Stack: react").
# Added on DEV (d19) before the policy design freeze; G22's job-side lead-ins stay as G22 froze them.
_README_USE_FRAME = re.compile(
    r"\b(?:uses?|using|built\s+(?:with|on|in)|written\s+in|powered\s+by|requires?|needs?|stack|implemented\s+in|"
    r"based\s+on)\s*:?\s*$", re.I)


def _sentence(text: str, start: int, end: int) -> tuple[int, str]:
    left = max((m.end() for m in _SENTENCE_BREAK.finditer(text, 0, start)), default=0)
    right_m = _SENTENCE_BREAK.search(text, end)
    right = right_m.start() if right_m else len(text)
    return left, text[left:right]


def _in_code(text: str, start: int, end: int) -> bool:
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    line = text[line_start:line_end if line_end != -1 else len(text)]
    inline = line[: start - line_start].count("`") % 2 == 1
    fenced = text[:start].count("```") % 2 == 1
    return inline or fenced


def readme_has_technical_cue(text: str, start: int, end: int) -> bool:
    if _in_code(text, start, end) or text[text.rfind("\n", 0, start) + 1:start].lstrip().startswith("#"):
        return True  # code span / fence, or a heading line
    if _INSTALL_OR_VERSION.match(text[end:]):
        return True  # "torch >= 2.0", "react 18.3"
    offset, sentence = _sentence(text, start, end)
    if _README_USE_FRAME.search(sentence[: start - offset]):
        return True  # README claim of use

    concept = _concept_for(text, start, end)
    m = ConceptMention(concept.concept_id, text[start:end].lower(), start - offset, end - offset)
    others = [o for o in find_concept_mentions(sentence) if not (o.start < m.end and m.start < o.end)]
    return g22pol._has_cue(sentence, m, others)


def readme_ambiguous_without_cue(text: str, start: int, end: int) -> bool:
    return text[start:end].lower() in README_AMBIGUOUS_ALIASES and not readme_has_technical_cue(text, start, end)


# ---- policy plumbing ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Policy:
    name: str
    job: object = g22pol.BASE
    readme_rule: object = None
    readme_only_insufficient: bool = False
    description: str = ""


BASE = Policy("BASE", description="production parser v15 / README extractor readme:v4")
A = Policy("A_job_generic_usage", job=g22pol.A, description="job side: G22 A generic-usage guard")
B = Policy("B_readme_generic_usage", readme_rule=readme_generic_usage,
           description="README side: the generic-usage predicate on each README occurrence")
C = Policy("C_shared_generic_usage", job=g22pol.A, readme_rule=readme_generic_usage,
           description="one shared rule for job text and README text (A + B)")
D = Policy("D_alias_metadata_split", job=g22pol.B, readme_rule=readme_ambiguous_without_cue,
           description="7 reviewed ambiguous aliases; job = G22 B cue rule, README = README-specific cue rule")
R = Policy("R_readme_only_insufficient", readme_only_insufficient=True,
           description="STUDY ONLY (semantic change): README evidence needs non-README corroboration")
DR = Policy("DR_metadata_plus_corroboration", job=g22pol.B, readme_rule=readme_ambiguous_without_cue,
            readme_only_insufficient=True, description="STUDY ONLY: D + R")
POLICIES = (BASE, A, B, C, D, R, DR)


@contextlib.contextmanager
def applied(policy: Policy):
    saved = readme_mod.is_non_implementation_mention
    rule = policy.readme_rule

    def wrapped(text, start, end, context):
        return saved(text, start, end, context) or rule(text, start, end)

    with g22pol.applied(policy.job):
        try:
            if rule is not None:
                readme_mod.is_non_implementation_mention = wrapped
            yield policy
        finally:
            readme_mod.is_non_implementation_mention = saved
