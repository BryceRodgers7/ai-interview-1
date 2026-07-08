# Requirements & Goals — People-Work Report Generator

*Authored before implementation. This is the source of truth for what the system must do.
Every requirement below maps to at least one automated test (see the "Verified by" column
and the traceability matrix in [DESIGN.md](DESIGN.md)).*

## Problem

Organizations hold **people-work data** (employee records, resumes, work history) in
messy, heterogeneous forms. They need to present that data as clean documents — an
external **resume** for hiring, or an internal **work-profile** for finding employees
with the right skills — each rendered in a company's own visual **brand**.

The raw data does **not** match the fields a document needs, so the system uses an AI
step to *safely* map ("cram") arbitrary raw data into a document's field schema, then
renders it through independent template and brand layers.

## Goals

- **G1 — Separation of concerns.** Raw data, content templates, and presentation brands
  are independent, composable assets. Any template × any brand produces a report.
- **G2 — Safe AI cramming.** Unstructured/arbitrary raw data is transformed into a
  template's structured fields by AI, *safely*: schema-valid, grounded (no fabrication),
  injection-resistant, and traceable to sources.
- **G3 — Branded output.** The system produces self-contained, brand-styled HTML reports.

## Requirements

| ID | Requirement | Goal | Verified by |
|----|-------------|------|-------------|
| REQ-1 | Load arbitrary raw people-data from `data/raw/`; enumerate available raw sources, templates, and brands. | G1 | `test_loader` |
| REQ-2 | Each **template** is defined by a field `schema.json` plus a Jinja HTML fragment that uses only semantic CSS classes (no hard-coded colors/fonts). Schemas capture the fields their document needs — e.g. projects, certification status, internal staffing signals. | G1 | `test_loader`, `test_renderer` |
| REQ-3 | Each **brand** is defined by visual design tokens (colors, fonts, spacing) plus chrome text (tagline, header/footer, section-label styling). | G1 | `test_loader`, `test_renderer` |
| REQ-4 | The AI cram maps raw JSON into a template's schema using OpenAI **structured outputs** (strict `json_schema`), guaranteeing schema-valid content. | G2 | `test_crammer`, `test_integration` |
| REQ-5 | **No fabrication.** Fields unsupported by the source are `null`/empty and render as a blank marker ("—"), never invented. | G2 | `test_renderer`, `test_integration` |
| REQ-6 | **Injection resistance.** Instructions embedded inside the raw data (e.g., "ignore previous instructions") are treated as data and have no effect on extraction. | G2 | `test_crammer` (prompt assembly), `test_integration` (behavior) |
| REQ-7 | **Source traceability.** The cram emits a `sources` list mapping each populated field to a verbatim source quote, rendered as a "Sources & Provenance" appendix. | G2 | `test_crammer`, `test_renderer`, `test_integration` |
| REQ-8 | **Composability.** Any template × any brand renders successfully; editing a brand never requires touching a template and vice-versa. | G1 | `test_renderer` |
| REQ-9 | CLI provides `list`, `render` (select a person with `--person`), and `render-all` (the full record × template × brand matrix, deduping records by id across files, writing a browsable `index.html`); `render-all` caches cram per (record × template) and reuses it across brands (no redundant API calls). | G1, G3 | `test_cli` |
| REQ-10 | Reports are **self-contained HTML** — system fonts only, no external stylesheet/script/image fetches. | G3 | `test_renderer` |
| REQ-11 | Ingest a raw source into per-person **records**, supporting a `{people:[…]}` bundle, a JSON array, a single object, and NDJSON; derive a stable id per record; list sources recursively across `.json`/`.ndjson`. | G1, G2 | `test_ingest`, `test_loader` |
| REQ-12 | **Graceful degradation on messy data.** Malformed NDJSON lines and non-object records are skipped and reported (never fatal); a single record's cram/render failure never aborts a `render-all` batch; structurally inconsistent records and missing fields degrade to blanks rather than crashing. | G2 | `test_ingest`, `test_renderer`, `test_cli` |

## Non-functional requirements

| ID | Requirement | Verified by |
|----|-------------|-------------|
| NFR-1 | AI uses OpenAI `gpt-4o-mini` by default, reads the key from the `OPENAI_API_KEY` env var, and the model is overridable via `--model` / `OPENAI_MODEL`. | `test_cli` |
| NFR-2 | Minimal dependencies (`jinja2`, `openai`, `pytest`). The OpenAI client is **injectable** so unit tests run fully offline against a stub. | `test_crammer` |

## Out of scope (this demo)

- Persistent storage / database, authentication, and any web server or UI.
- PDF export (HTML is structured so it could be added later).
- Editing raw data through the tool (raw JSON files are provided externally).
