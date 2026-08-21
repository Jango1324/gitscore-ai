import sys
from gitscore.github.client import GitHubClient
from gitscore.github.parser import parse_repo
from gitscore.feautures.profile import extract_profile_features
from gitscore.db.queries import save_user,save_profile_features
from gitscore.scoring.readiness import calculate_readiness_score


if len(sys.argv) < 2:
    print("Usage: python scripts/collect_user.py <github_username>")
    sys.exit(1)
username = sys.argv[1]

client = GitHubClient()
data = client.get_user(username)
saved_user = save_user(data)
repos = client.get_repositories(username)

print(f"Username: {data['login']}")
print(f"Name: {data['name']}")
print(f"Followers: {data['followers']}")
print(f"Public repos: {data['public_repos']}")
clean_repos = []
for repo in repos: # loops through all the reposistories accessed by the requests (github rest api)
    repo_name = repo["name"]
    languages = client.get_repository_languages(username, repo_name)
    readme = client.get_repository_readme(username, repo_name)
    clean_repo = parse_repo(repo, languages, readme)
    clean_repos.append(clean_repo)


for repo in clean_repos:
    print(f"Repository: {repo['name']}")
    print(f"Description: {repo['description']}")
    print(f"Primary Language: {repo['primary_language']}")
    print(f"Languages: {repo['languages']}" )
    print(f"Stars: {repo['stars']}")
    print(f"Forks: {repo['forks']}")
    print(f"Updated: {repo['updated_at']}")
    print(f"URL: {repo['html_url']}")
    print("-" * 40)

features = extract_profile_features(clean_repos)
score = calculate_readiness_score(features)
print(
f"{"total_score: "}{score["total_score"]}",
f"{"ml experience: "}  {score["ml_experience"]}",
f"{"project_originality: "} {score['project_originality']}",
f"{"documentation_quality: "}  {score['documentation_quality']}",
f"{"language_tool_relevance: "}  {score['language_tool_relevance']}",
f"{"community_signal: "}  {score['community_signal']}")

saved_features = save_profile_features(
    saved_user.id,
    features,
    score
)
print(features)
print(
    "Saved feature snapshot:",
    saved_features.id,
    saved_features.user_id,
    saved_features.total_repos
)