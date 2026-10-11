"""Milestone 8D.2: gitscore.ranking.job_relevance (job-aware retrieval).

All fixtures are synthetic repository summaries shaped like
gitscore.github.parser.parse_repo_summary's output -- no real network
calls, no GitHub token required, mirroring tests/test_repository_ranking.py.
"""
from datetime import datetime, timezone

import pytest

from gitscore.ranking.job_relevance import (
    DEFAULT_MAX_SELECTED,
    JobRelevanceTerm,
    PREFERRED_WEIGHT,
    REQUIRED_WEIGHT,
    RepositorySelection,
    score_repository_relevance,
    select_job_relevant_repositories,
    select_repositories,
)

NOW = datetime(2026, 9, 11, tzinfo=timezone.utc)


def summary(name="repo", **overrides):
    """A repository summary shaped like parse_repo_summary's output."""
    base = {
        "name": name,
        "description": "A real project with a description",
        "primary_language": "Python",
        "is_fork": False,
        "archived": False,
        "size_kb": 500,
        "stars": 3,
        "forks": 0,
        "topics": [],
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
        "pushed_at": "2026-06-01T00:00:00Z",
        "html_url": f"https://github.com/user/{name}",
    }
    base.update(overrides)
    return base


def term(*concept_ids, weight=REQUIRED_WEIGHT):
    return JobRelevanceTerm(concept_ids=tuple(concept_ids), weight=weight)


# ---------------------------------------------------------------------------
# JobRelevanceTerm validation
# ---------------------------------------------------------------------------


def test_term_rejects_empty_concept_ids():
    with pytest.raises(ValueError):
        JobRelevanceTerm(concept_ids=(), weight=1.0)


def test_term_rejects_duplicate_concept_ids():
    with pytest.raises(ValueError):
        JobRelevanceTerm(concept_ids=("language.python", "language.python"), weight=1.0)


def test_term_rejects_non_positive_weight():
    with pytest.raises(ValueError):
        JobRelevanceTerm(concept_ids=("language.python",), weight=0.0)


# ---------------------------------------------------------------------------
# Language-field relevance
# ---------------------------------------------------------------------------


def test_exact_language_match():
    result = score_repository_relevance(
        summary("repo", primary_language="Python", description=None), (term("language.python"),)
    )
    assert result.relevance_score == REQUIRED_WEIGHT


def test_language_match_is_concept_specific_not_substring():
    # "C++" must never satisfy a bare "language.c" term via the language field.
    result = score_repository_relevance(
        summary("repo", primary_language="C++", description=None), (term("language.c"),)
    )
    assert result.relevance_score == 0.0


def test_jupyter_notebook_language_match():
    result = score_repository_relevance(
        summary("repo", primary_language="Jupyter Notebook", description=None),
        (term("language.jupyter_notebook", weight=PREFERRED_WEIGHT),),
    )
    assert result.relevance_score == PREFERRED_WEIGHT


# ---------------------------------------------------------------------------
# Safe-alias text relevance: name / description / topics
# ---------------------------------------------------------------------------


def test_safe_alias_in_description_matches():
    result = score_repository_relevance(
        summary("repo", primary_language=None, description="A tiny PyTorch-like autograd engine"),
        (term("ml.framework.pytorch"),),
    )
    assert result.relevance_score == REQUIRED_WEIGHT


def test_safe_alias_in_name_matches():
    result = score_repository_relevance(
        summary("my-kubernetes-operator", primary_language=None, description=None),
        (term("infra.kubernetes"),),
    )
    assert result.relevance_score == REQUIRED_WEIGHT


def test_safe_alias_in_topics_matches():
    result = score_repository_relevance(
        summary("repo", primary_language=None, description=None, topics=["docker", "containers"]),
        (term("infra.docker"),),
    )
    assert result.relevance_score == REQUIRED_WEIGHT


def test_no_match_scores_zero():
    result = score_repository_relevance(
        summary("repo", primary_language="Ruby", description="A Rails app"), (term("language.python"),)
    )
    assert result.relevance_score == 0.0
    assert result.matched_terms == ()


# ---------------------------------------------------------------------------
# Required vs. preferred weighting
# ---------------------------------------------------------------------------


def test_required_term_weighs_more_than_preferred():
    repo = summary("repo", primary_language="Python", description=None)
    required = score_repository_relevance(repo, (term("language.python", weight=REQUIRED_WEIGHT),))
    preferred = score_repository_relevance(repo, (term("language.python", weight=PREFERRED_WEIGHT),))
    assert required.relevance_score > preferred.relevance_score


# ---------------------------------------------------------------------------
# Alternative-group (ANY-side) relevance
# ---------------------------------------------------------------------------


def test_alternative_group_matches_on_either_side():
    repo = summary("repo", primary_language="Go", description=None)
    result = score_repository_relevance(repo, (term("language.python", "language.go"),))
    assert result.relevance_score == REQUIRED_WEIGHT


def test_alternative_group_matches_at_most_once():
    # A repo matching BOTH sides of an alternative group still only earns
    # the term's weight once (presence signal, not a tally -- Part 8).
    result = score_repository_relevance(
        summary("repo", primary_language="Python", description="Built with Go tooling too"),
        (term("language.python", "unresolved:go-tooling"),),
    )
    assert result.relevance_score == REQUIRED_WEIGHT


# ---------------------------------------------------------------------------
# Unresolved-concept safe matching
# ---------------------------------------------------------------------------


def test_unresolved_concept_matches_exact_boundary_safe_term():
    result = score_repository_relevance(
        summary("repo", primary_language=None, description="A Flutter app for iOS and Android"),
        (term("unresolved:flutter"),),
    )
    assert result.relevance_score == REQUIRED_WEIGHT


def test_unresolved_concept_does_not_substring_match():
    result = score_repository_relevance(
        summary("repo", primary_language=None, description="A flutterby butterfly garden tracker"),
        (term("unresolved:flutter"),),
    )
    assert result.relevance_score == 0.0


# ---------------------------------------------------------------------------
# C / Go collision safety (bare short-alias readme-unsafe exclusion)
# ---------------------------------------------------------------------------


def test_bare_c_does_not_match_via_text():
    result = score_repository_relevance(
        summary("repo", primary_language=None, description="A great C book review club"),
        (term("language.c"),),
    )
    assert result.relevance_score == 0.0


def test_bare_c_still_matches_via_language_field():
    # The structured primary_language field is a different, safe source
    # (mirrors language-stats evidence) -- bare "c" is retrievable there.
    result = score_repository_relevance(
        summary("repo", primary_language="C", description=None), (term("language.c"),)
    )
    assert result.relevance_score == REQUIRED_WEIGHT


def test_go_does_not_match_inside_google():
    result = score_repository_relevance(
        summary("repo", primary_language=None, description="Tools for Google Cloud users"),
        (term("language.go"),),
    )
    assert result.relevance_score == 0.0


# ---------------------------------------------------------------------------
# React vs. React Native specificity
# ---------------------------------------------------------------------------


def test_react_native_does_not_misattribute_as_react():
    result = score_repository_relevance(
        summary("repo", primary_language=None, description="Built with React Native"),
        (term("framework.react"),),
    )
    assert result.relevance_score == 0.0


def test_react_native_matches_its_own_concept():
    result = score_repository_relevance(
        summary("repo", primary_language=None, description="Built with React Native"),
        (term("framework.react_native"),),
    )
    assert result.relevance_score == REQUIRED_WEIGHT


def test_plain_react_still_matches_without_native():
    result = score_repository_relevance(
        summary("repo", primary_language=None, description="A React component library"),
        (term("framework.react"),),
    )
    assert result.relevance_score == REQUIRED_WEIGHT


# ---------------------------------------------------------------------------
# select_job_relevant_repositories: top-K, zero-exclusion, determinism
# ---------------------------------------------------------------------------


def test_zero_relevance_repo_excluded_from_top_k():
    summaries = [
        summary("relevant", primary_language="Python"),
        summary("irrelevant", primary_language="Ruby"),
    ]
    results = select_job_relevant_repositories(summaries, (term("language.python"),), top_k=10)
    names = [r.name for r in results]
    assert "relevant" in names
    assert "irrelevant" not in names


def test_deterministic_tie_break_by_name():
    summaries = [
        summary("zebra", primary_language="Python"),
        summary("alpha", primary_language="Python"),
    ]
    results = select_job_relevant_repositories(summaries, (term("language.python"),), top_k=10)
    assert [r.name for r in results] == ["alpha", "zebra"]


def test_top_k_bounds_relevant_selection():
    summaries = [summary(f"repo-{i:02d}", primary_language="Python") for i in range(5)]
    results = select_job_relevant_repositories(summaries, (term("language.python"),), top_k=3)
    assert len(results) == 3


# ---------------------------------------------------------------------------
# select_repositories: deterministic union, ordering, budget
# ---------------------------------------------------------------------------


def _trivial(name, **overrides):
    """Every Stage-1 component scores 0 -- ties broken by name ascending,
    exactly like tests/test_pipeline_evidence.py's helper of the same
    purpose, so generic-ranking order is fully predictable.
    """
    base = dict(primary_language=None, description=None, stars=0, size_kb=0)
    base.update(overrides)
    return summary(name, **base)


def test_no_job_terms_is_pure_generic_ranking():
    summaries = [_trivial(f"repo-{i:02d}") for i in range(20)]
    selection = select_repositories(summaries, top_n=15, reference_time=NOW)
    assert selection.job_relevant_additions == ()
    assert len(selection.names) == 15
    assert selection.names == selection.generic_names


def test_job_relevant_repo_outside_generic_top_n_is_added():
    # topics are not read by ANY Stage-1 component (rank.py's score_repository
    # only looks at size/recency/language-presence/description-presence/
    # stars) -- so a topics-only signal keeps this repo's Stage-1 score
    # tied with the other all-zero trivial repos (and therefore outside
    # the top-15 by the name-ascending tie-break), while still being
    # job-relevant via the text scan.
    generic = [_trivial(f"repo-{i:02d}") for i in range(15)]
    relevant_but_excluded = _trivial("zzz-hidden-gem", topics=["pytorch"])
    summaries = generic + [relevant_but_excluded]

    selection = select_repositories(
        summaries, top_n=15, job_relevance_terms=(term("ml.framework.pytorch"),), reference_time=NOW
    )
    assert "zzz-hidden-gem" not in selection.generic_names
    assert "zzz-hidden-gem" in selection.names
    assert "zzz-hidden-gem" in selection.job_relevant_additions


def test_generic_top_n_order_is_preserved_not_reordered():
    generic = [_trivial(f"repo-{i:02d}") for i in range(15)]
    addition = _trivial("zzz-addition", topics=["pytorch"])
    summaries = generic + [addition]

    selection = select_repositories(
        summaries, top_n=15, job_relevance_terms=(term("ml.framework.pytorch"),), reference_time=NOW
    )
    assert selection.names[:15] == selection.generic_names
    assert selection.names[15:] == ("zzz-addition",)


def test_duplicate_repo_appears_only_once():
    # "repo-00" is already in the generic top-15 AND also job-relevant --
    # it must not be double-counted/duplicated in the final selection.
    summaries = [_trivial(f"repo-{i:02d}", primary_language="Python" if i == 0 else None) for i in range(15)]
    selection = select_repositories(
        summaries, top_n=15, job_relevance_terms=(term("language.python"),), reference_time=NOW
    )
    assert selection.names.count("repo-00") == 1
    assert selection.job_relevant_additions == ()


def test_hard_maximum_selection_budget():
    generic = [_trivial(f"repo-{i:02d}") for i in range(15)]
    # 20 more relevant repos on offer -- far more than relevance_top_k or
    # the remaining budget could ever admit. topics-only so Stage-1
    # scoring (which never reads topics) keeps them out of the generic
    # top-15 on their own merits -- this exercises job-relevance
    # retrieval specifically, not an accidental generic-ranking reorder.
    relevant = [_trivial(f"zzz-relevant-{i:02d}", topics=["pytorch"]) for i in range(20)]
    summaries = generic + relevant

    selection = select_repositories(
        summaries,
        top_n=15,
        job_relevance_terms=(term("ml.framework.pytorch"),),
        relevance_top_k=10,
        max_selected=20,
        reference_time=NOW,
    )
    assert len(selection.names) <= 20
    assert len(selection.names) == len(set(selection.names))
    assert len(selection.job_relevant_additions) == 5  # budget: 20 max - 15 generic = 5 remaining slots


def test_default_max_selected_equals_top_n_plus_relevance_top_k():
    # Documents the exact Part-9 budget arithmetic the module's own
    # docstring asserts: 15 (DEFAULT_TOP_N) + 10 (DEFAULT_RELEVANCE_TOP_K).
    assert DEFAULT_MAX_SELECTED == 25


def test_selection_is_deterministic_across_repeated_calls():
    generic = [_trivial(f"repo-{i:02d}") for i in range(15)]
    relevant = [_trivial(f"zzz-relevant-{i:02d}", topics=["pytorch"]) for i in range(5)]
    summaries = generic + relevant

    terms = (term("ml.framework.pytorch"),)
    first = select_repositories(summaries, top_n=15, job_relevance_terms=terms, reference_time=NOW)
    second = select_repositories(summaries, top_n=15, job_relevance_terms=terms, reference_time=NOW)
    assert first.names == second.names


def test_empty_job_relevance_terms_behaves_like_none():
    summaries = [_trivial(f"repo-{i:02d}") for i in range(20)]
    with_empty = select_repositories(summaries, top_n=15, job_relevance_terms=(), reference_time=NOW)
    with_none = select_repositories(summaries, top_n=15, job_relevance_terms=None, reference_time=NOW)
    assert with_empty.names == with_none.names
    assert isinstance(with_empty, RepositorySelection)
