"""Milestone 5D -- shared dependency-declaration -> Evidence conversion.

Every manifest extractor (`python_deps.py`, `js_deps.py`) parses its own
file format into a small, format-agnostic `DependencyDeclaration`, then
hands the list here. This is the ONE place a package/dependency name is
turned into a concept id -- per the milestone instruction to centralize
the mapping as data rather than scattering package-specific conditionals
through parsing code.

Design decision -- no second "package name -> concept" table
(Milestone 5D Part 11): package/dependency names resolve through the
SAME `concepts.registry` aliases every other source uses
(`resolve_concept()`). `torch`, `psycopg2-binary`, etc. are already
registered as aliases of their concept (see `concepts/registry.py`'s
Milestone 5D additions) specifically so this module needs no
independent mapping to maintain or keep in sync.

Milestone 5D.1 note: `resolve_concept()` here intentionally uses a
concept's FULL `aliases`, not `readme_safe_aliases()` -- a manifest
entry (a package.json key, a requirements.txt line) is already a
structured, unambiguous declaration by construction, not free-form
prose, so short aliases like "next" that are unsafe in a README are
exactly correct here. Only `evidence/extraction/readme.py` restricts
itself to the safe subset.

Design decision -- unresolved dependencies are SKIPPED, not turned into
"unresolved:" Evidence (unlike `languages.py`'s `primary_language`
handling): a repository's dependency manifest can list dozens to
hundreds of packages, most of them irrelevant transitive-looking names,
internal/private package names, or simple typos -- turning every single
one into an Evidence row would flood the evidence pool with noise, not
signal, and is exactly what the milestone's "unknown dependencies must
NOT automatically become canonical technical concepts... do not pretend
every dependency is a useful technical concept" instruction warns
against. This mirrors `v1_bridge.py`'s existing topics-skip precedent
(a repository's topics are also a free-form, potentially-noisy list),
not its primary_language precedent (a single, well-defined, always-
worth-recording field). Unknown names are still surfaced -- as a plain
list returned alongside the Evidence, for a caller to report as a
diagnostic (Milestone 5D Part 17/19) -- just never written into the
registry or the Evidence pool.
"""
from __future__ import annotations

from dataclasses import dataclass

from gitscore.concepts.registry import resolve_concept
from gitscore.evidence.models import Evidence, RepositoryIdentity
from gitscore.evidence.types import ConfidenceLevel, EvidenceType


@dataclass(frozen=True)
class DependencyDeclaration:
    """One parsed dependency line/entry, before concept resolution.

    `raw_text` is the bounded, human-readable observation to preserve as
    provenance (e.g. `"torch==2.5.0"`, `"react (dependencies)"`) --
    format-specific parsers decide exactly what this looks like.
    """

    package_name: str
    raw_text: str


def declarations_to_evidence(
    owner: str,
    repo_name: str,
    declarations: list[DependencyDeclaration],
    *,
    file_path: str,
    extractor_version: str,
    evidence_type: EvidenceType = EvidenceType.DEPENDENCY,
    confidence: ConfidenceLevel = ConfidenceLevel.STRONG,
) -> tuple[list[Evidence], list[str]]:
    """Resolve each declaration and split into (Evidence, unknown names).

    A dependency manifest declaration is high-confidence by construction
    (Milestone 5D Part 13) -- it is a real, buildable/installable
    dependency the repository's own tooling declares, not a loose textual
    mention (contrast README evidence's MODERATE confidence).
    """
    evidence: list[Evidence] = []
    unknown_names: list[str] = []
    for declaration in declarations:
        resolution = resolve_concept(declaration.package_name)
        if not resolution.matched:
            unknown_names.append(declaration.package_name)
            continue
        evidence.append(
            Evidence(
                repository=RepositoryIdentity(owner=owner, name=repo_name),
                evidence_type=evidence_type,
                raw_observation=declaration.raw_text,
                concept_id=resolution.concept_id,
                confidence=confidence,
                extractor_version=extractor_version,
                file_path=file_path,
            )
        )
    return evidence, unknown_names
