# GitScore AI — Milestone 7B.0: Job Match Scoring / Coverage / Explanation Design

> **STATUS: APPROVED AND IMPLEMENTED.** This design was written and
> reviewed as a design-only milestone (7B.0) before any production code
> existed, then implemented unchanged in Milestone 7B
> (`src/gitscore/assessment/`). See `docs/ARCHITECTURE.md` §21 for the
> as-built summary and `docs/CHANGELOG_DEV.md`'s Milestone 7B entry for
> the implementation changelog. This file is the retained design
> record — if the two ever disagree, the code and §21 are authoritative
> for current behavior; this file explains *why* that behavior was
> chosen.

Written against the codebase as of Milestone 7A (686 tests passing,
`gitscore.matching` producing per-requirement `SUPPORTED`/
`NOT_OBSERVED`/`NOT_ASSESSABLE` verdicts with no score, no weighting, no
explanation prose).

---

## 1. Product question

GitScore's primary question: *given a job description, what evidence in
a candidate's GitHub suggests they are or aren't a fit?* The result must
help a human understand (1) how well GitHub-observable requirements
align, (2) how much confidence to place in that, (3)/(4)/(5) which
requirements are supported / not observed / not assessable, and (6)
which repositories support the conclusions. GitScore is **not**
determining whether to hire, not measuring total professional ability,
and is **never** allowed to treat missing GitHub evidence as proof of a
missing skill.

## 2. Core principle

**Match/alignment and coverage/confidence stay separate, always.** Two
candidates can have identical `3/3` requirement alignment with wildly
different amounts of GitHub material actually analyzed — collapsing
those into one number would hide exactly the distinction that matters.

## 3. GitHub Evidence Alignment — the score

> GitHub Evidence Alignment measures, among the job requirements GitHub
> evidence can meaningfully speak to, what percentage are supported by
> evidence found in the candidate's analyzed GitHub material.

```
assessable_count = supported_count + not_observed_count
alignment_score  = None                                       if assessable_count == 0
alignment_score  = round_half_up(100 * supported_count / assessable_count)  otherwise
```

`NOT_ASSESSABLE` is excluded from the denominator: it is not evidence of
absence, so including it would silently convert "this posting happens
to list non-technical requirements" into "the candidate missed them" —
directly violating the product's non-negotiable constraint.

## 4. Required vs. Preferred

**Decision: no necessity weighting in the headline formula; `required`/
`preferred` reported as mandatory co-display `SubscoreFacts(supported,
assessable)` — "X of Y," never a second percentage.**

Rejected: a `W_REQUIRED`/`W_PREFERRED` weighting scheme (the never-
implemented Milestone 5A draft's own approach) — inventing such weights
now, with zero labeled data, repeats exactly what two milestones in a
row (6A's `Importance`, 7A's evidence-sufficiency policy) were
deliberately told not to do. Rejected: ignoring necessity with no
co-display either — that produces the adversarial case below with no
way for a reader to notice it.

**Adversarial case (pinned by test):** Required Python/PostgreSQL both
`NOT_OBSERVED`; Preferred Docker/AWS/React/Redis/GitHub Actions/
Kubernetes all `SUPPORTED`. Unweighted headline = 75 (6 of 8 assessable).
A hidden 0.8/0.2 weighted formula would instead produce 20 — a huge
swing from one invented ratio, and in the opposite direction of what the
unweighted number shows. The approved resolution: keep 75, but make
`required == SubscoreFacts(0, 2)` an always-rendered fact beside it. No
cap, no floor, no gate — transparency over an invented threshold.

## 5. Importance

**Decision: read-only, excluded from the score.** `jobs/parsing/
importance.py`'s `infer_importance()` already defaults a `PREFERRED`
requirement to `LOW` importance unless an emphasis phrase overrides it —
`Importance` is a heuristic partially *derived from* `Necessity`, not an
independent signal. A `necessity × importance` scheme would compound one
parser heuristic's uncertainty into the score twice, amplifying a single
regex match (e.g. the word "essential") into a disproportionate swing.

## 6. ParserConfidence

**Decision: metadata only, surfaced as `low_parser_confidence_count`
(assessable requirements only), never affecting score or coverage.**
`ParserConfidence` measures confidence in GitScore's own reading of the
job text, not the candidate's evidence — folding it into the score would
make a candidate's number depend on how cleanly their target posting
happened to be worded, entirely outside their control.

## 7. Evidence confidence

**Decision: every `SUPPORTED` requirement counts equally; strength
remains inspectable per-match, never scored.** Extends 7A's own settled
policy (`MINIMUM_SUPPORTING_CONFIDENCE = ConfidenceLevel.WEAK`) one
layer up rather than reopening it — `ConfidenceLevel` is confidence in
the observation being real, never candidate proficiency.

## 8. Repository coverage

**Decision: structured facts only — `discovered_count`/`analyzed_count`/
`is_complete`, passed through unmodified. No synthesized 0–100 coverage
percentage, and no presentation string stored in domain state** (the
latter a correction made during design review — a first draft proposed
a `coverage_note` string field; rejected in favor of keeping domain
state structured and leaving prose to a future presentation layer). A
raw `analyzed/discovered` ratio would understate true coverage, since
Milestone 5B's ranker deliberately analyzes the highest-substantiveness
repositories first.

## 9. Required-requirement floor/caps

**Decision: none.** Resolved via §4's mandatory co-display instead of a
formula gate — any specific cap/floor threshold would be exactly the
kind of invented, uncalibrated precision this project has consistently
rejected elsewhere (`Importance`/`ParserConfidence`'s own "no fake
precision" design history).

## 10. Score naming

**Decision: "GitHub Evidence Alignment."** Avoids "match"/"fit," both of
which imply a bidirectional judgment about the candidate rather than a
one-directional statement about evidence coverage.

## 11. Explanation model

Three categories, derived from `JobMatchAnalysis.requirement_matches`
grouped by `MatchStatus` — no new traversal logic:

| Status | Heading | Required disclaimer |
|---|---|---|
| `SUPPORTED` | "Supported by GitHub evidence" | — |
| `NOT_OBSERVED` | "Not observed in analyzed GitHub evidence" | "...does not mean the candidate lacks the skill." |
| `NOT_ASSESSABLE` | "Not assessable from GitHub" | "...does not mean the candidate failed it." |

"Gaps" was considered and rejected as a section label — it reuses
`MatchStatus`'s own already-neutral vocabulary instead of introducing a
second, more deficiency-framed synonym at the presentation boundary.

## 12. Edge cases

See `docs/ARCHITECTURE.md` §21.9 for the full table (no assessable
requirements -> `None`; all supported -> 100; zero supported -> 0; only
one necessity tier assessable -> the other is `None`; a single
assessable requirement -> legitimately volatile 0/100; OR groups count
once; unresolved concepts get no special treatment; LOW parser
confidence on a `NOT_ASSESSABLE` requirement does not increment
`low_parser_confidence_count`).

## 13–14. Worked examples / parser-heuristic sensitivity

Full worked-example table (8 scenarios including the adversarial case)
and the Necessity/Importance/ParserConfidence sensitivity analysis are
preserved in the Milestone 7B.0 design review transcript; the single
most important one — the adversarial 75-with-0-of-2-required case — is
pinned directly as a test
(`tests/test_assessment_engine.py::
test_adversarial_case_strong_headline_despite_zero_required_support`)
rather than only living in documentation.

## 15. Calibration / future learning path

Nothing in `gitscore.assessment` requires changing `RequirementMatch`,
`CandidateEvidenceProfile`, or `JobRequirementProfile` for a future
learned ranker: every feature worth logging (per-match status/necessity/
importance/parser_confidence/github_observability/evidence detail, plus
`alignment_score`/subscores/coverage) is already derivable from
`JobMatchAnalysis` and `JobAssessment`. A learned model would replace
`assess_job()`'s internals behind the same `JobAssessment` shape.

## 16. Domain model (as implemented)

```
SubscoreFacts(supported: int, assessable: int)
    # assessable >= 1 enforced; supported in [0, assessable]

JobAssessment(match_analysis: JobMatchAnalysis, scoring_version: str)
    # alignment_score, assessable_count, required, preferred,
    # low_parser_confidence_count -- all @property, derived on read
    # supported_matches() / not_observed_matches() / not_assessable_matches()
```

`assess_job(match_analysis) -> JobAssessment` is the sole public entry
point (`assessment/engine.py`).

## 17. Versioning

`SCORING_VERSION = "github_evidence_alignment:v1"` (new, independent).
`JOB_REQUIREMENT_SCHEMA_VERSION`, `EVIDENCE_SCHEMA_VERSION`,
`CONCEPT_REGISTRY_VERSION`, `JOB_DESCRIPTION_PARSER_VERSION`,
`MATCHER_VERSION` all unchanged — confirmed, this milestone is purely
additive. No `EXPLANATION_VERSION`: the explanation groupings (§11) are
exactly this package's own `MatchStatus` partitioning, not a separate
prose-generation step yet.

## 18–19. Mockup and final decision

See `docs/ARCHITECTURE.md` §21 for the as-built mockup-equivalent
(the locked wording table in §21.8) and the full per-topic decision
record (§21.1–§21.12).

## Known limitations carried into implementation

- The dedup-survival double-count case (`jobs/parsing/dedup.py` dedupes
  by `(concept_id, necessity)`, so the same concept asserted once as
  REQUIRED and once as PREFERRED elsewhere in a posting is counted
  twice) is a known, inherited limitation from 7A's domain model, not
  silently patched with an undefined second dedup pass.
- Presentation wording (§11) is documented but not yet user/legal-
  reviewed for a real recruiter-facing release.
