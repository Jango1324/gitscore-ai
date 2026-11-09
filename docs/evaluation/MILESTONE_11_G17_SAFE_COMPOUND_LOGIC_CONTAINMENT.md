# Milestone 11-G17 — Safe Compound-Logic Containment (parser v13)

Status: **narrow production change implemented and verified. Not
committed.**

- Production logic changed in **one file**, `src/gitscore/jobs/parsing/alternatives.py`.
  `src/gitscore/jobs/parsing/parser.py` changed only its version label
  (v12 → v13).
- **Unchanged:** the matcher, scoring formula, `SCORING_VERSION`,
  `JobRequirement`, `MatchStatus`, public schemas, API, frontend, G10–G13
  implementations, frozen gold and freezes.
- **Not implemented:** G15 Policy B and G16 Option C (decomposition).
- No LLM call.

## The production defect

Under v12 the parser flattened mixed AND/OR qualifications into **one OR
group**. Examples:

- "Docker or Kubernetes, and Python" → OR(Docker, Kubernetes, Python)
- "Python and either Docker or Kubernetes"
- "Python or Go, and Docker or Kubernetes"
- "at least two of …"

Any single alternative could then satisfy a requirement whose mandatory
conjunct was missing. G16 measured **106 of 414** claim-level false
SUPPORTED outcomes on its frozen controls.

**Earliest irreversible loss:** `alternatives.py`.
`_split_alternative_segments` splits on every "or" and every comma, and
`_resolve_segment` returns all concepts in a segment. The resulting
`AlternativeClaim` is a flat tuple. M10D documented this as "Root Cause 6"
and deferred it.

## The implemented guard (option D as evaluated in G16)

`alternatives.py` gains `is_structurally_mixed(text, registry)` and
`_contain_mixed()`, applied to the result of both `classify_alternative_claim`
paths (the explicit any-of trigger and the bare "or" path).

A `technical` (flat OR) result is returned as `unsafe` when the claim is
**structurally** mixed. Each signal is structural, never a bare keyword
anywhere in the claim:

1. an OR segment resolves to **two or more distinct concepts** ("Java and
   SQL", "Kubernetes; Python");
2. a comma item **begins** with a conjunction (", and Python", ", plus
   AWS", ", as well as …");
3. a cardinality of two or more ("at least two of …"), or a "both" /
   "all of" lead-in.

`unsafe` routes the claim to the parser's **existing** 6B.1 fallback. No
new parser path, model or field was added.

**The decline pathway (user decision for G17).** Requirement 8 of the
brief ("declined claims do not become JobRequirements") conflicted with
"option D as evaluated" and the authorized file scope. The decision was to
use the existing fallback, so requirement 8 is enforced as *never a
scoreable JobRequirement*. A declined claim is a placeholder row with:

- `category="alternative_requirement"`
- no concept and no alternatives
- PARTIALLY_OBSERVABLE, therefore always **NOT_ASSESSABLE**
- **never in the alignment denominator**
- shown by the API as `interpretation_status="unparsed_placeholder"`
  (counted in `uninterpreted_requirement_count`)
- its exact original text, source span and stated necessity kept

**Why decline, not decompose.** Decomposition (option C) is not
authorized. Declining is the only change that removes the false SUPPORTED
without inventing a reading the parser cannot verify.

## Red → green regression tests (written before the change)

`tests/test_m11g17_compound_logic_containment.py`. Before the production
edit, **10 tests failed against v12** and the 6 behaviour-preservation
tests passed. After the edit, **18 / 18 pass**:

| # | Pinned behaviour | v12 | v13 |
|---|---|---|---|
| 1 | (A∨B)∧C not satisfied by C alone | ✗ | ✓ |
| 2 | A∧(B∨C) not satisfied by A alone | ✗ | ✓ |
| 3 | (A∨B)∧(C∨D) never a flat OR | ✗ | ✓ |
| 4 | Simple A∨B still SUPPORTED | ✓ | ✓ |
| 5 | Simple A∧B unchanged (1/2 → 50) | ✓ | ✓ |
| 6 | Ambiguous precedence declines | ✗ | ✓ |
| 7 | Declined claim keeps exact text and span | ✓ | ✓ |
| 8 | Declined claim never scoreable (NOT_ASSESSABLE) | ✗ | ✓ |
| 9 | Declined claim excluded from denominator; unrelated row still scored | ✗ | ✓ |
| 10 | Necessity kept: REQUIRED stays REQUIRED, PREFERRED stays PREFERRED | ✗ ×2 | ✓ |
| 10b | UNKNOWN necessity stays an UnparsedClaim, never REQUIRED | ✓ | ✓ |
| 11 | Company narrative still produces no requirement | ✓ | ✓ |
| 12 | Unrelated qualifications in the same job stay assessable | ✓ | ✓ |
| — | Parser version is v13 | ✗ | ✓ |
| — | Declined placeholder visible as `unparsed_placeholder` in the API | (new) | ✓ |
| — | No declined claim re-enters scoring via another row | (new) | ✓ |
| — | **Live parser equals G16's simulated option-D rows on all 58 controls** | ✗ | ✓ |

## Actual v12 vs v13 results (real code, nothing simulated)

`scripts/evaluate_m11g17_v12_v13.py` runs the **real committed v12
parser** in a throwaway clone of HEAD and the v13 working tree, through
the same real matcher and assessor, over identical corpora. Output:
`evaluation/m11g17/v12_v13_comparison.json`.

**G16's 414 deterministic evidence scenarios (58 frozen controls):**

| | v12 | v13 |
|---|---|---|
| Claim-level false SUPPORTED | **106 / 414** | **7 / 414** |
| False SUPPORTED eliminated | — | **99** |
| New false SUPPORTED introduced | — | **0** |
| Genuine compound claims declined | 2 / 43 | **24 / 43** (22 newly declined + 2 already declined in v12) |
| Genuinely satisfied outcomes no longer scored (recall cost) | — | 77 |
| Fixture outcomes with a changed denominator or score | — | 238 |
| Fixture outcomes scored **more favourably** in v13 | — | **0** |
| Rows across the 58 controls | 76 | 76 |
| …scoreable rows | 73 | 42 |
| …non-scoreable `alternative_requirement` placeholders | 2 | 33 |
| UnparsedClaims | 3 | 3 (unchanged) |

- **31 controls newly declined:** 22 representable genuine compound
  claims, 8 the gold expects to be declined (unrepresentable or
  ambiguous), and 1 responsibility sentence (053).
- **Simulation vs implementation:** the achieved result **equals** G16's
  simulation of option D exactly. A test asserts the live v13 production
  results, per control and per fixture, equal the frozen report's option-D
  results, and that the metrics match.

**Other corpora:**

| Corpus | Change |
|---|---|
| G15 OR-scoring controls (19) | only **K1** changes. Its flattened OR(Docker, Kubernetes, Python) is now a placeholder, so the v12 false SUPPORTED for "Python only" (100) is gone (no score). |
| Frozen 8c:v1 and 8c:v1.1 (12 pairs each) | **0** pairs change (scores, denominators, row counts identical) |
| SOTI / Manulife (M10 tracked sources) | **identical** rows |
| Private postings (inspected, not independent, counts only) | M11-D 0/12, M11-F **1/18** (+1 placeholder, −1 scoreable row), M11-G5 0/18, M11-G9 0/14 |

**User-visible effect:**

- A newly declined claim appears in the not-assessable list as an
  `unparsed_placeholder`, with its text and necessity.
- `uninterpreted_requirement_count` rises by one per declined claim.
- The alignment score no longer counts it. The score is never made more
  favourable by v13; it either drops or becomes `None` when nothing else
  is assessable.

## Residual false SUPPORTED (exactly 7, not fixed by design)

| Root cause | Controls | Count |
|---|---|---|
| Mixed-kind comma/OR list with no conjunction ("Python, Docker or Kubernetes") | 043 | 4 |
| Bare "Go" unrecognised in prose, so the segment looks single-concept | 018 | 3 |

## Historical evaluation preservation

The frozen G15 and G16 research reports describe **v12**. They were not
regenerated or rewritten. Test expectations changed only where v13
legitimately changes behaviour:

| Test | Change | Why |
|---|---|---|
| `test_m10d…::test_m10d_corpus_control_e1/e2_mixed_and_or_stays_safe_not_fabricating` | assert `unsafe` with no concepts (was: the flattened 3-way group) | M10D deliberately pinned the v12 flattening "so a future change … is a deliberate decision". G17 is that decision, and the M10D controls' own frozen annotation already names `unsupported_mixed` as the conservative fallback. |
| `test_m11g15…` `report` fixture + `test_report_is_reproducible` | fixture loads the frozen v12 report; reproducibility becomes an explicit v12-vs-v13 comparison | Under v13 a live re-run may differ **only** on K1, which must now be contained; all other controls and the 8c re-score must be identical. |
| `test_m11g16…` `report` fixture + `test_report_is_reproducible` | fixture loads the frozen v12 report; reproducibility asserts live v13 production = frozen option-D results on all 58 controls and identical metrics | The frozen G16 report simulated option D on v12; v13 *is* option D. |
| `test_m11a2…`, `test_m11b…`, `test_m11c…`, `test_m11e…` parser-version assertions | literal v12 → v13, with comment | These tests track the current version; their purpose (their own milestone didn't change it) is unaffected. Same convention as the G6/G7 bumps. |

No test was deleted or skipped.

**Correction to G16's regression probe.** G16 predicted that only the 2
G15 tests would break. It missed the 2 M10D tests because its in-memory
probe rebound only the *parser's* reference to `classify_alternative_claim`,
while these M10D tests call the function directly. The production change
in `alternatives.py` reaches every caller.

**"Production unchanged since HEAD" guards.** These are
`test_m11g13…::test_g10_g11_g12_and_production_unchanged` and the G15 and
G16 `test_no_production_change_and_no_production_import`. They assert
`git diff HEAD -- src` is empty, so they fail on **any uncommitted**
`src/` change, and pass again once that change is committed. They are
left unchanged. Verified in post-commit-equivalent clean checkouts (see
Verification).

## Remaining known limitations (explicitly unresolved)

1. "Python, Docker or Kubernetes" mixed-list ambiguity (043).
2. Bare "Go" vocabulary recognition (018).
3. "At least two of" without "or" is scored as all-required AND rows
   (037). Only the "or" form is contained.
4. "One of:" sub-list segmentation produces all-required rows (028).
5. Cross-sentence "Alternatively" yields a fabricated
   `unresolved:alternatively` (058).
6. Responsibilities misclassified as qualifications (053 is now
   incidentally declined, not correctly classified). Its placeholder is
   user-visible as `not_assessable` / `unparsed_placeholder` with the exact
   sentence, but still labelled `required` -- the necessity v12 already
   assigned (v12 *scored* it as a REQUIRED 3-way OR). G17 adds no new
   necessity; the row is merely no longer scored.
7. G15 mixed-observability OR scoring (Policy B not implemented).
8. G15 standalone unassessable technology requirements.

## Future decomposition requirements (option C, not approved)

Decomposition would restore faithful scoring (38/43 exact in G16) with no
schema, matcher or scorer change. It needs:

- per-conjunct rows emitted from `_requirements_from_claim`, with
  per-conjunct necessity from the production `infer_necessity`;
- an absorption rule for duplicates ((D∨K)∧D → D);
- prior narrative / responsibility handling (residual 6), so that a
  responsibility sentence is not re-scored;
- a parser version bump.

## Verification

- **G17:** 18 passed.
- **G16:** 20 passed (versioned). **G15:** 12 passed (versioned), except
  the HEAD guard noted above. **G14:** 124 passed. **G13:** 15 passed,
  12 xfailed, except its HEAD guard.
- **G6 / G7:** pass. **M10D:** 60 passed.
- **M10A–E, M11-A1 / A2 / B / C / E, matching, assessment, evaluation
  harness:** pass.
- **Full backend suite (working tree, uncommitted):** **2029 passed, 3
  failed, 13 skipped, 18 xfailed** (2014 + 18 G17 tests). The 3 failures
  are exactly the three HEAD-relative production guards. **0 behaviour
  failures.**
- **Post-commit-equivalent clean checkouts** (HEAD plus every G17 change
  committed in a throwaway clone):

  | | `autocrlf=true` | `autocrlf=false` |
  |---|---|---|
  | Full suite | **2008 passed, 37 skipped, 18 xfailed, 0 failed** | **2008 passed, 37 skipped, 18 xfailed, 0 failed** |
  | Historical freeze verifiers | 11 / 11 pass | 11 / 11 pass |

  The three guards pass there. The 37 skips are private-dataset tests
  (13 in the full environment). Native Linux/macOS was not run.
- Frozen gold, freezes and the G14 manifest are unchanged (10 entries).
  No new freeze record exists.
- Privacy: the committed-candidate artifacts contain synthetic text,
  tracked fixtures and counts only.

## Changed-file inventory (uncommitted)

**Production (approved scope):**

- `src/gitscore/jobs/parsing/alternatives.py` (guard plus docstring)
- `src/gitscore/jobs/parsing/parser.py` (version label only)

**Tests:**

- `tests/test_m11g17_compound_logic_containment.py` (new)
- `tests/test_m10d_alternative_requirement_semantics.py`
- `tests/test_m11g15_mixed_observability_or_scoring.py`
- `tests/test_m11g16_compound_requirement_logic.py`
- `tests/test_m11a2_line_wrap_integrity.py`
- `tests/test_m11b_qualification_model.py`
- `tests/test_m11c_competency_extraction.py`
- `tests/test_m11e_paraphrase_extraction.py`

**Evaluation (new):**

- `scripts/evaluation_lib/m11g17_parse_dump.py`
- `scripts/evaluate_m11g17_v12_v13.py`
- `evaluation/m11g17/v12_v13_comparison.json`
- `evaluation/m11g17/private_v12_v13_aggregates.json` (counts only)

**Docs:**

- `docs/evaluation/MILESTONE_11_G17_SAFE_COMPOUND_LOGIC_CONTAINMENT.md`
  (new)
- `docs/ARCHITECTURE.md`, `docs/PIPELINE.md`, `docs/CHANGELOG_DEV.md`

## Commit-readiness verdict

Ready for review; **not committed or pushed**, as instructed. G18 has not
started.
