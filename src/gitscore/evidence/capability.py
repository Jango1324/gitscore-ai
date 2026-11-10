"""Milestone 11-G19 -- the evidence-assessment CAPABILITY contract.

Answers exactly one question, for ONE concept id, without ever looking at
a candidate: can any of GitScore's existing evidence extractors EVER emit
evidence carrying this concept id? It is a statement about the
extractors, not about any person -- "capability" (could evidence exist?)
is deliberately kept apart from "evidence" (does this candidate have
it?), which remains `matching.support.has_sufficient_evidence`'s job.

Consumed by `assessment.models` to decide which requirements may enter the
GitHub Evidence Alignment numerator/denominator (scoring v2; see
docs/evaluation/MILESTONE_11_G19_OBSERVABILITY_SCORING_V2.md). Internal:
no API, schema or matcher type exposes `Capability` directly.

Source of truth -- the extractors themselves, read here, never re-declared
as a separate concept list:

| Pathway | Extractor | Declares coverage of |
|---|---|---|
| `README_MENTION` | `evidence/extraction/readme.py` scans `concept.readme_safe_aliases()` for every registry concept | a concept with >= 1 README-safe alias |
| `REPOSITORY_LANGUAGE` | `evidence/extraction/languages.py` resolves GitHub language-stats names through the registry | a concept the registry itself categorizes as `"language"` (the Milestone 5D set added precisely so language names resolve) |
| `DOCKER_FILES` | `evidence/extraction/docker.py` | `docker.DOCKER_CONCEPT_ID` only |

Deliberately NOT a capability ground: dependency manifests
(`dependency_evidence.py`). They resolve ARBITRARY package names through
every alias, so they cannot establish, candidate-independently, that any
particular concept is reachable; counting them would make every
registered concept "assessable" by registration alone.

Three states:
* `ASSESSABLE` -- at least one pathway above covers the concept.
* `NOT_ASSESSABLE` -- a registered concept no pathway covers, or an id
  that is neither registered nor an `unresolved:` placeholder. A future
  concept added without detector coverage lands here automatically.
* `UNRESOLVED` -- an `unresolved:<term>` id. Only the language extractor
  emits such ids, and only for GitHub-reported language names; nothing in
  the repository declares which terms those are, so the question cannot
  be decided. Treated conservatively (never scoreable). Evidence the
  language extractor DOES emit for such ids still reaches the matcher and
  stays visible -- capability gates scoring only, never matching.

Pure and deterministic: same concept id (and registry) in, same decision
out, with an explicit reason for every decision.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from gitscore.concepts.registry import ConceptRegistry, default_registry, is_unresolved_concept_id
from gitscore.evidence.extraction.docker import DOCKER_CONCEPT_ID

# The registry category whose concepts `languages.py` exists to resolve
# (concepts/registry.py, Milestone 5D additions). Read from the registry,
# never a list of language names.
REPOSITORY_LANGUAGE_CATEGORY = "language"


class Capability(str, Enum):
    ASSESSABLE = "assessable"
    NOT_ASSESSABLE = "not_assessable"
    UNRESOLVED = "unresolved"


class EvidencePathway(str, Enum):
    README_MENTION = "readme_mention"
    REPOSITORY_LANGUAGE = "repository_language"
    DOCKER_FILES = "docker_files"


@dataclass(frozen=True)
class CapabilityDecision:
    concept_id: str
    capability: Capability
    pathways: tuple[EvidencePathway, ...]
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.reasons:
            raise ValueError(f"{self.concept_id}: every capability decision needs a reason")
        if (self.capability == Capability.ASSESSABLE) != bool(self.pathways):
            raise ValueError(f"{self.concept_id}: ASSESSABLE iff at least one evidence pathway")


def concept_capability(concept_id: str, registry: ConceptRegistry | None = None) -> CapabilityDecision:
    """The capability decision for ONE concept id. Never sees a candidate."""
    registry = registry or default_registry()
    if is_unresolved_concept_id(concept_id):
        return CapabilityDecision(
            concept_id, Capability.UNRESOLVED, (),
            ("outside the concept registry; only the GitHub language-stats extractor emits unresolved ids, and "
             "no declared vocabulary says whether this term is a GitHub-reported language",))
    concept = registry.get(concept_id)
    if concept is None:
        return CapabilityDecision(concept_id, Capability.NOT_ASSESSABLE, (),
                                  ("neither a registered concept nor an unresolved placeholder",))
    pathways: list[EvidencePathway] = []
    reasons: list[str] = []
    safe = concept.readme_safe_aliases()
    if safe:
        pathways.append(EvidencePathway.README_MENTION)
        reasons.append("README extractor scans its README-safe aliases: " + ", ".join(safe))
    if concept.category == REPOSITORY_LANGUAGE_CATEGORY:
        pathways.append(EvidencePathway.REPOSITORY_LANGUAGE)
        reasons.append("registry category 'language': GitHub language statistics resolve to it")
    if concept_id == DOCKER_CONCEPT_ID:
        pathways.append(EvidencePathway.DOCKER_FILES)
        reasons.append("Docker file detector emits it")
    if not pathways:
        return CapabilityDecision(concept_id, Capability.NOT_ASSESSABLE, (),
                                  ("registered, but no evidence extractor declares coverage of it",))
    return CapabilityDecision(concept_id, Capability.ASSESSABLE, tuple(pathways), tuple(reasons))
