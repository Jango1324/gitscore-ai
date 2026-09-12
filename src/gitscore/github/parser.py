def parse_repo(repo, languages, readme):
    return {
        "name": repo["name"],
        "description": repo["description"],
        "primary_language": repo["language"],
        "languages": parse_languages(languages),
        "stars": repo["stargazers_count"],
        "forks": repo["forks_count"],
        "created_at": repo["created_at"],
        "updated_at": repo["updated_at"],
        "is_fork": repo["fork"],
        "html_url": repo["html_url"],
        "readme": readme
    }

def parse_languages(languages):
    if not languages:
        return {}
    total = sum(languages.values())
    percentages = {}

    for language, bytes_of_code in languages.items():
        percentages[language] = round((bytes_of_code / total) * 100,2)
    return percentages


def parse_repo_summary(repo):
    """Extract repository-ranking fields from a raw repo-list entry.

    Unlike parse_repo(), this needs only the payload already returned by
    GitHubClient.get_repositories() -- no per-repository languages/README
    fetch, so it costs zero additional API requests. Used by
    gitscore.ranking (Milestone 5B) to decide which repositories are worth
    a deep per-repository fetch in the first place, before any such fetch
    happens.

    `archived`, `size`, `pushed_at`, and `topics` are present on every
    entry GitHub's repos-list endpoint already returns (verified against
    the live API) -- they are simply not read by parse_repo() today.
    """
    return {
        "name": repo["name"],
        "description": repo["description"],
        "primary_language": repo["language"],
        "is_fork": repo["fork"],
        "archived": repo.get("archived", False),
        "size_kb": repo.get("size") or 0,
        "stars": repo["stargazers_count"],
        "forks": repo["forks_count"],
        "topics": repo.get("topics") or [],
        "created_at": repo["created_at"],
        "updated_at": repo["updated_at"],
        "pushed_at": repo.get("pushed_at"),
        "html_url": repo["html_url"],
    }

