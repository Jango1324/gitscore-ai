"""Milestone 5D -- gitscore.evidence.extraction.files (root discovery) and
gitscore.evidence.extraction.docker (Docker structural evidence).
"""
from conftest import root_entry

from gitscore.evidence.extraction.docker import DOCKER_CONCEPT_ID, evidence_from_docker_files
from gitscore.evidence.extraction.files import discover_supported_root_files
from gitscore.evidence.types import ConfidenceLevel, EvidenceType


def test_root_discovery_finds_supported_files_only():
    entries = [
        root_entry("Dockerfile"),
        root_entry("README.md"),
        root_entry("src", entry_type="dir"),
        root_entry("requirements.txt"),
    ]
    found = discover_supported_root_files(entries)
    assert found == {"Dockerfile": "Dockerfile", "requirements.txt": "requirements.txt"}


def test_root_discovery_ignores_directories_even_with_a_matching_name():
    entries = [root_entry("Dockerfile", entry_type="dir")]
    assert discover_supported_root_files(entries) == {}


def test_root_discovery_is_case_sensitive():
    entries = [root_entry("dockerfile")]
    assert discover_supported_root_files(entries) == {}


def test_root_discovery_on_empty_listing():
    assert discover_supported_root_files([]) == {}


def test_dockerfile_produces_strong_docker_evidence():
    discovered = {"Dockerfile": "Dockerfile"}
    evidence = evidence_from_docker_files("octocat", "repo", discovered)

    assert len(evidence) == 1
    item = evidence[0]
    assert item.concept_id == DOCKER_CONCEPT_ID
    assert item.confidence == ConfidenceLevel.STRONG
    assert item.evidence_type == EvidenceType.DOCKER
    assert item.file_path == "Dockerfile"


def test_compose_file_produces_docker_evidence():
    discovered = {"docker-compose.yml": "docker-compose.yml"}
    evidence = evidence_from_docker_files("octocat", "repo", discovered)
    assert evidence[0].concept_id == DOCKER_CONCEPT_ID


def test_multiple_docker_files_produce_separate_evidence_items():
    discovered = {"Dockerfile": "Dockerfile", "docker-compose.yml": "docker-compose.yml"}
    evidence = evidence_from_docker_files("octocat", "repo", discovered)

    assert len(evidence) == 2
    assert {item.file_path for item in evidence} == {"Dockerfile", "docker-compose.yml"}


def test_no_docker_files_produces_no_evidence():
    assert evidence_from_docker_files("octocat", "repo", {"requirements.txt": "requirements.txt"}) == []


def test_identical_docker_evidence_from_two_calls_deduplicates_via_set():
    discovered = {"Dockerfile": "Dockerfile"}
    first = evidence_from_docker_files("octocat", "repo", discovered)
    second = evidence_from_docker_files("octocat", "repo", discovered)

    assert len(set(first + second)) == 1
