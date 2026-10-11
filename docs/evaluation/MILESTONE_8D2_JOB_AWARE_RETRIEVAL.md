# Milestone 8D.2 — Job-Aware Repository Retrieval

Fixes the repository-selection failure Milestone 8C's real-world
evaluation documented (`docs/evaluation/MILESTONE_8C_EVALUATION.md`
Section 13, and §25.7's own named limitation in
`docs/ARCHITECTURE.md`): Milestone 5B's generic, job-independent
repository ranking can exclude a small repository that is highly
relevant to one SPECIFIC job posting, purely because a prolific
candidate has too many repositories competing for too few analysis
slots. Full architecture writeup: `docs/ARCHITECTURE.md` §26. This
document is the evaluation record — why generic ranking alone was
insufficient, the retrieval design, the offline evaluation and its
measured numbers, and known limitations.

## 1. Why generic ranking alone was insufficient

Milestone 5B's `rank_repositories()` answers one job-INDEPENDENT
question — "which repositories look substantively real" (size,
recency, language presence, description presence, stars) — and is
capped at `top_n=15` regardless of a candidate's total repository
count. Milestone 8C's evaluation found three genuine, documented
instances of a relevant repository falling outside that cutoff
(`retrieval_miss_relevant: true` in `evaluation/gold/candidates/*.json`):

- `Jango1324/Pneumonia-Detection-Ai` — used as an illustrative example
  in Milestone 8A's own prompt, genuinely ML-relevant (Python), excluded
  from a 20-repository account's top-15.
- `karpathy/nn-zero-to-hero` — a 24.6k-star ML teaching repository,
  excluded from a 63-repository account's top-15.
- `sindresorhus/execa` — a 7.6k-star, well-engineered JS library,
  excluded from a 1,142-repository account's top-15.

None of these are ranking BUGS — 8C's own report is explicit that
generic ranking deliberately does not let popularity dominate and is
working as designed. The problem is architectural: a single,
job-independent cutoff cannot simultaneously serve every possible job a
candidate might be evaluated against.

## 2. Architecture

A second, independent retrieval signal (`gitscore.ranking.job_relevance`),
unioned deterministically with the frozen generic ranking — never a
replacement, never a reweighting of it:

```
all repositories
    |-- generic ranking (5B, frozen)       --> top N (names unchanged)
    `-- job relevance (8D.2, new)          --> top K
                               |
                               v
                  deterministic union: generic order preserved,
                  then job-relevant additions not already
                  present, in relevance order
                               |
                               v
                  bounded deep extraction (5D, unchanged)
```

`rank.py`/`config.py` (Milestone 5B) are untouched — not one line
changed, not one weight retuned, `REPOSITORY_RANKING_VERSION` stays `1`.
The new module's own `JOB_RELEVANCE_VERSION = 1` versions only the new
relevance formula/weights/budget.

### Dependency direction

`gitscore.ranking.job_relevance` imports ONLY `gitscore.concepts` and
its own package siblings — **zero dependency on `gitscore.jobs`**. The
new `JobRelevanceTerm` dataclass (`concept_ids: tuple[str, ...]`,
`weight: float`) is a small, neutral retrieval-query representation,
not the full `JobRequirementProfile`/`JobRequirement` domain model —
chosen specifically so `pipeline.evidence.extract_candidate_evidence()`
(the candidate-only, job-independent entry point since Milestone 5D)
never has to import `gitscore.jobs` to accept a retrieval query, and
remains fully usable with zero job context.

The ONE function that bridges the two domains,
`_relevance_terms_from_job_profile()` (converts a real
`JobRequirementProfile` into `tuple[JobRelevanceTerm, ...]`), lives in
`gitscore.application.job_fit` — already documented (Milestone 7C) as
"the one layer allowed to know about all of them together." `jobs`
stays unaware retrieval exists; `ranking.job_relevance` stays unaware
the job domain model exists. Verified non-circular by direct inspection:
`gitscore.jobs` imports only `gitscore.concepts` anywhere in the
package, so this dependency direction cannot form a cycle.

Text-scanning reuses the exact primitives Milestone 8D.1 introduced for
README/job-description prose (`concepts.matching.alias_pattern` +
`select_longest_overlapping_matches`) via its own thin collection loop
— mirroring `evidence/extraction/readme.py`'s own loop rather than
importing `jobs.parsing.concepts.find_concept_mentions()` across
packages, the established pattern in this codebase (share the
low-level primitive, not the orchestration function).

## 3. Cheap relevance signals

Computed ONLY from `parse_repo_summary()`'s existing fields (`name`,
`description`, `primary_language`, `topics`) — never an additional
fetch, never a README/manifest/source read for ranking purposes. One
`JobRelevanceTerm` per technical `JobRequirement` (non-technical claims
never produce a term); a term earns its weight (REQUIRED=1.0,
PREFERRED=0.5 — no `Importance`-based scaling) at most once, via any
ONE of:

1. **Structured language field** — `primary_language` resolves (full
   alias list, the same structured-source resolution `languages.py`
   evidence uses) to exactly this concept id. The only path that
   recovers a bare-unsafe-alias concept like `language.c`.
2. **Safe-alias text match** — name + description + topics, scanned
   with the identical `readme_safe_aliases()` + overlap-resolution
   mechanism README prose uses. A bare "go"/"c" alias never matches
   here; "React Native" never misattributes as plain "React."
3. **Bounded unresolved-term match** — exact, word-boundary-safe
   (never fuzzy) text match for an `unresolved:<term>` requirement.

An alternative group ("Python or Go") reuses `alternative_concept_ids`
directly — ANY one option matching satisfies the term; OR text is never
re-parsed. Relevance is explicitly retrieval-only: `match_job()`/
`assess_job()` never see a relevance score at all.

## 4. Budget, ordering, determinism

`relevance_top_k=10` (new) alongside the existing `top_n=15` (Milestone
5B, unchanged) → `max_selected=25` total (their exact sum — a
redundant-but-explicit hard cap). Zero-relevance repositories never
enter the relevance ranking. Deterministic tie-break: relevance score
descending, then repository name ascending/case-insensitive. Ordering
policy: the generic top-N's own order is never reordered; job-relevant
additions are appended afterward in relevance order, skipping any
repository already present (so a repository never appears twice).

## 5. `CandidateEvidenceProfile` semantics decision

**No schema change.** `CandidateEvidenceProfile` gains zero new fields;
its SHAPE stays unconditionally job-independent. What changes is a
documented CONTENT caveat: calling `extract_candidate_evidence()` WITH
`job_relevance_terms` means the analyzed repository set — and therefore
`coverage`/`evidence`/`concept_summaries` — may differ between two
calls for the SAME candidate against two DIFFERENT jobs. The resulting
profile instance is a bounded, job-CONDITIONED snapshot for that one
run; it must never be cached or treated as the single canonical,
job-independent evidence profile. Calling with no `job_relevance_terms`
(the default) still produces exactly that canonical profile. This
milestone implements no caching of any kind — only this documentation,
so a future caching layer does not silently reuse a job-conditioned
profile across unrelated jobs. (`EvidenceExtractionResult`, the
pipeline-level diagnostics wrapper already explicitly outside the
domain model, gains one new optional field, `repository_selection`, for
tests/evaluation/debugging — not serialized by the HTTP API.)

## 6. Offline evaluation

New, additive harness — `scripts/evaluate_repository_retrieval.py` +
`scripts/evaluation_lib/retrieval_eval.py` +
`evaluation/gold/retrieval_cases.json` (corpus version `8d2:v1`, brand
new, introduced by this milestone — does not touch or correct any
`8c:v1`/`8c:v1.1` file). `scripts/evaluate_end_to_end.py` is
**untouched**: it still calls `extract_candidate_evidence()` with no
`job_relevance_terms`, so its published report (`end_to_end_report.*`)
is byte-for-byte unchanged by this milestone.

For each gold case, the real pipeline runs TWICE against the same
offline fixture — once generic-only, once with `job_relevance_terms`
from the SAME `_relevance_terms_from_job_profile()` function
`analyze_job_fit()` itself uses (never a reimplementation) — and the
result is classified by `classify_retrieval_outcome()`.

### Evaluation-integrity correction (post-review)

An earlier version of this section scored each case against a single
`expect_recovered` field and reported `karpathy/nn-zero-to-hero` and
`sindresorhus/execa` as "correct" negative-control exclusions after
flipping that field from `true` to `false` once the algorithm failed to
recover them. On review, this was rejected: **relevance ground truth
must never be revised because the algorithm failed to recover a
genuinely relevant repository** — that is a real, reportable retrieval
miss, not evidence the repository was never relevant.

The gold schema now carries two INDEPENDENT fields per case:
`genuinely_relevant` (ground truth, authored without regard to the
algorithm's output, never revised to match it) and `expected_analyzed`
(a separate regression pin on the CURRENT measured outcome, which is
allowed to diverge from `genuinely_relevant`). `classify_retrieval_outcome()`
(`scripts/evaluation_lib/retrieval_eval.py`) turns these into five
mutually exclusive outcomes — `RETRIEVAL_RECOVERED`,
`RETRIEVAL_ALREADY_COVERED`, `RETRIEVAL_MISSED_RELEVANT`,
`RETRIEVAL_CORRECTLY_EXCLUDED`, `RETRIEVAL_FALSE_POSITIVE_ADDITION` —
that keep a missed relevant repository structurally distinct from a
correct negative control. `tests/test_evaluation_harness.py` pins this
classification directly (synthetic inputs) and also asserts, against
the real gold file, that both known-limitation cases keep
`genuinely_relevant: true` — a regression guard against this exact
conflation recurring. No production retrieval code changed as part of
this correction (`gitscore.ranking.job_relevance` is unchanged; the
15+10=25 budget is unchanged) — this was purely an evaluation-harness
and documentation fix.

### Results: 7 cases, honestly separated

| candidate | job | repo | genuinely_relevant | expected_analyzed | outcome |
|---|---|---|---|---|---|
| jango1324 | ml_engineering_01 | Pneumonia-Detection-Ai | true | true | **RETRIEVAL_RECOVERED** |
| jango1324 | general_swe_01 | Pneumonia-Detection-Ai | true | true | **RETRIEVAL_RECOVERED** (via alternative-group ANY-match) |
| karpathy | computer_vision_01 | nn-zero-to-hero | true | false | **RETRIEVAL_MISSED_RELEVANT** (known limitation, §7) |
| karpathy | frontend_01 | nn-zero-to-hero | false | false | RETRIEVAL_CORRECTLY_EXCLUDED (negative control) |
| sindresorhus | fullstack_01 | execa | true | false | **RETRIEVAL_MISSED_RELEVANT** (known limitation, §7) |
| sindresorhus | robotics_controls_01 | execa | false | false | RETRIEVAL_CORRECTLY_EXCLUDED (negative control) |
| sindresorhus | frontend_01 | awesome | false | false | RETRIEVAL_CORRECTLY_EXCLUDED (negative control) |

**Genuinely relevant repositories (4 cases): 2 recovered, 0 already
covered by generic ranking, 2 missed despite job-aware retrieval.**
**Negative controls (3 cases): 3 correctly excluded, 0 false-positive
additions.** The regression pin (`expected_analyzed` vs. measured
outcome) holds 7/7 — i.e. the implementation's observed behavior is
unchanged by this correction; only how it is CLASSIFIED and REPORTED
changed.

Additions stayed bounded throughout — `jango1324`'s two pairs added
exactly 1 repository each; `karpathy`/`sindresorhus` additions were
capped at `relevance_top_k=10` even though hundreds of repositories
scored above zero. No negative-control case produced a false-positive
addition (0/3).

## 7. Known limitations

**Crowding on high-repo-count accounts.** When many repositories share
the SAME single weak signal, a fixed `relevance_top_k=10` cannot
surface one specific repository among hundreds of ties:

- `sindresorhus` has 1,142 repositories; 992 of them score `>0` for
  `fullstack_01` (the account is overwhelmingly JavaScript, so a single
  `language.javascript` match is a very weak discriminator). `execa`
  ties at score `1.0` with hundreds of others and ranks **231st of
  992** by the deterministic name-ascending tie-break — nowhere near
  any reasonable top-K. This is the SAME underlying "extremely prolific
  account defeats any small fixed cutoff" problem 8C originally named
  for this exact repository; Stage-2 retrieval narrows it (a repository
  with a MORE SPECIFIC/rarer matching concept fares far better — see
  the `jango1324` recoveries above) but does not eliminate it for a
  single-weak-signal match on a 1000+-repository account.
- `karpathy` has 63 repositories; 39 score `>0` for `computer_vision_01`.
  `nn-zero-to-hero` only matches the PREFERRED-weight
  `language.jupyter_notebook` term (score `0.5`), while most of its 38
  siblings match one or more REQUIRED terms (score `1.0`-`2.0`) — so it
  ranks **38th of 39**, just outside `relevance_top_k=10`. The signal
  correctly identifies it as relevant; the budget still excludes it
  because so many other repositories score higher.

Deliberately NOT fixed by enlarging `relevance_top_k` or
`max_selected` for this milestone — the brief's own instruction was
"conservative defaults based on the existing `top_n=15` behavior," not
tuning the budget until this evaluation's specific cases pass. A
genuine fix (if ever prioritized) would need a signal that
discriminates WITHIN a large same-concept cluster, not a larger fixed
cutoff.

**Other deliberate scope boundaries:**

- Relevance deliberately does NOT apply Milestone 5B's fork/archived/
  trivial-size dampeners — topical match and general substantiveness
  are different axes; a tiny but genuinely on-topic repository stays
  retrievable. A low-substance match still only decides whether a
  repository gets analyzed, never whether it counts as evidence (§26.3
  of `docs/ARCHITECTURE.md` — relevance is retrieval-only).
- `find_bare_short_alias_mentions()`'s job-description-prose fallback
  (Milestone 8D.1, gated on a nearby skill-context word like
  "experience"/"programming") is intentionally NOT extended to
  repository name/description/topics — that context vocabulary has no
  reason to appear in repo metadata. Bare `c` remains retrievable only
  via the structured `primary_language` field here.
- No embeddings, no LLM, no fuzzy matching, no CatBoost, no role-name
  classifier, no per-role special-casing — exact, deterministic,
  boundary-safe, concept-driven matching only, exactly as required.
- `rank.py`/`config.py` (Milestone 5B), the matcher, the assessment
  formula, the API contract, and the frontend are all unchanged.
- `scripts/evaluate_end_to_end.py` does not (yet) exercise job-aware
  retrieval — its `build_candidate_profiles()` still builds one
  job-independent profile per candidate, reused across every job pair
  in the matrix, by design (changing that is explicitly out of this
  milestone's scope; the new, separate retrieval evaluator above is
  where job-aware behavior is measured instead).

## 8. Versions

| Constant | Before | After |
|---|---|---|
| `REPOSITORY_RANKING_VERSION` (`ranking/config.py`) | 1 | **1 (unchanged)** |
| `JOB_RELEVANCE_VERSION` (`ranking/job_relevance.py`, new) | — | **1 (new)** |
| `CONCEPT_REGISTRY_VERSION` | 4 | 4 (unchanged) |
| `JOB_DESCRIPTION_PARSER_VERSION` | `v3` | `v3` (unchanged) |
| `JOB_REQUIREMENT_SCHEMA_VERSION` | 2 | 2 (unchanged) |
| `EVIDENCE_SCHEMA_VERSION` | 2 | 2 (unchanged) |
| `MATCHER_VERSION` | `requirement_matcher:v1` | unchanged |
| `SCORING_VERSION` | `github_evidence_alignment:v1` | unchanged |

No existing version was bumped for this milestone — repository
selection changing which Evidence a run produces is not, itself, a
change to any of the above packages' own analytical semantics.
