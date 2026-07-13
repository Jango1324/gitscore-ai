def extract_readme_features(repositories):
    
    total_repositories = len(repositories)
    repositories_with_readme = 0
    total_readme_length = 0
    repositories_with_installation = 0
    repositories_with_usage = 0
    repositories_with_demo = 0
    average_readme_length = 0
    readme_coverage_ratio = 0
    repositories_with_badges = 0
    repositories_with_license = 0
    repositories_with_contributing = 0

    installation_keywords = ["installation", "install", "setup", "getting started"]
    usage_keywords = ["usage", "how to use", "example", "examples"]
    demo_keywords = ["demo", "live site", "deployed", "vercel", "netlify", "render"]
    badge_keywords = ["shields.io", "img.shields.io", "badge"]
    license_keywords = ["license", "mit", "apache", "gpl", "bsd"]  
    contributing_keywords = ["contributing", "contribute"]

    for repo in repositories:
        readme = repo["readme"]
        if not readme:
            continue
        repositories_with_readme += 1
        total_readme_length += len(readme)
        readme_text = readme.lower()
        if any(keyword in readme_text for keyword in installation_keywords):
            repositories_with_installation += 1
        if any(keyword in readme_text for keyword in demo_keywords):
            repositories_with_demo += 1
        if any(keyword in readme_text for keyword in usage_keywords):
            repositories_with_usage += 1
        if any(keyword in readme_text for keyword in badge_keywords):
            repositories_with_badges += 1
        if any(keyword in readme_text for keyword in license_keywords):
            repositories_with_license += 1
        if any(keyword in readme_text for keyword in contributing_keywords):
            repositories_with_contributing += 1
    
    if total_repositories == 0:
        readme_coverage_ratio = 0
    else:
        readme_coverage_ratio = repositories_with_readme / total_repositories
    
    if repositories_with_readme == 0:
        average_readme_length = 0
    else:
        average_readme_length = total_readme_length / repositories_with_readme

    return{
        "repositories_with_readme": repositories_with_readme,
        "readme_coverage_ratio": readme_coverage_ratio,
        "average_readme_length": average_readme_length,
        "repositories_with_installation": repositories_with_installation,
        "repositories_with_usage": repositories_with_usage,
        "repositories_with_demo": repositories_with_demo,
        "repositories_with_badges": repositories_with_badges,
        "repositories_with_license": repositories_with_license,
        "repositories_with_contributing": repositories_with_contributing

    }


