"""Data-quality report for a built Dataset V1 frame.

Pure functions over a ``DatasetBuildResult`` -- no DB access, no file IO.
``dataset_quality_report`` returns a plain dict; ``format_report`` renders
it as a human-readable text block for CLI use.
"""
from __future__ import annotations

import pandas as pd

from gitscore.dataset import schema
from gitscore.dataset.builder import DatasetBuildResult

# A feature whose single most common value covers >= this share of rows is
# flagged "near-constant" (carries little signal for a model).
NEAR_CONSTANT_THRESHOLD = 0.95


def _f(value) -> float | None:
    """Float, or None for NaN/NA -- keeps the dict JSON-serialisable."""
    return None if pd.isna(value) else float(value)


def _target_histogram(series: pd.Series, *, lo: int = 0, hi: int = 100, step: int = 10) -> dict:
    edges = list(range(lo, hi + step, step))
    out: dict[str, int] = {}
    for i in range(len(edges) - 1):
        left, right = edges[i], edges[i + 1]
        is_last = i == len(edges) - 2
        if is_last:
            mask = (series >= left) & (series <= right)
            label = f"[{left},{right}]"
        else:
            mask = (series >= left) & (series < right)
            label = f"[{left},{right})"
        out[label] = int(mask.sum())
    return out


def dataset_quality_report(result: DatasetBuildResult) -> dict:
    """Summarise a built dataset: users, selection counts, nulls, dtypes,
    target distribution, numeric summary, ``most_used_language``
    distribution, and constant / near-constant features.
    """
    df = result.frame
    n = len(df)

    report: dict = {
        **schema.versions(),
        "row_grain": schema.ROW_GRAIN,
        "unique_users": result.unique_user_count,
        "rows_before_latest_selection": result.raw_snapshot_count,
        "rows_after_latest_selection": result.selected_row_count,
        "row_count": n,
        "duplicate_user_count": result.duplicate_user_count,
        "duplicate_usernames": list(result.duplicate_usernames),
        "missing_values": {c: int(df[c].isna().sum()) for c in schema.DATASET_COLUMNS},
        "total_missing_values": int(df[schema.DATASET_COLUMNS].isna().to_numpy().sum()),
        "feature_dtypes": {c: str(df[c].dtype) for c in schema.DATASET_COLUMNS},
    }

    if n == 0:
        report.update(
            target={},
            numeric_summary={},
            most_used_language_distribution={},
            constant_features=[],
            near_constant_features=[],
        )
        return report

    target = df[schema.TARGET_COLUMN].astype("float64")
    report["target"] = {
        "min": _f(target.min()),
        "max": _f(target.max()),
        "mean": _f(target.mean()),
        "std": _f(target.std(ddof=0)),
        "quantiles": {str(q): _f(target.quantile(q)) for q in (0.0, 0.25, 0.5, 0.75, 1.0)},
        "histogram": _target_histogram(target),
    }

    numeric_cols = schema.NUMERIC_FEATURE_COLUMNS + [schema.TARGET_COLUMN]
    described = df[numeric_cols].astype("float64").describe().to_dict()
    report["numeric_summary"] = {
        col: {stat: _f(val) for stat, val in stats.items()}
        for col, stats in described.items()
    }

    lang = df[schema.CATEGORICAL_FEATURE_COLUMNS[0]].astype("object")
    report["most_used_language_distribution"] = {
        str(value): int(count)
        for value, count in lang.value_counts(dropna=False).items()
    }

    constant: list[str] = []
    near_constant: list[dict] = []
    for col in schema.FEATURE_COLUMNS:
        if df[col].nunique(dropna=False) <= 1:
            constant.append(col)
            continue
        dominant_share = df[col].value_counts(dropna=False).iloc[0] / n
        if dominant_share >= NEAR_CONSTANT_THRESHOLD:
            near_constant.append({"feature": col, "dominant_share": _f(dominant_share)})
    report["constant_features"] = constant
    report["near_constant_features"] = near_constant

    return report


def format_report(report: dict) -> str:
    """Render ``dataset_quality_report`` output as a text block."""
    lines: list[str] = []
    add = lines.append

    add("=== GitScore Dataset V1 -- quality report ===")
    add(
        f"versions: dataset={report['dataset_version']} "
        f"feature_schema={report['feature_schema_version']} "
        f"scoring_rubric={report['scoring_rubric_version']}"
    )
    add(f"row grain: {report['row_grain']}")
    add("")
    add(f"unique users:                 {report['unique_users']}")
    add(f"rows before latest-selection: {report['rows_before_latest_selection']}")
    add(f"rows after latest-selection:  {report['rows_after_latest_selection']}")
    add(f"final row count:              {report['row_count']}")
    add(f"users with >1 snapshot:       {report['duplicate_user_count']}")
    if report["duplicate_usernames"]:
        add(f"  {', '.join(report['duplicate_usernames'])}")
    add("")
    add(f"total missing values: {report['total_missing_values']}")
    non_zero_missing = {c: v for c, v in report["missing_values"].items() if v}
    if non_zero_missing:
        for col, count in non_zero_missing.items():
            add(f"  {col}: {count}")

    if report["row_count"] == 0:
        add("")
        add("(empty dataset -- no distribution / summary sections)")
        return "\n".join(lines)

    add("")
    tgt = report["target"]
    add("target (readiness_score):")
    add(
        f"  min={tgt['min']} max={tgt['max']} mean={tgt['mean']:.2f} "
        f"std={tgt['std']:.2f}"
    )
    add(f"  quantiles: {tgt['quantiles']}")
    add(f"  histogram: {tgt['histogram']}")

    add("")
    add("most_used_language distribution:")
    for value, count in report["most_used_language_distribution"].items():
        shown = value if value != "" else '"" (unknown)'
        add(f"  {shown}: {count}")

    add("")
    add(f"constant features ({len(report['constant_features'])}): "
        f"{report['constant_features'] or '-'}")
    if report["near_constant_features"]:
        add("near-constant features (dominant value share >= "
            f"{NEAR_CONSTANT_THRESHOLD:.2f}):")
        for item in report["near_constant_features"]:
            add(f"  {item['feature']}: {item['dominant_share']:.3f}")
    else:
        add("near-constant features: -")

    add("")
    add("feature dtypes:")
    for col, dtype in report["feature_dtypes"].items():
        add(f"  {col}: {dtype}")

    return "\n".join(lines)
