# Milestone 10D — Alternative-Requirement Semantics

**Status: IMPLEMENTED.** All five §6.7 STOP questions were approved.
Candidate A+B (§6.1) was ported into production. See the
"Implementation addendum" at the end of this document for exactly what
shipped, the final measured before/after, and what remains
out-of-scope and undone. The body of this document below is otherwise
unchanged from the original evaluation-first design review — it is the
record of the design decision, not retroactively edited to match the
implementation.

## 0. Baseline verification (Phase 0)

- HEAD: `56c1d866627ac56d2a91da69b6011c15a339d352` — confirmed, matches
  the M10C post-commit SHA exactly.
- Working tree: clean at the start of this investigation.
- Full backend suite: **1096 passed** (unchanged from M10C).
- Parser version: `job_description_parser:v6` — confirmed via
  `JOB_DESCRIPTION_PARSER_VERSION` in `jobs/parsing/parser.py`.
- M9B preservation, M10A real-world, and M10C heading-classification
  evaluation scripts were each re-run and diffed **byte-identical**
  against their committed reports, both before this investigation
  began and again after every file in this milestone was written —
  confirming this milestone changed nothing measurable about any prior
  milestone's result.
- Frozen `evaluation/gold`/`evaluation/gold_v1_1` (the project's
  `8c:v1`/`8c:v1.1` gold): untouched (absent from `git status --short`
  throughout).
- `git status --short` at the end of this milestone shows exactly five
  new, additive paths and **zero modifications to any existing file**:
  `evaluation/m10d/`, `evaluation/reports/m10d_alternatives_report.{json,md}`,
  `scripts/evaluate_m10d_alternatives.py`,
  `scripts/evaluation_lib/alternative_classifiers.py`.

## 1. Reproducing the real failures (Phase 1)

### 1.1 Exact committed source text

Read directly from the committed, byte-exact transcriptions (never
reconstructed from memory):

- SOTI (`evaluation/m10/source/soti_raw.txt`, line 20): *"Basic
  knowledge of programming in **one or more of** the following
  programming languages: C, C++, Java, JavaScript, SQL, Ruby, Rust,
  Lua, Haskell"*
- Manulife (`evaluation/m10/source/manulife_raw.txt`, line 17):
  *"Experience with **at least one** programming language (e.g.,
  Java, Python, Go, JavaScript)"*

### 1.2 End-to-end trace, current (post-M10C, v6) parser

Run directly against `parse_job_description_with_diagnostics()` on the
full, real posting text (not isolated fragments):

| Posting | Requirement rows produced today | Denominator impact |
|---|---|---|
| SOTI | **1 row**, `concept_id=None`, `category="alternative_requirement"` (the conservative "unsafe" fallback) | **0** assessable rows for a 9-language ANY-of requirement — a real coverage false-negative, but safe (no fabrication) |
| Manulife | **4 independent REQUIRED rows**: `language.java`, `language.python`, `language.javascript`, `unresolved:go` | **4** denominator slots for what is really **1** logical requirement — inflates the requirement count 4x and loses OR semantics entirely |

Confirmed via direct `classify_alternative_claim()` calls on the exact
bullet text (Phase 1, isolated from segmentation):

- SOTI → `kind="unsafe"` (Root Cause 5: the idiom "one or more" inside
  the sentence is split as if it were a list-separator "or", producing
  a garbage leading segment that fails even the `leading_token`
  escalation, correctly forcing the whole claim to the conservative
  fallback — safe, but the 9-language ANY-of structure is entirely
  lost).
- Manulife → `kind="not_technical"` (Root Cause 4: no literal "or"
  anywhere in the sentence — the list is a parenthetical `"(e.g., ...)"`
  example clause introduced by the bare phrase "at least one," which
  `contains_alternative_marker()` never even looks for — so
  `classify_alternative_claim()` never attempts group detection at
  all, and the claim falls through to the ordinary per-claim
  concept-mention pipeline, minting one independent row per matched
  language).
- `general_swe_01`'s frozen gold control, *"Proficiency in at least
  one of Python, Java, or C++"* → `kind="technical"`,
  `(language.cpp, language.java, language.python)` — **already
  correct today**, confirming Root Cause 4 is specifically about the
  *"(e.g., ...)"* / no-literal-"or" phrasing variant, not about "at
  least one of" in general.

### 1.3 A secondary, previously-undocumented defect inside Manulife's own trace

The real Manulife trace above shows `unresolved:go`, not the real
`language.go` concept, even though `resolve_concept("Go")` correctly
matches `language.go` in isolation (confirmed directly). Root cause:
`find_concept_mentions()` only scans `readme_safe_aliases()`, and bare
"go" has none (5D.1's same short-alias-safety restriction `language.c`
has); `find_bare_short_alias_mentions()`'s fallback never fires because
it is gated on the safe-mention scan finding **zero** matches
total — and here Java/Python/JavaScript already matched. "Go" then
falls to `find_conservative_unknown_terms()`, which cleans the
fragment *"Go)"* (the parenthetical's own closing paren survives
`clean_list_fragment`'s `rstrip(".,;:")`, which does not strip `)`) and
promotes it as `unresolved:go` instead of resolving the real concept.
This is a **side effect of Root Cause 4's independent-rows fallback**,
not a separate root cause — it never manifests once a single ANY-of
group is correctly formed around the whole parenthetical list instead
(confirmed: every M10D candidate that fixes Root Cause 4 also fixes
this for free, Phase 3).

### 1.4 A more severe fabrication mechanism than M10A's own framing fully mechanized (Root Cause 5, sharpened)

M10A's own write-up (§"Root Cause 5") noted *"An earlier illustrative
reconstruction tried during this investigation's prior turn... instead
fabricated a spurious `unresolved:one`... proving the exact failure
mode... is phrasing-sensitive"* without pinning down the mechanism.
This milestone reproduces it exactly and traces the real cause:

```
"Experience with one or more of the following languages: Python, Java, Go"
  -> classify_alternative_claim() -> kind="technical"
  -> concept_ids = (language.go, language.java, language.python, unresolved:one)
```

```
"Knowledge of one or more of: C, C++, Java"
  -> classify_alternative_claim() -> kind="technical"
  -> concept_ids = (language.cpp, language.java, "unresolved:more_of:_c", unresolved:one)
```

The second example fabricates a **garbled, not-even-plausible**
technology id (`unresolved:more_of:_c`) — strictly worse than a single
spurious `unresolved:one`. The mechanism, confirmed by direct
inspection of `alternatives._resolve_segment()`: when the idiom-blind
splitter's garbage segment (here, "one" or "more of: C") is **short
enough** (≤3 words) to pass `clean_list_fragment()`'s whole-fragment
shape check, `_resolve_segment()`'s `clean_list_fragment`-escalation
branch promotes it to `unresolved:<term>` **unconditionally** — this
branch has **no `looks_like_specific_technology_name()` shape gate at
all**, unlike the sibling "ALL-UNRESOLVED OR-group rescue" inside
`classify_alternative_claim()` itself, which *does* gate on shape.
Whether a given idiom-blind split is "safely unsafe" (SOTI's real
sentence — the garbage segment is long enough to fail
`clean_list_fragment` outright) or "actively fabricating" (both
variants above — the garbage segment is short enough to survive) is
**pure accident of surrounding punctuation/wording length**, not a
property either variant's author chose. **This is the single most
severe currently-reproducible defect found in this milestone**: a
confirmed fabrication, not merely a lost structure, reachable by a
plausible real-world phrasing one punctuation choice away from SOTI's
actual sentence.

### 1.5 A newly-identified, separate gap: MIXED AND/OR flattening (Root Cause 6 — NOT in scope for this milestone's fix, reported for completeness)

```
"Python or Java and SQL" -> kind="technical", concept_ids=(language.java, language.python, language.sql)
```

The correct reading is almost certainly *"(Python or Java) AND SQL"*
— two rows, a 2-way ANY-of-group plus one independently-mandatory SQL
row — but the current parser silently **flattens the mandatory "and
SQL" clause into the same ANY-of-3 group**, because
`find_concept_mentions()` scans the *entire* OR-segment text (here,
"Java and SQL," produced by splitting only on "or" and commas) without
regard for an embedded "and" boundary. This makes the claim satisfiable
by SQL evidence **alone**, silently dropping a mandatory requirement —
a real, scoring-relevant semantic defect, but **distinct from, and not
caused by, Root Causes 4/5**, and **not required to reproduce or fix
either real posting** (neither SOTI's nor Manulife's target sentence
is a mixed AND/OR shape). Documented here because the mission brief's
category E explicitly asks for it to be traced and because Phase 3's
`candidate_c` partially engages with it — see §3 and §6.3.

### 1.6 Positive/negative controls confirmed unaffected

- `general_swe_01`'s frozen gold OR-group: confirmed already correct
  (§1.2).
- `"control systems or state estimation"` (M9A's own frozen negative
  example): confirmed it stays correctly non-technical under every
  candidate tested in Phase 3 (§3) — no candidate's broadened trigger
  or idiom guard ever promotes ordinary descriptive prose.
- A true AND list, `"Experience with Python and SQL"`: confirmed it
  stays two independent REQUIRED rows (correct ALL semantics) under
  every candidate — see §3/§4.

## 2. Independently annotated evaluation corpus (Phase 2)

`evaluation/m10d/alternative_controls.json` — **41 controls**, every
`has_candidate_qualification` / `logical_structure` / expected-outcome
field annotated **before** either candidate classifier module existed
(provenance recorded in the corpus file's own `annotation_provenance`
field, mirroring this project's M10C precedent). Breakdown:

| Category | Count | Covers |
|---|---|---|
| real-posting | 2 | SOTI, Manulife verbatim |
| general_swe_01-control | 1 | frozen-gold positive control |
| root-cause-5-variant | 2 | the two fabrication reproductions, §1.4 |
| A–H (mission brief's required cases) | 33 | simple alternatives, explicit ANY-of phrasing, colon enumerations, true AND, mixed/ambiguous, idiom hazards, concept-resolution hazards, formatting variants |

Two controls (`m10d-e1`, `m10d-e2`, true MIXED "X or Y and Z" shapes)
and one formatting control (`m10d-h6`, two list-shaped clauses in one
bullet) are annotated `expected_concept_ids: null`,
`conservative_fallback_expected: "unsupported_mixed"` — the corpus
explicitly marks these **unsupported by any candidate below**, per the
brief's instruction not to invent an equivalence the current model
cannot safely represent. `m10d-e3` ("and/or") and `m10d-e4` ("such
as... or") are annotated `ANY`, not `MIXED` — "and/or" and an
enumeration-cue "or" list both have an unambiguous *conventional*
ANY reading despite surface resemblance to the MIXED category.

Two annotation corrections were made **during** this investigation
after the harness exposed them (both are pre-existing, out-of-scope
facts about the registry/mention pipeline, not M10D defects — recorded
honestly rather than silently patched):

- `m10d-d2`: corrected a wrong guessed concept-id prefix
  (`devops.*` → the registry's real `infra.docker`/`infra.kubernetes`).
- `m10d-d3`: corrected `expected_concept_ids` to exclude `language.go`
  — confirmed via direct testing that bare "Go" is never matched by
  `find_concept_mentions()` in a **plain AND list** (no OR-segment
  escalation applies there); this is the same bare-short-alias
  limitation as §1.3, surfacing in a different context, and is not an
  alternative-structure defect at all.

## 3. Candidate comparison (Phase 3/5)

`scripts/evaluation_lib/alternative_classifiers.py` (prototypes,
**not** wired into `src/gitscore`) implements:

- **Candidate A** — idiom-aware "or" splitting only: protects
  `"<number-word> or more"` from being treated as a list separator,
  changing nothing else.
- **Candidate B** — explicit ANY-of trigger-phrase recognition:
  detects `"one or more of"`, `"at least one"`, `"any one of"`, `"one
  of the following"`, `"any of"`, `"either of"` anywhere in the claim,
  then locates the list that follows (a parenthetical example clause,
  a colon-introduced list, or — failing both — the bare remainder) and
  resolves it with a **mandatory** shape requirement on every segment
  (never a shapeless promotion — this is also what fixes §1.4's
  fabrication). Falls through to the unmodified baseline when no
  trigger phrase matches.
- **Candidate AB** — Candidate B's trigger path, falling through to
  Candidate A (not the unmodified baseline) when no trigger matches —
  the "combined A+B" design the brief asks to assess as sufficient.
- **Candidate C** — Candidate AB plus a single top-level `" and "`
  boundary split, attempting (not fully achieving) MIXED-structure
  recognition for category E. Explicitly does **not** attempt real
  AND/OR precedence disambiguation — a fixed left-to-right heuristic,
  not a grammar (documented in the module's own docstring).

### 3.1 Aggregate results (`evaluation/reports/m10d_alternatives_report.{json,md}`, reproducible)

| Candidate | Exact match | Fabricated | Regression |
|---|---|---|---|
| baseline (today, unmodified) | 28/41 | 5 | — |
| Candidate A | 30/41 | **0** | 0 |
| Candidate B | 38/41 | 1 | 0 |
| **Candidate A+B** | **38/41** | **0** | **0** |
| Candidate C | 40/41 | 0 | 0 |

- **Determinism**: every candidate, run twice against every control,
  produced byte-identical results — 0 failures.
- **Zero regressions** for any candidate against any control already
  annotated "already correct today" (category A, D, F, G, and the
  `general_swe_01` control, every formatting variant that doesn't
  itself exercise the defect) — confirmed directly in
  `per_control` scores, not asserted.
- **Candidate B alone still fabricates once** (`m10d-h6`): its own
  trigger table requires `"one or more **of**"` (matching the real
  SOTI phrasing), but a claim whose idiom is `"one or more scripting
  languages"` (no trailing "of") matches no trigger at all and falls
  through to the **unmodified** baseline, inheriting its exact
  fabrication risk. This is the concrete, measured reason Candidate B
  cannot stand alone — not a theoretical concern.
- **Candidate A+B closes that gap** at the same 38/41 coverage,
  because its fallback is Candidate A (idiom-protected), not the raw
  baseline.
- **Candidate C's 2 extra correct answers over A+B are both category
  E (MIXED)** — `m10d-e1` and `m10d-e2` happen to be phrased
  left-to-right in the order Candidate C's single fixed heuristic
  expects. The corpus's own annotation for both already flags this as
  "correct by coincidence of phrasing, not a real grammar" — Candidate
  C does **not** resolve `m10d-h6` (still safely `UNSAFE`, the
  conservative, honest outcome for an unsupported shape) and would not
  be expected to generalize to the opposite-order phrasing variants
  the corpus does not even include, by design, since nothing in this
  milestone's scope asks for a real AND/OR grammar.

### 3.2 Highlighted traces

| Control | Baseline today | Candidate A+B |
|---|---|---|
| SOTI (real) | `UNSAFE` — 0 assessable rows | `ANY`, 9 concepts (`language.c`, `.cpp`, `.java`, `.javascript`, `.ruby`, `.rust`, `.sql`, `unresolved:haskell`, `unresolved:lua`) — **1** assessable row |
| Manulife (real) | `MIXED` (3 independent rows — "Go" lost to `unresolved:go`) | `ANY`, 4 concepts including the real `language.go` — **1** assessable row |
| `general_swe_01` control | `ANY`, correct | `ANY`, **identical**, unchanged |
| Fabrication variant (§1.4) | `ANY` **with `unresolved:one` fabricated** | `ANY`, same 3 real concepts, **zero fabrication** |
| Fabrication colon variant (§1.4) | `ANY` **with 2 fabricated ids, one garbled** | `ANY`, same 3 real concepts, **zero fabrication** |

## 4. Matcher and scoring semantics preserved (Phase 4)

- **No file under `src/gitscore` was modified** — confirmed by
  `git status --short` throughout (§0). The matcher
  (`matching/engine.py`), scoring formula, necessity weighting,
  evidence extraction, concept registry, and repository retrieval were
  never touched, read-modified, or exercised by anything in this
  milestone beyond read-only tracing.
- **The existing `JobRequirement` schema already represents every
  REPRESENTABLE outcome in this corpus** — confirmed by inspection
  (`jobs/models.py`, §"Milestone 6B.1"): a pure ANY-of list is one
  `JobRequirement` with `alternative_concept_ids` populated (exactly
  what Candidates B/AB/C already produce); a true ALL/AND list is
  simply N independent `JobRequirement` rows (exactly what every
  candidate's `_mention_fallthrough` already produces, unchanged from
  today); and — this is the one new finding worth flagging — even a
  MIXED "(A or B) and C" shape is representable **today, with no
  schema change**, as **one** `alternative_concept_ids` group **plus**
  one ordinary single-`concept_id` row, exactly mirroring how "Docker
  and Kubernetes" already becomes two independent rows. **No
  `JobRequirement`/matcher/schema change is being requested by this
  milestone.** The gap for MIXED is entirely in the *parser's* ability
  to correctly locate the AND/OR boundary (Root Cause 6, §1.5/§6.3),
  not in what the domain model can hold.
- For every representable ANY-of control, the candidate produces
  **exactly one** `JobRequirement`-equivalent group — confirmed
  directly via `expected_requirement_group_count` scoring (§3.1) — so
  `match_requirement()`'s existing "SUPPORTED if ANY alternative has
  evidence" semantics is entered **at most once** per logical
  requirement, never double-counted.
- Illustrative vs. exhaustive (§2's `exhaustive_or_illustrative`
  field) is annotated throughout but **no policy is implemented or
  proposed** that would award credit for a technology *outside* an
  illustrative list — every candidate here only ever resolves
  technologies the posting actually named.

## 5. Regression plan — results (Phase 5)

| Check | Result |
|---|---|
| M10D alternative controls (41) | §3.1 |
| SOTI exact requirement | §1.2, §3.2 |
| Manulife exact requirement | §1.2, §3.2 |
| `general_swe_01` OR-group | unchanged under every candidate (§1.2, §3.1) |
| M10C heading controls | unaffected — `evaluate_m10c_heading_classification.py` re-run byte-identical (§0) |
| M10B section-state controls | unaffected — full suite (includes `test_m10b_section_state_safety.py`) at 1096 passed (§0) |
| M10A real-world benchmark | unaffected — `evaluate_m10a_realworld.py` re-run byte-identical (§0) |
| M9B preservation benchmark | unaffected — `evaluate_m9b_preservation.py` re-run byte-identical (§0) |
| Frozen `8c:v1`/`8c:v1.1` gold | untouched, never read as a source of new annotations (§0, §2) |

No alternative-group accuracy, false-OR-group, fabricated-concept,
incorrect-row, unparsed-claim, required/preferred row-count, or
denominator metric for any EXISTING evaluation corpus changed, because
no production code changed. The denominator/alignment implications
reported in §3.2 are prototype-only projections (what WOULD change if
Candidate A+B were implemented), not measured changes to any committed
report.

## 6. Architectural proposal (Phase 6)

### 6.1 Recommended smallest safe implementation, if approved

**Candidate A+B**, not Candidate C. Measured justification (§3.1):
identical 38/41 coverage and 0 regressions/fabrications as Candidate C
on every control this milestone's real-world evidence (SOTI,
Manulife, both fabrication variants) actually requires; Candidate C's
only advantage is 2 MIXED-category answers correct by coincidence of
phrasing, using a fixed heuristic with no real AND/OR grammar behind
it (§3.1) — adopting it now would ship a mechanism that looks like it
solves MIXED semantics without actually having decided a policy for
them (§6.3). Concretely, this means (mirroring M10A §6.2(a)/(b), now
with the exact real-posting-derived trigger table and the mandatory
shape-check fix §1.4 identified):

1. A narrow idiom guard preventing `"<number-word> or more"` from
   being read as a list separator.
2. An explicit ANY-of trigger-phrase table (`"one or more of"`, `"at
   least one"`, `"any one of"`, `"one of the following"`, `"any of"`,
   `"either of"`) that locates a parenthetical/colon/bare list after
   itself and resolves it through the SAME existing per-segment
   resolution primitives (`_resolve_segment`, `_shaped_term`,
   `looks_like_specific_technology_name`) — never new concept-matching
   logic, only new segmentation/trigger-detection logic.
3. Tightening `_resolve_segment`'s escalation branch so an
   `unresolved:<term>` promotion is only ever accepted when the term
   also passes `looks_like_specific_technology_name` — this is a
   strictly *narrowing* change to existing behavior (closes §1.4's
   fabrication), confirmed by this milestone's own regression data to
   change **zero** already-correct outcomes.

### 6.2 Is the current `JobRequirement` representation sufficient?

**Yes**, for everything this milestone proposes fixing. See §4.
`alternative_concept_ids` already expresses ANY-of correctly; multiple
independent rows already express AND correctly; no new field, no new
`Necessity`/`GithubObservability` value, no matcher change is being
requested.

### 6.3 Mixed AND/OR fallback policy — proposed, NOT implemented

Root Cause 6 (§1.5) needs its own, separately-scoped, separately
-approved design pass before any implementation, for the same reason
M10A's own architectural decision 3 withdrew an under-specified
default (a "smallest safe change" must not be guessed at under time
pressure). What this milestone **does** establish, so that future pass
does not have to re-derive it: (a) no schema change is needed (§4);
(b) a real solution needs genuine AND/OR precedence handling, not a
single fixed split point (Candidate C's limitation, §3.1); (c) the
conservative, interim behavior until that design is approved should be
the SAME `UNSAFE`/conservative-placeholder fallback this project
already uses elsewhere — Candidate A+B already produces this for every
MIXED control in this corpus (never a fabrication, never a silently
wrong flattening) **except** the two already-worked-today baseline
behaviors this milestone's own regression checks protect
(`m10d-e3`/`e4`, which are conventionally ANY, not MIXED, despite
surface resemblance) and the pre-existing baseline flattening defect
itself (`m10d-e1`/`e2`, which Candidate A+B — by design, since it never
touches non-triggered, non-idiom "or" claims — leaves exactly as
baseline-flattened as they are today, a KNOWN, EXPLICITLY DISCLOSED
limitation, not a silent regression).

### 6.4 Illustrative vs. exhaustive list policy

Both are now annotated throughout the corpus (§2) and distinguished in
every trace in this document. **No credit-scoping policy is proposed**
(e.g., "an illustrative list should also silently accept a sibling
technology not named") — Candidate A+B resolves only what the posting
actually named in both cases, which this milestone considers already
correct and sufficient; a policy that extrapolates beyond the named
list would be a substantive scoring-semantics change requiring its own
approval, explicitly out of scope here.

### 6.5 False-positive / false-negative risk of the recommended design

- **False positive (new fabrication introduced by the trigger table
  itself)**: bounded by the corpus's own category-F/E regression
  guards (`m10d-f1`, `f2`, `f3`, `f4`, `e5`) — a bare idiom with no
  list attached, or a trigger phrase followed by a generic noun phrase
  instead of a named-technology list, measured and confirmed to stay
  `NONE`/unparsed under Candidate A+B (§3.1).
- **False negative (a real alternative-list phrasing the trigger table
  still misses)**: residual risk — the six-phrase trigger table is
  derived from the two real postings plus M10A's own proposal, not
  from a larger real-world corpus; a differently-worded real posting
  (e.g., "select at least one from the list below") would still fall
  through to Candidate A's idiom-aware baseline, which is **safe**
  (never fabricates) but may still lose ANY-of structure exactly as
  SOTI does today under Candidate A alone (§3.1's Candidate-A-only
  row). This is an accepted, bounded residual gap, not a newly
  introduced risk.

### 6.6 Proposed parser version bump

`job_description_parser:v6` → `v7`, if and when Candidate A+B is
approved and implemented — not performed in this milestone (no
production file was touched; the version constant remains `v6`).

### 6.7 Verbatim STOP / architectural approval questions

1. **Approve Candidate A+B (not Candidate C) as the implementation
   target for a future, separately-scoped M10D-implementation
   milestone?** (§6.1)
2. **Approve the six-phrase ANY-of trigger table verbatim** (`"one or
   more of"`, `"at least one"`, `"any one of"`, `"one of the
   following"`, `"any of"`, `"either of"`), including the DELIBERATELY
   BARE `"at least one"` (no required trailing "of") needed to match
   Manulife's real wording — accepting the residual false-negative
   risk this broadens (§6.5) in exchange for covering the real
   posting?
3. **Approve tightening `_resolve_segment`'s unconditional
   `clean_list_fragment`-escalation branch to require
   `looks_like_specific_technology_name`** before accepting an
   `unresolved:<term>` promotion — confirmed narrowing-only against
   this milestone's regression corpus (§3.1), but not yet checked
   against the FULL M9B/M10A corpora under an actual code change
   (only Phase 0's unmodified-baseline re-runs were performed; a real
   implementation PR would need its own full-suite + M9B/M10A/M10C
   re-run, per this project's standing workflow)?
4. **Confirm Root Cause 6 (MIXED AND/OR flattening, §1.5/§6.3) is
   explicitly deferred to its own future milestone**, with the interim
   behavior remaining exactly as it is today (the existing baseline
   flattening defect, now disclosed rather than silently present) —
   i.e., this milestone's implementation target does NOT attempt any
   AND/OR precedence detection, and Candidate C is NOT adopted?
5. **Confirm no `JobRequirement`/matcher/scoring-formula/schema change
   is requested or needed** (§4/§6.2) — the proposed change is
   entirely confined to `jobs/parsing/alternatives.py` (and possibly
   `jobs/parsing/concepts.py`, mirroring M10C's precedent of sharing a
   lead-in/trigger-phrase table across modules) and the parser version
   constant?

**No further action will be taken on any of the above without explicit
approval. No narrative-versus-requirement semantics (reserved for a
future M10E) were implemented or proposed. No frozen gold was
modified. No commit or push was made.**

---

## Implementation addendum (post-approval)

All five §6.7 questions were approved verbatim, with one refinement
added at approval time: the ANY-of trigger match alone is insufficient
— a safely identified technology/language enumeration must also
follow it (already the design's own stated safety mechanism, §6.5;
the approval made it explicit rather than implicit) — plus an explicit
negative control, *"at least one year of experience with Python" must
not become an ANY-of technology group*, now covered directly by
`test_bare_at_least_one_in_non_enumeration_prose_is_not_a_fake_any_of_group`.

### What shipped

Entirely within `src/gitscore/jobs/parsing/alternatives.py`:

1. `_classify_any_of_trigger()` / `_find_any_of_list_region()` — the
   six-phrase ANY-of trigger table (§6.7 Q2), checked FIRST in
   `classify_alternative_claim()`, before the ordinary bare-"or" path.
   Falls through (returns `None`) whenever no trigger fires, no list
   structure follows one, or the list region itself resolves to
   `not_technical` — in every such case the ordinary path runs on the
   full, original text unchanged.
2. `_classify_segment_list()` — the original per-segment resolution
   loop, extracted (not duplicated) so both the trigger path and the
   ordinary bare-"or" path share one copy.
3. `_IDIOM_OR_MORE` / `_idiom_protected_spans()` — the idiom guard
   inside `_split_alternative_segments()`, protecting
   "<number-word/digit> or more" from being read as a list separator.
4. `_resolve_segment()`'s `clean_list_fragment`-escalation branch now
   requires `looks_like_specific_technology_name` before promoting to
   `unresolved:<term>` (§6.7 Q3) — a single added `if`, global to the
   function, so both the trigger and ordinary paths benefit.
5. `JOB_DESCRIPTION_PARSER_VERSION`: `v6` → `v7`
   (`jobs/parsing/parser.py`; no other change to that file beyond its
   module docstring).

No change to `jobs/parsing/concepts.py` was needed — the trigger table
and its helper regexes live in `alternatives.py` itself; every shared
primitive the new code reuses (`clean_list_fragment`,
`looks_like_specific_technology_name`, `find_concept_mentions`) was
already imported there. No change to `JobRequirement`, the matcher, or
any scoring/necessity/evidence/retrieval code (§6.7 Q5, confirmed, not
just assumed — `git status` throughout showed only `alternatives.py`
and `parser.py` modified).

### Final verification results

| Check | Result |
|---|---|
| Full backend suite | 1096 pre-existing + 61 new (`tests/test_m10d_alternative_requirement_semantics.py`) = **1157 passed** |
| New focused tests (41 corpus controls + 2 real postings + `general_swe_01` + 2 fabrication variants + C/C++, Java/JS + unknown-tech mix + 2 negative-trigger controls + illustrative/exhaustive + 2 AND-regression + source-span/determinism + denominator) | **61/61 passed** |
| M10D 41-control exactness | All 38 determinate controls match their annotated ideal outcome exactly (confirmed via the new test file, which asserts production directly against the corpus — see note below on why `scripts/evaluate_m10d_alternatives.py` itself was NOT re-run) |
| Fabricated concepts | **0** — confirmed via explicit assertions that neither `unresolved:one` nor any `unresolved:more*` id appears in either fabrication-variant's result |
| Regressions | **0** — every category A/D/F/G/`general_swe_01` control and every existing `tests/test_job_parser.py` alternative-group test still passes unchanged |
| SOTI requirement-group change | 0 assessable rows → **1** `alternative_concept_ids` group of 9 (`language.c/.cpp/.java/.javascript/.ruby/.rust/.sql`, `unresolved:haskell`, `unresolved:lua`) |
| Manulife requirement-group change | 4 independent rows (incl. fabricated `unresolved:go`) → **1** group of 4 (`language.go/.java/.javascript/.python`, the real `language.go` now resolved) |
| M10A real-world benchmark | `malformed_alternative_groups` 1 → 0; `meets_ideal_count` 39/43 → 40/43; `neither_ideal_nor_fallback` `[man-06, man-10]` → `[man-06]`; SOTI side **unchanged** (its one remaining defect is the out-of-scope C#/SQL narrative false positive) |
| M9B preservation benchmark | **byte-identical** except the `parser_version_under_test` string |
| M10C heading-classification report | **byte-identical** (zero diff at all) |
| Frozen `8c:v1`/`8c:v1.1` gold | **zero diff** (never read as a source of new annotations, never modified) |
| Unparsed/diagnostic count | Unaffected for every claim not exercising Root Cause 4/5 (confirmed via the unchanged M9B/M10C reports) |
| Genuine requirements lost | **None** — both real postings' language requirements are now MORE fully represented (one correctly-structured group each) than before, not less |
| Remaining illustrative-list limitation | Unchanged from §6.4: no credit-scoping policy exists or is implemented for a technology named outside an illustrative "(e.g., ...)" list — only what the posting actually names is ever resolved |
| Remaining MIXED AND/OR defect | Unchanged from §1.5/§6.3 (Root Cause 6) — `"Python or Java and SQL"` still resolves to one flattened ANY-of-3 group today, pinned explicitly by `test_m10d_corpus_control_e1_mixed_and_or_stays_safe_not_fabricating` as a KNOWN, undone limitation, not silently claimed fixed |

**Note on `scripts/evaluate_m10d_alternatives.py`:** this script's
prototype candidates (`scripts/evaluation_lib/alternative_classifiers.py`)
import and reuse several now-modified private functions directly from
`alternatives.py` (`_resolve_segment`, `_split_alternative_segments`,
etc.) — by design, so the prototype's resolution logic was never a
second, independently-drifting copy. This means re-running that script
post-implementation would no longer compare "today's baseline" against
"the candidates," since its own "baseline" wrapper now calls the
ALREADY-FIXED production code — not a meaningful before/after any
more. `evaluation/reports/m10d_alternatives_report.{json,md}` are left
exactly as they were at design time (the true pre-implementation
snapshot); the authoritative post-implementation check is the new
`tests/test_m10d_alternative_requirement_semantics.py`, which asserts
production directly against the same 41-control corpus and passes
61/61.

### Outstanding, explicitly undone

- **Root Cause 6 (MIXED AND/OR)** — not attempted, per §6.7 Q4's
  approval. `m10d-e1`/`m10d-e2`/`m10d-h6` are pinned to their current,
  still-imperfect (but non-fabricating) behavior by dedicated tests.
- **No schema/matcher/scoring change** — confirmed, not merely
  asserted (§6.7 Q5).
- **M9E's narrative-versus-requirement semantics** — reserved for
  M10E, untouched.
- **No commit, no push, M10E not started** — per this turn's explicit
  instructions.

## Post-implementation audit addendum — illustrative-list matching limitation (disclosed, not fixed)

A dedicated audit, performed with deterministic synthetic
`CandidateEvidenceProfile` objects (no GitHub API calls), traced the
exact Manulife requirement through `match_requirement()` for three
candidates:

**Requirement:** `"Experience with at least one programming language
(e.g., Java, Python, Go, JavaScript)"` →
`JobRequirement(concept_id=None, alternative_concept_ids=('language.go',
'language.java', 'language.javascript', 'language.python'),
necessity=REQUIRED, github_observability=STRONGLY_OBSERVABLE)`.

| Candidate | Evidence | Status | Assessable |
|---|---|---|---|
| 1 | `language.java` | `SUPPORTED` | yes |
| 2 | `language.rust` (no Java/Python/Go/JS) | `NOT_OBSERVED` | yes |
| 3 | none | `NOT_OBSERVED` | yes |

**Candidates 2 and 3 are indistinguishable to the matcher.** Both are
`NOT_OBSERVED`, both count against the candidate in the assessable
denominator, even though Candidate 2 has real, observable evidence of
*a* programming language — just not one of the four the posting's
`"(e.g., ...)"` clause happened to name as examples.

**Explicitly stated, per this audit's mandate:**

- The Manulife list is illustrative (introduced by `"(e.g., ...)"`),
  not necessarily exhaustive — the posting is asking for "at least one
  programming language," using four names only as examples.
- The current `JobRequirement` representation retains NO
  illustrative-versus-exhaustive metadata at all — that distinction
  exists only in this milestone's own evaluation corpus annotations
  (`evaluation/m10d/alternative_controls.json`'s
  `exhaustive_or_illustrative` field), never on the domain model
  itself.
- `match_requirement()` (`matching/engine.py`) matches an alternative
  group ONLY against its named `alternative_concept_ids` — it has no
  mechanism to credit a same-family-but-unlisted technology, and by
  design never re-parses `original_text` to recover what "illustrative"
  might have meant.
- **A candidate with an unlisted but plausibly acceptable language can
  therefore receive a misleading `NOT_OBSERVED` result**, indistinguishable
  from a candidate with no relevant evidence at all, which affects the
  computed alignment score.
- The frontend does not currently explain this limitation anywhere —
  confirmed by searching `src/gitscore/api` and `frontend/src` for
  illustrative/exhaustive caveat language; no such disclosure exists
  today.
- **This is pre-existing, not introduced or worsened by M10D.** Before
  this milestone, the same sentence produced FOUR independent REQUIRED
  rows instead of one; a Rust-only candidate scored `NOT_OBSERVED` on
  all four, the identical underlying conflation, just spread across
  four rows and additionally inflating the denominator 4x. M10D's fix
  corrects the grouping/parsing (one row, correct OR semantics, no
  denominator inflation) and leaves the illustrative-list-as-exhaustive
  gap exactly as it was — neither better nor worse along that specific
  axis.
- **This documentation update is a disclosure, not a mitigation.** It
  changes no code and does not reduce the risk of a misleading
  `NOT_OBSERVED` result for any real candidate. Fixing the underlying
  gap requires either a new field on `JobRequirement` (e.g. an
  `is_illustrative` flag) or new matcher logic (matching against a
  broader concept family, e.g. "any `language.*`") — both are
  schema/matcher changes requiring their own separate, future approval,
  not performed here.

**Tracked as a future, separately-scoped correctness milestone** —
distinct from M10E's narrative-versus-qualification semantics problem,
though both concern the same general class of issue (a formal,
scoring-relevant requirement representation that does not fully
capture the posting's real semantic intent).
