"""Parse the batch-collection username file used by
``scripts/collect_dataset.py``.

Format (see ``data/collection/usernames.example.txt``):

- one GitHub username per line
- blank / whitespace-only lines are ignored
- a line whose first non-space character is ``#`` is a comment, ignored
- text after a ``#`` elsewhere on a line is an inline comment, stripped
  (a GitHub username can't contain ``#``)
- duplicates are removed case-insensitively; the first spelling wins
"""
from __future__ import annotations

from pathlib import Path


class UsernameFileError(Exception):
    """The username file is missing or unreadable."""


def parse_usernames(text: str) -> list[str]:
    """Parse file contents into a de-duplicated, order-preserving list."""
    seen: set[str] = set()
    usernames: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "#" in line:
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
        # A GitHub username has no internal whitespace; if a line has
        # trailing junk, take the first token rather than guess.
        token = line.split()[0]
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        usernames.append(token)

    return usernames


def load_username_file(path) -> list[str]:
    """Read and parse ``path``. Raises ``UsernameFileError`` if it is absent."""
    file_path = Path(path)
    if not file_path.exists():
        raise UsernameFileError(
            f"username file not found: {file_path}\n"
            "Copy data/collection/usernames.example.txt to "
            f"{file_path} and add one GitHub username per line."
        )
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - unusual IO failure
        raise UsernameFileError(f"could not read {file_path}: {exc}") from exc
    return parse_usernames(text)
