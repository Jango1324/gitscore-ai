# Milestone 9A — Lossless Job Requirement Parsing

**Status: implemented.** Fixes the M8E-identified high-severity bug
("Entire requirement bullets vanish with zero structural trace when
their only concept is unregistered" — `MILESTONE_8E_CONSOLIDATED_EVALUATION.md`
§8, issue #1). No scoring formula, matcher semantics, API contract, or
concept-registry *resolution* logic changed. `JobRequirement`'s shape is
unchanged (no new field; `category` gains one new, documented string
value). `JOB_REQUIREMENT_SCHEMA_VERSION` stays `2`.
`JOB_DESCRIPTION_PARSER_VERSION` bumps `v3 -> v4` (output changes on
identical input).

---

## 1. Baseline

| Check | Result |
|---|---|
| HEAD at start | `9c53b3d` ("test: add consolidated end-to-end evaluation" — M8E) |
| Working tree | clean |
| `python -m pytest` | 864 passed, 0 failed (matches M8E's recorded baseline exactly) |
| `JOB_DESCRIPTION_PARSER_VERSION` | `job_description_parser:v3` -> `v4` |
| `JOB_REQUIREMENT_SCHEMA_VERSION` | `2` (unchanged) |
| `MATCHER_VERSION` / `SCORING_VERSION` | unchanged |

---

## 2. Root cause (Phase 1)

Traced both M8E examples through `segment_description()` ->
`classify_alternative_claim()` -> the per-claim detector chain in
`_requirements_from_claim()`. Both claims correctly survive
segmentation (they are judged requirement-shaped) — the drop happens
entirely inside `_requirements_from_claim`, which returned `[]` when
**all** of the following held:

1. `classify_alternative_claim` returned `"not_technical"` for an
   OR-list whenever **zero** segments resolved to a *real* (non-
   `unresolved:`) concept (`any_confirmed=False`). The per-segment
   `unresolved:<term>` ids it computed internally were **discarded**,
   never reaching the caller.
2. `find_concept_mentions` / the bare-short-alias fallback found no
   real concept anywhere in the claim.
3. `find_conservative_unknown_terms` (the comma-gated unresolved-term
   promoter) required a non-empty **confirmed** `mentions` before even
   looking at the comma list — with zero confirmed mentions it returned
   `()` immediately, regardless of whether the comma-separated items
   were obviously named technologies.
4. No numeric years qualifier, no non-technical phrase-table match.

When 1–4 all held, the claim contributed **zero** rows to
`JobRequirementProfile.requirements` — no row, no span, no
`unresolved:<term>` placeholder, nothing.

### 2.1 Generalization across the cases Phase 1 asked about

| Case | Pre-9A outcome | Mechanism |
|---|---|---|
| Unknown single technology, no list (`"Experience with dbt"`) | **Silent drop** | No extraction path existed at all for a bare, unlisted term. |
| Unknown technical OR-group (`"Vue or Angular"`, `"Snowflake or BigQuery"`, `"MATLAB or Simulink"`) | **Silent drop** | `any_confirmed=False` gate in (1). |
| Unknown technical AND-list (`"SPI, I2C, and UART"`) | **Silent drop** | comma-gate in (3) required a confirmed sibling that didn't exist. |
| Recognized + unresolved combination (`"React, Vue, and SomeLib"`) | **Already worked** | the one case with a confirmed sibling (React) already unlocking (3) — untouched by this milestone. |
| Embedded-systems requirements | **Silent drop** | same mechanism as the AND-list case. |
| Technical requirement with no technology name at all (`"control systems or state estimation"`, `"experience designing distributed systems"`) | **Silent drop**, and the **hardest** case | there is no single term to preserve — the whole phrase is the content. Partially addressed (see §4); a known residual gap remains (§7). |

### 2.2 Gold already encoded the intended fix for the list/OR cases

`evaluation/gold/jobs/frontend_01.json` and `embedded_firmware_01.json`
(frozen, pre-9A) already specify, as their "ideal" expected rows:

- `"Knowledge of Vue or Angular"` -> `facet=alternative,
  alternative_concept_ids=[unresolved:angular, unresolved:vue]`
- `"...SPI, I2C, and UART"` -> three separate `facet=technical` rows,
  `concept_id` = `unresolved:spi` / `unresolved:i2c` / `unresolved:uart`

but **not** for `"Bachelor's degree ... or a related field"` (stays
`category=education`) or `"control systems or state estimation"`
(stays non-technical/`other`) — even though both of the latter also
contain "or" and pass the existing length/stopword shape check
(`clean_list_fragment`). The only reliable signal separating
`Vue`/`MATLAB`/`SPI`/`I2C` from `control systems`/`a related field` is
**capitalization/acronym shape**, which nothing in the codebase checked
before this milestone.

---

## 3. Domain-model decision (Phase 2)

Presented to the user as an explicit STOP-point (per the milestone
brief) with three options; **the hybrid design was approved and
implemented.**

### Piece 1 — gold-aligned unresolved-concept minting (loosens two existing gates, narrowly)

New shared shape helper,
`gitscore.jobs.parsing.concepts.looks_like_specific_technology_name(term)`:
true iff every whitespace-separated word starts with an uppercase
letter (covers `Vue`, `Angular`, `MATLAB`, `Simulink`, `Snowflake`,
`BigQuery`, `SPI`, `I2C`, `UART`, `PLC`) **and** the term does not end
in a possessive `'s` (excludes `Bachelor's`/`Master's` — capitalized,
but never a technology name in this domain). Shape only, never
meaning — no vocabulary list.

Used to:

- Let `classify_alternative_claim` (`alternatives.py`) treat an
  OR-list as technical even with **zero** real confirmed concepts,
  provided every segment's resolved term (real-or-`unresolved:`)
  passes the shape check. Reproduces gold's `Vue`/`Angular`,
  `Snowflake`/`BigQuery`, `MATLAB`/`Simulink` expectations exactly.
- Add a new branch to `find_conservative_unknown_terms`
  (`concepts.py`) that fires when there is **no** confirmed sibling,
  but the claim has a comma **and** an explicit enumeration cue
  (`"such as"`, `"including"`, `"like"`, `"e.g."`, `"for example"`),
  extracting shape-passing fragments **starting right after the cue**
  (not from position 0 — see §3.2). Reproduces gold's
  `SPI`/`I2C`/`UART` expectation exactly. The existing sibling-confirmed
  branch (`mentions` non-empty) is **completely unchanged**.

### Piece 2 — a new, honest "unresolved, not fabricated" placeholder

A new `category="unresolved_requirement"`
(`concept_id=None`, `GithubObservability.PARTIALLY_OBSERVABLE`,
`ParserConfidence.LOW` — mirroring the existing `alternative_requirement`
precedent exactly; **no schema/shape change**). Fires only as a last
resort, inside `_requirements_from_claim`, when a claim has one of
three narrow structural signals **and** every other detector (including
Piece 1) produced nothing:

1. An explicit alternative marker ("Vue or Angular", "control systems
   or state estimation").
2. A comma list introduced by an enumeration cue ("...peripherals such
   as SPI, I2C, and UART").
3. A single bare claim led by a narrow, unambiguous technical lead-in
   phrase (`"experience with"`, `"knowledge of"`, `"familiarity with"`,
   `"proficiency in"`, `"proficient in"`, `"expert in"` — deliberately
   **not** the full, much weaker `_LIST_ITEM_PREFIXES` table used for
   stripping an already-confirmed list item, which includes bare
   fillers like `"with"`/`"strong"`/`"solid"` that would wrongly match
   `"Strong communication"`), with a short, non-generic remainder.

This guarantees invariant 1 (never silently vanish) without ever
inventing a concept id — `concept_id=None` forces
`MatchStatus.NOT_ASSESSABLE` in `matching.engine.match_requirement`
**regardless of `github_observability`**, so it can never be scored
`SUPPORTED` (invariant 3, by construction, not by new matcher logic —
the matcher is unchanged).

### 3.1 A false positive caught and fixed during implementation

Initial implementation let `classify_alternative_claim`'s all-unresolved
rescue path use `leading_token()` (grab the segment's first word) when
`clean_list_fragment` failed on an over-long segment — this is exactly
how `"Simulink"` gets rescued from `"Simulink for controls simulation"`.
But the very same mechanism, applied to the **first** OR-segment of a
claim, promoted `"Security certification such as OSCP or CISSP"` into a
fabricated `unresolved:security` + `unresolved:cissp` alternative group:
`"Security"` is capitalized *only* because it starts the sentence
(ordinary English grammar), not because it names a product — exactly
the same ambiguity the possessive-`'s` exclusion already guards against
for `"Bachelor's"`/`"Master's"`, but for a *different* capitalization
artifact. **Fix:** the `leading_token`-sourced shape rescue is now only
trusted for a **non-first** OR-segment (`index > 0`) — a word
immediately following an `"or"`/comma is not subject to sentence-initial
capitalization, so genuine capitalization there remains a real signal.
Confirmed fixed and covered by a regression test
(`test_sentence_initial_capitalization_does_not_fabricate_a_concept`).

### 3.2 Why the comma-enumeration extraction slices from *after* the cue

A naive comma-split starting at position 0 loses the **first** list item
whenever it's preceded by a long lead-in clause: for
`"...peripherals such as SPI, I2C, and UART"`, the fragment before the
first comma is `"Familiarity with microcontroller peripherals such as
SPI"` — 6 words, fails the `<=3-word` shape check, so `"SPI"` would be
lost even though `"I2C"`/`"UART"` survive. This is a known, pre-existing
limitation of the *sibling-confirmed* branch too (unaffected, out of
scope here) — but for the new no-sibling branch, slicing the search to
start right after the enumeration cue's own end position sidesteps it
entirely, since everything "SPI, I2C, and UART" without the lead-in
clause fits the shape check cleanly.

---

## 4. Evaluation design (Phase 3)

New, implementation-independent gold examples:
`tests/test_job_requirement_preservation.py` (12 cases, written with
expected outcomes stated first). Covers every category the brief asked
for: recognized single requirement; unknown single technical
requirement; unknown technical OR-group; unknown technical AND-list;
mixed known/unknown combination (regression control); nontechnical
professional-experience requirement (regression control); ordinary
prose that must *not* become a requirement (false-positive control,
two variants); both real M8E examples; the degree-or-related-field
regression control; and the sentence-initial-capitalization false
positive from §3.1.

The pre-existing frozen gold corpora (`evaluation/gold/jobs/`,
`evaluation/gold_v1_1/jobs/`) were **not modified** — per the brief's
explicit instruction not to rewrite frozen gold to fit the
implementation — and were re-run via the existing
`scripts/evaluate_job_parser.py` harness to measure real-world impact
(§5).

---

## 5. Results

### 5.1 Before / after, both unit test examples

```python
>>> parse_job_description("Preferred Qualifications:\n- Knowledge of Vue or Angular\n").requirements
# before: ()
# after:  (JobRequirement(alternative_concept_ids=('unresolved:angular', 'unresolved:vue'),
#                          github_observability=STRONGLY_OBSERVABLE, necessity=PREFERRED, ...),)

>>> parse_job_description("Requirements:\n- Familiarity with microcontroller peripherals such as SPI, I2C, and UART\n").requirements
# before: ()
# after:  3 rows, concept_id in {unresolved:spi, unresolved:i2c, unresolved:uart}
```

### 5.2 `scripts/evaluate_job_parser.py` (frozen gold, unmodified)

| Corpus | Metric | Before | After |
|---|---|---|---|
| `8c:v1` | Recall | 0.563 | **0.621** |
| `8c:v1` | Precision | 0.892 | 0.771 |
| `8c:v1` | CORRECT / MISSING | 58 / 44 | 64 / 38 |
| `8c:v1.1` | Recall | 0.641 | **0.699** |
| `8c:v1.1` | Precision | 1.0 | 0.857 |
| `8c:v1.1` | CORRECT / MISSING | 66 / 37 | 72 / 31 |

Recall improved on both corpora (+6 `CORRECT` rows each — exactly the
`Vue`/`Angular`/`SPI`/`I2C`/`UART`/`MATLAB`/`Simulink`/`Snowflake`/
`BigQuery` family gold already anticipated). Precision dropped because
the evaluator's strict claim-text join counts every actual row with
**no corresponding gold row at all** as spurious — and gold, built
against the old silently-dropping parser, never annotated sentences
that previously produced zero rows. **Every one of the 12 newly
"spurious" rows was manually inspected; all 12 carry
`concept_id=None, category='unresolved_requirement'`** (the non-
fabricating Piece 2 placeholder) — none invent a technology. The 7
pre-existing spurious rows (`infra.kubernetes`, `language.sql`,
`language.swift`, `language.kotlin` matches with no gold counterpart)
are unrelated to this milestone and present in both before/after runs.
**This is a measurement-methodology artifact of a frozen,
pre-9A-authored gold corpus, not a correctness regression** — see §7
for the explicit recommendation to extend the gold corpus with
negative/positive rows for this exact case rather than treat this
precision number as a real quality drop.

### 5.3 Regression checks

- `python -m pytest`: **876 passed** (864 pre-existing + 12 new), 0
  failed. One pre-existing test
  (`tests/test_job_parser.py::test_manual_validation_robotics`) pinned
  the *old* silent-drop behavior as an explicitly-commented "known,
  documented limitation" for `"control systems or robotics"` — updated
  to assert the new, correct preservation behavior instead (not a gold
  rewrite; this was a unit test describing the exact bug this milestone
  fixes).
- `scripts/evaluate_evidence.py`, `scripts/evaluate_repository_retrieval.py`:
  unchanged (false positives=1, retrieval recovered=2/missed=2/
  false_positive=0 — identical to M8E's recorded baseline; these layers
  don't touch job parsing).
- `scripts/evaluate_end_to_end.py`: re-run fresh against **both**
  pre-9A and post-9A code (isolating 9A's effect from the already-
  disclosed, pre-existing M8D.3 staleness in the committed report file
  — same methodology M8E's own job-aware comparison script used).
  Pre-9A fresh: `karpathy×frontend_01` required `(3,4)`, preferred
  `(0,1)`. Post-9A: required **unchanged** at `(3,4)`; preferred becomes
  `(0,2)` — the Vue/Angular requirement is now a real, assessable
  (`NOT_OBSERVED`) row instead of invisible. No required/preferred
  tier's *supported* count changed anywhere in the 12-pair matrix;
  every change is additive (new `NOT_OBSERVED`/`NOT_ASSESSABLE` rows
  becoming visible), never a flip of a previously-`SUPPORTED` row.

---

## 6. Invariant-by-invariant check

| # | Invariant | Status |
|---|---|---|
| 1 | A meaningful requirement must not silently disappear | **Improved** — both M8E examples and the general OR/AND-list/bare-term cases now preserved; one narrow residual gap remains (§7). |
| 2 | The parser must not invent technical capabilities | **Held** — Piece 1 only mints `unresolved:<term>` for shape-confirmed, structurally-enumerated items (never a vocabulary guess); Piece 2 never attaches a `concept_id` at all. The one false positive found during implementation (§3.1) was fixed before shipping. |
| 3 | Unparsed/ambiguous requirements must not be counted SUPPORTED | **Held, by construction** — `concept_id=None` forces `NOT_ASSESSABLE` in the (unchanged) matcher; a minted `unresolved:<term>` can only become `SUPPORTED` if the candidate's own evidence extraction independently produces the identical id (the same pre-existing, already-reviewed Milestone 5C guarantee every other `unresolved:<term>` concept already relies on). |
| 4 | Absence of GitHub evidence must not imply absence of candidate skill | **Held** — unchanged; `MatchStatus`'s own semantics were never touched. |
| 5 | A potentially-assessable but unparsed requirement must not disappear from the denominator without a visible limitation | **Improved** — confirmed directly in §5.3's end-to-end re-run: previously-invisible requirements are now visible `NOT_OBSERVED`/`NOT_ASSESSABLE` rows, correctly shrinking `alignment_score` where the gap is real (e.g. `torvalds×embedded_firmware_01` drops because SPI/I2C/UART are now honestly assessed as not observed) rather than hiding it. |
| 6 | Existing correctly parsed requirements must retain their meaning | **Held** — both new code paths are strictly additive to claims that previously produced zero rows (Piece 2) or where `any_confirmed` was already `False` (Piece 1); every claim that already produced >=1 row under the pre-9A parser is untouched. Confirmed by the full regression suite + the one unit test update, which corrected a test pinning the OLD bug, not new behavior. |
| 7 | Requirement preservation must not turn every heading/intro sentence into a requirement | **Held** — the three structural triggers (§3, Piece 2) are narrow and were stress-tested against ordinary prose (`"Write clean, maintainable, and well-tested code"`, `"Strong communication"`, skip-section benefits prose) — none trigger the new fallback. Headings themselves are already consumed by segmentation before reaching this code at all. |

---

## 7. Remaining limitations (disclosed, not silently left)

- **A technical-sounding requirement with no named technology at all
  and no qualifying lead-in phrase** (e.g. `"Experience designing
  distributed systems"`) still produces no placeholder — catching it
  would require a much broader heuristic (scanning for arbitrary
  technical-sounding nouns) the milestone brief explicitly warns
  against ("do not assume all unknown technical requirements can be
  safely resolved", "no blanket vocabulary expansion"). Recommended for
  9B as a separate, explicitly-scoped design question, not silently
  bundled into this fix.
- **Lowercase-styled product names in a list context** (hypothetically
  `"graphql, grpc, and rest"` all-lowercase) fail the proper-noun shape
  check and fall to the generic Piece 2 placeholder rather than minting
  a clean `unresolved:<term>` — intentionally conservative.
- **A single bare unknown term combined with a numeric experience
  qualifier in the same sentence** (e.g. `"3+ years experience with
  dbt"`) still only produces the experience-category row; the lead-in
  check (Piece 2, branch 3) requires the claim to *start* with the
  lead-in phrase, which `"3+ years..."` does not. Narrower than the
  plain `"Experience with dbt"` case; disclosed, not fixed here.
- **Evaluation harness precision metric** (§5.2) conflates "parser
  invented something wrong" with "parser now surfaces a previously-
  invisible claim gold never covered." Recommend 9B deliberately add a
  small number of new gold rows/negative controls for this exact
  preservation behavior (not rewriting any existing frozen row) so
  precision reflects genuine quality rather than corpus-coverage
  staleness.

---

## 8. Files and versions changed

| File | Change |
|---|---|
| `src/gitscore/jobs/parsing/concepts.py` | New `looks_like_specific_technology_name()`, `contains_enumeration_cue()`, `_split_list_terms()`/`_append_clean_term()`; `find_conservative_unknown_terms()` gained the new no-sibling, cue-gated branch (sibling-confirmed branch unchanged). |
| `src/gitscore/jobs/parsing/alternatives.py` | `classify_alternative_claim()` loosened to accept an all-unresolved, shape-confirmed OR-list as technical; new `_shaped_term()` helper with the first-segment `leading_token` restriction (§3.1). |
| `src/gitscore/jobs/parsing/observability.py` | New `"unresolved_requirement"` -> `PARTIALLY_OBSERVABLE` table entry. |
| `src/gitscore/jobs/parsing/confidence.py` | New `"unresolved_requirement_fallback"` -> `LOW` confidence kind. |
| `src/gitscore/jobs/parsing/parser.py` | New last-resort placeholder fallback in `_requirements_from_claim`; `JOB_DESCRIPTION_PARSER_VERSION` `v3 -> v4`. |
| `tests/test_job_parser.py` | Updated one pre-existing test that pinned the old silent-drop bug as a documented limitation. |
| `tests/test_job_requirement_preservation.py` | New — 12 Phase-3 gold examples. |
| `evaluation/reports/parser_report*.{json,md}` | Regenerated (reflects the real recall/precision change in §5.2). |
| `docs/evaluation/MILESTONE_9A_REQUIREMENT_PRESERVATION.md` | This document. |

No change to: `jobs/models.py`, `jobs/profile.py`, `jobs/types.py`
(schema version unchanged), `matching/`, `assessment/`, `api/`,
`concepts/registry.py`'s resolution logic, the concept registry's
contents, or any scoring/ranking/retrieval module.
