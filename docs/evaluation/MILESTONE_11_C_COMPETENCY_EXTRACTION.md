# Milestone 11-C — Generalized Technical Competency Extraction (Path B)

**Status: evaluation-first, OFFLINE PROTOTYPE only.** No production code
was modified. No commit was made. The live parser's own call graph is
untouched, confirmed by a dedicated test and by `git diff --name-only --
src/gitscore` showing only new, unimported files added.

## Phase 0 — Verified baseline

| Check | Expected | Actual |
|---|---|---|
| HEAD | `c1f4244560fc7ec9ad7564296828d2449dc8ea60` | confirmed |
| Branch | `main` | confirmed |
| Parser version | `job_description_parser:v10` | confirmed, unchanged |
| Tests | 1343 passed, 13 skipped | confirmed |
| Qualification model (Stage 1) | implemented, unwired | confirmed, untouched by this milestone |
| Qualification adapter (Stage 2B) | implemented, full-fidelity | confirmed, untouched |
| Frozen historical gold | unchanged | confirmed (`git diff --stat` empty) |
| Five M11 generalization files | untracked, preserved | confirmed present |

---

## Phase 1 — The extraction problem, defined

### The 9-way taxonomy (plus the already-solved baseline)

| Category | Already solved by the live parser? | This milestone's own scope |
|---|---|---|
| 1. Named technologies | Yes (`find_concept_mentions`, `classify_alternative_claim`) | Baseline control only — confirm this prototype never regresses or duplicates it |
| 2. Technical competencies | **No** — confirmed structurally absent (M11-B Stage 2A §1.4: zero code path anywhere assigns this category) | **The core target of this milestone** |
| 3. Education / experience | Yes (`non_technical.py`, `experience.py`) | Baseline control only |
| 4. Nontechnical qualifications | Yes (`non_technical.py`) | Baseline control only |
| 5. Responsibilities / job duties | Partially — M10E's own narrative-cue/section-origin logic rejects SOME, not all | Must not be mistaken for a competency claim merely because a competency term appears in a duty bullet |
| 6. Learning opportunities | Yes, for the EXISTING narrow grammatical shapes `narrative.py::contains_narrative_cue` already covers | Reused as-is; measured whether it generalizes to new phrasing (it does, for the one learning-opportunity control exercised here) |
| 7. Company/product narratives | Partially — same `contains_narrative_cue`, confirmed NARROWER than this milestone's own new adversarial phrasing requires (§3.2) | A new, bounded, additive heuristic was required (not a `narrative.py` edit) |
| 8. Administrative/compensation text | Yes, implicitly (no detector fires at all → `UnparsedClaim`) | Baseline exclusion control only |
| 9. Ambiguous statements | Yes, implicitly (`UNINTERPRETABLE` already exists on `Qualification`, Stage 1) | Confirmed this prototype correctly declines rather than guessing |

### The three separated decisions

- **A — Is this an applicant qualification at all?** Decided by sentence-role rejection (narrative/responsibility/learning/negation) before any competency vocabulary is even consulted for KIND.
- **B — What technical competency does it describe?** Decided by the bounded vocabulary table (§3.1) — a closed set of (tag, pattern) pairs, the SAME design `non_technical.py` already uses, never a role-specific keyword list.
- **C — Can GitHub evidence defensibly establish it?** Explicitly OUT OF SCOPE for the extractor itself — handled entirely by the EXISTING `GithubObservability` field plus a new, documentation-only policy lookup table (§5.1) that answers "is this KIND of claim even plausibly checkable at all," never "does THIS candidate's repository actually demonstrate it" (that remains a competency EVIDENCE DETECTOR, explicitly forbidden by this milestone's own Restrictions).

### A meta-finding carried over from Stage 2A, re-confirmed here

A `Qualification` constructing without error is a shape-validity fact,
never a semantic-correctness fact (Stage 2A §1.9). This milestone's
own 45-example corpus (Phase 2) exists specifically because no amount
of unit-testing the EXTRACTOR's own code can substitute for measuring
it against independently-authored sentences it was never tuned against
sentence-by-sentence.

---

## Phase 2 — Evaluation corpus, authored BEFORE any strategy comparison

`evaluation/m11c/competency_extraction_controls.json` — **45 entries**,
authored from first principles (what each SENTENCE means, independent
of any candidate extractor's output) before Phase 3's strategies were
implemented or run against it. M11's own 9 postings and M11-B's 21
semantic examples are cited only as DEVELOPMENT background, per that
corpus's own `annotation_provenance` field — never re-described as
held-out.

### Coverage

| Dimension | Count |
|---|---|
| Total controls | 45 |
| `is_applicant_qualification: true` | 37 |
| `is_applicant_qualification: false` (adversarial/baseline negatives) | 8 |
| `text_category: technical_competency` | 28 |
| Named-technology baseline controls | 4 |
| Education/experience/nontechnical baseline controls | 3 |
| Company-narrative adversarial negatives | 2 |
| Responsibility/duty adversarial negatives | 2 |
| Learning-opportunity adversarial negative | 1 |
| Administrative baseline exclusions | 2 |
| Negated-requirement adversarial negative | 1 |
| Genuinely ambiguous/uninterpretable controls | 2 |

Engineering disciplines covered by the 28 competency rows: algorithms
and data structures, concurrency, distributed systems, system design,
debugging/performance, OS/networking, database design, ML
fundamentals, GPU/parallel computing, signal processing, circuit
theory, embedded systems design, control systems, computer vision,
cybersecurity/threat modeling, digital logic — all 16 of the mission's
own named examples — PLUS one domain deliberately OUTSIDE that list
(quantum computing, `m11c-unrecognized-domain-01`) as the explicit
generalization test.

Other required dimensions, each with at least one dedicated control:
unusual wording (`m11c-concurrency-01`'s "you should be comfortable",
`m11c-sysdesign-01`'s "proven ability to"), requirements outside
formal sections (`m11c-outside-section-01/02`), explicit REQUIRED and
PREFERRED (`m11c-preferred-mixed-01`), ambiguous necessity
(`m11c-perf-01`, `m11c-dbdesign-01`, `m11c-bullet-01`), competency
mixed with a named technology in one sentence
(`m11c-mixed-tech-competency-01`), several competencies in one
sentence — both the "one area, descriptive sub-terms" shape
(`m11c-distsys-01`) and the "genuinely distinct areas" shape
(`m11c-multi-02`), AND/OR relationships (`m11c-orany-01`,
`m11c-exhaustive-02`, `m11c-mixed-logical-01`), competencies in company
descriptions (`m11c-narrative-01/02`), competencies appearing only in
job duties (`m11c-responsibility-01/02`), learning opportunities
(`m11c-learning-01`), negated/excluded requirements (`m11c-negated-01`),
conditional qualifications (`m11c-conditional-01`), formatting/
line-wrap variations (`m11c-linewrap-01`, `m11c-bullet-01`), and an
unrecognized technical domain (`m11c-unrecognized-domain-01`).

### One corpus-authoring bug found and fixed DURING Phase 3 (before any strategy was chosen — not after the fact)

Eleven entries were initially annotated `logical_composition: "and"`
(ten) or `"or_any"` (one, `m11c-cv-01`) for sentences that are
genuinely ONE competency claim phrased with descriptive sub-terms
("deep knowledge of distributed systems, consensus algorithms, and
fault tolerance" — one competency AREA, not three independent
requirements) — inconsistent with this corpus's OWN notes field
(several of which already said "annotated as ONE competency claim")
and with `LogicalComposition`'s own Stage-1 semantics (composition of
the REQUIREMENT, never a scan for the literal word "and"/"such as" in
the English sentence). Fixed to `"single"` for all eleven, discovered
by the SAME mechanism M11-A2/M11-B's own corpus bugs were — running a
real prototype against the annotation and finding a result that forced
re-reading the annotation's own stated intent. See
`docs/CHANGELOG_DEV.md`'s Milestone 11-C entry for the exact eleven ids.

### Holdout protocol (methodology only — no content authored, no tuning against it)

Extending Stage 2A's own 5-point holdout methodology and its JSON
manifest format (`docs/evaluation/MILESTONE_11_B_STAGE_2A_SHADOW_INTEGRATION.md`
Phase 5) unchanged — this milestone adds nothing new to that
methodology, confirms it still applies, and explicitly does NOT author
any holdout content: no independently-sourced, previously-unseen
postings were available during this milestone, and none were
acquired. The 45-entry corpus above remains DEVELOPMENT material,
used to compare and tune Phase 3's strategies — exactly the kind of
material the holdout protocol exists to be measured AGAINST once a
real holdout corpus exists, never a substitute for it.

---

## Phase 3 — Comparing three extraction strategies (real offline prototypes)

Implemented in `scripts/evaluation_lib/m11c_competency_prototypes.py`,
measured by `scripts/evaluate_m11c_competency_extraction.py` against
all 45 corpus controls. All three strategies share the SAME bounded,
17-tag competency vocabulary (§Phase 1 B) — they differ only in
sentence-role handling, which is the actual variable this comparison
isolates.

### Option A — expanded deterministic keyword/phrase recognition

Fires on ANY competency-vocabulary match plus a local necessity
marker, with **no sentence-role awareness at all**.

### Option B — structured extraction using EXISTING linguistic-context infrastructure

Reuses, unmodified: `jobs/parsing/necessity.py::infer_necessity` (called
with a `None` hint, isolating exactly its own LOCAL-marker signal) and
`jobs/parsing/narrative.py::contains_narrative_cue`. Adds two NEW,
bounded, generic signals: a responsibility-lead imperative-verb check,
and three narrow negation patterns.

### Option C — Option B plus a broader, bounded, additive narrative heuristic

Everything Option B has, PLUS `_BROADER_NARRATIVE_SUBJECT` — a new,
generic ("our team"/"we're a"/"the team") pattern, confirmed necessary
by measurement, not assumed: `contains_narrative_cue()` was confirmed
(directly, by running it) to NOT match either of this corpus's two
company-narrative adversarial examples ("Our engineering team has...
built...", "We're a small team solving...") — both escape its three
existing, M10E-tuned alternatives. Never a `narrative.py` edit.

### Measured results (exact numerator/denominator, all three strategies, same corpus)

| Metric | Option A | Option B | Option C |
|---|---|---|---|
| Qualification recall | 28/28 | 28/28 | 28/28 |
| Qualification precision | 28/34 | 28/30 | **28/28** |
| FP — responsibility | 2 | 0 | 0 |
| FP — company narrative | 2 | **2** | 0 |
| FP — learning opportunity | 1 | 0 | 0 |
| FP — negation | 1 | 0 | 0 |
| FP — administrative/baseline | 0 | 0 | 0 |
| Necessity classification | 21/28 | 21/28 | 21/28 |
| Logical grouping | 27/28 | 27/28 | 27/28 |
| Multi-competency splitting | 2/2 | 2/2 | 2/2 |
| Uninterpretable correctly declined | 2/2 | 2/2 | 2/2 |
| Deterministic | Yes | Yes | Yes |
| New heuristics beyond the shared vocabulary | 0 | 2 (responsibility-lead, negation) | 3 (+ broader narrative subject) |

**Recall is identical across all three strategies** — confirming
Phase 3's own instruction not to select a candidate on recall alone;
the actual differentiator is precision, and only Option C reaches
100% on this corpus. The necessity (21/28) and logical-grouping
(27/28) figures are IDENTICAL across all three because they measure a
property of the shared vocabulary/necessity-reuse layer, not of
sentence-role handling — see §Phase 4's own re-measurement against
the REAL module for why these numbers are more informative when
computed correctly (below).

### Complexity / maintenance burden (qualitative)

Option A: ~15 lines beyond the vocabulary table. Option B: +2 bounded
regex-based checks, reusing 2 existing production functions
unmodified. Option C: +1 more bounded regex pattern over Option B. The
marginal complexity from B→C is small (one new pattern) for a
precision gain from 93%→100% — the basis for recommending C as the
"smallest viable" candidate rather than treating A→B's gain as
sufficient and stopping there.

### Recommendation

**Option C.** Zero false positives on every adversarial category this
corpus tests, identical recall/necessity/logical-grouping to A and B,
and the smallest additional complexity that reaches zero FPs (one new
pattern over B, not a new architecture). Per the mission's own
instruction, this was NOT chosen "based solely on recall" — it was
chosen because it is the only strategy with zero measured
false-positive rate while matching the others everywhere else.

---

## Phase 4 — The offline extractor (real implementation)

`src/gitscore/jobs/parsing/competency_extraction.py` (new, standalone
— confirmed not imported by `parser.py`/`segmentation.py`/
`necessity.py`/`narrative.py` by a dedicated test). Implements Option
C's own logic, but produces REAL `Qualification` objects via the
EXISTING, unmodified Stage 1 model, consuming an already-segmented
claim's `text`/`SourceSpan` (the same shape `Claim` already has) —
never calling `segment_description()` itself.

### A genuine missing-contract finding — declined, not invented

`NormalizedReference` (Stage 1, already committed) supports exactly
three shapes: one registered concept (`concept_id`), a GROUP of
registered concepts (`alternative_concept_ids`), or ONE unregistered
competency tag (`competency_tag`). **It has no field at all for a GROUP
of multiple competency tags** — e.g. "at least one of the following:
distributed systems, concurrent programming, or high-performance
computing" (`m11c-orany-01`) names three alternative COMPETENCY
options, none of which is a registered concept. Per this milestone's
own explicit instruction ("If the existing Qualification model cannot
express a necessary state safely, STOP and describe the missing
contract rather than inventing an incompatible default"), the
extractor **declines** this shape entirely
(`DeclinedExtraction(reason="missing_contract", ...)`) — it does NOT
construct a `Qualification` with `normalized_reference=None`, which
would silently discard which specific options the sentence named with
no trace that the loss even happened. The decline's own `detail` text
names every tag found, so nothing is silently dropped even though no
`Qualification` is produced. **A fix would require adding a new field
to `Qualification`'s `NormalizedReference`** (e.g.
`alternative_competency_tags: tuple[str, ...]`) — a Stage-1 model
change outside this milestone's own approval, not made here.

### The "AND of distinct areas" vs. "one area with descriptive sub-terms" distinction

Confirmed safely representable WITHOUT a missing-contract problem: a
genuine AND of several INDEPENDENTLY-named competency areas
(`m11c-multi-02`, "concurrency, distributed systems, and database
design") splits into N sibling `Qualification` objects, each `SINGLE`
with its own `competency_tag` — mirroring Milestone 6A/10E/11-B's own
established "one sentence, multiple qualification objects" precedent
exactly. Distinguished from a single competency area merely DESCRIBED
by several related sub-terms (`m11c-distsys-01`, "distributed systems,
consensus algorithms, and fault tolerance" — one tag, `SINGLE`) by
simple vocabulary-match count: if the SAME tag's own pattern matches
every named sub-term, it is one match, not several.

### Applicability conditions, negation, and MIXED_UNSUPPORTED

All three reuse Stage 1's EXISTING, unmodified safety rules exactly:
a conditional clause ("unless you have equivalent experience with
other forms of parallel computing") is extracted verbatim into
`applicability_condition`, and `project_qualification()`'s own
pre-existing rule (unchanged since Stage 1, never touched by this
milestone) routes it to `UnparsedClaim` with the full original
sentence — including the condition — preserved. A `MIXED_UNSUPPORTED`
shape (an AND of an OR-group, M10D's own Root Cause 6, re-confirmed
here for competencies) is detected via one bounded structural regex
and routed the same safe way.

### Negation — a measured, honest limitation, not claimed as solved generally

Three narrow, closed negation patterns are checked ("no prior
experience... is necessary", "not required", "no need to/for") —
sufficient for this corpus's own one negation control, but this is
explicitly NOT a general negation-detection capability (natural
language negation is a much broader linguistic phenomenon than three
fixed phrases can cover). Stated plainly: this prototype's negation
handling reduces one KNOWN false-positive shape to zero on THIS
corpus; it is not validated against the open-ended space of possible
negation phrasings, and no such claim is made.

---

## Phase 5 — Observability and projection safety (verified, not assumed)

### The core requirement, confirmed empirically

> Technical competency extraction MUST NOT automatically add new
> assessable rows to the alignment score.

`scripts/evaluate_m11c_offline_extractor_safety.py` runs the REAL
extractor's every produced `Qualification` through the REAL,
unmodified `project_qualification()` and, where that safely yields a
`JobRequirement`, through the REAL, unmodified `match_requirement()`
against an EMPTY candidate evidence profile. Result, across all 28
`JobRequirement`-producing cases in the corpus:

- **`never_supported_with_empty_evidence: True`** — no competency
  requirement was ever scored `SUPPORTED` with zero evidence (it
  cannot be: `concept_id`/`alternative_concept_ids` is always empty
  for a competency-tagged requirement, so the matcher's own existing
  `has_sufficient_evidence` check never has anything to check against).
- **`never_falsely_assessable_without_concept_mapping: True`** — every
  one of the 28 correctly resolves to `MatchStatus.NOT_ASSESSABLE`
  (`matching/engine.py`'s own existing decision table: no concept
  mapping at all → always `NOT_ASSESSABLE`, regardless of
  `github_observability`'s value, confirmed directly, not inferred).

### The competency observability policy table (new, data-only, not a detector)

`competency_extraction.py`'s own `_COMPETENCY_OBSERVABILITY` dict — the
"third table" Stage 2A's own Phase 4 found missing, now implemented as
a plain lookup (never a repository scan): `circuit-theory`,
`ml-fundamentals`, and `quantum-computing` map to `NOT_OBSERVABLE`
(no software artifact possible for the first, no artifact at all for
the second, no realistic GitHub proxy for genuine quantum-hardware
competency for the third); every other of the 17 vocabulary tags maps
to `PARTIALLY_OBSERVABLE` (a plausible but inconclusive implementation
proxy); none maps to `STRONGLY_OBSERVABLE` — a technical competency is
never treated as directly, concretely demonstrable the way a named
technology is.

### "A technology mention does not prove a competency" — verified by construction, not by a new check

This module has **zero code path that reads any `concept_id`,
`alternative_concept_ids`, or technology mention from anywhere** — its
only input is raw claim text, matched against a vocabulary of
COMPETENCY language, never technology names. The three named examples
(Python→algorithms, React→system-design, CUDA→GPU/parallel-computing)
are exercised as adversarial corpus controls
(`m11c-python-adversarial-01`, `m11c-react-adversarial-01`,
`m11c-cuda-adversarial-01`) whose OWN expected outcome is the ALREADY-
CORRECT existing `SPECIFIC_TECHNOLOGY` classification — this milestone
adds no code that could conflate the two, confirmed structurally
(there is nothing to disconnect, since nothing was ever connected).

### No new competency evidence detector

Confirmed: nothing in `competency_extraction.py` inspects a
repository, a dependency manifest, or any `Evidence`/
`CandidateEvidenceProfile` object. The observability table above
answers "is this KIND of claim ever checkable," never "does THIS
candidate's GitHub activity demonstrate it" — the latter remains
entirely unaddressed, by explicit restriction.

### Extraction quality vs. scoring metrics, kept separate

Phase 3/4's own precision/recall/necessity/logical-grouping numbers
(above) measure the EXTRACTOR against the corpus's own annotations —
they say nothing about, and are never combined with, `alignment_score`/
`assessable_count` (which this unwired module cannot affect at all,
confirmed by the "not imported" test and by Phase 6's own
byte-identical regression results below).

---

## Phase 6 — Historical regression verification

| Check | Result |
|---|---|
| Focused M11-C tests | 29/29 passed |
| Full backend suite | 1343 pre-existing + 29 new = **1372 passed, 13 skipped** — skip count/set unchanged |
| M11 development evaluation | Byte-identical (`TECHNICAL_COMPETENCY` 1/11 recall, 0 false qualifications — unchanged, since the live parser was never touched) |
| M11-A1/M11-A2 regression tests | Included in the full suite above, unchanged |
| M11-B Stage 1/Stage 2B tests | Included in the full suite above, unchanged (56 + 26 tests, all still passing) |
| M10A real postings | Byte-identical — `meets_neither: []` for both SOTI and Manulife |
| M9B preservation | Byte-identical across all 10 named metrics |
| M10D alternatives | Byte-identical (`baseline exact_match=30/41 fabricated=0 regression=0`); regenerated tracked report reverted via `git checkout --` |
| M11-A2 line-wrap | Byte-identical baseline column across all five corpora; regenerated tracked report reverted the same way |
| Frozen `8c:v1`/`8c:v1.1` | **FRESH, 0 diffs** |
| `evidence_report.json`/`end_to_end_report.json` staleness | Same pre-existing, unrelated drift already disclosed in Stage 1/2B's own reports — unaffected |
| `git diff --check` | Clean |
| `git diff --name-only -- src/gitscore` | Only `competency_extraction.py`, new |
| Frozen gold | `git diff --stat` empty |

**Demonstrated, not merely asserted:** zero change to live parser
output (the module is never imported by it); zero change to alignment
scores (nothing wires into `assess_job()`/`match_job()`; the Phase 5
safety harness confirms the WOULD-BE scoring behavior stays safe even
if it were, which it is not); zero change to existing API serialization
(nothing touches `api/`); no historical-gold edits; no requirement
fabrication (0 false positives of every kind measured, Phase 3/4);
exact source-span preservation (28/28, Phase 4). `JOB_DESCRIPTION_PARSER_VERSION`
stays `job_description_parser:v10` — the live parser has not changed.

---

## Generalization limitations (stated plainly, not minimized)

1. **Vocabulary coverage, not language understanding.** The 17-tag
   vocabulary covers the mission's own 16 named disciplines plus one
   deliberately-added domain (quantum computing) to test
   generalization — it does NOT generalize to an arbitrary, unlisted
   competency phrased in novel vocabulary. A sentence naming a
   discipline with no matching pattern at all is correctly declined
   (`no_competency_language`), never guessed — safe, but genuinely
   zero recall for that case, not measured as a failure by this
   milestone's own metrics (which only test the 17 tags actually
   implemented).
2. **Necessity detection is local-marker-only.** `infer_necessity(text, None)`
   finds nothing for several realistic phrasings this corpus itself
   surfaced ("you should be comfortable...", "must demonstrate...",
   "should have...") — none are in `necessity.py`'s own existing marker
   vocabulary. This prototype does not thread SECTION-derived necessity
   hints through at all (unlike the live parser's own
   `resolve_necessity_hint`) — a real integration would need to, and is
   explicitly future work, not attempted here.
3. **Negation detection is three fixed phrases, not a capability.**
   Stated in Phase 4 — do not read the one negation control passing as
   evidence of general negation understanding.
4. **The missing-contract gap (OR_ANY groups of competency tags) is a
   real, un-fixed representational hole** — two of this corpus's own
   45 controls (`m11c-orany-01`, `m11c-exhaustive-02`) cannot be safely
   represented at all today, declined rather than guessed.
5. **No claim of universal postings understanding.** 45 development
   examples, authored by one process, in one sitting, is not a
   representative sample of arbitrary real-world job descriptions —
   this document does not and must not claim otherwise. A genuine
   holdout corpus (Phase 2's own protocol, content not yet authored)
   would be required before any broader generalization claim could be
   made responsibly.
6. **Sibling composition across DIFFERENT qualification kinds is not
   detected.** `m11c-mixed-tech-competency-01`'s own "and" at the
   sentence level (a named technology AND a competency, two different
   `QualificationKind`s) is the one remaining logical-grouping
   mismatch (27/28, Phase 4) — this extractor has no code path that
   coordinates with a technology-mention detector to recognize this
   shape, by design (Phase 1's own A/B/C decision separation keeps
   this extractor's scope to competency recognition alone).

---

## Recommendation for eventual controlled production integration

**Not recommended yet, and this document does not ask for that
authorization.** A realistic path, in dependency order, each requiring
its OWN separate approval:

1. **Author the Phase 2 holdout corpus** (independently sourced, hash-
   frozen, per the existing Stage 2A/this document's own protocol) and
   measure THIS SAME, UNCHANGED prototype against it, with no tuning
   permitted between measurement and any decision.
2. **Thread section-derived necessity hints through**, mirroring the
   live parser's own `resolve_necessity_hint` — a real integration
   question, not attempted here.
3. **Resolve the missing-contract gap** — requires a SEPARATELY-
   approved `Qualification`/`NormalizedReference` schema addition
   (outside this milestone's own authority).
4. **A shadow-mode comparison** against real (not corpus) job postings,
   using the Option A offline-runner architecture Stage 2A already
   designed and Stage 2B already implemented for Path A — extended to
   compare this Path B prototype's output, never replacing the live
   parser's own authoritative output.
5. Only after (1)-(4) are each separately measured and approved would
   any wiring into the live parser become a question this project asks
   at all.

---

## Explicit STOP / architectural approval questions

1. **Approve Option C** (bounded vocabulary + contextual qualification
   classification + conservative validation) as the architecture this
   milestone's own offline prototype implements — confirming the
   choice was measured (100% precision, identical recall to A/B), not
   assumed?
2. **Confirm the missing-contract finding** (no `NormalizedReference`
   field for a GROUP of multiple competency tags) is accepted as a
   genuine, disclosed gap requiring its OWN future, separately-approved
   schema decision — NOT to be worked around by this or any future
   milestone without that approval?
3. **Confirm the Phase 5 observability/scoring-safety verification**
   (empirically confirmed `never_supported_with_empty_evidence` and
   `never_falsely_assessable_without_concept_mapping`, both `True`
   across all 28 cases) is sufficient evidence that no new competency
   evidence detector is needed or implied by this milestone?
4. **Confirm the Phase 2 holdout protocol** (unchanged from Stage 2A)
   remains the required standard before ANY generalization claim beyond
   this development corpus — and that authoring its actual content
   requires its own, separate authorization, not implied by this
   milestone's own approval?
5. **Confirm NO wiring into the live parser, no competency evidence
   detector, and no public schema change begins under this same
   approval** — each named in the recommendation above only as a
   FUTURE, separately-approved step?

---

**STOP — offline prototype, evaluation, and architectural
recommendation only. No production code was modified
(`git diff --name-only -- src/gitscore` shows only new, unimported
files). No commit was made. All five previously-untracked M11
generalization files, M11-B's Stage 1/Stage 2B's own committed modules,
and all frozen historical gold remain exactly as they were. Awaiting
approval on the five questions above before any production integration
step.**
