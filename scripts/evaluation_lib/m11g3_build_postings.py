"""Milestone 11-G3 Phase 2 -- full-posting development corpus generator.

Every sentence below is either (a) already self-authored and already
PUBLICLY committed in M11-G1/M11-G2's own corpora/tests (safe to
reuse -- not third-party text), or (b) freshly self-authored, built
only from the 17-tag canonical/alias VOCABULARY already present in
production source (`competency_extraction.py`/`competency_aliases.py`
-- code, not posting text). No sentence here is copied, paraphrased,
or reconstructed from M11-D's or M11-F's own PRIVATE real-posting
corpora, which remain untouched and unread for this purpose.

Each posting has an explicit `physical_lines` list (the exact raw
lines assembled into `description`) and a separate `controls` list,
each control naming the exact `target_text` it expects
`segment_description()` to produce as a real `Claim.text` (or
`expect_no_claim: true` for text that should never become a Claim at
all). Ground-truth qualification-intent categories (A-F) and all
expected outcomes are annotated BEFORE the real
`segment_description()`/`extract_competency_qualifications_v2()`/
`project_qualification()` chain is ever run against this corpus.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = REPO_ROOT / "evaluation" / "m11g3" / "full_posting_controls.json"


def c(target_text, category, *, is_competency_relevant=False, expect_decline=False, expect_reason=None,
      expect_tag=None, expect_sibling_tags=None, expect_necessity=None, expect_logical_composition=None,
      expect_projection=None, expect_unsafe_reason=None, expect_applicability_present=None,
      expect_no_claim=False, notes=None):
    entry = {
        "target_text": target_text, "category": category, "is_competency_relevant": is_competency_relevant,
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
        "id": "p01", "title": "Backend Engineer",
        "physical_lines": [
            "Requirements:",
            "Experience with distributed systems is required.",
            "Strong understanding of algorithms and data structures.",
            "Preferred Qualifications:",
            "Knowledge of concurrency.",
            "Responsibilities:",
            "Design and build systems with strong distributed systems expertise.",
            "Strong ownership of distributed systems reliability.",
        ],
        "controls": [
            c("Experience with distributed systems is required.", "A", is_competency_relevant=True,
              expect_tag="distributed-systems", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement"),
            c("Strong understanding of algorithms and data structures.", "A", is_competency_relevant=True,
              expect_tag="algorithms-data-structures", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement"),
            c("Knowledge of concurrency.", "A", is_competency_relevant=True,
              expect_tag="concurrency", expect_necessity="PREFERRED",
              expect_logical_composition="single", expect_projection="job_requirement"),
            c("Design and build systems with strong distributed systems expertise.", "B",
              expect_decline=True, expect_reason="responsibility_lead"),
            c("Strong ownership of distributed systems reliability.", "B", is_competency_relevant=True,
              expect_tag="distributed-systems", expect_necessity=None,
              expect_logical_composition="single", expect_projection="unparsed_claim",
              expect_unsafe_reason="necessity_unknown",
              notes="genuine duty wording with qualifying-intent language; the G2-disclosed tradeoff -- "
                    "a Qualification is still constructed but safely routed via necessity=UNKNOWN, never scored"),
        ],
    },
    {
        "id": "p02", "title": "Embedded Systems Engineer",
        "physical_lines": [
            "What You'll Bring:",
            "Embedded systems experience is required.",
            "Experience with bare-metal programming.",
            "Nice to Have:",
            "Experience with network protocols.",
        ],
        "controls": [
            c("Embedded systems experience is required.", "A", is_competency_relevant=True,
              expect_tag="embedded-systems-design", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement",
              notes="UNKNOWN-heading preservation via explicit local marker"),
            c("Experience with bare-metal programming.", "A", is_competency_relevant=True,
              expect_tag="embedded-systems-design", expect_necessity=None,
              expect_logical_composition="single", expect_projection="unparsed_claim",
              expect_unsafe_reason="necessity_unknown"),
            c("Experience with network protocols.", "A", is_competency_relevant=True,
              expect_tag="os-networking", expect_necessity="PREFERRED",
              expect_logical_composition="single", expect_projection="job_requirement"),
        ],
    },
    {
        "id": "p03", "title": "Computer Vision Engineer",
        "physical_lines": [
            "Required Skills:",
            "Strong background in object detection and image segmentation is required.",
            "What You'll Learn:",
            "Familiarity with distributed systems.",
        ],
        "controls": [
            c("Strong background in object detection and image segmentation is required.", "A",
              is_competency_relevant=True, expect_tag="computer-vision", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement"),
            c("Familiarity with distributed systems.", "C", is_competency_relevant=True,
              expect_tag="distributed-systems", expect_necessity=None,
              expect_logical_composition="single", expect_projection="unparsed_claim",
              expect_unsafe_reason="necessity_unknown"),
        ],
    },
    {
        "id": "p04", "title": "Security Engineer",
        "physical_lines": [
            "Requirements:",
            "Strong background in threat modeling and secure coding practices is required.",
            "We offer competitive compensation and comprehensive benefits.",
        ],
        "controls": [
            c("Strong background in threat modeling and secure coding practices is required.", "A",
              is_competency_relevant=True, expect_tag="cybersecurity-threat-modeling", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement"),
            c("We offer competitive compensation and comprehensive benefits.", "E",
              expect_decline=True, expect_reason="no_competency_language",
              notes="administrative text remaining under the still-open REQUIRED section (no closing heading); "
                    "safely declined by the competency extractor regardless"),
        ],
    },
    {
        "id": "p05", "title": "Data Engineer",
        "physical_lines": [
            "Our team has years of experience with distributed systems.",
            "",
            "Requirements:",
            "Experience with distributed systems is required.",
        ],
        "controls": [
            c("Our team has years of experience with distributed systems.", "D",
              expect_decline=True, expect_reason="narrative_cue",
              notes="preamble before the document's own later real heading"),
            c("Experience with distributed systems is required.", "A", is_competency_relevant=True,
              expect_tag="distributed-systems", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement"),
        ],
    },
    {
        "id": "p06", "title": "Robotics Engineer",
        "physical_lines": [
            "Requirements:",
            "Knowledge of control systems.",
            "Experience with concurrency or distributed systems is required.",
        ],
        "controls": [
            c("Knowledge of control systems.", "A", is_competency_relevant=True,
              expect_tag="control-systems", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement"),
            c("Experience with concurrency or distributed systems is required.", "F",
              expect_decline=True, expect_reason="missing_contract",
              notes="M11-G1's OR-list safety fix, confirmed intact end-to-end under section context"),
        ],
    },
    {
        "id": "p07", "title": "Machine Learning Engineer",
        "physical_lines": [
            "Requirements:",
            "Familiarity with overfitting and regularization techniques is required.",
            "Preferred Qualifications:",
            "Knowledge of bias-variance tradeoffs.",
        ],
        "controls": [
            c("Familiarity with overfitting and regularization techniques is required.", "A",
              is_competency_relevant=True, expect_tag="ml-fundamentals", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement"),
            c("Knowledge of bias-variance tradeoffs.", "A", is_competency_relevant=True,
              expect_tag="ml-fundamentals", expect_necessity="PREFERRED",
              expect_logical_composition="single", expect_projection="job_requirement"),
        ],
    },
    {
        "id": "p08", "title": "Data Scientist",
        "physical_lines": [
            "Requirements:",
            "Solid grounding in basic statistics is required.",
            "Responsibilities:",
            "Collaborate across teams with strong machine learning fundamentals expertise.",
        ],
        "controls": [
            c("Solid grounding in basic statistics is required.", "A", is_competency_relevant=True,
              expect_tag="ml-fundamentals", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement"),
            c("Collaborate across teams with strong machine learning fundamentals expertise.", "B",
              expect_decline=True, expect_reason="responsibility_lead"),
        ],
    },
    {
        "id": "p09", "title": "Hardware / Digital Logic Engineer",
        "physical_lines": [
            "Requirements:",
            "Strong grasp of digital logic design and boolean algebra is required.",
            "Nice to Have:",
            "Familiarity with circuit theory and analog electronics.",
        ],
        "controls": [
            c("Strong grasp of digital logic design and boolean algebra is required.", "A",
              is_competency_relevant=True, expect_tag="digital-logic", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement"),
            c("Familiarity with circuit theory and analog electronics.", "A", is_competency_relevant=True,
              expect_tag="circuit-theory", expect_necessity="PREFERRED",
              expect_logical_composition="single", expect_projection="job_requirement"),
        ],
    },
    {
        "id": "p10", "title": "Signal Processing Engineer",
        "physical_lines": [
            "Requirements:",
            "Experience with digital signal processing and filter design is required.",
            "What You'll Learn:",
            "Familiarity with FFTs and filter design techniques.",
        ],
        "controls": [
            c("Experience with digital signal processing and filter design is required.", "A",
              is_competency_relevant=True, expect_tag="signal-processing", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement"),
            c("Familiarity with FFTs and filter design techniques.", "C", is_competency_relevant=True,
              expect_tag="signal-processing", expect_necessity=None,
              expect_logical_composition="single", expect_projection="unparsed_claim",
              expect_unsafe_reason="necessity_unknown"),
        ],
    },
    {
        "id": "p11", "title": "Database Engineer",
        "physical_lines": [
            "Requirements:",
            "Strong background in database design and relational schemas is required.",
            "Preferred Qualifications:",
            "Knowledge of indexing strategies.",
        ],
        "controls": [
            c("Strong background in database design and relational schemas is required.", "A",
              is_competency_relevant=True, expect_tag="database-design", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement"),
            c("Knowledge of indexing strategies.", "A", is_competency_relevant=True,
              expect_tag="database-design", expect_necessity="PREFERRED",
              expect_logical_composition="single", expect_projection="job_requirement"),
        ],
    },
    {
        "id": "p12", "title": "GPU / HPC Engineer",
        "physical_lines": [
            "Requirements:",
            "Experience with GPU programming and parallel computing is required.",
            "Responsibilities:",
            "Optimize workloads with strong GPU programming and high-performance computing expertise.",
        ],
        "controls": [
            c("Experience with GPU programming and parallel computing is required.", "A",
              is_competency_relevant=True, expect_tag="gpu-parallel-computing", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement"),
            c("Optimize workloads with strong GPU programming and high-performance computing expertise.", "B",
              expect_decline=True, expect_reason="responsibility_lead"),
        ],
    },
    {
        "id": "p13", "title": "Systems / OS Engineer",
        "physical_lines": [
            "Requirements:",
            "Strong understanding of operating systems internals is required.",
            "Nice to Have:",
            "Familiarity with TCP/IP networking and process scheduling.",
        ],
        "controls": [
            c("Strong understanding of operating systems internals is required.", "A",
              is_competency_relevant=True, expect_tag="os-networking", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement"),
            c("Familiarity with TCP/IP networking and process scheduling.", "A", is_competency_relevant=True,
              expect_tag="os-networking", expect_necessity="PREFERRED",
              expect_logical_composition="single", expect_projection="job_requirement"),
        ],
    },
    {
        "id": "p14", "title": "Performance Engineering",
        "physical_lines": [
            "Requirements:",
            "Experience debugging and optimizing performance-critical systems is required.",
            "Responsibilities:",
            "Maintain systems with strong performance-critical optimization expertise.",
        ],
        "controls": [
            c("Experience debugging and optimizing performance-critical systems is required.", "A",
              is_competency_relevant=True, expect_tag="performance-optimization", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement"),
            c("Maintain systems with strong performance-critical optimization expertise.", "B",
              expect_decline=True, expect_reason="responsibility_lead"),
        ],
    },
    {
        "id": "p15", "title": "Control Systems Engineer",
        "physical_lines": [
            "Requirements:",
            "Strong understanding of control systems theory and PID is required.",
            "Nice to Have:",
            "Familiarity with state-space methods.",
        ],
        "controls": [
            c("Strong understanding of control systems theory and PID is required.", "A",
              is_competency_relevant=True, expect_tag="control-systems", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement"),
            c("Familiarity with state-space methods.", "A", is_competency_relevant=True,
              expect_tag="control-systems", expect_necessity="PREFERRED",
              expect_logical_composition="single", expect_projection="job_requirement"),
        ],
    },
    {
        "id": "p16", "title": "Quantum Computing Research",
        "physical_lines": [
            "Requirements:",
            "Experience with quantum circuit design and qubit error correction is required.",
            "Additional Information:",
            "Quantum computing experience is required.",
        ],
        "controls": [
            c("Experience with quantum circuit design and qubit error correction is required.", "A",
              is_competency_relevant=True, expect_tag="quantum-computing", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement"),
            c("Quantum computing experience is required.", "A", is_competency_relevant=True,
              expect_tag="quantum-computing", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement",
              notes="UNKNOWN-heading preservation via explicit local marker"),
        ],
    },
    {
        "id": "p17", "title": "Infrastructure Engineer",
        "physical_lines": [
            "Requirements:",
            "Strong skills in concurrency, system design, and database design are required.",
            "- Experience with embedded systems.",
            "- Knowledge of concurrency.",
        ],
        "controls": [
            c("Strong skills in concurrency, system design, and database design are required.", "A",
              is_competency_relevant=True, expect_tag="concurrency",
              expect_sibling_tags=["system-design", "database-design"],
              expect_necessity="REQUIRED", expect_logical_composition="and", expect_projection="job_requirement"),
            c("Experience with embedded systems.", "A", is_competency_relevant=True,
              expect_tag="embedded-systems-design", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement",
              notes="bulleted list item under REQUIRED"),
            c("Knowledge of concurrency.", "A", is_competency_relevant=True,
              expect_tag="concurrency", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement",
              notes="second bulleted list item under the same REQUIRED section"),
        ],
    },
    {
        "id": "p18", "title": "Platform Engineer",
        "physical_lines": [
            "Requirements:",
            "Experience with distributed systems is expected, unless a manager approves an exception.",
            "Deep familiarity with",
            "concurrency fundamentals.",
        ],
        "controls": [
            c("Experience with distributed systems is expected, unless a manager approves an exception.", "A",
              is_competency_relevant=True, expect_tag="distributed-systems", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="unparsed_claim",
              expect_unsafe_reason="material_applicability_condition_not_representable_on_job_requirement",
              expect_applicability_present=True,
              notes="project_qualification's own pre-existing, unmodified safety rule: ANY applicability "
                    "condition routes to UnparsedClaim, never JobRequirement -- the condition is preserved "
                    "(applicability_condition is not None) but never silently scored"),
            c("Deep familiarity with\nconcurrency fundamentals.", "A", is_competency_relevant=True,
              expect_tag="concurrency", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement",
              notes="soft line-wrap across two physical lines, joined by segment_description's own M11-A2 logic"),
        ],
    },
    {
        "id": "p19", "title": "Unsectioned Mini-Posting",
        "physical_lines": [
            "Experience with concurrency.",
            "Strong understanding of concurrency.",
            "Our company offers great perks and a fun culture.",
        ],
        "controls": [
            c("Experience with concurrency.", "A", is_competency_relevant=True,
              expect_tag="concurrency", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement",
              notes="genuinely unsectioned whole document -- Milestone 6B's own "
                    "'no section at all -> default REQUIRED' policy"),
            c("Strong understanding of concurrency.", "F", expect_no_claim=True,
              notes="DELIBERATE integration-interface-mismatch demonstration (Phase 6): "
                    "segmentation.py's own _looks_like_requirement vocabulary does not include "
                    "'strong'/'understanding of', even though competency_extraction.py's own "
                    "_QUALIFYING_INTENT_V2 gate explicitly recognizes 'strong' as a bare qualifying "
                    "cue -- outside a recognized section, this sentence never reaches the offline "
                    "extractor at all, confirmed directly, not assumed"),
            c("Our company offers great perks and a fun culture.", "E", expect_no_claim=True,
              notes="no REQUIREMENT_SIGNAL word and no concept mention -- never becomes a Claim at all"),
        ],
    },
    {
        "id": "p20", "title": "Mixed Structure / Negation / Alias",
        "physical_lines": [
            "Requirements:",
            "Experience with system design, and familiarity with either distributed systems or performance optimization.",
            "No prior experience with embedded systems is necessary.",
            "Experience with computer vision and object detection is required.",
            "Knowledge of socket programming.",
        ],
        "controls": [
            c("Experience with system design, and familiarity with either distributed systems or performance optimization.",
              "A", is_competency_relevant=True, expect_necessity="REQUIRED",
              expect_logical_composition="mixed_unsupported", expect_projection="unparsed_claim",
              expect_unsafe_reason="mixed_unsupported_logical_structure",
              notes="genuine AND-of-OR structure, M11-E's own already-public test sentence"),
            c("No prior experience with embedded systems is necessary.", "F",
              expect_decline=True, expect_reason="negation"),
            c("Experience with computer vision and object detection is required.", "A", is_competency_relevant=True,
              expect_tag="computer-vision", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement",
              notes="two canonical phrases for the SAME tag, not a sibling-tag AND"),
            c("Knowledge of socket programming.", "A", is_competency_relevant=True,
              expect_tag="os-networking", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement",
              notes="alias-based match (semantically_equivalent) under a REQUIRED section"),
        ],
    },
    {
        "id": "p21", "title": "Responsibility and Narrative Diversity",
        "physical_lines": [
            "Our engineering team has years of experience with concurrency.",
            "Requirements:",
            "Experience with lock-free programming is required.",
            "Responsibilities:",
            "Build and maintain systems with strong distributed systems expertise.",
            "Lead the group with strong consensus algorithm and fault tolerance expertise.",
        ],
        "controls": [
            c("Our engineering team has years of experience with concurrency.", "D",
              expect_decline=True, expect_reason="narrative_cue"),
            c("Experience with lock-free programming is required.", "A", is_competency_relevant=True,
              expect_tag="concurrency", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement"),
            c("Build and maintain systems with strong distributed systems expertise.", "B",
              expect_decline=True, expect_reason="responsibility_lead"),
            c("Lead the group with strong consensus algorithm and fault tolerance expertise.", "B",
              expect_decline=True, expect_reason="responsibility_lead",
              notes="starts with 'Lead', a bare imperative duty verb, despite containing distributed-systems vocabulary"),
        ],
    },
    {
        "id": "p22", "title": "Additional Required/Preferred Domain Pairs",
        "physical_lines": [
            "Requirements:",
            "Strong understanding of distributed consensus algorithms and fault tolerance is required.",
            "Experience with scalable system architecture is required.",
            "Preferred Qualifications:",
            "Knowledge of database internals.",
            "Familiarity with attack vectors and secure coding.",
        ],
        "controls": [
            c("Strong understanding of distributed consensus algorithms and fault tolerance is required.", "A",
              is_competency_relevant=True, expect_tag="distributed-systems", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement",
              notes="distinct canonical alternatives within the distributed-systems pattern"),
            c("Experience with scalable system architecture is required.", "A", is_competency_relevant=True,
              expect_tag="system-design", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement"),
            c("Knowledge of database internals.", "A", is_competency_relevant=True,
              expect_tag="database-design", expect_necessity="PREFERRED",
              expect_logical_composition="single", expect_projection="job_requirement"),
            c("Familiarity with attack vectors and secure coding.", "A", is_competency_relevant=True,
              expect_tag="cybersecurity-threat-modeling", expect_necessity="PREFERRED",
              expect_logical_composition="single", expect_projection="job_requirement"),
        ],
    },
    {
        "id": "p23", "title": "Qualification Embedded in Responsibility",
        "physical_lines": [
            "Responsibilities:",
            "Candidates must have experience with distributed systems for this responsibility area.",
            "A strong candidate will have embedded systems experience, which is preferred for this duty.",
        ],
        "controls": [
            c("Candidates must have experience with distributed systems for this responsibility area.", "A",
              is_competency_relevant=True, expect_tag="distributed-systems", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement",
              notes="explicit local REQUIRED marker preserved under a RESPONSIBILITY section (reused from M11-G2)"),
            c("A strong candidate will have embedded systems experience, which is preferred for this duty.", "A",
              is_competency_relevant=True, expect_tag="embedded-systems-design", expect_necessity="PREFERRED",
              expect_logical_composition="single", expect_projection="job_requirement",
              notes="explicit local PREFERRED marker preserved under a RESPONSIBILITY section (reused from M11-G2)"),
        ],
    },
    {
        "id": "p24", "title": "Required/Preferred Transition with Bullets",
        "physical_lines": [
            "Requirements:",
            "- Experience with multithreading and concurrent programming is required.",
            "- Experience with resource-constrained embedded systems is required.",
            "Preferred Qualifications:",
            "- Experience with high-performance computing.",
            "- Experience with analog electronics.",
        ],
        "controls": [
            c("Experience with multithreading and concurrent programming is required.", "A",
              is_competency_relevant=True, expect_tag="concurrency", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement",
              notes="bulleted list item, two canonical alternatives for the SAME tag"),
            c("Experience with resource-constrained embedded systems is required.", "A",
              is_competency_relevant=True, expect_tag="embedded-systems-design", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement",
              notes="bulleted list item under the same REQUIRED section"),
            c("Experience with high-performance computing.", "A", is_competency_relevant=True,
              expect_tag="gpu-parallel-computing", expect_necessity="PREFERRED",
              expect_logical_composition="single", expect_projection="job_requirement",
              notes="bulleted list item under PREFERRED"),
            c("Experience with analog electronics.", "A", is_competency_relevant=True,
              expect_tag="circuit-theory", expect_necessity="PREFERRED",
              expect_logical_composition="single", expect_projection="job_requirement",
              notes="second bulleted list item under the same PREFERRED section"),
        ],
    },
    {
        "id": "p25", "title": "Algorithms / Firmware / Image Segmentation",
        "physical_lines": [
            "Requirements:",
            "Strong background in algorithmic problem-solving and big-O analysis is required.",
            "Experience with firmware development is required.",
            "Preferred Qualifications:",
            "Knowledge of image segmentation.",
            "Familiarity with race conditions.",
            "What You'll Learn:",
            "Familiarity with machine learning fundamentals.",
        ],
        "controls": [
            c("Strong background in algorithmic problem-solving and big-O analysis is required.", "A",
              is_competency_relevant=True, expect_tag="algorithms-data-structures", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement"),
            c("Experience with firmware development is required.", "A", is_competency_relevant=True,
              expect_tag="embedded-systems-design", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement"),
            c("Knowledge of image segmentation.", "A", is_competency_relevant=True,
              expect_tag="computer-vision", expect_necessity="PREFERRED",
              expect_logical_composition="single", expect_projection="job_requirement"),
            c("Familiarity with race conditions.", "A", is_competency_relevant=True,
              expect_tag="concurrency", expect_necessity="PREFERRED",
              expect_logical_composition="single", expect_projection="job_requirement"),
            c("Familiarity with machine learning fundamentals.", "C", is_competency_relevant=True,
              expect_tag="ml-fundamentals", expect_necessity=None,
              expect_logical_composition="single", expect_projection="unparsed_claim",
              expect_unsafe_reason="necessity_unknown"),
        ],
    },
    {
        "id": "p26", "title": "Multi-Section Mixed Posting",
        "physical_lines": [
            "Minimum Qualifications:",
            "Experience with distributed architecture is required.",
            "Nice to Have:",
            "Knowledge of qubit error correction.",
            "Responsibilities:",
            "Architect systems with strong performance-critical infrastructure expertise.",
            "Strong ownership of control systems reliability.",
            "Additional Information:",
            "Database design experience is required.",
            "We are a fast-growing company building the future of logistics.",
        ],
        "controls": [
            c("Experience with distributed architecture is required.", "A", is_competency_relevant=True,
              expect_tag="system-design", expect_sibling_tags=["distributed-systems"],
              expect_necessity="REQUIRED", expect_logical_composition="and", expect_projection="job_requirement",
              notes="employer-specific REQUIRED heading wording ('Minimum Qualifications:'); DISCOVERED "
                    "cross-tag vocabulary overlap -- 'distributed architecture' is simultaneously "
                    "system-design's own canonical phrase AND a pre-existing distributed-systems "
                    "SEMANTICALLY_EQUIVALENT alias (from M11-E's own alias table), so both tags fire even "
                    "though the sentence names only one concept and contains no 'and'/'or' word at all"),
            c("Knowledge of qubit error correction.", "A", is_competency_relevant=True,
              expect_tag="quantum-computing", expect_necessity="PREFERRED",
              expect_logical_composition="single", expect_projection="job_requirement"),
            c("Architect systems with strong performance-critical infrastructure expertise.", "B",
              expect_decline=True, expect_reason="responsibility_lead",
              notes="starts with 'Architect', a bare imperative duty verb, despite containing performance-optimization vocabulary"),
            c("Strong ownership of control systems reliability.", "B", is_competency_relevant=True,
              expect_tag="control-systems", expect_necessity=None,
              expect_logical_composition="single", expect_projection="unparsed_claim",
              expect_unsafe_reason="necessity_unknown",
              notes="RESPONSIBILITY-section duty wording with qualifying-intent language and no local marker"),
            c("Database design experience is required.", "A", is_competency_relevant=True,
              expect_tag="database-design", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement",
              notes="UNKNOWN-heading preservation via explicit local marker"),
            c("We are a fast-growing company building the future of logistics.", "D", expect_no_claim=True,
              notes="company narrative with no REQUIREMENT_SIGNAL word and no concept mention -- never becomes a Claim at all"),
        ],
    },
    {
        "id": "p27", "title": "Final Coverage Pad", "physical_lines": [
            "Preferred Qualifications:",
            "Knowledge of lock-free data structures and concurrent programming.",
            "Experience with networking fundamentals.",
            "Learning Opportunities:",
            "Familiarity with quantum computing.",
            "Required Qualifications:",
            "Experience with distributed systems is required.",
        ],
        "controls": [
            c("Knowledge of lock-free data structures and concurrent programming.", "A", is_competency_relevant=True,
              expect_tag="concurrency", expect_necessity="PREFERRED",
              expect_logical_composition="single", expect_projection="job_requirement"),
            c("Experience with networking fundamentals.", "A", is_competency_relevant=True,
              expect_tag="os-networking", expect_necessity="PREFERRED",
              expect_logical_composition="single", expect_projection="job_requirement"),
            c("Familiarity with quantum computing.", "C", is_competency_relevant=True,
              expect_tag="quantum-computing", expect_necessity=None,
              expect_logical_composition="single", expect_projection="unparsed_claim",
              expect_unsafe_reason="necessity_unknown",
              notes="employer-specific LEARNING heading wording ('Learning Opportunities:')"),
            c("Experience with distributed systems is required.", "A", is_competency_relevant=True,
              expect_tag="distributed-systems", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement",
              notes="employer-specific REQUIRED heading wording ('Required Qualifications:')"),
        ],
    },
    {
        "id": "p28", "title": "Named Technology and Education",
        "physical_lines": [
            "Requirements:",
            "Experience with Python is required.",
            "Bachelor's degree in Computer Science is required.",
            "Three years of professional software engineering experience is required.",
            "Experience with distributed systems is required.",
        ],
        "controls": [
            c("Experience with Python is required.", "A", is_competency_relevant=False,
              expect_decline=True, expect_reason="no_competency_language",
              notes="genuine qualification (named technology), but outside the 17-tag competency "
                    "vocabulary by design -- correctly declined, not fabricated into a competency tag"),
            c("Bachelor's degree in Computer Science is required.", "A", is_competency_relevant=False,
              expect_decline=True, expect_reason="no_competency_language",
              notes="genuine qualification (education), outside competency scope by design"),
            c("Three years of professional software engineering experience is required.", "A",
              is_competency_relevant=False, expect_decline=True, expect_reason="no_competency_language",
              notes="genuine qualification (years of experience), outside competency scope by design"),
            c("Experience with distributed systems is required.", "A", is_competency_relevant=True,
              expect_tag="distributed-systems", expect_necessity="REQUIRED",
              expect_logical_composition="single", expect_projection="job_requirement",
              notes="confirms mixing non-competency qualification lines with a genuine competency "
                    "line in the same REQUIRED section does not cause cross-contamination"),
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
        "corpus_version": "m11g3-dev:v1",
        "annotation_provenance": (
            "19 self-authored mini-postings. Every sentence is either already self-authored and "
            "publicly committed in M11-G1/M11-G2's own corpora/tests, or freshly authored using "
            "only the 17-tag canonical/alias VOCABULARY already present in production source code "
            "(never posting TEXT). No sentence is copied, paraphrased, or reconstructed from "
            "M11-D's or M11-F's own private real-posting corpora. Qualification-intent categories "
            "(A-F) and all expected outcomes were annotated BEFORE segment_description()/"
            "extract_competency_qualifications_v2()/project_qualification() were ever run against "
            "this corpus."
        ),
        "postings": postings_payload,
    }
    OUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")
    print(f"Wrote {len(postings_payload)} postings, {total_controls} annotated controls -> {OUT_PATH}")


if __name__ == "__main__":
    main()
