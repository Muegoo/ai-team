#!/usr/bin/env python3
"""Plan bounded work, wait for Orca receipts, and summarize supplied usage logs."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


class InputError(ValueError):
    pass


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise InputError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise InputError(f"nonfinite JSON number: {value}")


def _float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise InputError(f"nonfinite JSON number: {value}")
    return number


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs,
                          parse_constant=_constant, parse_float=_float)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise InputError(f"cannot read JSON {path}: {error}") from error


def _string(value: Any, field: str, *, trimmed: bool = False) -> str:
    if not isinstance(value, str) or not value.strip() or (trimmed and value != value.strip()):
        raise InputError(f"{field} must be a nonempty{' trimmed' if trimmed else ''} string")
    return value


def _string_list(value: Any, field: str, *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or (nonempty and not value):
        raise InputError(f"{field} must be a {'nonempty ' if nonempty else ''}list of strings")
    result = []
    for index, item in enumerate(value):
        result.append(_string(item, f"{field}[{index}]"))
    return result


def _path(value: Any, field: str) -> str:
    path = _string(value, field)
    parsed = PurePosixPath(path)
    if (path.startswith("/") or "\\" in path or any(c in path for c in "*?[]")
            or any(part in ("", ".", "..") for part in path.split("/"))
            or parsed.as_posix() != path):
        raise InputError(f"{field} must be a canonical relative POSIX path")
    return path


def _plan_data(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, dict) or not isinstance(data.get("tasks"), list) or not data["tasks"]:
        raise InputError("plan input must be an object with a nonempty tasks array")
    tasks: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    for index, source in enumerate(data["tasks"]):
        label = f"tasks[{index}]"
        if not isinstance(source, dict):
            raise InputError(f"{label} must be an object")
        task_id = _string(source.get("task_id"), f"{label}.task_id", trimmed=True)
        if task_id in by_id:
            raise InputError(f"duplicate task_id: {task_id}")
        goal = _string(source.get("goal"), f"{label}.goal")
        paths_value = source.get("writable_paths")
        if not isinstance(paths_value, list) or not paths_value:
            raise InputError(f"{label}.writable_paths must be a nonempty list")
        paths = [_path(path, f"{label}.writable_paths[{i}]") for i, path in enumerate(paths_value)]
        if len(set(paths)) != len(paths):
            raise InputError(f"{label}.writable_paths contains a duplicate path")
        worktree = _string(source.get("worktree_id"), f"{label}.worktree_id", trimmed=True)
        deps = _string_list(source.get("depends_on", []), f"{label}.depends_on")
        if len(set(deps)) != len(deps):
            raise InputError(f"{label}.depends_on contains a duplicate ID")
        acceptance = _string_list(source.get("acceptance"), f"{label}.acceptance", nonempty=True)
        constraints = _string_list(source.get("constraints", []), f"{label}.constraints")
        review = source.get("review", "lead")
        if review not in ("lead", "independent"):
            raise InputError(f"{label}.review must be 'lead' or 'independent'")
        task = {"task_id": task_id, "goal": goal, "writable_paths": paths,
                "worktree_id": worktree, "depends_on": deps, "acceptance": acceptance,
                "constraints": constraints, "review": review}
        tasks.append(task)
        by_id[task_id] = task
    for task in tasks:
        for dependency in task["depends_on"]:
            if dependency not in by_id:
                raise InputError(f"task {task['task_id']} has unknown dependency {dependency}")
            if dependency == task["task_id"]:
                raise InputError(f"task {task['task_id']} depends on itself")
    visited: set[str] = set()
    visiting: set[str] = set()

    def visit(task_id: str) -> None:
        if task_id in visiting:
            raise InputError(f"dependency cycle includes task {task_id}")
        if task_id in visited:
            return
        visiting.add(task_id)
        for dependency in by_id[task_id]["depends_on"]:
            visit(dependency)
        visiting.remove(task_id)
        visited.add(task_id)

    for task in tasks:
        visit(task["task_id"])
    return tasks


def _paths_conflict(left: str, right: str) -> bool:
    a, b = left.casefold().split("/"), right.casefold().split("/")
    return a[:len(b)] == b or b[:len(a)] == a


def _conflict(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return (a["worktree_id"] == b["worktree_id"] or
            any(_paths_conflict(left, right) for left in a["writable_paths"] for right in b["writable_paths"]))


def plan(data: Any, workers: int = 1, completed: list[str] | None = None,
         active: list[str] | None = None, max_brief_chars: int = 6000) -> dict[str, Any]:
    if isinstance(workers, bool) or not isinstance(workers, int) or not 1 <= workers <= 4:
        raise InputError("workers must be an integer from 1 to 4")
    if isinstance(max_brief_chars, bool) or not isinstance(max_brief_chars, int) or max_brief_chars <= 0:
        raise InputError("max-brief-chars must be a positive integer")
    tasks = _plan_data(data)
    by_id = {task["task_id"]: task for task in tasks}
    completed, active = completed or [], active or []
    for label, ids in (("completed", completed), ("active", active)):
        if len(set(ids)) != len(ids):
            raise InputError(f"duplicate {label} task ID")
        for task_id in ids:
            if task_id not in by_id:
                raise InputError(f"unknown {label} task ID: {task_id}")
    if set(completed) & set(active):
        raise InputError("active and completed task IDs overlap")
    if len(active) > workers:
        raise InputError("active task count exceeds worker capacity")
    for task_id in completed + active:
        missing = [dependency for dependency in by_id[task_id]["depends_on"] if dependency not in completed]
        if missing:
            raise InputError(f"{task_id} requires completed dependencies: {', '.join(missing)}")
    active_tasks = [by_id[task_id] for task_id in active]
    for i, task in enumerate(active_tasks):
        if any(_conflict(task, other) for other in active_tasks[:i]):
            raise InputError("active tasks have conflicting worktree or writable paths")
    slots = workers - len(active)
    selected: list[dict[str, Any]] = []
    deferred: list[dict[str, str]] = []
    blocked: list[dict[str, Any]] = []
    occupied = active_tasks[:]
    excluded = set(completed) | set(active)
    for task in tasks:
        if task["task_id"] in excluded:
            continue
        missing = [dependency for dependency in task["depends_on"] if dependency not in completed]
        if missing:
            blocked.append({"task_id": task["task_id"], "unmet_dependencies": missing})
            continue
        conflict = next((other for other in occupied if _conflict(task, other)), None)
        if conflict:
            deferred.append({"task_id": task["task_id"], "reason": f"conflicts with {conflict['task_id']}"})
            continue
        if len(selected) >= slots:
            deferred.append({"task_id": task["task_id"], "reason": "worker capacity"})
            continue
        brief = {"goal": task["goal"], "writable_paths": task["writable_paths"],
                 "worktree_id": task["worktree_id"], "acceptance": task["acceptance"],
                 "constraints": task["constraints"], "review": task["review"],
                 "invariant": "Sol/Astra decides behavior and architecture; Luna/Terra executes. Stop and escalate ambiguity or out-of-scope changes. The executor owns tests unless the lead explicitly requests independent review."}
        brief_text = json.dumps(brief, ensure_ascii=False, separators=(",", ":"))
        if len(brief_text) > max_brief_chars:
            raise InputError(f"brief for task {task['task_id']} exceeds max-brief-chars ({len(brief_text)} > {max_brief_chars})")
        selected.append({"task_id": task["task_id"], "review": task["review"], "brief": brief_text})
        occupied.append(task)
    return {"worker_cap": workers, "active": active, "completed": completed,
            "selected": selected, "deferred": deferred, "blocked": blocked}


def _message_payload(message: dict[str, Any]) -> dict[str, Any]:
    payload = message.get("payload")
    encoded_payload = isinstance(payload, str)
    if encoded_payload:
        try:
            payload = json.loads(payload, object_pairs_hook=_pairs, parse_constant=_constant, parse_float=_float)
        except (json.JSONDecodeError, InputError) as error:
            raise InputError("payload must be an object or JSON string containing an object") from error
    if payload is None and not encoded_payload:
        return {}
    if not isinstance(payload, dict):
        raise InputError("payload must be an object")
    return payload


def wait_for_messages(run_id: str, timeout_seconds: float, *, runner: Any = subprocess.run,
                      clock: Any = time.monotonic) -> dict[str, Any]:
    if not isinstance(run_id, str) or not run_id.strip():
        raise InputError("run must be a nonempty string")
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise InputError("timeout-seconds must be a positive finite number")
    deadline = clock() + timeout_seconds
    while True:
        remaining = deadline - clock()
        if remaining <= 0:
            return {"event": "timeout", "run_id": run_id, "checkpoint": True, "failure": False}
        timeout_ms = max(1, min(30000, math.ceil(remaining * 1000)))
        command = ["orca", "orchestration", "check", "--run", run_id, "--wait",
                   "--timeout-ms", str(timeout_ms), "--types", "worker_done,escalation,question", "--json"]
        try:
            result = runner(command, capture_output=True, text=True, shell=False,
                            timeout=min(remaining + 1, timeout_ms / 1000 + 1))
        except (OSError, subprocess.TimeoutExpired) as error:
            raise InputError(f"Orca check failed: {error}") from error
        if result.returncode != 0:
            raise InputError(f"Orca check exited {result.returncode}: {result.stderr.strip() or 'no error detail'}")
        try:
            receipt = json.loads(result.stdout, object_pairs_hook=_pairs, parse_constant=_constant, parse_float=_float)
        except (json.JSONDecodeError, InputError) as error:
            raise InputError(f"Orca check returned invalid JSON: {error}") from error
        if not isinstance(receipt, dict) or receipt.get("ok") is not True:
            raise InputError("Orca check returned an invalid receipt")
        data = receipt.get("result")
        if not isinstance(data, dict):
            raise InputError("Orca check receipt result schema is invalid")
        if data.get("connectionLost") is True or data.get("connection_lost") is True:
            raise InputError("Orca check connection was lost")
        if data.get("cancelled") is True:
            raise InputError("Orca check was cancelled")
        if not isinstance(data, dict) or data.get("runId", data.get("run_id")) != run_id:
            raise InputError("Orca check receipt run ID mismatch or missing")
        messages = data.get("messages")
        if not isinstance(messages, list) or any(not isinstance(item, dict) for item in messages):
            raise InputError("Orca check receipt messages schema is invalid")
        if messages:
            delivery_id = data.get("deliveryId", data.get("delivery_id"))
            if not isinstance(delivery_id, str) or not delivery_id.strip() or delivery_id != delivery_id.strip():
                raise InputError("deliveryId must be a nonempty trimmed string")
            compact = []
            for message in messages:
                payload = _message_payload(message)
                message_id = message.get("id")
                message_type = message.get("type")
                if not isinstance(message_id, str) or not message_id.strip() or message_id != message_id.strip():
                    raise InputError("id must be a nonempty trimmed string")
                if not isinstance(message_type, str) or not message_type.strip() or message_type != message_type.strip():
                    raise InputError("type must be a nonempty trimmed string")
                subject = message.get("subject", "")
                if not isinstance(subject, str):
                    raise InputError("subject must be a string")
                body = message.get("body", "")
                if not isinstance(body, str):
                    raise InputError("body must be a string")
                normalized_payload = {}
                for source, output in (("taskId", "task_id"), ("dispatchId", "dispatch_id")):
                    if source in payload:
                        value = payload[source]
                        if not isinstance(value, str) or not value.strip() or value != value.strip():
                            raise InputError(f"{source} must be a nonempty trimmed string")
                        normalized_payload[output] = value
                if "outcome" in payload:
                    value = payload["outcome"]
                    if value not in ("succeeded", "failed") or not isinstance(value, str):
                        raise InputError("outcome must be succeeded or failed")
                    normalized_payload["outcome"] = value
                if "reportPath" in payload:
                    value = payload["reportPath"]
                    if value is not None and (not isinstance(value, str) or not value.strip() or value != value.strip()):
                        raise InputError("reportPath must be null or a nonempty trimmed string")
                    normalized_payload["report_path"] = value
                compact.append({"id": message_id,
                                "type": message_type,
                                "subject": subject,
                                "body_preview": body[:1000], "body_truncated": len(body) > 1000,
                                **normalized_payload})
            return {"event": "messages", "run_id": run_id, "delivery_id": delivery_id,
                    "messages": compact, "review_before_ack": True, "acknowledged": False}
        timed_out = data.get("timedOut", data.get("timed_out"))
        if timed_out is not True:
            raise InputError("Orca check returned no messages without a timeout receipt")


def _timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise InputError(f"{field} must be a timezone-aware ISO8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise InputError(f"{field} must be a timezone-aware ISO8601 timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise InputError(f"{field} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _event_time(record: dict[str, Any], field: str) -> datetime:
    return _timestamp(record.get("timestamp"), field)


def _counters(value: Any, field: str) -> dict[str, int | None]:
    if not isinstance(value, dict):
        raise InputError(f"{field} must be an object")
    result: dict[str, int | None] = {}
    for key in ("input_tokens", "output_tokens", "total_tokens"):
        number = value.get(key)
        if isinstance(number, bool) or not isinstance(number, int) or number < 0:
            raise InputError(f"{field}.{key} must be a nonnegative integer")
        result[key] = number
    if result["input_tokens"] + result["output_tokens"] != result["total_tokens"]:
        raise InputError(f"{field}.total_tokens must equal input_tokens + output_tokens")
    for key in ("cached_input_tokens", "reasoning_output_tokens"):
        number = value.get(key)
        if number is not None and (isinstance(number, bool) or not isinstance(number, int) or number < 0):
            raise InputError(f"{field}.{key} must be a nonnegative integer when present")
        result[key] = number
    if result["cached_input_tokens"] is not None and result["cached_input_tokens"] > result["input_tokens"]:
        raise InputError(f"{field}.cached_input_tokens exceeds input_tokens")
    if result["reasoning_output_tokens"] is not None and result["reasoning_output_tokens"] > result["output_tokens"]:
        raise InputError(f"{field}.reasoning_output_tokens exceeds output_tokens")
    return result


METRICS = ("input_tokens", "cached_input_tokens", "uncached_input_tokens", "output_tokens", "reasoning_output_tokens", "total_tokens")


def _log(path: Path, expected_id: str) -> dict[str, Any]:
    meta = None
    models: list[str] = []
    checkpoints: list[tuple[datetime, dict[str, int | None], Any]] = []
    tasks: list[tuple[str, datetime]] = []
    try:
        with path.open(encoding="utf-8") as stream:
            for line_no, line in enumerate(stream, 1):
                try:
                    record = json.loads(line, object_pairs_hook=_pairs, parse_constant=_constant, parse_float=_float)
                except (json.JSONDecodeError, InputError) as error:
                    raise InputError(f"{path}:{line_no}: malformed JSON: {error}") from error
                if not isinstance(record, dict):
                    raise InputError(f"{path}:{line_no}: record must be an object")
                kind, payload = record.get("type"), record.get("payload", {})
                if not isinstance(payload, dict):
                    raise InputError(f"{path}:{line_no}: payload must be an object")
                if kind == "session_meta":
                    session_id = payload.get("id", payload.get("session_id"))
                    if not isinstance(session_id, str):
                        raise InputError(f"{path}:{line_no}: session_meta ID is missing")
                    if session_id != expected_id:
                        raise InputError(f"{path}: session_meta ID does not match manifest")
                    if meta is not None and meta != session_id:
                        raise InputError(f"{path}:{line_no}: conflicting session metadata")
                    meta = session_id
                elif kind == "turn_context":
                    value = payload.get("model")
                    if value is not None:
                        _string(value, f"{path}:{line_no} model")
                        if value not in models:
                            models.append(value)
                elif kind == "event_msg":
                    event_type = payload.get("type")
                    info = payload.get("info")
                    if event_type in ("task_started", "task_complete"):
                        tasks.append((event_type, _event_time(record, f"{path}:{line_no} timestamp")))
                        continue
                    if event_type != "token_count" or not isinstance(info, dict):
                        continue
                    if "total_token_usage" not in info or "last_token_usage" not in info:
                        raise InputError(f"{path}:{line_no}: token_count is missing usage counters")
                    cumulative = _counters(info["total_token_usage"], f"{path}:{line_no} total_token_usage")
                    stamp = _event_time(record, f"{path}:{line_no} timestamp")
                    checkpoints.append((stamp, cumulative, info["last_token_usage"]))
    except OSError as error:
        raise InputError(f"cannot read session log {path}: {error}") from error
    if meta is None:
        raise InputError(f"{path}: session_meta is missing")
    increments: list[tuple[datetime, dict[str, int | None]]] = []
    duplicate_stamps: list[datetime] = []
    previous: dict[str, int | None] | None = None
    for stamp, cumulative, raw_last in checkpoints:
        if previous is not None and cumulative == previous:
            duplicate_stamps.append(stamp)
            continue
        last = _counters(raw_last, f"{path} last_token_usage")
        if previous is None:
            for key in ("input_tokens", "output_tokens", "total_tokens"):
                if cumulative[key] != last[key]:
                    raise InputError(f"{path}: first cumulative counters do not reconcile last_token_usage; origin is incomplete")
            for key in ("cached_input_tokens", "reasoning_output_tokens"):
                if cumulative[key] is not None and last[key] is not None and cumulative[key] != last[key]:
                    raise InputError(f"{path}: first cumulative {key} does not reconcile last_token_usage; origin is incomplete")
        else:
            for key in ("input_tokens", "output_tokens", "total_tokens"):
                delta = cumulative[key] - previous[key]
                if delta < 0:
                    raise InputError(f"{path}: cumulative token counter reset")
                if delta != last[key]:
                    raise InputError(f"{path}: cumulative delta does not match last_token_usage")
            for key in ("cached_input_tokens", "reasoning_output_tokens"):
                old, new = previous[key], cumulative[key]
                if old is not None and new is not None:
                    delta = new - old
                    if delta < 0:
                        raise InputError(f"{path}: cumulative {key} counter reset")
                    if last[key] is not None and delta != last[key]:
                        raise InputError(f"{path}: cumulative {key} delta does not match last_token_usage")
        if previous is None:
            increment = dict(last)
        else:
            increment = {key: (None if cumulative[key] is None or previous[key] is None else cumulative[key] - previous[key])
                         for key in cumulative}
        if increment["cached_input_tokens"] is not None and increment["cached_input_tokens"] > increment["input_tokens"]:
            raise InputError(f"{path}: cached token delta exceeds input delta")
        if increment["reasoning_output_tokens"] is not None and increment["reasoning_output_tokens"] > increment["output_tokens"]:
            raise InputError(f"{path}: reasoning token delta exceeds output delta")
        increments.append((stamp, increment))
        previous = cumulative
    return {"models": models, "checkpoints": increments, "duplicate_stamps": duplicate_stamps,
            "duplicate_checkpoint_count": len(duplicate_stamps), "task_events": tasks,
            "first": checkpoints[0][0] if checkpoints else None,
            "last": checkpoints[-1][0] if checkpoints else None}


def _scope(spec: dict[str, Any], label: str) -> tuple[datetime | None, datetime | None]:
    start, end = spec.get("start"), spec.get("end")
    if (start is None) != (end is None):
        raise InputError(f"{label} must provide both start and end")
    if start is None:
        return None, None
    start_dt, end_dt = _timestamp(start, f"{label}.start"), _timestamp(end, f"{label}.end")
    if start_dt >= end_dt:
        raise InputError(f"{label} start must be before end")
    return start_dt, end_dt


def usage(manifest: Any, manifest_path: Path) -> dict[str, Any]:
    if not isinstance(manifest, dict) or not isinstance(manifest.get("sessions"), list) or not manifest["sessions"]:
        raise InputError("usage manifest must be an object with a nonempty sessions array")
    sessions = []
    for index, spec in enumerate(manifest["sessions"]):
        label = f"sessions[{index}]"
        if not isinstance(spec, dict):
            raise InputError(f"{label} must be an object")
        session_id = _string(spec.get("session_id"), f"{label}.session_id", trimmed=True)
        role = spec.get("role")
        if role not in ("controller", "worker"):
            raise InputError(f"{label}.role must be controller or worker")
        path_text = _string(spec.get("path"), f"{label}.path")
        if Path(path_text).suffix != ".jsonl":
            raise InputError(f"{label}.path must name a .jsonl file")
        path = Path(path_text)
        if not path.is_absolute():
            path = manifest_path.parent / path
        start, end = _scope(spec, label)
        logs = _log(path, session_id)
        sessions.append({"session_id": session_id, "role": role, "path": path,
                         "start": start, "end": end, **logs})
    by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for session in sessions:
        by_session[session["session_id"]].append(session)
    unique: list[dict[str, Any]] = []
    duplicate_count = 0
    for session_id, group in by_session.items():
        if len({session["role"] for session in group}) > 1:
            raise InputError(f"session {session_id} has conflicting roles")
        kept: list[dict[str, Any]] = []
        for current in group:
            same = next((prior for prior in kept if prior["start"] == current["start"] and prior["end"] == current["end"]), None)
            if same:
                signature = lambda item: (item["role"], item["models"], item["checkpoints"], item["duplicate_stamps"], item["task_events"])
                if signature(same) != signature(current):
                    raise InputError(f"session {session_id} has conflicting duplicate logs or roles")
                duplicate_count += 1
                continue
            for prior in kept:
                a0, a1 = prior["start"], prior["end"]
                b0, b1 = current["start"], current["end"]
                if a0 is None or b0 is None or max(a0, b0) < min(a1, b1):
                    raise InputError(f"session {session_id} has overlapping scopes")
            kept.append(current)
        unique.extend(kept)
    rows = []
    for session in unique:
        start, end = session["start"], session["end"]
        chosen = [(stamp, counters) for stamp, counters in session["checkpoints"]
                  if (start is None or stamp >= start) and (end is None or stamp < end)]
        chosen_duplicates = [stamp for stamp in session["duplicate_stamps"]
                             if (start is None or stamp >= start) and (end is None or stamp < end)]
        totals = {metric: None for metric in METRICS}
        if chosen:
            sums = {key: 0 for key in ("input_tokens", "output_tokens", "total_tokens")}
            option_known = {"cached_input_tokens": True, "reasoning_output_tokens": True}
            optional_sums = {"cached_input_tokens": 0, "reasoning_output_tokens": 0}
            for _, counters in chosen:
                for key in sums:
                    sums[key] += counters[key]
                for key in option_known:
                    if counters[key] is None:
                        option_known[key] = False
                    else:
                        optional_sums[key] += counters[key]
            totals.update(sums)
            totals["cached_input_tokens"] = optional_sums["cached_input_tokens"] if option_known["cached_input_tokens"] else None
            totals["uncached_input_tokens"] = (sums["input_tokens"] - totals["cached_input_tokens"]
                                                  if totals["cached_input_tokens"] is not None else None)
            totals["reasoning_output_tokens"] = optional_sums["reasoning_output_tokens"] if option_known["reasoning_output_tokens"] else None
        rows.append({"session_id": session["session_id"], "role": session["role"],
                     "scope": "supplied_session" if start is None else "completion_window",
                     "start": start.isoformat() if start else None, "end": end.isoformat() if end else None,
                     "previous_boundary": (max((stamp for stamp, _ in session["checkpoints"] if start and stamp < start), default=None).isoformat()
                                           if start and any(stamp < start for stamp, _ in session["checkpoints"]) else None),
                     "next_boundary": (min((stamp for stamp, _ in session["checkpoints"] if end and stamp >= end), default=None).isoformat()
                                        if end and any(stamp >= end for stamp, _ in session["checkpoints"]) else None),
                     "attribution": "completion_window" if start else "supplied_session",
                     "causal_split": "unknown", "models": session["models"], "usage": totals,
                     "task_started": sum(kind == "task_started" and (start is None or stamp >= start) and (end is None or stamp < end) for kind, stamp in session["task_events"]),
                     "task_complete": sum(kind == "task_complete" and (start is None or stamp >= start) and (end is None or stamp < end) for kind, stamp in session["task_events"]),
                     "usage_event_count": len(chosen), "duplicate_checkpoint_count": len(chosen_duplicates)})
    def aggregate(selected: list[dict[str, Any]]) -> dict[str, Any]:
        metrics = {}
        for metric in METRICS:
            vals = [row["usage"][metric] for row in selected if row["usage"][metric] is not None]
            metrics[metric] = {"measured_sessions": len(vals), "session_count": len(selected),
                               "total": sum(vals) if len(vals) == len(selected) and vals else (0 if selected and len(vals) == len(selected) else None)}
        return {"session_count": len(selected), "models": sorted({model for row in selected for model in row["models"]}), "metrics": metrics}
    return {"sessions": rows, "duplicates_removed": duplicate_count,
            "duplicate_checkpoint_count": sum(row["duplicate_checkpoint_count"] for row in rows),
            "duplicate_checkpoint_validation_count": sum(session["duplicate_checkpoint_count"] for session in unique),
            "controller": aggregate([row for row in rows if row["role"] == "controller"]),
            "worker": aggregate([row for row in rows if row["role"] == "worker"]),
            "combined": aggregate(rows), "cost": None}


def emit(value: Any) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan_parser = commands.add_parser("plan")
    plan_parser.add_argument("path", type=Path)
    plan_parser.add_argument("--workers", type=int, default=1)
    plan_parser.add_argument("--completed", action="append", default=[])
    plan_parser.add_argument("--active", action="append", default=[])
    plan_parser.add_argument("--max-brief-chars", type=int, default=6000)
    wait_parser = commands.add_parser("wait")
    wait_parser.add_argument("--run", required=True)
    wait_parser.add_argument("--timeout-seconds", type=float, default=300)
    usage_parser = commands.add_parser("usage")
    usage_parser.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            emit(plan(_read_json(args.path), args.workers, args.completed, args.active, args.max_brief_chars))
        elif args.command == "wait":
            emit(wait_for_messages(args.run, args.timeout_seconds))
        else:
            emit(usage(_read_json(args.path), args.path.resolve()))
        return 0
    except (InputError, OSError, UnicodeError, ValueError, OverflowError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
