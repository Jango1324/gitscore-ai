# Milestone 11-G22-S2 — Concept occurrence overlap correction

**Status:** narrow production fix implemented and verified; **uncommitted**.

- **What changed:** README extractor `readme:v5` → **`readme:v6` = the independent-occurrence overlap correction on
  top of v5's setext handling**.
- **What did not change:**
  - no README guard policy (G22-R2 D, R3, P4, D_S), attribution guard, homonym lexicon or corroboration
    requirement;
  - no new alias.
- **Other components unchanged:**
  - parser `job_description_parser:v15`;
  - scoring `github_evidence_alignment:v2`;
  - matcher `requirement_matcher:v1`;
  - registry version 4;
  - the shared `select_longest_overlapping_matches()`;
  - the job parser, repository ranking, the manifest, language and Docker extractors, the evidence schema, API and
    frontend.

## 1. Baseline

- **Git:** HEAD `4c6277a106f6c7d2be04e934af73f81c7add62a6` (G22-S1, pushed) equals `origin/main`.
- **Versions:** v15 / v2 / v1 / `readme:v5` / registry 4.
- **Tests:** backend 2550 passed, 13 skipped, 18 xfailed; frontend 53 passed.
- **Freezes:** 27 G14 freezes, all verifying.
- **Working tree:** the 18 private/untracked M11 entries are present.

## 2. Root cause: trace through the real extractor

The primary example is `"A React Native app. The web dashboard uses React."`.

| Step | Observation |
|---|---|
| Raw alias matches | `framework.react` `'react'` at (2,7) "React" (inside "React Native"); `framework.react` `'react'` at (43,48) "React"; `framework.react_native` `'react native'` at (2,14) "React Native". None is excluded by the 8D.3 context rules |
| Per-concept selection (`readme.py`, v5) | for each concept, the first alias with a non-excluded occurrence, and **only that alias's FIRST such occurrence**: React → (2,7); React Native → (2,14) |
| Overlap resolution (`select_longest_overlapping_matches`, 8D.1) | (2,7) is shadowed by the strictly longer (2,14) → dropped |
| Surviving evidence | `framework.react_native` only. **React's independent occurrence at (43,48) was never a candidate** |
| Job parser on the same text | `find_concept_mentions` → React Native (2,14) **and** React (43,48): it collects every occurrence before overlap resolution |
| MatchStatus / score (v5) | a probe "Experience with React." is `not_observed` → numerator 0 (G22-R5 DEV dev-035: **missed**) |

**Precise location:** `src/gitscore/evidence/extraction/readme.py`, `evidence_from_readme()`'s selection loop. The
shared overlap function is correct, and its other callers (`jobs/parsing/concepts.py`,
`ranking/job_relevance.py`) already feed it every occurrence. No shared-scanner, job-parser, registry or matcher
change was required.

**Registry facts:**

- **Cross-concept containment:** the only one is `react` ⊂ `react native` / `react-native` (`framework.react` vs
  `framework.react_native`).
- **Same-concept containments:**
  - shell ⊂ shell script;
  - psycopg2 ⊂ psycopg2-binary;
  - react ⊂ react.js;
  - express ⊂ express.js;
  - nestjs ⊂ @nestjs;
  - prisma ⊂ @prisma.
- **Non-overlaps:** "javascript" does not contain the word "java", and "pytorch" does not contain "torch". There is
  no Docker Compose concept.

## 3. Semantics

- **Same-position overlap (different concepts):** the strictly longer alias wins, which is the existing 8D.1 rule.
  "React" inside "React Native" is never React evidence, whether or not the React Native mention itself is excluded
  by context.
- **Accepted v5 → v6 difference at the same position (Gate 1 decision):** the 8D.3 following-cue window starts at
  a match's *end*, so "React" (5 characters) and "React Native" (12 characters) at one position look at windows
  offset by 7 characters. With the cue in that 7-character tail, for example
  `"A React Native client. " + 21×"y" + " and it is not supported."`, v5 excluded the React Native mention but
  emitted **React** evidence from the "React" inside it. Its only source was the words "React Native", so it was
  incorrect. v6 emits neither React nor React Native there, and a separate valid "React" later in the README is
  still recovered. Verified against genuine `4c6277a` (v5) and the working tree (v6). The plain
  "React Native is not supported." gives nothing under either version. React/React Native is the registry's only
  cross-concept containment, so this is the whole scope. None of the measured G22 or 8c inputs contain this pattern
  (§7–§8 are unchanged). The 60-character window itself is unchanged. Pinned by four tests in §5.
- **Independent occurrences:** an overlap at position A never suppresses an occurrence at position B. Selection
  skips the covered occurrence and **keeps scanning** that alias, then the concept's next alias.
- **Same-concept overlaps** ("react" inside "React.js"): unchanged. The existing alias order still decides which
  alias labels the item.
- **Equal-length overlaps:** never shadow each other, as in 8D.1.
- **Unchanged:** 8D.3 section and negation exclusions (including the 60-character adjacency window), S1 setext
  sections, fall-through, one item per concept per repository, MODERATE confidence, snippets and file path.

## 4. Production diff (`readme.py` only)

- `all_occurrences`: every (start, end, concept) for every README-safe alias, computed once per README.
- New `_inside_longer_other_concept_match(start, end, concept_id, all_occurrences)`: true iff a different concept's
  occurrence overlaps and is strictly longer.
- In the selection loop, `continue` past such an occurrence, before the unchanged exclusion check.
- `EXTRACTOR_VERSION = "readme:v6"`, with a docstring defining v6.
- The final 8D.1 overlap pass is kept, unchanged.

**No other file in `src/` changed.**

## 5. Red → green

The tests are in `tests/test_m11g22s2_occurrence_overlap.py`. They were written before the production change and
run against committed `readme:v5`.

| | Result |
|---|---|
| Against `readme:v5` | **12 failed, 26 passed of 38** |
| After the fix | **38/38**, plus 4 pin and comparison tests added afterwards: **42 passed** |
| After the Gate 1 decision | 6 regression tests added for the negated React Native case (§3): **48 passed** |

**Red against v5:**

- React Native → React (primary);
- distinct paragraphs;
- separate ATX sections;
- around a setext heading;
- "React-Native … uses React";
- multiple valid mentions;
- provenance of the recovered item;
- LF/CRLF (×3);
- "every README-safe alias after a React Native mention";
- version.

**Green against v5, and still green:**

- React → React Native;
- React Native alone; React alone;
- repeated React;
- same-position longer alias (×3);
- "React … React Native" placement;
- same-concept alias precedence (×4);
- different concepts;
- Java/JavaScript, Docker/Docker Compose, PyTorch/torch, Express/Express.js;
- excluded → valid; valid → excluded;
- negated → explicit use (×2);
- repeated React Native never invents React;
- the new negation-window characterisation;
- ATX/setext exclusions (×2);
- every alias in a plain context.

**One expectation corrected before implementation.** As first written, the requirement-19 case "We do not use React
Native. The web app uses React." expected React. The **existing** 8D.3 negation cue ("do not use") lies within the
60-character lookback of the later "React" too, so that occurrence is excluded under v5 *and* under the intended v6.
That rule is explicitly preserved. The case now places the explicit use beyond the window, and a separate test pins
the near case as still excluded. This corrects an expectation that contradicted a preserved rule; it is not a
weakening.

## 6. Historical compatibility

**The pins:**

- **`scripts/evaluation_lib/readme_v5_pin.py` (new):** reproduces committed `readme:v5` exactly by replacing the v6
  predicate with one that never skips, and labelling evidence `readme:v5`.
- **`scripts/evaluation_lib/readme_v4_pin.py`:** from v6, it first applies the v5 pin, then the ATX-only heading
  index.
- **Behaviour:** both restore state on normal exit and on exceptions. Valid nestings (v4 inside v5, v4 inside v4,
  v5 inside v5) are safe. A v5 pin inside an active v4 pin is refused with an error, since it would be incoherent,
  and still leaks no state.

**Exactness checks against genuine code:**

| Pin | Reference | Result |
|---|---|---|
| v5 | a disposable checkout of `4c6277a` | identical on every measurement (all eight labelled sets, G22-R controls, every 8c evidence item including snippets and version labels, both 8c matrices, G19 capability) |
| v4 (from v6) | the dump from genuine `9502676` | identical on every measurement |

**Tests:**

- The G22-S1 test module now runs pinned to v5 (measured `EXTRACTOR_VERSION`, autouse fixture), with all S1
  assertions verbatim.
- The five G22 research modules keep their v4 pin.
- One assertion I added in S1 (R3: production ∈ {v4, v5}) now also admits v6.
- The 8D.3 version-pin test asserts `readme:v6`, with its history comment extended.

**Runners:** the S1 comparison runner's comparison path runs pinned to v5. Its `--dump` mode still measures the
current environment.

**Reproduction under v6 with pins:** see §9.

## 7. Real-pipeline comparison (`readme:v5` pinned vs `readme:v6`)

The comparison runs the real pipeline under each version: README extractor, aggregation, matcher v1 and scoring v2.
It is written to `evaluation/m11g22s2/occurrence_overlap_comparison.json` by
`scripts/evaluate_m11g22s2_occurrence_overlap.py`.

| Set | Recovered | Newly excluded | Provenance moved | MatchStatus changes | False SUPPORTED | True SUPPORTED |
|---|---|---|---|---|---|---|
| G22-R2 DEV / EVAL | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 21 → 21 / 18 → 18 | 20 → 20 / 19 → 19 |
| G22-R3 VAL-1 / VAL-2 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 35 → 35 / 24 → 24 | 36 → 36 / 24 → 24 |
| G22-R4 DEV / fresh | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 29 → 29 / 42 → 42 | 29 → 29 / 50 → 50 |
| **G22-R5 DEV** | **1** | 0 | 0 | **1** | 23 → 23 | **24 → 25** |
| G22-R5 fresh | 0 | 0 | 0 | 0 | 52 → 52 | 42 → 42 |
| G22-R controls | no README evidence change | | | | | |

**The one change:** dev-035, `"A React Native mobile app. The web dashboard uses React."`. React is recovered and the
probe goes from missed to **true SUPPORTED**.

- **Truth source:** the frozen R5 DEV label (written before S2) is React = use, and React is in `used`. That truth is
  independent of this implementation, though the label is policy-author-written.
- **Provenance:** the recovered item's snippet is the genuine "… uses React" occurrence.
- **Unchanged:** false SUPPORTED did not change anywhere, no new false SUPPORTED appeared, no genuine evidence was
  lost, and no score became undefined.

## 8. Frozen 8c and G19

- **8c evidence and scores:** **zero changes**. No evidence item, provenance, MatchStatus, numerator, denominator or
  score changed in either matrix version, and no score became undefined. torvalds/systems_cpp_01 **remains 67**;
  torvalds/libgit2 and sindresorhus/Gifski are unchanged.
- **React occurrences in 8c:**

  | Repository | React mentions | React Native mentions |
  |---|---|---|
  | jango1324/Jango1324 | 2 | 0 |
  | karpathy/llm-council | 2 (repeated in prose) | 0 |
  | sindresorhus/ky | 1 | 0 |

  v5 and v6 both give `framework.react` there, so the fixtures never exercise the defect.
- **G19:** capability is identical for all 39 concepts. All 64 README-safe aliases are extracted, including after a
  preceding React Native mention (red under v5 for `react`).

## 9. Verification

- **Tests:**
  - S2 tests 48/48 (42 + the 6 Gate 1 regression tests); S1 tests 59/59 (pinned to v5);
  - G22-R..R5 research tests pass, with no skips;
  - full backend suite and frontend: see the final report and changelog.
- **Source-vs-HEAD identity checks:** G13, G15, G16, G18 and G20 assert `git diff --quiet HEAD -- src` and fail
  before commit only, as in S1. They were verified in a disposable committed checkout.
- **Historical reports, regenerated under v6 with pins:**
  - G22-R, R2, R3 and R5 public reports and all five private aggregates: byte-identical;
  - G22-R4 report: differs only in the documented `freezes.historical_manifest` count (25 → 27), which already exists
    at S1's parent;
  - G22-S1 comparison report: byte-identical (under the v5 pin).
- **Freezes and history:** 27/27 freezes unchanged and verified; no frozen control, gold file or report rewritten.

## 10. Remaining limitations

- The 8D.3 adjacency window (60 characters, crossing sentences) can still exclude an independent mention near a
  negated one. This is unchanged by design and pinned by a test.
- If two different-concept aliases of **equal** length ever overlapped, both would survive. That is 8D.1's
  conservative choice, and it cannot occur in the current registry.
- The shadow check scans every occurrence of every alias once per README. Its cost is negligible at README sizes,
  but it is quadratic in the number of occurrences.
- **Not addressed:**
  - ordinary-English homonyms;
  - attribution phrasing;
  - level-aware section inheritance.

## 11. Rollback

Revert `readme.py` (the predicate, the `all_occurrences` list, the `continue` and the version string) together with
the S2 test, the version-pin test line and the S1 test module's pin header.

- **The pins are harmless:** under v5, `readme_v5_pin` is a no-op and `readme_v4_pin` behaves as it did in S1.
- **Data:** no data, schema or API change, so no migration.

## 12. Files

**Production (1):** `src/gitscore/evidence/extraction/readme.py`.

**Tests:**

- New: `tests/test_m11g22s2_occurrence_overlap.py` (48).
- `tests/test_evidence_extraction_readme.py` (version pin v6).
- `tests/test_m11g22s1_setext_heading_boundaries.py` (explicit v5 pin).
- `tests/test_m11g22r3_readme_context_guard.py` (admits v6 in the S1-added assertion).

**Research tooling:**

- New: `scripts/evaluation_lib/readme_v5_pin.py`, `scripts/evaluate_m11g22s2_occurrence_overlap.py`,
  `evaluation/m11g22s2/occurrence_overlap_comparison.json`.
- `scripts/evaluation_lib/readme_v4_pin.py` (composes with the v5 pin).
- `scripts/evaluate_m11g22s1_setext_boundaries.py` (comparison path pinned to v5).

**Docs:**

- this file;
- `docs/CHANGELOG_DEV.md`;
- `docs/ARCHITECTURE.md` (§25.2 correction);
- `docs/PIPELINE.md`.
