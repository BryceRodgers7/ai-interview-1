"""Asset loading for raw data, templates, and brands (REQ-1, REQ-2, REQ-3).

These are the three independent, composable asset types (Goal G1). Everything is
plain files on disk so the assets can be managed without touching code:
  - raw JSON      -> data/raw/*.json          (arbitrary, unstructured)
  - templates     -> content_templates/<name>/{schema.json, template.html.j2, guidance.md}
  - brands        -> brands/<id>.json

Loader functions accept optional directory overrides so tests can point them at
fixtures (see tests/).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
TEMPLATES_DIR = ROOT / "content_templates"
BRANDS_DIR = ROOT / "brands"


@dataclass
class RawInput:
    """A whole raw file treated as one source document. `text` is passed verbatim to the
    model as untrusted source; `data` is the parsed JSON (used only for validation)."""
    name: str
    text: str
    data: object


@dataclass
class RawRecord:
    """One person record extracted from a raw source (REQ-11). A collection file yields
    many of these. `text` (the serialized record) is the untrusted source for the cram."""
    id: str
    text: str
    data: dict
    source: str  # source file path
    index: int   # position within the source


@dataclass
class IngestIssue:
    """A record/line that could not be ingested cleanly (REQ-12). Reported, not fatal."""
    source: str
    location: str  # e.g. "line 4" or "people[7]"
    reason: str


# Keys we recognize as a record's identifier, in priority order.
COMMON_ID_KEYS = ("personId", "id", "employeeId", "recordId", "uid")


@dataclass
class Template:
    """A content template: the field `schema` the AI must fill, the extraction
    `guidance`, and the Jinja `template_file` that renders the filled content."""
    name: str
    schema: dict
    guidance: str
    template_file: str  # path relative to TEMPLATES_DIR, for the Jinja loader
    directory: Path


@dataclass
class Brand:
    """A presentation format: visual design tokens plus chrome text (REQ-3)."""
    id: str
    data: dict

    @property
    def name(self) -> str:
        return self.data.get("name", self.id)

    @property
    def tokens(self) -> dict:
        return self.data.get("tokens", {})

    @property
    def tagline(self) -> str:
        return self.data.get("tagline", "")

    @property
    def logo_text(self) -> str:
        return self.data.get("logo_text", self.name)

    @property
    def footer_text(self) -> str:
        return self.data.get("footer_text", "")


def _normalize_template_name(name: str) -> str:
    """Accept either `work-profile` or `work_profile`; directories use underscores."""
    return name.strip().replace("-", "_")


# --- listing -------------------------------------------------------------------
# Directory args default to None and resolve the module-level globals at call time,
# so tests (and the CLI) can redirect asset locations by monkeypatching the globals.

def list_raw(raw_dir: Path | None = None) -> list[str]:
    """List raw source files (recursively), both .json and .ndjson, as paths relative
    to the raw dir. Recurses because collections may live in per-format subfolders."""
    raw_dir = Path(raw_dir) if raw_dir else RAW_DIR
    if not raw_dir.exists():
        return []
    files = list(raw_dir.rglob("*.json")) + list(raw_dir.rglob("*.ndjson"))
    return sorted(str(f.relative_to(raw_dir)).replace("\\", "/") for f in files)


def list_templates(templates_dir: Path | None = None) -> list[str]:
    templates_dir = Path(templates_dir) if templates_dir else TEMPLATES_DIR
    if not templates_dir.exists():
        return []
    return sorted(
        p.name for p in templates_dir.iterdir()
        if p.is_dir() and (p / "schema.json").is_file()
    )


def list_brands(brands_dir: Path | None = None) -> list[str]:
    brands_dir = Path(brands_dir) if brands_dir else BRANDS_DIR
    if not brands_dir.exists():
        return []
    return sorted(p.stem for p in brands_dir.glob("*.json"))


# --- loading -------------------------------------------------------------------

def _resolve_raw_path(name_or_path: str | Path, raw_dir: Path) -> Path:
    """Resolve a raw source by absolute/relative path, or by name within `raw_dir`
    (searched recursively; .json/.ndjson suffix optional)."""
    p = Path(name_or_path)
    if p.is_file():
        return p
    # Try as a path relative to raw_dir, then as a bare name searched recursively.
    candidate = raw_dir / name_or_path
    if candidate.is_file():
        return candidate
    for suffix in ("", ".json", ".ndjson"):
        c = raw_dir / f"{name_or_path}{suffix}"
        if c.is_file():
            return c
    matches = [
        f for f in list(raw_dir.rglob("*.json")) + list(raw_dir.rglob("*.ndjson"))
        if f.stem == Path(name_or_path).stem or f.name == Path(name_or_path).name
    ]
    if matches:
        return matches[0]
    raise FileNotFoundError(f"Raw data file not found: {name_or_path}")


def load_raw(name_or_path: str | Path, raw_dir: Path | None = None) -> RawInput:
    """Load a whole raw file as a single source document (legacy one-file-one-doc path)."""
    raw_dir = Path(raw_dir) if raw_dir else RAW_DIR
    p = _resolve_raw_path(name_or_path, raw_dir)
    text = p.read_text(encoding="utf-8")
    data = json.loads(text)  # validate it is JSON; raises on malformed input
    return RawInput(name=p.stem, text=text, data=data)


def _derive_record_id(data: dict, source_stem: str, index: int) -> str:
    for key in COMMON_ID_KEYS:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return f"{source_stem}#{index}"


def _record_from_obj(obj, source: str, stem: str, index: int) -> RawRecord:
    return RawRecord(
        id=_derive_record_id(obj, stem, index),
        text=json.dumps(obj, ensure_ascii=False, indent=2),
        data=obj,
        source=source,
        index=index,
    )


def _records_from_container(obj, source: str, stem: str,
                            issues: list[IngestIssue]) -> list[RawRecord]:
    """Turn a parsed JSON value into person records: unwrap a {people:[...]} bundle,
    a bare list, or treat a lone object as a single record. Non-object items are skipped."""
    if isinstance(obj, dict) and isinstance(obj.get("people"), list):
        items, prefix = obj["people"], "people"
    elif isinstance(obj, list):
        items, prefix = obj, "item"
    else:
        items, prefix = [obj], "record"
    records = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            issues.append(IngestIssue(source, f"{prefix}[{i}]",
                                      f"skipped non-object record ({type(item).__name__})"))
            continue
        records.append(_record_from_obj(item, source, stem, i))
    return records


def _load_ndjson(text: str, source: str, stem: str,
                 issues: list[IngestIssue]) -> list[RawRecord]:
    records = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        s = line.strip()
        if not s:
            continue
        try:
            obj = json.loads(s)
        except json.JSONDecodeError as exc:
            issues.append(IngestIssue(source, f"line {lineno}", f"invalid JSON: {exc}"))
            continue
        if not isinstance(obj, dict):
            issues.append(IngestIssue(source, f"line {lineno}",
                                      f"skipped non-object ({type(obj).__name__})"))
            continue
        records.append(_record_from_obj(obj, source, stem, lineno - 1))
    return records


def load_records(name_or_path: str | Path,
                 raw_dir: Path | None = None) -> tuple[list[RawRecord], list[IngestIssue]]:
    """Ingest a raw source into per-person records plus a list of ingest issues (REQ-11/12).

    Handles: NDJSON (one object per line), a {people:[...]} bundle, a bare JSON array, and
    a single object. Malformed NDJSON lines and non-object records are skipped and reported,
    never fatal. A .json file that fails whole-file parsing is retried as NDJSON.
    """
    raw_dir = Path(raw_dir) if raw_dir else RAW_DIR
    p = _resolve_raw_path(name_or_path, raw_dir)
    text = p.read_text(encoding="utf-8")
    source, stem = str(p), p.stem
    issues: list[IngestIssue] = []

    if p.suffix.lower() == ".ndjson":
        return _load_ndjson(text, source, stem, issues), issues

    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        # A .json file that isn't valid JSON might actually be NDJSON — try that before failing.
        ndjson_records = _load_ndjson(text, source, stem, [])
        if ndjson_records:
            issues.append(IngestIssue(source, "file",
                                      "not valid JSON; parsed as NDJSON instead"))
            return ndjson_records, issues
        issues.append(IngestIssue(source, "file", f"invalid JSON: {exc}"))
        return [], issues

    return _records_from_container(obj, source, stem, issues), issues


def load_template(name: str, templates_dir: Path | None = None) -> Template:
    templates_dir = Path(templates_dir) if templates_dir else TEMPLATES_DIR
    dir_name = _normalize_template_name(name)
    directory = templates_dir / dir_name
    schema_path = directory / "schema.json"
    if not schema_path.is_file():
        raise FileNotFoundError(f"Unknown template '{name}' (expected {schema_path})")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    guidance_path = directory / "guidance.md"
    guidance = guidance_path.read_text(encoding="utf-8") if guidance_path.is_file() else ""
    return Template(
        name=dir_name,
        schema=schema,
        guidance=guidance,
        template_file=f"{dir_name}/template.html.j2",
        directory=directory,
    )


def load_brand(brand_id: str, brands_dir: Path | None = None) -> Brand:
    brands_dir = Path(brands_dir) if brands_dir else BRANDS_DIR
    path = brands_dir / f"{brand_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Unknown brand '{brand_id}' (expected {path})")
    data = json.loads(path.read_text(encoding="utf-8"))
    return Brand(id=data.get("id", brand_id), data=data)
