# Milestone 9B — Evaluation Integrity, Requirement Coverage & Retrieval-Sensitive Testing

**Status: evaluation only.** No production code under `src/gitscore/`
was modified. No concept registry, matcher, assessment formula,
ranking/retrieval behavior, API, or frontend was touched. No frozen
gold under `evaluation/gold/` (`8c:v1`) or `evaluation/gold_v1_1/`
(`8c:v1.1`) was modified, re-annotated, or regenerated. Everything this
milestone adds is additive and lives under `evaluation/m9b/`,
`scripts/evaluation_lib/`, new top-level `scripts/evaluate_m9b_*.py` /
`scripts/check_evaluation_staleness.py` entry points, and three new
`tests/test_m9b_*.py` files. Nothing has been committed or pushed.

---

## 1. Verified baseline (Phase 0)

| Check | Result |
|---|---|
| HEAD at start | `0235a1a` ("fix: preserve unresolved job requirements" — M9A) |
| Working tree | clean |
| `python -m pytest` | **876 passed**, 0 failed (matches the expected ~876 baseline exactly) |
| `JOB_DESCRIPTION_PARSER_VERSION` | `job_description_parser:v4` (unchanged by this milestone) |
| `JOB_REQUIREMENT_SCHEMA_VERSION` / `MATCHER_VERSION` / `SCORING_VERSION` / `CONCEPT_REGISTRY_VERSION` | unchanged |
| Python / pytest | 3.14 / 9.1.1 (same environment as M8E/M9A) |

Read before design work began: `docs/ARCHITECTURE.md` §§17–28 (job
domain model through M9A's requirement-preservation fix),
`docs/PIPELINE.md`'s V2/job-fit sections, `docs/CHANGELOG_DEV.md`,
`MILESTONE_8C_EVALUATION.md`, `MILESTONE_8D1_PARSER_IMPROVEMENTS.md`,
`MILESTONE_8D2_JOB_AWARE_RETRIEVAL.md`, `MILESTONE_8D3_EVIDENCE_ATTRIBUTION.md`,
`MILESTONE_8E_CONSOLIDATED_EVALUATION.md`,
`MILESTONE_9A_REQUIREMENT_PRESERVATION.md`, the existing harness
(`scripts/evaluation_lib/*.py`, `scripts/evaluate_*.py`), and the job
parser/matcher/assessment/retrieval source
(`jobs/parsing/{parser,concepts,alternatives}.py`,
`matching/engine.py`, `assessment/models.py`,
`ranking/job_relevance.py`, `application/job_fit.py`,
`concepts/registry.py`).

---

## 2. Corpus design and independent annotation method (Phase 1)

**New, additive corpus:** `evaluation/m9b/corpus.json` (`corpus_version:
"9b:v1"`), 30 entries. Does not touch `evaluation/gold/` or
`evaluation/gold_v1_1/`.

**Annotation policy (enforced, not just stated):** every entry declares
`is_requirement`, `is_technical`, `or_and_structure`, `ideal_outcome`,
and (where a degraded-but-honest outcome is distinguishable from a real
gap) `acceptable_fallback` — all written by reading the claim text alone
and reasoning about what a maximally-correct, non-fabricating parser
*should* produce. The real parser was run only **after** every entry's
annotation was finalized, as a separate evaluation step
(`scripts/evaluation_lib/preservation_eval.py::evaluate_entry`).
`tests/test_m9b_preservation_eval.py::test_every_entry_declares_its_annotation_independently_of_the_parser`
guards the corpus's own JSON against ever carrying a field that would
imply the opposite (e.g. `"actual_parser_output"`).

Each entry also documents where more than one annotation is defensible
(`ambiguity_notes`) rather than manufacturing false certainty — e.g.
m9b-013 (`"Python, Rust, or an equally performant systems language"`)
records that collapsing to the conservative placeholder is the
*correct* choice here, not a loss, because building a two-of-three
alternative group would misrepresent what the posting actually offered.

**Coverage** (all categories the milestone brief named, confirmed by
`test_corpus_covers_every_required_category`): registered concepts (2),
unregistered named technologies (2), unknown single terms (2), unknown
AND-lists (2), unknown OR-groups (3), mixed known/unknown (2), technical
competencies with no named product (3), professional
experience/education (2), certifications incl. OSCP/CISSP (2), soft
skills (3), non-requirement prose (2), headings/section intros (2),
ambiguous language (2), plus one adversarial comma-list stress test
(`"Write clean, maintainable, and well-tested code"`, lifted from M9A's
own disclosed stress sentence).

---

## 3. Independent gold labeling rules

- Gold is never derived by running `parse_job_description()` first.
- An `ideal_outcome` records the ceiling (what a maximally correct
  parser would do); an `acceptable_fallback`, where present, records a
  degraded-but-honest outcome this corpus does **not** count as a
  failure (e.g. a generic `unresolved_requirement` placeholder instead
  of a specific `unresolved:<term>` id). The two are never merged into
  one pass/fail bit.
- Some entries deliberately have **no** `acceptable_fallback` at all
  (m9b-006, m9b-014/015/016, m9b-007/009/010/011) — a silent drop there
  is recorded as a genuine gap, not tolerated, because the claim is
  concretely technical and GitHub-observable in principle.
- Some entries deliberately **do** accept a silent drop (m9b-020,
  m9b-022, m9b-023, m9b-029, m9b-030) — because the claim is either not
  technical at all, or so vague that a dropped trace is a lower-severity
  gap than for the concrete cases above. Severity is explicit per entry,
  never uniform.
- `ambiguity_notes` is used exactly where the brief asks for it:
  genuinely ambiguous language (m9b-028, m9b-029) is recorded as
  *uncertain*, not resolved by guessing a specific vendor list the
  sentence never named.

---

## 4. Requirement-preservation benchmark results

Run: `python scripts/evaluate_m9b_preservation.py` →
`evaluation/reports/m9b_preservation_report.{json,md}`.

| # | Metric | Value |
|---|---|---|
| 1 | Genuine requirement preservation recall | **0.615** (16/26) |
| 2 | Correctly structured technical requirements | **0.500** (9/18) |
| 3 | Unknown-concept preservation | **0.500** (5/10) |
| 4 | Unknown OR/AND structural correctness | **0.833** (5/6) |
| 5 | Correct unparsed placeholder preservation | **0.643** (9/14) |
| 6 | Spurious requirement creation | **0** |
| 7 | Incorrect technology fabrication | **0** |
| 8 | Exact source-span correctness | **1.000** (16/16) |
| 9 | Silent-drop count | **0 accepted / 6 flagged as a gap** |
| 10 | Correctly excluded non-requirement prose | **1.000** (4/4) |

**These are never merged.** Metric 5 (placeholder success) and metric 7
(fabrication) are reported with different shapes on purpose — 5 is a
rate over placeholder-relevant entries, 7 is a raw count over the whole
corpus — exactly the distinction M9A's own report (§7) asked a future
milestone to make, instead of one misleading combined "precision."

**Headline finding: zero spurious requirements, zero fabricated
technologies, perfect span correctness.** Every failure this benchmark
found is a *silent drop* (an honest absence), never a wrong or invented
claim. This is the single most important integrity fact in this
report: M9A's non-fabrication invariant holds completely across 30
independently-authored examples, including three adversarial cases
specifically designed to try to break it (m9b-013's mixed-unsafe OR
group, m9b-019's OSCP/CISSP sentence-initial-capitalization trap,
m9b-030's comma-heavy soft-skill sentence).

### 4.1 Six silent-drop findings (the genuine gaps)

| Entry | Claim | Why it drops |
|---|---|---|
| m9b-006 | "The ideal candidate has used Snowflake extensively" | no comma, no OR, no qualifying lead-in phrase at all |
| m9b-008 | "Hands-on experience with PLC programming and SCADA systems" | `find_conservative_unknown_terms` requires an actual **comma**; this is a bare "X and Y" |
| m9b-014 | "Experience designing distributed systems" | no named technology, "designing" is not in the narrow lead-in table |
| m9b-015 | "Experience building reliable distributed services" | same — the brief's own named example |
| m9b-016 | "Ability to design and implement scalable backend architectures" | same category, different phrasing |

(m9b-005, "Familiarity with Snowflake is a plus", correctly resolved to
the `unresolved_requirement` fallback — it is *not* a silent drop; it is
listed in the metric-5 table above as a FALLBACK_MATCH.)

These six are exactly M9A's own disclosed residual limitation (§7 of
that report: "a technical-sounding requirement with no named technology
and no qualifying lead-in phrase ... is still silently dropped by
design — flagged for 9B, not fixed here") — this benchmark is the first
one to **count** it (6 of 26 real requirement claims, 23%) rather than
only name it.

### 4.2 The OSCP/CISSP regression held

m9b-019 ("Security certification such as OSCP or CISSP") landed on
`FALLBACK_MATCH` — the non-fabricating `unresolved_requirement`
placeholder, `concept_id=None` — confirming the sentence-initial-
capitalization fix M9A made *during its own implementation* (§3.1 of
that report) still holds against an independently-authored copy of the
same adversarial sentence.

---

## 5. Parser false-positive and silent-drop examples

**False positives: none found.** Zero spurious rows, zero fabricated
concept ids, across all 30 entries including four entries specifically
designed to tempt fabrication (m9b-013, m9b-019, m9b-025's in-skip-
section React mention, m9b-030's comma-heavy prose).

**Silent drops: six, all in one coherent category** — see §4.1. All six
share the same root cause (no named technology + no qualifying lead-in
phrase), consistent with a single, well-understood, already-disclosed
limitation rather than a scattering of unrelated bugs.

---

## 6. Retrieval-sensitive A/B evaluation (Phase 2)

Run: `python scripts/evaluate_m9b_retrieval_sensitivity.py` →
`evaluation/reports/m9b_retrieval_sensitivity_report.{json,md}`.

Three cases, two SYNTHETIC candidate fixtures
(`evaluation/m9b/retrieval/synthetic_candidates.json`), each engineered
to isolate one of the four events the brief requires kept separate: (A)
retrieval success, (B) new evidence discovery, (C) new requirement
support, (D) alignment-score impact.

| job_id | candidate | A: retrieved? | B: new evidence | C: newly SUPPORTED | D: score before→after | justified |
|---|---|---|---|---|---|---|
| `m9b_rust_or_go_backend_01` | `crowded_polyglot_dev` | **True** | `language.rust` | `Proficiency in Rust or Go` | **67 → 100** | True |
| `m9b_kotlin_preferred_01` | `crowded_polyglot_dev` | **False** | (none) | (none) | 67 → 67 | True |
| `m9b_redundant_rust_01` | `redundant_recovery_dev` | **True** | (none) | (none) | 100 → 100 | True |

**Case 1 — the genuine flip M8E's matrix could never produce.** Both
runs use the real `extract_candidate_evidence()` → `match_job()` →
`assess_job()` composition `analyze_job_fit()` itself uses. Generic-only
ranking excludes `aaa-rust-microtool` (tiny, old, zero stars, no
description — buried outside the top-15 among 21 well-formed JS/Python
"noise" repositories). Job-aware retrieval recovers it via the
structured `primary_language` signal (the only repository on the
account reporting Rust at all). Its deep extraction produces
`language.rust` evidence — a concept absent from every other analyzed
repository — which flips the job's `"Proficiency in Rust or Go"`
alternative-group requirement from `NOT_OBSERVED` to `SUPPORTED`,
raising `required` from `(2,3)` to `(3,3)` and `alignment_score` from
`67` to `100`. Every number above was read directly from a real
`assess_job()` call; nothing was asserted without being observed.

**Case 2 — a genuinely relevant repository still crowded out.** Same
candidate, same crowding, but the only matching repository
(`kotlin-microtool`) sits behind a **PREFERRED** requirement (retrieval
weight 0.5), while 21 other repositories each score the **REQUIRED**
weight (1.0) for this job's JavaScript/Python terms. The fixed
`relevance_top_k=10` budget fills entirely with 1.0-scorers before
`kotlin-microtool` (0.5) is ever considered — this is not an
alphabetical-tie artifact, it is a genuine, deterministic score gap.
`alignment_score` correctly does not move (`67 → 67`), because nothing
was actually recovered.

**Case 3 — recovery with no impact (the realistic common case).**
`aaa-rust-only-mini` IS newly recovered (retrieval succeeds, (A)=True),
but `language.rust` was already `SUPPORTED` before retrieval via a
different, generically-selected repository (`polyglot-service`, 20%
Rust alongside 80% JavaScript — above the 5% significance floor). No
new concept, no new support, no score change. This is the SAME shape as
every real-fixture recovery M8D.2/M8E already measured (§6.3 below).

**Common-language dominance check.** `viral-js-framework` (80,000
stars) and `js-service-01` (50 stars) score **identically** (`1.0`) for
the same job's JavaScript term — confirmed by calling
`score_repository_relevance()` directly, not inferred from the
architecture doc. Stars are not a relevance-scoring input at all; only
the job-independent generic ranker reads them.

### 6.1 Integrity check built into the harness itself

`retrieval_sensitivity_eval.py`'s `justification_note` field cross-checks
that every score change is **fully explained** by a real `SUPPORTED`
flip, and that every flip **is** reflected in the score — in both
directions. All three cases above report `justified=True`; an
`UNEXPLAINED` note (which would mean `match_job()`/`assess_job()`
disagree with themselves on real data) never appeared.
`tests/test_m9b_retrieval_sensitivity.py::test_every_case_in_the_full_evaluation_is_internally_justified`
pins this.

### 6.2 Why synthetic fixtures were necessary here

Per the brief's own instruction ("use existing offline fixtures when
possible... if existing fixtures cannot demonstrate unique evidence,
create clearly labeled, realistic synthetic fixtures"): M8E's own
measurement (§3.1 of `MILESTONE_8E_CONSOLIDATED_EVALUATION.md`) already
showed **0 of 12** real-fixture matrix pairs change `alignment_score`
under job-aware retrieval, because every real recovered repository's
evidence happened to be redundant. Re-confirmed fresh in this milestone
(§6.3) — the real fixtures genuinely cannot demonstrate a NEW-evidence
score flip; a synthetic fixture was the only way to test whether the
*mechanism* (recovery → new evidence → new support → score change) ever
actually fires correctly when the right conditions are engineered, as
opposed to merely asserting it should.

### 6.3 Real-fixture findings, re-confirmed fresh (not duplicated, cited)

- `python scripts/evaluate_repository_retrieval.py` (unchanged script,
  real `karpathy`/`torvalds`/`sindresorhus`/`Jango1324` fixtures):
  **recovered=2, already_covered=0, missed=2, correctly_excluded=3,
  false_positive=0** — identical to M8D.2/M8E's recorded baseline.
  `Jango1324/Pneumonia-Detection-Ai` (recovered, both for
  `ml_engineering_01` and, via an alternative group, for
  `general_swe_01`) is the real-world recovered-and-redundant case;
  `karpathy/nn-zero-to-hero` and `sindresorhus/execa` are the real-world
  crowded-out-despite-relevance cases; `sindresorhus/awesome` is the
  real-world correctly-excluded, huge-star, low-substance negative
  control.
- `python scripts/evaluate_end_to_end_job_aware.py` (unchanged script):
  **0 of 12** pairs' `alignment_score`/`required`/`preferred` change —
  confirmed still true under current code, matching M8E exactly.

These real numbers are **cited, not re-derived or modified** — this
milestone's job was to explain *why* they look the way they do (§6.2)
and to build a complementary, synthetic test that can actually move the
needle, not to question or rerun the real-fixture conclusion itself.

---

## 7. Real versus synthetic fixture distinctions

| | Real fixtures | Synthetic fixtures (this milestone) |
|---|---|---|
| Source | 4 real, public GitHub accounts, snapshotted once (`evaluation/fixtures/candidates/`) | Hand-constructed repository data, `evaluation/m9b/retrieval/synthetic_candidates.json` |
| Marked | implicitly real (no flag needed) | `"synthetic": true` on every fixture, plus a `notes` field stating exactly why it was built and what real-world limitation it demonstrates |
| Used for | crowding, recovered-redundant, correctly-excluded, common-language-non-dominance (§6.3) | genuine new-evidence score flip, PREFERRED-weight crowding (§6) |
| Never used for | claiming a specific real account's alignment score | anything presented as a measurement of a real candidate |
| Can demonstrate | everything the real corpus already contains | exactly the one mechanism (new evidence → new support → score change) the real corpus is structurally unable to contain, per M8E's own finding |

No synthetic repository was labeled relevant merely because its name
resembles a job description — `aaa-rust-microtool`/`aaa-rust-only-mini`/
`kotlin-microtool` are relevant **because their GitHub-reported
`primary_language` field is what the job requires**, the exact
structured signal `job_relevance.py` actually reads, confirmed by
tracing `score_repository_relevance()` directly rather than assuming it
from the repository's name.

---

## 8. Unique evidence and scoring-impact results

Already presented in full in §6's table and per-case detail
(`evaluation/reports/m9b_retrieval_sensitivity_report.md`). Summary:

- **Unique evidence gained:** exactly one case (`m9b_rust_or_go_backend_01`),
  exactly one concept (`language.rust`).
- **Scoring impact:** exactly one case, a clean `67 → 100` move, fully
  attributable to the one newly-SUPPORTED alternative-group requirement
  — no other requirement's status changed in that run.
- **Retrieval success without scoring impact:** one case
  (`m9b_redundant_rust_01`) — retrieval genuinely succeeded (a new
  repository was analyzed) but contributed nothing new.
- **Retrieval failure (crowding):** one case (`m9b_kotlin_preferred_01`)
  — a genuinely relevant repository, never recovered, no score impact.

---

## 9. Historical comparison caveats

- `evaluation/reports/m9b_preservation_report.*` and
  `evaluation/reports/m9b_retrieval_sensitivity_report.*` are **brand
  new** this milestone — there is no prior version to compare against.
  Both carry `corpus_version: "9b:v1"` explicitly.
- The pre-existing `8c:v1`/`8c:v1.1` parser/evidence/retrieval/
  end-to-end reports are **not superseded** by this milestone's numbers
  — they measure a different, frozen corpus and must not be compared
  cell-for-cell against the M9B corpus's metrics (different claim set,
  different metric definitions entirely).
- §10.2 below documents a **newly measured** staleness gap in the
  committed `end_to_end_report.json` that goes beyond what M8E/M9A
  already disclosed — this is a finding about report freshness, not
  about M9B's own corpus.

---

## 10. Evaluation-integrity safeguards (Phase 3)

**New tool:** `scripts/check_evaluation_staleness.py` — generalizes the
exact manual process M8D.3/M8E/M9A each used ad hoc ("recompute fresh in
memory, diff against the committed file, never overwrite it") into one
reusable, read-only script. It calls the SAME `evaluation_lib`
aggregation functions each `scripts/evaluate_*.py` already uses,
entirely in memory, and only *reads* the committed JSON reports — it
never calls any `evaluate_*.py`'s own `main()` (which overwrites files
in place) and never writes anything itself.
`tests/test_m9b_evaluation_integrity.py::test_check_evaluation_staleness_main_never_writes_to_any_committed_report`
pins this with a byte-for-byte before/after comparison of every
committed report file.

### 10.1 Run results (read-only; `evaluation/reports/` untouched — confirmed by the pinning test above)

| Report | Status | Finding |
|---|---|---|
| `parser_report.json` (`8c:v1`) | FRESH | — |
| `parser_report_v1_1.json` (`8c:v1.1`) | FRESH | — |
| `evidence_report.json` (`8c:v1`) | **STALE** | `false_positives`: committed `2`, fresh `1` — the **already-disclosed** M8D.3 staleness (M8E §3, run #3), re-confirmed still present and still exactly as documented. Not a new finding. |
| `evidence_report_v1_1.json` (`8c:v1.1`) | FRESH | — |
| `retrieval_report.json` | FRESH | — |
| `end_to_end_report.json` | **STALE** | **5 of 12 cells** disagree with a fresh recompute — see §10.2, a genuinely new finding beyond what any prior milestone disclosed. |

### 10.2 A genuinely new finding: `end_to_end_report.json` is stale across *two* milestones, not one

M8E/M9A each confirmed exactly **one** stale cell in this committed
file (`karpathy × frontend_01`, attributed to M8D.3's README fix).
Re-running the full matrix fresh under current code (M9A included) finds
**four additional** stale cells:

| Cell | Committed | Fresh | Why |
|---|---|---|---|
| `karpathy × frontend_01` | align 80, required (4,4), preferred (0,1) | align 50, required (3,4), preferred (0,2) | M8D.3 (already known) **+ M9A** (Vue/Angular now a real preferred row) |
| `torvalds × embedded_firmware_01` | align 50, required (1,1) | align 20, required (1,4) | **M9A**: SPI/I2C/UART now three real, assessable (and unsupported) required rows |
| `sindresorhus × frontend_01` | align 80, required (4,4), preferred (0,1) | align 67, required (4,4), preferred (0,2) | **M9A**: Vue/Angular preferred row |
| `sindresorhus × robotics_controls_01` | align 33, preferred `None` | align 25, preferred (0,1) | **M9A**: a new assessable preferred row appears where none existed before |
| `Jango1324 × embedded_firmware_01` | required (0,1) | required (0,4) | **M9A**: SPI/I2C/UART |

Every one of these five cells' drift is **fully explained** by the
already-committed, already-tested M9A parser change (new
`unresolved:<term>`/alternative-group rows for exactly the
SPI/I2C/UART/Vue/Angular family M9A's own report named) — this is not a
new bug, it is a previously-unmeasured consequence of a change that was
already correctly implemented and tested. Per this project's own
established discipline (M8D.3/M8E/M9A all left the frozen `8c:v1`
reports un-regenerated rather than silently "fixing" a stale number),
**this report does not regenerate `end_to_end_report.json`** — that
would be a production-adjacent-artifact change outside this milestone's
evaluation-only scope, and the file's own prior staleness note already
sets the precedent of disclosing rather than silently correcting it.
**Recommended for M9C:** either regenerate it with a clear "M9A applied"
note, or add an explicit staleness banner — see §12.

### 10.3 Other integrity safeguards checked

- **Gold modified after seeing output:** structurally prevented for
  M9B's own corpus — `preservation_eval.py`'s classification logic is
  unit-tested against hand-built `JobRequirement` objects
  (`tests/test_m9b_preservation_eval.py`), independent of the real
  corpus's measured verdicts, so there is no code path where a
  disappointing measured result could be "fixed" by editing gold without
  that edit being visible as a separate, reviewable diff.
- **Frozen gold directories never referenced:**
  `test_frozen_8c_gold_directories_are_not_imported_by_any_m9b_module`
  greps the actual M9B module source for the real
  `GOLD_JOBS_DIR(_V1_1)`/`GOLD_CANDIDATES_DIR(_V1_1)` Python identifiers
  (not docstring prose describing the directories, which is expected) —
  none appear.
- **Cached candidate-only evidence reused under a job-aware label:**
  cannot happen in this milestone's Phase 2 harness — both the
  generic-only and job-aware runs in `retrieval_sensitivity_eval.py`
  call `extract_candidate_evidence()` fresh, through a freshly-built
  fake client each time (mirroring `evaluation_lib.end_to_end_eval`'s
  own existing, already-reviewed pattern).
- **Regression pins disguised as correctness truth:** M9B's own
  synthetic fixtures are explicitly documented
  (`tests/test_m9b_retrieval_sensitivity.py`'s module docstring) as
  regression pins, not independent ground truth — unlike the M8D.2 real
  corpus's `genuinely_relevant` field, there is no separate "independent
  judgment" to keep apart here, because the fixture WAS constructed to
  produce one predetermined, engineered outcome; conflating the two
  would have been the mistake, and the module docstring states this
  explicitly rather than silently reusing the M8D.2 pattern where it
  does not actually apply.
- **Non-assessable placeholders mistaken for failed technical
  requirements:** every placeholder this milestone's corpus or fixtures
  produce carries `concept_id=None`, which the unchanged matcher
  (§20.2 of `ARCHITECTURE.md`) forces to `NOT_ASSESSABLE` — confirmed
  directly in the Phase 2 per-case reports (`not_assessable_count`),
  never silently counted as a missed requirement in any metric above.
- **Requirements dropped before assessment:** this is exactly what
  Phase 1's metric 9 (silent-drop count) exists to surface, and it
  found six (§4.1) — reported, not hidden.

---

## 11. Remaining correctness risks (Phase 4 product-risk analysis)

Ranked by severity × frequency × cost of a wrong conclusion, using this
milestone's own measurements plus the already-known M8E findings:

1. **Silent drop of a genuinely technical, no-named-product requirement
   (HIGH severity, MEDIUM-HIGH frequency).** 6 of 26 real requirement
   claims (23%) in an independently-authored, realistic corpus produced
   zero trace. This is strictly worse than a visible `MISSING` gold row
   — a future "show every parsed requirement, including unassessable
   ones" UI feature would have nothing at all to render for these
   claims, and a recruiter reading a high alignment score would have no
   way to know a real requirement like "experience designing distributed
   systems" was silently never assessed. This directly risks the
   product's core promise: "clearly distinguishing missing evidence
   from missing skills" cannot even begin for a requirement that never
   became a row.
2. **Denominator volatility compounding with stale committed reports
   (MEDIUM-HIGH severity, confirmed concrete via §10.2).** M9A's own
   fix — correctly implemented — changes `required`/`preferred`
   denominators by as much as 4x in a single cell
   (`torvalds × embedded_firmware_01`: required (1,1) → (1,4),
   alignment 50 → 20) purely by making previously-invisible
   `NOT_OBSERVED` rows visible. This is the CORRECT, more honest
   behavior — but it means any committed snapshot of
   `alignment_score`/`required`/`preferred` ages faster than the
   project's own documentation discipline has so far accounted for
   (one stale cell disclosed; five actually exist). A recruiter-facing
   product that ever caches or publishes a score needs an explicit
   policy for this, not an assumption that scores are stable once
   computed.
3. **Repository-retrieval crowding (MEDIUM-HIGH severity, already
   flagged "LARGE" scope in M8D.2/M8E, re-confirmed live in §6.3).** No
   new information this milestone changes that assessment, but Phase
   2's Case 2 (§6) is the first CONTROLLED demonstration that a
   PREFERRED-weight requirement is categorically more vulnerable to
   crowding than a REQUIRED one (0.5 vs 1.0 is a real, deterministic
   score gap, not merely a tie-break artifact) — a job posting whose
   most differentiating requirement happens to be phrased as "a plus"
   is structurally disadvantaged in retrieval regardless of how
   genuinely relevant the candidate's buried repository is.
4. **Required vs. preferred requirements rendered with equal headline
   weight (MEDIUM severity, architecture-level, not a bug).**
   `alignment_score` does not distinguish necessity (§21.3 of
   `ARCHITECTURE.md`, by design) — this milestone's own Case 1 (§6)
   shows a REQUIRED alternative-group flip moving the headline score by
   33 points in one step; the already-documented mandatory co-display
   requirement (`required`/`preferred` subscores) is the only mitigation,
   and nothing in this milestone found a reason to revisit that
   decision, but the magnitude observed here is a useful concrete data
   point for any future UI review.
5. **GitHub evidence mistaken for proof of professional competence
   (LOW-MEDIUM severity, not newly observed, but reconfirmed).** Every
   `SUPPORTED` status in both this milestone's corpus and fixtures
   traces to a real, inspectable `Evidence`/`RepositoryIdentity` —
   never a probability or confidence score presented as competence
   proof. No regression found. Listed for completeness, not because
   anything new was found.
6. **Weak README mentions producing unsupported conclusions (LOW
   severity, specifically re-checked, not found live).** All three
   Phase 2 synthetic cases produce evidence exclusively through the
   structured `primary_language`/language-stats path, never README
   text — deliberately, so this milestone adds no new README-attribution
   risk. The pre-existing, already-disclosed latent gap (`MILESTONE_8E`
   §5.7 — unlisted comparison-table headings like "## Comparison") is
   unchanged and not re-investigated here; it remains a real, dormant
   risk the next milestone should still prioritize over most items in
   this list if the goal is false-positive prevention specifically.

**Not found to be a risk, confirmed directly:** fabrication (§4, §5 —
zero across every adversarial case tried), small-denominator score
instability in isolation (already documented, M8E §6 — no new instance
found, though §10.2 shows the denominators themselves are less stable
over TIME than previously measured).

---

## 12. Prioritized recommendations for Milestone 9C

1. **Decide, explicitly, whether the no-named-product silent-drop gap
   (§4.1, §11 risk #1) is worth a scoped fix, or should be converted
   into a disclosed, permanent product limitation.** This milestone
   deliberately did not implement a fix (out of scope — "do not
   implement production features" — and the brief's own prior guidance
   against "blanket vocabulary expansion"). A scoped option worth
   evaluating: a narrow, generic "technical-sounding gerund + object"
   shape heuristic (e.g. "designing/building/architecting + {systems,
   services, pipelines, platforms}") analogous to `looks_like_specific_
   technology_name()`'s shape-only philosophy — never a vocabulary list,
   and still only ever producing the non-fabricating
   `unresolved_requirement` placeholder, never a concept id.
2. **Resolve the `end_to_end_report.json` staleness (§10.2) before it
   compounds further** — either regenerate it with a clear changelog
   note ("M9A applied") or add an explicit, automated staleness banner
   that `check_evaluation_staleness.py` can enforce in CI. Left
   unresolved, a THIRD future milestone's change will make the
   divergence even harder to attribute to a single cause.
3. **Extend `check_evaluation_staleness.py` into a lightweight CI gate**
   (currently a reporting tool only, exit code always 0) — e.g. a
   `--fail-on-stale` flag for whichever reports a milestone's own
   instructions say must stay current, while leaving intentionally
   frozen snapshots exempted by an explicit allowlist rather than by
   silent convention.
4. **Revisit the PREFERRED-weight retrieval disadvantage (§11 risk #3)**
   with the controlled mechanism this milestone's Case 2 now provides —
   e.g. consider whether a PREFERRED-but-sole-differentiator requirement
   deserves a different retrieval weight, or whether this is an accepted
   trade documented alongside the existing crowding limitation.
5. **Do not start M9C's scope before the above are triaged** — this
   explicitly matches the brief's own instruction not to begin new
   production work from an evaluation-only milestone.

---

## Reproduction commands

```powershell
# Phase 0 baseline
git status --short
git log -5 --oneline
python -m pytest                                              # 904 passed (876 + 28 new)

# Phase 1 -- requirement-preservation benchmark
python scripts/evaluate_m9b_preservation.py
python -m pytest tests/test_m9b_preservation_eval.py -v

# Phase 2 -- retrieval-sensitive end-to-end evaluation
python scripts/evaluate_m9b_retrieval_sensitivity.py
python -m pytest tests/test_m9b_retrieval_sensitivity.py -v

# Phase 2 -- real-fixture findings, re-confirmed (unchanged scripts, cited not duplicated)
python scripts/evaluate_repository_retrieval.py
python scripts/evaluate_end_to_end_job_aware.py

# Phase 3 -- evaluation-integrity safeguards
python scripts/check_evaluation_staleness.py
python -m pytest tests/test_m9b_evaluation_integrity.py -v

# Final verification
python -m pytest
git diff --check
git status --short
git diff --stat
```

## Final verification (run at the end of this milestone)

```
python -m pytest           -> 904 passed, 0 failed
git diff --check           -> (no output: no whitespace errors)
git status --short         -> docs/CHANGELOG_DEV.md modified (this milestone's own changelog entry,
                               the one deliberate tracked-file edit Phase 5 asks for); every other
                               change is a new, untracked file under evaluation/m9b/,
                               evaluation/reports/m9b_*, docs/evaluation/MILESTONE_9B_*.md,
                               scripts/evaluate_m9b_*.py, scripts/check_evaluation_staleness.py,
                               scripts/evaluation_lib/{preservation,retrieval_sensitivity}_eval.py,
                               tests/test_m9b_*.py
git diff --stat            -> docs/CHANGELOG_DEV.md | 102 +++++++++++++++++++++++ (1 file changed,
                               102 insertions(+)) -- no other tracked file touched
```

**No frontend/shared contract changed** — this milestone touches no API
response shape, no HTTP contract, and no file under `frontend/`; a
frontend rebuild is unnecessary because nothing the frontend consumes
was built, modified, or regenerated.

**DO NOT COMMIT. DO NOT PUSH.** (per this milestone's own instructions —
no commit was made by this work.)
