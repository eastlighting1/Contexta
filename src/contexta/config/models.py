"""Canonical configuration models for Contexta."""

from __future__ import annotations

from dataclasses import MISSING, dataclass, field, fields, is_dataclass, replace
from pathlib import Path
import types
from typing import Any, Literal, Mapping, Sequence, get_args, get_origin, get_type_hints

from ..common.errors import ConfigurationError
from ..common.io import resolve_path


ProfileName = Literal["local", "test"]
ProfileOverlayName = Literal["debug", "ci", "readonly", "forensic"]
PROFILE_NAMES = get_args(ProfileName)
PROFILE_OVERLAY_NAMES = get_args(ProfileOverlayName)


def _is_blank(value: str) -> bool:
    return not value.strip()


def _resolve_optional_path(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    return resolve_path(value)


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    raise ConfigurationError(
        f"Invalid boolean value: {value!r}",
        code="invalid_config_value",
        details={"value": value, "expected": "bool"},
    )


def _unwrap_optional(annotation: Any) -> tuple[bool, Any]:
    origin = get_origin(annotation)
    if origin in (types.UnionType, getattr(types, "UnionType", object)):
        args = get_args(annotation)
    elif origin is None and hasattr(annotation, "__args__") and type(annotation).__name__ == "_UnionGenericAlias":
        args = get_args(annotation)
    else:
        args = ()
    if not args:
        return False, annotation
    non_none = tuple(arg for arg in args if arg is not type(None))
    if len(non_none) == 1 and len(non_none) != len(args):
        return True, non_none[0]
    return False, annotation


def _coerce_literal(annotation: Any, value: Any) -> Any:
    allowed = get_args(annotation)
    if value in allowed:
        return value
    raise ConfigurationError(
        f"Invalid literal value: {value!r}",
        code="invalid_config_value",
        details={"value": value, "allowed": allowed},
    )


def _coerce_sequence(annotation: Any, value: Any) -> Any:
    origin = get_origin(annotation)
    item_type = get_args(annotation)[0] if get_args(annotation) else str

    if isinstance(value, str):
        text = value.strip()
        if text == "[]":
            items: list[Any] = []
        else:
            items = [part.strip() for part in text.split(",") if part.strip()]
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        items = list(value)
    else:
        raise ConfigurationError(
            f"Invalid sequence value: {value!r}",
            code="invalid_config_value",
            details={"value": value},
        )

    coerced = [_coerce_value(item_type, item) for item in items]
    if origin is tuple:
        return tuple(coerced)
    return coerced


def _coerce_value(annotation: Any, value: Any) -> Any:
    optional, inner = _unwrap_optional(annotation)
    if value is None:
        if optional:
            return None
        raise ConfigurationError(
            "Non-optional config field cannot be null.",
            code="invalid_config_value",
        )

    origin = get_origin(inner)
    if origin is Literal:
        return _coerce_literal(inner, value)

    if origin in (tuple, list):
        return _coerce_sequence(inner, value)

    if inner is Any:
        return value
    if inner is bool:
        return _coerce_bool(value)
    if inner is int:
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        if isinstance(value, str):
            return int(value)
        raise ConfigurationError("Invalid int value.", code="invalid_config_value")
    if inner is float:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        if isinstance(value, str):
            return float(value)
        raise ConfigurationError("Invalid float value.", code="invalid_config_value")
    if inner is str:
        if isinstance(value, str):
            return value
        raise ConfigurationError("Invalid string value.", code="invalid_config_value")
    if inner is Path:
        if isinstance(value, (str, Path)):
            return resolve_path(value)
        raise ConfigurationError("Invalid path value.", code="invalid_config_value")
    if isinstance(inner, type) and is_dataclass(inner):
        if isinstance(value, inner):
            return value
        if isinstance(value, Mapping):
            return _instantiate_dataclass(inner, value)
        raise ConfigurationError(
            f"Invalid nested config value for {inner.__name__}.",
            code="invalid_config_value",
        )
    return value


def _instantiate_dataclass(cls: type[Any], values: Mapping[str, Any]) -> Any:
    hints = get_type_hints(cls)
    field_map = {field_info.name: field_info for field_info in fields(cls)}
    unknown_keys = sorted(set(values) - set(field_map))
    if unknown_keys:
        raise ConfigurationError(
            f"Unknown config field(s) for {cls.__name__}: {', '.join(unknown_keys)}",
            code="unknown_config_field",
            details={"class": cls.__name__, "unknown_keys": unknown_keys},
        )

    kwargs: dict[str, Any] = {}
    for name, field_info in field_map.items():
        if name in values:
            kwargs[name] = _coerce_value(hints.get(name, field_info.type), values[name])
            continue
        if field_info.default is not MISSING:
            continue
        if field_info.default_factory is not MISSING:  # type: ignore[attr-defined]
            continue
        raise ConfigurationError(
            f"Missing required config field: {cls.__name__}.{name}",
            code="missing_config_field",
            details={"class": cls.__name__, "field": name},
        )
    return cls(**kwargs)


def _mappingify(value: Any) -> Any:
    if is_dataclass(value):
        return {field_info.name: _mappingify(getattr(value, field_info.name)) for field_info in fields(value)}
    if isinstance(value, tuple):
        return tuple(_mappingify(item) for item in value)
    if isinstance(value, list):
        return [_mappingify(item) for item in value]
    return value


def _config_to_patch_base(config: "UnifiedConfig") -> dict[str, Any]:
    """Convert a finalized config into a patch-friendly mapping."""

    mapping = config_to_mapping(config)

    workspace = config.workspace
    workspace_patch = mapping["workspace"]
    if workspace_patch["metadata_path"] == workspace.root_path / "metadata":
        workspace_patch["metadata_path"] = None
    if workspace_patch["records_path"] == workspace.root_path / "records":
        workspace_patch["records_path"] = None
    if workspace_patch["artifacts_path"] == workspace.root_path / "artifacts":
        workspace_patch["artifacts_path"] = None
    if workspace_patch["reports_path"] == workspace.root_path / "reports":
        workspace_patch["reports_path"] = None
    if workspace_patch["exports_path"] == workspace.root_path / "exports":
        workspace_patch["exports_path"] = None
    if workspace_patch["cache_path"] == workspace.root_path / "cache":
        workspace_patch["cache_path"] = None

    metadata_patch = mapping["metadata"]
    if metadata_patch["database_path"] == workspace.metadata_path / "ledger.db":
        metadata_patch["database_path"] = None

    records_patch = mapping["records"]
    if records_patch["root_path"] == workspace.records_path:
        records_patch["root_path"] = None

    artifacts_patch = mapping["artifacts"]
    if artifacts_patch["root_path"] == workspace.artifacts_path:
        artifacts_patch["root_path"] = None

    recovery_patch = mapping["recovery"]
    if recovery_patch["outbox_root"] == workspace.cache_path / "outbox":
        recovery_patch["outbox_root"] = None
    if recovery_patch["backup_root"] == workspace.exports_path / "backups":
        recovery_patch["backup_root"] = None
    if recovery_patch["restore_staging_root"] == workspace.cache_path / "restore":
        recovery_patch["restore_staging_root"] = None

    return mapping


def merge_config_patch(base: Mapping[str, Any], patch: Mapping[str, Any] | None) -> dict[str, Any]:
    """Deep-merge a config patch into a base mapping."""
    merged = dict(base)
    if not patch:
        return merged

    for key, value in patch.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = merge_config_patch(merged[key], value)
        else:
            merged[key] = value
    return merged


@dataclass(frozen=True, slots=True)
class WorkspaceConfig:
    """Workspace root and derived storage paths."""

    root_path: Path = Path(".contexta")
    metadata_path: Path | None = None
    records_path: Path | None = None
    artifacts_path: Path | None = None
    reports_path: Path | None = None
    exports_path: Path | None = None
    cache_path: Path | None = None
    create_missing_dirs: bool = True

    def __post_init__(self) -> None:
        root_path = resolve_path(self.root_path)
        object.__setattr__(self, "root_path", root_path)
        object.__setattr__(
            self,
            "metadata_path",
            _resolve_optional_path(self.metadata_path) or root_path / "metadata",
        )
        object.__setattr__(
            self,
            "records_path",
            _resolve_optional_path(self.records_path) or root_path / "records",
        )
        object.__setattr__(
            self,
            "artifacts_path",
            _resolve_optional_path(self.artifacts_path) or root_path / "artifacts",
        )
        object.__setattr__(
            self,
            "reports_path",
            _resolve_optional_path(self.reports_path) or root_path / "reports",
        )
        object.__setattr__(
            self,
            "exports_path",
            _resolve_optional_path(self.exports_path) or root_path / "exports",
        )
        object.__setattr__(
            self,
            "cache_path",
            _resolve_optional_path(self.cache_path) or root_path / "cache",
        )


@dataclass(frozen=True, slots=True)
class ContractConfig:
    """Canonical contract policy settings."""

    schema_version: str = "1.0.0"
    validation_mode: Literal["strict", "lenient"] = "strict"
    compatibility_mode: Literal["strict", "lenient"] = "strict"
    deterministic_serialization: bool = True


@dataclass(frozen=True, slots=True)
class CaptureConfig:
    """Capture/runtime posture settings."""

    producer_ref: str = "sdk.python.local"
    capture_environment_snapshot: bool = True
    capture_installed_packages: bool = True
    capture_code_revision: bool = True
    capture_config_snapshot: bool = True
    retry_attempts: int = 0
    retry_backoff_seconds: float = 0.0
    dispatch_failure_mode: Literal["raise", "outbox"] = "raise"
    write_degraded_marker_on_partial_failure: bool = True


@dataclass(frozen=True, slots=True)
class MetadataStoreConfig:
    """Metadata truth-plane settings."""

    storage_adapter: str = "duckdb"
    database_path: Path | None = None
    auto_create: bool = True
    read_only: bool = False
    auto_migrate: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "database_path", _resolve_optional_path(self.database_path))


@dataclass(frozen=True, slots=True)
class RecordStoreConfig:
    """Record truth-plane settings."""

    root_path: Path | None = None
    max_segment_bytes: int = 1_048_576
    durability_mode: Literal["flush", "fsync"] = "fsync"
    layout_mode: Literal["jsonl_segments"] = "jsonl_segments"
    layout_version: str = "1"
    enable_indexes: bool = True
    read_only: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "root_path", _resolve_optional_path(self.root_path))


@dataclass(frozen=True, slots=True)
class ArtifactStoreConfig:
    """Artifact truth-plane settings."""

    root_path: Path | None = None
    default_ingest_mode: Literal["copy", "move", "adopt"] = "copy"
    verification_mode: Literal["none", "stored", "manifest_if_available", "strict"] = (
        "manifest_if_available"
    )
    create_missing_dirs: bool = True
    layout_version: str = "v1"
    chunk_size_bytes: int = 1_048_576
    read_only: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "root_path", _resolve_optional_path(self.root_path))


@dataclass(frozen=True, slots=True)
class ComparisonPolicy:
    """Comparison defaults."""

    metric_selection: Literal["latest", "max", "min", "mean"] = "latest"
    include_unchanged_metrics: bool = False
    missing_stage_severity: Literal["info", "warning", "error"] = "warning"


@dataclass(frozen=True, slots=True)
class DiagnosticsPolicy:
    """Diagnostics defaults."""

    require_metrics_for_completed_stages: bool = True
    detect_degraded_records: bool = True
    expected_terminal_stage_names: tuple[str, ...] = ("evaluate", "package")


@dataclass(frozen=True, slots=True)
class ReportPolicy:
    """Report generation defaults."""

    include_completeness_notes: bool = True
    include_lineage_summary: bool = True
    include_evidence_summary: bool = True


@dataclass(frozen=True, slots=True)
class SearchPolicy:
    """Search defaults."""

    default_limit: int = 50
    text_match_fields: tuple[str, ...] = ("name", "tags", "status")
    case_sensitive: bool = False


@dataclass(frozen=True, slots=True)
class TrendPolicy:
    """Trend defaults."""

    default_window_runs: int = 20
    metric_aggregation: Literal["latest", "max", "min", "mean"] = "latest"


@dataclass(frozen=True, slots=True)
class AnomalyPolicy:
    """Anomaly defaults."""

    z_score_threshold: float = 2.5
    min_baseline_runs: int = 3
    monitored_metrics: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AlertPolicy:
    """Alert defaults."""

    stop_on_first_trigger: bool = False
    default_severity: Literal["info", "warning", "error"] = "warning"


@dataclass(frozen=True, slots=True)
class InterpretationConfig:
    """Interpretation-layer settings."""

    comparison: ComparisonPolicy = field(default_factory=ComparisonPolicy)
    diagnostics: DiagnosticsPolicy = field(default_factory=DiagnosticsPolicy)
    reports: ReportPolicy = field(default_factory=ReportPolicy)
    search: SearchPolicy = field(default_factory=SearchPolicy)
    trend: TrendPolicy = field(default_factory=TrendPolicy)
    anomaly: AnomalyPolicy = field(default_factory=AnomalyPolicy)
    alert: AlertPolicy = field(default_factory=AlertPolicy)


@dataclass(frozen=True, slots=True)
class RecoveryConfig:
    """Recovery orchestration settings."""

    outbox_root: Path | None = None
    backup_root: Path | None = None
    restore_staging_root: Path | None = None
    replay_mode_default: Literal["strict", "tolerant"] = "tolerant"
    require_plan_before_apply: bool = True
    create_backup_before_restore: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "outbox_root", _resolve_optional_path(self.outbox_root))
        object.__setattr__(self, "backup_root", _resolve_optional_path(self.backup_root))
        object.__setattr__(
            self,
            "restore_staging_root",
            _resolve_optional_path(self.restore_staging_root),
        )


@dataclass(frozen=True, slots=True)
class CLIConfig:
    """CLI delivery surface defaults."""

    default_output_format: Literal["text", "json"] = "text"
    verbosity: Literal["quiet", "normal", "debug", "forensic"] = "normal"
    color: bool = True


@dataclass(frozen=True, slots=True)
class HTTPConfig:
    """Embedded HTTP defaults."""

    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = 8765
    open_browser: bool = False


@dataclass(frozen=True, slots=True)
class HTMLConfig:
    """HTML surface defaults."""

    enabled: bool = True
    inline_charts: bool = True


@dataclass(frozen=True, slots=True)
class NotebookConfig:
    """Notebook surface defaults."""

    enabled: bool = True


@dataclass(frozen=True, slots=True)
class ExportSurfaceConfig:
    """Export surface defaults."""

    csv_delimiter: str = ","
    html_inline_charts: bool = True
    include_completeness_notes: bool = True


@dataclass(frozen=True, slots=True)
class SurfaceConfig:
    """Delivery surface settings."""

    cli: CLIConfig = field(default_factory=CLIConfig)
    http: HTTPConfig = field(default_factory=HTTPConfig)
    html: HTMLConfig = field(default_factory=HTMLConfig)
    notebook: NotebookConfig = field(default_factory=NotebookConfig)
    export: ExportSurfaceConfig = field(default_factory=ExportSurfaceConfig)


@dataclass(frozen=True, slots=True)
class RetentionConfig:
    """Retention defaults."""

    cache_ttl_days: int | None = 7
    report_ttl_days: int | None = None
    export_ttl_days: int | None = None
    artifact_retention_mode: Literal["manual", "planned", "enforced"] = "manual"
    records_compaction_enabled: bool = False


@dataclass(frozen=True, slots=True)
class SecurityConfig:
    """Security/redaction defaults."""

    redaction_mode: Literal["safe_default", "strict", "off"] = "safe_default"
    environment_variable_allowlist: tuple[str, ...] = ()
    secret_key_patterns: tuple[str, ...] = ("token", "secret", "password", "passwd", "key")
    allow_unredacted_local_exports: bool = False
    encryption_provider: str | None = None


@dataclass(frozen=True, slots=True)
class UnifiedConfig:
    """Canonical root configuration object for Contexta."""

    config_version: str = "1"
    profile_name: ProfileName = "local"
    project_name: str = "default"
    workspace: WorkspaceConfig = field(default_factory=WorkspaceConfig)
    contract: ContractConfig = field(default_factory=ContractConfig)
    capture: CaptureConfig = field(default_factory=CaptureConfig)
    metadata: MetadataStoreConfig = field(default_factory=MetadataStoreConfig)
    records: RecordStoreConfig = field(default_factory=RecordStoreConfig)
    artifacts: ArtifactStoreConfig = field(default_factory=ArtifactStoreConfig)
    interpretation: InterpretationConfig = field(default_factory=InterpretationConfig)
    recovery: RecoveryConfig = field(default_factory=RecoveryConfig)
    surfaces: SurfaceConfig = field(default_factory=SurfaceConfig)
    retention: RetentionConfig = field(default_factory=RetentionConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)

    def __post_init__(self) -> None:
        if _is_blank(self.config_version):
            raise ConfigurationError("config_version must not be blank.", code="invalid_config_value")
        if self.profile_name not in PROFILE_NAMES:
            raise ConfigurationError(
                f"Unsupported profile_name: {self.profile_name!r}",
                code="invalid_config_value",
                details={"profile_name": self.profile_name, "allowed": PROFILE_NAMES},
            )
        if _is_blank(self.profile_name):
            raise ConfigurationError("profile_name must not be blank.", code="invalid_config_value")
        if _is_blank(self.project_name):
            raise ConfigurationError("project_name must not be blank.", code="invalid_config_value")

        workspace = self.workspace

        metadata = self.metadata
        if metadata.database_path is None:
            metadata = replace(metadata, database_path=workspace.metadata_path / "ledger.db")

        records = self.records
        if records.root_path is None:
            records = replace(records, root_path=workspace.records_path)

        artifacts = self.artifacts
        if artifacts.root_path is None:
            artifacts = replace(artifacts, root_path=workspace.artifacts_path)

        recovery = self.recovery
        if recovery.outbox_root is None:
            recovery = replace(recovery, outbox_root=workspace.cache_path / "outbox")
        if recovery.backup_root is None:
            recovery = replace(recovery, backup_root=workspace.exports_path / "backups")
        if recovery.restore_staging_root is None:
            recovery = replace(recovery, restore_staging_root=workspace.cache_path / "restore")

        object.__setattr__(self, "metadata", metadata)
        object.__setattr__(self, "records", records)
        object.__setattr__(self, "artifacts", artifacts)
        object.__setattr__(self, "recovery", recovery)


def build_schema_defaults() -> UnifiedConfig:
    """Return the schema-default configuration."""
    return UnifiedConfig()


def config_to_mapping(config: UnifiedConfig) -> dict[str, Any]:
    """Convert a config object into a plain nested mapping."""
    return _mappingify(config)


def build_unified_config(patch: Mapping[str, Any] | None = None) -> UnifiedConfig:
    """Build a validated config from an optional nested patch."""
    base = _config_to_patch_base(build_schema_defaults())
    merged = merge_config_patch(base, patch)
    return _instantiate_dataclass(UnifiedConfig, merged)


def replace_unified_config(
    config: UnifiedConfig,
    patch: Mapping[str, Any] | None = None,
) -> UnifiedConfig:
    """Return a new config with a nested patch applied."""
    base = _config_to_patch_base(config)
    merged = merge_config_patch(base, patch)
    return _instantiate_dataclass(UnifiedConfig, merged)


__all__ = [
    "AlertPolicy",
    "AnomalyPolicy",
    "ArtifactStoreConfig",
    "CLIConfig",
    "CaptureConfig",
    "ComparisonPolicy",
    "ContractConfig",
    "DiagnosticsPolicy",
    "ExportSurfaceConfig",
    "HTMLConfig",
    "HTTPConfig",
    "InterpretationConfig",
    "MetadataStoreConfig",
    "NotebookConfig",
    "ProfileName",
    "ProfileOverlayName",
    "PROFILE_NAMES",
    "PROFILE_OVERLAY_NAMES",
    "RecordStoreConfig",
    "RecoveryConfig",
    "ReportPolicy",
    "RetentionConfig",
    "SearchPolicy",
    "SecurityConfig",
    "SurfaceConfig",
    "TrendPolicy",
    "UnifiedConfig",
    "WorkspaceConfig",
    "build_schema_defaults",
    "build_unified_config",
    "config_to_mapping",
    "merge_config_patch",
    "replace_unified_config",
]
