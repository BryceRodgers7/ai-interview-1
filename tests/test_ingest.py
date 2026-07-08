"""Tests for record ingestion and messy-data robustness — REQ-11, REQ-12."""
from __future__ import annotations

import json

from app import loader


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_unwraps_people_bundle(tmp_path):
    # REQ-11: a {..., people:[...]} bundle yields one record per person.
    bundle = {"datasetName": "x", "brands": [], "people": [
        {"personId": "a", "profile": {}}, {"personId": "b", "profile": {}}]}
    _write(tmp_path, "bundle.json", json.dumps(bundle))
    records, issues = loader.load_records("bundle.json", raw_dir=tmp_path)
    assert [r.id for r in records] == ["a", "b"]
    assert issues == []


def test_bare_array_skips_non_objects(tmp_path):
    # REQ-12: non-object items are skipped and reported, not fatal.
    _write(tmp_path, "arr.json", json.dumps([{"id": "a"}, "junk", {"id": "b"}]))
    records, issues = loader.load_records("arr.json", raw_dir=tmp_path)
    assert [r.id for r in records] == ["a", "b"]
    assert len(issues) == 1 and "non-object" in issues[0].reason


def test_single_object_is_one_record(tmp_path):
    _write(tmp_path, "one.json", json.dumps({"personId": "solo", "profile": {}}))
    records, issues = loader.load_records("one.json", raw_dir=tmp_path)
    assert len(records) == 1 and records[0].id == "solo"


def test_ndjson_skips_bad_lines(tmp_path):
    # REQ-11 (NDJSON) + REQ-12 (malformed lines & non-objects skipped, reported).
    _write(tmp_path, "d.ndjson", '{"id":"ok1"}\n{broken\n\n42\n{"id":"ok2"}\n')
    records, issues = loader.load_records("d.ndjson", raw_dir=tmp_path)
    assert [r.id for r in records] == ["ok1", "ok2"]
    assert len(issues) == 2  # the broken line and the bare int


def test_missing_id_is_synthesized(tmp_path):
    # REQ-11: records without a recognizable id still get a stable id.
    _write(tmp_path, "noid.json", json.dumps([{"profile": {"name": "A"}}, {"profile": {}}]))
    records, _ = loader.load_records("noid.json", raw_dir=tmp_path)
    assert records[0].id == "noid#0" and records[1].id == "noid#1"


def test_json_extension_falls_back_to_ndjson(tmp_path):
    # REQ-12: a .json file that is actually NDJSON is parsed rather than failing outright.
    _write(tmp_path, "mislabeled.json", '{"id":"a"}\n{"id":"b"}\n')
    records, issues = loader.load_records("mislabeled.json", raw_dir=tmp_path)
    assert [r.id for r in records] == ["a", "b"]
    assert any("NDJSON" in i.reason for i in issues)


def test_record_text_is_serialized_json(tmp_path):
    # The record's untrusted-source text is the serialized record (fed to the crammer).
    _write(tmp_path, "one.json", json.dumps({"personId": "solo", "k": "v"}))
    records, _ = loader.load_records("one.json", raw_dir=tmp_path)
    assert json.loads(records[0].text)["k"] == "v"
