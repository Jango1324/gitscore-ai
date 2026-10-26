# Milestone 10A — Real-World Job Description Parsing Failure Investigation

**Status: investigation and evaluation only.** No file under `src/gitscore/`
was modified. No matcher, scoring formula, concept registry, or
assessment semantic was touched. No frozen gold under `evaluation/gold/`,
`evaluation/gold_v1_1/`, or `evaluation/m9b/` was modified. Two new,
additive, read-only artifacts were added: `evaluation/m10/corpus.json`
(the independently-annotated benchmark) and `scripts/evaluate_m10a_realworld.py`
(the measurement harness, producing `evaluation/reports/m10a_realworld_report.json`).
Not committed, not pushed. No production code change was made or is
proposed without explicit approval (Section 8).

---

## 0. Source material and provenance

`evaluation/m10/source/soti_raw.txt` and `manulife_raw.txt` are plain-text
transcriptions the project owner provided of two real job postings
(SOTI Software Engineering Intern; Manulife John Hancock Software
Engineering Co-op). **Not claimed byte-exact** to the original postings —
treated throughout as "a real-world posting's structure and wording,"
never as a verified-exact legal document. Confirmed present and read in
full before any annotation was written.

### 0.1 What fidelity is, and is not, guaranteed (verification-pass check F)

**Confirmed, checked directly against the raw bytes:**
- Both files are valid UTF-8, with no byte-order mark.
- Neither file contains a Unicode replacement character (`U+FFFD`) —
  the `�` glyphs visible in this session's own terminal output when
  printing the files are a **Windows-console display artifact only**
  (this terminal's limited codepage failing to render a real character)
  — the underlying file bytes decode correctly. Confirmed directly: the
  character at every such position is `U+2019` (RIGHT SINGLE QUOTATION
  MARK, a proper curly apostrophe), not corrupted data.

**NOT guaranteed, and not claimed:**
- Byte-exact fidelity to the original web posting (formatting, exact
  line wrapping, any markup that did not survive a copy/paste
  transcription).
- That every real section of either original posting is represented —
  the Manulife transcription itself ends mid-section at "Working
  Arrangement" with no further text, which `evaluation/m10/corpus.json`'s
  own `m10a-man-43` entry notes explicitly as "genuinely unknown"
  rather than inferring what would have followed.

**A real integrity bug this exact distinction caught, during the
verification pass that added `tests/test_m10a_evaluation_integrity.py`:**
five corpus entries (`m10a-man-01`, `17`, `18`, `19`, `20`) were
originally hand-typed using plain ASCII straight apostrophes (`'`),
while the real source file — and therefore every real `Claim.text` the
segmenter actually produces — uses the curly `U+2019` character. This
silently broke the measurement script's exact-text lookup for those
five entries (every lookup returned "not found," regardless of what the
real parser actually did), confirmed and fixed this session; see §2.1
below. The aggregate counts in §4 happened to be unaffected (all five
are non-requirement company narrative where the fix only corrected an
internal `has_unparsed_claim` field, not the entry's final verdict),
but the per-entry data was objectively wrong until this fix landed.

---

## 1. Verified baseline (Phase 0)

| Check | Result |
|---|---|
| Working tree before this milestone's own additions | clean (confirmed via `git status --short`) |
| `python -m pytest` | **934 passed**, 0 failed — unchanged after this milestone's additions (no production file touched) |
| `python scripts/evaluate_m9b_preservation.py` re-run | byte-identical to the committed report (`git diff --stat` empty) |

---

## 2. Annotation method — corrected characterization (verification-pass check D)

**Correction to this document's own first draft.** An earlier version
of this section, and of `evaluation/m10/corpus.json`'s own
`source_note`, claimed every annotation was "written by reading the
posting text alone, BEFORE running the real parser," explicitly
likening it to M9B's discipline. **That claim is not accurate for this
milestone and has been retracted** (both here and in the corpus file's
own `source_note`, which now carries the correction in place). The
actual sequence, honestly reconstructed: the posting text was read and
a semantic judgment formed first, but the real parser was then run
against both postings as an exploratory step, and the `is_requirement`/
`category_annotation`/`ideal_outcome`/`acceptable_fallback` fields were
only FORMALIZED INTO `corpus.json` afterward, in the same working
session, with that output already observed. **These are retrospective
evaluation judgments, not a blind pre-registration** — unlike M9B's
corpus, which has a dedicated structural test
(`test_every_entry_declares_its_annotation_independently_of_the_parser`)
enforcing the separation, M10A's corpus has no equivalent guarantee and
none is claimed. `tests/test_m10a_evaluation_integrity.py`'s own module
docstring states this explicitly, and no test in that file asserts or
could truthfully assert pre-parser independence.

This does not retroactively invalidate the semantic judgments
themselves (§6 independently cross-checks several against the frozen
`general_swe_01` gold, and the category/requirement-or-not calls are
independently defensible on a fresh re-read), but the PROCESS does not
carry M9B's stronger procedural guarantee, and no future reader of this
corpus should assume otherwise.

### 2.1 What the integrity tests added this verification pass actually caught

`tests/test_m10a_evaluation_integrity.py` (new) found three real
defects on its first run, before any of them were fixed:

1. Five corpus entries' `text` field used the wrong apostrophe
   character relative to the real source file (§0.1) — found by
   `test_every_claim_text_is_an_exact_substring_of_its_posting_source_file`
   and `test_every_real_segmentation_claim_has_a_corpus_entry`. Fixed by
   replacing the five `text` values with the exact string extracted
   from the source file.
2. One test (not the corpus) was too narrow — it didn't recognize
   `"heading_recognized_not_a_claim"` as a valid "no requirement row"
   outcome for a confirmed false positive. Fixed in the test itself.

Both are now fixed and the full suite (13 tests) passes; see §G below
for the full re-run.

**Why a per-posting, not per-sentence, corpus.** M9B's `evaluation_lib/preservation_eval.py::wrap_entry`
wraps every individual corpus sentence into one of six fixed templates —
`"Requirements:\n- {text}\n"`, `"Preferred Qualifications:\n- {text}\n"`,
etc. — **always using an already-recognized heading string**. Confirmed
by direct inspection: none of M9B's 30 entries, and none of
`evaluation/jobs/*.json`'s frozen `8c:v1`/`8c:v1.1` postings, ever test a
heading VARIANT ("Required Skills" vs. "Requirements," "Position
Responsibilities" vs. "Responsibilities," "About SOTI" vs. "About Us").
**This milestone's central finding is structurally invisible to every
existing evaluation corpus** — it only manifests across a real,
multi-section document with the heading phrasing an actual company
chose, which is exactly why `evaluation/m10/corpus.json` preserves each
posting's FULL text and section structure rather than decomposing it
into isolated, re-wrapped sentences.

---

## 3. Exact root causes (traced live against the real, unmodified parser)

### Root Cause 1 — the heading-recognition table is a small, exact-match set that misses extremely common real-world phrasing

`jobs/parsing/segmentation.py`'s four heading tables require the
**entire** line (after stripping one trailing colon and lowercasing) to
equal one of a small set of fixed phrases. Confirmed misses, from the
two real postings:

| Real heading | Closest recognized phrase | Recognized? |
|---|---|---|
| "Required skills" (SOTI) | "requirements" / "required qualifications" / "qualifications" | **No** |
| "Position Responsibilities" (Manulife) | "responsibilities" / "key responsibilities" | **No** |
| "What you will learn" (SOTI) | *(no category exists for this at all)* | **No** |
| "About SOTI" / "About Manulife and John Hancock" | "about us" / "about the company" | **No** |
| "When you join our team" / "Application instructions" / "Working Arrangement" (Manulife) | *(no category exists)* | **No** |
| "Required Qualifications" / "Preferred Qualifications" (Manulife) | exact matches in `_REQUIRED_HEADINGS`/`_PREFERRED_HEADINGS` | **Yes** |

A heading only needs ONE extra or different word ("Position
Responsibilities" vs. "Responsibilities") to silently fail.

### Root Cause 2 — `current_kind` never resets when a heading fails to match; it stays whatever the LAST successfully-recognized heading set it to, for the rest of the document

This is the single most consequential, newly-confirmed mechanism of
this milestone. Live-traced via `segment_description()` directly:
**every claim in the Manulife posting from "Exposure to software
frameworks, libraries, or development tools" (the first "Preferred
Qualifications" bullet) through "Working Arrangement" (the posting's
final line) carries `necessity_hint = PREFERRED`** — a span covering
"When you join our team," "Application instructions," the entire
salary-disclosure paragraph, "About Manulife and John Hancock," and the
**entire EEO/accommodation legal paragraph** — because none of the five
headings in that span re-match any table, so `current_kind` is never
reassigned away from `_SectionKind.PREFERRED`.

```python
necessity_hint = _SECTION_NECESSITY_HINT.get(current_kind, Necessity.REQUIRED)
```

This single line is the entire mechanism: it has no "reset to neutral/
unknown on an unrecognized heading" branch — a currently-open section
kind persists indefinitely.

### Root Cause 3 — the outside-heading `_looks_like_requirement()` gate is accidental in both directions

Once `current_kind` is `None` or inherited-but-irrelevant, content is
admitted as a `Claim` only if it contains one of ~16 generic trigger
words (`experience|proficien...|knowledge of|familiar...|degree|years?|
required|preferred|plus|responsib...|skills?|certificat...|licensed?|
eligible|authoriz...|mentor...`) or mentions a registered concept. This
single gate:

- **Admits** unrelated prose whenever it happens to contain a trigger
  word or an incidental concept-name substring (confirmed: a company-
  bio URL ending in `.html`; a pay-transparency disclosure mentioning
  "knowledge, skills, qualifications, experience"; an EEO clause whose
  long protected-characteristics list happens to contain two literal
  "or"s).
- **Silently discards** genuine requirement content with **zero trace
  anywhere** (not even `unparsed_claims`) whenever it does not happen to
  contain a trigger word (confirmed: all six Manulife "Position
  Responsibilities" bullets; SOTI's "Most importantly curiosity, a
  desire to learn and be a part of a team").

### Root Cause 4 — `"at least one of A, B, C (e.g., ...)"` without the literal word "or" is never recognized as an alternative group at all

`jobs/parsing/alternatives.py::contains_alternative_marker()` requires
the literal word `"or"`. Manulife's "Experience with at least one
programming language (e.g., Java, Python, Go, JavaScript)" contains no
"or" — it uses a parenthetical `"(e.g., ...)"` example list instead.
`classify_alternative_claim()` therefore never attempts group detection
at all; `find_concept_mentions()` finds all four languages independently,
and the existing "one row per matched concept per claim" design (M9A/
6B.1 — correct for "Docker AND Kubernetes," both genuinely required)
mints **four separate, independently-assessed REQUIRED rows** instead
of one "any ONE of 4" group.

**Confirmed via a clean contrast test against the FROZEN `general_swe_01`
gold** (`evaluation/gold/jobs/general_swe_01.json`): "Proficiency in at
least one of Python, Java, or C++" — the SAME "at least one of" idiom,
but phrased with an Oxford-comma "or" before the last item — is
**already correctly handled today** as a single alternative group. This
isolates Root Cause 4 precisely to the "(e.g., ...)" parenthetical-list
phrasing variant, confirmed genuinely absent from every existing frozen/
M9B corpus entry (`grep` confirms no `.html`/URL and no "(e.g.," pattern
without an accompanying "or" anywhere in `evaluation/gold*/jobs/` or
`evaluation/m9b/corpus.json`).

### Root Cause 5 — idiom-blind "or" splitting in the SAME alternative-detection code

SOTI's "Basic knowledge of programming in **one or more of** the
following programming languages: C, C++, Java, JavaScript, SQL, Ruby,
Rust, Lua, Haskell" DOES contain a literal "or" — inside the filler
idiom "one or more." `_split_alternative_segments()` has no idiom
awareness and splits on it anyway, producing a garbage leading segment.
For this exact sentence the garbage segment fails even the `leading_token`
escalation (no real registry match) → `unsafe=True` → the whole claim
correctly falls back to the existing conservative placeholder (zero
fabrication, confirmed), but the full 9-language ANY-of structure is
entirely lost. **An earlier illustrative reconstruction tried during
this investigation's prior turn, with slightly different punctuation
around the same idiom, instead fabricated a spurious `unresolved:one`
"technology" merged into an otherwise-real alternative group** — proving
the exact failure mode (safe-but-structure-losing vs. actively
fabricating) is phrasing-sensitive, but both trace to the identical
idiom-blind root cause.

---

## 4. Measured results (`scripts/evaluate_m10a_realworld.py`, reproducible)

| Metric | SOTI (12 claims) | Manulife (43 claims) |
|---|---|---|
| False-positive requirements (scored row from non-requirement text) | **1** | **5** |
| Invisible genuine **qualifications** (`is_requirement: true`, zero trace anywhere) | **1** | **0** |
| Invisible **responsibilities/duties** (`is_requirement: false`, category `responsibilities`, zero trace anywhere — never a missed qualification) | **0** | **6** |
| Malformed alternative groups (fabricated option, or OR-semantics lost entirely) | **0** | **1** |
| Meets `ideal_outcome` | 6 / 12 | 29 / 43 |
| Meets `acceptable_fallback` only | 4 / 12 | 2 / 43 |
| Meets neither (genuine defect) | **2 / 12** | **12 / 43** |

**Deliberately two separate, never-summed rows for "invisible," per a
verification-pass correction**: the six fully-invisible Manulife claims
are "Position Responsibilities" bullets — job DUTIES, independently
annotated `is_requirement: false` in `evaluation/m10/corpus.json` from
the outset — never applicant qualifications. Merging them into one
"invisible genuine requirements" count (as an earlier draft of this
table did) would have inflated a requirement-RECALL metric with
non-requirement content. They remain diagnostic-worthy (losing all
trace, including from `unparsed_claims`, is still worse than the
acceptable `unparsed_claim` fallback this corpus specifies for them)
but are never comparable to SOTI's one genuine missed qualification
(the "curiosity, a desire to learn..." bullet, correctly annotated
`is_requirement: true`). The six Manulife bullets are a single,
complete section — 100% of "Position Responsibilities," zero trace
anywhere — not six independent misses.

**Zero instances of fabricating a concept id that does not correspond
to ANY real or plausible technology name were found** (the `unresolved:one`
fabrication occurred only in the prior turn's illustrative
reconstruction, not in either real posting) — this milestone's own
non-fabrication measurement (`malformed_alternative_groups`) counts the
Manulife "at least one of" OR-structure loss (Root Cause 4), which
fabricates nothing but silently changes assessment semantics (see §5).

### 4.1 Full false-positive list (both postings)

| Claim | What it actually is | What it became |
|---|---|---|
| "The technologies you learn during an internship... languages like C#, or... leveraging SQL..." (SOTI) | Learning-exposure narrative | **REQUIRED** alternative group `(language.csharp, language.sql)` |
| "The actual salary will vary depending on... factors such as knowledge, skills, qualifications, experience, and education/training." (Manulife) | Pay-transparency compensation-methodology disclosure | **PREFERRED** `unresolved_requirement` placeholder |
| "This posting supports an ongoing hiring initiative for existing and/or future vacancies." (Manulife) | A statement about the REQ/posting itself | **PREFERRED** `unresolved_requirement` placeholder |
| "We use data and analytics technologies, such as artificial intelligence (AI)..." (Manulife) | Applicant-data-processing/privacy disclosure | **PREFERRED** `unresolved_requirement` placeholder |
| "To learn more about us, visit https://www.manulife.com/en/about/our-story.html." (Manulife) | A URL pointing to company information | **PREFERRED**, `concept_id='language.html'` |
| The entire EEO/anti-discrimination clause (Manulife) | Legal boilerplate — the original user-reported defect | **PREFERRED** `unresolved_requirement` placeholder |

---

## 5. Expected vs. actual requirement extraction (summary table)

See `evaluation/m10/corpus.json` for the complete, claim-by-claim
annotation (12 + 43 entries). Headline contrasts:

| | Expected | Actual |
|---|---|---|
| SOTI "Opportunity"/learning-exposure text | Zero requirement rows | 1 fabricated REQUIRED alt-group |
| SOTI "Required skills:" heading | Section boundary, never a claim | Spurious `unparsed_claim` |
| SOTI 4 genuine required-skill bullets | Visible at minimum as diagnostics | 3 of 4 correctly reach `unparsed_claims`; the 9-language enumeration correctly avoids fabrication but loses ANY-of structure |
| SOTI "curiosity/desire to learn" bullet | At minimum a diagnostic trace | **Zero trace anywhere** |
| SOTI "About SOTI" company bio | Zero requirement rows | Zero rows (correctly excluded — but by accident of no trigger word matching, not by design) |
| Manulife "Position Responsibilities" (6 bullets) | At minimum a diagnostic trace each | **Zero trace anywhere, for all six** |
| Manulife "at least one programming language (e.g., ...)" | One ANY-of-4 alternative group | **Four independent REQUIRED rows** |
| Manulife EEO/legal/salary/privacy boilerplate (5 sentences) | Zero requirement rows | **5 separate PREFERRED rows** |

---

## 6. Proposed generalizable designs (not implemented)

### 6.1 Conservative, priority-aware section classifier (addresses Root Causes 1 & 2 together)

**Principle: classify every heading by checking a small set of ROOT
WORDS the line *contains*, never an exact-phrase table it must *equal*
— and resolve ties by an explicit priority order, never a blocklist of
company names.**

```
REQUIRED-family root words:   requir*, qualif* (when not preceded by "preferred"/"nice to have" nearby), must have, mandatory
PREFERRED-family root words:  preferr*, "nice to have", bonus, "a plus"
RESPONSIBILITY-family:        respons*, duties, "what you'll do", "the role"
LEARNING-family (NEW category): "what you will/'ll learn", "you will learn", "growth opportunit*"
SKIP-family:                  about, benefit*, perk*, compensation, salary, "how to apply", "equal opportunity", diversity, accommodation, "application instructions"
```

A line matching MORE THAN ONE family (rare) resolves by explicit
priority: REQUIRED > PREFERRED > RESPONSIBILITY > LEARNING > SKIP —
chosen so a false SKIP never swallows a real requirement, but a
genuine requirement heading is never miscategorized as a skip either.

**Equally important as the classifier itself: fix Root Cause 2
independently of broadening the table.** Whenever a line is
heading-SHAPED (short, title-cased, often colon-terminated) but matches
NO family at all, `current_kind` should become a new, distinct
`_SectionKind.UNKNOWN` — **never silently inheriting the previous
section's kind.**

**Correction, verification pass, architectural decision 3 (NOT
approved): defaulting `_SectionKind.UNKNOWN` to `Necessity.PREFERRED`.**
An earlier draft of this section proposed mapping `UNKNOWN` to
`Necessity.PREFERRED` in `_SECTION_NECESSITY_HINT` — reasoning that it
is the less alarming of the two existing values when genuinely
uncertain. **This was presented as an option, not approved, and is
explicitly withdrawn**: unknown-section text must never automatically
become a FORMAL, necessity-bearing requirement at all, neither REQUIRED
nor PREFERRED — picking the "lesser of two evils" from an existing
two-value enum is still fabricating a necessity judgment the posting
never actually made.

**The correct design question for a future, separately-scoped
proposal** is therefore not "which of REQUIRED/PREFERRED should
`UNKNOWN` default to," but "should content under an unrecognized
heading be allowed to become a scored `JobRequirement` row via the
default-necessity path AT ALL." A non-scoring diagnostic sketch (not
implemented, not yet approved, offered as the shape such a proposal
would need to take): a `Claim` carrying `necessity_hint = UNKNOWN`
would still run through every existing per-claim detector exactly as
today, and LOCAL wording would still take precedence exactly as
`necessity.py` already does (an explicit "required"/"must have" in the
claim's own text still wins, unchanged) — but if NO local marker fires,
the claim would route to a diagnostic-only outcome (conceptually
extending the existing `UnparsedClaim`/`unparsed_claims` shape, which
already carries no necessity at all, rather than inventing a third
`Necessity` value) instead of silently defaulting to either formal
necessity. This is deliberately a SKETCH of the shape, not a proposed
implementation — the exact mechanism (a new diagnostic type vs.
reusing `UnparsedClaim` vs. something else) needs its own design pass
and its own approval, exactly as decision 3 requires.

This would still have prevented every Manulife false positive in §4.1
(none of those five sentences contains a local REQUIRED/PREFERRED
marker, so all five would correctly fall through to the non-scoring
diagnostic rather than a formal row of any necessity) — independent of
whether the classifier recognizes "About Manulife and John Hancock" by
name.

**False-positive risk:** substring matching on roots like `qualif*`
could over-match ("Skills you'll gain" under a LEARNING heading
contains no REQUIRED-family root, so that specific example is safe, but
this needs a real, curated positive/negative control set before
implementation — not asserted safe here).

### 6.2 Smallest generalizable fix for "one or more of" / "at least one of" alternative-list parsing (separate, smaller proposal)

Two independent, narrowly-scoped sub-fixes, deliberately NOT combined
into one change:

**(a) Idiom-blind "or" splitting (Root Cause 5).** Add a negative
lookaround to `_ALTERNATIVE_MARKER` (or a pre-filter before
`_split_alternative_segments` runs) that recognizes the fixed English
idioms `"one or more"` and `"X or more"` as NOT list-separator "or"s.
Narrowly scoped to these specific idioms, never a general "or" blocklist.

**(b) "At least one of A, B, C (e.g., ...)" with no literal "or" (Root
Cause 4).** Add a SECOND, narrow trigger phrase set
(`"at least one of"`, `"any one of"`, `"one of the following"`) that
`classify_alternative_claim()` also checks, independent of
`contains_alternative_marker()`'s bare-"or" check — when found, treat
the subsequent comma/parenthetical-list exactly as an OR-segment list,
through the SAME existing per-segment resolution logic
(`_resolve_segment`) alternative detection already uses for "or"-joined
lists. This generalizes to the exact Manulife phrasing without ever
hardcoding "Java, Python, Go, JavaScript."

**False-positive risk for (b):** lower than §6.1's classifier — this is
a narrow phrase-trigger addition, not a heading-wide reclassification,
and reuses existing, already-tested segment-resolution code rather than
inventing new matching logic. Still requires its own before/after
regression against the full M9B corpus before implementation.

---

## 7. Comparison against M9B and frozen 8C (no gold modified)

- **Zero existing M9B corpus entries exercise a heading variant, a
  sticky-necessity scenario, or a URL/`.html` pattern** — confirmed by
  direct `grep` across `evaluation/m9b/corpus.json` and every
  `evaluation/gold*/jobs/*.json` file. This milestone's findings are
  **entirely additive and non-overlapping** with M9B's own 23%
  silent-drop measurement (M9B's gap is about PER-CLAIM detector-chain
  narrowness within an already-correctly-sectioned posting; this
  milestone's gap is about SECTION/HEADING recognition itself).
- **One existing frozen entry (`general_swe_01`'s "Proficiency in at
  least one of Python, Java, or C++") was used as a clean POSITIVE
  contrast control**, confirming the "or"-joined phrasing already works
  correctly today — isolating Root Cause 4 precisely to the
  "(e.g., ...)" phrasing variant, rather than to "at least one of" in
  general.
- **`python scripts/evaluate_m9b_preservation.py` re-run and diffed
  byte-identical** against the committed report — this investigation
  changed nothing about M9B's own measured 0.615 recall / 0 fabrication
  counts.
- **No frozen `8c:v1`/`8c:v1.1` gold file was read as ground truth to
  derive new annotations from** — `general_swe_01`'s gold was consulted
  only as an independent cross-check AFTER this milestone's own
  SOTI/Manulife annotations were already written, per this project's
  standing rule against deriving gold from gold.

---

## 8. Architectural approval questions — WITH DECISIONS RECORDED

1. **Approve evaluation-first scoping of the §6.1 section classifier**
   as its own, separately-approved future milestone, requiring a
   dedicated positive/negative control corpus (headings that SHOULD and
   should NOT match each family, across multiple real companies' likely
   phrasing) before any parser code is written — mirroring M9F's own
   precedent for Option B there?
   **DECIDED: approved, evaluation-only.** No parser code written.
2. **Approve the §6.1 "never silently inherit the previous section's
   necessity" fix as a priority item independent of the classifier
   itself**? Should this be scoped and approved SEPARATELY and FIRST,
   ahead of the broader heading-vocabulary work?
   **DECIDED: the GOAL (prevent stale-necessity inheritance) is
   approved as a priority. The originally-proposed MECHANISM
   (`_SectionKind.UNKNOWN` defaulting to `Necessity.PREFERRED`) is
   explicitly NOT approved** — unknown-section text must never
   automatically become a formal preferred qualification either. §6.1
   now sketches a non-scoring-diagnostic shape instead, which still
   needs its own separate design proposal and approval before any
   implementation.
3. **Approve §6.2(a) and §6.2(b)** as two independent, narrowly-scoped
   near-term fix candidates, each requiring its own before/after
   regression against the full M9B corpus?
   **DECIDED: approved as independent future fix CANDIDATES. Not
   authorized for implementation yet** — still requires its own later
   STOP-point approval once each is actually designed in detail.
4. **Confirm severity ranking**: should the Manulife Responsibilities
   finding be ranked as this project's highest-severity open parsing
   defect to date?
   **DECIDED, with correction: this is a transparency/section-coverage
   defect, NOT a missing-applicant-qualification defect** — the six
   bullets are job duties, independently annotated `is_requirement:
   false` throughout. Ranked as the worst TRANSPARENCY gap found to
   date (zero trace of substantive posting content, worse than
   `unparsed_claims`), explicitly not as a requirement-recall defect.
   See §4's now-split metric and §E below.
5. **Decide disposition of the prior session's Manulife necessity-
   marker (same-sentence "bonus"/"ideally" keyword-bleed) finding** —
   distinct and lower-priority, or superseded?
   **DECIDED: preserved as distinct and lower-priority**, exactly as
   proposed — both mechanisms are independently real.

---

## Verification-pass addendum (post-first-draft corrections)

This document was revised after a dedicated verification pass. Three
corrections of substance were made, each cross-referenced above:

- **§0.1 / §2 / §2.1**: the claim that annotations were written BEFORE
  running the parser has been retracted and replaced with an honest,
  retrospective-judgment characterization. `evaluation/m10/corpus.json`'s
  own `source_note` carries the same correction.
- **§6.1**: the `_SectionKind.UNKNOWN` → `Necessity.PREFERRED` default
  has been withdrawn per architectural decision 3 above; replaced with
  a non-scoring-diagnostic sketch requiring its own future approval.
- **§4**: the "invisible" metric has been split into
  `invisible_genuine_qualifications` (SOTI: 1, Manulife: 0) and
  `invisible_responsibilities_or_duties` (SOTI: 0, Manulife: 6),
  **never summed**, so the six Manulife job-duty bullets can never be
  misread as six missed applicant qualifications.
- **New**: `tests/test_m10a_evaluation_integrity.py` (13 tests) —
  caught and fixed a real data bug (five corpus entries using the wrong
  apostrophe character, silently breaking their text-matching lookup;
  see §0.1) and one too-narrow test assertion, both now fixed.

---

## 9. Files added this milestone

- `evaluation/m10/corpus.json` (new, additive — 2 postings, 55 total
  claims, retrospectively annotated; see §2's corrected characterization)
- `evaluation/m10/source/soti_raw.txt`, `manulife_raw.txt` (new,
  additive — the real posting transcriptions this corpus and script
  both depend on; **required for the benchmark to run at all**, see §B
  of the verification-pass report)
- `scripts/evaluate_m10a_realworld.py` (new, additive, read-only measurement harness)
- `evaluation/reports/m10a_realworld_report.json` (new, generated by the script above)
- `tests/test_m10a_evaluation_integrity.py` (new, additive — 13 structural integrity tests)
- `docs/evaluation/MILESTONE_10A_REALWORLD_PARSING_FAILURES.md` (this file)

**No file under `src/gitscore/` was modified. No frozen gold was
modified. `python -m pytest` remains 934 passed, unchanged.**

---

## Reproduction

```powershell
python -m pytest                                  # 934 passed, unchanged
python -m pytest tests/test_m10a_evaluation_integrity.py -v   # 13 passed
python scripts/evaluate_m10a_realworld.py          # writes evaluation/reports/m10a_realworld_report.json
python scripts/evaluate_m9b_preservation.py        # byte-identical to committed report
git diff --stat evaluation/reports/m9b_preservation_report.json evaluation/reports/m9b_preservation_report.md
```

**Requires `evaluation/m10/corpus.json` AND
`evaluation/m10/source/{soti,manulife}_raw.txt` AND
`scripts/evaluate_m10a_realworld.py` to all be present together — the
script has no other, hidden dependency (no untracked local file, no
`scripts/evaluation_lib` import).**

**DO NOT COMMIT. DO NOT PUSH. DO NOT IMPLEMENT ANY MATERIAL CHANGE
BEFORE THE §8 APPROVAL QUESTIONS' REMAINING OPEN ITEMS (the classifier
control corpus; the non-scoring-diagnostic design; either §6.2 fix's
own detailed design) ARE SEPARATELY PROPOSED AND APPROVED.**
