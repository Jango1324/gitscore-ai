def extract_quality_features(repositories):
    total_stars = 0
    repositories_with_description = 0
    total_repos = len(repositories)
    total_forks = 0
    for repo in repositories:
        total_stars += repo["stars"]
        total_forks += repo["forks"]
        description = repo["description"]
        # A description only counts if it's present AND non-blank.
        # (Previously used `or`, which was always True regardless of
        # the actual description, so this ratio was always 1.0.)
        if description is not None and description.strip() != "":
            repositories_with_description += 1

    if total_repos == 0:
        # No repositories to measure: 0 is the deterministic "no data"
        # value, consistent with readme.py's empty-profile handling.
        average_stars = 0
        average_forks = 0
        description_coverage_ratio = 0
    else:
        average_stars = total_stars/total_repos
        average_forks = total_forks/total_repos
        description_coverage_ratio = repositories_with_description/total_repos
    return{
        "total_stars": total_stars,
        "average_stars": average_stars,
        "total_forks": total_forks,
        "average_forks": average_forks,
        "repositories_with_description": repositories_with_description,
        "description_coverage_ratio": description_coverage_ratio
    }
