"""Run fixed local repository checks without configurable shell commands."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any

try:
    from .contracts import validate_contract
    from .lessons import validate_store
    from .practice_common import InputError, emit, loads_json, read_json
    from .skills import audit
except ImportError:
    from contracts import validate_contract
    from lessons import validate_store
    from practice_common import InputError, emit, loads_json, read_json
    from skills import audit

MAX_STAGED_BYTES = 1_048_576
TIMEOUT_SECONDS = 120
SECRET_RULES = (
    ("PRIVATE_KEY_HEADER", re.compile(rb"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----")),
    ("AWS_ACCESS_KEY_ID", re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("GITHUB_TOKEN", re.compile(rb"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})\b")),
    ("OPENAI_STYLE_KEY", re.compile(rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b")),
)
SKIP_DIRS = {".git", ".build", ".cache", ".pytest_cache", ".mypy_cache", ".serena", ".codegraph",
             "node_modules", "__pycache__", ".venv", "graft", "cache", "caches"}


def _run(command: list[str], root: Path, *, runner: Any = subprocess.run, timeout: int = 15) -> subprocess.CompletedProcess:
    return runner(command, cwd=str(root), capture_output=True, timeout=timeout, shell=False)


def _protected_path(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return any(part.casefold() in SKIP_DIRS or part.casefold().startswith(".env") or part.casefold() == ".bashrc"
               for part in parts)


def _validate_registry_state(data: Any, registry_path: Path) -> dict[str, Any]:
    inventory = audit(data, registry_path)
    unreadable_active = any(item["path"] is not None and
                            (item["exists"] is not True or item["content_sha256"] is None)
                            for item in inventory["skills"])
    if unreadable_active or any(finding["rule"] == "local_file_unavailable"
                                for finding in inventory["findings"]):
        raise InputError("active local skill file is missing or unreadable")
    return inventory


def scan_staged(root: Path, *, runner: Any = subprocess.run) -> dict[str, Any]:
    skipped = {"protected": 0, "generated": 0, "symlink_or_submodule": 0, "binary": 0, "oversized": 0, "unavailable": 0}
    try:
        changed = _run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"], root, runner=runner)
        indexed = _run(["git", "ls-files", "--stage", "-z"], root, runner=runner)
    except (OSError, subprocess.TimeoutExpired):
        return {"status": "failed", "exit_code": 1, "error": "git index read failed", "diagnostics": [], "skipped": skipped, "scope_limited": True}
    if changed.returncode != 0 or indexed.returncode != 0:
        code = changed.returncode if changed.returncode != 0 else indexed.returncode
        return {"status": "failed", "exit_code": code or 1, "error": "git index read failed", "diagnostics": [], "skipped": skipped, "scope_limited": True}
    changed_paths = [item for item in changed.stdout.split(b"\0") if item]
    index_entries: dict[bytes, tuple[str, str]] = {}
    for entry in indexed.stdout.split(b"\0"):
        if not entry or b"\t" not in entry:
            continue
        metadata, raw_path = entry.split(b"\t", 1)
        fields = metadata.split()
        if len(fields) != 3:
            continue
        mode, object_id, stage = fields
        index_entries[raw_path] = (mode.decode("ascii", "ignore"), object_id.decode("ascii", "ignore") if stage == b"0" else "")
    diagnostics = []
    scan_error = None
    validators = {
        "skills-registry.json": lambda value: _validate_registry_state(value, root / "skills-registry.json"),
        "knowledge/lessons.json": lambda value: validate_store(value, root / "knowledge/lessons.json", root),
        "examples/practices/contract.json": lambda value: validate_contract(value, root / "examples/practices/contract.json", root),
    }
    for raw_path in changed_paths:
        path = raw_path.decode("utf-8", "backslashreplace")
        validator = validators.get(path)
        parts = PurePosixPath(path).parts
        if any(part.casefold().startswith(".env") or part.casefold() == ".bashrc" for part in parts):
            skipped["protected"] += 1
            continue
        if any(part.casefold() in SKIP_DIRS for part in parts):
            skipped["generated"] += 1
            continue
        mode, object_id = index_entries.get(raw_path, ("", ""))
        if mode in {"120000", "160000"}:
            if validator is not None:
                diagnostics.append({"path": path, "line": 1, "rule_id": "INVALID_STAGED_JSON"})
            else:
                skipped["symlink_or_submodule"] += 1
            continue
        if not object_id:
            if validator is not None:
                diagnostics.append({"path": path, "line": 1, "rule_id": "INVALID_STAGED_JSON"})
            else:
                scan_error = "staged blob read failed"
                break
            continue
        try:
            size_result = _run(["git", "cat-file", "-s", object_id], root, runner=runner)
            if size_result.returncode != 0:
                scan_error = "staged blob read failed"
                break
            size = int(size_result.stdout.strip())
            if size > MAX_STAGED_BYTES:
                if validator is not None:
                    diagnostics.append({"path": path, "line": 1, "rule_id": "INVALID_STAGED_JSON"})
                else:
                    skipped["oversized"] += 1
                continue
            blob = _run(["git", "cat-file", "blob", object_id], root, runner=runner)
        except (OSError, subprocess.TimeoutExpired, ValueError):
            scan_error = "staged blob read failed"
            break
        if blob.returncode != 0:
            scan_error = "staged blob read failed"
            break
        content = blob.stdout
        if b"\0" in content:
            if validator is not None:
                diagnostics.append({"path": path, "line": 1, "rule_id": "INVALID_STAGED_JSON"})
            else:
                skipped["binary"] += 1
                continue
        if validator is not None:
            try:
                staged_data = loads_json(content.decode("utf-8"))
                validator(staged_data)
            except (InputError, UnicodeDecodeError, ValueError):
                diagnostics.append({"path": path, "line": 1, "rule_id": "INVALID_STAGED_JSON"})
        for line_number, line in enumerate(content.splitlines(), 1):
            for rule_id, pattern in SECRET_RULES:
                if pattern.search(line):
                    diagnostics.append({"path": path, "line": line_number, "rule_id": rule_id})
    return {"status": "failed" if diagnostics or scan_error else "passed",
            "exit_code": 1 if diagnostics or scan_error else 0,
            "diagnostics": diagnostics, "skipped": skipped, "scope_limited": True,
            "error": scan_error,
            "note": "limited staged-index scan; skipped coverage is reported; not a security assurance"}


def _minimal_checks(root: Path) -> list[dict[str, Any]]:
    results = []
    registry_path = root / "skills-registry.json"
    try:
        registry = read_json(registry_path)
        inventory = _validate_registry_state(registry, registry_path)
        results.append({"name": "skills_registry", "status": "passed", "exit_code": 0,
                        "skill_count": len(inventory["skills"])})
    except (InputError, OSError, ValueError):
        results.append({"name": "skills_registry", "status": "failed", "exit_code": 1})
    store_path = root / "knowledge/lessons.json"
    try:
        store = validate_store(read_json(store_path), store_path, root)
        results.append({"name": "lesson_store", "status": "passed", "exit_code": 0,
                        "lesson_count": len(store["lessons"])})
    except (InputError, OSError, ValueError):
        results.append({"name": "lesson_store", "status": "failed", "exit_code": 1})
    contract_path = root / "examples/practices/contract.json"
    try:
        contract = validate_contract(read_json(contract_path), contract_path, root)
        results.append({"name": "example_contract", "status": "passed", "exit_code": 0,
                        "ticket_count": len(contract["tickets"])})
    except (InputError, OSError, ValueError):
        results.append({"name": "example_contract", "status": "failed", "exit_code": 1})
    return results


def _diff_check(root: Path, runner: Any) -> dict[str, Any]:
    try:
        result = _run(["git", "diff", "--check"], root, runner=runner, timeout=30)
        changed = _run(["git", "diff", "--name-only", "-z"], root, runner=runner, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return {"name": "git_diff_check", "status": "failed", "exit_code": 1, "locations": []}
    if changed.returncode != 0:
        return {"name": "git_diff_check", "status": "failed", "exit_code": changed.returncode or 1, "locations": []}
    changed_paths = [item.decode("utf-8", "replace") for item in changed.stdout.split(b"\0") if item]
    locations = []
    raw = result.stdout if isinstance(result.stdout, bytes) else (result.stdout or "").encode()
    raw += result.stderr if isinstance(result.stderr, bytes) else (result.stderr or "").encode()
    violations = (b"trailing whitespace.", b"space before tab in indent.", b"new blank line at EOF.")
    for line in raw.splitlines():
        for path in changed_paths:
            prefix = re.escape(path.encode("utf-8", "surrogateescape"))
            match = re.match(rb"^" + prefix + rb":([0-9]+): (?:trailing whitespace|space before tab in indent|new blank line at EOF)\.$", line)
            if match and any(line.endswith(violation) for violation in violations):
                locations.append({"path": path, "line": int(match.group(1))})
                break
    return {"name": "git_diff_check", "status": "passed" if result.returncode == 0 else "failed",
            "exit_code": result.returncode, "locations": locations}


def run_profile(profile: str, root: Path, *, staged: bool = False, runner: Any = subprocess.run) -> tuple[dict[str, Any], int]:
    if profile not in {"minimal", "standard", "strict"}:
        raise InputError("profile must be minimal, standard, or strict")
    checks = _minimal_checks(root)
    if profile in {"standard", "strict"}:
        command = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"]
        try:
            result = runner(command, cwd=str(root), capture_output=True, text=True, timeout=TIMEOUT_SECONDS, shell=False)
            output = f"{result.stdout or ''}\n{result.stderr or ''}"
            match = re.search(r"Ran ([0-9]+) tests?", output)
            checks.append({"name": "unit_tests", "status": "passed" if result.returncode == 0 else "failed",
                           "exit_code": result.returncode, "test_count": int(match.group(1)) if match else None})
        except subprocess.TimeoutExpired:
            checks.append({"name": "unit_tests", "status": "failed", "exit_code": 124, "test_count": None})
        except OSError:
            checks.append({"name": "unit_tests", "status": "failed", "exit_code": 127, "test_count": None})
    if profile == "strict":
        checks.append(_diff_check(root, runner))
    if staged:
        scan = scan_staged(root, runner=runner)
        checks.append({"name": "staged_secret_scan", **scan})
    failures = [check for check in checks if check["status"] == "failed"]
    exit_code = next((max(1, min(255, int(check.get("exit_code") or 1))) for check in failures), 0)
    return {"profile": profile, "checks": checks,
            "acceptance_claimed": False, "working_tree_checks": True}, exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("minimal", "standard", "strict"), default="minimal")
    parser.add_argument("--staged", action="store_true")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    try:
        report, status = run_profile(args.profile, root, staged=args.staged)
        emit(report)
        return status
    except InputError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
