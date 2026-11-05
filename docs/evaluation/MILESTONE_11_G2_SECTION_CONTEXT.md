# Milestone 11-G2 — Section-Aware Qualification and Necessity Inference

**Status:** Implemented and evaluated. **Not committed, not pushed.** STOP point reached per milestone instructions.

**Scope discipline:** Only `src/gitscore/jobs/parsing/competency_extraction.py` was modified (+81/−3 lines; the 3 deletions are the import line, the function-signature line, and the single `necessity = infer_necessity(text, None)` line, each replaced in place — not a rewrite). `extract_competency_qualifications` (v1) has zero lines changed and zero new parameters (confirmed by a dedicated test inspecting its signature). The live parser, matcher, scoring formula, API, frontend, public schema, `Qualification`/`NormalizedReference` contracts, competency tag list, and alias table are all unchanged. No LLM. No new evidence detectors.

## 0. Verified baseline

HEAD at start: `299d229fd53e97684e04a766829d0bf1f9403aff`, branch `main`, full suite **1439 passed, 13 skipped**, status clean except the preserved untracked set (five M11-generalization files; M11-D's two private files; M11-F's three private files). All preserved throughout, confirmed again at the end.

## 1. Root-cause analysis

Traced through the requested modules:

- **`segmentation.py`** already computes exactly the section-context signal this milestone needs: `Claim.section_kind` (`"REQUIRED"`/`"PREFERRED"`/`"RESPONSIBILITY"`/`"LEARNING"`/`"UNKNOWN"`/`None`), deterministically, from the live parser's own heading classifier. `document_has_any_recognized_heading()` distinguishes "no headings anywhere" from "no section recognized *yet*, but the document has real structure later."
- **`necessity.py`** already has a complete, already-tested, already-reviewed policy function for USING that signal: `resolve_necessity_hint()` (Milestone 10E) — local REQUIRED/PREFERRED marker always wins; a genuine REQUIRED/PREFERRED section, or a genuinely unsectioned whole document, keeps its default; everything else (RESPONSIBILITY/LEARNING/UNKNOWN, or a preamble claim before the document's own later real sections) is downgraded to unresolved; plus an independent narrative-cue veto for content that slips through section-eligibility.
- **`parser.py`** already calls this exact function, for the live parser's own non-competency requirement pathway.
- **`competency_extraction.py`** (the offline, unwired module this milestone is scoped to) does none of this: `extract_competency_qualifications_v2()` hardcodes `infer_necessity(text, None)` — the hint is always `None`, regardless of what section a claim actually came from. This is precisely the gap M11-F's Phase 5 measured (`necessity: 0/0` on the independent holdout — every genuinely-matched control had `necessity=None`, confirmed by direct trace, because real "Requirements:" bullets rarely repeat "is required" per sentence).
- **`Qualification` model / `project_qualification()`**: `necessity: Necessity | None` already treats `None` as a first-class, legitimate state — `project_qualification()`'s own existing `necessity_unknown` safety rule already routes it conservatively to `UnparsedClaim`, never silently scored. No schema change needed to express "necessity unresolved."

**Conclusion:** existing parser section context (`Claim.section_kind` + `resolve_necessity_hint`) can be reused safely from an independent offline pathway — it is a pure function with no side effects, already decoupled from the live parser's own control flow. The live parser is not rerouted: this milestone adds a NEW caller of already-existing functions, not a new route for the live parser's own `_requirements_from_claim`.

**The three-way decision split:** (A) is-this-a-qualification and (B) necessity turned out NOT to need separate new mechanisms. A `Qualification` with `necessity=None` is already a normal, legitimate, constructible output (true today for the large majority of real-posting bullets with no explicit local marker) — mirroring the live parser's own precedent exactly: a `Claim` with no resolvable necessity still becomes a `JobRequirement` candidate with `necessity=None`-equivalent handling, falling through to `UnparsedClaim`, never simply discarded. Reusing this precedent meant no new decline reason, no new qualification-rejection gate, and no new field was needed — only necessity (B) needed section-awareness; (A) already behaves correctly once (B) is fixed, since a responsibility-sourced claim with no local marker now correctly resolves to `necessity=None` rather than either a false default or a fabricated rejection. (C), GitHub-assessability, was not touched.

## 2. Frozen control inventory (Phase 2)

49 self-authored, synthetic assertions in `evaluation/m11g2/section_context_controls.json`: 36 `direct_controls` (hand-specified `section_kind`/`document_has_recognized_heading` pairs, exercising the new logic in isolation) + 10 `mini_posting_controls` carrying 13 target assertions (genuine multi-line mini-postings run through the REAL, unmodified `segment_description()`, confirming end-to-end plumbing). All 10 mini-posting predictions were verified directly against the real segmenter and matched exactly before freezing. Hash-frozen in `evaluation/m11g2/controls_hash_freeze.json`.

Four corpus-authoring mistakes were found and fixed during baseline establishment (disclosed in the freeze file), consistent with this project's established discipline:
- Three controls (`m11g2-d10`, `m11g2-d11`, `m11g2-m03`) originally used "systems architecture"/"systems design" phrasing that accidentally triggers the SAME pre-existing, already-disclosed M11-E stemming-overlap artifact (text-side stemming turns "systems"→"system," so "embedded systems design" also matches the bare `system-design` canonical phrase) — unrelated to what this milestone tests. Reworded to avoid it.
- One control (`m11g2-d25`) used phrasing ("...systems experience for...") that does not satisfy the existing, unmodified `_QUALIFYING_INTENT_V2` gate at all. Reworded to "...experience with distributed systems for...".

All four are corpus-authoring fixes, not extraction defects, made and re-verified **before** any production code was touched.

## 3. Compared approaches (Phase 3)

Implemented and measured as standalone prototypes (`scripts/evaluation_lib/m11g2_section_strategy_prototypes.py`), before touching production code:

- **Option A — reuse:** calls the REAL `resolve_necessity_hint()` directly, fed a default hint derived from the REAL `_SectionKind`/`_SECTION_NECESSITY_HINT` constants (`segmentation.py`). Zero new classification logic.
- **Option B — dedicated, independent offline structural propagation:** a parallel, hand-rolled section/necessity mapping authored fresh, deliberately NOT importing `segmentation.py`'s own constants.
- **Option C — hybrid** (section intent + local language cues + conservative conflict handling): Option A's own three-step design (local marker wins → section-origin eligibility → narrative veto) is *already* exactly this hybrid — implemented as a thin wrapper around Option A to make the convergence an explicit, measured finding rather than an assumption.

**Measured on the frozen corpus's 33 necessity-relevant direct controls:** all three score **33/33** — not distinguishable on recall alone, consistent with the instruction not to choose on recall. The deciding factor, found by probing outside the frozen set: Option B's independently-authored local-marker regex is already *less complete* than the production one it duplicates — confirmed directly:

```
"Concurrency experience would be nice."  (unsectioned document)
  Option A: PREFERRED   (production _PREFERRED_MARKER includes "would be nice")
  Option B: REQUIRED    (hand-rolled regex omits it -> falls through to the unsectioned default)
```

This is exactly the drift risk reuse avoids: a second, independently-maintained classifier silently diverges from the first as either evolves. **Option A/C selected** on architectural grounds (reuse of already-tested machinery, zero duplicated maintenance surface, demonstrated lower regression risk) — not recall, which tied.

## 4. Selected implementation (Phase 4)

`extract_competency_qualifications_v2()` gained three new **keyword-only, defaulted** parameters: `section_kind: str | None = None`, `document_has_recognized_heading: bool = False`, `has_section_context: bool = False`. When `has_section_context` is `False` (the default — every pre-existing call site), necessity resolution is the exact pre-M11-G2 expression (`infer_necessity(text, None)`), unconditionally. When `True`, a new helper `_claim_necessity_hint_for_section_v2()` mirrors `Claim.necessity_hint`'s own computation (reusing the real `_SectionKind`/`_SECTION_NECESSITY_HINT`, never re-deriving it independently), and the result feeds the REAL `resolve_necessity_hint()` before the existing, unchanged `infer_necessity()` runs — the identical two-step call pattern `parser.py::_requirements_from_claim` already uses for its own non-competency pathway.

Every Phase 4 requirement is satisfied:
- Section context propagates without losing source provenance (`span`/`source_text` on the produced `Qualification` are completely unaffected — the change touches only the `necessity` field's value).
- Explicit local wording overrides section hints via `resolve_necessity_hint`'s own already-tested, unmodified precedence — confirmed in both directions (PREFERRED-marker-in-REQUIRED-section and REQUIRED-marker-in-PREFERRED-section).
- REQUIRED is never assigned merely because a heading seems qualification-related: a RESPONSIBILITY/LEARNING/UNKNOWN section with no local marker resolves to `necessity=None` (UNKNOWN), never a default.
- Genuine qualifications under unconventional (UNKNOWN) headings are preserved via the local-marker-always-wins rule.
- Responsibility/narrative claims are not promoted to a scored requirement absent explicit independent qualification intent (an explicit local REQUIRED/PREFERRED marker) — mirroring the live parser's own already-reviewed precedent exactly, via `necessity=None` → `project_qualification()`'s existing `necessity_unknown` → `UnparsedClaim`, never fabricated.
- M11-G1's OR-list safety fix is completely unaffected — that check runs and returns before necessity is ever computed, under any `has_section_context` value.
- No competency IDs are fabricated, no new tags, no GitHub-scoreability change (unrelated field, untouched).

No architectural blocker was hit: the only type extended was `DeclinedExtraction` (M11-G1, already done) — nothing further was needed here since `Qualification.necessity: Necessity | None` already fully supports the required "unresolved" state.

## 5. Before/after qualification-extraction results

| Run | G2 frozen corpus (49 assertions) |
|---|---|
| Before the fix (old code; section kwargs did not exist) | 28/49 |
| After the fix, `has_section_context=True` (new, opt-in behavior) | **49/49** |
| After the fix, `has_section_context=False` (legacy call path) | 28/49 — byte-identical to the before-fix row |

The third row is the direct confirmation of Phase 5 item 10 ("unchanged behavior for inputs without section context"): calling the fixed function exactly the way every pre-existing caller already does reproduces the pre-fix numbers exactly.

## 6. Necessity classification accuracy, full denominators

Of the 33 necessity-relevant `direct_controls` (excluding the 3 negation/OR-safety controls, whose outcome is identical regardless of necessity):

| | Before | After (section-aware) |
|---|---|---|
| Correct necessity resolution | 12/33 (only explicit-local-marker cases ever resolved correctly) | **33/33** |
| UNKNOWN correctly assigned (RESPONSIBILITY/LEARNING/UNKNOWN/preamble, no local marker) | 0/11 (all incorrectly `None` for the WRONG reason — no hint existed at all, not a deliberate UNKNOWN decision) | **11/11** |
| REQUIRED correctly assigned from section default | 0/9 | **9/9** |
| PREFERRED correctly assigned from section default | 0/5 | **5/5** |

## 7. False-positive and false-negative analysis

- **False REQUIRED assignments: 0.** No control that should resolve to PREFERRED or UNKNOWN resolves to REQUIRED after the fix (verified across all 49 assertions).
- **False PREFERRED assignments: 0.**
- **False qualification creation: 0.** Section context never causes a `Qualification` to be constructed for text that would otherwise correctly decline (negation/narrative/responsibility-lead/no-vocabulary/OR-unsafe) — all of those checks run, unaffected, before necessity is ever touched; confirmed by `m11g2-d27` (negation), `m11g2-m09`'s education bullet (no_competency_language), and the full G1 regression (§ below).
- **Genuine qualification suppression: 0.** Every control with a genuine tag match and an explicit local marker still produces a correctly-tagged, correctly-necessitied `Qualification`, under every section kind tested including UNKNOWN/LEARNING (`m11g2-d09`, `m11g2-d17`, `m11g2-d23`, `m11g2-d26`).

## 8. Source-span and logical-grouping verification

Every produced `Qualification`'s `source_text`/`source_span` is unaffected by this change (the modification touches only the `necessity` field) — confirmed directly for the soft-line-wrap mini-posting (`m11g2-m06`: the Claim's exact embedded-newline span is preserved and still resolves correctly). `LogicalComposition` (`SINGLE`/`AND`/`MIXED_UNSUPPORTED`) is computed entirely independently of necessity and is unaffected; M11-G1's OR-list `missing_contract` safety check runs and returns before necessity is ever computed under any section-context value, confirmed by `m11g2-d30`/`d31`/`d32` and a dedicated regression test re-running the real G1 control corpus (§10).

## 9. Historical regression outcomes (Phase 6)

- New M11-G2 tests: **19/19 passed** (`tests/test_m11g2_section_context.py`).
- Full backend suite: **1458 passed, 13 skipped** (1439 baseline + 19 new).
- M11-G1 safety controls (`evaluate_m11g1_alternative_requirements.py`): unchanged — v2 **32/32**, v1 **21/32** (v1 untouched).
- M11-E Phase 5 harness (`evaluate_m11e_v2_extractor.py`): byte-identical — necessity 66/66, logical grouping 69/69, span 69/69, 1 pre-existing unrelated mismatch, v1 numbers (27/27, 29/29, 29/29, 39 mismatches) also unchanged. (M11-E's own harness calls the extractor with no section kwargs at all, so it exercises exactly the legacy path.)
- M11-C harness (`evaluate_m11c_competency_extraction.py`): unchanged — necessity 21/28, logical grouping 27/28, Option C 28/28 precision/recall, deterministic.
- M11-F independent holdout, used strictly as an already-inspected diagnostic benchmark (its own harness also calls with no section kwargs, exercising the legacy path): byte-identical to the post-G1 numbers (v2 qualification precision 11/11, tag precision/recall 12/12, 12/74). Its committed historical report was regenerated locally to confirm this, then **restored via `git checkout`** — the committed artifact itself was never rewritten.
- M11-B/M11-A1/A2/M10A–E/M9B/8c:v1/v1.1: all covered by, and passing within, the full 1458-test backend suite.
- Live parser confirmed still v10 (unimported-module test still passing).
- `git diff --stat -- src/` shows exactly one file, +81/−3 — no API/matcher/scoring/schema change anywhere; the matcher/scoring/API/frontend/evidence/concepts/live-parser/`segmentation.py`/`necessity.py`/`narrative.py` paths show zero diff (only NEW callers were added from the offline module, no existing file in that list was edited).
- Private M11-D and M11-F source/annotation/builder files, and the five pre-existing M11-generalization files, remain untracked and untouched.

## 10. Remaining limitations

- **Section-context must be supplied by the caller.** This module still does not call `segment_description()` itself — a caller must run the real parser's segmentation separately and pass `Claim.section_kind`/`document_has_recognized_heading` through explicitly. This is deliberate (the mission's own "do not reroute the live parser" instruction), but it means the offline pathway's improved accuracy is only realized by a caller that does this wiring — not yet exercised by any evaluation harness operating on bare, context-free sentences (M11-E's and M11-F's own harnesses, by construction, still call the legacy path).
- **No new representation for a genuine alternative GROUP, and no change to GitHub-assessability** — both explicitly out of scope, unchanged from M11-G1 and M11-C respectively.
- **The three Phase-3 "independent" strategies converge** (A and C are literally the same implementation) — a genuinely different, non-reuse-based design was not explored beyond the one hand-rolled Option B prototype, which was built specifically to probe the reuse-vs-duplicate tradeoff, not as a fully competitive alternative.
- **Narrative/responsibility detection for claims that pass the qualifying-intent gate but don't start with a bare imperative verb** (e.g. "Strong ownership of X" under a Responsibilities heading) is now handled correctly via necessity=UNKNOWN rather than outright rejection — a deliberate, disclosed interpretation of "reject as a qualification" (§1), not a literal DeclinedExtraction. A reviewer preferring the stricter literal reading would need a separate, explicitly-scoped follow-up.

## 11. Commit-readiness verdict

The fix, its tests, the frozen control corpus, and this document are internally consistent, fully regression-clean, and narrowly scoped exactly as instructed. **Not committed and not pushed**, per explicit milestone instruction — awaiting separate authorization. M11-G3 has not been started. No live-GitScore integration was made.
