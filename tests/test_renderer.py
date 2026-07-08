"""Tests for the render/compose layer — REQ-2, REQ-3, REQ-5, REQ-7, REQ-8, REQ-10."""
from __future__ import annotations

import copy

from app import loader, renderer


def _render_resume(content, sources, brand_id="procom"):
    return renderer.render(
        content, sources, loader.load_template("resume"), loader.load_brand(brand_id)
    )


def test_renders_content_and_provenance(resume_content, resume_sources):
    # REQ-2 (content) + REQ-7 (provenance appendix).
    html = _render_resume(resume_content, resume_sources)
    assert "Dana Reed" in html
    assert "Python" in html
    assert "Sources &amp; Provenance" in html
    assert "strong Python background" in html  # the source evidence quote


def test_missing_fields_render_blank_not_invented(resume_content):
    # REQ-5: unsupported fields are blank ("—"), never fabricated.
    content = copy.deepcopy(resume_content)
    content["summary"] = None
    content["certifications"] = []
    content["experience"] = []
    content["projects"] = []
    html = _render_resume(content, [])
    assert "—" in html          # em dash blank marker is present
    assert "Summary" not in html     # summary section omitted when null (nothing invented)


def test_certification_status_is_rendered(resume_content):
    # REQ-2: enriched certs carry status; Expired is visually distinguished.
    html = _render_resume(resume_content, [])
    assert "AWS Certified Developer" in html
    assert "cert-status--active" in html
    assert "cert-status--expired" in html and "Expired" in html


def test_projects_section_rendered(resume_content):
    # REQ-2: projects section uses the enriched projects data.
    html = _render_resume(resume_content, [])
    assert "Projects" in html
    assert "Billing Rewrite" in html
    assert "Cut release friction" in html


def test_brand_changes_look_not_content(resume_content, resume_sources):
    # REQ-8 + REQ-3: same content, different brand -> same text, different styling.
    procom = _render_resume(resume_content, resume_sources, "procom")
    conspro = _render_resume(resume_content, resume_sources, "conspro")
    assert "Dana Reed" in procom and "Dana Reed" in conspro
    assert procom != conspro
    assert "#4f46e5" in procom and "#4f46e5" not in conspro   # ProCom indigo
    assert "#0f766e" in conspro and "#0f766e" not in procom   # ConsPro teal


def test_template_changes_content_not_look(resume_content, work_profile_content):
    # REQ-8 + REQ-2: same brand, different template -> different sections.
    brand = loader.load_brand("procom")
    resume_html = renderer.render(resume_content, [], loader.load_template("resume"), brand)
    wp_html = renderer.render(work_profile_content, [], loader.load_template("work_profile"), brand)
    assert "Internal Staffing" in wp_html and "Internal Staffing" not in resume_html
    assert "Education" in resume_html and "Education" not in wp_html


def test_report_is_self_contained(resume_content, resume_sources):
    # REQ-10: no external stylesheet/script/font/image fetches.
    html = _render_resume(resume_content, resume_sources)
    for needle in ("<link", "<script", "http://", "https://", "@import", "url("):
        assert needle not in html


def test_autoescape_neutralizes_injected_markup():
    # Defense in depth: HTML hiding in extracted data cannot inject into the report.
    content = {
        "name": "<script>alert(1)</script>",
        "headline": None, "summary": None,
        "contact": {"email": None, "phone": None, "location": None, "links": []},
        "experience": [], "projects": [], "skills": [], "education": [], "certifications": [],
    }
    html = _render_resume(content, [])
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
