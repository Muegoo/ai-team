"""Shared strict input and path helpers for the practice CLIs."""

from __future__ import annotations

import json
import math
import unicodedata
from pathlib import Path, PurePosixPath
from typing import Any


class InputError(ValueError):
    pass


PROTECTED_PARTS = {".git", "node_modules", "__pycache__", ".serena", ".pytest_cache", ".mypy_cache",
                   ".build", ".codegraph", "graft", ".cache", "cache", "caches", ".venv"}


def _protected(path: Path, *, allow_generated: bool = False) -> bool:
    blocked = PROTECTED_PARTS - ({".build"} if allow_generated else set())
    return any(part.casefold() in blocked or part.casefold().startswith(".env")
               or part.casefold() == ".bashrc" for part in path.parts)


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise InputError("duplicate JSON object key")
        result[key] = value
    return result


def _constant(_value: str) -> None:
    raise InputError("nonfinite JSON number")


def _float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise InputError("nonfinite JSON number")
    return number


def loads_json(text: str) -> Any:
    try:
        return json.loads(text, object_pairs_hook=_object, parse_constant=_constant, parse_float=_float)
    except (json.JSONDecodeError, UnicodeError) as error:
        raise InputError("invalid JSON") from error


def read_bytes(path: Path, *, max_bytes: int = 1_048_576, allow_generated: bool = False) -> bytes:
    if _protected(path, allow_generated=allow_generated):
        raise InputError("refusing to read a protected path")
    try:
        resolved = path.resolve(strict=False)
        if _protected(resolved, allow_generated=allow_generated):
            raise InputError("refusing to read a protected path")
        with path.open("rb") as stream:
            data = stream.read(max_bytes + 1)
    except InputError:
        raise
    except (OSError, RuntimeError) as error:
        raise InputError(f"cannot read file {path}") from error
    if len(data) > max_bytes:
        raise InputError(f"file exceeds {max_bytes} byte limit: {path}")
    return data


def read_json(path: Path, *, max_bytes: int = 1_048_576) -> Any:
    try:
        text = read_bytes(path, max_bytes=max_bytes, allow_generated=True).decode("utf-8")
    except UnicodeDecodeError as error:
        raise InputError(f"file is not UTF-8: {path}") from error
    return loads_json(text)


def relative_path(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or any(unicodedata.category(char) == "Cc" for char in value):
        raise InputError(f"{field} must be a canonical relative POSIX path")
    path = PurePosixPath(value)
    if (path.is_absolute() or path.as_posix() != value or "\\" in value
            or any(part in ("", ".", "..") for part in value.split("/"))
            or any(char in value for char in "*?[]{}")):
        raise InputError(f"{field} must be a canonical relative POSIX path")
    return value


def resolve_local(root: Path, value: Any, field: str, *, must_exist: bool = False) -> Path:
    rel = relative_path(value, field)
    parts = PurePosixPath(rel).parts
    lowered = tuple(part.casefold() for part in parts)
    if any(part == ".git" or part == "node_modules" or part in {"__pycache__", ".serena", ".pytest_cache", ".mypy_cache"}
           or part.startswith(".env") or part == ".bashrc" for part in lowered):
        raise InputError(f"{field} references a protected path")
    root_real = root.resolve()
    candidate = root_real.joinpath(*parts)
    try:
        resolved = candidate.resolve(strict=must_exist)
        resolved.relative_to(root_real)
    except (OSError, RuntimeError, ValueError) as error:
        raise InputError(f"{field} resolves outside its allowed root") from error
    if _protected(resolved):
        raise InputError(f"{field} resolves to a protected path")
    if must_exist and not resolved.is_file():
        raise InputError(f"{field} does not name a readable file")
    return resolved


def emit(value: Any) -> None:
    try:
        output = json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, OverflowError) as error:
        raise InputError("result cannot be represented as JSON") from error
    print(output)


def safe_error(error: Exception) -> str:
    return str(error) if isinstance(error, InputError) else "invalid input"
