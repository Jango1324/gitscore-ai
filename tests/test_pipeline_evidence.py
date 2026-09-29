"""Milestone 5D -- gitscore.pipeline.evidence.extract_candidate_evidence.

End-to-end orchestration tests: repository selection bounded by ranking,
discovered-vs-analyzed/partially-analyzed bookkeeping, per-source failure
isolation, and provenance on the resulting Evidence. All via
`FakeEvidenceGitHubClient` -- no network access, no GitHub token.
"""
import json

from conftest import FakeEvidenceGitHubClient, raw_repo, root_entry

from gitscore.github.exceptions import GitHubRateLimitError, GitHubRequestError
from gitscore.pipeline.evidence import extract_candidate_evidence


def _trivial_repo(name):
    """A repo shaped so every Stage-1 ranking component scores 0 -- every
    such repo ties, and rank_repositories()'s deterministic tie-break
    (name ascending) becomes the whole ordering. Makes repository
    SELECTION trivially predictable across a whole test suite without
    depending on the ranking formula's internals.
    """
    return raw_repo(name=name, description=None, language=None, stargazers_count=0)


# ---------------------------------------------------------------------------
# Repository selection
# ---------------------------------------------------------------------------


def test_fewer_than_top_n_repositories_are_all_analyzed():
    repos = [_trivial_repo(f"repo-{i}") for i in range(5)]
    client = FakeEvidenceGitHubClient(repos=repos)

    result = extract_candidate_evidence("octocat", client=client, top_n=15)

    assert result.profile.coverage.discovered_count == 5
    assert result.profile.coverage.analyzed_count == 5
    assert result.profile.coverage.is_complete


def test_exactly_top_n_repositories_are_all_analyzed():
    repos = [_trivial_repo(f"repo-{i}") for i in range(15)]
    client = FakeEvidenceGitHubClient(repos=repos)

    result = extract_candidate_evidence("octocat", client=client, top_n=15)

    assert result.profile.coverage.discovered_count == 15
    assert result.profile.coverage.analyzed_count == 15
    assert result.profile.coverage.is_complete


def test_more_than_top_n_repositories_only_top_n_are_analyzed():
    repos = [_trivial_repo(f"repo-{i:02d}") for i in range(20)]
    client = FakeEvidenceGitHubClient(repos=repos)

    result = extract_candidate_evidence("octocat", client=client, top_n=15)

    assert result.profile.coverage.discovered_count == 20
    assert result.profile.coverage.analyzed_count == 15
    assert not result.profile.coverage.is_complete


def test_a_repository_ranked_outside_top_n_is_discovered_but_not_analyzed():
    # Deterministic tie-break is name-ascending, so with 20 trivially-tied
    # repos and top_n=15, "repo-19" is guaranteed to fall outside the
    # selection -- "discovered=yes, analyzed=no" (Milestone 5D Part 15),
    # never manually forced in either direction.
    repos = [_trivial_repo(f"repo-{i:02d}") for i in range(20)]
    client = FakeEvidenceGitHubClient(repos=repos)

    result = extract_candidate_evidence("octocat", client=client, top_n=15)

    analyzed_names = {repo.name for repo in result.profile.coverage.analyzed}
    discovered_names = {repo.name for repo in result.profile.coverage.discovered}
    assert "repo-19" in discovered_names
    assert "repo-19" not in analyzed_names


def test_very_large_repository_list_still_bounds_analysis_to_top_n():
    repos = [_trivial_repo(f"repo-{i:04d}") for i in range(500)]
    client = FakeEvidenceGitHubClient(repos=repos)

    result = extract_candidate_evidence("octocat", client=client, top_n=15)

    assert result.profile.coverage.discovered_count == 500
    assert result.profile.coverage.analyzed_count == 15


def test_only_selected_repositories_receive_deep_fetches():
    repos = [_trivial_repo(f"repo-{i:02d}") for i in range(20)]
    languages = {f"repo-{i:02d}": {"Python": 1000} for i in range(20)}
    client = FakeEvidenceGitHubClient(repos=repos, languages=languages)

    # A repo outside the top-15 selection (e.g. "repo-19") has no readme/
    # root_contents fixture registered at all -- if the pipeline tried to
    # deep-fetch it, FakeEvidenceGitHubClient would return the empty
    # defaults rather than crash, so we instead assert directly on what
    # ended up "analyzed".
    result = extract_candidate_evidence("octocat", client=client, top_n=15)

    analyzed_names = {repo.name for repo in result.profile.coverage.analyzed}
    assert len(analyzed_names) == 15
    assert "repo-19" not in analyzed_names
    # Every piece of language evidence must belong to a selected repo.
    evidenced_repo_names = {item.repository.name for item in result.profile.evidence}
    assert evidenced_repo_names <= analyzed_names


# ---------------------------------------------------------------------------
# End-to-end evidence + provenance
# ---------------------------------------------------------------------------


def test_end_to_end_evidence_across_all_sources_with_provenance():
    repo_name = "showcase"
    repos = [_trivial_repo(repo_name)]
    client = FakeEvidenceGitHubClient(
        repos=repos,
        languages={repo_name: {"Python": 9000, "Shell": 1000}},
        readme={repo_name: ("Built with FastAPI and PostgreSQL.", "README.md")},
        root_contents={
            repo_name: [
                root_entry("requirements.txt"),
                root_entry("package.json"),
                root_entry("Dockerfile"),
            ]
        },
        files={
            (repo_name, "requirements.txt"): "torch==2.5\nsome-made-up-thing==1.0\n",
            (repo_name, "package.json"): json.dumps({"dependencies": {"react": "^18.0.0"}}),
        },
    )

    result = extract_candidate_evidence("octocat", client=client, top_n=15)

    evidence_by_type = {}
    for item in result.profile.evidence:
        evidence_by_type.setdefault(item.evidence_type.value, []).append(item)

    assert "language.python" in {e.concept_id for e in evidence_by_type["repository_language"]}
    assert {e.concept_id for e in evidence_by_type["readme"]} == {"framework.fastapi", "database.postgresql"}
    assert {e.concept_id for e in evidence_by_type["dependency"]} == {"ml.framework.pytorch", "framework.react"}
    assert evidence_by_type["docker"][0].concept_id == "infra.docker"

    for item in result.profile.evidence:
        assert item.repository.owner == "octocat"
        assert item.repository.name == repo_name

    assert result.unknown_dependency_names == ("some-made-up-thing",)
    assert result.extractor_failures == ()
    assert result.profile.coverage.partially_analyzed == ()


# ---------------------------------------------------------------------------
# Failure semantics (Milestone 5D Part 14)
# ---------------------------------------------------------------------------


def test_language_fetch_failure_marks_repo_partially_analyzed_but_continues():
    repo_name = "flaky"
    repos = [_trivial_repo(repo_name)]
    client = FakeEvidenceGitHubClient(
        repos=repos,
        languages_exc_for={repo_name: GitHubRequestError("boom", status_code=500)},
        readme={repo_name: ("Uses PostgreSQL.", "README.md")},
    )

    result = extract_candidate_evidence("octocat", client=client, top_n=15)

    assert len(result.extractor_failures) == 1
    assert result.extractor_failures[0].source == "languages"
    assert result.extractor_failures[0].repository.name == repo_name
    partially = {r.name for r in result.profile.coverage.partially_analyzed}
    assert repo_name in partially
    # The repo is still counted as analyzed -- a partial failure does not
    # demote it back to "not analyzed".
    assert repo_name in {r.name for r in result.profile.coverage.analyzed}
    # README evidence still made it through despite the language failure.
    assert any(item.concept_id == "database.postgresql" for item in result.profile.evidence)


def test_readme_404_is_expected_absence_not_a_failure():
    repo_name = "no-readme"
    repos = [_trivial_repo(repo_name)]
    # FakeEvidenceGitHubClient returns None for a repo with no readme
    # fixture registered at all -- mirrors get_repository_readme_with_path()
    # already translating a 404 into None before the pipeline ever sees it.
    client = FakeEvidenceGitHubClient(repos=repos)

    result = extract_candidate_evidence("octocat", client=client, top_n=15)

    assert result.extractor_failures == ()
    assert result.profile.coverage.partially_analyzed == ()


def test_readme_fetch_failure_is_recorded_as_a_real_failure():
    repo_name = "readme-error"
    repos = [_trivial_repo(repo_name)]
    client = FakeEvidenceGitHubClient(
        repos=repos, readme_exc_for={repo_name: GitHubRequestError("boom", status_code=500)}
    )

    result = extract_candidate_evidence("octocat", client=client, top_n=15)

    assert len(result.extractor_failures) == 1
    assert result.extractor_failures[0].source == "readme"
    assert repo_name in {r.name for r in result.profile.coverage.partially_analyzed}


def test_root_contents_failure_skips_manifest_and_docker_but_not_languages():
    repo_name = "no-root-listing"
    repos = [_trivial_repo(repo_name)]
    client = FakeEvidenceGitHubClient(
        repos=repos,
        languages={repo_name: {"Python": 1000}},
        root_contents_exc_for={repo_name: GitHubRequestError("boom", status_code=500)},
    )

    result = extract_candidate_evidence("octocat", client=client, top_n=15)

    sources = {f.source for f in result.extractor_failures}
    assert "root_contents" in sources
    assert any(item.concept_id == "language.python" for item in result.profile.evidence)
    assert not any(item.evidence_type.value == "docker" for item in result.profile.evidence)


def test_manifest_fetch_failure_is_recorded_and_isolated():
    repo_name = "manifest-fetch-fails"
    repos = [_trivial_repo(repo_name)]
    client = FakeEvidenceGitHubClient(
        repos=repos,
        root_contents={repo_name: [root_entry("requirements.txt")]},
        files_exc_for={(repo_name, "requirements.txt"): GitHubRequestError("boom", status_code=500)},
    )

    result = extract_candidate_evidence("octocat", client=client, top_n=15)

    assert len(result.extractor_failures) == 1
    assert result.extractor_failures[0].source == "requirements.txt"


def test_malformed_package_json_is_recorded_and_does_not_crash_analysis():
    repo_name = "bad-package-json"
    repos = [_trivial_repo(repo_name)]
    client = FakeEvidenceGitHubClient(
        repos=repos,
        root_contents={repo_name: [root_entry("package.json")]},
        files={(repo_name, "package.json"): "{not valid json"},
    )

    result = extract_candidate_evidence("octocat", client=client, top_n=15)

    assert len(result.extractor_failures) == 1
    assert result.extractor_failures[0].source == "package.json"
    assert repo_name in {r.name for r in result.profile.coverage.analyzed}


def test_malformed_pyproject_toml_is_recorded_and_does_not_crash_analysis():
    repo_name = "bad-pyproject"
    repos = [_trivial_repo(repo_name)]
    client = FakeEvidenceGitHubClient(
        repos=repos,
        root_contents={repo_name: [root_entry("pyproject.toml")]},
        files={(repo_name, "pyproject.toml"): "not [valid toml"},
    )

    result = extract_candidate_evidence("octocat", client=client, top_n=15)

    assert len(result.extractor_failures) == 1
    assert result.extractor_failures[0].source == "pyproject.toml"


def test_rate_limit_aborts_the_whole_run():
    repos = [_trivial_repo("repo-a"), _trivial_repo("repo-b")]
    client = FakeEvidenceGitHubClient(
        repos=repos,
        languages_exc_for={"repo-a": GitHubRateLimitError("rate limited")},
    )

    try:
        extract_candidate_evidence("octocat", client=client, top_n=15)
        assert False, "expected GitHubRateLimitError to propagate"
    except GitHubRateLimitError:
        pass
