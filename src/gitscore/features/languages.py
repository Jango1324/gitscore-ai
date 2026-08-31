def extract_language_features(repositories):
    all_languages = {}
    for repo in repositories:
        for language in repo["languages"]:
            if language not in all_languages:
                all_languages[language] = 0
            all_languages[language] += 1
    unique_language_count = len(all_languages)
    if all_languages:
        most_used_language = max(all_languages, key=all_languages.get)
    else:
        # No repositories, or none report language data: "" is the
        # deterministic "no language data available" sentinel.
        # (most_used_language is a non-nullable DB column, so None
        # is not an option here.)
        most_used_language = ""
    python_repository_count = all_languages.get("Python", 0)
    typescript_repository_count = all_languages.get("TypeScript", 0)
    has_python = python_repository_count> 0
    has_typescript = typescript_repository_count > 0
    return {
    "unique_language_count": unique_language_count,
    "most_used_language": most_used_language,
    "python_repository_count": python_repository_count,
    "typescript_repository_count": typescript_repository_count,
    "has_python": has_python,
    "has_typescript": has_typescript
}


