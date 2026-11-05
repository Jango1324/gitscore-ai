# Milestone 11-G5 — Independent Full-Pipeline Qualification Validation

Evaluation-only. No production code, live parser, matcher, scoring, API,
frontend, or frozen gold changed. Nothing here is integrated. Nothing
here is committed by this milestone (per its own instructions) — this
document records what was measured so a human can decide what to do
next.

## 0. Verified baseline (Phase 0)

| Expectation | Verified |
|---|---|
| HEAD | `321c2481f184c22bebbd17fa7ee8c43697ee0792` ✅ |
| Branch | `main` ✅ |
| Parser version | v10 (unchanged — no edits to `src/gitscore/jobs/parsing/*`) ✅ |
| Full suite | **1485 passed, 13 skipped** before any G5 work; **1493 passed, 13 skipped** after adding this milestone's 8 focused tests (8 new, 0 regressed, skip count unchanged) ✅ |
| M11-G1–G4 | Committed (`299d229`, `da32c49`, `4b4e3b9`, `321c248`) ✅ |
| Live scoring/matcher/API/frontend | Untouched — confirmed via `git status --short` showing zero modified tracked files throughout this milestone ✅ |

A substantial amount of Phase 0–4 work for this exact milestone was
already present on disk as untracked, local-only files when this pass
began (the corpus, provenance, hash freeze, annotations, and the Phase
1/Phase 4 harness scripts). This pass **verified** that prior work
rather than re-doing it: re-hashed the frozen gold and all 18 source
files against their recorded freezes (both matched byte-for-byte),
re-ran the Phase 4 execution script and confirmed it reproduces
identical output, then built the Phase 4 **aggregate metrics** (the
part that was missing — the existing harness emitted per-control rows
but no TP/FP/FN rollup) and the Phase 5/6 analysis below.

## 1. Corpus inventory and source integrity (Phase 2)

18 postings (target was 15–25), acquired via WebSearch/WebFetch against
live `jobs.lever.co` postings in November 2026, each with a recorded
URL, employer, role, domain, collection date, and SHA-256 hash in
`evaluation/m11g5/provenance.json` / `source_hashes.json`. No posting
overlaps M11-D, M11-F, M11-E, SOTI, Manulife, NVIDIA, or any synthetic
corpus (the prior corpora acquirer's own disclosure log is preserved
verbatim in `provenance.json`).

Domain distribution: ml ×3, infrastructure ×3, embedded ×2, electrical
×2, distributed systems ×2, data engineering ×2, backend ×1,
cybersecurity ×1, robotics ×1, systems (HPC) ×1. **Disclosed shortfall**
(carried over from the existing provenance record, re-verified here):
backend, cybersecurity, robotics, and systems landed at 1 posting each,
not 2+, because repeated durable-listing searches on public boards
mostly 404'd or surfaced only one non-expired candidate per domain —
documented honestly rather than padded with a reused or fabricated
posting. One partial employer-independence compromise is disclosed:
the single robotics posting (FieldAI) shares an employer with two
M11-F robotics postings, though it is a different URL and different
role content, not text reuse.

**161 annotated controls, 143 of them genuine applicant qualifications**
(exceeds the ≥100-annotation target). Gold was independently annotated
against the 17-tag competency taxonomy and the full G1-G4 semantic
contract *before* either pathway was run, hash-frozen immediately after
(`gold_hash_freeze.json`), and **re-verified unaltered** by this pass
(`sha256` match, 108,044 bytes). A redacted, publication-safe derivative
(`holdout_annotations_metadata.json`) strips verbatim posting text,
keeping only structural fields plus a per-control text hash/length —
this is the only G5 annotation artifact safe to reference in a
committed report; raw text stays local-only.

## 2. Evaluation-only harness (Phase 1)

`scripts/evaluation_lib/m11g5_dual_path_comparison.py::run_dual_path()`
runs the REAL, unmodified Path A (`parse_job_description_with_diagnostics`)
and the REAL, unmodified Path B (`segment_description` +
`document_has_any_recognized_heading` + M11-G4's
`recover_unadmitted_qualification_claims` + M11-G1/G2's
`extract_competency_qualifications_v2(..., has_section_context=True)` +
M11-B's `project_qualification`) against identical text, then
reconciles — never concatenates — the two outputs per exact source span
into one of exactly four named relationships:
`path_b_only_recovered`, `path_b_adds_competency_to_already_admitted`,
`path_b_declines_already_admitted`, `contradictory`. A new focused test
(`tests/test_m11g5_independent_validation.py`) pins that every
comparison the harness ever produces carries one of those four labels,
that reconciliation is deterministic, and that the gold/source hash
freezes hold.

`scripts/evaluation_lib/m11g5_phase4_metrics.py` (new this pass) runs
the harness over all 161 frozen controls and computes the aggregate
numerators/denominators below, writing a publication-safe rollup to
`evaluation/reports/m11g5_phase4_metrics.json` (counts and structural
labels only — no verbatim posting or gold text).

## 3. Category A — all genuine applicant qualifications (Phase 4A)

n = 143 positive controls (genuine qualifications), 18 negative controls
(responsibilities/narrative).

| | Path A (baseline) | Candidate (A + G1-G4 pathway) |
|---|---|---|
| Recognized (job_requirement or unparsed) | **135/143 = 94.41%** | **135/143 = 94.41%** |
| Missed (FN) | 8 | 8 |
| False requirements promoted from the 18 non-qualifications | **0/18** | **0/18** |
| Claims recovered ONLY by M11-G4's recovery pass | — | **0** |

**Identical recall, identical false-positive count, zero additional
coverage from the candidate pathway on this corpus.**
`recover_unadmitted_qualification_claims` recovered nothing here —
not because nothing was missed, but because the 8 misses are a
*different shape* of gap than the one G4 was built to catch (see below).

Recall by `qualification_kind` (identical for both paths — the 8 misses
are entirely Path-A-level, so Path B inherits them unchanged):

| kind | n | recognized |
|---|---|---|
| education | 12 | 11 |
| nontechnical | 30 | 28 |
| specific_technology | 44 | 42 |
| technical_competency | 57 | 54 |

**Root cause of all 8 misses, confirmed by direct inspection — not two
separate problems, but two:**

1. **7 of 8** come from a single posting (`p03-alluxio-distributed.txt`,
   whose own section heading is `"Who We Are Looking For:"`). Confirmed
   directly against `segmentation.py`:
   `_classify_heading_line("Who We Are Looking For:", ...)` returns
   `_SectionKind.SKIP`, because the `NON_QUALIFICATION`/`SKIP` heading
   root `\bwho we are\b` — correctly built to suppress "Who We Are"
   company-narrative headings — also matches this unrelated, authentic
   "who is our candidate" qualifications-heading style. The effect:
   `segment_description()` returns **zero claims** for that entire
   section — not one phrasing miss, the complete REQUIRED block (degree
   requirement, years of experience, language requirements, etc.), with
   no diagnostic `unparsed_claim` trace either. This is a **pre-existing
   Path A (live parser v10) defect**, not something introduced by
   G1-G5, and it is now pinned by
   `test_who_we_are_looking_for_heading_is_a_known_false_positive_skip_collision`
   / `test_entire_qualifications_section_under_that_heading_is_admitted_as_zero_claims`.
   M11-G4's recovery pass does not catch it because it targets a
   structurally different gap (unsectioned content that fails the
   requirement-shape gate but passes the competency-intent gate) — a
   whole section misclassified as `SKIP` never reaches that code path
   at all.
2. **1 of 8** (`m11g5-p18-04`) is a near-duplicate AWS/Azure
   infrastructure-knowledge claim — the *third* such claim in the same
   posting (after `p18-01`, `p18-02`, which cover the same underlying
   cloud-platform skill in different wording). This is `dedup.py`'s
   intended near-duplicate suppression working correctly, not a
   coverage gap — the annotator's own note flags it as a deliberate
   near-duplicate test, and the content was already captured once.

## 4. Category B — technical competencies, tag level (Phase 4B)

n = 57 `technical_competency` controls; 40 expect a specific one of the
17 production tags, 17 are deliberately tag-less (related_only /
unknown / or_any-spanning-multiple-tags / out-of-vocabulary).

| | Value |
|---|---|
| Tag-level TP / FN (of 40 taggable) | **5 / 35** |
| Tag-level recall | **5/40 = 12.5%** |
| Total tag predictions emitted (all 57 controls) | 7 |
| — correct primary tag | 5 |
| — accepted sibling tag (declared `sibling_tags`) | 1 |
| — incorrect/unrelated tag | 1 |
| Tag-level precision (every emission counted) | **6/7 = 85.71%** |
| Untaggable controls (17) correctly declined | **17/17 = 100%** |
| Untaggable controls wrongly given a tag | 0 |

The one incorrect emission: `m11g5-p16-05` (a claim naming familiarity
with a real-time operating system used in safety-rated embedded
contexts), expected `embedded-systems-design`, produced
`os-networking` instead — the `\boperating\s+systems?\b` canonical
pattern fired on the generic "operating system(s)" phrase before the
more specific embedded reading could take priority.

**Root cause of the 12.5% recall ceiling, confirmed directly by
isolated reproduction against the real functions, not inferred:**

- `_QUALIFYING_INTENT_V2` (the precision gate `extract_competency_qualifications_v2`
  checks before even looking at vocabulary) requires an explicit leading
  cue (`experience|knowledge|understanding|familiarity|proficiency|
  skills?|background|expertise|grounding|grasp` + `with|of|in|building|
  optimizing|debugging`) or a trailing `is/are required/preferred/
  necessary/a plus`. Two extremely common authentic bullet-point shapes
  fall through this gate entirely, confirmed by isolated reproduction
  against the real function on minimal constructed inputs sharing the
  same structure (not the staged posting text itself): (a) a bare
  comma-separated skill/technology list ending in a bare adjective with
  no copula ("…, X preferred." rather than "X is preferred.") declines
  even when a canonical competency phrase is literally present among
  the listed items (`m11g5-p07-08`, embedded/signal-processing/control-
  systems domain); (b) a years-of-experience lead-in using a bare verb
  immediately after "years" rather than the noun "experience" directly
  before that verb (e.g. "N years **building** X" vs. "experience
  **building** X") also declines (`m11g5-p02-01`, ML domain).
- Separately, several alias patterns are narrower than real phrasing:
  the `system-design` alias only matches the compound nouns `"API
  design"`/`"service design"`, not an equally common verb-phrase
  equivalent naming the same skill via a different part of speech
  (`m11g5-p01-01`, backend domain) — this exact miss was one the gold
  annotator expected to match and it did not, confirmed by isolated
  reproduction.

**This is not new information in kind — it is new information in
confirmation.** M11-F independently measured **12/74 = 16.2%** tag
recall on its own, different independent corpus, and already named
`_QUALIFYING_INTENT_V2` as the root cause for its own misses. G5's
**5/40 = 12.5%** on a third, non-overlapping corpus lands in the same
range. Three independent corpora now agree: whatever this pathway
achieves on its own development data (M11-E: 64/64 = 100%), real-world
tag recall sits in the **12–16%** band.

## 5. Category C — semantic correctness (Phase 4C)

Measured only where the candidate pathway actually produced a
competency `Qualification` (6 instances, across the 5 controls where it
committed to a tag at all — one control, `m11g5-p06-02`, produced two
`Qualification`s from one claim).

| | n checked | n agree | rate |
|---|---|---|---|
| Necessity (REQUIRED/PREFERRED/UNKNOWN) | 6 | 6 | **100%** |
| Logical composition (single/and/or_any/mixed_unsupported) | 6 | 1 | 16.7% |
| Exact source-span preservation | 6 | 6 | **100%** |

**Necessity and source-span are perfectly reliable** on this corpus
whenever the pathway commits to output at all — it never asserts an
untrue REQUIRED/PREFERRED, and never drifts a `Qualification`'s span
away from its originating claim.

The logical-composition disagreement splits into two distinct causes,
confirmed by inspecting all 6 directly (not estimated):

- **1 genuine defect**: `m11g5-p06-02` (electrical domain) is a
  "N years of experience in at least two of the following M named
  areas" combinatorial selection — gold expects `mixed_unsupported`
  (the same honest "we cannot safely flatten this" diagnostic M11-B
  built for AND-of-OR shapes). The pathway instead emits two separate
  `Qualification`s, both labeled `and`, silently treating "at least
  two of three" as "all three required." This is a real gap in N-of-M
  handling that the mixed-unsupported mechanism was never extended to
  cover.
- **4 measurement-granularity cases, not defects**: e.g. `m11g5-p01-02`
  (backend domain) states two distinct competency claims joined by
  "and" in one sentence; gold labels the whole sentence `and` (two
  conjuncts); the pathway only has vocabulary for one of the two
  (`distributed-systems` — the other names a concept outside the
  17-tag vocabulary), produces exactly one `Qualification`, and
  correctly labels *that single extraction* `single`. It never
  fabricates the missing second conjunct — it just doesn't claim a
  sentence-level structure it only partially recognized. This is the
  safe direction to err in, but it does mean `logical_composition` on
  a `Qualification` answers "how does *this extracted claim* compose"
  rather than "how does the *source sentence* compose," and a consumer
  must not conflate the two.

Decline-reason distribution across all 161 controls: **147 of 147
declines were `no_competency_language`** — the other three wired-in
decline reasons (`negation`, `narrative_cue`, `responsibility_lead`)
never fired on this corpus. This is itself a diagnostic-granularity
limitation worth naming: the overwhelming majority of real declines
give no finer-grained reason than "nothing matched," which makes it
hard to distinguish "this is genuinely not a competency claim" from
"this is a competency claim phrased in a way the gate doesn't cover" —
exactly the ambiguity Category B's root-cause analysis above had to
resolve by hand.

**Domain-leak trap cases** (8 controls the annotator specifically
designed to test whether competency-sounding vocabulary sitting under a
Responsibilities/narrative heading gets wrongly promoted): **0/8 false
positives on either path.** 7 of the 8 are genuine non-qualifications
and both paths correctly declined to treat them as requirements; the
8th (`m11g5-p18-14`) is a genuine qualification missed by both paths —
already counted in Category A, not a leak.

## 6. Category D — combined interpretation (Phase 4D)

| | Value |
|---|---|
| Unique genuine qualifications recognized by candidate | 135 (identical set to Path A — see §3) |
| Contradictory relationship (A and B disagree on necessity for the same span) | **0 / 161** |
| Competency found but projection declined (lost between extraction and `project_qualification`) | **0** |
| Duplicate outputs | 0 by construction (reconciliation keys on exact span; no two comparisons ever share one) |

The one true near-duplicate *content* case in the corpus — the same
ARM/C/C++/Python/Go/Rust technology list appearing once under a
Responsibilities heading (`m11g5-p05-resp1`) and once under
Qualifications (`m11g5-p05-04`) — is preserved as **two distinct
recognized claims**, not merged. This is disclosed as a scope boundary
(cross-section claim-merging was never attempted; an evaluation-only
harness has no mandate to invent one) rather than a defect:
score-eligibility is not at stake here since nothing from Path B ever
reaches live scoring.

## 7. Comparison against M11-D/M11-F (Phase 5)

| Question | Answer |
|---|---|
| Does candidate coverage improve over parser v10? | **No** — identical recall (94.41%) and identical false-positive count (0/18) on this corpus. G4's recovery pass added zero claims. |
| Which categories improve? | None at the recognition level. At the tag level, Path A has no tagging capability at all, so the candidate's 5/40 tags (85.7% precision) are a genuine net-new signal — just a sparse one. |
| Which genuine qualifications remain missing? | The same 8 as Path A: 7 from the `p03` SKIP-heading collision, 1 from benign dedup. |
| Does false-qualification count increase? | No — 0/18 on both paths; 0/8 domain-leak false positives confirmed directly. |
| Does necessity or grouping accuracy deteriorate? | Necessity: no (100% agreement where checked). Grouping: one real N-of-M gap newly *discovered* by this corpus's deliberate stress test — not a regression, since no prior corpus tested this shape. |
| Does any improvement depend on known corpus wording? | **Yes, decisively.** 12.5% tag recall here closely tracks M11-F's independently-measured 16.2% on a different corpus — both far below the 100% this pathway achieves on its own M11-E development data. Three non-overlapping corpora now agree on a 12–16% real-world ceiling. |
| Does reconciliation create duplicate or contradictory claims? | No contradictions (0/161). One disclosed, scope-bounded non-merge of a true cross-section near-duplicate — not a defect. |

This is the same qualitative verdict M11-F reached independently, now
reconfirmed on a *third*, non-overlapping corpus collected after G1-G4
landed: **the G1-G4 lineage's measured improvements do not transfer to
genuinely new wording.**

## 8. Product readiness assessment (Phase 6)

| Option | Verdict |
|---|---|
| 1. Continued offline development only | **Appropriate — stay here.** |
| 2. Offline shadow reporting | Not justified. At 12.5% recall, absence of a tag is overwhelmingly the dominant output, not a meaningful signal distinct from "nothing to report" — a shadow log would be mostly blank with little diagnostic value beyond what this evaluation already captured. |
| 3. Limited user-visible, non-scoreable qualification reporting | **Not ready.** Checklist: sound classification — fails at 12.5% recall; most genuine competencies simply would not surface, and for a recruiter-facing display, a missing tag reads as "lacks X" by omission even when honestly labeled "not detected" — the "fake precision" the UX direction explicitly bans. |
| 4. Full live integration | Not ready, by a wide margin; also explicitly out of scope for this milestone. |

**On the specific blocking-semantic-contract question this milestone's
instructions asked to check explicitly** ("if the architecture cannot
distinguish responsibilities from recognized-but-unassessable
qualifications, identify that as blocking"): **checked directly, not
found.** Zero domain-leak false positives across 8 deliberately
designed trap cases, and zero false-requirement promotions across all
18 non-qualification controls — the existing distinction between
"responsibility/narrative" and "genuine but non-assessable requirement"
(e.g. `m11g5-p09-04`, US-citizenship, correctly `REQUIRED` +
`NOT_OBSERVABLE`, correctly never conflated with a safe decline) holds
on this corpus.

**The two blockers this milestone actually found:**

1. **`_QUALIFYING_INTENT_V2`'s recall ceiling** (12–16% across three
   independent corpora) — a stable, now triple-confirmed structural
   limit of the current alias+intent-gate design, not a corpus-specific
   artifact.
2. **The `"who we are"` SKIP-heading false positive in live
   `segmentation.py`** — a Path A (production) defect, pre-existing,
   unrelated to the competency pathway, responsible for 7 of this
   corpus's 8 total missed qualifications.

## 9. Historical regression results (Phase 7)

- Full backend suite: **1493 passed, 13 skipped** (1485 baseline + 8 new
  G5 tests; 0 regressions; skip count unchanged).
- Focused G5 tests (`tests/test_m11g5_independent_validation.py`): 8/8
  passed — gold-hash freeze integrity, source-hash integrity, valid
  named reconciliation relationships, reconciliation determinism, and
  the two characterization tests pinning the SKIP-heading finding.
- G4 admission recovery, G3 end-to-end integration, G2 section context,
  G1 alternative safety, M11-C/E evaluations, M11-B compatibility, M10A–
  M10E, M9B, and the frozen 8c:v1/v1.1 checks are all included in the
  same full-suite run above and passed unchanged.
- `git status --short` shows **zero modified tracked files** throughout
  this milestone — only new, untracked files were added (this doc, the
  new metrics script, the new test file, and the regenerated
  `evaluation/reports/m11g5_phase4_metrics.json`).

## 10. Remaining architectural blockers

See §8: (1) the intent-gate recall ceiling, now reconfirmed on a third
corpus; (2) the `"who we are"` SKIP false positive in live
`segmentation.py`. Neither was touched — both are reported, not fixed,
per this milestone's instructions.

## 11. Production-readiness verdict

**Not ready for any user-visible or scoring-integrated use.** Continued
offline development only (Option 1). This is not a new conclusion — it
is the same conclusion M11-F already reached, now independently
reconfirmed on fresh, non-overlapping data collected after four
additional milestones (G1-G4) of targeted fixes. Those fixes measurably
helped the specific wording patterns they were built against
(confirmed by this project's own prior docs) but contributed **zero**
measurable improvement on this new corpus.

## 12. Recommended next smallest milestone

Fix the `"who we are"` SKIP-heading false positive in
`_NON_QUALIFICATION_ROOT` (`segmentation.py`) — a narrow, low-risk,
high-confidence regex fix (distinguish "Who We Are" as a bare/trailing
phrase from "Who We Are Looking For"/"Who You Are" candidate-profile
headings) with a directly measured impact: it alone accounts for 7 of
this corpus's 8 missed qualifications, affecting an entire real
posting's entire requirements section. This is smaller, safer, and
higher-confidence than attempting to widen `_QUALIFYING_INTENT_V2`,
which would trade recall against the precision it was specifically
added to protect and would need its own fresh, held-out corpus to
validate without tuning against this one.

## 13. Commit-readiness verdict

**Not committed, per instructions.** New files produced this pass
(all evaluation-only, non-production):

- `docs/evaluation/MILESTONE_11_G5_FULL_PIPELINE_VALIDATION.md` (this doc)
- `scripts/evaluation_lib/m11g5_phase4_metrics.py`
- `evaluation/reports/m11g5_phase4_metrics.json`
- `tests/test_m11g5_independent_validation.py`

Plus the pre-existing, already-local `evaluation/m11g5/*` corpus,
provenance, hash-freeze, annotation, and Phase 1/Phase 4 harness files
this pass verified rather than regenerated from scratch (all untracked,
all local-only by design — no restricted posting text is reproduced in
any of the four files listed above). If the user wants any of this
committed, that is their call to make explicitly.
