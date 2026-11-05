"""Milestone 11-G4 Phase 2 -- admission-recovery control corpus generator.

Every sentence is either already self-authored and publicly committed
in M11-G1/M11-G2/M11-G3's own corpora/tests, or freshly built using
only the 17-tag canonical/alias VOCABULARY already present in
production source code (never posting text). No sentence is copied,
paraphrased, or reconstructed from M11-D's or M11-F's own private
real-posting corpora.

Each posting has an explicit `physical_lines` list and a separate
`controls` list, each control naming the exact `target_text` it
expects to become a recognized qualification-bearing unit (recovered
or already-admitted) -- or `expect_no_claim: true` for text that must
correctly stay excluded even after the fix.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = REPO_ROOT / "evaluation" / "m11g4" / "admission_recovery_controls.json"


def c(target_text, category, *, currently_admitted, expect_recovered=False, expect_no_claim=False,
      expect_decline=False, expect_reason=None, expect_tag=None, expect_sibling_tags=None,
      expect_necessity=None, expect_logical_composition=None, expect_projection=None,
      expect_unsafe_reason=None, expect_applicability_present=None, notes=None):
    entry = {
        "target_text": target_text, "category": category,
        "currently_admitted": currently_admitted, "expect_recovered": expect_recovered,
        "expect_no_claim": expect_no_claim,
        "expect_decline": expect_decline, "expect_reason": expect_reason,
        "expect_tag": expect_tag, "expect_necessity": expect_necessity,
        "expect_logical_composition": expect_logical_composition,
        "expect_projection": expect_projection, "expect_unsafe_reason": expect_unsafe_reason,
    }
    if expect_sibling_tags:
        entry["expect_sibling_tags"] = expect_sibling_tags
    if expect_applicability_present is not None:
        entry["expect_applicability_present"] = expect_applicability_present
    if notes:
        entry["notes"] = notes
    return entry


POSTINGS = [
    {
        "id": "q01", "title": "Genuinely Unsectioned, Recoverable Qualification",
        "physical_lines": [
            "Strong understanding of distributed systems.",
            "Our company offers great perks.",
        ],
        "controls": [
            c("Strong understanding of distributed systems.", "A", currently_admitted=False,
              expect_recovered=True, expect_tag="distributed-systems", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement",
              notes="genuinely unsectioned document -- Milestone 6B's own default-REQUIRED policy applies once recovered"),
            c("Our company offers great perks.", "E", currently_admitted=False, expect_no_claim=True,
              notes="fails BOTH _looks_like_requirement and _QUALIFYING_INTENT_V2 -- must stay excluded even after the fix"),
        ],
    },
    {
        "id": "q02", "title": "Recoverable Preamble Before Real Heading",
        "physical_lines": [
            "Strong understanding of concurrency.",
            "",
            "Requirements:",
            "Experience with embedded systems is required.",
        ],
        "controls": [
            c("Strong understanding of concurrency.", "A", currently_admitted=False,
              expect_recovered=True, expect_tag="concurrency", expect_necessity=None,
              expect_logical_composition="single", expect_projection="unparsed_claim",
              expect_unsafe_reason="necessity_unknown",
              notes="preamble before the document's own later real heading -- M11-G2's section-eligibility rule downgrades it, exactly as an already-admitted preamble claim would be"),
            c("Experience with embedded systems is required.", "A", currently_admitted=True,
              expect_tag="embedded-systems-design", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement",
              notes="already-admitted baseline, confirms unaffected"),
        ],
    },
    {
        "id": "q03", "title": "Recoverable UNKNOWN Heading vs. Already-Admitted Local Marker",
        "physical_lines": [
            "Additional Information:",
            "Strong understanding of control systems.",
            "Control systems experience is required.",
        ],
        "controls": [
            c("Strong understanding of control systems.", "A", currently_admitted=False,
              expect_recovered=True, expect_tag="control-systems", expect_necessity=None,
              expect_logical_composition="single", expect_projection="unparsed_claim",
              expect_unsafe_reason="necessity_unknown",
              notes="UNKNOWN-heading content with no local marker -- correctly stays UNKNOWN necessity once recovered"),
            c("Control systems experience is required.", "A", currently_admitted=True,
              expect_tag="control-systems", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement",
              notes="already-admitted today via local REQUIRED marker -- confirms unaffected, not duplicated"),
        ],
    },
    {
        "id": "q04", "title": "Recoverable LEARNING Heading",
        "physical_lines": [
            "What You'll Learn:",
            "Strong understanding of quantum computing.",
        ],
        "controls": [
            c("Strong understanding of quantum computing.", "C", currently_admitted=False,
              expect_recovered=True, expect_tag="quantum-computing", expect_necessity=None,
              expect_logical_composition="single", expect_projection="unparsed_claim",
              expect_unsafe_reason="necessity_unknown"),
        ],
    },
    {
        "id": "q05", "title": "Responsibility Duty Under an Unrecognized Heading, Not Recovered as a Qualification",
        "physical_lines": [
            "Additional Information:",
            "Design and build strong distributed systems architecture.",
        ],
        "controls": [
            c("Design and build strong distributed systems architecture.", "B", currently_admitted=False,
              expect_recovered=True, expect_decline=True, expect_reason="responsibility_lead",
              notes="the WIDENED admission gate recovers this line as a Claim (it now reaches the extractor), "
                    "but the extractor's own, UNCHANGED _RESPONSIBILITY_LEAD check still correctly declines it -- "
                    "recovering admission never means confidently accepting the content"),
        ],
    },
    {
        "id": "q06", "title": "Company Narrative, Not Recovered as a False Qualification",
        "physical_lines": [
            "Our team has deep expertise in distributed systems.",
            "",
            "Requirements:",
            "Knowledge of concurrency.",
        ],
        "controls": [
            c("Our team has deep expertise in distributed systems.", "D", currently_admitted=False,
              expect_recovered=True, expect_decline=True, expect_reason="narrative_cue",
              notes="recovered as a Claim, then correctly declined by the extractor's own unchanged narrative check"),
            c("Knowledge of concurrency.", "A", currently_admitted=True,
              expect_tag="concurrency", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement"),
        ],
    },
    {
        "id": "q06b", "title": "Company Product Narrative, Not Recovered as a False Qualification",
        "physical_lines": [
            "We've built and leveraged strong distributed systems expertise.",
        ],
        "controls": [
            c("We've built and leveraged strong distributed systems expertise.", "D", currently_admitted=False,
              expect_recovered=True, expect_decline=True, expect_reason="narrative_cue",
              notes="a DIFFERENT narrative trigger (company/product narrative, not the broader-subject one) -- "
                    "same safety property confirmed"),
        ],
    },
    {
        "id": "q07", "title": "Negation, Recovered Then Declined",
        "physical_lines": [
            "No prior knowledge with control systems is necessary.",
        ],
        "controls": [
            c("No prior knowledge with control systems is necessary.", "F", currently_admitted=False,
              expect_recovered=True, expect_decline=True, expect_reason="negation"),
        ],
    },
    {
        "id": "q08", "title": "Conditional Statement, Recovered",
        "physical_lines": [
            "Strong understanding of distributed systems is expected, unless a manager approves an exception.",
        ],
        "controls": [
            c("Strong understanding of distributed systems is expected, unless a manager approves an exception.",
              "A", currently_admitted=False, expect_recovered=True,
              expect_tag="distributed-systems", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="unparsed_claim",
              expect_unsafe_reason="material_applicability_condition_not_representable_on_job_requirement",
              expect_applicability_present=True),
        ],
    },
    {
        "id": "q09", "title": "Multi-Competency AND Statement, Recovered",
        "physical_lines": [
            "Deep expertise in concurrency, system design, and database design.",
        ],
        "controls": [
            c("Deep expertise in concurrency, system design, and database design.", "A",
              currently_admitted=False, expect_recovered=True,
              expect_tag="concurrency", expect_sibling_tags=["system-design", "database-design"],
              expect_necessity="REQUIRED", expect_logical_composition="and", expect_projection="job_requirement"),
        ],
    },
    {
        "id": "q10", "title": "OR-List Safety, Recovered",
        "physical_lines": [
            "Strong understanding of concurrency or distributed systems.",
        ],
        "controls": [
            c("Strong understanding of concurrency or distributed systems.", "F", currently_admitted=False,
              expect_recovered=True, expect_decline=True, expect_reason="missing_contract",
              notes="M11-G1's OR-list safety fix, confirmed intact for a recovered claim"),
        ],
    },
    {
        "id": "q11", "title": "Wrapped Statement, Recovered",
        "physical_lines": [
            "Strong understanding of",
            "distributed systems.",
        ],
        "controls": [
            c("Strong understanding of\ndistributed systems.", "A", currently_admitted=False,
              expect_recovered=True, expect_tag="distributed-systems", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement",
              notes="soft line-wrap across two physical lines, joined by the SAME M11-A2 logic reused via import"),
        ],
    },
    {
        "id": "q12", "title": "Education and Ambiguous Statements, No Tag Fabrication",
        "physical_lines": [
            "Strong background in a relevant engineering discipline.",
            "A strong technical aptitude is expected.",
            "Bachelor's degree in Computer Science.",
        ],
        "controls": [
            c("Strong background in a relevant engineering discipline.", "F", currently_admitted=False,
              expect_recovered=True, expect_decline=True, expect_reason="no_competency_language",
              notes="recovered as a Claim, but no competency tag exists for this phrasing -- confirms "
                    "widened admission never fabricates a tag"),
            c("A strong technical aptitude is expected.", "F", currently_admitted=False,
              expect_recovered=True, expect_decline=True, expect_reason="no_competency_language"),
            c("Bachelor's degree in Computer Science.", "A", currently_admitted=True,
              expect_decline=True, expect_reason="no_competency_language",
              notes="already-admitted today via 'degree' -- confirms unaffected baseline"),
        ],
    },
    {
        "id": "q13", "title": "Full Multi-Section Posting: Recovered, Already-Admitted, and Excluded Content Together",
        "physical_lines": [
            "Our team has deep expertise in distributed systems.",
            "",
            "Requirements:",
            "Experience with concurrency is required.",
            "What You'll Learn:",
            "Strong exposure to quantum computing.",
            "Responsibilities:",
            "Design and build systems with strong database design expertise.",
            "Additional Information:",
            "Strong understanding of control systems.",
        ],
        "controls": [
            c("Our team has deep expertise in distributed systems.", "D", currently_admitted=False,
              expect_recovered=True, expect_decline=True, expect_reason="narrative_cue"),
            c("Experience with concurrency is required.", "A", currently_admitted=True,
              expect_tag="concurrency", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement"),
            c("Strong exposure to quantum computing.", "C", currently_admitted=False,
              expect_recovered=True, expect_tag="quantum-computing", expect_necessity=None,
              expect_logical_composition="single", expect_projection="unparsed_claim",
              expect_unsafe_reason="necessity_unknown"),
            c("Design and build systems with strong database design expertise.", "B",
              currently_admitted=True,
              expect_decline=True, expect_reason="responsibility_lead",
              notes="under a RESPONSIBILITY heading, already admitted unconditionally by segment_description "
                    "itself (in_recognized_section bypass) -- this recovery pass must never touch it"),
            c("Strong understanding of control systems.", "A", currently_admitted=False,
              expect_recovered=True, expect_tag="control-systems", expect_necessity=None,
              expect_logical_composition="single", expect_projection="unparsed_claim",
              expect_unsafe_reason="necessity_unknown"),
        ],
    },
    {
        "id": "q14", "title": "Bulleted Recoverable Qualifications",
        "physical_lines": [
            "- Strong understanding of embedded systems.",
            "- Familiarity with network protocols.",
        ],
        "controls": [
            c("Strong understanding of embedded systems.", "A", currently_admitted=False,
              expect_recovered=True, expect_tag="embedded-systems-design", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement",
              notes="bulleted, unsectioned -- confirms bullet-prefix stripping is preserved via reuse"),
            c("Familiarity with network protocols.", "A", currently_admitted=True,
              expect_tag="os-networking", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement",
              notes="already-admitted today via 'familiar*' -- confirms unaffected"),
        ],
    },
    {
        "id": "q15", "title": "Proficiency and Comfortable Constructions, Recovered",
        "physical_lines": [
            "Proficiency with GPU programming and parallel computing.",
            "Comfortable with digital logic design and boolean algebra.",
        ],
        "controls": [
            c("Proficiency with GPU programming and parallel computing.", "A", currently_admitted=True,
              expect_tag="gpu-parallel-computing", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement",
              notes="'Proficiency' DOES match segmentation's own 'proficien*' root -- already admitted "
                    "today, confirms unaffected baseline rather than a recovery case"),
            c("Comfortable with digital logic design and boolean algebra.", "A", currently_admitted=False,
              expect_recovered=True, expect_tag="digital-logic", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement",
              notes="'comfortable' is one of _QUALIFYING_INTENT_V2's own bare cue words, absent entirely "
                    "from segmentation's own vocabulary -- a genuine gap case"),
        ],
    },
    {
        "id": "q16", "title": "Already-Admitted REQUIRED/PREFERRED Baseline, Confirms No Duplication",
        "physical_lines": [
            "Requirements:",
            "Strong understanding of signal processing.",
            "Preferred Qualifications:",
            "Strong understanding of circuit theory.",
        ],
        "controls": [
            c("Strong understanding of signal processing.", "A", currently_admitted=True,
              expect_tag="signal-processing", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement",
              notes="REQUIRED section -- already admitted unconditionally via in_recognized_section bypass; "
                    "this recovery pass must never touch (or duplicate) content here at all"),
            c("Strong understanding of circuit theory.", "A", currently_admitted=True,
              expect_tag="circuit-theory", expect_necessity="PREFERRED",
              expect_logical_composition="single", expect_projection="job_requirement",
              notes="PREFERRED section -- same confirmation"),
        ],
    },
    {
        "id": "q17", "title": "Recoverable Qualifications Across Additional Domains",
        "physical_lines": [
            "Strong understanding of computer vision and object detection.",
            "Deep expertise in cybersecurity threat modeling.",
            "Solid grasp of algorithms and data structures.",
        ],
        "controls": [
            c("Strong understanding of computer vision and object detection.", "A", currently_admitted=False,
              expect_recovered=True, expect_tag="computer-vision", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement"),
            c("Deep expertise in cybersecurity threat modeling.", "A", currently_admitted=False,
              expect_recovered=True, expect_tag="cybersecurity-threat-modeling", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement"),
            c("Solid grasp of algorithms and data structures.", "A", currently_admitted=False,
              expect_recovered=True, expect_tag="algorithms-data-structures", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement"),
        ],
    },
    {
        "id": "q18", "title": "Learning Opportunity With Explicit Local Marker Preserved",
        "physical_lines": [
            "What You'll Learn:",
            "Embedded systems experience is required.",
            "Strong understanding of embedded systems.",
        ],
        "controls": [
            c("Embedded systems experience is required.", "A", currently_admitted=True,
              expect_tag="embedded-systems-design", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement",
              notes="already admitted today ('experience' signal word) -- local REQUIRED marker preserved "
                    "under LEARNING, confirms unaffected"),
            c("Strong understanding of embedded systems.", "C", currently_admitted=False,
              expect_recovered=True, expect_tag="embedded-systems-design", expect_necessity=None,
              expect_logical_composition="single", expect_projection="unparsed_claim",
              expect_unsafe_reason="necessity_unknown",
              notes="recovered sibling line, no local marker -- correctly stays UNKNOWN"),
        ],
    },
    {
        "id": "q19", "title": "Mixed AND/OR Structure, Recovered",
        "physical_lines": [
            "Strong background in system design, and familiarity with either distributed systems or performance optimization.",
        ],
        "controls": [
            c("Strong background in system design, and familiarity with either distributed systems or performance optimization.",
              "A", currently_admitted=True,
              expect_necessity="REQUIRED", expect_logical_composition="mixed_unsupported",
              expect_projection="unparsed_claim", expect_unsafe_reason="mixed_unsupported_logical_structure",
              notes="'familiarity' already matches segmentation's own 'familiar*' root -- already admitted "
                    "today; confirms the genuine AND-of-OR MIXED_UNSUPPORTED structure is unaffected baseline, "
                    "not a recovery case"),
        ],
    },
    {
        "id": "q20", "title": "Responsibility Phrased Without Imperative Lead, Outside a Recognized Section",
        "physical_lines": [
            "Strong ownership of distributed systems reliability.",
            "",
            "Requirements:",
            "Experience with concurrency is required.",
        ],
        "controls": [
            c("Strong ownership of distributed systems reliability.", "B", currently_admitted=False,
              expect_recovered=True, expect_tag="distributed-systems", expect_necessity=None,
              expect_logical_composition="single", expect_projection="unparsed_claim",
              expect_unsafe_reason="necessity_unknown",
              notes="genuine duty wording with qualifying-intent vocabulary and NO imperative lead verb, "
                    "preceding the document's own later real heading -- recovered as a Claim (the admission "
                    "gate is widened), but correctly stays UNKNOWN necessity (a preamble claim is ineligible "
                    "for the section default once the document has real structure elsewhere) -- never "
                    "confidently scored, the same G2-disclosed tradeoff measured in M11-G3 §5"),
            c("Experience with concurrency is required.", "A", currently_admitted=True,
              expect_tag="concurrency", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement",
              notes="already-admitted baseline, confirms unaffected"),
        ],
    },
    {
        "id": "q21", "title": "Final Coverage Pad: Grounding/Grasp Cues and a Second Preamble Case",
        "physical_lines": [
            "Solid grounding in database design and relational schemas.",
            "Deep grasp of control systems theory and PID.",
            "Our engineering team has deep expertise in concurrency.",
            "",
            "Required Qualifications:",
            "Experience with distributed systems is required.",
        ],
        "controls": [
            c("Solid grounding in database design and relational schemas.", "A", currently_admitted=False,
              expect_recovered=True, expect_tag="database-design", expect_necessity=None,
              expect_logical_composition="single", expect_projection="unparsed_claim",
              expect_unsafe_reason="necessity_unknown",
              notes="'grounding' is one of _QUALIFYING_INTENT_V2's own leading-qualifier words, absent "
                    "from segmentation's own vocabulary; this line precedes the posting's own LATER real "
                    "heading, so once recovered it is a preamble claim -- ineligible for a default "
                    "necessity, correctly stays UNKNOWN (NOT the same as a genuinely unsectioned whole "
                    "document, already covered by q01/q17)"),
            c("Deep grasp of control systems theory and PID.", "A", currently_admitted=False,
              expect_recovered=True, expect_tag="control-systems", expect_necessity=None,
              expect_logical_composition="single", expect_projection="unparsed_claim",
              expect_unsafe_reason="necessity_unknown",
              notes="'grasp' is likewise absent from segmentation's own vocabulary; same preamble-ineligibility reasoning"),
            c("Our engineering team has deep expertise in concurrency.", "D", currently_admitted=False,
              expect_recovered=True, expect_decline=True, expect_reason="narrative_cue",
              notes="second _BROADER_NARRATIVE_SUBJECT trigger ('our engineering team'), preamble position"),
            c("Experience with distributed systems is required.", "A", currently_admitted=True,
              expect_tag="distributed-systems", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement",
              notes="employer-specific REQUIRED heading wording ('Required Qualifications:'), already admitted"),
        ],
    },
]


def main() -> None:
    postings_payload = []
    total_controls = 0
    for p in POSTINGS:
        description = "\n".join(p["physical_lines"]) + "\n"
        postings_payload.append({
            "id": p["id"], "title": p["title"], "description": description, "controls": p["controls"],
        })
        total_controls += len(p["controls"])

    payload = {
        "corpus_version": "m11g4-dev:v1",
        "annotation_provenance": (
            "Self-authored synthetic controls, no third-party text. Expected outcomes frozen "
            "BEFORE any new offline admission-recovery code was implemented. Admission status "
            "('currently_admitted') was verified directly against the real, unmodified "
            "segment_description()/_looks_like_requirement before freezing; extractor/projection "
            "outcomes were verified against the real, unmodified extract_competency_qualifications_v2/"
            "project_qualification given the predicted section context. Whether each "
            "'expect_recovered' control is ACTUALLY recovered by the new offline function is "
            "verified AFTER implementation, never tuned backwards into this gold."
        ),
        "postings": postings_payload,
    }
    OUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")
    print(f"Wrote {len(postings_payload)} postings, {total_controls} controls -> {OUT_PATH}")


if __name__ == "__main__":
    main()
