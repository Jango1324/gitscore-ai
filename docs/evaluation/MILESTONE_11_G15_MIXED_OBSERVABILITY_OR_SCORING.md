# Milestone 11-G15 — Mixed-Observability OR Scoring Integrity

Status: **evaluation-first research result, committed to preserve it.
No production implementation.** Policy B is preferred for *future*
production consideration only. Policy C is rejected. Every changed score
in this document is a **counterfactual result of a simulated policy**, not
a retroactive correction of any frozen gold or historical report.

- No production file changed: `src/gitscore` is byte-identical to HEAD
  (test-enforced).
- No matcher, scoring formula, public schema, API, frontend, G10–G14
  implementation or frozen gold changed.
- No LLM call.
- Every production outcome below comes from *calling* the real,
  unmodified `parse_job_description`, `match_job`/`match_requirement`
  and `assess_job`.

| Artifact | Path |
|---|---|
| Frozen controls (19 controls, 35 candidate variants, 55 expectations) | `evaluation/m11g15/or_scoring_controls.json`, `controls_hash_freeze.json` |
| Control builder + frozen semantic rule | `scripts/evaluation_lib/m11g15_build_controls.py` |
| Production reproduction + policy simulation | `scripts/evaluation_lib/m11g15_or_scoring.py` |
| Runner (synthetic, 8c re-score, structure frequency) | `scripts/evaluate_m11g15_or_scoring.py` → `evaluation/m11g15/or_scoring_report.json`, `structure_frequency.json` |
| Regression probe (throwaway clones only) | `scripts/evaluation_lib/m11g15_option_regression_probe.py` → `evaluation/m11g15/option_regression_probe.json` |
| Focused tests (12) | `tests/test_m11g15_mixed_observability_or_scoring.py` |

## Phase 0 — Baseline (verified)

- HEAD `9c82073012b2173c1046e908a671510fbeca45e1` = `origin/main`, no
  tracked diffs, parser `job_description_parser:v12`.
- Full suite: 1969 passed, 13 skipped, 18 xfailed.
- 18 private / untracked M11 entries preserved.

## Phase 1 — Exact production semantics (from code and execution)

| # | Question | Answer |
|---|---|---|
| 1 | What makes an individual alternative assessable? | **Nothing per-alternative.** Production has no member-level observability. Whether evidence *can* exist for a member is decided de facto by the evidence extractors: registry concepts can be emitted. `unresolved:<term>` ids are emitted ONLY by the language extractor (`languages.py`, plus `v1_bridge` primary language). The dependency extractor deliberately *skips* unknown packages. So `unresolved:elixir` or `unresolved:vue` can be evidenced; `unresolved:azure`, `unresolved:terraform` or `unresolved:numpy` never can. |
| 2 | What makes an OR group assessable? | The requirement-level `github_observability`. The parser gives every technical alternative group `observability_for_technical()` = STRONGLY_OBSERVABLE, **regardless of its members**. The matcher evaluates it whenever it is not NOT_OBSERVABLE and has concept ids. |
| 3 | How is positive evidence aggregated? | `match_requirement` checks every member with `has_sufficient_evidence` (WEAK or better). SUPPORTED if ANY member matches; `matched_concept_ids` lists all matched members. |
| 4 | NOT_OBSERVED vs NOT_ASSESSABLE | NOT_OBSERVED: an evaluated requirement with no matching evidence. It **is counted** in the alignment denominator (`_assessable_matches` = SUPPORTED + NOT_OBSERVED). NOT_ASSESSABLE: NOT_OBSERVABLE, or no concept id at all. It is excluded from the denominator and cannot carry matched ids or evidence (a `RequirementMatch` invariant). |
| 5 | Does UNKNOWN observability exist? | Not on `JobRequirement`: `github_observability` is non-nullable. M11-B `Qualification.github_observability=None` exists offline only and is routed to `UnparsedClaim` by `project_qualification`. An unknown non-technical category defaults to NOT_OBSERVABLE. |
| 6 | Does one assessable member make the whole group assessable? | **Yes.** Indeed even zero evidenceable members do: `(unresolved:azure, unresolved:gcp)` is STRONGLY_OBSERVABLE and can only ever be NOT_OBSERVED. |
| 7 | Can alternative evidence satisfy a different requirement? | Not between separate rows (control M1: Docker evidence leaves the Kubernetes row NOT_OBSERVED). **But** the parser can merge requirements: "Docker or Kubernetes, and Python" becomes ONE three-way OR group, so Python evidence alone satisfies the Docker-or-Kubernetes requirement (control K1). |
| 8 | One OR group = one denominator entry? | Yes, one row and one entry. Duplicate members are deduplicated (N1); no duplicate counting was observed. |

**Denominator and rounding.**

- `alignment_score = _round_half_up_percentage(supported_count, assessable_count)`,
  or `None` when assessable is 0.
- Required and preferred sub-scores use the same `_assessable_matches`.
- Necessity never affects matching.

### Root cause

A requirement is scored as fully GitHub-assessable even when one or more
of its concepts can never receive evidence. Observability is decided per
requirement from "is it technical?", not per member from "can the
extractors ever emit evidence for this concept?".

For an OR group, absence of evidence for its evidenceable members is then
recorded as NOT_OBSERVED and counted in the denominator. That happens
even though the candidate may satisfy it through an alternative GitHub
can never show (`AWS or Azure` with an Azure-only candidate).

The same root cause also affects **single** requirements with an
`unresolved:` concept id (`unresolved:numpy`, `:spi`, `:i2c`, `:uart`).
See Phase 5: this is frequent in real postings and outside G15's OR
scope.

**Pathway nuances established by execution, not assumed:**

- A **single** "Experience with Terraform is required." takes the
  `unresolved_requirement` fallback (NOT_ASSESSABLE), but list or
  enumeration phrasings can produce STRONGLY_OBSERVABLE single unresolved
  rows.
- Alias ORs ("Kubernetes or k8s") and non-technical alternatives ("Docker
  or a security clearance") take the existing 6B.1 `alternative_requirement`
  fallback, which is **NOT_ASSESSABLE** and safe, though it discards
  positive evidence.
- Unresolved **language** members are genuinely evidenceable, so the
  `unresolved:` prefix alone does not identify unevidenceable members.

## Phase 2/3 — Frozen controls and expectations

**Controls.** 19 original synthetic controls covering cases A–P, 35
candidate variants and 55 (gold requirement × candidate) expectations.

- Frozen **before** any production or policy run: sha256 and
  LF-normalized sha256 `cd015c9608f06f8e24899708f068a0045c6866bdd7ed708f966a2d82a0433fc7`
  (contract `crlf-to-lf/v1`).
- Same author as G10–G14; not independently annotated.

**Annotated facts:**

- each member's true evidenceability (`registry` / `language_stats` /
  `none` / `non_technical`)
- the candidate's evidence
- the candidate's true competencies, including ones GitHub cannot show
- the annotator's reading of the logical structure

**Expected outcomes** are derived from those facts by the written rule
`expected_outcome()`. A test verifies every frozen expectation still
equals the rule, so none was hand-edited to match production.

| Category | Count | Representable by public MatchStatus? |
|---|---|---|
| satisfied_by_observed_evidence | 29 | yes (SUPPORTED) |
| not_observed_fully_assessable | 10 | yes (NOT_OBSERVED) |
| partially_observable_no_positive_evidence | 11 | **no**: NOT_OBSERVED overclaims a decidable negative; NOT_ASSESSABLE hides that part is checkable |
| completely_non_assessable | 3 | yes (NOT_ASSESSABLE) |
| structurally_ambiguous | 1 | **no**: no status for "grouping undetermined" |
| unsupported_related_evidence_only | 1 | yes (NOT_OBSERVED) |

## Phase 2 — Production outcome matrix

Real parser, matcher and assessor. Score format: score (supported /
assessable).

| Ctl | Production rows (members) | Candidate | Production status | Expected | A (production) | B | C |
|---|---|---|---|---|---|---|---|
| A1 | docker+k8s | docker evidence | SUPPORTED | satisfied | 100 (1/1) | 100 (1/1) | 100 (1/1) |
| B1 | docker+k8s (preferred) | none / knows k8s, no evidence | NOT_OBSERVED | not observed, fully assessable | 0 (0/1) | 0 (0/1) | 0 (0/1) |
| C1 | aws+**azure** | aws evidence | SUPPORTED | satisfied | 100 (1/1) | None (0/0) | 100 (1/1) |
| D1 | aws+**azure** | Azure-only (true) | NOT_OBSERVED | **partial** | **0 (0/1)** | None | None |
| E1 | **azure+gcp** | Azure (true) | NOT_OBSERVED | **completely non-assessable** | **0 (0/1)** | None | None |
| F1 | aws+**azure**+elixir | elixir language evidence | SUPPORTED | satisfied | 100 (1/1) | None | 100 (1/1) |
| F1 | | Azure-only / neither | NOT_OBSERVED | **partial** | **0 (0/1)** | None | None |
| G1 | `unresolved_requirement` fallback | — | NOT_ASSESSABLE | completely non-assessable | None | None | None |
| G2 | `unresolved_requirement` fallback (Elixir) | elixir evidence | NOT_ASSESSABLE | satisfied | None (evidence discarded) | None | None |
| G3 | elixir+zig | zig evidence / neither | SUPPORTED / NOT_OBSERVED | satisfied / not observed, fully assessable | 100 / 0 | None / None | 100 / None |
| H1 | aws+**azure** (preferred) | Azure-only / aws | NOT_OBSERVED / SUPPORTED | partial / satisfied | 0 / 100 | None / None | None / 100 |
| I1 | alias fallback | k8s evidence | NOT_ASSESSABLE | satisfied | None (discarded) | None | None |
| I2 | non-technical fallback | docker evidence | NOT_ASSESSABLE | satisfied | None (discarded) | None | None |
| J1 | python ; docker | python only | SUPPORTED, NOT_OBSERVED | satisfied, not observed | 50 (1/2) | 50 | 50 |
| K1 | **docker+k8s+python (flattened)** | python only | SUPPORTED | (Docker or K8s) NOT satisfied | **100 (1/1): false SUPPORTED** | 100 | 100 |
| L1 | docker+k8s+**terraform** | docker | SUPPORTED | structurally ambiguous | 100 (1/1) | None | 100 (1/1) |
| M1 | k8s ; docker | docker only | NOT_OBSERVED, SUPPORTED | related-only, satisfied | 50 (1/2) | 50 | 50 |
| N1 | go+python (deduplicated) | duplicated python evidence | SUPPORTED | satisfied | 100 (1/1) | 100 | 100 |
| O1 | python ; docker ; postgres ; aws+**azure** | 3 + Azure (true) | 3× SUPPORTED, NOT_OBSERVED | 3× satisfied, partial | **75 (3/4)** | 100 (3/3) | 100 (3/3) |
| O1 | | all four with aws | 4× SUPPORTED | 4× satisfied | 100 (4/4) | 100 (3/3) | 100 (4/4) |
| P1 | k8s ; aws+**azure+gcp** (bare "Go" bullet produces no row) | nothing / go / go+k8s / go+k8s+aws / go+k8s+GCP (true) | — | — | 0 / 0 / 50 / 100 / **50** | 0 / 0 / 100 / 100 / 100 | 0 / 0 / 100 / 100 / 100 |

**Justification verdicts (production):**

- A1, B1, J1, M1, N1 and the positive rows of C1, F1, G3, H1 are
  **justified**.
- D1, E1, F1 (negative), H1 (negative), O1 (Azure) and P1 (GCP) are
  **unjustified NOT_OBSERVED**.
- K1 is an **unjustified SUPPORTED**.
- L1 is **unjustified scoring** of an ambiguous structure.
- G2, I1 and I2 are **conservative losses** (true evidence discarded by
  safe fallbacks).

**Confound (disclosed).** P1's bare "- Go" bullet produces **no row at
all** under the live parser: the bare alias is prose-unsafe. This is
pre-existing behaviour unrelated to OR handling, reported separately as
"unrepresented" (5/55) and excluded from metric 4b. The frozen gold is
unchanged.

## Phase 4 — Policy comparison (55 gold requirement × candidate outcomes, 19 controls)

Policies decide only from production-visible facts; none sees gold. The
existing formula is unchanged throughout: every score uses the production
`_round_half_up_percentage`.

- **A** — production.
- **B** — requirements with any `unresolved:` member are excluded from the
  score; their production status is retained as a diagnostic.
- **C** — such requirements count when SUPPORTED, and are excluded when
  not.
- **D** — the existing 6B.1 parser fallback is applied to such groups.

| Metric | A | B | C | D |
|---|---|---|---|---|
| 1 False SUPPORTED | 1 | 1 | 1 | 1 |
| 2 False NOT_OBSERVED | **12** | 0 | 0 | 0 |
| 2b …where the candidate truly qualifies | **6** | 0 | 0 | 0 |
| 3 Non-assessable claims counted in the denominator | **13** | 0 | 1 (L1) | 0 |
| 4 Genuine positive evidence discarded | 7 | 13 | 7 | 13 |
| 4b …excluding parser-unrepresented | 3 | **9** | 3 | **9** |
| 5 Duplicate denominator counting | 0 | 0 | 0 | 0 |
| 5b Requirements merged and counted as one (K1) | 4 | 4 | 4 | 4 |
| 6 Evidence leakage between requirements (K1) | 1 | 1 | 1 | 1 |
| 7 Synthetic scores changed vs A | — | 16 | 11 | 16 |
| 9 Controls with candidate-dependent denominators | 0/19 | 0/19 | **5/19** | 0/19 |
| 10 Existing formula unchanged | yes | yes | yes, but its denominator now varies by candidate | yes |
| Diagnostic positive evidence retained | yes | yes | yes | **no** (contract forbids evidence on NOT_ASSESSABLE) |

### Denominator stability (metric 9)

**C is asymmetric.** A partially observable group counts only when it
helps the candidate (positive evidence) and is hidden when it would hurt.
The same job therefore yields different requirement sets per candidate:

- P1: denominators 1 or 2
- O1: 3 or 4
- F1, G3, H1: 0 or 1

The "X of Y" comparison stops being like-for-like across candidates, and
there is a systematic upward bias for these groups.

**B and D are symmetric.** Each job has one denominator for every
candidate.

**Decision (accepted): policy C is rejected.** A scored requirement set
that changes with the candidate being scored is unacceptable: it makes
the same job's "X of Y" non-comparable across candidates and biases scores
upward for exactly the uncertain groups.

### The trade-off

B gives up crediting genuine positive evidence for 6 more outcomes (C1,
F1, G3, H1, O1/aws, P1/aws). The score effect is often nil (O1: 100
either way), and the evidence remains visible as a diagnostic.

**No scoring policy fixes K1** (the nested AND/OR flattened by the
parser). That is a structural parser defect.

## Phase 5 — Historical impact

### Frozen 8c matrices

8c:v1 and 8c:v1.1 have the same 12 pairs and raw job texts; v1.1 differs
only in its gold annotations, so the scores are identical.

**These are counterfactual scores.** They are what the existing,
unchanged formula *would* produce under each simulated policy. The frozen
8c gold, the 8c matrices and every historical scoring report are
unchanged; none of these numbers corrects them retroactively.

- **5 of 12 pairs change alignment under any of B, C or D.**
- **3 of those are caused by OR groups alone:**
  - karpathy × frontend_01: 50 → 60
  - sindresorhus × frontend_01: 67 → 80
  - sindresorhus × robotics_controls_01: 25 → 33
- The other 2 come from single unresolved rows:
  - torvalds × embedded_firmware_01 (SPI, I²C, UART): 20 → 50
  - torvalds × data_science_01 (numpy): 20 → 25

The 8c corpus's unresolved OR members:

- `mysql`, `azure`, `flutter` in mixed groups
- `bigquery`/`snowflake`, `angular`/`vue`, `matlab`/`simulink` in
  all-unresolved groups

**Vue and MATLAB are GitHub languages**, so those members are actually
evidenceable via language statistics. A prefix-based guard would exclude
them conservatively.

### Structure frequency (live parser v12, aggregate counts)

| Corpus | Provenance | OR groups | …with an unresolved member | …all-unresolved | Possible AND/OR mixing (lexical) | Single unresolved rows / technical rows |
|---|---|---|---|---|---|---|
| 8c job corpus (15) | tracked, synthetic, previously inspected | 13 | 6 | 3 | 0 | 4 / 60 |
| M10 sources (2) | tracked, previously inspected | 2 | 1 | 0 | 0 | 0 / 2 |
| M11-D (12) | private, previously inspected — not independent | 2 | 1 | 1 | 0 | 4 / 14 |
| M11-F (18) | private, previously inspected | 2 | 1 | 0 | 2 | 17 / 41 |
| M11-G5 (18) | private, previously inspected | 5 | 3 | 0 | 1 | 22 / 54 |
| M11-G9 (14) | private, previously inspected | 1 | 1 | 0 | 0 | **23 / 34** |

**Reading.** Unresolved members occur in most real OR groups (6 of 10
across the private corpora). But OR groups themselves are rare; single
unresolved STRONGLY_OBSERVABLE rows are far more frequent (up to 68% of
technical rows in M11-G9). The larger scoring-integrity exposure is
therefore outside the OR scope this milestone was asked to address.

None of this is new independent data: every corpus was inspected in
earlier milestones. Only aggregate counts were produced; no posting text
or file name.

### Other history

- **G13:** production's `(cloud.aws, unresolved:azure)` denominator risk
  is confirmed and generalised. The production fallback for alias ORs and
  `A or <non-technical>` is confirmed safe.
- **M10D / M10E / M11-A1 / M11-A2:** these regression suites assert the
  *current* group shapes on real tracked SOTI/Manulife postings. Option 3
  breaks them (below).
- **M11-B:** `project_qualification` already refuses unknown observability
  offline. Production has no such guard.
- **G10:** related-concept edges are not evidence entailment, and nothing
  here uses the G10 graph (M1 confirms Docker does not satisfy
  Kubernetes).
- **Milestone 8D.1** made an explicit, tested design decision:
  *"unresolved concepts get no special treatment"*
  (`test_or_group_counts_as_exactly_one_assessable_requirement`,
  `test_unresolved_concept_requirement_scored_like_any_other`). Every
  correction overturns part of that decision.

## Phase 6 — Correction options

**Regression probe.** Each option's minimal illustrative patch was applied
ONLY inside a throwaway clone of HEAD, and the full existing suite was run
there. The working repository was never modified.

| | Option 1: assessor guard (policy B, OR groups only) | Option 1 widened to single unresolved rows | Option 2: partial state (policy C) | Option 3: parser normalization (policy D) |
|---|---|---|---|---|
| Correctness (false NOT_OBSERVED / non-assessable in denominator) | 0 / 0 | 0 / 0 (plus single rows) | 0 / 1 | 0 / 0 |
| Positive evidence | not credited, but kept as a diagnostic | same | credited | **lost** (not even diagnostic) |
| Denominator stability | stable | stable | **unstable** (5/19) | stable |
| Conservative failure | excludes; never invents | same | hides only negatives (biased) | excludes |
| Source provenance | unchanged | unchanged | unchanged | row loses concept ids |
| Public schema | `MatchStatus`/`JobRequirement` unchanged. The API lists the row under its status while `assessable_requirement_count` excludes it, so an **additive** explanatory field is needed (precedent: M9C `interpretation_status`) | same | same consideration for excluded negatives | unchanged (existing category) |
| Matcher API | unchanged | unchanged | unchanged, or a new internal state | unchanged |
| Existing tests broken (excluding G13's "production unchanged" guard, which any patch trips) | **1** (the 8D.1 OR test asserting the contested behaviour) | 6 | **0** | **9** (parser/M10D/M10E/M11-A1/A2/job-fit/manual examples) plus G13 report |
| Fixes K1 flattening? | no | no | no | no (a separate structural guard is needed) |
| Migration complexity | low: `assessment/models.py` (one filter + numerator), `SCORING_VERSION` bump, additive API field, regenerated reports | low/medium | medium: new state plus adapter | medium: parser v13 and regression-gold updates |

## Recommendation (not implemented)

Adopt **Option 1 with policy B, scoped to OR groups**. This is the
smallest change that removes the misleading numbers.

**In the assessor** (scoring step, not the matcher):

- Exclude from the alignment numerator, denominator and sub-scores any
  `alternative_concept_ids` group containing an `unresolved:` member.
- Keep its `RequirementMatch` status, and its matched evidence when
  SUPPORTED, as diagnostics.
- Expose an **additive** per-requirement field so the API's counts stay
  explainable.
- Bump `SCORING_VERSION` (`github_evidence_alignment:v1` → `v2`).

**Why B and not C.**

- Both eliminate false NOT_OBSERVED.
- B keeps one requirement set per job, so it has no selection bias and
  "X of Y" stays comparable across candidates (relevant to the planned
  recruiter mode).
- C is more backward-compatible (0 regressions) and credits positive
  evidence, but its score systematically favours exactly the uncertain
  groups.

**Known costs of B:**

- Positive evidence for such groups no longer moves the score (6 extra
  synthetic outcomes; 3 changed 8c pairs). It stays visible as a
  diagnostic.
- Unresolved **language** members (Vue, MATLAB, Elixir) are treated as
  unevidenceable, which over-excludes. A precise rule would need a
  maintained language allow-list, which is not in the repository.
- It deliberately breaks one existing test, the 8D.1 contract assertion.

**Separate, unresolved issues** (recorded here; not fixed by G15 and not
part of this recommendation):

1. **AND/OR flattening (K1).** The parser merges "(Docker or Kubernetes)
   and Python" into one OR group, giving a false SUPPORTED under every
   scoring policy. Needs a parser structural guard.
2. **Single unknown-technology requirements.** STRONGLY_OBSERVABLE single
   `unresolved:` rows (numpy, SPI/I²C/UART) can essentially never be
   supported. This is the much larger real-world exposure.

### Expected production-file scope (if approved)

- `src/gitscore/assessment/models.py`: `_assessable_matches` scoring
  filter and an alignment numerator computed from the same filter.
- `src/gitscore/assessment/types.py`: `SCORING_VERSION`.
- `src/gitscore/api/schemas.py` and `src/gitscore/api/serialization.py`:
  additive field only.
- Tests:
  - update `tests/test_assessment_engine.py::test_or_group_counts_as_exactly_one_assessable_requirement`
    (the contested behaviour)
  - add new focused tests
- Regenerate the 8c end-to-end reports, and check the evaluation harness's
  `_recompute_alignment`, which recomputes from `supported_count`.

No change to the matcher, `MatchStatus`, `JobRequirement` or the parser.

## Risks and remaining uncertainty

- **Coverage and independence:** synthetic controls by the same author,
  and only 10 OR groups across the inspected real corpora.
- **Evidenceability is approximate:** it is approximated by the
  `unresolved:` prefix; language members are misclassified.
- **Simulation fidelity:** policies were simulated by re-classifying real
  `RequirementMatch` results. The regression probe used illustrative
  patches, not reviewed implementations.
- **Scope:** single unresolved rows are excluded from the recommendation
  by mandate, though they are the larger exposure.
## G14 manifest compatibility (resolved at commit time)

**Reproduced.** With G15's freeze record tracked in a post-commit-equivalent
clone, two G14 tests failed. The G15 freeze was tracked but unregistered,
and `test_manifest_covers_exactly_the_tracked_frozen_files` also
hard-coded 8. The two tests:

- `test_manifest_covers_exactly_the_tracked_frozen_files`
- `test_manifest_is_reproducible_from_committed_history`

**Registration.** G15 was registered additively in
`evaluation/integrity/canonical_hash_manifest.json` (+8 lines, 0 removed;
the original eight records are value-identical). It was attested from the
exact bytes being committed, and accepted only after reconciling three
independent anchors:

- the freeze-time hash reported before any evaluation ran,
  `cd015c96…3fc7`, which the staged blob reproduces;
- the freeze record's own raw and freeze-time LF-normalized hashes;
- `gold_integrity.attest()`.

The registration refuses to overwrite an existing entry.

**Coverage rule.** `exactly 8` was replaced by an explicit registration
rule, `inventory_problems()` in the G14 test file:

- registered set = tracked-freeze set, in both directions;
- duplicate freeze records and duplicate manifest keys are rejected;
- the eight M11-G14 registrations are pinned value by value;
- every later registration must equal its freeze record's freeze-time
  `sha256_lf_normalized`.

Eight adversarial tests prove each violation is detected: unregistered,
missing, duplicated, altered, removed, raw-hash divergence, unreconciled,
wrong record link.

**Reproducibility test.** `test_manifest_is_reproducible_from_committed_history`
is unchanged. It rebuilds from HEAD, so it passes once G15 is committed;
before that commit it cannot, and neither can the builder-refusal test.
Both were verified in post-commit-equivalent clean checkouts.

## Testing and verification

- **G15 focused:** 12 passed.
- **G14:** 111 passed. **G13:** 15 passed, 12 xfailed. **G12:** 37
  passed, 4 xfailed. **G11 / G10:** 23 / 35 passed.
- **assessment / matching / M10D suites:** 36 / 42 / 60 passed.
- **Full suite: 1981 passed, 13 skipped, 18 xfailed** (1969 + 12). No new
  skips; the 18 strict xfails are unchanged.
- No production, matcher, scoring, schema, API or frontend change; no
  G10–G14 implementation change; G14 gold portability preserved.
- Privacy scan of all 10 new files against 1,178 private names, ids and
  text fragments: **0 matches**.
- No LLM calls or dependencies.

## Changed-file inventory (committed together as one research commit)

Plus two G14 compatibility changes:

- `evaluation/integrity/canonical_hash_manifest.json` (additive G15
  registration)
- `tests/test_m11g14_gold_integrity.py` (explicit inventory rule replacing
  "exactly 8", with adversarial tests)

New files:

- `docs/evaluation/MILESTONE_11_G15_MIXED_OBSERVABILITY_OR_SCORING.md`
- `scripts/evaluation_lib/m11g15_build_controls.py`
- `scripts/evaluation_lib/m11g15_or_scoring.py`
- `scripts/evaluation_lib/m11g15_option_regression_probe.py`
- `scripts/evaluate_m11g15_or_scoring.py`
- `evaluation/m11g15/or_scoring_controls.json`
- `evaluation/m11g15/controls_hash_freeze.json`
- `evaluation/m11g15/or_scoring_report.json`
- `evaluation/m11g15/structure_frequency.json` (aggregates; includes
  private-corpus counts)
- `evaluation/m11g15/option_regression_probe.json`
- `tests/test_m11g15_mixed_observability_or_scoring.py`

No production or historical evaluation file is modified.

## Implementation approval questions (for a future milestone)

1. **Policy choice.** Resolved at acceptance: B is preferred, and C is
   rejected.
2. **Overturning 8D.1.** Accept overturning the "unresolved concepts get
   no special treatment" decision, and the `SCORING_VERSION` bump, with
   3 frozen 8c alignment values changing?
3. **Public API.** Approve an **additive** per-requirement scoring-eligibility
   field so API counts stay explainable?
4. **Unresolved languages.** Accept conservatively excluding them (Vue,
   MATLAB, Elixir)? Or authorise a maintained language allow-list?
5. **Single unresolved rows.** Open a separate milestone for them (the
   larger real-world exposure)?
6. **K1 flattening.** Open a separate parser milestone for the AND/OR
   flattening (a parser version bump)?
7. **Commit mechanics.** Resolved; see "G14 manifest compatibility".

## Commit status

Committed as `test: evaluate mixed-observability OR scoring integrity`
after all authorization gates passed. No production implementation. G16
has not started.
