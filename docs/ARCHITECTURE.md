# GitScore AI — Architecture

Status: updated 2026-09-27 (Milestone 5D — bounded technical evidence
extraction). New §15 documents the first real V2 evidence-extraction
pipeline, connecting Milestone 5B's ranking to Milestone 5C's domain
model. §1, §11 and §12 reflect Milestone 4 (the `dataset/` package, the
dataset builder/report/export, the username-file collection input,
expanded test suite). §1, §7, §10 reflect Milestone 3 (package rename,
dependency declaration, DB snapshot semantics). §3 and §8 reflect
Milestone 2 (GitHub data collection reliability). Other sections are
unchanged from the 2026-08-30 audit snapshot — in particular §2's
data-flow sketch still shows the pre-Milestone-2 "first page only" /
`executor.map` shape; §3 and §8 are the current truth for the GitHub
layer. **All of §1-§14 describe V1 (`pipeline/analyze.py`) and remain
completely unchanged by Milestone 5D** — see §15 for the new, separate V2
path.

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
  dataset/                   Dataset V1 layer (Milestone 4) — see §12.
    schema.py                  column lists, version stamps, validate_frame()
    builder.py                 build_dataset(): ProfileFeature snapshots -> clean frame
    report.py                  dataset_quality_report() / format_report()
    export.py                  export_dataset(): deterministic CSV + .meta.json sidecar
    collection_input.py        parse_usernames() / load_username_file()
    exceptions.py              DatasetError / DatasetSchemaError / DatasetValidationError
scripts/
  init_db.py                   creates tables (Base.metadata.create_all)
  collect_user.py               CLI: analyze one username, print the result dict
  collect_dataset.py             CLI: batch-analyze usernames from data/collection/usernames.txt
                                (Milestone 4: no longer a hardcoded list; continue-on-failure)
  build_dataset.py              CLI: build + quality-report + export Dataset V1 CSV
  dataset_report.py             CLI: print the dataset quality report only (no file writes)
  show_dataset.py                raw SELECT * of profile_features into Pandas — INSPECTION ONLY,
                                not the dataset path (that is build_dataset.py / dataset/)
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

**Milestone 4 (clean Dataset V1 infrastructure)** added the `dataset/`
package and its tests (+65, 166 → 231):
- `tests/test_dataset_schema.py` (17) — the dataset contract
  (`FEATURE_COLUMNS` partition is complete & disjoint, no
  identifier/timestamp columns, `EXCLUDED_COLUMNS` documents the
  omissions) and every `validate_frame` failure mode.
- `tests/test_dataset_builder.py` (17) — latest-snapshot-per-user
  selection (incl. the `collected_at`-tie → `snapshot_id` tie-break),
  duplicate-user detection, deterministic ascending-`github_username`
  row order, repeated builds identical (`assert_frame_equal`), exact
  column set/order, value round-trip from the DB, identifier-leak and
  timestamp-leak prevention, `most_used_language` preserved as a
  `category`, `""` sentinel survival, and the builder validating its
  own output.
- `tests/test_dataset_export.py` (6) — CSV + `.meta.json` written,
  header == schema columns, byte-for-byte determinism, LF endings, no
  identifier columns, empty dataset → header-only CSV.
- `tests/test_dataset_report.py` (8) — empty-safe, rows before/after
  selection, target distribution, `""` in the language distribution,
  constant vs near-constant flagging, dtype coverage, formatter output.
- `tests/test_collection_input.py` (12) — username-file parsing (blank
  lines, full-line + inline comments, case-insensitive dedup, order
  preservation, first-token fallback, empty input, missing-file error,
  the committed template parses to zero usernames).
- `tests/test_collect_dataset_script.py` (5) — the refactored batch
  script continues across per-user failures and reports counts/elapsed;
  exit codes 0/2/1; the GitHub token is never printed.
- `tests/conftest.py` gained `PROFILE_FEATURE_DEFAULTS`, the `SnapshotDB`
  helper, and the `snapshot_db` fixture (a throwaway per-test SQLite DB
  with the real `User`/`ProfileFeature` schema and an `add_snapshot(...)`
  method — never touches `data/gitscore.db`).

Current count: 231 tests, all passing. No live GitHub calls, no writes to
`data/gitscore.db`.

## 12. Dataset V1 layer (`src/gitscore/dataset/`) — Milestone 4

Turns persisted `ProfileFeature` snapshots into a clean, reproducible,
one-row-per-user Pandas dataset. Read-only over the database; produces a
gitignored CSV under `data/processed/`. No model training, no rubric
change, no schema change.

### 12.1 The contract (`dataset/schema.py`)

Single source of truth — `builder`, `report`, `export` and the tests all
import their column lists from here; nothing re-derives them.

- **`FEATURE_COLUMNS`** — 30 ordered names, all from `ProfileFeature`:
  23 in `NUMERIC_FEATURE_COLUMNS`, 6 in `BOOLEAN_FEATURE_COLUMNS` (the
  `has_*` flags), 1 in `CATEGORICAL_FEATURE_COLUMNS` (`most_used_language`).
  The three lists partition `FEATURE_COLUMNS` exactly.
- **`TARGET_COLUMN`** — `readiness_score` (the rule-based label from
  `scoring/readiness.py`; see `docs/ML_NOTES.md` §3).
- **`DATASET_COLUMNS`** — `FEATURE_COLUMNS + [TARGET_COLUMN]`, the exact
  CSV column order.
- **`EXCLUDED_COLUMNS`** — `{db.column: reason}` for every deliberately
  omitted column: `profile_features.id` / `.user_id` / `.collected_at`,
  `users.id` / `.github_username` / `.name` / `.followers` /
  `.public_repos` / `.collected_at`. Identifiers, timestamps, collection
  metadata, and two `users` columns that are not V1 rubric inputs.
- **`INTERNAL_ONLY_COLUMNS`** — `snapshot_id`, `user_id`,
  `github_username`, `collected_at`: pulled by the builder for row
  selection / diagnostics, then dropped. `validate_frame` rejects any of
  them in a dataset frame.
- **`validate_frame(df, *, allow_empty=True)`** — exact column set+order;
  no forbidden identifier/timestamp columns; no nulls in required
  columns; numeric columns numeric; boolean columns ⊆ {True,False,0,1};
  categorical column all-strings. Raises `DatasetSchemaError` (shape) or
  `DatasetValidationError` (values).

### 12.2 Versioning (lightweight — constants, not a DB column)

`DATASET_VERSION = "v1"`, `FEATURE_SCHEMA_VERSION = 1`,
`SCORING_RUBRIC_VERSION = 1`. Written into the export `.meta.json` and the
quality report. When the rubric changes the process is "bump
`SCORING_RUBRIC_VERSION`, re-collect, do not mix versions"; promoting this
to a real `scoring_rubric_version` DB column is the documented future step
(`docs/ML_NOTES.md` §4) and was deliberately not done this milestone (no
schema change).

### 12.3 Builder (`dataset/builder.py`)

`build_dataset(session_factory=SessionLocal) -> DatasetBuildResult`.

- Explicit `select(...)` naming every column — **no `SELECT *`, no
  post-hoc drop-by-name.**
- **One row per user = latest valid snapshot**: sort by
  `(collected_at, snapshot_id)` ascending, `groupby("user_id").tail(1)`.
  The `snapshot_id` tie-break keeps selection deterministic when two
  snapshots share a timestamp.
- Deterministic dataset row order: ascending `github_username`, applied
  before that column is dropped.
- Detects duplicate users (snapshots-per-user > 1); reports count +
  usernames, does not error.
- `_coerce_dtypes`: numerics via `pd.to_numeric(errors="raise")`,
  booleans → `bool`, `most_used_language` → pandas `category` over
  strings with `""` for any missing value (never null).
- Validates its own output (`validate_frame`); empty DB → empty-but-valid
  frame, not an error.
- `DatasetBuildResult`: `frame`, `raw_snapshot_count`,
  `selected_row_count`, `unique_user_count`, `duplicate_user_count`,
  `duplicate_usernames`, `.dataset_version` / `.feature_schema_version` /
  `.scoring_rubric_version`.

### 12.4 Report / export / collection input

- `dataset/report.py` — `dataset_quality_report(result) -> dict` (unique
  users, rows before/after selection, duplicates, missing values, dtypes,
  target distribution + histogram, `describe()` summary,
  `most_used_language` counts incl. `""`, constant / near-constant
  features at a 0.95 dominant-share threshold) and
  `format_report(report) -> str`. Empty-dataset-safe.
- `dataset/export.py` — `export_dataset(result_or_frame, path=None, *,
  write_meta=True) -> Path`. Deterministic CSV (fixed column + row order,
  `\n` endings, no index; two exports byte-identical). `.meta.json`
  sidecar carries the three versions + counts + `built_at_utc` (the
  timestamp makes the *meta* non-deterministic on purpose — the CSV is
  the reproducible artifact). Default path
  `data/processed/gitscore_dataset_v1.csv` (gitignored).
- `dataset/collection_input.py` — `parse_usernames(text)` /
  `load_username_file(path)`: one username per line, ignore blank + `#`
  lines, strip inline `#…`, case-insensitive dedup (first spelling wins),
  order-preserving. `UsernameFileError` on a missing file. Used by the
  refactored `scripts/collect_dataset.py`
  (`data/collection/usernames.txt`, gitignored; template committed as
  `usernames.example.txt`).

## 13. Repository ranking (`src/gitscore/ranking/`) — Milestone 5B

**Still not wired into `pipeline/analyze.py` (V1) or any collection
script** — that remains intentional; V1's `analyze_user()` is completely
unchanged and still fetches languages/README for every repository.
Milestone 5D DID wire this module into a new, separate V2 path
(`pipeline/evidence.py`, §15) — this section otherwise describes the
same standalone ranking module Milestone 5B shipped, validated via
`scripts/rank_user_repos.py` and its own test suite.

**Purpose:** decide which of a candidate's repositories are worth a
deep per-repository fetch, *before* any such fetch happens — Stage 1
(+ optional Stage 2) of the two-stage ranking strategy from the
Milestone 5A design (Part 11). It is job-independent, not ML-specific,
and is not a candidate or job-fit score of any kind — it only decides
what to look at next.

- `github/parser.py::parse_repo_summary(repo)` — extracts ranking
  fields (`archived`, `size_kb`, `pushed_at`, `topics`, plus the fields
  `parse_repo()` already captures) from the raw repo-list payload
  `GitHubClient.get_repositories()` already returns. Zero additional
  API requests; `parse_repo()` itself (which needs already-fetched
  languages + README) is unchanged.
- `ranking/config.py` — `RankingWeights` (frozen dataclass, every
  weight/threshold centralized), `DEFAULT_TOP_N = 15`,
  `REPOSITORY_RANKING_VERSION = 1`. Independent of
  `SCORING_RUBRIC_VERSION`/`DATASET_VERSION` (`dataset/schema.py`).
- `ranking/rank.py`:
  - `score_repository(summary, weights=None, relevance_terms=None, reference_time=None) -> RepositoryRankingResult`
    — Stage-1 base score (size/recency/language/description/stars
    components, log-scaled where popularity/size could otherwise
    dominate) times fork/archived/trivial-size multiplicative
    dampeners, times an optional Stage-2 relevance-boost multiplier.
    `RepositoryRankingResult` carries the full `components`/
    `multipliers` breakdown, not just the final score, specifically so
    a ranking can be explained after the fact.
  - `rank_repositories(summaries, top_n=15, weights=None, relevance_terms=None, reference_time=None) -> list[RepositoryRankingResult]`
    — sorts (score desc, then `pushed_at` desc, then name asc — the
    deterministic tie-break) and truncates to `top_n`. Fewer than
    `top_n` repositories → all returned, never padded.
- Fork/archived repositories are dampened, not excluded — they may
  still hold real evidence, per the design doc's provenance philosophy.
  Stars are capped at a fifth of the total weight mass and log-scaled
  so a single viral repository cannot dominate the ranking.
- The optional Stage-2 `relevance_terms` parameter is a plain list of
  caller-supplied strings for testing the two-stage interface — it is
  explicitly **not** the future Job Requirement Parser and contains no
  NLP; matching reuses `features/ml.py`'s word-boundary regex approach.

See `docs/CHANGELOG_DEV.md`'s Milestone 5B entry for the full formula,
the N=10/15/20 validation against real pilot accounts, and known
limitations (`size_kb` can't distinguish authored code from vendored
bulk; the relevance boost can't rescue a repository Stage 1 scores as
trivial; the organization-owned-work blind spot persists at the ranking
stage too).

## 14. Generalized evidence domain model (`src/gitscore/concepts/`, `src/gitscore/evidence/`) — Milestone 5C

**As of Milestone 5D, this domain model IS wired to real extraction** —
see §15. This section otherwise still describes the model exactly as
Milestone 5C shipped it (nothing about `Evidence`, `TechnicalConcept`,
`CandidateConceptSummary`, or `CandidateEvidenceProfile`'s core shape
changed in Milestone 5D beyond the additive `partially_analyzed` field
noted in §15.3): validated originally by its own test suite plus a
demonstration bridge (`evidence/v1_bridge.py`, still present,
still demonstration-only) — nothing in the existing V1 pipeline
(`features/*`, `scoring/readiness.py`, `pipeline/analyze.py`) is
imported, changed, or replaced by either 5C or 5D. No SQLAlchemy import
exists anywhere in either package — persistence remains deliberately
deferred (Milestone 5C Part 9; still not revisited in 5D).

**Where this sits in the pipeline, updated for Milestone 5D** (every
stage below now exists and is connected; see §15 for the full detail):

```
Repository Ranking (Milestone 5B, src/gitscore/ranking/)
        |  (selects top-N repositories -- see ARCHITECTURE.md §13)
        v
selected repositories                     <-- CONNECTED in Milestone 5D (§15)
        |
        v
Evidence Extraction (Milestone 5D, src/gitscore/evidence/extraction/)
        |  (languages, README, requirements.txt/pyproject.toml/package.json,
        |   Docker -- see §15.2; source imports/tests/CI remain post-MVP)
        v
Evidence objects (src/gitscore/evidence/models.py)   <-- Milestone 5C
        |
        v
Candidate Evidence Profile (src/gitscore/evidence/profile.py)   <-- Milestone 5C
        |
        v
(future) Job Requirement Profile + Deterministic Matcher -> Job Match Result   <-- NOT YET IMPLEMENTED
```

**Two things this section must state explicitly, per the Milestone 5C
instructions:**

- **Evidence Profile != Job Match.** `CandidateEvidenceProfile` has no
  field for a target job, a match score, required/preferred skills, or
  alternative roles (enforced by a test —
  `tests/test_candidate_evidence_profile.py::test_profile_has_no_job_related_fields`).
  It answers "what technical evidence exists," never "is this a good
  fit for X." Producing a job-conditional result is future work
  (Milestone 6A+/7A+) that *consumes* this profile; it does not live
  inside it.
- **Evidence confidence != candidate proficiency.** `ConfidenceLevel`
  (`WEAK`/`MODERATE`/`STRONG`) describes how sure GitScore is about the
  *observation itself* — e.g. "how confident are we that this
  `requirements.txt` line really declares PyTorch as a dependency" — not
  how skilled the candidate is with PyTorch, how much they used it, or
  whether they'd pass an interview on it. A `STRONG`-confidence
  observation of a dependency says nothing about depth of use.

### 14.1 Provenance philosophy

Every `Evidence` record answers, unconditionally: which repository,
which file (if applicable), what type of observation, what the raw text
actually said, which concept it was normalized to, how confident that
specific claim is, and which extractor/version produced it. This is
deliberate, not incidental — it is what makes every later number
GitScore ever produces (a future job-match score, a "strongest
supporting repositories" list, a recruiter-facing explanation)
traceable back to a specific, inspectable fact rather than an opaque
aggregate. `docs/design/MILESTONE_5A_JOB_MATCHING_DESIGN.md` Part 7 is
the fuller architectural rationale; this milestone is the first concrete
implementation of that model.

**Evidence is the source of truth; nothing else is.**
`CandidateConceptSummary` (`evidence/summary.py`) and
`CandidateEvidenceProfile` (`evidence/profile.py`) are always *derived*
from a pool of `Evidence` by a module-level function
(`summarize_concept`, `build_concept_summaries`,
`build_candidate_evidence_profile`) — there is no code path that
constructs or mutates either independently of the `Evidence` it should
reflect. `CandidateEvidenceProfile.concept_summaries` is exposed as a
`types.MappingProxyType` specifically so this can't be violated by
accident from outside the package either.

- `src/gitscore/concepts/` — `TechnicalConcept` (`models.py`), a small
  representative registry + `ConceptRegistry` + `resolve_concept()`
  (`registry.py`), and pure case/punctuation normalization
  (`normalize.py`). `CONCEPT_REGISTRY_VERSION = 1`. An unmatched term
  resolves to a deterministic `"unresolved:<term>"` pseudo-id — never
  silently dropped, and never written into the registry itself.
- `src/gitscore/evidence/` — `RepositoryIdentity` + `Evidence`
  (`models.py`, both frozen and hashable — a pool of `Evidence` can be
  deduplicated with a plain `set()`), `EvidenceType` + `ConfidenceLevel`
  (`types.py`, `EVIDENCE_SCHEMA_VERSION = 1`), `CandidateConceptSummary`
  (`summary.py`), `RepositoryAnalysisCoverage` + `CandidateEvidenceProfile`
  (`profile.py`), and `v1_bridge.py` (demonstration-only — see below).

### 14.2 Discovered vs. analyzed repositories

`RepositoryAnalysisCoverage` (`evidence/profile.py`) carries both
`discovered` (every repository GitHub listed) and `analyzed` (the subset
actually looked at deeply — e.g. Milestone 5B's ranked top-N, once
wired in) as separate tuples, with `discovered_count`, `analyzed_count`,
and `is_complete` derived from them. This exists specifically so a
future explanation layer can state "GitScore discovered 1,140
repositories but deeply analyzed 15" as a queryable fact on the profile
itself, supporting the `INSUFFICIENT_ANALYSIS` semantics described in
`docs/design/MILESTONE_5A_JOB_MATCHING_DESIGN.md` Part 16 — not yet
implemented, but now representable.

### 14.3 V1 compatibility, not V1 migration

`evidence/v1_bridge.py` demonstrates (via
`tests/test_v1_evidence_bridge.py`) that information the *existing* V1
pipeline already produces — a repository's primary language
(`parse_repo()`), README text (`parse_repo()`), and topics
(`parse_repo_summary()`, Milestone 5B) — can be represented as `Evidence`
under the new model. It is not imported by `pipeline/analyze.py` or any
script; `features/ml.py`, `features/readme.py`, `features/languages.py`,
and `scoring/readiness.py` are unchanged and continue to run exactly as
before. This proves the new model *can* eventually subsume V1's
signals — it does not do so yet.

See `docs/CHANGELOG_DEV.md`'s Milestone 5C entry for the full domain
model, the confidence-model rationale, the duplicate-evidence policy,
and open design questions.

## 15. Bounded technical evidence extraction (`src/gitscore/evidence/extraction/`, `src/gitscore/pipeline/evidence.py`) — Milestone 5D

The first real V2 pipeline: connects Milestone 5B's ranking to Milestone
5C's domain model with an actual per-repository extraction step, and
produces `Evidence` from real GitHub data for the first time.

```
GitHub username
  -> GitHubClient.get_repositories()        listing, paginated (unchanged, 5B)
  -> parse_repo_summary()                    per-repo, zero extra calls (5B)
  -> rank_repositories()                      job-independent ranking, top N (5B)
  -> top N selected repositories
  -> per selected repository:
       get_repository_languages()            1 call
       get_repository_readme_with_path()      1 call
       get_repository_root_contents()         1 call -- bounded root listing
       get_repository_file() x (files present among the 8 supported names)
  -> extractors -> Evidence[]                (5D, this milestone)
  -> build_candidate_evidence_profile()       CandidateEvidenceProfile (5C)
```

Entry point: `gitscore.pipeline.evidence.extract_candidate_evidence(username,
client=None, top_n=DEFAULT_TOP_N, collected_at=None) -> EvidenceExtractionResult`.
This is a **new, separate path** — `pipeline/analyze.py::analyze_user()`
(V1) is byte-for-byte unchanged, still fetches languages/README for
*every* repository, still produces the historical readiness score, still
writes to Dataset V1. Nothing in `evidence/extraction/` or
`pipeline/evidence.py` is imported by V1, and neither imports anything
from `features/*` or `scoring/readiness.py`.

### 15.1 Repository selection

Exactly Milestone 5B's `rank_repositories(summaries, top_n=DEFAULT_TOP_N)`
(`DEFAULT_TOP_N = 15`, unchanged) — no new selection logic. `discovered`
is every repository `get_repositories()` returned; `analyzed` is the
ranked top N (all of them if the candidate has ≤ N). A repository ranked
outside the selection is `discovered` but never `analyzed` — this is
never manually overridden (see §15.6's failure-semantics table and the
real-account validation in §15.11: `Jango1324/Pneumonia-Detection-Ai`
stayed outside the top 15 in live validation, exactly as 5B's own
validation already found, and is reported truthfully as
discovered-not-analyzed rather than forced in).

### 15.2 Extractors (`src/gitscore/evidence/extraction/`)

| Module | Produces | Extractor version |
|---|---|---|
| `languages.py` | `REPOSITORY_LANGUAGE` evidence from `get_repository_languages()` | `language:v1` |
| `readme.py` | `README` evidence: registry-alias mentions in README text, restricted to each concept's `readme_safe_aliases()` (§15.6) | `readme:v2` |
| `python_deps.py` | `DEPENDENCY` declarations from `requirements.txt` / `pyproject.toml` | `requirements:v1` / `pyproject:v1` |
| `js_deps.py` | `DEPENDENCY` declarations from `package.json` (`dependencies` + `devDependencies`) | `npm:v1` |
| `dependency_evidence.py` | shared declaration -> Evidence resolution (used by both dep modules) | (uses the caller's version) |
| `docker.py` | `DOCKER` evidence: presence of Dockerfile/compose files | `docker:v1` |
| `files.py` | root-file discovery (pure filter over one Contents-API listing) | n/a (no Evidence) |

**Not implemented** (explicitly out of scope, per the milestone's
prompt): source-import scanning, test-directory evidence, CI-workflow
evidence, notebook content analysis, Terraform/IaC, Maven/Gradle, Cargo,
Go modules, CMake/Makefile analysis, HDL source analysis, commit-history/
contribution attribution, job-description parsing or matching of any
kind. `Pipfile`/`environment.yml` (Part 7's "optional if trivial") were
evaluated and **not** added — `requirements.txt`/`pyproject.toml`/
`package.json` already covered every dependency signal actually observed
across all four real-account validations (§15.11); adding two more manifest
parsers for zero observed real-world benefit was judged not worth the
scope.

### 15.3 Evidence-schema change (`EVIDENCE_SCHEMA_VERSION` 1 -> 2)

`RepositoryAnalysisCoverage` (`evidence/profile.py`) gained one additive
field: `partially_analyzed: tuple[RepositoryIdentity, ...] = ()` — the
subset of `analyzed` where at least one evidence source for that
repository could not be inspected (§15.6). It is a genuine SHAPE change
(new field), which is exactly `EVIDENCE_SCHEMA_VERSION`'s documented bump
condition (`evidence/types.py`) — bumped to `2`. It is NOT a new coverage
tier: every `partially_analyzed` repository is still counted in
`analyzed`/`analyzed_count`/`is_complete` exactly as before this field
existed. `build_candidate_evidence_profile()` gained one new optional
keyword, `partially_analyzed=()`, defaulting to the pre-5D behavior.
`CONCEPT_REGISTRY_VERSION` was independently bumped 1 -> 2 for the new
concepts added in §15.5/§15.7 (registry content change, per its own
documented bump condition — unrelated to the schema-shape bump above).
`SCORING_RUBRIC_VERSION`, `DATASET_VERSION`, and
`REPOSITORY_RANKING_VERSION` are untouched.

### 15.4 API cost model (real numbers, from §15.11's live validation)

Per selected repository, deep analysis costs a **base of 3 requests**
(languages + README + one root-listing call) **plus one more request per
supported manifest/Docker file actually present** at that repository's
root — never more than 3 + 8 = 11, and in practice far fewer (0-2 extra
per repo was typical across all four validated accounts). Root discovery
is the key bound here (Part 3): ONE `GET /repos/{o}/{r}/contents` call
learns which of the 8 supported filenames exist, instead of guessing at
every filename individually (which would cost up to 8 requests/repo just
to *check* for files, most of which don't exist).

Total cost = `ceil(total_repos / 100)` (listing pagination) + `analyzed_count
× (3 + avg_files_present)`. Since `analyzed_count` is capped at
`DEFAULT_TOP_N = 15`, **deep-analysis cost is O(N), not O(total repos)** —
confirmed directly, not just estimated:

| Candidate (real account) | Repos discovered | Repos analyzed | Actual API requests |
|---|---|---|---|
| `torvalds` | 12 | 12 (≤ N) | 38 |
| `karpathy` | 63 | 15 | 54 |
| `Jango1324` | 20 | 15 | 53 |
| `sindresorhus` | 1,141 | 15 | 70 |

Approximate model for the three sizes the milestone asks about, `top_n =
15`, assuming a typical 0-2 extra manifest/Docker requests per selected
repo (matching the observed range above):

| Total repos | Listing requests | Deep-analysis requests (N=15, bounded) | Approx. total |
|---|---|---|---|
| 20 | 1 | ~45-60 | ~46-61 |
| 100 | 1 | ~45-60 | ~46-61 |
| 1,000 | 10 | ~45-60 | ~55-70 |

The listing cost grows with total repository count (unavoidable — GitHub
must enumerate every repository at least once to know what exists); the
deep-analysis cost does **not** — it is flat, bounded by N, regardless of
whether the candidate has 20 repos or 1,141. This is not an exaggerated
claim: `sindresorhus` (1,141 repos) cost 70 total requests end-to-end, in
the same ballpark as `Jango1324` (20 repos, 53 requests) and `karpathy`
(63 repos, 54 requests) — the bulk of the difference between them is
pagination, a handful of requests, not a multiplier on deep analysis.

### 15.5 Language significance policy (`extraction/languages.py`)

A language must be **≥ 5.0%** of a repository's language bytes
(`MIN_SIGNIFICANT_PERCENTAGE`) to produce evidence at all — percentage-
based, not a raw byte floor, because GitHub's language-stats endpoint
already normalizes for repository size (a 5% language in a 50 MB repo and
a 5% language in a 50 KB repo are equally "a real part of this repo" in a
way a fixed byte count can't express across repo sizes). A language at
**≥ 40.0%** (`MODERATE_CONFIDENCE_PERCENTAGE`) gets `MODERATE` confidence
instead of `WEAK` — confident enough to be the repo's dominant (or
co-dominant) language, vs. present-but-secondary. Both are module-level
constants, trivially tunable. An unrecognized-but-meaningful language
(e.g. `OpenSCAD`, `CMake`, `Makefile`, `Swift`, `Astro`, `QML`, `XSLT`,
`PostScript` — all observed live in §15.11's validation) still produces
Evidence with an `unresolved:<language>` id, mirroring
`evidence/v1_bridge.py`'s existing `primary_language` handling — never
silently dropped.

### 15.6 README matching policy (`extraction/readme.py`)

Deterministic, alias-aware, case-insensitive, word-boundary matching
(`(?<![A-Za-z0-9])alias(?![A-Za-z0-9])`, `re.IGNORECASE`) — no fuzzy
inference, no LLM, no arbitrary substring matching. One Evidence item per
matched **concept** per repository (never per alias, never per
occurrence), carrying one bounded ~120-character snippet from the first
occurrence — never the whole README duplicated once per concept.
Confidence is `MODERATE` (a mention declares presence/intent, not a
buildable dependency). Only the resolved path is exercised — an
unmatched mention produces no evidence (mirrors `v1_bridge.py`'s
topics-skip precedent: free-form prose has no single scalar value to
hang an "unresolved" placeholder off of the way a repo's one
`primary_language` does).

**Milestone 5D.1 — source-aware alias safety.** Unlike every other
source, this extractor does NOT match against a concept's full
`aliases` (that's what `resolve_concept()` uses for structured sources —
dependency manifests, language stats). It matches only
`concept.readme_safe_aliases()` — `aliases` minus whatever the concept
marks `readme_unsafe_aliases` in `concepts/registry.py` (data on the
concept, no per-alias `if` in this module). This exists because
Milestone 5D's initial live validation found that some aliases are
completely safe as a package name or a GitHub language-stats value but
are short and/or ordinary English words that collide constantly with
free-form prose:
- **Bare `"go"`** (alias of `language.go`) matched ordinary English
  ("I **go** for large components", "let it **go**") on
  `torvalds/1590A` and `karpathy/autoresearch`. Now `readme_unsafe`:
  bare "Go" mentions produce **no** README evidence (an intentional,
  documented precision-over-recall choice — there is no context-free
  way to tell the language apart from the verb without exactly the
  fuzzy/NLP inference this milestone avoids). `"golang"` remains
  README-safe and unambiguous ("Written in Golang" still matches); "go"
  itself is untouched as a `resolve_concept()` alias, so GitHub's
  language-stats name `"Go"` still resolves via `languages.py`.
- **Bare `"next"`** (alias of `framework.nextjs`) matched ordinary
  English ("**Next** Track", "**next** steps") on
  `Jango1324/Arduino-Based-Media-Player`. Now `readme_unsafe`: bare
  "next" produces no README evidence, but `"next.js"`/`"nextjs"` remain
  README-safe (`"Uses Next.js"` still matches), and `"next"` is
  untouched as a `resolve_concept()` alias — `package.json`'s literal
  `"next"` dependency key still resolves to `framework.nextjs` exactly
  as before (§15.7).
- **`"js"`/`"ts"`** (aliases of `language.javascript`/`language.typescript`)
  are also `readme_unsafe`: the boundary regex treats `.` as a valid
  separator, so a bare `"js"` alias gave every `".js"`-suffixed name
  (Next.js, Vue.js, Node.js, ...) incidental JavaScript evidence — a
  mention of "Next.js" alone no longer implies "JavaScript" unless the
  README independently says so. The full words `"javascript"`/
  `"typescript"` remain README-safe.
- **Bare `"c"`** (`language.c`'s only alias) is also `readme_unsafe` — a
  single letter has no safe deterministic form in prose at all, so
  `language.c` now produces **zero** README evidence
  (`readme_safe_aliases()` is empty for it); language-stats extraction
  remains the practical source of C evidence.
- Pinned by dedicated tests in `tests/test_evidence_extraction_readme.py`
  (the `test_bare_*_no_longer_matches_*` / `test_*_still_matches_*`
  pairs) and by `tests/test_technical_concepts.py`'s
  `readme_safe_aliases()` / `resolve_concept()` regression tests.
- Other short-and-also-an-English-word aliases already in the registry
  (e.g. `react`, `flask`, `express`) were **not** evaluated this round —
  out of this cleanup's scope, which was bounded to the aliases live
  validation actually flagged plus the explicitly-named `js`/`ts`/`c`
  short-alias class. A future pass can mark more `readme_unsafe_aliases`
  entries the same data-driven way if real validation surfaces them.

### 15.7 Dependency mapping (`extraction/dependency_evidence.py`)

**No second "package name -> concept" table.** Package/dependency names
resolve through the exact same `concepts.registry` aliases every other
evidence source uses (`resolve_concept(package_name)`) — `torch`,
`psycopg2-binary`, `next`, etc. are registered there once. Adding a
mapping is one alias on one `TechnicalConcept` entry in
`concepts/registry.py`, not a change to any extraction algorithm.

**Unknown dependencies are deliberately NOT turned into `unresolved:`
Evidence** (unlike languages, §15.5) — they are tracked as a plain list
of names on `EvidenceExtractionResult.unknown_dependency_names` (a
pipeline-level diagnostic, not part of `CandidateEvidenceProfile`) and
otherwise dropped. A dependency manifest can list dozens to hundreds of
packages (`sindresorhus`'s `package.json` alone produced 185 unknown
names in live validation — mostly `@scope/package`-style tooling and
transitive-looking names); turning every one into an Evidence row would
flood the evidence pool with noise, not signal — exactly what the
milestone's "do not pretend every dependency is a useful technical
concept" instruction warns against. This mirrors `v1_bridge.py`'s
existing topics-skip precedent, not its primary_language-always-evidence
precedent.

Same-package-in-both-sections policy (`package.json`): `dependencies` is
canonical; a package listed in both `dependencies` and `devDependencies`
produces exactly one declaration, from `dependencies`.

### 15.8 Docker semantics (`extraction/docker.py`)

Presence-only, from the same one root-listing call §15.1 already makes —
no Dockerfile/compose CONTENT is ever read or judged. A `Dockerfile` or
compose file at the repository root is `STRONG` confidence that Docker/
containerization is used, and nothing more (confidence-vs-proficiency,
§14). Multiple present Docker-related files (e.g. both `Dockerfile` and
`docker-compose.yml`) produce separate Evidence items (different
`file_path`s, so not exact duplicates) — a repository "has Docker AND has
a compose setup" is two distinct, separately-provenanced facts, not
merged into one.

### 15.9 Confidence assignments

| Source | `evidence_type` | Confidence |
|---|---|---|
| Repository language, < 40% of bytes | `REPOSITORY_LANGUAGE` | `WEAK` |
| Repository language, ≥ 40% of bytes | `REPOSITORY_LANGUAGE` | `MODERATE` |
| README concept mention | `README` | `MODERATE` |
| Dependency-manifest declaration | `DEPENDENCY` | `STRONG` |
| Docker/compose file presence | `DOCKER` | `STRONG` |

The existing 3-level `WEAK`/`MODERATE`/`STRONG` ordinal scale
(Milestone 5C) proved sufficient for every real extractor built this
milestone — no case was found where two genuinely different
confidence levels needed to be collapsed into the same tier. Not
changed.

### 15.10 Failure semantics (`pipeline/evidence.py`)

Every network call in `_analyze_repository()` is isolated in its own
try/except; one failing source degrades only that source, never aborts
the rest of that repository's analysis or any other selected repository:

| Situation | Outcome |
|---|---|
| README / manifest genuinely absent (404) | Expected absence — no Evidence, NOT recorded as a failure (`get_repository_readme_with_path()` already translates 404 -> `None`; an absent manifest simply never appears in `discover_supported_root_files()`'s result) |
| Language-stats fetch fails (timeout, 5xx, ...) | Recorded as an `ExtractionFailure` (`source="languages"`); repo added to `partially_analyzed`; other sources for that repo still attempted |
| README fetch fails (non-404) | Recorded as an `ExtractionFailure` (`source="readme"`) |
| Root-listing fetch fails | Recorded (`source="root_contents"`); manifest/Docker detection skipped for that repo (nothing to discover files from) — languages/README for that repo are unaffected |
| A present manifest file fails to fetch | Recorded (`source=<filename>`) |
| A present manifest file is malformed (bad TOML/JSON) | Recorded (`source=<filename>`, error text from `tomllib.TOMLDecodeError` / `json.JSONDecodeError`) — that ONE file's evidence is skipped, everything else continues |
| `GitHubRateLimitError`, anywhere | Propagates immediately and aborts the WHOLE run (mirrors V1's existing batch-abort policy, `pipeline/analyze.py` §8) — never caught, never degraded into a partial result |

`RepositoryAnalysisCoverage.partially_analyzed` (§15.3) is the queryable,
per-repository summary of this table's failure rows.
`EvidenceExtractionResult.extractor_failures` carries the full detail
(`repository`, `source`, `error` message) for reporting.

### 15.11 Real-account validation

Run via `scripts/inspect_evidence_profile.py <username>` (inspection
only — no persistence, no score of any kind) against four accounts
chosen for diversity, using ONLY the new V2 pipeline:

**Milestone 5D.1 correction:** this table previously swapped the
"Requests" and "Evidence items" columns for `karpathy` and
`sindresorhus` (worked around at the time with a footnote instead of
being fixed). It also now reflects a RE-RUN of all four accounts against
the fixed README extractor (`readme:v2`) — `Evidence items` and
`Concepts detected` dropped for every account that had a bare
`go`/`next`/`js` false positive, confirming the fix; `API requests` is
unaffected (README matching doesn't change what's fetched, only what's
extracted from it) and still matches §15.4 exactly, for every row.

| Account | Profile | Repos discovered | Repos analyzed | Actual API requests | Evidence items | Concepts detected | Extractor failures |
|---|---|---|---|---|---|---|---|
| `Jango1324` | Python/web, small account | 20 | 15 | 53 | 57 (was 62) | 16 (was 17) | 0 |
| `torvalds` | C/systems | 12 | 12 | 38 | 31 (was 37) | 14 (was 15) | 0 |
| `karpathy` | Python/ML | 63 | 15 | 54 | 96 (was 111) | 20 (was 22) | 0 |
| `sindresorhus` | JS/TS, 1,140+ repos | 1,141 | 15 | 70 | 65 (was 84) | 16 (was 19) | 0 |

("was ..." = the Milestone 5D pre-fix number, kept for a direct
before/after comparison — not a second measurement to reconcile.)

Zero extractor failures across all four real accounts. The bare
`go`/`next`/`js` README false positives originally found here (Milestone
5D) are fixed as of Milestone 5D.1 (§15.6) — confirmed by this re-run:
`torvalds/1590A` and `karpathy/autoresearch` no longer produce
`language.go` README evidence, and `Jango1324/Arduino-Based-Media-Player`
no longer produces `framework.nextjs` README evidence from "Next Track";
`framework.nextjs` is still correctly detected for `Jango1324` overall,
from its actual `package.json` dependency (STRONG confidence, unaffected
by the README-only restriction). No obvious false NEGATIVE was found
in manual review of the provenance output (every dependency/language/
Docker signal actually present in a selected repository's root was
detected) — the only "missing" evidence is entirely explained by the
top-N selection boundary (§15.1), which is honestly represented via
`discovered`-not-`analyzed`, never silently absent.

**`Jango1324/Pneumonia-Detection-Ai`** (Part 15's named edge case):
confirmed still outside the top 15 in this milestone's live run —
`discovered=yes, analyzed=no`. Not manually forced in; no ranking-weight
or job-aware special-casing was added for it, per the milestone's
explicit instruction. It appears in `inspect_evidence_profile.py`'s
"discovered but NOT analyzed" section for `Jango1324` like any other
excluded repository.

### 15.12 Known limitations

- README matching's short-alias false positives (bare `go`/`next`/`js`/
  `ts`/`c`) are fixed as of Milestone 5D.1 by excluding those specific
  aliases from prose matching (§15.6) — but the underlying limitation is
  structural, not patched away: bare "Go" (and bare "C") genuinely cannot
  be told apart from ordinary English by literal, context-free keyword
  matching, so this milestone chooses to detect them via no README
  signal at all rather than guess, relying on language-stats/dependency
  evidence instead. Not fixable within "no fuzzy inference, no LLM"
  scope; any *other* short-and-also-an-English-word alias not yet
  evaluated (§15.6's `react`/`flask`/`express` note) could still produce
  the same class of false positive until reviewed the same way.
- The concept registry remains small and representative (now ~35
  concepts across languages, ML/data, web frameworks, ORMs,
  infrastructure) — most real-world dependency names resolve to
  `unknown_dependency_names`, by design (§15.7), not registry
  incompleteness alone.
- `Pipfile`/`environment.yml`, source imports, test-directory evidence,
  CI-workflow evidence, and notebook content analysis remain unimplemented
  (§15.2) — explicitly post-MVP per the Milestone 5A design doc Part 12.
  A meaningful language like `Jupyter Notebook` IS still detected (via
  `languages.py`, from GitHub's own language stats), just not the
  notebooks' cell *content*.
- `EvidenceExtractionResult`'s diagnostics (`extractor_failures`,
  `unknown_dependency_names`) are pipeline-level, not persisted anywhere
  and not part of `CandidateEvidenceProfile` — a future milestone that
  wants to persist or report on them across runs needs its own decision
  about where that data lives.

See `docs/CHANGELOG_DEV.md`'s Milestone 5D entry for the full narrative,
and `scripts/inspect_evidence_profile.py` to reproduce §15.11's numbers
against any public GitHub account.

## 16. Context-safe concept resolution (Milestone 5D.1)

Milestone 5D's initial real-world validation (§15.11) found that some
`concepts.registry` aliases are safe for the STRUCTURED sources they were
added for (a `package.json` dependency key, a GitHub language-stats name)
but produce false-positive evidence when the exact same alias list is
matched against FREE-FORM README prose — a fundamentally more ambiguous
context. Full detail is inline at §15.6 (the fix, per-alias) and §15.11
(the before/after re-run numbers); this section is the short version.

**Root cause:** one flat `aliases` tuple per `TechnicalConcept`, matched
identically by every source (`resolve_concept()` for structured sources,
`readme.py`'s own loop over `concept.aliases` for prose) — there was no
way for a concept to say "this alias is fine for a package name, not for
a sentence."

**Fix (`concepts/models.py`):** `TechnicalConcept` gained one new field,
`readme_unsafe_aliases: frozenset[str]` (validated in `__post_init__` to
be a subset of `aliases`), and one new method, `readme_safe_aliases()`
(`aliases` minus `readme_unsafe_aliases`). `resolve_concept()` and every
structured-source caller (`dependency_evidence.py`, `languages.py`) are
completely unchanged — they still resolve against the full `aliases`.
Only `evidence/extraction/readme.py` was changed, to iterate
`concept.readme_safe_aliases()` instead of `concept.aliases`. This is
the "source-aware alias metadata" design, not a second parallel
dependency-alias table (a `DEPENDENCY_CONCEPT_ALIASES`-style mapping was
considered and rejected — `resolve_concept()` already does exactly the
right thing for structured sources; the only source that needed
restricting was README prose).

**Data changed (`concepts/registry.py`, `CONCEPT_REGISTRY_VERSION` 2 ->
3):** `readme_unsafe_aliases={"go"}` / `{"next"}` / `{"js"}` / `{"ts"}` /
`{"c"}` on `language.go` / `framework.nextjs` / `language.javascript` /
`language.typescript` / `language.c` respectively. No concept added,
renamed, or removed; `normalize_term()` unchanged.

**Extractor version bumped (`readme:v1` -> `readme:v2`,
`evidence/extraction/readme.py`):** behavior changed (which mentions
produce evidence), so the version string changed — every other
extractor's behavior is unchanged, so no other extractor version moved.

**Not bumped, and why:** `EVIDENCE_SCHEMA_VERSION` stays `2` — no field
was added/removed/retyped on `Evidence`, `CandidateConceptSummary`,
`CandidateEvidenceProfile`, or `RepositoryAnalysisCoverage` (see
`evidence/types.py`'s own bump policy: it tracks SHAPE, not extractor
behavior). `SCORING_RUBRIC_VERSION`, `DATASET_VERSION`, and
`REPOSITORY_RANKING_VERSION` are untouched, per instruction — nothing in
this cleanup touches scoring, the dataset schema, or repository ranking.

**Result, confirmed by re-running §15.11's same four accounts against
the fixed extractor** (see that section's corrected table): `torvalds`
and `karpathy` no longer produce `language.go` README evidence from
ordinary English ("I go for...", "let it go"); `Jango1324` no longer
produces `framework.nextjs` README evidence from "Next Track", while its
real `package.json` `"next"` dependency still correctly resolves to
`framework.nextjs` at `STRONG` confidence, unaffected. Zero regressions
in structured extraction (dependency mapping, language-statistics
resolution) — covered by dedicated regression tests in
`tests/test_evidence_extraction_dependency_mapping.py` and
`tests/test_evidence_extraction_languages.py`.

**Known remaining limitation, unchanged from §15.6/§15.12:** bare "Go"
in a README (e.g. "Written in Go") still produces no evidence — there is
no literal, deterministic way to tell it apart from the English verb
without exactly the fuzzy/NLP inference this project avoids. This is an
intentional precision-over-recall choice, not an oversight: language-stats
extraction (`languages.py`) remains the practical, and unaffected, source
of Go evidence. Bare "C" is the same story. Other short-and-also-an-
English-word aliases already in the registry (`react`, `flask`,
`express`, ...) were out of scope for this cleanup and may need the same
treatment if a future real-account validation flags them.

## 17. Job requirement domain model (`src/gitscore/jobs/`) — Milestone 6A

**Domain model only — no parser, no matcher, no scoring exist yet.**
This section defines the job-side counterpart to §14's
`CandidateEvidenceProfile`, the second of the two structured inputs the
future deterministic matcher will compare:

```
Raw Job Description (pasted text)
        |
        v
future parser                                   <-- NOT YET IMPLEMENTED
(LLM-assisted phrase extraction + deterministic
 concept normalization, docs/design/MILESTONE_5A_JOB_MATCHING_DESIGN.md
 Parts 8/18)
        |
        v
JobRequirementProfile (src/gitscore/jobs/profile.py)      <-- THIS MILESTONE
        |
        +-- title, company                (informational only, Part 7)
        +-- raw_text                       (verbatim, preserved)
        +-- parser_version, schema_version
        +-- requirements: (JobRequirement, ...)   <-- order preserved exactly as given
                  |
                  +-- JobRequirement (src/gitscore/jobs/models.py)
                        +-- original_text                        (verbatim span)
                        +-- concept_id: str | None                (resolved concept, "unresolved:<term>", or None)
                        +-- category: str | None
                        +-- necessity: Necessity                  (REQUIRED | PREFERRED)
                        +-- importance: Importance                 (LOW | MEDIUM | HIGH, ordinal)
                        +-- github_observability: GithubObservability  (NOT_ | PARTIALLY_ | STRONGLY_OBSERVABLE)
                        +-- parser_confidence: ParserConfidence | None  (LOW | MEDIUM | HIGH, ordinal -- distinct from ConfidenceLevel)
                        +-- source_span: SourceSpan | None          ((start, end) offsets into raw_text)
```

And the eventual boundary this milestone sets up but does not cross:

```
CandidateEvidenceProfile (§14, Milestone 5C/5D)     JobRequirementProfile (this section, Milestone 6A)
                    |                                              |
                    +--------------------  future  ----------------+
                                    deterministic matcher                <-- NOT IMPLEMENTED
                                    (docs/design/MILESTONE_5A_JOB_MATCHING_DESIGN.md Part 15)
```

### 17.1 Why a generic model, not a role enum

The product must support arbitrary technical jobs, including roles never
anticipated during development (embedded, robotics, compiler engineering,
HPC, security automation, ...). Nothing in `src/gitscore/jobs/` branches
on a role name or belongs to a finite role enum: `JobRequirementProfile`
has only a free-text, informational `title`/`company` (never read by any
logic in this package), and `JobRequirement` is keyed entirely by
`concept_id` — the SAME open-ended mechanism `concepts/registry.py`
already uses for candidate-side evidence (§14). Adding support for a
previously-unseen job type never requires a new class, a new field, or a
new branch — only, at most, a new concept-registry entry (already
governed by `CONCEPT_REGISTRY_VERSION`, §14/§15.7). §17.4's three manual
examples (backend, robotics, ML) are proof: all three are plain
`JobRequirementProfile` instances, differing only in which
`JobRequirement` rows and concept ids they contain.

### 17.2 JobRequirement: one indivisible claim

Mirrors `evidence.models.Evidence`'s shape (frozen, fully hashable,
plain value object, no synthetic id yet — persistence is not addressed
by this milestone either) but is NOT a re-skinned `Evidence`: a
`JobRequirement` is a claim a JOB makes; `Evidence` is an observation
about a CANDIDATE. Neither object references the other; nothing in
`src/gitscore/jobs/` imports `gitscore.evidence`, and nothing in
`gitscore.evidence` imports `gitscore.jobs`.

**The one-claim-per-object rule is the direct fix for Milestone 6A
Part 1's warning case.** "3+ years of experience building Python backend
services" must never become one `JobRequirement` with
`concept_id="language.python"` — that would silently assert
"3+ years of experience" is as GitHub-observable as "uses Python," which
it is not. A future parser must instead emit TWO `JobRequirement` rows
from that one sentence — one technical (`concept_id="language.python"`,
`github_observability=STRONGLY_OBSERVABLE`), one non-technical
(`concept_id=None`, `github_observability=NOT_OBSERVABLE`,
`category="experience"`) — both legitimately sharing the same
`original_text`/`source_span`. `tests/test_job_requirement_models.py::test_compound_sentence_splits_into_two_separate_requirement_claims`
demonstrates this split manually; no automatic splitting logic exists.

**Non-technical requirements (Part 6)** — "Bachelor's degree," "excellent
communication," "eligible to work in Canada," "3+ years of professional
experience" — are represented with `concept_id=None`, never with an
invented `TechnicalConcept` id like `skill.communication` or
`experience.three_years`. They are never discarded: `original_text` and
`category` (a free-form, uncontrolled label — deliberately not a closed
enum, for the same "don't build an ontology prematurely" reason
`TechnicalConcept.category` itself is a plain string, §14) preserve
exactly what the posting said and roughly what kind of claim it is, so a
future explanation layer can render "GitHub cannot assess this" rather
than silently dropping it.

**Update, Milestone 6B.1:** `JobRequirement` gained a fourth field,
`alternative_concept_ids: tuple[str, ...] = ()`, for a single logical
requirement satisfied by ANY ONE of several technical concepts ("Python
or Go") — mutually exclusive with `concept_id`. `JOB_REQUIREMENT_SCHEMA_VERSION`
bumped 1 -> 2 as a result. Full detail: §19.

### 17.3 Concept resolution reuses §14's registry exactly — no second table

A technical `JobRequirement.concept_id` is populated by calling the
EXISTING `gitscore.concepts.registry.resolve_concept()` — the identical
function/registry candidate-side extractors use (§15.7's dependency
mapping is the direct precedent: "no second package name -> concept
table" there; "no second job-requirement -> concept table" here). An
unanticipated technology named in a job posting (e.g. "warp-level
primitives") resolves through the SAME `"unresolved:<term>"` policy
`Evidence` already relies on (§14, Milestone 5C Part 3) — never dropped,
never silently promoted into a new canonical concept, and never written
into the registry itself. This directly answers Part 5's question ("is
the existing `unresolved:<term>` policy appropriate here" — yes) and
avoids the earlier 5A design draft's separate, never-implemented
`"provisional:<slug>"` scheme, which would have meant two different
unresolved-id conventions to keep straight across the codebase for no
benefit.

`JobRequirement` does not call `resolve_concept()` itself — exactly like
`Evidence` does not call it either. Resolution is the caller's job (a
future parser, or — for this milestone — a test); the domain object only
STORES the resulting `concept_id` string. This keeps `jobs/models.py`
free of any dependency on resolution mechanics, matching this milestone's
"domain model only" scope precisely.

**Milestone 6A.1 addendum — VALIDATING that stored string, without
resolving it.** The initial 6A implementation only checked that a
non-`None` `concept_id` was a non-empty string — `JobRequirement(...,
concept_id="whatever.random.string")` constructed cleanly and its
`is_resolved_concept` property reported `True`, silently treating an
arbitrary string as if it were a real registered concept. Fixed by
adding one new function, `concepts.registry.is_valid_concept_id(concept_id,
registry=None) -> bool` — pure validation of an ALREADY-PRODUCED id
(`registry.get(concept_id) is not None`, OR the id is exactly what
`unresolved_concept_id()` would re-produce for its own suffix, checked by
calling that same function again rather than re-implementing its
normalization rules) — reusing `is_unresolved_concept_id()`/
`unresolved_concept_id()` verbatim rather than inventing a second
unresolved-id grammar. `is_valid_concept_id("Postgres")` is `False` even
though `resolve_concept("Postgres")` succeeds: the two answer different
questions ("is this already a valid id" vs. "what does this raw term
mean"), and only the former belongs in a `__post_init__` validation
check. `JobRequirement.__post_init__` now calls this helper instead of
the old bare non-empty-string check; the dependency direction is
unchanged (`gitscore.jobs` -> `gitscore.concepts`, never the reverse, no
circular import, no registry mutation, no fuzzy matching). Does not
change `JOB_REQUIREMENT_SCHEMA_VERSION` (no field added/removed/retyped)
or `CONCEPT_REGISTRY_VERSION` (no concept/alias/normalization change —
a new pure helper function, not a registry content change). See
`docs/CHANGELOG_DEV.md`'s Milestone 6A.1 entry for the full writeup.

### 17.4 Necessity, importance, and GitHub observability are three
independent axes

Deliberately three separate fields, not one combined "requirement type"
(contrast the 5A draft's single four-state `requirement_type` — narrowed
here per this milestone's explicit "do not invent excessive granularity"
instruction):

- **`Necessity`** (`REQUIRED` | `PREFERRED`, a plain `str` enum, no
  ordering) — does the posting say this is mandatory or a plus.
- **`Importance`** (`LOW` < `MEDIUM` < `HIGH`, ordinal `IntEnum`,
  mirroring `ConfidenceLevel`'s "ordinal, not a float" reasoning — no
  fake-precision numeric weight is justified by anything the 5A draft
  actually calibrated) — how much THIS ONE requirement matters,
  independent of necessity. A job can require both Git (`LOW`
  importance) and Python (`HIGH` importance) — both `REQUIRED`, but not
  equally emphasized; collapsing the two axes into one field would lose
  exactly this distinction.
- **`GithubObservability`** (`NOT_OBSERVABLE` < `PARTIALLY_OBSERVABLE` <
  `STRONGLY_OBSERVABLE`, ordinal `IntEnum`) — can a GitHub account
  plausibly demonstrate this KIND of claim at all, regardless of whether
  this specific candidate happens to. This is the field that keeps
  GitScore from ever implying "GitHub can verify everything in a job
  description" (Milestone 6A Part 4, verbatim) — "5 years of professional
  experience" can be exactly as `REQUIRED` and `HIGH`-importance as
  "Python," yet the two must never be scored as if GitHub could speak to
  both equally; that distinction lives here, in a field orthogonal to
  necessity/importance, never folded into either.

All three are ordinal-or-plain enums, never floats — consistent with
`ConfidenceLevel`'s own precedent (§14) and this milestone's explicit
instruction not to introduce fake-precision weights without strong
justification.

### 17.5 Parser confidence is a distinct type from evidence confidence

`ParserConfidence` (`LOW` | `MEDIUM` | `HIGH`, ordinal `IntEnum`,
optional on `JobRequirement`, defaulting to `None`) answers "how sure a
future parser was that it read this job-description text correctly" —
e.g. whether "experience with cloud platforms such as AWS or Azure"
names AWS/Azure as independent requirements, interchangeable
alternatives, or merely illustrative examples. This is intentionally
NOT `gitscore.evidence.types.ConfidenceLevel` reused: `ConfidenceLevel`
answers "how sure are we this CANDIDATE-SIDE observation is real" (a
claim about GitHub evidence); `ParserConfidence` answers "how sure are we
we correctly interpreted THIS JOB TEXT" (a claim about job-description
interpretation). Reusing one enum for both would make a job-parsing
uncertainty read as if it were a claim about a candidate's GitHub
activity — exactly the kind of meaning-blurring this milestone's
instructions warned against. `None` means "no parser has evaluated this
yet" (true for every `JobRequirement` in this milestone, since none are
parser-produced) — not "certain."

### 17.6 Provenance: SourceSpan

`SourceSpan` (`start: int`, `end: int`, frozen, hashable) is the smallest
representation that lets a future explanation layer say "this
requirement came from exactly this portion of the job description" —
Milestone 6A Part 8 explicitly scoped this to "manually constructed test
objects are enough... NOT implementing automatic span extraction yet."
Two-tier validation, matching where each check can actually be performed:
`SourceSpan.__post_init__` rejects a locally-nonsensical span (`start <
0`, `end <= start`) with no knowledge of any document; whether a span
falls WITHIN a particular posting's text requires knowing that posting's
length, so `JobRequirementProfile.__post_init__` is what rejects a span
extending past `len(raw_text)`.

### 17.7 JobRequirementProfile: candidate-independent by construction

Mirrors `CandidateEvidenceProfile`'s own job-independence guarantee
(§14) in the opposite direction — pinned by
`tests/test_job_requirement_profile.py::test_profile_has_no_candidate_or_match_fields`,
the direct counterpart to
`test_candidate_evidence_profile.py::test_profile_has_no_job_related_fields`.
Contains no candidate/username, no `Evidence`, no match score, no
coverage score, no strengths/gaps, no repository references, no
alternative roles — those are future-matcher concerns that CONSUME this
profile plus a `CandidateEvidenceProfile`, never fields living inside
either one.

**Two deliberate policy differences from `CandidateEvidenceProfile`,
each documented in `jobs/profile.py`'s own docstring so neither reads as
an unexplained inconsistency:**
- **Duplicate requirements are REJECTED (raise `ValueError`), not
  silently deduplicated.** `CandidateEvidenceProfile.evidence` silently
  collapses exact structural duplicates via `set()` (§14) because
  repeated identical Evidence is an expected, harmless corroboration
  artifact (the same detector re-observing the same real fact).
  `JobRequirementProfile` has no equivalent legitimate source for an
  EXACT duplicate `JobRequirement` (same text, same span, same
  everything) — a job posting's requirements are each supposed to be one
  distinct claim, so an exact duplicate is far more likely a construction
  bug, which Milestone 6A Part 11 asks domain objects to reject rather
  than silently absorb. Two requirements sharing the same text but
  appearing at different `source_span` locations are NOT duplicates and
  both survive (a genuine JD may restate the same requirement in two
  sections).
- **`requirements` preserves EXACTLY the given order, never re-sorted.**
  `CandidateEvidenceProfile.evidence` IS canonically re-sorted
  (`evidence_sort_key`, §14) because an evidence pool has no inherent
  meaningful order. A job posting's requirement order can be informative
  (earlier requirements are often more prominent) — re-sorting it would
  destroy real information, so "deterministic" here means "the same
  input order always produces the same output," not "canonically
  reordered."

No separate "only intended constructor" builder function exists here
(contrast `build_candidate_evidence_profile()`, §14) — there is no
derived/aggregate field to protect (no `concept_summaries` equivalent
yet); `__post_init__` alone is sufficient to enforce every invariant
this milestone needs.

### 17.8 Versioning

`JOB_REQUIREMENT_SCHEMA_VERSION = 1` (`jobs/types.py`), a new, fully
independent constant — introducing it does not bump
`EVIDENCE_SCHEMA_VERSION`, `CONCEPT_REGISTRY_VERSION`,
`REPOSITORY_RANKING_VERSION`, `SCORING_RUBRIC_VERSION`, or
`DATASET_VERSION`; nothing in this milestone touches candidate-evidence
extraction, the concept registry's data, repository ranking, or V1
scoring/dataset shape. Bumps when `JobRequirement` or
`JobRequirementProfile` change SHAPE (a field added/removed/retyped) —
mirroring `EVIDENCE_SCHEMA_VERSION`'s own policy exactly; adding a new
enum member to `Necessity`/`Importance`/`GithubObservability`/
`ParserConfidence` alone does NOT bump it (additive, non-breaking, same
reasoning as a new `EvidenceType` member).

### 17.9 Manual examples: one model, three unrelated jobs

`tests/test_job_requirement_manual_examples.py` hand-builds full
`JobRequirementProfile`s for a Backend Software Engineer, a Robotics
Software Engineer, and a Machine Learning Engineer — deliberately
choosing jobs with almost no requirement overlap. All three are plain
`JobRequirementProfile` instances; none required a new class, a new
field, or a role-specific branch. Notably: `language.python` appears in
all three at different `Importance` levels (proving concepts, not role
templates, drive the model); the robotics example's "Linux" resolves via
the SAME `unresolved:<term>` path as an unrecognized language-stats value
would (§14) — demonstrating that an unanticipated technology degrades
gracefully instead of being dropped or crashing, without a single new
line of resolution code.

### 17.10 What remains explicitly unimplemented

No job-description parser (regex or LLM-based), no URL/job-board
ingestion, no deterministic matcher, no match/coverage score, no
strengths/gaps output, no alternative-role discovery, no persistence.
Every `JobRequirement`/`JobRequirementProfile` produced so far is
hand-constructed by test code — turning raw job-description text into
these objects is the next milestone's work, not this one's.

**Update, Milestone 6B (§18): the job-description parser now exists.**
`gitscore.jobs.parsing.parse_job_description()` turns raw text into a
`JobRequirementProfile` using this EXACT, unchanged domain model — no
field was added to `JobRequirement`/`JobRequirementProfile`,
`JOB_REQUIREMENT_SCHEMA_VERSION` did not move. Everything else in this
section (§17.1-17.9) still describes the model exactly as it shipped in
6A/6A.1.

## 18. Job-description parser (`src/gitscore/jobs/parsing/`) — Milestone 6B / 6B.1

**Deterministic, rule-based, zero external dependencies.** Turns raw
job-description text into a `JobRequirementProfile` (§17, extended in
6B.1 by one additive field -- see §19) -- no matcher, no scoring, no
candidate/job comparison of any kind.

```
Raw Job Description
        |
        v
segment_description()                    (18.2 -- Claim: text + exact span + necessity hint)
        |
        v
per claim:
  classify_alternative_claim()  (§19)
    "technical"      --> ONE JobRequirement, alternative_concept_ids set
    "unsafe"         --> ONE conservative alternative_requirement fallback
    "not_technical"  --> normal pipeline, exactly as if no "or" were present:
        find_concept_mentions()  -> known concepts (18.3/18.4)
        find_conservative_unknown_terms()  -> unresolved:<term> (18.5)
        find_experience_qualifier()  -> non-technical "experience" claim (18.9)
        find_non_technical_match()  -> non-technical claim (18.6)
        |
        v
infer_necessity() / infer_importance() / observability_for_*() / confidence_for()   (18.6/18.7/18.8)
        |
        v
deduplicate_requirements()                (18.8, alternative-group-aware since 6B.1)
        |
        v
JobRequirementProfile(raw_text=<verbatim>, requirements=<deduplicated>, parser_version="job_description_parser:v2")
```

### 18.1 Architecture decision: A (deterministic) over B/C (LLM-assisted)

Milestone 6B's instructions explicitly required evaluating this, not
defaulting to an LLM just because the product is named GitScore AI.
Chosen: **Option A, purely deterministic/rule-based** — for exactly the
same reason the "Good" flow in the milestone brief already IS
deterministic end-to-end: identify claims -> identify technical
terms/concepts -> normalize through the EXISTING concept registry ->
preserve unresolved concepts -> construct generic `JobRequirement`
objects. Arbitrary-role support does not require language understanding
of what a role IS — it requires an OPEN concept vocabulary (already
solved: the registry + `unresolved:<term>`, §14) and conservative,
generic-vocabulary heuristics for document STRUCTURE (section headings,
bullets, sentences) and CLAIM SHAPE (necessity/experience/alternative
wording) — none of which is role-specific. No test in this milestone
needs a network call or an API key.

**Where a future LLM adapter could plug in, without changing anything
downstream:** the ONE place free-text judgment is genuinely hard for
regex is `segmentation.py`'s conservative gate for claims outside a
recognized section, and `non_technical.py`'s fixed phrase table (a
posting phrasing a non-technical requirement in a way the curated table
doesn't cover is silently missed, §18.10). An `LLMClaimExtractor`
adapter could replace `segment_description()`'s output — a list of
candidate claim TEXT spans — while every downstream step (concept
resolution, necessity/importance/observability, dedup,
`JobRequirementProfile` construction) stays byte-for-byte the same,
exactly mirroring the existing project boundary
(`docs/design/MILESTONE_5A_JOB_MATCHING_DESIGN.md` Part 18: LLM only
ever produces unnormalized candidate phrases, never writes a concept id,
a score, or Evidence directly). Not built here — no external AI
dependency was introduced without approval, per instruction.

### 18.2 Segmentation (`segmentation.py`, Part 3)

A fixed, generic table of common JD section headings (Requirements /
Qualifications / Preferred Qualifications / Nice to Have /
Responsibilities / ... and a separate SKIP table: Benefits / Perks /
About Us / Compensation / ...) — about DOCUMENT STRUCTURE, not domain
content, so it applies unchanged to a backend, robotics, or FPGA
posting. Every `Claim` carries its EXACT `(start, end)` offset into the
original description (never reconstructed) plus a `necessity_hint`
inherited from its section.

Inside a recognized requirement-like section, every bullet/sentence
becomes a claim unconditionally. Inside a SKIP section, nothing does,
until the next heading. OUTSIDE any recognized section, a claim is only
emitted if it contains a known concept mention OR a small, generic
requirement-vocabulary signal (`experience`, `degree`, `required`,
`skills`, ...) — this is what keeps "We are a fast-growing startup
revolutionizing how teams ship software" from ever becoming a
requirement, confirmed in Milestone 6B's manual validation (§18.11): the
Backend example's marketing intro and its entire `Benefits:` section
(including a "React JS meetups" line that would otherwise be a
`framework.react` false positive) produced zero claims.

**Known limitation:** a section's `necessity_hint` persists until the
NEXT recognized heading — text appearing after the last real heading in
a posting inherits whatever section was last open, which is not always
semantically appropriate (observed directly in manual validation, §18.11
false positives). Sentence splitting is a conservative
`(?<=[.!?])\s+(?=[A-Z0-9])` heuristic, not real NLU — it can under-split
one long sentence into fewer claims than a human would, never silently
corrupts an offset.

### 18.3 Known-concept extraction (`concepts.py`, Part 5)

Reuses `gitscore.concepts.registry.default_registry()` exactly — no
second, parser-specific ontology, adding a job-description-recognizable
technology is still exactly one `TechnicalConcept` registry entry
(§14/§15.7's "no second table" precedent, applied a third time).

### 18.4 Alias safety (Part 6) — reuses, does not fork, Milestone 5D.1's mechanism

Job-description prose is treated as the SAME free-form-text risk class
README prose is: a job posting's requirement bullets are still natural
language, not structured data, so the exact bare `go`/`next`/`js`/`ts`/`c`
false positives Milestone 5D.1 fixed for README extraction apply equally
here. `find_concept_mentions()` scans `concept.readme_safe_aliases()` --
the IDENTICAL per-concept safe-alias set `evidence/extraction/readme.py`
uses — rather than a second `job_unsafe_aliases` table. The shared
boundary-regex primitive itself was extracted from `readme.py` into
`concepts/matching.py::alias_pattern()` (Milestone 6B) specifically so
both callers use identical matching mechanics, not just identical DATA;
`readme.py`'s own behavior and tests are unaffected (confirmed:
`tests/test_evidence_extraction_readme.py` unchanged and passing).
Explicitly evaluated and rejected: a job-specific safety table — no
job-description-only false positive distinct from README's has been
observed (§18.11); if one ever is, `TechnicalConcept` could gain a
`job_unsafe_aliases` field the same data-driven way, without touching
this reasoning.

### 18.5 Unresolved/unknown-concept policy (Part 5)

Conservative by design: an unrecognized term is preserved as
`unresolved:<term>` (the SAME Milestone 5C mechanism, reused via
`concepts.registry.unresolved_concept_id()` — no second convention) ONLY
when it appears in a comma-containing list that ALSO contains at least
one term that already resolved to a known concept in the SAME claim
(`find_conservative_unknown_terms()`) — e.g. "Kubernetes" in "Python,
Kubernetes, and Docker". An isolated unrecognized word, or ANY claim with
zero already-confirmed concepts, is left alone entirely — "ordinary
prose should not" become `unresolved:*` (Part 5, verbatim).

**Requiring an actual comma** is itself a fix for two real false
positives found in Milestone 6B's own manual validation (§18.11) before
the guard was added: a bare "X and Y" with no comma is far more often a
verb phrase or prose clause than a technology list —
`"Build and maintain ETL pipelines using Python"` was promoting `"Build"`
to `unresolved:build`, and `"Proficiency in Python for tooling and
scripting"` was promoting `"scripting"` — both fixed by requiring a
comma before the list-scan runs at all (see `tests/test_job_parser.py`'s
two dedicated regression tests).

**Known limitation (accepted, documented, not fixed):** a standalone
bullet naming an out-of-registry technology with NO co-occurring known
concept in the same claim (e.g. a bare `"Kubernetes"` bullet on its own
line, or `"Familiarity with dbt"`) produces nothing — a real, observed
false negative (§18.11). Broadening the trigger to "any short,
capitalized, standalone bullet" was evaluated and explicitly rejected: it
would misfire on ordinary short phrases with no list-context guard at
all (e.g. "Fast learner" is exactly as shape-plausible as "Kubernetes"),
which is precisely the recklessness Part 5 warns against. The accepted
trade is fewer false positives at the cost of some missed standalone
technology bullets.

### 18.6 Non-technical requirements (Part 10) and necessity/importance/observability

`non_technical.py` is a small, curated, GENERIC phrase table (education,
legal/work-authorization, leadership/mentoring, soft-skill/
communication) — universal HR boilerplate present in virtually every
technical posting, never a technology name, so it is not "role-specific
parsing" in the sense the milestone forbids. A match always produces
`concept_id=None` — never a manufactured `TechnicalConcept` id like
`skill.communication`.

Necessity (`necessity.py`, Part 7): LOCAL wording in the claim's own
text (`required`/`must have`/... vs. `preferred`/`a plus`/`nice to
have`/...) always overrides the claim's section-derived
`necessity_hint`; with no local wording, the section hint applies
(REQUIRED for a Requirements/Responsibilities section or no recognized
section at all; PREFERRED for a Preferred-Qualifications-type section).
If a claim's text somehow contains BOTH markers, REQUIRED wins — the
conservative direction.

Importance (`importance.py`, Part 8): `MEDIUM` by default; a small
explicit strong-emphasis vocabulary (`critical`, `essential`, `expert`,
...) upgrades to `HIGH`; a small hedge vocabulary (`familiarity with`,
`exposure to`, ...) downgrades to `LOW`; a `PREFERRED` requirement with
no strong-emphasis override defaults to `LOW` (a "plus" is inherently
secondary). Ordinal only — no floating-point weights, per instruction.

Observability (`observability.py`, Part 9): two centralized dict
lookups, never `if concept == ...`. Every technical concept (resolved or
`unresolved:*`) defaults to `STRONGLY_OBSERVABLE` uniformly (every
category in the current small registry IS a concrete, demonstrable
technology). Non-technical requirements look up their `category` label
in a small table (`experience`/`education`/`legal`/`soft_skill` ->
`NOT_OBSERVABLE`; `leadership`/`alternative_requirement` ->
`PARTIALLY_OBSERVABLE`); an unrecognized category safely defaults to
`NOT_OBSERVABLE` — never silently overclaims what GitHub can verify.

Parser confidence (`confidence.py`, Part 12): one small mapping by
extraction "kind" — `resolved_concept`/`experience_qualifier` -> `HIGH`;
`unresolved_concept_listed`/`non_technical_pattern` -> `MEDIUM`;
`alternative_fallback` -> `LOW` (deliberately ambiguous by construction,
never higher).

### 18.7 Alternative/OR requirements (Part 14) — the milestone's central correctness gate

**Final design: structured alternative groups (Milestone 6B.1) — full
detail in §19.** In brief: an OR-shaped claim like "Python or Go" is
represented as ONE `JobRequirement` with `alternative_concept_ids =
("language.go", "language.python")` — never two independent `REQUIRED`
rows (which would misrepresent OR as AND), and never a text-only
placeholder the matcher would have to re-parse. `original_text` is still
preserved verbatim; necessity/importance apply to the GROUP as a whole,
never per-alternative. `PostgreSQL, MySQL, or MongoDB` and `AWS or Azure`
work the same way, mixing real registered concepts with conservatively
promoted `unresolved:<term>` ids where needed. Normal conjunction
(`"Python and PostgreSQL"`, `"Python, PostgreSQL, and Docker"`) is
unaffected — those remain independent requirements, exactly as before.

An earlier iteration of this milestone (still visible in
`docs/CHANGELOG_DEV.md`'s Milestone 6B entry, kept as the historical
record) implemented a text-only, non-technical placeholder for OR-claims
instead, following a selection misunderstanding about which of two
presented options was approved. That iteration was replaced with the
structured design above before Milestone 6B was committed — see the
Milestone 6B.1 changelog entry for the correction.

### 18.8 Deduplication (Part 13)

`dedup.py`: technical requirements dedupe on `(concept_id, necessity)` —
"Strong Python skills" (Requirements) and "Build Python backend
services" (Responsibilities) both assert "language.python is REQUIRED"
and collapse to one row. Alternative-group requirements (Milestone 6B.1,
§19) dedupe on `(alternative_concept_ids, necessity)` — checked BEFORE
the plain-technical key, since `is_technical` is `True` for both and
`concept_id` is `None` for a group, so without a dedicated key every
alternative group with the same necessity would collide regardless of
WHICH concepts it names (a real bug caught and fixed in 6B.1's own
tests, `test_alternative_group_never_collides_with_a_single_concept_requirement`).
Because `alternative_concept_ids` is stored SORTED
(`JobRequirement.__post_init__`, §19), "Python or Go" and "Go or Python"
produce the identical key and collapse to one row for free — no
set-vs-tuple special-casing needed in `dedup.py` itself. Non-technical
requirements dedupe on
`(category, necessity, normalized original_text)` — deliberately
narrower on TEXT so "3+ years of professional experience" and "5 years
professional Python experience" (different sentences, both
`category="experience"`) are NEVER merged into each other. This is
exactly what keeps Part 13's own worked example intact: "Python
required" and "5 years professional Python experience" — the two
TECHNICAL Python sub-claims correctly collapse (same fact, restated),
but the EXPERIENCE sub-claim the second sentence also produces has no
matching key anywhere and survives untouched (`tests/test_job_parser_extraction.py
::test_technical_and_experience_claims_from_overlapping_text_both_survive`).
When two requirements share a key, the HIGHER-`importance` occurrence is
kept (more informative for a future matcher); ties/no-conflict keep
first occurrence; output order always follows first occurrence,
regardless of which occurrence's field values won.

### 18.9 Experience qualifiers (Part 15)

`experience.py`: a bare numeric years-count (`"3+ years"`, `"5 years"`)
is the core, sufficient trigger — deliberately not requiring the literal
word "experience" nearby, since `"2+ years working with Kubernetes"`
never says it. When "experience" (optionally through "of" and a few
descriptive words) follows shortly after, the captured span extends to
include it for readability. Always becomes its OWN non-technical
requirement (`category="experience"`, `concept_id=None`), kept strictly
separate from whatever technical concept the same sentence mentions —
the direct mechanism behind Part 1/4's central worked example.

### 18.10 Known limitations

- The non-technical phrase table (§18.6) is fixed and curated — a
  posting phrasing "must have a degree" in a way the table doesn't cover
  is silently missed (not promoted to any fake category, just dropped).
- Section-hint leakage past the last real heading (§18.2).
- Standalone unknown-technology bullets with no list-context (§18.5).
- An OR-list where NONE of the alternatives is a registered concept
  (e.g. "Snowflake or BigQuery" — neither is in the registry) produces
  nothing at all, by the same conservative "needs an anchor" rule
  `find_conservative_unknown_terms` already applies to comma-lists (§19).
- No cross-sentence claim merging: a claim spanning two sentences
  connected only by pronoun reference ("Experience with Python. It
  should be recent.") is not stitched back together.
- No source imports/CI/test-directory-style deep reading of anything —
  this milestone only ever reads the pasted description text itself.

### 18.11 Manual real-world validation (Part 19)

Four hand-written, LOCAL job descriptions (no scraping) — Backend
Software Engineer, Robotics Software Engineer, ML Engineer, and Data
Engineer (the required "substantially different fourth role") — run
through `parse_job_description()` and inspected directly (see
`tests/test_job_parser.py`'s `test_manual_validation_*` for the locked-in
assertions; the fixture text lives in that same file).

**Confirmed correct across all four:** every known concept resolved
(`language.python`, `language.cpp`, `database.postgresql`,
`database.redis`, `infra.docker`, `cloud.aws`, `framework.nextjs`,
`robotics.ros2`, `platform.cuda`, `embedded.rtos.freertos`,
`ml.framework.pytorch`); every non-technical category fired correctly
(`experience`, `education`, `legal`, `leadership`, `soft_skill`); every
genuinely technical `or`-shaped claim ("Docker or Kubernetes", "AWS or
Azure") produced exactly ONE structured `alternative_concept_ids` group
and ZERO independent REQUIRED technical rows (Milestone 6B.1, §19); the
Backend example's entire `Benefits:` section (including a "React JS
meetups" line) produced zero requirements, confirming the skip-section
mechanism and proving `framework.react` was never falsely triggered by
marketing copy.

**Re-run after Milestone 6B.1's structured-alternative fix — two
concrete improvements over the original 6B run:**
- "Bachelor's degree in Computer Science, Robotics, or a related field"
  (Robotics) and "3+ years of experience in data engineering or a
  related field" (Data Engineer) now correctly categorize as
  `education`/`experience` (`NOT_OBSERVABLE`) instead of the generic
  `alternative_requirement` bucket — since neither OR-list contains a
  registered concept, 6B.1's `classify_alternative_claim()` correctly
  judges them `"not_technical"` and lets the normal non-technical
  detectors handle them (§19).
- "Docker or Kubernetes" (ML) and "AWS or Azure" (ML, Backend) now carry
  real structured `alternative_concept_ids` instead of an opaque
  text-only placeholder.

**False positives found and FIXED before this entry was written** (§18.5):
`unresolved:build` (from "Build and maintain ETL pipelines using
Python") and `unresolved:scripting` (from "Proficiency in Python for
tooling and scripting") — both fixed by requiring a comma before the
conservative unknown-term list-scan runs at all; both are now dedicated
regression tests.

**False negatives observed and ACCEPTED (documented, not fixed):**
"Kubernetes" and "dbt" as standalone bullets with no co-occurring known
concept in the same claim produce nothing (§18.5); "SQL" (not yet a
registry concept at all) inside "Strong SQL and Python skills" (no
comma) is not recovered; "Snowflake or BigQuery" (Data Engineer) — an
OR-list where NEITHER alternative is a registered concept — produces
nothing at all, the OR-list analog of the same "needs an anchor" rule
(§19); "Prior experience with control systems or robotics" (Robotics)
similarly produces nothing (neither side resolves, and no other detector
matches the remaining text).

No candidate was scored against any of these four postings — this
milestone produces `JobRequirementProfile`s only.

## 19. Structured alternative requirements — Milestone 6B.1

**Corrects Milestone 6B's OR-handling before it was committed.** 6B
represented "Python or Go" as a text-only, non-technical placeholder
(`concept_id=None`, `category="alternative_requirement"`) — safe against
misrepresenting OR as AND, but the future matcher would have had to
re-parse `original_text` to recover what the alternatives even were. The
parser owns text interpretation; the matcher must consume structured
semantics. This section documents the corrected, final design; §18.7
points here rather than duplicating it.

### 19.1 Schema extension

`JobRequirement` (`jobs/models.py`) gained one new field:

```
alternative_concept_ids: tuple[str, ...] = ()
```

Three, and only three, valid states for a technical-or-not requirement:

| State | `concept_id` | `alternative_concept_ids` |
|---|---|---|
| Normal technical requirement | a concept id | `()` |
| Alternative technical requirement | `None` | `(id_1, id_2, ...)`, >= 2 entries |
| Non-concept requirement | `None` | `()` |

`concept_id` and a non-empty `alternative_concept_ids` are mutually
exclusive — `__post_init__` raises if both are set. Each entry is
validated with the SAME `concepts.registry.is_valid_concept_id()` 6A.1
introduced for the single-`concept_id` case (no second validation rule,
per instruction); a set with fewer than 2 entries, or containing a
duplicate, is rejected. The stored tuple is SORTED, not kept in
call-order — "Python or Go" and "Go or Python" name the same set of
options (order is a fact about the sentence, not about the options), so
canonicalizing the order makes the two phrasings compare/hash equal
automatically, with no custom `__eq__`/`__hash__` needed. This is what
lets `dedup.py` and `JobRequirementProfile`'s existing exact-duplicate
rejection (Milestone 6A) treat both phrasings as identical for free (see
§18.8, and `tests/test_job_requirement_profile.py::
test_alternative_group_with_reordered_ids_is_an_exact_duplicate`).

`is_technical` is `True` for a group (it's still fundamentally about a
technology, just with >1 acceptable answer). `is_resolved_concept` /
`is_unresolved_concept` stay scoped to the single-`concept_id` case only
(a group is neither); two new properties cover the group case instead:
`is_alternative_group` and `has_unresolved_alternative` (true if at
least one option is an `unresolved:<term>` placeholder — e.g. "Python or
SomeNewRuntime").

### 19.2 Classification (`alternatives.py`): three outcomes, not two

`classify_alternative_claim()` replaces the old blanket "any claim with
a standalone 'or' is alternative-shaped" rule with one that requires
actual evidence the OR joins TECHNICAL alternatives:

1. Split the claim on `or` (and on `,` within each part, for Oxford-style
   "A, B, or C" enumerations) into segments, stripping a small set of
   trailing filler/necessity words per segment ("Go required" / "Go
   experience" -> "Go" — these belong to necessity/importance inference,
   computed separately from the full claim text, not to the alternative's
   name).
2. Resolve each segment in two steps: first `find_concept_mentions()`
   (prose-SAFE aliases only, §18.4) for a longer segment with a concept
   embedded in surrounding words; if that finds nothing, clean the
   segment to its core term and try `resolve_concept()` against the
   FULL alias set — a deliberate, narrow escalation, justified because a
   segment produced by splitting a CONFIRMED "X or Y" enumeration (at
   least one sibling already resolved) is closer to an isolated,
   structured token than to arbitrary free prose, which is exactly the
   context Milestone 5D.1's alias-safety restriction was never meant to
   apply to. This is what lets `"Go"` in `"Python or Go"` resolve to the
   real `language.go` (bare `"go"` is `readme_unsafe` for free-form prose
   scanning, but this is not that) instead of a needless
   `unresolved:go`. A segment that resolves neither way falls to the
   SAME conservative shape/stopword check `find_conservative_unknown_terms`
   already uses (§18.5) — passes -> `unresolved:<term>`; fails -> the
   whole claim is marked unsafe.
3. Combine: if NO segment resolved to a REAL registered concept anywhere
   (`any_confirmed` stays `False`), the claim is `"not_technical"` —
   there is not enough evidence this is a technology enumeration at all,
   so the caller runs the claim through the exact same pipeline as any
   other claim (this is the fix for "Bachelor's degree ... or a related
   field" and "3+ years experience or equivalent education" — both now
   correctly land in `education`/`experience`, not a fake alternative
   group, confirmed in the re-run manual validation, §18.11). If at
   least one segment IS confirmed but at least one OTHER segment failed
   the shape check, or fewer than 2 distinct ids survive, the claim is
   `"unsafe"` — falls back to the OLD 6B placeholder
   (`category="alternative_requirement"`, `parser_confidence=LOW`)
   rather than either dropping an option or inventing a reckless
   unresolved id. Otherwise `"technical"` — the caller builds one
   `JobRequirement` with `alternative_concept_ids` set.

### 19.3 Necessity / importance / observability for a group

Computed ONCE from the full claim text exactly as for any other claim
(`necessity.py`/`importance.py`, §18.6) — an alternative group is ONE
logical requirement, so "Python or Go required" has one `REQUIRED`
necessity, never per-alternative. Observability reuses
`observability_for_technical()` unmodified (`STRONGLY_OBSERVABLE`) — by
construction, every id in an `alternative_concept_ids` group is either a
real registered concept or a conservatively-promoted `unresolved:<term>`,
the same two shapes a normal technical requirement can have.

### 19.4 Deduplication

Full detail in §18.8. Key point: `is_technical` being `True` for BOTH a
normal technical requirement and an alternative group (both can have
`concept_id=None` in the group case) means the dedup key MUST branch on
`is_alternative_group` before falling back to the plain-technical key —
missing this was a real bug caught by this milestone's own tests
(`test_alternative_group_never_collides_with_a_single_concept_requirement`):
without it, EVERY alternative group with the same necessity would have
collided under one key regardless of which concepts it actually named.

### 19.5 Versioning

- `JOB_REQUIREMENT_SCHEMA_VERSION` 1 -> 2 — `JobRequirement` gained a
  field (§19.1), a genuine shape change per `jobs/types.py`'s own bump
  policy.
- `JOB_DESCRIPTION_PARSER_VERSION` `"job_description_parser:v1"` ->
  `"...v2"` — the parser's emitted semantics for OR-claims changed
  materially (structured groups instead of a text-only placeholder),
  mirroring the precedent `readme:v1` -> `readme:v2` set (Milestone
  5D.1: a behavior change to an extractor/parser bumps ITS OWN version
  string, independent of the domain-model schema version).
- `CONCEPT_REGISTRY_VERSION`, `EVIDENCE_SCHEMA_VERSION`,
  `REPOSITORY_RANKING_VERSION`, `SCORING_RUBRIC_VERSION`,
  `DATASET_VERSION` — all untouched; nothing in this correction touches
  the concept registry's data, candidate evidence, ranking, or V1
  scoring/dataset.

### 19.6 Known limitations (additive to §18.10)

- An OR-list where NO alternative is a registered concept (e.g.
  "Snowflake or BigQuery") produces nothing at all — the same
  conservative "needs a confirmed anchor" rule §18.5 already applies to
  comma-lists, applied consistently here rather than carved out as a
  special case.
- The `"unsafe"` fallback still loses per-concept structure for the ONE
  segment that failed the shape check, even though the OTHER segment(s)
  resolved cleanly (e.g. "Python or a genuinely amazing attitude" loses
  Python's own alternative-group structure, not just "attitude"'s) —
  accepted because building a partial group would misrepresent what the
  posting actually offered as alternatives.
- Trailing-filler stripping (§19.2 step 1) is a small, fixed word list
  (`required`, `preferred`, `experience`, `skills`, ...) — a phrasing
  using a filler word outside that list will leave it attached to the
  segment, which then fails to resolve as a clean technology name.

## 20. Deterministic requirement matching — Milestone 7A

```
CandidateEvidenceProfile (evidence/profile.py, §14-16)
        +
JobRequirementProfile (jobs/profile.py, §17-19)
        |
        v
match_job()                          (matching/engine.py)
        |
   (per requirement) match_requirement()
        |
        v
JobMatchAnalysis(requirement_matches=<tuple of RequirementMatch>, coverage=..., matcher_version=...)
```

New package: `gitscore.matching` (`matching/types.py`, `matching/
support.py`, `matching/models.py`, `matching/engine.py`). Not to be
confused with `gitscore.concepts.matching` (§19's shared alias-boundary
regex, `alias_pattern()`) — an unrelated layer that happens to share the
word "matching": that module answers "does this alias appear in this
text"; this package answers "does this candidate's GitHub evidence
support this job requirement."

**Scope boundary, explicit:** this milestone produces per-requirement
`SUPPORTED`/`NOT_OBSERVED`/`NOT_ASSESSABLE` verdicts only. NO 0-100
job-fit score, NO weighted aggregation, NO strengths/gaps prose, NO
hire/reject conclusion, NO alternative-role discovery. Those are
Milestone 7B+ concerns that CONSUME `JobMatchAnalysis` — deferred
because scoring/weighting requires calibration decisions
(`W_REQUIRED`/`W_PREFERRED`-style formulas, docs/design/
MILESTONE_5A_JOB_MATCHING_DESIGN.md Part 15) this milestone was not
asked to make, and because keeping "does evidence exist for this claim"
separate from "how much should that claim count toward a score" lets 7B
change the SCORING formula later without ever re-running the matcher.

### 20.1 MatchStatus — three states, not five

`docs/design/MILESTONE_5A_JOB_MATCHING_DESIGN.md` Part 16 (an early,
never-implemented draft) sketched a five-state status
(`SUPPORTED`/`WEAK`/`NOT_DETECTED`/`NOT_OBSERVABLE`/
`INSUFFICIENT_ANALYSIS`). Milestone 7A's actual instructions ask for a
smaller, principled set instead, and this is what got built:

| Status | Meaning |
|---|---|
| `SUPPORTED` | The requirement names >=1 technical concept (single `concept_id`, or — §19 — `alternative_concept_ids`) for which the candidate has sufficient evidence (§20.3). |
| `NOT_OBSERVED` | The requirement IS technical and IS GitHub-observable, but no sufficient evidence was found in the ANALYZED evidence. Never rendered as "the candidate lacks this skill" — only as "not observed in the analyzed GitHub evidence." `JobMatchAnalysis.coverage` (§20.5) is what tells a future explanation layer how much of the account that even was. |
| `NOT_ASSESSABLE` | The requirement is not the kind of claim GitHub evidence can meaningfully speak to at all (§20.2). Never rendered as "the candidate failed this requirement." |

**No `PARTIALLY_SUPPORTED`.** Considered and rejected, not merely
omitted: the only ordinal signal `CandidateConceptSummary` currently
offers is `ConfidenceLevel` (WEAK/MODERATE/STRONG), which
`evidence/types.py` itself documents as confidence in the OBSERVATION
being real, never a measure of candidate proficiency or "how much of a
requirement" is satisfied — there is no principled, deterministic way to
read a fractional-support meaning out of it today. For an alternative
group, "some but not all alternatives supported" is not partial support
either — 6B.1's OR semantics mean ANY one supported alternative already
fully satisfies the logical requirement; `RequirementMatch.
matched_concept_ids` records WHICH alternatives matched (for a future
explanation layer), but `status` is still a plain `SUPPORTED`.
`INSUFFICIENT_ANALYSIS` was also considered (the draft design's own
name for what `RepositoryAnalysisCoverage` — §20.5 — already
represents) and rejected AS A STATUS: coverage incompleteness is
preserved as its own structured fact on `JobMatchAnalysis`, not folded
into the per-requirement status, so a `NOT_OBSERVED` verdict and the
"how much of the account was analyzed" fact stay independently
queryable rather than conflated into one enum value.

### 20.2 The NOT_ASSESSABLE decision table

`matching/engine.py`'s `match_requirement()` docstring carries the full
table; summarized:

| `github_observability` | has a concept mapping (`concept_id` or `alternative_concept_ids`)? | result |
|---|---|---|
| `NOT_OBSERVABLE` | either | `NOT_ASSESSABLE` |
| `PARTIALLY_OBSERVABLE` | no | `NOT_ASSESSABLE` |
| `PARTIALLY_OBSERVABLE` | yes | checked like `STRONGLY_OBSERVABLE` |
| `STRONGLY_OBSERVABLE` | no | `NOT_ASSESSABLE` |
| `STRONGLY_OBSERVABLE` | yes | checked against evidence |

The one non-obvious row: a `PARTIALLY_OBSERVABLE` requirement WITH a
real concept mapping is matched exactly like a `STRONGLY_OBSERVABLE`
one. This is deliberate, not "simply treating `PARTIALLY_OBSERVABLE` as
`STRONGLY_OBSERVABLE`" by accident — it was checked against the ACTUAL
domain model rather than assumed: Milestone 6A's own hand-built manual
examples (`tests/test_job_requirement_manual_examples.py`) already
contain `PARTIALLY_OBSERVABLE` requirements WITH a populated
`concept_id` — "AWS experience preferred" (`concept_id="cloud.aws"`),
"Comfortable working in Linux environments"
(`concept_id="unresolved:linux"`), "Experience deploying models to
cloud platforms." Collapsing every `PARTIALLY_OBSERVABLE` requirement to
`NOT_ASSESSABLE` regardless of concept mapping would make real,
checkable GitHub evidence (a `boto3` dependency, a Dockerfile, a CI
config) for these permanently unmatchable — strictly LESS truthful than
checking it, not the "smallest safe behavior." What genuinely IS
`NOT_ASSESSABLE` under `PARTIALLY_OBSERVABLE` is a requirement with NO
concept mapping at all — `category="leadership"` ("mentoring junior
engineers", confirmed in the ML manual-validation fixture, §20.6) and
the 6B.1 "unsafe" alternative-group fallback (`category=
"alternative_requirement"`) — there the candidate-evidence model
genuinely has no structured surface to check (no concept id to look
up), so `NOT_ASSESSABLE` is the truthful answer, not a discount applied
on top of `SUPPORTED`/`NOT_OBSERVED`.

`NOT_OBSERVABLE` always wins regardless of concept mapping (defensive —
the job-side signal that GitHub cannot speak to this AT ALL is never
second-guessed by a `concept_id` happening to be attached, even though
the current parser never actually produces that combination).

### 20.3 Evidence-sufficiency policy

`matching/support.py`: `MINIMUM_SUPPORTING_CONFIDENCE =
ConfidenceLevel.WEAK` — i.e. the presence of ANY qualifying `Evidence`
for a concept, at any confidence tier, is sufficient for `SUPPORTED`.
Centralized as one named, testable constant (`has_sufficient_evidence()`)
rather than assumed inline — considered and NOT simply "any Evidence
exists":

1. `ConfidenceLevel` answers "how sure are we this observation is
   real," never candidate skill depth — using it as a skill-depth gate
   would repeat the exact conflation its own docstring warns against.
2. Every extractor already applies ITS OWN significance filter before
   producing Evidence at all — e.g. `evidence/extraction/languages.py`
   only emits Evidence (WEAK or above) for a language at >= 5% of a
   repository's bytes. WEAK evidence is not "maybe not real"; it is
   "genuinely present, just not the dominant signal." A stricter floor
   here would silently re-apply a SECOND, undocumented significance bar
   on top of each extractor's own.
3. With no `PARTIALLY_SUPPORTED` status (§20.1), discarding WEAK
   evidence would force it into `NOT_OBSERVED` — misrepresenting
   "observed, but weakly" as "not observed at all."

Kept as one named constant specifically so it CAN be tightened later
(e.g. if real-world validation shows WEAK-only language evidence alone
produces false-positive matches) without redesigning the matcher.

### 20.4 Normal and alternative-group matching

Normal technical requirement (`concept_id` set): looked up directly via
`CandidateEvidenceProfile.concept(concept_id)` — no fuzzy string
matching anywhere in this package; the parser (§18) and concept registry
already normalized every concept id on both the job side and the
candidate side, so the matcher only ever compares canonical concept-id
strings, including `unresolved:<term>` ids (matched by exact string
equality, the same deterministic ids `concepts.registry.
unresolved_concept_id()` already produces on both sides).

Alternative group (`alternative_concept_ids`, §19): EVERY alternative is
checked; the requirement is `SUPPORTED` if ANY has sufficient evidence
(true OR semantics — Part 6, directly: "Python or Go" requires evidence
for EITHER, never both). `RequirementMatch.matched_concept_ids` retains
EVERY alternative that matched (not just the first), stored sorted —
"Python or Go" with evidence for both Python and Go produces
`("language.go", "language.python")` deterministically regardless of
which was checked first.

Necessity, Importance, and ParserConfidence are read by NOTHING in this
matching logic — `RequirementMatch.requirement` retains them unchanged
for Milestone 7B to read later, but a `REQUIRED` vs. `PREFERRED`,
`HIGH` vs. `LOW` importance, or `LOW` vs. `HIGH` parser-confidence
requirement with identical candidate evidence always produces the
identical `status`.

### 20.5 Coverage handling

`JobMatchAnalysis.coverage` is the candidate's own
`RepositoryAnalysisCoverage` (§16), copied by reference (not
recomputed) from the matched `CandidateEvidenceProfile` — kept in
exactly ONE place, not duplicated onto every `RequirementMatch`
(repeating the identical object per match would be pure duplication
with no new information per match, mirroring how
`CandidateEvidenceProfile` itself keeps coverage once rather than
duplicating it onto every `Evidence` item). This is what lets Milestone
7B distinguish "Python not observed, every discovered repository was
analyzed" from "Python not observed, but only 15 of 1,140 repositories
were" without re-deriving that fact. No coverage PERCENTAGE or score is
computed here — `discovered_count`/`analyzed_count`/`is_complete` are
already exposed by `RepositoryAnalysisCoverage` itself (§16); inventing
a derived number on top of them is explicitly Milestone 7B's job, once
a calibrated formula exists.

### 20.6 Manual validation (Part 18)

The same four real job postings used for Milestone 6B/6B.1's manual
parser validation (§18.11 — Backend Software Engineer, Robotics
Software Engineer, ML Engineer, Data Engineer) run through the REAL
`parse_job_description()`, then matched against several deliberately
mixed, hand-built candidate evidence profiles
(`tests/test_matching_manual_examples.py`). Confirmed across all four:

- "Docker or Kubernetes" (ML): a candidate with ONLY Docker evidence
  (no Kubernetes evidence at all) is `SUPPORTED`, with
  `matched_concept_ids == ("infra.docker",)` — never requires both
  alternatives, the exact false-AND bug class this milestone guards
  against.
- "AWS or Azure" (ML, preferred): no candidate evidence for either ->
  `NOT_OBSERVED`, never `NOT_ASSESSABLE` (it IS a real technical
  alternative group).
- "3+ years ... experience", "Bachelor's degree ...", "eligible to work
  in the United States", "excellent written and verbal communication"
  (all four postings): all `NOT_ASSESSABLE`, never a technical gap.
- "mentoring junior engineers" (ML, `category="leadership"`,
  `PARTIALLY_OBSERVABLE`, no concept mapping): `NOT_ASSESSABLE` — NOT
  silently promoted to `SUPPORTED` by treating `PARTIALLY_OBSERVABLE`
  loosely.
- Every `SUPPORTED` match's `supporting_evidence` traces to real,
  attributable `Evidence`/`RepositoryIdentity` objects from the
  hand-built candidate profile — never fabricated, never generated
  prose.
- No score, coverage percentage, or hire/reject conclusion is computed
  anywhere in these tests.

### 20.7 Versioning

`MATCHER_VERSION = "requirement_matcher:v1"` (`matching/types.py`) — a
NEW, independent constant identifying THIS package's matching rules
(which statuses exist, what counts as sufficient evidence, how
alternative groups resolve). Does NOT bump
`JOB_REQUIREMENT_SCHEMA_VERSION`, `EVIDENCE_SCHEMA_VERSION`,
`CONCEPT_REGISTRY_VERSION`, or `JOB_DESCRIPTION_PARSER_VERSION` — this
milestone is purely additive: no existing domain-model shape, parser
behavior, or concept-registry data changed. `JobRequirement` and
`CandidateEvidenceProfile` are both consumed exactly as-is, unmodified.

### 20.8 Known limitations

- No 0-100 score, weighted aggregation, strengths/gaps prose, or
  hire/reject conclusion — explicitly deferred to Milestone 7B.
- No coverage PERCENTAGE — only the existing
  `discovered_count`/`analyzed_count`/`is_complete` facts are exposed;
  turning that into a calibrated number is 7B's job.
- `PARTIALLY_OBSERVABLE` with a concept mapping is matched identically
  to `STRONGLY_OBSERVABLE` (§20.2) — there is currently no distinct,
  principled way to require STRONGER evidence for a partially-observable
  claim than for a strongly-observable one; if a future milestone
  defines one, this is the extension point.
- No alternative-role discovery, no persistence, no API, no UI — all
  explicitly out of scope per this milestone's own instructions.

---

## 21. GitHub Evidence Alignment & structured assessment — Milestone 7B

```
JobMatchAnalysis (gitscore.matching, Milestone 7A)
        |
        v
  assess_job()                         (assessment/engine.py)
        |
        v
JobAssessment(match_analysis=..., scoring_version=...)
        |
   alignment_score, required/preferred SubscoreFacts,
   low_parser_confidence_count, supported/not_observed/not_assessable
   grouping helpers — all @property, derived on demand
```

New package: `gitscore.assessment` (`types.py`, `models.py`,
`engine.py`). Design approved in
`docs/design/MILESTONE_7B_SCORING_DESIGN.md` prior to implementation;
this section documents the as-built result. `assess_job()` consumes a
Milestone 7A `JobMatchAnalysis` exactly as-is — no rematching, no
GitHub/network/LLM calls, no new field required on `JobRequirement`,
`CandidateEvidenceProfile`, `RequirementMatch`, or `JobMatchAnalysis`.

### 21.1 GitHub Evidence Alignment — definition and formula

> GitHub Evidence Alignment measures, among the job requirements GitHub
> evidence can meaningfully speak to, what percentage are supported by
> evidence found in the candidate's analyzed GitHub material.

```
assessable_count = supported_count + not_observed_count
                  (equivalently: requirement_count - not_assessable_count)

alignment_score = None                                        if assessable_count == 0
alignment_score = round_half_up(100 * supported_count / assessable_count)   otherwise
```

**`NOT_ASSESSABLE` is excluded from the denominator entirely** — this is
the one load-bearing architectural decision the whole package exists to
enforce. `NOT_ASSESSABLE` means GitHub evidence cannot speak to the claim
at all (years of experience, a degree, work authorization, "mentoring
junior engineers" with no concept mapping); counting it in the
denominator would silently convert "this posting happens to list three
non-technical requirements" into "the candidate missed three
requirements," which directly contradicts the product rule that absence
of GitHub evidence is never treated as proof of absence of skill. See
`assessment/models.py`'s `_assessable_matches()` — the ONE place this
exclusion is implemented, reused by `assessable_count`,
`low_parser_confidence_count`, and the required/preferred subscore
computation, so there is no second, independently-maintained definition
of "assessable" anywhere in the package.

### 21.2 Rounding policy

`round_half_up_percentage(numerator, denominator)` (private,
`assessment/models.py`) rounds ties UP, via pure integer arithmetic
(`(2*numerator*100 + denominator) // (2*denominator)`) — NOT Python's
builtin `round()`, which uses round-half-to-even ("banker's rounding"):
`round(62.5) == 62` but `round(63.5) == 64`, a parity-dependent flip with
no product justification for a human-facing percentage. Pinned by
`tests/test_assessment_engine.py::test_half_up_rounding_62_5_rounds_up_to_63`
and `..._72_5_rounds_up_to_73`. No float arithmetic is used anywhere in
the computation — the `(2n + d) // (2d)` identity is the exact-integer
form of `floor(n/d + 0.5)`.

### 21.3 Required / Preferred — submetrics, not weights

`Necessity` does **not** weight `alignment_score`. Instead,
`JobAssessment.required`/`.preferred` each expose a `SubscoreFacts(
supported, assessable)` — a plain "X of Y" count, deliberately not a
second percentage (a second ratio would compete with `alignment_score`
for "which number is the real one"). `SubscoreFacts` rejects
`assessable < 1` by construction: a necessity tier with zero assessable
requirements is `None` on `JobAssessment`, never `SubscoreFacts(0, 0)` —
those are different facts ("never assessable" vs. "assessed and found
nothing").

**No cap, no floor, no gate.** A candidate with 0-of-2 REQUIRED
requirements supported and 6-of-6 PREFERRED requirements supported gets
`alignment_score == 75` — uncapped, not discounted to reflect the
required shortfall. This is pinned exactly in
`tests/test_assessment_engine.py::
test_adversarial_case_strong_headline_despite_zero_required_support`.
The resolution to the "a strong headline can hide zero required
coverage" problem is a **mandatory co-display requirement**, not a
formula change: `required` is always computed and must always be
rendered alongside `alignment_score` by any future presentation layer —
the instant both numbers are read together, "75, but 0 of 2 required"
is self-correcting. A hard ceiling/floor was considered and rejected:
with no labeled data, any specific cutoff (e.g. "cap at 50 if required
coverage < 50%") would be exactly the kind of invented precision this
project's "no fake precision" principle (`CLAUDE.md`,
`jobs/types.py`'s `Importance`/`ParserConfidence` docstrings) has
consistently rejected elsewhere.

### 21.4 Importance — read, never weighted

`Importance` (HIGH/MEDIUM/LOW) is never read by anything in this
package's scoring math. It remains available, unchanged, on
`RequirementMatch.requirement.importance` for any future presentation
layer — `JobAssessment` does not duplicate it. Rejected explicitly, not
merely unused: `jobs/parsing/importance.py`'s own `infer_importance()`
defaults a `PREFERRED` requirement to `LOW` unless an emphasis phrase
overrides it, meaning `Importance` is already a heuristic partially
*derived from* `Necessity`, not a clean second axis of ground truth —
weighting by both would compound one parser heuristic's uncertainty
twice, amplifying a single regex match into a disproportionate score
swing.

### 21.5 ParserConfidence — metadata, never score-affecting

`ParserConfidence` answers "how sure was GitScore's own parser it read
this sentence correctly," not anything about the candidate's evidence
(`jobs/types.py`'s own docstring). It affects neither `alignment_score`
nor repository coverage. The only aggregate this package computes from
it is `JobAssessment.low_parser_confidence_count` — the count of
**assessable** requirements (`SUPPORTED` or `NOT_OBSERVED`) whose
`parser_confidence == ParserConfidence.LOW`, informational metadata
only. Scoped to assessable requirements deliberately: a `NOT_ASSESSABLE`
requirement parsed with LOW confidence says nothing about how GitHub
evidence was read for it, so including it would mix two unrelated facts.
`parser_confidence is None` ("not evaluated by any parser") is never
counted as LOW — fabricating uncertainty where none was recorded would
be worse than reporting none.

### 21.6 Evidence confidence — unchanged from Milestone 7A

This package does not reopen Milestone 7A's evidence-sufficiency policy
(`matching/support.py`'s `MINIMUM_SUPPORTING_CONFIDENCE =
ConfidenceLevel.WEAK`). A `SUPPORTED` `RequirementMatch` counts as
exactly one supported assessable requirement in `alignment_score`,
regardless of whether its strongest supporting evidence is WEAK,
MODERATE, or STRONG — `ConfidenceLevel` remains confidence in the
observation being real, never candidate proficiency, one layer up from
where 7A already drew that line. Per-match evidence detail remains fully
inspectable (`RequirementMatch.supporting_evidence`) for any future
presentation layer that wants to show it; `JobAssessment` does not
pre-weight it.

### 21.7 Repository coverage — passed through unmodified

`JobAssessment.match_analysis.coverage` is the `RepositoryAnalysisCoverage`
Milestone 7A already attached — not duplicated, not recomputed, and NOT
turned into a coverage percentage. A naive `analyzed_count /
discovered_count` ratio would understate true coverage, since
Milestone 5B's ranker deliberately analyzes the highest-substantiveness
repositories first — "15 of 80 analyzed" is not "19% of the candidate's
evidence," and a synthesized percentage would claim a precision the
ranking heuristic can't support. `JobAssessment` deliberately has **no**
`coverage_note`/presentation-string field either (a correction made
during the Milestone 7B.0 design review): rendering "15 of 80
repositories deeply analyzed; highest-ranked repositories prioritized"
from `discovered_count`/`analyzed_count`/`is_complete` is a future
UI/API layer's job, not domain state.

### 21.8 Explanation groupings

`JobAssessment.supported_matches()` / `.not_observed_matches()` /
`.not_assessable_matches()` each delegate directly to
`JobMatchAnalysis.matches_with_status()` — no `RequirementMatch`/
`Evidence` object is copied or rebuilt, and `match_analysis.
requirement_matches`' own order (meaningful posting order, never
re-sorted — §17/§20) is preserved exactly.

Locked presentation wording (documented here, deliberately NOT stored as
strings in the domain model):

| Status | Heading | Required disclaimer |
|---|---|---|
| `SUPPORTED` | "Supported by GitHub evidence" | — |
| `NOT_OBSERVED` | "Not observed in analyzed GitHub evidence" | "...does not mean the candidate lacks the skill." |
| `NOT_ASSESSABLE` | "Not assessable from GitHub" | "...does not mean the candidate failed it." |

"Gaps" is deliberately not used anywhere — the heading reuses
`MatchStatus`'s own already-settled vocabulary (`NOT_OBSERVED`'s
docstring) rather than introducing a second, more deficiency-framed
synonym at the presentation boundary.

### 21.9 Edge cases

| Case | Behavior |
|---|---|
| No assessable requirements | `alignment_score = None`, `required = None`, `preferred = None` |
| All assessable supported | `alignment_score = 100` |
| Zero assessable supported | `alignment_score = 0` (not special-cased) |
| Only preferred assessable | `required = None`; `preferred` computed normally |
| Only required assessable | `preferred = None`; `required` computed normally |
| One assessable requirement | Score is legitimately 0 or 100 — volatile by construction, not a bug |
| All requirements `NOT_ASSESSABLE` | `alignment_score = None` |
| Incomplete repository analysis | Does not alter `alignment_score` — coverage stays a separate, parallel fact |
| LOW-parser-confidence assessable requirement | Increments `low_parser_confidence_count`; does not alter `alignment_score` |
| LOW-parser-confidence `NOT_ASSESSABLE` requirement | Does NOT increment `low_parser_confidence_count` (§21.5) |
| Unresolved concept (`unresolved:<term>`) | No special treatment — scored exactly like any other concept id |
| OR group (`alternative_concept_ids`) | Counts as exactly ONE assessable requirement, since 7A already produced one `RequirementMatch` for it |
| Candidate with zero evidence | Every technical requirement is `NOT_OBSERVED`; formula degrades correctly with no special-casing |

### 21.10 Versioning

`SCORING_VERSION = "github_evidence_alignment:v1"` (`assessment/
types.py`) — a new, independent constant identifying this package's
scoring rules (the formula, the rounding policy, which statuses are
excluded from the denominator, what counts toward
`low_parser_confidence_count`). Does NOT bump
`JOB_REQUIREMENT_SCHEMA_VERSION`, `EVIDENCE_SCHEMA_VERSION`,
`CONCEPT_REGISTRY_VERSION`, `JOB_DESCRIPTION_PARSER_VERSION`, or
`MATCHER_VERSION` — this milestone is purely additive, consuming
`JobMatchAnalysis` exactly as Milestone 7A produces it. No
`EXPLANATION_VERSION` was introduced: the explanation groupings (§21.8)
are exactly the `MatchStatus` partitions this package's scoring logic
already computes, not a distinct prose-generation step — a future
LLM-rendered-prose layer would be the point to introduce one.

### 21.11 Future calibration path

Nothing in this package needs to change for a future learned ranker to
replace the deterministic formula: every feature worth logging (per-
`RequirementMatch` status/necessity/importance/parser_confidence/
github_observability/evidence count/strongest confidence, plus the
whole-assessment `alignment_score`/`assessable_count`/subscores/coverage
facts) is already derivable from `JobMatchAnalysis` and `JobAssessment`
without new instrumentation. A learned model would replace
`assess_job()`'s internals behind the same `JobAssessment` shape — no
migration of `RequirementMatch`, `CandidateEvidenceProfile`, or
`JobRequirementProfile` data required.

### 21.12 Known limitations

- The dedup-survival double-count case: `jobs/parsing/dedup.py` dedupes
  by `(concept_id, necessity)`, so the same concept stated once as
  REQUIRED and once as PREFERRED elsewhere in the same posting survives
  as two distinct `JobRequirement` rows and is counted twice (once in
  each subscore) — a known, inherited limitation from 7A's domain model,
  not something this package silently "fixes" with a second, undefined
  dedup pass.
- No alternative-role discovery, no learned/CatBoost scoring, no
  recruiter labels or hire/reject recommendation, no persistence, no
  API, no UI, no LLM-generated prose — all explicitly out of scope per
  this milestone's own instructions.
- Exact presentation wording (§21.8) is documented but not yet
  user/legal-reviewed for a real recruiter-facing release.
