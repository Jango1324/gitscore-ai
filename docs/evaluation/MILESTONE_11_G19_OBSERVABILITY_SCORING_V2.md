# Milestone 11-G19 — Observability-Aware Scoring v2

Status: **production implementation, uncommitted, ready for review.**
This implements M11-G18's evaluated and approved policy B/C.

- `SCORING_VERSION` `github_evidence_alignment:v1` → **`v2`**.
- Parser stays `job_description_parser:v13`; matcher stays
  `requirement_matcher:v1`.
- No change to parsing, matching, `MatchStatus`, `JobRequirement`, the
  evidence extractors or the concept registry.
- No frozen gold, frozen report or G18 result was rewritten. No LLM call.

## Why scoring v2 is necessary

Under v1, every requirement the matcher evaluated counted toward the
GitHub Evidence Alignment score. That included requirements where GitHub
evidence could never exist for some or all acceptable alternatives:

- **Mixed OR:** for "AWS or Azure", an Azure-qualified candidate scored
  NOT_OBSERVED (0/1). Azure is unregistered, and no extractor can emit it.
- **Standalone unknown technology:** for "Python, SPI, I2C, UART", a
  candidate who truly has all four scored 25 (1/4). The three interfaces
  can only ever be NOT_OBSERVED.

G18 measured this on 106 frozen outcomes:

- 27 wrong NOT_OBSERVED results counted in the score, 13 of them for
  candidates who truly qualify;
- 33 uncheckable requirements in the denominator.

In the inspected private postings, 50 % of technical rows were of this
kind.

## Capability versus evidence

- **Evidence** is a fact about a candidate: does this profile have
  sufficient evidence for a concept? `matching.support`, unchanged.
- **Capability** is a fact about GitScore's extractors: can any extractor
  *ever* emit evidence for this concept id? New, internal:
  `src/gitscore/evidence/capability.py`.

| Pathway | Extractor (the source of truth) | Covers |
|---|---|---|
| `README_MENTION` | `readme.py` scans `readme_safe_aliases()` of every registry concept | a concept with ≥ 1 README-safe alias |
| `REPOSITORY_LANGUAGE` | `languages.py` resolves GitHub language names through the registry | a concept the registry itself categorises `"language"` |
| `DOCKER_FILES` | `docker.py` | `DOCKER_CONCEPT_ID` |

Dependency manifests are **not** a capability ground: they resolve
*arbitrary* package names, so counting them would make every registered
concept "assessable" by registration alone.

Each concept gets one of three states, and every decision carries
deterministic reasons:

| State | Applies to |
|---|---|
| **ASSESSABLE** | a concept covered by ≥ 1 pathway |
| **NOT_ASSESSABLE** | a registered concept with no pathway, or an unknown id |
| **UNRESOLVED** | every `unresolved:<term>` id |

Properties:

- **Current registry:** all 39 registered concepts are ASSESSABLE.
  `language.c` qualifies only through repository language statistics,
  since its bare "c" alias is README-unsafe.
- **Validated pathways:** a test runs the real README, language or Docker
  extractor on synthetic input for every declared pathway and confirms it
  emits that concept id.
- **No automatic scoring for undetected concepts:** a future concept with
  no pathway is NOT_ASSESSABLE automatically (tested).
- **No hardcoded list:** the module names no concept id or language,
  apart from importing the Docker extractor's own constant (tested).
- **No candidate input:** `concept_capability()` takes only
  `(concept_id, registry)`.

## Score eligibility (candidate-independent)

`assessment.models.score_eligibility(requirement)` decides from the job
requirement alone:

1. If the matcher would return NOT_ASSESSABLE (NOT_OBSERVABLE, or no
   concept mapping: non-technical claims and the 9A/6B.1/G17
   placeholders), the row is **not eligible**, reason `not_assessable`.
2. Otherwise it is eligible **only if every acceptable alternative is
   ASSESSABLE**. A single requirement is a group of one. An OR group is
   counted once or excluded once, never partially.

Exclusion reasons are a closed set, `assessment.AlignmentExclusionReason`:

| Reason | Meaning |
|---|---|
| `not_assessable` | the matcher had nothing to check (NOT_ASSESSABLE status) |
| `unresolved_technology` | no alternative is assessable; the blocking members are UNRESOLVED |
| `unresolved_alternative` | a mixed OR: ≥ 1 alternative is assessable, the others are UNRESOLVED |
| `technology_without_evidence_pathway` | no alternative is assessable; some member is a registered concept with no pathway |
| `alternative_without_evidence_pathway` | a mixed OR where some member has no pathway |

### Mixed-observability OR behaviour

"AWS or Azure" is excluded as a whole.

- **Not penalised:** absence of AWS evidence says nothing about an
  Azure-qualified candidate, so the group can't count as a negative.
- **Not credited:** counting it only when AWS evidence exists would make
  the denominator depend on the candidate (rejected in G15 and G18).

The row keeps `status` (`supported` or `not_observed`), `matched_concept_ids`
and its evidence.

### Standalone unresolved requirements

Terraform, NumPy, Kafka, SPI, I2C, UART, and fabricated ids such as
`unresolved:c` or `unresolved:alternatively` are excluded
(`unresolved_technology`). They stay visible with their status.

## Numerator and denominator

- **`JobAssessment._assessable_matches`** is still the one "assessable"
  definition. It now means: status ≠ NOT_ASSESSABLE **and** eligible.
- **Denominator:** `assessable_count` = number of eligible rows.
- **Numerator:** SUPPORTED rows **within the eligible set**. It no longer
  uses `match_analysis.supported_count`, which can now include excluded
  SUPPORTED rows.
- **Sub-scores** (`required` / `preferred`) and
  `low_parser_confidence_count` use the same eligible set.
- **Unchanged formula:** `_round_half_up_percentage`. The score is `None`,
  never 0, when no requirement is eligible.
- **New accessors:**
  - module-level `counts_toward_alignment(match)` and
    `alignment_exclusion_reason(match)`, shared by `JobAssessment` and the
    API serializer;
  - `excluded_from_alignment_matches()`;
  - `excluded_from_alignment_count`.
- **Excluded rows keep their meaning:** a SUPPORTED row is never turned
  into NOT_OBSERVED, and a NOT_OBSERVED row is never turned into
  NOT_ASSESSABLE.

## API (additive)

| Field | Where | Meaning |
|---|---|---|
| `counts_toward_alignment: bool` | `RequirementOut` | in the numerator/denominator set |
| `alignment_exclusion_reason: str \| null` | `RequirementOut` | one of the closed set above; `null` exactly when counted |
| `excluded_from_alignment_count: int` | `AssessmentOut` | `supported` + `not_observed` rows that do not count |

The new fields follow the existing response convention: required,
server-populated, enum values serialized as strings.

Reconciliation: `len(supported) + len(not_observed) ==
assessable_requirement_count + excluded_from_alignment_count`. This is
tested on unit cases and on every corpus in the v1/v2 comparison.

Compatibility:

- No field was removed or renamed, and the `status` and
  `interpretation_status` meanings are unchanged. A test pins both field
  sets.
- `assessable_requirement_count` keeps its name and is still the
  alignment denominator. What it counts changed with v2, which the
  `versions.scoring` bump announces.
- Every `not_assessable` row reports `counts_toward_alignment=false`,
  reason `not_assessable`. It is not part of `excluded_from_alignment_count`,
  because it was never evaluated.

## What the frontend communicates

Minimal change, no redesign:

- **Per-row disclosure:** each evaluated row that is excluded (in the
  supported or not-observed list) shows a neutral **"Not counted in
  alignment score"** badge. A short explanation keyed by
  `alignment_exclusion_reason` follows; for example: "At least one
  acceptable option in this requirement cannot be checked from GitHub
  evidence, so GitHub evidence alone cannot decide it either way."
  Evidence is still listed.
- **Counted rows:** a counted not-observed row has no badge, so the two
  kinds are visibly different.
- **Not-assessable rows:** these keep their existing section and get no
  badge.
- **Headline:** always states "The score covers only requirements
  GitScore can check from GitHub evidence." When `excluded_from_alignment_count`
  > 0, it adds "N evaluated requirements are not counted because not
  every acceptable option can be checked from GitHub evidence".
  "Not available" is still used for an undefined score, never 0.
- **Wording:** the copy never says or implies that an excluded
  requirement is irrelevant, that the candidate lacks the skill, or that
  anything is a penalty (tested).

## Regression tests written before the implementation

`tests/test_m11g19_observability_scoring_v2.py` covers all 20 required
scenarios plus reconciliation and G18 equivalence.

Against scoring v1, **22 failed and 2 passed**. The 2 passing were the
unchanged-behaviour guards (assessable standalone; fully assessable OR).

- **12 v1 failures were real score defects,** with the assertion showing
  the actual v1 numbers:

  | Case | v1 | Expected |
  |---|---|---|
  | Unassessable standalone | 67 (2/3) | 100 (2/2) |
  | Unresolved technical concepts | 25 (1/4) | 100 (1/1) |
  | Mixed OR, AWS evidence | 100 (1/1) | undefined |
  | Mixed OR, no evidence | 0 (0/1) | undefined |
  | Azure or GCP | 0 (0/1) | undefined |
  | Multiple independent | 75 (3/4) | 100 (3/3) |
  | Required / preferred sub-scores | 1/2 and 1/3 | 1/1 and 1/2 |
  | Unregistered-language fallback | 67 (2/3) | 50 (2/2 → 1/2) |
  | Duplicate alternatives | 0 (0/1) | undefined |
  | No eligible requirement | 0 | undefined |
  | Live-v2-equals-G18 check | — | fails on v1 |
  | G18 acceptance metrics | — | fail on v1 |

- **The other 10** failed because the v2 contract (the API fields or the
  capability module) did not exist.

The file now has **33 tests, all passing.** The extra 9 cover:

- capability pathways validated by the real extractors;
- unresolved and unknown ids;
- no hardcoded lists;
- the closed reason set;
- the "without evidence pathway" reasons reaching the API;
- additive API fields;
- comparison invariants;
- private-aggregate key safety.

## Actual v1 vs v2 comparison

`scripts/evaluate_m11g19_v1_v2.py` runs the real parser, matcher,
assessor **and API serializer** of:

- **v1:** the last scoring-v1 commit `ac4a15e`, in a throwaway clone;
- **v2:** the working tree.

Both run over identical corpora, and the output goes to
`evaluation/m11g19/v1_v2_comparison.json`. Nothing is simulated.

**Unchanged in every corpus:** match statuses, matched concepts and
evidence counts, all 0 differences. Count reconciliation and reason
consistency fail 0 times.

### G18 frozen controls (26 controls, 54 candidate pairs, 106 outcomes)

- **Live v2 equals G18's simulated policy C (declared) on 54 / 54 pairs**
  (score, eligible SUPPORTED, denominator). This was measured, not
  assumed.
- Wrong NOT_OBSERVED counted: **27 → 0.**
- Uncheckable rows scored: **33 → 2.** Both are control 25, where the
  parser turns a narrative sentence into REQUIRED Python/Docker rows. That
  is a separate parser defect.
- Eligibility is candidate-independent. It is tested on every control and
  with 40 random evidence sets on one mixed job.

| Direction | Count | Cases (v1 → v2) |
|---|---|---|
| Unchanged | 17 | — |
| **Increased** | 10 | 09 (67 → 100), 10 three-true-no-Elixir-evidence (67 → 100), 11 (67 → 100), 12 (25 → 100), 13 (33 → 100), 18 Python-only (25 → 33), 18 three+Azure (75 → 100), 21 python+docker (67 → 100), 21 python-only (33 → 50), 25 (67 → 100) |
| **Decreased** | 2 | 10 Python+Elixir evidence (67 (2/3) → 50 (1/2)), 23 Python+MATLAB evidence (67 → 50) |
| **Denominator only** | 8 | 09/10/11/12/13/18/23 "none" candidates, 18 all-four (100 (4/4) → 100 (3/3)) |
| **Became undefined** | 17 | every candidate of 02, 03, 04, 05, 06, 07, 15, 17: the job's only requirement is uncheckable |

- **Why some scores decrease:** the only decreases are lost credit for
  genuine evidence for an **unregistered GitHub language**: Elixir and
  MATLAB, which language statistics *can* evidence. Excluding them is a
  **conservative policy choice** made because no language vocabulary is
  declared. It is not a finding that these languages are unassessable.
- **Why some scores become undefined:** with nothing checkable left,
  there is no alignment to report. `None` ("Not available") is a different
  fact from 0.
- **Why most changes are increases:** the removed rows could only ever be
  NOT_OBSERVED.

### G15 frozen controls (35 candidate pairs)

15 unchanged, 3 increased, 4 denominator-only, 13 became undefined, 0
decreased.

- Under v2, the real assessor equals G15's simulated policy B on every
  pair (fidelity assertion).
- The frozen G15 report reproduces byte for byte.

### G16/G17 compound controls (414 fixture outcomes)

403 unchanged, 3 increased, 2 denominator-only, 6 became undefined.

- **045** "Docker, Kubernetes or Terraform…" is excluded because of its
  `unresolved:terraform` member.
- **058**'s fabricated `unresolved:alternatively` row leaves the
  denominator.
- G17 containment is intact: rows and statuses are identical, and false
  SUPPORTED stays at 7.
- G16's frozen metric 4 (false declines of representable controls) goes
  from 24 to 25. The one addition is 045, which is no longer scored at
  all. The G16 test pins exactly this.

### Frozen 8c v1 and v1.1 (identical results)

6 of 12 pairs change, exactly as G18 predicted. The frozen 8c gold and
reports are untouched.

| Pair | v1 | v2 | Excluded |
|---|---|---|---|
| karpathy × frontend_01 | 50 (3/6) | **60** (3/5) | Angular-or-Vue (`unresolved_technology`) |
| sindresorhus × frontend_01 | 67 (4/6) | **80** (4/5) | Angular-or-Vue |
| sindresorhus × robotics_controls_01 | 25 (1/4) | **33** (1/3) | MATLAB-or-Simulink |
| torvalds × data_science_01 | 20 (1/5) | **25** (1/4) | NumPy |
| torvalds × embedded_firmware_01 | 20 (1/5) | **50** (1/2) | SPI, I2C, UART |
| Jango1324 × embedded_firmware_01 | 0 (0/5) | 0 (0/2) | SPI, I2C, UART (denominator only) |

### M10 SOTI / Manulife

Parser and matcher output is unchanged. With an empty candidate, SOTI's
single technical row (a mixed OR) makes its score go from 0 (0/1) to
undefined. Manulife is unchanged.

### Previously inspected private postings

Not fresh holdouts; integer counts only, in
`evaluation/m11g19/private_v1_v2_aggregates.json`.

| | M11-D | M11-F | M11-G5 | M11-G9 | Total |
|---|---|---|---|---|---|
| Postings | 12 | 18 | 18 | 14 | 62 |
| Technical rows | 14 | 40 | 54 | 34 | 142 |
| Denominator rows v1 → v2 | 14 → 9 | 40 → 23 | 54 → 29 | 34 → 10 | 142 → 71 |
| Excluded (v2) | 5 | 17 | 25 (3 mixed OR) | 24 (1 mixed OR) | **71 (50 %)** |
| Postings with any exclusion | 1 | 8 | 9 | 6 | 24 |
| Postings with no eligible requirement, v1 → v2 | 7 → 7 | 7 → 8 | 5 → 6 | 5 → 7 | 24 → 28 |

## Historical results kept versioned

The G15, G16 and G18 frozen reports are byte-identical and still
reproduce. Their scripts' fidelity checks against the real assessor are
now scoring-version-aware:

| Scoring version | G15 must equal | G18 must equal |
|---|---|---|
| v1 | simulated policy A | simulated policy A |
| v2 | simulated policy B | simulated C (declared) |

The simulations and their outputs did not change.

G16's reproducibility test, under v2:

- requires rows and statuses identical to the frozen Option D simulation;
- requires `assessable` / `score` to equal a v2 recomputation from the
  frozen statuses;
- allows changes only in controls 045 and 058.

The other existing tests that changed fall into three groups:

- **8D.1 decision overturned deliberately:**
  - `test_or_group_counts_as_exactly_one_assessable_requirement` still
    checks that a fully assessable group counts once, and now also checks
    that a mixed group is excluded once, keeping its status.
  - `test_unresolved_concept_requirement_scored_like_any_other` is renamed
    `…_excluded_from_score_but_keeps_evidence`; its assertions are
    stronger.
- **Fixture migration** (synthetic `unresolved:cN` filler → registered
  concepts; same numbers): the 62.5 and 72.5 rounding tests,
  `test_alignment_score_bounds`, and
  `test_low_parser_confidence_count_never_exceeds_assessable_count`.
- **Legitimately changed v2 values:**
  - the 7B adversarial example: React and Kubernetes now use their
    registered ids; GitHub Actions is still unregistered and excluded, so
    75 (6/8) becomes **71 (5/7)**, and the uncapped-headline property
    holds;
  - `test_api_routes` scoring literal `v1` → `v2`, plus checks for the new
    fields.

None of these was removed or weakened. Each one has an explanatory
comment.

## Remaining known limitations

1. **Unregistered GitHub languages** (Elixir, Zig, Vue, MATLAB) are
   conservatively excluded, and their evidence no longer moves the score.
   It stays visible. A declared language vocabulary would need separate
   approval.
2. **Parser defects remain:**
   - fabricated `unresolved:` terms (generic words, fragments, bare "C");
     these now show as "not counted" rows instead of penalties;
   - narrative-as-REQUIRED (control 25);
   - alias-OR placeholders ("Go or Golang");
   - mixed lists without a conjunction (G17 residual 043);
   - bare "Go" (018).
3. **Large real-world shift:** half of the technical rows in the inspected
   postings leave the denominator, so scores rise more often than they
   fall and become "Not available" more often.
4. **Capability is inferred from the extractors' code:** a new extractor
   or registry category must be reflected in `capability.py`. The
   validation test catches a declared pathway that does not actually
   emit, but not a new pathway nobody declared.
5. **G17's comparison script can't be re-run usefully after commit:**
   `scripts/evaluate_m11g17_v12_v13.py` clones HEAD as "v12", so it asserts
   after that commit. That is a pre-existing limitation, not changed here.
   G19's comparison pins its v1 reference commit.

## Verification

| Check | Result |
|---|---|
| G19 focused tests | 33 / 33 |
| Full backend suite (working tree, uncommitted) | **2092 passed, 13 skipped, 18 xfailed, 4 failed** |
| Frontend tests (vitest) | 53 passed (46 → 53) |
| `tsc --noEmit` | clean |
| `next build` (includes TypeScript) | succeeds |
| G14 integrity | manifest still has 11 entries; no frozen file or freeze record touched |

Notes on the backend suite:

- **The 4 failures** are exactly the HEAD-relative "production unchanged"
  guards of G13, G15, G16 and G18. They fail only while `src/` is
  uncommitted and pass in a post-commit checkout.
- **Counts:** 2092 + 4 = 2063 + 33 new tests.
- **Skips:** the same pre-existing M10E (10) and M11-A2 (3); none new.
  All 18 strict xfails are intact.

**Post-commit-equivalent clean checkouts** (HEAD plus all 31 G19 files
committed in a throwaway clone):

| | `autocrlf=true` | `autocrlf=false` |
|---|---|---|
| Full suite | **2072 passed, 37 skipped, 18 xfailed, 0 failed** | **2072 passed, 37 skipped, 18 xfailed, 0 failed** |
| Freeze verifiers | all pass (newline-only mismatches) | all pass |

- The four guards pass there.
- **Skip counts:** 37 vs 13 is the private datasets being absent from
  clean clones.
- **Not run:** native Linux/macOS.

**Publication scan:** the added content of all 31 files was checked
against 1,178 private-posting phrases and ids, with 0 hits. The private
aggregates file holds integer counts only (test-enforced).

## Commit status

Not committed and not pushed. No freeze was added, so no manifest
registration is needed.
