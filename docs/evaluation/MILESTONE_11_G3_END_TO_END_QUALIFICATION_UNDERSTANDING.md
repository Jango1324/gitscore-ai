# Milestone 11-G3 — Offline End-to-End Qualification Understanding

**Status:** Implemented and evaluated. **Not committed, not pushed.** STOP point reached per milestone instructions.

**Scope discipline:** `git diff --stat -- src/` is **empty** — this milestone touched zero production code. Every artifact is a new, additive evaluation script, test file, or frozen corpus under `scripts/`, `tests/`, and `evaluation/m11g3/`. The live parser's own pathway (`parse_job_description()`/`_parse()`/`_requirements_from_claim`) is never called, imported, or modified by anything here — confirmed by a dedicated test inspecting `parser.py`'s own source for any reference to `extract_competency_qualifications`/`project_qualification`.

## 1. Verified baseline

HEAD at start: `da32c497f6d91fd426f4965b78b9a833feccde0e`, branch `main`, full suite **1458 passed, 13 skipped**, status clean except the preserved untracked set (five M11-generalization files; M11-D's two private files; M11-F's three private files). All preserved throughout, confirmed again at the end.

## 2. Full pipeline architecture

A new, standalone offline runner pattern (used directly by the Phase 5 harness and the new test file — no new production module was created, since the chain is short enough to express inline against already-existing functions):

```
raw description
  -> segment_description(description)                         [segmentation.py, unmodified]
  -> document_has_any_recognized_heading(description)          [segmentation.py, unmodified]
  -> for each Claim:
       extract_competency_qualifications_v2(
           claim.text, SourceSpan(claim.start, claim.end),
           section_kind=claim.section_kind,
           document_has_recognized_heading=<doc-level flag>,
           has_section_context=True,
       )                                                        [competency_extraction.py, M11-G1+G2, unmodified]
     -> DeclinedExtraction | tuple[Qualification, ...]
  -> for each Qualification:
       project_qualification(q)                                [qualification.py, unmodified]
     -> ProjectionResult(job_requirement | unparsed_claim, unsafe_reason)
```

Every function in this chain already existed and was already independently tested before this milestone (`segment_description`/`document_has_any_recognized_heading`: M10A–M10E/M11-A2; `extract_competency_qualifications_v2` with section context: M11-G1/M11-G2; `project_qualification`: M11-B Stage 1). This milestone's own contribution is exclusively the **composition** — confirming these pieces, each already correct in isolation, remain correct when chained together on complete, multi-section postings — and the **evaluation harness** that measures this composition.

## 3. Frozen evaluation inventory (Phase 2)

28 self-authored mini-postings, **81** independently-annotated controls, in `evaluation/m11g3/full_posting_controls.json`, hash-frozen in `evaluation/m11g3/controls_hash_freeze.json`. No sentence is copied, paraphrased, or reconstructed from M11-D's or M11-F's own private real-posting corpora — every sentence is either already self-authored and publicly committed in M11-G1/M11-G2's own corpora/tests, or freshly built using only the 17-tag canonical/alias **vocabulary** already present in production source code (never posting text).

Category distribution (ground-truth qualification-intent, Phase 3's A–F): A=60 (56 competency-relevant + 4 deliberately out-of-scope: named technology/education/years-of-experience), B=9, C=4, D=3, E=2, F=3 (negation ×1, OR-list-safety ×1, a deliberately-kept integration-gap demonstration ×1).

**Pre-freeze verification discipline:** a separate script (`evaluate_m11g3_pre_freeze_check.py`) ran the corpus against the real, unmodified pipeline iteratively; 16 initial mismatches were found and fixed — all disclosed in the freeze file, all either (a) a sentence that failed to exercise the mechanism it was meant to test (reworded), or (b) a wrong assumption about already-existing, unmodified code (corrected), or (c) a genuinely discovered system behavior (kept, explicitly flagged, never hidden — see §9/§10). A later coverage gap (no named-technology/education controls) was found and closed with posting `p28` before the final freeze. **Zero mismatches** at the frozen hash.

M11-F's own corpus was used only as an already-inspected diagnostic benchmark (its legacy call path re-confirmed byte-identical, §8) — never as fresh evidence, and its committed report was never rewritten.

## 4. End-to-end precision/recall

All counts below are from `scripts/evaluate_m11g3_end_to_end.py` against the frozen 81-control corpus.

| Metric | TP | FP | FN | Precision | Recall |
|---|---|---|---|---|---|
| Applicant-qualification identification (A, competency-relevant) | 57 | 0 | 0 | 57/57 | 57/57 |
| Technical-competency tag prediction (per-prediction, M11-F Phase-1 methodology) | 65 | 0 | 0 | 65/65 | 65/65 |
| Out-of-competency-scope correctly declined (A, not competency-relevant) | 3/3 | — | — | — | — |

**This is an integration-correctness check against synthetic development controls, not a held-out generalization claim** — consistent with M11-F's own independent-holdout finding that recall collapses sharply on genuinely unseen real postings. No claim of universal generalization is made here.

## 5. Qualification-intent error analysis (Phase 3)

| Category | Total | Matched expectation | False qualifications (confident necessity on non-A) | Safe non-qualification construction (necessity=None) |
|---|---|---|---|---|
| A | 60 | 60 | — | — |
| B (responsibility) | 9 | 9 | 0 | 2 |
| C (learning) | 4 | 4 | 0 | 4 |
| D (narrative) | 3 | 3 | 0 | 0 |
| E (administrative) | 2 | 2 | 0 | 0 |
| F (uncertain/negation/OR-safety) | 3 | 3 | 0 | 0 |

**Zero false qualifications** — no B/C/D claim ever received a confident (non-`None`) necessity. **6 instances of "safe non-qualification construction"**: a `Qualification` object was still constructed for a B/C-labeled claim (because it genuinely contains qualifying-intent *vocabulary*), but always with `necessity=None`, routed via `project_qualification`'s own `necessity_unknown` rule to `UnparsedClaim` — never scored, never visible to the matcher. This is the G2-disclosed interpretation choice ("reject as a qualification" implemented as necessity=UNKNOWN, not a literal decline), now **measured directly on complete postings** rather than only asserted: 6 of 13 B/C claims took this path; the other 7 declined outright (`responsibility_lead`) because their own phrasing happened to also open with a bare imperative verb.

## 6. Necessity accuracy

**66/66** correct, with full breakdown: REQUIRED assigned correctly from an explicit local marker or from a REQUIRED-section default — 2 cases where the two combine to override a conflicting section default, confirmed; PREFERRED assigned correctly from a local marker or PREFERRED-section default; UNKNOWN (`None`) correctly assigned for every RESPONSIBILITY/LEARNING/UNKNOWN-section claim and every preamble claim lacking an explicit local marker — **UNKNOWN was never coerced to REQUIRED or PREFERRED** (verified directly, zero exceptions).

## 7. Logical grouping and provenance results

- Logical grouping: **66/66** correct (`SINGLE`/`AND`/`MIXED_UNSUPPORTED`, including a genuine 3-tag AND-split and the genuine AND-of-OR `MIXED_UNSUPPORTED` case).
- Source-span exactness: **66/66** — every produced `Qualification.source_text`/`source_span` exactly matches the real `Claim.text`/`(start, end)` `segment_description()` itself produced, including across the soft-line-wrap case (an embedded-newline span preserved exactly).
- M11-G1's OR-list safety: **intact end-to-end** — the one OR-list control (`p06`) declines `missing_contract` under real section context exactly as it does in isolation.

## 8. Projection and scoring safety (Phase 4)

- Conservative projection correctness: **66/66**.
- Unsupported qualifications are never silently discarded: every `necessity=None`, `MIXED_UNSUPPORTED`, and applicability-conditioned `Qualification` is still constructed and still routed to `UnparsedClaim` with a named `unsafe_reason` (`necessity_unknown` ×8, `mixed_unsupported_logical_structure` ×1, `material_applicability_condition_not_representable_on_job_requirement` ×1) — never a `JobRequirement`, never vaporized.
- UNKNOWN necessity is never coerced (§6).
- Applicability conditions are preserved on the `Qualification` itself even though `project_qualification`'s own **pre-existing, unmodified** rule always routes a conditioned claim to `UnparsedClaim` rather than `JobRequirement` — confirmed directly (this was itself a corpus-authoring correction during Phase 2, not a new finding about changed behavior).
- Technical competencies never automatically receive GitHub evidence credit: an isolated matcher check (mirroring M11-E's own harness pattern, not a new mechanism) ran every produced `JobRequirement` through `match_requirement()` against an **empty** candidate evidence profile — **57/57 checks**, zero `SUPPORTED`, zero falsely-`ASSESSABLE` non-technical requirement. `github_observability` is populated from the existing, unmodified `_COMPETENCY_OBSERVABILITY` table, untouched by this milestone.
- Existing live alignment scores/denominators: untouched — this pathway is never called by anything that feeds scoring (confirmed by the "not wired into the live parser" test, §1).

## 9. Historical regression results (Phase 7)

- New M11-G3 tests: **12/12 passed** (`tests/test_m11g3_end_to_end_pathway.py`).
- Full backend suite: **1470 passed, 13 skipped** (1458 baseline + 12 new).
- M11-G2 section-context controls: unchanged — opt-in 49/49, legacy path 28/49 (byte-identical).
- M11-G1 alternative-requirement safety controls: unchanged — v2 32/32, v1 21/32.
- M11-E Phase 5 harness: byte-identical — necessity 66/66, logical grouping 69/69, span 69/69.
- M11-C harness: byte-identical — necessity 21/28, logical grouping 27/28.
- M11-F independent holdout (legacy call path, diagnostic only): byte-identical to the post-G2 numbers; its committed report was regenerated locally for confirmation then `git checkout`-restored, never rewritten.
- M11-B/M11-A1/A2/M10A–E/M9B/8c:v1/v1.1: all covered by, and passing within, the full 1470-test backend suite.
- Live parser confirmed still v10 (unimported-module test still passing; `git diff --stat -- src/` empty).
- Frozen historical gold (`evaluation/m11c`, `m11d`, `m11e`, `m11f`, `m11g1`, `m11g2`, `8c`) shows zero diff.

## 10. Remaining blocking defects

**One genuine, systemic, material finding requiring a future, separately-scoped production change — reported, not silently fixed:**

`segmentation.py`'s own `_looks_like_requirement` admission-gate vocabulary (`experience|proficien|knowledge of|familiar|degree|years?|required|preferred|plus|responsib|skills?|certificat|licensed?|eligible|authoriz|mentor`, plus a registered-concept check) is **narrower** than `competency_extraction.py`'s own `_QUALIFYING_INTENT_V2` gate (which additionally recognizes bare `strong`/`solid`/`deep`/`comfortable`). For content **outside** a recognized REQUIRED/PREFERRED/RESPONSIBILITY section (i.e. under LEARNING/UNKNOWN, or in an unsectioned preamble/whole document), a sentence phrased as `"Strong understanding of X."` never becomes a `Claim` at all — it is filtered out by segmentation's own earlier, independent gate before the offline competency extractor (which WOULD recognize it) ever sees it. Confirmed directly (`test_disclosed_integration_gap_strong_phrasing_outside_a_section_never_reaches_extractor`), not assumed. This is exactly the "integration interface mismatch" category Phase 6 asked to prioritize — it is a real gap in the END-TO-END pathway even though both component gates are individually correct and already-tested on their own terms. **Fixing it would require changing `segmentation.py`'s own vocabulary (a production file this milestone's own restrictions explicitly forbid touching) — reported here rather than fixed, per the explicit STOP instruction for a material correctness defect outside this milestone's authorized scope.**

**One disclosed, lower-severity, pre-existing vocabulary-design finding (not an integration defect):** `"distributed architecture"` is simultaneously `system-design`'s own canonical phrase and a pre-existing `distributed-systems` `SEMANTICALLY_EQUIVALENT` alias (from M11-E's own alias table) — a cross-tag ambiguity that causes a single, non-compound sentence naming one concept to resolve to two sibling tags. Pre-existing (not introduced by G1/G2/G3), confirmed directly, left unfixed per this milestone's own "do not modify extraction algorithms" restriction.

**One disclosed, accepted interpretation choice (not a defect):** B/C-labeled claims carrying qualifying-intent vocabulary still construct a `Qualification` (necessity=`None`) rather than declining outright — by design (M11-G2), now measured at 6/13 occurrences on this corpus (§5).

## 11. Recommended next smallest implementation milestone

A narrowly-scoped fix widening `segmentation.py`'s own `_looks_like_requirement` vocabulary to include the bare `strong`/`solid`/`deep`/`comfortable` cues `_QUALIFYING_INTENT_V2` already recognizes (or, more conservatively, passing `_QUALIFYING_INTENT_V2` itself through as an additional admission signal for non-in_recognized_section content) — evaluated, as every prior milestone in this series has been, against a fresh, hash-frozen development corpus BEFORE any code change, with the existing M10A–M10E/M11-A2 segmentation regression suite re-run in full to confirm no unrelated admission-gate behavior shifts.

## 12. Commit-readiness verdict

The harness, its tests, the frozen 81-control corpus, and this document are internally consistent and fully regression-clean. **No production code was touched, so there is nothing to commit from a code-change standpoint** — the evaluation artifacts themselves (scripts, tests, corpus, this report) are ready to commit as evaluation material **once reviewed**, per instructions. **Not committed and not pushed.** M11-G4 has not been started. No live-GitScore integration was made.
