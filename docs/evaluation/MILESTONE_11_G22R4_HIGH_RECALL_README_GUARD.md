# Milestone 11-G22-R4 — High-recall (inverse) README evidence guard research

**Status:** research and evaluation only; **`readme:v5` was NOT implemented** and nothing is recommended for
production as frozen. The chosen inverse candidate P4 kept 100% of genuine README use on the fresh held-out set. It
cut false SUPPORTED by only 43% (42 → 24), so it missed the frozen ≥ 50% reduction gate.

- **Production unchanged:**
  - parser `job_description_parser:v15`;
  - scoring `github_evidence_alignment:v2`;
  - matcher `requirement_matcher:v1`;
  - README extractor `readme:v4`;
  - registry version 4.
- `src/` and registry data are unchanged, and no LLM is called anywhere in the evaluation.
- **Freezes:** the 23 historical freezes are untouched and all verify.
- **Research accepted and committed** as a research-only commit ("test: evaluate high-recall README evidence guards")
  after authorization. The finding that P4 failed gate G3 is final.
  - The R4 DEV and fresh control sets are registered in the G14 manifest at that commit with their original
    freeze-time hashes (23 → 25; the previous 23 are unchanged field for field).
  - Their freeze records keep their freeze-time note ("NOT registered … pending authorization"); they are not
    rewritten.
- **Kinds of evidence, kept distinct throughout:**
  - seen design data (G22-R, G22-R2, G22-R3 VAL-1/VAL-2, 8c, R4 DEV);
  - a separately authored fresh held-out set (same model family, not human-independent);
  - post-hoc diagnostics, run after the held-out run;
  - simulated historical score effects;
  - actual production behaviour.

## 1. Baseline (verified at session start)

- **Git:** HEAD `8241a24b9e0d07ebd33835bd1a20d3cddab6e429` on `main`, equal to `origin/main`.
- **Versions:** parser v15, scoring v2, matcher v1, `readme:v4`, registry 4.
- **Backend suite:** 2420 passed, 13 skipped, 18 xfailed.
- **Freezes:** the G14 manifest has 23 entries, and all verify.
- **Working tree:** the 18 private/untracked M11 entries were present and are preserved.
- **G22-R3 reproduced byte for byte.** Its report regenerated identically in memory:
  - VAL-2 false SUPPORTED: `readme:v4` 24, D 7, R3 8;
  - R3 genuine README use 18/23, true SUPPORTED 21/24, corroborated 6/6;
  - criteria 4 and 5 failed for both D and R3, and neither was implemented.

## 2. Historical false-evidence taxonomy (Phase 2)

All 139 `readme:v4` false SUPPORTED rows were classified: 132 README-side rows across G22-R, G22-R2 and G22-R3, plus
7 G22-R job-side rows.

- Rows from G22-R2 and G22-R3 follow their frozen author label and family.
- G22-R labels only "mentioned / used", so its six mention-without-use rows were classified by reading the public
  synthetic text. Those judgments are listed in the report.
- Frozen gold is unchanged.

| Category | Rows | Fixed by P4 (seen) | Fixed by D | Fixed by R3 |
|---|---|---|---|---|
| A ordinary English (concept identity) | 88 | 81 | 87 | 87 |
| B mention without demonstrated use | 1 | 0 | 0 | 0 |
| C negated | 5 | 5 | 1 | 1 |
| D historical | 5 | 5 | 2 | 2 |
| E future / hypothetical | 13 | 12 | 10 | 10 |
| F third-party docs | 5 | 3 | 4 | 4 |
| G quotation / comparison | 15 | 15 | 8 | 7 |
| H not confidently classifiable | 0 | — | — | — |
| J job-side concept (out of scope) | 7 | 4* | 5* | 5* |

\* A job-side false concept is no longer SUPPORTED once its false README evidence is removed. The job parse itself
is identical under every policy.

**Concept identity vs attribution.** 88 rows are concept-identity errors (A). 44 are project-attribution errors
(B–G).

**Which categories admit deterministic rejection:**

- **C, D and G**, mostly. These have bounded, directional lexical frames: a negator within three words; "originally" /
  "moved off" / "the old"; "inspired by" / "than" / "like the" / an attributed blockquote.
- **E**, mostly: "plan to", "would like to", "<X> bindings are planned", "can be generated", unchecked task items.
- **A**, only where the homonym sense sits in a fixed structural slot: an adjacent modifier or head noun, a coordinated
  sibling, a verb or adjective frame, a determiner-headed count noun, or a name frame.
- **F**, only with an explicit frame ("notes on how the …", "the X documentation", "maintained by another team", a
  linked bindings list).
- **B and H** are not locally resolvable.

**Cannot be resolved with local context** (residual on the seen sets under P4):

- "a start port on Java, add stops on Bali or Lombok";
- "Swift onboarding is the goal";
- "ruby for the fortieth";
- "React, record, repeat";
- "# ruby-the-cat" (the prose "my cat, Ruby" is rejected, but the hyphenated repository-name heading leaks through
  fall-through);
- "React to failed builds automatically";
- "the python grows each level";
- "Source for the documentation site of Quarry, a Java persistence library";
- "works with React, Vue or Svelte" (B);
- two non-ambiguous PyTorch cases (out of scope by gate G6).

## 3. Inverse-guard design (Phases 3–4)

**Default-accept.** An occurrence of one of the 11 ambiguous aliases (react, express, swift, rust, ruby, shell, torch,
python, java, flask, pandas) is rejected only when a bounded local signal shows that it is not project-use evidence.
Every other alias is exactly `readme:v4`.

**Production behaviour preserved:**

- the 8D.3 filter still runs first;
- a rejected occurrence falls through to the next occurrence or alias;
- one item per concept, MODERATE confidence.

**Capitalisation is never sufficient.** Where case is consulted, it is only an additional *necessary* condition for a
rejection. Lowercase "a swift reply" is rejected; "A Swift package" is never accepted *because* it is capitalised.

| Policy | Adds |
|---|---|
| P0 | production `readme:v4` |
| P1 | homonym-sense rejection in fixed slots (§2) using a per-alias lexicon; no README-wide word lists ("train", "island", "coffee" or "corrosion" elsewhere in a README do nothing) |
| P2 | P1 + bounded negation (a negator ≤ 3 words before, same clause, no exception/causal word in the gap; "X-free"; "X is not required") |
| P3 | P2 + attribution: reference/comparison, historical, future/hypothetical, other-project docs, attributed blockquotes, third-party linked lists under bindings/ports/community headings (ATX or setext), "[project](https://…) (X)" |
| P4 | P3 + narrow positive overrides **only** to resolve two known conflicts: a P1 rejection is withdrawn by code / version / claim-of-use frame / registry sibling / software head noun ("A Java and Kotlin Android app"); a P3 "like X" is withdrawn when a claim-of-use verb opens the clause ("built with tools like React") |

**Research-only infrastructure.** Neither piece exists in production:

- a paragraph-aware sentence model, because hard-wrapped READMEs (torvalds/libgit2) split mid-sentence under G22-R's
  newline-as-sentence rule;
- a setext-aware heading index.

**Every rejection returns a reason string.** The report lists every rejected occurrence with its rule.

**R4 DEV near-neighbour controls (60, policy-author-written, DEV only).**

| Pair | Text | readme:v4 | P4 | D | R3 |
|---|---|---|---|---|---|
| express-train (Rust probe) | "Express train simulator built in Rust" | ✓ | ✓ | ✓ | ✓ |
| express-train (Express probe) | same text | false SUP | ✓ | ✓ | ✓ |
| rust-removal (Rust probe) | "Rust removal tool written in Python" | false SUP | ✓ | false SUP | false SUP |
| ruby-gem | "A Ruby gemstone catalog built in Ruby" | ✓ | ✓ | ✓ | ✓ |
| pure-python | "Pure Python TOML parser" | ✓ | ✓ | missed | missed |
| swift-api | "One-line Swift API …" | ✓ | ✓ | missed | missed |
| python-snake | "feeds the python every ten days" | false SUP | **false SUP** | ✓ | ✓ |
| rust-bindings-gen / -real | "can be generated" vs "maintained here" | false / ✓ | ✓ / ✓ | ✓ / ✓ | ✓ / ✓ |
| java-coffee-amb | "Java coffee ordering application" | uncertain (labelled H) | — | — | — |

## 4. Candidate comparison on seen design data (Phase 5)

| Set | readme:v4 FS | P1 | P2 | P3 | **P4** | D | R3 | P4 genuine use / true SUP |
|---|---|---|---|---|---|---|---|---|
| R4 DEV (60) | 29 | 13 | 11 | 3 | **3** | 5 | 6 | 31/31 · 29/29 (D 21/31, R3 23/31) |
| G22-R2 DEV | 21 | 4 | 4 | 0 | **0** | 0 | 0 | 20/20 · 20/20 |
| G22-R2 EVAL | 18 | 4 | 4 | 0 | **0** | 1 | 1 | 19/19 · 19/19 (D/R3 16/19) |
| G22-R3 VAL-1 | 35 | 21 | 18 | 4 | **4** | 9 | 9 | 36/36 · 36/36 (D 26, R3 33) |
| G22-R3 VAL-2 | 24 | 13 | 11 | 3 | **3** | 7 | 8 | 23/23 · 24/24 (D 17, R3 18) |
| G22-R DEV / EVAL | 21 / 20 | 5 / 7 | 5 / 7 | 2 / 5 | **2 / 5** | 2 / 3 | 2 / 3 | README recall 14/14, 12/12 (D/R3 12/14, 11/12) |

- **Always preserved on these sets:** corroborated cases, non-ambiguous items (0 changes), G19 capability and job
  parsing.
- **These are design results.** Every number in this section was visible while P1–P4 were being written.

## 5. Policy-design freeze and chronology (Phase 6)

| Time (UTC, 2026-11-15) | Event | sha256 (LF canonical) |
|---|---|---|
| (launch) | Fresh-set author launched **before** any R4 policy existed; given no rules, code or results | — |
| 23:11:45 | R4 DEV controls frozen before any R4 policy ran on them | `8e1034770d543e25a843700cfee11294d1c45058065aa2c348cab6955374cd3e` |
| (design) | P1–P4 drafted and revised on seen data (4 disclosed changes, below) | — |
| 23:22:01 | Fresh author finished; raw part-file hashes recorded unread | part1 `58c54c08…`, part2 `315a5043…`, part3 `7b14274e…` |
| 23:23:29 | **Policy design freeze** (chosen P4, rules, gates, limitations, file hashes) | `5ad3c0bbabeab0266482d46100bb076ba89afaeaa7aad3b7f511c30f457175d9` |
| 23:24:07 | Fresh set converted verbatim and frozen; pre-freeze checks: 0 unlabelled mentions, 0 phantom labels, 0 status inconsistencies | `8d003c6ef6f873a43d6618a7775d575b780d1d5eccfcf3b6c99966667d3b92ed` |
| 23:27:08 | **Single held-out run** of frozen P4 | — |

- **Frozen implementation:** `scripts/evaluation_lib/m11g22r4_policies.py` `e56c518c…9b963ce4`.
- **Shared files unchanged.** The reused G22/G22-R/G22-R2/G22-R3 policy and harness files hash identically to their
  own G22-R3 freeze.
- **The evaluator re-verifies every frozen hash before it runs.**

**Design changes before the freeze, all on seen data:**

1. The P4 head-noun override no longer counts "service(s)". It had re-admitted "Local and express services".
2. An "as X as" comparison was added.
3. The paragraph-aware sentence model was introduced, after the libgit2 audit.
4. The roadmap-heading rule was **removed**: it rejected a *completed* "Python SDK" roadmap item in Jango1324/hive.

**Leakage disclosure.** Before the freeze, the policy author read the fresh author's hand-back message. It named about
ten case-level details (SWIFT/BIC banking codes; "Supports Express." in a courier context; a ```` ```bash ```` fence;
slack-ruby-client; index.html; analysis.ipynb; a version badge; two conflicting-signal cases). **No policy change was
made after that message.** The freeze was written immediately after it, without opening the files.

**Gates frozen before the run.** The brief's suggested gates were adopted unchanged; no alternative threshold was
justified:

| Gate | Requirement |
|---|---|
| G1 | ≥ 95% genuine README use retention |
| G2 | ≥ 95% true SUPPORTED retention |
| G3 | ≤ 50% of `readme:v4` false SUPPORTED |
| G4 | no new false SUPPORTED |
| G5 | all corroborated cases preserved |
| G6 | no non-ambiguous evidence change |
| G7 | G19 capability and all 64 alias pathways preserved |
| G8 | job parsing identical on all corpora (G22-Q, G21, G20, …, M10) |

All gates must pass. If any fails: no recommendation, no threshold change, and a new fresh set is needed for any
revision.

## 6. Fresh validation: authorship and provenance (Phase 7)

**Human-authored validation was not available.** The set was written by **a separate Claude subagent instance**:

- **Tools:** instructed to use the Write tool only. Its run recorded 4 tool uses: 3 Writes plus its hand-back
  report. It made no read, search or command call, so it never accessed the repository or any policy code.
- **What it was given:**
  - the task and a declared evidence-validity policy: valid iff the word means the technology **and** the text
    attributes current use to this repository;
  - the registry vocabulary with matching semantics;
  - the artifact rules (5% language floor; root `requirements.txt` / `pyproject.toml` / `package.json`; Docker
    presence);
  - the output schema and coverage targets.
- **What it was not given:** no R4, D or R3 rule, code, test, design set or result.
- **Not human-independent.** It is the same model family as the policy author and may share blind spots.
- **Frozen held-out, not fully blind independent validation.** Labels were frozen before any run, and P4 was frozen
  before the set was opened. However:
  - the author shares the policy author's model family;
  - about ten case-level details reached the policy author through the hand-back note before the design freeze (no
    policy change followed; §5).
- **This set is now seen.** It has been evaluated and cannot be reused as an untouched holdout. G22-R, G22-R2,
  G22-R3 and the R4 DEV controls were already seen design data.

**Contents: 96 controls.**

- 22 near-neighbour pairs, 10 mixed, 20 non-use, 10 structure, 12 artifact combinations;
- target status: 50 SUPPORTED, 45 NOT_SUPPORTED, 1 UNCERTAIN.

**Labels.** Each control records:

- concept-level classes;
- per-occurrence labels: class, technical in context, project use indicated, sentence;
- `used`, `corroborated` and `uncertain`;
- the expected target status and the expected effect (status, and score 100 or 0).

All 153 ambiguous-alias occurrences aligned exactly with the author's occurrence list.

## 7. Held-out result: run once (fresh set)

| Fresh (96) | readme:v4 | P1 | P2 | P3 | **P4 (frozen)** | D | R3 |
|---|---|---|---|---|---|---|---|
| False SUPPORTED | 42 | 31 | 30 | 24 | **24 (−43%)** | 14 | 15 |
| … ordinary / reference / future / historical / negated | 25/10/4/2/1 | | | | **14/7/1/2/0** | 3/6/3/2/0 | 3/7/3/2/0 |
| Genuine README use items kept | 88/88 | 88 | 88 | 88 | **88/88 (100%)** | 75 (85%) | 76 (86%) |
| True SUPPORTED kept | 50/50 | 50 | 50 | 50 | **50/50 (100%)** | 41 (82%) | 42 (84%) |
| Corroborated kept | 11/11 | 11 | 11 | 11 | **11/11** | 11 | 11 |
| New false SUPPORTED vs v4 | — | 0 | 0 | 0 | **0** | 0 | 0 |
| Non-ambiguous items changed | — | 0 | 0 | 0 | **0** | 0 | 0 |
| Use **occurrences** wrongly rejected (of 68) | — | 0 | 0 | 0 | **0** | 19 | 16 |
| Invalid occurrences rejected (of 80 not already excluded by 8D.3) | — | 29 | 32 | 43 | **43** | 60 | 59 |

**Effect on matching and scoring (P4 vs `readme:v4`):**

- 18 probes change from `supported` to `not_observed`, all of them false SUPPORTED corrected;
- numerator −18, denominator unchanged;
- 0 scores become undefined.

| Gate | Result |
|---|---|
| G1 genuine use ≥ 95% | **pass** (100%) |
| G2 true SUPPORTED ≥ 95% | **pass** (100%) |
| G3 false SUPPORTED ≤ 50% | **FAIL** (24 > 21) |
| G4 no new false SUPPORTED | pass |
| G5 corroborated | pass |
| G6 non-ambiguous unchanged | pass |
| G7 G19 capability | pass |
| G8 job side identical | pass |

**Decision.** The frozen rule says that if any gate fails, P4 is not recommended. **P4 is not recommended as
frozen.** Any revision needs a new fresh set; this set is now seen.

**The trade-off holds on fresh data:**

| | False SUPPORTED reduction | Recall |
|---|---|---|
| Inverse P4 | 43% | 100% |
| Positive-cue D / R3 | 64–67% | 82–86% |

Neither family met every gate.

**Two recall denominators.** They count different things:

- **88/88** counts concept-level README items labelled "use" that `readme:v4` extracts: at most one per concept per
  control. 64 are for the 11 ambiguous-alias concepts and 24 for non-ambiguous concepts.
- **0 of 68** counts individual ambiguous-alias *occurrences* that the author labelled "use", aligned one to one with
  the text. Some READMEs mention a used concept more than once, so 64 concepts carry 68 occurrences.

**Remaining false positives under P4.** The 24 residuals, by the author's probe label, are 14 ordinary + 7 reference
+ 2 historical + 1 future = 24. They are listed in the report:

- 14 ordinary, mostly long-tail senses outside the lexicon or outside a fixed slot:
  - "acids react with sodium hydroxide";
  - "swift colonies in church towers";
  - SWIFT/BIC codes;
  - "wheat stem rust";
  - "Ruby, the chore bot";
  - "shell length / shell damage";
  - "torch angle";
  - a team called "the Pandas";
  - "ruby for the fortieth";
  - a JSON birthstone record;
- 7 reference. One of them is fresh-082, a ```` ```bash ```` code-fence tag that the author labelled "reference".
  Its alias "bash" is non-ambiguous, so it is outside the guard's scope by design (gate G6). It is **included** in
  the 7, not an additional case. An earlier draft of this report listed it as a separate item, which was a reporting
  inconsistency, now corrected.
- 2 historical;
- 1 future.

**Post-hoc diagnostic (after the run; not validation).** 7 of the 24 were *partially* caught: P4 rejected one invalid
occurrence, but a later invalid occurrence of the same alias leaked through production's fall-through. 34 of 96
fresh controls mention their target alias more than once. A default-accept guard must reject **every** invalid
occurrence in a README, so its precision falls as READMEs repeat a homonym.

**Remaining false negatives under P4:** none at item, probe or occurrence level on this set. D and R3 lost 13 and 12
use items, including "flask"-, "pandas"- and "shell"-led genuine phrasings.

## 8. Historical impact and regression (Phase 8)

These results are simulated; nothing is deployed.

**Frozen 8c:**

- P3/P4 remove 4 README items, all from libgit2's other-projects language-bindings list: Java, Ruby, Rust and Swift
  are lost for torvalds.
- **libgit2 Python is kept.** Its first occurrence ("[pygit2](…) (Python)") is rejected, and evidence moves to
  "Python is used by our test framework, and should be installed". D and R3 removed Python entirely.
- *Post-inspection judgment, not gold:* that second occurrence is a genuine build/test requirement. G22-R2's
  `REVIEW_8C` had judged libgit2 Python a reference from its first occurrence only.
- **Gifski Rust is kept** under P0–P4. D and R3 removed it.
- **torvalds/systems_cpp_01: simulated 67 → 33** (numerator 2 → 1, denominator 3) in both matrix versions; 2 pairs
  change status; 0 scores become undefined.
- **Production is still 67.** The 33 is a research-adapter simulation.

**Named phrases:** P0–P4 extract each of these; D and R3 extract none of them:

- "Pure Python";
- "Pure Python, no third-party dependencies";
- "One-line Swift API";
- "image diffing in Rust";
- "python plotting helper";
- "trained with torch";
- "store in Rust";
- "Streaming CSV reader, in Swift".

"Like the Rust compiler" (reference) is rejected by P3/P4 and D, and admitted by R3.

**Difficult cases:**

- The traps "A Java coffee app for our cafe" and "with a torch" are rejected.
- "Photos taken in Java last summer" and "Ruby, our app's mascot" are still admitted. These are known limitations.

**Regression checks:**

- G22-Q, G21/G20, G17, G16/G15 and M10/M10E job parsing is identical on every corpus under every policy.
- The 62 private postings show 0 changes (integer counts only).
- G19 capability is identical for all 39 concepts, and all 64 README-safe aliases are extracted from "This project is
  built with <alias>."
- **Existing README/evidence/harness tests under P1–P4:** 8 failed, 159 passed. These are exactly the 8 tests that
  fail under every G22-R2 guard. They pin `readme:v4`'s documented ordinary-English false positives and two
  whole-report/alias-table reproductions. Under P0, 167 passed.

## 9. Production feasibility (Phase 9)

- **Where it could live.** The guard could live entirely in `readme_context.py` as an extra
  `is_non_implementation_mention` signal. `readme.py` would need only a `readme:v4 → v5` version bump. The matcher
  (v1) and scoring (v2) would be unchanged, as would the evidence schema and provenance: one snippet per concept from
  the selected occurrence.
- **SUPPORTED's definition is unchanged.** A requirement is still SUPPORTED by one MODERATE README item; only which
  occurrences count changes. No matcher or scoring review is triggered.
- **Alias-specific metadata.** The P1 homonym lexicon is per-alias, so a production version needs a reviewed home: a
  registry field or a `readme_context` table. Registry aliases themselves need no change.
- **Two infrastructure changes beyond a filter:**
  - a paragraph-aware sentence span;
  - setext heading support in `ReadmeContext`, which today is ATX only (a gap it already documents).
- **Attribution rules are generic** (negation, history, future, third-party lists). Restricting them to the 11
  ambiguous aliases was a gate (G6), not a linguistic necessity. Extending them to all aliases would change
  non-ambiguous evidence and would need its own review.
- **Smallest viable future correction**, if a later fresh set supports it: the attribution rules (P2/P3) without the
  homonym lexicon.
  - The P2/P3 rules never rejected a genuine use occurrence on any measured set, fresh included. P3's only use loss,
    on G22-R2 DEV, came from P1's determiner rule.
  - They are alias-agnostic apart from scope.
  - Together with P2, they account for all 40 of the 44 historical attribution rows that P4 fixes.
  - An attribution-only policy was **not** run as a separate candidate; its standalone numbers are unmeasured.
  - The ordinary-English half needs a lexicon whose coverage is open-ended. On fresh data its gain was 42 → 31.

## 10. Recommendation and decisions needed

1. **Keep `readme:v4`.** Do not implement P4, D, R3 or a hybrid as `readme:v5` from this evidence.
2. **Neither guard family meets all gates.** If precision work continues, the evidence points to three options:
   - (a) the attribution-only guard (P2/P3 rules) as a candidate needing a new **human-authored** fresh set;
   - (b) explanation-level labelling of README-only evidence for ambiguous aliases;
   - (c) a combined design that requires *all* occurrences of an ambiguous alias to pass, which is a different
     fall-through semantic and needs its own design review.
3. **Decisions for the user:**
   - The research commit and the 23 → 25 registration were authorized and done.
   - Still open: whether to commission human-authored validation, and which of 2(a)–(c), if any, to pursue.

## 11. Files (research only; committed at the research commit)

- **Controls and freezes:**
  - `evaluation/m11g22r4/dev_controls.json`, `dev_hash_freeze.json`
  - `evaluation/m11g22r4/fresh_validation_controls.json`, `fresh_hash_freeze.json`, `fresh_author_provenance.json`
  - `evaluation/m11g22r4/policy_design_freeze.json`
- **Reports:**
  - `evaluation/m11g22r4/high_recall_guard_report.json` (public; deterministic)
  - `evaluation/m11g22r4/private_high_recall_guard_aggregates.json` (integer counts only)
- **Scripts:**
  - `scripts/evaluate_m11g22r4_high_recall_guard.py`
  - `scripts/evaluation_lib/m11g22r4_policies.py`
  - `scripts/evaluation_lib/m11g22r4_build_dev_controls.py`
  - `scripts/evaluation_lib/m11g22r4_build_fresh_controls.py`
  - `scripts/evaluation_lib/m11g22r4_pytest_policy.py`
- **Tests:** `tests/test_m11g22r4_high_recall_readme_guard.py`. Its registration test pins both states:
  - at the parent commit `8241a24`, the manifest had 23 entries and neither R4 set;
  - now both are registered with their freeze-time hashes and verify.
- **Manifest:** `evaluation/integrity/canonical_hash_manifest.json` (+2 entries).
- **Report regeneration after registration.** The public report's `freezes` section records each R4 set's
  registration status and the manifest's verified-entry count, so it was regenerated once after registration. Only
  those four fields differ from the held-out run's output (`false → true`, `23 → 25`); every measured section is
  byte-identical. A later milestone that adds registrations would change that count again.
- **Docs:**
  - this file;
  - `docs/CHANGELOG_DEV.md`;
  - limitation notes in `docs/ARCHITECTURE.md` and `docs/PIPELINE.md`.
