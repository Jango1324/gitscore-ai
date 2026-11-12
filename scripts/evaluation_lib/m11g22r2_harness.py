"""Milestone 11-G22-R2 -- harness: real evidence pipeline + real parser + matcher + scoring v2.

Synthetic repositories are served by the 8c offline fixture client (via G22-R's `fixture()`), go through
`pipeline.evidence.extract_candidate_evidence()` unchanged, and the probe requirement
"Experience with <display>." goes through the real parser, `match_job` and `assess_job` (v2).
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import m11g22r2_policies as p2
import m11g22r_harness as h22r
from gitscore.assessment import assess_job
from gitscore.concepts.registry import default_registry, is_unresolved_concept_id
from gitscore.jobs.parsing.parser import parse_job_description_with_diagnostics
from gitscore.matching import match_job
from gitscore.pipeline.evidence import extract_candidate_evidence
from loaders import FakeCandidateGitHubClient

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "evaluation" / "m11g22r2"
_REG = default_registry()
NON_USE = ("reference", "historical", "future", "negated")


def load_controls(split: str) -> list[dict]:
    return json.loads((DATA / f"readme_context_controls_{split}.json").read_text(encoding="utf-8"))["controls"]


def profile_for(repos: list[dict], policy: p2.Policy):
    fx = h22r.fixture({"repos": repos})
    with p2.applied(policy):
        prof = extract_candidate_evidence(h22r.OWNER, client=FakeCandidateGitHubClient(repos=fx["repos_raw"],
                                                                                        selected=fx["selected"]),
                                          top_n=15, collected_at=h22r.COLLECTED_AT).profile
    return p2.interpret(prof, policy)


def run_control(c: dict, policy: p2.Policy = p2.A) -> dict:
    prof = profile_for(c["repos"], policy)
    text = f"Requirements:\n- Experience with {_REG.get(c['probe']).display_name}."
    a = assess_job(match_job(prof, parse_job_description_with_diagnostics(text).profile))
    (m,) = [x for x in a.match_analysis.requirement_matches if x.requirement.concept_id == c["probe"]]
    readme = {e.concept_id: e for e in prof.evidence if e.evidence_type.value == "readme"}
    classes = c["concepts"]
    probe_truth = "uncertain" if c["probe"] in c["uncertain"] else c["probe"] in c["used"]
    supported = m.status.value == "supported" and a.counts_toward_alignment(m)
    return {
        "id": c["id"], "family": c["family"], "pair": c["pair"], "probe": c["probe"],
        "evidence": sorted([e.repository.name, e.evidence_type.value, e.concept_id, e.confidence.name]
                           for e in prof.evidence),
        "readme_concepts": {cid: classes.get(cid, "unlabelled") for cid in sorted(readme)},
        "probe_class": classes.get(c["probe"]),
        "probe_status": m.status.value, "probe_counts": a.counts_toward_alignment(m),
        "probe_evidence_types": sorted({e.evidence_type.value for e in m.supporting_evidence}),
        "probe_truth": probe_truth, "score": a.alignment_score, "numerator": int(supported),
        "denominator": a.assessable_count,
        "outcome": ("uncertain_" + ("supported" if supported else "not_supported")) if probe_truth == "uncertain" else
                   ("true_supported" if supported and probe_truth else "false_supported" if supported else
                    "missed" if probe_truth else "true_not_supported"),
    }


def aggregate(results: list[dict], controls: list[dict]) -> dict:
    by_id = {c["id"]: c for c in controls}
    cls = Counter()
    for r in results:
        for cid, k in r["readme_concepts"].items():
            cls[k] += 1
    labelled = Counter(k for c in controls for k in c["concepts"].values())
    use_total = sum(1 for c in controls for cid, k in c["concepts"].items() if k == "use")
    use_kept = sum(1 for r in results for cid, k in r["readme_concepts"].items() if k == "use")
    ordinary_total = labelled["ordinary"]
    outcomes = Counter(r["outcome"] for r in results)
    fs_cause = Counter(r["probe_class"] or "unlabelled" for r in results if r["outcome"] == "false_supported")
    corroborated = [r for r in results if r["probe_truth"] is True and any(t != "readme" for t in
                    {e[1] for e in r["evidence"] if e[2] == r["probe"]} | set())]
    return {
        "controls": len(results),
        "readme_items_by_label_class": dict(sorted(cls.items())),
        "false_readme_evidence_ordinary": cls["ordinary"] + cls["unlabelled"],
        "nonuse_readme_evidence": {k: cls[k] for k in NON_USE},
        "ordinary_correctly_rejected": [ordinary_total - cls["ordinary"], ordinary_total],
        "use_claims_retained": [use_kept, use_total],
        "genuine_use_lost": use_total - use_kept,
        "corroborated_supported": [sum(1 for r in corroborated if r["outcome"] == "true_supported"), len(corroborated)],
        "false_supported": outcomes["false_supported"], "false_supported_by_probe_class": dict(sorted(fs_cause.items())),
        "true_supported": outcomes["true_supported"], "missed_true_supported": outcomes["missed"],
        "true_not_supported": outcomes["true_not_supported"],
        "uncertain": {"supported": outcomes["uncertain_supported"], "not_supported": outcomes["uncertain_not_supported"]},
        "numerator": sum(r["numerator"] for r in results), "denominator": sum(r["denominator"] for r in results),
        "unlabelled_readme_concepts": sorted({(r["id"], cid) for r in results for cid, k in r["readme_concepts"].items()
                                              if k == "unlabelled"}),
        "_ids_with_unregistered": [r["id"] for r in results if any(is_unresolved_concept_id(e[2]) for e in r["evidence"])
                                   and r["id"] not in by_id],
    }


def run_split(split: str, policy: p2.Policy = p2.A):
    controls = load_controls(split)
    results = [run_control(c, policy) for c in controls]
    return results, aggregate(results, controls)
