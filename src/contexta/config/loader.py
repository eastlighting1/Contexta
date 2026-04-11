"""Profile and file-based config loading for Contexta."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import tomllib
from typing import Any, Mapping, Sequence

from ..common.errors import ConfigurationError
from ..common.io import read_text, resolve_path
from .env import EnvSelector, apply_env_overrides, read_env_selector
from .models import (
    PROFILE_NAMES,
    PROFILE_OVERLAY_NAMES,
    ProfileName,
    ProfileOverlayName,
    UnifiedConfig,
    build_unified_config,
    merge_config_patch,
    replace_unified_config,
)


OVERLAY_PRIORITY = ("readonly", "ci", "forensic", "debug")
OVERLAY_APPLICATION_ORDER = tuple(reversed(OVERLAY_PRIORITY))

PROFILE_PATCHES: dict[ProfileName, dict[str, Any]] = {
    "local": {
        "profile_name": "local",
        "workspace": {"root_path": ".contexta"},
        "capture": {
            "capture_environment_snapshot": True,
            "capture_installed_packages": True,
            "capture_code_revision": True,
            "capture_config_snapshot": True,
            "dispatch_failure_mode": "raise",
        },
        "records": {"durability_mode": "fsync"},
        "artifacts": {"verification_mode": "manifest_if_available"},
        "surfaces": {
            "http": {"enabled": False},
            "cli": {"verbosity": "normal"},
        },
        "security": {"redaction_mode": "safe_default"},
    },
    "test": {
        "profile_name": "test",
        "project_name": "test",
        "workspace": {"root_path": ".contexta-test"},
        "capture": {
            "capture_environment_snapshot": False,
            "capture_installed_packages": False,
            "capture_code_revision": False,
            "capture_config_snapshot": True,
            "retry_attempts": 0,
            "dispatch_failure_mode": "raise",
        },
        "records": {"durability_mode": "flush"},
        "artifacts": {"verification_mode": "strict"},
        "surfaces": {
            "http": {"enabled": False},
            "html": {"enabled": False},
            "notebook": {"enabled": False},
        },
        "security": {"redaction_mode": "strict"},
        "recovery": {"create_backup_before_restore": False},
    },
}

OVERLAY_PATCHES: dict[ProfileOverlayName, dict[str, Any]] = {
    "debug": {
        "surfaces": {"cli": {"verbosity": "debug"}},
        "interpretation": {
            "diagnostics": {"detect_degraded_records": True},
            "reports": {"include_evidence_summary": True},
        },
        "retention": {"cache_ttl_days": None},
    },
    "ci": {
        "surfaces": {
            "cli": {"default_output_format": "json", "color": False},
            "http": {"enabled": False},
        },
        "capture": {"retry_attempts": 0},
    },
    "readonly": {
        "metadata": {"read_only": True},
        "records": {"read_only": True},
        "artifacts": {"read_only": True},
    },
    "forensic": {
        "surfaces": {"cli": {"verbosity": "forensic"}},
        "interpretation": {
            "reports": {
                "include_lineage_summary": True,
                "include_evidence_summary": True,
            }
        },
        "retention": {
            "cache_ttl_days": None,
            "export_ttl_days": None,
        },
    },
}

SELECTOR_KEYS = {"profile", "overlays"}


@dataclass(frozen=True, slots=True)
class ProfileSelector:
    """Resolved profile selector after precedence rules are applied."""

    profile: ProfileName
    overlays: tuple[ProfileOverlayName, ...]


def _normalize_profile(name: str) -> ProfileName:
    candidate = name.strip()
    if candidate not in PROFILE_NAMES:
        raise ConfigurationError(
            f"Unsupported profile name: {name!r}",
            code="invalid_profile_selector",
            details={"value": name, "allowed": PROFILE_NAMES},
        )
    return candidate  # type: ignore[return-value]


def _normalize_overlays(overlays: Sequence[str] | None) -> tuple[ProfileOverlayName, ...]:
    if overlays is None:
        return ()

    values = [str(item).strip() for item in overlays if str(item).strip()]
    invalid = sorted(set(values) - set(PROFILE_OVERLAY_NAMES))
    if invalid:
        raise ConfigurationError(
            f"Unsupported profile overlay(s): {', '.join(invalid)}",
            code="invalid_profile_selector",
            details={"invalid": invalid, "allowed": PROFILE_OVERLAY_NAMES},
        )

    active = set(values)
    return tuple(name for name in OVERLAY_APPLICATION_ORDER if name in active)  # type: ignore[return-value]


def _load_file_mapping(config_file: str | Path | None) -> dict[str, Any]:
    if config_file is None:
        return {}

    path = resolve_path(config_file)
    if not path.exists():
        raise ConfigurationError(
            f"Config file does not exist: {path}",
            code="config_file_not_found",
            details={"config_file": str(path)},
        )

    suffix = path.suffix.lower()
    text = read_text(path)
    try:
        if suffix == ".json":
            payload = json.loads(text)
        elif suffix == ".toml":
            payload = tomllib.loads(text)
        else:
            raise ConfigurationError(
                f"Unsupported config file format: {path.name}",
                code="unsupported_config_file",
                details={"config_file": str(path), "supported": [".json", ".toml"]},
            )
    except ConfigurationError:
        raise
    except Exception as exc:  # pragma: no cover
        raise ConfigurationError(
            f"Failed to parse config file: {path}",
            code="invalid_config_file",
            details={"config_file": str(path)},
            cause=exc,
        ) from exc

    if not isinstance(payload, Mapping):
        raise ConfigurationError(
            "Config file root must be a mapping.",
            code="invalid_config_file",
            details={"config_file": str(path)},
        )
    return dict(payload)


def _read_file_selector(config_file: str | Path | None) -> EnvSelector:
    payload = _load_file_mapping(config_file)
    raw_profile = payload.get("profile")
    raw_overlays = payload.get("overlays")

    profile = None
    if raw_profile is not None:
        if not isinstance(raw_profile, str):
            raise ConfigurationError(
                "Config file selector 'profile' must be a string.",
                code="invalid_config_file",
                details={"config_file": str(resolve_path(config_file)) if config_file is not None else None},
            )
        profile = _normalize_profile(raw_profile)

    overlays = None
    if raw_overlays is not None:
        if isinstance(raw_overlays, str):
            overlays = _normalize_overlays([part.strip() for part in raw_overlays.split(",") if part.strip()])
        elif isinstance(raw_overlays, Sequence):
            overlays = _normalize_overlays([str(part) for part in raw_overlays])
        else:
            raise ConfigurationError(
                "Config file selector 'overlays' must be a string or sequence.",
                code="invalid_config_file",
                details={"config_file": str(resolve_path(config_file)) if config_file is not None else None},
            )

    return EnvSelector(profile=profile, overlays=overlays)


def _read_file_patch(config_file: str | Path | None) -> dict[str, Any]:
    payload = _load_file_mapping(config_file)
    return {key: value for key, value in payload.items() if key not in SELECTOR_KEYS}


def _resolve_selector(
    *,
    default_profile: ProfileName = "local",
    default_overlays: Sequence[ProfileOverlayName] = (),
    file_selector: EnvSelector | None = None,
    env_selector: EnvSelector | None = None,
    direct_profile: ProfileName | None = None,
    direct_overlays: Sequence[ProfileOverlayName] | None = None,
) -> ProfileSelector:
    profile = default_profile
    overlays: Sequence[ProfileOverlayName] | None = tuple(default_overlays)

    if file_selector is not None:
        if file_selector.profile is not None:
            profile = file_selector.profile
        if file_selector.overlays is not None:
            overlays = file_selector.overlays

    if env_selector is not None:
        if env_selector.profile is not None:
            profile = env_selector.profile
        if env_selector.overlays is not None:
            overlays = env_selector.overlays

    if direct_profile is not None:
        profile = direct_profile
    if direct_overlays is not None:
        overlays = direct_overlays

    return ProfileSelector(profile=profile, overlays=_normalize_overlays(overlays))


def _build_profile_config(
    profile: ProfileName,
    overlays: Sequence[ProfileOverlayName],
) -> UnifiedConfig:
    patch = PROFILE_PATCHES[profile]
    for overlay in overlays:
        patch = merge_config_patch(patch, OVERLAY_PATCHES[overlay])
    return build_unified_config(patch)


def _reject_full_config_with_resolution_inputs(
    *,
    profile: ProfileName | None,
    overlays: Sequence[ProfileOverlayName] | None,
    config_file: str | Path | None,
    workspace: str | Path | None,
    project_name: str | None,
    env: Mapping[str, str] | None,
    use_env: bool,
) -> None:
    if profile is not None:
        raise ConfigurationError("Resolved UnifiedConfig cannot be combined with profile=.", code="invalid_config_input")
    if overlays not in (None, (), []):
        raise ConfigurationError("Resolved UnifiedConfig cannot be combined with overlays=.", code="invalid_config_input")
    if config_file is not None:
        raise ConfigurationError("Resolved UnifiedConfig cannot be combined with config_file=.", code="invalid_config_input")
    if workspace is not None:
        raise ConfigurationError("Resolved UnifiedConfig cannot be combined with workspace=.", code="invalid_config_input")
    if project_name is not None:
        raise ConfigurationError("Resolved UnifiedConfig cannot be combined with project_name=.", code="invalid_config_input")
    if env is not None:
        raise ConfigurationError("Resolved UnifiedConfig cannot be combined with env=.", code="invalid_config_input")
    if use_env is not True:
        raise ConfigurationError("Resolved UnifiedConfig cannot be combined with use_env=.", code="invalid_config_input")


def load_profile(
    name: ProfileName,
    *,
    overlays: Sequence[ProfileOverlayName] = (),
    workspace: str | Path | None = None,
    project_name: str | None = None,
) -> UnifiedConfig:
    """Load a built-in profile with optional overlays and shorthand overrides."""

    resolved = _build_profile_config(_normalize_profile(name), _normalize_overlays(overlays))
    if project_name is not None:
        resolved = replace_unified_config(resolved, {"project_name": project_name})
    if workspace is not None:
        resolved = replace_unified_config(resolved, {"workspace": {"root_path": workspace}})
    return resolved


def load_config(
    *,
    profile: ProfileName | None = None,
    overlays: Sequence[ProfileOverlayName] | None = None,
    config_file: str | Path | None = None,
    config: UnifiedConfig | Mapping[str, object] | None = None,
    workspace: str | Path | None = None,
    project_name: str | None = None,
    env: Mapping[str, str] | None = None,
    use_env: bool = True,
) -> UnifiedConfig:
    """Resolve configuration from profile, file, environment, and direct patches."""

    if isinstance(config, UnifiedConfig):
        _reject_full_config_with_resolution_inputs(
            profile=profile,
            overlays=overlays,
            config_file=config_file,
            workspace=workspace,
            project_name=project_name,
            env=env,
            use_env=use_env,
        )
        return config

    file_selector = _read_file_selector(config_file) if config_file is not None else None
    env_selector = read_env_selector(env) if use_env else None
    selector = _resolve_selector(
        file_selector=file_selector,
        env_selector=env_selector,
        direct_profile=profile,
        direct_overlays=overlays,
    )

    resolved = _build_profile_config(selector.profile, selector.overlays)
    file_patch = _read_file_patch(config_file)
    if file_patch:
        resolved = replace_unified_config(resolved, file_patch)
    if use_env:
        resolved = apply_env_overrides(resolved, env=env)
    if config is not None:
        if not isinstance(config, Mapping):
            raise ConfigurationError(
                "config= must be UnifiedConfig or a mapping patch.",
                code="invalid_config_input",
            )
        resolved = replace_unified_config(resolved, config)
    if project_name is not None:
        resolved = replace_unified_config(resolved, {"project_name": project_name})
    if workspace is not None:
        resolved = replace_unified_config(resolved, {"workspace": {"root_path": workspace}})
    return resolved


__all__ = [
    "OVERLAY_APPLICATION_ORDER",
    "OVERLAY_PATCHES",
    "OVERLAY_PRIORITY",
    "PROFILE_PATCHES",
    "ProfileSelector",
    "load_config",
    "load_profile",
]
