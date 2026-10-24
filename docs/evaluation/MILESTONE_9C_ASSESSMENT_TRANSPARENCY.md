# Milestone 9C — Assessment Transparency & Requirement Coverage

**Status: implemented.** No matcher semantic change
(`gitscore.matching` is byte-for-byte unchanged), no scoring-formula
change (`gitscore.assessment` is byte-for-byte unchanged), no concept
registry change, no frozen-gold change, no M5B ranking change, no M8D.2
retrieval change. `JOB_REQUIREMENT_SCHEMA_VERSION`, `MATCHER_VERSION`,
`SCORING_VERSION`, `CONCEPT_REGISTRY_VERSION`,
`REPOSITORY_RANKING_VERSION`, and `JOB_RELEVANCE_VERSION` are all
unchanged. `JOB_DESCRIPTION_PARSER_VERSION` is unchanged
(`parse_job_description()` itself produces byte-for-byte identical
output to before this milestone — confirmed directly, §8). Not
committed, not pushed.

---

## 1. Baseline

| Check | Result |
|---|---|
| HEAD at start | `ae38ed7` ("test: add requirement coverage and retrieval sensitivity benchmarks" — M9B) |
| Working tree | clean |
| `python -m pytest` | **904 passed**, 0 failed (matches the expected baseline exactly) |
| `JOB_DESCRIPTION_PARSER_VERSION` | `job_description_parser:v4` |
| `JOB_REQUIREMENT_SCHEMA_VERSION` | `2` |
| `MATCHER_VERSION` | `requirement_matcher:v1` |
| `SCORING_VERSION` | `github_evidence_alignment:v1` |
| `CONCEPT_REGISTRY_VERSION` | `4` |
| `EVIDENCE_SCHEMA_VERSION` | `2` |
| `REPOSITORY_RANKING_VERSION` / `JOB_RELEVANCE_VERSION` | `1` / `1` |

Read before design work began: `MILESTONE_9A_REQUIREMENT_PRESERVATION.md`,
`MILESTONE_9B_EVALUATION_INTEGRITY.md`, `MILESTONE_8E_CONSOLIDATED_EVALUATION.md`,
and — read directly, not from memory — `jobs/parsing/parser.py`,
`matching/engine.py`, `matching/models.py`, `matching/types.py`,
`assessment/models.py`, `assessment/engine.py`, `api/schemas.py`,
`api/serialization.py`, `frontend/src/components/{RequirementSection,ResultView,AlignmentHeadline}.tsx`,
`frontend/src/lib/labels.ts`, `frontend/src/types/api.ts`.

---

## 2. Root-cause analysis (Phase 1 design audit)

Traced the full data flow: raw text → `segment_description()` →
`_requirements_from_claim()` → `JobRequirement` → `match_requirement()` →
`RequirementMatch` → `assess_job()` → `serialize_job_analysis_result()` →
`AnalyzeResponse` → `ResultView`.

**Finding 1 — information is not lost in the domain model; it is lost
at the API serialization boundary.** `JobRequirement.category` already
distinguishes a genuine non-technical claim (`"experience"`,
`"education"`, `"soft_skill"`, `"leadership"`) from a parser-uncertainty
placeholder (`"unresolved_requirement"`, `"alternative_requirement"`)
all the way through `RequirementMatch.requirement` — but
`serialize_requirement_match()` never put `category` on the wire, so
both kinds rendered with the identical `not_assessable` sentence.

**Finding 2 — a claim can be lost before the domain model ever sees
it, and this is categorically different from Finding 1.** Milestone
9B's own benchmark measured 6 of 26 corpus claims producing **zero**
`JobRequirement` rows — `_requirements_from_claim()` returns `[]` for
them even though `segment_description()` already judged them
requirement-shaped. There is no object anywhere to attach `category`,
`concept_id`, or a `MatchStatus` to. This is strictly worse than the
Milestone 9A `unresolved_requirement` placeholder (which DOES produce a
real, inspectable row) and needed its own representation.

---

## 3. Design and dependency direction (approved decisions)

Four STOP-point decisions were presented with options, migration
implications, and test impact, per this milestone's own instruction;
all four recommended options were approved before any implementation:

| Decision | Approved option |
|---|---|
| **A** — extraction diagnostics representation | New field on `JobAnalysisResult` only, via a new `parse_job_description_with_diagnostics()` sibling function. `parse_job_description()` itself stays byte-for-byte unchanged. Mirrors the `ExtractionFailure`/`extractor_failures` precedent (Milestone 5D) exactly. |
| **B** — API field design | Raw `category` passthrough + a derived, backend-computed `interpretation_status` enum, so the classification rule lives in exactly one tested place (never duplicated in TypeScript). |
| **C** — UI transparency scope | Split `not_assessable` into two subsections + a headline caveat count + a fourth, clearly-separate `unparsed_claims` list. Nothing here reads or changes `alignment_score`. |
| **D** — silent-drop (23% gap) scope | Visibility only, zero new classification risk — report (via Decision A) exactly the claims that already survive segmentation's existing, unmodified gate but still produce zero rows. No regex/vocabulary broadening. The 23% gap itself is NOT reduced by this milestone. |

**Dependency direction:** `jobs.parsing.parser` gained `UnparsedClaim`/
`ParsedJobDescription`/`parse_job_description_with_diagnostics` with no
new external dependency. `application.job_fit` is the only caller of
the new function (mirroring its own "the one layer allowed to know
about all of them together" precedent from Milestone 8D.2).
`api.serialization` is the only place `_interpretation_status()` is
computed. No package gained a dependency on a package it didn't already
depend on.

---

## 4. Domain and API decisions — implementation detail

### 4.1 `UnparsedClaim` (`jobs/parsing/parser.py`)

```python
@dataclass(frozen=True)
class UnparsedClaim:
    text: str
    source_span: SourceSpan
```

Both `parse_job_description()` and `parse_job_description_with_diagnostics()`
now call one shared `_parse()` implementation — no duplicated logic, and
`parse_job_description()`'s own signature/behavior is provably
unaffected (§8).

### 4.2 `interpretation_status` (`api/serialization.py`)

```python
def _interpretation_status(match: RequirementMatch) -> str:
    if match.status != MatchStatus.NOT_ASSESSABLE:
        return "recognized"
    if match.requirement.category in {"unresolved_requirement", "alternative_requirement"}:
        return "unparsed_placeholder"
    return "non_technical"
```

One function, three outcomes, zero new `MatchStatus` members.

### 4.3 API schema additions (`api/schemas.py`) — all additive

- `RequirementOut.category: str | None`
- `RequirementOut.interpretation_status: str`
- `AssessmentOut.uninterpreted_requirement_count: int`
- `UnparsedClaimOut.text: str` (new model)
- `AnalyzeResponse.unparsed_claims: list[UnparsedClaimOut]`

No existing field renamed, retyped, or removed.

---

## 5. Source text and provenance retention

Every `UnparsedClaim` retains `text` (verbatim claim text) and
`source_span` (exact offsets into the raw job description) — the same
provenance discipline `SourceSpan`/`JobRequirement.original_text`
already apply everywhere else in this codebase. Nothing is paraphrased,
summarized, or truncated. Pinned by
`tests/test_job_parser_diagnostics.py::test_unparsed_claim_source_span_is_exact`.

---

## 6. Requirement visibility guarantees (now provable, not just claimed)

| Case | Before M9C | After M9C |
|---|---|---|
| Recognized technical requirement (SUPPORTED/NOT_OBSERVED) | Visible, status shown | Unchanged; `interpretation_status="recognized"` |
| Genuine non-technical requirement (education, soft skill, ...) | `not_assessable`, generic explanation | `not_assessable`, subsection "Genuinely non-technical requirements" |
| M9A `unresolved_requirement`/`alternative_requirement` placeholder | `not_assessable`, **identical generic explanation as above** | `not_assessable`, subsection "Could not be confidently interpreted" — distinct wording |
| Claim surviving segmentation, zero rows produced | **Invisible — no trace anywhere** | Listed verbatim in `unparsed_claims` / "Statements GitScore could not parse as requirements" |

---

## 7. Score interpretation — explicitly unchanged, now independently verified

`alignment_score = round_half_up(100 * supported_count / assessable_count)`,
`assessable_count = supported_count + not_observed_count` — **byte-for-
byte identical formula**, `assessment/models.py` untouched.
`uninterpreted_requirement_count` is informational only.
`tests/test_api_serialization.py::test_uninterpreted_requirement_count_never_affects_alignment_or_assessable_count`
independently recomputes the formula from `JobMatchAnalysis` counts and
compares against the served value — not merely asserted, checked.

Per Phase 2's explicit instruction, restated here for the record: this
score is an evidence-alignment measure, not a probability of hiring
success, not a measure of overall engineering competence; missing
GitHub evidence never means a skill is absent; the score may be
incomplete when requirements are unparsed (exactly the gap this
milestone makes visible, §6); job-conditioned retrieval (Milestone
8D.2) can affect which evidence was even available to assess. No new
coverage percentage was invented — `uninterpreted_requirement_count` is
a plain, observable count, not a ratio.

---

## 8. M9B regression results

`parse_job_description()` is provably unaffected:
`tests/test_job_parser_diagnostics.py::test_diagnostics_profile_matches_plain_parse_across_the_full_m9b_corpus`
compares its output against `parse_job_description_with_diagnostics(...).profile`
for every one of Milestone 9B's 30 corpus entries — all equal.

Re-ran both Milestone 9B evaluation scripts after this milestone's full
implementation and diffed against the pre-9C committed reports:

```
python scripts/evaluate_m9b_preservation.py
python scripts/evaluate_m9b_retrieval_sensitivity.py
git diff --stat evaluation/reports/m9b_preservation_report.json evaluation/reports/m9b_preservation_report.md \
                 evaluation/reports/m9b_retrieval_sensitivity_report.json evaluation/reports/m9b_retrieval_sensitivity_report.md
```

Result: **empty diff — byte-identical.** Zero score or requirement-
count changes anywhere in either report, exactly as required (this
milestone changes visibility, never analytical semantics).

`unparsed_claims` was independently cross-checked against the same
corpus: `test_unparsed_claims_reproduces_every_m9b_known_silent_drop`
confirms all 6 of M9B's own measured silent-drop entries
(`m9b-005`, `m9b-006`, `m9b-008`, `m9b-014`, `m9b-015`, `m9b-016`) now
appear in `unparsed_claims`, and
`test_unparsed_claims_never_includes_a_recognized_or_placeholder_claim`
confirms zero false positives against the other 24 entries.

**Correction found during this cross-check:** `MILESTONE_9B_EVALUATION_INTEGRITY.md`
originally misstated `m9b-005`'s measured outcome as a `FALLBACK_MATCH`
(resolved to the `unresolved_requirement` placeholder); direct
re-verification shows it is actually a `SILENT_DROP_GAP` — the lead-in
phrase matches but the remainder ("Snowflake is a plus") is 4 words,
failing `clean_list_fragment`'s `<=3`-word shape check. That report's
own aggregate numbers (`"flagged_as_gap": 6`) were already correct;
only its prose naming which six entries they were was wrong. Corrected
in place in that document, with the correction itself disclosed rather
than silently edited away — see that file's §4.1.

---

## 9. Tests and builds

| Suite | Result |
|---|---|
| `python -m pytest` (backend, full) | **920 passed** (904 baseline + 16 new: 8 in `test_job_parser_diagnostics.py`, 8 in `test_api_serialization.py`) |
| `cd frontend && npm run type-check` | clean, 0 errors |
| `cd frontend && npm test` (vitest) | **29 passed** (23 baseline + 6 new, all in `ResultView.test.tsx`) |
| `cd frontend && npm run build` | succeeds (Next.js production build, static export) |
| `python scripts/evaluate_m9b_preservation.py` | byte-identical to pre-9C (§8) |
| `python scripts/evaluate_m9b_retrieval_sensitivity.py` | byte-identical to pre-9C (§8) |

---

## 10. Files and versions changed

**Backend:** `src/gitscore/jobs/parsing/parser.py` (new `UnparsedClaim`,
`ParsedJobDescription`, `parse_job_description_with_diagnostics`,
shared `_parse()`), `src/gitscore/jobs/parsing/__init__.py`,
`src/gitscore/jobs/__init__.py` (re-exports), `src/gitscore/application/job_fit.py`
(`JobAnalysisResult.unparsed_claims`, `analyze_job_fit()` body),
`src/gitscore/api/schemas.py` (`RequirementOut.category`/
`.interpretation_status`, `AssessmentOut.uninterpreted_requirement_count`,
new `UnparsedClaimOut`, `AnalyzeResponse.unparsed_claims`),
`src/gitscore/api/serialization.py` (`_interpretation_status()`,
`serialize_unparsed_claim()`, wiring).

**Backend tests:** `tests/test_job_parser_diagnostics.py` (new, 8 tests),
`tests/test_api_serialization.py` (+8 tests), `tests/test_application_job_fit.py`
(1 test updated — monkeypatch target renamed to match the new call).

**Frontend:** `frontend/src/types/api.ts`, `frontend/src/lib/labels.ts`,
`frontend/src/components/RequirementSection.tsx`,
`frontend/src/components/AlignmentHeadline.tsx`,
`frontend/src/components/ResultView.tsx`, new
`frontend/src/components/UnparsedClaimsSection.tsx`,
`frontend/src/test/fixtures.ts` (new required fields).

**Frontend tests:** `frontend/src/components/__tests__/ResultView.test.tsx`
(+6 tests, 1 existing fixture override updated for the new required field).

**Docs:** `docs/ARCHITECTURE.md` §29 (new), `docs/PIPELINE.md` (job-fit/
API/frontend sections updated), `docs/CHANGELOG_DEV.md` (new entry),
`docs/evaluation/MILESTONE_9C_ASSESSMENT_TRANSPARENCY.md` (this file),
`docs/evaluation/MILESTONE_9B_EVALUATION_INTEGRITY.md` (one factual
correction, §8 above).

**Versions unchanged:** `JOB_DESCRIPTION_PARSER_VERSION`,
`JOB_REQUIREMENT_SCHEMA_VERSION`, `MATCHER_VERSION`, `SCORING_VERSION`,
`CONCEPT_REGISTRY_VERSION`, `EVIDENCE_SCHEMA_VERSION`,
`REPOSITORY_RANKING_VERSION`, `JOB_RELEVANCE_VERSION`.

---

## 11. Remaining risks

1. **The 23% silent-drop rate is unchanged** — by design (Decision D).
   A candidate/recruiter reading the new `unparsed_claims` list for the
   first time may be surprised by how much is there for some postings;
   this is the intended, honest surfacing of a pre-existing gap, not a
   regression, but the UI copy's tone (§ labels.ts) should be revisited
   if user feedback suggests it reads as alarming rather than
   informative.
2. **Two different parser mechanisms (M9A's bare-lead-in placeholder and
   M6B.1's "unsafe" OR-group fallback) are now presented identically**
   (`"unparsed_placeholder"`) — correct per this milestone's own
   design, but means a future reader of `category` directly (bypassing
   `interpretation_status`) could still be confused by the two distinct
   underlying category strings; `category` is documented as "raw
   passthrough, not for branching on" but nothing enforces that at the
   type level.
3. **The not-assessable subsection empty-state** (§29.5 of
   `ARCHITECTURE.md`) always renders both subsections once any
   `not_assessable` requirement exists, even if one subsection is
   empty — a minor, deliberate consistency choice, not re-evaluated
   against real user feedback.
4. **`end_to_end_report.json`'s pre-existing staleness** (found in
   M9B, §10.2 of that report) is untouched by this milestone — still
   an open item for a future milestone to resolve.

---

## 12. Recommended M9D scope

1. **Decide on the 23% silent-drop gap's long-term disposition** — now
   that it is visible and measured twice (M9B's benchmark, M9C's live
   `unparsed_claims`), decide whether a scoped, shape-only detector
   (the option presented but not approved in this milestone) is worth
   building, or whether permanent disclosure is the product's final
   answer.
2. **User-test the new UI copy** (headline caveat, two subsections,
   unparsed-claims list) — this milestone implemented the approved
   design; it has not been validated against real user reactions.
3. **Resolve `end_to_end_report.json`'s staleness** (carried over from
   M9B, still unresolved).
4. **Do not start any of the above without explicit scoping** — per
   this milestone's own instruction, M9D has not been started.

---

## Reproduction commands

```powershell
python -m pytest                                         # 920 passed
python scripts/evaluate_m9b_preservation.py
python scripts/evaluate_m9b_retrieval_sensitivity.py
git diff --stat evaluation/reports/m9b_preservation_report.json evaluation/reports/m9b_preservation_report.md `
                 evaluation/reports/m9b_retrieval_sensitivity_report.json evaluation/reports/m9b_retrieval_sensitivity_report.md
cd frontend
npm run type-check
npm test
npm run build
```

**DO NOT COMMIT. DO NOT PUSH. DO NOT START M9D.**
