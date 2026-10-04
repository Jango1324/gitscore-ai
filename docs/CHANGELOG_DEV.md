# GitScore AI — Dev Changelog

## 2026-10-04 — Milestone 8B: Minimal product frontend

**What changed:** First usable browser experience for GitScore. New,
fully separate application `frontend/` (Next.js + TypeScript) consuming
the Milestone 8A `/api/v1/analyze` contract — a user enters a GitHub
username and pastes a job description, and sees GitHub Evidence
Alignment, required/preferred support, repository coverage, and the
supported/not-observed/not-assessable requirement groups with evidence
provenance. No GitScore analysis logic is reproduced in TypeScript; the
frontend is a renderer/client only. Full as-built writeup:
`docs/ARCHITECTURE.md` §24. This entry summarizes.

**Framework decision:** no frontend existed before this milestone.
Selected Next.js + TypeScript (App Router) per the milestone's stated
default. One plain global stylesheet, no Tailwind/component-library
dependency. Pinned `typescript@^5.9.3` (latest stable 5.x) rather than
the newly-released TypeScript 7 major — a deliberate "boring" choice,
not an oversight. Testing: Vitest + React Testing Library + jsdom
(lighter than Jest + `next/jest` for a project this size).

**Location:** `frontend/` is fully separate from `src/gitscore/` — its
own `package.json`/`node_modules`/build. The two applications
communicate only over the frozen HTTP contract;
`frontend/src/types/api.ts` is a hand-written mirror of
`gitscore.api.schemas`, never generated from the Python dataclasses.

**API client:** `lib/api.ts::analyzeJob()` throws `ApiError`
(status/code/message/retryable from the API's own error envelope) or
`NetworkError` (fetch itself failed — offline/DNS/CORS/backend down).
Base URL via `NEXT_PUBLIC_GITSCORE_API_URL`, defaulting to
`http://localhost:8000` in code — never a hardcoded production URL.

**Component structure:** `AnalyzePage` (state: idle/loading/success/
error, one `useState` per concern, no Redux/Zustand) composes
`AnalyzeForm` → `LoadingNotice`/`ErrorBanner`/`ResultView`.
`ResultView` composes, in the required order: `AlignmentHeadline` →
`SubscoreRow` (required/preferred, immediately beneath the headline,
never in an accordion) → `RepositoryCoverage` → `RequirementSection`
×3 (supported/not_observed/not_assessable) → `DiagnosticsPanel` (last,
collapsed).

**Null/zero rendering (carried through from 7B/8A):**
`alignment === null` → "Not available" + explanation, never 0/NaN/-1.
`required`/`preferred === null` → "No {required|preferred}
requirements were assessable", never "0 of 0 supported".
`RepositoryCoverage` never computes a percentage — "N of M repositories
deeply analyzed" plus a prioritization note when incomplete, or "All N
discovered repositories were deeply analyzed" when complete.

**Requirement-section wording** (the one place it lives:
`lib/labels.ts::requirementSectionCopy()`): "Supported by GitHub
evidence" / "Not observed in analyzed GitHub evidence" (+ "This does
not mean the candidate lacks the skill.") / "Not assessable from
GitHub" (+ "GitHub evidence cannot reliably establish these
requirements."). An empty group renders "None." rather than
disappearing. Pinned by a forbidden-word sweep: "failed"/"missing
skill"/"unqualified"/"hire"/"reject"/"weakness" never appear in a
rendered result.

**Evidence provenance:** grouped by repository, friendly
`evidence_type` labels (cosmetic lookup table, unrecognized values fall
back to themselves), confidence capitalized, `file_path`/`detail`
shown — only fields `EvidenceItem` actually carries. No fabricated
repository/file URL, source line, star count, or commit activity.

**Error handling:** API/network errors render the API's own safe
message via `ErrorBanner` — never a stack trace, exception name, or
backend path. "Try again" shown only when `retryable` is true.

**Accessibility/responsive:** real `<label htmlFor>` on every input,
`aria-invalid`/`aria-describedby` on validation errors, `role="status"
aria-live="polite"` loading notice, `role="alert"` error banner,
visible `:focus-visible`, semantic headings. One `max-width: 600px`
breakpoint stacks the two-column form row and the required/preferred
cards — desktop is the primary MVP target.

**Diagnostics:** last section, collapsed `<details>` by default. A
non-zero `extraction_failure_count` surfaces one modest, neutrally
styled sentence outside the `<details>` — never implying the whole
analysis failed.

**Tests:** 23 — `ResultView.test.tsx` (13, pure rendering against
hand-built fixtures: null/zero distinctions, neutral wording, evidence
provenance, diagnostics ordering, forbidden-word sweep, no fabricated
links) and `AnalyzePage.test.tsx` (10, integration through the real
form/API client with `fetch` mocked: rendering, validation, loading/
disabled-submit, success render, every error-mapping case, retry).
`npm run type-check` (`tsc --noEmit`) is the type-check/lint gate — no
separate ESLint config added (dependency-minimization choice).
**Backend: 777 tests, unchanged. Frontend: 23/23 passing. Production
build (`next build`) succeeds.**

**Local integration smoke test:** ran the real backend (`uvicorn`) and
frontend (`next dev`) together and issued one real
`POST /api/v1/analyze` for `Jango1324` WITH an `Origin:
http://localhost:3000` header, reproducing exactly what the browser's
CORS preflight + fetch would send — confirmed
`access-control-allow-origin: http://localhost:3000` on both the
preflight `OPTIONS` and the real `POST`, and a normal 200 response
(`alignment=67`, `required={2,3}`, 2 supported / 1 not_observed /
0 not_assessable). The session's interactive browser-automation tool
did not respond after repeated attempts, so visually clicking through
the rendered page (loading spinner, rendered DOM, empty console) was
NOT completed this session — flagged as a known limitation; the
scripted check above does verify the real CORS/HTTP behavior a browser
depends on, just not the rendering itself.

**Backend/API changes:** none. Milestone 8A's contract was consumed
exactly as frozen.

**Files changed:**
- `frontend/` — new application (`package.json`, `tsconfig.json`,
  `next.config.ts`, `vitest.config.ts`, `.env.local.example`,
  `.gitignore`, `src/app/*`, `src/components/*`, `src/lib/*`,
  `src/types/*`, `src/test/*`).
- `docs/ARCHITECTURE.md` — new §24.
- `docs/PIPELINE.md` — new "Frontend" section.
- `docs/CHANGELOG_DEV.md` — this entry.

**How to test:**
```
cd frontend && npm install && npm run test       # 23 tests, offline
cd frontend && npm run type-check && npm run build
cd .. && python -m pytest                        # 777 tests, unchanged
```
Local dev: terminal 1 `uvicorn gitscore.api.app:app --reload`; terminal
2 `cd frontend && npm run dev`; browse `http://localhost:3000`.

**Known limitations:** the actual browser click-through (loading
spinner, rendered result, empty console) was not performed this
session — the browser-automation tool was unresponsive; a human (or a
future session) should still do this once. No ESLint config. No result
persistence, accounts, job-URL ingestion, LLM, or alternative-role
discovery — all explicitly out of scope. No commit was made.

## 2026-10-03 — Milestone 8A: Thin backend API

**What changed:** First HTTP transport exposing
`gitscore.application.analyze_job_fit()`. New package `gitscore.api`
(`app.py`, `routes.py`, `schemas.py`, `serialization.py`, `errors.py`):
`POST /api/v1/analyze` and `GET /api/v1/health`. Contains no business
logic — the endpoint validates the request shape, calls
`analyze_job_fit()` exactly once, and serializes its result. Full
as-built writeup: `docs/ARCHITECTURE.md` §23. This entry summarizes.

**Framework decision:** no HTTP framework existed in the repo before
this milestone (nothing web-related in `pyproject.toml` or `.venv`).
Selected FastAPI + Pydantic + uvicorn per the milestone's own stated
default — typed contracts, generated OpenAPI, offline `TestClient`
testing, future React/Next.js integration. A brand-new package with
nothing existing to conflict with; no major architectural change
required.

**Package boundary:** `gitscore.api` depends on `gitscore.application`;
nothing in `gitscore.application` or any domain package imports from
`gitscore.api` — dependency direction stays one-way.

**Endpoint behavior:** `routes.py::analyze()` calls `analyze_job_fit()`
exactly once and hands its result straight to
`serialize_job_analysis_result()`. No `parse_job_description`/
`match_job`/`assess_job`/`extract_candidate_evidence` name is bound
anywhere in `routes.py` — pinned by a test that checks the module's
actual bound names, not a text grep. `health()` performs no GitHub or
database call.

**Request contract — `AnalyzeRequest`:** `github_username` (required,
1-39 chars — GitHub's own account-name limit) and `job_description`
(required, 1-20,000 chars), both rejected if blank/whitespace-only
after stripping; `job_title`/`job_company` (optional, <=200 chars,
blank coerced to `None`). `top_n`, a custom `GitHubClient`, and every
other internal `analyze_job_fit()` knob are deliberately NOT exposed.

**Response contract — `AnalyzeResponse`:** a hand-selected shape
(`analysis`, `assessment`, `required`, `preferred`,
`repository_analysis`, `requirements` with `supported`/`not_observed`/
`not_assessable`, `diagnostics`, `versions`) — never a raw
`dataclasses.asdict(JobAnalysisResult)` dump. `alignment_score`/
`required`/`preferred` serialize `None` as JSON `null`, never `0`/
`"N/A"`/`-1`/a fabricated `{"supported": 0, "assessable": 0}`.
`not_assessable` requirements are always present in the response, never
omitted for not affecting the score. Every `status` value is one of
`MatchStatus`'s own neutral strings — never "failed"/"missing_skill"/
"unqualified"/"gap".

**Evidence serialization:** only fields `Evidence` actually stores —
`concept_id`, `evidence_type`, `confidence` (lower-cased enum name,
never a raw int), `repository` (`owner`/`name`), `file_path`, and
`detail` (`raw_observation`, already extractor-bounded, never a full
README/manifest dump). No fabricated repository URL (`Evidence`/
`RepositoryIdentity` have no `source_url` field by design) and no
`location` (no extractor has ever populated it).

**Error mapping — one structured envelope
(`{"error": {"code", "message", "retryable"}}`) for every non-2xx
response:**

| Exception | HTTP | code |
|---|---|---|
| Blank/oversized input / stray `ValueError` | 422 | `invalid_request` |
| `GitHubNotFoundError` | 404 | `github_user_not_found` |
| `GitHubRateLimitError` | 503 (+`Retry-After`) | `github_rate_limited` |
| `GitHubRequestError`, status 401/403 | 500 | `github_auth_configuration_error` |
| `GitHubRequestError`, status in `RETRYABLE_STATUS_CODES` | 502 | `github_upstream_error` |
| `GitHubRequestError`, status `None` (connection/timeout) | 503 | `github_unavailable` |
| `GitHubRequestError`, other status | 502 | `github_upstream_error` |
| Anything else | 500 | `internal_error` |

Rate limiting is modeled as 503, not 429: the caller never talks to
GitHub directly, so it's GitScore's own server-side credential that's
exhausted, not the caller's quota. A 401/403 on GitScore's own outbound
GitHub request is a server configuration problem (bad/missing
`GITHUB_TOKEN`), not a caller error — 500. No new exception subclasses
were added to `gitscore.github.exceptions` for HTTP convenience; this
package branches on `GitHubRequestError.status_code`, the one signal it
already carries. Nothing is ever leaked to the caller — no stack trace,
no exception text, no token, no filesystem path; the unexpected-failure
handler logs the full exception server-side and returns only the
generic `internal_error` envelope.

**Synchronous/blocking strategy:** `analyze_job_fit()` is synchronous
(`GitHubClient` is a plain blocking `requests.Session` user). Both
endpoints are plain `def`, not `async def` — FastAPI's own documented
mechanism: a sync path-operation function runs in a worker thread pool
automatically, so a blocking `analyze_job_fit()` call never blocks the
event loop. Nothing under `gitscore.application`/`gitscore.github` was
rewritten to be async.

**Dependency injection:** `routes.py::get_github_client()` returns
`None` in production (so `analyze_job_fit()` constructs its own real
`GitHubClient()`); tests override it via
`app.dependency_overrides[get_github_client]` to inject the existing
`FakeEvidenceGitHubClient` test double — every API test is offline.

**CORS:** explicit local dev origins (`http://localhost:3000`,
`http://127.0.0.1:3000`), `allow_credentials=False` — never `"*"`
combined with credentials.

**No persistence:** request → analysis → response; `JobAnalysisResult`/
`AnalyzeResponse` are never written to the database.

**Versioning:** API is path-versioned (`/api/v1/...`). No analytical
version constant bumped or duplicated; no separate `API_SCHEMA_VERSION`
introduced — the path prefix is the versioning signal for this
milestone.

**Dependency hygiene:** added `fastapi`/`uvicorn[standard]` under a new
`[project.optional-dependencies] api` extra; added `httpx` under the
existing `dev` extra (only needed for `TestClient`). No lock file
exists to hand-edit; no unrelated dependency upgraded.

**Tests:** 31 new — `tests/test_api_serialization.py` (10: pure
domain -> API conversion on hand-built `JobAnalysisResult`s, no HTTP —
exact happy-path values, `None`/null for alignment/required/preferred,
neutral status values, NOT_ASSESSABLE presence, OR-group concept ids,
evidence shape incl. no fabricated repository URL, diagnostics counts,
version pass-through, ordinal-enum-as-lowercase-name serialization) and
`tests/test_api_routes.py` (21: health; valid analyze with full shape;
optional title/company; null alignment/required/preferred; NOT_OBSERVED/
NOT_ASSESSABLE presence; OR-group preservation; evidence/diagnostics
preservation; blank/oversized username/JD rejection; GitHub not-found/
rate-limit/auth/network/upstream-5xx -> HTTP mapping incl. `Retry-After`;
sanitized unexpected-failure response with no leakage; `analyze_job_fit`
called exactly once; `routes.py` binds no domain-stage-function name;
deterministic serialization). All offline via `FakeEvidenceGitHubClient`
and FastAPI's `TestClient` — no network, no GitHub token. **777 tests
total, all passing** (up from 746).

**Real-account validation:** ran the server locally
(`uvicorn gitscore.api.app:app`) and made one real
`POST /api/v1/analyze` for `Jango1324` against the same ML Engineer
posting used in 7C's smoke test, with a real `GITHUB_TOKEN`. HTTP 200;
`alignment_score=50`, `required={2,3}`, `preferred={0,1}`,
`repository_analysis={discovered:20, analyzed:15, complete:false}`,
2 supported / 2 not_observed / 2 not_assessable requirements, zero
extraction failures — identical to 7C's direct-pipeline result, as
expected for pure transport. Not treated as scientific validation.

**Files changed:**
- `src/gitscore/api/__init__.py`, `app.py`, `routes.py`, `schemas.py`,
  `serialization.py`, `errors.py` — new package.
- `tests/test_api_routes.py`, `tests/test_api_serialization.py` — new.
- `pyproject.toml` — new `api` extra (`fastapi`, `uvicorn[standard]`);
  `httpx` added to `dev`.
- `docs/ARCHITECTURE.md` — new §23.
- `docs/PIPELINE.md` — new "HTTP API" section.
- `docs/CHANGELOG_DEV.md` — this entry.

**How to test:** `python -m pytest` (whole suite, 777 tests, no
network/token required) or `python -m pytest tests/test_api_routes.py
tests/test_api_serialization.py -v` for just the 8A-relevant subset.
Run the server locally (requires the `api` extra installed and
`GITHUB_TOKEN` in `.env` for real requests):
`uvicorn gitscore.api.app:app --reload`.

**Explicitly NOT done this milestone (per instruction):** repository
ranking, evidence extraction, job parsing, matching, and assessment/
scoring logic were not touched or duplicated — only exposed. No
frontend, no accounts/auth/OAuth, no persistence, no job-URL ingestion,
no LLM, no alternative-role discovery. No commit was made.

## 2026-10-03 — Milestone 7C: End-to-end job-analysis orchestration

**What changed:** First application-level operation that composes the
whole GitScore job-fit pipeline into one call. New package
`gitscore.application` (`job_fit.py`):
`analyze_job_fit(username, job_description, *, client=None, top_n=DEFAULT_TOP_N,
job_title=None, job_company=None) -> JobAnalysisResult`. No new analysis
logic, no new scoring semantics, no new domain schema — it calls
`extract_candidate_evidence()` (5D), `parse_job_description()` (6B),
`match_job()` (7A), and `assess_job()` (7B) each exactly once and
returns their outputs bundled together. Full as-built writeup:
`docs/ARCHITECTURE.md` §22. This entry summarizes.

**Architectural review first:** Milestone 5D's
`gitscore.pipeline.evidence.extract_candidate_evidence()` already
composed repository listing -> ranking -> bounded deep extraction ->
`CandidateEvidenceProfile` end-to-end. This milestone found it already
complete and REUSED it unchanged — no ranking/extraction logic was
duplicated into `gitscore.application`, and no existing schema
(`CandidateEvidenceProfile`, `JobRequirementProfile`,
`JobMatchAnalysis`, `JobAssessment`) needed a change to compose. No
architectural stop condition was hit; nothing in this milestone's §18
"stop before changing established schemas" list applied.

**Package boundary:** `gitscore.application` depends on
`gitscore.pipeline`, `gitscore.jobs`, `gitscore.matching`, and
`gitscore.assessment`; none of those import from `gitscore.application`
— this is the one layer allowed to know about all of them together.

**Output model — `JobAnalysisResult`:** `candidate_profile`,
`job_profile`, `assessment`, `extractor_failures`,
`unknown_dependency_names`. No separate `match_analysis` field —
reachable unchanged via `assessment.match_analysis`. `candidate_profile`/
`job_profile` ARE kept as their own fields because neither is fully
reachable from the match/assessment objects (`JobMatchAnalysis` retains
only `coverage` and `title`/`company`, not the full evidence/concept
summaries or the full requirements tuple/raw text) — see
`docs/ARCHITECTURE.md` §22.3.

**Dependency injection:** `client` is forwarded UNCHANGED to
`extract_candidate_evidence()`, which itself only constructs a real
`GitHubClient()` when `client is None`. `job_fit.py` never constructs a
network client itself, so tests inject the existing
`FakeEvidenceGitHubClient` test double and never touch the network.

**Execution order:** job parsing runs BEFORE GitHub retrieval — local,
deterministic, free, so a blank/rejected job description fails before
any GitHub request is made rather than after spending part of the
candidate's rate-limit budget on a request that was always going to be
discarded. Each of the four stages runs exactly once — no rematching to
build a convenience field (pinned by
`test_each_stage_runs_exactly_once`).

**Failure semantics — reused, not reinvented:** blank `username` raises
`ValueError` directly (nothing downstream validates it); blank
`job_description` raises `ValueError` via `JobRequirementProfile`'s own
existing invariant. Every GitHub-side exception
(`GitHubNotFoundError`/`GitHubRateLimitError`/`GitHubRequestError`) and
every partial per-repository extraction failure propagates or is
surfaced completely unchanged — no `except Exception` anywhere in
`job_fit.py`. Zero repositories, zero candidate evidence, a job
description parsing to zero requirements, and zero assessable
requirements are each a NORMAL successful result (the existing
components already degrade gracefully through empty collections,
verified directly rather than assumed) — never collapsed with a true
I/O failure. Confirmed the `alignment_score is None` ("nothing was
assessable") vs. `alignment_score == 0` ("assessed, nothing supported")
distinction survives orchestration in both directions.

**Determinism boundary:** `extract_candidate_evidence()` is the only
stage with GitHub I/O; `parse_job_description()`/`match_job()`/
`assess_job()` are pure. Pinned by
`test_identical_fake_github_responses_produce_identical_results`: two
independent calls with byte-identical fake GitHub responses and
identical job text produce `==`-equal results.

**Smoke path:** `scripts/analyze_job.py <username> <job_description_file>
[--top N]` — prints alignment score, required/preferred "X of Y
supported", repository coverage, and the supported/not-observed/
not-assessable groupings by original job-posting text. Inspection only,
no persistence.

**Real-account validation:** ran `scripts/analyze_job.py Jango1324
<ML posting>` against the project's own existing test account (used
previously for 5D's `inspect_evidence_profile.py` validation) with a
real `GITHUB_TOKEN`. 20 repositories discovered, 15 analyzed, zero
extractor failures, `alignment_score = 50` (`required = 2 of 3`,
`preferred = 0 of 1`). Not treated as scientific validation of the
score, per instruction.

**Versioning:** no schema/formula version introduced or bumped.
`JOB_REQUIREMENT_SCHEMA_VERSION`, `EVIDENCE_SCHEMA_VERSION`,
`CONCEPT_REGISTRY_VERSION`, `JOB_DESCRIPTION_PARSER_VERSION`,
`MATCHER_VERSION`, `SCORING_VERSION` are all read, never written, by
`gitscore.application` — pure composition.

**Tests:** 18 new, `tests/test_application_job_fit.py`, all offline via
`FakeEvidenceGitHubClient` (no network, no GitHub token): happy path;
orchestrated result equals direct `extract_candidate_evidence()` ->
`parse_job_description()` -> `match_job()` -> `assess_job()`
composition (score, required/preferred, and full `JobAssessment`
equality); supporting evidence and repository coverage survive
orchestration; OR-group and `NOT_ASSESSABLE` semantics survive
orchestration; blank username/job description; GitHub not-found/
rate-limit/request-error propagation; zero repositories; zero matching
evidence; zero-requirement job description; zero-assessable-requirement
job description; partial per-repository extraction failure is
surfaced, not fatal; determinism across identical fake responses; each
stage called exactly once. **746 tests total, all passing** (up from
728).

**Files changed:**
- `src/gitscore/application/__init__.py`, `job_fit.py` — new package.
- `scripts/analyze_job.py` — new smoke-path CLI.
- `tests/test_application_job_fit.py` — new.
- `docs/ARCHITECTURE.md` — new §22.
- `docs/PIPELINE.md` — new "Job-fit pipeline" and "End-to-end
  orchestration" sections.
- `docs/CHANGELOG_DEV.md` — this entry.

**How to test:** `python -m pytest` (whole suite, 746 tests, no
network/token required) or `python -m pytest
tests/test_application_job_fit.py -v` for just the 7C-relevant subset.
Real-account smoke path (requires `GITHUB_TOKEN` in `.env`):
`python scripts/analyze_job.py <username> <path-to-job-description.txt> --top 15`.

**Explicitly NOT done this milestone (per instruction):** repository
ranking, evidence extraction, job parsing, matching, and
assessment/scoring logic were not redesigned — only composed.
Alternative-role discovery, web API, frontend, LLM logic, persistence
of results, and a commit were all explicitly out of scope and not
done.

## 2026-10-01 — Milestone 7B: GitHub Evidence Alignment & structured assessment

**What changed:** First milestone to turn Milestone 7A's per-requirement
`SUPPORTED`/`NOT_OBSERVED`/`NOT_ASSESSABLE` verdicts into a single
human-facing number. New package `gitscore.assessment` (`types.py`,
`models.py`, `engine.py`): `assess_job(match_analysis) -> JobAssessment`
consumes an already-computed `JobMatchAnalysis` and derives "GitHub
Evidence Alignment" plus required/preferred submetrics and explanation
groupings — no rematching, no GitHub/network/LLM calls. Design approved
in `docs/design/MILESTONE_7B_SCORING_DESIGN.md` before any code was
written; full as-built writeup: `docs/ARCHITECTURE.md` §21. This entry
summarizes.

**GitHub Evidence Alignment — definition:** "Among the job requirements
GitHub evidence can meaningfully speak to, what percentage are supported
by evidence found in the candidate's analyzed GitHub material."

```
assessable_count = supported_count + not_observed_count
alignment_score  = None                                       if assessable_count == 0
alignment_score  = round_half_up(100 * supported_count / assessable_count)  otherwise
```

`NOT_ASSESSABLE` is excluded from the denominator entirely — the one
load-bearing rule this milestone exists to enforce, implemented in
exactly one place (`assessment/models.py`'s `_assessable_matches()`,
reused by every derived property) so there is no second, drifting
definition of "assessable."

**Rounding — half-up, not Python's `round()`:** Python's builtin
`round()` uses round-half-to-even (`round(62.5) == 62`,
`round(63.5) == 64`) — a parity-dependent flip with no product
justification for a human-facing percentage. `assessment/models.py`'s
`_round_half_up_percentage()` rounds ties up via pure integer arithmetic
(`(2*numerator*100 + denominator) // (2*denominator)`, the exact-integer
form of `floor(n/d + 0.5)`) — no floats anywhere in the computation.
Pinned by dedicated tests (62.5 -> 63, 72.5 -> 73).

**Required/Preferred — submetrics, never weights:** `Necessity` does not
weight `alignment_score`. `JobAssessment.required`/`.preferred` each
expose a `SubscoreFacts(supported, assessable)` — a plain "X of Y" count,
deliberately not a second percentage. `SubscoreFacts` rejects
`assessable < 1` by construction (a necessity tier with zero assessable
requirements is `None` on `JobAssessment`, never `SubscoreFacts(0, 0)` —
those are different facts). **No cap, no floor, no gate**: a candidate
with 0-of-2 REQUIRED supported and 6-of-6 PREFERRED supported gets
`alignment_score == 75`, uncapped — pinned exactly by
`test_adversarial_case_strong_headline_despite_zero_required_support`.
The "strong headline hides zero required coverage" problem is resolved
by making `required` a mandatory co-display fact for any future
presentation layer, never by silently discounting the number.

**Importance — read, never weighted:** remains available unchanged on
`RequirementMatch.requirement.importance`, never duplicated onto
`JobAssessment` or folded into the score. Rejected explicitly: `jobs/
parsing/importance.py`'s `infer_importance()` already defaults a
PREFERRED requirement to LOW unless an emphasis phrase overrides it —
`Importance` is a heuristic partially *derived from* `Necessity`, not an
independent axis, so weighting by both would compound one parser
heuristic's uncertainty twice.

**ParserConfidence — metadata only:** affects neither `alignment_score`
nor coverage. The only aggregate computed from it is
`JobAssessment.low_parser_confidence_count` — assessable requirements
only (`SUPPORTED`/`NOT_OBSERVED`) with `parser_confidence ==
ParserConfidence.LOW`; a `NOT_ASSESSABLE` requirement parsed with LOW
confidence does not count, and `parser_confidence is None` ("not
evaluated by any parser") is never counted as LOW.

**Evidence confidence — unchanged from 7A:** does not reopen
`matching/support.py`'s `MINIMUM_SUPPORTING_CONFIDENCE =
ConfidenceLevel.WEAK` policy. A `SUPPORTED` match counts as exactly one
supported assessable requirement regardless of WEAK/MODERATE/STRONG
evidence strength.

**Repository coverage — passed through unmodified:**
`JobAssessment.match_analysis.coverage` is 7A's own
`RepositoryAnalysisCoverage`, not duplicated, not turned into a
percentage (Milestone 5B's ranker prioritizes the highest-substantiveness
repositories first, so a raw ratio would understate true coverage and
claim false precision). **No `coverage_note` presentation string either**
— a correction made during the Milestone 7B.0 design review: rendering
coverage prose from the structured facts is a future UI/API layer's job,
not domain state.

**Explanation groupings:** `supported_matches()`/`not_observed_matches()`/
`not_assessable_matches()` delegate directly to
`JobMatchAnalysis.matches_with_status()` — no `RequirementMatch`/
`Evidence` copied or rebuilt, posting order preserved exactly. Locked
wording (documented, not stored as strings in the domain model):
"Supported by GitHub evidence" / "Not observed in analyzed GitHub
evidence" (never "lacks the skill") / "Not assessable from GitHub"
(never "failed it"). "Gaps" is deliberately not used anywhere.

**Versioning:** `SCORING_VERSION = "github_evidence_alignment:v1"`
(`assessment/types.py`) — new, independent. Does NOT bump
`JOB_REQUIREMENT_SCHEMA_VERSION`, `EVIDENCE_SCHEMA_VERSION`,
`CONCEPT_REGISTRY_VERSION`, `JOB_DESCRIPTION_PARSER_VERSION`, or
`MATCHER_VERSION` — purely additive; `JobMatchAnalysis` is consumed
exactly as Milestone 7A produces it. No `EXPLANATION_VERSION` introduced
(the explanation groupings ARE this package's scoring logic, not a
separate prose step yet).

**Tests:** 42 new — `tests/test_assessment_engine.py` (33: formula
correctness, `NOT_ASSESSABLE` denominator exclusion, `None`/0/100 scores,
half-up rounding vs. Python's `round()`, required/preferred
`SubscoreFacts` including the pinned adversarial 75-with-0-of-2-required
case, Necessity/Importance/ParserConfidence/evidence-confidence/coverage
independence from the score, `low_parser_confidence_count` scoping,
OR-group single-counting, unresolved-concept handling, grouping-helper
order/identity, purity of `assess_job()`, `SubscoreFacts`/`JobAssessment`
invariants, and a check that no prose/presentation field exists anywhere
on the domain object) and `tests/test_assessment_manual_examples.py` (9:
the same four real Backend/Robotics/ML/Data-Engineer postings from 7A's
manual validation, run through the REAL `parse_job_description()` and
`match_job()`, then `assess_job()`, confirming no rematching, no
weighting, no coverage percentage, and no hire/reject verdict anywhere
in the result). All deterministic, offline, no network calls. **728
tests total, all passing** (up from 686).

**Manual end-to-end validation:** ran all four real postings
(Backend/Robotics/ML/Data Engineer) through the full
parse -> match -> assess pipeline. Confirmed: the Backend posting splits
"3+ years of experience building Python backend services" into a
technical `language.python` requirement plus a non-technical
`NOT_ASSESSABLE` experience claim (6A's own splitting rule) — assessable
set of 5 (python/postgresql/docker/aws/next.js), 2 supported
(python/docker) -> `alignment_score == 40`, `required ==
SubscoreFacts(2, 3)`, `preferred == SubscoreFacts(0, 2)`. The ML
posting's "Docker or Kubernetes" OR group counts as exactly one
assessable requirement, supported via Docker alone. Repository coverage
facts (`discovered_count`/`analyzed_count`/`is_complete`) pass through
unmodified with no synthesized percentage anywhere.

**Files changed:**
- `src/gitscore/assessment/__init__.py`, `types.py`, `models.py`,
  `engine.py` — new package.
- `tests/test_assessment_engine.py`, `tests/test_assessment_manual_examples.py`
  — new.
- `docs/ARCHITECTURE.md` — new §21.
- `docs/design/MILESTONE_7B_SCORING_DESIGN.md` — new, the approved
  design report.
- `docs/CHANGELOG_DEV.md` — this entry.

**How to test:** `python -m pytest` (whole suite, 728 tests, no
network/token required) or `python -m pytest tests/test_assessment_engine.py
tests/test_assessment_manual_examples.py -v` for just the 7B-relevant
subset.

**Explicitly NOT done this milestone (per instruction):**
alternative-role discovery, role archetype ranking, CatBoost/learned
scoring, recruiter labels, hire/reject recommendations, persistence, API,
UI, LLM-generated explanation prose, job-posting URL ingestion. No
existing 7A matching semantics were changed. No commit was made.

## 2026-09-29 — Milestone 7A: Deterministic requirement matching engine

**What changed:** First milestone connecting `CandidateEvidenceProfile`
(Milestone 5C/5D) and `JobRequirementProfile` (Milestone 6A/6B/6B.1). New
package `gitscore.matching` (`types.py`, `support.py`, `models.py`,
`engine.py`) determines, per `JobRequirement`, what the candidate's
GitHub evidence says about it — `SUPPORTED` / `NOT_OBSERVED` /
`NOT_ASSESSABLE`. Full design writeup: `docs/ARCHITECTURE.md` §20. This
entry summarizes.

**Explicitly NOT implemented (per instruction):** overall 0-100 job-fit
score, weighted aggregation, strengths/gaps prose, hire/reject
conclusion, alternative-role discovery, persistence, API, UI, CatBoost,
LLM, job-posting URL ingestion. `JobMatchAnalysis` exposes only plain
descriptive counts (`supported_count`/`not_observed_count`/
`not_assessable_count`) — arithmetic a human could reproduce by hand,
not a weighting decision.

**MatchStatus — three states:** `SUPPORTED`, `NOT_OBSERVED`,
`NOT_ASSESSABLE`. `NOT_OBSERVED` means "no sufficient evidence found in
the ANALYZED GitHub evidence" — never "the candidate lacks this skill."
`NOT_ASSESSABLE` means "not the kind of claim GitHub evidence can speak
to" — never "the candidate failed this requirement."

**No `PARTIALLY_SUPPORTED`:** considered and rejected, not omitted.
`ConfidenceLevel` (WEAK/MODERATE/STRONG) answers "how sure are we this
observation is real," never candidate proficiency or "how much of a
requirement" is met — no principled, deterministic partial-support
reading exists in the current evidence model. For an alternative group,
"some but not all alternatives supported" is not partial support either
— Milestone 6B.1's OR semantics mean ANY one supported alternative
already fully satisfies the requirement (`matched_concept_ids` records
which ones, but `status` stays a plain `SUPPORTED`).

**Normal technical requirement:** looked up directly via
`CandidateEvidenceProfile.concept(concept_id)` — no fuzzy string
matching; the parser/registry already normalized every concept id on
both sides, including `unresolved:<term>` ids (matched by exact string
equality).

**Alternative group (`alternative_concept_ids`, 6B.1):** `SUPPORTED` if
ANY alternative has sufficient evidence (true OR — never requires all).
`matched_concept_ids` retains EVERY alternative that matched (not just
the first), stored sorted for determinism. Verified against the actual
ML manual-validation posting: a candidate with ONLY Docker evidence (no
Kubernetes evidence) against "Docker or Kubernetes" is `SUPPORTED` with
`matched_concept_ids == ("infra.docker",)` — never requires both.

**Non-observable requirements:** `github_observability ==
NOT_OBSERVABLE` -> always `NOT_ASSESSABLE`, regardless of any concept
mapping (defensive; the parser never actually attaches one, but the
domain model doesn't forbid it).

**`PARTIALLY_OBSERVABLE` — the one non-obvious rule, checked against
real fixtures, not assumed:** a `PARTIALLY_OBSERVABLE` requirement WITH
a real concept mapping (`concept_id` or `alternative_concept_ids`) is
matched exactly like `STRONGLY_OBSERVABLE`. Milestone 6A's own
hand-built manual examples already contain this combination — "AWS
experience preferred" (`concept_id="cloud.aws"`, `PARTIALLY_OBSERVABLE`)
and "Comfortable working in Linux environments"
(`concept_id="unresolved:linux"`, `PARTIALLY_OBSERVABLE`) — so
collapsing every `PARTIALLY_OBSERVABLE` requirement to `NOT_ASSESSABLE`
regardless of concept mapping would make real, checkable evidence
(a `boto3` dependency, a Dockerfile) permanently unmatchable, which is
LESS truthful, not the "smallest safe behavior." A `PARTIALLY_OBSERVABLE`
requirement with NO concept mapping (`category="leadership"` — "Experience
mentoring junior engineers" in the actual ML posting — or the 6B.1
"unsafe" alternative-group fallback) IS `NOT_ASSESSABLE`: there is no
structured evidence surface to check at all, so `NOT_ASSESSABLE` is
truthful there, not a discount on `SUPPORTED`/`NOT_OBSERVED`.

**Evidence-sufficiency policy (`matching/support.py`):**
`MINIMUM_SUPPORTING_CONFIDENCE = ConfidenceLevel.WEAK` — ANY qualifying
Evidence, any confidence tier, is sufficient. A considered decision, not
an assumption: every extractor already applies its OWN significance
filter before producing Evidence at all (`languages.py`'s 5%-of-bytes
floor is the clearest example) — WEAK evidence is "genuinely present,
just not the dominant signal," not "maybe not real." A stricter floor
would silently re-apply a second, undocumented significance bar on top
of each extractor's own, and — with no `PARTIALLY_SUPPORTED` status —
would misrepresent "observed, but weakly" as "not observed at all."
Centralized as one named, testable constant so it can be tightened later
without redesigning the matcher.

**Coverage handling:** `JobMatchAnalysis.coverage` holds the candidate's
`RepositoryAnalysisCoverage`, copied by reference in ONE place (not
duplicated onto every `RequirementMatch` — that would be pure
duplication with no new information per match, mirroring how
`CandidateEvidenceProfile` itself keeps coverage once, not per
`Evidence`). No coverage percentage or score computed — only the
existing `discovered_count`/`analyzed_count`/`is_complete` facts,
unchanged; deriving a calibrated number from them is Milestone 7B's job.

**Necessity/Importance/ParserConfidence independence:** none of the
three affect matching status — `RequirementMatch.requirement` retains
them unchanged for 7B to read later, but REQUIRED vs. PREFERRED, HIGH
vs. LOW importance, and LOW vs. HIGH parser confidence with identical
candidate evidence always produce the identical `status`. Verified by
dedicated tests.

**Whole-profile entry point:** `match_job(candidate_profile, job_profile)
-> JobMatchAnalysis`, one `RequirementMatch` per requirement, in
`job_profile.requirements`' own order (never re-sorted — that order is
meaningful posting order).

**Versioning:** `MATCHER_VERSION = "requirement_matcher:v1"`
(`matching/types.py`) — a new, independent constant. Does NOT bump
`JOB_REQUIREMENT_SCHEMA_VERSION`, `EVIDENCE_SCHEMA_VERSION`,
`CONCEPT_REGISTRY_VERSION`, or `JOB_DESCRIPTION_PARSER_VERSION` — purely
additive; `JobRequirement` and `CandidateEvidenceProfile` are consumed
exactly as-is, unmodified.

**Tests:** 48 new — `tests/test_matching_engine.py` (42: normal/
alternative-group matching A-U from the milestone brief, invariants on
`RequirementMatch`/`JobMatchAnalysis`, threshold/coverage/ordering
behavior) and `tests/test_matching_manual_examples.py` (6: the real
Backend/Robotics/ML/Data-Engineer postings, parsed with the real
`parse_job_description()`, matched against several deliberately mixed
hand-built candidate profiles). All deterministic, offline, no network
calls. **686 tests total, all passing** (up from 638).

**Manual validation:** see `docs/ARCHITECTURE.md` §20.6 for the full
write-up — no false AND for OR groups, non-observable claims never
became technical gaps, every `SUPPORTED` match traced to real
attributable Evidence, and no score/coverage-percentage/hire-reject
conclusion was computed anywhere.

**Files changed:**
- `src/gitscore/matching/__init__.py`, `types.py`, `support.py`,
  `models.py`, `engine.py` — new package.
- `tests/test_matching_engine.py`, `tests/test_matching_manual_examples.py`
  — new.
- `docs/ARCHITECTURE.md` — new §20.
- `docs/CHANGELOG_DEV.md` — this entry.

**How to test:** `python -m pytest` (whole suite, 686 tests, no
network/token required) or `python -m pytest tests/test_matching_engine.py
tests/test_matching_manual_examples.py -v` for just the 7A-relevant
subset.

**Explicitly NOT done this milestone (per instruction):** job-fit score,
weighted aggregation, strengths/gaps, alternative-role discovery, LLM,
URL ingestion, persistence, UI, CatBoost, Milestone 7B. No commit was
made.

## 2026-09-28 — Milestone 6B.1: Structured alternative requirements

**What changed:** Corrects Milestone 6B's OR-handling before that
milestone was committed. 6B's OR-handling stop condition was presented
as an explicit A/B choice; it was implemented as Option A (a text-only,
non-technical placeholder) following a selection misunderstanding — the
intended choice was **Option B: a minimal additive schema extension**.
This milestone implements Option B: `JobRequirement` gained
`alternative_concept_ids: tuple[str, ...] = ()`, and the parser now
represents "Python or Go" as ONE requirement with structured semantics
(`supported(Python) OR supported(Go)`) instead of a placeholder the
matcher would have had to re-parse `original_text` to interpret. Full
design writeup: `docs/ARCHITECTURE.md` §19 (new); §18.7/§18.8/§18.10/
§18.11 updated in place to describe the corrected, final behavior. This
entry summarizes.

**Schema extension chosen:** `JobRequirement.alternative_concept_ids:
tuple[str, ...] = ()` (`jobs/models.py`) — the exact shape the 6B report
had already flagged as the smallest additive option, confirmed on
inspection to remain the cleanest design (no cleaner alternative was
found; a `RequirementGroup` wrapper object was considered and rejected
as unnecessary structural weight for what one additive tuple field
already expresses). Mutually exclusive with `concept_id` (never both
populated); requires >= 2 entries (a one-element "alternative" is
meaningless — use `concept_id`); rejects duplicates; each entry
validated with the SAME `concepts.registry.is_valid_concept_id()` 6A.1
introduced (no second, duplicated concept-id validation rule). The
stored tuple is SORTED at construction (`__post_init__`), not kept in
whatever order the caller passed — "Python or Go" and "Go or Python" are
the same logical requirement, so canonicalizing the order makes the two
phrasings compare/hash equal automatically, which is what lets
`dedup.py` and `JobRequirementProfile`'s existing exact-duplicate
rejection (Milestone 6A) treat them as identical for free, with no
set-vs-tuple special-casing anywhere.

**How "Python or Go" is represented:** ONE `JobRequirement`,
`concept_id=None`, `alternative_concept_ids=("language.go",
"language.python")`, necessity/importance/observability/confidence
computed for the GROUP as a whole from the full claim text (never
per-alternative) — never two independent `REQUIRED` rows.

**How "Python and PostgreSQL" is represented:** unchanged from 6B — two
independent `JobRequirement` rows, `concept_id="language.python"` and
`concept_id="database.postgresql"`, both `REQUIRED`. Conjunction and
alternation remain explicitly different representations; nothing about
AND-list handling changed in this milestone.

**Mixed/unknown alternatives:** `alternatives.py`'s `classify_alternative_claim()`
resolves each OR-segment in two steps — `find_concept_mentions()`
(prose-safe aliases, same as everywhere else) first, then, only if that
finds nothing, a narrower escalation: clean the segment to its core term
and try `resolve_concept()` against the FULL alias set. This escalation
is deliberate and bounded — a segment produced by splitting a CONFIRMED
"X or Y" enumeration (at least one sibling already resolved) is closer
to an isolated, structured token than to arbitrary free prose, which is
exactly the context Milestone 5D.1's alias-safety restriction was never
meant to constrain. It's what lets `"Go"` in `"Python or Go"` resolve to
the real `language.go` (bare `"go"` is `readme_unsafe` for prose
scanning; this isn't prose scanning) instead of an needless
`unresolved:go`. A segment resolving neither way falls to the SAME
conservative shape/stopword check `find_conservative_unknown_terms`
already uses (Milestone 6B) — passes -> `unresolved:<term>` (e.g.
`"AWS or Azure"` -> `("cloud.aws", "unresolved:azure")`); fails -> the
whole claim is marked `"unsafe"` and falls back to the OLD 6B
placeholder rather than dropping an option or inventing a reckless id
(e.g. `"Python or a genuinely amazing attitude"`).

**Non-technical "or" is no longer swept into a fake technical bucket:**
an OR-list with NO confirmed registered concept anywhere in it (e.g.
"Bachelor's degree in Computer Science or related field", "3+ years
experience or equivalent education") is now classified `"not_technical"`
and runs through the exact same pipeline as any other claim — these two
examples now correctly land in `education`/`experience` categories
(confirmed in the re-run manual validation, `docs/ARCHITECTURE.md`
§18.11), instead of 6B's blanket "any 'or' is alternative-shaped" rule.
No role-specific logic and no giant special-phrase list were added — one
general rule (does the OR-list contain a confirmed technical concept
anywhere?), applied uniformly.

**Necessity/importance/observability for a group:** computed once from
the full claim text, exactly as for any other claim — an alternative
group is ONE logical requirement. "Python or Go required" ->
`REQUIRED`. "CUDA or ROCm preferred" -> `PREFERRED`. Observability
reuses the existing `STRONGLY_OBSERVABLE` technical default unmodified
— every id in a group is either a real registered concept or a
conservatively-promoted `unresolved:<term>`, the same two shapes a
normal technical requirement can have.

**Deduplication:** a REAL BUG was found and fixed while implementing
this. `is_technical` is `True` for both a normal technical requirement
and an alternative group, but `concept_id` is `None` for the group case
— the OLD dedup key (`("technical", concept_id, necessity)`) would have
collapsed EVERY alternative group sharing a necessity into ONE, losing
distinct groups like "Python or Go" and "AWS or Azure" entirely. Fixed
by adding a dedicated key, checked first:
`("technical_alternative", alternative_concept_ids, necessity)`. Because
`alternative_concept_ids` is stored sorted, "Python or Go" and "Go or
Python" collapse to one (same logical requirement, correctly); "Python
or Go" and "AWS or Azure" do not (different requirements, correctly).
Caught by this milestone's own new tests, not by inspection alone.

**Provenance:** unchanged in mechanism — the group's `original_text`/
`source_span` is still the FULL original claim, exact and unmodified
(Milestone 6A's `SourceSpan`). No fake reconstructed per-alternative
spans are created; there is no representation for "where inside the
claim did alternative #2 appear" — the group's span covers the whole
claim, matching how a compound AND-claim's multiple requirements already
share one span (Milestone 6B).

**Versioning:**
- `JOB_REQUIREMENT_SCHEMA_VERSION` 1 -> 2 — `JobRequirement` gained a
  field, a genuine shape change per `jobs/types.py`'s own bump policy.
- `JOB_DESCRIPTION_PARSER_VERSION` `"job_description_parser:v1"` ->
  `"...v2"` — the parser's emitted semantics for OR-claims changed
  materially, mirroring the `readme:v1` -> `readme:v2` precedent
  (Milestone 5D.1: a behavior change bumps the extractor/parser's OWN
  version, independent of the domain-model schema version).
- `CONCEPT_REGISTRY_VERSION`, `EVIDENCE_SCHEMA_VERSION`,
  `REPOSITORY_RANKING_VERSION`, `SCORING_RUBRIC_VERSION`,
  `DATASET_VERSION` untouched.

**Tests:** 41 new/changed — `tests/test_job_requirement_models.py` (17
new: the three valid states, canonicalized ordering, mixed resolved/
unresolved, mutual-exclusivity and every other invariant, reuse of the
6A.1 concept-id validator), `tests/test_job_requirement_profile.py` (1
new: reordered-alternatives-are-an-exact-duplicate; 1 changed: the
`JOB_REQUIREMENT_SCHEMA_VERSION` pin), `tests/test_job_parser_extraction.py`
(19 new for `classify_alternative_claim()`, 4 new for the dedup fix),
`tests/test_job_parser.py` (4 tests rewritten from Option-A to Option-B
expectations, 2 manual-validation fixtures updated for the corrected
non-technical-"or" boundary). All deterministic, offline, no network
calls. **638 tests total, all passing** (up from 597; every V1/5B/5C/
5D/5D.1/6A/6A.1 test, and every 6B test not describing Option-A-specific
behavior, untouched and still green).

**Manual validation re-run:** all four Milestone 6B fixtures (Backend,
Robotics, ML, Data Engineer) re-run against the corrected parser.
Confirmed improvements: "Bachelor's degree ... or a related field"
(Robotics) and "3+ years of experience ... or a related field" (Data
Engineer) now correctly categorize as `education`/`experience` instead
of the generic `alternative_requirement` bucket; "Docker or Kubernetes"
and "AWS or Azure" (ML) now carry real `alternative_concept_ids` instead
of an opaque placeholder. New accepted limitation: "Snowflake or
BigQuery" (Data Engineer, neither alternative is a registered concept)
and "control systems or robotics" (Robotics, same reason) now produce
nothing at all — the OR-list analog of the existing "needs a confirmed
anchor" rule for comma-lists, applied consistently rather than carved
out as a special case.

**Files changed:**
- `src/gitscore/jobs/models.py` — `alternative_concept_ids` field,
  updated invariants, `is_alternative_group`/`has_unresolved_alternative`
  properties, `is_technical` extended.
- `src/gitscore/jobs/types.py` — `JOB_REQUIREMENT_SCHEMA_VERSION` 1 -> 2.
- `src/gitscore/jobs/parsing/concepts.py` — `clean_list_fragment()`/
  `GENERIC_LIST_STOPWORDS` promoted to public, shared with
  `alternatives.py` (no duplicated shape-check logic).
- `src/gitscore/jobs/parsing/alternatives.py` — rewritten:
  `classify_alternative_claim()` (three-outcome classification) replaces
  the old blanket marker-only detection; `contains_alternative_marker()`
  kept (still used internally).
- `src/gitscore/jobs/parsing/dedup.py` — alternative-group dedup key
  (the bug fix above).
- `src/gitscore/jobs/parsing/parser.py` — orchestrates the three
  `classify_alternative_claim()` outcomes; `JOB_DESCRIPTION_PARSER_VERSION`
  v1 -> v2.
- `tests/test_job_requirement_models.py`, `test_job_requirement_profile.py`,
  `test_job_parser_extraction.py`, `test_job_parser.py` — see Tests above.
- `docs/ARCHITECTURE.md` — new §19; §17.2/§18.1/§18.7/§18.8/§18.10/
  §18.11 updated in place to describe the corrected design.
- `docs/CHANGELOG_DEV.md` — Milestone 6B's entry amended (Option A no
  longer described as the approved final design) plus this entry.

**How to test:** `pytest` (whole suite, 638 tests, no network/token
required) or `pytest tests/test_job_requirement_models.py
tests/test_job_requirement_profile.py tests/test_job_parser_extraction.py
tests/test_job_parser.py -v` for just the 6B/6B.1-relevant subset.

**Explicitly NOT done this milestone (per instruction):** matcher,
match score, evidence coverage, strengths/gaps, alternative-role
discovery, LLM, URL ingestion, persistence, UI, CatBoost, Milestone 7.
No commit was made.

## 2026-09-28 — Milestone 6B: Job-description parser

**What changed:** A new subpackage, `src/gitscore/jobs/parsing/`,
implementing `parse_job_description(description, *, title=None,
company=None) -> JobRequirementProfile` — the first automatic parser
turning raw job-description text into Milestone 6A's EXACT, unchanged
domain model. No matcher, no scoring, no candidate/job comparison, no
URL ingestion, no external LLM/API, no persistence. Full design
writeup: `docs/ARCHITECTURE.md` §18 (new). This entry summarizes.

**Why:** 6A/6A.1 defined the job-side domain model in isolation
(mirroring how 5C defined the candidate-side model before 5D wired real
extraction into it); this milestone is the first to actually populate it
from real text.

**Architecture decision (Part 1's evaluation, required before writing
any code):** deterministic, rule-based (Option A), not LLM-assisted.
Arbitrary-role support does not require language understanding of what
a role IS — it requires an open concept vocabulary (already solved:
`concepts.registry` + `unresolved:<term>`) plus conservative, generic
heuristics for document structure and claim shape, none of it
role-specific. No external AI dependency was introduced without
approval. See §18.1 for the full A/B/C evaluation and the documented
boundary where a future LLM claim-extraction adapter could plug in
without changing anything downstream.

**IMPORTANT STOP CONDITION presented before implementing that piece:**
`JobRequirement.concept_id` is a single scalar — it cannot represent
"this ONE requirement is satisfied by ANY of {Python, Go}" without a
schema change. Presented as an explicit A/B choice (Option A: no schema
change, one conservative non-technical fallback claim; Option B:
additive `alternative_concept_ids` field). This milestone initially
implemented Option A following a selection misunderstanding — the
user's intended choice was Option B. **Corrected in Milestone 6B.1
(below, same day, before this milestone was committed):** an
alternative/OR-shaped claim ("Python or Go", "AWS or Azure") is
represented with structured `alternative_concept_ids`, not a text-only
placeholder. See the Milestone 6B.1 entry for the final design; this
entry is left otherwise unchanged as the historical record of what was
originally built.

**Pipeline (new modules under `jobs/parsing/`):**

| Module | Role |
|---|---|
| `segmentation.py` | Part 3: raw text -> `Claim` (exact text + offsets + section-derived necessity hint), via a generic JD section-heading table (Requirements/Preferred/Responsibilities/skip-sections) + bullet/sentence splitting |
| `concepts.py` | Parts 5/6: known-concept mentions via the EXISTING registry; conservative `unresolved:<term>` promotion (comma-list-co-occurrence gated) |
| `alternatives.py` | Part 14: OR-shaped claim detection (the correctness gate above) |
| `experience.py` | Part 15: numeric years-of-experience qualifier detection |
| `non_technical.py` | Part 10: curated, generic (never role-specific) non-technical phrase table — education/legal/leadership/soft-skill |
| `necessity.py` | Part 7: local wording overrides section hint; REQUIRED wins on conflict |
| `importance.py` | Part 8: MEDIUM default, small HIGH/LOW keyword overrides, no floats |
| `observability.py` | Part 9: two centralized dict lookups (technical category -> always STRONGLY_OBSERVABLE today; non-technical category -> table), never scattered `if concept ==` |
| `confidence.py` | Part 12: one small mapping by extraction "kind" |
| `dedup.py` | Part 13: technical dedup key `(concept_id, necessity)`; non-technical key adds normalized text so different experience claims never merge |
| `parser.py` | orchestrates all of the above; `JOB_DESCRIPTION_PARSER_VERSION = "job_description_parser:v1"` |

**Alias safety (Part 6) reuses, does not fork, Milestone 5D.1's
mechanism:** job-description prose is treated as the SAME free-form-text
risk class README prose is, so `find_concept_mentions()` scans
`concept.readme_safe_aliases()` — the identical per-concept safe-alias
set `readme.py` uses. The shared boundary-regex primitive itself was
extracted from `evidence/extraction/readme.py` into a new
`concepts/matching.py::alias_pattern()` (pure refactor, confirmed
zero behavior change: `test_evidence_extraction_readme.py` unchanged and
still green) so both callers share identical matching mechanics, not
just identical data. No job-specific alias-safety table was needed — no
job-description-only false positive distinct from README's was observed
in manual validation.

**Two real false positives found in manual validation, fixed before this
entry was written:** `"Build and maintain ETL pipelines using Python"`
was promoting `"Build"` to `unresolved:build`; `"Proficiency in Python
for tooling and scripting"` was promoting `"scripting"` similarly. Root
cause: the conservative unknown-term list-splitter fired on any bare
`"X and Y"`, and a bare "and" (no comma) is far more often a verb phrase
than a technology list. Fixed by requiring an actual comma in the claim
text before the list-scan runs at all — both now have dedicated
regression tests.

**Versioning:** `JOB_DESCRIPTION_PARSER_VERSION = "job_description_parser:v1"`
(new, `jobs/parsing/parser.py`) — the value stamped into
`JobRequirementProfile.parser_version`, an EXISTING field (Milestone 6A),
so no schema change was needed to introduce it.
`JOB_REQUIREMENT_SCHEMA_VERSION` stays `1` (confirmed: `git diff` shows
zero changes to `jobs/models.py`/`jobs/profile.py`/`jobs/types.py`).
`CONCEPT_REGISTRY_VERSION` stays `3` (no concept added/renamed; the new
`concepts/matching.py` is a pure code refactor, not a registry content
change). `EVIDENCE_SCHEMA_VERSION`, `REPOSITORY_RANKING_VERSION`,
`SCORING_RUBRIC_VERSION`, `DATASET_VERSION` untouched.

**Manual real-world validation (Part 19):** four hand-written, local job
descriptions (no scraping) — Backend Software Engineer, Robotics
Software Engineer, ML Engineer, and Data Engineer (the required
"substantially different fourth role") — full results in
`docs/ARCHITECTURE.md` §18.11, locked in as regression tests in
`tests/test_job_parser.py`'s `test_manual_validation_*`. All known
concepts resolved correctly; every `or`-shaped claim across all four
produced exactly one non-technical fallback and zero false
REQUIRED-technical rows; the Backend example's `Benefits:` section
(including a "React JS meetups" line) correctly produced zero
requirements, proving `framework.react` was never triggered by
marketing copy. Known accepted false negatives (documented, not fixed):
a standalone "Kubernetes"/"dbt" bullet with no co-occurring known
concept in the same claim produces nothing; "SQL" (not yet a registry
concept) inside a comma-less phrase is not recovered.

*(This paragraph describes the original Option A run. The
`alternative_requirement`-bucket side effect on non-technical "or"
phrasing it originally reported was ITSELF fixed by Milestone 6B.1's
structured-alternative correction, which added real evidence-based
classification instead of a blanket "any 'or'" rule — see that entry.)*

**Tests:** 113 new — `tests/test_concepts_matching.py` (4, the extracted
shared primitive), `tests/test_job_parser_segmentation.py` (17),
`tests/test_job_parser_extraction.py` (56, one file per pure function
module), `tests/test_job_parser.py` (36: input validation, provenance/
span-correctness, compound requirements, alternatives, non-technical,
unknown-tech policy, alias-safety regression, the four manual-validation
fixtures, and a 6A/6A.1 regression check). All deterministic, offline,
no network calls. **597 tests total, all passing** (up from 484; every
V1/5B/5C/5D/5D.1/6A/6A.1 test untouched and still green).

**Files changed:**
- `src/gitscore/concepts/matching.py` — new: `alias_pattern()`, extracted
  from `evidence/extraction/readme.py`.
- `src/gitscore/evidence/extraction/readme.py` — uses the extracted
  helper instead of its own private copy; no behavior change.
- `src/gitscore/jobs/parsing/__init__.py`, `segmentation.py`,
  `concepts.py`, `alternatives.py`, `experience.py`, `non_technical.py`,
  `necessity.py`, `importance.py`, `observability.py`, `confidence.py`,
  `dedup.py`, `parser.py` — new package.
- `src/gitscore/jobs/__init__.py` — exports `parse_job_description`,
  `JOB_DESCRIPTION_PARSER_VERSION`.
- `tests/test_concepts_matching.py`, `test_job_parser_segmentation.py`,
  `test_job_parser_extraction.py`, `test_job_parser.py` — new.
- `docs/ARCHITECTURE.md` — new §18; §17.10 amended with a forward
  pointer.
- This changelog entry.

**How to test:** `pytest` (whole suite, 597 tests, no network/token
required) or `pytest tests/test_concepts_matching.py
tests/test_job_parser_segmentation.py tests/test_job_parser_extraction.py
tests/test_job_parser.py -v` for just the 6B-relevant subset.

**Explicitly NOT done this milestone (per instruction — wait for
approval before starting):** deterministic matcher, match/coverage
score, strengths/gaps, alternative-role discovery, role archetypes, URL
ingestion, LinkedIn/Indeed/Glassdoor scraping, external LLM API,
CatBoost, UI, database persistence, any change to candidate evidence
extraction, Milestone 7. No commit was made — see Milestone 6B.1 for the
OR-handling correction applied before this milestone was committed.

## 2026-09-28 — Milestone 6A.1: Concept-id invariant review

**What changed:** A tiny correctness fix, not a redesign. Milestone 6A's
`JobRequirement.__post_init__` only checked that a non-`None`
`concept_id` was a non-empty string — `JobRequirement(...,
concept_id="whatever.random.string")` constructed without error, and
`is_resolved_concept` reported `True` for it, silently treating an
arbitrary, never-registered string as if it were a real concept.

**Fix:** one new function, `is_valid_concept_id(concept_id,
registry=None) -> bool` in `concepts/registry.py` (exported from
`gitscore.concepts`) — pure VALIDATION of an already-produced id, never
RESOLUTION: it returns `True` only if `concept_id` is (a) a real,
registered `TechnicalConcept.concept_id`, or (b) exactly what
`unresolved_concept_id()` would re-produce for its own suffix (checked
by calling that SAME existing function again, not by inventing a second
unresolved-id grammar). `is_valid_concept_id("Postgres")` is `False` even
though `resolve_concept("Postgres")` succeeds — the two answer different
questions. `JobRequirement.__post_init__` (`jobs/models.py`) now calls
this helper in place of the old bare non-empty-string check.

**Dependency direction unchanged:** `gitscore.jobs` still only ever
imports FROM `gitscore.concepts`, never the reverse; `gitscore.concepts`
still knows nothing about jobs; no circular import; the registry is
still never mutated; `JobRequirement` still never calls
`resolve_concept()` or performs any fuzzy/automatic conversion of an
unknown id — it only validates a string a caller already produced.

**The three intended states, now actually enforced:**
1. `concept_id=None` — non-conceptual requirement. Valid.
2. `concept_id` = a real registered `TechnicalConcept.concept_id` (e.g.
   `"database.postgresql"`). Valid.
3. `concept_id` = a well-formed `"unresolved:<term>"` id (e.g.
   `"unresolved:warp-level_primitives"`). Valid.
4. Anything else (`""`, whitespace, `"unresolved:"`,
   `"unresolved:   "`, `"garbage"`, `"language.does_not_exist"`,
   `"whatever.random.string"`, or a raw un-resolved human term like
   `"Postgres"`) — now rejected with `ValueError` at construction time,
   previously silently accepted.

**Versioning:** `JOB_REQUIREMENT_SCHEMA_VERSION` stays `1` — no field
added/removed/retyped on `JobRequirement`/`JobRequirementProfile`, only
tightened validation of an existing field. `CONCEPT_REGISTRY_VERSION`
stays `3` — no concept added/renamed/merged, no alias-safety or
normalization change; a new pure helper function is not a registry
content change under that constant's documented bump policy.
`EVIDENCE_SCHEMA_VERSION`, `REPOSITORY_RANKING_VERSION`,
`SCORING_RUBRIC_VERSION`, `DATASET_VERSION` untouched.

**Tests:** 7 new tests in `tests/test_technical_concepts.py`
(`is_valid_concept_id`: registered id, well-formed unresolved id,
malformed unresolved id, arbitrary nonexistent canonical-looking id,
empty/whitespace/padded string, never-resolves-a-raw-term, explicit
custom registry). 10 new tests in `tests/test_job_requirement_models.py`
covering the three valid states plus every invalid state listed above,
plus two regression tests confirming the existing Postgres/PyTorch
resolution examples and the compound-requirement (Python +
professional-experience) example are unchanged. **484 tests total, all
passing** (up from 467; every prior test, including all of 6A's manual
job examples, untouched and still green).

**Files changed:**
- `src/gitscore/concepts/registry.py` — new `is_valid_concept_id()`.
- `src/gitscore/concepts/__init__.py` — exports it.
- `src/gitscore/jobs/models.py` — `JobRequirement.__post_init__` uses it;
  docstring addendum.
- `tests/test_technical_concepts.py`, `tests/test_job_requirement_models.py`
  — new tests.
- `docs/ARCHITECTURE.md` — §17.3 addendum.
- This changelog entry.

**How to test:** `pytest` (whole suite, 484 tests, no network/token
required) or `pytest tests/test_technical_concepts.py
tests/test_job_requirement_models.py -v` for just the 6A.1-relevant
subset.

**Explicitly NOT done (per instruction):** no parser, no matcher, no
scoring, no job ingestion, no LLM, no URL ingestion, no persistence, no
new concept ontology, no new `JobRequirement`/`JobRequirementProfile`
field, no redesign of any 6A object. No commit was made.

## 2026-09-28 — Milestone 6A: Job requirement domain model

**What changed:** A new package, `src/gitscore/jobs/`, defining the
job-side structured representation that will eventually sit opposite
`CandidateEvidenceProfile`:

```
CandidateEvidenceProfile  +  JobRequirementProfile  -> (future) deterministic matcher
```

**Domain model only.** No job-description parser (regex or LLM-based),
no deterministic matcher, no scoring, no URL/job-board ingestion, no
persistence, and no change of any kind to candidate-evidence extraction,
the concept registry's data, repository ranking, or V1 scoring/dataset.
Full design writeup: `docs/ARCHITECTURE.md` §17 (new). This entry
summarizes.

**Why:** `docs/design/MILESTONE_5A_JOB_MATCHING_DESIGN.md` established
the two-sided architecture (Part 9) but was never implemented; Milestones
5B-5D.1 built out the candidate side only. This milestone builds the
missing job side, in isolation, so its shape can be validated before any
parser or matcher is built against it — mirroring exactly how Milestone
5C built the candidate-side domain model before Milestone 5D wired real
extraction into it.

**Domain objects introduced:**

| Object | Module | Role |
|---|---|---|
| `SourceSpan` | `jobs/models.py` | `(start, end)` character offsets into a `JobRequirementProfile.raw_text` — provenance, not automatic span extraction |
| `JobRequirement` | `jobs/models.py` | one indivisible claim from a job posting: original text, optional resolved concept, category, necessity, importance, GitHub observability, optional parser confidence, optional source span |
| `Necessity` | `jobs/types.py` | `REQUIRED` \| `PREFERRED` (plain enum, no ordering) |
| `Importance` | `jobs/types.py` | ordinal `LOW` < `MEDIUM` < `HIGH` — how much this requirement matters, independent of necessity |
| `GithubObservability` | `jobs/types.py` | ordinal `NOT_OBSERVABLE` < `PARTIALLY_OBSERVABLE` < `STRONGLY_OBSERVABLE` — can GitHub evidence plausibly speak to this KIND of claim at all |
| `ParserConfidence` | `jobs/types.py` | ordinal `LOW`/`MEDIUM`/`HIGH`, optional — how sure a future parser was it read the job text correctly; deliberately NOT `evidence.types.ConfidenceLevel` reused (see below) |
| `JobRequirementProfile` | `jobs/profile.py` | one job posting: title/company (informational only), raw text, requirements tuple, parser/schema version |

**Concept-driven, never role-driven:** nothing in `src/gitscore/jobs/`
branches on a role name, and there is no finite role enum anywhere.
`JobRequirement` is keyed by `concept_id`, resolved through the EXACT
SAME `gitscore.concepts.registry.resolve_concept()` every candidate-side
extractor already uses (Milestone 5D Part 11's "no second package-name
table" precedent, applied again here: no second job-requirement-to-
concept table either). An unanticipated technology in a job posting
resolves via the SAME `"unresolved:<term>"` policy `Evidence` already
uses (Milestone 5C Part 3) — never dropped, never silently promoted into
a new canonical concept, never written into the registry. This
supersedes the original 5A design draft's separate, never-implemented
`"provisional:<slug>"` proposal (one unresolved-id convention across the
whole codebase, not two).

**The one-claim-per-JobRequirement rule** is the direct fix for this
milestone's central warning example: "3+ years of experience building
Python backend services" must produce TWO `JobRequirement` rows (one
technical, `concept_id="language.python"`,
`github_observability=STRONGLY_OBSERVABLE`; one non-technical,
`concept_id=None`, `github_observability=NOT_OBSERVABLE`), never one row
asserting both a GitHub-observable concept and a non-observable
experience claim together. Non-technical requirements ("Bachelor's
degree," "excellent communication," "eligible to work in Canada") are
represented with `concept_id=None` and a free-form `category` string —
never with an invented `TechnicalConcept` id like `skill.communication`.

**Necessity, importance, and GitHub observability are three independent
axes**, not one combined field — narrower than the 5A draft's four-state
`requirement_type`, per this milestone's explicit "do not invent
excessive granularity" instruction. A job can require both Git (`LOW`
importance) and Python (`HIGH` importance) — both `REQUIRED`, weighted
very differently.

**Parser confidence is a genuinely separate type from evidence
confidence** — `ParserConfidence` was added as its own small `IntEnum`
rather than reusing `ConfidenceLevel`, because the two answer different
questions (how sure we are a job-text interpretation is correct, vs. how
sure we are a candidate-side GitHub observation is real); reusing one
enum for both would blur a job-parsing uncertainty into what would read
as a claim about a candidate's GitHub activity.

**`JobRequirementProfile` is candidate-independent by construction** —
no candidate/username, no `Evidence`, no match score, no coverage score,
no strengths/gaps, no repository references, no alternative roles. Pinned
by `test_job_requirement_profile.py::test_profile_has_no_candidate_or_match_fields`,
the direct counterpart to Milestone 5C's
`test_profile_has_no_job_related_fields`.

**Two deliberate policy differences from `CandidateEvidenceProfile`**
(both documented in `jobs/profile.py` so neither reads as an
inconsistency): (1) exact structural duplicate requirements are
REJECTED (`ValueError`), not silently deduplicated like Evidence —
Evidence's silent dedup exists for a corroboration model (the same real
fact re-observed); a job posting's requirements have no equivalent
legitimate source for an exact duplicate, so one is treated as a
construction bug. (2) `requirements` preserves the EXACT given order,
never canonically re-sorted like `Evidence` — a posting's requirement
order can itself be informative (earlier = often more prominent),
unlike an evidence pool's order, which carries no meaning.

**Versioning:** `JOB_REQUIREMENT_SCHEMA_VERSION = 1` (`jobs/types.py`),
a new, fully independent constant. `EVIDENCE_SCHEMA_VERSION`,
`CONCEPT_REGISTRY_VERSION`, `REPOSITORY_RANKING_VERSION`,
`SCORING_RUBRIC_VERSION`, and `DATASET_VERSION` are all untouched —
nothing in this milestone meets any of their bump conditions. Bumps when
`JobRequirement`/`JobRequirementProfile` change SHAPE; does NOT bump for
a new enum member (additive), mirroring `EVIDENCE_SCHEMA_VERSION`'s own
policy.

**Manual examples (Part 12):** `tests/test_job_requirement_manual_examples.py`
hand-builds full `JobRequirementProfile`s for a Backend Software
Engineer, a Robotics Software Engineer, and a Machine Learning Engineer
— deliberately near-zero requirement overlap, no automated parsing, no
candidate scored against any of them. All three fit the exact same
`JobRequirementProfile`/`JobRequirement` shape; `language.python` appears
in all three at different `Importance` levels; the robotics example's
"Linux" resolves via the same `unresolved:<term>` path an unrecognized
GitHub language-stats value would.

**Tests:** 57 new tests across
`tests/test_job_requirement_models.py` (`SourceSpan`/`JobRequirement`:
technical-resolved, technical-unresolved, non-technical, necessity,
importance, observability, parser confidence, provenance, invalid
states, equality/hash),
`tests/test_job_requirement_profile.py` (`JobRequirementProfile`:
multiple/mixed requirements, order preservation, description
preservation, optional title/context, invalid empty description, invalid
provenance spans, duplicate rejection, candidate-independence), and
`tests/test_job_requirement_manual_examples.py` (Part 12's three jobs).
All deterministic, offline, no network calls. **467 tests total, all
passing** (up from 410; every 5B/5C/5D/5D.1/V1 test untouched and still
passing).

**Files changed:**
- `src/gitscore/jobs/__init__.py`, `types.py`, `models.py`, `profile.py`
  — new package.
- `tests/test_job_requirement_models.py`,
  `test_job_requirement_profile.py`,
  `test_job_requirement_manual_examples.py` — new.
- `docs/ARCHITECTURE.md` — new §17 (full design detail).
- This changelog entry.

**How to test:** `pytest` (whole suite, 467 tests, no network/token
required) or `pytest tests/test_job_requirement_models.py
tests/test_job_requirement_profile.py
tests/test_job_requirement_manual_examples.py -v` for just the
6A-relevant subset.

**Explicitly NOT done this milestone (per instruction — wait for
approval before starting):** job-description parser (regex or LLM), URL
ingestion, deterministic matcher, match/coverage scores, strengths/gaps,
alternative-role discovery, CatBoost, UI, database persistence/migration,
any change to candidate-evidence extraction. No commit was made.

## 2026-09-28 — Milestone 5D.1: Context-safe concept resolution

**What changed:** A focused correctness fix to Milestone 5D's README
extractor, requested after real-world validation showed it was treating
known ordinary-English false positives ("go", "next", the "js" suffix of
".js"-named frameworks) as accepted behavior instead of fixing them. No
architecture, pipeline, ranking, evidence model, API strategy, confidence
system, or extraction-scope change — see `docs/ARCHITECTURE.md` §16 for
the full design writeup; this entry summarizes.

**Root cause:** `TechnicalConcept.aliases` was one flat list, matched
identically by every source. A structured source (a `package.json` key,
a GitHub language-stats name) hands the matcher an already-scoped,
intentional term, so short aliases like `"go"`/`"next"`/`"js"` are
completely safe there. Free-form README prose is not scoped at all —
those same short aliases collide with ordinary English ("I **go** for
large components", "**Next** Track") or with unrelated `.js`-suffixed
names ("Next**.js**" incidentally satisfying a bare `"js"` alias).

**Fix — source-aware alias metadata, not a second table:**
`TechnicalConcept` (`concepts/models.py`) gained
`readme_unsafe_aliases: frozenset[str]` (validated as a subset of
`aliases` in `__post_init__`) and a `readme_safe_aliases()` method
(`aliases` minus `readme_unsafe_aliases`). `concepts/registry.py` marks
`"go"` (on `language.go`), `"next"` (on `framework.nextjs`), `"js"` (on
`language.javascript`), `"ts"` (on `language.typescript`), and `"c"` (on
`language.c`, its only alias) as `readme_unsafe`.
`evidence/extraction/readme.py` is the ONLY caller of
`readme_safe_aliases()` — it now matches that restricted list instead of
the full `aliases`. `resolve_concept()` and every structured-source
caller (`dependency_evidence.py`, `languages.py`) are byte-for-byte
unchanged: they still resolve the full alias set, so `package.json`'s
`"next"` dependency and GitHub's `"Go"` language-stats name keep
resolving exactly as before. A `DEPENDENCY_CONCEPT_ALIASES`-style second
mapping was considered and rejected — nothing about structured
dependency resolution was actually broken, so nothing there needed
changing.

**README-safe alias policy:** an alias is README-safe by default; it is
marked unsafe only when it is short and/or an ordinary English word that
literal, boundary-only, case-insensitive matching cannot tell apart from
non-technical prose. `"golang"`/`"next.js"`/`"nextjs"`/`"javascript"`/
`"typescript"` remain README-safe unambiguous forms. `language.c`'s only
alias (`"c"`, a single letter) has no safe form at all, so it now
produces **zero** README evidence — a documented limitation (see below),
not a bug.

**Structured dependency alias policy:** unchanged from Milestone 5D — no
second package-name table; `resolve_concept()`'s full alias set is
exactly correct for a manifest declaration, which is unambiguous by
construction.

**Language-statistics resolution:** unchanged — `languages.py` still
calls `resolve_concept()` with GitHub's exact language-stats names
(`"Go"`, `"JavaScript"`, `"TypeScript"`, `"C"`, `"C++"`, ...), which
resolve through the full alias set, not `readme_safe_aliases()`. Covered
by a new regression test,
`test_evidence_extraction_languages.py::test_short_readme_unsafe_aliases_still_resolve_githubs_exact_language_names`.

**Versioning:**
- `CONCEPT_REGISTRY_VERSION` 2 -> 3 — no concept added/renamed/merged,
  but the registry's per-alias safety metadata changed, which its own
  bump policy (`registry.py`) treats as a content change worth tracking.
- `readme.py`'s `EXTRACTOR_VERSION` `readme:v1` -> `readme:v2` — its
  matching behavior changed. No other extractor's version moved.
- `EVIDENCE_SCHEMA_VERSION` stays `2` — no shape change to `Evidence`,
  `CandidateConceptSummary`, `CandidateEvidenceProfile`, or
  `RepositoryAnalysisCoverage`.
- `SCORING_RUBRIC_VERSION`, `DATASET_VERSION`, `REPOSITORY_RANKING_VERSION`
  untouched, per instruction.

**Tests:** 2 existing version-pin tests updated
(`test_technical_concepts.py::test_concept_registry_version_constant_exists_and_is_an_int`,
updated for the 2 -> 3 bump). `test_evidence_extraction_readme.py`'s two
former "known false positive, accepted" tests replaced with tests
proving the false positive is GONE (`test_bare_next_no_longer_matches_ordinary_english`,
`test_bare_go_no_longer_matches_ordinary_english_i_go_for`, `..._let_it_go`,
`test_written_in_go_bare_form_is_a_documented_limitation_not_detected`),
plus new tests for the surrounding behavior: `"next steps"`/`"Next Track"`
still produce no evidence, `"Uses Next.js"` still matches
`framework.nextjs`, a `Next.js` mention does NOT also produce
`language.javascript` evidence, an independent `"JavaScript"` mention
still does, `"golang"` still matches, and bare `"C"` never matches. 6 new
tests added to `test_technical_concepts.py` for
`readme_safe_aliases()`/the `__post_init__` subset validation, plus a
resolve_concept() regression test confirming go/next/js/ts/c are still
valid structured-source aliases. 1 new regression test each in
`test_evidence_extraction_languages.py` (GitHub language-stats names) and
`test_evidence_extraction_dependency_mapping.py` (`"next"` package
dependency). All new tests are deterministic, offline, no network calls.
**410 tests total, all passing** (up from 395; no test removed, several
rewritten in place).

**Real-account re-validation** (the same 4 accounts Milestone 5D's
original validation used — `Jango1324`, `torvalds`, `karpathy`,
`sindresorhus` — NOT the 18-account pilot, per instruction), via
`scripts/inspect_evidence_profile.py`, confirms the false positives are
gone: `torvalds/1590A` and `karpathy/autoresearch` no longer produce
`language.go` README evidence; `Jango1324/Arduino-Based-Media-Player` no
longer produces `framework.nextjs` README evidence from "Next Track", and
`Jango1324`'s real `package.json` `"next"` dependency still correctly
resolves to `framework.nextjs` at `STRONG` confidence. `API requests` is
identical to Milestone 5D's original run for all four accounts (README
matching doesn't change what's fetched); `Evidence items`/`Concepts
detected` dropped for every account, as expected. Full corrected
before/after table: `docs/ARCHITECTURE.md` §15.11 (also fixes that
table's separate, unrelated Requests/Evidence-items column swap for
`karpathy`/`sindresorhus`, found while re-measuring). Zero extractor
failures across all four, both before and after.

**Known remaining limitation (intentional, not fixed):** bare "Go"
("Written in Go") and bare "C" still produce no README evidence — there
is no literal, deterministic way to distinguish them from ordinary
English without the fuzzy/NLP inference this project is scoped to avoid.
Language-stats extraction remains the practical source for both. Other
short-and-also-an-English-word registry aliases (`react`, `flask`,
`express`, ...) were not evaluated this round — out of this cleanup's
bounded scope — and may need the same `readme_unsafe_aliases` treatment
if real validation flags them later.

**Files changed:**
- `src/gitscore/concepts/models.py` — `TechnicalConcept.readme_unsafe_aliases`,
  `readme_safe_aliases()`, `__post_init__` subset validation.
- `src/gitscore/concepts/registry.py` — `CONCEPT_REGISTRY_VERSION` 2->3;
  `readme_unsafe_aliases` on `language.go`, `framework.nextjs`,
  `language.javascript`, `language.typescript`, `language.c`; updated
  module/entry docstrings (the old "accepted false positive" comments on
  `framework.nextjs` no longer describe current behavior).
- `src/gitscore/evidence/extraction/readme.py` — matches
  `concept.readme_safe_aliases()` instead of `concept.aliases`;
  `EXTRACTOR_VERSION` `readme:v1` -> `readme:v2`.
- `src/gitscore/evidence/extraction/dependency_evidence.py` — clarifying
  comment only (no behavior change): explains why this module
  intentionally keeps using the full `aliases` list.
- `tests/test_technical_concepts.py`, `tests/test_evidence_extraction_readme.py`,
  `tests/test_evidence_extraction_languages.py`,
  `tests/test_evidence_extraction_dependency_mapping.py` — see Tests above.
- `docs/ARCHITECTURE.md` — new §16; §15.6/§15.11/§15.12 updated in place
  (false positives now documented as fixed, not accepted; validation
  table corrected and re-measured).
- This changelog entry.

**How to test:** `pytest` (whole suite, 410 tests, no network/token
required) or `pytest tests/test_evidence_extraction_readme.py
tests/test_technical_concepts.py tests/test_evidence_extraction_languages.py
tests/test_evidence_extraction_dependency_mapping.py -v` for just the
5D.1-relevant subset. Real-account re-validation:
`python scripts/inspect_evidence_profile.py <username>` against
`Jango1324`/`torvalds`/`karpathy`/`sindresorhus` (requires `GITHUB_TOKEN`
in `.env`).

**Explicitly NOT done this milestone (per instruction — wait for
approval before starting):** Milestone 6, `JobRequirementProfile`,
job-description parsing, any deterministic matcher, match scores,
alternative-role discovery, CatBoost, LLM-based extraction, UI, no
redesign of the pipeline/ranking/evidence model/API strategy/confidence
system/extraction scope, no `react`/`flask`/`express`-style alias review
beyond what was asked. No commit was made.

## 2026-09-27 — Milestone 5D: Bounded technical evidence extraction

**What changed:**

The first real V2 evidence pipeline, connecting Milestone 5B's
repository ranking to Milestone 5C's Evidence/CandidateEvidenceProfile
domain model with an actual per-repository extraction step. New package
`src/gitscore/evidence/extraction/` (`languages.py`, `readme.py`,
`python_deps.py`, `js_deps.py`, `dependency_evidence.py`, `docker.py`,
`files.py`) plus a new orchestrating entry point,
`gitscore.pipeline.evidence.extract_candidate_evidence()`. **No job
matching, no JobRequirementProfile, no job-description parsing, no match
scores, no alternative-role discovery, no CatBoost, no LLM extraction, no
UI, no source-code/test/CI/notebook-content crawling, no recursive
repository crawling, no database schema change, no pilot recollection.**
V1 (`features/*`, `scoring/readiness.py`, `pipeline/analyze.py`, Dataset
V1) is byte-for-byte unchanged. 320 of Milestone 5C's 322 pre-existing
tests untouched; 2 version-pin tests updated for a deliberate, documented
version bump (see below); 73 new tests added. Full suite: **395 tests,
all passing**, no live GitHub calls, no GitHub token required.

**Why:** Milestones 5B and 5C each shipped as standalone, unconnected
modules by design (validate each piece in isolation before wiring). This
milestone is the first to connect them end-to-end and prove the whole
loop — ranking bounds cost, extraction produces real provenance-backed
Evidence — against real GitHub accounts, not just synthetic fixtures.

**Full design writeup, API cost model (with real measured numbers across
4 validated accounts), language-significance policy, README-matching
policy and its two documented known false positives, dependency-mapping
design, Docker semantics, confidence table, and failure-semantics table:
see `docs/ARCHITECTURE.md` §15 (new).** This entry summarizes; §15 is the
authoritative detail.

**The new V2 flow:**

```
GitHub username
  -> GitHubClient.get_repositories()        listing (5B, unchanged)
  -> parse_repo_summary() -> rank_repositories()   top N=15 (5B, unchanged)
  -> per selected repo: languages + README + ONE root-listing call
     + get_repository_file() for whichever of 8 supported filenames
     the root listing showed actually exist
  -> extractors -> Evidence[]                (THIS MILESTONE)
  -> build_candidate_evidence_profile()       CandidateEvidenceProfile (5C, unchanged)
```

**GitHub client additions (`github/client.py`):** `get_repository_readme_with_path()`
(README text + its resolved path, for provenance),
`get_repository_root_contents()` (one bounded, non-recursive root-listing
call — a 404 means a genuinely empty repo, returns `[]`, not a failure),
`get_repository_file()` (fetch one known-to-exist file by path; unlike
the README method, a 404 here IS a real reportable failure — the file
disappeared between listing and fetch). `get_repository_readme()`'s
existing signature/behavior is unchanged; `_fetch_readme()` is now the
one shared implementation both README methods call.

**Extractors, versions, and confidence** (full rationale in
ARCHITECTURE.md §15.5-§15.9):

| Extractor | Evidence type | Confidence | Version |
|---|---|---|---|
| `languages.py` | `REPOSITORY_LANGUAGE` | `WEAK` (<40% of bytes) / `MODERATE` (≥40%) | `language:v1` |
| `readme.py` | `README` | `MODERATE` | `readme:v1` |
| `python_deps.py` (requirements.txt) | `DEPENDENCY` | `STRONG` | `requirements:v1` |
| `python_deps.py` (pyproject.toml, `[project.dependencies]` only) | `DEPENDENCY` | `STRONG` | `pyproject:v1` |
| `js_deps.py` (package.json `dependencies`+`devDependencies`) | `DEPENDENCY` | `STRONG` | `npm:v1` |
| `docker.py` | `DOCKER` | `STRONG` | `docker:v1` |

Language significance policy: a language must be ≥5.0% of a repo's
byte total to produce evidence (`MIN_SIGNIFICANT_PERCENTAGE`,
`languages.py`); ≥40.0% promotes `WEAK` to `MODERATE`
(`MODERATE_CONFIDENCE_PERCENTAGE`). Percentage-based, not a byte floor,
because GitHub's language-stats endpoint already normalizes for repo
size. An unresolved-but-meaningful language still produces
`unresolved:<name>` evidence (mirrors `v1_bridge.py`'s existing
`primary_language` handling) — 8 distinct unresolved languages were
observed live (`cmake`, `makefile`, `openscad`, `qml`, `xslt`, `lua`,
`astro`, `postscript`, `swift`), confirming the policy works as intended
rather than silently dropping real signal.

Dependency mapping is **data, not code**: package/dependency names
resolve through the SAME `concepts.registry` aliases every other source
uses (`resolve_concept()`) — no second "package name → concept" table.
Registry additions this milestone: a representative set of GitHub
language names (`javascript`, `typescript`, `java`, `c`, `cpp`, `csharp`,
`go`, `rust`, `ruby`, `php`, `shell`, `html`, `css`,
`jupyter_notebook`) plus a handful of dependency-manifest-only concepts
(`tensorflow`, `pandas`, `express`, `nestjs`, `fastapi`, `flask`,
`prisma`) and expanded aliases on `postgresql`
(`psycopg2`/`psycopg2-binary`/`psycopg`). `CONCEPT_REGISTRY_VERSION`
bumped 1 → 2 (content change, per its own bump policy). **Unknown**
dependency names are deliberately NOT turned into `unresolved:` Evidence
(unlike languages) — tracked only as a plain diagnostic list
(`EvidenceExtractionResult.unknown_dependency_names`), never written into
the registry or the Evidence pool, because a manifest can list hundreds
of irrelevant/niche package names (185 unique unknown names observed on
`sindresorhus` alone) and turning every one into Evidence would be noise,
not signal — exactly what the "do not pretend every dependency is a
useful technical concept" instruction warns against. This mirrors
`v1_bridge.py`'s existing topics-skip precedent, not its
always-evidence primary-language precedent.

**Root-file discovery (`files.py`):** ONE `get_repository_root_contents()`
call per selected repo returns every root entry; `discover_supported_root_files()`
is a pure, case-sensitive filter against the 8 supported filenames
(`requirements.txt`, `pyproject.toml`, `package.json`, `Dockerfile`,
`docker-compose.yml`, `docker-compose.yaml`, `compose.yml`,
`compose.yaml`) — never a recursive crawl, never one probe-request per
candidate filename. `Pipfile`/`environment.yml` were evaluated (Part 7's
"optional if trivial") and deliberately **not** added: none of the four
validated real accounts had either, and `requirements.txt`/
`pyproject.toml`/`package.json` already covered every dependency signal
actually observed.

**pyproject.toml support is deliberately bounded:** only PEP 621's
`[project] dependencies = [...]` string array, parsed with the stdlib
`tomllib` (no new dependency — the project already requires Python
≥3.11). Poetry's `[tool.poetry.dependencies]` table format is explicitly
NOT supported (a fundamentally different, name-keyed shape) — confirmed
by a dedicated test. Malformed TOML raises `tomllib.TOMLDecodeError`,
caught by the orchestration layer and recorded as an extractor failure,
never crashing candidate analysis.

**Evidence-schema change (`EVIDENCE_SCHEMA_VERSION` 1 → 2):**
`RepositoryAnalysisCoverage` gained one additive field,
`partially_analyzed: tuple[RepositoryIdentity, ...] = ()` — the subset of
`analyzed` where at least one evidence source for that repository could
not be inspected (a real failure, not an expected absence like "no
requirements.txt"). This is the smallest compatible extension found
necessary to represent Milestone 5D Part 14's distinction between "we
looked and it's not there" and "we couldn't look" — no broader redesign
of `CandidateEvidenceProfile` was needed. It does not add a new coverage
tier: a `partially_analyzed` repository is still counted in
`analyzed`/`analyzed_count`/`is_complete` exactly as before. Two existing
version-pin tests (`test_evidence_schema_version_constant_exists`,
`test_concept_registry_version_constant_exists_and_is_an_int`) were
updated to assert the new values, with comments explaining why each bump
is legitimate per its own documented policy.
`SCORING_RUBRIC_VERSION`/`DATASET_VERSION`/`REPOSITORY_RANKING_VERSION`
are untouched — nothing in this milestone meets any of their bump
conditions.

**Failure semantics (`pipeline/evidence.py`):** every network call per
selected repository is isolated in its own try/except — one failing
source degrades only that source. `README`/manifest absence (404 / not
in the root listing) is an expected absence, never recorded as a
failure. A languages/README/root-listing/manifest fetch failure, or a
malformed manifest (bad TOML/JSON), is recorded as an `ExtractionFailure`
(`repository`, `source`, `error`) and marks that repository
`partially_analyzed` — analysis of the rest of that repo and every other
selected repo continues. `GitHubRateLimitError` is the one exception NOT
caught anywhere in this path — it propagates immediately and aborts the
whole run, mirroring V1's existing `pipeline/analyze.py` batch-abort
policy. `EvidenceExtractionResult` (new, `pipeline/evidence.py`) bundles
`profile` + `extractor_failures` + `unknown_dependency_names` —
deliberately NOT part of `CandidateEvidenceProfile` itself, since these
are pipeline-run diagnostics, not candidate technical evidence.

**API cost — real measured numbers, not just an estimate** (full table
in ARCHITECTURE.md §15.4): `torvalds` (12 repos) → 38 requests;
`Jango1324` (20 repos) → 53; `karpathy` (63 repos) → 54; `sindresorhus`
(1,141 repos) → 70. Deep-analysis cost is bounded by N=15 regardless of
total repo count — confirmed directly: `sindresorhus` at 1,141 repos
costs roughly the same as `karpathy` at 63, the difference being a
handful of extra listing-pagination requests, not a multiplier on deep
analysis.

**Known false positives, found in live validation** (see
ARCHITECTURE.md §15.6 for the full original writeup):
- Bare `"go"` (alias of `language.go`) matches ordinary English ("I
  **go** for...", "let it **go**") — inherent to context-free keyword
  matching, not fixable without exactly the fuzzy/NLP inference this
  milestone is scoped to avoid. Observed on `torvalds/1590A` and
  `karpathy/autoresearch`.
- Bare `"next"` (alias of `framework.nextjs`) matches ordinary English
  ("**Next** Track"). Observed on `Jango1324/Arduino-Based-Media-Player`.
- A real (and initially test-driven-out) bug, fixed before it shipped:
  `requirements.txt` parsing originally read a bare VCS/URL requirement
  (`git+https://...`) as if `git` were a package name. Fixed by skipping
  any line containing `"://"`.

> **Amendment (Milestone 5D.1, see that entry above):** the "go"/"next"
> README false positives above were originally *accepted* as documented
> limitations here. Follow-up real-world validation judged that
> unacceptable for ordinary English to keep producing known-wrong
> technical evidence, so Milestone 5D.1 fixed them at the alias level
> (`readme_unsafe_aliases`) instead — they are no longer current,
> intended behavior. This paragraph is left as the historical record of
> what Milestone 5D actually shipped and why; see the Milestone 5D.1
> entry and `docs/ARCHITECTURE.md` §15.6/§16 for the current, corrected
> policy.

**Real-account validation (Milestone 5D Part 17/18), V2 pipeline only, no
score of any kind produced:** `Jango1324`, `torvalds`, `karpathy`,
`sindresorhus` — chosen for diversity (small Python/web account, C/systems,
Python/ML, JS/TS at 1,140+ repos). Zero extractor failures across all
four. Full per-account breakdown (repos discovered/analyzed, evidence by
type, concepts detected, unresolved concepts, unknown dependency counts,
representative provenance) in ARCHITECTURE.md §15.11. Reproducible via
`scripts/inspect_evidence_profile.py <username>` (new, inspection-only —
no persistence, no job-fit/readiness score).

**`Jango1324/Pneumonia-Detection-Ai` (Part 15's named edge case):**
confirmed still ranked outside the top 15 in this milestone's real run —
reported truthfully as `discovered=yes, analyzed=no` in
`inspect_evidence_profile.py`'s output. Not manually forced into the
selection; no ranking-weight change or job-aware special-casing was
added for it, per explicit instruction.

**Files changed:**
- `src/gitscore/github/client.py` — `get_repository_readme_with_path()`,
  `get_repository_root_contents()`, `get_repository_file()`,
  `_fetch_readme()` (shared implementation).
- `src/gitscore/concepts/registry.py` — `CONCEPT_REGISTRY_VERSION` 1→2;
  new language + dependency-manifest-only concepts (see above); expanded
  `database.postgresql` aliases.
- `src/gitscore/evidence/types.py` — `EVIDENCE_SCHEMA_VERSION` 1→2.
- `src/gitscore/evidence/profile.py` — `RepositoryAnalysisCoverage.partially_analyzed`
  (+ `partially_analyzed_count`), `build_candidate_evidence_profile(partially_analyzed=...)`.
- `src/gitscore/evidence/extraction/__init__.py`, `files.py`,
  `languages.py`, `readme.py`, `python_deps.py`, `js_deps.py`,
  `dependency_evidence.py`, `docker.py` — new package.
- `src/gitscore/pipeline/evidence.py` — new: `extract_candidate_evidence()`,
  `EvidenceExtractionResult`, `ExtractionFailure`.
- `scripts/inspect_evidence_profile.py` — new manual inspection/validation tool.
- `tests/conftest.py` — `FakeEvidenceGitHubClient`, `root_entry()` helper.
- `tests/test_evidence_extraction_languages.py`,
  `test_evidence_extraction_readme.py`,
  `test_evidence_extraction_requirements_txt.py`,
  `test_evidence_extraction_pyproject_toml.py`,
  `test_evidence_extraction_package_json.py`,
  `test_evidence_extraction_dependency_mapping.py`,
  `test_evidence_extraction_docker.py`, `test_pipeline_evidence.py` — new.
- `tests/test_candidate_evidence_profile.py` — new `partially_analyzed`
  coverage tests.
- `tests/test_evidence_models.py`, `tests/test_technical_concepts.py` —
  version-pin tests updated for the deliberate 1→2 bumps, with rationale
  comments.
- `docs/ARCHITECTURE.md` — new §15 (full design detail); §13/§14 updated
  to reflect that 5B/5C are now wired together, not just standalone.
- `docs/PIPELINE.md` — new short section pointing to the V2 path.
- This changelog entry.

**How to test:** `pytest` (whole suite, 395 tests, no network/token
required) or `pytest tests/test_pipeline_evidence.py
tests/test_evidence_extraction_*.py tests/test_candidate_evidence_profile.py -v`
for just the Milestone 5D-relevant subset. Real-account validation:
`python scripts/inspect_evidence_profile.py <username>` (requires
`GITHUB_TOKEN` in `.env` for a reasonable rate limit, per the existing
`.env.example`).

**Explicitly NOT done this milestone (per instruction — wait for
approval before starting):** Milestone 6/6A, `JobRequirementProfile`,
job-description parsing, any deterministic matcher, match scores,
alternative-role discovery, CatBoost, LLM-based extraction, UI. No commit
was made.

## 2026-09-11 — Milestone 5C: Generalized evidence domain model

**What changed:**

Two new packages, `src/gitscore/concepts/` and `src/gitscore/evidence/`
— the domain vocabulary future evidence extractors will produce and
future job matching will consume: `Candidate → Repository →
Observation → Technical Concept`, with provenance preserved end to end.
**No deep evidence extraction, no dependency/manifest/Dockerfile/CI/
notebook parsing, no job-description parsing, no JobRequirementProfile,
no job matching, no match scores, no alternative-role discovery, no role
archetypes, no CatBoost, no LLM analysis, no UI, no source-code
crawling, no database schema change, no org-contribution attribution, no
pilot recollection.** Repository ranking (Milestone 5B) was not wired
into this milestone's model either — the two remain independent,
standalone modules. V1 (`features/*`, `scoring/readiness.py`, Dataset
V1) is completely unchanged. Existing 257 tests untouched and still
passing; 65 new tests added (322 total). Everything is in-memory plain
Python — no SQLAlchemy import anywhere in either new package.

**Why:** Milestone 5A's design established that GitScore needs a
structured, provenance-backed representation of "what a candidate's
GitHub evidence shows" *before* any job-matching logic can be built on
top of it. This milestone builds exactly that representation in
isolation, so its shape can be validated (by tests and by bridging real
V1-shaped data into it) before locking anything into a database schema
or building extractors against it.

*Domain objects introduced:*

| Object | Module | Role |
|---|---|---|
| `TechnicalConcept` | `concepts/models.py` | one canonical concept (`concept_id`, `display_name`, `category`, `aliases`, optional `parent_id`/`related_ids`) |
| `ConceptRegistry` / `default_registry()` | `concepts/registry.py` | immutable, in-memory alias index; built once, never mutated |
| `resolve_concept(term)` / `ConceptResolution` | `concepts/registry.py` | deterministic term → concept resolution, explicit `matched` flag |
| `RepositoryIdentity` | `evidence/models.py` | minimal `(owner, name)` reference — not a full repository summary (that's `ranking.RepositoryRankingResult`, kept separate) |
| `Evidence` | `evidence/models.py` | one provenance-backed observation: repository, evidence type, raw text, normalized concept id, confidence, extractor version, optional file/location/timestamp |
| `EvidenceType` | `evidence/types.py` | `REPOSITORY_LANGUAGE`, `REPOSITORY_METADATA`, `README`, `DEPENDENCY`, `SOURCE_IMPORT`, `CONFIG`, `DOCKER`, `CI`, `TEST`, `NOTEBOOK`, `DEPLOYMENT` (not all have extractors yet) |
| `ConfidenceLevel` | `evidence/types.py` | ordinal `WEAK` / `MODERATE` / `STRONG` (see rationale below) |
| `CandidateConceptSummary` | `evidence/summary.py` | Evidence for one concept, always *derived*, never independently constructed |
| `RepositoryAnalysisCoverage` | `evidence/profile.py` | `discovered` vs. `analyzed` repository tuples + `is_complete` |
| `CandidateEvidenceProfile` | `evidence/profile.py` | the full job-independent picture: candidate, coverage, evidence, derived concept summaries, versions |

*Representative concept registry (13 entries, spanning 10 categories —
proving the mechanism, not a complete ontology):* `language.python`,
`database.postgresql`, `database.redis`, `ml.framework.pytorch`,
`framework.react`, `framework.nextjs`, `infra.docker`, `cloud.aws`,
`platform.cuda`, `robotics.ros2`, `embedded.rtos.freertos`,
`hdl.verilog`, `toolchain.llvm`. Adding a concept is one new
`TechnicalConcept(...)` entry in `concepts/registry.py::_CONCEPTS` — no
change to `ConceptRegistry`, `resolve_concept`, or anything downstream.

*Normalization rules (`concepts/normalize.py`):* lowercase, strip
periods and commas only, collapse internal whitespace. Deliberately
narrow — a blanket "strip all punctuation" normalizer would collide
unrelated concepts (e.g. "C++" and "C"); this rule set was chosen
specifically because it resolves every example in the milestone brief
correctly (`Postgres`/`postgresql`/`POSTGRESQL` → `database.postgresql`;
`React.js`/`ReactJS`/`react` → `framework.react`;
`torch`/`PyTorch` → `ml.framework.pytorch`;
`AWS`/`Amazon Web Services` → `cloud.aws`) without merging `C++`/`C`.
No LLM, no fuzzy matching — exact match against normalized aliases only.

*Unknown-concept policy (Part 3 — explicit choice):* `resolve_concept()`
returns an **explicit unresolved result** (`matched=False`,
`concept=None`), not a synthesized "provisional concept" object added
anywhere. Separately, at the `Evidence`-construction layer, an unmatched
raw term is given a deterministic, non-registry pseudo-id —
`"unresolved:<normalized-term>"` — so no observation is ever silently
dropped (architectural rule 4) while the canonical registry itself is
never mutated (architectural rule: no dynamic registry mutation from
unknown input — verified by
`test_technical_concepts.py::test_resolving_an_unknown_term_does_not_mutate_the_shared_registry`).
The same literal unknown term always maps to the same unresolved id
(useful later for tallying which unknown terms recur, for registry
curation); two *different* spellings of an unknown concept are
deliberately **not** merged — that would require the fuzzy-matching/
ontology-building work this milestone is explicitly scoped to avoid.

*Confidence model (Part 5 — ordinal, not float):* `ConfidenceLevel.WEAK
/ MODERATE / STRONG` (an `IntEnum`, so "strongest evidence" is a plain
`max()`). Chosen over a float (e.g. `0.87`) because nothing in this
milestone calibrates a claim like that against any real ground truth —
a float would assert a precision the system does not have. Confidence
describes confidence in **the evidence claim**, never candidate skill,
proficiency, or job fit — e.g. a `STRONG`-confidence dependency-manifest
observation of `torch` means "we are sure `requirements.txt` declares
this dependency," not "the candidate is skilled at PyTorch." Stated
explicitly in code docstrings and in `docs/ARCHITECTURE.md` §14 so it
can't be misread later.

*Aggregation rules (`evidence/summary.py`):* `CandidateConceptSummary`
is always built by `summarize_concept()` / `build_concept_summaries()`
from a pool of `Evidence` — never constructed or mutated directly.
`evidence_count`, `repositories` (distinct, sorted), and
`strongest_confidence` (max over the group) are all derived properties,
computed fresh from `evidence`, not separately stored fields that could
drift. Deterministic ordering: repository owner → repository name →
file path → evidence type → raw observation text, applied regardless of
input order.

*Duplicate policy:* `Evidence` is a frozen, fully hashable dataclass, so
exact structural duplicates (identical repository, file, evidence type,
concept, raw text, confidence, extractor version) collapse to one via a
plain `set()` — both inside `summarize_concept()` and at the whole-profile
level in `build_candidate_evidence_profile()`. Evidence differing in
*any* field (different file, different repo, different raw text, even a
re-run with a new `extractor_version`) is kept as a **separate** item,
not merged — corroborating evidence should be visible, not silently
absorbed.

*`CandidateEvidenceProfile` job-independence (Part 7 / architectural
rule 8):* no field for a target job, match score, required/preferred
skills, or alternative roles — pinned by
`test_candidate_evidence_profile.py::test_profile_has_no_job_related_fields`.
`concept_summaries` is exposed as a `types.MappingProxyType` (read-only
view), not a plain dict, so external code cannot mutate the derived
summaries independently of the `Evidence` that produced them —
structurally enforced, not just documented.

*Discovered vs. analyzed (Part 7):* `RepositoryAnalysisCoverage` carries
both `discovered` and `analyzed` repository-identity tuples plus
`is_complete` — the representable form of "GitScore discovered 1,140
repositories but deeply analyzed 15," laying the groundwork for the
`INSUFFICIENT_ANALYSIS` semantics from
`docs/design/MILESTONE_5A_JOB_MATCHING_DESIGN.md` Part 16. Not yet
connected to Milestone 5B's ranking output — that wiring is explicit
future work (see Part 24 milestone sequence), not part of this
milestone's scope.

**Persistence decision (Part 9):** agreed with the requested default —
**domain model first, persistence later.** No SQLAlchemy table was
added; `db/models.py`, `db/database.py`, and `db/queries.py` are
untouched. Justification: (1) no deep-extraction detector exists yet to
validate the shape against real output — the same mistake that produced
`ProfileFeature`'s known gaps (no unique constraint, no per-row rubric
version — `docs/ML_NOTES.md` §4 item 3) would be easy to repeat by
locking a schema in before the shape has been exercised; (2)
`CLAUDE.md`'s own DB rule ("prefer Alembic if schema evolution becomes
non-trivial") argues against introducing migration machinery for a model
still expected to change; (3) nothing in this milestone's success
criteria requires cross-process durability — everything is validated by
unit tests. No database migration was performed.

**Bridging existing V1 information (Part 10), without touching V1:**
`evidence/v1_bridge.py` (demonstration-only, not imported by
`pipeline/analyze.py` or any script) shows three concrete examples,
each backed by a test in `tests/test_v1_evidence_bridge.py`:
- `parse_repo()`'s `primary_language` → weak `REPOSITORY_LANGUAGE`
  evidence (and demonstrates the unresolved-concept path: an unrecognized
  language like "COBOL" still produces Evidence, with an
  `unresolved:cobol` concept id, never silently dropped).
- `parse_repo()`'s `readme` text → moderate `README` evidence, one item
  per matched concept (e.g. "Built using ROS2 for navigation" →
  `robotics.ros2`).
- `parse_repo_summary()`'s `topics` (Milestone 5B) → weak
  `REPOSITORY_METADATA` evidence, for topics that resolve to a known
  concept (non-technical topics like `"hacktoberfest"` are deliberately
  skipped, not turned into unresolved evidence — a detector-design
  choice, not a violation of the no-silent-drop rule, which concerns
  evidence that *was* extracted).
`features/ml.py`, `features/readme.py`, `features/languages.py`, and
`scoring/readiness.py` are byte-for-byte unchanged.

**Versioning:** `CONCEPT_REGISTRY_VERSION = 1`
(`concepts/registry.py`) — bump when a concept is added/renamed/merged,
or when `normalize.py`'s normalization rules change (that changes which
aliases resolve). `EVIDENCE_SCHEMA_VERSION = 1` (`evidence/types.py`) —
bump when `Evidence`, `CandidateConceptSummary`,
`CandidateEvidenceProfile`, or `RepositoryAnalysisCoverage` change SHAPE
(fields added/removed/retyped) — NOT for adding a new `EvidenceType`
member (additive, non-breaking) or a new concept (that's the registry
version). `SCORING_RUBRIC_VERSION`, `DATASET_VERSION`
(`dataset/schema.py`), and `REPOSITORY_RANKING_VERSION`
(`ranking/config.py`) are untouched — none of this milestone's changes
meet any of their bump conditions.

**Files changed:**
- `src/gitscore/concepts/__init__.py`, `models.py`, `normalize.py`,
  `registry.py` — new package.
- `src/gitscore/evidence/__init__.py`, `models.py`, `types.py`,
  `summary.py`, `profile.py`, `v1_bridge.py` — new package.
- `tests/test_technical_concepts.py`, `test_evidence_models.py`,
  `test_candidate_concept_summary.py`,
  `test_candidate_evidence_profile.py`, `test_v1_evidence_bridge.py` —
  new, 65 tests, all synthetic/in-memory, no network calls, no GitHub
  token.
- `docs/ARCHITECTURE.md` — new §14 documenting the domain model, the
  provenance philosophy, the discovered-vs-analyzed distinction, and the
  "Evidence Profile != Job Match" / "confidence != proficiency"
  statements.
- This changelog entry.

**Unresolved design questions (not decided in this milestone):**
- Whether `RepositoryAnalysisCoverage.analyzed` should eventually store
  richer per-repository ranking metadata (score, rank position) rather
  than plain `RepositoryIdentity` — deferred until a real caller (the
  future extraction pipeline) needs it.
- Whether `Evidence.location` (line/cell-level position, currently
  always `None` — no extractor populates it yet) is the right shape for
  every future evidence type (e.g. a Dockerfile instruction vs. a
  notebook cell vs. a source line) or whether it needs to become a
  structured type per `evidence_type` — left generic and unexercised
  until Milestone 5D's extractors have real opinions.
- Whether `ConfidenceLevel`'s 3-level ordinal scale is granular enough
  once Milestone 5D extractors exist for very different evidence
  strengths (e.g. a source-import + test-usage combination might
  deserve more separation from a single dependency-manifest line than
  "STRONG" vs. "MODERATE" allows) — the 5A design doc's fuller
  weak/moderate/strong/strongest ladder with numeric combination
  (Part 13) was deliberately NOT implemented here; reconciling the two
  is future work, not resolved now.
- The topics-skip-vs-unresolved asymmetry in `v1_bridge.py` (language
  always produces evidence, even unresolved; topics silently skip
  non-matches) is a reasonable per-source design choice but is not
  itself a governed rule — a future real topics extractor should
  revisit whether that asymmetry is still right.

**How to test:** `pytest tests/test_technical_concepts.py
tests/test_evidence_models.py tests/test_candidate_concept_summary.py
tests/test_candidate_evidence_profile.py tests/test_v1_evidence_bridge.py -v`
(65 tests, no network/token required).

## 2026-09-11 — Milestone 5B: Deterministic repository ranking

**What changed:**

New package `src/gitscore/ranking/` — a deterministic, job-independent
repository ranking system that selects which of a candidate's
repositories are worth a deep (per-repository) fetch later. This is
Stage 1 (+ an optional Stage 2 relevance boost) of the two-stage
ranking strategy proposed in
`docs/design/MILESTONE_5A_JOB_MATCHING_DESIGN.md` Part 11, approved as
the Milestone 5A design direction. **No CandidateEvidenceProfile
persistence, no Evidence tables, no JobRequirementProfile, no
job-description NLP, no deterministic job matching, no alternative-role
discovery, no CatBoost, no LLM analysis, no UI, no deep source-code
inspection, no database/schema change, no users recollected.** Existing
231 tests untouched and still passing; 26 new tests added (257 total).

**Why:** Milestone 4.5's pilot measured the current per-repository
collection cost directly — `sindresorhus` (1,140 repos) alone consumed
~34% of the 18-account pilot's ~6,740 GitHub API calls, because
languages + README are fetched for *every* repository regardless of how
informative it is. Ranking lets future deep analysis run on a bounded
top-N instead of the full repository list, without needing any new API
requests to decide the ranking itself.

**Ranking is deliberately job-independent and not a score.** It answers
"which repositories best represent this candidate's substantive
technical work" — never "is this candidate good," "is this candidate
ML-focused," or "does this candidate fit a job." It has no notion of
ML relevance, job requirements, or candidate quality. It only decides
what gets inspected next; the actual evidence-strength and job-matching
work (Milestones 5C+/6+/7+) is unaffected in shape or meaning by this
milestone.

*Zero-additional-API-cost fields (`github/parser.py`):*
- New `parse_repo_summary(repo)` extracts ranking fields — `archived`,
  `size` (as `size_kb`), `pushed_at`, `topics`, plus the fields
  `parse_repo()` already captures (`fork`→`is_fork`, `stargazers_count`,
  `forks_count`, `language`, `description`, `created_at`, `updated_at`,
  `html_url`) — straight from the repository-list payload
  `GitHubClient.get_repositories()` already returns. Verified against
  the live API: `archived`/`size`/`pushed_at`/`topics` are present on
  every entry today, they were simply never read. `parse_repo()` itself
  is unchanged (still requires languages+README, still used by the V1
  pipeline unmodified).

*Ranking formula (`ranking/rank.py`, weights in `ranking/config.py`):*
- Stage 1 base score = weighted sum of five components, each in
  `[0, 1]`: `size` (log-scaled against `size_reference_kb=2000`, so raw
  byte count can't reward vendored/binary bulk beyond a saturation
  point), `recency` (exponential decay on `pushed_at` — not
  `updated_at`, which also bumps on stars/issues — with a gentle
  `recency_half_life_days=730`), `language` (primary language present),
  `description` (non-blank description present), `stars` (log-scaled
  against `star_reference=50`, saturating early so a single viral repo
  cannot dominate). Default weights: size 0.35, recency 0.30, language
  0.15, description 0.10, stars 0.10 — stars capped at a fifth of the
  weight mass, per the milestone's "do not let stars dominate"
  requirement.
- Multiplicative dampeners (not exclusions — "fork ≠ useless"):
  `fork_multiplier=0.35`, `archived_multiplier=0.55`, and a
  `trivial_multiplier=0.25` for repositories at or below
  `trivial_size_kb_threshold=8` KB (near-empty scaffolds).
- Optional Stage-2 relevance boost: a caller-supplied plain list of
  terms (e.g. `["postgresql", "python", "docker"]`) matched against a
  repo's name/description/language/topics with the same word-boundary
  regex approach as `features/ml.py`'s `ML_KEYWORDS` (no substring
  false positives). Multiplies the Stage-1 score by
  `1 + relevance_boost_weight * (matched_terms / total_terms)`. Ranking
  with no terms supplied is byte-identical to Stage-1-only — this is
  explicitly **not** job-description parsing, just a literal,
  capped keyword-overlap hook for testing the two-stage interface.
- All weights/thresholds centralized in the frozen `RankingWeights`
  dataclass (`ranking/config.py`) — nothing is a scattered magic number
  in `rank.py`.

*Determinism and tie-breaking (`rank.py::_sort_key`):* score descending,
then `pushed_at` descending (missing/unparseable sorts oldest), then
repository name ascending case-insensitive. For a fixed `reference_time`
(resolved once per `rank_repositories()` call and reused for every
repository scored in that call), the same input always produces the
same order. Two calls at different real-world times may legitimately
reorder repositories as recency decays — intended, not nondeterminism.

*Top-N policy:* `DEFAULT_TOP_N = 15`. Fewer than N repositories → all
are returned, ranked, never padded. More than N → truncated to exactly
N, keeping the highest-scoring repositories (not an arbitrary prefix).

*Versioning:* `REPOSITORY_RANKING_VERSION = 1` (`ranking/config.py`),
a new constant, sibling to but independent of `SCORING_RUBRIC_VERSION`
and `DATASET_VERSION` (`dataset/schema.py`) — neither of those was
touched.

*New manual-inspection tool:* `scripts/rank_user_repos.py <username>
[--top N] [--relevance term1,term2,...]` — fetches one user's repo
listing (same calls `analyze_user()` already makes before any
per-repository fetch) and prints the top-N ranked repositories with
their full score/component/multiplier breakdown. Performs no
per-repository API calls, no persistence, does not call `analyze_user()`.

**N=10 vs 15 vs 20 validation (real accounts, listing-only fetches, no
per-repository calls):** ranked `Jango1324`, `chris1610`, `jph00`,
`sindresorhus`, `lucidrains`, `antirez`, `rasbt` (20 to 1,140 total
repositories). Score drop-off from rank 1→10→15→20 is steep for small
accounts (`Jango1324`: 0.90 → 0.24 → 0.12 → 0.02 — most real signal is
already in the top 8-10) and gentle-to-flat for large, prolific accounts
(`sindresorhus`/`lucidrains`/`rasbt`/`antirez` all stay above ~0.76-0.94
through rank 20 — everything that far down is still genuinely
substantial). N=15 was confirmed as a reasonable default: past the
point of diminishing returns for ordinary/small accounts, and a real,
predictable cost cap for large ones. Across these 7 accounts, deep
analysis at N=15 costs an estimated 237 API calls vs. 3,859 for
analyzing every repository (93.9% reduction; `sindresorhus` alone:
2,293 → 43, a 98.1% reduction) — using the same 2-calls-per-repository
cost model measured in the Milestone 4.5 pilot.

**Surprising/notable result (`Jango1324`):** the ranking correctly
surfaces the account's substantive engineering projects
(`JPod-ESP32`, `Mentoria`, `Arduino-Based-Media-Player`, `obsidianblog`,
`House-Of-Memories`) above its forks and trivial repositories, which is
the core validation this milestone asked for. But the one repository
Milestone 4.5 identified as this account's single genuine ML-relevant
work (`Pneumonia-Detection-Ai`, from an educational AI program) ranks
**16th of 20** — just outside the top-15 cutoff — because it is only
4 KB with no stars, so on pure substantiveness signals it looks
trivial. Applying the optional Stage-2 relevance boost with ML-flavored
terms (`["ai", "machine learning", "pytorch"]`) still does **not** pull
it into the top 15: the boost is multiplicative on an already
near-zero base score, so it cannot rescue a repository Stage 1 scores
as trivial. Documented as a known limitation (see below), not patched —
patching a specific account's ranking would violate the "do not
hardcode repository names" instruction this validation was run under.

**Known limitations (deliberately not fixed in this milestone):**
- `size_kb` cannot distinguish authored code from vendored/binary bulk
  — observed on `antirez/llama.cpp-deepseek-v4-flash` (317 MB, likely
  large vendored/model content) scoring as maximally "substantive" on
  size alone. Log-scaling caps the damage but doesn't eliminate it.
  Would need content inspection to fix, out of scope for a
  zero-additional-request Stage 1.
- The optional relevance boost cannot rescue a repository that Stage 1
  scores as trivial (see `Pneumonia-Detection-Ai` above) — it can only
  re-rank *among* repositories Stage 1 already considers reasonably
  substantive. Whether that's the right behavior for the eventual
  Stage 2 (once a real Job Requirement Parser exists) is an open
  product question, not resolved here.
- Organization-owned work remains invisible at the ranking stage too
  (`jph00`'s top-ranked personal repos are smaller side projects, not
  his `fastai`-org work) — consistent with, not a new instance of, the
  blind spot already documented in Milestone 4.5 and
  `docs/design/MILESTONE_5A_JOB_MATCHING_DESIGN.md`.
- `topics` is parsed and available but not used as a Stage-1
  substantiveness signal (many genuinely substantial repos never set
  topics) — only consulted for the optional Stage-2 boost. Not
  observed populated on any repository across the 7 validation
  accounts in this pilot-scale sample.

**Files changed:**
- `src/gitscore/github/parser.py` — added `parse_repo_summary()`
  (additive; `parse_repo()`/`parse_languages()` unchanged).
- `src/gitscore/ranking/__init__.py`, `config.py`, `rank.py` — new package.
- `scripts/rank_user_repos.py` — new manual-inspection script.
- `tests/test_repo_summary_parsing.py`,
  `tests/test_repository_ranking.py` — new, 26 tests, all synthetic
  fixtures, no network calls.
- `docs/design/MILESTONE_5A_JOB_MATCHING_DESIGN.md` — Part 11 annotated
  with the approved N=15 default and a pointer to this validation.
- `docs/ARCHITECTURE.md` — new §13 documenting the ranking module.
- This changelog entry.

**Risks/limitations:** see "Known limitations" above. Additionally: the
formula's weights (`RankingWeights` defaults) are a reasoned starting
point, not calibrated against labeled "this repo is/isn't substantive"
ground truth — there is no such ground truth yet. `reference_time`
defaults to wall-clock "now," so repeated runs on the same account over
time will legitimately reorder repositories as recency decays; this is
intended, not a bug, but callers needing byte-for-byte reproducibility
across time must pass an explicit `reference_time`.

**How to test:** `pytest tests/test_repository_ranking.py
tests/test_repo_summary_parsing.py -v` (26 tests, synthetic fixtures,
no network/token required). Manual inspection:
`python scripts/rank_user_repos.py <username> --top 15`.

## 2026-09-08 — Milestone 4: Clean Dataset V1 infrastructure

**What changed:**

New package `src/gitscore/dataset/` — the infrastructure to turn persisted
`ProfileFeature` snapshots into a clean, reproducible, one-row-per-user
Pandas dataset. **No CatBoost, no UI, no scoring-rubric change, no
org-repo analysis, no database-schema change, no real dataset collected.**

*Dataset contract (`dataset/schema.py`):*
- `FEATURE_COLUMNS` — 30 ordered feature names (23 numeric/count + 6
  boolean + 1 categorical), all sourced from `ProfileFeature`.
- `CATEGORICAL_FEATURE_COLUMNS = ["most_used_language"]`,
  `BOOLEAN_FEATURE_COLUMNS` (the six `has_*`), `NUMERIC_FEATURE_COLUMNS`
  (the rest). The three sets partition `FEATURE_COLUMNS` exactly
  (asserted by a test).
- `TARGET_COLUMN = "readiness_score"`; `DATASET_COLUMNS = FEATURE_COLUMNS
  + [TARGET_COLUMN]` is the exact CSV column order.
- `EXCLUDED_COLUMNS` — a `{db.column: reason}` map documenting every
  deliberately-omitted column: `profile_features.id`,
  `profile_features.user_id`, `profile_features.collected_at`,
  `users.id`, `users.github_username`, `users.name`, `users.followers`,
  `users.public_repos`, `users.collected_at`. Identifiers + timestamps +
  collection metadata + two `users` columns that are not rubric inputs in
  V1.
- `INTERNAL_ONLY_COLUMNS` — `snapshot_id`, `user_id`, `github_username`,
  `collected_at`: pulled by the builder for row-selection/diagnostics
  only, dropped before the frame is returned. `validate_frame` rejects
  any of them appearing in a dataset frame.
- `validate_frame(df, *, allow_empty=True)` — exact column set+order,
  no forbidden identifier/timestamp columns, no nulls in required
  columns, numeric columns numeric, boolean columns in {True,False,0,1},
  categorical column all-strings. Raises `DatasetSchemaError` (shape) or
  `DatasetValidationError` (values) from `dataset/exceptions.py`.

*Versioning (`dataset/schema.py`, lightweight — constants, not a schema
change):*
- `DATASET_VERSION = "v1"` — bump when a row's *meaning* changes.
- `FEATURE_SCHEMA_VERSION = 1` — bump on any change to `FEATURE_COLUMNS`.
- `SCORING_RUBRIC_VERSION = 1` — mirrors `scoring/readiness.py`; bump only
  when weights/thresholds/ladders change. `readiness_score` (the target)
  is not comparable across rubric versions.
- All three are written into the export's `.meta.json` sidecar and shown
  in the quality report. The DB is unchanged; the documented process
  when the rubric changes is "bump `SCORING_RUBRIC_VERSION`, re-collect,
  do not mix". Adding a real `scoring_rubric_version` DB column stays a
  future option (see `docs/ML_NOTES.md` §4) — deliberately not done here.

*Dataset builder (`dataset/builder.py`):*
- `build_dataset(session_factory=SessionLocal) -> DatasetBuildResult`.
  Explicit SQLAlchemy `select(...)` naming every column (feature, target,
  plus the four internal-only columns) — **no `SELECT *`, no post-hoc
  column dropping.**
- One row per user = the **latest valid snapshot**: sort by
  `(collected_at, snapshot_id)` ascending, `groupby("user_id").tail(1)`.
  The `snapshot_id` tie-break makes selection deterministic even when two
  snapshots share a `collected_at`.
- Deterministic dataset row order: ascending `github_username`, applied
  before `github_username` is dropped.
- Detects duplicate users (snapshots-per-user > 1) and reports the count
  + usernames — does not error on them (that's the point of "latest
  snapshot").
- `_coerce_dtypes` normalises: numerics via `pd.to_numeric(errors=raise)`,
  booleans to `bool`, `most_used_language` to pandas `category` over
  strings with `""` for any missing value (never null).
- Runs `validate_frame` on its own output; a malformed frame raises
  rather than returning silently-broken data.
- Empty database → empty-but-valid frame (right columns, zero rows), not
  an error.
- `DatasetBuildResult` carries `frame`, `raw_snapshot_count`,
  `selected_row_count`, `unique_user_count`, `duplicate_user_count`,
  `duplicate_usernames`, and the three version properties.

*Quality report (`dataset/report.py`):*
- `dataset_quality_report(result) -> dict` — versions, unique users,
  rows before/after latest-snapshot selection, duplicate users, per-column
  missing-value counts, feature dtypes, target distribution
  (min/max/mean/std/quantiles + a fixed 0–100 by-tens histogram),
  `describe()` numeric summary, `most_used_language` value counts
  (including the `""` sentinel), and constant / near-constant features
  (dominant value share ≥ 0.95).
- `format_report(report) -> str` — human-readable text block for the CLIs.
- Empty-dataset-safe (distribution sections collapse to `{}`).

*Deterministic export (`dataset/export.py`):*
- `export_dataset(result_or_frame, path=None, *, write_meta=True) -> Path`.
  Writes `data/processed/gitscore_dataset_v1.csv` by default: fixed column
  order, fixed row order, `\n` line endings, `index=False`. Two exports of
  the same database are byte-identical (tested).
- `<name>.meta.json` sidecar: the three versions, row grain, source,
  column lists, counts, and a `built_at_utc` timestamp. The timestamp
  makes the *meta* file non-deterministic on purpose; the CSV is the
  reproducible artifact. `write_meta=False` skips it.
- Both land under `data/processed/` (already gitignored).

*Collection input (`dataset/collection_input.py`, replaces the hardcoded
list in `scripts/collect_dataset.py`):*
- `parse_usernames(text)` / `load_username_file(path)` — one username per
  line; ignore blank lines and `#` comment lines; strip inline `#…`
  comments; de-duplicate case-insensitively (first spelling wins);
  preserve first-occurrence order. `UsernameFileError` (clear message
  pointing at the example file) when the file is missing.
- `scripts/collect_dataset.py` — rewritten. Reads
  `data/collection/usernames.txt` (or `argv[1]`), continues across
  ordinary per-user failures, prints per-user status + a final
  succeeded/failed/attempted/elapsed summary + a failure list. Exit code
  0 (all ok) / 2 (finished with failures) / 1 (could not start). Only
  exception *type + message* is printed — never the token (and
  GitHubClient messages carry URL/status, not credentials; a test pins
  this).
- `data/collection/usernames.example.txt` — committed template
  (comments only, no real list). `data/collection/usernames.txt` is
  gitignored.

*New scripts:*
- `scripts/build_dataset.py` — build + report + export (`argv[1]`
  optional output path). Exits 1 with "nothing exported" on an empty DB.
- `scripts/dataset_report.py` — report only, no file writes.
- `scripts/show_dataset.py` — unchanged; still a raw `SELECT *` *inspection*
  tool, explicitly **not** the dataset path (documented in
  `docs/PIPELINE.md` Stage 6).

*Tests (`tests/`, +65, suite 166 → 231, all passing, still offline):*
- `tests/conftest.py` — added `PROFILE_FEATURE_DEFAULTS`, a `SnapshotDB`
  helper, and the `snapshot_db` fixture: a throwaway per-test SQLite
  database with the real `User`/`ProfileFeature` schema and an
  `add_snapshot(username, *, collected_at=None, **feature_overrides)`
  method. Never touches `data/gitscore.db`.
- `tests/test_dataset_schema.py` (17) — contract shape (partition
  complete & disjoint, no id/timestamp columns, excluded-columns map)
  and every `validate_frame` path (missing/extra/reordered column,
  identifier present, nulls, non-numeric, null categorical, `""`
  sentinel allowed, empty allowed/disallowed).
- `tests/test_dataset_builder.py` (17) — empty DB, latest-snapshot
  selection incl. `collected_at`-tie → `snapshot_id` tie-break, duplicate
  detection, deterministic ascending-username row order, repeated builds
  `assert_frame_equal`, exact column set/order, value round-trip from DB,
  **no identifier column leaks**, **no timestamp column leaks**,
  username only affects ordering, `most_used_language` preserved as
  `category`, `""` sentinel survives, builder validates its own output.
- `tests/test_dataset_export.py` (6) — CSV+meta written, header == schema
  columns, byte-for-byte determinism, LF endings, no identifier columns
  in the header, empty dataset → header-only CSV.
- `tests/test_dataset_report.py` (8) — empty-safe, before/after counts,
  target distribution, `""` in language distribution, constant vs
  near-constant flagging, dtype coverage, no missing values on clean
  data, formatter mentions versions.
- `tests/test_collection_input.py` (12) — blank lines, full-line and
  inline comments, case-insensitive dedup, order preservation, first-token
  fallback, empty input, `load_username_file` happy path + missing-file
  error, and that the committed example template parses to zero usernames.
- `tests/test_collect_dataset_script.py` (5) — continues across per-user
  failures + reports, all-success → exit 0, missing file → exit 1, empty
  list → exit 1, and the token is never printed.

*Docs:* this entry; `docs/ARCHITECTURE.md` §1/§11 + new §12;
`docs/PIPELINE.md` Stages 6/6b/9; `docs/ML_NOTES.md` new §8 (+ §4/§6/§7
cross-refs); `README.md` (dataset build/report commands, usernames.txt
input, CSV is a gitignored derived artifact).

**Why:** first step of the ML track from `CLAUDE.md`'s priority order —
"robust dataset creation" + "ML dataset preparation" — building the
reproducible pipeline *before* any real collection or model training, so
the dataset has a defined contract, a leakage policy, versioning, and
quality tooling from row one.

**Risks / limitations:**
- **`SCORING_RUBRIC_VERSION` is a code constant, not a DB column.**
  Nothing stamps the rubric version onto historical rows; the "don't mix
  rubric versions" policy is enforced by discipline + re-collection, not
  by the data. Adding the column remains the documented upgrade
  (`docs/ML_NOTES.md` §4) if the rubric starts changing.
- The builder trusts `ProfileFeature`'s `nullable=False` columns to
  actually be non-null (SQLite enforces this). `validate_frame` is the
  backstop if that ever changes; the null-path test injects the failure
  via a monkeypatched coercion step rather than a real null (SQLite won't
  store one).
- Pre-existing `datetime.utcnow` `DeprecationWarning`s (from
  `db/models.py`, unchanged this milestone) now surface in the new
  dataset tests' output. Not an error; not fixed here (would touch the DB
  layer, out of scope).
- `data/processed/gitscore_dataset_v1.csv` + `.meta.json` are the only
  outputs; both are gitignored. No dataset was actually built from real
  GitHub data — the dev DB still holds only the 13 pre-fix rows
  (`docs/ML_NOTES.md` §7).
- CSV floats use pandas' default `repr` (round-trips, deterministic on
  CPython); no fixed decimal formatting was imposed.

**How to test it:**
```
cd gitscore-ai
pytest
```
Expected: 231 passed.

Smoke test (no real collection):
```
python scripts/dataset_report.py            # read-only, against data/gitscore.db
python scripts/build_dataset.py             # writes data/processed/gitscore_dataset_v1.csv (gitignored)
```

---

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
