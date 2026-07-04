import sys
from gitscore.github.client import GitHubClient

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
for repo in repos: # loops through all the reposistories accessed by the requests (github rest api)
    print(f"Repository Name: {repo['name']}")
    print(f"Language: {repo['language']}")
    print(f"Stars: {repo['stargazers_count']}")
    print("-" * 30)

