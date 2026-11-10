"""Milestone 11-G15 -- mixed-observability OR scoring: production
reproduction and policy simulation.

Evaluation-only; nothing in `src/gitscore` imports this module and no
production code is changed. Production behaviour is obtained by CALLING
the real `parse_job_description`, `match_requirement`/`match_job` and
`assess_job`. Policies B-D are SIMULATED by re-classifying the real
production `RequirementMatch` results and re-applying the production
rounding function (`assessment.models._round_half_up_percentage`) -- no
new scoring formula exists anywhere here.

Policies (all decide ONLY from production-visible facts; none sees gold):
* A -- current production behaviour.
* B -- a requirement whose concept set contains any `unresolved:` member
       is excluded from the numerical score (numerator and denominator)
       regardless of evidence; its production status is retained as a
       diagnostic.
* C -- richer internal state: such a requirement counts as SUPPORTED when
       an alternative has observed evidence; when none does it becomes
       PARTIALLY_OBSERVABLE_NOT_OBSERVED and is excluded from the score.
* D -- existing-contract normalization: the parser's own Milestone 6B.1
       "unsafe" fallback (category="alternative_requirement",
       PARTIALLY_OBSERVABLE, no concept) is applied to such groups before
       matching -- scoring effect of B, but matched-concept diagnostics
       are lost.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (_REPO_ROOT / "src", _REPO_ROOT / "scripts" / "evaluation_lib"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from gitscore.assessment import SCORING_VERSION, assess_job  # noqa: E402
from gitscore.assessment.models import _round_half_up_percentage  # noqa: E402
from gitscore.concepts.registry import is_unresolved_concept_id  # noqa: E402
from gitscore.evidence import (  # noqa: E402
    ConfidenceLevel,
    Evidence,
    EvidenceType,
    RepositoryIdentity,
    build_candidate_evidence_profile,
)
from gitscore.jobs.parsing.parser import parse_job_description  # noqa: E402
from gitscore.matching import MatchStatus, match_job  # noqa: E402

import gold_integrity as gi  # noqa: E402

CONTROLS_PATH = _REPO_ROOT / "evaluation" / "m11g15" / "or_scoring_controls.json"
FREEZE_PATH = _REPO_ROOT / "evaluation" / "m11g15" / "controls_hash_freeze.json"
POLICIES = ("A_production", "B_exclude_unresolved_groups", "C_partial_state", "D_parser_unsafe_fallback")
SUPPORTED, NOT_OBSERVED, NOT_ASSESSABLE = "supported", "not_observed", "not_assessable"
NEGATIVE_DECIDABLE = ("not_observed_fully_assessable", "unsupported_related_evidence_only")
NOT_SCOREABLE = ("completely_non_assessable", "structurally_ambiguous", "partially_observable_no_positive_evidence")


def load_frozen_controls() -> dict:
    raw = CONTROLS_PATH.read_bytes()
    freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    if gi.sha256(gi.canonical_bytes(raw)) != freeze["sha256_lf_normalized"]:
        raise SystemExit("M11-G15 FROZEN CONTROLS CHANGED (LF-normalized comparison)")
    return json.loads(raw.decode("utf-8"))


def candidate_profile(evidence_ids: list[str]):
    """Registry concepts as dependency evidence; `unresolved:<language>` as
    repository-language evidence (the only extractor that emits unresolved
    ids). A repeated id becomes two evidence items in two repositories,
    plus one exact duplicate (which the profile deduplicates)."""
    items = []
    repos = {}
    for i, cid in enumerate(evidence_ids):
        n = evidence_ids[:i].count(cid)
        repo = RepositoryIdentity(owner="candidate", name=f"repo{n}")
        repos[repo] = None
        etype = EvidenceType.REPOSITORY_LANGUAGE if is_unresolved_concept_id(cid) else EvidenceType.DEPENDENCY
        ev = Evidence(repository=repo, evidence_type=etype, raw_observation=f"synthetic {cid}", concept_id=cid,
                      confidence=ConfidenceLevel.MODERATE, extractor_version="m11g15@1")
        items.append(ev)
        if n:
            items.append(ev)
    discovered = tuple(repos) or (RepositoryIdentity(owner="candidate", name="repo0"),)
    return build_candidate_evidence_profile("candidate", discovered=discovered, analyzed=discovered,
                                            evidence_items=tuple(items))


def row_concepts(req) -> tuple[str, ...]:
    if req.alternative_concept_ids:
        return tuple(req.alternative_concept_ids)
    return (req.concept_id,) if req.concept_id else ()


def has_unresolved(req) -> bool:
    return any(is_unresolved_concept_id(c) for c in row_concepts(req))


def policy_status(policy: str, match) -> tuple[str, bool]:
    """(public status, diagnostic retained)."""
    prod = match.status.value
    if policy == "A_production" or not has_unresolved(match.requirement):
        return prod, True
    if policy == "B_exclude_unresolved_groups":
        return NOT_ASSESSABLE, True
    if policy == "C_partial_state":
        return (SUPPORTED, True) if prod == SUPPORTED else (NOT_ASSESSABLE, True)
    if policy == "D_parser_unsafe_fallback":
        return NOT_ASSESSABLE, False
    raise ValueError(policy)


def score(statuses: list[str]) -> tuple[int | None, int, int]:
    supported = statuses.count(SUPPORTED)
    assessable = supported + statuses.count(NOT_OBSERVED)
    return (None if assessable == 0 else _round_half_up_percentage(supported, assessable)), supported, assessable


def _covers(req, gold: dict, job_text: str) -> bool:
    start = job_text.index(gold["span_text"])
    end = start + len(gold["span_text"])
    span = req.source_span
    overlaps = span is None or (span.start < end and start < span.end)
    concepts = set(row_concepts(req))
    gold_ids = {m["concept_id"] for m in gold["members"]}
    return overlaps and (not concepts or bool(concepts & gold_ids))


def evaluate_control(control: dict) -> dict:
    job_profile = parse_job_description(control["job_text"])
    rows = job_profile.requirements
    golds = control["gold_requirements"]
    coverage = {i: [g["gid"] for g in golds if _covers(r, g, control["job_text"])] for i, r in enumerate(rows)}
    out = {"rows": [
        {"concepts": list(row_concepts(r)), "category": r.category, "necessity": r.necessity.value,
         "observability": r.github_observability.name, "has_unresolved_member": has_unresolved(r),
         "covers_gold": coverage[i]}
        for i, r in enumerate(rows)
    ], "candidates": {}}
    for cand in control["candidates"]:
        profile = candidate_profile(cand["evidence"])
        analysis = match_job(profile, job_profile)
        assessment = assess_job(analysis)
        matches = analysis.requirement_matches
        member_evidence = {
            g["gid"]: {m["concept_id"]: (profile.concept(m["concept_id"]) is not None) for m in g["members"]}
            for g in golds
        }
        per_policy = {}
        for policy in POLICIES:
            statuses = [policy_status(policy, m) for m in matches]
            sc, sup, ass = score([s for s, _ in statuses])
            # Fidelity check against the REAL assessor. Under scoring v1 it must
            # equal simulated policy A; M11-G19 implemented the excluded-unresolved
            # rule as scoring v2, so under v2 it must equal simulated policy B.
            # The simulation itself (and therefore this frozen report) is unchanged.
            if policy == ("A_production" if SCORING_VERSION.endswith(":v1") else "B_exclude_unresolved_groups"):
                assert sc == assessment.alignment_score and ass == assessment.assessable_count, control["id"]
            per_gold = {}
            for g in golds:
                idx = [i for i in coverage if g["gid"] in coverage[i]]
                gstat = [statuses[i][0] for i in idx]
                counted = [s for s in gstat if s in (SUPPORTED, NOT_OBSERVED)]
                matched = set()
                for i in idx:
                    if statuses[i][0] == SUPPORTED:
                        matched |= set(matches[i].matched_concept_ids)
                own = {m["concept_id"] for m in g["members"]}
                per_gold[g["gid"]] = {
                    "rows": idx,
                    "status": gstat[0] if gstat else "unrepresented",
                    "counted_rows": len(counted),
                    "merged_with_other_gold": any(len(coverage[i]) > 1 for i in idx),
                    "support_from_other_requirement": bool(matched) and not (matched & own),
                    "diagnostic_retained": all(statuses[i][1] for i in idx) if idx else False,
                }
            per_policy[policy] = {"score": sc, "supported": sup, "assessable": ass, "per_gold": per_gold}
        out["candidates"][cand["name"]] = {
            "production_row_status": [m.status.value for m in matches],
            "member_evidence": member_evidence,
            "policies": per_policy,
        }
    return out


def _frac(ids: list, denom: int) -> dict:
    return {"count": len(ids), "denominator": denom, "ids": ids}


def metrics(controls: list[dict], results: dict) -> dict:
    out = {}
    triples = [(c, cand["name"], g) for c in controls for cand in c["candidates"] for g in c["gold_requirements"]]
    for policy in POLICIES:
        false_sup, false_no, false_no_truth, nonassess, discarded, leak, merged, dup, unrep = ([] for _ in range(9))
        for c, cname, g in triples:
            exp = c["expected"][cname][g["gid"]]
            pg = results[c["id"]]["candidates"][cname]["policies"][policy]["per_gold"][g["gid"]]
            key = f"{c['id']}/{cname}/{g['gid']}"
            st, counted = pg["status"], pg["counted_rows"] > 0
            if st == SUPPORTED and (exp["truth_satisfied"] is False
                                    or exp["category"] == "unsupported_related_evidence_only"):
                false_sup.append(key)
            if st == NOT_OBSERVED and exp["category"] not in NEGATIVE_DECIDABLE:
                false_no.append(key)
                if exp["truth_satisfied"]:
                    false_no_truth.append(key)
            if counted and exp["category"] in NOT_SCOREABLE:
                nonassess.append(key)
            if exp["category"] == "satisfied_by_observed_evidence" and st != SUPPORTED:
                discarded.append(key)
            if st == SUPPORTED and pg["support_from_other_requirement"]:
                leak.append(key)
            if counted and pg["merged_with_other_gold"]:
                merged.append(key)
            if pg["counted_rows"] > 1:
                dup.append(key)
            if st == "unrepresented":
                unrep.append(key)
        n = len(triples)
        denominators = {}
        for c in controls:
            ds = sorted({results[c["id"]]["candidates"][cand["name"]]["policies"][policy]["assessable"]
                         for cand in c["candidates"]})
            denominators[c["id"]] = ds
        unstable = [cid for cid, ds in denominators.items() if len(ds) > 1]
        out[policy] = {
            "1_false_supported": _frac(false_sup, n),
            "2_false_not_observed": _frac(false_no, n),
            "2b_false_not_observed_where_candidate_truly_qualifies": _frac(false_no_truth, n),
            "3_non_assessable_counted_in_denominator": _frac(nonassess, n),
            "4_positive_evidence_discarded": _frac(discarded, n),
            "4b_positive_evidence_discarded_excluding_parser_unrepresented": _frac(
                [k for k in discarded if k not in unrep], n),
            "0_gold_requirement_unrepresented_by_parser": _frac(unrep, n),
            "5_duplicate_denominator_counting": _frac(dup, n),
            "5b_merged_requirements_counted_as_one": _frac(merged, n),
            "6_evidence_leakage_between_requirements": _frac(leak, n),
            "9_denominator_unstable_across_candidates": _frac(unstable, len(controls)),
            "denominators_by_control": denominators,
        }
    return out


def run() -> dict:
    data = load_frozen_controls()
    controls = data["controls"]
    results = {c["id"]: evaluate_control(c) for c in controls}
    scores = {
        c["id"]: {cand["name"]: {p: results[c["id"]]["candidates"][cand["name"]]["policies"][p]["score"]
                                 for p in POLICIES} for cand in c["candidates"]}
        for c in controls
    }
    changed = {p: sorted(f"{cid}/{cn}" for cid, cs in scores.items() for cn, s in cs.items()
                         if s[p] != s["A_production"]) for p in POLICIES[1:]}
    return {
        "milestone": "M11-G15",
        "controls_sha256_lf_normalized": gi.sha256(gi.canonical_bytes(CONTROLS_PATH.read_bytes())),
        "policies": list(POLICIES),
        "metrics": metrics(controls, results),
        "7_scores": scores,
        "7_score_changes_vs_production": {p: {"count": len(v), "ids": v} for p, v in changed.items()},
        "results": results,
    }
