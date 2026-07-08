"""Tests for the CLI — REQ-9 (commands + cram caching) and NFR-1 (model configurable)."""
from __future__ import annotations

import argparse

from app import cli, crammer, loader


def test_render_parser_flags_and_model_default():
    # NFR-1: --model exists and defaults to None (so env/gpt-4o-mini applies downstream).
    parser = cli.build_parser()
    args = parser.parse_args(["render", "--raw", "x.json", "--template", "resume", "--brand", "procom"])
    assert args.model is None
    assert args.dump is False

    args2 = parser.parse_args(
        ["render", "--raw", "x.json", "--template", "resume", "--brand", "procom",
         "--model", "gpt-4o", "--dump"]
    )
    assert args2.model == "gpt-4o"
    assert args2.dump is True


def test_list_command_prints_assets(capsys):
    # REQ-9: `list` surfaces templates and brands.
    rc = cli.cmd_list(argparse.Namespace())
    out = capsys.readouterr().out
    assert rc == 0
    assert "resume" in out
    assert "procom" in out


def test_render_all_crams_once_per_raw_template_then_reuses_across_brands(monkeypatch, tmp_path):
    # REQ-9: cram is cached per (raw x template); brands add renders, not API calls.
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "a.json").write_text('{"who": "A"}', encoding="utf-8")
    (raw_dir / "b.json").write_text('{"who": "B"}', encoding="utf-8")
    monkeypatch.setattr(loader, "RAW_DIR", raw_dir)

    calls = {"n": 0}

    def fake_cram(raw, template, model=None):
        calls["n"] += 1
        return {"content": {}, "sources": []}

    monkeypatch.setattr(crammer, "cram", fake_cram)

    out_dir = tmp_path / "out"
    rc = cli.cmd_render_all(
        argparse.Namespace(raw=None, limit=None, out_dir=str(out_dir), model=None)
    )
    assert rc == 0

    n_templates = len(loader.list_templates())  # 2
    n_brands = len(loader.list_brands())         # 2
    assert calls["n"] == 2 * n_templates                      # 2 records x templates, NOT x brands
    reports = [f for f in out_dir.glob("*.html") if f.name != "index.html"]
    assert len(reports) == 2 * n_templates * n_brands
    assert (out_dir / "index.html").is_file()
