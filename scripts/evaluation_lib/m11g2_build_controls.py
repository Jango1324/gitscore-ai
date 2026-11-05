"""Milestone 11-G2 Phase 2 -- section-context control corpus generator.

Two kinds of controls, authored BEFORE any production code is changed:

- `direct_controls`: a hand-specified (text, section_kind,
  document_has_recognized_heading) triple, testing the new section-aware
  necessity/qualification logic directly and in isolation from
  `segmentation.py`'s own (separately, already extensively tested)
  heading classifier.
- `mini_posting_controls`: a genuine multi-line mini job-posting run
  through the REAL, unmodified `segment_description()` to produce real
  `Claim` objects -- confirming the end-to-end plumbing (heading ->
  Claim.section_kind -> offline extractor) actually works, not just the
  isolated necessity-resolution logic.

No third-party text. All self-authored synthetic sentences (same
discipline as M11-E/M11-F/M11-G1's own corpora).
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = REPO_ROOT / "evaluation" / "m11g2" / "section_context_controls.json"


def d(id_, category, text, section_kind, doc_heading, *, expect_decline=False,
      expect_reason=None, expect_tag=None, expect_necessity=None,
      expect_applicability_present=None, notes=None):
    entry = {
        "id": id_, "category": category, "text": text,
        "section_kind": section_kind, "document_has_recognized_heading": doc_heading,
        "expect_decline": expect_decline, "expect_reason": expect_reason,
        "expect_tag": expect_tag, "expect_necessity": expect_necessity,
    }
    if expect_applicability_present is not None:
        entry["expect_applicability_present"] = expect_applicability_present
    if notes:
        entry["notes"] = notes
    return entry


DIRECT_CONTROLS = [
    # --- Category 1: explicit required-skills sections, no local marker ---
    d("m11g2-d01", "required_section", "Experience with distributed systems.", "REQUIRED", True,
      expect_tag="distributed-systems", expect_necessity="REQUIRED"),
    d("m11g2-d02", "required_section", "Strong understanding of algorithms and data structures.", "REQUIRED", True,
      expect_tag="algorithms-data-structures", expect_necessity="REQUIRED"),
    d("m11g2-d03", "required_section", "Knowledge of control systems.", "REQUIRED", True,
      expect_tag="control-systems", expect_necessity="REQUIRED"),

    # --- Category 2: explicit preferred/nice-to-have sections, no local marker ---
    d("m11g2-d04", "preferred_section", "Experience with distributed systems.", "PREFERRED", True,
      expect_tag="distributed-systems", expect_necessity="PREFERRED"),
    d("m11g2-d05", "preferred_section", "Familiarity with embedded systems.", "PREFERRED", True,
      expect_tag="embedded-systems-design", expect_necessity="PREFERRED"),
    d("m11g2-d06", "preferred_section", "Knowledge of concurrency.", "PREFERRED", True,
      expect_tag="concurrency", expect_necessity="PREFERRED"),

    # --- Category 4: ambiguous qualifications headings (UNKNOWN section) ---
    d("m11g2-d07", "ambiguous_heading", "Experience with distributed systems.", "UNKNOWN", True,
      expect_tag="distributed-systems", expect_necessity=None),
    d("m11g2-d08", "ambiguous_heading", "Knowledge of concurrency.", "UNKNOWN", True,
      expect_tag="concurrency", expect_necessity=None),
    d("m11g2-d09", "ambiguous_heading", "Distributed systems experience is required.", "UNKNOWN", True,
      expect_tag="distributed-systems", expect_necessity="REQUIRED",
      notes="explicit local marker preserves genuine qualifications under unconventional headings"),

    # --- Category 5: responsibilities/duties sections, qualifying-intent language, NO local marker ---
    d("m11g2-d10", "responsibility_section", "Strong ownership of distributed systems reliability.",
      "RESPONSIBILITY", True, expect_tag="distributed-systems", expect_necessity=None),
    d("m11g2-d11", "responsibility_section", "Deep expertise in the project's embedded systems reliability strategy.",
      "RESPONSIBILITY", True, expect_tag="embedded-systems-design", expect_necessity=None),
    d("m11g2-d12", "responsibility_section", "Solid ownership of control systems tuning efforts.",
      "RESPONSIBILITY", True, expect_tag="control-systems", expect_necessity=None),

    # --- Category 6: company-background-like preamble (section=None, doc has later headings) ---
    d("m11g2-d13", "preamble_before_real_sections", "Strong background in distributed systems.", None, True,
      expect_tag="distributed-systems", expect_necessity=None),
    d("m11g2-d14", "preamble_before_real_sections", "Deep expertise in concurrency.", None, True,
      expect_tag="concurrency", expect_necessity=None),

    # --- Category 7: learning-opportunity sections, no local marker ---
    d("m11g2-d15", "learning_section", "Strong exposure to distributed systems.", "LEARNING", True,
      expect_tag="distributed-systems", expect_necessity=None),
    d("m11g2-d16", "learning_section", "Deep familiarity with embedded systems.", "LEARNING", True,
      expect_tag="embedded-systems-design", expect_necessity=None),
    d("m11g2-d17", "learning_section", "Embedded systems experience is required.", "LEARNING", True,
      expect_tag="embedded-systems-design", expect_necessity="REQUIRED",
      notes="explicit local marker preserved even under a LEARNING heading"),

    # --- Category 8: unsectioned postings (section=None, doc has NO headings at all) ---
    d("m11g2-d18", "unsectioned_document", "Strong understanding of concurrency.", None, False,
      expect_tag="concurrency", expect_necessity="REQUIRED",
      notes="Milestone 6B's own 'no section at all -> default REQUIRED' policy preserved"),
    d("m11g2-d19", "unsectioned_document", "Experience with embedded systems.", None, False,
      expect_tag="embedded-systems-design", expect_necessity="REQUIRED"),
    d("m11g2-d20", "unsectioned_document", "Knowledge of control systems.", None, False,
      expect_tag="control-systems", expect_necessity="REQUIRED"),

    # --- Category 9: explicit local necessity conflicting with section defaults ---
    d("m11g2-d21", "local_overrides_section", "Distributed systems experience is preferred.", "REQUIRED", True,
      expect_tag="distributed-systems", expect_necessity="PREFERRED"),
    d("m11g2-d22", "local_overrides_section", "Concurrency experience is required.", "PREFERRED", True,
      expect_tag="concurrency", expect_necessity="REQUIRED"),
    d("m11g2-d23", "local_overrides_section", "Embedded systems experience is required.", "RESPONSIBILITY", True,
      expect_tag="embedded-systems-design", expect_necessity="REQUIRED"),
    d("m11g2-d24", "local_overrides_section", "Control systems experience is preferred.", "UNKNOWN", True,
      expect_tag="control-systems", expect_necessity="PREFERRED"),

    # --- Category 10: qualifications embedded in responsibilities ---
    d("m11g2-d25", "qualification_embedded_in_responsibility",
      "Candidates must have experience with distributed systems for this responsibility area.",
      "RESPONSIBILITY", True, expect_tag="distributed-systems", expect_necessity="REQUIRED"),
    d("m11g2-d26", "qualification_embedded_in_responsibility",
      "A strong candidate will have embedded systems experience, which is preferred for this duty.",
      "RESPONSIBILITY", True, expect_tag="embedded-systems-design", expect_necessity="PREFERRED"),

    # --- Category 17: conditional and negated requirements ---
    d("m11g2-d27", "negated_requirement", "No prior experience with embedded systems is necessary.",
      "REQUIRED", True, expect_decline=True, expect_reason="negation"),
    d("m11g2-d28", "conditional_requirement",
      "Experience with distributed systems is expected, unless a manager approves an exception.",
      "REQUIRED", True, expect_tag="distributed-systems", expect_necessity="REQUIRED",
      expect_applicability_present=True),
    d("m11g2-d29", "conditional_requirement",
      "Strong grasp of concurrency is expected, unless a manager approves an exception.",
      "RESPONSIBILITY", True, expect_tag="concurrency", expect_necessity=None,
      expect_applicability_present=True),

    # --- Category 18: OR groups and unsupported compound requirements (G1 safety under section context) ---
    d("m11g2-d30", "or_list_safety", "Experience with concurrency or distributed systems is required.",
      "REQUIRED", True, expect_decline=True, expect_reason="missing_contract"),
    d("m11g2-d31", "or_list_safety", "Experience with concurrency or culinary arts is preferred.",
      "PREFERRED", True, expect_decline=True, expect_reason="missing_contract"),
    d("m11g2-d32", "or_list_safety",
      "Strong grasp of concurrency, race conditions, or multithreading is expected.",
      "RESPONSIBILITY", True, expect_tag="concurrency", expect_necessity=None,
      notes="synonymous OR of the same tag still resolves safely, not declined"),

    # --- Category 19: cases where no necessity can safely be inferred (extra, dedicated) ---
    d("m11g2-d33", "necessity_unresolvable", "Experience with control systems.", "LEARNING", True,
      expect_tag="control-systems", expect_necessity=None),
    d("m11g2-d34", "necessity_unresolvable", "Knowledge of embedded systems.", None, True,
      expect_tag="embedded-systems-design", expect_necessity=None),

    # --- Extra: alias-based matches behave identically under section context ---
    d("m11g2-d35", "alias_match_required_section", "Knowledge of network protocols.", "REQUIRED", True,
      expect_tag="os-networking", expect_necessity="REQUIRED"),
    d("m11g2-d36", "alias_match_preferred_section", "Experience with bare-metal programming.", "PREFERRED", True,
      expect_tag="embedded-systems-design", expect_necessity="PREFERRED"),
]


def m(id_, category, description, targets):
    return {"id": id_, "category": category, "description": description, "targets": targets}


def t(target_text, *, expect_decline=False, expect_reason=None, expect_tag=None, expect_necessity=None):
    return {
        "target_text": target_text, "expect_decline": expect_decline,
        "expect_reason": expect_reason, "expect_tag": expect_tag, "expect_necessity": expect_necessity,
    }


MINI_POSTING_CONTROLS = [
    m("m11g2-m01", "employer_specific_required_heading",
      "Minimum Qualifications:\nStrong experience with distributed systems.\n",
      [t("Strong experience with distributed systems.", expect_tag="distributed-systems", expect_necessity="REQUIRED")]),

    m("m11g2-m02", "employer_specific_preferred_heading",
      "Nice to Have:\nKnowledge of concurrency.\n",
      [t("Knowledge of concurrency.", expect_tag="concurrency", expect_necessity="PREFERRED")]),

    m("m11g2-m03", "employer_specific_responsibility_heading",
      "What You'll Do:\nStrong ownership of the embedded systems rollout.\n",
      [t("Strong ownership of the embedded systems rollout.", expect_tag="embedded-systems-design", expect_necessity=None)]),

    m("m11g2-m04", "required_preferred_transition",
      "Requirements:\nExperience with distributed systems.\n\nPreferred Qualifications:\nKnowledge of concurrency.\n",
      [
          t("Experience with distributed systems.", expect_tag="distributed-systems", expect_necessity="REQUIRED"),
          t("Knowledge of concurrency.", expect_tag="concurrency", expect_necessity="PREFERRED"),
      ]),

    m("m11g2-m05", "blank_lines_between_heading_and_content",
      "Requirements:\n\n\nExperience with distributed systems.\n",
      [t("Experience with distributed systems.", expect_tag="distributed-systems", expect_necessity="REQUIRED")]),

    m("m11g2-m06", "wrapped_qualification_across_lines",
      "Requirements:\nStrong experience with\ndistributed systems.\n",
      [t("Strong experience with\ndistributed systems.", expect_tag="distributed-systems", expect_necessity="REQUIRED")]),

    m("m11g2-m07", "bulleted_list_under_heading",
      "Requirements:\n- Strong experience with distributed systems.\n- Knowledge of concurrency.\n",
      [
          t("Strong experience with distributed systems.", expect_tag="distributed-systems", expect_necessity="REQUIRED"),
          t("Knowledge of concurrency.", expect_tag="concurrency", expect_necessity="REQUIRED"),
      ]),

    m("m11g2-m08", "unsupported_unknown_heading",
      "Additional Information:\nExperience with embedded systems.\n",
      [t("Experience with embedded systems.", expect_tag="embedded-systems-design", expect_necessity=None)]),

    m("m11g2-m08b", "unsupported_unknown_heading_with_local_marker",
      "Additional Information:\nEmbedded systems experience is required.\n",
      [t("Embedded systems experience is required.", expect_tag="embedded-systems-design", expect_necessity="REQUIRED")]),

    m("m11g2-m09", "mixed_technical_and_nontechnical_in_same_section",
      "Requirements:\n- Strong experience with distributed systems.\n- Bachelor's degree in Computer Science.\n",
      [
          t("Strong experience with distributed systems.", expect_tag="distributed-systems", expect_necessity="REQUIRED"),
          t("Bachelor's degree in Computer Science.", expect_decline=True, expect_reason="no_competency_language"),
      ]),
]


def main() -> None:
    payload = {
        "corpus_version": "m11g2-dev:v1",
        "annotation_provenance": (
            "Self-authored synthetic controls, no third-party text. Expected outcomes frozen "
            "BEFORE any production or offline-extractor code was modified for Milestone 11-G2. "
            "direct_controls exercise the new section-aware necessity logic directly via a "
            "hand-specified (section_kind, document_has_recognized_heading) pair; "
            "mini_posting_controls run the REAL, unmodified segment_description() over a genuine "
            "multi-line mini-posting to confirm end-to-end plumbing (heading -> Claim.section_kind "
            "-> offline extractor)."
        ),
        "direct_controls": DIRECT_CONTROLS,
        "mini_posting_controls": MINI_POSTING_CONTROLS,
    }
    OUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")
    total_targets = len(DIRECT_CONTROLS) + sum(len(mp["targets"]) for mp in MINI_POSTING_CONTROLS)
    print(f"Wrote {len(DIRECT_CONTROLS)} direct controls + {len(MINI_POSTING_CONTROLS)} mini-postings "
          f"({sum(len(mp['targets']) for mp in MINI_POSTING_CONTROLS)} targets) "
          f"= {total_targets} total evaluated assertions -> {OUT_PATH}")


if __name__ == "__main__":
    main()
