#!/usr/bin/env python3
"""Local tool preflight and pilot result aggregation."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


MODES = ("baseline", "team-2", "team-4")
STATUSES = ("accepted", "rejected", "blocked")
EXECUTABLES = (
    "python3",
    "rtk",
    "orca",
    "gemini",
    "teamai",
    "graft",
    "codegraph",
    "chatcone-resolve",
    "chatcone-launch",
)


class InputError(ValueError):
    pass


def preflight() -> dict[str, Any]:
    return {
        "executables": {name: shutil.which(name) is not None for name in EXECUTABLES},
        "authentication": "unknown",
        "model_entitlement": "unknown",
    }


def _finite_nonnegative(value: Any, field: str, *, integer: bool = False) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InputError(f"{field} must be a {('nonnegative integer' if integer else 'finite nonnegative number')}")
    if integer and not isinstance(value, int):
        raise InputError(f"{field} must be a nonnegative integer")
    if value < 0 or (isinstance(value, float) and not math.isfinite(value)):
        raise InputError(f"{field} must be finite and nonnegative")
    return value


def _reject_json_constant(value: str) -> None:
    raise InputError(f"invalid number {value}")


def validate_records(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, list):
        raise InputError("input must be a JSON array of result records")
    if not data:
        raise InputError("input has no measurements")

    records: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(data):
        label = f"record {index + 1}"
        if not isinstance(item, dict):
            raise InputError(f"{label} must be an object")
        task_id = item.get("task_id")
        if not isinstance(task_id, str) or not task_id.strip():
            raise InputError(f"{label} task_id must be a nonempty string")
        mode = item.get("mode")
        if mode not in MODES:
            raise InputError(f"{label} mode must be one of: {', '.join(MODES)}")
        status = item.get("status")
        if status not in STATUSES:
            raise InputError(f"{label} status must be one of: {', '.join(STATUSES)}")

        key = (task_id, mode)
        if key in seen:
            raise InputError(f"duplicate task_id/mode: {task_id!r}, {mode!r}")
        seen.add(key)

        record: dict[str, Any] = {
            "task_id": task_id,
            "mode": mode,
            "status": status,
            "elapsed_seconds": _finite_nonnegative(item.get("elapsed_seconds"), f"{label} elapsed_seconds"),
            "rework_count": _finite_nonnegative(item.get("rework_count"), f"{label} rework_count", integer=True),
        }
        for metric in ("cost_usd", "tokens"):
            value = item.get(metric)
            if value is not None:
                record[metric] = _finite_nonnegative(value, f"{label} {metric}", integer=(metric == "tokens"))
            else:
                record[metric] = None
        records.append(record)
    return records


def _metric_summary(rows: list[dict[str, Any]], metric: str, accepted: int) -> dict[str, Any]:
    measured = [row[metric] for row in rows if row[metric] is not None]
    complete = len(measured) == len(rows)
    total = _aggregate_sum(measured, metric) if complete else None
    per_accepted = _safe_divide(total, accepted, f"{metric} per accepted") if total is not None and accepted else None
    return {
        "measured_count": len(measured),
        "total": total,
        "per_accepted": per_accepted,
    }


def _aggregate_sum(values: list[int | float], field: str) -> int | float:
    try:
        total = sum(values)
    except OverflowError as error:
        raise InputError(f"aggregated {field} is outside the representable range") from error
    if isinstance(total, float) and not math.isfinite(total):
        raise InputError(f"aggregated {field} is not finite")
    return total


def _safe_divide(numerator: int | float, denominator: int, field: str) -> float:
    try:
        result = numerator / denominator
    except OverflowError as error:
        raise InputError(f"{field} is outside the representable range") from error
    if not math.isfinite(result):
        raise InputError(f"{field} is not finite")
    return result


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        groups[record["mode"]].append(record)

    result: dict[str, Any] = {"modes": {}}
    for mode in MODES:
        rows = groups.get(mode, [])
        if not rows:
            continue
        counts = {status: sum(row["status"] == status for row in rows) for status in STATUSES}
        accepted = counts["accepted"]
        elapsed = _aggregate_sum([row["elapsed_seconds"] for row in rows], "elapsed_seconds")
        first_pass = sum(row["status"] == "accepted" and row["rework_count"] == 0 for row in rows)
        seconds_per_accepted = _safe_divide(elapsed, accepted, "seconds per accepted") if accepted else None
        result["modes"][mode] = {
            "counts": counts,
            "accepted": accepted,
            "total": len(rows),
            "first_pass_rate": first_pass / len(rows),
            "total_elapsed_seconds": elapsed,
            "seconds_per_accepted": seconds_per_accepted,
            "total_rework": sum(row["rework_count"] for row in rows),
            "cost_usd": _metric_summary(rows, "cost_usd", accepted),
            "tokens": _metric_summary(rows, "tokens", accepted),
        }
    return result


def _emit(payload: Any) -> None:
    try:
        serialized = json.dumps(payload, indent=2, allow_nan=False)
    except (ValueError, OverflowError) as error:
        raise InputError(f"result cannot be represented as JSON: {error}") from error
    sys.stdout.write(serialized + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("preflight", help="report executable presence only")
    summarize_parser = subparsers.add_parser("summarize", help="aggregate JSON pilot records")
    summarize_parser.add_argument("path", type=Path)
    args = parser.parse_args(argv)

    if args.command == "preflight":
        _emit(preflight())
        return 0

    try:
        data = json.loads(args.path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
        records = validate_records(data)
        _emit(summarize(records))
        return 0
    except (OSError, UnicodeError, json.JSONDecodeError, InputError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
