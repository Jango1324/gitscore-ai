# GitScore AI — Dev Changelog

## 2026-11-11 — Milestone 11-G22-R2: README evidence context and confidence (research only; no production change)

**What changed:** Research and design only, committed as a research-only commit ("test: evaluate README evidence context precision") after authorization.

- **Unchanged:** `src/` and registry data; parser v15, scoring v2, matcher v1, `readme:v4`, registry 4.
- **Controls:** new frozen synthetic README control sets, DEV (44) and EVAL (40), with use / reference / future / historical / negated / ordinary labels, G14 portable freezes registered in the canonical manifest at the research commit with their original freeze-time hashes (19 → 21 entries; the previous 19 unchanged), and a policy-design freeze taken before EVAL ran.
- **Research code:** offline policy adapters A–F, a post-hoc variant D2 (not validated), a harness over the real evidence pipeline, a runner, and a pytest plugin that measures existing tests under each policy.
- **Outputs:** a public report and counts-only private aggregates.
- **Tests:** 21 research tests. G22-R's hard-coded "manifest has exactly 19 entries" assertion (`tests/test_m11g22r_ambiguous_alias_evidence.py`) now pins the manifest at G22-R's commit `13f79fe` (19 entries, all still present field for field) instead.
- **Doc:** `docs/evaluation/MILESTONE_11_G22R2_README_EVIDENCE_CONTEXT.md`.

**Accepted interpretation:** policy D is the recommended baseline for a future `readme:v5`, **not an approved production fix**. D2's blanket preposition cues are not authorized. Registry v4, aliases and G19 capability stay unchanged; matcher v1 and scoring v2 stay unchanged. A README claim is not proof of competence. Fresh, preferably independently authored validation is required before a production commit.

**Why:** G22-R showed that `readme:v4` turns ordinary English, references and future plans into MODERATE README evidence. That evidence alone makes a requirement SUPPORTED.

**How it works:** Policies wrap the existing per-occurrence filter `readme.is_non_implementation_mention`. Policy E additionally reinterprets the profile. The job parser, registry and capability are never touched (verified).

**Measured** (false SUPPORTED, DEV / EVAL):

| Policy | False SUPPORTED | Genuine use claims kept, EVAL |
|---|---|---|
| Current | 21 / 18 | 19/19 |
| G22-R D (README side) | 8 / 6 | 14/19 |
| D (per-alias collocates + non-use frames) | 0 / 1 | 16/19, with all ordinary text rejected |
| E, F (corroboration / strict) | 0 / 0 | 5/19 |

- D's non-use frames generalised to none of EVAL's phrasings; the collocates do the work.
- D loses three genuine EVAL use claims: "image diffing in Rust", "python plotting helper" and "Analysis with pandas" (the last stays SUPPORTED via the manifest). These are separate from G22-R's own controls (baseline 21 / 20), where D loses "with pandas", "trained with torch" and "store in Rust".
- **Real 8c (simulated, not deployed):** `readme:v4` credits torvalds with Java, Ruby, Rust and Swift from libgit2's list of other projects' bindings. Under D those would be removed and torvalds/systems_cpp_01 would go 67 → 33, a correction (post-hoc review, not independent gold). D has one genuine occurrence loss (Gifski Rust; the concept stays evidenced).
- All 126 real README items are MODERATE; 32 have neither a use claim nor corroboration.

**Risks / limitations:**

- The synthetic controls were written by the same author, so they are not independent. EVAL is weakly held out.
- **Unresolved by local rules:**
  - capitalised homonyms next to generic collocates ("A Java coffee app");
  - "in X" place versus use (D2 trade-off);
  - unseen reference phrasing ("borrowed from Express");
  - lowercase genuine mentions with no collocate.
- D2 is post-hoc and not validated.
- G21-n10 is a job-side case (G22 B head nouns) that README policies cannot reach.

**How to test:**

- `python -m pytest tests/test_m11g22r2_readme_evidence_context.py`
- `python scripts/evaluate_m11g22r2_readme_context.py --private-corpora`

## 2026-11-11 — Milestone 11-G22-R: ambiguous alias and README evidence audit (research only; no production change)

**What changed:** Research only, committed as a research-only commit ("test: evaluate ambiguous alias README evidence") after authorization.

- **Unchanged:** `src/`; parser v15, scoring v2, matcher v1, `readme:v4`.
- **Controls:** frozen synthetic DEV (40) and EVAL (36) alias/evidence controls with G14 portable freezes, plus a policy-design freeze.
- **Manifest:** both freezes registered in `evaluation/integrity/canonical_hash_manifest.json` with their original freeze-time hashes (17 → 19 entries; the previous 17 are unchanged).
- **G22 test update:** `tests/test_m11g22_concept_recognition_research.py`'s hard-coded "exactly 17 manifest entries" now pins the manifest at G22's commit `fad7c6d` (17 entries, all still present field for field).
- **Research code:** offline policy adapters, a harness using the real evidence pipeline, a runner, and a pytest plugin that measures existing tests under each policy.
- **Outputs:** a public report and counts-only private aggregates.
- **Tests:** 21 research tests.
- **Doc:** `docs/evaluation/MILESTONE_11_G22R_AMBIGUOUS_ALIAS_EVIDENCE.md`.

**Why:** G22 measured false job-side concept recognition. The README evidence path shares the same alias table and boundary regex, and its effect on SUPPORTED had not been measured.

**How it works:** Synthetic repositories go through `extract_candidate_evidence` via the 8c offline fixture client. Jobs go through the real parser, then `match_job` and `assess_job`. Policies patch `readme.is_non_implementation_mention` per occurrence and reuse G22's job-side adapters.

**Measured:**

- **BASE:** every ordinary-English README use of react, express, swift, rust, ruby, shell, torch, flask, pandas, python or java became MODERATE README evidence. With a matching requirement it became a counted SUPPORTED scoring 100. False SUPPORTED: DEV 21, EVAL 20 (14 each from README extraction).
- **Structured extractors:** language, manifest and Docker extractors produced 0 false evidence.
- **Policy D** (per-alias metadata, separate job and README cue rules):
  - false SUPPORTED: DEV 21 → 5, EVAL 20 → 7;
  - false job concepts → 0;
  - genuine README and job recall kept on both sets;
  - 0 frozen 8c score changes; 337/337 existing extractor, pipeline, capability and parser tests pass.
- **Occurrence guards** leave G19 capability unchanged. Editing `readme_unsafe_aliases` instead would make Flask and pandas NOT_ASSESSABLE and stop job-side recognition of React, Express, Python and others.
- **Study R** (README-only evidence insufficient) drops 47 of 126 real 8c README items and lowers 4 frozen 8c pairs in each matrix version. It is a semantic change and not recommended as a small fix.

**Risks / limitations:**

- The synthetic controls were written by the same author, so they are not independent validation. EVAL is only weakly held out.
- **D's README residuals:** inherited `of`/`and` lead-in cues, and capitalised homonyms (Ruby, Java).
- **Mention without use** stays SUPPORTED.
- **D's job side loses React on G21-n10**, as G22 already measured.
- **M10E-g3** is unchanged.
- **d22 label erratum:** recorded, and the frozen control is not edited.

**How to test:**

- `python -m pytest tests/test_m11g22r_ambiguous_alias_evidence.py`
- `python scripts/evaluate_m11g22r_alias_evidence.py --private-corpora`

## 2026-11-10 — Milestone 11-G22-Q: canonical alias-equivalence correction (parser v15)

**What changed:** One production logic change plus a version label, committed as "fix: canonicalize equivalent technology alternatives" after authorization.

- **`src/gitscore/jobs/parsing/alternatives.py`:**
  - new `equivalent_alias_concept_id()`;
  - `classify_alternative_claim()` now runs the unchanged v14 classification (renamed `_classify_alternative_structure`) and converts only an `unsafe` result with an established equivalence into `not_technical`.
- **`src/gitscore/jobs/parsing/parser.py`:** `JOB_DESCRIPTION_PARSER_VERSION` `v14` → `v15`, the label only.
- **Unchanged:** scoring `github_evidence_alignment:v2`, matcher, extractors, registry, concepts.py, qualification_intent.py, necessity.py, segmentation.py, schemas, API and frontend.
- **Tests:**
  - `tests/test_m11g22q_canonical_alias_equivalence.py` (75 tests, written red-first against v14);
  - explicit v15 branches in 14 existing test files.
- **Evaluation:**
  - `scripts/evaluate_m11g22q_v14_v15.py`;
  - `scripts/evaluation_lib/m11g22q_parser_dump.py`;
  - `evaluation/m11g22q/v14_v15_comparison.json`;
  - `evaluation/m11g22q/private_v14_v15_aggregates.json` (counts only).
- **Doc:** `docs/evaluation/MILESTONE_11_G22Q_CANONICAL_ALIAS_EQUIVALENCE.md`.

**Why:** An OR between aliases of one concept ("Kubernetes or k8s", "Go or Golang") left fewer than two distinct ids. It was therefore classified `unsafe` and became a NOT_ASSESSABLE placeholder for a requirement that names exactly one technology. This contradicted the frozen gold of G15-I1, G18-16 and G13-o007, and G22's class-D controls. This is G22's Option Q, the only approved option.

**How it works:** An equivalence is established from canonical registry identity only. All of these must hold:

- the claim has a literal "or" and is not G17-structurally mixed;
- there are at least two alternatives, and each is a bare list item;
- each alternative resolves independently to the same registered id;
- each alternative is that id's alias in its entirety (`resolve_concept`);
- a full-claim scan finds only that id.

The parser's ordinary path then builds one `concept_id` row with the original text, span and necessity. Relation edges, similarity and candidate evidence are never consulted.

The "whole alias" condition was added during implementation. Without it, the real comparison merged G13-o012 "Docker or Docker Compose" (gold: related, non-equivalent) through the embedded "Docker".

**Measured** (real pinned v14 `fad7c6d` in a clone vs v15 working tree; real parser, matcher, scoring v2 and API serializer):

- 3 tracked placeholders recovered: G15-I1, G18-16 and G13-o007. Each now matches its frozen gold or expected scores.
- 88/88 OR groups preserved. 0 other row or UnparsedClaim changes.
- MatchStatus: not_assessable → supported ×2 and → not_observed ×2. No kept-row status change.
- Denominators: G15 19 → 21, G18 50 → 52. 4 scores became defined; 0 became undefined.
- 0 new false SUPPORTED. G16 claim-level false SUPPORTED stays 7 → 7.
- 0 changes on frozen 8c v1/v1.1, M10, M10D, M10E, G6, G7, G16, G20 and G21.
- G22 synthetic controls: EVAL exact 22 → 25 of 44 (DEV 29 → 30 of 45). False registered, fabricated `unresolved:` and false SUPPORTED are all unchanged.
- 62 previously inspected private postings: 0 changed. These are not independent validation.
- The pinned clone reproduces G22's committed report byte-identically.

**Risks / limitations:**

- **Divergence from G22's simulation:** e25 "Bash or shell scripting" is not recovered, because "shell scripting" is not a registry alias.
- **Conservative recall:** when the first alternative carries lead-in prose ("3+ years of experience with Kubernetes or k8s") or a trailing "(preferred)", the claim stays a placeholder, as in v14.
- **Registry aliases are trusted:** "PyTorch or Torch" becomes one PyTorch row.
- **Out of scope and unchanged:** G22's false registered and fabricated concepts, bare "Go" and M10E-g3's counted SQL row.
- **Research-only guards:** five `git diff --quiet HEAD -- src` guards (G13, G15, G16, G18, G20) failed while the production change was uncommitted. They pass once it is committed.

**How to test:**

- `python -m pytest tests/test_m11g22q_canonical_alias_equivalence.py`
- `python scripts/evaluate_m11g22q_v14_v15.py --private-corpora`
- `python -m pytest tests`

## 2026-11-10 — Milestone 11-G22: technical concept recognition precision (research only; no production change)

**What changed:** Research only. No `src/` change. The parser stays v14, scoring stays v2, and the matcher and extractors are unchanged. Committed as a research-only commit after authorization.

- **Two frozen synthetic control sets** (`evaluation/m11g22/`): DEV (46) and a separately authored EVAL (44). Both were labelled before any parser run, use the G14 portable freezes, and are registered in the G14 manifest with their original pre-evaluation hashes (15 → 17 entries; additive, previous entries unchanged).
- **Policy-design freeze:** taken before EVAL ran. One recorded post-freeze change is a simulation-fidelity fix.
- **Offline policy adapters:** `scripts/evaluation_lib/m11g22_policies.py`, plus post-hoc variants in `m11g22_posthoc.py`. They patch only the recognition inputs of the real parser, in-process.
- **Harness and runner:** `m11g22_concepts.py` and `scripts/evaluate_m11g22_concept_precision.py`.
- **Report:** public, reproducible byte-identically, plus private aggregates (counts only).
- **Tests:** 25 research tests.
- **Doc:** `docs/evaluation/MILESTONE_11_G22_CONCEPT_RECOGNITION_PRECISION.md`.

**Why:** G20 and G21 deferred concept-recognition defects:

- ordinary English words ("react", "express", "swift", "torch", "shell", "rust") recognised as registry technologies, counted and SUPPORTED;
- single-word fragments ("curiosity", "teamwork", "Alternatively", "context", "Go") minted as `unresolved:` concepts;
- equivalent aliases ("Go or Golang") turned into a NOT_ASSESSABLE placeholder;
- bare "Go" not recognised.

**How it works:** Every wrong identity is created at one of three sites:

- `concepts.find_concept_mentions` (no usage check);
- `concepts._consider_fragment` (single-word exemption from M11-A1's shape gate);
- `alternatives._classify_segment_list` (one concept named twice is treated as `unsafe`).

After `parser._requirements_from_claim` builds the row, the identity is only an id. The matcher and scoring v2 cannot recover from it.

**Measured** (live v14; "false SUPPORTED" assumes a candidate with evidence for the falsely recognised technology):

| Set | Counted false concepts | Fabricated `unresolved:` (excluded by v2) |
|---|---|---|
| DEV | 9, all SUPPORTED | 6 |
| EVAL | 7, all SUPPORTED | 9 |

Options, with costs measured across DEV, EVAL and the historical corpora:

| Option | What it does | Effect | Cost |
|---|---|---|---|
| A | Usage guard, no metadata | Counted false concepts DEV 9→4, EVAL 7→3 | 0 recall loss |
| B | Reviewed 7-alias metadata + positive cue | Counted false concepts → 0 on DEV and EVAL | Loses Ruby and one G21 React |
| C | Fragment validation | Fabricated DEV 6→0, EVAL 9→2 | Loses Plotly; no score effect |
| Q | Alias equivalence | Fixes the frozen-gold discrepancies G15-I1 and G18-16 | none measured |
| G | Cue-gated capitalised "Go" | +7 historical and +1 private genuine Go rows; contains G16-018 (G16 false SUPPORTED 7→4) | none measured |

- **Historical:** 0 regressions on 456 tracked texts apart from the costs listed. 8c and M10 scores are unchanged, admission is identical, and spans are exact.
- **Private** (62 postings, counts only): 0 changes under every option except G (1 posting).

**M10E-g3:** the frozen gold is correct and internally consistent:

- `should_create_job_requirement=true` and `technical_concepts_may_enter_scoring=false` are both present, and no gold field names SQL.
- The M10E test projects only row existence, which v14 satisfies through the SQL row from the learning clause; that row violates the second field.
- Clause scoping alone (G20 C / G22 E) breaks the gold.
- Not rewritten.

**Files affected (all new):**

- `evaluation/m11g22/*`
- `evaluation/integrity/canonical_hash_manifest.json` (+2 entries)
- `scripts/evaluate_m11g22_concept_precision.py`
- `scripts/evaluation_lib/m11g22_{build_controls,policies,concepts,posthoc}.py`
- `tests/test_m11g22_concept_recognition_research.py`
- `docs/evaluation/MILESTONE_11_G22_CONCEPT_RECOGNITION_PRECISION.md`
- this entry

**Risks / limitations:**

- Same-author controls; EVAL is only weakly held out.
- Post-hoc variants (B2, C2, DB2) are not validated.
- Low real-world prevalence on the inspected private sample.
- `unresolved:context` and embedded-C-beside-FreeRTOS remain open.

**How to test:**

- `python -m pytest tests/test_m11g22_concept_recognition_research.py`
- `python scripts/evaluate_m11g22_concept_precision.py [--private-corpora]` (regenerates the report byte-identically)

**Recommended next:** separate milestones, in this order:

1. Q (alias equivalence; `alternatives.py`)
2. A (usage guard)
3. C2 (fragment validation, after fresh validation)
4. G and B (each need a decision)

The ordering relative to the reserved G23 headings milestone needs approval.

## 2026-11-10 — Milestone 11-G21: qualification-intent admission guard (production; parser v13 -> v14)

**What changed:** New `src/gitscore/jobs/parsing/qualification_intent.py` (G20's evaluated B1NR admission
decision: closed grammatical qualification / non-qualification frames per clause). `parser.
_requirements_from_claim` calls it first; a declined claim returns [] and becomes the existing
`UnparsedClaim`. `necessity.refine_necessity()` (new, called by the parser after the unchanged
`infer_necessity`) only narrows necessity: concession -> PREFERRED, negated REQUIRED -> PREFERRED or no row,
REQUIRED + soft cue -> PREFERRED. `JOB_DESCRIPTION_PARSER_VERSION` v13 -> v14. Scoring v2, matcher,
segmentation, headings, alternatives (G17), concepts, API and frontend unchanged.

**Why:** G20 traced false qualifications (company narrative, duties, technology discussion scored as
REQUIRED) to the absence of any qualification-intent decision (G18 control 25, G17 control 053).

**How it works:** a claim is declined only on POSITIVE evidence of a non-qualification frame (employer
subject, future duty, learning, benefit, hiring process, technology-as-subject, team practice, negation,
inline "About us:", bare duty verb in a qualifications section); a strong candidate frame or a marker
attached to an attribute in the same clause overrides. Includes G20's two post-hoc corrections
(case-sensitive "us" vs "US"; concessive "while not required ... a plus").

**Measured (real v13 at a260282 vs v14):** G20 dev false admissions 26 -> 0, held-out 16 -> 1 (h003 "You
must be on call ..." -- documented), necessity 46/46 and 19/19, near-neighbour pairs 12/12 and 4/4; live v14
equals G20's frozen B1NR research aggregates exactly. Historical: only G16-053 and G18-25 change (both gold
fixes), 0 regressions, 0 frozen-8c score changes, G17 guard 0 violations, no status/eligibility change on any
kept row. Private (inspected, counts only): 0 qualifications lost, necessity 231 -> 233/242. Fresh adversarial
synthetic set (35 controls, same author, not independent): false admissions 17 -> 11, 2 genuine
qualifications lost (whole-claim negation; "preferred but not essential").

**Files affected:** `src/gitscore/jobs/parsing/{qualification_intent (new),necessity,parser}.py`;
`tests/test_m11g21_qualification_intent.py` (new) and version-aware updates to m11a2/m11b/m11c/m11e/G15-G20
tests (v13 checks kept); `scripts/evaluate_m11g21_v13_v14.py`, `scripts/evaluation_lib/m11g21_{parser_dump,
build_adversarial}.py` (new); G20 evaluator v13-only guard; `evaluation/m11g21/*`; docs.

**Negation-scope correction (Option B, same milestone):** the first v14 lost 2 genuine qualifications on
the fresh adversarial set ("A degree is not required; strong Python skills are."; "TypeScript is preferred but
not essential."). Negation is now clause-local: subjectless "but"-continuations join the clause they complete;
a negated unit is masked (offsets kept) out of the text the parser analyses when another unit is a
qualification; the only ellipsis resolved is a contrast after an explicitly negated predicate;
`refine_necessity(..., full_text=)` resolves it. Result: adversarial losses 2 -> 0, false admissions unchanged
at 11, necessity 18/18 -> 20/20; G20, historical corpora, scoring and private counts identical to the first
v14; new author-created negation-scope set 4/16 (v13) -> 14/16. The 35 adversarial controls are development
data now. Files: also `parser.py` (scoped analysis text), `scripts/evaluation_lib/m11g21_build_negation_scope.py`,
`evaluation/m11g21/{negation_scope_*,v13_v14_revised_comparison,private_v13_v14_revised_aggregates}.json`.

**Risks / limitations:** strong-subject duties ("You must be on call", "Applicants must complete") and
company sentences without a We/Our subject still pass; "No prior <tech> experience is necessary" is outside
the negation vocabulary; per-clause necessity in one sentence ("X is required; Y is preferred") is decided per
claim; G6 candidate-profile headings (G23) and fabricated
concepts (G22) untouched.

**How to test:** `python -m pytest tests/test_m11g21_qualification_intent.py`;
`python scripts/evaluate_m11g21_v13_v14.py [--private-corpora]`.

## 2026-11-10 — Milestone 11-G20: false qualification admission & parser precision (research only)

**What changed:** Research, evaluation and design only -- no production code changed (parser v13, scoring
v2, matcher, API and frontend byte-identical to `2144fe6`). New frozen synthetic control sets
(`evaluation/m11g20/admission_controls_{dev,holdout}.json`, 71/36 controls, 103/46 gold units, labelled and
frozen before the parser ran; G14-portable freeze records, registered as canonical-manifest entries 12-13, 11 -> 13), a
policy-design freeze record, a research tracer/replica with policy hooks, three candidate approaches plus
ablations, a historical/private impact harness, the evaluation report, integer-only private aggregates, and
26 focused tests.

**Why:** G18 control 25, G17 control 053 and G19's residual list showed the live parser admitting company
narrative, responsibilities and generic words as REQUIRED technical requirements, which scoring v2 then
counts.

**How it works:** `scripts/evaluation_lib/m11g20_admission.py` replicates only the `segment_description()`
and `_parse()` loops (asserted identical to production on 405 texts) and calls the real production helpers
for every decision; policies plug in as hooks. Root cause: v13 never decides qualification intent --
in-section claims are admitted unconditionally, unsectioned claims default to REQUIRED, a local marker always
wins, and concept recognition has no usage check.

**Measured:** v13 false admissions 26/45 (dev) and 16/18 (held-out) synthetic non-qualification units, 30/18
false rows SUPPORTED and counted for an all-evidence candidate; 6/4 fabricated concepts. Recommended slice
B1NR (clause-level non-qualification frames + necessity refinement): 0/45 and 1/18, 0 legitimate
qualifications lost, necessity 46/46 and 19/19, 0 regressions on G15/G16/G18/M10D/M10E/G6/G7 gold, G17
containment byte-identical, frozen 8c scores unchanged. Real annotated private postings: v13 4/153 false
admissions (none scored); B1NR loses 0 of 497 qualifications (post-hoc, after two frame defects were found
on that data). A "require positive intent" variant was rejected (destroys 5 M10D bare lists).

**Files affected:** `docs/evaluation/MILESTONE_11_G20_FALSE_QUALIFICATION_ADMISSION.md` (new),
`evaluation/m11g20/*` (7 new), `scripts/evaluate_m11g20_false_qualification.py`,
`scripts/evaluation_lib/m11g20_{build_controls,admission,policies,posthoc,historical}.py`,
`tests/test_m11g20_false_qualification_admission.py`; `evaluation/integrity/canonical_hash_manifest.json`
(+2 entries); this changelog.

**Risks / limitations:** self-authored controls (not blind; held-out only weakly held out); synthetic rates
are not prevalence; the two frame fixes are post-hoc for the previously inspected private sets (1: case-insensitive "us"
matched "US"; 2: "while not required, ... is a plus" treated as a general negation) -- known G21 risks; candidate-profile headings would
change 18 frozen G6/G7 heading labels and need a separate decision.

**How to test:** `python -m pytest tests/test_m11g20_false_qualification_admission.py`;
`python scripts/evaluate_m11g20_false_qualification.py [--private-corpora]` reproduces the report.

## 2026-11-09 — Milestone 11-G19: observability-aware scoring v2 (production; scoring v1 -> v2)

**What changed:** A requirement now enters the GitHub Evidence Alignment numerator and denominator only
if the matcher evaluated it AND every acceptable alternative has a declared GitHub evidence-assessment
capability. New internal `src/gitscore/evidence/capability.py` (ASSESSABLE / NOT_ASSESSABLE / UNRESOLVED,
with reasons, derived from the README, language-stats and Docker extractors). `assessment/models.py`:
`score_eligibility()`, `counts_toward_alignment()`, `alignment_exclusion_reason()`; `_assessable_matches`
filters on eligibility and the numerator counts SUPPORTED within that set; `excluded_from_alignment_*`.
`assessment/types.py`: `SCORING_VERSION` v1 -> v2 and the closed `AlignmentExclusionReason` set. API
(additive): `RequirementOut.counts_toward_alignment`, `.alignment_exclusion_reason`,
`AssessmentOut.excluded_from_alignment_count`. Frontend: "Not counted in alignment score" badge with a
reason-keyed explanation on excluded supported/not-observed rows, a headline scope sentence and excluded
count.

**Why:** M11-G15/G18 measured mixed OR groups ("AWS or Azure") and standalone unresolved rows
(Terraform, NumPy, SPI) scored as NOT_OBSERVED although no extractor can ever evidence them: 27 wrong
NOT_OBSERVED (13 truly qualified) and 33 uncheckable rows on 106 frozen outcomes. G18's policy B/C was
approved for production.

**How it works:** eligibility is decided from the requirement alone (candidate-independent); an OR group
counts once or is excluded once; excluded rows keep MatchStatus, matched concepts and evidence. Formula and
half-up rounding unchanged; `None` when nothing is eligible. Parser (v13), matcher, extractors, registry,
`MatchStatus` and `JobRequirement` untouched.

**Measured (actual v1 at ac4a15e vs v2):** live v2 == G18 simulated policy C on 54/54 pairs; wrong
NOT_OBSERVED 27 -> 0; uncheckable scored 33 -> 2 (control 25's narrative parser defect); 0 status/evidence
changes in any corpus; 6/12 frozen 8c pairs change exactly as predicted; private corpora (inspected)
142 -> 71 denominator rows.

**Files affected:** `src/gitscore/evidence/capability.py` (new), `src/gitscore/assessment/{models,types,
__init__}.py`, `src/gitscore/api/{schemas,serialization}.py`; frontend `types/api.ts`, `lib/labels.ts`,
`components/{RequirementSection,AlignmentHeadline,ResultView}.tsx`, `app/globals.css`, `test/fixtures.ts`,
`__tests__/ResultView.test.tsx`, new `__tests__/AlignmentExclusion.test.tsx`; tests
`test_m11g19_observability_scoring_v2.py` (new, 22 red on v1), `test_assessment_engine.py` (8D.1 overturn
+ fixture migration), `test_api_routes.py`, G15/G16 version-aware reproducibility; G15/G18 research
fidelity assertions made scoring-version-aware (outputs unchanged); `scripts/evaluate_m11g19_v1_v2.py`,
`scripts/evaluation_lib/m11g19_scoring_dump.py`, `evaluation/m11g19/*`; docs.

**Risks / limitations:** unregistered GitHub languages (Elixir, MATLAB, ...) are conservatively excluded
(2/54 synthetic scores drop); fabricated `unresolved:` terms and other parser defects remain (now shown
as "not counted" rather than penalising); half of real technical rows leave the denominator, so scores
rise and become undefined more often.

**How to test:** `pytest tests/test_m11g19_observability_scoring_v2.py tests/test_assessment_engine.py`;
`cd frontend && npx vitest run && npx tsc --noEmit`; `python scripts/evaluate_m11g19_v1_v2.py
[--private-corpora]`.

## 2026-11-09 — Milestone 11-G18: observability-aware score eligibility (evaluation only, no production change)

**What changed:** Added an evaluation-only study of which requirements may legitimately enter the
GitHub Evidence Alignment score. New: frozen controls `evaluation/m11g18/eligibility_controls.json`
(26 controls, 54 candidate variants, 106 outcomes; G14-portable freeze), builder
`scripts/evaluation_lib/m11g18_build_controls.py`, capability classifier + policy simulation
`scripts/evaluation_lib/m11g18_eligibility.py`, runner `scripts/evaluate_m11g18_scoring_eligibility.py`
(report `evaluation/m11g18/eligibility_report.json`; opt-in counts-only private aggregates), regression
probe `scripts/evaluation_lib/m11g18_option_regression_probe.py`, 29 focused tests
`tests/test_m11g18_observability_aware_scoring.py`, and
`docs/evaluation/MILESTONE_11_G18_OBSERVABILITY_AWARE_SCORING.md`.

**Why:** Production counts every evaluable technical row in the denominator, including mixed OR groups
("AWS or Azure") and standalone `unresolved:` rows (Terraform, NumPy, SPI) that no extractor can ever
evidence, so they can only add NOT_OBSERVED. Measured: 27 false NOT_OBSERVED (13 for truly qualified
candidates) and 33 uncheckable rows counted on the frozen controls; 50 % of technical rows in the
(previously inspected) private corpora are of this kind.

**How it works:** `concept_capability()` derives ASSESSABLE / NOT_ASSESSABLE / UNRESOLVED from what the
extractors can emit (registry aliases, README-safe aliases, Docker detector; `unresolved:` ids are
UNRESOLVED because no GitHub-language vocabulary is declared). A requirement is score-eligible iff every
member is ASSESSABLE -- candidate-independent. Policies are simulated on real `RequirementMatch`
results with the unchanged production rounding.

**Risks / limitations:** synthetic controls by the same author; the capability contract excludes genuine
evidence for unregistered GitHub languages (2/54 synthetic pairs drop); 6/12 frozen 8c pairs would
change under a future scoring v2. Nothing is implemented: recommendation and approval questions are in
the milestone document.

**How to test:** `pytest tests/test_m11g18_observability_aware_scoring.py`;
`python scripts/evaluate_m11g18_scoring_eligibility.py [--private-corpora]`.

## 2026-11-09 — Milestone 11-G17: compound AND/OR containment (alternatives.py, approved production change)

**What changed:** Parser v12 flattened mixed AND/OR qualifications
("Docker or Kubernetes, and Python"; "Python and either Docker or
Kubernetes"; "Python or Go, and Docker or Kubernetes"; "at least two of
...") into ONE OR group, so a single alternative could satisfy a
requirement whose mandatory conjunct was missing. This is M10D's deferred
"Root Cause 6"; M11-G16 measured 106/414 claim-level false SUPPORTED on
its frozen controls. `src/gitscore/jobs/parsing/alternatives.py` (the only
file with behavioural changes) adds `is_structurally_mixed()` and
`_contain_mixed()`: a `technical` result is returned as `unsafe` when an
OR segment resolves to >= 2 distinct concepts, a comma item begins with a
conjunction, or a k>=2-of / both / all-of lead-in is present.
`src/gitscore/jobs/parsing/parser.py`: `JOB_DESCRIPTION_PARSER_VERSION`
bumped `v12` -> `v13` (label-only to that module).

**Why:** Option D exactly as evaluated in M11-G16 (structural guard, not
decomposition -- Option C was not approved). Routing to the EXISTING 6B.1
fallback (user decision) keeps the claim visible as a non-scoreable
`alternative_requirement` placeholder (NOT_ASSESSABLE, never in the
denominator, `interpretation_status="unparsed_placeholder"`, original
text/span/necessity kept) instead of a flat OR group.

**Files affected:** `alternatives.py`, `parser.py` (label);
`tests/test_m11g17_compound_logic_containment.py` (new, written before
the change: 10 red on v12, 18/18 green on v13); version-literal updates in
`tests/test_m11a2_*`, `test_m11b_*`, `test_m11c_*`, `test_m11e_*`;
`tests/test_m10d_*` e1/e2 now assert the contained `unsafe` outcome (M10D
pinned the v12 flattening precisely so this change would be deliberate);
G15/G16 tests made explicitly version-aware (their frozen v12 reports are
untouched); new `scripts/evaluate_m11g17_v12_v13.py`,
`scripts/evaluation_lib/m11g17_parse_dump.py`, `evaluation/m11g17/*`;
`docs/evaluation/MILESTONE_11_G17_SAFE_COMPOUND_LOGIC_CONTAINMENT.md`.

**How it works / measured result (real v12 clone vs v13, nothing
simulated):** false SUPPORTED 106 -> **7**/414 (99 eliminated, 0 new);
genuine compound claims declined 2 -> 24/43 (recall cost: 77 satisfied
outcomes no longer scored); 0 outcomes scored more favourably; G15 only K1
changes; frozen 8c:v1/v1.1 0/12 pairs change; SOTI/Manulife identical;
1/62 inspected private postings changes. Identical to G16's Option D
simulation.

**Risks / limitations:** residual false SUPPORTED from mixed-kind lists
without a conjunction ("Python, Docker or Kubernetes") and bare "Go";
"at least two of" without "or", "One of:" sub-lists, cross-sentence
"Alternatively" and responsibility misclassification remain; G15 Policy B
not implemented. The three research-milestone "production unchanged since
HEAD" guard tests fail only while this `src/` change is uncommitted.

**How to test it:**
```
.venv/Scripts/python.exe -m pytest tests/test_m11g17_compound_logic_containment.py -q
.venv/Scripts/python.exe scripts/evaluate_m11g17_v12_v13.py
```

## 2026-11-06 — Milestone 11-G7: section-boundary integrity fix (segmentation.py, approved production change)

**What changed:** `_classify_heading_line()`'s word-count shape gate
rejected ANY heading-shaped line over 7 words UNIFORMLY, regardless of
signal strength. When a genuine, long, colon/ALL-CAPS/Markdown-
terminated heading was misjudged as ordinary content, `current_kind`
(the single forward-carrying section state in
`segment_description()`'s loop) never updated, letting whatever
section was open BEFORE that line leak across the boundary into
content AFTER it. Confirmed, by direct execution, THREE severity
tiers — two newly discovered and more severe than this milestone's own
initial framing: a stale `UNKNOWN`/`LEARNING` state admits content at
worst as a diagnostic (never scored, LOW); a stale `REQUIRED`/
`PREFERRED` state admits content UNCONDITIONALLY, confirmed to
fabricate a scored, ASSESSABLE `JobRequirement` from responsibility
prose naming a real technology (HIGH); a stale `SKIP` state drops
content before a `Claim` exists, confirmed to SILENTLY, TOTALLY
SUPPRESS a genuine, locally-marked REQUIRED qualification — the exact
M11-G5 failure mode, now reachable by heading LENGTH alone (HIGH).

`src/gitscore/jobs/parsing/segmentation.py` (the only file with
behavioral changes): the existing `has_strong_shape_signal` computation
moved above the word-count decision (pure reordering), and the
word-count condition changed from a fixed `7` to `14 if
has_strong_shape_signal else 7`. ~5 changed lines.
`src/gitscore/jobs/parsing/parser.py`: `JOB_DESCRIPTION_PARSER_VERSION`
bumped `v11` -> `v12` (label-only to that module).

`evaluation/m11g7/boundary_controls.json` (new, 42 independently-
authored, synthetic controls across 16 categories; two disclosed,
same-session self-correction rounds before the final freeze — a
field-scope error, and a batch-verified family-matching correction,
neither touching any safety-relevant outcome) +
`tests/test_m11g7_section_boundary_integrity.py` (new, 137 tests,
written and run against the real classifier BEFORE implementation —
confirmed red on exactly the defect rows, confirmed green after, with
3 characterization tests updated post-fix to assert the new correct
behavior) + `scripts/evaluation_lib/m11g7_build_boundary_controls.py`/
`m11g7_preflight_check.py`/`m11g7_phase1_current_behavior.py`/
`m11g7_phase3_candidate_fix_simulation.py` (new, evaluation-only
harness and strategy-comparison simulation).

**Why:** Three strategies compared and simulated against production's
own real regexes before any `src/gitscore` edit: (A) uniformly raise
the cap for every line — fixes all 18 defect rows but wrongly
reclassifies a long, colon-terminated lead-in sentence introducing a
sub-list from inside an already-open section as a new heading
(demoting the bare one-word value that follows it out of its real
section), rejected; (B) remove the cap entirely for strong-signal
lines — same lead-in failure, plus mis-heading-ifies a deliberately
degenerate 42-word run-on clause, rejected; (C) the signal-dependent
branch above — 42/42 frozen controls matched, 0 regressions, every
adversarial lead-in/degenerate-run-on case passed. Selected and
implemented verbatim, on explicit approval.

**Measured result:** `tests/test_m11g7_section_boundary_integrity.py`:
137 passed, 0 failed. Full backend suite: 1595->**1732 passed**, 13
skipped unchanged, 2 xfailed unchanged (the two M11-G6 em-dash-case
xfails are confirmed unrelated — that control's heading is 5 words,
below even the unchanged weak-signal cap). Against the frozen 42-control
corpus: heading-kind mismatches 18->**0**, false requirement
fabrications 5->**0**, silent suppressions 1->**0**. End-to-end on the
three HIGH-severity controls (real `match_job`/`assess_job`,
deterministic empty candidate fixture): REQUIRED-tier fabrication
`assessable_count`/`alignment_score` 1/0 (corrupted) -> 0/None
(correctly undefined); SKIP-tier silent suppression 0/0 requirements
(total loss) -> a genuinely recovered, assessable `JobRequirement`
(`assessable_count=1`, `alignment_score=0` — the CORRECT effect of
recovering a real requirement this candidate shows no evidence for,
not a defect); PREFERRED-tier fabrication eliminated while the genuine
PREFERRED qualification on the same control is preserved. No scoring
formula change — the alignment-score changes measured above are the
direct, intended, legitimate effect of correcting the underlying
requirement set, never a change to how a score is computed from a
given requirement set.

**Risks/limitations:** the 14-word cap is a measured, disclosed,
bounded constant sized to this milestone's own 42-control corpus (max
13 words authored) with a 1-word margin — not independently re-derived
from a larger real-world heading-length survey; a genuine heading
longer than 14 words would still be missed. This defect is confirmed
independent of the separately-measured competency-recall limitation
(different module, zero overlap) — this fix has no bearing on that
limitation and does not attempt to address it. No scoring/matcher/
schema/API/frontend/competency-evidence/LLM change of any kind.

**How to test:** `pytest tests/test_m11g7_section_boundary_integrity.py`;
`python scripts/evaluation_lib/m11g7_phase1_current_behavior.py`
(hash-verifies the frozen corpus first); full suite via `pytest -q`.

See `docs/evaluation/MILESTONE_11_G7_SECTION_BOUNDARY_INTEGRITY.md` for
the full root-cause trace, strategy comparison, and before/after
reconciliation.

## 2026-11-06 — Milestone 11-G6: heading-classification correctness fix (segmentation.py, approved production change)

**What changed:** M11-G5's independent validation traced 7 of 8 missed
qualifications on one real posting to a single root cause in
`segmentation.py`: `_NON_QUALIFICATION_ROOT`'s unanchored substring
match `\bwho we are\b` fires identically on genuine company-narrative
headings ("Who We Are:") and on unrelated candidate-profile headings
that merely start the same way ("Who We Are Looking For:"), because
nothing else on the second heading's line matches any other family, so
the existing "more than one family -> honest `UNKNOWN`" collision rule
never engages. The result is `_SectionKind.SKIP` -- total,
unrecoverable suppression (zero `Claim`s, not even a diagnostic),
upstream of `necessity.py`'s own local-marker-always-wins safety net,
and explicitly excluded from M11-G4's own recovery pass by design.

`src/gitscore/jobs/parsing/segmentation.py` (the only file with
behavioral changes): a new, generic, closed-vocabulary
`_CANDIDATE_PROFILE_ROOT` constant ("looking for" / "we need" / "we
want" / "you('ll) bring" / "ideal candidate") is added near the other
root-word tables, and `_matched_heading_families()`'s `NON_QUALIFICATION`
firing condition changes from `if has_non_qualification:` to
`has_non_qualification and not has_candidate_profile` -- mirroring the
EXISTING `qualification`-excluded-by-`preferred` precedent already
shipped in the same function. The new signal is NEVER added to
`families` itself, so it can never become its own section kind and
never defaults anything to REQUIRED/PREFERRED; a rescued heading falls
through to the EXISTING, already-tested "zero families + strong shape
signal -> `UNKNOWN`" path. `src/gitscore/jobs/parsing/parser.py`:
`JOB_DESCRIPTION_PARSER_VERSION` bumped `v10` -> `v11` (label-only to
that module).

`evaluation/m11g6/heading_controls.json` (new, 44 independently-authored,
synthetic controls across 22 categories; three disclosed, same-session
self-correction rounds before the final freeze -- a terminology
mix-up, two pre-existing shape-gate rule misunderstandings, and
confounded body-text wording, none touching the 9 genuine defect rows)
+ `tests/test_m11g6_heading_classification.py` (new, 104 tests,
written and run against the real classifier BEFORE implementation --
confirmed red on exactly the 9 target rows, confirmed green after,
with 2 explicit, documented `xfail`s for one narrow, verified-safe
weak-shape-signal formatting edge case) +
`scripts/evaluation_lib/m11g6_build_heading_controls.py`/
`m11g6_phase1_current_behavior.py`/`m11g6_phase3_candidate_fix_simulation.py`
(new, evaluation-only harness and strategy-comparison simulation).

**Why:** Three candidate strategies were compared and simulated
against production's own real regexes before any `src/gitscore` edit
(full comparison in the design doc): (A) fixed family-precedence order
-- fixes 0 of the 9 target rows (no competing match exists in the base
case to prefer) while regressing 3 already-correct ambiguous cases,
rejected; (B) strict per-word family-coverage boundary matching -- 9
regressions for 9 fixes, a wash, rejected; (C) the generic exclusion
signal above -- 44/44 frozen controls matched, 0 regressions, exactly
the 9 target rows fixed. Selected and implemented verbatim, on
explicit approval.

**Measured result:** `tests/test_m11g6_heading_classification.py`:
102 passed, 2 documented `xfail` (one weak-shape-signal, no-colon
formatting variant resolves to `NOT_A_HEADING` rather than `UNKNOWN`,
verified SAFE -- confirmed not to fabricate anything and not to
reintroduce the reported defect for any realistic, colon-terminated
heading; disclosed and pinned, not hidden by editing frozen gold).
Full backend suite: 1493->**1595 passed**, 13 skipped unchanged, 2
xfailed. The original M11-G5 private posting fixture: 0/0
`JobRequirement`/`UnparsedClaim` before -> 0 `JobRequirement` / 6
`UnparsedClaim` after, recovering 5 of its 7 genuine qualifications as
diagnostics (none individually carry a local REQUIRED/PREFERRED
marker, so none are scored -- the "do not assume a qualification
heading means REQUIRED" guarantee holding exactly as designed); the
remaining 2 stay unrecovered for a separate, already-disclosed reason
(the generic `_looks_like_requirement` admission gate's own vocabulary
completeness, unrelated to heading classification) -- out of this
fix's scope. SOTI and Manulife re-run end-to-end:
byte-identical `JobRequirement`/`UnparsedClaim` counts to before (SOTI
1/7, Manulife 5/9), only the version label differs -- neither
posting's headings contain any phrase from the new vocabulary.
Across the 9 target-defect rows in the frozen corpus: `JobRequirement`
count 2->4 (+2, both carrying an explicit local marker), `UnparsedClaim`
count 0->6 (+6, diagnostic only) -- zero new false REQUIRED/PREFERRED
defaults, zero narrative/responsibility content promoted, zero
contradictory claims.

**Risks/limitations:** the new vocabulary is a bounded, non-exhaustive
list (consistent with every other root-word table in this file) -- a
candidate-seeking heading phrased with a continuation NOT in the list
would still reproduce the original defect; disclosed, not claimed as a
complete fix for every conceivable phrasing. The one weak-shape-signal
formatting edge case above is a known, narrow residual, not expected
to affect realistic (colon-terminated) real-world postings. No
scoring/matcher/schema/API/frontend/competency-evidence/LLM change of
any kind.

**How to test:** `pytest tests/test_m11g6_heading_classification.py`;
`python scripts/evaluation_lib/m11g6_phase1_current_behavior.py`
(hash-verifies the frozen corpus first); full suite via `pytest -q`.

See `docs/evaluation/MILESTONE_11_G6_HEADING_CLASSIFICATION.md` for the
full root-cause trace, strategy comparison, and before/after
reconciliation.

## 2026-11-06 — Milestone 11-G4: offline-only qualification-admission recovery (segmentation.py byte-unchanged)

**What changed:** Fixes exactly the one systemic finding M11-G3 disclosed rather
than fixed: `segmentation.py`'s own `_looks_like_requirement()` admission gate --
consulted only for content outside a recognized REQUIRED/PREFERRED/RESPONSIBILITY
section -- recognizes a STRICT SUBSET of `competency_extraction.py`'s own,
already-approved `_QUALIFYING_INTENT_V2` vocabulary, missing the bare cue words
"strong"/"solid"/"deep"/"comfortable" and the leading qualifiers "understanding"/
"background"/"expertise"/"grounding"/"grasp". A sentence like "Strong
understanding of distributed systems." outside a recognized section never became
a `Claim` at all, even though the offline extractor would recognize it.

`src/gitscore/jobs/parsing/qualification_admission_recovery.py` (new -- the ONLY
new production file this milestone adds) -- `recover_unadmitted_qualification_claims()`
mirrors `segment_description()`'s own per-line loop exactly, reusing every one of
its real, private helpers via import (`_SectionKind`, `_SECTION_NECESSITY_HINT`,
`_BULLET_PREFIX`, `_classify_heading_line`, `_looks_like_requirement`,
`_ends_incomplete`, `_is_paragraph_gap`, `_line_content_span`, `_split_sentences`)
-- zero duplicated regex or admission logic, only the orchestration shape is
mirrored. Never recovers content inside a recognized section, never recovers
content under a SKIP section, never recovers a line `_looks_like_requirement`
would already admit -- avoiding duplication by construction, not a post-hoc
dedup step. Recovers a line only when the REAL `_QUALIFYING_INTENT_V2` gate
passes. Recovered `Claim`s are returned in the exact shape real ones have, so
every existing, unmodified downstream safety check applies unchanged.
`segmentation.py` itself is byte-unchanged -- confirmed both by `git diff` and by
a dedicated test that fails loudly if it is ever modified.

`evaluation/m11g4/admission_recovery_controls.json` (new, 22 self-authored
postings, 42 controls) + `tests/test_m11g4_admission_recovery.py` (new, 15
tests) -- a preliminary freeze recorded independent predictions BEFORE
implementation; a pre-freeze verification pass against the real, implemented
pipeline found 5 mismatches (all disclosed in the freeze file, all the author's
own prediction errors -- two sentences already matched segmentation's existing
vocabulary without being noticed, three preamble/unsectioned-necessity-default
mispredictions), fixed before the final freeze. Zero mismatches at the final
hash.

**Why:** Three candidate strategies were compared before implementation:
widening `segmentation.py`'s own vocabulary directly (would require a production
change this milestone was explicitly restricted from making without a STOP);
this offline-only recovery pass (selected, on architectural grounds -- reuse
over duplication, zero production-file risk); a future shared, context-aware
admission policy both parsers could adopt (the new predicate is written cleanly
enough to be adoptable there later, not wired in now).

**Measured result:** on the frozen 42-control corpus: admission 41/41,
applicant-qualification identification 26/26, competency-tag prediction 31/31,
necessity 31/31, logical structure handling 31/31, source-span exactness 31/31,
safe projection 31/31, previously-correct (already-admitted) behavior preserved
14/14, zero false narrative/responsibility admissions, zero duplicate claims.
Re-running M11-G3's own, untouched 81-control corpus through the combined
(admitted + recovered) pathway as development/regression material (never
independent generalization evidence) recovers EXACTLY the one claim M11-G3
itself disclosed as missing, and nothing else -- confirmed to now resolve
correctly (`concurrency`, REQUIRED, job_requirement). Full backend suite:
1470->**1485 passed**, 13 skipped. M11-G1/M11-G2/M11-G3's own controls and the
M11-C/M11-E harnesses are byte-identical before/after.

**Risks/limitations:** the recovery pass duplicates `segment_description()`'s
own per-line orchestration SHAPE (though none of its regex/classification/
joining logic, all reused via import) -- a future Option-C-style unification
(folding this widened check directly into `segmentation.py`) would remove even
that, at the cost of touching a production file this milestone was explicitly
restricted from modifying. This pathway remains entirely offline -- nothing
calls it except this milestone's own evaluation harness and tests.

**How to test:** `pytest tests/test_m11g4_admission_recovery.py`;
`python scripts/evaluate_m11g4_admission_recovery.py` (hash-verifies the frozen
corpus first); `python scripts/evaluate_m11g4_pre_freeze_check.py` for the
detailed per-control diagnostic; full suite via `pytest -q`.

See `docs/evaluation/MILESTONE_11_G4_QUALIFICATION_ADMISSION.md` for the full
root-cause trace, strategy comparison, and before/after metrics.

## 2026-11-05 — Milestone 11-G3: offline end-to-end qualification-understanding evaluation (no production change)

**What changed:** An integration-VALIDATION milestone, not an extraction-development
one -- `git diff --stat -- src/` is empty; zero production code was touched. A new,
purely additive OFFLINE evaluation harness
(`scripts/evaluate_m11g3_end_to_end.py` + `scripts/evaluate_m11g3_pre_freeze_check.py`
+ `scripts/evaluation_lib/m11g3_build_postings.py`, new) chains four already-existing,
already-tested functions into one pathway: `segment_description()` /
`document_has_any_recognized_heading()` (unmodified) ->
`extract_competency_qualifications_v2(..., has_section_context=True)` (M11-G1/M11-G2,
unmodified) -> `project_qualification()` (M11-B Stage 1, unmodified). The live parser's
own pathway (`parse_job_description()`/`_parse()`/`_requirements_from_claim`) is never
called, imported, or modified -- confirmed by a dedicated test inspecting `parser.py`'s
own source for any reference to either function.

`evaluation/m11g3/full_posting_controls.json` (new, 28 self-authored mini-postings, 81
independently-annotated controls spanning all 6 qualification-intent categories A-F) +
`tests/test_m11g3_end_to_end_pathway.py` (new, 12 tests) -- expected outcomes hash-
frozen only after a separate pre-freeze verification script found and fixed 16 initial
corpus-authoring mistakes against the real, unmodified pipeline (all disclosed in the
freeze file), plus one later coverage gap (named-technology/education controls) closed
before the final freeze. No sentence is copied, paraphrased, or reconstructed from
M11-D's or M11-F's own private real-posting corpora -- every sentence is either already
self-authored and publicly committed in M11-G1/M11-G2's own corpora/tests, or freshly
built using only the 17-tag canonical/alias VOCABULARY already present in production
source code.

**Why:** M11-G1 and M11-G2 each fixed one isolated defect; this milestone confirms those
fixes, plus the already-existing segmentation and projection machinery, actually compose
correctly on COMPLETE, multi-section postings -- not just in the single-sentence
isolation every prior milestone's own test suite exercised.

**Measured result:** applicant-qualification identification 57/57, competency-tag
prediction (per-prediction methodology) 65/65, necessity classification 66/66 (UNKNOWN
never coerced to REQUIRED/PREFERRED, zero exceptions), logical grouping 66/66,
source-span exactness 66/66, conservative projection correctness 66/66, zero false
qualifications across 9 responsibility + 4 learning + 3 narrative controls (6 of the 13
instead safely construct a Qualification with necessity=None, the M11-G2-disclosed
interpretation choice, now measured directly), 57/57 isolated matcher checks confirming
NOT_ASSESSABLE safety with empty evidence. Explicitly reported as an INTEGRATION-
correctness result on synthetic development controls, not a generalization claim. Full
backend suite: 1458->**1470 passed**, 13 skipped. M11-G1/M11-G2's own controls and the
M11-C/M11-E harnesses are byte-identical before/after; M11-F's independent holdout
(diagnostic only) is also byte-identical, its committed report regenerated locally for
confirmation then `git checkout`-restored, never rewritten.

**Risks/limitations (reported, not fixed -- outside this milestone's authorized scope):**
one genuine, systemic integration-interface mismatch was found: `segmentation.py`'s own
`_looks_like_requirement` admission-gate vocabulary is narrower than
`competency_extraction.py`'s own `_QUALIFYING_INTENT_V2` gate (the latter additionally
recognizes bare "strong"/"solid"/"deep"/"comfortable") -- a sentence like "Strong
understanding of X" outside a recognized REQUIRED/PREFERRED/RESPONSIBILITY section never
becomes a `Claim` at all, confirmed directly by a dedicated test. A second, lower-
severity, pre-existing cross-tag alias overlap was also found and disclosed:
"distributed architecture" matches both `system-design`'s own canonical phrase and a
pre-existing `distributed-systems` alias. Neither was patched.

**How to test:** `pytest tests/test_m11g3_end_to_end_pathway.py`;
`python scripts/evaluate_m11g3_end_to_end.py` (hash-verifies the frozen corpus first);
`python scripts/evaluate_m11g3_pre_freeze_check.py` for the detailed per-control
diagnostic; full suite via `pytest -q`.

See `docs/evaluation/MILESTONE_11_G3_END_TO_END_QUALIFICATION_UNDERSTANDING.md` for the
full architecture, control inventory, and before/after metrics.

## 2026-11-05 — Milestone 11-G2: section-aware qualification/necessity inference for v2 (opt-in)

**What changed:** `extract_competency_qualifications_v2`'s necessity inference was
always purely LOCAL (`infer_necessity(text, None)`), even though
`jobs/parsing/segmentation.py` already computes exactly the section-origin signal
needed (`Claim.section_kind`) and `jobs/parsing/necessity.py::resolve_necessity_hint`
(Milestone 10E) already implements the full, already-tested policy for using it --
confirmed as the exact mechanism M11-F's own independent holdout found missing
(`necessity: 0/0` -- every genuinely-matched control carried no resolvable
necessity, because real "Requirements:" bullets rarely repeat "is required" per
sentence).

`src/gitscore/jobs/parsing/competency_extraction.py` (extended, +81/-3 lines, v2
ONLY -- `extract_competency_qualifications` (v1) has zero lines changed and zero
new parameters, confirmed by a dedicated test inspecting its signature) -- three
new, keyword-only, DEFAULTED parameters (`section_kind`,
`document_has_recognized_heading`, `has_section_context=False`) make this
fully opt-in and backward-compatible: every pre-existing call site (M11-E's and
M11-F's own harnesses included) is byte-identical to before. A new helper
(`_claim_necessity_hint_for_section_v2`) mirrors `Claim.necessity_hint`'s own
computation by reusing the REAL `_SectionKind`/`_SECTION_NECESSITY_HINT` constants
directly (never a second, independently-maintained copy), then feeds the REAL
`resolve_necessity_hint()` before the existing, unchanged `infer_necessity()` runs
-- the identical two-step pattern `jobs/parsing/parser.py::_requirements_from_claim`
already uses for its own non-competency pathway.

`evaluation/m11g2/section_context_controls.json` (new, 49 self-authored
assertions: 36 hand-specified + 13 targets across 10 real mini-postings run
through the actual, unmodified `segment_description()`) +
`scripts/evaluation_lib/m11g2_section_strategy_prototypes.py` (new, Phase 3) +
`scripts/evaluate_m11g2_strategy_comparison.py` (new) +
`scripts/evaluate_m11g2_section_context.py` (new) +
`tests/test_m11g2_section_context.py` (new, 19 tests) -- expected outcomes hash-
frozen before any extractor code was touched; four corpus-authoring mistakes
(phrasing that accidentally re-triggered M11-E's own already-disclosed stemming
overlap, and one sentence that didn't satisfy the existing qualifying-intent gate)
found and fixed before the freeze, not after.

**Why:** Three candidate designs were measured before implementation (Option A:
reuse of `resolve_necessity_hint`; Option B: an independent, hand-rolled duplicate;
Option C: hybrid, found to already equal Option A). All three tied 33/33 on the
frozen corpus, so the choice was made on architectural grounds, not recall: probing
outside the frozen set found Option B's own hand-rolled marker regex already
missing coverage the production one has ("would be nice" -- PREFERRED under the
real regex, wrongly REQUIRED under the duplicate) -- the exact drift risk reuse
avoids.

**Measured result:** G2 corpus 28/49 (no section awareness existed) ->
**49/49** opt-in; the SAME corpus through the unchanged legacy call path stays
byte-identical at 28/49. Zero false REQUIRED/PREFERRED assignments, zero false
qualification creation, zero genuine-qualification suppression. A responsibility-
sourced claim with qualifying-intent language but no explicit local marker now
correctly resolves to `necessity=None` (UNKNOWN) -- conservative uncertainty, not a
new "responsibility rejected" decline -- mirroring the live parser's own
`necessity_unknown` -> `UnparsedClaim` precedent exactly. M11-G1's OR-list safety
fix is completely unaffected (that check runs and returns before necessity is ever
computed). M11-E's own 92-control corpus, M11-C's harness, M11-F's independent
holdout (used only as an already-inspected diagnostic benchmark, its committed
report regenerated locally for confirmation then `git checkout`-restored, never
rewritten), and M11-G1's own 32-control safety corpus are all byte-identical
before/after. Full backend suite: 1439->**1458 passed**, 13 skipped.

**Risks/limitations:** this module still does not call `segment_description()`
itself -- a caller must run real segmentation separately and pass
`Claim.section_kind`/`document_has_recognized_heading` through explicitly; no
evaluation harness today does this on bare, context-free sentences. Options A and
C are literally the same implementation (not a genuinely independent third data
point). "Reject as a qualification" (the mission brief's own phrase) is
implemented as necessity=UNKNOWN rather than a literal `DeclinedExtraction` -- a
deliberate, disclosed interpretation choice.

**How to test:** `pytest tests/test_m11g2_section_context.py`;
`python scripts/evaluate_m11g2_section_context.py` (and `--baseline` for the
legacy-path comparison; both hash-verify the frozen corpus first);
`python scripts/evaluate_m11g2_strategy_comparison.py`; full suite via `pytest -q`.

See `docs/evaluation/MILESTONE_11_G2_SECTION_CONTEXT.md` for the full root-cause
trace, control inventory, strategy comparison, and before/after metrics.

## 2026-11-04 — Milestone 11-G1: alternative-requirement (OR-list) safety fix for v2

**What changed:** M11-F's own independent-holdout evaluation surfaced one real
safety defect: `extract_competency_qualifications_v2` (and, identically,
unmodified v1) only consulted its `has_or`/`has_and` flags inside the
`len(tags) > 1` branch. A sentence whose OR-list names several alternatives
but where only ONE alternative happens to match a known competency tag took
the `len(tags) == 1` fast path instead, returning a fully-confident single-tag
`Qualification` that silently discarded every other named alternative.

`src/gitscore/jobs/parsing/competency_extraction.py` (extended, +138/−0 lines,
v2 ONLY -- `extract_competency_qualifications` (v1) has zero lines changed in
its own function body) -- a new structural check
(`_split_alternative_segments_v2` + `_segment_competency_tags_v2`) runs BEFORE
the tag-count branching: it segments a confidently-list-shaped OR sentence
and independently re-matches each segment. If any segment matches nothing, or
segments collectively span more than one distinct tag, the sentence declines
as `missing_contract` regardless of how many tags the whole-sentence match
found. If every segment agrees on the SAME single tag (e.g. three synonymous
phrasings of one competency), it falls through unchanged to the pre-existing
logic. The segmentation helper deliberately returns "not a list" (falling
back to prior behavior) for ordinary prose and for the common
"...or equivalent/similar X" substitutability idiom, to avoid new false
declines. The shared `DeclinedExtraction` type gained three optional,
default-empty diagnostic fields (`source_text`, `source_span`,
`recognized_tags`) -- additive to this module-local helper type, not to the
Stage-1 `Qualification`/`NormalizedReference` contracts.

`evaluation/m11g1/alternative_requirement_controls.json` (new, 32 controls,
18 categories) + `tests/test_m11g1_alternative_requirement_safety.py` (new,
26 tests) + `scripts/evaluate_m11g1_alternative_requirements.py` (new) --
expected outcomes hash-frozen before any extractor code was touched.

**Why:** Resolving a single matched tag as though it were equivalent to a
whole unresolved alternative list is a false-confidence risk this project's
own established discipline (M11-C through M11-F) has consistently treated as
worse than an honest decline.

**Measured result:** G1 corpus 25/32→**32/32** (the 7 baseline failures were
exactly this shape, nothing broader). M11-E's own 92-control development
corpus: byte-identical before/after (necessity 66/66, logical grouping 69/69,
span 69/69, 1 pre-existing unrelated mismatch). M11-F's independent holdout,
used only as an already-inspected diagnostic benchmark (never retuned, never
rewritten): tag precision 12/13→**12/12** (the one false positive the fix
targets, now a correct decline), tag recall unchanged at 12/74 (that control
was never gold-expected to contribute a tag). Full backend suite:
1413→**1439 passed**, 13 skipped.

**Risks/limitations:** Still cannot REPRESENT a genuine alternative group of
two different, real, recognized tags -- only decides whether to decline one;
no schema change was made or needed. Nested alternative structures beyond the
existing flat-list/`MIXED_SHAPE` cases are not specially parsed. The
"or equivalent/similar/comparable" guard is the only general safeguard
against idiomatic, non-list "or" usage; verified against this milestone's own
32-control corpus, not against unbounded real-world phrasing.

**How to test:** `pytest tests/test_m11g1_alternative_requirement_safety.py`;
`python scripts/evaluate_m11g1_alternative_requirements.py` (hash-verifies the
frozen corpus first); full suite via `pytest -q`.

See `docs/evaluation/MILESTONE_11_G1_ALTERNATIVE_REQUIREMENT_SAFETY.md` for
the full root-cause trace, control inventory, and before/after metrics.

## 2026-11-03 — Milestone 11-E: paraphrase-tolerant competency extraction (v2, additive to v1)

**What changed:** Following M11-D's own independent-holdout finding
(`TECHNICAL_COMPETENCY` recall collapsing 93%→5% on authentic
postings, dominated by exact-phrase vocabulary intolerance to ordinary
paraphrasing), built and measured a general-mechanism response.

`src/gitscore/jobs/parsing/competency_aliases.py` (new) -- a bounded,
auditable alias table: 54 aliases across all 17 existing competency
tags (no new tags added), each classified `SEMANTICALLY_EQUIVALENT` /
`NARROWER_OR_MORE_SPECIFIC` / `RELATED_ONLY` / `UNKNOWN`. Only the
first two relation types are ever compiled into an active matching
pattern -- `RELATED_ONLY`/`UNKNOWN` entries (17 of the 54) exist for
audit and evaluation use only, excluded from active matching by
construction (filtered at import time), never consulted by any
extraction function.

`src/gitscore/jobs/parsing/competency_extraction.py` (extended,
+210/−1 lines -- the one deletion is a single import-line edit; v1's
own function bodies are byte-for-byte unchanged, confirmed by
re-running its own M11-C development harness identically) --
`extract_competency_qualifications_v2()`, a new, additive function
reusing every one of v1's own safety mechanisms unchanged
(`_NEGATION_PATTERNS`, narrative/responsibility rejection, the
`missing_contract` decline, `MIXED_UNSUPPORTED` detection,
applicability-condition routing, AND-splitting into siblings, the
unchanged `_COMPETENCY_OBSERVABILITY` policy table). The one genuine
extension: tag recognition via EITHER the exact canonical phrase OR a
compiled active alias, matched against text stemmed by a small, fixed
suffix-stripping function (never a dictionary, never statistical),
gated by a qualifying-intent template covering both the leading
("experience with X") and trailing ("X experience is required")
real-world sentence shapes. Each match's strength is reported via the
EXISTING `ParserConfidence` field (`HIGH` for exact/equivalent,
`MEDIUM` for narrower) -- no new field invented.

`evaluation/m11e/paraphrase_development_controls.json` (new, 92
controls) -- a fresh development corpus, independent of M11-D's own
raw postings/annotations (not re-read while authoring it), covering
all 17 tags × 3 variants, 11 `related_only` adversarial examples, 3
out-of-taxonomy examples, and full structural/adversarial coverage.
Two corpus-authoring bugs (a mis-encoded expected tag contradicting
its own notes field; a `logical_composition` annotated "and" for two
phrases that both resolve to the same tag) found and fixed during
comparison, before any strategy was finalized -- same discipline as
every prior milestone's own corpus fixes.

`scripts/evaluation_lib/m11e_paraphrase_prototypes.py` +
`scripts/evaluate_m11e_paraphrase_extraction.py` (new) -- three real
offline strategies compared: Option A (alias table, exact-phrase only,
no stemming): 62/64 recall, 0 unexpected tags. Option B (bag-of-words
keyword overlap): 31/64 recall, 5 unexpected tags -- worse on both
axes. **Option C (alias table matched against stemmed text, gated by
a qualifying-intent template): 63/64 recall, 1 unexpected tag** --
chosen on the combination of recall, precision, and demonstrated
generalization headroom, not recall alone. Two real implementation
bugs found and fixed DURING this comparison (not after selection): a
tokenizer bug where a pattern's own `\b` word-boundary anchor merged
with the following word, occasionally corrupting a stem; a qualifying-
intent template that only recognized a leading qualifier phrase and
missed the equally common trailing "X experience is required" shape.

`scripts/evaluate_m11e_v2_extractor.py` (new) -- ran BOTH the real,
unmodified v1 and the real v2 against the identical 92-control corpus.

**Why:** M11-D's own disclosed recommendation was "an evaluation-first
investigation into paraphrase-tolerant competency-phrase matching...
not a larger fixed vocabulary" -- this milestone is exactly that step,
held to the same discipline: fresh corpus before code, three real
strategies measured before a choice, every v1 safety invariant
preserved and re-verified, not merely assumed.

**Measured, reconciled result:** tag recall 39%→**100%** (25/64→
64/64), tag precision 100%→**100%** (25/25→64/64), qualification
recall 32%→**79%** (26/82→65/82) -- the 79% figure's 21-point gap
from 100% is entirely attributable to 18 controls v2 is CORRECTLY
expected to decline (13 `related_only`/`unknown` terms that must never
auto-map per Phase 3's own contract, 1 `missing_contract` shape, 3
controls entirely outside a competency-only extractor's own scope),
confirmed by exact arithmetic, not estimated -- zero of v2's declines
are a missed, in-scope, mappable competency. **One real, measured
precision cost is disclosed, not minimized**: stemming "systems"→
"system" makes "embedded system**s** design" also match the bare
`system-design` canonical phrase, producing one unexpected sibling
tag (`unexpected_additional_tag_count: 1`, identical in both the
Phase 3 comparison and the Phase 5 production measurement). This
count was initially UNDER-reported by the Phase 5 evaluation script's
own first version, which never checked for an unexpected additional
tag at all -- found and corrected by widening the harness itself
during this same report's own reconciliation pass; no annotation was
altered to make any number look better. M11-D's own historical 3/6
precision / 3/59 recall are reported for context only, hardcoded from
that milestone's own committed report, never recomputed here, and
never conflated with this milestone's own development-corpus numbers.

**Files affected:** `src/gitscore/jobs/parsing/competency_aliases.py`
(new); `src/gitscore/jobs/parsing/competency_extraction.py` (extended,
v1 unmodified); `evaluation/m11e/paraphrase_development_controls.json`
(new); `scripts/evaluation_lib/m11e_paraphrase_prototypes.py` (new);
`scripts/evaluate_m11e_paraphrase_extraction.py` (new);
`scripts/evaluate_m11e_v2_extractor.py` (new);
`tests/test_m11e_paraphrase_extraction.py` (new, 34 tests);
`docs/evaluation/MILESTONE_11_E_PARAPHRASE_EXTRACTION.md` (new);
`docs/ARCHITECTURE.md` (new subsection); `docs/PIPELINE.md` (follow-up
note). No existing `src/gitscore` file's own BEHAVIOR changed (v1
byte-identical); no matcher, scoring, public schema, API, frontend, or
concept-registry change; `JOB_DESCRIPTION_PARSER_VERSION` stays
`job_description_parser:v10`.

**Risks / limitations:** alias/vocabulary coverage is still bounded,
not universal -- new, not-yet-seen paraphrases still correctly decline
rather than guess, but the real residual gap size is unknown until
measured against genuinely new text. The embedded-systems-design/
system-design stemming overlap (above) is a real, bounded precision
cost, not special-cased away. The qualifying-intent template remains a
fixed, closed vocabulary of its own. Necessity inference is still
local-marker-only (unchanged from v1). Zero coordination with the
technology-mention detector remains (the "C coding... for embedded
systems" false-positive class M11-D found is a different subsystem's
own gap). No new independently-sourced validation corpus was acquired
this milestone -- stated explicitly, not implied; see that document's
own Phase 6/§12 for the required protocol before any real-world-
generalization claim.

**How to test it:** `pytest tests/test_m11e_paraphrase_extraction.py -q`
(34 tests); full suite `pytest -q` (1372 pre-existing + 34 new = 1406
passed, 13 skipped, unchanged skip set);
`python scripts/evaluate_m11e_paraphrase_extraction.py` (the Phase 3
strategy comparison); `python scripts/evaluate_m11e_v2_extractor.py`
(the Phase 5 v1-vs-v2 comparison and reconciled metrics);
`python scripts/evaluate_m11c_offline_extractor_safety.py` (confirms
v1 byte-identical to its own M11-C baseline);
`python scripts/evaluate_m11_generalization.py`,
`python scripts/evaluate_m10a_realworld.py`,
`python scripts/evaluate_m9b_preservation.py`,
`python scripts/evaluate_m10d_alternatives.py`, and
`python scripts/check_evaluation_staleness.py` all byte-identical to
the M11-D baseline (frozen `8c:v1`/`8c:v1.1` FRESH, 0 diffs).
`evaluate_m10d_alternatives.py`'s own regenerated tracked report files
were reverted via `git checkout --` afterward, matching every prior
milestone's own practice.

**Not done, by explicit scope:** no live parser wiring (confirmed by
test); no competency GitHub evidence detector; no LLM extraction; no
public schema/matcher/scoring/API/frontend change; no new
independently-sourced validation corpus; no modification to any
frozen historical gold or to M11-D's own private artifacts
(`evaluation/m11d/source/`, `holdout_annotations.json` -- confirmed
present, untracked, not re-read); no commit, no push -- held for
separate, explicit authorization.

## 2026-11-02 — Milestone 11-C: generalized technical-competency extraction, offline Path B prototype

**What changed:** An evaluation-first investigation into Path B
(independent semantic qualification extraction), per Milestone 11-B
Stage 2A's own dependency-ordered plan. Produced a new 45-example
evaluation corpus, compared three real offline extraction strategies,
and implemented the winning strategy as a standalone, unwired
prototype module -- no production code touched.

`evaluation/m11c/competency_extraction_controls.json` (new, 45
entries) -- authored BEFORE any strategy was implemented or run
against it, covering all 16 mission-named engineering disciplines
(algorithms, concurrency, distributed systems, system design,
debugging/performance, OS/networking, database design, ML
fundamentals, GPU/parallel computing, signal processing, circuit
theory, embedded systems, control systems, computer vision,
cybersecurity, digital logic) plus one deliberately unlisted domain
(quantum computing) as a generalization test, 8 adversarial/baseline
negatives (company narrative x2, responsibility bullets x2, a learning
opportunity, a negated requirement, administrative text x2), AND/OR
logical structures, conditional qualifications, line-wrap/bulleted
formatting, and requirements outside formal sections. One
corpus-authoring bug found and fixed DURING comparison (not after):
11 entries had `logical_composition` set to `"and"`/`"or_any"` for
sentences that are genuinely ONE competency claim with descriptive
sub-terms, inconsistent with the corpus's own notes field and with
`LogicalComposition`'s actual Stage-1 semantics -- corrected to
`"single"`, discovered the same way M11-A2/M11-B's own corpus bugs
were (a real prototype's measured output forcing a re-read of the
annotation's own stated intent).

`scripts/evaluation_lib/m11c_competency_prototypes.py` +
`scripts/evaluate_m11c_competency_extraction.py` (new) -- three real
offline prototypes sharing one bounded, 17-tag competency vocabulary
(the same closed, generic-phrase-table design `non_technical.py`
already uses). Option A (naive, no sentence-role awareness): 28/28
recall, 28/34 precision (6 false positives). Option B (reuses the
EXISTING, unmodified `infer_necessity`/`contains_narrative_cue` plus 2
new bounded signals -- responsibility-lead detection, negation): 28/30
precision (2 residual false positives -- confirmed directly that
`contains_narrative_cue()`'s own three M10E-tuned alternatives do not
match either of this corpus's new company-narrative phrasings). Option
C (Option B plus one more bounded, additive narrative-subject pattern,
never a `narrative.py` edit): **28/28 precision, zero false positives
of any kind**, identical recall/necessity/logical-grouping to A and B.
Chosen on measured precision, not recall (all three tied on recall).

`src/gitscore/jobs/parsing/competency_extraction.py` (new, standalone,
confirmed not imported by `parser.py`/`segmentation.py`/
`necessity.py`/`narrative.py`) -- the real Option C implementation,
producing actual `Qualification` objects (Stage 1, unmodified) from
already-segmented claim text/spans. Found one genuine missing
contract, declined rather than invented around: `NormalizedReference`
has no field for a GROUP of multiple competency tags (only one
registered concept, a GROUP of registered concepts, or ONE competency
tag) -- "at least one of: distributed systems, concurrent programming,
or high-performance computing" cannot be safely represented today;
the extractor returns a named `DeclinedExtraction(reason=
"missing_contract", ...)` whose own detail text names every option
found, rather than silently discarding them. Added a new, data-only
competency-observability policy table (`_COMPETENCY_OBSERVABILITY`,
never an evidence detector -- a plain lookup, mirroring
`observability.py`'s own existing design): `circuit-theory`,
`ml-fundamentals`, and `quantum-computing` map to `NOT_OBSERVABLE`;
every other tag maps to `PARTIALLY_OBSERVABLE`; none maps to
`STRONGLY_OBSERVABLE`.

`scripts/evaluate_m11c_offline_extractor_safety.py` (new) -- re-measured
the REAL module (not just the comparison prototype) and empirically
verified the Phase 5 safety requirement by actually calling the REAL,
unmodified `match_requirement()` against an empty candidate evidence
profile for every produced requirement: `never_supported_with_empty_evidence`
and `never_falsely_assessable_without_concept_mapping` both `True`
across all 28 cases -- a technical competency can never be silently
scored `SUPPORTED` or enter `assessable_count`'s denominator without a
real concept mapping, confirmed directly rather than assumed.

**Why:** Milestone 11's own finding (9% `TECHNICAL_COMPETENCY` recall,
a structural absence, not a detection miss) and Stage 2A's own
dependency-ordered plan named Path B extraction as the step requiring
its own evaluation-first milestone, explicitly deferred until Path
A/tooling work was committed. This milestone is that step, held to the
EXACT same discipline: corpus before code, measured comparison before
a choice, explicit STOP on anything the existing model cannot safely
represent.

**Measured results (the real module, not the comparison prototype):**
26/28 recall (2 disclosed missing-contract declines, never a false
positive), 26/26 precision (zero false positives of any kind), 20/20
necessity classification (genuinely-unknown cases correctly excluded
from the denominator, never penalized as wrong), 27/28 logical
grouping (the one residual is a disclosed, M11-B-precedented
limitation: this extractor does not coordinate with a technology-
mention detector to recognize sibling composition ACROSS different
qualification kinds within one sentence), 28/28 source-span exactness,
fully deterministic.

**Files affected:** `evaluation/m11c/competency_extraction_controls.json`
(new); `scripts/evaluation_lib/m11c_competency_prototypes.py` (new);
`scripts/evaluate_m11c_competency_extraction.py` (new);
`src/gitscore/jobs/parsing/competency_extraction.py` (new);
`tests/test_m11c_competency_extraction.py` (new, 29 tests);
`scripts/evaluate_m11c_offline_extractor_safety.py` (new);
`docs/evaluation/MILESTONE_11_C_COMPETENCY_EXTRACTION.md` (new);
`docs/ARCHITECTURE.md` (new subsection); `docs/PIPELINE.md` (follow-up
note). No existing `src/gitscore` file modified; no matcher, scoring,
public schema, API, frontend, or concept-registry change;
`JOB_DESCRIPTION_PARSER_VERSION` stays `job_description_parser:v10`
(the live parser has not changed).

**Risks / limitations:** vocabulary coverage, not language
understanding (17 tags, no recall claim beyond them); necessity
detection is local-marker-only (no section-hint threading, a real
future integration question); negation handling is three fixed
phrases, not a general capability; the missing-contract gap (OR_ANY
groups of competency tags) is real and unfixed; no claim of universal
postings understanding is made anywhere in this entry or the design
doc -- 45 single-session development examples is not a representative
holdout sample, and the design doc's own Phase 2 holdout protocol
(unchanged from Stage 2A, content still unauthored) remains the
required bar before any broader claim.

**How to test it:** `pytest tests/test_m11c_competency_extraction.py -q`
(29 tests); full suite `pytest -q` (1343 pre-existing + 29 new = 1372
passed, 13 skipped, unchanged skip set);
`python scripts/evaluate_m11c_competency_extraction.py` (the Phase 3
strategy comparison); `python scripts/evaluate_m11c_offline_extractor_safety.py`
(the Phase 4/5 real-module measurement and scoring-safety
verification); `python scripts/evaluate_m11_generalization.py`,
`python scripts/evaluate_m10a_realworld.py`,
`python scripts/evaluate_m9b_preservation.py`,
`python scripts/evaluate_m10d_alternatives.py`, and
`python scripts/check_evaluation_staleness.py` all byte-identical to
the Stage 2B baseline (frozen `8c:v1`/`8c:v1.1` FRESH, 0 diffs).
`evaluate_m11a2_line_wrap.py` was also re-run to confirm its baseline
column is unchanged; its own and `evaluate_m10d_alternatives.py`'s
regenerated tracked report files were reverted via `git checkout --`
afterward, matching every prior milestone's own practice.

**Not done, by explicit scope:** no live parser wiring (confirmed by
test); no competency GitHub evidence detector; no public schema/
matcher/scoring/API/frontend change; no holdout corpus content
authored (methodology only, unchanged from Stage 2A); no commit, no
push -- held for separate, explicit authorization.

## 2026-11-02 — Milestone 11-B Stage 2B: Path A compatibility adapter + offline shadow-evaluation harness

**What changed:** Following Stage 2A's architecture-only review
(`docs/evaluation/MILESTONE_11_B_STAGE_2A_SHADOW_INTEGRATION.md`),
implemented exactly the two approved pieces -- Path A (a compatibility
adapter) and the Option A offline evaluation harness -- with Path B
(a future semantic extractor) explicitly withheld.

`src/gitscore/jobs/parsing/qualification_adapter.py` (new, standalone,
confirmed not imported by `parser.py`/`segmentation.py`/`necessity.py`/
`narrative.py`, exactly like `qualification.py` itself). A first pass
achieved round-trip equality on seven named fields
(`original_text`/`source_span`/`necessity`/`concept_id`/
`alternative_concept_ids`/`github_observability`/`parser_confidence`)
but NOT on `importance` or `category`'s raw string --
`project_qualification()` has no `importance` field to reconstruct and
always writes `category=qualification_kind.value`. Commit was held
specifically because "full `JobRequirement` dataclass equality" is the
real bar, not a hand-picked subset -- and because one concrete
consequence (the two existing placeholder categories both collapsing
to `"other_legitimate"`, silently changing
`api/serialization.py::_interpretation_status()`) is a real behavior
change, not an abstract gap. **Corrected** by `AdaptedQualification`
(new, frozen, adapter-internal) -- a typed envelope carrying the
Stage-1 `Qualification` PLUS `legacy_importance`/`legacy_category`
verbatim, reconstructed via `dataclasses.replace()` onto the
EXISTING, unmodified `project_qualification()`'s own safe output
(`adapt_job_requirement()`/`job_requirement_from_adapted()`). Two
rejected alternatives: broadening `Qualification` itself (reopens
Stage 1's own separately-approved scope outside this correction) and
reporting every requirement with a non-`MEDIUM` importance or a
non-`"education"`/`"experience"` category as `UnsupportedAdapterCase`
(technically sound but measured, in the held-back version, to affect
237/265 requirements -- 89% -- making the adapter nearly useless for
its validation purpose). No public schema changes anywhere:
`Qualification`/`JobRequirement`/`UnparsedClaim` are exactly as
before; `AdaptedQualification` is new and adapter-only, never imported
by production code. `QualificationKind` is still derived from
STRUCTURAL facts only (`concept_id`/`alternative_concept_ids`
populated, or one of a small, closed non-technical category-string
set) -- never equated with the preserved `legacy_category`.

`scripts/evaluate_m11b_stage2b_compatibility.py` (new, the Option A
offline harness, same 184 fixtures across the same seven existing,
already-committed evaluation sources -- `evaluation/jobs/*.json`,
`evaluation/m10/corpus.json` + its `source/*.txt` files,
`evaluation/m9b/corpus.json`, `evaluation/m10d/alternative_controls.json`,
`evaluation/m11a2/line_wrap_controls.json`, `evaluation/m11/corpus.json`,
`evaluation/m11b/structured_qualification_controls.json`) runs each
through the real, unmodified `parse_job_description_with_diagnostics()`,
round-trips every resulting `JobRequirement`/`UnparsedClaim` through
the full-fidelity adapter, and reports SIX separate dimensions: full
dataclass equality, core-field equality, serialized-output equality,
scoring-denominator equality (verified by actually calling
`match_requirement()` against an empty candidate profile for both the
original and reconstructed requirement -- not inferred from field
equality alone), placeholder-category identity preservation, and
unsupported-adapter-case count. Writes
`evaluation/reports/m11b_stage2b_compatibility_report.json`.

**Why:** Stage 1 approved an internal representation but explicitly
deferred whether that representation can losslessly express what the
CURRENT parser already produces. Path A now answers that question
completely: a pure reverse-mapping plus a round trip through the
already-shipped, unmodified `project_qualification()`, with the two
previously-lossy legacy fields carried alongside it rather than
through it -- no new detector, no new policy, no public schema change.

**Measured result:** 265/265 `JobRequirement`s and 98/98
`UnparsedClaim`s achieve **full dataclass equality** (not a named
field subset), **100% serialized-output equality**, **100%
scoring-denominator equality**, and **100% placeholder-category
identity preservation** (37/37 rows whose category is
`"unresolved_requirement"`/`"alternative_requirement"`) -- zero
mismatches, zero unsupported-adapter cases, across all 184 fixtures.
The previously-reported `_interpretation_status()` presentation risk
(both placeholder categories collapsing to `"other_legitimate"`) is
now resolved as a direct consequence of full `category` preservation
-- confirmed directly, with **no change to `api/serialization.py`**.

**Files affected:** `src/gitscore/jobs/parsing/qualification_adapter.py`
(new); `tests/test_m11b_stage2b_qualification_adapter.py` (new, 26
tests); `scripts/evaluate_m11b_stage2b_compatibility.py` (new);
`docs/evaluation/MILESTONE_11_B_STAGE_2A_SHADOW_INTEGRATION.md`
(implementation addendum appended, including the correction's own
reasoning, a Phase 4 observability-policy table by `QualificationKind`,
and a Phase 5 holdout-corpus manifest format -- methodology only, no
content authored); `docs/ARCHITECTURE.md` (new subsection);
`docs/PIPELINE.md` (follow-up note). No existing `src/gitscore` file
modified; no concept registry, matcher, scoring, API, or frontend
change; `JOB_DESCRIPTION_PARSER_VERSION` stays `job_description_parser:v10`.

**Risks / limitations:** no Path B extractor exists -- this milestone
adds no new classification capability, only a validated, now
full-fidelity reverse-mapping of what already exists;
`TECHNICAL_COMPETENCY` recall is unchanged at 1/11 (9%). The
`applicability_condition` and `MIXED_UNSUPPORTED` detector gaps (Stage
2A §1.2/§1.5) remain untouched. The Phase 4 observability-policy table
for `TECHNICAL_COMPETENCY` is documented but implements nothing -- no
code reads it yet.

**How to test it:** `pytest tests/test_m11b_stage2b_qualification_adapter.py -q`
(26 tests); full suite `pytest -q` (1317 pre-existing + 26 new = 1343
passed, 13 skipped, unchanged skip set);
`python scripts/evaluate_m11b_stage2b_compatibility.py` (writes the
compatibility report, prints the six-dimension summary above);
`python scripts/evaluate_m11_generalization.py`,
`python scripts/evaluate_m10a_realworld.py`,
`python scripts/evaluate_m9b_preservation.py`,
`python scripts/evaluate_m10d_alternatives.py`, and
`python scripts/check_evaluation_staleness.py` all byte-identical to
the Stage 1 baseline (frozen `8c:v1`/`8c:v1.1` FRESH, 0 diffs).
`evaluate_m11a2_line_wrap.py` was also re-run to confirm its baseline
column is unchanged; its own regenerated tracked report file (like
`evaluate_m10d_alternatives.py`'s two report files) was reverted via
`git checkout --` afterward, matching Stage 1's own practice.

**Not done, by explicit scope:** Path B semantic extraction; any new
GitHub competency evidence detector; any public schema/matcher/
scoring/API/frontend change; concept-registry expansion; holdout
corpus CONTENT (methodology/manifest only); no commit, no push --
held for separate, explicit authorization.

## 2026-11-02 — Milestone 11-B Stage 1: standalone structured `Qualification` model (not wired into the live parser)

**What changed:** A new, standalone module,
`src/gitscore/jobs/parsing/qualification.py`, implementing the
internal domain model and conservative projection function recommended
by `docs/evaluation/MILESTONE_11_B_STRUCTURED_QUALIFICATION_MODEL.md`
(Option C) and approved for **Stage 1 only**, explicitly narrower than
that document's own original sketch: the model is standalone and
independently testable but is **not** wired into
`_requirements_from_claim` or any other live parser code path. Zero
existing file in `src/gitscore` was modified — confirmed via `git diff
--name-only -- src/gitscore`.

The module adds: `QualificationKind` (7 values — `SPECIFIC_TECHNOLOGY`,
`TECHNICAL_COMPETENCY`, `EDUCATION`, `EXPERIENCE`, `NONTECHNICAL`,
`OTHER_LEGITIMATE`, `UNINTERPRETABLE`); `LogicalComposition`
(`SINGLE`/`AND`/`OR_ANY`/`MIXED_UNSUPPORTED`); `NormalizedReference`
(frozen, mutually-exclusive `concept_id` XOR
`alternative_concept_ids` XOR `competency_tag` — enforced in
`__post_init__` so a bare competency tag can never be projected into
`JobRequirement.concept_id`, which would fail that field's own
existing validation); the `Qualification` dataclass itself (frozen,
reusing `SourceSpan`/`Necessity`/`ParserConfidence`/
`GithubObservability` verbatim rather than inventing parallel types —
`Necessity`/`GithubObservability` stay nullable here even though
they are non-nullable on `JobRequirement`, since "unknown" is a real,
distinct state this model must be able to hold); `ProjectionResult`
(frozen, exactly one of `job_requirement`/`unparsed_claim` populated);
and `project_qualification()`, a pure function implementing five
safety rules, in order: unknown necessity, unknown observability,
`MIXED_UNSUPPORTED` logical structure, `UNINTERPRETABLE` kind, or a
non-null `applicability_condition` (no field exists on `JobRequirement`
to hold a condition, so ANY material one routes to `UnparsedClaim`
instead — the condition is not lost, since it survives verbatim inside
`UnparsedClaim.text`, the original source sentence) each force a safe
`UnparsedClaim` fallback rather than a coerced `JobRequirement`; a
`JobRequirement` construction `ValueError` (e.g. a malformed
`concept_id`) is also caught and falls back the same way, rather than
propagating a crash. `_STAGE_1_PLACEHOLDER_IMPORTANCE = Importance.MEDIUM`
is used only because `JobRequirement.importance` is non-nullable and
`Qualification` has no `importance` field at all (not a Phase-1
dimension) — documented explicitly as a neutral placeholder, never
`HIGH`/`LOW`, which would fabricate a judgment never made.

**Why:** the design doc's own Phase 1 investigation found
`ParserConfidence` already exists and is already populated in
production (6 call sites in `parser.py`, via `confidence.py`) — the
"how sure was the interpretation" dimension the milestone set out to
design already has a home, and is a dimension independent of
`Necessity` (what the employer required vs. how sure the parser is
about having read that correctly). Preserving that independence,
rather than conflating the two, is the one piece of this milestone's
own design the approval message called out by name (decision 4): a
`Qualification` with `necessity=REQUIRED, interpretation_certainty=LOW`
(we ARE sure it says REQUIRED, unsure about something else) and one
with `necessity=None, interpretation_certainty=HIGH` (genuinely
unresolved necessity) must both be representable and must never be
conflated — both are covered by dedicated tests.

**One corpus-authoring bug found and fixed, same class as M11-A2's
unregistered `Node.js`/`GraphQL` fixtures:** while writing the test
file, `evaluation/m11b/structured_qualification_controls.json`'s
`m11b-illustrative-01` ("Experience with cloud platforms such as AWS
or Azure.") turned out to reference `cloud.azure`, a concept that was
never registered in `src/gitscore/concepts/registry.py` — only
`cloud.aws` exists under `cloud.*`, no Azure/GCP concept exists at
all. This is a mechanical reference error in the pre-existing fixture,
not a semantic redesign, and the concept registry itself was NOT
touched (out of scope without separate approval). Fixed by swapping to
a domain with two already-registered concepts
(`ml.framework.pytorch`/`ml.framework.tensorflow`, "Experience with
deep learning frameworks such as PyTorch or TensorFlow."), preserving
every other annotated field (`necessity=REQUIRED`,
`interpretation_certainty=LOW`, `logical_composition=OR_ANY`,
`github_observability=STRONGLY_OBSERVABLE`, `exhaustive=false`) — the
example's expected outcome (a safe projection demonstrating
illustrative/non-exhaustive alternatives) is unchanged.

**Files affected:** `src/gitscore/jobs/parsing/qualification.py` (new);
`tests/test_m11b_qualification_model.py` (new, 56 tests);
`evaluation/m11b/structured_qualification_controls.json` (one concept
reference fixed, all other fields and all 21 examples' annotations
unchanged); `docs/evaluation/MILESTONE_11_B_STRUCTURED_QUALIFICATION_MODEL.md`
(implementation addendum appended); `docs/ARCHITECTURE.md` (new §
"Milestone 11-B Stage 1"); `docs/PIPELINE.md` (follow-up note under the
job-description-parser stage). No existing `src/gitscore` file
modified; no concept registry, matcher, scoring, API, or frontend
change; `JOB_DESCRIPTION_PARSER_VERSION` stays `job_description_parser:v10`
(confirmed by test — no bump, since nothing observable changed).

**How the new logic works:** see the implementation addendum in
`docs/evaluation/MILESTONE_11_B_STRUCTURED_QUALIFICATION_MODEL.md` and
the module's own docstrings in `qualification.py`.

**Risks / limitations:** this model represents zero new recall —
`TECHNICAL_COMPETENCY` recall against the M11 generalization corpus is
unchanged at 1/11 (9%), confirmed byte-identical by re-running
`scripts/evaluate_m11_generalization.py`. Introducing a model that CAN
represent a technical competency is not the same as the live parser
recognizing more of them; no such claim is made anywhere in this
entry or the design doc's addendum. `qualification_kind` has no public
surface yet (Stage 3, unapproved). No technical-competency evidence
detector exists or is proposed (Stage 4+, unapproved, and explicitly
not scoped by the design doc's own §5 GitHub-evidence-boundary
analysis).

**How to test it:** `pytest tests/test_m11b_qualification_model.py -q`
(56 tests, all 13 requested categories, all 21 corpus examples
parametrized); full suite `pytest -q` (1261 pre-existing + 56 new =
1317 passed, 13 skipped, unchanged skip set);
`python scripts/evaluate_m11_generalization.py` (byte-identical to the
pre-M11-B baseline); `python scripts/evaluate_m10a_realworld.py`,
`python scripts/evaluate_m9b_preservation.py`, and
`python scripts/check_evaluation_staleness.py` (frozen `8c:v1`/
`8c:v1.1` FRESH, 0 diffs) all byte-identical to baseline.
`evaluate_m11a2_line_wrap.py` was also re-run to confirm its "baseline"
(current-parser) column is unchanged across all five corpora; the
script's own regenerated report file was reverted via `git checkout
--` afterward, since Stage 1 carries no authorization to update that
tracked artifact.

**Not done, by explicit scope:** the live parser is not rerouted
through this model (Stage 2+); no public API/schema change (Stage 3);
no technical-competency evidence detector (Stage 4+); no commit, no
push — held for separate, explicit authorization per the approval
message's own instruction.

## 2026-11-02 — Milestone 11-A2: Line-wrap segmentation integrity

**What changed:** Two coordinated fixes, approved separately from the
broader M11-B architecture question
(`docs/evaluation/MILESTONE_11_A2_LINE_WRAP_INTEGRITY.md`). (1)
`jobs/parsing/segmentation.py::segment_description()`'s own per-line
loop now extends an ordinary (non-heading, non-bullet) line's content
span across any immediately-following line, PROVIDED the gap between
them is a single newline (never across a blank-line paragraph gap),
the next line is not heading-shaped, the next line is not
bullet-prefixed, AND the accumulated text so far ends in a comma or
semicolon, OR a closed, generic English function-word/copula-verb/
subject-pronoun-contraction vocabulary (`_CONTINUATION_WORDS` — never
a technology/employer-specific term). The combined span is a DIRECT
SLICE of the original `description` — no rewritten string, no
offset-mapping table: consecutive physical lines separated by one
newline are already one contiguous range of the original text. (2)
`narrative.py`'s `_COMPANY_NARRATIVE_CUE`/`_LEARNING_NARRATIVE_CUE` and
`necessity.py`'s `_REQUIRED_MARKER`/`_PREFERRED_MARKER` had every
literal single-ASCII-space word separator widened to `\s+`, so a
phrase now spanning a reconstructed multi-line `Claim`'s embedded
newline is still recognized exactly as it would be with an ordinary
space. `JOB_DESCRIPTION_PARSER_VERSION` bumps `v9` → `v10`.

**Why:** M11-A1's own disclosed residual limitation — the real
`m11-unicode-contradiction-01` fixture's "We've built our platform on
Go and PostgreSQL..." sentence was still fabricating 3 spurious rows
(`database.postgresql`, `unresolved:our`, `category='experience'`)
even after M11-A1's fix, because the sentence is physically WORD-
WRAPPED across three source lines and `segment_description()` treats
every physical line as a fully independent unit — `"We've"` (end of
one line) and `"built our platform..."` (the next) were never seen
together by anything downstream, so M10E's own narrative-cue check
never got the chance to recognize the sentence it was designed for.
An evaluation-first design review measured three candidate designs (a
naive blanket text-join; a structural-only join with no content
judgment; the recommended structural+content-signal join) against a
new 38-control paired corpus PLUS six pre-existing regression corpora.
The naive candidates scored HIGHER on raw pair-equivalence but were
measurably unsafe — both corrupted a genuine two-item PREFERRED
requirement list (`"React"`/`"Node.js"`) into one merged claim, a
regression the recommended design does not introduce anywhere.

**A second, necessary companion defect found during the same
investigation, not anticipated by the mission brief:** reconstructing
the correct joined TEXT alone was not sufficient — `narrative.py`'s own
cue regex uses a literal ASCII space between `"we've"`/`"have"` and the
verb that follows, which does not match an embedded newline at exactly
that position. Confirmed directly: `contains_narrative_cue()` returned
`True` for the identical sentence with a real space, `False` with the
original line-wrap's `\n` there instead. The SAME literal-space
fragility is present in `necessity.py`'s `_REQUIRED_MARKER`/
`_PREFERRED_MARKER` (`"must have"`, `"must know"`, `"need to have"`)
and, confirmed but NOT exercised by any control in this corpus, in
`non_technical.py`'s own multi-word phrases — deferred to a separate
follow-up per explicit approval, not widened in this pass.

**A deliberately NOT-fully-solved residual, measured and disclosed, not
hidden:** a line ending in an ordinary content word (adjective/noun)
with no comma/semicolon/function-word, continuing in lowercase on the
next line, is NOT joined by the recommended design — 3 of 28 true
pairs in the new corpus (`m11a2-explicit-02`, `m11a2-nested-02`,
`m11a2-ambiguous-02`), and the real `m11-unicode-contradiction-01`
fixture's SECOND wrapped sentence (`"...however,\nwe are also open
to... with strong\nfundamentals..."`). A line-length-based secondary
signal was evaluated and explicitly REJECTED: a constructed
counter-example (`m11a2-bullets-02` — two genuinely separate,
period-less, 65-70-character bullet requirements stacked back to
back) shows a length heuristic would wrongly merge them. Accepted as a
documented limitation rather than risking that regression.

**Before/after (the real fixture, measured, not oversold):**
`m11-unicode-contradiction-01`'s fabricated-row count drops from **5
spurious rows to 2** — the first wrapped sentence's `database.postgresql`/
`unresolved:our`/one `category='experience'` row are gone entirely
(down to 0, a real `UnparsedClaim` instead); the second wrapped
sentence's 2 `category='experience'` rows remain, per the disclosed
residual above. M10A (SOTI/Manulife): byte-identical
(`false_positive_requirements`, `meets_ideal_outcome`, `meets_neither`
all unchanged — neither real posting's OWN existing content triggers
this specific residual). M9B: byte-identical except the version
string. M11's own generalization corpus: byte-identical (none of its
own tracked claim substrings cross this fix's specific trigger).
Frozen `8c:v1`/`8c:v1.1`: **zero diff**, confirmed via
`scripts/check_evaluation_staleness.py` on a clean pre-fix tree (via
`git stash`) AND the post-fix tree, for a true before/after. Full
suite: 1223 pre-existing (after M11-A1's own `v9` pin removal) − 1
removed (stale `v9` pin, superseded) + 38 new
(`tests/test_m11a2_line_wrap_integrity.py`, including the pre-
established 38-control corpus parametrized AS-IS, 3 explicitly
`skip`-marked as the disclosed residual gap) = **1261 passed, 13
skipped** (10 pre-existing M10E out-of-scope skips + 3 new M11-A2
residual-gap skips).

**Explicitly NOT done, per the approval message's own restrictions:**
no `qualification_kind`, no `Necessity` enum widening, no technical-
competency extraction, no matcher/scoring/API/schema change, no POS
tagger or new NLP dependency, no `non_technical.py` widening (deferred
separately), no length-based merging, no concept-registry expansion,
no LLM, no frontend change, no historical-gold edit.

**How to test it:** `tests/test_m11a2_line_wrap_integrity.py` (38
tests — the version pin, 24 of the pre-established 38-control corpus
pairs asserted exactly equivalent, 1 ambiguous-boundary non-fabrication
check, 9 named mandatory-safety-requirement tests, and the exact
real-posting traces including the measured, not-fully-solved
`m11-unicode-contradiction-01` residual). Full suite: `pytest -q` →
1261 passed, 13 skipped.

## 2026-11-02 — Milestone 11-A1: Narrow fabrication safety fixes

**What changed:** Two small, independently-testable fixes, both found
during Milestone 11's evaluation-first generalization review
(`docs/evaluation/MILESTONE_11_GENERALIZABLE_JOB_UNDERSTANDING.md`),
scoped and approved separately from M11's broader architecture
question. (1) `jobs/parsing/concepts.py::_consider_fragment` (the
sibling-confirmed branch of `find_conservative_unknown_terms` — fires
when a comma/"and"-joined list contains at least one ALREADY-confirmed
concept mention) now requires any MULTI-WORD leftover fragment to also
pass `looks_like_specific_technology_name` before being promoted to
`unresolved:<term>` — mirroring the shape gate M10D already applied to
`alternatives.py`'s own escalation branch, which this sibling function
never received. Single-word fragments are exempt (Python-package
naming convention is lowercase — `numpy`, `pandas` — so a
capitalization-only check cannot apply unconditionally). (2)
`jobs/parsing/narrative.py::_COMPANY_NARRATIVE_CUE` gains one new,
narrow alternative: `"our <optional token(s)> backend/frontend/
codebase/infrastructure"` — a small, generic, employer-agnostic
structural-noun vocabulary, not a verb-paired pattern like the three
existing alternatives.

**Why:** M11's own held-out corpus found both defects by direct trace,
independent of any line-wrap artifact (confirmed by re-testing each as
a single, unwrapped physical line): `"The system uses PostgreSQL, our
main database, for storage."` fabricated BOTH
`unresolved:our_main_database` and `unresolved:for_storage`;
`"Experience with PostgreSQL, and a willingness to learn, is
required."` fabricated `unresolved:is_required`; and `"...touching
everything from our Node.js backend to our React frontend."` — pure
company narrative — was scored as a REQUIRED `framework.react`
qualification because M10E's own narrative-cue regex only recognizes
"our product/platform/company/engineers/team... uses/builds/develops,"
never "our \<noun\> backend/frontend."

**Process, per the approval message's explicit requirement:** a new
regression file (`tests/test_m11_a1_fabrication_fixes.py`, eventually
16 cases including the version pin — both defects reproduced, both
fixes verified, and 9 positive/negative regression anchors) was
written and confirmed to fail EXACTLY the 5
intended cases against baseline (pre-fix) code, before any production
file was touched. Implementing the FIRST version of fix (1) with a
BARE `looks_like_specific_technology_name` check (no word-count
exemption) broke an existing, unrelated test
(`tests/test_api_serialization.py::test_concept_label_for_an_unresolved_concept_in_a_comma_enumeration`,
`"Python, pandas, and numpy"` → `unresolved:numpy`) — found by running
the full suite before considering the fix complete, not assumed safe;
the word-count exemption above is the fix for that regression, not the
original design.

**Before/after:** both of the two confirmed defects above no longer
fabricate (re-verified directly). Zero change to SOTI/Manulife's own
M10A benchmark (`false_positive_requirements`, `meets_ideal_outcome`,
`meets_neither` all byte-identical to the post-M10E numbers — neither
real posting contains either fixed pattern). Zero change to M9B
(byte-identical report). Zero change to the frozen `8c:v1`/`8c:v1.1`
parser benchmarks (`scripts/check_evaluation_staleness.py`, confirmed
both via direct read and a clean-tree `git stash` before/after
comparison — `parser_report.json`/`parser_report_v1_1.json` FRESH, 0
diff, both before and after). Full suite: 1209 pre-existing − 1 removed
(stale `v8` version pin, superseded) + 16 new = **1224 passed, 10
skipped** (the 10 skips are M10E's own
pre-existing, documented, out-of-scope corpus mismatches — unrelated
to and unaffected by this fix).

**Explicitly NOT done, per the approval message's own restrictions:**
no `qualification_kind` field, no `Necessity` enum widening, no
technical-competency extraction, no matcher/scoring change, no
line-wrap fix (the `unresolved:our` fabrication as ORIGINALLY traced in
M11's design doc turned out, on closer inspection during this
implementation, to be a DOWNSTREAM SYMPTOM of the still-untouched
line-wrap defect — see this entry's "Known remaining limitations"
below, not a third thing this fix closes), no concept-registry
expansion, no LLM, no frontend change, no historical-gold edit.

**Known remaining limitations (disclosed, not fixed):** the REAL
`m11-unicode-contradiction-01` posting's line-wrapped sentence still
produces a residual, reduced fabrication after this fix — the
`unresolved:our` row is gone (fix 1), but a stray `database.postgresql`
REQUIRED row and a stray `category="experience"` REQUIRED row persist,
because the line-wrap defect truncates "We've built our platform on
Go and PostgreSQL..." to a FRAGMENT that no longer contains "We've
built" at all (that phrase is left on the prior physical line), so
fix 2's cue can never see it. This is exactly why the production-
approval message treats line-wrap as its own, separately-gated
question rather than bundling it into A1. The bare-common-word-language
gap (Go/R/C-shaped names outside an enumerated list, M11 §4.4) and
every `TECHNICAL_COMPETENCY`/schema question remain entirely untouched,
as approved. `JOB_DESCRIPTION_PARSER_VERSION` bumps `v8` → `v9`,
consistent with every prior behavior-affecting milestone in this
series (a version-LABEL update only — no schema/API/matcher/scoring
contract changed).

**How to test it:** `tests/test_m11_a1_fabrication_fixes.py` (16
tests, including the `v9` version-pin — superseding M10E's own `v8`
pin, removed from `tests/test_m10e_narrative_requirement_semantics.py`
the same way M10E removed M10D's). Full suite: 1209 pre-existing − 1
removed (stale `v8` pin, superseded) + 16 new = **1224 passed, 10
skipped**.

## 2026-11-01 — Milestone 10E: Narrative vs. applicant-qualification semantics

**What changed:** Evaluation-first design review
(`docs/evaluation/MILESTONE_10E_NARRATIVE_REQUIREMENT_SEMANTICS.md`),
approved (production-approval message's six §5.8 mappings + two
mandatory safety gates, both verified), then implemented across three
small, additive pieces. (1) `Claim` (`jobs/parsing/segmentation.py`)
gains a `section_kind: str | None` field — the real `_SectionKind`
member name, which `necessity_hint` alone already collapses (a genuine
`REQUIRED` section and an ordinary `RESPONSIBILITY` bullet both became
`Necessity.REQUIRED`) — populated from the SAME `current_kind` the
existing loop already tracks; a new `document_has_any_recognized_heading()`
answers whether the WHOLE posting has a heading anywhere at all. (2)
`jobs/parsing/narrative.py` (new module): exactly two generic regexes —
a LEARNING-narrative cue and a COMPANY-narrative cue, never a
technology/employer-specific term — mirroring `non_technical.py`'s own
"small, curated table" precedent. (3) `jobs/parsing/necessity.py::resolve_necessity_hint()`
(new function; `infer_necessity()` itself is UNCHANGED): an explicit
local REQUIRED/PREFERRED marker always wins unconditionally first;
otherwise a claim's section must be a genuine `REQUIRED`/`PREFERRED`
heading, OR `current_kind is None` with NO heading anywhere in the
whole document (preserving the original Milestone 6B "no section at
all" default byte-for-byte); every other origin is downgraded to
`None`; finally even a section-eligible claim is vetoed by a narrative
cue. Called once, by `parser.py::_requirements_from_claim`, before
`infer_necessity()`. `JOB_DESCRIPTION_PARSER_VERSION` bumps `v7` →
`v8`.

**Why:** M10A's own traced-but-deferred real-posting defects, left
explicitly out of scope by both M10C and M10D. SOTI's narrative
"Opportunity" paragraph ("The technologies you learn... languages like
C#, or deepening your knowledge of databases by leveraging SQL...") was
fabricated into a scored `(language.csharp, language.sql)`
alternative-group requirement — `current_kind is None` (the heading
above it, a bare "Opportunity," never classifies) defaulted the
paragraph's necessity to REQUIRED via the SAME mechanism that correctly
defaults a genuinely unsectioned posting, with no way to tell "no
section at all" apart from "a preamble before this same document's own
later real sections." Manulife's "Collaborate with engineering and
business teams to build user-focused solutions." (a `Position
Responsibilities:` bullet) was fabricated into a scored
`category='soft_skill'` requirement via `non_technical.py`'s generic
`collaborat*` pattern — `RESPONSIBILITY` sections default to
`Necessity.REQUIRED` by design (correctly, for the necessity VALUE),
but nothing downstream ever asked whether the bullet was describing a
duty or stating a qualification before running every detector against
it anyway. An evaluation-first design review built a 51-control corpus
(`evaluation/m10e/narrative_controls.json`) and compared three
candidate designs (text-pattern-only exclusion; section-origin-aware
gating; the two combined). The approved "Candidate C" fixed both real
postings exactly (removing only the two confirmed-bad rows, nothing
else) and matched gold on 41/51 synthetic controls, with zero
regressions measured across M10A, M10D, M9B, and the frozen
`8c:v1`/`8c:v1.1` benchmarks.

**A scope decision found only during implementation regression-testing
(not anticipated by the design review, raised explicitly for product
decision rather than resolved unilaterally):** the evaluation corpus's
own `m10e-d3`/`d4` controls generalized past the two confirmed real
defects to also suppress an ORDINARY technology mention inside a
`RESPONSIBILITY` bullet with no soft-skill pattern involved at all
(e.g. "Build and maintain ETL pipelines using Python."). This directly
conflicted with four pre-existing, Milestone 6B "manual validation"
tests that have validated the OPPOSITE since before M10A — a
Responsibilities bullet naming a real technology IS legitimate,
checkable signal. Approved resolution: accept the broader, uniform
suppression (a Responsibilities bullet describes work, not a
credential check, regardless of whether it also names a technology)
and update those four tests, each with a dated comment explaining why.
An explicit local REQUIRED/PREFERRED marker — even mixed into the same
duty sentence ("...; Java experience is required.") — still always
wins, confirmed by both mandatory safety gates below.

**Mandatory safety gates, both verified against the REAL production
parser (not a prototype), before this change was considered complete:**

- *Gate A (genuine preamble qualifications):* "Applicants must know
  Python." before an "About Us:" section, "Experience with Java is
  required." before a "Benefits:" section, a truly unsectioned posting,
  and the real SOTI document — all four preserve their explicit
  qualifications; SOTI's narrative paragraph alone is suppressed, its
  genuine "Required skills:" section is unaffected. (Finding, fixed
  during this gate's own verification: `_REQUIRED_MARKER`
  — `jobs/parsing/necessity.py`, reused unchanged elsewhere — did not
  recognize "must know" as a local marker at all, only "must have"/
  "must be"; a single, narrow addition, `\bmust know\b`, closes this,
  confirmed to affect no other existing fixture.)
- *Gate B (mixed responsibility/qualification statements):* "Develop
  Java services." and "Collaborate with engineers." under
  `Responsibilities:` are no longer automatic requirements; "Develop
  Java services; Java experience is required.", "You will learn SQL,
  but SQL knowledge is preferred.", and a genuinely required soft skill
  under `Required Qualifications:` all still produce their exact,
  correct scored requirement — the local-marker override is checked
  FIRST, before section origin or narrative-cue logic ever runs, in
  every candidate.

**Before/after (real postings, `evaluate_m10a_realworld.py`, frozen
M10A gold unchanged):** SOTI — `false_positive_requirements` 1 → 0,
`meets_ideal_outcome` 6/12 → 7/12, `meets_neither` `[m10a-soti-01]` →
`[]`. Manulife — `false_positive_requirements` 1 → 0,
`meets_ideal_outcome` 40/43 → 41/43, `meets_neither` `[m10a-man-06]` →
`[]`. M10C heading classification report: byte-identical. M10D's own
41-control corpus and pytest suite: byte-identical (isolated claim
fragments with no section headings — this milestone's mechanism cannot
reach them). M9B preservation metrics: byte-identical except the
version string. Frozen `8c:v1`/`8c:v1.1` (`scripts/check_evaluation_staleness.py`,
re-run on a clean pre-M10E tree for comparison): **zero diff**.

**M10D's own `evaluation/reports/m10d_alternatives_report.{json,md}`
— preserved, NOT regenerated, by explicit product decision, confirmed
consistent with M10D's own documented intent.** Phase 0 of this
milestone initially flagged that file's `baseline` column (`28/41
exact_match, 5 fabricated`) as unexpectedly stale against a live
re-run of today's code (`30/41, 0 fabricated` — M10D's own `e51713a`
fix landed correctly). `docs/evaluation/MILESTONE_10D_ALTERNATIVE_SEMANTICS.md`'s
own "Implementation addendum" clarifies this was INTENTIONAL, not an
oversight: that report is "left exactly as they were at design time
(the true pre-implementation snapshot)," with M10D's own authoritative
post-implementation check living in
`tests/test_m10d_alternative_requirement_semantics.py` instead.
Regenerating it was considered for this milestone and explicitly
rejected, consistent with that stated intent.

**Risks / limitations (disclosed, not fixed):**
- *SKIP blanket-suppression gap, newly found.* A recognized
  `NON_QUALIFICATION`/`SKIP` heading (e.g. Manulife's own real "When
  you join our team:") suppresses every line after it unconditionally,
  with no diagnostic fallback at all — unlike `UNKNOWN`. An explicit
  qualification after such a heading is lost with zero trace today.
  Deferred to a separately-scoped follow-up (different mechanism,
  its own regression surface).
- *`non_technical.py` vocabulary-coverage gaps.* Generic phrasing this
  milestone's corpus surfaced ("knowledge of database fundamentals,"
  "willingness to learn new technologies," "strong technical
  background") has never been recognized, under ANY section, by
  baseline OR this fix — out of scope, needs expanding
  `non_technical.py`'s own category table.
- No third real posting beyond SOTI/Manulife was examined.
- This milestone does not claim to resolve every narrative-vs-
  qualification ambiguity a posting can contain — only the two
  confirmed real defects and the generalizable mechanism behind them.

**How to test it:** `tests/test_m10e_narrative_requirement_semantics.py`
(63 tests — the parser-version pin, both exact real-posting traces,
both mandatory safety gates (9 tests), and all 51 M10E corpus controls
run against the REAL production parser, 10 explicitly `skip`-marked as
pre-existing out-of-scope gaps rather than silently passing). Four
pre-existing tests revised with dated rationale comments
(`tests/test_job_parser.py::test_manual_validation_data_engineering`,
`::test_bare_verb_phrase_does_not_produce_a_false_positive_unresolved_concept`,
`tests/test_assessment_manual_examples.py::test_data_engineer_assessment_python_and_postgres_only`,
`tests/test_matching_manual_examples.py::test_data_engineer_candidate_with_python_and_postgres_only`);
one stale version-pin test removed
(`tests/test_m10d_alternative_requirement_semantics.py::test_parser_version_bumped_to_v7`,
superseded). Full suite: 1157 pre-existing − 1 removed + 63 new =
**1219 collected, 1209 passed, 10 skipped**.

## 2026-11-01 — Milestone 10D: Alternative-requirement semantics

**What changed:** Evaluation-first design review
(`docs/evaluation/MILESTONE_10D_ALTERNATIVE_SEMANTICS.md`), approved
(five §6.7 STOP questions all approved), then implemented, entirely
within `jobs/parsing/alternatives.py`. `classify_alternative_claim()`
now tries an explicit ANY-of trigger-phrase path first
(`_classify_any_of_trigger`): six lead-in phrases ("one or more of,"
"at least one," "any one of," "one of the following," "any of,"
"either of" — "at least one" deliberately bare, no required trailing
"of," to match the real Manulife posting's own wording) checked
independently of a literal "or" at all. Once found,
`_find_any_of_list_region()` locates the actual list that follows — a
parenthetical example clause, a colon-introduced list, or the bare
remainder — and resolves it through `_classify_segment_list()`
(extracted, not duplicated, from the function's prior body), the same
loop the ordinary bare-"or" path already used. That ordinary path
(`_split_alternative_segments`) gained an idiom guard (`_IDIOM_OR_MORE`)
protecting "<number-word/digit> or more" from being read as a list
separator. `_resolve_segment()`'s own `clean_list_fragment`-escalation
branch — previously an UNCONDITIONAL promotion to `unresolved:<term>`,
with no shape check at all — now requires
`looks_like_specific_technology_name`, the same gate the sibling
ALL-UNRESOLVED-group rescue already used. `JOB_DESCRIPTION_PARSER_VERSION`
bumps `v6` → `v7`.

**Why:** M10A found two real-world alternative-requirement bugs left
open by M10C — Root Cause 4 (Manulife's "at least one programming
language (e.g., Java, Python, Go, JavaScript)" has no literal "or" at
all, so group detection never even attempted, minting four independent
REQUIRED rows instead of one) and Root Cause 5 (SOTI's "one or more of
the following programming languages: ..." — the idiom's own "or" split
like an ordinary list separator, losing the 9-language ANY-of
structure to the conservative placeholder). An evaluation-first design
review built a 41-control corpus
(`evaluation/m10d/alternative_controls.json`, annotated before any
candidate classifier existed) and compared four prototype designs
(idiom guard alone; trigger-phrase recognition alone; the two
combined; the combination plus a top-level AND-boundary split). The
approved "Candidate A+B" matched the broadest candidate's coverage on
every control that actually mattered (38/41 exact match, zero
fabrications, zero regressions) without adopting a broader AND/OR
structural classifier whose only edge was two MIXED-case answers
correct by coincidence of phrasing rather than a real grammar.

**A third defect found and fixed during the same investigation, not
in M10A's original framing:** reproducing Root Cause 5 on a
differently-punctuated "one or more of" sentence ("Experience with one
or more of the following languages: Python, Java, Go") revealed that
`_resolve_segment()`'s escalation branch could fabricate a spurious
`unresolved:one` — or, with a colon immediately after "of," a garbled
`unresolved:more_of:_c` — merged into an otherwise-real alternative
group, one punctuation choice away from SOTI's own sentence. Root
cause: that branch promoted ANY `clean_list_fragment`-accepted term to
`unresolved:<term>` with no shape check, unlike its sibling rescue path
inside `classify_alternative_claim()`. Fixed by adding the same shape
gate; confirmed non-regressing against every previously-correct
alternative-group case because the caller's own pre-existing safety
net already excluded these shapeless promotions from scoring — this
change only moves that exclusion one step earlier.

**Before/after (real postings):** SOTI's 9-language requirement, 0
assessable rows before, now one correctly-structured
`alternative_concept_ids` group of 9 (including safely-promoted
`unresolved:haskell`/`unresolved:lua`, neither registered). Manulife's
"at least one programming language" requirement, previously four
independent rows (one fabricating `unresolved:go` instead of the real
`language.go`), now one correctly-structured group of 4.
`evaluate_m10a_realworld.py`: Manulife's `malformed_alternative_groups`
1 → 0, `meets_ideal_count` 39/43 → 40/43,
`neither_ideal_nor_fallback` shrinks from `[man-06, man-10]` to
`[man-06]` only. SOTI's own counts are unaffected — its one remaining
defect (the C#/SQL learning-narrative false positive) is an explicitly
out-of-scope, pre-existing limitation, untouched by design. M9B
preservation metrics: byte-identical except the version string. M10C
heading classification report: byte-identical. Frozen 8c:v1/8c:v1.1:
**zero diff**.

**Risks / limitations:** a newly-identified Root Cause 6 — a MIXED
AND/OR shape ("Python or Java and SQL") is still silently flattened
into one over-permissive ANY-of-3 group today, explicitly NOT
addressed by this milestone (deferred, needs genuine AND/OR precedence
detection, reserved for a future, separately-approved milestone); the
six-phrase trigger table is derived from the two real postings plus
M10A's own proposal, not a larger real-world corpus, so a differently
-worded real posting may still only get the safe (never-fabricating),
structure-losing fallback rather than the ideal grouping. **A
post-implementation audit, using deterministic synthetic candidate
profiles, found a second, PRE-EXISTING limitation (not introduced or
worsened by this milestone): a candidate with real evidence of an
unlisted-but-plausible technology scores identically
(`MatchStatus.NOT_OBSERVED`) to a candidate with no relevant evidence
at all**, for any alternative-group requirement built from an
illustrative `"(e.g., ...)"` list (e.g. Manulife's "at least one
programming language (e.g., Java, Python, Go, JavaScript)" — a
Rust-only candidate is indistinguishable from a no-language-evidence
candidate). `JobRequirement` retains no illustrative-vs-exhaustive
metadata, and the frontend discloses nothing about this today. This
is disclosure only, not a mitigation — it changes no code and does not
reduce the risk of a misleading result for a real candidate. Fixing it
needs either a new `JobRequirement` field or new matcher logic (both
schema/matcher changes requiring their own separate approval); tracked
as a future, separately-scoped correctness milestone, distinct from
(but related in kind to) M10E's narrative-versus-qualification
problem. Full detail:
`docs/evaluation/MILESTONE_10D_ALTERNATIVE_SEMANTICS.md`'s
post-implementation audit addendum.

**How to test it:** `tests/test_m10d_alternative_requirement_semantics.py`
(61 tests — all 41 corpus controls, the real SOTI/Manulife sentences,
the frozen `general_swe_01` positive control, both fabrication
-reproduction variants, concept-resolution hazards (`C` vs. `C++`,
`Java` vs. `JavaScript`), negative controls (bare "at least one" in
non-enumeration prose, generic category nouns, true AND lists), and
source-span/determinism/single-requirement-denominator checks). Full
suite: 1096 pre-existing tests unchanged + 61 new = 1157 passed.

## 2026-10-31 — Milestone 10C: Real-world heading recognition

**What changed:** Evaluation-first design review
(`docs/evaluation/MILESTONE_10C_SECTION_CLASSIFICATION.md`), approved,
then implemented. `jobs/parsing/segmentation.py`'s small exact-phrase
heading table (~30 fixed phrases) is replaced by `_classify_heading_line()`:
a structural "is this line heading-shaped at all" gate (short, not a
bullet, never sentence-terminal punctuation, never a colon followed by
an inline comma-separated list) fully independent of word content, then
anchored, word-boundary-bounded root-word families
(`REQUIRED`/`PREFERRED`/`RESPONSIBILITY`/new `LEARNING`/
`NON_QUALIFICATION`, the last reusing the existing `SKIP` kind) with
built-in collision exclusions (e.g. `qualif*` never fires REQUIRED when
`preferr*` is also present, so "Preferred Qualifications" resolves
correctly). A line matching more than one family, or none, maps to the
existing `UNKNOWN` kind rather than a forced, fixed-precedence winner.
`_SectionKind.LEARNING` is a new internal kind (never maps to a
`Necessity`, exactly like `UNKNOWN`). `concepts.py` gained a small
shared constant (`TECHNICAL_LEAD_IN`, moved from `parser.py`, still used
only there). `JOB_DESCRIPTION_PARSER_VERSION` bumps `v5` → `v6`.

**Why:** M10A found the old table missed extremely common real-world
phrasing ("Required skills" vs. "Requirements," "Position
Responsibilities" vs. "Responsibilities," "About SOTI" vs. "About Us")
and had no category at all for a "what you will learn" section. An
evaluation-first design review compared three candidate designs against
an independently-authored 78-entry heading corpus
(`evaluation/m10c/heading_controls.json`); the selected design scored
highest (0.987 pre-implementation; 0.923 post-implementation-fix,
measured honestly after a real regression was found and fixed, see
below) with zero high-severity unsafe misclassifications.

**Implementation-discovered regression, fixed before landing:** an
early version of the shape gate treated a single bare, title-cased word
with no colon/Markdown/ALL-CAPS as heading-shaped by itself — which
swallowed a real, un-bulleted, one-item-per-line requirement list
("Python"/"PostgreSQL"/"Docker" each on their own line) as a phantom
`UNKNOWN` heading, caught by the pre-existing
`test_newline_separated_requirements_without_bullets` test. Fixed: plain
title-case alone now also requires at least one matched family root;
colon/ALL-CAPS/Markdown remain sufficient alone (consistent with M10B's
already-shipped colon-heading precedent). Accepted tradeoff: a rare,
family-root-less generic catch-all heading with no colon/Markdown/
ALL-CAPS (e.g. "Additional Information") is now also left unrecognized
— safe (never fabricates a family), not a regression against today's
pre-M10C baseline (which never recognized it either).

**Before/after (real postings):** SOTI — `Required skills:`/`About SOTI`/
`What you will learn:` now recognized; SOTI's one confirmed genuine
qualification ("curiosity, a desire to learn...") moves from zero trace
to a guaranteed `unparsed_claims` diagnostic; SOTI's one confirmed false
positive (a fabricated `(language.csharp, language.sql)` alternative
group from learning-exposure prose) is **unchanged** — its only
surviving heading, "Opportunity," is a single bare word with no family
root, exactly the shape the regression fix above excludes; this is
Root-Cause-4/5-adjacent and explicitly out of scope (reserved for M10D).
Manulife — all 7 of its missing headings (`Position Responsibilities:`,
`When you join our team:`, `Application instructions:`, `About Manulife
and John Hancock`, `Working Arrangement`, plus `Required`/`Preferred
Qualifications:` already recognized) now recognized; 5 of 6 previously
100%-invisible "Position Responsibilities" duty bullets now land in
`unparsed_claims`; the 6th ("Collaborate with engineering and business
teams...") now produces one scored, non-fabricating `soft_skill`
`JobRequirement` (`concept_id=None`, never enters `assess_job()`'s
denominator) via the SAME pre-existing non-technical pattern already
used elsewhere in this exact posting — flagged explicitly as meeting
neither this entry's `ideal_outcome` nor `acceptable_fallback`, a new,
disclosed finding, not hidden. `meets_ideal_outcome`: 34/43 → 39/43.
M9B preservation metrics: byte-identical except the version string.
Frozen 8c:v1/8c:v1.1: **zero diff**.

**Risks / limitations:** the "Additional Information"-class
family-root-less heading gap above; Manulife's "Collaborate..." duty
bullet becoming a visible (never scored/denominator-affecting)
REQUIRED soft-skill row; SOTI's pre-existing Root-Cause-4/5 false
positive, unchanged; the Manulife "at least one programming language
(e.g., ...)" OR-structure loss and the "one or more of" idiom-blind
splitting — both explicitly out of scope, reserved for M10D.

**How to test it:** `tests/test_m10c_heading_classification.py` (121
tests — both the 78-entry design corpus and an independently-authored,
post-implementation 18-entry held-out set, run against the real,
shipped classifier; section-transition, Unicode/Markdown/bullet
formatting, no-scoring-from-LEARNING/NON_QUALIFICATION, and source-span/
determinism coverage) plus two amended `tests/test_m10b_section_state_safety.py`
assertions (explicitly documented, narrowly-scoped overrides — see that
file's own module docstring — for the two M10B controls whose
underlying heading is now correctly recognized). Full suite: 1096
passed (975 baseline + 121 new), 0 failed.

## 2026-10-31 — Milestone 10B: Safe section-state handling

**What changed:** Fixes M10A's highest-severity traced defect
(`docs/evaluation/MILESTONE_10A_REALWORLD_PARSING_FAILURES.md` Root
Cause 2) with a narrow, design-reviewed-first fix
(`docs/evaluation/MILESTONE_10B_SECTION_STATE_SAFETY.md`). Three files
under `src/gitscore/jobs/parsing/`:
- `segmentation.py` — new internal `_SectionKind.UNKNOWN` member. A
  colon-terminated, non-bulleted, table-unmatched heading-shaped line
  now resets `current_kind` to `UNKNOWN` instead of silently leaving a
  stale REQUIRED/PREFERRED kind in effect — but ONLY when
  `current_kind` was already a real recognized kind (never from `None`,
  preserving the separate, pre-existing "no section at all → default
  REQUIRED" policy untouched) and ONLY for a non-bulleted line (a
  bulleted colon lead-in inside an already-open section, e.g.
  "- Experience with the following:", is a list item, never a section
  boundary — found and fixed during approval review, before
  implementation). `Claim.necessity_hint` widens to `Necessity | None`.
- `necessity.py` — `infer_necessity()`'s return type widens to
  `Necessity | None`; its local-marker-wins precedence (Milestone 6B
  Part 7) is completely unchanged.
- `parser.py` — `_requirements_from_claim()` short-circuits to `[]`
  when necessity is `None`, routing the claim through the EXISTING
  Milestone 9C `UnparsedClaim` mechanism (no new diagnostic type).
  `JOB_DESCRIPTION_PARSER_VERSION` bumps `v4` → `v5`.

**Why:** M10A found that once ANY heading failed to match the small,
generic heading table, the previously-open section's necessity kept
applying to everything after it for the rest of the document — company
bio, legal/EEO text, salary disclosures, even a blog-post `.html` URL —
producing scored, fabricated `JobRequirement` rows (e.g. a Manulife
salary-disclosure sentence scored as a `PREFERRED` requirement). The
mission was explicit that `UNKNOWN` must never default to REQUIRED or
PREFERRED merely because the `Necessity` enum has only two values, and
that no `JobRequirement` schema/API/matcher/scoring change be made
without a separate STOP/approval — both honored: zero new public types,
zero schema bumps beyond the parser's own version string, zero matcher
or scoring-formula changes.

**Before/after (real postings, the exact two M10A sourced):** Manulife
— false-positive `JobRequirement` rows: 5 → **0** (zero new false
positives introduced); `meets_ideal_outcome`: 29/43 → 34/43. SOTI —
**byte-identical**, 0 changes (it never exhibited this specific defect;
every unrecognized heading in it occurs while `current_kind` was
already `None`, not a stale real section — confirms the fix is
correctly scoped to the actual defect). `evaluate_m9b_preservation.py`:
byte-identical metrics except the `parser_version_under_test` string
(every M9B template uses only a recognized heading or none at all).
The frozen 8c:v1/8c:v1.1 parser evaluations
(`evaluation/reports/parser_report*.json`): byte-identical, zero diff.

**Design process:** this was a bounded design review FIRST (Phase
0–3 trace, options evaluation, an 11-control corpus authored
independently of any parser output), presented for approval before any
`src/gitscore` file was touched. Approval review itself caught a real
gap in the originally-drafted trigger rule (the bulleted-colon-lead-in
case above), fixed and re-verified against all original controls plus
a 12th new control before implementation began — see
`docs/evaluation/MILESTONE_10B_SECTION_STATE_SAFETY.md` §3.1b for the
full amendment trace.

**Risks / limitations:** a small amount of `unparsed_claims`
diagnostic-list visibility is traded for silence on content that is
*definitely* not requirement text (pure company narrative, pure job
duties) once it falls under `UNKNOWN` — this mirrors the exact
drop behavior un-sectioned marketing prose already had before this
milestone (Root Cause 3, unchanged), not a new kind of loss, and never
drops genuinely ambiguous-but-plausibly-relevant text (confirmed via
all 12 controls — such content is always preserved as a diagnostic).
Explicitly NOT addressed, per Phase 4 scope boundary: the narrow
heading-recognition vocabulary itself (M10A Root Cause 1), the
Manulife "at least one ... (e.g., ...)" OR-structure loss (Root Cause
4), and the "one or more of" idiom-blind splitting (Root Cause 5) — all
three remain exactly as limited as before.

**How to test it:**
```
python -m pytest                                      # 975 passed (947 + 28 new)
python -m pytest tests/test_m10b_section_state_safety.py -v   # 28 passed
python scripts/evaluate_m10a_realworld.py              # Manulife FP: 5 -> 0
python scripts/evaluate_m9b_preservation.py            # byte-identical metrics
python scripts/evaluate_job_parser.py                  # 8c:v1, byte-identical
python scripts/evaluate_job_parser.py --corpus-version 8c:v1.1   # byte-identical
```

**Files affected:** `src/gitscore/jobs/parsing/segmentation.py`,
`src/gitscore/jobs/parsing/necessity.py`,
`src/gitscore/jobs/parsing/parser.py`;
`tests/test_m10b_section_state_safety.py` (new, 28 tests);
`evaluation/m10b/section_state_controls.json` (new, 12 independently-
authored controls); `docs/ARCHITECTURE.md` (§32, new), `docs/PIPELINE.md`,
`docs/evaluation/MILESTONE_10B_SECTION_STATE_SAFETY.md` (design review +
implementation results), `docs/CHANGELOG_DEV.md` (this entry). No
`JobRequirement`/`JobRequirementProfile` schema change, no API field
added/renamed/retyped, no matcher/scoring-formula change, no frozen
gold modified.

## 2026-10-25 — Milestone 9G: Headline coverage-gap visibility

**What changed:** Frontend-only. Implements the one M9F-approved,
presentation-only design (Option C) — nothing under `src/gitscore/` was
touched. `AlignmentHeadline.tsx` now shows a small, non-alarming
`"Known coverage gaps"` badge beside the score (or "Not available")
whenever a known interpretation gap exists — derived entirely from two
counts the API already returns (`assessment.uninterpreted_requirement_count`,
M9C; `assessment.unparsed_claim_count`, M9E), combined with a plain
boolean OR (`hasKnownCoverageGap()`, `lib/labels.ts`) that never
double-counts, since the two counts are already guaranteed mutually
exclusive per source claim. Alongside the badge: a fixed, generic
sentence ("This score excludes job-description text GitScore could not
interpret.") and, when real claim text is available, a concrete,
verbatim excerpt naming the first unparsed claim (truncated past 140
characters for very long claims, with a plain "+N more" count for
additional ones) — reusing `AnalyzeResponse.unparsed_claims[].text`,
never synthesizing text. The two pre-existing M9C/M9E caveat sentences
are unchanged and still render alongside the new badge/summary. When no
gap is known, nothing new renders — the product never claims
"Complete"/"Fully analyzed"/"100% requirements interpreted," since
absence of a known diagnostic is not proof of exhaustive parsing.

**Why:** M9F's design review (`docs/evaluation/MILESTONE_9F_REQUIREMENT_COVERAGE_DESIGN.md`)
found that closing the silent-drop gap at the parser level would NOT,
by itself, change `karpathy × computer_vision_01`'s `100` (the OpenCV
row would be `NOT_ASSESSABLE`, already excluded from the denominator) —
only a presentation change can move or qualify that number. All three
of M9F's approval questions were answered: adopt presentation-only
disclosure now (approved); scope a technical-competency detector as a
separate, evaluation-first milestone (approved, not started); reject
unconditional preservation of every segmented claim as a formal
requirement (approved, rejected with cause).

**Before/after (`karpathy × computer_vision_01`, real, live-verified
values):** before — a bare "100 / 100" with no on-page indication
anything was uncertain; after — "100 / 100 [Known coverage gaps]" plus
"Potential requirement not interpreted: \"Experience with OpenCV for
image processing\"" directly at the headline. The `100` itself is
confirmed byte-identical before and after — this is a presentation
change only.

**Risks / limitations:** the badge cannot distinguish REQUIRED from
PREFERRED gaps (`UnparsedClaim` carries no necessity field at all, by
construction — inventing one would violate this milestone's own
no-invented-criticality constraint). The "qualified headline" sub-option
(e.g. "100 — based on 4 of 5 extracted requirements") was not
implemented, only the badge + excerpt combination. Browser click-through
was attempted (offline-fixture backend + Next.js dev server both
confirmed listening) but this session's Chrome browser-automation tool
did not respond — the same limitation M9D's and M9E's sessions each
hit; verification instead relies on 10 new RTL tests plus a clean
type-check/build. The 23%-silent-drop rate itself is unreduced — only
more visible.

**How to test it:**
```
cd frontend && npx vitest run       # 46 passed (36 + 10 new)
cd frontend && npm run type-check   # clean
cd frontend && npm run build        # succeeds
python -m pytest                    # 934 passed (unchanged -- no backend touched)
```

**Files affected:** `frontend/src/lib/labels.ts`,
`frontend/src/components/AlignmentHeadline.tsx`,
`frontend/src/components/ResultView.tsx`, `frontend/src/app/globals.css`,
`frontend/src/components/__tests__/ResultView.test.tsx` (+10);
`docs/ARCHITECTURE.md` (§31, new), `docs/PIPELINE.md`,
`docs/evaluation/MILESTONE_9G_HEADLINE_COVERAGE_VISIBILITY.md` (new),
`docs/CHANGELOG_DEV.md` (this entry). No file under `src/gitscore/`
touched. No API field added, renamed, or retyped.

## 2026-10-25 — Milestone 9F: Requirement coverage & score validity (design review)

**What changed:** Nothing in `src/gitscore/` or `frontend/` — a
design-and-evaluation-only milestone. Live-traced all six of M9B's
measured silent-drop requirement claims through every internal parser
gate (`_unresolved_requirement_signal`, `_TECHNICAL_LEAD_IN`,
`clean_list_fragment`, `find_conservative_unknown_terms`) and
classified them into a precise five-category taxonomy; evaluated three
design alternatives (unconditional preservation, a scoped
technical-competency detector, presentation-only safeguards) against
false-positive risk, scoring impact, and schema/API implications;
re-verified live (real `karpathy` fixture, real running API) exactly
what `karpathy × computer_vision_01`'s 100 does and does not represent;
proposed a new positive/negative control set for evaluating a future
verb-led competency detector (design content only, no corpus file
committed).

**Why:** M9B, M9C, M9D, and M9E each raised the same still-open
question (the 23% silent-drop gap's long-term disposition) without a
final answer. This milestone exists to make that decision explicit
rather than deferring it a fifth time.

**Key finding:** closing the silent-drop gap (via either alternative
design evaluated) would NOT, by itself, change `karpathy ×
computer_vision_01`'s `alignment_score` of 100 — the resulting row would
be `NOT_ASSESSABLE` (excluded from the denominator by the EXISTING,
unchanged formula), not `NOT_OBSERVED`. Only a presentation-layer
change can actually move or qualify that specific number.

**Recommendation (see `docs/evaluation/MILESTONE_9F_REQUIREMENT_COVERAGE_DESIGN.md`
for full detail, trade-off tables, and three explicit approval
questions):** adopt presentation-only coverage disclosure (a visible
"partial coverage" signal, naming the specific unparsed claim) as the
next implementation milestone, requiring no schema/matcher/scoring
change; separately scope evaluation-only work for a narrow,
verb-led competency detector gated on zero false positives against a
new negative-control set; formally reject unconditional preservation
(demonstrated, live, to convert a real non-technical sentence
misplaced under a "Requirements:" heading into a formal,
indistinguishable-from-real requirement row).

**Files affected:** `docs/evaluation/MILESTONE_9F_REQUIREMENT_COVERAGE_DESIGN.md`
(new), `docs/CHANGELOG_DEV.md` (this entry). No file under `src/gitscore/`
or `frontend/` touched. No frozen gold modified.

**DO NOT COMMIT. DO NOT PUSH. Awaiting approval on §9's three
questions before any implementation begins.**

## 2026-10-25 — Milestone 9E: Assessment clarity & trust corrections

**What changed:** Fixes three confirmed, M9D-measured presentation
defects — WITHOUT touching the matcher, scoring formula, concept
registry content, parser semantics, or retrieval/ranking.

1. **Headline undercounted interpretive uncertainty (Workstream A).**
   `AssessmentOut`/`Assessment` gained `unparsed_claim_count` (additive)
   — a plain `len(unparsed_claims)` passthrough — rendered as a SECOND,
   separate headline caveat (`AlignmentHeadline.tsx`,
   `unparsedClaimsCaveat()` in `lib/labels.ts`), deliberately never
   summed with the existing `uninterpreted_requirement_count`: the two
   counts measure category-different facts (a real row GitScore could
   not interpret, vs. text that never became a row at all), and a claim
   is structurally counted by at most one of them, never both.
2. **Duplicate-looking requirement text, including across contradictory
   statuses (Workstream B).** Confirmed NOT a matcher/parser bug — two
   rows sharing identical text is the intentional Milestone 9A/6B.1
   "one row per matched concept" design. New
   `gitscore.concepts.registry.concept_display_label()` (additive) and
   `RequirementOut.concept_label` (additive) expose a short,
   human-readable label (e.g. "infra.kubernetes" → "Kubernetes"); the
   frontend now appends it to a requirement's displayed text whenever
   that exact text repeats anywhere in the result (`ResultView.findDuplicateRequirementTexts()`),
   so "Strong experience with Docker and Kubernetes" renders as
   "...(Docker)" and "...(Kubernetes)" instead of appearing to
   contradict itself under "Supported" and "Not observed" at once.
3. **Evidence provenance and strength (Workstream C).** `EvidenceList.tsx`
   now links each cited repository to `https://github.com/{owner}/{name}`
   (`lib/github.ts`, new) — built only from fields the API already
   returns, repository-root only (never a file-specific/branch-guessed
   deep link, since no default-branch fact exists anywhere in the
   domain model). Each evidence item also shows a short, calibrated,
   non-numeric description of what its `evidence_type` represents
   (`evidenceTypeDescription()`, `lib/labels.ts`) — no new strength
   score was invented.
4. **`karpathy × computer_vision_01` re-verified, not re-fixed
   (Workstream D).** Confirmed live that the omitted "OpenCV" requirement
   was already visible in `unparsed_claims` (M9C), but the pre-9E
   headline caveat never surfaced it (`uninterpreted_requirement_count`
   was `0` for this posting). Workstream A's fix now surfaces it; the
   score itself (100, required 3/3, preferred 1/1) is confirmed
   byte-identical before and after — this milestone does not resolve the
   underlying 23%-silent-drop gap (M9B/M9C), only makes the existing
   diagnostic visible instead of silent.

**Why:** M9D's own product-validation pilot
(`docs/evaluation/MILESTONE_9D_PRODUCT_VALIDATION.md`) found and ranked
these as its top prioritized improvements (§9: risks #1, #4, #11) and
recommended this exact scope as the next milestone (§10), explicitly
deprioritizing the evidence-weighting calibration risk (#2) and the
23%-silent-drop disposition decision (#3) until after a human pilot runs.

**Root causes (traced directly in source, not assumed):**
- Workstream A: `api/serialization.py`'s pre-9E `uninterpreted_count`
  only summed `not_assessable` rows with
  `interpretation_status == "unparsed_placeholder"`, structurally
  excluding `JobAnalysisResult.unparsed_claims` (M9C's own, strictly
  more severe diagnostic for claims that never became a row at all).
- Workstream B: `RequirementSection.tsx`'s `RequirementItemsList`
  rendered only `requirement.text`, never `concept_id`/`matched_concept_ids`
  — confirmed, live, against `devops_cloud_01`
  ("Docker and Kubernetes" → `infra.docker` + `infra.kubernetes`, two
  correct, distinct rows) and `data_science_01`
  ("Python, pandas, and numpy" → `language.python` +
  `data.library.pandas` + `unresolved:numpy`, three correct, distinct
  rows).
- Workstream C: `EvidenceList.tsx` had zero `<a href>` anywhere (the
  pre-existing regression test explicitly pinned zero links); evidence
  type was labeled but never explained.
- Workstream D: `_unresolved_requirement_signal()`'s narrow lead-in
  check does not match "Experience with OpenCV for image processing"
  (remainder "OpenCV for image processing" fails `clean_list_fragment`'s
  shape check), so the claim produces zero rows and becomes an
  `UnparsedClaim` — correctly, per M9A/9C's existing, unmodified design.

**Scoring/matching invariants:** `gitscore.matching`, `gitscore.assessment`,
`gitscore.jobs.parsing`, and `gitscore.concepts.registry`'s `_CONCEPTS`/
`resolve_concept()` are byte-for-byte unchanged.
`scripts/evaluate_m9b_preservation.py`,
`scripts/evaluate_m9b_retrieval_sensitivity.py`, and
`scripts/evaluate_m9d_pilot_cohort.py` were all re-run after full
implementation; every report diffed byte-identical against the pre-9E
committed version.

**Risks / limitations:** The 23%-silent-drop disposition decision (M9C
§12, M9D §9/§10) remains unresolved — raised a third time, still open.
The `sindresorhus × devops_cloud_01` evidence-weighting calibration risk
(M9D §6.3) is unchanged — this milestone makes the evidence easier to
verify and more honestly labeled, not differently weighted. No
file/line-specific evidence link exists (would need a default-branch
fact not present in the current domain model). The M9D human pilot has
still not been run — now even more relevant, since the screens it
specifies as materials (Task 1/Task 4) render differently after this
milestone.

**How to test it:**
```
python -m pytest                                      # 934 passed (920 + 14 new)
cd frontend && npx vitest run                          # 36 passed (29 + 7 new)
cd frontend && npm run type-check                      # clean
cd frontend && npm run build                           # succeeds
python scripts/evaluate_m9b_preservation.py            # byte-identical
python scripts/evaluate_m9b_retrieval_sensitivity.py   # byte-identical
cd scripts && python evaluate_m9d_pilot_cohort.py      # byte-identical
```

**Files affected:** `src/gitscore/concepts/registry.py`
(`concept_display_label()`, new), `src/gitscore/concepts/__init__.py`
(re-export), `src/gitscore/api/schemas.py`
(`RequirementOut.concept_label`, `AssessmentOut.unparsed_claim_count`),
`src/gitscore/api/serialization.py` (`_concept_label()`, wiring);
`tests/test_technical_concepts.py` (+5),
`tests/test_api_serialization.py` (+9); `frontend/src/types/api.ts`,
`frontend/src/lib/labels.ts`, new `frontend/src/lib/github.ts`,
`frontend/src/components/AlignmentHeadline.tsx`,
`frontend/src/components/ResultView.tsx`,
`frontend/src/components/RequirementSection.tsx`,
`frontend/src/components/EvidenceList.tsx`,
`frontend/src/test/fixtures.ts`,
`frontend/src/components/__tests__/ResultView.test.tsx` (+12, 1
updated); `docs/ARCHITECTURE.md` (§30, new), `docs/PIPELINE.md`,
`docs/evaluation/MILESTONE_9E_ASSESSMENT_CLARITY.md` (new),
`docs/CHANGELOG_DEV.md` (this entry).
`JOB_DESCRIPTION_PARSER_VERSION`/`JOB_REQUIREMENT_SCHEMA_VERSION`/
`MATCHER_VERSION`/`SCORING_VERSION`/`CONCEPT_REGISTRY_VERSION`/
`EVIDENCE_SCHEMA_VERSION`/`REPOSITORY_RANKING_VERSION`/
`JOB_RELEVANCE_VERSION` all unchanged.

## 2026-10-24 — Milestone 9D: Product validation & trustworthiness pilot

**What changed:** Nothing in `src/gitscore/` or `frontend/` — this is a
validation-only milestone. Added one new, additive evaluation script
(`scripts/evaluate_m9d_pilot_cohort.py`, mirroring the M8E precedent of
adding a small harness when needed for a fair measurement) that runs the
real, unmodified `extract_candidate_evidence()` →
`parse_job_description_with_diagnostics()` → `match_job()` →
`assess_job()` composition against an 8-scenario pilot cohort (6 pairs
reused from the frozen `evaluation/gold/matrix.json`, 2 new pairs for
DevOps/platform and non-assessable-heavy scenarios), capturing full
per-requirement evidence detail and `unparsed_claims` diagnostics that
the existing `evaluate_end_to_end*.py` scripts do not report. Reviewed
the job description, GitHub evidence, API contract, and every frontend
component in the result-rendering path independently (never using
GitScore's own output as ground truth) and audited the end-to-end
product workflow (submission, loading/error/empty states, result
organization, evidence traceability) against the existing API/frontend
source and test suites.

**Why:** M9C's own §12 explicitly recommended this milestone's scope
("user-test the new UI copy... this milestone implemented the approved
design; it has not been validated against real user reactions") and
asked that M9D not start before it was explicitly scoped. This milestone
answers the product-level questions the prior, more code-focused
milestones (M7A-M9C) were not asked to answer: are GitScore's
evidence-grounded conclusions technically defensible against an
independent review, and does the product's interface communicate
alignment vs. hiring probability, and parser uncertainty, clearly enough
for a real user.

**Findings (see
`docs/evaluation/MILESTONE_9D_PRODUCT_VALIDATION.md` for full detail):**
1. **New:** the headline `uninterpreted_requirement_count` caveat
   excludes `unparsed_claims` entirely (confirmed in
   `api/schemas.py`/`api/serialization.py`) — a reader can see "1
   requirement could not be confidently interpreted" at the top while 2
   more claims that never became a row at all sit in a separate section
   further down, undercounting the real interpretive uncertainty.
2. **New:** on a real pairing (`sindresorhus × devops_cloud_01`), the
   existing, already-documented `WEAK`-evidence-sufficiency policy
   combined with a very large, topically-unrelated account (1,142
   repos) produces a 75% "GitHub Evidence Alignment" score built
   substantially from incidental README mentions and one unrelated
   tiny repository — a concrete, real-evidence demonstration of a risk
   this project's own architecture docs already flagged as theoretical.
3. **Re-confirmed on fresh pairs:** M9B's measured 23% requirement
   silent-drop rate continues to inflate/deflate `alignment_score` by
   shrinking the assessable denominator without a visible trace in the
   scored breakdown (e.g. `karpathy × computer_vision_01` reports a
   clean 100 on a pairing the frozen matrix itself pre-registered as
   only "partial," caused by the OpenCV requirement vanishing entirely).
4. Evidence citations are textually traceable but not clickable links
   to GitHub (`EvidenceList.tsx`); required/preferred items are not
   visually grouped within a status section. Both minor, confirmed in
   code.
5. **New:** identical requirement text renders multiple times — in one
   confirmed pattern, the exact same sentence appears under both
   "Supported" and "Not observed" simultaneously — because
   `RequirementSection.tsx` renders only `requirement.text`, never the
   `concept_id` the API already provides to distinguish rows born from
   the same raw sentence. Confirmed systemic: present in 4 of the 8
   pilot pairs (`evaluation/reports/m9d_pilot_cohort_report.json`).
6. A full human-review pilot protocol (5 tasks, questionnaire,
   observation sheet, pre-registered success criteria) was produced but
   not run — no participants were recruited or simulated.
7. A new offline, fixture-backed harness
   (`scripts/m9d_serve_offline_fixture.py`) served the real FastAPI app
   over an actual HTTP request this session (zero live GitHub calls) and
   confirmed the live API process matches its documented contract —
   browser-level click-through was attempted (Next.js dev server
   confirmed running) but could not complete: this session's Chrome
   browser-automation tool did not respond.

**Risks / limitations:** browser-rendered click-through was not
completed this session (see the main report §11) — the live backend/API
process itself was verified over a real request, which is a step beyond
pure source reading, but actual rendered appearance and information
density remain unverified. Small, fixed corpus (4 real accounts, 15
synthetic jobs, 8 pilot pairs); no ground-truth hiring-outcome label
exists or was invented anywhere in this milestone.

**How to test it:**
```
python -m pytest                                    # 920 passed (unchanged)
cd frontend && npm test                               # 29 passed (unchanged)
cd scripts && python evaluate_m9d_pilot_cohort.py
python scripts/m9d_serve_offline_fixture.py torvalds --port 8011   # live API, offline
```

**Files affected:** `scripts/evaluate_m9d_pilot_cohort.py` (new),
`scripts/m9d_serve_offline_fixture.py` (new),
`evaluation/reports/m9d_pilot_cohort_report.json` (new),
`docs/evaluation/MILESTONE_9D_PRODUCT_VALIDATION.md` (new),
`docs/evaluation/M9D_HUMAN_PILOT_PROTOCOL.md` (new),
`docs/CHANGELOG_DEV.md` (this entry). No file under `src/gitscore/` or
`frontend/` was modified. No frozen gold under `evaluation/gold/`,
`evaluation/gold_v1_1/`, or `evaluation/m9b/` was modified.
`JOB_DESCRIPTION_PARSER_VERSION`/`JOB_REQUIREMENT_SCHEMA_VERSION`/
`MATCHER_VERSION`/`SCORING_VERSION`/`CONCEPT_REGISTRY_VERSION` all
unchanged.

## 2026-10-24 — Milestone 9C: Assessment transparency & requirement coverage

**What changed:** Makes two pre-existing, Milestone-9B-measured
transparency gaps VISIBLE without touching the matcher, the scoring
formula, the concept registry, or `JobRequirementProfile`/
`JobRequirement`'s own schema. (1) A new `parse_job_description_with_diagnostics()`
sibling of the unchanged `parse_job_description()` reports every claim
segmentation judged requirement-shaped for which the parser's own
per-claim detector chain still produced ZERO `JobRequirement` rows (a
new `UnparsedClaim`, text + source span only) — this is strictly worse
than the Milestone 9A `unresolved_requirement` placeholder, which DOES
produce a real, inspectable row; Milestone 9B measured 6 of 26 (23%) of
an independent benchmark hitting this gap. (2) The API/frontend gained
a presentation-only `interpretation_status` ("recognized" /
"non_technical" / "unparsed_placeholder") distinguishing GitScore's OWN
parser uncertainty from a genuinely non-technical requirement within
the existing, unchanged `NOT_ASSESSABLE` status — both previously
rendered with the identical generic sentence.

**Why:** A recruiter reading "Not assessable from GitHub" for both
"Bachelor's degree" and a requirement GitScore's own parser simply
couldn't interpret was being told two different facts (one about the
job posting, one about GitScore's own reading of it) in identical
words. A requirement that silently vanished before even reaching the
domain model had, until now, no trace anywhere a user or developer
could inspect.

**Design process:** Four STOP-point decisions (diagnostics
representation, API field design, UI scope, silent-drop-gap scope) were
presented with options, migration implications, and test impact before
any implementation — all four recommended options approved. Full
write-up: `docs/evaluation/MILESTONE_9C_ASSESSMENT_TRANSPARENCY.md`.

**How the new logic works:** `jobs/parsing/parser.py`'s
`parse_job_description()` and the new `parse_job_description_with_diagnostics()`
now share one internal `_parse()` implementation — `parse_job_description()`
itself is byte-for-byte unchanged (confirmed against all 30 Milestone
9B corpus entries). `gitscore.api.serialization._interpretation_status()`
is the ONE place the recognized/non_technical/unparsed_placeholder rule
is computed, from fields the domain model already carries
(`RequirementMatch.status` + `JobRequirement.category`) — introduces no
new `MatchStatus`. The frontend's `not_assessable` section now renders
two distinctly-worded subsections from `interpretation_status`, a small
headline caveat count, and a fourth, clearly separate
`UnparsedClaimsSection` for `unparsed_claims` — omitted entirely when
empty (the normal case).

**Risks / limitations:** the underlying 23%-of-corpus silent-drop rate
is NOT reduced by this milestone (visibility only, by approved design)
— `unparsed_claims` reports it, nothing resolves it. A factual error
was found and corrected in `MILESTONE_9B_EVALUATION_INTEGRITY.md` during
this milestone's own regression testing (`m9b-005` was misreported as a
`FALLBACK_MATCH`; it is actually a `SILENT_DROP_GAP` — that report's
aggregate numbers were already correct, only its prose naming which six
entries was wrong). See `docs/evaluation/MILESTONE_9C_ASSESSMENT_TRANSPARENCY.md`
§11 for the full remaining-risks list.

**How to test it:**
```
python -m pytest                                              # 920 passed (904 + 16 new)
python scripts/evaluate_m9b_preservation.py                   # byte-identical to pre-9C
python scripts/evaluate_m9b_retrieval_sensitivity.py           # byte-identical to pre-9C
cd frontend && npm run type-check && npm test && npm run build
```

**Files affected:** `src/gitscore/jobs/parsing/parser.py`,
`src/gitscore/jobs/parsing/__init__.py`, `src/gitscore/jobs/__init__.py`,
`src/gitscore/application/job_fit.py`, `src/gitscore/api/{schemas,serialization}.py`,
`tests/test_job_parser_diagnostics.py` (new),
`tests/{test_api_serialization,test_application_job_fit}.py`,
`frontend/src/types/api.ts`, `frontend/src/lib/labels.ts`,
`frontend/src/components/{RequirementSection,AlignmentHeadline,ResultView}.tsx`,
`frontend/src/components/UnparsedClaimsSection.tsx` (new),
`frontend/src/test/fixtures.ts`,
`frontend/src/components/__tests__/ResultView.test.tsx`,
`docs/ARCHITECTURE.md` §29 (new), `docs/PIPELINE.md`,
`docs/evaluation/MILESTONE_9C_ASSESSMENT_TRANSPARENCY.md` (new),
`docs/evaluation/MILESTONE_9B_EVALUATION_INTEGRITY.md` (one factual
correction). No file under `src/gitscore/matching/`, `src/gitscore/assessment/`,
`src/gitscore/concepts/`, `src/gitscore/ranking/`, or any frozen
`evaluation/gold*/` directory was modified.
`JOB_DESCRIPTION_PARSER_VERSION`/`JOB_REQUIREMENT_SCHEMA_VERSION`/
`MATCHER_VERSION`/`SCORING_VERSION`/`CONCEPT_REGISTRY_VERSION` all
unchanged.

## 2026-10-24 — Milestone 9B: Evaluation integrity, requirement coverage & retrieval-sensitive testing

**What changed:** Evaluation-only milestone — no production code under
`src/gitscore/` was modified. Adds three new, additive evaluation
capabilities, none of which touch the frozen `evaluation/gold/`
(`8c:v1`) or `evaluation/gold_v1_1/` (`8c:v1.1`) corpora:

1. **Requirement-preservation benchmark** (`evaluation/m9b/corpus.json`,
   `corpus_version: "9b:v1"`, 30 independently-authored examples) +
   `scripts/evaluation_lib/preservation_eval.py` +
   `scripts/evaluate_m9b_preservation.py`, reporting ten DISTINCT
   metrics (never merged into one precision number) covering genuine
   preservation recall, technical structural correctness,
   unknown-concept preservation, OR/AND structural correctness,
   placeholder preservation, spurious-requirement count, fabrication
   count, source-span correctness, silent-drop count, and
   non-requirement-prose exclusion. Result: zero fabricated
   technologies and zero spurious rows across every entry, including
   four adversarial cases specifically built to try to break M9A's
   non-fabrication invariant (all held) — but 6 of 26 real requirement
   claims (23%) still silently drop, all sharing M9A's own already-
   disclosed residual limitation (a technical requirement naming no
   specific product and using no qualifying lead-in phrase, e.g.
   `"Experience designing distributed systems"`). This is the first
   milestone to *count* that gap rather than only name it.
2. **Retrieval-sensitive end-to-end evaluation**
   (`evaluation/m9b/retrieval/synthetic_{candidates,jobs}.json`,
   explicitly marked `"synthetic": true`) +
   `scripts/evaluation_lib/retrieval_sensitivity_eval.py` +
   `scripts/evaluate_m9b_retrieval_sensitivity.py`. M8E's own
   consolidated evaluation found 0 of 12 real-fixture matrix pairs
   change `alignment_score` under job-aware retrieval (M8D.2) — every
   real recovery happened to be redundant. Two synthetic candidate
   fixtures, engineered so a repository's recovery can supply evidence
   found nowhere else on the account, demonstrate for the first time
   that the full mechanism (retrieval success → new evidence → new
   requirement support → score change) genuinely fires when the right
   conditions hold: one case produces a real `67 → 100` alignment flip
   from a single newly-recovered repository; a second shows a
   genuinely relevant PREFERRED-weight repository still crowded out of
   the fixed `relevance_top_k=10` budget by REQUIRED-weight
   competitors (no score change, correctly); a third reproduces the
   realistic "recovered but redundant" case the real fixtures already
   showed. Re-ran (unchanged) `evaluate_repository_retrieval.py` /
   `evaluate_end_to_end_job_aware.py` fresh and cited those real-fixture
   numbers rather than duplicating them.
3. **Evaluation-integrity safeguard tooling**
   (`scripts/check_evaluation_staleness.py`) — generalizes the manual
   "recompute fresh, diff against the committed file, never overwrite
   it" process M8D.3/M8E/M9A each used ad hoc into one reusable,
   read-only script (pinned never to write to any committed report by
   `tests/test_m9b_evaluation_integrity.py`). Found the already-known,
   already-disclosed `evidence_report.json` staleness (unchanged) PLUS
   a genuinely new finding: the committed `end_to_end_report.json` is
   stale in **5 of 12 cells**, not the 1 cell M8E/M9A each previously
   confirmed — the other 4 are a previously-unmeasured, fully-explained
   consequence of M9A's own (already correctly shipped) parser fix
   making several SPI/I2C/UART/Vue/Angular-family requirements visible
   and assessable in jobs that previously silently dropped them
   entirely. Not a bug — flagged for M9C to either regenerate the file
   with a clear changelog note or add an automated staleness banner.

**Why:** The product promise — "identify observable GitHub evidence
supporting the candidate's alignment with specific requirements, while
clearly distinguishing missing evidence from missing skills" — depends
on two things this milestone measures directly for the first time:
whether M9A's requirement-preservation fix generalizes beyond its own
12 unit-test examples (it does, with zero fabrication but a measurable,
bounded residual gap), and whether job-aware retrieval (M8D.2) can ever
actually change a real alignment score, not just change which
repositories get analyzed (it can, under the right conditions — M8E's
own real-fixture matrix just never happened to contain those
conditions).

**Files affected:** `evaluation/m9b/` (new: `corpus.json`,
`retrieval/synthetic_candidates.json`, `retrieval/synthetic_jobs.json`),
`scripts/evaluation_lib/{preservation_eval,retrieval_sensitivity_eval}.py`
(new), `scripts/evaluate_m9b_{preservation,retrieval_sensitivity}.py`
(new), `scripts/check_evaluation_staleness.py` (new),
`tests/test_m9b_{preservation_eval,retrieval_sensitivity,evaluation_integrity}.py`
(new, 28 tests), `evaluation/reports/m9b_{preservation,retrieval_sensitivity}_report.{json,md}`
(new), `docs/evaluation/MILESTONE_9B_EVALUATION_INTEGRITY.md` (new).
No file under `src/`, `evaluation/gold/`, or `evaluation/gold_v1_1/`
was modified. `JOB_DESCRIPTION_PARSER_VERSION`,
`JOB_REQUIREMENT_SCHEMA_VERSION`, `MATCHER_VERSION`, `SCORING_VERSION`,
and `CONCEPT_REGISTRY_VERSION` are all unchanged.

**Risks / limitations:** see
`docs/evaluation/MILESTONE_9B_EVALUATION_INTEGRITY.md` §11 for the full
prioritized product-risk analysis; the two headline items are the
23%-of-corpus silent-drop residual gap (§4.1/§11 risk #1) and the newly
measured `end_to_end_report.json` staleness (§10.2/§11 risk #2), both
explicitly deferred to M9C rather than fixed here.

**How to test it:**
```
python -m pytest                                              # 904 passed (876 + 28 new)
python scripts/evaluate_m9b_preservation.py
python scripts/evaluate_m9b_retrieval_sensitivity.py
python scripts/check_evaluation_staleness.py
```

## 2026-10-19 — Milestone 9A: Lossless job requirement parsing

**What changed:** Fixes the M8E-identified high-severity bug (entire
requirement bullets — `"Knowledge of Vue or Angular"`, `"...SPI, I2C,
and UART"` — silently producing ZERO `JobRequirement` rows, not even an
`unresolved:<term>` placeholder). Root cause: `classify_alternative_claim`
discarded its own computed per-segment `unresolved:<term>` ids whenever
no segment was a *real* registered concept, and
`find_conservative_unknown_terms`'s comma-gated unknown-term policy
required an already-confirmed sibling concept to fire at all — so an
OR-list or comma-enumeration where *every* item was unregistered lost
the whole claim. Full root-cause trace, design options presented to and
approved by the user, and results:
`docs/evaluation/MILESTONE_9A_REQUIREMENT_PRESERVATION.md`.

**Fix — two additive pieces, no schema/matcher/scoring change:**
(1) `jobs/parsing/alternatives.py` and `jobs/parsing/concepts.py` now
ALSO mint `unresolved:<term>` concept id(s) for an OR-list or
enumeration-cue comma-list with zero real confirmed concepts, provided
every item is shaped like a specific named technology (new
`looks_like_specific_technology_name()` — capitalization/acronym shape,
never a vocabulary list) — matching what the pre-existing frozen gold
fixtures already expected for `Vue`/`Angular`/`SPI`/`I2C`/`UART`/
`MATLAB`/`Simulink`/`Snowflake`/`BigQuery`. (2) `jobs/parsing/parser.py`
gained a new last-resort `category="unresolved_requirement"` placeholder
(`concept_id=None` — never fabricates a technology) for anything (1)
still can't shape-confirm (e.g. `"control systems or state estimation"`,
`"Experience with dbt"`), fired only by one of three narrow structural
signals (an "or", an enumeration-cue comma list, or a short claim led
by an unambiguous technical lead-in phrase). `concept_id=None` forces
the existing, UNCHANGED matcher to `NOT_ASSESSABLE` regardless of
observability, so neither piece can ever be scored `SUPPORTED`.

**A false positive caught during implementation, not shipped:** the
first version of (1) let a segment's raw leading word rescue an
over-long OR-segment regardless of position — which promoted
`"Security certification such as OSCP or CISSP"` into a fabricated
`unresolved:security`, since `"Security"` is capitalized only because
it starts the sentence. Fixed by restricting that specific rescue path
to non-first OR-segments (a word right after "or"/a comma has no
sentence-initial-capitalization ambiguity); covered by a regression
test.

**How the new logic works:** see
`docs/evaluation/MILESTONE_9A_REQUIREMENT_PRESERVATION.md` §3 for the
full per-piece design and §3.1/§3.2 for the two subtlety fixes
(sentence-initial capitalization; slicing the comma-enumeration search
to start after the cue so the first listed item, e.g. "SPI", isn't lost
behind a long lead-in clause).

**Risks / limitations:** a technical requirement with no named
technology and no qualifying lead-in phrase (e.g. "Experience designing
distributed systems") is still silently dropped — fixing it would need
a much broader heuristic explicitly out of scope per the brief. The
frozen parser-evaluation gold corpora were deliberately NOT edited, so
the harness's precision metric drops (0.892->0.771 on `8c:v1`) purely
because gold never annotated sentences that previously produced zero
rows — every one of the 12 newly "spurious" rows was manually confirmed
to carry `concept_id=None`, never a fabricated technology. Recall
improved on both corpora (0.563->0.621 on `8c:v1`, 0.641->0.699 on
`8c:v1.1`).

**How to test it:** `python -m pytest tests/test_job_requirement_preservation.py -v`
(12 new gold examples) and `python -m pytest` (876 passed, full suite);
`python scripts/evaluate_job_parser.py` / `--corpus-version 8c:v1.1`
for the recall/precision numbers above.

**Files affected:** `src/gitscore/jobs/parsing/{concepts,alternatives,
observability,confidence,parser}.py`, `tests/test_job_parser.py` (one
pre-existing test updated — it pinned the old bug as a "known
limitation"), `tests/test_job_requirement_preservation.py` (new),
`evaluation/reports/parser_report*.{json,md}` (regenerated),
`docs/evaluation/MILESTONE_9A_REQUIREMENT_PRESERVATION.md` (new).
`JOB_DESCRIPTION_PARSER_VERSION` bumped `v3 -> v4`.
`JOB_REQUIREMENT_SCHEMA_VERSION` unchanged (`2`) — no new field, only
one new documented `category` string value.

## 2026-10-11 — Milestone 8D.3: Evidence attribution precision

**What changed:** Fixes the known `karpathy/llm.c` -> `language.cpp`
false positive already flagged (not fixed) in
`evaluation/gold_v1_1/candidates/karpathy.json`'s `not_expected_concepts`.
Root cause traced to actual evidence provenance, not assumed: `llm.c`'s
real README has a "## notable forks" section listing OTHER people's
separate, externally-linked ports (a C# port, a C++/CUDA port, a Go
port, ...) — "C++" appears there three times, textually real, but never
a claim that `llm.c` itself uses C++ (GitHub's own language stats put
C++ at ~3.5% of `llm.c`'s bytes, below `languages.py`'s 5% significance
floor). `extraction/readme.py`'s alias matcher had no notion of WHERE in
the document a match sat — a provenance/attribution gap, not a
matching-correctness bug. Confirmed NOT isolated to this one repo: the
identical pattern independently exists in `karpathy/llama2.c`'s own
"notable forks" section (a `llama2.ts` TypeScript port by a different
author) and in most of `sindresorhus`'s small-library READMEs (a
ubiquitous "## Related" section linking to the author's OTHER
packages). Full writeup: `docs/ARCHITECTURE.md` §27. Full evaluation
record: `docs/evaluation/MILESTONE_8D3_EVIDENCE_ATTRIBUTION.md`.

**Fix — a new, source-aware attribution layer, not a technology
blacklist:** new module `gitscore.evidence.extraction.readme_context`
adds two deterministic, bounded signals checked per alias occurrence
before it becomes Evidence: (1) a section-heading denylist (`"notable
forks"`, `"related"`, `"acknowledgements"`, `"references"`, ... —
normalized, markdown-emphasis-stripped headings; code-fence-aware so a
shell comment is never mistaken for a heading), and (2) a small,
curated, DIRECTIONAL set of negation/future-intent cues ("does not use
X", "X is on the roadmap") checked in a fixed 60-character window
immediately before/after the match. `readme.py`'s matching loop changed
from one `.search()` per alias to `.finditer()` over every occurrence,
skipping excluded ones — a concept's first occurrence being excluded no
longer discards the whole concept; a later genuine occurrence (or the
concept's next alias) is still tried. Same design spirit as Milestone
5D.1's `readme_unsafe_aliases` (a per-ALIAS denylist) on an orthogonal
axis (a per-CONTEXT denylist) — no per-technology special-casing,
generalizes to any concept.

**Precision/recall tradeoff — presented, not silently chosen:** a
whole-sentence cue scan was prototyped and REJECTED. Generic comparison
cues ("instead of", "rather than", "versus", "compared to") are
directionally ambiguous at sentence scope — "Built in Python instead of
C" affirms Python and negates C in the SAME sentence; a whole-sentence
scan keyed on "instead of" would wrongly suppress the genuine Python
mention too, with no principled way to tell which side of the sentence
the matched term is on without the sentence-structure parsing this
milestone's "no NLP" constraint forbids. Decision: restrict adjacency
cues to a small, bounded, DIRECTIONAL set (where the cue's position
relative to the match unambiguously determines what it negates) in a
fixed small window, and exclude the ambiguous comparison cues entirely
— a documented, intentional limitation (§27.5), not an oversight.

**Evaluation (`python scripts/evaluate_evidence.py --corpus-version
8c:v1.1`):** False positives `1 -> 0`. Concept checks unchanged, `10/10`
found both before and after — zero recall regression, confirmed by
direct inspection that every `expected_concepts` entry across all 4
gold candidates sources from `language_stats`/`dependency`, never
`readme`, so this extractor change could only ever affect false
positives in this benchmark. The original frozen `8c:v1` benchmark
(`evaluation/gold/`, `evaluation/reports/evidence_report.*`) is left
un-regenerated in committed form, per "keep the original 8C benchmark
and historical reports intact" — re-running it locally shows the same
drop (`2 -> 1`) plus one pre-existing, unrelated stale entry
(`sindresorhus/Gifski` -> `language.swift`, predating that concept's
registration).

**End-to-end consequence, verified not assumed
(`scripts/evaluate_end_to_end.py`, also left un-regenerated in
committed form):** re-running locally shows exactly one cell changes —
`karpathy` x `frontend_01` (an intentionally cross-domain "negative"
scenario) drops from alignment `80` to `60`, required `(4,4) -> (3,4)`.
Traced directly to `karpathy/llama2.c`'s own "notable forks" section
(the `llama2.ts` TypeScript-port mention) — the exact same mechanism as
the driving `llm.c` case, previously inflating this account's apparent
frontend-skill alignment on an explicitly negative-control pair. The
score moving further in the correct direction for a labeled-negative
scenario is the intended effect of fixing a false positive.

**Known limitations:** comparison cues are intentionally not exclusion
cues (§27.3/§27.5); the adjacency window is a fixed 60 characters, not a
real sentence boundary; the heading denylist is a bounded, curated set,
partly evidence-grounded and partly a documented, modest generalization
of the same README convention; a separate, out-of-scope false-positive
mechanism was observed (a project name like `llama.cpp` incidentally
satisfying the `"cpp"` alias via its `.`-separated suffix, unrelated to
attribution context) and left for a future milestone; heading detection
only recognizes ATX (`# heading`) markdown syntax, not Setext.

**Versions:** `EXTRACTOR_VERSION` (`extraction/readme.py`) `readme:v3`
-> `readme:v4`. `EVIDENCE_SCHEMA_VERSION`, `CONCEPT_REGISTRY_VERSION`,
`REPOSITORY_RANKING_VERSION`, `JOB_RELEVANCE_VERSION`,
`JOB_DESCRIPTION_PARSER_VERSION`, `JOB_REQUIREMENT_SCHEMA_VERSION`,
`MATCHER_VERSION`, `SCORING_VERSION` all unchanged — no concept added/
renamed/removed, no domain-model shape change, no matcher/assessment
change.

**Tests:** 864/864 backend (841 pre-existing + 23 new: 14 in
`tests/test_evidence_extraction_readme_context.py` (new), 9 added to
`tests/test_evidence_extraction_readme.py` — the `karpathy/llm.c`
regression, positive controls for genuine implementation/dependency
statements and a surviving-elsewhere mention, and negative controls for
comparison/external-reference/explicit-non-use/future-intent). Frontend/
API/contract untouched this milestone — no frontend re-verification run
(nothing shared-contract-relevant changed).

**Files changed:** `src/gitscore/evidence/extraction/readme_context.py`
(new), `src/gitscore/evidence/extraction/readme.py`,
`tests/test_evidence_extraction_readme_context.py` (new),
`tests/test_evidence_extraction_readme.py`,
`evaluation/reports/evidence_report_v1_1.{json,md}` (regenerated — the
only report files updated; `evidence_report.*` and
`end_to_end_report.*` deliberately left as committed),
`docs/ARCHITECTURE.md` (new §27), `docs/PIPELINE.md`,
`docs/evaluation/MILESTONE_8D3_EVIDENCE_ATTRIBUTION.md` (new),
`docs/CHANGELOG_DEV.md` (this entry).

**How to test:**
```
python -m pytest                                        # 864/864
python scripts/evaluate_evidence.py --corpus-version 8c:v1.1   # False positives: 0
```

## 2026-10-06 — Milestone 8D.2: Job-aware repository retrieval

**What changed:** Follows directly from Milestone 8C's evaluation
(Section 13) and Milestone 8D.1's own §25.7 named limitation: Milestone
5B's generic, job-independent repository ranking can exclude a
repository that is highly relevant to one SPECIFIC job posting, purely
because a prolific candidate has too many repositories competing for
too few analysis slots (e.g. `karpathy/nn-zero-to-hero`, 24.6k stars,
excluded from a 63-repo account's top-15; `sindresorhus/execa`, 7.6k
stars, excluded from a 1,142-repo account's top-15). Full writeup:
`docs/ARCHITECTURE.md` §26. Full evaluation record:
`docs/evaluation/MILESTONE_8D2_JOB_AWARE_RETRIEVAL.md`.

**Architecture — a second, independent retrieval signal:** new module
`gitscore.ranking.job_relevance` adds Stage-2 job-relevance retrieval,
deterministically UNIONED with Milestone 5B's frozen generic ranking
(`rank.py`/`config.py` completely untouched, not one weight retuned,
`REPOSITORY_RANKING_VERSION` stays `1`). Without job context, selection
is byte-for-byte the pre-8D.2 behavior (confirmed: all 796 pre-existing
tests pass unchanged). Union policy: generic top-N's own order is never
reordered; job-relevant additions (not already present) are appended
afterward in relevance order. Budget: `relevance_top_k=10` alongside
the existing `top_n=15` → `max_selected=25` total (their exact sum).

**Dependency direction (deliberate):** `gitscore.ranking.job_relevance`
depends ONLY on `gitscore.concepts` — zero dependency on `gitscore.jobs`.
The new `JobRelevanceTerm` (`concept_ids: tuple[str, ...]`, `weight:
float`) is a small, neutral retrieval-query representation, not the
full `JobRequirementProfile` domain model, so
`pipeline.evidence.extract_candidate_evidence()` (the candidate-only
entry point since Milestone 5D) never has to import `gitscore.jobs`.
The one bridging function, `_relevance_terms_from_job_profile()`, lives
in `gitscore.application.job_fit` — already documented as "the one
layer allowed to know about all of them together." Verified
non-circular: `gitscore.jobs` imports only `gitscore.concepts`
throughout its package.

**Relevance signal:** one `JobRelevanceTerm` per technical
`JobRequirement` (non-technical claims never produce one);
`alternative_concept_ids` reused as-is for OR-group ANY-matching;
weight REQUIRED=1.0/PREFERRED=0.5 (`Importance` deliberately unused). A
repository matches via (1) the structured `primary_language` field
resolving to the exact concept id (recovers even bare-unsafe-alias
concepts like `language.c`), (2) a `readme_safe_aliases()`-gated,
overlap-resolved text match against name/description/topics (reusing
8D.1's `select_longest_overlapping_matches` — "React Native" never
misattributes as plain "React"; bare "go"/"c" never match), or (3) a
bounded, exact, word-boundary-safe match for an `unresolved:<term>`
concept. Relevance is retrieval-only — never consulted by
`match_job()`/`assess_job()`.

**`CandidateEvidenceProfile` semantics:** no schema change (zero new
fields). Documented caveat instead: a job-aware call's returned profile
is a bounded, job-CONDITIONED snapshot that may differ from a
job-independent call for the same candidate, and must never be cached
as the universal profile. `EvidenceExtractionResult` (already outside
the domain model) gains one optional diagnostic field,
`repository_selection`, not serialized by the HTTP API.

**Offline evaluation:** new, additive harness
(`scripts/evaluate_repository_retrieval.py`,
`scripts/evaluation_lib/retrieval_eval.py`,
`evaluation/gold/retrieval_cases.json`, corpus `8d2:v1`) —
`scripts/evaluate_end_to_end.py` is untouched and its published report
is unchanged. 7 gold cases, classified by `classify_retrieval_outcome()`
into outcomes that keep relevance ground truth separate from the
observed result (see "Evaluation-integrity correction" below): of 4
genuinely relevant cases, 2 RECOVERED (`Jango1324/Pneumonia-Detection-Ai`
for `ml_engineering_01` and, via alternative-group ANY-matching,
`general_swe_01`) and 2 MISSED despite job-aware retrieval, measured not
assumed — `karpathy/nn-zero-to-hero` (ranks 38th of 39 relevant repos,
just outside the top-10 budget) and `sindresorhus/execa` (ranks 231st
of 992 — an extremely prolific, single-language-dominant account
defeats a fixed top-10 the same way it already defeated the generic
top-15); of 3 negative controls, all 3 correctly excluded, 0
false-positive additions.

**Evaluation-integrity correction (post-review, same milestone, before
commit):** an earlier pass of this evaluator scored each case against a
single `expect_recovered` field and had flipped `karpathy/nn-zero-to-hero`
and `sindresorhus/execa` from `true` to `false` after the algorithm
failed to recover them, reporting both as "correct" negative-control
exclusions. Rejected on review: relevance ground truth must never be
revised because the algorithm failed to recover a genuinely relevant
repository. Fixed by separating `genuinely_relevant` (ground truth,
never revised to match the algorithm's output) from `expected_analyzed`
(a regression pin on the current measured outcome) in
`evaluation/gold/retrieval_cases.json`, and adding
`classify_retrieval_outcome()` (`scripts/evaluation_lib/retrieval_eval.py`)
to turn that pair into five mutually exclusive outcomes
(`RETRIEVAL_RECOVERED`/`RETRIEVAL_ALREADY_COVERED`/`RETRIEVAL_MISSED_RELEVANT`/
`RETRIEVAL_CORRECTLY_EXCLUDED`/`RETRIEVAL_FALSE_POSITIVE_ADDITION`) that
keep a missed relevant repository structurally distinct from a correct
negative control. 8 new tests in `tests/test_evaluation_harness.py` pin
this classification (synthetic inputs) and assert, against the real
gold file, that both known-limitation cases keep `genuinely_relevant:
true` — a permanent regression guard against this exact conflation.
No production retrieval code changed (`gitscore.ranking.job_relevance`,
the 15+10=25 budget, and the matcher/assessment formula are all
unchanged) — purely an evaluation-harness and documentation fix; the
regression pin (`expected_analyzed` vs. measured outcome) holds 7/7,
confirming the implementation's actual behavior never changed, only how
it is classified and reported.

**Known limitations:** crowding on high-repo-count accounts where many
repositories share one weak signal (documented above, not fixed —
enlarging the budget to pass this evaluation's specific cases would be
tuning to the benchmark, not a principled fix). Relevance deliberately
skips Milestone 5B's fork/archived/trivial-size dampeners. The bare-C
job-description-prose fallback (8D.1) is intentionally not extended to
repo metadata. `scripts/evaluate_end_to_end.py` does not exercise
job-aware retrieval (by design — its candidate profiles stay
job-independent, reused across the matrix).

**Versions:** `JOB_RELEVANCE_VERSION = 1` (new, `ranking/job_relevance.py`).
`REPOSITORY_RANKING_VERSION`, `CONCEPT_REGISTRY_VERSION`,
`JOB_DESCRIPTION_PARSER_VERSION`, `JOB_REQUIREMENT_SCHEMA_VERSION`,
`EVIDENCE_SCHEMA_VERSION`, `MATCHER_VERSION`, `SCORING_VERSION` all
unchanged.

**Tests:** 841/841 backend (796 pre-existing + 45 new: 32 in
`tests/test_job_relevance.py`, 3 in `tests/test_pipeline_evidence.py`,
2 in `tests/test_application_job_fit.py`, 8 in
`tests/test_evaluation_harness.py` for the integrity correction below).
Frontend untouched and re-verified this milestone: 23/23 tests,
`tsc --noEmit` clean, `next build` succeeds (no frontend or API code
changed).

**Files changed:** `src/gitscore/ranking/job_relevance.py` (new),
`src/gitscore/ranking/__init__.py`, `src/gitscore/pipeline/evidence.py`,
`src/gitscore/evidence/profile.py` (docstring only), `src/gitscore/application/job_fit.py`,
`tests/test_job_relevance.py` (new), `tests/test_pipeline_evidence.py`,
`tests/test_application_job_fit.py`, `tests/test_evaluation_harness.py`,
`evaluation/gold/retrieval_cases.json`
(new), `scripts/evaluate_repository_retrieval.py` (new),
`scripts/evaluation_lib/retrieval_eval.py` (new),
`scripts/evaluation_lib/loaders.py`, `evaluation/reports/retrieval_report.{json,md}`
(new), `docs/ARCHITECTURE.md` (new §26), `docs/PIPELINE.md`,
`docs/evaluation/MILESTONE_8D2_JOB_AWARE_RETRIEVAL.md` (new),
`docs/CHANGELOG_DEV.md` (this entry).

**How to test:**
```
python -m pytest                                    # 841/841
python scripts/evaluate_repository_retrieval.py      # new 8D.2 harness
python scripts/evaluate_end_to_end.py                # unchanged, confirms byte-identical report
```

## 2026-10-06 — Milestone 8D.1: Registry expansion & parser-precision fixes

**What changed:** Follows directly from Milestone 8C's real-world
evaluation (`docs/evaluation/MILESTONE_8C_EVALUATION.md`), which
measured the pipeline as 8B left it and recommended, but did not
implement, a ranked list of fixes. 8D.1 implements the top items from
that list. Full as-built writeup: `docs/ARCHITECTURE.md` §25. Full
benchmark/correction record: `docs/evaluation/MILESTONE_8D1_PARSER_IMPROVEMENTS.md`.
This entry summarizes.

**Registry additions (`concepts/registry.py`, `CONCEPT_REGISTRY_VERSION`
3 → 4):** five new `TechnicalConcept`s — `infra.kubernetes`,
`language.sql` (generic/vendor-agnostic, distinct from
`database.postgresql`), `language.swift`, `language.kotlin`, and
`framework.react_native` (added specifically to fix the collision
below). Pure additive data, zero logic change; every extractor/parser
that calls `resolve_concept()`/`find_concept_mentions()` picks these up
automatically. None marked `readme_unsafe_aliases` — no observed
real-world false positive for any of them, the same evidence-based bar
`rust`/`java`/`ruby` were already held to.

**"Most-specific alias wins" (`concepts/matching.py`):** new
`select_longest_overlapping_matches()` — a generic, data-driven conflict
resolver (not a per-concept special case) fixing the real false
positive 8C's evaluation found: "React Native" satisfies both
`framework.react`'s bare "react" alias and `framework.react_native`'s
"react native" alias; the longer, more specific match now always wins.
Adopted by both free-form-text scanners: `jobs/parsing/concepts.py`'s
`find_concept_mentions()` and `evidence/extraction/readme.py`'s
`evidence_from_readme()` (`EXTRACTOR_VERSION` `readme:v2` → `readme:v3`).

**Bounded bare-short-alias fallback (the `torvalds`/embedded-C fix,
`jobs/parsing/concepts.py::find_bare_short_alias_mentions`):** 8C's
single highest-value finding — "Strong C experience in embedded,
resource-constrained environments" produced ZERO `JobRequirement` rows
at all (`language.c` has no safe alias; bare "c" is indistinguishable
from prose), scoring `torvalds` a flat 0 on an embedded-firmware
posting. New last-resort fallback, tried only when the normal scan
finds nothing, bounded on three axes at once: only concepts with no
`readme_safe_aliases()` (today: uniquely `language.c`), only a
single-character alias, case-sensitive exact-letter match AND a small
fixed skill-context vocabulary word required in the same claim. Kept
structurally separate from the comma-gated unknown-term promotion path
(`parser.py`'s `safe_mentions` vs. `mentions`) to avoid a caught side
effect: letting this fallback also unlock that path would have promoted
an unrelated comma-separated clause ("resource-constrained
environments") into a fabricated `unresolved:` concept.

**OR/alternative-group fixes (`alternatives.py`, `concepts.py`):** three
of 8C's four `WRONG_ALTERNATIVE_STRUCTURE` cases shared one root cause —
a `readme_unsafe` bare alias (`c`, `go`) next to a descriptive word the
fixed vocabulary didn't anticipate. `_TRAILING_FILLER` gained
"programming"; a new `leading_token()` escalation step resolves just the
first word when the whole-fragment shape check fails (never promotes a
new `unresolved:` id from it — too weak a signal); `_LIST_ITEM_PREFIXES`
gained skill-level descriptors (`expert-level`, `advanced`, `proficient
in`, `strong`, `solid`). `JOB_DESCRIPTION_PARSER_VERSION` `v2` → `v3`.

**Parser benchmark** (`scripts/evaluate_job_parser.py`, 103 expected
requirements, 15 jobs): same frozen `8c:v1` gold, before → after code:
CORRECT 54 → 58, WRONG_ALTERNATIVE_STRUCTURE 4 → 1 — the real,
gold-independent improvement. Precision measured against that same
frozen gold drops 1.000 → 0.892, but entirely because 7 of its rows'
premise ("X is not in the registry") is now stale, not from any new
parser false positive. Against the corrected `8c:v1.1` gold (see
below): CORRECT 66, MISSING 37, zero WRONG_ALTERNATIVE_STRUCTURE,
precision back to 1.0, recall 0.524 → 0.641.

**Evaluation corpus — `8c:v1` frozen, `8c:v1.1` added:**
`evaluation/gold/` is byte-for-byte unchanged (every 8C number stays
reproducible). `evaluation/gold_v1_1/` is a separate, parallel snapshot;
exactly 9 rows across 7 files differ in content (8 parser-gold rows
across 6 job files, all "concept X is now registered" corrections, plus
1 candidate evidence-gold row — `sindresorhus/Gifski`'s Swift
expectation, whose sole old premise was "Swift is not in the registry,"
now false). `scripts/evaluate_job_parser.py` and
`scripts/evaluate_evidence.py` both gained an optional
`--corpus-version 8c:v1.1` flag (default unchanged) writing to separate
`*_report_v1_1.{json,md}` files. Full row-by-row correction list and
rationale: `docs/evaluation/MILESTONE_8D1_PARSER_IMPROVEMENTS.md`.

**Evidence benchmark result:** regenerating `evidence_report.json/md`
against frozen `8c:v1` gold with 8D.1 code raised "False positives" 1 →
2, adding `sindresorhus/Gifski → language.swift` — audited and confirmed
stale (frozen gold's sole premise was registry absence). Against
corrected `8c:v1.1`: false positives back to 1 — only the genuine,
unrelated `karpathy/llm.c → language.cpp` README-over-attribution issue
remains, left uncorrected and visible by design (not this milestone's
scope, not a stale-gold artifact). Production extraction code
(`evidence/extraction/languages.py`) was NOT modified for this —
Swift evidence resolves automatically through the registry addition
alone.

**E2E consequences (`scripts/evaluate_end_to_end.py`, no E2E code
changed):** `torvalds` × `embedded_firmware_01` goes from
`alignment_score=0`/`required=None` to `alignment_score=50`/
`required=(1,1)` — 8C's single highest-value finding, resolved. `torvalds`
× `data_science_01` drops 25 → 20 (`required` `(1,3)` → `(1,4)`, one
more real, assessable, unmet `language.sql` requirement — intentional,
not a regression). `Jango1324` × `embedded_firmware_01` stays at 0 but
`required` goes `None` → `(0,1)` (now a real, explained unmet
requirement rather than "not assessable").

**Versions:** `CONCEPT_REGISTRY_VERSION` 3 → 4.
`JOB_DESCRIPTION_PARSER_VERSION` `v2` → `v3`. `readme.py`'s
`EXTRACTOR_VERSION` `v2` → `v3`. `JOB_REQUIREMENT_SCHEMA_VERSION`,
`EVIDENCE_SCHEMA_VERSION`, `MATCHER_VERSION`, `SCORING_VERSION` all
unchanged — `JobRequirement`/`Evidence`'s shape, the matcher, and the
assessment formula are untouched.

**Tests:** 796/796 backend (pytest), 23/23 frontend, `tsc --noEmit`
clean, `next build` clean. No production test behavior regressed —
test fixtures using Kubernetes/Swift/Kotlin/SQL purely as illustrative
"unresolved concept" examples were swapped for synthetic unknown terms,
since those four are now real registered concepts (not a weakening of
unresolved-concept test coverage — a like-for-like substitution).

**Files changed:** `src/gitscore/concepts/{registry,matching}.py`,
`src/gitscore/jobs/parsing/{concepts,alternatives,confidence,parser}.py`,
`src/gitscore/evidence/extraction/readme.py`,
`scripts/{evaluate_job_parser,evaluate_evidence}.py`,
`scripts/evaluation_lib/loaders.py`, `evaluation/gold_v1_1/` (new),
`evaluation/reports/{parser,evidence,end_to_end}_report*.{json,md}`
(regenerated; `*_v1_1` variants new), `tests/test_{job_parser,
job_parser_extraction,matching_engine,matching_manual_examples,
technical_concepts,assessment_engine,evaluation_harness,
api_serialization}.py`, `docs/ARCHITECTURE.md` (new §25),
`docs/PIPELINE.md`, `docs/evaluation/MILESTONE_8D1_PARSER_IMPROVEMENTS.md`
(new), `docs/CHANGELOG_DEV.md` (this entry).

**How to test:**
```
python -m pytest                                              # 796/796
python scripts/evaluate_job_parser.py                         # 8c:v1 (frozen)
python scripts/evaluate_job_parser.py --corpus-version 8c:v1.1
python scripts/evaluate_evidence.py --corpus-version 8c:v1.1
cd frontend && npm run test && npx tsc --noEmit && npm run build
```

**Known limitations:** the generic registry-gap backlog beyond these
five concepts (Terraform, Jenkins, dbt, Snowflake/BigQuery, Flutter,
MATLAB/Simulink, PLC, OpenCV, scikit-learn, GraphQL, OAuth, CMake,
Azure/GCP, generic phrases) — intentionally batched for a future
registry-expansion milestone, not fixed piecemeal. The
`karpathy/llm.c` README-over-attribution false positive — unrelated,
still present, still deferred. Kubernetes YAML/Helm/`Chart.yaml`
evidence scanning — explicitly out of scope. Top-N repository-retrieval
behavior, matcher semantics, the assessment formula, the API contract,
and the frontend are all unchanged. No commit was made.

## 2026-10-04 — Milestone 8B: Minimal product frontend

**What changed:** First usable browser experience for GitScore. New,
fully separate application `frontend/` (Next.js + TypeScript) consuming
the Milestone 8A `/api/v1/analyze` contract — a user enters a GitHub
username and pastes a job description, and sees GitHub Evidence
Alignment, required/preferred support, repository coverage, and the
supported/not-observed/not-assessable requirement groups with evidence
provenance. No GitScore analysis logic is reproduced in TypeScript; the
frontend is a renderer/client only. Full as-built writeup:
`docs/ARCHITECTURE.md` §24. This entry summarizes.

**Framework decision:** no frontend existed before this milestone.
Selected Next.js + TypeScript (App Router) per the milestone's stated
default. One plain global stylesheet, no Tailwind/component-library
dependency. Pinned `typescript@^5.9.3` (latest stable 5.x) rather than
the newly-released TypeScript 7 major — a deliberate "boring" choice,
not an oversight. Testing: Vitest + React Testing Library + jsdom
(lighter than Jest + `next/jest` for a project this size).

**Location:** `frontend/` is fully separate from `src/gitscore/` — its
own `package.json`/`node_modules`/build. The two applications
communicate only over the frozen HTTP contract;
`frontend/src/types/api.ts` is a hand-written mirror of
`gitscore.api.schemas`, never generated from the Python dataclasses.

**API client:** `lib/api.ts::analyzeJob()` throws `ApiError`
(status/code/message/retryable from the API's own error envelope) or
`NetworkError` (fetch itself failed — offline/DNS/CORS/backend down).
Base URL via `NEXT_PUBLIC_GITSCORE_API_URL`, defaulting to
`http://localhost:8000` in code — never a hardcoded production URL.

**Component structure:** `AnalyzePage` (state: idle/loading/success/
error, one `useState` per concern, no Redux/Zustand) composes
`AnalyzeForm` → `LoadingNotice`/`ErrorBanner`/`ResultView`.
`ResultView` composes, in the required order: `AlignmentHeadline` →
`SubscoreRow` (required/preferred, immediately beneath the headline,
never in an accordion) → `RepositoryCoverage` → `RequirementSection`
×3 (supported/not_observed/not_assessable) → `DiagnosticsPanel` (last,
collapsed).

**Null/zero rendering (carried through from 7B/8A):**
`alignment === null` → "Not available" + explanation, never 0/NaN/-1.
`required`/`preferred === null` → "No {required|preferred}
requirements were assessable", never "0 of 0 supported".
`RepositoryCoverage` never computes a percentage — "N of M repositories
deeply analyzed" plus a prioritization note when incomplete, or "All N
discovered repositories were deeply analyzed" when complete.

**Requirement-section wording** (the one place it lives:
`lib/labels.ts::requirementSectionCopy()`): "Supported by GitHub
evidence" / "Not observed in analyzed GitHub evidence" (+ "This does
not mean the candidate lacks the skill.") / "Not assessable from
GitHub" (+ "GitHub evidence cannot reliably establish these
requirements."). An empty group renders "None." rather than
disappearing. Pinned by a forbidden-word sweep: "failed"/"missing
skill"/"unqualified"/"hire"/"reject"/"weakness" never appear in a
rendered result.

**Evidence provenance:** grouped by repository, friendly
`evidence_type` labels (cosmetic lookup table, unrecognized values fall
back to themselves), confidence capitalized, `file_path`/`detail`
shown — only fields `EvidenceItem` actually carries. No fabricated
repository/file URL, source line, star count, or commit activity.

**Error handling:** API/network errors render the API's own safe
message via `ErrorBanner` — never a stack trace, exception name, or
backend path. "Try again" shown only when `retryable` is true.

**Accessibility/responsive:** real `<label htmlFor>` on every input,
`aria-invalid`/`aria-describedby` on validation errors, `role="status"
aria-live="polite"` loading notice, `role="alert"` error banner,
visible `:focus-visible`, semantic headings. One `max-width: 600px`
breakpoint stacks the two-column form row and the required/preferred
cards — desktop is the primary MVP target.

**Diagnostics:** last section, collapsed `<details>` by default. A
non-zero `extraction_failure_count` surfaces one modest, neutrally
styled sentence outside the `<details>` — never implying the whole
analysis failed.

**Tests:** 23 — `ResultView.test.tsx` (13, pure rendering against
hand-built fixtures: null/zero distinctions, neutral wording, evidence
provenance, diagnostics ordering, forbidden-word sweep, no fabricated
links) and `AnalyzePage.test.tsx` (10, integration through the real
form/API client with `fetch` mocked: rendering, validation, loading/
disabled-submit, success render, every error-mapping case, retry).
`npm run type-check` (`tsc --noEmit`) is the type-check/lint gate — no
separate ESLint config added (dependency-minimization choice).
**Backend: 777 tests, unchanged. Frontend: 23/23 passing. Production
build (`next build`) succeeds.**

**Local integration smoke test:** ran the real backend (`uvicorn`) and
frontend (`next dev`) together and issued one real
`POST /api/v1/analyze` for `Jango1324` WITH an `Origin:
http://localhost:3000` header, reproducing exactly what the browser's
CORS preflight + fetch would send — confirmed
`access-control-allow-origin: http://localhost:3000` on both the
preflight `OPTIONS` and the real `POST`, and a normal 200 response
(`alignment=67`, `required={2,3}`, 2 supported / 1 not_observed /
0 not_assessable). The session's interactive browser-automation tool
did not respond after repeated attempts, so visually clicking through
the rendered page (loading spinner, rendered DOM, empty console) was
NOT completed this session — flagged as a known limitation; the
scripted check above does verify the real CORS/HTTP behavior a browser
depends on, just not the rendering itself.

**Backend/API changes:** none. Milestone 8A's contract was consumed
exactly as frozen.

**Files changed:**
- `frontend/` — new application (`package.json`, `tsconfig.json`,
  `next.config.ts`, `vitest.config.ts`, `.env.local.example`,
  `.gitignore`, `src/app/*`, `src/components/*`, `src/lib/*`,
  `src/types/*`, `src/test/*`).
- `docs/ARCHITECTURE.md` — new §24.
- `docs/PIPELINE.md` — new "Frontend" section.
- `docs/CHANGELOG_DEV.md` — this entry.

**How to test:**
```
cd frontend && npm install && npm run test       # 23 tests, offline
cd frontend && npm run type-check && npm run build
cd .. && python -m pytest                        # 777 tests, unchanged
```
Local dev: terminal 1 `uvicorn gitscore.api.app:app --reload`; terminal
2 `cd frontend && npm run dev`; browse `http://localhost:3000`.

**Known limitations:** the actual browser click-through (loading
spinner, rendered result, empty console) was not performed this
session — the browser-automation tool was unresponsive; a human (or a
future session) should still do this once. No ESLint config. No result
persistence, accounts, job-URL ingestion, LLM, or alternative-role
discovery — all explicitly out of scope. No commit was made.

## 2026-10-03 — Milestone 8A: Thin backend API

**What changed:** First HTTP transport exposing
`gitscore.application.analyze_job_fit()`. New package `gitscore.api`
(`app.py`, `routes.py`, `schemas.py`, `serialization.py`, `errors.py`):
`POST /api/v1/analyze` and `GET /api/v1/health`. Contains no business
logic — the endpoint validates the request shape, calls
`analyze_job_fit()` exactly once, and serializes its result. Full
as-built writeup: `docs/ARCHITECTURE.md` §23. This entry summarizes.

**Framework decision:** no HTTP framework existed in the repo before
this milestone (nothing web-related in `pyproject.toml` or `.venv`).
Selected FastAPI + Pydantic + uvicorn per the milestone's own stated
default — typed contracts, generated OpenAPI, offline `TestClient`
testing, future React/Next.js integration. A brand-new package with
nothing existing to conflict with; no major architectural change
required.

**Package boundary:** `gitscore.api` depends on `gitscore.application`;
nothing in `gitscore.application` or any domain package imports from
`gitscore.api` — dependency direction stays one-way.

**Endpoint behavior:** `routes.py::analyze()` calls `analyze_job_fit()`
exactly once and hands its result straight to
`serialize_job_analysis_result()`. No `parse_job_description`/
`match_job`/`assess_job`/`extract_candidate_evidence` name is bound
anywhere in `routes.py` — pinned by a test that checks the module's
actual bound names, not a text grep. `health()` performs no GitHub or
database call.

**Request contract — `AnalyzeRequest`:** `github_username` (required,
1-39 chars — GitHub's own account-name limit) and `job_description`
(required, 1-20,000 chars), both rejected if blank/whitespace-only
after stripping; `job_title`/`job_company` (optional, <=200 chars,
blank coerced to `None`). `top_n`, a custom `GitHubClient`, and every
other internal `analyze_job_fit()` knob are deliberately NOT exposed.

**Response contract — `AnalyzeResponse`:** a hand-selected shape
(`analysis`, `assessment`, `required`, `preferred`,
`repository_analysis`, `requirements` with `supported`/`not_observed`/
`not_assessable`, `diagnostics`, `versions`) — never a raw
`dataclasses.asdict(JobAnalysisResult)` dump. `alignment_score`/
`required`/`preferred` serialize `None` as JSON `null`, never `0`/
`"N/A"`/`-1`/a fabricated `{"supported": 0, "assessable": 0}`.
`not_assessable` requirements are always present in the response, never
omitted for not affecting the score. Every `status` value is one of
`MatchStatus`'s own neutral strings — never "failed"/"missing_skill"/
"unqualified"/"gap".

**Evidence serialization:** only fields `Evidence` actually stores —
`concept_id`, `evidence_type`, `confidence` (lower-cased enum name,
never a raw int), `repository` (`owner`/`name`), `file_path`, and
`detail` (`raw_observation`, already extractor-bounded, never a full
README/manifest dump). No fabricated repository URL (`Evidence`/
`RepositoryIdentity` have no `source_url` field by design) and no
`location` (no extractor has ever populated it).

**Error mapping — one structured envelope
(`{"error": {"code", "message", "retryable"}}`) for every non-2xx
response:**

| Exception | HTTP | code |
|---|---|---|
| Blank/oversized input / stray `ValueError` | 422 | `invalid_request` |
| `GitHubNotFoundError` | 404 | `github_user_not_found` |
| `GitHubRateLimitError` | 503 (+`Retry-After`) | `github_rate_limited` |
| `GitHubRequestError`, status 401/403 | 500 | `github_auth_configuration_error` |
| `GitHubRequestError`, status in `RETRYABLE_STATUS_CODES` | 502 | `github_upstream_error` |
| `GitHubRequestError`, status `None` (connection/timeout) | 503 | `github_unavailable` |
| `GitHubRequestError`, other status | 502 | `github_upstream_error` |
| Anything else | 500 | `internal_error` |

Rate limiting is modeled as 503, not 429: the caller never talks to
GitHub directly, so it's GitScore's own server-side credential that's
exhausted, not the caller's quota. A 401/403 on GitScore's own outbound
GitHub request is a server configuration problem (bad/missing
`GITHUB_TOKEN`), not a caller error — 500. No new exception subclasses
were added to `gitscore.github.exceptions` for HTTP convenience; this
package branches on `GitHubRequestError.status_code`, the one signal it
already carries. Nothing is ever leaked to the caller — no stack trace,
no exception text, no token, no filesystem path; the unexpected-failure
handler logs the full exception server-side and returns only the
generic `internal_error` envelope.

**Synchronous/blocking strategy:** `analyze_job_fit()` is synchronous
(`GitHubClient` is a plain blocking `requests.Session` user). Both
endpoints are plain `def`, not `async def` — FastAPI's own documented
mechanism: a sync path-operation function runs in a worker thread pool
automatically, so a blocking `analyze_job_fit()` call never blocks the
event loop. Nothing under `gitscore.application`/`gitscore.github` was
rewritten to be async.

**Dependency injection:** `routes.py::get_github_client()` returns
`None` in production (so `analyze_job_fit()` constructs its own real
`GitHubClient()`); tests override it via
`app.dependency_overrides[get_github_client]` to inject the existing
`FakeEvidenceGitHubClient` test double — every API test is offline.

**CORS:** explicit local dev origins (`http://localhost:3000`,
`http://127.0.0.1:3000`), `allow_credentials=False` — never `"*"`
combined with credentials.

**No persistence:** request → analysis → response; `JobAnalysisResult`/
`AnalyzeResponse` are never written to the database.

**Versioning:** API is path-versioned (`/api/v1/...`). No analytical
version constant bumped or duplicated; no separate `API_SCHEMA_VERSION`
introduced — the path prefix is the versioning signal for this
milestone.

**Dependency hygiene:** added `fastapi`/`uvicorn[standard]` under a new
`[project.optional-dependencies] api` extra; added `httpx` under the
existing `dev` extra (only needed for `TestClient`). No lock file
exists to hand-edit; no unrelated dependency upgraded.

**Tests:** 31 new — `tests/test_api_serialization.py` (10: pure
domain -> API conversion on hand-built `JobAnalysisResult`s, no HTTP —
exact happy-path values, `None`/null for alignment/required/preferred,
neutral status values, NOT_ASSESSABLE presence, OR-group concept ids,
evidence shape incl. no fabricated repository URL, diagnostics counts,
version pass-through, ordinal-enum-as-lowercase-name serialization) and
`tests/test_api_routes.py` (21: health; valid analyze with full shape;
optional title/company; null alignment/required/preferred; NOT_OBSERVED/
NOT_ASSESSABLE presence; OR-group preservation; evidence/diagnostics
preservation; blank/oversized username/JD rejection; GitHub not-found/
rate-limit/auth/network/upstream-5xx -> HTTP mapping incl. `Retry-After`;
sanitized unexpected-failure response with no leakage; `analyze_job_fit`
called exactly once; `routes.py` binds no domain-stage-function name;
deterministic serialization). All offline via `FakeEvidenceGitHubClient`
and FastAPI's `TestClient` — no network, no GitHub token. **777 tests
total, all passing** (up from 746).

**Real-account validation:** ran the server locally
(`uvicorn gitscore.api.app:app`) and made one real
`POST /api/v1/analyze` for `Jango1324` against the same ML Engineer
posting used in 7C's smoke test, with a real `GITHUB_TOKEN`. HTTP 200;
`alignment_score=50`, `required={2,3}`, `preferred={0,1}`,
`repository_analysis={discovered:20, analyzed:15, complete:false}`,
2 supported / 2 not_observed / 2 not_assessable requirements, zero
extraction failures — identical to 7C's direct-pipeline result, as
expected for pure transport. Not treated as scientific validation.

**Files changed:**
- `src/gitscore/api/__init__.py`, `app.py`, `routes.py`, `schemas.py`,
  `serialization.py`, `errors.py` — new package.
- `tests/test_api_routes.py`, `tests/test_api_serialization.py` — new.
- `pyproject.toml` — new `api` extra (`fastapi`, `uvicorn[standard]`);
  `httpx` added to `dev`.
- `docs/ARCHITECTURE.md` — new §23.
- `docs/PIPELINE.md` — new "HTTP API" section.
- `docs/CHANGELOG_DEV.md` — this entry.

**How to test:** `python -m pytest` (whole suite, 777 tests, no
network/token required) or `python -m pytest tests/test_api_routes.py
tests/test_api_serialization.py -v` for just the 8A-relevant subset.
Run the server locally (requires the `api` extra installed and
`GITHUB_TOKEN` in `.env` for real requests):
`uvicorn gitscore.api.app:app --reload`.

**Explicitly NOT done this milestone (per instruction):** repository
ranking, evidence extraction, job parsing, matching, and assessment/
scoring logic were not touched or duplicated — only exposed. No
frontend, no accounts/auth/OAuth, no persistence, no job-URL ingestion,
no LLM, no alternative-role discovery. No commit was made.

## 2026-10-03 — Milestone 7C: End-to-end job-analysis orchestration

**What changed:** First application-level operation that composes the
whole GitScore job-fit pipeline into one call. New package
`gitscore.application` (`job_fit.py`):
`analyze_job_fit(username, job_description, *, client=None, top_n=DEFAULT_TOP_N,
job_title=None, job_company=None) -> JobAnalysisResult`. No new analysis
logic, no new scoring semantics, no new domain schema — it calls
`extract_candidate_evidence()` (5D), `parse_job_description()` (6B),
`match_job()` (7A), and `assess_job()` (7B) each exactly once and
returns their outputs bundled together. Full as-built writeup:
`docs/ARCHITECTURE.md` §22. This entry summarizes.

**Architectural review first:** Milestone 5D's
`gitscore.pipeline.evidence.extract_candidate_evidence()` already
composed repository listing -> ranking -> bounded deep extraction ->
`CandidateEvidenceProfile` end-to-end. This milestone found it already
complete and REUSED it unchanged — no ranking/extraction logic was
duplicated into `gitscore.application`, and no existing schema
(`CandidateEvidenceProfile`, `JobRequirementProfile`,
`JobMatchAnalysis`, `JobAssessment`) needed a change to compose. No
architectural stop condition was hit; nothing in this milestone's §18
"stop before changing established schemas" list applied.

**Package boundary:** `gitscore.application` depends on
`gitscore.pipeline`, `gitscore.jobs`, `gitscore.matching`, and
`gitscore.assessment`; none of those import from `gitscore.application`
— this is the one layer allowed to know about all of them together.

**Output model — `JobAnalysisResult`:** `candidate_profile`,
`job_profile`, `assessment`, `extractor_failures`,
`unknown_dependency_names`. No separate `match_analysis` field —
reachable unchanged via `assessment.match_analysis`. `candidate_profile`/
`job_profile` ARE kept as their own fields because neither is fully
reachable from the match/assessment objects (`JobMatchAnalysis` retains
only `coverage` and `title`/`company`, not the full evidence/concept
summaries or the full requirements tuple/raw text) — see
`docs/ARCHITECTURE.md` §22.3.

**Dependency injection:** `client` is forwarded UNCHANGED to
`extract_candidate_evidence()`, which itself only constructs a real
`GitHubClient()` when `client is None`. `job_fit.py` never constructs a
network client itself, so tests inject the existing
`FakeEvidenceGitHubClient` test double and never touch the network.

**Execution order:** job parsing runs BEFORE GitHub retrieval — local,
deterministic, free, so a blank/rejected job description fails before
any GitHub request is made rather than after spending part of the
candidate's rate-limit budget on a request that was always going to be
discarded. Each of the four stages runs exactly once — no rematching to
build a convenience field (pinned by
`test_each_stage_runs_exactly_once`).

**Failure semantics — reused, not reinvented:** blank `username` raises
`ValueError` directly (nothing downstream validates it); blank
`job_description` raises `ValueError` via `JobRequirementProfile`'s own
existing invariant. Every GitHub-side exception
(`GitHubNotFoundError`/`GitHubRateLimitError`/`GitHubRequestError`) and
every partial per-repository extraction failure propagates or is
surfaced completely unchanged — no `except Exception` anywhere in
`job_fit.py`. Zero repositories, zero candidate evidence, a job
description parsing to zero requirements, and zero assessable
requirements are each a NORMAL successful result (the existing
components already degrade gracefully through empty collections,
verified directly rather than assumed) — never collapsed with a true
I/O failure. Confirmed the `alignment_score is None` ("nothing was
assessable") vs. `alignment_score == 0` ("assessed, nothing supported")
distinction survives orchestration in both directions.

**Determinism boundary:** `extract_candidate_evidence()` is the only
stage with GitHub I/O; `parse_job_description()`/`match_job()`/
`assess_job()` are pure. Pinned by
`test_identical_fake_github_responses_produce_identical_results`: two
independent calls with byte-identical fake GitHub responses and
identical job text produce `==`-equal results.

**Smoke path:** `scripts/analyze_job.py <username> <job_description_file>
[--top N]` — prints alignment score, required/preferred "X of Y
supported", repository coverage, and the supported/not-observed/
not-assessable groupings by original job-posting text. Inspection only,
no persistence.

**Real-account validation:** ran `scripts/analyze_job.py Jango1324
<ML posting>` against the project's own existing test account (used
previously for 5D's `inspect_evidence_profile.py` validation) with a
real `GITHUB_TOKEN`. 20 repositories discovered, 15 analyzed, zero
extractor failures, `alignment_score = 50` (`required = 2 of 3`,
`preferred = 0 of 1`). Not treated as scientific validation of the
score, per instruction.

**Versioning:** no schema/formula version introduced or bumped.
`JOB_REQUIREMENT_SCHEMA_VERSION`, `EVIDENCE_SCHEMA_VERSION`,
`CONCEPT_REGISTRY_VERSION`, `JOB_DESCRIPTION_PARSER_VERSION`,
`MATCHER_VERSION`, `SCORING_VERSION` are all read, never written, by
`gitscore.application` — pure composition.

**Tests:** 18 new, `tests/test_application_job_fit.py`, all offline via
`FakeEvidenceGitHubClient` (no network, no GitHub token): happy path;
orchestrated result equals direct `extract_candidate_evidence()` ->
`parse_job_description()` -> `match_job()` -> `assess_job()`
composition (score, required/preferred, and full `JobAssessment`
equality); supporting evidence and repository coverage survive
orchestration; OR-group and `NOT_ASSESSABLE` semantics survive
orchestration; blank username/job description; GitHub not-found/
rate-limit/request-error propagation; zero repositories; zero matching
evidence; zero-requirement job description; zero-assessable-requirement
job description; partial per-repository extraction failure is
surfaced, not fatal; determinism across identical fake responses; each
stage called exactly once. **746 tests total, all passing** (up from
728).

**Files changed:**
- `src/gitscore/application/__init__.py`, `job_fit.py` — new package.
- `scripts/analyze_job.py` — new smoke-path CLI.
- `tests/test_application_job_fit.py` — new.
- `docs/ARCHITECTURE.md` — new §22.
- `docs/PIPELINE.md` — new "Job-fit pipeline" and "End-to-end
  orchestration" sections.
- `docs/CHANGELOG_DEV.md` — this entry.

**How to test:** `python -m pytest` (whole suite, 746 tests, no
network/token required) or `python -m pytest
tests/test_application_job_fit.py -v` for just the 7C-relevant subset.
Real-account smoke path (requires `GITHUB_TOKEN` in `.env`):
`python scripts/analyze_job.py <username> <path-to-job-description.txt> --top 15`.

**Explicitly NOT done this milestone (per instruction):** repository
ranking, evidence extraction, job parsing, matching, and
assessment/scoring logic were not redesigned — only composed.
Alternative-role discovery, web API, frontend, LLM logic, persistence
of results, and a commit were all explicitly out of scope and not
done.

## 2026-10-01 — Milestone 7B: GitHub Evidence Alignment & structured assessment

**What changed:** First milestone to turn Milestone 7A's per-requirement
`SUPPORTED`/`NOT_OBSERVED`/`NOT_ASSESSABLE` verdicts into a single
human-facing number. New package `gitscore.assessment` (`types.py`,
`models.py`, `engine.py`): `assess_job(match_analysis) -> JobAssessment`
consumes an already-computed `JobMatchAnalysis` and derives "GitHub
Evidence Alignment" plus required/preferred submetrics and explanation
groupings — no rematching, no GitHub/network/LLM calls. Design approved
in `docs/design/MILESTONE_7B_SCORING_DESIGN.md` before any code was
written; full as-built writeup: `docs/ARCHITECTURE.md` §21. This entry
summarizes.

**GitHub Evidence Alignment — definition:** "Among the job requirements
GitHub evidence can meaningfully speak to, what percentage are supported
by evidence found in the candidate's analyzed GitHub material."

```
assessable_count = supported_count + not_observed_count
alignment_score  = None                                       if assessable_count == 0
alignment_score  = round_half_up(100 * supported_count / assessable_count)  otherwise
```

`NOT_ASSESSABLE` is excluded from the denominator entirely — the one
load-bearing rule this milestone exists to enforce, implemented in
exactly one place (`assessment/models.py`'s `_assessable_matches()`,
reused by every derived property) so there is no second, drifting
definition of "assessable."

**Rounding — half-up, not Python's `round()`:** Python's builtin
`round()` uses round-half-to-even (`round(62.5) == 62`,
`round(63.5) == 64`) — a parity-dependent flip with no product
justification for a human-facing percentage. `assessment/models.py`'s
`_round_half_up_percentage()` rounds ties up via pure integer arithmetic
(`(2*numerator*100 + denominator) // (2*denominator)`, the exact-integer
form of `floor(n/d + 0.5)`) — no floats anywhere in the computation.
Pinned by dedicated tests (62.5 -> 63, 72.5 -> 73).

**Required/Preferred — submetrics, never weights:** `Necessity` does not
weight `alignment_score`. `JobAssessment.required`/`.preferred` each
expose a `SubscoreFacts(supported, assessable)` — a plain "X of Y" count,
deliberately not a second percentage. `SubscoreFacts` rejects
`assessable < 1` by construction (a necessity tier with zero assessable
requirements is `None` on `JobAssessment`, never `SubscoreFacts(0, 0)` —
those are different facts). **No cap, no floor, no gate**: a candidate
with 0-of-2 REQUIRED supported and 6-of-6 PREFERRED supported gets
`alignment_score == 75`, uncapped — pinned exactly by
`test_adversarial_case_strong_headline_despite_zero_required_support`.
The "strong headline hides zero required coverage" problem is resolved
by making `required` a mandatory co-display fact for any future
presentation layer, never by silently discounting the number.

**Importance — read, never weighted:** remains available unchanged on
`RequirementMatch.requirement.importance`, never duplicated onto
`JobAssessment` or folded into the score. Rejected explicitly: `jobs/
parsing/importance.py`'s `infer_importance()` already defaults a
PREFERRED requirement to LOW unless an emphasis phrase overrides it —
`Importance` is a heuristic partially *derived from* `Necessity`, not an
independent axis, so weighting by both would compound one parser
heuristic's uncertainty twice.

**ParserConfidence — metadata only:** affects neither `alignment_score`
nor coverage. The only aggregate computed from it is
`JobAssessment.low_parser_confidence_count` — assessable requirements
only (`SUPPORTED`/`NOT_OBSERVED`) with `parser_confidence ==
ParserConfidence.LOW`; a `NOT_ASSESSABLE` requirement parsed with LOW
confidence does not count, and `parser_confidence is None` ("not
evaluated by any parser") is never counted as LOW.

**Evidence confidence — unchanged from 7A:** does not reopen
`matching/support.py`'s `MINIMUM_SUPPORTING_CONFIDENCE =
ConfidenceLevel.WEAK` policy. A `SUPPORTED` match counts as exactly one
supported assessable requirement regardless of WEAK/MODERATE/STRONG
evidence strength.

**Repository coverage — passed through unmodified:**
`JobAssessment.match_analysis.coverage` is 7A's own
`RepositoryAnalysisCoverage`, not duplicated, not turned into a
percentage (Milestone 5B's ranker prioritizes the highest-substantiveness
repositories first, so a raw ratio would understate true coverage and
claim false precision). **No `coverage_note` presentation string either**
— a correction made during the Milestone 7B.0 design review: rendering
coverage prose from the structured facts is a future UI/API layer's job,
not domain state.

**Explanation groupings:** `supported_matches()`/`not_observed_matches()`/
`not_assessable_matches()` delegate directly to
`JobMatchAnalysis.matches_with_status()` — no `RequirementMatch`/
`Evidence` copied or rebuilt, posting order preserved exactly. Locked
wording (documented, not stored as strings in the domain model):
"Supported by GitHub evidence" / "Not observed in analyzed GitHub
evidence" (never "lacks the skill") / "Not assessable from GitHub"
(never "failed it"). "Gaps" is deliberately not used anywhere.

**Versioning:** `SCORING_VERSION = "github_evidence_alignment:v1"`
(`assessment/types.py`) — new, independent. Does NOT bump
`JOB_REQUIREMENT_SCHEMA_VERSION`, `EVIDENCE_SCHEMA_VERSION`,
`CONCEPT_REGISTRY_VERSION`, `JOB_DESCRIPTION_PARSER_VERSION`, or
`MATCHER_VERSION` — purely additive; `JobMatchAnalysis` is consumed
exactly as Milestone 7A produces it. No `EXPLANATION_VERSION` introduced
(the explanation groupings ARE this package's scoring logic, not a
separate prose step yet).

**Tests:** 42 new — `tests/test_assessment_engine.py` (33: formula
correctness, `NOT_ASSESSABLE` denominator exclusion, `None`/0/100 scores,
half-up rounding vs. Python's `round()`, required/preferred
`SubscoreFacts` including the pinned adversarial 75-with-0-of-2-required
case, Necessity/Importance/ParserConfidence/evidence-confidence/coverage
independence from the score, `low_parser_confidence_count` scoping,
OR-group single-counting, unresolved-concept handling, grouping-helper
order/identity, purity of `assess_job()`, `SubscoreFacts`/`JobAssessment`
invariants, and a check that no prose/presentation field exists anywhere
on the domain object) and `tests/test_assessment_manual_examples.py` (9:
the same four real Backend/Robotics/ML/Data-Engineer postings from 7A's
manual validation, run through the REAL `parse_job_description()` and
`match_job()`, then `assess_job()`, confirming no rematching, no
weighting, no coverage percentage, and no hire/reject verdict anywhere
in the result). All deterministic, offline, no network calls. **728
tests total, all passing** (up from 686).

**Manual end-to-end validation:** ran all four real postings
(Backend/Robotics/ML/Data Engineer) through the full
parse -> match -> assess pipeline. Confirmed: the Backend posting splits
"3+ years of experience building Python backend services" into a
technical `language.python` requirement plus a non-technical
`NOT_ASSESSABLE` experience claim (6A's own splitting rule) — assessable
set of 5 (python/postgresql/docker/aws/next.js), 2 supported
(python/docker) -> `alignment_score == 40`, `required ==
SubscoreFacts(2, 3)`, `preferred == SubscoreFacts(0, 2)`. The ML
posting's "Docker or Kubernetes" OR group counts as exactly one
assessable requirement, supported via Docker alone. Repository coverage
facts (`discovered_count`/`analyzed_count`/`is_complete`) pass through
unmodified with no synthesized percentage anywhere.

**Files changed:**
- `src/gitscore/assessment/__init__.py`, `types.py`, `models.py`,
  `engine.py` — new package.
- `tests/test_assessment_engine.py`, `tests/test_assessment_manual_examples.py`
  — new.
- `docs/ARCHITECTURE.md` — new §21.
- `docs/design/MILESTONE_7B_SCORING_DESIGN.md` — new, the approved
  design report.
- `docs/CHANGELOG_DEV.md` — this entry.

**How to test:** `python -m pytest` (whole suite, 728 tests, no
network/token required) or `python -m pytest tests/test_assessment_engine.py
tests/test_assessment_manual_examples.py -v` for just the 7B-relevant
subset.

**Explicitly NOT done this milestone (per instruction):**
alternative-role discovery, role archetype ranking, CatBoost/learned
scoring, recruiter labels, hire/reject recommendations, persistence, API,
UI, LLM-generated explanation prose, job-posting URL ingestion. No
existing 7A matching semantics were changed. No commit was made.

## 2026-09-29 — Milestone 7A: Deterministic requirement matching engine

**What changed:** First milestone connecting `CandidateEvidenceProfile`
(Milestone 5C/5D) and `JobRequirementProfile` (Milestone 6A/6B/6B.1). New
package `gitscore.matching` (`types.py`, `support.py`, `models.py`,
`engine.py`) determines, per `JobRequirement`, what the candidate's
GitHub evidence says about it — `SUPPORTED` / `NOT_OBSERVED` /
`NOT_ASSESSABLE`. Full design writeup: `docs/ARCHITECTURE.md` §20. This
entry summarizes.

**Explicitly NOT implemented (per instruction):** overall 0-100 job-fit
score, weighted aggregation, strengths/gaps prose, hire/reject
conclusion, alternative-role discovery, persistence, API, UI, CatBoost,
LLM, job-posting URL ingestion. `JobMatchAnalysis` exposes only plain
descriptive counts (`supported_count`/`not_observed_count`/
`not_assessable_count`) — arithmetic a human could reproduce by hand,
not a weighting decision.

**MatchStatus — three states:** `SUPPORTED`, `NOT_OBSERVED`,
`NOT_ASSESSABLE`. `NOT_OBSERVED` means "no sufficient evidence found in
the ANALYZED GitHub evidence" — never "the candidate lacks this skill."
`NOT_ASSESSABLE` means "not the kind of claim GitHub evidence can speak
to" — never "the candidate failed this requirement."

**No `PARTIALLY_SUPPORTED`:** considered and rejected, not omitted.
`ConfidenceLevel` (WEAK/MODERATE/STRONG) answers "how sure are we this
observation is real," never candidate proficiency or "how much of a
requirement" is met — no principled, deterministic partial-support
reading exists in the current evidence model. For an alternative group,
"some but not all alternatives supported" is not partial support either
— Milestone 6B.1's OR semantics mean ANY one supported alternative
already fully satisfies the requirement (`matched_concept_ids` records
which ones, but `status` stays a plain `SUPPORTED`).

**Normal technical requirement:** looked up directly via
`CandidateEvidenceProfile.concept(concept_id)` — no fuzzy string
matching; the parser/registry already normalized every concept id on
both sides, including `unresolved:<term>` ids (matched by exact string
equality).

**Alternative group (`alternative_concept_ids`, 6B.1):** `SUPPORTED` if
ANY alternative has sufficient evidence (true OR — never requires all).
`matched_concept_ids` retains EVERY alternative that matched (not just
the first), stored sorted for determinism. Verified against the actual
ML manual-validation posting: a candidate with ONLY Docker evidence (no
Kubernetes evidence) against "Docker or Kubernetes" is `SUPPORTED` with
`matched_concept_ids == ("infra.docker",)` — never requires both.

**Non-observable requirements:** `github_observability ==
NOT_OBSERVABLE` -> always `NOT_ASSESSABLE`, regardless of any concept
mapping (defensive; the parser never actually attaches one, but the
domain model doesn't forbid it).

**`PARTIALLY_OBSERVABLE` — the one non-obvious rule, checked against
real fixtures, not assumed:** a `PARTIALLY_OBSERVABLE` requirement WITH
a real concept mapping (`concept_id` or `alternative_concept_ids`) is
matched exactly like `STRONGLY_OBSERVABLE`. Milestone 6A's own
hand-built manual examples already contain this combination — "AWS
experience preferred" (`concept_id="cloud.aws"`, `PARTIALLY_OBSERVABLE`)
and "Comfortable working in Linux environments"
(`concept_id="unresolved:linux"`, `PARTIALLY_OBSERVABLE`) — so
collapsing every `PARTIALLY_OBSERVABLE` requirement to `NOT_ASSESSABLE`
regardless of concept mapping would make real, checkable evidence
(a `boto3` dependency, a Dockerfile) permanently unmatchable, which is
LESS truthful, not the "smallest safe behavior." A `PARTIALLY_OBSERVABLE`
requirement with NO concept mapping (`category="leadership"` — "Experience
mentoring junior engineers" in the actual ML posting — or the 6B.1
"unsafe" alternative-group fallback) IS `NOT_ASSESSABLE`: there is no
structured evidence surface to check at all, so `NOT_ASSESSABLE` is
truthful there, not a discount on `SUPPORTED`/`NOT_OBSERVED`.

**Evidence-sufficiency policy (`matching/support.py`):**
`MINIMUM_SUPPORTING_CONFIDENCE = ConfidenceLevel.WEAK` — ANY qualifying
Evidence, any confidence tier, is sufficient. A considered decision, not
an assumption: every extractor already applies its OWN significance
filter before producing Evidence at all (`languages.py`'s 5%-of-bytes
floor is the clearest example) — WEAK evidence is "genuinely present,
just not the dominant signal," not "maybe not real." A stricter floor
would silently re-apply a second, undocumented significance bar on top
of each extractor's own, and — with no `PARTIALLY_SUPPORTED` status —
would misrepresent "observed, but weakly" as "not observed at all."
Centralized as one named, testable constant so it can be tightened later
without redesigning the matcher.

**Coverage handling:** `JobMatchAnalysis.coverage` holds the candidate's
`RepositoryAnalysisCoverage`, copied by reference in ONE place (not
duplicated onto every `RequirementMatch` — that would be pure
duplication with no new information per match, mirroring how
`CandidateEvidenceProfile` itself keeps coverage once, not per
`Evidence`). No coverage percentage or score computed — only the
existing `discovered_count`/`analyzed_count`/`is_complete` facts,
unchanged; deriving a calibrated number from them is Milestone 7B's job.

**Necessity/Importance/ParserConfidence independence:** none of the
three affect matching status — `RequirementMatch.requirement` retains
them unchanged for 7B to read later, but REQUIRED vs. PREFERRED, HIGH
vs. LOW importance, and LOW vs. HIGH parser confidence with identical
candidate evidence always produce the identical `status`. Verified by
dedicated tests.

**Whole-profile entry point:** `match_job(candidate_profile, job_profile)
-> JobMatchAnalysis`, one `RequirementMatch` per requirement, in
`job_profile.requirements`' own order (never re-sorted — that order is
meaningful posting order).

**Versioning:** `MATCHER_VERSION = "requirement_matcher:v1"`
(`matching/types.py`) — a new, independent constant. Does NOT bump
`JOB_REQUIREMENT_SCHEMA_VERSION`, `EVIDENCE_SCHEMA_VERSION`,
`CONCEPT_REGISTRY_VERSION`, or `JOB_DESCRIPTION_PARSER_VERSION` — purely
additive; `JobRequirement` and `CandidateEvidenceProfile` are consumed
exactly as-is, unmodified.

**Tests:** 48 new — `tests/test_matching_engine.py` (42: normal/
alternative-group matching A-U from the milestone brief, invariants on
`RequirementMatch`/`JobMatchAnalysis`, threshold/coverage/ordering
behavior) and `tests/test_matching_manual_examples.py` (6: the real
Backend/Robotics/ML/Data-Engineer postings, parsed with the real
`parse_job_description()`, matched against several deliberately mixed
hand-built candidate profiles). All deterministic, offline, no network
calls. **686 tests total, all passing** (up from 638).

**Manual validation:** see `docs/ARCHITECTURE.md` §20.6 for the full
write-up — no false AND for OR groups, non-observable claims never
became technical gaps, every `SUPPORTED` match traced to real
attributable Evidence, and no score/coverage-percentage/hire-reject
conclusion was computed anywhere.

**Files changed:**
- `src/gitscore/matching/__init__.py`, `types.py`, `support.py`,
  `models.py`, `engine.py` — new package.
- `tests/test_matching_engine.py`, `tests/test_matching_manual_examples.py`
  — new.
- `docs/ARCHITECTURE.md` — new §20.
- `docs/CHANGELOG_DEV.md` — this entry.

**How to test:** `python -m pytest` (whole suite, 686 tests, no
network/token required) or `python -m pytest tests/test_matching_engine.py
tests/test_matching_manual_examples.py -v` for just the 7A-relevant
subset.

**Explicitly NOT done this milestone (per instruction):** job-fit score,
weighted aggregation, strengths/gaps, alternative-role discovery, LLM,
URL ingestion, persistence, UI, CatBoost, Milestone 7B. No commit was
made.

## 2026-09-28 — Milestone 6B.1: Structured alternative requirements

**What changed:** Corrects Milestone 6B's OR-handling before that
milestone was committed. 6B's OR-handling stop condition was presented
as an explicit A/B choice; it was implemented as Option A (a text-only,
non-technical placeholder) following a selection misunderstanding — the
intended choice was **Option B: a minimal additive schema extension**.
This milestone implements Option B: `JobRequirement` gained
`alternative_concept_ids: tuple[str, ...] = ()`, and the parser now
represents "Python or Go" as ONE requirement with structured semantics
(`supported(Python) OR supported(Go)`) instead of a placeholder the
matcher would have had to re-parse `original_text` to interpret. Full
design writeup: `docs/ARCHITECTURE.md` §19 (new); §18.7/§18.8/§18.10/
§18.11 updated in place to describe the corrected, final behavior. This
entry summarizes.

**Schema extension chosen:** `JobRequirement.alternative_concept_ids:
tuple[str, ...] = ()` (`jobs/models.py`) — the exact shape the 6B report
had already flagged as the smallest additive option, confirmed on
inspection to remain the cleanest design (no cleaner alternative was
found; a `RequirementGroup` wrapper object was considered and rejected
as unnecessary structural weight for what one additive tuple field
already expresses). Mutually exclusive with `concept_id` (never both
populated); requires >= 2 entries (a one-element "alternative" is
meaningless — use `concept_id`); rejects duplicates; each entry
validated with the SAME `concepts.registry.is_valid_concept_id()` 6A.1
introduced (no second, duplicated concept-id validation rule). The
stored tuple is SORTED at construction (`__post_init__`), not kept in
whatever order the caller passed — "Python or Go" and "Go or Python" are
the same logical requirement, so canonicalizing the order makes the two
phrasings compare/hash equal automatically, which is what lets
`dedup.py` and `JobRequirementProfile`'s existing exact-duplicate
rejection (Milestone 6A) treat them as identical for free, with no
set-vs-tuple special-casing anywhere.

**How "Python or Go" is represented:** ONE `JobRequirement`,
`concept_id=None`, `alternative_concept_ids=("language.go",
"language.python")`, necessity/importance/observability/confidence
computed for the GROUP as a whole from the full claim text (never
per-alternative) — never two independent `REQUIRED` rows.

**How "Python and PostgreSQL" is represented:** unchanged from 6B — two
independent `JobRequirement` rows, `concept_id="language.python"` and
`concept_id="database.postgresql"`, both `REQUIRED`. Conjunction and
alternation remain explicitly different representations; nothing about
AND-list handling changed in this milestone.

**Mixed/unknown alternatives:** `alternatives.py`'s `classify_alternative_claim()`
resolves each OR-segment in two steps — `find_concept_mentions()`
(prose-safe aliases, same as everywhere else) first, then, only if that
finds nothing, a narrower escalation: clean the segment to its core term
and try `resolve_concept()` against the FULL alias set. This escalation
is deliberate and bounded — a segment produced by splitting a CONFIRMED
"X or Y" enumeration (at least one sibling already resolved) is closer
to an isolated, structured token than to arbitrary free prose, which is
exactly the context Milestone 5D.1's alias-safety restriction was never
meant to constrain. It's what lets `"Go"` in `"Python or Go"` resolve to
the real `language.go` (bare `"go"` is `readme_unsafe` for prose
scanning; this isn't prose scanning) instead of an needless
`unresolved:go`. A segment resolving neither way falls to the SAME
conservative shape/stopword check `find_conservative_unknown_terms`
already uses (Milestone 6B) — passes -> `unresolved:<term>` (e.g.
`"AWS or Azure"` -> `("cloud.aws", "unresolved:azure")`); fails -> the
whole claim is marked `"unsafe"` and falls back to the OLD 6B
placeholder rather than dropping an option or inventing a reckless id
(e.g. `"Python or a genuinely amazing attitude"`).

**Non-technical "or" is no longer swept into a fake technical bucket:**
an OR-list with NO confirmed registered concept anywhere in it (e.g.
"Bachelor's degree in Computer Science or related field", "3+ years
experience or equivalent education") is now classified `"not_technical"`
and runs through the exact same pipeline as any other claim — these two
examples now correctly land in `education`/`experience` categories
(confirmed in the re-run manual validation, `docs/ARCHITECTURE.md`
§18.11), instead of 6B's blanket "any 'or' is alternative-shaped" rule.
No role-specific logic and no giant special-phrase list were added — one
general rule (does the OR-list contain a confirmed technical concept
anywhere?), applied uniformly.

**Necessity/importance/observability for a group:** computed once from
the full claim text, exactly as for any other claim — an alternative
group is ONE logical requirement. "Python or Go required" ->
`REQUIRED`. "CUDA or ROCm preferred" -> `PREFERRED`. Observability
reuses the existing `STRONGLY_OBSERVABLE` technical default unmodified
— every id in a group is either a real registered concept or a
conservatively-promoted `unresolved:<term>`, the same two shapes a
normal technical requirement can have.

**Deduplication:** a REAL BUG was found and fixed while implementing
this. `is_technical` is `True` for both a normal technical requirement
and an alternative group, but `concept_id` is `None` for the group case
— the OLD dedup key (`("technical", concept_id, necessity)`) would have
collapsed EVERY alternative group sharing a necessity into ONE, losing
distinct groups like "Python or Go" and "AWS or Azure" entirely. Fixed
by adding a dedicated key, checked first:
`("technical_alternative", alternative_concept_ids, necessity)`. Because
`alternative_concept_ids` is stored sorted, "Python or Go" and "Go or
Python" collapse to one (same logical requirement, correctly); "Python
or Go" and "AWS or Azure" do not (different requirements, correctly).
Caught by this milestone's own new tests, not by inspection alone.

**Provenance:** unchanged in mechanism — the group's `original_text`/
`source_span` is still the FULL original claim, exact and unmodified
(Milestone 6A's `SourceSpan`). No fake reconstructed per-alternative
spans are created; there is no representation for "where inside the
claim did alternative #2 appear" — the group's span covers the whole
claim, matching how a compound AND-claim's multiple requirements already
share one span (Milestone 6B).

**Versioning:**
- `JOB_REQUIREMENT_SCHEMA_VERSION` 1 -> 2 — `JobRequirement` gained a
  field, a genuine shape change per `jobs/types.py`'s own bump policy.
- `JOB_DESCRIPTION_PARSER_VERSION` `"job_description_parser:v1"` ->
  `"...v2"` — the parser's emitted semantics for OR-claims changed
  materially, mirroring the `readme:v1` -> `readme:v2` precedent
  (Milestone 5D.1: a behavior change bumps the extractor/parser's OWN
  version, independent of the domain-model schema version).
- `CONCEPT_REGISTRY_VERSION`, `EVIDENCE_SCHEMA_VERSION`,
  `REPOSITORY_RANKING_VERSION`, `SCORING_RUBRIC_VERSION`,
  `DATASET_VERSION` untouched.

**Tests:** 41 new/changed — `tests/test_job_requirement_models.py` (17
new: the three valid states, canonicalized ordering, mixed resolved/
unresolved, mutual-exclusivity and every other invariant, reuse of the
6A.1 concept-id validator), `tests/test_job_requirement_profile.py` (1
new: reordered-alternatives-are-an-exact-duplicate; 1 changed: the
`JOB_REQUIREMENT_SCHEMA_VERSION` pin), `tests/test_job_parser_extraction.py`
(19 new for `classify_alternative_claim()`, 4 new for the dedup fix),
`tests/test_job_parser.py` (4 tests rewritten from Option-A to Option-B
expectations, 2 manual-validation fixtures updated for the corrected
non-technical-"or" boundary). All deterministic, offline, no network
calls. **638 tests total, all passing** (up from 597; every V1/5B/5C/
5D/5D.1/6A/6A.1 test, and every 6B test not describing Option-A-specific
behavior, untouched and still green).

**Manual validation re-run:** all four Milestone 6B fixtures (Backend,
Robotics, ML, Data Engineer) re-run against the corrected parser.
Confirmed improvements: "Bachelor's degree ... or a related field"
(Robotics) and "3+ years of experience ... or a related field" (Data
Engineer) now correctly categorize as `education`/`experience` instead
of the generic `alternative_requirement` bucket; "Docker or Kubernetes"
and "AWS or Azure" (ML) now carry real `alternative_concept_ids` instead
of an opaque placeholder. New accepted limitation: "Snowflake or
BigQuery" (Data Engineer, neither alternative is a registered concept)
and "control systems or robotics" (Robotics, same reason) now produce
nothing at all — the OR-list analog of the existing "needs a confirmed
anchor" rule for comma-lists, applied consistently rather than carved
out as a special case.

**Files changed:**
- `src/gitscore/jobs/models.py` — `alternative_concept_ids` field,
  updated invariants, `is_alternative_group`/`has_unresolved_alternative`
  properties, `is_technical` extended.
- `src/gitscore/jobs/types.py` — `JOB_REQUIREMENT_SCHEMA_VERSION` 1 -> 2.
- `src/gitscore/jobs/parsing/concepts.py` — `clean_list_fragment()`/
  `GENERIC_LIST_STOPWORDS` promoted to public, shared with
  `alternatives.py` (no duplicated shape-check logic).
- `src/gitscore/jobs/parsing/alternatives.py` — rewritten:
  `classify_alternative_claim()` (three-outcome classification) replaces
  the old blanket marker-only detection; `contains_alternative_marker()`
  kept (still used internally).
- `src/gitscore/jobs/parsing/dedup.py` — alternative-group dedup key
  (the bug fix above).
- `src/gitscore/jobs/parsing/parser.py` — orchestrates the three
  `classify_alternative_claim()` outcomes; `JOB_DESCRIPTION_PARSER_VERSION`
  v1 -> v2.
- `tests/test_job_requirement_models.py`, `test_job_requirement_profile.py`,
  `test_job_parser_extraction.py`, `test_job_parser.py` — see Tests above.
- `docs/ARCHITECTURE.md` — new §19; §17.2/§18.1/§18.7/§18.8/§18.10/
  §18.11 updated in place to describe the corrected design.
- `docs/CHANGELOG_DEV.md` — Milestone 6B's entry amended (Option A no
  longer described as the approved final design) plus this entry.

**How to test:** `pytest` (whole suite, 638 tests, no network/token
required) or `pytest tests/test_job_requirement_models.py
tests/test_job_requirement_profile.py tests/test_job_parser_extraction.py
tests/test_job_parser.py -v` for just the 6B/6B.1-relevant subset.

**Explicitly NOT done this milestone (per instruction):** matcher,
match score, evidence coverage, strengths/gaps, alternative-role
discovery, LLM, URL ingestion, persistence, UI, CatBoost, Milestone 7.
No commit was made.

## 2026-09-28 — Milestone 6B: Job-description parser

**What changed:** A new subpackage, `src/gitscore/jobs/parsing/`,
implementing `parse_job_description(description, *, title=None,
company=None) -> JobRequirementProfile` — the first automatic parser
turning raw job-description text into Milestone 6A's EXACT, unchanged
domain model. No matcher, no scoring, no candidate/job comparison, no
URL ingestion, no external LLM/API, no persistence. Full design
writeup: `docs/ARCHITECTURE.md` §18 (new). This entry summarizes.

**Why:** 6A/6A.1 defined the job-side domain model in isolation
(mirroring how 5C defined the candidate-side model before 5D wired real
extraction into it); this milestone is the first to actually populate it
from real text.

**Architecture decision (Part 1's evaluation, required before writing
any code):** deterministic, rule-based (Option A), not LLM-assisted.
Arbitrary-role support does not require language understanding of what
a role IS — it requires an open concept vocabulary (already solved:
`concepts.registry` + `unresolved:<term>`) plus conservative, generic
heuristics for document structure and claim shape, none of it
role-specific. No external AI dependency was introduced without
approval. See §18.1 for the full A/B/C evaluation and the documented
boundary where a future LLM claim-extraction adapter could plug in
without changing anything downstream.

**IMPORTANT STOP CONDITION presented before implementing that piece:**
`JobRequirement.concept_id` is a single scalar — it cannot represent
"this ONE requirement is satisfied by ANY of {Python, Go}" without a
schema change. Presented as an explicit A/B choice (Option A: no schema
change, one conservative non-technical fallback claim; Option B:
additive `alternative_concept_ids` field). This milestone initially
implemented Option A following a selection misunderstanding — the
user's intended choice was Option B. **Corrected in Milestone 6B.1
(below, same day, before this milestone was committed):** an
alternative/OR-shaped claim ("Python or Go", "AWS or Azure") is
represented with structured `alternative_concept_ids`, not a text-only
placeholder. See the Milestone 6B.1 entry for the final design; this
entry is left otherwise unchanged as the historical record of what was
originally built.

**Pipeline (new modules under `jobs/parsing/`):**

| Module | Role |
|---|---|
| `segmentation.py` | Part 3: raw text -> `Claim` (exact text + offsets + section-derived necessity hint), via a generic JD section-heading table (Requirements/Preferred/Responsibilities/skip-sections) + bullet/sentence splitting |
| `concepts.py` | Parts 5/6: known-concept mentions via the EXISTING registry; conservative `unresolved:<term>` promotion (comma-list-co-occurrence gated) |
| `alternatives.py` | Part 14: OR-shaped claim detection (the correctness gate above) |
| `experience.py` | Part 15: numeric years-of-experience qualifier detection |
| `non_technical.py` | Part 10: curated, generic (never role-specific) non-technical phrase table — education/legal/leadership/soft-skill |
| `necessity.py` | Part 7: local wording overrides section hint; REQUIRED wins on conflict |
| `importance.py` | Part 8: MEDIUM default, small HIGH/LOW keyword overrides, no floats |
| `observability.py` | Part 9: two centralized dict lookups (technical category -> always STRONGLY_OBSERVABLE today; non-technical category -> table), never scattered `if concept ==` |
| `confidence.py` | Part 12: one small mapping by extraction "kind" |
| `dedup.py` | Part 13: technical dedup key `(concept_id, necessity)`; non-technical key adds normalized text so different experience claims never merge |
| `parser.py` | orchestrates all of the above; `JOB_DESCRIPTION_PARSER_VERSION = "job_description_parser:v1"` |

**Alias safety (Part 6) reuses, does not fork, Milestone 5D.1's
mechanism:** job-description prose is treated as the SAME free-form-text
risk class README prose is, so `find_concept_mentions()` scans
`concept.readme_safe_aliases()` — the identical per-concept safe-alias
set `readme.py` uses. The shared boundary-regex primitive itself was
extracted from `evidence/extraction/readme.py` into a new
`concepts/matching.py::alias_pattern()` (pure refactor, confirmed
zero behavior change: `test_evidence_extraction_readme.py` unchanged and
still green) so both callers share identical matching mechanics, not
just identical data. No job-specific alias-safety table was needed — no
job-description-only false positive distinct from README's was observed
in manual validation.

**Two real false positives found in manual validation, fixed before this
entry was written:** `"Build and maintain ETL pipelines using Python"`
was promoting `"Build"` to `unresolved:build`; `"Proficiency in Python
for tooling and scripting"` was promoting `"scripting"` similarly. Root
cause: the conservative unknown-term list-splitter fired on any bare
`"X and Y"`, and a bare "and" (no comma) is far more often a verb phrase
than a technology list. Fixed by requiring an actual comma in the claim
text before the list-scan runs at all — both now have dedicated
regression tests.

**Versioning:** `JOB_DESCRIPTION_PARSER_VERSION = "job_description_parser:v1"`
(new, `jobs/parsing/parser.py`) — the value stamped into
`JobRequirementProfile.parser_version`, an EXISTING field (Milestone 6A),
so no schema change was needed to introduce it.
`JOB_REQUIREMENT_SCHEMA_VERSION` stays `1` (confirmed: `git diff` shows
zero changes to `jobs/models.py`/`jobs/profile.py`/`jobs/types.py`).
`CONCEPT_REGISTRY_VERSION` stays `3` (no concept added/renamed; the new
`concepts/matching.py` is a pure code refactor, not a registry content
change). `EVIDENCE_SCHEMA_VERSION`, `REPOSITORY_RANKING_VERSION`,
`SCORING_RUBRIC_VERSION`, `DATASET_VERSION` untouched.

**Manual real-world validation (Part 19):** four hand-written, local job
descriptions (no scraping) — Backend Software Engineer, Robotics
Software Engineer, ML Engineer, and Data Engineer (the required
"substantially different fourth role") — full results in
`docs/ARCHITECTURE.md` §18.11, locked in as regression tests in
`tests/test_job_parser.py`'s `test_manual_validation_*`. All known
concepts resolved correctly; every `or`-shaped claim across all four
produced exactly one non-technical fallback and zero false
REQUIRED-technical rows; the Backend example's `Benefits:` section
(including a "React JS meetups" line) correctly produced zero
requirements, proving `framework.react` was never triggered by
marketing copy. Known accepted false negatives (documented, not fixed):
a standalone "Kubernetes"/"dbt" bullet with no co-occurring known
concept in the same claim produces nothing; "SQL" (not yet a registry
concept) inside a comma-less phrase is not recovered.

*(This paragraph describes the original Option A run. The
`alternative_requirement`-bucket side effect on non-technical "or"
phrasing it originally reported was ITSELF fixed by Milestone 6B.1's
structured-alternative correction, which added real evidence-based
classification instead of a blanket "any 'or'" rule — see that entry.)*

**Tests:** 113 new — `tests/test_concepts_matching.py` (4, the extracted
shared primitive), `tests/test_job_parser_segmentation.py` (17),
`tests/test_job_parser_extraction.py` (56, one file per pure function
module), `tests/test_job_parser.py` (36: input validation, provenance/
span-correctness, compound requirements, alternatives, non-technical,
unknown-tech policy, alias-safety regression, the four manual-validation
fixtures, and a 6A/6A.1 regression check). All deterministic, offline,
no network calls. **597 tests total, all passing** (up from 484; every
V1/5B/5C/5D/5D.1/6A/6A.1 test untouched and still green).

**Files changed:**
- `src/gitscore/concepts/matching.py` — new: `alias_pattern()`, extracted
  from `evidence/extraction/readme.py`.
- `src/gitscore/evidence/extraction/readme.py` — uses the extracted
  helper instead of its own private copy; no behavior change.
- `src/gitscore/jobs/parsing/__init__.py`, `segmentation.py`,
  `concepts.py`, `alternatives.py`, `experience.py`, `non_technical.py`,
  `necessity.py`, `importance.py`, `observability.py`, `confidence.py`,
  `dedup.py`, `parser.py` — new package.
- `src/gitscore/jobs/__init__.py` — exports `parse_job_description`,
  `JOB_DESCRIPTION_PARSER_VERSION`.
- `tests/test_concepts_matching.py`, `test_job_parser_segmentation.py`,
  `test_job_parser_extraction.py`, `test_job_parser.py` — new.
- `docs/ARCHITECTURE.md` — new §18; §17.10 amended with a forward
  pointer.
- This changelog entry.

**How to test:** `pytest` (whole suite, 597 tests, no network/token
required) or `pytest tests/test_concepts_matching.py
tests/test_job_parser_segmentation.py tests/test_job_parser_extraction.py
tests/test_job_parser.py -v` for just the 6B-relevant subset.

**Explicitly NOT done this milestone (per instruction — wait for
approval before starting):** deterministic matcher, match/coverage
score, strengths/gaps, alternative-role discovery, role archetypes, URL
ingestion, LinkedIn/Indeed/Glassdoor scraping, external LLM API,
CatBoost, UI, database persistence, any change to candidate evidence
extraction, Milestone 7. No commit was made — see Milestone 6B.1 for the
OR-handling correction applied before this milestone was committed.

## 2026-09-28 — Milestone 6A.1: Concept-id invariant review

**What changed:** A tiny correctness fix, not a redesign. Milestone 6A's
`JobRequirement.__post_init__` only checked that a non-`None`
`concept_id` was a non-empty string — `JobRequirement(...,
concept_id="whatever.random.string")` constructed without error, and
`is_resolved_concept` reported `True` for it, silently treating an
arbitrary, never-registered string as if it were a real concept.

**Fix:** one new function, `is_valid_concept_id(concept_id,
registry=None) -> bool` in `concepts/registry.py` (exported from
`gitscore.concepts`) — pure VALIDATION of an already-produced id, never
RESOLUTION: it returns `True` only if `concept_id` is (a) a real,
registered `TechnicalConcept.concept_id`, or (b) exactly what
`unresolved_concept_id()` would re-produce for its own suffix (checked
by calling that SAME existing function again, not by inventing a second
unresolved-id grammar). `is_valid_concept_id("Postgres")` is `False` even
though `resolve_concept("Postgres")` succeeds — the two answer different
questions. `JobRequirement.__post_init__` (`jobs/models.py`) now calls
this helper in place of the old bare non-empty-string check.

**Dependency direction unchanged:** `gitscore.jobs` still only ever
imports FROM `gitscore.concepts`, never the reverse; `gitscore.concepts`
still knows nothing about jobs; no circular import; the registry is
still never mutated; `JobRequirement` still never calls
`resolve_concept()` or performs any fuzzy/automatic conversion of an
unknown id — it only validates a string a caller already produced.

**The three intended states, now actually enforced:**
1. `concept_id=None` — non-conceptual requirement. Valid.
2. `concept_id` = a real registered `TechnicalConcept.concept_id` (e.g.
   `"database.postgresql"`). Valid.
3. `concept_id` = a well-formed `"unresolved:<term>"` id (e.g.
   `"unresolved:warp-level_primitives"`). Valid.
4. Anything else (`""`, whitespace, `"unresolved:"`,
   `"unresolved:   "`, `"garbage"`, `"language.does_not_exist"`,
   `"whatever.random.string"`, or a raw un-resolved human term like
   `"Postgres"`) — now rejected with `ValueError` at construction time,
   previously silently accepted.

**Versioning:** `JOB_REQUIREMENT_SCHEMA_VERSION` stays `1` — no field
added/removed/retyped on `JobRequirement`/`JobRequirementProfile`, only
tightened validation of an existing field. `CONCEPT_REGISTRY_VERSION`
stays `3` — no concept added/renamed/merged, no alias-safety or
normalization change; a new pure helper function is not a registry
content change under that constant's documented bump policy.
`EVIDENCE_SCHEMA_VERSION`, `REPOSITORY_RANKING_VERSION`,
`SCORING_RUBRIC_VERSION`, `DATASET_VERSION` untouched.

**Tests:** 7 new tests in `tests/test_technical_concepts.py`
(`is_valid_concept_id`: registered id, well-formed unresolved id,
malformed unresolved id, arbitrary nonexistent canonical-looking id,
empty/whitespace/padded string, never-resolves-a-raw-term, explicit
custom registry). 10 new tests in `tests/test_job_requirement_models.py`
covering the three valid states plus every invalid state listed above,
plus two regression tests confirming the existing Postgres/PyTorch
resolution examples and the compound-requirement (Python +
professional-experience) example are unchanged. **484 tests total, all
passing** (up from 467; every prior test, including all of 6A's manual
job examples, untouched and still green).

**Files changed:**
- `src/gitscore/concepts/registry.py` — new `is_valid_concept_id()`.
- `src/gitscore/concepts/__init__.py` — exports it.
- `src/gitscore/jobs/models.py` — `JobRequirement.__post_init__` uses it;
  docstring addendum.
- `tests/test_technical_concepts.py`, `tests/test_job_requirement_models.py`
  — new tests.
- `docs/ARCHITECTURE.md` — §17.3 addendum.
- This changelog entry.

**How to test:** `pytest` (whole suite, 484 tests, no network/token
required) or `pytest tests/test_technical_concepts.py
tests/test_job_requirement_models.py -v` for just the 6A.1-relevant
subset.

**Explicitly NOT done (per instruction):** no parser, no matcher, no
scoring, no job ingestion, no LLM, no URL ingestion, no persistence, no
new concept ontology, no new `JobRequirement`/`JobRequirementProfile`
field, no redesign of any 6A object. No commit was made.

## 2026-09-28 — Milestone 6A: Job requirement domain model

**What changed:** A new package, `src/gitscore/jobs/`, defining the
job-side structured representation that will eventually sit opposite
`CandidateEvidenceProfile`:

```
CandidateEvidenceProfile  +  JobRequirementProfile  -> (future) deterministic matcher
```

**Domain model only.** No job-description parser (regex or LLM-based),
no deterministic matcher, no scoring, no URL/job-board ingestion, no
persistence, and no change of any kind to candidate-evidence extraction,
the concept registry's data, repository ranking, or V1 scoring/dataset.
Full design writeup: `docs/ARCHITECTURE.md` §17 (new). This entry
summarizes.

**Why:** `docs/design/MILESTONE_5A_JOB_MATCHING_DESIGN.md` established
the two-sided architecture (Part 9) but was never implemented; Milestones
5B-5D.1 built out the candidate side only. This milestone builds the
missing job side, in isolation, so its shape can be validated before any
parser or matcher is built against it — mirroring exactly how Milestone
5C built the candidate-side domain model before Milestone 5D wired real
extraction into it.

**Domain objects introduced:**

| Object | Module | Role |
|---|---|---|
| `SourceSpan` | `jobs/models.py` | `(start, end)` character offsets into a `JobRequirementProfile.raw_text` — provenance, not automatic span extraction |
| `JobRequirement` | `jobs/models.py` | one indivisible claim from a job posting: original text, optional resolved concept, category, necessity, importance, GitHub observability, optional parser confidence, optional source span |
| `Necessity` | `jobs/types.py` | `REQUIRED` \| `PREFERRED` (plain enum, no ordering) |
| `Importance` | `jobs/types.py` | ordinal `LOW` < `MEDIUM` < `HIGH` — how much this requirement matters, independent of necessity |
| `GithubObservability` | `jobs/types.py` | ordinal `NOT_OBSERVABLE` < `PARTIALLY_OBSERVABLE` < `STRONGLY_OBSERVABLE` — can GitHub evidence plausibly speak to this KIND of claim at all |
| `ParserConfidence` | `jobs/types.py` | ordinal `LOW`/`MEDIUM`/`HIGH`, optional — how sure a future parser was it read the job text correctly; deliberately NOT `evidence.types.ConfidenceLevel` reused (see below) |
| `JobRequirementProfile` | `jobs/profile.py` | one job posting: title/company (informational only), raw text, requirements tuple, parser/schema version |

**Concept-driven, never role-driven:** nothing in `src/gitscore/jobs/`
branches on a role name, and there is no finite role enum anywhere.
`JobRequirement` is keyed by `concept_id`, resolved through the EXACT
SAME `gitscore.concepts.registry.resolve_concept()` every candidate-side
extractor already uses (Milestone 5D Part 11's "no second package-name
table" precedent, applied again here: no second job-requirement-to-
concept table either). An unanticipated technology in a job posting
resolves via the SAME `"unresolved:<term>"` policy `Evidence` already
uses (Milestone 5C Part 3) — never dropped, never silently promoted into
a new canonical concept, never written into the registry. This
supersedes the original 5A design draft's separate, never-implemented
`"provisional:<slug>"` proposal (one unresolved-id convention across the
whole codebase, not two).

**The one-claim-per-JobRequirement rule** is the direct fix for this
milestone's central warning example: "3+ years of experience building
Python backend services" must produce TWO `JobRequirement` rows (one
technical, `concept_id="language.python"`,
`github_observability=STRONGLY_OBSERVABLE`; one non-technical,
`concept_id=None`, `github_observability=NOT_OBSERVABLE`), never one row
asserting both a GitHub-observable concept and a non-observable
experience claim together. Non-technical requirements ("Bachelor's
degree," "excellent communication," "eligible to work in Canada") are
represented with `concept_id=None` and a free-form `category` string —
never with an invented `TechnicalConcept` id like `skill.communication`.

**Necessity, importance, and GitHub observability are three independent
axes**, not one combined field — narrower than the 5A draft's four-state
`requirement_type`, per this milestone's explicit "do not invent
excessive granularity" instruction. A job can require both Git (`LOW`
importance) and Python (`HIGH` importance) — both `REQUIRED`, weighted
very differently.

**Parser confidence is a genuinely separate type from evidence
confidence** — `ParserConfidence` was added as its own small `IntEnum`
rather than reusing `ConfidenceLevel`, because the two answer different
questions (how sure we are a job-text interpretation is correct, vs. how
sure we are a candidate-side GitHub observation is real); reusing one
enum for both would blur a job-parsing uncertainty into what would read
as a claim about a candidate's GitHub activity.

**`JobRequirementProfile` is candidate-independent by construction** —
no candidate/username, no `Evidence`, no match score, no coverage score,
no strengths/gaps, no repository references, no alternative roles. Pinned
by `test_job_requirement_profile.py::test_profile_has_no_candidate_or_match_fields`,
the direct counterpart to Milestone 5C's
`test_profile_has_no_job_related_fields`.

**Two deliberate policy differences from `CandidateEvidenceProfile`**
(both documented in `jobs/profile.py` so neither reads as an
inconsistency): (1) exact structural duplicate requirements are
REJECTED (`ValueError`), not silently deduplicated like Evidence —
Evidence's silent dedup exists for a corroboration model (the same real
fact re-observed); a job posting's requirements have no equivalent
legitimate source for an exact duplicate, so one is treated as a
construction bug. (2) `requirements` preserves the EXACT given order,
never canonically re-sorted like `Evidence` — a posting's requirement
order can itself be informative (earlier = often more prominent),
unlike an evidence pool's order, which carries no meaning.

**Versioning:** `JOB_REQUIREMENT_SCHEMA_VERSION = 1` (`jobs/types.py`),
a new, fully independent constant. `EVIDENCE_SCHEMA_VERSION`,
`CONCEPT_REGISTRY_VERSION`, `REPOSITORY_RANKING_VERSION`,
`SCORING_RUBRIC_VERSION`, and `DATASET_VERSION` are all untouched —
nothing in this milestone meets any of their bump conditions. Bumps when
`JobRequirement`/`JobRequirementProfile` change SHAPE; does NOT bump for
a new enum member (additive), mirroring `EVIDENCE_SCHEMA_VERSION`'s own
policy.

**Manual examples (Part 12):** `tests/test_job_requirement_manual_examples.py`
hand-builds full `JobRequirementProfile`s for a Backend Software
Engineer, a Robotics Software Engineer, and a Machine Learning Engineer
— deliberately near-zero requirement overlap, no automated parsing, no
candidate scored against any of them. All three fit the exact same
`JobRequirementProfile`/`JobRequirement` shape; `language.python` appears
in all three at different `Importance` levels; the robotics example's
"Linux" resolves via the same `unresolved:<term>` path an unrecognized
GitHub language-stats value would.

**Tests:** 57 new tests across
`tests/test_job_requirement_models.py` (`SourceSpan`/`JobRequirement`:
technical-resolved, technical-unresolved, non-technical, necessity,
importance, observability, parser confidence, provenance, invalid
states, equality/hash),
`tests/test_job_requirement_profile.py` (`JobRequirementProfile`:
multiple/mixed requirements, order preservation, description
preservation, optional title/context, invalid empty description, invalid
provenance spans, duplicate rejection, candidate-independence), and
`tests/test_job_requirement_manual_examples.py` (Part 12's three jobs).
All deterministic, offline, no network calls. **467 tests total, all
passing** (up from 410; every 5B/5C/5D/5D.1/V1 test untouched and still
passing).

**Files changed:**
- `src/gitscore/jobs/__init__.py`, `types.py`, `models.py`, `profile.py`
  — new package.
- `tests/test_job_requirement_models.py`,
  `test_job_requirement_profile.py`,
  `test_job_requirement_manual_examples.py` — new.
- `docs/ARCHITECTURE.md` — new §17 (full design detail).
- This changelog entry.

**How to test:** `pytest` (whole suite, 467 tests, no network/token
required) or `pytest tests/test_job_requirement_models.py
tests/test_job_requirement_profile.py
tests/test_job_requirement_manual_examples.py -v` for just the
6A-relevant subset.

**Explicitly NOT done this milestone (per instruction — wait for
approval before starting):** job-description parser (regex or LLM), URL
ingestion, deterministic matcher, match/coverage scores, strengths/gaps,
alternative-role discovery, CatBoost, UI, database persistence/migration,
any change to candidate-evidence extraction. No commit was made.

## 2026-09-28 — Milestone 5D.1: Context-safe concept resolution

**What changed:** A focused correctness fix to Milestone 5D's README
extractor, requested after real-world validation showed it was treating
known ordinary-English false positives ("go", "next", the "js" suffix of
".js"-named frameworks) as accepted behavior instead of fixing them. No
architecture, pipeline, ranking, evidence model, API strategy, confidence
system, or extraction-scope change — see `docs/ARCHITECTURE.md` §16 for
the full design writeup; this entry summarizes.

**Root cause:** `TechnicalConcept.aliases` was one flat list, matched
identically by every source. A structured source (a `package.json` key,
a GitHub language-stats name) hands the matcher an already-scoped,
intentional term, so short aliases like `"go"`/`"next"`/`"js"` are
completely safe there. Free-form README prose is not scoped at all —
those same short aliases collide with ordinary English ("I **go** for
large components", "**Next** Track") or with unrelated `.js`-suffixed
names ("Next**.js**" incidentally satisfying a bare `"js"` alias).

**Fix — source-aware alias metadata, not a second table:**
`TechnicalConcept` (`concepts/models.py`) gained
`readme_unsafe_aliases: frozenset[str]` (validated as a subset of
`aliases` in `__post_init__`) and a `readme_safe_aliases()` method
(`aliases` minus `readme_unsafe_aliases`). `concepts/registry.py` marks
`"go"` (on `language.go`), `"next"` (on `framework.nextjs`), `"js"` (on
`language.javascript`), `"ts"` (on `language.typescript`), and `"c"` (on
`language.c`, its only alias) as `readme_unsafe`.
`evidence/extraction/readme.py` is the ONLY caller of
`readme_safe_aliases()` — it now matches that restricted list instead of
the full `aliases`. `resolve_concept()` and every structured-source
caller (`dependency_evidence.py`, `languages.py`) are byte-for-byte
unchanged: they still resolve the full alias set, so `package.json`'s
`"next"` dependency and GitHub's `"Go"` language-stats name keep
resolving exactly as before. A `DEPENDENCY_CONCEPT_ALIASES`-style second
mapping was considered and rejected — nothing about structured
dependency resolution was actually broken, so nothing there needed
changing.

**README-safe alias policy:** an alias is README-safe by default; it is
marked unsafe only when it is short and/or an ordinary English word that
literal, boundary-only, case-insensitive matching cannot tell apart from
non-technical prose. `"golang"`/`"next.js"`/`"nextjs"`/`"javascript"`/
`"typescript"` remain README-safe unambiguous forms. `language.c`'s only
alias (`"c"`, a single letter) has no safe form at all, so it now
produces **zero** README evidence — a documented limitation (see below),
not a bug.

**Structured dependency alias policy:** unchanged from Milestone 5D — no
second package-name table; `resolve_concept()`'s full alias set is
exactly correct for a manifest declaration, which is unambiguous by
construction.

**Language-statistics resolution:** unchanged — `languages.py` still
calls `resolve_concept()` with GitHub's exact language-stats names
(`"Go"`, `"JavaScript"`, `"TypeScript"`, `"C"`, `"C++"`, ...), which
resolve through the full alias set, not `readme_safe_aliases()`. Covered
by a new regression test,
`test_evidence_extraction_languages.py::test_short_readme_unsafe_aliases_still_resolve_githubs_exact_language_names`.

**Versioning:**
- `CONCEPT_REGISTRY_VERSION` 2 -> 3 — no concept added/renamed/merged,
  but the registry's per-alias safety metadata changed, which its own
  bump policy (`registry.py`) treats as a content change worth tracking.
- `readme.py`'s `EXTRACTOR_VERSION` `readme:v1` -> `readme:v2` — its
  matching behavior changed. No other extractor's version moved.
- `EVIDENCE_SCHEMA_VERSION` stays `2` — no shape change to `Evidence`,
  `CandidateConceptSummary`, `CandidateEvidenceProfile`, or
  `RepositoryAnalysisCoverage`.
- `SCORING_RUBRIC_VERSION`, `DATASET_VERSION`, `REPOSITORY_RANKING_VERSION`
  untouched, per instruction.

**Tests:** 2 existing version-pin tests updated
(`test_technical_concepts.py::test_concept_registry_version_constant_exists_and_is_an_int`,
updated for the 2 -> 3 bump). `test_evidence_extraction_readme.py`'s two
former "known false positive, accepted" tests replaced with tests
proving the false positive is GONE (`test_bare_next_no_longer_matches_ordinary_english`,
`test_bare_go_no_longer_matches_ordinary_english_i_go_for`, `..._let_it_go`,
`test_written_in_go_bare_form_is_a_documented_limitation_not_detected`),
plus new tests for the surrounding behavior: `"next steps"`/`"Next Track"`
still produce no evidence, `"Uses Next.js"` still matches
`framework.nextjs`, a `Next.js` mention does NOT also produce
`language.javascript` evidence, an independent `"JavaScript"` mention
still does, `"golang"` still matches, and bare `"C"` never matches. 6 new
tests added to `test_technical_concepts.py` for
`readme_safe_aliases()`/the `__post_init__` subset validation, plus a
resolve_concept() regression test confirming go/next/js/ts/c are still
valid structured-source aliases. 1 new regression test each in
`test_evidence_extraction_languages.py` (GitHub language-stats names) and
`test_evidence_extraction_dependency_mapping.py` (`"next"` package
dependency). All new tests are deterministic, offline, no network calls.
**410 tests total, all passing** (up from 395; no test removed, several
rewritten in place).

**Real-account re-validation** (the same 4 accounts Milestone 5D's
original validation used — `Jango1324`, `torvalds`, `karpathy`,
`sindresorhus` — NOT the 18-account pilot, per instruction), via
`scripts/inspect_evidence_profile.py`, confirms the false positives are
gone: `torvalds/1590A` and `karpathy/autoresearch` no longer produce
`language.go` README evidence; `Jango1324/Arduino-Based-Media-Player` no
longer produces `framework.nextjs` README evidence from "Next Track", and
`Jango1324`'s real `package.json` `"next"` dependency still correctly
resolves to `framework.nextjs` at `STRONG` confidence. `API requests` is
identical to Milestone 5D's original run for all four accounts (README
matching doesn't change what's fetched); `Evidence items`/`Concepts
detected` dropped for every account, as expected. Full corrected
before/after table: `docs/ARCHITECTURE.md` §15.11 (also fixes that
table's separate, unrelated Requests/Evidence-items column swap for
`karpathy`/`sindresorhus`, found while re-measuring). Zero extractor
failures across all four, both before and after.

**Known remaining limitation (intentional, not fixed):** bare "Go"
("Written in Go") and bare "C" still produce no README evidence — there
is no literal, deterministic way to distinguish them from ordinary
English without the fuzzy/NLP inference this project is scoped to avoid.
Language-stats extraction remains the practical source for both. Other
short-and-also-an-English-word registry aliases (`react`, `flask`,
`express`, ...) were not evaluated this round — out of this cleanup's
bounded scope — and may need the same `readme_unsafe_aliases` treatment
if real validation flags them later.

**Files changed:**
- `src/gitscore/concepts/models.py` — `TechnicalConcept.readme_unsafe_aliases`,
  `readme_safe_aliases()`, `__post_init__` subset validation.
- `src/gitscore/concepts/registry.py` — `CONCEPT_REGISTRY_VERSION` 2->3;
  `readme_unsafe_aliases` on `language.go`, `framework.nextjs`,
  `language.javascript`, `language.typescript`, `language.c`; updated
  module/entry docstrings (the old "accepted false positive" comments on
  `framework.nextjs` no longer describe current behavior).
- `src/gitscore/evidence/extraction/readme.py` — matches
  `concept.readme_safe_aliases()` instead of `concept.aliases`;
  `EXTRACTOR_VERSION` `readme:v1` -> `readme:v2`.
- `src/gitscore/evidence/extraction/dependency_evidence.py` — clarifying
  comment only (no behavior change): explains why this module
  intentionally keeps using the full `aliases` list.
- `tests/test_technical_concepts.py`, `tests/test_evidence_extraction_readme.py`,
  `tests/test_evidence_extraction_languages.py`,
  `tests/test_evidence_extraction_dependency_mapping.py` — see Tests above.
- `docs/ARCHITECTURE.md` — new §16; §15.6/§15.11/§15.12 updated in place
  (false positives now documented as fixed, not accepted; validation
  table corrected and re-measured).
- This changelog entry.

**How to test:** `pytest` (whole suite, 410 tests, no network/token
required) or `pytest tests/test_evidence_extraction_readme.py
tests/test_technical_concepts.py tests/test_evidence_extraction_languages.py
tests/test_evidence_extraction_dependency_mapping.py -v` for just the
5D.1-relevant subset. Real-account re-validation:
`python scripts/inspect_evidence_profile.py <username>` against
`Jango1324`/`torvalds`/`karpathy`/`sindresorhus` (requires `GITHUB_TOKEN`
in `.env`).

**Explicitly NOT done this milestone (per instruction — wait for
approval before starting):** Milestone 6, `JobRequirementProfile`,
job-description parsing, any deterministic matcher, match scores,
alternative-role discovery, CatBoost, LLM-based extraction, UI, no
redesign of the pipeline/ranking/evidence model/API strategy/confidence
system/extraction scope, no `react`/`flask`/`express`-style alias review
beyond what was asked. No commit was made.

## 2026-09-27 — Milestone 5D: Bounded technical evidence extraction

**What changed:**

The first real V2 evidence pipeline, connecting Milestone 5B's
repository ranking to Milestone 5C's Evidence/CandidateEvidenceProfile
domain model with an actual per-repository extraction step. New package
`src/gitscore/evidence/extraction/` (`languages.py`, `readme.py`,
`python_deps.py`, `js_deps.py`, `dependency_evidence.py`, `docker.py`,
`files.py`) plus a new orchestrating entry point,
`gitscore.pipeline.evidence.extract_candidate_evidence()`. **No job
matching, no JobRequirementProfile, no job-description parsing, no match
scores, no alternative-role discovery, no CatBoost, no LLM extraction, no
UI, no source-code/test/CI/notebook-content crawling, no recursive
repository crawling, no database schema change, no pilot recollection.**
V1 (`features/*`, `scoring/readiness.py`, `pipeline/analyze.py`, Dataset
V1) is byte-for-byte unchanged. 320 of Milestone 5C's 322 pre-existing
tests untouched; 2 version-pin tests updated for a deliberate, documented
version bump (see below); 73 new tests added. Full suite: **395 tests,
all passing**, no live GitHub calls, no GitHub token required.

**Why:** Milestones 5B and 5C each shipped as standalone, unconnected
modules by design (validate each piece in isolation before wiring). This
milestone is the first to connect them end-to-end and prove the whole
loop — ranking bounds cost, extraction produces real provenance-backed
Evidence — against real GitHub accounts, not just synthetic fixtures.

**Full design writeup, API cost model (with real measured numbers across
4 validated accounts), language-significance policy, README-matching
policy and its two documented known false positives, dependency-mapping
design, Docker semantics, confidence table, and failure-semantics table:
see `docs/ARCHITECTURE.md` §15 (new).** This entry summarizes; §15 is the
authoritative detail.

**The new V2 flow:**

```
GitHub username
  -> GitHubClient.get_repositories()        listing (5B, unchanged)
  -> parse_repo_summary() -> rank_repositories()   top N=15 (5B, unchanged)
  -> per selected repo: languages + README + ONE root-listing call
     + get_repository_file() for whichever of 8 supported filenames
     the root listing showed actually exist
  -> extractors -> Evidence[]                (THIS MILESTONE)
  -> build_candidate_evidence_profile()       CandidateEvidenceProfile (5C, unchanged)
```

**GitHub client additions (`github/client.py`):** `get_repository_readme_with_path()`
(README text + its resolved path, for provenance),
`get_repository_root_contents()` (one bounded, non-recursive root-listing
call — a 404 means a genuinely empty repo, returns `[]`, not a failure),
`get_repository_file()` (fetch one known-to-exist file by path; unlike
the README method, a 404 here IS a real reportable failure — the file
disappeared between listing and fetch). `get_repository_readme()`'s
existing signature/behavior is unchanged; `_fetch_readme()` is now the
one shared implementation both README methods call.

**Extractors, versions, and confidence** (full rationale in
ARCHITECTURE.md §15.5-§15.9):

| Extractor | Evidence type | Confidence | Version |
|---|---|---|---|
| `languages.py` | `REPOSITORY_LANGUAGE` | `WEAK` (<40% of bytes) / `MODERATE` (≥40%) | `language:v1` |
| `readme.py` | `README` | `MODERATE` | `readme:v1` |
| `python_deps.py` (requirements.txt) | `DEPENDENCY` | `STRONG` | `requirements:v1` |
| `python_deps.py` (pyproject.toml, `[project.dependencies]` only) | `DEPENDENCY` | `STRONG` | `pyproject:v1` |
| `js_deps.py` (package.json `dependencies`+`devDependencies`) | `DEPENDENCY` | `STRONG` | `npm:v1` |
| `docker.py` | `DOCKER` | `STRONG` | `docker:v1` |

Language significance policy: a language must be ≥5.0% of a repo's
byte total to produce evidence (`MIN_SIGNIFICANT_PERCENTAGE`,
`languages.py`); ≥40.0% promotes `WEAK` to `MODERATE`
(`MODERATE_CONFIDENCE_PERCENTAGE`). Percentage-based, not a byte floor,
because GitHub's language-stats endpoint already normalizes for repo
size. An unresolved-but-meaningful language still produces
`unresolved:<name>` evidence (mirrors `v1_bridge.py`'s existing
`primary_language` handling) — 8 distinct unresolved languages were
observed live (`cmake`, `makefile`, `openscad`, `qml`, `xslt`, `lua`,
`astro`, `postscript`, `swift`), confirming the policy works as intended
rather than silently dropping real signal.

Dependency mapping is **data, not code**: package/dependency names
resolve through the SAME `concepts.registry` aliases every other source
uses (`resolve_concept()`) — no second "package name → concept" table.
Registry additions this milestone: a representative set of GitHub
language names (`javascript`, `typescript`, `java`, `c`, `cpp`, `csharp`,
`go`, `rust`, `ruby`, `php`, `shell`, `html`, `css`,
`jupyter_notebook`) plus a handful of dependency-manifest-only concepts
(`tensorflow`, `pandas`, `express`, `nestjs`, `fastapi`, `flask`,
`prisma`) and expanded aliases on `postgresql`
(`psycopg2`/`psycopg2-binary`/`psycopg`). `CONCEPT_REGISTRY_VERSION`
bumped 1 → 2 (content change, per its own bump policy). **Unknown**
dependency names are deliberately NOT turned into `unresolved:` Evidence
(unlike languages) — tracked only as a plain diagnostic list
(`EvidenceExtractionResult.unknown_dependency_names`), never written into
the registry or the Evidence pool, because a manifest can list hundreds
of irrelevant/niche package names (185 unique unknown names observed on
`sindresorhus` alone) and turning every one into Evidence would be noise,
not signal — exactly what the "do not pretend every dependency is a
useful technical concept" instruction warns against. This mirrors
`v1_bridge.py`'s existing topics-skip precedent, not its
always-evidence primary-language precedent.

**Root-file discovery (`files.py`):** ONE `get_repository_root_contents()`
call per selected repo returns every root entry; `discover_supported_root_files()`
is a pure, case-sensitive filter against the 8 supported filenames
(`requirements.txt`, `pyproject.toml`, `package.json`, `Dockerfile`,
`docker-compose.yml`, `docker-compose.yaml`, `compose.yml`,
`compose.yaml`) — never a recursive crawl, never one probe-request per
candidate filename. `Pipfile`/`environment.yml` were evaluated (Part 7's
"optional if trivial") and deliberately **not** added: none of the four
validated real accounts had either, and `requirements.txt`/
`pyproject.toml`/`package.json` already covered every dependency signal
actually observed.

**pyproject.toml support is deliberately bounded:** only PEP 621's
`[project] dependencies = [...]` string array, parsed with the stdlib
`tomllib` (no new dependency — the project already requires Python
≥3.11). Poetry's `[tool.poetry.dependencies]` table format is explicitly
NOT supported (a fundamentally different, name-keyed shape) — confirmed
by a dedicated test. Malformed TOML raises `tomllib.TOMLDecodeError`,
caught by the orchestration layer and recorded as an extractor failure,
never crashing candidate analysis.

**Evidence-schema change (`EVIDENCE_SCHEMA_VERSION` 1 → 2):**
`RepositoryAnalysisCoverage` gained one additive field,
`partially_analyzed: tuple[RepositoryIdentity, ...] = ()` — the subset of
`analyzed` where at least one evidence source for that repository could
not be inspected (a real failure, not an expected absence like "no
requirements.txt"). This is the smallest compatible extension found
necessary to represent Milestone 5D Part 14's distinction between "we
looked and it's not there" and "we couldn't look" — no broader redesign
of `CandidateEvidenceProfile` was needed. It does not add a new coverage
tier: a `partially_analyzed` repository is still counted in
`analyzed`/`analyzed_count`/`is_complete` exactly as before. Two existing
version-pin tests (`test_evidence_schema_version_constant_exists`,
`test_concept_registry_version_constant_exists_and_is_an_int`) were
updated to assert the new values, with comments explaining why each bump
is legitimate per its own documented policy.
`SCORING_RUBRIC_VERSION`/`DATASET_VERSION`/`REPOSITORY_RANKING_VERSION`
are untouched — nothing in this milestone meets any of their bump
conditions.

**Failure semantics (`pipeline/evidence.py`):** every network call per
selected repository is isolated in its own try/except — one failing
source degrades only that source. `README`/manifest absence (404 / not
in the root listing) is an expected absence, never recorded as a
failure. A languages/README/root-listing/manifest fetch failure, or a
malformed manifest (bad TOML/JSON), is recorded as an `ExtractionFailure`
(`repository`, `source`, `error`) and marks that repository
`partially_analyzed` — analysis of the rest of that repo and every other
selected repo continues. `GitHubRateLimitError` is the one exception NOT
caught anywhere in this path — it propagates immediately and aborts the
whole run, mirroring V1's existing `pipeline/analyze.py` batch-abort
policy. `EvidenceExtractionResult` (new, `pipeline/evidence.py`) bundles
`profile` + `extractor_failures` + `unknown_dependency_names` —
deliberately NOT part of `CandidateEvidenceProfile` itself, since these
are pipeline-run diagnostics, not candidate technical evidence.

**API cost — real measured numbers, not just an estimate** (full table
in ARCHITECTURE.md §15.4): `torvalds` (12 repos) → 38 requests;
`Jango1324` (20 repos) → 53; `karpathy` (63 repos) → 54; `sindresorhus`
(1,141 repos) → 70. Deep-analysis cost is bounded by N=15 regardless of
total repo count — confirmed directly: `sindresorhus` at 1,141 repos
costs roughly the same as `karpathy` at 63, the difference being a
handful of extra listing-pagination requests, not a multiplier on deep
analysis.

**Known false positives, found in live validation** (see
ARCHITECTURE.md §15.6 for the full original writeup):
- Bare `"go"` (alias of `language.go`) matches ordinary English ("I
  **go** for...", "let it **go**") — inherent to context-free keyword
  matching, not fixable without exactly the fuzzy/NLP inference this
  milestone is scoped to avoid. Observed on `torvalds/1590A` and
  `karpathy/autoresearch`.
- Bare `"next"` (alias of `framework.nextjs`) matches ordinary English
  ("**Next** Track"). Observed on `Jango1324/Arduino-Based-Media-Player`.
- A real (and initially test-driven-out) bug, fixed before it shipped:
  `requirements.txt` parsing originally read a bare VCS/URL requirement
  (`git+https://...`) as if `git` were a package name. Fixed by skipping
  any line containing `"://"`.

> **Amendment (Milestone 5D.1, see that entry above):** the "go"/"next"
> README false positives above were originally *accepted* as documented
> limitations here. Follow-up real-world validation judged that
> unacceptable for ordinary English to keep producing known-wrong
> technical evidence, so Milestone 5D.1 fixed them at the alias level
> (`readme_unsafe_aliases`) instead — they are no longer current,
> intended behavior. This paragraph is left as the historical record of
> what Milestone 5D actually shipped and why; see the Milestone 5D.1
> entry and `docs/ARCHITECTURE.md` §15.6/§16 for the current, corrected
> policy.

**Real-account validation (Milestone 5D Part 17/18), V2 pipeline only, no
score of any kind produced:** `Jango1324`, `torvalds`, `karpathy`,
`sindresorhus` — chosen for diversity (small Python/web account, C/systems,
Python/ML, JS/TS at 1,140+ repos). Zero extractor failures across all
four. Full per-account breakdown (repos discovered/analyzed, evidence by
type, concepts detected, unresolved concepts, unknown dependency counts,
representative provenance) in ARCHITECTURE.md §15.11. Reproducible via
`scripts/inspect_evidence_profile.py <username>` (new, inspection-only —
no persistence, no job-fit/readiness score).

**`Jango1324/Pneumonia-Detection-Ai` (Part 15's named edge case):**
confirmed still ranked outside the top 15 in this milestone's real run —
reported truthfully as `discovered=yes, analyzed=no` in
`inspect_evidence_profile.py`'s output. Not manually forced into the
selection; no ranking-weight change or job-aware special-casing was
added for it, per explicit instruction.

**Files changed:**
- `src/gitscore/github/client.py` — `get_repository_readme_with_path()`,
  `get_repository_root_contents()`, `get_repository_file()`,
  `_fetch_readme()` (shared implementation).
- `src/gitscore/concepts/registry.py` — `CONCEPT_REGISTRY_VERSION` 1→2;
  new language + dependency-manifest-only concepts (see above); expanded
  `database.postgresql` aliases.
- `src/gitscore/evidence/types.py` — `EVIDENCE_SCHEMA_VERSION` 1→2.
- `src/gitscore/evidence/profile.py` — `RepositoryAnalysisCoverage.partially_analyzed`
  (+ `partially_analyzed_count`), `build_candidate_evidence_profile(partially_analyzed=...)`.
- `src/gitscore/evidence/extraction/__init__.py`, `files.py`,
  `languages.py`, `readme.py`, `python_deps.py`, `js_deps.py`,
  `dependency_evidence.py`, `docker.py` — new package.
- `src/gitscore/pipeline/evidence.py` — new: `extract_candidate_evidence()`,
  `EvidenceExtractionResult`, `ExtractionFailure`.
- `scripts/inspect_evidence_profile.py` — new manual inspection/validation tool.
- `tests/conftest.py` — `FakeEvidenceGitHubClient`, `root_entry()` helper.
- `tests/test_evidence_extraction_languages.py`,
  `test_evidence_extraction_readme.py`,
  `test_evidence_extraction_requirements_txt.py`,
  `test_evidence_extraction_pyproject_toml.py`,
  `test_evidence_extraction_package_json.py`,
  `test_evidence_extraction_dependency_mapping.py`,
  `test_evidence_extraction_docker.py`, `test_pipeline_evidence.py` — new.
- `tests/test_candidate_evidence_profile.py` — new `partially_analyzed`
  coverage tests.
- `tests/test_evidence_models.py`, `tests/test_technical_concepts.py` —
  version-pin tests updated for the deliberate 1→2 bumps, with rationale
  comments.
- `docs/ARCHITECTURE.md` — new §15 (full design detail); §13/§14 updated
  to reflect that 5B/5C are now wired together, not just standalone.
- `docs/PIPELINE.md` — new short section pointing to the V2 path.
- This changelog entry.

**How to test:** `pytest` (whole suite, 395 tests, no network/token
required) or `pytest tests/test_pipeline_evidence.py
tests/test_evidence_extraction_*.py tests/test_candidate_evidence_profile.py -v`
for just the Milestone 5D-relevant subset. Real-account validation:
`python scripts/inspect_evidence_profile.py <username>` (requires
`GITHUB_TOKEN` in `.env` for a reasonable rate limit, per the existing
`.env.example`).

**Explicitly NOT done this milestone (per instruction — wait for
approval before starting):** Milestone 6/6A, `JobRequirementProfile`,
job-description parsing, any deterministic matcher, match scores,
alternative-role discovery, CatBoost, LLM-based extraction, UI. No commit
was made.

## 2026-09-11 — Milestone 5C: Generalized evidence domain model

**What changed:**

Two new packages, `src/gitscore/concepts/` and `src/gitscore/evidence/`
— the domain vocabulary future evidence extractors will produce and
future job matching will consume: `Candidate → Repository →
Observation → Technical Concept`, with provenance preserved end to end.
**No deep evidence extraction, no dependency/manifest/Dockerfile/CI/
notebook parsing, no job-description parsing, no JobRequirementProfile,
no job matching, no match scores, no alternative-role discovery, no role
archetypes, no CatBoost, no LLM analysis, no UI, no source-code
crawling, no database schema change, no org-contribution attribution, no
pilot recollection.** Repository ranking (Milestone 5B) was not wired
into this milestone's model either — the two remain independent,
standalone modules. V1 (`features/*`, `scoring/readiness.py`, Dataset
V1) is completely unchanged. Existing 257 tests untouched and still
passing; 65 new tests added (322 total). Everything is in-memory plain
Python — no SQLAlchemy import anywhere in either new package.

**Why:** Milestone 5A's design established that GitScore needs a
structured, provenance-backed representation of "what a candidate's
GitHub evidence shows" *before* any job-matching logic can be built on
top of it. This milestone builds exactly that representation in
isolation, so its shape can be validated (by tests and by bridging real
V1-shaped data into it) before locking anything into a database schema
or building extractors against it.

*Domain objects introduced:*

| Object | Module | Role |
|---|---|---|
| `TechnicalConcept` | `concepts/models.py` | one canonical concept (`concept_id`, `display_name`, `category`, `aliases`, optional `parent_id`/`related_ids`) |
| `ConceptRegistry` / `default_registry()` | `concepts/registry.py` | immutable, in-memory alias index; built once, never mutated |
| `resolve_concept(term)` / `ConceptResolution` | `concepts/registry.py` | deterministic term → concept resolution, explicit `matched` flag |
| `RepositoryIdentity` | `evidence/models.py` | minimal `(owner, name)` reference — not a full repository summary (that's `ranking.RepositoryRankingResult`, kept separate) |
| `Evidence` | `evidence/models.py` | one provenance-backed observation: repository, evidence type, raw text, normalized concept id, confidence, extractor version, optional file/location/timestamp |
| `EvidenceType` | `evidence/types.py` | `REPOSITORY_LANGUAGE`, `REPOSITORY_METADATA`, `README`, `DEPENDENCY`, `SOURCE_IMPORT`, `CONFIG`, `DOCKER`, `CI`, `TEST`, `NOTEBOOK`, `DEPLOYMENT` (not all have extractors yet) |
| `ConfidenceLevel` | `evidence/types.py` | ordinal `WEAK` / `MODERATE` / `STRONG` (see rationale below) |
| `CandidateConceptSummary` | `evidence/summary.py` | Evidence for one concept, always *derived*, never independently constructed |
| `RepositoryAnalysisCoverage` | `evidence/profile.py` | `discovered` vs. `analyzed` repository tuples + `is_complete` |
| `CandidateEvidenceProfile` | `evidence/profile.py` | the full job-independent picture: candidate, coverage, evidence, derived concept summaries, versions |

*Representative concept registry (13 entries, spanning 10 categories —
proving the mechanism, not a complete ontology):* `language.python`,
`database.postgresql`, `database.redis`, `ml.framework.pytorch`,
`framework.react`, `framework.nextjs`, `infra.docker`, `cloud.aws`,
`platform.cuda`, `robotics.ros2`, `embedded.rtos.freertos`,
`hdl.verilog`, `toolchain.llvm`. Adding a concept is one new
`TechnicalConcept(...)` entry in `concepts/registry.py::_CONCEPTS` — no
change to `ConceptRegistry`, `resolve_concept`, or anything downstream.

*Normalization rules (`concepts/normalize.py`):* lowercase, strip
periods and commas only, collapse internal whitespace. Deliberately
narrow — a blanket "strip all punctuation" normalizer would collide
unrelated concepts (e.g. "C++" and "C"); this rule set was chosen
specifically because it resolves every example in the milestone brief
correctly (`Postgres`/`postgresql`/`POSTGRESQL` → `database.postgresql`;
`React.js`/`ReactJS`/`react` → `framework.react`;
`torch`/`PyTorch` → `ml.framework.pytorch`;
`AWS`/`Amazon Web Services` → `cloud.aws`) without merging `C++`/`C`.
No LLM, no fuzzy matching — exact match against normalized aliases only.

*Unknown-concept policy (Part 3 — explicit choice):* `resolve_concept()`
returns an **explicit unresolved result** (`matched=False`,
`concept=None`), not a synthesized "provisional concept" object added
anywhere. Separately, at the `Evidence`-construction layer, an unmatched
raw term is given a deterministic, non-registry pseudo-id —
`"unresolved:<normalized-term>"` — so no observation is ever silently
dropped (architectural rule 4) while the canonical registry itself is
never mutated (architectural rule: no dynamic registry mutation from
unknown input — verified by
`test_technical_concepts.py::test_resolving_an_unknown_term_does_not_mutate_the_shared_registry`).
The same literal unknown term always maps to the same unresolved id
(useful later for tallying which unknown terms recur, for registry
curation); two *different* spellings of an unknown concept are
deliberately **not** merged — that would require the fuzzy-matching/
ontology-building work this milestone is explicitly scoped to avoid.

*Confidence model (Part 5 — ordinal, not float):* `ConfidenceLevel.WEAK
/ MODERATE / STRONG` (an `IntEnum`, so "strongest evidence" is a plain
`max()`). Chosen over a float (e.g. `0.87`) because nothing in this
milestone calibrates a claim like that against any real ground truth —
a float would assert a precision the system does not have. Confidence
describes confidence in **the evidence claim**, never candidate skill,
proficiency, or job fit — e.g. a `STRONG`-confidence dependency-manifest
observation of `torch` means "we are sure `requirements.txt` declares
this dependency," not "the candidate is skilled at PyTorch." Stated
explicitly in code docstrings and in `docs/ARCHITECTURE.md` §14 so it
can't be misread later.

*Aggregation rules (`evidence/summary.py`):* `CandidateConceptSummary`
is always built by `summarize_concept()` / `build_concept_summaries()`
from a pool of `Evidence` — never constructed or mutated directly.
`evidence_count`, `repositories` (distinct, sorted), and
`strongest_confidence` (max over the group) are all derived properties,
computed fresh from `evidence`, not separately stored fields that could
drift. Deterministic ordering: repository owner → repository name →
file path → evidence type → raw observation text, applied regardless of
input order.

*Duplicate policy:* `Evidence` is a frozen, fully hashable dataclass, so
exact structural duplicates (identical repository, file, evidence type,
concept, raw text, confidence, extractor version) collapse to one via a
plain `set()` — both inside `summarize_concept()` and at the whole-profile
level in `build_candidate_evidence_profile()`. Evidence differing in
*any* field (different file, different repo, different raw text, even a
re-run with a new `extractor_version`) is kept as a **separate** item,
not merged — corroborating evidence should be visible, not silently
absorbed.

*`CandidateEvidenceProfile` job-independence (Part 7 / architectural
rule 8):* no field for a target job, match score, required/preferred
skills, or alternative roles — pinned by
`test_candidate_evidence_profile.py::test_profile_has_no_job_related_fields`.
`concept_summaries` is exposed as a `types.MappingProxyType` (read-only
view), not a plain dict, so external code cannot mutate the derived
summaries independently of the `Evidence` that produced them —
structurally enforced, not just documented.

*Discovered vs. analyzed (Part 7):* `RepositoryAnalysisCoverage` carries
both `discovered` and `analyzed` repository-identity tuples plus
`is_complete` — the representable form of "GitScore discovered 1,140
repositories but deeply analyzed 15," laying the groundwork for the
`INSUFFICIENT_ANALYSIS` semantics from
`docs/design/MILESTONE_5A_JOB_MATCHING_DESIGN.md` Part 16. Not yet
connected to Milestone 5B's ranking output — that wiring is explicit
future work (see Part 24 milestone sequence), not part of this
milestone's scope.

**Persistence decision (Part 9):** agreed with the requested default —
**domain model first, persistence later.** No SQLAlchemy table was
added; `db/models.py`, `db/database.py`, and `db/queries.py` are
untouched. Justification: (1) no deep-extraction detector exists yet to
validate the shape against real output — the same mistake that produced
`ProfileFeature`'s known gaps (no unique constraint, no per-row rubric
version — `docs/ML_NOTES.md` §4 item 3) would be easy to repeat by
locking a schema in before the shape has been exercised; (2)
`CLAUDE.md`'s own DB rule ("prefer Alembic if schema evolution becomes
non-trivial") argues against introducing migration machinery for a model
still expected to change; (3) nothing in this milestone's success
criteria requires cross-process durability — everything is validated by
unit tests. No database migration was performed.

**Bridging existing V1 information (Part 10), without touching V1:**
`evidence/v1_bridge.py` (demonstration-only, not imported by
`pipeline/analyze.py` or any script) shows three concrete examples,
each backed by a test in `tests/test_v1_evidence_bridge.py`:
- `parse_repo()`'s `primary_language` → weak `REPOSITORY_LANGUAGE`
  evidence (and demonstrates the unresolved-concept path: an unrecognized
  language like "COBOL" still produces Evidence, with an
  `unresolved:cobol` concept id, never silently dropped).
- `parse_repo()`'s `readme` text → moderate `README` evidence, one item
  per matched concept (e.g. "Built using ROS2 for navigation" →
  `robotics.ros2`).
- `parse_repo_summary()`'s `topics` (Milestone 5B) → weak
  `REPOSITORY_METADATA` evidence, for topics that resolve to a known
  concept (non-technical topics like `"hacktoberfest"` are deliberately
  skipped, not turned into unresolved evidence — a detector-design
  choice, not a violation of the no-silent-drop rule, which concerns
  evidence that *was* extracted).
`features/ml.py`, `features/readme.py`, `features/languages.py`, and
`scoring/readiness.py` are byte-for-byte unchanged.

**Versioning:** `CONCEPT_REGISTRY_VERSION = 1`
(`concepts/registry.py`) — bump when a concept is added/renamed/merged,
or when `normalize.py`'s normalization rules change (that changes which
aliases resolve). `EVIDENCE_SCHEMA_VERSION = 1` (`evidence/types.py`) —
bump when `Evidence`, `CandidateConceptSummary`,
`CandidateEvidenceProfile`, or `RepositoryAnalysisCoverage` change SHAPE
(fields added/removed/retyped) — NOT for adding a new `EvidenceType`
member (additive, non-breaking) or a new concept (that's the registry
version). `SCORING_RUBRIC_VERSION`, `DATASET_VERSION`
(`dataset/schema.py`), and `REPOSITORY_RANKING_VERSION`
(`ranking/config.py`) are untouched — none of this milestone's changes
meet any of their bump conditions.

**Files changed:**
- `src/gitscore/concepts/__init__.py`, `models.py`, `normalize.py`,
  `registry.py` — new package.
- `src/gitscore/evidence/__init__.py`, `models.py`, `types.py`,
  `summary.py`, `profile.py`, `v1_bridge.py` — new package.
- `tests/test_technical_concepts.py`, `test_evidence_models.py`,
  `test_candidate_concept_summary.py`,
  `test_candidate_evidence_profile.py`, `test_v1_evidence_bridge.py` —
  new, 65 tests, all synthetic/in-memory, no network calls, no GitHub
  token.
- `docs/ARCHITECTURE.md` — new §14 documenting the domain model, the
  provenance philosophy, the discovered-vs-analyzed distinction, and the
  "Evidence Profile != Job Match" / "confidence != proficiency"
  statements.
- This changelog entry.

**Unresolved design questions (not decided in this milestone):**
- Whether `RepositoryAnalysisCoverage.analyzed` should eventually store
  richer per-repository ranking metadata (score, rank position) rather
  than plain `RepositoryIdentity` — deferred until a real caller (the
  future extraction pipeline) needs it.
- Whether `Evidence.location` (line/cell-level position, currently
  always `None` — no extractor populates it yet) is the right shape for
  every future evidence type (e.g. a Dockerfile instruction vs. a
  notebook cell vs. a source line) or whether it needs to become a
  structured type per `evidence_type` — left generic and unexercised
  until Milestone 5D's extractors have real opinions.
- Whether `ConfidenceLevel`'s 3-level ordinal scale is granular enough
  once Milestone 5D extractors exist for very different evidence
  strengths (e.g. a source-import + test-usage combination might
  deserve more separation from a single dependency-manifest line than
  "STRONG" vs. "MODERATE" allows) — the 5A design doc's fuller
  weak/moderate/strong/strongest ladder with numeric combination
  (Part 13) was deliberately NOT implemented here; reconciling the two
  is future work, not resolved now.
- The topics-skip-vs-unresolved asymmetry in `v1_bridge.py` (language
  always produces evidence, even unresolved; topics silently skip
  non-matches) is a reasonable per-source design choice but is not
  itself a governed rule — a future real topics extractor should
  revisit whether that asymmetry is still right.

**How to test:** `pytest tests/test_technical_concepts.py
tests/test_evidence_models.py tests/test_candidate_concept_summary.py
tests/test_candidate_evidence_profile.py tests/test_v1_evidence_bridge.py -v`
(65 tests, no network/token required).

## 2026-09-11 — Milestone 5B: Deterministic repository ranking

**What changed:**

New package `src/gitscore/ranking/` — a deterministic, job-independent
repository ranking system that selects which of a candidate's
repositories are worth a deep (per-repository) fetch later. This is
Stage 1 (+ an optional Stage 2 relevance boost) of the two-stage
ranking strategy proposed in
`docs/design/MILESTONE_5A_JOB_MATCHING_DESIGN.md` Part 11, approved as
the Milestone 5A design direction. **No CandidateEvidenceProfile
persistence, no Evidence tables, no JobRequirementProfile, no
job-description NLP, no deterministic job matching, no alternative-role
discovery, no CatBoost, no LLM analysis, no UI, no deep source-code
inspection, no database/schema change, no users recollected.** Existing
231 tests untouched and still passing; 26 new tests added (257 total).

**Why:** Milestone 4.5's pilot measured the current per-repository
collection cost directly — `sindresorhus` (1,140 repos) alone consumed
~34% of the 18-account pilot's ~6,740 GitHub API calls, because
languages + README are fetched for *every* repository regardless of how
informative it is. Ranking lets future deep analysis run on a bounded
top-N instead of the full repository list, without needing any new API
requests to decide the ranking itself.

**Ranking is deliberately job-independent and not a score.** It answers
"which repositories best represent this candidate's substantive
technical work" — never "is this candidate good," "is this candidate
ML-focused," or "does this candidate fit a job." It has no notion of
ML relevance, job requirements, or candidate quality. It only decides
what gets inspected next; the actual evidence-strength and job-matching
work (Milestones 5C+/6+/7+) is unaffected in shape or meaning by this
milestone.

*Zero-additional-API-cost fields (`github/parser.py`):*
- New `parse_repo_summary(repo)` extracts ranking fields — `archived`,
  `size` (as `size_kb`), `pushed_at`, `topics`, plus the fields
  `parse_repo()` already captures (`fork`→`is_fork`, `stargazers_count`,
  `forks_count`, `language`, `description`, `created_at`, `updated_at`,
  `html_url`) — straight from the repository-list payload
  `GitHubClient.get_repositories()` already returns. Verified against
  the live API: `archived`/`size`/`pushed_at`/`topics` are present on
  every entry today, they were simply never read. `parse_repo()` itself
  is unchanged (still requires languages+README, still used by the V1
  pipeline unmodified).

*Ranking formula (`ranking/rank.py`, weights in `ranking/config.py`):*
- Stage 1 base score = weighted sum of five components, each in
  `[0, 1]`: `size` (log-scaled against `size_reference_kb=2000`, so raw
  byte count can't reward vendored/binary bulk beyond a saturation
  point), `recency` (exponential decay on `pushed_at` — not
  `updated_at`, which also bumps on stars/issues — with a gentle
  `recency_half_life_days=730`), `language` (primary language present),
  `description` (non-blank description present), `stars` (log-scaled
  against `star_reference=50`, saturating early so a single viral repo
  cannot dominate). Default weights: size 0.35, recency 0.30, language
  0.15, description 0.10, stars 0.10 — stars capped at a fifth of the
  weight mass, per the milestone's "do not let stars dominate"
  requirement.
- Multiplicative dampeners (not exclusions — "fork ≠ useless"):
  `fork_multiplier=0.35`, `archived_multiplier=0.55`, and a
  `trivial_multiplier=0.25` for repositories at or below
  `trivial_size_kb_threshold=8` KB (near-empty scaffolds).
- Optional Stage-2 relevance boost: a caller-supplied plain list of
  terms (e.g. `["postgresql", "python", "docker"]`) matched against a
  repo's name/description/language/topics with the same word-boundary
  regex approach as `features/ml.py`'s `ML_KEYWORDS` (no substring
  false positives). Multiplies the Stage-1 score by
  `1 + relevance_boost_weight * (matched_terms / total_terms)`. Ranking
  with no terms supplied is byte-identical to Stage-1-only — this is
  explicitly **not** job-description parsing, just a literal,
  capped keyword-overlap hook for testing the two-stage interface.
- All weights/thresholds centralized in the frozen `RankingWeights`
  dataclass (`ranking/config.py`) — nothing is a scattered magic number
  in `rank.py`.

*Determinism and tie-breaking (`rank.py::_sort_key`):* score descending,
then `pushed_at` descending (missing/unparseable sorts oldest), then
repository name ascending case-insensitive. For a fixed `reference_time`
(resolved once per `rank_repositories()` call and reused for every
repository scored in that call), the same input always produces the
same order. Two calls at different real-world times may legitimately
reorder repositories as recency decays — intended, not nondeterminism.

*Top-N policy:* `DEFAULT_TOP_N = 15`. Fewer than N repositories → all
are returned, ranked, never padded. More than N → truncated to exactly
N, keeping the highest-scoring repositories (not an arbitrary prefix).

*Versioning:* `REPOSITORY_RANKING_VERSION = 1` (`ranking/config.py`),
a new constant, sibling to but independent of `SCORING_RUBRIC_VERSION`
and `DATASET_VERSION` (`dataset/schema.py`) — neither of those was
touched.

*New manual-inspection tool:* `scripts/rank_user_repos.py <username>
[--top N] [--relevance term1,term2,...]` — fetches one user's repo
listing (same calls `analyze_user()` already makes before any
per-repository fetch) and prints the top-N ranked repositories with
their full score/component/multiplier breakdown. Performs no
per-repository API calls, no persistence, does not call `analyze_user()`.

**N=10 vs 15 vs 20 validation (real accounts, listing-only fetches, no
per-repository calls):** ranked `Jango1324`, `chris1610`, `jph00`,
`sindresorhus`, `lucidrains`, `antirez`, `rasbt` (20 to 1,140 total
repositories). Score drop-off from rank 1→10→15→20 is steep for small
accounts (`Jango1324`: 0.90 → 0.24 → 0.12 → 0.02 — most real signal is
already in the top 8-10) and gentle-to-flat for large, prolific accounts
(`sindresorhus`/`lucidrains`/`rasbt`/`antirez` all stay above ~0.76-0.94
through rank 20 — everything that far down is still genuinely
substantial). N=15 was confirmed as a reasonable default: past the
point of diminishing returns for ordinary/small accounts, and a real,
predictable cost cap for large ones. Across these 7 accounts, deep
analysis at N=15 costs an estimated 237 API calls vs. 3,859 for
analyzing every repository (93.9% reduction; `sindresorhus` alone:
2,293 → 43, a 98.1% reduction) — using the same 2-calls-per-repository
cost model measured in the Milestone 4.5 pilot.

**Surprising/notable result (`Jango1324`):** the ranking correctly
surfaces the account's substantive engineering projects
(`JPod-ESP32`, `Mentoria`, `Arduino-Based-Media-Player`, `obsidianblog`,
`House-Of-Memories`) above its forks and trivial repositories, which is
the core validation this milestone asked for. But the one repository
Milestone 4.5 identified as this account's single genuine ML-relevant
work (`Pneumonia-Detection-Ai`, from an educational AI program) ranks
**16th of 20** — just outside the top-15 cutoff — because it is only
4 KB with no stars, so on pure substantiveness signals it looks
trivial. Applying the optional Stage-2 relevance boost with ML-flavored
terms (`["ai", "machine learning", "pytorch"]`) still does **not** pull
it into the top 15: the boost is multiplicative on an already
near-zero base score, so it cannot rescue a repository Stage 1 scores
as trivial. Documented as a known limitation (see below), not patched —
patching a specific account's ranking would violate the "do not
hardcode repository names" instruction this validation was run under.

**Known limitations (deliberately not fixed in this milestone):**
- `size_kb` cannot distinguish authored code from vendored/binary bulk
  — observed on `antirez/llama.cpp-deepseek-v4-flash` (317 MB, likely
  large vendored/model content) scoring as maximally "substantive" on
  size alone. Log-scaling caps the damage but doesn't eliminate it.
  Would need content inspection to fix, out of scope for a
  zero-additional-request Stage 1.
- The optional relevance boost cannot rescue a repository that Stage 1
  scores as trivial (see `Pneumonia-Detection-Ai` above) — it can only
  re-rank *among* repositories Stage 1 already considers reasonably
  substantive. Whether that's the right behavior for the eventual
  Stage 2 (once a real Job Requirement Parser exists) is an open
  product question, not resolved here.
- Organization-owned work remains invisible at the ranking stage too
  (`jph00`'s top-ranked personal repos are smaller side projects, not
  his `fastai`-org work) — consistent with, not a new instance of, the
  blind spot already documented in Milestone 4.5 and
  `docs/design/MILESTONE_5A_JOB_MATCHING_DESIGN.md`.
- `topics` is parsed and available but not used as a Stage-1
  substantiveness signal (many genuinely substantial repos never set
  topics) — only consulted for the optional Stage-2 boost. Not
  observed populated on any repository across the 7 validation
  accounts in this pilot-scale sample.

**Files changed:**
- `src/gitscore/github/parser.py` — added `parse_repo_summary()`
  (additive; `parse_repo()`/`parse_languages()` unchanged).
- `src/gitscore/ranking/__init__.py`, `config.py`, `rank.py` — new package.
- `scripts/rank_user_repos.py` — new manual-inspection script.
- `tests/test_repo_summary_parsing.py`,
  `tests/test_repository_ranking.py` — new, 26 tests, all synthetic
  fixtures, no network calls.
- `docs/design/MILESTONE_5A_JOB_MATCHING_DESIGN.md` — Part 11 annotated
  with the approved N=15 default and a pointer to this validation.
- `docs/ARCHITECTURE.md` — new §13 documenting the ranking module.
- This changelog entry.

**Risks/limitations:** see "Known limitations" above. Additionally: the
formula's weights (`RankingWeights` defaults) are a reasoned starting
point, not calibrated against labeled "this repo is/isn't substantive"
ground truth — there is no such ground truth yet. `reference_time`
defaults to wall-clock "now," so repeated runs on the same account over
time will legitimately reorder repositories as recency decays; this is
intended, not a bug, but callers needing byte-for-byte reproducibility
across time must pass an explicit `reference_time`.

**How to test:** `pytest tests/test_repository_ranking.py
tests/test_repo_summary_parsing.py -v` (26 tests, synthetic fixtures,
no network/token required). Manual inspection:
`python scripts/rank_user_repos.py <username> --top 15`.

## 2026-09-08 — Milestone 4: Clean Dataset V1 infrastructure

**What changed:**

New package `src/gitscore/dataset/` — the infrastructure to turn persisted
`ProfileFeature` snapshots into a clean, reproducible, one-row-per-user
Pandas dataset. **No CatBoost, no UI, no scoring-rubric change, no
org-repo analysis, no database-schema change, no real dataset collected.**

*Dataset contract (`dataset/schema.py`):*
- `FEATURE_COLUMNS` — 30 ordered feature names (23 numeric/count + 6
  boolean + 1 categorical), all sourced from `ProfileFeature`.
- `CATEGORICAL_FEATURE_COLUMNS = ["most_used_language"]`,
  `BOOLEAN_FEATURE_COLUMNS` (the six `has_*`), `NUMERIC_FEATURE_COLUMNS`
  (the rest). The three sets partition `FEATURE_COLUMNS` exactly
  (asserted by a test).
- `TARGET_COLUMN = "readiness_score"`; `DATASET_COLUMNS = FEATURE_COLUMNS
  + [TARGET_COLUMN]` is the exact CSV column order.
- `EXCLUDED_COLUMNS` — a `{db.column: reason}` map documenting every
  deliberately-omitted column: `profile_features.id`,
  `profile_features.user_id`, `profile_features.collected_at`,
  `users.id`, `users.github_username`, `users.name`, `users.followers`,
  `users.public_repos`, `users.collected_at`. Identifiers + timestamps +
  collection metadata + two `users` columns that are not rubric inputs in
  V1.
- `INTERNAL_ONLY_COLUMNS` — `snapshot_id`, `user_id`, `github_username`,
  `collected_at`: pulled by the builder for row-selection/diagnostics
  only, dropped before the frame is returned. `validate_frame` rejects
  any of them appearing in a dataset frame.
- `validate_frame(df, *, allow_empty=True)` — exact column set+order,
  no forbidden identifier/timestamp columns, no nulls in required
  columns, numeric columns numeric, boolean columns in {True,False,0,1},
  categorical column all-strings. Raises `DatasetSchemaError` (shape) or
  `DatasetValidationError` (values) from `dataset/exceptions.py`.

*Versioning (`dataset/schema.py`, lightweight — constants, not a schema
change):*
- `DATASET_VERSION = "v1"` — bump when a row's *meaning* changes.
- `FEATURE_SCHEMA_VERSION = 1` — bump on any change to `FEATURE_COLUMNS`.
- `SCORING_RUBRIC_VERSION = 1` — mirrors `scoring/readiness.py`; bump only
  when weights/thresholds/ladders change. `readiness_score` (the target)
  is not comparable across rubric versions.
- All three are written into the export's `.meta.json` sidecar and shown
  in the quality report. The DB is unchanged; the documented process
  when the rubric changes is "bump `SCORING_RUBRIC_VERSION`, re-collect,
  do not mix". Adding a real `scoring_rubric_version` DB column stays a
  future option (see `docs/ML_NOTES.md` §4) — deliberately not done here.

*Dataset builder (`dataset/builder.py`):*
- `build_dataset(session_factory=SessionLocal) -> DatasetBuildResult`.
  Explicit SQLAlchemy `select(...)` naming every column (feature, target,
  plus the four internal-only columns) — **no `SELECT *`, no post-hoc
  column dropping.**
- One row per user = the **latest valid snapshot**: sort by
  `(collected_at, snapshot_id)` ascending, `groupby("user_id").tail(1)`.
  The `snapshot_id` tie-break makes selection deterministic even when two
  snapshots share a `collected_at`.
- Deterministic dataset row order: ascending `github_username`, applied
  before `github_username` is dropped.
- Detects duplicate users (snapshots-per-user > 1) and reports the count
  + usernames — does not error on them (that's the point of "latest
  snapshot").
- `_coerce_dtypes` normalises: numerics via `pd.to_numeric(errors=raise)`,
  booleans to `bool`, `most_used_language` to pandas `category` over
  strings with `""` for any missing value (never null).
- Runs `validate_frame` on its own output; a malformed frame raises
  rather than returning silently-broken data.
- Empty database → empty-but-valid frame (right columns, zero rows), not
  an error.
- `DatasetBuildResult` carries `frame`, `raw_snapshot_count`,
  `selected_row_count`, `unique_user_count`, `duplicate_user_count`,
  `duplicate_usernames`, and the three version properties.

*Quality report (`dataset/report.py`):*
- `dataset_quality_report(result) -> dict` — versions, unique users,
  rows before/after latest-snapshot selection, duplicate users, per-column
  missing-value counts, feature dtypes, target distribution
  (min/max/mean/std/quantiles + a fixed 0–100 by-tens histogram),
  `describe()` numeric summary, `most_used_language` value counts
  (including the `""` sentinel), and constant / near-constant features
  (dominant value share ≥ 0.95).
- `format_report(report) -> str` — human-readable text block for the CLIs.
- Empty-dataset-safe (distribution sections collapse to `{}`).

*Deterministic export (`dataset/export.py`):*
- `export_dataset(result_or_frame, path=None, *, write_meta=True) -> Path`.
  Writes `data/processed/gitscore_dataset_v1.csv` by default: fixed column
  order, fixed row order, `\n` line endings, `index=False`. Two exports of
  the same database are byte-identical (tested).
- `<name>.meta.json` sidecar: the three versions, row grain, source,
  column lists, counts, and a `built_at_utc` timestamp. The timestamp
  makes the *meta* file non-deterministic on purpose; the CSV is the
  reproducible artifact. `write_meta=False` skips it.
- Both land under `data/processed/` (already gitignored).

*Collection input (`dataset/collection_input.py`, replaces the hardcoded
list in `scripts/collect_dataset.py`):*
- `parse_usernames(text)` / `load_username_file(path)` — one username per
  line; ignore blank lines and `#` comment lines; strip inline `#…`
  comments; de-duplicate case-insensitively (first spelling wins);
  preserve first-occurrence order. `UsernameFileError` (clear message
  pointing at the example file) when the file is missing.
- `scripts/collect_dataset.py` — rewritten. Reads
  `data/collection/usernames.txt` (or `argv[1]`), continues across
  ordinary per-user failures, prints per-user status + a final
  succeeded/failed/attempted/elapsed summary + a failure list. Exit code
  0 (all ok) / 2 (finished with failures) / 1 (could not start). Only
  exception *type + message* is printed — never the token (and
  GitHubClient messages carry URL/status, not credentials; a test pins
  this).
- `data/collection/usernames.example.txt` — committed template
  (comments only, no real list). `data/collection/usernames.txt` is
  gitignored.

*New scripts:*
- `scripts/build_dataset.py` — build + report + export (`argv[1]`
  optional output path). Exits 1 with "nothing exported" on an empty DB.
- `scripts/dataset_report.py` — report only, no file writes.
- `scripts/show_dataset.py` — unchanged; still a raw `SELECT *` *inspection*
  tool, explicitly **not** the dataset path (documented in
  `docs/PIPELINE.md` Stage 6).

*Tests (`tests/`, +65, suite 166 → 231, all passing, still offline):*
- `tests/conftest.py` — added `PROFILE_FEATURE_DEFAULTS`, a `SnapshotDB`
  helper, and the `snapshot_db` fixture: a throwaway per-test SQLite
  database with the real `User`/`ProfileFeature` schema and an
  `add_snapshot(username, *, collected_at=None, **feature_overrides)`
  method. Never touches `data/gitscore.db`.
- `tests/test_dataset_schema.py` (17) — contract shape (partition
  complete & disjoint, no id/timestamp columns, excluded-columns map)
  and every `validate_frame` path (missing/extra/reordered column,
  identifier present, nulls, non-numeric, null categorical, `""`
  sentinel allowed, empty allowed/disallowed).
- `tests/test_dataset_builder.py` (17) — empty DB, latest-snapshot
  selection incl. `collected_at`-tie → `snapshot_id` tie-break, duplicate
  detection, deterministic ascending-username row order, repeated builds
  `assert_frame_equal`, exact column set/order, value round-trip from DB,
  **no identifier column leaks**, **no timestamp column leaks**,
  username only affects ordering, `most_used_language` preserved as
  `category`, `""` sentinel survives, builder validates its own output.
- `tests/test_dataset_export.py` (6) — CSV+meta written, header == schema
  columns, byte-for-byte determinism, LF endings, no identifier columns
  in the header, empty dataset → header-only CSV.
- `tests/test_dataset_report.py` (8) — empty-safe, before/after counts,
  target distribution, `""` in language distribution, constant vs
  near-constant flagging, dtype coverage, no missing values on clean
  data, formatter mentions versions.
- `tests/test_collection_input.py` (12) — blank lines, full-line and
  inline comments, case-insensitive dedup, order preservation, first-token
  fallback, empty input, `load_username_file` happy path + missing-file
  error, and that the committed example template parses to zero usernames.
- `tests/test_collect_dataset_script.py` (5) — continues across per-user
  failures + reports, all-success → exit 0, missing file → exit 1, empty
  list → exit 1, and the token is never printed.

*Docs:* this entry; `docs/ARCHITECTURE.md` §1/§11 + new §12;
`docs/PIPELINE.md` Stages 6/6b/9; `docs/ML_NOTES.md` new §8 (+ §4/§6/§7
cross-refs); `README.md` (dataset build/report commands, usernames.txt
input, CSV is a gitignored derived artifact).

**Why:** first step of the ML track from `CLAUDE.md`'s priority order —
"robust dataset creation" + "ML dataset preparation" — building the
reproducible pipeline *before* any real collection or model training, so
the dataset has a defined contract, a leakage policy, versioning, and
quality tooling from row one.

**Risks / limitations:**
- **`SCORING_RUBRIC_VERSION` is a code constant, not a DB column.**
  Nothing stamps the rubric version onto historical rows; the "don't mix
  rubric versions" policy is enforced by discipline + re-collection, not
  by the data. Adding the column remains the documented upgrade
  (`docs/ML_NOTES.md` §4) if the rubric starts changing.
- The builder trusts `ProfileFeature`'s `nullable=False` columns to
  actually be non-null (SQLite enforces this). `validate_frame` is the
  backstop if that ever changes; the null-path test injects the failure
  via a monkeypatched coercion step rather than a real null (SQLite won't
  store one).
- Pre-existing `datetime.utcnow` `DeprecationWarning`s (from
  `db/models.py`, unchanged this milestone) now surface in the new
  dataset tests' output. Not an error; not fixed here (would touch the DB
  layer, out of scope).
- `data/processed/gitscore_dataset_v1.csv` + `.meta.json` are the only
  outputs; both are gitignored. No dataset was actually built from real
  GitHub data — the dev DB still holds only the 13 pre-fix rows
  (`docs/ML_NOTES.md` §7).
- CSV floats use pandas' default `repr` (round-trips, deterministic on
  CPython); no fixed decimal formatting was imposed.

**How to test it:**
```
cd gitscore-ai
pytest
```
Expected: 231 passed.

Smoke test (no real collection):
```
python scripts/dataset_report.py            # read-only, against data/gitscore.db
python scripts/build_dataset.py             # writes data/processed/gitscore_dataset_v1.csv (gitignored)
```

---

## 2026-08-31 — Milestone 3: Project hygiene, pipeline testing, pre-ML release readiness

**What changed:**

*Dependency / packaging (see docs/ARCHITECTURE.md §10):*
- `pyproject.toml` — added `dependencies = ["requests>=2.31",
  "python-dotenv>=1.0", "SQLAlchemy>=2.0", "pandas>=2.0"]` (floor
  versions, no upper-bound pins) and
  `[project.optional-dependencies] dev = ["pytest>=7.0"]`. Previously
  declared zero dependencies anywhere.
- `requirements.txt` — **removed**. It was a `pip freeze` dump from an
  unrelated ROS2 project (confirmed in the original audit), not this
  project's dependencies. Rather than regenerate it as a second,
  easily-stale copy of what `pyproject.toml` now declares, it was
  deleted outright — `pyproject.toml` is the single source of truth.
  Documented decision (see "Packaging decisions" below).
- Verified fresh-environment installability: `pip install -e .` and
  `pip install -e ".[dev]"` both resolved and succeeded (dry-run,
  against a real package index), and `pip wheel . --no-deps` produced a
  real wheel whose contents were inspected directly.

*Package structure / rename (see docs/ARCHITECTURE.md §1, §5, §10):*
- **Renamed `src/gitscore/feautures/` -> `src/gitscore/features/`.**
  Moved `activity.py`, `languages.py`, `ml.py`, `profile.py`,
  `quality.py`, `readme.py`; updated their imports
  (`gitscore.feautures.*` -> `gitscore.features.*`) in `profile.py` and
  in `src/gitscore/pipeline/analyze.py`; fixed the three
  `..._feautures` local-variable typos in `profile.py` to
  `..._features` while already editing that file; updated the two
  affected test files' imports
  (`tests/test_feature_extractors_current_behavior.py`,
  `tests/test_profile_module_dedup.py`, the latter also gaining a test
  that the old `feautures/` directory is gone); updated `CLAUDE.md`'s
  note about the misspelling; updated `docs/ARCHITECTURE.md`,
  `docs/PIPELINE.md`, `docs/ML_NOTES.md` current-state references (old
  changelog entries below are left as accurate history of what was true
  at the time, not rewritten). `feautures/deployment.py` (already
  documented as an empty, unused stub) was not carried over into the
  new directory — dropped as dead code. Verified via
  `grep -rn feautures` that only intentional historical references
  remain (docstrings/changelog entries describing the rename itself).
- Added `src/gitscore/features/__init__.py` and
  `src/gitscore/scoring/__init__.py` — both packages previously had
  none, unlike every other package in the tree (the one packaging
  fragility this milestone's fresh-install verification actually
  exercises — see "Packaging decisions" below).
- Removed two other empty, `git`-untracked, unreferenced placeholder
  directories left over from initial project scaffolding:
  `src/gitscore/app/`, `src/gitscore/ml/`, `src/gitscore/nlp/`.
  Confirmed empty and unreferenced (`grep` across `src/`, `scripts/`,
  `tests/`, `docs/`, `CLAUDE.md`, `pyproject.toml`) before removal.

*Repository hygiene (see docs/CHANGELOG_DEV.md "Findings" below):*
- `.gitignore` — added `.pytest_cache/`, `build/`, `dist/`,
  `*.egg-info/`, SQLite journal/WAL/SHM sidecar patterns
  (`data/*.db-journal`, `-wal`, `-shm` and the `.sqlite*` equivalents),
  a forward-looking `models/`/`*.cbm`/`*.pkl`/`*.joblib` block for
  not-yet-existent CatBoost artifacts, and `.vscode/`/`.idea/`.
- `src/gitscore_ai.egg-info/` — **untracked** (`git rm --cached`) and
  deleted from the working tree. It was committed to git and stale
  (confirmed missing several real files); it's fully auto-regenerated
  by `pip install -e .` and now matched by the new `.gitignore` rule.
- `.env.example` — was empty (0 bytes); now documents `GITHUB_TOKEN`
  with the rate-limit rationale for setting it.
- Confirmed via `git log --all --diff-filter=A --name-only` that `.env`
  has never been committed, and via pattern grep across `*.py`/`*.md`/
  `*.toml`/`*.txt` that no hardcoded GitHub token is present anywhere
  in the repo. No secret values were printed while checking either.

*Scoring tests (see docs/PIPELINE.md Stage 4):*
- `tests/test_scoring_readiness.py` — **new**, 90 tests.
  `scoring/readiness.py` had zero dedicated tests before this. Covers
  the all-zero-features minimum (0), the documented 100-point maximum
  (including deliberately absurd input values, to confirm the total
  cannot exceed 100), category-scores-always-sum-to-total-score,
  determinism, every if/elif threshold boundary in all five category
  ladders, and three hand-computed representative low/medium/high
  profiles. **No scoring bug was found** and **no weights or
  thresholds were changed** — every category's maximum matches its
  documented weight exactly (ML 35 + Originality 20 + Documentation 15
  + Language/Tool 20 + Community 10 = 100), confirmed by both the
  per-category max tests and the all-categories-maxed-simultaneously
  test.
- `tests/conftest.py` — added `make_score_features()`.

*Pipeline tests (see docs/PIPELINE.md, docs/ARCHITECTURE.md §11):*
- `tests/test_analyze_user_pipeline.py` — **new**, 5 tests, mocking
  only the two boundaries `analyze_user()` actually crosses (GitHub via
  a fake `GitHubClient`, persistence via recording fakes for
  `save_user`/`save_profile_features`):
  - normal user, full pipeline, asserts the public result shape
    (`{"user", "features", "score", "time"}`) and that both boundaries
    were called with the right data;
  - zero-repository user completes cleanly with the documented
    zero/no-evidence values and a `0` total score;
  - a nonexistent user (`GitHubNotFoundError` from `get_user()`)
    propagates and **persists nothing** (`save_user`/
    `save_profile_features` both un-called);
  - one repo's languages/README fetch failing (Milestone 2 policy)
    still produces a complete profile with the repo included, at the
    `analyze_user()` level, not just unit-tested in `fetch_repo_data()`;
  - a `save_profile_features()` failure propagates instead of being
    swallowed into a result that looks successfully saved (`save_user`
    already committed by that point — documented limitation, not a bug,
    see `docs/PIPELINE.md` Stage 5).
  - (A rate-limit-during-processing scenario is already covered by
    Milestone 2's
    `tests/test_pipeline_repo_failure_handling.py::test_analyze_user_aborts_the_batch_when_a_worker_hits_a_rate_limit`
    and is not duplicated here.)
- `tests/conftest.py` — added `raw_repo()` (also now used by
  `tests/test_pipeline_repo_failure_handling.py`, replacing a duplicate
  local copy — same repo dict shape, no behavior change),
  `FakeGitHubClient`, `fake_github_client_factory()`, `FakeSavedUser`.

*Database snapshot semantics (see docs/ARCHITECTURE.md §7a,
docs/ML_NOTES.md §6) — reviewed, not changed:*
- `save_profile_features()` inserts a new `ProfileFeature` row on every
  `analyze_user()` call — no upsert, no unique constraint on `user_id`.
  Read as an intentional "timestamped historical snapshot" mechanism
  (each row is individually timestamped) that is currently
  **unexploited** — nothing queries "latest per user" anywhere yet.
- **No schema change made this milestone** (no `is_latest` flag, no
  unique constraint) — not required by an actual correctness bug, so
  deferred per instruction.
- **Policy defined for later:** the future dataset builder must select
  one row per `user_id` (max `collected_at`) *before* any statistics/
  split, not query `profile_features` unfiltered. Documented in full in
  `docs/ML_NOTES.md` §6, including a concrete illustration from the
  current dev database (see below).

*Old development data (see docs/ML_NOTES.md §7):*
- Inspected `data/gitscore.db` directly: 3 users, 13 `profile_features`
  rows. Confirmed **every row predates Milestones 1 and 2**:
  `description_coverage_ratio == 1.0` on all 13 rows (the Milestone-1
  bug signature) and `karpathy`'s row has `total_repos == 30` exactly
  (the Milestone-2 pagination-truncation signature). One user
  (`Jango1324`) accounts for 8 of the 13 rows (~62%) — a concrete,
  present-day illustration of the snapshot-overrepresentation risk
  above, not a hypothetical one.
- Documented clearly (`docs/ML_NOTES.md` §7) that none of these rows
  may be used in the clean ML dataset.
- **Did not delete or modify `data/gitscore.db`.** Recommendation only
  (exact commands given in `docs/ML_NOTES.md` §7: `rm data/gitscore.db`
  + `python scripts/init_db.py`), to be executed by whoever starts real
  dataset collection, not automatically by this milestone.
- **Real dataset collection was not started**, per explicit instruction.

*Developer workflow / README (see docs/ARCHITECTURE.md §10):*
- `README.md` — was empty (0 bytes); now covers what GitScore AI does,
  what the score means and explicitly does **not** mean (not a hiring
  prediction), current MVP architecture, setup (`python -m venv`,
  `pip install -e ".[dev]"`, `python scripts/init_db.py`), environment
  variables (`GITHUB_TOKEN`, optional/recommended, with rate-limit
  rationale), how to run single-user analysis and the batch/inspection
  scripts, how to run tests (`pytest`), and current project status
  (Milestones 1-3 done; dataset/CatBoost/UI/org-analysis not yet). No
  Docker, no marketing claims.

**Why:** This milestone's purpose was to make the GitHub → features →
scoring → database pipeline a clean, reproducible, well-tested
foundation before real dataset collection or CatBoost work begins —
explicitly scoped ahead of that work by instruction, with scoring
weights, feature definitions, the DB schema, org-contribution analysis,
and the UI all explicitly out of scope.

**Packaging decisions (explicit, per instruction to choose one and
document why):**
- *Dependencies:* declared in `pyproject.toml` rather than left
  implicit, with floor versions rather than exact pins — this is a
  library-style application, not a deployment artifact; exact pins
  belong in a lockfile generated from `pyproject.toml` if/when a
  reproducible deployment environment is actually needed, not
  hand-maintained in `pyproject.toml` itself.
- *`requirements.txt`:* removed rather than regenerated or replaced
  with a minimal version. `pyproject.toml` already fully declares
  runtime + dev dependencies; a second file duplicating that
  information is pure drift risk with no offsetting benefit at this
  project's current size — and drift is exactly how the file ended up
  as an unrelated ROS2 dump in the first place. If a pinned lockfile
  becomes genuinely necessary later (CI reproducibility, deployment),
  generate one from `pyproject.toml` at that time.
- *`feautures` -> `features` rename:* done now rather than deferred,
  per the instruction's own framing ("before ML/UI layers create more
  imports") — the rename touched exactly 6 source files' imports, 2
  test files, and current-state doc references; that blast radius only
  grows once CatBoost feature-engineering code and a UI layer start
  importing from this package too. No compatibility shim was added
  (none was needed — this is a private internal package, not a
  published API with external consumers).

**Tests added/changed:** suite grew from 71 to 166 tests (90 scoring +
5 pipeline, plus `raw_repo()`/`FakeSavedUser()`/`fake_github_client_factory()`
sharing eliminating one small duplicate), all passing, still no network
access, GitHub token, or real database writes required.

**Risks / limitations:**
- The old dev database (`data/gitscore.db`) still exists on disk with
  its 13 pre-fix rows — it was deliberately not touched (see above).
  Anyone running `scripts/show_dataset.py` before it's cleaned up will
  see that stale data.
- No schema change was made for DB snapshot semantics, so nothing
  currently *enforces* the "latest row per user" dataset policy — it is
  a documented convention the future dataset-builder script must
  actually implement, not something the database guarantees on its own.
- `pyproject.toml`'s dependency floors were chosen from what's
  currently installed/working, not exhaustively tested against their
  literal minimum-declared versions (e.g. `requests>=2.31` was not
  separately verified to work with exactly 2.31.0) — low risk for this
  project's usage, but worth knowing if a very old dependency set is
  ever forced.
- The `feautures` -> `features` rename is a pure rename with identical
  behavior — verified by the full test suite passing and by
  `grep -rn feautures` returning only intentional historical
  references — but it was not exercised against a real GitHub API call
  in this session (see "release-readiness checks" below for what was
  and wasn't run).

**How to test it:**
```
cd gitscore-ai
pytest
```
Expected: 166 passed.

---

## 2026-08-31 — Milestone 2: GitHub data collection reliability

**What changed:**
- `src/gitscore/github/exceptions.py` — **new**. `GitHubError` (base),
  `GitHubNotFoundError` (genuine 404), `GitHubRateLimitError` (carries
  `reset_at`/`retry_after` when GitHub supplied them), `GitHubRequestError`
  (non-retryable / retry-exhausted failures, carries `status_code`).
  Replaces the bare `Exception(f"... {status_code}")` used for every
  failure mode previously.
- `src/gitscore/github/client.py` — rewritten around one internal
  `_get()` request helper used by all four public methods:
  - **Pagination**: `get_repositories()` now loops `page=1,2,...` with
    an explicit `per_page=100` until a page comes back shorter than
    `per_page` (i.e. it's the last page), concatenating pages in fetch
    order. A `max_pages=50` safety cap (~5000 repos) raises
    `GitHubRequestError` instead of looping forever if GitHub ever kept
    returning full pages indefinitely.
  - **Timeouts**: every request now passes `timeout=` (default `10.0s`,
    centralized as `DEFAULT_TIMEOUT_SECONDS`, configurable per
    `GitHubClient(timeout=...)`).
  - **Retries**: connection errors, timeouts, and `{500, 502, 503, 504}`
    responses are retried with bounded exponential backoff
    (`0.5s, 1s, 2s`, capped at `8s`; `DEFAULT_MAX_RETRIES=3` → up to 4
    attempts total). 404s and other 4xx codes are never retried. The
    sleep function is injectable (`sleep_func=`) so tests never wait
    through real backoff delays.
  - **Rate limits**: a 403 with `X-RateLimit-Remaining: 0`, a 403 with
    `Retry-After`, or a plain 429 now raises `GitHubRateLimitError`
    immediately (never retried, never waited-out automatically) with
    `reset_at`/`retry_after` populated from GitHub's headers when
    present. A plain 403 with none of those signals (e.g. permission
    denied) still raises `GitHubRequestError`, not a rate-limit error.
  - Removed the dead header-construction code (three methods built an
    `Accept`/`X-Requested-With` dict then immediately discarded it with
    `headers = {}`) — headers are now built once in `_headers()` and
    actually sent (`Accept: application/vnd.github+json`).
  - `get_repository_readme()`'s existing "404 → `None`" behavior for a
    missing README is preserved (now implemented by catching the new
    `GitHubNotFoundError` internally).
- `src/gitscore/pipeline/analyze.py`:
  - **Per-repo failure policy**: `fetch_repo_data()` now treats a
    repo's languages/README fetch as optional metadata — if it raises
    `GitHubRequestError`/`GitHubNotFoundError` after the client's own
    retries are exhausted, that one repo degrades gracefully
    (`languages={}` / `readme=None`) and the repo is still included, so
    one flaky repo no longer fails the whole profile analysis. A
    `GitHubRateLimitError` is **not** swallowed — it propagates and
    aborts the batch, since continuing would just burn more of an
    already-exhausted rate-limit budget for degraded data. `get_user()`
    and `get_repositories()` failures still propagate uncaught, per
    "user fetch failure → profile cannot be analyzed."
  - **Thread-safety**: each `ThreadPoolExecutor` worker thread now gets
    its own lazily-created `GitHubClient` (`threading.local()`) instead
    of all 8 workers sharing one `requests.Session`. `requests.Session`
    is not documented as safe for concurrent use; this removes that
    assumption entirely while keeping most of the connection-reuse
    benefit (each worker thread still reuses its own session across
    every repo it handles). `max_workers=8` (now `MAX_REPO_WORKERS`) is
    unchanged — already conservative, kept for the same batch
    performance as before.
  - Repo fetches are now submitted via `executor.submit()` (instead of
    `executor.map()`) so that on a fatal error (a rate limit) every
    not-yet-started future is cancelled instead of letting the whole
    queued batch run first — `executor.map()` would still drain the
    queue before propagating the exception, wasting more of an
    already-exhausted rate-limit budget. Result order is unchanged
    (`.result()` is read back in submission order).
  - Added concise `logging` (page-fetch progress at `debug`, retry/
    degradation notices at `warning`/`info`) — no request headers,
    tokens, or full request objects are ever logged.
- `tests/test_github_client_current_behavior.py` — the three tests that
  intentionally pinned the old bugs (single-page fetch, no timeout, no
  rate-limit typing) are rewritten to assert the corrected behavior.
- `tests/test_github_client_reliability.py` — **new**, 21 tests:
  pagination (fewer-than-one-page, exactly-one-full-page,
  multiple-pages, empty-list, infinite-loop guard), timeout
  configuration, retry/backoff (connection error, timeout, 5xx, bounded
  exhaustion, backoff growth/cap, 404-not-retried, 422-not-retried),
  and rate limits (primary, secondary/`Retry-After`, `429`, plain-403
  is-not-a-rate-limit).
- `tests/test_pipeline_repo_failure_handling.py` — **new**, 6 tests:
  `fetch_repo_data()` graceful degradation and rate-limit propagation,
  one-`GitHubClient`-per-worker-thread, and batch-abort-on-rate-limit
  at the `analyze_user()` level.
- `tests/conftest.py` — added shared `FakeResponse`, `ScriptedSession`
  (records calls, returns a pre-programmed sequence of
  responses/exceptions), and `RecordingSleep` fakes used across all
  three GitHub-client/pipeline test files.

**Why:** These were the pagination/timeout/retry/rate-limit/concurrency
findings from the 2026-08-30 audit, scoped as Milestone 2 by explicit
instruction. Feature definitions, scoring weights, the DB schema, the
UI, and CatBoost were explicitly out of scope and untouched.

**Repository-level failure policy (explicit decision):**
| Failure | Behavior |
|---|---|
| `get_user()` fails (any reason) | Propagates — profile cannot be analyzed without knowing who the user is. |
| `get_repositories()` fails (any reason) | Propagates — profile cannot be analyzed without knowing what repos exist. |
| One repo's README is missing (404) | Expected condition — `readme=None`, repo still included. Unchanged from before. |
| One repo's languages/README fetch fails transiently, retries exhausted | Repo degrades gracefully (`languages={}`/`readme=None`), still included — logged at `warning`. |
| Any repo fetch hits a rate limit | Propagates immediately, aborts the whole `analyze_user()` call — not swallowed per-repo. |

**Tests added/changed:** suite grew from 46 to 70 tests, all passing,
still no network access or GitHub token required.

**Risks / limitations:**
- Pagination stops based on `len(page) < per_page`, not by parsing
  GitHub's `Link` header. This is simpler and equally correct given a
  fixed `per_page`, but relies on GitHub's documented default page-size
  behavior rather than an explicit "no more pages" signal.
- Retry backoff has no jitter — under concurrent worker threads hitting
  the same transient failure simultaneously, their retries could
  cluster instead of spreading out. Not addressed here; `max_workers=8`
  keeps the practical blast radius small.
- Even with future-cancellation on a rate-limit abort, futures **already
  running** when the rate limit is detected still complete (Python
  threads can't be interrupted mid-flight) — only not-yet-started queued
  futures are cancelled. With `max_workers=8` this bounds the worst-case
  extra wasted requests to a small constant, not the whole remaining
  batch.
- `GitHubClient(sleep_func=...)` is a real constructor parameter (not
  just a test seam) — production code always uses the default
  `time.sleep`; nothing changes there.
- **Dataset impact (see `docs/ML_NOTES.md` §5 update)**: any rows in
  `data/gitscore.db` collected before this fix reflect at most 30 repos
  per user (the old single-page bug) and may be missing users entirely
  where an unhandled rate limit or transient failure aborted collection
  partway through a batch. These rows must not be mixed with data
  collected after this fix without re-verification — no migration or
  backfill was performed (out of scope; database schema untouched).

**How to test it:**
```
cd gitscore-ai
.venv/Scripts/python.exe -m pytest tests/ -v
```
Expected: 70 passed.

---

## 2026-08-30 — Milestone 1: Feature correctness

**What changed:**
- `src/gitscore/feautures/quality.py` — fixed the description-coverage
  condition (`or` → `and` + blank-string check) and added a
  `total_repos == 0` guard so `average_stars`/`average_forks`/
  `description_coverage_ratio` return `0` instead of raising
  `ZeroDivisionError`.
- `src/gitscore/feautures/languages.py` — guarded `max(all_languages,
  ...)` against an empty dict; `most_used_language` now returns `""`
  (sentinel for "no language data") instead of raising `ValueError`.
  Also fixed the `most_used_langauge` variable-name typo internally.
- `src/gitscore/feautures/ml.py` — rewrote keyword matching from raw
  `word in text` substring search to word-boundary-aware regex
  (`ML_KEYWORDS` list unchanged; matching strategy changed).
- `src/gitscore/feautures/profile_features.py` — **deleted**. Confirmed
  unused via `grep -rn "profile_features" --include="*.py" .` (only
  hits were the unrelated `profile_features` DB table name and
  function name, no actual import of the module). See "Correction"
  below.
- `tests/test_feature_extractors_current_behavior.py` — rewritten:
  tests that previously pinned the three bugs above now assert the
  fixed behavior; new tests added for the empty-repo-list sentinel
  values, every entry in `ML_KEYWORDS` matching as a standalone token,
  and hyphen/underscore-separated tokens still matching.
- `tests/test_profile_module_dedup.py` — new, guards against
  `profile_features.py` reappearing and confirms
  `feautures/profile.py` still works as the pipeline's actual import
  target.
- `docs/ARCHITECTURE.md`, `docs/PIPELINE.md`, `docs/ML_NOTES.md` —
  updated to describe the fixed behavior instead of the bugs (see
  each file's diff for specifics).

**Why:** These were the top correctness findings from the 2026-08-30
audit (below) that directly affect what the GitScore measures. Fixing
them was scoped as Milestone 1 by explicit instruction — no pagination,
retries, CatBoost, UI, or deployment work included.

**Previous incorrect behavior → new behavior:**
| Area | Before | After |
|---|---|---|
| `description_coverage_ratio` | Always `1.0` (the `or` condition was tautologically true) | Reflects the actual fraction of repos with a non-blank description |
| `extract_quality_features([])` | Raised `ZeroDivisionError` | Returns all-zero feature dict |
| `extract_language_features([])` (or repos with no language data) | Raised `ValueError` from `max()` on an empty dict | Returns `most_used_language=""`, all counts `0` |
| `ml.py` keyword matching | Raw substring search; `"ai"` matched inside "container"/"explain"/"email", `"ml"` matched inside "html" | Word-boundary-aware regex; only matches the keyword as a standalone token (space/hyphen/underscore/punctuation-delimited) |
| `feautures/profile_features.py` | Existed, unused, previously (inaccurately) documented as a byte-identical duplicate of `profile.py` — it was actually empty | Deleted |

**Correction to the prior audit entry:** the 2026-08-30 audit below
described `profile_features.py` as "byte-identical" to `profile.py`.
Re-reading the file while implementing this fix showed it was actually
0 bytes on disk (and 0 bytes in the git-tracked version — confirmed via
`git diff --stat` showing `0 insertions, 0 deletions` for its
deletion). The original read that reported matching content was
inaccurate; the file's true state was empty, not duplicated. It has
been removed regardless, since it was confirmed unused either way.

**Tests added/changed:** suite grew from 12 to 46 tests, all passing.
See `tests/test_feature_extractors_current_behavior.py` and
`tests/test_profile_module_dedup.py`.

**Risks / limitations:**
- Any rows already in `data/gitscore.db` (`profile_features` table)
  were collected under the old buggy code —
  `description_coverage_ratio` and `ml_repository_count`/
  `ml_keyword_total` in those historical rows are not comparable to
  data collected after this fix. No migration or backfill was
  performed (out of scope for this milestone; database schema was not
  touched, per instructions).
- `scoring/readiness.py` was **not modified** — score weights and
  thresholds are unchanged, as instructed. Scores computed from
  corrected features will differ from scores computed from the old
  buggy features for the same GitHub profile (e.g. a profile with a
  false-positive "html" ML match will now score lower on ML
  Experience), which is the intended effect of fixing the bug, not a
  regression.
- Pagination, retries/timeouts, CatBoost, and UI/deployment work were
  explicitly out of scope and remain exactly as described in the prior
  audit.

**How to test it:**
```
cd gitscore-ai
.venv/Scripts/python.exe -m pytest tests/ -v
```
Expected: 46 passed.

---

## 2026-08-30 — Full engineering audit (no production code changed)

**What changed:** No behavior in `src/gitscore/` was modified. Added:
- `docs/ARCHITECTURE.md`, `docs/PIPELINE.md`, `docs/ML_NOTES.md` (this
  file was previously created but empty — filled in for the first time)
- `tests/conftest.py`, `tests/test_feature_extractors_current_behavior.py`,
  `tests/test_github_client_current_behavior.py` — 12 characterization
  tests, all passing against the current codebase, no network access
  required
- `pytest` installed into `.venv` (not yet declared in `pyproject.toml`
  or `requirements.txt` — see ARCHITECTURE.md §10)

**Why:** Requested full audit of the repository before any rewrite
work begins, per the user's instructions and `CLAUDE.md`'s Code Change
Workflow ("inspect relevant files, explain the current architecture,
identify issues, propose a short plan" before implementing).

**Files affected:** `docs/ARCHITECTURE.md`, `docs/PIPELINE.md`,
`docs/ML_NOTES.md`, `docs/CHANGELOG_DEV.md` (all new/filled-in);
`tests/conftest.py`, `tests/test_feature_extractors_current_behavior.py`,
`tests/test_github_client_current_behavior.py` (new). No files under
`src/` or `scripts/` were modified.

**How the new logic works:** N/A — no new production logic. Tests are
pure characterization tests: they call existing extractor functions
with synthetic repo dicts (see `tests/conftest.py::make_repo`) and a
fake `requests.Session` substitute for `GitHubClient`, and assert on
the *current* (including buggy) behavior, to make audit findings
independently verifiable and to catch accidental behavior changes
during future refactors.

**Risks / limitations:**
- This audit is based on static reading of the code plus offline tests
  against synthetic data. No live call to the GitHub API was made, so
  live-only behaviors (actual rate-limit response headers, actual
  `Link` header pagination format) are described from GitHub's
  documented API contract, not from an observed live response.
- `src/gitscore/github/client.py` has one **pre-existing uncommitted**
  change (`git diff` shows an added, unused `import time` on line 4) —
  present before this audit started, not introduced by it, left as-is.
- Two files (`.env.example`, `README.md`) were confirmed empty (0
  bytes) but intentionally left untouched — writing user-facing
  onboarding docs and an env template is scoped as implementation work
  for the roadmap below, not part of a read-only audit.

**How to test it:**
```
cd gitscore-ai
.venv/Scripts/python.exe -m pytest tests/ -v
```
Expected: 12 passed. Each test's docstring explains which specific
finding (in ARCHITECTURE.md / PIPELINE.md / ML_NOTES.md) it verifies.

**Findings summary (see the three docs above for full detail):**
1. `quality.py:9` description-coverage condition (`or` instead of
   `and`) makes `description_coverage_ratio` always `1.0` — BUG
2. `quality.py`/`languages.py` crash on an empty repo list
   (`ZeroDivisionError`/`ValueError`); `readme.py`/`activity.py` guard
   the same case — inconsistent, crashes `analyze_user()` for brand-new
   accounts — BUG
3. `ml.py` keyword matching is unbounded substring search
   ("ai" inside "container", "ml" inside "html") — false positives
   inflate the ML Experience score (35/100 weight) — misleading score
4. `feautures/profile.py` and `feautures/profile_features.py` are
   byte-identical duplicate files; `profile_features.py` is dead code
   — duplication
5. `github/client.py`: no pagination (`get_repositories` fetches page 1
   of 30 only), no `timeout=`, no retries, no rate-limit-aware handling,
   generic `Exception` for every failure mode, and dead
   header-construction code (`headers = {}` overwrites a built dict in
   3 methods) — correctness + robustness
6. `requirements.txt` is a `pip freeze` dump from an unrelated ROS2
   project, not this project's dependencies; `pyproject.toml` declares
   zero runtime dependencies — dependency-configuration gap
7. `src/gitscore_ai.egg-info/` (a build artifact) is committed to git
   and is stale relative to the current source tree
8. `scripts/collect_dataset.py:23` references a loop variable outside
   the loop — `NameError` risk / misleading batch-summary output
9. Rule-based `readiness_score` is a deterministic closed-form function
   of the stored feature vector; training CatBoost on it will primarily
   reproduce the rubric, not predict real-world hiring success — see
   `docs/ML_NOTES.md` §3
10. Org-owned-repository blind spot: only user-owned repos are fetched,
    systematically undercounting candidates whose ML work lives in an
    organization's GitHub — see `docs/ML_NOTES.md` §5

**Next step:** see the roadmap delivered alongside this audit (5
milestones, ordered) — no implementation has started; this entry will
be followed by a new entry per milestone once work begins, per
`CLAUDE.md`'s documentation requirement.
