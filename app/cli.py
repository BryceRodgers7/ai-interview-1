"""Command-line interface (REQ-9, REQ-11, REQ-12, NFR-1).

    python render.py list
    python render.py render --raw <file> [--person ID] --template resume --brand procom [--out F] [--model M] [--dump]
    python render.py render-all [--raw <file>] [--limit N] [--out-dir output] [--model M]

The unit of work is a *person record* (REQ-11): a raw file may be a {people:[...]} bundle,
a JSON array, a single object, or NDJSON. `render-all` renders the full record x template x
brand matrix, deduping records by id across files, caching the cram per (record x template)
so brands add renders but not API calls (REQ-9). Malformed records and per-record failures
are reported but never abort the batch (REQ-12).
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

from . import crammer, loader, renderer


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("_") or "record"


def _out_name(record_id: str, template: str, brand: str) -> str:
    return f"{_slug(record_id)}__{template}__{brand}.html"


def _gather_records(raw_arg: str | None):
    """Collect records from a single file (raw_arg) or all raw files (deduped by id).

    Returns (records, issues, duplicate_count)."""
    files = [raw_arg] if raw_arg else loader.list_raw()
    records, issues, seen, dups = [], [], set(), 0
    for f in files:
        recs, iss = loader.load_records(f)
        issues.extend(iss)
        for r in recs:
            if r.id in seen:
                dups += 1
                continue
            seen.add(r.id)
            records.append(r)
    return records, issues, dups


def _report_issues(issues) -> None:
    for i in issues:
        print(f"  [skip] {i.source} {i.location}: {i.reason}", file=sys.stderr)


def cmd_list(args: argparse.Namespace) -> int:
    print("Raw sources (data/raw/):")
    files = loader.list_raw()
    for f in files:
        recs, issues = loader.load_records(f)
        note = f"{len(recs)} record(s)" + (f", {len(issues)} issue(s)" if issues else "")
        print(f"  - {f}  ({note})")
    if not files:
        print("  (none yet — drop .json/.ndjson files into data/raw/)")

    print("\nTemplates (content_templates/):")
    for t in loader.list_templates():
        print(f"  - {t}")

    print("\nBrands (brands/):")
    for b in loader.list_brands():
        print(f"  - {b}")
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    records, issues, _ = _gather_records(args.raw)
    if issues:
        _report_issues(issues)

    if args.person:
        matches = [r for r in records if r.id == args.person]
        if not matches:
            ids = ", ".join(r.id for r in records[:20])
            print(f"Error: no record with id '{args.person}'. Available: {ids}"
                  + (" ..." if len(records) > 20 else ""), file=sys.stderr)
            return 2
        record = matches[0]
    elif len(records) == 1:
        record = records[0]
    elif not records:
        print("Error: no records found in the source.", file=sys.stderr)
        return 2
    else:
        ids = ", ".join(r.id for r in records[:20])
        print(f"Error: source has {len(records)} records; pick one with --person <id>. "
              f"e.g. {ids}" + (" ..." if len(records) > 20 else ""), file=sys.stderr)
        return 2

    template = loader.load_template(args.template)
    brand = loader.load_brand(args.brand)
    result = crammer.cram(record, template, model=args.model)
    content = result.get("content", {})
    sources = result.get("sources", [])

    out_path = Path(args.out) if args.out else Path("output") / _out_name(
        record.id, template.name, brand.id
    )
    renderer.render_to_file(content, sources, template, brand, out_path)
    print(f"Wrote {out_path}")
    if args.dump:
        dump_path = out_path.with_suffix(".cram.json")
        dump_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Wrote {dump_path}")
    return 0


def cmd_render_all(args: argparse.Namespace) -> int:
    records, issues, dups = _gather_records(args.raw)
    if issues:
        print(f"Ingest issues ({len(issues)}):", file=sys.stderr)
        _report_issues(issues)
    if dups:
        print(f"Deduped {dups} record(s) with ids already seen in another file.")
    if args.limit:
        records = records[: args.limit]
    if not records:
        print("No records to render. Add files to data/raw/.", file=sys.stderr)
        return 1

    templates = loader.list_templates()
    brands = loader.list_brands()
    out_dir = Path(args.out_dir)

    cram_cache: dict[tuple[str, str], dict | None] = {}
    entries, errors = [], []
    rendered = cram_calls = failed = 0

    print(f"Rendering {len(records)} record(s) x {len(templates)} template(s) x "
          f"{len(brands)} brand(s) = {len(records)*len(templates)*len(brands)} report(s)...")

    for record in records:
        for template_name in templates:
            template = loader.load_template(template_name)
            key = (record.id, template.name)
            if key not in cram_cache:
                try:
                    cram_cache[key] = crammer.cram(record, template, model=args.model)
                    cram_calls += 1
                except Exception as exc:  # noqa: BLE001 - a bad record must not abort the batch
                    cram_cache[key] = None
                    errors.append((record.id, template.name, f"cram: {exc}"))
            result = cram_cache[key]
            if result is None:
                failed += len(brands)
                continue
            content = result.get("content", {})
            sources = result.get("sources", [])
            for brand_name in brands:
                brand = loader.load_brand(brand_name)
                fname = _out_name(record.id, template.name, brand.id)
                try:
                    renderer.render_to_file(content, sources, template, brand, out_dir / fname)
                    rendered += 1
                    entries.append((record.id, template.name, brand.id, fname))
                except Exception as exc:  # noqa: BLE001
                    failed += 1
                    errors.append((record.id, f"{template.name}/{brand.id}", f"render: {exc}"))

    _write_index(out_dir, entries)
    print(f"\nDone: {rendered} rendered, {cram_calls} cram call(s), {failed} failed.")
    print(f"Index: {out_dir / 'index.html'}")
    if errors:
        print(f"\n{len(errors)} error(s):", file=sys.stderr)
        for rid, what, msg in errors[:15]:
            print(f"  [fail] {rid} {what}: {msg[:120]}", file=sys.stderr)
    return 0


def _write_index(out_dir: Path, entries: list[tuple[str, str, str, str]]) -> None:
    """Write a plain, brand-neutral index.html linking every rendered report."""
    out_dir.mkdir(parents=True, exist_ok=True)
    by_person: dict[str, list[tuple[str, str, str]]] = {}
    for rid, template, brand, fname in entries:
        by_person.setdefault(rid, []).append((template, brand, fname))

    rows = []
    for rid in sorted(by_person):
        links = " · ".join(
            f'<a href="{html.escape(fn)}">{html.escape(t)} / {html.escape(b)}</a>'
            for t, b, fn in sorted(by_person[rid])
        )
        rows.append(f"<tr><td class='id'>{html.escape(rid)}</td><td>{links}</td></tr>")

    doc = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>People-Work Reports — Index</title><style>"
        "body{font-family:system-ui,sans-serif;margin:32px;color:#0f172a;}"
        "h1{font-size:1.3rem;} table{border-collapse:collapse;width:100%;}"
        "td{border-bottom:1px solid #e2e8f0;padding:6px 10px;vertical-align:top;font-size:.9rem;}"
        ".id{font-family:ui-monospace,Consolas,monospace;white-space:nowrap;color:#4f46e5;}"
        "a{color:#0f766e;text-decoration:none;} a:hover{text-decoration:underline;}"
        "</style></head><body>"
        f"<h1>People-Work Reports — {len(entries)} report(s), {len(by_person)} person(s)</h1>"
        "<table><tbody>" + "".join(rows) + "</tbody></table></body></html>"
    )
    (out_dir / "index.html").write_text(doc, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="render.py", description="People-Work Report Generator")
    sub = parser.add_subparsers(dest="command", required=True)

    lp = sub.add_parser("list", help="List raw sources (with record counts), templates, and brands")
    lp.set_defaults(func=cmd_list)

    rp = sub.add_parser("render", help="Render one report from one person record")
    rp.add_argument("--raw", required=True, help="Raw source file (path or name in data/raw/)")
    rp.add_argument("--person", help="Record id to select when the source has many people")
    rp.add_argument("--template", required=True, help="Template name (resume, work-profile)")
    rp.add_argument("--brand", required=True, help="Brand id (procom, conspro)")
    rp.add_argument("--out", help="Output HTML path (default: output/<id>__<template>__<brand>.html)")
    rp.add_argument("--model", default=None, help="OpenAI model (default: $OPENAI_MODEL or gpt-4o-mini)")
    rp.add_argument("--dump", action="store_true", help="Also write the crammed {content, sources} JSON")
    rp.set_defaults(func=cmd_render)

    ap = sub.add_parser("render-all", help="Render the full record x template x brand matrix")
    ap.add_argument("--raw", help="Restrict to one source file (default: all files in data/raw/, deduped)")
    ap.add_argument("--limit", type=int, help="Cap the number of records (useful for a quick check)")
    ap.add_argument("--out-dir", default="output", help="Output directory (default: output)")
    ap.add_argument("--model", default=None, help="OpenAI model (default: $OPENAI_MODEL or gpt-4o-mini)")
    ap.set_defaults(func=cmd_render_all)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except crammer.CramError as exc:
        print(f"Cram error: {exc}", file=sys.stderr)
        return 3
