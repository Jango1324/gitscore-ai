# Milestone 11-G22-R2 — README evidence context and confidence (research)

**Status:** research, evaluation and design only.

- **No production, registry, matcher or scoring change:**
  - parser `job_description_parser:v15`;
  - scoring `github_evidence_alignment:v2`;
  - matcher `requirement_matcher:v1`;
  - README extractor `readme:v4`;
  - registry version 4.
- **No LLM call.**
- **Committed as a research-only commit** ("test: evaluate README evidence context precision") after authorization. The
  DEV and EVAL freezes are registered in the G14 manifest at that commit with their original freeze-time hashes
  (19 → 21 entries; the previous 19 are unchanged field for field). Their freeze records keep their freeze-time note
  ("NOT registered … pending authorization"); they are not rewritten.
- **Accepted interpretation** (see §13): policy D is the **recommended baseline, not an approved production fix**; D2 is
  **not authorized**; fresh, preferably independently authored validation is required before any `readme:v5`
  production commit is approved.

**Evidence sources and what can be claimed from them:**

| Source | Status |
|---|---|
| DEV / EVAL controls (`evaluation/m11g22r2/`) | Synthetic and written by the same researcher who designed the policies, so **not independent validation**. EVAL is only weakly held out. |
| Frozen 8c fixtures | Real public README text. The review of what policies remove is **post-hoc** and is not gold. Score changes on them are **simulated historical impact** under research adapters, not deployed behaviour. |

**Five result populations, kept separate throughout:**

1. **Original G22-R results** on G22-R's frozen controls (current false SUPPORTED 21 / 20), reproduced in §1.
2. **New G22-R2 results** on the new DEV/EVAL controls (current false SUPPORTED 21 / 18), §4. The two control
   populations have different baselines and must not be pooled or compared count for count.
3. **Policy D's pre-EVAL simulation**: designed on DEV, frozen at 21:57:07Z, then run once on EVAL.
4. **D2's post-EVAL refinement**: written after seeing EVAL's results; not validated and not authorized.
5. **Historical real-README observations** (frozen 8c, §6): judged by the researcher after inspection, not frozen gold.

## 1. Baseline (verified)

- HEAD = `origin/main` = `13f79fe04ec7d962e3e94ddd0a1003b8dab999f8`.
- Parser v15, scoring v2, matcher v1, `readme:v4`, registry 4.
- 19/19 G14 freezes verify; the 18 private/untracked M11 entries are preserved.
- **G22-R reproduces exactly:**

  | | DEV | EVAL |
  |---|---|---|
  | Current false SUPPORTED | 21 | 20 |
  | G22-R policy D | 5 | 7 |
  | G22-R study R | 1 (recall 9/14) | 1 (recall 8/12) |
  | Genuine README recall (current) | 14/14 | 12/12 |
  | False README evidence, raw / adjusted | 18 / 17 (d22) | 16 / 16 |

## 2. What a README mention means in `readme:v4`

| Category | Does `readme:v4` distinguish it? |
|---|---|
| A. A word occurrence of a README-safe alias | **Scanned.** Case-insensitive word-boundary match via the shared `alias_pattern`. |
| B. A technical concept reference | **No.** Only 8D.3's section-heading denylist and adjacency negation/roadmap cues are applied. |
| C. A self-reported project-use claim | **No.** |
| D. A technically corroborated claim | **No.** Corroboration exists only implicitly: other extractors may add items for the same concept. |
| E. Evidence sufficient for SUPPORTED | **Yes.** One MODERATE README item meets `MINIMUM_SUPPORTING_CONFIDENCE = WEAK`. |

So `readme:v4` maps **A directly to E**.

- **Earliest irreversible point:** `evidence_from_readme` emits `Evidence(concept_id, MODERATE, raw_observation=snippet)`.
  After that, `build_concept_summaries` pools items per concept, and `has_sufficient_evidence` sees only "at least one
  item at WEAK or above". Nothing downstream can tell a word from a project-use claim.
- **Every README item is MODERATE**, whatever its kind. On the real 8c fixtures (126 README items):
  - only 39 carry an explicit claim-of-use frame;
  - 47 are corroborated by an artifact in the same repository and 32 by another repository;
  - **32 have neither a use frame nor any corroboration.**
- **Cross-repository aggregation:** README items are deduplicated per concept per repository. Repeated ordinary
  mentions in several repositories still produce one SUPPORTED requirement.

## 3. New controls (frozen; G14 portable; registered at the research commit)

| Set | Controls | sha256 (LF canonical) | Frozen |
|---|---|---|---|
| DEV `readme_context_controls_dev.json` | 44 | `18c21a505a472182b2d3fd5bc23d29957a1806834108ed58e7aef19d7307b12b` | 2026-11-11T21:54:40Z |
| EVAL `readme_context_controls_eval.json` | 40 | `3a59672a55745927ab945e671f9b867854bb81f08c418271e9669136893bfa0e` | 2026-11-11T21:54:40Z |

- **Policy-design freeze** (`policy_design_freeze.json`, 21:57:07Z): taken after the DEV design and **before EVAL was
  ever run**. Its one DEV-time design change is recorded there.
- **Labels** (per mentioned concept): ordinary, reference, use, historical, future, negated, ambiguous.
- **SUPPORTED truth:** `used` is the truth; `uncertain` covers historical or conflicting cases and is excluded from
  both true and false SUPPORTED counts.
- **Coverage:**
  - every ordinary, genuine and ambiguous case named in the brief;
  - all six corroboration shapes (manifest, language statistics, Docker, README-only, multiple repositories,
    conflicting);
  - quoted text, negation, future and historical use;
  - near-neighbour pairs: "free of rust" / "free of unsafe code", "local and express" / "Node and Express",
    "Java coffee" / "Java and Kotlin", "a ruby ring" / "Ruby on Rails".
- **Not independent validation:** EVAL's wording was written by the policy author, so EVAL is only weakly held out.

## 4. Policies compared (offline adapters, `scripts/evaluation_lib/m11g22r2_policies.py`)

Each policy wraps `readme.is_non_implementation_mention`, the existing per-occurrence filter. The alias table and the
extractor's fall-through behaviour are unchanged.

| Policy | Rule |
|---|---|
| **A** | current `readme:v4` |
| **Dref** | G22-R policy D, README side only |
| **B** | G22-R D's cues with the `of`/`and`/`or` lead-ins removed; casing still counts |
| **C** | per-alias **technical collocates** for the 11 README-ambiguous aliases (e.g. ruby: rails, gem, app, script; java: jvm, spring, service, android; react: component, hooks, ui, vite), plus code, heading, version, claim-of-use frame or registry list sibling; casing **never** counts |
| **D** | C + explicit **non-use frames** for every alias ("inspired by", "migrating … to", "considering", "previously used", "… can be generated"), written from DEV phrasings only |
| **E** | D + README evidence without corroboration counts only with an explicit claim-of-use frame. This **changes when evidence is sufficient** and would need a matcher-contract review. |
| **F** | ambiguous aliases need an explicit use frame, code, heading or version |
| *D2 (post-hoc)* | D + `with`/`in`/`using`/`on`/`via` lead-ins. Written after EVAL and **not validated**. |

**Results.** "Use kept" = explicit or plain-reading use claims that keep their README evidence. "Ordinary rejected" =
ordinary-language occurrences correctly not extracted.

| Policy | DEV false SUPPORTED | DEV use kept | DEV ordinary rejected | EVAL false SUPPORTED | EVAL use kept | EVAL ordinary rejected | EVAL true SUPPORTED / missed |
|---|---|---|---|---|---|---|---|
| A | 21 | 20/20 | 0/18 | 18 | 19/19 | 0/15 | 19 / 0 |
| Dref | 8 | 18/20 | 13/18 | 6 | 14/19 | 12/15 | 14 / 5 |
| B | 5 | 18/20 | 16/18 | 6 | 14/19 | 13/15 | 14 / 5 |
| C | 1 | 20/20 | 18/18 | 1 | 16/19 | 15/15 | 17 / 2 |
| **D** | **0** | **20/20** | **18/18** | **1** | **16/19** | **15/15** | **17 / 2** |
| E | 0 | 7/20 | 18/18 | 0 | 5/19 | 15/15 | 7 / 12 |
| F | 0 | 9/20 | 18/18 | 0 | 5/19 | 15/15 | 7 / 12 |
| *D2 (post-hoc)* | *0* | *20/20* | *18/18* | *1* | *18/19* | *15/15* | *18 / 1* |

**Reading the table:**

- **Corroborated evidence is kept by every policy** (4/4 SUPPORTED on both sets): manifest, language and Docker
  evidence never depend on README text.
- **D's non-use frames add nothing on EVAL.** EVAL's phrasings ("borrowed from", "ported … later", "are planned",
  "evaluating … versus", "originally written in") are not in the DEV lexicon, so C and D are identical there. **The
  per-alias collocates do the work.** A closed non-use lexicon will not generalise.
- **D's EVAL residuals:**
  - false SUPPORTED: e25 "API design borrowed from Express" (reference, and 'api' is an Express collocate);
  - missed: e15 "image diffing in Rust" and e23 "python plotting helper";
  - e32 "Analysis with pandas": the README item is lost, but the concept is still SUPPORTED through the manifest.
- **The three genuine EVAL use claims D loses (16/19 kept):**
  1. e15 "image diffing **in Rust**" (prepositional; requirement becomes NOT_OBSERVED);
  2. e23 "python plotting helper" (no collocate; requirement becomes NOT_OBSERVED);
  3. e32 "Analysis **with pandas**" (prepositional; README item lost, requirement still SUPPORTED via the manifest).

  D therefore **still misses genuine README evidence**, mostly prepositional use without a technical collocate.
- **E and F** reach 0 false SUPPORTED only by discarding roughly three quarters of genuine README use claims. Do not
  adopt.
- **G22-R frozen controls** (README side only, so G22-R's job-side false concepts remain):

  | Policy | False SUPPORTED, DEV / EVAL | Genuine README recall, DEV / EVAL |
  |---|---|---|
  | A | 21 / 20 | 14/14, 12/12 |
  | D | 2 / 3 | **12/14, 11/12** |
  | D2 (post-hoc) | 2 / 3 | 14/14, 12/12 |

  D loses "analysis … with pandas", "trained with torch" and "key-value store in Rust".

## 5. Difficult cases (Phase 6): what local rules can and cannot do

| Case | Genuine? | A | D | D2 (post-hoc) | Verdict |
|---|---|---|---|---|---|
| "free of rust" | no | extracts | rejects | rejects | **solved** (no Rust collocate; `of` is not a cue) |
| "free of unsafe code" (Rust) | yes | ✓ | ✓ | ✓ | kept (`unsafe` collocate / "written in") |
| "local and express trains" | no | extracts | rejects | rejects | **solved** |
| capitalised Ruby / Java in ordinary prose | no | extracts | rejects | rejects | **solved when no collocate is present** |
| "Ruby, our app's mascot"; "A Java coffee app" | no | extracts | **extracts** | **extracts** | **unresolved**: a generic collocate (`app`) next to a capitalised homonym |
| "python visualizer" | yes | ✓ | ✓ | ✓ | kept (collocate added on DEV) |
| "python plotting helper" | yes | ✓ | ✗ | ✗ | **unresolved**: collocate lists are open-ended |
| "inspired by React" | no | extracts | rejects | rejects | solved (DEV frame) |
| "API design borrowed from Express" | no | extracts | **extracts** | **extracts** | **unresolved**: unseen reference phrasing |
| "Rust bindings can be generated" / "… are planned" | no | extracts | rejects / rejects | rejects | solved (frame / no collocate) |
| "image diffing in Rust", "trained with torch" | yes | ✓ | ✗ | ✓ | D loses them; D2 recovers them, but… |
| "Photos taken in Java last summer" | no | extracts | rejects | **extracts** | **…D2 accepts this**: "in Rust" and "in Java" are lexically identical |
| G21-n10 "React knowledge is welcome …" | yes (job) | — | — | — | **job side**: G22 B drops it ("knowledge" is not a head noun); README policies cannot reach it (verified) |

**Conclusion:** local deterministic context removes every ordinary-language false match in both control sets and the
real libgit2 reference list. It **cannot reliably** separate:

- a capitalised homonym from a technology when a generic collocate is nearby;
- a prepositional "in X" use from an "in X" place;
- unseen reference phrasing from use.

These remain documented uncertainty, not solved cases.

## 6. Real README impact (frozen 8c fixtures, 126 README items)

| Policy | Items removed | Post-hoc review: reference / use | Concepts lost entirely | 8c v1 & v1.1 score changes | Undefined |
|---|---|---|---|---|---|
| Dref | 1 | 0 / 1 | 0 | 0 | 0 |
| B | 4 | 3 / 1 | 3 | torvalds/systems_cpp_01 67 → 33 | 0 |
| **C, D, D2** | **6** | **5 / 1** | **4** (torvalds Java, Ruby, Rust, Swift) | **torvalds/systems_cpp_01 67 → 33** | 0 |
| F | 10 | 7 / 3 | 6 (incl. karpathy React) | + karpathy/frontend_01 60 → 40 | 0 |
| E | 34 | 6 / 2 (26 unreviewed) | 15 | 4 pairs per matrix version (e.g. sindresorhus/frontend 80 → 40) | 0 |

- **Status of these numbers:** every row is a **simulated** historical impact, computed by running research adapters
  over frozen fixtures. None of it is deployed behaviour (production remains `readme:v4`), and the reference/use review
  was made by the researcher after inspecting the removed items, so it is **not independent gold**.
- **Real false evidence `readme:v4` produces today.** torvalds/libgit2's README lists *other projects'* language
  bindings: Rugged (Ruby), git2-rs (Rust), SwiftGit2, Jagged (Java), pygit2 (Python). `readme:v4` turns that list into
  Java, Ruby, Rust and Swift evidence for the candidate.
  - C, D and D2 remove all five. Four of those concepts had **no other evidence**.
  - The single simulated score change (67 → 33, numerator 2 → 1, same denominator) would therefore be a correction
    under GitScore's own evidence rules. The kernel's Rust share is 0.45% of bytes, below the language extractor's 5% floor.
- **Genuine loss under C/D/D2:** one occurrence ("To build the app … you need to have Rust installed", Gifski). Rust
  stays evidenced for that candidate elsewhere.
- **A reference that slips past every policy except F:** sindresorhus/file-type's "Java class file", a file format,
  is kept by C and D through the `class` collocate.

## 7. Registry and capability contract (Phase 7)

- **Where metadata belongs:** alias + text source. The README collocate table is per alias and README-specific; the
  job side needs different cues (G22 B and G21-n10). Concept-level metadata is too coarse: "PyTorch" is unambiguous,
  "torch" is not.
- **Smallest home:** a README-context table inside `evidence/extraction/readme_context.py`, keyed by registry alias
  strings, plus a test that every key is a registered README-safe alias (to prevent drift). Under that design:
  - **no registry field and no registry version change** are needed;
  - `readme_safe_aliases()` stays unchanged.
- **A registry field** (`ambiguous_aliases` with source tags) is the alternative. It is cleaner if the job side later
  shares the data, but it needs `CONCEPT_REGISTRY_VERSION` 4 → 5 and a models change. Defer it to the job-side
  milestone.
- **G19 capability is unaffected by occurrence rules.** It was verified identical for all 39 concepts under every
  policy. README-safe aliases stay unchanged, so the `README_MENTION` pathway still exists and no concept becomes
  unassessable. Capability tests need no update. A concept harder to detect in ambiguous prose keeps every other
  pathway.
- **Job parsing is unaffected** (verified identical on every G22 corpus, under every policy).

## 8. Evidence confidence and product semantics (Phase 8)

- **Three distinct things**, which `readme:v4` conflates:
  - an **ordinary mention**: the alias string appears (a word, a reference, a plan, a comparison);
  - a **project-use claim**: the README states the project uses the technology (self-reported);
  - **corroboration**: an artifact (manifest, language bytes, Docker file) independently shows the technology.
- **A README claim is not proof of professional competence.** Even a corroborated use claim is evidence that a
  repository uses a technology, not that the candidate is proficient in it. GitScore measures GitHub evidence only.
- MODERATE is applied identically to:
  - "Stack: React + Vite" (an explicit use claim);
  - "inspired by React" (a reference);
  - "react quickly" (not the technology at all).

  It therefore does **not** communicate the source's strength.
- **Recommended later, as a separate milestone:** an internal evidence attribute, e.g. `readme_mention_kind` with values
  use_claim / mention / corroborated, surfaced only in explanations. MatchStatus stays unchanged.
  - That is an **evidence-schema change** (`EVIDENCE_SCHEMA_VERSION` review) and an API/explanation review. No public
    field is added now.
- **E-style interpretation** (README-only evidence needs an explicit use claim or corroboration) changes when evidence
  is sufficient for SUPPORTED. It would need a **matcher-contract review**; if score meaning changes, a
  **scoring-version review** too. Not proposed.

## 9. Historical compatibility (Phase 9)

- **G22-R frozen controls:** see §4.
- **Job side unaffected under every README policy:** G22-Q, G22, G21, G20, G17, G16, G15, M10, M10E and the private
  postings. Verified, not assumed: job parsing is identical on all G22 corpora, and the 62 private postings show
  0 changes.
- **G19 capability:** identical.
- **Frozen 8c:** see §6.
- **M10:** no repositories, so README policies cannot reach it.
- **Existing tests under each extractor policy:** 167 extractor, pipeline, capability, 8c-harness and end-to-end tests
  were run.
  - Every failure (8 per policy) is in G22-R's own research test file, which deliberately pins today's `readme:v4`
    false-evidence behaviour. A future `readme:v5` must version-branch them.
  - All 159 other tests pass under every policy.
- **M10E-g3:** untouched; the job-side defect is still open.

## 10. Recommendation (smallest future `readme:v5`)

1. **Source files:**
   - `src/gitscore/evidence/extraction/readme_context.py`: the per-alias collocate table and the non-use frames;
   - `src/gitscore/evidence/extraction/readme.py`: `EXTRACTOR_VERSION` `readme:v4` → `readme:v5`.
2. **Alias metadata:** yes, as a README-specific table keyed by registry aliases (the 11 reviewed aliases).
3. **Registry version:** no change (v4), provided the table stays in the extractor module.
4. **Rules supported by evaluation:**
   - D's per-alias collocates (casing never counts; no `of`/`and` cues);
   - explicit non-use frames as a bounded supplement, explicitly not relied on for coverage.
   - Whether to add D2's prepositional lead-ins is an **open decision**. They recover genuine "in Rust"/"with torch"
     uses but admit "in Java (place)".
5. **Must stay unresolved, and be documented:**
   - capitalised homonyms next to generic collocates;
   - unseen reference phrasing;
   - lowercase genuine mentions with no collocate ("python plotting helper").
6. **Regression tests:**
   - both frozen R2 sets and the G22-R sets;
   - near-neighbour pairs;
   - the 8c removal list (libgit2 bindings removed; the Gifski-type loss documented);
   - capability identical;
   - job parsing identical;
   - existing extractor tests;
   - version branches for G22-R's 8 `readme:v4` pins.
7. **Recall safeguards:**
   - fall-through to the next occurrence and next alias stays (8D.3 behaviour);
   - non-ambiguous aliases are untouched;
   - corroborating extractors are untouched.
8. **Versions:** extractor only (`readme:v5`). **No matcher or scoring version change.** This follows the 8D.1 / 8D.3
   precedent: extraction filters bumped only `EXTRACTOR_VERSION`.
9. **API / explanation:** none for `readme:v5`. Evidence-strength labelling is a separate, later milestone (§8).
10. **Rollback:** revert the two files. `extractor_version` on each Evidence item identifies v5-produced evidence.

Evidence **recognition** (`readme:v5`) and evidence-**strength** semantics (§8) should be **separate milestones**.

## 11. Approval questions

1. Approve `readme:v5` on policy D (per-alias README collocates + bounded non-use frames) as the implementation basis?
2. Include D2's prepositional lead-ins (recovers "in Rust"/"with torch" use; admits "in Java" as a place), or leave them
   out?
3. Keep the alias table in `readme_context.py` (no registry change), or move ambiguity metadata into the registry
   (v4 → v5) together with the job-side milestone?
4. Require a fresh, separately authored validation set (not by the policy author) before implementation?
5. Schedule evidence-strength explanation metadata (no MatchStatus change) as a later, separate milestone?
6. ~~Register the G22-R2 DEV and EVAL freezes at a research commit?~~ Approved and done at the research commit
   (19 → 21).

## 12. Files (research only; committed at the research commit)

- **Controls and freezes:**
  - `evaluation/m11g22r2/readme_context_controls_{dev,eval}.json`
  - `evaluation/m11g22r2/{dev,eval}_hash_freeze.json`
  - `evaluation/m11g22r2/policy_design_freeze.json`
- **Reports:**
  - `evaluation/m11g22r2/readme_context_report.json`
  - `evaluation/m11g22r2/private_readme_context_aggregates.json`
- **Scripts:**
  - `scripts/evaluate_m11g22r2_readme_context.py`
  - `scripts/evaluation_lib/m11g22r2_{build_controls,policies,posthoc,harness,pytest_policy}.py`
- **Tests:**
  - `tests/test_m11g22r2_readme_evidence_context.py` (21).
  - `tests/test_m11g22r_ambiguous_alias_evidence.py`: G22-R's hard-coded "manifest has exactly 19 entries" assertion
    became false once these freezes were registered. It now pins the historical fact exactly instead: the manifest at
    G22-R's commit `13f79fe` had 19 entries, and every one is still present field for field. Its hash and field
    comparisons for the G22-R entries are unchanged.
- **Docs:** this file and `docs/CHANGELOG_DEV.md`.
- **Manifest:** `evaluation/integrity/canonical_hash_manifest.json` (+2 entries).

## 13. Accepted interpretation (research acceptance)

- **Policy D is the recommended baseline, not an approved production fix.** `readme:v5` is not implemented.
- **D still misses genuine README evidence** (§4: e15, e23, e32 on EVAL; "with pandas", "trained with torch", "store in
  Rust" on the G22-R controls).
- **D2's blanket preposition cues (`with`/`in`/`using`/`on`/`via`) are not authorized.** They were written after EVAL
  and admit "in Java" as a place.
- **Alias-context rules may live in `readme_context.py` without changing registry v4.** Registry aliases,
  `readme_safe_aliases()` and G19 capability must remain unchanged.
- **Ordinary mentions, project-use claims and corroboration are distinct** (§8), and **a README claim is not proof of
  professional competence.**
- **Matcher `requirement_matcher:v1` and scoring `github_evidence_alignment:v2` remain unchanged.** Any future
  evidence-confidence or sufficiency change requires a **separate design review**.
- **Fresh, preferably independently authored validation is required before a production commit is approved.** The
  G22-R2 controls were authored by the policy designer and are not independent.
