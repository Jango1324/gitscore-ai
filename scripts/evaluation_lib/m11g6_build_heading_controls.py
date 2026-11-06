"""Milestone 11-G6 Phase 2 -- builds the independently-authored,
synthetic heading-classification gold corpus and writes it to
`evaluation/m11g6/heading_controls.json`.

Evaluation-only. Every control's text is hand-authored for this
milestone (never borrowed from a real posting -- no provenance/privacy
concerns, unlike M11-D/F/G5's authentic-posting corpora). Gold is
authored and frozen BEFORE any candidate fix is measured against it
(see `m11g6_phase1_current_behavior.py`, which runs AFTER this file and
the freeze script, and never informs this file's own content).
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = REPO_ROOT / "evaluation" / "m11g6" / "heading_controls.json"

# Each control: heading_line (or None for unsectioned), body_lines (list
# of str), expected_heading_kind (gold -- one of REQUIRED/PREFERRED/
# RESPONSIBILITY/LEARNING/NON_QUALIFICATION/UNKNOWN/NOT_A_HEADING),
# skip_suppression_appropriate (should this heading cause TOTAL,
# unrecoverable suppression of everything under it), and
# body_qualifications: per body-line annotation of
# is_genuine_qualification / expected_necessity / should_enter_assessment.

CONTROLS: list[dict] = []


def add(id_, category, heading_line, body_lines, expected_heading_kind,
        skip_suppression_appropriate, rationale, body_qualifications):
    CONTROLS.append({
        "id": id_,
        "category": category,
        "heading_line": heading_line,
        "body_lines": body_lines,
        "expected_heading_kind": expected_heading_kind,
        "skip_suppression_appropriate": skip_suppression_appropriate,
        "rationale": rationale,
        "body_qualifications": body_qualifications,
    })


# 1. "Who We Are" -- genuine company narrative, bare heading.
add("m11g6-001-who-we-are-bare", "who_we_are",
    "Who We Are:",
    ["We build tools that help small businesses grow."],
    "SKIP", True,
    "Genuine, unmodified company-narrative heading -- the baseline "
    "positive control any fix must not regress. (SKIP is the real "
    "_SectionKind enum member name; 'NON_QUALIFICATION' in this "
    "corpus's category/rationale text names the vocabulary family, "
    "never the gold label value -- corrected after v1 conflated the "
    "two, see corpus-level correction_log.)",
    [{"text": "We build tools that help small businesses grow.",
      "is_genuine_qualification": False, "expected_necessity": None,
      "should_enter_assessment": False}])

add("m11g6-002-who-we-are-with-mission", "who_we_are",
    "Who We Are:",
    ["Founded in 2015, our team is distributed across three continents."],
    "SKIP", True,
    "Second bare 'Who We Are' instance with different narrative content -- "
    "confirms the heading itself, not the body wording, drives the "
    "classification.",
    [{"text": "Founded in 2015, our team is distributed across three continents.",
      "is_genuine_qualification": False, "expected_necessity": None,
      "should_enter_assessment": False}])

# 2. "Who We Are Looking For" -- the confirmed G5 defect.
add("m11g6-003-who-we-are-looking-for", "who_we_are_looking_for",
    "Who We Are Looking For:",
    ["A software engineer with strong distributed systems experience."],
    "UNKNOWN", False,
    "Confirmed G5 defect: a candidate-profile heading, not company "
    "narrative. Must not be silently dropped (current behavior: SKIP, "
    "total suppression) -- the honest outcome given no local "
    "REQUIRED/PREFERRED marker on this exact body sentence is UNKNOWN "
    "(diagnostic-eligible via the existing _looks_like_requirement gate), "
    "never SKIP and never a forced REQUIRED default.",
    [{"text": "A software engineer with strong distributed systems experience.",
      "is_genuine_qualification": True, "expected_necessity": "UNKNOWN",
      "should_enter_assessment": True,
      "note": "No local marker; UNKNOWN section defaults necessity to None "
              "(reported as UNKNOWN/diagnostic), never REQUIRED by assumption."}])

add("m11g6-004-who-we-are-looking-for-degree", "who_we_are_looking_for",
    "Who We Are Looking For:",
    ["A Bachelor's degree in Computer Science or a related field is required."],
    "UNKNOWN", False,
    "Same heading, but the body sentence carries an EXPLICIT local "
    "REQUIRED marker -- tests whether the local-marker-always-wins rule "
    "(necessity.py step 1) can still save this claim once the heading "
    "itself stops being SKIP. It can, PROVIDED the heading no longer "
    "suppresses the claim's admission entirely (SKIP admits zero claims, "
    "local-marker override never even runs).",
    [{"text": "A Bachelor's degree in Computer Science or a related field is required.",
      "is_genuine_qualification": True, "expected_necessity": "REQUIRED",
      "should_enter_assessment": True,
      "note": "Local 'is required' marker always wins per necessity.py step 1 -- "
              "but only reachable if the claim is admitted at all."}])

# 3. "What We're Looking For"
add("m11g6-005-what-were-looking-for", "what_were_looking_for",
    "What We're Looking For:",
    ["Experience with Kubernetes and container orchestration."],
    "UNKNOWN", False,
    "Same semantic shape as 'Who We Are Looking For' (candidate-profile "
    "heading), different grammatical subject ('What' vs 'Who', 'We're' "
    "vs 'We Are'). Confirms the risk generalizes beyond one exact phrase.",
    [{"text": "Experience with Kubernetes and container orchestration.",
      "is_genuine_qualification": True, "expected_necessity": "UNKNOWN",
      "should_enter_assessment": True}])

add("m11g6-006-what-were-looking-for-plus-plain", "what_were_looking_for",
    "What We're Looking For",
    ["3+ years of backend development experience."],
    "NOT_A_HEADING", False,
    "Same heading without the trailing colon. Zero family-root match AND "
    "no colon/ALL-CAPS/Markdown strong-shape signal -- per the existing, "
    "already-tested M10C design, plain title-case ALONE (no family "
    "corroboration) is not enough to count as heading-shaped at all; "
    "this control exercises that pre-existing rule, unrelated to the "
    "'who we are' defect (v1 incorrectly expected UNKNOWN here, see "
    "corpus-level correction_log).",
    [{"text": "3+ years of backend development experience.",
      "is_genuine_qualification": True, "expected_necessity": "REQUIRED",
      "should_enter_assessment": True,
      "note": "Heading line is NOT_A_HEADING, so current_kind never leaves "
              "its initial None -- the body line inherits M6B's original, "
              "unrelated 'no section at all' REQUIRED default (confirmed by "
              "direct execution), not the UNKNOWN-section None-necessity "
              "path. Different mechanism from the UNKNOWN-heading controls "
              "above; v1 incorrectly expected UNKNOWN here."}])

# 4. "What We Need to See"
add("m11g6-007-what-we-need-to-see", "what_we_need_to_see",
    "What We Need to See:",
    ["Proven experience with SQL and relational databases."],
    "UNKNOWN", False,
    "Another candidate-profile heading style sharing no vocabulary with "
    "'who'/'about' at all -- a general fix must cover this shape too, "
    "not just literal 'who we are' collisions.",
    [{"text": "Proven experience with SQL and relational databases.",
      "is_genuine_qualification": True, "expected_necessity": "UNKNOWN",
      "should_enter_assessment": True}])

add("m11g6-008-what-we-need-to-see-second", "what_we_need_to_see",
    "What We Need To See:",
    ["A proven track record with 5+ years of professional experience."],
    "UNKNOWN", False,
    "Title-case variant of the same heading phrase. Body line carries "
    "'experience' (the existing, unrelated _looks_like_requirement "
    "vocabulary gate) so it genuinely exercises admission under UNKNOWN, "
    "rather than confounding the heading finding with an unrelated "
    "vocabulary-recall gap (v1's vaguer wording here was declined for "
    "that unrelated reason, not because of this heading).",
    [{"text": "A proven track record with 5+ years of professional experience.",
      "is_genuine_qualification": True, "expected_necessity": "UNKNOWN",
      "should_enter_assessment": True}])

# 5. "What You'll Bring"
add("m11g6-009-what-youll-bring", "what_youll_bring",
    "What You'll Bring:",
    ["Strong communication skills and a collaborative mindset."],
    "UNKNOWN", False,
    "Another extremely common candidate-profile heading with no "
    "vocabulary overlap with any existing family root.",
    [{"text": "Strong communication skills and a collaborative mindset.",
      "is_genuine_qualification": True, "expected_necessity": "UNKNOWN",
      "should_enter_assessment": True}])

add("m11g6-010-what-you-bring-contraction-free", "what_youll_bring",
    "What You Will Bring:",
    ["Five or more years of professional software engineering experience."],
    "UNKNOWN", False,
    "Non-contracted ('You Will' vs \"You'll\") variant of the same heading.",
    [{"text": "Five or more years of professional software engineering experience.",
      "is_genuine_qualification": True, "expected_necessity": "UNKNOWN",
      "should_enter_assessment": True}])

# 6. "About Us" -- genuine narrative, anchored ^about root.
add("m11g6-011-about-us", "about_us",
    "About Us:",
    ["We are a 200-person company serving customers in 40 countries."],
    "SKIP", True,
    "Genuine company-narrative heading, correctly matched today via the "
    "anchored `^about\\b` root -- a baseline positive control.",
    [{"text": "We are a 200-person company serving customers in 40 countries.",
      "is_genuine_qualification": False, "expected_necessity": None,
      "should_enter_assessment": False}])

add("m11g6-012-about-the-company", "about_us",
    "About the Company:",
    ["Our headquarters are in Austin with remote teams worldwide."],
    "SKIP", True,
    "A second 'About X' narrative heading variant -- should also "
    "correctly suppress.",
    [{"text": "Our headquarters are in Austin with remote teams worldwide.",
      "is_genuine_qualification": False, "expected_necessity": None,
      "should_enter_assessment": False}])

# 7. "About the Role" -- ambiguous collision: ^about (SKIP) AND "the role" (RESPONSIBILITY).
add("m11g6-013-about-the-role", "about_the_role",
    "About the Role:",
    ["You will own the backend architecture for our payments platform."],
    "UNKNOWN", False,
    "Already-ambiguous today (matches BOTH the anchored `^about\\b` SKIP "
    "root AND the `\\bthe role\\b` RESPONSIBILITY root) -- the EXISTING "
    "multi-family-match rule already resolves this safely to UNKNOWN, "
    "not SKIP. Included as a positive control that today's rule for "
    "GENUINE two-way collisions already works -- a fix must not break it.",
    [{"text": "You will own the backend architecture for our payments platform.",
      "is_genuine_qualification": False, "expected_necessity": None,
      "should_enter_assessment": False,
      "note": "A responsibility statement, not an applicant qualification."}])

add("m11g6-014-about-the-role-with-requirement", "about_the_role",
    "About the Role:",
    ["5+ years of experience with distributed systems is required."],
    "UNKNOWN", False,
    "Same already-ambiguous heading (UNKNOWN today), body sentence carries "
    "an explicit local REQUIRED marker -- confirms local-marker override "
    "already works correctly for UNKNOWN sections today (this heading "
    "was never SKIP to begin with).",
    [{"text": "5+ years of experience with distributed systems is required.",
      "is_genuine_qualification": True, "expected_necessity": "REQUIRED",
      "should_enter_assessment": True}])

# 8. "Your Qualifications"
add("m11g6-015-your-qualifications", "your_qualifications",
    "Your Qualifications:",
    ["Experience with Python and distributed systems."],
    "REQUIRED", False,
    "Fires the existing QUALIFICATION_ROOT -- already correctly resolves "
    "to REQUIRED today; a baseline positive control the fix must preserve.",
    [{"text": "Experience with Python and distributed systems.",
      "is_genuine_qualification": True, "expected_necessity": "REQUIRED",
      "should_enter_assessment": True}])

add("m11g6-016-your-qualifications-plain", "your_qualifications",
    "Your Qualifications",
    ["A degree in Computer Science or a related field."],
    "REQUIRED", False,
    "Same heading without a trailing colon.",
    [{"text": "A degree in Computer Science or a related field.",
      "is_genuine_qualification": True, "expected_necessity": "REQUIRED",
      "should_enter_assessment": True}])

# 9. "Required Qualifications"
add("m11g6-017-required-qualifications", "required_qualifications",
    "Required Qualifications:",
    ["Three or more years of experience with Java."],
    "REQUIRED", False,
    "Already correctly REQUIRED today (both REQUIRED_ROOT and "
    "QUALIFICATION_ROOT fire, only one family appended) -- baseline "
    "positive control.",
    [{"text": "Three or more years of experience with Java.",
      "is_genuine_qualification": True, "expected_necessity": "REQUIRED",
      "should_enter_assessment": True}])

add("m11g6-018-required-qualifications-colon-caps", "required_qualifications",
    "REQUIRED QUALIFICATIONS",
    ["Fluency in SQL."],
    "REQUIRED", False,
    "ALL-CAPS formatting variant of the same heading.",
    [{"text": "Fluency in SQL.",
      "is_genuine_qualification": True, "expected_necessity": "REQUIRED",
      "should_enter_assessment": True}])

# 10. "Preferred Qualifications"
add("m11g6-019-preferred-qualifications", "preferred_qualifications",
    "Preferred Qualifications:",
    ["Experience with Kubernetes is a plus."],
    "PREFERRED", False,
    "Already correctly resolves to PREFERRED today via the existing "
    "qualif*-excluded-when-preferr*-present rule -- baseline positive "
    "control the fix must not regress.",
    [{"text": "Experience with Kubernetes is a plus.",
      "is_genuine_qualification": True, "expected_necessity": "PREFERRED",
      "should_enter_assessment": True}])

add("m11g6-020-preferred-qualifications-markdown", "preferred_qualifications",
    "**Preferred Qualifications**",
    ["Prior experience with Go."],
    "PREFERRED", False,
    "Markdown-bold formatting variant of the same heading.",
    [{"text": "Prior experience with Go.",
      "is_genuine_qualification": True, "expected_necessity": "PREFERRED",
      "should_enter_assessment": True}])

# 11. "Nice to Have"
add("m11g6-021-nice-to-have", "nice_to_have",
    "Nice to Have:",
    ["Familiarity with Terraform."],
    "PREFERRED", False,
    "Already correctly PREFERRED today -- baseline positive control.",
    [{"text": "Familiarity with Terraform.",
      "is_genuine_qualification": True, "expected_necessity": "PREFERRED",
      "should_enter_assessment": True}])

add("m11g6-022-nice-to-haves-plural", "nice_to_have",
    "Nice-to-Haves:",
    ["Open-source contributions."],
    "PREFERRED", False,
    "Hyphenated, pluralized variant of the same heading.",
    [{"text": "Open-source contributions.",
      "is_genuine_qualification": True, "expected_necessity": "PREFERRED",
      "should_enter_assessment": True}])

# 12. "What You'll Do"
add("m11g6-023-what-youll-do", "what_youll_do",
    "What You'll Do:",
    ["Design and build scalable backend services."],
    "RESPONSIBILITY", False,
    "Already correctly RESPONSIBILITY today -- baseline positive control.",
    [{"text": "Design and build scalable backend services.",
      "is_genuine_qualification": False, "expected_necessity": None,
      "should_enter_assessment": False}])

add("m11g6-024-what-you-will-do-full", "what_youll_do",
    "What You Will Do:",
    ["Collaborate with product and design on new features."],
    "RESPONSIBILITY", False,
    "Non-contracted variant of the same heading.",
    [{"text": "Collaborate with product and design on new features.",
      "is_genuine_qualification": False, "expected_necessity": None,
      "should_enter_assessment": False}])

# 13. Other company-narrative headings.
add("m11g6-025-our-mission", "company_narrative_other",
    "Our Mission:",
    ["To make healthcare accessible for everyone."],
    "UNKNOWN", False,
    "A company-narrative heading NOT currently in the NON_QUALIFICATION "
    "vocabulary at all -- correctly falls through to UNKNOWN today "
    "(zero families matched, strong colon shape signal present), which "
    "is ALREADY the safe behavior this milestone recommends for "
    "'who we are looking for' too. Included to show the fix direction is "
    "consistent with how an unrecognized-but-harmless narrative heading "
    "is already handled -- not fully SKIP-suppressed (narrative body "
    "content is still separately declined by _looks_like_requirement, "
    "achieving the same practical outcome via a different, safer "
    "mechanism).",
    [{"text": "To make healthcare accessible for everyone.",
      "is_genuine_qualification": False, "expected_necessity": None,
      "should_enter_assessment": False,
      "note": "Not REQUIREMENT_SIGNAL-shaped text, so _looks_like_requirement "
              "gates it out even though the section is UNKNOWN, not SKIP."}])

add("m11g6-026-why-join-us", "company_narrative_other",
    "Why Join Us:",
    ["Competitive pay, flexible hours, and a strong engineering culture."],
    "SKIP", True,
    "Already in the NON_QUALIFICATION vocabulary today and correctly so "
    "-- a genuine, unambiguous narrative heading, baseline positive "
    "control.",
    [{"text": "Competitive pay, flexible hours, and a strong engineering culture.",
      "is_genuine_qualification": False, "expected_necessity": None,
      "should_enter_assessment": False}])

# 14. Unusual qualification headings.
add("m11g6-027-the-ideal-candidate", "unusual_qualification_heading",
    "The Ideal Candidate:",
    ["Has 5+ years of experience shipping production machine learning systems."],
    "UNKNOWN", False,
    "An unusual but genuine candidate-profile heading sharing no "
    "vocabulary with any existing family -- correctly falls through to "
    "UNKNOWN today (zero families, strong shape signal) since nothing "
    "currently misclassifies it as SKIP. Included to confirm this shape "
    "is NOT currently broken, only 'who we are'-prefixed and a few "
    "related phrasings are. Body line carries 'experience' so it "
    "genuinely tests admission under UNKNOWN (v1's vaguer wording "
    "here was separately declined by the unrelated _looks_like_requirement "
    "gate).",
    [{"text": "Has 5+ years of experience shipping production machine learning systems.",
      "is_genuine_qualification": True, "expected_necessity": "UNKNOWN",
      "should_enter_assessment": True}])

add("m11g6-028-you-might-be-a-fit", "unusual_qualification_heading",
    "You Might Be a Great Fit If:",
    ["You have 5+ years of experience leading engineering teams."],
    "UNKNOWN", False,
    "Another unusual genuine candidate-profile heading, correctly "
    "UNKNOWN today (not SKIP) -- confirms the defect is specifically "
    "about headings that happen to contain a NON_QUALIFICATION substring, "
    "not about unusual headings in general. Body line carries "
    "'experience' so it genuinely tests admission (v1's vaguer wording "
    "was separately declined by the unrelated _looks_like_requirement "
    "gate).",
    [{"text": "You have 5+ years of experience leading engineering teams.",
      "is_genuine_qualification": True, "expected_necessity": "UNKNOWN",
      "should_enter_assessment": True}])

# 15. Ambiguous / unknown headings.
add("m11g6-029-additional-information", "ambiguous_unknown_heading",
    "Additional Information:",
    ["This role may require occasional travel."],
    "UNKNOWN", False,
    "A bare colon IS itself a strong shape signal (independent of family "
    "match, per the existing, already-tested M10C design) -- so this "
    "zero-family-root heading resolves to UNKNOWN, not 'not a heading at "
    "all' (v1 incorrectly expected NOT_A_HEADING here, conflating this "
    "with the DIFFERENT, no-colon 'Additional Information' example from "
    "the module's own docstring -- see corpus-level correction_log). The "
    "body line itself is still correctly declined by _looks_like_requirement "
    "('may require' is not the literal word 'required'), confirmed by "
    "direct execution (0 requirements, 0 diagnostics).",
    [{"text": "This role may require occasional travel.",
      "is_genuine_qualification": False, "expected_necessity": None,
      "should_enter_assessment": False,
      "note": "Heading itself not recognized; body line's own eligibility "
              "depends entirely on whatever section was open before it."}])

add("m11g6-030-good-to-know", "ambiguous_unknown_heading",
    "Good to Know:",
    ["We conduct background checks for all final candidates."],
    "UNKNOWN", False,
    "Same shape as Additional Information -- bare colon as a strong "
    "signal with zero family-root match resolves to UNKNOWN, confirmed "
    "by direct execution (0 requirements, 0 diagnostics for the body "
    "line, which _looks_like_requirement correctly declines).",
    [{"text": "We conduct background checks for all final candidates.",
      "is_genuine_qualification": False, "expected_necessity": None,
      "should_enter_assessment": False}])

# 16. Overlapping-prefix headings.
add("m11g6-031-who-we-are-bare-prefix-control", "overlapping_prefix_headings",
    "Who We Are",
    ["A remote-first engineering team."],
    "SKIP", True,
    "The bare, unmodified three-word phrase with no trailing continuation "
    "-- the TRUE positive this family exists to match. Any fix must "
    "preserve this exact classification.",
    [{"text": "A remote-first engineering team.",
      "is_genuine_qualification": False, "expected_necessity": None,
      "should_enter_assessment": False}])

add("m11g6-032-who-we-are-and-what-youll-do", "overlapping_prefix_headings",
    "Who We Are and What You'll Do:",
    ["Own the backend architecture end to end."],
    "UNKNOWN", False,
    "A compound heading genuinely matching TWO existing families on one "
    "line: `\\bwho we are\\b` (SKIP) AND `\\bwhat you(?:'ll| will) do\\b` "
    "(RESPONSIBILITY) -- confirmed by direct execution to ALREADY "
    "resolve to UNKNOWN today (the existing multi-family-match rule), "
    "not a confident SKIP. Demonstrates the existing collision-safety "
    "net already generalizes correctly to a 'who we are'-prefixed "
    "compound once a second family co-fires; the recommended fix adds a "
    "comparable corroborating signal for the 'Looking For' continuation "
    "specifically (v1's original 9-word heading here exceeded "
    "`_classify_heading_line`'s own 7-word shape-gate cap and measured "
    "as NOT_A_HEADING, an unrelated artifact -- corrected, see "
    "corpus-level correction_log).",
    [{"text": "Own the backend architecture end to end.",
      "is_genuine_qualification": False, "expected_necessity": None,
      "should_enter_assessment": False,
      "note": "A responsibility statement, not an applicant qualification."}])

# 17. Unicode punctuation and whitespace variants.
add("m11g6-033-who-we-are-looking-for-nbsp", "unicode_punctuation_whitespace",
    "Who We Are Looking For:",
    ["5+ years of experience working across the full stack."],
    "UNKNOWN", False,
    "Same phrase with REAL non-breaking spaces (U+00A0) between EVERY "
    "word, including inside the 'who we are' trigram itself. v1 only "
    "had NBSP in two of the four gaps (a typo, not every space), an "
    "authoring oversight. Confirmed by direct execution with ALL-NBSP "
    "spacing: _NON_QUALIFICATION_ROOT's `\bwho we are\b` is written "
    "with LITERAL ASCII spaces, which do NOT match across U+00A0 gaps -- "
    "this fully-NBSP variant does NOT reproduce the defect today, "
    "resolving to UNKNOWN by accident of the pattern's own literal "
    "construction, not by design. A directly-measured Phase 1 Q3 "
    "finding: the collision is an ASCII-literal-pattern artifact, not a "
    "universal 'any whitespace' collision.",
    [{"text": "5+ years of experience working across the full stack.",
      "is_genuine_qualification": True, "expected_necessity": "UNKNOWN",
      "should_enter_assessment": True}])

add("m11g6-034-who-we-are-looking-for-em-dash", "unicode_punctuation_whitespace",
    "Who We Are Looking For—",
    ["Strong ownership mentality."],
    "UNKNOWN", False,
    "Same phrase terminated with an em dash instead of a colon. Confirmed "
    "by direct execution: no colon/ALL-CAPS/Markdown strong-shape signal, "
    "but plain-title-case IS corroborated by the `_NON_QUALIFICATION_ROOT` "
    "family match firing on the embedded 'who we are' substring (the "
    "em dash attaches to 'For' as a token-trailing character and doesn't "
    "block that match) -- so this reaches `_matched_heading_families` and "
    "resolves to SKIP under current code (the same defect as the colon "
    "form), expected UNKNOWN once the corroborating-signal fix is in "
    "place (v1 incorrectly expected NOT_A_HEADING here, assuming the weak "
    "shape signal alone would exclude it without accounting for the "
    "family match also satisfying that same corroboration requirement -- "
    "see corpus-level correction_log).",
    [{"text": "Strong ownership mentality.",
      "is_genuine_qualification": True, "expected_necessity": "UNKNOWN",
      "should_enter_assessment": True,
      "note": "Expected classification depends on exact shape-gate behavior; "
              "flagged for direct measurement rather than assumed."}])

# 18. Markdown and colon heading variants.
add("m11g6-035-who-we-are-looking-for-markdown-atx", "markdown_colon_variants",
    "## Who We Are Looking For",
    ["Excellent debugging skills."],
    "UNKNOWN", False,
    "Markdown ATX-header variant of the defect-triggering phrase -- "
    "`_strip_heading_decoration` removes the leader before classification, "
    "so expected to reproduce the identical defect.",
    [{"text": "Excellent debugging skills.",
      "is_genuine_qualification": True, "expected_necessity": "UNKNOWN",
      "should_enter_assessment": True}])

add("m11g6-036-who-we-are-looking-for-markdown-bold", "markdown_colon_variants",
    "**Who We Are Looking For**",
    ["Proficiency with CI/CD pipelines."],
    "UNKNOWN", False,
    "Markdown-bold variant of the same phrase, same expected defect "
    "reproduction.",
    [{"text": "Proficiency with CI/CD pipelines.",
      "is_genuine_qualification": True, "expected_necessity": "UNKNOWN",
      "should_enter_assessment": True}])

# 19. Mixed company narrative and applicant qualifications under one heading.
add("m11g6-037-mixed-narrative-and-qualification", "mixed_narrative_and_qualification",
    "Who We Are Looking For:",
    ["We are a fast-growing, mission-driven team.",
     "You have 5+ years of experience with distributed systems."],
    "UNKNOWN", False,
    "Two consecutive lines under the SAME defect-triggering heading: the "
    "first is pure narrative, the second a genuine qualification. Tests "
    "whether a general fix correctly leaves narrative-shaped content "
    "ungated (declined by _looks_like_requirement, not forced in) while "
    "still admitting the genuine qualification as a diagnostic.",
    [{"text": "We are a fast-growing, mission-driven team.",
      "is_genuine_qualification": False, "expected_necessity": None,
      "should_enter_assessment": False},
     {"text": "You have 5+ years of experience with distributed systems.",
      "is_genuine_qualification": True, "expected_necessity": "UNKNOWN",
      "should_enter_assessment": True}])

add("m11g6-038-mixed-narrative-with-explicit-requirement", "mixed_narrative_and_qualification",
    "Who We Are Looking For:",
    ["Join a team that values curiosity and ownership.",
     "A degree in Computer Science is required."],
    "UNKNOWN", False,
    "Same shape, but the genuine qualification line carries an EXPLICIT "
    "local REQUIRED marker -- tests that the local-marker-always-wins "
    "rule produces REQUIRED (not UNKNOWN) once the claim is no longer "
    "SKIP-suppressed.",
    [{"text": "Join a team that values curiosity and ownership.",
      "is_genuine_qualification": False, "expected_necessity": None,
      "should_enter_assessment": False},
     {"text": "A degree in Computer Science is required.",
      "is_genuine_qualification": True, "expected_necessity": "REQUIRED",
      "should_enter_assessment": True}])

# 20. Section transitions.
add("m11g6-039-transition-defect-heading-then-required", "section_transition",
    "Who We Are Looking For:",
    ["5+ years of experience thriving in ambiguous, fast-moving environments."],
    "UNKNOWN", False,
    "First half of a two-heading document (see companion control 040) -- "
    "a defect-triggering heading followed later by a genuine Required "
    "Qualifications heading. Verifies `current_kind` correctly resets at "
    "the SECOND heading regardless of what the first one resolved to. "
    "Body line carries 'experience' so it genuinely tests admission "
    "once the heading defect is fixed.",
    [{"text": "5+ years of experience thriving in ambiguous, fast-moving environments.",
      "is_genuine_qualification": True, "expected_necessity": "UNKNOWN",
      "should_enter_assessment": True}])

add("m11g6-040-transition-full-two-heading-document", "section_transition",
    "Who We Are Looking For:",
    ["5+ years of experience thriving in ambiguous, fast-moving environments.",
     "Required Qualifications:",
     "5+ years of experience with Python."],
    "UNKNOWN", False,
    "Full two-section document: a defect-triggering heading followed by "
    "a genuine REQUIRED heading. The SECOND heading's own content must "
    "resolve to REQUIRED regardless of how the FIRST heading is "
    "classified -- this is a pure section-transition correctness check, "
    "already expected to pass today and after any fix.",
    [{"text": "5+ years of experience thriving in ambiguous, fast-moving environments.",
      "is_genuine_qualification": True, "expected_necessity": "UNKNOWN",
      "should_enter_assessment": True},
     {"text": "5+ years of experience with Python.",
      "is_genuine_qualification": True, "expected_necessity": "REQUIRED",
      "should_enter_assessment": True}])

# 21. Unsectioned descriptions (no heading at all).
add("m11g6-041-unsectioned-plain", "unsectioned_description",
    None,
    ["Looking for a software engineer with 3+ years of Python experience."],
    "NOT_A_HEADING", False,
    "No heading anywhere in the document -- Milestone 6B's original "
    "'no section at all' default applies (REQUIRED hint, gated by "
    "_looks_like_requirement). Included as an unrelated-but-adjacent "
    "baseline: the phrase 'Looking for' appearing in body TEXT (not a "
    "heading line) must never be affected by any heading-classification "
    "fix, since `_classify_heading_line` is never even called on a line "
    "that fails the heading SHAPE gate (this one ends in a sentence-"
    "terminal period and exceeds 7 words).",
    [{"text": "Looking for a software engineer with 3+ years of Python experience.",
      "is_genuine_qualification": True, "expected_necessity": "REQUIRED",
      "should_enter_assessment": True}])

add("m11g6-042-unsectioned-narrative-then-requirement", "unsectioned_description",
    None,
    ["We are growing fast and need great engineers.",
     "Experience with Kubernetes is required."],
    "NOT_A_HEADING", False,
    "No heading anywhere; first line is narrative (declined by "
    "_looks_like_requirement), second line carries an explicit local "
    "REQUIRED marker and is admitted. A second baseline unaffected by any "
    "heading-classification fix.",
    [{"text": "We are growing fast and need great engineers.",
      "is_genuine_qualification": False, "expected_necessity": None,
      "should_enter_assessment": False},
     {"text": "Experience with Kubernetes is required.",
      "is_genuine_qualification": True, "expected_necessity": "REQUIRED",
      "should_enter_assessment": True}])

# 22. Explicit required/preferred qualifications beneath other ambiguous headings.
add("m11g6-043-what-were-looking-for-with-preferred", "explicit_under_ambiguous_heading",
    "What We're Looking For:",
    ["Experience with GraphQL is preferred but not required."],
    "UNKNOWN", False,
    "A different candidate-profile heading (not 'who we are'-prefixed) "
    "with a body line carrying an explicit local PREFERRED marker -- "
    "confirms the local-marker override generalizes across every "
    "heading in this ambiguous family, not just the one G5 found.",
    [{"text": "Experience with GraphQL is preferred but not required.",
      "is_genuine_qualification": True, "expected_necessity": "PREFERRED",
      "should_enter_assessment": True}])

add("m11g6-044-the-ideal-candidate-with-required", "explicit_under_ambiguous_heading",
    "The Ideal Candidate:",
    ["A valid security clearance is required."],
    "UNKNOWN", False,
    "An unusual, already-UNKNOWN-today heading with an explicit "
    "'is required' marker -- a second confirmation that explicit local "
    "markers already survive ambiguous (UNKNOWN) headings correctly "
    "today; this category is about the EXISTING safety net, not a gap. "
    "Reworded from v1's 'Must have...' so the line also carries the "
    "literal word 'required' (the existing _looks_like_requirement "
    "admission gate's own vocabulary, distinct from "
    "_classify_heading_line's heading-level _REQUIRED_ROOT) -- "
    "'must have' alone does not guarantee admission under UNKNOWN on "
    "its own; confirmed directly.",
    [{"text": "A valid security clearance is required.",
      "is_genuine_qualification": True, "expected_necessity": "REQUIRED",
      "should_enter_assessment": True}])


def main() -> None:
    out = {
        "corpus_version": "m11g6-heading-controls:v2",
        "authorship_note": (
            "Every control's text is independently hand-authored for this "
            "milestone, synthetic and generic -- never copied from any real "
            "job posting (unlike M11-D/F/G5's authentic corpora). No "
            "provenance/privacy concerns; safe to commit in full, including "
            "verbatim text."
        ),
        "correction_log": (
            "v1 was authored and hash-frozen first, then run against the "
            "real (unmodified) _classify_heading_line/segment_description "
            "for the first time -- this surfaced 21/44 apparent "
            "mismatches. Direct re-verification against the module's own "
            "code and docstring (never against 'whatever the parser "
            "happened to output') found the 'who we are'/'who we are "
            "looking for'-family defect rows (003, 004, 033, 034, 035, "
            "036, 037, 038, 039, 040) were correctly authored in v1 -- "
            "those mismatches ARE the confirmed defect, unchanged in v2. "
            "The remaining 11 mismatches were v1 AUTHORING ERRORS, not "
            "new defects, corrected in v2: (a) six controls (001, 002, "
            "011, 012, 026, 031) used the label 'NON_QUALIFICATION' (the "
            "vocabulary-family name) where the real _SectionKind enum "
            "member is 'SKIP' -- a pure terminology fix, zero semantic "
            "change; (b) control 025 contradicted its own rationale text "
            "(said UNKNOWN, field said NON_QUALIFICATION) -- fixed to "
            "UNKNOWN; (c) controls 006/029/030 misapplied the shape-gate "
            "rule (missed that a bare colon alone is a strong signal "
            "regardless of family match, and that plain-title-case "
            "without ANY strong signal needs family corroboration) -- "
            "fixed to match this ALREADY-EXISTING, already-tested, "
            "pre-M11-G6 behavior, confirmed by direct execution; (d) "
            "control 032's original 9-word heading exceeded the 7-word "
            "shape-gate cap entirely (an unrelated artifact) -- replaced "
            "with a 7-word compound that genuinely exercises the intended "
            "two-family collision; (e) control 033 only had NBSP in two "
            "of four word-gaps (typo) -- replaced with NBSP in every gap, "
            "which changed the measured outcome itself (see its own "
            "rationale); (f) control 034's expected value assumed the weak "
            "shape signal alone would exclude it, missing that the family "
            "match independently satisfies that same corroboration "
            "requirement -- corrected to UNKNOWN, matching the other "
            "formatting variants. No control's text or label was changed "
            "to make any genuine defect-relevant row agree with current "
            "behavior -- every correction either fixes pure terminology "
            "or aligns gold with PRE-EXISTING, documented, unrelated "
            "parser behavior, confirmed directly against the source, not "
            "against inference convenience. A SECOND, independently "
            "caught authoring bug (same session, before any commit): "
            "controls 015-024 (the already-correctly-working REQUIRED/"
            "PREFERRED/RESPONSIBILITY baseline positive controls) had "
            "skip_suppression_appropriate=True -- confusing 'this "
            "heading's classification is already correct' with the "
            "field's actual, documented meaning ('should ALL content "
            "under this heading be fully, unrecoverably suppressed'). "
            "Fixed to False for all ten; skip_suppression_appropriate is "
            "now True if and only if expected_heading_kind == 'SKIP', "
            "verified programmatically across all 44 controls. A THIRD "
            "round of corrections (same session): controls 008, 027, "
            "028, 033, 039, and 040 originally used body sentences too "
            "generic to match the EXISTING, unrelated "
            "_looks_like_requirement admission gate ('comfortable "
            "working...', 'has shipped...', 'someone who thrives...') "
            "-- correctly declined for that separate, pre-existing "
            "reason regardless of the heading finding, confounding the "
            "measurement. Reworded to carry clear requirement-signal "
            "vocabulary ('5+ years of experience...'), each verified by "
            "direct execution of _looks_like_requirement before "
            "committing. Control 044's 'Must have...' was similarly "
            "reworded to 'is required' for the same reason."
        ),
        "schema_notes": {
            "expected_heading_kind": (
                "Gold answer for what _classify_heading_line SHOULD resolve "
                "the heading_line to, per sound general policy -- one of "
                "REQUIRED/PREFERRED/RESPONSIBILITY/LEARNING/SKIP/UNKNOWN/"
                "NOT_A_HEADING -- these are the REAL _SectionKind enum "
                "member names (SKIP is the live code's own name for what "
                "this milestone's prose calls the NON_QUALIFICATION "
                "vocabulary family; the two are the same runtime value). "
                "NOT_A_HEADING: the line should not be recognized as a "
                "heading at all, i.e. _classify_heading_line returns None, "
                "or heading_line is null because the control has no "
                "heading."
            ),
            "skip_suppression_appropriate": (
                "True iff ALL content under this heading should be fully, "
                "unrecoverably suppressed (zero claims, zero diagnostics) -- "
                "the live behavior of _SectionKind.SKIP today. False for "
                "every heading where at least some body content could "
                "legitimately be a genuine, admissible qualification."
            ),
            "body_qualifications.expected_necessity": (
                "REQUIRED/PREFERRED/UNKNOWN (reported, not scored, when the "
                "section itself carries no default) or null for a "
                "non-qualification line. Never asserts a section-level "
                "default necessity without either a REQUIRED/PREFERRED "
                "section OR an explicit local marker in the claim text "
                "itself -- consistent with necessity.py's own real "
                "resolve_necessity_hint contract."
            ),
            "body_qualifications.should_enter_assessment": (
                "True iff this line should be admitted as AT LEAST a "
                "diagnostic claim (UnparsedClaim or JobRequirement) -- "
                "false for narrative/non-qualification lines that should "
                "be declined by the existing _looks_like_requirement gate "
                "or correctly suppressed by a genuine SKIP section."
            ),
        },
        "controls": CONTROLS,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"wrote {len(CONTROLS)} controls to {OUT_PATH}")


if __name__ == "__main__":
    main()
