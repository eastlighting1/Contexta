"""Validation report models for Contexta contract validators."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from ...common.errors import ValidationError


VALIDATION_SEVERITIES = ("error", "warning")


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """One validation issue emitted by a contract validator."""

    code: str
    path: str
    message: str
    severity: str = "error"

    def __post_init__(self) -> None:
        code = self.code.strip() if isinstance(self.code, str) else ""
        path = self.path.strip() if isinstance(self.path, str) else ""
        message = self.message.strip() if isinstance(self.message, str) else ""
        severity = self.severity.strip() if isinstance(self.severity, str) else ""

        if not code:
            raise ValidationError("ValidationIssue.code must not be blank.", code="validation_issue_invalid_code")
        if not path:
            raise ValidationError("ValidationIssue.path must not be blank.", code="validation_issue_invalid_path")
        if not message:
            raise ValidationError(
                "ValidationIssue.message must not be blank.",
                code="validation_issue_invalid_message",
            )
        if severity not in VALIDATION_SEVERITIES:
            raise ValidationError(
                "ValidationIssue.severity must be one of the canonical values.",
                code="validation_issue_invalid_severity",
                details={"severity": severity, "allowed": VALIDATION_SEVERITIES},
            )

        object.__setattr__(self, "code", code)
        object.__setattr__(self, "path", path)
        object.__setattr__(self, "message", message)
        object.__setattr__(self, "severity", severity)

    @property
    def is_error(self) -> bool:
        return self.severity == "error"

    def with_prefix(self, prefix: str) -> "ValidationIssue":
        """Return a copy with a path prefix applied."""

        normalized = prefix.strip()
        if not normalized or normalized == "$":
            return self
        if self.path == "$":
            path = normalized
        elif self.path.startswith("$."):
            path = f"{normalized}{self.path[1:]}"
        else:
            path = f"{normalized}.{self.path}"
        return ValidationIssue(code=self.code, path=path, message=self.message, severity=self.severity)

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "path": self.path,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """Aggregate validation result for one object."""

    valid: bool
    issues: tuple[ValidationIssue, ...] = ()

    def __post_init__(self) -> None:
        normalized = tuple(self.issues)
        for issue in normalized:
            if not isinstance(issue, ValidationIssue):
                raise ValidationError(
                    "ValidationReport.issues must contain ValidationIssue objects.",
                    code="validation_report_invalid_issue",
                    details={"type": type(issue).__name__},
                )
        computed_valid = not any(issue.is_error for issue in normalized)
        object.__setattr__(self, "issues", normalized)
        object.__setattr__(self, "valid", computed_valid)

    @property
    def errors(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.is_error)

    @property
    def warnings(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.issues if not issue.is_error)

    @classmethod
    def ok(cls) -> "ValidationReport":
        return cls(valid=True, issues=())

    @classmethod
    def from_issues(cls, issues: Sequence[ValidationIssue]) -> "ValidationReport":
        return cls(valid=True, issues=tuple(issues))

    @classmethod
    def merge(cls, *reports: "ValidationReport") -> "ValidationReport":
        issues: list[ValidationIssue] = []
        for report in reports:
            if not isinstance(report, ValidationReport):
                raise ValidationError(
                    "ValidationReport.merge expects ValidationReport objects.",
                    code="validation_report_invalid_merge",
                    details={"type": type(report).__name__},
                )
            issues.extend(report.issues)
        return cls.from_issues(issues)

    def prefixed(self, prefix: str) -> "ValidationReport":
        return ValidationReport.from_issues(tuple(issue.with_prefix(prefix) for issue in self.issues))

    def raise_for_errors(self) -> None:
        if self.valid:
            return
        raise ValidationError(
            "Validation failed.",
            code="validation_failed",
            details={"issues": [issue.to_dict() for issue in self.errors]},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "issues": [issue.to_dict() for issue in self.issues],
        }


__all__ = [
    "VALIDATION_SEVERITIES",
    "ValidationIssue",
    "ValidationReport",
]
