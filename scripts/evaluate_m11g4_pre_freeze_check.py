"""Milestone 11-G4 -- PRE-FREEZE verification only. Runs the real
segment_description() + the new recover_unadmitted_qualification_claims()
+ extract_competency_qualifications_v2() + project_qualification() chain
against every control in evaluation/m11g4/admission_recovery_controls.json
and reports every mismatch in full detail, so corpus-authoring mistakes
can be found and fixed before the corpus is (re-)hash-frozen.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from gitscore.jobs.models import SourceSpan  # noqa: E402
from gitscore.jobs.parsing.competency_extraction import (  # noqa: E402
    DeclinedExtraction,
    extract_competency_qualifications_v2,
)
from gitscore.jobs.parsing.qualification import project_qualification  # noqa: E402
from gitscore.jobs.parsing.qualification_admission_recovery import (  # noqa: E402
    recover_unadmitted_qualification_claims,
)
from gitscore.jobs.parsing.segmentation import (  # noqa: E402
    document_has_any_recognized_heading,
    segment_description,
)

CORPUS_PATH = REPO_ROOT / "evaluation" / "m11g4" / "admission_recovery_controls.json"


def main() -> None:
    data = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    total = 0
    mismatches = []

    for posting in data["postings"]:
        description = posting["description"]
        admitted = segment_description(description)
        recovered = recover_unadmitted_qualification_claims(description)
        doc_heading = document_has_any_recognized_heading(description)

        by_text_admitted = {cl.text: cl for cl in admitted}
        by_text_recovered = {r.claim.text: r.claim for r in recovered}

        for control in posting["controls"]:
            total += 1
            target = control["target_text"]

            was_admitted = target in by_text_admitted
            was_recovered = target in by_text_recovered

            if was_admitted and was_recovered:
                mismatches.append({"posting": posting["id"], "target": target, "error": "DUPLICATE: claim both admitted AND recovered"})
                continue

            if control.get("expect_no_claim"):
                if was_admitted or was_recovered:
                    mismatches.append({"posting": posting["id"], "target": target, "error": "expected NO claim, but one was produced"})
                continue

            expect_admitted = control.get("currently_admitted", False)
            if expect_admitted != was_admitted:
                mismatches.append({
                    "posting": posting["id"], "target": target,
                    "error": f"expected currently_admitted={expect_admitted}, got {was_admitted}",
                })
                continue

            expect_recovered = control.get("expect_recovered", False)
            if expect_admitted:
                claim = by_text_admitted[target]
            elif expect_recovered:
                if not was_recovered:
                    mismatches.append({
                        "posting": posting["id"], "target": target,
                        "error": "expected recovery, but claim was NOT recovered",
                        "recovered_in_posting": sorted(by_text_recovered.keys()),
                    })
                    continue
                claim = by_text_recovered[target]
            else:
                mismatches.append({"posting": posting["id"], "target": target, "error": "control has neither currently_admitted nor expect_recovered set"})
                continue

            span = SourceSpan(claim.start, claim.end)
            result = extract_competency_qualifications_v2(
                claim.text, span, section_kind=claim.section_kind,
                document_has_recognized_heading=doc_heading, has_section_context=True,
            )
            is_decline = isinstance(result, DeclinedExtraction)
            expect_decline = control.get("expect_decline", False)

            if is_decline != expect_decline:
                mismatches.append({
                    "posting": posting["id"], "target": target,
                    "error": f"expect_decline={expect_decline} but got declined={is_decline}",
                    "actual_reason": result.reason if is_decline else None,
                    "actual_tags": None if is_decline else sorted(
                        q.normalized_reference.competency_tag for q in result if q.normalized_reference is not None
                    ),
                    "section_kind": claim.section_kind,
                })
                continue

            if is_decline:
                if result.reason != control.get("expect_reason"):
                    mismatches.append({
                        "posting": posting["id"], "target": target,
                        "error": f"expected decline reason {control.get('expect_reason')!r}, got {result.reason!r}",
                    })
                continue

            actual_tags = sorted(q.normalized_reference.competency_tag for q in result if q.normalized_reference is not None)
            expected_tags = sorted(([control["expect_tag"]] if control.get("expect_tag") else []) + control.get("expect_sibling_tags", []))
            if actual_tags != expected_tags:
                mismatches.append({"posting": posting["id"], "target": target, "error": f"expected tags {expected_tags}, got {actual_tags}", "section_kind": claim.section_kind})
                continue

            actual_necessity = result[0].necessity.value.upper() if result[0].necessity is not None else None
            if actual_necessity != control.get("expect_necessity"):
                mismatches.append({"posting": posting["id"], "target": target, "error": f"expected necessity {control.get('expect_necessity')!r}, got {actual_necessity!r}", "section_kind": claim.section_kind})
                continue

            actual_logic = result[0].logical_composition.value if len(result) == 1 else "and"
            if control.get("expect_logical_composition") and actual_logic != control["expect_logical_composition"]:
                mismatches.append({"posting": posting["id"], "target": target, "error": f"expected logical_composition {control['expect_logical_composition']!r}, got {actual_logic!r}"})
                continue

            expect_app = control.get("expect_applicability_present")
            if expect_app is not None:
                actual_app = any(q.applicability_condition is not None for q in result)
                if actual_app != expect_app:
                    mismatches.append({"posting": posting["id"], "target": target, "error": f"expected applicability_present={expect_app}, got {actual_app}"})
                    continue

            for q in result:
                proj = project_qualification(q)
                actual_projection = "job_requirement" if proj.job_requirement is not None else "unparsed_claim"
                if control.get("expect_projection") and actual_projection != control["expect_projection"]:
                    mismatches.append({
                        "posting": posting["id"], "target": target,
                        "error": f"expected projection {control['expect_projection']!r}, got {actual_projection!r}",
                        "unsafe_reason": proj.unsafe_reason,
                    })
                if proj.unsafe_reason is not None and control.get("expect_unsafe_reason") and proj.unsafe_reason != control["expect_unsafe_reason"]:
                    mismatches.append({"posting": posting["id"], "target": target, "error": f"expected unsafe_reason {control['expect_unsafe_reason']!r}, got {proj.unsafe_reason!r}"})

    print(f"Total controls: {total}")
    print(f"Mismatches: {len(mismatches)}")
    for m in mismatches:
        print(" ", m)


if __name__ == "__main__":
    main()
