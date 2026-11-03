"""Milestone 11-D -- independent holdout validation of the M11-C offline
competency extractor.

Evaluation-only, additive, read-only against production code. Runs the
REAL, UNMODIFIED `extract_competency_qualifications()` (M11-C) against
`evaluation/m11d/holdout_annotations.json` -- 165 independently
annotated claims drawn from 12 authentic, hash-frozen job postings
(`evaluation/m11d/provenance.json`), annotated BEFORE this script was
written or run. No algorithm modification. Reports exact numerator/
denominator counts for every Phase 3 metric, broken down by domain,
and runs the Phase 5 observability-safety check against the REAL
matcher.

Writes `evaluation/reports/m11d_generalization_validation_report.json`.

**Publication safety.** `evaluation/m11d/holdout_annotations.json` (the
full annotation file this script reads) and `evaluation/m11d/source/*.txt`
are retained LOCAL-ONLY and are not committed to this public repository:
both substantially reproduce third-party employers' job-posting text,
and republication rights for that text have not been confirmed. This
script only ever runs against the local, un-published annotation file
-- a maintainer with that file present can reproduce every number in
this report exactly (verified against the frozen hash recorded in
`evaluation/m11d/holdout_annotations_metadata.json`, the published,
text-redacted derivative); this script's own JSON output never embeds
verbatim claim text, only an `id` plus a `text_length_chars`/
`text_sha256` pair, so re-running it never accidentally republishes
posting content even though the report itself IS committed.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from gitscore.evidence.profile import build_candidate_evidence_profile  # noqa: E402
from gitscore.jobs.models import SourceSpan  # noqa: E402
from gitscore.jobs.parsing.competency_extraction import DeclinedExtraction, extract_competency_qualifications  # noqa: E402
from gitscore.jobs.parsing.qualification import project_qualification  # noqa: E402
from gitscore.matching.engine import match_requirement  # noqa: E402
from gitscore.matching.types import MatchStatus  # noqa: E402

ANNOTATIONS_PATH = REPO_ROOT / "evaluation" / "m11d" / "holdout_annotations.json"
PROVENANCE_PATH = REPO_ROOT / "evaluation" / "m11d" / "provenance.json"
REPORT_PATH = REPO_ROOT / "evaluation" / "reports" / "m11d_generalization_validation_report.json"

_EMPTY_PROFILE = build_candidate_evidence_profile("m11d-harness", [], [], [])


def _text_fingerprint(text: str) -> dict:
    """Never embed verbatim third-party posting text in this script's
    own output -- a length+hash pair is enough to verify, against a
    LOCAL copy of the unpublished annotation file, which exact claim a
    mismatch refers to, without this committed report reproducing any
    of that claim's own copyrighted text."""
    return {"text_length_chars": len(text), "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}


def main() -> None:
    claims = json.loads(ANNOTATIONS_PATH.read_text(encoding="utf-8"))["claims"]
    provenance = json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))
    domain_by_posting = {p["id"]: p["domain"] for p in provenance["postings"]}

    tp = fn = 0
    fp_responsibility = fp_narrative = fp_other_nonqual = 0
    necessity_total = necessity_correct = 0
    logical_total = logical_correct = 0
    missing_contract_declines = 0
    vocabulary_gap_total = vocabulary_gap_correctly_declined = 0
    span_total = span_correct = 0
    safety_checks = 0
    never_supported = True
    never_falsely_assessable = True
    by_domain: dict[str, dict] = {}
    mismatches: list[dict] = []

    def _domain_bucket(posting_id: str) -> dict:
        domain = domain_by_posting.get(posting_id, "unknown")
        return by_domain.setdefault(domain, {"tp": 0, "fn": 0, "fp": 0, "total_competency": 0})

    for claim in claims:
        text = claim["text"]
        span = SourceSpan(0, len(text))
        result = extract_competency_qualifications(text, span)
        predicted_positive = not isinstance(result, DeclinedExtraction)
        gt_category = claim["text_category"]
        gt_is_qual = claim["is_applicant_qualification"]
        is_gap_claim = bool(claim.get("new_vocabulary_gap"))
        bucket = _domain_bucket(claim["posting_id"])

        if gt_category == "technical_competency":
            bucket["total_competency"] += 1
            if is_gap_claim:
                vocabulary_gap_total += 1
            if predicted_positive:
                tp += 1
                bucket["tp"] += 1
                if is_gap_claim:
                    # The extractor recognized a term we marked as a
                    # vocabulary gap -- means our gap prediction was
                    # wrong (its pattern happened to overlap an existing
                    # tag's own regex); recorded, not hidden.
                    mismatches.append({"id": claim["id"], "error": "vocabulary_gap_unexpectedly_recognized", **_text_fingerprint(text)})
            elif isinstance(result, DeclinedExtraction) and result.reason == "missing_contract":
                missing_contract_declines += 1
                fn += 1
                bucket["fn"] += 1
            else:
                fn += 1
                bucket["fn"] += 1
                if is_gap_claim:
                    vocabulary_gap_correctly_declined += 1
        elif not gt_is_qual and gt_category == "responsibility":
            if predicted_positive:
                fp_responsibility += 1
                bucket["fp"] += 1
                mismatches.append({"id": claim["id"], "error": "false_positive_responsibility", **_text_fingerprint(text)})
        elif not gt_is_qual and gt_category == "company_narrative":
            if predicted_positive:
                fp_narrative += 1
                bucket["fp"] += 1
                mismatches.append({"id": claim["id"], "error": "false_positive_company_narrative", **_text_fingerprint(text)})
        elif not gt_is_qual:
            if predicted_positive:
                fp_other_nonqual += 1
                bucket["fp"] += 1
                mismatches.append({"id": claim["id"], "error": f"false_positive_{gt_category}", **_text_fingerprint(text)})
        else:
            # A genuine qualification of a DIFFERENT kind (named_technology,
            # education, experience, nontechnical, ambiguous) -- the
            # competency extractor must never fire here either.
            if predicted_positive:
                fp_other_nonqual += 1
                mismatches.append({"id": claim["id"], "error": f"false_positive_baseline_{gt_category}", **_text_fingerprint(text)})

        if predicted_positive:
            for qualification in result:
                span_total += 1
                if qualification.source_text == text and qualification.source_span is span:
                    span_correct += 1
                else:
                    mismatches.append({"id": claim["id"], "error": "span_or_text_mismatch"})

                gt_necessity = claim.get("necessity")
                if gt_necessity is not None and qualification.necessity is not None:
                    necessity_total += 1
                    if qualification.necessity.value.upper() == gt_necessity:
                        necessity_correct += 1
                    else:
                        mismatches.append({"id": claim["id"], "error": "necessity_mismatch", "expected": gt_necessity, "actual": qualification.necessity.value})

                gt_logical = claim.get("logical_composition")
                if gt_logical is not None:
                    logical_total += 1
                    if qualification.logical_composition.value == gt_logical:
                        logical_correct += 1
                    else:
                        mismatches.append({"id": claim["id"], "error": "logical_composition_mismatch", "expected": gt_logical, "actual": qualification.logical_composition.value})

                projection = project_qualification(qualification)
                if projection.job_requirement is not None:
                    safety_checks += 1
                    match = match_requirement(projection.job_requirement, _EMPTY_PROFILE)
                    if match.status == MatchStatus.SUPPORTED:
                        never_supported = False
                        mismatches.append({"id": claim["id"], "error": "UNEXPECTED_SUPPORTED_WITH_EMPTY_EVIDENCE"})
                    if not projection.job_requirement.is_technical and match.status != MatchStatus.NOT_ASSESSABLE:
                        never_falsely_assessable = False
                        mismatches.append({"id": claim["id"], "error": "COMPETENCY_WITHOUT_CONCEPT_MAPPING_WAS_ASSESSABLE"})

    report = {
        "publication_note": (
            "Mismatch entries are fingerprinted (text_length_chars/text_sha256), never verbatim -- "
            "see this script's own module docstring. Aggregate counts and domain breakdowns below are complete."
        ),
        "corpus": {"postings": len(provenance["postings"]), "claims": len(claims)},
        "qualification_recall_technical_competency": {"numerator": tp, "denominator": tp + fn},
        "qualification_precision_technical_competency": {
            "numerator": tp,
            "denominator": tp + fp_responsibility + fp_narrative + fp_other_nonqual,
        },
        "false_positives": {
            "from_responsibilities": fp_responsibility,
            "from_company_narratives": fp_narrative,
            "from_other_non_qualification_or_different_kind": fp_other_nonqual,
        },
        "necessity_classification": {"numerator": necessity_correct, "denominator": necessity_total},
        "logical_grouping": {"numerator": logical_correct, "denominator": logical_total},
        "missing_contract_declines": missing_contract_declines,
        "vocabulary_coverage_gap": {
            "total_new_vocabulary_claims": vocabulary_gap_total,
            "correctly_declined_as_no_competency_language": vocabulary_gap_correctly_declined,
            "unexpectedly_recognized_anyway": sum(
                1 for m in mismatches if m.get("error") == "vocabulary_gap_unexpectedly_recognized"
            ),
        },
        "source_span_exactness": {"numerator": span_correct, "denominator": span_total},
        "scoring_safety": {
            "safety_checks_run": safety_checks,
            "never_supported_with_empty_evidence": never_supported,
            "never_falsely_assessable_without_concept_mapping": never_falsely_assessable,
        },
        "by_domain": by_domain,
        "mismatches": mismatches,
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    print(f"Corpus: {report['corpus']['postings']} postings, {report['corpus']['claims']} claims")
    r = report["qualification_recall_technical_competency"]
    p = report["qualification_precision_technical_competency"]
    print(f"TECHNICAL_COMPETENCY recall:    {r['numerator']}/{r['denominator']}")
    print(f"TECHNICAL_COMPETENCY precision: {p['numerator']}/{p['denominator']}")
    print(f"False positives: {report['false_positives']}")
    print(f"Necessity classification: {necessity_correct}/{necessity_total}")
    print(f"Logical grouping: {logical_correct}/{logical_total}")
    print(f"Missing-contract declines: {missing_contract_declines}")
    print(f"Vocabulary coverage gap: {report['vocabulary_coverage_gap']}")
    print(f"Source span exactness: {span_correct}/{span_total}")
    print(f"Scoring safety: {report['scoring_safety']}")
    print("\nBy domain:")
    for domain, stats in sorted(by_domain.items()):
        print(f"  {domain}: tp={stats['tp']} fn={stats['fn']} fp={stats['fp']} total_competency={stats['total_competency']}")
    print(f"\nTotal mismatches/findings: {len(mismatches)}")
    print(f"Wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
