"""Convenience bootstrap helpers for Contexta config profiles."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

from .loader import load_config
from .models import ProfileOverlayName, UnifiedConfig


def make_local_config(
    *,
    overlays: Sequence[ProfileOverlayName] | None = None,
    config_file: str | Path | None = None,
    config: UnifiedConfig | Mapping[str, object] | None = None,
    workspace: str | Path | None = None,
    project_name: str | None = None,
    env: Mapping[str, str] | None = None,
    use_env: bool = True,
) -> UnifiedConfig:
    """Build a validated config using the ``local`` base profile."""

    return load_config(
        profile="local",
        overlays=overlays,
        config_file=config_file,
        config=config,
        workspace=workspace,
        project_name=project_name,
        env=env,
        use_env=use_env,
    )


def make_test_config(
    *,
    overlays: Sequence[ProfileOverlayName] | None = None,
    config_file: str | Path | None = None,
    config: UnifiedConfig | Mapping[str, object] | None = None,
    workspace: str | Path | None = None,
    project_name: str | None = None,
    env: Mapping[str, str] | None = None,
    use_env: bool = False,
) -> UnifiedConfig:
    """Build a validated config using the ``test`` base profile."""

    return load_config(
        profile="test",
        overlays=overlays,
        config_file=config_file,
        config=config,
        workspace=workspace,
        project_name=project_name,
        env=env,
        use_env=use_env,
    )


__all__ = [
    "make_local_config",
    "make_test_config",
]
