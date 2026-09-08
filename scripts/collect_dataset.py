"""Batch-collect GitScore profiles listed in a username file.

Usage:
    python scripts/collect_dataset.py [path/to/usernames.txt]

Default input: data/collection/usernames.txt (gitignored -- copy it from
data/collection/usernames.example.txt). One username per line; blank lines
and '#' comments are ignored; duplicates are removed.

Ordinary per-user failures (bad username, transient GitHub error, rate
limit for one user) are reported and skipped -- collection continues.
Exit code: 0 = all succeeded, 2 = finished with some failures,
1 = could not start (missing/empty file).

The GitHub token is never printed: only exception type + message are
shown, and GitHubClient error messages contain the request URL/status,
never credentials.
"""
import logging
import sys
import time
from pathlib import Path

from gitscore.dataset.collection_input import UsernameFileError, load_username_file
from gitscore.pipeline.analyze import analyze_user

DEFAULT_USERNAME_FILE = Path("data/collection/usernames.txt")


def main(argv):
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

    print(f"Collecting {len(usernames)} unique user(s) from {path}\n")

    batch_start = time.perf_counter()
    succeeded: list[str] = []
    failed: list[tuple[str, str]] = []

    for index, username in enumerate(usernames, start=1):
        prefix = f"[{index}/{len(usernames)}] {username}"
        try:
            result = analyze_user(username)
        except KeyboardInterrupt:
            print("\nInterrupted -- stopping (already-collected users are saved).")
            break
        except Exception as error:  # ordinary per-user failure: report and continue
            reason = f"{type(error).__name__}: {error}"
            failed.append((username, reason))
            print(f"{prefix}: FAILED -- {reason}")
            continue

        succeeded.append(username)
        print(
            f"{prefix}: {result['score']['total_score']}/100 "
            f"({result['time']:.1f}s)"
        )

    elapsed = time.perf_counter() - batch_start

    print("\nCollection complete.")
    print(f"  succeeded: {len(succeeded)}")
    print(f"  failed:    {len(failed)}")
    print(f"  attempted: {len(usernames)}")
    print(f"  elapsed:   {elapsed:.1f}s")
    if failed:
        print("  failures:")
        for username, reason in failed:
            print(f"    - {username}: {reason}")

    return 0 if not failed else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
