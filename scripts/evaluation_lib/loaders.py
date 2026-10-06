"""Milestone 8C -- loading the version-controlled evaluation corpus.

Everything here reads JSON from `evaluation/` and raises a loud,
specific error on a missing/malformed file -- an evaluation run must
fail fast and obviously, never silently skip a corpus entry.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EVALUATION_DIR = REPO_ROOT / "evaluation"
JOBS_DIR = EVALUATION_DIR / "jobs"
GOLD_JOBS_DIR = EVALUATION_DIR / "gold" / "jobs"
GOLD_CANDIDATES_DIR = EVALUATION_DIR / "gold" / "candidates"
CANDIDATE_FIXTURES_DIR = EVALUATION_DIR / "fixtures" / "candidates"

# Milestone 8D.1: the frozen `8c:v1` gold corpus (above) is never edited
# in place -- see docs/evaluation/MILESTONE_8D1_PARSER_IMPROVEMENTS.md.
# `8c:v1.1` is a SEPARATE, parallel snapshot directory, used only when a
# caller explicitly passes `gold_jobs_dir=GOLD_JOBS_DIR_V1_1` (or the
# matching `--corpus-version v1.1` CLI flag on
# `scripts/evaluate_job_parser.py`) -- every existing call with no
# override keeps reading the original, byte-for-byte-unchanged `8c:v1`
# files, so this addition cannot change `8c:v1`'s own published results.
GOLD_JOBS_DIR_V1_1 = EVALUATION_DIR / "gold_v1_1" / "jobs"
GOLD_CANDIDATES_DIR_V1_1 = EVALUATION_DIR / "gold_v1_1" / "candidates"


class EvaluationFixtureError(Exception):
    """A corpus/fixture/gold file is missing or malformed.

    Distinct from an evaluation FINDING (a measured GitScore gap) --
    this is a harness-level problem with the evaluation inputs
    themselves, the one thing `scripts/evaluate_*.py` should exit
    non-zero for (Milestone 8C Part 18).
    """


def _read_json(path: Path) -> dict:
    if not path.exists():
        raise EvaluationFixtureError(f"missing evaluation file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise EvaluationFixtureError(f"malformed JSON in {path}: {exc}") from exc


def list_job_ids() -> tuple[str, ...]:
    return tuple(sorted(p.stem for p in JOBS_DIR.glob("*.json")))


def load_job(job_id: str) -> dict:
    return _read_json(JOBS_DIR / f"{job_id}.json")


def load_gold_job(job_id: str, gold_jobs_dir: Path = GOLD_JOBS_DIR) -> dict:
    path = gold_jobs_dir / f"{job_id}.json"
    gold = _read_json(path)
    if gold.get("job_id") != job_id:
        raise EvaluationFixtureError(
            f"{path}: job_id mismatch: expected {job_id!r}, got {gold.get('job_id')!r}"
        )
    if "expected_requirements" not in gold:
        raise EvaluationFixtureError(f"{path}: missing 'expected_requirements'")
    return gold


def load_job_and_gold(job_id: str, gold_jobs_dir: Path = GOLD_JOBS_DIR) -> tuple[dict, dict]:
    return load_job(job_id), load_gold_job(job_id, gold_jobs_dir=gold_jobs_dir)


def list_candidate_names() -> tuple[str, ...]:
    return tuple(sorted(p.stem for p in CANDIDATE_FIXTURES_DIR.glob("*.json")))


def load_candidate_fixture(name: str) -> dict:
    return _read_json(CANDIDATE_FIXTURES_DIR / f"{name}.json")


def load_gold_candidate(name: str, gold_candidates_dir: Path = GOLD_CANDIDATES_DIR) -> dict:
    return _read_json(gold_candidates_dir / f"{name}.json")


@dataclass(frozen=True)
class FakeCandidateGitHubClient:
    """Minimal offline stand-in for `GitHubClient`, built from a
    persisted fixture (`evaluation/fixtures/candidates/<name>.json`).

    Shaped identically to `tests/conftest.py::FakeEvidenceGitHubClient`
    (same method surface `extract_candidate_evidence()` needs), but
    defined here rather than imported from `tests/` -- evaluation
    tooling should not depend on test-only code, and this one is driven
    by a real persisted fixture dict instead of inline kwargs.
    """

    repos: list
    selected: dict

    def get_repositories(self, username):
        return self.repos

    def get_repository_languages(self, owner, repo):
        return self.selected.get(repo, {}).get("languages", {})

    def get_repository_readme_with_path(self, owner, repo):
        readme = self.selected.get(repo, {}).get("readme")
        return tuple(readme) if readme else None

    def get_repository_root_contents(self, owner, repo):
        return self.selected.get(repo, {}).get("root_contents", [])

    def get_repository_file(self, owner, repo, path):
        files = self.selected.get(repo, {}).get("files", {})
        # Fixtures key `files` by filename (as discover_supported_root_files
        # would resolve it for a root-level file); `path` here is that
        # same root-level filename for every file this milestone's bounded
        # extractors ever request.
        filename = path.rsplit("/", 1)[-1]
        return files.get(filename)


def build_fake_client(fixture: dict) -> FakeCandidateGitHubClient:
    return FakeCandidateGitHubClient(repos=fixture["repos_raw"], selected=fixture["selected"])
