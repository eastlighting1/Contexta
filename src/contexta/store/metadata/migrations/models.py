"""Public migration models for the metadata truth plane."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


def _freeze_notes(values: tuple[str, ...] | list[str] | None) -> tuple[str, ...]:
    if not values:
        return ()
    return tuple(str(value) for value in values)


def _freeze_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    if value is None:
        return None
    return {str(key): value[key] for key in sorted(value)}


@dataclass(frozen=True, slots=True)
class SchemaInspection:
    exists: bool
    current_version: str | None
    target_version: str
    requires_migration: bool
    supported: bool
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "notes", _freeze_notes(self.notes))


@dataclass(frozen=True, slots=True)
class MigrationStep:
    from_version: str
    to_version: str
    description: str
    step_id: str

    def __post_init__(self) -> None:
        if not self.from_version or not self.to_version or not self.step_id or not self.description:
            raise ValueError("MigrationStep requires non-empty version, step_id, and description.")


@dataclass(frozen=True, slots=True)
class MigrationPlan:
    current_version: str | None
    target_version: str
    steps: tuple[MigrationStep, ...] = ()
    requires_migration: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "steps", tuple(self.steps))
        requires_migration = bool(self.steps) or (
            self.current_version is not None and self.current_version != self.target_version
        )
        object.__setattr__(self, "requires_migration", requires_migration)


@dataclass(frozen=True, slots=True)
class MigrationHistoryRow:
    step_id: str
    from_version: str
    to_version: str
    description: str
    status: str
    applied_at: str
    notes: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.status not in {"applied", "failed"}:
            raise ValueError("MigrationHistoryRow.status must be 'applied' or 'failed'.")
        object.__setattr__(self, "notes", _freeze_mapping(self.notes))


@dataclass(frozen=True, slots=True)
class MigrationResult:
    current_version: str | None
    target_version: str
    applied_steps: tuple[MigrationStep, ...] = ()
    dry_run: bool = False
    changed: bool = False
    history_rows: tuple[MigrationHistoryRow, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "applied_steps", tuple(self.applied_steps))
        object.__setattr__(self, "history_rows", tuple(self.history_rows))
        object.__setattr__(self, "warnings", _freeze_notes(self.warnings))


__all__ = [
    "MigrationHistoryRow",
    "MigrationPlan",
    "MigrationResult",
    "MigrationStep",
    "SchemaInspection",
]
