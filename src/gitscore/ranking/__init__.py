"""Milestone 5B -- deterministic, job-independent repository ranking.

See docs/design/MILESTONE_5A_JOB_MATCHING_DESIGN.md Part 11 for the
architectural context this implements (Stage 1 of the two-stage
repository-ranking strategy) and docs/CHANGELOG_DEV.md for the Milestone
5B entry.

Scope note: this package decides WHICH repositories are worth a deep
fetch later. It does not fetch languages/READMEs, does not extract
evidence, does not persist anything, and does not compute a candidate or
job-fit score of any kind.
"""
from gitscore.ranking.config import DEFAULT_TOP_N, REPOSITORY_RANKING_VERSION, RankingWeights
from gitscore.ranking.job_relevance import (
    DEFAULT_MAX_SELECTED,
    DEFAULT_RELEVANCE_TOP_K,
    JOB_RELEVANCE_VERSION,
    JobRelevanceTerm,
    RepositoryRelevanceResult,
    RepositorySelection,
    score_repository_relevance,
    select_job_relevant_repositories,
    select_repositories,
)
from gitscore.ranking.rank import RepositoryRankingResult, rank_repositories, score_repository

__all__ = [
    "DEFAULT_MAX_SELECTED",
    "DEFAULT_RELEVANCE_TOP_K",
    "DEFAULT_TOP_N",
    "JOB_RELEVANCE_VERSION",
    "JobRelevanceTerm",
    "REPOSITORY_RANKING_VERSION",
    "RankingWeights",
    "RepositoryRankingResult",
    "RepositoryRelevanceResult",
    "RepositorySelection",
    "rank_repositories",
    "score_repository",
    "score_repository_relevance",
    "select_job_relevant_repositories",
    "select_repositories",
]
