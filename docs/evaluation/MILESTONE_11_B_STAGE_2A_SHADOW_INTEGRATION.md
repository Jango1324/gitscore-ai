# Milestone 11-B Stage 2A — Shadow Integration Architecture

**Status: architecture/design review only. No production code modified.
No commit made.** This document is the deliverable for an
evaluation-first design milestone — it proposes a migration path from
today's deterministic parser toward a more general qualification-
understanding pipeline, and ends in STOP questions, not shipped code.

## 0. Verified baseline

| Check | Expected | Actual |
|---|---|---|
| HEAD | `c9ac6bb922ae703bbb39ddb03ed4ab8c06b7b500` | confirmed (`git rev-parse HEAD`) |
| Branch | `main` | confirmed |
| Parser version | `job_description_parser:v10` | confirmed (`parser.py` line 217) |
| Tests | 1317 passed, 13 skipped | confirmed (`pytest -q`) |
| `jobs/parsing/qualification.py` | standalone, unwired | confirmed — not imported by `parser.py`/`segmentation.py`/`necessity.py`/`narrative.py` (pinned by `test_module_is_not_imported_by_the_live_parser`) |
| Frozen historical gold | unchanged | confirmed (`git diff --stat -- evaluation/gold evaluation/gold_v1_1` empty) |
| Five untracked M11 generalization files | preserved | confirmed present and untouched (`git status --porcelain`) |

This document adds no code to `src/gitscore`. Where a prototype was
needed to verify a claim below (e.g. "does today's parser actually
produce X"), it was run directly against the already-existing,
unmodified pipeline via `python -c` / targeted `Read`/`Grep` — never by
writing a new module.

---

## Phase 1 — Audit of the Stage 1 representation against the real pipeline

Stage 1 (`qualification.py`) was audited field-by-field against the
ACTUAL current implementations of `segmentation.py`, `necessity.py`,
`confidence.py`, `observability.py`, `non_technical.py`,
`concepts/registry.py`, `matching/engine.py`, and `api/serialization.py`
— not against what those modules are assumed to do. Findings below are
each backed by a specific line/behavior read directly from the file
named.

### 1.1 Unknown necessity — fully preserved, no gap

`infer_necessity()`/`resolve_necessity_hint()` (`necessity.py`) already
return `Necessity | None` today, and `None` already has a real,
honored meaning in production (`_requirements_from_claim` short-
circuits to `[]`, routing the claim to `UnparsedClaim` rather than
guessing). `Qualification.necessity: Necessity | None` and
`project_qualification()`'s `necessity_unknown` rule are a faithful,
lossless mirror of this EXISTING policy. **No representational gap.**

### 1.2 Conditional applicability — model can hold it, nothing produces it

`Qualification.applicability_condition` is a real field. But **no
existing detector extracts one at all.** `necessity.py`,
`segmentation.py`, and every other parsing module were read directly:
none contains any logic that identifies a conditional clause ("unless
you can demonstrate...", "if the role requires it") as a distinct
span separate from the claim's primary necessity marker. A sentence
like `m11b-conditional-01` ("Bachelor's degree required, unless you can
demonstrate equivalent practical experience.") is, to today's parser,
simply ordinary claim text: `_REQUIRED_MARKER` fires on "required",
`infer_necessity` returns `REQUIRED`, and the "unless..." clause is
inert — present in `original_text` but never separately recognized.
**Confirmed gap: representation exists, extraction does not.** This is
the single largest piece of genuinely NEW detector work any Path B
extractor would need to do that has zero precedent anywhere in the
existing codebase (every other `Qualification` dimension has at least
a partial existing analogue; this one has none).

### 1.3 Interpretation confidence — reused type, but coarser population policy than the model can express

`interpretation_certainty` reuses `ParserConfidence` correctly (§0 of
the Stage 1 doc already established this enum exists and is
populated). But reading `confidence.py` directly surfaces a concrete
mismatch: `confidence_for()` is keyed by a small, fixed vocabulary of
six extraction **kinds**, not by any assessment of the sentence's own
ambiguity. Critically, `parser.py`'s `alternative.kind == "technical"`
branch (an OR-group with every member resolved to a real concept)
*always* calls `confidence_for("resolved_concept")` → `HIGH`,
regardless of whether the sentence said "such as" (illustrative,
`m11b-illustrative-01`, corpus-annotated `LOW`) or "one of the
following" (exhaustive, `m11b-exhaustive-01`, corpus-annotated `HIGH`).
**Today's parser cannot distinguish these two cases at all** — both
would get `HIGH` confidence under the current policy. A compatibility
adapter (Phase 2, Path A) must not treat `confidence_for()`'s output as
a ground-truth value to copy uncritically into `interpretation_certainty`
for alternative-group claims; it is a real, measured information loss
the current parser already has, independent of anything Stage 1 or
Stage 2A introduces.

### 1.4 Technical competencies — zero existing detector, confirmed structurally

Grepping `find_concept_mentions`, `find_conservative_unknown_terms`,
and `non_technical.py`'s `_PATTERNS` table confirms: no code path
anywhere in the current parser assigns `category="technical_competency"`
or anything resembling it. The string `technical_competency` does not
appear outside `qualification.py` and its own tests. This matches
Milestone 11's own measured 9% recall finding exactly — not a detection
*miss*, a structural *absence*. **Confirmed, not assumed.**

### 1.5 Compound requirements — AND and OR_ANY implicit today, MIXED has no representation at all

`AND` is already representable today, just not AS a labeled value: two
independent `JobRequirement` rows from one sentence (Milestone 6A's own
"ONE sentence, TWO qualification objects" precedent, exercised by
`m11b-multi-01`/`02`'s `sibling_qualifications` shape). `OR_ANY` is
already representable via `alternative_concept_ids`. `MIXED_UNSUPPORTED`
(an AND of ORs, "CI/CD tooling... AND observability tooling such as...")
has **no representation in production at all** — confirmed via
`alternatives.py` (read in the Stage 1 design phase) and M10D's own
disclosed Root Cause 6, still open. Stage 1 gives this an honest
diagnostic name; nothing produces it from real text yet.

### 1.6 Source-span integrity — no gap, already load-bearing elsewhere

`SourceSpan`/`Claim.start`/`.end` have been direct-slice, exact,
non-reconstructed since Milestone 6B Part 11, and M11-A2 specifically
hardened this (`test_source_spans_remain_exact_for_a_joined_claim`).
`Qualification.source_span` reuses the identical type; Stage 1's own
tests already pin exactness through both the safe and unsafe
projection path. **No gap.**

### 1.7 GitHub assessability — confirmed representational gap for competencies

`observability.py` was read directly. There are exactly two policies:
a single constant (`STRONGLY_OBSERVABLE`) for any confirmed technical
concept, and a five-entry table keyed by the non-technical `category`
string (`experience`/`education`/`legal`/`soft_skill`/`leadership`/
`alternative_requirement`/`unresolved_requirement`, default
`NOT_OBSERVABLE`). **Neither policy has any notion of a technical
competency at all.** `m11b-competency-01` ("concurrency",
`PARTIALLY_OBSERVABLE`) and `m11b-competency-02` ("circuit theory",
`NOT_OBSERVABLE`) require a *third* table, keyed by `competency_tag`
(not `category`, not concept mention) — a table that does not exist
today in any form. This is the concrete evidence behind Phase 5's
own observability-boundary analysis below.

### 1.8 Uninterpretable qualification text — representation is already a no-op, detection does not exist as a distinct state

Functionally, `UnparsedClaim` already *is* "the parser could not
responsibly interpret this" today — `project_qualification()`'s own
`UNINTERPRETABLE` rule reduces to exactly that same destination. There
is **no representational gap** here. The real gap is upstream of the
model entirely: nothing in today's parser distinguishes "this text
matched zero patterns because it IS genuinely uninterpretable" from
"this text matched zero patterns because no detector for its content
exists yet" (e.g. a technical-competency sentence, §1.4) — both
currently collapse into the identical "zero `JobRequirement` rows"
outcome. Stage 1 correctly does not attempt to resolve this; it is a
Path B extraction-quality question, not a representation question.

### 1.9 A meta-finding that applies to every dimension above

**A `Qualification` constructing without error is a shape-validity
fact, never a semantic-correctness fact.** `Qualification(qualification_kind=
SPECIFIC_TECHNOLOGY, normalized_reference=NormalizedReference(concept_id=
"language.rust"), ...)` constructs and projects identically whether the
underlying `source_text` actually says "Rust" or says nothing about
Rust at all — `__post_init__` validates field shape (non-empty text, a
registered concept id, mutual exclusivity), never the relationship
between `source_text` and the other fields. This means: **no amount of
model-level testing (Stage 1's 56 tests included) can catch an
extractor that classifies a sentence wrong.** Only evaluation against
independently-annotated examples can catch that — which is exactly why
Phase 4 below insists on a genuinely held-out corpus for ANY future
extractor, not more unit tests of the model itself. A caller building a
Path B extractor must never report "N `Qualification`s constructed
successfully" as if it were an accuracy metric.

### 1.10 A concrete taxonomy mismatch, found while building Phase 2's compatibility adapter prototype

`JobRequirement.category` and `QualificationKind` are **two unrelated
vocabularies that happen to share a few word-roots.** Reading
`concepts/registry.py` directly: a confirmed technical mention sets
`category` to the concept's OWN registry category — `"language"`,
`"database"`, `"ml_framework"`, `"infra"`, etc. (dozens of values, one
per concept family) — never `"specific_technology"`. A non-technical
match sets `category` to one of `non_technical.py`'s four literal
strings (`"education"`, `"legal"`, `"leadership"`, `"soft_skill"`) or
`experience.py`'s `"experience"`, or one of `parser.py`'s own two
fallback-placeholder categories (`"alternative_requirement"`,
`"unresolved_requirement"`). **None of these nine-plus strings is
`QualificationKind`'s own seven-value vocabulary.** A reverse-mapping
adapter (Phase 2) must derive `qualification_kind` from STRUCTURAL
facts (is `concept_id`/`alternative_concept_ids` populated at all?
which of the closed non-technical/placeholder category strings is it?)
— never by assuming `category` already speaks `QualificationKind`'s
language, because it demonstrably does not.

---

## Phase 2 — Two fundamentally different pathways

### Path A: Compatibility adapter (validates representation, not recall)

**Design:** a pure, deterministic function
`qualification_from_job_requirement(requirement: JobRequirement) -> Qualification`
and its `UnparsedClaim` counterpart
`qualification_from_unparsed_claim(claim: UnparsedClaim) -> Qualification`
— the REVERSE of `project_qualification()` — built from the structural
rule in §1.10, never from assuming `category` already means
`qualification_kind`:

| Existing fact | → `qualification_kind` |
|---|---|
| `concept_id is not None` or `alternative_concept_ids` populated | `SPECIFIC_TECHNOLOGY` |
| `category == "education"` | `EDUCATION` |
| `category == "experience"` | `EXPERIENCE` |
| `category in {"legal", "leadership", "soft_skill"}` | `NONTECHNICAL` |
| `category in {"alternative_requirement", "unresolved_requirement"}` | `OTHER_LEGITIMATE` (today's own conservative, non-fabricating fallback shape — not a confident technology claim, but a legitimate, already-preserved one) |
| anything else (bare `category=None`, no concept mapping) | `OTHER_LEGITIMATE` as well, same reasoning |
| `UnparsedClaim` (no `JobRequirement` exists at all) | `UNINTERPRETABLE` |

**Acceptance criterion (independent of Path B):** for every
`JobRequirement`/`UnparsedClaim` produced by the CURRENT, unmodified
`_parse()` across every existing regression/frozen corpus
(M9B/M10A/M10C/M10D/M11/`8c:v1`/`8c:v1.1`), the round trip
`requirement -> qualification_from_job_requirement() ->
project_qualification() -> job_requirement` must be **byte-identical**
to the original (`==` on the frozen dataclass, which already gives
structural equality for free). Any non-identical round trip is a
genuine adapter bug and must be fixed before Path A can be called
validated — it is never acceptable to adjust the ORIGINAL corpus
annotations to make a round trip match (mirrors every prior milestone's
"never reinterpret existing annotations to fit a new model" discipline).

**What this proves, and what it explicitly does NOT prove:** a clean
Path A round trip proves the `Qualification`/`project_qualification()`
representation is *expressive enough* to carry today's parser's output
losslessly — a real, useful fact (it rules out "the model itself is
too narrow"). **It proves nothing about recall, about technical
competencies, or about any text the current parser already gets
wrong** — wrapping an existing, unchanged output in a new type is not
an improvement to what that output contains. This repeats the Stage 1
doc's own guardrail and is restated here because Path A's own
test-suite output (e.g. "100% of 350 existing JobRequirements round-
trip cleanly") could easily be misread by a future reader as a
generalization claim if not labeled explicitly.

### Path B: Independent semantic interpretation (where generalization must originate)

**Design direction, not an implementation:** a future extractor
`extract_qualifications(claim: Claim) -> list[Qualification]`, called
INSTEAD of (not alongside) `_requirements_from_claim`'s own detector
chain for a given claim, built to recognize the kinds §1.4/§1.2 show
have zero existing detector — most importantly `TECHNICAL_COMPETENCY`
and `applicability_condition`. This is explicitly out of scope to
design in detail here (no LLM extraction is approved, per the
Restrictions — and a purely rule-based competency detector would need
its own evaluation-first milestone, likely its own curated keyword/
phrase taxonomy analogous to `non_technical.py`'s, which does not exist
yet even in sketch form).

**Acceptance criterion (independent of Path A):** measured recall,
precision, and false-qualification-creation rate against a genuinely
HELD-OUT corpus (Phase 4) the extractor's own author never saw while
writing extraction rules — Path A's round-trip-equality criterion is
structurally inapplicable here (there is no existing output to round-
trip against for a `TECHNICAL_COMPETENCY` claim; the extractor is
creating a NEW classification that did not exist in the output at all).

**The two pathways must never be conflated when reporting results.** A
dashboard or report that shows "qualifications extracted" without
separating Path-A-sourced rows (which already existed as
`JobRequirement`s) from Path-B-sourced rows (which are a genuinely new
classification) would silently manufacture an appearance of improved
coverage — exactly the failure mode this document's own instructions
warn against ("do not treat wrapping existing outputs as improved
qualification recall").

---

## Phase 3 — Shadow-mode architecture

Three implementation options were evaluated for comparing a candidate
structured pathway against the live parser without changing any
user-visible output.

### Option A — Offline evaluation-only runner

A script (`scripts/evaluate_shadow_*.py`, following the existing
`scripts/evaluate_m*.py` naming/structure already used by every prior
milestone) that takes a corpus of raw job-description text, runs BOTH
`parse_job_description_with_diagnostics()` (today's real parser,
unmodified) and a candidate Path A/B pathway, and reports a structured
diff — module-for-module identical in spirit to
`scripts/check_evaluation_staleness.py`'s existing committed-vs-fresh
comparison pattern. Zero runtime dependency: nothing in the live API,
CLI, or `gitscore.application` package changes at all. Can be run
on-demand, in CI, or ad hoc.

### Option B — Opt-in shadow parser, callable independently

A new, explicitly-separate entry point (e.g.
`gitscore.jobs.parsing.shadow.parse_job_description_shadow()`) that a
caller — a script, a notebook, a future internal tool — can invoke
side-by-side with the real parser on the same input, getting both
results back for manual or scripted comparison. Still zero change to
`parse_job_description()`/`parse_job_description_with_diagnostics()`/
`gitscore.application.job_fit.analyze_job_fit()`/the HTTP API/the
frontend. The only difference from Option A is that the comparison
logic lives in an importable function rather than only a standalone
script — meaningfully more reusable, meaningfully more surface area
than strictly needed for the question this milestone is trying to
answer ("does the candidate pathway even work, at what recall").

### Option C — Shadow execution inside normal API requests

Every real `/analyze` request also runs the candidate pathway
internally (e.g. logged, or returned in a diagnostics-only response
field never read by the frontend) so shadow data accumulates from real
production-shaped traffic rather than only curated corpora. This
touches `gitscore.application.job_fit`/the HTTP request path directly
— a live-system change, with live-system failure modes (the shadow
pathway raising an exception, running slowly, or leaking into logs)
that a purely offline comparison can never have. It would also be the
first point this design touches anything downstream of parsing at all
during a milestone whose own Restrictions explicitly forbid wiring
`Qualification` into live API requests.

### Recommendation: Option A

The smallest option that delivers exactly the diagnostic evidence this
milestone needs (recall/precision/false-creation numbers against known
corpora) with **zero** touch to any live, user-facing code path, zero
new runtime dependency, and a design pattern (`scripts/evaluate_*.py`
+ a JSON report under `evaluation/reports/`) this project has already
used successfully nine times (M9B through M11-A2). Option B is not
wrong, but it is more machinery than the stated objective
("compare... without modifying live user-visible outputs") requires —
it should be built only if and when a second, non-milestone consumer
of the comparison function actually materializes, not speculatively
now. Option C is explicitly out of scope: the Restrictions name this
exact outcome ("Do not wire Qualification into live API requests") and
this document's own Phase 3 instruction says the same ("the live
parser must remain authoritative until a separate production migration
is approved") — Option C is incompatible with that on its face, not
merely riskier.

---

## Phase 4 — Evaluation-first controls

### Development material (never re-described as held-out)

The existing 21-entry `evaluation/m11b/structured_qualification_controls.json`
and Milestone 11's own 9-posting/68-claim generalization corpus remain
exactly what they have always been labeled: hand-authored DEVELOPMENT
material, used to validate that the `Qualification` model and
`project_qualification()` can represent a known range of shapes — never
re-labeled as a held-out validation set for a future extractor, and
never modified to fit a new model (per this document's own
Restrictions and every prior milestone's identical discipline).

### Additional test categories a future Path A/B implementation would need (not written now — Stage 2A is architecture only)

For each category below: which pathway it exercises, and what a
passing/failing result would mean.

| Category | Pathway | What a result means |
|---|---|---|
| Existing technology qualification parity | Path A | Round-trip equality — a failure is an ADAPTER bug, never a parser-behavior change |
| Technical competencies absent from the registry | Path B only | Path A has structurally nothing to say here (no existing `JobRequirement` ever has `category="technical_competency"`) — this is pure extractor recall/precision |
| Genuine education/experience requirements | Path A (parity) + Path B (recall on phrasing today's fixed patterns miss, e.g. non-`non_technical.py`-table phrasings) | A combined view: does the adapter preserve what's already caught, does the extractor catch MORE than `non_technical.py`'s four-phrase table |
| Genuine nontechnical requirements | Same as above | Same |
| Narrative technology mentions (should NOT become qualifications) | Path B only | A false-qualification-creation check — `contains_narrative_cue()` (`narrative.py`) is the EXISTING safeguard; a Path B extractor must be measured against the same M10E/M11-A1/M11-A2 narrative fixtures to confirm it does not reintroduce a fabrication class those milestones specifically closed |
| Responsibilities vs. applicant qualifications | Path B only | Same narrative-safety category — the Manulife "Collaborate with..." class of bug |
| Compound AND/OR semantics, including MIXED | Path A (parity for AND/OR_ANY) + Path B (can a future extractor at least correctly emit `MIXED_UNSUPPORTED` rather than silently flattening it) | M10D's Root Cause 6 is the concrete regression to watch for |
| Unclear employer necessity | Path A (parity) | `necessity=None` must survive the round trip untouched, never coerced |
| Conditional qualifications | Path B only | Path A has nothing to adapt (§1.2 — no existing detector produces this at all); this is 100% new extraction surface |
| Explicit preferred qualifications | Path A (parity) | `Necessity.PREFERRED` round-trips |
| GitHub-unassessable qualifications | Path A (parity) + Path B (does a competency extractor assign observability correctly — §1.7's missing third table) | |
| Source text/offset preservation | Path A (parity, already covered by Stage 1's own tests) + Path B (a NEW extractor must be independently proven not to approximate/reconstruct spans — M11-A2's own hard-won discipline) | |
| Malformed/ambiguous claims | Path B only | Does the extractor correctly emit `UNINTERPRETABLE` rather than guessing, and does `project_qualification()`'s existing `invalid_normalized_reference` fallback catch anything the extractor gets structurally wrong |

### Holdout methodology (to be AUTHORED only once Path B implementation is separately approved — not now)

A genuinely held-out corpus must satisfy, at minimum:

1. **Sourced from real postings the extractor's author has not read
   while writing extraction rules** — the same discipline M11's own
   9-posting corpus already followed relative to the production
   parser, extended one level further: the *development* corpus
   (M11/M11-B's existing 21+9 examples) and the *holdout* corpus must
   have zero sentence-level overlap, and ideally zero same-posting
   overlap.
2. **Frozen by content hash before any extractor code is written
   against it** — mirroring `evaluation/gold`'s existing frozen-gold
   discipline (`scripts/check_evaluation_staleness.py`) extended to a
   NEW corpus, not reusing the existing `8c:v1`/`8c:v1.1` hashes (those
   remain scoped to the current parser's own claims, never
   repurposed).
3. **Annotated independently of the extractor's own output** — exactly
   as M11-B's 21 controls were authored from the sentence's own meaning
   "independent of what today's production parser does with it," never
   back-filled from what a candidate extractor happened to produce.
4. **Stratified across writing style and domain**, continuing M11's own
   12-industry framing (cybersecurity/devops/electrical/embedded/
   frontend/fullstack/general_swe/systems_performance, per the Phase 1
   investigation's own measured per-domain breakdown) rather than one
   style repeated.
5. **Never touched by Path A's own compatibility-adapter work** — Path
   A validates representation against EXISTING parser output only; it
   has no legitimate reason to ever read the Path B holdout corpus, and
   must not.

This document deliberately stops at specifying the methodology, not
the content — authoring 20+ new held-out sentences now, before Path B
implementation is even approved, would risk the corpus going stale (or
tempting a future author to peek at it while designing extraction
rules) long before it is actually used.

---

## Phase 5 — Observability and projection boundaries

### The three destinations, and when each applies

1. **Safe projection into a scoreable `JobRequirement`.** Already
   fully specified by Stage 1's `project_qualification()` — applies
   whenever necessity, observability, and logical structure are all
   known and representable. §1.7's finding matters here: a
   `TECHNICAL_COMPETENCY` `Qualification` with a `competency_tag` (no
   `concept_id`) and `github_observability=PARTIALLY_OBSERVABLE`
   **already projects successfully today** (confirmed directly:
   `project_qualification()`'s own code path sets `concept_id=None`,
   `alternative_concept_ids=()` when only `competency_tag` is set, and
   neither of those blocks projection). This was verified against
   `matching/engine.py`'s own `NOT_ASSESSABLE` decision table
   (`PARTIALLY_OBSERVABLE` + no concept mapping → `NOT_ASSESSABLE`,
   confirmed by reading the table directly) — such a `JobRequirement`
   would be correctly, safely treated as `NOT_ASSESSABLE` by the
   EXISTING, unmodified matcher, never falsely `SUPPORTED`. **This is a
   more complete story than it first appears**: the representation
   problem for technical competencies is almost entirely a Phase 1
   EXTRACTION gap (§1.4), not a projection-safety gap — Stage 1's
   model and matcher-safety already handle it correctly once something
   populates the fields.
2. **Preserved as `UnparsedClaim`.** Applies to every case
   `project_qualification()`'s existing five safety rules already
   name: unknown necessity, unknown observability, `MIXED_UNSUPPORTED`,
   `UNINTERPRETABLE`, or a material `applicability_condition`.
3. **Represented internally only, with no public destination.** This
   is a genuinely open question, addressed below.

### Is `UnparsedClaim` semantically sufficient long-term?

**Mostly yes for the SAFETY property, no for the PRESENTATION
property.** `UnparsedClaim` already correctly guarantees "never
scored, never silently dropped" — nothing in Phase 1-5's findings
changes that. But reading `api/serialization.py` directly surfaces a
concrete risk for any FUTURE stage that wires `qualification_kind`
into `JobRequirement.category`: `_interpretation_status()`'s own
`_UNPARSED_PLACEHOLDER_CATEGORIES` set is a closed, two-string literal
(`{"unresolved_requirement", "alternative_requirement"}`). A
`NOT_ASSESSABLE` `JobRequirement` with `category="technical_competency"`
would fall through to `_interpretation_status()`'s `else` branch and be
labeled `"non_technical"` — **actively misleading**, since a technical
competency is not "non-technical" at all; it is a recognized technical
claim that merely lacks structured GitHub evidence (§1.7). **This is a
real, named presentation-layer risk for Stage 3+, not solved here** —
this document does not propose a fix (a fix would mean either widening
that set or introducing a new `interpretation_status` value, both
explicit public-contract changes outside this milestone's scope). It
is recorded here specifically so a future Stage 3 reviewer does not
discover it for the first time after `category="technical_competency"`
has already shipped to the public API.

### Future score-denominator changes: detection and review mechanism

`JobAssessment.assessable_count` (`assessment/models.py`) is a live-
computed `@property` — `len(SUPPORTED + NOT_OBSERVED matches)`, never
stored, never independently settable. The ONLY lever that can move it
is a `JobRequirement`'s `MatchStatus`, which is itself fully determined
by `github_observability` + `concept_id`/`alternative_concept_ids`
(the `NOT_ASSESSABLE` decision table, `matching/engine.py`) plus
candidate evidence. This gives a precise, mechanical detection method
for any future wiring change, identical in spirit to this milestone's
own Stage 1 verification pattern:

> Run the full frozen-gold + regression-corpus suite
> (`8c:v1`/`8c:v1.1`/M9B/M10A/M10C/M10D/M11) through `match_job()`/
> `assess_job()` BEFORE and AFTER the candidate change, and diff
> `assessable_count`, `alignment_score`, `required`, and `preferred`
> per fixture. A `0` diff across every fixture means the denominator
> population did not move — the exact bar this milestone's own Stage 1
> report held itself to (`evaluate_m11_generalization.py`,
> `evaluate_m10a_realworld.py`, `evaluate_m9b_preservation.py`,
> `check_evaluation_staleness.py`, all byte-identical before/after).

Any non-zero diff is the signal that a change crossed from "internal
representation" into "live scoring" territory and requires the same
explicit, separate approval this milestone's own Restrictions already
demand for matcher/scoring changes.

**No third public output destination and no schema change is proposed
by this document**, per the explicit instruction — the analysis above
identifies risk and a detection method, not a fix.

---

## Phase 6 — Measurable acceptance criteria

| Criterion | Threshold | Measurement method |
|---|---|---|
| Zero changes to existing assessment outputs during shadow evaluation | 0 diffs | Option A's offline runner computes its comparison from a COPY of each requirement/match pool; the live `assess_job()`/`match_job()` call path for real requests is never touched, confirmed by `git diff --name-only -- src/gitscore` showing no change to `matching/`, `assessment/`, `api/` for the shadow runner's own implementation |
| Technology extraction precision/recall (Path A parity) | 100% round-trip equality against every existing regression/frozen corpus | Exact dataclass `==` comparison, pre- vs. post-adapter, per §Phase 2 Path A |
| Technical competency identification recall (Path B) | Measured and reported, NO target floor claimed in advance | Against the Phase 4 holdout corpus only, once authored and approved — reporting a number is not the same as claiming the number is adequate; M11's own 9% baseline recall for this category, measured against DEVELOPMENT material, is the only number that exists today and must not be conflated with a future holdout measurement |
| False requirement creation | 0 | Same methodology Stage 1/M11-A1/M11-A2 already used: a dedicated count of `NEW` scored rows that do not correspond to a genuine qualification in the holdout corpus's own independent annotation |
| Preservation of true applicant qualifications | 100% (no genuine qualification silently reaches zero trace) | Same "lost qualifications" metric `evaluate_m11_generalization.py` already reports today (5 lost / 68 claims baseline) — any Path B candidate must be compared against this EXACT existing metric, not a redefined one |
| Required/preferred classification correctness | 100% against the holdout corpus's own independent necessity annotation | Direct field comparison |
| Logical grouping correctness (SINGLE/AND/OR_ANY/MIXED_UNSUPPORTED) | 100% against holdout annotation; `MIXED_UNSUPPORTED` emitted (not silently flattened) wherever annotated | Direct field comparison |
| Source provenance integrity | 100% exact span match (`text[span.start:span.end] == source_text`) | Identity-level check, mirroring M11-A2's own test discipline |
| GitHub observability correctness | 100% against holdout annotation, INCLUDING the §1.7 competency-tag table once it exists | Direct field comparison |
| Evaluation reproducibility | Byte-identical report on repeated runs against the same code + corpus | Deterministic pipeline, no randomness anywhere in scope (mirrors every existing `evaluate_*.py` script's own property) |

### Failure analysis requirement

Any Path B evaluation run must report failures broken down by (a) job
category / domain (continuing M11's own 8-domain breakdown:
cybersecurity, devops_cloud, electrical, embedded, frontend,
fullstack, general_swe, systems_performance) and (b) writing style
(bulleted vs. prose, section-structured vs. unsectioned, per M10C/M10E's
own existing stratification) — a single aggregate percentage is
explicitly insufficient, matching this document's own instruction and
every prior milestone's practice of reporting per-domain tables rather
than one number.

### Explicit non-claim

**No universal generalization claim may be made from the existing ~30
development examples (21 M11-B + 9 M11 postings).** Any Path B report
must state its holdout corpus's own size and domain coverage
explicitly, and must not extrapolate beyond it — mirroring this
document's own Phase 4 instruction and M11's own original finding
(9% recall on 11 held-out `TECHNICAL_COMPETENCY` claims) being reported
as exactly that — a measurement on 11 claims — never as a property of
"technical competencies in general."

---

## Dependency-ordered implementation plan (for a SEPARATE, future approval — not started here)

1. **Path A compatibility adapter** (`qualification_from_job_requirement`/
   `qualification_from_unparsed_claim` + round-trip test suite against
   every existing regression/frozen corpus). No new detector, no new
   policy — pure reverse-mapping of facts already computed today. Lowest
   risk, fully mechanical, and the natural first step since it has no
   dependency on anything else in this plan.
2. **Shadow runner, Option A** (`scripts/evaluate_shadow_parity.py` or
   similar) — depends on (1) existing, since its first and simplest use
   is confirming (1)'s own round-trip claim at scale, offline, with a
   report artifact matching the existing `evaluation/reports/` pattern.
3. **Holdout corpus authored and frozen**, per Phase 4's methodology —
   depends on nothing above technically, but should follow (1)/(2) in
   practice so the corpus is frozen as close as possible to when a real
   Path B candidate will actually be measured against it (minimizing
   drift/staleness risk, per `check_evaluation_staleness.py`'s own
   existing concern).
4. **Technical-competency observability table** (§1.7's missing third
   policy table, keyed by `competency_tag`) — a prerequisite for ANY
   Path B extractor to safely populate `github_observability` for a
   `TECHNICAL_COMPETENCY` qualification; has no dependency on a working
   extractor existing yet (it can and should be designed/evaluated
   against the Phase 4 development corpus's own already-annotated
   `github_observability` values first).
5. **Path B extractor, rule-based, no LLM** — depends on (3) and (4);
   the actual new detector work, scoped to a SEPARATE, future
   evaluation-first milestone of its own (explicitly not designed in
   implementation detail here).
6. **Shadow comparison of Path B against the live parser**, using the
   Option A runner from (2) extended to a second pathway — depends on
   (5).
7. **Presentation-layer fix for the `_interpretation_status()` risk**
   (Phase 5) — depends on a Stage 3+ decision (out of scope for this
   plan) to surface `qualification_kind` publicly at all; listed last
   because it has no reason to exist before that decision is made.

Steps 1-4 touch no detector logic and carry no fabrication risk by
construction (pure reverse-mapping, evaluation tooling, and a new,
additive lookup table that nothing calls yet). Step 5 is where real,
separately-scrutinized risk begins, and is explicitly deferred to its
own future milestone.

---

## Explicit STOP / architectural approval questions

1. **Approve Path A (compatibility adapter) as the next implementation
   step**, scoped EXACTLY to: `qualification_from_job_requirement()`,
   `qualification_from_unparsed_claim()`, and a round-trip test suite
   against existing regression/frozen corpora — explicitly WITHOUT any
   shadow runner, holdout corpus, or Path B work in the same step?
2. **Approve the Option A offline shadow-evaluation-runner architecture**
   (§Phase 3) as the target design for any future shadow comparison,
   explicitly rejecting Option C (in-API shadow execution) for this
   product's current maturity, and deferring Option B (an importable,
   independently-callable shadow function) until a second real consumer
   of it exists?
3. **Confirm the Phase 4 holdout-corpus methodology** (sourced
   independently of development material, frozen by hash before
   extractor code exists, annotated independently of any candidate
   extractor's output, stratified by domain/style) as the standard a
   future Path B milestone must meet — while explicitly NOT authorizing
   the corpus's actual content to be authored yet?
4. **Confirm the Phase 5 observability/projection analysis** — that
   `UnparsedClaim` remains sufficient for the SAFETY property
   long-term, that the `_interpretation_status()` presentation risk is
   acknowledged and deferred (not fixed) until a Stage 3+ public-surface
   decision, and that the score-denominator detection method
   (before/after `assessable_count`/`alignment_score` diffing across
   frozen gold) is the required review mechanism for any future wiring
   change?
5. **Confirm NO Path B extraction work, no `qualification_kind`
   wiring into `JobRequirement.category`, and no technical-competency
   observability table begins in this same approval** — each is listed
   in the dependency-ordered plan above only as a FUTURE, separately-
   approved step?

---

**STOP — architecture and shadow-integration design review only. No
production code was modified (confirmed: `git diff --name-only --
src/gitscore` empty for this milestone's own work). No commit was made.
The five previously-untracked M11 generalization files, Stage 1's own
committed module, and all frozen historical gold remain exactly as they
were. Awaiting approval on the five questions above before any
implementation.**

---

## Implementation addendum (Stage 2B -- Path A adapter + offline harness)

All five STOP questions were approved: Q1 (Path A) approved; Q2
(Option A offline runner) approved; Q3 (holdout methodology, content
deferred) approved; Q4 (observability/projection analysis,
presentation risk deferred) approved; Q5 (no Path B) confirmed. The
approval message bundled Q1 and Q2 into one combined implementation
pass (Path A adapter AND the offline harness together) rather than
strictly sequencing them as this document's own dependency-ordered
plan suggested -- a reasonable scheduling choice by the approver, not
a contradiction of either answer (both were independently approved on
their own merits; nothing about building them together changes what
either one does).

### Correction: full-fidelity round trip (held before commit)

The first Stage 2B pass achieved round-trip equality on seven named
fields but NOT on `importance` or `category`'s raw string --
`project_qualification()` has no way to reconstruct either (no
`importance` field on `Qualification` at all; `category` is always
written back as `qualification_kind.value`). Commit was held
specifically because "full `JobRequirement` dataclass equality" is the
real bar, and because one concrete, measured consequence of the
`category` gap (the two existing placeholder categories both
collapsing to `"other_legitimate"`, silently changing
`api/serialization.py`'s own `interpretation_status`) is a real
behavior change, not merely an abstract one.

Three fix shapes were weighed (see `qualification_adapter.py`'s own
module docstring for the full reasoning): (B) broaden `Qualification`
itself with new fields -- rejected, since that reopens Stage 1's own,
separately-approved scope decision outside this correction's scope;
(C) report every requirement whose `importance`/`category` cannot
round-trip as `UnsupportedAdapterCase` -- technically sound, but
measured (in the held-back version) to affect 237/265 requirements
(89%), which would make Path A nearly useless for its stated purpose;
(A) a typed, adapter-internal compatibility envelope,
`AdaptedQualification`, carrying the `Qualification` PLUS the two
legacy scalars verbatim -- **chosen**. No public schema anywhere
changes: `Qualification`/`JobRequirement`/`UnparsedClaim` are all
exactly as before; `AdaptedQualification` is new, adapter-only, never
imported by production code.

### What shipped

1. **`src/gitscore/jobs/parsing/qualification_adapter.py`** (new,
   standalone -- confirmed not imported by `parser.py`/`segmentation.py`/
   `necessity.py`/`narrative.py` by a dedicated test, exactly like
   `qualification.py` itself) --
   - `qualification_from_job_requirement()`/`qualification_from_unparsed_claim()`
     -- the Stage-1-only view (unchanged from the first pass),
     documented as NOT achieving full round-trip equality on its own.
   - `AdaptedQualification` (new, frozen, adapter-internal) --
     `qualification` + `legacy_importance` + `legacy_category`, the
     latter two preserved verbatim, never equated with
     `qualification_kind`.
   - `adapt_job_requirement()`/`job_requirement_from_adapted()` -- the
     FULL-FIDELITY round trip. The latter calls the EXISTING,
     unmodified `project_qualification()` first (every Stage 1 safety
     rule still applies unchanged), then `dataclasses.replace()`s the
     two legacy scalars back onto the safely-projected result. Raises
     `UnsupportedAdapterCase(reason="unsafe_projection")` if that
     projection were ever unsafe (not observed for any real-parser
     output -- confirmed by the harness's own 0 count below -- but not
     assumed impossible).
   - `_qualification_kind_for_requirement()` -- unchanged: derives
     `QualificationKind` from STRUCTURAL facts only (§1.10's own
     finding), used ONLY to shape the internal `Qualification`, never
     written back as `category`.
   - `UnsupportedAdapterCase` -- unchanged, still the one genuine
     construction-blocking case (`source_span=None`).
2. **`tests/test_m11b_stage2b_qualification_adapter.py`** (26 tests,
   2 more than the held-back version) -- every test that previously
   asserted a field "does NOT round-trip" (the documented gaps) now
   asserts the OPPOSITE -- full equality -- plus two new tests:
   `test_qualification_kind_is_never_written_back_as_category` and
   `test_unsafe_projection_raises_unsupported_adapter_case_rather_than_a_changed_object`.
3. **`scripts/evaluate_m11b_stage2b_compatibility.py`** (same seven
   fixture sources, 184 fixtures, unchanged) -- rewritten to use the
   full-fidelity path and report six separate dimensions: full-object
   equality, core-field equality, serialized-output equality,
   scoring-denominator equality (verified by actually calling
   `match_requirement()` against an empty candidate profile for both
   the original and reconstructed requirement, not inferred from field
   equality), placeholder-category identity preservation, and
   unsupported-adapter-case count -- never conflated with each other.

No change to `jobs/parsing/parser.py`, `jobs/parsing/segmentation.py`,
`jobs/parsing/qualification.py`, `matching/`, `scoring/`, `api/`,
`frontend/`, the concept registry, or any frozen evaluation gold --
confirmed via `git diff --name-only -- src/gitscore`, which shows only
the one file (`qualification_adapter.py`) added.

### Phase 2 harness results (measured, not estimated)

| Metric | Count |
|---|---|
| Fixtures processed (raw descriptions, across all 7 sources) | 184 |
| `JobRequirement`s produced by the real parser | 265 |
| -- **full dataclass equality** after round trip | **265 / 265 (100%)** |
| -- core-field equality | 265 / 265 (100%) |
| -- serialized-output equality | 265 / 265 (100%) |
| -- scoring-denominator equality (verified via `match_requirement()`) | 265 / 265 (100%) |
| -- unsupported adapter case | 0 |
| -- reconstruction mismatch (an adapter bug) | **0** |
| -- placeholder-category rows, identity preserved | **37 / 37 (100%)** |
| `UnparsedClaim`s produced by the real parser | 98 |
| -- full dataclass equality after round trip | **98 / 98 (100%)** |
| -- serialized-output equality | 98 / 98 (100%) |
| -- unsupported adapter case | 0 |
| -- reconstruction mismatch | **0** |

**Interpretation:** every one of the two previously-disclosed gaps
(`importance`, `category`'s raw string) is now closed -- confirmed by
a direct re-run, not inferred. `importance` and `category` are
preserved exactly for all 265 requirements, including the 37 whose
category is one of the two existing placeholder strings
(`"unresolved_requirement"`/`"alternative_requirement"`), confirmed
individually preserved rather than collapsed. No `UnsupportedAdapterCase`
was raised for any real fixture; the one reachable case (missing
`source_span`) remains exercised only by a synthetic, hand-built test
fixture, exactly as before.

### The previously-reported serialization risk is now resolved as a consequence, not a separate fix

The prior version found that `api/serialization.py::_interpretation_status()`'s
`_UNPARSED_PLACEHOLDER_CATEGORIES` check would silently reclassify a
`NOT_ASSESSABLE` match's `interpretation_status` from
`"unparsed_placeholder"` to `"non_technical"` after a round trip,
because both placeholder categories collapsed to `"other_legitimate"`.
With `legacy_category` now preserved exactly, `reconstructed.category`
equals the original string in every case, so
`_interpretation_status()` (never itself modified) now computes the
IDENTICAL result for the reconstructed requirement as for the
original -- confirmed directly
(`test_interpretation_status_is_preserved_for_the_two_existing_placeholder_categories`).
No change to `api/serialization.py` was needed or made; the fix is
entirely in the adapter's own fidelity.

### Phase 4 -- Observability and projection policy, by category

| `QualificationKind` | Can GitHub plausibly support it? | What evidence would be needed | What evidence is insufficient | When is `NOT_ASSESSABLE` appropriate | Extraction support today | Matching support today | Future work |
|---|---|---|---|---|---|---|---|
| `SPECIFIC_TECHNOLOGY` | Yes -- `STRONGLY_OBSERVABLE` (`observability.py::TECHNICAL_DEFAULT_OBSERVABILITY`, a single constant) | Dependency manifests, source files, config, substantive usage of the named technology | A single trivial/boilerplate file mentioning the name once | Never, for a resolved concept with evidence present (`SUPPORTED`/`NOT_OBSERVED` instead) | Full (`find_concept_mentions`, `find_bare_short_alias_mentions`, `find_conservative_unknown_terms`) | Full (`matching/support.py::has_sufficient_evidence`) | None identified |
| `TECHNICAL_COMPETENCY` | **It depends -- no single answer**, confirmed by the two sharpest corpus contrasts: "concurrency" (`PARTIALLY_OBSERVABLE` -- implementations, benchmarks, commit messages referencing race conditions are plausible but inconclusive proxies) vs. "circuit theory" (`NOT_OBSERVABLE` -- a hardware-design domain, no software artifact exists regardless of specificity) | Domain-specific artifacts (concurrent data structure implementations, profiling/benchmark tooling, commit-message content) -- never a dependency-manifest scan | A single file touching a related library (e.g. importing `asyncio`) is not evidence of UNDERSTANDING concurrency, only of using a tool that offers it | When the competency's own domain has no software artifact at all (circuit theory, analog hardware, etc.) -- always; otherwise, when no qualifying artifact is found | **None** -- confirmed structurally absent (§1.4), zero detector anywhere | **Partial, already safe** -- a `Qualification` with a `competency_tag` (no `concept_id`) correctly projects to a `JobRequirement` the EXISTING matcher already resolves to `NOT_ASSESSABLE` (§Phase 5's own finding: `PARTIALLY_OBSERVABLE` + no concept mapping -> `NOT_ASSESSABLE`, confirmed by reading `matching/engine.py` directly) -- never falsely `SUPPORTED` | A THIRD observability policy table, keyed by `competency_tag` (not `category`, not concept mention) -- does not exist in any form today; a prerequisite for any Path B competency extractor (dependency-ordered plan step 4) |
| `EDUCATION` | No -- `NOT_OBSERVABLE` | None plausible | Enrollment/degree status has no repository-level analogue | Always | Full (`non_technical.py`'s `education` pattern) | Full | None identified |
| `EXPERIENCE` | Mostly no; `PARTIALLY_OBSERVABLE` only for an ARTIFACT-shaped claim ("shipped at least one production web application" -- a deployed, non-trivial repository is a genuine if imperfect proxy); bare years-of-experience is `NOT_OBSERVABLE` (commit-history timespan is a weak, never-asserted proxy; professional/paid status is never GitHub-visible at all) | A deployed, non-trivial repository structure (CI/CD config, a live-looking app) for the artifact-shaped case; nothing for the bare-years case | Commit-history timespan alone, for a years-of-experience claim | Always for bare years-of-experience; when no qualifying artifact is found for the artifact-shaped case | Full for bare years-of-experience (`experience.py::find_experience_qualifier`); **none** for the artifact-shaped distinction (not detected as a different case today) | Full | A detector distinguishing "shipped X" (artifact-shaped) from "N years of experience" (bare) -- not scoped by this milestone |
| `NONTECHNICAL` | No -- `NOT_OBSERVABLE` (legal/soft-skill), or `PARTIALLY_OBSERVABLE` (leadership -- "mentor\*"/"manage... a team" wording, same weak-proxy caveat as artifact-shaped experience) | None defensible for legal/soft-skill; for leadership, a plausible but never-asserted proxy (repository ownership patterns, PR review volume) | README/PR-description tone as a proxy for communication skill | Always for legal/soft-skill; when no qualifying proxy exists for leadership | Full (`non_technical.py`'s `legal`/`soft_skill`/`leadership` patterns) | Full | None identified |
| `OTHER_LEGITIMATE` | Varies by instance -- the sharpest corpus contrast in either direction: open-source contributions (`STRONGLY_OBSERVABLE`, no concept to normalize against at all, yet the single most directly GitHub-native claim possible) vs. the two existing conservative placeholders (`alternative_requirement`/`unresolved_requirement`, `PARTIALLY_OBSERVABLE`, no concept mapping, correctly `NOT_ASSESSABLE` today) | Cross-repository commit/PR history for open-source contribution claims; nothing for the two placeholder categories (no concept to check) | A single commit to an unrelated repository as "contribution to a well-known open-source project" | For the two placeholder categories, always (no concept mapping exists for them to be checked against); for open-source contributions, when no qualifying cross-repo activity is found | Full for the two placeholders (`parser.py`'s own fallback branches); **none** for open-source-contribution recognition as its own category (no detector assigns this meaning today -- it is, if anything, silently absorbed into `soft_skill`/left `UNINTERPRETABLE`) | Full | An open-source-contribution detector is a genuinely NEW extraction capability, not merely a relabeling -- explicitly Path B scope, not scoped further here |
| `UNINTERPRETABLE` | N/A by definition | N/A | N/A | Always (routes to `UnparsedClaim`, never scored) | N/A -- this is the "we don't know what kind of statement this is" state, not a detector target | N/A -- never reaches the matcher | None -- by construction, this state should shrink only as OTHER kinds' detectors improve, never be "detected" directly |

**Explicitly not implemented by this table:** no new GitHub competency
evidence detector, no matcher change, no scoring change -- this is
documentation of EXISTING policy plus honest gaps, per the Restrictions.

### Phase 5 -- Holdout manifest format (methodology only; no content authored)

Extending Stage 2A's own 5-point methodology with a concrete file
shape, so a FUTURE milestone that is given real, independently-sourced
postings has a ready target to populate -- no instance of this format
is created by Stage 2B; no independently-sourced postings were
available or acquired during this milestone:

```json
{
  "corpus_version": "m11b-holdout:v1",
  "annotation_provenance": "<exact sourcing method, acquisition date, and a statement that the annotator had zero prior exposure to this text>",
  "source_hash_sha256": "<hash of the concatenated raw posting texts, computed BEFORE any extractor code is written against this file>",
  "domain_coverage": ["cybersecurity", "devops_cloud", "electrical", "embedded", "frontend", "fullstack", "general_swe", "systems_performance"],
  "style_coverage": ["bulleted", "prose", "section_structured", "unsectioned"],
  "postings": [
    {
      "id": "<stable id>",
      "domain": "<one of domain_coverage>",
      "style": "<one of style_coverage>",
      "raw_text": "<verbatim posting text>",
      "qualifications": [
        {
          "qualification_kind": "...",
          "source_text": "...",
          "source_span": [0, 0],
          "necessity": "...",
          "applicability_condition": null,
          "logical_composition": "...",
          "normalized_reference": null,
          "github_observability": "...",
          "annotation_notes": "..."
        }
      ]
    }
  ]
}
```

This mirrors `evaluation/m11b/structured_qualification_controls.json`'s
own per-entry shape (reused, not reinvented) at the per-qualification
level, nested under per-posting `raw_text` (new -- the development
corpus is per-claim, not per-posting, since it was never meant to
measure segmentation; a holdout corpus measuring a real extractor DOES
need whole postings, so segmentation-induced errors are visible too).
`source_hash_sha256` is the concrete mechanism for Stage 2A's own
"frozen by content hash before any extractor code is written" rule --
computed once, checked by a future script analogous to
`check_evaluation_staleness.py`, never recomputed to match a later
edit.

### Final verification results

| Check | Result |
|---|---|
| Focused Stage 2B tests | 26/26 passed |
| Focused Stage 1 tests (re-run, unaffected) | 56/56 passed |
| Full backend suite | 1317 pre-existing + 26 new = **1343 passed, 13 skipped** -- skip count/set unchanged |
| Path A round-trip harness | 265/265 requirements, 98/98 UnparsedClaims: **full dataclass equality**, serialized equality, scoring-denominator equality, and placeholder-identity preservation all 100%; 0 mismatches; 0 unsupported cases |
| M11 generalization dev corpus | Byte-identical (`TECHNICAL_COMPETENCY` 1/11, 0 false qualifications, 5 lost, 17 diagnostic-only, 8 observability mismatches) |
| M10A real postings | Byte-identical -- `meets_neither: []` for both SOTI and Manulife |
| M9B preservation | Byte-identical across all 10 named metrics |
| M10D alternatives | Byte-identical (`baseline exact_match=30/41 fabricated=0 regression=0`) |
| M11-A2 line-wrap | Byte-identical "baseline" column across all five corpora; regenerated report files reverted via `git checkout --` after inspection, same practice as Stage 1 |
| Frozen `8c:v1`/`8c:v1.1` | **FRESH, 0 diffs** |
| `evidence_report.json`/`end_to_end_report.json` staleness | Same pre-existing, unrelated drift already disclosed in Stage 1's own report -- unaffected by this milestone's work |
| `git diff --check` | Clean |
| `git diff --name-only -- src/gitscore` | Only `qualification_adapter.py`, new |
| Frozen gold (`evaluation/gold`, `evaluation/gold_v1_1`) | `git diff --stat` empty |

### Remaining extraction limitations (unchanged by this milestone, restated for the final report)

- No Path B extractor exists. `TECHNICAL_COMPETENCY` recall is
  unchanged at 1/11 (9%) -- this milestone adds no new classification
  capability, only a validated reverse-mapping of what already exists.
- The `applicability_condition` detector gap (§1.2) is untouched.
- The `MIXED_UNSUPPORTED` detector gap (§1.5) is untouched.
- The competency-observability third table (Phase 4 above) is
  documented but not implemented -- no code reads it, nothing produces
  a `TECHNICAL_COMPETENCY` `Qualification` from real text yet for it to
  apply to.
- The `_interpretation_status()` presentation risk for the two
  EXISTING placeholder categories is now resolved (as a consequence of
  full `category` preservation, not a separate `api/` change -- see
  the correction section above). A FUTURE `technical_competency`
  category (Stage 3+, not approved) would still need its own review at
  that time -- this adapter does not and cannot pre-empt a category
  that does not exist yet.

### Outstanding, explicitly undone

- **Path B semantic extraction** -- not started, per explicit Restriction.
- **Any new GitHub competency evidence detector** -- not implemented.
- **Public schema/matcher/scoring/API/frontend change** -- confirmed absent.
- **Concept registry expansion** -- none; `_qualification_kind_for_requirement`
  reads the registry's existing categories, never adds to them.
- **Holdout corpus content** -- not authored; only the manifest format
  and methodology are defined.
- **`JOB_DESCRIPTION_PARSER_VERSION` bump** -- none; the adapter is
  unwired, standalone tooling, exactly like Stage 1's own model.
