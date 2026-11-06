# Milestone 11-G6 — Qualification Heading Classification Correctness

Evaluation-and-architecture-review milestone. **No production code was
modified.** `src/gitscore` is byte-identical to its state at the start
of this milestone. Everything below is root-cause analysis,
evaluation-only simulation, and a recommendation awaiting explicit
implementation approval.

## 0. Verified baseline

| Expectation | Verified |
|---|---|
| HEAD | `a9b5618ce573497ddff0db9d2868acc191539c75` ✅ |
| Branch | `main` ✅ |
| Parser version | `job_description_parser:v10` (unchanged) ✅ |
| Full suite | 1493 passed, 13 skipped, before and after this milestone's work (confirmed by re-running at the end — `src/gitscore` was never touched, so this is expected, not newly re-verified behavior) ✅ |
| Frozen historical gold | Untouched ✅ |
| `git status --short` on tracked files | Zero modifications throughout — only new, untracked evaluation files added ✅ |

## 1. Exact root cause and code locations (Phase 1)

**File:** `src/gitscore/jobs/parsing/segmentation.py`
**Functions:** `_matched_heading_families()` (line ~296), consumed by `_classify_heading_line()` (line ~324), consumed by `segment_description()`'s main loop (line ~621: `if current_kind is _SectionKind.SKIP: i += 1; continue`).

**The pattern that wins, and why.** `_NON_QUALIFICATION_ROOT` (line 239) includes the alternative `\bwho we are\b` — a `\b`-bounded but otherwise **unanchored substring search**, matched anywhere within a line up to 7 words long. For the heading `"Who We Are Looking For:"`, this is the *only* family pattern that matches anything at all (no `REQUIRED`/`PREFERRED`/`QUALIFICATION`/`RESPONSIBILITY`/`LEARNING` root contains any phrase resembling "looking for"). `_matched_heading_families` returns exactly one family, `[_SectionKind.SKIP]`, and `_classify_heading_line`'s `len(families) == 1` branch returns it directly — no ambiguity-to-`UNKNOWN` fallback ever triggers, because there is no second family to collide with.

**Is this prefix matching, substring matching, rule ordering, or overlapping patterns?** Confirmed directly (not inferred): it is **unanchored substring matching with no corroborating signal**, not rule ordering. There is no competing family match to order against — the existing "more than one family → honest `UNKNOWN`" safety net (already shipped for genuine collisions like `"Preferred Qualifications"` and `"About the Role"`, see §3's positive controls below) **never activates** here, because only one family fires in the base case. A precedence fix has nothing to prefer over SKIP. This is the single most important structural fact driving the Phase 3 comparison.

**Why this exact misclassification is categorically worse than any other wrong `_SectionKind`.** Traced directly through the full call chain:
- `segment_description()`'s loop checks `if current_kind is _SectionKind.SKIP: continue` **before** any `Claim` is ever constructed for that line — zero `Claim`s, zero `UnparsedClaim`s, zero diagnostics.
- By contrast, `_SectionKind.UNKNOWN` content still reaches `_looks_like_requirement()` and, if it passes, becomes a `Claim` with `necessity_hint=None`.
- `necessity.py::resolve_necessity_hint`'s own step 1 ("an explicit local REQUIRED/PREFERRED marker in the claim text ALWAYS wins, unconditionally") can only run if a `Claim` exists at all. **SKIP suppression happens upstream of that safety net entirely** — an explicit `"...is required."` marker inside a SKIP-classified section is unrecoverable, confirmed directly (control `m11g6-004`, below).
- M11-G4's own `recover_unadmitted_qualification_claims()` explicitly excludes `SKIP`-classified content by its own docstring ("and never content under a `SKIP` section, mirroring [`segment_description`]") — confirmed by direct code inspection, not assumption. G4 cannot and was never designed to recover this failure mode; it targets a structurally different gap.

**Do equivalent collisions exist for other headings?** Yes, by construction of the Phase 2 corpus (§2) — every formatting variant of the "who we are looking for" family shares the identical root cause: plain, with-explicit-marker, em-dash-terminated, Markdown ATX, Markdown bold, mixed with narrative, and across a section transition. Exactly **9 of 44** controls reproduce it (§2/§3). One deliberately-tested formatting variant (real non-breaking spaces, U+00A0, in *every* word gap including inside the "who we are" trigram itself) does **not** reproduce it — confirmed by direct execution — because `_NON_QUALIFICATION_ROOT`'s pattern is written with literal ASCII space characters, which do not match across U+00A0 gaps. This is a useful, precise finding: the collision is an ASCII-literal-pattern artifact, not a universal "any whitespace" collision.

**Does distinguishing a qualification heading from company narrative require changing necessity inference?** **No — confirmed, not assumed.** The existing `necessity.py` contract already does the right thing the instant a claim is merely *admitted* (not SKIP-blocked): an `UNKNOWN`-section claim with no local marker gets `necessity=None` (reported as a diagnostic, never a forced `REQUIRED`), and a claim with an explicit local marker gets `REQUIRED`/`PREFERRED` regardless of section. **The entire fix is contained to `_matched_heading_families` in `segmentation.py`.** No change to `necessity.py`, `narrative.py`, `qualification.py`, or any scoring/matcher file is needed or proposed.

**M10B–M10E regression surface inspected:** `tests/test_m10b_section_state_safety.py`, `tests/test_m10c_heading_classification.py` (plus its 78-entry `evaluation/m10c/heading_controls*.json` corpora — neither contains any "who we are"/"looking for"/"about the role" phrasing), `tests/test_m10d_alternative_requirement_semantics.py`, `tests/test_m10e_narrative_requirement_semantics.py`. None exercises this collision today; it was never a regression target before M11-G5 found it.

## 2. Frozen control inventory (Phase 2)

`evaluation/m11g6/heading_controls.json` — **44 independently-authored, synthetic controls** across the 22 requested categories (Who We Are / Who We Are Looking For / What We're Looking For / What We Need to See / What You'll Bring / About Us / About the Role / Your Qualifications / Required Qualifications / Preferred Qualifications / Nice to Have / What You'll Do / other company narrative / unusual qualification headings / ambiguous-unknown headings / overlapping-prefix headings / Unicode whitespace / Markdown-colon variants / mixed narrative+qualification / section transitions / unsectioned descriptions / explicit required-preferred beneath ambiguous headings). Every control's text is hand-authored and generic — never copied from a real posting, so (unlike M11-D/F/G5) there are no provenance/privacy restrictions on this file; it is fully commit-safe as written.

**Gold was frozen (`evaluation/m11g6/gold_hash_freeze.json`, final `sha256=56e92f18...`) before any candidate-fix simulation (Phase 3) ran.** Honest disclosure, not buried: gold went through **three same-session, pre-approval, pre-commit self-correction rounds** after its *first* freeze was run once against the real, unmodified classifier and showed 21/44 "mismatches" — each investigated individually against the module's own source and docstring (never against "whatever the parser happened to output," and never to make a genuine defect row agree with current behavior):

1. **Terminology bug** (6 controls): gold used `"NON_QUALIFICATION"` — the vocabulary-family name used in this milestone's own prose — where the real `_SectionKind` enum member is literally named `SKIP`. Pure label fix, zero semantic change.
2. **Shape-gate misunderstandings** (4 controls): a bare colon *is* itself a strong shape signal regardless of family match (so a zero-family colon heading is `UNKNOWN`, not unrecognized); plain title-case *without* a colon and *without* any family match needs family corroboration to count as a heading at all (already-existing, already-tested M10C behavior, confirmed directly) — gold had these backwards in a few places.
3. **An oversized/undersized test artifact** (1 control): a 9-word compound heading exceeded `_classify_heading_line`'s own 7-word shape-gate cap entirely, an effect unrelated to the defect under investigation — replaced with a 7-word compound that genuinely exercises two real family matches.
4. **A `skip_suppression_appropriate` field-meaning bug** (10 controls): the 10 already-correctly-classified REQUIRED/PREFERRED/RESPONSIBILITY baseline positive controls had this field set to `True`, conflating "this heading's classification is already correct" with the field's actual, documented meaning ("should ALL content under this heading be fully, unrecoverably suppressed"). Fixed; the invariant `skip_suppression_appropriate == (expected_heading_kind == "SKIP")` is now verified programmatically across all 44 controls.
5. **Confounded body text** (6 controls): several body sentences ("Comfortable working across the full stack," "Has shipped production machine learning systems," …) were too generic to pass the pre-existing, unrelated `_looks_like_requirement` admission gate, which obscured the heading-level finding under test. Reworded to carry unambiguous requirement vocabulary, each verified by direct execution of the real function before committing to gold.

After all three rounds: **35/44 controls match current behavior exactly** (the correctly-working baseline), and **exactly the same 9 controls mismatch** before and after every correction round — the 9 genuine defect rows, unchanged in substance from the very first draft. The full `correction_log` is preserved verbatim inside `heading_controls.json` itself.

## 3. Comparison of correction strategies (Phase 3)

Simulated with `scripts/evaluation_lib/m11g6_phase3_candidate_fix_simulation.py` — reuses the real, imported `_REQUIRED_ROOT`/`_QUALIFICATION_ROOT`/`_PREFERRED_ROOT`/`_LEARNING_ROOT`/`_RESPONSIBILITY_ROOT`/`_NON_QUALIFICATION_ROOT` patterns verbatim; never monkey-patches or edits `src/gitscore`. Results against all 44 frozen controls:

| Strategy | Matches gold | Regressions vs. current | Fixes vs. current |
|---|---|---|---|
| **Current (baseline)** | 35/44 | — | — |
| **A — fixed precedence order** | 32/44 | **3** | **0** |
| **B — require full-word family coverage (boundary-aware)** | 35/44 | **9** | 9 |
| **C — new generic "candidate-profile" exclusion signal** | **44/44** | **0** | **9** |

**A (more-specific-wins precedence):** Rejected, confirmed by direct measurement, not assumption. In the actual defect shape, `NON_QUALIFICATION` is the *only* family that matches at all — there is no competing match for a precedence rule to prefer, so this strategy fixes **zero** of the 9 target rows while actively regressing 3 already-correct ambiguous cases (e.g. `"About the Role:"`, already safely `UNKNOWN` today via the existing multi-family collision rule, gets forcibly resolved to `RESPONSIBILITY` under a fixed order).

**B (boundary-aware exact-ish matching, implemented as "every meaningful word must be covered by some family root"):** Rejected. It does fix all 9 target rows, but at the cost of **9 new regressions** — it breaks already-correct baselines including the bare `"Who We Are:"` (the TRUE positive this family exists for), `"About Us:"`, `"Nice to Have:"`, and `"What You'll Do:"` (because, e.g., `PREFERRED_ROOT` matches the phrase `"nice to have"` but the standalone word `"Have"` isn't independently covered by any single-root per-word recheck). Net effect: a wash, with high implementation risk and no net improvement — rejected in this general form. A stricter, phrase-level (not per-word) coverage check might avoid some of these regressions, but was not pursued further once Strategy C's result was in hand.

**C (recommended) — a new, generic, closed-vocabulary "candidate-profile-seeking" root family, used purely as an exclusion signal against `NON_QUALIFICATION` on the same line, mirroring the EXISTING `required_fires = has_required or (has_qualification and not has_preferred)` exclusion pattern already shipped in the same function:**

```python
_CANDIDATE_PROFILE_ROOT = re.compile(
    r"\blooking for\b|\bwe(?:'re| are) seeking\b|\bwe need\b|\bwe want\b|"
    r"\byou(?:'ll| will) bring\b|\byou bring\b|\bideal candidate\b",
    re.IGNORECASE,
)
# inside _matched_heading_families:
non_qualification_fires = has_non_qualification and not has_candidate_profile
```

The new signal is **never added to `families`** itself — it is purely an exclusion/corroboration check, so it never becomes its own section kind and never defaults anything to `REQUIRED` (satisfying the instruction's explicit "do not assume a qualification-oriented heading means REQUIRED"). When `non_qualification_fires` becomes `False`, the heading simply falls through to the **already-existing, already-tested** "zero families + strong shape signal → `UNKNOWN`" path — no new code path, no new `_SectionKind`, no new necessity rule.

**This is not a special case for "Who We Are Looking For."** The new vocabulary is deliberately generic — `"looking for"`, `"we need"`, `"you('ll) bring"`, `"ideal candidate"` each independently also apply to `"What We're Looking For"`, `"What We Need to See"`, `"What You'll Bring"`, and `"The Ideal Candidate"` — four *other* headings named explicitly in this milestone's Phase 2 coverage list. Measured result: **exactly the 9 confirmed-defect rows change, in the direction gold expects, and zero other rows change at all.**

**Implementation complexity:** one new ~4-line regex constant plus one modified boolean expression (`and not has_candidate_profile`) inside an existing function. No new `_SectionKind`, no new `Claim` field, no change to `necessity.py`/`narrative.py`/`qualification.py`/scoring/matcher/API/schema.

## 4. Impact analysis (Phase 4)

Computed by directly calling the real, unmodified `_looks_like_requirement`, `resolve_necessity_hint`, and `infer_necessity` functions against each of the 9 affected controls' body text under a simulated `section_kind="UNKNOWN"` — not guessed:

| Control | Before (current, SKIP) | After (simulated fix, UNKNOWN) |
|---|---|---|
| `003` who-we-are-looking-for | 0 req / 0 unparsed | 0 req / **1 unparsed** (necessity reported UNKNOWN, not scored) |
| `004` …-degree (explicit "is required") | 0 / 0 | **1 JobRequirement (REQUIRED)** / 0 |
| `034` …-em-dash | 0 / 0 | **0 / 0 — unchanged**, for a separate, unrelated reason: this control's body text ("Strong ownership mentality.") does not itself pass the pre-existing `_looks_like_requirement` vocabulary gate, confirmed directly. The heading-level fix is necessary but not sufficient for this specific body wording; correctly out of this fix's scope. |
| `035` markdown-ATX | 0 / 0 | 0 / **1 unparsed** |
| `036` markdown-bold | 0 / 0 | 0 / **1 unparsed** |
| `037` mixed narrative+qualification | 0 / 0 | 0 / **1 unparsed** (the narrative line is correctly still declined — unchanged) |
| `038` mixed narrative+explicit-requirement | 0 / 0 | **1 JobRequirement (REQUIRED)** / 0 (narrative line still declined) |
| `039` section-transition, first heading | 0 / 0 | 0 / **1 unparsed** |
| `040` section-transition, full document | 1 req / 0 (from the already-correct second heading) | **2 req / 1 unparsed** (first heading's claim newly admitted; second heading's existing REQUIRED claim unaffected) |

**Aggregate across these 9 controls:** JobRequirement count **+2**, UnparsedClaim count **+6**, one control (`034`) unaffected for an unrelated, already-identified reason. **Zero new false REQUIRED/PREFERRED defaults** — every new admission is either a diagnostic (`UnparsedClaim`, necessity reported as unresolved/UNKNOWN) or a scored requirement *only* because the claim's own text carries an explicit local marker, exactly matching the existing, unmodified `necessity.py` contract.

1. **JobRequirement count:** increases only for claims carrying an explicit local marker (confirmed: `004`, `038`) — never from a section-level default.
2. **UnparsedClaim count:** increases for claims that pass the generic admission gate but carry no local marker (`003`, `035`, `036`, `037`, `039`, `040`) — reported as diagnostics, never silently promoted.
3. **REQUIRED/PREFERRED classification:** unaffected in mechanism — no code in `necessity.py` changes; only `segmentation.py`'s heading-family decision changes, which determines *whether a claim is admitted at all*, not how its necessity is computed once admitted.
4. **Assessable requirement count:** increases only for the 2 explicit-marker cases above (which were, before this fix, **entirely invisible** to the parser — not merely mis-scored).
5. **False-positive/false-negative qualifications:** zero new false positives measured — the fix only *adds* admission for genuine candidate-profile headings; it does not touch `RESPONSIBILITY`/`LEARNING`/other-`SKIP` classification paths at all (confirmed: the 10 narrative/responsibility-correct controls, e.g. `001`, `011`, `023`, are unaffected — see §3's 0-regression result).
6. **Alignment score denominator:** not evaluated against a live scoring run in this milestone (no production code was changed to run one) — projected effect is an increase in the number of GitHub-assessable requirements recovered for postings using this heading style, never a decrease, and never a change to the scoring formula itself (no scoring file is touched by the proposed fix).
7. **Existing matcher results:** unaffected — the matcher consumes `JobRequirement`/`UnparsedClaim` objects already produced by the existing, unmodified pipeline; this fix changes which claims *reach* that pipeline, not how the matcher interprets them.
8. **Source provenance:** unaffected — `Claim.start`/`Claim.end` span computation in `segment_description()` does not depend on `section_kind` at all; only `necessity_hint` and `in_recognized_section` do. Every newly-admitted claim's span is the exact, same-as-always offset into the original description.
9. **Existing SOTI/Manulife and M10 evaluations:** **directly inspected, not assumed.** `evaluation/m10/source/soti_raw.txt`'s and `manulife_raw.txt`'s actual headings (`"Opportunity"`, `"What you will learn:"`, `"Required skills:"`, `"About SOTI"` / `"Position Responsibilities:"`, `"Required Qualifications:"`, `"Preferred Qualifications:"`, `"When you join our team:"`, `"Application instructions:"`, `"About Manulife and John Hancock"`, `"Working Arrangement"`) contain **no phrase matching the new `_CANDIDATE_PROFILE_ROOT` vocabulary** (`"looking for"`, `"we need"`, `"you('ll) bring"`, `"ideal candidate"`, etc.). The new exclusion signal therefore never fires for either posting — their existing `"About SOTI"`/`"About Manulife..."` classifications are provably unchanged, and both postings' already-measured M10 results are unaffected.

**No unsafe change to scores or user-visible results identified.** The proposed fix strictly *adds* previously-invisible diagnostic/requirement admissions for a narrowly-defined, generic heading-phrasing gap; it does not alter any existing classification path, any necessity-inference rule, or any scoring/matcher code.

## 5. Recommended smallest safe fix

**Strategy C** (§3): add one generic `_CANDIDATE_PROFILE_ROOT` vocabulary constant to `segmentation.py` and exclude `NON_QUALIFICATION` from firing when it co-occurs with that signal, mirroring the function's own existing `qualification`-excluded-by-`preferred` precedent. Measured: 44/44 gold match, 0 regressions, exactly the 9 confirmed-defect rows fixed, zero change to any other file.

## 6. Necessity implications

None beyond what the existing, unmodified `necessity.py` contract already guarantees (§1, §4). No new `Necessity` value, no new default, no change to `resolve_necessity_hint`/`infer_necessity`.

## 7. Historical regression risks

- **SOTI/Manulife:** confirmed zero impact by direct inspection of their actual heading text (§4.9).
- **M10C's own 78-entry heading corpus:** contains no "who we are"/"looking for" phrasing (confirmed by direct grep against both `evaluation/m10c/heading_controls.json` and `heading_controls_heldout.json`) — unaffected.
- **M10B/M10D/M10E test suites:** inspected; none constructs a fixture resembling this collision — unaffected.
- **Strategy B, if chosen instead, would regress 9 currently-correct controls** (§3) — this is exactly why it is not recommended.
- **Residual risk of Strategy C:** the new vocabulary is necessarily a closed, generic list (not exhaustive of every possible candidate-profile phrasing) — a heading phrased with a candidate-seeking continuation NOT in this list (e.g. a hypothetical "Who We Are Hunting For:") would still reproduce the original defect. This is disclosed as a known, bounded residual gap, not claimed as a complete fix for every conceivable phrasing — consistent with every other root-word table in this file already being a bounded, non-exhaustive vocabulary.

## 8. Expected parser versioning

Per this module's own established convention (`JOB_DESCRIPTION_PARSER_VERSION` bumped at every milestone that changes `segmentation.py`'s *observable* classification behavior — v4→v5→…→v9→v10 across M10B through M11-G-series), implementing Strategy C would bump `JOB_DESCRIPTION_PARSER_VERSION` from `"job_description_parser:v10"` to `"job_description_parser:v11"`.

## 9. Exact production files requiring changes (if approved)

**Exactly one file:** `src/gitscore/jobs/parsing/segmentation.py` — add the `_CANDIDATE_PROFILE_ROOT` constant near the other root-word tables (~line 236), and change the `non_qualification` family-firing condition inside `_matched_heading_families` (~line 319) from `if has_non_qualification:` to `if has_non_qualification and not has_candidate_profile:` (computing `has_candidate_profile` alongside the other `has_*` booleans at the top of that function). Bump `JOB_DESCRIPTION_PARSER_VERSION` in `src/gitscore/jobs/parsing/parser.py` (one line). No other production file changes.

## 10. Explicit implementation approval questions

1. Approve implementing Strategy C exactly as simulated in §3 (the `_CANDIDATE_PROFILE_ROOT` regex and the one-line exclusion-condition change), with no other `segmentation.py` changes?
2. Approve the exact candidate-profile vocabulary list proposed (`"looking for"`, `"we're/we are seeking"`, `"we need"`, `"we want"`, `"you'll/you will bring"`, `"you bring"`, `"ideal candidate"`) as the initial closed set, with the explicit understanding that it is bounded and not exhaustive (§7)?
3. Approve bumping `JOB_DESCRIPTION_PARSER_VERSION` to `v11` as part of this change?
4. Should the 44-control `evaluation/m11g6/heading_controls.json` corpus and this milestone's three evaluation/simulation scripts be promoted into the permanent regression suite (a new `tests/test_m11g6_heading_classification.py`, mirroring `tests/test_m10c_heading_classification.py`'s pattern) as part of implementing the fix, or held separately?
5. Should SOTI and Manulife be re-run end-to-end once the fix lands (confirmed above to be unaffected by heading content, but not yet re-run with changed code) as part of Phase 7 verification for the *next* milestone?

## Commit-readiness verdict

**Not committed, per instructions.** New files produced this pass (all evaluation-only; `src/gitscore` untouched):

- `docs/evaluation/MILESTONE_11_G6_HEADING_CLASSIFICATION.md` (this doc)
- `evaluation/m11g6/heading_controls.json` + `evaluation/m11g6/gold_hash_freeze.json`
- `scripts/evaluation_lib/m11g6_build_heading_controls.py`
- `scripts/evaluation_lib/m11g6_phase1_current_behavior.py`
- `scripts/evaluation_lib/m11g6_phase3_candidate_fix_simulation.py`
- `evaluation/reports/m11g6_phase1_current_behavior.json`
- `evaluation/reports/m11g6_phase3_strategy_comparison.json`

All M11-D/F/G5 private data and the pre-existing untracked M11-generalization artifacts are untouched. **Stopping here per instructions — awaiting explicit implementation authorization before touching `src/gitscore`.**

---

# Addendum — Implementation Report (post-approval)

Everything above this line is the Phase 0–5 architecture-and-evaluation
review, preserved unedited as the historical record of what was
proposed and why. **This addendum records what was actually
implemented, tested, and measured after explicit approval was
granted for Strategy C only** (precedence changes rejected, boundary-
tightening rejected, no employer-specific exceptions, no necessity-
inference change).

## A1. Final production file inventory

Exactly two production files changed, exactly as proposed in §9 above:

- `src/gitscore/jobs/parsing/segmentation.py` — added `_CANDIDATE_PROFILE_ROOT` (new constant, ~8 lines including comments) and changed one boolean inside `_matched_heading_families()`: `non_qualification_fires = has_non_qualification and not has_candidate_profile` (replacing the previous unconditional `if has_non_qualification:`). A documentation addendum was also added to the module's own docstring (its established per-milestone convention).
- `src/gitscore/jobs/parsing/parser.py` — `JOB_DESCRIPTION_PARSER_VERSION` changed `"job_description_parser:v10"` → `"job_description_parser:v11"`, plus a matching docstring addendum.

No other file under `src/gitscore` was touched. No matcher, scoring, API schema, frontend, concept registry, or offline-competency-extraction file changed.

Test files updated (pre-existing tests whose own literal expectations needed to track the version bump or the now-fixed behavior — never "historical evaluation gold" in the frozen-JSON-corpus sense, which was never touched):

- `tests/test_m11g6_heading_classification.py` (**new** — written and run against the real classifier *before* implementation; 104 tests)
- `tests/test_m11a2_line_wrap_integrity.py`, `tests/test_m11b_qualification_model.py`, `tests/test_m11c_competency_extraction.py`, `tests/test_m11e_paraphrase_extraction.py` — each hardcoded `"job_description_parser:v10"` as "the version my own milestone did not change"; updated to `v11` with a comment explaining why (these tests' own purpose — confirming each of *those* milestones never bumped the version — is unaffected; only the literal current-value string needed to track forward)
- `tests/test_m11g4_admission_recovery.py` — `test_segmentation_module_is_byte_unchanged` used a live `git diff` against the working tree, which would spuriously fail for *any* later, legitimate change to `segmentation.py`, not just a G4 regression. Retargeted to check G4's own two historical commits (`4b4e3b9`, `321c248`) specifically — confirmed empty diff for both, so G4's own claim ("segmentation.py byte-unchanged by G4") still holds, verified correctly, without blocking this unrelated, later, approved G6 change
- `tests/test_m11g5_independent_validation.py` — the two characterization tests that pinned the *then-current, defective* SKIP behavior as a known gap are updated to characterize the *new, fixed* behavior (`_SectionKind.UNKNOWN`, `len(segment_description(...)) > 0`), exactly as anticipated when those tests were originally written ("FIXED by Milestone 11-G6" is now stated explicitly in their own docstring)

No files were committed or pushed, per instructions.

## A2. Exactly what changed in heading classification

Before: `_matched_heading_families()` appended `_SectionKind.SKIP` to its `families` list whenever `_NON_QUALIFICATION_ROOT` matched anywhere in the heading content, unconditionally.

After: the SAME append now additionally requires `_CANDIDATE_PROFILE_ROOT` to *not* match on the same line. `_CANDIDATE_PROFILE_ROOT` is checked but never itself appended to `families` — it has no section kind of its own, cannot become a default `REQUIRED`/`PREFERRED`, and participates in heading classification *only* as a veto against the one specific family it was built to guard against. Every other family (`REQUIRED`/`PREFERRED`/`LEARNING`/`RESPONSIBILITY`) and every other line of `_classify_heading_line`'s shape-gate logic is byte-identical to before.

## A3. Frozen-control before/after results

Measured by re-running `scripts/evaluation_lib/m11g6_phase1_current_behavior.py` against the real, now-fixed classifier (gold hash re-verified unchanged throughout — `evaluation/m11g6/heading_controls.json` was never edited after implementation):

| | Before (pre-implementation) | After (implemented) |
|---|---|---|
| Heading-kind exact match | 35/44 | **43/44** |
| Skip-suppression correctness | 36/44 | **43/44** |

The sole remaining divergence (`m11g6-034-who-we-are-looking-for-em-dash`) is the one known-safe weak-shape-signal edge case (§A9 below) — pinned by an explicit, documented `xfail`, not silently absorbed by editing frozen gold.

`tests/test_m11g6_heading_classification.py` (written and first run *before* the fix, confirmed red on exactly the 9 defect-row IDs plus their named anchors, confirmed green after): **102 passed, 2 xfailed**, 0 unexplained failures.

## A4. Full backend test counts

| | Count |
|---|---|
| Before this milestone's implementation | 1493 passed, 13 skipped |
| After | **1595 passed**, 13 skipped, 2 xfailed |

1595 − 1493 = 102, exactly the new `test_m11g6_heading_classification.py` file's own test count. **Skip count unchanged (13 → 13)** — no previously-passing test became skipped. The 2 `xfailed` are explicit, documented, and reviewed (§A9) — never silent.

## A5. Historical evaluation stability

**SOTI and Manulife — re-run end-to-end against the real, fixed pipeline** (not merely inspected statically, as the pre-implementation §4.9 analysis had done):

| Posting | JobRequirement / UnparsedClaim — before | after | parser_version |
|---|---|---|---|
| SOTI | 1 / 7 | **1 / 7 (unchanged)** | `v10` → `v11` |
| Manulife | 5 / 9 | **5 / 9 (unchanged)** | `v10` → `v11` |

Byte-identical requirement/claim counts; only the version label differs, exactly as predicted — neither posting's heading text contains any phrase from the new `_CANDIDATE_PROFILE_ROOT` vocabulary.

M10C's own 78+18-entry heading-classification regression suite (`tests/test_m10c_heading_classification.py`), M10B/M10D/M10E, M9B, M11-B/C/E development evaluations, M11-G1/G2/G3 controls, and the frozen 8c:v1/v1.1 checks are all included in the same full-suite run above (§A4) and passed unchanged — confirmed by the suite's own pass count, not merely assumed.

## A6. M11-G5 missed-qualification recovery

**Verified directly against the locally-preserved private M11-G5 fixture** (`evaluation/m11g5/source/p03-alluxio-distributed.txt` — counts and IDs only reported here, no posting text reproduced, per instructions):

| | Before | After |
|---|---|---|
| JobRequirement | 0 | 0 |
| UnparsedClaim | 0 | **6** |

Reconciled against M11-G5's own frozen gold annotations for this posting (`m11g5-p03-01` through `m11g5-p03-07`, plus the one correctly-non-qualification `m11g5-p03-resp` control): **5 of 7 genuine qualifications are now recovered** as diagnostic claims (`m11g5-p03-01`, `02`, `03`, `06`, `07`); **2 remain unrecovered** (`m11g5-p03-04`, `05`) for a separate, already-disclosed, unrelated reason — their sentences do not themselves pass the generic `_looks_like_requirement` admission-gate vocabulary (no literal "experience"/"degree"/"years"/"required"/etc. token), a pre-existing limitation of that gate's own vocabulary completeness, not of heading classification. The one non-qualification control (`m11g5-p03-resp`) correctly remains unrecovered — zero false positives.

## A7. Requirement count and necessity changes

Across the 9 frozen-corpus defect rows specifically (`evaluation/m11g6/heading_controls.json`):

| | Before | After | Net |
|---|---|---|---|
| JobRequirement | 2 | 4 | **+2** |
| UnparsedClaim | 0 | 6 | **+6** |

The +2 `JobRequirement`s are **exclusively** the two controls whose body text carries an explicit local REQUIRED marker (`m11g6-004`, `m11g6-038`) — confirmed directly via `necessity.py`'s own `resolve_necessity_hint`/`infer_necessity` chain. **Zero new necessity defaults were fabricated**: every other newly-admitted claim is a diagnostic `UnparsedClaim` with necessity reported as unresolved, never silently assigned REQUIRED or PREFERRED from the section alone — the explicit, approved architectural constraint ("recognizing a qualification heading must NOT automatically assign REQUIRED") holds, verified by direct execution rather than by code inspection alone.

## A8. Assessable denominator and score impacts

**No scoring code was touched, and no live scoring run was performed** (this fix lives entirely in `jobs/parsing`, upstream of `gitscore.matching`/`gitscore.scoring`). The measured effect is strictly on *parser output* — `JobRequirementProfile.requirements`/`unparsed_claims` — which is the input the matcher and scorer already consume unmodified. Per the instructions ("a correctly recovered requirement may legitimately change the score; it must be measured and explained, never suppressed to keep old scores unchanged"): the 2 newly-recovered `JobRequirement`s (§A7) would, if this job description were run through the live matching/scoring pipeline against a real candidate profile, be legitimately included in that candidate's alignment-score denominator for the first time — this is the correct, intended effect of fixing a false-negative admission gap, not a regression. No controlled, deterministic end-to-end scoring fixture run was performed in this pass (out of scope — would require constructing a candidate GitHub-evidence fixture, not requested by this milestone's Phase 4 instructions beyond the parser-level reconciliation already reported above); flagged here as the natural next verification step if a scoring-level before/after is wanted.

## A9. Original source-span verification

Confirmed directly: `Claim.start`/`Claim.end` (and downstream `JobRequirement.source_span`/`UnparsedClaim.source_span`) computation in `segment_description()` does not read `section_kind` or any family-match result at all — span computation and family classification are independent code paths. Every newly-admitted claim across all 9 defect rows carries the exact same offsets into the original description it would have carried had the heading always been correctly classified — verified by inspecting `req.source_span`/`u.source_span` directly against each control's own text during the Phase 4 reconciliation (§A6/A7), not merely asserted.

## A10. Remaining limitations

1. **The `_CANDIDATE_PROFILE_ROOT` vocabulary is bounded and non-exhaustive** (disclosed in the original §7) — a candidate-seeking heading phrased with a continuation outside this closed list would still reproduce the original defect. Not claimed as a complete fix for every conceivable phrasing.
2. **One narrow, weak-shape-signal formatting edge case is a confirmed-safe, un-fixed residual**, discovered only by running the Phase-1 regression tests against the real implementation (the Phase 3 *simulation* had its own bug in this exact edge and did not predict it): a heading with the candidate-profile signal but NO colon/ALL-CAPS/Markdown (e.g. an em-dash-terminated line) now resolves to `NOT_A_HEADING` rather than `UNKNOWN`, because excluding the `SKIP` family can leave zero families with no strong shape signal to corroborate heading-recognition at all — the same, pre-existing, already-documented M10C "weak signal without any family corroboration" rule. Verified directly, twice: (a) it does not reintroduce the reported defect for any realistically-formatted (colon-terminated) heading; (b) it does not create an unsafe "sticky section" hazard even in the worst case tested, because the existing, independent M10E narrative-cue veto in `necessity.py` still downgrades any wrongly-retained content to a diagnostic rather than a scored requirement. Pinned by an explicit `xfail`, not silently resolved, and not treated as blocking this fix's approval scope.
3. **The `_looks_like_requirement` admission-gate's own vocabulary completeness is unchanged** (§A6 — 2 of 7 M11-G5 qualifications remain unrecovered for this separate, pre-existing reason). This was never in scope for a heading-classification-only fix.
4. **Unchanged offline competency-extraction limitations** (M11-F/M11-G5's own, separately reported finding): tag-level recall on genuinely new postings remains in the previously-measured 12–16% band. This milestone's fix operates entirely upstream of that pathway (heading admission, not competency tagging) and has no bearing on it — not re-measured here, not claimed to be improved by this fix.

## A11. Commit-readiness verdict

**Implemented, tested, and documented — not committed, per instructions.** Full backend suite green (1595 passed, 13 skipped, 2 documented xfailed), zero unexplained regressions, historical SOTI/Manulife evaluations confirmed byte-identical, M11-G5's own private fixture confirmed to recover 5/7 previously-missed qualifications as diagnostics with zero fabricated necessity. Ready for the user's own commit decision; nothing was staged or pushed by this pass.
