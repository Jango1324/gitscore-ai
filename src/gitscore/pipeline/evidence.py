"""Milestone 5D -- the V2 evidence-extraction pipeline entry point.

    GitHub username
        -> GitHubClient.get_repositories()            listing (paginated)
        -> parse_repo_summary()                        per-repo, zero extra calls (5B)
        -> rank_repositories()                          job-independent ranking (5B)
        -> top N selected repositories
        -> bounded deep extraction per selected repo:
             languages, README, root-file discovery,
             requirements.txt / pyproject.toml / package.json, Docker
        -> Evidence[]                                   (5C)
        -> CandidateEvidenceProfile                      (5C)

This is a NEW, separate path -- `pipeline.analyze.analyze_user()` (V1) is
completely untouched: still fetches languages/README for EVERY
repository, still produces the historical readiness score, still writes
to Dataset V1. Nothing in this module is imported by `analyze.py` or any
V1 script, and this module imports nothing from `features/*` or
`scoring/readiness.py`. See `docs/ARCHITECTURE.md`'s Milestone 5D section
for the full design rationale and API-cost model.

Deep-analysis cost is bounded by `top_n`, not by the candidate's total
repository count (Milestone 5D Part 3) -- exactly one root-listing
request per selected repository decides which manifest/Docker files
exist, instead of guessing at every candidate filename individually.
"""
from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from datetime import datetime

from gitscore.evidence.extraction import docker as docker_extractor
from gitscore.evidence.extraction import js_deps, python_deps
from gitscore.evidence.extraction import languages as languages_extractor
from gitscore.evidence.extraction import readme as readme_extractor
from gitscore.evidence.extraction.dependency_evidence import declarations_to_evidence
from gitscore.evidence.extraction.files import discover_supported_root_files
from gitscore.evidence.models import Evidence, RepositoryIdentity
from gitscore.evidence.profile import CandidateEvidenceProfile, build_candidate_evidence_profile
from gitscore.github.client import GitHubClient
from gitscore.github.exceptions import GitHubError, GitHubRateLimitError
from gitscore.github.parser import parse_repo_summary
from gitscore.ranking.config import DEFAULT_TOP_N
from gitscore.ranking.rank import rank_repositories

# One (filename, parser, extractor_version, exceptions-that-mean-"malformed")
# entry per supported manifest. Adding a manifest format is one new tuple
# here -- no change to the orchestration loop itself.
_MANIFEST_SPECS = (
    ("requirements.txt", python_deps.parse_requirements_txt, python_deps.EXTRACTOR_VERSION_REQUIREMENTS, ()),
    ("pyproject.toml", python_deps.parse_pyproject_toml, python_deps.EXTRACTOR_VERSION_PYPROJECT, (tomllib.TOMLDecodeError,)),
    ("package.json", js_deps.parse_package_json, js_deps.EXTRACTOR_VERSION, (json.JSONDecodeError,)),
)


@dataclass(frozen=True)
class ExtractionFailure:
    """One source that could NOT be inspected for one repository.

    Distinct from an expected absence (no README, no requirements.txt --
    those simply produce no Evidence and are not recorded here at all).
    This is Milestone 5D Part 14's "could not inspect" case: a timeout, a
    non-404 HTTP error, or a manifest that could not be parsed.
    """

    repository: RepositoryIdentity
    source: str
    error: str


@dataclass(frozen=True)
class EvidenceExtractionResult:
    """Everything `extract_candidate_evidence()` produces for one candidate.

    `profile` is the job-independent `CandidateEvidenceProfile` (5C).
    `extractor_failures` and `unknown_dependency_names` are pipeline-level
    diagnostics for reporting/validation (Milestone 5D Part 17-19) -- they
    are deliberately NOT part of `CandidateEvidenceProfile` itself, so
    that domain object's schema does not grow for a concern (run
    diagnostics) that isn't about the candidate's technical evidence.
    `RepositoryAnalysisCoverage.partially_analyzed` (on `profile.coverage`)
    is the queryable, per-repository summary of the same failures.
    """

    profile: CandidateEvidenceProfile
    extractor_failures: tuple[ExtractionFailure, ...] = ()
    unknown_dependency_names: tuple[str, ...] = ()


def _process_manifest(client, owner, repo_name, discovered_files, filename, parse_fn, malformed_exceptions, extractor_version):
    """Fetch + parse one manifest file if `discover_supported_root_files()`
    found it present. Returns `(evidence, unknown_names, failure_or_None)`.

    Absence (`filename` not in `discovered_files`) is not a failure --
    the caller simply gets back three empty/None results, same as if
    this function had never been called.
    """
    path = discovered_files.get(filename)
    if path is None:
        return [], [], None

    try:
        text = client.get_repository_file(owner, repo_name, path)
    except GitHubRateLimitError:
        raise
    except GitHubError as exc:
        return [], [], ExtractionFailure(RepositoryIdentity(owner, repo_name), filename, str(exc))

    try:
        declarations = parse_fn(text)
    except malformed_exceptions as exc:
        return [], [], ExtractionFailure(RepositoryIdentity(owner, repo_name), filename, str(exc))

    evidence, unknown = declarations_to_evidence(
        owner, repo_name, declarations, file_path=path, extractor_version=extractor_version
    )
    return evidence, unknown, None


def _analyze_repository(client, owner, repo_name):
    """Run every Milestone 5D extractor against one selected repository.

    Every network call is isolated with its own try/except -- one failing
    source (a language-stats timeout, an unreadable README) degrades only
    that source, never aborts analysis of the rest of this repository or
    any other selected repository. A `GitHubRateLimitError` is the one
    exception NOT caught here: it means every subsequent request is about
    to fail the same way, so it propagates out and aborts the whole run
    (mirroring `pipeline/analyze.py`'s existing V1 policy).

    Returns `(evidence, failures, unknown_dependency_names)` for this one
    repository.
    """
    evidence: list[Evidence] = []
    failures: list[ExtractionFailure] = []
    unknown_names: list[str] = []

    try:
        raw_languages = client.get_repository_languages(owner, repo_name)
    except GitHubRateLimitError:
        raise
    except GitHubError as exc:
        failures.append(ExtractionFailure(RepositoryIdentity(owner, repo_name), "languages", str(exc)))
    else:
        evidence.extend(languages_extractor.evidence_from_languages(owner, repo_name, raw_languages))

    try:
        readme_result = client.get_repository_readme_with_path(owner, repo_name)
    except GitHubRateLimitError:
        raise
    except GitHubError as exc:
        # A missing README (404) never reaches this except clause --
        # get_repository_readme_with_path() already translates that into
        # a plain `None` return (expected absence, not a failure).
        failures.append(ExtractionFailure(RepositoryIdentity(owner, repo_name), "readme", str(exc)))
    else:
        if readme_result is not None:
            text, path = readme_result
            evidence.extend(readme_extractor.evidence_from_readme(owner, repo_name, text, path))

    try:
        root_entries = client.get_repository_root_contents(owner, repo_name)
    except GitHubRateLimitError:
        raise
    except GitHubError as exc:
        # Root-listing failed: manifest/Docker detection for this
        # repository can't proceed (there's nothing to discover files
        # from), but languages/README above are unaffected.
        failures.append(ExtractionFailure(RepositoryIdentity(owner, repo_name), "root_contents", str(exc)))
        discovered_files = {}
    else:
        discovered_files = discover_supported_root_files(root_entries)
        evidence.extend(docker_extractor.evidence_from_docker_files(owner, repo_name, discovered_files))

    for filename, parse_fn, extractor_version, malformed_exceptions in _MANIFEST_SPECS:
        manifest_evidence, manifest_unknown, failure = _process_manifest(
            client, owner, repo_name, discovered_files, filename, parse_fn, malformed_exceptions, extractor_version
        )
        evidence.extend(manifest_evidence)
        unknown_names.extend(manifest_unknown)
        if failure is not None:
            failures.append(failure)

    return evidence, failures, unknown_names


def extract_candidate_evidence(
    username: str,
    client: GitHubClient | None = None,
    top_n: int = DEFAULT_TOP_N,
    collected_at: datetime | None = None,
) -> EvidenceExtractionResult:
    """Run the full V2 evidence pipeline for one GitHub username.

    Deep extraction only runs on the `top_n` repositories `rank_repositories()`
    selects (all of them, if the candidate has `top_n` or fewer) -- a
    repository ranked outside that selection is `discovered` but not
    `analyzed`. That is a truthful, expected outcome of the ranking budget,
    never manually overridden here (Milestone 5D Part 15).

    A `GitHubRateLimitError` raised at any point aborts the whole run and
    propagates to the caller -- nothing is silently partial-returned past
    that point, matching V1's existing batch-abort policy.
    """
    client = client or GitHubClient()

    repos_raw = client.get_repositories(username)
    discovered = tuple(RepositoryIdentity(owner=username, name=repo["name"]) for repo in repos_raw)

    summaries = [parse_repo_summary(repo) for repo in repos_raw]
    ranked = rank_repositories(summaries, top_n=top_n)
    selected_names = [result.name for result in ranked]

    all_evidence: list[Evidence] = []
    all_failures: list[ExtractionFailure] = []
    unknown_dependency_names: set[str] = set()
    analyzed: list[RepositoryIdentity] = []
    partially_analyzed: list[RepositoryIdentity] = []

    for repo_name in selected_names:
        identity = RepositoryIdentity(owner=username, name=repo_name)
        analyzed.append(identity)

        evidence, failures, unknown_names = _analyze_repository(client, username, repo_name)
        all_evidence.extend(evidence)
        unknown_dependency_names.update(unknown_names)
        if failures:
            all_failures.extend(failures)
            partially_analyzed.append(identity)

    profile = build_candidate_evidence_profile(
        candidate=username,
        discovered=discovered,
        analyzed=tuple(analyzed),
        evidence_items=all_evidence,
        partially_analyzed=tuple(partially_analyzed),
        collected_at=collected_at,
    )

    return EvidenceExtractionResult(
        profile=profile,
        extractor_failures=tuple(all_failures),
        unknown_dependency_names=tuple(sorted(unknown_dependency_names)),
    )
