# Milestone 11-G22-S1 — Setext heading section boundaries

**Status:** narrow structural fix implemented and verified; **uncommitted**.

- **What changed:** README extractor `readme:v4` → **`readme:v5` = setext heading boundary correction ONLY**.
- **What did not change:** `readme:v5` does **not** implement any README guard policy researched and rejected in
  G22-R..R5 (D, R3, P4, D_S).
- **Other components unchanged:**
  - parser `job_description_parser:v15`;
  - scoring `github_evidence_alignment:v2`;
  - matcher `requirement_matcher:v1`;
  - registry version 4;
  - the language, manifest and Docker extractors;
  - API schema and frontend.

## 1. Baseline

- **Git:** HEAD `95026764ddbcc7af2a2ce2c3fbbdcf1bba5ba3ce` (G22-R5 research commit, already pushed) equals
  `origin/main`.
- **Freezes:** the G14 manifest has 27 entries, all verifying.
- **Tests:** backend 2491 passed, 13 skipped, 18 xfailed; frontend 53 passed.
- **Working tree:** the 18 private/untracked M11 entries are present.

## 2. Root cause

**Where:** `src/gitscore/evidence/extraction/readme_context.py`, `_heading_spans()`. This is the heading index behind
`ReadmeContext.enclosing_heading()`, which the 8D.3 section denylist uses
(`is_non_implementation_mention`: a mention under a heading such as "related projects", "notable forks" or
"acknowledgements" is not attributed to the repository).

**Why it failed:** `_heading_spans()` matched only ATX headings (`^#{1,6}\s+…`). A setext heading was invisible.

| Input | `readme:v4` behaviour |
|---|---|
| `## Related projects` … then `Development` / `-----------` … `Our implementation uses Python.` | "development" never started a section, so the genuine Python mention stayed inside "related projects" and was discarded |
| `Related projects` / `================` … `- ripgrep (Rust)` | the excluded section was not recognised, so the other project's Rust became evidence |

## 3. Correct section semantics

**Section rule, unchanged:** a section runs from its heading to the next heading of **any** level. The nearest
preceding heading wins.

**Setext headings (CommonMark):**

- **Definition:** a paragraph of one or more non-blank text lines immediately followed by an underline of `=` (H1)
  or `-` (H2). The underline is indented at most three spaces and has only trailing whitespace after it.
- **Section start:** the heading starts at its first text line. Multi-line heading text is joined with single
  spaces, then normalised exactly like ATX text (emphasis stripped, trailing colon dropped, lower-cased, whitespace
  collapsed).

**Not a heading:**

- `---`, `***`, `___` or `- - -` after a blank line (a thematic break);
- `---` or `===` after a list item or blockquote, or after their lazy continuation lines;
- an underline separated from its text by a blank line;
- an underline indented by four or more spaces;
- anything inside a fenced code block (the same fence spans the ATX index already uses).

**Untouched:** the denylist, the adjacency cues, fall-through to the next occurrence or alias, overlap resolution and
one-item-per-concept deduplication. No new attribution heuristic was added.

## 4. Production diff

**`readme_context.py`:**

- The old `_heading_spans()` was renamed `_atx_heading_spans()`, with its body unchanged (the literal v4 index).
- New `_setext_heading_spans()`: a single line scan with three small regexes (underline, non-paragraph block start,
  thematic break) plus the existing fence spans. Text is never modified; a trailing `\r` is ignored only for
  matching, so LF and CRLF give identical results.
- `_heading_spans()` returns both lists merged in document order.

**`readme.py`:** `EXTRACTOR_VERSION = "readme:v5"`, plus a docstring stating that v5 is the setext fix only.

**Nothing else in `src/` changed.**

## 5. Red → green tests

The tests are in `tests/test_m11g22s1_setext_heading_boundaries.py`. They were written **before** the production
change and run against `readme:v4` first.

| | Result |
|---|---|
| Against `readme:v4` | **22 red, 34 green** of the 56 initial tests. Red: every setext-heading case and the version pin. Green: existing ATX exclusions, thematic breaks, list-item/blockquote dashes, fenced headings, blank-line and four-space cases, valid-then-invalid ordering, and CRLF/LF equality (trivially equal under v4) |
| After the fix | 56/56 green, plus 3 tests added afterwards (v4 pin, recorded comparison, comparison reproducibility): **59 passed** |

**Covered:**

1. Setext H1 (`===`) and H2 (`---`), including one-character and indented underlines.
2. ATX `## Related projects` followed by setext Development.
3. Setext Related projects followed by ATX Development.
4. Genuine-sounding text inside excluded sections stays excluded (ATX and setext).
5. Recovery after an excluded section.
6. Consecutive setext headings.
7. Thematic breaks (`---`, `***`, `___`, `- - -`, long dashes) are not headings.
8. Dashes or equals after a list item or blockquote are not underlines.
9. A blank line between the text and the underline breaks the heading.
10. A four-space-indented underline is not an underline.
11. `---`, `===`, `#` and `##` inside fenced code are ignored.
12. A setext heading after a closed fence is recognised.
13. Extra blank lines.
14. Mixed ATX and setext levels.
15. Multi-line setext text.
16. Emphasis, colon and whitespace normalisation.
17. The original snippet and file path are preserved.
18. All 13 existing denylisted ATX headings are still excluded.
19. ATX-only documents keep the same index.
20. Invalid-then-valid and valid-then-invalid occurrences are handled independently.
21. CRLF and LF give the same sections and evidence.
22. Deduplication, with no unrelated concepts.
23. Heading text itself never becomes evidence.
24. The version is `readme:v5`.

## 6. Historical compatibility: explicit `readme:v4` pin

**The problem.** The G22-R..R5 research measured `readme:v4`. Under v5, their tests would have **skipped** (24 tests
gated on `EXTRACTOR_VERSION == "readme:v4"`) or failed (4), and their runners refuse to run.

**The pin.** `scripts/evaluation_lib/readme_v4_pin.py` restores v4 exactly inside a `with` block: production's
unchanged `_atx_heading_spans()` serves as the heading index, and evidence is labelled `readme:v4`. Nothing in `src/`
imports it.

**Proof that the pin is exact.** A disposable checkout of the previous HEAD (genuine v4 code) and the pinned current
tree produce identical measurements on:

- all eight labelled G22 control sets;
- the G22-R controls;
- every 8c evidence item, including snippets and version labels;
- the 8c matrices;
- G19 capability.

**Historical tests.** Each of the five G22 research test modules:

- imports production's version under a private name;
- defines `EXTRACTOR_VERSION` as the **measured** version (`readme:v4`, via the pin);
- runs every test pinned (an autouse fixture).

All historical assertions are kept verbatim. G22-R3's `test_readme_v5_was_not_implemented` gained a note: G22-R3's
"readme:v5" meant the R3 guard (never implemented), while today's v5 is this setext fix.

**Historical runners.** In the five G22 runners, `main()` became `_main()`, wrapped in the pin, and the reported
`readme_extractor` is the measured `readme:v4`. Policy and harness modules hash-pinned by the research design freezes
are **not** modified, and their freeze verifications still pass.

**Existing version pin.** `tests/test_evidence_extraction_readme.py::test_extractor_version_bumped_for_8d3` now
asserts `readme:v5`. A comment records the history: 8D.3's v3 → v4, and G22-S1's v4 → v5.

**Report reproduction under v5 + pin:**

- **Byte-identical:** the public reports of G22-R, G22-R2, G22-R3 and G22-R5, and all five private aggregates.
- **G22-R4's report:** identical except `freezes.historical_manifest.entries` and `.verified` (25 → 27). This comes
  from the **G22-R5 registration** (commit `9502676`), not from S1. It is the limitation G22-R4 already documented,
  and the reason G22-R5's report omits manifest state. All measured sections reproduce, and the committed R4 report
  is untouched.

## 7. Real-pipeline comparison (`readme:v4` vs `readme:v5`)

The comparison runs the real pipeline under each version: README extractor, evidence aggregation, matcher v1 and
scoring v2. It is written to `evaluation/m11g22s1/setext_boundary_comparison.json` by
`scripts/evaluate_m11g22s1_setext_boundaries.py`.

| Set | Evidence recovered | Newly excluded | Provenance moved | MatchStatus changes | False SUPPORTED v4 → v5 | True SUPPORTED v4 → v5 |
|---|---|---|---|---|---|---|
| G22-R2 DEV / EVAL | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 21 → 21 / 18 → 18 | 20 → 20 / 19 → 19 |
| G22-R3 VAL-1 / VAL-2 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 35 → 35 / 24 → 24 | 36 → 36 / 24 → 24 |
| G22-R4 DEV / fresh | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 29 → 29 / 42 → 42 | 29 → 29 / 50 → 50 |
| **G22-R5 DEV** | **1** | **1** | **1** | **2** | **24 → 23** | **23 → 24** |
| **G22-R5 fresh** | 0 | 0 | **1** | 0 | 52 → 52 | 42 → 42 |
| G22-R controls | no README evidence change | | | | | |

**Every change was inspected:**

- **dev-037** (ATX "Related projects", then setext "Development: written in Rust"): Rust is **recovered**, and the
  probe goes from missed to **true SUPPORTED**. The genuine evidence v4 lost.
- **dev-038** (setext-only "Related projects / ripgrep (Rust)"): Rust is **newly excluded**, and the probe goes from
  false SUPPORTED to **correctly not supported**.
- **dev-036:** the Rust evidence **moves** from the "ripgrep (Rust)" reference to "This tool is written in Rust"
  (same status).
- **fresh r5-078** (author-labelled): Kotlin evidence **moves** from "a Kotlin server template by another author"
  under a setext `Related Projects` to "`budget-cli` … written in Kotlin" (same SUPPORTED status, correct provenance).

**Not every changed score is assumed to be a correction.** Each of these was checked against its label:

- two are policy-author DEV labels;
- one is a separately authored fresh label.

**No genuine evidence was lost** on any set. No new false SUPPORTED appeared, and no score became undefined.

## 8. Historical 8c impact

The frozen 8c fixtures show **zero** changes:

- no README item added, removed or moved;
- no MatchStatus, numerator, denominator or score change in either matrix version (`8c_v1`, `8c_v1_1`);
- no undefined-score change.

**Repositories examined:**

- **torvalds/libgit2:** its setext headings ("Using libgit2", "Quick Start", …) end no denylisted section, so the
  third-party bindings list stays evidence exactly as in v4.
- **The libgit2 Python test-framework mention:** unchanged.
- **sindresorhus/Gifski Rust:** unchanged.
- **torvalds/systems_cpp_01:** **remains 67**.
- **torvalds/linux** and **libdc-for-dirk:** setext headings, but none denylisted.
- **karpathy/llm.c:** its two setext-shaped lines after "## notable forks" are not underlined paragraphs under
  CommonMark, so the section is unchanged.

## 9. G19 capability and job side

- **G19 capability** is identical for all 39 concepts. All 64 README-safe aliases are still extracted (the research
  capability contracts pass under the pin and in production).
- **Job parsing** is untouched: no job-side code changed.

## 10. Remaining limitations

- Level-aware section inheritance is not implemented; the nearest heading still wins (G22-R5 §3).
- YAML front matter (`---` … `---` at the top of a file) follows plain CommonMark: its closing `---` underlines the
  preceding line. This was not observed in any fixture.
- Fence detection is unchanged: only column-0 ` ``` ` fences, as in v4. Indented or `~~~` fences are not treated as
  code by the heading index, which is the same behaviour ATX headings already had.
- **Not fixed:**
  - the 8D.1 overlap loss ("React Native" then "uses React");
  - ordinary-English homonyms;
  - attribution phrasing.
- A future manifest registration will again change G22-R4's manifest-count field (pre-existing, §6).

## 11. Rollback

Revert the two production files (`readme_context.py`, `readme.py`). The v4 heading index is the unchanged
`_atx_heading_spans()`, so the rollback is a version string plus one function body. Then revert the version-pin test
and the S1 tests.

- **The pin and the historical test/runner changes are harmless under v4:** `pinned()` is a no-op when production is
  already v4.
- **Data:** no stored data, schema or API changes, so no migration.

## 12. Files

**Production (2):**

- `src/gitscore/evidence/extraction/readme_context.py`
- `src/gitscore/evidence/extraction/readme.py`

**Tests:**

- New: `tests/test_m11g22s1_setext_heading_boundaries.py` (59).
- Updated version pin: `tests/test_evidence_extraction_readme.py`.
- Explicit v4 pin: `tests/test_m11g22r_ambiguous_alias_evidence.py`, `tests/test_m11g22r2_readme_evidence_context.py`,
  `tests/test_m11g22r3_readme_context_guard.py`, `tests/test_m11g22r4_high_recall_readme_guard.py`,
  `tests/test_m11g22r5_attribution_readme.py`.

**Research tooling:**

- New: `scripts/evaluation_lib/readme_v4_pin.py`, `scripts/evaluate_m11g22s1_setext_boundaries.py`,
  `evaluation/m11g22s1/setext_boundary_comparison.json`.
- Runner pins: `scripts/evaluate_m11g22r_alias_evidence.py`, `scripts/evaluate_m11g22r2_readme_context.py`,
  `scripts/evaluate_m11g22r3_readme_guard.py`, `scripts/evaluate_m11g22r4_high_recall_guard.py`,
  `scripts/evaluate_m11g22r5_attribution_readme.py`.

**Docs:**

- this file;
- `docs/CHANGELOG_DEV.md`;
- `docs/ARCHITECTURE.md` (the setext limitation marked resolved; v5 wording);
- `docs/PIPELINE.md`.
