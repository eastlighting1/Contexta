"""Artifact registration helpers for capture surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Mapping, Sequence

from ..common.errors import ValidationError
from ..common.io import resolve_path
from ..common.time import iso_utc_now
from ..contract import ArtifactManifest, StableRef
from ._service_utils import make_artifact_ref
from .models import ArtifactRegistrationEmission
from .results import BatchCaptureResult, CaptureResult, PayloadFamily

if TYPE_CHECKING:
    from ..config import UnifiedConfig
    from ..runtime.session import ActiveContext


def _freeze_mapping(values: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not values:
        return MappingProxyType({})
    return MappingProxyType({key: values[key] for key in sorted(values)})


def _normalize_nonblank_string(field_name: str, value: str) -> str:
    if not isinstance(value, str):
        raise ValidationError(
            f"{field_name} must be a string.",
            code="artifact_registration_invalid_value",
            details={"field_name": field_name, "type": type(value).__name__},
        )
    text = value.strip()
    if not text:
        raise ValidationError(
            f"{field_name} must not be blank.",
            code="artifact_registration_invalid_value",
            details={"field_name": field_name},
        )
    return text


def _hash_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


class ArtifactSourceKind(str, Enum):
    """Source location kind for artifact registration."""

    PATH = "PATH"
    STAGED_PATH = "STAGED_PATH"
    URI = "URI"


class ArtifactBindingStatus(str, Enum):
    """Prepared artifact binding status before store handoff."""

    BOUND = "BOUND"
    PENDING = "PENDING"
    DEGRADED = "DEGRADED"


@dataclass(frozen=True, slots=True)
class ArtifactSource:
    """Source descriptor for one artifact registration request."""

    kind: ArtifactSourceKind | str
    uri: str
    exists: bool

    def __post_init__(self) -> None:
        kind = self.kind if isinstance(self.kind, ArtifactSourceKind) else ArtifactSourceKind(_normalize_nonblank_string("kind", self.kind).upper())
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "uri", _normalize_nonblank_string("uri", self.uri))
        if not isinstance(self.exists, bool):
            raise ValueError("exists must be a bool.")

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind.value, "uri": self.uri, "exists": self.exists}


@dataclass(frozen=True, slots=True)
class ArtifactVerificationPolicy:
    """Verification policy bundled with one registration request."""

    compute_hash: bool = True
    require_existing_source: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.compute_hash, bool):
            raise ValueError("compute_hash must be a bool.")
        if not isinstance(self.require_existing_source, bool):
            raise ValueError("require_existing_source must be a bool.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "compute_hash": self.compute_hash,
            "require_existing_source": self.require_existing_source,
        }


@dataclass(frozen=True, slots=True)
class ArtifactRegistrationRequest:
    """Prepared artifact registration write request."""

    artifact_ref: StableRef | str
    artifact_kind: str
    source: ArtifactSource
    verification_policy: ArtifactVerificationPolicy
    attributes: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        ref = self.artifact_ref if isinstance(self.artifact_ref, StableRef) else StableRef.parse(self.artifact_ref)
        if ref.kind != "artifact":
            raise ValueError("artifact_ref must use kind 'artifact'.")
        object.__setattr__(self, "artifact_ref", ref)
        object.__setattr__(self, "artifact_kind", _normalize_nonblank_string("artifact_kind", self.artifact_kind))
        if not isinstance(self.source, ArtifactSource):
            raise ValueError("source must be ArtifactSource.")
        if not isinstance(self.verification_policy, ArtifactVerificationPolicy):
            raise ValueError("verification_policy must be ArtifactVerificationPolicy.")
        object.__setattr__(self, "attributes", _freeze_mapping(self.attributes))

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_ref": str(self.artifact_ref),
            "artifact_kind": self.artifact_kind,
            "source": self.source.to_dict(),
            "verification_policy": self.verification_policy.to_dict(),
            "attributes": dict(self.attributes),
        }


def prepare_artifact_registration(
    *,
    config: "UnifiedConfig",
    context: "ActiveContext",
    artifact_kind: str,
    path: str,
    artifact_ref: StableRef | str | None = None,
    attributes: Mapping[str, Any] | None = None,
    compute_hash: bool = True,
    allow_missing: bool = False,
) -> tuple[ArtifactManifest, ArtifactRegistrationRequest, ArtifactSource, ArtifactBindingStatus]:
    """Build the canonical manifest and write request for one artifact."""

    if context.run_ref is None:
        raise ValidationError(
            "Artifact registration requires an active run context.",
            code="artifact_registration_requires_run",
        )

    emission = ArtifactRegistrationEmission(
        artifact_kind=artifact_kind,
        path=path,
        artifact_ref=artifact_ref,
        attributes=attributes,
        compute_hash=compute_hash,
        allow_missing=allow_missing,
    )
    resolved_path = resolve_path(emission.path)
    exists = resolved_path.exists()
    if not exists and not emission.allow_missing:
        raise ValidationError(
            "Artifact source path does not exist.",
            code="artifact_source_missing",
            details={"path": str(resolved_path)},
        )

    source = ArtifactSource(
        kind=ArtifactSourceKind.PATH,
        uri=str(resolved_path),
        exists=exists,
    )
    verification_policy = ArtifactVerificationPolicy(
        compute_hash=emission.compute_hash,
        require_existing_source=not emission.allow_missing,
    )

    resolved_artifact_ref = emission.artifact_ref
    if resolved_artifact_ref is None:
        resolved_artifact_ref = make_artifact_ref(context.run_ref, emission.artifact_kind)
    elif isinstance(resolved_artifact_ref, str):
        resolved_artifact_ref = StableRef.parse(resolved_artifact_ref)
    if resolved_artifact_ref.kind != "artifact":
        raise ValidationError(
            "artifact_ref must use kind 'artifact'.",
            code="artifact_registration_invalid_ref",
            details={"artifact_ref": str(resolved_artifact_ref)},
        )

    hash_value: str | None = None
    size_bytes: int | None = None
    if exists and resolved_path.is_file():
        size_bytes = resolved_path.stat().st_size
        if emission.compute_hash:
            hash_value = _hash_file(resolved_path)

    manifest = ArtifactManifest(
        artifact_ref=resolved_artifact_ref,
        artifact_kind=emission.artifact_kind,
        created_at=iso_utc_now(),
        producer_ref=config.capture.producer_ref,
        run_ref=context.run_ref,
        location_ref=f"path:{resolved_path.as_posix()}",
        deployment_execution_ref=context.deployment_execution_ref,
        stage_execution_ref=context.stage_execution_ref,
        batch_execution_ref=context.batch_execution_ref,
        sample_observation_ref=context.sample_observation_ref,
        operation_context_ref=context.operation_context_ref,
        hash_value=hash_value,
        size_bytes=size_bytes,
        attributes=emission.attributes,
        schema_version=config.contract.schema_version,
    )
    request = ArtifactRegistrationRequest(
        artifact_ref=manifest.artifact_ref,
        artifact_kind=manifest.artifact_kind,
        source=source,
        verification_policy=verification_policy,
        attributes=manifest.attributes,
    )
    binding_status = ArtifactBindingStatus.BOUND if exists else ArtifactBindingStatus.PENDING
    return manifest, request, source, binding_status


def register_artifact(
    *,
    config: "UnifiedConfig",
    context: "ActiveContext",
    artifact_kind: str,
    path: str,
    artifact_ref: StableRef | str | None = None,
    attributes: Mapping[str, Any] | None = None,
    compute_hash: bool = True,
    allow_missing: bool = False,
) -> CaptureResult:
    """Prepare one artifact registration request for the active context."""

    manifest, request, source, binding_status = prepare_artifact_registration(
        config=config,
        context=context,
        artifact_kind=artifact_kind,
        path=path,
        artifact_ref=artifact_ref,
        attributes=attributes,
        compute_hash=compute_hash,
        allow_missing=allow_missing,
    )
    payload = {
        "manifest": manifest,
        "request": request,
        "source": source,
        "binding_status": binding_status.value,
    }
    metadata = {
        "service": "artifact_registration",
        "artifact_ref": str(manifest.artifact_ref),
        "dispatch_pending": True,
    }
    if binding_status is ArtifactBindingStatus.PENDING:
        return CaptureResult.with_degradation(
            PayloadFamily.ARTIFACT,
            payload=payload,
            degradation_reasons=("artifact source is missing but allow_missing=True",),
            metadata=metadata,
        )
    return CaptureResult.success(PayloadFamily.ARTIFACT, payload=payload, metadata=metadata)


def register_artifacts(
    *,
    config: "UnifiedConfig",
    context: "ActiveContext",
    emissions: Sequence[ArtifactRegistrationEmission | Mapping[str, Any]],
) -> BatchCaptureResult:
    """Prepare artifact registration requests in order and aggregate results."""

    normalized = tuple(
        item if isinstance(item, ArtifactRegistrationEmission) else ArtifactRegistrationEmission(**item)
        for item in emissions
    )
    results = []
    for emission in normalized:
        try:
            result = register_artifact(
                config=config,
                context=context,
                artifact_kind=emission.artifact_kind,
                path=emission.path,
                artifact_ref=emission.artifact_ref,
                attributes=emission.attributes,
                compute_hash=emission.compute_hash,
                allow_missing=emission.allow_missing,
            )
        except Exception as exc:
            result = CaptureResult.failure_result(PayloadFamily.ARTIFACT, exc)
        results.append(result)

    return BatchCaptureResult.from_results(
        PayloadFamily.ARTIFACT,
        tuple(results),
        metadata={"service": "artifact_registration_batch", "dispatch_pending": True},
    )


__all__ = [
    "ArtifactBindingStatus",
    "ArtifactRegistrationRequest",
    "ArtifactSource",
    "ArtifactSourceKind",
    "ArtifactVerificationPolicy",
    "prepare_artifact_registration",
    "register_artifact",
    "register_artifacts",
]
