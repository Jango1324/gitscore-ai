# Milestone 11-G20 — False Qualification Admission & Parser Precision

Research, evaluation and design only. No production code was changed. Parser
`job_description_parser:v13`, scoring `github_evidence_alignment:v2`, the matcher,
the API and the frontend are byte-identical to HEAD `2144fe6`. No LLM calls.

Reproduce: `python scripts/evaluate_m11g20_false_qualification.py [--private-corpora]`
(about 3 minutes). Report: `evaluation/m11g20/admission_report.json`; private counts:
`evaluation/m11g20/private_admission_aggregates.json`.

**Result provenance** (also recorded in the report's `result_provenance` block):

- Only `v13` is production behaviour, through an asserted byte-identical replica.
  Every other policy, including the recommended B1NR, is an **offline simulation**.
- *Development* results come from the set the policies were designed against.
- *Held-out* results are synthetic and only **weakly** held out: same author, run once
  after the policy freeze.
- *Private* results come from **previously inspected** postings and are **not
  independent validation**.
- **Two post-hoc adjustments** were made after the first private run:
  1. a case-insensitive "us" matched the country abbreviation "US";
  2. "while not required, … is a plus" was treated as a general negation.

  B1NR's private results are therefore post-hoc; both are known risks for G21.
- The known held-out failure, h003 "You must be on call…", is preserved.

## 0. Verified baseline

| Check | Result |
|---|---|
| HEAD / branch | `2144fe6fe23ed1e6451a246120ed93984f216492`, `main`, 0 ahead / 0 behind `origin/main` |
| Parser / scoring | `job_description_parser:v13` / `github_evidence_alignment:v2` |
| Backend suite | 2096 passed, 13 skipped, 18 xfailed |
| Frontend | Vitest 53/53 |
| G14 manifest | 11 freezes |
| G17 containment / G19 eligibility | active (G16-045/058 contained, v2 exclusion reasons emitted) |
| Private M11 artifacts | 18 untracked entries, untouched |

## 1. How v13 admits a qualification, and where it goes wrong

The live path is `parser._parse` → `segmentation.segment_description` →
`parser._requirements_from_claim` → `dedup`. The shadow qualification and competency
modules (`qualification*.py`, `competency_extraction.py`) are not on the live path.

| Stage | Location | Decision it makes |
|---|---|---|
| Heading classification | `segmentation.py:431` `_classify_heading_line` | A heading line maps to REQUIRED / PREFERRED / RESPONSIBILITY / LEARNING / SKIP / UNKNOWN. |
| Sentence admission | `segmentation.py:779-787` | Inside a REQUIRED / PREFERRED / RESPONSIBILITY section, **every** sentence becomes a Claim. Elsewhere a sentence needs `_looks_like_requirement` (`:680`): any registry-alias mention, or a generic HR word such as "experience", "degree" or "skills". |
| Section suppression | `segmentation.py:749`, `:305` | A SKIP section drops every line. `^about\b` also matches "About you:". |
| Necessity eligibility | `necessity.py:154` | Step 1: a local REQUIRED/PREFERRED marker always wins, in any section and any sentence. |
| | `necessity.py:157` | Step 2: only REQUIRED/PREFERRED sections, or a heading-less document, keep their hint. RESPONSIBILITY, LEARNING, UNKNOWN and pre-heading preamble return `None`, which produces an UnparsedClaim. |
| | `necessity.py:163` | Step 3: the narrative veto applies only to two narrow shapes (`narrative.py:45`, `:62`). It catches "our team uses" but not "We use", "We deploy", "You will build" or "Rust is gaining". |
| Concept recognition | `concepts.py:198`, `:217` | Readme-safe aliases are matched in any admitted claim, including the ordinary words "react", "express" and "swift" (`registry.py:193/259/297`). |
| | `concepts.py:414` | A single-word list fragment next to a confirmed concept is exempt from the shape gate, so it becomes `unresolved:<word>` ("curiosity", "alternatively"). |
| Row construction | `parser.py:287-474` | Every detector runs on every admitted claim. No step asks whether the claim is a candidate qualification. |
| Scoring v2 | `assessment/models.py` | Counts every registry-concept row the parser produced. It excludes `unresolved:` rows but cannot recognise a false admission. |

**Root cause.** The v13 parser never decides *qualification intent*. It decides
admission from section context plus vocabulary, and necessity from section context
plus marker words. Three places accept a false qualification:

- **R1** (`segmentation.py:779-787` with `necessity.py:157`): an unconditional
  in-section admission, plus an unsectioned default of REQUIRED.
- **R2** (`necessity.py:154`): a local marker overrides any sentence purpose
  ("You will be required to deploy…", "All services must be written in…").
- **R3** (`concepts.py`): concept recognition has no usage check.

The matcher and scorer behave correctly given the parser's output.

## 2. Phase 2 — reproduced defects (real parser, matcher and scorer)

All 19 reproductions, with every claim's section, marker, hint, necessity, alternative
kind, rows, matcher status, v2 eligibility and score impact, are in
`admission_report.json` under `phase2_reproductions`.

| # | Input (id) | Section / admission | Rows (necessity) | Earliest stage | v2 impact |
|---|---|---|---|---|---|
| 1 | G18-25 "About us: we use Python, Terraform and Docker." | none; admitted | Python, Docker (REQ; SUPPORTED, counted); `unresolved:terraform` (excluded) | R1, unsectioned default; narrative veto misses "we use" | 100 (2/2) instead of undefined |
| 2 | G16-053 "You will maintain services … Python or Go … Docker." | none; admitted | 1 `alternative_requirement` placeholder (REQ, not assessable) | R1 + future-duty sentence | not scored; shown as REQUIRED |
| 3 | d018 "Experience with SQL, attention to detail, and curiosity." | REQUIRED | SQL, `unresolved:curiosity` | R3, single-word fragment | curiosity excluded by v2 |
| 3 | d023 / G16-058 "Alternatively, …" | REQUIRED / none | `unresolved:alternatively` | R3 | excluded by v2 |
| 3 | d016 "Ability to react quickly…" | REQUIRED | `framework.react` | R3, generic word | **counted**; SUPPORTED if the candidate knows React |
| 4 | d060 "Kubernetes adoption has grown…", d011b "Rust is gaining popularity…" | none | k8s / rust (REQ) | R1 | 100 (1/1) instead of undefined |
| 5 | d038 "Our team has grown to 40 engineers across Python and Golang services." under Qualifications | REQUIRED | Python, Go (REQ) | R1, in-section | 100 (3/3) instead of 100 (1/1) |
| 5 | d037 "PyTorch has become the industry standard…" under Requirements | REQUIRED | PyTorch (REQ) | R1 | 100 (1/1) instead of undefined |
| 6 | d039 "Role requirements:" → "Design and ship APIs in Golang." | REQUIRED | Go, Redis (REQ) | R1, misleading heading trusted | 100 (2/2) instead of undefined |
| 6 | d006 "You will be required to deploy services to AWS and Kubernetes." | RESPONSIBILITY | AWS, k8s (REQ) | R2, local marker wins | 100 (2/2) instead of undefined |
| 7 | d025 prose: company, then "Candidates must have strong experience with Python and PostgreSQL.", then benefits | none | only the qualification sentence | correct | — |
| 8 | d030 "Must-haves:" / "Nice-to-haves:" | REQUIRED / PREFERRED | correct | correct | — |
| 8 | d028 "About you:" list | **SKIP; no claim at all** | none | `^about\b` suppresses the list | requirements silently lost |
| 8 | d029 "What you bring:" list | UNKNOWN → UnparsedClaim | none | heading not recognised (G6 design) | lost, shown as a diagnostic |
| 9 | d043 "Bonus:" sub-heading; d009a "Knowledge of Docker is a plus." | PREFERRED | correct | correct | — |
| 10 | d026 unsectioned prose ("You should have solid experience with Golang and Redis. Knowledge of Kubernetes is a plus.") | none | Go, Redis (REQ); k8s (PREF) | correct | — |

## 3. Evaluation controls (Phase 3)

| Set | File | Controls / units | Role |
|---|---|---|---|
| Development | `evaluation/m11g20/admission_controls_dev.json` | 71 / 103 (45 non-qualification, 55 qualification, 3 ambiguous) | Policy design |
| Held-out | `evaluation/m11g20/admission_controls_holdout.json` | 36 / 46 (18 / 27 / 1) | Run once, after the policy freeze |
| Previously inspected real postings | private M11-D/F/G5/G9 sources and annotations; M10 SOTI/Manulife | 62 private postings, 651 annotated claims | Counts only |

Coverage includes:

- clear required and preferred qualifications;
- responsibilities, both headed and unheaded;
- company, product, benefits and hiring-process text;
- generic technology discussion;
- ambiguous qualification language;
- prose and embedded qualifications;
- inherited and soft-wrapped lists;
- unconventional and misleading headings;
- mixed duty and qualification sentences;
- generic-word and legitimate unregistered terms;
- negated and soft necessity.

There are 16 **near-neighbour pairs** (12 dev, 4 held-out), for example
"Experience with Python is required." versus "Our team uses Python.", and "You have
hands-on experience with Kubernetes." versus "You will get hands-on experience with
Kubernetes.".

**Provenance, stated plainly:**

- All controls are self-authored synthetic text, with no real posting text and no
  employer names.
- The author had read the v13 source before writing them, so they are targeted probes,
  **not blind and not independently validated**.
- Gold labels were written, and both files frozen, **before** the parser ran on any of
  them.
- "Held-out" means only "not used to design policies". The same author wrote both sets
  and could recall them, so the held-out set is weakly held out.
- Synthetic rates measure behaviour on targeted shapes. **They are not prevalence
  estimates.**

**Freezes** (G14 portable method, `crlf-to-lf/v1`, LF bytes). Both are registered as
separate entries 12 and 13 of `evaluation/integrity/canonical_hash_manifest.json` in the
authorized research commit. Each was attested from its own freeze record and the hash
printed at freeze time. The freeze records themselves are unchanged; their "not
registered" note was true when written.

| File | sha256 | bytes |
|---|---|---|
| `admission_controls_dev.json` | `eaf2834e31f12fdb4b85466221d5c570ccfb7b691289d08de09f350385bcc729` | 54613 |
| `admission_controls_holdout.json` | `12cc884e33b115391573e702d4fb6dd31783c9c3f3de3a13e3cb513b4087b628` | 26723 |

`policy_design_freeze.json` (frozen 2026-11-10T05:18:31Z, before any held-out or
label-backed private run) records the policy source hashes:

- `m11g20_policies.py`: `2ffe2a94…461a0b`
- `m11g20_admission.py`: `a00e821d…37557`

The evaluator refuses to run if either hash changes.

## 4. Failure attribution (v13, Phase 4)

Each defective unit is assigned one primary category: the earliest stage that accepted
it.

| Category | Dev | Held-out | Representative ids |
|---|---|---|---|
| A. Section / heading | 9 | 7 | d001 (inline "About us:"), d028 ("About you:" → SKIP), d029, d032 (list section leaks into the next paragraph), d039/d040 (duties under a "requirements" heading), h003, h008–h010 |
| B. Qualification intent | 22 | 15 | d002/d003/d009b (employer narrative), d004/d010b (future duty), d006/d007b (marker in a non-qualification), d011b/d037/d060 (technology as subject), d034 (process), d047 (negation), d038 (narrative in Qualifications) |
| C. Segmentation | 0 | 0 | no claim crossed two gold units |
| D. Necessity | 3 | 2 | d044 "would be great", d045 "helpful but not essential", d046 "not required, but appreciated", h021 "beneficial", h022 "helps" |
| E. Concept recognition | 5 | 3 | d016 react, d017 express, d022 swift, d018 curiosity, d019 communication, h011–h013 |
| F. Alternative logic | 0 | 0 | — (G17 containment holds) |
| G. Other (vocabulary gap) | 1 | 0 | d037 "machine learning" (no concept) |

The outcome classes, reported separately:

| Outcome | Dev | Held-out |
|---|---|---|
| False requirement units with content rows | 26 | 16 |
| False rows **entering scoring** (all-evidence candidate) | 30 rows, 30 SUPPORTED | 18 rows, 18 SUPPORTED |
| False rows excluded by v2 | 0 (synthetic) + G18-25's `unresolved:terraform` | 0 |
| False rows shown only as not-assessable | 2 (education, leadership) | 1 |
| Legitimate qualifications missed entirely | 2 (d028) | 2 (h009) |
| Legitimate qualifications declined (visible UnparsedClaim) | 4 | 4 |
| Legitimate qualifications with wrong necessity | 3 | 2 |
| Fabricated concept ids | 6 (3 registry generic-word, 3 unresolved) | 4 (2 + 2) |
| Fabricated registry rows counted / SUPPORTED | 3 / 3 | 2 / 2 |
| Controls whose v2 score or denominator differs from the clean-admission score | 23 | 14 |

## 5. Safety and recall (Phase 5)

Definitions, with non-ambiguous units only:

- **Unit precision** = qualification units with ≥1 row / all units with ≥1 row.
- **Row precision** = legitimate rows / all rows. A legitimate row is on a
  qualification unit and has all members genuinely named, an acceptable non-technical
  category, or a placeholder.
- **Unit recall** = qualification units with ≥1 legitimate content row / all
  qualification units.
- **Concept recall** = gold technologies present as row members / all gold
  technologies.
- **Necessity** = represented qualifications whose rows all carry the gold necessity.
- **Source spans:** every row's span lies inside one gold unit in every policy, and no
  claim crossed two units.
- **Mixed-content postings:** v13 kept 8 of 10 (dev) and 3 of 6 (held-out) independent
  qualifications.

**Dev (designed against):**

| Policy | False adm. | False REQ rows | Pref→REQ | Fabricated | False SUPPORTED | Missed | Unit P | Row P | Unit R | Concept R | Necessity |
|---|---|---|---|---|---|---|---|---|---|---|---|
| v13 | 26/45 | 33 | 3 | 6 | 30 | 2 | 0.653 | 0.587 | 0.836 | 0.889 | 43/46 |
| A0 require intent (rejected) | 14/45 | 18 | 3 | 6 | 16 | 2 | 0.778 | 0.701 | 0.836 | 0.889 | 43/46 |
| A minimal veto | 5/45 | 7 | 3 | 6 | 6 | 2 | 0.907 | 0.818 | 0.836 | 0.889 | 43/46 |
| B1 admission only | 0/45 | 0 | 3 | 6 | 0 | 2 | 1.0 | 0.915 | 0.836 | 0.889 | 43/46 |
| **B1NR admission + necessity (post-hoc fixed)** | **0/45** | **0** | **0** | 6 | **0** | 2 | **1.0** | 0.915 | 0.836 | 0.889 | **46/46** |
| B section-aware | 0/45 | 0 | 0 | 6 | 0 | 0 | 1.0 | 0.923 | 0.909 | 0.963 | 50/50 |
| C two-stage | 0/45 | 0 | 0 | 0 | 0 | 0 | 1.0 | 1.0 | 0.909 | 0.963 | 50/50 |
| S2U stage-2 guards only | 26/45 | 33 | 3 | 0 | 30 | 2 | 0.639 | 0.621 | 0.836 | 0.889 | 43/46 |

**Held-out (run once, after the freeze):**

| Policy | False adm. | False REQ rows | Pref→REQ | Fabricated | False SUPPORTED | Missed | Unit P | Row P | Unit R | Concept R | Necessity |
|---|---|---|---|---|---|---|---|---|---|---|---|
| v13 | 16/18 | 19 | 2 | 4 | 18 | 2 | 0.568 | 0.489 | 0.704 | 0.774 | 17/19 |
| A0 (rejected) | 6/18 | 6 | 2 | 4 | 6 | 2 | 0.778 | 0.677 | 0.704 | 0.774 | 17/19 |
| A minimal veto | 2/18 | 2 | 2 | 4 | 2 | 2 | 0.913 | 0.793 | 0.704 | 0.774 | 17/19 |
| B1 | 1/18 | 1 | 2 | 4 | 1 | 2 | 0.955 | 0.821 | 0.704 | 0.774 | 17/19 |
| **B1NR** | **1/18** | **1** | **0** | 4 | **1** | 2 | **0.955** | 0.821 | 0.704 | 0.774 | **19/19** |
| B | 1/18 | 1 | 0 | 4 | 1 | 0 | 0.963 | 0.853 | 0.889 | 0.968 | 24/24 |
| C | 1/18 | 1 | 0 | 0 | 1 | 0 | 0.960 | 0.967 | 0.889 | 0.968 | 24/24 |
| S2U | 16/18 | 19 | 2 | 0 | 18 | 2 | 0.543 | 0.535 | 0.704 | 0.774 | 17/19 |

**Near-neighbour pairs with both members correct:**

| Policy | Dev | Held-out |
|---|---|---|
| v13 | 2/12 | 0/4 |
| B1NR | 12/12 | 4/4 |
| C | 12/12 | 4/4 |

**Residual (every policy):** h003 "You must be on call one week per month for our AWS
infrastructure." The strong candidate frame "you must" overrides the duty reading.
Recall never fell below v13 for any policy except A0, which loses held-out h031 and
5 M10D bare lists.

## 6. Candidate approaches (Phase 6)

All policies are offline hooks around the real production functions
(`scripts/evaluation_lib/m11g20_policies.py`; post-hoc corrections in
`m11g20_posthoc.py`). A v13 replica is asserted identical to production on all 405
texts.

**Frames.** Every frame is a closed grammatical shape, never a technology, employer or
role word:

- **Positive:** a strong candidate subject ("you have / must / should", "candidates
  must", "we require / are looking for…"); a weak attribute noun ("experience",
  "knowledge", "proficiency", "degree", "N years"); a local or predicate necessity
  marker.
- **Negative:** employer subject ("We / Our / The team …"); future duty ("You will /
  You'll <verb>", except need/have/bring/be comfortable); learning; benefit; hiring
  process; technology-as-subject discussion; team practice; negation.

A negative frame is overridden only by a strong frame, or by a marker attached to an
attribute in the **same clause**. Clauses are split on ";" and ", but".

| Option | What it does | False adm. removed (dev / held-out) | Legitimate lost | Necessity errors | Fabricated | G17 | v2 effect | Complexity | Files |
|---|---|---|---|---|---|---|---|---|---|
| A0 (rejected) | Unsectioned claims must show positive intent | 12 / 10 | **5 M10D bare lists, 1 M10E, 1 held-out** | unchanged | unchanged | ok | — | low | parser |
| A minimal | Today's narrative-veto scope (no marker; REQUIRED/PREFERRED or heading-less doc), widened to the closed negative-frame set | 21 / 14 | 0 historical; 1 private (frame bug) | unchanged | unchanged | ok | fewer false counted rows | low | `narrative.py` / `necessity.py` |
| B section-aware | Frames in every section; marker must sit in a qualification clause; duty-lead bullets in qualification sections; candidate-profile headings → REQUIRED; list-section paragraph reset; necessity refinement | 26 / 15 | 0 historical; 2 private (frame bugs) | 3→0 / 2→0 | unchanged | ok | +2 private denominator rows | medium | new `qualification_intent.py`, `parser.py`, `necessity.py`, `segmentation.py` |
| C two-stage | Stage 1 = B. Stage 2 = concept recognition scoped to qualifying clauses, plus generic-word usage guard (lowercase verb/adjective surface after "to" / "a", or before an "-ly" word) and abstract-noun / discourse-adverb fragment gate | 26 / 15 | as B; **M10E-g3** (`SQL` from "You will learn SQL" is dropped → UnparsedClaim) | 3→0 / 2→0 | **6→0 / 4→0** | ok | fabricated counted rows 3→0 / 2→0 | high | B + `concepts.py` |
| B1 (component) | B's admission decision only | 26 / 15 | 0 historical; 2 private (frame bugs) | unchanged | unchanged | ok | false counted rows 30→0 / 18→1 | low–medium | new module + `parser.py` |
| **B1NR (recommended)** | B1 + necessity refinement + the 2 post-hoc frame fixes | 26 / 15 | **0** anywhere | 3→0 / 2→0; private 7→5 | unchanged | ok | private denominator 71→71 | low–medium | new module, `parser.py`, `necessity.py` |
| S2U (component) | Stage-2 guards without clause scoping | 0 | 0 | — | **6→0 / 4→0** | ok | fixes G16-058 | low | `concepts.py` (+ parser) |
| H (component) | Candidate-profile headings + paragraph reset | 1 / 1 | 0 | — | — | ok | +7 private rows | low | `segmentation.py` — but **changes 18 frozen G6/G7 heading-kind labels** |

A0 is rejected. Declining text merely for lacking a qualification frame is exactly the
"exclude all prose" failure the brief warns against: it destroyed genuine bare
technology lists ("Java, Python and/or Go").

The design rule kept by every other option: decline **only on positive evidence** of a
non-qualification.

## 7. Constraint compliance of the recommended slice (Phase 7)

| Constraint | B1NR |
|---|---|
| G17 containment | 0 violations; every admitted G16 alternative row is byte-identical |
| G19 scoring v2 | untouched; only the set of rows changes |
| Evidence extraction / matcher | untouched |
| API / frontend | untouched; declined claims use the existing `UnparsedClaim` |
| REQUIRED / PREFERRED / UNKNOWN | kept; a decline gives "unknown" (no row); necessity is only *narrowed* (REQUIRED → PREFERRED on an explicit soft or concessive cue) |
| Source text and spans | rows keep their exact claim spans |
| Legitimate headings and lists | 0 regressions on G6 / G7 / M10D / M10E / G15 / G16 / G18 gold |
| Historical gold | read-only; no file rewritten |
| Diagnostics | ambiguous or declined content stays visible as an UnparsedClaim |
| No blacklist | closed grammatical frames; strong candidate frames always override |

## 8. Historical impact (Phase 8)

**Design sets:**

- G20 dev
- G15, G16, G18
- M10D, M10E
- G6, G7
- 8c job fixtures
- M10 postings

**Held out from design:**

- G20 held-out (weakly)
- the label-backed private annotations, first run only. The post-hoc variants were
  corrected after that run and are labelled as such.

**Tracked corpora** (298 texts: gold fixed and regressed, row deltas):

| Policy | Fixed vs gold | Regressed vs gold | Rows −/+ | G6 / G7 heading-label agreement | 8c v2 scores changed |
|---|---|---|---|---|---|
| A0 (rejected) | G16-053, G18-25 | **M10D c1 c2 e1 e2 e3; M10E-h2** | −11 / 0 | 41 / 39 (unchanged) | 0 / 24 |
| A | G16-053, G18-25 | 0 | −4 / 0 | unchanged | 0 |
| B1, B1N, B1R, **B1NR** | G16-053, G18-25 | **0** | −4 / 0 | unchanged | 0 |
| B | + 9 G6 body qualifications | 0 | −4 / +9 | **41→25 / 42, 39→37 / 39** | 0 |
| C, CR | as B | **M10E-g3** | −6 / +9 | 41→25, 39→37 | 0 |
| S2U | fabricated `unresolved:alternatively` removed (G16-058) | 0 | −1 / 0 | unchanged | 0 |

The G18-25 fix moves the narrative control's synthetic score from 100 (2/2) to
undefined. G16-053 becomes an UnparsedClaim instead of a REQUIRED placeholder.

The frozen 8c pairs, M10 SOTI and Manulife are unchanged by every policy.

**Private postings, unlabeled impact** (62 postings, counts only):

| Policy | Postings changed | Rows | REQUIRED rows | v2 denominator rows | No-eligible postings |
|---|---|---|---|---|---|
| v13 | — | 379 | 311 | 71 | 28 |
| A | 1 | 378 | 310 | 71 | 28 |
| B1 (frozen) | 3 | 376 | 308 | 71 | 28 |
| **B1NR** | 3 | 378 | 308 | 71 | 28 |
| B / C | 6 | 383 | 314 | 73 | 27 |
| CR | 5 | 385 | 315 | 73 | 27 |

**Private postings, label-backed** (651 pre-existing claim annotations from
M11-D/F/G5/G9; 650 located; 153 non-qualification, 497 qualification):

| Policy | False admissions | Qualifications admitted | Precision | Recall | Necessity correct | Preferred marked REQUIRED |
|---|---|---|---|---|---|---|
| v13 | 4 / 153 | 242 / 497 | 0.9837 | 0.4869 | 231 / 242 | 7 |
| A (frozen) | 4 | 241 (−1) | 0.9837 | 0.4849 | 230 / 241 | 7 |
| B1 (frozen) | 4 | **240 (−2)** | 0.9836 | 0.4829 | 230 / 240 | 6 |
| B1N (frozen) | 4 | 240 (−2) | 0.9836 | 0.4829 | 231 / 240 | 5 |
| **B1NR (post-hoc)** | 4 | **242 (±0)** | 0.9837 | 0.4869 | **233 / 242** | **5** |
| B / C (frozen) | 4 | 245 (+3) | 0.9839 | 0.4930 | 236 / 245 | 5 |
| CR (post-hoc) | 4 | 247 (+5) | 0.9841 | 0.4970 | 238 / 247 | 5 |

What the real data shows, honestly:

1. **Real false admissions are rare here.** v13 admits 4 of 153 annotated
   non-qualification claims. **None enters scoring** under v2: 2 are
   `unresolved_requirement` placeholders, 1 is a legal row, and 1 is a learning-interest
   sentence whose 6 `unresolved:` rows v2 excludes. No policy removes them; they reveal
   uncovered shapes: a negated-need statement and a learning-interest statement (synthetic analogues: "No prior
   fintech background is needed."; "Curiosity about tools such as Kafka or Spark.").
   The annotations focus on qualification sections, so this is a sample, not a
   prevalence estimate.
2. **The frozen frames had two real defects,** found only on this data:
   - `EMPLOYER_SUBJECT` was case-insensitive, so a sentence opening with the country
     abbreviation "US" (synthetic analogue: "US work authorization is required.") matched
     the pronoun "us";
   - a concessive negation (synthetic analogue: "Although not required, Rust experience is
     a plus.") was read as a negation.

   Each caused one false decline. `m11g20_posthoc.py` fixes exactly these two frames.
   The corrected B1NR loses 0 and is **post-hoc** for these sets.
3. The 48.7% qualification recall is a pre-existing concept-vocabulary ceiling (M11-G8),
   not an admission effect. No policy materially changes it.

## 9. Recommended implementation plan (Phase 9)

Use **three narrow milestones, not one rewrite.** Each is separately approved and
versioned.

### G21 — qualification-intent admission guard + necessity refinement (B1NR)

- **Root cause addressed:** R1 and R2. No stage decides qualification intent, and a
  local marker overrides sentence purpose.
- **Intervention point:** the top of `parser._requirements_from_claim`, before
  `resolve_necessity_hint`. A claim whose clause-level decision is "non-qualification"
  returns `[]`, which takes the **existing** UnparsedClaim path. Necessity refinement
  runs after `infer_necessity`, **in the parser**, so the shadow `competency_extraction`
  path, which also calls `infer_necessity`, is unaffected.
- **Production files:**
  - `src/gitscore/jobs/parsing/qualification_intent.py` (new: closed frames, clause
    split, `decide()`);
  - `src/gitscore/jobs/parsing/parser.py` (one call; version **v13 → v14**);
  - `src/gitscore/jobs/parsing/necessity.py` (new `refine_necessity()`: negated and
    concessive REQUIRED markers, soft-preferred cues);
  - optionally `competency_extraction.py`, only to import `_RESPONSIBILITY_LEAD` from the
    new module instead of owning it (no behaviour change).

  No segmentation, concepts, alternatives, matcher, assessment, API or frontend change.
- **Tests required before implementation:**
  - G20 dev + held-out pinned as `pytest` parametrized tests against the live parser;
  - all 16 near-neighbour pairs;
  - the two post-hoc defect shapes (sentence-initial "US …"; concessive "although not
    required, … a plus");
  - G15 / G16 / G18 / M10D / M10E / G6 / G7 gold: 0 regressions;
  - G17 containment byte-identity;
  - G19 v2 reconciliation;
  - the private label-backed aggregate (0 lost qualifications);
  - version-aware updates to every test that pins `v13` (G16's pattern; no frozen gold
    rewritten);
  - a test that A0-style "require intent" stays absent: M10D bare lists still admitted.
- **Diagnostics contract:** a declined claim is an `UnparsedClaim(text, source_span)`,
  unchanged. The decision and frame are an internal record for tests only. Exposing a
  reason is a separate, additive API decision (Q5).
- **Necessity preservation:** admission never invents necessity. Refinement only
  narrows REQUIRED → PREFERRED on an explicit cue, or turns a bare negation into no row.
- **Rollback:** one revert commit. v14 vs v13 is visible in every payload's `versions`.
  The G20 report keeps the v13 baseline.
- **Exclusions:** headings, stage-2 concept guards, clause-scoped concept extraction,
  preamble recovery (d027), the h003 duty-with-"you must" shape, the private residual
  shapes, and vocabulary gaps.

### G22 — concept-recognition guards (S2U)

- **Root cause addressed:** R3.
- **Changes:**
  - `concepts.py` `_consider_fragment`: abstract-noun suffix and sentence-initial
    discourse adverb gate for single-word fragments;
  - a generic-usage check for a lowercase surface of a capitalised registry name used
    as a verb or adjective. This needs the alias data reviewed: `swift`, `react` and
    `express` are the measured cases.
- **Measured:** 6→0 and 4→0 fabricated, 0 regressions, fixes G16-058.
- **Deferred:** clause scoping, which drives M10E-g3, until the M10E gold-versus-
  rationale conflict is decided (Q3).

### G23 — candidate-profile headings (H)

- "About you" / "What you bring" / "The ideal candidate" → a qualification section.
- **Recovers** 9 G6 body qualifications, 4 dev and 5 held-out units, and 3–5 private
  qualifications.
- **Reverses** G6's explicit "never default REQUIRED" decision and changes 18 frozen
  heading-kind labels (G6: 16, G7: 2). It needs an explicit decision (Q4) and
  version-aware tests. Gold is never rewritten.

**Not recommended:** A0, and any broad keyword list.

### Remaining unresolved issues

- the h003 "You must be on call…" condition;
- the negated-need and learning-interest shapes seen in private postings;
- pre-heading preamble qualifications (d027);
- concept-vocabulary recall (M11-G8);
- the G17 residuals (043, 018), cross-sentence alternatives, and alias ORs.

## 10. Verification (Phase 10)

- **Backend suite:** 2122 passed, 13 skipped, 18 xfailed, 0 failed. This is the
  baseline 2096 plus 26 new G20 tests. Skips are identical; all 18 xfails are kept.
- **Frontend:** untouched (53/53 at baseline).
- **Versions:** parser `v13`, scoring `v2`.
- **Production unchanged:** `git diff HEAD -- src` is empty, asserted by
  `test_production_source_unchanged_from_head`. The research modules are never imported
  by `src`.
- **Historical integrity:** the pre-existing G14 freezes are unchanged. At research
  time the manifest had 11 entries; the research commit adds the two G20 entries
  (11 → 13), leaving the existing 11 unchanged field for field.
- **Replica fidelity:** the v13 replica equals production on 405 texts (107 G20 + 298
  historical).
- **Inputs:** no LLM and no network.
- **Privacy:**
  - private aggregates are integer-only (enforced by the writer and a test);
  - a test checks every ≥40-character line of all 62 private postings against every
    tracked G20 artifact and finds 0 hits;
  - private diagnoses in this document are by frame name only.

## 11. Known limitations

- **Controls are not independent.** They are self-authored, written after reading the
  parser, and the held-out set is only weakly held out.
- **Synthetic rates are not prevalence.** Real annotated postings show 4 / 153 false
  admissions, none scored.
- **Post-hoc frame fixes:** the private sets that revealed the two frame bugs are no
  longer unseen for B1NR. An independent fresh corpus is needed before claiming
  generalisation.
- **Necessity has two values.** "Unknown" stays expressed as "no row".
- **Frames are English-only** and closed. New shapes need evidence-driven, versioned
  additions.

## 12. Committed files (15 new + 2 modified)

- **New:**
  - `docs/evaluation/MILESTONE_11_G20_FALSE_QUALIFICATION_ADMISSION.md`
  - `evaluation/m11g20/{admission_controls_dev,admission_controls_holdout,controls_dev_hash_freeze,controls_holdout_hash_freeze,policy_design_freeze,admission_report,private_admission_aggregates}.json`
  - `scripts/evaluate_m11g20_false_qualification.py`
  - `scripts/evaluation_lib/m11g20_{build_controls,admission,policies,posthoc,historical}.py`
  - `tests/test_m11g20_false_qualification_admission.py`
- **Modified:**
  - `docs/CHANGELOG_DEV.md`
  - `evaluation/integrity/canonical_hash_manifest.json` (+2 entries)

## 13. Approval questions

1. Approve **G21 = B1NR** (admission guard + necessity refinement, parser v14) as the
   next production milestone?
2. Should the necessity refinement ship inside G21, or as its own milestone?
3. Approve **G22** stage-2 guards without clause scoping? For M10E-g3, which wins:
   the frozen gold (create the SQL requirement) or its own rationale (no concept to
   score)?
4. Is revisiting G6's "candidate-profile headings stay UNKNOWN" decision (**G23**)
   acceptable, given 18 frozen heading labels would diverge?
5. Keep `UnparsedClaim` unchanged, or add an additive decline-reason field later?
6. *(Resolved: the research commit and the registration of manifest entries 12–13 were
   authorized.)*

**Commit status:** committed as a research-only commit
("test: evaluate false qualification admission") after authorization. B1NR is **not**
implemented in production, and G21 has not started.
