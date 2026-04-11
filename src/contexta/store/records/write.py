"""Append-oriented record store implementation."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from ...common.errors import ReadOnlyStoreError, RecordError, SerializationError, ValidationError
from ...common.io import atomic_write_json, ensure_directory, read_json, resolve_path
from ...common.time import iso_utc_now
from ...contract import (
    DegradedRecord,
    MetricRecord,
    StructuredEventRecord,
    TraceSpanRecord,
    to_payload,
    validate_degraded_record,
    validate_metric_record,
    validate_structured_event_record,
    validate_trace_span_record,
)
from .config import DurabilityMode, LayoutMode, StoreConfig
from .models import (
    AppendReceipt,
    AppendRejection,
    AppendResult,
    CanonicalRecord,
    DurabilityStatus,
)


_INDEX_SAFE_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True, slots=True)
class _RecordManifest:
    layout_mode: str
    layout_version: str
    current_segment_id: int
    next_sequence: int
    last_committed_sequence: int
    current_segment_record_count: int

    @classmethod
    def bootstrap(cls, config: StoreConfig) -> "_RecordManifest":
        return cls(
            layout_mode=config.layout_mode.value,
            layout_version=config.layout_version,
            current_segment_id=1,
            next_sequence=1,
            last_committed_sequence=0,
            current_segment_record_count=0,
        )

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "_RecordManifest":
        return cls(
            layout_mode=str(payload["layout_mode"]),
            layout_version=str(payload["layout_version"]),
            current_segment_id=int(payload["current_segment_id"]),
            next_sequence=int(payload["next_sequence"]),
            last_committed_sequence=int(payload["last_committed_sequence"]),
            current_segment_record_count=int(payload["current_segment_record_count"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "layout_mode": self.layout_mode,
            "layout_version": self.layout_version,
            "current_segment_id": self.current_segment_id,
            "next_sequence": self.next_sequence,
            "last_committed_sequence": self.last_committed_sequence,
            "current_segment_record_count": self.current_segment_record_count,
        }


class AppendError(RecordError):
    """Raised when record truth append fails after store mutation begins."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "record_append_error",
        partial_result: AppendResult | None = None,
        details: dict[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message, code=code, details=details, cause=cause)
        self.partial_result = partial_result


class RecordStore:
    """Filesystem-backed append-only record store."""

    def __init__(self, config: StoreConfig | None = None) -> None:
        self.config = config or StoreConfig()
        if self.config.root_path is None:
            raise ValidationError(
                "RecordStore requires a concrete root_path.",
                code="record_store_missing_root_path",
            )
        self.root_path = resolve_path(self.config.root_path)
        self._bootstrap()

    def append(self, record: object) -> AppendResult:
        return self.append_many((record,))

    def append_many(self, records: list[object] | tuple[object, ...]) -> AppendResult:
        manifest = self._load_manifest()
        accepted: list[AppendReceipt] = []
        rejected: list[AppendRejection] = []
        for index, item in enumerate(records):
            try:
                record = self._coerce_record(item)
                self._validate_record(record)
            except ValidationError as exc:
                rejected.append(self._build_rejection(index=index, item=item, error=exc))
                continue
            except SerializationError as exc:
                rejected.append(self._build_rejection(index=index, item=item, error=exc, code="serialization_error"))
                continue

            try:
                manifest, receipt = self._append_validated_record(record=record, manifest=manifest)
            except AppendError as exc:
                partial = exc.partial_result or self._build_result(accepted=accepted, rejected=rejected)
                raise AppendError(
                    exc.message,
                    code=exc.code,
                    partial_result=partial,
                    details=dict(exc.details) if exc.details is not None else None,
                    cause=exc.cause,
                ) from exc
            accepted.append(receipt)
        return self._build_result(accepted=accepted, rejected=rejected)

    def scan(self, scan_filter: Any | None = None) -> Iterator[Any]:
        from .read import scan_records

        return scan_records(self, scan_filter)

    def replay(self, scan_filter: Any | None = None, *, mode: Any = None) -> Any:
        from .replay import replay_records
        from .models import ReplayMode

        return replay_records(self, scan_filter, mode=ReplayMode.STRICT if mode is None else mode)

    def iter_replay(self, scan_filter: Any | None = None, *, mode: Any = None) -> Iterator[Any]:
        from .replay import iter_replay_records
        from .models import ReplayMode

        return iter_replay_records(self, scan_filter, mode=ReplayMode.STRICT if mode is None else mode)

    def export_jsonl(self, destination: str | Path, scan_filter: Any | None = None, *, mode: Any = None) -> Any:
        from .export import export_jsonl
        from .models import ReplayMode

        return export_jsonl(self, destination, scan_filter, mode=ReplayMode.STRICT if mode is None else mode)

    def check_integrity(self) -> Any:
        from .integrity import check_integrity

        return check_integrity(self)

    def rebuild_indexes(self) -> Any:
        from .repair import rebuild_indexes

        return rebuild_indexes(self)

    def repair_truncated_tails(self) -> Any:
        from .repair import repair_truncated_tails

        return repair_truncated_tails(self)

    def __enter__(self) -> "RecordStore":
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: Any) -> bool:
        return False

    def _bootstrap(self) -> None:
        if self.config.read_only:
            if not self.root_path.exists():
                raise ReadOnlyStoreError(
                    "Record store root does not exist in read-only mode.",
                    code="record_store_missing_root",
                    details={"root_path": str(self.root_path)},
                )
            return
        ensure_directory(self.root_path)
        ensure_directory(self._segments_dir())
        ensure_directory(self._indexes_dir())
        ensure_directory(self._cursors_dir())
        ensure_directory(self._quarantine_dir())
        if not self._manifest_path().exists():
            self._write_manifest(_RecordManifest.bootstrap(self.config))

    def _load_manifest(self) -> _RecordManifest:
        path = self._manifest_path()
        if not path.exists():
            if self.config.read_only:
                raise ReadOnlyStoreError(
                    "Record manifest is missing in read-only mode.",
                    code="record_store_manifest_missing",
                    details={"manifest_path": str(path)},
                )
            manifest = _RecordManifest.bootstrap(self.config)
            self._write_manifest(manifest)
            return manifest
        payload = read_json(path)
        manifest = _RecordManifest.from_mapping(payload)
        if manifest.layout_mode != self.config.layout_mode.value:
            raise AppendError(
                "Record store layout_mode does not match the configured layout.",
                code="record_store_layout_mode_mismatch",
                details={"manifest_layout_mode": manifest.layout_mode, "configured_layout_mode": self.config.layout_mode.value},
            )
        if manifest.layout_version != self.config.layout_version:
            raise AppendError(
                "Record store layout_version does not match the configured layout.",
                code="record_store_layout_version_mismatch",
                details={"manifest_layout_version": manifest.layout_version, "configured_layout_version": self.config.layout_version},
            )
        return manifest

    def _write_manifest(self, manifest: _RecordManifest) -> None:
        atomic_write_json(self._manifest_path(), manifest.to_dict(), indent=2, sort_keys=True)

    def _append_validated_record(self, *, record: CanonicalRecord, manifest: _RecordManifest) -> tuple[_RecordManifest, AppendReceipt]:
        if self.config.read_only:
            raise ReadOnlyStoreError("Record store is read-only.", code="record_store_read_only")

        appended_at = iso_utc_now()
        sequence = manifest.next_sequence
        segment_id = manifest.current_segment_id
        offset = manifest.current_segment_record_count + 1
        segment_path = self._segment_path(segment_id)
        payload = {
            "sequence": sequence,
            "appended_at": appended_at,
            "record": to_payload(record),
        }
        line = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        durability_status = DurabilityStatus.ACCEPTED
        try:
            ensure_directory(segment_path.parent)
            with segment_path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(line)
                if self.config.durability_mode is DurabilityMode.FLUSH:
                    handle.flush()
                    durability_status = DurabilityStatus.FLUSHED
                elif self.config.durability_mode is DurabilityMode.FSYNC:
                    handle.flush()
                    os.fsync(handle.fileno())
                    durability_status = DurabilityStatus.FSYNCED
        except Exception as exc:
            raise AppendError(
                "Failed to append record to the active segment.",
                code="record_store_segment_append_failed",
                details={"segment_path": str(segment_path), "sequence": sequence},
                cause=exc,
            ) from exc

        updated_manifest = _RecordManifest(
            layout_mode=manifest.layout_mode,
            layout_version=manifest.layout_version,
            current_segment_id=segment_id,
            next_sequence=sequence + 1,
            last_committed_sequence=sequence,
            current_segment_record_count=offset,
        )
        try:
            self._write_manifest(updated_manifest)
        except Exception as exc:
            partial = AppendResult(
                accepted=(
                    AppendReceipt(
                        sequence=sequence,
                        segment_id=segment_id,
                        offset=offset,
                        record_ref=str(record.envelope.record_ref),
                        record_type=record.envelope.record_type,
                        run_ref=str(record.envelope.run_ref),
                        durability_status=durability_status,
                    ),
                ),
                rejected=(),
                durability_status=durability_status,
                durable_count=1 if durability_status is not DurabilityStatus.ACCEPTED else 0,
            )
            raise AppendError(
                "Failed to persist the record manifest after append.",
                code="record_store_manifest_write_failed",
                partial_result=partial,
                details={"manifest_path": str(self._manifest_path()), "sequence": sequence},
                cause=exc,
            ) from exc

        receipt = AppendReceipt(
            sequence=sequence,
            segment_id=segment_id,
            offset=offset,
            record_ref=str(record.envelope.record_ref),
            record_type=record.envelope.record_type,
            run_ref=str(record.envelope.run_ref),
            durability_status=durability_status,
        )
        if self.config.enable_indexes:
            try:
                self._write_index_entries(receipt=receipt, record=record)
            except Exception as exc:
                partial = AppendResult(
                    accepted=(receipt,),
                    rejected=(),
                    durability_status=durability_status,
                    durable_count=1 if durability_status is not DurabilityStatus.ACCEPTED else 0,
                )
                raise AppendError(
                    "Record truth was appended but derived index write failed.",
                    code="record_store_index_write_failed",
                    partial_result=partial,
                    details={"record_ref": receipt.record_ref, "sequence": receipt.sequence},
                    cause=exc,
                ) from exc
        return updated_manifest, receipt

    def _coerce_record(self, item: object) -> CanonicalRecord:
        if isinstance(item, (StructuredEventRecord, MetricRecord, TraceSpanRecord, DegradedRecord)):
            return item
        raise ValidationError(
            "RecordStore only accepts canonical record objects at this stage.",
            code="unsupported_record_type",
            details={"type": type(item).__name__},
        )

    def _validate_record(self, record: CanonicalRecord) -> None:
        if isinstance(record, StructuredEventRecord):
            validate_structured_event_record(record).raise_for_errors()
            return
        if isinstance(record, MetricRecord):
            validate_metric_record(record).raise_for_errors()
            return
        if isinstance(record, TraceSpanRecord):
            validate_trace_span_record(record).raise_for_errors()
            return
        if isinstance(record, DegradedRecord):
            validate_degraded_record(record).raise_for_errors()
            return
        raise ValidationError(
            "Unsupported record family.",
            code="unsupported_record_type",
            details={"type": type(record).__name__},
        )

    def _build_rejection(
        self,
        *,
        index: int,
        item: object,
        error: BaseException,
        code: str | None = None,
    ) -> AppendRejection:
        record_ref = None
        record_type = None
        envelope = getattr(item, "envelope", None)
        if envelope is not None:
            record_ref = getattr(envelope, "record_ref", None)
            record_type = getattr(envelope, "record_type", None)
        rejection_code = code
        if rejection_code is None:
            rejection_code = getattr(error, "code", None) or "validation_error"
        return AppendRejection(
            index=index,
            code=str(rejection_code),
            message=str(error) or type(error).__name__,
            record_ref=None if record_ref is None else str(record_ref),
            record_type=None if record_type is None else str(record_type),
        )

    def _build_result(
        self,
        *,
        accepted: list[AppendReceipt],
        rejected: list[AppendRejection],
    ) -> AppendResult:
        durability_status = self._aggregate_durability(tuple(accepted))
        durable_count = sum(receipt.durability_status is not DurabilityStatus.ACCEPTED for receipt in accepted)
        return AppendResult(
            accepted=tuple(accepted),
            rejected=tuple(rejected),
            durability_status=durability_status,
            durable_count=durable_count,
        )

    def _aggregate_durability(self, accepted: tuple[AppendReceipt, ...]) -> DurabilityStatus:
        if not accepted:
            return DurabilityStatus.ACCEPTED
        order = {
            DurabilityStatus.ACCEPTED: 0,
            DurabilityStatus.FLUSHED: 1,
            DurabilityStatus.FSYNCED: 2,
        }
        return min((receipt.durability_status for receipt in accepted), key=lambda item: order[item])

    def _write_index_entries(self, *, receipt: AppendReceipt, record: CanonicalRecord) -> None:
        pointer = json.dumps(
            {"sequence": receipt.sequence, "segment_id": receipt.segment_id, "offset": receipt.offset},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ) + "\n"
        targets = [
            self._index_file_path("run_ref", str(record.envelope.run_ref)),
            self._index_file_path("record_type", record.envelope.record_type),
        ]
        if record.envelope.stage_execution_ref is not None:
            targets.append(self._index_file_path("stage_execution_ref", str(record.envelope.stage_execution_ref)))
        if record.envelope.batch_execution_ref is not None:
            targets.append(self._index_file_path("batch_execution_ref", str(record.envelope.batch_execution_ref)))
        if record.envelope.sample_observation_ref is not None:
            targets.append(self._index_file_path("sample_observation_ref", str(record.envelope.sample_observation_ref)))
        for target in targets:
            ensure_directory(target.parent)
            with target.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(pointer)

    def _index_file_path(self, family: str, key: str) -> Path:
        safe_key = _INDEX_SAFE_PATTERN.sub("_", key.replace(":", "__"))
        return self._indexes_dir() / family / f"{safe_key}.jsonl"

    def _manifest_path(self) -> Path:
        return self.root_path / "manifest.json"

    def _segments_dir(self) -> Path:
        return self.root_path / "segments"

    def _indexes_dir(self) -> Path:
        return self.root_path / "indexes"

    def _cursors_dir(self) -> Path:
        return self.root_path / "cursors" / "replay"

    def _quarantine_dir(self) -> Path:
        return self.root_path / "quarantine"

    def _segment_path(self, segment_id: int) -> Path:
        return self._segments_dir() / f"segment-{segment_id:06d}.jsonl"


__all__ = ["AppendError", "RecordStore"]
