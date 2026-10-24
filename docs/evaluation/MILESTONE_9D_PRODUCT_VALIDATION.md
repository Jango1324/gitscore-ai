# Milestone 9D — Product Validation & Trustworthiness Pilot

**Status: validation only.** No production code under `src/gitscore/`
or `frontend/` was modified. No matcher, scoring formula, concept
registry, repository ranking, retrieval, or API/frontend contract was
touched. No frozen gold under `evaluation/gold/`, `evaluation/gold_v1_1/`,
or `evaluation/m9b/` was modified. Three new, additive, evaluation-only
artifacts were added: `scripts/evaluate_m9d_pilot_cohort.py` (the harness
that produced every number in §4, mirroring the precedent set by
`scripts/evaluate_end_to_end_job_aware.py` in M8E) and its output
`evaluation/reports/m9d_pilot_cohort_report.json`; and
`scripts/m9d_serve_offline_fixture.py`, a small FastAPI dependency-override
harness that serves the real API against one offline candidate fixture
(no live GitHub call) — used this session to live-verify the API process
itself (§5), and left as ready-made tooling for the browser-level
click-through this milestone could not complete (§11, §12). None
is wired into any other script. Not committed, not pushed.

---

## 1. Verified baseline (Phase 0)

| Check | Result |
|---|---|
| HEAD at start | `c8a64ed` ("feat: add assessment transparency and parser diagnostics" — M9C) |
| Working tree | clean |
| `python -m pytest` | **920 passed**, 0 failed, 70 warnings (pre-existing `datetime.utcnow()`/httpx deprecations, unrelated) — matches the expected ~920 baseline exactly |
| `cd frontend && npm test` (vitest) | **29 passed** (2 test files) — matches the expected ~29 baseline exactly |
| Python | 3.14.0 |
| pytest | 9.1.1 |
| Node / vitest | vitest v5.0.3 |
| `JOB_DESCRIPTION_PARSER_VERSION` | `job_description_parser:v4` |
| `JOB_REQUIREMENT_SCHEMA_VERSION` | `2` |
| `MATCHER_VERSION` | `requirement_matcher:v1` |
| `SCORING_VERSION` | `github_evidence_alignment:v1` |
| `CONCEPT_REGISTRY_VERSION` | `4` |
| `EVIDENCE_SCHEMA_VERSION` | `2` |
| `REPOSITORY_RANKING_VERSION` / `JOB_RELEVANCE_VERSION` | `1` / `1` |

Baseline matches M9C's recorded end state exactly. No blocker — proceeded
past Phase 0.

Read before this milestone's own work began: `docs/ARCHITECTURE.md`
§§14–29 (evidence model through M9C's transparency layer),
`docs/PIPELINE.md` (full, including the V2/job-fit/API/frontend
sections), `docs/evaluation/MILESTONE_8E_CONSOLIDATED_EVALUATION.md`,
`MILESTONE_9A_REQUIREMENT_PRESERVATION.md`,
`MILESTONE_9B_EVALUATION_INTEGRITY.md`,
`MILESTONE_9C_ASSESSMENT_TRANSPARENCY.md`, `evaluation/README.md`,
`evaluation/gold/matrix.json`, the job parser/matcher/assessment source
(`jobs/parsing/parser.py`, `matching/engine.py`, `assessment/models.py`),
the full API contract (`api/routes.py`, `api/schemas.py`,
`api/serialization.py`, `api/errors.py`), and every frontend component in
the result-rendering path (`ResultView.tsx`, `AlignmentHeadline.tsx`,
`RequirementSection.tsx`, `SubscoreRow.tsx`, `RepositoryCoverage.tsx`,
`EvidenceList.tsx`, `UnparsedClaimsSection.tsx`, `DiagnosticsPanel.tsx`,
`AnalyzePage.tsx`, `ErrorBanner.tsx`, `LoadingNotice.tsx`, `lib/labels.ts`).

---

## 2. Candidate–job scenario selection (Phase 1)

The pilot cohort was defined by scenario before any score was run, using
two sources: (a) the frozen `evaluation/gold/matrix.json`'s own
pre-registered `expected_direction`/`rationale` fields (never GitScore
output), and (b) direct reading of the relevant raw job-description text
for two scenarios the frozen matrix does not cover. Six of eight pairs
reuse the existing matrix (re-run fresh, not re-annotated); two are new
pairs assembled for this milestone, explicitly **not** added to the
frozen matrix file.

| # | Scenario (per the M9D brief) | Candidate × Job | Source | Pre-registered expectation |
|---|---|---|---|---|
| 1 | Strong observable software-job alignment | `torvalds` × `systems_cpp_01` | frozen matrix | positive |
| 2 | Weak observable alignment | `torvalds` × `data_science_01` | frozen matrix | negative |
| 3 | Embedded/firmware role | `Jango1324` × `embedded_firmware_01` | frozen matrix | partial |
| 4 | ML / computer-vision role | `karpathy` × `computer_vision_01` | frozen matrix | partial |
| 5 | Frontend / mobile role | `sindresorhus` × `frontend_01` | frozen matrix | positive |
| 6 | DevOps / platform role | `sindresorhus` × `devops_cloud_01` | **new pair** | none (selected because `sindresorhus` is JS/TS-dominant and `devops_cloud_01` requires AWS/Azure, Docker/Kubernetes, Terraform, Python/Shell — a deliberate domain mismatch worth measuring, not assumed to be negative) |
| 7 | Candidate with limited GitHub evidence | `Jango1324` × `general_swe_01` | frozen matrix | partial (`Jango1324` is the smallest fixture account, 20 discovered repos) |
| 8 | Job with substantial non-GitHub-assessable requirements | `torvalds` × `sre_platform_01` | **new pair** | none (selected because `sre_platform_01`'s raw text has 2 of 6 bullets that are professional-experience/soft-skill claims — "3+ years operating production systems," "on-call experience and incident response" — against a candidate with no Kubernetes/monitoring evidence) |

All eight pairs are drawn from the existing, previously-disclosed
evaluation corpus: `evaluation/jobs/*.json` (synthetic, hand-authored
postings, never copied from a real employer — see each file's
`source_note`) and `evaluation/fixtures/candidates/*.json` (four real,
public GitHub accounts, snapshotted once, per `evaluation/README.md`'s
provenance statement). No live GitHub call was made. No private
candidate data was accessed. All synthetic material is clearly labeled
as such above and in the reproduction script.

**New script, evaluation-only:** `scripts/evaluate_m9d_pilot_cohort.py`
runs the real, unmodified `extract_candidate_evidence()` →
`parse_job_description_with_diagnostics()` → `match_job()` →
`assess_job()` composition (the exact same functions
`gitscore.application.job_fit.analyze_job_fit()` composes, using
job-independent retrieval — the same scope `evaluate_end_to_end.py` and
the frozen matrix already use) against the eight pairs above, and writes
every requirement's status, matched concept ids, **and full supporting
`Evidence` detail** (repository, evidence type, confidence, raw
observation text) plus `unparsed_claims` (M9C's diagnostic) to
`evaluation/reports/m9d_pilot_cohort_report.json`. This additional
evidence-detail and diagnostics capture is new relative to the existing
`evaluate_end_to_end*.py` scripts (which report only counts), because
Phase 2 below requires inspecting the *actual* evidence behind each
verdict, not just the verdict.

---

## 3. Independent technical review methodology (Phase 2)

Per the brief's explicit instruction, GitScore's own output was **not**
used as the gold standard. For each of the 8 pairs:

1. The job's `raw_text` was read directly and independently decomposed
   into its real bullet-level claims, before looking at any parsed
   `JobRequirement` or `unparsed_claims` output.
2. Where a frozen, pre-existing gold annotation already existed for that
   exact job (`evaluation/gold/jobs/*.json` — all 6 job ids used here have
   one), it was cross-checked **as a second, independent, pre-9A-authored
   opinion** (never as ground truth to defer to) — these files predate
   M9A/M9B/M9C's parser-preservation fixes and explicitly mark
   `"notes": "PREDICTED MISS: ..."` for claims the evaluator expected the
   *then-current* parser to drop. Comparing a fresh live run against
   these predictions lets this milestone distinguish "a claim still
   drops, exactly as independently predicted" from "a claim that was
   predicted to drop now resolves correctly" (registry/parser
   improvement) without re-deriving either judgment from GitScore's
   current behavior.
3. For each `SUPPORTED` verdict, the actual `Evidence` objects behind it
   were inspected individually (repository, evidence type — dependency
   manifest / language statistics / README mention —, confidence,
   and the raw observation text) and classified by strength: **direct
   implementation evidence** (a dependency declaration, e.g.
   `torch==2.9.1`), **GitHub language statistics** (a repository's
   reported language-byte percentage), **repository documentation
   claims** (a matched README mention), or **mere mention** (a README
   hit whose surrounding context does not describe the candidate's own
   implementation — e.g. a comparison table or an unrelated usage
   example).
4. Every `NOT_ASSESSABLE`/invisible claim was checked against the raw
   job text to confirm no row (or no *visible* row) exists for it, and
   against `unparsed_claims` to see whether M9C's own diagnostic at least
   surfaces it even when the scored breakdown does not.

This mirrors, and explicitly builds on, the independent-annotation
discipline M9B already formalized for its own 30-entry corpus (gold
authored before running the parser; `ideal_outcome` vs.
`acceptable_fallback` kept distinct; silent drops never silently
resolved by editing gold after seeing output) — M9D applies the same
discipline to a *product-level* (full pipeline, not parser-only) review,
on a cohort chosen for role/scenario diversity rather than parser-edge-case
density.

---

## 4. Evidence-grounding findings (Phase 2 results)

### 4.1 Full pilot cohort results

| Candidate × Job | Scenario | Alignment | Required | Preferred | Coverage |
|---|---|---|---|---|---|
| `torvalds` × `systems_cpp_01` | strong alignment | **67** | 1/1 | 1/2 | 12/12 (complete) |
| `torvalds` × `data_science_01` | weak alignment | **20** | 1/4 | 0/1 | 12/12 (complete) |
| `Jango1324` × `embedded_firmware_01` | embedded/firmware | **0** | 0/4 | 0/1 | 15/20 (incomplete) |
| `karpathy` × `computer_vision_01` | ML/CV | **100** | 3/3 | 1/1 | 15/63 (incomplete) |
| `sindresorhus` × `frontend_01` | frontend | **67** | 4/4 | 0/2 | 15/1142 (incomplete) |
| `sindresorhus` × `devops_cloud_01` | DevOps/platform (new) | **75** | 3/4 | None | 15/1142 (incomplete) |
| `Jango1324` × `general_swe_01` | limited evidence | **100** | 1/1 | None | 15/20 (incomplete) |
| `torvalds` × `sre_platform_01` | non-assessable-heavy (new) | **50** | 1/2 | None | 12/12 (complete) |

Full per-requirement detail, including every supporting `Evidence`
item's repository/type/confidence/raw text, is in
`evaluation/reports/m9d_pilot_cohort_report.json`.

### 4.2 Disputed or notable conclusions

| Job requirement | GitScore status | Evidence reference | Independent judgment | Agreement? |
|---|---|---|---|---|
| "Experience with Linux systems programming" (`systems_cpp_01`, required) | `NOT_ASSESSABLE` (`unresolved_requirement` placeholder) | Candidate's own `linux` repository: 97.83% C, 1.45 GB — the actual Linux kernel | GitHub evidence here is about as strong as this product could ever observe for this exact claim (the account literally owns the repository the claim describes), yet no concept mapping exists for a competency phrase with no named product, so it cannot become `SUPPORTED` | **Agree** with the conservative non-fabrication choice (no concept id ⇒ no capability claim, by design — ARCHITECTURE.md §20.2); **flag** as the clearest concrete illustration found this milestone of the accepted trade-off's cost: self-evident, overwhelming contextual evidence cannot be credited when a requirement is phrased as a skill rather than a named technology. |
| "Experience with OpenCV for image processing" (`computer_vision_01`, required) | **Invisible to the scored breakdown** — appears only in `unparsed_claims`, never as a `JobRequirement` | N/A — no candidate evidence was ever checked against this claim because no row exists | A maximally-informative parser should, at minimum, preserve this as an assessable row (ideally `NOT_OBSERVED`, since none of `karpathy`'s 15 analyzed repositories show an OpenCV dependency or import) | **Disagree** with the current silent-drop outcome. Its concrete effect here: if preserved as `NOT_OBSERVED`, the required subscore becomes 3/4 (75%) instead of the reported 4/4 "required" math currently shown as 3/3 (100%) — a `karpathy`×CV pairing the frozen matrix itself pre-registered as only `"partial"` currently reports a clean **100**. This is not a new defect (M9A/M9B/M9C already measured and disclosed this exact mechanism at 23% corpus-wide); this is a fresh, concrete demonstration of its scoring impact on a real pilot pairing. |
| "Experience with Git-based version control workflows" (`general_swe_01`, required) | **Invisible** — `unparsed_claims` only | N/A | The pre-existing frozen gold for this exact job (`evaluation/gold/jobs/general_swe_01.json`) independently notes this claim is "plausibly inferable from a GitHub account by definition" but still predicts (correctly) that no registry concept exists for it | **Agree** the claim cannot be auto-credited without inventing a "every GitHub account uses git" shortcut the project's own non-fabrication rule would reject; **disagree** that it should vanish without a trace rather than appear as a visible, generically-unassessable row — same root cause as the OpenCV case above, now confirmed on a second, independent job posting. |
| "Experience with AWS or Azure" / Docker half of "Strong experience with Docker and Kubernetes" / "Scripting experience in Python or Shell" (`devops_cloud_01`, all required) | All three **`SUPPORTED`** | AWS: two README mentions — `file-type`'s README describing detecting a file "stored on Amazon S3" (a usage *example* in documentation, not a statement about the candidate's own cloud deployment) and `got`'s README linking to its own TypeScript-support docs page; Docker: one README mention in `got`; Python/Shell: `sublime-autoprefixer`, a 3.5 KB Sublime Text editor plugin, reported as 71% Python | None of this evidence reflects genuine operational AWS/Docker/DevOps-scripting experience — it reflects a prolific JavaScript/TypeScript tooling author whose enormous repository volume (1,142 repos) produces enough incidental textual/language overlap with almost any technology list to clear the matcher's `MINIMUM_SUPPORTING_CONFIDENCE = WEAK` bar (ARCHITECTURE.md §20.3) on 3 of 4 required bullets | **Disagree** that a 75% "GitHub Evidence Alignment" headline is a fair single-number signal for this pairing; **agree** every individual evidence item is itself genuine and correctly attributed (no fabrication — each citation is a real, traceable observation). This is the single most consequential finding of this milestone: it is not a correctness bug (every underlying design decision — WEAK-sufficiency is sufficient, no evidence-type weighting — is already deliberately documented), but it is the clearest demonstration found of how those decisions compound into a misleadingly confident score for a large, topically-unrelated account. See §6.3. |
| "Experience with monitoring and observability tooling" (required) / "On-call experience and incident response" (preferred) (`sre_platform_01`) | **Invisible** — both in `unparsed_claims`; the headline's own `uninterpreted_requirement_count` caveat reports only **1** (the separately-dropped `Terraform` placeholder), not 3 | N/A | The true count of claims GitScore could not confidently interpret for this analysis is **3** (1 visible placeholder + 2 fully-invisible `unparsed_claims`), not the 1 shown next to the score | **Disagree** that the headline caveat communicates the real scope of interpretive uncertainty — confirmed directly in `src/gitscore/api/schemas.py:143-155` (`uninterpreted_requirement_count` is defined and computed only over rows with `interpretation_status == "unparsed_placeholder"`; it structurally excludes `unparsed_claims`, which never become rows at all). See §6.1. |

### 4.3 Evidence-strength classification (requested distinction)

Across all `SUPPORTED` verdicts in the cohort:

| Evidence strength | Example | Frequency in cohort |
|---|---|---|
| Direct implementation evidence (dependency manifest) | `karpathy/autoresearch`: `torch==2.9.1` for `ml.framework.pytorch` | Common for `karpathy` (ML-framework-heavy, Python packaging); present for `language.typescript` via `sindresorhus`'s `devDependencies` |
| GitHub language statistics | `torvalds/linux`: `C: 97.83%` for `language.c` | The dominant evidence type for every strong-alignment pair (`systems_cpp_01`, `computer_vision_01`, `frontend_01`) |
| Repository documentation claims (README mention, implementation context) | `libgit2`'s README: "README mentions 'rust': ... bindings ..." for `language.rust` | Common, generally corroborating a language/framework already also seen via language stats or dependencies |
| Mere mention (README hit with weak/no implementation context) | `file-type`'s README mentioning "Amazon" while describing a usage example, not the author's own AWS use | Found specifically in the `devops_cloud_01` pairing (§4.2); not observed as the *sole* evidence for any requirement in the other 7 pairs |
| Insufficient evidence (correctly `NOT_OBSERVED`) | `Jango1324`'s embedded-firmware repo carries no `unresolved:spi`/`i2c`/`uart` evidence | The majority outcome for `embedded_firmware_01` (5 of 7 requirements) |

No case of **incorrect** evidence (a citation that does not actually
say what the matched concept claims) was found in this cohort — every
`SUPPORTED` match traces to a real, verifiable observation. The risk
identified in §4.2's `devops_cloud_01` row is a **calibration/weighting**
risk (real evidence, insufficiently discriminating), never a
fabrication or misattribution risk.

---

## 5. End-to-end workflow audit (Phase 3)

Verified by direct reading of `src/gitscore/api/{routes,schemas,
serialization,errors}.py` and every frontend component in the
result-rendering path, plus the existing test suites that exercise them
(`tests/test_api_routes.py`, `tests/test_api_serialization.py`,
`frontend/src/components/__tests__/*.test.tsx`).

**Backend/API level — live-verified, not just read.** A new,
evaluation-only script (`scripts/m9d_serve_offline_fixture.py`) serves
the REAL `gitscore.api.app` FastAPI application and overrides its
`get_github_client` test-injection seam (`api/routes.py`) with a fixture-
backed fake client, using the same `build_fake_client()` helper
`evaluate_m9d_pilot_cohort.py` already depends on — zero live GitHub
calls, zero production-code changes. Started on `127.0.0.1:8011` and
exercised with a real `POST /api/v1/analyze` HTTP request (not a
pytest `TestClient`, an actual running process reached over the
network), the response matched the documented contract exactly: correct
`supported`/`not_observed`/`not_assessable` grouping,
`interpretation_status` split, `unparsed_claims` populated and excluded
from `uninterpreted_requirement_count`, and `versions` reported as
expected. This confirms the API process itself — not just its unit
tests — behaves as documented when actually served.

**Frontend level — attempted, did not complete.** The Next.js dev
server was also started (`npm run dev`, pointed at the offline backend
above via `NEXT_PUBLIC_GITSCORE_API_URL`) and confirmed listening on
`localhost:3000`. An actual browser click-through was then attempted via
this session's Chrome browser-automation tool, but the tool did not
respond (`tabs_context_mcp` timed out three consecutive times,
consistent with an unanswered extension-side permission prompt) — see
§11 for what this leaves unverified. Both dev servers were stopped at
the end of this session; §12 gives the exact commands to restart them
for a follow-up hands-on pass.

### 5.1 Can users submit a GitHub username and job description?

Yes, structurally — `AnalyzeForm` → `AnalyzePage.runAnalysis()` →
`POST /api/v1/analyze` (`AnalyzeRequest{github_username, job_description,
job_title?, job_company?}`). Backend validation rejects blank input with
a clean `422 invalid_request` (both Pydantic-level and the domain's own
`ValueError` path render through the identical `ErrorResponse` envelope
— a caller never has to special-case which kind of 422 occurred).

### 5.2 Are loading, failure, and empty-result states understandable?

- **Loading:** a simple four-state model (`idle/loading/success/error`,
  `AnalyzePage.tsx`) renders `LoadingNotice` while the request is in
  flight. Verified in code; its actual visual content/wording was not
  independently re-read against UX best practice beyond confirming it
  renders.
- **Failure:** `gitscore.api.errors` maps every exception the domain
  pipeline can raise to a specific, user-safe message and a `retryable`
  flag (candidate not found → 404, not retryable; GitHub rate limit →
  503, retryable with `Retry-After`; GitHub auth misconfiguration → 500,
  not retryable; unexpected internal error → 500, sanitized, full detail
  server-side-only). `ErrorBanner` renders the server's own message
  verbatim and shows a "Try again" button only when `retryable` is true.
  This is a well-designed, specific error taxonomy — confirmed directly
  in `api/errors.py`'s own exhaustive exception-handler registration.
- **Empty result:** a zero-repository candidate is a **tested**,
  intentional success path, not an error —
  `tests/test_application_job_fit.py::test_zero_repositories_still_produces_a_successful_result`
  confirms `analyze_job_fit()` returns a complete result (every technical
  requirement becomes `NOT_OBSERVED`, never an exception) for a brand-new
  account with 0 repositories. `RepositoryCoverage.tsx` renders a correct,
  specific sentence for this case ("No repositories were discovered on
  this account.") rather than a generic empty-state placeholder.
  `AlignmentHeadline` renders "Not available" (never `0`/`NaN`) when
  zero requirements are assessable at all — confirmed in
  `AlignmentHeadline.tsx`'s own explicit `alignment === null` branch and
  its docstring's explicit null-vs-zero rule.

### 5.3 Are results organized clearly? Required vs. preferred? Sources traceable?

- `SubscoreRow` renders required/preferred counts immediately beneath the
  headline, unconditionally, never collapsed — by explicit design
  (comment cites the M7B "strong headline despite zero required support"
  adversarial case). This directly mitigates the risk class in §6.2
  below, when read.
- Within a single status section (e.g. "Supported by GitHub evidence"),
  individual requirement items are **not** visually grouped by necessity
  — each item shows a small "Required"/"Preferred" label inline
  (`RequirementSection.tsx`/`necessityLabel`), but required and preferred
  items for the same status appear interleaved in the job posting's own
  order, not sorted together. Minor; does not contradict the
  aggregate-level required/preferred co-display above.
- Evidence is **textually** traceable: `EvidenceList.tsx` groups every
  citation by `owner/repo`, shows the evidence type (a human label, e.g.
  "Dependency manifest", "README mention"), confidence, file path when
  applicable, and the raw observation text. It does **not** render a
  clickable link to the actual GitHub repository or file — a user must
  manually navigate to GitHub to verify a citation themselves. Confirmed
  by reading `EvidenceList.tsx` in full: no `<a href>` exists anywhere in
  the component, and `EvidenceItem`'s own fields (repository
  owner/name, file path) are never assembled into a URL.

### 5.4 Are unparsed claims visible? Are GitHub-unassessable requirements explained?

Yes to both, and with carefully differentiated copy (verified directly in
`frontend/src/lib/labels.ts`): a genuinely non-technical claim ("Genuinely
non-technical requirements") is worded distinctly from GitScore's own
parser uncertainty ("Could not be confidently interpreted"), and a fourth,
separate `UnparsedClaimsSection` — rendered only when non-empty — lists
claims that never became a row at all, verbatim, with an explicit
"nothing about the posting is silently hidden" framing. This is a
genuinely strong design; see §6.1 for the one gap found in how it
connects to the headline number.

### 5.5 Can users distinguish alignment from hiring probability?

The product name ("GitHub Evidence Alignment," never "Job Fit Score" /
"Hiring Score" / "Hire Probability") and every piece of copy reviewed
(`labels.ts`, `AlignmentHeadline.tsx`'s own docstring) consistently avoid
competence/hiring-probability framing. No instance of overreaching
language was found anywhere in the reviewed frontend or API surface.
This matches `CLAUDE.md`'s explicit instruction not to claim GitScore
predicts hiring success.

### 5.6 What was NOT independently verified this milestone

- Actual rendered visual presentation (CSS, information density, color,
  responsive layout, whether the headline caveat is visually prominent
  enough to actually be read first) — reading JSX/TSX confirms structure
  and logic, not what a real screen looks like.
- Whether a first-time user can set up and run the local dev
  environment without friction (`npm install`, `.env` configuration,
  `GITHUB_TOKEN` setup) — not exercised end-to-end this milestone.
- Real user comprehension of any of the above — this is exactly what
  Phase 4's human-pilot protocol (§7, full document) exists to measure.

---

## 6. Assessment interpretation risks (Phase 5)

### 6.1 Headline caveat undercounts true interpretive uncertainty (new finding, confirmed in code)

`AssessmentOut.uninterpreted_requirement_count` (`api/schemas.py:142-155`)
is defined, and computed in `api/serialization.py`, as the count of
`not_assessable` requirements whose `interpretation_status ==
"unparsed_placeholder"` — i.e., claims that *did* become a
`JobRequirement` row (M9A's `unresolved_requirement`/
`alternative_requirement` placeholders) but whose concept could not be
resolved. It **excludes** `unparsed_claims` entirely — claims that never
became a row at all (M9C's own, strictly-more-severe category). This
milestone's own `torvalds × sre_platform_01` pairing demonstrates the gap
concretely: the headline caveat reads "1 requirement could not be
confidently interpreted," while a separate, lower section lists 2 more
(`"Experience with monitoring and observability tooling"`, `"On-call
experience and incident response"`) that a reader must scroll past the
entire requirement breakdown to find. The single number placed next to
the score — where a time-pressed reader looks first — undercounts the
analysis's real interpretive uncertainty by 2 of 3 in this example. This
is not a scoring defect (`alignment_score` itself is correctly
unaffected either way, per M9C's own design), but it is a demonstrated
gap in exactly the kind of "communicates uncertainty adequately"
property this milestone was asked to validate.

### 6.2 Small assessable denominators remain volatile (re-confirmed, not new)

`Jango1324 × general_swe_01`'s required subscore is 1/1 (100%) and
`karpathy × computer_vision_01`'s is 3/3 (100%) — both are
denominator-1-or-few cases where a single concept's evidence determines
a 0/100 swing, exactly the pattern M8E's §6 and M9B's §11 already
documented and ranked as a medium-severity interpretability risk. Both
cases in this cohort are *caused*, concretely, by §6.3's silent-drop
mechanism (a real second required bullet that never became an assessable
row) — this milestone newly confirms the causal link on two fresh,
independently-selected pairings, not merely re-stating the prior
finding.

### 6.3 Evidence-sufficiency policy can produce a misleadingly confident score for a large, topically-unrelated account (new finding, most consequential)

`sindresorhus × devops_cloud_01` (§4.2) reports **75%** "GitHub Evidence
Alignment" — a score built almost entirely from README-mention and
tangential-repository evidence, for a candidate whose real, enormous body
of work (1,142 repositories) is JavaScript/TypeScript developer tooling,
not cloud infrastructure. Every contributing design decision is already
deliberate and documented (`MINIMUM_SUPPORTING_CONFIDENCE = WEAK`,
ARCHITECTURE.md §20.3; no evidence-type weighting in scoring, §21.6) —
this is not a new defect. What this milestone adds is a concrete,
real-evidence demonstration that the theoretical risk these design
decisions accept ("a WEAK README mention is sufficient") actually
materializes at a damaging magnitude (a 75, not a marginal 10-20) on a
real account whose repository volume alone is enough to clear the bar on
unrelated technologies. A recruiter who reads only the headline number
has no way to distinguish this pairing from a pairing whose required
evidence is dependency-manifest-grade.

### 6.4 Conservative design cannot credit self-evident contextual evidence (accepted trade-off, newly illustrated)

`torvalds`'s own `linux` repository is, by definition, maximally strong
evidence for "Experience with Linux systems programming" — yet the
requirement renders `NOT_ASSESSABLE` because the claim has no registered
concept mapping (it is a competency phrase, not a named technology). This
is the mirror image of §6.3: here, the product is *too* conservative
relative to what a human reviewer would credit instantly. Both §6.3 and
this finding stem from the same root choice — GitScore never infers
beyond what a `concept_id` lookup can answer — and the product
consistently applies it in both directions (never fabricates toward a
higher score, and never infers toward a higher score from context alone
either). Listed as a known, accepted limitation for completeness, not as
a new defect to fix.

### 6.5 Identical requirement text renders multiple times — including across contradictory statuses — with no visible disambiguation (new finding, confirmed systemic)

Checked directly against `evaluation/reports/m9d_pilot_cohort_report.json`
(the cohort report this milestone already produced for §4, re-inspected
for a pattern suspected from the parser's own documented design — one
raw job-posting sentence legitimately producing more than one
`JobRequirement` row, one per matched concept, same `original_text` —
`ARCHITECTURE.md` §28, M9A). Grouping each pairing's requirements by
`text` and counting duplicates: **4 of the 8 pilot pairs exhibit this**,
not an isolated case:

| Candidate × Job | Duplicated requirement text | Rows behind it | Rendered statuses |
|---|---|---|---|
| `torvalds` × `data_science_01` | "Experience with Python, pandas, and numpy" | `language.python`, `data.library.pandas`, `unresolved:numpy` | **Supported** (Python) *and* **Not observed** (pandas, numpy) — same sentence, both sections |
| `Jango1324` × `embedded_firmware_01` | "Familiarity with microcontroller peripherals such as SPI, I2C, and UART" | `unresolved:spi`, `unresolved:i2c`, `unresolved:uart` | Not observed, ×3, identical text, no distinguishing label |
| `sindresorhus` × `frontend_01` | "Strong proficiency in JavaScript and TypeScript" | `language.javascript`, `language.typescript` | Supported, ×2, identical text |
| `sindresorhus` × `devops_cloud_01` | "Strong experience with Docker and Kubernetes" | `infra.docker`, `infra.kubernetes` | **Supported** (Docker) *and* **Not observed** (Kubernetes) — same sentence, both sections |

Root cause, confirmed in `api/schemas.py`/`RequirementOut` and
`frontend/src/components/RequirementSection.tsx`: the API already
carries `concept_id`/`matched_concept_ids` distinguishing each row, but
`RequirementItemsList` (the shared rendering helper both plain sections
and each not-assessable subsection call) renders only `requirement.text`
— never the concept id or a human label for it. A user sees either
(a) the same bullet repeated verbatim within one section with no way to
tell it apart from a rendering bug, or, more seriously, (b) the
**identical sentence appearing under "Supported by GitHub evidence" and
"Not observed" at the same time** (the `data_science_01` and
`devops_cloud_01` rows above) — which reads as a direct self-
contradiction rather than two different concepts sharing one raw-text
sentence. This is strictly a presentation gap, not a backend defect: the
domain model's "one row per matched concept, same original text" design
is itself correct and already documented (M9A); nothing here recommends
changing it.

This finding directly affects this milestone's own Phase 4 materials:
Task 2 of `M9D_HUMAN_PILOT_PROTOCOL.md` uses the `torvalds ×
data_science_01` "Not observed" section as its example — and the
candidate's own "Experience with Python, pandas, and numpy" also appears
one section up, under "Supported," which a participant may notice and
be confused by. Flagged as an added observer note in that document
rather than changing the task's real-data material.

### 6.6 Already-disclosed risks re-confirmed, not re-litigated

Repository-retrieval crowding (M8D.2/M8E/M9B), the un-resolved 23%
silent-drop disposition decision (M9C §12, still open), and
`end_to_end_report.json`'s pre-existing staleness (M9B §10.2, M9C §11) —
all unchanged by this milestone; cited, not re-measured.

---

## 7. Human-review pilot protocol summary (Phase 4)

Full materials: `docs/evaluation/M9D_HUMAN_PILOT_PROTOCOL.md`. Summary:
a ~30-45 minute session for 3-5 volunteer participants (engineering
students, software developers, and — if available — a technical hiring
manager/recruiter), using two real pilot-cohort results from §4.1 as
session materials (`karpathy × computer_vision_01` for the high-score
task, `torvalds × sre_platform_01` for the parser-uncertainty task), five
structured tasks (interpret a high alignment score; explain a
`NOT_OBSERVED` requirement; explain a `NOT_ASSESSABLE` requirement;
identify parser uncertainty; verify whether repository evidence supports
a specific claim), a feedback questionnaire (understanding, perceived
clarity, evidence traceability, trust calibration, usability, most
confusing feature), a structured observation sheet, and success criteria
defined before running the study. No participants were recruited,
contacted, or simulated — this is a protocol for the project owner to
run, not a completed study.

---

## 8. Product-risk register (Phase 6)

Ranked by user impact × correctness risk × frequency. Confidence
reflects how directly each finding was verified this milestone (code
read + live reproduction = CONFIRMED; code read only, not exercised =
PLAUSIBLE; genuinely requires human testing = HYPOTHESIZED).

| # | Finding | Category | Severity | Confidence | Evidence | Mitigation | Complexity |
|---|---|---|---|---|---|---|---|
| 1 | Headline `uninterpreted_requirement_count` excludes `unparsed_claims`, undercounting true interpretive uncertainty (§6.1) | Demonstrated defect (transparency gap, not a scoring bug) | Medium-High | **CONFIRMED** (code: `api/schemas.py:142-155`; reproduced live in `torvalds×sre_platform_01`: 1 shown vs. 3 real) | `evaluation/reports/m9d_pilot_cohort_report.json` | Include `unparsed_claims` in the headline caveat count (or add a second, equally prominent count) | Low |
| 2 | Evidence-sufficiency policy + large/unrelated account volume can produce a misleadingly confident headline score (§6.3) | Demonstrated defect (calibration, not fabrication) | High | **CONFIRMED** (live evidence trace, `sindresorhus×devops_cloud_01`, alignment=75) | `m9d_pilot_cohort_report.json`; §4.2/§4.3 | A presentation-layer evidence-strength signal (e.g. visually distinguish dependency/language-stat evidence from README-mention-only evidence for required concepts) without changing the scoring formula | Medium |
| 3 | Entire-requirement silent drop (23% corpus-wide, M9B) continues to shrink/inflate denominators in fresh pairings (§6.2, §4.2) | Reproducible limitation (already disclosed, newly re-confirmed on new pairs) | High | **CONFIRMED** (live: `karpathy×computer_vision_01`, `Jango1324×general_swe_01`, `torvalds×sre_platform_01`) | §4.2 table | M9C §12's own still-open recommendation: either a scoped shape-only detector, or a permanent, explicit UI disclosure of "this score may cover fewer requirements than the posting lists" | Medium (detector) / Low (disclosure) |
| 4 | Evidence citations are not clickable links to GitHub (§5.3) | Reproducible usability limitation | Low-Medium | **CONFIRMED** (code: `EvidenceList.tsx`, no `<a href>`) | — | Render `https://github.com/{owner}/{name}` (+ file path where present) as a link | Low |
| 5 | Required/preferred items interleaved rather than grouped within a status section (§5.3) | Reproducible usability limitation | Low | **CONFIRMED** (code: `RequirementSection.tsx`) | — | Sort or visually group by necessity within each section | Low |
| 6 | Conservative design cannot credit strong contextual evidence for competency-phrased requirements (§6.4) | Accepted design trade-off, not a defect | — | **CONFIRMED**, but intentional | `torvalds×systems_cpp_01` | None recommended — the alternative (inferring beyond `concept_id` lookups) reintroduces fabrication risk the project has repeatedly, deliberately rejected | N/A |
| 7 | Real users may not notice/correctly interpret the headline caveat, the two `not_assessable` subsections, or the alignment/hiring-probability distinction | Hypothesized concern | Unknown | **HYPOTHESIZED** — requires human testing | — | Run the Phase 4 pilot protocol (§7) | N/A (research, not a code change) |
| 8 | Local dev-environment first-run experience (setup friction, actual rendered UI) unverified this session | Hypothesized concern / audit gap | Unknown | **HYPOTHESIZED** | §5.6, §11 | Hands-on click-through by the project owner or a follow-up session with working dev-server access | N/A |
| 9 | Repository-retrieval crowding (M8D.2/M8E/M9B) | Already-disclosed, large-scope architectural limitation | Medium-High | CONFIRMED (prior milestones; not re-measured) | cited | Already flagged "LARGE, needs product judgment" — no new information this milestone | High |
| 10 | `end_to_end_report.json` staleness (M9B §10.2) | Already-disclosed process/maintenance risk | Low-Medium | CONFIRMED (prior milestones; not touched — preserved as historical per this milestone's instructions) | cited | Regenerate with a changelog note, or add an automated staleness-check CI gate (`check_evaluation_staleness.py` already exists, exit code always 0 today) | Low |
| 11 | Identical requirement text renders multiple times, including simultaneously under "Supported" and "Not observed," with no visible concept label to disambiguate (§6.5) | Demonstrated, reproducible usability limitation | Medium | **CONFIRMED** (live: `evaluation/reports/m9d_pilot_cohort_report.json`, systemic in 4 of 8 pairs; code: `RequirementSection.tsx`'s `RequirementItemsList` renders only `requirement.text`) | §6.5 table | Append a short, human-readable concept label to each row's displayed text when more than one row in the same section shares identical text (e.g. "Strong experience with Docker and Kubernetes (Kubernetes)") — API already carries `concept_id`; presentation-only change | Low |

Nothing above is labeled a confirmed defect without having been either
directly read in source code or reproduced live against the real
pipeline this milestone; items 7-8 are explicitly marked hypothesized,
not demonstrated.

---

## 9. Top five prioritized improvements

1. **Fold `unparsed_claims` into the headline interpretive-uncertainty
   signal** (risk #1) — the single lowest-complexity, highest-trust-impact
   fix available: a reader should never see a smaller number at the top
   of the page than the real count of claims GitScore could not
   interpret.
2. **Add a presentation-layer evidence-strength distinction for required
   concepts** (risk #2) — directly targets the most consequential finding
   in this report (a real account can clear "75% required" almost
   entirely on README-mention-grade evidence) without touching the
   scoring formula or the WEAK-sufficiency policy itself.
3. **Resolve the 23%-silent-drop disposition decision** that M9C §12
   already raised and left open (risk #3) — either a scoped,
   shape-only detector (per M9B §12's own suggested design) or a
   permanent, explicit "this score may be based on fewer requirements
   than the posting lists" disclosure. Either answer is better than
   leaving the decision point open across a fourth milestone.
4. **Two small, additive `RequirementSection`/`EvidenceList` presentation
   fixes, bundled** — make evidence citations clickable links to GitHub
   (risk #4), and append a short concept label to duplicate-looking
   requirement text so identical sentences never render as an apparent
   self-contradiction across "Supported"/"Not observed" (risk #11,
   §6.5 — confirmed systemic in 4 of 8 pilot pairs, including one that
   is itself human-pilot session material). Both are low complexity,
   presentation-only, and directly improve "traceability" and
   "evidence-grounding clarity" — the exact properties this milestone
   was asked to validate.
5. **Run the Phase 4 human pilot before investing further in UI
   copy or scoring changes** — every code-level finding above has been
   verified; the single biggest remaining unknown is whether real users
   (students, developers, recruiters) actually interpret the existing,
   carefully-designed distinctions (`NOT_OBSERVED` vs. `NOT_ASSESSABLE`
   vs. unparsed) the way the product intends. No further design
   investment should be prioritized over getting that signal.

---

## 10. Recommended next milestone

**Primary recommendation: run the Phase 4 human pilot (M9D's own
deliverable) in parallel with a small, scoped "Milestone 9E — Headline
Transparency & Evidence-Strength Signaling"** covering improvements #1
and #4 above (both low-complexity, additive, presentation-layer-only
changes with no scoring-formula or matcher impact — #4 itself bundles
the clickable-evidence-link and duplicate-requirement-text-label fixes,
risks #4 and #11) plus a STOP-point decision on improvement #3's
disposition (per `CLAUDE.md`'s Code Change Workflow, present options
before implementing).

Rationale: #1 and #4 are exactly the kind of small, mechanical,
additive, low-risk fixes this project's own milestone history (M8D.1,
M9A) has consistently preferred over large redesigns; #3 needs an
explicit decision, not another milestone's worth of deferral; and the
human pilot is independent, additive research that can run on the
*current* UI without waiting for #1/#4 to land, so nothing blocks on
anything else. Risk #2 (evidence-strength signaling) is correctly
**not** bundled into this immediate next milestone — it is Medium
complexity and touches more of the presentation layer; it should follow
once the human pilot's results are in, since participant feedback on
trust calibration (questionnaire dimension, §7) may directly inform how
that signal should be designed.

**Explicitly deprioritized:** retrieval crowding (risk #9, still
correctly flagged "LARGE" scope); any LLM-based scoring, CatBoost, or
role-specific/market-aware scoring (explicitly out of scope per
`CLAUDE.md`'s MVP-first priority order and this milestone's own
constraints); `end_to_end_report.json`'s staleness (risk #10, low
severity, no new urgency found).

---

## 11. Limitations and confidence levels

- **Small, fixed corpus.** All findings are measured against 4 real
  GitHub accounts, 15 synthetic job postings, and this milestone's own
  8 pilot pairs (6 reused from the frozen 12-pair matrix). Every count
  and percentage in this report is a precise measurement on this fixed
  corpus, never an estimate of a broader population — consistent with
  every prior evaluation milestone's own disclosed limitation (M8E §4).
- **No ground-truth "true fit" label exists**, here or in any prior
  milestone's corpus. This report evaluates evidence-grounding fidelity
  and interpretability, never a precision/recall number against a real
  hiring outcome — no such label exists or was fabricated.
- **Browser-rendered UI testing was not completed this session; the live
  backend/API was.** §5 verified the actual, running FastAPI process
  (not just its unit tests) over a real HTTP request using the offline
  fixture-backed harness (`scripts/m9d_serve_offline_fixture.py`), and
  separately confirmed the Next.js dev server starts and listens. The
  remaining gap is specifically the browser click-through: this
  session's Chrome browser-automation tool did not respond
  (`tabs_context_mcp` timed out three times). Actual rendered appearance,
  information density, and whether a real user's eye lands on the
  headline caveat before the detailed sections remain genuinely
  unverified and are exactly what Phase 4's human pilot (§7) is designed
  to surface.
- **No participants were recruited or simulated.** Phase 4 produced a
  protocol only, per the milestone's explicit instruction. Every
  "real user" statement in this report is phrased as a risk or a
  hypothesis requiring the pilot, never as a finding about actual users.
- **AI-generated judgments are internal audit findings, not validated
  independent human labels** — every "independent judgment" in §4.2's
  table is this review's own reasoning from the raw job text and raw
  evidence, cross-checked against a pre-existing frozen gold annotation
  where one exists, but it is not a second human reviewer's opinion.
- **The scoring formula, matcher, concept registry, and retrieval logic
  were not modified or re-evaluated for correctness** — this milestone
  validates how existing, already-tested behavior presents and reads as
  a product, not whether the underlying analytical logic itself is
  correct (that was M7A/M7B/M8D.1-3/M9A's own scope).

---

## 12. Reproduction instructions

```powershell
# Phase 0 baseline
git status --short
git log -5 --oneline
python -m pytest                                               # 920 passed
cd frontend; npm test; cd ..                                    # 29 passed

# Phase 1/2 -- this milestone's own pilot cohort (new, additive script)
cd scripts
python evaluate_m9d_pilot_cohort.py
cd ..
# Writes evaluation/reports/m9d_pilot_cohort_report.json (full requirement
# + evidence + unparsed_claims detail for all 8 pairs in Section 2 above)

# Cross-reference: existing, unmodified harnesses (cited, not re-derived)
python scripts/evaluate_end_to_end_job_aware.py
python scripts/evaluate_m9b_preservation.py
python scripts/check_evaluation_staleness.py

# Final verification
python -m pytest
git diff --check
git status --short
git diff --stat
```

Running `evaluate_m9d_pilot_cohort.py` is read-only against
`evaluation/jobs/` and `evaluation/fixtures/candidates/` and writes only
its own new report file — it does not touch any existing committed
report, any frozen gold directory, or any file under `src/` or
`frontend/`.

**To complete the hands-on browser click-through this session could not
finish** (§5, §11) — run the real backend against an offline fixture
(no live GitHub call) and the real frontend against it:

```powershell
# Terminal 1 -- real API, fixture-backed, zero GitHub calls
python scripts/m9d_serve_offline_fixture.py torvalds --port 8011

# Terminal 2 -- real Next.js dev server, pointed at the offline backend
cd frontend
$env:NEXT_PUBLIC_GITSCORE_API_URL = "http://127.0.0.1:8011"
npm run dev
# open http://localhost:3000 -- any GitHub username submitted returns
# the `torvalds` fixture's real evidence regardless of what's typed
# (single-fixture-per-process harness, see the script's own docstring)
```

---

## End-of-milestone verification

```
python -m pytest           -> 920 passed, 0 failed
git diff --check           -> (no output: no whitespace errors)
git status --short         -> new, untracked files only:
                               scripts/evaluate_m9d_pilot_cohort.py
                               scripts/m9d_serve_offline_fixture.py
                               evaluation/reports/m9d_pilot_cohort_report.json
                               docs/evaluation/MILESTONE_9D_PRODUCT_VALIDATION.md
                               docs/evaluation/M9D_HUMAN_PILOT_PROTOCOL.md
                               docs/CHANGELOG_DEV.md (modified -- this milestone's own entry)
git diff --stat             -> docs/CHANGELOG_DEV.md only; no other tracked file touched
```

**No production code, frozen gold, API contract, or frontend file was
modified.**

**DO NOT COMMIT. DO NOT PUSH.**
