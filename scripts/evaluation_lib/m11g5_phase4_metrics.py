"""Milestone 11-G5 Phase 4 -- aggregate metrics over the frozen,
independently-annotated M11-G5 corpus.

Evaluation-only. Imports no new production code; writes no production
code; never mutates gold or source after the hash-freeze point. Reads
`evaluation/m11g5/holdout_annotations.json` and
`evaluation/m11g5/source/*.txt` (both local-only, never staged) and
re-runs the Phase 1 `run_dual_path()` harness directly (not the
flattened `phase4_raw_execution.json`) so that Category C/D metrics
needing fields the flat file does not carry (logical_composition,
applicability_condition, section_kind, decline reason, exact-span
bounds) are computed from the real objects, not re-derived.

Writes `evaluation/reports/m11g5_phase4_metrics.json` -- a
publication-safe aggregate (no verbatim posting text, no verbatim gold
text; only ids, counts, and short structural labels already present in
the redacted `holdout_annotations_metadata.json` schema).
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "evaluation_lib"))

from gitscore.jobs.parsing.competency_extraction import DeclinedExtraction  # noqa: E402
from m11g5_dual_path_comparison import run_dual_path  # noqa: E402
from m11g5_phase4_run_comparison import find_span, load_posting_body, spans_overlap  # noqa: E402

GOLD_PATH = REPO_ROOT / "evaluation" / "m11g5" / "holdout_annotations.json"
PROVENANCE_PATH = REPO_ROOT / "evaluation" / "m11g5" / "provenance.json"
OUT_PATH = REPO_ROOT / "evaluation" / "reports" / "m11g5_phase4_metrics.json"


def main() -> None:
    gold = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    provenance = json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))
    posting_meta = {p["id"]: p for p in provenance["postings"]}

    controls_by_posting: dict[str, list[dict]] = defaultdict(list)
    for c in gold["controls"]:
        controls_by_posting[c["posting"]].append(c)

    rows: list[dict] = []
    unmatched: list[str] = []

    for posting_id, controls in controls_by_posting.items():
        meta = posting_meta[posting_id]
        company, role, body = load_posting_body(posting_id)
        result = run_dual_path(body, title=role, company=company)
        comparisons = result["comparisons"]
        profile = result["profile"]
        unparsed_claims = result["unparsed_claims"]

        a_req = [(r.source_span.start, r.source_span.end, r) for r in profile.requirements]
        a_unparsed = [(u.source_span.start, u.source_span.end) for u in unparsed_claims]

        for control in controls:
            gold_span = find_span(body, control["text"])
            if gold_span is None:
                unmatched.append(control["id"])
                continue

            matching_a_reqs = [r for (s, e, r) in a_req if spans_overlap(gold_span, (s, e))]
            a_unparsed_hit = any(spans_overlap(gold_span, s) for s in a_unparsed)

            matched = [c for c in comparisons if spans_overlap(gold_span, c.span)]

            b_found_competency = False
            b_has_job_requirement = False
            b_relationship = None
            b_section_kinds: list[str | None] = []
            b_decline_reasons: list[str] = []
            b_quals: list[dict] = []  # one entry per produced Qualification

            for comp in matched:
                b_section_kinds.append(None)  # filled below via claim text match is not tracked on comp; use source flag instead
                if isinstance(comp.path_b_result, DeclinedExtraction):
                    b_decline_reasons.append(comp.path_b_result.reason)
                else:
                    b_found_competency = True
                    for q, proj in zip(comp.path_b_result, comp.path_b_projections):
                        ref = q.normalized_reference
                        tag = (ref.competency_tag or ref.concept_id) if ref is not None else None
                        b_quals.append({
                            "tag": tag,
                            "necessity": q.necessity.name if q.necessity is not None else None,
                            "logical_composition": q.logical_composition.value,
                            "applicability_condition": q.applicability_condition,
                            "span_exact": (q.source_span.start, q.source_span.end) == comp.span,
                        })
                        if proj.job_requirement is not None:
                            b_has_job_requirement = True
                b_relationship = comp.relationship

            rows.append({
                "id": control["id"],
                "posting": posting_id,
                "domain": control["domain"],
                "is_applicant_qualification": control["is_applicant_qualification"],
                "qualification_kind": control.get("qualification_kind"),
                "expected_competency_tag": control.get("expected_competency_tag"),
                "sibling_tags": control.get("sibling_tags", []),
                "expected_match_relation": control.get("expected_match_relation"),
                "expected_necessity": control.get("necessity"),
                "expected_logical_composition": control.get("logical_composition"),
                "expected_applicability_condition": control.get("applicability_condition"),
                "expected_conservative_projection": control.get("expected_conservative_projection"),
                "notes": control.get("notes"),
                "a_has_job_requirement": bool(matching_a_reqs),
                "a_has_unparsed": a_unparsed_hit,
                "a_necessities": sorted({str(r.necessity) for r in matching_a_reqs}),
                "b_found_competency": b_found_competency,
                "b_has_job_requirement": b_has_job_requirement,
                "b_relationship": b_relationship,
                "b_decline_reasons": b_decline_reasons,
                "b_quals": b_quals,
            })

    # ---- Category A: ALL genuine applicant qualifications ----
    positives = [r for r in rows if r["is_applicant_qualification"]]
    negatives = [r for r in rows if not r["is_applicant_qualification"]]

    def admitted_a(r: dict) -> bool:
        return r["a_has_job_requirement"] or r["a_has_unparsed"]

    def admitted_candidate(r: dict) -> bool:
        return admitted_a(r) or r["b_relationship"] == "path_b_only_recovered"

    a_tp = sum(1 for r in positives if admitted_a(r))
    a_fn = len(positives) - a_tp
    cand_tp = sum(1 for r in positives if admitted_candidate(r))
    cand_fn = len(positives) - cand_tp

    a_false_req = sum(1 for r in negatives if r["a_has_job_requirement"])
    cand_false_req = sum(1 for r in negatives if r["a_has_job_requirement"] or r["b_has_job_requirement"])

    by_kind_a: dict[str, dict] = {}
    by_kind_cand: dict[str, dict] = {}
    for kind in sorted({r["qualification_kind"] for r in positives if r["qualification_kind"]}):
        subset = [r for r in positives if r["qualification_kind"] == kind]
        by_kind_a[kind] = {
            "n": len(subset),
            "recognized": sum(1 for r in subset if admitted_a(r)),
        }
        by_kind_cand[kind] = {
            "n": len(subset),
            "recognized": sum(1 for r in subset if admitted_candidate(r)),
        }

    recovered_rows = [r for r in positives if r["b_relationship"] == "path_b_only_recovered"]

    category_a = {
        "n_positive_controls": len(positives),
        "n_negative_controls": len(negatives),
        "path_a": {
            "recognized_tp": a_tp,
            "missed_fn": a_fn,
            "recall": round(a_tp / len(positives), 4) if positives else None,
            "false_requirements_from_non_qualifications": a_false_req,
            "false_requirement_denominator": len(negatives),
        },
        "candidate": {
            "recognized_tp": cand_tp,
            "missed_fn": cand_fn,
            "recall": round(cand_tp / len(positives), 4) if positives else None,
            "false_requirements_from_non_qualifications": cand_false_req,
            "false_requirement_denominator": len(negatives),
            "recovered_only_count": len(recovered_rows),
            "recovered_only_ids": [r["id"] for r in recovered_rows],
        },
        "missed_by_category": {
            "path_a_recall_by_kind": by_kind_a,
            "candidate_recall_by_kind": by_kind_cand,
        },
        "path_a_missed_ids": [r["id"] for r in positives if not admitted_a(r)],
        "candidate_missed_ids": [r["id"] for r in positives if not admitted_candidate(r)],
    }

    # ---- Category B: technical competencies (tag level) ----
    tech = [r for r in rows if r["qualification_kind"] == "technical_competency"]
    taggable = [r for r in tech if r["expected_competency_tag"]]
    untaggable = [r for r in tech if not r["expected_competency_tag"]]

    tag_tp = 0
    tag_fn_ids = []
    for r in taggable:
        emitted = {q["tag"] for q in r["b_quals"] if q["tag"]}
        if r["expected_competency_tag"] in emitted:
            tag_tp += 1
        else:
            tag_fn_ids.append(r["id"])
    tag_fn = len(tag_fn_ids)

    total_emitted = 0
    correct_emitted = 0
    sibling_emitted = 0
    wrong_emitted = []
    untagged_vocab_hits = 0
    for r in tech:
        accepted = set()
        if r["expected_competency_tag"]:
            accepted.add(r["expected_competency_tag"])
        accepted.update(r.get("sibling_tags") or [])
        for q in r["b_quals"]:
            if q["tag"] is None:
                untagged_vocab_hits += 1
                continue
            total_emitted += 1
            if r["expected_competency_tag"] and q["tag"] == r["expected_competency_tag"]:
                correct_emitted += 1
            elif q["tag"] in accepted:
                sibling_emitted += 1
            else:
                wrong_emitted.append({"id": r["id"], "tag": q["tag"], "expected": r["expected_competency_tag"]})

    precision_denom = total_emitted
    precision_numer = correct_emitted + sibling_emitted
    tag_precision = round(precision_numer / precision_denom, 4) if precision_denom else None
    tag_recall = round(tag_tp / len(taggable), 4) if taggable else None

    untaggable_correctly_declined = sum(
        1 for r in untaggable if not any(q["tag"] for q in r["b_quals"])
    )
    untaggable_wrongly_tagged = len(untaggable) - untaggable_correctly_declined

    category_b = {
        "n_technical_competency_controls": len(tech),
        "n_taggable_expected_tag": len(taggable),
        "n_untaggable_expected_no_tag": len(untaggable),
        "tag_level_tp": tag_tp,
        "tag_level_fn": tag_fn,
        "tag_level_fn_ids": tag_fn_ids,
        "prediction_level": {
            "total_tag_predictions_emitted": total_emitted,
            "correct_primary_tag_emitted": correct_emitted,
            "accepted_sibling_tag_emitted": sibling_emitted,
            "incorrect_sibling_or_unrelated_tag_emitted": len(wrong_emitted),
            "incorrect_emissions": wrong_emitted,
            "precision": tag_precision,
            "precision_formula": "(correct_primary + accepted_sibling) / total_tag_predictions_emitted",
        },
        "recall": tag_recall,
        "untagged_vocabulary_hits_no_resolved_tag": untagged_vocab_hits,
        "untaggable_controls_correctly_declined": untaggable_correctly_declined,
        "untaggable_controls_wrongly_tagged": untaggable_wrongly_tagged,
    }

    # ---- Category C: semantic correctness ----
    necessity_checked = [r for r in tech if r["b_quals"] and r["expected_necessity"]]
    necessity_agree = sum(
        1 for r in necessity_checked
        if r["expected_necessity"] in {q["necessity"] for q in r["b_quals"] if q["necessity"]}
    )

    composition_checked = [r for r in tech if r["b_quals"] and r["expected_logical_composition"]]
    composition_agree = sum(
        1 for r in composition_checked
        if r["expected_logical_composition"] in {q["logical_composition"] for q in r["b_quals"]}
    )

    span_checked = [r for r in tech if r["b_quals"]]
    span_exact = sum(1 for r in span_checked if all(q["span_exact"] for q in r["b_quals"]))

    decline_reason_counts = Counter()
    for r in rows:
        for reason in r["b_decline_reasons"]:
            decline_reason_counts[reason] += 1

    domain_leak_traps = [r for r in rows if r["notes"] and "domain-leak" in r["notes"]]
    domain_leak_results = []
    for r in domain_leak_traps:
        domain_leak_results.append({
            "id": r["id"],
            "is_applicant_qualification": r["is_applicant_qualification"],
            "a_admitted_as_requirement": r["a_has_job_requirement"],
            "candidate_found_competency": r["b_found_competency"],
            "candidate_relationship": r["b_relationship"],
        })

    nonassessable_required = [
        r for r in rows
        if r["is_applicant_qualification"] and r["expected_necessity"] == "REQUIRED"
        and r.get("expected_conservative_projection") == "job_requirement"
    ]

    category_c = {
        "necessity_agreement": {
            "n_checked": len(necessity_checked),
            "n_agree": necessity_agree,
            "rate": round(necessity_agree / len(necessity_checked), 4) if necessity_checked else None,
        },
        "logical_composition_agreement": {
            "n_checked": len(composition_checked),
            "n_agree": composition_agree,
            "rate": round(composition_agree / len(composition_checked), 4) if composition_checked else None,
        },
        "exact_source_span_preservation": {
            "n_checked": len(span_checked),
            "n_exact": span_exact,
            "rate": round(span_exact / len(span_checked), 4) if span_checked else None,
        },
        "decline_reason_distribution": dict(decline_reason_counts),
        "domain_leak_trap_cases": domain_leak_results,
    }

    # ---- Category D: combined interpretation ----
    contradictory = [r for r in rows if r["b_relationship"] == "contradictory"]
    projection_losses = [
        r for r in rows if r["b_found_competency"] and not r["b_has_job_requirement"]
    ]

    category_d = {
        "unique_genuine_qualifications_recognized_by_candidate": cand_tp,
        "contradictory_relationship_count": len(contradictory),
        "contradictory_ids": [r["id"] for r in contradictory],
        "competency_found_but_projection_declined_count": len(projection_losses),
        "competency_found_but_projection_declined_ids": [r["id"] for r in projection_losses],
        "note_on_duplicate_outputs": (
            "Reconciliation operates on exact source spans; no two ClaimComparison rows "
            "ever share an identical span, so 'duplicate outputs' in this corpus means two "
            "DIFFERENT spans describing overlapping real-world skill content (e.g. the same "
            "technology list appearing once under a Responsibilities heading and once under "
            "Qualifications -- m11g5-p05-resp1/m11g5-p05-04). These are reported as distinct "
            "recognized claims, not merged, since merging across sections is out of scope for "
            "an evaluation-only harness and was never attempted."
        ),
    }

    out = {
        "corpus_version": gold["corpus_version"],
        "n_controls_total": len(gold["controls"]),
        "n_controls_matched_to_span": len(rows),
        "n_controls_unmatched": len(unmatched),
        "unmatched_ids": unmatched,
        "category_a_all_genuine_qualifications": category_a,
        "category_b_technical_competencies": category_b,
        "category_c_semantic_correctness": category_c,
        "category_d_combined_interpretation": category_d,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"wrote metrics to {OUT_PATH}")


if __name__ == "__main__":
    main()
