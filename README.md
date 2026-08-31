# GitScore AI

GitScore AI analyzes a public GitHub profile and produces a rule-based
**portfolio-readiness score (0-100)** for ML/AI-oriented roles, from
GitHub evidence alone (repositories, languages, READMEs, stars/forks —
no code execution, no private data).

## What the score means

The score is a hand-written, deterministic rubric over five categories:

| Category | Weight |
|---|---|
| ML Experience | 35 |
| Project Originality | 20 |
| Documentation Quality | 15 |
| Language / Tool Relevance | 20 |
| Community Signal | 10 |
| **Total** | **100** |

Each category is scored from features extracted from the user's public
repositories (ML-related keywords/frameworks detected, ratio of
original vs. forked repos, README completeness, language mix, stars and
forks). See `src/gitscore/scoring/readiness.py` for the exact rules and
`docs/ML_NOTES.md` for the full feature/target definitions.

## What the score does NOT mean

**GitScore is an engineering/portfolio-readiness rubric, not a
prediction or proof of hiring success.** Specifically:

- It does not predict whether a candidate will get hired, pass an
  interview, or perform well on the job.
- It only sees what's public on GitHub under the analyzed user's own
  account — it does not see organization-owned repositories the user
  contributes to, private work, or non-GitHub experience.
- It rewards patterns that correlate loosely with "has an active,
  documented ML portfolio," not code quality, correctness, or technical
  depth.
- No model has been trained on this score yet, and any future model
  trained *on* this score would primarily learn to reproduce the rubric
  itself (see `docs/ML_NOTES.md` for why) — not an independent measure
  of anything.

## Current architecture (MVP)

```
GitHub username
  -> GitHub REST API collection      (src/gitscore/github/)
  -> repository parsing              (src/gitscore/github/parser.py)
  -> feature engineering             (src/gitscore/features/)
  -> rule-based GitScore             (src/gitscore/scoring/readiness.py)
  -> SQLite persistence              (src/gitscore/db/)
  -> Pandas dataset (via scripts/show_dataset.py)
```

There is no web UI or CatBoost model yet — this is a CLI-driven,
pre-ML foundation. See `docs/ARCHITECTURE.md` and `docs/PIPELINE.md`
for the full component/data-flow breakdown, and `docs/CHANGELOG_DEV.md`
for the history of what's been fixed and why.

## Setup

Requires Python 3.11+.

```bash
python -m venv .venv

# activate it:
# Windows (PowerShell):  .venv\Scripts\Activate.ps1
# Windows (cmd):          .venv\Scripts\activate.bat
# macOS/Linux:            source .venv/bin/activate

pip install -e ".[dev]"
```

This installs the project itself (`gitscore`) in editable mode plus its
runtime dependencies (`requests`, `python-dotenv`, `SQLAlchemy`,
`pandas`) and dev/test dependencies (`pytest`) as declared in
`pyproject.toml` — that file is the single source of truth for
dependencies; there is no separate `requirements.txt`.

Then initialize the local SQLite database (creates `data/gitscore.db`,
idempotent — safe to re-run):

```bash
python scripts/init_db.py
```

### Environment variables

Copy `.env.example` to `.env` and fill in `GITHUB_TOKEN`:

```bash
cp .env.example .env
```

| Variable | Required | Purpose |
|---|---|---|
| `GITHUB_TOKEN` | Optional, strongly recommended | A GitHub personal access token (no special scopes needed for public data). Unauthenticated requests are capped at 60/hour; an authenticated token raises that to 5000/hour. |

Never commit `.env` (it's gitignored) or paste a real token into chat,
logs, or a script argument.

## Running it

Analyze a single GitHub user and print the result (fetches from the
real GitHub API and writes to `data/gitscore.db`):

```bash
python scripts/collect_user.py <github-username>
```

Run a small hardcoded batch of users (see the list in the script):

```bash
python scripts/collect_dataset.py
```

Inspect everything collected so far as a Pandas DataFrame:

```bash
python scripts/show_dataset.py
```

## Running tests

```bash
pytest
```

All tests are offline — no real GitHub API calls, no token required,
and no writes to the real development database (`data/gitscore.db`).
GitHub HTTP responses and the persistence layer are faked/mocked at
their boundaries; see `tests/conftest.py` for the shared fakes and
`docs/ARCHITECTURE.md` §11 for what each test file covers.

## Current project status

Milestones completed so far (see `docs/CHANGELOG_DEV.md` for full
detail on each):

1. **Feature correctness** — fixed description-coverage, empty-repo-list
   crashes, and ML-keyword false-positive bugs in feature extraction.
2. **GitHub data collection reliability** — full repository pagination,
   HTTP timeouts, bounded retry/backoff, distinguishable rate-limit
   errors, per-repo graceful degradation, thread-safe concurrent fetching.
3. **Project hygiene / pre-ML release readiness** — dependency
   declaration in `pyproject.toml`, the `feautures` -> `features`
   package rename, repository hygiene (`.gitignore`, dropped stale
   generated files), scoring and end-to-end pipeline test coverage,
   this README.

**Not yet implemented:** the real training dataset has not been
collected (existing rows in the local dev database predate the
Milestone 1/2 fixes and must not be used for it — see
`docs/ML_NOTES.md`), no CatBoost model exists, there is no web UI, and
organization-owned-repository analysis is not implemented. See
`CLAUDE.md`'s priority order for what's next.
