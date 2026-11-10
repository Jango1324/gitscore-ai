# Milestone 11-G21 — Qualification-Intent Admission Guard (parser v14)

This milestone ports G20's evaluated policy **B1NR** to production. B1NR is an
admission guard plus a necessity refinement. The change touches only these files:

- `qualification_intent.py` (new)
- `necessity.py`
- `parser.py`

The parser version moves `job_description_parser:v13` → **`v14`**. Scoring stays at
`github_evidence_alignment:v2`. The matcher, segmentation, headings, alternatives,
concepts, API and frontend are all unchanged.

**Reproduce.** The v13 side is always the pinned commit `a260282`, never a moving HEAD.

- **Revised v14 (the committed implementation).**
  `python scripts/evaluate_m11g21_v13_v14.py --label revised [--private-corpora]`
  writes `v13_v14_revised_comparison.json` and `private_v13_v14_revised_aggregates.json`.
- **First v14 (never committed).**
  `python scripts/evaluate_m11g21_v13_v14.py --reproduce-original [--private-corpora]`
  applies `evaluation/m11g21/first_v14_reverse.patch` to the three production files in a
  throwaway clone. It then checks that the preserved `v13_v14_comparison.json` and
  `private_v13_v14_aggregates.json` are reproduced **byte-identically**. Both were
  verified before the commit.
- **No label.** Running without a label is refused, so the preserved first-v14 record
  cannot be overwritten.

> **Status: revised by the Option B negation-scope correction (§4b).** The first v14
> port lost two genuine qualifications on the fresh adversarial set. Negation is now
> clause-local. §1–§4 describe the first port and its results, which are kept as
> recorded (`v13_v14_comparison.json`). §4b gives the correction and the revised
> results (`v13_v14_revised_comparison.json`, written with `--label revised`). Since
> their failures informed the correction, the 35 adversarial controls are now
> **development data**.

## 0. Baseline (verified)

| Check | Value |
|---|---|
| HEAD | `a2602820b21d521c7ac4006b6738224fde716e2c`, `main`, level with `origin/main` |
| Parser / scoring | v13 / v2 |
| Backend | 2126 passed, 13 skipped, 18 xfailed |
| Frontend | 53 passing |
| Manifest | 13 entries |
| Private untracked M11 entries | 18 (preserved) |

## 1. Production change

**`parser._requirements_from_claim`** — two steps, both run before any
`JobRequirement` is built.

1. **Admission check.**
   `if not decide_qualification_intent(claim.text, claim.section_kind).admit: return []`.
   The empty return sends the claim down the existing `UnparsedClaim` path, keeping its
   exact text and span.
2. **Necessity refinement.** After `infer_necessity()` and its existing `None` check,
   `necessity = refine_necessity(claim.text, necessity)` runs. A `None` result also
   returns `[]`.

**Admission algorithm** (`qualification_intent.py`). This is the frozen G20 B1 admission
(`admit_b`) plus G20's two documented post-hoc frame corrections.

- The claim is split into clauses on ";" and ", but".
- **Positive frames:**
  - *strong:* a candidate subject — "you have / must / should / need / bring",
    "candidates must", "the ideal candidate", "we are looking for", "we require
    N years / someone";
  - *weak:* a candidate-attribute phrase — experience, knowledge, proficiency,
    familiarity, degree, "N years", "ability to", "comfortable with";
  - *marker:* production's REQUIRED/PREFERRED marker, a predicate such as "is a must"
    or "is a plus", or a concession.
- **Negative frames:**
  - employer or product subject ("We / Our / The team …", case-sensitive "us");
  - future duty ("you will / you'll + verb", except need / have / bring / "be comfortable"
    and similar);
  - learning;
  - benefit;
  - hiring process;
  - technology-as-subject discussion ("Rust is gaining…");
  - team practice ("All services must be written…").
- **Clause role.** A clause is a qualification if it has a strong frame, or a marker
  together with an attribute. Otherwise any negative frame makes it a non-qualification.
  Otherwise any weak frame or marker makes it a qualification. Otherwise it is neutral.
- **Claim decision** (first port; superseded by the clause-local negation in §4b).
  - A whole-claim negation (not concessive or appreciative) or an inline
    "About us:" prefix → decline.
  - Any qualification clause → admit.
  - Else any non-qualification clause → decline.
  - A neutral claim beginning with a bare duty verb inside a REQUIRED/PREFERRED section
    → decline.
  - Everything else → admit, which is the v13 behaviour.
- **Never declined merely for lacking a qualification frame.** Bare lists and prose
  survive.
- **Purity.** The decision is pure and deterministic. It uses only the claim text and
  its section kind, plus concept recognition for the technology-as-subject shape. It
  never reads candidate evidence.
- **Duty-verb pattern.** The duty-verb regex is a byte-identical copy of the shadow
  path's `_RESPONSIBILITY_LEAD`. Importing it would create an import cycle
  (`competency_extraction` → `qualification` → `parser`). A test pins the two
  patterns as equal.

**Necessity refinement** (`necessity.refine_necessity`). It only narrows a necessity,
and is tested separately from admission.

- `None` stays `None`.
- A concession ("While not required, X is a plus") → PREFERRED.
- A negated REQUIRED marker with no other un-negated REQUIRED marker → PREFERRED if a
  preference cue is present, otherwise `None` (no row).
- REQUIRED plus a soft cue ("would be great", "is beneficial", "helps", "appreciated",
  "desirable") with no un-negated REQUIRED marker → PREFERRED.
- Explicit REQUIRED and PREFERRED, and section inheritance, are otherwise unchanged.
- `infer_necessity` itself is unchanged, so the shadow competency path that also calls
  it is unaffected.

## 2. Red → green

`tests/test_m11g21_qualification_intent.py` holds 79 focused tests, written before the
parser was wired. **27 were red on v13** and pass on v14:

- the v14 version label;
- team narrative;
- "You will be required to deploy services to AWS…";
- narrative inside a qualifications section;
- a misleading "Role requirements" heading;
- a duty/qualification mixed bullet;
- technology discussion;
- G17-053;
- G18-25;
- concessive negation;
- 14 near-neighbour narrative members;
- the section-leak paragraph;
- API diagnostic visibility;
- necessity through the parser;
- the module-hygiene test.

**52 were green guards on v13 and stay green.** They cover:

- explicit, "you must have" and preferred qualifications;
- unconventional "Must-haves:" headings;
- bare lists, including unsectioned ones;
- prose qualifications and inherited list necessity;
- mixed postings;
- exact spans;
- the "US" case;
- the duty-pattern pin;
- the necessity unit tests.

The set grows to **90** with 11 comparison-backed tests.

**Characterized, not hidden:**

- "You must be on call during weekends." produces no requirement in v13 or v14: it is
  never even a claim.
- The G20 held-out case h003, "You must be on call … for our AWS infrastructure.", is
  **still admitted** as REQUIRED AWS. "You must" is the same strong shape as "you must
  have". A dedicated test asserts this known limitation. It is not an xfail.

## 3. G20 frozen controls — actual v13 versus v14 production code

| Metric | Dev v13 | Dev v14 | Held-out v13 | Held-out v14 |
|---|---|---|---|---|
| False admissions (non-qualification units) | 26 / 45 | **0** / 45 | 16 / 18 | **1** / 18 (h003) |
| False REQUIRED rows | 33 | 0 | 19 | 1 |
| PREFERRED marked REQUIRED | 3 | 0 | 2 | 0 |
| False SUPPORTED, counted (all-evidence candidate) | 30 | 0 | 18 | 1 |
| Necessity accuracy | 43 / 46 | **46 / 46** | 17 / 19 | **19 / 19** |
| Near-neighbour pairs correct | 2 / 12 | **12 / 12** | 0 / 4 | **4 / 4** |
| Unit precision | 0.653 | 1.0 | 0.568 | 0.955 |
| Unit recall | 0.836 | 0.836 | 0.704 | 0.704 |
| Genuine qualifications lost | — | 0 | — | 0 |
| Fabricated concepts (G22 scope) | 6 | 6 | 4 | 4 |

**Research adapter versus live code.** There is **no divergence.**

- The v13 clone reproduces G20's frozen v13 aggregates exactly.
- Live v14 reproduces G20's frozen B1NR research aggregates exactly, on both sets.

A v14 test asserts the second point.

## 4. Fresh adversarial validation (newly authored synthetic, not independent)

`evaluation/m11g21/adversarial_controls.json` has 35 controls and 43 units. Its gold was
written and frozen before v14 or the comparison ran on it (sha256 `2cae574e…08d1`). It
covers:

- hiring-process obligations;
- on-call and incident duties;
- attendance and travel;
- "required to perform" versus "required to know";
- U.S./US capitalisation;
- negated requirements and preferences;
- compound qualifications;
- bare lists;
- company descriptions;
- mixed paragraphs.

It was written by the same author after B1NR was known, and I did not tune on it.

| | v13 | v14 |
|---|---|---|
| False admissions | 17 / 21 | **11** / 21 |
| Genuine qualifications lost vs v13 | — | **2** |
| Necessity accuracy (admitted qualifications) | 18 / 20 | 18 / 18 |
| Near-neighbour pairs | 0 / 2 | 0 / 2 |
| Source-span errors | 0 | 0 |
| Scores changed / became undefined (all-evidence) | — | 8 / 7 |

**Still falsely admitted (11):**

- hiring-process obligations with a strong subject (a01 "Applicants must complete…",
  a03 "Candidates will be asked…");
- duty imperatives outside the closed verb list (a04 "Participate…", a06 "Respond…");
- obligations phrased as "is mandatory / is required" without an attribute (a08, a09,
  a11b);
- "You are required to deploy…" (a10b);
- company sentences without a We/Our/The-team subject (a17 "Join us…", a27
  "Founded in 2012, Lumen Labs…", a28 "Every team here…").

**Lost (v13 represented them, v14 declines them visibly):**

- a19 "A degree is not required; strong Python skills are." The whole-claim negation
  frame overrides the qualification clause.
- a20 "TypeScript is preferred but not essential." "preferred but not" is not in the
  appreciative-tail vocabulary.

Both were **real regressions of the evaluated B1NR design**. Option B (§4b) corrects them.

## 4b. Option B — clause-local negation scope (revised v14)

**Root causes:**

1. **a19 "A degree is not required; strong Python skills are."**
   - `claim_role()` evaluated the negation frame on the **whole claim** before any clause
     analysis, so the existing `;` split never got a chance.
   - The negated clause even scored as a qualification on its own: the "required" marker
     sits next to the attribute "degree".
   - `refine_necessity()` was also claim-level. It saw "not required", no other REQUIRED
     marker and no preference cue, and returned `None`.
   - Even if the claim had been admitted, the detectors read the whole claim, so the
     degree would have become a REQUIRED education row.
2. **a20 "TypeScript is preferred but not essential."** "not essential" fired the
   whole-claim negation. The appreciative-tail patterns only cover "but … appreciated / a
   plus / helpful …" and "helpful / a plus … but not", not "preferred … but not". The same
   gap declined "Python is optional but desirable.", because its subjectless continuation
   "desirable." never lent a preference to "Python is optional".

**Correction** (narrow; no new vocabulary, no sentence-specific exception):

- **Units.** Clauses are split on the existing separators. A clause introduced by "but"
  that has no subject of its own ("not essential", "desirable", "appreciated") joins the
  clause it completes. A `;` always starts a new unit.
- **Negation is per unit.** A unit containing a requirement negation is negated unless it
  expresses optionality. Optionality means a concession, the existing appreciative tail,
  or a merged continuation carrying the existing preference vocabulary.
- **Masking.** When another unit is a qualification, each negated unit is replaced by
  spaces (same length) in a `scoped_text`. The parser runs every detector and necessity
  step on that scoped text. Each row keeps the whole claim's original text and exact span.
  When nothing is negated, the scoped text *is* the claim text, so behaviour is
  byte-identical to the first port.
- **No qualification unit.** If no unit is a qualification, a negated unit declines the
  claim, as before.
- **Ellipsis — exactly one case.** A unit with its own subject that ends in a bare copula,
  directly after a unit that explicitly negates a predicate ("is not
  required / essential / mandatory / necessary / needed / preferred"), re-uses that
  predicate positively. `refine_necessity(scoped, necessity, full_text=claim)` resolves it
  to REQUIRED, or to PREFERRED for "preferred". "X are." alone never resolves.

**Diff added by the correction:**

- `qualification_intent.py`: unit construction, per-unit negation, masking, and
  `scoped_text` on the internal decision record.
- `necessity.py`: `NEGATED_PREDICATE`, `ELLIPTICAL_CONTRAST`, `has_preference_cue()`
  (the existing cue set), and the `full_text` parameter.
- `parser.py`: one `text = decision.scoped_text or claim.text`, used by the necessity
  steps and the detectors.

The `parser.py` substitution goes beyond the two files Option B listed. It is the only way
to keep the masked clause's own content out of the rows: the degree row comes from the
non-technical detector reading the whole claim. It is a substitution inside the same
function, not an architecture change, and it is inert whenever nothing is negated.

**Results with real production code** (`v13_v14_revised_comparison.json`):

| Set | v13 | First v14 | Revised v14 |
|---|---|---|---|
| Adversarial (35, now development data): false admissions | 17 / 21 | 11 / 21 | **11 / 21** |
| … genuine qualifications lost vs v13 | — | 2 (a19, a20) | **0** |
| … necessity correct | 18 / 20 | 18 / 18 | **20 / 20** |
| … unit recall | 0.952 | 0.857 | **0.952** |
| … source-span errors | 0 | 0 | 0 |
| G20 dev: false admissions / necessity / pairs | 26, 43/46, 2/12 | 0, 46/46, 12/12 | **identical to first v14** |
| G20 held-out: false admissions / necessity / pairs | 16, 17/19, 0/4 | 1, 19/19, 4/4 | **identical to first v14** |
| Historical corpora, all scored fixtures, G17 guard, private counts | — | (§5–§6) | **identical to first v14** |

**Revised v14 against G20's frozen B1NR research aggregates:** still exactly equal on dev
and held-out. No G20 control contains a clause-scoped negation, so this is expected.

**New author-created examples** (`negation_scope_controls.json`): 16 controls, expected
rows written and frozen (`04114d47…bbda`) before the revision existed. Same author, so
**not an independent holdout.** v13 gets 4/16 exactly right and revised v14 gets 14/16.

- **Failing exactly as pre-flagged** (`expected_limitation`):
  - n07 "No prior Rust experience is necessary, but strong C++ skills are." — the
    negation vocabulary needs "no prior *experience/knowledge*" directly.
  - n16 "Strong SQL skills are required; Docker knowledge is preferred." — necessity is
    per claim. Per-clause necessity needs per-conjunct rows (G16 decomposition territory).
- **One prediction was wrong in the favourable direction:** n10 "React knowledge is
  welcome though not essential." was flagged as a likely limitation but passes, through
  the existing concession pattern.

**Focused red tests** (written before the correction): 8 red on the first v14, all green
now. They cover:

- the two regressions;
- "A degree is not required; Python experience is required.";
- "Python is preferred, but not required.";
- "Python is optional but desirable.";
- provenance of the masked claim;
- the ellipsis restrictions;
- optionality never promoting to REQUIRED.

Green guards cover "A degree is not required; Python is used by our team.",
"Python experience is not required.", "Python is not required and is not considered.",
"You must be on call during weekends." and "Our team prefers TypeScript for internal
projects.". "Experience with Java is required; Python is preferred." is characterized
explicitly: both are admitted, but Python is REQUIRED because necessity is per claim.

## 5. Historical compatibility (real v13 vs v14)

| Corpus | Rows removed / added | Necessity changed | Newly declined | Gold fixed | Gold regressed |
|---|---|---|---|---|---|
| G16 (58) | 1 / 0 | 0 | 1 | **053** | 0 |
| G18 (26) | 3 / 0 | 0 | 1 | **25** | 0 |
| G15, M10D, M10E, G6, G7, 8c jobs, M10 SOTI / Manulife | 0 / 0 | 0 | 0 | — | 0 |

- **G17 guard:** all 46 G16 controls still admitted keep byte-identical alternative or
  placeholder rows. 0 violations.
- **G19 eligibility:** on every kept row, in every scored corpus, the match status,
  `counts_toward_alignment` and exclusion reason are identical.
- **No new false SUPPORTED** anywhere.
- **No whole qualification section is suppressed.**
- **G6 candidate-profile headings are unchanged.** "About you" and "What you bring"
  remain G23 scope.

**Version-aware test updates.** In every updated test, v13 checks are kept intact under a
v13 branch, and the v14 branch asserts the exact, enumerated delta. No gold was changed.

- **Version-literal tests** (m11a2, m11b, m11c, m11e, G17, G19 API, G20) now track v14.
- **G15 report:** no change under v14.
- **G16 report:** exactly 053, which goes from REQUIRED placeholder to declined; it was
  never scored.
- **G18 report:** exactly control 25 and its aggregates.
- **G17 option-D test:** exactly 053.
- **G19 live = G18 policy C:** exactly 25/python_docker, which becomes undefined. The two
  remaining uncheckable rows (both control 25) become 0.
- **G20:** the v13-behaviour pins have a v14 branch, and the v13 report-reproduction test
  under v14 must equal the frozen B1NR aggregate.
- **M11-A2 m11a2-unicode-03, an enumerated divergence asserted exactly:**
  - the unwrapped "We’ve built our platform on Go and PostgreSQL…" is now declined;
  - the wrapped variant splits at the curly apostrophe, a pre-existing A2 segmentation
    limitation, so its fragment stays admitted exactly as in v13.
- **G20 evaluator:** now refuses to run on a non-v13 parser, so it cannot overwrite the
  frozen v13 research outputs.

## 6. User-visible impact (v13 → v14)

**Scored candidate fixtures:**

| Fixture set | Outcomes | Σ numerator v13→v14 | Σ denominator v13→v14 | Score changed | Became undefined | Status / eligibility changed on kept rows |
|---|---|---|---|---|---|---|
| G15 | 35 | 13 → 13 | 19 → 19 | 0 | 0 | 0 |
| G16 | 414 | 146 → 146 | 300 → 300 | 0 | 0 | 0 |
| G18 | 54 | 28 → 26 | 52 → 50 | 1 | 1 (25/python_docker: 2/2 = 100 → 0/0 undefined) | 0 |
| Frozen 8c v1 / v1.1 | 12 / 12 | 26 → 26 (each) | 44 → 44 (each) | 0 | 0 | 0 |
| M10 | 2 | 0 → 0 | 1 → 1 | 0 | 0 | 0 |

**G20 synthetic controls, all-evidence candidate:** scores or denominators change on
23 dev and 13 held-out controls. Of these, 20 and 12 move to undefined, because the
only rows were false admissions.

**Specific cases:**

- **G17-053:** it was a REQUIRED `alternative_requirement` placeholder, never scored.
  It is now an UnparsedClaim, with the score unchanged (undefined).
- **G18-25:** REQUIRED Python and Docker rows plus `unresolved:terraform` used to give
  100 (2/2). Now there is no row, and the score is undefined.

**Private postings** (62, previously inspected; counts only):

| | v13 | v14 |
|---|---|---|
| JobRequirements | 379 | 378 |
| REQUIRED / PREFERRED rows | 311 / 68 | 308 / 70 |
| UnparsedClaims | 697 | 698 |
| v2 denominator rows | 71 | 71 |
| Postings with no eligible requirement | 28 | 28 |

- **Changes:** 3 postings changed; none lost all its rows.
- **Label-backed (651 annotations, 650 located; not independent validation):**
  - false admissions unchanged at 4 / 153 (none of them scored);
  - qualifications admitted 242 / 497 → 242 / 497 (**0 lost**);
  - necessity correct 231 → 233 / 242;
  - PREFERRED marked REQUIRED 7 → 5.

  This is exactly G20's post-hoc B1NR prediction.

## 7. Diagnostics and spans

- Every declined claim is an `UnparsedClaim` whose text equals
  `raw[start:end]`. It is serialised in `AnalyzeResponse.unparsed_claims` and counted
  in `unparsed_claim_count`, which a test checks through the real API serializer.
- Every v14 row's `original_text` equals its source span, across all controls and
  corpora (0 span errors).
- No new type or field was added.

## 8. Verification

- **Backend suite:** 2229 passed, 5 failed, 13 skipped, 18 xfailed (revised v14; the first
  port was 2211 passed). The 5 failures are
  the HEAD-identity guards — G13, G15, G16 and G18 "production unchanged", plus G20
  "src equals HEAD" — which assert `git diff --quiet HEAD -- src`. They cannot pass
  until the change is committed, the same pattern as G19. The 13 skips are identical to
  the baseline, and all 18 xfails are preserved.
- **Frontend:** 53/53 (the API is unchanged).
- **Inputs:** no LLM, no network.
- **Privacy:**
  - private outputs are integer counts only, enforced by a test;
  - no private text appears in the tracked G21 artifacts.

## 9. Remaining known failures and recommended next steps

1. **h003-style duties with a strong subject** ("You must be on call…", "Applicants
   must complete…", "You are required to deploy…").
2. **Duty verbs outside the closed list, and obligations phrased "X is mandatory".**
3. **Company sentences without a We/Our/The-team subject.**
4. **Negation-scope residuals** (after the §4b correction): "No prior <tech>
   experience is necessary" (n07), and per-clause necessity inside one sentence (n16).
   The original a19/a20 losses are corrected.
5. **Accepted existing limitation — clause-level necessity.**
   "Experience with Java is required; Python is preferred." Both are admitted, but
   **Python is still REQUIRED**: necessity is decided per claim, not per clause. This was
   accepted at the G21 commit; fixing it needs per-conjunct rows and is out of G21's scope.
6. **G22 / G23 scope:** fabricated concepts (G22) and candidate-profile headings (G23).
7. **Wrapped curly-apostrophe contractions** (A2 segmentation).

## 10. Changed files

- **Production:**
  - `src/gitscore/jobs/parsing/qualification_intent.py` (new)
  - `src/gitscore/jobs/parsing/necessity.py`
  - `src/gitscore/jobs/parsing/parser.py`
- **Tests:**
  - `tests/test_m11g21_qualification_intent.py` (new)
  - version-aware updates to `test_m11a2_line_wrap_integrity.py`,
    `test_m11b_qualification_model.py`, `test_m11c_competency_extraction.py`,
    `test_m11e_paraphrase_extraction.py`, `test_m11g15_*`, `test_m11g16_*`,
    `test_m11g17_*`, `test_m11g18_*`, `test_m11g19_*` and `test_m11g20_*`
- **Scripts:**
  - `scripts/evaluate_m11g21_v13_v14.py` (new)
  - `scripts/evaluation_lib/m11g21_parser_dump.py` (new)
  - `scripts/evaluation_lib/m11g21_build_adversarial.py` (new)
  - `scripts/evaluation_lib/m11g21_build_negation_scope.py` (new, Option B)
  - `scripts/evaluate_m11g20_false_qualification.py` (v13-only guard)
- **Evaluation:** `evaluation/m11g21/`
  - `adversarial_controls.json`
  - `adversarial_hash_freeze.json`
  - `v13_v14_comparison.json`, `private_v13_v14_aggregates.json` (first v14, preserved;
    reproducible through `first_v14_reverse.patch`)
  - `first_v14_reverse.patch` (revised → first-v14 production sources, evaluation input
    only)
  - `negation_scope_controls.json`, `negation_scope_hash_freeze.json` (Option B)
  - `v13_v14_revised_comparison.json`, `private_v13_v14_revised_aggregates.json`
    (revised v14)
- **Docs:**
  - this file
  - `docs/ARCHITECTURE.md`
  - `docs/PIPELINE.md`
  - `docs/CHANGELOG_DEV.md`
