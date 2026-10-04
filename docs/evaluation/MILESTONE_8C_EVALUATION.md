# Milestone 8C — Real-World Evaluation & Failure Analysis

**Status:** evaluation only. No production code under `src/gitscore/` was
changed. This report measures the pipeline as Milestone 8B left it
(`HEAD=f3213e4`) and recommends — but does not implement — fixes.

**Corpus version:** `8c:v1` (`evaluation/`, `scripts/evaluation_lib/`,
`scripts/evaluate_*.py`, `tests/test_evaluation_harness.py`).

**Methodology summary:** four layers (A. job parsing, B. candidate
evidence, C. matching, D. assessment/presentation) were each evaluated
against hand-authored, evaluator-written gold expectations, run through
the REAL, unmodified pipeline functions. Every gold annotation below was
written by reading the job text / inspecting the raw candidate repo list
directly — never by running the parser/extractor first and copying its
output as "gold." Where a prediction was later found to be wrong due to a
genuine misunderstanding on the evaluator's part (two cases, both
disclosed in §1), the gold row was corrected and the correction is
documented; no gold row was adjusted to make a real pipeline behavior
"pass."

---

## 1. How many job descriptions were evaluated?

**15** synthetic, hand-authored job descriptions
(`evaluation/jobs/*.json`), covering **103** evaluator-authored expected
requirement rows (`evaluation/gold/jobs/*.json`).

Every posting is original text written for this evaluation — none are
copied or paraphrased from a real company's listing (see each job file's
`source_note`).

## 2. Which role families?

backend, frontend, fullstack, general_swe, mobile, embedded_firmware,
robotics_controls, ml_engineering, computer_vision, data_science,
data_engineering, devops_cloud, sre_platform, systems_cpp, security — 15
families, one posting each. (Controls/mechatronics was folded into
`robotics_controls` rather than given a 16th separate posting, to stay
inside the instructed 12–20 range while still covering nearly every
listed family.)

## 3. How many expected requirements?

**103** gold rows across the 15 postings (median ~7 per posting). Facet
breakdown: 46 technical (single-concept), 9 alternative (OR-group), 48
non-technical (including the deliberate "no registry concept, no
non_technical.py pattern" placeholder rows used to probe registry gaps).

## 4. Parser recovery/error breakdown

| status | count | % of 103 |
|---|---|---|
| CORRECT | 54 | 52.4% |
| MISSING | 45 | 43.7% |
| WRONG_ALTERNATIVE_STRUCTURE | 4 | 3.9% |
| PARTIALLY_CORRECT | 0 | 0% |
| WRONG_CONCEPT / WRONG_NECESSITY / WRONG_OBSERVABILITY (standalone) | 0 | 0% |

**Recall = 0.524** (CORRECT+PARTIALLY_CORRECT / total). **Precision =
1.0** (zero spurious requirements — the parser never invented a
requirement gold didn't anticipate, across the whole corpus).

**OBSERVATION:** the parser is highly *precise* (it essentially never
hallucinates a requirement) but has a wide recall gap, driven almost
entirely by two root causes, not scattered bugs:

1. **Concept registry gaps (by far the largest contributor).** Of the 45
   MISSING rows, the overwhelming majority are technologies/concepts
   genuinely named in the posting that simply have no `TechnicalConcept`
   entry: SQL, Kubernetes (alone), GraphQL, Jenkins, Terraform, CMake,
   dbt, Snowflake/BigQuery, Swift, Kotlin, React Native, Flutter,
   MATLAB/Simulink, PLC, OpenCV, scikit-learn, OAuth, SPI/I2C/UART, "Git,"
   "Linux," generic "distributed systems"/"CI/CD" phrasing, etc. This is
   §6's finding, not a parser defect — the parser is doing exactly what
   it is designed to do (never fabricate a concept the registry doesn't
   know).
2. **A specific, reproducible parser fragility in the OR/alternative
   path for short, "unsafe-aliased" concepts** (`C`, `Go`) — see §10 for
   the full trace. This produced all 4 WRONG_ALTERNATIVE_STRUCTURE cases
   and is the single most surprising, highest-severity PARSER finding in
   this report (§13, #1).
3. **A standalone discovery, independent of the OR path:** bare `C` (the
   language) stated in ordinary prose, with no comma-list and no OR,
   is **silently and completely dropped** — not even promoted to an
   `unresolved:` placeholder — because `language.c` has **zero**
   README-safe aliases (by design, to avoid the single-letter
   ambiguity). See §10.

**Two gold-authoring corrections made during this evaluation** (disclosed
per this report's own methodology section): (a) a FreeRTOS-OR-RTOS gold
row was initially miscoded as a plain technical row instead of the
correct non-technical "unsafe fallback" facet — fixed after tracing the
real `classify_alternative_claim()` logic, not after seeing the parser's
output and copying it; (b) a numpy-in-a-comma-list gold bullet was
rewritten twice after discovering the comma-gated promotion policy
(a) requires an *actual comma character*, not "and," and (b) requires
the promoted term to be the list's *last* token with no trailing
descriptive phrase after it — both are real, previously-undocumented-by-us
shape constraints on `find_conservative_unknown_terms()`, now written up
in §10.

## 5. Which concepts were most often missed?

| concept_id / term | miss count |
|---|---|
| `unresolved:kubernetes` | 2 |
| `language.c` | 2 |
| `language.go` | 2 † |
| `language.python` | 2 † |
| `language.cpp` | 1 † |
| `unresolved:bigquery`, `unresolved:snowflake`, `unresolved:spi`, `unresolved:i2c`, `unresolved:uart`, `unresolved:angular`, `unresolved:vue`, `unresolved:flutter`, `unresolved:react_native`, `unresolved:matlab`, `unresolved:simulink` | 1 each |

† `language.go`/`language.python`/`language.cpp` are counted here because
they were members of a `WRONG_ALTERNATIVE_STRUCTURE` group (§10), not
because the individual concept was unrecognized in isolation — Python
resolved correctly within those same claims. Reported as-is for
transparency rather than hand-adjusted, with this caveat.

## 6. Concept registry gap analysis

**Already supported** (31 concepts; see `src/gitscore/concepts/registry.py`):
languages (python, javascript, typescript, java, c, c++, c#, go, rust,
ruby, php, shell, html, css, jupyter notebook), 2 databases (postgresql,
redis), 2 ML frameworks (pytorch, tensorflow), pandas, 2 frontend
frameworks (react, next.js), 3 backend frameworks (express, nestjs,
fastapi, flask), prisma, docker, aws, cuda, ros2, freertos, verilog, llvm.

**Recurring gaps this corpus surfaced** (technologies named by name in
real-sounding postings, with zero registry representation): **SQL
(generic)**, **Kubernetes**, GraphQL, Terraform, Jenkins, dbt,
Snowflake, BigQuery, **Swift**, **Kotlin**, React Native, Flutter,
MATLAB, Simulink, PLC, OpenCV, scikit-learn, numpy (partially mitigated —
see §10, it DOES reach `unresolved:` under narrow conditions), MongoDB/
MySQL (reach `unresolved:` only inside an OR), Azure/GCP (AWS only today),
OAuth, CMake, generic cloud terms. **Kubernetes and Swift are the two
highest-frequency, highest-real-world-importance gaps** — Kubernetes
appeared in 3 of 15 postings (backend, devops, SRE) and Swift/Kotlin are
the entire mobile-engineering vocabulary.

**Alias false positives found (not predicted in advance):**
1. **`react native` → `framework.react`.** "React Native" (a distinct
   mobile framework) contains the substring "React" as a whole word, and
   `framework.react`'s README-safe alias list includes bare `react`
   with no phrase-level disambiguation — so "Experience with React
   Native or Flutter" resolves to `('framework.react',
   'unresolved:flutter')`, NOT `(unresolved:react_native,
   unresolved:flutter)`. This is a genuine `CONCEPT_ALIAS_FALSE_POSITIVE`
   — a job asking for React Native would be (mis)matched against a
   candidate's plain React evidence. **HIGH severity** (silently
   conflates two meaningfully different skills).
2. **llm.c README over-attribution (evidence layer, not the job
   parser):** karpathy/llm.c's README discusses *other contributors'*
   derivative ports in other languages ("C# — llm.cs by @azret"), and
   the README extractor attributes `language.cpp`/`language.csharp`
   evidence to karpathy's own repository for mentioning them in passing.
   This is consistent with the already-documented "contextual mention,
   not proof of use" disclaimer (`evidence/extraction/readme.py`), but
   the specific *failure mode* (misattributing a credited third party's
   separate reimplementation) had not been previously observed/written
   up. **LOW–MEDIUM severity** (rare phrasing pattern; the mis-evidence
   is WEAK/MODERATE confidence and would be outweighed by real evidence
   in most profiles).

No fix for either is implemented in this milestone (§24 freeze).

## 7. How many relevant repos fell outside top-N?

**3 of 4 evaluated "not-analyzed" predictions were confirmed genuine,
relevant retrieval misses** (`REPOSITORY_RANKING_MISS`), out of 10
ranking checks across 4 real candidates:

| candidate | repo | stars | why relevant | why excluded |
|---|---|---|---|---|
| Jango1324 | `Pneumonia-Detection-Ai` | — | Python ML project; this EXACT repo name was used as the illustrative example in Milestone 8A's own prompt ("Supported by: pneumonia-detection-ai") | falls outside this 20-repo account's top-15 cutoff |
| karpathy | `nn-zero-to-hero` | 24,636 | substantive Jupyter-Notebook ML teaching repo | falls outside this 63-repo account's top-15 cutoff |
| sindresorhus | `execa` | 7,609 | genuine, actively maintained JS/TS CLI library, real engineering substance | falls outside this 1,142-repo account's top-15 cutoff |

The 4th prediction (`sindresorhus/awesome`, 514k+ stars — the single
most-starred repo on GitHub) was **correctly** excluded and is NOT
counted as a miss: it is a pure curated markdown link-list with no real
language/substance, and `ranking/config.py`'s own design explicitly
states popularity must not dominate. This is the ranker working as
intended, not a bug.

**OBSERVATION:** the single strongest, most generalizable finding here
is structural, not anecdotal: **the moment a candidate has materially
more repositories than `top_n` (15), SOME genuinely relevant repository
will be excluded, with no mechanism to recover it even when a specific
job posting would clearly care about it.** `torvalds` (12 repos, 100%
coverage) shows the ranker performs perfectly when there's no scarcity;
`sindresorhus` (1,142 repos, 1.3% coverage) shows the scarcity problem at
its most extreme.

## 8/9. Evidence misses inside analyzed repos / which extractor source types caused them?

**Zero.** All 9 concept-level checks on repositories that WERE analyzed
came back `found=True` — `language.c`/`language.cpp` (language stats),
`platform.cuda`/`language.python` (language stats), `ml.framework.pytorch`
(dependency/requirements.txt), `language.jupyter_notebook` (language
stats), `language.typescript` (language stats). Zero `BUG` classifications,
zero `KNOWN_SCOPE_LIMITATION` misses triggered (the ones this evaluation
anticipated — notebook-content inspection, `setup.py` not being a
supported manifest — were correctly absent-and-accounted-for, not
silently wrong).

**One false positive**, already covered in §6 (llm.c README
over-attribution).

**OBSERVATION:** given a repository that DOES make the ranking cutoff,
the bounded Milestone 5D extractors (language stats, README, dependency
manifests, Docker) are reliable on this sample — the evidence layer's
risk is concentrated in §7 (whether a repo is even looked at), not in
what happens once it is. This is a genuinely reassuring result for a
small sample; it is not proof the extractors are bug-free in general
(see §19 Known Limitations).

## 10. Did the matcher make errors given correct upstream data?

**Zero matcher/assessment logic errors** across the 12 end-to-end pairs
(`assessment_aggregation_errors=0`, `matcher_integrity_errors=0`) — every
`alignment_score` independently recomputed from `supported_count`/
`assessable_count` via the exact half-up formula matched
`JobAssessment.alignment_score` bit-for-bit, and every `SUPPORTED` match's
`matched_concept_ids` stayed inside its requirement's own declared
concept set. 7A/7B's existing dedicated test suites already cover this
extensively on hand-built fixtures; this milestone's contribution is
confirming the SAME zero-error result holds on 12 *real* candidate ×
job combinations the matcher/assessment code had never seen before.

**The real finding at this layer is upstream-caused, not a matcher bug** —
the full trace, because it is this report's single highest-value finding:

> **`torvalds` × `embedded_firmware_01` → `alignment_score = 0`,
> `required = None` ("no required requirements were assessable").**
> The posting's ONLY required *technical* claim is "Strong C experience
> in embedded, resource-constrained environments." Because `language.c`
> has zero README-safe aliases (§6's design trade-off against the
> single-letter-ambiguity problem), this sentence — in ordinary prose,
> no comma-list, no OR — produces **zero** `JobRequirement` rows: not a
> `NOT_ASSESSABLE` placeholder, not an `unresolved:` concept, nothing at
> all. The posting's SPI/I2C/UART and oscilloscope/CMake bullets are
> separately dropped for the registry-gap reasons in §6. What survives
> parsing is exactly two requirements (an `alternative_requirement`
> fallback for "FreeRTOS or another RTOS," and a preferred Verilog
> claim) — and `torvalds` has zero Verilog evidence. The result: one of
> the most famous C programmers alive gets a flat **0** on an embedded
> firmware posting, and the UI's own "Required: No required requirements
> were assessable" message — accurate as a literal statement about
> `JobAssessment`, completely misleading as a statement about this
> candidate's actual C expertise, which the SAME pipeline's language-
> stats extractor correctly measured as `language.c` on `torvalds/linux`
> in the very same run (§9). The matcher and assessment math are both
> *provably correct* here; the defect is entirely upstream, in the job
> parser's handling of a single, extremely common, one-letter language
> name.

**Full trace of the OR/alternative parsing fragility that produced all 4
`WRONG_ALTERNATIVE_STRUCTURE` cases** (not predicted in advance; found by
tracing the actual output):

| posting bullet | expected | actual `alternative_concept_ids` | root cause |
|---|---|---|---|
| "Proficiency in Python or Go for tooling development" | `(language.go, language.python)` | *collapsed entirely* to the non-technical `alternative_requirement` fallback | `_strip_trailing_filler` doesn't recognize "for tooling development" as fillable, so the Go segment becomes "Go for tooling development" (4 words) → `clean_list_fragment`'s ≤3-word shape check fails → `kind="unsafe"` |
| "Strong Python or Go programming skills" | `(language.go, language.python)` | `(language.python, unresolved:go_programming)` | "programming" isn't in `_TRAILING_FILLER`'s fixed vocabulary (required/mandatory/essential/preferred/experience/skills/knowledge/proficiency), so only "skills" strips, leaving "Go programming" — which fails to resolve as "go" and gets promoted as a NEW, wrong unresolved term |
| "Expert-level C or C++" | `(language.c, language.cpp)` | `(language.cpp, unresolved:expert-level_c)` | `clean_list_fragment`'s prefix-stripper doesn't know "expert-level"; bare `c` has NO README-safe alias at all (§6), so "Expert-level C" never matches via step 1 and the escalation lookup of the whole phrase fails |
| "Experience with React Native or Flutter" | `(unresolved:flutter, unresolved:react_native)` | `(framework.react, unresolved:flutter)` | the §6 alias false positive — "React" matches inside "React Native" |

**Root cause, stated once:** every one of these 4 cases involves a
registry concept whose bare alias is short/ambiguous enough to be marked
`readme_unsafe_aliases` (`c`, `go`) or substring-collides with another
concept's alias (`react` inside `react native`) — and the OR-segment
resolution path's trailing/leading-word stripping is a small, fixed
vocabulary that doesn't anticipate ordinary descriptive words
("programming," "for tooling development," "expert-level") sitting next
to the technology name. **This is a narrow, well-understood, fixable
class of bug**, not a sign of broad unreliability — it only manifests for
the specific concepts whose bare alias was already flagged unsafe, and
only when something uncommon is adjacent to them, which disproportionately
means SHORT technology names (C, Go) are the ones affected.

## 11. Did assessment aggregation make any errors?

No (see §10 — zero `assessment_aggregation_errors`). The one "surprising"
number in the matrix (`karpathy × frontend_01 = 80`, scoring HIGHER than
`karpathy × ml_engineering_01 = 75` despite the "negative" cross-domain
expected direction) is **mathematically correct, not an aggregation
bug** — it is a `PRESENTATION_CONFUSION`-class finding about what a
small assessable denominator can do to an otherwise-honest percentage;
see §12.

## 12. Which failures most affected end-to-end interpretation?

Two, both already covered above, repeated here because they are the
report's center of gravity:

1. **The `torvalds`/embedded-C case (§10)** — a correct matcher/assessor
   rendering a *parser* gap into a flatly wrong headline number and a
   doubly-misleading "no required requirements were assessable" message
   for a textbook-strong candidate.
2. **`karpathy × frontend_01 = 80` vs. `karpathy × ml_engineering_01 =
   75`.** Both scores are arithmetically honest given what was found —
   `frontend_01`'s assessable set is small (4 required + 1 preferred),
   and `karpathy`'s one CSS-based GitHub Pages blog
   (`karpathy.github.io`) plus incidental JavaScript/TypeScript
   evidence from his analyzed repos happens to clear most of that small
   bar. Nothing here is a scoring defect — `docs/ARCHITECTURE.md` §21.9
   already documents "a small assessable denominator is legitimately
   volatile" as an accepted edge case, not a bug. It is, however, a
   genuine **interpretation risk**: a recruiter skimming only the
   headline number would see a frontend-leaning score for an ML
   specialist and a lower ML-leaning score for the same person on the
   "right" posting, from the exact same underlying evidence. Classified
   `PRESENTATION_CONFUSION`, not `ASSESSMENT_AGGREGATION_ERROR`.

## 13. Top 5 highest-value fixes (ranked by the actual results above)

| # | Fix | Impact | Frequency (this corpus) | Scope |
|---|---|---|---|---|
| 1 | **Give bare single/short-letter language names (`C`, `Go`) a safe path to be recognized in ordinary job-description prose** — not necessarily by making them README-safe everywhere, but by giving the job-description parser a narrower, context-aware allowance (e.g. "the sole technology-shaped word in a short requirement sentence" is a different risk profile than free README prose) | **HIGH** — directly caused a flat-0 score for the embedded-C posting on a true C expert (§10) | 2 of 15 postings exercise bare "C" directly (embedded_firmware, systems_cpp's OR case); any posting mentioning Go the same way is equally affected | **MEDIUM** — needs careful, narrow design per `concepts.py`'s own already-documented false-positive history; touches `jobs/parsing/concepts.py` + `alternatives.py` |
| 2 | **Fix the OR/alternative trailing-word-stripping fragility** (`_TRAILING_FILLER`'s fixed vocabulary + `clean_list_fragment`'s prefix list both miss common real phrasings) | **HIGH** — produced all 4 `WRONG_ALTERNATIVE_STRUCTURE` cases; silently wrong structure is worse than a visible miss | 4 of 15 postings (27%) | **SMALL–MEDIUM** — `jobs/parsing/alternatives.py` + `concepts.py`, isolated functions, already well-tested in isolation |
| 3 | **Fix the "React Native" / "React" alias collision** | **HIGH** when it occurs (silently conflates two different skills) | 1 of 15 postings directly; likely recurs for other substring-colliding pairs (e.g. "Vue"/future "Vuetify", "Next"/"Next.js" already handled) not otherwise exercised by this corpus | **SMALL** — one alias-safety annotation, same mechanism `readme_unsafe_aliases` already uses |
| 4 | **Add the highest-frequency missing concepts: Kubernetes, SQL (generic), Swift, Kotlin** | **HIGH** — Kubernetes alone affected 3/15 postings; Swift/Kotlin are the entire mobile-family vocabulary | Kubernetes 3/15, SQL 3/15, Swift+Kotlin 1/15 (mobile) but structurally 100% of any mobile posting | **SMALL** — pure registry additions, no logic change, mirrors how every existing concept was added |
| 5 | **Give the ranker (or a future job-aware retrieval step) a way to recover a specific named/relevant repository that falls outside the static top-N** — the `Pneumonia-Detection-Ai`/`nn-zero-to-hero`/`execa` pattern generalizes to any candidate with materially more repos than `top_n` | **MEDIUM-HIGH long-term, but requires product judgment** (job-aware retrieval is explicitly out of scope for an isolated fix — Milestone 5A's own design doc already flagged this as Stage-2 future work) | 3 of 4 real candidates evaluated (75%) | **LARGE** — this is the one item that isn't a narrow code fix; it's a design question (job-aware re-ranking, a larger top_n, or an explicit "N of M, want more?" product affordance) |

## 14. Which problems should NOT be fixed yet?

- **The generic registry-gap backlog beyond #4's top picks** (Terraform,
  Jenkins, dbt, Snowflake/BigQuery, MATLAB/Simulink, PLC, OpenCV,
  scikit-learn, React Native/Flutter, Azure/GCP, GraphQL, OAuth, CMake,
  MySQL/MongoDB outside OR context, "distributed systems"/"CI/CD"-as-
  generic-phrases). All real, all legitimate, none urgent enough to beat
  #1–4 above; batching them into one future "registry expansion"
  milestone is more efficient than fixing them piecemeal.
- **The llm.c README-over-attribution false positive (§6 item 2).** Rare
  phrasing pattern (a README crediting a third party's separate
  reimplementation by name), LOW–MEDIUM severity, and any fix risks
  tightening README matching in a way that could suppress genuine
  mentions elsewhere — needs its own small design pass, not a rushed
  patch.
- **The `karpathy × frontend_01` presentation-confusion case (§12).**
  This is a known, already-documented, ACCEPTED trade-off
  (`docs/ARCHITECTURE.md` §21.9) about small assessable denominators —
  changing it would mean revisiting 7B's scoring design itself, which is
  explicitly out of this milestone's (and arguably 8D's) scope without a
  dedicated product decision.
- **The top-N retrieval problem's actual SOLUTION (fix #5's "how").**
  The finding (repos get excluded) is solid and worth fixing; the right
  mechanism (bigger top_n? job-aware re-ranking? a "show more" UI
  affordance?) is a genuine product/architecture decision this
  evaluation should surface, not settle.

## 15. What should Milestone 8D contain?

**Recommendation** (see §13's ranked table for the "why"):

1. Fix the OR/alternative trailing-word-stripping fragility (#2 above) —
   smallest, most isolated, highest-confidence fix.
2. Fix the React Native/React alias collision (#3) — same mechanism
   already exists (`readme_unsafe_aliases`), trivial to extend.
3. Add Kubernetes, generic SQL, Swift, Kotlin to the concept registry
   (#4) — pure additive data, zero logic risk, directly unblocks the
   mobile role family entirely and meaningfully improves backend/devops/
   SRE/data coverage.
4. Design (not yet implement) a narrow, reviewed fix for bare
   short-token language names in job-description prose (#1) — this one
   needs a short design note first, given `concepts.py`'s own documented
   history of real false positives from relaxing exactly this kind of
   restriction.
5. Write up the top-N retrieval problem (#5) as its own design question
   for product review, separate from 8D's code changes — do not fold an
   architecture decision into the same milestone as small, mechanical
   fixes.

Do NOT use 8D for: alternative-role discovery, a learned/CatBoost
scorer, or any frontend redesign — none of this evaluation's findings
point there.

---

## Appendix A — Corpus & harness details

- **Jobs:** `evaluation/jobs/*.json` (15 files) + gold
  `evaluation/gold/jobs/*.json` (103 expected-requirement rows total).
- **Candidates:** 4 real, public GitHub accounts — `Jango1324` (the
  project's own existing test account, reused for continuity),
  `karpathy`, `torvalds`, `sindresorhus` (all three already used by this
  project's own prior Milestone 5D real-account validation per
  `docs/CHANGELOG_DEV.md`). Offline fixtures:
  `evaluation/fixtures/candidates/*.json`, collected ONCE each via a
  one-off ad hoc script (not part of the deliverable), persisting
  `collected_at`, `repository_ranking_version`, `evidence_schema_version`,
  and `api_request_count`. Gold evidence/ranking expectations:
  `evaluation/gold/candidates/*.json`.
- **End-to-end matrix:** `evaluation/gold/matrix.json`, 12 strategically
  selected candidate × job pairs (positive/partial/negative directional
  spread across all 4 candidates), run through the real `match_job()`/
  `assess_job()`.
- **Harness:** `scripts/evaluation_lib/` (taxonomy, loaders, parser_eval,
  evidence_eval, end_to_end_eval, report) + three entry points
  (`scripts/evaluate_job_parser.py`, `scripts/evaluate_evidence.py`,
  `scripts/evaluate_end_to_end.py`), each writing a deterministic
  JSON + Markdown report under `evaluation/reports/`. All three exit 0
  regardless of how many findings they report — only a missing/malformed
  fixture file produces a non-zero harness exit (Milestone 8C Part 18).
- **Live GitHub usage:** 4 accounts, collected once each (one account —
  `karpathy` — was re-collected a second time after an ad hoc collector
  script bug, described in the completion report, was fixed; all four
  were then re-collected together for consistency). Total ≈588 API
  requests across the whole milestone, well inside the 5,000/hour
  authenticated budget. Zero live calls are made by the automated test
  suite or by any `scripts/evaluate_*.py` run — every one of those reads
  only the persisted fixtures.

## Appendix B — Fairness/privacy note

Every candidate-evidence finding in this report is a statement about
*technical repository evidence only* (languages, dependencies, README
mentions, repository counts) — never a judgment of the person. No
protected characteristic, personality trait, or "good/bad
engineer"/"hire"/"reject" label was inferred or recorded for any of the
four public accounts evaluated, per Milestone 8C Part 21.
