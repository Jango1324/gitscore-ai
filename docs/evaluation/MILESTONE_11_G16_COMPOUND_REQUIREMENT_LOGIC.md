# Milestone 11-G16 — Compound Requirement Logic Integrity

Status: **evaluation-first research result, committed to preserve it.
Parser v13 is not implemented.** Neither option D nor option C is
implemented.

**These are development-corpus findings**: same-author synthetic controls
plus previously inspected postings. They are not independent
generalization estimates.

- No production file changed: `src/gitscore` is byte-identical to HEAD
  (test-enforced) and the parser is still `job_description_parser:v12`.
- No matcher, scoring, schema, API, frontend, G10–G15, freeze or
  historical-gold change. No LLM call.
- Production results come from *calling* the real parser, matcher and
  assessor.
- Candidate fixes are simulated by rebinding two parser module helpers
  **in memory** (always restored; test-enforced) and, for the regression
  probe, only inside throwaway clones.

| Artifact | Path |
|---|---|
| Frozen controls (58) + derivation rules | `evaluation/m11g16/compound_logic_controls.json`, `controls_hash_freeze.json`, `scripts/evaluation_lib/m11g16_build_controls.py` |
| Reproduction + option simulation | `scripts/evaluation_lib/m11g16_compound_logic.py` |
| Runner (synthetic, 8c counterfactual, tracked corpora; private opt-in) | `scripts/evaluate_m11g16_compound_logic.py` → `evaluation/m11g16/compound_logic_report.json`, `private_impact_aggregates.json` |
| Regression probe (throwaway clones only) | `scripts/evaluation_lib/m11g16_option_regression_probe.py` → `evaluation/m11g16/option_regression_probe.json` |
| Focused tests (20) | `tests/test_m11g16_compound_requirement_logic.py` |

## Phase 0 — Baseline (verified)

- HEAD `8d5b3801049f7d28736e921885681bd46db3c58b` = `origin/main`, no
  tracked diffs, parser v12.
- Full suite 1992 passed, 13 skipped, 18 xfailed.
- G14 manifest: 9 registered freezes. No Policy B integration.
- The 18 private / untracked M11 entries are preserved.

## Phase 1 — Root-cause trace

This is a **known, documented, deferred defect**. M10D's own docstring
(`jobs/parsing/alternatives.py`, "Root Cause 6") records that "a MIXED
AND/OR shape ('Python or Java and SQL') is still silently flattened into
one over-permissive ANY-of-3 group", reserved for a future milestone. It
also records that a mixed requirement "is already representable today as
one `alternative_concept_ids` group plus one ordinary single-`concept_id`
row".

| Stage | Finding |
|---|---|
| A. Segmentation | Mostly correct: a claim is a sentence or bullet. **Two segmentation losses:** a "One of:" nested sublist becomes separate bullet claims, so each alternative turns into a mandatory AND row (control 028). And a semicolon inside one sentence ("Required: Docker or Kubernetes; Python.") does not split the claim. |
| **B. Extraction — earliest irreversible loss** | `classify_alternative_claim` → `_split_alternative_segments` splits on **every** bare "or" **and every comma**, so ", and Python" becomes another OR segment. Then `_resolve_segment` returns **all** concepts mentioned in a segment, so "Java and SQL" or "Kubernetes; Python" adds both to the OR group. The result, `AlternativeClaim(kind, concept_ids)`, is a **flat tuple**: AND/OR precedence is discarded here, before any `JobRequirement` exists, and nothing downstream can recover it. |
| C. Representation | `JobRequirement.alternative_concept_ids` is a flat OR. It **cannot** express OR-of-AND (`A or (B and C)`) or k-of-n with 1<k<n. It **can** express every AND of single concepts and OR-groups, as several rows. So for most mixed shapes the representation is not the bottleneck; extraction is. |
| D. Legacy projection | M11-B `qualification_from_job_requirement` faithfully projects the already-flattened row as `OR_ANY`. It inherits the error and adds none. `LogicalComposition.MIXED_UNSUPPORTED` exists only in the offline M11-B model. |
| E. Matcher | Correct: a group is SUPPORTED if any member has evidence. It cannot know the group was mis-built. |
| F. Scorer | Correct given the rows. A flattened claim is one denominator entry where the logic needs two or more (undercount 22/43). |

**Separation of errors:** every false SUPPORTED observed originates in
the parser (A/B). Given faithful rows, the unchanged matcher and scorer
produce the gold-consistent result (see option C below). No matcher or
scorer change is needed.

## Phase 2 — Frozen controls

**Controls.** **58 original synthetic controls in 20 families**: simple
OR / AND, (A∨B)∧C, A∧(B∨C), (A∨B)∧(C∨D), A∨(B∧C), three or more, nested,
bullets / sublists, natural-language conjunctions, either / both / one of
/ all of, at-least-k, conditional, required vs preferred, ambiguous
"A, B or C", unregistered technologies, mixed observability, duplicates,
narrative / responsibilities, cross-sentence.

- Frozen **before** any production run or fix strategy: sha256 and
  LF-normalized sha256 `7078c3fc80bad84bd7cc789f62fcd5ca436f17e0e1592914ec87938dc7bb9bc0`
  (contract `crlf-to-lf/v1`).
- Same author as G10–G15; not independently annotated.

**Annotated per control** (hand-written):

- the source span
- whether it is a genuine applicant qualification
- a Boolean tree (AND / OR / k-of-n)
- necessity, including per-conjunct necessity
- whether it is ambiguous or conditional

**Derived by frozen rules in the builder** (verified by test):

- whether the current model can represent it;
- the expected safe behaviour: represent 43, decline 12, not a
  qualification 3;
- the faithful rows: CNF clauses with absorption;
- deterministic evidence fixtures (only A / B / C / D, A+C, B+C, all
  members, none, irrelevant, mixed-observability);
- the expected truth per fixture in **three-valued logic**: a concept
  GitHub can never evidence is *unknown*, never *false*;
- expected scored and supported rows (denominator).

**Totals:** 414 fixture evaluations (146 true, 257 false, 11 unknown).

## Phase 3 — Production reproduction (real parser, matcher, assessor)

**Claim-level false SUPPORTED** means every scored row of the claim is
SUPPORTED while the frozen truth is not *true*. Production has
**106 / 414**, distributed by family as:

| Family | Count |
|---|---|
| and_then_or | 16 |
| or_then_and | 15 |
| or_and_or | 11 |
| nested | 11 |
| natural_language | 8 |
| necessity_mix | 7 |
| or_of_and | 6 |
| three_plus | 6 |
| unregistered | 6 |
| ambiguous_list | 4 |
| duplicates | 4 |
| bullets | 3 |
| conditional | 3 |
| k_of_n | 3 |
| mixed_observability | 2 |
| either_both | 1 |

**Representative before/after**, as scores across fixtures (production →
option C):

| Control | Production rows | Production: only A / only C / A+C / all | C rows | C: only A / only C / A+C / all | Truth |
|---|---|---|---|---|---|
| 007 "Docker or Kubernetes, and Python" | docker+k8s+python | **100 / 100** / 100 / 100 | docker+k8s ; python | 50 / 50 / 100 / 100 | F / F / T / T |
| 012 "Python and either Docker or Kubernetes" | docker+k8s+python | **100 / 100** / 100 / 100 | python ; docker+k8s | 50 / 50 / 100 / 100 | F / F / T / T |
| 016 "Python or Go, and Docker or Kubernetes" | 4-way OR | **100 / 100** / 100 / 100 | go+python ; docker+k8s | 50 / 50 / 100 / 100 | F / F / T / T |
| 019 "Rust, or both Docker and Kubernetes" | 3-way OR | 100 / **100** / 100 / 100 | declined (fallback) | None | T / F / T / T |
| 036 "at least two of Python, Java, or Rust" | 3-way OR | **100 / 100** / 100 / 100 | declined | None | F / F / T / T |
| 040 "Python required; Docker or Kubernetes preferred" | one REQUIRED 3-way OR | **100 / 100** / 100 / 100 | python (R) ; docker+k8s (P) | 50 / 50 / 100 / 100 | F / F / T / T |
| 049 "AWS or Azure, and Docker" | aws+docker+azure | **100** / – / – / 100 | aws+azure ; docker | 50 / 100 | F / T |
| 013 "Python and Docker or Kubernetes" (ambiguous) | 3-way OR | **100 / 100** / 100 / 100 | declined | None | — |

Every row above whose production score is 100 against a false truth value
is a **SUPPORTED despite failing a mandatory conjunctive condition**. The
complete list of 106 is in `compound_logic_report.json`.

## Phase 4 — Strategy comparison

58 controls, 414 fixture evaluations; denominators shown.

| Metric | Production | A: lexical guard | D: structural guard | C: decomposition (B ≡ C publicly) |
|---|---|---|---|---|
| Claim-level false SUPPORTED | **106/414** | 4/414 | 7/414 | 7/414 |
| Ambiguous / unrepresentable still scored | 11/12 | 3/12 | 3/12 | 3/12 |
| Genuine representable claims represented exactly | 17/43 | 17/43 | 17/43 | **38/43** |
| …with correct necessity | 17/43 | 17/43 | 17/43 | **38/43** |
| False declines of representable claims | 2/43 | **25/43** | **24/43** | 2/43 |
| Denominator over-count | 1/43 | 1/43 | 1/43 | 2/43 |
| Denominator under-count (merged) | **22/43** | 0/43 | 1/43 | 1/43 |
| Narrative claims scored | 1/3 | 0/3 | 0/3 | 1/3 |
| Rows without valid source span | 0/58 | 0/58 | 0/58 | 0/58 |
| Eligibility unstable across candidates | 0/58 | 0/58 | 0/58 | 0/58 |
| Unevidenceable concept used as positive | 0 | 0 | 0 | 0 |
| Existing tests broken (throwaway-clone probe) | — | 2 (G15 only) | 2 (G15 only) | 2 (G15 only) |
| Public schema / matcher / scorer change | — | none | none | none |
| Complexity | — | trivial guard | small guard (segment-level detection) | moderate: guard + decomposition + per-conjunct necessity |

### The options

- **A — minimal lexical guard:** any OR claim containing and, &, plus,
  as well as, along with, both, all of, "at least two", or ";" goes to
  the existing 6B.1 fallback.
- **D — structural guard (the smaller, more precise variant):** decline
  only if an OR segment resolves to ≥2 concepts, a comma item begins
  with a conjunction, or a k≥2-of / both / all-of lead-in is present.
- **C — decomposition:** D's detection, then split **only** shapes that
  are an AND of single concepts / OR-groups into separate existing rows,
  with per-conjunct necessity from the production `infer_necessity`.
  Everything else is declined.
- **B — internal Boolean tree, public schema unchanged:** must publish
  exactly C's rows for representable shapes and decline the rest, so its
  observable outputs equal C's by construction. It adds internal
  provenance at higher complexity; it is not simulated separately.

### Interaction with G15 Policy B

The two are independent:

- Decomposed OR rows that contain an unresolved member are exactly what
  Policy B would exclude from scoring.
- The G16 guard changes only parser output; Policy B changes only the
  scoring filter.

## Phase 5 — Safety invariants (real matcher and scorer)

| # | Invariant | Production | A | D | C |
|---|---|---|---|---|---|
| 1 | Evidence for C alone cannot satisfy (A∨B)∧C | **✗** | ✓ | ✓ | ✓ |
| 2 | Evidence for A alone cannot satisfy A∧(B∨C) | **✗** | ✓ | ✓ | ✓ |
| 3 | A and C may satisfy (A∨B)∧C | ✓ | ✗ (declined) | ✗ (declined) | ✓ |
| 4 | Distinct alternatives not equivalent | ✓ | ✓ | ✓ | ✓ |
| 5 | Irrelevant evidence satisfies nothing | ✓ | ✓ | ✓ | ✓ |
| 6 | Unevidenceable concepts never positive | ✓ | ✓ | ✓ | ✓ |
| 7 | Ambiguous expressions never scored | ✗ | ✗ | ✗ | ✗ |
| 8 | Stable eligibility across candidates | ✓ | ✓ | ✓ | ✓ |
| 9 | No double counting | ✗ | ✗ | ✗ | ✗ |
| 10 | Source provenance kept | ✓ | ✓ | ✓ | ✓ (claim-level span; conjunct text kept as `original_text`) |
| 11 | No new REQUIRED by default | ✓ | ✓ | ✓ | ✓ |
| 12 | Simple OR / AND unchanged | ✓ | ✓ | ✓ | ✓ |

Ten invariants for option C are pinned by tests.

### Residual false SUPPORTED under option D (exactly 7)

Option D does **not** eliminate every logical-parsing defect. Its 7
residual cases have two root causes:

- **Mixed-kind list ambiguity: 4** (043 only_A, only_B, only_C, B_and_C).
  "Python, Docker or Kubernetes" contains no conjunction, so the
  structural detector never fires and it stays a 3-way OR.
- **Bare "Go" recognition gap: 3** (018 only_A, only_C, only_D). In
  "Either Python or Go and either Docker or Kubernetes", "Go" is
  prose-unsafe and unrecognised, so the segment looks single-concept and
  evades detection. The row becomes OR(Docker, Kubernetes, Python), with
  Go dropped entirely.

### Residual failures under every option

These failures share causes outside the compound-logic guard:

1. **043 "Python, Docker or Kubernetes"** (mixed-kind comma list, no
   conjunction). Nothing marks it as compound, so it stays a 3-way OR.
   Main remaining false SUPPORTED (4 of 7). A category-heterogeneity rule
   is possible, but it is unevaluated and carries false-decline risk.
2. **018** "Either Python or Go and either Docker…": bare **"Go"** is
   prose-unsafe and is not recognised, so the segment looks like one
   concept and evades detection (3 of 7). This is the G15 P1 alias issue.
3. **058** cross-sentence "Alternatively…": two independent rows plus a
   **fabricated `unresolved:alternatively` concept**. A separate parser
   bug.
4. **037** "at least two of: Docker, Kubernetes, AWS" has no "or", so it
   becomes 3 AND rows. Over-strict (false NOT_OBSERVED), not false
   SUPPORTED.
5. **028** "One of:" nested sublist: a segmentation loss, giving 3 AND
   rows instead of OR + AND. Over-strict.
6. **051** duplicates: C lacks absorption ((D∨K)∧D gives two rows), so
   there is a double count.
7. **053** "You will maintain…": production already scores this
   responsibility; C re-creates rows from it. A narrative-detection
   issue.

## Phase 6 — Historical impact

**Frozen 8c scores.**

- **8c:v1 and 8c:v1.1: 0 of 12 pairs change under any option.**
- The frozen 8c reports, gold and scores are unaffected, so these
  options would produce **no counterfactual 8c score change**.

**Tracked corpora** (texts whose parsed rows change, per option A / D / C):

| Corpus | Texts | A | D | C |
|---|---|---|---|---|
| 8c job corpus | 15 | 0 | 0 | 0 |
| M10 tracked sources (SOTI / Manulife) | 2 | 0 | 0 | 0 |
| G13 OR-contract controls | 13 | 0 | 0 | 0 |
| G15 scoring controls | 19 | 1 (K1) | 1 | 1 |

**Private corpora** (previously inspected, so not independent; counts
only):

| Corpus | Postings | A | D | C |
|---|---|---|---|---|
| M11-D | 12 | 0 | 0 | 0 |
| M11-F | 18 | 2 | 1 | 1 |
| M11-G5 | 18 | 1 (lexical false decline) | 0 | 0 |
| M11-G9 | 14 | 0 | 0 | 0 |

**Reading.** The mechanism is severe wherever it occurs (106 false
SUPPORTED on the synthetic set). But in the inspected real postings it
affects **1 of 62 postings** (D/C), and none of the frozen 8c scores. No
new independent real data exists.

**Existing tests (regression probe).**

- Every option breaks exactly **2** existing tests, both in G15's own
  suite: `test_report_is_reproducible` and
  `test_simulated_policy_properties`. Both pin G15's *measurement* of the
  K1 flattening, so a correct parser fix legitimately changes them.
- **No** M10A–M10E, M11-A1/A2, M11-B, G6/G7, parser, matcher, assessment
  or evaluation-harness test breaks. Nothing in the existing suite covers
  mixed AND/OR, consistent with M10D deferring it.

## Phase 7 — Recommendation (not implemented)

**Smallest safe correction: option D, the structural guard, as parser
v12 → v13.** Mixed AND/OR claims go to the parser's **existing** 6B.1
`alternative_requirement` fallback (NOT_ASSESSABLE) instead of being
flattened.

- It eliminates the conjunct-violating false SUPPORTED family (invariants
  1 and 2): 106 → 7 on the synthetic set. The 7 that remain come from
  residuals 1 and 2, which no option addresses.
- It changes no model, schema, matcher, scorer or API, has zero 8c
  impact, and breaks only the 2 G15 measurement tests.
- **Cost:** representable mixed claims become unscored (24/43 synthetic;
  1 of 62 inspected real postings).

**Follow-up worth approving separately: option C (decomposition).**

- It restores faithful scoring (38/43 exact, correct per-conjunct
  necessity) with the same false-SUPPORTED level, still with no
  schema / matcher / scorer change.
- It needs an absorption rule (residual 6) and should not run before the
  narrative issue (residual 7) is handled, because it re-creates rows for
  a responsibility sentence.

Option B is not justified: the public model already expresses every
shape C emits, and must decline the rest anyway.

### Versioning and file scope (if approved)

- `src/gitscore/jobs/parsing/alternatives.py`: mixed-structure detection,
  returning the existing `unsafe` kind (D); for C, also a structured
  conjunct result.
- `src/gitscore/jobs/parsing/parser.py`:
  `JOB_DESCRIPTION_PARSER_VERSION` v12 → **v13**; for C, `_requirements_from_claim`
  emits one row per conjunct with per-conjunct necessity.
- Tests:
  - new focused tests;
  - G15's two K1 measurement tests and its regenerated report (a
    legitimate change);
  - a regenerated G16 report.
- **Unchanged:** `JobRequirement`, `MatchStatus`, the matcher, the scorer,
  `SCORING_VERSION`, the API and the frontend.

### Deployment order with G15 Policy B

The guard first: it is parser-only, prevents false SUPPORTED, and has no
score-formula change. Policy B later or alongside: they are independent.

## Phase 8 — Verification

- **G16 focused:** 20 passed.
- **G15:** 12 passed. **G14:** 122 passed. **G13:** 15 passed, 12
  xfailed.
- **G6:** 102 passed, 2 xfailed. **G7:** 137 passed.
- **M10D:** 60 passed. **M10E:** 52 passed, 10 skipped (pre-existing).
- **M11-B:** 56 passed. **M11-B stage 2b:** 26 passed. **M11-A1:** 15
  passed.
- **job_parser / matching / assessment / evaluation harness:**
  43 / 42 / 36 / 27 passed.
- **Full suite: 2012 passed, 13 skipped, 18 xfailed** (1992 + 20). No new
  skips; the 18 strict xfails are unchanged.
- Parser v12; no `src/` change; matcher, scoring, API and frontend
  unchanged; G10–G15 unchanged; no historical gold or freeze changed.
- Privacy scan of all 10 new files against 1,178 private names, ids and
  text fragments: **0 matches**.

### G14 freeze registration (done at commit time)

G16 was registered as the **tenth** entry in
`evaluation/integrity/canonical_hash_manifest.json` (+8 lines, 0 removed),
using the same refuse-on-doubt procedure as G15. It was attested from the
exact bytes committed, and accepted only after reconciling three anchors:

- the pre-evaluation freeze hash `7078c3fc…9bc0`, which the staged blob
  reproduces;
- the freeze record's raw and freeze-time `sha256_lf_normalized` hashes;
- `gold_integrity.attest()`.

The original nine entries are identical field for field. No hash was
regenerated from current content, and no integrity-framework code or test
changed.

G14's inventory rule (registered set = tracked set, pinned historical
entries, new entries reconciled with their freeze-time anchor) accepts
G16. The two HEAD-rebuild tests pass in post-commit-equivalent clean
checkouts.

## Changed-file inventory (committed together as one research commit, plus the additive manifest registration)

- `docs/evaluation/MILESTONE_11_G16_COMPOUND_REQUIREMENT_LOGIC.md`
- `scripts/evaluation_lib/m11g16_build_controls.py`
- `scripts/evaluation_lib/m11g16_compound_logic.py`
- `scripts/evaluation_lib/m11g16_option_regression_probe.py`
- `scripts/evaluate_m11g16_compound_logic.py`
- `evaluation/m11g16/compound_logic_controls.json`
- `evaluation/m11g16/controls_hash_freeze.json`
- `evaluation/m11g16/compound_logic_report.json`
- `evaluation/m11g16/option_regression_probe.json`
- `evaluation/m11g16/private_impact_aggregates.json` (counts only)
- `tests/test_m11g16_compound_requirement_logic.py`

No tracked file is modified.

## STOP — implementation approval questions

1. Approve the **structural guard (option D)** as parser **v13**,
   declining mixed AND/OR to the existing fallback?
2. Approve **decomposition (option C)** now, or as a follow-up after the
   guard? If approved, it should include the absorption rule (residual 6)
   and wait for narrative handling (residual 7).
3. Open separate work for the residuals:
   - mixed-kind comma lists (043)
   - bare "Go" alias detection (018)
   - k-of-n without "or" (037)
   - "One of:" sublists (028)
   - the fabricated `unresolved:alternatively` (058)
   - responsibility sentences scored (053)
4. Deploy the guard before G15 Policy B, as recommended?
5. At commit time, register the G16 freeze in the G14 manifest using the
   same procedure as G15?

## Commit status

Committed as `test: evaluate compound requirement logic integrity`, with
the additive G14 manifest registration, after all authorization gates
passed. Parser v13 is not implemented, and the production parser remains
v12. G17 has not started.
