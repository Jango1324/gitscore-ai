"""Milestone 5B -- repository ranking configuration.

Centralizes every weight/threshold the ranking formula uses so nothing
is a scattered magic number in rank.py, per the Milestone 5B instruction
to keep weights "centralized/configurable rather than scattering magic
numbers."

Bump REPOSITORY_RANKING_VERSION whenever a weight, threshold, or the
formula shape in rank.py changes -- so a future "why was this repo
selected" record (Milestone 5C+) can name exactly which ranking logic
produced it.

This module does NOT touch SCORING_RUBRIC_VERSION or DATASET_VERSION
(gitscore.dataset.schema) -- repository ranking is a separate,
job-independent concern (see docs/design/MILESTONE_5A_JOB_MATCHING_DESIGN.md
Part 11) that decides what to look at next, not a portfolio or job-fit
score.
"""
from __future__ import annotations

from dataclasses import dataclass

REPOSITORY_RANKING_VERSION = 1

# Default number of repositories selected for future deep analysis.
# See docs/CHANGELOG_DEV.md (Milestone 5B) for the N=10 / 15 / 20
# comparison this default is based on.
DEFAULT_TOP_N = 15


@dataclass(frozen=True)
class RankingWeights:
    """All tunable repository-ranking constants in one place.

    The five ``w_*`` fields are the Stage-1 base-score component weights
    and are expected to sum to 1.0 (not enforced -- experiments may break
    that deliberately, but the shipped defaults do).
    """

    # --- Stage 1 base-score component weights (job-independent) ---
    w_size: float = 0.35
    w_recency: float = 0.30
    w_language: float = 0.15
    w_description: float = 0.10
    w_stars: float = 0.10

    # --- size ---
    # Repo size (KB) at which size_score saturates to 1.0. Log-scaled so
    # a 2MB repo and a 20MB repo aren't wildly different -- raw byte
    # count rewards vendored dependencies/binary assets, not "more real
    # work done".
    size_reference_kb: float = 2000.0
    # Repos at or below this size are treated as very likely trivial
    # (near-empty scaffold, single placeholder file) regardless of any
    # other signal, via trivial_multiplier below.
    trivial_size_kb_threshold: float = 8.0
    trivial_multiplier: float = 0.25

    # --- recency ---
    # Exponential half-life on days since the repo's last push
    # (`pushed_at`, not `updated_at` -- the latter also bumps on stars/
    # issues/wiki edits and is a noisier "last real activity" signal).
    # Gentle decay, not a cliff: an older repo still counts, just less --
    # "has evidence of having done something" doesn't expire the way a
    # "current daily practice" claim might (design doc Part 25).
    recency_half_life_days: float = 730.0

    # --- stars (deliberately minor; ranking must not let popularity dominate) ---
    # Log-scaled and saturating early so a single viral repo cannot
    # outrank several modest, substantive, active repositories.
    star_reference: float = 50.0

    # --- fork / archived: multiplicative dampeners, not exclusions ---
    # A fork or archived repo may still hold real evidence; it should
    # rank below equivalent original/active work, not disappear from
    # consideration entirely.
    fork_multiplier: float = 0.35
    archived_multiplier: float = 0.55

    # --- optional Stage-2 job-relevance boost (Milestone 5A Part 3 / this
    # milestone's Part 3) ---
    # Applied only when the caller supplies relevance_terms; ranking
    # without them is completely unaffected (multiplier stays 1.0).
    relevance_boost_weight: float = 0.5
