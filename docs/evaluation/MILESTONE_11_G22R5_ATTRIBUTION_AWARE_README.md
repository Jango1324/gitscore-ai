# Milestone 11-G22-R5 — Attribution-aware README evidence research

**Status:** research and evaluation only; **`readme:v5` was NOT implemented**.

- **Result:** the frozen attribution-only candidate D_S kept every genuine README use on a fresh held-out set and
  changed nothing outside attribution. It reduced attribution-specific false SUPPORTED by only **20%** (49 → 39),
  failing its frozen ≥ 50% gate (G8). The failure is preserved, and the candidate is not recommended.
- **Production unchanged:**
  - parser `job_description_parser:v15`;
  - scoring `github_evidence_alignment:v2`;
  - matcher `requirement_matcher:v1`;
  - README extractor `readme:v4`;
  - registry version 4.
- `src/`, `frontend/`, registry data and historical gold are unchanged. No LLM is called anywhere in the evaluation.
- **Freezes:** the 25 previously registered G14 freezes verify, unchanged.
- **Research accepted and committed** as a research-only commit ("test: evaluate README attribution guard
  limitations") after authorization. D_S's failure of gate G8 is final, and D_S is not approved for production.
  - The R5 DEV and fresh control sets are registered in the G14 manifest at that commit with their original
    freeze-time hashes (25 → 27; the previous 25 are unchanged field for field).
  - The policy-design freeze is a provenance record (no `frozen_file`), so it is not a registered control set.
  - Freeze records keep their freeze-time "NOT registered … pending authorization" note.
- **Kinds of evidence, kept distinct throughout:**
  - seen design data (every earlier control set, 8c, R5 DEV);
  - one frozen held-out set from a separately instructed AI author (not human-independent);
  - post-hoc diagnostics, run after the held-out run;
  - simulated 8c score effects;
  - actual production behaviour.

## 1. Baseline and reproduction (Phases 0–1)

- **Git:** HEAD `39b570c83b09cb62db49d664fcae062ae9731c02` on `main`, equal to `origin/main`.
- **Versions:** v15 / v2 / v1 / `readme:v4` / registry 4.
- **Tests:** backend 2462 passed, 13 skipped, 18 xfailed; frontend 53 passed.
- **Freezes:** 25 manifest entries, and all verify.
- **Working tree:** the 18 private/untracked M11 entries are present.
- **Earlier reports reproduce.** The committed G22-R2, G22-R3 and G22-R4 public reports were regenerated in memory and
  are byte-identical.
- **G22-R4 confirmed:**
  - P4 false SUPPORTED 42 → 24;
  - use 88/88, true SUPPORTED 50/50, corroborated 11/11;
  - G3 failed, and P4 is not approved.

## 2. Attribution-only candidates (Phase 2)

**Rules.** They are the attribution rules of G22-R4 P3/P4, reused **verbatim** from the hash-pinned
`m11g22r4_policies.py` (`e56c518c…`) and regrouped into cumulative candidates.

**Excluded:** P1's homonym lexicon, P2's negation rule, P4's homonym overrides, positive technical-noun cues, blanket
preposition rules, capitalisation and any registry change.

**Scope: every README-safe alias.** Attribution is not alias-specific ("plan to add Kubernetes", "inspired by
FastAPI"). R4 had limited its rules to the 11 ambiguous aliases because of its gate G6.

| Candidate | Adds |
|---|---|
| A | third-party projects, documentation and references: inspired by / port of / alternative to / than / like X (unless a claim-of-use verb opens the clause) / notes or translation of X / "the X documentation" / maintained by another team |
| B | A + bounded historical frames (originally, began life as, moved off, old/former/previous, until vN, no longer, used to) |
| C | B + future and hypothetical frames (plan to, would like to, someday, `TODO:`, "X bindings are planned", "can be generated for"); an unchecked task item counts only under a planning heading |
| D | C + Markdown attribution (attributed blockquotes; `[project](https://…) (X)` and reference-style `[project][1] (X)` annotations; linked list items under bindings/ports/community headings, ATX or setext). Never fires inside a fenced block |
| **D_S** (selected) | D + a setext- and fence-aware heading index swapped into production's unchanged 8D.3 heading denylist |
| D_ambiguous_only | D limited to the 11 ambiguous aliases (comparison) |
| O | **not attribution:** overlap-aware fall-through (a separate multi-occurrence finding) |

**Changes made on seen data before the freeze**, each tied to a seen failure:

1. A TODO marker needs a colon. R4's `to-?do:?` rejected "A to-do list in one HTML file".
2. Unchecked task items count only under a planning heading. Otherwise jango1324/Mentoria's setup checklist ("-
   [ ] `supabase/schema.sql` has been run …", heading "Database") was rejected.
3. Reference-style link annotations are supported.
4. Markdown rules never fire inside fenced code.

## 3. Markdown parsing findings (Phase 3)

| Structure | Production `readme:v4` | Finding |
|---|---|---|
| ATX headings | indexed (8D.3 denylist) | adequate |
| **Setext headings** | **not indexed** | A setext "Development" heading does not end a preceding "## Related projects" section. Production **discards the genuine "This tool is written in Rust."** (D_S recovers it), and setext "Related projects" sections go unrecognised (D_S rejects them) |
| Section inheritance by level | none (nearest heading wins) | A `### FastAPI` subsection of `## Alternatives` escapes the denylist. Inheriting would also discard `### Why we chose FastAPI` / "built on FastAPI", so it was **not** implemented |
| Paragraph boundaries | every newline ends a "sentence" (G22-R helper) | Hard-wrapped prose splits mid-sentence. The research sentence model joins soft wraps |
| Nested lists | n/a | The bindings-list rule follows nested sub-items for the external link (libgit2 `* Java` / `* jgit …`) |
| Blockquotes | not distinguished | Attributed only when introduced by a line ending ":" or under a quote/testimonial heading. A project note ("> **Note:** this project requires Python 3.11") stays valid |
| Fenced code | headings inside fences ignored | **A fence neither proves nor disproves use.** Code copied from another project's docs stays evidence (a limitation) |
| Inline code | no effect | no attribution signal found |
| Links and references | text only | `[project](url) (X)` and `[project][ref] (X)` with an external definition annotate external projects |

**Scope of the parsing changes.** The setext index and the sentence model are parsing changes to
`readme_context.py`, not filter predicates. Level-aware inheritance and document-level genre (see §8) exceed a narrow
extractor guard and are documented, not implemented.

## 4. Multi-occurrence behaviour (Phase 4)

**Production fall-through already guarantees two properties:**

- A rejected occurrence never blocks a later valid one, because production selects the first non-rejected
  occurrence.
- A rejected occurrence is never used as evidence just because another occurrence shares its concept.

**R5 DEV covers all ten scenarios at least once.** Under D_S:

- invalid-only becomes not SUPPORTED;
- valid-only, invalid → valid, valid → invalid, several valid, invalid in another section, a valid project quote,
  mixed history and current use, and README history plus a manifest all stay SUPPORTED;
- concept deduplication is unchanged.

**Provenance moves when an earlier invalid occurrence is rejected.**

- R5 DEV: 4 items.
- G22-R4 fresh: 2 items.
- 8c: libgit2 Python moves from "[pygit2](…) (Python)" to "[Python](https://www.python.org) is used by our test
  framework".

**Production defect found (not attribution):** in "A React Native app. The web dashboard uses React.",
`framework.react` is **lost**. The first "react" lies inside "React Native"; it is selected and then dropped by 8D.1
overlap resolution, so the later genuine mention never counts.

- The research variant O (skip occurrences contained in a longer alias) fixes it as a filter-level change.
- O is reported separately and is not part of D_S.

## 5. Seen-data comparison (Phase 5)

Attribution false SUPPORTED counts false SUPPORTED controls whose probe label is reference, historical or future.

| Set | v4 FS / attribution FS | A | B | C | D | **D_S** | D_amb | P4 | D_S genuine use |
|---|---|---|---|---|---|---|---|---|---|
| R5 DEV (51; 1 unscoreable) | 24 / 24 | 16 | 13 | 11 | 6 | **5** | 18 | 19 | 27/28 (v4 26/28) |
| G22-R2 DEV | 21 / 4 | 3 | 3 | 0 | 0 | **0** | 0 | 0 | 20/20 |
| G22-R2 EVAL | 18 / 4 | 3 | 3 | 0 | 0 | **0** | 0 | 0 | 19/19 |
| G22-R3 VAL-1 | 35 / 16 | 10 | 7 | 4 | 1 | **1** | 2 | 2 | 36/36 |
| G22-R3 VAL-2 | 24 / 9 | 6 | 4 | 3 | 1 | **1** | 1 | 1 | 23/23 |
| G22-R4 DEV | 29 / 9 | 6 | 4 | 2 | 0 | **0** | 1 | 1 | 31/31 |
| G22-R4 fresh (seen) | 42 / 16 | 15 | 15 | 12 | 10 | **10** | 10 | 10 | 88/88 |

- **Columns A–P4** give attribution-specific false SUPPORTED under each policy.
- **Overall false SUPPORTED under D_S,** in table order: 5, 17, 14, 20, 16, 20, 36. The ordinary-English cases are
  out of scope.
- **G22-R controls under D_S:** false SUPPORTED 21 → 18 and 20 → 18, README recall 14/14 and 12/12. All
  mention-without-use errors are fixed except "works with React, Vue or Svelte".
- **Preserved on every seen set:** no new false SUPPORTED, no non-README evidence change, all corroborated cases.
- **Occurrence level, G22-R4 fresh, all 187 occurrences aligned:** 0 of 101 genuine-use occurrences rejected.

## 6. Freeze, chronology, authorship (Phases 6–7)

All times are 2026-11-16 UTC.

| Time | Event | sha256 |
|---|---|---|
| (before any R5 code) | Fresh-set author launched | — |
| 21:18:36 | R5 DEV controls frozen (51), before any R5 candidate ran on them | `c415966a0112ed2324c7285805594eafa41d73fc7bc9699fcaa74f80fb3a9718` |
| 21:26:14 | **Policy design freeze**: D_S selected; gates, taxonomy, rollout scope, method, limitations | `61e6c9dca527ebe61456289504eb42de1c88679f4d1b398527553d45e2e36671` |
| 21:31:41 | Author finished; raw files hashed | part1 `56831670…`, part2 `c217abee…`, part3 `cb5ae023…` |
| 21:31:42 | **Fresh set frozen** (96); 0 unlabelled mentions, 0 phantom labels, 0 inconsistencies | `697fde84c5632bba991f5e76903aad750405bac3931f9c9d119f61710ca0f4c3` |
| 21:31:51 | **Single held-out run** started | — |

- **Implementation hash:** `m11g22r5_policies.py` = `6e9bfbb3db0c98cfd7bf879cafb3a1fb3186d523b5ee74b4e6cac1bbc6c20767`.
- **State at the design freeze:** the author had written one of its three files, recorded in the freeze as a
  directory listing. Nothing from it had been received or opened.

**Authorship.** The fresh set was written by **a separately instructed Claude subagent, not a human**.

- **Inputs:** the declared evidence-validity policy, the registry vocabulary, the artifact rules, the schema and the
  coverage targets.
- **Not shown:** no earlier control set, example, rule, code or result.
- **Tools:** Write only. Its run recorded 4 tool uses: 3 Writes plus the hand-back.
- **Reply restriction:** its reply was limited to paths and counts, and it complied (no case detail was disclosed,
  unlike G22-R4).
- **Same model family, so not independent human validation.** The set is now seen.

**Frozen gates (G1–G7: the brief's recommendations; G8 target chosen from development data):**

| Gate | Requirement |
|---|---|
| G1 | ≥ 95% genuine README use retention |
| G2 | ≥ 95% true SUPPORTED retention |
| G3 | no new false SUPPORTED |
| G4 | all corroborated cases preserved |
| G5 | no non-README evidence change; only "use" items may be added; removals of ordinary/negated/ambiguous items are documented exceptions |
| G6 | G19 capability and all 64 alias pathways preserved |
| G7 | job parsing identical |
| G8 | **attribution-specific false SUPPORTED ≤ 50% of `readme:v4`** |

**Why 50% for G8:**

- The seen sets pooled show 82 → 17 (−79%), but they shaped the rules.
- The R4 fresh set, whose rules were frozen before it ran, shows −37.5%.
- 50% sits between the two estimates.

## 7. Held-out result (fresh set, 96 controls, run once)

| | `readme:v4` | A | B | C | D | **D_S** | D_amb | P4 |
|---|---|---|---|---|---|---|---|---|
| Overall false SUPPORTED | 52 | 51 | 51 | 47 | 42 | **42 (−19%)** | 47 | 46 |
| **Attribution false SUPPORTED** | 49 | 48 | 48 | 44 | 39 | **39 (−20%)** | 44 | 44 |
| False README evidence (all non-use / attribution) | 81 / 74 | 79 / 72 | 79 / 72 | 75 / 68 | 69 / 62 | **69 / 62** | 75 / 68 | 73 / 68 |
| Genuine README use kept | 95/95 | 95 | 95 | 95 | 95 | **95/95** | 95 | 95 |
| True SUPPORTED kept | 42/42 | 42 | 42 | 42 | 42 | **42/42** | 42 | 42 |
| Corroborated kept | 33/33 | 33 | 33 | 33 | 33 | **33/33** | 33 | 33 |

**Incremental effect of each added layer, on attribution false SUPPORTED:**

| Layer added | Change |
|---|---|
| A, third-party | −1 |
| B, historical | 0 |
| C, future | −4 |
| D, Markdown | −5 |
| S, setext | 0 |

**Effect of D_S on matching and scoring:**

- 10 probes change from `supported` to `not_observed`, all of them false SUPPORTED corrected;
- numerator −10, denominator unchanged;
- 0 scores become undefined;
- 7 provenance items move to another occurrence;
- 0 non-README evidence changes.

**Occurrence level (269 occurrences, all aligned).** D_S wrongly rejected **0 of 139** genuine-use occurrences. It
caught only **25 of 119** invalid attribution occurrences, compared with production's 6 (bindings-section headings):

| Attribution kind | Caught by D_S |
|---|---|
| quotation | 6/6 |
| future | 4/13 |
| reference / comparison | 4/21 |
| third-party project | 8/44 |
| historical | 2/22 |
| third-party docs | 1/13 |

| Gate | Result |
|---|---|
| G1 genuine use ≥ 95% | pass (95/95) |
| G2 true SUPPORTED ≥ 95% | pass (42/42) |
| G3 no new false SUPPORTED | pass |
| G4 corroborated | pass (33/33) |
| G5 non-attribution change | pass (0 non-README changes; nothing added; removed: 8 reference, 4 future) |
| G6 G19 capability | pass |
| G7 parser | pass |
| **G8 attribution false SUPPORTED ≤ 50%** | **FAIL (39 > 24.5)** |

**Decision: STOP.** The failure is preserved. No candidate was revised after the run, so any revision needs a new
fresh set.

**Four levels of outcome.** They count different things and must not be conflated:

| Level | What it counts | `readme:v4` → D_S |
|---|---|---|
| 1. Individual invalid attribution mentions | occurrences, author-labelled per mention, 269 aligned | D_S rejects 25 of 119 invalid attribution mentions (production 6); 0 of 139 genuine-use mentions rejected |
| 2. Concept-level README evidence | one README item per concept per repository | invalid items 81 → 69 overall, 74 → 62 attribution-related; genuine use items 95/95 kept |
| 3. Incorrect MatchStatus | probe requirements whose status changes | 10 change from `supported` to `not_observed`, all corrections |
| 4. False SUPPORTED scoring outcomes | counted SUPPORTED probes the candidate does not use | 52 → 42 overall; **49 → 39 attribution-specific** (G8 needs ≤ 24) |

Rejecting one invalid mention changes concept-level evidence only if no other invalid mention of that concept remains.
A concept-level change alters MatchStatus only if no other evidence supports the requirement.

## 7a. Validation disclosure

1. **Author:** the fresh controls were written by a separately instructed **Claude subagent**, not a human.
2. **Blindness:** the author never saw any G22-R/R2/R3/R4/R5 policy, rule, code, test, earlier control set or
   result.
3. **Same model family:** the author is the same model family as the policy author, and may share its blind spots.
4. **Hand-back:** its response contained file paths and case counts only; no case content reached the policy author
   before the design freeze.
5. **Not independent:** this is a frozen held-out evaluation, **not independent human validation**.
6. **Now seen:** having been evaluated once, the fresh set cannot be reused as an untouched holdout.
7. **Earlier sets:** the G22-R, G22-R2, G22-R3 and G22-R4 controls (and the R5 DEV controls) were development data
   for R5.
8. **No tuning:** no policy change followed the held-out run; the design-freeze file hashes are re-verified before
   every evaluation.
9. **Why D_S is not approved:** D_S is precise in what it rejects, but it rejects too few invalid attribution
   mentions on unseen phrasing. Its false-evidence reduction is therefore insufficient, which prevents production
   approval.

## 8. Why it failed (post-hoc diagnostic; not validation, no policy change)

The guard is **precise but low-recall on unseen phrasing**. Its closed, occurrence-local frames match the phrasings
of earlier sets, not the fresh author's. Most missed invalid mentions fall into three groups:

- **Document-level attribution.** The whole README is about other projects or topics:
  - "awesome-list" style sections without links (`## Python` / `- Flask - a lightweight WSGI framework`);
  - documentation and notes repositories (`- Running the dev server inside Docker`, "A Spanish translation of the
    official Kotlin coroutines guide").

  No local frame is present, and deciding this needs a repository-genre judgment. That is beyond a per-occurrence
  guard.
- **Open-ended historical phrasing:**
  - "dropped the PostgreSQL backend";
  - "the Flask code was deleted";
  - "the `legacy-java` branch contains the original Java implementation";
  - "is archived in the `ruby-archive` tag";
  - "TensorFlow checkpoints are no longer supported".
- **Open-ended future phrasing:**
  - "could make rendering much faster";
  - "(help wanted)";
  - "contributions to support Next.js are welcome";
  - "on the wish list";
  - "not provided yet".

**The same pattern holds across both fresh sets.** Seen sets −79%; G22-R4 fresh (rules frozen earlier) −37.5%; R5
fresh −20%. Extending the closed lists from these examples would be tuning on held-out data.

## 9. Real-pipeline impact on 8c (Phase 8)

The real offline pipeline was run on the frozen 8c fixtures under pinned `readme:v4` and under D_S. All differences
are simulated; production is unchanged.

- **torvalds/libgit2:** D_S removes 7 README items from the language-bindings list: C++, Java, JavaScript, PHP, Ruby,
  Rust and Swift. C++ and JavaScript survive for torvalds through other repositories; Java, PHP, Ruby, Rust and Swift
  are lost.
- **libgit2 Python is kept.** Provenance moves to the genuine "Python is used by our test framework" requirement.
- **sindresorhus/Gifski Rust is kept** ("you need to have Rust installed").
- **torvalds/systems_cpp_01: simulated 67 → 33** (numerator 2 → 1, denominator 3) in both matrix versions. 2 pairs
  change status, and 0 scores become undefined. **Production remains 67.**
- **Repository documentation copied from another project.** Copied upstream text stays evidence unless it is an
  attributed blockquote (R5 DEV `copied_upstream_readme`, `fence_other_project`). No 8c fixture contains such a copy.
- **Jango1324/Mentoria's setup checklist** is kept, after refinement 2 in §2.

## 10. Capability, regressions, safety (Phase 9)

- **G19:** capability is identical for all 39 concepts under every policy, and all 64 README-safe aliases are
  extracted.
- **Job side:** job parsing is identical on every G22 corpus (G22-Q, G22, G21, G20, G17, G16, G15, M10/M10E). The 62
  private postings show 0 changes (integer counts only).
- **Existing README / evidence / harness tests under the research candidates:** 166 passed, 1 failed. The one failure
  is the whole-report reproduction of the G22-R report, which is expected to differ under a substituted README
  policy. The homonym-pinning tests that failed under R4's P1–P4 all pass, because R5 never touches ordinary English.
  Production: 167 passed.
- **Full suite (production, with R5 files present):** see the changelog entry. No new skips or xfails.
- **The public report holds no canonical-manifest state.** Registering freezes later cannot change it; a test enforces
  this.

## 11. Future production changes, if pursued

- **Possible home:** `readme_context.py` — one more `is_non_implementation_mention` signal, a setext- and fence-aware
  `ReadmeContext`, and a paragraph-aware sentence span. `readme.py` would need only a v4 → v5 bump.
- **Unchanged:** registry, matcher (v1), scoring (v2), evidence schema and API.
- **Not justified by this evidence:** the attribution guard. It is safe (0 genuine-use rejections) but recovers too
  little attribution error on unseen text.
- **Separable, attribution-independent defects worth their own reviewed fixes:**
  1. Setext headings break the 8D.3 denylist and discard genuine evidence.
  2. 8D.1 overlap resolution drops a concept whose first occurrence sits inside a longer alias ("React Native" then
     "uses React").
  Each is a small, testable `readme_context.py` / `readme.py` change, but each changes production evidence and needs
  its own authorization, controls and version bump.
- **Document-level attribution** ("this repository is a list of / notes about other projects") needs a separate
  design. It is a repository-genre signal, not an occurrence frame.

## 12. Decisions needed

1. Keep `readme:v4`; do not implement D_S or any attribution guard as `readme:v5`.
2. The research-only commit and the 25 → 27 registration were authorized and done.
3. Whether to open separate, narrowly scoped milestones for the two production defects in §11 (setext section
   boundaries; overlap blocking).
4. Whether to commission human-authored validation before any further README-guard work. Two successive AI-authored
   fresh sets show closed-list attribution frames do not generalise.

## 13. Files (research only; committed at the research commit)

- **Manifest:** `evaluation/integrity/canonical_hash_manifest.json` (+2 entries).
- **Report independence:** the R5 public report records no manifest state, so registration did not change it. It was
  re-verified byte for byte after registration.

- **Controls and freezes:**
  - `evaluation/m11g22r5/dev_controls.json`, `dev_hash_freeze.json`
  - `evaluation/m11g22r5/fresh_validation_controls.json`, `fresh_hash_freeze.json`, `fresh_author_provenance.json`
  - `evaluation/m11g22r5/policy_design_freeze.json`
- **Reports:**
  - `evaluation/m11g22r5/attribution_readme_report.json` (public; deterministic; no manifest state)
  - `evaluation/m11g22r5/private_attribution_readme_aggregates.json` (integer counts only)
- **Scripts:**
  - `scripts/evaluate_m11g22r5_attribution_readme.py`
  - `scripts/evaluation_lib/m11g22r5_policies.py`
  - `scripts/evaluation_lib/m11g22r5_build_dev_controls.py`
  - `scripts/evaluation_lib/m11g22r5_build_fresh_controls.py`
  - `scripts/evaluation_lib/m11g22r5_pytest_policy.py`
- **Tests:** `tests/test_m11g22r5_attribution_readme.py`. Its registration tests pin both states:
  - at the parent commit `39b570c`, the manifest had 25 entries and neither R5 set;
  - now both are registered with their freeze-time hashes and verify.
- **Docs:** this file; `docs/CHANGELOG_DEV.md`.
