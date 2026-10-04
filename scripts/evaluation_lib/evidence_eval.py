"""Milestone 8C -- Layer B: candidate evidence evaluation.

Distinguishes REPOSITORY RETRIEVAL/RANKING failure (a relevant repo
never got deeply analyzed at all) from EXTRACTION failure (a repo WAS
analyzed, but expected evidence inside it is missing) -- Milestone 8C's
own Part 7 instruction. Runs the REAL
`gitscore.pipeline.evidence.extract_candidate_evidence()` against an
offline fixture rebuilt from one real, previously-collected GitHub
account snapshot (`evaluation/fixtures/candidates/<name>.json`),
compared against hand-authored gold (`evaluation/gold/candidates/<name>.json`).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from gitscore.pipeline.evidence import extract_candidate_evidence

from evaluation_lib import taxonomy as tax
from evaluation_lib.loaders import build_fake_client


_SOURCE_TO_TAXONOMY = {
    "language_stats": tax.EVIDENCE_LANGUAGE_MISS,
    "readme": tax.EVIDENCE_README_MISS,
    "dependency": tax.EVIDENCE_DEPENDENCY_MISS,
    "manifest": tax.EVIDENCE_MANIFEST_MISS,
    "source_code": tax.EVIDENCE_SOURCE_SCOPE_LIMITATION,
    "ci": tax.EVIDENCE_CI_SCOPE_LIMITATION,
    "test": tax.EVIDENCE_TEST_SCOPE_LIMITATION,
    "notebook": tax.EVIDENCE_NOTEBOOK_SCOPE_LIMITATION,
    "nested_file": tax.EVIDENCE_NESTED_FILE_SCOPE_LIMITATION,
}


@dataclass
class RankingVerdict:
    username: str
    repo: str
    expected: str
    actual: str
    prediction_correct: bool
    is_retrieval_miss: bool
    notes: str


@dataclass
class ConceptVerdict:
    username: str
    repo: str
    concept_id: str
    found: bool
    tag: str
    classification: str  # BUG | KNOWN_SCOPE_LIMITATION | "" (when found)
    notes: str


@dataclass
class FalsePositiveVerdict:
    username: str
    repo: str
    concept_id: str
    notes: str


@dataclass
class CandidateResult:
    username: str
    discovered_count: int
    analyzed_count: int
    is_complete: bool
    ranking_verdicts: list[RankingVerdict] = field(default_factory=list)
    concept_verdicts: list[ConceptVerdict] = field(default_factory=list)
    false_positives: list[FalsePositiveVerdict] = field(default_factory=list)
    extractor_failure_count: int = 0


def evaluate_candidate(fixture: dict, gold: dict) -> CandidateResult:
    username = fixture["username"]
    client = build_fake_client(fixture)
    result = extract_candidate_evidence(username, client=client, top_n=fixture["top_n"])
    profile = result.profile
    analyzed_names = {identity.name for identity in profile.coverage.analyzed}

    candidate_result = CandidateResult(
        username=username,
        discovered_count=profile.coverage.discovered_count,
        analyzed_count=profile.coverage.analyzed_count,
        is_complete=profile.coverage.is_complete,
        extractor_failure_count=len(result.extractor_failures),
    )

    for target in gold["targets"]:
        repo = target["repo"]
        actual_state = "analyzed" if repo in analyzed_names else "not_analyzed"
        expected_state = target["ranking_expectation"]
        # Is this a real product-level retrieval miss -- a genuinely
        # relevant repository that the ranker excluded -- as opposed to
        # a deliberately-correct deprioritization (e.g. a huge-star
        # curated list with no real engineering substance)? Driven by
        # the gold author's OWN independent relevance judgment
        # (`retrieval_miss_relevant`), never derived from the ranking
        # score itself.
        is_retrieval_miss = actual_state == "not_analyzed" and target.get("retrieval_miss_relevant", False)
        candidate_result.ranking_verdicts.append(
            RankingVerdict(
                username=username, repo=repo, expected=expected_state, actual=actual_state,
                prediction_correct=(expected_state == actual_state), is_retrieval_miss=is_retrieval_miss,
                notes=target.get("notes", ""),
            )
        )

        if actual_state != "analyzed":
            continue  # nothing to check extraction-wise if it was never analyzed

        repo_evidence = [item for item in profile.evidence if item.repository.name == repo]
        actual_concept_ids = {item.concept_id for item in repo_evidence}

        for expected in target.get("expected_concepts", []):
            concept_id = expected["concept_id"]
            found = concept_id in actual_concept_ids
            if found:
                candidate_result.concept_verdicts.append(
                    ConceptVerdict(username, repo, concept_id, True, "", "", "")
                )
                continue
            source = expected.get("source", "other")
            classification = tax.BUG
            notes = ""
            for limitation in target.get("scope_limitations_observed", []):
                if limitation.get("source") == source:
                    classification = limitation.get("classification", tax.BUG)
                    notes = limitation.get("notes", "")
                    break
            tag = _SOURCE_TO_TAXONOMY.get(source, tax.EVIDENCE_OTHER_EXTRACTION_MISS)
            candidate_result.concept_verdicts.append(
                ConceptVerdict(username, repo, concept_id, False, tag, classification, notes)
            )

        for not_expected in target.get("not_expected_concepts", []):
            concept_id = not_expected["concept_id"]
            if concept_id in actual_concept_ids:
                candidate_result.false_positives.append(
                    FalsePositiveVerdict(username, repo, concept_id, not_expected.get("notes", ""))
                )

    return candidate_result


def evaluate_candidates(fixtures_and_gold: list[tuple[dict, dict]]) -> list[CandidateResult]:
    return [evaluate_candidate(fixture, gold) for fixture, gold in fixtures_and_gold]


def aggregate_metrics(results: list[CandidateResult]) -> dict:
    ranking_misses = [v for r in results for v in r.ranking_verdicts if v.is_retrieval_miss]
    ranking_checks = [v for r in results for v in r.ranking_verdicts]
    prediction_errors = [v for v in ranking_checks if not v.prediction_correct]
    concept_found = sum(1 for r in results for v in r.concept_verdicts if v.found)
    concept_missing = [v for r in results for v in r.concept_verdicts if not v.found]
    bugs = [v for v in concept_missing if v.classification == tax.BUG]
    known_limitations = [v for v in concept_missing if v.classification == tax.KNOWN_SCOPE_LIMITATION]
    false_positives = [fp for r in results for fp in r.false_positives]

    return {
        "candidates_evaluated": len(results),
        "ranking_checks": len(ranking_checks),
        "ranking_prediction_errors": len(prediction_errors),
        "repository_ranking_misses": len(ranking_misses),
        "concept_checks": concept_found + len(concept_missing),
        "concept_found": concept_found,
        "concept_missing": len(concept_missing),
        "concept_missing_bugs": len(bugs),
        "concept_missing_known_scope_limitations": len(known_limitations),
        "false_positives": len(false_positives),
        "total_extractor_failures": sum(r.extractor_failure_count for r in results),
    }
