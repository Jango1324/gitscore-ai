"""Milestone 5D -- bounded root-file discovery.

One call to `GitHubClient.get_repository_root_contents()` per selected
repository returns every root-level entry in a single request. This
module is the pure, in-memory filter over that response: which of the
small set of manifest/Docker filenames this milestone supports are
actually present, and at what path.

Deliberately non-recursive -- only entries returned by the ROOT listing
are considered. A `requirements.txt` living in a subdirectory (e.g.
`backend/requirements.txt`) is out of scope; see the milestone's "no
recursive repository crawling" rule.
"""
from __future__ import annotations

SUPPORTED_ROOT_FILENAMES = (
    "requirements.txt",
    "pyproject.toml",
    "package.json",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
)

DOCKER_FILENAMES = (
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
)

_SUPPORTED_SET = frozenset(SUPPORTED_ROOT_FILENAMES)


def discover_supported_root_files(root_entries) -> dict[str, str]:
    """Filter a root-contents listing down to the supported filenames present.

    `root_entries` is shaped like `GitHubClient.get_repository_root_contents()`'s
    return value -- a list of GitHub Contents-API entries, each a dict with
    at least `name`, `path`, `type` ("file" or "dir"). Directories (and any
    unsupported filename) are ignored; matching is on the exact,
    case-sensitive root filename -- GitHub filenames are case-sensitive on
    the filesystems repositories are actually checked out on, so
    `dockerfile` != `Dockerfile`.

    Returns `{filename: path}` -- `path` is carried separately (rather than
    assuming `path == filename`) purely for forward-compatibility with the
    Contents API's own `path` field; for a root-level file the two are
    always equal today.
    """
    found: dict[str, str] = {}
    for entry in root_entries or ():
        if entry.get("type") != "file":
            continue
        name = entry.get("name")
        if name in _SUPPORTED_SET:
            found[name] = entry.get("path") or name
    return found
