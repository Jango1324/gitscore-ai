# GitScore AI — Dev Changelog

## 2026-08-31 — Milestone 3: Project hygiene, pipeline testing, pre-ML release readiness

**What changed:**

*Dependency / packaging (see docs/ARCHITECTURE.md §10):*
- `pyproject.toml` — added `dependencies = ["requests>=2.31",
  "python-dotenv>=1.0", "SQLAlchemy>=2.0", "pandas>=2.0"]` (floor
  versions, no upper-bound pins) and
  `[project.optional-dependencies] dev = ["pytest>=7.0"]`. Previously
  declared zero dependencies anywhere.
- `requirements.txt` — **removed**. It was a `pip freeze` dump from an
  unrelated ROS2 project (confirmed in the original audit), not this
  project's dependencies. Rather than regenerate it as a second,
  easily-stale copy of what `pyproject.toml` now declares, it was
  deleted outright — `pyproject.toml` is the single source of truth.
  Documented decision (see "Packaging decisions" below).
- Verified fresh-environment installability: `pip install -e .` and
  `pip install -e ".[dev]"` both resolved and succeeded (dry-run,
  against a real package index), and `pip wheel . --no-deps` produced a
  real wheel whose contents were inspected directly.

*Package structure / rename (see docs/ARCHITECTURE.md §1, §5, §10):*
- **Renamed `src/gitscore/feautures/` -> `src/gitscore/features/`.**
  Moved `activity.py`, `languages.py`, `ml.py`, `profile.py`,
  `quality.py`, `readme.py`; updated their imports
  (`gitscore.feautures.*` -> `gitscore.features.*`) in `profile.py` and
  in `src/gitscore/pipeline/analyze.py`; fixed the three
  `..._feautures` local-variable typos in `profile.py` to
  `..._features` while already editing that file; updated the two
  affected test files' imports
  (`tests/test_feature_extractors_current_behavior.py`,
  `tests/test_profile_module_dedup.py`, the latter also gaining a test
  that the old `feautures/` directory is gone); updated `CLAUDE.md`'s
  note about the misspelling; updated `docs/ARCHITECTURE.md`,
  `docs/PIPELINE.md`, `docs/ML_NOTES.md` current-state references (old
  changelog entries below are left as accurate history of what was true
  at the time, not rewritten). `feautures/deployment.py` (already
  documented as an empty, unused stub) was not carried over into the
  new directory — dropped as dead code. Verified via
  `grep -rn feautures` that only intentional historical references
  remain (docstrings/changelog entries describing the rename itself).
- Added `src/gitscore/features/__init__.py` and
  `src/gitscore/scoring/__init__.py` — both packages previously had
  none, unlike every other package in the tree (the one packaging
  fragility this milestone's fresh-install verification actually
  exercises — see "Packaging decisions" below).
- Removed two other empty, `git`-untracked, unreferenced placeholder
  directories left over from initial project scaffolding:
  `src/gitscore/app/`, `src/gitscore/ml/`, `src/gitscore/nlp/`.
  Confirmed empty and unreferenced (`grep` across `src/`, `scripts/`,
  `tests/`, `docs/`, `CLAUDE.md`, `pyproject.toml`) before removal.

*Repository hygiene (see docs/CHANGELOG_DEV.md "Findings" below):*
- `.gitignore` — added `.pytest_cache/`, `build/`, `dist/`,
  `*.egg-info/`, SQLite journal/WAL/SHM sidecar patterns
  (`data/*.db-journal`, `-wal`, `-shm` and the `.sqlite*` equivalents),
  a forward-looking `models/`/`*.cbm`/`*.pkl`/`*.joblib` block for
  not-yet-existent CatBoost artifacts, and `.vscode/`/`.idea/`.
- `src/gitscore_ai.egg-info/` — **untracked** (`git rm --cached`) and
  deleted from the working tree. It was committed to git and stale
  (confirmed missing several real files); it's fully auto-regenerated
  by `pip install -e .` and now matched by the new `.gitignore` rule.
- `.env.example` — was empty (0 bytes); now documents `GITHUB_TOKEN`
  with the rate-limit rationale for setting it.
- Confirmed via `git log --all --diff-filter=A --name-only` that `.env`
  has never been committed, and via pattern grep across `*.py`/`*.md`/
  `*.toml`/`*.txt` that no hardcoded GitHub token is present anywhere
  in the repo. No secret values were printed while checking either.

*Scoring tests (see docs/PIPELINE.md Stage 4):*
- `tests/test_scoring_readiness.py` — **new**, 90 tests.
  `scoring/readiness.py` had zero dedicated tests before this. Covers
  the all-zero-features minimum (0), the documented 100-point maximum
  (including deliberately absurd input values, to confirm the total
  cannot exceed 100), category-scores-always-sum-to-total-score,
  determinism, every if/elif threshold boundary in all five category
  ladders, and three hand-computed representative low/medium/high
  profiles. **No scoring bug was found** and **no weights or
  thresholds were changed** — every category's maximum matches its
  documented weight exactly (ML 35 + Originality 20 + Documentation 15
  + Language/Tool 20 + Community 10 = 100), confirmed by both the
  per-category max tests and the all-categories-maxed-simultaneously
  test.
- `tests/conftest.py` — added `make_score_features()`.

*Pipeline tests (see docs/PIPELINE.md, docs/ARCHITECTURE.md §11):*
- `tests/test_analyze_user_pipeline.py` — **new**, 5 tests, mocking
  only the two boundaries `analyze_user()` actually crosses (GitHub via
  a fake `GitHubClient`, persistence via recording fakes for
  `save_user`/`save_profile_features`):
  - normal user, full pipeline, asserts the public result shape
    (`{"user", "features", "score", "time"}`) and that both boundaries
    were called with the right data;
  - zero-repository user completes cleanly with the documented
    zero/no-evidence values and a `0` total score;
  - a nonexistent user (`GitHubNotFoundError` from `get_user()`)
    propagates and **persists nothing** (`save_user`/
    `save_profile_features` both un-called);
  - one repo's languages/README fetch failing (Milestone 2 policy)
    still produces a complete profile with the repo included, at the
    `analyze_user()` level, not just unit-tested in `fetch_repo_data()`;
  - a `save_profile_features()` failure propagates instead of being
    swallowed into a result that looks successfully saved (`save_user`
    already committed by that point — documented limitation, not a bug,
    see `docs/PIPELINE.md` Stage 5).
  - (A rate-limit-during-processing scenario is already covered by
    Milestone 2's
    `tests/test_pipeline_repo_failure_handling.py::test_analyze_user_aborts_the_batch_when_a_worker_hits_a_rate_limit`
    and is not duplicated here.)
- `tests/conftest.py` — added `raw_repo()` (also now used by
  `tests/test_pipeline_repo_failure_handling.py`, replacing a duplicate
  local copy — same repo dict shape, no behavior change),
  `FakeGitHubClient`, `fake_github_client_factory()`, `FakeSavedUser`.

*Database snapshot semantics (see docs/ARCHITECTURE.md §7a,
docs/ML_NOTES.md §6) — reviewed, not changed:*
- `save_profile_features()` inserts a new `ProfileFeature` row on every
  `analyze_user()` call — no upsert, no unique constraint on `user_id`.
  Read as an intentional "timestamped historical snapshot" mechanism
  (each row is individually timestamped) that is currently
  **unexploited** — nothing queries "latest per user" anywhere yet.
- **No schema change made this milestone** (no `is_latest` flag, no
  unique constraint) — not required by an actual correctness bug, so
  deferred per instruction.
- **Policy defined for later:** the future dataset builder must select
  one row per `user_id` (max `collected_at`) *before* any statistics/
  split, not query `profile_features` unfiltered. Documented in full in
  `docs/ML_NOTES.md` §6, including a concrete illustration from the
  current dev database (see below).

*Old development data (see docs/ML_NOTES.md §7):*
- Inspected `data/gitscore.db` directly: 3 users, 13 `profile_features`
  rows. Confirmed **every row predates Milestones 1 and 2**:
  `description_coverage_ratio == 1.0` on all 13 rows (the Milestone-1
  bug signature) and `karpathy`'s row has `total_repos == 30` exactly
  (the Milestone-2 pagination-truncation signature). One user
  (`Jango1324`) accounts for 8 of the 13 rows (~62%) — a concrete,
  present-day illustration of the snapshot-overrepresentation risk
  above, not a hypothetical one.
- Documented clearly (`docs/ML_NOTES.md` §7) that none of these rows
  may be used in the clean ML dataset.
- **Did not delete or modify `data/gitscore.db`.** Recommendation only
  (exact commands given in `docs/ML_NOTES.md` §7: `rm data/gitscore.db`
  + `python scripts/init_db.py`), to be executed by whoever starts real
  dataset collection, not automatically by this milestone.
- **Real dataset collection was not started**, per explicit instruction.

*Developer workflow / README (see docs/ARCHITECTURE.md §10):*
- `README.md` — was empty (0 bytes); now covers what GitScore AI does,
  what the score means and explicitly does **not** mean (not a hiring
  prediction), current MVP architecture, setup (`python -m venv`,
  `pip install -e ".[dev]"`, `python scripts/init_db.py`), environment
  variables (`GITHUB_TOKEN`, optional/recommended, with rate-limit
  rationale), how to run single-user analysis and the batch/inspection
  scripts, how to run tests (`pytest`), and current project status
  (Milestones 1-3 done; dataset/CatBoost/UI/org-analysis not yet). No
  Docker, no marketing claims.

**Why:** This milestone's purpose was to make the GitHub → features →
scoring → database pipeline a clean, reproducible, well-tested
foundation before real dataset collection or CatBoost work begins —
explicitly scoped ahead of that work by instruction, with scoring
weights, feature definitions, the DB schema, org-contribution analysis,
and the UI all explicitly out of scope.

**Packaging decisions (explicit, per instruction to choose one and
document why):**
- *Dependencies:* declared in `pyproject.toml` rather than left
  implicit, with floor versions rather than exact pins — this is a
  library-style application, not a deployment artifact; exact pins
  belong in a lockfile generated from `pyproject.toml` if/when a
  reproducible deployment environment is actually needed, not
  hand-maintained in `pyproject.toml` itself.
- *`requirements.txt`:* removed rather than regenerated or replaced
  with a minimal version. `pyproject.toml` already fully declares
  runtime + dev dependencies; a second file duplicating that
  information is pure drift risk with no offsetting benefit at this
  project's current size — and drift is exactly how the file ended up
  as an unrelated ROS2 dump in the first place. If a pinned lockfile
  becomes genuinely necessary later (CI reproducibility, deployment),
  generate one from `pyproject.toml` at that time.
- *`feautures` -> `features` rename:* done now rather than deferred,
  per the instruction's own framing ("before ML/UI layers create more
  imports") — the rename touched exactly 6 source files' imports, 2
  test files, and current-state doc references; that blast radius only
  grows once CatBoost feature-engineering code and a UI layer start
  importing from this package too. No compatibility shim was added
  (none was needed — this is a private internal package, not a
  published API with external consumers).

**Tests added/changed:** suite grew from 71 to 166 tests (90 scoring +
5 pipeline, plus `raw_repo()`/`FakeSavedUser()`/`fake_github_client_factory()`
sharing eliminating one small duplicate), all passing, still no network
access, GitHub token, or real database writes required.

**Risks / limitations:**
- The old dev database (`data/gitscore.db`) still exists on disk with
  its 13 pre-fix rows — it was deliberately not touched (see above).
  Anyone running `scripts/show_dataset.py` before it's cleaned up will
  see that stale data.
- No schema change was made for DB snapshot semantics, so nothing
  currently *enforces* the "latest row per user" dataset policy — it is
  a documented convention the future dataset-builder script must
  actually implement, not something the database guarantees on its own.
- `pyproject.toml`'s dependency floors were chosen from what's
  currently installed/working, not exhaustively tested against their
  literal minimum-declared versions (e.g. `requests>=2.31` was not
  separately verified to work with exactly 2.31.0) — low risk for this
  project's usage, but worth knowing if a very old dependency set is
  ever forced.
- The `feautures` -> `features` rename is a pure rename with identical
  behavior — verified by the full test suite passing and by
  `grep -rn feautures` returning only intentional historical
  references — but it was not exercised against a real GitHub API call
  in this session (see "release-readiness checks" below for what was
  and wasn't run).

**How to test it:**
```
cd gitscore-ai
pytest
```
Expected: 166 passed.

---

## 2026-08-31 — Milestone 2: GitHub data collection reliability

**What changed:**
- `src/gitscore/github/exceptions.py` — **new**. `GitHubError` (base),
  `GitHubNotFoundError` (genuine 404), `GitHubRateLimitError` (carries
  `reset_at`/`retry_after` when GitHub supplied them), `GitHubRequestError`
  (non-retryable / retry-exhausted failures, carries `status_code`).
  Replaces the bare `Exception(f"... {status_code}")` used for every
  failure mode previously.
- `src/gitscore/github/client.py` — rewritten around one internal
  `_get()` request helper used by all four public methods:
  - **Pagination**: `get_repositories()` now loops `page=1,2,...` with
    an explicit `per_page=100` until a page comes back shorter than
    `per_page` (i.e. it's the last page), concatenating pages in fetch
    order. A `max_pages=50` safety cap (~5000 repos) raises
    `GitHubRequestError` instead of looping forever if GitHub ever kept
    returning full pages indefinitely.
  - **Timeouts**: every request now passes `timeout=` (default `10.0s`,
    centralized as `DEFAULT_TIMEOUT_SECONDS`, configurable per
    `GitHubClient(timeout=...)`).
  - **Retries**: connection errors, timeouts, and `{500, 502, 503, 504}`
    responses are retried with bounded exponential backoff
    (`0.5s, 1s, 2s`, capped at `8s`; `DEFAULT_MAX_RETRIES=3` → up to 4
    attempts total). 404s and other 4xx codes are never retried. The
    sleep function is injectable (`sleep_func=`) so tests never wait
    through real backoff delays.
  - **Rate limits**: a 403 with `X-RateLimit-Remaining: 0`, a 403 with
    `Retry-After`, or a plain 429 now raises `GitHubRateLimitError`
    immediately (never retried, never waited-out automatically) with
    `reset_at`/`retry_after` populated from GitHub's headers when
    present. A plain 403 with none of those signals (e.g. permission
    denied) still raises `GitHubRequestError`, not a rate-limit error.
  - Removed the dead header-construction code (three methods built an
    `Accept`/`X-Requested-With` dict then immediately discarded it with
    `headers = {}`) — headers are now built once in `_headers()` and
    actually sent (`Accept: application/vnd.github+json`).
  - `get_repository_readme()`'s existing "404 → `None`" behavior for a
    missing README is preserved (now implemented by catching the new
    `GitHubNotFoundError` internally).
- `src/gitscore/pipeline/analyze.py`:
  - **Per-repo failure policy**: `fetch_repo_data()` now treats a
    repo's languages/README fetch as optional metadata — if it raises
    `GitHubRequestError`/`GitHubNotFoundError` after the client's own
    retries are exhausted, that one repo degrades gracefully
    (`languages={}` / `readme=None`) and the repo is still included, so
    one flaky repo no longer fails the whole profile analysis. A
    `GitHubRateLimitError` is **not** swallowed — it propagates and
    aborts the batch, since continuing would just burn more of an
    already-exhausted rate-limit budget for degraded data. `get_user()`
    and `get_repositories()` failures still propagate uncaught, per
    "user fetch failure → profile cannot be analyzed."
  - **Thread-safety**: each `ThreadPoolExecutor` worker thread now gets
    its own lazily-created `GitHubClient` (`threading.local()`) instead
    of all 8 workers sharing one `requests.Session`. `requests.Session`
    is not documented as safe for concurrent use; this removes that
    assumption entirely while keeping most of the connection-reuse
    benefit (each worker thread still reuses its own session across
    every repo it handles). `max_workers=8` (now `MAX_REPO_WORKERS`) is
    unchanged — already conservative, kept for the same batch
    performance as before.
  - Repo fetches are now submitted via `executor.submit()` (instead of
    `executor.map()`) so that on a fatal error (a rate limit) every
    not-yet-started future is cancelled instead of letting the whole
    queued batch run first — `executor.map()` would still drain the
    queue before propagating the exception, wasting more of an
    already-exhausted rate-limit budget. Result order is unchanged
    (`.result()` is read back in submission order).
  - Added concise `logging` (page-fetch progress at `debug`, retry/
    degradation notices at `warning`/`info`) — no request headers,
    tokens, or full request objects are ever logged.
- `tests/test_github_client_current_behavior.py` — the three tests that
  intentionally pinned the old bugs (single-page fetch, no timeout, no
  rate-limit typing) are rewritten to assert the corrected behavior.
- `tests/test_github_client_reliability.py` — **new**, 21 tests:
  pagination (fewer-than-one-page, exactly-one-full-page,
  multiple-pages, empty-list, infinite-loop guard), timeout
  configuration, retry/backoff (connection error, timeout, 5xx, bounded
  exhaustion, backoff growth/cap, 404-not-retried, 422-not-retried),
  and rate limits (primary, secondary/`Retry-After`, `429`, plain-403
  is-not-a-rate-limit).
- `tests/test_pipeline_repo_failure_handling.py` — **new**, 6 tests:
  `fetch_repo_data()` graceful degradation and rate-limit propagation,
  one-`GitHubClient`-per-worker-thread, and batch-abort-on-rate-limit
  at the `analyze_user()` level.
- `tests/conftest.py` — added shared `FakeResponse`, `ScriptedSession`
  (records calls, returns a pre-programmed sequence of
  responses/exceptions), and `RecordingSleep` fakes used across all
  three GitHub-client/pipeline test files.

**Why:** These were the pagination/timeout/retry/rate-limit/concurrency
findings from the 2026-08-30 audit, scoped as Milestone 2 by explicit
instruction. Feature definitions, scoring weights, the DB schema, the
UI, and CatBoost were explicitly out of scope and untouched.

**Repository-level failure policy (explicit decision):**
| Failure | Behavior |
|---|---|
| `get_user()` fails (any reason) | Propagates — profile cannot be analyzed without knowing who the user is. |
| `get_repositories()` fails (any reason) | Propagates — profile cannot be analyzed without knowing what repos exist. |
| One repo's README is missing (404) | Expected condition — `readme=None`, repo still included. Unchanged from before. |
| One repo's languages/README fetch fails transiently, retries exhausted | Repo degrades gracefully (`languages={}`/`readme=None`), still included — logged at `warning`. |
| Any repo fetch hits a rate limit | Propagates immediately, aborts the whole `analyze_user()` call — not swallowed per-repo. |

**Tests added/changed:** suite grew from 46 to 70 tests, all passing,
still no network access or GitHub token required.

**Risks / limitations:**
- Pagination stops based on `len(page) < per_page`, not by parsing
  GitHub's `Link` header. This is simpler and equally correct given a
  fixed `per_page`, but relies on GitHub's documented default page-size
  behavior rather than an explicit "no more pages" signal.
- Retry backoff has no jitter — under concurrent worker threads hitting
  the same transient failure simultaneously, their retries could
  cluster instead of spreading out. Not addressed here; `max_workers=8`
  keeps the practical blast radius small.
- Even with future-cancellation on a rate-limit abort, futures **already
  running** when the rate limit is detected still complete (Python
  threads can't be interrupted mid-flight) — only not-yet-started queued
  futures are cancelled. With `max_workers=8` this bounds the worst-case
  extra wasted requests to a small constant, not the whole remaining
  batch.
- `GitHubClient(sleep_func=...)` is a real constructor parameter (not
  just a test seam) — production code always uses the default
  `time.sleep`; nothing changes there.
- **Dataset impact (see `docs/ML_NOTES.md` §5 update)**: any rows in
  `data/gitscore.db` collected before this fix reflect at most 30 repos
  per user (the old single-page bug) and may be missing users entirely
  where an unhandled rate limit or transient failure aborted collection
  partway through a batch. These rows must not be mixed with data
  collected after this fix without re-verification — no migration or
  backfill was performed (out of scope; database schema untouched).

**How to test it:**
```
cd gitscore-ai
.venv/Scripts/python.exe -m pytest tests/ -v
```
Expected: 70 passed.

---

## 2026-08-30 — Milestone 1: Feature correctness

**What changed:**
- `src/gitscore/feautures/quality.py` — fixed the description-coverage
  condition (`or` → `and` + blank-string check) and added a
  `total_repos == 0` guard so `average_stars`/`average_forks`/
  `description_coverage_ratio` return `0` instead of raising
  `ZeroDivisionError`.
- `src/gitscore/feautures/languages.py` — guarded `max(all_languages,
  ...)` against an empty dict; `most_used_language` now returns `""`
  (sentinel for "no language data") instead of raising `ValueError`.
  Also fixed the `most_used_langauge` variable-name typo internally.
- `src/gitscore/feautures/ml.py` — rewrote keyword matching from raw
  `word in text` substring search to word-boundary-aware regex
  (`ML_KEYWORDS` list unchanged; matching strategy changed).
- `src/gitscore/feautures/profile_features.py` — **deleted**. Confirmed
  unused via `grep -rn "profile_features" --include="*.py" .` (only
  hits were the unrelated `profile_features` DB table name and
  function name, no actual import of the module). See "Correction"
  below.
- `tests/test_feature_extractors_current_behavior.py` — rewritten:
  tests that previously pinned the three bugs above now assert the
  fixed behavior; new tests added for the empty-repo-list sentinel
  values, every entry in `ML_KEYWORDS` matching as a standalone token,
  and hyphen/underscore-separated tokens still matching.
- `tests/test_profile_module_dedup.py` — new, guards against
  `profile_features.py` reappearing and confirms
  `feautures/profile.py` still works as the pipeline's actual import
  target.
- `docs/ARCHITECTURE.md`, `docs/PIPELINE.md`, `docs/ML_NOTES.md` —
  updated to describe the fixed behavior instead of the bugs (see
  each file's diff for specifics).

**Why:** These were the top correctness findings from the 2026-08-30
audit (below) that directly affect what the GitScore measures. Fixing
them was scoped as Milestone 1 by explicit instruction — no pagination,
retries, CatBoost, UI, or deployment work included.

**Previous incorrect behavior → new behavior:**
| Area | Before | After |
|---|---|---|
| `description_coverage_ratio` | Always `1.0` (the `or` condition was tautologically true) | Reflects the actual fraction of repos with a non-blank description |
| `extract_quality_features([])` | Raised `ZeroDivisionError` | Returns all-zero feature dict |
| `extract_language_features([])` (or repos with no language data) | Raised `ValueError` from `max()` on an empty dict | Returns `most_used_language=""`, all counts `0` |
| `ml.py` keyword matching | Raw substring search; `"ai"` matched inside "container"/"explain"/"email", `"ml"` matched inside "html" | Word-boundary-aware regex; only matches the keyword as a standalone token (space/hyphen/underscore/punctuation-delimited) |
| `feautures/profile_features.py` | Existed, unused, previously (inaccurately) documented as a byte-identical duplicate of `profile.py` — it was actually empty | Deleted |

**Correction to the prior audit entry:** the 2026-08-30 audit below
described `profile_features.py` as "byte-identical" to `profile.py`.
Re-reading the file while implementing this fix showed it was actually
0 bytes on disk (and 0 bytes in the git-tracked version — confirmed via
`git diff --stat` showing `0 insertions, 0 deletions` for its
deletion). The original read that reported matching content was
inaccurate; the file's true state was empty, not duplicated. It has
been removed regardless, since it was confirmed unused either way.

**Tests added/changed:** suite grew from 12 to 46 tests, all passing.
See `tests/test_feature_extractors_current_behavior.py` and
`tests/test_profile_module_dedup.py`.

**Risks / limitations:**
- Any rows already in `data/gitscore.db` (`profile_features` table)
  were collected under the old buggy code —
  `description_coverage_ratio` and `ml_repository_count`/
  `ml_keyword_total` in those historical rows are not comparable to
  data collected after this fix. No migration or backfill was
  performed (out of scope for this milestone; database schema was not
  touched, per instructions).
- `scoring/readiness.py` was **not modified** — score weights and
  thresholds are unchanged, as instructed. Scores computed from
  corrected features will differ from scores computed from the old
  buggy features for the same GitHub profile (e.g. a profile with a
  false-positive "html" ML match will now score lower on ML
  Experience), which is the intended effect of fixing the bug, not a
  regression.
- Pagination, retries/timeouts, CatBoost, and UI/deployment work were
  explicitly out of scope and remain exactly as described in the prior
  audit.

**How to test it:**
```
cd gitscore-ai
.venv/Scripts/python.exe -m pytest tests/ -v
```
Expected: 46 passed.

---

## 2026-08-30 — Full engineering audit (no production code changed)

**What changed:** No behavior in `src/gitscore/` was modified. Added:
- `docs/ARCHITECTURE.md`, `docs/PIPELINE.md`, `docs/ML_NOTES.md` (this
  file was previously created but empty — filled in for the first time)
- `tests/conftest.py`, `tests/test_feature_extractors_current_behavior.py`,
  `tests/test_github_client_current_behavior.py` — 12 characterization
  tests, all passing against the current codebase, no network access
  required
- `pytest` installed into `.venv` (not yet declared in `pyproject.toml`
  or `requirements.txt` — see ARCHITECTURE.md §10)

**Why:** Requested full audit of the repository before any rewrite
work begins, per the user's instructions and `CLAUDE.md`'s Code Change
Workflow ("inspect relevant files, explain the current architecture,
identify issues, propose a short plan" before implementing).

**Files affected:** `docs/ARCHITECTURE.md`, `docs/PIPELINE.md`,
`docs/ML_NOTES.md`, `docs/CHANGELOG_DEV.md` (all new/filled-in);
`tests/conftest.py`, `tests/test_feature_extractors_current_behavior.py`,
`tests/test_github_client_current_behavior.py` (new). No files under
`src/` or `scripts/` were modified.

**How the new logic works:** N/A — no new production logic. Tests are
pure characterization tests: they call existing extractor functions
with synthetic repo dicts (see `tests/conftest.py::make_repo`) and a
fake `requests.Session` substitute for `GitHubClient`, and assert on
the *current* (including buggy) behavior, to make audit findings
independently verifiable and to catch accidental behavior changes
during future refactors.

**Risks / limitations:**
- This audit is based on static reading of the code plus offline tests
  against synthetic data. No live call to the GitHub API was made, so
  live-only behaviors (actual rate-limit response headers, actual
  `Link` header pagination format) are described from GitHub's
  documented API contract, not from an observed live response.
- `src/gitscore/github/client.py` has one **pre-existing uncommitted**
  change (`git diff` shows an added, unused `import time` on line 4) —
  present before this audit started, not introduced by it, left as-is.
- Two files (`.env.example`, `README.md`) were confirmed empty (0
  bytes) but intentionally left untouched — writing user-facing
  onboarding docs and an env template is scoped as implementation work
  for the roadmap below, not part of a read-only audit.

**How to test it:**
```
cd gitscore-ai
.venv/Scripts/python.exe -m pytest tests/ -v
```
Expected: 12 passed. Each test's docstring explains which specific
finding (in ARCHITECTURE.md / PIPELINE.md / ML_NOTES.md) it verifies.

**Findings summary (see the three docs above for full detail):**
1. `quality.py:9` description-coverage condition (`or` instead of
   `and`) makes `description_coverage_ratio` always `1.0` — BUG
2. `quality.py`/`languages.py` crash on an empty repo list
   (`ZeroDivisionError`/`ValueError`); `readme.py`/`activity.py` guard
   the same case — inconsistent, crashes `analyze_user()` for brand-new
   accounts — BUG
3. `ml.py` keyword matching is unbounded substring search
   ("ai" inside "container", "ml" inside "html") — false positives
   inflate the ML Experience score (35/100 weight) — misleading score
4. `feautures/profile.py` and `feautures/profile_features.py` are
   byte-identical duplicate files; `profile_features.py` is dead code
   — duplication
5. `github/client.py`: no pagination (`get_repositories` fetches page 1
   of 30 only), no `timeout=`, no retries, no rate-limit-aware handling,
   generic `Exception` for every failure mode, and dead
   header-construction code (`headers = {}` overwrites a built dict in
   3 methods) — correctness + robustness
6. `requirements.txt` is a `pip freeze` dump from an unrelated ROS2
   project, not this project's dependencies; `pyproject.toml` declares
   zero runtime dependencies — dependency-configuration gap
7. `src/gitscore_ai.egg-info/` (a build artifact) is committed to git
   and is stale relative to the current source tree
8. `scripts/collect_dataset.py:23` references a loop variable outside
   the loop — `NameError` risk / misleading batch-summary output
9. Rule-based `readiness_score` is a deterministic closed-form function
   of the stored feature vector; training CatBoost on it will primarily
   reproduce the rubric, not predict real-world hiring success — see
   `docs/ML_NOTES.md` §3
10. Org-owned-repository blind spot: only user-owned repos are fetched,
    systematically undercounting candidates whose ML work lives in an
    organization's GitHub — see `docs/ML_NOTES.md` §5

**Next step:** see the roadmap delivered alongside this audit (5
milestones, ordered) — no implementation has started; this entry will
be followed by a new entry per milestone once work begins, per
`CLAUDE.md`'s documentation requirement.
