# Milestone 11-G18 — Observability-Aware Scoring Eligibility

Status: **evaluation-first research result. No production change.**

- `src/gitscore` is byte-identical to HEAD (test-enforced).
- Matcher, scoring formula, `MatchStatus`, `JobRequirement`, public
  schemas, API, frontend, G10–G13 implementations and all frozen gold are
  unchanged. Parser is `job_description_parser:v13`.
- No LLM call. No private posting text is published (private corpora
  appear only as integer counts).
- Every changed score below is a **counterfactual result of a simulated
  policy** on the real production `RequirementMatch` objects, not a
  correction of any frozen report.

**Provenance of every number in this document.**

| Kind | What it is | Where |
|---|---|---|
| **Production results** | Output of the real, unmodified v13 parser, matcher and assessor (`github_evidence_alignment:v1`) | the "A / Production" columns |
| **Offline simulated policy results** | Policies B–E re-classifying those same production `RequirementMatch` objects; counterfactual, never deployed | every non-A column, every "would change" figure, the hypothetical v2 8c differences |
| **Synthetic development controls** | 26 G18 controls (and G15's 19), authored by the same author as G10–G17, not independently annotated | Phases 2–5 |
| **Previously inspected private material** | M11-D/F/G5/G9 postings, inspected in earlier milestones (not independent), reported as integer counts only | Phase 7 private table |

| Artifact | Path |
|---|---|
| Frozen controls (26 controls, 54 candidate variants, 106 outcomes) | `evaluation/m11g18/eligibility_controls.json`, `controls_hash_freeze.json` |
| Control builder + frozen contract rule | `scripts/evaluation_lib/m11g18_build_controls.py` |
| Capability classifier + policy simulation | `scripts/evaluation_lib/m11g18_eligibility.py` |
| Runner (G18 + G15 controls, G16/G17 controls, frozen 8c, M10) | `scripts/evaluate_m11g18_scoring_eligibility.py` → `evaluation/m11g18/eligibility_report.json` |
| Private aggregates (opt-in, counts only) | `--private-corpora` → `evaluation/m11g18/private_eligibility_aggregates.json` |
| Regression probe (throwaway clones only) | `scripts/evaluation_lib/m11g18_option_regression_probe.py` → `evaluation/m11g18/option_regression_probe.json` |
| Focused tests (29) | `tests/test_m11g18_observability_aware_scoring.py` |

## Phase 0 — Baseline (verified)

- HEAD `1faf5d78bda680c2c6bde59970265a33caa9be82` = `origin/main`, branch
  `main`, no tracked diffs.
- Parser `job_description_parser:v13`; G17 containment active; G15 Policy
  B not implemented.
- Full suite at that HEAD: 2032 passed, 13 skipped, 18 xfailed.
- G14 manifest: 10 entries. 18 private / untracked M11 entries preserved.

## Phase 1 — Observability contracts (from code)

### Six different things that are easy to conflate

| | Meaning | Where it lives today |
|---|---|---|
| **A. Recognized technology** | The parser saw a technology-shaped term. | Parser output: a registered `concept_id` **or** an `unresolved:<term>` id. Unknown terms become `unresolved:` ids only in enumerations/OR segments; a single "Experience with X is required." becomes the 9A `unresolved_requirement` placeholder instead. |
| **B. Registered concept** | The term resolves to one of the 39 entries in `concepts/registry.py`. | `ConceptRegistry`. |
| **C. Supported evidence detector** | Some extractor can *emit* evidence carrying that concept id. | Implicit in the extractors (below). Nothing declares it. |
| **D. GitHub-assessable requirement** | Every acceptable alternative is C. | **Does not exist.** `github_observability` is set per requirement by `observability_for_technical()` = STRONGLY_OBSERVABLE for *every* technical row, registered or not. |
| **E. Candidate evidence observed** | This candidate's profile has sufficient evidence for a member. | `has_sufficient_evidence()` → `MatchStatus.SUPPORTED`. |
| **F. Eligible for numerical scoring** | Counted in numerator/denominator. | `_assessable_matches()` = status ≠ NOT_ASSESSABLE. So eligibility today = "matcher evaluated it", i.e. A, not D. |

### Which extractor can emit which ids (the real detector contract)

| Extractor | Emits | Unknown terms |
|---|---|---|
| `dependency_evidence.py` (pip / npm manifests) | registered concepts whose alias equals the package name | **skipped** (counted only in `unknown_dependency_count`) |
| `docker.py` | `infra.docker` | — |
| `languages.py` (GitHub language stats ≥ 5 %) | registered concept, **or `unresolved:<language>`** | emitted — the only production source of `unresolved:` evidence |
| `readme.py` | registered concepts via README-safe aliases only | never |

Consequences, established by execution and not assumed:

- **Every one of the 39 registered concepts has at least one declared
  pathway** (README-safe alias and/or structured alias resolution; Docker
  files for `infra.docker`). `language.c` has no README-safe alias and is
  reachable only through language stats or a dependency.
- **The GitHub-language fallback is real.** `unresolved:elixir`,
  `unresolved:zig`, `unresolved:vue`, `unresolved:matlab` *can* be
  SUPPORTED, by language statistics. So "unresolved" ≠ "unassessable".
- **But nothing in the repository declares which terms are GitHub
  languages.** Whether `unresolved:<t>` can ever be emitted cannot be
  decided candidate-independently from repository facts. `unresolved:azure`,
  `:terraform`, `:numpy`, `:kafka`, `:spi` can essentially never be
  SUPPORTED.
- **The parser also fabricates `unresolved:` ids**: a bare "C" (a
  prose-unsafe alias) becomes `unresolved:c`, which can never match the
  `language.c` evidence GitHub produces; "Alternatively, …" becomes
  `unresolved:alternatively` (G17 limitation 5). In the private corpora,
  17 of 75 unresolved mentions are generic words or parse fragments, not
  technologies (local review; counts only).

### Matcher / assessor / API facts

- `match_requirement`: NOT_OBSERVABLE → NOT_ASSESSABLE; no concept → NOT_ASSESSABLE;
  otherwise SUPPORTED if *any* member has sufficient evidence, else
  NOT_OBSERVED. Members are never individually qualified.
- `JobAssessment`: `_assessable_matches` = SUPPORTED + NOT_OBSERVED;
  `alignment_score = _round_half_up_percentage(match_analysis.supported_count, assessable_count)`,
  `None` when 0. Sub-scores and `low_parser_confidence_count` share the
  same filter. **The numerator is read from `JobMatchAnalysis`, not from
  the filter** — any eligibility rule must change both.
- API: `RequirementOut.status` (3 values), `interpretation_status`
  (`recognized` / `non_technical` / `unparsed_placeholder`, M9C additive),
  `AssessmentOut.assessable_requirement_count`. The frontend shows the
  headline score plus the three status lists; it does not reconcile counts.
- Versions: `MATCHER_VERSION = requirement_matcher:v1`,
  `SCORING_VERSION = github_evidence_alignment:v1`. `assessment/types.py`
  says to bump `SCORING_VERSION` when scoring rules change.
- Existing helpers already mark the prefix: `JobRequirement.is_unresolved_concept`
  and `has_unresolved_alternative`.

### Root cause (both defects)

Eligibility is "the matcher could evaluate it", and the matcher evaluates
anything with a concept id. No layer asks "can any extractor ever produce
evidence for every acceptable alternative?". Mixed OR groups and
standalone unresolved rows therefore enter the denominator, and since
their unassessable members can never be SUPPORTED, they can only ever
add NOT_OBSERVED.

## Phase 2 — Reproduced defects (real parser, matcher, assessor)

Capability per row member: A = ASSESSABLE, U = UNRESOLVED (`?` prefix =
`unresolved:`). Score = score (supported / denominator).
"Contract" = the frozen declared contract (Phase 3).

| Ctl | Production rows | Caps | Candidate | Production status | **Production** | C (declared) | Contract |
|---|---|---|---|---|---|---|---|
| 01 | docker+k8s | A,A | docker / none / k8s (no evidence) | S / NO / NO | 100 (1/1) / 0 (0/1) / 0 (0/1) | same | same |
| 02 | aws+?azure (required) | A,U | aws | S | 100 (1/1) | None (0/0) | None (0/0) |
| 02 | | | **Azure-only, truly qualified** | NO | **0 (0/1)** | None | None |
| 03 | aws+?azure (preferred) | A,U | aws / Azure-only | S / NO | 100 / **0** | None / None | None |
| 04 | ?azure+?gcp | U,U | Azure (true) / none | NO | **0 (0/1)** | None | None |
| 05 | ?ansible+?terraform | U,U | Terraform (true) | NO | **0 (0/1)** | None | None |
| 06 | ?elixir+?zig | U,U | Zig language evidence | S | 100 (1/1) | None | None |
| 07 | react+?vue | A,U | Vue language evidence / react | S / S | 100 / 100 | None / None | None |
| 08 | postgresql | A | postgres / none | S / NO | 100 / 0 | same | same |
| 09 | python; docker; ?terraform | A;A;U | all three true | S,S,NO | **67 (2/3)** | 100 (2/2) | 100 (2/2) |
| 10 | python; docker; ?elixir | A;A;U | python + Elixir evidence | S,NO,S | 67 (2/3) | 50 (1/2) | 50 (1/2) |
| 11 | python; pandas; ?numpy | A;A;U | all three true | S,S,NO | **67 (2/3)** | 100 (2/2) | 100 (2/2) |
| 12 | python; ?spi; ?i2c; ?uart | A;U;U;U | all four true | S,NO,NO,NO | **25 (1/4)** | 100 (1/1) | 100 (1/1) |
| 13 | verilog; ?c; ?spi | A;U;U | C + Verilog evidence | S,NO,NO | **33 (1/3)** | 100 (1/1) | 100 (2/2) |
| 14 | education; soft skill; docker | –;–;A | docker | NA,NA,S | 100 (1/1) | same | same |
| 15 | ?azure+?microsoft_azure | U,U | Azure (true) | NO | **0 (0/1)** | None | None |
| 16 | alias placeholder ("Go or Golang") | – | go | NA | None | None | 100 (1/1) |
| 17 | docker+python+?terraform (ambiguous list) | A,A,U | python | S | 100 (1/1) | None | None |
| 18 | python; docker; aws+?azure; postgres | A;A;A,U;A | three + Azure (true) | S,S,NO,S | **75 (3/4)** | 100 (3/3) | 100 (3/3) |
| 18 | | | all four with aws | S,S,S,S | 100 (4/4) | 100 (3/3) | 100 (3/3) |
| 19 | G17 placeholder; postgres | –;A | python + postgres | NA,S | 100 (1/1) | same | same |
| 20 | `unresolved_requirement` placeholder | – | Terraform (true) | NA | None | None | None |
| 21 | python; docker; ?kafka (preferred) | A;A;U | python + docker | S,S,NO | **67 (2/3)** | 100 (2/2) | 100 (2/2) |
| 22 | non-technical OR placeholder | – | docker / clearance | NA | None | None | None |
| 23 | python; docker; ?matlab | A;A;U | python + MATLAB evidence | S,NO,S | 67 (2/3) | 50 (1/2) | 50 (1/2) |
| 24 | kubernetes | A | Docker evidence only | NO | 0 (0/1) | same | same |
| 25 | python; docker; ?terraform from **narrative** | A;A;U | python + docker | S,S,NO | 67 (2/3) | 100 (2/2) | None (0/0) |
| 26 | aws | A | Azure-only (true) | NO | 0 (0/1) | same | same |

(Full per-candidate detail: `eligibility_report.json` → `g18_controls.results`.)

**Misrepresentation verdicts (production).**

- **Mixed OR, unjustified NOT_OBSERVED** (an Azure-only candidate is
  "not observed" for "AWS or Azure"): 02, 03, 18.
- **All-unassessable OR, unjustified NOT_OBSERVED**: 04, 05, 15.
- **Standalone unassessable rows deflating the score**: 09, 11, 12, 13,
  21 (Terraform, NumPy, SPI/I2C/UART, Kafka, fabricated `unresolved:c`).
- **Justified**: 01, 08, 14, 24, 26. Control 26 shows that a standalone
  registered AWS row correctly stays NOT_OBSERVED for an Azure-only
  candidate. Azure is not an acceptable alternative there.
- **Pre-existing parser defects, not scoring defects** (recorded, not
  fixed): 13 (`unresolved:c`), 16 (alias OR → placeholder), 17 (ambiguous
  list flattened; G17 residual pattern), 25 (narrative → REQUIRED rows).

Totals on the 106 frozen outcomes: **27 false NOT_OBSERVED counted in the
score, 13 of them where the candidate truly qualifies; 33 uncheckable
requirements counted in the denominator.** On G15's 55 outcomes: 12 / 6 / 18.

## Phase 3 — Frozen scoring contract

Controls were frozen (G14 portable scheme, contract `crlf-to-lf/v1`)
**before** the matcher, assessor or any policy ran on them:
`sha256_lf_normalized = b9f155b2776a151b691a6cf837924d4549278338651a09f7db17a9a9834bf859`.
Job texts were parsed while authoring, only to confirm each phrasing
produces rows; this is disclosed in the file. Same author as G10–G17; not
independently annotated.

Annotated facts: each member's evidenceability (`registry` /
`language_stats` / `none` / `non_technical`), the structure (`single`,
`or`, `alias`, `ambiguous_list`, `compound`, `non_technical`,
`non_requirement`), necessity, candidate evidence, and true
competencies. Expectations come from the written rule
`expected_contract()`, and a test pins every frozen expectation to it.

**Candidate-independent eligibility rule.** A requirement is eligible iff
it is a scoreable structure (`single` / `or` / `alias`) and every
acceptable alternative is evidenceable. The rule has two frozen readings:

- **declared** (every member registered). This is what the repository
  can establish today.
- **ideal** (registered or GitHub language). This needs a declared
  language vocabulary.

Eligible → SUPPORTED if an evidenceable member has evidence, else
NOT_OBSERVED. Not eligible → excluded from the score; positive evidence
may stay visible.

| # | Invariant | How it is checked |
|---|---|---|
| 1 | Unassessable standalone requirements do not enter scoring | metric 3 |
| 2 | Mixed OR not penalized for absent evidence on the observable branch | metric 1 = 0 |
| 3 | Valid positive evidence stays visible in diagnostics | metric 4b |
| 4 | Fully observable requirements continue to count | metric 5b / contract match |
| 5 | Eligibility independent of the candidate | metric 8; random-evidence property test |
| 6 | Each OR counts at most once | metric 7 |
| 7 | No alternative's evidence satisfies an unrelated requirement | metric 6, M1-style control 24 |
| 8 | Unsupported/ambiguous concepts never positive by assumption | eligibility never consults evidence; UNRESOLVED ≠ ASSESSABLE |
| 9 | No UNKNOWN necessity fabricated into REQUIRED | metric 10 |
| 10 | Source spans and provenance kept | span test; statuses/evidence retained |
| 11 | Formula unchanged | every score = `_round_half_up_percentage` |
| 12 | No eligible requirement → score undefined | controls 04, 05, 15, 20 → `None` |

## Phase 4 — Capability classification

`concept_capability(concept_id)` (evaluation-only, in
`m11g18_eligibility.py`) returns a capability and the reasons for it:

| Concept id | Capability | Reason |
|---|---|---|
| registered, with a README-safe alias or structured alias | **ASSESSABLE** | names the pathways (all 39 today; `language.c` via structured sources only) |
| registered, no pathway | **NOT_ASSESSABLE** | "registered, but no extractor declares a pathway" (none today; a test proves registration alone is not enough) |
| `unresolved:<t>` | **UNRESOLVED** | only the language extractor emits unresolved ids, only for GitHub language names, and no language vocabulary is declared |
| `unresolved:<t>` + a supplied language vocabulary | ASSESSABLE if `t` ∈ vocabulary, else NOT_ASSESSABLE | — |
| no concept / NOT_OBSERVABLE row | not eligible | existing NOT_ASSESSABLE path |

`requirement_eligibility(requirement)` decides from the requirement
alone: eligible iff it is evaluable and **every** member is ASSESSABLE. It
labels the reason (`standalone`, `mixed_or_group`,
`or_group_without_assessable_member`, `not_observable`,
`no_concept_mapping`).

**Can an existing type carry this?**

- **`GithubObservability` on `JobRequirement`:** no. It is set by the
  parser from the requirement *type*. The matcher deliberately evaluates
  PARTIALLY_OBSERVABLE rows that have a concept, and re-purposing it would
  change matcher behaviour and the parser.
- **`MatchStatus`:** no. Folding eligibility into the status destroys
  the positive-evidence diagnostic (that is policy D).
- **`interpretation_status`:** no. It answers "why NOT_ASSESSABLE", and
  an excluded row can be SUPPORTED.
- **`is_unresolved_concept` / `has_unresolved_alternative`:** they compute
  B's prefix today, but encode a registry fact, not a detector fact.

So eligibility needs one small **internal** concept: a capability
function plus a requirement-level eligibility predicate. No public enum is
required.

**Language vocabulary.** No hardcoded language list was used to pass
controls. The `C_capability_oracle` policy uses the annotators'
`language_stats` facts (Elixir, Zig, Vue, MATLAB) **only** to size what a
declared vocabulary would buy. It is labelled as an oracle and is not
implementable from the repository.

## Phase 5 — Policy comparison

- **A**: production.
- **B**: exclude any row with an `unresolved:` member (G15 B widened to
  standalone rows).
- **C (declared)**: the capability contract with no vocabulary.
- **C (oracle)**: the capability contract plus the annotated language
  vocabulary.
- **D**: re-route to the 6B.1 placeholder.
- **E**: G15's rejected asymmetric policy.

B, C and D keep production's status and evidence; D discards them.

**G18 frozen controls (106 outcomes, 54 candidate pairs, 26 controls; 38 positive-evidence outcomes)**

| Metric | A | B | C declared | C oracle | D | E (rejected) |
|---|---|---|---|---|---|---|
| 1 False NOT_OBSERVED counted | **27** | 0 | 0 | 0 | 0 | 0 |
| 2 …where truly qualified | **13** | 0 | 0 | 0 | 0 | 0 |
| 3 Uncheckable counted in denominator | **33** | 2* | 2* | 2* | 2* | 6 |
| 4 Positive evidence credited in score | 35 | 26 | 26 | 31 | 26 | 35 |
| 4b Positive evidence visible in diagnostics | 35 | 35 | 35 | 35 | **26** | 35 |
| 5 Over-exclusion vs ideal contract | 2 | 12 | 12 | 2 | 12 | 7 |
| 5b Over-exclusion vs declared contract | 2† | 2† | 2† | 2† | 2† | 2† |
| 6 False SUPPORTED counted | 3 | 2* | 2* | 2* | 2* | 3 |
| 7 Duplicate / merged counting | 0 | 0 | 0 | 0 | 0 | 0 |
| 8 Controls with candidate-dependent eligible set | 0 | 0 | 0 | 0 | 0 | **8** |
| 10 Necessity differs on a counted row | 0 | 0 | 0 | 0 | 0 | 0 |
| 12 Orphan rows counted (`unresolved:c`) | 2 | 0 | 0 | 0 | 0 | 0 |
| Score = declared contract (of 54) | 15 | **49** | **49** | 39 | **49** | 40 |
| Score = ideal contract (of 54) | 25 | 39 | 39 | **49** | 39 | 40 |

\* Control 25 only: the parser turns a narrative sentence into REQUIRED
Python/Docker rows. This is pre-existing and no scoring policy can fix it.
† Control 16 only: the parser routes "Go or Golang" to a placeholder.
The 5 pairs that miss the declared contract under B/C/D are all
pre-existing parser representation defects (13, 16, 25).

**G15 frozen controls (55 outcomes; G18 rule applied to G15's unchanged gold facts)**

| Metric | A | B | C declared | C oracle | D | E |
|---|---|---|---|---|---|---|
| False NOT_OBSERVED counted / truly qualified | 12 / 6 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| Uncheckable counted | 18 | 0 | 0 | 0 | 0 | 6 |
| Positive credited / visible | 20 / 20 | 13 / 20 | 13 / 20 | 14 / 20 | 13 / 13 | 20 / 20 |
| False SUPPORTED counted | 1 (K1, v12-era flattening; now contained by G17 elsewhere) | 0 | 0 | 0 | 0 | 1 |
| Candidate-dependent controls | 0 | 0 | 0 | 0 | 0 | **5** |

**B ≡ C (declared) on every row of both corpora.** This holds only because
every registered concept currently has a pathway, and nothing enforces
that.

**Reading.**

- **A** is the only policy that penalises candidates for uncheckable
  alternatives.
- **E** credits positives but makes "X of Y" candidate-dependent. It is
  rejected again, as in G15.
- **D** matches B's score but deletes the positive-evidence diagnostic
  and the concept provenance.
- **B and C give the same numbers.** C's difference is architectural: it
  states *why* a row is excluded and fails safe when a future concept has
  no detector. B instead hard-codes the evidence layer's emission policy
  as a string prefix inside scoring.
- **C (oracle)** shows that a language vocabulary would recover 5 credited
  positives on synthetic controls. On real data (Phase 7) it recovers
  nothing.

**Does B need C's representation to be safe?** Yes, to stay correct over
time; today they compute the same thing. Implement B's semantics through
C's minimal internal representation. This is not two features.

## Score, denominator and candidate independence

Direction of change, A → C (declared):

| Corpus | Unchanged | Up | Down | Denominator only | Became undefined |
|---|---|---|---|---|---|
| G18 (54 pairs) | 17 | 10 | **2** | 8 | 17 |
| G15 (35 pairs) | 15 | 3 | 0 | 4 | 13 |

- **Both decreases are lost credit for genuine evidence** for an
  unregistered GitHub language (10: Elixir, 23: MATLAB, 67 → 50). This is
  the declared contract's recall cost.

  The exclusion is a **conservative policy choice** made because no
  language vocabulary is declared. It is **not** a finding that these
  languages are unassessable: GitHub language statistics can and do
  evidence them, as the oracle column shows.
- **Increases** come from removing rows that could only ever be
  NOT_OBSERVED.
- **"Became undefined"** is invariant 12: the job's only requirement is
  uncheckable.
- **Integrity:** in every pair supported ≤ eligible, and `None` exactly
  when eligible = 0. Every score is the production half-up function.
- **Candidate independence:**
  - metric 8 = 0 for A, B, C and D on both corpora;
  - E is dependent in 8 + 5 controls;
  - a property test re-matches one mixed job against 40 random evidence
    sets, and C's counted set never changes.

## Phase 6 — API and backward compatibility (proposal, not implemented)

G15's "additive per-requirement field", made concrete:

- **`RequirementOut.counts_toward_alignment: bool`** (per requirement, additive).
- **`RequirementOut.alignment_exclusion_reason: str | None`**:
  - `null` when counted;
  - `"not_assessable"` for a NOT_ASSESSABLE status;
  - `"alternative_not_checkable_from_github"` for a mixed OR group;
  - `"technology_not_checkable_from_github"` for a standalone or
    all-unassessable row.
- **`AssessmentOut.excluded_from_alignment_count: int`** (aggregate,
  additive): SUPPORTED + NOT_OBSERVED rows that are not counted.

**Reconciliation:** `len(supported) + len(not_observed) ==
assessable_requirement_count + excluded_from_alignment_count`. Required
and preferred sub-scores use the eligible set.

**Statuses still reconcile.** `status` remains an evidence statement and
the matcher is unchanged.

- An excluded SUPPORTED row stays in `requirements.supported` with its
  evidence. That is the honest "supported but not counted" case, e.g.
  "AWS evidence found — not counted, because the Azure alternative cannot
  be checked from GitHub".
- An excluded NOT_OBSERVED row stays in `not_observed`. It must be
  labelled "not counted", because `NOT_OBSERVED`'s docstring ("the
  requirement IS GitHub-observable") is only true for its checkable
  members. The docstring would need one sentence of amendment.

**NOT_ASSESSABLE vs excluded-from-score.** NOT_ASSESSABLE means the
matcher had nothing to check. Excluded means it checked something, but
the result cannot decide the requirement. Every NOT_ASSESSABLE row is
excluded; not every excluded row is NOT_ASSESSABLE. Keeping them separate
is what preserves invariant 3.

**`interpretation_status`** is unchanged: an excluded row is still a
recognized concept.

**Clients.**

- **Shape:** fields are additive Pydantic fields; old clients ignore them.
- **Meaning:** `assessable_requirement_count` changes meaning (eligible,
  not evaluated). That semantic change is why the scoring version must
  bump.
- **Frontend:** it would keep working, but without a "not counted" label
  an excluded NOT_OBSERVED row would look like a penalty. A frontend label
  is a separate approval.

**Versions:**

- `SCORING_VERSION` `github_evidence_alignment:v1` → **v2**: required,
  because the same two profiles produce different scores.
- `MATCHER_VERSION` unchanged: no status changes.
- Parser unchanged.
- `JOB_REQUIREMENT_SCHEMA_VERSION` unchanged: `JobRequirement` is not
  touched.

## Phase 7 — Historical evaluation (counterfactual, read-only inputs)

- **G15 (55 outcomes):** see Phase 5. The frozen G15 report and gold are
  unchanged.
- **G16/G17 compound controls (58 controls × fixtures = 414, v13):**
  - false SUPPORTED stays **7** under every policy: the policies neither
    add nor remove leakage;
  - 11 fixture outcomes change, under B/C/D only.
  - **045** "Docker, Kubernetes or Terraform" is a mixed list with
    `unresolved:terraform`, now excluded.
  - **058** "Alternatively…": its fabricated `unresolved:alternatively` row
    leaves the denominator.
- **Frozen 8c v1 and v1.1** (identical results): **6 of 12 pairs change
  under B/C/D/E**.

  | Pair | Production | C (declared) | Excluded rows |
  |---|---|---|---|
  | karpathy × frontend_01 | 50 (3/6) | 60 (3/5) | Angular-or-Vue group |
  | sindresorhus × frontend_01 | 67 (4/6) | 80 (4/5) | Angular-or-Vue group |
  | sindresorhus × robotics_controls_01 | 25 (1/4) | 33 (1/3) | MATLAB-or-Simulink group |
  | torvalds × data_science_01 | 20 (1/5) | 25 (1/4) | NumPy |
  | torvalds × embedded_firmware_01 | 20 (1/5) | 50 (1/2) | SPI, I2C, UART |
  | Jango1324 × embedded_firmware_01 | 0 (0/5) | 0 (0/2) | SPI, I2C, UART (denominator only) |

  G15 reported 5 at parser v12. The sixth is the denominator-only pair.
  Even the oracle vocabulary recovers none of these: Angular and Simulink
  are not GitHub-evidenceable.
- **M10 SOTI / Manulife:** SOTI's single technical row is a mixed OR
  (excluded). Manulife's technical row is fully assessable.
- **Private corpora** (opt-in; previously inspected, so not independent;
  counts only):

  | Corpus | Postings | Technical rows | Excluded by contract | Standalone | Mixed OR | All-unassessable OR |
  |---|---|---|---|---|---|---|
  | M11-D | 12 | 14 | 5 | 4 | 0 | 1 |
  | M11-F | 18 | 40 | 17 | 17 | 0 | 0 |
  | M11-G5 | 18 | 54 | 25 | 22 | 3 | 0 |
  | M11-G9 | 14 | 34 | **24** | 23 | 1 | 0 |
  | **Total** | 62 | 142 | **71 (50 %)** | 66 | 4 | 1 |

  A local review (counts only; author judgement, not independently
  verified) of the 75 unresolved member mentions (72 distinct terms)
  found:
  - **53** tools, cloud services or hardware names that no extractor can
    ever emit;
  - **5** real technologies carrying a parse fragment (e.g. a trailing
    ")");
  - **17** generic words or fragments the parser promoted to "technologies";
  - **0** GitHub-reported language names.

  So on real postings the declared contract over-excludes essentially
  nothing, and half of today's technical denominator rows are rows that
  could only ever be NOT_OBSERVED. **The standalone defect is ~16× more
  frequent than the mixed-OR defect.**

## Phase 8 — Recommended future implementation (not implemented)

**Recommendation: the capability contract (C, declared), which gives B's
scoring semantics, scoped to both mixed/all-unassessable OR groups and
standalone rows.** No language vocabulary for now (Phase 7: it would
recover nothing on real data).

1. **Source files**
   - `src/gitscore/evidence/capability.py` (new, internal):
     - `concept_capability(concept_id, registry)` returning an internal
       ASSESSABLE / NOT_ASSESSABLE / UNRESOLVED value with reasons, derived
       from registry aliases, README-safe aliases and the Docker detector
       constant;
     - `requirement_score_eligibility(requirement)` returning
       `(eligible, reason)`.

     It lives next to the extractors because it describes what *they* can
     emit.
   - `src/gitscore/assessment/models.py`:
     - `_assessable_matches` also requires eligibility;
     - `alignment_score`'s numerator counts SUPPORTED **within that
       filter** instead of `match_analysis.supported_count`;
     - new `excluded_from_score_matches()`.
   - `src/gitscore/assessment/types.py`: `SCORING_VERSION` → `v2`.
   - `src/gitscore/api/schemas.py` and `serialization.py`: the three
     additive fields above (separate approval).
   - Frontend "not counted" label: separate approval, separate milestone.
2. **Assessment model:** eligibility is a property of the requirement,
   computed once, never stored separately from `match_analysis` (the 7B
   "derive, never duplicate" rule holds).
3. **Matcher:** no change. `MatchStatus` is unchanged; one docstring
   sentence for NOT_OBSERVED on excluded rows.
4. **API:** additive only (Phase 6).
5. **Semantics:** a row counts iff status ≠ NOT_ASSESSABLE and every
   member is ASSESSABLE. Status, matched ids and evidence are always
   retained.
6. **Scoring version:** `github_evidence_alignment:v2`.
7. **Historical scores:**
   - 6/12 frozen 8c pairs (5 alignment values, 1 denominator only) would
     differ under v2;
   - frozen 8c gold and reports are not rewritten; the 8c end-to-end
     reports are regenerated as v2 outputs;
   - check `_recompute_alignment` in the evaluation harness, which reads
     `supported_count`.
8. **Test migration:** see the regression probe below. Add a registry
   invariant test: every registered concept has ≥ 1 declared pathway.
9. **Known limitations:**
   - genuine evidence for unregistered GitHub languages stops counting
     (2/54 synthetic pairs drop);
   - fabricated `unresolved:` terms become "recognized, not counted" rows
     instead of score penalties. They remain visible noise, a parser
     problem;
   - narrative-as-REQUIRED (25), bare-"C" (13), alias-OR placeholder (16)
     and ambiguous lists (17) are pre-existing parser defects that this
     does not fix;
   - not-assessable registered concepts would only appear if a concept
     without a pathway were added.

### Regression probe (throwaway clones; repository untouched)

Clean clones of HEAD lack the private datasets (37 skips). The three
HEAD-identity guards (G13, G15, G16 "production unchanged") fail under
any patch and are counted separately. One assessor patch measures both
B and C, since they select identical rows today.

| Option | Suite | Behavioural failures |
|---|---|---|
| Baseline (unpatched clone) | 2008 passed, 37 skipped, 18 xfailed | 0 |
| B, OR groups only (G15 scope) | 7 failed (3 guards), 2001 passed | **4** |
| **B ≡ C declared** (OR groups + standalone) | 12 failed (3 guards), 1996 passed | **9** |

The 9 tests for the recommended scope fall into three groups:

- **Contested 8D.1 decision, to be overturned deliberately (2):**
  `test_assessment_engine.py::test_or_group_counts_as_exactly_one_assessable_requirement`
  and `::test_unresolved_concept_requirement_scored_like_any_other`.
- **Fixture artifacts, to be migrated to registered ids with no semantic
  change (4):** `test_half_up_rounding_62_5_rounds_up_to_63`,
  `test_half_up_rounding_72_5_rounds_up_to_73`, `test_alignment_score_bounds`
  and `test_adversarial_case_strong_headline_despite_zero_required_support`.
  These use synthetic `unresolved:cN` ids as filler concepts.
- **Frozen-research reproducibility, to get scoring-version-aware branches
  as G17 did for the parser (3):**
  - G15 `test_policy_a_score_equals_the_real_assessor`
  - G15 `test_report_is_reproducible`
  - G16 `test_report_is_reproducible`

G18's own `test_report_is_reproducible` would need the same treatment.
It was not in the probe, because the clone does not contain the untracked
G18 files.

## Risks and uncertainty

- **Coverage and independence:** synthetic controls by the same author.
  The private corpora were inspected before (not independent), and the
  term categorisation is a local judgement.
- **Detector contract inferred from code:** the extractors don't declare
  it themselves. The capability function would be the first place it is
  written down, and it must be kept in step with the extractors (an
  invariant test is proposed).
- **Simulation fidelity:** policies re-classify real `RequirementMatch`
  results. The probe patches are illustrative, not reviewed
  implementations.
- **Large real-world effect:** half of the technical rows leave the
  denominator. Headline alignment would generally rise and become
  `None` more often. This is more truthful, but it is a visible product
  change.

## Approval questions

1. **Scope.** Approve exclusion for both mixed / all-unassessable OR
   groups **and** standalone unresolved rows (recommended), or OR groups
   only (G15 scope)?
2. **Representation.** Approve implementing it as an internal capability
   contract (`evidence/capability.py`) rather than a raw `unresolved:`
   prefix check in the assessor?
3. **Language vocabulary.** Accept excluding unregistered GitHub
   languages (Elixir, Zig, Vue, MATLAB) for now? Or authorise a declared
   vocabulary (e.g. vendored Linguist names) in a later milestone?
4. **Scoring version.** Approve `github_evidence_alignment:v1` → `v2`, the
   overturned 8D.1 tests, and 6/12 frozen 8c pairs differing under v2?
5. **API.** Approve the three additive fields (`counts_toward_alignment`,
   `alignment_exclusion_reason`, `excluded_from_alignment_count`)? Approve
   a frontend "not counted" label as a separate milestone?
6. **Parser follow-ups.** Open separate milestones for fabricated
   `unresolved:` terms (generic words, fragments, bare "C"),
   narrative-as-REQUIRED, and alias-OR placeholders?

## Verification

- **Focused tests:** 29 / 29 pass.
- **Full backend suite** (working tree): **2061 passed, 13 skipped, 18
  xfailed, 0 failed**.
  - 2061 = 2032 + 29 new tests.
  - The 13 skips are the same pre-existing M10E (10) and M11-A2 (3)
    skips: no new skips. All 18 xfails are preserved.
- **G14 integrity suite:** 124 passed. The manifest still has 10 entries.
  No historical gold, freeze or report was modified. The only tracked
  diff is the new `docs/CHANGELOG_DEV.md` entry.
- **Parser:** `job_description_parser:v13`. Matcher, scorer, API, schemas,
  frontend and G10–G13 are byte-identical to HEAD.
- **No network or LLM:** this is test-enforced for all G18 scripts.
- **Privacy scan:** all 11 new files were checked against 1,178
  private-posting phrases and ids, with 0 hits. The private aggregates
  file holds integer counts only (test-enforced key allow-list).
- **Not run:** native Linux/macOS, and a clean-checkout `autocrlf`
  matrix. G18 adds no CRLF-sensitive tracked file beyond the freeze,
  which is LF-normalised.

## Commit status

Not committed. Ready for review. At commit time, the new tracked freeze
`evaluation/m11g18/controls_hash_freeze.json` must be registered in
`evaluation/integrity/canonical_hash_manifest.json` (G15/G16 precedent),
or G14's inventory test will flag it once tracked.
