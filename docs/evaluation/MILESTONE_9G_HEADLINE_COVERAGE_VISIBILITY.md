# Milestone 9G — Headline Coverage Visibility

**Status: implemented, frontend-only.** No file under `src/gitscore/`
was modified — no matcher, scoring formula, concept registry, parser
semantics, retrieval behavior, API schema, or serialization logic was
touched. No frozen gold under `evaluation/gold/`, `evaluation/gold_v1_1/`,
or `evaluation/m9b/` was modified. No new backend field was added. Not
committed, not pushed. Technical-competency detection (M9F's Option B)
was not started.

---

## 1. Approved M9F decisions, as implemented

| # | M9F question | Decision | How this milestone honors it |
|---|---|---|---|
| Q1 | Approve presentation-only coverage disclosure (Option C)? | **Approved**, no `has_coverage_gap` API field | The known-gap boolean is derived entirely in the frontend from two fields the API already returns (`assessment.uninterpreted_requirement_count`, `assessment.unparsed_claim_count`) — see §3 |
| Q2 | Scope Option B's evaluation work separately? | **Approved for a separate, future, evaluation-only milestone** | No detector, no vocabulary, no new parser signal was written or even prototyped this milestone |
| Q3 | Formally reject Option A (unconditional preservation)? | **Rejected** | Untouched — `jobs/parsing/parser.py` is byte-for-byte unchanged; the rejection is recorded here and in `MILESTONE_9F_REQUIREMENT_COVERAGE_DESIGN.md` §9 |

---

## 2. Baseline (Phase 0)

| Check | Result |
|---|---|
| HEAD at start | `46d591a` ("docs: evaluate requirement coverage and score validity" — M9F) |
| Working tree | clean |
| `python -m pytest` | **934 passed**, 0 failed (matches the expected baseline exactly) |
| `cd frontend && npx vitest run` | **36 passed** (matches the expected baseline exactly) |

Read before implementation: `docs/evaluation/MILESTONE_9F_REQUIREMENT_COVERAGE_DESIGN.md`,
`docs/evaluation/MILESTONE_9E_ASSESSMENT_CLARITY.md`,
`docs/evaluation/MILESTONE_9D_PRODUCT_VALIDATION.md`,
`frontend/src/components/{AlignmentHeadline,ResultView}.tsx`,
`frontend/src/lib/labels.ts`, `frontend/src/types/api.ts`,
`frontend/src/test/fixtures.ts`,
`frontend/src/components/__tests__/ResultView.test.tsx`,
`frontend/src/app/globals.css`.

---

## 3. Why no new API field was added

`Assessment.uninterpreted_requirement_count` (M9C) and
`Assessment.unparsed_claim_count` (M9E) are already sufficient to derive
the one boolean this feature needs — "does a known coverage gap exist
at all." Both are already guaranteed mutually exclusive per source
claim (a claim is counted by at most one of them, never both —
established by M9E's own `test_unparsed_claim_count_and_uninterpreted_requirement_count_never_overlap`),
so a plain boolean OR of the two never double-counts the same
underlying gap:

```ts
export function hasKnownCoverageGap(uninterpretedCount: number, unparsedClaimCount: number): boolean {
  return uninterpretedCount > 0 || unparsedClaimCount > 0;
}
```

The one piece of information this feature ALSO needs that is not a
count — the actual verbatim text of an unparsed claim, to show a
concrete example — is already present on `AnalyzeResponse.unparsed_claims[].text`
(M9C). No field anywhere was added, renamed, or retyped; `Assessment`,
`AnalyzeResponse`, and `RequirementOut` are byte-for-byte unchanged.
Per M9F §8.4's own conclusion, this reuse was possible specifically
because this milestone implements ONLY the presentation half of Option
C — the small, optional `has_coverage_gap`-style field M9F flagged as
"the only open question" was deliberately not added, per this
milestone's own explicit instruction.

---

## 4. Exact display logic

### 4.1 `lib/labels.ts` (new, additive exports)

- `hasKnownCoverageGap(uninterpretedCount, unparsedClaimCount): boolean`
  — §3 above.
- `KNOWN_COVERAGE_GAP_LABEL = "Known coverage gaps"` — the badge text.
  Deliberately never "Incorrect"/"Invalid"/"Unreliable"/"Unqualified"
  (per this milestone's explicit constraint).
- `coverageGapSummary(): string` — a fixed, generic sentence ("This
  score excludes job-description text GitScore could not interpret.")
  shown whenever `hasKnownCoverageGap()` is true, REGARDLESS of which
  kind of gap it is or whether concrete claim text is available to
  quote.
- `coverageGapExample(claims: UnparsedClaim[]): string | null` — `null`
  when `claims` is empty (never fabricates an example); otherwise names
  the FIRST claim's verbatim text (truncated at 140 characters with a
  trailing `…` for very long claims — the untruncated original remains
  fully visible, unchanged, in `UnparsedClaimsSection` further down the
  page) plus a plain `(+N more — see below)` suffix when more than one
  claim exists, rather than listing every diagnostic in the headline.

### 4.2 `AlignmentHeadline.tsx`

New optional prop `unparsedClaims: UnparsedClaim[] = []`, used ONLY by
`coverageGapExample()` — the boolean "is there a gap at all" decision
is made entirely from the two existing counts, never from this array's
length. Rendering, in order, whenever `hasKnownCoverageGap()` is true:

1. A `<span className="coverage-gap-badge">Known coverage gaps</span>`
   inside the SAME paragraph as the score (or "Not available") — so the
   badge sits visibly beside the number, not in a separate block a
   reader could miss.
2. `coverageGapSummary()`'s sentence, always.
3. `coverageGapExample()`'s sentence, only when non-`null`.
4. The pre-existing, byte-for-byte unchanged `uninterpretedCaveat()`
   and `unparsedClaimsCaveat()` paragraphs, exactly as before this
   milestone (see §6 for why these were deliberately kept, not
   replaced).

When `hasKnownCoverageGap()` is false, **nothing new renders at all** —
no badge, no summary, no "Complete"/"Fully analyzed"/"100% requirements
interpreted" affirmation of any kind (M9F §5.4's own conclusion: absence
of a known diagnostic is not proof of exhaustive parsing, so the
product must never claim it is).

### 4.3 `ResultView.tsx`

One new line: `result.unparsed_claims` is now also passed into
`AlignmentHeadline` (it was already being passed, unchanged, into
`UnparsedClaimsSection`) — the exact same array read twice for two
different purposes, never a second fetch, never a duplicated backend
field.

### 4.4 `globals.css`

`.alignment-value` gained `display: flex; flex-wrap: wrap; gap: 0.5rem`
so the number, the "/ 100" scale, and the badge wrap naturally on
narrow viewports instead of overflowing. `.coverage-gap-badge` is a
small, muted-amber pill (reusing the EXISTING `--color-warning-bg`/
`--color-warning-border` tokens already used for the diagnostics
panel's non-alarming warning — no new color introduced).
`.alignment-coverage-gap-example` uses `overflow-wrap: break-word` so a
long quoted claim never overflows its container on a narrow screen.

---

## 5. Before / after headline examples

### 5.1 No known gap (unchanged from M9E)

```
GitHub Evidence Alignment
40 / 100
```
No badge, no new text — identical to pre-M9G rendering.

### 5.2 `karpathy × computer_vision_01` — live-verified real values (required 3/3, preferred 1/1, one unparsed claim: "Experience with OpenCV for image processing")

**Before this milestone:**
```
GitHub Evidence Alignment
100 / 100
```
(plus the required/preferred subscores below, unchanged) — **zero**
visible indication anything was uncertain, because
`uninterpreted_requirement_count` is `0` for this exact posting (no
placeholder row exists) and the pre-9G headline had no mechanism to
react to `unparsed_claim_count` beyond the M9E caveat sentence.

**After this milestone:**
```
GitHub Evidence Alignment
100 / 100  [Known coverage gaps]
This score excludes job-description text GitScore could not interpret.
Potential requirement not interpreted: "Experience with OpenCV for image processing"
1 additional statement in the job posting could not be parsed as a requirement at all -- see below.
```
The `100` itself is byte-identical before and after (confirmed by test
#10, §7) — only the surrounding presentation changed. OpenCV is now
named directly at the headline, not just discoverable by scrolling to
`UnparsedClaimsSection`.

### 5.3 Both kinds of gap present (synthetic example, for clarity)

```
GitHub Evidence Alignment
60 / 100  [Known coverage gaps]
This score excludes job-description text GitScore could not interpret.
Potential requirement not interpreted: "First unparsed statement" (+1 more -- see below)
1 requirement could not be confidently interpreted by GitScore's parser -- see below.
2 additional statements in the job posting could not be parsed as a requirement at all -- see below.
```
Exactly ONE badge, even though both `uninterpreted_requirement_count`
and `unparsed_claim_count` are non-zero — confirmed by test #3 (§7).

---

## 6. Why the two pre-existing M9C/M9E caveats were kept, not replaced

This milestone's badge/summary/example are presentational ADDITIONS,
not replacements, for three reasons:

1. **This milestone's own constraint E** ("Preserve... existing
   requirement diagnostics") — the two existing caveat sentences are
   exactly that.
2. **The two existing counts remain the only PRECISE numbers** — the
   new summary/example sentences are deliberately generic/single-example;
   a reader who wants the exact count of either category still needs
   the existing sentences, which the badge/summary do not duplicate or
   subsume.
3. **Avoiding information loss**: `coverageGapSummary()` fires for
   EITHER gap kind identically, so it alone cannot tell a reader which
   kind(s) exist or how many — only the pre-existing, category-specific
   sentences can.

---

## 7. Tests and build results

| Suite | Before M9G | After M9G |
|---|---|---|
| `cd frontend && npx vitest run` | 36 passed | **46 passed** (36 + 10 new, all in `ResultView.test.tsx`) |
| `cd frontend && npm run type-check` | clean | clean, 0 errors |
| `cd frontend && npm run build` | succeeds | succeeds (Next.js production build) |
| `python -m pytest` | 934 passed | **934 passed** (unchanged — no backend file touched) |
| `git diff --check` | — | clean (only pre-existing CRLF-normalization notices) |

### 7.1 The ten regression scenarios (§F of the milestone brief), each pinned by its own test

1. High alignment with an unparsed claim — `karpathy × computer_vision_01`'s real, live-verified values (§5.2).
2. High alignment with only an uninterpreted placeholder (no unparsed-claim text) — confirms the example line correctly does NOT render when there is nothing real to quote.
3. Both kinds of gaps present simultaneously — confirms exactly one badge, both pre-existing caveats intact.
4. No detected gaps — confirms zero new text renders, and explicitly asserts the absence of "Complete"/"Fully analyzed"/"100% requirements interpreted" anywhere in the section.
5. Zero assessable requirements (`alignment === null`) with a known gap — confirms the badge renders beside "Not available," not only beside a numeric score.
6. Multiple (4) unparsed claims — confirms only the first is named, with an accurate "+3 more" count, and the other three's text is absent from the headline.
7. A deliberately very long claim (>140 characters) — confirms headline truncation (with `…`) while the full, untruncated text remains verbatim in `UnparsedClaimsSection`.
8. `AlignmentHeadline` rendered with no coverage-gap props at all (simulating missing/empty diagnostics) — confirms no crash and no false-positive badge.
9. No invented requirement-criticality — confirms neither the excerpt nor the badge text ever contains "required" or "critical" (`UnparsedClaim` structurally carries no necessity to classify with in the first place).
10. The alignment score's own numeric value (`"100"`) is identical whether or not a coverage gap is present.

---

## 8. Known limitations

- **Browser click-through not completed this session.** The offline-
  fixture backend (`scripts/m9d_serve_offline_fixture.py karpathy`) and
  the Next.js dev server were both started and confirmed listening
  (`curl` 200/`{"status":"ok"}`), but this session's Chrome browser-
  automation tool did not respond (`tabs_context_mcp` timed out,
  consistent with an unanswered extension-side permission prompt) — the
  same limitation M9D's and M9E's own sessions hit. Per this
  milestone's own instruction, this did not block the milestone;
  verification instead relies on (a) the exact, live-captured real
  `karpathy` fixture values reproduced as an offline test fixture (test
  #1), (b) 10 passing React Testing Library tests asserting exact
  rendered DOM text/structure, and (c) a clean TypeScript type-check and
  production build. Actual rendered visual appearance (badge color
  contrast, wrapping behavior on a real narrow viewport, font
  rendering) remains unverified by direct observation.
- **The badge/summary cannot distinguish REQUIRED from PREFERRED gaps.**
  `UnparsedClaim` carries no necessity field at all (by construction —
  necessity is computed by `infer_necessity()`, which is never reached
  for a claim producing zero rows), so neither the badge nor the
  example sentence can say whether the missed claim was required or
  preferred. This is an accurate reflection of what the data actually
  contains, not an oversight — inventing a necessity here would violate
  this milestone's own "do not classify as required/critical unless
  independently available" constraint.
- **The qualified-headline sub-option (e.g. "100 — based on 4 of 5
  extracted requirements") was NOT implemented.** M9F §5.4 listed this
  as a stronger disclosure option alongside the badge; this milestone
  implements the badge + named-excerpt combination only, per the scope
  given. Could be revisited in a future milestone if the (not yet run)
  human pilot indicates the badge alone is insufficiently noticed.
- **The M9D human pilot still has not been run.** Both of its named
  task materials (`karpathy × computer_vision_01`,
  `torvalds × sre_platform_01`) now render with the new badge — a
  pilot run after this milestone would see different screens than the
  protocol's own internal observer notes describe.
- **Technical-competency detection (M9F Q2) was not started**, per this
  milestone's explicit instruction — the 23% silent-drop rate itself
  remains exactly as measured in M9B, unreduced.

---

## 9. Recommendation for the human pilot

Run `docs/evaluation/M9D_HUMAN_PILOT_PROTOCOL.md` against the CURRENT
(post-9G) UI, not the pre-9G screens its own internal notes describe.
Specifically:

- **Task 1** (`karpathy × computer_vision_01`, interpreting a high
  score) now shows the "Known coverage gaps" badge and names OpenCV
  directly at the headline — re-run this task to see whether the badge
  changes whether participants still over-trust the 100, directly
  extending the task's existing over-trust check (§7 of M9D's
  protocol) with a sharper, more falsifiable question: does seeing
  "Known coverage gaps" next to a 100 change what a participant says
  about their confidence, compared to M9D's own pre-9G session notes
  (never run, but the protocol's internal observer guidance assumed a
  bare, unqualified 100).
- **Task 4** (`torvalds × sre_platform_01`, headline-completeness
  check) is substantially less relevant to its ORIGINAL purpose now —
  the specific gap it was designed to surface (the headline caveat
  undercounting real interpretive uncertainty) was already fixed in
  M9E, and this milestone adds a THIRD, even more prominent signal.
  Consider replacing Task 4's question with a more targeted one: "Does
  the 'Known coverage gaps' badge draw your attention before you form
  an opinion of the score?"
- Add one new open-ended question to §C (the questionnaire): "Did the
  'Known coverage gaps' label change how much you trusted the number
  next to it? If so, how?" — this is the single most direct way to
  learn whether this milestone's actual product goal (making a
  known-incomplete analysis visibly different from a complete one) was
  achieved, versus merely asserted in this report.

---

## Final verification

```
cd frontend
npx vitest run         -> 46 passed
npm run type-check     -> clean, 0 errors
npm run build          -> succeeds
cd ..
python -m pytest       -> 934 passed, 0 failed (unchanged)
git diff --check       -> clean
git status --short     -> 5 modified frontend files (AlignmentHeadline.tsx,
                           ResultView.tsx, labels.ts, globals.css,
                           ResultView.test.tsx) + 2 new/modified doc files
git diff --stat        -> 373 insertions(+), 3 deletions(-) across the 5
                           frontend files; no file under src/gitscore/ touched
```

**No production backend code, frozen gold, API contract, or
requirement/matching/scoring semantics was modified.**

**DO NOT COMMIT. DO NOT PUSH. Technical-competency detection (M9F Q2)
was not started.**
