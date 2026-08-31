# GitScore AI — Pipeline (API → Parser → Features → Scoring → DB → ML → UI)

Status: updated 2026-08-31 (Milestone 3 — project hygiene, pipeline
testing, pre-ML release readiness). This document traces one call to
`analyze_user(username)` end to end and calls out where it deviates
from what a "GitHub profile readiness pipeline" needs to be correct and
efficient. Every claim below is backed by a file/line reference and,
for the behavioral ones, a test in `tests/`. Stage 1 reflects Milestone
2 (GitHub data collection reliability); Stage 5/6 reflect the
Milestone 3 database-snapshot-semantics review; `feautures/` paths
elsewhere have been updated to `features/` (renamed in Milestone 3).
Other content is unchanged from the 2026-08-30 audit.

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

## Stage 6 — Dataset assembly (`scripts/show_dataset.py`)

`pd.read_sql("SELECT * FROM profile_features", engine)` loads the whole
table unfiltered. Every row is one full analysis run (one `readiness_score`
plus every feature that produced it) — i.e. this *is* the training
dataset described in `docs/ML_NOTES.md`. No dedup by user, no train/test
split, no versioning of which scoring-rubric version produced each row.
**Before this becomes the real training dataset**, the dataset builder
must select only the latest `profile_features` row per `user_id` (see
`docs/ML_NOTES.md` §6) — not implemented yet, and real dataset
collection has not started (see `docs/ML_NOTES.md` §7).

## Stage 7 — ML (not yet implemented)

No CatBoost code exists anywhere in the repo (`grep` for `catboost`
returns nothing outside the keyword list in `features/ml.py`, and it
is not installed in `.venv`). `docs/ML_NOTES.md` covers what needs to
be true before this stage is added.

## Stage 8 — Explanations / recommendations / UI (not yet implemented)

No code exists for either. `CLAUDE.md` explicitly defers these until
after the MVP is stable — consistent with what's in the repo today.
