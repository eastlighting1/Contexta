"""HTML template primitives for the embedded read surface."""

from __future__ import annotations

from html import escape


def page_shell(*, title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(title)}</title>
  <style>
    :root {{
      --bg: #f6f1e8;
      --panel: #fffaf2;
      --ink: #1f2328;
      --muted: #6b6f76;
      --accent: #0b6e4f;
      --accent-2: #d97706;
      --line: #d9d1c3;
      --shadow: rgba(31, 35, 40, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(217, 119, 6, 0.12), transparent 30%),
        linear-gradient(180deg, #fbf7f0 0%, var(--bg) 100%);
    }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 32px 20px 64px; }}
    header.page-header {{ margin-bottom: 24px; }}
    h1, h2, h3 {{ margin: 0; font-weight: 700; }}
    h1 {{ font-size: clamp(2rem, 4vw, 3.2rem); line-height: 1.05; }}
    h2 {{ font-size: 1.2rem; margin-bottom: 14px; }}
    p, li, td, th, a, span, div {{ line-height: 1.45; }}
    .subtitle {{ color: var(--muted); margin-top: 8px; }}
    .action-bar {{
      display: flex; flex-wrap: wrap; gap: 10px; margin: 18px 0 24px;
    }}
    .action-bar a {{
      color: var(--accent); text-decoration: none; border: 1px solid var(--line);
      background: var(--panel); padding: 8px 12px; border-radius: 999px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 14px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 18px;
      box-shadow: 0 8px 24px var(--shadow);
      margin-top: 18px;
    }}
    .stat {{
      background: rgba(11, 110, 79, 0.05);
      border-radius: 14px;
      padding: 12px 14px;
    }}
    .stat-label {{ color: var(--muted); font-size: 0.9rem; }}
    .stat-value {{ display: block; font-size: 1.3rem; margin-top: 4px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ text-align: left; padding: 10px 8px; vertical-align: top; }}
    thead th {{ border-bottom: 2px solid var(--line); color: var(--muted); }}
    tbody td {{ border-bottom: 1px solid rgba(217, 209, 195, 0.55); }}
    code {{ background: rgba(31, 35, 40, 0.06); padding: 1px 6px; border-radius: 8px; }}
    .note {{
      border-left: 4px solid var(--accent-2);
      background: rgba(217, 119, 6, 0.08);
      padding: 12px 14px;
      border-radius: 10px;
      margin-top: 10px;
    }}
    .empty {{ color: var(--muted); font-style: italic; }}
    .chart-wrap svg {{ width: 100%; height: auto; display: block; }}
    .muted {{ color: var(--muted); }}
    a {{ color: var(--accent); }}
  </style>
</head>
<body>
  <main>{body}</main>
</body>
</html>"""


def page_header(title: str, subtitle: str | None = None) -> str:
    subtitle_html = "" if subtitle is None else f'<p class="subtitle">{escape(subtitle)}</p>'
    return f'<header class="page-header"><h1>{escape(title)}</h1>{subtitle_html}</header>'


def action_bar(links: tuple[tuple[str, str], ...]) -> str:
    if not links:
        return ""
    rendered = "".join(
        f'<a href="{escape(href, quote=True)}">{escape(label)}</a>'
        for label, href in links
    )
    return f'<nav class="action-bar">{rendered}</nav>'


def stat_grid(items: tuple[tuple[str, str], ...], *, section_id: str | None = None, title: str | None = None) -> str:
    header = "" if title is None else f"<h2>{escape(title)}</h2>"
    stats = "".join(
        f'<div class="stat"><span class="stat-label">{escape(label)}</span><span class="stat-value">{escape(value)}</span></div>'
        for label, value in items
    )
    section_attr = "" if section_id is None else f' id="{escape(section_id, quote=True)}"'
    return f'<section{section_attr} class="card">{header}<div class="grid">{stats}</div></section>'


def table_card(
    *,
    section_id: str,
    title: str,
    headers: tuple[str, ...],
    rows: tuple[tuple[str, ...], ...],
    empty_text: str,
) -> str:
    if not rows:
        table_html = f'<p class="empty">{escape(empty_text)}</p>'
    else:
        header_html = "".join(f"<th>{escape(header)}</th>" for header in headers)
        body_html = "".join(
            "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>"
            for row in rows
        )
        table_html = f"<table><thead><tr>{header_html}</tr></thead><tbody>{body_html}</tbody></table>"
    return f'<section id="{escape(section_id, quote=True)}" class="card"><h2>{escape(title)}</h2>{table_html}</section>'


def note_block(*, section_id: str, title: str, notes: tuple[str, ...], empty_text: str = "No notes.") -> str:
    if notes:
        content = "".join(f'<div class="note">{escape(note)}</div>' for note in notes)
    else:
        content = f'<p class="empty">{escape(empty_text)}</p>'
    return f'<section id="{escape(section_id, quote=True)}" class="card"><h2>{escape(title)}</h2>{content}</section>'


def raw_section(*, section_id: str, title: str, body: str) -> str:
    return f'<section id="{escape(section_id, quote=True)}" class="card"><h2>{escape(title)}</h2>{body}</section>'


__all__ = [
    "action_bar",
    "note_block",
    "page_header",
    "page_shell",
    "raw_section",
    "stat_grid",
    "table_card",
]
