# Milestone 9F — Requirement Coverage & Score Validity: Design Review

**Status: design and evaluation only.** No file under `src/gitscore/`
or `frontend/` was modified. No matcher, scoring formula, concept
registry, parser semantics, or retrieval behavior was touched. No
frozen gold under `evaluation/gold/`, `evaluation/gold_v1_1/`, or
`evaluation/m9b/` was modified, re-annotated, or regenerated. No new
evaluation corpus file was created either — the new positive/negative
controls Phase 4 below proposes are presented as design-document
content, not as a committed corpus, so that authoring them does not
itself count as "modifying frozen gold" or "implementing" anything.
Not committed, not pushed.

---

## 1. Verified baseline (Phase 0)

| Check | Result |
|---|---|
| HEAD at start | `b04e363` ("feat: improve assessment clarity and evidence traceability" — M9E) |
| Working tree | clean |
| `python -m pytest` | **934 passed**, 0 failed (matches the expected baseline exactly) |
| `cd frontend && npx vitest run` | **36 passed** (matches the expected baseline exactly) |

Read before any analysis: `docs/evaluation/MILESTONE_9B_EVALUATION_INTEGRITY.md`,
`docs/evaluation/MILESTONE_9C_ASSESSMENT_TRANSPARENCY.md`,
`docs/evaluation/MILESTONE_9D_PRODUCT_VALIDATION.md`,
`docs/evaluation/MILESTONE_9E_ASSESSMENT_CLARITY.md`,
`jobs/parsing/{parser,segmentation,concepts,alternatives,experience,non_technical,dedup}.py`,
`jobs/{models,profile,types}.py`, `matching/{engine,models,support}.py`,
`matching/types.py`, `assessment/models.py`, `application/job_fit.py`,
`api/{schemas,serialization}.py`, the frontend result-rendering path
(`AlignmentHeadline.tsx`, `RequirementSection.tsx`,
`UnparsedClaimsSection.tsx`, `lib/labels.ts`), and
`evaluation/m9b/corpus.json` (all 30 entries, with particular attention
to the six silent-drop entries).

---

## 2. Exact failure taxonomy (Phase 1)

### 2.1 Method

All six of M9B's own measured silent-drop entries were re-run live
through `parse_job_description_with_diagnostics()` under current code
(unchanged since M9B) and traced through every internal gate
(`_unresolved_requirement_signal`, `_TECHNICAL_LEAD_IN`,
`clean_list_fragment`, `contains_enumeration_cue`,
`find_concept_mentions`, `find_conservative_unknown_terms`) directly —
not inferred from the M9B report's prose, re-verified against the real
functions this session, with exact intermediate values printed for each
claim. All six still produce **zero** `JobRequirement` rows and all six
still appear in `unparsed_claims` (confirmed — nothing has changed in
the parser since M9B/M9C/M9D/M9E, as expected, since none of those
milestones touched `jobs/parsing/`).

### 2.2 The five categories, mapped to real evidence

**1. Unregistered named technologies.** A single concrete product name
with no concept-registry entry. Two sub-shapes observed, each failing
for a DIFFERENT reason:

- **1a — shape-check word-limit failure.** `m9b-005` ("Familiarity
  with Snowflake is a plus"): the lead-in phrase "Familiarity with"
  DOES match `_TECHNICAL_LEAD_IN` (confirmed: `lead_in.end()` succeeds).
  The remainder, "Snowflake is a plus," is passed to
  `clean_list_fragment()`, which fails it on `len(stripped.split()) > 3`
  (four words: "Snowflake", "is", "a", "plus") — the SAME shape check
  that exists specifically to reject ordinary descriptive clauses.
  **Root cause: a correctly-interpreted technology name is lost purely
  because the sentence ALSO carries a short, common hedge clause
  ("is a plus") after it.**
- **1b — no recognized lead-in at all.** `m9b-006` ("The ideal candidate
  has used Snowflake extensively"): `_TECHNICAL_LEAD_IN.match()` returns
  `None` outright — the sentence does not start with any of the six
  recognized noun-phrase lead-ins ("experience with," "knowledge of,"
  "familiarity with," "proficiency in," "proficient in," "expert in").
  **Root cause: the claim is a free-form verb-phrase sentence structure
  the lead-in table was never designed to recognize at all** (it only
  matches a narrow, fixed set of sentence-INITIAL noun-phrase prefixes).

**2. Technical requirements with no registered concept, structured as
an AND-list.** `m9b-008` ("Hands-on experience with PLC programming and
SCADA systems"): fails on TWO independent gates simultaneously —
(a) `_TECHNICAL_LEAD_IN` is anchored at the string start (`^`) and does
not match, because the sentence begins with "Hands-on experience with,"
not a bare "Experience with"; (b) even disregarding (a),
`find_conservative_unknown_terms()`'s no-sibling-confirmed branch
requires BOTH an enumeration cue ("such as"/"including"/"like"/etc.)
AND an actual comma — this sentence has neither (a bare "X and Y," no
comma at all). **Root cause: a real, deliberate, previously-disclosed
design boundary — the comma requirement exists specifically to avoid
promoting ordinary verb-phrase "and" clauses (e.g. "build and maintain
pipelines") into fabricated unresolved concepts — but it also rejects
this genuine two-item technology enumeration that happens to use "and"
with no comma.**

**3. Technical competencies expressed via gerund/infinitive verbs with
no named product.** `m9b-014`/`015`/`016` ("Experience designing
distributed systems," "Experience building reliable distributed
services," "Ability to design and implement scalable backend
architectures"): all three fail `_TECHNICAL_LEAD_IN` for the same
structural reason as 1b — the regex only matches the SIX fixed
noun-phrase lead-ins, none of which match a verb-phrase construction
("experience designing X," "experience building X," "ability to
design and implement X"). **Root cause: this category is a
categorically DIFFERENT sentence shape from every other narrow signal
the parser already has** — there is no named technology anywhere in the
sentence to even attempt a shape check against; the "requirement" is a
competency described by a verb + an abstract technical noun, not a
proper noun.

**4. Genuine ambiguity.** None of the six silent-drop entries are
examples of this category — `m9b-005`'s and `m9b-008`'s
`ambiguity_notes` describe ambiguity in which GATING RULE should apply,
not ambiguity in what the sentence means. The corpus's own genuinely
ambiguous entries are elsewhere (`m9b-013` — "Python, Rust, or an
equally performant systems language," where the corpus itself records
that collapsing to the conservative placeholder is correct, not a loss;
`m9b-028`/`m9b-029`, vague technology-family references the gold
explicitly marks as uncertain rather than resolved by guessing a
specific vendor). **These are NOT part of the six-claim failure set this
milestone must solve — they are already correctly handled (conservative
placeholder, never resolved by guessing) and should stay that way.**

**5. Ordinary prose that should not be classified as a requirement at
all.** None of the six fall in this category either — all six are
independently annotated (`is_requirement: true`, `is_technical: true`)
as genuine, GitHub-observable-in-principle technical claims, not
prose. **Live-verified this milestone (new repro, not in any prior
report):** a genuinely non-technical sentence placed inside a
recognized "Requirements:" section heading (where every line becomes a
`Claim` unconditionally, per `segmentation.py`'s own documented policy)
also currently produces zero rows and lands in `unparsed_claims`:

```
Requirements:
- We value diverse perspectives and backgrounds on our team.
- Experience with Python

requirements produced: ["Experience with Python" -> language.python]
unparsed_claims: ["We value diverse perspectives and backgrounds on our team."]
```

This is the CORRECT outcome today — a sentence that is not a
requirement at all, misplaced under a requirements heading, is not
promoted into a fabricated technical claim. **This single fact is the
central risk any fix for categories 1–3 must not break** (see §4.2,
Option A).

### 2.3 Taxonomy summary table

| Category | Entries | Exact failing gate | Would a shape-only (proper-noun) fix help? |
|---|---|---|---|
| 1a. Named tech + trailing hedge clause | m9b-005 | `clean_list_fragment`'s ≤3-word limit | Yes — a longer-tolerant or hedge-clause-stripping variant of the shape check could resolve this narrowly |
| 1b. Named tech, no recognized lead-in | m9b-006 | `_TECHNICAL_LEAD_IN` anchor miss | No — this is a lead-in COVERAGE gap, not a shape-check gap; would need a broader (and inherently less narrow) lead-in detector |
| 2. AND-list, no comma, no cue | m9b-008 | `_TECHNICAL_LEAD_IN` anchor + comma requirement in `find_conservative_unknown_terms` | Partially — the lead-in anchor issue is fixable narrowly; the no-comma AND-list gap is a deliberate, disclosed trade-off (M9A) |
| 3. Verb-led competency, no named product | m9b-014/015/016 | `_TECHNICAL_LEAD_IN` does not cover verb-phrase shapes at all | **No** — there is no proper noun to shape-check; any fix here is inherently a vocabulary/meaning heuristic, not a shape heuristic |
| 4. Genuine ambiguity | (not in the six) | N/A — already correctly conservative | N/A |
| 5. Ordinary prose | (not in the six) | N/A — already correctly excluded | N/A — must stay this way |

**The single most important conclusion of Phase 1:** categories 1–2 are
narrow, bounded, shape-or-structure gaps a scoped fix could plausibly
close with low false-positive risk (they still involve a real proper
noun or an unambiguous enumeration). **Category 3 is fundamentally
different** — it has no proper noun to anchor a shape check to at all,
so any fix is necessarily a verb/noun VOCABULARY heuristic, the exact
kind of heuristic this project has previously and deliberately avoided
(`jobs/parsing/parser.py`'s own module docstring: `_TECHNICAL_LEAD_IN`
is "deliberately NOT the full... table... far too weak a signal to
single-handedly justify flagging an entire bare claim"). This is why
**no single regex safely solves every category** — confirmed directly
by this milestone's own tracing, not assumed from the brief.

---

## 3. Reproduced examples (Phase 1, continued)

All six traced live this session (not quoted from a prior report):

```
m9b-005 | 'Familiarity with Snowflake is a plus'
  or=False comma=False cue=False lead_in=True remainder='Snowflake is a plus'
  cleaned=None mentions=() unk_terms=() -> signal=False -> 0 rows -> unparsed_claim

m9b-006 | 'The ideal candidate has used Snowflake extensively'
  or=False comma=False cue=False lead_in=False
  -> signal=False -> 0 rows -> unparsed_claim

m9b-008 | 'Hands-on experience with PLC programming and SCADA systems'
  or=False comma=False cue=False lead_in=False
  -> signal=False -> 0 rows -> unparsed_claim

m9b-014 | 'Experience designing distributed systems'
  or=False comma=False cue=False lead_in=False
  -> signal=False -> 0 rows -> unparsed_claim

m9b-015 | 'Experience building reliable distributed services'
  or=False comma=False cue=False lead_in=False
  -> signal=False -> 0 rows -> unparsed_claim

m9b-016 | 'Ability to design and implement scalable backend architectures'
  or=False comma=False cue=False lead_in=False
  -> signal=False -> 0 rows -> unparsed_claim
```

End-to-end, through the current (post-M9E) API/frontend layer: each of
these six, wrapped in a real job posting, now (a) appears verbatim in
`unparsed_claims` (M9C), (b) is counted in
`assessment.unparsed_claim_count` (M9E), and (c) surfaces a headline
caveat ("N additional statements... could not be parsed as a
requirement at all") whenever that count is `> 0` — but the caveat
never names which claim, nor its necessity, nor whether it was the ONE
requirement most central to the role (see §5).

---

## 4. Design alternatives (Phase 2)

### Option A — Preserve every eligible segmented requirement as a structured, non-scoreable row

**Mechanism.** Remove `_requirements_from_claim`'s narrow
`_unresolved_requirement_signal` gate on the LAST-RESORT fallback —
instead of firing only for the three narrow structural shapes, fire
unconditionally for any claim that survives segmentation's existing
gate and still produced zero rows from every other detector. No new
field is needed on `JobRequirement` — it already supports exactly this
shape (`concept_id=None`, `category="unresolved_requirement"`,
`github_observability=PARTIALLY_OBSERVABLE`), the same shape M9A's
existing narrow placeholder already uses. `UnparsedClaim`/
`unparsed_claims` would become permanently empty (every claim that
used to land there now becomes a real row instead).

| Dimension | Assessment |
|---|---|
| What it gains | Every one of the six silent-drop categories (and the OpenCV case, and the `sre_platform_01` monitoring/on-call cases) becomes a real, visible, necessity/importance-attributed row instead of a bare diagnostic string |
| False positives | **Real risk, demonstrated live (§2.2 category 5):** a genuinely non-technical sentence misplaced under a "Requirements:" heading currently produces a low-stakes `unparsed_claim`; under Option A it would become a FORMAL `NOT_ASSESSABLE` requirement row, visually indistinguishable in the UI from a genuinely missed technical requirement like OpenCV. Segmentation's `_REQUIREMENT_SIGNAL` gate (used only OUTSIDE recognized sections) is itself fairly broad (`experience\|proficien\|knowledge of\|familiar\|degree\|years?\|required\|preferred\|plus\|responsib\|skills?\|certificat\|licensed?\|eligible\|authoriz\|mentor`), so even outside a recognized section, borderline HR/responsibility prose can already become a `Claim` — today that is a low-visibility diagnostic string; under Option A it becomes a formal requirement |
| Requirement preservation recall | Becomes 1.0 by construction — nothing is ever silently dropped again |
| Interpretation precision | **Unchanged or arguably worse** — recall goes to 100% at the cost of blending genuinely technical, previously-silent-dropped claims with any borderline prose that happens to survive segmentation's gate, all under the identical `interpretation_status="unparsed_placeholder"` label |
| Effect on scoring/denominators | **None on `alignment_score`/`assessable_count`** — the placeholder is always `NOT_ASSESSABLE`, which both are already defined to exclude. `not_assessable_count` and `uninterpreted_requirement_count` would increase; `unparsed_claim_count` would go to zero |
| Domain/schema implications | **None** — reuses the existing `JobRequirement`/`category="unresolved_requirement"` shape exactly. `JOB_REQUIREMENT_SCHEMA_VERSION` unaffected |
| API implications | **None required** — the existing `RequirementOut`/`AssessmentOut` shape already represents this case fully; `unparsed_claims` would simply always serialize as `[]` |
| UX implications | The `UnparsedClaimsSection`/caveat (M9C/M9E) would become permanently dead code (always empty) — would need removing or repurposing |
| Implementation complexity | **Low** — a one-line change to `_requirements_from_claim`'s final condition |
| Risk to existing valid behavior | **Highest of the three options.** This is a genuine PARSER SEMANTIC CHANGE: every posting currently producing an `unparsed_claim` for ANY reason (including ordinary prose that happens to pass the loose outer-gate) changes its `not_assessable` breakdown. It also removes M9C's entire category distinction (genuine parser uncertainty about a REAL technical claim vs. "nothing survived the detector chain at all") — collapsing two different severities of "I don't know" into one |

### Option B — Narrowly scoped technical-competency recognition, with strict controls

**Mechanism.** Add ONE new, narrow structural signal to
`_unresolved_requirement_signal` (or a sibling function) that
recognizes a FIXED, small, curated set of competency-indicating VERBS
("design," "build," "architect," "implement," "operate," "develop,"
"scale") immediately followed by a FIXED, small, curated set of
technical-sounding OBJECT nouns ("systems," "services," "pipelines,"
"architectures," "platforms," "infrastructure," "APIs"), anywhere in
the claim (not anchored to the sentence start, unlike
`_TECHNICAL_LEAD_IN`) — firing only the EXISTING non-fabricating
`unresolved_requirement` placeholder (`concept_id=None`), never a new
concept or category.

| Dimension | Assessment |
|---|---|
| What it gains | Closes category 3 specifically (m9b-014/015/016 and the structurally identical `sre_platform_01` "monitoring and observability tooling"/"incident response" cases) — the single category Phase 1 identified as having NO shape-only (proper-noun) solution available |
| False positives | **The central, unresolved risk of this option.** Unlike `looks_like_specific_technology_name()` (a SHAPE check — capitalization, no meaning required), a verb+noun vocabulary is inherently a MEANING heuristic — there is no capitalization signal to lean on for common nouns like "systems" or "relationships." The brief's own named contrast ("Experience building reliable distributed services" vs. "Experience building strong relationships with stakeholders") is exactly the case this option must get right, and no existing mechanism in this codebase currently distinguishes them — a genuinely new curated negative-control vocabulary ("relationships," "rapport," "consensus," "stakeholder buy-in," "team culture") would need to be authored and tested BEFORE any implementation (see §6) |
| Requirement preservation recall | Improves category 3 to ~1.0 (for phrasings matching the curated verb/noun set); categories 1/2 remain unaddressed unless separately, independently fixed (this option does not, by itself, fix m9b-005/006/008) |
| Interpretation precision | Depends entirely on the quality and narrowness of the curated vocabulary — this is NOT measurable in the abstract; it requires the controlled evaluation in §6 before any confidence claim can be made |
| Effect on scoring/denominators | **None on `alignment_score`/`assessable_count`** — same reasoning as Option A: the result is always the existing non-fabricating placeholder, always `NOT_ASSESSABLE`. `not_assessable_count`/`uninterpreted_requirement_count` increase slightly (only for claims matching the new, narrow signal); `unparsed_claim_count` decreases by the same amount |
| Domain/schema implications | **None** — same placeholder shape as Option A, scoped to fewer claims |
| API implications | **None required** |
| UX implications | `UnparsedClaimsSection ` remains non-empty for every OTHER silent-drop category (1, 2, and anything this vocabulary doesn't cover) — so, unlike Option A, the existing two-severity distinction (M9C) is preserved, just with fewer claims in the more-severe bucket |
| Implementation complexity | **Medium** — the detector itself is small, but a defensible, well-tested verb/noun vocabulary with negative controls is real design and evaluation work, not a one-line change |
| Risk to existing valid behavior | **Medium, bounded** — unlike Option A, this only affects claims matching a specific, narrow, newly-added pattern; every other claim's behavior (including the category-5 ordinary-prose case, §2.2) is provably unaffected by construction, since the new signal requires BOTH a matching verb AND a matching object noun, not a broad gate |

### Option C — Retain current parsing behavior; strengthen score-presentation safeguards

**Mechanism.** No parser change of any kind. Build on M9E's existing,
additive `unparsed_claim_count` (already computed, already surfaced as
a headline caveat) with STRONGER presentation treatment specifically
when the combination "a high-looking score" + "at least one unparsed
claim" + (optionally) "the unparsed claim was likely REQUIRED, inferred
from `necessity_hint`/section placement" co-occurs. Concretely, any of:
(i) a more visually prominent, qualified headline format (e.g. "100 —
based on 4 of 5 extracted requirements" rather than a bare "100" with a
caveat sentence below it); (ii) naming the SPECIFIC unparsed claim(s) in
the headline caveat itself (the text is already retained verbatim in
`unparsed_claims` — no new data needed); (iii) under precisely defined
circumstances (e.g. `unparsed_claim_count > 0` and every assessable
required requirement is `SUPPORTED`), replacing the bare numeric
headline with an explicitly qualified one, never a silent, unqualified
"100."

| Dimension | Assessment |
|---|---|
| What it gains | Directly addresses the PRODUCT-LEVEL risk (a misleadingly confident headline) without touching the measurement-level risk (the silent drop itself) — the two are genuinely separable problems, and this option addresses the one M9D/M9E already found has the highest "reader is misled" severity |
| False positives | **None possible** — no parsing decision changes at all; this is purely how an unchanged set of facts is DISPLAYED |
| Requirement preservation recall | **Unchanged — still 0.615 (M9B)** — this option does not close the measurement gap, only discloses it more effectively |
| Interpretation precision | Unchanged |
| Effect on scoring/denominators | **None whatsoever** — `alignment_score`, `assessable_count`, `required`, `preferred` are read, never computed differently |
| Domain/schema implications | **None.** `unparsed_claims`/`unparsed_claim_count` already exist (M9C/M9E) |
| API implications | **None required**, though a small additive field (e.g. a boolean the frontend could use instead of re-deriving "is this a high-looking-but-incomplete score" logic itself) would be a reasonable, still-additive enhancement — optional, not required |
| UX implications | The most significant changes are entirely here — headline visual weight, whether a number can ever render "bare" when coverage is incomplete |
| Implementation complexity | **Low** — mostly `AlignmentHeadline.tsx`/`lib/labels.ts` presentation logic, continuing the exact pattern M9E already established |
| Risk to existing valid behavior | **Lowest of the three options** — by construction, nothing about matching, scoring, or parsing can regress, because nothing in that layer changes |

### Hybrid recommendation preview

No single option alone is sufficient: Option C does not reduce the 23%
silent-drop rate at all; Option A reduces it to zero but at a real,
demonstrated precision cost; Option B reduces it partially, for exactly
the one category (verb-led competencies) that most needs it, but
requires real evaluation investment before it can be trusted. See §8.

---

## 5. High-alignment validity (Phase 3) — `karpathy × computer_vision_01`

### 5.1 What the 100 actually represents (live-reproduced, real fixture, not hypothetical)

Reproduced this milestone against the REAL `karpathy` evaluation
fixture (not a hand-built mock), via the actual, running FastAPI
process (`scripts/m9d_serve_offline_fixture.py karpathy`) over a real
HTTP request:

```
required:  {supported: 3, assessable: 3}   (language.python, ml.framework.pytorch, platform.cuda)
preferred: {supported: 1, assessable: 1}   (language.jupyter_notebook)
alignment_score: 100
uninterpreted_requirement_count: 0
unparsed_claim_count: 1
unparsed_claims: ["Experience with OpenCV for image processing"]
```

The `100` means: **of the 4 claims that survived parsing into a real,
assessable `JobRequirement` row, all 4 found sufficient GitHub
evidence.** It does NOT mean "100% of this posting's requirements are
met," and it does NOT mean "the posting has exactly 4 technical
requirements" — the posting's raw text names 5 distinct technologies/
competencies as requirements (Python, OpenCV, PyTorch, CUDA, Jupyter
Notebook); one of the five (OpenCV) never became an assessable row at
all.

### 5.2 Which requirement was excluded, and is it a defining one?

"Experience with OpenCV for image processing" — the posting's own
`required` bullet list. This is arguably the SINGLE MOST
role-DEFINING item in the entire posting: Python/PyTorch/CUDA are
generic to most ML/deep-learning roles, while OpenCV is the one
named technology that specifically signals *computer vision* work as
opposed to, say, NLP or generic ML engineering. Its exclusion is
maximally consequential precisely because it is the LEAST generic, MOST
differentiating requirement in the posting — not an incidental or
redundant one.

### 5.3 Do current caveats sufficiently disclose this? (verified, not assumed)

**Partially, after M9E — not before.** Before M9E, `uninterpreted_requirement_count`
was `0` for this exact posting (confirmed live, repeated here) — zero
placeholder rows exist because the claim never became a row of any
kind — so the pre-M9E headline rendered NO caveat at all. After M9E,
the headline now additionally renders: "1 additional statement in the
job posting could not be parsed as a requirement at all — see below."
This is a genuine, meaningful improvement, but it has three concrete
gaps a reader must independently close:

1. It does not say the unparsed statement was asked for OpenCV
   specifically — a reader must scroll to `UnparsedClaimsSection` to
   find that out.
2. It does not say the statement was phrased as REQUIRED, not
   PREFERRED — `UnparsedClaim` carries no necessity at all (by
   construction — necessity is computed by `infer_necessity()`, which
   `_requirements_from_claim` never reaches for a claim that produces
   zero rows). A reader cannot currently learn this fact from the API
   AT ALL, even by reading every field in the response.
3. It does not say the headline number would likely be LOWER had this
   claim been assessable — no explicit linkage between "there is a gap"
   and "that gap could plausibly affect the number you are looking at."

**Per this milestone's own constraint, a generic disclaimer is not
claimed to resolve this** — this is exactly M9E §5.3's own
documented, still-open conclusion, re-confirmed rather than re-litigated
here.

### 5.4 Should display distinguish complete-coverage from known-gap assessments?

**Yes — recommended as the primary Phase 5 direction** (§8, Option C
extended). A binary, always-computable signal already exists without
any new field: `unparsed_claim_count == 0` (complete extracted
coverage) vs. `> 0` (known parsing gap exists). Today this signal only
changes whether a caveat SENTENCE appears below the number; it does not
change the number's own visual treatment. Three explainable approaches
were evaluated (per the brief's own list), **none of which change the
numerical formula**:

| Approach | What it does | Risk |
|---|---|---|
| **Improved interpretation** (closing the gap via parsing) | Reduces `unparsed_claim_count` itself | This IS Options A/B above — a parsing-layer change, not a presentation one |
| **Explicit assessment incompleteness** (a visible badge/label distinct from the caveat sentence, e.g. "Partial coverage" vs. "Complete coverage" next to the headline) | Makes the binary signal impossible to miss, without touching the number | Low risk, purely presentational, recommended |
| **A qualified headline** (e.g. "100 — based on 4 of 5 extracted requirements") | Puts the incompleteness INSIDE the number's own visual unit, not a separate sentence a reader can skip | Low risk; slightly more complex copy; strongest disclosure |
| **Withholding a headline score** under precisely defined circumstances | Replaces the bare number with something like "Score withheld — pending a fully-parsed required requirement" | **Higher risk**: 23% of real-world postings carry at least one unparsed claim (M9B), so this could withhold a score on a very large fraction of real analyses, which risks reading as the product failing routinely rather than being honest about a known limitation. Also forecloses the required/preferred subscores, which remain valid and informative even when one claim is unparsed |
| **Another explainable approach**: naming the specific unparsed claim(s) directly in the headline caveat (no new field needed — `unparsed_claims[].text` already exists) | Turns "something is missing" into "OpenCV, specifically, is missing" | Low risk, highest specificity, recommended alongside the badge |

**Recommendation for this axis specifically:** combine "explicit
assessment incompleteness" (a visible badge) with "naming the specific
claim(s)" — both are presentation-only, zero scoring/schema/API risk,
and directly close gaps 1–3 in §5.3 without the downside of outright
withholding scores on a large fraction of analyses.

---

## 6. Independent evaluation strategy (Phase 4)

### 6.1 What can be measured from existing frozen/M9B gold, unchanged

| Metric | Source | Current value | Notes |
|---|---|---|---|
| Genuine requirement preservation recall | `evaluation/m9b/corpus.json` (30 entries) | **0.615** (16/26) | Unchanged since M9B; re-confirmed this milestone (parser untouched) |
| Correctly structured technical requirements | same | **0.500** (9/18) | |
| Unknown-concept preservation | same | **0.500** (5/10) | |
| Unknown OR/AND structural correctness | same | **0.833** (5/6) | |
| Correct unparsed-placeholder preservation | same | **0.643** (9/14) | |
| False-positive requirement creation (spurious rows) | same | **0** | Zero across 30 independently-authored entries including 4 adversarial cases |
| Unsupported concept fabrication | same | **0** | |
| Exact source-span correctness | same | **1.000** (16/16) | |
| Silent-drop count | same | **0 accepted / 6 flagged** | The six this milestone's Phase 1 classifies |
| Correctly excluded non-requirement prose | same | **1.000** (4/4) | |
| Unparsed-claim disclosure (M9C/9E) | `unparsed_claims`/`unparsed_claim_count` live-verified | 100% of the six silent-drops appear verbatim | Confirmed live this milestone, §3 |
| Impact on assessable denominators | `assessment/models.py`, live-verified | **Zero** for any `NOT_ASSESSABLE` placeholder (by construction — excluded from `assessable_count`) | Confirmed; this is why Options A/B above are scoring-neutral |
| Assessment consistency | `evaluate_m9b_preservation.py`/`evaluate_m9b_retrieval_sensitivity.py` | byte-identical across M9C/9D/9E re-runs | Re-confirmed each milestone; would need re-confirming again after any Option A/B implementation |

### 6.2 The gap this milestone found: no existing negative controls for a verb/noun competency vocabulary

M9B's 30-entry corpus has exactly **3** `technical_competency_no_named_product`
positive examples (m9b-014/015/016) and **zero** negative controls in
that specific family — no existing entry tests a verb-led, no-named-
product sentence that is semantically NOT a technical requirement
(e.g. a stakeholder-relationship or soft-skill claim phrased with the
same "action verb + abstract plural noun" shape). This is a genuine gap
for evaluating Option B specifically, not a flaw in M9B's own corpus
(which was never scoped to test this one option).

**Proposed additional controls (design content only — not committed to
any file this milestone, consistent with "do not modify frozen gold" and
"do not implement production code during the design review"):**

*Positive controls (should resolve, if Option B is ever implemented):*
1. "Experience designing distributed systems" (m9b-014, already in corpus)
2. "Experience building reliable distributed services" (m9b-015, already in corpus)
3. "Ability to design and implement scalable backend architectures" (m9b-016, already in corpus)
4. "Experience operating production infrastructure at scale"
5. "Track record of architecting event-driven pipelines"
6. "Experience developing high-throughput data platforms"

*Negative controls (MUST NOT resolve — the exact brief-named contrast and five more, spanning different "false friend" shapes):*
1. **"Experience building strong relationships with stakeholders"** (the brief's own named example — verb "building" + plural abstract noun "relationships," identical shape to positive control #2, semantically a soft skill)
2. "Experience designing onboarding programs for new hires" (HR/people-process, not technical)
3. "Track record of building high-performing teams" ("building" + "teams" — people management, not infrastructure)
4. "Experience developing talent across the organization" ("developing" + abstract noun, people development not software development)
5. "Ability to design inclusive, welcoming team rituals" (culture, not architecture)
6. "Experience architecting go-to-market strategies" ("architecting" — a verb this option's vocabulary might include — applied to a business, not technical, object)

**Required gate before implementation:** zero false positives on EVERY
negative control above (and any additional ones a future milestone's
own review adds) — mirroring the "zero spurious requirements, zero
fabricated technologies" bar M9A/9B already established and M9B's own
benchmark already confirmed holds today. A single false positive on
"building strong relationships with stakeholders" would be a direct,
demonstrated regression of that invariant and should block the option
entirely until the vocabulary is narrowed further.

### 6.3 Measuring score-validity presentation changes (Option C extensions)

Unlike Options A/B, Option C has no parsing correctness to measure —
its evaluation is a UX-comprehension question, which is exactly what
M9D's own (not-yet-run) human-pilot protocol was designed to answer.
**Recommendation: extend that existing, already-designed protocol**
(`docs/evaluation/M9D_HUMAN_PILOT_PROTOCOL.md`) with one additional task
once any Option C enhancement ships — "does a qualified headline /
coverage badge change whether a participant over-trusts a high score,"
directly extending Task 1's existing over-trust check rather than
designing a new study from scratch.

---

## 7. Score-validity analysis (Phase 3, consolidated)

- `alignment_score`'s DEFINITION is sound and internally consistent
  (percentage of ASSESSABLE requirements supported) — this milestone
  found no defect in the formula itself, and the brief explicitly
  forbids changing it.
- The defect is entirely in what reaches the "assessable" pool in the
  first place — a claim that never becomes a `JobRequirement` row
  cannot be assessable, cannot lower the denominator, and therefore
  cannot lower the score, no matter how central it is to the role. This
  is the precise mechanism by which a 100 can be the mathematically
  correct answer to "of what we assessed, how much was supported" while
  being a misleading answer to "does this candidate meet this posting."
- Because `NOT_ASSESSABLE` (the existing placeholder shape) is ALSO
  excluded from the denominator, closing the gap via Option A or B
  would NOT by itself change `alignment_score` for `karpathy ×
  computer_vision_01` or any of the six M9B cases — OpenCV would become
  a visible `NOT_ASSESSABLE` row, not a `NOT_OBSERVED` one (there is
  still no OpenCV concept in the registry, and this milestone's
  constraints forbid adding one). **The headline number itself would
  still read 100 even under Options A or B** — only the breakdown below
  it, and the caveat counts, would change. This is an important,
  previously-unstated finding: **closing the silent-drop gap alone does
  NOT fix the `karpathy` 100; only a presentation change (Option C) or
  a future concept-registry addition (explicitly out of scope) can
  actually move or qualify that specific number.**

---

## 8. Recommended architecture (Phase 5)

### 8.1 Recommendation: adopt Option C now; scope Option B as a separately-approved future milestone; reject Option A

**Why Option C is safer than the alternatives:** it is the only option
with zero measurable false-positive risk, zero effect on any tested
invariant, and zero new schema/API/matcher/scoring surface — every
other option's risk is a parsing-precision risk measured in a
false-positive RATE that cannot be bounded below "unknown" until built
and tested. Option C also directly addresses §7's finding that the
`karpathy` 100 cannot be fixed by closing the drop gap alone — making it
the ONLY option that can move the needle on this milestone's own
headline example at all.

**Why Option A is rejected, not merely deprioritized:** it trades a
measurable, bounded gap (23%, already disclosed three milestones running)
for an UNBOUNDED new one — any borderline prose that survives
segmentation's existing (intentionally loose, outside-section)
`_REQUIREMENT_SIGNAL` gate, or any mis-sectioned sentence inside a
recognized heading, becomes a formal, necessity-attributed requirement
row. This directly undermines the one invariant every milestone from
M9A onward has protected (zero spurious requirements) by relabeling
"spurious" as "a real but totally unresolved requirement" rather than
preventing it from looking like a requirement at all.

**Why Option B is deferred, not rejected:** it is the only option that
can close category 3 specifically, and category 3 is exactly the
`karpathy`/OpenCV case's sibling category in spirit (a real, concrete,
role-defining technical ask with no way to represent it structurally
today — though OpenCV itself is category 1, a named product, not
category 3). It requires real evaluation work (§6.2) this design-review
milestone is not scoped to perform, and the brief's own instruction is
explicit: a material parser change requires a STOP before
implementation.

### 8.2 Does the recommendation require a domain/schema change?

**No**, for either the Option C work recommended immediately or the
Option B work scoped for later. Both reuse existing shapes
(`JobRequirement.category="unresolved_requirement"`,
`UnparsedClaim`/`unparsed_claims`, `AssessmentOut.unparsed_claim_count`)
exactly as they exist today. `JOB_REQUIREMENT_SCHEMA_VERSION` would
remain unchanged under either.

### 8.3 Must matcher or scoring semantics change?

**No**, under either recommendation. `matching.engine.match_requirement()`
and `assessment.models`'s formula are untouched by both Option C
(pure presentation) and Option B (produces only the existing,
already-`NOT_ASSESSABLE`-by-construction placeholder). Confirmed in
§7: even a fully successful Option B implementation would not move
`alignment_score` for the `karpathy` example.

### 8.4 Must the frontend/API change?

**Option C:** yes, additively — new presentation logic in
`AlignmentHeadline.tsx`/`lib/labels.ts` (a coverage badge, naming the
specific unparsed claim(s) in the caveat). A small, optional, additive
API field (e.g. `assessment.has_coverage_gap: bool`, a plain
`unparsed_claim_count > 0 or uninterpreted_requirement_count > 0`
passthrough) would let the frontend avoid re-deriving this from two
numbers, but is NOT required — the frontend can already compute it from
existing fields. **This still does not require a STOP by this
project's own established precedent** — M9C and M9E both already added
materially similar additive fields/presentation logic without a
prior approval gate, because they are additive, backward-compatible,
and change no existing field's meaning. It should still be scoped and
reviewed as its own small implementation milestone, not implemented
inside this design review.

**Option B:** no API/frontend change beyond what Option C already
proposes — the new detector produces the SAME placeholder shape
`RequirementOut`/`interpretation_status="unparsed_placeholder"` already
represents fully today.

### 8.5 How would the recommendation address the OpenCV example specifically?

- **Immediately (Option C, next milestone):** the `karpathy ×
  computer_vision_01` headline would show a visible "partial coverage"
  indicator and the caveat would name "OpenCV" directly, rather than a
  generic "1 additional statement." The number itself would still read
  `100` (per §7) unless the "qualified headline" sub-option is also
  adopted, in which case it could read "100 — based on 4 of 5 extracted
  requirements."
- **Not addressed by Option B** — OpenCV is a named-product claim
  (category 1b in this milestone's taxonomy: no recognized lead-in),
  not a verb-led competency claim (category 3). Option B's scope, as
  evaluated here, does not cover it. Closing category 1b would require
  either broadening `_TECHNICAL_LEAD_IN`'s lead-in coverage (a separate,
  not-yet-evaluated sub-option with its own false-positive risk) or
  registering `OpenCV` as a concept (explicitly out of scope per this
  milestone's own constraints and M9C/9D/9E's prior constraints).

### 8.6 What remains unsolved

- The 23% silent-drop rate itself is **not reduced** by the immediate
  recommendation (Option C) — only disclosed more effectively. This is
  the fourth milestone in a row (M9B → M9C → M9D → M9E → **M9F**) to
  measure and discuss this gap without closing it. A decision to accept
  this permanently (treat Option C's disclosure as the product's final
  answer) or to commit to Option B's evaluation work is now overdue —
  see §9.
- Option B, even if fully approved and successfully implemented, would
  not close categories 1b/2 (unregistered named technologies with no
  recognized lead-in; comma-less AND-lists) — those would need their own,
  separately-scoped, separately-evaluated narrow fixes.
- No option here registers OpenCV or any other missing concept — that
  remains explicitly out of scope by this milestone's own constraints
  and every prior milestone's constraints.
- Whether real users actually notice/correctly interpret a coverage
  badge or a qualified headline is **unverified** — the M9D human pilot
  (never run) remains the correct instrument to answer this, and should
  be extended (§6.3), not bypassed.

---

## 9. Explicit approval questions

This design review surfaces three decisions that each require an
explicit answer before any further implementation work, per this
milestone's own "STOP and request approval" instruction:

1. **Approve Option C (presentation-only coverage disclosure) as the
   next implementation milestone's scope?** This requires no
   schema/matcher/scoring change; the only open question is whether to
   also add the small, optional `has_coverage_gap`-style additive API
   field, or keep the frontend deriving it from existing fields.
2. **Approve scoping Option B's evaluation work (§6.2's positive/
   negative control corpus) as a SEPARATE milestone, with an explicit
   zero-false-positive gate before any parser code is written?** This
   is a request to approve EVALUATION work, not implementation — the
   actual `_requirements_from_claim` change would still need its own,
   later STOP-point approval once the evaluation results are in.
3. **Is Option A (unconditional preservation) to be formally closed out
   as rejected**, so a future milestone does not re-propose it without
   addressing the category-5 false-positive risk this review
   demonstrated live (§4, §2.2)? Recommended: yes, document as
   rejected with cause, consistent with this project's practice of
   recording — not silently forgetting — considered-and-declined
   designs.

**No implementation of any kind should proceed until at least question
1 is answered**, since it is the only option this review found to be
both low-risk and capable of improving the `karpathy`/OpenCV case at
all.

---

## 10. Future implementation/testing plan

**If Option C is approved (recommended, immediate):**
1. Design the exact visual treatment (badge text/placement, qualified-
   headline copy) — likely a short design pass, not a full milestone.
2. Implement in `AlignmentHeadline.tsx`/`lib/labels.ts` only — no
   backend change required (or, optionally, the small additive
   `has_coverage_gap` field discussed in §8.4).
3. Add frontend component tests mirroring M9E's own pattern (exact
   rendered text/structure assertions), plus a regression test
   confirming `alignment_score` is byte-identical before/after.
4. Update `docs/ARCHITECTURE.md`/`docs/PIPELINE.md`/`docs/CHANGELOG_DEV.md`
   per this project's standing documentation requirement.
5. Extend the M9D human-pilot protocol with one additional task (§6.3)
   before or alongside running it for the first time.

**If Option B's evaluation work is approved (separate, later milestone):**
1. Author the full positive/negative control set (§6.2's six-plus-six
   starting point, expanded with any additional "false friend" shapes
   a dedicated review surfaces) as a new, clearly-labeled, additive
   evaluation corpus — never editing the existing M9B `corpus.json`.
2. Prototype the verb/noun detector in isolation (a pure function, not
   wired into `_requirements_from_claim` yet) and run it against every
   positive AND negative control.
3. Require zero false positives on every negative control as a hard
   gate; if any false positive occurs, narrow the vocabulary and
   re-test — do not relax the gate.
4. Only once the gate passes: present a scoped STOP-point proposal
   (mirroring M9A/9C's own precedent) to wire the detector into
   `_requirements_from_claim`'s last-resort fallback, with its own
   before/after measurement against the full M9B corpus (confirming
   zero regression in the existing 0/0 fabrication/spurious-row counts).
5. Re-run `evaluate_m9b_preservation.py` and diff every metric, not just
   the new one — confirm no existing passing entry regresses.

**Option A:** no implementation plan — recommended rejected (§9,
question 3).

---

## Final verification

```
python -m pytest           -> 934 passed, 0 failed (unchanged -- no production code touched)
git diff --check           -> (clean)
git status --short         -> docs/evaluation/MILESTONE_9F_REQUIREMENT_COVERAGE_DESIGN.md (new, untracked)
                               docs/CHANGELOG_DEV.md (modified -- this milestone's own entry)
git diff --stat            -> docs/CHANGELOG_DEV.md only; no file under src/ or frontend/ touched
```

**No production code, frozen gold, API contract, or frontend file was
modified.**

**DO NOT COMMIT. DO NOT PUSH.**
