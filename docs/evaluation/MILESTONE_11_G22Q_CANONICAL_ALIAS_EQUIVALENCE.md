# Milestone 11-G22-Q — Canonical alias-equivalence correction (parser v15)

Status: production change implemented, verified, and committed after authorization ("fix: canonicalize equivalent
technology alternatives"). It is Option Q from
`MILESTONE_11_G22_CONCEPT_RECOGNITION_PRECISION.md`, the only G22 option approved. Options A, B, C2, G and G23 are not
started.

| | Before | After |
|---|---|---|
| Parser | `job_description_parser:v14` | `job_description_parser:v15` |
| Scoring | `github_evidence_alignment:v2` | unchanged |
| Matcher, extractors, registry, schemas, API, frontend | — | unchanged |
| Production files | — | `src/gitscore/jobs/parsing/alternatives.py` (logic), `src/gitscore/jobs/parsing/parser.py` (version label only) |

**Scope.** Q corrects one narrow defect. It does **not** solve G22's broader precision problem: every false registered
concept and every fabricated `unresolved:` concept G22 measured is still produced by v15 (§8).

---

## 1. Baseline (verified before any change)

- HEAD = `origin/main` = `fad7c6dc3dd8608e382478ed10156b414d86b7ae` (the G22 research commit), branch `main`.
- Parser v14, scoring v2.
- Backend: 2270 passed, 13 skipped, 18 xfailed. Frontend: 53 passing. G14 manifest: 17 freezes.
- The 18 private/untracked M11 entries are present and are left untouched.

## 2. The defect

`alternatives._classify_segment_list` counts the distinct concept ids across an OR's segments. When two or more
segments resolve to the **same** registered id ("Kubernetes or k8s", "Go or Golang", "Postgres or PostgreSQL"), fewer
than two distinct ids remain. The function then returns `kind="unsafe"` (alternatives.py, the
`len(ordered_ids) < 2` branch).

The parser's 6B.1 fallback turns `unsafe` into a `category="alternative_requirement"` placeholder with
`concept_id=None`. The matcher always gives that placeholder `NOT_ASSESSABLE`, and scoring v2 never counts it. So a
requirement that names exactly **one** technology was dropped from the score.

v14 effects, measured with the real pinned v14:

- **G15-I1** "Experience with Kubernetes or k8s is required." — the frozen gold is an `alias` structure with one
  `infra.kubernetes` requirement. v14 gave an undefined score for both candidates.
- **G18-16** "Experience with Go or Golang" — the frozen `expected_scores` are 100 (1/1) and 0 (0/1). v14 gave
  undefined (0/0).
- **G13-o007** (the same text as G15-I1, gold `equivalent_aliases`) — v14 dropped this decidable requirement.
- **G22 equivalent-alias controls** d19, e17, e20, e21, e25 — v14 placed all five in taxonomy class D.

The representation cannot express this as a group: `JobRequirement.alternative_concept_ids` must hold at least two
distinct entries (`jobs/models.py`). A single concept must therefore be a `concept_id` row, and the parser builds such a
row only on its ordinary (`not_technical`) per-claim path.

## 3. Why canonical identity is enough, and the algorithm

The registry id **is** the canonical identity. Two aliases that `resolve_concept` maps to the same id are, by the
registry's own definition, the same concept. No similarity, relation edge or candidate evidence is needed. Q only lets
the parser act on an identity it already computed.

`alternatives.equivalent_alias_concept_id(text)` returns that id, or `None`, and **all** of the following must hold:

1. The claim contains a literal "or" and is **not** structurally mixed. G17's `is_structurally_mixed` runs first and
   always wins.
2. It splits (`_split_alternative_segments`, unchanged) into at least two alternatives. Each must be a **bare list
   item**: `clean_list_fragment` accepts it. An alternative carrying prose, such as "react quickly to incidents" or
   "Go for backend services", is never equated.
3. Each alternative resolves **independently**, through the existing `_resolve_segment`, to exactly one **registered**
   id. An `unresolved:` id never qualifies, and the id must be the same for every alternative.
4. Each alternative's cleaned term is **in its entirety** a registry alias of that id (`resolve_concept`). An alias
   merely *embedded* in a longer name is not enough.
5. The full-claim scan that the single-concept path will run (`find_concept_mentions` +
   `find_conservative_unknown_terms`) finds that id and **nothing else**. The outcome is therefore exactly one row for
   that id.

`classify_alternative_claim` calls the unchanged v14 classification (now `_classify_alternative_structure`). It
converts the result to `not_technical` **only** when that result is `unsafe` and an equivalence is established; every
other result is returned untouched. The parser then builds the row exactly as for a claim naming one technology.
Text, span, necessity, importance and observability are all computed by unchanged parser code.

**Revision made during implementation.** The first version omitted condition 4. The real comparison showed it merging
G13-o012, "Experience with Docker or Docker Compose", into a single Docker row through the embedded "Docker" mention.
The gold for o012 is `or_any`, "related, non-equivalent alternatives". Condition 4 was added, and o012 keeps its v14
placeholder. The same condition also leaves G22-e25, "Bash or shell scripting", unmerged, because "shell scripting" is
not a registry alias (§7).

## 4. Identical concepts versus genuine alternatives

| Claim | v14 | v15 | Why |
|---|---|---|---|
| Kubernetes or k8s / K8s or Kubernetes / kubernetes or K8S | placeholder | `infra.kubernetes` | whole aliases of one id |
| Go or Golang / Golang or Go experience / go or golang | placeholder | `language.go` | the isolated OR-segment "go" already resolved in v14 (M6B.1) |
| Kubernetes or Kubernetes; Kubernetes, K8s, or k8s | placeholder | `infra.kubernetes` | repeated or three aliases |
| Python or Go; Docker or Kubernetes | OR group | OR group (unchanged) | different ids |
| Kubernetes or k8s or Docker | {docker, kubernetes} | unchanged | already deduplicated by v14; Docker kept |
| K8s, Kubernetes, or OpenShift | {kubernetes, `unresolved:openshift`} | unchanged | the unknown alternative is kept |
| PostgreSQL or SQL; React or Next.js; JavaScript or TypeScript | OR group | unchanged | related, never equated |
| FreeRTOS or RTOS | {freertos, `unresolved:rtos`} | unchanged | the registry's only parent edge (`embedded.rtos`) is not even registered |
| Docker or Docker Compose | placeholder | placeholder | embedded alias; a different tool |
| Bash or shell scripting | placeholder | placeholder | "shell scripting" is no registry alias |
| Kubernetes or a similar orchestrator | placeholder | placeholder | unknown alternative |
| You should react calmly under pressure or use React daily | placeholder | placeholder | prose segment (G22 class-A false identity) |
| 3+ years of experience with Kubernetes or k8s / Strong knowledge of Kubernetes or k8s | placeholder | placeholder | first alternative is not a bare alias (conservative; §10) |
| Kubernetes or k8s (preferred) | placeholder, PREFERRED | unchanged | "k8s (preferred)" is not a bare alias |
| Azure or Microsoft Azure | {`unresolved:azure`, `unresolved:microsoft_azure`} | unchanged | unregistered: no new alias is invented |
| Must be able to go or travel to client sites | `unresolved_requirement` | unchanged | prose "go" never resolves; Q is not a Go recogniser |

## 5. Interaction with G17 containment

- Q is checked **after** the complete v14 classification, including G17's `_contain_mixed`. It also calls
  `is_structurally_mixed` itself and declines on any structural signal: k≥2-of, "both"/"all of", a conjunction-led
  comma item, or a segment resolving to two or more concepts.
- Every mixed claim keeps its placeholder: "Python and Kubernetes or k8s", "At least two of Kubernetes, k8s, or
  Docker", "Kubernetes or k8s, and Python", "both Kubernetes or k8s", and "Kubernetes or k8s, and Docker or Podman".
- Q converts **only** `unsafe` results, so no flat `technical` group can change. This includes the known G16 residuals
  018 and 043.
- Real comparison: 46 G16 controls with alternative rows were checked, with 0 violations. 88 of 88 v14 OR groups are
  preserved byte-for-byte across every tracked corpus and control set.
- G17 tests were not weakened. Their only edit is the version-literal update for `test_parser_version_is_v13`.

## 6. Scoring v2 impact

No scoring or matching code changed. A recovered row is an ordinary registered `concept_id` row, so scoring v2 treats
it exactly like the same claim with one technology.

Results with the real v14 and v15:

| Fixture | v14 | v15 | Frozen expectation |
|---|---|---|---|
| G15-I1 k8s_evidence | undefined (0 eligible) | 100 (1/1) SUPPORTED | SUPPORTED |
| G15-I1 neither | undefined | 0 (0/1) NOT_OBSERVED | NOT_OBSERVED |
| G18-16 go | undefined | 100 (1/1) | 100 (1/1) |
| G18-16 none | undefined | 0 (0/1) | 0 (0/1) |
| G13-o007 (Kubernetes evidence) | dropped | 100 (1/1) | satisfies, 1 scored requirement |

- A newly assessable requirement is **not** automatically supported. Without evidence it becomes NOT_OBSERVED and
  lowers the score, as G18-16's "none" fixture shows.
- Unrelated evidence (Docker, Go, AWS for Kubernetes; Kubernetes, Python, JavaScript for Go) never satisfies the
  requirement. These cases are tested.

## 7. Real v14 → v15 comparison

`scripts/evaluate_m11g22q_v14_v15.py --private-corpora` produces `evaluation/m11g22q/v14_v15_comparison.json` and
`private_v14_v15_aggregates.json` (counts only).

**Method:**

- v14 is the real code at the pinned commit `fad7c6d`, the G22 research commit and parent of G22-Q. Its `src/` is
  identical to the G21 commit `de2a906` (checked). It runs in a throwaway clone with `core.autocrlf=false`. v15 is the
  working tree.
- All 200 tracked inputs are identical under the G14 newline contract, and both span-bearing `.txt` inputs are
  byte-identical.
- Both sides run `scripts/evaluation_lib/m11g22q_parser_dump.py`. That script reuses G21's dump and adds G22's
  harness, G13 and M10E. The run uses the real parser, matcher, scoring v2 and API serializer, with no simulation.
- Inside the pinned clone, G22's own report builder reproduces the committed G22 report **byte-identically**, so the
  G22 frozen research outputs are confirmed by real v14 and were not rewritten.

| # | Measure | Result |
|---|---|---|
| 1 | Same-concept OR placeholders recovered | **3** tracked: G15-I1, G18-16, G13-o007. Plus G22 synthetic d19, e17, e20, e21 |
| 2 | Genuine OR groups preserved | **88 / 88**; 0 other row or UnparsedClaim changes in any tracked corpus or control set |
| 3 | Newly scoreable requirements | 4 fixture outcomes (I1 ×2, 16 ×2) |
| 4 | MatchStatus changes | `not_assessable → supported (counted)` ×2, `not_assessable → not_observed (counted)` ×2; no status change on any kept row |
| 5 | Evidence counts | G15 21 → 22, G18 35 → 36: the Kubernetes and Go evidence now attached to the recovered rows; every other fixture identical |
| 6 | Denominators | G15 19 → 21, G18 50 → 52; G16, 8c v1, 8c v1.1 and M10 unchanged |
| 7 | Scores | only I1 and 16 (undefined → 100 / 0) |
| 8 | Undefined scores | 4 became defined, **0 became undefined** |
| 9 | False SUPPORTED | **0 new**. Both new SUPPORTED rows are frozen-truth correct; G16 claim-level false SUPPORTED 7 → 7 |
| 10 | Private postings | 62 previously inspected postings, **0 changed** (rows, necessity, placeholders, unresolved, denominator) |

**Further results:**

- **Frozen 8c v1 / v1.1 and M10 SOTI/Manulife:** 0 changes.
- **M10D, M10E, G6, G7, G16, G20 dev and hold-out, G21 adversarial:** 0 row changes. G21 negation scope stays at
  14/16.
- **M10E row-existence mismatches outside the known list:** none, in either version.

**G22 control sets** (synthetic, written by the same author; not independent validation):

| | DEV v14 → v15 | EVAL v14 → v15 | G22 Q *simulation* (EVAL) |
|---|---|---|---|
| exact | 29 → **30** / 45 | 22 → **25** / 44 | 26 |
| concept recall (registry) | 51 → 52 / 54 (42 → 43 / 45) | 56 → 59 / 64 (41 → 44 / 48) | 60/64 (45/48) |
| necessity | 48/48 → 49/49 | 47/50 → 50/53 | 51/54 |
| taxonomy D (alias equivalence) | 1 → 0 | 4 → 1 (e25) | 0 |
| false registered / fabricated / false SUPPORTED | 9 / 6 / 9 unchanged | 7 / 9 / 7 unchanged | unchanged |

**Divergence from the simulation (actual finding):** the G22 simulation accepted e25, "Bash or shell scripting", through
the embedded "shell" mention. Production v15 does not, because condition 4 is the rule that keeps "Docker or Docker
Compose" an OR. e25's frozen gold is unchanged and its v14 placeholder is retained, with no regression and no recovery.
Every other simulated Q outcome is reproduced exactly.

## 8. What Q does not fix (remaining G22 defects)

- **False registered concepts:** DEV 9 and EVAL 7, unchanged. Examples: lowercase "react", "express", "swift" and
  "torch" in prose. These are classes A and B, handled by Options A and B, which are not started.
- **Fabricated `unresolved:` concepts:** DEV 6 and EVAL 9, unchanged. Examples: "curiosity", "teamwork",
  "Alternatively", "context" and `unresolved:go`. These are class C, handled by Option C2, which is not started.
- **Bare "Go" in prose:** still unrecognised (Option G, not started).
- **M10E-g3** (out of scope; frozen gold unchanged): "You will learn SQL, but prior knowledge of databases is
  required." still yields a counted REQUIRED `language.sql` row in v15, identical to v14. A SQL candidate scores 100,
  which violates the frozen `technical_concepts_may_enter_scoring=false`. Q has no OR here and changes nothing, so it
  neither fixes nor disguises this defect.

## 9. Historical compatibility (version branches; nothing weakened, nothing newly skipped)

Every assertion pinning v14 behaviour is kept for v14 and gains an explicit v15 branch with exact expectations:

- **Version literal only**, following the established convention: M11-A2, M11-B, M11-C, M11-E, G17, G21 and G20
  (accepts v15).
- **`test_job_parser_extraction`** "Python or python": v14 is `unsafe`; v15 is `not_technical` and still never a
  group.
- **G13** report: v15 differs from the committed report in exactly the o007 entries and the two aggregates that list
  o007.
- **G15** report: v15 may additionally differ only on I1, asserted as one Kubernetes row and SUPPORTED / NOT_OBSERVED
  under every policy.
- **G16** report: v15 accepted with the v14 assertions unchanged; Q changes no G16 control.
- **G18** report: v15 may additionally change only G15-I1 and G18-16, asserted exactly. Every metric id list, with
  those controls removed, is identical.
- **G19:**
  - duplicate alternatives — "Go or Golang" is (0, 1) with Python evidence and (100, 1) with Go evidence; "Azure or
    Microsoft Azure" is unchanged.
  - the 54-pair check — mismatches are exactly 16/go, 16/none (now equal to 16's frozen `expected_scores`) and the
    G21 control 25.
- **G21** first-v14 reverse patch: under v15 the patch is applied to the three files read from the pinned commit
  `fad7c6d`, never the working tree or a moving HEAD.
- **G22 research tests:** the four `only_v14` skips (eight test cases) became explicit branches.
  - Classes A, B and C and M10E-g3 are asserted unchanged on v15.
  - The equivalent-alias test asserts the v15 correction.
  - The public-report test, on v15, disables only the G22-Q step in-process and requires byte-identity with the
    committed v14 report.

## 10. Known limitations

- **Conservative recall.**
  - When the first alternative carries lead-in prose that the existing cleaner keeps ("3+ years of experience with
    Kubernetes or k8s", "Strong knowledge of Kubernetes or k8s"), or a trailing "(preferred)", the claim stays a
    non-assessable placeholder exactly as in v14.
  - The same applies to an alias embedded in a longer phrase ("shell scripting").
  - None of these is a regression.
- **The registry alias table is trusted as-is.** "Torch" is a registry alias of PyTorch, so "PyTorch or Torch" is one
  PyTorch row. G22 flagged `torch` as prose-ambiguous (class B), but only under a bare-list-item condition. Q adds no
  alias and no ambiguity metadata (Option B is not started).
- **A comma-only same-concept list with no "or"** (for example, inside an "at least one of" trigger) is not handled.
  It keeps its v14 outcome.
- **Validation status.** The G22 synthetic controls are written by the same author and are not independent validation.
  The 62 private postings were inspected before, so their "0 changed" is not independent validation either.

## 11. Files

- **Production:**
  - `src/gitscore/jobs/parsing/alternatives.py` — `equivalent_alias_concept_id`; `classify_alternative_claim` wraps
    the unchanged `_classify_alternative_structure`.
  - `src/gitscore/jobs/parsing/parser.py` — version label only.
- **Tests:**
  - `tests/test_m11g22q_canonical_alias_equivalence.py` (new; 75 tests).
  - Version branches in 14 existing test files (§9).
- **Evaluation:**
  - `scripts/evaluate_m11g22q_v14_v15.py`
  - `scripts/evaluation_lib/m11g22q_parser_dump.py`
  - `evaluation/m11g22q/v14_v15_comparison.json`
  - `evaluation/m11g22q/private_v14_v15_aggregates.json`
- No new frozen control set and no G14 manifest change: still 17 freezes. G22's freezes and outputs are unchanged.

## 12. How to test

```
python -m pytest tests/test_m11g22q_canonical_alias_equivalence.py
python scripts/evaluate_m11g22q_v14_v15.py --private-corpora   # rewrites only evaluation/m11g22q/
python -m pytest tests
```
