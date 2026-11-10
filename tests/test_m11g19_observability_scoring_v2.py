"""Milestone 11-G19 -- observability-aware scoring v2 (production).

Written BEFORE the production change, and red against scoring v1. Every
test runs the real parser, matcher, assessor and (where named) the API
serializer; nothing is simulated.

Contract under test (M11-G18 policy B/C, approved for G19): a requirement
enters the alignment numerator and denominator only if the matcher can
evaluate it AND every acceptable alternative has a declared GitHub
evidence-assessment capability. Eligibility is decided from the job
requirement alone, never from candidate evidence. Excluded rows keep
their MatchStatus, matched concepts and evidence.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (REPO_ROOT / "src", REPO_ROOT / "scripts" / "evaluation_lib"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from gitscore.api.serialization import serialize_job_analysis_result  # noqa: E402
from gitscore.application import JobAnalysisResult  # noqa: E402
from gitscore.assessment import SCORING_VERSION, assess_job  # noqa: E402
from gitscore.concepts.registry import is_unresolved_concept_id  # noqa: E402
from gitscore.evidence import (  # noqa: E402
    ConfidenceLevel,
    Evidence,
    EvidenceType,
    RepositoryIdentity,
    build_candidate_evidence_profile,
)
from gitscore.jobs import parse_job_description_with_diagnostics  # noqa: E402
from gitscore.matching import match_job  # noqa: E402

G18 = REPO_ROOT / "evaluation" / "m11g18"
PY, DOCKER, K8S, AWS, PG = "language.python", "infra.docker", "infra.kubernetes", "cloud.aws", "database.postgresql"


def _evidence(concept_ids):
    items = []
    for i, cid in enumerate(concept_ids):
        etype = EvidenceType.REPOSITORY_LANGUAGE if is_unresolved_concept_id(cid) else EvidenceType.DEPENDENCY
        items.append(Evidence(repository=RepositoryIdentity(owner="candidate", name=f"repo{i}"), evidence_type=etype,
                              raw_observation=f"synthetic {cid}", concept_id=cid,
                              confidence=ConfidenceLevel.MODERATE, extractor_version="m11g19@1"))
    return tuple(items)


def run(text: str, evidence=()):
    """(assessment, API response) from the real parser/matcher/assessor/serializer."""
    items = _evidence(evidence)
    repos = sorted({e.repository for e in items}, key=lambda r: r.name) or [RepositoryIdentity("candidate", "repo0")]
    profile = build_candidate_evidence_profile("candidate", discovered=repos, analyzed=repos, evidence_items=items)
    parsed = parse_job_description_with_diagnostics(text)
    assessment = assess_job(match_job(profile, parsed.profile))
    result = JobAnalysisResult(candidate_profile=profile, job_profile=parsed.profile, assessment=assessment,
                               extractor_failures=(), unknown_dependency_names=(),
                               unparsed_claims=parsed.unparsed_claims)
    return assessment, serialize_job_analysis_result(result)


def score(assessment):
    return assessment.alignment_score, assessment.assessable_count


def rows(resp):
    return resp.requirements.supported + resp.requirements.not_observed + resp.requirements.not_assessable


def row_for(resp, member):
    for r in rows(resp):
        if member in ([r.concept_id] if r.concept_id else []) + list(r.alternative_concept_ids):
            return r
    raise AssertionError(member)


# --------------------------------------------------------------------------- 0
def test_scoring_version_is_v2():
    assert SCORING_VERSION == "github_evidence_alignment:v2"


# 1. Assessable standalone requirement still counts --------------------------
def test_assessable_standalone_requirement_counts():
    assert score(run("Requirements:\n- Experience with PostgreSQL", [PG])[0]) == (100, 1)
    assert score(run("Requirements:\n- Experience with PostgreSQL")[0]) == (0, 1)


# 2. Unassessable standalone requirement is excluded --------------------------
def test_unassessable_standalone_requirement_excluded():
    assessment, resp = run("Requirements:\n- Python, Terraform, Docker", [PY, DOCKER])
    assert score(assessment) == (100, 2)                       # v1: 67 (2/3)
    terraform = row_for(resp, "unresolved:terraform")
    assert terraform.status == "not_observed" and terraform.counts_toward_alignment is False
    assert terraform.alignment_exclusion_reason == "unresolved_technology"


# 3. Unresolved technical concepts (hardware interfaces) ----------------------
def test_unresolved_technical_concepts_excluded():
    assessment, _ = run("Requirements:\n- Python, SPI, I2C, UART", [PY])
    assert score(assessment) == (100, 1)                       # v1: 25 (1/4)


# 4. Two fully assessable OR alternatives: unchanged ---------------------------
def test_fully_assessable_or_group_counts_once():
    assert score(run("Requirements:\n- Experience with Docker or Kubernetes", [DOCKER])[0]) == (100, 1)
    assert score(run("Requirements:\n- Experience with Docker or Kubernetes")[0]) == (0, 1)


# 5. Mixed assessable / unresolved OR is excluded -----------------------------
def test_mixed_or_group_excluded():
    assessment, resp = run("Requirements:\n- Experience with AWS or Azure")
    assert score(assessment) == (None, 0)                      # v1: 0 (0/1)
    assert row_for(resp, AWS).alignment_exclusion_reason == "unresolved_alternative"


# 6. Two unresolved OR alternatives -------------------------------------------
def test_all_unresolved_or_group_excluded():
    assessment, resp = run("Requirements:\n- Experience with Azure or GCP")
    assert score(assessment) == (None, 0)
    assert row_for(resp, "unresolved:azure").alignment_exclusion_reason == "unresolved_technology"


# 7 + 18. Positive evidence for one member of a mixed OR: supported but excluded
def test_supported_but_excluded_keeps_status_and_evidence():
    assessment, resp = run("Requirements:\n- Experience with AWS or Azure", [AWS])
    assert score(assessment) == (None, 0)                      # v1: 100 (1/1)
    (row,) = resp.requirements.supported
    assert row.status == "supported" and row.matched_concept_ids == [AWS]
    assert row.evidence and row.evidence[0].concept_id == AWS
    assert row.counts_toward_alignment is False
    assert resp.assessment.excluded_from_alignment_count == 1


# 8 + 19. No positive evidence for a mixed OR: not observed but excluded -------
def test_not_observed_but_excluded_keeps_status():
    _, resp = run("Requirements:\n- Experience with AWS or Azure")
    (row,) = resp.requirements.not_observed
    assert row.status == "not_observed" and row.counts_toward_alignment is False
    assert resp.requirements.not_assessable == []


# 9. Multiple independent requirements ---------------------------------------
def test_multiple_independent_requirements():
    text = "Requirements:\n- Python\n- Docker\n- Experience with AWS or Azure\n- PostgreSQL"
    assert score(run(text, [PY, DOCKER, PG])[0]) == (100, 3)                       # v1: 75 (3/4)
    assert score(run(text, [PY])[0]) == (33, 3)                                     # v1: 25 (1/4)
    assert score(run(text, [PY, DOCKER, AWS, PG])[0]) == (100, 3)                   # v1: 100 (4/4)


# 10. REQUIRED and PREFERRED sub-scores use the same eligible set -------------
def test_required_and_preferred_subscores():
    text = ("Requirements:\n- Experience with PostgreSQL\n- Experience with AWS or Azure\n\n"
            "Nice to have:\n- Python, Kafka, Docker")
    assessment, resp = run(text, [PG, PY])
    assert (assessment.required.supported, assessment.required.assessable) == (1, 1)    # v1: 1/2
    assert (assessment.preferred.supported, assessment.preferred.assessable) == (1, 2)  # v1: 1/3
    kafka = row_for(resp, "unresolved:kafka")
    assert kafka.necessity == "preferred" and kafka.counts_toward_alignment is False


# 11. Education and non-technical requirements --------------------------------
def test_non_technical_rows_are_not_assessable_and_excluded():
    text = ("Requirements:\n- Bachelor's degree in Computer Science\n- Strong communication skills\n"
            "- Experience with Docker")
    assessment, resp = run(text, [DOCKER])
    assert score(assessment) == (100, 1)
    for r in resp.requirements.not_assessable:
        assert r.counts_toward_alignment is False and r.alignment_exclusion_reason == "not_assessable"
    assert resp.assessment.excluded_from_alignment_count == 0   # NOT_ASSESSABLE rows are not "excluded"


# 12. G17 compound placeholder ------------------------------------------------
def test_g17_compound_placeholder_excluded_and_unchanged():
    text = "Requirements:\n- Experience with Docker or Kubernetes, and Python\n- Experience with PostgreSQL"
    assessment, resp = run(text, [PY, PG])
    assert score(assessment) == (100, 1)
    (placeholder,) = resp.requirements.not_assessable
    assert placeholder.interpretation_status == "unparsed_placeholder"
    assert placeholder.alignment_exclusion_reason == "not_assessable"


# 13. Unknown GitHub-language fallback: evidence stays visible ----------------
def test_unregistered_github_language_evidence_visible_but_not_counted():
    assessment, resp = run("Requirements:\n- Python, Elixir, Docker", [PY, "unresolved:elixir"])
    assert score(assessment) == (50, 2)                        # v1: 67 (2/3)
    elixir = row_for(resp, "unresolved:elixir")
    assert elixir.status == "supported" and elixir.evidence
    assert elixir.counts_toward_alignment is False
    assert elixir.alignment_exclusion_reason == "unresolved_technology"


# 14. Duplicate alternatives --------------------------------------------------
def test_duplicate_alternatives():
    assert score(run("Requirements:\n- Experience with Azure or Microsoft Azure")[0]) == (None, 0)   # v1: 0 (0/1)
    assert score(run("Requirements:\n- Experience with Go or Golang", [PY])[0]) == (None, 0)


# 15. Candidate evidence changes for the same job -----------------------------
def test_eligibility_is_candidate_independent():
    text = ("Requirements:\n- Python\n- Experience with AWS or Azure\n- Python, Terraform, Docker\n"
            "- Experience with Elixir or Zig\n- Experience with Docker or Kubernetes")
    pool = [PY, AWS, DOCKER, K8S, "unresolved:elixir", "unresolved:zig"]
    rng = random.Random(19)
    seen = set()
    for _ in range(40):
        _, resp = run(text, rng.sample(pool, rng.randint(0, len(pool))))
        seen.add(tuple(sorted((r.text, r.concept_id or ",".join(r.alternative_concept_ids), r.counts_toward_alignment)
                              for r in rows(resp))))
    assert len(seen) == 1


# 16. No eligible requirements remaining --------------------------------------
def test_no_eligible_requirement_means_undefined_score():
    # One eligible requirement left (Python): a defined 0, not undefined.
    assessment, resp = run("Requirements:\n- Experience with Azure or GCP\n- Python, SPI", [])
    assert (assessment.alignment_score, resp.assessment.assessable_requirement_count) == (0, 1)
    assert resp.assessment.excluded_from_alignment_count == 2
    # Nothing eligible: undefined, never 0.
    assessment, resp = run("Requirements:\n- Experience with Azure or GCP")
    assert (resp.assessment.github_evidence_alignment, resp.assessment.assessable_requirement_count) == (None, 0)
    assert assessment.required is None


# 17. Registered concept without a declared evidence pathway ------------------
def test_registered_concept_without_pathway_is_not_assessable():
    from gitscore.concepts.models import TechnicalConcept
    from gitscore.concepts.registry import ConceptRegistry
    from gitscore.evidence.capability import Capability, concept_capability
    reg = ConceptRegistry((TechnicalConcept(concept_id="hardware.bus_x", display_name="Bus X",
                                            category="hardware_interface", aliases=("bx",),
                                            readme_unsafe_aliases=frozenset({"bx"})),))
    decision = concept_capability("hardware.bus_x", reg)
    assert decision.capability == Capability.NOT_ASSESSABLE and decision.reasons


# 20. Unrelated evidence never satisfies a requirement -------------------------
def test_related_evidence_does_not_satisfy():
    assessment, resp = run("Requirements:\n- Experience with Kubernetes", [DOCKER])
    assert score(assessment) == (0, 1)
    (row,) = resp.requirements.not_observed
    assert row.counts_toward_alignment is True and row.alignment_exclusion_reason is None


# Count reconciliation ---------------------------------------------------------
@pytest.mark.parametrize("text, evidence", [
    ("Requirements:\n- Python\n- Docker\n- Experience with AWS or Azure\n- PostgreSQL", [PY, AWS]),
    ("Requirements:\n- Python, Elixir, Docker\n- Bachelor's degree in Computer Science", [PY, "unresolved:elixir"]),
    ("Requirements:\n- Experience with Azure or GCP", []),
])
def test_counts_reconcile_exactly(text, evidence):
    _, resp = run(text, evidence)
    evaluated = resp.requirements.supported + resp.requirements.not_observed
    assert len(evaluated) == resp.assessment.assessable_requirement_count + \
        resp.assessment.excluded_from_alignment_count
    assert resp.assessment.assessable_requirement_count == sum(r.counts_toward_alignment for r in rows(resp))
    assert all(r.alignment_exclusion_reason is None for r in rows(resp) if r.counts_toward_alignment)
    assert all(r.alignment_exclusion_reason for r in rows(resp) if not r.counts_toward_alignment)
    assert resp.versions.scoring == "github_evidence_alignment:v2"


# Frozen G18 controls: live v2 == G18's simulated policy C (declared) ----------
def _g18():
    controls = json.loads((G18 / "eligibility_controls.json").read_text(encoding="utf-8"))["controls"]
    report = json.loads((G18 / "eligibility_report.json").read_text(encoding="utf-8"))
    return controls, report


def test_live_v2_equals_g18_policy_c_on_all_54_candidate_pairs():
    controls, report = _g18()
    mismatches = []
    for c in controls:
        for cand in c["candidates"]:
            a, resp = run(c["job_text"], cand["evidence"])
            eligible_supported = sum(r.counts_toward_alignment for r in resp.requirements.supported)
            sim = report["g18_controls"]["results"][c["id"]]["candidates"][cand["name"]]["policies"][
                "C_capability_declared"]
            if (a.alignment_score, eligible_supported, a.assessable_count) != \
                    (sim["score"], sim["supported"], sim["eligible"]):
                mismatches.append(f"{c['id']}/{cand['name']}")
    assert sum(len(c["candidates"]) for c in controls) == 54
    assert mismatches == []


_NOT_SCOREABLE = ("partially_observable_no_positive_evidence", "completely_non_assessable", "structurally_ambiguous",
                  "compound_logic_contained", "non_technical_claim", "not_a_requirement")


def test_g18_acceptance_targets_measured_live():
    """Wrong NOT_OBSERVED counted 27 -> 0; uncheckable rows scored 33 -> 2
    (both control 25's narrative parser defect), over the 106 frozen
    outcomes, measured from the live API's counts_toward_alignment."""
    import m11g18_eligibility as el
    from gitscore.jobs.parsing.parser import parse_job_description
    controls, _ = _g18()
    wrong_not_observed, uncheckable, outcomes = [], [], 0
    for c in controls:
        reqs = parse_job_description(c["job_text"]).requirements
        for cand in c["candidates"]:
            a, _ = run(c["job_text"], cand["evidence"])
            matches = a.match_analysis.requirement_matches
            counted = {i for i, m in enumerate(matches) if a.counts_toward_alignment(m)}
            for g in c["gold_requirements"]:
                outcomes += 1
                e = c["expected"][cand["name"]][g["gid"]]
                cover = [i for i, r in enumerate(reqs) if el._covers(r, g, c["job_text"])]
                statuses = [matches[i].status.value for i in cover if i in counted]
                key = f"{c['id']}/{cand['name']}/{g['gid']}"
                if e["category"] in _NOT_SCOREABLE and "not_observed" in statuses:
                    wrong_not_observed.append(key)
                if not e["eligible_ideal"] and statuses:
                    uncheckable.append(key)
    assert outcomes == 106
    assert wrong_not_observed == []
    assert uncheckable == ["m11g18-25/python_docker/g1", "m11g18-25/python_docker/g3"]


# Capability contract (Phase 2) -------------------------------------------------
def _pathway_emits(concept, pathway) -> bool:
    """Run the REAL extractor behind `pathway` on synthetic input built from
    the concept's own registry data; True iff it emits this concept id."""
    from gitscore.evidence.capability import EvidencePathway
    from gitscore.evidence.extraction.docker import evidence_from_docker_files
    from gitscore.evidence.extraction.languages import evidence_from_languages
    from gitscore.evidence.extraction.readme import evidence_from_readme
    if pathway == EvidencePathway.README_MENTION:
        emitted = {e.concept_id for alias in concept.readme_safe_aliases()
                   for e in evidence_from_readme("o", "r", f"This project is built with {alias}.", "README.md")}
    elif pathway == EvidencePathway.REPOSITORY_LANGUAGE:
        emitted = {e.concept_id for name in (concept.display_name, *concept.aliases)
                   for e in evidence_from_languages("o", "r", {name: 1000})}
    else:
        emitted = {e.concept_id for e in evidence_from_docker_files("o", "r", {"Dockerfile": "Dockerfile"})}
    return concept.concept_id in emitted


def test_every_assessable_concept_has_a_pathway_validated_by_its_real_extractor():
    from gitscore.concepts.registry import default_registry
    from gitscore.evidence.capability import Capability, concept_capability
    concepts = default_registry().all_concepts()
    assert len(concepts) == 39
    for concept in concepts:
        decision = concept_capability(concept.concept_id)
        assert decision.capability == Capability.ASSESSABLE and decision.reasons, concept.concept_id
        for pathway in decision.pathways:
            assert _pathway_emits(concept, pathway), (concept.concept_id, pathway)


def test_unresolved_and_unknown_ids_are_never_assessable():
    from gitscore.evidence.capability import Capability, concept_capability
    for cid in ("unresolved:azure", "unresolved:elixir", "unresolved:terraform"):
        d = concept_capability(cid)
        assert d.capability == Capability.UNRESOLVED and d.pathways == () and d.reasons
    assert concept_capability("cloud.azure").capability == Capability.NOT_ASSESSABLE


def test_capability_is_deterministic_candidate_free_and_list_free():
    import inspect

    from gitscore.concepts.registry import default_registry
    from gitscore.evidence import capability
    assert list(inspect.signature(capability.concept_capability).parameters) == ["concept_id", "registry"]
    assert capability.concept_capability("language.c") == capability.concept_capability("language.c")
    src = inspect.getsource(capability).lower()
    # No hardcoded concept/language list: the only concept id it names comes
    # from the Docker extractor's own constant.
    named = [c.concept_id for c in default_registry().all_concepts() if f'"{c.concept_id}"' in src]
    assert named == []
    for language in ("elixir", "zig", "vue", "matlab", "python"):
        assert f'"{language}"' not in src


def test_exclusion_reason_vocabulary_is_closed_and_stable():
    from gitscore.assessment import AlignmentExclusionReason
    assert {r.value for r in AlignmentExclusionReason} == {
        "not_assessable", "unresolved_technology", "unresolved_alternative",
        "technology_without_evidence_pathway", "alternative_without_evidence_pathway"}


def test_without_pathway_reasons_reach_the_api(monkeypatch):
    """A registered concept with no declared pathway is excluded with the
    'without_evidence_pathway' reasons (alone and inside a mixed group)."""
    from gitscore.assessment import models
    from gitscore.evidence.capability import Capability, CapabilityDecision, concept_capability

    def fake(cid, registry=None):
        if cid == AWS:
            return CapabilityDecision(cid, Capability.NOT_ASSESSABLE, (), ("test: no pathway",))
        return concept_capability(cid, registry)
    monkeypatch.setattr(models, "concept_capability", fake)
    assessment, resp = run("Requirements:\n- Experience with AWS\n- Experience with Docker or AWS", [AWS, DOCKER])
    assert score(assessment) == (None, 0)
    reasons = sorted(r.alignment_exclusion_reason for r in rows(resp))
    assert reasons == ["alternative_without_evidence_pathway", "technology_without_evidence_pathway"]
    assert all(r.status == "supported" and r.evidence for r in rows(resp))


# API backward compatibility (Phase 5/9) ----------------------------------------
def test_api_changes_are_strictly_additive():
    from gitscore.api.schemas import AssessmentOut, RequirementOut
    assert set(RequirementOut.model_fields) == {
        "text", "status", "necessity", "importance", "github_observability", "parser_confidence", "concept_id",
        "concept_label", "category", "interpretation_status", "alternative_concept_ids", "matched_concept_ids",
        "evidence", "counts_toward_alignment", "alignment_exclusion_reason"}
    assert set(AssessmentOut.model_fields) == {
        "github_evidence_alignment", "assessable_requirement_count", "uninterpreted_requirement_count",
        "unparsed_claim_count", "excluded_from_alignment_count"}
    _, resp = run("Requirements:\n- Experience with AWS or Azure\n- Experience with Docker", [AWS])
    # status meanings unchanged: the excluded AWS-or-Azure row is still "supported"
    assert [r.status for r in resp.requirements.supported] == ["supported"]
    assert [r.status for r in resp.requirements.not_observed] == ["not_observed"]
    assert resp.versions.matcher == "requirement_matcher:v1"
    assert resp.versions.job_parser == "job_description_parser:v13"


# Actual v1 vs v2 comparison (Phase 7/8), committed output ----------------------
def _comparison():
    return json.loads((REPO_ROOT / "evaluation" / "m11g19" / "v1_v2_comparison.json").read_text(encoding="utf-8"))


def test_v1_v2_comparison_preserves_every_status_and_evidence_item():
    cmp = _comparison()
    assert cmp["versions"]["v1"][0] == "github_evidence_alignment:v1"
    assert cmp["versions"]["v2"][0] == "github_evidence_alignment:v2"
    assert cmp["versions"]["v1"][1:] == cmp["versions"]["v2"][1:]          # parser and matcher unchanged
    corpora = [cmp[k] for k in ("g18", "g15", "g16", "m10_soti_manulife")] + list(cmp["frozen_8c"].values())
    for corpus in corpora:
        assert corpus["match_status_or_evidence_changed"] == []
        assert corpus["count_reconciliation_failures"] == []
        assert corpus["reason_consistency_failures"] == []


def test_v1_v2_comparison_matches_g18_predictions():
    cmp = _comparison()
    assert cmp["g18_live_v2_vs_simulated_policy_c"]["equal_to_g18_simulated_policy_c"] == 54
    assert cmp["g18"]["by_direction"] == {"became_undefined": 17, "decreased": 2, "denominator_only": 8,
                                          "increased": 10, "unchanged": 17}
    assert sorted(cmp["g18"]["ids_by_direction"]["decreased"]) == [
        "m11g18-10/python_elixir_evidence", "m11g18-23/python_matlab_evidence"]
    expected_8c = {
        "karpathy/frontend_01": [[50, 6], [60, 5]], "sindresorhus/frontend_01": [[67, 6], [80, 5]],
        "sindresorhus/robotics_controls_01": [[25, 4], [33, 3]], "torvalds/data_science_01": [[20, 5], [25, 4]],
        "torvalds/embedded_firmware_01": [[20, 5], [50, 2]], "Jango1324/embedded_firmware_01": [[0, 5], [0, 2]]}
    for label in ("8c:v1", "8c:v1.1"):
        changes = cmp["frozen_8c"][label]["changes"]
        assert {k: [v["v1"], v["v2"]] for k, v in changes.items()} == expected_8c


def test_private_v1_v2_aggregates_are_counts_only():
    path = REPO_ROOT / "evaluation" / "m11g19" / "private_v1_v2_aggregates.json"
    if not path.exists():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    allowed_reasons = {"unresolved_technology", "unresolved_alternative", "technology_without_evidence_pathway",
                       "alternative_without_evidence_pathway"}
    for name, block in data.items():
        if name == "note":
            continue
        assert name in {"m11d", "m11f", "m11g5", "m11g9"}
        for k, v in block.items():
            if k == "excluded_by_reason_v2":
                assert set(v) <= allowed_reasons and all(isinstance(n, int) for n in v.values())
            else:
                assert isinstance(v, int), (name, k)
