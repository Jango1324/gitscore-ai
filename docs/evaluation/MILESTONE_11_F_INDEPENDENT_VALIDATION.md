# Milestone 11-F — Independent Validation of Paraphrase-Tolerant Extraction

**Status:** Evaluation complete. Not committed. STOP point reached per milestone instructions — awaiting review before any commit authorization.

**Scope discipline:** This milestone changed no production code. `competency_extraction.py`, `competency_aliases.py`, the matcher, the scoring formula, the live parser, and every prior milestone's frozen gold file are byte-identical to HEAD (`7804ff0995f59af077ac0846d61b965800e89fc4`) throughout. Everything below is evaluation-only: new scripts, a new local-only holdout corpus, and new reports.

---

## 1. Verified baseline

Before any new work, the repository state was confirmed: HEAD `7804ff0995f59af077ac0846d61b965800e89fc4` (M11-E's committed state), branch `main`, clean except the five pre-existing untracked M11-generalization files and M11-D's two private artifacts (`evaluation/m11d/source/`, `evaluation/m11d/holdout_annotations.json`) — all still present, untouched. Full suite: **1406 passed, 13 skipped**.

## 2. M11-E metric-reporting audit (Phase 1)

M11-E's own Phase 5 harness (`evaluate_m11e_v2_extractor.py`) scored tag precision/recall at the **control level**: a control counted as a full "hit" the instant its expected tag appeared anywhere among the tags produced, with any extra unexpected tag tracked only in a side-channel `unexpected_additional_tag_count` field — never folded into the precision denominator. It also collapsed every control to exactly one expected tag, undercounting the three controls that legitimately have `sibling_tags`.

Recomputing against the **same frozen M11-E corpus and the same unmodified v1/v2 extractors** with a strict per-(control, tag) prediction framework (`scripts/evaluate_m11f_metric_reconciliation.py`, 7 dedicated tests in `tests/test_m11f_metric_reconciliation.py`):

| Metric | v1 (M11-C) | v2 (M11-E), as originally reported | v2 (M11-E), corrected |
|---|---|---|---|
| Tag TP / FP / FN | 29 / 0 / 39 | — | 68 / 1 / 0 |
| Tag precision | 29/29 | 64/64 | **68/69** |
| Tag recall | 29/68 | 64/64 | **68/68** |
| Exact-set accuracy | 40/79 | not reported | 78/79 |
| Qualification coverage | 26/82 | 65/82 | 65/82 (unchanged) |

The expected-tag population grew from 64 to 68 because three controls (`m11e-and-01`, `m11e-multi-01`, `m11e-multi-02`) carry `sibling_tags` that the original harness never counted. v2's one genuine false positive (the `system-design` sibling leak on `m11e-multi-02`) now correctly costs precision: **68/69, not a clean 1.0.** Conservative declines were also re-bucketed into three mutually-exclusive, sum-consistent categories (safety-correct / out-of-scope / missed-tag) rather than one flat total.

This was a **reporting-only correction** — no change to `competency_extraction.py` or `paraphrase_development_controls.json`. The methodology reconciled cleanly (no STOP triggered).

## 3. New holdout corpus — provenance and integrity

**Acquisition.** 18 real, live job postings (target 15–25) acquired via WebSearch/WebFetch against `jobs.lever.co` and `job-boards.greenhouse.io`, November 2026. Full provenance (employer, role, URL, domain, collection date) in `evaluation/m11f/provenance.json`.

**Acquisition friction, disclosed honestly:** a large majority of `greenhouse.io`-hosted and every `ashbyhq.com`-hosted individual job link either 404'd or redirected to a generic board-listing index rather than the original posting — `ashbyhq.com` postings in particular render their description client-side via JavaScript, which a static fetch never sees (confirmed: only the job title was ever recoverable from any `ashbyhq.com` URL). `jobs.lever.co` postings were markedly more durable (fully server-rendered) and account for 16 of the 18 acquired postings. This mirrors M11-D's own prior experience with URL-expiry friction.

**Domain coverage** (target: software/backend, embedded, electrical, robotics, ML, cybersecurity, infrastructure, systems, data engineering):

| Domain | Postings |
|---|---|
| embedded | 3 |
| electrical | 3 |
| backend | 3 |
| cybersecurity | 2 |
| infrastructure | 2 |
| robotics | 2 |
| systems | 1 |
| data_engineering | 1 |
| ml | 1 |

**Shortfall disclosed honestly:** `ml` and `systems` landed at 1 posting each rather than the 2+ targeted — every other live ML or kernel/systems posting found during acquisition 404'd or redirected before it could be fetched. Not padded with a reused or fabricated posting.

**No reuse:** zero overlap with M11-C, M11-D, M11-E, SOTI, Manulife, or NVIDIA material — confirmed by construction (every posting is a fresh, newly-searched URL).

**Independent annotation (Phase 3).** All 103 controls (85 `technical_competency`, exceeding the ≥75-annotation target) were authored in `scripts/evaluation_lib/m11f_build_gold.py` by direct reading of each posting's Qualifications/Requirements and Responsibilities sections against the 17-tag taxonomy, **before either extractor was run against this text.** Uncertain or genuinely ambiguous cases were recorded as `related_only`/`unknown`/`or_any`/`mixed_unsupported` with explanatory `notes`, never forced into a falsely confident label. Deliberately hard cases included: compound sentences naming two tags at once (`sibling_tags`), a PCB "signal integrity" vs. DSP "signal processing" boundary case, a real `mixed_unsupported` sentence, and a real `or_any` structural case.

**Hash-freeze protocol:**
- 18 raw source files hashed in `evaluation/m11f/source_hashes.json` immediately after acquisition, before annotation began.
- The completed annotation file was hashed **immediately upon completion, before either extractor was ever run**: SHA-256 `ae6da816…ef1de6`, recorded in `evaluation/m11f/gold_hash_freeze.json`.
- `scripts/evaluate_m11f_independent_holdout.py` re-verifies this hash on every run and refuses to evaluate if the gold file has since changed.

**Publication safety.** Raw postings (`evaluation/m11f/source/*.txt`) and the full-text annotation file (`evaluation/m11f/holdout_annotations.json`) remain **local-only, untracked** — never staged. A text-redacted derivative (`evaluation/m11f/holdout_annotations_metadata.json`: every `text` field replaced with `text_length_chars` + `text_sha256`) follows the exact pattern established in M11-D, safe to publish on its own.

## 4. Independent v1-vs-v2 performance (Phase 4)

Run via `scripts/evaluate_m11f_independent_holdout.py`, using the Phase 1 corrected per-prediction methodology, against the frozen holdout (93 `is_applicant_qualification=True` controls; 85 `technical_competency` controls carrying 74 total expected tags once sibling tags are folded in):

| Metric | v1 (M11-C) | v2 (M11-E) |
|---|---|---|
| Qualification precision | 9/9 | 12/12 |
| Qualification recall | 9/93 | 12/93 |
| Tag precision (corrected) | 8/9 | 12/13 |
| Tag recall (corrected) | 8/74 | 12/74 |
| Exact tag-set accuracy | 25/85 | 29/85 |
| False accepts on non-qualification text | 0 | 0 |
| Necessity classification | 0/0 | 0/0 |
| Logical grouping | 5/9 | 10/13 |
| Source-span exactness | 9/9 | 13/13 |

v2 still outperforms v1 (12 vs. 9 qualifications detected, 12 vs. 8 tags), so the Phase-M11-E improvement direction holds on independent data. But both extractors' **absolute recall collapses on real postings**: v2 recovers only **12 of 74 expected tags (16%)** and **12 of 93 genuine qualifications (13%)**, versus 64/64 and 65/82 on M11-E's own development corpus. This is the headline finding of this milestone.

## 5. Precision/recall — exact denominators and exclusions

- **Qualification-level** denominator (93) = every control where `is_applicant_qualification=true`, across ALL text categories (technical_competency, education, named_technology, ambiguous/uninterpretable) — consistent with M11-E's own convention. The 10 `responsibility`-category controls are correctly excluded (they are not qualifications at all).
- **Tag-level** denominator (74 expected tags) = the sum, over all 85 `technical_competency` controls, of `|expected_competency_tag ∪ sibling_tags|` — folding in the 11 extra tags contributed by the posting's own genuinely compound sentences (e.g. `m11f-venus-04`, `m11f-canon-04`, `m11f-kit-03/04`, `m11f-field2-01`, `m11f-main-05`). No case was excluded from the headline denominator.
- Every raw count behind every percentage above is printed by the harness and stored in `evaluation/reports/m11f_independent_holdout_report.json`.

## 6. False-positive / false-negative analysis

**False positives: zero on both extractors**, across every non-qualification category present in this corpus (`responsibility`). No false accept on duty/narrative text, exactly as M11-C/M11-D/M11-E's design intended — this critical safety property **held up on genuinely unseen real text**, not just the authored development corpus.

**False negatives dominate.** Of v2's 56 tag-set mismatches, 53 are pure misses (nothing extracted at all) and only 3 are partial/wrong:

1. **`m11f-venus-04`** — found `concurrency` but missed the sibling `embedded-systems-design` (the dominant tag of the sentence). The compound-tag mechanism can catch one half of a dual-tag sentence while dropping the primary.
2. **`m11f-array-01`** — found `embedded-systems-design` but missed sibling `os-networking`, same pattern.
3. **`m11f-array-02`** — a genuine `or_any` structural case (an embedded-domain sentence listing seven alternative sub-topics, none of which are the same tag) that **should have declined** (gold: `missing_contract`) but instead resolved confidently to `os-networking`.

Case 3 was investigated directly (not just inferred from the mismatch log): `find_competency_mentions_v2` on that control's source text returns `{'os-networking': SEMANTICALLY_EQUIVALENT}` — only one of the seven OR-ed alternatives happens to canonical-match a known tag; none of the other six do. **The `or_any` safety mechanism is not a semantic understanding of "or" — it is an emergent side effect of ≥2 OR-ed segments independently matching *different* tags.** When a real sentence's OR-list has only one matchable segment, the ambiguity is silently lost and the sentence is treated as an unconditional single-tag claim. This is a genuine, newly-discovered safety-relevant gap, not present in M11-E's own hand-authored `or_any` test case (which was deliberately constructed so all three OR-ed options matched different existing tags).

A second newly-discovered mechanism, investigated directly via `_QUALIFYING_INTENT_V2`: v1 catches `m11f-kit-04` (an ML-domain sentence enumerating several computer-vision task names plus one NLP mention) via `computer-vision`, but **v2 misses it entirely** — confirmed: `_QUALIFYING_INTENT_V2.search(text)` returns no match, because the sentence's lead-in verb phrase doesn't fit either the gated "Understanding of/with/in X" leading template or the trailing "X is required" template v2 expects. **v2's precision-oriented intent gate, added in M11-E specifically to suppress false positives, measurably regresses recall relative to v1 on authentic phrasing that doesn't fit its template.**

## 7. Conservative-decline breakdown

Using the Phase 1 three-bucket framework (mutually exclusive, sums to total) across all 103 controls:

| | v1 | v2 |
|---|---|---|
| Total declines | 94 | 91 |
| Safety-correct (true non-qualifications) | 10 | 10 |
| Out-of-scope (real qualification, outside tag taxonomy by design) | 28 | 28 |
| **Missed-tag (real miss)** | **56** | **53** |

Both extractors decline far more than they should on this corpus, and the overwhelming majority of those declines are genuine misses, not safe abstentions — the inverse of M11-E's own development-corpus result (where v2's missed-tag count was 0).

## 8. Performance by discipline (v2, tag-level TP/FP/FN)

| Domain | TP | FP | FN | Technical-competency controls |
|---|---|---|---|---|
| embedded | 3 | 1 | 13 | 20 |
| robotics | 3 | 0 | 6 | 10 |
| backend | 3 | 0 | 4 | 8 |
| electrical | 2 | 0 | 18 | 17 |
| cybersecurity | 1 | 0 | 2 | 8 |
| data_engineering | 0 | 0 | 4 | 4 |
| infrastructure | 0 | 0 | 5 | 8 |
| ml | 0 | 0 | 6 | 5 |
| systems | 0 | 0 | 4 | 5 |

No domain performs well; **electrical (2/20 tags), data_engineering, infrastructure, ml, and systems recover essentially nothing.** Embedded and robotics — the domains the alias table was most heavily built around during M11-E — perform comparatively best but are still far below the development-corpus numbers.

## 9. Historical regression

Full backend suite: **1413 passed, 13 skipped** (1406 baseline + 7 new M11-F metric-reconciliation tests). No production file touched; `git status` shows only new, untracked M11-F artifacts plus the five pre-existing untracked M11-generalization files and M11-D's two private files, all preserved.

## 10. Generalization analysis (Phase 5)

Distinguishing the failure categories the milestone asked about:

- **Paraphrase improvements held up, but are swamped by vocabulary limitations.** v2 still strictly dominates v1 (12 vs. 9 qualifications), confirming the alias/stemming mechanism generalizes in the *direction* M11-E intended. But the 54-entry alias table, built from a hand-authored 92-control corpus, simply does not cover the vocabulary real postings use — domain-specific phrasings for control-theory, PCB/mechanical-design, and sim-to-real-transfer concepts among several others (see the local, unpublished per-control mismatch log for exact phrasing) — this is the dominant failure mode, responsible for the bulk of the 53 pure misses.
- **Qualification-intent misclassification:** confirmed as a real, new regression (`m11f-kit-04` above) — v2's intent gate is narrower than real-world phrasing.
- **Overgeneralized aliases:** not observed as a precision problem here — zero false positives on non-qualification text, and the only two "wrong-tag" style errors (venus-04, array-01) are *under*-generalization (missed sibling), not over-matching.
- **Compound-competency failures:** confirmed — both dual-tag misses (venus-04, array-01) involve genuine compound sentences where only one of two intended tags was recovered.
- **Section-level necessity failures:** confirmed and significant — `necessity` classification denominator was **0/0 for both extractors** on this corpus. Investigated directly: production's necessity field is `None` even for a correctly-tagged, genuinely-matched control (verified directly against one of the posting sentences, not reproduced here), because real "Requirements:"-section bullets rarely repeat an explicit "is required" cue per-sentence the way M11-E's authored corpus always did — necessity is usually established once by the section header, not per bullet. Neither extractor has any section-level necessity inheritance; this is a genuine, newly-measured gap.
- **Source segmentation problems:** not observed — source-span exactness is 9/9 and 13/13 wherever anything was extracted at all.
- **Missing semantic representation:** the `or_any` false-confidence case (array-02, §6) is exactly this — the schema has no way to represent "ambiguous disjunction partially recognized," so the extractor's only options are "decline entirely" or "resolve to whatever single tag happened to fire," and real text pushed it into the unsafe second branch.

No employer-specific fixes were made; no tuning against this holdout occurred — it is now "inspected" material, reported as-is.

## 11. Production-readiness recommendation and commit-readiness verdict

**Readiness:** **Option A (offline development/evaluation use only).** Given 12/74 independent tag recall and 53/85 missed-tag declines, this extractor is not ready for Option B (shadow comparison), Option C (limited non-scoreable recognition), or Option D (broader integration) — all three would surface a tool that silently fails to recognize the large majority of real competency claims. No integration was implemented, consistent with the milestone's restrictions.

**Commit-readiness verdict:** The M11-F evaluation artifacts themselves (scripts, provenance, hash-frozen redacted metadata, this report) are internally consistent and ready to commit as evaluation material **once reviewed** — but per instructions, **no commit or push has been made**, and none should occur until the next milestone explicitly authorizes specific scope (most likely: expand the alias table against the *categories* of vocabulary gap identified in §10, using a freshly-acquired corpus for validation, and add section-level necessity inheritance as a separate, explicitly-scoped change).

**Recommended next smallest milestone:** a vocabulary-expansion milestone targeting the specific gap categories found here (not blind alias-list padding), evaluated again against a *third*, still-unseen holdout — this corpus is now inspected and must not be reused as that validation set.
