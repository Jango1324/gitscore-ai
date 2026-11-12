# Milestone 11-G22-R3 — README context guard validation

**Status:** validation completed; **`readme:v5` was NOT implemented**. Neither G22-R2's Policy D (unchanged) nor
the narrowly revised R3 met the genuine-use recall criteria. Those criteria were frozen before the held-out set ran.

- **Production unchanged:**
  - parser `job_description_parser:v15`;
  - scoring `github_evidence_alignment:v2`;
  - matcher `requirement_matcher:v1`;
  - README extractor `readme:v4`;
  - registry version 4.
- `src/` is unchanged, registry data is unchanged, and no LLM call is made by GitScore.
- **Research accepted and committed** as a research-only commit ("test: validate README evidence guard recall
  tradeoffs") after authorization. The decision to stop without `readme:v5` was approved.
  - VAL-1 and VAL-2 are registered in the G14 manifest at that commit with their original freeze-time hashes
    (21 → 23 entries; the previous 21 are unchanged field for field).
  - Their freeze records keep their freeze-time note ("NOT registered … pending authorization"); they are not
    rewritten.

**What this milestone did and did not change:**

- **No `readme:v5` implementation occurred.** Policy D, D2 and R3 exist only as offline research adapters.
- **R3's recall losses prevented implementation.** It failed criteria 4 and 5, which were frozen before VAL-2 ran;
  neither the thresholds nor the failed results were changed.
- **Production behaviour:** torvalds/systems_cpp_01 **remains 67** in production. The 67 → 33 change in §7 is a
  hypothetical, simulated research-adapter result and is **not deployed**.
- **VAL-2 cannot be reused as an untouched holdout.** It was run once and is now seen data. VAL-1 is development
  data.
- **Kinds of evidence, kept distinct throughout:**
  - synthetic validation;
  - same-model-family separate authorship (not human-independent);
  - post-validation policy development (R3 designed on VAL-1 after D's run);
  - simulated historical score effects;
  - actual production behaviour.

## 1. Confirmed false-evidence root causes (reproduced)

- `readme:v4` extracts every non-excluded word-boundary occurrence of a README-safe alias as one MODERATE README
  item, and one item is enough for SUPPORTED (`MINIMUM_SUPPORTING_CONFIDENCE = WEAK`).
- Eleven aliases are ordinary English words: react, express, rust, ruby, java, swift, flask, torch, pandas, python
  and shell. Their homonyms ("react quickly", "free of rust", "express trains") become technology evidence.
- 8D.3's heading denylist and adjacency cues cover only a few negation and roadmap phrasings. References, history,
  plans and quoted third-party text still become evidence.
- **G22-R2 reproduced at HEAD `9552543`:**

  | Policy | False SUPPORTED, DEV / EVAL | Genuine EVAL use claims kept | Corroborated cases kept |
  |---|---|---|---|
  | current `readme:v4` | 21 / 18 | — | — |
  | D | 0 / 1 | 16/19 | 4/4 |

- **G22-R's own controls:** 21 / 20 false SUPPORTED under `readme:v4`, a separate population. The full G22-R2 report
  reproduced byte for byte.

## 2. Validation-set provenance

| Set | Cases | sha256 (LF canonical) | Frozen | Role |
|---|---|---|---|---|
| VAL-1 `validation_controls_val1.json` | 75 | `575c57c1698160d949eb879b5e4161a90af72dcf6a8cd99ed98ba5d64fb9d0ae` | 2026-11-12T04:41:36Z | validates D unchanged; then R3's **design** set |
| VAL-2 `validation_controls_val2.json` | 51 | `fadc95eb858c949620a50216ab83af443c43a1c7025e89e42c797d76a951c759` | 2026-11-12T04:41:36Z | reserve: run **once**, after R3 was frozen |

- **Author:** a separate Claude subagent instance.
  - **What it was given:** the classification task, the alias and concept list, the artifact rules (the 5% language
    floor and which manifests are parsed), the output schema and the required coverage.
  - **What it never saw:** Policy D's rules, collocates, non-use frames, code, tests or results. It had no repository
    access.
  - **Tool use:** two Writes, plus one disclosed Edit that removed a JSON trailing comma. Nothing was read, searched
    or run.
- **Not human-independent.** The author is the same model family as the policy author and may share its blind spots.
- **Pre-freeze checks:**
  - schema validation;
  - a plain registry alias text scan for label completeness (0 unlabelled mentions, 0 labels without a mention).
  - No extractor, matcher or policy ran on either set before the freeze, and no label was edited.
- **Raw author files:** their hashes are in `author_provenance.json`.
- **Coverage:**
  - ten required near-neighbour pairs plus shell, each with technical and ordinary cases;
  - the eight named phrases, in VAL-1 only;
  - explicit and implied use; historical, future and negated use; inspiration or comparison; other-project docs;
    quoted third-party text;
  - README plus manifest, README plus language statistics, README-only use, multiple mentions, conflicting cases.
- **Freezes:** G14 portable records `{val1,val2}_hash_freeze.json`, registered in the G14 manifest at the research
  commit with their original freeze-time hashes (21 → 23).

## 3. Policy D on fresh data (unchanged; hash identical to G22-R2's design freeze)

| VAL-1 (75) | A `readme:v4` | **D** | D2 (post-hoc, unauthorized) |
|---|---|---|---|
| False SUPPORTED | 35 | **9** | 11 |
| ... of which ordinary English | 16 | **0** | 1 |
| False README evidence, ordinary class | 20 | 2 | 3 |
| Genuine README use items kept | 36/36 | **26/36** | 28/36 |
| Truly-used requirements still SUPPORTED | 36 | 31 (5 → NOT_OBSERVED) | 32 |
| Artifact-corroborated cases kept | 10/10 | 10/10 | 10/10 |

- **D's precision generalises:**
  - every ordinary-English false SUPPORTED is gone;
  - the 9 residuals are all reference, historical, future or negated ("originally written in Ruby", "moved off
    Flask", "plan to add a PyTorch backend", "does not depend on pandas", "not an Express middleware", "Think of it as
    Express", quoted third-party notes).
- **D's recall does not generalise.** EVAL kept 16/19 (84%); fresh VAL-1 keeps only 26/36 (72%). It loses the most
  canonical phrasings:
  - "A Rust library for …";
  - "Swift client for …";
  - "Rate limits for Flask apps" (plural "apps" misses the collocate "app");
  - "library for Java 17+";
  - "A micro web framework for Python";
  - "React 18 for the dashboard";
  - "A Rust implementation of …";
  - "key-value store in Rust";
  - "python plotting helper".
- **D unchanged also applies its non-use frames to every alias.** That would change non-ambiguous behaviour, which is
  not allowed (for example, "inspired by FastAPI" is removed).

## 4. Revised policy R3 and its design timeline

1. D ran unchanged on VAL-1 (04:41:55Z).
2. **R3 drafted** on the seen sets only: G22-R2 DEV/EVAL, G22-R DEV/EVAL, VAL-1 after D's run, 8c and the G22-R2
   difficult cases.
   - **Scope:** the guard touches only the 11 ambiguous aliases.
   - **Precision:** D's components are unchanged (collocates, code/heading/version/claim-of-use/list-sibling cues,
     non-use frames).
   - **Three structural recall cues** (no blanket preposition rules):
     1. the alias's own collocate, or its plural, as the head noun right after the alias ("Flask apps");
     2. a software-artifact head noun right after the alias ("Rust library", "Swift client", "Java 17 library"), or
        "<library|framework|plugin|extension|middleware|sdk|package|module|toolkit> for <alias>";
     3. a major-version token after the alias ("Java 17+", "React 18").
3. **First draft rejected during design.** A plural-tolerant collocate *window* admitted "free of rust … tools"
   (G22-R2 e37, G22-R e29). It was narrowed to cue 1 above.
4. **Final R3 on the seen sets:**
   - identical to D on G22-R2 DEV/EVAL, G22-R DEV/EVAL, 8c and the difficult cases;
   - VAL-1 (design): 33/36 use items, 9 false SUPPORTED;
   - capability and job parsing identical.
5. **Design freeze** (`policy_design_freeze.json`, 04:45:31Z) recorded the policy hashes, VAL-2's hash and seven
   **acceptance criteria declared before VAL-2 ran**:
   - false SUPPORTED ≤ 50% of `readme:v4`;
   - no new false SUPPORTED;
   - all corroborated probes stay SUPPORTED;
   - ≥ 85% of `readme:v4`'s genuine README use items, and at least as many as D;
   - ≥ 90% of `readme:v4`'s true SUPPORTED probes;
   - ≤ 1 ordinary-English false SUPPORTED;
   - non-ambiguous items unchanged;
   - **if any fails: no `readme:v5`.**

## 5. Held-out VAL-2 (run once) and the decision gate

| VAL-2 (51) | A `readme:v4` | D (unseen) | D2 (post-hoc) | **R3 (held out)** |
|---|---|---|---|---|
| False SUPPORTED | 24 | 7 | 8 | **8** |
| ... ordinary English | 13 | 0 | 0 | **0** |
| Genuine README use items kept | 23/23 | 17/23 | 19/23 | **18/23 (78%)** |
| True SUPPORTED probes | 24 | 20 | 21 | **21 (87.5%)** |
| Corroborated cases kept | 6/6 | 6/6 | 6/6 | **6/6** |
| New false SUPPORTED vs `readme:v4` | — | 0 | 0 | **0** |
| Non-ambiguous README items changed | — | 0 | 0 | **0** |

| Frozen criterion | R3 on VAL-2 | D on VAL-2 | D on VAL-1 |
|---|---|---|---|
| 1. False SUPPORTED reduction | pass (24 → 8) | pass | pass |
| 2. No new false SUPPORTED | pass | pass | pass |
| 3. Corroborated preserved | pass | pass | pass |
| 4. Genuine README use items ≥ 85% | **fail (78%)** | **fail (74%)** | **fail (72%)** |
| 5. Requirement recall ≥ 90% | **fail (87.5%)** | **fail (83%)** | **fail (86%)** |
| 6. Ordinary false SUPPORTED ≤ 1 | pass (0) | pass | pass |
| 7. Non-ambiguous unchanged | pass | pass | n/a (D changes them) |

- **Decision: `readme:v5` is not implemented.** This follows the rule frozen before the run and the brief's gate
  ("If D's recall loss is unacceptable, DO NOT implement it unchanged").
- VAL-2 has now been seen. **Any further revision needs a new fresh set.** R3 must not be tuned on VAL-2 and then
  called validated.
- **R3's VAL-2 misses:**
  - "One-line Swift API";
  - "Pure Python, no third-party dependencies";
  - "Streaming CSV reader, in Swift";
  - two README items whose probes stayed SUPPORTED through other evidence ("a small React front end", "feature
    preparation with pandas").
- **New trap exposed by R3's head-noun cue:** "Like the Rust compiler, it …" is a reference that R3 admits.

## 6. Named phrases (VAL-1, author's labels)

| Phrase | Author label | A | D | D2 | R3 |
|---|---|---|---|---|---|
| image diffing in Rust | use | SUPPORTED | SUPPORTED* | SUPPORTED | SUPPORTED* |
| python plotting helper | use | SUPPORTED | **missed** | missed | **missed** |
| Analysis with pandas | use | SUPPORTED | SUPPORTED | SUPPORTED | SUPPORTED |
| trained with torch | use | SUPPORTED | SUPPORTED | SUPPORTED | SUPPORTED |
| store in Rust | use | SUPPORTED | **missed** | SUPPORTED | **missed** |
| API design borrowed from Express | reference | false SUPPORTED | false SUPPORTED | false SUPPORTED | false SUPPORTED |
| free of rust | ordinary | false SUPPORTED | correct | correct | correct |
| local and express trains | ordinary | false SUPPORTED | correct | correct | correct |

\* The "image diffing in Rust" README item itself is removed under D and R3, but other evidence in the same case still
carries the requirement. In this set's contexts, "Analysis with pandas" and "trained with torch" keep their README
items under every policy because nearby collocates are present. In G22-R2/G22-R's shorter contexts D lost them. Full
per-item detail is in the report.

## 7. Historical impact (simulated; nothing deployed)

- **Frozen 8c:** D and R3 make identical removals:
  - 6 README items: 5 references (libgit2's list of other projects' Java, Python, Ruby, Rust and Swift bindings) and
    1 genuine use (Gifski's "need to have Rust installed");
  - 4 torvalds concepts are lost entirely;
  - **simulated** torvalds/systems_cpp_01 changes from 67 → 33 (numerator 2 → 1, denominator 3) in both matrix
    versions, with 2 pairs changing status;
  - 0 scores become undefined.
- **These figures are not deployed.** Production remains `readme:v4`, so the actual torvalds score is still 67. The
  33 is what the research adapter would produce. It is not assumed, and it is not gold.
- **G22-R controls, README side:**

  | | False SUPPORTED, DEV / EVAL | Recall, DEV / EVAL |
  |---|---|---|
  | `readme:v4` | 21 / 20 | 14/14, 12/12 |
  | D | 2 / 3 | 12/14, 11/12 |
  | R3 | 2 / 3 | 12/14, 11/12 |

- **G22-R2 controls:**
  - R3 matches D exactly: false SUPPORTED 0 / 1, EVAL use claims 16/19, corroborated 4/4.
- **Job side:** README policies never touch job parsing. It was verified identical on every G22 corpus, and the 62
  private postings show 0 changes (`private_readme_guard_aggregates.json`, integer counts only).
  - This covers G22-Q, G22, G21, G20, G17, G16, G15 and M10/M10E.
  - M10 has no repositories, so README policies cannot reach it.

## 8. Capability contract (Phase 9)

- All 64 README-safe aliases of all registered concepts are still extracted, under A, D and R3, from a valid
  technical context ("This project is built with <alias>.").
- G19 capability is identical for all 39 concepts.
- No concept loses its only genuine pathway.

## 9. Remaining ambiguous cases

- **Ordinary English:** solved on both fresh sets by per-alias collocates (0 false SUPPORTED). A capitalised homonym
  next to a generic collocate ("A Java coffee app") is still unresolved.
- **Non-use framing:**
  - closed phrase lists do not generalise ("began life as a Ruby app", "No Flask or other web framework", "without
    React", "modelled on pandas", a cheat sheet *about* PyTorch, quoted release notes);
  - these are now the dominant residual false SUPPORTED, but they are **not new**: every one is also false under
    `readme:v4`.
- **Genuine use without a technical cue:**
  - "Pure Python";
  - "One-line Swift API";
  - "in Swift," as a parenthetical;
  - "python plotting helper";
  - "key-value store in Rust".

  These are open-ended. Each new cue either recovers a few of them or admits a trap ("in Java" as a place under D2;
  "Like the Rust compiler" under R3).

## 10. Why README evidence still does not prove competence

A README use claim, even one corroborated by a manifest, shows that a repository uses a technology. It does not show
that the candidate is proficient in it. GitScore measures GitHub evidence only. The guard changes which README
occurrences count as evidence; it would not change what evidence means.

## 11. Recommendation and future work

1. Keep `readme:v4`. Do not implement D, D2 or R3.
2. **If the precision problem is pursued, two directions are untested and would each need design on the seen sets
   plus a NEW fresh set:**
   - **(a) An inverse guard:** default-accept, and reject an ambiguous occurrence only on a positive *homonym-sense*
     cue (trains, corrosion, gemstone, island, coffee, snake, …). This targets the ordinary-English class, which D
     solves but at a recall cost.
   - **(b) Explanation-level labelling:** keep the extraction, but mark README-only, uncorroborated, ambiguous-alias
     evidence as weaker in explanations. This is an evidence-schema and API review, with no MatchStatus change.
3. **Validation should be human-authored,** or at least come from a different model family, before any production
   commit.
4. **Evidence-confidence work** (README mention kind: use claim / mention / corroborated) stays a separate design
   review.

## 12. Rollback

Nothing to roll back: production is unchanged. The research files are additive and can be deleted without effect on
`src/`.

## 13. Files (research only; committed at the research commit)

- **Validation sets and freezes:**
  - `evaluation/m11g22r3/validation_controls_{val1,val2}.json`
  - `evaluation/m11g22r3/{val1,val2}_hash_freeze.json`
  - `evaluation/m11g22r3/author_provenance.json`
  - `evaluation/m11g22r3/policy_design_freeze.json`
- **Reports:**
  - `evaluation/m11g22r3/readme_guard_report.json` (deterministic)
  - `evaluation/m11g22r3/private_readme_guard_aggregates.json` (integer counts only)
- **Scripts:**
  - `scripts/evaluate_m11g22r3_readme_guard.py`
  - `scripts/evaluation_lib/m11g22r3_build_controls.py`
  - `scripts/evaluation_lib/m11g22r3_policies.py`
- **Tests:** `tests/test_m11g22r3_readme_context_guard.py` (21). Its registration test pins both states: at the
  parent commit `9552543` the manifest had 21 entries and neither G22-R3 set; now both are registered with their
  freeze-time hashes and verify. No other test needed a change, because every other manifest-size assertion is
  already pinned to a historical commit.
- **Manifest:** `evaluation/integrity/canonical_hash_manifest.json` (+2 entries).
- **Docs:**
  - this file;
  - `docs/CHANGELOG_DEV.md`;
  - limitation notes in `docs/ARCHITECTURE.md` §27.5 and `docs/PIPELINE.md`.
