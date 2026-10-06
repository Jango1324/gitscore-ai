# Milestone 8D.1 — Registry Expansion & Parser-Precision Fixes

Implements the top-ranked, highest-value fixes recommended (not
implemented) by `docs/evaluation/MILESTONE_8C_EVALUATION.md`, which
measured the real pipeline as Milestone 8B left it. Full as-built
writeup: `docs/ARCHITECTURE.md` §25. This document is the evaluation
record — the corpus correction rationale and the before/after benchmark
numbers — referenced from there and from `docs/CHANGELOG_DEV.md`.

**Not production code itself** — `evaluation/` is never imported by
`src/gitscore/`. This document explains what changed in `src/gitscore/`
only insofar as it's needed to justify the evaluation-corpus correction
below.

## 1. What changed in production code (summary; §25 has the full detail)

- `concepts/registry.py`: `CONCEPT_REGISTRY_VERSION` 3 → 4. Five new
  concepts: `infra.kubernetes`, `language.sql`, `language.swift`,
  `language.kotlin`, `framework.react_native`. Pure additive data, zero
  logic change.
- `concepts/matching.py`: new `select_longest_overlapping_matches()` —
  generic "most-specific alias wins" conflict resolver, fixing the
  "React Native" → `framework.react` collision structurally (not a
  per-concept special case).
- `jobs/parsing/concepts.py`: `find_concept_mentions()` now runs matches
  through the resolver above; new `find_bare_short_alias_mentions()` — a
  narrow, case-sensitive, context-gated last-resort fallback for
  `language.c` (the only concept with no `readme_safe_aliases()` at
  all), fixing the "Strong C experience" zero-requirements bug.
- `jobs/parsing/alternatives.py` / `concepts.py`: three OR-group
  trailing-word/prefix-stripping fixes (`_TRAILING_FILLER` gains
  "programming"; new `leading_token()` escalation step; `_LIST_ITEM_PREFIXES`
  gains skill-level descriptors like "expert-level"/"strong"/"proficient in").
- `evidence/extraction/readme.py`: adopts the same overlap resolver.
  `EXTRACTOR_VERSION` `v2` → `v3`.
- `jobs/parsing/parser.py`: `JOB_DESCRIPTION_PARSER_VERSION` `v2` → `v3`.
- `jobs/parsing/confidence.py`: new `"bare_short_alias_context"` →
  MEDIUM confidence kind.

None of this touches `JobRequirement`/`Evidence`'s shape, the matcher,
or the assessment formula — `JOB_REQUIREMENT_SCHEMA_VERSION`,
`EVIDENCE_SCHEMA_VERSION`, `MATCHER_VERSION`, `SCORING_VERSION` are all
unchanged.

## 2. Parser benchmark: A/B/C comparison

All three runs use `scripts/evaluate_job_parser.py` against the same 15
synthetic job postings (`evaluation/jobs/`), 103 expected requirements.

| Run | Code | Gold | Correct | Missing | Wrong-alt-structure | Recall | Precision |
|---|---|---|---|---|---|---|---|
| A | pre-8D.1 (historical) | `8c:v1` (frozen) | 54 | 45 | 4 | 0.524 | 1.000 |
| B | 8D.1 | `8c:v1` (frozen) | 58 | 44 | 1 | 0.563 | 0.892 |
| C | 8D.1 | `8c:v1.1` (corrected) | 66 | 37 | 0 | 0.641 | 1.000 |

**A → B** (same frozen gold, before/after code): +4 correct, −1
wrong-alt-structure. This is the real, gold-independent improvement:
§25.2 (React Native collision) fixes 1 wrong-alt-structure case, §25.3
(bare-C) fixes 1 missing case (`torvalds`/`embedded_firmware_01`), §25.4
(OR-group trailing/prefix fixes) fixes the other 2 wrong-alt-structure
cases. Precision *drops* 1.000 → 0.892 — **entirely** because 7 of
`8c:v1`'s rows now disagree with the parser on a premise that 8D.1
intentionally invalidated ("X is not in the registry"), not because of
any new genuine parser false positive. `parser_report.md`'s own
"Spurious requirements: 7" list is exactly those 7 rows (§3 below).

**B → C** (same 8D.1 code, frozen vs. corrected gold): +8 correct, −1
missing... precision restored to 1.000, recall 0.563 → 0.641. This
isolates the stale-gold effect from B: once the gold's premise is
updated to match the registry 8D.1 actually shipped, every one of
those "spurious" rows becomes a genuine CORRECT verdict and zero new
problems are introduced.

## 3. Parser gold correction (`evaluation/gold_v1_1/`)

`evaluation/gold/` (`8c:v1`) is **byte-for-byte unchanged** — every
historical number in `MILESTONE_8C_EVALUATION.md` remains exactly
reproducible by running the evaluator with no flag. `evaluation/gold_v1_1/`
is a full, separate parallel snapshot (all 15 job files, all 4 candidate
files, `matrix.json`), with `corpus_version: "8c:v1.1"` stamped
throughout. Only the rows below differ in *content* from `8c:v1`
(verified programmatically — see `scripts/evaluation_lib/loaders.py`'s
`GOLD_JOBS_DIR_V1_1`/`GOLD_CANDIDATES_DIR_V1_1`); every other row/file in
`gold_v1_1/` is `8c:v1`'s content with only `corpus_version` and
formatting changed.

**8 parser-gold rows across 6 job files**, all sharing the exact same
justification — a row whose sole stated premise was "concept X does not
exist in the registry," which Milestone 8D.1 made false by registering
that concept:

| Job file | Claim | Old concept_id / verdict premise | New concept_id |
|---|---|---|---|
| `backend_01` | "Familiarity with Docker and Kubernetes" | `unresolved:kubernetes`, predicted MISS (no comma, can't reach the unknown-term promotion path) | `infra.kubernetes` |
| `data_engineering_01` | "Strong SQL skills across relational databases" | no concept_id, `category=other`/`facet=non_technical`, predicted MISS | `language.sql` |
| `data_science_01` | "Proficiency in SQL for data analysis" | same shape as above | `language.sql` |
| `devops_cloud_01` | "Strong experience with Docker and Kubernetes" | `unresolved:kubernetes`, predicted MISS | `infra.kubernetes` |
| `mobile_01` | "Strong experience with Swift for iOS development" | no concept_id, `not_observable`/`non_technical`, predicted MISS | `language.swift` |
| `mobile_01` | "Experience with Kotlin for Android development" | no concept_id, `not_observable`/`non_technical`, predicted MISS | `language.kotlin` |
| `mobile_01` | "Experience with React Native or Flutter" (OR group) | `alternative_concept_ids=[unresolved:flutter, unresolved:react_native]` — documented in 8C §10 as actually resolving to a WRONG `framework.react` false positive | `alternative_concept_ids=[framework.react_native, unresolved:flutter]` |
| `sre_platform_01` | "Experience with Kubernetes for container orchestration" | no concept_id, `category=other`/`non_technical`, predicted MISS | `infra.kubernetes` |

Every row's `notes` field in `gold_v1_1/` carries a `8c:v1.1 CORRECTION`
block recording the exact old value, new value, and why the old premise
is stale — not just a silent edit. This is **all** of the content
difference in the 6 parser-gold files; `Flutter` deliberately stays
`unresolved:flutter` in the mobile_01 OR-group row (not registered in
8D.1, out of scope).

**1 candidate evidence-gold row, 1 file** — see §4.

**Total: 9 rows across 7 files.** No other row in any of the 15
job-gold files or 4 candidate-gold files changed in content.
`matrix.json` is semantically identical between `8c:v1` and `8c:v1.1`
(confirmed programmatically — no row added/removed/reordered).

## 4. Evidence benchmark correction — `sindresorhus/Gifski`

**The issue:** regenerating `evidence_report.json/md` (frozen `8c:v1`
gold, 8D.1 code) changed "False positives: 1 → 2," adding
`sindresorhus/Gifski → unexpectedly found 'language.swift'`.

**Audit:** the `8c:v1` gold row for `Gifski` stated its *entire*
justification as:

> "Chosen specifically because Swift is NOT in the concept registry at
> all — this is a CONCEPT_REGISTRY_GAP check, not an extraction-bug
> check." ... "no such concept exists in the registry — Swift evidence
> is structurally impossible to produce today, regardless of extractor
> correctness."

This premise is now false: 8D.1 registered `language.swift`. Per the
task's own ground rule — **do not suppress valid Swift evidence, do not
weaken production extraction to satisfy stale evaluation gold** —
the correct fix is the gold annotation, not the extractor.
`evidence/extraction/languages.py` was NOT touched for this; it already
resolved every GitHub-reported language name through the full concept
registry (`resolve_concept()`), so Gifski's pre-existing 85.5%-Swift
language stats resolve to real `language.swift` evidence automatically,
with zero extractor changes. This is a genuine, intentional,
newly-unlocked evidence-extraction result, not a bug and not a parser
change.

**Correction applied** (`evaluation/gold_v1_1/candidates/sindresorhus.json`,
`Gifski` target):

| Field | Old (`8c:v1`) | New (`8c:v1.1`) |
|---|---|---|
| `expected_concepts` | `[]` | `[{concept_id: language.swift, source: language_stats}]` |
| `not_expected_concepts` | `[{concept_id: language.swift, notes: "structurally impossible..."}]` | `[]` |
| `scope_limitations_observed` | `[{source: language_stats, classification: KNOWN_SCOPE_LIMITATION, notes: "Swift has no TechnicalConcept entry"}]` | `[]` |

**Result** (`scripts/evaluate_evidence.py --corpus-version 8c:v1.1`,
`evidence_report_v1_1.md`): concept checks 9 → 10 (found=10, missing=0),
**false positives back to 1** — the only false positive remaining is
`karpathy/llm.c → language.cpp`, which is unrelated to this milestone
(a pre-existing README-over-attribution issue, present in both `8c:v1`
and `8c:v1.1`, not introduced or fixed by 8D.1 — see §25.7 of
`docs/ARCHITECTURE.md` and §5 below). It remains visible and uncorrected
by design: it is a genuine extraction-accuracy issue, not a stale-gold
artifact, and correcting gold annotations to hide a real finding would
violate this milestone's own audit rule.

The frozen `evidence_report.json/md` (no `--corpus-version` flag) is
**not** rewritten to hide the 2-false-positive result — it continues to
correctly show the frozen `8c:v1` gold's now-stale expectation produces
a reportable false positive against 8D.1's code, exactly as the A/B
parser comparison's precision drop does. That report's own "False
positives" section is the historical artifact; this document and
`evidence_report_v1_1.md` are the corrected read.

## 5. Downstream end-to-end (E2E) consequences

Measured via `scripts/evaluate_end_to_end.py` (`end_to_end_report.md`),
no E2E code changed — these are consequences of the parser/registry
fixes flowing through unchanged matcher/assessment logic:

- **`torvalds` × `embedded_firmware_01`**: `alignment_score` 0 → 50,
  `required` `None` → `(1, 1)`. The single highest-value finding in the
  8C report ("a flat 0 for a real C expert, with 'required: None — no
  required requirements were assessable'") is directly resolved by the
  bare-C fix (§25.3) — the posting's "Strong C experience" claim is now
  a real, assessable `language.c` requirement, and `torvalds/linux`'s
  already-correct `language.c` evidence satisfies it.
- **`torvalds` × `data_science_01`**: `alignment_score` 25 → 20,
  `required` `(1, 3)` → `(1, 4)`. One more required requirement
  (`language.sql`, from the parser-gold correction's twin row) became
  real and assessable; `torvalds` doesn't satisfy it, so the score is
  correctly lower with more assessable required items — an intentional
  scoring change, not a regression.
- **`Jango1324` × `embedded_firmware_01`**: `alignment_score` unchanged
  (0), but `required` `None` → `(0, 1)` — the same bare-C requirement
  becomes assessable here too; `JPod-ESP32` is C++-dominant, not C, so
  it stays unmet, but the result is now a real, explained "0 of 1
  required" rather than "no required requirements were assessable."

No other row in `end_to_end_report.md` changed.

## 6. Remaining parser misses (37, against corrected `8c:v1.1`)

All genuine registry gaps, not extraction-bug or parser-structure
misses — the same backlog `MILESTONE_8C_EVALUATION.md` already
recommended batching into a future registry-expansion milestone rather
than fixing piecemeal: `bigquery`, `snowflake`, `spi`, `i2c`, `uart`,
`angular`, `vue`, `matlab`, `simulink`, plus others not in the
"most-missed" top list (Terraform, Jenkins, dbt, Flutter, PLC, OpenCV,
scikit-learn, GraphQL, OAuth, CMake, Azure/GCP, generic phrases like
"distributed systems"/"CI/CD"). None of these were in 8D.1's scope.

## 7. Genuine remaining false positive

`karpathy/llm.c → language.cpp` (evidence layer): a README-over-attribution
issue (the README credits a third party's separate C#/other-language
reimplementation) — unrelated to this milestone's registry/parser
changes, present before and after 8D.1, still LOW–MEDIUM severity, still
deferred pending its own design pass. Explicitly NOT touched here.

## 8. Corpus versioning mechanics

`scripts/evaluate_job_parser.py` and `scripts/evaluate_evidence.py` both
gained an optional `--corpus-version 8c:v1.1` flag (default: unchanged,
reads `8c:v1`). Passing it points at `evaluation/gold_v1_1/` instead and
writes to `*_report_v1_1.{json,md}` rather than overwriting the
`8c:v1` report files — every existing call with no flag reproduces the
exact, byte-for-byte-identical `8c:v1` report. `scripts/evaluation_lib/loaders.py`
exposes this via `GOLD_JOBS_DIR_V1_1`/`GOLD_CANDIDATES_DIR_V1_1` and
optional `gold_jobs_dir`/`gold_candidates_dir` parameters on the existing
loader functions (default unchanged).
