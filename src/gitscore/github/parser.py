def parse_repo(repo, languages):
    return {
        "name": repo["name"],
        "description": repo["description"],
        "primary_language": repo["language"],
        "languages": languages,
        "stars": repo["stargazers_count"],
        "forks": repo["forks_count"],
        "created_at": repo["created_at"],
        "updated_at": repo["updated_at"],
        "is_fork": repo["fork"],
        "html_url": repo["html_url"],
    }