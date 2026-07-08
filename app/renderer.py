"""Rendering layer: compose crammed content + a brand into a self-contained HTML report.

Separation of concerns (REQ-8):
  - content templates decide *what* content/sections appear (using semantic classes only)
  - brands decide *how* it looks (design tokens injected as CSS variables) + chrome text

Autoescaping is ON, so any HTML/script that slipped into the extracted (untrusted) data is
neutralized rather than injected into the report — defense in depth alongside the crammer.
"""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from .loader import TEMPLATES_DIR, Brand, Template

# Human-friendly document label per template (falls back to a title-cased name).
DOC_KIND = {"resume": "Resume", "work_profile": "Work Profile"}


def _env(templates_dir: Path = TEMPLATES_DIR) -> Environment:
    return Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render(
    content: dict,
    sources: list,
    template: Template,
    brand: Brand,
    templates_dir: Path = TEMPLATES_DIR,
) -> str:
    """Render one report to an HTML string."""
    env = _env(templates_dir)
    tpl = env.get_template(template.template_file)
    return tpl.render(
        doc=content,
        sources=sources or [],
        brand=brand,
        doc_kind=DOC_KIND.get(template.name, template.name.replace("_", " ").title()),
    )


def render_to_file(
    content: dict,
    sources: list,
    template: Template,
    brand: Brand,
    out_path: str | Path,
    templates_dir: Path = TEMPLATES_DIR,
) -> Path:
    """Render and write the report; returns the written path."""
    html = render(content, sources, template, brand, templates_dir)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out
