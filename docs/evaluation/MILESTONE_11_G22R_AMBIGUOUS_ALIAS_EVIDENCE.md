# Milestone 11-G22-R — Ambiguous alias and README evidence audit (research)

**Status:** research and evaluation only.

- **No production code changed:**
  - parser `job_description_parser:v15`;
  - scoring `github_evidence_alignment:v2`;
  - matcher `requirement_matcher:v1`;
  - README extractor `readme:v4`;
  - registry, other extractors, API and frontend all unchanged.
- **No LLM call.**
- **Committed as a research-only commit** ("test: evaluate ambiguous alias README evidence") after authorization. The DEV
  and EVAL freezes are registered in the G14 manifest at that commit with their original freeze-time hashes
  (17 → 19 entries; the previous 17 are unchanged). Their freeze records keep their freeze-time note ("NOT registered …
  pending authorization"), which was true when they were written.

**Research contract (what this milestone does and does not establish):**

- A README mention is **not** proof of demonstrated technology use.
- Current production (`readme:v4` + matcher v1 + scoring v2) **does** let README-only evidence produce a counted
  SUPPORTED requirement, including from ordinary English.
- Policy D **reduces but does not eliminate** false SUPPORTED (DEV 21 → 5, EVAL 20 → 7). Its job side **loses a genuine
  React recognition** (G21-n10), and its README side still lets some ordinary English through.
- Policy R (README-only insufficient) **substantially reduces genuine README evidence coverage** (9/14 and 8/12; 47 of
  126 real 8c README items).
- Job-side and README-side aliases need **source-specific** policies.
- G19 capability relies on the existing README alias pathways. Removing or restricting registry aliases could
  incorrectly change score eligibility.
- **No production change, scoring-version change or matcher-version change has been implemented.** Every fix in §9 is a
  proposal, not deployed behaviour.
- All results come from self-authored synthetic controls and previously inspected fixtures, not independent prevalence
  estimates.

**Evidence sources and what can be claimed from them:**

| Source | Status |
|---|---|
| DEV / EVAL controls (`evaluation/m11g22r/`) | Synthetic and written by the same researcher who designed the policies, so **not independent validation**. EVAL is only weakly held out. |
| Frozen 8c fixtures | Real public README text. Measured here as a historical regression check, not as a prevalence estimate. |
| Private postings (62) | Inspected before, job side only. Reported as integer counts. |

## 1. Baseline (verified)

- HEAD = `origin/main` = `9cfe17accdded672ec51d31dcc64bf8fac791a7d` on `main`.
- Parser v15 (G22-Q active), scoring v2.
- Backend 2345 passed / 13 skipped / 18 xfailed; frontend 53.
- 17 G14 freezes; the 18 private/untracked M11 entries preserved.

## 2. The two pipelines and what they share

**One alias table, one matching primitive, four consumers.** `TechnicalConcept.readme_safe_aliases()` (registry metadata) and
`concepts.matching.alias_pattern()` (case-insensitive word-boundary regex), resolved by
`select_longest_overlapping_matches()`, are used identically by:

| Consumer | File | Extra context it applies | Earliest irreversible point |
|---|---|---|---|
| Job-description concept recognition | `jobs/parsing/concepts.py::find_concept_mentions` | G21 admission (claim level), G22-Q equivalence (OR level); **no usage check per occurrence** | `parser._requirements_from_claim` builds the `JobRequirement` with that `concept_id` |
| README evidence | `evidence/extraction/readme.py::evidence_from_readme` | 8D.3 attribution filter only: section-heading denylist + negation/roadmap adjacency cues; **no usage check** | the `Evidence(concept_id=…, MODERATE)` item; the profile pools it per concept with no alias or usage provenance beyond the snippet |
| Repository selection | `ranking/job_relevance.py` | repository name, description and topics only | which repositories are analysed (selection, not evidence) |
| G19 capability | `evidence/capability.py` | `README_MENTION` pathway exists iff the concept has at least one README-safe alias | requirement eligibility for scoring v2 |

**Independent, structured extractors**, which never scan prose:

- `languages.py`: GitHub language-stat names through `resolve_concept`; WEAK/MODERATE above 5% of bytes.
- `dependency_evidence.py`: manifest package names through `resolve_concept`, using every alias including README-unsafe ones; STRONG.
- `docker.py`: file presence; STRONG.

**Matcher:** `matching.support.has_sufficient_evidence` needs one item at WEAK or above. One README mention (MODERATE) is
therefore always enough for **SUPPORTED**, and README evidence is not marked as weaker anywhere in the status.

**Scoring v2:** eligibility is decided per concept from capability, never per evidence item. A false README item is
counted exactly like a manifest declaration.

## 3. Measured production behaviour (BASE)

Real pipeline: an offline fixture client (`loaders.FakeCandidateGitHubClient`, the one 8c uses) feeds
`extract_candidate_evidence`, then the real parser, `match_job` and `assess_job`.

| | DEV (40) | EVAL (36) |
|---|---|---|
| False README extractions (ordinary English) | 18 (17 errata-adjusted) | 16 |
| README mentions without demonstrated use, extracted | 3 | 4 |
| Genuine README evidence recall | 14/14 | 12/12 |
| False job concepts | 7 | 5 |
| **False SUPPORTED** (counted) | **21** | **20** |
| … caused by false README extraction | 14 | 14 |
| … caused by a false job concept | 4 | 3 |
| … caused by a genuine mention without use | 3 | 3 |
| True SUPPORTED | 12 | 11 |
| False evidence from language/manifest/Docker | 0 | 0 |

**Confirmed false README evidence.** Each example below became a SUPPORTED, counted requirement scoring 100 against the
matching probe requirement:

| Alias | Example sentence | Concept |
|---|---|---|
| react | "react quickly", "acids react with metals" | `framework.react` |
| express | "express their opinion", "express trains" | `framework.express` |
| swift | "a swift CSV parser", "swift and swallow sightings" | `language.swift` |
| rust | "rust stains", "free of rust" | `language.rust` |
| ruby | "my cat, Ruby", "Ruby, Sapphire" | `language.ruby` |
| shell | "every shell you find", "shell length" | `language.shell` |
| torch | "pass the torch", "tent, torch, stove" | `ml.framework.pytorch` |
| flask | "beaker and flask" | `framework.flask` |
| pandas | "red pandas", "giant pandas" | `data.library.pandas` |
| python | "a ball python" | `language.python` |
| java | "Java coffee bar" | `language.java` |

**Paired matrix (BASE):**

| Cell | Case | Outcome |
|---|---|---|
| 1 | correct job + genuine evidence | SUPPORTED (correct) |
| 2 | correct job + incidental English | **false SUPPORTED** ×3 |
| 3 | incorrect job + genuine unrelated evidence | **false SUPPORTED** ×2 (e.g. "express ideas" + an Express API repository) |
| 4 | incorrect job + incidental README | **false SUPPORTED** ×3 |
| 5 | ambiguous in both | **false SUPPORTED** ×2 |
| 6 | README + manifest | SUPPORTED (correct) |
| 7 | README + language statistics | SUPPORTED (correct) |
| 8 | repeated mentions across repositories | **false SUPPORTED**: still one requirement; deduplication is per concept |
| 9 | negative descriptions ("Unlike Rust", "Express is not used") | NOT_OBSERVED (correct): the 8D.3 cues work |
| 10 | documentation mention without use | **SUPPORTED** (evidentiary gap) |

The 8D.3 cues do not cover "a Rust port would be a fun future project", "inspired by React", "bindings for Rust can be
generated", "works with React, Vue or Svelte" or "notes comparing React and Vue". All of these produce SUPPORTED.

## 4. Freezes (G14 portable; registered at the research commit)

| File | sha256 (LF canonical) | Controls |
|---|---|---|
| `alias_evidence_controls_dev.json` | `b7c42f5904f4191824083a5fa5175cdf5ec18ff16d5f871d77b04f3fc5bf2172` | 40 |
| `alias_evidence_controls_eval.json` | `15ae7d6951cafe3ce139e4266e5123c30459d104556237a41534f8c2f8999a81` | 36 |
| `policy_design_freeze.json` | policies `e0efd597…`, harness `bce3687f…`, G22 policies `58a582b7…` | — |

- **Label timing:** labels were frozen before any GitScore code ran on these texts. The policy design was frozen after
  DEV and before EVAL ran.
- **Design changes made on DEV before the freeze** (both recorded in the freeze file):
  - the README alias list for D (G22's 7 aliases plus python, java, flask, pandas);
  - D's README claim-of-use frames.
- **Erratum:** d22's frozen `mentioned` label omits a genuine "plain JavaScript". The control is not edited; reports give
  raw and errata-adjusted counts.
  - The raw DEV false README-evidence count (18) includes the `language.javascript` README item extracted from d22.
    That mention is genuine, and JavaScript is also the repository's language, so the adjusted count is 17.
  - The correction changes no SUPPORTED outcome. d22's only false SUPPORTED is the React mention without use.
- **Full original hashes:**
  - DEV `b7c42f5904f4191824083a5fa5175cdf5ec18ff16d5f871d77b04f3fc5bf2172` (24,699 bytes)
  - EVAL `15ae7d6951cafe3ce139e4266e5123c30459d104556237a41534f8c2f8999a81` (22,053 bytes)
  - Both were frozen at 2026-11-11T06:17:10Z in LF form.
  - The policy design was frozen at 06:20:32Z, before the first EVAL run.

## 5. Candidate policies (offline adapters, `scripts/evaluation_lib/m11g22r_policies.py`)

- **A:** job side only. G22 A, the generic-usage guard: a lowercase surface of a capitalised name in a verb or adjective
  frame.
- **B:** README side only. The same predicate, added to `readme.is_non_implementation_mention` per occurrence.
- **C:** one shared rule (A + B).
- **D:** per-alias metadata with separate policies.
  - **Job side:** G22 B, the 7 reviewed aliases plus a technical cue.
  - **README side:** 11 reviewed aliases. Each needs README-specific corroboration: code or inline code, a heading, a
    version or install string, a claim-of-use frame ("uses", "built with", "Stack:"), or G22's cue.
- **R (study only, a semantic change):** README evidence for a concept with no non-README corroboration is dropped.
- **DR:** D + R (study only).

| | DEV false README | DEV false job | DEV false SUPPORTED | DEV README recall | EVAL false README | EVAL false job | EVAL false SUPPORTED | EVAL README recall | EVAL true SUPPORTED |
|---|---|---|---|---|---|---|---|---|---|
| BASE | 18 | 7 | 21 | 14/14 | 16 | 5 | 20 | 12/12 | 11 |
| A | 18 | 2 | 18 | 14/14 | 16 | 3 | 18 | 12/12 | 11 |
| B | 14 | 7 | 17 | 14/14 | 13 | 5 | 17 | 12/12 | 11 |
| C | 14 | 2 | 15 | 14/14 | 13 | 3 | 15 | 12/12 | 11 |
| **D** | **3** | **0** | **5** | 14/14 | **5** | **0** | **7** | 12/12 | 11 |
| R *(study)* | 1 | 7 | 1 | **9/14** | 0 | 5 | 1 | **8/12** | **8** |
| DR *(study)* | 1 | 0 | 0 | 9/14 | 0 | 0 | 0 | 8/12 | 8 |

**Reading the table:**

- **A and B** each fix only their own source. The generic-usage frame catches "react quickly", "a swift" and "to react",
  but not "express their opinion", "rust stains" or "red pandas".
- **D** removes every false job concept on both sets with no measured genuine job or README recall loss.
  - **EVAL residuals:** "free of rust" and "full of rust", which pass the inherited `of` lead-in cue; "local and express
    trains", which passes the `and` list-sibling cue; and capitalised "Ruby" and "Java".
  - **DEV residuals:** "my cat, Ruby", "beaker and flask", and the d22 erratum.
  - **Mentions without use** (3 per set) are untouched by D. That is an evidentiary-strength issue, not a recognition
    issue.
- **R** removes almost all false SUPPORTED, but loses a third of genuine README recall and true SUPPORTED. It changes
  the meaning of SUPPORTED (§8).

## 6. G19 capability

- **Occurrence guards leave capability unchanged.** B, C and D never touch the alias table, and capability is identical
  for all 39 concepts under every policy (verified).
- **Changing the alias table instead would do damage.** Marking an ambiguous alias `readme_unsafe`, the 5D.1 approach,
  would:
  - make `framework.flask` and `data.library.pandas` **NOT_ASSESSABLE**, dropping them from every denominator;
  - remove README coverage from Swift, Rust, Ruby and Java, leaving them language-only;
  - leave React and Express only "react.js" / "expressjs" coverage;
  - **and stop the job parser recognising "React", "Express", "Python", "Swift" and others in job prose at all**,
    because `readme_safe_aliases()` is also the job parser's scan list.
- An alias-table change is therefore **not** a safe fix for either side. Per-occurrence guards are.
- If an alias ever does become context-restricted in the table, G19's capability tests, G15, G18 and G19 reports, and
  the scoring v2 denominators would all need re-review.

## 7. G21 and G22-Q compatibility

- **G21:** job-side policies only blank recognition spans inside G21's `scoped_text`; admission and necessity never
  change (inherited G22 adapter guarantee).
- **G22-Q:** equivalence survives every policy. G15-I1 gives one Kubernetes row and G18-16 one Go row; "React or ReactJS"
  and "Express or Express.js" each give one row.

## 8. Historical impact (actual measurements)

| | A / C job side (G22 A) | D job side (G22 B) | B, C, D README side | R (study) |
|---|---|---|---|---|
| G20 dev / hold-out | React, Express, Swift removed from d016, d017, d022, h011, h012 (all intended) | same | — | — |
| G21 negation scope | 0 | **React lost on n10 (genuine)** | — | — |
| G15, G16, G18, M10, 8c job scoring | 0 changes; G16 claim false SUPPORTED 7 → 7 | 0 changes; 7 → 7 | — | — |
| G17 containment | 0 | 0 | — | — |
| M10E row existence | 0 mismatches; **g3's SQL row unchanged (still open)** | 0 | — | — |
| G22 DEV / EVAL false registered | 9 → 4 / 7 → 3 | 9 → 1 / 7 → 0 | — | — |
| 8c real README evidence (126 items) | 0 | 0 | B: 1 occurrence moved (shell → bash, same concept); D: 3 changed, of which 2 moved and 1 dropped (AudioNoise "python visualizer", still evidenced by language statistics) | **47 items dropped** |
| Frozen 8c v1 / v1.1 scores | 0 | 0 | **0** | **4 pairs lower in each matrix version** (8 matrix entries; e.g. sindresorhus/frontend 80 → 40); denominators unchanged |
| Existing extractor, pipeline, capability, 8c and parser tests (337) | 337 pass | 337 pass | 337 pass | n/a |
| Private postings (62; job side) | 0 changed | 0 changed | no private repositories | — |

## 9. Recommendation (smallest safe future correction)

1. **Separate milestones, job side first.**
   - The job side is a **parser** change (v16), using G22's Option B metadata and cue.
   - The README side is an **evidence-extractor** change (`readme:v4` → `v5`), with no matcher or scoring change.
   - The two have different text, different cues and different regression surfaces (job corpora versus real READMEs).
     G22's own job-side list was already judged unsuitable for READMEs (python, java, flask, pandas).
2. **Per-alias ambiguity metadata, but not in `readme_unsafe_aliases`.**
   - Add a separate, reviewed `ambiguous_aliases` field per concept, read by an occurrence guard. The safe-alias table
     is not edited, so capability, ranking and job recognition stay intact.
   - Each source keeps its own cue policy.
3. **README cue design needs one more pass before production.** The `of` and `and` lead-in cues inherited from job prose
   must not count for README text, and capitalised-name homonyms (Ruby, Java) are not solved by casing.
4. **README-only claims:** do **not** change SUPPORTED semantics in a small fix.
   - R shows README-only evidence carries a large share of genuine real-world evidence; 8c scores fall by up to 40 points.
   - A future, separately versioned design could expose evidence strength (README-only versus corroborated) in the
     API or explanation layer. Any change to what counts toward the numerator would need a scoring-version review (v3)
     and a matcher-contract review.
5. **Provenance:** keep the existing per-item snippet and `extractor_version`. A guard that rejects an occurrence should
   leave the next occurrence or alias to be tried, as 8D.3 already does, so evidence remains auditable.

**Production files a future fix would touch:**

| Side | File | Change |
|---|---|---|
| Job | `jobs/parsing/concepts.py` or `parser.py` | occurrence guard |
| Job | `concepts/models.py` + `concepts/registry.py` | new metadata field, not `readme_unsafe_aliases`; `CONCEPT_REGISTRY_VERSION` review |
| Job | `parser.py` | version label |
| README | `evidence/extraction/readme_context.py` or `readme.py` | per-occurrence guard |
| README | `readme.py` | `EXTRACTOR_VERSION` `readme:v4` → `v5` |

There is no matcher or scoring change unless README-only semantics are pursued, and that requires its own milestone.

## 10. Decisions required

1. Approve the job-side and evidence-side split into two milestones, and their order?
2. Approve a new per-concept `ambiguous_aliases` metadata field, which would need a registry version review?
3. Approve a README cue redesign (dropping the `of`/`and` lead-ins, and deciding how to handle capitalised homonyms) on a
   fresh, separately authored control set before implementation?
4. Should README-only "mentioned without use" evidence be surfaced differently, as an explanation-layer label without a
   scoring change, or left as is?
5. ~~Approve registering the G22-R DEV and EVAL freezes in the G14 manifest at a research commit?~~ Approved and done at
   the research commit (17 → 19).

## 11. Files (research only)

- **Controls and freezes:**
  - `evaluation/m11g22r/alias_evidence_controls_{dev,eval}.json`
  - `evaluation/m11g22r/{dev,eval}_hash_freeze.json`
  - `evaluation/m11g22r/policy_design_freeze.json`
- **Reports:**
  - `evaluation/m11g22r/alias_evidence_report.json`
  - `evaluation/m11g22r/private_alias_aggregates.json`
- **Scripts:**
  - `scripts/evaluate_m11g22r_alias_evidence.py`
  - `scripts/evaluation_lib/m11g22r_{build_controls,policies,harness,pytest_policy}.py`
- **Tests:**
  - `tests/test_m11g22r_ambiguous_alias_evidence.py` (21).
  - `tests/test_m11g22_concept_recognition_research.py`: G22's hard-coded "manifest has exactly 17 entries" assertion
    became false once these freezes were registered. It now pins the historical fact exactly instead: the manifest at
    G22's commit `fad7c6d` had 17 entries, and every one is still present field for field.
- **Docs:** this file and `docs/CHANGELOG_DEV.md`.
- **Manifest:** `evaluation/integrity/canonical_hash_manifest.json` (+2 entries).
