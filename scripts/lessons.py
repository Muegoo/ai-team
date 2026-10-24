"""Validate and select controller-reviewed project lessons from an explicit store."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    from .practice_common import InputError, emit, read_json, relative_path, resolve_local, safe_error
except ImportError:
    from practice_common import InputError, emit, read_json, relative_path, resolve_local, safe_error

REVIEWERS = {"Codex Astra", "Codex Sol"}
STATUSES = {"proposed", "approved", "retired"}
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def _iso_date(value: Any, field: str, *, required: bool = False) -> None:
    if value is None and not required:
        return
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise InputError(f"{field} must be an ISO date")
    try:
        date.fromisoformat(value)
    except ValueError as error:
        raise InputError(f"{field} must be an ISO date") from error


def validate_store(data: Any, store_path: Path, root_override: Path | None = None) -> dict[str, Any]:
    if (not isinstance(data, dict) or set(data) != {"schema_version", "lessons"}
            or type(data.get("schema_version")) is not int or data["schema_version"] != 1):
        raise InputError("lesson store must have schema_version 1")
    lessons = data.get("lessons")
    if not isinstance(lessons, list):
        raise InputError("lesson store must contain a lessons array")
    root = (root_override or store_path.resolve().parent).resolve()
    seen: set[str] = set()
    normalized = []
    for index, lesson in enumerate(lessons):
        label = f"lessons[{index}]"
        if not isinstance(lesson, dict):
            raise InputError(f"{label} must be an object")
        if set(lesson) != {"lesson_id", "project_id", "trigger", "observation", "action", "evidence",
                           "source_task", "status", "reviewed_by", "reviewed_at"}:
            raise InputError(f"{label} has missing or unknown fields")
        lesson_id = lesson.get("lesson_id")
        if not isinstance(lesson_id, str) or not ID_RE.fullmatch(lesson_id):
            raise InputError(f"{label}.lesson_id is invalid")
        if lesson_id in seen:
            raise InputError("duplicate lesson_id")
        seen.add(lesson_id)
        for field in ("project_id", "trigger", "observation", "action", "source_task"):
            if not isinstance(lesson.get(field), str) or not lesson[field].strip():
                raise InputError(f"{label}.{field} must be a nonempty string")
        evidence = lesson.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise InputError(f"{label}.evidence must be a nonempty list")
        for ref in evidence:
            if not isinstance(ref, str) or not ref.strip():
                raise InputError(f"{label}.evidence entries must be nonempty strings")
            parsed = urlparse(ref)
            if parsed.scheme == "https" and parsed.netloc:
                continue
            resolve_local(root, ref, f"{label}.evidence")
        status = lesson.get("status")
        if not isinstance(status, str) or status not in STATUSES:
            raise InputError(f"{label}.status is invalid")
        reviewer = lesson.get("reviewed_by")
        reviewed_at = lesson.get("reviewed_at")
        if reviewer is not None and (not isinstance(reviewer, str) or reviewer not in REVIEWERS):
            raise InputError(f"{label}.reviewed_by must be Codex Astra, Codex Sol, or null")
        _iso_date(reviewed_at, f"{label}.reviewed_at", required=status == "approved")
        if status == "approved" and reviewer not in REVIEWERS:
            raise InputError(f"{label}.approved lesson requires a controller reviewer")
        normalized.append(lesson)
    return {"schema_version": 1, "lessons": normalized, "root": str(root),
            "reviewer_labels_are_runtime_authenticated": False}


def _tokens(value: str) -> set[str]:
    return {token.casefold() for token in re.findall(r"\w+", value, flags=re.UNICODE)}


def select_lessons(store: dict[str, Any], project_id: str, trigger: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
    if not isinstance(project_id, str) or not project_id.strip():
        raise InputError("project ID must be a nonempty string")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise InputError("limit must be an integer from 1 to 100")
    requested = _tokens(trigger) if trigger is not None else set()
    candidates = []
    for lesson in store["lessons"]:
        if lesson["status"] != "approved" or lesson["project_id"] != project_id:
            continue
        overlap = len(requested & _tokens(lesson["trigger"])) if requested else 0
        if requested and overlap == 0:
            continue
        candidates.append((overlap, lesson))
    candidates.sort(key=lambda item: (-item[0], item[1]["lesson_id"]))
    return [lesson for _score, lesson in candidates[:limit]]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate_parser = commands.add_parser("validate")
    validate_parser.add_argument("store", type=Path)
    validate_parser.add_argument("--root", type=Path)
    select_parser = commands.add_parser("select")
    select_parser.add_argument("store", type=Path)
    select_parser.add_argument("--root", type=Path)
    select_parser.add_argument("--project", required=True)
    select_parser.add_argument("--trigger")
    select_parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args(argv)
    try:
        store = validate_store(read_json(args.store), args.store, args.root)
        if args.command == "validate":
            result = {"valid": True, "lesson_count": len(store["lessons"]),
                      "reviewer_labels_are_runtime_authenticated": False}
        else:
            result = {"project_id": args.project, "lessons": select_lessons(store, args.project, args.trigger, args.limit),
                      "reviewer_labels_are_runtime_authenticated": False}
        emit(result)
        return 0
    except (InputError, OSError, ValueError) as error:
        print(f"error: {safe_error(error)}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
