"""Milestone 5D -- requirements.txt and pyproject.toml dependency parsing.

Parses conservatively: only what's needed to recover a package NAME from
a line/entry, never a full re-implementation of pip's requirement-string
grammar or a general TOML/Python-packaging library. Anything that
doesn't cleanly match is skipped rather than guessed at -- a skipped
line degrades this one extractor's evidence for this one file, it never
crashes candidate analysis (Milestone 5D Part 14).

Both formats parse down to the same `DependencyDeclaration` shape
(`dependency_evidence.py`), which is what actually resolves a name to a
concept -- neither parser here talks to the concept registry itself.
"""
from __future__ import annotations

import re
import tomllib

from gitscore.evidence.extraction.dependency_evidence import DependencyDeclaration

EXTRACTOR_VERSION_REQUIREMENTS = "requirements:v1"
EXTRACTOR_VERSION_PYPROJECT = "pyproject:v1"

# A PEP 508-ish package name: starts with a letter/digit, then letters,
# digits, `.`, `_`, `-`. Deliberately not the full PEP 508 grammar (no
# environment markers, no direct URL references) -- see module docstring.
_NAME_PATTERN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)")


def _extract_package_name(requirement_text: str) -> str | None:
    """Pull the bare package name off the front of one PEP 508-ish
    requirement string (e.g. "torch==2.5.0" -> "torch",
    "psycopg2-binary>=2" -> "psycopg2-binary", "fastapi[all]" -> "fastapi").

    Returns None if the string doesn't start with something name-shaped
    at all (e.g. a VCS URL, a bare `.` local-path reference).
    """
    match = _NAME_PATTERN.match(requirement_text)
    if match is None:
        return None
    return match.group(1)


def parse_requirements_txt(text: str) -> list[DependencyDeclaration]:
    """Parse a `requirements.txt` file's text into DependencyDeclarations.

    Handled: bare names (`torch`), version specifiers (`pandas>=2`,
    `torch==2.5`, `fastapi~=0.1`), extras (`fastapi[all]`), comments
    (whole-line `#...` and trailing ` # ...`), blank lines.

    Safely skipped, not crashed on: pip directives (`-r other.txt`,
    `-e .`, `--index-url ...`), VCS/URL requirements (`git+https://...`),
    and any other line that doesn't start with a name-shaped token.
    Neither this function nor its caller ever raises on a malformed or
    unsupported line -- worst case, that one line simply contributes no
    declaration.
    """
    if not text:
        return []

    declarations = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-"):
            # pip option/directive (-r, -e, --index-url, ...) -- not a
            # dependency declaration.
            continue
        if "://" in line:
            # A VCS/URL requirement (git+https://..., https://... .whl,
            # ssh://...) -- not a plain "name[==version]" declaration;
            # _extract_package_name would otherwise happily (and
            # incorrectly) read a package name like "git" or "https" off
            # the front of the scheme.
            continue
        # Strip a trailing inline comment (pip requires whitespace before
        # the `#` for it to count as a comment, not part of the spec).
        line = re.sub(r"\s+#.*$", "", line).strip()
        if not line:
            continue

        package_name = _extract_package_name(line)
        if package_name is None:
            continue

        declarations.append(DependencyDeclaration(package_name=package_name, raw_text=line))
    return declarations


def parse_pyproject_toml(text: str) -> list[DependencyDeclaration]:
    """Parse the bounded subset of `pyproject.toml` this milestone supports:
    PEP 621's `[project] dependencies = [...]` array of PEP 508-ish
    requirement strings.

    Explicitly NOT supported (out of scope -- a deliberately bounded
    parser, not a universal Python packaging tool): Poetry's
    `[tool.poetry.dependencies]` table format (name-keyed, not a string
    array -- a fundamentally different shape), `optional-dependencies`
    groups, PEP 508 environment markers (`; python_version < "3.9"` is
    tolerated because `_extract_package_name` only reads the leading
    name token, but is not evaluated).

    Malformed TOML raises `tomllib.TOMLDecodeError` -- the caller
    (`pipeline.evidence`) is responsible for catching it and recording an
    extractor failure rather than crashing candidate analysis (Milestone
    5D Part 14).
    """
    if not text:
        return []

    parsed = tomllib.loads(text)
    raw_dependencies = parsed.get("project", {}).get("dependencies", [])
    if not isinstance(raw_dependencies, list):
        return []

    declarations = []
    for entry in raw_dependencies:
        if not isinstance(entry, str):
            continue
        package_name = _extract_package_name(entry.strip())
        if package_name is None:
            continue
        declarations.append(DependencyDeclaration(package_name=package_name, raw_text=entry.strip()))
    return declarations
