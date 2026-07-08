# People-Work Report Generator

A small back-end demo that manages three **independent, composable** assets — raw
people-data, content **templates**, and presentation **brands** — and produces
brand-styled HTML reports. Because the raw data is unstructured and does not match
template fields, an AI step **safely crams** the raw data into each template's schema.

```
raw JSON  ──►  [ AI cram (OpenAI, safe) ]  ──►  structured fields (+ provenance)
                                                       │
                                       [ TEMPLATE ] ──►│──► [ BRAND ] ──► HTML report
                                       (what content)       (how it looks)
```

- **Templates** (`content_templates/`) own *what* content appears: `resume` (external
  hiring) and `work-profile` (internal skill-matching). Each is a field `schema.json`
  + a Jinja HTML fragment using only semantic CSS classes.
- **Brands** (`brands/`) own *how it looks*: `procom` (techy) and `conspro` (corporate)
  — design tokens (colors/fonts/spacing) + chrome text (tagline/header/footer).
- **The cram** (`app/crammer.py`) maps arbitrary raw JSON into a template's schema with
  four safeguards: **schema-validated** output, **no fabrication**, **injection-resistance**,
  and **source traceability**.

See [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) for goals/requirements and
[docs/DESIGN.md](docs/DESIGN.md) for the as-built design and requirement→test traceability.

## Setup

```powershell
pip install -r requirements.txt
# OPENAI_API_KEY must be set in the environment (it already is on the dev machine)
$env:OPENAI_API_KEY = "sk-..."   # if not already set
```

## Usage

```powershell
# List raw sources (with record counts), templates, and brands
python render.py list

# Render one person's report (cram + template + brand -> HTML)
python render.py render --raw json/people_work_template_demo_seed.json --person procom_emp_1001 --template resume --brand procom --dump

# Render the full record x template x brand matrix (dedup across formats; writes output/index.html)
python render.py render-all              # everything in data/raw/
python render.py render-all --limit 3    # quick check on the first 3 people
```

Put raw files in `data/raw/` (searched recursively). A source may be a single JSON object,
a JSON array, a `{ "people": [ … ] }` bundle, or **NDJSON** (one object per line). Each
person becomes a **record**; the pipeline makes **no assumptions** about a record's
structure — it is serialized and passed to the model as untrusted source, and the AI cram
maps whatever is present into the template's schema. Malformed lines/records are skipped and
reported; a single record's failure never aborts a `render-all` batch.

## Tests

```powershell
pytest                 # offline unit tests (stubbed OpenAI client)
pytest -m integration  # live API tests: grounding + injection-resistance (needs OPENAI_API_KEY)
```
