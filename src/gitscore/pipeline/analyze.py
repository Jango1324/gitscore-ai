from gitscore.github.client import GitHubClient
from concurrent.futures import ThreadPoolExecutor
from gitscore.github.parser import parse_repo
from gitscore.feautures.profile import extract_profile_features
from gitscore.db.queries import save_user,save_profile_features
from gitscore.scoring.readiness import calculate_readiness_score
import time

def fetch_repo_data(client, username, repo):
    repo_name = repo["name"]
    languages = client.get_repository_languages(username, repo_name)
    readme = client.get_repository_readme(username, repo_name)
    clean_repo = parse_repo(repo, languages, readme)
    return clean_repo


def analyze_user(username):
    start = time.perf_counter()
    # create GitHub client
    client = GitHubClient()

    # fetch user data
    data = client.get_user(username)

    # save/update user
    saved_user = save_user(data)
    # fetch repos
    repos = client.get_repositories(username)

    # build clean_repos
       # for each repo:
        #   fetch languages
        #   fetch README
        #   parse repo
        #   append to clean_repos
    clean_repos = []
    # loops through all the reposistories accessed by the requests (github rest api)
    with ThreadPoolExecutor(max_workers=8) as executor:
        clean_repos = list(
            executor.map(
                lambda repo: fetch_repo_data(client, username, repo),
                repos
        )
    )

    # extract features
    features = extract_profile_features(clean_repos)
    # calculate score
    score = calculate_readiness_score(features)

    # persist feature snapshot
    saved_features = save_profile_features(
    saved_user.id,
    features,
    score
    )
    # return useful result
    elapsed = time.perf_counter() - start
    return{
        "user": saved_user,
        "features":features,
        "score": score,
        "time": elapsed
    }