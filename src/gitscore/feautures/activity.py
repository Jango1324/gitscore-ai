def extract_activity_features(repositories):
    total_repositories = len(repositories)
    forked_repositories = 0

    for repo in repositories:
        if(repo["is_fork"]):
            forked_repositories += 1  
    original_repositories  = total_repositories - forked_repositories
    return {
        "total_repos": total_repositories,
        "forked_repos": forked_repositories,
         "original_repos": original_repositories

    }



    

