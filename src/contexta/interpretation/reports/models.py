"""Canonical report document models for interpretation outputs."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

from ...common.errors import InterpretationError
from ..query import EvidenceLink


class ReportError(InterpretationError):
    """Raised for report-specific failures."""


class ReportSerializationError(ReportError):
    """Raised when a report cannot be rendered into a target format."""


@dataclass(frozen=True, slots=True)
class ReportSection:
    title: str
    body: str
    evidence_links: tuple[EvidenceLink, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "title", self.title.strip())
        object.__setattr__(self, "body", self.body.strip())
        object.__setattr__(self, "evidence_links", tuple(self.evidence_links))

    def to_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "body": self.body,
            "evidence_links": [
                {"kind": link.kind, "ref": link.ref, "label": link.label}
                for link in self.evidence_links
            ],
        }


@dataclass(frozen=True, slots=True)
class ReportDocument:
    title: str
    sections: tuple[ReportSection, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "title", self.title.strip())
        object.__setattr__(self, "sections", tuple(self.sections))

    def to_dict(self) -> dict[str, object]:
        return self.to_json()

    def to_json(self) -> dict[str, object]:
        return {
            "title": self.title,
            "sections": [section.to_dict() for section in self.sections],
        }

    def to_markdown(self) -> str:
        lines = [f"# {self.title}"]
        for section in self.sections:
            lines.extend(("", f"## {section.title}", section.body))
            if section.evidence_links:
                lines.extend(("", "Evidence:"))
                lines.extend(f"- {link.label} ({link.kind}: {link.ref})" for link in section.evidence_links)
        return "\n".join(lines).strip()

    def to_html(self) -> str:
        parts = [
            "<article>",
            f"<h1>{escape(self.title)}</h1>",
        ]
        for section in self.sections:
            parts.append("<section>")
            parts.append(f"<h2>{escape(section.title)}</h2>")
            body = "<br/>".join(escape(line) for line in section.body.splitlines())
            parts.append(f"<p>{body}</p>")
            if section.evidence_links:
                parts.append("<ul>")
                for link in section.evidence_links:
                    parts.append(
                        f"<li>{escape(link.label)} ({escape(link.kind)}: {escape(link.ref)})</li>"
                    )
                parts.append("</ul>")
            parts.append("</section>")
        parts.append("</article>")
        return "".join(parts)

    def to_csv(self, metric_keys: tuple[str, ...] = ()) -> str:
        lines = ["section_title,body"]
        for section in self.sections:
            if metric_keys and section.title not in metric_keys:
                continue
            title = section.title.replace('"', '""')
            body = section.body.replace('"', '""')
            lines.append(f'"{title}","{body}"')
        return "\n".join(lines)


__all__ = [
    "ReportDocument",
    "ReportError",
    "ReportSection",
    "ReportSerializationError",
]
