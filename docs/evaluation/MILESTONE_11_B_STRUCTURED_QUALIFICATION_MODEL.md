# Milestone 11-B — Structured Qualification Representation

Evaluation-first architecture and domain-design milestone. **No
production code was modified, no commit was made.** `src/gitscore` is
untouched; every file this milestone adds is new
(`evaluation/m11b/`, this document). The five previously-created M11
architecture/evaluation files remain exactly as they were — untouched,
uncommitted, never staged.

## 0. Baseline verification (Phase 0)

| Check | Result |
|---|---|
| HEAD / tracking | `main` == `origin/main` (`d4c4331db2f968e9012d29abf8cc26ebc9da85d8`). |
| Parser version | `job_description_parser:v10`. |
| Backend baseline | **1261 passed, 13 skipped**, confirmed via `pytest -q`. |
| Frozen historical gold | Unchanged. |
| Preserved untracked files | `docs/evaluation/MILESTONE_11_GENERALIZABLE_JOB_UNDERSTANDING.md`, `evaluation/m11/`, `evaluation/reports/m11_generalization_report.json`, `scripts/evaluate_m11_generalization.py`, `scripts/evaluation_lib/m11_generalization_probe.py` — all five present, untouched. |

**Not repeating the completed M11 investigation** — this document
treats M11's own findings (§4.1's 9% `TECHNICAL_COMPETENCY` recall, the
whack-a-mole regex ceiling, the bare-common-word-language gap) as
settled, cited rather than re-derived.

**A load-bearing architectural fact found while reading the existing
contracts (Phase 0's own "read before designing" instruction), not
previously documented in M11's own doc:** `gitscore.jobs.types.ParserConfidence`
(`HIGH`/`MEDIUM`/`LOW`) **already exists, is already populated on every
real `JobRequirement` today** (`confidence.py::confidence_for()`,
called from six separate branches of `parser.py::_requirements_from_claim`),
and its own docstring already defines it as "how sure a parser was that
it interpreted a piece of job text correctly... e.g. whether 'experience
with cloud platforms such as AWS or Azure' names AWS and Azure as
independent requirements, as interchangeable alternatives, or merely as
illustrative examples." This is, almost verbatim, Phase 1's own
"interpretation certainty" dimension — already shipped, under a
different name, for an unrelated milestone (6B Part 12), years before
this question was asked. This materially changes the recommended
design (§3.5/§6): interpretation certainty is NOT a new field this
milestone needs to invent.

Also confirmed, directly: `JobRequirement.necessity: Necessity` has
**no `| None` and no default** (`jobs/models.py:121`) — a `JobRequirement`
cannot exist today with an unresolved necessity at all. This is the
precise, concrete reason "qualification kind is known but necessity is
not" is a genuinely NEW representable state the current public schema
cannot hold without either widening `JobRequirement` itself (a real
schema-version bump) or keeping that state OUT of the public schema
entirely (§2/§6).

## 1. A semantic contract — independent dimensions (Phase 1)

| Dimension | Type | New or existing? |
|---|---|---|
| `qualification_kind` | New enum: `SPECIFIC_TECHNOLOGY` / `TECHNICAL_COMPETENCY` / `EDUCATION` / `EXPERIENCE` / `NONTECHNICAL` / `OTHER_LEGITIMATE` / `UNINTERPRETABLE` | **New** — M11's own headline gap (no representation at all for competency today). |
| `source_text` / `source_span` | `str` / existing `SourceSpan` | Existing, reused verbatim. |
| `necessity` | Existing `Necessity` (`REQUIRED`/`PREFERRED`), **or `None`** | Existing enum, UNCHANGED shape (still exactly 2 meaningful values) — "unknown" is the ABSENCE of a value, never a 3rd member. |
| `applicability_condition` | New: `str \| None` (the verbatim conditional clause, e.g. `"unless you can demonstrate equivalent practical experience"`) | **New, separate dimension.** |
| `interpretation_certainty` | **Existing** `ParserConfidence` (`HIGH`/`MEDIUM`/`LOW`) | Existing — see §0's finding. Only the SET of triggers that assign `LOW` needs extending (`confidence.py`), never the enum itself. |
| `logical_composition` | New enum: `SINGLE` / `AND` / `OR_ANY` / `MIXED_UNSUPPORTED` | **New** for `MIXED_UNSUPPORTED` (M10D Root Cause 6's own honest diagnostic value); `SINGLE`/`AND`/`OR_ANY` already exist IMPLICITLY (separate `JobRequirement` rows / `alternative_concept_ids`) but are never named as a value a caller can branch on today. |
| `normalized_reference` | Tagged union: `{concept: <registry id>}` \| `{competency_tag: <free, unregistered slug>}` \| `None` | `concept` existing (`concept_id`/`alternative_concept_ids`); `competency_tag` **new**, deliberately NOT a concept-registry entry (no registry expansion, no detector — a placeholder for a future stage to attach to). |
| `github_observability` | Existing `GithubObservability` (3 values) | Existing, UNCHANGED. |
| `evidence_requirements` | New: `str \| None`, documentary only | **New**, never consumed by the matcher — what WOULD plausibly count as evidence, for a human/future-detector reader, never a scoring input. |

### 1.1 Is CONDITIONAL a necessity value or an applicability dimension?

**Applicability.** `necessity` stays the claim's PRIMARY, stated
reading (`m11b-conditional-01`: `"Bachelor's degree required, unless
you can demonstrate equivalent practical experience"` → `necessity=
REQUIRED`), and `applicability_condition` carries the verbatim
exception/condition as a SEPARATE fact a consumer may act on or
ignore, always falling back safely to the primary necessity if ignored.
Folding `CONDITIONAL` into `Necessity` as a third enum value would
force every consumer (matcher, scoring, API, frontend) to decide what
a "conditional" requirement even MEANS for matching/scoring before
they could compile — exactly the "blindly widen an enum by combining
unrelated dimensions" the brief warns against. Keeping it a separate,
optional, inert-by-default field means every existing consumer that
has never heard of conditions keeps working unchanged (reads
`necessity` exactly as before), while a future, explicitly-approved
consumer can opt into reading `applicability_condition` too.

### 1.2 Is AMBIGUOUS a necessity value or an interpretation-status dimension?

**Interpretation status — and it already has one.** §0's finding
settles this directly: `ParserConfidence.LOW` already exists for
exactly this purpose and is already populated in production for
analogous cases (`alternative_fallback`, `unresolved_requirement_fallback`).
`m11b-ambiguous-necessity-01` (the real M11-A2 fixture's own
self-contradicting sentence) models this exactly: `necessity=REQUIRED`
(the posting's own stated primary claim) + `applicability_condition`
describing the contradiction + `interpretation_certainty=LOW` (the
honest signal that a human, not an automated consumer, should see this
exact caveat). `UNINTERPRETABLE` (a `qualification_kind` member,
`m11b-uninterpretable-01`, `"A strong technical background"`) answers a
DIFFERENT question — "what KIND of statement is this" — not "how sure
are we about some other dimension's value." The two are deliberately
not conflated: a claim can be confidently `UNINTERPRETABLE` (no
ambiguity about the fact that it's uninterpretable) just as easily as
it can be a confidently-typed `SPECIFIC_TECHNOLOGY` claim with `LOW`
certainty about its necessity (`m11b-conditional-02`).

## 2. Compatibility analysis (Phase 2)

| Existing contract | Interaction | Public contract change? |
|---|---|---|
| `Claim` (`segmentation.py`, internal) | Unaffected — `Qualification` (proposed, §6) is built FROM a `Claim` plus the SAME detectors already run on it, never replaces it. | No — `Claim` is already internal-only. |
| `JobRequirement`/`JobRequirementProfile` | **Unaffected in this milestone.** The recommended design (§3, Option C) keeps today's flat shape as the ONLY thing the matcher/scoring/API ever see; `Qualification` is a strictly-internal, PRE-projection representation. | **No**, by design — any eventual widening (e.g. an additive `qualification_kind` field actually landing on `JobRequirement`) is explicitly deferred to its own, separately-approved future milestone (§6, Stage 2+). |
| `UnparsedClaim` | The natural destination for a `Qualification` whose `necessity is None` (unresolved) OR `logical_composition == MIXED_UNSUPPORTED` OR `qualification_kind == UNINTERPRETABLE` — mirrors the EXISTING "zero requirements → `UnparsedClaim`" fallback (M10B's own precedent) exactly; no new diagnostic type needed. | No. |
| Parser diagnostics (`ParserConfidence`) | `confidence.py`'s kind-table gains new entries (an applicability-condition detection, a `MIXED_UNSUPPORTED` detection) mapping to `LOW` — additive to an EXISTING function, not a new mechanism. | No — `ParserConfidence` itself is unchanged; only which detector KINDS exist is extended, mirroring how `HIGH_CONFIDENCE_KINDS`/etc. have been extended before. |
| Matcher (`matching/engine.py`) | **Zero interaction in this milestone.** The `NOT_ASSESSABLE` decision table is keyed on `github_observability` + concept-mapping presence — both UNCHANGED inputs. A `TECHNICAL_COMPETENCY` claim still projects to today's `GithubObservability`/`concept_id=None` shape exactly as any other non-technical claim does; the matcher never sees `qualification_kind` at all in this milestone. | No. |
| Alignment denominator (`assessment/models.py`) | **Zero interaction.** `_assessable_matches()` still excludes `NOT_ASSESSABLE` exactly as today; nothing from this milestone changes which matches are assessable or how the percentage is computed. | No. |
| API (`schemas.py`/`serialization.py`) | **Zero interaction in this milestone** (explicit constraint). Note for a FUTURE stage: `RequirementOut.interpretation_status` (`"recognized"`/`"non_technical"`/`"unparsed_placeholder"`) is an EXISTING, presentation-layer 3-way split computed AFTER matching — a natural future home for surfacing `qualification_kind`-derived facts, but not touched here. | No. |
| Frontend (`RequirementSection.tsx`) | **Zero interaction** (explicit constraint). | No. |
| Evaluation corpora / schema versioning | `evaluation/m11b/structured_qualification_controls.json` (new, this milestone) is NEW held-out material, never conflated with M11's own corpus (reused here only as cited background, per the brief's own explicit instruction). `JOB_REQUIREMENT_SCHEMA_VERSION` (currently 2) is **NOT bumped** — nothing on the public `JobRequirement`/`JobRequirementProfile` shape changes. | No schema-version bump in this milestone — see §6 for when one WOULD be needed. |

**Internal-only vs. public-contract changes, summarized:** everything
this milestone recommends implementing in a future stage (§6) is
INTERNAL to `jobs/parsing` — a new `Qualification` dataclass and a
conservative projection function. Nothing recommended here touches
`JobRequirement`'s own shape, the matcher, scoring, the API, or the
frontend. **No newly-represented competency is ever assigned
assessability or score credit** — by construction, the projection step
(§6) maps `TECHNICAL_COMPETENCY`/`UNINTERPRETABLE`/unresolved-necessity
`Qualification`s to the EXACT SAME `UnparsedClaim`/non-technical-row
shapes those claims already produce today, never a new, more generous
`GithubObservability` value.

## 3. Comparing design options (Phase 3)

### Option A — additive internal representation mapped straight into `JobRequirement`

A `Qualification` object exists only transiently inside a detector
function, immediately converted into a `JobRequirement` (or dropped to
`UnparsedClaim`) with no new field ever retained.

| Criterion | Assessment |
|---|---|
| Generality | Low — `qualification_kind`/`applicability_condition`/`logical_composition` are computed then THROWN AWAY; nothing downstream (API, future detectors) can ever read them. |
| Migration complexity | Lowest. |
| Compatibility | Perfect (nothing changes shape). |
| Source provenance | Fine — spans unaffected. |
| Uncertainty handling | Poor — `ParserConfidence`'s existing triggers can be extended, but `applicability_condition`/`MIXED_UNSUPPORTED` have nowhere to live even internally for a future stage to build on. |
| Information loss | **High** — this is the option's defining weakness: every new dimension is computed and discarded in the same function call. |
| Testability | Can only test the FINAL `JobRequirement` shape, never the intermediate semantic judgment directly. |
| Matcher/scoring effect | None. |
| API/frontend effect | None. |

### Option B — versioned `JobRequirement` schema extension

Add `qualification_kind`/`applicability_condition`/`logical_composition`
etc. directly onto `JobRequirement` itself, bumping
`JOB_REQUIREMENT_SCHEMA_VERSION`.

| Criterion | Assessment |
|---|---|
| Generality | High — every consumer (matcher, API, future detectors) can read the richer fields directly. |
| Migration complexity | **Highest** — a real, public schema-version bump; every EXISTING serializer, test fixture, and frozen gold entry that constructs a `JobRequirement` literal needs auditing (confirmed real, not hypothetical: `tests/test_job_requirement_manual_examples.py` and others construct `JobRequirement(...)` directly). |
| Compatibility | Requires care but achievable additively (new fields with defaults) — still a genuine version bump, per `jobs/types.py`'s own documented policy ("Bump... whenever `JobRequirement`... change SHAPE"). |
| Source provenance | Unaffected. |
| Uncertainty handling | Best, if actually built — but §0's non-nullable-`necessity` finding means representing "kind known, necessity unknown" STILL requires either a nullable `necessity` (a behavior-risk: every existing matcher/scoring code path that assumes a real `Necessity` value must be re-audited) or a parallel never-reaches-`JobRequirement` state (which is Option C's own idea, grafted on). |
| Information loss | Lowest, in principle. |
| Testability | Good, but the blast radius of the schema change makes EVERY existing test a candidate for review, not just new ones. |
| Matcher/scoring effect | Not required to change immediately, but the TEMPTATION to let `qualification_kind` leak into `NOT_ASSESSABLE` logic is real and must be explicitly resisted (Phase 2's own constraint). |
| API/frontend effect | None required immediately, but the schema is now public-shaped for a change nothing in M11-B asked for yet. |

### Option C (recommended) — two-stage: internal `Qualification` extraction → conservative projection

A new, internal-only `Qualification` dataclass (every field in §1)
built from a `Claim` using the SAME detectors `_requirements_from_claim`
already calls (concept resolution, non-technical patterns, experience
qualifier, the narrative/necessity gating from M10E–M11-A2) — NEVER a
second, independently-drifting interpretation of the same text. A
**projection function** then maps each `Qualification` into EITHER a
`JobRequirement` (when `necessity` is resolved AND `logical_composition`
is representable as `SINGLE`/`AND`/`OR_ANY`) OR an `UnparsedClaim`
(when `necessity is None`, `qualification_kind == UNINTERPRETABLE`, or
`logical_composition == MIXED_UNSUPPORTED`) — the EXACT SAME two
destinations that exist today, never a third.

| Criterion | Assessment |
|---|---|
| Generality | High — the full semantic contract (§1) exists and is testable on its own, independent of what gets projected. |
| Migration complexity | **Low** — no public schema change, no `JOB_REQUIREMENT_SCHEMA_VERSION` bump, no existing test/fixture needs auditing. |
| Compatibility | Perfect for every EXISTING consumer (matcher/API/frontend see byte-identical `JobRequirement`/`UnparsedClaim` shapes); a FUTURE consumer that wants the richer `Qualification` directly (e.g. a recruiter-facing mode, explicitly named in CLAUDE.md's own long-term direction) has a real, tested object to build against without a second migration. |
| Source provenance | Preserved exactly — `Qualification.source_span` is the SAME `SourceSpan` type, computed the same way. |
| Uncertainty handling | Best achievable without a public schema change — `necessity: Necessity \| None` is legal on an INTERNAL dataclass with no `__post_init__` invariant forcing it non-null (unlike `JobRequirement`). |
| Information loss | Lowest of the three options that ship SOMETHING in this milestone's own implementation-stage recommendation (Option A) — nothing is computed and thrown away; it is computed, retained on `Qualification`, and ONLY discarded at the projection boundary, which is the one place information loss is actually intended (the public contract staying conservative). |
| Testability | Best — `Qualification` extraction and the projection function are two independently unit-testable stages, mirroring M11-A2's own successful "prototype a stage, measure it, then land it" discipline. |
| Matcher/scoring effect | None — confirmed by construction, not merely intended. |
| API/frontend effect | None — confirmed by construction. |

### 3.1 Recommendation

**Option C.** Not the smallest code diff (Option A is smaller), but the
smallest architecture that is actually DEFENSIBLE against the brief's
own standing instruction ("recommend the smallest defensible
architecture, not necessarily the smallest code diff"): it is the only
option that preserves the new semantic information anywhere durable
without forcing a public schema migration before any real consumer of
the richer shape exists.

## 4. Evaluation (Phase 4)

`evaluation/m11b/structured_qualification_controls.json` — **21 NEW,
independently-annotated worked examples**, covering every category the
brief named: technology requirements, technical competencies (3,
including the sharpest cross-axis contrasts — `m11b-competency-02`
circuit theory, maximally specific and REQUIRED yet categorically
`NOT_OBSERVABLE`), education, professional experience (including the
`"shipped at least one production web application"` shape that is
genuinely more observable than a bare years-count), non-technical
qualifications, conditional requirements (2), ambiguous necessity (the
real M11-A2 self-contradiction fixture, re-modeled under the new
contract), illustrative vs. exhaustive alternatives (side by side,
`m11b-illustrative-01`/`m11b-exhaustive-01`), a mixed AND-of-ORs
structure (M10D's own Root Cause 6, given its first honest
representation — `MIXED_UNSUPPORTED` — rather than a silent
flattening), two sentences each carrying multiple independent
qualifications (mirroring Milestone 6A's own original "one sentence,
two `JobRequirement` rows" precedent), two explicit qualifications
appearing outside any formal section, one genuinely `UNINTERPRETABLE`
claim, and one `OTHER_LEGITIMATE` GitHub-native claim with no
technology concept at all (open-source contribution history) —
deliberately placed next to `m11b-competency-02` as the sharpest
possible demonstration that "is this a real qualification" and "can
GitHub evidence speak to it" are independent in BOTH directions.

**Reused, not re-described:** `evaluation/m11/corpus.json` (M11's own
9-posting, 68-claim corpus) is cited only as qualitative DEVELOPMENT
background (§0) — none of its sentences are reproduced here, and
nothing in this document claims it as newly held-out material.

**Frozen gold:** untouched; nothing in `evaluation/gold*` was read as a
source of new annotations or modified.

**Expected outcomes were not adjusted to match implementation
limitations** — e.g. `m11b-mixed-01`'s `MIXED_UNSUPPORTED` value is
recorded as the CORRECT, honest answer precisely BECAUSE no
implementation in this milestone (or M10D) can safely resolve it
further; the control does not pretend a resolution exists.

## 5. GitHub evidence boundary (Phase 5)

| `qualification_kind` | Can public GitHub evidence plausibly support it? | Needs a specialized detector? | Reliably assessable today? | Needs human evaluation / evidence unavailable to GitScore? |
|---|---|---|---|---|
| `SPECIFIC_TECHNOLOGY` | **Yes**, directly (`STRONGLY_OBSERVABLE`) | No — the existing concept registry + dependency/import scan already IS the detector. | Yes. | No. |
| `TECHNICAL_COMPETENCY` | **Sometimes**, and ONLY via a fundamentally different evidence model than a dependency scan (profiling scripts, benchmark suites, algorithm implementations, commit-message content-analysis) — `m11b-competency-01`/`m11b-nested-competency-01`. | **Yes, always** — no such detector exists or is proposed in this milestone (explicit constraint: "Do not implement technical competency detectors"). | **No**, not today, for any competency. | Partially — even a future detector could only ever show CODE CONSISTENT WITH the competency, never confirm UNDERSTANDING (`m11b-competency-01`'s own evidence-requirements note). |
| `TECHNICAL_COMPETENCY` (hardware/domain-specific, e.g. circuit theory) | **No**, categorically — not a detector gap, a domain fact (`m11b-competency-02`). | N/A — no detector could ever close this gap. | No, and never will be via GitHub evidence alone. | Yes, entirely. |
| `EDUCATION` | No. | No (nothing to detect). | No. | Yes, entirely (a credential fact, not a code fact). |
| `EXPERIENCE` (bare years-count) | No. | No. | No. | Yes — a dated/durational claim with no repository analogue. |
| `EXPERIENCE` (artifact-shaped, e.g. "shipped a production application") | **Weakly, yes** (`PARTIALLY_OBSERVABLE`) — `m11b-experience-02`. | Arguably — "does this repository look production-deployed" is a real, if fuzzy, detection question, not implemented here. | Not reliably today. | Partially. |
| `NONTECHNICAL` | No (soft skills, legal status, communication). | No. | No. | Yes, entirely. |
| `OTHER_LEGITIMATE` (e.g. open-source contribution history) | **Yes, directly and strongly** — the sharpest case where GitHub evidence is the NATIVE signal (`m11b-github-native-01`). | No — contribution/commit history is already visible to today's evidence-extraction layer; what's missing is a QUALIFICATION-KIND categorization for it, not a new detector. | Today: no `JobRequirement` category exists for it at all (falls through every detector, becomes `UnparsedClaim`) — a RECALL gap, not an observability gap. | No. |
| `UNINTERPRETABLE` | Not applicable — the claim's own nature is undetermined. | N/A. | No. | Yes — a human reading the original text is the only way to resolve it. |

**The distinction the mission asked to make explicit:** "GitScore
recognizes this competency" (a `qualification_kind` classification —
what §6's `Qualification` stage would provide) is **categorically
different** from "GitScore has defensible evidence that the candidate
demonstrates it" (an evidence/observability judgment — what
`GithubObservability` + a real detector would need to jointly provide,
which THIS milestone explicitly does not build). Recognizing that
`"Deep understanding of concurrency"` IS a `TECHNICAL_COMPETENCY`
claim, worth preserving and surfacing honestly to a user, is not the
same act as, and must never be presented as equivalent to, confirming
that a specific candidate has that understanding. Every `TECHNICAL_COMPETENCY`
`Qualification` this milestone's own design would classify still
projects to `GithubObservability.NOT_OBSERVABLE`/`PARTIALLY_OBSERVABLE`
with `concept_id=None` — i.e. still `NOT_ASSESSABLE` at the matcher,
exactly as every such claim is today, un-scored, by construction.

## 6. Architecture proposal (Phase 6)

### 6.1 Proposed domain model

```python
# jobs/parsing/qualification.py -- NEW, INTERNAL-ONLY module.
# Never imported by matching/, assessment/, api/, or frontend/.

class QualificationKind(str, Enum):
    SPECIFIC_TECHNOLOGY = "specific_technology"
    TECHNICAL_COMPETENCY = "technical_competency"
    EDUCATION = "education"
    EXPERIENCE = "experience"
    NONTECHNICAL = "nontechnical"
    OTHER_LEGITIMATE = "other_legitimate"
    UNINTERPRETABLE = "uninterpretable"

class LogicalComposition(str, Enum):
    SINGLE = "single"
    AND = "and"
    OR_ANY = "or_any"
    MIXED_UNSUPPORTED = "mixed_unsupported"

@dataclass(frozen=True)
class NormalizedReference:
    concept_id: str | None = None                 # existing registry id
    alternative_concept_ids: tuple[str, ...] = ()  # existing OR-group shape
    competency_tag: str | None = None              # NEW, free, unregistered
    exhaustive: bool | None = None                 # NEW -- illustrative vs exhaustive, §4's own gap

@dataclass(frozen=True)
class Qualification:
    qualification_kind: QualificationKind
    source_text: str
    source_span: SourceSpan                 # EXISTING type, reused verbatim
    necessity: Necessity | None              # EXISTING enum; None = unresolved
    applicability_condition: str | None = None
    interpretation_certainty: ParserConfidence = ParserConfidence.HIGH  # EXISTING enum
    logical_composition: LogicalComposition = LogicalComposition.SINGLE
    normalized_reference: NormalizedReference | None = None
    github_observability: GithubObservability | None = None  # EXISTING enum
    evidence_requirements: str | None = None  # documentary only
```

### 6.2 Example structured qualification objects

```python
# "Experience with Rust is required." (m11b-tech-01)
Qualification(
    qualification_kind=QualificationKind.SPECIFIC_TECHNOLOGY,
    source_text="Experience with Rust is required.",
    source_span=SourceSpan(...),
    necessity=Necessity.REQUIRED,
    interpretation_certainty=ParserConfidence.HIGH,
    logical_composition=LogicalComposition.SINGLE,
    normalized_reference=NormalizedReference(concept_id="language.rust"),
    github_observability=GithubObservability.STRONGLY_OBSERVABLE,
)

# "Deep understanding of concurrency... is required." (m11b-competency-01)
Qualification(
    qualification_kind=QualificationKind.TECHNICAL_COMPETENCY,
    source_text="Deep understanding of concurrency and lock-free data structures is required.",
    source_span=SourceSpan(...),
    necessity=Necessity.REQUIRED,
    logical_composition=LogicalComposition.AND,
    normalized_reference=NormalizedReference(competency_tag="concurrency"),
    github_observability=GithubObservability.PARTIALLY_OBSERVABLE,
    evidence_requirements="Lock-free data structure implementations, benchmark/profiling tooling.",
)

# The real M11-A2 self-contradiction fixture (m11b-ambiguous-necessity-01)
Qualification(
    qualification_kind=QualificationKind.EXPERIENCE,
    source_text="5+ years of professional Go experience is required for this role, however, ...",
    source_span=SourceSpan(...),
    necessity=Necessity.REQUIRED,
    applicability_condition="unless the candidate is an 'exceptional entry-level candidate'",
    interpretation_certainty=ParserConfidence.LOW,
)
```

### 6.3 Old-to-new mapping (projection function)

```
Qualification -> JobRequirement, iff:
    necessity is not None
    AND logical_composition in (SINGLE, AND, OR_ANY)
    AND qualification_kind != UNINTERPRETABLE
  -- byte-for-byte the SAME JobRequirement shape produced today,
     github_observability/concept_id/category computed by the
     EXACT SAME unchanged detectors Qualification wraps.

Qualification -> UnparsedClaim, iff:
    necessity is None
    OR logical_composition == MIXED_UNSUPPORTED
    OR qualification_kind == UNINTERPRETABLE
  -- the SAME two conditions (unresolved necessity; an unsafe/
     unsupported structure) that already route to UnparsedClaim today,
     now with an HONEST, named reason instead of an implicit one.
```

No case exists where a `Qualification` produces something NEITHER a
`JobRequirement` NOR an `UnparsedClaim` would already represent today —
the projection is a RENAME of existing destinations, not a third one.

### 6.4 Information-loss risks

- Every field NOT projected (`applicability_condition`,
  `logical_composition` beyond what `alternative_concept_ids` already
  encodes, `evidence_requirements`, `competency_tag`,
  `exhaustive`) is **lost at the projection boundary** in Stage 1
  (§6.5) — by design, since nothing downstream can read it yet. This is
  an explicit, accepted cost: the alternative (Option B) pays a public
  schema migration to avoid it before any real consumer exists.
- `m11b-conditional-01`'s own implicit SECOND qualification (the
  "equivalent practical experience" substitute) is flagged, not
  resolved — the proposed model does not attempt to SPLIT one sentence
  into two `Qualification` objects when the second is only implied, not
  separately stated. A future stage could; this one does not claim to.

### 6.5 Proposed implementation stages (none implemented in this milestone)

1. **Stage 1** (smallest, matches Option C exactly): add
   `jobs/parsing/qualification.py` (new module, `Qualification`
   dataclass + the projection function), wire it into
   `_requirements_from_claim` as a THIN wrapper (the function computes
   a `Qualification` first, then immediately projects it) — net
   behavior change: **zero**, confirmed by construction (the projection
   rules are the SAME two existing destinations). Purely a refactor
   that gives the next stage something to build on, independently
   testable against `evaluation/m11b/`'s own 21 controls.
2. **Stage 2** (separately approved): extend `confidence.py`'s kind
   table so `applicability_condition` detection and
   `MIXED_UNSUPPORTED` detection genuinely assign `ParserConfidence.LOW`
   — still no public schema change.
3. **Stage 3** (separately approved, likely its own milestone): decide
   whether `qualification_kind` (or a derived summary of it) should
   surface on the PUBLIC API at all, e.g. via `RequirementOut`'s
   existing `interpretation_status` field gaining a value, or a new
   field — the FIRST point any of this touches a public contract, and
   explicitly out of scope here.
4. **Stage 4+** (not before Phase 5's own boundary is product-approved):
   any technical-competency EVIDENCE detector at all — explicitly not
   proposed, scoped, or estimated by this milestone.

### 6.6 Schema versioning

**No `JOB_REQUIREMENT_SCHEMA_VERSION` bump in Stage 1** — `JobRequirement`'s
own shape is untouched. A bump would first become necessary at Stage 3
or later, IF a decision is made to surface any new field on the public
model — a decision this document does not make.

## Explicit STOP / architectural approval questions

1. **Approve Option C** (two-stage internal `Qualification` extraction
   → conservative projection, §3.1) as the target architecture for a
   future, separately-approved implementation milestone?
2. **Approve Stage 1 alone** (§6.5 — the `Qualification` dataclass +
   projection function, net behavior change zero, confirmed by
   construction) as the smallest next implementation step, explicitly
   WITHOUT Stages 2–4?
3. **Confirm `applicability_condition` is modeled as a separate,
   optional field** (never a `Necessity` enum value) and
   **`interpretation_certainty` reuses the EXISTING `ParserConfidence`
   enum** (never a new field) — per §1.1/§1.2's own investigation
   findings?
4. **Confirm no public schema change, matcher change, scoring change,
   API change, or frontend change is approved in ANY stage of this
   milestone's own recommendation** — Stage 3 (§6.5) is named here only
   as a FUTURE option, not a request for approval now?
5. **Confirm the GitHub-evidence boundary (§5) — "GitScore recognizes
   this competency" vs. "GitScore has defensible evidence of it" — is
   accepted as a product/documentation distinction to be upheld in any
   future stage**, with no technical-competency detector or evidence
   policy proposed, scoped, or approved by this milestone?

---

**STOP — architecture and domain-design decision only. No production
code was modified. No commit was made. All five previously-untracked
M11 design/evaluation files remain exactly as they were. Awaiting
approval on the five questions above before any implementation

---

## Implementation addendum (post-approval, Stage 1 only)

All five questions were approved: Q1 (Option C) approved; Q2 approved
with an explicit NARROWING — Stage 1 must build the `Qualification`
model and `project_qualification()` as a **standalone, unwired**
module, not as a thin wrapper rerouting `_requirements_from_claim`
(§6.5's own Stage 1 sketch described wiring it in; the approval
message overrode that specific detail: *"Stage 1 must not reroute the
production parser through this new model yet"*); Q3 approved exactly
as investigated (`applicability_condition` stays a separate optional
field, never a `Necessity` value; `interpretation_certainty` reuses
the existing `ParserConfidence` enum, never a new type); Q4 approved
(zero public-contract changes in any stage, Stage 1 included); Q5
approved (the GitHub-observability boundary from §5 is a documentary
distinction only — no competency detector, no auto-upgrade of
`github_observability` by `qualification_kind`).

### What shipped

1. **`src/gitscore/jobs/parsing/qualification.py`** (new file, zero
   existing files modified) —
   - `QualificationKind` (7 values per §1's table), `LogicalComposition`
     (`SINGLE`/`AND`/`OR_ANY`/`MIXED_UNSUPPORTED`).
   - `NormalizedReference` (frozen) — `concept_id` XOR
     `alternative_concept_ids` XOR `competency_tag`, enforced in
     `__post_init__` so a bare competency slug can never reach
     `JobRequirement.concept_id` by construction, not by convention.
   - `Qualification` (frozen) — every Phase-1 dimension from §1's table
     as a field, reusing `SourceSpan`/`Necessity`/`ParserConfidence`/
     `GithubObservability` verbatim; no `importance` field (not a
     Phase-1 dimension; see placeholder below).
   - `ProjectionResult` (frozen) — exactly one of `job_requirement` /
     `unparsed_claim` populated; `unsafe_reason` set iff the latter.
   - `project_qualification()` — the conservative projection function.
     Routes to `UnparsedClaim` (never a coerced `JobRequirement`)
     whenever: `necessity is None`; `github_observability is None`;
     `logical_composition is MIXED_UNSUPPORTED`; `qualification_kind
     is UNINTERPRETABLE`; or `applicability_condition is not None`
     (no field exists on `JobRequirement` to hold it, so a condition is
     never silently dropped — it survives verbatim inside
     `UnparsedClaim.text`, the original sentence). A `JobRequirement`
     construction `ValueError` (e.g. a malformed `concept_id`) is
     caught and falls back to `UnparsedClaim(unsafe_reason=
     "invalid_normalized_reference")` rather than crashing — defense
     in depth, not a new validation rule; `JobRequirement`'s own
     existing validation is the sole source of truth.
   - `_STAGE_1_PLACEHOLDER_IMPORTANCE = Importance.MEDIUM` — an
     explicit, documented neutral placeholder, used only because
     `JobRequirement.importance` is non-nullable and `Qualification`
     has no `importance` field at all (not requested by the mission).
     Never `HIGH`/`LOW`, which would fabricate a judgment never made.
   - One deliberate deviation from this document's own §6.1 sketch:
     `interpretation_certainty` defaults to `None`, not
     `ParserConfidence.HIGH`. Defaulting to `HIGH` would itself be the
     fabricated-certainty failure mode the approval message's decision
     4 warned against; `None` matches `JobRequirement.parser_confidence`'s
     own existing "not evaluated" meaning.
   - **Not imported by `parser.py`, `segmentation.py`, `necessity.py`,
     or `narrative.py`** — confirmed by a dedicated test
     (`test_module_is_not_imported_by_the_live_parser`), not merely by
     omission.

2. **`tests/test_m11b_qualification_model.py`** (new, 56 tests) —
   covers all 13 requested categories: every `QualificationKind`
   constructs (via the full 21-entry corpus, parametrized); unknown
   necessity never coerced; required/preferred necessity both project;
   material applicability conditions always route to `UnparsedClaim`
   with the condition still visible in its `text`; `interpretation_certainty`
   passes through onto `JobRequirement.parser_confidence` unchanged,
   and is shown independent of necessity (`REQUIRED`+`LOW` vs.
   `None`+`HIGH` are both valid, non-conflated states — the direct test
   for decision 4's nuance); `TECHNICAL_COMPETENCY` never auto-upgrades
   `github_observability` and never receives a `concept_id`; safe vs.
   unsafe projection paths enumerated; illustrative (`exhaustive=False`)
   and exhaustive alternative groups both project correctly;
   `MIXED_UNSUPPORTED` always routes to `UnparsedClaim`; source spans
   preserved exactly (identity-checked, not just equality) on both the
   safe and unsafe path; determinism (same input → equal output twice);
   immutability (`Qualification`/`NormalizedReference`/`ProjectionResult`
   all reject attribute mutation) and constructor validation
   (blank `source_text`/`applicability_condition` rejected, mutually
   exclusive `NormalizedReference` fields rejected, `ProjectionResult`'s
   own invariants rejected when violated).

3. **`evaluation/m11b/structured_qualification_controls.json`** — one
   corpus-authoring bug fixed, discovered while writing the test file:
   `m11b-illustrative-01` referenced `cloud.azure`, which was never a
   registered concept in this codebase (only `cloud.aws` exists under
   `cloud.*`; no Azure/GCP concept exists at all). This is the same bug
   class M11-A2 found and fixed (unregistered `Node.js`/`GraphQL`
   fixtures) — a mechanical reference error, not a semantic redesign.
   Fixed by swapping the illustrative example to a domain with two
   concepts that actually exist (`ml.framework.pytorch`/
   `ml.framework.tensorflow`, "Experience with deep learning frameworks
   such as PyTorch or TensorFlow."), preserving every other annotated
   field (`necessity=REQUIRED`, `interpretation_certainty=LOW`,
   `logical_composition=OR_ANY`, `github_observability=
   STRONGLY_OBSERVABLE`, `exhaustive=false`) — the example's *expected
   outcome* (safe projection demonstrating illustrative/non-exhaustive
   alternatives) is unchanged; only the broken concept reference is
   corrected. No concept-registry change was made or needed.

No change to `jobs/models.py`, `jobs/parsing/parser.py`,
`jobs/parsing/segmentation.py`, `jobs/parsing/necessity.py`,
`jobs/parsing/narrative.py`, `jobs/parsing/confidence.py`,
`jobs/types.py`, `matching/`, `scoring/`, `api/schemas.py`,
`api/serialization.py`, `frontend/`, the concept registry, or any
frozen evaluation gold — confirmed via `git status`/`git diff
--name-only -- src/gitscore`, which shows only the one new file added.
`JOB_DESCRIPTION_PARSER_VERSION` stays `job_description_parser:v10`
(no bump — confirmed by test) since no consumer of the new module
exists yet and no public/behavioral contract changed.

### Final verification results

| Check | Result |
|---|---|
| Focused M11-B tests | 56/56 passed (`tests/test_m11b_qualification_model.py`) |
| Full backend suite | 1261 pre-existing + 56 new = **1317 passed, 13 skipped** — skip count/set unchanged |
| Live-parser isolation | Confirmed by dedicated test — `qualification.py` not imported by any of the four parsing modules |
| Parser version | Unchanged, `job_description_parser:v10` — confirmed by test |
| M11 generalization dev corpus | Byte-identical (`TECHNICAL_COMPETENCY` 1/11 recall, 0 false qualifications, 5 lost, 17 diagnostic-only, 8 observability mismatches — same figures as M11-A2's own baseline) |
| M11-A2 line-wrap evaluation | Byte-identical "baseline" column across all five corpora (33/33, 41/41, 22/22, 82/82, 82/82) — the regenerated report file was reverted via `git checkout --` after inspection, since Stage 1 has no authorization to update this tracked artifact |
| M10A real postings | Byte-identical — `meets_neither: []` for both SOTI and Manulife, 0 false positives, 0 invisible qualifications |
| M9B preservation | Byte-identical (0 spurious creation, 0 fabrication, 1.0 source-span correctness) |
| Frozen `8c:v1`/`8c:v1.1` | **FRESH, 0 diffs** via `scripts/check_evaluation_staleness.py` |
| `evidence_report.json` / `end_to_end_report.json` staleness | Pre-existing, unrelated drift (live-GitHub-profile evidence extraction — `karpathy`/`torvalds`/`sindresorhus`/`Jango1324` cells), not caused by this milestone; `qualification.py` is unimported and cannot affect evidence extraction. Not investigated further — out of scope for a job-description-parser milestone. |
| `git diff --name-only -- src/gitscore` | Empty — only the new, untracked `qualification.py` added |
| Frozen gold (`evaluation/gold`, `evaluation/gold_v1_1`) | `git diff --stat` empty |

### Remaining architectural gaps (explicitly not addressed by Stage 1)

- **Stage 2** (semantic extraction wiring the live parser through this
  model) — not started, not scoped further than §6.5's own outline.
- **Stage 3** (any public-contract surfacing of `qualification_kind`)
  — not started.
- **Stage 4+** (technical-competency evidence detectors) — not
  started, not proposed.
- **The 21-entry corpus's `evidence_requirements` field** is
  documentary only — no code reads it; it exists purely to record each
  example's own reasoning for a human reviewer.
- **No recall/behavior claim is made.** `TECHNICAL_COMPETENCY` recall
  is unchanged at 1/11 — introducing a model that CAN represent a
  competency is not the same as the live parser recognizing more of
  them, and this document makes no such claim.

### Outstanding, explicitly undone

- **Production rerouting** — `_requirements_from_claim` still builds
  `JobRequirement`/`UnparsedClaim` directly; it does not construct a
  `Qualification` first. Deliberately not done per Q2's narrowed
  approval.
- **Any public schema/matcher/scoring/API/frontend change** —
  confirmed absent, not merely asserted.
- **Any new enum value added "for evaluation coverage"** — none added;
  all three new enums (`QualificationKind`, `LogicalComposition`,
  `NormalizedReference`) hold exactly the values described in this
  document's own §1/§6.1, no more.
milestone begins.**
