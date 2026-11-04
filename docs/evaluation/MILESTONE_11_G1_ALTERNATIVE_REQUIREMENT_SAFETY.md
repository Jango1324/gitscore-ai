# Milestone 11-G1 — Safe Interpretation of Alternative Requirements

**Status:** Fix implemented and evaluated. **Not committed, not pushed.** STOP point reached per milestone instructions.

**Scope discipline:** Only `src/gitscore/jobs/parsing/competency_extraction.py` was modified — purely additively (+138/-0 lines; `git diff --stat` confirms zero deletions). `extract_competency_qualifications` (v1) is untouched at the function-body level. The live parser, matcher, scoring formula, API, frontend, public schema, competency tag list, and alias table are all unchanged. No LLM. No new competency tags. No new aliases.

## 0. Verified baseline

HEAD at start: `cb0d37b351077dee45e3e7e6973d9dd66b5dfef0`, branch `main`, full suite **1413 passed, 13 skipped**, status clean except the preserved untracked set (five M11-generalization files; M11-D's two private files; M11-F's three private files — `source/`, `holdout_annotations.json`, `m11f_build_gold.py`). All preserved throughout this milestone, confirmed again at the end.

## 1. Root-cause analysis

Both `extract_competency_qualifications` (v1) and `extract_competency_qualifications_v2` (v2) compute `has_or`/`has_and` flags and only ever **consult** them inside the `len(tags) > 1` branch — the branch that runs when the whole-sentence vocabulary match already found two or more *different* competency tags. The `len(tags) == 1` branch, evaluated first, returns a fully-confident single-tag `Qualification` unconditionally, without ever checking `has_or` at all.

Consequence: when an OR-list names several alternatives but only **one** of them happens to match a known competency tag, `find_competency_mentions`/`_v2` returns a tag set of size 1, the function takes the `len(tags) == 1` fast path, and the sentence's true "any ONE of N options" semantics is silently collapsed into "this ONE specific competency is confidently required" — discarding every other named alternative and misrepresenting the full requirement.

Confirmed directly against the real M11-F diagnostic case (`m11f-array-02`, a 7-alternative OR-list where only "Operating Systems" matches a known tag):

```
v2 (before fix): Qualification(..., logical_composition=SINGLE, normalized_reference=NormalizedReference(competency_tag='os-networking'))
v1 (unchanged):  Qualification(..., logical_composition=SINGLE, normalized_reference=NormalizedReference(competency_tag='os-networking'))
```

**The defect affects v1 and v2 identically** — both took the exact same `len(tags) == 1` fast path and produced the same overclaim. This milestone fixes **v2 only**, per explicit scope; v1's own call to the fast path is left byte-unchanged.

Trace through the six stages requested:
- **Source segmentation:** not applicable here — this module consumes an already-segmented claim; no change.
- **Logical OR detection:** `_AND_WORD`/`_OR_WORD` detection itself was already correct (`has_or` was computed correctly) — the bug was that it was never *read* on the single-tag path.
- **Competency mention matching:** correct in isolation — `find_competency_mentions_v2` correctly found exactly the one matchable tag.
- **Tag filtering:** this is where the loss occurred — `len(tags) == 1` was treated as "the sentence makes one unambiguous claim," conflating "exactly one DISTINCT TAG was found" with "the sentence names exactly one OPTION."
- **Qualification construction:** constructed a real, confident `Qualification` from the single matched tag — the overclaim became externally visible here.
- **DeclinedExtraction generation:** never reached for this shape, because control flow returned from the `len(tags) == 1` branch first.

## 2. New control inventory (Phase 2)

32 self-authored, synthetic controls across all 18 required categories, in `evaluation/m11g1/alternative_requirement_controls.json`. No third-party text; M11-F's real posting is used only as a local, already-inspected diagnostic trace (§1 above), never copied into any committed file. Hash-frozen in `evaluation/m11g1/controls_hash_freeze.json` **before** any production code was touched.

Two test-authoring mistakes were found and fixed during baseline establishment (disclosed in the hash-freeze file's own `corpus_authoring_fix_disclosed` field, consistent with this project's established discipline of fixing the test rather than the code):
- Category 12's original sentences contained no `_QUALIFYING_INTENT_V2` cue word at all, so they short-circuited to `no_competency_language` before ever reaching the narrative/responsibility filters they were meant to exercise — reworded to include a cue word while remaining clearly narrative/responsibility-shaped.
- Category 15's original `"...unless the team lead approves an exception"` phrase accidentally collided with the pre-existing `_BROADER_NARRATIVE_SUBJECT` pattern's `\bthe\s+team\b` branch — reworded to `"...unless a manager approves an exception"`.

Both fixes were made, and the corpus hash taken, **before** any extractor code was modified.

## 3. Baseline failures (pre-fix, frozen corpus)

| | v1 | v2 |
|---|---|---|
| Pass / total | 21/32 | 25/32 |

v2's 7 baseline failures, all exactly the targeted defect (one recognized tag among several alternatives, resolved confidently instead of declining):

| Control | Category | Alternatives |
|---|---|---|
| `m11g1-02` | 2 — one recognized, one unrecognized | 2 |
| `m11g1-02b` | 2 — one recognized, one unrecognized | 2 |
| `m11g1-03` | 3 — seven alternatives, one recognized | 7 |
| `m11g1-03b` | 3 — four alternatives, one recognized | 4 |
| `m11g1-07` | 7 — competency vs. named technology | 2 |
| `m11g1-08` | 8 — competency vs. education | 2 |
| `m11g1-17b` | 17 — semicolon-separated list | 3 |

No other category showed a baseline failure — confirming the bug's blast radius is exactly the "single matched tag, unmatched sibling alternatives" shape, nothing broader.

## 4. Implemented correction (Phase 4)

A new structural check runs **before** the `len(tags) == 1` branch, under the same precondition the existing `missing_contract` branch already used (`has_or and not has_and`):

1. `_split_alternative_segments_v2(text)` splits the sentence into its OR-list segments (comma/semicolon-separated, final item introduced by a bare `"or "`, or a plain two-way `"X or Y"` when there's no comma) — returning `None` whenever the text doesn't confidently look like a clean list, including the common `"...or equivalent/similar/comparable X"` substitutability idiom, so ordinary prose is never force-fit into list semantics.
2. `_segment_competency_tags_v2(segment)` independently re-runs the same stemmed canonical+alias matching v2 already uses, against each segment on its own.
3. If any segment matches **nothing**, or the segments collectively span **more than one** distinct tag, the sentence declines as `missing_contract` — regardless of how many tags the whole-sentence match happened to find.
4. If every segment matches something and they all agree on the **same single tag** (e.g. `"concurrency, race conditions, or multithreading"` — three synonymous phrasings of one competency), the sentence falls through unchanged to the pre-existing single/AND-split logic.

The shared `DeclinedExtraction` type gained three new **optional, default-empty** fields (`source_text`, `source_span`, `recognized_tags`) to satisfy Phase 3's diagnostic-preservation requirement. This is an additive change to a module-local helper type (not `Qualification`/`NormalizedReference`, the Stage-1 shared contracts the milestone's STOP clause was scoped to) — no architectural blocker was hit, so no STOP was triggered. v1's own `missing_contract` call site now also has these fields available with safe defaults it simply never sets; v1's own function body has zero lines changed.

## 5. Before/after correctness metrics

**G1 frozen corpus** (`scripts/evaluate_m11g1_alternative_requirements.py`):

| | v1 | v2 |
|---|---|---|
| Before fix | 21/32 | 25/32 |
| After fix | 21/32 (unchanged) | **32/32** |

**M11-E's own frozen development corpus** (92 controls, re-run via `evaluate_m11e_v2_extractor.py`): necessity 66/66, logical grouping 69/69, span exactness 69/69, mismatches 1 — **byte-identical to the pre-fix numbers**. Zero impact.

**M11-F's independent holdout**, used strictly as an already-inspected diagnostic benchmark (never as fresh evidence, never retuned):

| Metric | v2 before | v2 after |
|---|---|---|
| Tag precision (corrected) | 12/13 | **12/12** |
| Tag recall | 12/74 | 12/74 (unchanged — the fixed control was never gold-expected to contribute a tag) |
| Exact tag-set accuracy | 29/85 | 30/85 |
| Mismatches | 59 | 57 |
| `embedded` domain tag FP | 1 | **0** |

The one false positive discovered during M11-F is gone; nothing else on that corpus moved.

## 6. Preserved and newly declined cases

**Newly declined** (correct, intended change): the 7 G1 baseline failures above, plus the real M11-F diagnostic case.

**Preserved exactly as before** (no new false declines, verified explicitly):
- Synonymous-OR-of-the-same-tag resolution (`"concurrency, race conditions, or multithreading"`, alias-level `"network protocols or socket programming"`, mixed canonical+alias `"DS&A or algorithms and data structures"`).
- The `"...or equivalent/similar X"` substitutability idiom (both REQUIRED and PREFERRED necessity).
- Narrative-cue and responsibility-lead rejection precedence over the new check.
- AND-only sibling-splitting and `MIXED_UNSUPPORTED` detection (both gated out of the new check entirely since it only runs when `has_and` is false).
- A plain single-tag claim with no "or" at all.
- A single-tag claim with a genuine applicability condition (`"unless a manager approves an exception"`) — `applicability_condition` still captured correctly.

## 7. Source-span integrity

Every newly-declined case's `DeclinedExtraction.source_text`/`source_span` exactly match the original `text`/`span` passed in — verified both by a dedicated unit test (`test_decline_preserves_source_text_and_span`) and directly against the real M11-F trace case (`source_span=SourceSpan(start=0, end=109)` matching the full 109-character source text exactly). `recognized_tags` correctly records the partial matches that were found but not promoted (`('os-networking',)` for the real case; `('concurrency',)` for the synthetic one-recognized/one-unrecognized case) — nothing is silently lost even though no `Qualification` is produced.

## 8. Full regression results

- New M11-G1 tests: **26/26 passed** (`tests/test_m11g1_alternative_requirement_safety.py`).
- Full backend suite: **1439 passed, 13 skipped** (1413 baseline + 26 new).
- M11-C harness (`evaluate_m11c_competency_extraction.py`): unchanged — Option C still 28/28 qualification precision/recall, necessity 21/28, logical grouping 27/28, deterministic.
- M11-E Phase 5 harness (`evaluate_m11e_v2_extractor.py`): unchanged — necessity 66/66, logical grouping 69/69, span 69/69, 1 mismatch (the pre-existing, disclosed stemming-overlap case, unrelated to this fix).
- M11-F Phase 1 reconciliation (M11-E corpus, corrected methodology): unchanged — v2 68/69 precision, 68/68 recall.
- M11-F independent holdout (diagnostic only): the one expected, intended change (§5), nothing else moved.
- M11-B/M11-A1/A2/M10A–E/M9B/8c:v1/v1.1: all covered by, and passing within, the full 1439-test backend suite — no isolated regression found.
- Live parser confirmed still v10 (unimported module, same as every prior milestone's own "not wired in" test, still passing).
- `git diff --stat -- src/` shows exactly one file, +138/-0 — no API/matcher/scoring/schema change anywhere.
- Private M11-D and M11-F source/annotation/builder files remain untracked and untouched.

## 9. Remaining unsupported logical structures

Explicitly NOT addressed by this narrow fix (left for a future, separately-scoped milestone):
- **No new representation for a genuine alternative GROUP.** The fix only decides *whether* to decline; it still cannot represent "the candidate needs ANY ONE of {A, B}" when both A and B are real, different, recognized competency tags. That remains a `missing_contract` decline, exactly as before M11-E even started — unchanged by design (Phase 3 forbade schema changes).
- **Nested alternative structures beyond one flat list** (e.g. `"(A or B) and (C or D)"`) are not specially parsed — only the already-existing `_MIXED_SHAPE` ("and ... either ... or") pattern is recognized; anything more deeply nested than that falls through to whatever the pre-existing AND/OR branching already did, unchanged.
- **Non-list, idiomatic uses of "or"** beyond the one explicitly-guarded `"or equivalent/similar/comparable"` idiom (e.g. hypothetical phrasings like `"or so"`, parenthetical asides) are not exhaustively enumerated; the segmentation helper's `None`-returning fallback is the only general safety net, and it has only been verified against the categories in this milestone's own 32-control corpus, not against unbounded real-world phrasing.
- **Slash-joined synonym pairs within a single list item** (an abbreviation paired with its own spelled-out form, as the real M11-F diagnostic case's first alternative happens to contain) are deliberately NOT split on `/` — intentional, since splitting there would risk breaking a single term into two meaningless halves; this was verified not to affect correctness for the one real case exercising it, but it is a scope boundary worth naming.

## 10. Commit-readiness verdict

The fix, its tests, and this document are internally consistent, fully regression-clean, and narrowly scoped exactly as instructed. **Not committed and not pushed**, per explicit milestone instruction — awaiting separate authorization. M11-G2 has not been started.
