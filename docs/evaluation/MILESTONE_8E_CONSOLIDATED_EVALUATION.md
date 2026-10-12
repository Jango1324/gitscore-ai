# Milestone 8E — Consolidated Evaluation & Product Readiness Assessment

**Status: evaluation only.** No production code under `src/gitscore/` was
modified. No scoring/matching/retrieval formula, concept registry, or
frozen gold under `evaluation/gold/`/`evaluation/gold_v1_1/` was changed.
Nothing was committed by this milestone (the two new files below are
left as uncommitted, untracked additions for review).

**New evaluation-only files added:**
- `scripts/evaluate_end_to_end_job_aware.py` — the one new harness this
  milestone's Phase 1 audit determined was necessary (see §2).
- `evaluation/reports/end_to_end_job_aware_report.json` — its output.

---

## 1. Verified baseline

| Check | Result |
|---|---|
| HEAD | `f5b1c31` ("fix: improve README evidence attribution" — M8D.3) |
| Working tree | clean |
| `python -m pytest` | **864 passed**, 0 failed, 70 warnings (pre-existing `datetime.utcnow()`/httpx deprecations, unrelated to this milestone) |
| Python | 3.14.0 |
| pytest | 9.1.1 |
| Key packages | pandas 3.0.5, SQLAlchemy 2.0.51, fastapi 0.142.2 |

Baseline matches the expected ~864 backend tests exactly. No blocker —
proceeded past Phase 0.

---

## 2. Evaluation methodology

### 2.1 What each existing script actually measures

| Script | Pipeline functions called | Level | Calls `analyze_job_fit()`? |
|---|---|---|---|
| `evaluate_job_parser.py` | `parse_job_description()` only | isolated — Layer A | No |
| `evaluate_evidence.py` | `extract_candidate_evidence()` only, **no** `job_relevance_terms` (`evaluation_lib/evidence_eval.py:80`) | isolated — Layer B | No |
| `evaluate_repository_retrieval.py` | `parse_job_description()` + `extract_candidate_evidence()` **twice** per case (with/without `job_relevance_terms`, via the real `_relevance_terms_from_job_profile()`) | retrieval only — never calls `match_job`/`assess_job` | No |
| `evaluate_end_to_end.py` | `extract_candidate_evidence()` (no relevance terms) **once per candidate, reused across every job pair** in the matrix, then `parse_job_description`/`match_job`/`assess_job` per pair | matcher/assessment workflow, but **job-independent retrieval** | No |

**No evaluation script calls `gitscore.application.job_fit.analyze_job_fit()`** — the real product entry point. Only `evaluate_repository_retrieval.py` exercises job-aware retrieval at all, and it deliberately stops before matching/assessment (by design, per its own module docstring — it measures retrieval in isolation).

### 2.2 Resolving the byte-identical-report question

The milestone brief asked us to investigate whether a prior "byte-identical after M8D.2" result meant the end-to-end evaluation runs the old, candidate-only pipeline instead of job-conditioned retrieval. **Confirmed true, directly in code**, not inferred from docs:

`evaluation_lib/end_to_end_eval.py:80-86`:
```python
def build_candidate_profiles(fixtures: dict[str, dict]) -> dict:
    profiles = {}
    for name, fixture in fixtures.items():
        client = build_fake_client(fixture)
        result = extract_candidate_evidence(name, client=client, top_n=fixture["top_n"])
        profiles[name] = result.profile
    return profiles
```

One `CandidateEvidenceProfile` is built **per candidate** (never per candidate×job pair) and reused unchanged across every job in the matrix. `job_relevance_terms` is never passed. This is architecturally incapable of reflecting M8D.2's retrieval change — not a bug in the harness, but a real, documented scope limitation (`docs/evaluation/MILESTONE_8D2_JOB_AWARE_RETRIEVAL.md` §7, last bullet, already disclosed this before 8E started). **M8D.2's effect on end-to-end outcomes was simply never measured by any existing script.**

### 2.3 The smallest additive fix: `evaluate_end_to_end_job_aware.py`

Per the brief's explicit allowance ("you may add evaluation-only tooling... if necessary for a fair, reproducible comparison"), a new, non-invasive script was added. It does not modify `evaluate_end_to_end.py` or any existing `evaluation_lib` module. For each matrix pair it:

1. Computes the job-independent baseline **fresh, under current code** (not read from the possibly-stale committed `end_to_end_report.json` — see §3's staleness finding, which made this necessary to avoid conflating 8D.2's effect with 8D.3's unrelated README fix).
2. Computes the job-aware result via the exact same composition `analyze_job_fit()` uses — imports its private `_relevance_terms_from_job_profile()` directly rather than reimplementing the bridge logic.
3. Diffs `alignment_score`/`required`/`preferred` and reports which repositories were newly analyzed.

This is evaluation-only (reads `evaluation/`, calls only already-existing, unmodified production functions) and does not change benchmark semantics of any existing script.

---

## 3. Reproducible benchmark comparison

All six commands below were re-run fresh against `f5b1c31` from the repo root.

| # | Command | Result | vs. documented |
|---|---|---|---|
| 1 | `python scripts/evaluate_job_parser.py` | CORRECT=58 MISSING=44 WRONG_ALT=1 — Recall=0.563, Precision=0.892 | ✅ exact match, `MILESTONE_8D1...md` |
| 2 | `python scripts/evaluate_job_parser.py --corpus-version 8c:v1.1` | CORRECT=66 MISSING=37 — Recall=0.641, Precision=1.0 | ✅ exact match |
| 3 | `python scripts/evaluate_evidence.py` | False positives: **1** (fresh run) | ⚠️ committed `evidence_report.md` says **2** |
| 4 | `python scripts/evaluate_evidence.py --corpus-version 8c:v1.1` | False positives: 0 | ✅ exact match; `_v1_1` committed file already byte-identical |
| 5 | `python scripts/evaluate_repository_retrieval.py` | recovered=2, already_covered=0, missed=2, correctly_excluded=3, false_positive=0 | ✅ exact match; committed file byte-identical |
| 6 | `python scripts/evaluate_end_to_end.py` | 1/12 cells differs from committed file: `karpathy×frontend_01` 80→60, required (4,4)→(3,4) | ✅ exact match to the change `MILESTONE_8D3...md` §8 predicts |

**Finding, not a bug:** run #3's discrepancy is `evaluation/reports/evidence_report.md`/`.json` (the frozen, no-flag `8c:v1` report) being **genuinely stale relative to current code** — it was last regenerated after M8D.1 but before M8D.3's README-attribution fix, and `MILESTONE_8D3_EVIDENCE_ATTRIBUTION.md` §7 explicitly says this file is "intentionally left un-regenerated." Confirmed exactly as documented: the only remaining false positive after 8D.3's fix is the pre-existing, unrelated `sindresorhus/Gifski`→`language.swift` stale-gold row (predates `language.swift`'s registration, not touched by 8D.3). All diffs produced by re-running were reverted with `git checkout --` after inspection; the tree was confirmed clean before continuing.

### 3.1 Job-aware vs. job-independent end-to-end (new measurement, §2.3's script)

Running `scripts/evaluate_end_to_end_job_aware.py` against all 12 `evaluation/gold/matrix.json` pairs, with **both** baselines computed fresh under current code (isolating the 8D.2 retrieval effect from the unrelated 8D.3 README fix):

| candidate | job_id | job-independent alignment | job-aware alignment | changed? | newly-analyzed repos |
|---|---|---|---|---|---|
| karpathy | ml_engineering_01 | 75 | 75 | No | 6 repos (arxiv-sanity-lite, arxiv-sanity-preserver, covid-sanity, examples, pytorch-made, tf-agent) |
| karpathy | computer_vision_01 | 100 | 100 | No | 7 repos |
| karpathy | frontend_01 | 60 | 60 | No | 7 repos |
| torvalds | systems_cpp_01 | 67 | 67 | No | (none) |
| torvalds | embedded_firmware_01 | 50 | 50 | No | (none) |
| torvalds | data_science_01 | 20 | 20 | No | (none) |
| sindresorhus | frontend_01 | 80 | 80 | No | 10 repos |
| sindresorhus | fullstack_01 | 57 | 57 | No | 10 repos |
| sindresorhus | robotics_controls_01 | 33 | 33 | No | 7 repos |
| Jango1324 | embedded_firmware_01 | 0 | 0 | No | (none) |
| Jango1324 | ml_engineering_01 | 50 | 50 | No | **Pneumonia-Detection-Ai** |
| Jango1324 | general_swe_01 | 100 | 100 | No | **Pneumonia-Detection-Ai** |

**Result: 0 of 12 pairs' `alignment_score`/`required`/`preferred` changed**, even though job-aware retrieval materially expands the analyzed repository set in 9 of 12 pairs — including recovering `Pneumonia-Detection-Ai`, M8D.2's own headline recovery example (`RETRIEVAL_RECOVERED` in the retrieval harness). The newly-analyzed repositories' evidence was, in every one of these 12 cases, redundant with concepts already supported from the generic top-15/top-25 selection — job-aware retrieval changed *which* repositories were analyzed, never *whether* any requirement's verdict flipped, **on this specific 12-pair matrix**.

**This is the headline methodology finding for Phase 1:** M8D.2 cannot be credited with improving end-to-end alignment outcomes based on any evidence gathered so far — not because it doesn't work (the dedicated retrieval harness shows it does recover genuinely relevant repositories), but because this particular 12-pair matrix happens not to contain a case where the newly-recovered evidence would have flipped a requirement that was previously `not_observed`. The matrix was designed for 8C's qualitative positive/partial/negative spread, not for job-aware-retrieval sensitivity — a genuine corpus limitation (§4), not a retrieval defect.

---

## 4. Corpus limitations

- **The 12-pair matrix was never designed to exercise retrieval sensitivity.** §3.1 shows 0/12 pairs are sensitive to job-aware retrieval under the current relevance signal set — this says more about the matrix's design goal (qualitative direction checks) than about M8D.2's real-world value, which the separate 7-case retrieval harness measures directly instead (2 recovered, 2 known-limitation misses).
- **The frozen `8c:v1` evidence/end-to-end reports are stale by design**, not by accident — confirmed in §3, and already disclosed in `MILESTONE_8D3_EVIDENCE_ATTRIBUTION.md` §7/§8. Anyone reading only the committed `evaluation/reports/*.md` files (not the `_v1_1` variants, and not re-running the scripts) sees numbers one milestone out of date for the evidence/end-to-end layers.
- **Only 4 real candidate accounts, 15 synthetic job postings, 12 matrix pairs.** Every quantitative claim in this report inherits that small-N sample; percentages (e.g. "37/103 missing") are precise counts on this fixed corpus, not estimates of a broader population.
- **No ground-truth "true fit" label exists anywhere in this corpus** (`expected_direction` is a qualitative sanity check, never scored) — there is no way to compute a real precision/recall for the *product's* top-level promise, only for its individual layers (parser recall/precision, evidence found/missing/false-positive, retrieval outcome classification).

---

## 5. Current end-to-end results — Phase 3 scenario walkthrough

All data below is from live runs against the real pipeline (`analyze_job_fit()`-equivalent composition), using only existing fixtures/jobs/matrix — nothing invented.

**1. Strong-match pairing** — `karpathy × ml_engineering_01` (matrix: `positive`). 6 requirements parsed (3 required-technical, 1 required-non-technical, 2 preferred). `language.python` and `ml.framework.pytorch` SUPPORTED; `infra.docker` NOT_OBSERVED (genuine gap: no analyzed repo has a Dockerfile); 2 non-technical claims NOT_ASSESSABLE. **Alignment=75, required (2,3), preferred (1,1).**

**2. Weak-match pairing** — `torvalds × data_science_01` (matrix: `negative`). 5 requirements, all technical. Only bare `language.python` SUPPORTED; `data.library.pandas`, `unresolved:numpy`, `language.sql`, `language.jupyter_notebook` all NOT_OBSERVED (torvalds' 12 kernel/tooling repos genuinely carry none of this). **Alignment=20, required (1,4).**

**3. Job requiring unregistered technologies** — confirmed via live parse that entire bullets vanish with **zero** `JobRequirement` rows produced (not even an `unresolved:` placeholder):
- `frontend_01`: "Knowledge of Vue or Angular" (preferred OR-group)
- `embedded_firmware_01`: "Familiarity with microcontroller peripherals such as SPI, I2C, and UART"
- `data_engineering_01`: "Experience with Snowflake or BigQuery", "Experience with dbt"
- `robotics_controls_01`: "Experience with MATLAB or Simulink...", "Familiarity with PLC programming", "Experience with control systems or state estimation"

This is a **new finding beyond what 8C/8D.1 already documented** (those reports counted these as `MISSING` gold rows against known registry gaps; this milestone additionally confirms, by direct parse, that the *entire claim* — not just its concept id — disappears from `JobRequirementProfile.requirements`, with no structural trace at all, not even on the non-technical side).

**4. Alternative-requirement role** — `Jango1324 × general_swe_01`: "Proficiency in at least one of Python, Java, or C++" parses correctly as one alternative-group requirement; `matched_concept_ids=(language.cpp, language.java, language.python)` (all three present in Jango1324's repos) → SUPPORTED. **Alignment=100, required (1,1), preferred=None** (confirmed live — this job has zero preferred requirements at all, not a display artifact).

**5. Professional-experience requirement GitHub cannot assess** — same pair: "Bachelor's degree in Computer Science, Engineering, or equivalent experience" → NOT_ASSESSABLE, correctly never rendered as "failed."

**6. Relevant repos crowded out of retrieval** — re-verified live against current code (not copied from the 8D.2 doc): `sindresorhus` has **1,142** total repositories; **992** score `>0` for `fullstack_01`'s relevance terms; `execa` scores exactly `1.0` (matched only via the single weak `language.javascript` term) and ranks **231st of 992** by the deterministic tie-break — nowhere near `relevance_top_k=10`. Still `RETRIEVAL_MISSED_RELEVANT` under current code. Same confirmed for `karpathy/nn-zero-to-hero` against `computer_vision_01` (ranks 38th of 39 same-concept-cluster competitors).

**7. README evidence that could be misleading** — swept every fixture README's markdown headings against `readme_context.py`'s `NON_IMPLEMENTATION_SECTION_HEADINGS` denylist. Two structurally-identical-but-unlisted headings were found: `sindresorhus/got`'s `"## Comparison"` (a full feature table vs. `node-fetch`/`ky`/`axios`/`superagent`) and `sindresorhus/file-type`'s `"### Available third-party file-type detectors"`. **Neither currently produces a live false positive** — the compared/listed items are npm package names and file formats, not registry concept aliases — but the denylist is a fixed heading-text match, not a semantic one, so this is a demonstrated latent gap (a differently-worded "list of other things" section), not yet a triggered bug in this specific corpus.

**Overall assessment of report usefulness:** for the scenarios tested, the pipeline consistently distinguishes SUPPORTED / NOT_OBSERVED / NOT_ASSESSABLE in a way that never equates "not observed on GitHub" with "candidate lacks the skill" (confirmed by direct inspection of `MatchStatus`'s own docstring and every requirement_match printed above — no status string anywhere renders as a capability judgment). The biggest usefulness gap is **upstream of assessment**: scenario 3's silently-vanishing bullets mean a recruiter reading "required (1,1), 100%" for `Jango1324 × general_swe_01` has no way to know the posting's degree requirement was the ONLY other bullet and it was correctly excluded — that's fine here, but the *same silent-drop mechanism*, applied to a posting whose only substantive bullet happens to need an unregistered concept, can produce a technically-honest but practically-empty assessable set with no visible explanation of why.

---

## 6. Score interpretability risks (Phase 4)

Concrete, not hypothetical, pulled from the current matrix + live reruns:

- **Assessable denominator of exactly 1** appears in 5 of 12 matrix pairs (`torvalds×systems_cpp_01` required (1,1); `torvalds×embedded_firmware_01` required (1,1); `Jango1324×embedded_firmware_01` required (0,1); `Jango1324×general_swe_01` required (1,1); plus preferred=(1,1) in two `karpathy` pairs). Each is a single pass/fail with no partial credit, by construction of the half-up percentage formula — a 100%-vs-0% swing hinges on one concept's evidence.
- **`preferred=None` confirmed live**: `Jango1324×general_swe_01` has zero preferred requirements. Not a display bug — this job posting genuinely has none after parsing — but a reader who doesn't know "None" differs from "0 of 0" could misread it.
- **No `required=None` remains in the current matrix** (the historical `torvalds×embedded_firmware_01` None case, M8C's headline finding, is now (1,1) post-M8D.1's bare-C fix) — but §5 scenario 3 shows the *mechanism* that produces `None`/near-empty denominators (whole bullets silently dropped pre-assessment) is still fully live for any job/bullet combination outside this specific matrix.
- **Crowding (§5 scenario 6) directly shrinks the evidence pool feeding the denominator-1 cases above** — a candidate with one relevant repository sitting at rank 231 of 992 same-signal competitors contributes nothing to assessability, same as if the repository didn't exist, for any job sharing that weak signal.
- **Causal link between scenario 3 and this section:** the registry-gap bullets that vanish entirely (never even reaching `NOT_ASSESSABLE`) shrink the assessable denominator further than a reader counting bullets in the raw job posting would expect — a 7-bullet posting can produce an assessable set of 2–3, making the published percentage far more volatile than its face value suggests.

None of these are scoring-formula defects (the formula does exactly what its own half-up percentage design states); the risk is entirely in a reader's intuition about what a given denominator size implies, compounded by two upstream mechanisms (registry gaps, retrieval crowding) that shrink it below what the job posting's bullet count would suggest.

---

## 7. Failure analysis (Phase 5)

| Category | Count / evidence | Severity |
|---|---|---|
| Registry/parser coverage gaps | 37 MISSING (8c:v1.1, re-derived live) — Vue, Angular, MATLAB, Simulink, PLC, SPI, I2C, UART, BigQuery, Snowflake, dbt, Terraform, Jenkins, GraphQL, OAuth, CMake, scikit-learn, OpenCV, Azure/GCP, generic phrases | Medium-high, well understood, batchable |
| Entire-bullet silent drop (new, §5.3) | 4+ confirmed live examples across 4 job files, zero structural trace | **High** — worse than a visible MISSING because there is no row to even notice is missing in the parsed profile itself |
| Repository retrieval crowding | 2 confirmed `RETRIEVAL_MISSED_RELEVANT` (re-verified live); mechanism scales with account size (992-way tie for `sindresorhus`) | Medium-high, architectural, needs a discriminating signal not a bigger cutoff |
| Evidence attribution | 0 current false positives on `8c:v1.1` (confirmed live); 1 latent-but-untriggered near-miss class found (§5.7, heading-denylist is lexical not semantic) | Low now, latent risk remains |
| Score interpretation | 5/12 matrix pairs have a denominator-1 required or preferred bucket; causally worsened by the two gaps above | Medium, UX/communication problem more than a correctness bug |
| Job-aware retrieval's real end-to-end effect | 0/12 pairs changed (new measurement, §3.1) — not a defect, a corpus-design gap: the existing matrix cannot certify M8D.2's end-to-end value either way | Measurement gap, not a product gap |
| Benchmark/reporting discipline | 1 confirmed stale committed report (`evidence_report.md`, pre-8D.3) — intentional per docs, but a maintenance trap for anyone reading the committed file without cross-checking the `_v1_1` variant or re-running | Low-medium, process risk |

No accuracy/precision number was invented where ground truth doesn't exist — every count above is either a direct corpus measurement or explicitly marked as a qualitative/non-scored observation.

---

## 8. Five highest-priority product issues

Ranked by user impact × correctness risk × frequency, not by implementation ease:

1. **Entire requirement bullets vanish with zero structural trace when their only concept is unregistered** (§5.3, §6). This is strictly worse than the already-documented `MISSING` classification: a `MISSING` gold row at least corresponds to a real `JobRequirement` the evaluator could annotate against; here there is no requirement object at all, so a future "show all parsed requirements, including unassessable ones" UI feature would have nothing to display for these bullets. Highest-impact single fix: even a non-technical placeholder (`category="unregistered_concept"`, `NOT_ASSESSABLE`) for every dropped bullet would make the gap visible without touching the concept registry or scoring.
2. **Small, job-aware-retrieval-insensitive assessable denominators make the alignment score volatile in a way readers won't anticipate from the raw job posting's length** (§6). Not a formula bug, but the single biggest interpretability risk for a recruiter-facing product — a 7-bullet posting silently assessing only 2 bullets looks, numerically, identical to a posting that genuinely only had 2 substantive bullets.
3. **Repository-retrieval crowding has no mechanism that scales with account size** (§5.6, §7) — confirmed still live (execa at 231/992, nn-zero-to-hero at 38/39). This is the one issue flagged as architecturally "LARGE" scope back in 8C and still unresolved; it compounds with #1 and #2 (a crowded-out repository's evidence can't rescue a shrunk denominator).
4. **No existing harness measures whether job-aware retrieval (M8D.2) changes end-to-end outcomes** (§3.1, §4) — a genuine measurement gap, now partially closed by this milestone's new script, but the underlying matrix should be deliberately expanded (not just re-used) with at least one pair designed so a crowded-in repository's newly-recovered evidence would flip a requirement, to actually certify M8D.2's value claim going forward.
5. **README section-heading denylist is a fixed lexical list, not a semantic classifier** (§5.7) — zero live false positives today, but two real, unlisted near-miss headings were found in the existing fixture corpus itself (`"## Comparison"`, `"### Available third-party X"`), meaning the next README that happens to compare itself against something sharing a registry alias will reproduce the exact `llm.c` bug class 8D.3 just fixed.

---

## 9. Recommended Milestone 9

**Primary recommendation: fix issue #1 (entire-bullet silent drop) first, paired with expanding the Phase-3 scenario set into a small, deliberate addition to `evaluation/gold/matrix.json`/`retrieval_cases.json` that can actually certify or falsify M8D.2's end-to-end value (issue #4).**

Rationale for this pairing over picking either issue alone:
- #1 is the single highest-severity, highest-frequency finding in this milestone (confirmed live in 4 of 15 job postings) and is a **small, mechanical, additive fix** (a placeholder non-technical requirement for any claim whose sole candidate concept has no registry id) — same risk profile as M8D.1's registry-additive work, not a new design problem.
- #4 costs almost nothing beyond the script already built in this milestone (§2.3) plus 2-3 deliberately chosen new matrix pairs (e.g. pairing `sindresorhus` against a job whose relevance terms would recover a repository carrying evidence for a currently-`NOT_OBSERVED` requirement) — it converts "we don't know if M8D.2 helps end-to-end" into a real, reproducible number either way.
- Both are evaluation-adjacent/small-scope, continuing this milestone's own momentum, and neither requires touching the scoring formula, matcher, or concept registry's semantics (only registry-additive work and new gold data).

**Explicitly deprioritized for M9** (not because they're unimportant, but because they are larger-scope, less-understood, or already explicitly out-of-scope per the user's own long-term roadmap):
- The retrieval-crowding architecture problem (#3) — still correctly flagged as "LARGE, needs product judgment" per 8D.2's own doc; no new information from this milestone changes that assessment.
- Any LLM-based scoring, CatBoost, or role-specific/market-aware scoring — explicitly out of scope per `CLAUDE.md`'s MVP-first priority order and this milestone's own constraints.
- The README-heading-denylist generalization (#5) — real but zero-frequency in the current corpus; worth a short design note, not urgent implementation.

---

## 10. Reproduction instructions

```bash
# Phase 0 baseline
git status --short && git log -5 --oneline
python -m pytest                                               # 864 passed

# Phase 2 benchmark comparison (Section 3 of this report)
python scripts/evaluate_job_parser.py                           # 8c:v1, frozen
python scripts/evaluate_job_parser.py --corpus-version 8c:v1.1
python scripts/evaluate_evidence.py                             # 8c:v1 -- NOTE: committed report is stale, see Section 3
python scripts/evaluate_evidence.py --corpus-version 8c:v1.1
python scripts/evaluate_repository_retrieval.py
python scripts/evaluate_end_to_end.py                            # NOTE: committed report is stale for karpathy x frontend_01

# New in 8E -- job-aware end-to-end comparison (Section 3.1)
python scripts/evaluate_end_to_end_job_aware.py

# Evaluation harness self-test
python -m pytest tests/test_evaluation_harness.py -q            # 27 passed
```

Running `evaluate_evidence.py` and `evaluate_end_to_end.py` with no flag will produce a local diff against the committed `8c:v1` report files (§3) — this is the already-documented, intentional staleness from M8D.3, not a new regression. Restore with `git checkout -- evaluation/reports/evidence_report.json evaluation/reports/evidence_report.md evaluation/reports/end_to_end_report.json evaluation/reports/end_to_end_report.md` if a clean tree is needed afterward.

---

## End-of-milestone verification

```
python -m pytest           -> 864 passed
git diff --check           -> (no output: no whitespace errors)
git status --short         -> 2 untracked files only (new evaluation script + its report)
git diff --stat             -> (empty: nothing tracked was modified)
```
