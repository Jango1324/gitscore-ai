"""Milestone 11-G22 -- concept-recognition evaluation harness (research only).

Runs the REAL production parser v14 (optionally under an `m11g22_policies` research
adapter), the real matcher and scoring v2, and measures concept identity per control:
false registered concepts, fabricated `unresolved:` concepts, missed / declined genuine
concepts, alias-equivalence and grouping errors, necessity, and score effects.
Nothing here is imported by `src/gitscore`.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (REPO_ROOT / "src", REPO_ROOT / "scripts", REPO_ROOT / "scripts" / "evaluation_lib"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import m11g22_policies as pol  # noqa: E402
from gitscore.assessment import assess_job  # noqa: E402
from gitscore.concepts.registry import is_unresolved_concept_id  # noqa: E402
from gitscore.jobs.parsing.parser import parse_job_description_with_diagnostics  # noqa: E402
from gitscore.jobs.parsing.qualification_intent import decide_qualification_intent  # noqa: E402
from gitscore.jobs.parsing.segmentation import segment_description  # noqa: E402
from gitscore.matching import match_job  # noqa: E402
from m11g15_or_scoring import candidate_profile  # noqa: E402

DATA = REPO_ROOT / "evaluation" / "m11g22"
PLACEHOLDERS = ("alternative_requirement", "unresolved_requirement")


def load_controls(split: str) -> list[dict]:
    return json.loads((DATA / f"concept_controls_{split}.json").read_text(encoding="utf-8"))["controls"]


def members(r) -> tuple[str, ...]:
    if r.alternative_concept_ids:
        return tuple(sorted(r.alternative_concept_ids))
    return (r.concept_id,) if r.concept_id else ()


def parse(text: str, policy: pol.Policy = pol.BASE):
    with pol.applied(policy):
        return parse_job_description_with_diagnostics(text)


def _score(parsed, evidence: list[str]) -> dict:
    a = assess_job(match_job(candidate_profile(sorted(set(evidence))), parsed.profile))
    rows = []
    for m in a.match_analysis.requirement_matches:
        reason = a.alignment_exclusion_reason(m)
        rows.append({"members": list(members(m.requirement)), "status": m.status.value,
                     "counts": a.counts_toward_alignment(m), "reason": None if reason is None else reason.value})
    return {"score": a.alignment_score, "denominator": a.assessable_count, "rows": rows}


def evaluate_control(c: dict, policy: pol.Policy = pol.BASE) -> dict:
    parsed = parse(c["text"], policy)
    rows = parsed.profile.requirements
    tech = [r for r in rows if members(r)]
    produced = Counter((members(r), r.necessity.value) for r in tech)
    expected = Counter((tuple(sorted(k["members"])), k["necessity"]) for k in c["expected_concepts"])
    p_ids = {i for r in tech for i in members(r)}
    e_ids = {i for k in c["expected_concepts"] for i in k["members"]}
    placeholder = any(r.category in PLACEHOLDERS for r in rows)
    declined = placeholder or bool(parsed.unparsed_claims)
    admission_declined = any(not decide_qualification_intent(cl.text, cl.section_kind).admit
                             for cl in segment_description(c["text"]))
    false_reg = sorted(i for i in p_ids - e_ids if not is_unresolved_concept_id(i))
    fabricated = sorted(i for i in p_ids - e_ids if is_unresolved_concept_id(i))
    out = {"id": c["id"], "family": c["family"], "pair": c["pair"], "qual": c["is_qualification"],
           "identity_only": c["identity_only"], "false_registered": false_reg, "fabricated_unresolved": fabricated,
           "produced": sorted([list(m), n] for (m, n) in produced.elements()),
           "placeholders": sorted(r.category for r in rows if r.category in PLACEHOLDERS),
           "unparsed_claims": len(parsed.unparsed_claims),
           "admission_declined": admission_declined}
    taxonomy: list[tuple[str, str]] = []
    for i in false_reg + fabricated:
        taxonomy.append(("F" if not c["is_qualification"] else ("A" if i in false_reg else "B"), i))
    missed_completely, missed_declined, grouping = [], [], []
    nec_ok = nec_n = 0
    if not c["identity_only"]:
        for i in sorted(e_ids - p_ids):
            (missed_declined if declined else missed_completely).append(i)
            group_member = any(len(k["members"]) > 1 and i in k["members"] for k in c["expected_concepts"])
            if c["family"] == "equivalent_alias":
                taxonomy.append(("D", i))
            elif group_member:
                taxonomy.append(("E", i))
            elif admission_declined:
                taxonomy.append(("F", i))
            else:
                taxonomy.append(("C", i))
        exp_sets = {tuple(sorted(k["members"])) for k in c["expected_concepts"]}
        prod_sets = {members(r) for r in tech}
        # an OR group expected but not produced exactly, or produced but not expected
        grouping = sorted(list(s) for s in exp_sets ^ prod_sets if len(s) > 1)
        if grouping and not any(t in ("D", "E") for t, _ in taxonomy):
            taxonomy.append(("E", "|".join(grouping[0])))
        for (m, n), cnt in expected.items():
            got = [pn for (pm, pn) in produced.elements() if pm == m]
            for k in range(cnt):
                if k < len(got):
                    nec_n += 1
                    nec_ok += got[k] == n
        if nec_n > nec_ok:
            taxonomy.append(("G", "necessity"))
    out.update({"missed_completely": missed_completely, "missed_declined": missed_declined, "grouping_errors": grouping,
                "necessity_correct": nec_ok, "necessity_scored": nec_n,
                "exact": (produced == expected) if not c["identity_only"] else None,
                "expected_ids": sorted(e_ids), "recalled_ids": sorted(e_ids & p_ids) if not c["identity_only"] else [],
                "taxonomy": [list(t) for t in taxonomy]})
    # score effects: a genuine candidate (exactly the true registry skills) and an adversarial one who
    # ALSO has evidence for every falsely recognised registry technology (e.g. really knows React).
    genuine = [i for i in e_ids if not is_unresolved_concept_id(i)]
    g = _score(parsed, genuine)
    adv = _score(parsed, genuine + false_reg)
    false_ids = set(false_reg) | set(fabricated)
    false_rows = [r for r in adv["rows"] if set(r["members"]) & false_ids]
    out["scoring"] = {
        "genuine": {"score": g["score"], "denominator": g["denominator"]},
        "adversarial": {"score": adv["score"], "denominator": adv["denominator"]},
        "false_rows_counted": sum(1 for r in false_rows if r["counts"]),
        "false_rows_excluded_v2": sum(1 for r in false_rows if not r["counts"] and r["status"] != "not_assessable"),
        "false_rows_not_assessable": sum(1 for r in false_rows if r["status"] == "not_assessable"),
        "false_supported_counted": sum(1 for r in false_rows if r["counts"] and r["status"] == "supported"),
    }
    return out


def aggregate(results: list[dict]) -> dict:
    full = [r for r in results if not r["identity_only"]]
    tax = Counter(t for r in results for t, _ in r["taxonomy"])
    e_total = sum(len(r["expected_ids"]) for r in full)
    e_hit = sum(len(r["recalled_ids"]) for r in full)
    reg_total = sum(1 for r in full for i in r["expected_ids"] if not is_unresolved_concept_id(i))
    reg_hit = sum(1 for r in full for i in r["recalled_ids"] if not is_unresolved_concept_id(i))
    return {
        "controls": len(results),
        "exact_controls": sum(1 for r in full if r["exact"]), "exact_scored": len(full),
        "false_registered": sum(len(r["false_registered"]) for r in results),
        "fabricated_unresolved": sum(len(r["fabricated_unresolved"]) for r in results),
        "false_in_nonqualification": sum(len(r["false_registered"]) + len(r["fabricated_unresolved"])
                                         for r in results if not r["qual"]),
        "concept_recall": [e_hit, e_total], "registry_concept_recall": [reg_hit, reg_total],
        "missed_completely": sum(len(r["missed_completely"]) for r in full),
        "missed_declined": sum(len(r["missed_declined"]) for r in full),
        "grouping_errors": sum(len(r["grouping_errors"]) for r in full),
        "necessity": [sum(r["necessity_correct"] for r in full), sum(r["necessity_scored"] for r in full)],
        "taxonomy": {k: tax.get(k, 0) for k in "ABCDEFG"},
        "false_rows_counted": sum(r["scoring"]["false_rows_counted"] for r in results),
        "false_rows_excluded_v2": sum(r["scoring"]["false_rows_excluded_v2"] for r in results),
        "false_rows_not_assessable": sum(r["scoring"]["false_rows_not_assessable"] for r in results),
        "false_supported_counted": sum(r["scoring"]["false_supported_counted"] for r in results),
        "pairs_both_exact": _pairs(results),
    }


def _pairs(results: list[dict]) -> list[int]:
    by_id = {r["id"]: r for r in results}
    seen, ok, n = set(), 0, 0
    for r in results:
        if not r["pair"] or r["pair"] not in by_id or frozenset((r["id"], r["pair"])) in seen:
            continue
        seen.add(frozenset((r["id"], r["pair"])))
        o = by_id[r["pair"]]
        n += 1
        ok += bool(r["exact"]) and bool(o["exact"])
    return [ok, n]


def run_split(split: str, policy: pol.Policy = pol.BASE) -> tuple[list[dict], dict]:
    results = [evaluate_control(c, policy) for c in load_controls(split)]
    return results, aggregate(results)
