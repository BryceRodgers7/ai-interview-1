"""Shared test fixtures + an offline stub OpenAI client (NFR-2).

The stub mimics the shape the crammer relies on:
``client.chat.completions.create(...) -> resp.choices[0].message.{content, refusal}``
and records every call's kwargs so tests can assert on them.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


class _StubCompletions:
    def __init__(self, owner):
        self._owner = owner

    def create(self, **kwargs):
        self._owner.calls.append(kwargs)
        message = SimpleNamespace(content=self._owner._content, refusal=self._owner._refusal)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class StubClient:
    """Drop-in stand-in for openai.OpenAI used in offline unit tests."""

    def __init__(self, payload=None, *, content=None, refusal=None):
        if content is None and payload is not None:
            content = json.dumps(payload)
        self._content = content
        self._refusal = refusal
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=_StubCompletions(self))


@pytest.fixture
def make_client():
    """Factory: build a StubClient returning a fixed payload (or a refusal)."""
    def _make(payload=None, *, content=None, refusal=None):
        return StubClient(payload, content=content, refusal=refusal)
    return _make


@pytest.fixture
def resume_content():
    # Note: phone is null -> exercises blank rendering (REQ-5); certs carry status incl. Expired.
    return {
        "name": "Dana Reed",
        "headline": "Senior Software Engineer",
        "summary": "Builds reliable backend services.",
        "contact": {
            "email": "dana@example.com",
            "phone": None,
            "location": "Austin, TX",
            "links": ["github.com/danareed"],
        },
        "experience": [
            {
                "company": "Acme",
                "title": "Senior Engineer",
                "start": "2021",
                "end": "Present",
                "highlights": ["Led the billing rewrite", "Cut p95 latency 40%"],
            }
        ],
        "projects": [
            {
                "name": "Billing Rewrite",
                "role": "Lead",
                "impact": "Cut release friction",
                "technologies": ["Python", "Postgres"],
            }
        ],
        "skills": ["Python", "Go", "PostgreSQL"],
        "education": [{"school": "UT Austin", "degree": "BS Computer Science", "year": "2015"}],
        "certifications": [
            {"name": "AWS Certified Developer", "status": "Active"},
            {"name": "CKA", "status": "Expired"},
        ],
    }


@pytest.fixture
def resume_sources():
    return [
        {"field": "name", "evidence": "Dana Reed"},
        {"field": "skills[0]", "evidence": "strong Python background"},
    ]


@pytest.fixture
def work_profile_content():
    return {
        "name": "Dana Reed",
        "current_role": {"title": "Support Engineer", "department": "IT Services", "tenure": "3 years"},
        "summary": "Reliable support engineer with deep ticketing experience.",
        "skills": [
            {"name": "Ticketing", "group": "primary", "level": "Expert"},
            {"name": "Networking", "group": "secondary", "level": None},
        ],
        "experience": [
            {
                "organization": "ConsPro",
                "role": "Support Engineer",
                "start": "2021",
                "end": "Present",
                "highlights": ["Resolved 2,000+ tickets"],
            }
        ],
        "projects": [
            {
                "name": "Helpdesk Migration",
                "role": "Owner",
                "impact": "Cut resolution time",
                "technologies": ["Zendesk"],
            }
        ],
        "certifications": [{"name": "CompTIA A+", "status": "Active"}],
        "internal": {
            "availability": "Open to new projects",
            "promotion_readiness": "Ready in 6-12 months",
            "performance_rating": "4.1",
            "manager": "Dana Walsh",
            "interests": ["Cloud"],
            "notes": "Strong cross-functional candidate.",
        },
    }
