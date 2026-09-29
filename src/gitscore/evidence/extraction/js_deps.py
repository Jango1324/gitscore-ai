"""Milestone 5D -- package.json dependency parsing.

Reads only `dependencies` and `devDependencies` -- no lockfile parsing,
no `peerDependencies`/`optionalDependencies` (a small, deliberately
bounded slice, matching the milestone's `requirements.txt`/`pyproject.toml`
scope on the Python side).
"""
from __future__ import annotations

import json

from gitscore.evidence.extraction.dependency_evidence import DependencyDeclaration

EXTRACTOR_VERSION = "npm:v1"

_DEPENDENCY_KEYS = ("dependencies", "devDependencies")


def parse_package_json(text: str) -> list[DependencyDeclaration]:
    """Parse `package.json` text into DependencyDeclarations.

    Deterministic same-package-in-both-sections policy (Milestone 5D
    Part 9): `dependencies` is treated as canonical. A package listed in
    BOTH `dependencies` and `devDependencies` produces exactly one
    declaration, from `dependencies` -- `devDependencies` is only
    consulted for package names not already seen in `dependencies`.

    Malformed JSON raises `json.JSONDecodeError` -- the caller
    (`pipeline.evidence`) catches it and records an extractor failure
    rather than crashing candidate analysis (Milestone 5D Part 14).
    """
    if not text:
        return []

    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        return []

    declarations = []
    seen_names: set[str] = set()
    for section in _DEPENDENCY_KEYS:
        entries = parsed.get(section)
        if not isinstance(entries, dict):
            continue
        for name, version in entries.items():
            if not isinstance(name, str) or name in seen_names:
                continue
            seen_names.add(name)
            version_text = version if isinstance(version, str) else str(version)
            declarations.append(
                DependencyDeclaration(
                    package_name=name,
                    raw_text=f"{name}@{version_text} ({section})",
                )
            )
    return declarations
