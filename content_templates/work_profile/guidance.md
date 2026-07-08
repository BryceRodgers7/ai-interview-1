You are producing the structured data for an internal **work-profile** — a document a
company uses to find one of its *existing* employees with the right skills for a new
piece of work. The audience is internal (managers/staffing), not an external employer.

Map the source into these fields:

- **name** — the employee's full/display name.
- **current_role** — title, department, and tenure, each only if present in the source
  (department and tenure are frequently absent — use null rather than guessing).
- **summary** — a short internal-facing summary of strengths and focus, synthesized ONLY
  from facts in the source. If unsupported, use null.
- **skills** — a list of { name, group, level }. Set group to the grouping the source
  uses if any (e.g. "primary", "secondary", "soft"); otherwise null. Set level only when
  the source states a proficiency; otherwise null.
- **experience** — internal-relevant work history: organization, role, start, end, and
  highlights, grounded in the source.
- **projects** — name, the person's role, the impact/outcome, and technologies used.
- **certifications** — name and status per certification; copy status verbatim when
  present (e.g. "Active", "Expired", "In Progress"), else null.
- **internal** — internal staffing signals, each only from the source:
  - availability (e.g. availability for new work),
  - promotion_readiness,
  - performance_rating (as text, e.g. "4.1"),
  - manager,
  - interests (career interests),
  - notes (internal notes).

Include only what the source supports. Leave unknown scalar fields null and unknown lists
empty. Do not invent roles, departments, tenure, skills, proficiency levels, projects,
certifications/status, ratings, managers, or availability.
