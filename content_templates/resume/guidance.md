You are producing the structured data for an external **resume** — a document an
employer uses to evaluate an outside candidate for hire.

Map the source into these fields:

- **name** — the person's full/display name.
- **headline** — a short professional title. If not stated or clearly implied, use null.
- **summary** — a 2–4 sentence professional summary. You may synthesize it, but ONLY
  from facts present in the source. If there is not enough to support one, use null.
- **contact** — email, phone, location, and links (URLs such as LinkedIn / GitHub /
  portfolio). Contact info is often missing in the source; any absent field is null and
  links is an empty array if none. Build location from any city/state/region present.
- **experience** — one entry per job, most recent first: company, title, start, end
  (use "Present" only if the source marks the role current, e.g. a null/blank end date),
  and highlights (accomplishments, grounded in the source).
- **projects** — notable projects: name, the person's role, the impact/outcome, and the
  technologies used. Empty array if the source has none.
- **skills** — individual skill names (flatten any groupings the source uses).
- **education** — school, degree, year for each entry present.
- **certifications** — one entry per certification: name and status. Copy the status
  verbatim from the source when present (e.g. "Active", "Expired", "In Progress"); if the
  source gives a name but no status, set status to null.

Include only what the source supports. Leave unknown scalar fields null and unknown lists
empty. Do not add employers, titles, skills, projects, dates, certifications, or a
certification status that are not in the source.
