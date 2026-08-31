# GitScore AI — Project Instructions

## Product Goal

GitScore AI analyzes a GitHub profile and produces a portfolio-readiness score for ML/AI roles.

Current MVP flow:

GitHub username
→ GitHub API collection
→ repository parsing
→ feature engineering
→ rule-based GitScore
→ SQLite persistence
→ Pandas dataset
→ future CatBoost model
→ explanations/recommendations
→ UI/demo

The current MVP measures generic ML/AI portfolio readiness from GitHub evidence only.
Do not claim that GitScore predicts actual hiring success.

Long-term product direction:
- role-specific scoring from a job title / job description
- dynamically adjust scoring based on current ML/AI hiring demands
- AI-generated strengths, weaknesses, and project recommendations
- recruiter-facing analysis mode

Do NOT implement those long-term features until the core MVP is stable unless explicitly requested.

## Engineering Principles

1. First make it work, then make it reliable, then make it beautiful.
2. Preserve existing working behavior unless there is a clear reason to change it.
3. Prefer small, understandable refactors over large rewrites.
4. Do not duplicate logic.
5. Keep modules single-purpose.
6. Use type hints where practical.
7. Handle API failures, rate limits, missing repositories, missing READMEs, and malformed data gracefully.
8. Never expose secrets.
9. Never commit `.env`, tokens, `.venv`, local database files, or model artifacts unless intentionally configured.
10. Do not silently change the GitScore scoring definition.

## Current Architecture

### GitHub layer
`src/gitscore/github/client.py`
- GitHub REST API access
- user lookup
- repository lookup
- language lookup
- README lookup

`src/gitscore/github/parser.py`
- transforms raw GitHub API data into clean internal repository objects

### Feature engineering
`src/gitscore/features/`
NOTE: this package was originally misspelled `feautures`; it was renamed to
`features` in Milestone 3 (see docs/CHANGELOG_DEV.md) with all imports/tests/docs
updated. If you see `feautures` anywhere (old branches, stale docs), it refers
to this same package under its old name.

Feature modules include:
- activity
- languages
- quality
- ML signals
- README/documentation
- profile aggregation

### Database
`src/gitscore/db/database.py`
- SQLite configuration
- SQLAlchemy engine
- SessionLocal
- ORM Base

`src/gitscore/db/models.py`
- User
- ProfileFeature

`src/gitscore/db/queries.py`
- persistence operations

### Scoring
`src/gitscore/scoring/readiness.py`

Current score:
- ML Experience: 35
- Project Originality: 20
- Documentation Quality: 15
- Language / Tool Relevance: 20
- Community Signal: 10

Total: 100

The current readiness score is a rule-based synthetic label.
Important: a CatBoost model trained only on this label will primarily learn to reproduce this scoring formula.
Do not present that model as proof of real-world hiring prediction.

### Pipeline
`src/gitscore/pipeline/analyze.py`

`analyze_user(username)` is the reusable application pipeline:
- fetch user
- save/update user
- fetch repositories
- fetch repo languages and READMEs
- parse repositories
- extract features
- calculate GitScore
- persist feature snapshot
- return user/features/score

Repository metadata fetching uses ThreadPoolExecutor for concurrency.

### CLI scripts
`scripts/collect_user.py`
- single-user CLI

`scripts/collect_dataset.py`
- batch collection

`scripts/show_dataset.py`
- inspect SQLite data with Pandas

`scripts/init_db.py`
- initialize local SQLite schema

## Performance

GitHub repository processing is network-bound.

Current strategy:
- ThreadPoolExecutor
- conservative worker count
- batch error handling

When optimizing:
- measure before/after
- respect GitHub rate limits
- prefer connection reuse and caching
- avoid unnecessary repeated API calls
- do not sacrifice correctness for speed

## Database Rules

- SQLite is currently the MVP database.
- Local DB files are development artifacts and should not be committed.
- Do not delete the database automatically.
- If schema changes are required, explain whether migration or recreation is needed.
- Prefer Alembic if schema evolution becomes non-trivial.

## AI / ML Rules

Before training any model:
- clearly define X and y
- prevent leakage
- remove identifiers and timestamps that should not be predictive
- split train/test correctly
- document all preprocessing
- report proper evaluation metrics
- never fake metrics or training data

For CatBoost:
- preserve categorical variables when useful
- record feature importance
- save model metadata
- make inference deterministic and reproducible

## UX Direction

Final product should feel like a professional recruiting / engineering analytics tool, not a school project.

Desired UI:
- clean
- minimal
- technical
- recruiter-friendly
- strong typography
- clear score hierarchy
- category breakdown
- strengths
- weaknesses
- concrete recommendations
- repository evidence
- loading/progress feedback

Avoid:
- excessive gradients
- generic AI-chatbot aesthetic
- gamified childish visuals
- meaningless animations
- fake precision

## Documentation Requirement — IMPORTANT

Every meaningful change MUST update documentation.

Maintain:

`docs/ARCHITECTURE.md`
- current system structure
- major data flow
- responsibilities of important files/modules

`docs/CHANGELOG_DEV.md`
- append one entry for every meaningful code/system change
- explain:
  - what changed
  - why
  - files affected
  - how the new logic works
  - risks / limitations
  - how to test it

`docs/PIPELINE.md`
- end-to-end data flow
- API → parser → features → scoring → DB → ML → UI

`docs/ML_NOTES.md`
- feature definitions
- target definition
- training strategy
- leakage risks
- metrics
- model assumptions

Whenever you add or modify a system:
1. implement it
2. test it
3. update the relevant docs
4. summarize the change to the user

Do not create a brand-new documentation file for every tiny edit.
Update the existing documentation files unless a new subsystem genuinely deserves its own document.

## Code Change Workflow

Before making substantial changes:
1. inspect relevant files
2. explain the current architecture
3. identify issues
4. propose a short plan
5. implement
6. run tests / smoke tests
7. review your own diff
8. update docs

Do not rewrite the whole repository in one pass.

## Git Rules

- Do not commit unless explicitly asked.
- Never force push.
- Never rewrite history.
- Before suggesting a commit, show a concise summary of changed files.
- Keep commits cohesive.

## Secrets

Never print, log, expose, or commit:
- GitHub PAT
- `.env`
- API keys
- credentials

## Testing

Add tests around critical behavior:
- feature extraction
- score boundaries
- database persistence
- pipeline behavior
- malformed/missing GitHub data

Prefer deterministic unit tests over live GitHub API calls.

## Current Priority

Finish a polished MVP before building GitScore 2.0.

Priority order:
1. correct data collection
2. robust dataset creation
3. ML dataset preparation
4. CatBoost baseline
5. inference pipeline
6. explanation/recommendation layer
7. UI
8. deployment / polish
9. role-specific and market-aware GitScore