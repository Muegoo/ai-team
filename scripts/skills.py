"""Audit a declared skills registry without discovering or installing skills."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    from .practice_common import InputError, emit, read_bytes, read_json, relative_path, resolve_local, safe_error
except ImportError:
    from practice_common import InputError, emit, read_bytes, read_json, relative_path, resolve_local, safe_error

ROLES = {"controller", "executor", "research"}
STATUSES = {"active", "candidate"}
VERDICTS = {"unreviewed", "keep", "improve", "update", "retire", "merge"}
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def _date(value: Any, field: str) -> None:
    if value is not None:
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise InputError(f"{field} must be an ISO date or null")
        try:
            date.fromisoformat(value)
        except ValueError as error:
            raise InputError(f"{field} must be an ISO date or null") from error


def _validate_registry(data: Any) -> list[dict[str, Any]]:
    if (not isinstance(data, dict) or set(data) != {"schema_version", "skills"}
            or type(data.get("schema_version")) is not int or data["schema_version"] != 1
            or not isinstance(data.get("skills"), list)):
        raise InputError("registry must have schema_version 1 and a skills array")
    ids: set[str] = set()
    records: list[dict[str, Any]] = []
    for index, skill in enumerate(data["skills"]):
        label = f"skills[{index}]"
        if not isinstance(skill, dict):
            raise InputError(f"{label} must be an object")
        required = {"id", "name", "path", "source_url", "source_revision", "role", "triggers",
                    "overlap_group", "status", "review"}
        if set(skill) != required:
            raise InputError(f"{label} has missing or unknown fields")
        skill_id = skill.get("id")
        if not isinstance(skill_id, str) or not ID_RE.fullmatch(skill_id):
            raise InputError(f"{label}.id is invalid")
        if skill_id in ids:
            raise InputError(f"duplicate skill id: {skill_id}")
        ids.add(skill_id)
        if not isinstance(skill.get("name"), str) or not skill["name"].strip():
            raise InputError(f"{label}.name must be a nonempty string")
        path = skill.get("path")
        if skill.get("status") == "active":
            if not isinstance(path, str) or not path.endswith("SKILL.md"):
                raise InputError(f"{label}.path must name a local SKILL.md for active skills")
        elif skill.get("status") == "candidate":
            if path is not None:
                raise InputError(f"{label}.path must be null for candidates")
        else:
            raise InputError(f"{label}.status is invalid")
        if path is not None:
            relative_path(path, f"{label}.path")
        source_url = skill.get("source_url")
        if source_url is not None:
            parsed = urlparse(source_url) if isinstance(source_url, str) else None
            if parsed is None or parsed.scheme != "https" or not parsed.netloc:
                raise InputError(f"{label}.source_url must be HTTPS or null")
        revision = skill.get("source_revision")
        if revision is not None and (not isinstance(revision, str) or not revision.strip()):
            raise InputError(f"{label}.source_revision must be a nonempty string or null")
        if not isinstance(skill.get("role"), str) or skill["role"] not in ROLES:
            raise InputError(f"{label}.role is invalid")
        triggers = skill.get("triggers")
        if not isinstance(triggers, list) or not triggers or any(not isinstance(item, str) or not item.strip() for item in triggers):
            raise InputError(f"{label}.triggers must be a nonempty list of strings")
        overlap = skill.get("overlap_group")
        if overlap is not None and (not isinstance(overlap, str) or not overlap.strip()):
            raise InputError(f"{label}.overlap_group must be a nonempty string or null")
        review = skill.get("review")
        if (not isinstance(review, dict) or set(review) != {"verdict", "reason", "reviewed_at"}
                or not isinstance(review.get("verdict"), str) or review["verdict"] not in VERDICTS):
            raise InputError(f"{label}.review is invalid")
        if not isinstance(review.get("reason"), str) or not review["reason"].strip():
            raise InputError(f"{label}.review.reason must be a nonempty string")
        _date(review.get("reviewed_at"), f"{label}.review.reviewed_at")
        records.append(skill)
    return records


def _validate_snapshot(data: Any) -> dict[str, dict[str, Any]]:
    required_top = {"schema_version", "source_freshness", "skills", "findings", "changes", "snapshot",
                    "metadata_labels_prove_installed_identity_or_authorization"}
    if (not isinstance(data, dict) or set(data) != required_top or type(data.get("schema_version")) is not int
            or data["schema_version"] != 1 or data.get("source_freshness") != "not_checked"
            or data.get("metadata_labels_prove_installed_identity_or_authorization") is not False
            or not isinstance(data.get("skills"), list) or not isinstance(data.get("findings"), list)
            or not isinstance(data.get("changes"), dict)):
        raise InputError("previous input must be a CLI inventory snapshot")
    change_fields = {"new_ids", "removed_ids", "metadata_changed_ids", "content_changed_ids"}
    if set(data["changes"]) != change_fields or any(
            not isinstance(data["changes"][field], list)
            or any(not isinstance(value, str) for value in data["changes"][field]) for field in change_fields):
        raise InputError("previous snapshot contains invalid change metadata")
    snapshot = data.get("snapshot") if isinstance(data, dict) else None
    if (not isinstance(snapshot, dict) or set(snapshot) != {"schema_version", "skills"}
            or type(snapshot.get("schema_version")) is not int or snapshot["schema_version"] != 1
            or not isinstance(snapshot.get("skills"), list)):
        raise InputError("previous input must be a CLI inventory snapshot")
    result: dict[str, dict[str, Any]] = {}
    summaries = {}
    for item in data["skills"]:
        if (not isinstance(item, dict) or set(item) != {"id", "name", "path", "exists", "content_sha256",
                                                        "metadata_sha256", "source_freshness"}
                or not isinstance(item.get("id"), str)
                or item.get("source_freshness") != "not_checked"
                or not isinstance(item.get("metadata_sha256"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", item["metadata_sha256"])):
            raise InputError("previous snapshot contains an invalid inventory record")
        if item["id"] in summaries:
            raise InputError("previous snapshot has duplicate skill IDs")
        summaries[item["id"]] = item
    for item in snapshot["skills"]:
        if (not isinstance(item, dict) or set(item) != {"id", "metadata", "content_sha256"}
                or not isinstance(item.get("id"), str) or not isinstance(item.get("metadata"), dict)):
            raise InputError("previous snapshot contains an invalid skill record")
        if item["id"] in result:
            raise InputError("previous snapshot has duplicate skill IDs")
        digest = item.get("content_sha256")
        if digest is not None and (not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
            raise InputError("previous snapshot contains an invalid content digest")
        metadata = _validate_registry({"schema_version": 1, "skills": [item["metadata"]]})[0]
        if metadata["id"] != item["id"]:
            raise InputError("previous snapshot skill ID does not match metadata")
        summary = summaries.get(item["id"])
        if summary is None or summary["metadata_sha256"] != hashlib.sha256(
                json.dumps(metadata, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest():
            raise InputError("previous snapshot metadata does not match inventory")
        if summary["content_sha256"] != digest:
            raise InputError("previous snapshot content digest does not match inventory")
        result[item["id"]] = item
    if set(summaries) != set(result):
        raise InputError("previous snapshot inventory and snapshot IDs differ")
    return result


def audit(registry: Any, registry_path: Path, previous: Any = None) -> dict[str, Any]:
    records = _validate_registry(registry)
    root = registry_path.resolve().parent
    findings: list[dict[str, Any]] = []
    inventory = []
    snapshot_items = []
    names: dict[str, list[str]] = {}
    groups: dict[str, list[str]] = {}
    contents: dict[str, list[str]] = {}
    for record in records:
        names.setdefault(record["name"].casefold(), []).append(record["id"])
        if record["overlap_group"] is not None:
            groups.setdefault(record["overlap_group"], []).append(record["id"])
        raw = json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        metadata_sha = hashlib.sha256(raw).hexdigest()
        content_sha = None
        exists = None
        if record["path"] is not None:
            path = resolve_local(root, record["path"], f"skill {record['id']} path")
            try:
                data = read_bytes(path)
            except InputError as error:
                exists = path.is_file()
                findings.append({"rule": "local_file_unavailable", "skill_ids": [record["id"]], "detail": "local skill file is missing or unreadable"})
            else:
                exists = True
                content_sha = hashlib.sha256(data).hexdigest()
                contents.setdefault(content_sha, []).append(record["id"])
        if record["source_url"] is not None and (record["source_revision"] is None or
                not re.fullmatch(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})", record["source_revision"])):
            findings.append({"rule": "remote_revision_unpinned", "skill_ids": [record["id"]], "source_freshness": "not_checked"})
        inventory.append({"id": record["id"], "name": record["name"], "path": record["path"],
                          "exists": exists, "content_sha256": content_sha,
                          "metadata_sha256": metadata_sha, "source_freshness": "not_checked"})
        snapshot_items.append({"id": record["id"], "metadata": record, "content_sha256": content_sha})
    for ids in names.values():
        if len(ids) > 1:
            findings.append({"rule": "duplicate_name", "skill_ids": sorted(ids)})
    for group, ids in groups.items():
        if len(ids) > 1:
            findings.append({"rule": "shared_overlap_group", "overlap_group": group, "skill_ids": sorted(ids)})
    for digest, ids in contents.items():
        if len(ids) > 1:
            findings.append({"rule": "identical_local_content", "content_sha256": digest, "skill_ids": sorted(ids)})
    changes = {"new_ids": [], "removed_ids": [], "metadata_changed_ids": [], "content_changed_ids": []}
    if previous is not None:
        old = _validate_snapshot(previous)
        current = {item["id"]: item for item in snapshot_items}
        changes["new_ids"] = sorted(current.keys() - old.keys())
        changes["removed_ids"] = sorted(old.keys() - current.keys())
        for skill_id in sorted(current.keys() & old.keys()):
            if current[skill_id]["metadata"] != old[skill_id]["metadata"]:
                changes["metadata_changed_ids"].append(skill_id)
            if current[skill_id]["content_sha256"] != old[skill_id]["content_sha256"]:
                changes["content_changed_ids"].append(skill_id)
    return {"schema_version": 1, "source_freshness": "not_checked", "skills": inventory,
            "findings": findings, "changes": changes,
            "snapshot": {"schema_version": 1, "skills": snapshot_items},
            "metadata_labels_prove_installed_identity_or_authorization": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    audit_parser = commands.add_parser("audit", help="inventory a declared registry")
    audit_parser.add_argument("registry", type=Path)
    audit_parser.add_argument("--previous", type=Path)
    args = parser.parse_args(argv)
    try:
        registry = read_json(args.registry)
        previous = read_json(args.previous) if args.previous else None
        emit(audit(registry, args.registry, previous))
        return 0
    except (InputError, OSError, ValueError) as error:
        print(f"error: {safe_error(error)}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
