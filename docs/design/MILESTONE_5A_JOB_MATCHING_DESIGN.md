# GitScore AI — Milestone 5A: Job-Description-Driven Candidate Matching

> **STATUS: DRAFT — ARCHITECTURE PROPOSAL ONLY.**
> Nothing in this document has been implemented. No production code,
> database schema, scoring rubric, or feature-extraction logic has been
> changed. No GitHub users were collected while writing this. This file
> is additive documentation under `docs/design/` and does not alter
> `docs/ARCHITECTURE.md`, `docs/PIPELINE.md`, `docs/ML_NOTES.md`, or
> `docs/CHANGELOG_DEV.md`, which remain the record of the shipped V1
> system. Written against the codebase as of Milestone 4.5 (231 tests
> passing, Dataset V1 pilot complete, no CatBoost, no UI).

---

## 1. Executive Summary

GitScore is pivoting from a **universal ML-readiness score** (`GitHub
username → 0–100`) to a **contextual job-match engine**
(`GitHub username + job description → match report`). Milestone 4.5's
pilot gave the concrete evidence for why: the V1 rubric produces a
compressed, saturating distribution (17/18 pilot scores in 60–92) and
has no way to express that the *same* profile is a strong backend
candidate and a weak embedded candidate — it only has one number.

The proposed architecture keeps everything that already works
(GitHub API layer, pagination/retry/rate-limit handling, the
parse → extract → persist shape) and replaces the *aggregation and
scoring* layer with three new concepts:

1. A **Candidate Evidence Profile** — a structured, provenance-backed
   record of what a GitHub account demonstrates, at the concept level
   (`PyTorch`, `PostgreSQL`, `I2C`, ...), not a single feature vector.
2. A **Job Requirement Profile** — a structured extraction of what a
   pasted job description actually asks for, with each requirement
   tagged by importance and by whether GitHub can plausibly prove it.
3. A **deterministic Matching Engine** that compares the two and
   produces an explainable, evidence-cited match score — never a
   black-box number.

V1 (`readiness_score`, Dataset V1, `SCORING_RUBRIC_VERSION=1`) is not
deleted or reinterpreted. It becomes a frozen historical baseline.

---

## 2. Product Definition

**Old product:** GitHub username → one portfolio-readiness score,
implicitly ML-flavored, permanent per candidate.

**New product:** GitHub username + job description → a per-job match
report: overall score, matched/weak/missing requirements with cited
evidence, strongest supporting repositories, and (secondary) alternative
role suggestions where the same evidence scores better.

The job description is the primary source of truth for what "good"
means in a given run. The system must not be built around a fixed list
of role names — it must work for job descriptions the developers never
saw, by reasoning over technical **concepts** extracted from free text,
not over hardcoded role categories.

---

## 3. Why the V1 Universal Readiness Model No Longer Fits

Direct evidence from the Milestone 4.5 pilot (n=18, real GitHub accounts,
current rubric, current feature extraction — no bugs found in either):

| Finding | Value | Implication |
|---|---|---|
| Score range | min 43, median 82.5, mean 78.61, max 92 | 17/18 accounts land in a 30-point band — a single scalar can't discriminate role fit |
| Documentation Quality at ceiling | 14/18 | 78% of accounts get identical marks on a 15-point axis |
| Community Signal at ceiling | 17/18 | 94% identical on a 10-point axis |
| ML Experience at ceiling | 8/18 | Saturates well before distinguishing "10 real ML repos" from "242 real ML repos" |
| Language/Tool Relevance | never exceeds 14/20 in the pilot | 6 of 20 points structurally unreachable (`has_huggingface`/`has_catboost` never fired) |
| `Jango1324` = 71/100 | correct rubric arithmetic, verified by hand | ML axis rewards naming a repo `*-ai` as much as doing ML work |
| `bradtraversy` ML Experience = 30/35 | 8 of 328 repos (2.4%) keyword-matched, 7 of those 8 are non-ML tooling/tutorial repos | an *absolute* repo-count threshold is trivially cleared by volume alone, independent of relevance |

None of this is a bug to patch. It is evidence that **"ML-readiness" is
the wrong universal axis** — a candidate's GitHub evidence is not
inherently strong or weak; it is strong or weak *relative to a specific
set of requirements*. The same profile that produces a mediocre "ML
readiness" number might be an excellent match for a backend role that
never asked for ML at all, and the V1 rubric has no way to say that.
Moving to contextual matching doesn't fix the V1 numbers — it makes the
question the numbers were trying to answer obsolete.

---

## 4. Current Architecture Review

Classification per actual inspected file, five buckets as requested.

| Component | Classification | Notes |
|---|---|---|
| `github/client.py` | **1. Reusable as-is** | Pagination, bounded retry/backoff, `GitHubRateLimitError`/`GitHubNotFoundError`/`GitHubRequestError` split, thread-per-worker session model. Nothing about it is V1-specific; the new engine calls the same client for the same endpoints. |
| `github/exceptions.py` | **1. Reusable as-is** | Same reasoning. |
| `github/parser.py` | **2. Reusable with modification** | `parse_repo()` already captures `is_fork`, `created_at`, `updated_at`, `html_url`, and per-repo language **percentages** (not just presence) — genuinely useful for ranking and evidence, but currently thrown away downstream. Needs additions that cost **zero extra API calls** because they're already in the same repo-list payload: `archived`, `size` (KB), `topics`, `pushed_at` (a better "last real activity" signal than `updated_at`, which also bumps on stars/issues), `default_branch`. |
| `features/activity.py`, `languages.py`, `quality.py` | **2. Reusable with modification** | The *aggregation* pattern (one flat count across all repos) doesn't fit a per-repo, per-concept Evidence model, but the underlying signals (fork ratio, per-repo language mix, description presence) are legitimate low-level detectors to re-wrap as Evidence emitters. |
| `features/ml.py` | **2. Reusable with modification** | `ML_KEYWORDS` + the word-boundary regex approach (`_KEYWORD_PATTERNS`) is a solid *pattern* for concept detection from text — generalize it into a concept-keyed detector table instead of one ML-specific list, and stop treating "keyword in name/description" as the ceiling of evidence (see Part 7 — it should be the *weakest* evidence tier, not the only one). |
| `features/readme.py` | **2. Reusable with modification** | Same reasoning; its section-keyword lists (`installation_keywords`, `demo_keywords`, etc.) become one input into project-quality signals (Part 8), not a documentation *score*. |
| `features/profile.py` (aggregator) | **4. Should eventually be deprecated** | Superseded by the Evidence pipeline for new analyses; keep only to keep V1 collection runnable. |
| `scoring/readiness.py` | **3. Useful historical baseline** | Frozen. Not extended, not called by the new matcher — it answers a different question (universal readiness) than the new matcher answers (job-conditional fit). Kept for `docs/ML_NOTES.md`'s own reasons and as a regression reference. |
| `db/database.py`, `db/models.py` (`User`, `ProfileFeature`) | **1. Reusable as-is (additive)** | Engine/session/`Base` setup is fine unchanged. New ORM models are added *alongside* `User`/`ProfileFeature` in the same file or a sibling module — those two classes are not touched. |
| `db/queries.py` | **2. Reusable with modification** | Existing functions (`save_user`, `save_profile_features`) stay; new query functions are additive, not rewrites. |
| `pipeline/analyze.py` | **2. Reusable with modification** | The orchestration *shape* — fetch → transform → persist, with `ThreadPoolExecutor` for repo-level concurrency — is exactly right. Steps 2+ change from "extract 30 aggregate features" to "rank repos → deep-fetch top N → extract Evidence per repo." |
| `dataset/schema.py`, `builder.py`, `report.py`, `export.py` | **3. Useful historical baseline** | Entirely V1-specific (keyed to the frozen 30-column contract and `readiness_score`). The *pattern* — an explicit schema contract module, versioned constants, a `validate_frame`-style guard, deterministic export — is worth replicating for the new Evidence/Match schemas (see Part 21, milestone 5C). |
| `dataset/collection_input.py` | **1. Reusable as-is** | Username-file parsing is orthogonal to scoring; used unchanged by any future batch collection. |
| `scripts/collect_user.py`, `collect_dataset.py` | **1. Reusable as-is** | Keep for maintaining/extending the V1 baseline if ever needed. New scripts are added for the new pipeline, not replacements. |
| `scripts/collect_pilot.py` (Milestone 4.5 pilot script) | **3. Useful historical baseline / candidate for promotion** | Its rate-limit-aware throttle-and-resume logic is genuinely reusable collection infrastructure and is a strong candidate to be promoted into whatever new orchestration script is built — flagged here, not yet done. |
| `tests/*` | **1. Reusable as-is** | Regression protection for everything kept; new modules get new test files following the same offline-fakes convention (`tests/conftest.py`). |
| `docs/ARCHITECTURE.md`, `PIPELINE.md`, `ML_NOTES.md`, `CHANGELOG_DEV.md` | **3. Useful historical baseline** | Stay as the accurate record of the V1 system. This design doc is additive. |
| Evidence storage (per-repo, per-concept) | **5. Entirely new subsystem required** | **Critical gap**: nothing today persists anything at repository granularity. `ProfileFeature` is a pre-aggregated snapshot; the moment `analyze_user()` returns, per-repo detail is gone. Explainability ("which repo proves PostgreSQL?") is structurally impossible without a new `Repository`/`Evidence` layer. |
| Job parsing / matching / concepts | **5. Entirely new subsystem required** | Does not exist in any form today. |

**Important reassurance, per your instruction:** none of the current ML
features (`has_pytorch`, `ml_repository_count`, etc.) need to be
deleted. They become **one detector among many** feeding a generic
`Concept: PyTorch` node in the new model, on equal footing with
`Concept: PostgreSQL` or `Concept: FreeRTOS` — "ML" stops being a
privileged axis and becomes one category of concept like any other.

---

## 5. Reusable Existing Components (Summary)

Kept unchanged, called by both old and new pipelines:
`github/client.py`, `github/exceptions.py`, `db/database.py`,
`dataset/collection_input.py`, all existing tests, `scripts/collect_user.py`,
`scripts/collect_dataset.py`.

Kept unchanged, used only by the frozen V1 path:
`scoring/readiness.py`, `features/profile.py`, `dataset/schema.py` +
`builder.py` + `report.py` + `export.py`.

Adapted (same file, extended) for the new pipeline:
`github/parser.py` (new fields, zero new API cost), `pipeline/analyze.py`
(new orchestration steps), `db/models.py`/`db/queries.py` (additive new
tables/functions).

Net effect: **the expensive, hard-won infrastructure (rate limits,
retries, pagination, thread-safety, dedup-by-snapshot pattern) survives
the pivot entirely.** The pivot replaces the *aggregation and scoring*
layer, not the *collection* layer.

---

## 6. Candidate Evidence Profile

A flat feature vector (today's `ProfileFeature`) cannot represent "this
candidate has strong evidence of PostgreSQL in one repo and weak evidence
of Docker in another." The new profile is a graph of **concepts**, each
backed by one or more **Evidence** records (Part 7), computed per
candidate and reusable across every job it is later matched against
(the expensive part — GitHub collection and evidence extraction — is
job-independent and done once; matching against a specific JD is cheap
and repeatable).

Conceptual shape (illustrative, not a final ORM definition):

```
CandidateEvidenceProfile
├── candidate_id            # -> Candidate (renamed/aliased User)
├── collected_at            # snapshot time, same append-only pattern as ProfileFeature
├── evidence_schema_version
├── repositories: [RepositorySummary]        # ranked, see Part 9
│     ├── repo_id, name, is_original, archived, size_kb,
│     │   primary_language, languages: {lang: pct}, pushed_at,
│     │   stars, forks, description, readme_present,
│     │   quality_signals: RepositoryQualitySignals   # Part 8
│     └── analyzed: bool     # was this repo deep-analyzed or only listed?
├── concepts: {concept_id -> CandidateConceptSummary}   # Part 8's aggregate
│     e.g. "framework.pytorch" -> {
│         best_confidence: 0.9,
│         evidence_count: 3,
│         distinct_repo_count: 2,
│         evidence_type_diversity: {"dependency_manifest", "source_import"},
│         last_seen: "2024-11-02",
│         evidence_ids: [...]                 # -> Evidence table, Part 7
│     }
└── coverage_meta
      ├── total_repos_listed
      ├── total_repos_analyzed        # N from ranking, Part 9
      └── analysis_completeness: "full" | "partial"   # feeds confidence, Part 16/20
```

Why not one flat vector: a job matcher needs to ask "does this concept
have *strong* evidence" per concept, independently, for an arbitrary set
of concepts chosen at match time (from whatever job description was
pasted) — that is a lookup into `concepts{}`, not a query over 30 fixed
columns. The `coverage_meta` block is what lets the explanation layer
say "we could only deep-analyze 15 of your 1,140 repositories" instead
of silently pretending full coverage.

---

## 7. Evidence Provenance Model

This is the load-bearing structure for the whole redesign — every
number the product ever shows a recruiter must trace back to one or more
of these rows.

```
Evidence
├── evidence_id
├── candidate_id
├── repository_id                 # -> Repository (new table, Part 17)
├── file_path                     # nullable — e.g. null for repo-language-stats evidence
├── evidence_type                 # enum, see below
├── raw_observation                # the actual matched text/line, verbatim
├── matched_concept_id             # -> Concept (Part 8)
├── normalization_confidence       # how sure the alias resolver was (Part 8)
├── evidence_confidence            # this evidence's own strength (Part 7 ladder), independent of normalization confidence
├── extractor_version               # which detector produced this (versioning, Part 18)
├── collected_at
```

`evidence_type` enum (extensible — adding a new source is a new enum
value + one new detector, not a schema change):

| evidence_type | Example raw_observation | Source |
|---|---|---|
| `repo_language_stats` | `"Python: 62%"` | GitHub languages API (already fetched) |
| `repo_topic` | `"topics: ['machine-learning']"` | repo metadata (already fetched, currently unused) |
| `readme_text` | `"...built with PostgreSQL..."` | README (already fetched) |
| `dependency_manifest` | `requirements.txt: "torch==2.1.0"` | new fetch, Part 10 |
| `config_file` | `Dockerfile FROM python:3.11` | new fetch, Part 10 |
| `ci_workflow` | `.github/workflows/ci.yml: "pytest"` | new fetch, Part 10 |
| `source_import` | `train.py: "import torch"` | new fetch, Part 10 |
| `test_evidence` | file under `tests/` importing the same concept | new fetch, Part 10 |
| `notebook` | `.ipynb` cell importing `sklearn` | new fetch, Part 10 |
| `release_metadata` | tagged release exists | repo metadata |

Worked example matching the prompt's format:

```
Evidence {
  repository: "pneumonia-classifier",
  file_path: "requirements.txt",
  evidence_type: "dependency_manifest",
  raw_observation: "torch==2.1.0",
  matched_concept_id: "ml.framework.pytorch",
  evidence_confidence: 0.7,
  extractor_version: "manifest-detector@1"
}
Evidence {
  repository: "pneumonia-classifier",
  file_path: "src/train.py",
  evidence_type: "source_import",
  raw_observation: "import torch",
  matched_concept_id: "ml.framework.pytorch",
  evidence_confidence: 0.85,
  extractor_version: "python-import-detector@1"
}
```

`CandidateConceptSummary.best_confidence` for `ml.framework.pytorch`
would combine these two (Part 7's combination rule), not just take one.

**Why provenance matters concretely, per the prompt's list:**
- *Explainability*: the recruiter-facing report (Part 14) is a direct
  render of `Evidence` rows grouped by concept — there is no separate
  "explanation generation" step that could drift from what was actually
  found.
- *Debugging*: when a candidate disputes a result ("I use PostgreSQL
  every day"), you inspect their `Evidence` rows and find either a real
  gap (no manifest/import evidence — the account genuinely doesn't show
  it) or an extractor bug (a detector missed a valid file) — the two
  are distinguishable, which they are not in today's aggregate-only model.
- *Scoring*: the matcher (Part 6) operates on `CandidateConceptSummary`
  aggregates, not on raw text, so scoring stays deterministic while
  still being traceable back to source rows on demand.
- *Recruiter reports*: Part 14's report is literally a query over this
  table, grouped and filtered by the job's requirement concepts.
- *Future model training*: if a supervised signal is ever added
  (recruiter feedback, interview outcomes), `Evidence` is a far richer,
  leakage-auditable feature source than 30 pre-aggregated columns — you
  can construct arbitrary aggregates later without re-collecting.

---

## 8. Concept Normalization / Technical Knowledge Model

**Canonical concept, not free text, is what Evidence and Requirements
key on.**

```
Concept
├── concept_id        # stable, dotted namespace, never reused/deleted once shipped
│                      # e.g. "language.python", "database.postgresql",
│                      #      "ml.framework.pytorch", "embedded.protocol.i2c",
│                      #      "embedded.rtos.freertos"
├── display_name       # "PostgreSQL"
├── category            # one of an extensible category list (Part 6 of the prompt's
│                        #  candidate-profile categories) — a classification tag, not a
│                        #  constraint on which concepts can exist
├── aliases: [str]      # ["Postgres", "PostgreSQL", "psql"]  (case/punct-insensitive match)
├── parent_id: str|null # optional hierarchy, e.g. "ml.framework.pytorch" parent
│                        #  could be "category.ml_framework"
├── related_ids: [str]  # non-hierarchical links, e.g. postgresql <-> sqlalchemy
├── status               # "active" | "deprecated_merged_into:<id>"  (append-only)
└── registry_version     # CONCEPT_REGISTRY_VERSION this entry was added/changed under
```

**Mechanism, not a finished ontology** (per the instruction not to build
the whole ontology now):

1. **Storage:** a versioned, human-reviewable **config file** (YAML/JSON
   under `src/gitscore/concepts/registry/`), not a database table, for
   the same reason the project already keeps `ML_KEYWORDS` as a Python
   list rather than DB rows: it changes rarely, benefits from code
   review/diffing, and must never silently disappear mid-analysis. A DB
   mirror can be added later purely for admin-UI curation without
   changing the source of truth.
2. **Resolution algorithm**, applied both to repo-text matching and to
   job-description term extraction:
   - normalize case/punctuation, exact-match against `aliases`;
   - if no match, attempt a conservative fuzzy/substring match (e.g.
     `"react.js"` → `react`) with a lower `normalization_confidence`;
   - if still no match, emit a **provisional concept** —
     `concept_id = "provisional:<slug>"`, flagged for curation, *never
     silently dropped and never silently invented as a real concept*.
     This is exactly what lets an unanticipated job ("GPU Kernel
     Engineer" asking for "warp-level primitives") degrade gracefully
     instead of crashing or ignoring the term.
3. **Versioning:** `CONCEPT_REGISTRY_VERSION` bumps on any add/rename/merge;
   `concept_id`s are never deleted, only marked `deprecated_merged_into`,
   so historical `Evidence`/`Requirement` rows always resolve.
4. **Hierarchy is optional per concept**, not mandatory — most concepts
   (e.g. `language.rust`) need no parent; hierarchy exists only where it
   adds value (grouping `embedded.rtos.*` for role-archetype matching,
   Part 12).

This directly generalizes the current codebase's only existing
normalization instinct — `ML_KEYWORDS` — from one hardcoded, ML-only
list into a registry mechanism that covers every category in the
prompt's list (and any category not anticipated).

---

## 9. Job Requirement Profile

Primary MVP input is pasted plain text; the *parsed* output is this
structured object (parsing mechanism is Part 15's LLM boundary — this
section is only the schema).

```
JobRequirementProfile
├── job_id
├── raw_text                     # verbatim pasted text, kept for provenance/re-parsing
├── role_title_extracted           # best-effort, informational only — NOT used to select a scoring branch
├── role_family_inferred: str|null # optional, e.g. for archetype comparison (Part 12), never required
├── seniority_signal: str|null     # e.g. "senior" if stated; unreliable, low weight
├── job_parser_version
└── requirements: [Requirement]

Requirement
├── requirement_id
├── original_text                  # verbatim span from the JD
├── source_span: (start, end)      # offsets into raw_text, for UI highlighting later
├── normalized_concept_id           # -> Concept, or "provisional:<slug>"
├── requirement_type                # "required" | "preferred" | "responsibility" | "nice_to_have"
├── category                        # mirrors Concept.category when resolvable
├── github_observable                # "yes" | "weak" | "no"
├── extraction_confidence            # how sure the parser is this is a real, distinct requirement
```

Worked examples matching the prompt exactly:

```
Requirement {
  original_text: "Experience with PostgreSQL",
  normalized_concept_id: "database.postgresql",
  requirement_type: "required",
  category: "database",
  github_observable: "yes"
}
Requirement {
  original_text: "Strong communication skills",
  normalized_concept_id: "provisional:communication_skills",
  requirement_type: "required",
  category: "soft_skill",
  github_observable: "no"
}
```

`github_observable` is not decorative — the matcher (Part 6) excludes
`"no"` requirements from the score's denominator entirely and lists them
in a separate "could not be evaluated from GitHub" section, so the
product never implies GitHub can prove communication skills, seniority,
or years of experience. `"weak"` (e.g. "system design experience" —
partially inferable from architecture/scale of repos, but not reliably)
is included in scoring at a reduced weight and always annotated.

---

## 10. Arbitrary Job Support

The matcher is **concept-driven, never role-name-driven**, by
construction: nothing in the pipeline branches on `role_title`. The flow
for any job description, anticipated or not, is always the same four
steps:

```
raw JD text
   → extract candidate requirement phrases (LLM-assisted, Part 15)
   → normalize each phrase to a concept_id (Part 8's resolver;
      unknown terms become provisional concepts, not dropped)
   → look up each concept_id in the candidate's CandidateConceptSummary
   → aggregate into a MatchResult (Part 6) — same code path regardless
      of which concepts were involved
```

Worked through the prompt's five unanticipated examples — no new code
per row, only registry entries (some already implied by categories the
prompt lists, some genuinely new and handled via the provisional-concept
path until curated):

| Job | Requirement phrases → concepts | Handled by |
|---|---|---|
| GPU Kernel Engineer | CUDA→`platform.cuda`, C++→`language.cpp`, "performance profiling"→`practice.perf_profiling`, "parallel computing"→`practice.parallel_computing` | existing categories (language, platform) + new practice-category concepts, same resolver |
| FPGA Signal Processing Engineer | Verilog/VHDL→`hdl.verilog`/`hdl.vhdl`, "FPGA tooling"→provisional until a specific tool is named, DSP→`domain.dsp`, "simulation"→`practice.hw_simulation` | new `hdl.*` and `domain.*` category namespace — additive registry entries, no matcher change |
| Robotics Software Engineer | C++, ROS2→`robotics.ros2`, SLAM→`domain.slam`, "sensor fusion"→`domain.sensor_fusion`, Linux→`os.linux` | same |
| Compiler Engineer | C++, LLVM→`toolchain.llvm`, "compilers"→`domain.compilers`, "optimization"→`practice.optimization`, "systems programming"→`domain.systems_programming` | same |
| Security Automation Engineer | Python, Linux, "security tooling"→provisional/`domain.security_tooling`, "automation"→`practice.automation`, CI/CD→`infra.ci_cd` | same |

The only thing that ever needs to be added for a genuinely new domain is
**registry entries** (Part 8) and, for concepts with no existing
detector coverage, a **new low-level detector** (Part 12 of the prompt /
Part 11 of this doc — e.g. a `.v`/`.sv` file-extension detector for
Verilog). Neither requires touching the matching engine.

---

## 11. Repository Ranking Strategy

> **Milestone 5B update (2026-09-11):** this section's proposal was
> implemented in isolation (repository ranking only — no evidence
> persistence, no matching) and validated against 7 real accounts
> spanning 13 to 1,140 repositories. **N=15 is confirmed as the
> default**, based on measured score drop-off (steep for small
> accounts, gentle-to-flat for large ones) and a measured 93.9% API-cost
> reduction across the validation accounts (`sindresorhus`: 2,293 → 43
> calls). See `docs/CHANGELOG_DEV.md`'s Milestone 5B entry and
> `docs/ARCHITECTURE.md` §13 for the implementation, formula, and known
> limitations (notably: the optional Stage-2 relevance boost cannot
> rescue a repository Stage 1 scores as trivial — observed on
> `Jango1324`'s one genuine ML-relevant repository, which stayed
> ranked 16th of 20 even with an ML-flavored relevance boost applied).
> Everything below is the original Milestone 5A proposal, unchanged.

**The core scalability fix.** Milestone 4.5 measured this directly:
`sindresorhus` (1,140 repos) alone consumed ~34% of the entire 18-account
pilot's ~6,740 API calls, at 2 calls/repo (languages + README) with zero
caching or ranking. Deep analysis must not be O(total repos).

**Two-stage design, matching the prompt's Option C:**

- **Stage 1 — job-independent "substantiveness" ranking.** Computed
  entirely from data the app **already fetches** in the initial repo
  listing (`GET /users/{u}/repos` — zero additional API calls):
  not-a-fork (or: fork with a materially different description, a weak
  proxy for "meaningfully modified"), not archived, `size_kb` above a
  small floor (filters out empty/placeholder repos), `pushed_at`
  recency, presence of a description, a known primary language. Produces
  a ranked list of "real, substantial work" independent of any job.
- **Stage 2 — job-aware boost.** Cheap keyword overlap between each
  repo's `name` + `description` + `primary_language`/`topics` (all
  already in hand from Stage 1, still zero new calls) and the concepts
  extracted from the submitted JD. Re-ranks Stage 1's list, does not
  replace it — a repo with strong Stage-1 substantiveness never drops out
  entirely just because it doesn't mention the target job's keywords; it
  is boosted, not gated.
- **Deep analysis** (README fetch, manifest-file fetch, Part 12) runs
  only on the **top N** repos from the boosted ranking.

**Default N = 15**, with a floor rule: if a candidate has ≤ 15 original
repos (true for the majority of accounts, including every "ordinary"
account examined in the pilot design work — `Jango1324` has 15 original
repos exactly), analyze all of them; N only truncates accounts *above*
that size. Justification:
- Cost becomes **O(N), not O(total repos)**: every account now costs
  roughly the same regardless of whether it has 20 or 1,140 repos,
  directly eliminating the `sindresorhus` 34%-of-cost problem.
- 15 is large enough that for a normal, non-spammy portfolio it likely
  *is* the full substantive repo set (the pilot's original-repo median,
  excluding the handful of 100+-repo outliers, was well under 15 for most
  accounts).
- 15 is small enough to keep deep-analysis cost per account bounded and
  predictable (roughly 15 × ~3–4 calls ≈ 45–60 calls/account for
  MVP-scope manifest detectors, vs. up to ~2,300 for a `sindresorhus`-scale
  account today).
- It is a config constant, not a structural limit — trivially tunable
  after real usage data, and the `coverage_meta.analysis_completeness`
  field (Part 6) ensures the product is always honest about whether N
  was a real constraint for a given candidate.

**Why two stages, not job-independent-only or job-aware-only:**
job-independent-only risks missing a candidate's most job-relevant work
if it happens to rank outside the top N on generic substantiveness alone
(e.g. a small but perfectly on-target side project). Job-aware-only
risks rewarding **repository spam that happens to mention the right
keyword** (exactly the `bradtraversy`/`ai-keyword-extractor`-style
false-positive pattern already observed) over genuinely substantial
unrelated work, and would need to re-rank from scratch for every job
against every candidate repo, discarding the job-independent profile
reuse described in Part 6. The two-stage design keeps Stage 1's ranking
(and the deep evidence extracted from it) **cacheable and reusable
across every job the candidate is later matched against**, while still
letting Stage 2 tune *which* of the substantial repos get the deepest
look for a specific job.

---

## 12. Deep Evidence Extraction Strategy

Evaluated per the prompt's list. "MVP" = Milestone 5D/6A scope (Part 21).

| Source | Info value | Reliability | False-positive risk | Cost | MVP? | Confidence contribution |
|---|---|---|---|---|---|---|
| `requirements.txt` / `pyproject.toml` / `Pipfile` / `environment.yml` | High (Python deps) | High | Low (pinned/declared, rarely accidental) | 1 file fetch/repo | **Yes** | `dependency_manifest`, moderate-high |
| `package.json` (+ lockfiles as a secondary confirm) | High (JS/TS deps) | High | Low | 1 fetch (+1 optional) | **Yes** | `dependency_manifest`, moderate-high |
| `setup.py` | Medium (older Python packaging) | Medium (harder to parse reliably than `pyproject.toml`) | Low-medium | 1 fetch | Yes, best-effort regex only | moderate |
| `pom.xml` / `build.gradle` (Java) | High | High | Low | 1 fetch | Post-MVP (adds a language ecosystem, not core to first slice) | moderate-high |
| `Cargo.toml` (Rust), `go.mod` (Go) | High | High | Low | 1 fetch | Post-MVP | moderate-high |
| `CMakeLists.txt` / `Makefile` | Medium (signals C/C++/build complexity, not specific libs reliably) | Medium | Medium (free-form) | 1 fetch | Post-MVP | low-moderate |
| `Dockerfile` | High (base image, exposed services) | High | Low | 1 fetch | **Yes** | `config_file`, moderate |
| `docker-compose.yml` | High (multi-service architecture, e.g. Postgres/Redis sidecars) | High | Low | 1 fetch | Yes (bundled with Dockerfile detector) | moderate |
| `.github/workflows/*.yml` | Medium-high (test/deploy practices, CI tooling) | High | Low | 1 fetch (dir listing + files) | Post-MVP (valuable but adds a directory-listing call pattern) | moderate |
| Notebooks (`.ipynb`) | High for data/ML roles | Medium (import cells easy to find; execution/output claims are not verifiable this way) | Medium | 1 fetch/notebook (can be large) | Post-MVP | moderate, capped below source-code confidence |
| Source imports (`import torch`, `#include <...>`) | Highest (proof of actual usage, not just declared intent) | High | Low | requires fetching source files, not just manifests — highest cost | Post-MVP (5D-plus once manifest detectors are proven) | high |
| Test directories | High (signals real usage + quality, not just a dependency listed and never used) | Medium | Low | requires directory listing + file fetch | Post-MVP | high, when concept also appears in test code |
| Deployment config / IaC (Terraform, k8s manifests) | High for infra roles | Medium (declares intent, doesn't prove it runs) | Medium | 1+ fetch | Post-MVP | moderate |
| Embedded/HDL files (`.ino`, `.v`, `.sv`, platformio.ini) | High for embedded/FPGA roles | High (file extension is nearly unambiguous) | Low | 1 fetch or even just filename from a tree listing | Post-MVP, but cheap and high-value — good 5D-plus candidate | moderate-high |

**MVP boundary (Milestone 5D):** manifest files only
(`requirements.txt`, `pyproject.toml`, `Pipfile`, `environment.yml`,
`package.json`) plus `Dockerfile`/`docker-compose.yml` and the
already-fetched README/language-stats sources. This covers the highest
info-value, lowest-false-positive, lowest-marginal-cost tier (1 extra
fetch per file, only for the top-N ranked repos) and lets the matcher
ship without needing a source-file-walking capability yet. Source
imports, tests, and CI workflows are explicitly **post-MVP** — they
require either directory-tree traversal or larger file fetches, and their
information gain over manifests is real but secondary to first proving
the ranking + evidence + matching loop end-to-end.

---

## 13. Evidence Strength / Confidence Model

A **general, domain-agnostic ladder** keyed by `evidence_type`, not by
concept — the same table applies whether the concept is `PyTorch`,
`PostgreSQL`, or `FreeRTOS`; only the *detectors* that produce each
`evidence_type` differ per concept/domain.

| Tier | `evidence_type` | Base confidence | Rationale |
|---|---|---|---|
| Weakest | `repo_language_stats`, `repo_topic`, `readme_text` | 0.30–0.40 | Declares presence/intent; today's entire V1 signal set lives here |
| Moderate | `dependency_manifest`, `config_file` | 0.50–0.60 | Declares an actual, buildable dependency or deployment artifact |
| Strong | `source_import`, `notebook` import cell | 0.70–0.80 | Proves the code actually references the concept, not just declares intent |
| Strongest | `test_evidence` (concept used in both implementation and tests) | 0.80–0.90 | Proves sustained, verifiable usage |

**Combination rule** (per candidate × concept, across possibly many
Evidence rows):
- Start from the single highest-tier evidence's base confidence.
- Add a small, capped bonus for **evidence-type diversity within the
  same repository** (e.g. manifest *and* import for the same concept in
  the same repo) — corroboration, not repetition.
- Add a small, **logarithmically diminishing** bonus for the concept
  appearing across **multiple distinct repositories** (`log(1 + n)`
  scaled, capped) — this is exactly the mechanism that prevents
  repository-count spam from inflating confidence linearly (see Part 6).
- Cap combined confidence at 0.95 — determinism, not false certainty;
  GitHub evidence is never proof of on-the-job proficiency (Part 22).

Backend example from the prompt, mapped onto this same ladder:
`README mentions PostgreSQL` (weak, `readme_text`, ~0.35) <
`postgres/psycopg2 dependency exists` (moderate, `dependency_manifest`,
~0.55) < `migrations/schema files exist` (`config_file`-class evidence,
~0.6) < `application source imports/uses the DB client` (`source_import`,
~0.75) — the same shape as the ML example in the prompt, driven by the
same generic table.

---

## 14. Project Quality Model

**Kept explicitly separate from evidence confidence and from the match
score's concept-coverage terms** — quality signals act as a *modifier*
(on ranking, Part 11, and as a small evidence-confidence adjustment), not
as their own scored category, to avoid resurrecting "popularity = skill"
in a new form.

| Signal | MVP? | Role |
|---|---|---|
| Original vs. fork | **Yes** | Stage-1 ranking input (Part 11); forks are not excluded but are heavily deprioritized |
| Recent activity (`pushed_at`) | **Yes** | Stage-1 ranking input; already-fetched field, zero new cost |
| Repository size (non-trivial) | **Yes** | Stage-1 ranking input; filters placeholder/empty repos |
| Meaningful source structure (more than a single trivial file) | Partial — approximated by `size_kb` + language-stats presence for MVP; a real "is this substantial" check needs a tree listing, deferred | Ranking |
| Tests present | Post-MVP (Part 12's test-evidence tier) | Evidence-confidence boost |
| CI present | Post-MVP | Evidence-confidence boost, minor project-quality signal |
| Releases / tags | Post-MVP | Minor project-quality signal (signals a "shipped," not just "started," project) |
| Documentation (README section coverage) | **Yes, but reframed** | Feeds Evidence confidence for *documentation-adjacent* requirements only (e.g. a JD asking for "clear technical writing"), not a universal score category |
| Archived status | **Yes** | Stage-1 ranking exclusion/deprioritization; zero new cost (already in the repo-list payload) |
| License | Post-MVP | Very minor signal; not proof of anything technical |
| Stars/forks | **Yes, but capped and secondary** | Included as a small tiebreaker/corroboration signal only, explicitly **not** a coverage or confidence driver — directly answers "avoid popularity = skill" and "don't reward repository spam" |
| Issue/PR activity | Post-MVP (requires additional API calls per repo) | Collaboration-signal category, not technical-fit |
| Reproducibility (does it actually run) | Out of scope indefinitely | Would require code execution, explicitly outside this product's stated boundaries (README: "no code execution") |

---

## 15. Deterministic Job Matching Engine

**No black-box ML for the primary MVP matcher** — a rules/formula engine
over `CandidateConceptSummary` × `JobRequirementProfile`, fully
inspectable, matching the project's existing "rule-based, explainable"
philosophy (`scoring/readiness.py`'s own design intent, just applied to
a contextual instead of universal target).

### 15.1 Per-requirement match

For each `Requirement` with `github_observable != "no"`:

```
requirement_score =
    0                                   if concept not found in candidate profile
    evidence_confidence * depth_factor  if found

depth_factor = min(1.0, 0.5 + 0.5 * log(1 + distinct_repo_count) / log(1 + REPO_DEPTH_CAP))
```

`REPO_DEPTH_CAP` (e.g. 5) is the point beyond which additional
repositories showing the same concept stop adding much — this is the
formula-level enforcement of "don't reward repository spam": a
candidate with 100 shallow repos mentioning a concept gets, at most, the
same `depth_factor` ceiling as a candidate with `REPO_DEPTH_CAP` solid
repos, and a candidate with **one very strong** repo (high
`evidence_confidence` from `source_import`/`test_evidence`) can already
score close to the ceiling without needing repo count at all.

### 15.2 Aggregate coverage

```
required_coverage  = Σ(requirement_score * importance_weight) / Σ(importance_weight)   over required requirements
preferred_coverage = same formula                                                       over preferred requirements
```

### 15.3 Overall match score, with an explicit anti-"just sum points" gate

```
overall_match = 100 * (
    W_REQUIRED  * required_coverage +
    W_PREFERRED * preferred_coverage
)

# Hard ceiling gate — models "missing half your required stack caps you,
# no amount of preferred-skill strength buys it back":
required_presence_ratio = (# required concepts with ANY evidence) / (# required concepts total)
if required_presence_ratio < REQUIRED_PRESENCE_FLOOR (e.g. 0.5):
    overall_match = min(overall_match, HARD_CEILING)   # e.g. 50
```

`W_REQUIRED` / `W_PREFERRED` (illustrative starting point, e.g. 0.8/0.2 —
**explicitly marked as an assumption to calibrate, not a derived
constant**) and the gate thresholds are config, versioned under
`MATCHER_VERSION` (Part 20), never hardcoded inline the way `readiness.py`'s
ladders currently are — a lesson directly taken from how hard V1's
if/elif thresholds turned out to be to reason about after the fact.

### 15.4 Output shape

```
MatchResult
├── candidate_id, job_id, matcher_version
├── overall_match: float
├── required_coverage, preferred_coverage
├── requirement_results: [RequirementMatch]
│     ├── requirement_id, status (Part 16), requirement_score,
│     │   contributing_evidence_ids, explanation_text (LLM layer, Part 19)
├── unscored_requirements: [Requirement]   # github_observable == "no"
├── strongest_repositories: [repo_id]       # by aggregate contribution to matched requirements
├── irrelevant_strengths: [concept_id]       # strong candidate evidence with no matching requirement
├── overall_confidence                       # separate from score — see 15.5
```

### 15.5 Overall confidence (distinct from the score itself)

A function of: JD `extraction_confidence` average, fraction of
requirements that were `github_observable`, and
`coverage_meta.analysis_completeness` from the Candidate profile (Part 6)
— so a candidate with only 3 public repos, or a JD that parsed poorly,
produces a score **and** an explicit "this result is based on limited
evidence" flag, rather than presenting every match with false uniform
certainty.

---

## 16. Missing Evidence vs. Lack of Skill Semantics

A five-state status per requirement, not a boolean:

| Status | Meaning | Example |
|---|---|---|
| `SUPPORTED` | Evidence found, confidence at/above threshold | source-import evidence for PyTorch |
| `WEAK` | Some evidence, below the strong threshold | only a README mention |
| `NOT_DETECTED` | No evidence found **in the repositories analyzed** | *never* rendered as "does not know" |
| `NOT_OBSERVABLE` | Requirement category isn't the kind GitHub evidence can speak to at all | "strong communication skills" |
| `INSUFFICIENT_ANALYSIS` | Evidence might exist but wasn't checked — the account's repo count exceeded the Stage-1/N ranking budget (Part 11), or the candidate has too few public repos to judge anything | a concept could be sitting in repo #200 of 1,140, never reached |

`INSUFFICIENT_ANALYSIS` is the status most systems in this space skip,
and it matters most exactly because of Part 11's ranking limit: **"not
detected in the top 15 repos" is a materially weaker claim than "not
detected anywhere,"** and the product must never blur that distinction.
The explanation layer (Part 19) always states `repos_analyzed /
repos_total` alongside any `NOT_DETECTED` verdict for an account where
the two numbers differ.

Language for `NOT_DETECTED`, exactly: *"No meaningful \[Concept\]
evidence was detected in the \[N\] analyzed repositories."* Never:
*"the candidate does not know \[Concept\]."*

---

## 17. Alternative Role Discovery

Secondary feature, built as a **zero-marginal-cost reuse** of the same
matcher (Part 15), not a separate scoring path.

```
RoleArchetype                      # config/template, NOT a hardcoded conditional
├── archetype_id                    # e.g. "archetype.backend_engineer"
├── display_name
├── concept_weights: {concept_id: weight}    # a synthetic "job requirement profile"
├── archetype_version
```

**Mechanism:** each `RoleArchetype` is converted into a synthetic
`JobRequirementProfile` (its `concept_weights` become `Requirement`
rows) and run through the exact same matcher used for the user-submitted
JD. Archetypes are ranked by resulting `overall_match`; any archetype
scoring meaningfully higher than the submitted job's own match is
surfaced as an alternative-role suggestion.

**Extensibility:** archetypes live as data (YAML/JSON config, mirroring
the Concept registry's storage choice in Part 8), so adding
"Game Development" or "Compiler Engineering" as a new archetype is a new
config entry with concept weights — no new code, no new conditional
branch, and critically, **archetypes never gate or constrain the primary
matcher** — they are only ever compared *against* its output, never used
to select which scoring logic runs for the submitted job.

---

## 18. LLM Responsibilities and Boundaries

| Task | LLM? | Why |
|---|---|---|
| Extract candidate requirement phrases from raw JD text | **Yes** | Free text is inherently NLP; deterministic regex cannot cover arbitrary phrasing |
| Map an extracted phrase to a concept_id | **No (deterministic)**, LLM may *suggest* for the provisional/curation queue | Normalization must be reproducible and auditable — an LLM re-run should not silently change which concept a past requirement resolved to |
| Compute the numeric match score | **No, ever** | The prompt is explicit and the project's own philosophy (README: rule-based, explainable) agrees — a black box here defeats the entire redesign's purpose |
| Decide requirement importance (required/preferred) | **Partially** — LLM proposes, deterministic keyword/structure heuristics (e.g. "required," "must have," "nice to have" phrasing) can override/confirm | Keeps importance auditable rather than vibes-based |
| Render `MatchResult` into recruiter-readable prose | **Yes** | Pure presentation over an already-fully-computed, cited object — the LLM is given the `MatchResult` and told to describe it, never to invent facts not present in it |
| Alternative-role narrative framing | **Yes** | Same boundary — narrates `RoleArchetype` match results, doesn't compute them |
| Invent or assume technical evidence not present in `Evidence` rows | **Never** | Explicitly listed as unsafe in the prompt; enforced by interface boundary below |
| Make unsupported hiring claims ("this candidate would be a good hire") | **Never** | Out of scope for the product entirely, not just the LLM boundary |

**Enforced interface boundary:** the LLM layer only ever consumes and
produces two kinds of objects: (a) `ExtractedRequirementCandidate[]`
(unnormalized phrases, from JD text — input to the deterministic
normalizer, Part 8) and (b) prose generated from an **already fully
computed** `MatchResult`/`RoleArchetype` ranking. It never writes
directly into `Evidence`, `CandidateConceptSummary`, or
`MatchResult.overall_match` — those are produced exclusively by the
deterministic engine. This is a structural guarantee (the LLM call sites
simply have no write path into those tables/objects), not a prompting
convention.

---

## 19. Future Job URL Ingestion

Not implemented now; scoped as an adapter interface only:

```
JobSourceAdapter (interface)
    fetch(url: str) -> raw_text: str
```

Every adapter (LinkedIn, Glassdoor, Indeed, a company careers page) feeds
the **same** downstream `JobDescriptionParser(raw_text) ->
JobRequirementProfile` used for pasted text — URL ingestion only ever
changes how `raw_text` is obtained, never how it's interpreted. This
separation is deliberate, not just tidy: each job board has distinct,
brittle, ToS-sensitive scraping requirements (structure changes, anti-bot
measures, legal terms of use vary by site) that are a substantial,
independent engineering and legal surface — bundling that complexity into
the parsing/matching core would couple a stable, testable pipeline to the
least stable, least controllable part of the system. MVP ships exactly
one adapter: `PastedTextAdapter`, a trivial passthrough.

---

## 20. Data Model Evolution

**No database change now.** Proposed new entities, additive to the
existing `User`/`ProfileFeature` tables (kept, frozen, per Part 4):

| Entity | Persisted? | Notes |
|---|---|---|
| `Candidate` | Existing `User`, reused/aliased | No rename forced on the existing table; new code can refer to it as "the candidate" conceptually without a schema rename |
| `Repository` | **New, persisted** | Currently doesn't exist at all — the biggest structural gap identified in Part 4. One row per (candidate, repo, `collected_at` snapshot), mirroring `ProfileFeature`'s existing append-only-snapshot pattern |
| `Evidence` | **New, persisted** | Append-only; expensive to re-derive, valuable for audit — never overwritten, only added to on re-analysis |
| `Concept` | **New, config-file-backed** (Part 8), optionally DB-mirrored later for admin curation | Not urgent to put in the DB — changes rarely, benefits from code review |
| `CandidateConceptSummary` | **New, persisted (materialized cache)** | Derivable from `Evidence` at any time; persisted for query performance, tagged with `source_evidence_version`/`computed_at` so staleness is detectable and it can be safely rebuilt |
| `JobDescription` | **New, persisted** | Raw text + `job_parser_version` + extraction metadata |
| `JobRequirement` | **New, persisted** | One-to-many from `JobDescription` |
| `MatchResult` (the prompt's `JobAnalysis`/`RequirementMatch`, combined) | **New, persisted, immutable** | One row per (candidate snapshot, job, matcher_version) — **this is the direct structural replacement for "one permanent score,"** since a candidate can have many `MatchResult` rows, one per job/version, none of them overwriting another |
| `RoleArchetype` | **New, config-file-backed**, same reasoning as `Concept` | |

**What's computed on demand vs. persisted:** `Evidence` is always
persisted (source of truth, expensive to redo). `CandidateConceptSummary`
is persisted as a cache but is always reproducible by re-aggregating
`Evidence` — never a second source of truth. `MatchResult` is persisted
and **immutable** once computed — re-matching the same candidate against
the same job after either side changes produces a *new* `MatchResult`
row, never an in-place update, exactly extending the existing
`ProfileFeature` snapshot philosophy (`docs/ML_NOTES.md` §6) to the new
tables.

**Re-analysis after repositories change:** a new candidate-evidence
collection run creates a new `Repository`/`Evidence` snapshot generation
(shares the `collected_at`-keyed pattern already used for `ProfileFeature`);
old `Evidence` rows are not deleted, so historical `MatchResult`s remain
reproducible and auditable against the evidence that actually produced
them at the time.

---

## 21. Versioning / Migration Plan

New sibling constants to the existing `SCORING_RUBRIC_VERSION`/
`DATASET_VERSION`/`FEATURE_SCHEMA_VERSION` (`dataset/schema.py` is the
precedent to follow structurally):

| Constant | Bumps when |
|---|---|
| `EVIDENCE_SCHEMA_VERSION` | `Evidence`/`Repository` shape changes |
| `REPO_RANKING_VERSION` | Stage-1/Stage-2 ranking logic or N changes |
| `CONCEPT_REGISTRY_VERSION` | Concept registry adds/renames/merges |
| `JOB_PARSER_VERSION` | JD extraction prompt/logic changes |
| `MATCHER_VERSION` | Matching formula/weights/gates change |
| `ROLE_ARCHETYPE_VERSION` | Archetype config changes |

**What happens to `readiness_score`:** nothing. `SCORING_RUBRIC_VERSION=1`,
`scoring/readiness.py`, and Dataset V1 stay exactly as they are —
frozen, documented, still queryable as `V1 readiness_score → historical
baseline`. `MatchResult.overall_match` (`job_match_score`) is an
entirely separate, additively-introduced number; no migration converts
one into the other, and no future rubric change is applied retroactively
to old V1 rows (consistent with the existing project rule: "Do not
silently change the GitScore scoring definition").

---

## 22. MVP Definition

**Proposed MVP**, following and lightly refining the prompt's own sketch:

```
INPUT: job description text + GitHub username
  → repository listing (existing github/client.py, unchanged)
  → Stage-1 ranking (job-independent, Part 11) — zero new API calls
  → Stage-2 boost + select top N=15 (Part 11)
  → deep fetch: README + manifest files only, for the N selected repos (Part 12 MVP scope)
  → Evidence extraction (manifest + README + language-stats detectors)
  → CandidateConceptSummary aggregation
  → JD text → LLM-assisted requirement extraction → deterministic concept normalization
     → JobRequirementProfile
  → deterministic matcher (Part 15) → MatchResult
  → LLM explanation rendering over the completed MatchResult (Part 18)
OUTPUT: match score, matched/weak/missing requirements (with status semantics, Part 16),
        strongest supporting repositories, non-GitHub-observable requirements called out
```

**Open question flagged, not silently decided:** the prompt's Part 20
sketch includes alternative-role suggestions in the MVP output, while
Part 12 calls alternative-role discovery "a SECONDARY feature." Because
it reuses the matcher at effectively zero marginal engineering cost
(Part 17), the recommendation is to **build it in the same milestone as
the matcher but ship it as an optional/secondary section of the report**,
not gate MVP completion on it — but this is a product-priority call for
you, not one this design silently resolves.

**Explicitly NOT in MVP** (per your list, confirmed against the
codebase, nothing here contradicts current capability):
LinkedIn/Glassdoor/Indeed URL ingestion, CatBoost or any ML-based
scoring, recruiter dashboards/accounts, organization-owned-repository
attribution, commit-level attribution, multi-user ATS integrations,
source-import/test-directory evidence extraction (Part 12's post-MVP
tier), CI-workflow evidence, multi-language JD support, any UI.

---

## 23. Post-MVP Features

In roughly increasing order of engineering weight: source-import and
test-directory evidence extraction (Part 12); CI-workflow evidence;
notebook evidence; additional manifest ecosystems (`Cargo.toml`,
`go.mod`, `pom.xml`/`build.gradle`); organization-owned-repository
attribution (a real fix for the blind spot Milestone 4.5 flagged as
"insufficient evidence" to confirm — needs its own investigation);
job-posting URL adapters (Part 19); a Concept-registry admin/curation UI;
recruiter-facing dashboards; any consideration of a learned (non-rule-based)
matching component, only ever as a *secondary* signal alongside the
deterministic engine, never a replacement for it.

---

## 24. Recommended Implementation Milestones

Sequenced against the actual files identified in Part 4, smallest
independently-testable slices first.

### 5B — Repository ranking (job-independent, Stage 1 only)
- **Objective:** rank a candidate's already-fetched repo list by
  substantiveness, with zero new API calls.
- **Files likely affected:** new `src/gitscore/ranking/` package; extends
  `github/parser.py` to surface `archived`, `size`, `pushed_at`, `topics`
  from the payload already returned by `get_repositories()`.
- **Tests:** deterministic ordering given fixture repo-list payloads;
  edge cases — 0 repos, fewer than N repos (nothing truncated), all
  forks, all archived, ties.
- **Success criteria:** ranking is pure/deterministic given the same
  input list; no GitHub calls beyond what `analyze_user()` already makes today.
- **Out of scope:** job-aware boosting (Stage 2), any persistence.

### 5C — Repository + Evidence persistence model
- **Objective:** introduce `Repository` and `Evidence` ORM models,
  additive only.
- **Files:** `db/models.py` (new classes, `User`/`ProfileFeature`
  untouched), `db/queries.py` (new save/query functions).
- **Tests:** round-trip persistence, snapshot/append-only semantics
  mirrored from `ProfileFeature`'s existing test coverage
  (`tests/test_profile_module_dedup.py` is the direct precedent to extend).
- **Success criteria:** existing 231 tests still pass unmodified; new
  tables coexist without altering `profile_features`/`users` behavior.
- **Out of scope:** any detector logic, any matcher.

### 5D — Deep evidence extraction v1 (manifest detectors)
- **Objective:** fetch and parse `requirements.txt`/`pyproject.toml`/
  `package.json`/`Dockerfile` for the top-N ranked repos (5B), emit
  `Evidence` rows (5C) for a small starter Concept set.
- **Files:** new `src/gitscore/evidence/` detector package;
  `pipeline/analyze.py` gains a new orchestration path (existing
  `analyze_user()` untouched, a new `build_candidate_profile()`-style
  entry point added alongside it).
- **Tests:** fixture manifest files → expected Evidence rows;
  malformed/missing-file handling (mirrors the project's existing
  "handle malformed/missing data gracefully" test culture).
- **Success criteria:** correct Evidence extraction on fixtures; real
  API cost per account for a representative pilot-scale account measured
  and reported (direct sanity check against Part 11's N=15 cost estimate).
- **Out of scope:** concept normalization/registry (6A), any scoring.

### 6A — Concept registry + normalization mechanism
- **Objective:** the Part 8 registry (config file + resolver), covering
  the concepts needed by 5D's detectors plus a modest starter set
  spanning several of the prompt's categories (not exhaustive).
- **Files:** new `src/gitscore/concepts/` package + registry config.
- **Tests:** alias resolution, provisional-concept fallback, version bump
  behavior (no `concept_id` ever disappears).
- **Success criteria:** every `Evidence.matched_concept_id` from 5D
  resolves through this registry.
- **Out of scope:** job parsing.

### 6B — Job Requirement Profile + JD parser
- **Objective:** `JobDescriptionParser(raw_text) -> JobRequirementProfile`
  (Part 9 schema), LLM-assisted extraction behind the Part 18 boundary.
- **Files:** new `src/gitscore/jobs/` package.
- **Tests:** fixture JD texts → expected requirement sets (with an LLM
  call mocked/faked, per the project's existing "no live external calls
  in tests" convention).
- **Success criteria:** `github_observable` classification correctly
  separates a fixture set of technical vs. soft-skill requirements.
- **Out of scope:** matching.

### 7A — Deterministic matcher
- **Objective:** implement Part 15's formulas over 5D+6A candidate data
  and 6B job data.
- **Files:** new `src/gitscore/matching/` package.
- **Tests:** hand-computed fixture cases (mirroring
  `tests/test_scoring_readiness.py`'s existing style) covering: full
  coverage, partial coverage, the required-presence gate triggering,
  the repo-spam diminishing-returns behavior explicitly.
- **Success criteria:** every documented formula in Part 15 reproduces
  exactly on fixtures; no test requires a live GitHub or LLM call.
- **Out of scope:** explanation rendering, alternative roles.

### 7B — Explanation layer
- **Objective:** structured `MatchResult` → recruiter-readable report
  data (Part 14's shape), LLM-rendered prose over a fixed, fully-computed
  object.
- **Files:** new `src/gitscore/explain/` package.
- **Tests:** given a fixed `MatchResult` fixture, verify grouping/labeling
  logic (`SUPPORTED`/`WEAK`/`NOT_DETECTED`/etc.) without needing a live LLM.
- **Success criteria:** every claim in the rendered report traces to a
  `MatchResult`/`Evidence` field — no unfixtured/free-floating claims.
- **Out of scope:** UI.

### 8 — Alternative-role discovery
- **Objective:** `RoleArchetype` config + reuse of 7A's matcher (Part 17).
- **Files:** new archetype config; small orchestration addition, no
  matcher changes.
- **Tests:** archetype ranking against fixture candidate profiles.
- **Success criteria:** adding a new archetype requires zero code changes.
- **Out of scope:** UI.

### 9 — UI
- Explicitly out of scope for this design milestone entirely.

---

## 25. Risks and Open Questions

| Risk | Mitigation |
|---|---|
| GitHub profile ≠ complete professional capability | Product framing (README, UI copy) must repeat this as prominently as V1's existing disclaimer; `NOT_OBSERVABLE`/`INSUFFICIENT_ANALYSIS` statuses (Part 16) make the limitation structural, not just a disclaimer |
| False negatives (real skill, no GitHub trace — private repos, org work, non-GitHub experience) | Never render `NOT_DETECTED` as "lacks the skill" (Part 16); org-owned-work attribution is an explicit post-MVP investigation, not silently ignored |
| Keyword false positives (same class as `bradtraversy`'s `ai-keyword-extractor`) | Evidence-tier ladder (Part 13) demotes name/description-only matches to the weakest tier; manifest/import evidence required for anything above `WEAK` |
| Repository spam (100 shallow repos beating 4 strong ones) | `depth_factor`'s logarithmic cap (Part 15.1) and ranking's substantiveness gate (Part 11) both directly target this |
| Giant accounts (API cost) | N=15 ranking cap (Part 11) makes cost O(N) instead of O(total repos) |
| Organization-owned work invisible | Explicitly unresolved in this design (Part 23); flagged, not silently patched |
| Private repositories | Out of scope — product only ever sees what's public, stated plainly in every report |
| Old/abandoned repositories | `pushed_at` recency is a ranking input (Part 11), not currently a scoring input — a genuinely stale but historically strong repo can still contribute evidence, deliberately, since GitHub evidence of *having done* something doesn't expire the way "current daily practice" claims might; flagged as a product-philosophy choice, not an oversight |
| Tutorials/forks inflating evidence | Fork status is a ranking deprioritization (Part 11); tutorial-content detection is not solved here — flagged as an open gap |
| Job-description ambiguity / poor phrasing | `extraction_confidence` per requirement (Part 9) feeds `overall_confidence` (Part 15.5); low-confidence parses are surfaced, not hidden |
| Soft skills / unmeasurable requirements | `github_observable = "no"` exclusion from scoring (Parts 9, 15) |
| Seniority inference | Treated as a low-weight, explicitly-labeled signal only (Part 9); never a gating factor |
| API rate limits at scale | Directly addressed by Part 11's ranking; `scripts/collect_pilot.py`'s throttle logic (Part 4) is a candidate for promotion into production collection |
| Scraping restrictions (URL ingestion) | Deferred entirely via the adapter boundary (Part 19); no scraping implemented in this milestone or its immediate successors |
| LLM hallucination | Structural boundary (Part 18) — LLM never writes scores or invents Evidence; all rendered claims trace to already-computed objects |
| Score overconfidence | `overall_confidence` (Part 15.5) and `INSUFFICIENT_ANALYSIS` (Part 16) are first-class, not afterthoughts |
| Hiring fairness / recruiter misuse | Product must never claim to predict job performance or hiring success (same posture as the existing README's V1 disclaimer, carried forward and sharpened — a job-match score is evidence of technical overlap, not a hiring recommendation); this is a product-policy risk that engineering alone cannot fully mitigate and should be revisited explicitly before any recruiter-facing release |

**Open questions for you, not resolved by this design:**
1. MVP scope of alternative-role discovery (Part 22) — bundled with 7A/8 or deferred past first release?
2. `W_REQUIRED`/`W_PREFERRED` and gate thresholds (Part 15.3) are placeholder assumptions — need calibration against real job descriptions before they mean anything.
3. Whether/when to invest in the organization-owned-work blind spot (flagged as unresolved by both this doc and the Milestone 4.5 pilot).
4. How aggressively to pursue LLM-based JD parsing vs. a simpler deterministic keyword-extraction baseline for the very first slice of 6B.

---

## 26. Final Recommended Architecture Diagram

```
                         ┌────────────────────────────┐
                         │   GitHub username input    │
                         └──────────────┬─────────────┘
                                        │  (github/client.py — REUSED AS-IS)
                                        ▼
                         ┌────────────────────────────┐
                         │  Repository listing fetch   │
                         └──────────────┬─────────────┘
                                        │
                                        ▼
                    ┌───────────────────────────────────────┐
                    │  Stage 1: job-independent ranking (5B) │  0 new API calls
                    └──────────────────┬──────────────────────┘
                                       │
        JobRequirementProfile ───────►│  Stage 2: job-aware boost, select top N=15
        (from 6A/6B, below)           └──────────────────┬──────────────────────┘
                                                          │
                                                          ▼
                                       ┌───────────────────────────────────┐
                                       │ Deep fetch: README + manifests (5D)│
                                       └──────────────────┬──────────────────┘
                                                          │
                                                          ▼
                                       ┌───────────────────────────────────┐
                                       │  Evidence extraction (5D + 6A)     │
                                       │  -> Evidence rows (5C, persisted)  │
                                       └──────────────────┬──────────────────┘
                                                          │
                                                          ▼
                                       ┌───────────────────────────────────┐
                                       │ CandidateConceptSummary (cache)    │
                                       └──────────────────┬──────────────────┘
                                                          │
   ┌──────────────────────────┐                          │
   │  Pasted job description   │                          │
   └──────────────┬────────────┘                          │
                  ▼                                       │
   ┌───────────────────────────────────┐                  │
   │ LLM: extract requirement phrases   │  (6B, bounded per Part 18)
   └──────────────┬────────────────────┘                  │
                  ▼                                       │
   ┌───────────────────────────────────┐                  │
   │ Deterministic concept normalization │ (6A registry)   │
   └──────────────┬────────────────────┘                  │
                  ▼                                       │
   ┌───────────────────────────────────┐                  │
   │   JobRequirementProfile (6B)        │                 │
   └──────────────┬────────────────────┘                  │
                  │                                       │
                  └───────────────┬───────────────────────┘
                                  ▼
                  ┌───────────────────────────────────┐
                  │  Deterministic Matcher (7A)         │  <-- source of truth for score
                  │  -> MatchResult (persisted, 5C)     │
                  └──────────────────┬──────────────────┘
                                     │
                     ┌───────────────┴───────────────┐
                     ▼                                ▼
       ┌───────────────────────────┐    ┌───────────────────────────────┐
       │ LLM: explanation prose (7B)│    │ RoleArchetype matching (8)     │
       │ (renders MatchResult only) │    │ (reuses 7A on synthetic jobs)  │
       └───────────────────────────┘    └───────────────────────────────┘

   Frozen, untouched, historical baseline (still fully functional):
   github/client.py's other consumers -> pipeline/analyze.py (V1) ->
   features/* -> scoring/readiness.py -> ProfileFeature.readiness_score ->
   dataset/{schema,builder,report,export}.py -> gitscore_dataset_v1.csv
```
