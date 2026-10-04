"""Milestone 8C -- deterministic report writers shared by all three
evaluate_*.py entry points.

Evaluation findings are MEASUREMENTS, not test assertions (Part 18): a
report documents the current state of the pipeline, however many
failures it finds. Nothing here raises or exits non-zero for a
"failed" evaluation case -- only `scripts/evaluate_*.py`'s own
harness-level error handling does that, for a genuinely broken
fixture/corpus file.
"""
from __future__ import annotations

import json
from pathlib import Path


def write_json_report(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False) + "\n", encoding="utf-8")


def write_text_report(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def markdown_table(headers: list[str], rows: list[list]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return lines
