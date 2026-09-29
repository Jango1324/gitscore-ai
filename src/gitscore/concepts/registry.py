"""Milestone 5C -- the technical concept registry and resolver.

A SMALL, REPRESENTATIVE set of concepts proving the mechanism, not a
complete ontology (per the Milestone 5C instructions: "the important
thing is the mechanism, not the number of concepts"). Adding a new
concept is adding one entry to _CONCEPTS below -- no change to
normalize.py, ConceptRegistry, or resolve_concept.

Bump CONCEPT_REGISTRY_VERSION whenever:
  - a concept is added, renamed, or merged/deprecated,
  - normalize.py's normalization rules change (that changes which
    aliases resolve), or
  - a concept's alias-safety metadata changes (`readme_unsafe_aliases`)
    -- this doesn't change what `resolve_concept()` matches, but it does
    change what the registry's data means for consumers that read it
    (see models.py's `TechnicalConcept.readme_safe_aliases()`), which is
    exactly the kind of registry-content change this version exists to
    track.
Never touch SCORING_RUBRIC_VERSION, DATASET_VERSION (dataset/schema.py),
or REPOSITORY_RANKING_VERSION (ranking/config.py) for any of this --
this registry is an independent concern.

The registry is built ONCE at import time and never mutated afterward.
Unknown terms (see resolve_concept) are represented explicitly; they are
never written into this registry (architectural rule: no dynamic
registry mutation from unrecognized input).
"""
from __future__ import annotations

from dataclasses import dataclass

from gitscore.concepts.models import TechnicalConcept
from gitscore.concepts.normalize import normalize_term

CONCEPT_REGISTRY_VERSION = 3

# A small, representative registry spanning several categories -- proves
# the mechanism (data-driven, no if/elif ladder) without building a full
# ontology. Aliases are the raw, human-typed forms; normalize_term()
# is applied to them (and to lookup terms) before comparison, so an
# alias here does not need to already be lowercase/punctuation-free.
#
# Milestone 5D additions (see docs/CHANGELOG_DEV.md's Milestone 5D entry):
# a representative set of GitHub-reported languages (so
# evidence/extraction/languages.py has something to resolve real language
# names against) plus a handful of dependency-manifest-only concepts
# (frameworks/ORMs that only ever show up as a package name, never as a
# GitHub "language"). Package/dependency names resolve through THESE SAME
# aliases via resolve_concept() -- Milestone 5D does not maintain a
# second, separate "package name -> concept" table; see
# evidence/extraction/dependency_evidence.py.
#
# Milestone 5D.1: a handful of these aliases ("go", "next", "js", "ts",
# the bare "c") are also common/short enough to collide with ordinary
# English in free-form README prose (see the real-world false positives
# this milestone fixed, in docs/CHANGELOG_DEV.md). Those are marked
# `readme_unsafe_aliases` on the concept below -- they remain valid
# `resolve_concept()` aliases for structured sources (a package.json
# key, a GitHub language-stats name), just excluded from
# evidence/extraction/readme.py's matching. See models.py's
# `TechnicalConcept.readme_safe_aliases()` for the mechanism.
_CONCEPTS: tuple[TechnicalConcept, ...] = (
    TechnicalConcept(
        concept_id="language.python",
        display_name="Python",
        category="language",
        aliases=("python", "python3"),
    ),
    TechnicalConcept(
        concept_id="language.javascript",
        display_name="JavaScript",
        category="language",
        aliases=("javascript", "js"),
        # "js" is a legitimate package/language-stats shorthand but is
        # also the suffix of ".js"-named frameworks (Next.js, Vue.js,
        # Node.js) -- the boundary regex treats "." as a valid separator,
        # so a bare "js" alias would give every one of those README
        # mentions incidental JavaScript evidence. "javascript" (the full
        # word) is unambiguous and stays README-safe.
        readme_unsafe_aliases=frozenset({"js"}),
    ),
    TechnicalConcept(
        concept_id="language.typescript",
        display_name="TypeScript",
        category="language",
        aliases=("typescript", "ts"),
        # Same short-alias risk as "js" above (e.g. common non-code
        # abbreviations); "typescript" alone is README-safe.
        readme_unsafe_aliases=frozenset({"ts"}),
    ),
    TechnicalConcept(
        concept_id="language.java",
        display_name="Java",
        category="language",
        aliases=("java",),
    ),
    TechnicalConcept(
        concept_id="language.c",
        display_name="C",
        category="language",
        aliases=("c",),
        # "c" is a single letter -- there is no literal, deterministic
        # way to tell it apart from ordinary prose ("plan a, b, or c").
        # It has no other alias to fall back to, so language.c produces
        # NO README evidence at all (readme_safe_aliases() is empty for
        # this concept) -- a documented limitation, not a bug. GitHub
        # language-stats extraction (languages.py), which resolves
        # against the SAME alias unaffected by this restriction, remains
        # the practical source of C evidence.
        readme_unsafe_aliases=frozenset({"c"}),
    ),
    TechnicalConcept(
        concept_id="language.cpp",
        display_name="C++",
        category="language",
        aliases=("c++", "cpp"),
    ),
    TechnicalConcept(
        concept_id="language.csharp",
        display_name="C#",
        category="language",
        aliases=("c#", "csharp"),
    ),
    TechnicalConcept(
        concept_id="language.go",
        display_name="Go",
        category="language",
        aliases=("go", "golang"),
        # Bare "go" is both the language name and an ordinary English
        # verb ("I go for...", "let it go") -- literally indistinguishable
        # to context-free, boundary-only matching (Milestone 5D real-world
        # validation, torvalds/1590A and karpathy/autoresearch both hit
        # this). "go" stays a valid resolve_concept() alias (GitHub's
        # language-stats name for this language IS "Go", and that's a
        # structured, always-safe source) but is excluded from README
        # prose matching. "golang" is unambiguous and stays README-safe --
        # "Written in Golang" still produces evidence; bare "Written in
        # Go" intentionally does not (prefer precision over a guess).
        readme_unsafe_aliases=frozenset({"go"}),
    ),
    TechnicalConcept(
        concept_id="language.rust",
        display_name="Rust",
        category="language",
        aliases=("rust",),
    ),
    TechnicalConcept(
        concept_id="language.ruby",
        display_name="Ruby",
        category="language",
        aliases=("ruby",),
    ),
    TechnicalConcept(
        concept_id="language.php",
        display_name="PHP",
        category="language",
        aliases=("php",),
    ),
    TechnicalConcept(
        concept_id="language.shell",
        display_name="Shell",
        category="language",
        aliases=("shell", "bash", "shell script"),
    ),
    TechnicalConcept(
        concept_id="language.html",
        display_name="HTML",
        category="language",
        aliases=("html",),
    ),
    TechnicalConcept(
        concept_id="language.css",
        display_name="CSS",
        category="language",
        aliases=("css",),
    ),
    TechnicalConcept(
        concept_id="language.jupyter_notebook",
        display_name="Jupyter Notebook",
        category="language",
        aliases=("jupyter notebook", "ipynb"),
    ),
    TechnicalConcept(
        concept_id="database.postgresql",
        display_name="PostgreSQL",
        category="database",
        aliases=("postgresql", "postgres", "psql", "psycopg2", "psycopg2-binary", "psycopg"),
    ),
    TechnicalConcept(
        concept_id="database.redis",
        display_name="Redis",
        category="database",
        aliases=("redis",),
    ),
    TechnicalConcept(
        concept_id="ml.framework.pytorch",
        display_name="PyTorch",
        category="ml_framework",
        aliases=("pytorch", "torch"),
    ),
    TechnicalConcept(
        concept_id="ml.framework.tensorflow",
        display_name="TensorFlow",
        category="ml_framework",
        aliases=("tensorflow",),
    ),
    TechnicalConcept(
        concept_id="data.library.pandas",
        display_name="pandas",
        category="data_library",
        aliases=("pandas",),
    ),
    TechnicalConcept(
        concept_id="framework.react",
        display_name="React",
        category="frontend_framework",
        aliases=("react", "react.js", "reactjs"),
    ),
    TechnicalConcept(
        concept_id="framework.nextjs",
        display_name="Next.js",
        category="frontend_framework",
        # "next" (bare) is the real, literal npm package name
        # `package.json`'s "dependencies" declares Next.js under, so it
        # stays a resolve_concept() alias -- structured dependency
        # evidence needs it (Milestone 5D Part 11: dependency names
        # resolve through this SAME table, no second package-name
        # mapping). But it is ALSO ordinary English ("Next Track", "next
        # steps" -- observed live on
        # Jango1324/Arduino-Based-Media-Player, Milestone 5D real-world
        # validation), so Milestone 5D.1 excludes it from README prose
        # matching specifically: "next.js"/"nextjs" (unambiguous,
        # punctuation- or case-distinguished forms) remain README-safe,
        # so "Uses Next.js" still produces evidence. See
        # docs/CHANGELOG_DEV.md's Milestone 5D.1 entry.
        aliases=("next", "next.js", "nextjs"),
        readme_unsafe_aliases=frozenset({"next"}),
    ),
    TechnicalConcept(
        concept_id="framework.express",
        display_name="Express",
        category="backend_framework",
        aliases=("express", "express.js", "expressjs"),
    ),
    TechnicalConcept(
        concept_id="framework.nestjs",
        display_name="NestJS",
        category="backend_framework",
        aliases=("nestjs", "nest.js", "@nestjs"),
    ),
    TechnicalConcept(
        concept_id="framework.fastapi",
        display_name="FastAPI",
        category="backend_framework",
        aliases=("fastapi",),
    ),
    TechnicalConcept(
        concept_id="framework.flask",
        display_name="Flask",
        category="backend_framework",
        aliases=("flask",),
    ),
    TechnicalConcept(
        concept_id="orm.prisma",
        display_name="Prisma",
        category="orm",
        aliases=("prisma", "@prisma"),
    ),
    TechnicalConcept(
        concept_id="infra.docker",
        display_name="Docker",
        category="infrastructure",
        aliases=("docker", "dockerfile"),
    ),
    TechnicalConcept(
        concept_id="cloud.aws",
        display_name="AWS",
        category="cloud",
        aliases=("aws", "amazon web services"),
    ),
    TechnicalConcept(
        concept_id="platform.cuda",
        display_name="CUDA",
        category="platform",
        aliases=("cuda",),
    ),
    TechnicalConcept(
        concept_id="robotics.ros2",
        display_name="ROS2",
        category="robotics",
        aliases=("ros2", "ros 2"),
    ),
    TechnicalConcept(
        concept_id="embedded.rtos.freertos",
        display_name="FreeRTOS",
        category="embedded",
        aliases=("freertos",),
        parent_id="embedded.rtos",
    ),
    TechnicalConcept(
        concept_id="hdl.verilog",
        display_name="Verilog",
        category="hardware_description",
        aliases=("verilog",),
    ),
    TechnicalConcept(
        concept_id="toolchain.llvm",
        display_name="LLVM",
        category="compiler_toolchain",
        aliases=("llvm",),
    ),
)


class ConceptRegistry:
    """An immutable, in-memory index over a fixed set of TechnicalConcepts.

    Built once at construction; never mutated afterward.
    """

    def __init__(self, concepts):
        self._by_id = {concept.concept_id: concept for concept in concepts}
        self._by_normalized_alias: dict[str, TechnicalConcept] = {}
        for concept in concepts:
            for alias in concept.aliases:
                self._by_normalized_alias[normalize_term(alias)] = concept

    def get(self, concept_id: str) -> TechnicalConcept | None:
        return self._by_id.get(concept_id)

    def lookup_by_normalized_alias(self, normalized_alias: str) -> TechnicalConcept | None:
        return self._by_normalized_alias.get(normalized_alias)

    def all_concepts(self) -> tuple[TechnicalConcept, ...]:
        return tuple(self._by_id.values())


_DEFAULT_REGISTRY = ConceptRegistry(_CONCEPTS)


def default_registry() -> ConceptRegistry:
    """The shared, immutable default registry instance."""
    return _DEFAULT_REGISTRY


_UNRESOLVED_PREFIX = "unresolved:"


def unresolved_concept_id(term: str) -> str:
    """A deterministic pseudo-concept-id for a term with no registry match.

    The SAME literal term always produces the SAME unresolved id (useful
    later for tallying which unknown terms show up most, for registry
    curation) -- but two differently-spelled unknown terms referring to
    the same real thing are NOT merged. That would require exactly the
    fuzzy-matching/ontology-building work this milestone is scoped to
    avoid.
    """
    return _UNRESOLVED_PREFIX + normalize_term(term).replace(" ", "_")


def is_unresolved_concept_id(concept_id: str) -> bool:
    return concept_id.startswith(_UNRESOLVED_PREFIX)


@dataclass(frozen=True)
class ConceptResolution:
    """The outcome of resolving one raw term against the registry.

    `matched` is the explicit, checkable result Milestone 5C Part 3
    asks for. `concept_id` is always populated regardless of `matched`
    -- callers that just need an id to attach to an Evidence record
    never have to branch on `matched` themselves (see
    is_unresolved_concept_id() when they do need to check).
    """

    raw_term: str
    normalized_term: str
    matched: bool
    concept: TechnicalConcept | None

    @property
    def concept_id(self) -> str:
        if self.matched:
            return self.concept.concept_id
        return unresolved_concept_id(self.raw_term)


def resolve_concept(term: str, registry: ConceptRegistry | None = None) -> ConceptResolution:
    """Resolve one raw term to a TechnicalConcept, deterministically.

    No LLM, no fuzzy matching -- exact match against normalized aliases
    only (Milestone 5C Part 3: "Normalization must NOT use an LLM").
    An unmatched term is never dropped and never written into the
    registry -- see ConceptResolution.concept_id / unresolved_concept_id.
    """
    registry = registry or default_registry()
    normalized = normalize_term(term)
    concept = registry.lookup_by_normalized_alias(normalized)
    return ConceptResolution(
        raw_term=term,
        normalized_term=normalized,
        matched=concept is not None,
        concept=concept,
    )
