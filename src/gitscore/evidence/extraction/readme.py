"""Milestone 5D -- README concept-mention evidence.

Deterministic, alias-aware, case-insensitive, boundary-aware matching
against the SAME concept registry `resolve_concept()` uses elsewhere --
no separate keyword list, no fuzzy inference, no LLM, no invented
technologies. This is a stricter, registry-driven generalization of
`evidence/v1_bridge.py`'s demonstration README matcher (kept as a
demo-only bridge; this module is the real Milestone 5D extractor).

One Evidence item per matched CONCEPT per repository (never per alias,
never per occurrence) -- a README mentioning "Next.js" three times still
produces exactly one `framework.nextjs` observation, carrying one bounded
snippet from its first occurrence. This is deliberately contextual
mention evidence, not proof of depth of use -- see
`docs/ARCHITECTURE.md`'s confidence-vs-proficiency statement.

Milestone 5D.1 -- matches only `concept.readme_safe_aliases()`, NOT the
full `concept.aliases()` list `resolve_concept()` uses for structured
sources. Free-form prose is a fundamentally more ambiguous matching
context than a package.json key or a GitHub language-stats name: a short
or ordinary-English alias ("go", "next", "js", ...) that's perfectly
unambiguous there produces real false-positive evidence here (see
docs/CHANGELOG_DEV.md's Milestone 5D.1 entry for the real-world
examples this fixed). The exclusion list itself lives on the concept in
`concepts/registry.py` -- this module has no per-alias special-casing.

Milestone 6B: the boundary-regex primitive this module used to define
privately now lives in `concepts/matching.py` (`alias_pattern()`), shared
with `jobs/parsing/concepts.py` -- job-description prose is the SAME
free-form-text risk class README prose is (see that module's docstring
for the full reasoning), so both scan with the identical mechanics. This
is a pure extraction, not a behavior change -- `readme_safe_aliases()`
still decides what THIS module scans.

Milestone 8D.1: candidate per-concept matches are now resolved through
`concepts.matching.select_longest_overlapping_matches()` before becoming
Evidence, so a short alias overlapping a longer, more specific one (e.g.
`framework.react`'s "react" inside `framework.react_native`'s "react
native") no longer produces a false-positive attribution for the shorter
concept -- see that function's docstring. `EXTRACTOR_VERSION` bumped
2 -> 3 for this behavior change.

Milestone 8D.3 -- evidence ATTRIBUTION, not just matching. A
textually-correct alias match can still be the wrong thing to attribute
to this repository: a README's "## notable forks" section lists OTHER
people's separate repositories, each with its own tech stack (the
`karpathy/llm.c` -> `language.cpp` false positive this milestone fixes).
Every alias occurrence (not just the first, previously found via a
single `.search()`) is now checked against
`readme_context.is_non_implementation_mention()` -- see that module's
docstring for the full policy (section-heading denylist + bounded
local adjacency cues for negation/future-intent). An alias whose first
occurrence is excluded now falls through to its next occurrence, and if
every occurrence of one alias is excluded, to the concept's next alias
-- "no safe evidence found yet" no longer means "give up on this
concept entirely." `EXTRACTOR_VERSION` bumped 3 -> 4 for this behavior
change.

Milestone 11-G22-S1 -- `readme:v5` = the setext heading boundary
correction ONLY. `readme_context`'s heading index now recognises setext
headings (`Development` / `-----------`) as well as ATX ones, so a setext
heading ends a preceding denylisted section (whose genuine evidence v4
discarded) and a setext denylisted section (`Related projects` /
`================`) is recognised. Nothing else changed: same denylist,
same adjacency cues, same aliases, same fall-through and deduplication.
`readme:v5` does NOT implement any of the README guard policies researched
and rejected in Milestones 11-G22-R..R5 (D, R3, P4, D_S). `EXTRACTOR_VERSION`
bumped 4 -> 5 for this behavior change.

Milestone 11-G22-S2 -- `readme:v6` = the independent-occurrence overlap
correction on top of v5's setext handling. readme:v5 picked ONE occurrence
per concept (its first non-excluded one) and only then resolved overlaps,
so when that occurrence sat inside a longer alias of another concept
("react" inside "React Native") the concept was dropped even if a separate,
genuine mention followed ("... the web dashboard uses React"). Selection now
skips an occurrence covered by a strictly longer match of another concept
and keeps scanning -- the same "most-specific alias wins" precedence, but
applied per occurrence, as `jobs/parsing/concepts.py` and
`ranking/job_relevance.py` already do. Same-concept alias precedence,
exclusions, deduplication and snippets are unchanged. One same-position
outcome deliberately differs from v5: the 8D.3 following-cue window starts
at a match's END, so a cue can exclude "React Native" while the shorter
"React" inside it escapes; v5 then emitted React evidence whose only source
was the words "React Native" (e.g. "... React Native client ... is not
supported"). v6 never treats that inner "React" as React evidence, whether
or not the React Native mention is itself excluded; a separate, valid
"React" elsewhere is still selected under the unchanged context rules.
`EXTRACTOR_VERSION` bumped 5 -> 6.
"""
from __future__ import annotations

import re

from gitscore.concepts.matching import alias_pattern, select_longest_overlapping_matches
from gitscore.concepts.registry import default_registry
from gitscore.evidence.extraction.readme_context import build_context, is_non_implementation_mention
from gitscore.evidence.models import Evidence, RepositoryIdentity
from gitscore.evidence.types import ConfidenceLevel, EvidenceType

EXTRACTOR_VERSION = "readme:v6"

# How much surrounding text to keep on each side of a match, so the
# stored observation is a short, inspectable snippet -- never the whole
# README duplicated once per concept.
_SNIPPET_RADIUS = 60


def _bounded_snippet(text: str, start: int, end: int) -> str:
    window_start = max(0, start - _SNIPPET_RADIUS)
    window_end = min(len(text), end + _SNIPPET_RADIUS)
    snippet = text[window_start:window_end]
    return re.sub(r"\s+", " ", snippet).strip()


def _inside_longer_other_concept_match(
    start: int, end: int, concept_id: str, all_occurrences: list[tuple[int, int, str]]
) -> bool:
    """Milestone 11-G22-S2 -- is `[start, end)` (an occurrence of
    `concept_id`) overlapped by a STRICTLY LONGER occurrence of a DIFFERENT
    concept? This is the same-position precedence 8D.1's
    `select_longest_overlapping_matches()` already applies ("react" inside
    "React Native" belongs to `framework.react_native`), evaluated per
    occurrence instead of after one occurrence per concept has been
    chosen. Same-concept overlaps ("react" inside "React.js") are left to
    the existing alias order; equal-length overlaps never shadow (as in
    8D.1). It never suppresses an occurrence at a different position.
    """
    return any(
        other_concept != concept_id and o_start < end and o_end > start and (o_end - o_start) > (end - start)
        for o_start, o_end, other_concept in all_occurrences
    )


def evidence_from_readme(
    owner: str, repo_name: str, readme_text: str | None, readme_path: str | None
) -> list[Evidence]:
    """`readme_text`/`readme_path` come from
    `GitHubClient.get_repository_readme_with_path()`. A `None` text (no
    README, or a README the caller could not decode) produces no
    evidence here -- callers are responsible for distinguishing "no
    README" (expected absence) from "README fetch failed" (Milestone 5D
    Part 14) before calling this function.

    Only the RESOLVED path is exercised (mirrors `v1_bridge.py`'s README
    bridge): a mention of something outside the registry produces no
    evidence, since there is no single scalar value (unlike a repo's one
    `primary_language`) to hang an "unresolved" placeholder off of for
    free-form prose -- inventing one would mean guessing at an arbitrary
    substring of the README as "the concept," which the "no arbitrary
    substring matching" rule explicitly forbids.
    """
    if not readme_text:
        return []

    registry = default_registry()
    context = build_context(readme_text)
    # Milestone 11-G22-S2: every occurrence of every README-safe alias, so a
    # concept's occurrence can be checked against OTHER concepts' longer
    # overlapping matches BEFORE it is selected (see
    # `_inside_longer_other_concept_match`).
    all_occurrences = [
        (match.start(), match.end(), concept.concept_id)
        for concept in registry.all_concepts()
        for alias in concept.readme_safe_aliases()
        for match in alias_pattern(alias).finditer(readme_text)
    ]
    candidates: list[tuple[int, int, tuple]] = []
    for concept in registry.all_concepts():
        for alias in concept.readme_safe_aliases():
            # Milestone 8D.3: scan every occurrence of this alias (not
            # just the first) and skip any that
            # `is_non_implementation_mention` flags -- a concept's first
            # textual occurrence being excluded (e.g. inside a "##
            # notable forks" section) no longer means the whole concept
            # is skipped; a later, genuine occurrence of the SAME alias
            # still counts, and if every occurrence of this alias is
            # excluded, the next alias is still tried below.
            #
            # Milestone 11-G22-S2: also skip an occurrence that lies inside
            # a strictly longer match of ANOTHER concept at the same place
            # ("react" inside "React Native") and keep scanning. readme:v5
            # selected that occurrence and then dropped it in the 8D.1
            # overlap resolution below, so a later independent mention
            # ("... uses React") was never considered and the concept was
            # lost.
            selected = None
            for match in alias_pattern(alias).finditer(readme_text):
                if _inside_longer_other_concept_match(
                    match.start(), match.end(), concept.concept_id, all_occurrences
                ):
                    continue
                if not is_non_implementation_mention(readme_text, match.start(), match.end(), context):
                    selected = match
                    break
            if selected is not None:
                candidates.append(
                    (selected.start(), selected.end(), (concept, alias, selected.start(), selected.end()))
                )
                break

    # Milestone 8D.1: resolve any overlapping matches ("react" inside
    # "react native") by keeping only the most specific one -- see
    # `concepts.matching.select_longest_overlapping_matches()`'s
    # docstring for the full rationale (shared with
    # `jobs/parsing/concepts.py`'s `find_concept_mentions`, the SAME
    # risk class in a different free-form-text context).
    evidence = []
    for concept, matched_alias, start, end in select_longest_overlapping_matches(candidates):
        snippet = _bounded_snippet(readme_text, start, end)
        evidence.append(
            Evidence(
                repository=RepositoryIdentity(owner=owner, name=repo_name),
                evidence_type=EvidenceType.README,
                raw_observation=f"README mentions '{matched_alias}': ...{snippet}...",
                concept_id=concept.concept_id,
                confidence=ConfidenceLevel.MODERATE,
                extractor_version=EXTRACTOR_VERSION,
                file_path=readme_path or "README.md",
            )
        )
    return evidence
