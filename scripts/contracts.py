"""Validate a traceable practice contract and render workflow input or a task brief."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

try:
    from .practice_common import InputError, emit, read_json, relative_path, resolve_local, safe_error
except ImportError:
    from practice_common import InputError, emit, read_json, relative_path, resolve_local, safe_error


def _strings(value: Any, field: str, *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or (nonempty and not value):
        raise InputError(f"{field} must be a {'nonempty ' if nonempty else ''}list of strings")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise InputError(f"{field} entries must be nonempty strings")
    return value


def validate_contract(data: Any, contract_path: Path, root_override: Path | None = None) -> dict[str, Any]:
    if (not isinstance(data, dict) or set(data) != {"schema_version", "spec", "tickets"}
            or type(data.get("schema_version")) is not int or data["schema_version"] != 1):
        raise InputError("contract must have schema_version 1")
    spec = data.get("spec")
    tickets = data.get("tickets")
    if not isinstance(spec, dict) or not isinstance(tickets, list) or not tickets:
        raise InputError("contract must contain spec and a nonempty tickets array")
    if set(spec) != {"spec_id", "problem", "outcome", "acceptance", "out_of_scope", "glossary", "decisions"}:
        raise InputError("spec has missing or unknown fields")
    for field in ("spec_id", "problem", "outcome"):
        if not isinstance(spec.get(field), str) or not spec[field].strip():
            raise InputError(f"spec.{field} must be a nonempty string")
    acceptance = spec.get("acceptance")
    if not isinstance(acceptance, list) or not acceptance:
        raise InputError("spec.acceptance must be a nonempty list")
    criteria: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(acceptance):
        label = f"spec.acceptance[{index}]"
        if not isinstance(item, dict):
            raise InputError(f"{label} must be an object")
        if set(item) != {"id", "description", "verification"}:
            raise InputError(f"{label} has missing or unknown fields")
        criterion_id = item.get("id")
        if not isinstance(criterion_id, str) or not criterion_id.strip() or criterion_id != criterion_id.strip():
            raise InputError(f"{label}.id must be a nonempty trimmed string")
        if criterion_id in criteria:
            raise InputError(f"duplicate acceptance id: {criterion_id}")
        if not isinstance(item.get("description"), str) or not item["description"].strip():
            raise InputError(f"{label}.description must be a nonempty string")
        checks = _strings(item.get("verification"), f"{label}.verification", nonempty=True)
        criteria[criterion_id] = {"id": criterion_id, "description": item["description"], "verification": checks}
    out_of_scope = _strings(spec.get("out_of_scope"), "spec.out_of_scope")
    glossary = spec.get("glossary")
    decisions = _strings(spec.get("decisions"), "spec.decisions")
    root = (root_override or contract_path.resolve().parent).resolve()
    if glossary is not None:
        resolve_local(root, glossary, "spec.glossary", must_exist=True)
    for index, path in enumerate(decisions):
        resolve_local(root, path, f"spec.decisions[{index}]", must_exist=True)
    by_id: dict[str, dict[str, Any]] = {}
    assigned: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(tickets):
        label = f"tickets[{index}]"
        if not isinstance(item, dict):
            raise InputError(f"{label} must be an object")
        if set(item) != {"task_id", "goal", "acceptance_ids", "worktree_id", "writable_paths",
                         "depends_on", "constraints", "review"}:
            raise InputError(f"{label} has missing or unknown fields")
        task_id = item.get("task_id")
        if not isinstance(task_id, str) or not task_id.strip() or task_id != task_id.strip():
            raise InputError(f"{label}.task_id must be a nonempty trimmed string")
        if task_id in by_id:
            raise InputError(f"duplicate task_id: {task_id}")
        goal = item.get("goal")
        if not isinstance(goal, str) or not goal.strip():
            raise InputError(f"{label}.goal must describe nonempty end-to-end behavior")
        acceptance_ids = _strings(item.get("acceptance_ids"), f"{label}.acceptance_ids", nonempty=True)
        if len(set(acceptance_ids)) != len(acceptance_ids):
            raise InputError(f"{label}.acceptance_ids contains duplicates")
        unknown = [value for value in acceptance_ids if value not in criteria]
        if unknown:
            raise InputError(f"{label} references unknown acceptance ID {unknown[0]}")
        assigned.update(acceptance_ids)
        worktree_id = item.get("worktree_id")
        if not isinstance(worktree_id, str) or not worktree_id.strip() or worktree_id != worktree_id.strip():
            raise InputError(f"{label}.worktree_id must be a nonempty trimmed opaque string")
        paths = _strings(item.get("writable_paths"), f"{label}.writable_paths", nonempty=True)
        paths = [relative_path(path, f"{label}.writable_paths") for path in paths]
        if len(set(paths)) != len(paths):
            raise InputError(f"{label}.writable_paths contains duplicates")
        dependencies = _strings(item.get("depends_on"), f"{label}.depends_on")
        if len(set(dependencies)) != len(dependencies):
            raise InputError(f"{label}.depends_on contains duplicates")
        constraints = _strings(item.get("constraints"), f"{label}.constraints")
        review = item.get("review")
        if review not in ("lead", "independent"):
            raise InputError(f"{label}.review must be lead or independent")
        task = {"task_id": task_id, "goal": goal, "acceptance_ids": acceptance_ids,
                "worktree_id": worktree_id, "writable_paths": paths,
                "depends_on": dependencies, "constraints": constraints, "review": review}
        normalized.append(task)
        by_id[task_id] = task
    missing_acceptance = sorted(set(criteria) - assigned)
    if missing_acceptance:
        raise InputError(f"acceptance criteria are unassigned: {', '.join(missing_acceptance)}")
    for task in normalized:
        for dependency in task["depends_on"]:
            if dependency not in by_id:
                raise InputError(f"task {task['task_id']} has unknown dependency {dependency}")
            if dependency == task["task_id"]:
                raise InputError(f"task {task['task_id']} depends on itself")
    visiting: set[str] = set()
    visited: set[str] = set()

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

    for task in normalized:
        visit(task["task_id"])
    return {"schema_version": 1, "spec": {"spec_id": spec["spec_id"], "problem": spec["problem"],
            "outcome": spec["outcome"], "acceptance": criteria, "out_of_scope": out_of_scope,
            "glossary": glossary, "decisions": decisions}, "tickets": normalized,
            "root": str(root)}


def plan_input(contract: dict[str, Any]) -> dict[str, Any]:
    criteria = contract["spec"]["acceptance"]
    tasks = []
    for ticket in contract["tickets"]:
        tasks.append({"task_id": ticket["task_id"], "goal": ticket["goal"],
                      "writable_paths": ticket["writable_paths"], "worktree_id": ticket["worktree_id"],
                      "acceptance": [f"{key}: {criteria[key]['description']}" for key in ticket["acceptance_ids"]],
                      "depends_on": ticket["depends_on"], "constraints": ticket["constraints"],
                      "review": ticket["review"]})
    return {"tasks": tasks}


def task_brief(contract: dict[str, Any], task_id: str) -> dict[str, Any]:
    ticket = next((item for item in contract["tickets"] if item["task_id"] == task_id), None)
    if ticket is None:
        raise InputError(f"unknown task_id: {task_id}")
    spec = contract["spec"]
    return {"spec_id": spec["spec_id"], "problem": spec["problem"], "outcome": spec["outcome"],
            "task_id": task_id, "goal": ticket["goal"], "worktree_id": ticket["worktree_id"],
            "writable_paths": ticket["writable_paths"], "depends_on": ticket["depends_on"],
            "constraints": ticket["constraints"], "review": ticket["review"],
            "acceptance": [spec["acceptance"][key] for key in ticket["acceptance_ids"]],
            "out_of_scope": spec["out_of_scope"], "glossary": spec["glossary"], "decisions": spec["decisions"],
            "invariant": "The controller owns behavior and architecture decisions. The executor implements the approved brief, runs its tests, and stops to escalate ambiguity or out-of-scope changes.",
            "worktree_identity_verified": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "plan-input", "brief"):
        command = commands.add_parser(name)
        command.add_argument("contract", type=Path)
        command.add_argument("--root", type=Path)
        if name == "brief":
            command.add_argument("--task", required=True)
    args = parser.parse_args(argv)
    try:
        contract = validate_contract(read_json(args.contract), args.contract, args.root)
        if args.command == "validate":
            result = {"valid": True, "spec_id": contract["spec"]["spec_id"],
                      "ticket_ids": [task["task_id"] for task in contract["tickets"]]}
        elif args.command == "plan-input":
            result = plan_input(contract)
        else:
            result = task_brief(contract, args.task)
        emit(result)
        return 0
    except (InputError, OSError, ValueError) as error:
        print(f"error: {safe_error(error)}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
