# Milestone 9E — Assessment Clarity & Trust Corrections

**Status: implemented.** No matcher semantic change (`gitscore.matching`
untouched), no scoring-formula change (`gitscore.assessment` untouched),
no concept-registry *content* change (no concept added/renamed/merged —
one new, additive helper function was added to `gitscore.concepts.registry`),
no parser/segmentation change (`gitscore.jobs.parsing` untouched), no
job-relevance/retrieval change, no frozen-gold change. `JOB_DESCRIPTION_PARSER_VERSION`,
`JOB_REQUIREMENT_SCHEMA_VERSION`, `MATCHER_VERSION`, `SCORING_VERSION`,
`CONCEPT_REGISTRY_VERSION`, `EVIDENCE_SCHEMA_VERSION`,
`REPOSITORY_RANKING_VERSION`, and `JOB_RELEVANCE_VERSION` are all
unchanged. Every change is additive at the API/frontend presentation
layer, mirroring the exact precedent Milestone 9C already set. Not
committed, not pushed, M9F not started.

---

## 1. Baseline (Phase 0)

| Check | Result |
|---|---|
| HEAD at start | `a9ccd0b` ("test: add product trustworthiness pilot" — M9D) |
| Working tree | clean |
| `python -m pytest` | **920 passed**, 0 failed (matches the expected baseline exactly) |
| `cd frontend && npx vitest run` | **29 passed** (matches the expected baseline exactly) |

Read before any implementation: `docs/evaluation/MILESTONE_9D_PRODUCT_VALIDATION.md`,
`docs/evaluation/MILESTONE_9C_ASSESSMENT_TRANSPARENCY.md`,
`docs/evaluation/M9D_HUMAN_PILOT_PROTOCOL.md`, `api/schemas.py`,
`api/serialization.py`, `jobs/parsing/parser.py`, `jobs/models.py`,
`matching/engine.py`, `matching/models.py`, `matching/support.py`,
`assessment/models.py`, `application/job_fit.py`, `evidence/models.py`,
`evidence/types.py`, `concepts/models.py`, `concepts/registry.py`, and
every frontend component in the result-rendering path
(`AlignmentHeadline.tsx`, `RequirementSection.tsx`, `EvidenceList.tsx`,
`UnparsedClaimsSection.tsx`, `ResultView.tsx`, `lib/labels.ts`,
`types/api.ts`, `test/fixtures.ts`).

---

## 2. Workstream A — Headline uncertainty count

### 2.1 Root cause (traced, not assumed)

`AssessmentOut.uninterpreted_requirement_count` (`api/serialization.py`,
pre-9E) was computed as:

```python
uninterpreted_count = sum(1 for r in not_assessable if r.interpretation_status == "unparsed_placeholder")
```

This counts ONLY `not_assessable` requirements whose
`interpretation_status == "unparsed_placeholder"` — claims that DID
survive parsing far enough to become a real `JobRequirement` row
(Milestone 9A's last-resort placeholder, or the Milestone 6B.1 "unsafe"
OR-group fallback). It structurally excludes `JobAnalysisResult.unparsed_claims`
(Milestone 9C's `UnparsedClaim` diagnostic) — claims that survived
`segment_description()`'s requirement-shaped gate but for which the
per-claim detector chain (`_requirements_from_claim`) produced **zero**
rows at all. These were never counted anywhere in the headline, even
though M9C's own `UnparsedClaimsSection` already rendered them, further
down the page.

Confirmed live against the real `torvalds × sre_platform_01` pairing
(reproducing M9D §6.1 exactly): the posting carries 1 placeholder
("Terraform") and 2 fully-unparsed claims ("Experience with monitoring
and observability tooling," "On-call experience and incident response").
Pre-9E, the headline read "1 requirement could not be confidently
interpreted" — undercounting the true interpretive uncertainty by 2 of 3.

### 2.2 Design decision

Per the milestone brief's own instruction ("If one combined count cannot
be semantically justified, display separate counts"): the two counts are
**category-different facts**, not two measurements of the same thing —
one counts real, inspectable `JobRequirement` rows; the other counts
text that never became a row and is explicitly *not* a confirmed job
requirement. Summing them into one number would misrepresent the more
severe category (nothing preserved at all) as the less severe one
(a real row exists, just unresolved). **Two separate counts and two
separate caveat sentences were implemented**, never merged.

No double-counting is possible by construction: a claim either produces
≥1 `JobRequirement` row (possibly the placeholder, captured by
`uninterpreted_requirement_count`) or produces zero rows (captured by
`unparsed_claim_count`) — `jobs/parsing/parser.py::_parse()`'s own loop
makes these two outcomes mutually exclusive per claim (confirmed by the
pre-existing `tests/test_job_parser_diagnostics.py::test_unparsed_claims_never_includes_a_recognized_or_placeholder_claim`,
and re-confirmed at the API layer by this milestone's new
`test_unparsed_claim_count_and_uninterpreted_requirement_count_never_overlap`).

### 2.3 Changes

- `api/schemas.py` — `AssessmentOut.unparsed_claim_count: int` (new,
  additive field). `RequirementOut`/`AssessmentOut` docstrings updated to
  explain why the two counts are kept separate.
- `api/serialization.py` — `unparsed_claim_count=len(result.unparsed_claims)`,
  computed directly in `serialize_job_analysis_result()`, no new logic.
- `frontend/src/types/api.ts` — `Assessment.unparsed_claim_count: number`.
- `frontend/src/lib/labels.ts` — new `unparsedClaimsCaveat(count)`,
  deliberately worded "N additional **statements** ... could not be
  parsed as a requirement **at all**" (never "requirements") so it can
  never be read as describing a confirmed job requirement.
- `frontend/src/components/AlignmentHeadline.tsx` — new optional
  `unparsedClaimCount` prop; renders a SECOND caveat paragraph
  (`<p className="alignment-unparsed-claims-caveat">`) when `> 0`, below
  the existing `uninterpretedCaveat` paragraph. Both render independently
  — either, both, or neither can appear, exactly matching the two
  underlying counts.
- `frontend/src/components/ResultView.tsx` — passes
  `result.assessment.unparsed_claim_count` through.

### 2.4 Before / after — `torvalds × sre_platform_01`

| | Before M9E | After M9E |
|---|---|---|
| Headline caveat(s) shown | "1 requirement could not be confidently interpreted by GitScore's parser — see below." | Same first sentence, **plus** "2 additional statements in the job posting could not be parsed as a requirement at all — see below." |
| Real interpretive uncertainty communicated at the top of the page | 1 of 3 | 3 of 3 (1 + 2, shown as two honest, correctly-labeled counts) |
| `alignment_score` | 50 | 50 (unchanged) |

### 2.5 Before / after — `karpathy × computer_vision_01` (also Workstream D)

Reproduced live (not asserted) with a hand-built evidence profile giving
`karpathy` the same required/preferred outcome M9D measured
(§4 of `MILESTONE_9D_PRODUCT_VALIDATION.md`: required 3/3, preferred 1/1,
alignment 100):

| | Before M9E | After M9E |
|---|---|---|
| `uninterpreted_requirement_count` | 0 | 0 (unchanged — no placeholder row exists for this posting) |
| Headline caveat shown | **none at all** | "1 additional statement in the job posting could not be parsed as a requirement at all — see below." |
| `unparsed_claims` | `["Experience with OpenCV for image processing"]` (already present, M9C) | same, now also surfaced at the headline |
| `alignment_score` / `required` / `preferred` | 100 / 3 of 3 / 1 of 1 | 100 / 3 of 3 / 1 of 1 (byte-identical — confirmed, not assumed) |

This is the single most concrete fix of this milestone: a reader
previously saw a clean 100 with **zero** indication anything was
uncertain; they now see the same 100 accompanied by an honest caveat that
a real posting requirement (OpenCV) could not be parsed at all. See
§5 (Workstream D) for what this does and does NOT resolve.

### 2.6 Tests added

`tests/test_api_serialization.py` (9 new tests): zero/one/multiple
unparsed claims; a claim duplicated at two distinct source spans is
counted **twice**, never collapsed (`unparsed_claims` is never
deduplicated by text — confirmed directly against `_parse()`'s own
loop); the two counts never overlap on a fixture carrying both
categories simultaneously; neither count affects `alignment_score` or
`assessable_requirement_count` (independently recomputed, not merely
asserted — mirroring M9C's own `test_uninterpreted_requirement_count_never_affects_alignment_or_assessable_count`
pattern).

`frontend/src/components/__tests__/ResultView.test.tsx` (3 new tests):
both caveats render independently and simultaneously; the unparsed-claims
caveat is omitted when zero; its wording uses "statement(s)," never
"requirement(s)."

---

## 3. Workstream B — Duplicate-looking requirements

### 3.1 Root cause (confirmed: NOT a matcher or parser bug)

Investigated directly against the real parser/matcher output for the
exact M9D-reported pairs:

```
devops_cloud_01:
  'Strong experience with Docker and Kubernetes' | infra.docker      | category=infrastructure
  'Strong experience with Docker and Kubernetes' | infra.kubernetes  | category=infrastructure
data_science_01:
  'Experience with Python, pandas, and numpy' | language.python      | category=language
  'Experience with Python, pandas, and numpy' | data.library.pandas  | category=data_library
  'Experience with Python, pandas, and numpy' | unresolved:numpy     | category=None
```

Each duplicate-looking pair is **two (or three) distinct, correctly
formed `JobRequirement` objects** sharing identical `original_text` —
exactly the documented, intentional Milestone 9A/6B.1 "one row per
matched concept" design (`docs/ARCHITECTURE.md` §28/§20): one sentence
in a job posting can name more than one technology, and each gets its
own row so the matcher can evaluate each concept independently (Docker
present ≠ Kubernetes present). `matching.engine.match_requirement()`
correctly evaluates each row against its own `concept_id`, producing
`SUPPORTED` for one and `NOT_OBSERVED` for the other — this is the
matcher working exactly as designed, not a defect. **No matcher, parser,
or dedup change was made or considered necessary** — per the brief's own
instruction, this was the first question answered before writing any
code, and the answer is "intentional design, presentation gap only."

The actual gap: `RequirementItemsList` (`RequirementSection.tsx`) rendered
only `requirement.text` — the API already carried `concept_id`/
`matched_concept_ids` distinguishing the rows (M8A), but nothing in the
UI ever read them for display. A user had no way to tell two identical
sentences apart, including the most confusing case: the SAME sentence
appearing under "Supported by GitHub evidence" **and** "Not observed in
analyzed GitHub evidence" simultaneously (`devops_cloud_01`'s Docker/
Kubernetes split, `data_science_01`'s Python/pandas+numpy split).

### 3.2 Fix

Additive, presentation-only, two parts:

**Backend** — `gitscore.concepts.registry.concept_display_label(concept_id)`
(new function): returns the registered `TechnicalConcept.display_name`
for a real concept (e.g. `"infra.kubernetes"` → `"Kubernetes"` — reading
a field that already existed, inventing nothing), or, for an
`"unresolved:<term>"` placeholder, a title-cased re-rendering of the SAME
raw term already encoded into the id (e.g. `unresolved:numpy` →
`"Numpy"`) — never inventing new information about an unregistered term,
just reformatting what the parser already captured. Raises `ValueError`
for a genuinely invalid concept id (a programming error, never expected
in practice). `RequirementOut.concept_label: str | None` (new field,
`None` exactly when `concept_id` is `None`) is computed from this in
`api/serialization.py`.

**Frontend** — `ResultView.tsx` computes, ONCE per render, the set of
`requirement.text` values that appear more than once across the **whole**
result (all three groups — supported, not_observed, not_assessable, not
just within one section), because the cross-status case is the one M9D
flagged as most consequential. That set is threaded down through
`RequirementSection`/`NotAssessableSubsection` into `RequirementItemsList`,
which appends `" ({concept_label})"` to a row's displayed text **only
when** that row's text is in the duplicate set **and** it has a
`concept_label` to disambiguate with — never fabricates a label when
none exists (e.g. a genuinely non-technical row with `concept_id = null`
stays bare).

### 3.3 Before / after — `devops_cloud_01`

| Section | Before M9E | After M9E |
|---|---|---|
| Supported by GitHub evidence | "Strong experience with Docker and Kubernetes" | "Strong experience with Docker and Kubernetes (Docker)" |
| Not observed in analyzed GitHub evidence | "Strong experience with Docker and Kubernetes" | "Strong experience with Docker and Kubernetes (Kubernetes)" |

The identical sentence no longer appears, unexplained, under two
contradictory-looking statuses at once.

### 3.4 Before / after — `data_science_01`

| Section | Before M9E | After M9E |
|---|---|---|
| Supported | "Experience with Python, pandas, and numpy" | "Experience with Python, pandas, and numpy (Python)" |
| Not observed | "Experience with Python, pandas, and numpy" (×2) | "...  (pandas)" and "... (Numpy)" |

### 3.5 Tests added

`tests/test_technical_concepts.py` (5 new tests): `concept_display_label`
reads the real `display_name` for registered concepts; derives a
title-cased label for unresolved concepts; is deterministic regardless
of input casing; raises `ValueError` for an invalid id.

`tests/test_api_serialization.py` (4 new tests): label present for a
resolved concept; `None` for non-technical/alternative-group/placeholder
rows (no single concept to label); the exact Docker/Kubernetes
disambiguation scenario end-to-end; the exact unresolved-`numpy`
scenario end-to-end.

`frontend/.../ResultView.test.tsx` (3 new tests): a duplicate pair across
`supported`/`not_observed` both get correctly, distinctly labeled, and
the bare ambiguous text never remains; a unique (non-duplicated)
requirement text is never altered; a duplicate row with no `concept_label`
(the pre-existing fixture case — one compound sentence split into a
technical + a genuinely non-technical claim) is correctly left bare,
confirming the mechanism never fabricates a label where none exists.

---

## 4. Workstream C — Evidence provenance and strength

### 4.1 What already existed (investigated before changing anything)

`EvidenceOut`/`EvidenceItem` already carries `evidence_type`,
`confidence`, `repository.{owner,name}`, `file_path`, and `detail` (the
raw observation text) — Milestone 8A. `EvidenceList.tsx` already groups
by repository and renders a human label for `evidence_type`
(`evidenceTypeLabel()`, Milestone 8B) and the confidence level. What was
**not** already available: (1) any way to follow a citation back to the
actual repository (M9D risk #4 — confirmed by direct code read: zero
`<a href>` anywhere in `EvidenceList.tsx`, and the existing regression
test explicitly pinned zero links), and (2) any explanation of what a
given `evidence_type` actually represents as a KIND of signal (a
dependency declaration vs. a README mention are structurally very
different claims, but were presented with equal visual weight beyond the
type label itself).

### 4.2 Fix — additive, no new score invented

**Evidence links.** `frontend/src/lib/github.ts` (new file) —
`repositoryUrl(owner, name)` returns `https://github.com/{owner}/{name}`,
built ONLY from `RepositoryIdentity` fields the API already returns
(the candidate's own account/repository, already confirmed to exist by
the GitHub API during evidence extraction earlier in the pipeline). This
is **not** a fabricated URL — GitHub's public path convention is a
stable fact, not a guess. `EvidenceList.tsx` now renders the
`owner/name` text as a link to this URL. **Deliberately links the
repository root only, never a file-specific deep link**: `file_path` has
no accompanying branch/ref anywhere in the domain model
(`evidence.models.Evidence` has no `source_url` field by design — see
its own docstring), and guessing a branch (e.g. assuming `"main"`) risks
a dead or misleading link for a repository using a different default
branch — exactly the "never fabricate missing URLs" case this milestone
explicitly rules out. `file_path` continues to render as plain text,
unchanged.

**Source-type calibration.** `lib/labels.ts` gained
`evidenceTypeDescription(evidenceType)`: one calibrated, plain-language
sentence per `evidence_type` (e.g. `dependency` → "An explicit dependency
declared in a project manifest (e.g. requirements.txt, package.json)";
`readme` → "A text mention found in the repository's README — may
describe the candidate's own usage, or only a reference, comparison, or
example."). Rendered in `EvidenceList.tsx` beneath each evidence item's
existing type/confidence line. **No numeric strength/competence score of
any kind was invented** — this is explanatory text about what KIND of
observation an item is, using facts (`evidence_type`) the API already
returns, never a new confidence number, weight, or "evidence quality"
metric.

### 4.3 `sindresorhus × devops_cloud_01` — concretely what this does and does not change

Reproducing M9D §4.2/§6.3's own finding: the "Experience with AWS or
Azure" requirement is `SUPPORTED` on a README mention in `file-type`
describing a usage example ("...file stored on Amazon S3"), not the
candidate's own cloud deployment. After this milestone:

- The citation now links directly to `https://github.com/sindresorhus/file-type`
  — a reader can click through and read the actual README themselves in
  seconds, rather than manually navigating to GitHub and searching.
- The evidence item now additionally shows: "A text mention found in the
  repository's README — may describe the candidate's own usage, or only
  a reference, comparison, or example." — a calibrated hint that this
  specific evidence TYPE warrants closer reading before trusting it as
  strongly as a dependency declaration would warrant.
- **Not changed**: the requirement still reads `SUPPORTED`; `alignment_score`
  is still `75`; `MINIMUM_SUPPORTING_CONFIDENCE` is still `WEAK`; no
  evidence-type weighting was added to scoring. M9D's risk #2 (a large,
  topically-unrelated account's evidence volume can clear the WEAK bar on
  unrelated technologies) is **not resolved** by this milestone — it was
  explicitly deprioritized by M9D's own §10 recommendation ("Medium
  complexity... should follow once the human pilot's results are in")
  and remains open for a future milestone. This milestone makes the
  underlying evidence easier to verify and more honestly labeled; it does
  not change how much weight the score gives it.

### 4.4 Tests added

`frontend/.../ResultView.test.tsx` (2 new tests): every rendered evidence
link resolves to `https://github.com/{owner}/{name}` with no file-path/
branch-guessing suffix, and the `Dockerfile` path still renders as plain
text; the calibrated, non-numeric description text renders for
`docker`-type and `repository_language`-type evidence respectively.

The pre-existing test `"never fabricates a repository URL or file URL
not present in the API response"` was intentionally updated (not
removed) to reflect this milestone's deliberate behavior change — it now
asserts every rendered link is derived ONLY from `owner`/`name` already
present in the API response and is never a file-specific/branch-guessed
URL, preserving the original test's actual intent (no fabrication)
rather than its now-outdated literal assertion (zero links).

---

## 5. Workstream D — High-alignment limitations (`karpathy × computer_vision_01`)

### 5.1 Investigation (per the brief: no registry/heuristic change permitted)

Ran the real parser against `evaluation/jobs/computer_vision_01.json`'s
`raw_text` directly:

```
requirements produced:
  Strong Python programming skills                              -> language.python          (required)
  Experience with PyTorch for deep learning-based vision models  -> ml.framework.pytorch      (required)
  Familiarity with CUDA-accelerated training pipelines           -> platform.cuda             (required)
  Experience with Jupyter Notebook-based experimentation         -> language.jupyter_notebook (preferred)
  Master's degree in ... related field                           -> None (category=education) (preferred)

unparsed_claims:
  'Experience with OpenCV for image processing'
```

**The OpenCV requirement is NOT invisible to diagnostics** — it already
appears in `unparsed_claims` (M9C's own mechanism), confirming M9D §4.2's
own finding exactly. It never became a `JobRequirement` row because no
registry concept exists for `"OpenCV"` and the claim does not match any
of `_unresolved_requirement_signal`'s three narrow shapes (no "or", no
enumeration-cue comma list, and its lead-in "Experience with OpenCV for
image processing" fails `clean_list_fragment`'s check on the long
remainder "OpenCV for image processing" — the last-resort placeholder
is deliberately narrow and does not fire here). **No parser heuristic was
widened and no concept was registered** — per the brief's explicit
instruction not to resolve this during 9E.

### 5.2 Did the UI caveat already communicate this limitation? (verified, not assumed)

**No, before this milestone.** `uninterpreted_requirement_count` was `0`
for this exact posting (confirmed by live reproduction, §2.5 above) —
zero placeholder rows exist, because the claim never became a row of any
kind. The pre-9E headline caveat is conditioned on
`uninterpreted_requirement_count > 0`, so it rendered nothing at all. A
reader saw a clean "100 / 100" with zero on-page indication that
anything was uncertain, for a posting whose own raw text asked for
OpenCV.

**After this milestone, yes — within the limits of Workstream A's fix.**
`unparsed_claim_count` is now `1` for this exact posting, and the
headline now renders a second caveat: "1 additional statement in the job
posting could not be parsed as a requirement at all — see below." A
reader now has an honest, on-page signal, next to the score, that the
analysis may be incomplete — satisfying this workstream's "verify the UI
caveat accurately communicates the observed limitation" instruction.

### 5.3 What remains genuinely unresolved (documented, not silently claimed fixed)

Per the brief's explicit instruction, a generic disclaimer does not fully
resolve this risk, and it is not claimed to here:

- `alignment_score` is still `100`, `required` is still `3 of 3` —
  unchanged, correctly, since this milestone does not touch scoring. A
  reader who does not read past the headline number still sees a
  perfect score for a posting with an unassessed required requirement.
- The new caveat says a statement "could not be parsed as a requirement
  at all" — it does NOT say which specific skill/technology was missed,
  nor that it was a REQUIRED bullet. A reader must still open the
  `UnparsedClaimsSection` further down the page to see the literal text
  ("Experience with OpenCV for image processing") and infer its likely
  necessity themselves.
- This is the SAME underlying mechanism M9B/M9C already measured and
  disclosed at 23% corpus-wide (the silent-drop gap) and M9D §6.2/§4.2
  already identified as shrinking/inflating small denominators — this
  milestone does not reduce that rate, add detection for it, or change
  how it affects `required`/`preferred`/`alignment_score`. It only makes
  the EXISTING diagnostic (which already captured this exact case,
  unchanged since M9C) visible at the headline instead of silent.

**Recommendation carried forward to M9F** (restating M9C §12's
still-open decision point, now demonstrated twice over — M9D's finding
and this milestone's live reproduction): decide whether a scoped,
shape-only detector that could resolve "OpenCV"-shaped single-named-
technology claims into a real `JobRequirement` row is worth building, or
whether this milestone's two-caveat disclosure is the product's
permanent answer to the 23% gap. Either decision should be made
explicitly, not deferred again.

---

## 6. Scoring/matching invariants — verified, not merely asserted

- `gitscore/matching/engine.py`, `gitscore/matching/models.py`,
  `gitscore/matching/support.py`, `gitscore/assessment/models.py`,
  `gitscore/jobs/parsing/*.py` (all parser modules), and
  `gitscore/concepts/normalize.py` — byte-for-byte unchanged (confirmed
  by `git diff --stat`, §8 below).
- `gitscore/concepts/registry.py` gained exactly one new, additive
  function (`concept_display_label`) and no change to `_CONCEPTS`,
  `ConceptRegistry`, `resolve_concept()`, or `CONCEPT_REGISTRY_VERSION`.
- `scripts/evaluate_m9b_preservation.py` and
  `scripts/evaluate_m9b_retrieval_sensitivity.py` re-run after full
  implementation; `git diff --stat` against the pre-9E committed reports
  is **empty — byte-identical**.
- `scripts/evaluate_m9d_pilot_cohort.py` (M9D's own evaluation-only
  script, which calls the domain pipeline directly and never touches
  `gitscore.api`) re-run after full implementation; its output report is
  also byte-identical (this script does not exercise the API
  serialization layer at all, so this is an additional confirmation that
  nothing in the shared domain/matching/scoring path moved).
- New backend tests independently recompute `alignment_score`/
  `assessable_requirement_count` from the underlying domain counts and
  compare against the served value, rather than merely asserting a
  number (mirroring M9C's own discipline).

---

## 7. Tests and regression results

| Suite | Before M9E | After M9E |
|---|---|---|
| `python -m pytest` | 920 passed | **934 passed** (920 + 14 new: 5 in `test_technical_concepts.py`, 9 in `test_api_serialization.py`) |
| `cd frontend && npx vitest run` | 29 passed | **36 passed** (29 + 7 new, all in `ResultView.test.tsx`) |
| `cd frontend && npm run type-check` | clean | clean, 0 errors |
| `cd frontend && npm run build` | succeeds | succeeds (Next.js production build) |
| `scripts/evaluate_m9b_preservation.py` | — | byte-identical to pre-9E |
| `scripts/evaluate_m9b_retrieval_sensitivity.py` | — | byte-identical to pre-9E |
| `scripts/evaluate_m9d_pilot_cohort.py` | — | byte-identical to pre-9E |
| `git diff --check` | — | clean (only pre-existing CRLF-normalization notices, no real whitespace errors) |

---

## 8. Files modified

**Backend:** `src/gitscore/concepts/registry.py` (new
`concept_display_label()`), `src/gitscore/concepts/__init__.py`
(re-export), `src/gitscore/api/schemas.py`
(`RequirementOut.concept_label`, `AssessmentOut.unparsed_claim_count`,
docstring updates), `src/gitscore/api/serialization.py`
(`_concept_label()`, wiring for both new fields).

**Backend tests:** `tests/test_technical_concepts.py` (+5),
`tests/test_api_serialization.py` (+9).

**Frontend:** `frontend/src/types/api.ts`
(`RequirementItem.concept_label`, `Assessment.unparsed_claim_count`),
`frontend/src/lib/labels.ts` (`unparsedClaimsCaveat()`,
`evidenceTypeDescription()`), new `frontend/src/lib/github.ts`
(`repositoryUrl()`), `frontend/src/components/AlignmentHeadline.tsx`
(`unparsedClaimCount` prop), `frontend/src/components/ResultView.tsx`
(`findDuplicateRequirementTexts()`, wiring), `frontend/src/components/RequirementSection.tsx`
(`duplicateTexts` prop, `disambiguatedRequirementText()`),
`frontend/src/components/EvidenceList.tsx` (repository link, evidence-type
description), `frontend/src/test/fixtures.ts` (new required fields).

**Frontend tests:** `frontend/src/components/__tests__/ResultView.test.tsx`
(+12: 3 Workstream A, 3 Workstream B, 2 Workstream C, plus 1 updated
pre-existing test and minor fixture-alignment updates to 2 others).

**Docs:** `docs/ARCHITECTURE.md` §30 (new), `docs/PIPELINE.md` (job-fit/
API/frontend sections updated), `docs/CHANGELOG_DEV.md` (new entry),
`docs/evaluation/MILESTONE_9E_ASSESSMENT_CLARITY.md` (this file).

**Versions unchanged:** `JOB_DESCRIPTION_PARSER_VERSION`,
`JOB_REQUIREMENT_SCHEMA_VERSION`, `MATCHER_VERSION`, `SCORING_VERSION`,
`CONCEPT_REGISTRY_VERSION`, `EVIDENCE_SCHEMA_VERSION`,
`REPOSITORY_RANKING_VERSION`, `JOB_RELEVANCE_VERSION`.

---

## 9. Remaining risks (carried forward, not resolved by this milestone)

1. **The 23% silent-drop rate itself is unchanged** (M9B/M9C, re-confirmed
   live by Workstream D above) — `unparsed_claim_count` makes it visible
   at the headline; it does not reduce it. `required`/`preferred`
   denominators can still silently shrink when a required bullet becomes
   an `UnparsedClaim` instead of a row (M9D §6.2). **Still the single
   largest open decision point**, now raised a third time (M9C §12, M9D
   §9/§10, here).
2. **Evidence-sufficiency/weighting calibration risk is unchanged**
   (M9D §6.3, `sindresorhus × devops_cloud_01`) — this milestone makes
   the evidence easier to verify (clickable link) and more honestly
   labeled (calibrated type description), but does not change
   `MINIMUM_SUPPORTING_CONFIDENCE` or add any evidence-type weighting to
   scoring. A large, topically-unrelated account can still clear a
   "75% required" headline almost entirely on README-mention-grade
   evidence.
3. **Conservative design still cannot credit self-evident contextual
   evidence** (M9D §6.4, `torvalds`'s own `linux` repository for "Linux
   systems programming") — unchanged, intentional, not revisited.
4. **No clickable deep-link to the specific file/line** — only the
   repository root links; `file_path` remains plain text. A genuinely
   safe file-specific link would require a default-branch fact nowhere
   in the current domain model; adding one is an additive API/evidence-
   model change, not attempted here (would need its own STOP-point
   proposal per the Code Change Workflow).
5. **The Phase 4 human pilot (M9D's own deliverable) has still not been
   run** — nothing in this milestone's own validation substitutes for
   real user testing of the new caveats/labels/links. The two Task 1/Task 4
   pilot materials M9D specified (`karpathy × computer_vision_01`,
   `torvalds × sre_platform_01`) now render differently (both headline
   caveats changed) — if the pilot is run after this milestone, the
   protocol's own observer notes (§B of `M9D_HUMAN_PILOT_PROTOCOL.md`)
   should be read as describing the PRE-9E screen; a participant may now
   notice the new caveat language where the protocol's internal notes
   assumed they would not.

## 10. Recommendations for M9F

1. **Resolve the 23%-silent-drop disposition decision** (risk #1 above) —
   this is the third milestone in a row to surface it without a final
   answer. Either build the scoped, shape-only detector M9B/M9C already
   sketched, or formally declare the two-caveat disclosure this milestone
   adds as the product's permanent answer.
2. **Run the M9D human pilot** against the current (post-9E) UI, now that
   both headline caveats and the requirement-disambiguation labels exist
   — the pilot's Task 4 (parser-uncertainty) and Task 5
   (evidence-verification) materials are directly affected by this
   milestone's changes and should be run against the current state, not
   retrofitted after the fact.
3. **Consider risk #2** (evidence-strength/weighting calibration,
   `devops_cloud_01`) only after the pilot's trust-calibration
   questionnaire results are in, per M9D §10's own reasoning — this
   milestone deliberately did not touch it.
4. **Do not start any of the above without explicit scoping** — per this
   milestone's own instruction, M9F has not been started.

---

## Reproduction commands

```powershell
python -m pytest                                         # 934 passed
python -m pytest tests/test_technical_concepts.py tests/test_api_serialization.py -q
python scripts/evaluate_m9b_preservation.py
python scripts/evaluate_m9b_retrieval_sensitivity.py
cd scripts; python evaluate_m9d_pilot_cohort.py; cd ..
git diff --stat evaluation/reports/m9b_preservation_report.json evaluation/reports/m9b_preservation_report.md `
                 evaluation/reports/m9b_retrieval_sensitivity_report.json evaluation/reports/m9b_retrieval_sensitivity_report.md `
                 evaluation/reports/m9d_pilot_cohort_report.json
cd frontend
npx vitest run
npm run type-check
npm run build
cd ..
git diff --check
```

**DO NOT COMMIT. DO NOT PUSH. DO NOT START M9F.**
