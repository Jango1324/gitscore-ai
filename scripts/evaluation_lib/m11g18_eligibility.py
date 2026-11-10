"""Milestone 11-G18 -- observability-aware score eligibility: capability
classification and policy simulation.

Evaluation-only; nothing in `src/gitscore` imports this module and no
production code is changed. Production behaviour is obtained by CALLING
the real `parse_job_description`, `match_job` and `assess_job`. Every
policy re-uses the production `RequirementMatch` objects unchanged and
re-applies the production rounding function
(`assessment.models._round_half_up_percentage`); no new formula exists.

Capability (per concept, candidate-independent):
* ASSESSABLE -- some existing extractor DECLARES a pathway that can emit
  evidence for this concept id.
* NOT_ASSESSABLE -- no extractor can ever emit it.
* UNRESOLVED -- an extractor might emit it, but nothing in the repository
  declares whether it does (the `unresolved:<term>` ids: only the
  language extractor emits them, and only for GitHub-reported language
  names; no language vocabulary exists in the repository).

Requirement score eligibility (candidate-independent, decided from the
requirement alone): eligible iff the matcher can evaluate it at all
(not NOT_OBSERVABLE, has a concept mapping) AND every member concept is
ASSESSABLE. A single requirement is an OR group of one.

Policies (all decide ONLY from production-visible facts; none sees gold):
* A_production -- counted iff status != NOT_ASSESSABLE.
* B_prefix_exclusion -- additionally excluded if any member id carries
  the `unresolved:` prefix (G15 policy B widened to standalone rows).
  Status and evidence retained as diagnostics.
* C_capability_declared -- additionally excluded unless every member is
  ASSESSABLE under the capability contract with NO language vocabulary
  (what the repository declares today). Diagnostics retained.
* C_capability_oracle -- the same contract given a language vocabulary
  (ORACLE upper bound: built from annotator facts, not implementable from
  the repository; reported only to size what a vocabulary would buy).
* D_parser_fallback -- B's eligibility, but rows are re-routed to the
  6B.1 placeholder: status NOT_ASSESSABLE, matched evidence discarded.
* E_asymmetric_rejected -- G15's rejected policy C: a non-eligible row
  counts when SUPPORTED, is excluded otherwise (candidate-dependent).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (_REPO_ROOT / "src", _REPO_ROOT / "scripts" / "evaluation_lib"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from gitscore.assessment import SCORING_VERSION, assess_job  # noqa: E402
from gitscore.assessment.models import _round_half_up_percentage  # noqa: E402
from gitscore.concepts.registry import ConceptRegistry, default_registry, is_unresolved_concept_id  # noqa: E402
from gitscore.evidence.extraction.docker import DOCKER_CONCEPT_ID  # noqa: E402
from gitscore.jobs.parsing.parser import parse_job_description  # noqa: E402
from gitscore.jobs.types import GithubObservability  # noqa: E402
from gitscore.matching import MatchStatus, match_job  # noqa: E402

import gold_integrity as gi  # noqa: E402
import m11g18_build_controls as builder  # noqa: E402
from m11g15_or_scoring import candidate_profile  # noqa: E402

CONTROLS_PATH = _REPO_ROOT / "evaluation" / "m11g18" / "eligibility_controls.json"
FREEZE_PATH = _REPO_ROOT / "evaluation" / "m11g18" / "controls_hash_freeze.json"
G15_CONTROLS_PATH = _REPO_ROOT / "evaluation" / "m11g15" / "or_scoring_controls.json"

ASSESSABLE, NOT_ASSESSABLE_CAP, UNRESOLVED = "ASSESSABLE", "NOT_ASSESSABLE", "UNRESOLVED"
SUPPORTED, NOT_OBSERVED, NOT_ASSESSABLE = "supported", "not_observed", "not_assessable"
POLICIES = ("A_production", "B_prefix_exclusion", "C_capability_declared", "C_capability_oracle",
            "D_parser_fallback", "E_asymmetric_rejected")
DEPLOYABLE = ("A_production", "B_prefix_exclusion", "C_capability_declared", "D_parser_fallback")
_UNRESOLVED_PREFIX = "unresolved:"

# ORACLE ONLY: the annotator's `language_stats` facts across the frozen
# G15 + G18 gold and the 8c corpus (G15 Phase 5 identified Vue and MATLAB
# there). NOT a production proposal and NOT derived from the repository.
ORACLE_LANGUAGE_VOCABULARY = frozenset({"elixir", "zig", "vue", "matlab"})


# ---------------------------------------------------------------- capability
def concept_capability(concept_id: str, registry: ConceptRegistry | None = None,
                       language_vocabulary: frozenset[str] | None = None) -> tuple[str, list[str]]:
    """(capability, reasons) for ONE concept id. Never looks at a candidate."""
    registry = registry or default_registry()
    if is_unresolved_concept_id(concept_id):
        term = concept_id[len(_UNRESOLVED_PREFIX):]
        if language_vocabulary is None:
            return UNRESOLVED, ["outside the registry; only evidence/extraction/languages.py emits unresolved ids "
                                "and only for GitHub-reported language names; the dependency extractor skips "
                                "unknown packages and the README extractor scans registered aliases only; no "
                                "language vocabulary is declared in the repository"]
        if term in language_vocabulary:
            return ASSESSABLE, [f"'{term}' is in the supplied GitHub-language vocabulary (language-stats fallback)"]
        return NOT_ASSESSABLE_CAP, [f"'{term}' is not in the supplied GitHub-language vocabulary and no other "
                                    "extractor emits unresolved ids"]
    concept = registry.get(concept_id)
    if concept is None:
        return NOT_ASSESSABLE_CAP, ["not a registered concept and not an unresolved placeholder"]
    pathways = []
    if concept.readme_safe_aliases():
        pathways.append("readme_mention (readme-safe aliases: "
                        + ", ".join(concept.readme_safe_aliases()) + ")")
    if concept.aliases:
        pathways.append("structured_alias_resolution (dependency manifests and GitHub language stats resolve "
                        "through the full alias list)")
    if concept_id == DOCKER_CONCEPT_ID:
        pathways.append("docker_root_files (Dockerfile / compose detector)")
    if not pathways:
        return NOT_ASSESSABLE_CAP, ["registered, but no extractor declares a pathway that can emit it"]
    return ASSESSABLE, pathways


def requirement_members(req) -> tuple[str, ...]:
    if req.alternative_concept_ids:
        return tuple(req.alternative_concept_ids)
    return (req.concept_id,) if req.concept_id else ()


def requirement_eligibility(req, registry=None, language_vocabulary=None) -> tuple[bool, str]:
    """Candidate-independent score eligibility of ONE JobRequirement."""
    if req.github_observability == GithubObservability.NOT_OBSERVABLE:
        return False, "not_observable"
    members = requirement_members(req)
    if not members:
        return False, "no_concept_mapping"
    caps = {m: concept_capability(m, registry, language_vocabulary)[0] for m in members}
    if all(c == ASSESSABLE for c in caps.values()):
        return True, "all_members_assessable"
    blocked = sorted(m for m, c in caps.items() if c != ASSESSABLE)
    kind = "mixed_or_group" if len(members) > 1 and len(blocked) < len(members) else (
        "or_group_without_assessable_member" if len(members) > 1 else "standalone")
    return False, f"{kind}:" + ",".join(f"{m}={caps[m]}" for m in blocked)


# ------------------------------------------------------------------- policies
def _has_unresolved(req) -> bool:
    return any(m.startswith(_UNRESOLVED_PREFIX) for m in requirement_members(req))


def policy_row(policy: str, match) -> dict:
    """Public status, whether the row counts toward the score, and whether
    the production diagnostic (status + matched evidence) is retained."""
    prod = match.status.value
    req = match.requirement
    evaluable = prod != NOT_ASSESSABLE
    if policy == "A_production":
        return {"status": prod, "counted": evaluable, "diagnostic_retained": True}
    if policy == "B_prefix_exclusion":
        return {"status": prod, "counted": evaluable and not _has_unresolved(req), "diagnostic_retained": True}
    if policy == "C_capability_declared":
        return {"status": prod, "counted": evaluable and requirement_eligibility(req)[0], "diagnostic_retained": True}
    if policy == "C_capability_oracle":
        ok = requirement_eligibility(req, language_vocabulary=ORACLE_LANGUAGE_VOCABULARY)[0]
        return {"status": prod, "counted": evaluable and ok, "diagnostic_retained": True}
    if policy == "D_parser_fallback":
        if _has_unresolved(req):
            return {"status": NOT_ASSESSABLE, "counted": False, "diagnostic_retained": prod == NOT_ASSESSABLE}
        return {"status": prod, "counted": evaluable, "diagnostic_retained": True}
    if policy == "E_asymmetric_rejected":
        if _has_unresolved(req):
            return {"status": prod, "counted": prod == SUPPORTED, "diagnostic_retained": True}
        return {"status": prod, "counted": evaluable, "diagnostic_retained": True}
    raise ValueError(policy)


def score_rows(rows: list[dict]) -> dict:
    counted = [r for r in rows if r["counted"]]
    sup = sum(r["status"] == SUPPORTED for r in counted)
    elig = len(counted)
    assert sup <= elig
    return {"score": None if elig == 0 else _round_half_up_percentage(sup, elig), "supported": sup, "eligible": elig}


# ------------------------------------------------------------------- controls
def load_frozen_controls() -> dict:
    raw = CONTROLS_PATH.read_bytes()
    freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    if gi.sha256(gi.canonical_bytes(raw)) != freeze["sha256_lf_normalized"]:
        raise SystemExit("M11-G18 FROZEN CONTROLS CHANGED (LF-normalized comparison)")
    return json.loads(raw.decode("utf-8"))


def load_g15_controls() -> list[dict]:
    import m11g15_or_scoring as g15
    return g15.load_frozen_controls()["controls"]


def _covers(req, gold: dict, job_text: str) -> bool:
    start = job_text.index(gold["span_text"])
    end = start + len(gold["span_text"])
    span = req.source_span
    overlaps = span is None or (span.start < end and start < span.end)
    concepts = set(requirement_members(req))
    gold_ids = {m["concept_id"] for m in gold["members"]}
    return overlaps and (not concepts or bool(concepts & gold_ids))


_NOT_SCOREABLE_CATEGORIES = ("partially_observable_no_positive_evidence", "completely_non_assessable",
                             "structurally_ambiguous", "compound_logic_contained", "non_technical_claim",
                             "not_a_requirement")


def evaluate_control(control: dict) -> dict:
    text = control["job_text"]
    job_profile = parse_job_description(text)
    reqs = job_profile.requirements
    golds = control["gold_requirements"]
    cover = {i: [g["gid"] for g in golds if _covers(r, g, text)] for i, r in enumerate(reqs)}
    out = {"rows": [], "candidates": {}}
    for i, r in enumerate(reqs):
        eligible, reason = requirement_eligibility(r)
        out["rows"].append({
            "members": list(requirement_members(r)), "category": r.category, "necessity": r.necessity.value,
            "observability": r.github_observability.name, "covers_gold": cover[i],
            "span_exact": r.source_span is None or text[r.source_span.start:r.source_span.end] == r.original_text,
            "capabilities": {m: concept_capability(m)[0] for m in requirement_members(r)},
            "eligible_declared": eligible, "eligibility_reason": reason,
            "eligible_oracle": requirement_eligibility(r, language_vocabulary=ORACLE_LANGUAGE_VOCABULARY)[0],
        })
    for cand in control["candidates"]:
        analysis = match_job(candidate_profile(cand["evidence"]), job_profile)
        assessment = assess_job(analysis)
        matches = analysis.requirement_matches
        # G18 controls carry their frozen contract (tests pin it == the rule).
        # G15 controls carry G15's own expectation format, so the G18 rule
        # is applied to their unchanged frozen gold FACTS instead.
        if "expected_scores" in control:
            expected, exp_scores = control["expected"][cand["name"]], control["expected_scores"][cand["name"]]
        else:
            expected = {g["gid"]: builder.expected_contract(g, cand) for g in golds}
            exp_scores = builder.expected_scores(golds, cand)
        cand_out = {"production_status": [m.status.value for m in matches],
                    "matched_concept_ids": [list(m.matched_concept_ids) for m in matches],
                    "expected": expected,
                    "expected_scores": exp_scores,
                    "policies": {}}
        for policy in POLICIES:
            rows = [policy_row(policy, m) for m in matches]
            sc = score_rows(rows)
            # Fidelity check against the REAL assessor: policy A under scoring v1;
            # under scoring v2 (M11-G19 implemented C_capability_declared) the real
            # assessor must equal the simulated C. Simulation output is unchanged.
            if policy == ("A_production" if SCORING_VERSION.endswith(":v1") else "C_capability_declared"):
                assert sc["score"] == assessment.alignment_score and sc["eligible"] == assessment.assessable_count
            per_gold = {}
            for g in golds:
                idx = [i for i in cover if g["gid"] in cover[i]]
                counted = [i for i in idx if rows[i]["counted"]]
                per_gold[g["gid"]] = {
                    "rows": idx,
                    "represented": bool(idx),
                    "counted_rows": counted,
                    "counted_statuses": [rows[i]["status"] for i in counted],
                    "visible_statuses": [rows[i]["status"] for i in idx],
                    "positive_visible": any(rows[i]["status"] == SUPPORTED and rows[i]["diagnostic_retained"]
                                            for i in idx),
                    "merged_with_other_gold": any(len(cover[i]) > 1 for i in counted),
                }
            orphans = [i for i in cover if not cover[i] and rows[i]["counted"]]
            cand_out["policies"][policy] = {**sc, "per_gold": per_gold, "counted_rows": [i for i, r in enumerate(rows)
                                                                                         if r["counted"]],
                                            "orphan_counted_rows": orphans,
                                            "orphan_counted_statuses": [rows[i]["status"] for i in orphans]}
        out["candidates"][cand["name"]] = cand_out
    return out


def metrics(controls: list[dict], results: dict) -> dict:
    out = {}
    for policy in POLICIES:
        m = {k: [] for k in (
            "1_false_not_observed_counted", "2_false_not_observed_where_truly_qualified",
            "3_uncheckable_counted_in_denominator", "4_positive_evidence_credited_in_score",
            "4b_positive_evidence_visible_in_diagnostics", "5_over_exclusion_vs_ideal_contract",
            "5b_over_exclusion_vs_declared_contract", "6_false_supported_counted", "7_duplicate_or_merged_counting",
            "10_necessity_differs_on_counted_row", "11_non_requirement_counted", "12_orphan_rows_counted",
            "13_score_equals_declared_contract", "14_score_equals_ideal_contract", "unrepresented_gold")}
        positives = 0
        cand_dependent = []
        for c in controls:
            res = results[c["id"]]
            sets = set()
            for cand in c["candidates"]:
                p = res["candidates"][cand["name"]]["policies"][policy]
                sets.add(tuple(p["counted_rows"]))
                exp_scores = res["candidates"][cand["name"]]["expected_scores"]
                key = f"{c['id']}/{cand['name']}"
                if (p["score"], p["supported"], p["eligible"]) == tuple(exp_scores["declared"][k] for k in
                                                                         ("score", "supported", "eligible")):
                    m["13_score_equals_declared_contract"].append(key)
                if (p["score"], p["supported"], p["eligible"]) == tuple(exp_scores["ideal"][k] for k in
                                                                         ("score", "supported", "eligible")):
                    m["14_score_equals_ideal_contract"].append(key)
                if p["orphan_counted_rows"]:
                    m["12_orphan_rows_counted"].append(f"{key}:{p['orphan_counted_statuses']}")
                for g in c["gold_requirements"]:
                    e = res["candidates"][cand["name"]]["expected"][g["gid"]]
                    pg = p["per_gold"][g["gid"]]
                    gk = f"{key}/{g['gid']}"
                    if not pg["represented"]:
                        m["unrepresented_gold"].append(gk)
                    if e["category"] in _NOT_SCOREABLE_CATEGORIES and NOT_OBSERVED in pg["counted_statuses"]:
                        m["1_false_not_observed_counted"].append(gk)
                        if e["truth_satisfied"]:
                            m["2_false_not_observed_where_truly_qualified"].append(gk)
                    if not e["eligible_ideal"] and pg["counted_rows"]:
                        m["3_uncheckable_counted_in_denominator"].append(gk)
                    if e["positive_evidence_observed"]:
                        positives += 1
                        if SUPPORTED in pg["counted_statuses"]:
                            m["4_positive_evidence_credited_in_score"].append(gk)
                        if pg["positive_visible"]:
                            m["4b_positive_evidence_visible_in_diagnostics"].append(gk)
                    if e["eligible_ideal"] and pg["represented"] and not pg["counted_rows"]:
                        m["5_over_exclusion_vs_ideal_contract"].append(gk)
                    if e["eligible_declared"] and pg["represented"] and not pg["counted_rows"]:
                        m["5b_over_exclusion_vs_declared_contract"].append(gk)
                    if SUPPORTED in pg["counted_statuses"] and e["category"] != "satisfied_by_observed_evidence":
                        m["6_false_supported_counted"].append(gk)
                    if len(pg["counted_rows"]) > 1 or pg["merged_with_other_gold"]:
                        m["7_duplicate_or_merged_counting"].append(gk)
                    if pg["counted_rows"] and e["necessity"] != "unknown":
                        rows = res["rows"]
                        if any(rows[i]["necessity"] != e["necessity"] for i in pg["counted_rows"]):
                            m["10_necessity_differs_on_counted_row"].append(gk)
                    if e["category"] == "not_a_requirement" and pg["counted_rows"]:
                        m["11_non_requirement_counted"].append(gk)
            if len(sets) > 1:
                cand_dependent.append(c["id"])
        n_out = sum(len(c["candidates"]) * len(c["gold_requirements"]) for c in controls)
        n_pairs = sum(len(c["candidates"]) for c in controls)
        out[policy] = {k: {"count": len(v), "ids": v} for k, v in m.items()}
        out[policy]["8_controls_with_candidate_dependent_eligible_set"] = {"count": len(cand_dependent),
                                                                           "ids": cand_dependent}
        out[policy]["denominators"] = {"outcomes": n_out, "candidate_pairs": n_pairs, "controls": len(controls),
                                       "positive_evidence_outcomes": positives}
    return out


def run_corpus(controls: list[dict]) -> dict:
    results = {c["id"]: evaluate_control(c) for c in controls}
    return {"results": results, "metrics": metrics(controls, results)}


def b_equals_c_declared(results: dict) -> bool:
    for res in results.values():
        for cand in res["candidates"].values():
            if cand["policies"]["B_prefix_exclusion"]["counted_rows"] != \
                    cand["policies"]["C_capability_declared"]["counted_rows"]:
                return False
    return True


def registry_capability_table(registry=None) -> dict:
    registry = registry or default_registry()
    return {c.concept_id: dict(zip(("capability", "reasons"), concept_capability(c.concept_id, registry)))
            for c in registry.all_concepts()}
