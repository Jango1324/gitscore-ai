# Milestone 11-G8 — Competency Recall Bottleneck Decomposition

Evaluation-only. **No production code was modified.** `src/gitscore`
is byte-identical to its state at the start of this milestone
(confirmed: `git diff --stat -- src/gitscore` is empty throughout). No
LLM API was called, no network request was made, no frozen gold was
edited. Everything below is read-only instrumentation of the existing,
already-shipped offline pipeline, plus evaluation-only experiments.

## 0. Verified baseline

| Expectation | Verified |
|---|---|
| HEAD | `9d1cdeef947b0590ad3b272981b8f2dd30fbdb0f` ✅ |
| Parser version | `v12` (unchanged) ✅ |
| Full suite | 1732 → **1738** passed (6 new diagnostic tests), 13 skipped, 2 xfailed — unchanged otherwise ✅ |
| `src/gitscore` | Zero diff throughout ✅ |
| M11-F / M11-G5 frozen gold | Hash-verified unchanged throughout (`test_m11g5_gold_hash_unchanged`/`test_m11f_gold_hash_unchanged`) ✅ |

**Both corpora used below (`evaluation/m11f`, `evaluation/m11g5`) are
preserved, already-inspected, local-only material — never fresh
holdouts, never tuned against by this milestone.**

## 1. Reproduced historical competency metrics

Re-ran the existing, already-committed evaluation scripts against the
preserved, local-only gold — no new corpus, no new script logic for
this step:

| | Reproduced result | Matches cited reference |
|---|---|---|
| M11-F v2 (`scripts/evaluate_m11f_independent_holdout.py`) | tag recall **12/74** | ✅ exactly |
| M11-G5 (`scripts/evaluation_lib/m11g5_phase4_metrics.py`) | tag recall **5/40** | ✅ exactly |

**Denominator definitions verified to differ, and the difference is
now precisely quantified, not merely noted:**

- **M11-F's own convention** (`_expected_tags()` in its evaluation
  script): for every `technical_competency`-category control (85
  total), the expected-tag SET is `{expected_competency_tag} ∪
  sibling_tags`. The recall denominator (74) is the SUM of this set's
  size across all 85 controls (0 for untaggable controls, usually 1,
  occasionally 2+ for controls with declared siblings) — a **per-tag-slot**
  denominator. The numerator (12) counts set-intersection size summed
  the same way — a control emitting BOTH its primary tag and a sibling
  tag can contribute 2 to the numerator.
- **M11-G5's own convention** (`m11g5_phase4_metrics.py`): the
  denominator (40) counts only TAGGABLE **controls** (one slot per
  control, regardless of sibling count); the numerator checks only
  whether the single `expected_competency_tag` was produced, **never**
  crediting a sibling-only match toward recall (siblings are credited
  only on the separate precision side, as "accepted sibling" emissions).
- **Measured practical impact of the difference, not merely asserted:**
  re-applying M11-F's per-tag-slot convention to the G5 corpus (4 of
  its 40 taggable controls declare a sibling) would widen G5's own
  denominator to 44; checked directly, none of the 3 sibling-bearing
  FN controls had ANY tag emitted at all (not even the sibling), so the
  numerator is unaffected — the recomputed figure would be **5/44
  (11.4%)** instead of 5/40 (12.5%), a small downward shift from a
  wider denominator, not from a counting error that favors either
  figure. Conversely, applying G5's own per-control convention to
  M11-F's corpus (via this milestone's own stage-attribution script,
  §2) gives **11/64 (17.2%)** against the per-tag-slot 12/74 (16.2%) —
  the two conventions land within 1 percentage point of each other in
  practice, but are not the same measurement and should not be quoted
  interchangeably without this caveat.
- Frozen gold for both corpora was never modified to produce any of
  the above — all three figures (12/74, 11/64, 5/44) are different
  **readings** of the identical, unedited underlying data.

## 2. Exact failure-stage distribution (Phase 2)

Instrumented via `scripts/evaluation_lib/m11g8_stage_attribution.py`,
which calls the REAL, already-shipped internal functions
(`_QUALIFYING_INTENT_V2`, `find_competency_mentions_v2`,
`_NEGATION_PATTERNS`, `contains_narrative_cue`, `_RESPONSIBILITY_LEAD`,
`extract_competency_qualifications_v2`, `segment_description`,
`recover_unadmitted_qualification_claims`) in their own real call
order — never re-implementing or changing any decision, never
double-counting (each row lands in exactly one stage, verified by
`test_stage_attribution_categories_sum_to_confirmed_fn`).

**Combined across both corpora (104 taggable controls, 88 confirmed
tag-level FNs — reconciling exactly with §1's reproduced 5/40 and
11/64 control-level figures):**

| Stage | M11-G5 | M11-F | Combined | Share of 88 confirmed FN |
|---|---|---|---|---|
| **A** — discarded by segmentation (never admitted, never G4-recovered) | 1 | 0 | **1** | 1.1% |
| **B** — intent-gate (`_QUALIFYING_INTENT_V2`) rejected before vocabulary matching | 15 | 24 | **39** | 44.3% |
| **C** — intent passed; zero canonical/alias term matched | 18 | 29 | **47** | 53.4% |
| **D** — wrong tag produced | 1 | 0 | **1** | 1.1% |
| **E** — negation/narrative-cue/responsibility-lead/missing-contract decline | 0 | 0 | **0** | 0% |
| **F** — projection discarded/transformed the result | — | — | **0 by construction** | n/a |
| **H** — unexplained | 0 | 0 | **0** | 0% |

**Critical caveat, directly tested rather than assumed: "earliest
blocking stage" is NOT the same claim as "sole blocking stage," and
the 39-count for B must not be read as 39 recoverable tags.** `attribute_one_control`
stops at the FIRST stage that would decline a claim, by design (per
the mission's own "avoid double-counting" instruction) — but a
Category-B claim (intent-gate rejected) might ALSO fail vocabulary
matching even if the intent gate were hypothetically perfect. This was
checked directly, not inferred: for each of the 39 Category-B controls,
the real stemmed vocabulary/alias matching logic
(`_stemmed_text_v2`/`_STEMMED_COMPETENCY_PATTERNS_V2`/
`_STEMMED_ACTIVE_ALIAS_PATTERNS_V2`) was run directly, bypassing ONLY
the `_QUALIFYING_INTENT_V2` check (never bypassing vocabulary/alias
matching itself, never bypassing any `extract_competency_qualifications_v2`
decision beyond that one gate):

| | Count | Meaning |
|---|---|---|
| B-cases where vocabulary ALSO already matches the expected tag | **7 / 39** | Genuinely recoverable by an intent-gate-only fix |
| B-cases where vocabulary would STILL fail even with intent fixed | **32 / 39** | Double-blocked — an intent-gate fix alone cannot recover these; vocabulary/alias coverage would ALSO need to change |

**An intent-gate-only fix therefore has a measured ceiling of +7
(not +39) tag-level recoveries** — 16/104 → 23/104 (15.4% → 22.1%).

The SAME check was run in the other direction for Category C's 47
cases (hypothetically assume vocabulary now matches — would the
downstream negation/narrative-cue/responsibility-lead/missing-contract
safeguards (stage E) THEN block it?): **0 of 47** would be blocked. An
alias/vocabulary-only fix has a theoretical ceiling of **+47** (16/104
→ 63/104, 60.6%) — a much larger ceiling than B's, but see §6/§7: this
larger number is a THEORETICAL, per-sentence ceiling for THIS frozen
corpus's exact 47 phrasings, not a generalizable estimate — achieving
it would almost certainly require sentence-specific alias additions
carrying a strong overfitting risk, the exact failure mode already
observed twice (M11-C→M11-E widened aliases against a dev corpus,
each time landing at a much smaller real-world gain on the NEXT fresh,
independent corpus). The 47 ceiling is reported honestly as measured,
not presented as an achievable production target.

**Category F is reported as zero by construction, not by absence of
looking:** confirmed directly against `project_qualification()`'s own
source — it decides ONLY `JobRequirement`-vs-`UnparsedClaim` routing
(necessity-unknown, observability-unknown, mixed-logical-structure,
applicability-condition, or uninterpretable-kind safety rules); it
never reads or rewrites `Qualification.normalized_reference.competency_tag`.
Projection structurally cannot cause a tag-level false negative —
stated precisely here so it is not mistaken for "zero measured," which
would understate the certainty.

**The one confirmed stage-D case** (`m11g5-p16-05` — control ID only,
no posting text reproduced, consistent with M11-G5's own publication-safe
reporting convention): a claim naming familiarity with a real-time
operating system used in safety-rated embedded contexts, where the
`os-networking` canonical pattern (`\boperating\s+systems?\b`) fired
on the generic "operating system(s)" phrase before the more specific
`embedded-systems-design` reading could — already identified and
reported during M11-G5 itself, now reconfirmed as the corpus's
**only** wrong-tag instance.

**The sole stage-A case** (`m11g5-p03-05`) is addressed directly in §3
(Experiment A).

**Separate, non-FN category G (ontology representability):** of 142
total `technical_competency` controls across both corpora, **38 are
untaggable by gold's own design** (no `expected_competency_tag` at
all — 17 in M11-G5, 21 in M11-F) — not a pipeline failure, a
deliberate "this competency has no safe 17-tag representation" gold
annotation. Analyzed further in §3 (Experiment B).

## 3. Oracle admission upper-bound (Experiment A)

**The sole stage-A control, tested directly under oracle admission**
(the real extractor called on the gold text with segmentation/recovery
entirely bypassed). **What "oracle" means here, precisely, so this is
never confused with the different, intent-gate-specific oracle check
in §2:** ONLY the upstream admission decision (`segment_description()`/
`recover_unadmitted_qualification_claims()` — whether the sentence
ever becomes a `Claim` at all) is bypassed. The call target is the
real, complete, unmodified `extract_competency_qualifications_v2()` —
its own internal `_QUALIFYING_INTENT_V2` intent-gate check and its own
`find_competency_mentions_v2()` vocabulary/alias matching both still
run exactly as shipped, with no bypass, no stub, and no shortcut:

```
ORACLE RESULT: still declined -> no_competency_language
```

**Experiment A's result: oracle-perfect admission recovers ZERO
additional confirmed FNs.** Current measured recall (16/104, 15.4%
combined) **is already the admission-oracle ceiling** — segmentation/
recovery admission is not a measurable bottleneck at all in either
corpus, and this single case fails for an entirely separate reason
(it is, independently, EITHER a Category-B or Category-C case once
admission stops being the blocker — the decline reason
`no_competency_language` is exactly the shared signal both stages
produce, consistent with §2's own stage taxonomy). This is the single
cleanest, most decisive finding of this
milestone: **the 85%+ miss rate has nothing to do with whether a
sentence reaches the extractor.** (Pinned by
`test_experiment_a_oracle_admission_recovers_zero_additional_cases` —
not presented as a deployable result, an evaluation-only diagnostic
ceiling per the explicit instruction.)

## 4. Ontology/alias coverage analysis (Experiment B)

| | Count | Interpretation |
|---|---|---|
| Category C (taggable, vocabulary/alias non-match) | **47 / 104** taggable controls (45.2%) | The ontology already has a tag for these; the specific PHRASING used doesn't match any canonical/alias pattern. A missing-alias problem, by construction (gold assigned a real 17-tag-vocabulary tag). |
| Category G (untaggable, no ontology slot) | **38 / 142** total technical_competency controls (26.8%) | Gold itself declares no safe 17-tag representation exists. A missing-ontology-representation problem, structurally distinct from C. |

**Missing-alias (C) and missing-ontology-representation (G) are
comparable in magnitude and require different fixes** — widening alias
tables cannot ever close the G gap (there is no tag to alias TO), and
adding ontology tags cannot close the C gap (the tag already exists;
the phrasing simply isn't recognized). **Diagnostic, not a
production recommendation in itself per the explicit instruction** —
no new alias or ontology entry was added or tuned against either
corpus.

## 5. Conservative validation rejection analysis (Experiment C)

**Among the 88 confirmed tag-level FNs: zero were caused by the
existing negation/narrative-cue/responsibility-lead/missing-contract
validation safeguards** (Category E, §2) — pinned by
`test_category_e_validation_safeguards_are_not_the_measured_bottleneck`.

**Within the separate 38-control untaggable (Category G) set**, only
a minority are driven by the specific logical-safety shapes these
safeguards exist to decline:

| | M11-G5 (17 untaggable) | M11-F (21 untaggable) |
|---|---|---|
| `or_any`/`mixed_unsupported` logical composition (the N-of-M/OR-group safety shape) | 4 (23.5%) | 2 (9.5%) |
| `single`/`and` composition, declared `unknown`/`related_only` match relation | 13 (76.5%) | 19 (90.5%) |

**Headline finding: the existing conservative-validation layer is NOT
the measured bottleneck anywhere in this data.** The overwhelming
majority of untaggable competencies (32/38, 84% combined) are missing
for pure vocabulary/ontology reasons entirely unconnected to the
necessity/logical-group/ambiguity safeguards — those safeguards are
doing their intended, narrow job correctly and rarely (6 of 142
technical_competency controls combined, 4.2%), not quietly suppressing
a large hidden pool of correct extractions. **No safeguard was
weakened to produce this measurement; this is a count of existing,
unmodified behavior.**

## 6. Option A/B/C comparison (Phase 4)

Grounded directly in §2–5's measured facts, not asserted:

| | **Option A** — deterministic admission/normalization improvement | **Option B** — future LLM extraction stage + deterministic verification | **Option C** — hybrid (deterministic first, escalate unresolved) |
|---|---|---|---|
| Recall opportunity, per measured attribution | Measured, tiered ceilings, not a single number: intent-gate-only fix +7 (confirmed); alias-only fix up to +47 (theoretical, corpus-specific, see §2); the 32 double-blocked B-cases need BOTH | Unmeasured; no evaluation run (per explicit restriction) — plausibly addresses the double-blocked cases too, but this is a hypothesis, not evidence | Same ceiling as B, scoped to the subset deterministic processing can't resolve — but that subset is currently ~85% of taggable controls (16/104 succeed today), so "escalation" would be the NORM, not a rare tail |
| False-positive / fabrication risk | Low, bounded — same regex/vocabulary risk surface already measured 3× (M11-C→E→F/G5), never produced a tag-level false positive in 3 independent corpora (confirmed: 0 tag_fp in M11-F's own report) | New risk class entirely: hallucinated tags/necessity at the INPUT boundary, before any existing guardrail sees it | Same new risk class as B, for a large (not small) fraction of real input |
| Source provenance | Unchanged — exact span discipline already enforced | Would need NEW span-verification (explicitly named in Option B's own design) — unproven | Same new requirement as B |
| REQUIRED/PREFERRED safety | Unchanged — §5 confirms existing necessity/logical guardrails are not even the bottleneck, so they remain exactly as conservative as today | Depends entirely on the deterministic post-validation layer Option B proposes keeping — if implemented faithfully, risk is bounded to the SAME layer; unproven in practice | Same as B |
| OR/AND/conditional handling | Unchanged — §5 confirms `mixed_unsupported`/OR-group safety already works correctly and rarely fires | Unproven — LLM-generated structure would still need the same deterministic classification this milestone confirms already works | Same as B |
| Determinism/reproducibility | Full — same guarantee the whole offline pipeline already has | Not guaranteed without careful temperature/prompt control — unproven here | Same concern, for a larger fraction of input than typically assumed for "hybrid" systems |
| Operational complexity | Low — same module, same test discipline (G6/G7's own evaluation-first process) | High — new dependency, new failure modes, new monitoring surface | High, and the "small escalation tail" assumption does not hold given current ~85% miss rate |
| Latency/cost | Negligible — regex-speed | Real, per-call cost and latency — unmeasured here | Real cost for the majority of input, not a tail case |
| Privacy | None — fully local, no data leaves the process | **Material** — private job-posting text would need to leave the local process to reach an external LLM API, explicitly restricted in this milestone and requiring separate authorization even to prototype | Same material privacy concern, for most input |
| Scoring/assessability contract impact | None — this milestone confirms (§3) admission/necessity/logical/projection stages are untouched and not the bottleneck | Would still route through the SAME existing `project_qualification()`/matcher/scorer, if faithfully implemented — but unproven | Same as B |
| Fails safely when uncertain | Yes — confirmed: the pipeline already declines (never fabricates) on all 88 measured misses | Depends on prompt/verification design — not evaluated | Same dependency |

**No claim is made here that Option B/C would improve recall — only
that, structurally, the intent-recognition and paraphrase-tolerance
problem these 86 non-trivial cases (39 B + 47 C) represent is the kind
of flexible natural-language task a regex-based deterministic approach
has now plateaued on across 3 independent corpora (M11-E's own dev
corpus: 100%; M11-F: 16.2%; M11-G5: 12.5% — a consistent ~5–8×
real-world drop each time), which is evidence FOR eventually trying
something structurally different, not evidence that an LLM would
work.**

## 7. Recommended next smallest implementation (Phase 5)

Given the measured facts — not development-corpus accuracy alone, and
not the earliest-blocking-stage counts alone (§2's caveat):

1. **Admission (A) and wrong-tag (D) are not worth further investment**
   right now — 1 case each, oracle-confirmed to yield zero additional
   recall for A.
2. **Validation safeguards (E) are not the bottleneck** and must not
   be loosened — they are already correctly conservative and rarely
   triggered.
3. **The REAL, tiered recoverable ceilings, directly tested (§2), are
   smaller and more structured than a flat B/C split suggests:**
   - **+7** genuinely recoverable by an intent-gate-only fix (the 7 of
     39 B-cases where vocabulary already matches).
   - **+47** theoretically recoverable by a vocabulary/alias-only fix
     (all of Category C) — but this is a corpus-specific ceiling for
     47 individual phrasings, not a generalizable estimate; achieving
     it for real would require exactly the kind of sentence-by-sentence
     alias tuning this project's own evaluation-first discipline exists
     to prevent, and the kind that has already been tried twice
     (M11-C→M11-E) with diminishing real-world returns.
   - **32 of 39 B-cases are double-blocked** — neither lever alone
     recovers them; both the intent gate AND the vocabulary/alias table
     would need to change for the same sentence.
4. **G (ontology gaps, 26.8% of all technical_competency controls) is
   a separate, large, independent ceiling** that no amount of
   alias/intent-gate work can ever close.

**Recommendation: Option 1 — a narrowly scoped deterministic
improvement, specifically targeting the intent-gate (Category B)
using the SAME evaluation-first discipline M11-G6/G7 already
established** (a fresh, adversarially-tested, hash-frozen corpus;
candidate designs compared before any production edit; explicit
false-positive testing) — **not** another round of alias-table
widening (Category C), for two compounding reasons now directly
measured rather than assumed: (a) alias-table widening has already
absorbed two prior milestones' effort with diminishing, corpus-specific
returns, and (b) even a PERFECT intent-gate fix only recovers 7 cases
on its own — a small, honestly-scoped, low-risk experiment, chosen
because it is bounded and structurally clean (a single regex change
tends to generalize, per G4/G6/G7's own track record), not because it
promises a large headline number.

**This recommendation is explicitly bounded, not open-ended, and the
expected gain is modest by design:** +7 tag-level recoveries (16/104 →
23/104, 15.4% → 22.1%) is the measured ceiling for this specific,
narrow experiment — it will not, by itself, close the 32-case
double-blocked gap or the 47-case alias ceiling. If this third
narrowly-scoped deterministic attempt (on a FRESH corpus, never this
one) also fails to move real-world recall by anywhere near its own
measured ceiling, that would constitute measured evidence — not mere
intuition — that even bounded, structurally-clean deterministic fixes
don't generalize past dev-corpus phrasing, at which point **Option 2
(a controlled, separately-authorized offline LLM proof of concept,
with zero live postings transmitted and explicit privacy review)**
becomes the best-evidenced next experiment, specifically because it
targets exactly the double-blocked and alias-ceiling cases a
regex-only approach has now shown real difficulty reaching — not
because this milestone asserts an LLM would improve recall, which it
explicitly does not.

**Option 4 (ontology correction)** is recommended as a separate,
independently valuable, low-risk, PARALLEL track (it touches a
disjoint 38-control set with zero interaction with B/C) — not
contingent on Option 1's outcome.

**Option 3 (hybrid)** is not recommended as the next step: the
"escalate only unresolved edge cases" framing does not match this
corpus's own measured reality (85% of taggable controls are currently
unresolved, not a tail), so a hybrid design today would functionally
be Option B for most input with extra routing complexity on top,
without first establishing (via Option 1's bounded experiment)
whether that majority can be meaningfully shrunk deterministically
first.

## 8. Future independent evaluation protocol

Any future milestone that touches Category B or C (or proposes Option
2/3) must measure, on a corpus meeting the SAME standard this
project's own M11-D/F/G5 lineage already established (independently
sourced, never previously inspected, hash-frozen before inference,
never tuned against):

1. **Qualification-level precision/recall** (is a genuine applicant
   qualification recognized as a qualification at all).
2. **Tag-level precision/recall**, with the denominator convention
   stated EXPLICITLY and consistently (per-control or per-tag-slot —
   §1 shows these are not interchangeable without disclosure) and
   every emitted prediction counted in the denominator, including
   wrong-tag emissions.
3. **Necessity safety**: zero fabricated REQUIRED/PREFERRED from
   non-qualification content (the exact invariant M11-G6/G7 already
   established and tested).
4. **Source-span and provenance exactness** for every produced claim.
5. **Score-denominator invariants**: confirm `assessable_count`/
   `alignment_score` are affected ONLY by legitimate, measured
   requirement-set changes, never by a change to scoring logic itself
   (the exact discipline M11-G7's Phase 4 already demonstrated).
6. **Stage attribution** (this milestone's own A–H taxonomy) run
   BEFORE any strategy comparison, to confirm WHERE a candidate
   change's gains actually come from, not just that a headline number
   moved.
7. **No full live integration without this independent validation
   completing first**, regardless of development-corpus results.

## 9. Full regression-test results

| | Count |
|---|---|
| New diagnostic tests (`tests/test_m11g8_competency_recall_bottleneck.py`) | 6 passed |
| Full backend suite | 1732 → **1738 passed**, 13 skipped (unchanged), 2 xfailed (unchanged) |

## 10. Exact changed-file inventory

**Zero changes under `src/gitscore`.** New files only (all
evaluation-only):

- `docs/evaluation/MILESTONE_11_G8_COMPETENCY_RECALL_BOTTLENECK.md` (this doc)
- `scripts/evaluation_lib/m11g8_stage_attribution.py`
- `tests/test_m11g8_competency_recall_bottleneck.py`
- `evaluation/reports/m11g8_stage_attribution.json`

All M11-D/F/G5 private data and the pre-existing untracked M11-generalization artifacts are untouched.

## 11. Explicit implementation approval questions

1. Approve Option 1 (a bounded, evaluation-first, intent-gate-only deterministic improvement attempt) as the next smallest milestone, explicitly scoped to NOT touch alias tables (Category C) this round?
2. If Option 1's own fresh, adversarially-tested corpus shows the same ~15% real-world ceiling persisting a third time, pre-approve treating that as sufficient evidence to propose (in a SEPARATE, future authorization request) a controlled, zero-live-posting, privacy-reviewed offline LLM proof of concept (Option 2) — or would a different threshold/criterion be preferred?
3. Approve Option 4 (ontology correction for the 38-control Category-G gap) as an independent, parallel-track milestone, not contingent on Option 1's outcome?
4. Should the stage-attribution script (`m11g8_stage_attribution.py`) and its 6 tests be treated as a permanent, reusable diagnostic (re-run automatically whenever `competency_extraction.py` changes), or kept as a one-off investigation artifact?
5. Does the denominator-definition disclosure in §1 warrant retroactively annotating the M11-F/G5 milestone docs with a cross-reference to this one, or is a forward-only citation (this doc pointing back at them) sufficient?

## Commit-readiness verdict

**Not committed, per instructions.** New files produced this pass (all evaluation-only; `src/gitscore` untouched):

- `docs/evaluation/MILESTONE_11_G8_COMPETENCY_RECALL_BOTTLENECK.md` (this doc)
- `scripts/evaluation_lib/m11g8_stage_attribution.py`
- `tests/test_m11g8_competency_recall_bottleneck.py`
- `evaluation/reports/m11g8_stage_attribution.json`

All M11-D/F/G5 private data and the pre-existing untracked M11-generalization artifacts are untouched. **Stopping here per instructions — no production change was proposed for immediate implementation; M11-G9 has not started.**
