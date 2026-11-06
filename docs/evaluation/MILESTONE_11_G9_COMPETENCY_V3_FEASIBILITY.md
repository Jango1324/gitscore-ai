# Milestone 11-G9 — Offline Competency Extractor V3 Feasibility

**Status: evaluation complete, STOPPED per instructions. No production code changed. No commit/push made.**

M11-G8 is complete and already pushed (`0536b20`); it is not recommitted, regenerated, or modified by this milestone. This document, the fresh corpus, the v3 prototype, the evaluation harness, and the focused tests are all **new, untracked, local-only files** — see §10 for the exact inventory. Nothing has been staged or committed.

## 0. Baseline verification

| Check | Expected | Confirmed |
|---|---|---|
| HEAD | `0536b20e4526c43213d0f6f5fccd01f310156344` | ✅ matches |
| Branch | `main` | ✅ matches |
| Parser version | `job_description_parser:v12` | ✅ matches, unchanged throughout this milestone |
| Full suite before this milestone | 1739 passed / 13 skipped / 2 xfailed | ✅ matches (this was M11-G8's own post-commit state) |
| Full suite after this milestone | — | **1748 passed** / 13 skipped / 2 xfailed (+9 new M11-G9 focused tests, zero regressions) |

v1/v2 (`src/gitscore/jobs/parsing/competency_extraction.py`) and `competency_aliases.py` are byte-unchanged — confirmed by `git status`/`git diff` showing zero modifications to any tracked file, and by `tests/test_m11g9_v3_feasibility.py::test_v1_v2_module_is_byte_identical_to_pre_g9_state`.

## 1. Corpus and holdout independence (Phase 1)

A fresh, independently-sourced corpus of **14 live `jobs.lever.co` postings** was acquired via WebSearch/WebFetch, November 2026, split into a **DEV set (7 postings, 122 annotated controls)** used to shape the v3 prototype, and a **SEALED HOLDOUT (7 postings, 100 annotated controls)**, hash-frozen *before* v3 was written and never touched again.

- No company from M11-D/M11-F/M11-G5 appears in this corpus. One incidental overlap was found and disclosed rather than hidden: **Vida Health** also appears in M11-F, but as a *different, separately-URLed posting* for a different role title (M11-F used a backend-focused title; this corpus uses a data-engineering-focused title). It is placed in the DEV split specifically so it carries no holdout-integrity risk.
- 4 of 18 initially-located posting URLs (Coderio, Daily Wire, two Kpler URLs, Aircall) returned HTTP 404 by fetch time and were replaced with alternate live postings rather than forced through or fabricated — disclosed in `evaluation/m11g9/provenance.json`.
- Domains covered: software, ML, data engineering, embedded firmware, cybersecurity, cloud infrastructure/DevOps, electrical, and robotics/computer-vision — deliberately skewed toward modern web/cloud/identity/data roles the existing 17-tag ontology was never built against, to stress-test it honestly rather than confirm it on familiar ground.
- Full qualifications **and** responsibilities text was captured (not qualifications alone), so the corpus can test responsibility/narrative suppression, not just tag recall.
- One line in the Extreme Networks source file is this project's own descriptive paraphrase (added while locally saving the posting, not genuine employer text) and is explicitly excluded from annotation — disclosed in `m11g9_author_holdout_annotations.py`'s own docstring rather than silently annotated as if genuine.
- **Holdout freeze**: `evaluation/m11g9/gold_hash_freeze.json`, computed immediately after annotation, before v3 (Phase 3) was written or run against it. `tests/test_m11g9_v3_feasibility.py::test_m11g9_holdout_gold_hash_unchanged` re-verifies this on every test run.
- Posting text, full annotations, and all verbatim quotes stay local-only — never reproduced verbatim in this document or in any report JSON (every report below uses control IDs and aggregate counts only; see §10 for the publication-safety discipline applied).

## 2. Ontology audit (Phase 2)

Direct inspection of `competency_aliases.py` (the 17-tag alias table) and `competency_extraction.py` (the 17-tag canonical vocabulary + observability table), cross-referenced against all 222 freshly-annotated controls.

### 2a. Missing aliases for already-supported concepts

Several genuine paraphrases of an EXISTING tag's competency do not literally match any canonical phrase or active alias:

- **embedded-systems-design**: `RTOS environments`/`RTOS experience` (product-name-based phrasing naming specific RTOS products rather than the literal existing alias phrase "RTOS development"); `developing (software for) bare metal` (verb-first paraphrase of "bare-metal programming"); `developing device drivers` (word-order variant of the existing alias "device driver development").
- **signal-processing**: `designed/designing filters` (verb-first paraphrase of the canonical "filter design").
- **database-design**: `data modeling` / `dimensional modeling` (narrower instance of "schema design" not currently aliased).
- **cybersecurity-threat-modeling**: `secure development practices`, `application vulnerabilities` — conceptually in-scope, no literal match.

### 2b. Genuinely missing concepts (no tag at all)

The single largest finding of this audit. Recurring across **5 or more** independently-sourced postings, with no representation whatsoever in the 17-tag ontology:

- **Generative AI / agentic systems** — appeared in 5 of 14 postings (Extreme Networks, Basis, Board Intelligence, Simbe Robotics, PointClickCare), spanning both a competency-shaped claim (naming generative-AI/agentic-systems experience directly) and a tool-use claim (routine use of AI coding assistants). The strongest, most recurring gap found.
- **Cloud infrastructure / DevOps / IaC** (Infrastructure-as-Code, CI/CD, Kubernetes, GitOps) — PointClickCare, Extreme Networks.
- **Data engineering / ETL / pipelines** (ingestion, data-pipeline correctness, data warehousing) — Vida Health, Firework, Extreme Networks.

Found but **not** promoted (single-posting evidence within this bounded corpus, deliberately not fabricated into a tag per the milestone's own "do not auto-create a tag for every technology noun" restriction):
Identity & authorization (OAuth2/OIDC/ReBAC — Basis only), SRE/production-ops practices (WMG, PointClickCare — only 2 postings, judged below the bar used for the other 3), realtime-ML-serving infrastructure (MoonPay only), robotics middleware/SLAM (Simbe only), electromechanical integration (Hydrow only).

### 2c. Overlapping/conflated concepts — risk of assigning a broad tag from narrow evidence

Found directly inside this corpus's own text, each a concrete illustration, not a hypothetical:

1. `incident management` (general SRE/production-ops, WMG) vs. the EXISTING active alias `incident response` (cybersecurity-threat-modeling). Same English word shape, different discipline — a naive alias addition here would wrongly imply security-incident-handling skill from a sentence about pager rotations.
2. `cost optimization` / `cloud cost optimization` (PointClickCare) vs. performance-optimization. Shares the word "optimization"; is a FinOps concept, not a performance claim.
3. `AI/ML workload exposure` (operational, PointClickCare) vs. ml-fundamentals (modeling theory). Operating ML infrastructure is not the same competency as understanding ML theory.
4. `embedded systems` as an ML-model **deployment target** (a sentence about deploying real-time AI models onto embedded/edge hardware, Simbe Robotics) vs. embedded-systems-design as a **firmware-engineering discipline**. Same keyword, different discipline; the GitHub signal that would actually validate the Simbe claim is inference/deployment tooling, not firmware repositories.
5. `networking background` (Extreme Networks, generic) vs. os-networking (specific technical competency) — too ambiguous a bare phrase to safely alias.

### 2d. Concepts that cannot be GitHub-assessed

No new NOT_OBSERVABLE concept was found — on the contrary, several newly-identified concepts (OAuth/identity usage, Infrastructure-as-Code, data-pipeline tooling) are directly, strongly observable from repository content (dependency manifests, `.tf`/`.yaml` files, pipeline DAG code) if ever represented at all. The dominant NOT_OBSERVABLE category remains what it already was: soft-skill/leadership/communication/legal-eligibility claims, which are pervasive across every single posting in this corpus and are a structural ceiling on the whole `TECHNICAL_COMPETENCY` category, not an ontology gap.

### 2e. Proposed versioned internal representation (documentary only — no schema change made)

The current `CompetencyAlias` model (`tag`, `phrase`, `relation`) assumes every alias maps to exactly one EXISTING parent tag. It cannot represent a genuinely new, independent top-level concept (it has no "this IS a new tag, not an alias of one" case) and cannot represent a concept that is adjacent to *two* existing tags without being subordinate to either (e.g. data-engineering/ETL sits between database-design and distributed-systems without being a narrower instance of either). A future, properly-approved ontology change should move toward a `CompetencyConcept` graph — `concept_id`, `display_name`, optional `parent_concept_id`, `relation_to_parent` (reusing the existing `AliasRelation` enum), `github_observability`, `status` (`ACTIVE`/`PROPOSED`/`REJECTED`), `introduced_in` (milestone ID) — generalizing today's flat (tag, phrase, relation) triples into a tree that can hold both narrower/equivalent relations to an existing tag AND genuinely new top-level concepts side by side. **Not implemented as a schema change in this milestone** — sketched here only as the Phase 2 deliverable the brief asked for; the v3 prototype (§3) implements the three strongest new concepts as plain additional tag rows, deliberately NOT as a new data model, to keep this milestone bounded.

## 3. V3 prototype (Phase 3)

`scripts/evaluation_lib/m11g9_competency_extraction_v3.py` — evaluation-only, lives entirely outside `src/gitscore`, imports v1/v2's real primitives read-only, never modifies them. Confirmed by `test_v1_v2_module_is_byte_identical_to_pre_g9_state` and `test_v3_is_not_imported_by_production_or_by_v1_v2`.

v3 reuses v2's exact control flow (negation → narrative → responsibility-lead → OR-list structural safety → single/AND-split) and every existing safety rule unchanged. The ONLY change is a larger vocabulary table, via two bounded, corpus-traceable additions:

1. **3 new top-level concepts** (§2b's three recurrence-justified candidates): `generative-ai-agentic-systems`, `cloud-infrastructure-devops`, `data-engineering-pipelines` — each with its own `GithubObservability` entry (`PARTIALLY_OBSERVABLE`, `STRONGLY_OBSERVABLE`, `STRONGLY_OBSERVABLE` respectively).
2. **4 targeted missing-alias-phrasing fixes** for existing tags (§2a's four findings: RTOS environments/experience, bare-metal paraphrase, filter-design verb-first paraphrase, data/dimensional modeling).

v3 deliberately leaves every §2c "risky" case un-aliased — declining by absence, the same mechanism v1/v2 already use for every other excluded case. No LLM or external API calls; no live integration.

## 4. Phase 4 — fair v2-vs-v3 evaluation on the sealed holdout

Run exactly once, by `scripts/evaluate_m11g9_v3_feasibility.py`, which verifies the holdout's frozen hash before reading it (hard failure on mismatch). Results also computed on the DEV set, labeled diagnostic-only and never used for the decision below.

### 4a. Headline numbers — SEALED HOLDOUT (100 controls, 27 `technical_competency`)

| Metric | v2 | v3 |
|---|---|---|
| Technical-competency controls recognized (≥1 tag produced) | 1 / 27 | 2 / 27 |
| Denominator **A** — recall against the **existing 17-tag** set (17 taggable controls) | **1/17 = 5.88%** | **1/17 = 5.88%** (no change) |
| Denominator **B** — recall against the **3 new v3 concepts only** (3 taggable controls) | 0/3 = 0% | **1/3 = 33.33%** |
| Tag-level false positives (any emitted tag ≠ expected) | 0 | 0 |
| False positives on non-qualification controls (73 responsibility/narrative/education/named-tech/nontechnical controls) | **1** | **1** (identical row — see §5) |
| Necessity accuracy among resolved predictions | not computed (0 resolved — see §6) | not computed (0 resolved) |

**v3's bounded alias-table fixes for the EXISTING 17 tags produced ZERO net holdout recall gain** (0/4 targeted fixes actually fired on sealed-holdout text — see §7 for why). **v3's 3 new concepts produced exactly 1 additional correct tag** (a Firework control naming ETL/ELT, data-pipeline, and data-warehousing concepts together, correctly tagged `data-engineering-pipelines`), out of 3 eligible controls. Overall recognition moved from 1/27 to 2/27 technical-competency controls.

Full machine-readable results: `evaluation/reports/m11g9_phase4_v2_vs_v3.json` (sealed holdout, decisive) and `..._DEV_DIAGNOSTIC.json` (dev set, diagnostic only, never used for §9's decision). Every row is identified by control ID only — no verbatim posting text in either file.

### 4b. Why holdout recall (5.88%) is even lower than M11-F (16%) or M11-G5 (12.5%)

Not a regression — a deliberate corpus-design consequence. M11-F/M11-G5 sampled domains closer to the ontology's own CS-fundamentals/STEM-interview design center (embedded, electrical, cybersecurity, backend). M11-G9 deliberately added identity/auth, cloud DevOps, and data-engineering postings specifically because those domains were under-represented before — and they turned out to have almost zero representation in the 17-tag vocabulary at all. This is the single most important empirical finding of this milestone (§9).

## 5. Precision / safety findings

Both v2 and v3 produce the **exact same single false positive**, on the exact same control, on a sentence that is **not** a `technical_competency` control at all:

> A `nontechnical` holdout control (Simbe Robotics, a soft-skill sentence about debugging/benchmarking/systems-thinking ability) is mistagged `performance-optimization`.

Root cause: the existing ACTIVE alias `benchmarking` (`NARROWER_OR_MORE_SPECIFIC` under performance-optimization) fires on the bare word "benchmarking" used in a generic engineering-competence sense, not a performance claim. **This is a pre-existing v1/v2 defect, confirmed inherited unchanged by v3, not introduced by it** (`test_v3_introduces_no_new_false_positive_beyond_v2` pins exactly this). v3's own new vocabulary introduces **zero** new false positives anywhere in the 100-control sealed holdout.

Three additional confirmed-safe declines worth noting as deliberate successes, not gaps:
- A PointClickCare responsibility line about on-call/incident handling, which contains the literal, active alias phrase "incident response," is correctly suppressed by `_RESPONSIBILITY_LEAD` (it opens with a bare imperative duty verb), not tagged.
- A Simbe Robotics responsibility line naming literal computer-vision canonical phrases (object-detection/segmentation terminology) while opening with a bare imperative duty verb ("Own...") is correctly suppressed the same way.
- An Extreme Networks 7-item OR-list of mostly out-of-ontology infrastructure/data terms, where the only item with any existing mapping at all ("microservices") is an EXCLUDED/related_only alias, is correctly declined in full by both v2 and v3 (excluded aliases are never consulted by the active matcher) rather than silently tagged via the one coincidentally-related word.

## 6. Necessity-accuracy limitation (disclosed, not scored as a defect)

Both extractors were called sentence-level, matching M11-F/M11-G5/M11-G8's own established direct-call convention (no document-level `section_kind` context). Without a section hint, `infer_necessity(text, None)` correctly returns an **unresolved** (`None`) necessity for any sentence lacking a local REQUIRED/PREFERRED marker — this is the project's own, pre-existing, intentional conservative behavior (an unresolved necessity safely routes to `UnparsedClaim`, never a silently-wrong score), not a v3 regression. Every one of the handful of recognized controls in this evaluation happened to lack a local marker, so necessity accuracy is reported honestly as "0 resolved predictions to score," not fabricated into a misleading percentage.

## 7. Per-category failure analysis — why v3's targeted alias fixes under-delivered

Direct tracing of all 4 targeted fixes against the sealed holdout found two distinct, independent blocking mechanisms, illustrating the same "earliest blocking stage ≠ sole blocking stage" lesson M11-G8 established, now reproduced at the vocabulary-fix level:

- **Word-order mismatch the new alias didn't anticipate**: a Laminar control phrasing embedded C/C++ skill as applying "on microcontrollers" (prepositional phrasing) rather than the ACTIVE alias's literal "microcontroller programming" (noun-phrase order) — a genuine miss, confirming the gold annotation's own `semantically_equivalent` judgment was about human-level meaning, not a prediction of current regex behavior.
- **An orthogonal, pre-existing intent-gate gap**, discovered while directly testing v3's own new bare-metal alias end-to-end on an Alif Semiconductor control: the control's text uses the adjective construction "proficient in developing software for bare metal..."; v3's new alias regex *does* match the stemmed text, confirmed by direct test, but `_QUALIFYING_INTENT_V2` (reused unchanged from v2) requires the noun form ("proficienc*y* with/of/in") and does not recognize the adjective construction ("proficient in"). The vocabulary fix was necessary but not sufficient; v3 deliberately did not also patch the intent gate (out of this milestone's bounded scope, and not something its own docstring commits to reusing unmodified) — recorded here as a found limitation, not implemented.

Both are documented, reproducible, and testable — not hypothesized.

## 8. Scoring-contract compatibility

No `Qualification`/`NormalizedReference`/`DeclinedExtraction` field was added or changed. v3's 3 new concepts are represented as ordinary `competency_tag` strings on the existing `NormalizedReference`, exactly like any of the 17 existing tags — no new field, no schema migration, fully compatible with every existing consumer of a `Qualification` object. The missing-contract decline path (an OR-list naming multiple distinct competency tags) is unchanged and was exercised correctly during evaluation (§5, the microservices OR-list case).

## 9. Recommendation (Phase 5)

**Recommended: Option (C) — fix the ontology/data-model gap before further extraction work**, with a secondary, explicitly-conditional note on Option (B).

Rationale:
- v3 showed a **real but small** gain (1 additional correct tag out of 27 sealed-holdout technical-competency controls; overall recognition 1/27 → 2/27; the existing-17-tag denominator was completely unmoved at 5.88%) with **zero** measured precision/safety cost. This does not meet the "meaningful recall gain" bar Option (A) requires to justify continuing bare deterministic vocabulary/alias-table expansion as the primary strategy.
- The dominant, by far largest blocker measured this milestone is **structural, not a vocabulary-coverage gap a bigger alias table can close at reasonable cost**: entire employer domains (identity/authorization, cloud DevOps, data engineering) have *no* tag representation at all, and even closing the 3 most-recurring new concepts required hand-curated regex vocabulary plus a recurrence-justification process (§2b) that does not scale — this single 14-posting corpus alone surfaced 8 distinct missing-concept clusters, of which only 3 cleared the ">=2 independently-sourced postings" bar used here. Scaling that process to adequately cover a modern SWE/ML/data/security/robotics job market would require dozens of further new top-level concepts, each needing the same manual process repeated.
- §7 additionally found that even a CORRECTLY-matching new alias can still be blocked by an orthogonal, pre-existing intent-gate phrasing gap — confirming that closing the ontology alone will not be sufficient without also eventually revisiting the intent-recognition layer, a second, separate piece of the "data-model" work Option (C) names.
- Per the milestone's explicit restriction, this report does **not** claim a semantic/LLM-based extraction approach would perform better — no such evidence was gathered. Once Option (C)'s ontology groundwork (the `CompetencyConcept` graph sketched in §2e, prioritized toward the proven-recurring new concepts) is in place, a **separate, future milestone** should evaluate whether a structured semantic-extraction PoC (Option B) closes the remaining gap faster than continued hand-curated deterministic expansion — but that is a follow-on question this milestone does not have evidence to answer, not a standalone recommendation made here.
- Option (D) (retain v2, no change) is not recommended either: v3 demonstrated, with real sealed-holdout evidence, that *some* bounded, disciplined deterministic improvement is possible with zero safety cost — discarding that finding entirely would be the opposite overcorrection.

This is a prototype-success-vs-production-readiness distinction, stated explicitly: v3's existence and its 1-control sealed-holdout win demonstrate the APPROACH is sound and safe when done carefully; it is not a recommendation to wire v3 into production, and no such change is proposed or made.

## 10. Regression status, file inventory, and commit-readiness (Phase 6)

**Regression status**: full suite 1748 passed / 13 skipped / 2 xfailed (was 1739/13/2 before this milestone; +9 is exactly the new M11-G9 focused test file, zero other change). `src/gitscore` is byte-identical to the stated baseline (confirmed via `git status`/`git diff` showing no tracked-file modifications, and via the focused tests' own structural confirmations). Parser remains `job_description_parser:v12`. No frozen historical gold (M11-F, M11-G5, or any earlier milestone's) was touched — confirmed unchanged by file content, and this milestone never opened any of those files for writing. No API/frontend/schema change was made. No posting text was published in this document or in any committed-eligible report file (every report uses control IDs and aggregate counts only, verified by direct inspection of `evaluation/reports/m11g9_phase4_v2_vs_v3*.json`, mirroring the exact convention already used by the committed `m11f_independent_holdout_report.json`/`m11g8_stage_attribution.json`). No previously-passing test was skipped or weakened.

**New, untracked files this milestone produced** (none staged, none committed):

```
docs/evaluation/MILESTONE_11_G9_COMPETENCY_V3_FEASIBILITY.md   (this document)
evaluation/m11g9/                                               (provenance.json, source_hashes.json,
                                                                  gold_hash_freeze.json, dev_annotations.json,
                                                                  holdout_annotations.json, source/dev/*.txt,
                                                                  source/holdout/*.txt — all local-only)
evaluation/reports/m11g9_phase4_v2_vs_v3.json                    (sealed-holdout results, decisive)
evaluation/reports/m11g9_phase4_v2_vs_v3_DEV_DIAGNOSTIC.json     (dev-set results, diagnostic only)
scripts/evaluate_m11g9_v3_feasibility.py                        (Phase 4 harness)
scripts/evaluation_lib/m11g9_author_dev_annotations.py          (Phase 1 dev-gold authoring)
scripts/evaluation_lib/m11g9_author_holdout_annotations.py      (Phase 1 holdout-gold authoring)
scripts/evaluation_lib/m11g9_competency_extraction_v3.py        (Phase 3 prototype)
tests/test_m11g9_v3_feasibility.py                              (Phase 6 focused tests, 9 passing)
```

If this work is later approved for commit, the same convention already used for M11-F/M11-G5 should be followed: commit `provenance.json`, `source_hashes.json`, `gold_hash_freeze.json`, the two Phase 4 report JSONs, the two evaluation-only scripts (`evaluate_m11g9_v3_feasibility.py`, `m11g9_competency_extraction_v3.py`), the test file, and this document; do **not** commit `evaluation/m11g9/source/`, `dev_annotations.json`/`holdout_annotations.json`, or the two `m11g9_author_*_annotations.py` builder scripts (all four contain verbatim third-party posting text) — only a redacted `*_metadata.json` companion, authored separately, mirroring `evaluation/m11f/holdout_annotations_metadata.json`'s own existing convention, should ever be committed in their place.

**Post-acceptance correction (pre-commit verification pass)**: during mandatory pre-commit verification, 5 of the test file's fixture strings (in `test_preexisting_benchmarking_false_positive_pinned` and `test_v3_declines_every_identified_risky_alias_case`) were found to be exact verbatim sentences lifted from the private holdout/dev source postings (WMG, Basis, PointClickCare x2, Simbe Robotics) — a violation of this milestone's own "no external posting text published" rule that the original authoring pass missed. They were rewritten as original synthetic sentences preserving the same alias/keyword triggers, confirmed via an n-gram overlap re-scan against the full private corpus and via all 9 focused tests plus the full 1748-test suite re-passing identically. No metric, finding, or test outcome elsewhere in this document changed as a result.

**Commit-readiness verdict**: Evaluation complete. Per explicit instruction, **STOPPING here — no commit or push performed, M11-G10 not begun.**
