"""Milestone 11-G7 Phase 2 -- builds the independently-authored,
synthetic section-boundary-integrity gold corpus and writes it to
`evaluation/m11g7/boundary_controls.json`.

Evaluation-only. Every control's text is hand-authored for this
milestone (synthetic, generic -- no real-posting provenance/privacy
concerns, same discipline as M11-G6's corpus). Gold is authored and
frozen BEFORE any candidate-fix simulation runs against it.

Root cause under investigation: `_classify_heading_line()`'s fixed
`word_count > 7: return None` shape gate rejects ANY heading-shaped
line exceeding 7 words regardless of how strong its other structural
signal is (colon/ALL-CAPS/Markdown) -- the EXACT shape that already
gates the separate "weak-signal-without-family-corroboration" rule
elsewhere in the same function. When a genuine, long heading is
misjudged as ordinary content, `current_kind` (single forward-carrying
loop state) never updates, so whatever section was open BEFORE it
leaks across the boundary into content AFTER it. Confirmed, by direct
execution (not assumed), to have THREE distinct severity tiers
depending on what `current_kind` was stale-carrying:

  - UNKNOWN carry-forward: produces a diagnostic `UnparsedClaim` at
    worst (necessity=None) -- never scored. LOW severity (G5/G6's own
    finding).
  - REQUIRED/PREFERRED carry-forward: can fabricate an ASSESSABLE,
    SCORED false `JobRequirement` (necessity=REQUIRED/PREFERRED) from
    pure responsibility/duty prose that happens to mention a real
    technology -- confirmed directly to produce a non-None
    `alignment_score` from a sentence that was never a qualification at
    all. HIGH severity.
  - SKIP carry-forward: can SILENTLY SUPPRESS a genuine, explicitly
    locally-marked REQUIRED qualification in the FOLLOWING real section
    entirely (zero claims, zero diagnostics) -- the same failure mode
    M11-G5 originally found, triggered by heading LENGTH instead of
    vocabulary collision. HIGH severity.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = REPO_ROOT / "evaluation" / "m11g7" / "boundary_controls.json"

CONTROLS: list[dict] = []


def add(id_, category, heading_line, body_lines, expected_heading_kind,
        word_count, has_strong_shape_signal, rationale, body_qualifications,
        severity_tier=None):
    CONTROLS.append({
        "id": id_,
        "category": category,
        "heading_line": heading_line,
        "body_lines": body_lines,
        "expected_heading_kind": expected_heading_kind,
        "heading_word_count": word_count,
        "has_strong_shape_signal": has_strong_shape_signal,
        "rationale": rationale,
        "severity_tier": severity_tier,
        "body_qualifications": body_qualifications,
    })


# 1. Short genuine headings (<=7 words) -- baseline, must never regress.
add("m11g7-001-short-required-colon", "short_genuine_heading_baseline",
    "Required Qualifications:", ["Experience with Python."],
    "REQUIRED", 2, True,
    "Already-correct 2-word heading, baseline positive control any fix must preserve.",
    [{"text": "Experience with Python.", "is_genuine_qualification": True,
      "expected_necessity": "REQUIRED", "should_enter_assessment": True}])

add("m11g7-002-short-responsibility-colon", "short_genuine_heading_baseline",
    "What You'll Do:", ["Design backend services."],
    "RESPONSIBILITY", 3, True,
    "Already-correct 3-word heading, baseline positive control.",
    [{"text": "Design backend services.", "is_genuine_qualification": False,
      "expected_necessity": None, "should_enter_assessment": False}])

add("m11g7-003-exactly-seven-words", "short_genuine_heading_baseline",
    "What You Will Be Responsible For Delivering:", ["Lead the platform migration."],
    "RESPONSIBILITY", 7, True,
    "Exactly at the current 7-word boundary -- must remain classified "
    "identically under any candidate fix (the fix only changes behavior "
    "ABOVE this boundary, never at or below it).",
    [{"text": "Lead the platform migration.", "is_genuine_qualification": False,
      "expected_necessity": None, "should_enter_assessment": False}])

# 2. Long genuine headings, strong shape signal -- the target defect family.
add("m11g7-004-long-responsibility-colon-9words", "long_genuine_heading_colon",
    "What You Will Be Able To Build And Own:", ["Design backend services."],
    "UNKNOWN", 9, True,
    "9-word colon-terminated heading (the exact M11-G5 p03 shape, "
    "reconstructed generically) -- currently NOT_A_HEADING (exceeds "
    "the 7-word cap). Confirmed by direct execution of "
    "`_matched_heading_families`: this phrase does NOT match "
    "`_RESPONSIBILITY_ROOT` at all (which requires the bare word "
    "'respons*', 'duties'/'duty', the EXACT phrase 'what you(\\'ll| "
    "will) do', 'the role', or 'day in this role' -- 'build and own' "
    "matches none of these) -- zero family, strong signal (colon) -> "
    "UNKNOWN once the word-count gate is fixed, not RESPONSIBILITY.",
    [{"text": "Design backend services.", "is_genuine_qualification": False,
      "expected_necessity": None, "should_enter_assessment": False}])

add("m11g7-005-long-required-colon-10words", "long_genuine_heading_colon",
    "Required Technical Skills And Experience For This Senior Role:",
    ["Experience with distributed systems is required."],
    "REQUIRED", 9, True,
    "9-word colon-terminated REQUIRED heading -- currently UNKNOWN or "
    "NOT_A_HEADING depending on family match, should resolve to REQUIRED.",
    [{"text": "Experience with distributed systems is required.",
      "is_genuine_qualification": True, "expected_necessity": "REQUIRED",
      "should_enter_assessment": True}])

add("m11g7-006-long-preferred-colon-8words", "long_genuine_heading_colon",
    "Additional Skills That Would Be Nice To Have:",
    ["Familiarity with Kubernetes."],
    "PREFERRED", 8, True,
    "8-word colon-terminated PREFERRED heading (via the 'nice to have' "
    "root) -- currently exceeds the cap.",
    [{"text": "Familiarity with Kubernetes.", "is_genuine_qualification": True,
      "expected_necessity": "PREFERRED", "should_enter_assessment": True}])

add("m11g7-007-long-qualification-colon-9words", "long_genuine_heading_colon",
    "The Qualifications We Are Looking For In This Candidate:",
    ["A degree in Computer Science is required."],
    "REQUIRED", 9, True,
    "9-word colon-terminated heading. Contains 'qualifications' "
    "(QUALIFICATION_ROOT) and a candidate-seeking continuation ('looking "
    "for', the G6-added CANDIDATE_PROFILE_ROOT signal), but NOT the "
    "'who we are' trigram, so NON_QUALIFICATION never fires here at "
    "all -- confirmed by direct execution of `_matched_heading_families` "
    "on this exact text: exactly one family (REQUIRED) fires. Expected "
    "REQUIRED once the word-count gate is fixed, not UNKNOWN.",
    [{"text": "A degree in Computer Science is required.",
      "is_genuine_qualification": True, "expected_necessity": "REQUIRED",
      "should_enter_assessment": True}],
    )

# 3. Long headings, Markdown/ALL-CAPS strong signal.
add("m11g7-008-long-markdown-atx-9words", "long_genuine_heading_markdown",
    "## What You Will Be Able To Build And Own", ["Design backend services."],
    "UNKNOWN", 9, True,
    "Markdown ATX variant of control 004 (see its corrected rationale "
    "-- zero family match, expected UNKNOWN, not RESPONSIBILITY).",
    [{"text": "Design backend services.", "is_genuine_qualification": False,
      "expected_necessity": None, "should_enter_assessment": False}])

add("m11g7-009-long-markdown-bold-9words", "long_genuine_heading_markdown",
    "**What You Will Be Able To Build And Own**", ["Design backend services."],
    "UNKNOWN", 9, True,
    "Markdown-bold variant of control 004 (zero family match, "
    "expected UNKNOWN, not RESPONSIBILITY).",
    [{"text": "Design backend services.", "is_genuine_qualification": False,
      "expected_necessity": None, "should_enter_assessment": False}])

add("m11g7-010-long-allcaps-9words", "long_genuine_heading_allcaps",
    "WHAT YOU WILL BE ABLE TO BUILD AND OWN", ["Design backend services."],
    "UNKNOWN", 9, True,
    "ALL-CAPS variant of control 004 (no colon at all; zero family "
    "match, expected UNKNOWN, not RESPONSIBILITY).",
    [{"text": "Design backend services.", "is_genuine_qualification": False,
      "expected_necessity": None, "should_enter_assessment": False}])

# 4. Long heading, strong signal, but NO family root -- must resolve to
#    UNKNOWN once recognized, never SKIP, never a forced default.
add("m11g7-011-long-no-family-colon-9words", "long_heading_no_family_root",
    "Some Additional Context About This Particular Opening:",
    ["You will enjoy flexible hours and great benefits."],
    "UNKNOWN", 7, True,
    "9-word colon-terminated heading matching NO family root at all -- "
    "already-existing 'zero families + strong shape signal -> UNKNOWN' "
    "rule should apply once recognized as heading-shaped; must not "
    "become SKIP, REQUIRED, or any forced default.",
    [{"text": "You will enjoy flexible hours and great benefits.",
      "is_genuine_qualification": False, "expected_necessity": None,
      "should_enter_assessment": False}])

# 5. Long heading, WEAK shape signal only (bare title-case, no colon) --
#    adversarial: must remain NOT_A_HEADING even under any fix, since
#    this is the exact unreliable shape the cap was built to guard.
add("m11g7-012-long-weak-signal-no-colon", "long_weak_signal_heading",
    "What You Will Be Able To Build And Own",
    ["Design backend services."],
    "NOT_A_HEADING", 9, False,
    "Same 9-word phrase as control 004 but with NO colon/ALL-CAPS/"
    "Markdown -- bare plain title-case only. Must remain NOT_A_HEADING "
    "under ANY safe fix: a long, weak-signal, family-root-having phrase "
    "is not meaningfully more trustworthy than a short one once the "
    "colon/caps/markdown corroboration is absent (this control DOES "
    "match RESPONSIBILITY_ROOT, unlike the zero-family weak-signal case "
    "below -- adversarial precisely because it has a family match AND "
    "weak shape, testing whether a fix accidentally lets family-match "
    "alone override the weak-signal exclusion for LONG phrases).",
    [{"text": "Design backend services.", "is_genuine_qualification": False,
      "expected_necessity": None, "should_enter_assessment": False}])

add("m11g7-013-long-weak-signal-no-family", "long_weak_signal_heading",
    "Some Additional Context About This Particular Opening",
    ["You will enjoy flexible hours and great benefits."],
    "NOT_A_HEADING", 7, False,
    "Same phrase as control 011 but with the colon removed -- bare "
    "weak signal, zero family match. Must remain NOT_A_HEADING under "
    "any fix (already the existing, correct, pre-G7 behavior).",
    [{"text": "You will enjoy flexible hours and great benefits.",
      "is_genuine_qualification": False, "expected_necessity": None,
      "should_enter_assessment": False}])

# 6. THE critical adversarial category: long colon-terminated LEAD-IN
#    phrases that are semantically NOT section headings at all (they
#    introduce a sub-list within an ALREADY-OPEN section) but are
#    structurally indistinguishable from a long heading once the
#    word-count gate alone is relaxed.
add("m11g7-014-leadin-not-heading-required-section", "long_colon_leadin_not_a_heading",
    "Required Qualifications:",
    ["Our ideal candidate will bring deep expertise across the following broad set of complementary technical and professional areas:",
     "Python"],
    "REQUIRED", 2, True,
    "The SECOND line is a long (17-word), colon-terminated, otherwise "
    "heading-SHAPED lead-in sentence introducing a one-word-per-line "
    "sub-list ('Python') WITHIN the already-open REQUIRED section -- "
    "semantically a claim/lead-in, not a new section boundary. A naive "
    "'just raise the word cap' fix risks reclassifying this as a NEW "
    "heading (likely UNKNOWN, since it matches no REQUIRED/PREFERRED/"
    "RESPONSIBILITY root), which would WRONGLY demote 'Python' on the "
    "next line out of the REQUIRED section it is actually inside of. "
    "The existing sentence-terminal-punctuation guard does NOT exclude "
    "this (it ends in ':', not '.'/'?'/'!') and `_has_inline_colon_list` "
    "does not fire either (no comma-separated list on the SAME line) -- "
    "this is deliberately the hardest, most realistic adversarial case.",
    [{"text": "Python", "is_genuine_qualification": True,
      "expected_necessity": "REQUIRED", "should_enter_assessment": True,
      "note": "Must remain REQUIRED -- the lead-in sentence must NOT be "
              "treated as a heading that resets current_kind."}])

add("m11g7-015-leadin-not-heading-responsibility-section", "long_colon_leadin_not_a_heading",
    "What You'll Do:",
    ["You will partner closely with product, design, and other engineering teams across the following major functional areas of ownership:",
     "Backend services"],
    "RESPONSIBILITY", 3, True,
    "Same adversarial shape as control 014, inside a RESPONSIBILITY "
    "section instead -- the 18-word lead-in must not reset current_kind "
    "away from RESPONSIBILITY before 'Backend services' is reached.",
    [{"text": "Backend services", "is_genuine_qualification": False,
      "expected_necessity": None, "should_enter_assessment": False}])

# 7. Ordinary long prose sentences (sentence-terminal punctuation) --
#    already safely excluded by the EXISTING gate; confirm unaffected.
add("m11g7-016-ordinary-long-prose-period", "ordinary_long_prose_sentence",
    None,
    ["We are looking for a software engineer who can work independently and collaborate effectively across multiple distributed teams."],
    "NOT_A_HEADING", 19, False,
    "A 19-word ordinary sentence ending in a period -- already excluded "
    "by the pre-existing sentence-terminal-punctuation check regardless "
    "of word count; must remain unaffected by any word-count-focused fix.",
    [{"text": "We are looking for a software engineer who can work independently and collaborate effectively across multiple distributed teams.",
      "is_genuine_qualification": False, "expected_necessity": None,
      "should_enter_assessment": False,
      "note": "No heading line in this control; this is a standalone "
              "sentence under the M6B 'no section at all' default, "
              "declined by _looks_like_requirement (no signal word)."}])

# 8. Bullet list items -- must never become headings regardless of length.
add("m11g7-017-long-bulleted-item", "bullet_list_item_long",
    "Required Qualifications:",
    ["- Experience with distributed systems, cloud infrastructure, container orchestration, and modern CI/CD pipelines across production environments"],
    "REQUIRED", 2, True,
    "A long (14-word) BULLETED line -- `_BULLET_PREFIX` already "
    "excludes any bulleted line from heading classification regardless "
    "of word count; confirms this exclusion is unaffected by any fix.",
    [{"text": "Experience with distributed systems, cloud infrastructure, container orchestration, and modern CI/CD pipelines across production environments",
      "is_genuine_qualification": True, "expected_necessity": "REQUIRED",
      "should_enter_assessment": True}])

# 9. Severity-tier carry-forward scenarios, each isolated and testable.
add("m11g7-018-severity-unknown-carryforward", "severity_tier_unknown_carryforward",
    "Who We Are Looking For:",
    ["Someone with experience thriving in ambiguity.",
     "What You Will Be Able To Build And Own:",
     "Mentor junior engineers on architecture reviews."],
    "UNKNOWN", 5, True,
    "LOW-severity tier. `heading_word_count`/`has_strong_shape_signal` "
    "describe `heading_line` itself (the FIRST heading, 5 words, "
    "already correctly UNKNOWN via M11-G6's fix) -- the actual G7 "
    "target defect is the SECOND, embedded heading ('What You Will Be "
    "Able To Build And Own:', 9 words, inside body_lines). Before any "
    "G7 fix, current_kind stays UNKNOWN across that second heading, so "
    "the final sentence is at worst a diagnostic UnparsedClaim "
    "(confirmed safe: necessity=None, never scored).",
    [{"text": "Someone with experience thriving in ambiguity.", "is_genuine_qualification": True,
      "expected_necessity": "UNKNOWN", "should_enter_assessment": True},
     {"text": "Mentor junior engineers on architecture reviews.",
      "is_genuine_qualification": False, "expected_necessity": None,
      "should_enter_assessment": False,
      "note": "A responsibility sentence that may be admitted as a "
              "diagnostic (necessity=None) if it passes the generic "
              "signal gate ('mentor') -- diagnostic-only, never scored, "
              "regardless of this fix."}],
    severity_tier="LOW_diagnostic_only")

add("m11g7-019-severity-required-carryforward-HIGH", "severity_tier_required_carryforward",
    "Requirements:",
    ["Experience with distributed systems is required.",
     "What You Will Be Able To Build And Own In This Role:",
     "Mentor junior engineers while writing production Python and Go services daily."],
    "REQUIRED", 1, True,
    "HIGH-severity tier, CONFIRMED by direct execution (not assumed). "
    "`heading_word_count`/`has_strong_shape_signal` describe "
    "`heading_line` itself ('Requirements:', 1 word, already correctly "
    "REQUIRED) -- the actual G7 target defect is the SECOND, embedded "
    "heading (10 words, inside body_lines): currently NOT_A_HEADING, "
    "so current_kind stays REQUIRED across it -- the responsibility "
    "sentence becomes an ASSESSABLE, SCORED JobRequirement "
    "(necessity=REQUIRED, concept_id=language.python, "
    "github_observability=STRONGLY_OBSERVABLE), producing a non-None "
    "alignment_score from pure duty prose. This is the single most "
    "severe confirmed finding of this milestone.",
    [{"text": "Experience with distributed systems is required.",
      "is_genuine_qualification": True, "expected_necessity": "REQUIRED",
      "should_enter_assessment": True},
     {"text": "Mentor junior engineers while writing production Python and Go services daily.",
      "is_genuine_qualification": False, "expected_necessity": None,
      "should_enter_assessment": False,
      "note": "MUST NOT become a scored JobRequirement under any safe "
              "fix -- confirmed to currently do so."}],
    severity_tier="HIGH_fabricated_assessable_requirement")

add("m11g7-020-severity-skip-carryforward-HIGH", "severity_tier_skip_carryforward",
    "About Us:",
    ["We are a fast growing company in the logistics space.",
     "Why This Role Matters To Our Growing Engineering Team:",
     "Experience with Python and distributed systems is required."],
    "SKIP", 2, True,
    "HIGH-severity tier, CONFIRMED by direct execution (not assumed). "
    "`heading_word_count`/`has_strong_shape_signal` describe "
    "`heading_line` itself ('About Us:', 2 words, already correctly "
    "SKIP) -- the actual G7 target defect is the SECOND, embedded "
    "heading (9 words, inside body_lines): currently NOT_A_HEADING, so "
    "current_kind stays SKIP across it -- the explicit, locally-marked "
    "genuine REQUIRED qualification on the final line is SILENTLY, "
    "TOTALLY SUPPRESSED (0 requirements, 0 diagnostics) -- the exact "
    "same failure mode M11-G5 originally found, triggered here by "
    "heading LENGTH rather than vocabulary collision.",
    [{"text": "We are a fast growing company in the logistics space.",
      "is_genuine_qualification": False, "expected_necessity": None,
      "should_enter_assessment": False},
     {"text": "Experience with Python and distributed systems is required.",
      "is_genuine_qualification": True, "expected_necessity": "REQUIRED",
      "should_enter_assessment": True,
      "note": "MUST be recovered under any safe fix -- confirmed to "
              "currently be silently lost entirely."}],
    severity_tier="HIGH_silent_total_suppression")

# 10. Section-transition correctness -- a long heading correctly resets
#     state to a NEW real family once recognized.
add("m11g7-021-transition-long-heading-resets-correctly", "section_transition_correctness",
    "Preferred Qualifications:",
    ["Experience with Kubernetes.",
     "Other Responsibilities You Will Take On:",
     "Mentor junior engineers."],
    "PREFERRED", 2, True,
    "`heading_word_count`/`has_strong_shape_signal` describe "
    "`heading_line` itself ('Preferred Qualifications:', 2 words, "
    "already correctly PREFERRED). The SECOND, embedded heading ('Other "
    "Responsibilities You Will Take On:', 6 words -- AT, not over, the "
    "7-word cap, confirmed by direct execution to already correctly "
    "resolve to RESPONSIBILITY TODAY) correctly resets current_kind "
    "away from PREFERRED -- 'Mentor junior engineers.' correctly does "
    "NOT inherit PREFERRED necessity. A genuine POSITIVE control (not a "
    "defect row): confirms clean section-transition behavior already "
    "works for a heading just inside the cap, which any G7 fix must "
    "continue to preserve. (v1 of this control used an 8-word second "
    "heading and mischaracterized it as already-working when it was in "
    "fact ALSO defective -- corrected before freeze via direct "
    "verification, see m11g7-030 for that same PREFERRED-tier defect "
    "shape covered properly as a defect row instead.)",
    [{"text": "Experience with Kubernetes.", "is_genuine_qualification": True,
      "expected_necessity": "PREFERRED", "should_enter_assessment": True},
     {"text": "Mentor junior engineers.", "is_genuine_qualification": False,
      "expected_necessity": None, "should_enter_assessment": False}])

# 11. Unicode and punctuation variants of long headings.
add("m11g7-022-long-heading-em-dash", "unicode_and_punctuation_variants",
    "What You Will Be Able To Build And Own—", ["Design backend services."],
    "NOT_A_HEADING", 9, False,
    "Em-dash-terminated (no bare colon) variant of control 004. Unlike "
    "the M11-G6 em-dash finding (where a family DID match, via 'who we "
    "are'), this phrase matches ZERO families (confirmed directly) -- "
    "so weak shape signal + zero families triggers the "
    "weak-signal-without-corroboration exclusion regardless of word "
    "count, correctly remaining NOT_A_HEADING under ANY safe G7 fix "
    "(a useful contrast with control 004's colon-terminated form, "
    "which DOES gain strong-signal corroboration from the colon alone).",
    [{"text": "Design backend services.", "is_genuine_qualification": False,
      "expected_necessity": None, "should_enter_assessment": False}])

add("m11g7-023-long-heading-nbsp", "unicode_and_punctuation_variants",
    "What You Will Be Able To Build And Own:",
    ["Design backend services."],
    "UNKNOWN", 9, True,
    "Real non-breaking-space (U+00A0) variant of control 004 -- "
    "`_RESPONSIBILITY_ROOT`'s `what you(?:'ll| will) do` pattern "
    "requires literal ASCII spaces and does NOT match 'what you will "
    "do' when NBSP-separated (mirrors the M11-G6 NBSP finding "
    "precisely) -- but this heading doesn't contain the word 'do' at "
    "all regardless, so it is a zero-family, strong-signal (colon) "
    "case either way, expected UNKNOWN, not RESPONSIBILITY, once "
    "recognized as heading-shaped -- flagged for direct verification.",
    [{"text": "Design backend services.", "is_genuine_qualification": False,
      "expected_necessity": None, "should_enter_assessment": False}])

# 12. Mixed qualification content after a long, now-fixed heading --
#     confirms substantive recovery, not just classification.
add("m11g7-024-mixed-qualifications-after-long-heading", "mixed_qualification_after_long_heading",
    "Who We Are Looking For In This Particular Role:",
    ["A degree in Computer Science is required.",
     "Experience with Kubernetes is preferred."],
    "UNKNOWN", 9, True,
    "9-word candidate-profile heading (contains the M11-G6-fixed "
    "'looking for' exclusion signal too, but no SKIP-family root fires "
    "here at all since 'who we are' is absent -- 'Who We' alone is not "
    "the trigram) -- zero family match, strong signal (colon) -> "
    "UNKNOWN once recognized. Both body lines carry explicit local "
    "markers and must resolve to their own stated necessity regardless "
    "of the UNKNOWN section default.",
    [{"text": "A degree in Computer Science is required.",
      "is_genuine_qualification": True, "expected_necessity": "REQUIRED",
      "should_enter_assessment": True},
     {"text": "Experience with Kubernetes is preferred.",
      "is_genuine_qualification": True, "expected_necessity": "PREFERRED",
      "should_enter_assessment": True}])

# 13. Narrative section, long heading.
add("m11g7-025-long-narrative-heading", "narrative_sections",
    "A Little More About Our Company And What We Value:",
    ["We believe in transparency and continuous learning."],
    "UNKNOWN", 10, True,
    "10-word narrative-flavored heading. `_NON_QUALIFICATION_ROOT`'s "
    "`^about\\b` is anchored to the very FIRST character of content, "
    "which here is 'A' (from 'A Little More...'), not 'About' -- "
    "confirmed directly: zero family match. Strong signal (colon) + "
    "zero family -> UNKNOWN once length-fixed, NOT SKIP (contrast with "
    "control 026, where 'About' genuinely starts the content and "
    "correctly resolves to SKIP) -- a useful adversarial pair showing "
    "the anchor is positional, not merely 'contains the word about'.",
    [{"text": "We believe in transparency and continuous learning.",
      "is_genuine_qualification": False, "expected_necessity": None,
      "should_enter_assessment": False}])

add("m11g7-026-long-narrative-heading-anchored", "narrative_sections",
    "About Our Company Culture And What We Value Most:",
    ["We believe in transparency and continuous learning."],
    "SKIP", 9, True,
    "9-word narrative/SKIP heading with '^about' correctly anchored at "
    "the very start -- should resolve to SKIP once recognized, "
    "currently NOT_A_HEADING.",
    [{"text": "We believe in transparency and continuous learning.",
      "is_genuine_qualification": False, "expected_necessity": None,
      "should_enter_assessment": False}])

# 14. Already-recognized long headings elsewhere in the live corpus --
#     sanity cross-check (not a new control, a reference note).
add("m11g7-027-degenerate-very-long-colon-line", "adversarial_degenerate_cases",
    None,
    ["In order to be considered for this role you must demonstrate a strong track record of delivering complex technical projects on time and within budget while managing cross-functional stakeholders across the organization and communicating clearly with both technical and non-technical audiences:"],
    "NOT_A_HEADING", 42, False,
    "A deliberately DEGENERATE case: a 42-word run-on clause that "
    "happens to end in a bare colon (no sentence-terminal punctuation) "
    "-- structurally passes the colon/strong-signal check but is "
    "obviously not a heading by any reasonable standard. Tests whether "
    "any candidate fix needs an UPPER bound even for strong-signal "
    "lines, or whether removing the cap entirely for strong signals "
    "would wrongly heading-ify this. No heading_line (treated as a "
    "standalone body line) so its OWN classification is checked "
    "directly in the strategy-comparison script, not via this field.",
    [{"text": "", "is_genuine_qualification": False, "expected_necessity": None,
      "should_enter_assessment": False,
      "note": "Placeholder -- this control's real check is the heading "
              "classification of its own single line, done directly in "
              "the Phase 3 simulation, not via body-line admission."}])

add("m11g7-028-eight-word-boundary-plus-one", "long_genuine_heading_colon",
    "Technical Requirements And Qualifications Expected Of All Applicants:",
    ["Experience with SQL is required."],
    "REQUIRED", 8, True,
    "8 words -- one past the current cap, a minimal boundary-plus-one "
    "case distinct from the 9/10-word controls above.",
    [{"text": "Experience with SQL is required.", "is_genuine_qualification": True,
      "expected_necessity": "REQUIRED", "should_enter_assessment": True}])

add("m11g7-029-twelve-word-heading", "long_genuine_heading_colon",
    "A Full And Complete List Of All Required Technical Qualifications For This Position:",
    ["Experience with Go is required."],
    "REQUIRED", 13, True,
    "13-word heading -- tests whether any proposed new cap (if the "
    "chosen strategy keeps a bounded, raised cap rather than removing "
    "it for strong signals) is itself wide enough, or whether this "
    "stays correctly/safely NOT_A_HEADING under a bounded-raise strategy.",
    [{"text": "Experience with Go is required.", "is_genuine_qualification": True,
      "expected_necessity": "REQUIRED", "should_enter_assessment": True}])


# 15. Additional severity-tier variants (PREFERRED, LEARNING carry-forward).
add("m11g7-030-severity-preferred-carryforward", "severity_tier_required_carryforward",
    "Preferred Qualifications:",
    ["Experience with Kubernetes is preferred.",
     "Additional Things You Might End Up Doing Occasionally:",
     "Mentor junior engineers while writing production Rust services."],
    "PREFERRED", 2, True,
    "`heading_word_count`/`has_strong_shape_signal` describe "
    "`heading_line` itself ('Preferred Qualifications:', 2 words, "
    "already correctly PREFERRED). PREFERRED-tier variant of the "
    "HIGH-severity carry-forward: the SECOND, embedded heading (8 "
    "words, confirmed NOT_A_HEADING by direct execution) means "
    "current_kind stays PREFERRED across it, so the responsibility "
    "sentence could become a fabricated, ASSESSABLE PREFERRED "
    "requirement (concept_id=language.rust) -- "
    "measured directly in Phase 4, not assumed identical to the "
    "REQUIRED case.",
    [{"text": "Experience with Kubernetes is preferred.", "is_genuine_qualification": True,
      "expected_necessity": "PREFERRED", "should_enter_assessment": True},
     {"text": "Mentor junior engineers while writing production Rust services.",
      "is_genuine_qualification": False, "expected_necessity": None,
      "should_enter_assessment": False,
      "note": "MUST NOT become a scored requirement under any safe fix."}],
    severity_tier="HIGH_fabricated_assessable_requirement")

add("m11g7-031-severity-learning-carryforward", "severity_tier_unknown_carryforward",
    "Skills You Will Learn On The Job:",
    ["You will grow your distributed-systems expertise.",
     "What You Will Be Able To Build And Own Over Time:",
     "Mentor junior engineers on system design."],
    "LEARNING", 7, True,
    "`heading_word_count`/`has_strong_shape_signal` describe "
    "`heading_line` itself ('Skills You Will Learn On The Job:', 7 "
    "words, AT the cap, matches `_LEARNING_ROOT`'s 'skills you will "
    "learn' phrase, confirmed by direct execution to already correctly "
    "resolve to LEARNING today). The SECOND, embedded heading (10 "
    "words) is the actual defect. LEARNING-tier variant: LEARNING "
    "content never receives a default "
    "necessity either (same as UNKNOWN) -- confirms the carry-forward "
    "from a stale LEARNING state is also LOW severity, diagnostic-only.",
    [{"text": "You will grow your distributed-systems expertise.",
      "is_genuine_qualification": False, "expected_necessity": None,
      "should_enter_assessment": False},
     {"text": "Mentor junior engineers on system design.",
      "is_genuine_qualification": False, "expected_necessity": None,
      "should_enter_assessment": False}],
    severity_tier="LOW_diagnostic_only")

# 16. Inline-colon-list exclusion -- already excluded regardless of word count.
add("m11g7-032-long-inline-colon-list", "ordinary_long_prose_sentence",
    "Required Qualifications:",
    ["Experience with the following widely used modern technologies: Python, Go, Rust, Kubernetes"],
    "REQUIRED", 2, True,
    "The body line itself (not the heading) contains an inline colon "
    "followed by a comma-separated list -- already excluded from EVER "
    "being misclassified as a heading by `_has_inline_colon_list` "
    "regardless of word count; confirms this exclusion is unaffected "
    "by any word-count-focused fix.",
    [{"text": "Experience with the following widely used modern technologies: Python, Go, Rust, Kubernetes",
      "is_genuine_qualification": True, "expected_necessity": "REQUIRED",
      "should_enter_assessment": True}])

# 17. More bullet-list variants (numbered, asterisk).
add("m11g7-033-long-numbered-bullet", "bullet_list_item_long",
    "Required Qualifications:",
    ["1. Experience with distributed systems, container orchestration, and modern continuous delivery pipelines"],
    "REQUIRED", 2, True,
    "A long (12-word) NUMBERED bullet -- `_BULLET_PREFIX` already "
    "matches numbered markers too; confirms unaffected by any fix.",
    [{"text": "Experience with distributed systems, container orchestration, and modern continuous delivery pipelines",
      "is_genuine_qualification": True, "expected_necessity": "REQUIRED",
      "should_enter_assessment": True}])

# 18. Markdown long heading with NO family root.
add("m11g7-034-long-markdown-no-family", "long_heading_no_family_root",
    "## Some Additional Context About This Particular Opening",
    ["You will enjoy flexible hours and great benefits."],
    "UNKNOWN", 7, True,
    "Markdown ATX variant of control 011 -- zero family match, strong "
    "signal via Markdown -- should resolve to UNKNOWN once recognized.",
    [{"text": "You will enjoy flexible hours and great benefits.",
      "is_genuine_qualification": False, "expected_necessity": None,
      "should_enter_assessment": False}])

# 19. Zero-width space Unicode variant.
add("m11g7-035-long-heading-zero-width-space", "unicode_and_punctuation_variants",
    "What You Will Be Able To Build And Own:",
    ["Design backend services."],
    "UNKNOWN", 9, True,
    "Zero-width-space (U+200B) variant of control 004 (zero family "
    "match, expected UNKNOWN, not RESPONSIBILITY -- see control 004's "
    "own corrected rationale) -- "
    "`_INVISIBLE_CHARS` already strips these during "
    "`_strip_heading_decoration` for classification purposes; confirms "
    "unaffected by any word-count fix (word count is computed on the "
    "ALREADY-stripped content).",
    [{"text": "Design backend services.", "is_genuine_qualification": False,
      "expected_necessity": None, "should_enter_assessment": False}])

# 20. Boundary case at exactly 7 words, weak signal, zero family (sanity).
add("m11g7-036-exactly-seven-weak-signal-zero-family", "long_weak_signal_heading",
    "Some Interesting Context About This Opening Today",
    ["You will enjoy flexible hours and great benefits."],
    "NOT_A_HEADING", 7, False,
    "Exactly 7 words (AT the boundary, not over it), weak signal, zero "
    "family -- already correctly NOT_A_HEADING today via the existing "
    "weak-signal-without-corroboration rule, unrelated to the word-"
    "count cap itself; must remain unaffected by any G7 fix (the fix "
    "only changes behavior for word_count > 7).",
    [{"text": "You will enjoy flexible hours and great benefits.",
      "is_genuine_qualification": False, "expected_necessity": None,
      "should_enter_assessment": False}])

# 21. Narrative section with a long lead-in to a benefits list (adversarial:
#     must not reset OUT of SKIP).
add("m11g7-037-leadin-not-heading-inside-skip-section", "long_colon_leadin_not_a_heading",
    "Why Join Us:",
    ["We offer a comprehensive and highly competitive total rewards package including the following notable highlights:",
     "Unlimited vacation"],
    "SKIP", 3, True,
    "A long (14-word) colon-terminated lead-in INSIDE an already-open "
    "SKIP (narrative/benefits) section -- must not be reclassified as a "
    "new heading under any fix, which would wrongly reset current_kind "
    "away from SKIP and risk admitting 'Unlimited vacation' as a "
    "diagnostic or (worse) a claim.",
    [{"text": "Unlimited vacation", "is_genuine_qualification": False,
      "expected_necessity": None, "should_enter_assessment": False,
      "note": "Must remain fully suppressed (SKIP) -- a benefits-list "
              "item, not a qualification, must never leak into "
              "assessment via a wrongly-reset section boundary."}])

# 22. G6+G7 interaction: a long compound heading combining the G6-fixed
#     candidate-profile vocabulary with a long overall phrase.
add("m11g7-038-g6-g7-interaction-long-compound", "adversarial_degenerate_cases",
    "Who We Are Looking For And What You Will Be Responsible For:",
    ["A degree in Computer Science is required.",
     "Mentor junior engineers on system design."],
    "RESPONSIBILITY", 12, True,
    "A 12-word compound heading combining the M11-G6-fixed 'who we "
    "are'+'looking for' exclusion AND the M11-G7 word-count cap in one "
    "line. Also contains 'Responsible', which DOES match "
    "`_RESPONSIBILITY_ROOT`'s bare `\\brespons\\w*\\b` alternative "
    "(confirmed directly -- a broader match than 'what you'll do' "
    "alone, missed in an earlier draft of this rationale). Exactly one "
    "family fires (RESPONSIBILITY); the G6 exclusion correctly prevents "
    "a SKIP mismatch that never would have fired anyway (no 'who we "
    "are' trigram here, only 'who we' + 'are looking for' separately). "
    "Confirms the two milestones' fixes compose safely -- a single, "
    "unambiguous family wins, no collision.",
    [{"text": "A degree in Computer Science is required.",
      "is_genuine_qualification": True, "expected_necessity": "REQUIRED",
      "should_enter_assessment": True},
     {"text": "Mentor junior engineers on system design.",
      "is_genuine_qualification": False, "expected_necessity": None,
      "should_enter_assessment": False}])

# 23. A second ordinary-long-prose control with no terminal punctuation at all.
add("m11g7-039-long-prose-no-terminal-punctuation", "ordinary_long_prose_sentence",
    None,
    ["We are looking for a software engineer who can work independently across distributed teams and own outcomes end to end"],
    "NOT_A_HEADING", 20, False,
    "A 20-word ordinary sentence with NO terminal punctuation at all "
    "(neither period nor colon) -- excluded purely by the word-count "
    "cap today (word_count > 7), NOT by the sentence-terminal-"
    "punctuation guard (which only fires on '.'/'?'/'!', never on "
    "absence of punctuation) and NOT by the colon-based strong-shape "
    "check (no colon present, so has_strong_shape_signal=False here, "
    "relying on word-count-gated weak-signal titlecase path) -- a "
    "distinct adversarial shape from control 016's period-terminated "
    "version, testing the weak-signal (not strong-signal) path "
    "specifically at long length.",
    [{"text": "We are looking for a software engineer who can work independently across distributed teams and own outcomes end to end",
      "is_genuine_qualification": False, "expected_necessity": None,
      "should_enter_assessment": False,
      "note": "Standalone sentence, no heading line, M6B 'no section' "
              "default REQUIRED hint but declined by "
              "_looks_like_requirement (no literal signal word present)."}])

# 24. A long LEARNING heading with strong signal, no carry-forward --
#     direct positive-recognition control (distinct from the
#     carry-forward test in control 031).
add("m11g7-040-long-learning-heading-direct", "long_genuine_heading_colon",
    "Skills And Technologies You Will Learn And Grow Into:",
    ["You will gain exposure to Kubernetes."],
    "LEARNING", 9, True,
    "9-word LEARNING heading (via 'learn' root) -- currently "
    "NOT_A_HEADING, should resolve to LEARNING once fixed; LEARNING "
    "content never gets a default necessity either way (same "
    "diagnostic-only guarantee as UNKNOWN).",
    [{"text": "You will gain exposure to Kubernetes.", "is_genuine_qualification": False,
      "expected_necessity": None, "should_enter_assessment": False}])

add("m11g7-041-long-required-markdown-bold-10words", "long_genuine_heading_markdown",
    "**Required Technical Skills And Experience For This Senior Role**",
    ["Experience with distributed systems is required."],
    "REQUIRED", 9, True,
    "Markdown-bold variant of control 005.",
    [{"text": "Experience with distributed systems is required.",
      "is_genuine_qualification": True, "expected_necessity": "REQUIRED",
      "should_enter_assessment": True}])

add("m11g7-042-fourteen-word-heading-upper-bound-probe", "adversarial_degenerate_cases",
    "A Complete And Thorough Overview Of Every Single Required Technical Qualification Expected:",
    ["Experience with C++ is required."],
    "REQUIRED", 12, True,
    "12-word heading, probing further toward a plausible upper bound "
    "than control 029's 13-word case with different wording -- used "
    "together to triangulate whether a bounded-raise strategy's chosen "
    "cap (if any) is wide enough for realistic long headings without "
    "being unbounded.",
    [{"text": "Experience with C++ is required.", "is_genuine_qualification": True,
      "expected_necessity": "REQUIRED", "should_enter_assessment": True}])


def main() -> None:
    out = {
        "corpus_version": "m11g7-boundary-controls:v1",
        "authorship_note": (
            "Every control's text is independently hand-authored for this "
            "milestone, synthetic and generic -- never copied from any real "
            "job posting (same discipline as M11-G6's corpus). Safe to "
            "commit in full, including verbatim text."
        ),
        "correction_log": (
            "Pre-freeze verification (via m11g7_preflight_check.py, run "
            "BEFORE the hash freeze -- learned from M11-G6's post-freeze "
            "correction rounds) caught and fixed, before any freeze: (a) "
            "m11g7-007's word count (10->9, a manual counting error) and "
            "its expected_heading_kind (UNKNOWN->REQUIRED, corrected after "
            "directly executing _matched_heading_families on the real "
            "text rather than assuming a two-family collision that does "
            "not actually occur); (b) m11g7-018/019/020/021/030/031's "
            "top-level heading_word_count/has_strong_shape_signal fields "
            "described the WRONG heading (the embedded, second, "
            "defect-triggering heading inside body_lines) instead of "
            "heading_line itself -- corrected to describe heading_line "
            "consistently, with the second heading's own word count "
            "stated in prose instead; (c) m11g7-021 was authored as a "
            "'positive control' claiming an 8-word second heading was "
            "'already recognized today' without verifying this directly "
            "-- direct execution showed it was ALSO defective (8 > 7); "
            "replaced with a genuinely-verified 6-word heading (confirmed "
            "to already resolve correctly today) so this control tests "
            "what it was always meant to test (clean transition behavior "
            "once a heading IS recognized), with the 8-word defect shape "
            "now covered properly by m11g7-030 instead; (d) "
            "m11g7-038/042's word counts (13->12, manual counting errors). "
            "A SECOND pre-freeze round, caught by batch-verifying every "
            "distinct heading-like string against `_matched_heading_families` "
            "directly rather than assuming: the phrase 'What You Will Be "
            "Able To Build And Own' (used across controls 004/008/009/"
            "010/023/035 and embedded in several severity-tier controls) "
            "does NOT match `_RESPONSIBILITY_ROOT` at all -- that root "
            "requires the bare word 'respons*', 'duties'/'duty', the "
            "EXACT phrase 'what you'll do'/'what you will do', 'the "
            "role', or 'day in this role'; 'build and own' matches none "
            "of these. Corrected expected_heading_kind from RESPONSIBILITY "
            "to UNKNOWN for all six. m11g7-022 (the same phrase, em-dash "
            "terminated, weak shape signal) has zero family AND weak "
            "signal, so it correctly stays NOT_A_HEADING under ANY G7 "
            "fix -- corrected from RESPONSIBILITY. m11g7-025's "
            "'A Little More About Our Company...' does NOT trigger "
            "`_NON_QUALIFICATION_ROOT`'s `^about\\b` (anchored to the "
            "literal FIRST character, 'A', not 'About') -- corrected "
            "from SKIP to UNKNOWN. m11g7-038's 'What You Will Be "
            "Responsible For' DOES match the bare `respons*` root (a "
            "broader alternative than 'what you'll do' that an earlier "
            "draft missed) -- corrected from UNKNOWN to RESPONSIBILITY. "
            "No control's SAFETY-RELEVANT expected outcome (which lines "
            "must never be scored, which must never be silently lost) was "
            "changed by any of these corrections -- all were either pure "
            "label/field-scope fixes or corrections to match directly-"
            "verified, pre-existing, unrelated behavior."
        ),
        "schema_notes": {
            "body_qualifications.should_enter_assessment": (
                "Asymmetric by design, matching the two DIFFERENT safety "
                "invariants this milestone measures: for a genuine "
                "qualification (is_genuine_qualification=true), True means "
                "'must be admitted as AT LEAST a diagnostic claim (a "
                "JobRequirement OR an UnparsedClaim) -- never silently, "
                "totally dropped' (the HIGH_silent_total_suppression risk). "
                "For a non-qualification (is_genuine_qualification=false), "
                "False means 'must NEVER become a SCORED JobRequirement' "
                "(the HIGH_fabricated_assessable_requirement risk) -- it "
                "says nothing about whether the line may still, safely, "
                "appear as a diagnostic UnparsedClaim (confirmed, by direct "
                "execution, to be the existing, safe, intended behavior for "
                "RESPONSIBILITY-section content with no local marker). "
                "Exact diagnostic-admission COUNTS are a Phase 1/4 "
                "MEASUREMENT against the real pipeline, not a gold "
                "prediction -- learned directly from an authoring error "
                "caught before this freeze (see correction_log)."
            ),
            "expected_heading_kind": (
                "Gold answer for what the heading_line SHOULD resolve to "
                "under a correct, safe fix -- real _SectionKind enum "
                "member names (REQUIRED/PREFERRED/RESPONSIBILITY/LEARNING/"
                "SKIP/UNKNOWN) or NOT_A_HEADING (should never be "
                "recognized as a heading at all, under ANY safe fix -- "
                "the adversarial/weak-signal controls)."
            ),
            "severity_tier": (
                "For carry-forward scenario controls only: the measured "
                "severity of what happens if this specific defect instance "
                "is left unfixed -- LOW_diagnostic_only (never scored), "
                "HIGH_fabricated_assessable_requirement (confirmed to "
                "produce a non-None alignment_score from non-qualification "
                "prose), or HIGH_silent_total_suppression (confirmed to "
                "silently drop a genuine, locally-marked REQUIRED claim "
                "entirely). null for controls not testing a carry-forward "
                "scenario."
            ),
        },
        "controls": CONTROLS,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"wrote {len(CONTROLS)} controls to {OUT_PATH}")


if __name__ == "__main__":
    main()
