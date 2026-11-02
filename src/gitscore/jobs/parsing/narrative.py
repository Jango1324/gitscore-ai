"""Milestone 10E -- narrative-cue detection.

A small, curated table of GENERIC (never role- or employer-specific)
grammatical cues that a sentence is describing what the EMPLOYER will
teach/expose the candidate to (LEARNING narrative), or is describing the
employer's OWN product/team/history (COMPANY narrative) -- never a
statement of what the applicant must already possess. Mirrors
`non_technical.py`'s own existing separation precedent: a small, curated,
structural pattern table, isolated in its own module so it can be
unit-tested independently of section-origin logic
(`jobs/parsing/necessity.py::resolve_necessity_hint`, the sole caller).

Confirmed, via the real SOTI posting's own wording (Milestone 10E Phase 1
trace, `docs/evaluation/MILESTONE_10E_NARRATIVE_REQUIREMENT_SEMANTICS.md`):
"The technologies you learn during an internship at SOTI range from
learning to develop middle tier services using languages like C#, or
deepening your knowledge of databases by leveraging SQL..." -- a
narrative paragraph preceding the SAME document's own later, real
"Required skills:" section, today fabricated into a scored
`(language.csharp, language.sql)` alternative-group requirement because
nothing downstream of `_looks_like_requirement`'s admission gate ever
asks WHAT the sentence is describing, only whether it mentions a known
technology at all.

**Deliberately NOT a large keyword blacklist and NOT a company-specific
exception table** (the milestone's own explicit restriction): exactly
two regexes, each a GRAMMATICAL shape ("you will/you'll learn/gain...",
"our product/team/engineers... uses/builds/develops...", "we have
used/built/leveraged...") rather than any specific technology, employer,
or industry term. `jobs/parsing/necessity.py::resolve_necessity_hint`
is the ONLY caller, and only consults this module AFTER an explicit
local REQUIRED/PREFERRED marker has already been checked and found
absent, and only when the claim's section-origin was ALREADY eligible
(a genuine `REQUIRED`/`PREFERRED` section, or a genuinely unsectioned
whole document) -- an explicit local marker always wins unconditionally,
regardless of anything in this module (confirmed by Milestone 10E's own
51-control corpus, categories C/F/G: "Willingness to learn new
technologies is required." and "You will learn SQL, but prior knowledge
of databases is required." both correctly remain scored qualifications).
"""
from __future__ import annotations

import re

_LEARNING_NARRATIVE_CUE = re.compile(
    r"\byou(?:'ll| will) (?:learn|gain|have the opportunity to)\b|"
    r"\bthe (?:technologies|skills|tools) you(?:'ll| will)? learn\b|"
    r"\byou may (?:get an opportunity to )?learn\b|"
    r"\bdeepen(?:ing)? your knowledge\b|\bgain (?:an? )?(?:understanding|exposure)\b",
    re.IGNORECASE,
)

_COMPANY_NARRATIVE_CUE = re.compile(
    r"\bour (?:product|platform|company|engineers?|team)\b[^.?!]*\b"
    r"(?:uses?|use|built|builds?|develops?|leverages?)\b|"
    r"\bwe(?:'ve| have)? (?:used|built|developed?|leverage[ds]?)\b|"
    # Milestone 11-A1 -- "our <optional Capitalized/compound token> <structural
    # system noun>" (e.g. "our Node.js backend," "our React frontend," "our
    # codebase," "our infrastructure") -- confirmed, during M11's evaluation
    # review, to escape the three patterns above entirely (neither contains a
    # listed noun/verb pair in the required order). Deliberately a SEPARATE,
    # narrower alternative with no verb requirement at all: this structural-
    # noun vocabulary is generic across any employer (never a product/company
    # name) and specific enough on its own -- a sentence naming "our backend"/
    # "our frontend"/"our codebase"/"our infrastructure" is, in practice,
    # always describing the EMPLOYER's own system, never a candidate
    # qualification -- unlike the broader "our + ANY noun phrase" heuristic
    # this milestone's own Phase 5 probe measured and rejected for trading
    # these false positives for new false suppressions
    # (`scripts/evaluation_lib/m11_generalization_probe.py`,
    # docs/evaluation/MILESTONE_11_GENERALIZABLE_JOB_UNDERSTANDING.md §5.1).
    # An explicit local REQUIRED/PREFERRED marker still wins unconditionally
    # regardless (checked first by every caller of `contains_narrative_cue`),
    # so "Experience with our React codebase is required" is unaffected.
    r"\bour\s+(?:[\w.\-]+\s+){0,2}(?:backend|frontend|front-end|back-end|codebase|infrastructure)\b",
    re.IGNORECASE,
)


def contains_narrative_cue(text: str) -> bool:
    """`True` iff `text` matches a LEARNING-opportunity or
    COMPANY/product-narrative grammatical shape -- see this module's own
    docstring for the exact two patterns and their scope.
    """
    return _LEARNING_NARRATIVE_CUE.search(text) is not None or _COMPANY_NARRATIVE_CUE.search(text) is not None
