# Milestone 11-G4 — Qualification Admission Consistency

**Status:** Implemented and evaluated. **Not committed, not pushed.** STOP point reached per milestone instructions.

**Scope discipline:** Exactly one new production file (`src/gitscore/jobs/parsing/qualification_admission_recovery.py`), purely additive. `git diff --stat -- src/gitscore/jobs/parsing/segmentation.py` is **empty** — segmentation.py was never touched, confirmed directly (and by a dedicated regression-guard test that fails loudly if it ever is). No other existing file under `src/` was modified.

## 0. Verified baseline

HEAD at start: `4b4e3b911651d434b51af464642b96f8a7b1438b`, branch `main`, full suite **1470 passed, 13 skipped**, status clean except the preserved untracked set. All preserved throughout, confirmed again at the end.

## 1. Root cause (Phase 1)

Traced exactly as M11-G3 §10 already found and disclosed: `segmentation.py`'s own `_looks_like_requirement()` is consulted only for content where `current_kind` is NOT `REQUIRED`/`PREFERRED`/`RESPONSIBILITY` (`in_recognized_section` is `False`) — i.e. a genuinely unsectioned document, a preamble before the document's own later real headings, or content under an `UNKNOWN`/`LEARNING` heading. Its vocabulary (`experience|proficien*|knowledge of|familiar*|degree|years?|required|preferred|plus|responsib*|skills?|certificat*|licensed?|eligible|authoriz*|mentor*`) is a **strict subset** of `competency_extraction.py`'s own, already-approved `_QUALIFYING_INTENT_V2` gate — missing specifically the bare cue words `strong`/`solid`/`deep`/`comfortable` and the leading qualifiers `understanding`/`background`/`expertise`/`grounding`/`grasp`. A sentence like "Strong understanding of distributed systems." never becomes a `Claim` at all outside a recognized section, even though the extractor would recognize it.

**Confirmed: the issue occurs ONLY outside recognized sections.** Inside a `REQUIRED`/`PREFERRED`/`RESPONSIBILITY` section, `in_recognized_section` bypasses `_looks_like_requirement` entirely — every line already becomes a `Claim` unconditionally, so nothing is lost there.

**Minimum interface correction identified:** an additional, offline-only admission pass that, for exactly this gap region, also checks `_QUALIFYING_INTENT_V2` (the real, already-approved gate) before giving up on a line.

## 2. Frozen controls (Phase 2)

42 self-authored controls across 22 postings, `evaluation/m11g4/admission_recovery_controls.json`, hash-frozen in `evaluation/m11g4/controls_hash_freeze.json`. A preliminary freeze recorded independent predictions before implementation; a pre-freeze verification pass against the real, implemented pipeline found 5 mismatches (disclosed in the freeze file) — all my own prediction errors (two sentences already matched segmentation's vocabulary without my noticing; two preamble lines were wrongly predicted as "genuinely unsectioned" when their own posting has a later heading, making them ineligible for the default necessity; one single-line posting needed a real heading added elsewhere to actually test preamble-ineligibility as intended) — none required changing the new module's own logic. **Zero mismatches** at the final freeze.

## 3. Strategy comparison (Phase 3)

- **Option A — widen segmentation.py's own vocabulary.** Would close the gap for both the live parser and the offline pathway in one place, but requires modifying a heavily-covered production file. Per this milestone's own explicit restriction, this would require a STOP-and-present before touching it — not attempted.
- **Option B — an offline-only recovery pass.** Selected. A new function reuses every one of `segmentation.py`'s own private helpers via import (`_SectionKind`, `_SECTION_NECESSITY_HINT`, `_BULLET_PREFIX`, `_classify_heading_line`, `_looks_like_requirement`, `_ends_incomplete`, `_is_paragraph_gap`, `_line_content_span`, `_split_sentences`) — **zero duplicated regex or admission logic**, only the per-line orchestration shape is mirrored (the same lesson M11-G2's own Phase 3 comparison already established: reuse beats duplication).
- **Option C — a shared, context-aware admission policy both parsers could eventually adopt.** The new function's one substitution (`_looks_like_requirement(text) or _QUALIFYING_INTENT_V2.search(text)`, restricted to the exact gap region) is written as a clean, self-contained predicate — it could be adopted by `segmentation.py` directly in a future milestone with minimal rework. Not wired in now; the live parser remains completely unmodified.

**Measured, not assumed:** running the new recovery function against M11-G3's own, unmodified 81-control corpus produces exactly **one** newly-recovered claim — the exact sentence M11-G3 itself flagged as the disclosed gap (`p19`, "Strong understanding of concurrency.") — and **zero** unintended additional recoveries across the other 80 controls. This is the precision confirmation the comparison needed: the fix is exactly as narrow as intended.

## 4. Selected implementation (Phase 4)

`recover_unadmitted_qualification_claims(description) -> tuple[RecoveredClaim, ...]` mirrors `segment_description()`'s own per-line loop exactly, but:
- Never recovers content inside a recognized section (`in_recognized_section` → skip entirely; `segment_description()` already admits it).
- Never recovers content under a `SKIP` section (mirrors `segment_description()`'s own unconditional suppression there — confirmed by a dedicated test).
- Never recovers a line `_looks_like_requirement` would already admit (avoiding duplication by construction, not by a post-hoc dedup step).
- Recovers a line only when the real `_QUALIFYING_INTENT_V2` gate passes.
- Computes `necessity_hint`/`section_kind` using the exact same formulas `segment_description()` itself uses (reused via import, not re-derived).
- Returns real `Claim` objects in the exact shape `segment_description()` produces, so every downstream, unmodified safety check (negation, narrative, responsibility-lead, M11-G1's OR-list safety, M11-G2's section-aware necessity, `project_qualification`'s conservative rules) applies unchanged.

No change to `segmentation.py`, no change to public schemas, no change to the technology concept registry. No STOP was triggered.

## 5. Before/after measured results (Phase 5)

From `scripts/evaluate_m11g4_admission_recovery.py` against the frozen 42-control corpus (raw counts, exact denominators):

| Metric | TP | FP | FN | Precision | Recall |
|---|---|---|---|---|---|
| Applicant-qualification identification (A) | 26 | — | 0 | 26/26 | 26/26 |
| Admission (did the right line become a claim, admitted or recovered) | 41 | 0 | 0 | 41/41 | 41/41 |
| Technical-competency tag prediction (per-prediction) | 31 | 0 | 0 | 31/31 | 31/31 |

- Necessity accuracy: **31/31**.
- Unsupported logical-structure handling: **31/31** (including a genuine 3-tag AND-split and a genuine AND-of-OR `MIXED_UNSUPPORTED` case, both recovered).
- Exact source-span correctness: **31/31**.
- Safe projection behavior: **31/31**.
- Previously-correct (already-admitted) behavior preserved: **14/14**.
- False narrative/responsibility admissions (a B/C/D claim receiving a confident, non-`None` necessity after recovery): **0**.
- Duplicate qualification count (a claim both admitted and recovered): **0**.
- Total recovered claims across the frozen corpus: **27**.

**M11-G3's own 81-control corpus, used strictly as development/regression material (never independent generalization evidence):** re-running it through the combined (admitted + recovered) pathway produces exactly **1** newly-recovered claim — the one M11-G3 itself disclosed — confirmed to now resolve correctly (`concurrency`, `REQUIRED`, `job_requirement`, matching the control's own sibling line "Experience with concurrency." on the same unsectioned document). Every other one of the 80 G3 controls is untouched.

## 6. New false positives or lost qualifications (Phase 5 items 4-5, 10)

**Zero.** No new false positive was introduced on any of the 42 frozen controls or the 81 G3 regression controls. No previously-correct admission was lost — `previously_correct_behavior_preserved` is 14/14, and the "never recovers content inside a recognized section" / "never duplicates an already-admitted claim" properties are each enforced structurally (by the loop's own early-skip conditions), not merely tested as an emergent property, and are each covered by a dedicated unit test.

## 7. Historical regression results (Phase 6)

- New M11-G4 tests: **15/15 passed** (`tests/test_m11g4_admission_recovery.py`), including a dedicated guard that fails if `segmentation.py` is ever found modified.
- Full backend suite: **1485 passed, 13 skipped** (1470 baseline + 15 new).
- M11-G3 end-to-end harness (unmodified, does not call the new recovery function): byte-identical — 57/57, 65/65, 66/66.
- M11-G2 section-context controls: unchanged — opt-in 49/49, legacy path 28/49.
- M11-G1 alternative-requirement safety controls: unchanged — v2 32/32, v1 21/32.
- M11-E Phase 5 harness: byte-identical — necessity 66/66, logical grouping 69/69, span 69/69.
- M11-C harness: byte-identical.
- M11-B/M11-A1/A2/M10A–E/M9B/8c:v1/v1.1: all covered by, and passing within, the full 1485-test backend suite.
- Live parser confirmed still v10; `segmentation.py` confirmed byte-unchanged; frozen historical gold (`evaluation/m11c`, `m11d`, `m11e`, `m11f`, `m11g1`, `m11g2`, `m11g3`, `8c`) shows zero diff.

## 8. Remaining limitations

- The recovery pass duplicates `segment_description()`'s own per-line **orchestration shape** (though none of its regex/classification/joining **logic**, all reused via import) — a future Option-C-style unification (folding this widened check directly into `segmentation.py`) would remove even that, at the cost of touching a production file this milestone was explicitly restricted from modifying.
- Recovery only widens the **admission** vocabulary; it does not add any new qualifying-intent cue beyond what `_QUALIFYING_INTENT_V2` already recognizes. Any future gap in THAT gate's own vocabulary (not discovered here) would still be missed.
- This pathway remains entirely offline — nothing calls `recover_unadmitted_qualification_claims()` except the new evaluation harness and tests. Realizing its benefit in any live or batch pipeline would require a separate, explicitly-scoped wiring decision, not made here.

## 9. Commit-readiness verdict

The fix, its tests, the frozen 42-control corpus, and this document are internally consistent and fully regression-clean. `segmentation.py` is confirmed untouched; the live parser is confirmed unaffected. **Not committed and not pushed**, per explicit milestone instruction — awaiting separate authorization. M11-G5 has not been started. No live-GitScore integration was made.
