"""Shared path, file, and JSON helpers for Contexta."""

from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


def resolve_path(path: str | Path, *, base: str | Path | None = None) -> Path:
    """Resolve a path against an optional base directory."""
    raw = Path(path).expanduser()
    if raw.is_absolute():
        return raw.resolve(strict=False)

    anchor = Path(base).expanduser() if base is not None else Path.cwd()
    if not anchor.is_absolute():
        anchor = (Path.cwd() / anchor).resolve(strict=False)
    return (anchor / raw).resolve(strict=False)


def ensure_directory(path: str | Path) -> Path:
    """Create a directory and return its resolved path."""
    directory = resolve_path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def read_text(path: str | Path, *, encoding: str = "utf-8") -> str:
    """Read a text file."""
    return resolve_path(path).read_text(encoding=encoding)


def write_text(
    path: str | Path,
    text: str,
    *,
    encoding: str = "utf-8",
    ensure_parent: bool = True,
) -> Path:
    """Write a text file."""
    target = resolve_path(path)
    if ensure_parent:
        ensure_directory(target.parent)
    target.write_text(text, encoding=encoding, newline="\n")
    return target


def atomic_write_text(path: str | Path, text: str, *, encoding: str = "utf-8") -> Path:
    """Atomically write a text file using ``os.replace``."""
    target = resolve_path(path)
    ensure_directory(target.parent)
    temp_path: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding=encoding,
            dir=target.parent,
            delete=False,
            newline="\n",
        ) as handle:
            handle.write(text)
            temp_path = Path(handle.name)
        os.replace(temp_path, target)
        temp_path = None
        return target
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink(missing_ok=True)


def json_dumps(
    payload: Any,
    *,
    indent: int | None = 2,
    sort_keys: bool = True,
) -> str:
    """Serialize JSON using Contexta defaults."""
    return json.dumps(
        payload,
        ensure_ascii=False,
        indent=indent,
        sort_keys=sort_keys,
        default=str,
    )


def read_json(path: str | Path, *, encoding: str = "utf-8") -> Any:
    """Read a JSON file."""
    return json.loads(read_text(path, encoding=encoding))


def write_json(
    path: str | Path,
    payload: Any,
    *,
    encoding: str = "utf-8",
    indent: int | None = 2,
    sort_keys: bool = True,
    ensure_parent: bool = True,
) -> Path:
    """Write a JSON file."""
    text = json_dumps(payload, indent=indent, sort_keys=sort_keys) + "\n"
    return write_text(path, text, encoding=encoding, ensure_parent=ensure_parent)


def atomic_write_json(
    path: str | Path,
    payload: Any,
    *,
    encoding: str = "utf-8",
    indent: int | None = 2,
    sort_keys: bool = True,
) -> Path:
    """Atomically write a JSON file."""
    text = json_dumps(payload, indent=indent, sort_keys=sort_keys) + "\n"
    return atomic_write_text(path, text, encoding=encoding)


__all__ = [
    "atomic_write_json",
    "atomic_write_text",
    "ensure_directory",
    "json_dumps",
    "read_json",
    "read_text",
    "resolve_path",
    "write_json",
    "write_text",
]
