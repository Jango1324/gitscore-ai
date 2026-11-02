# Milestone 10E — Narrative vs. Applicant Qualification Semantics

Evaluation-first architecture milestone. **No production code was
modified, no commit was made.** `src/gitscore` is untouched; every file
this milestone adds is new (`evaluation/m10e/`, `scripts/evaluate_m10e_narrative_controls.py`,
`scripts/evaluation_lib/narrative_classifiers.py`, this document). The
full suite still passes at the same 1157 the milestone brief names.

## 0. Baseline verification (Phase 0)

| Check | Result |
|---|---|
| M10D committed and pushed | Yes — `HEAD` (`e51713a`) == `origin/main`, `git status` clean at session start. |
| Current branch / tracking | `main`, tracking `origin/main`, up to date. |
| Working tree clean | Yes, before and after this milestone's additive-only files. |
| Parser version | `job_description_parser:v7` (`src/gitscore/jobs/parsing/parser.py:147`). |
| Backend baseline | **1157 passed**, confirmed via `pytest -q`. |
| M10A/M10C evaluations reproducible | Yes — `scripts/evaluate_m10a_realworld.py` and `scripts/evaluate_m10c_heading_classification.py` reproduce their committed reports exactly. |
| M10D evaluation reproducible | **No — found stale.** `scripts/evaluate_m10d_alternatives.py`'s re-run baseline column (`30/41 exact_match, 0 fabricated`) does not match the committed `evaluation/reports/m10d_alternatives_report.{json,md}` (`28/41, 5 fabricated`). The committed report documents **pre-fix** baseline numbers; it was not regenerated when `e51713a` ("fix: correct alternative requirement parsing...") landed. This is a pure documentation-staleness issue in M10D, not an ambiguous or broken working tree — the code itself is correct and the fix works (confirmed by the live re-run). Reverted the regenerated files (`git checkout --`) to keep the tree clean; **recommend a follow-up to regenerate and recommit `m10d_alternatives_report.{json,md}`** so the committed artifact matches `e51713a`'s own code. Not blocking for M10E.
| Frozen historical gold unchanged | Confirmed — `evaluation/gold/`, `evaluation/gold_v1_1/` untouched by anything in this session; `git status` showed no diff against them at any point. |

Since the only inconsistency found (M10D's stale report) is explained,
non-ambiguous, and does not call the parser's actual behavior into
question, this milestone proceeded rather than stopping.

## 1. Reproducing the real problems (Phase 1)

### 1.1 SOTI — exact trace

Source: `evaluation/m10/source/soti_raw.txt` lines 1–5 (verbatim, committed):

```
Opportunity

SOTI's growth and success is a result of commitment to innovation through
entrepreneurial culture and leadership. [...]

The technologies you learn during an internship at SOTI range from learning
to develop middle tier services using languages like C#, or deepening your
knowledge of databases by leveraging SQL and learning how to build high
performance apps using storage procedures. [...]
```

Confirmed, via direct call to the unmodified
`parse_job_description_with_diagnostics()`:

```
JobRequirement(necessity=REQUIRED, concept_id=None,
                alternative_concept_ids=('language.csharp', 'language.sql'),
                github_observability=STRONGLY_OBSERVABLE)
original_text = "The technologies you learn during an internship at SOTI
                  range from learning to develop middle tier services using
                  languages like C#, or deepening your knowledge of
                  databases by leveraging SQL and learning how to build
                  high performance apps using storage procedures."
```

**Exact mechanism, in order:**

1. **Heading recognition.** `"Opportunity"` is a single bare word with no
   colon/Markdown/ALL-CAPS and no family-root match
   (`_classify_heading_line`, `segmentation.py:304-367`) — it is NOT
   heading-shaped at all (confirmed, directly, by M10C's own documented
   regression guard — `segmentation.py:127-139`). `current_kind` stays
   `None`.
2. **Section-less default necessity.** With `current_kind is None`, every
   subsequent sentence's `necessity_hint` is computed as
   `_SECTION_NECESSITY_HINT.get(current_kind, Necessity.REQUIRED)`
   (`segmentation.py:488-492`) — **`None` is not a key in that dict, so
   `.get`'s own default argument, `Necessity.REQUIRED`, is returned.**
   This is the pre-existing, deliberate Milestone 6B "no section at all →
   default REQUIRED, heuristic-gated" policy (`segmentation.py:33-36`),
   now firing on content that PRECEDES the same document's own later,
   real sections (`"What you will learn:"`, `"Required skills:"`), not on
   a genuinely unsectioned posting.
3. **Admission.** `in_recognized_section` is `False` (`current_kind` is
   `None`, not one of `REQUIRED`/`PREFERRED`/`RESPONSIBILITY`), so
   admission is gated by `_looks_like_requirement` (`segmentation.py:439-442`).
   The sentence mentions "C#" and "SQL" — `find_concept_mentions` matches
   — so the gate passes and the sentence is admitted as a `Claim` with
   `necessity_hint=REQUIRED`.
4. **Alternative-group construction.** `classify_alternative_claim`
   (`alternatives.py:448-467`) finds no `_ANY_OF_TRIGGER` phrase, but
   finds a literal `" or "` (`contains_alternative_marker`), and splits
   the sentence on it: `_split_alternative_segments` produces two long,
   separate CLAUSES (not list items) — `"...using languages like C#"`
   and `"deepening your knowledge of databases by leveraging SQL and..."`
   (`alternatives.py:197-229`). `_resolve_segment` → `find_concept_mentions`
   (`concepts.py:198-`) scans the **entire clause**, not a bounded list
   token, and matches "C#" in the first and "SQL" in the second.
   `_classify_segment_list` (`alternatives.py:319-378`) sees two
   confirmed concepts and returns `kind="technical"`.
5. **Necessity inference.** `infer_necessity(text, hint=REQUIRED)`
   (`necessity.py:41-46`) finds neither a `REQUIRED_MARKER` nor a
   `PREFERRED_MARKER` literally in the sentence, so it returns the hint,
   `REQUIRED`, unchanged.
6. Result: `_requirements_from_claim`'s `alternative.kind == "technical"`
   branch (`parser.py:196-211`) builds exactly the fabricated
   `JobRequirement` shown above.

The grammatical "or" here links two broad TEACHING ACTIVITIES
("learning to develop... using C#" OR "deepening your knowledge... via
SQL"), never two interchangeable qualification options ("know C# or
know SQL") — a genuinely different `"or"` shape than every correctly-
handled case in M10D's own 41-control corpus, none of which involve a
multi-clause narrative sentence.

### 1.2 Manulife — exact trace

Source: `evaluation/m10/source/manulife_raw.txt` lines 7–12:

```
Position Responsibilities:
- Contribute to a team of engineers focused on building scalable, reliable applications
- Support application development, testing, and debugging efforts
- Assist in feature development and system enhancements
- Collaborate with engineering and business teams to build user-focused solutions
- Participate in code reviews and maintain code quality standards
- Support deployment, monitoring, and ongoing application maintenance
```

Confirmed, via direct call:

```
JobRequirement(necessity=REQUIRED, concept_id=None, category='soft_skill',
                github_observability=NOT_OBSERVABLE)
original_text = "Collaborate with engineering and business teams to build
                  user-focused solutions."
```

**Exact mechanism:**

1. `"Position Responsibilities:"` is colon-terminated (a strong shape
   signal) and matches `_RESPONSIBILITY_ROOT` only
   (`segmentation.py:211-215`) — classified `RESPONSIBILITY`, correctly.
2. `_SECTION_NECESSITY_HINT[RESPONSIBILITY] = Necessity.REQUIRED`
   (`segmentation.py:173-177`, an EXISTING, DELIBERATE mapping —
   "a responsibility bullet states what the role entails, treated as a
   requirement of the role by default"). `in_recognized_section=True`,
   so every bullet under this heading is admitted UNCONDITIONALLY (no
   heuristic gate at all), each with `necessity_hint=REQUIRED`.
3. `infer_necessity(text, REQUIRED)` finds no local marker, returns
   `REQUIRED` unchanged.
4. `classify_alternative_claim` → `not_technical` (no "or").
   `find_concept_mentions` → nothing (no technology named).
   `find_non_technical_match` (`non_technical.py:52-60`) tests the
   `_PATTERNS` table and matches `\bcollaborat\w*\b` under the
   `"soft_skill"` category (`non_technical.py:42-48`) — **a GENERIC,
   non-role-specific HR-boilerplate pattern, matched against this bullet
   with zero awareness that it came from a `RESPONSIBILITY` section.**
5. Result: a formal, scored `JobRequirement(necessity=REQUIRED,
   category='soft_skill')` for a plain duty description.

**Is the row scored?** `github_observability=NOT_OBSERVABLE` for
`category="soft_skill"` (`observability.py:36`) forces
`MatchStatus.NOT_ASSESSABLE` regardless of evidence
(`matching/engine.py:20`), and `NOT_ASSESSABLE` rows are excluded from
every scoring denominator (`assessment/models.py:73`). **So today this
specific row does not move any score.** The defect is nonetheless real
and in-scope: the row still exists as a formal `JobRequirement` with
`necessity=REQUIRED`, is counted in "required qualification" totals, and
would be rendered to a user/recruiter as if the employer had explicitly
demanded collaboration skills as a prerequisite — when the sentence is
simply describing the work. A future role-specific or recruiter-facing
mode (the project's own stated long-term direction) could easily surface
this count without re-deriving NOT_ASSESSABLE's own meaning each time.

### 1.3 A broader false-positive surface than the two named sentences (newly found, Phase 1 extension)

Tracing every Manulife responsibility bullet individually (not just the
one the brief names) found the defect is **not limited to
`non_technical.py` pattern matches**. `"Develop backend services using
Java."` and `"Maintain SQL databases."` — two bullets that merely NAME a
real technology while describing work, no soft-skill wording at all —
are ALSO promoted today to scored `REQUIRED` `JobRequirement` rows
(`concept_id='language.java'` / `'language.sql'`), via the completely
ordinary `find_concept_mentions` path every technical claim uses. The
SAME `_SECTION_NECESSITY_HINT[RESPONSIBILITY] = REQUIRED` default that
enables the Manulife soft-skill fabrication enables this too, with no
`non_technical.py` involvement at all. **This is the strongest evidence
against a narrow, pattern-based fix (Option A below): any responsibility
bullet naming a real technology — "Build dashboards in Python," "Write
SQL migrations," "Deploy services to AWS" — is fabricated as a scored
REQUIRED technical qualification today**, not just the two sentence
shapes (OR-group, soft-skill-pattern) the mission brief names.

### 1.4 A SKIP-section blanket-suppression gap (newly found, Phase 1/2 extension)

A third, independent gap, found while building the Phase 2 corpus
(`m10e-f4`): Manulife's own real heading `"When you join our team:"`
matches `_NON_QUALIFICATION_ROOT` (`segmentation.py:219-225`) and
classifies `SKIP`. `SKIP` content is suppressed UNCONDITIONALLY
(`segmentation.py:485-486`), with **no diagnostic fallback at all** —
unlike `UNKNOWN`/`LEARNING`, which still preserve a plain-text
`UnparsedClaim` via `necessity.py`'s `necessity=None` short-circuit.
Confirmed directly: wrapping the explicit, unambiguous sentence
`"Applicants must know Java."` under this real heading produces **zero**
`JobRequirement` rows and **zero** `UnparsedClaim` diagnostics — not even
a trace that anything was seen. This contradicts `necessity.py`'s own
documented "a local marker always wins" precedence (`necessity.py:3-10`)
— that precedence can only run on a claim that was ADMITTED in the first
place, and `SKIP` suppresses admission entirely, upstream of necessity
inference. This is squarely within this milestone's own mission
("Preserve genuine applicant qualifications, including those expressed
outside formal Requirements sections") even though it was not one of the
two sentences the brief named, and is reported here rather than silently
noticed and dropped.

### 1.5 The "no section" state is a dual-use mechanism — the real architectural tension

The single most important finding, confirmed by both the real-posting
traces above and the Phase 2 corpus (§2): `current_kind is None` is used
identically by the SAME line of code
(`segmentation.py:488-492`'s `.get(current_kind, Necessity.REQUIRED)`)
for two genuinely different real-world situations the parser cannot
currently distinguish:

- **"This whole posting has no headings at all"** — the ORIGINAL,
  still-valid Milestone 6B policy, and still correct today (confirmed:
  `m10e-i8`/`i9`/`i10`/`h2`, §2, §4 below — a genuinely unsectioned
  posting's content SHOULD still be heuristically admitted and defaulted
  to REQUIRED, exactly as today).
- **"No section recognized YET, but the document has real structure
  later"** — SOTI's actual shape, where the SAME default fabricates a
  requirement out of narrative prose.

**Any fix must preserve the first case and correct the second.** This is
the reason a narrow, pattern-only fix is architecturally insufficient on
its own (it cannot see section origin at all) and the reason a blunt "any
`current_kind is None` claim is ineligible" rule would be a REGRESSION
(it would break the genuinely-unsectioned-posting case). See §3/§5.

## 2. Independently annotated evaluation corpus (Phase 2)

`evaluation/m10e/narrative_controls.json` — **51 controls**, spanning
every category (A–I) the mission brief specifies, each independently
annotated with: source text, section context (a synthetic heading
wrapper, or `null`), `sentence_purpose` (QUALIFICATION / RESPONSIBILITY
/ LEARNING / COMPANY_CONTEXT / OTHER / AMBIGUOUS), whether it is a
candidate qualification, necessity if explicitly justified, whether it
should create a formal `JobRequirement`, whether it should produce a
diagnostic, whether its technical concepts may enter scoring, an
ambiguity rationale (for AMBIGUOUS entries), and — captured LIVE by
calling the real, unmodified parser, never hand-transcribed —
`current_baseline_outcome`.

**Annotation timing and provenance, stated honestly** (`annotation_provenance`
field in the corpus itself, mirroring this project's own existing norm
in `evaluation/m10/corpus.json`): this is **not** a blind,
pre-registered annotation independent of parser knowledge. The author
had already traced both real postings' fabrication mechanisms (§1)
before writing a single control, and several controls
(`m10e-a5`, `m10e-d6`, `m10e-e5`, `m10e-i11`) are direct restatements of
the real postings' own sentences. What IS true: every `sentence_purpose`
/ `should_create_job_requirement` / `should_produce_diagnostic` /
`technical_concepts_may_enter_scoring` judgment was decided from first
principles (what SHOULD happen, given the sentence's real-world meaning)
**before** `current_baseline_outcome` was captured by actually running
the parser — and several of the author's own initial assumptions about
CURRENT behavior were wrong, corrected only after that live run (the
`known_finding_*` entries in the corpus's own `schema_notes`: the
`"Required skills"` title-case heading-recognition gap, the SKIP
blanket-suppression gap, the RESPONSIBILITY-section concept-mention
surface, and the dual-use "no section" mechanism — all four were found
DURING corpus construction, not known in advance).

A known scope limitation of the corpus's own construction, surfaced
honestly rather than hidden (also recorded in the corpus's own
`schema_notes.known_finding_no_section_default_is_a_dual_use_mechanism`):
every control is wrapped as its OWN single-sentence synthetic document.
For a `heading=null` control, this means the document trivially has "no
heading anywhere" — it cannot, by itself, distinguish §1.5's two
`current_kind is None` situations (whole-document-unsectioned vs.
preamble-before-real-structure). §4's candidate comparison compensates
for this directly by also running every candidate against the REAL,
complete, multi-section SOTI and Manulife documents, where that
distinction is genuinely present.

| Category | Count | What it covers |
|---|---|---|
| A — Learning opportunities | 6 | `m10e-a1`…`a6`, incl. a direct SOTI-shape restatement |
| B — Genuine technical qualifications | 6 | incl. unsectioned-but-explicit (`m10e-b6`) |
| C — Genuine qualifications involving learning | 4 | applicant-side learning aptitude, never confused with Category A |
| D — Job duties | 7 | incl. Manulife's exact sentence (`m10e-d6`) and the new Java/SQL finding (`d3`/`d4`) |
| E — Company/product narrative | 6 | incl. SOTI's real opening sentence (`m10e-e5`) and a minimal SOTI-mechanism repro (`m10e-e6`) |
| F — Explicit qualifications outside Requirements | 4 | incl. the new SKIP-suppression finding (`m10e-f4`) |
| G — Responsibilities mixed with qualifications | 3 | confirms today's handling is already correct (regression guard) |
| H — Ambiguous statements | 4 | incl. the explicit acceptance of the existing unsectioned-AND-rows fallback (`m10e-h2`) |
| I — Formatting/structural hazards | 11 | Markdown, bullets, inline colon lists, Unicode NBSP, multi-line claims, compound/ALL-CAPS/bare headings, SKIP, bare one-item lines |

## 3. Comparing architectural strategies (Phase 3)

Three candidates, each a **prototype in `scripts/evaluation_lib/narrative_classifiers.py`**
— never wired into `src/gitscore` — reusing every existing detector
(`infer_necessity`, `classify_alternative_claim`, `find_concept_mentions`,
`find_non_technical_match`, `find_experience_qualifier`,
`find_conservative_unknown_terms`, `observability_for_*`) **completely
unchanged**. Each candidate only computes a (possibly narrowed)
necessity hint fed into that unchanged pipeline — mirroring M10D's own
discipline of prototyping only the decision the milestone is actually
about.

- **A — narrow contextual exclusion patterns.** A small, generic
  (never role-specific) regex table recognizing LEARNING-narrative
  (`"you will/you'll learn/gain"`, `"the technologies you learn"`,
  `"deepening your knowledge"`, …) and COMPANY-narrative (`"our
  product/platform/engineers... uses/builds/develops"`, `"we have
  used/built/leveraged"`, …) grammatical cues anywhere in a claim's own
  text. Fires regardless of section origin; suppresses JobRequirement
  construction only when the claim ALSO carries no local
  REQUIRED/PREFERRED marker.
- **B — section-origin-aware claim interpretation.** Exposes the REAL
  `_SectionKind` per claim via a parallel segmenter
  (`segment_with_section_kind`) that reuses every one of
  `segmentation.py`'s existing private primitives unmodified, plus a new
  whole-document fact, `document_has_any_recognized_heading`. A claim is
  qualification-eligible iff (a) its own text carries a local marker
  (unconditional, unchanged), OR (b) its section is a genuine `REQUIRED`/
  `PREFERRED` heading, OR (c) `current_kind is None` AND the WHOLE
  document has no recognized heading at all (§1.5's first case,
  preserved byte-for-byte). Every other origin (`RESPONSIBILITY`,
  `LEARNING`, `UNKNOWN`, or a `None` PREAMBLE before later real
  sections) is ineligible by default.
- **C — deterministic statement-purpose classifier.** B's eligibility
  gate, PLUS A's own grammatical-cue table as a second, independent veto
  — applied even inside an otherwise-eligible context (a real
  `REQUIRED`/`PREFERRED` section, or B's case-(c) fallback) — never
  overriding an explicit local marker.

A hybrid of A+B is explicitly what C is; no fourth, separate "hybrid"
candidate was needed.

**Rejected outright, per the mission's own restriction:** a large
keyword blacklist (A is deliberately narrow — 2 regex patterns, generic,
no company names) and any company-specific exception (none of A/B/C
reference SOTI, Manulife, or any employer by name).

### 3.1 Does `Claim` need a separate internal field for source-section purpose?

**Yes, for a real implementation** (not prototyped here, since this
milestone must not touch `src/gitscore`). Today `Claim.necessity_hint`
is the ONLY section-derived signal `parser.py` receives, and it already
collapses `RESPONSIBILITY` into the same `Necessity.REQUIRED` value a
genuine `REQUIRED` section produces (`_SECTION_NECESSITY_HINT`,
§1.5) — exactly the information loss this milestone's own root cause
depends on. Candidate B/C's prototype works around this by duplicating
segmentation's orchestration loop (`segment_with_section_kind`,
`narrative_classifiers.py:94-128`) to attach the REAL `_SectionKind` per
claim; a real implementation should instead add this once, as an
additive field on `Claim` itself (e.g. `section_kind: _SectionKind |
None`), so `necessity.py`/`parser.py` can gate on it directly without a
second, parallel segmenter ever existing in production. This is an
**internal, private, additive** change to a dataclass that is not part
of any public schema (`Claim` never leaves `jobs/parsing`) — consistent
with M10B's own precedent of widening `necessity_hint`'s type
(`Necessity | None`) without that being treated as a "material" schema
change requiring special sign-off beyond ordinary milestone review.

## 4. Evaluation against real postings (Phase 4)

Script: `scripts/evaluate_m10e_narrative_controls.py` (additive,
reproducible — reruns live against the unmodified production parser
plus the three prototypes). Full output:
`evaluation/reports/m10e_narrative_report.json`.

### 4.1 Exact SOTI / Manulife traces

| | baseline | candidate_a | candidate_b | candidate_c |
|---|---|---|---|---|
| SOTI total requirements | 2 (1 fabricated) | **1 (fixed)** | **1 (fixed)** | **1 (fixed)** |
| Manulife total requirements | 6 (1 fabricated) | 6 (**not fixed**) | **5 (fixed)** | **5 (fixed)** |

**Candidate A fixes SOTI but NOT Manulife** — "Collaborate with
engineering and business teams to build user-focused solutions" matches
no learning/company-narrative grammatical cue at all (it is plain duty
prose), so a text-pattern-only candidate cannot see that the problem is
WHERE the sentence came from (a `RESPONSIBILITY` section), not what it
says. **Candidates B and C both correctly fix both real postings**, and
critically — confirmed directly against the FULL real documents, not
isolated fragments — **remove exactly the 2 known-bad rows and nothing
else**: every other requirement in both real postings (the genuine
"Required skills" alt-group, Manulife's genuine education/experience/
language/soft-skill/preferred rows) survives unchanged under B and C.

### 4.2 M10E's own 51-control corpus (`has_job_requirement` accuracy against the gold annotation)

| Candidate | Matches gold `should_create_job_requirement` |
|---|---|
| baseline | 30/51 |
| candidate_a | 36/51 |
| candidate_b | 35/51 |
| **candidate_c** | **41/51** |

Candidate C's 10 remaining mismatches are, **every single one**, a
PRE-EXISTING, OUT-OF-SCOPE gap this milestone was never meant to fix —
confirmed by inspection, not asserted: `m10e-b3`/`b4`/`c1`-`c4`/`f2`/`h3`/`h4`
are generic non-technical phrasing (`"knowledge of database
fundamentals,"` `"willingness to learn,"` `"strong technical
background"`) that `non_technical.py`'s own category table has never
recognized, under ANY section, baseline included — a vocabulary-coverage
gap, not a narrative-misclassification one, and expanding
`non_technical.py`'s categories is explicitly out of this milestone's
scope. `m10e-f4` is §1.4's newly-found SKIP-blanket-suppression gap — a
real, separate architectural question (does SKIP need its own
diagnostic-preserving fallback, mirroring UNKNOWN's?) that candidates
A/B/C were never designed to touch (they only narrow WHICH already-
admitted claims become scored requirements; none of them can admit a
claim SKIP has already suppressed before necessity inference ever runs).

Candidate B's lower score here (35/51, missing category A/E) is an
artifact of this corpus's own single-sentence isolation (§2's disclosed
limitation), confirmed by §4.1: run against SOTI's REAL, complete,
multi-section document, candidate B correctly removes the SOTI
fabrication — because THERE, `document_has_any_recognized_heading`
genuinely returns `True` (the document has `"What you will learn:"`/
`"Required skills:"` later), correctly triggering case (c)'s exclusion.
In an isolated single-sentence test, that same control trivially has no
other heading either way, so case (c) ALWAYS applies and B reproduces
baseline. **This is not a flaw in B's logic — it is a real, principled
difference in what the two kinds of "no section" content actually need**,
and it is exactly why Candidate C's additional grammatical-cue veto
(§4.1, which does NOT depend on document-wide structure) is the more
ROBUST choice when document structure is absent or genuinely ambiguous,
as a totally unsectioned real posting's company narrative legitimately
could be.

### 4.3 Regression corpora — zero fabrication by construction, measured for false negatives

**Formal property, not just an empirical observation:** every candidate
here only ever narrows a necessity hint fed into `infer_necessity`,
which checks local markers BEFORE consulting the hint
(`necessity.py:41-46`). So for any claim: if a local marker is present,
baseline and every candidate compute the IDENTICAL necessity (the hint
never mattered); if no marker is present, a candidate's necessity is
either identical to baseline's, or `None` (suppressed). **No candidate
can ever introduce a necessity value, a concept id, or a category that
baseline did not already produce for the identical claim** — every
candidate's requirement set is a SUBSET of baseline's, per claim, by
construction. This means the only thing left to measure against a
frozen/regression corpus is false NEGATIVES (wrongly suppressed genuine
qualifications), never new fabrications.

| Corpus | n items | baseline total | candidate_a removed | candidate_b removed | candidate_c removed |
|---|---|---|---|---|---|
| M10A real-world (full postings, real headings) | 2 | 8 | 1 (SOTI only) | **2 (both known-bad rows, exact)** | **2 (both known-bad rows, exact)** |
| M10D alternative controls (41, isolated fragments) | 41 | 41 | **0** | **0** | **0** |
| M9B preservation corpus (30, isolated fragments) | 30 | 23 | **0** | **0** | **0** |
| 8c:v1 gold (93 claim fragments) | 93 | 81 | **0** | **0** | **0** |
| 8c:v1.1 gold (93 claim fragments) | 93 | 81 | **0** | **0** | **0** |

**Zero regressions on every frozen corpus named in the mission brief,
for all three candidates.** M10C's own 78-entry heading-classification
corpus needed no separate requirement-count check: none of A/B/C touch
`_classify_heading_line` at all (heading recognition is reused 100%
unchanged), so M10C's own result set is unaffected by construction, not
merely by measurement.

M10D/M9B/8c:v1/8c:v1.1 show **zero removals, not just few** — these
corpora are isolated claim fragments with no literal heading text, so
every one hits case (c) uniformly (§2's disclosed limitation, same
mechanism), and (for A/C) none of their genuine fragments happen to
contain a learning/company-narrative grammatical cue. This is a real,
confirmed, EXACT zero — not an artifact of a small sample size masking a
rarer problem — but it also means these specific corpora cannot be
cited as proof B/C's section-origin logic is regression-safe in a
MULTI-SECTION document; §4.1's full real-posting traces are what
actually establishes that.

### 4.4 Phase 4 report items, by number

1. **False-positive qualifications removed:** 2, both confirmed real
   (SOTI's C#/SQL alt-group, Manulife's "Collaborate..." soft-skill row)
   — candidates B/C only; candidate A removes 1 of 2 (misses Manulife).
2. **Genuine qualifications preserved or lost:** Preserved — every
   genuine qualification in both real postings, M10D, M9B, and
   8c:v1/8c:v1.1 survives unchanged under B/C (§4.3). None lost by any
   candidate on any frozen corpus.
3. **Responsibility statements incorrectly treated as prerequisites:**
   1 confirmed in the real Manulife posting (fixed by B/C); 2 more
   confirmed in this milestone's own synthetic corpus (`m10e-d3`/`d4`,
   §1.3) of the SAME mechanism, also fixed by B/C.
4. **Learning/company narratives incorrectly scored:** 1 confirmed in
   the real SOTI posting (fixed by all three candidates); 4 more in the
   synthetic corpus (`m10e-a1`/`a3`/`a6`, `m10e-e1`/`e6`), fixed by A and
   C, NOT by B alone (§4.2's disclosed single-sentence-isolation
   limitation).
5. **Previously invisible genuine qualifications:** None surfaced by any
   candidate — none of A/B/C ever GRANTS eligibility beyond what
   baseline already had (the subset property, §4.3); this milestone
   finds no new qualifications, only removes false ones.
6. **Diagnostics added or removed:** None of A/B/C change
   `UnparsedClaim` counts directly in this prototype (the prototype
   short-circuits to `[]`, same as `UNKNOWN`/`LEARNING` already do —
   a real implementation wired into `parser.py::_parse` would
   automatically route these into `UnparsedClaim` via the EXISTING
   "zero requirements → UnparsedClaim" fallback, with no new diagnostic
   type needed, mirroring M10B's own precedent exactly).
7. **Required/preferred requirement counts:** SOTI: 2 → 1 REQUIRED rows
   (B/C). Manulife: 4 REQUIRED + 2 PREFERRED → 3 REQUIRED + 2 PREFERRED
   (B/C) — the "Collaborate..." REQUIRED row removed; every other
   REQUIRED/PREFERRED row and its necessity value is unchanged.
8. **Score denominator changes:** **None, for Manulife's own fixed row**
   — `category="soft_skill"` was already `NOT_ASSESSABLE` (§1.2),
   already excluded from every denominator before this fix. For SOTI,
   the fabricated row WAS `STRONGLY_OBSERVABLE` with structured concept
   ids (`alternative_concept_ids`), so removing it DOES remove one
   assessable, denominator-participating row — see item 9.
9. **Alignment-score changes where measurable:** The SOTI fabrication is
   the only row of the two real-posting fixes that could have moved a
   score (it was assessable; Manulife's was already excluded). Removing
   it can only ever REDUCE a candidate's measured alignment against this
   one posting (one fewer thing to be `SUPPORTED`/`NOT_OBSERVED` on) —
   consistent with "Do not equate a lower score with greater accuracy"
   (item 10): the score becomes more TRUTHFUL (no longer rewarding or
   penalizing a candidate for a technology the employer never actually
   required), not more or less favorable by design.
10. **False-positive / false-negative tradeoff:** Candidates B/C trade 2
    confirmed false positives (real postings) + 5 more (synthetic
    corpus) removed, against **zero** newly-introduced false negatives
    on any frozen corpus (§4.3) — the only false negatives in play
    (`m10e-b3`/`b4`/`c1`-`c4`/`f2`/`f4`/`h3`/`h4`) are PRE-EXISTING,
    unaffected by any candidate (§4.2). Candidate A trades fewer false
    positives removed (1 of 2 real-posting defects; 5 of 11 synthetic)
    for the SAME zero-new-false-negative profile — it is strictly
    dominated by C, never safer.

## 5. Architectural decision

### 5.1 Recommendation: Candidate C (B's section-origin gate + A's grammatical-cue veto)

Justification, directly from §4's measurements:

- Only C fixes **both** real postings AND the full synthetic corpus's
  learning/company-narrative cases (A misses Manulife-shaped duty/
  concept-mention fabrications entirely; B alone, measured in isolation,
  misses learning/company-narrative cases that have no section-origin
  signal to anchor on — though B's OWN logic is proven correct against
  the real, multi-section postings, §4.2).
- Zero regressions on every frozen corpus named in the mission brief,
  for all three — so the choice is decided entirely by which candidate
  fixes the MOST confirmed defects, not by regression risk.
- C's two layers are independently justified and independently testable
  (B's section-origin gate alone already proven correct against real
  postings; A's text-pattern veto alone already proven correct against
  synthetic learning/company cases) — not a single, harder-to-reason-
  about combined heuristic.
- C never overrides an explicit local REQUIRED/PREFERRED marker (both
  layers share this one, unconditional override, checked first) —
  genuine qualifications in categories B/F/G (explicit markers, even
  outside Requirements sections, even mixed with duty language) are
  preserved 100% under C, confirmed directly (§4.2, zero category B/F/G
  regressions beyond the pre-existing vocabulary gaps already present in
  baseline).

### 5.2 Smallest defensible implementation (NOT implemented this milestone — proposed only)

1. Add `section_kind: str | None` (or the real `_SectionKind` enum
   member, boxed) as an additive field on `Claim`
   (`segmentation.py`) — populated from the SAME `current_kind` variable
   `segment_description`'s loop already tracks, no new logic. (§3.1)
2. Add `document_has_any_recognized_heading: bool`, computed once per
   `segment_description()` call (a single extra pass reusing
   `_classify_heading_line` unchanged — or, more cheaply, tracked as a
   side-effect flag during the existing loop since every call to
   `_classify_heading_line` that returns non-`None` already happens
   there).
3. In `jobs/parsing/parser.py::_requirements_from_claim`, BEFORE calling
   `infer_necessity`, compute a candidate-adjusted hint using exactly
   `candidate_c_hint`'s logic (`narrative_classifiers.py:220-233`,
   already written and tested against all 5 corpora in §4) — a single,
   small, pure function, no detector changes.
4. Add the two new, generic, non-role-specific regex constants
   (`_LEARNING_NARRATIVE_CUE`, `_COMPANY_NARRATIVE_CUE`,
   `narrative_classifiers.py:170-187`) to `segmentation.py` or a new
   small module (`jobs/parsing/narrative.py`), mirroring
   `non_technical.py`'s own existing "small, curated, generic table"
   precedent (`non_technical.py:1-10`).
5. No change to `JobRequirement`, `JobRequirementProfile`,
   `UnparsedClaim`, the matcher, or the scoring formula — a suppressed
   claim already has an existing, correct destination
   (`_requirements_from_claim` returning `[]` → `_parse`'s existing
   "zero requirements → `UnparsedClaim`" fallback, §4.4 item 6).
6. Bump `JOB_DESCRIPTION_PARSER_VERSION` `v7` → `v8`.

### 5.3 Section-origin provenance requirements

`Claim.section_kind` must be populated from the EXACT SAME `current_kind`
the existing necessity-hint computation already uses (never a second,
independently-derived classification) — this is the entire reason
`segment_with_section_kind`'s prototype duplicates ONLY the orchestration
loop and reuses every classification primitive unchanged (§3.1); a real
implementation collapses this duplication back into
`segment_description` itself, which is strictly simpler than today
(one field added to one existing loop) rather than more complex.

### 5.4 Handling of ambiguous and mixed-purpose statements

Confirmed directly (§4.2, category G: zero regressions; category H:
`m10e-h2` explicitly preserved): local markers win unconditionally in
every candidate, so a mixed sentence ("You will develop Python services;
experience with Python is required.") is unaffected regardless of
section origin or narrative phrasing elsewhere in the same sentence. A
genuinely ambiguous, unsectioned, structureless sentence with NO local
marker and NO section to anchor on (`m10e-h2`) is left exactly as today
— Candidate C's eligibility case (c) preserves it deliberately, per §1.5.

### 5.5 Expected scoring and denominator effects

Per §4.4 items 7–9: necessity/requirement COUNTS change (2 fewer rows
across both real postings); denominator membership changes for exactly
ONE of those two (SOTI's, since Manulife's was already
`NOT_ASSESSABLE`); no matcher/scoring FORMULA changes. A future
candidate's measured alignment score against a posting containing
SOTI-shaped or Manulife-shaped content can only go down or stay the same
under this fix, never up — this is the TRUTHFUL direction (§4.4 item 9),
not a scoring regression.

### 5.6 Parser version

`job_description_parser:v7` → `v8`, consistent with every prior
milestone in this series.

### 5.7 Regression risks

- The two-regex table (`_LEARNING_NARRATIVE_CUE`/`_COMPANY_NARRATIVE_CUE`)
  is the one piece of this design not anchored to section structure —
  it is a plain text-pattern match and, like any such pattern, could in
  principle false-positive on a genuine qualification sentence that
  happens to share phrasing (e.g., a hypothetical "Experience with
  technologies our engineers use daily, such as Python, is required" —
  contrived, not found in any real posting or corpus this milestone
  examined, but worth a reviewer's attention). Mitigated, not eliminated,
  by the unconditional local-marker override both layers share.
- `document_has_any_recognized_heading` is a WHOLE-DOCUMENT fact — a
  posting that mixes one genuinely unsectioned fragment with other, real
  sections (not observed in either real posting, but conceivable) is
  classified by this same rule either way; §4.1/§4.3 confirm this is
  correct for BOTH real postings examined, but a third real posting with
  a more unusual structure was not available to test.
- `non_technical.py`'s vocabulary-coverage gaps (§4.2, 10 remaining
  corpus mismatches) and the SKIP blanket-suppression gap (§1.4) are
  EXPLICITLY NOT fixed by this design — they are separate, honestly
  reported limitations, not silently left for a future reader to
  rediscover.

### 5.8 Verbatim architectural approval questions

1. **Approve implementing Candidate C** (§5.2) as the actual production
   fix, bumping `JOB_DESCRIPTION_PARSER_VERSION` `v7` → `v8`?
2. **Approve adding `section_kind` as a new, additive, internal-only
   field on `Claim`** (`jobs/parsing/segmentation.py`, never exposed
   outside the `jobs.parsing` package, never touching
   `JobRequirementProfile`/`JobRequirement`'s own public schema)?
3. Should the two new narrative-cue regexes live inside
   `segmentation.py` (next to the existing heading-family regexes) or in
   a new, small `jobs/parsing/narrative.py` module (mirroring
   `non_technical.py`'s own separation)? No measured difference in
   behavior either way — purely a code-organization call.
4. **Should the SKIP blanket-suppression gap (§1.4) be fixed in the SAME
   milestone, or deferred as a separately-scoped follow-up?** It is a
   different mechanism (admission-time suppression, not a necessity/
   purpose-classification question) from everything else this milestone
   addresses, and fixing it (giving SKIP an UNKNOWN-like diagnostic
   fallback) is a small but logically separate change with its own
   regression surface (every currently-silent SKIP section, e.g.
   Benefits/Perks/About Us, would start needing the SAME
   `_looks_like_requirement` gate UNKNOWN already uses, which this
   milestone has not evaluated against).
5. **Should the 10 pre-existing `non_technical.py` vocabulary-coverage
   gaps this milestone's own corpus surfaced** (`m10e-b3`/`b4`/`c1`-`c4`/
   `f2`/`h3`/`h4` — generic non-technical qualification phrasing like
   "knowledge of database fundamentals," "willingness to learn new
   technologies," "strong technical background") **be tracked as a
   separate follow-up ticket?** This milestone's own candidates cannot
   and do not attempt to fix them (§4.4 item 5's subset property makes
   this impossible by construction) — they require expanding
   `non_technical.py`'s own category table, explicitly out of THIS
   milestone's scope, but worth not losing track of given how directly
   this milestone's own mission (preserving genuine qualifications)
   touches them.
6. **Should M10D's stale evaluation report** (`evaluation/reports/m10d_alternatives_report.{json,md}`,
   §0) **be regenerated and recommitted** as a small, separate,
   immediate follow-up (not blocking this milestone)?

## 6. Known remaining limitations

- `candidate_a`/`candidate_b`/`candidate_c` are prototypes; none are
  wired into `src/gitscore`. §5.2's implementation plan is proposed,
  not shipped.
- The M10E corpus's own single-sentence isolation (§2, §4.2) cannot
  exercise Candidate B's "preamble vs. fully-unsectioned" distinction in
  isolation — only the real SOTI/Manulife full-document traces (§4.1)
  do. A future corpus revision could add explicit two-section synthetic
  documents (a narrative preamble sentence followed by a real
  Requirements section) to close this gap without relying solely on the
  two real postings.
- The SKIP blanket-suppression gap (§1.4) and the `non_technical.py`
  vocabulary-coverage gaps (§4.2) are real, confirmed, honestly reported
  — and explicitly NOT fixed by anything in §5.2's recommended design.
- No third real-world posting beyond SOTI/Manulife was examined — §5.7's
  `document_has_any_recognized_heading` risk is confirmed safe for
  exactly these two documents, not a larger sample.

---

**STOP — architecture decision only. No production code was modified. No
commit was made. Awaiting approval on §5.8's six questions before any
implementation milestone begins.**

## Implementation addendum (post-approval)

### §5.8 question mapping — confirmed, no material discrepancy

| # | §5.8 question | Approval decision |
|---|---|---|
| 1 | Approve implementing Candidate C? | Approved. |
| 2 | Approve additive `Claim.section_kind`, internal-only? | Approved. |
| 3 | Where should the narrative-cue regexes live? | A dedicated, independently-testable module (`jobs/parsing/narrative.py`) — answered explicitly. |
| 4 | Fix the SKIP blanket-suppression gap now, or defer? | Defer to a separately-scoped follow-up. |
| 5 | Track the `non_technical.py` vocabulary gaps separately? | Defer/track separately. |
| 6 | Regenerate M10D's stale report? | **Reversed from this doc's own recommendation** — preserve it as a historical snapshot instead, clarified in documentation. Confirmed, on inspection, consistent with M10D's OWN already-documented intent (its "Implementation addendum" explicitly calls that report "the true pre-implementation snapshot," left unregenerated by design) — not a new policy, a correction of this doc's own Phase 0 mischaracterization. |

No material discrepancy found between the six questions above and the
production-approval message's six architectural decisions; implementation
proceeded.

### Mandatory safety gate outcomes

**Gate A (genuine preamble qualifications) — PASS, after one fix found
during verification.** All four named cases (explicit qualification
before an About/Benefits section, a truly unsectioned posting, the real
SOTI document) preserve their explicit qualifications; SOTI's narrative
alone is suppressed. **Finding:** the first attempt at this gate's own
test (`"Applicants must know Python."` before an About section) FAILED
— `_REQUIRED_MARKER` (`necessity.py`, reused unchanged from before this
milestone) recognizes `"must have"`/`"must be"` but not `"must know"` —
a real, narrow gap this milestone's own eligibility gate exposed (the
pre-existing fallback never needed a marker to cover this case; the new
PREAMBLE-ineligibility rule does). Fixed by adding `\bmust know\b` to
`_REQUIRED_MARKER` — confirmed via `grep` across every existing
corpus/fixture that no other sentence used that exact phrase, so this
is a pure addition with zero risk of changing any PREVIOUSLY-correct
case's necessity.

**Gate B (mixed responsibility/qualification statements) — PASS, after
an explicit scope decision (see below).** All five named cases behave
exactly as specified: plain RESPONSIBILITY tech mentions and
soft-skill-pattern duties are no longer automatic; an explicit local
marker — even mixed into the same duty sentence, even as a PREFERRED
marker contradicting a LEARNING clause in the same sentence — always
wins; a genuinely required soft skill under `Required Qualifications:`
is unaffected.

**A genuine, material discrepancy WAS found (not avoided) during Gate
B's verification against the full test suite**, exactly per this
milestone's own "STOP if exact semantics cannot be represented safely"
instruction: suppressing plain RESPONSIBILITY tech mentions (Gate B's
own literal wording) broke four pre-existing, Milestone 6B "manual
validation" tests that have validated the OPPOSITE since before M10A.
Raised explicitly; the user resolved it by approving the broader,
uniform suppression and updating those four tests with documented
rationale — see `docs/CHANGELOG_DEV.md`'s Milestone 10E entry for the
exact tests and reasoning. This was NOT something this document's own
Phase 4 evaluation (§4) could have caught: none of the six corpora
tested there include `BACKEND_JD`/`ROBOTICS_JD`/`ML_JD`/`DATA_ENGINEERING_JD` — a real,
disclosed gap in this document's OWN evaluation coverage, not
discovered until implementation's full-suite regression run.

### Final verification results

| Check | Result |
|---|---|
| Full backend suite | 1157 pre-existing − 1 removed (stale `v7` version pin, superseded) + 63 new = **1219 collected, 1209 passed, 10 skipped** |
| M10E's own 51-control corpus, run against the REAL production parser | **41/51** exact match on `should_create_job_requirement` (identical to the Candidate C prototype's own §4.2 measurement — confirmed the production wiring reproduces the prototype exactly); the 10 mismatches are the SAME 10 pre-existing, out-of-scope gaps §4.2 already named, now explicitly `pytest.mark.skip`-documented rather than silently passing |
| SOTI/Manulife exact traces | Both fixed exactly, nothing else changed — confirmed via dedicated regression tests AND `evaluate_m10a_realworld.py` |
| M10A real-world benchmark | SOTI `false_positive_requirements` 1→0, `meets_ideal_outcome` 6/12→7/12, `meets_neither` `[m10a-soti-01]`→`[]`; Manulife `false_positive_requirements` 1→0, `meets_ideal_outcome` 40/43→41/43, `meets_neither` `[m10a-man-06]`→`[]` |
| M10C heading classification report | byte-identical (confirmed: this milestone never touches `_classify_heading_line`) |
| M10D 41-control corpus + its own pytest suite | byte-identical (isolated claim fragments, no section headings — this milestone's mechanism structurally cannot reach them) |
| M9B preservation report | byte-identical except the `parser_version_under_test` string |
| Frozen `8c:v1`/`8c:v1.1` | **zero diff**, confirmed via `scripts/check_evaluation_staleness.py` run on a clean pre-M10E tree (via `git stash`) AND the post-implementation tree, for a true before/after rather than a single point-in-time read |
| Genuine requirements lost on any frozen corpus | **None** — every removed row across all corpora is one of the two confirmed real defects or their direct synthetic analogues; zero unexplained removals |
| Score/denominator effect | SOTI: one fewer `STRONGLY_OBSERVABLE`, denominator-participating row (the fabricated alt-group). Manulife: **none** (the fabricated row was already `NOT_ASSESSABLE`, already excluded) |

### Disposition of the 10 remaining M10E corpus mismatches

Every one is a documented, pre-existing, out-of-scope gap this
milestone's candidates cannot fix by construction (§4.4 item 5's subset
property) — explicitly `pytest.mark.skip`-ed in
`tests/test_m10e_narrative_requirement_semantics.py`, not silently
passing:

| Control(s) | Category | Gap | Disposition |
|---|---|---|---|
| `m10e-b3`, `m10e-b4` | B | `non_technical.py` has no category for generic qualification phrasing ("knowledge of database fundamentals," "familiarity with cloud services") | Deferred — needs expanding `non_technical.py`'s category table |
| `m10e-c1`–`c4` | C | Same gap, applied to applicant-side learning-aptitude phrasing ("willingness to learn," "ability to learn") | Deferred — same follow-up as above |
| `m10e-f2` | F | Same gap, unsectioned ("experience with data structures") | Deferred — same follow-up |
| `m10e-f4` | F | **SKIP blanket-suppression gap** — a real heading ("When you join our team:") swallows an explicit qualification with zero trace | Deferred — separately-scoped follow-up (different mechanism, own regression surface) |
| `m10e-h3`, `m10e-h4` | H | Same `non_technical.py` gap, vague boilerplate ("strong technical background") | Deferred — same follow-up as b3/b4 |

### Outstanding, explicitly undone

- **The SKIP blanket-suppression gap** — not attempted, per §5.8 Q4's
  approval to defer.
- **`non_technical.py` vocabulary-coverage expansion** — not attempted,
  per §5.8 Q5's approval to defer.
- **A third real posting beyond SOTI/Manulife** — not examined; §5.7's
  risk disclosure stands as originally written.
- **No schema/matcher/scoring change** — confirmed, not merely
  asserted (`git status` throughout implementation showed only
  `jobs/parsing/{segmentation,necessity,narrative,parser}.py` and the
  four disclosed test revisions touched in `src`/`tests`).
- This milestone does not claim to resolve every narrative-vs-
  qualification ambiguity a job posting can contain.
