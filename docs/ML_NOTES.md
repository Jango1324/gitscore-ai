# GitScore AI — ML Notes

Status: updated 2026-08-31 (Milestone 3 — project hygiene, pipeline
testing, pre-ML release readiness). §6 (dataset snapshot/dedup policy)
and §7 (old development data policy) are new this milestone. §5 items
1 and 8 were updated when Milestone 2 fixed the pagination and
rate-limit issues they originally described; other sections are
unchanged from the 2026-08-30 audit. No model training code exists in
the repo yet (`catboost` is not installed, not imported anywhere). This
document is the pre-training analysis `CLAUDE.md` requires ("Before
training any model: clearly define X and y, prevent leakage...").
**Real dataset collection has not started — see §7.**

## 1. What data exists today

Every row of `profile_features` (SQLite, `data/gitscore.db`) is one
`analyze_user()` run: the full feature vector produced by
`extract_profile_features()` (see field list below) plus
`readiness_score`, the **rule-based** total from
`calculate_readiness_score()`. There is currently no other label source
— no recruiter ratings, no hiring outcomes, no human review of any kind.

## 2. Feature definitions (current, as implemented)

From `features/activity.py`:
- `total_repos`, `forked_repos`, `original_repos` (= total - forked)

From `features/languages.py`:
- `unique_language_count`, `most_used_language` (categorical),
  `python_repository_count`, `typescript_repository_count`,
  `has_python`, `has_typescript`
- Note: `most_used_language` is picked by `max(all_languages,
  key=all_languages.get)` where `all_languages` counts **number of
  repos containing each language**, not bytes of code — a repo with a
  1-line shell script and a 5000-line Python file both count as "1" for
  their respective languages.

From `features/quality.py`:
- `total_stars`, `average_stars`, `total_forks`, `average_forks`,
  `repositories_with_description`, `description_coverage_ratio`
- **Fixed in Milestone 1.** `description_coverage_ratio` previously
  was always `1.0` regardless of actual data (`quality.py:9`'s
  `or`/`and` bug). Now a description only counts if it is non-`None`
  and non-blank after stripping whitespace, so this feature carries
  real signal again — confirmed by
  `tests/test_feature_extractors_current_behavior.py::test_description_coverage_ignores_blank_descriptions`.
  **Any model trained on data collected before this fix should be
  re-collected or discarded** — rows collected under the old code have
  `description_coverage_ratio == 1.0` for every user regardless of
  truth, which is not a real historical value, it's a constant
  artifact of the bug.

From `features/ml.py`:
- `ml_repository_count`, `ml_keyword_total`, `has_pytorch`,
  `has_huggingface`, `has_pandas`, `has_catboost`
- **Fixed in Milestone 1.** Matching previously was raw substring
  search on lowercased `"{name} {description}"`, no word boundaries:
  `"ai"` matched inside "container", "explain", "email"; `"ml"` matched
  inside "html". Now each keyword in `ML_KEYWORDS` requires
  non-alphanumeric boundaries on both sides (hyphens/underscores/spaces
  still count as valid separators), eliminating that noise while
  preserving matches like `"my-ai-project"` — confirmed by
  `tests/test_feature_extractors_current_behavior.py::test_ml_keyword_matching_no_longer_has_false_positives`
  and the true-positive tests in the same file. As with
  `description_coverage_ratio`, **rows collected before this fix may
  have inflated `ml_repository_count`/`ml_keyword_total` and should not
  be mixed with post-fix data** without re-verifying.

From `features/readme.py`:
- `repositories_with_readme`, `readme_coverage_ratio`,
  `average_readme_length`, `repositories_with_installation`,
  `repositories_with_usage`, `repositories_with_demo`,
  `repositories_with_badges`, `repositories_with_license`,
  `repositories_with_contributing`
- Keyword-substring based like `ml.py`, same class of false-positive
  risk but lower severity (words like "license", "contributing" are
  less ambiguous than "ai"/"ml").

Not currently captured at all: commit recency/frequency, commit
authorship (vs. co-authorship/bot commits), issue/PR activity, CI
presence, test coverage, code complexity, org-owned repository
contributions (see §5), account age, or anything time-weighted.

## 3. Target definition: `readiness_score`

`readiness_score = ml_score + originality_score + documentation_score +
language_tool_score + community_score`, each a deterministic
if/elif ladder over the features listed above (`scoring/readiness.py`).
It is **entirely a function of the same feature vector stored alongside
it** — there is no independent signal.

### Why training CatBoost on this target is limited (explicitly requested — item 8)

This is not a train/test leakage problem in the classic sense (no
future information, no test-set contamination) — it is a **circularity
problem**: `y` is a deterministic, closed-form function of `X`
(literally `y = f(X)` for a known, hand-written `f`). Concretely:

- A CatBoost model trained on `(X, f(X))` will, with enough
  capacity and data, primarily learn to **reverse-engineer `f`** — the
  hand-written scoring rules — not any independent notion of "portfolio
  readiness." Near-perfect R²/accuracy on held-out data would mean the
  model successfully approximated the rubric, not that it discovered
  something predictive of real hiring outcomes.
- Because `f` is piecewise-linear/step-function (if/elif ladders on raw
  counts), a tree-based model like CatBoost is *especially* well-suited
  to memorizing it almost exactly — expect suspiciously high metrics
  (e.g. R² > 0.95) that reflect rubric-fitting, not generalization.
  A high score here should be read as "the model learned the formula,"
  never as "the model predicts hiring success."
- Any bug in a feature extractor (e.g. the `description_coverage_ratio`
  bug above) becomes baked into both `X` and `y` identically, so the
  model cannot "see" the bug or correct for it — it will faithfully
  reproduce the bug's effect on the score.
- Feature importances from this model tell you which features the
  **rubric weights most**, not which features actually predict a strong
  ML/AI candidate. Presenting CatBoost feature importances as "what
  makes a portfolio strong" would overstate what was actually measured.

**This matches the explicit warning already in `CLAUDE.md`**: *"a
CatBoost model trained only on this label will primarily learn to
reproduce this scoring formula... Do not present that model as proof of
real-world hiring prediction."* This audit confirms that warning is
accurate and, if anything, understates the risk given the exact-formula
circularity described above.

### What a model trained on this target is actually useful for

- A fast, differentiable/smooth **approximation** of the rule-based
  score (useful if the rubric later becomes too complex to evaluate
  cheaply, or if you want a smoothed score instead of hard if/elif
  cliffs).
- A sanity check that the rubric behaves consistently (e.g. no feature
  the rubric weights heavily is degenerate/constant across the dataset
  — this audit already found one such case: `description_coverage_ratio`).
- **Not** usable, without an independent label, as evidence the score
  predicts real hiring outcomes, interview success, or job performance.

### What real leakage risk *would* look like, if a better target is introduced later

If `readiness_score` is ever replaced with an independent label
(recruiter rating, interview outcome, hire/no-hire), watch for:
- **Identifier leakage:** `user_id`, `github_username`, `collected_at`
  must be excluded from `X` — they carry no generalizable signal and
  can leak group identity across train/test splits if the same user is
  collected more than once (`profile_features` has no unique constraint
  per user — see `docs/ARCHITECTURE.md` §7 — so a user analyzed twice
  produces two rows that could land on opposite sides of a naive random
  split, functionally leaking that user's identity into training).
  **Split by user, not by row**, once multiple snapshots per user exist.
- **Temporal leakage:** if a label is collected after some features were
  updated (e.g. stars accrued after the "readiness" moment being
  labeled), the model could learn from information that postdates the
  label.
- **Rubric-derived leakage:** don't feed the five category sub-scores
  (`ml_experience`, `project_originality`, etc.) as features when
  predicting a *new* label — they are themselves already
  deterministic functions of `X`, so including them alongside `X` is
  redundant at best and can dominate a weaker independent signal at worst.

## 4. Training strategy (not yet implemented — recommendation only)

Before any `catboost` code is written:
1. Fix the feature-extractor bugs listed in `docs/ARCHITECTURE.md` §5 —
   training on `description_coverage_ratio` while it's a constant `1.0`
   wastes a feature slot and would look like "the model ignored
   documentation," which is misleading.
2. Decide explicitly whether the near-term model target is
   "approximate the rubric" (legitimate, low-risk, but must be labeled
   as such everywhere it's shown) or "predict something independent"
   (requires collecting an independent label first — not yet possible
   with this schema).
3. Add a `scoring_rubric_version` column (or equivalent) to
   `ProfileFeature` before iterating on `scoring/readiness.py`, so
   historical rows remain interpretable after the rubric changes.
4. Split by `user_id`, not by row, once repeated snapshots per user exist.
5. Document preprocessing (categorical handling for `most_used_language`,
   missing-value policy) alongside the CatBoost training script, per
   `CLAUDE.md`'s AI/ML rules.
6. Report evaluation metrics honestly labeled as "rubric-approximation
   accuracy," not "readiness prediction accuracy."

## 5. What could make the GitScore itself misleading (item 3, independent of ML)

These affect the rule-based score today, before any ML model exists:

1. ~~**Pagination truncation**: scores for users with >30 public repos
   are computed from an arbitrary subset~~ — **fixed in Milestone 2**
   (`docs/PIPELINE.md` Stage 1): `get_repositories()` now fetches every
   page. **Any row in `data/gitscore.db` collected before this fix may
   still reflect only the first ≤30 repos** for a user with more than
   that many public repos — this is not a value that can be corrected
   in place, the affected users must be re-collected. Do not mix
   pre-Milestone-2 and post-Milestone-2 rows in the same
   training/analysis pass without accounting for this.
2. **Org-repo blind spot**: `GET /users/{username}/repos` returns only
   repositories **owned by that user account**, not repositories owned
   by an organization the user contributes to. A candidate who does
   most of their ML work inside a company/lab GitHub org (common for
   people with prior experience) will score artificially low, while a
   candidate who forks/re-uploads work under their personal account
   scores higher. This systematically disadvantages exactly the
   candidates most likely to already have real ML experience.
3. ~~**`ml.py` keyword false positives** inflate `ml_repository_count`
   for unrelated repos ("html-portfolio" counted as ML)~~ — **fixed in
   Milestone 1**, see §2.
4. ~~**`description_coverage_ratio` always 1.0`**~~ — **fixed in
   Milestone 1**, see §2.
5. **No recency weighting**: a repo last touched in 2019 counts
   identically to one pushed to yesterday. Stale, abandoned portfolios
   score the same as active ones.
6. **Stars/forks as "Community Signal"** (10 pts) reward popularity/luck
   (timing, promotion, being first) more than skill — a technically
   strong but unpromoted project scores near-zero on this axis.
7. **No repo-size/effort signal**: a 20-line script and a 20,000-line
   production system both count as "1 original repo" identically.
8. **Rate-limit-induced inconsistency** — **partially addressed in
   Milestone 2**: a rate limit now raises a distinguishable
   `GitHubRateLimitError` immediately (instead of a generic exception,
   or previously, individual repo fetches silently degrading to empty
   data one-by-one until the whole hourly budget was gone) and aborts
   that user's `analyze_user()` call cleanly. `scripts/collect_dataset.py`
   still has no shared rate-limit budget/backoff *across users* in a
   batch — each user in the loop simply fails once the shared token is
   exhausted, still `except Exception`-caught and reported as "FAILED."
   This means a batch can still end up with some users scored from
   complete data and others entirely missing (not silently degraded)
   once the budget runs out — a real, but now at least *visible and
   attributable*, dataset construction bias. An authenticated
   `GITHUB_TOKEN` (5000/hour vs. 60/hour unauthenticated) makes this
   far less likely to trigger in practice at current usage volumes.

`CLAUDE.md` already states the top-level caveat correctly: *"Do not
claim that GitScore predicts actual hiring success."* Items 1-8 above
are the concrete mechanisms by which the current score could also be
**internally inconsistent** — i.e., misleading even as a relative
ranking between two GitHub profiles, not just as a hiring predictor.

## 6. Dataset snapshot / dedup policy (Milestone 3)

`save_profile_features()` inserts a new row on every `analyze_user()`
call — there is no upsert and no unique constraint on
`ProfileFeature.user_id` (see `docs/ARCHITECTURE.md` §7a for the full
review). This milestone deliberately does **not** change the schema to
add an `is_latest` flag or a unique constraint — that's more machinery
than a not-yet-collected dataset needs right now, and a schema change
should wait until it's actually required. Instead, the policy is
enforced at **dataset-build time**, by whatever script eventually reads
`profile_features` into the training dataset (there is no such script
yet — `scripts/show_dataset.py` currently just dumps the whole table
for inspection, see `docs/PIPELINE.md` Stage 6):

1. **Select one row per `user_id` before doing anything else** — the
   row with the maximum `collected_at` (equivalently, the maximum `id`,
   since rows are inserted in order) per user. In pandas terms:
   `df.sort_values("collected_at").groupby("user_id").tail(1)`. Do this
   *before* computing any statistics, feature distributions, or splits
   — not after, and not "mostly."
2. Only then apply the existing `docs/ML_NOTES.md` §3 recommendation to
   **split by `user_id`, not by row**, if/when multiple snapshots per
   user exist alongside a train/test split.
3. If a future need arises to compare a user's score *over time*
   (trend analysis, not training data), that's a legitimate use of the
   full historical row set — but it is a different, explicit query, not
   the default `SELECT *` a dataset builder should reach for.

**Concrete numbers from the current dev database** (see
`docs/ARCHITECTURE.md` §7a): 3 users, 13 rows, one user represented in
8 of 13 (~62%) — a naive `SELECT *` dataset built from this exact
database today would be dominated by one person's repeated test runs,
not a balanced sample of 3 users. This is not a hypothetical risk.

## 7. Old development data policy (Milestone 3) — pre-Milestone-1/2 rows

**Every row currently in `data/gitscore.db` predates both Milestone 1
(feature correctness) and Milestone 2 (GitHub data collection
reliability) and must NOT be used in the clean ML dataset.** Verified
by direct inspection during this milestone: all 13 existing
`profile_features` rows have `description_coverage_ratio == 1.0`
exactly (the Milestone-1 bug signature — see §2/§5 item 4), and the
`karpathy` row has `total_repos == 30` exactly (the Milestone-2
pagination-truncation signature — see §5 item 1). These rows may
contain, depending on which user/repos they came from:
- a `description_coverage_ratio` that is a constant bug artifact, not a
  real measurement (§2/§5 item 4),
- `ml_repository_count`/`ml_keyword_total` inflated by keyword
  false-positive matching (§2/§5 item 3),
- a repository set silently truncated to the first ≤30 repos for any
  user with more than that many (§5 item 1),
- and, per §6 above, heavy per-user duplication from repeated manual
  test runs during development.

**Do not begin collecting the real training dataset as part of this
milestone or as a side effect of it** — that remains explicitly
out of scope until a dedicated "collect the clean dataset" milestone.

**Recommendation for `data/gitscore.db` (not executed — needs explicit
approval):** once real dataset collection is about to begin, delete and
recreate the local dev database so nothing pre-fix can accidentally
leak into a later unfiltered query:

```bash
rm data/gitscore.db
python scripts/init_db.py
```

This is safe to do at that point because (a) every row in it today is
confirmed pre-fix and unusable for the clean dataset per this section,
and (b) `scripts/init_db.py` recreates the schema from the current
`models.py` idempotently. It is **not** being done automatically by
this milestone — it's a recommendation for whoever starts the real
dataset-collection milestone, not a cleanup task bundled into this one.
