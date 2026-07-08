def extract_quality_features(repositories):
    total_stars = 0
    repositories_with_description = 0
    total_repos = len(repositories)
    total_forks = 0
    for repo in repositories:
        total_stars += repo["stars"]
        total_forks += repo["forks"]
        if(repo["description"] is not None or repo["description"] != ""):
            repositories_with_description += 1
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
