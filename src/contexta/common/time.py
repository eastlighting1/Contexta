"""Shared timestamp helpers for Contexta."""

from __future__ import annotations

from datetime import UTC, datetime


def ensure_utc(value: datetime) -> datetime:
    """Return a timezone-aware UTC datetime."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def parse_timestamp(value: str | datetime) -> datetime:
    """Parse a timestamp-like input into a UTC datetime."""
    if isinstance(value, datetime):
        return ensure_utc(value)

    text = value.strip()
    if not text:
        raise ValueError("Timestamp value must not be blank.")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return ensure_utc(datetime.fromisoformat(text))


def normalize_timestamp(value: str | datetime) -> str:
    """Return an ISO-8601 UTC timestamp with a trailing ``Z``."""
    return parse_timestamp(value).isoformat().replace("+00:00", "Z")


def utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime."""
    return datetime.now(tz=UTC)


def iso_utc_now() -> str:
    """Return the current UTC time as a normalized ISO-8601 string."""
    return normalize_timestamp(utc_now())


__all__ = [
    "ensure_utc",
    "iso_utc_now",
    "normalize_timestamp",
    "parse_timestamp",
    "utc_now",
]
