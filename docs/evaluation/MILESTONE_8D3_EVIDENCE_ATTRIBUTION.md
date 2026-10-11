# Milestone 8D.3 — Evidence Attribution Precision

Fixes the known `karpathy/llm.c` -> `language.cpp` false positive
already flagged (but not fixed) in
`evaluation/gold_v1_1/candidates/karpathy.json`'s `not_expected_concepts`,
and generalizes the mechanism behind it. Full architecture writeup:
`docs/ARCHITECTURE.md` §27. This document is the evaluation record —
the exact provenance trace, the root cause, the design decided (and the
one deliberately rejected), the positive/negative controls, and the
before/after numbers.

## 1. Provenance trace — from fixture to Evidence

Starting point: `evaluation/fixtures/candidates/karpathy.json`'s
`selected.llm.c` entry, the frozen offline snapshot driving
`extract_candidate_evidence()` in the evaluation harness.

**GitHub language stats** (`languages` field): `Cuda: 778454, Python:
158852, C: 140734, C++: 45575, Shell: 26407, Makefile: 19955, Jupyter
Notebook: 5702` — total 1,175,679 bytes. C++'s share is
`45575 / 1175679 ≈ 3.88%`, below `extraction/languages.py`'s
`MIN_SIGNIFICANT_PERCENTAGE = 5.0`. **`languages.py` correctly produces
NO `language.cpp` evidence for this repository** — confirmed by reading
the extractor and reproducing the percentage by hand; this was never the
source of the false positive.

**README** (`readme` field): the real `llm.c` README contains a
"## notable forks" section — a bullet list of OTHER people's separate,
externally-linked ports of the project, each describing its OWN tech
stack:

```
## notable forks

- CUDA C++
  - [llm.cpp](https://github.com/gevtushenko/llm.c) by @gevtushenko:
    a port of this project using the CUDA C++ Core Libraries
- C++/CUDA
  - [llm.cpp](https://github.com/zhangpiu/llm.cpp/...) by @zhangpiu:
    a port of this project using Eigen, supporting CPU/CUDA
- WebGPU C++
  - [gpu.cpp](https://github.com/AnswerDotAI/gpu.cpp) by @austinvhuang:
    a library for portable GPU compute in C++ using native WebGPU
```

Before this milestone, `extraction/readme.py`'s alias matcher
(`"c++"`/`"cpp"`, `language.cpp`'s `readme_safe_aliases()`) ran a plain
word-boundary `.search()` over the ENTIRE README text with no notion of
section structure. The first of these three "C++" occurrences
(offset 13287 of the full README text) is what produced the Evidence:

- **Extractor:** `evidence/extraction/readme.py`, `EXTRACTOR_VERSION =
  "readme:v3"` (pre-fix)
- **Exact text:** `"...gevtushenko: a port of this project using the
  [CUDA C++ Core Libraries]..."` — describing `llm.cpp`
  (`gevtushenko/llm.c`), a DIFFERENT repository by a DIFFERENT author
- **Evidence type / confidence:** `EvidenceType.README`,
  `ConfidenceLevel.MODERATE`
- **Why attributed:** the matcher has no concept of "which repository
  is this sentence actually describing" — a textually-correct alias
  match was unconditionally credited to `llm.c` itself

**Verdict:** genuine false positive, not a stale/incorrect gold
annotation. `evaluation/gold_v1_1/candidates/karpathy.json`'s
`not_expected_concepts` entry for `llm.c` -> `language.cpp` (already
present before this milestone) correctly anticipated this; the
production code had not yet been fixed to match.

**Same mechanism, confirmed elsewhere (not a one-off):**
- `karpathy/llama2.c`'s own "## notable forks" section mentions
  `llama2.ts`, "a TypeScript port of this project" by a different
  author (`wizzard0/llama2.ts`) — the identical pattern, independently
  discovered, inside the SAME candidate's own repository set.
- Most of `sindresorhus`'s small-library READMEs carry a ubiquitous
  "## Related" section linking to the AUTHOR'S OTHER packages — the
  same structural category (a section that lists things other than this
  repository's own stack), observed directly in the fixtures
  (`eslint-plugin-unicorn`, `wallpaper`, `electron-dl`, `type-fest`,
  `image-dimensions`, `file-type`, `Gifski`, `ky`, `ow`,
  `KeyboardShortcuts`).

This confirms the fix targets a structural attribution mechanism, not a
single benchmark case.

## 2. Is this a genuine false positive or an annotation problem?

Genuine false positive. GitHub's own language statistics (the
structured, authoritative source) already say C++ is below
`languages.py`'s significance floor for this repository; the README
mention is of a DIFFERENT repository's tech stack, introduced in a
"notable forks" section whose explicit editorial purpose (stated in the
README's own prose: *"I'd like this repo to only maintain C and CUDA
code. Ports to other languages or repos are very welcome, but should be
done in separate repos"*) is to list work the author explicitly
disclaims as not part of this repository.

## 3. Could the same mechanism affect other concepts?

Yes — confirmed, not hypothetical (Section 1's "same mechanism,
confirmed elsewhere"). Any concept whose `readme_safe_aliases()` text
appears inside a README's forks/related-projects/acknowledgements/
references section is subject to the identical misattribution,
regardless of which technology it is. This is why the fix is a
source-aware, per-CONTEXT policy (Section 4), not a per-technology
blacklist on "cpp".

## 4. Design chosen

New module, `gitscore.evidence.extraction.readme_context`, providing
two independent, deterministic, bounded signals (no fuzzy inference, no
embeddings, no LLM):

1. **Section-heading denylist** (`NON_IMPLEMENTATION_SECTION_HEADINGS`)
   — a match whose nearest preceding markdown heading (normalized:
   lowercased, markdown emphasis/trailing punctuation stripped,
   whitespace collapsed; headings inside fenced code blocks ignored so
   a shell comment is never mistaken for a section boundary) is one of
   `{"notable forks", "forks", "related", "related projects", "related
   work", "see also", "alternatives", "similar projects", "inspired
   by", "acknowledgements", "acknowledgments", "credits", "references"}`
   is excluded. Directly evidence-grounded for `"notable forks"`,
   `"related"`, `"acknowledgements"`, `"references"` (all directly
   observed in real fixture READMEs, Section 1); the remaining entries
   are a documented, modest generalization of the same convention.
2. **Local adjacency cues** (`_PRECEDING_EXCLUSION_CUES` /
   `_FOLLOWING_EXCLUSION_CUES`) — a small, curated, DIRECTIONAL set of
   negation/future-intent phrases ("unlike", "does not use", "is on the
   roadmap", "coming soon", ...) checked in a fixed 60-character window
   immediately before/after the match. See Section 5 for why this is
   local, not whole-sentence.

`evidence/extraction/readme.py`'s matching loop changed from a single
`.search()` per alias to `.finditer()` over every occurrence, skipping
excluded ones and falling through to the next occurrence, then the next
alias, if every occurrence found so far is excluded — a concept's first
textual occurrence being excluded no longer discards the whole concept.
`EXTRACTOR_VERSION` bumped `readme:v3` -> `readme:v4`.

**Why this, not a `language.cpp`-specific exclusion:** the milestone's
own constraint ("no technology-specific hacks to satisfy one benchmark")
and Section 3's confirmed cross-repository/cross-technology recurrence
both rule it out — a per-alias blacklist would have fixed `llm.c` alone
and left `llama2.c`'s identical TypeScript misattribution (Section 1)
completely unaddressed.

**Why not a confidence downgrade instead of suppression:**
`matching/support.py`'s `MINIMUM_SUPPORTING_CONFIDENCE =
ConfidenceLevel.WEAK` means ANY confidence tier (including the weakest)
is already sufficient for `match_requirement()` to call a concept
`SUPPORTED` — downgrading README evidence from `MODERATE` to `WEAK`
would not have changed the matcher's verdict at all, and matcher
threshold changes are explicitly out of this milestone's scope.
Suppressing the Evidence at its source, before it's attributed, is the
only change that stays within scope and actually fixes the attribution
error.

## 5. Precision/recall tradeoff — presented, not silently chosen

A whole-sentence cue scan (flag a match if ANY exclusion phrase appears
anywhere in its sentence, not just adjacent to it) was prototyped
against real fixture text and REJECTED. Real examples found during
investigation:

- `karpathy/nanochat`: *"nanochat does not use `torch.amp.autocast`."*
  — "does not use" correctly excludes this specific `torch` mention.
- A hypothetical but structurally common pattern: *"Built in Python
  instead of C for portability."* — "instead of" appears in the SAME
  sentence as BOTH "Python" (affirmed) and "C" (negated). A
  whole-sentence scan keyed on "instead of" cannot tell which side of
  the sentence a given match is on without sentence-structure parsing —
  exactly the "no NLP" boundary this milestone must not cross. Flagging
  the whole sentence would wrongly suppress the genuine, affirmed
  Python mention alongside the correctly-excluded C one.

**Decision made:** restrict adjacency cues to a SMALL, bounded,
DIRECTIONAL set, checked in a FIXED, LOCAL window immediately
before/after the match (not the whole sentence) — a cue's position
relative to the match unambiguously determines what it negates for
every cue in the chosen set ("unlike X" always negates the X that
immediately follows; "X is on the roadmap" always defers the X that
immediately precedes). Generic comparison cues ("instead of", "rather
than", "versus", "compared to") are deliberately EXCLUDED from the cue
list for this reason — not an oversight, a scope boundary. This means:

- **Caught:** "Unlike the Python implementation, this is written in
  C" (mission's own illustrative example) — "unlike" immediately
  precedes "Python".
- **Not caught, by design:** "We use Y, not the X approach other
  projects take" or any comparison where the negated term is not
  immediately adjacent to a directional cue word. Left as a documented
  limitation (`docs/ARCHITECTURE.md` §27.5), not guessed at.

No matcher-threshold change was made or considered necessary to
implement this decision — it is entirely contained in the extraction
layer.

## 6. Positive and negative controls

All added to `tests/test_evidence_extraction_readme.py` and
`tests/test_evidence_extraction_readme_context.py`. Built from actual
fixture evidence where available (the `llm.c` regression), synthetic
for the rest (per the milestone's own "synthetic cases are acceptable
for focused regression tests" allowance):

| Category | Test | Result |
|---|---|---|
| Regression (real fixture text) | `test_known_false_positive_regression_karpathy_llm_c_notable_forks` | `language.cpp` absent; `platform.cuda`/`ml.framework.pytorch` still present |
| Positive — genuine implementation statement | `test_cpp_mentioned_outside_any_excluded_section_still_matches` | matches |
| Positive — genuine occurrence survives alongside an excluded one | `test_genuine_mention_elsewhere_survives_even_when_forks_section_also_matches` | matches |
| Positive — dependency-flavored statement | `test_dependency_style_statement_still_matches_outside_excluded_context` | matches |
| Negative — comparison ("unlike X") | `test_comparison_only_mention_is_excluded` | excluded |
| Negative — external reference section | `test_external_reference_section_mention_is_excluded` | excluded |
| Negative — explicit non-use | `test_explicit_non_use_statement_is_excluded` | excluded |
| Negative — future intention without implementation | `test_future_intention_without_implementation_is_excluded` | excluded |

Plus 14 direct unit tests of `readme_context.py` itself
(`tests/test_evidence_extraction_readme_context.py`), including a
`"unlikely"`-does-not-falsely-trigger-`"unlike"` boundary-safety case
and a fenced-code-block heading-false-positive case.

## 7. Evaluation — before/after

Run: `python scripts/evaluate_evidence.py --corpus-version 8c:v1.1`

| Metric | Before | After |
|---|---|---|
| Candidates evaluated | 4 | 4 |
| Ranking checks / misses | 10 / 3 | 10 / 3 (unchanged) |
| Concept checks found | 10/10 | 10/10 (unchanged) |
| Concept checks missing | 0 | 0 (unchanged) |
| **False positives** | **1** (`karpathy/llm.c` -> `language.cpp`) | **0** |
| Extractor failures | 0 | 0 (unchanged) |

**Recall impact: none, verified not assumed.** Every single
`expected_concepts` entry across all 4 gold candidates
(`evaluation/gold_v1_1/candidates/*.json`) has `"source":
"language_stats"` or `"source": "dependency"` — zero have `"source":
"readme"`. This was checked directly before implementing the fix, not
inferred after the fact: a change confined to `extraction/readme.py`
could only ever move the `False positives` number in this specific
benchmark, never `Found`/`Missing`. No legitimate evidence was lost
against the gold corpus.

**The frozen original `8c:v1` benchmark** (`python
scripts/evaluate_evidence.py`, no flag) is intentionally left
un-regenerated in the committed `evaluation/reports/evidence_report.*`
files, per the milestone's "keep the original 8C benchmark and
historical reports intact" instruction. Running it locally (not
committed) shows the identical drop: `evaluation/gold/candidates/
karpathy.json` carries the SAME `not_expected_concepts` entry as
`gold_v1_1`, so false positives there drop `2 -> 1` — the remaining `1`
is `sindresorhus/Gifski` -> `language.swift`, a pre-existing, unrelated
stale annotation (predates `language.swift`'s registration in the
concept registry) that this milestone does not touch.

## 8. End-to-end consequence

`python scripts/evaluate_end_to_end.py` (`evaluation/reports/
end_to_end_report.*`, also left un-regenerated in committed form for
the same reporting-discipline reason) was run locally to check whether
the job-fit matrix changes. Exactly one of 12 candidate x job pairs
changes:

| candidate | job_id | expected_direction | alignment (before -> after) | required (before -> after) |
|---|---|---|---|---|
| karpathy | frontend_01 | negative | 80 -> 60 | (4,4) -> (3,4) |

Traced directly, not assumed: `karpathy/llama2.c`'s own "## notable
forks" section mentions `llama2.ts`, "a TypeScript port of this
project" by a different author in a different repository (Section 1) —
the exact same misattribution mechanism as the driving `llm.c` case,
previously inflating this account's apparent `language.typescript`
evidence and, through it, its alignment against a Frontend Engineer
posting on an explicitly negative-control pair (an ML-focused account
evaluated against a frontend job, where LOW alignment is the expected,
correct outcome). The score moving further in the correct direction for
a labeled-negative scenario is the intended effect of fixing a false
positive, not a regression — confirmed by inspecting
`profile.evidence` directly before and after the fix, which shows
`language.typescript` present for `karpathy` before and absent after,
with every other required concept (`language.javascript`,
`framework.react`, `language.css`) unaffected and still correctly
supported from genuine sources (`convnetjs`'s/`llm-council`'s actual
language stats and README content).

No other pair in the matrix changes — confirming the fix's blast radius
matches what Sections 1–4 predicted (README-sourced evidence only).

## 9. Known limitations

See `docs/ARCHITECTURE.md` §27.5 for the full list (comparison cues
intentionally excluded; fixed 60-character adjacency window, not a real
sentence boundary; heading denylist partly evidence-grounded/partly a
documented generalization; the separate, out-of-scope `llama.cpp`-style
proper-noun/alias collision mechanism; ATX-only heading detection).

## 10. Versions changed / unchanged

- `EXTRACTOR_VERSION` (`extraction/readme.py`): `readme:v3` -> `readme:v4`.
- Unchanged: `EVIDENCE_SCHEMA_VERSION` (`2`), `CONCEPT_REGISTRY_VERSION`
  (`4`), `REPOSITORY_RANKING_VERSION` (`1`), `JOB_RELEVANCE_VERSION`
  (`1`), `JOB_DESCRIPTION_PARSER_VERSION`, `JOB_REQUIREMENT_SCHEMA_VERSION`,
  `MATCHER_VERSION`, `SCORING_VERSION`. No concept added, renamed, or
  removed in `concepts/registry.py`. `Evidence`,
  `CandidateEvidenceProfile`, `RepositoryAnalysisCoverage` shapes
  unchanged. `match_job()`/`assess_job()`/`matching/support.py`'s
  `MINIMUM_SUPPORTING_CONFIDENCE` unchanged. The HTTP API contract and
  frontend are unchanged — no frontend/typecheck/build re-verification
  was run this milestone, since nothing shared-contract-relevant
  changed.

## 11. How to reproduce

```
python -m pytest                                              # 864/864
python scripts/evaluate_evidence.py --corpus-version 8c:v1.1  # False positives: 0
python scripts/evaluate_evidence.py                            # local only, not committed: False positives 2 -> 1
python scripts/evaluate_end_to_end.py                           # local only, not committed: karpathy x frontend_01 changes
```
