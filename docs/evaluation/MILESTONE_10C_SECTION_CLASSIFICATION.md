# Milestone 10C — Real-World Section Classification & Requirement Coverage

**Status: §1–7 below are the original design-review deliverable
(evaluation-only), preserved unedited as the record of what was
proposed and why. §8 is the post-approval addendum: all seven §6.10
approval questions were explicitly decided, a narrow implementation
scope was authorized, and this section records what was actually
implemented, the real regression found and fixed during implementation,
and the measured before/after. No frozen gold under `evaluation/gold/`,
`evaluation/gold_v1_1/`, or `evaluation/m9b/` was modified. No file
under `src/gitscore/concepts/`, `src/gitscore/matching/`, or
`src/gitscore/assessment/` was touched. Not committed, not pushed.**

---

## 0. Baseline (Phase 0)

| Check | Result |
|---|---|
| `git status --short` before this milestone's own additions | clean |
| `git log -1 --oneline` (HEAD) | `5dc6bba fix: prevent job section necessity inheritance` (M10B) |
| `python -m pytest` | **975 passed**, 0 failed — unchanged after this milestone's additions (no production file touched) |
| `JOB_DESCRIPTION_PARSER_VERSION` | `job_description_parser:v5` (unchanged) |
| `python scripts/evaluate_m10a_realworld.py` re-run | `git diff --stat` against the committed `m10a_realworld_report.json` is empty — byte-identical |
| `python scripts/evaluate_m9b_preservation.py` re-run | `git diff --stat` against both committed `m9b_preservation_report.{json,md}` is empty — byte-identical |
| `evaluation/gold/`, `evaluation/gold_v1_1/` | `git status --short` empty — untouched |

Baseline consistent. Proceeding.

### 0.1 Files inspected

- `src/gitscore/jobs/parsing/segmentation.py`, `parser.py`, `necessity.py`,
  `alternatives.py`, `concepts.py`, `non_technical.py`
- `src/gitscore/jobs/models.py` (`JobRequirement`, `SourceSpan`)
- `src/gitscore/jobs/parsing/parser.py`'s `UnparsedClaim`
- `docs/evaluation/MILESTONE_10A_REALWORLD_PARSING_FAILURES.md`,
  `MILESTONE_10B_SECTION_STATE_SAFETY.md`
- `evaluation/m10/corpus.json`, `evaluation/m10/source/{soti,manulife}_raw.txt`
- `evaluation/m10b/section_state_controls.json`

---

## 1. Phase 1 — What the real postings actually show

### 1.1 Headings currently recognized correctly (today's table)

Across both real postings, exactly **two** headings are recognized by
today's exact-match table: Manulife's `"Required Qualifications:"` and
`"Preferred Qualifications:"`. Nothing in SOTI is recognized at all.

### 1.2 Headings missed because of exact-match vocabulary (Root Cause 1, M10A)

| Posting | Real heading | Why it misses today's table |
|---|---|---|
| SOTI | `"Required skills:"` | lowercase "skills", table only has "required qualifications"/"requirements"/"qualifications" |
| SOTI | `"What you will learn:"` | no LEARNING category exists at all today |
| SOTI | `"About SOTI"` | table only has "about us"/"about the company"/"about the team" |
| Manulife | `"Position Responsibilities:"` | table only has "responsibilities"/"key responsibilities" |
| Manulife | `"When you join our team:"` | no category exists for a culture/values blurb heading |
| Manulife | `"Application instructions:"` | table only has "how to apply" |
| Manulife | `"About Manulife and John Hancock"` | same company-name gap as SOTI |
| Manulife | `"Working Arrangement"` | no category exists at all |

### 1.3 Company/learning sections incorrectly interpreted as qualifications

None of the above, TODAY, are incorrectly interpreted as qualifications —
M10B already removed that failure mode (sticky-necessity inheritance). What
remains, confirmed by direct re-trace with the real M10B-fixed parser: this
content is either (a) excluded entirely with zero trace (the three
Manulife sentences with no local marker and no incidental signal word —
hiring-initiative statement, fair-recruitment statement, AI/privacy
disclosure), or (b) preserved as an honest `UnparsedClaim` diagnostic (the
salary-methodology sentence, the `.html`-URL sentence) — **never** a scored
`JobRequirement`. The failure mode THIS milestone addresses is different:
recognizing these headings would not currently change any requirement
outcome at all (since they're all already excluded or diagnosed correctly
post-M10B) — their value is **transparency** (a human reading the parsed
output should see "About Manulife and John Hancock" as a labeled,
recognized section, not an opaque gap) and **preventing a RE-REGRESSION**
to the pre-M10B sticky-inheritance bug the next time a posting's ordering
differs (see §4 below for why this matters).

### 1.4 Genuine qualifications currently lost or reduced to diagnostics

**SOTI's "Most importantly curiosity, a desire to learn and be a part of a
team"** (the fifth bullet under the unrecognized "Required skills:"
heading) is the one confirmed case, traced live against the real
unmodified parser:

- `current_kind` is `None` throughout SOTI (the heading is never
  recognized, so nothing is ever inherited — SOTI never exhibits M10A Root
  Cause 2 at all, confirmed again this session).
- Because `current_kind` is `None` (not a recognized section), claim
  creation is gated by `_looks_like_requirement()` (`segmentation.py`
  line 193) — **this sentence contains none of the ~16 generic trigger
  words** (`experience|proficien...|knowledge of|familiar...|degree|
  years?|required|preferred|plus|responsib...|skills?|certificat...|
  licensed?|eligible|authoriz...|mentor...`) and no registered concept.
- Result: **zero claims created, zero trace anywhere** — not even an
  `UnparsedClaim`. Confirmed directly against the real
  `parse_job_description_with_diagnostics()`.

This is the SAME bullet M10A already found and ranked (its one confirmed
`invisible_genuine_qualifications` entry, SOTI count = 1). What M10A's own
writeup did not fully spell out, and what this milestone's Phase 1 tracing
adds: **fixing heading recognition alone is NOT guaranteed to surface this
bullet as a scored requirement** — see §4 below for exactly how far
heading-fix-alone gets it, and where it still stops short.

### 1.5 Responsibilities incorrectly treated as requirements, or lost entirely

Manulife's six "Position Responsibilities" bullets remain **100% invisible
with zero trace anywhere**, confirmed again this session against the real,
unmodified, post-M10B parser (M10B did not touch this — it only prevents
necessity *fabrication*, it does not expand heading recognition). None of
the six bullets ("Contribute to a team of engineers...", "Support
application development, testing, and debugging efforts", ...) contains a
trigger word or a registered concept, so all six fail
`_looks_like_requirement()` under `current_kind=None` and are dropped
silently. This is **not** a requirement-recall defect (none of the six is
an applicant qualification) but remains the single worst *transparency*
gap in either posting — exactly M10A's own finding, unaffected by M10B,
confirmed unaffected by anything in this milestone's own investigation
either (no production code was changed).

### 1.6 Interactions with M10B's UNKNOWN state

Traced directly: **SOTI never enters `_SectionKind.UNKNOWN` at all**
(`current_kind` starts and stays `None` the entire document, since no
heading it contains is in today's table). **Manulife enters `UNKNOWN`
twice** — after `"Preferred Qualifications:"` fails to match
`"When you join our team:"`, and again after `"Application instructions:"`'s
own content block, right up until `"About Manulife and John Hancock"`
(itself unrecognized, so `UNKNOWN` persists) through to the final line
`"Working Arrangement"` (also unrecognized). Confirmed: **zero** of
Manulife's content under `UNKNOWN` carries a local REQUIRED/PREFERRED
marker, so M10B's fix correctly routes all of it to either an honest
diagnostic or full exclusion — **exactly the already-measured, already-
approved M10B behavior** (13 → 8 `JobRequirement` rows, 27 → 5
`unparsed_claims`, §11.4 of the M10B doc). This milestone's own heading
recognition work, if implemented, would **reduce reliance on `UNKNOWN`**
for Manulife specifically (every one of its five `UNKNOWN`-triggering
headings above has a proposed real family in §2–3 below) — `UNKNOWN`
would then only ever fire for a heading no family recognizes at all
(e.g., a hypothetical "Additional Information" with no clean family,
§2's control 069), which is exactly what `UNKNOWN` is *for*.

### 1.7 Markdown, Unicode whitespace, punctuation, bullet-structure effects

Neither real posting's transcription contains Markdown heading syntax
(`#`), but this is a real-world risk independent of these two postings
specifically (many ATS exports and copy/pasted postings use Markdown or
bold-emphasis headings) — covered by the independent corpus (§2) rather
than by the two real postings alone, per Phase 2's explicit formatting-
variety requirement. One genuine Unicode effect **is** present in the real
SOTI text (confirmed directly against the raw bytes, consistent with
M10A's own §0.1 finding): apostrophes throughout are the curly `U+2019`
character, not ASCII `'` — this affects exact-text *matching* (already
the subject of a real, fixed bug in M10A's own evaluation harness) more
than heading *recognition* (none of SOTI's headings contain an apostrophe).
Bullet structure matters precisely at the boundary M10B already handles
correctly (a bulleted colon lead-in inside an open section, e.g. a
hypothetical `"- Experience with the following:"` under SOTI's own
`"Required skills:"` heading if it existed there) — confirmed, neither
real posting actually contains this exact shape, but §2's corpus
specifically includes it (and its **unbulleted** sibling, which M10B's
fix does *not* cover — see control `m10c-058`) because it is a document-
structure risk, not a company-specific one.

---

## 2. Phase 2 — Independent heading-classification benchmark

`evaluation/m10c/heading_controls.json` — **78 entries**, written before
any candidate classifier in `scripts/evaluation_lib/heading_classifiers.py`
existed (see that file's own `annotation_honesty_note`, which states this
honestly and distinguishes it from M9B's stronger, structurally-enforced
blind-annotation guarantee — no such enforcing test exists here).

**Coverage, directly against the milestone's "required examples" list**:
every one of the 27 named example phrases appears at least once, each
exactly as literally given. **Coverage against Phase 2's other explicit
requirements**:

- **Positive and negative controls**: 54 `is_heading: true` entries across
  all 6 section values, 24 `is_heading: false` entries (ordinary sentences
  that happen to contain family-root words, and colon/bullet list
  lead-ins that structurally resemble headings).
- **Varied formatting**: Markdown ATX headings (`##`, `###`), Markdown
  bold (`**...**`), colon-terminated, ALL-CAPS, plain, NBSP (`U+00A0`)
  internal whitespace, zero-width-space (`U+200B`) trailing, leading tab,
  bulleted lead-ins (bulleted and un-bulleted siblings of the same text).
- **Multiple fictional companies**: Lumenbridge, Coriander Labs, Vertrix
  Systems, Northfield Analytics — four distinct fictional names, used both
  as a leading `"About <Company>"` heading and embedded mid-phrase inside
  an otherwise-unrelated LEARNING heading, specifically to test whether a
  design generalizes the *structure* "about a proper noun" / "a company
  name appearing somewhere in a heading" rather than memorizing names.
- **Ambiguous and compound headings, documented honestly**: `"Qualifications
  and Responsibilities"`, `"Required Responsibilities"`, `"Required Skills
  and Responsibilities"` (compound-purpose headings a single section tag
  cannot represent faithfully — annotated `ambiguous: true` with an
  explicit `acceptable_sections` list and a `rationale` explaining the
  judgment call, never silently forced to one answer); `"Technical Skills"`,
  `"The Role"`, `"Growth Opportunities"`, `"Good to Know"` (idiomatic
  headings carrying no reliable root-word signal at all).
- **The milestone's own explicit collision list** — all five are present
  and separately traceable: `m10c-019`/`020` (Preferred Skills/
  Qualifications vs REQUIRED), `m10c-034`/`035` (Skills You'll Learn vs
  REQUIRED), `m10c-041`/`045`–`047` (About Our Team / About
  &lt;fictional company&gt; vs qualifications), `m10c-017` (Required
  Responsibilities vs REQUIRED), `m10c-057`/`058`/`060`/`077` (a genuine
  bulleted-or-bare requirement claim ending in, or containing, a colon vs
  a new section heading).

See the corpus file's own `rationale` field per entry for the full
reasoning; not duplicated here.

---

## 3. Phase 3 — Comparing three classification strategies

Implemented in `scripts/evaluation_lib/heading_classifiers.py`
(evaluation-only; **not imported by `src/gitscore`**) and measured by
`scripts/evaluate_m10c_heading_classification.py` against the Phase 2
corpus. Full numeric results:
`evaluation/reports/m10c_heading_classification_report.{json,md}`.

### 3.1 The three designs

**A — Expanded exact-match vocabulary, normalized.** A direct scale-up of
today's production design (`_HEADING_KIND` table): a bigger, Unicode/
Markdown-normalized table of literal phrases. By construction it has **no
way to represent "heading-shaped but not in my table"** — a phrase not in
the table is indistinguishable from ordinary prose, exactly today's Root
Cause 1/2 precondition, just with a narrower miss rate.

**B — Conservative, anchored heading-pattern families with explicit
precedence.** Two independent stages: a structural "heading-shape" gate
(short; colon-terminated-with-nothing-after, OR Markdown, OR ALL-CAPS, OR
title-cased; never itself a bullet; never ending in sentence-terminal
punctuation; never a colon followed by an inline comma-separated list) —
completely independent of word content — followed by anchored root-word
regex families (`requir*`/`qualif*`-excluding-preferred for REQUIRED,
`preferr*`/`nice-to-have`/`bonus` for PREFERRED, etc.), resolved by a
**fixed total-order precedence** (REQUIRED > PREFERRED > LEARNING >
RESPONSIBILITY > NON_QUALIFICATION) when more than one family's root
matches the same line.

**C — Structured classifier separating detection from purpose, hybrid.**
Reuses B's exact shape gate and root families, with two additions: (1) a
bare, colon-terminated line that ALSO matches `jobs/parsing/parser.py`'s
own already-tested `_TECHNICAL_LEAD_IN` pattern (reused, not reinvented)
is excluded from heading consideration at all — this is what distinguishes
a real heading from an un-bulleted list lead-in like `"Experience with the
following:"`; (2) a line matching **more than one** family is reported as
an explicit `AMBIGUOUS` outcome carrying its candidate families, rather
than forced to one winner by precedence. This is the "hybrid" the
milestone invited consideration of: B's anchored-pattern core, plus reuse
of an already-approved production heuristic, plus an honest third output
state for genuinely compound headings.

### 3.2 Measured results

| Strategy | Heading-detection accuracy | exact_match | safe_disagreement | unsafe_mismatch | Real-posting headings correct (of 11) |
|---|---|---|---|---|---|
| A — expanded exact-match | 0.872 | 68 | 6 | 4 (all **low** severity) | 10 |
| B — anchored patterns, fixed precedence | 0.962 | 74 | 3 | 1 (**high** severity) | 11 |
| C — structured detection + honest ambiguity | **0.987** | **77** | 1 | **0** | **11** |

("Outcome tier" — never a flat pass/fail, per this project's M10B
precedent: `exact_match` = matches the annotated truth, or an
`ambiguous`-flagged entry's `acceptable_sections`; `safe_disagreement` =
wrong but never fabricates a scoring-relevant family — e.g. calling a real
heading `UNKNOWN`, or calling a genuinely ambiguous bare list lead-in a
heading at all; `unsafe_mismatch` = confidently assigns, or confidently
denies, a specific named family against contrary annotated truth.
`severity` on an unsafe mismatch is `high` only when either the truth or
the prediction is REQUIRED or PREFERRED — the only two families that can
ever enter `assess_job()`'s alignment-score denominator at all.)

**Strict per-family precision/recall** (computed only over the
non-ambiguous, `is_heading=true` subset — 65 of 78 entries — so a
genuinely disputed compound heading never pollutes a "hard number"):

- **A**: REQUIRED/PREFERRED/RESPONSIBILITY/LEARNING all 1.000/1.000.
  NON_QUALIFICATION recall drops to **0.842** (misses all three fictional
  companies — `About Lumenbridge`/`Coriander Labs`/`Vertrix Systems` — plus
  a bare "Additional Information" UNKNOWN entry it has no table slot for).
- **B** and **C**: every family 1.000/1.000 on this strict subset —
  including NON_QUALIFICATION for all three fictional companies, confirming
  the anchored `^about\b` structural rule generalizes to names neither
  design has seen, something a closed vocabulary table fundamentally
  cannot do without an unbounded company-name list.

**The one finding that most separates B from C**: B's single
`unsafe_mismatch` is `m10c-017` (`"Required Responsibilities"` → B's fixed
precedence forces **REQUIRED**, contradicting the independently-authored
RESPONSIBILITY-leaning truth) — and it is **high severity**, because
REQUIRED is one of the two scoring-relevant families. C never makes this
call at all: both `"Required Responsibilities"` and
`"Qualifications and Responsibilities"` are reported as `AMBIGUOUS`
(`["REQUIRED", "RESPONSIBILITY"]`), which the scorer credits as an
`exact_match` against those entries' own `acceptable_sections` — not
because C is "right" about an inherently disputed heading, but because C
is **honest about the dispute** instead of confidently picking a side with
no real basis, which is exactly the posture this project's `UNKNOWN`
design (M10B) already established as the correct default for genuine
uncertainty.

**A real-posting corroboration**: all three strategies correctly classify
all 11 of the real SOTI/Manulife headings used as a secondary trace (not
mixed into the corpus-based precision/recall numbers) **except Strategy A,
which misses `"Opportunity"`** (SOTI's own un-categorizable intro heading
— not in any table, reported `NOT_HEADING`) where B and C both correctly
call it `UNKNOWN` (heading-shaped, no family fires, honestly reported as
such rather than silently dropped).

### 3.3 Determinism and maintenance complexity

All three strategies are pure functions of one line of text — no
document-level state, no network calls, no LLM, fully deterministic and
reproducible (confirmed: re-running `evaluate_m10c_heading_classification.py`
produces byte-identical output). Maintenance complexity differs
meaningfully: **A** requires a human to notice and manually add every new
phrasing variant forever (the exact failure mode that produced M10A's
Root Cause 1 in the first place); **B** requires tuning a fixed precedence
order whenever a new collision is discovered, with no way to express "I
am not sure" short of adding yet another exclusion clause; **C** requires
the same root-family maintenance as B, but new collisions default safely
to `AMBIGUOUS` without requiring an immediate precedence decision — lower
ongoing maintenance pressure, at the cost of a second output shape
(`AMBIGUOUS` + candidates) a downstream consumer must know how to handle
(see §4.3).

### 3.4 Recommendation

**Strategy C** (or a near-identical hybrid) is the strongest candidate
measured: highest heading-detection accuracy, zero unsafe mismatches of
either severity, zero strict-metric false positives/negatives on the
confident subset, and the only design that never forces a confident
answer onto a heading this project's own independent annotation could not
confidently resolve either. Its only added complexity is the `AMBIGUOUS`
output shape, discussed in §4.3 as needing its own, explicit answer before
implementation.

---

## 4. Phase 4 — Section-aware claim preservation (investigation, not implementation)

### 4.1 Does fixing heading recognition alone fix claim preservation?

**Mostly, by a mechanism already built into `segmentation.py` — but not
completely.** Re-read of `segment_description()`: for a genuinely
recognized section (`in_recognized_section = current_kind in (REQUIRED,
PREFERRED, RESPONSIBILITY)`), **every contained sentence becomes a `Claim`
unconditionally** — the `_looks_like_requirement()` gate is bypassed
entirely (it only applies when `current_kind` is `None` or `UNKNOWN`).
This means: **if** heading recognition correctly classified SOTI's
`"Required skills:"` as REQUIRED, the "curiosity, a desire to learn..."
bullet would become a `Claim` with `necessity_hint=REQUIRED` — a guaranteed
improvement over today's **zero trace at all**.

**But it would still not become a scored `JobRequirement`.** Traced
through every existing detector in `_requirements_from_claim`:
`find_concept_mentions` (no registered concept), `find_bare_short_alias_mentions`
(no context-cue word present), `find_conservative_unknown_terms` (no
confirmed sibling, no enumeration cue), `find_experience_qualifier`
(no years/experience phrasing), `find_non_technical_match` (none of
`non_technical.py`'s four categories — education/legal/leadership/
soft_skill — covers "curiosity" or "desire to learn"; `soft_skill`'s
pattern requires `communication skills`/`written and verbal`/
`interpersonal skills`/`teamwork`/`cross-functional team`/`collaborat*`,
none of which this bullet contains), `_unresolved_requirement_signal`
(no "or", no enumeration cue, no technical lead-in phrase). **Zero
detectors fire** — but because the claim WAS created (heading correctly
recognized), `_parse`'s existing "zero requirements produced →
`UnparsedClaim`" fallback (already wired, no change needed) guarantees it
at least becomes a diagnostic. **This is the single clearest, most
important finding of Phase 4**: correct heading recognition, by itself,
upgrades this bullet from *zero trace anywhere* to *a guaranteed, honest
diagnostic* — without requiring any new non-technical category, any
concept-registry change, or any claim-preservation mechanism beyond what
already exists. Whether it should go FURTHER (become an actual scored,
non-technical `JobRequirement` — e.g. a new `growth_mindset`/`soft_skill`
pattern recognizing "curiosity"/"desire to learn"/"eagerness to learn") is
a **separate, smaller, concept-registry-adjacent question**, not a
section-classification question at all.

### 4.2 The five "must not" guardrails, checked against the proposed design

- **A requirement must not silently disappear.** §4.1 shows the proposed
  heading fix, by itself, converts the one confirmed real-world case from
  "silently disappears" to "guaranteed diagnostic" — satisfied, with the
  important caveat that "diagnostic" is not "scored requirement" (that
  gap is pre-existing and orthogonal, see §4.1's last sentence).
- **A nontechnical qualification should not be fabricated as a technical
  concept.** Nothing in Strategies A/B/C/the proposed design touches
  concept resolution (`concepts.py`, `alternatives.py`) at all — this
  guardrail is entirely upheld by code this milestone does not propose
  changing.
- **A responsibility should not automatically become a candidate
  requirement.** Confirmed directly: fixing `"Position Responsibilities:"`
  recognition (RESPONSIBILITY family) maps to `Necessity.REQUIRED` in
  `_SECTION_NECESSITY_HINT` — **this is already true today for the
  existing, recognized `RESPONSIBILITY` family** (`"responsibilities"`,
  `"what you will do"`, etc. already map to REQUIRED necessity in
  production, confirmed by direct reading of `segmentation.py` line 118).
  This is a **pre-existing design decision this milestone does not
  revisit** (duties ARE treated as REQUIRED-necessity claims today,
  reflecting that a posting's "what you'll do" section is read as "this is
  what the job requires you to be capable of," not as an optional
  qualification list) — but it IS the reason the six Manulife duty
  bullets, once the heading is recognized, would become `Claim`s with
  `necessity_hint=REQUIRED` and then flow through the SAME detector chain
  as any other claim. None of the six (confirmed, re-traced) contains a
  registered concept or a non-technical pattern match, so **all six would
  still land in `unparsed_claims`, never as a scored `JobRequirement`** —
  the guardrail holds in practice for this specific posting, but it holds
  by *coincidence of content*, not by a structural rule that duties can
  never become requirements. **This is a real, open design question** (not
  resolved by this milestone): should `RESPONSIBILITY`-family content that
  DOES happen to contain a registered concept (e.g., a duty bullet reading
  "Deploy services using Docker and Kubernetes") be allowed to become a
  scored REQUIRED row, exactly as it already can today for any
  RESPONSIBILITY-recognized posting? This milestone takes no position
  beyond flagging it as pre-existing, unchanged behavior.
- **Learning opportunities should not automatically enter scoring.**
  Confirmed: `_SECTION_NECESSITY_HINT` (the dict all three candidate
  classifiers in §3 would still ultimately feed, via whatever production
  change is eventually approved) has **no entry for LEARNING at all** in
  any design proposed here — mirroring `UNKNOWN`'s existing treatment
  exactly (§4.4 of the M10B doc). A LEARNING-recognized claim with no
  local REQUIRED/PREFERRED marker in its own text would resolve to
  `necessity=None` via the exact same `infer_necessity` short-circuit path
  M10B already implemented — **no new mechanism needed**, LEARNING simply
  joins UNKNOWN as a second non-scoring section kind.
- **Company/legal text should not become a qualification.** Already true
  today, post-M10B (§1.3 above) for both real postings, independent of
  this milestone. Recognizing `NON_QUALIFICATION`-family headings by name
  adds transparency (a labeled, recognized "About X"/"Working Arrangement"
  section instead of an opaque `UNKNOWN` span) without changing any
  requirement outcome for either real posting — confirmed, §1.3.
- **Ambiguous text should remain distinguishable from confidently
  interpreted requirements.** This is exactly what `AMBIGUOUS` (§3, design
  C) and the existing `UNKNOWN`/diagnostic-vs-excluded split already do;
  see §4.3 for the one open representational question this raises.

### 4.3 Does `UnparsedClaim` sufficiently distinguish unsupported parsing from intentional exclusion?

**No — and this is the one place Phase 4 found a real, if narrow,
representational gap**, distinct from anything already flagged in M10A/
M10B. Today, `UnparsedClaim` means exactly one thing: "this claim survived
segmentation's requirement-shape gate, but zero detectors could
responsibly produce a `JobRequirement` for it." It does **not**, and
cannot today, distinguish:

1. A claim under a **confidently-recognized REQUIRED/PREFERRED** heading
   that no detector could resolve (e.g. the SOTI curiosity bullet, §4.1) —
   high-confidence SECTION, low-confidence CONTENT.
2. A claim under an **UNKNOWN/ambiguous** heading that happened to pass the
   outside-heuristic gate (e.g. M10B's own salary-disclosure diagnostic) —
   low-confidence SECTION, and therefore low-confidence everything.
3. (A hypothetical, not yet real for either posting) A claim under a
   section whose heading was itself classified `AMBIGUOUS` (§3, design C)
   between two named families, e.g. a bullet under a compound
   `"Qualifications and Responsibilities"` heading.

All three currently collapse into the same flat `UnparsedClaim(text,
source_span)` shape. This is **not a bug this milestone is reporting as
broken** — M9C's own design rationale (an `UnparsedClaim` is a pipeline
diagnostic, never domain state) is still sound — but a caller consuming
`unparsed_claims` today (e.g. a future UI surfacing "things we couldn't
parse") cannot currently prioritize case 1 (probably a real, missed
qualification worth a human's attention) over case 2 (probably noise) or
represent case 3 (a structurally uncertain section, not a content
uncertainty) at all. **No new schema change is proposed here** — this is
flagged as an open question for whoever scopes the eventual implementation
milestone, with three honestly-stated options, not a recommendation:

- (a) Leave `UnparsedClaim` exactly as-is; accept that section-confidence
  and content-confidence are conflated in this one diagnostic shape.
- (b) Add an **optional, additive** field to `UnparsedClaim` (e.g.
  `section_confidence: Literal["recognized", "unknown", "ambiguous"] |
  None`) — a real, if small, schema change requiring its own STOP/approval
  per this project's standing rule (`docs/PIPELINE.md`'s versioning
  convention).
- (c) Keep `UnparsedClaim` unchanged and instead let a caller re-derive
  this distinction itself from the `JobRequirementProfile` section
  structure it would need anyway for a future "show requirements grouped
  by section" UI feature — deferring the question entirely to that
  separate, not-yet-scoped UI milestone.

This document takes no position among (a)/(b)/(c) — it is explicitly
flagged as a Phase 6 approval question (§6.8).

---

## 5. Phase 5 — End-to-end evaluation plan (proposed, most not yet executed)

Executed this session (read-only, against the existing, unmodified
production parser and existing committed reports — no candidate design was
wired into production code for this):

- **M10C heading benchmark** — executed, §3 above, reproducible via
  `python scripts/evaluate_m10c_heading_classification.py`.
- **Frozen 8c:v1 / 8c:v1.1, M9B preservation, M10A real-world** — re-run
  and diffed byte-identical against their committed reports (§0 above);
  **unaffected by anything in this milestone**, since no production file
  changed.
- **M10B's 12 controls** — not re-executed as a formal pytest run this
  session (the 28 real tests in `tests/test_m10b_section_state_safety.py`
  already ran as part of the full 975-test suite, §0); not re-derived
  independently here since M10B's design doc already reports them
  passing 11/11 (12/12 post-amendment) and nothing in this milestone
  touches `necessity.py`'s `UNKNOWN`-short-circuit logic.

**Proposed, NOT executed this session** (would require either implementing
a candidate design into `src/gitscore` under its own approval, per scope
restrictions, or a second standalone-prototype pass mirroring M10B's own
§4.1/§5 "prototype using real, unmodified detector code" precedent):

1. **Before/after on the real SOTI/Manulife postings**, prototyped the
   same way M10B's design review was (a standalone copy reusing the real
   `alternatives.py`/`concepts.py`/`non_technical.py`/etc. verbatim,
   never merged into `src/gitscore`) — measuring, separately and never
   summed: new `JobRequirement` row count by necessity, new
   `unparsed_claims` count, which specific M10A-catalogued gaps close
   (expected: the `"About SOTI"`/`"Required skills:"`/`"What you will
   learn:"` SOTI gaps and all seven Manulife heading gaps from §1.2),
   which do not (Root Causes 4/5 — alternative-list parsing — explicitly
   untouched, per scope restriction), and the resulting `alignment_score`
   delta for a representative candidate against each posting.
2. **Heading classification precision/recall by section type** — already
   executed (§3.2); would be re-measured identically once a specific
   design is approved and actually implemented, to confirm the prototype
   numbers match the shipped implementation exactly (mirroring M10B's own
   §5-vs-§11.4 before/after discipline).
3. **False-positive candidate requirements** — zero introduced by any of
   A/B/C against the corpus (§3.2's `unsafe_mismatch` column); would be
   re-measured against the two real postings once implemented.
4. **Invisible genuine qualifications** (never summed with duties) —
   expected to drop from SOTI's 1 to 0 (§4.1); Manulife's is already 0
   (M10A/M10B, unaffected — its gap is entirely `invisible_responsibilities`).
5. **Invisible responsibilities/duties, separately** — expected to drop
   from Manulife's 6 to 0 *trace* (all six would become `unparsed_claims`,
   §4.2) but **remain 0 scored requirements** (none contains a resolvable
   concept) — this is the headline, measurable Phase 5 claim once
   implemented: transparency gained, zero scoring change.
6. **Diagnostic count and quality** — expected to shift, not just shrink:
   fewer `unparsed_claims` from pure company/legal/culture prose (now
   correctly excluded via a recognized `NON_QUALIFICATION` section,
   mirroring M10B's own already-measured Manulife reduction, 27→5, for a
   *different* root cause), offset by new diagnostics from genuinely
   recognized-but-undetected content (the SOTI curiosity bullet, the six
   Manulife duty bullets) — a **composition change**, not simply "fewer is
   better."
7. **Genuine requirements incorrectly excluded** — the explicit regression
   check any implementation must pass: re-verify, entry-by-entry against
   `evaluation/m10/corpus.json`'s own `is_requirement` annotations (exactly
   as M10B's §11.4 did), that zero previously-correct rows are lost.
8. **Required/preferred row-count changes, and score-denominator changes**
   — expected zero change for both real postings under a heading-only fix
   (§4.1/§4.2 show the newly-recognized content stops at the diagnostic
   layer for both confirmed cases) — this would need explicit
   confirmation once a design is actually implemented, not assumed.
9. **Remaining limitations in SOTI and Manulife, explicitly** — Root
   Causes 4 and 5 (the Manulife "at least one programming language (e.g.,
   ...)" OR-structure loss, and SOTI's "one or more of" idiom-blind
   splitting) are **completely untouched by anything in this milestone**,
   exactly as scoped ("Do not fix alternative-list semantics — reserved
   for M10D"). Confirmed by direct re-reading of `alternatives.py`: no
   change proposed or made.

**Explicitly not optimized for only the two real postings**: §3's
corpus-based precision/recall (the primary Phase 3 metric) is computed
over the independently-authored 78-entry benchmark, not the two postings;
the real-posting trace (§3.2's rightmost column) is reported as a
secondary corroboration, never the basis for choosing among A/B/C.

---

## 6. Phase 6 — Architectural proposal

### 6.1 Recommended heading-recognition design

**Strategy C** (§3.1/3.4): a structural heading-shape gate fully
independent of word content, an anchored root-word family classifier
reusing the already-tested `_TECHNICAL_LEAD_IN` production pattern as an
exclusion, and an explicit `AMBIGUOUS` output for genuinely compound
headings instead of a forced single answer.

### 6.2 Exact recognition and normalization rules (as measured, §3)

- **Heading-shape gate** (word-content-independent): not bullet-prefixed;
  not ending in sentence-terminal punctuation (`.`/`!`/`?`); not a colon
  with non-empty, comma-containing text after it on the same line (the
  explicit fix for `"Experience with: Python, JavaScript"`); word count
  (ignoring a stripped trailing bare colon) between 1 and 7; AND at least
  one of: ends in a bare colon with nothing following, OR is a Markdown
  ATX heading (`^#{1,6}\s`) or bold-wrapped (`^\*\*.*\*\*$`), OR is fully
  upper-case, OR is "title-cased" (every word capitalized except a small,
  fixed set of lowercase-tolerated function words: a/an/the/of/in/on/and/
  or/to/for/at/by/as).
- **Lead-in exclusion**: a line that ALSO matches
  `_TECHNICAL_LEAD_IN` (`^(?:experience with|knowledge of|familiarity
  with|proficiency in|proficient in|expert in)\s+`) is excluded from
  heading consideration even if it passed the shape gate — this is what
  correctly excludes a bare (unbulleted) `"Experience with the
  following:"`/`"Familiarity with the following tools:"`.
- **Unicode normalization**: strip `U+200B`/`U+200C`/`U+200D`/`U+FEFF`
  (zero-width characters — invisible but NOT covered by Python's `\s`/
  `.strip()`) explicitly, before any other processing; `\s`-based
  whitespace collapsing already correctly handles `U+00A0` (NBSP) with no
  special-casing needed (confirmed, `m10c-015`).
- **Family roots** (anchored, word-boundary-bounded, case-insensitive):
  REQUIRED = `requir*` / `must[- ]have*` / `mandatory`, OR `qualif*` when
  no PREFERRED root is also present in the same line; PREFERRED =
  `preferr*` / `nice[- ]to[- ]have*` / `bonus*` / `"a plus"`; LEARNING =
  `"you'll/will learn/gain"` / `"learning opportunit*"` / `"growth
  opportunit*"` / `"skills you'll/will learn/gain"`; RESPONSIBILITY =
  `respons*` / `duties` / `duty` / `"what you'll/will do"` / `"the role"`
  / `"day in this role"`; NON_QUALIFICATION = a line **starting with**
  `"about"` (structural, generalizes to any proper noun, never a company
  list) / `benefit*` / `perk*` / `compensation` / `salary` / `"equal
  opportunity"` / `"how to apply"` / `"application process/instructions"`
  / `diversity` / `accommodation` / `"working arrangement"` / `"why join
  us"` / `"our values"` / `"who we are"` / `"what we offer"` / `"when you
  join our team"`.
- **Explicit known residual gap** (not solved by any of A/B/C, honestly
  reported): a heading idiom carrying **no** root word at all —
  `"Technical Skills"`, `"Core Competencies"` (hypothetical) — cannot be
  recognized by B or C without either (i) a small, explicitly-curated list
  of such known idioms layered on top of the root families (the same
  technique already used for `"the role"`/`"day in this role"`), or (ii) a
  looser root (e.g. a bare `skills` root), which §3.2's `m10c-019`
  ("Preferred Skills" must NOT become REQUIRED) explicitly rules out as
  unsafe. This document recommends (i) if "Technical Skills" recognition
  is wanted at all — adding it to the REQUIRED family as a fixed idiom
  phrase, exactly like `"the role"` — but takes no position on whether
  it's worth adding versus leaving as `UNKNOWN` (§6.8, question 4).

### 6.3 Classification precedence and ambiguity policy

**No fixed total-order precedence.** A line matching exactly one family
resolves to that family. A line matching zero families resolves to
`UNKNOWN`. A line matching more than one family resolves to a new,
explicit `AMBIGUOUS` outcome carrying its candidate family set — **never**
silently collapsed to a single winner. §3.2's measured evidence
(`m10c-017`, high-severity) is the direct justification: a fixed
precedence order picked the less-defensible of two readings on a real,
if invented-for-testing, heading shape.

### 6.4 Interaction with M10B's `UNKNOWN` state

**Fully compatible, additive, no conflict.** M10B's `_SectionKind.UNKNOWN`
already means exactly "an unrecognized heading followed a real recognized
one, with no necessity default" — nothing in this proposal changes that
meaning. What changes is the **denominator** of "recognized": every
heading Strategy C's families newly recognize (REQUIRED/PREFERRED/
RESPONSIBILITY, exactly as today, PLUS the two new LEARNING and
NON_QUALIFICATION kinds) shrinks how often `UNKNOWN` fires at all — but
`UNKNOWN` itself, and its non-scoring guarantee, is untouched. A line
Strategy C itself calls `UNKNOWN` (no family root fired) would feed
`_SectionKind.UNKNOWN` exactly as an unrecognized heading does today.

### 6.5 How unknown headings transition between sections, under the proposed design

Unchanged from M10B's already-approved, already-implemented rule
(`segmentation.py`'s existing trigger: colon-terminated, not bulleted, only
resets from an already-real recognized kind) — **this milestone does not
propose changing that trigger rule at all**, only the TABLE of what counts
as "recognized." The one new wrinkle: should `LEARNING` and
`NON_QUALIFICATION` count as "real recognized kinds" for the purposes of
M10B's own reset-trigger (i.e., can `UNKNOWN` be reached by falling off
the end of a `LEARNING` section the same way it can today from REQUIRED/
PREFERRED/RESPONSIBILITY/SKIP)? **Recommended: yes, symmetrically** —
anything else would reintroduce a scoped-down version of the exact
sticky-inheritance bug M10B fixed, just for the two newly-added kinds.
This is flagged explicitly as approval question 3 (§6.8) rather than
assumed.

### 6.6 False-positive/false-negative tradeoffs (final accounting)

**Gained**: recognition of 5 of M10A's 8 confirmed heading misses
(`"Required skills:"`, `"About SOTI"`, `"Position Responsibilities:"`,
`"About Manulife and John Hancock"`, `"Working Arrangement"` — directly
measured, §3.2's real-posting trace) plus 2 more via the new LEARNING/
NON_QUALIFICATION categories (`"What you will learn:"`,
`"When you join our team:"`/`"Application instructions:"`) — **8 of 8**
under Strategy C specifically. **Lost/risked**: zero unsafe mismatches
measured anywhere in the 78-entry corpus for Strategy C; the one residual,
explicitly-acknowledged gap is idiom-only headings with no root word at
all (§6.2's "Technical Skills" case), which fails SAFELY (falls to
`UNKNOWN`, never a wrong confident family) rather than dangerously.

### 6.7 Source-span and provenance guarantees

**Unaffected.** None of A/B/C touches `Claim.start`/`Claim.end` computation
(`_line_content_span`/`_trim_span`, unchanged in every design discussed) —
heading classification only decides what `current_kind` becomes and
whether a line itself becomes a `Claim` at all (a heading line never does,
in any design, exactly as today); every surviving claim's exact character
offsets into the original `description` are computed by the same,
untouched code path.

### 6.8 Does claim preservation (Phase 4) need its own implementation sub-milestone?

**Yes, explicitly recommended as separate from the heading-classification
work itself**, for two reasons: (1) §4.1 shows heading recognition alone
already delivers the measurable, scoped win (zero-trace → guaranteed
diagnostic) without touching `non_technical.py`/concept registry at all —
bundling a concept-registry expansion into the SAME change would conflate
two independently-approvable, independently-testable risk surfaces; (2)
§4.3's `UnparsedClaim`-granularity question is explicitly a schema
question (option (b)) that may not even be wanted — resolving it should
not block shipping the heading-classification fix itself, which needs no
schema change of any kind.

### 6.9 Proposed parser versioning

If Strategy C (or an equivalent design) is approved and implemented in a
future milestone: `JOB_DESCRIPTION_PARSER_VERSION` bumps `v5` → `v6`, per
this package's own existing convention (a parsing-decision-logic change,
not a schema/shape change) — mirroring M10B's own `v4`→`v5` precedent
exactly. No `JOB_REQUIREMENT_SCHEMA_VERSION`, `MATCHER_VERSION`, or
`SCORING_VERSION` change is implied by anything in this document.

### 6.10 Explicit STOP/approval decisions

This document is the STOP point. **No production code has been written or
is proposed for immediate implementation.** The following need affirmative
approval before any future implementation milestone begins:

1. **Approve Strategy C's overall shape** (structural shape-gate +
   anchored root families + reused lead-in exclusion + `AMBIGUOUS` output)
   as the design basis for a future implementation milestone, over
   Strategy A (rejected — cannot represent "heading-shaped but unknown,"
   the direct cause of Root Cause 1/2) or Strategy B alone (the one
   measured high-severity mismatch, §3.2) — or request changes to the
   specific root patterns/shape rules in §6.2 before approval.
2. **Approve introducing exactly two new section kinds** (`LEARNING`,
   `NON_QUALIFICATION`-as-a-named-internal-kind — note `NON_QUALIFICATION`
   already exists today as `_SectionKind.SKIP`; this is a **rename/
   generalization** of the existing SKIP mechanism's vocabulary table, not
   a new behavior) plus the new `AMBIGUOUS` outcome as an internal
   classification-time construct. **Open sub-question**: should
   `AMBIGUOUS` map to `_SectionKind.UNKNOWN` directly (simplest, reuses
   M10B's existing non-scoring machinery with zero further change), or
   does it need its own internal state? **This document recommends
   mapping `AMBIGUOUS` directly to `UNKNOWN`** — identical non-scoring
   behavior, zero new `Necessity`-adjacent surface — but flags it as a
   decision needing explicit sign-off, not assumed.
3. **Approve §6.5's symmetry decision**: `LEARNING` and
   `NON_QUALIFICATION` count as "real recognized kinds" for M10B's
   existing UNKNOWN-reset trigger, exactly like REQUIRED/PREFERRED/
   RESPONSIBILITY/SKIP already do.
4. **Decide whether to add a small, explicitly-curated idiom-phrase list**
   (`"Technical Skills"`, and any others a future curator identifies) on
   top of the root families, accepting Strategy A's exact-match technique
   in this one narrow, explicitly-bounded role (never as the primary
   mechanism) — or leave such idioms as `UNKNOWN` indefinitely. No default
   is recommended; this is a pure product-judgment call with no safety
   implication either way (both resolve safely, differing only in
   transparency/recall).
5. **Decide the `UnparsedClaim` granularity question from §4.3** — options
   (a) leave as-is, (b) add an additive `section_confidence` field
   (requires its own schema-change approval), or (c) defer to a future
   UI-facing milestone that re-derives this from section structure
   directly. No default is recommended.
6. **Confirm Phase 4's scope boundary**: this milestone recommends
   treating "fix heading recognition" and "expand non-technical claim
   preservation" (e.g., a new `growth_mindset`/curiosity-pattern category
   in `non_technical.py`, hypothetically closing the SOTI gap all the way
   to a scored row rather than stopping at a diagnostic) as **two
   separate future sub-milestones**, per §6.8 — approve, or request they
   be combined?
7. **Approve `JOB_DESCRIPTION_PARSER_VERSION` v5 → v6`** as part of
   whatever future implementation is eventually approved, per §6.9.

None of these decisions require touching the concept registry, matcher,
assessment formula, frozen gold, alternative-list parsing (M10D's scope),
or frontend presentation.

---

## 7. Files added this milestone

- `evaluation/m10c/heading_controls.json` (new, additive — 78
  independently-authored heading/non-heading controls)
- `scripts/evaluation_lib/heading_classifiers.py` (new, additive — three
  candidate classifier implementations; **not imported by `src/gitscore`**)
- `scripts/evaluate_m10c_heading_classification.py` (new, additive,
  read-only measurement harness)
- `evaluation/reports/m10c_heading_classification_report.{json,md}` (new,
  generated by the script above)
- `docs/evaluation/MILESTONE_10C_SECTION_CLASSIFICATION.md` (this file)

**No file under `src/gitscore/` was modified. No frozen gold was modified.
`python -m pytest` remains 975 passed, unchanged.**

---

## Reproduction

```powershell
python -m pytest                                              # 975 passed, unchanged
python scripts/evaluate_m10c_heading_classification.py        # writes evaluation/reports/m10c_heading_classification_report.{json,md}
python scripts/evaluate_m10a_realworld.py                     # byte-identical to committed report
python scripts/evaluate_m9b_preservation.py                   # byte-identical to committed report
git diff --stat evaluation/gold evaluation/gold_v1_1           # empty
```

**DO NOT COMMIT. DO NOT PUSH. DO NOT IMPLEMENT ANY `src/gitscore` CHANGE
BEFORE THE §6.10 APPROVAL QUESTIONS ARE ANSWERED.**

---

## 8. Post-approval addendum — actual implementation

All seven §6.10 approval questions were explicitly decided. This
section records the design-gate mapping, what was actually implemented,
the real regression found and fixed before it landed, and the measured
results — as distinct from §1–7's design-review-only prototype numbers.

### 8.1 The seven §6.10 questions, reproduced verbatim, mapped to the approved decisions

**1. Approve Strategy C's overall shape... over Strategy A... or Strategy
B... — or request changes to the specific root patterns/shape rules in
§6.2 before approval.**
→ **Approved: Strategy C**, via decisions 1 ("Use Strategy C: separate
structural heading detection from semantic section-purpose
classification") and 4 ("Use curated, anchored, generalizable heading
patterns rather than unrestricted substring or company-specific
matching"). Implemented as `segmentation.py::_classify_heading_line()`.
One root-pattern change from §6.2's draft, found necessary during
implementation (not a design-gate question, a regression) — see §8.3.

**2. Approve introducing exactly two new section kinds (`LEARNING`,
`NON_QUALIFICATION`-as-a-named-internal-kind)... Open sub-question:
should `AMBIGUOUS` map to `UNKNOWN` directly... or does it need its own
internal state?**
→ **Approved, with the recommended answer confirmed**, via decision 2
("Prefer conservative ambiguity handling to forced REQUIRED/PREFERRED
classification") and decision 3 ("Do not let ambiguous headings inherit
necessity from an earlier section"). **Implemented exactly as
recommended**: `AMBIGUOUS` (a line matching more than one family) maps
directly to the existing `_SectionKind.UNKNOWN` — zero new `Necessity`-
adjacent surface. `NON_QUALIFICATION` maps to the EXISTING `_SectionKind.SKIP`
(a vocabulary expansion, not a new kind — confirmed in §6.2 but worth
restating: only `LEARNING` is a genuinely new internal enum member).

**3. Approve §6.5's symmetry decision: `LEARNING` and
`NON_QUALIFICATION` count as "real recognized kinds" for M10B's
existing UNKNOWN-reset trigger, exactly like REQUIRED/PREFERRED/
RESPONSIBILITY/SKIP already do.**
→ **Approved**, via decision 3. **Required zero additional code**:
M10B's actual, shipped trigger condition is `current_kind is not None`
(not an explicit real-kinds tuple as its own docstring summarized it) —
`LEARNING` and `SKIP`-via-`NON_QUALIFICATION` both already satisfy "not
`None`," so the symmetry holds automatically. Confirmed by direct
reading and by `test_recognized_section_after_learning_is_not_sticky`/
`test_learning_section_does_not_stay_sticky_into_unknown_then_required`
(`tests/test_m10c_heading_classification.py`).

**4. Decide whether to add a small, explicitly-curated idiom-phrase
list ("Technical Skills," and any others)... or leave such idioms as
`UNKNOWN` indefinitely. No default is recommended.**
→ **Not explicitly resolved by name in the approved decisions** — this
is the one question the mandatory design gate flags as not fully
covered. **Resolved conservatively during implementation**: NO
additional curated idiom phrases were added beyond what Phase 3's
already-measured Strategy C implementation used (`"the role"`/`"day in
this role"`, baked into the RESPONSIBILITY root; `"you will/'ll
learn/gain"`, baked into the LEARNING root). `"Technical Skills"`
remains `UNKNOWN` (unrecognized). Justification: decision 4's own
wording ("curated, ANCHORED, GENERALIZABLE heading patterns") describes
a root/idiom-pattern technique, not an open invitation to add more
single, non-generalizing exact phrases on top of it; and the
already-validated numbers in §3/§8.4 reflect exactly this scope,
unexpanded. **This resolution did not require a STOP** — it carries no
schema/API/matcher/scoring implication and its worst case (a known
idiom classified `UNKNOWN` instead of a named family) is explicitly
safe by this milestone's own design. Revisiting it (adding "Technical
Skills" and similar idioms) remains open for a future, separately-scoped
pass if desired.

**5. Decide the `UnparsedClaim` granularity question from §4.3 — options
(a) leave as-is, (b) add an additive `section_confidence` field..., or
(c) defer to a future UI-facing milestone... No default is recommended.**
→ **Resolved: option (a)**, via decision 6 ("Reuse the existing
UnparsedClaim mechanism where appropriate. Do not add a public
diagnostic schema in M10C"). `UnparsedClaim` is byte-for-byte unchanged
— confirmed, `git diff` shows no change to `jobs/models.py` or
`jobs/parsing/parser.py`'s `UnparsedClaim` class.

**6. Confirm Phase 4's scope boundary: treat "fix heading recognition"
and "expand non-technical claim preservation"... as two separate future
sub-milestones — approve, or request they be combined?**
→ **Approved as separate**, via decision 7 ("Treat broad claim-
preservation and concept-recognition improvements as a separate
submilestone"). `non_technical.py`, `concepts.py`'s concept-matching
logic, and the concept registry are untouched — confirmed by `git
diff --stat` (§8.2). The one exception, flagged honestly rather than
treated as scope creep: Manulife's "Collaborate..." bullet now
triggers the PRE-EXISTING `soft_skill` pattern as a direct, unavoidable
SIDE EFFECT of RESPONSIBILITY recognition (not a new pattern, not a new
category, not a registry change) — see §8.4.

**7. Approve `JOB_DESCRIPTION_PARSER_VERSION` v5 → v6 as part of
whatever future implementation is eventually approved.**
→ **Approved**, via decision 8 ("Bump parser version v5 → v6 if
production parsing behavior is changed"). Implemented — behavior did
change (confirmed throughout §8.4), so the bump applies.

### 8.2 Implemented files and exact scope

| File | Change |
|---|---|
| `src/gitscore/jobs/parsing/segmentation.py` | `_HEADING_KIND`/`_REQUIRED_HEADINGS`/`_PREFERRED_HEADINGS`/`_RESPONSIBILITY_HEADINGS`/`_SKIP_HEADINGS` removed entirely (every phrase they listed is also matched by the new anchored families, confirmed by the full regression suite). New `_SectionKind.LEARNING`. New `_classify_heading_line()` + helpers (`_strip_heading_decoration`, `_is_titlecase_heading`, `_has_inline_colon_list`, `_matched_heading_families`) + five anchored root-pattern constants. `segment_description()`'s heading-check block replaced by one call to `_classify_heading_line()`; `necessity_hint` computation widened to treat `LEARNING` the same as `UNKNOWN`. |
| `src/gitscore/jobs/parsing/concepts.py` | `TECHNICAL_LEAD_IN` moved here from `parser.py` (still used only by `parser.py` — a cross-module reuse attempt in `segmentation.py` was tried and reverted, §8.3). |
| `src/gitscore/jobs/parsing/parser.py` | Imports `TECHNICAL_LEAD_IN` from `concepts.py` instead of defining its own copy; `JOB_DESCRIPTION_PARSER_VERSION` bumped `v5` → `v6`; module docstring updated. |
| `tests/test_m10c_heading_classification.py` | **New, 121 tests** — both the 78-entry design corpus and a NEW, independently-authored, post-implementation 18-entry held-out set (`evaluation/m10c/heading_controls_heldout.json`), run against the real, shipped `_classify_heading_line`; section-transition, Unicode/Markdown/bullet-formatting, no-scoring-from-LEARNING/NON_QUALIFICATION, source-span/determinism coverage. |
| `tests/test_m10b_section_state_safety.py` | **Two assertions amended** (`m10b-07`, `m10b-10`, plus `test_unknown_section_claim_never_fabricates_a_necessity`) via an explicit, documented override dict — see §8.5. `evaluation/m10b/section_state_controls.json` itself is **byte-for-byte unmodified**. |
| `evaluation/m10c/heading_controls_heldout.json` | **New** — the 18-entry held-out set. |
| `scripts/evaluation_lib/heading_classifiers.py` | Updated to match the real, shipped `_classify_heading_line` exactly (the weak-signal/family-match fix and the `TECHNICAL_LEAD_IN` reversion, §8.3) — kept in sync so §3's numbers describe what actually ships, not a stale draft. |
| `evaluation/m10/corpus.json` | **Notes-only** updates to 7 entries (`m10a-soti-12`, `m10a-man-03/04/05/06/07/08`) whose `notes` field described a now-superseded mechanism ("never becomes a Claim") — `is_requirement`/`ideal_outcome`/`acceptable_fallback` for every entry are **byte-for-byte unchanged**; only the factual mechanism description was corrected. See §8.4. |
| `evaluation/reports/m10a_realworld_report.json`, `m9b_preservation_report.{json,md}`, `m10c_heading_classification_report.{json,md}` | Regenerated by the scripts above. |

**No file under `src/gitscore/concepts/`, `src/gitscore/matching/`,
`src/gitscore/assessment/`, or `src/gitscore/evidence/` was touched.
No frozen gold under `evaluation/gold/` or `evaluation/gold_v1_1/` was
touched. `evaluation/m10b/section_state_controls.json` and
`evaluation/m9b/corpus.json` were NOT modified.**

### 8.3 Real regressions found and fixed before landing

**Regression 1 (production-breaking, caught by a PRE-EXISTING test).**
An early version of `_classify_heading_line()` treated ANY plain
title-cased line (no colon/ALL-CAPS/Markdown) as heading-shaped,
including a single bare word. This classified `"Python"` standing
alone on its own line (an un-bulleted, one-item-per-line requirement
list — `"Requirements:\nPython\nPostgreSQL\nDocker\n"`) as a phantom
`UNKNOWN` heading, which reset `current_kind` away from `REQUIRED` and
caused `test_newline_separated_requirements_without_bullets`
(pre-existing, part of the original 975) to fail. **Fixed**: plain
title-case alone now ALSO requires at least one matched family root to
count as heading-shaped; a STRONG signal (colon-terminated-with-nothing-
after, ALL-CAPS, Markdown) remains sufficient on its own, unaffected.
**Accepted tradeoff, confirmed and documented, not hidden**: a rare,
family-root-less generic catch-all heading with no colon/ALL-CAPS/
Markdown at all (e.g. `"Additional Information"`) is now also left
unrecognized — safe (falls through exactly as it did before M10C;
never fabricates a family), not a regression against the pre-M10C
baseline. This also means SOTI's own `"Opportunity"` heading (a single
bare word, no family root) is NOT recognized either — see §8.4 for why
this specifically keeps SOTI's one pre-existing false positive
unchanged rather than fixing it as an earlier design-doc draft of this
addendum briefly, and incorrectly, claimed before this regression was found.

**Regression 2 (production-breaking, caught by a PRE-EXISTING test).**
An early version reused `concepts.TECHNICAL_LEAD_IN` (the same pattern
`parser.py` uses for its own last-resort placeholder) to exclude a bare,
colon-terminated requirement-claim lead-in (`"Experience with the
following:"`) from heading detection entirely. This broke
`test_non_bulleted_colon_heading_still_resets_state`: such a line,
INSIDE an already-open recognized section, must still reset state to
`UNKNOWN` (Milestone 10B's existing, already-shipped, already-tested
behavior) so the lead-in line itself never becomes a spurious claim —
excluding it from heading detection let it fall through as an ordinary
claim under the still-open section instead, producing a spurious
`unresolved_requirement` row for the lead-in text. **Fixed**: the
`TECHNICAL_LEAD_IN` exclusion was removed from `_classify_heading_line()`
entirely; `_has_inline_colon_list` (an independent, already-present
check) still correctly excludes the DIFFERENT shape this milestone's
own corpus names explicitly (`"Experience with: Python, JavaScript"` —
a comma-separated list AFTER a non-terminal colon). `TECHNICAL_LEAD_IN`
itself stays moved to `concepts.py` (used only by `parser.py` now) since
that module is already this package's shared home for such constants;
no functional harm in leaving it there unused by `segmentation.py`.

**Both regressions were caught by the PRE-EXISTING 975-test baseline,
not by any new M10C test** — confirming the existing regression suite's
value, and that no implementation change shipped without the full
suite passing first.

### 8.4 Before/after measurement (real postings, M10B's 12 controls, M9B, 8c)

```
python -m pytest                                    # 1096 passed (975 baseline + 121 new), 0 failed
python scripts/evaluate_m10c_heading_classification.py
python scripts/evaluate_m10a_realworld.py
python scripts/evaluate_m9b_preservation.py
python scripts/evaluate_job_parser.py
python scripts/evaluate_job_parser.py --corpus-version 8c:v1.1
```

**M10C heading corpus** (`evaluation/reports/m10c_heading_classification_report.md`,
re-measured against the FINAL, post-regression-fix implementation —
honestly worse than §3's pre-fix draft numbers, which this addendum
supersedes):

| Strategy | Detection accuracy | unsafe_mismatch (severity) |
|---|---|---|
| A — expanded exact-match | 0.872 | 4 (all low) |
| B — anchored patterns, fixed precedence | 0.923 | 2 (1 high, 1 low) |
| C — structured detection + honest ambiguity | **0.923** | **1 (low)** |

C's one remaining unsafe mismatch is the accepted `"Additional
Information"` tradeoff (§8.3, low severity — never a REQUIRED/PREFERRED
misassignment). **C remains the clear best choice** among the three —
the honest, post-fix numbers change, the recommendation does not.

**Held-out set** (`evaluation/m10c/heading_controls_heldout.json`, 18
entries, authored AFTER Strategy C was selected and implemented):
all 18 score `exact_match` or `safe_disagreement`; **zero**
`unsafe_mismatch` (`tests/test_m10c_heading_classification.py::test_heldout_corpus_all_exact_or_safe`).
Two entries landed as the anticipated, pre-declared `safe_disagreement`
(`heldout-04`, a RESPONSIBILITY idiom variant that does not generalize
as written, flagged ambiguous BEFORE this set was run; `heldout-07`/
`heldout-11`, deliberately root-less headings authored to test that the
classifier does not overreach).

| Metric | SOTI (12 claims) | Manulife (43 claims) |
|---|---|---|
| False-positive requirements | 1 (unchanged — `"Opportunity"` is a bare-word, family-root-less heading, §8.3) | 1 (**new**: `m10a-man-06`, see below) |
| Invisible genuine qualifications (never trace) | **0** (was 1 — `m10a-soti-12` now reaches `unparsed_claims`) | 0 (unchanged) |
| Invisible responsibilities/duties (never trace) | 0 (unchanged) | **0** (was 6 — all six `"Position Responsibilities"` bullets now reach at least `unparsed_claims` or a scored row) |
| Malformed alternative groups | 0 (unchanged) | 1 (unchanged — `m10a-man-10`, Root Cause 4, out of scope) |
| `meets_ideal_outcome` | 6/12 (unchanged) | 39/43 (was 34/43) |
| `meets_neither` (genuine, flagged defect) | `m10a-soti-01` only (SOTI's pre-existing false positive) | `m10a-man-06`, `m10a-man-10` (down from 7: `03/04/05/06/07/08/10`) |

**Required/preferred row-count and score-denominator changes**: SOTI —
zero (the curiosity bullet moves from zero trace to `unparsed_claims`,
never a scored row, so it does not enter `assess_job()` at all).
Manulife — five duty bullets move from zero trace to `unparsed_claims`
(also never scored); ONE duty bullet (`m10a-man-06`, "Collaborate with
engineering and business teams to build user-focused solutions") now
produces a real, scored `JobRequirement` (`category='soft_skill'`,
`necessity=REQUIRED`, `concept_id=None`) via `non_technical.py`'s
PRE-EXISTING `collaborat*` pattern — flagged explicitly: `concept_id=None`
means it is `NOT_ASSESSABLE` and **never enters `assess_job()`'s
denominator**, so `alignment_score` itself is unaffected, but the
requirement LIST a caller would see gains one new, visible, non-
fabricating REQUIRED row sourced from a job-duty sentence. This is the
ONE place this milestone's own §4.2 Phase-4 open question ("should
RESPONSIBILITY content that happens to contain a registered pattern
become a scored row?") turned out to be live, not hypothetical — not
resolved here (per decision 7/question 6's scope boundary), only
measured and disclosed. `evaluation/m10/corpus.json`'s own `notes`
fields for all seven affected entries were corrected to describe this
reality (§8.2); `is_requirement`/`ideal_outcome`/`acceptable_fallback`
for every entry are unchanged.

**M9B preservation**: all 10 metrics byte-identical; only
`parser_version_under_test` changed (`v5`→`v6`), confirmed via
`git diff`.

**Frozen 8c:v1 / 8c:v1.1**: **zero diff** — `git diff --stat` against
both committed `parser_report*.{json,md}` files is empty. Recall/
Precision unchanged (0.621/0.771 and 0.699/0.857 respectively).

**Explicitly verified, per the specific request to check it**: the
SOTI internship-learning C#/SQL paragraph (`"The technologies you learn
during an internship at SOTI range from learning to develop middle tier
services using languages like C#, or deepening your knowledge of
databases by leveraging SQL..."`) **still produces a fabricated REQUIRED
`(language.csharp, language.sql)` alternative group — UNCHANGED by this
milestone.** This is an honest, disclosed result, not the hoped-for
outcome: an earlier draft of this implementation DID eliminate it, as a
side effect of treating SOTI's bare `"Opportunity"` heading as
heading-shaped (`UNKNOWN`), which correctly ended the un-sectioned
preamble before this paragraph. That side effect was **reverted** as
part of fixing Regression 1 (§8.3) — the SAME shape (a single bare
title-cased word, no family root) that made `"Opportunity"` incorrectly
heading-shaped is indistinguishable, at the single-line level, from a
genuine one-item requirement-list value, and the regression this
milestone's own suite caught (swallowing `"Python"`/`"PostgreSQL"`/
`"Docker"` as phantom headings) is the far more severe, far more common
failure mode to guard against. This false positive remains exactly
what §1.4/§6.6 already characterized it as: Root-Cause-4/5-adjacent
(an alternative-list/learning-narrative fabrication), explicitly
reserved for M10D, not something a heading-recognition fix alone can
safely resolve.

### 8.5 Scope boundaries honored

Confirmed by direct `git status`/`git diff --stat`: no change to
`src/gitscore/concepts/`, `src/gitscore/matching/`,
`src/gitscore/assessment/`, `src/gitscore/evidence/`, any file under
`evaluation/gold/` or `evaluation/gold_v1_1/`, `evaluation/m9b/corpus.json`,
or `evaluation/m10b/section_state_controls.json`, or any frontend file.
M10D (alternative-list semantics) was not started.

The two `tests/test_m10b_section_state_safety.py` assertions amended
(§8.2) are the one deliberate exception to "never touch M10B's own
artifacts," and are handled as transparently as possible: an explicit,
named, commented override dict (`_M10C_RECLASSIFIED_OUTCOMES`) applied
to exactly two ids, for exactly the reason stated in the test file's
own amended module docstring (M10C's MANDATED recognition of
`"Compensation"` and the `"day in this role"` idiom — both explicitly
required examples / natural idiom variants of this milestone's own
scope — necessarily moves those two controls' outcomes between M10B's
own two ALREADY-accepted non-fabricating buckets). The underlying data
file, `evaluation/m10b/section_state_controls.json`, was not edited.
Both tests still assert, unconditionally, that neither control ever
produces `formal_requirement` — the one invariant that actually
mattered is preserved, not relaxed.

### 8.6 Remaining limitations and M10D scope

Unaffected, confirmed by the unchanged false-positive/malformed-group
counts above:
- Root Cause 4 (Manulife's `"at least one programming language (e.g.,
  ...)"` parenthetical-list alternative-detection gap).
- Root Cause 5 (SOTI's `"one or more of"` idiom-blind "or" splitting).
- SOTI's `"Opportunity"`-adjacent false positive (the C#/SQL
  alternative-group fabrication) — would require EITHER a Root-Cause-4/5
  fix (recognizing the learning-exposure sentence's own OR-list as
  non-technical/narrative, not a heading-recognition fix at all) OR a
  deliberate, separately-approved relaxation of the bare-title-case-
  needs-family-match rule (§8.3) that this milestone's own regression
  testing shows is NOT safe to relax without reintroducing a worse,
  more common failure mode.

Newly surfaced by this milestone, explicitly NOT resolved (per decision
7/question 6's scope boundary), candidates for a future, separately-
scoped sub-milestone:
- Whether `RESPONSIBILITY`-sourced content that happens to match an
  existing non-technical pattern (§8.4's `m10a-man-06`) should be
  exempted from that detector chain, or left as-is (a duty description
  doubling as an implicit soft-skill requirement is arguably reasonable,
  not obviously wrong — this milestone takes no position).
- The idiom-phrase-list question from §6.10 question 4 (`"Technical
  Skills"` and similar), resolved conservatively (not added) for this
  implementation but not foreclosed for the future.
- The `UnparsedClaim` section-confidence granularity question from
  §4.3, resolved as option (a) (no change) for this implementation.

### 8.7 Commit-readiness verdict

**Ready to commit, pending explicit user confirmation** (per this
project's standing git rule: never commit without being asked). All
checks pass: `python -m pytest` = 1096 passed, 0 failed; both
evaluation corpora (78-entry design set, 18-entry held-out set) show
zero `unsafe_mismatch` beyond the one accepted, documented tradeoff;
M9B byte-identical except the version string; frozen 8c:v1/8c:v1.1
zero diff; no frozen gold, concept registry, matcher, scoring formula,
or `evaluation/m10b`/`evaluation/m9b` data file touched; every
behavior change is measured, explained, and traced to either a mandated
requirement (the "Compensation"/responsibility-idiom recognition) or an
honestly-disclosed, non-fabricating side effect (`m10a-man-06`). Not
committed. Not pushed. M10D not started.

---

## 9. Pre-commit product-correctness investigation (two findings traced in full)

Requested before authorizing commit: an exact, stage-by-stage trace of
the two product-level findings §8.4 already disclosed. Nothing in this
section changes any implemented behavior — it is investigation only.

### 9.1 Finding 1 — SOTI's C#/SQL alternative-group false positive

**Exact trace**, sentence: *"The technologies you learn during an
internship at SOTI range from learning to develop middle tier services
using languages like C#, or deepening your knowledge of databases by
leveraging SQL and learning how to build high performance apps using
storage procedures."* (SOTI posting, paragraph 2, before any heading.)

| Stage | What happens | Why |
|---|---|---|
| 1. Heading structural detection | The posting's actual first line, `"Opportunity"`, is checked by `_classify_heading_line("Opportunity", "Opportunity")` → **returns `None`** (confirmed live). Word count 1, no colon/ALL-CAPS/Markdown (no strong signal), plain-titlecase-only (weak signal) with zero matched family root → the Regression-1 fix (§8.3) requires a strong signal OR a family-root match for a weak-signal line to count as heading-shaped at all; neither is present. | `"Opportunity"` is a single bare capitalized word with no `requir*`/`qualif*`/`preferr*`/learning-idiom/`respons*`/`about`/benefit-etc root — structurally identical, at the single-line level, to a bare one-item list value. |
| 2. Section-purpose classification | **Not reached.** Step 1 already returned "not a heading" — no family/purpose decision is made at all. | — |
| 3. M10B `UNKNOWN` transition | **Not reached, and no longer a separate step.** In the M10C-unified implementation, the old two-step "table match, else check for an unrecognized-heading reset" is replaced by ONE call to `_classify_heading_line()`. Since that call returns `None`, `current_kind` is left completely unchanged — it stays `None` (its value before this line, since this is the very first line of the document). | — |
| 4. Claim generation | `current_kind` is `None` → NOT in `(UNKNOWN, LEARNING)` → `necessity_hint = _SECTION_NECESSITY_HINT.get(None, Necessity.REQUIRED)` → **`Necessity.REQUIRED`** (the dict has no `None` key, so this is the pre-existing, separately-approved Milestone 6B "no section at all → default REQUIRED" policy, untouched by M10C). `in_recognized_section = False` (`None` is not in the REQUIRED/PREFERRED/RESPONSIBILITY tuple) → the sentence is gated by `_looks_like_requirement()`. It contains the literal phrase `"knowledge of"` (`"...deepening your knowledge of databases..."`), one of `_REQUIREMENT_SIGNAL`'s ~16 trigger words → **admitted as a `Claim`** with `necessity_hint=REQUIRED`. | A pre-existing (Milestone 6B), unrelated-to-M10C gate; `"knowledge of"` is an accidental, generic trigger match — M10A's own Root Cause 3 ("the outside-heading gate is accidental in both directions"). |
| 5. Necessity inference | `infer_necessity(text, REQUIRED)` — no local `required`/`must have`/`preferred`/`a plus` marker in the sentence → returns the hint unchanged → **`Necessity.REQUIRED`**. | Milestone 6B Part 7, unchanged. |
| 6. Requirement construction | `classify_alternative_claim()`: the sentence contains a standalone `"or"`; both resulting segments contain a real, resolvable concept mention (`"C#"` → `language.csharp`, `"SQL"` → `language.sql`) via `find_concept_mentions`'s prose-safe alias scan; `any_confirmed=True`, `len(ordered_ids)=2` → **`kind="technical"`, `concept_ids=(language.csharp, language.sql)`**. `_requirements_from_claim` builds ONE `JobRequirement` with `alternative_concept_ids=(language.csharp, language.sql)`, `necessity=REQUIRED`, `github_observability=STRONGLY_OBSERVABLE` (`observability_for_technical()`). | Milestone 6B.1's alternative-group classifier working exactly as designed on a sentence that happens to contain two real, OR-joined technology mentions — it has no way to know the sentence is narrative ("you'll learn...") rather than a claim ("you need..."). |
| 7. `UnparsedClaim` diagnostics | **Not reached** — a real `JobRequirement` was produced (1 row), so `_parse()`'s "zero requirements → `UnparsedClaim`" fallback never fires. | — |
| 8. Assessment denominator | `alternative_concept_ids` is populated with two REAL (non-`unresolved:`) concept ids and `github_observability=STRONGLY_OBSERVABLE` → `MatchStatus` is evaluated against evidence (`SUPPORTED`/`NOT_OBSERVED`), **never `NOT_ASSESSABLE`** → this row **DOES enter `_assessable_matches`/`alignment_score`'s denominator**. Confirmed via `src/gitscore/matching/engine.py`'s decision table and `src/gitscore/assessment/models.py::_assessable_matches`. | This is a real, scoring-relevant fabrication, not merely a cosmetic one. |

**Root cause, precisely stated**: this is **not a heading-classification
defect at all**. The paragraph has no heading of its own (it is
un-sectioned prose before any recognized section begins) and the
fabrication occurs entirely within the EXISTING, pre-M10C, Milestone-6B/
6B.1 pipeline: the outside-section heuristic gate (accidental admission
via `"knowledge of"`) feeding the alternative-group classifier
(correctly, faithfully converting a genuine OR-joined pair of real
concept mentions into a structured group). The missing distinction is
semantic: **narrative/exploratory phrasing** ("range from... to...",
"you may get an opportunity to...", "depending on the area you work
in, you may...") versus **an actual claim about what is required** —
nothing in the current parser, at any layer, represents this
distinction. It is exactly as M10A originally characterized it
(Root-Cause-4/5-adjacent) and exactly as M10B already confirmed:
*"SOTI is provably unaffected [by the M10B fix] — it never exhibited
[the sticky-section defect]"* — SOTI's false positive has never been a
section/heading problem.

**Was a conservative, in-scope fix attempted?** Yes — an earlier
implementation draft (before Regression 1 was found and fixed, §8.3)
DID eliminate this false positive, as a side effect of letting plain
title-case alone (no family-root corroboration) count as heading-shaped.
That same looseness is EXACTLY what caused Regression 1 (swallowing
`"Python"`/`"PostgreSQL"`/`"Docker"` as phantom headings in an
un-bulleted, one-item-per-line list) — caught by a pre-existing test.
**One narrower variant was considered and rejected**: letting a
weak-signal (plain-titlecase, no family root) line count as
heading-shaped ONLY when `current_kind` is still `None` (nothing
recognized yet) — this would fix `"Opportunity"` (processed while
`current_kind` is `None`) without affecting the `"Python"` regression
case (processed while `current_kind` is `REQUIRED`, not `None`, since
a real `"Requirements:"` heading precedes it there). Rejected for three
reasons: (1) it makes `_classify_heading_line()` **document-state-
aware** rather than a pure per-line function — a real architectural
change to the classifier's contract, not a parameter tweak, and exactly
the kind of change this milestone's own discipline (a dedicated control
corpus before any classification rule ships) says should get its own
STOP/corpus, not be slipped in reactively; (2) it has its OWN,
different, completely untested blast radius — a document that opens
with a bare one-word technology declaration and no heading at all (not
implausible, just not present in either the 78-entry or 18-entry
corpus) would newly lose that requirement's default-REQUIRED necessity,
demoting it to a diagnostic; (3) it is a company-agnostic BUT still
narrow, special-cased structural rule reacting to one specific document
shape (document-initial position), not a generalizable principle — the
same category of risk this investigation is specifically checking for.
**No company-specific exception and no blanket unsectioned-requirement
suppression were considered at all** — both were explicitly ruled out
by the brief and neither would be narrow enough to avoid new collateral
damage regardless.

**Conclusion: no safe, adequately-tested, in-scope correction exists
within M10C's heading-classification scope.** A correct fix requires a
genuinely different capability — recognizing narrative/exploratory
sentence structure as distinct from requirement-claim structure — which
is a sentence-level semantic classification problem, not a heading or
section-purpose classification problem, and is out of scope for both
M10C (headings) and M10D as currently scoped (alternative-list
semantics). **Recommended disposition: defer to a new, separately-scoped
future milestone** (tentatively "narrative vs. requirement claim
classification"), with its own independently-authored control corpus
covering exploratory phrasing ("you may," "depending on," "range from...
to...", "get exposure to") the same way this milestone built one for
headings.

**Classification: pre-existing, unchanged by M10C.** Confirmed
empirically: present before M10C (M10A's original finding), present
after M10C (§8.4's measurement), byte-identical in mechanism and
outcome in both cases — `"Opportunity"` was never heading-shaped under
either the pre-M10C exact-table design or the shipped M10C design.

### 9.2 Finding 2 — Manulife's "Collaborate..." responsibility bullet

**1. Original source text and section**: *"Collaborate with engineering
and business teams to build user-focused solutions"* — the fourth of
six bullets under Manulife's real `"Position Responsibilities:"`
heading (line 7–13 of the real posting).

**2. Classification before and after M10C**:
- **Before**: `"Position Responsibilities:"` is NOT in the old
  exact-phrase table (only `"responsibilities"`/`"key responsibilities"`
  were) → unrecognized → `current_kind` stays `None` (this is the
  posting's first heading) → the bullet is gated by `_looks_like_requirement()`
  → contains none of `_REQUIREMENT_SIGNAL`'s trigger words and no
  registered concept → **never admitted as a `Claim` at all** (confirmed
  live, zero trace — matches the M10A corpus's original, pre-M10C
  `notes` field for this entry).
- **After**: `"Position Responsibilities:"` matches the `RESPONSIBILITY`
  root (`\brespons\w*\b`) → `current_kind=RESPONSIBILITY` →
  `in_recognized_section=True` → the bullet is admitted as a `Claim`
  **unconditionally**, bypassing `_looks_like_requirement()` entirely.

**3. Requirement representation before and after M10C**: Before — none
(zero `JobRequirement`, zero `UnparsedClaim`). After —
`necessity_hint=_SECTION_NECESSITY_HINT[RESPONSIBILITY]=Necessity.REQUIRED`
(this mapping is Milestone-6B-era, unchanged by M10C); `infer_necessity`
finds no local override; `classify_alternative_claim` → `not_technical`
(no `"or"`); `find_concept_mentions`/`find_bare_short_alias_mentions` →
none; `find_conservative_unknown_terms` → `()` (no comma in the
sentence — the function's own first check); `find_experience_qualifier`
→ `None`; `find_non_technical_match` → **`"soft_skill"`**, because the
sentence contains `"Collaborate"`, matching `non_technical.py`'s
PRE-EXISTING `\bcollaborat\w*\b` pattern → ONE `JobRequirement`
produced.

**4. Necessity**: **REQUIRED** (confirmed: `row_necessity: ["required"]`
in the live run).

**5. Does it enter the alignment denominator?** **No.** Confirmed via
`src/gitscore/jobs/parsing/observability.py`: `NON_TECHNICAL_CATEGORY_OBSERVABILITY["soft_skill"]
= GithubObservability.NOT_OBSERVABLE`. Confirmed via
`src/gitscore/matching/engine.py`'s own decision table: `NOT_OBSERVABLE`
**always** resolves to `MatchStatus.NOT_ASSESSABLE`, "even in the
hypothetical of a technical concept mapping" (there isn't one here
anyway — `concept_id=None`). Confirmed via
`src/gitscore/assessment/models.py::_assessable_matches`, which
explicitly excludes `NOT_ASSESSABLE` from the set `assessable_count`
and `alignment_score` are both computed over. **`alignment_score` is
provably unaffected by this row, for any candidate, ever.**

**6. Could GitHub evidence actually assess it?** **No.** There is no
`concept_id` and no `alternative_concept_ids` — nothing structured to
look up in `CandidateEvidenceProfile` at all. "Ability to collaborate
with engineering and business teams" is not a GitHub-observable claim
under any evidence model this project has, which is exactly why
`soft_skill` is mapped to `NOT_OBSERVABLE` in the first place (alongside
`"experience"`, `"education"`, `"legal"`).

**7. New or pre-existing?** **Both, precisely**: the SPECIFIC ROW is
NEW (this exact bullet produced zero rows before M10C, confirmed
above). The MECHANISM is PRE-EXISTING, confirmed empirically —
`parse_job_description_with_diagnostics("Responsibilities:\n- Collaborate with engineering and business teams to build user-focused solutions.\n")`
(using the OLD, already-recognized, unchanged-by-M10C `"Responsibilities:"`
phrasing) produces the **identical** row (`category='soft_skill'`,
`necessity=REQUIRED`, `concept_id=None`, `github_observability=NOT_OBSERVABLE`)
— this would have happened for ANY posting using the old table's exact
phrasing, for as long as `non_technical.py`'s `soft_skill` pattern has
existed (Milestone 6B Part 10). M10C did not create this mechanism; it
newly EXPOSED it for the Manulife posting specifically, by correctly
recognizing a heading phrasing ("Position Responsibilities:") the old
table missed. Also confirmed: the SAME mechanism, independently, is
ALREADY firing elsewhere in this EXACT posting on a legitimate,
already-correct, unaffected-by-M10C row —
`"Strong communication skills and willingness to learn in a collaborative environment"`
(under `"Required Qualifications:"`) produces the identical
`category='soft_skill'` shape. `non_technical.py`'s pattern is, by
design, section-blind — it was never scoped to "only fire inside a
Qualifications section."

**8. Does it violate "a responsibility should not automatically become
a candidate requirement"?** **Yes, by the literal wording of that
guardrail — stated plainly, not minimized.** This sentence IS a
responsibility (the M10A corpus's own independent annotation:
`is_requirement: false`, `category_annotation: "responsibilities"`) and
it DID become a scored, necessity-bearing `JobRequirement`. The
project's OWN existing evaluation methodology agrees: re-running
`scripts/evaluate_m10a_realworld.py` flags this exact row
`false_positive_requirement: true` (confirmed, §8.4's own table — this
was not reinterpreted or argued away there either). **What the
violation is NOT**: it is not a fabricated TECHNICAL capability
(`concept_id=None`, never `STRONGLY_OBSERVABLE`), it never enters
`alignment_score`'s denominator (points 5–6 above), and the MECHANISM
that causes it (unconditional claim admission under `RESPONSIBILITY`,
feeding the SAME non-technical detector chain every other claim already
goes through) is not new — it is a latent, pre-existing design gap
(RESPONSIBILITY-sourced claims are not exempted from the non-technical
pattern chain, and never have been) that M10C's heading fix newly
exposed for this one posting.

**Is there a safe, smallest in-scope correction?** Three options were
considered, all rejected for this milestone:
- **(a) Exempt `RESPONSIBILITY`-sourced claims from the non-technical
  detector chain.** Requires `_requirements_from_claim` to know WHICH
  section kind produced a claim's necessity — but `RESPONSIBILITY` and
  `REQUIRED` both resolve to the identical `Necessity.REQUIRED` value
  before `_requirements_from_claim` ever sees the claim; distinguishing
  them would require `Claim` to carry its originating `_SectionKind`
  (or an equivalent new field) all the way through — a genuine
  **schema change**, exactly the kind of change the design gate says
  requires its own separate STOP, not something to add reactively here.
- **(b) Narrow `non_technical.py`'s `soft_skill` pattern** (e.g. remove
  the bare `collaborat*` root). Rejected: it would ALSO stop matching
  `"Strong communication skills and willingness to learn in a
  collaborative environment"` (point 7 above) — a different,
  legitimately-correct, already-scored row in the SAME posting —
  trading one disclosed finding for a new, different regression. Also
  out of scope per decision 7 (concept/pattern-table changes reserved
  for a separate sub-milestone).
- **(c) Revert "Position Responsibilities" recognition.** Rejected:
  this is the single highest-severity finding M10A/M10C exist to fix,
  and `"Position Responsibilities"`/`"Job Duties"` are explicitly
  mandated recognized examples — reverting it to avoid one soft-skill
  side effect would discard the milestone's primary deliverable, a
  wildly disproportionate response to a `NOT_ASSESSABLE`,
  denominator-inert row.

**Recommended disposition: no correction made within M10C; defer to the
same future sub-milestone §8.6 already proposed** ("should
`RESPONSIBILITY`-sourced content that matches an existing non-technical
pattern be exempted, or is a duty description that doubles as an
implicit soft-skill expectation a reasonable thing to surface?" — this
milestone takes no position, and should not decide it reactively under
investigation pressure).

**Classification: newly exposed instance of a pre-existing mechanism
gap — not a new mechanism, not fully pre-existing either (this specific
row did not exist before M10C), and not yet resolved.**

### 9.3 M10B override justification (regression integrity)

Confirmed by direct re-reading of `tests/test_m10b_section_state_safety.py`:
- `evaluation/m10b/section_state_controls.json` — **byte-for-byte
  unmodified** (not in `git status`'s changed-file list). Both
  controls' original `expected_outcome`, `description`, and `rationale`
  remain exactly as independently authored during M10B's own design
  review — nothing was erased or rewritten.
- The override (`_M10C_RECLASSIFIED_OUTCOMES`) is a **named, two-entry
  dict with an inline comment on each entry** stating the exact
  mechanical reason (heading now recognized) — not a silent
  monkey-patch, not a deletion of the parametrized assertion.
- The amended test file's module docstring **explicitly states** which
  two controls are affected, why, and that this reflects M10C's
  MANDATED scope (not a judgment call made to dodge a failing test).
- The **safety invariant that actually mattered** — neither control was
  ever supposed to produce `formal_requirement` — is asserted
  **unconditionally, for all 12 controls, including the two overridden
  ones** (`test_approved_section_state_control`'s final `if` block).
  This is STRICTER than simply swapping the expected string: a future
  change that caused either control to start fabricating a scored
  requirement would still fail this test, override or no override.
- Each override moves between M10B's own two ALREADY-accepted,
  ALREADY-non-fabricating outcome buckets (`diagnostic_preserved` ↔
  `correctly_excluded_non_requirement`) — never into `formal_requirement`.

**Conclusion: each override reflects an explicitly-approved semantic
change (mandated heading recognition), not a weakening of a safety
guarantee.** The guarantee is in fact asserted MORE strongly after the
amendment (explicit, unconditional, both controls) than it was by the
original parametrized check alone (which only ever compared against one
fixed string).

### 9.4 Revised commit-readiness verdict

Both findings traced to their root cause, both classified honestly, and
both deliberately left uncorrected within M10C's scope — for Finding 1
because no safe in-scope fix exists at all (a genuinely different,
future milestone is needed); for Finding 2 because every available
correction either requires a material schema change (needing its own
separate approval) or introduces a different, worse regression. Neither
finding affects `alignment_score` for any candidate on any posting
(Finding 1's fabricated alt-group DOES affect it — that part of the
false positive is real and scoring-relevant, but it is UNCHANGED by
M10C, not something this milestone's commit would introduce or worsen;
Finding 2 is provably `NOT_ASSESSABLE`, denominator-inert). The 1096-test
baseline is intact; no frozen gold, concept registry, matcher, or
scoring formula was touched; M10D was not started.

**Verdict: ready to commit, with both findings disclosed as known,
pre-existing-or-newly-exposed, non-blocking limitations rather than
silently fixed, rationalized away, or left undocumented.** Still not
committed, not pushed, pending explicit authorization.
