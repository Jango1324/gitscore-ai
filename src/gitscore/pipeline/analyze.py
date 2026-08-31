import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from gitscore.github.client import GitHubClient
from gitscore.github.exceptions import GitHubError, GitHubRateLimitError
from gitscore.github.parser import parse_repo
from gitscore.features.profile import extract_profile_features
from gitscore.db.queries import save_user, save_profile_features
from gitscore.scoring.readiness import calculate_readiness_score

logger = logging.getLogger(__name__)

# Conservative, unchanged from the original design: enough concurrency to
# make network-bound repo fetches fast, low enough to stay well clear of
# GitHub's secondary (abuse-detection) rate limits.
MAX_REPO_WORKERS = 8


def fetch_repo_data(client, username, repo):
    repo_name = repo["name"]

    # Optional metadata: a single repo failing here (after the client's
    # own retries are exhausted) should not take down the whole profile
    # analysis. A rate limit is different — it means every remaining
    # request is about to fail the same way, so it propagates instead of
    # being swallowed per-repo, aborting the batch instead of burning
    # through the remaining request budget for degraded data.
    try:
        languages = client.get_repository_languages(username, repo_name)
    except GitHubRateLimitError:
        raise
    except GitHubError as exc:
        logger.warning(
            "Degrading language data for %s/%s after failure: %s",
            username, repo_name, exc,
        )
        languages = {}

    try:
        readme = client.get_repository_readme(username, repo_name)
    except GitHubRateLimitError:
        raise
    except GitHubError as exc:
        logger.warning(
            "Degrading README for %s/%s after failure: %s",
            username, repo_name, exc,
        )
        readme = None

    return parse_repo(repo, languages, readme)


def analyze_user(username):
    start = time.perf_counter()
    # create GitHub client
    client = GitHubClient()

    # fetch user data
    data = client.get_user(username)

    # save/update user
    saved_user = save_user(data)
    # fetch repos (all pages)
    repos = client.get_repositories(username)

    # Each worker thread gets its own GitHubClient/requests.Session
    # instead of sharing one across threads. requests.Session is not
    # documented as thread-safe, and this removes that assumption
    # entirely while keeping most of the connection-reuse benefit (each
    # worker thread reuses its own session across every repo it handles).
    thread_local = threading.local()

    def get_thread_client():
        worker_client = getattr(thread_local, "client", None)
        if worker_client is None:
            worker_client = GitHubClient(
                timeout=client.timeout,
                max_retries=client.max_retries,
                backoff_base=client.backoff_base,
                max_backoff=client.max_backoff,
            )
            thread_local.client = worker_client
        return worker_client

    def fetch(repo):
        return fetch_repo_data(get_thread_client(), username, repo)

    logger.info("Fetching metadata for %d repositories (%s)", len(repos), username)
    with ThreadPoolExecutor(max_workers=MAX_REPO_WORKERS) as executor:
        # Submit up front (not executor.map) so that on a fatal error --
        # a rate limit -- we can cancel every not-yet-started future
        # instead of letting the whole queued batch run first. map()
        # would still drain the queue before propagating the exception,
        # burning more of an already-exhausted rate-limit budget.
        # .result() is called in submission order, preserving the same
        # deterministic repo ordering executor.map gave.
        futures = [executor.submit(fetch, repo) for repo in repos]
        try:
            clean_repos = [future.result() for future in futures]
        except BaseException:
            for future in futures:
                future.cancel()
            raise

    # extract features
    features = extract_profile_features(clean_repos)
    # calculate score
    score = calculate_readiness_score(features)

    # persist feature snapshot
    saved_features = save_profile_features(
        saved_user.id,
        features,
        score,
    )
    # return useful result
    elapsed = time.perf_counter() - start
    return {
        "user": saved_user,
        "features": features,
        "score": score,
        "time": elapsed,
    }
