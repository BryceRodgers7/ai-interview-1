# Design (as-built) — People-Work Report Generator

*Written after implementation. Describes what was actually built and maps every
requirement in [REQUIREMENTS.md](REQUIREMENTS.md) to the code that satisfies it and the
test that verifies it.*

## Overview

Three independent asset types are composed into an HTML report by a three-stage pipeline:

```
data/raw/*.json ──► crammer.cram() ──► {content, sources} ──► renderer.render(content, sources, template, brand) ──► HTML
   (raw, any shape)   OpenAI, safe        (schema-valid)          template = what content · brand = how it looks
```

- **Raw data** is arbitrary JSON. Nothing in the code assumes its shape; it is serialized
  and handed to the model as untrusted text.
- **Templates** (`content_templates/<name>/`) decide *what* content appears. Each is a
  `schema.json` (the fields the AI must fill) + `guidance.md` (extraction hints) +
  `template.html.j2` (Jinja fragment using only semantic CSS classes).
- **Brands** (`brands/<id>.json`) decide *how it looks*: design tokens (colors, fonts,
  spacing) + chrome text (tagline, header/footer), injected as CSS variables.

The template axis and brand axis never reference each other, so any template × any brand
composes (REQ-8).

## Modules

### `app/loader.py` — asset management (REQ-1, REQ-2, REQ-3)
Loads and lists the three asset types from disk. `RawInput`, `Template`, and `Brand`
dataclasses. Directory arguments default to `None` and resolve module globals
(`RAW_DIR`, `TEMPLATES_DIR`, `BRANDS_DIR`) at call time, so tests and the CLI can
redirect asset locations. `load_template` accepts `resume` or `work-profile`
(hyphens normalized to the underscore directory name).

### `app/crammer.py` — the safe AI cram (REQ-4, REQ-5, REQ-6, REQ-7, NFR-1, NFR-2)
`cram(raw, template, *, client=None, model=None)` returns `{"content": {...}, "sources": [...]}`.
The four safeguards live here:

| Safeguard | Mechanism |
|-----------|-----------|
| Schema-valid (REQ-4) | `build_response_format()` sets `response_format` to a strict `json_schema` built from the template's schema. The model cannot return off-schema data. |
| No fabrication (REQ-5) | Template schemas make scalars nullable; `SYSTEM_PROMPT` rule 1 permits only facts in the source, else `null`/`[]`. |
| Injection-resistant (REQ-6) | `build_messages()` wraps raw data in `<source>…</source>`; `SYSTEM_PROMPT` rule 2 declares that block untrusted data and forbids obeying instructions inside it. |
| Traceability (REQ-7) | `build_wrapper_schema()` requires a `sources` array of `{field, evidence}`; `SYSTEM_PROMPT` rule 3 requires a verbatim quote per populated field. |

The OpenAI `client` is a parameter (only `_default_client()` constructs a real one from
`OPENAI_API_KEY`), so unit tests inject a stub and run offline (NFR-2). Model defaults to
`$OPENAI_MODEL` or `gpt-4o-mini` (NFR-1).

### `app/renderer.py` + `content_templates/` — composition (REQ-2, REQ-3, REQ-8, REQ-10)
A Jinja `Environment` with **autoescape on** renders `content` through the chosen
template, which `extends _base.html.j2`. The base turns `brand.tokens` into CSS custom
properties (`:root { --primary: … }`), draws the branded header/footer chrome, exposes
`{% block content %}`, and renders the "Sources & Provenance" appendix from `sources`.
Content templates use only semantic classes (`.section`, `.entry`, `.tag`, …) and never
hard-code colors/fonts — that is the physical separation behind REQ-8. Only system fonts
and inline CSS are used, so reports are self-contained (REQ-10). Autoescaping means any
HTML that slipped into the untrusted extracted data is escaped, not injected.

### `app/loader.py` — record ingestion (REQ-11, REQ-12)
`load_records(path)` turns a raw source into a list of `RawRecord` plus a list of
`IngestIssue`. It unwraps a `{people:[…]}` bundle, a bare JSON array, or a single object,
and parses NDJSON line-by-line. Malformed NDJSON lines and non-object records are skipped
and recorded as issues, never raised (REQ-12); a `.json` file that fails whole-file parsing
is retried as NDJSON. Each record gets a stable id from `personId`/`id`/… or a synthesized
`<file>#<index>`. `list_raw` recurses and includes `.json` and `.ndjson`. The record's
serialized JSON is the untrusted source text handed to the crammer — so structural variance
between records (skills as dict vs list, certs as string vs object, an empty profile, etc.)
is absorbed by the AI cram rather than by brittle parsing code.

### `app/renderer.py` + `content_templates/` — composition (REQ-2, REQ-3, REQ-8, REQ-10)
A Jinja `Environment` with **autoescape on** renders `content` through the chosen
template, which `extends _base.html.j2`. The base turns `brand.tokens` into CSS custom
properties (`:root { --primary: … }`), draws the branded header/footer chrome, exposes
`{% block content %}`, and renders the "Sources & Provenance" appendix from `sources`.
Content templates use only semantic classes (`.section`, `.entry`, `.tag`, `.cert-status`,
…) and never hard-code colors/fonts — that is the physical separation behind REQ-8. The
enriched resume adds a Projects section and certification status; the work-profile adds
projects, skill groups/levels, and internal staffing signals (promotion readiness,
performance rating, manager, notes). Only system fonts and inline CSS are used, so reports
are self-contained (REQ-10). Autoescaping means any HTML in the untrusted extracted data is
escaped, not injected.

### `app/cli.py` + `render.py` — interface (REQ-9, REQ-12, NFR-1)
`list` shows each raw source with its record count; `render --raw … [--person id]` renders
one record (erroring helpfully when a multi-record source needs a `--person`); `render-all`
gathers records from all sources, **dedupes by id across files**, and renders the full
record × template × brand matrix, caching the cram per `(record, template)` so brands add
renders but never extra API calls (REQ-9). A per-record cram/render failure is caught,
counted, and reported — the batch always completes (REQ-12) — and a browsable `index.html`
links every report. `--model` overrides the model (NFR-1); `--dump` writes the crammed JSON;
`--limit` caps records for a quick check.

## Requirement → implementation → test traceability

| Req | Implemented in | Verified by (test) |
|-----|----------------|--------------------|
| REQ-1 | `loader.load_raw`, `loader.list_raw` | `test_loader::test_load_raw_reads_arbitrary_json`, `::test_list_raw_empty_when_dir_absent` |
| REQ-2 | `loader.load_template`, `content_templates/*/{schema.json,template.html.j2}` | `test_loader::test_load_template_exposes_schema_guidance_and_file`, `test_renderer::test_template_changes_content_not_look` |
| REQ-3 | `loader.load_brand`, `brands/*.json` | `test_loader::test_load_brand_has_tokens_and_chrome`, `test_renderer::test_brand_changes_look_not_content` |
| REQ-4 | `crammer.build_wrapper_schema`, `build_response_format` | `test_crammer::test_response_format_is_strict_json_schema`, `test_integration_openai::test_output_is_schema_shaped` |
| REQ-5 | nullable schemas + `SYSTEM_PROMPT` + `_macros.dash` | `test_renderer::test_missing_fields_render_blank_not_invented`, `test_integration_openai::test_no_fabrication_of_absent_sections` |
| REQ-6 | `crammer.build_messages`, `SYSTEM_PROMPT` rule 2 | `test_crammer::test_messages_wrap_raw_as_untrusted_source`, `test_integration_openai::test_injection_is_ignored` |
| REQ-7 | `build_wrapper_schema` `sources`, `_base` provenance appendix | `test_crammer::test_wrapper_schema_wraps_content_and_requires_sources`, `test_renderer::test_renders_content_and_provenance`, `test_integration_openai::test_sources_are_present_and_grounded` |
| REQ-8 | semantic classes vs. brand CSS tokens | `test_renderer::test_brand_changes_look_not_content`, `::test_template_changes_content_not_look` |
| REQ-9 | `cli.cmd_render_all` (records × templates × brands, dedup, cram cache, index) | `test_cli::test_render_all_crams_once_per_raw_template_then_reuses_across_brands`, `::test_list_command_prints_assets` |
| REQ-10 | `_base.html.j2` (inline CSS, system fonts) | `test_renderer::test_report_is_self_contained` |
| REQ-11 | `loader.load_records`, `_records_from_container`, `_load_ndjson`, `_derive_record_id` | `test_ingest::test_unwraps_people_bundle`, `::test_single_object_is_one_record`, `::test_ndjson_skips_bad_lines`, `::test_missing_id_is_synthesized` |
| REQ-12 | issue collection in loader; try/except in `cli.cmd_render_all`; nullable rendering | `test_ingest::test_bare_array_skips_non_objects`, `::test_json_extension_falls_back_to_ndjson`, `test_renderer::test_missing_fields_render_blank_not_invented` |
| NFR-1 | `cli` `--model`, `crammer.DEFAULT_MODEL`/`$OPENAI_MODEL` | `test_cli::test_render_parser_flags_and_model_default` |
| NFR-2 | `crammer.cram(client=...)` injection | `test_crammer::test_cram_uses_injected_client_and_returns_parsed` |

Every REQ/NFR maps to ≥1 passing test. Offline suite: `pytest` (30 tests). Live suite:
`pytest -m integration` (4 tests; needs `OPENAI_API_KEY`).

## Key decisions & trade-offs

- **Template owns its schema.** Making each template define the extraction schema is what
  lets the same raw data feed different documents and keeps the cram generic.
- **Provenance as a sibling of content**, not per-field wrappers, keeps template schemas
  readable while still satisfying traceability. Field paths are dotted strings (e.g.
  `experience[0].company`); the model may prefix them with `content.` — still traceable.
- **Autoescape on** is deliberate defense-in-depth: even if the model echoed markup from
  the source, it cannot inject into the report.
- **Strict structured outputs** remove the need for a separate `jsonschema` validation
  dependency.
- **The record is the unit of work, and the AI absorbs structural messiness.** Because each
  record is serialized and handed to the model as text, inconsistent shapes across records
  (skills as dict vs list, certs as string vs object, missing/empty blocks, `type` vs
  `personType`) need no bespoke parsing — the cram maps whatever is present into the schema,
  and unmapped data simply doesn't appear. Structural failures are contained per-record.

## Limitations (demo scope)

- Very large raw files are sent whole; there is no chunking/summarization for inputs that
  approach the model's context window.
- Rendering is the full matrix (`render-all` = records × templates × brands); pairing a
  person to a "natural" template/brand by `personType`/`domain` is intentionally not done,
  and those fields are inconsistent in messy data anyway.
- No persistence, web server, auth, or PDF export.
- Brand tokens are trusted (developer-authored) and injected into `<style>` without
  escaping; brands are not user-supplied content.
