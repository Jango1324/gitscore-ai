# GitScore AI — Pipeline (API → Parser → Features → Scoring → DB → ML → UI)

Status: updated 2026-09-08 (Milestone 4 — clean Dataset V1
infrastructure). This document traces one call to
`analyze_user(username)` end to end and calls out where it deviates
from what a "GitHub profile readiness pipeline" needs to be correct and
efficient. Every claim below is backed by a file/line reference and,
for the behavioral ones, a test in `tests/`. Stage 1 reflects Milestone
2 (GitHub data collection reliability); Stage 5 reflects the Milestone 3
database-snapshot-semantics review; Stages 0 / 6 / 6b reflect Milestone
4 (batch collection input + dataset builder); `feautures/` paths elsewhere
have been updated to `features/` (renamed in Milestone 3). Other content
is unchanged from the 2026-08-30 audit.

## Stage 0 — Batch collection input (`scripts/collect_dataset.py`) — Milestone 4

`scripts/collect_dataset.py` no longer holds a hardcoded username list.
It reads `data/collection/usernames.txt` (or `argv[1]`) via
`gitscore.dataset.collection_input.load_username_file`: one username per
line, blank lines and `#` comment lines ignored, inline `#…` stripped,
case-insensitive de-duplication (first spelling wins), order preserved.
It then calls `analyze_user()` per username, **continuing across ordinary
per-user failures** (bad username, transient error, one user's rate
limit), and prints per-user status plus a final
succeeded/failed/attempted/elapsed summary and a failure list. Exit code
`0` = all succeeded, `2` = finished with failures, `1` = could not start.
Only the exception *type + message* is printed — never the token. The
real curated list (`usernames.txt`) is gitignored; a comments-only
template is committed as `data/collection/usernames.example.txt`.
Confirmed by `tests/test_collection_input.py` and
`tests/test_collect_dataset_script.py`.

## Stage 1 — GitHub API collection (`github/client.py`) — updated in Milestone 2

Calls made per `analyze_user()` run, in order:

1. `GET /users/{username}` — 1 call
2. `GET /users/{username}/repos` — **all pages**, `per_page=100` each
3. Per repository (N = total repos returned by step 2, across all pages):
   - `GET /repos/{owner}/{repo}/languages` — 1 call
   - `GET /repos/{owner}/{repo}/readme` — 1 call

Total HTTP calls ≈ `1 + ceil(N/100) + 1 + 2N` (the `+1` on the
pagination term accounts for the trailing short/empty page that
confirms there's nothing left). Each of the calls above may involve
additional retried attempts on a transient failure (bounded, see below).

### Pagination

`get_repositories()` sends an explicit `per_page=100` and loops
`page=1, 2, ...`, concatenating each page's items in fetch order, until
a page comes back with fewer than `per_page` items:

```python
response = self._get(url, params={"per_page": per_page, "page": page})
```

A `max_pages=50` safety cap (~5000 repos) raises `GitHubRequestError`
instead of looping forever if GitHub ever kept returning full pages
indefinitely — this is a defensive bound, not an expected real-world
case. Confirmed by `tests/test_github_client_reliability.py`:
`test_pagination_fewer_than_one_page`, `test_pagination_exactly_one_full_page`,
`test_pagination_multiple_pages_are_concatenated_in_order`,
`test_pagination_empty_repository_list`, and
`test_pagination_stops_instead_of_looping_forever`.

Termination is based on page length (`len(page) < per_page`), not on
parsing GitHub's `Link` header — simpler and equally correct given a
fixed `per_page`, at the cost of trusting GitHub's documented default
page-size contract rather than reading an explicit "no more pages"
signal out of the response itself.

**Previous consequence (now fixed):** any GitHub user with more than 30
public repositories used to have their score computed from an arbitrary
30-repo subset (GitHub's undocumented default page size for this
endpoint). Historical rows in `data/gitscore.db` collected before this
fix still reflect that truncation — see `docs/ML_NOTES.md` §5.

### Timeouts, retries, rate limits, error handling

- **Timeouts:** every `GitHubClient` request passes an explicit
  `timeout=` (default `10.0s`, `DEFAULT_TIMEOUT_SECONDS`, configurable
  per-instance). Confirmed by
  `test_requests_are_made_with_an_explicit_timeout` and
  `test_timeout_is_configurable_and_applied_to_every_call`. A stalled
  TCP connection can no longer block a worker thread forever.
- **Retries:** connection errors, timeouts, and `{500, 502, 503, 504}`
  responses are retried with bounded exponential backoff (`0.5s, 1s,
  2s`, capped at `8s`; up to 3 retries = 4 attempts total by default).
  404s and other 4xx codes are never retried. Confirmed by
  `test_connection_error_is_retried_then_succeeds`,
  `test_timeout_error_is_retried_then_succeeds`,
  `test_server_5xx_is_retried_then_succeeds`,
  `test_retries_are_bounded_and_raise_after_exhaustion`,
  `test_backoff_delays_grow_and_are_capped`,
  `test_genuine_404_is_not_retried`, and
  `test_client_validation_error_is_not_retried`.
- **Rate limit awareness:** a 403 with `X-RateLimit-Remaining: 0`, a
  403 with `Retry-After`, or a plain 429 now raises
  `GitHubRateLimitError` — a distinct, programmatically checkable type
  carrying `reset_at`/`retry_after` when GitHub supplied them — instead
  of the generic `Exception(f"... {status_code}")` used for every
  failure before. It is raised immediately, never retried and never
  waited-out automatically (no infinite wait); the caller decides what
  to do. A plain 403 with none of those signals (e.g. permission
  denied) still raises `GitHubRequestError`, not a rate-limit error.
  Confirmed by `test_primary_rate_limit_raises_distinct_error_with_reset_time`,
  `test_secondary_rate_limit_raises_distinct_error_with_retry_after`,
  `test_429_is_treated_as_rate_limit`, and
  `test_plain_403_without_rate_limit_signal_is_not_treated_as_rate_limit`.
  Unauthenticated requests are still capped at 60/hour by GitHub — this
  is unchanged and remains a real constraint for `scripts/collect_dataset.py`
  batches; a `GITHUB_TOKEN` is strongly recommended for anything beyond
  a handful of users.
- **Concurrency vs. rate limits:** `ThreadPoolExecutor(max_workers=8)`
  (`MAX_REPO_WORKERS`) still fires up to 8 repo fetches concurrently,
  with no shared rate-limiter/semaphore across threads — that remains
  out of scope (would require a shared, thread-safe token-bucket, which
  is more machinery than the current per-request scope warrants). What
  changed: repo fetches are now submitted via `executor.submit()`
  rather than `executor.map()`, so when a `GitHubRateLimitError`
  surfaces from any worker, every not-yet-started queued future is
  cancelled instead of the whole batch draining first — bounding (not
  eliminating) wasted requests after a rate limit is hit. See
  `docs/ARCHITECTURE.md` §8.
- **Error typing:** every failure mode now raises one of
  `GitHubNotFoundError`, `GitHubRateLimitError`, or
  `GitHubRequestError` (carrying `status_code`) — see
  `github/exceptions.py`. Callers can `except GitHubRateLimitError`
  specifically to decide "abort/back off" vs. a generic
  `except GitHubError` for "this failed." All three still subclass
  `Exception`, so existing `except Exception` call sites
  (`scripts/collect_dataset.py`) keep working unchanged.
- **Dead header-construction code removed:** headers are now built once
  in `_headers()` (`Accept: application/vnd.github+json` +
  `Authorization` if a token is set) and actually sent on every
  request.

### Thread-safety of `GitHubClient` + `ThreadPoolExecutor`

`analyze_user()` now gives each worker thread its own lazily-created
`GitHubClient` (and therefore its own `requests.Session`) via
`threading.local()`, instead of sharing one client across all 8
workers. This removes the previous fragile-but-undocumented assumption
that `requests.Session` is safe for concurrent use, while keeping most
of the connection-reuse benefit — each worker thread still reuses its
own session across every repo it handles during the run. Confirmed by
`tests/test_pipeline_repo_failure_handling.py::test_analyze_user_gives_each_worker_thread_its_own_client`
(asserts at most `1 + MAX_REPO_WORKERS` client instances are ever
created — one per worker thread, never one per repo). `max_workers=8`
is unchanged from before — already conservative for this network-bound
workload, kept to preserve the same batch performance.

### Repository-level failure policy

`fetch_repo_data()` now distinguishes three cases:

| Failure | Behavior |
|---|---|
| `get_user()` / `get_repositories()` fails | Propagates — profile cannot be analyzed. |
| One repo's README is missing (404) | Expected — `readme=None`, repo still included. |
| One repo's languages/README fetch fails transiently, retries exhausted | Repo degrades gracefully (`languages={}`/`readme=None`), still included, logged at `warning`. |
| Any repo fetch hits a rate limit | Propagates and aborts the whole `analyze_user()` call. |

A rate limit is deliberately **not** treated like an ordinary transient
failure: swallowing it per-repo would mean every remaining repo in the
batch also fails the same way, silently producing a profile built
almost entirely from degraded (empty) data instead of surfacing the
real problem. Confirmed by
`tests/test_pipeline_repo_failure_handling.py`.

## Stage 2 — Repository parsing (`github/parser.py`)

`parse_repo()` assumes every field GitHub's schema documents is present
and non-missing (`repo["name"]`, `repo["stargazers_count"]`, etc.). It
does not defend against `get_repositories()` having returned something
other than a list (e.g. GitHub's own error-object shape,
`{"message": "...", "documentation_url": "..."}`, if a caller ever
relaxes the status-code check) — that would produce a `TypeError`
iterating a dict instead of a clear error.

## Stage 3 — Feature extraction (`features/`, renamed from `feautures/` in Milestone 3)

See `docs/ARCHITECTURE.md` §5/§5a/§5b for full detail. As of Milestone 1
(feature correctness — see `docs/CHANGELOG_DEV.md`), all five
extractors return deterministic zero/sentinel values for an empty repo
list instead of raising: a brand-new GitHub account with 0 public repos
now flows all the way through to a clean `0/100` score
(`calculate_readiness_score` needs no change — it already handled
zero-valued features correctly, it just never used to receive them
because the extractors crashed first). The `description_coverage_ratio`
always-1.0 bug and the `ml.py` keyword false-positive issue described
in the previous revision of this document are also fixed — see
`docs/ML_NOTES.md` §2 for the corrected feature definitions.

## Stage 4 — Scoring (`scoring/readiness.py`) — test coverage added in Milestone 3

Pure, deterministic, feature-dict in → score-dict out. No external
calls, no randomness. Previously had no dedicated tests; now covered by
`tests/test_scoring_readiness.py` (90 tests: min/max, every if/elif
boundary, category-sum-to-total, determinism, representative profiles —
see `docs/ARCHITECTURE.md` §11). No scoring bug was found and no
weights/thresholds changed. No versioning of the scoring rubric itself
still exists (see `docs/ML_NOTES.md`).

## Stage 5 — Persistence (`db/`) — snapshot semantics reviewed in Milestone 3

`save_user()` then `save_profile_features()` are called sequentially
from `analyze_user()`, each opening/committing/closing its own
`SessionLocal()`. There is no single transaction wrapping "upsert user +
insert feature row" — if `save_profile_features()` fails after
`save_user()` already committed, the user row is updated with no
corresponding feature snapshot, and the caller has no way to detect or
roll that back (`analyze_user()` has no try/except here, so the
exception does propagate to the caller rather than silently returning a
result that looks saved — confirmed by
`tests/test_analyze_user_pipeline.py::test_persistence_failure_surfaces_instead_of_returning_a_result`).
For the current single-process CLI usage this is low risk; it becomes a
real correctness gap the moment there's a web frontend making
concurrent requests.

**`save_profile_features()` always inserts a new row** — there is no
upsert and no unique constraint on `ProfileFeature.user_id`, so
re-analyzing the same user N times produces N rows. This is reviewed in
detail, with concrete numbers from the current dev database, in
`docs/ARCHITECTURE.md` §7a. The dataset-building implication is defined
in `docs/ML_NOTES.md` §6 — no schema change was made this milestone.

## Stage 6 — Raw inspection (`scripts/show_dataset.py`)

`pd.read_sql("SELECT * FROM profile_features", engine)` loads the whole
table unfiltered — every column, every row, every historical snapshot.
As of Milestone 4 this is **an inspection tool only, not the dataset
path**: it does no dedup, no column selection, no validation. Use
`scripts/dataset_report.py` / `scripts/build_dataset.py` (Stage 6b) to
get the actual Dataset V1. `show_dataset.py` is kept for quick "what's in
the DB right now" checks.

## Stage 6b — Dataset V1 construction (`src/gitscore/dataset/`, `scripts/build_dataset.py`) — Milestone 4

`build_dataset(session_factory=SessionLocal)` in
`src/gitscore/dataset/builder.py`:

1. **Explicit `select(...)`** over `ProfileFeature` joined to `User` —
   every feature column, the target (`readiness_score`), plus four
   internal-only columns (`snapshot_id`, `user_id`, `github_username`,
   `collected_at`). No `SELECT *`; no "drop columns that look like ids"
   afterwards.
2. **Latest valid snapshot per user** — sort by
   `(collected_at, snapshot_id)` ascending, `groupby("user_id").tail(1)`.
   The `snapshot_id` tie-break makes the choice deterministic even when a
   user has two snapshots with the same `collected_at`. This is the
   query-time policy `docs/ML_NOTES.md` §6 defined in Milestone 3, now
   implemented.
3. **Duplicate-user detection** — counts users with >1 snapshot and
   reports the usernames (does not error; that is what "latest snapshot"
   resolves).
4. **Deterministic row order** — ascending `github_username`, applied
   before `github_username` is dropped.
5. **Dtype coercion** — numerics via `pd.to_numeric(errors="raise")`,
   booleans → `bool`, `most_used_language` → pandas `category` over
   strings with `""` (never null) for any missing value.
6. **Identifier / timestamp columns removed** — the four internal-only
   columns are dropped; the returned frame is exactly
   `schema.DATASET_COLUMNS` (30 features + target).
7. **`schema.validate_frame`** on the result — exact columns+order, no
   identifier/timestamp columns, no nulls, numeric/boolean/categorical
   type checks. Raises `DatasetSchemaError` / `DatasetValidationError`
   on malformed data. An empty DB yields an empty-but-valid frame.

`scripts/build_dataset.py` runs the builder, prints
`dataset_quality_report` (unique users, rows before/after selection,
duplicates, missing values, dtypes, target distribution, numeric summary,
`most_used_language` distribution, constant/near-constant features), then
`export_dataset` writes `data/processed/gitscore_dataset_v1.csv`
deterministically (fixed column + row order, `\n` endings, no index — two
runs byte-identical) plus a `.meta.json` sidecar (the three version
stamps + counts + a build timestamp). `data/processed/` is gitignored —
the CSV is a derived artifact; the SQLite DB is the source of truth.
`scripts/dataset_report.py` prints the report with no file writes.

Confirmed by `tests/test_dataset_builder.py`,
`tests/test_dataset_schema.py`, `tests/test_dataset_export.py`,
`tests/test_dataset_report.py`.

**Not yet done:** no real dataset has been built from real GitHub data —
the dev DB still holds only the 13 pre-fix rows (`docs/ML_NOTES.md` §7),
and `SCORING_RUBRIC_VERSION` is a code constant, not a per-row DB column
(`docs/ML_NOTES.md` §4/§8).

## Stage 7 — ML (not yet implemented)

No CatBoost code exists anywhere in the repo (`grep` for `catboost`
returns nothing outside the keyword list in `features/ml.py`, and it
is not installed in `.venv`). `docs/ML_NOTES.md` covers what needs to
be true before this stage is added.

## Stage 8 — Explanations / recommendations / UI (not yet implemented)

No code exists for either. `CLAUDE.md` explicitly defers these until
after the MVP is stable — consistent with what's in the repo today.

## V2 pipeline (Milestone 5D) — a separate path, not a replacement

Everything above (Stages 0-6b) is V1: `pipeline/analyze.py::analyze_user()`,
completely unchanged by Milestone 5D. A second, separate entry point now
exists: `gitscore.pipeline.evidence.extract_candidate_evidence(username)`,
which fetches the repository listing, selects repositories for deep
analysis (Milestone 5B's job-independent generic ranking, optionally
unioned with Milestone 8D.2's job-relevance retrieval -- see below),
deep-analyzes only the selected repositories (languages, README,
`requirements.txt`/`pyproject.toml`/`package.json`, Docker), and returns
a `CandidateEvidenceProfile` (Milestone 5C) instead of a readiness
score. It does not touch `features/*`, `scoring/readiness.py`, or
Dataset V1. See `docs/ARCHITECTURE.md` §15 for the full data flow,
extractor list, API cost model, and confidence/failure semantics, and
`scripts/inspect_evidence_profile.py` to run it against a real account.

### Job-aware repository retrieval — Milestone 8D.2 update

`extract_candidate_evidence()` gained one new optional parameter,
`job_relevance_terms` -- omitted (the default), repository selection is
EXACTLY Milestone 5B's frozen generic ranking, byte-for-byte unchanged.
When supplied (only by `analyze_job_fit()`, below, which has a real job
to be aware of), selection becomes the deterministic union of that
generic top-N and a second, independent "does this repository look
relevant to THIS job" signal (`gitscore.ranking.job_relevance`), bounded
at 15+10=25 repositories total. Exists because Milestone 5B's generic,
job-independent ranking can and does exclude a repository that is
highly relevant to one specific job posting on a prolific account (8C's
own documented finding). `CandidateEvidenceProfile`'s shape is
unchanged; its CONTENT may now differ between two calls for the same
candidate against two different jobs -- see
`docs/ARCHITECTURE.md` §26.5 for the documented caching caveat this
implies, and §26 for the full design. `rank_repositories()`/
`RankingWeights` (Milestone 5B) are completely untouched.

### README evidence attribution — Milestone 8D.3 update

`extraction/readme.py` (§15.6/§15.9's README source in the Stage/§15
extractor list) now distinguishes a textually-correct alias match from
a match that's safe to ATTRIBUTE to the repository: a mention under a
"## notable forks"/"## related"/etc. heading, or immediately adjacent to
a negation/future-intent phrase ("does not use X", "X is on the
roadmap"), no longer produces Evidence -- see
`docs/ARCHITECTURE.md` §27 and
`docs/evaluation/MILESTONE_8D3_EVIDENCE_ATTRIBUTION.md` for the full
root cause (the `karpathy/llm.c` -> `language.cpp` false positive) and
before/after numbers. `EXTRACTOR_VERSION` `readme:v3` -> `readme:v4`.
Every other extractor, the matcher, the assessment formula, the job
parser, and M5B ranking / 8D.2 job-aware retrieval are unaffected --
this is a README-extraction-only, additive precision fix.

## Job-fit pipeline (Milestone 7A/7B) — built on top of V2, not V1

Given the `CandidateEvidenceProfile` above plus a parsed job posting,
two more deterministic stages produce a human-facing result:
`gitscore.matching.match_job(candidate_profile, job_profile)` ->
`JobMatchAnalysis` (per-requirement `SUPPORTED`/`NOT_OBSERVED`/
`NOT_ASSESSABLE`), then `gitscore.assessment.assess_job(match_analysis)`
-> `JobAssessment` ("GitHub Evidence Alignment" and required/preferred
submetrics). See `docs/ARCHITECTURE.md` §20/§21.

### Job-description parser and concept registry — Milestone 8D.1 update

`parse_job_description()`'s shape and the job-fit pipeline above are
UNCHANGED — 8D.1 only improves what the parser's `concepts/registry.py`
step resolves and how a handful of OR/alternative-group edge cases
parse, following up on Milestone 8C's real-world evaluation
(`docs/evaluation/MILESTONE_8C_EVALUATION.md`). Five new concepts
registered (`infra.kubernetes`, `language.sql`, `language.swift`,
`language.kotlin`, `framework.react_native`), a generic "most-specific
alias wins" fix for overlapping concept matches (e.g. "React Native" no
longer resolves as plain "React"), a bounded fix for bare single-letter
language names in job-description prose (the `language.c`/"Strong C
experience" case), and three OR-group trailing-word/prefix-stripping
fixes. `CONCEPT_REGISTRY_VERSION` 3 -> 4,
`JOB_DESCRIPTION_PARSER_VERSION` `v2` -> `v3`,
`readme.py`'s `EXTRACTOR_VERSION` `v2` -> `v3` (the alias-collision fix
also applies to README evidence extraction, Stage/§15's extractor
list). `JOB_REQUIREMENT_SCHEMA_VERSION`, `EVIDENCE_SCHEMA_VERSION`,
`MATCHER_VERSION`, and `SCORING_VERSION` are all unchanged — `match_job()`
and `assess_job()` above are unaffected; they simply now receive more
complete, more accurate input from the parser/extractors. See
`docs/ARCHITECTURE.md` §25 and
`docs/evaluation/MILESTONE_8D1_PARSER_IMPROVEMENTS.md` for the full
detail and before/after benchmark numbers.

### Job-description parser — Milestone 9A update (lossless requirement preservation)

Same shape, one new parser behavior: a requirement bullet whose only
technical content is unregistered (`"Knowledge of Vue or Angular"`,
`"...SPI, I2C, and UART"`, `"Experience with dbt"`) no longer produces
ZERO `JobRequirement` rows. It now either mints a shape-confirmed
`unresolved:<term>` concept/alternative-group (when the item is
capitalized/acronym-shaped, matching what frozen gold already expected)
or, failing that, a new non-fabricating `category="unresolved_requirement"`
placeholder (`concept_id=None`) — which the UNCHANGED matcher/assessment
stages above always resolve to `NOT_ASSESSABLE`, never `SUPPORTED`.
`match_job()`/`assess_job()` themselves are unaffected; they simply now
receive a requirement row, where before there was none, for these
specific claim shapes. `JOB_DESCRIPTION_PARSER_VERSION` `v3` -> `v4`;
every other version constant is unchanged. See `docs/ARCHITECTURE.md`
§28 and `docs/evaluation/MILESTONE_9A_REQUIREMENT_PRESERVATION.md` for
the full root-cause trace and before/after numbers.

## End-to-end orchestration (Milestone 7C) — `gitscore.application`

`gitscore.application.job_fit.analyze_job_fit(username, job_description)`
composes every stage above into one call:

```
username                              raw job-description text
    |                                         |
    v                                         v
extract_candidate_evidence()  <--terms--  parse_job_description()
    |                           (8D.2)         |
    v                                         |
CandidateEvidenceProfile  ------+--------------+
                                 v
                           match_job()  ->  JobMatchAnalysis  ->  assess_job()  ->  JobAssessment
```

Milestone 8D.2 adds the `<--terms--` edge: `job_description` is still
parsed first (same fail-fast reasoning as before), and its parsed
`JobRequirementProfile` is now also converted into job-relevance terms
and passed into `extract_candidate_evidence()`, so repository selection
is job-aware end-to-end for this one caller. `match_job()`/`assess_job()`
are unaffected -- they still only ever see whatever Evidence the
selected repositories' real deep extraction produced.

It introduces no new analysis logic -- it calls each existing stage
function exactly once and returns a `JobAnalysisResult` bundling
`candidate_profile`, `job_profile`, `assessment`,
`extractor_failures`, `unknown_dependency_names`, and (Milestone 9C)
`unparsed_claims`. See `docs/ARCHITECTURE.md` §22 for the full contract,
failure semantics, and dependency-injection strategy, and
`scripts/analyze_job.py` to run it against a real account.

### Parser diagnostics and presentation-layer interpretation status — Milestone 9C

`analyze_job_fit()` now calls `parse_job_description_with_diagnostics()`
(new sibling of the unchanged `parse_job_description()`) instead of
`parse_job_description()` -- the ONE change to this function's body.
This surfaces `UnparsedClaim`s (claims segmentation judged requirement-
shaped for which zero `JobRequirement` rows were ever produced) as a
pipeline-level diagnostic, exactly like `extractor_failures` above.
`match_job()`/`assess_job()` are completely unaffected -- the
`JobRequirementProfile` they receive is byte-for-byte identical to what
`parse_job_description()` itself would have produced. Separately,
`gitscore.api.serialization` gained a presentation-only
`interpretation_status` classification (`"recognized"` /
`"non_technical"` / `"unparsed_placeholder"`) that distinguishes
GitScore's own parser uncertainty from a genuinely non-technical
requirement within the existing `NOT_ASSESSABLE` status -- no new
`MatchStatus`, no scoring-formula change. See `docs/ARCHITECTURE.md`
§29 and `docs/evaluation/MILESTONE_9C_ASSESSMENT_TRANSPARENCY.md` for
the full design audit and before/after detail.

### Safe section-state handling -- Milestone 10B

`segment_description()`'s section-tracking state machine
(`jobs/parsing/segmentation.py`) gained one internal state,
`_SectionKind.UNKNOWN`: an unrecognized, colon-terminated, non-bulleted
heading-shaped line now resets section state instead of silently
leaving a stale REQUIRED/PREFERRED kind in effect for the rest of the
document (M10A's highest-severity traced defect -- a real posting's
"When you join our team:"/"Working Arrangement" style transition was
turning company bio, legal/EEO text, and salary disclosures into
scored, fabricated requirement rows). `Claim.necessity_hint` and
`infer_necessity()`'s return type both widen to `Necessity | None`;
`_requirements_from_claim()` (`jobs/parsing/parser.py`) now
short-circuits to zero rows when necessity cannot be resolved, which
routes the claim through the EXISTING Milestone 9C `UnparsedClaim`
mechanism -- `parse_job_description()`'s signature,
`JobRequirementProfile`'s schema, the matcher, and the scoring formula
are all completely unchanged; only `JOB_DESCRIPTION_PARSER_VERSION`
bumps (`v4` -> `v5`). See `docs/ARCHITECTURE.md` §32 and
`docs/evaluation/MILESTONE_10B_SECTION_STATE_SAFETY.md` for the full
design review and measured before/after.

### Real-world heading recognition -- Milestone 10C

`segment_description()`'s heading recognition (`jobs/parsing/segmentation.py`)
replaces the small, exact-phrase `_HEADING_KIND` table M10A found too
narrow (Root Cause 1 -- "Required skills" vs. "Requirements," "Position
Responsibilities" vs. "Responsibilities," no category at all for a
"what you will learn" section) with `_classify_heading_line()`: a
structural shape gate independent of word content, then anchored
root-word families (`REQUIRED`/`PREFERRED`/`RESPONSIBILITY`/new
`LEARNING`/`NON_QUALIFICATION`) with built-in collision exclusions and
an honest `UNKNOWN` outcome for a line matching more than one family --
never a forced, fixed-precedence winner. `LEARNING` is a new internal
`_SectionKind` (joins `UNKNOWN` in never mapping to a `Necessity`); the
existing `SKIP` kind's recognized vocabulary widens (`NON_QUALIFICATION`).
`Claim`, `JobRequirement`, `UnparsedClaim`, the matcher, and the scoring
formula are all completely unchanged; only `JOB_DESCRIPTION_PARSER_VERSION`
bumps (`v5` -> `v6`). See `docs/ARCHITECTURE.md` §33 and
`docs/evaluation/MILESTONE_10C_SECTION_CLASSIFICATION.md` for the full
design review, the real implementation-time regression found and
fixed, and the measured before/after on both real postings.

### Alternative-requirement semantics -- Milestone 10D

`classify_alternative_claim()` (`jobs/parsing/alternatives.py`) gains
an explicit ANY-of trigger-phrase path, tried BEFORE the ordinary
bare-"or" path: six lead-in phrases ("one or more of," "at least one,"
"any one of," "one of the following," "any of," "either of") checked
independently of a literal "or" at all (M10A Root Cause 4 -- Manulife's
"at least one programming language (e.g., Java, Python, Go,
JavaScript)," previously four independent REQUIRED rows instead of one
ANY-of-4 group). The ordinary bare-"or" path (`_split_alternative_segments`)
gains an idiom guard preventing "<number-word> or more" from being
read as a list separator (M10A Root Cause 5 -- SOTI's "one or more of
the following programming languages: ...," previously the whole
9-language enumeration lost to the conservative `alternative_requirement`
placeholder). Both paths share the same extracted
`_classify_segment_list()` resolution loop, which also gained a
shape-gated fix closing a fabrication path (`unresolved:one`,
`unresolved:more_of:_c`) found while reproducing Root Cause 5 on a
differently-punctuated sentence. `JobRequirement`, the matcher, and
the scoring formula are all completely unchanged; only
`JOB_DESCRIPTION_PARSER_VERSION` bumps (`v6` -> `v7`). A MIXED AND/OR
shape ("Python or Java and SQL") is explicitly NOT addressed --
deferred as a newly-identified Root Cause 6. See `docs/ARCHITECTURE.md`
§34 and `docs/evaluation/MILESTONE_10D_ALTERNATIVE_SEMANTICS.md` for
the full evaluation-first design review and the measured before/after
on both real postings.

### Narrative vs. applicant-qualification semantics -- Milestone 10E

Between `segment_description()` (Part 3) and necessity/importance
inference (Part 7), one new step: `necessity.py::resolve_necessity_hint()`
computes an "effective" necessity hint from `Claim.necessity_hint`
PLUS two NEW, additive facts `segmentation.py` now also tracks per
claim -- `Claim.section_kind` (the real `_SectionKind`, not just the
lossy REQUIRED/PREFERRED hint `RESPONSIBILITY` already collapsed into)
and `document_has_any_recognized_heading()` (does the WHOLE posting
have a heading anywhere, distinguishing a genuinely unsectioned posting
from narrative prose that merely precedes the SAME document's own
later real sections). An explicit local REQUIRED/PREFERRED marker in a
claim's own text still wins unconditionally, exactly as before; a
`RESPONSIBILITY`/`LEARNING`/`UNKNOWN` claim, a narrative PREAMBLE claim,
or ANY claim matching a new, narrow LEARNING/COMPANY narrative-cue
regex pair (`jobs/parsing/narrative.py`, new module) is otherwise routed
to the EXISTING "zero requirements -> `UnparsedClaim`" diagnostic
fallback instead of a scored `JobRequirement`. Fixes the real SOTI
"Opportunity" narrative paragraph (fabricated a `(language.csharp,
language.sql)` alternative group) and the real Manulife "Collaborate
with engineering and business teams..." responsibility bullet
(fabricated a `category='soft_skill'` requirement). `infer_necessity()`,
every concept-resolution detector, `JobRequirement`, the matcher, and
the scoring formula are all completely unchanged; only
`JOB_DESCRIPTION_PARSER_VERSION` bumps (`v7` -> `v8`). The SKIP-section
blanket-suppression gap and `non_technical.py`'s own vocabulary-coverage
gaps, both found during this milestone's own evaluation, are explicitly
NOT fixed here. See `docs/ARCHITECTURE.md` §35 and
`docs/evaluation/MILESTONE_10E_NARRATIVE_REQUIREMENT_SEMANTICS.md` for
the full evaluation-first design review and the measured before/after
on both real postings.

**Milestone 11-A1 follow-up:** two narrow fixes to the SAME claim-
construction detectors, found during Milestone 11's broader
generalization review, confirmed independent of any line-wrap defect.
`concepts.py`'s comma-list unknown-term promotion now shape-gates any
multi-word leftover fragment (closing a fabrication path that
produced `unresolved:our_main_database`/`unresolved:is_required` from
ordinary prose); `narrative.py`'s company-narrative cue gains one new
alternative for `"our ... backend/frontend/codebase/infrastructure"`
phrasing. No new pipeline stage, no schema/matcher/scoring change.
`JOB_DESCRIPTION_PARSER_VERSION` bumps `v8` -> `v9`. See
`docs/ARCHITECTURE.md` §36 and `docs/CHANGELOG_DEV.md`'s Milestone
11-A1 entry.

**Milestone 11-A2 follow-up:** `segment_description()` (Part 3) now
extends an ordinary line's content span across any immediately-
following soft-wrap-continued line -- comma/semicolon-ending, or
ending in a closed, generic English function-word/copula-verb/
contraction vocabulary -- always stopping at a heading, a bullet, or a
blank-line paragraph gap, via direct slicing of the original
description text (no rewritten string, no offset-mapping table).
Paired with widening every literal single-space word separator in
`narrative.py`'s/`necessity.py`'s own cue/marker regexes to `\s+`, so a
phrase spanning a reconstructed multi-line `Claim`'s embedded newline
is still recognized. Closes the real residual M11-A1 left (a
word-wrapped company-narrative sentence still fabricating 3 spurious
rows) down to a measured, disclosed 2 -- not a claimed full fix (a
line ending in an ordinary content word with no corroborating
punctuation is a documented, accepted residual ambiguity).
`infer_necessity()`'s own precedence, every detector, `JobRequirement`,
the matcher, and the scoring formula are all completely unchanged;
only `JOB_DESCRIPTION_PARSER_VERSION` bumps (`v9` -> `v10`). See
`docs/ARCHITECTURE.md`'s Milestone 11-A2 section and
`docs/evaluation/MILESTONE_11_A2_LINE_WRAP_INTEGRITY.md` for the full
evaluation-first design review and the measured before/after.

**Milestone 11-B Stage 1 follow-up (no pipeline flow change):** a new,
standalone `jobs/parsing/qualification.py` module (`Qualification`,
`project_qualification()`) exists for a future extraction stage to
build on, but **is not called anywhere in this pipeline today** --
`_requirements_from_claim` still builds `JobRequirement`/
`UnparsedClaim` directly, exactly as described above. Confirmed by a
dedicated test, not just by omission. See `docs/ARCHITECTURE.md`'s
Milestone 11-B section and
`docs/evaluation/MILESTONE_11_B_STRUCTURED_QUALIFICATION_MODEL.md`'s
implementation addendum.

**Milestone 11-B Stage 2B follow-up (no pipeline flow change):** a new,
standalone `jobs/parsing/qualification_adapter.py` module can convert
an ALREADY-PRODUCED `JobRequirement`/`UnparsedClaim` into a
`Qualification` and back, purely for offline validation
(`scripts/evaluate_m11b_stage2b_compatibility.py`) -- it is not called
anywhere in this pipeline, confirmed by a dedicated test. See
`docs/ARCHITECTURE.md`'s Milestone 11-B Stage 2A/2B section and
`docs/evaluation/MILESTONE_11_B_STAGE_2A_SHADOW_INTEGRATION.md`'s
implementation addendum.

**Milestone 11-C follow-up (no pipeline flow change):** a new,
standalone `jobs/parsing/competency_extraction.py` module can produce
`Qualification` objects for technical-competency language ("concurrency,"
"circuit theory," ...) from already-segmented claim text -- but **is
not called anywhere in this pipeline today**, confirmed by a dedicated
test. `_requirements_from_claim` still has zero representation for
`TECHNICAL_COMPETENCY` claims, exactly as described above (M11's own
9% recall finding, unchanged). See `docs/ARCHITECTURE.md`'s Milestone
11-C section and
`docs/evaluation/MILESTONE_11_C_COMPETENCY_EXTRACTION.md` for the full
evaluation-first comparison and offline prototype.

**Milestone 11-E follow-up (no pipeline flow change):** the same
module gained a second, additive function,
`extract_competency_qualifications_v2()`, tolerant of paraphrased
competency language (plurals, grammatical variants, a bounded alias
table) -- v1 is unmodified; **neither v1 nor v2 is called anywhere in
this pipeline**, confirmed by a dedicated test. See
`docs/ARCHITECTURE.md`'s Milestone 11-E section and
`docs/evaluation/MILESTONE_11_E_PARAPHRASE_EXTRACTION.md` for the full
comparison, measured results, and the one disclosed precision cost
(an unexpected sibling tag on one compound-phrase shape).

**Milestone 11-G1 follow-up (no pipeline flow change):** `extract_competency_qualifications_v2()`
gained a structural fix for alternative-requirement (OR-list) safety --
a sentence naming several alternatives where only one matches a known
tag now correctly declines (`missing_contract`) instead of silently
resolving to that one tag. v1 is unmodified; **neither v1 nor v2 is
called anywhere in this pipeline**, confirmed by a dedicated test. See
`docs/ARCHITECTURE.md`'s Milestone 11-G1 section and
`docs/evaluation/MILESTONE_11_G1_ALTERNATIVE_REQUIREMENT_SAFETY.md` for
the full root-cause trace and measured results.

**Milestone 11-G2 follow-up (no pipeline flow change):** `extract_competency_qualifications_v2()`
gained three new, OPT-IN, keyword-only parameters
(`section_kind`/`document_has_recognized_heading`/`has_section_context`,
each defaulted so every existing call site is byte-identical to
before) letting a caller supply real section context (the same
`Claim.section_kind` this pipeline's own `segment_description()`
already computes) so necessity resolution can reuse the REAL,
already-tested `resolve_necessity_hint()` instead of always passing a
hardcoded `None` hint. v1 is unmodified; **neither v1 nor v2 is called
anywhere in this pipeline**, confirmed by a dedicated test -- this
module still does not call `segment_description()` itself, nor is it
wired into `_requirements_from_claim`. See `docs/ARCHITECTURE.md`'s
Milestone 11-G2 section and
`docs/evaluation/MILESTONE_11_G2_SECTION_CONTEXT.md` for the full
root-cause trace and measured results.

**Milestone 11-G3 follow-up (no pipeline flow change, no production code touched):** a new,
purely additive OFFLINE EVALUATION harness chains
`segment_description()`/`document_has_any_recognized_heading()` ->
`extract_competency_qualifications_v2(..., has_section_context=True)`
-> `project_qualification()` to validate that these already-existing,
already-tested pieces compose correctly on complete, multi-section job
descriptions. **This pathway is never called by `parse_job_description()`/
`_parse()`/`_requirements_from_claim`**, confirmed by a dedicated test
inspecting `parser.py`'s own source. One genuine, systemic integration-
interface mismatch was found and disclosed, not fixed: `segmentation.py`'s
own claim-admission vocabulary is narrower than `competency_extraction.py`'s
own qualifying-intent vocabulary, so some sentences the offline extractor
could recognize never become a `Claim` at all outside a recognized
section. See `docs/ARCHITECTURE.md`'s Milestone 11-G3 section and
`docs/evaluation/MILESTONE_11_G3_END_TO_END_QUALIFICATION_UNDERSTANDING.md`
for the full architecture, measured results, and this finding's exact
reproduction.

**Milestone 11-G4 follow-up (no pipeline flow change, segmentation.py byte-unchanged):**
a new, purely additive OFFLINE module,
`qualification_admission_recovery.py`, closes exactly the gap M11-G3
disclosed: `recover_unadmitted_qualification_claims()` re-walks a
description using `segmentation.py`'s own real, private helpers
(reused via import, never duplicated) and recovers a `Claim` for
content outside a recognized section that fails `_looks_like_requirement`
but passes `competency_extraction.py`'s own `_QUALIFYING_INTENT_V2`
gate. **`segmentation.py` itself was never modified** -- confirmed by
`git diff` and by a dedicated test that fails if it ever is. **This
recovery function is never called by `parse_job_description()`/`_parse()`/
`_requirements_from_claim`**, confirmed by a dedicated test. See
`docs/ARCHITECTURE.md`'s Milestone 11-G4 section and
`docs/evaluation/MILESTONE_11_G4_QUALIFICATION_ADMISSION.md` for the
full strategy comparison and measured results.

**Milestone 11-G6 fix (live pipeline flow unchanged — same stages,
same call order; `segmentation.py`'s heading-family matching logic is
the only thing that changed within Stage 1 of the job-description
parse):** M11-G5's independent validation traced 7 of 8 missed
qualifications on a real posting to `segmentation.py` misclassifying a
genuine candidate-profile heading ("Who We Are Looking For:") as a
company-narrative `SKIP` section — total, unrecoverable suppression,
upstream of even the local-REQUIRED/PREFERRED-marker safety net in
`necessity.py`. A new, generic `_CANDIDATE_PROFILE_ROOT` vocabulary now
excludes that false `SKIP` match; the heading falls through to the
EXISTING `UNKNOWN` path instead (diagnostic-eligible, never a forced
`REQUIRED` default). `JOB_DESCRIPTION_PARSER_VERSION` bumps `v10` ->
`v11`. Every downstream stage (necessity resolution, `_requirements_from_claim`,
dedup, matcher, scoring) is unmodified and untouched by this fix — it
only changes which claims REACH those stages. See `docs/ARCHITECTURE.md`'s
Milestone 11-G6 section and
`docs/evaluation/MILESTONE_11_G6_HEADING_CLASSIFICATION.md` for the
full root-cause trace, strategy comparison, and measured before/after
results.

**Milestone 11-G7 fix (live pipeline flow unchanged — same stages,
same call order; `segmentation.py`'s heading word-count shape gate is
the only thing that changed within Stage 1):** a genuine heading over
7 words going unrecognized let `segment_description()`'s single
forward-carrying section state leak across the boundary into
subsequent content — confirmed, in the worst cases, to fabricate a
scored, assessable `JobRequirement` from responsibility prose (a stale
`REQUIRED`/`PREFERRED` state admits content unconditionally) or to
silently, totally suppress a genuine REQUIRED qualification (a stale
`SKIP` state drops content before a `Claim` exists). The word-count
cap now branches on signal strength — 14 words for colon/ALL-CAPS/
Markdown-terminated (strong-signal) lines, the unchanged 7 for bare
title-case (weak-signal) lines — recognizing genuine long headings
while still rejecting long colon-terminated lead-in sentences that
introduce sub-lists from inside an already-open section (confirmed,
by adversarial testing, to be the real risk a naive uniform raise or
an unbounded removal would have reintroduced). `JOB_DESCRIPTION_PARSER_VERSION`
bumps `v11` -> `v12`. Every downstream stage (necessity resolution,
`_requirements_from_claim`, dedup, matcher, scoring) is unmodified and
untouched — this fix only changes WHETHER a line is recognized as a
heading at all. See `docs/ARCHITECTURE.md`'s Milestone 11-G7 section
and `docs/evaluation/MILESTONE_11_G7_SECTION_BOUNDARY_INTEGRITY.md`
for the full root-cause trace, strategy comparison, and measured
before/after results.

### Compound AND/OR containment -- Milestone 11-G17

Inside per-claim alternative classification (`alternatives.py`), a claim
that would become one flat OR group but structurally mixes AND with OR
("Docker or Kubernetes, and Python") is now classified `unsafe`, so
`_requirements_from_claim` emits the existing non-scoreable
`alternative_requirement` placeholder (NOT_ASSESSABLE; excluded from the
alignment denominator; visible as `unparsed_placeholder`) instead of an OR
group one alternative could satisfy. Simple OR and simple AND are
unchanged. `JOB_DESCRIPTION_PARSER_VERSION` bumps `v12` -> `v13`. Matcher,
assessment and scoring are untouched.

### Observability-aware scoring v2 -- Milestone 11-G19

Scoring step only (`assess_job`): after matching, each requirement is
score-eligible iff the matcher evaluated it AND every acceptable alternative
has a declared GitHub evidence-assessment capability
(`evidence/capability.py`; `unresolved:` concepts are never eligible). Only
eligible rows enter the numerator and denominator; excluded SUPPORTED /
NOT_OBSERVED rows keep their status and evidence and are reported with
`counts_toward_alignment=false` plus a stable `alignment_exclusion_reason`;
`excluded_from_alignment_count` is added to the API assessment. Eligibility
never depends on the candidate. `SCORING_VERSION` `v1` -> `v2`; parser,
matcher and extractors unchanged.

### Qualification-intent admission guard -- Milestone 11-G21

Per claim, BEFORE any `JobRequirement` is built, `_requirements_from_claim`
asks `qualification_intent.decide_qualification_intent()` whether the claim is
a candidate qualification; a claim with positive evidence of a
non-qualification frame (narrative, duty, learning, benefit, hiring process,
technology discussion, team practice, negation) yields no row and surfaces as
an `UnparsedClaim`. Negation is clause-local: a negated clause that does not
govern the qualification is masked out of the text the detectors analyse
("A degree is not required; strong Python skills are." -> Python REQUIRED only),
while the row keeps the whole claim's text and span. After `infer_necessity`, `refine_necessity` narrows
necessity on concessive / negated / softened wording (never promotes).
Segmentation, headings, alternatives (G17), concepts, matcher and scoring v2
are unchanged. `JOB_DESCRIPTION_PARSER_VERSION` bumps `v13` -> `v14`.

### Assessment clarity -- Milestone 9E

Milestone 9D's product-validation pilot found the M9C headline caveat
(`uninterpreted_requirement_count`) structurally excluded
`unparsed_claims` from the count a reader sees next to the score.
`gitscore.api.serialization` now also computes `unparsed_claim_count`
(a plain `len(result.unparsed_claims)`) as a SEPARATE, additive
`AssessmentOut` field -- never summed with `uninterpreted_requirement_count`,
since the two count category-different facts (a real row GitScore could
not interpret, vs. text that never became a row at all). Separately,
`RequirementOut` gained `concept_label` (`gitscore.concepts.registry.concept_display_label()`)
so a frontend can disambiguate two distinct `JobRequirement` rows that
share identical `original_text` (one job-posting sentence, multiple
matched concepts -- the documented, intentional Milestone 9A/6B.1 "one
row per concept" design) without re-deriving a label from the raw
concept id itself. Neither change touches `gitscore.matching`,
`gitscore.assessment`, `gitscore.jobs.parsing`, or the concept
registry's content -- see `docs/ARCHITECTURE.md` §30 and
`docs/evaluation/MILESTONE_9E_ASSESSMENT_CLARITY.md` for the full root-
cause analysis and before/after examples.

## HTTP API (Milestone 8A) -- `gitscore.api`

```
HTTP request -> gitscore.api (transport only) -> analyze_job_fit() -> response
```

`POST /api/v1/analyze` / `GET /api/v1/health`. Pure transport: validates
the request shape, calls `gitscore.application.analyze_job_fit()`
exactly once, serializes its result. No business logic lives in this
package -- see `docs/ARCHITECTURE.md` §23 for the full request/response
contract, error mapping, and dependency-injection strategy. Run locally
with `uvicorn gitscore.api.app:app --reload`. Milestone 9C added four
additive response fields (`requirements.*[].category`/
`.interpretation_status`, `assessment.uninterpreted_requirement_count`,
`unparsed_claims`) -- see `docs/ARCHITECTURE.md` §29.2; no existing
field changed meaning or shape. Milestone 9E added two more, equally
additive fields: `requirements.*[].concept_label` and
`assessment.unparsed_claim_count` -- see `docs/ARCHITECTURE.md` §30.

## Frontend (Milestone 8B) -- `frontend/`

```
Browser -> Next.js frontend (frontend/) -> HTTP -> gitscore.api -> analyze_job_fit()
```

A separate Next.js + TypeScript application, consuming the `/api/v1`
contract above over `fetch()` -- no GitScore logic is reproduced in
TypeScript. See `docs/ARCHITECTURE.md` §24 for page/component
structure, the null/zero rendering rules, and testing strategy.
Run locally: `cd frontend && npm install && npm run dev`
(`NEXT_PUBLIC_GITSCORE_API_URL` points it at the backend, default
`http://localhost:8000`). Milestone 9C split the `not_assessable`
requirement group into two labeled subsections, added a headline
caveat, and added a fourth `UnparsedClaimsSection` -- see
`docs/ARCHITECTURE.md` §29.3. Milestone 9E added a second, separate
headline caveat for `unparsed_claim_count`, a `concept_label` suffix
that disambiguates duplicate-looking requirement text (including
across contradictory statuses), a GitHub repository link on each
evidence citation, and a calibrated, non-numeric description of each
evidence type -- see `docs/ARCHITECTURE.md` §30. Milestone 9G added a
`"Known coverage gaps"` badge beside the headline score itself, plus a
generic summary sentence and a concrete, verbatim excerpt of the first
unparsed claim's text -- all derived entirely from fields the API
already returns, no backend change -- see `docs/ARCHITECTURE.md` §31.
