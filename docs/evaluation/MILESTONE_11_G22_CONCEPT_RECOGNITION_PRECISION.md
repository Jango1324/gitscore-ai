# Milestone 11-G22: Technical Concept Recognition Precision (research)

**Status:** research, evaluation and design only.

- No production code changed. The parser stays `job_description_parser:v14`, scoring stays `github_evidence_alignment:v2`, and the matcher and evidence extractors are unchanged.
- Committed as a research-only commit ("test: evaluate technical concept recognition precision") after authorization. No Q, A, B, C2 or G option is implemented.
- The DEV and EVAL freezes are registered in the G14 manifest at that commit, using their original pre-evaluation hashes (15 → 17 entries). Their freeze records keep their freeze-time note ("NOT registered … pending authorization"), which was true when they were written.
- No LLM is called anywhere.

**Honesty notes:**

- Every G22 control is author-created synthetic text, written by the same researcher who designed the candidate policies, so **none of it is independent validation**.
- EVAL was authored separately from DEV and frozen before any parser run. Its texts were nevertheless known to the policy designer, so it counts as **weakly held out** at best.
- Post-hoc variants are labelled as such everywhere.
- Private postings are reported as integer counts only.

**Artifacts:**

| Kind | Files |
|---|---|
| Controls | `evaluation/m11g22/concept_controls_{dev,eval}.json` + `{dev,eval}_hash_freeze.json` |
| Policy freeze | `evaluation/m11g22/policy_design_freeze.json` |
| Report | `evaluation/m11g22/concept_precision_report.json` (public, reproducible byte-identically) |
| Private | `evaluation/m11g22/private_concept_aggregates.json` (counts only) |
| Code | `scripts/evaluate_m11g22_concept_precision.py`, `scripts/evaluation_lib/m11g22_{build_controls,policies,concepts,posthoc}.py` |
| Tests | `tests/test_m11g22_concept_recognition_research.py` (25 tests) |

## 0. Baseline (verified)

| Check | Result |
|---|---|
| HEAD | `de2a906a0d98c3b2c19a8f5a49299f147468ade2` on `main`, equal to `origin/main` (0 ahead, 0 behind) |
| Versions | `job_description_parser:v14`, `github_evidence_alignment:v2` |
| Backend | 2241 passed, 13 skipped, 18 xfailed |
| Frontend | 53 passed |
| G14 manifest | 15 entries |
| Working tree | 0 tracked modifications; the 18 private untracked M11 entries are preserved |

## 1. Pipeline trace (Phase 1)

How a text span becomes each outcome, with live line numbers at `de2a906`:

| Outcome | Where | Mechanism |
|---|---|---|
| Claim | `segmentation.py:683` | A line is a claim if it has a requirement signal **or any concept mention**. The same unguarded alias scan admits "react quickly" lines. |
| Admission | `parser.py:304`, `qualification_intent.py` | G21 decision. `scoped_text` blanks negated units. `qualification_intent.py:165` also scans concepts (technology-as-subject frame). |
| Alternative group | `parser.py:349` → `alternatives.py:502` | OR / any-of claims. `_resolve_segment` (`:253`) uses the alias scan, then `resolve_concept` on the cleaned fragment (`:265`; this **does** match prose-unsafe "go"), then mints `unresolved:<Shaped Term>` (`:279`, `:370`). `len(ids) < 2` gives `unsafe` (`:391`), even when every segment named the *same* concept. G17 `is_structurally_mixed` is at `:473`. |
| Registered concept | `parser.py:391` → `concepts.py:198` | `find_concept_mentions`: boundary-only, case-insensitive match of every `readme_safe_aliases()` alias. **No usage or part-of-speech check.** "go", "next", "js", "ts" and "c" are excluded via `readme_unsafe_aliases` (`registry.py:158`); "react", "express", "swift", "rust", "shell", "torch" and "ruby" are not. |
| Unresolved concept | `parser.py:436` → `concepts.py:296` / `_consider_fragment` `:394` | Comma-list fragments next to a confirmed mention. M11-A1's shape gate (`:414`) applies to multi-word fragments only, so **every single-word fragment is minted**: "curiosity", "teamwork", "Alternatively", "context", "Go". |
| Placeholder | `parser.py:484` | `unresolved_requirement` (concept `None`) when nothing else was produced and a lead-in, OR or enumeration signal exists ("Experience with Go."). |
| Scoreable / excluded | `assessment/models.py:87` | v2 eligibility. Registry concepts are eligible. `unresolved:` rows are excluded (`unresolved_technology`). Placeholders are `NOT_ASSESSABLE`. |
| SUPPORTED / not observed | `matching/engine.py:108-110` | Pure concept-id lookup in the candidate profile. The matcher never sees the surface text. |

**Earliest irreversible point:** `_requirements_from_claim` builds the `JobRequirement` with `concept_id=mention.concept_id` (`parser.py:429`). From then on the identity is only an id. The matcher, eligibility and scoring cannot tell "react quickly" from "React". Every wrong identity G22 measured is created at **one of three recognition sites**: `find_concept_mentions`, `_consider_fragment` and `_classify_segment_list`.

**Parser recognition versus evidence capability:**

- Every G22 failure is a **parser recognition** error. The evidence side behaves exactly as specified for the id it is given.
- A false `framework.react` row is SUPPORTED by genuine React evidence. That is a correct match on a wrong requirement.
- A fabricated `unresolved:curiosity` is excluded by v2 because no detector can check it. This is correct capability classification, and it hides the parser error from the score.
- One adjacent finding outside G22 scope: README evidence extraction (`evidence/extraction/readme.py`) uses the same `readme_safe_aliases` table, so ordinary-English README prose can in principle yield false evidence too. Extractors were not changed and not measured here.

## 2. Reproductions with live v14 (Phase 2)

All cases below come from the real parser v14, matcher and scoring v2; the full per-case records are in `phase2_reproductions` in the report.

- **"Adversarial candidate" score:** the score for a candidate who has evidence for every registry concept the parser produced.
- **Spans:** every row keeps its exact source span and `original_text`. 0 span errors anywhere.

| Case | Admit | Aliases → rows (necessity) | Status / eligibility | Score effect | Earliest incorrect stage |
|---|---|---|---|---|---|
| "Ability to **react** quickly…" | yes (weak attribute) | react → `framework.react` (REQ) | counted; SUPPORTED with React evidence | **0 → 100** for a React developer | `find_concept_mentions` (no usage check) |
| "Experience with React." | yes | `framework.react` (REQ) | counted | correct | — |
| "Ability to **express** complex ideas…" | yes | `framework.express` (REQ) | counted, SUPPORTED | 0 → 100 | `find_concept_mentions` |
| "…REST APIs with Express." | yes | `framework.express` | counted | correct | — |
| "**Swift** decision-making under pressure." | yes (neutral) | `language.swift` | counted, SUPPORTED | 0 → 100 | `find_concept_mentions` (claim-initial capital) |
| "…iOS apps in Swift." | yes | `language.swift` | counted | correct | — |
| "…SQL, attention to detail, and **curiosity**." | yes | SQL + `unresolved:curiosity` | curiosity excluded (`unresolved_technology`) | none (diagnostic noise) | `_consider_fragment` single-word exemption |
| "…AWS is required. **Alternatively**, Docker…" (G16-058) | yes, yes | AWS; Docker + `unresolved:alternatively` | excluded | none | `_consider_fragment` (capitalised discourse adverb) |
| "Experience with **Go**." | yes | none → `unresolved_requirement` | `NOT_ASSESSABLE` | genuine Go never scored | registry marks "go" prose-unsafe |
| "A go-getter… to go the extra mile." | yes | none → UnparsedClaim | — | correct | — |
| "Experience with **Go or Golang**." | yes | `alternative_requirement` placeholder | `NOT_ASSESSABLE` | genuine requirement unscored | `_classify_segment_list`: one concept twice → `unsafe` |
| "Experience with **Go**, Docker, and Kubernetes." | yes | Docker, Kubernetes + **`unresolved:go`** | Go excluded | Go unscored (wrong identity) | `_consider_fragment` mints an unrecognised registry name |
| "About us: our platform is built with React and Python." | **no** (G21 inline prefix) | — | UnparsedClaim | correct | — |
| "Our platform is built with React, Python, and PostgreSQL." | **no** (G21 employer) | — | UnparsedClaim | correct | — |
| "Proficiency in React, Redux, and TypeScript." | yes | React, TypeScript, `unresolved:redux` | correct | correct | — |
| Bare list "Python, Docker, Kubernetes" | yes | 3 rows | counted | correct | — |
| "Python, **teamwork**, and Docker." | yes | + `unresolved:teamwork` (+ soft_skill row) | excluded | none | `_consider_fragment` |
| "Solid React experience, including hooks and **context**." | yes | React + `unresolved:context` | excluded | none | `_consider_fragment` (lowercase common noun) |
| **G16-018** "Either Python or Go and either Docker or Kubernetes…" | yes | one 3-way OR (Docker, Kubernetes, Python); **Go dropped** | counted | 3 claim-level false SUPPORTED (G16) | bare "Go" unrecognised, so G17's mixed-segment detector misses it. Compound logic is G16 scope and **not** worked around here. |
| **G16-043** (cross-check) "Python, Docker or Kubernetes…" | yes | 3-way OR | counted | 4 false SUPPORTED (G16) | mixed-kind list ambiguity. **No concept-identity error; no G22 policy changes it.** |

## 3. M10E-g3: a specification question (Phase 3)

**The frozen input** (`evaluation/m10e/narrative_controls.json`, section `Responsibilities:`):

> "You will learn SQL, but prior knowledge of databases is required."

**The frozen fields:**

| Field | Value |
|---|---|
| `sentence_purpose` | QUALIFICATION |
| `is_candidate_qualification` | true |
| `necessity_if_justified` | REQUIRED |
| `should_create_job_requirement` | **true** |
| `should_produce_diagnostic` | false |
| `technical_concepts_may_enter_scoring` | **false** |

- **Rationale:** "the explicit 'is required' on 'prior knowledge of databases' must win; 'databases' alone has no specific concept to score."
- **`current_baseline_outcome`:** "JobRequirement(… concept_id='language.sql' …)". `schema_notes` define this as a *captured baseline* from parser v7, explicitly **not** gold.

### Evidence

1. **Does the text assert a candidate qualification?** Yes. G21 splits it into two units:
   - "You will learn SQL" → `nonqual` / `future_duty`;
   - "prior knowledge of databases is required." → `qual` / `marker+attribute`.

   The claim is correctly admitted, and the qualification is *knowledge of databases*.
2. **Is SQL genuinely used as a technical concept?** As an *identity*, yes: SQL really is the SQL language, so this is not a G22 false recognition. As a *requirement*, no: the text says the candidate **will learn** it. The REQUIRED `language.sql` row asserts the opposite of the sentence.
3. **Which stage is ambiguous?** None of the four the brief lists:
   - Admission is right: a qualification unit exists.
   - Recognition is right: the identity is correct.
   - Necessity is right for the claim: REQUIRED is justified by "is required".

   The error is **concept attribution**. A concept from a non-qualification clause inherits the qualification clause's row, because concept extraction is claim-level, not clause-level.
4. **Do the label and the rationale use different definitions of correctness?** They describe **two different dimensions**, and those dimensions are mutually consistent:
   - `should_create_job_requirement=true`: the claim deserves a row, namely the databases requirement.
   - `technical_concepts_may_enter_scoring=false`: no technical concept may be scored.

   The ideal output is therefore a **non-scored** row for "prior knowledge of databases", e.g. `concept_id=None`, `NOT_ASSESSABLE`. Nothing in the frozen gold asks for a SQL requirement; "SQL" does not appear in the rationale.
5. **Is the annotation demonstrably inconsistent?** **No.** The apparent conflict comes from two places:
   - **The regression test projects only one field.** `tests/test_m10e_narrative_requirement_semantics.py` asserts only `len(requirements) > 0 == should_create_job_requirement`, and `technical_concepts_may_enter_scoring` is asserted nowhere.
   - **v14 satisfies that field by accident.** The only row it produces is the SQL row taken from the learning clause.

   Measured live under v14:
   - row existence passes;
   - the SQL row **is counted**, so a candidate with SQL evidence scores **100** against a "databases" requirement.

   v14 therefore violates the second gold field.

### Recommendation

The **frozen gold is correct and internally consistent, and it should stay a regression requirement**. Its row-existence half is already enforced; its concept-scoring half is currently violated by v14 and is not tested.

- **Consequence for design:** clause-scoped concept extraction alone breaks the gold. G20's option C and G22's study option E both drop SQL and return **zero rows**, so the M10E test fails on g3.
  - A correct fix must do **both**: drop SQL **and** preserve a non-scored row for the databases clause. That is a clause-attribution plus requirement-preservation design, outside G22 (clause-level redesign is out of scope).
- **No G22 candidate (A, B, C, Q, D, DB, B2, C2, D2, DB2) changes g3** (test-pinned).
  - g3 is excluded from every G22 aggregate.
  - Both interpretations are reported: row-existence passes, concept-scoring fails.
- **Frozen gold:** not rewritten.

## 4. Controls (Phase 4)

| Set | Controls | sha256 (G14 portable, raw = canonical, LF) | Role |
|---|---|---|---|
| DEV | 46 | `86ec710fc72b9196b5353df1b51bdd3057343784560a34af04104badf42b92f9` (23,190 B) | design set |
| EVAL | 44 | `29b3ea2acf1363fa6c3c7809581bd251a691e724ec3b6f7ba899504081835cc3` (23,219 B) | separately authored, different surfaces and aliases; weakly held out |

**Families** (both sets):

- clear registered technologies;
- ordinary English verbs, adjectives and nouns that are registry aliases (react, express, swift, rust, shell, torch);
- context-disambiguated near-neighbour pairs (DEV 8, EVAL 6);
- single-word fragments (abstract nouns, soft skills, discourse adverbs);
- genuine unknown technologies, including lowercase package names and names with abstract suffixes or "-ly" endings (Unity, Plotly);
- bare technical lists;
- qualifications versus responsibilities versus company narratives;
- equivalent aliases;
- OR alternatives;
- negative qualifications;
- mixed technical and non-technical wording;
- acronyms and punctuation variants (`K8s`, `React.js`, `C#`);
- "Go", Ruby and Rust.

**Labels** were written from first principles and frozen **before** any parser run:

- `is_qualification`;
- the exact multiset of technical rows (members and necessity);
- `identity_only` for G16-058-shaped structure.

The policy design was frozen afterwards (`policy_design_freeze.json`, sha256 of the policy and harness sources), and only then was EVAL run.

**One post-freeze change was a simulation-fidelity fix, not a design change.** Option G's cue was being evaluated on OR *segments*, which lost the claim-level context the design specifies. It is recorded in the freeze with its new hash; it changes no DEV or EVAL result and changes G16-018 only.

## 5. Failure taxonomy, live v14 (Phase 5)

| | DEV (46) | EVAL (44) |
|---|---|---|
| A. False registered concept | 8 | 7 |
| B. Fabricated unresolved concept | 6 | 9 |
| C. Missed genuine concept | 2 (Go ×2) | 4 (Go ×2, embedded C, Linux) |
| D. Incorrect alias equivalence | 1 | 4 |
| E. Incorrect alternative grouping | 0 | 0 |
| F. Admission error (G21 or earlier) | 1 (d29 "No Swift experience needed", the n07 shape) | 0 |
| G. Other (necessity: "Preferably," is not a preference cue) | 0 | 1 |
| **False concepts entering numerical scoring** | **9** | **7** |
| False concepts excluded by v2 | 6 | 9 |
| **False concepts that become SUPPORTED** (adversarial candidate) | **9** | **7** |
| False concepts only in diagnostics / `NOT_ASSESSABLE` | 0 | 0 |
| Real technologies missed completely (no trace) | 0 | 3 |
| Real technologies declined (placeholder or UnparsedClaim) | 3 | 5 |
| Concept recall (registry) | 51/54 (42/45) | 56/64 (41/48) |
| Exact controls | 29/45 | 22/44 |
| Near-neighbour pairs both exact | 0/8 | 0/6 |

**Scoring impact:**

- Every false *registered* concept is counted and becomes SUPPORTED for a candidate who really uses that technology.
- Every fabricated `unresolved:` concept is already excluded by scoring v2. It has **no score effect** and is payload and diagnostic noise only.

## 6. Candidate policies (Phase 6)

All policies are offline adapters (`m11g22_policies.py`) that rebind recognition inputs inside the **real** production parser in-process. Admission, necessity, G17, dedup, the matcher and scoring v2 are the production code.

- **Admission is unchanged by construction.** The G21 decision is wrapped and only extra spans are blanked in its length-preserving `scoped_text` (test-pinned).
- **No policy uses a word blacklist, rejects short aliases wholesale, promotes unfamiliar words, or calls an LLM.**

| Option | What it does |
|---|---|
| **A** minimal guard | G20's generic-usage guard: a **lowercase** surface of a capitalised registry name in a verb or adjective frame ("to react", "a swift", "react quickly"). No metadata. |
| **B** context-aware (B + G) | **B:** reviewed ambiguity metadata for 7 bare aliases (react, express, swift, rust, ruby, shell, torch), whose lowercase forms are ordinary workplace English. These **require a positive technical cue**: mid-sentence technical casing, the alias is the whole claim, a technical lead-in, a head noun after it, or a registry list sibling. Other aliases are untouched. **G:** cue-gated recognition of capitalised "Go". |
| **C** conservative validation | Registry recognition untouched. A single-word `unresolved:` fragment is rejected when it is a lowercase abstract noun (-ity, -ness, -ship, -tion, -ment, -ance, -ence, -ism) or classified by the **existing** `non_technical` detector. A claim-initial "-ly," discourse adverb is blanked (G20 S2U gate). |
| **Q** equivalence | An OR whose every segment resolves to the **same** registry concept is routed to the single-concept path. |
| **D** smaller combined | C + Q + A (no new metadata) |
| DB | C + Q + B |
| E (study only) | G21 clause scoping of concepts, run for M10E-g3. Clause-level redesign is out of scope. |
| B2 / C2 / D2 / DB2 | **POST-HOC** (written after EVAL; not validated). B2 adds head nouns knowledge/expertise plus a capitalised-sibling cue. C2 skips the adverb gate for a pure list of single capitalised tokens. |

**Results:**

- "False reg." = false registered concepts; "Fabricated" = fabricated `unresolved:` concepts.
- "Recall lost" = genuine concepts lost relative to v14 across DEV, EVAL and the historical corpora.
- "False SUPPORTED" = counted false rows SUPPORTED for the adversarial candidate.

| Policy | DEV exact | DEV false reg. | DEV fabricated | EVAL exact | EVAL false reg. | EVAL fabricated | EVAL recall (registry) | Recall lost | False SUPPORTED (DEV / EVAL) |
|---|---|---|---|---|---|---|---|---|---|
| v14 | 29/45 | 9 | 6 | 22/44 | 7 | 9 | 56/64 (41/48) | — | 9 / 7 |
| A | 34 | 4 | 6 | 26 | 3 | 9 | 56/64 (41/48) | **0** | 4 / 3 |
| B | 37 | 1 | 6 | 28 | **0** | 9 | 55/64 (40/48) | Ruby (e09), React (G21-n10) | 1 / 0 |
| G | 31 | 9 | 6 | 24 | 7 | 8 | 58/64 (43/48) | 0 (gains Go) | 9 / 7 |
| B + G | 39 | 1 | 6 | 30 | 0 | 8 | 57/64 (42/48) | as B | 1 / 0 |
| C | 33 | 9 | **0** | 26 | 7 | **2** | 55/64 (41/48) | Plotly (e43, `unresolved`) | 9 / 7 |
| Q | 30 | 9 | 6 | 26 | 7 | 9 | **60/64 (45/48)** | 0 | 9 / 7 |
| **D** = C+Q+A | 39 | 4 | 0 | 34 | 3 | 2 | 59/64 (45/48) | Plotly | 4 / 3 |
| DB = C+Q+B | 42 | 1 | 0 | 36 | 0 | 2 | 58/64 (44/48) | Ruby, React, Plotly | 1 / 0 |
| *DB2 (post-hoc)* | *42* | *1* | *0* | *38* | *0* | *2* | *60/64 (45/48)* | *0* | *1 / 0* |

**Reading the table:**

- **The remaining DEV false-SUPPORTED row under B and DB** is d29, an **F** (G21 negation vocabulary), not a recognition error.
- **The remaining EVAL fabrications under C and D** are:
  - `unresolved:context`, a lowercase common noun that no shape test can tell from a lowercase package name such as numpy;
  - `unresolved:go`, which only G fixes.
- **Necessity changes:** none on any kept row. The necessity counts move only because recovered rows add scored items (DEV 48/48 → 49/49; EVAL 47/50 → 51/54 under Q).
- **Unchanged misses:** embedded C beside FreeRTOS (the bare-C fallback runs only when no safe mention exists), Linux in "Comfortable with Linux, …", and e14 necessity are pre-existing and unchanged by every option.

### Per-option properties

| Option | Score v2 denominator | G17 / G21 | M10E-g3 | Complexity | Production files |
|---|---|---|---|---|---|
| A | removes counted false rows (G20 d016/d017/d022/h011/h012) | 0 G17 changes; admission unchanged | unchanged | low | `jobs/parsing/concepts.py` (usage guard), `parser.py` (apply before row construction) |
| B | as A, plus capitalised and noun cases | as A | unchanged | medium; **new registry metadata** (`TechnicalConcept` field + review) | `concepts/models.py`, `concepts/registry.py`, `jobs/parsing/concepts.py`, `parser.py` |
| G | +1 counted row per recognised Go; G16-018 → contained placeholder | **changes G16-018's G17 row** (an intended containment) | unchanged | low–medium; revisits the "go" prose-unsafe decision for job text | `jobs/parsing/concepts.py`, `parser.py`, `alternatives.py` |
| C | **none** (v2 already excludes `unresolved:`) | none | unchanged | low | `jobs/parsing/concepts.py` (`_consider_fragment`) |
| Q | +1 counted row per equivalence claim (placeholder → concept) | none | unchanged | low | `jobs/parsing/alternatives.py` |
| E | drops SQL | — | **breaks the row-existence gold** | high (clause-level) | out of scope |

## 7. Historical compatibility (Phase 7)

Every policy was compared with live v14 over 456 tracked texts:

| Corpus | Texts |
|---|---|
| G15 | 19 |
| G16 | 58 |
| G18 | 26 |
| M10D | 41 |
| M10E | 51 |
| G6 | 44 |
| G7 | 42 |
| 8c jobs | 15 |
| SOTI / Manulife | 2 |
| G20 dev / held-out | 71 / 36 |
| G21 adversarial | 35 |
| G21 negation scope | 16 |

Scoring was compared on G15, G16 and G18 candidate fixtures, the frozen 8c v1 / v1.1 matrices and M10.

| Policy | Texts changed | Rows −/+ | Registry ids −/+ | Fabricated `unresolved:` removed | Placeholders −/+ | UnparsedClaims Δ | Necessity / span changes |
|---|---|---|---|---|---|---|---|
| A | 5 | 5 / 0 | 5 / 0: **all intended** (G20 d016 react, d017 express, d022 swift, h011, h012) | 0 | 0 / 0 | +5 | 0 / 0 |
| B | 6 | 6 / 0 | as A + **G21-n10 React (genuine loss)** | 0 | 0 / 0 | +6 | 0 / 0 |
| G | 8 | 7 / 8 | G16-018 OR members −3; **language.go +7** (M10D-d3, M10E-i1/i3/i5, G6-020, G7-029/032; every gain matches gold) | 3 (`unresolved:go`, a wrong identity) | 3 / 1 | −1 | 0 / 0 |
| C | 5 | 6 / 0 | 0 | **6** (G16-058 alternatively; G20 curiosity, communication, alternatively; G20-h013 creativity, ownership) | 0 / 0 | 0 | 0 / 0 |
| Q | 2 | 2 / 2 | 0 / +2: **G15-I1 "Kubernetes or k8s", G18-16 "Go or Golang"**, both now match their frozen `alias` gold | 0 | 2 / 0 | 0 | 0 / 0 |
| D | 12 | 13 / 2 | A's 5 intended / Q's 2 | 6 | 2 / 0 | +5 | 0 / 0 |
| DB | 13 | 14 / 2 | as D + n10 | 6 | 2 / 0 | +6 | 0 / 0 |
| *DB2* | *12* | *13 / 2* | *as D (n10 kept)* | *6* | *2 / 0* | *+5* | *0 / 0* |
| E (study) | 2 | 2 / 0 | **M10E-g3 SQL**, G21-a33 Kubernetes (duty clause) | 0 | 0 | +1 | 0 / 0 |

**Scoring:**

- **8c v1 / v1.1 and M10:** 0 score or denominator changes under every policy.
- **Q:** G15-I1 and G18-16 go from *undefined* to **100 / 0**, exactly their frozen `expected_scores` (supported 1 / eligible 1, and 0 / 1).
- **G:** all 9 G16-018 fixtures become undefined (a contained placeholder). G16 claim-level **false SUPPORTED goes from 7 to 4**, and true SUPPORTED from 54 to 51 (018's three satisfied fixtures now decline).
- **A, B, C:** no fixture score changes; their false rows are only in synthetic sets. No policy creates a new false SUPPORTED anywhere.

**Compatibility:**

- **G17:** alternative rows are byte-identical on all 58 G16 controls under every policy, including the study option E, except G and B+G. Those change only 018, which becomes a contained placeholder (test-pinned).
- **M10E row existence:** 0 new mismatches for every G22 candidate. E breaks g3.
- **G21:** admission, role and frame are identical for every claim under every policy (test-pinned). The negation-scope rows are unchanged except B's n10.
- **Private postings** (62, previously inspected, **not independent**; counts only):

| Policy | Postings changed | Rows | Registry-concept rows | Unresolved rows | Denominator rows |
|---|---|---|---|---|---|
| v14 | — | 378 | 71 | 71 | 71 |
| A, B, C, Q, D, DB, B2, C2, D2, DB2 | **0** | 378 | 71 | 71 | 71 |
| G (and B+G) | 1 | 378 | 72 | 71 | 72 |

On the inspected real postings, **none** of the measured false-recognition or fabrication shapes occurs. The G22 defects are real and reproducible, but on this small, non-independent sample their real-world prevalence is low. The only real-posting effect of any option is one recovered "Go" requirement.

## 8. Parser v14 and scoring v2 safety (Phase 8)

Every option except E preserves the following.

| Preserved | How |
|---|---|
| G21 admission | Decisions are identical; only extra blanking is added, never a different decision. |
| G17 containment | Unchanged outside the intended G effect on 018. |
| G19 v2 eligibility | Untouched. |
| Matcher and evidence extraction | Untouched. |
| REQUIRED / PREFERRED / unknown | 0 necessity changes on kept rows. |
| Exact text and spans | 0 span errors in every corpus. |
| Bare technical lists | e.g. "React, Express, Swift" under B. |
| Positive evidence for correctly recognised concepts | Unchanged. |

**Out of scope:**

- clause-level concept attribution (M10E-g3, option E);
- per-clause necessity ("Preferably,", n16);
- heading policy;
- G16 compound logic (043; the 018 compound tree).

## 9. Recommended implementation plan (Phase 9)

The defects have **four distinct root causes in three code sites**. Following the "do not combine unrelated parser defects" rule, they become **separate production milestones**, each its own parser-version bump (v15, v16, …) with a pinned versioned comparison like G21's (`V_prev_REF` clone versus working tree, both reproducible from HEAD).

| Order | Milestone | Root cause → intervention | Files | Metadata | Expected effect | Safeguards |
|---|---|---|---|---|---|---|
| 1 | **Alias equivalence (Q)** | `_classify_segment_list` treats one concept named twice as an unsafe alternative → when every segment resolves (registry) to one identical concept, return the ordinary single-concept path | `alternatives.py` (+ version in `parser.py`) | none | Fixes **2 frozen-gold discrepancies** (G15-I1, G18-16) and 5/5 synthetic controls; +1 counted row each | Applies only when no segment is unsafe and all are registry-resolved. G17 mixed detection runs unchanged before it. |
| 2 | **Recognition usage guard (A)** | `find_concept_mentions` has no usage check → reject a lowercase surface of a capitalised registry name in a verb or adjective frame, applied where the parser builds rows (**not** in segmentation or G21) | `jobs/parsing/concepts.py`, `parser.py` | none | Counted false concepts DEV 9→4, EVAL 7→3; 0 recall loss anywhere | Lead-in or comma before the alias exempts it. Display-name casing is data-driven. |
| 3 | **Unresolved-fragment validation (C2)** | M11-A1's single-word exemption → abstract-noun (lowercase) / existing non-technical-detector gate, plus the claim-initial discourse adverb (skipped for pure capitalised lists) | `jobs/parsing/concepts.py` | none | Fabricated DEV 6→0, EVAL 9→2, historical −6; **no score effect** (v2 already excludes them) | Lowercase package names, Unity and Plotly are kept. C2 is post-hoc: needs a fresh control set before acceptance. |
| 4 | **Go recognition (G)**, decision required | Registry marks "go" prose-unsafe (a README false-positive history) → cue-gated capitalised "Go" in **job text only** | `jobs/parsing/concepts.py`, `parser.py`, `alternatives.py` | none | +7 historical and +1 private genuine Go rows; G16 false SUPPORTED 7→4 (018 contained) | Case-sensitive; requires a lead-in, head noun or registry sibling; never "Go-getter". |
| 5 | **Ambiguous-alias metadata (B / B2)**, decision required | Capitalised or noun ordinary uses A cannot see ("Swift decision-making", "pass the torch", "your shell", "rust and corrosion") → reviewed per-alias field plus positive-cue requirement | `concepts/models.py`, `concepts/registry.py`, `jobs/parsing/concepts.py`, `parser.py` | **yes** (7 aliases) | Counted false concepts → 0 on DEV and EVAL | Cue-only, never a rejection list. B2's recall fixes are post-hoc and need fresh validation. |

**Smallest safe next correction:** item 1 (Q).

- It is the only change backed by **existing frozen gold**.
- It touches one function and needs no new metadata.
- It makes 0 regressions anywhere.

Item 2 (A) is the smallest *precision* fix for counted false concepts, also with no metadata and 0 measured recall loss.

**Milestone ordering:** G20 and G21 reserved "G23" for candidate-profile headings. Taking items 1–5 before headings shifts that work later, so this needs an explicit decision (Q1 below).

**M10E-g3:** left as frozen. It is not a G22 target and changes under no recommended item. A future clause-attribution milestone must satisfy both of its fields.

**Rollback:** each milestone is one revert commit. The parser version in every payload identifies the behaviour, and the comparison runner keeps the previous version reproducible.

**Fresh validation:** EVAL is now spent. Each implementation milestone should be evaluated on a freshly authored, frozen control set, plus the G22 sets as regression.

## 10. Tests and verification (Phase 10)

**Tests** (`tests/test_m11g22_concept_recognition_research.py`, 25 tests) pin:

- the freezes and their manifest registration with the original pre-evaluation hashes (17 entries);
- control-set integrity;
- adapter fidelity: BASE is byte-identical to production, and patches are always restored;
- admission and span invariance under every policy;
- the live v14 failures (version-gated);
- each option's near-neighbour behaviour and documented limits;
- G17 invariance (only G changes G16-018);
- M10E-g3's frozen fields and both dimensions;
- byte-identical regeneration of the public report, compared under the G14 canonical (LF) contract so that a `core.autocrlf=true` checkout also passes. The report records only that each freeze verified, not the checkout-dependent method ("raw" or "canonical"). The clean-checkout matrix found this defect before the commit; it was fixed, and no other report content changed;
- integer-only private aggregates;
- production untouched (v14 / v2, no `src/` import of the research code).

## 11. Approval questions

1. **Milestone ordering:** take the concept-precision milestones (Q, then A, then C2) before candidate-profile headings, or keep headings as G23?
2. Approve **Q (alias equivalence)** as the next production milestone (parser v15)?
3. Approve **A (usage guard, no metadata)** as a separate following milestone? Or go directly to **B** with reviewed per-alias metadata, accepting a registry-model change and its 7-alias review?
4. Approve **C2** (unresolved-fragment validation; no score effect) after fresh validation, given its post-hoc origin?
5. Revisit "go" prose-unsafety **for job text only** (G)? It recovers genuine Go requirements and contains G16-018, but reverses a documented safety decision.
6. **M10E-g3:** confirm the reading (gold correct and consistent; test projection incomplete). Should an additional, non-gold-rewriting test assert the concept-scoring field as a known-failing `xfail`?
7. Should the README-evidence side of the same alias-ambiguity risk (same `readme_safe_aliases` table) get its own research milestone?

**Commit status:** committed as a research-only commit ("test: evaluate technical concept recognition precision") with the two additive manifest registrations (15 → 17). No production change, and no proposed option is implemented.
