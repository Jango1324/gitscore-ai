import requests
from gitscore.config import GITHUB_TOKEN


class GitHubClient:
    def get_user(self, username):
        url = f"https://api.github.com/users/{username}"

        headers = {}
        if GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

        response = requests.get(url, headers=headers)

        if response.status_code != 200:
            raise Exception(f"GitHub request failed: {response.status_code}")

        return response.json()