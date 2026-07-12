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
    

    
