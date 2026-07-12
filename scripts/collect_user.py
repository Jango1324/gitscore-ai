import sys
from gitscore.github.client import GitHubClient
from gitscore.github.parser import parse_repo
from gitscore.feautures.profile import extract_profile_features


if len(sys.argv) < 2:
    print("Usage: python scripts/collect_user.py <github_username>")
    sys.exit(1)
username = sys.argv[1]

client = GitHubClient()
data = client.get_user(username)
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
    print(f"Has README: {repo['readme'] is not None}")
    print(f"README length: {len(repo['readme']) if repo['readme'] else 0}")

features = extract_profile_features(clean_repos)
print(features)