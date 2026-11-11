"""Milestone 11-G22-R -- evaluation harness: real evidence pipeline + real parser + matcher + scoring v2.

Each control's synthetic repositories become a persisted-fixture-shaped dict served by the SAME
offline client the frozen 8c evaluation uses (`loaders.FakeCandidateGitHubClient`), and go through
`pipeline.evidence.extract_candidate_evidence()` unchanged: repository selection, the language,
README, Docker and manifest extractors, deduplication and concept summaries. The job text goes
through the real parser; matching is `match_job`; scoring is `assess_job` (v2). Nothing is
simulated except where a G22-R policy explicitly patches (see m11g22r_policies.py).
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import m11g22r_policies as rpol
from gitscore.assessment import assess_job
from gitscore.concepts.registry import default_registry, is_unresolved_concept_id
from gitscore.evidence.profile import build_candidate_evidence_profile
from gitscore.evidence.types import EvidenceType
from gitscore.jobs.parsing.parser import parse_job_description_with_diagnostics
from gitscore.matching import match_job
from gitscore.pipeline.evidence import extract_candidate_evidence
from loaders import FakeCandidateGitHubClient

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "evaluation" / "m11g22r"
OWNER = "synthetic-candidate"
COLLECTED_AT = datetime(2026, 11, 1, tzinfo=timezone.utc)
_REG = default_registry()
_README_ALIAS = re.compile(r"^README mentions '([^']+)'")


def load_controls(split: str) -> list[dict]:
    return json.loads((DATA / f"alias_evidence_controls_{split}.json").read_text(encoding="utf-8"))["controls"]


def fixture(control: dict) -> dict:
    repos_raw, selected = [], {}
    for r in control["repos"]:
        repos_raw.append({"name": r["name"], "description": None, "language": None, "fork": False, "archived": False,
                          "size": 100, "stargazers_count": 0, "forks_count": 0, "topics": [],
                          "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-10-01T00:00:00Z",
                          "pushed_at": "2026-10-01T00:00:00Z", "html_url": f"https://example.invalid/{r['name']}"})
        selected[r["name"]] = {"languages": r["languages"],
                               "readme": [r["readme"], "README.md"] if r["readme"] else None,
                               "root_contents": [{"name": f, "path": f, "type": "file"} for f in r["files"]],
                               "files": r["files"]}
    return {"repos_raw": repos_raw, "selected": selected}


def candidate_profile(control: dict, policy: rpol.Policy):
    fx = fixture(control)
    profile = extract_candidate_evidence(OWNER, client=FakeCandidateGitHubClient(repos=fx["repos_raw"],
                                                                                 selected=fx["selected"]),
                                         top_n=15, collected_at=COLLECTED_AT).profile
    if policy.readme_only_insufficient:
        corroborated = {e.concept_id for e in profile.evidence if e.evidence_type != EvidenceType.README}
        kept = [e for e in profile.evidence if e.evidence_type != EvidenceType.README or e.concept_id in corroborated]
        profile = build_candidate_evidence_profile(profile.candidate, profile.coverage.discovered,
                                                   profile.coverage.analyzed, kept, collected_at=COLLECTED_AT)
    return profile


def _members(r) -> tuple[str, ...]:
    return tuple(sorted(r.alternative_concept_ids)) or ((r.concept_id,) if r.concept_id else ())


def job_text(control: dict) -> str:
    if control["job_text"] is not None:
        return control["job_text"]
    return f"Requirements:\n- Experience with {_REG.get(control['probe']).display_name}."


def run_control(control: dict, policy: rpol.Policy = rpol.BASE) -> dict:
    mentioned, used = set(control["mentioned"]), set(control["used"])
    with rpol.applied(policy):
        profile = candidate_profile(control, policy) if control["repos"] else None
        text = job_text(control)
        parsed = parse_job_description_with_diagnostics(text)
    evidence = [] if profile is None else [
        {"repo": e.repository.name, "type": e.evidence_type.value, "concept": e.concept_id,
         "alias": (m.group(1) if (m := _README_ALIAS.match(e.raw_observation)) else None),
         "confidence": e.confidence.name, "file_path": e.file_path, "extractor": e.extractor_version}
        for e in profile.evidence]
    readme_ids = {e["concept"] for e in evidence if e["type"] == "readme"}
    other_ids = {e["concept"] for e in evidence if e["type"] != "readme" and not is_unresolved_concept_id(e["concept"])}
    from m11g15_or_scoring import candidate_profile as empty_profile
    a = assess_job(match_job(profile if profile is not None else empty_profile([]), parsed.profile))
    rows = []
    for m in a.match_analysis.requirement_matches:
        mem = _members(m.requirement)
        truth = bool(set(mem) & used)
        kinds = sorted({e.evidence_type.value for e in m.supporting_evidence})
        rows.append({"members": list(mem), "category": m.requirement.category,
                     "necessity": m.requirement.necessity.value,
                     "job_concept_correct": bool(set(mem) & set(control["job_concepts"])) if control["job_text"]
                     else bool(set(mem) & {control["probe"]}),
                     "status": m.status.value, "counts": a.counts_toward_alignment(m), "truth_used": truth,
                     "supporting_evidence_types": kinds,
                     "supported_by_false_readme_only": m.status.value == "supported" and kinds == ["readme"]
                     and not (set(m.matched_concept_ids) & mentioned)})
    job_ids = {i for r in rows for i in r["members"] if not is_unresolved_concept_id(i)}
    expected_job = set(control["job_concepts"]) if control["job_text"] else {control["probe"]}
    # false SUPPORTED: a counted SUPPORTED row whose requirement does not exist (job-side false concept) or
    # whose concept the candidate does not genuinely use (evidence-side)
    false_sup = [r for r in rows if r["status"] == "supported" and r["counts"]
                 and not (r["truth_used"] and r["job_concept_correct"])]
    return {
        "id": control["id"], "family": control["family"], "cell": control["cell"], "alias": control["alias"],
        "job_text_source": "control" if control["job_text"] is not None else "probe",
        "evidence": evidence,
        "readme_false_extraction": sorted(readme_ids - mentioned),
        "readme_mention_without_use": sorted((readme_ids & mentioned) - used),
        "readme_genuine_extracted": sorted(readme_ids & mentioned & used),
        "readme_genuine_expected": sorted(mentioned & used),
        "artifact_false_extraction": sorted(other_ids - used),
        "job_false_concepts": sorted(job_ids - expected_job),
        "job_missed_concepts": sorted(expected_job - job_ids),
        "rows": rows,
        "numerator": sum(1 for r in rows if r["counts"] and r["status"] == "supported"),
        "denominator": a.assessable_count, "score": a.alignment_score,
        "false_supported": [{"members": r["members"],
                             "cause": "job_false_concept" if not r["job_concept_correct"] else
                             ("false_readme_extraction" if r["supported_by_false_readme_only"] else
                              ("readme_mention_without_use" if r["supporting_evidence_types"] == ["readme"]
                               else "other"))} for r in false_sup],
        "true_supported": sum(1 for r in rows if r["status"] == "supported" and r["counts"] and r["truth_used"]
                              and r["job_concept_correct"]),
        "missed_true": sum(1 for r in rows if r["counts"] and r["status"] == "not_observed" and r["truth_used"]),
    }


def aggregate(results: list[dict]) -> dict:
    causes = Counter(f["cause"] for r in results for f in r["false_supported"])
    exp = sum(len(r["readme_genuine_expected"]) for r in results)
    got = sum(len(r["readme_genuine_extracted"]) for r in results)
    return {
        "controls": len(results),
        "readme_false_extractions": sum(len(r["readme_false_extraction"]) for r in results),
        "readme_mention_without_use_extractions": sum(len(r["readme_mention_without_use"]) for r in results),
        "readme_genuine_recall": [got, exp],
        "artifact_false_extractions": sum(len(r["artifact_false_extraction"]) for r in results),
        "job_false_concepts": sum(len(r["job_false_concepts"]) for r in results),
        "job_missed_concepts": sum(len(r["job_missed_concepts"]) for r in results),
        "false_supported": sum(len(r["false_supported"]) for r in results),
        "false_supported_by_cause": dict(sorted(causes.items())),
        "true_supported": sum(r["true_supported"] for r in results),
        "missed_true_supported": sum(r["missed_true"] for r in results),
        "numerator": sum(r["numerator"] for r in results), "denominator": sum(r["denominator"] for r in results),
    }


def run_split(split: str, policy: rpol.Policy = rpol.BASE) -> tuple[list[dict], dict]:
    results = [run_control(c, policy) for c in load_controls(split)]
    return results, aggregate(results)
