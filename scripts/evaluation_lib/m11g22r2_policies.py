"""Milestone 11-G22-R2 -- README evidence context policies (OFFLINE research adapters).

Nothing here is imported by `src/gitscore`. `applied(policy)` wraps the production README extractor's existing
per-occurrence attribution filter (`evidence.extraction.readme.is_non_implementation_mention`, 8D.3) so a policy may
reject MORE occurrences; everything else in `readme:v4` (alias table, overlap resolution, fall-through to the next
occurrence and alias, one item per concept per repository, MODERATE confidence) is unmodified. Policy E additionally
reinterprets the finished profile (a semantic change, see below). The job parser is never patched.

  A     current readme:v4 (nothing patched)
  Dref  G22-R policy D, unchanged (reference baseline)
  B     revised per-occurrence context rules for the 11 README-ambiguous aliases: G22-R D's cue rule with the
        permissive "of" / "and" / "or" lead-ins removed and list-sibling cues restricted to registry siblings;
        technical casing mid-sentence still counts
  C     per-alias ambiguity metadata: each ambiguous alias needs an ALIAS-SPECIFIC technical collocate in its
        sentence (or code / heading / version / claim-of-use frame / registry list sibling); casing never counts
  D     hybrid: C for ambiguous aliases + explicit non-use frames (reference / future / historical) for ALL aliases
  E     D + corroboration-aware interpretation: README evidence with no non-README corroboration counts only if its
        occurrence carries an explicit claim-of-use frame (changes when evidence is sufficient -> matcher-contract
        review if ever implemented)
  F     conservative fallback: ambiguous aliases need an EXPLICIT claim-of-use frame, code, heading or version;
        collocates alone are not enough; plus D's non-use frames

Design set: DEV only. Non-use frames are DEV's own phrasings and their grammatical variants; EVAL's wording was not
used to write them (same author, disclosed). Frozen in `evaluation/m11g22r2/policy_design_freeze.json` before EVAL ran.
"""
from __future__ import annotations

import contextlib
import re
from dataclasses import dataclass

import m11g22_policies as g22pol
import m11g22r_policies as rpol
from gitscore.evidence.extraction import readme as readme_mod
from gitscore.jobs.parsing.concepts import find_concept_mentions

AMBIGUOUS = rpol.README_AMBIGUOUS_ALIASES  # G22-R's reviewed README list (11 aliases)
_I = re.IGNORECASE

# ---- shared occurrence context ----------------------------------------------------------------------
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9.+#-]*")
_USE_FRAME = re.compile(  # explicit claim that THIS project uses the technology, immediately before the alias
    r"\b(?:uses?|using|built\s+(?:with|on|in)|written\s+in|powered\s+by|implemented\s+in|based\s+on|"
    r"runs?\s+(?:in|on)|requires?|needs?|stack)\s*:?\s*(?:the\s+|a\s+)?$", _I)
_STRONG_LEAD = re.compile(r"\b(?:with|in|using|on|via)\s+$", _I)  # B: "of" / "and" / "or" deliberately removed


def _token_window(sentence: str, s: int, e: int) -> set[str]:
    return {w.lower().rstrip(".") for w in _WORD.findall(sentence[:s] + " " + sentence[e:])}


def _occurrence(text: str, start: int, end: int):
    offset, sentence = rpol._sentence(text, start, end)
    return sentence, start - offset, end - offset


def strong_structural_cue(text: str, start: int, end: int) -> bool:
    """Code / inline code, a heading line, a version or install string, or an explicit claim-of-use frame."""
    if rpol._in_code(text, start, end) or text[text.rfind("\n", 0, start) + 1:start].lstrip().startswith("#"):
        return True
    if rpol._INSTALL_OR_VERSION.match(text[end:]):
        return True
    sentence, s, _ = _occurrence(text, start, end)
    return bool(_USE_FRAME.search(sentence[:s]))


def _registry_list_sibling(sentence: str, s: int, e: int) -> bool:
    for o in find_concept_mentions(sentence):
        if o.start < e and s < o.end:
            continue
        between = sentence[e:o.start] if o.start >= e else sentence[o.end:s]
        if re.fullmatch(r"[\s,/&+]*(?:and|or)?[\s,/&+]*", between, _I) and between.strip(" ") != "":
            return True
    return False


# ---- B: revised generic cue rule ---------------------------------------------------------------------
def cue_b(text: str, start: int, end: int) -> bool:
    if strong_structural_cue(text, start, end):
        return True
    sentence, s, e = _occurrence(text, start, end)
    surface = sentence[s:e]
    if surface != surface.lower() and re.search(r"\w", sentence[:s]):
        return True  # technical casing mid-sentence (still fooled by capitalised homonyms)
    if surface == surface.lower() and _STRONG_LEAD.search(sentence[:s]):
        return True
    if g22pol._HEAD_NOUN_AFTER.match(sentence[e:]):
        return True
    return _registry_list_sibling(sentence, s, e)


# ---- C: alias-specific technical collocates (per-alias metadata) --------------------------------------
COLLOCATES = {
    "react": {"component", "components", "hooks", "jsx", "props", "state", "ui", "frontend", "app", "native", "dom",
              "redux", "vite", "spa"},
    "express": {"express.js", "node", "node.js", "middleware", "server", "backend", "router", "routes", "api",
                "endpoint", "endpoints"},
    "swift": {"ios", "macos", "swiftui", "xcode", "package", "app", "apple", "cocoapods"},
    "rust": {"cargo", "crate", "crates", "rustc", "borrow", "unsafe", "cli", "command-line", "tool", "binary", "wasm",
             "webassembly"},
    "ruby": {"rails", "gem", "gems", "bundler", "rake", "rubocop", "application", "app", "script", "rbenv", "rvm"},
    "java": {"jvm", "spring", "maven", "gradle", "service", "application", "app", "class", "jdk", "android", "kotlin"},
    "shell": {"script", "scripts", "scripting", "bash", "zsh", "command", "commands", "terminal", "cli"},
    "torch": {"pytorch", "model", "models", "tensor", "tensors", "cuda", "nn", "training", "trains", "torchvision",
              "cnn"},
    "python": {"script", "scripts", "package", "pip", "module", "library", "code", "tool", "tooling", "sdk", "cli",
               "visualizer", "notebook", "virtualenv", "venv"},
    "flask": {"app", "application", "api", "web", "route", "routes", "server", "blueprint", "jinja", "backend"},
    "pandas": {"dataframe", "dataframes", "csv", "numpy", "series", "notebook"},
}


def cue_c(text: str, start: int, end: int) -> bool:
    if strong_structural_cue(text, start, end):
        return True
    sentence, s, e = _occurrence(text, start, end)
    if _token_window(sentence, s, e) & COLLOCATES.get(sentence[s:e].lower(), set()):
        return True
    return _registry_list_sibling(sentence, s, e)


# ---- D: explicit non-use frames (all aliases) -----------------------------------------------------------
_NONUSE_BEFORE = re.compile(
    r"\b(?:inspired\s+by|migrat(?:e|es|ing)\s+(?:\w+\s+){0,3}to|consider(?:s|ing)?|previously\s+used|used\s+to\s+use)"
    r"\s+(?:\w+\s+){0,1}$", _I)
_NONUSE_AFTER = re.compile(r"^[\w\s]{0,30}?\b(?:can|could|may|might)\s+be\s+generated\b", _I)


def nonuse_frame(text: str, start: int, end: int) -> bool:
    sentence, s, e = _occurrence(text, start, end)
    return bool(_NONUSE_BEFORE.search(sentence[:s]) or _NONUSE_AFTER.match(sentence[e:]))


def _ambiguous(text: str, start: int, end: int) -> bool:
    return text[start:end].lower() in AMBIGUOUS


def rule_b(text, start, end):
    return _ambiguous(text, start, end) and not cue_b(text, start, end)


def rule_c(text, start, end):
    return _ambiguous(text, start, end) and not cue_c(text, start, end)


def rule_d(text, start, end):
    return nonuse_frame(text, start, end) or rule_c(text, start, end)


def rule_f(text, start, end):
    return nonuse_frame(text, start, end) or (_ambiguous(text, start, end) and not strong_structural_cue(text, start, end))


_SNIPPET = re.compile(r"^README mentions '([^']+)': \.\.\.(.*)\.\.\.$", re.S)


def readme_item_has_use_frame(raw_observation: str) -> bool:
    """E: does the stored provenance snippet show an explicit claim-of-use frame before the alias?"""
    m = _SNIPPET.match(raw_observation)
    if not m:
        return False
    alias, snippet = m.group(1), m.group(2)
    # snippets are whitespace-collapsed (newlines gone), so heading / fence structure is NOT recoverable here:
    # only the claim-of-use frame within the snippet's own sentence, a version string or inline code count
    for occ in re.finditer(r"(?<![A-Za-z0-9])" + re.escape(alias) + r"(?![A-Za-z0-9])", snippet, _I):
        before = re.split(r"[.!?]\s", snippet[:occ.start()])[-1]
        if (_USE_FRAME.search(before) or rpol._INSTALL_OR_VERSION.match(snippet[occ.end():])
                or before.count("`") % 2 == 1):
            return True
    return False


@dataclass(frozen=True)
class Policy:
    name: str
    rule: object = None
    corroboration_interpretation: bool = False
    description: str = ""


A = Policy("A_current_readme_v4", description="production readme:v4")
DREF = Policy("Dref_g22r_policy_d", rule=rpol.readme_ambiguous_without_cue, description="G22-R policy D (reference)")
B = Policy("B_revised_context_rules", rule=rule_b, description="G22-R D cues minus of/and/or lead-ins; casing kept")
C = Policy("C_alias_collocates", rule=rule_c, description="per-alias technical collocates; casing never counts")
D = Policy("D_hybrid_use_frames", rule=rule_d, description="C + explicit non-use frames for every alias")
E = Policy("E_corroboration_interpretation", rule=rule_d, corroboration_interpretation=True,
           description="D + README-only evidence needs an explicit claim-of-use frame (semantic change)")
F = Policy("F_conservative_fallback", rule=rule_f, description="ambiguous aliases need explicit use/code/version cues")
POLICIES = (A, DREF, B, C, D, E, F)


@contextlib.contextmanager
def applied(policy: Policy):
    saved = readme_mod.is_non_implementation_mention
    rule = policy.rule

    def wrapped(text, start, end, context):
        return saved(text, start, end, context) or rule(text, start, end)

    try:
        if rule is not None:
            readme_mod.is_non_implementation_mention = wrapped
        yield policy
    finally:
        readme_mod.is_non_implementation_mention = saved


def interpret(profile, policy: Policy):
    """E only: drop README evidence that is neither corroborated by another artifact nor an explicit use claim."""
    if not policy.corroboration_interpretation:
        return profile
    from gitscore.evidence.profile import build_candidate_evidence_profile
    from gitscore.evidence.types import EvidenceType
    corroborated = {e.concept_id for e in profile.evidence if e.evidence_type != EvidenceType.README}
    kept = [e for e in profile.evidence if e.evidence_type != EvidenceType.README or e.concept_id in corroborated
            or readme_item_has_use_frame(e.raw_observation)]
    return build_candidate_evidence_profile(profile.candidate, profile.coverage.discovered, profile.coverage.analyzed,
                                            kept, collected_at=profile.collected_at)
