"""Print a data-quality report for the GitScore dataset without exporting.

Usage:
    python scripts/dataset_report.py

Reads only the SQLite snapshot database (data/gitscore.db). Useful before
committing to a full collection run or an export.
"""
import sys

from gitscore.dataset.builder import build_dataset
from gitscore.dataset.report import dataset_quality_report, format_report


def main():
    result = build_dataset()
    print(format_report(dataset_quality_report(result)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
