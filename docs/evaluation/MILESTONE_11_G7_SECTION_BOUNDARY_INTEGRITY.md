# Milestone 11-G7 — Section Boundary Integrity

Evaluation-and-architecture-review milestone. **No production code was
modified.** `src/gitscore` is byte-identical to its state at the start
of this milestone (confirmed: `git diff --stat -- src/gitscore` is
empty throughout). Everything below is root-cause analysis,
evaluation-only simulation, and a recommendation awaiting explicit
implementation approval.

## 0. Verified baseline

| Expectation | Verified |
|---|---|
| HEAD | `380c31696aa16bd35e803e2f537668f0f15841f0` ✅ |
| Parser version | `job_description_parser:v11` (unchanged) ✅ |
| Full suite | 1595 passed, 13 skipped, 2 xfailed — unchanged throughout this milestone ✅ |
| `src/gitscore` | Zero diff throughout ✅ |

## 1. Exact root cause (Phase 1)

**File:** `src/gitscore/jobs/parsing/segmentation.py`, function `_classify_heading_line()` (word-count check at what is currently line ~418: `if word_count == 0 or word_count > 7: return None`).

The check is **uniform regardless of signal strength** — it rejects a line exceeding 7 words whether that line has a bare, unreliable plain-title-case shape (the actual false-positive risk the cap exists to prevent — "a single bare capitalized word standing alone," per the module's own docstring) or a **strong, unambiguous structural signal** (colon-termination, ALL-CAPS, or Markdown) that already, independently, gates a *different* corroboration rule a few lines later in the same function. A genuine, long, colon-terminated heading is therefore indistinguishable, at the word-count check, from an unreliable long run of plain prose.

**The cascade, traced exactly:** `segment_description()`'s main loop holds exactly one piece of forward-carrying state, `current_kind`, updated **only** when `_classify_heading_line()` returns non-`None`. When a genuine, long heading is misjudged as ordinary content (`None`), `current_kind` never updates — whatever section was open **before** that line silently persists into every line **after** it, until the next line that *does* happen to pass the shape gate (which may be much later, or never, in the rest of the document).

**Three distinct, independently confirmed severity tiers, depending on what `current_kind` was carrying:**

| Carried-forward state | Confirmed effect | Severity |
|---|---|---|
| `UNKNOWN`/`LEARNING` | Content after the boundary is gated by `_looks_like_requirement`; if admitted, necessity is `None` (diagnostic `UnparsedClaim`) — **never scored**. | **LOW** (M11-G5/G6's own finding) |
| `REQUIRED`/`PREFERRED` | Content after the boundary is admitted **unconditionally** (no gate at all) with a default necessity matching the stale state. A responsibility/duty sentence that happens to name a real technology becomes a **scored, ASSESSABLE `JobRequirement`** — confirmed directly to produce a non-`None`, non-zero-denominator `alignment_score` from text that was never a qualification. | **HIGH** — genuine scoring corruption |
| `SKIP` | Content after the boundary is dropped **unconditionally**, before a `Claim` even exists — confirmed directly to **silently, totally suppress** a genuine, explicitly locally-marked REQUIRED qualification (zero `JobRequirement`s, zero `UnparsedClaim`s). | **HIGH** — the exact M11-G5 failure mode, now shown to be reachable by heading *length* alone, with no vocabulary collision involved at all |

The HIGH-severity findings were **not anticipated by this milestone's own mission framing** (which described the risk as "a responsibility sentence appearing as an UnparsedClaim" — the LOW tier only) and were discovered and confirmed by direct execution during Phase 1, not assumed.

**Why `necessity.py`'s existing safety nets don't catch the HIGH-severity cases:** `resolve_necessity_hint`'s step 3 narrative-cue veto (`contains_narrative_cue()`) only matches two narrow grammatical shapes (a LEARNING-promise cue, or a "our team/product ... built/uses" / "we've built" company-narrative cue) — confirmed directly against `narrative.py` — neither matches a bare imperative duty sentence like "Mentor junior engineers while writing production Python services." Such a sentence sails through step 3 untouched whenever `current_kind` is stale-`REQUIRED`/`PREFERRED` (step 2's section-eligibility check passes for both, by design, since that is also where a *genuine* Requirements-section claim must keep its necessity).

**Independence from the competency-recall limitation (explicit Phase 1 ask):** this defect is entirely contained within `segmentation.py`'s shape gate — a purely structural (word-count) check, unrelated to `competency_extraction.py`'s vocabulary-matching `_QUALIFYING_INTENT_V2` gate (the confirmed cause of M11-F/G5's 12–16% tag-recall ceiling). The two live in different modules, address different problems, and a fix to one has no bearing on the other — **confirmed by inspection, not merely asserted: the proposed fix touches zero lines outside `_classify_heading_line`'s own word-count branch.**

## 2. Frozen evaluation results (Phase 2)

`evaluation/m11g7/boundary_controls.json` — **42 independently-authored, synthetic controls** (final `sha256=563e9b9a...`) across 16 categories: short/long headings (colon/Markdown/ALL-CAPS), ordinary prose, bullet lists (bare/numbered), responsibilities, qualifications, narrative sections, the three severity tiers isolated, section-transition correctness, Unicode/punctuation variants, and — the hardest category — **long colon-terminated lead-in sentences that are NOT headings at all**, introducing a sub-list from *inside* an already-open section.

**Honest disclosure: two pre-freeze correction rounds**, both caught by direct verification against the real code *before* any freeze (building on the process discipline from M11-G6):

1. A **field-scope** round: several controls' structural metadata (`heading_word_count`/`has_strong_shape_signal`) described the wrong heading (the embedded, second, defect-triggering heading) instead of the top-level `heading_line` field; one control (`021`) was authored as a "positive control" claiming an 8-word heading was "already recognized today" without verifying this directly — it was not (8 > 7) — replaced with a genuinely-verified 6-word heading.
2. A **family-matching** round, caught by batch-verifying every distinct heading-like string against the real `_matched_heading_families()` directly rather than assuming: the phrase *"What You Will Be Able To Build And Own"* (modeled on the real M11-G5 posting's own heading) does **not** match `_RESPONSIBILITY_ROOT` at all (which requires the bare word `respons*`, `duties`/`duty`, the exact phrase `what you('ll/will) do`, `the role`, or `day in this role` — none present) — six controls corrected from `RESPONSIBILITY` to `UNKNOWN`. Conversely, *"What You Will Be Responsible For"* **does** match the bare `respons*` alternative — one control corrected from `UNKNOWN` to `RESPONSIBILITY`. `^about\b`'s anchor is confirmed positional (requires the literal first character), not "contains the word about" — one control corrected from `SKIP` to `UNKNOWN`. One structural bug (a leftover edit fragment silently shifting two positional arguments) was also caught and fixed. **No control's safety-relevant outcome** (which lines must never be scored; which must never be silently lost) was changed by any correction — only labels, field scope, and family-matching predictions were.

**Final, clean measurement against the real, unmodified classifier** (`evaluation/reports/m11g7_phase1_current_behavior.json`):

| | Count |
|---|---|
| Heading-kind mismatches (defect rows) | 18 / 42 |
| **False requirement fabrications** (non-qualification scored as `JobRequirement`) | **5** (controls `019`, `030` ×2 each, `038` ×1) |
| **Silent suppressions** (genuine, locally-marked qualification totally lost) | **1** (control `020`) |

## 3. Candidate fixes and tradeoffs (Phase 3)

Four strategies simulated against all 42 frozen controls, reusing the real `_matched_heading_families`/`_is_titlecase_heading`/`_has_inline_colon_list`/`_strip_heading_decoration` helpers verbatim — never monkey-patching or editing `src/gitscore`:

| Strategy | Heading-match | Lead-in adversarial (3 controls) | Degenerate 42-word run-on |
|---|---|---|---|
| **Current (baseline)** | 24/42 | safe (not reached — no fix applied) | safe |
| **A — naive uniform raise to 20 words** | 42/42 | **UNSAFE — all 3 wrongly reclassified** | safe (lucky: 42 > 20) |
| **B — remove cap entirely for strong-signal lines** | 42/42 | **UNSAFE — all 3 wrongly reclassified** | **UNSAFE — wrongly reclassified** |
| **C — bounded raise to 14 words, strong-signal lines only** | 42/42 | **safe — all 3 correctly stay `NOT_A_HEADING`** | **safe — stays `NOT_A_HEADING`** |

**Option A (do not simply raise the limit — confirmed unsafe, exactly as the mission brief warned):** fixes all 18 defect rows, but a long, colon-terminated lead-in sentence introducing a sub-list from inside an *already-open* section (e.g. "Our ideal candidate will bring deep expertise across the following broad set of complementary technical and professional areas:" followed by a bare `Python` on the next line) gets wrongly promoted to a **new** `UNKNOWN` heading — which would demote `Python` out of the REQUIRED/RESPONSIBILITY/SKIP section it is actually inside of. Confirmed directly, not assumed. Rejected.

**Option B (remove the cap entirely for strong-signal lines):** fixes the same 18 rows, fails the **same** 3 lead-in adversarial tests, **and additionally** heading-ifies the deliberately-constructed 42-word degenerate run-on clause (any bare colon at the end of an arbitrarily long paragraph becomes "heading-shaped"). Strictly worse than A on one axis, no better on the other. Rejected.

**Option C (recommended) — bounded raise for strong-signal lines only, weak-signal lines unchanged:**

```python
# _classify_heading_line, restructured so has_strong_shape_signal is
# computed BEFORE the word-count decision (currently computed after):
word_count = len(content_no_colon.split())
cap = 14 if has_strong_shape_signal else 7
if word_count == 0 or word_count > cap:
    return None
```

Fixes all 18 defect rows, **passes every adversarial check**: the lead-in sentences (17–18 words) and the degenerate run-on (42 words) all correctly stay `NOT_A_HEADING`, because 14 is a genuine upper bound, not a removal of one. The bound (14) was chosen to comfortably cover every genuine long heading authored in this corpus (max 13 words) with one word of margin — **disclosed as a chosen constant, not independently re-derived from a larger real-world corpus survey**, exactly the same honesty standard M10C's own original 7-word choice was held to (§7).

**End-to-end verification of Strategy C on the three HIGH-severity controls**, via safe in-memory monkey-patching of `_classify_heading_line` (never written to disk), full real pipeline (`parse_job_description_with_diagnostics` → `match_job` → `assess_job`):

| Control | Before (current) | After (Strategy C) |
|---|---|---|
| `019` (REQUIRED carry-forward) | 2 fabricated `JobRequirement`s, `assessable_count=1`, `alignment_score=0` | 0 fabricated requirements, `assessable_count=0`, `alignment_score=None` |
| `020` (SKIP carry-forward) | 0 requirements, 0 diagnostics (total silent loss) | **1 genuine `JobRequirement` recovered** (REQUIRED, language category), `assessable_count=1`, `alignment_score=0` |
| `030` (PREFERRED carry-forward) | 3 requirements (1 genuine + 2 fabricated), `assessable_count=2` | 1 genuine requirement preserved + 1 correctly-downgraded diagnostic, 0 fabricated |

## 4. Measured false-positive/false-negative risks

- **False positives eliminated by Strategy C:** the 5 fabricated `JobRequirement`s (§2) all become diagnostics or disappear entirely — confirmed end-to-end (§3).
- **False negatives recovered by Strategy C:** the 1 silent total suppression (§2) becomes a genuine, correctly-scored `JobRequirement` — confirmed end-to-end (§3).
- **New false positives introduced by Strategy C:** **zero**, measured against all 42 controls including the 3 adversarial lead-ins and the degenerate run-on (§3) — the specific risk category this milestone's instructions explicitly warned against.
- **Residual, disclosed limitation:** the 14-word bound is a chosen constant, not exhaustively validated against an independent corpus of real-world long headings beyond this milestone's own 42 synthetic controls (max 13 words authored). A genuine heading longer than 14 words would still be missed — disclosed, not claimed as a complete fix, the same honesty standard applied throughout this project's prior milestones (e.g. M11-G6 §7's own bounded-vocabulary disclosure).
- **Interaction with M11-G6:** confirmed safe by direct construction and measurement (control `038`) — a heading combining both milestones' target phrasing (`_CANDIDATE_PROFILE_ROOT` vocabulary + a long heading) resolves to exactly one family (`RESPONSIBILITY`), no collision, no regression.

## 5. Recommended narrow solution

**Strategy C**: compute `has_strong_shape_signal` before the word-count decision (a pure reordering of two already-existing computations, no new logic), then branch the cap: 14 words for strong-signal (colon/ALL-CAPS/Markdown) lines, 7 words (unchanged) for weak-signal (bare title-case) lines. Zero other changes to `_classify_heading_line`, zero changes to `_matched_heading_families`, `necessity.py`, `narrative.py`, or any scoring/matcher file.

## 6. Expected production changes (if approved)

**Exactly one file:** `src/gitscore/jobs/parsing/segmentation.py` — move the existing `has_strong_shape_signal` computation (currently several lines below the word-count check) above it, and change the word-count condition from a single fixed `7` to a `14 if has_strong_shape_signal else 7` branch. Approximately 4–6 changed lines, no new function, no new `_SectionKind`, no new `Claim` field. A version bump (`JOB_DESCRIPTION_PARSER_VERSION`, `v11` → `v12`) in `parser.py`, consistent with this project's established per-milestone convention.

## 7. Explicit STOP questions

1. Approve implementing Strategy C exactly as simulated in §3 (reorder `has_strong_shape_signal` above the word-count check; branch the cap to 14/7), with no other `_classify_heading_line` changes?
2. Approve **14 words** as the strong-signal cap specifically, understanding it is a chosen, disclosed constant (not independently re-derived from a larger real-world survey) sized to this milestone's own corpus with a 1-word margin — or would a different, explicitly-justified bound be preferred?
3. Approve bumping `JOB_DESCRIPTION_PARSER_VERSION` to `v12` as part of this change?
4. Should the 42-control `evaluation/m11g7/boundary_controls.json` corpus and its three evaluation/simulation scripts be promoted into the permanent regression suite (a new `tests/test_m11g7_section_boundary_integrity.py`, mirroring M11-G6's own pattern) as part of implementing the fix?
5. Should the M11-G5 private p03 fixture be re-run end-to-end once this fix lands (as M11-G6's own Phase 4 did), to directly confirm the 2 qualifications still unrecovered after M11-G6 (`m11g5-p03-04`/`05`, lost for a separate, already-disclosed reason — the generic `_looks_like_requirement` vocabulary gate) remain correctly unaffected by this different fix?

## Commit-readiness verdict

**Not committed, per instructions.** New files produced this pass (all evaluation-only; `src/gitscore` untouched):

- `docs/evaluation/MILESTONE_11_G7_SECTION_BOUNDARY_INTEGRITY.md` (this doc)
- `evaluation/m11g7/boundary_controls.json` + `evaluation/m11g7/gold_hash_freeze.json`
- `scripts/evaluation_lib/m11g7_build_boundary_controls.py`
- `scripts/evaluation_lib/m11g7_preflight_check.py`
- `scripts/evaluation_lib/m11g7_phase1_current_behavior.py`
- `scripts/evaluation_lib/m11g7_phase3_candidate_fix_simulation.py`
- `evaluation/reports/m11g7_phase1_current_behavior.json`
- `evaluation/reports/m11g7_phase3_strategy_comparison.json`

All M11-D/F/G5 private data and the pre-existing untracked M11-generalization artifacts are untouched. **Stopping here per instructions — awaiting explicit implementation authorization before touching `src/gitscore`.**

---

# Addendum — Implementation Report (post-approval)

Everything above this line is the Phase 0–7 architecture-and-evaluation
review, preserved unedited as the historical record of what was
proposed and why. **This addendum records what was actually
implemented, tested, and measured after explicit approval was
granted for Strategy C only** (indiscriminate raise rejected,
unlimited recognition rejected, lead-in/heading distinction preserved,
necessity classification preserved — a recognized heading never
implies REQUIRED by itself).

## A1. Production file inventory

Exactly two production files changed, as proposed:

- `src/gitscore/jobs/parsing/segmentation.py` — `has_strong_shape_signal` moved above the word-count decision (pure reordering); the word-count condition changed from `if word_count == 0 or word_count > 7:` to `_word_count_cap = 14 if has_strong_shape_signal else 7` / `if word_count == 0 or word_count > _word_count_cap:`. ~5 changed lines plus a module-docstring addendum (established per-milestone convention).
- `src/gitscore/jobs/parsing/parser.py` — `JOB_DESCRIPTION_PARSER_VERSION` changed `v11` → `v12`, plus a matching docstring addendum.

`git diff --name-only -- src/gitscore` confirms exactly these two files and no others.

Test files updated (pre-existing tests tracking the version bump — never "frozen gold" in the annotation-corpus sense):

- `tests/test_m11g7_section_boundary_integrity.py` (**new** — written and run against the real classifier *before* implementation; 137 tests)
- `tests/test_m11a2_line_wrap_integrity.py`, `tests/test_m11b_qualification_model.py`, `tests/test_m11c_competency_extraction.py`, `tests/test_m11e_paraphrase_extraction.py` — each hardcoded `"job_description_parser:v11"` as "the version current when my own milestone completed"; updated to `v12` with a comment explaining why (unaffected in purpose).

No files were committed or pushed, per instructions.

## A2. Baseline red tests and post-fix results

Before implementation: `tests/test_m11g7_section_boundary_integrity.py` showed **22 failed, 115 passed** (18 heading-kind mismatches + 3 false-fabrication controls + 1 silent-suppression control), plus all 10 named category (A–J) tests passing — including categories A/B/C, which were deliberately written to assert the *defect itself* reproduces, confirming red the honest way (by proving the bug exists), not by a trivially-failing assertion.

After implementation: **137 passed, 0 failed.** The 4 tests whose assertions directly encoded "the defect exists today" (categories A, B, C, E) were updated to assert the new, correct behavior instead — mirroring the exact pattern M11-G6 used for the M11-G5 characterization tests it inherited. All other 133 tests (including the critical adversarial lead-in/degenerate-run-on anchors, categories F and H) required **zero changes** — they already encoded the correct, safe behavior and continued to assert it unchanged.

## A3. Exact 42-control outcomes

Re-measured via `m11g7_phase1_current_behavior.py` against the real, now-fixed classifier (gold hash re-verified unchanged throughout):

| | Before | After |
|---|---|---|
| Heading-kind mismatches | 18 / 42 | **0 / 42** |
| False requirement fabrications | 5 | **0** |
| Silent suppressions | 1 | **0** |

## A4. Fabricated requirement elimination counts

All 5 confirmed fabrications eliminated:

- `m11g7-019` (REQUIRED tier): 2 fabricated rows (`language`/`leadership` categories, both `Necessity.REQUIRED`) on the responsibility sentence → **0** fabricated rows after the fix.
- `m11g7-030` (PREFERRED tier): 2 fabricated rows (`language`/`leadership`, both `Necessity.PREFERRED`) → **0** after the fix.
- `m11g7-038`: 1 fabricated row → **0** after the fix (this control's own heading is now directly recognized as `RESPONSIBILITY`, so no carry-forward occurs at all).

## A5. Suppressed qualification recovery

`m11g7-020` (SKIP tier): before, **0 `JobRequirement`s and 0 `UnparsedClaim`s** (total, silent loss) for the genuine, locally-marked "Experience with Python and distributed systems is required." claim. After: **1 genuine `JobRequirement`**, `necessity=REQUIRED`, `category=language`, recovered exactly as gold expected.

## A6. Real matcher/scorer before-and-after results

Via the real `match_job`/`assess_job` pipeline with a deterministic, empty `CandidateEvidenceProfile` (no evidence at all — isolates the parser-level effect from any candidate-specific variability):

| Control | Before: reqs / unparsed / assessable / score | After: reqs / unparsed / assessable / score |
|---|---|---|
| `019` (REQUIRED carry-forward) | 2 / 2 / **1** / **0** | 0 / 2 / **0** / **None** |
| `020` (SKIP carry-forward) | 0 / 0 / **0** / **None** | 1 / 0 / **1** / **0** |
| `030` (PREFERRED carry-forward) | 3 / 1 / **2** / **0** | 1 / 1 / **1** / **0** |

Every `MatchStatus` for the fabricated-then-eliminated rows was `NOT_OBSERVED`/`NOT_ASSESSABLE` before (confirming the corruption was already partially masked for `019` by one row landing `NOT_ASSESSABLE`, but the OTHER row — the real, technology-naming one — was fully `NOT_OBSERVED` and counted in the denominator); after, the sole genuinely assessable row for `020` is `NOT_OBSERVED` (correct: this deterministic candidate has zero evidence, so a 0% score on a real, now-visible requirement is the intended, correct outcome of recovering a false negative — not a new defect). **No scoring formula was changed** to produce these differences — they are the direct, legitimate effect of correcting which `JobRequirement`s exist in the first place, exactly as the approval anticipated ("a legitimate score change caused by correcting the job requirements is acceptable").

**No new false-assessable requirements appeared anywhere in the 42-control corpus** — confirmed by the same measurement showing 0 fabrications post-fix (§A3/A4).

## A7. Source-span verification

Confirmed directly (and by the dedicated `test_category_j_exact_source_spans_preserved` test): `Claim.start`/`Claim.end` computation in `segment_description()` never reads `section_kind` or any family-match result — span computation and heading classification are fully independent code paths, unchanged by this fix. Every requirement's `source_span`, both before and after, is the exact, same-as-always offset into the original description.

## A8. Full backend test results and xfail status

| | Before | After |
|---|---|---|
| Full suite | 1595 passed, 13 skipped, 2 xfailed | **1732 passed**, 13 skipped (unchanged), **2 xfailed (unchanged)** |

1732 − 1595 = 137, exactly the new test file's own count. **No previously-passing test became skipped.** The two M11-G6 xfails were explicitly reviewed per instructions: both concern `m11g6-034-who-we-are-looking-for-em-dash`, a 5-word heading — below even the unchanged 7-word weak-signal cap, and the em-dash form carries no colon/ALL-CAPS/Markdown, so `has_strong_shape_signal` is `False` for it regardless of this fix. Confirmed, not merely asserted: re-ran `tests/test_m11g6_heading_classification.py` after the G7 change and the same two `XFAIL`s reproduce with byte-identical reasons — this fix's 7-vs-14 branch is structurally unreachable for that control. No marker was changed.

## A9. Historical evaluation comparison

M10A–M10E, M9B, M11-B/C/E, M11-G1–G6, and the frozen 8c:v1/v1.1 checks were run explicitly (`pytest -k "8c or m10 or m9b or m11g1 or m11g2 or m11g3 or m11g4 or m11g5 or m11g6 or m11b or m11c or m11e"`): **632 passed, 10 skipped, 2 xfailed** — all included, unchanged, in the full-suite total above.

## A10. Remaining limitations

1. **The 14-word cap is a disclosed, bounded constant**, not independently re-derived from a larger real-world heading-length survey beyond this milestone's own 42-control corpus (max 13 words authored, 1-word margin). A genuine heading longer than 14 words would still be missed — not claimed as a complete fix for every conceivable heading length.
2. **Independent of the competency-recall limitation** (confirmed by inspection: the fix touches zero lines outside `_classify_heading_line`'s word-count branch) — not re-measured here, not claimed to be affected by this fix in either direction.
3. The `_looks_like_requirement` admission-gate's own vocabulary completeness (the separate, already-disclosed reason 2 of M11-G5's own 7 qualifications remain unrecovered even after M11-G6) is untouched and out of scope for this heading-length-only fix.

## A11. Commit-readiness verdict

**Implemented, tested, and documented — not committed, per instructions.** Full backend suite green (1732 passed, 13 skipped, 2 unchanged xfailed), zero unexplained regressions, all 5 confirmed fabrications eliminated, the 1 confirmed silent suppression recovered, zero new false-assessable requirements anywhere in the 42-control corpus. Ready for the user's own commit decision; nothing was staged or pushed by this pass.
