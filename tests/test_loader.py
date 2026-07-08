"""Tests for the asset loader — REQ-1 (raw), REQ-2 (templates), REQ-3 (brands)."""
from __future__ import annotations

import pytest

from app import loader
from conftest import FIXTURES


def test_list_templates_and_brands_present():
    # REQ-2 / REQ-3: the two templates and two brands are discoverable as assets.
    assert "resume" in loader.list_templates()
    assert "work_profile" in loader.list_templates()
    assert "procom" in loader.list_brands()
    assert "conspro" in loader.list_brands()


def test_load_template_exposes_schema_guidance_and_file():
    # REQ-2: a template = field schema + Jinja HTML + extraction guidance.
    tmpl = loader.load_template("resume")
    assert tmpl.schema["type"] == "object"
    assert "experience" in tmpl.schema["properties"]
    assert tmpl.guidance.strip()  # non-empty extraction guidance
    assert tmpl.template_file == "resume/template.html.j2"


def test_load_template_accepts_hyphenated_name():
    # REQ-2: `work-profile` and `work_profile` both resolve.
    assert loader.load_template("work-profile").name == "work_profile"


def test_load_brand_has_tokens_and_chrome():
    # REQ-3: a brand = visual tokens + chrome text.
    brand = loader.load_brand("procom")
    assert brand.tokens["primary_color"].startswith("#")
    assert brand.tokens["body_font"]
    assert brand.tagline
    assert brand.footer_text


def test_load_raw_reads_arbitrary_json():
    # REQ-1: load arbitrary raw JSON; keep verbatim text + parsed data.
    raw = loader.load_raw(FIXTURES / "raw_min.json")
    assert raw.name == "raw_min"
    assert "Dana Reed" in raw.text
    assert isinstance(raw.data, dict)


def test_list_raw_empty_when_dir_absent(tmp_path):
    # REQ-1: listing a missing raw dir yields no files (not an error).
    assert loader.list_raw(tmp_path / "nope") == []


def test_load_unknown_template_raises():
    with pytest.raises(FileNotFoundError):
        loader.load_template("does-not-exist")
