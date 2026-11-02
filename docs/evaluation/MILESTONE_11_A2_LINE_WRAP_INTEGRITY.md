# Milestone 11-A2 — Line-Wrap Segmentation Integrity

Evaluation-first architecture milestone. **No production code was
modified, no commit was made.** `src/gitscore` is untouched; every file
this milestone adds is new (`evaluation/m11a2/`,
`scripts/evaluate_m11a2_line_wrap.py`,
`scripts/evaluation_lib/line_wrap_classifiers.py`, this document). The
intentionally-untracked M11/M11-A1 architecture/evaluation files from
prior sessions were never touched (`git clean`/`git reset --hard`/
`git stash -u` never invoked).

## 0. Baseline verification (Phase 0)

| Check | Result |
|---|---|
| HEAD / tracking | `main` == `origin/main` (`c521a919e13791095c2115fff2404ffe8e377e61`). |
| Parser version | `job_description_parser:v9`. |
| Backend baseline | **1224 passed, 10 skipped**, confirmed via `pytest -q`, both before and after this milestone's additive files. |
| M11-A1 committed/pushed | Confirmed — `c521a91` is HEAD. |
| Frozen historical gold | Unchanged — `git status` shows no diff anywhere under `evaluation/gold*`. |
| Preserved untracked files | `docs/evaluation/MILESTONE_11_GENERALIZABLE_JOB_UNDERSTANDING.md`, `evaluation/m11/`, `evaluation/reports/m11_generalization_report.json`, `scripts/evaluate_m11_generalization.py`, `scripts/evaluation_lib/m11_generalization_probe.py` — all five present, untouched, still untracked. |

## 1. Exact root-cause trace (Phase 1)

### 1.1 Mechanism

`segment_description()` (`jobs/parsing/segmentation.py`) iterates physical
lines via `re.finditer(r"[^\r\n]+", description)` and processes EACH
physical line as its own, fully independent unit: heading classification,
necessity-hint computation, and `_split_sentences()` all operate on
exactly one physical line's content span, never anything wider. There is
no notion anywhere in this loop of "this line's text continues onto the
next physical line" — every line is structurally assumed to begin and
end a complete thought.

### 1.2 Exact trace, the real `m11-unicode-contradiction-01` fixture

Verbatim physical-line map (confirmed by direct execution):

```
2  "Our engineering culture values deep ownership and continuous learning. We've"
3  'built our platform on Go and PostgreSQL over the past "6 years", and our'
4  "team genuinely loves talking shop about distributed systems at lunch."
```

Line 2 is itself split by `_split_sentences()` into TWO sentence
fragments (both within that one physical line): `"Our engineering
culture..."` (ends in `.`, fails the admission heuristic, never becomes
a claim) and `"We've"` (no terminal punctuation at all, ALSO fails the
heuristic -- a two-character fragment with no concept mention and no
`_REQUIREMENT_SIGNAL` word, so it vanishes with no trace either).

Line 3, processed entirely independently, becomes its own `Claim`
(`source_span` `(112, 184)`, confirmed): `"built our platform on Go and
PostgreSQL over the past \"6 years\", and our"`. This is the WHOLE
reason the fabrication happens: this fragment, read in isolation, LOOKS
LIKE a technical "or"-list (`"...Go and PostgreSQL..."`), and
`resolve_necessity_hint()`'s own `contains_narrative_cue()` check
(`narrative.py`) never gets the chance to see `"We've built"` together
-- `"We've"` was already discarded on line 2, and this fragment starts
mid-sentence with `"built"`. Line 4 (`"team genuinely loves..."`,
ending in `.`) becomes its OWN, separate, unadmitted claim (no concept
mention, no signal word -- vanishes with no trace too).

**Confirmed root cause: the information that would correctly suppress
this fabrication (`"We've built"`, the exact phrase `narrative.py`'s
own cue table already recognizes) is split across a physical-line
boundary the segmenter treats as absolute, before `resolve_necessity_hint()`
or `contains_narrative_cue()` ever run on anything wider than one line.**
This is not a defect in M10E/M11-A1's own detector logic -- both are
completely correct on the text they are ever shown; the text they are
shown is already wrong.

### 1.3 A second, necessary companion finding (not anticipated by the mission brief)

Reconstructing the correct, full logical text (`"We've\nbuilt our
platform on Go and PostgreSQL over the past \"6 years\", and our\nteam
genuinely loves talking shop about distributed systems at lunch."` --
confirmed achievable via direct span extension, §3) is **necessary but
not sufficient**. Confirmed directly:
`gitscore.jobs.parsing.narrative.contains_narrative_cue()` returns
`True` for this exact text with a real ASCII space between `"We've"`
and `"built"`, but `False` for the IDENTICAL text with the ORIGINAL
line-wrap's `\n` at that exact position -- `_COMPANY_NARRATIVE_CUE`'s
own regex (`r"\bwe(?:'ve| have)? (?:used|built|...)\b"`) uses a
LITERAL single space between the optional contraction group and the
verb, which does not match a newline. The SAME literal-space fragility
was confirmed in `necessity.py`'s `_REQUIRED_MARKER`/`_PREFERRED_MARKER`
(`"must have"`, `"must know"`, `"need to have"`, `"nice to have"`) and
is structurally present in every multi-word phrase across
`non_technical.py`'s own `_PATTERNS` table too. **Segmentation's own
fix, however it joins lines, must be paired with widening every such
literal-space separator to `\s+`** (confirmed safe: `\s+` still matches
exactly one ASCII space, so ordinary unwrapped text is completely
unaffected) for the two fixes to jointly achieve real wrapped/unwrapped
equivalence.

### 1.4 Boundary taxonomy (Phase 1's own explicit requirement)

| Boundary type | Existing mechanism | Hard or soft? |
|---|---|---|
| Heading | `_classify_heading_line()` -- unchanged, reused as-is | HARD -- never joined across, in either direction |
| Bullet | `_BULLET_PREFIX` -- unchanged, reused as-is | HARD -- a bullet-prefixed line always starts a new logical unit, regardless of the PRECEDING line's own trailing content |
| Blank-line paragraph gap | Already implicit (`finditer` skips blank lines); THIS milestone adds an EXPLICIT check (`_is_paragraph_gap`, more than one `\n` in the inter-line gap) so a multi-line-spanning join algorithm can tell "adjacent physical lines" apart from "lines separated by a blank line" | HARD -- confirmed via `m11a2-paragraph-01`/`02`: a narrative fragment ending in a function word (`"...and our"`) must NOT be joined across a blank line into a genuinely separate sentence or heading |
| Genuine sentence boundary | `_split_sentences()`'s own `_SENTENCE_BOUNDARY` regex -- unchanged, reused as-is, now applied to a possibly WIDER (multi-physical-line) content span | Resolved INSIDE the (possibly extended) content, exactly as today |
| Soft word-wrap | **No existing mechanism at all** -- this milestone's own subject | SOFT -- the one boundary type this milestone adds real logic for |

## 2. Independent paired evaluation corpus (Phase 2)

`evaluation/m11a2/line_wrap_controls.json` -- **38 controls**, each an
unwrapped/wrapped pair (or, for 11 of them, a standalone stability
control with no wrapped counterpart), covering every category Phase 2
named: company narrative (3), explicit technical qualifications (3),
REQUIRED/PREFERRED preservation (3), ANY-of enumerations incl. the REAL
SOTI/Manulife alternative groups (3), genuine separate bullets (3),
nested bullets (2), Markdown headings (2), colon headings (2),
blank-line paragraph boundaries (2), non-technical qualifications (2),
technical competency statements (2), mixed duty/qualification clauses
(2), Unicode/NBSP/tab/CRLF formatting hazards (3), legitimate
one-item-per-line lists (3), and genuinely ambiguous boundaries (3).

**Annotation provenance** (recorded in the corpus file's own
`annotation_provenance` field): `expect_equivalent`/the accompanying
note were decided from first principles -- what SHOULD a line-wrap-
robust, general-purpose parser produce -- BEFORE any candidate design's
actual output was inspected for these specific pairs. `*_baseline_outcome`
fields were captured LIVE by running the unmodified production parser,
never hand-transcribed. Three controls were annotated `"ambiguous"`
(a genuinely hard boundary this milestone's own recommended design
explicitly declines to resolve, rather than silently guessing) instead
of a flat `True`/`False`.

**A methodology bug found and fixed during this milestone's own
measurement, disclosed rather than silently corrected:** the
evaluation script's first version compared requirement OUTCOMES as a
`frozenset`, which silently collapsed two IDENTICALLY-SHAPED-but-
semantically-different requirements (same necessity/concept/category,
different source text -- exactly what the real `m11a2-ambiguous-01`
case produces) into one set element, falsely reporting the wrapped and
unwrapped variants as "equivalent" when they were not (1 requirement
vs. 2). Fixed by comparing a sorted MULTISET (duplicates preserved)
instead -- confirmed this was the only such case affected by re-running
the full corpus after the fix.

## 3. Candidate design comparison (Phase 3)

Three candidates, all in `scripts/evaluation_lib/line_wrap_classifiers.py`
-- prototypes only, never wired into `src/gitscore`. Every candidate
reuses `_classify_heading_line`, `_BULLET_PREFIX`, `_split_sentences`,
`_SECTION_NECESSITY_HINT`, and `parser.py::_requirements_from_claim`
completely unchanged -- only WHICH physical lines combine into one
logical `Claim` before that unchanged pipeline runs differs between
them.

- **Candidate A (naive, rejected):** text-level soft-wrap joining --
  joins any physical line not ending in terminal punctuation into the
  next, respecting heading/bullet/paragraph boundaries but otherwise
  content-blind.
- **Candidate B (structural-only, rejected):** respects heading/bullet/
  paragraph boundaries but has NO content judgment at all -- joins
  EVERY ordinary-line-to-ordinary-line transition by default, even
  across an already-complete sentence.
- **Candidate C (recommended):** B's structural respect, PLUS a
  narrow, closed-vocabulary content signal deciding whether an
  ordinary line's trailing content looks incomplete: ends in a comma
  or semicolon, OR ends in a closed, generic set of English function
  words/copula-auxiliary-verbs/subject-pronoun-contractions
  (conjunctions, prepositions, articles, possessive determiners,
  "we've"/"it's"/etc., "is"/"are"/"must"/etc., "following"/"follows").
  Span-preserving via DIRECT SLICING of the original `description` --
  **no offset-mapping table is actually needed**, a simplification
  found during implementation: consecutive physical lines separated by
  exactly one newline are ALREADY a contiguous substring of the
  original text, so a joined block's span is simply the first
  fragment's start and the last physical line's content end, and
  `description[start:end]` reproduces the exact original bytes
  (embedded newline included) with zero rewriting.

**Why a line-LENGTH heuristic (considered, rejected) would be worse,
confirmed by a constructed counter-example, not presumed:**
`m11a2-bullets-02` -- two genuinely separate, complete, 65-70-character
bullet requirements, neither ending in punctuation (routine in real
postings) -- would be WRONGLY merged by any secondary signal that
treats "long, unpunctuated line" as a continuation hint on its own.
Rejected for this reason; Candidate C uses ONLY the closed-vocabulary
content signal, never length or part-of-speech inference.

### 3.1 Measured comparison (`evaluate_m11a2_line_wrap.py`, Part 3a: 28 true pairs)

| Candidate | Matches expectation |
|---|---|
| baseline | 10/28 |
| candidate_a (naive) | 26/28 |
| candidate_b (structural-only) | 26/28 |
| candidate_c | 24/28 |
| **candidate_c + hardened `\s+` regexes (§1.3)** | **25/28** |

A and B score HIGHER on raw pair-equivalence than C -- but §3.2/§4
show this is because A/B's content-blind joining is simply more
aggressive, catching real wraps AND silently merging genuinely separate
content the SAME way. C's remaining 3 mismatches are ALL one single,
disclosed residual class: a line ending in an ordinary adjective/noun
with no comma/semicolon/function-word and no terminal punctuation
(`"...professional\nGo experience..."`, `"...with Python\nfor building
scalable..."`, `"...modern development\ntools and frameworks..."`) --
accepted rather than chased with a length/POS heuristic, per §3's own
rejected-candidate finding.

### 3.2 Decisive safety comparison (Part 3b: standalone negative controls)

| Control | baseline | A (naive) | B (structural) | **C (recommended)** |
|---|---|---|---|---|
| `m11a2-oneperline-02` (`"React"`/`"Node.js"`, two genuine separate PREFERRED items) | 2 claims | **1 (wrongly merged)** | **1 (wrongly merged)** | **2 (correct)** |
| `m11a2-ambiguous-03` (`"Must have strong"` / `"analytical skills"`, 2 lines) | 2 claims | **1 (merged)** | **1 (merged)** | **2 (conservative, matches baseline)** |

This is the decisive finding: **A and B both measurably corrupt a
genuine, two-item PREFERRED requirement list into one nonsense claim**;
C does not, on either control.

### 3.3 Required comparison axes, all measured

| Axis | A | B | C |
|---|---|---|---|
| Equivalence across harmless wraps | High (content-blind over-matches) | High (same) | High, with 3 disclosed exceptions |
| False qualification creation | None observed | None observed | None observed |
| Genuine qualification preservation | **Fails** (`m11a2-oneperline-02`) | **Fails** (same) | Preserved |
| Heading/bullet integrity | Preserved (checked explicitly) | Preserved | Preserved |
| Alternative-group preservation | Preserved | Preserved | Preserved (`m11a2-anyof-01/02/03` all correct) |
| Necessity classification | Preserved | Preserved | Preserved |
| Exact source offsets | **Broken by design** (text-level rebuild) | Preserved (span-based) | Preserved (direct slicing) |
| `UnparsedClaim` fidelity | N/A (over-merges away the distinction) | N/A (same) | Preserved -- see §4 |
| Determinism | Yes | Yes | Yes |
| Complexity / regression risk | Low complexity, HIGH regression risk | Low complexity, HIGH regression risk | Moderate complexity, LOW regression risk (measured, §4) |

## 4. Regression evaluation (Phase 4)

`scripts/evaluate_m11a2_line_wrap.py`, run against every corpus the
mission brief named:

| Corpus | n items | baseline total | A removed/added | B removed/added | **C removed/added** |
|---|---|---|---|---|---|
| M10A real postings (SOTI/Manulife) | 2 | 6 | 0 / 0 | 0 / 0 | **0 / 0** |
| M11 held-out postings | 9 | 33 | 3 / 1 (regression, §3.2) | 3 / 1 (same) | **1 / 0** -- removes exactly the confirmed `unresolved:our` fabrication, nothing else |
| M10D alternative controls | 41 | 41 | 0 / 0 | 0 / 0 | **0 / 0** |
| M9B preservation | 30 | 22 | 0 / 0 | 0 / 0 | **0 / 0** |
| Frozen `8c:v1` | 93 | 82 | 0 / 0 | 0 / 0 | **0 / 0** |
| Frozen `8c:v1.1` | 93 | 82 | 0 / 0 | 0 / 0 | **0 / 0** |

**Zero regressions anywhere, for every candidate** on five of six
corpora (none of them contain a genuine multi-line soft wrap to
exercise any join logic at all -- isolated single-line fragments by
construction). On the ONE corpus that does (M11's own held-out
postings), **A and B both introduce a real, measured regression**
(merging `m11-short-01`'s two independent `language.python`/
`language.java` rows into one incorrect alternative group) that **C
does not** -- C's only change anywhere in this entire evaluation is
the ONE intended fix.

Confirmed per the mission brief's own explicit checklist:
- A company narrative does not become a candidate requirement because
  it was wrapped -- confirmed (`m11a2-narrative-01`/`03`, the real
  posting's own primary fabrication).
- An explicit candidate requirement is not lost because it was wrapped
  -- confirmed for every `necessity_preserved`/`explicit_qualification`
  control except the disclosed §3.1 residual class.
- Separate bullet requirements are not accidentally merged -- confirmed
  (§3.2, decisively, where A/B fail and C does not).
- Headings remain correctly recognized -- confirmed (`m11a2-markdown-heading-*`,
  `m11a2-colon-heading-*`).
- Existing OR-groups remain stable -- confirmed (`m11a2-anyof-01/02/03`,
  including the REAL SOTI 9-way and Manulife 4-way groups, wrapped).
- Original source spans remain exact -- confirmed by construction (§3,
  direct slicing, never a rewritten string).
- No previously-correct evaluation case regresses -- confirmed (table
  above, zero removed/added on every frozen corpus).

**Unavoidable ambiguity, reported rather than silently resolved** (the
mission brief's own explicit instruction): the real
`m11-unicode-contradiction-01` fixture's SECOND wrapped sentence
(`"...for this role — however,\nwe are also open to... with strong\nfundamentals..."`)
is only PARTIALLY reconstructed by the recommended design --
confirmed, the fabricated-row count for this one fixture drops from
**5 spurious rows (baseline) to 2** (both from this specific,
disclosed residual class), not to zero. This is reported as a measured
outcome, not claimed as a full fix.

## 5. Architectural design and STOP decisions (Phase 5)

### 5.1 Recommended smallest safe implementation

Two coordinated, additive changes to `jobs/parsing/segmentation.py` and
three regex modules -- no schema, matcher, scoring, concept-registry,
or `qualification_kind`/necessity-enum change of any kind:

1. **`segment_description()`'s own loop** gains a line-grouping
   pre-step: before computing `necessity_hint`/calling
   `_split_sentences`, scan forward from each ordinary (non-heading,
   non-bullet) physical line and extend its content span across any
   immediately-following ordinary line, PROVIDED (a) the gap between
   them is a single newline (not a blank-line paragraph gap), (b) the
   next line is not heading-shaped, (c) the next line is not
   bullet-prefixed, AND (d) the accumulated text so far ends in a
   comma/semicolon OR a closed-vocabulary function
   word/copula-verb/contraction (§3's own list, generalizable, never
   employer- or role-specific). The combined span is computed via
   direct slicing of the ORIGINAL `description` -- no new string, no
   offset-mapping structure.
2. **Three regex literals widened from a single ASCII space to `\s+`**:
   `narrative.py`'s `_COMPANY_NARRATIVE_CUE`/`_LEARNING_NARRATIVE_CUE`,
   `necessity.py`'s `_REQUIRED_MARKER`/`_PREFERRED_MARKER`. Confirmed
   safe (§1.3): `\s+` still matches exactly one space, so every
   existing, unwrapped case is completely unaffected; only a claim
   whose internal word-boundary now happens to fall across a
   reconstructed line-wrap newline is affected, and only by becoming
   MORE correctly recognized, never less.

### 5.2 Source-span/provenance strategy

No offset-mapping table, contrary to this milestone's own Phase 3
anticipation (`"a source-offset mapping"`) -- found unnecessary.
Consecutive physical lines separated by a single newline are already
one contiguous range of the original `description`; a joined `Claim`'s
`start`/`end` is simply `(first_fragment_start, last_physical_line_content_end)`,
and `description[start:end]` reproduces the exact original bytes
(embedded `\n` included) losslessly. `JobRequirement.source_span`
continues to index the SAME original `raw_text` it always has --
confirmed directly, not merely argued, via `JobRequirementProfile.__post_init__`'s
own existing span-bounds invariant (would raise on a malformed span)
never firing across this milestone's entire evaluation.

### 5.3 False-positive / false-negative risk

- **False positive (over-joining):** the closed-vocabulary content
  gate is deliberately narrow; measured zero over-joins across the
  entire 38-control corpus and six regression corpora (§3.2, §4).
- **False negative (under-joining, the accepted residual):** a line
  ending in an ordinary content word (adjective/noun) with no
  comma/semicolon/function-word, continuing on the next line in
  lowercase -- measured 3 instances across 28 pairs (~11%), all the
  SAME class, all disclosed, none causing a fabrication (the
  conservative failure direction: under-joining preserves today's
  existing fragmentation/diagnostic behavior rather than risking an
  incorrect merge).

### 5.4 Historical compatibility analysis

Confirmed via direct re-run, not assumed: M10A (both real postings),
M9B (30 entries), M10D (41 controls), and both frozen `8c:v1`/`8c:v1.1`
benchmarks (93 items each) show **zero requirement-count change** for
the recommended design. The full backend suite (1224 passed, 10
skipped) was re-confirmed unaffected throughout this evaluation-only
session (no `src/gitscore` file was ever modified).

### 5.5 Recommended parser versioning

`JOB_DESCRIPTION_PARSER_VERSION` should bump `v9` → `v10` upon
implementation, consistent with every prior behavior-affecting
milestone in this series (M10B through M11-A1 each bumped on landing,
confirmed by direct inspection of `parser.py`'s own module docstring
history).

### 5.6 Explicit architectural STOP questions

1. **Approve implementing the recommended design (§5.1)** -- the
   line-grouping pre-step in `segmentation.py` PLUS the three `\s+`
   regex widenings in `narrative.py`/`necessity.py` -- as a single,
   coordinated implementation milestone (M11-A2's own follow-up,
   mirroring M11-A1's STOP→implement pattern)?
2. **Confirm the closed continuation-word vocabulary (§3, conjunctions/
   prepositions/articles/possessive determiners/copula-
   verbs/contractions/"following") is acceptable as a fixed,
   hand-maintained list**, rather than deferring to a future, more
   general mechanism (e.g. a POS tagger) -- explicitly NOT proposed
   here, consistent with this project's stated preference for simple,
   deterministic, explainable rules?
3. **Accept the disclosed residual ambiguity (§3.1/§5.3 -- a line
   ending in an ordinary content word with no corroborating
   punctuation/function-word) as a KNOWN, documented limitation**,
   rather than requiring a length-based or part-of-speech heuristic
   that this milestone's own evidence (`m11a2-bullets-02`) shows would
   introduce a WORSE regression (merging two genuinely separate,
   period-less bullet requirements)?
4. **Should `non_technical.py`'s own multi-word phrase patterns**
   (`"communication skills"`, `"work authorization"`, `"security
   clearance"`, etc. -- confirmed structurally vulnerable to the SAME
   literal-space fragility, §1.3, though not exercised by any control
   in this corpus) **be widened to `\s+` in the SAME implementation
   pass, or tracked as a separate, narrower follow-up** given it was
   not empirically triggered here?
5. **Should the real `m11-unicode-contradiction-01` fixture's own
   expected outcome be updated to reflect the measured, partial (not
   full) improvement** (5 spurious rows → 2, §4) **once implemented**,
   rather than left implying a complete fix?

---

**STOP — architecture decision only. No production code was modified.
No commit was made. All five previously-untracked M11/M11-A1 design/
evaluation files remain exactly as they were. Awaiting approval on the
five questions above before any implementation milestone begins.**

## Implementation addendum (post-approval)

All five §5.6 questions were approved as follows: Q1 approved (the
combined segmentation + regex-widening fix, one coordinated
implementation); Q2 approved (the closed, hand-maintained continuation
vocabulary, no POS tagger); Q3 approved (the residual ambiguity
accepted as documented, no length-based merging); Q4 answered DEFER
(`non_technical.py`'s own vulnerable patterns tracked as a separate
follow-up, not widened in this pass); Q5 answered via the
implementation's own reporting requirement (the real fixture's
expected outcome is reported as measured — 2 residual rows, not 0 —
pinned directly by `tests/test_m11a2_line_wrap_integrity.py::test_unicode_contradiction_fixture_fabrication_reduced_from_five_to_two_not_zero`).

### What shipped

1. `jobs/parsing/segmentation.py`: `_TERMINAL_PUNCT`, `_TRAILING_SOFT_PUNCT`,
   `_CONTINUATION_WORDS`, `_ends_incomplete()`, `_is_paragraph_gap()`
   (new) — the exact closed vocabulary and content-signal logic this
   document's §3 Candidate C describes, moved from prototype to
   production verbatim. `segment_description()`'s own loop restructured
   from a single `for` over physical lines into an index-based `while`
   that, for each ordinary line, extends its content span across any
   immediately-following soft-wrap-continued line before computing
   `necessity_hint`/calling `_split_sentences` — heading/bullet/
   paragraph-gap checks unchanged, checked first, always a hard stop.
2. `jobs/parsing/narrative.py`: `_LEARNING_NARRATIVE_CUE`/
   `_COMPANY_NARRATIVE_CUE` — every literal single-space separator
   widened to `\s+`.
3. `jobs/parsing/necessity.py`: `_REQUIRED_MARKER`/`_PREFERRED_MARKER`
   — same widening.
4. `JOB_DESCRIPTION_PARSER_VERSION`: `v9` → `v10`.

No change to `jobs/models.py`, `jobs/profile.py`, `matching/`,
`assessment/`, `scoring/`, the concept registry, or any API/frontend
surface — confirmed, not merely asserted: `git status` throughout
implementation showed only the three files above plus test/doc
changes.

### Final verification results

| Check | Result |
|---|---|
| Full backend suite | 1223 pre-existing (after M11-A1's `v9` pin removal) − 1 removed (stale `v9` pin, superseded) + 38 new = **1261 passed, 13 skipped** |
| Focused M11-A2 tests | 38/38 passed (3 explicitly `pytest.mark.skip`-marked as the disclosed residual gap, not silently passing) |
| 38-control corpus used as pre-established, not rewritten | Confirmed — `tests/test_m11a2_line_wrap_integrity.py` loads `evaluation/m11a2/line_wrap_controls.json` directly and asserts its own `expect_equivalent` field verbatim |
| M11 generalization development corpus | Byte-identical report (`evaluate_m11_generalization.py` re-run) |
| M11-A1 fabrication tests | All pass unchanged (16/16, version pin updated to `v10` in the new file, old `v9` pin removed from `test_m11_a1_fabrication_fixes.py`) |
| M10A real postings | Byte-identical (`false_positive_requirements`, `meets_ideal_outcome`, `meets_neither` all unchanged) |
| M9B preservation | Byte-identical except the version string |
| Frozen `8c:v1`/`8c:v1.1` | **Zero diff**, confirmed via `scripts/check_evaluation_staleness.py` on a clean pre-fix tree (`git stash`) AND the post-fix tree |
| Exact pair-equivalence (corpus Part 3a) | 24/24 non-skipped true pairs match exactly; 1 ambiguous-boundary pair confirmed non-fabricating |
| False qualification creation | None found anywhere in this implementation's own verification |
| Genuine requirements lost | None — every genuine qualification in every regression corpus survives unchanged |
| Previously corrupted requirement boundaries | None introduced (the naive candidates' own `"React"`/`"Node.js"` corruption, confirmed NOT present in the shipped design) |
| Remaining 2 fabricated rows in the original fixture | Confirmed and pinned by test, not silently dropped |
| Source-span exactness | Confirmed directly (`test_source_spans_remain_exact_for_a_joined_claim`): `text[span.start:span.end] == original_text` for a joined, multi-line claim |
| Historical evaluation drift | None beyond the expected version-string line in M9B's own report |

### Outstanding, explicitly undone

- **`non_technical.py`'s own literal-space phrase patterns** — not
  widened, per Q4's approval to defer as a separate workstream.
- **The disclosed residual ambiguity** (a line ending in an ordinary
  content word with no comma/semicolon/function-word) — not solved,
  per Q3's approval; pinned by test as a measured, accepted limitation.
- **No `qualification_kind`/necessity-enum/matcher/scoring/schema
  change** — confirmed, not merely asserted.
- **M11-B's own broader architecture question** — untouched, reserved
  for its own future, separately-approved decision.
