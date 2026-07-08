# Project Status

_Last updated: 2026-07-08 (end of session)._

## Version 1 — draft complete

- Committed **locally** as `6264642` — "Initial draft: people-work report generator" — on
  branch `main`. **Not yet pushed**; the remote/push is handled manually by the maintainer.
- Working tree was clean at commit time; 34 files tracked (`output/` and caches gitignored).

## Verification snapshot

- **Tests:** 30 offline (`pytest`) + 4 live integration (`pytest -m integration`) — all green.
- **Full render (`render-all`):** 60 unique people × 2 templates × 2 brands = 240 reports.
  - **238 rendered, 119 cram calls, 2 failed.**
  - Dedup collapsed the duplicate json/ndjson copies (120 ingested → 60 unique).
  - Browsable output at `output/index.html`.

## Known issues

- **1 transient cram failure:** `external_it_4008` / work-profile returned truncated JSON
  ("unterminated string"). It was caught, reported, and the batch continued — its two
  work-profile reports are missing; its resume reports rendered. This is the poster case
  for app-level retry (roadmap item 3).

## Deferred / proposed changes (discussed this session — NOT yet implemented)

Priority order to be decided after reviewing `output/index.html`.

1. **Dedup polish (mostly done already).** `render-all` dedupes records by id across formats
   ("first file wins"). Optional: log *which* ids/source were dropped, add `--prefer json|ndjson`,
   and eventually a real reconciliation rule (e.g. newest `metadata.lastUpdated` wins).
   Files: `app/cli.py`, `app/loader.py`.
2. **Document the AI-call structure.** Current = "A": one OpenAI call per (record × template),
   whole-document extraction, reused across brands. Document trade-offs of A (whole-doc),
   B (per-field), C (per-section). Documentation-only. Files: `docs/DESIGN.md`.
3. **Problem handling — the real gap.**
   - *Observability:* structured logging + `output/run_manifest.json` (per person/template/brand:
     status, error, blank-field list, timing) + per-report completeness flagging (this is what the
     empty `metadata.dataQualityNotes` field is begging for).
   - *Resilience:* app-level retry with exponential backoff (+ optional repair re-ask) around cram
     calls — would auto-recover `external_it_4008`.
   - *Today:* blank fields are not flagged/logged (only implied by the provenance appendix); ingest
     issues and cram errors print to stderr only (not persisted); the only retry is the OpenAI SDK
     default (`max_retries=2`).
   Files: `app/crammer.py`, `app/cli.py`, + a new logging/manifest module.
4. **Enhancement menu.** On-disk cram cache keyed by (record-hash, template, model) for idempotent
   re-runs; concurrency for the cram calls; PDF export (weasyprint); a `doctor`/`lint` command
   (validate brands/schemas/raw before a run); token/cost accounting; PII-redaction toggle
   (external resume vs internal profile); golden-file render tests; optional auto-pair mode
   (personType→template, domain→brand) as an alternative to the full matrix.

## Next-session entry point

1. Push v1 to GitHub (maintainer, manual).
2. Review `output/index.html` — especially the messy records and the cert-status / provenance
   rendering — to set priorities.
3. Pick the first batch from the roadmap above.
