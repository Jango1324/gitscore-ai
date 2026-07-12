import requests
from gitscore.config import GITHUB_TOKEN
import base64


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
    def get_repositories(self, username):
        url = f"https://api.github.com/users/{username}/repos"
        headers = { "Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}
        headers = {}
        if GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

        response = requests.get(url, headers=headers)

        if response.status_code != 200:
            raise Exception(f"GitHub repositories request failed: {response.status_code}")
        
        return response.json()
    def get_repository_languages(self, owner, repo):
        url = f"https://api.github.com/repos/{owner}/{repo}/languages"
        headers = { "Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}
        headers = {}
        if GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

        response = requests.get(url, headers=headers)

        if response.status_code != 200:
            raise Exception(f"GitHub repositories request failed: {response.status_code}")
        
        return response.json()
    
    def get_repository_readme(self, owner, repo_name):
        url = f"https://api.github.com/repos/{owner}/{repo_name}/readme"
        headers = { "Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}
        headers = {}
        if GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            data =  response.json()
            decoded_bytes = base64.b64decode(data["content"])
            original_readme = decoded_bytes.decode('utf-8')
            return original_readme
        
        if response.status_code == 404:
            return None
        raise Exception(f"GitHub repositories request failed: {response.status_code}")
        
