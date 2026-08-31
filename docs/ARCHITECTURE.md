# GitScore AI — Architecture

Status: updated 2026-08-31 (Milestone 3 — project hygiene, pipeline
testing, pre-ML release readiness). §1, §7, §10, and §11 reflect
Milestone 3 (package rename, dependency declaration, DB snapshot
semantics, expanded test suite). §3 and §8 reflect Milestone 2 (GitHub
data collection reliability). Other sections are unchanged from the
2026-08-30 audit snapshot.

This document describes what the code **actually does today**, not the
intended design. Where behavior is a bug rather than a decision, it is
marked **BUG**.

## 1. Module map

```
src/gitscore/
  config.py                  loads GITHUB_TOKEN from .env via python-dotenv
  github/
    client.py                GitHubClient: requests.Session wrapper over the
                              GitHub REST API (user, repos, languages, readme).
                              As of Milestone 2: full pagination, explicit
                              timeouts, bounded retry/backoff, distinguishable
                              rate-limit errors — see §3 below.
    exceptions.py             GitHubError / GitHubNotFoundError /
                              GitHubRateLimitError / GitHubRequestError.
    parser.py                parse_repo(): raw GitHub JSON -> internal repo dict
    schemas.py                EMPTY. No pydantic/dataclass schemas exist; every
                              "schema" is an untyped dict passed by convention.
  features/                  feature extractors. Renamed from the misspelled
                              `feautures` in Milestone 3 — see docs/CHANGELOG_DEV.md.
                              Now has __init__.py (see §10).
    activity.py               extract_activity_features(): repo/fork counts
    languages.py               extract_language_features(): language mix
    quality.py                extract_quality_features(): stars/forks/description
    ml.py                     extract_ml_features(): keyword-based ML detection
    readme.py                 extract_readme_features(): README content signals
    profile.py                extract_profile_features(): combines the five above.
                              This is the function pipeline/analyze.py imports.
  scoring/
    readiness.py              calculate_readiness_score(): pure function, features dict -> score dict.
                              Now has __init__.py (see §10). Dedicated test
                              coverage added in Milestone 3, see §11.
  db/
    database.py               SQLAlchemy engine/SessionLocal/Base, SQLite at data/gitscore.db
    models.py                  User, ProfileFeature ORM models
    queries.py                 save_user(), save_profile_features(): imperative upsert/insert-only.
                              See §7 for save_profile_features()'s always-insert
                              (no upsert) snapshot semantics.
  pipeline/
    analyze.py                 analyze_user(): orchestrates the whole flow, ThreadPoolExecutor
                              for per-repo fetches
scripts/
  init_db.py                   creates tables (Base.metadata.create_all)
  collect_user.py               CLI: analyze one username, print the result dict
  collect_dataset.py             CLI: analyze a hardcoded list of usernames in a loop
  show_dataset.py                loads profile_features table into a Pandas DataFrame
```

There is no web/API/UI layer yet (`scripts/` + direct Python calls only).
No `notebooks/` content exists (directory is empty).

**Milestone 1 cleanup (unchanged since, noted for history):**
`feautures/profile_features.py` was a byte-empty, unused duplicate of
`profile.py`'s import target and was deleted. `feautures/deployment.py`
(also empty, also unused — no deployment-signal feature exists) was
dropped during the Milestone 3 `feautures` -> `features` rename (it was
never carried over into the new directory). Two other empty,
unreferenced placeholder directories left over from initial scaffolding
(`src/gitscore/app/`, `src/gitscore/ml/`, `src/gitscore/nlp/` — never
git-tracked, since git doesn't track empty directories) were also
removed in Milestone 3.

## 2. End-to-end data flow

```
username (str)
  -> GitHubClient.get_user()                  1 HTTP call
  -> save_user()                              upsert into `users` table
  -> GitHubClient.get_repositories()           1 HTTP call, FIRST PAGE ONLY (see PIPELINE.md)
  -> ThreadPoolExecutor(max_workers=8).map(    per repo, 2 HTTP calls each:
       fetch_repo_data)                          get_repository_languages()
                                                  get_repository_readme()
       -> parse_repo()                        raw JSON -> clean dict
  -> extract_profile_features()               5 extractors combined via dict union
  -> calculate_readiness_score()              5 category sub-scores summed to 0-100
  -> save_profile_features()                  insert one `profile_features` row
  -> return {user, features, score, time}
```

`analyze_user()` in `src/gitscore/pipeline/analyze.py` is the single
entry point every script calls. It has no return-value caching, no
persistence-layer transaction boundary spanning the whole run (each of
`save_user` / `save_profile_features` opens and commits its own
session), and no error handling — any exception anywhere in the chain
(a bad HTTP status, a KeyError from a malformed repo, a ZeroDivisionError
from an empty repo list) propagates uncaught out of `analyze_user()`.

## 3. GitHub API layer (`github/client.py`) — updated in Milestone 2

`GitHubClient` holds one `requests.Session()` created in `__init__`.
All four public methods (`get_user`, `get_repositories`,
`get_repository_languages`, `get_repository_readme`) route through a
single internal `_get(url, params=None)` helper, so pagination/timeout/
retry/rate-limit handling is centralized in one place rather than
duplicated per method.

- **Timeout**: every request passes `timeout=self.timeout` (default
  `DEFAULT_TIMEOUT_SECONDS = 10.0`, configurable via
  `GitHubClient(timeout=...)`).
- **Retry/backoff**: `requests.exceptions.ConnectionError`/`Timeout`
  and `{500, 502, 503, 504}` responses are retried with exponential
  backoff (`backoff_base * 2**attempt`, capped at `max_backoff`;
  defaults `0.5s`/`8s`), up to `max_retries` times (default `3`, i.e. 4
  attempts total). 404s and other 4xx codes are never retried. The
  sleep call is injectable (`sleep_func=`, defaults to `time.sleep`) so
  tests never wait through real delays.
- **Rate limits**: a 403 with `X-RateLimit-Remaining: 0`, a 403 with a
  `Retry-After` header, or a plain 429 raises `GitHubRateLimitError`
  (carrying `reset_at`/`retry_after` when GitHub supplied them) —
  immediately, never retried, never waited-out automatically. A plain
  403 with none of those signals (e.g. permission denied on a private
  resource) raises `GitHubRequestError` instead, since it isn't a rate
  limit.
- **Error typing**: `_get` raises one of `GitHubNotFoundError` (404),
  `GitHubRateLimitError` (see above), or `GitHubRequestError` (every
  other non-retryable/retry-exhausted failure, carries `status_code`)
  — see `github/exceptions.py`. All three subclass `GitHubError`
  (→ `Exception`), so existing `except Exception` call sites
  (`scripts/collect_dataset.py`) still work unchanged.
- The dead header-construction code (three methods built an
  `Accept`/`X-Requested-With` dict then immediately discarded it with
  `headers = {}`) is removed; headers are built once in `_headers()`
  (`Accept: application/vnd.github+json` + `Authorization` if a token
  is set) and actually sent.

### Pagination (`get_repositories`)

Loops `page=1, 2, ...` with an explicit `per_page=100`
(`DEFAULT_PER_PAGE`), concatenating each page's items in fetch order,
until a page comes back with fewer than `per_page` items (the last
page). A `max_pages=50` (`DEFAULT_MAX_PAGES`) safety cap raises
`GitHubRequestError` instead of looping forever if GitHub ever kept
returning full pages indefinitely (~5000 repos, comfortably above any
real user's repo count). This is page-count-based termination, not
`Link`-header parsing — simpler and equally correct given a fixed
`per_page`, at the cost of relying on GitHub's documented default
page-size contract rather than an explicit "no more pages" signal from
the response itself.

`get_repository_readme()`'s existing "404 → `None`" behavior (a missing
README is an expected condition, not a failure) is preserved — now
implemented by catching `GitHubNotFoundError` internally.

## 4. Repository parsing (`github/parser.py`)

`parse_repo(repo, languages, readme)` is a pure, stateless dict
transform. It assumes every key it reads (`repo["name"]`,
`repo["stargazers_count"]`, etc.) is present — reasonable for GitHub's
documented repo schema, but it will raise `KeyError` on any
unexpected/partial payload (e.g. GitHub returning an error object
instead of a repo list, which `get_repositories` would pass through
uninspected since it only checks `status_code`).

`parse_languages()` correctly guards the empty/`None` case and returns `{}`.

## 5. Feature extractors (`features/`, renamed from `feautures/` in Milestone 3)

Each extractor is a pure function `list[dict] -> dict[str, ...]`. They
are independent of each other and of the DB/HTTP layers, which is good
for testability — `tests/test_feature_extractors_current_behavior.py`
(added by this audit) exercises them directly with synthetic repo
dicts, no network required.

**Fixed in Milestone 1** (see `docs/CHANGELOG_DEV.md` for the full
entry; tests in `tests/test_feature_extractors_current_behavior.py`
verify all of the below):
- `quality.py:9` — description-coverage condition used `or` where `and`
  was intended, so `description_coverage_ratio` was always `1.0`
  regardless of actual data. Fixed to require a non-`None`,
  non-blank description.
- `quality.py` and `languages.py` had **no empty-repo-list guard**
  (`ZeroDivisionError` / `ValueError` respectively) while `readme.py`
  and `activity.py` already guarded the same case. A brand-new GitHub
  account with 0 public repos crashed `analyze_user()`. Fixed: both now
  return deterministic zero/sentinel values for an empty repo list (see
  §5a below).
- `ml.py` matched keywords as raw substrings ("ai", "ml") with no word
  boundaries, producing false positives on ordinary words ("html",
  "container", "explain", "email"). Fixed with word-boundary-aware
  regex matching (see §5b below).

### 5a. Empty-repository-list behavior (post-fix)

All five extractors now return deterministic, documented values for an
empty repo list — either because the arithmetic naturally handles zero
(`activity.py`) or because a guard now returns explicit zero/sentinel
values (`quality.py`, `languages.py`, `readme.py`, `ml.py`):

| Field | Empty-list value | Why |
|---|---|---|
| all count fields | `0` | natural zero |
| all ratio/average fields (`description_coverage_ratio`, `average_stars`, `readme_coverage_ratio`, ...) | `0` | avoids `ZeroDivisionError`; `0` reads as "no evidence" rather than a misleading "N/A" |
| `most_used_language` | `""` (empty string) | the DB column (`ProfileFeature.most_used_language`) is non-nullable `String`, so `None` isn't an option; `""` is the chosen "no language data" sentinel |
| all boolean `has_*` fields | `False` | natural default |

`""` for `most_used_language` is a deliberate sentinel, not a real
language name — any downstream code (scoring, ML features, UI) that
branches on `most_used_language` should treat `""` as "unknown," not as
a language to compare against.

### 5b. ML keyword matching (post-fix)

`ml.py` now matches each keyword in `ML_KEYWORDS` via a pre-compiled
regex requiring non-alphanumeric boundaries on both sides
(`(?<![a-z0-9])keyword(?![a-z0-9])`), applied to the same lowercased
`"{name} {description}"` text as before. Hyphens, underscores, spaces,
and punctuation all count as valid separators, so `"my-ai-project"` and
`"llm_app"` still match — only *glued-together* substrings like `"ai"`
inside `"container"` or `"ml"` inside `"html"` are excluded. See
`tests/test_feature_extractors_current_behavior.py` for the full set of
true-positive/false-positive cases, including one parametrized over
every entry in `ML_KEYWORDS`.

### Duplicated logic — resolved

**Correction to the original audit:** `feautures/profile.py` and
`feautures/profile_features.py` were described as "byte-identical."
Re-verified while implementing Milestone 1, `profile_features.py` was
actually **empty (0 bytes)**, not a content duplicate of `profile.py`
— the original read that reported matching content was inaccurate.
Either way, `profile_features.py` was confirmed unused (`grep` across
`src/` and `scripts/` found no import of
`gitscore.feautures.profile_features`), so it has been **deleted**.
`pipeline/analyze.py` continues to import `extract_profile_features`
from `feautures/profile.py`, unchanged.

## 6. Scoring (`scoring/readiness.py`)

Pure function, `dict -> dict`. Five independently-scored categories sum
to a 0-100 total: ML Experience (35), Project Originality (20),
Documentation Quality (15), Language/Tool Relevance (20), Community
Signal (10) — matches the weights documented in `CLAUDE.md`. Each
category uses hand-written score ladders (`if/elif` chains on raw
counts/ratios) with no configuration, no versioning, and no
persisted "scoring rubric version" — if the thresholds change later,
old rows in `profile_features.readiness_score` become
incomparable to new ones with no way to tell them apart. See
`docs/ML_NOTES.md` for why this matters for ML training.

## 7. Database layer (`db/`)

- `database.py` builds a single global SQLite `engine` at
  `data/gitscore.db` (repo-root-relative, computed via
  `Path(__file__).resolve().parents[3]`) and a `SessionLocal`
  sessionmaker. `check_same_thread: False` is set, which is required
  because `ProfileFeature`/`User` writes are not currently made from
  multiple threads, but does mean SQLite's own thread-safety
  guarantees are bypassed if that ever changes.
  `from sqlalchemy.orm import sessionmaker` is imported twice
  (line 2 and line 3) — harmless but redundant.
- `models.py`: `User` and `ProfileFeature` (1 profile-feature row per
  analysis run, FK to `users.id`, no unique constraint — re-analyzing
  the same user appends a new row rather than updating). Line 35,
  `default=datetime.utcnow`, is a bare statement outside any
  `mapped_column(...)` call — dead code, does nothing, likely leftover
  from an edit.
- `queries.py`: `save_user()` does a manual select-then-insert-or-update
  (no `session.merge` / upsert). Every call opens a **new**
  `SessionLocal()` and closes it manually with no `try/finally` — an
  exception between `session.add()` and `session.close()` (e.g. a
  `commit()` failure) leaks the connection instead of rolling back and
  closing it.

No Alembic/migration tooling exists yet (`CLAUDE.md` calls this out as
acceptable for the MVP stage, "prefer Alembic if schema evolution
becomes non-trivial").

### 7a. ProfileFeature snapshot semantics (reviewed in Milestone 3, unchanged)

**Every `analyze_user()` call inserts a new `ProfileFeature` row.**
Unlike `save_user()` (select-then-update-or-insert, one row per
`github_username`), `save_profile_features()` always does
`session.add(profile_feature)` unconditionally — there is no query for
an existing row, no upsert, and `ProfileFeature.user_id` has no unique
constraint (`models.py`). Re-analyzing the same user N times produces N
`profile_features` rows, each individually timestamped via
`collected_at` (`default=datetime.utcnow`).

**Is this intentional?** It reads as a deliberate "keep every analysis
run as a timestamped historical snapshot" design (each row *is*
individually timestamped, which a pure accidental-duplicate bug
wouldn't bother doing) — but nothing in the codebase currently *uses*
that history: there is no query anywhere (`queries.py`,
`scripts/show_dataset.py`) that selects "the latest row per user" or
otherwise treats old snapshots differently from new ones. So: probably
intentional as a mechanism, currently unexploited as a policy. This is
not a bug and this milestone does not change the schema to add an
`is_latest` flag or a unique constraint — see `docs/ML_NOTES.md` §6 for
the query-time (not schema-time) policy this implies for building the
future ML dataset.

**Concrete evidence from the current dev database** (`data/gitscore.db`,
inspected during this milestone, not part of any shipped dataset): 3
users, 13 `profile_features` rows — one user (`Jango1324`) was analyzed
8 times, another (`torvalds`) 3 times, the third (`karpathy`) 2 times.
A naive `SELECT * FROM profile_features` for a dataset would therefore
represent that one user in 8 of 13 rows (~62%) despite there being only
3 distinct users — the overrepresentation risk described in §6 is not
hypothetical, it is already present in this exact database.

## 8. Pipeline orchestration (`pipeline/analyze.py`) — updated in Milestone 2

`fetch_repo_data()` is called via `ThreadPoolExecutor` over the full
repo list (`MAX_REPO_WORKERS = 8`, unchanged from before — already a
reasonable, conservative default for this network-bound workload, kept
to preserve the same batch performance). Concurrency correctness:
- **Thread-safety**: each worker thread gets its own lazily-created
  `GitHubClient` (and therefore its own `requests.Session`) via
  `threading.local()`, instead of all workers sharing one client. This
  removes the previous fragile-but-undocumented assumption that
  `requests.Session` is safe for concurrent use, while keeping most of
  the connection-reuse benefit — each worker thread still reuses its
  own session across every repo it handles during the run.
- **Per-repo failure isolation**: `fetch_repo_data()` now catches
  `GitHubError` around the languages/README fetches individually. A
  transient failure (retries exhausted) on one repo's optional metadata
  degrades that repo gracefully (`languages={}`/`readme=None`) instead
  of failing the whole batch — see `docs/PIPELINE.md` §Stage 1 for the
  full repository-level failure policy table. `GitHubRateLimitError` is
  the one exception re-raised rather than swallowed, since a rate limit
  means every remaining request is about to fail the same way.
- **Batch abort on rate limit**: repo fetches are submitted via
  `executor.submit()` (not `executor.map()`) so that when a fatal error
  (a rate limit) surfaces, every not-yet-started queued future is
  cancelled before the exception propagates out of `analyze_user()`.
  `executor.map()` would still drain its internal queue — running every
  already-submitted task to completion — before propagating, wasting
  more of an already-exhausted rate-limit budget. Futures already
  *running* when the rate limit is detected still complete (Python
  threads can't be interrupted mid-flight); with `max_workers=8` this
  bounds the worst case to a small constant, not the whole remaining
  batch. Result order is preserved (`.result()` is read back in
  submission order, matching what `executor.map()` gave before).
- Every request has an explicit timeout (`GitHubClient` §3), so a
  single hung repo fetch can no longer stall a worker thread
  indefinitely.

## 9. Scripts

- `collect_user.py` — straightforward CLI, fine.
- `collect_dataset.py` — iterates a **hardcoded** username list
  (including a deliberately-invalid username to test failure handling).
  Line 23 references `result["time"]` outside the loop; `result` is
  only bound inside the `try:` block, so if the *last* username in the
  list fails, this line raises `NameError: name 'result' is not
  defined` after printing "Collection Complete". If an *earlier*
  username fails, the line silently reports the previous successful
  run's elapsed time as if it were the batch's — misleading output.
- `show_dataset.py` — reads the whole `profile_features` table into
  Pandas, no filtering/pagination; fine at current scale, will not
  scale past a few hundred thousand rows without change.
- `init_db.py` — fine, idempotent (`create_all` is a no-op on existing tables).

## 10. Packaging / project configuration — fixed in Milestone 3

- `pyproject.toml` now declares runtime dependencies (`requests`,
  `python-dotenv`, `SQLAlchemy`, `pandas`, each with a `>=` floor
  matching what's actually exercised, no upper-bound pins) under
  `[project.dependencies]`, and `pytest` as a dev/test-only dependency
  under `[project.optional-dependencies] dev = [...]`. This was
  previously undeclared entirely — see `docs/CHANGELOG_DEV.md` Milestone
  3 for the before/after and how it was verified (`pip install -e .`
  and `pip install -e ".[dev]"` dry-run, plus a real wheel build, all
  succeeded against a real package index).
- `requirements.txt` — previously a `pip freeze` dump from an unrelated
  ROS2 project — has been **removed**. `pyproject.toml` is now the
  single source of dependency truth; keeping a second, easily-stale
  file around (exactly the failure mode that produced the ROS2 dump in
  the first place) was judged worse than not having one. If a pinned,
  fully-resolved lockfile is ever needed (e.g. for a reproducible CI/
  deployment environment), regenerate one from `pyproject.toml` at that
  time rather than hand-maintaining a second list.
- `src/gitscore/features/` (renamed from `feautures/`, see §1/§5) and
  `src/gitscore/scoring/` now both have `__init__.py`, matching every
  other package in the tree. This was previously a **fragile
  assumption**: `[tool.setuptools.packages.find]` (not
  `find_namespace`) does not include implicit namespace packages in a
  *built* wheel/sdist by default, so a non-editable `pip install .`
  would likely have silently dropped these two packages. Verified fixed
  by building a real wheel (`pip wheel . --no-deps`) and inspecting its
  contents — `gitscore/features/*.py` and `gitscore/scoring/*.py` are
  both present.
- `src/gitscore_ai.egg-info/` (generated packaging metadata) was
  **committed to git and stale**. It has been `git rm --cached` and
  deleted from the working tree; `*.egg-info/`, `build/`, and `dist/`
  are now in `.gitignore` so it can't silently get re-committed. It
  regenerates automatically on the next `pip install -e .`.
- `.env.example` was empty — 0 bytes. It now documents `GITHUB_TOKEN`
  (optional but recommended, with the rate-limit rationale) as a
  template a new contributor can `cp .env.example .env` from.
- `README.md` was empty — 0 bytes. It now covers what the score
  means/doesn't mean, architecture, setup, environment variables,
  running single-user analysis, running tests, and current project
  status. See the repository root.

## 11. Testing

Before the initial audit, `tests/` existed as an empty directory — no
test files, no CI config referencing it. The audit added
`tests/test_feature_extractors_current_behavior.py` and
`tests/test_github_client_current_behavior.py` to characterize (pin
down, with assertions) the then-current bugs and gaps, using synthetic
data and a fake `requests.Session` — no network access, no GitHub token
required.

**Milestone 1 (feature correctness)** fixed several of those bugs
(description-coverage, empty-repo-list crashes, ML keyword false
positives — see `docs/CHANGELOG_DEV.md`) and updated
`test_feature_extractors_current_behavior.py` to assert the corrected
behavior instead of the old bug, per the rule that a characterization
test must not be kept green by preserving a known defect. It also added
`tests/test_profile_module_dedup.py` covering the `profile.py` /
`profile_features.py` cleanup.

**Milestone 2 (GitHub data collection reliability)** fixed the
GitHub-client issues (pagination, timeouts, retries, rate limits,
thread-safety) left out of scope for Milestone 1. Updated
`test_github_client_current_behavior.py`'s three tests to assert the
corrected behavior, and added `tests/test_github_client_reliability.py`
(21 tests: pagination, timeouts, retry/backoff, rate limits) and
`tests/test_pipeline_repo_failure_handling.py` (6 tests: per-repo
graceful degradation, rate-limit batch-abort, one-client-per-thread).
`tests/conftest.py` gained shared `FakeResponse`/`ScriptedSession`/
`RecordingSleep` fakes so no test needs real network access or real
backoff delays.

**Milestone 3 (project hygiene / pre-ML release readiness)** added
dedicated scoring and end-to-end pipeline test coverage that didn't
exist before, plus the `feautures` -> `features` rename (with
`tests/test_profile_module_dedup.py` extended to also guard against the
old misspelled directory reappearing):
- `tests/test_scoring_readiness.py` (90 tests) — `scoring/readiness.py`
  had zero dedicated tests before this; now covers the all-zero
  minimum, the documented 100-point maximum (including extreme/absurd
  inputs that must still cap at 100), category-scores-sum-to-total,
  determinism, every if/elif ladder boundary in the rubric, and three
  hand-computed representative low/medium/high profiles. No scoring bug
  was found — every category's max matches its documented weight
  exactly (35/20/15/20/10 = 100).
- `tests/test_analyze_user_pipeline.py` (5 tests) — `analyze_user()`
  end-to-end via `tests/conftest.py::FakeGitHubClient`/
  `fake_github_client_factory` (GitHub boundary) and recording fakes for
  `save_user`/`save_profile_features` (persistence boundary): a normal
  user, a zero-repository user, a nonexistent user (propagates
  `GitHubNotFoundError`, persists nothing), per-repo metadata
  degradation still producing a complete profile, and a persistence
  failure surfacing instead of returning a result that looks
  successfully saved. (A rate-limit-during-processing scenario is
  already covered by
  `tests/test_pipeline_repo_failure_handling.py::test_analyze_user_aborts_the_batch_when_a_worker_hits_a_rate_limit`
  from Milestone 2 and is not duplicated here.)
- `tests/conftest.py` gained `raw_repo()` (shared GitHub-shaped repo
  dict builder, replacing a duplicate that previously lived only in
  `test_pipeline_repo_failure_handling.py`), `make_score_features()`,
  `FakeGitHubClient`/`fake_github_client_factory()`, and
  `FakeSavedUser`.

Run the suite with:

```
pytest
```

(a bare `pytest` from the repo root discovers and runs everything under
`tests/`; `pytest tests/ -v` still works identically.)

Current count: 166 tests, all passing. `pytest` is now declared as a
dev/test dependency in `pyproject.toml` (see §10) rather than being an
undeclared `.venv` addition.
