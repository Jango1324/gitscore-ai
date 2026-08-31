import base64
import logging
import time

import requests

from gitscore.config import GITHUB_TOKEN
from gitscore.github.exceptions import (
    GitHubNotFoundError,
    GitHubRateLimitError,
    GitHubRequestError,
)

logger = logging.getLogger(__name__)

# GitHub's own median response time is well under a second; 10s gives
# generous headroom for slow responses/proxies without letting a hung
# connection block a worker thread indefinitely.
DEFAULT_TIMEOUT_SECONDS = 10.0

# Bounded exponential backoff: 0.5s, 1s, 2s, ... capped at 8s, up to
# DEFAULT_MAX_RETRIES retries (i.e. up to 4 attempts total) per request.
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE_SECONDS = 0.5
DEFAULT_MAX_BACKOFF_SECONDS = 8.0

# GitHub's REST repo-list endpoint accepts per_page up to 100.
DEFAULT_PER_PAGE = 100
# Safety cap on page count so a server-side bug (e.g. always returning a
# full page) can't turn pagination into an infinite loop. 50 pages *
# 100 per_page = 5000 repos, comfortably above any real user's repo
# count.
DEFAULT_MAX_PAGES = 50

# Only retry failures that are plausibly transient. A 5xx here means
# GitHub/its edge infrastructure had a momentary problem; 404s and other
# 4xx codes are genuine, stable outcomes and must not be retried.
RETRYABLE_STATUS_CODES = {500, 502, 503, 504}


class GitHubClient:
    def __init__(
        self,
        timeout=DEFAULT_TIMEOUT_SECONDS,
        max_retries=DEFAULT_MAX_RETRIES,
        backoff_base=DEFAULT_BACKOFF_BASE_SECONDS,
        max_backoff=DEFAULT_MAX_BACKOFF_SECONDS,
        sleep_func=time.sleep,
    ):
        self.session = requests.Session()
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.max_backoff = max_backoff
        self._sleep = sleep_func

    def _headers(self):
        headers = {"Accept": "application/vnd.github+json"}
        if GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
        return headers

    def _sleep_before_retry(self, attempt):
        delay = min(self.backoff_base * (2 ** (attempt - 1)), self.max_backoff)
        self._sleep(delay)

    def _rate_limit_error(self, response, url):
        if response.status_code not in (403, 429):
            return None

        remaining = response.headers.get("X-RateLimit-Remaining")
        retry_after = response.headers.get("Retry-After")
        reset = response.headers.get("X-RateLimit-Reset")

        primary_exhausted = remaining == "0"
        secondary_or_429 = retry_after is not None or response.status_code == 429
        if not (primary_exhausted or secondary_or_429):
            # A plain 403 with none of GitHub's rate-limit signals (e.g.
            # permission denied on a private repo) is not a rate limit.
            return None

        message = f"GitHub rate limit exceeded for {url}"
        if reset is not None:
            message += f" (resets at epoch {reset})"
        elif retry_after is not None:
            message += f" (retry after {retry_after}s)"

        return GitHubRateLimitError(
            message,
            reset_at=int(reset) if reset is not None and reset.isdigit() else None,
            retry_after=int(retry_after)
            if retry_after is not None and retry_after.isdigit()
            else None,
        )

    def _get(self, url, params=None):
        attempt = 0
        while True:
            attempt += 1
            try:
                response = self.session.get(
                    url, headers=self._headers(), params=params, timeout=self.timeout
                )
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
                if attempt > self.max_retries:
                    raise GitHubRequestError(
                        f"GitHub request to {url} failed after {attempt} attempts: {exc}"
                    ) from exc
                logger.warning(
                    "GitHub request error for %s (attempt %d/%d), retrying: %s",
                    url, attempt, self.max_retries + 1, exc,
                )
                self._sleep_before_retry(attempt)
                continue

            rate_limit_error = self._rate_limit_error(response, url)
            if rate_limit_error is not None:
                raise rate_limit_error

            if response.status_code == 200:
                return response

            if response.status_code == 404:
                raise GitHubNotFoundError(f"GitHub resource not found: {url}")

            if response.status_code in RETRYABLE_STATUS_CODES and attempt <= self.max_retries:
                logger.warning(
                    "GitHub server error %d for %s (attempt %d/%d), retrying",
                    response.status_code, url, attempt, self.max_retries + 1,
                )
                self._sleep_before_retry(attempt)
                continue

            raise GitHubRequestError(
                f"GitHub request failed: {response.status_code}",
                status_code=response.status_code,
            )

    def get_user(self, username):
        url = f"https://api.github.com/users/{username}"
        response = self._get(url)
        return response.json()

    def get_repositories(self, username, per_page=DEFAULT_PER_PAGE, max_pages=DEFAULT_MAX_PAGES):
        url = f"https://api.github.com/users/{username}/repos"
        all_repos = []
        page = 1

        while True:
            if page > max_pages:
                raise GitHubRequestError(
                    f"Exceeded max_pages={max_pages} while paginating repositories "
                    f"for '{username}'; aborting instead of looping indefinitely."
                )

            response = self._get(url, params={"per_page": per_page, "page": page})
            page_items = response.json()
            if not isinstance(page_items, list):
                raise GitHubRequestError(
                    f"Unexpected repositories payload for '{username}': {page_items!r}"
                )

            all_repos.extend(page_items)
            logger.debug(
                "Fetched repositories page %d for %s: %d repos (running total %d)",
                page, username, len(page_items), len(all_repos),
            )

            if len(page_items) < per_page:
                break
            page += 1

        return all_repos

    def get_repository_languages(self, owner, repo):
        url = f"https://api.github.com/repos/{owner}/{repo}/languages"
        response = self._get(url)
        return response.json()

    def get_repository_readme(self, owner, repo_name):
        url = f"https://api.github.com/repos/{owner}/{repo_name}/readme"
        try:
            response = self._get(url)
        except GitHubNotFoundError:
            return None

        data = response.json()
        decoded_bytes = base64.b64decode(data["content"])
        return decoded_bytes.decode("utf-8")
