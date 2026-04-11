"""Append-only record truth-plane package for Contexta."""

from .config import DurabilityMode, LayoutMode, RecordStoreConfig, StoreConfig
from .export import export_jsonl
from .integrity import IntegrityIssue, IntegrityReport, check_integrity
from .models import (
    AppendReceipt,
    AppendRejection,
    AppendResult,
    DurabilityStatus,
    IntegrityState,
    KnownGap,
    ReplayMode,
    ReplayResult,
    ScanFilter,
    StoredRecord,
)
from .replay import ReplayError
from .repair import RepairReport, rebuild_indexes, repair_truncated_tails
from .write import AppendError, RecordStore

__all__ = [
    "AppendError",
    "AppendReceipt",
    "AppendRejection",
    "AppendResult",
    "DurabilityMode",
    "DurabilityStatus",
    "IntegrityIssue",
    "IntegrityReport",
    "IntegrityState",
    "KnownGap",
    "LayoutMode",
    "RecordStoreConfig",
    "RepairReport",
    "ReplayError",
    "ReplayMode",
    "ReplayResult",
    "RecordStore",
    "ScanFilter",
    "StoreConfig",
    "StoredRecord",
    "check_integrity",
    "export_jsonl",
    "rebuild_indexes",
    "repair_truncated_tails",
]
