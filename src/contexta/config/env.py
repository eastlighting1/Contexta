"""Environment selector and override handling for Contexta config."""

from __future__ import annotations

import os
from dataclasses import fields, is_dataclass
import types
from typing import Any, Mapping, NamedTuple, get_args, get_origin, get_type_hints

from ..common.errors import ConfigurationError
from .models import (
    PROFILE_NAMES,
    PROFILE_OVERLAY_NAMES,
    ProfileName,
    ProfileOverlayName,
    UnifiedConfig,
    _coerce_value,
    replace_unified_config,
)


CANONICAL_ENV_PREFIX = "CONTEXTA_"
PROFILE_ENV_KEY = f"{CANONICAL_ENV_PREFIX}PROFILE"
PROFILE_OVERLAYS_ENV_KEY = f"{CANONICAL_ENV_PREFIX}PROFILE_OVERLAYS"
NON_OVERRIDABLE_ENV_KEYS = {
    f"{CANONICAL_ENV_PREFIX}CONFIG_VERSION",
    f"{CANONICAL_ENV_PREFIX}PROFILE_NAME",
}


class EnvSelector(NamedTuple):
    """Ambient profile selector extracted from environment variables."""

    profile: ProfileName | None
    overlays: tuple[ProfileOverlayName, ...] | None


class EnvFieldSpec(NamedTuple):
    """A single canonical environment field mapping."""

    path: tuple[str, ...]
    annotation: Any


def _normalize_env(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return dict(os.environ) if env is None else dict(env)


def _is_blank(raw: str | None) -> bool:
    return raw is None or not raw.strip()


def _unwrap_optional(annotation: Any) -> tuple[bool, Any]:
    origin = get_origin(annotation)
    if origin in (types.UnionType, getattr(types, "UnionType", object)):
        args = get_args(annotation)
    else:
        args = get_args(annotation) if origin is not None else ()
    if not args:
        return False, annotation
    non_none = tuple(arg for arg in args if arg is not type(None))
    if len(non_none) == 1 and len(non_none) != len(args):
        return True, non_none[0]
    return False, annotation


def _field_env_key(path: tuple[str, ...]) -> str:
    return f"{CANONICAL_ENV_PREFIX}{'_'.join(part.upper() for part in path)}"


def _collect_field_specs(
    cls: type[Any],
    *,
    prefix: tuple[str, ...] = (),
) -> dict[str, EnvFieldSpec]:
    hints = get_type_hints(cls)
    specs: dict[str, EnvFieldSpec] = {}
    for field_info in fields(cls):
        path = prefix + (field_info.name,)
        annotation = hints.get(field_info.name, field_info.type)
        _, inner = _unwrap_optional(annotation)
        if isinstance(inner, type) and is_dataclass(inner):
            specs.update(_collect_field_specs(inner, prefix=path))
            continue
        if path in {("config_version",), ("profile_name",)}:
            continue
        specs[_field_env_key(path)] = EnvFieldSpec(path=path, annotation=annotation)
    return specs


ENV_FIELD_SPECS = _collect_field_specs(UnifiedConfig)


def _normalize_profile(value: str, *, source: str) -> ProfileName:
    candidate = value.strip()
    if candidate not in PROFILE_NAMES:
        raise ConfigurationError(
            f"Unsupported profile selector from {source}: {value!r}",
            code="invalid_profile_selector",
            details={"source": source, "value": value, "allowed": PROFILE_NAMES},
        )
    return candidate  # type: ignore[return-value]


def _normalize_overlay_list(
    value: str | list[str] | tuple[str, ...],
    *,
    source: str,
) -> tuple[ProfileOverlayName, ...]:
    if isinstance(value, str):
        items = [part.strip() for part in value.split(",") if part.strip()]
    else:
        items = [str(part).strip() for part in value if str(part).strip()]

    invalid = sorted(set(items) - set(PROFILE_OVERLAY_NAMES))
    if invalid:
        raise ConfigurationError(
            f"Unsupported profile overlay selector from {source}: {', '.join(invalid)}",
            code="invalid_profile_selector",
            details={"source": source, "invalid": invalid, "allowed": PROFILE_OVERLAY_NAMES},
        )
    return tuple(items)  # type: ignore[return-value]


def _set_nested_value(target: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    cursor = target
    for key in path[:-1]:
        cursor = cursor.setdefault(key, {})
    cursor[path[-1]] = value


def _parse_env_value(annotation: Any, raw: str, *, env_key: str) -> Any:
    text = raw.strip()
    optional, _ = _unwrap_optional(annotation)
    lowered = text.lower()

    if lowered in {"null", "none"}:
        if optional:
            return None
        raise ConfigurationError(
            f"{env_key} cannot be cleared with null/none.",
            code="invalid_config_value",
            details={"env_key": env_key, "value": raw},
        )

    try:
        return _coerce_value(annotation, text)
    except Exception as exc:  # pragma: no cover
        if isinstance(exc, ConfigurationError):
            raise ConfigurationError(
                f"Failed to parse {env_key}.",
                code=exc.code,
                details={"env_key": env_key, "value": raw, "cause": exc.message},
                cause=exc,
            ) from exc
        raise


def _collect_canonical_env_values(
    env: Mapping[str, str],
) -> dict[str, str]:
    canonical: dict[str, str] = {}

    for key, value in env.items():
        if not key.startswith(CANONICAL_ENV_PREFIX):
            continue
        if key in NON_OVERRIDABLE_ENV_KEYS:
            raise ConfigurationError(
                f"{key} is not overridable via environment variables.",
                code="non_overridable_config_key",
                details={"env_key": key},
            )
        if key not in {PROFILE_ENV_KEY, PROFILE_OVERLAYS_ENV_KEY} and key not in ENV_FIELD_SPECS:
            raise ConfigurationError(
                f"Unknown Contexta environment key: {key}",
                code="unknown_config_field",
                details={"env_key": key},
            )
        canonical[key] = value

    return canonical


def read_env_selector(env: Mapping[str, str] | None = None) -> EnvSelector:
    """Read profile selector fields from the ambient environment."""

    source = _normalize_env(env)
    profile_value = source.get(PROFILE_ENV_KEY)
    overlays_value = source.get(PROFILE_OVERLAYS_ENV_KEY)

    profile = None if _is_blank(profile_value) else _normalize_profile(profile_value, source=PROFILE_ENV_KEY)
    overlays = None if _is_blank(overlays_value) else _normalize_overlay_list(overlays_value, source=PROFILE_OVERLAYS_ENV_KEY)
    return EnvSelector(profile=profile, overlays=overlays)


def read_env_patch(
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Convert canonical environment variables into a nested config patch."""

    source = _normalize_env(env)
    canonical_values = _collect_canonical_env_values(source)
    patch: dict[str, Any] = {}

    for env_key, raw_value in canonical_values.items():
        if env_key in {PROFILE_ENV_KEY, PROFILE_OVERLAYS_ENV_KEY}:
            continue
        if _is_blank(raw_value):
            continue
        spec = ENV_FIELD_SPECS[env_key]
        parsed = _parse_env_value(spec.annotation, raw_value, env_key=env_key)
        _set_nested_value(patch, spec.path, parsed)

    return patch


def apply_env_overrides(
    config: UnifiedConfig,
    *,
    env: Mapping[str, str] | None = None,
) -> UnifiedConfig:
    """Apply canonical environment overrides to a config object."""

    patch = read_env_patch(env)
    if not patch:
        return config
    return replace_unified_config(config, patch)


__all__ = [
    "CANONICAL_ENV_PREFIX",
    "EnvSelector",
    "NON_OVERRIDABLE_ENV_KEYS",
    "PROFILE_ENV_KEY",
    "PROFILE_OVERLAYS_ENV_KEY",
    "apply_env_overrides",
    "read_env_patch",
    "read_env_selector",
]
