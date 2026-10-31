# Milestone 10B — Safe Section-State Handling

**Status: design review (§1–10) COMPLETE, PRODUCTION IMPLEMENTATION
APPROVED AND LANDED (§11), not committed.** §1–10 below are the
original design-review deliverable, preserved unedited as the record
of what was proposed and why. §11 is the post-approval addendum
documenting the actual implementation, the bulleted-colon-lead-in
amendment found during approval review, the real test/evaluation
results, and the final diff. **No frozen gold, concept registry,
matcher, or scoring formula was touched. Not committed, not pushed.**

---

## 1. Baseline commit

| Check | Result |
|---|---|
| `git status --short` | clean |
| `git log -5 --oneline` (HEAD) | `dd32dac test: add real-world job parsing regression benchmark` (Milestone 10A) |
| `python -m pytest` | **947 passed**, 0 failed |
| `python scripts/evaluate_m10a_realworld.py` | runs clean, reproduces the committed `evaluation/reports/m10a_realworld_report.json` figures (SOTI 1 FP / Manulife 5 FP, etc.) |
| `python scripts/evaluate_m9b_preservation.py` | runs clean, reproduces the committed 0.615 genuine-requirement recall, 0 fabrication |

M10A is fully committed; the working tree was clean before any of this
milestone's own (non-`src/`) additions. Baseline verified — proceeding.

---

## 2. Exact root-cause trace (Phase 1)

Traced live against the real, unmodified `segment_description()`
(`jobs/parsing/segmentation.py`) and `_parse()` (`jobs/parsing/parser.py`)
using six constructed scenarios plus the two real M10A postings. Full
trace output is reproducible; the mechanism is summarized below.

### 2.1 The single line responsible

```python
necessity_hint = _SECTION_NECESSITY_HINT.get(current_kind, Necessity.REQUIRED)
in_recognized_section = current_kind is not None
```

`current_kind` is reassigned **only** when a line's colon-stripped,
lowercased text exactly equals one of the four heading tables
(`_REQUIRED_HEADINGS`/`_PREFERRED_HEADINGS`/`_RESPONSIBILITY_HEADINGS`/
`_SKIP_HEADINGS`). Any other line — including one that is obviously a
heading in context, just not one of the ~30 exact phrases in those
tables — falls straight through to ordinary claim handling under
whatever `current_kind` already is. There is no "this was a heading,
just not one I recognize" branch at all.

### 2.2 Scenario-by-scenario trace

| # | Scenario | State before | Heading recognized? | State after | Claim created? | Necessity inferred | Emitted as | Enters denominator |
|---|---|---|---|---|---|---|---|---|
| 1 | PREFERRED section → unknown heading → content | `PREFERRED` | No | **`PREFERRED` (unchanged)** | Yes, unconditionally (`in_recognized_section=True`) | `preferred` (inherited hint; no local marker) | `JobRequirement` (becomes scored IF any detector fires) | **Yes, if a concept/pattern matches** |
| 2 | REQUIRED section → unknown heading → content | `REQUIRED` | No | **`REQUIRED` (unchanged)** | Yes, unconditionally | `required` (inherited hint) | `JobRequirement` (if a detector fires) | **Yes, if a concept/pattern matches** |
| 3 | unknown heading → company/legal prose | `None` (nothing recognized yet) | No | `None` (unchanged — nothing to inherit) | Only if `_looks_like_requirement` passes (signal word or concept mention) | `required` (the **pre-existing, separate** "no section at all" default) | `JobRequirement` only if admitted and a detector fires; otherwise silently dropped, zero trace | Only if admitted with a concept mapping |
| 4 | unknown heading → genuine technical qualification | `None` | No | `None` | Yes, if admitted (the sentence itself usually contains a signal word, e.g. "required") | Local marker wins regardless of hint | `JobRequirement` | Yes |
| 5 | unknown heading → responsibilities/duties | `None` | No | `None` | Only if admitted | n/a | Usually **zero claims, zero trace** (duty prose rarely contains a signal word or concept) | n/a |
| 6 | recognized section encountered *after* an unknown heading | (irrelevant) | **Yes** | Correctly reassigned | Yes | From the newly-recognized section | `JobRequirement` | Yes |

**Live-confirmed, concrete false-positive reproduction** (mirrors the
real Manulife ".html" defect exactly):

```
Preferred Qualifications:
- Experience with Docker is a plus.

Learning Opportunities:
To learn more about our stack, visit our engineering blog at https://example.com/engineering.html.
```
produces **two** `JobRequirement` rows, both `necessity=preferred`,
`github_observability=STRONGLY_OBSERVABLE` — including
`concept_id='language.html'` for the second sentence, which is pure
company-blog prose that happens to contain a `.html` URL. It scores
exactly as if the posting had said "HTML is a preferred qualification."
Both rows **enter the alignment-score denominator**.

### 2.3 Heading-detection failure vs. necessity-inheritance failure — kept distinct

These are two independent defects that happen to share one root cause
investigation (M10A, Root Causes 1 and 2):

- **Heading-detection failure** (M10A Root Cause 1, e.g. "Required
  skills" vs. "Required Qualifications"): the table is too narrow. This
  is a **recall** problem — a real REQUIRED section is missed entirely.
  **Out of scope for M10B** (Phase 4 — "no broad root-word heading
  classification").
- **Necessity-inheritance failure** (M10A Root Cause 2, this
  milestone's mission): once ANY heading fails to match, the **state
  machine has no memory that something changed** — it just keeps using
  whatever kind was last real. This is a **precision/fabrication**
  problem — content with no stated necessity gets a confident, wrong one
  assigned to it. **This is M10B's target.**

Scenario 3/5 above (content gated out entirely because it never
contains a signal word, independent of any heading) are a **third,
separate** mechanism — M10A's Root Cause 3, the outside-section
heuristic gate — which already exists today for un-sectioned content
and is **not changed** by anything proposed below (see §4.4).

---

## 3. Design options evaluated (Phase 2)

### Option A — internal `UNKNOWN` section state + non-scoring diagnostics

Add a state the state machine can be *in* without that state implying
any necessity. The open design question is purely mechanical: what
happens to a claim whose necessity cannot be determined?

### Option B — explicit separation of section purpose and requirement necessity

Split "what kind of section is this" from "how necessary is this one
requirement" into two independently-tracked fields carried all the way
through to `JobRequirement`. Evaluated and **rejected as unnecessary**:
`necessity.py` already enforces local-wording-wins-over-section-hint
(Milestone 6B Part 7) — the two concepts are *already* independent at
the point necessity is finally decided. Promoting that independence
into a new field on the public `JobRequirement` domain model would be a
real schema change (`JOB_REQUIREMENT_SCHEMA_VERSION` bump, new API
field) to solve a problem that is fully solvable by fixing where the
*hint itself* comes from (segmentation), never reaching the domain
model at all. Rejected for being a larger blast radius for no behavioral
gain over Option A.

### Option C — conservative claim creation outside recognized sections

Already exists, live, in production, today — `_looks_like_requirement`
gates every claim outside a recognized `REQUIRED`/`PREFERRED`/
`RESPONSIBILITY` section (Milestone 6B Part 3, Root Cause 3 above). The
only question is *which states count as "outside a recognized
section"* for this existing gate. Today that's exactly `current_kind is
None`. Pure Option C taken alone — remove the sticky-inheritance bug by
simply making `SKIP`/an-unknown-heading always fall back to the
**existing** `None`-shaped gate — turns out to be **almost the entire
fix**, once combined with a way to actually detect that an unrecognized
heading occurred at all (which Option A's state value provides).

### Recommended: A+C hybrid, narrowly scoped

1. Add `_SectionKind.UNKNOWN` (segmentation.py-internal only, never
   exposed on `Claim`, `JobRequirement`, or any API type).
2. A line that is **colon-terminated** (checked with the exact same
   `rstrip(":")` normalization the heading-match code already performs),
   **not bullet-prefixed** (see §3.1b — a bulleted colon line is a list
   lead-in, never a section heading), and whose colon-stripped text does
   **not** match any of the four existing heading tables **resets
   `current_kind` to `UNKNOWN`** — but **only if `current_kind` was
   already a real recognized kind** (`REQUIRED`/`PREFERRED`/
   `RESPONSIBILITY`/`SKIP`). If `current_kind` is already `None`
   (nothing has ever been recognized in the document), it is left as
   `None` — see §3.1 for why this refinement is load-bearing.
3. `Claim.necessity_hint` becomes `Necessity | None`. The existing
   `_SECTION_NECESSITY_HINT` dict is **unchanged**. `UNKNOWN` maps to
   `None` explicitly (never looked up via the dict's `.get(...,
   Necessity.REQUIRED)` default — satisfying the explicit instruction:
   *"Do NOT assign UNKNOWN to REQUIRED or PREFERRED merely because the
   existing Necessity enum has only two values"*).
4. `in_recognized_section` becomes `current_kind in
   (REQUIRED, PREFERRED, RESPONSIBILITY)` (previously `is not None`) —
   so `UNKNOWN` is admitted by the **same existing** `_looks_like_requirement`
   gate `None` already uses. No new gate, no new vocabulary.
5. `necessity.py::infer_necessity` keeps its exact existing
   local-marker-wins logic unchanged; only its return type honestly
   becomes `Necessity | None` (a claim with no local marker and a `None`
   hint returns `None`).
6. `parser.py::_requirements_from_claim`: if the inferred necessity is
   `None`, return `[]` **before running any detector** — the caller
   (`_parse`) already has a defined, tested, API-visible destination for
   "zero requirements produced for an admitted claim": the existing
   `UnparsedClaim` / `unparsed_claims` mechanism (Milestone 9C). No new
   type is introduced.

**Zero new public types. Zero schema changes. Zero API changes.**

### 3.1 Why the "only reset from a real recognized kind" refinement matters

An earlier, simpler version of step 2 (reset to `UNKNOWN` on *any*
unrecognized colon-heading, unconditionally) was prototyped first and
rejected after measurement: it incorrectly also reclassified SOTI's
"Required skills:" bullet — a document where `current_kind` was `None`
throughout (that heading was never recognized by the table, so nothing
was ever inherited in the first place; this is a Root-Cause-1 gap, not
Root-Cause-2). The naive version changed that bullet's outcome from
today's existing, already-conservative `category="alternative_requirement"`
placeholder down to a bare diagnostic — a real regression, unjustified
by anything this milestone is supposed to fix, and a concrete
illustration of why "detect any unrecognized heading" and "detect an
unrecognized heading **following a real section**" are different rules
with different blast radii. The refined rule (§3, step 2) produces
**zero behavioral change** on the SOTI posting (confirmed by direct
re-run, §5.1) while still fully resolving the Manulife sticky-`PREFERRED`
chain.

### 3.1b Amendment — bullet-prefixed colon lines must be exempted

**Found during approval review, before implementation**, by stress-testing
the trigger rule against a case not in the original 11 controls: a
genuine requirement list formatted as a bulleted colon lead-in *inside
an already-open, correctly-recognized section* --

```
Requirements:
- Experience with the following:
- Python
- JavaScript
```

The rule as drafted in §3 step 2 checks only "colon-terminated, table-
unmatched, `current_kind` already real" — it does not check whether the
line is itself a bullet. "- Experience with the following:" satisfies
all three, so it was (incorrectly) resetting `current_kind` to `UNKNOWN`
**even though a real `Requirements:` section was still legitimately
open**, demoting `Python`/`JavaScript` from formal `REQUIRED` rows to
bare `UnparsedClaim` diagnostics. Confirmed empirically in the
prototype before any fix: both sub-bullets ended up in `unparsed_claims`
instead of as `JobRequirement` rows.

**Amendment**: add one more condition to step 2's trigger — the line
must **not** be bullet-prefixed (`_BULLET_PREFIX.match(line) is None`).
Real section headings are never formatted as list items; a bulleted
line ending in a colon is structurally a list lead-in, never a section
boundary. Re-verified after the amendment:

- The constructed case above now correctly produces `Python`/`JavaScript`
  as formal `REQUIRED` rows again.
- All 11 original controls still pass, unchanged.
- SOTI and Manulife real-posting numbers are unchanged (the amendment
  only affects bulleted colon lines, none of which occur among the
  unrecognized headings that drove the original fix — all of
  "Learning Opportunities:", "When you join our team:", "Application
  instructions:", "Working Arrangement" in the real Manulife posting are
  bare, non-bulleted lines, confirmed by direct inspection of the raw
  source file).

This amendment is now folded into the design in §3 and into the control
corpus as `m10b-12-bulleted-colon-leadin-inside-recognized-section`.

### 3.2 Dependency direction

```
segmentation.py  (adds _SectionKind.UNKNOWN; Claim.necessity_hint: Necessity | None)
      |
      v
necessity.py     (infer_necessity's return type becomes Necessity | None;
                   its REQUIRED/PREFERRED local-marker logic is untouched)
      |
      v
parser.py        (_requirements_from_claim short-circuits to [] on None;
                   _parse's EXISTING "no requirements produced -> UnparsedClaim"
                   fallback does the rest, completely unmodified)
      |
      v
jobs/profile.py, matching/*, assessment/*, api/*   <- UNTOUCHED
```

Every package downstream of `parser.py` sees only a **smaller, more
accurate set of `JobRequirement` rows** (and a different-but-already-
existing `unparsed_claims` population) — the exact same two output
shapes they already consume today. Nothing downstream needs to know a
third "unknown" concept exists at all.

### 3.3 Handling of unknown sections — final answer

Content under an `UNKNOWN` section:
- **If** it carries a local REQUIRED/PREFERRED marker in its own text
  (Milestone 6B Part 7's existing precedence, unchanged) → becomes a
  normal, correctly-necessitated `JobRequirement`, exactly as it would
  under any other state.
- **Else if** it is admitted by the existing outside-section heuristic
  gate (a signal word or a known concept mention) → every existing
  detector still runs (concept mentions, unresolved terms, experience
  qualifier, non-technical pattern, last-resort placeholder) to build
  the candidate requirement — but since no necessity can be assigned,
  the claim is **preserved as a diagnostic** (`UnparsedClaim`) rather
  than becoming a scored row. The parser is honest about having found
  *something* without fabricating *how necessary* it is.
- **Else** (no signal word, no concept mention) → excluded entirely,
  **exactly as un-sectioned marketing/duty prose already is today** —
  not a new drop mechanism, the existing one extended to a new state.

### 3.4 Compatibility check

| Surface | Impact |
|---|---|
| `JobRequirement` domain (`jobs/models.py`) | **None.** No field added/removed/retyped. |
| `UnparsedClaim` diagnostics | **Reused as-is.** More claims may route here; shape unchanged. |
| Exact source spans | **None.** `Claim.start/end` computation is untouched; only which `Claim`s get admitted and what necessity they're assigned changes. |
| Deterministic matching | **None.** `match_requirement`/`match_job` never see `Claim` or `UNKNOWN` at all — pure functions of an already-reduced `JobRequirementProfile`. |
| API serialization | **None.** `UnparsedClaimOut`/`AnalyzeResponse.unparsed_claims` already exist, already wired end-to-end (`api/serialization.py`, `application/job_fit.py`) — confirmed by direct grep, zero new Pydantic models needed. |
| Alignment scoring (`assessment/*`) | **Indirect only.** Fewer spurious `STRONGLY_OBSERVABLE`-with-`concept_id` rows enter `_assessable_matches`' denominator for postings exhibiting Root Cause 2 — `alignment_score` can shift for such postings as a **consequence of correcter input**, not because `SCORING_VERSION`/`MATCHER_VERSION` decision logic changed (neither needs to bump). |
| Existing correctly-recognized unsectioned requirements | **Preserved exactly** — confirmed empirically, §5.1. |
| `JOB_DESCRIPTION_PARSER_VERSION` | Would need bumping (`v4` → `v5`) under this package's own existing versioning convention — a metadata string, not a shape change. |

---

## 4. Independently-authored controls (Phase 3)

`evaluation/m10b/section_state_controls.json` (new, additive, 11
entries) was written by reasoning about each fragment fresh — **not**
derived from, or adjusted to match, either parser's output — then
checked against both the current parser and the prototype design
afterward (§5.2). It covers every scenario Phase 3 requires: Required
Skills, Preferred Qualifications, unknown-after-Preferred,
unknown-after-Required, About Company, Learning Opportunities,
Responsibilities, an unsectioned explicit genuine requirement, a
company-narrative sentence incidentally mentioning years of experience,
and a legal/salary disclosure incidentally mentioning technical-sounding
vocabulary — plus an 11th control (a real heading correctly recognized
*after* an unknown one) confirming `UNKNOWN` never itself becomes sticky.

Three outcome classes are used (never binary pass/fail on their own):
`formal_requirement`, `diagnostic_preserved`, and
`correctly_excluded_non_requirement` — deliberately keeping "preserved
as an honest diagnostic" and "correctly silent because it's definitely
not requirement content" as two different, both-acceptable outcomes,
so no single metric could reward silently deleting everything.

### 4.1 Prototype uses real, unmodified detector code

The design above was **not merely theorized** — it was prototyped as a
standalone copy (reusing the real `alternatives.py`, `concepts.py`,
`experience.py`, `non_technical.py`, `confidence.py`,
`observability.py`, `JobRequirement`/`SourceSpan`/`UnparsedClaim`
verbatim, unmodified) to produce the concrete numbers below. The
prototype lives only in this session's scratchpad; it was never merged
into, or imported by, `src/gitscore`.

---

## 5. Measured before/after (Phase 2/5 preview — simulation, not implementation)

### 5.1 Real-world postings (the actual M10A source files)

| Posting | Metric | Current (unmodified) | Prototype (proposed fix) |
|---|---|---|---|
| SOTI | `JobRequirement` rows | 2 | **2 (unchanged)** |
| SOTI | `unparsed_claims` | 6 | **6 (unchanged)** |
| SOTI | Any row added/removed | — | **0 / 0** |
| Manulife | `JobRequirement` rows | 13 | **8** |
| Manulife | False-positive rows removed (all 5 from M10A §4.1) | — | **5 / 5 removed, 0 new false positives added** |
| Manulife | `unparsed_claims` | 27 | **5** |

**SOTI is provably unaffected** — it never exhibited Root Cause 2 to
begin with (every unrecognized heading in it occurs while
`current_kind` was already `None`), so the refined rule (§3.1) changes
nothing. This is the single strongest piece of evidence that the fix is
correctly scoped to the actual defect and not a broader behavioral
change in disguise.

**Every one of Manulife's 5 documented false positives (M10A §4.1) is
removed, with zero new false positives introduced.** Of the 5: 2 (the
salary-methodology sentence, the `.html`-URL sentence) land in
`unparsed_claims` as honest diagnostics (they contain an incidental
signal word/concept mention); the other 3 (the hiring-initiative
statement, the fair-recruitment-commitment statement, the
AI/data-processing privacy disclosure) are excluded with no trace at
all, by the exact same pre-existing mechanism that already silently
excludes ordinary marketing prose outside any section today (§3.3,
third bullet) — **not a new silent-drop mechanism**, see §6 for why this
specific reduction in diagnostic-list noise is an intentional,
acceptable consequence rather than a new defect.

The 22 other `unparsed_claims` that disappear entirely (heading lines
themselves, benefits/EEO/accommodation/application-instructions prose)
are **exactly** the stuck-`PREFERRED`-span content M10A's Root Cause 2
traced — none is a genuine qualification or duty; cross-checked against
`evaluation/m10/corpus.json`'s own `is_requirement` annotations for
every Manulife entry in that span.

### 5.2 Control corpus (`evaluation/m10b/section_state_controls.json`)

| Control | Expected (authored truth) | Current parser | Prototype (proposed fix) |
|---|---|---|---|
| 01 required-skills-positive | formal_requirement | ✅ matches | ✅ matches |
| 02 preferred-qualifications-positive | formal_requirement | ✅ matches | ✅ matches |
| 03 unknown-after-preferred | diagnostic_preserved | ✅ matches | ✅ matches |
| 04 unknown-after-required | correctly_excluded_non_requirement | ❌ diagnostic_preserved (noisy, not unsafe) | ✅ matches |
| 05 about-company | correctly_excluded_non_requirement | ❌ diagnostic_preserved (noisy, not unsafe) | ✅ matches |
| 06 learning-opportunities | diagnostic_preserved | ✅ matches | ✅ matches |
| 07 responsibilities-under-unknown | correctly_excluded_non_requirement | ❌ diagnostic_preserved (noisy, not unsafe) | ✅ matches |
| 08 unsectioned-explicit-requirement | formal_requirement | ✅ matches | ✅ matches |
| 09 company-narrative-years-of-experience | diagnostic_preserved | ❌ **formal_requirement, fabricated necessity (unsafe)** | ✅ matches |
| 10 legal-salary-disclosure-with-technical-terms | diagnostic_preserved | ❌ **formal_requirement, fabricated necessity (unsafe)** | ✅ matches |
| 11 recognized-section-after-unknown | formal_requirement | ✅ matches | ✅ matches |

**11/11 match the authored truth under the proposed design; 6/11
already matched today.** Of the 5 current mismatches, **2 (controls
09/10) are genuine safety defects** — a scored, necessity-bearing
`JobRequirement` fabricated from content with no stated necessity,
exactly the mission's target — while **3 (controls 04/05/07) are
diagnostic-list noise, not a safety problem** (an `UnparsedClaim` is
never scored and never shown as a requirement). The proposed design
fixes all 5, including the 3 that were never urgent, as a byproduct of
reusing the one existing admission gate consistently rather than adding
a second one.

---

## 6. False-positive and recall tradeoffs (honest accounting)

**What is gained:** every scored-row false positive this milestone's
mission targets — content with no stated necessity receiving a
confident, fabricated `REQUIRED` or `PREFERRED` label purely because a
prior real section happened to still be "open" — is eliminated, with
zero new false positives in either the real-world postings or the
control corpus.

**What is given up:** a small amount of `unparsed_claims` visibility
for content that is *definitely* not requirement text (pure company
narrative, pure job duties, a one-line hybrid-schedule note) once it
falls under an `UNKNOWN` section — such content now goes fully silent
instead of appearing as diagnostic noise. This is the **same drop
behavior un-sectioned marketing/duty prose already has today**
(confirmed, §3.3), just newly also applied after an unrecognized
heading rather than only before any heading at all — not a new kind of
information loss, and specifically **not** a loss of any *qualification*
text: every control and every real-posting example where genuinely
ambiguous-but-plausibly-relevant content exists (controls 03/06/09/10;
the real Manulife salary and `.html` sentences) is **preserved** as a
diagnostic, never dropped.

**What is explicitly NOT attempted:** recovering "Required skills"
(M10A Root Cause 1), the Manulife "at least one programming language
(e.g., ...)" OR-structure (Root Cause 4), or the "one or more of" idiom
(Root Cause 5) — all three remain exactly as broken/limited as they are
today, confirmed by the SOTI zero-diff result and the unchanged
`alternative_requirement`/4-separate-language-rows outcomes in §5.1.
This milestone's fix and those three are provably independent (SOTI,
which exhibits Root Causes 1/4/5 but not 2, shows zero change).

---

## 7. Domain/API implications (summary)

No `JobRequirement`/`JobRequirementProfile` field changes, no
`JOB_REQUIREMENT_SCHEMA_VERSION` bump, no new Pydantic model, no
`AnalyzeResponse` shape change, no `MATCHER_VERSION`/`SCORING_VERSION`
bump. The only version constant that would move is
`JOB_DESCRIPTION_PARSER_VERSION` (`v4` → `v5`), per this package's own
existing convention for a parsing-decision-logic change — a string
bump, not a compatibility break. `alignment_score` outputs **can**
change for postings that exhibit Root Cause 2 (that is the point — see
§5.1's Manulife numbers), but the formula, rounding policy, and
NOT_ASSESSABLE decision table in `assessment/`/`matching/` are untouched.

---

## 8. Before/after evaluation plan (if approved)

1. Implement exactly the five code changes in §3 (steps 1–6; `Claim`
   dataclass, `infer_necessity` signature, `_requirements_from_claim`
   short-circuit, `JOB_DESCRIPTION_PARSER_VERSION` bump) — nothing else.
2. Re-run `python -m pytest` — expect **947 passed unchanged** (the
   existing 15 segmentation tests and every other existing test exercise
   only `None`/recognized states, never an unrecognized colon-heading
   following a recognized one; confirmed by direct reading, §2 of the
   existing `test_job_parser_segmentation.py`).
3. Add focused new tests for the `UNKNOWN` transition itself (the 11
   controls in `evaluation/m10b/section_state_controls.json`, promoted
   to real `pytest` assertions).
4. Re-run `scripts/evaluate_m10a_realworld.py` — expect the 5 Manulife
   false positives to drop to 0, `meets_ideal_outcome` to rise for the
   Manulife entries directly affected, and the SOTI figures to be
   **byte-identical** to the committed report (§5.1).
5. Re-run `scripts/evaluate_m9b_preservation.py` — expect **byte-identical**
   output (every M9B `wrap_entry` template uses only recognized headings
   or no heading at all, §3.2 of this analysis; confirmed by direct
   reading of `scripts/evaluation_lib/preservation_eval.py`).
6. Report, separately and explicitly (never summed): false-positive
   requirements removed, genuine requirements preserved, newly emitted
   diagnostics, any previously-valid requirement lost (expected: **zero**,
   per §5.1's SOTI result and the Manulife diff showing 0 additions),
   required/preferred count changes per posting, and the resulting
   `alignment_score` delta for SOTI (expected: **none**) and Manulife
   (expected: a change, since 5 `STRONGLY_OBSERVABLE` concept-bearing
   rows leave the denominator) — with an explicit statement of whether
   that score change is judged an improvement (it should be, since the
   removed rows were confirmed fabrications) rather than assuming so by
   default.

---

## 9. Explicit STOP decisions requiring approval

This document is itself the STOP point the milestone instructions
require before any implementation. Three decisions need affirmative
approval before any `src/gitscore` file is touched:

1. **Approve the A+C hybrid design in §3** (new internal
   `_SectionKind.UNKNOWN`; `Claim.necessity_hint: Necessity | None`;
   `infer_necessity` return type widened to `Necessity | None`;
   `_requirements_from_claim` short-circuits to `[]` on `None`, reusing
   the existing `UnparsedClaim` mechanism) over Option B (rejected,
   §3) or a pure-Option-C-only approach (insufficient alone — it needs
   Option A's state value to know an unrecognized heading occurred at
   all).
2. **Approve the specific trigger rule**: reset to `UNKNOWN` only on a
   colon-terminated, **non-bulleted**, table-unmatched line, and only
   when `current_kind` was already a real recognized kind (never from
   `None`) — §3.1's refinement, empirically required to avoid an
   unintended SOTI regression, **plus** §3.1b's bullet-exemption
   amendment, empirically required to avoid demoting genuine bulleted
   sub-requirements (e.g. "Python"/"JavaScript" under a bulleted
   "Experience with the following:" lead-in) inside an already-open
   recognized section.
3. **Approve the `JOB_DESCRIPTION_PARSER_VERSION` bump** (`v4` → `v5`)
   as part of the same change, per the package's own existing
   versioning convention.

None of these require touching the concept registry, matcher,
assessment formula, frozen gold, M5B ranking, job-aware retrieval, or
frontend presentation — all explicitly out of scope per Phase 4 and
left untouched by this design.

---

## 10. Recommended implementation scope

**Narrow and immediately actionable**, if approved: the five-point
change in §3/§8, nothing else. Explicitly **not** bundled with, and
explicitly **not** a prerequisite for:

- M10A's §6.1 broader root-word heading-vocabulary classifier (separate,
  still-future milestone, still requiring its own control corpus per
  M10A's own recorded decision).
- Either §6.2 alternative-list fix ("one or more of" idiom; "at least
  one of ... (e.g., ...)" phrasing) — independent, separately-scoped,
  unaffected by anything here (confirmed, §6).

This scope was chosen specifically because it is the smallest change
that (a) fully eliminates the measured Root-Cause-2 false positives in
both real postings and all 11 authored controls, (b) touches zero
public schema/API surface, (c) provably does not regress SOTI, M9B, or
any of the existing 947 tests, and (d) does not require, or
preemptively solve, any of the three explicitly-deferred future
workstreams.

---

## Files added this milestone (design-review phase)

- `evaluation/m10b/section_state_controls.json` (new, additive — 11
  independently-authored positive/negative section-transition controls;
  a 12th was added during approval review, §11.1 below)
- `docs/evaluation/MILESTONE_10B_SECTION_STATE_SAFETY.md` (this file)

**At the end of the design-review phase: no file under `src/gitscore/`
had been modified, no frozen gold was modified, `python -m pytest`
remained 947 passed, unchanged. §11 below records what happened after
explicit approval was given.**

---

## 11. Post-approval addendum — actual implementation

All three §9 STOP decisions were explicitly approved. This section
records what was actually implemented and measured, as distinct from
the design-review prototype in §5.

### 11.1 Amendment found during approval review, before implementation

Stress-testing the trigger rule against a case not in the original 11
controls surfaced a real gap: a bulleted, colon-terminated list
lead-in **inside an already-open, correctly-recognized section**:

```
Requirements:
- Experience with the following:
- Python
- JavaScript
```

The rule as drafted checked only "colon-terminated, table-unmatched,
`current_kind` already real" -- not whether the line was itself a
bullet. This was wrongly resetting state to `UNKNOWN` mid-list, which
would have demoted `Python`/`JavaScript` from formal `REQUIRED` rows to
bare diagnostics. **Fixed before any `src/gitscore` file was touched**:
the trigger now also requires the line NOT be bullet-prefixed (real
section headings are never themselves list items). Re-verified against
all 11 original controls (zero regressions) and locked in as a 12th
control, `m10b-12-bulleted-colon-leadin-inside-recognized-section`.
This is the only amendment to the approved design; §3's trigger rule
and §9 decision 2 are both updated in place to reflect it.

### 11.2 What was actually implemented

Exactly the five-point change in §3/§8, plus the §11.1 amendment:

- `src/gitscore/jobs/parsing/segmentation.py` -- `_SectionKind.UNKNOWN`
  added; `Claim.necessity_hint: Necessity | None`; the heading loop now
  resets to `UNKNOWN` on a colon-terminated, non-bulleted, table-unmatched
  line, only when `current_kind` was already real; `in_recognized_section`
  narrowed to the explicit three-member tuple.
- `src/gitscore/jobs/parsing/necessity.py` -- `infer_necessity()` return
  type widened to `Necessity | None`; zero logic change to the
  local-marker regexes or precedence order.
- `src/gitscore/jobs/parsing/parser.py` -- `_requirements_from_claim()`
  short-circuits to `[]` on a `None` necessity, before any detector
  runs; `JOB_DESCRIPTION_PARSER_VERSION` bumped `v4` -> `v5`.

No other file under `src/gitscore/` was touched. `git diff --stat`
(§11.6) confirms the exact blast radius.

### 11.3 Focused regression tests

`tests/test_m10b_section_state_safety.py` (new, 28 tests):
- A parametrized test loads `evaluation/m10b/section_state_controls.json`
  directly (12 controls, never edited to match the implementation) and
  asserts the real `parse_job_description_with_diagnostics()` output
  matches each control's independently-authored `expected_outcome`.
- Explicit local REQUIRED and PREFERRED markers inside an `UNKNOWN`
  section (two tests) -- confirms local wording still wins with no
  section hint at all.
- `infer_necessity(..., None)` unit tests -- confirms `None` propagates
  with no local marker, and a local marker still overrides a `None` hint.
- A fabrication guard -- the real Manulife salary-disclosure sentence
  construction never produces a scored row of any necessity, only a
  diagnostic.
- Re-entry into a recognized section after `UNKNOWN` never "sticks."
- No-section-at-all behavior proven byte-identical to the pre-existing
  segmentation suite's own assertions.
- Both bulleted-colon-lead-in cases (the §11.1 amendment) and its
  contrast case (a non-bulleted colon lead-in, which still correctly
  resets state).
- Exact text/span preservation for an `UNKNOWN`-originated `UnparsedClaim`.
- A full `match_job()` round-trip proving an ambiguous `UNKNOWN` claim
  never enters `requirement_matches` at all (not even as
  `NOT_ASSESSABLE` -- there is no `JobRequirement` row to classify).
- Determinism: identical `JobRequirementProfile`/`unparsed_claims` on
  repeated parsing of the same text.
- `Claim`'s frozen/hashable invariant still holds with `necessity_hint=None`.

All 28 passed on the corrected run (one test's own example wording --
"Terraform," not registered under that bare alias -- was fixed to use
"Docker," already proven elsewhere in the suite to match; this was a
test-authoring issue, not an implementation defect).

### 11.4 Full suite and real-posting evaluation results

```
python -m pytest
python scripts/evaluate_m10a_realworld.py
python scripts/evaluate_m9b_preservation.py
python scripts/evaluate_job_parser.py
python scripts/evaluate_job_parser.py --corpus-version 8c:v1.1
```

| Metric | Before | After |
|---|---|---|
| Full backend suite | 947 passed | **975 passed** (947 unchanged + 28 new) |
| M10A SOTI false positives | 1 | **1 (unchanged)** |
| M10A SOTI `meets_ideal_outcome` | 6/12 | **6/12 (unchanged)** |
| M10A Manulife false positives | 5 | **0** |
| M10A Manulife `meets_ideal_outcome` | 29/43 | **34/43** |
| M10A Manulife `meets_neither` (genuine defect) | 12 entries | **7 entries** (man-03/04/05/06/07/08/10 remain, each independently attributable to Root Causes 1/3/4/5 -- out of scope) |
| M9B all 10 metrics | 0.615 / 0.5 / 0.5 / 0.833 / 0.643 / 0 / 0 / 1.0 / {0,6} / 1.0 | **byte-identical** -- only `parser_version_under_test` changed (`v4`->`v5`) |
| 8c:v1 (`evaluation/reports/parser_report.json`) | Recall=0.621, Precision=0.771 | **byte-identical**, zero `git diff` |
| 8c:v1.1 (`evaluation/reports/parser_report_v1_1.json`) | Recall=0.699, Precision=0.857 | **byte-identical**, zero `git diff` |

**Genuine requirements preserved or lost:** zero lost. Cross-checked
every Manulife row that disappeared against `evaluation/m10/corpus.json`'s
own `is_requirement` annotations (written independently of this fix,
Milestone 10A) -- none was a genuine qualification; all were company
narrative, legal/EEO/accommodation prose, salary disclosure, or heading
lines. SOTI: zero rows changed at all.

**Previously invisible text newly visible as a diagnostic:** the real
Manulife salary-methodology sentence and the `.html`-URL sentence --
both previously silently became fabricated `PREFERRED JobRequirement`
rows; both now appear in `unparsed_claims` instead, honestly flagged as
uninterpreted rather than scored.

**Required/preferred row-count changes:** Manulife only -- 13 total
`JobRequirement` rows -> 8 (5 PREFERRED false positives removed, 0
REQUIRED rows changed). SOTI: 2 -> 2, unchanged.

**Alignment-score impact:** the removed `.html` row carried
`concept_id='language.html'` with `STRONGLY_OBSERVABLE` observability
and so WAS entering `assess_job()`'s denominator before this fix --
removing it changes `alignment_score` for any candidate matched against
that posting. This is judged a correctness improvement, not assumed so
by default, because the underlying row was a fabrication in the first
place: a blog-post URL is not a technical qualification the posting
ever stated. The other 4 removed rows had `concept_id=None`
(`unresolved_requirement`/non-technical placeholders), which were
already `NOT_ASSESSABLE` and excluded from the denominator -- removing
them changes nothing about `alignment_score` itself, only the
requirement LIST a caller would see (fewer spurious PREFERRED rows
displayed as "requirements" at all, even unscored ones).

### 11.5 Scope boundaries honored

Confirmed by direct `git diff`: no change to `src/gitscore/concepts/`,
`src/gitscore/matching/`, `src/gitscore/assessment/`,
`src/gitscore/evidence/`, any file under `evaluation/gold/` or
`evaluation/gold_v1_1/`, or any frontend file. M10C/M10D were not
started. The §6.1 broader heading classifier and both §6.2
alternative-list fixes remain unimplemented, exactly as scoped.

### 11.6 Final verification

```
git status --short
git diff --stat
git diff --check
```

`git diff --check` reported no whitespace errors. `git status --short`
and `git diff --stat` are reproduced verbatim in this milestone's
completion report (delivered alongside this document) rather than
duplicated here, since they reflect live repository state at the
moment of the run, not a fixed design fact.

**Nothing was committed. Nothing was pushed. No frozen gold, concept
registry, matcher, or scoring formula was touched.**
