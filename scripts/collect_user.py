import sys
from gitscore.github.client import GitHubClient

if len(sys.argv) < 2:
    print("Usage: python scripts/collect_user.py <github_username>")
    sys.exit(1)
username = sys.argv[1]

client = GitHubClient()
data = client.get_user(username)

print(f"Username: {data['login']}")
print(f"Name: {data['name']}")
print(f"Followers: {data['followers']}")
print(f"Public repos: {data['public_repos']}")