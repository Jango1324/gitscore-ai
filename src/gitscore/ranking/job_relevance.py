"""Milestone 8D.2 -- Stage-2 job-aware repository relevance (retrieval).

Milestone 5B's `rank.py` answers one job-INDEPENDENT question: "which
repositories look substantively real" (size/recency/language-presence/
description-presence/stars). Milestone 8C's real-world evaluation found
that this alone can and does exclude a small repository that is highly
relevant to a SPECIFIC job posting -- e.g. `karpathy/nn-zero-to-hero`
(an ML teaching repo, 24.6k stars) falling outside a 63-repository
account's top-15 cutoff, or `Jango1324/Pneumonia-Detection-Ai` (an
illustrative ML example from this project's own Milestone 8A write-up)
never receiving deep analysis at all. This module adds a SECOND,
independent retrieval signal -- "does this repository look relevant to
THIS job's technical asks" -- and a deterministic union with the frozen
Stage-1 ranking, per `docs/evaluation/MILESTONE_8D2_JOB_AWARE_RETRIEVAL.md`.

`rank.py`/`config.py` (Milestone 5B) are NOT modified by this module and
are not imported for their internals beyond `rank_repositories()` itself
-- the generic ranking formula/weights/version remain completely frozen.
This module's own `JOB_RELEVANCE_VERSION` versions ONLY the relevance
formula/weights/budget defined here.

Dependency direction (deliberate, see
docs/evaluation/MILESTONE_8D2_JOB_AWARE_RETRIEVAL.md for the full
rationale): this module imports ONLY `gitscore.concepts` (the same
registry/alias-matching primitives `evidence/extraction/readme.py` and
`jobs/parsing/concepts.py` already use) plus this package's own
`rank.py`/`config.py`. It has NO dependency on `gitscore.jobs` -- the
`JobRelevanceTerm` dataclass below is a small, neutral retrieval-query
representation (a tuple of concept ids + a weight) rather than the full
`JobRequirementProfile`/`JobRequirement` domain model, so
`gitscore.pipeline.evidence.extract_candidate_evidence()` (explicitly a
candidate-only, job-independent entry point) never has to import
`gitscore.jobs` to accept it. The one caller that DOES know about both
`gitscore.jobs` and this module is `gitscore.application.job_fit` --
already documented as "the one layer allowed to know about all of them
together" -- which converts a real `JobRequirementProfile` into
`tuple[JobRelevanceTerm, ...]` before calling into this package.

Text-scanning reuses the EXACT SAME shared primitives 8D.1 introduced
for README/job-description prose (`concepts.matching.alias_pattern` +
`select_longest_overlapping_matches`) rather than importing
`jobs.parsing.concepts.find_concept_mentions()` -- mirroring
`evidence/extraction/readme.py`'s own collection loop, the established
pattern in this codebase: share the low-level matching PRIMITIVE across
every free-form-text consumer, let each consumer own its own thin
orchestration loop suited to its own output shape, rather than share one
orchestration function across unrelated packages.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from gitscore.concepts.matching import alias_pattern, select_longest_overlapping_matches
from gitscore.concepts.normalize import normalize_term
from gitscore.concepts.registry import ConceptRegistry, default_registry, is_unresolved_concept_id
from gitscore.ranking.config import DEFAULT_TOP_N, RankingWeights
from gitscore.ranking.rank import rank_repositories

JOB_RELEVANCE_VERSION = 1

# Stage-2 budget (Part 9): at most this many ADDITIONAL repositories
# beyond the generic top-N may be pulled in by job relevance, and at
# most this many TOTAL repositories may ever be selected for deep
# analysis. With the shipped defaults (N=15, K=10), the maximum possible
# analyzed-repository count is 15 + 10 = 25 -- `DEFAULT_MAX_SELECTED`
# below is set to exactly that sum, so it is a redundant-but-explicit
# safety cap, never a looser limit than the N/K pairing already implies.
DEFAULT_RELEVANCE_TOP_K = 10
DEFAULT_MAX_SELECTED = 25

# Deterministic, Necessity-based retrieval weight (Part 7): a REQUIRED
# technical requirement contributes more retrieval pull than a PREFERRED
# one. Deliberately just two fixed floats -- no `Importance`-based
# scaling, no learned/tuned weighting -- mirroring `jobs.types.Necessity`
# itself being "deliberately just two states" and this project's own
# instruction (jobs/types.py's `Importance` docstring) against
# fake-precision floating-point weights without strong justification.
REQUIRED_WEIGHT = 1.0
PREFERRED_WEIGHT = 0.5


@dataclass(frozen=True)
class JobRelevanceTerm:
    """One retrieval-relevance signal, independent of the job domain model.

    `concept_ids` is ONE id for a single resolved- or unresolved-concept
    requirement, or 2+ ids for an alternative group ("Python or Go",
    Part 4) -- matching ANY ONE of them satisfies this term; the ANY
    semantics are exactly `JobRequirement.alternative_concept_ids`'s own
    (reused directly by the caller that builds these, never re-parsed
    from OR text here). `weight` is the retrieval pull this one
    requirement contributes if matched (see `REQUIRED_WEIGHT`/
    `PREFERRED_WEIGHT`).
    """

    concept_ids: tuple[str, ...]
    weight: float

    def __post_init__(self) -> None:
        if not self.concept_ids:
            raise ValueError("JobRelevanceTerm.concept_ids must not be empty")
        if len(set(self.concept_ids)) != len(self.concept_ids):
            raise ValueError(f"JobRelevanceTerm.concept_ids contains a duplicate: {self.concept_ids!r}")
        if self.weight <= 0:
            raise ValueError(f"JobRelevanceTerm.weight must be > 0, got {self.weight!r}")


@dataclass(frozen=True)
class RepositoryRelevanceResult:
    """One repository's job-relevance outcome, with an explainable
    per-term breakdown (Part "RELEVANCE SIGNAL" -- "a result should be
    explainable"). Not part of any public API response; consumed by
    tests and the offline evaluator (`scripts/evaluate_repository_retrieval.py`).
    """

    name: str
    relevance_score: float
    matched_terms: tuple[JobRelevanceTerm, ...] = field(default_factory=tuple)
    reasons: tuple[str, ...] = field(default_factory=tuple)


def _repo_text(summary: dict) -> str:
    """Repository name + description + topics, joined -- the ONLY cheap,
    pre-deep-extraction free text available for every repository without
    an additional fetch (Part "USE ONLY CHEAP PRE-DEEP-EXTRACTION
    INFORMATION"). Never includes a README, manifest, or source file.
    """
    parts = [summary.get("name") or "", summary.get("description") or ""]
    parts.extend(summary.get("topics") or [])
    return " ".join(parts)


def _registered_concept_matches(text: str, registry: ConceptRegistry) -> frozenset[str]:
    """Every registered concept whose README-safe alias appears in
    `text`, after the SAME "most-specific alias wins" overlap resolution
    8D.1 introduced for README/job-description prose. Deliberately
    reuses `readme_safe_aliases()` (NOT the full `aliases` list): repo
    name/description/topics are short, human-written free text carrying
    the identical false-positive risk class as README prose (Milestone
    5D.1) -- a bare, ordinary-English alias like "go" or the single
    letter "c" must not match here, exactly as it must not match a
    README. A C/C++/Swift-only repository is still retrievable via the
    structured `primary_language` field (`_language_match`, below) even
    when its name/description/topics carry no safe textual alias --
    mirroring how language-stats evidence already resolves `language.c`
    while README text never does (see `concepts/models.py`'s
    `readme_safe_aliases()` docstring, whose "used exclusively by the
    README extractor" note predates this second caller).
    """
    candidates = []
    for concept in registry.all_concepts():
        for alias in concept.readme_safe_aliases():
            for match in alias_pattern(alias).finditer(text):
                candidates.append((match.start(), match.end(), concept.concept_id))
    return frozenset(select_longest_overlapping_matches(candidates))


def _language_match(primary_language, concept_id: str, registry: ConceptRegistry) -> bool:
    """Does the repository's GitHub-reported primary language resolve,
    through the SAME structured-source resolution `languages.py` uses
    (the full `aliases` list, not `readme_safe_aliases()` -- `language`
    is a single already-scoped GitHub value, not free prose), to exactly
    this concept id? Only ever true for a REAL registered concept --
    `lookup_by_normalized_alias` never matches an `unresolved:<term>` id.
    """
    if not primary_language:
        return False
    concept = registry.lookup_by_normalized_alias(normalize_term(primary_language))
    return concept is not None and concept.concept_id == concept_id


def _unresolved_term_match(concept_id: str, text: str) -> bool:
    """Bounded, exact, word-boundary-safe match for an `unresolved:<term>`
    requirement against repo name/description/topics -- Part 5's "exact
    normalized/boundary-aware matching only, no fuzzy matching," reusing
    `concepts.matching.alias_pattern` (the same boundary-safety primitive
    every other matcher in this codebase uses) rather than inventing a
    second pattern-building rule.
    """
    term = concept_id.removeprefix("unresolved:").replace("_", " ")
    return bool(term) and bool(alias_pattern(term).search(text))


def _concept_id_matches_repo(concept_id: str, summary: dict, text: str, registered_matches, registry) -> bool:
    if is_unresolved_concept_id(concept_id):
        return _unresolved_term_match(concept_id, text)
    return _language_match(summary.get("primary_language"), concept_id, registry) or concept_id in registered_matches


def score_repository_relevance(
    summary: dict,
    terms: tuple[JobRelevanceTerm, ...],
    registry: ConceptRegistry | None = None,
) -> RepositoryRelevanceResult:
    """Score one repository summary against a job's relevance terms.

    Each term contributes its `weight` AT MOST ONCE, the instant ANY ONE
    of its `concept_ids` matches (language field OR safe-alias text OR
    bounded unresolved-term text) -- a term matching through two signals
    at once (e.g. both the language field AND the repo name) still
    counts once; this is a presence/retrieval signal, not an evidence
    tally (Part 8 -- relevance is for RETRIEVAL, never candidate
    scoring). A repository matching zero terms scores exactly `0.0`.
    """
    registry = registry or default_registry()
    text = _repo_text(summary)
    registered_matches = _registered_concept_matches(text, registry)

    total = 0.0
    matched_terms: list[JobRelevanceTerm] = []
    reasons: list[str] = []
    for term in terms:
        for concept_id in term.concept_ids:
            if _concept_id_matches_repo(concept_id, summary, text, registered_matches, registry):
                total += term.weight
                matched_terms.append(term)
                reasons.append(f"{concept_id} (weight {term.weight})")
                break

    return RepositoryRelevanceResult(
        name=summary["name"],
        relevance_score=total,
        matched_terms=tuple(matched_terms),
        reasons=tuple(reasons),
    )


def _relevance_sort_key(result: RepositoryRelevanceResult):
    # Deterministic tie-break (Part 10): score descending, then
    # repository name ascending/case-insensitive. No recency/size
    # tie-break level (unlike rank.py's `_sort_key`) -- relevance is a
    # topical-match signal, not a substantiveness signal, so a repo's
    # push recency has no principled bearing on it here.
    return (-result.relevance_score, result.name.lower())


def select_job_relevant_repositories(
    summaries,
    terms: tuple[JobRelevanceTerm, ...],
    top_k: int = DEFAULT_RELEVANCE_TOP_K,
    registry: ConceptRegistry | None = None,
) -> list[RepositoryRelevanceResult]:
    """Score every summary, drop zero-relevance repositories entirely
    (Part "zero-relevance repo excluded from relevance top K"), and
    return the top `top_k` by the deterministic tie-break above.
    """
    registry = registry or default_registry()
    scored = [score_repository_relevance(summary, terms, registry=registry) for summary in summaries]
    relevant = [result for result in scored if result.relevance_score > 0.0]
    relevant.sort(key=_relevance_sort_key)
    return relevant[:top_k]


@dataclass(frozen=True)
class RepositorySelection:
    """The final, deterministic set of repositories selected for bounded
    deep analysis -- the union of Milestone 5B's frozen generic ranking
    and (only if job context was supplied) this module's job-relevance
    retrieval.

    `names` preserves `generic_names`'s own order FIRST, then appends
    `job_relevant_additions` (repositories not already in `generic_names`)
    in relevance order -- Part 9's suggested policy, adopted as-is: the
    frozen Stage-1 ranking's own order is never silently reordered.
    """

    names: tuple[str, ...]
    generic_names: tuple[str, ...]
    job_relevant_additions: tuple[str, ...] = ()
    relevance_results: tuple[RepositoryRelevanceResult, ...] = ()


def select_repositories(
    summaries,
    *,
    top_n: int = DEFAULT_TOP_N,
    job_relevance_terms: tuple[JobRelevanceTerm, ...] | None = None,
    relevance_top_k: int = DEFAULT_RELEVANCE_TOP_K,
    max_selected: int = DEFAULT_MAX_SELECTED,
    weights: RankingWeights | None = None,
    reference_time: datetime | None = None,
    registry: ConceptRegistry | None = None,
) -> RepositorySelection:
    """Select repositories for bounded deep analysis.

    Without `job_relevance_terms` (`None` or empty -- the default), this
    is EXACTLY `rank_repositories(summaries, top_n=...)`: byte-for-byte
    the Milestone 5D behavior before this milestone, so
    `extract_candidate_evidence()`'s candidate-only call path is
    unaffected. With `job_relevance_terms`, the result is the
    deterministic union described on `RepositorySelection`, hard-capped
    at `max_selected` total repositories (Part 9) -- if the union would
    exceed it, the LOWEST-relevance job-aware additions are dropped
    first (generic top-N is never truncated to make room).
    """
    generic_results = rank_repositories(summaries, top_n=top_n, weights=weights, reference_time=reference_time)
    generic_names = tuple(result.name for result in generic_results)

    if not job_relevance_terms:
        return RepositorySelection(names=generic_names, generic_names=generic_names)

    registry = registry or default_registry()
    relevant_results = select_job_relevant_repositories(
        summaries, job_relevance_terms, top_k=relevance_top_k, registry=registry
    )

    generic_set = set(generic_names)
    budget = max(0, max_selected - len(generic_names))
    additions = tuple(
        result.name for result in relevant_results if result.name not in generic_set
    )[:budget]

    return RepositorySelection(
        names=generic_names + additions,
        generic_names=generic_names,
        job_relevant_additions=additions,
        relevance_results=tuple(relevant_results),
    )
