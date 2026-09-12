"""Milestone 5B: gitscore.github.parser.parse_repo_summary.

parse_repo_summary() extracts repository-ranking fields from the SAME
raw repo-list payload GitHubClient.get_repositories() already returns --
no languages/README fetch involved. These tests only check field
extraction; ranking behavior itself lives in test_repository_ranking.py.
"""
from conftest import raw_repo

from gitscore.github.parser import parse_repo_summary


def test_extracts_all_ranking_fields_from_a_full_payload():
    repo = raw_repo(
        name="my-project",
        description="A real project",
        language="Python",
        fork=True,
        archived=True,
        size=1234,
        stargazers_count=7,
        forks_count=2,
        topics=["cli", "tooling"],
        pushed_at="2025-06-01T00:00:00Z",
    )

    summary = parse_repo_summary(repo)

    assert summary == {
        "name": "my-project",
        "description": "A real project",
        "primary_language": "Python",
        "is_fork": True,
        "archived": True,
        "size_kb": 1234,
        "stars": 7,
        "forks": 2,
        "topics": ["cli", "tooling"],
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
        "pushed_at": "2025-06-01T00:00:00Z",
        "html_url": "https://github.com/user/my-project",
    }


def test_defaults_missing_optional_fields_instead_of_raising():
    # archived/size/topics/pushed_at are always present on GitHub's real
    # payload (verified against the live API), but parse_repo_summary
    # must not crash if a caller hands it a payload missing them.
    repo = raw_repo(name="minimal")
    for key in ("archived", "size", "topics", "pushed_at"):
        repo.pop(key, None)

    summary = parse_repo_summary(repo)

    assert summary["archived"] is False
    assert summary["size_kb"] == 0
    assert summary["topics"] == []
    assert summary["pushed_at"] is None


def test_null_size_and_null_topics_are_normalized_not_left_as_none():
    # GitHub returns size=0 for genuinely empty repos and topics=[] when
    # none are set -- but guard against a null coming through either way.
    repo = raw_repo(name="empty", size=None, topics=None)

    summary = parse_repo_summary(repo)

    assert summary["size_kb"] == 0
    assert summary["topics"] == []
