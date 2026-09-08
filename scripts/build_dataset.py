"""Build the clean GitScore Dataset V1 and export it deterministically.

Usage:
    python scripts/build_dataset.py [output.csv]

Reads only the SQLite snapshot database (data/gitscore.db). Prints a
data-quality report, then writes:

    data/processed/gitscore_dataset_v1.csv        (deterministic)
    data/processed/gitscore_dataset_v1.meta.json  (informational sidecar)

Both stay under data/processed/, which is gitignored -- the CSV is a
derived artifact; the database is the source of truth.

Exit code: 0 = exported, 1 = nothing to export (no snapshots).
"""
import sys

from gitscore.dataset.builder import build_dataset
from gitscore.dataset.export import export_dataset
from gitscore.dataset.report import dataset_quality_report, format_report


def main(argv):
    out_path = argv[1] if len(argv) > 1 else None

    result = build_dataset()
    print(format_report(dataset_quality_report(result)))

    if result.selected_row_count == 0:
        print(
            "\nNo rows selected -- the database has no ProfileFeature snapshots. "
            "Run scripts/collect_dataset.py first. Nothing exported."
        )
        return 1

    csv_path = export_dataset(result, out_path)
    print(
        f"\nWrote {result.selected_row_count} rows x "
        f"{len(result.frame.columns)} columns -> {csv_path}"
    )
    print(f"Metadata -> {csv_path.with_suffix('.meta.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
