"""Milestone 5D -- Docker/containerization structural evidence.

Presence-only: a `Dockerfile` or compose file at the repository root is
strong evidence that Docker/containerization is USED here, and nothing
more -- no Dockerfile content is inspected, no sophistication judged
(multi-stage builds, base image choice, etc. are all out of scope). See
`docs/ARCHITECTURE.md`'s confidence-vs-proficiency statement: STRONG
confidence in "Docker is used" is not a claim about advanced Docker
skill.
"""
from __future__ import annotations

from gitscore.evidence.extraction.files import DOCKER_FILENAMES
from gitscore.evidence.models import Evidence, RepositoryIdentity
from gitscore.evidence.types import ConfidenceLevel, EvidenceType

EXTRACTOR_VERSION = "docker:v1"

DOCKER_CONCEPT_ID = "infra.docker"


def evidence_from_docker_files(owner: str, repo_name: str, discovered_files: dict) -> list[Evidence]:
    """`discovered_files` is `files.discover_supported_root_files()`'s
    `{filename: path}` result. One Evidence item per PRESENT Docker-related
    root file -- a repository with both a `Dockerfile` and a
    `docker-compose.yml` gets two separate observations (different
    `file_path`, so they are not exact duplicates and both survive the
    existing Evidence dedup policy), not one merged "has Docker" fact.
    """
    evidence = []
    for filename in DOCKER_FILENAMES:
        if filename not in discovered_files:
            continue
        evidence.append(
            Evidence(
                repository=RepositoryIdentity(owner=owner, name=repo_name),
                evidence_type=EvidenceType.DOCKER,
                raw_observation=f"root file present: {filename}",
                concept_id=DOCKER_CONCEPT_ID,
                confidence=ConfidenceLevel.STRONG,
                extractor_version=EXTRACTOR_VERSION,
                file_path=discovered_files[filename],
            )
        )
    return evidence
