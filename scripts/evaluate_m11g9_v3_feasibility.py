"""Milestone 11-G9 Phase 4 -- v2 vs v3 fair evaluation on the SEALED holdout.

Evaluation-only. Verifies the holdout's frozen hash BEFORE reading it
(hard failure, not a warning, on mismatch) -- this corpus must never be
tuned against, and this script is the ONLY place v3 is ever run against
it, exactly once, after the prototype (Phase 3) was already finished.

Produces `evaluation/reports/m11g9_phase4_v2_vs_v3.json`.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "evaluation_lib"))

HOLDOUT = REPO_ROOT / "evaluation" / "m11g9" / "holdout_annotations.json"
FREEZE = REPO_ROOT / "evaluation" / "m11g9" / "gold_hash_freeze.json"

# Maps a Phase-1-annotated `out_of_ontology_concept_slug` to the v3 new-
# concept tag it corresponds to, IF v3's bounded (3-concept) expansion
# actually covers it. Slugs not listed here name a genuine ontology gap
# this prototype does NOT attempt to close (single-posting evidence or
# otherwise out of this milestone's bounded scope -- see Phase 2 of the
# milestone doc) and are excluded from denominator B entirely, not
# silently counted as a v3 miss.
SLUG_TO_V3_NEW_TAG: dict[str, str] = {
    "generative-ai-agentic-systems": "generative-ai-agentic-systems",
    "llm-agentic-coding-adoption": "generative-ai-agentic-systems",
    "data-engineering-etl-pipelines": "data-engineering-pipelines",
    "cloud-infrastructure-devops-iac": "cloud-infrastructure-devops",
}

ORIGINAL_17_TAGS = frozenset({
    "algorithms-data-structures", "concurrency", "distributed-systems", "system-design",
    "performance-optimization", "os-networking", "database-design", "ml-fundamentals",
    "gpu-parallel-computing", "signal-processing", "circuit-theory", "embedded-systems-design",
    "control-systems", "computer-vision", "cybersecurity-threat-modeling", "digital-logic",
    "quantum-computing",
})


def _verify_frozen() -> None:
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    actual = HOLDOUT.read_bytes()
    actual_hash = hashlib.sha256(actual).hexdigest()
    if actual_hash != freeze["sha256"]:
        raise SystemExit(
            f"FATAL: holdout gold has changed since freeze ({freeze['sha256']} -> {actual_hash}). "
            "Refusing to evaluate against a possibly-tuned-against corpus."
        )


def _run_extractor(extractor_name: str, text: str):
    from gitscore.jobs.models import SourceSpan

    span = SourceSpan(0, len(text))
    if extractor_name == "v2":
        from gitscore.jobs.parsing.competency_extraction import extract_competency_qualifications_v2
        return extract_competency_qualifications_v2(text, span)
    from m11g9_competency_extraction_v3 import extract_competency_qualifications_v3
    return extract_competency_qualifications_v3(text, span)


def _predicted_tags(result) -> list[str]:
    if isinstance(result, tuple):
        return [
            q.normalized_reference.competency_tag
            for q in result
            if q.normalized_reference is not None and q.normalized_reference.competency_tag is not None
        ]
    return []


def _predicted_necessity(result) -> str | None:
    if isinstance(result, tuple) and result:
        n = result[0].necessity
        return n.value.upper() if n is not None else None
    return None


def evaluate(gold_path: Path, corpus_label: str, *, verify_seal: bool) -> dict:
    if verify_seal:
        _verify_frozen()
    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    controls = gold["controls"]

    report = {
        "corpus": corpus_label,
        "n_controls_total": len(controls),
        "extractors": {},
    }

    for extractor_name in ("v2", "v3"):
        qual_controls = [c for c in controls if c["text_category"] == "technical_competency"]
        n_qual = len(qual_controls)

        # --- Qualification-level recall/precision (did it produce ANY
        # technical_competency Qualification where one was expected, and
        # did it correctly DECLINE where one was not expected?) ---
        n_recognized = 0  # produced >=1 Qualification for a genuine technical_competency control
        n_declined_when_expected = 0

        # --- Tag-level recall (ALL emitted tags count in the denominator,
        # per the brief's explicit instruction) ---
        tag_tp = 0
        tag_fn = 0
        tag_fp_rows = []  # any EMITTED tag not equal to the expected tag (or expected is None/multi)

        # Split A (existing 17-tag denominator) vs B (expanded, includes out_of_ontology)
        n_taggable_A = 0
        n_correct_A = 0
        n_taggable_B_new_concepts = 0
        n_correct_B_new_concepts = 0

        necessity_correct = 0
        necessity_total = 0
        necessity_unresolved_no_section_context = 0

        rows = []
        for c in qual_controls:
            result = _run_extractor(extractor_name, c["text"])
            predicted_tags = _predicted_tags(result)
            expected_tag = c.get("expected_competency_tag")
            relation = c.get("expected_match_relation")
            slug = c.get("out_of_ontology_concept_slug")
            v3_covered_new_tag = SLUG_TO_V3_NEW_TAG.get(slug) if relation == "out_of_ontology" else None

            produced_any = len(predicted_tags) > 0
            if produced_any:
                n_recognized += 1
            else:
                n_declined_when_expected += 1

            # Tag-level scoring: every EMITTED tag is a denominator entry.
            if expected_tag is not None:
                if expected_tag in ORIGINAL_17_TAGS:
                    n_taggable_A += 1
                    if expected_tag in predicted_tags:
                        n_correct_A += 1
                if expected_tag in predicted_tags:
                    tag_tp += 1
                else:
                    tag_fn += 1
            if v3_covered_new_tag is not None:
                n_taggable_B_new_concepts += 1
                if v3_covered_new_tag in predicted_tags:
                    n_correct_B_new_concepts += 1

            for pt in predicted_tags:
                if pt != expected_tag and pt != v3_covered_new_tag:
                    tag_fp_rows.append({"id": c["id"], "predicted": pt, "expected": expected_tag})

            if produced_any and c.get("necessity") is not None:
                predicted_necessity = _predicted_necessity(result)
                necessity_total += 1
                if predicted_necessity is None:
                    # No section context passed to this sentence-level
                    # harness call (mirrors M11-F/M11-G5's own established
                    # direct-call convention) -- infer_necessity(text, None)
                    # correctly returns an UNRESOLVED (not wrong) necessity
                    # absent a local marker or section hint. Not scored as
                    # a mismatch; tracked separately so the limitation is
                    # visible rather than silently folded into "accuracy".
                    necessity_unresolved_no_section_context += 1
                elif predicted_necessity == c["necessity"]:
                    necessity_correct += 1

            rows.append({
                "id": c["id"], "expected_tag": expected_tag, "relation": relation,
                "predicted_tags": predicted_tags, "declined": not produced_any,
            })

        # --- Precision/safety: non-technical_competency controls must
        # NEVER produce a technical_competency Qualification (false
        # positive on responsibility/narrative/education/named_technology/
        # nontechnical/ambiguous controls). ---
        non_qual_controls = [c for c in controls if c["text_category"] != "technical_competency"]
        false_positive_rows = []
        for c in non_qual_controls:
            result = _run_extractor(extractor_name, c["text"])
            predicted_tags = _predicted_tags(result)
            if predicted_tags:
                false_positive_rows.append({
                    "id": c["id"], "text_category": c["text_category"], "predicted_tags": predicted_tags,
                })

        report["extractors"][extractor_name] = {
            "n_technical_competency_controls": n_qual,
            "n_recognized_any_tag": n_recognized,
            "n_declined_when_technical_competency_expected": n_declined_when_expected,
            "tag_level": {
                "tp": tag_tp,
                "fn": tag_fn,
                "fp_count": len(tag_fp_rows),
                "fp_rows": tag_fp_rows,
            },
            "denominator_A_original_17_tags": {
                "n_taggable": n_taggable_A,
                "n_correct": n_correct_A,
                "recall": round(n_correct_A / n_taggable_A, 4) if n_taggable_A else None,
            },
            "denominator_B_new_concepts_only": {
                "n_taggable": n_taggable_B_new_concepts,
                "n_correct": n_correct_B_new_concepts,
                "recall": round(n_correct_B_new_concepts / n_taggable_B_new_concepts, 4) if n_taggable_B_new_concepts else None,
            },
            "necessity_accuracy": {
                "correct": necessity_correct,
                "total": necessity_total,
                "unresolved_no_section_context": necessity_unresolved_no_section_context,
                "accuracy_among_resolved": (
                    round(necessity_correct / (necessity_total - necessity_unresolved_no_section_context), 4)
                    if (necessity_total - necessity_unresolved_no_section_context) else None
                ),
            },
            "false_positive_safety": {
                "n_non_technical_competency_controls_checked": len(non_qual_controls),
                "n_false_positives": len(false_positive_rows),
                "rows": false_positive_rows,
            },
            "rows": rows,
        }

    return report


def _print_report(report: dict) -> None:
    for name, data in report["extractors"].items():
        print(f"--- {report['corpus']} / {name} ---")
        print(f"  recognized {data['n_recognized_any_tag']}/{data['n_technical_competency_controls']} technical_competency controls")
        print(f"  tag-level TP={data['tag_level']['tp']} FN={data['tag_level']['fn']} FP={data['tag_level']['fp_count']}")
        print(f"  denom A (17-tag) recall: {data['denominator_A_original_17_tags']}")
        print(f"  denom B (new concepts) recall: {data['denominator_B_new_concepts_only']}")
        print(f"  necessity: {data['necessity_accuracy']}")
        print(f"  false positives on non-qualification controls: {data['false_positive_safety']['n_false_positives']}")


def main() -> None:
    reports_dir = REPO_ROOT / "evaluation" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    dev_path = REPO_ROOT / "evaluation" / "m11g9" / "dev_annotations.json"
    dev_report = evaluate(dev_path, "m11g9-dev (DIAGNOSTIC ONLY -- never used for the Phase 5 decision)", verify_seal=False)
    (reports_dir / "m11g9_phase4_v2_vs_v3_DEV_DIAGNOSTIC.json").write_text(json.dumps(dev_report, indent=2), encoding="utf-8")
    _print_report(dev_report)

    holdout_report = evaluate(HOLDOUT, "m11g9-holdout", verify_seal=True)
    out_path = reports_dir / "m11g9_phase4_v2_vs_v3.json"
    out_path.write_text(json.dumps(holdout_report, indent=2), encoding="utf-8")
    _print_report(holdout_report)
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
