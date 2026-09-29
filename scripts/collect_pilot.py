"""Rate-limit-aware pilot batch collector (Milestone 4.5, Dataset V1 pilot).

Collects every username in ``data/collection/usernames.txt`` in a single
run so the whole pilot lands in one temporally-consistent snapshot,
despite GitHub's 5000 req/hour authenticated cap. Before each account it
checks the remaining core budget against a cost estimate (~2 calls per
public repo) and, if the budget is too small, sleeps until the rate-limit
reset and resumes. A ``GitHubRateLimitError`` raised mid-account is also
caught: the runner sleeps to the reset and retries that account from
scratch (``analyze_user`` persists nothing on failure).

This changes NOTHING about scoring, feature extraction, or the DB schema.
Each account is persisted by the normal
``gitscore.pipeline.analyze.analyze_user`` path -- exactly one
``ProfileFeature`` snapshot per account, same as
``scripts/collect_dataset.py`` would write.

For inspection it additionally writes three DERIVED artifacts under
``data/processed/`` (gitignored -- the SQLite DB stays the source of
truth):

    pilot_raw_features.csv     one row/account: username + the 30 extracted
                               features (schema.FEATURE_COLUMNS order) + total
    pilot_category_scores.csv  one row/account: username, total, and the five
                               rubric category sub-scores (recomputed live by
                               scoring.readiness -- the DB only stores the total)
    pilot_results.json         everything above + per-account user metadata
                               (name / followers / public_repos / elapsed) and
                               the list of any failed accounts

Usage:
    python scripts/collect_pilot.py [path/to/usernames.txt]

Exit code: 0 = all accounts collected, 2 = finished with some failures,
1 = could not start (missing/empty username file).
"""
from __future__ import annotations

import csv
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

from gitscore.config import GITHUB_TOKEN
from gitscore.dataset.collection_input import UsernameFileError, load_username_file
from gitscore.dataset.schema import FEATURE_COLUMNS, TARGET_COLUMN
from gitscore.github.client import GitHubClient
from gitscore.github.exceptions import GitHubNotFoundError, GitHubRateLimitError
from gitscore.pipeline.analyze import analyze_user
from gitscore.scoring.readiness import calculate_readiness_score

logger = logging.getLogger("collect_pilot")

DEFAULT_USERNAME_FILE = Path("data/collection/usernames.txt")
OUTPUT_DIR = Path("data/processed")

CATEGORY_KEYS = [
    "ml_experience",
    "project_originality",
    "documentation_quality",
    "language_tool_relevance",
    "community_signal",
]

# Keep a cushion below the hard cap so a slightly-low estimate (extra
# pagination pages, transient 5xx retries) does not tip an account over.
SAFETY_MARGIN_CALLS = 200
# Extra seconds to wait past the advertised reset -- clock skew / edge caching.
RESET_BUFFER_SECONDS = 60
# A single account that keeps hitting the limit even right after a reset
# is a real problem, not something to loop on forever.
MAX_RATE_RETRIES = 4


def _core_budget() -> tuple[int, int]:
    """(remaining, reset_epoch) for the REST core resource.

    ``/rate_limit`` itself does not count against the core budget.
    """
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    resp = requests.get(
        "https://api.github.com/rate_limit", headers=headers, timeout=10
    )
    resp.raise_for_status()
    core = resp.json()["resources"]["core"]
    return int(core["remaining"]), int(core["reset"])


def _estimate_cost(public_repos: int) -> int:
    """Rough upper-ish estimate of core calls to analyze one account.

    1 user call + ceil(repos/100) repo-list pages + 2 calls/repo
    (languages + README).
    """
    repo_list_pages = max(1, -(-public_repos // 100))
    return 1 + repo_list_pages + public_repos * 2


def _sleep_until(epoch_ts: float, reason: str) -> None:
    deadline = max(epoch_ts, time.time())
    total = deadline - time.time()
    if total <= 0:
        return
    until = datetime.utcfromtimestamp(deadline).isoformat()
    print(
        f"  [throttle] {reason}: sleeping {total / 60:.1f} min (until {until}Z)",
        flush=True,
    )
    while True:
        left = deadline - time.time()
        if left <= 0:
            break
        time.sleep(min(300.0, left))
        left = deadline - time.time()
        if left > 0:
            print(f"  [throttle] ~{left / 60:.1f} min left", flush=True)
    print("  [throttle] resuming", flush=True)


def _wait_out_rate_limit(exc: GitHubRateLimitError, context: str) -> None:
    if exc.reset_at is not None:
        target = exc.reset_at + RESET_BUFFER_SECONDS
    elif exc.retry_after is not None:
        target = time.time() + exc.retry_after + RESET_BUFFER_SECONDS
    else:
        target = time.time() + 300
    _sleep_until(target, f"rate limit during {context}")


def _preflight(client: GitHubClient, usernames: list[str]) -> tuple[list[dict], list[tuple[str, str]]]:
    """Resolve each username to (login, public_repos); drop 404s."""
    infos: list[dict] = []
    failed: list[tuple[str, str]] = []
    for name in usernames:
        while True:
            try:
                data = client.get_user(name)
                infos.append(
                    {
                        "username": data["login"],
                        "public_repos": int(data.get("public_repos", 0)),
                    }
                )
                break
            except GitHubRateLimitError as exc:
                _wait_out_rate_limit(exc, f"preflight {name}")
            except GitHubNotFoundError:
                print(f"  [preflight] {name}: NOT FOUND -- skipping", flush=True)
                failed.append((name, "GitHubNotFoundError: user not found"))
                break
    return infos, failed


def _collect_one(name: str) -> dict | None:
    """analyze_user(name) with rate-limit retry. None on non-retryable failure."""
    attempts = 0
    while True:
        attempts += 1
        try:
            return analyze_user(name)
        except GitHubRateLimitError as exc:
            if attempts > MAX_RATE_RETRIES:
                print(
                    f"  {name}: still rate-limited after {MAX_RATE_RETRIES} retries "
                    "-- giving up on this account",
                    flush=True,
                )
                return None
            _wait_out_rate_limit(exc, f"{name} (attempt {attempts})")
        except Exception as exc:  # ordinary per-account failure
            print(f"  {name}: FAILED -- {type(exc).__name__}: {exc}", flush=True)
            return None


def _write_artifacts(results: list[dict], failed: list[tuple[str, str]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ordered = sorted(results, key=lambda r: r["username"].lower())

    raw_path = OUTPUT_DIR / "pilot_raw_features.csv"
    with raw_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["username", *FEATURE_COLUMNS, TARGET_COLUMN])
        for r in ordered:
            feats = r["features"]
            writer.writerow(
                [r["username"], *(feats[c] for c in FEATURE_COLUMNS), r["score"]["total_score"]]
            )

    cat_path = OUTPUT_DIR / "pilot_category_scores.csv"
    with cat_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["username", "total_score", *CATEGORY_KEYS])
        for r in ordered:
            s = r["score"]
            writer.writerow(
                [r["username"], s["total_score"], *(s[k] for k in CATEGORY_KEYS)]
            )

    json_path = OUTPUT_DIR / "pilot_results.json"
    payload = {
        "collected_at_utc": datetime.utcnow().isoformat() + "Z",
        "note": (
            "Milestone 4.5 pilot. Rule-based rubric v1, feature schema v1. "
            "NOT a training set. category sub-scores recomputed live by "
            "scoring.readiness (DB stores only the total)."
        ),
        "accounts": [
            {
                "username": r["username"],
                "name": r["name"],
                "followers": r["followers"],
                "public_repos": r["public_repos"],
                "elapsed_seconds": r["elapsed_seconds"],
                "score": r["score"],
                "features": r["features"],
            }
            for r in ordered
        ],
        "failed": [{"username": u, "reason": why} for u, why in failed],
    }
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    print(f"\nWrote:\n  {raw_path}\n  {cat_path}\n  {json_path}", flush=True)


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    path = Path(argv[1]) if len(argv) > 1 else DEFAULT_USERNAME_FILE
    try:
        usernames = load_username_file(path)
    except UsernameFileError as exc:
        print(exc)
        return 1
    if not usernames:
        print(f"No usernames to collect in {path} (after ignoring blanks/comments).")
        return 1

    print(f"Pilot collection: {len(usernames)} account(s) from {path}\n", flush=True)

    probe = GitHubClient()
    infos, failed = _preflight(probe, usernames)
    # Smallest accounts first: the cheap ones are all banked before any
    # long sleep, and the one or two huge accounts are what we sleep for.
    infos.sort(key=lambda d: d["public_repos"])

    total_est = sum(_estimate_cost(i["public_repos"]) for i in infos)
    print(
        f"Preflight OK: {len(infos)} account(s), ~{total_est} core calls estimated "
        f"(cap is 5000/hour -- expect ~1 sleep).\n",
        flush=True,
    )

    batch_start = time.perf_counter()
    results: list[dict] = []

    for index, info in enumerate(infos, start=1):
        name = info["username"]
        prefix = f"[{index}/{len(infos)}] {name} ({info['public_repos']} repos)"

        remaining, reset = _core_budget()
        est = _estimate_cost(info["public_repos"])
        print(f"{prefix}: budget {remaining} left, est ~{est} calls", flush=True)
        if remaining < est + SAFETY_MARGIN_CALLS:
            _sleep_until(
                reset + RESET_BUFFER_SECONDS,
                f"only {remaining} calls left, need ~{est} for {name}",
            )

        result = _collect_one(name)
        if result is None:
            failed.append((name, "collection failed (see log above)"))
            print(f"{prefix}: FAILED", flush=True)
            continue

        features = result["features"]
        # analyze_user already returns the full score dict; recompute here
        # too as a cheap consistency check (same deterministic function).
        score = calculate_readiness_score(features)
        saved_user = result["user"]
        results.append(
            {
                "username": name,
                "name": saved_user.name,
                "followers": saved_user.followers,
                "public_repos": saved_user.public_repos,
                "elapsed_seconds": round(result["time"], 1),
                "features": features,
                "score": score,
            }
        )
        print(
            f"{prefix}: {score['total_score']}/100  "
            f"ml={score['ml_experience']} orig={score['project_originality']} "
            f"doc={score['documentation_quality']} lang={score['language_tool_relevance']} "
            f"comm={score['community_signal']}  ({result['time']:.1f}s)",
            flush=True,
        )

    elapsed = time.perf_counter() - batch_start
    _write_artifacts(results, failed)

    print("\nPilot collection complete.", flush=True)
    print(f"  collected: {len(results)}", flush=True)
    print(f"  failed:    {len(failed)}", flush=True)
    print(f"  attempted: {len(usernames)}", flush=True)
    print(f"  elapsed:   {elapsed / 60:.1f} min", flush=True)
    if failed:
        print("  failures:", flush=True)
        for username, reason in failed:
            print(f"    - {username}: {reason}", flush=True)

    return 0 if not failed else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
