# Milestone 11-G10 — Minimal Competency Concept Model

**Status: design + offline prototype complete, STOPPED per instructions. No production code changed. No commit/push made.**

M11-G9 is complete and pushed (`9c923b0`); nothing in this milestone recommits, regenerates, or modifies it. This document, the offline data model, and the focused tests are all **new, untracked, local-only files** — see §11 for the exact inventory.

## 1. Baseline verification

| Check | Expected | Confirmed |
|---|---|---|
| HEAD | `9c923b0496771326420637143cab5d9fcc6002a5` | ✅ matches |
| Branch | `main` | ✅ matches |
| Parser version | `job_description_parser:v12` | ✅ matches, unchanged throughout |
| Full suite before this milestone | 1748 passed / 13 skipped / 2 xfailed | ✅ matches (M11-G9's own post-push state) |
| Full suite after this milestone | — | **1783 passed** / 13 skipped / 2 xfailed (+35 new M11-G10 focused tests, zero regressions) |
| Private M11-D/F/G5/G9 datasets, frozen gold, M11-generalization artifacts | present, untouched | ✅ confirmed present in `git status`, confirmed byte-unchanged (never opened for writing by this milestone) |

`git diff --stat HEAD` is empty throughout — zero modification to any tracked file at any point in this milestone.

## 2. Existing-model audit (Phase 1)

Two independent concept vocabularies already exist in production, each doing its own job well, with no connective tissue between them:

1. **`gitscore.concepts.registry.TechnicalConcept`** (Milestone 5C/8D.1) — concrete, registered technologies (`concept_id` like `"infra.kubernetes"`), used for GitHub-evidence-side resolution (dependencies, language stats, README prose). Already carries `parent_id` (a single broader concept) and `related_ids` (a tuple) — but **both are UNTYPED** (no label distinguishing "broader" from "merely associated") and, more importantly, **neither is consumed anywhere**. Confirmed by grep: no file outside `concepts/models.py`/`concepts/registry.py` reads `parent_id` or `related_ids` at all. `matching/engine.py` + `matching/support.py` do exact `concept_id` lookup only (`CandidateEvidenceProfile.concept(concept_id)`), with zero cross-concept traversal.
2. **`gitscore.jobs.parsing.competency_aliases.AliasRelation`** (Milestone 11-C onward) — a **phrase-to-tag** relation (`SEMANTICALLY_EQUIVALENT` / `NARROWER_OR_MORE_SPECIFIC` / `RELATED_ONLY` / `UNKNOWN`): how a raw sentence phrase relates to ONE canonical `competency_tag`. It has **no tag-to-tag or tag-to-`concept_id` edge at all** — M11-G9's own §2e explicitly identified this gap.

The job-side `Qualification`/`NormalizedReference` model (Milestone 11-B, offline/not wired) already keeps the two namespaces **deliberately separate**: `NormalizedReference.concept_id` XOR `competency_tag` XOR `alternative_concept_ids`, enforced by its own `__post_init__`, never merged. `GithubObservability` (jobs/types.py) is already a clean three-state separation of "assessable in principle" (dimension D in this mission's A/B/C/D/E list) from "actually observed for this candidate" (dimension E), the latter owned entirely by `matching/support.has_sufficient_evidence` + `CandidateConceptSummary` — a different layer this milestone never touches.

**What's missing**: nothing to represent a typed relation (equivalent / broader / narrower / related-only / ambiguous) **between** a `competency_tag` and a `concept_id`, or between two tags, or between two concept ids — across either namespace, without modifying either namespace's own shape.

**What can be added without touching public contracts**: a small, standalone, offline graph referencing both namespaces read-only through a tiny tagged-union `ConceptRef` (mirroring `NormalizedReference`'s own exactly-one-of pattern) — exactly what Phase 2–4 below builds.

**What would require explicit future migration**: wiring any part of this graph into `matching/engine.py` to allow controlled cross-concept inference (e.g., scoring a narrower-concept match as partial support for a broader requirement) would be a new, explicit, reviewed matching-policy decision — never silent, and not proposed here. Merging the `competency_tag`/`concept_id` namespaces into one would be a genuine `NormalizedReference`/`JobRequirement` schema migration — also not proposed here.

**Concepts remaining fundamentally non-assessable from GitHub**: unchanged from M11-G8/G9's own finding — soft-skills, leadership, communication, years-of-experience, work authorization, education credentials. This graph doesn't change that ceiling; it only needs to represent it faithfully (§4 below shows `ml-fundamentals`/`circuit-theory`/`quantum-computing` correctly carry `NOT_OBSERVABLE`, not a silently-inflated default).

## 3. Proposed internal data model (Phase 2)

`scripts/evaluation_lib/m11g10_competency_concept_model.py` — offline-only, imports v1/v2/v3 and the registry read-only, modifies nothing.

- **`ConceptRef`** — exactly one of `registry_concept_id` (validated via the EXISTING `concepts.registry.is_valid_concept_id()`, no second validation rule) or `competency_tag` (free, unregistered slug, never validated against any registry — mirrors `NormalizedReference`'s own policy). `.key` disambiguates the two namespaces explicitly (`"concept:..."` vs `"tag:..."`) so they can never collide even incidentally.
- **`ConceptStatus`** — `ACTIVE` / `PROVISIONAL` / `REJECTED`. `REJECTED` is a kept, visible node, not a deletion — so a future proposal re-raising an idea M11-G9 already declined finds that decision recorded instead of re-litigating it from scratch.
- **`CompetencyConceptNode`** — identity only: `ref`, `display_name`, `status`, `introduced_in` (milestone id — concept-level provenance, never a document source-span, which stays on `Qualification` where it already lives). `tag_observability` has one deliberately strict invariant: a registry-concept node must NEVER set it locally (observability is derived live from `observability.py`'s `TECHNICAL_DEFAULT_OBSERVABILITY` via `effective_observability()` — storing a second copy would be a second source of truth that can silently drift); a tag node MUST set it explicitly (there is no other source of truth, and defaulting it would misrepresent what the concept's mere existence implies).
- **`ConceptRelationType`** — `EQUIVALENT` / `NARROWER_THAN` / `BROADER_THAN` (exact inverses of each other) / `RELATED_ONLY` / `AMBIGUOUS` (both self-inverse). Each edge is stored once; the reverse direction is derived from `.inverse()` on lookup, never stored twice (so the two directions can never silently disagree).
- **`ConceptRelation`** — `subject RELATION obj`, `introduced_in`, `note`. Self-loops rejected at construction.
- **`RelationLookup`** — three distinct statuses (`"resolved"` / `"unknown"` / `"ambiguous"`), never collapsed into a bool/`None` pair.
- **`CompetencyConceptGraph`** — immutable, built once; validates identity collisions, dangling edges, contradicting duplicate edges, and cycles restricted to the hierarchical (`NARROWER_THAN`/`BROADER_THAN`) sub-graph only (an `EQUIVALENT` cluster forming a cycle is explicitly fine — symmetric relations have no meaningful "cycle" defect).

The A/B/C/D/E separation the mission named is never collapsed:

| Dimension | Where it lives |
|---|---|
| A. phrase mentions a technology | `jobs/parsing/concepts.py` (existing, unchanged) |
| B. genuine applicant qualification | `Qualification.qualification_kind`/`necessity` (existing, unchanged) |
| C. normalized competency concept | **this milestone's `ConceptRef`/`CompetencyConceptNode`** |
| D. assessable using GitHub evidence at all | `CompetencyConceptNode.effective_observability()` (concept-level, no candidate) |
| E. actually supported by verified repository evidence | `matching/support.has_sufficient_evidence` + `CandidateConceptSummary` (existing, unchanged, per-candidate) |

## 4. Safety invariants and test results (Phase 3/7)

All 35 focused tests in `tests/test_m11g10_competency_concept_model.py` pass. Every invariant the mission named has a dedicated, named test:

| Invariant | Test |
|---|---|
| Docker must not automatically prove Kubernetes | `test_docker_does_not_prove_kubernetes` — `RELATED_ONLY`, `is_equivalent()` False |
| AWS must not automatically prove Azure | `test_aws_does_not_prove_azure` — same pattern, against an illustrative PROVISIONAL `cloud-platform-azure-pilot` node (Azure is not a registered `TechnicalConcept` today) |
| Related concepts are not equivalent | `test_related_only_is_never_equivalent_for_every_edge_in_reference_graph` — checked over every edge in the real reference graph, both directions |
| Narrower never proves broader without an explicit validated rule | Structural: no `satisfies()`/`implies_support()` method exists anywhere in the module (`test_module_provides_no_transitive_or_satisfaction_inference_function`, enumerates every public callable) |
| A technology mention is not automatically an applicant requirement | Unaffected — owned entirely by existing `jobs/parsing/qualification.py`/intent gates, outside this module's vocabulary (confirmed by `test_module_never_imports_necessity_evidence_or_scoring_types`) |
| Concept existence does not imply GitHub assessability | `test_tag_node_must_declare_observability_explicitly` — construction raises if a tag node omits it |
| GitHub assessability does not imply SUPPORTED | Structural: no evaluation-status field anywhere in the module; `test_module_never_imports_necessity_evidence_or_scoring_types` |
| Unknown relationships fail conservatively | `test_unknown_pair_fails_conservatively_not_as_related_or_equivalent` — distinct `"unknown"` status, not a default relation |
| Ambiguous aliases are not silently resolved | `test_ambiguous_relation_is_not_silently_resolved` — distinct `"ambiguous"` status, synthetic throwaway fixture |
| No automatic transitive inference across edges | `test_no_transitive_inference_across_narrower_chain` — A→B→C narrower chain; direct A/C lookup stays `"unknown"` (read conservatively: applies to every relation type, not only `RELATED_ONLY`) |
| No inferred REQUIRED/PREFERRED from concept identity | Structural: `Necessity` never imported (`test_module_never_imports_necessity_evidence_or_scoring_types`) |
| Relation direction | `test_narrower_than_and_broader_than_are_exact_inverses` |
| Cycles | `test_hierarchy_cycle_is_rejected_at_construction` (rejected) / `test_equivalent_cluster_cycle_is_allowed` (accepted — symmetric relations have no cycle defect) |
| Identity collisions | `test_duplicate_node_identity_is_rejected` |
| Dangling edges / contradicting duplicates | `test_dangling_edge_is_rejected` / `test_contradicting_reverse_edge_is_rejected` |
| Schema-version compatibility | `test_deserialize_rejects_version_mismatch` — hard failure, never a silent migration, mirroring M11-G9's own `gold_hash_freeze.json` policy |

## 5. Legacy compatibility findings (Phase 5)

- **Preserves all existing canonical identities**: `test_every_existing_17_tag_is_present_in_reference_graph_as_active` reads the live 17-tag set directly off `competency_aliases.ALL_ALIASES` (never hand-retyped) and confirms every one is present, `ACTIVE`.
- **Preserves existing alias distinctions**: the graph holds zero phrase-level data of its own; alias phrases remain exclusively in `competency_aliases.py` (confirmed by the module never importing `CompetencyAlias`).
- **Represents v3's 3 concepts without overwriting old ids**: `test_v3_pilot_concept_keys_are_disjoint_from_existing_17_tags`; all three are `PROVISIONAL`, not auto-promoted to `ACTIVE` (`test_v3_pilot_concepts_present_as_provisional_not_active`). Observability values are hand-pinned against the real v3 module (`test_v3_pilot_observability_values_match_the_real_v3_module`) so a future edit to either table that drifts from the other is caught.
- **Round-trips compatible `NormalizedReference`s without semantic loss**: `test_round_trips_a_registered_concept_normalized_reference` / `test_round_trips_a_competency_tag_normalized_reference` — both directions, exact equality.
- **Explicitly declines unsupported legacy projections**: a `NormalizedReference` carrying a populated `alternative_concept_ids` GROUP has no single-`ConceptRef` equivalent in this minimal model — `concept_ref_from_normalized_reference()` returns `None` (an explicit decline), never guesses a member of the group (`test_alternative_concept_group_is_explicitly_declined_not_guessed`). Same for the illustrative "neither field set" `NormalizedReference` shape.
- **Distinguishes relatedness from evidence entailment**: confirmed structurally (§4) — no function anywhere reads a `RELATED_ONLY`/`NARROWER_THAN` edge as an evidence rule.
- **Retains provenance and ambiguity**: `introduced_in` on every node/edge; `AMBIGUOUS` carries a dedicated `RelationLookup.status`.
- **New relationships never change alignment scores**: `test_no_new_relationship_changes_matching_engine_output` runs the REAL `matching.engine.match_requirement()` against a fixed Docker requirement and an empty candidate profile, builds this milestone's graph in between, and asserts byte-identical output. `test_matcher_and_registry_modules_unchanged_by_import` additionally confirms building a graph never mutates `concepts.registry`'s default registry or `matching.support`'s confidence threshold.

## 6. Representational coverage and limitations (Phase 4/5)

The Phase 4 reference graph (`build_reference_graph()`) is deliberately small and representative, not exhaustive:

- All 17 existing production tags (`ACTIVE`, observability read live off `competency_extraction._COMPETENCY_OBSERVABILITY`).
- v3's 3 pilot concepts (`PROVISIONAL`).
- 2 representative M11-G9 Phase-2b `REJECTED` concepts (`identity-authorization-oauth-oidc`, `robotics-middleware-ros`) — kept visible, not deleted.
- 3 real `TechnicalConcept`s (`infra.docker`, `infra.kubernetes`, `cloud.aws`).
- 1 illustrative `PROVISIONAL` pilot node standing in for "Azure" (not a registered concept today) — built **only** to exercise the AWS/Azure adversarial test named explicitly in this milestone's brief, clearly marked as such, never presented as a reviewed registry proposal.

26 nodes, 6 edges — **every edge in this real-data fixture is `RELATED_ONLY`**, deliberately. This milestone is authorized for data-model design, not for making new hierarchy/equivalence ontology claims about real production concepts (that would be a genuine taxonomy decision outside this bounded scope). Every hierarchy/equivalence/ambiguity/cycle **mechanism** test instead uses clearly-labelled synthetic throwaway nodes (`_synthetic_*` tags), built inline in the test file, never mixed into the real fixture — so nothing in the committed-eligible fixture can be misread as an asserted real-world taxonomy fact.

**Limitation, disclosed**: the model's "no alternative-group node shape" (§5) means a future consumer wanting to relate an alternative-concept GROUP (e.g. "Python or Go") to a third concept cannot yet do so in this graph — `concept_ref_from_normalized_reference()` declines it explicitly rather than silently dropping a group member. Extending the model to support this would be additive (a new, distinct node/edge kind), not a breaking change to what exists today.

## 7. Future extractor interface proposal (Phase 6)

**Decision: Option B — a small standalone `CompetencyConcept` registry with explicit relationship edges.** Option A (extend `TechnicalConcept`/`JobRequirement`/`NormalizedReference` minimally) is insufficient: adding typed cross-namespace relations to any of those would itself be the "modifying public contracts" this milestone is told to avoid, and would conflate concept-identity with claim-instance data `Qualification` already separates cleanly. Option C (also changing the base node models) is unwarranted — the audit (§2) found both existing vocabularies fine for their own existing jobs; only the connective tissue between them was missing, which is squarely Option B's scope.

**What stays outside the graph, by construction** (confirmed structurally, not merely documented): job necessity, repository evidence, candidate evaluation status, overall alignment score. `test_module_never_imports_necessity_evidence_or_scoring_types` greps the module's own source for `Necessity`/`CandidateEvidenceProfile`/`CandidateConceptSummary`/`match_job`/`match_requirement`/`ScoreBreakdown` and asserts none appear.

**Proposed future interface** (sketch only — not implemented, not wired):

```python
class ConceptCandidate(Protocol):
    def to_concept_ref(self) -> ConceptRef: ...
```

Any future extractor — deterministic (today's v1/v2/v3) or a later structured-semantic approach — would only ever need to produce a `ConceptRef` (alongside whatever instance-level `Qualification`/`JobRequirement` fields it already produces today). This graph would classify/relate that ref; it would never need to know which kind of extractor produced it, and scoring/matching remains a third, still entirely untouched layer.

## 8. Scoring-contract compatibility

No `Qualification`/`NormalizedReference`/`JobRequirement`/`TechnicalConcept` field was added or changed. `concept_ref_from_normalized_reference()`/`normalized_reference_from_concept_ref()` read and construct those existing types exactly as shaped today — zero schema migration, confirmed by `git diff --stat HEAD` being empty throughout and by the matcher-output-identity test (§5).

## 9. Historical regression status

Full suite: **1783 passed / 13 skipped / 2 xfailed** (was 1748/13/2 before this milestone; +35 is exactly the new M11-G10 focused test file, zero other change). `src/gitscore` byte-identical to baseline. Parser remains `job_description_parser:v12`. v1/v2/v3 extraction behavior unchanged (confirmed: this milestone never opens `competency_extraction.py`/`competency_aliases.py`/`m11g9_competency_extraction_v3.py` for writing, only reads from them). Matcher/scorer unchanged (confirmed by the matcher-output-identity test). No frozen historical gold (M11-D/F/G5/G9) touched. No API/frontend/public-schema change. No existing passing test skipped or weakened. No third-party posting text appears anywhere in this milestone's files (it never touches job-posting corpora at all — a structural, not incidental, guarantee, since the module imports no corpus/annotation file of any kind).

## 10. Next architecture recommendation

Per M11-G9's own Phase 5 (Option C: fix the ontology/data-model gap before further extraction work), this milestone is exactly that data-model work. Recommended next step: a bounded, still-offline pilot that uses this graph's `RELATED_ONLY` edges to **suppress** a would-be false-equivalence claim in a shadow evaluation (mirroring Milestone 11-B's own "Shadow Integration" precedent for a different model) — i.e., use the graph only to make an existing extractor more conservative where it would otherwise risk conflating two related-but-distinct concepts, never to add a new positive inference. Only after that shadow result is itself evaluated should wiring any part of this graph into live `matching/engine.py` be considered, and that would require its own explicit, reviewed matching-policy decision — not an automatic next step from this milestone.

## 11. Exact changed-file inventory

**New, untracked files this milestone produced** (none staged, none committed):

```
docs/evaluation/MILESTONE_11_G10_COMPETENCY_CONCEPT_MODEL.md      (this document)
scripts/evaluation_lib/m11g10_competency_concept_model.py         (Phase 2-4 data model + reference graph + adapter)
tests/test_m11g10_competency_concept_model.py                     (Phase 3/5/7 focused tests, 35 passing)
```

No report JSON, no corpus, no annotation file — this milestone is pure data-model design/prototyping, with no evaluation corpus of its own. If later approved for commit, all three files above are publication-safe as-is: no third-party text, no private dataset content, no production change.

## 12. Commit-readiness verdict

Design and offline prototype complete, all named safety invariants tested and passing, zero regressions, zero production drift. Per explicit instruction, **STOPPING here — no commit or push performed, M11-G11 not begun.**
