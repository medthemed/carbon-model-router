"""Batch route-file tests: parsing, savings summary, CLI."""

from __future__ import annotations

import json
from pathlib import Path

from carbon_model_router.batch import (
    frontier_model,
    parse_prompt_file,
    parse_prompt_text,
    route_prompts,
    summarize_savings,
)
from carbon_model_router.cli import EXIT_ERROR, EXIT_OK, main
from carbon_model_router.catalog import default_catalog
from tests.conftest import COMPLEX_PROMPT, SIMPLE_PROMPT


def test_parse_prompt_text_separators():
    text = "first prompt\n---\n\nsecond prompt\n---\nthird"
    prompts = parse_prompt_text(text)
    assert prompts == ["first prompt", "second prompt", "third"]


def test_parse_prompt_text_no_separator_is_single():
    assert parse_prompt_text("just one prompt\n") == ["just one prompt"]


def test_parse_prompt_text_skips_empty_chunks():
    assert parse_prompt_text("---\n\n---\nreal\n---\n") == ["real"]


def test_parse_prompt_file(tmp_path: Path):
    p = tmp_path / "prompts.txt"
    p.write_text(f"{SIMPLE_PROMPT}\n---\n{COMPLEX_PROMPT}\n", encoding="utf-8")
    prompts = parse_prompt_file(p)
    assert len(prompts) == 2
    assert prompts[0] == SIMPLE_PROMPT


def test_route_prompts_summary_savings(catalog):
    prompts = [SIMPLE_PROMPT, "hi", COMPLEX_PROMPT]
    report = route_prompts(prompts, catalog)
    assert len(report.items) == 3
    assert report.summary is not None
    assert report.summary.prompt_count == 3
    default = frontier_model(catalog)
    assert report.summary.default_model_id == default.id
    # Simple prompts should save money vs frontier
    assert report.summary.saved_cost > 0
    assert report.summary.saved_energy_kwh > 0
    assert 0 < report.summary.saved_cost_pct <= 100


def test_route_prompts_simple_uses_smaller_model(catalog):
    report = route_prompts([SIMPLE_PROMPT], catalog)
    item = report.items[0]
    frontier = frontier_model(catalog)
    assert item.decision.model.capability < frontier.capability
    assert item.default_model_id == frontier.id
    assert item.saved_cost > 0


def test_route_prompts_pure_deterministic(catalog):
    prompts = [SIMPLE_PROMPT, COMPLEX_PROMPT]
    a = route_prompts(prompts, catalog)
    b = route_prompts(prompts, catalog)
    assert [i.decision.model.id for i in a.items] == [
        i.decision.model.id for i in b.items
    ]
    assert a.summary.to_dict() == b.summary.to_dict()


def test_summarize_savings_empty():
    summary = summarize_savings([], default_model_id="frontier-x")
    assert summary.prompt_count == 0
    assert summary.saved_cost == 0
    assert summary.saved_cost_pct == 0


def test_cli_route_file_text(tmp_path: Path, capsys):
    p = tmp_path / "prompts.txt"
    p.write_text(f"{SIMPLE_PROMPT}\n---\n{COMPLEX_PROMPT}\n", encoding="utf-8")
    code = main(["route-file", str(p)])
    assert code == EXIT_OK
    out = capsys.readouterr().out
    assert "batch report" in out
    assert "savings vs default" in out
    assert "saved cost" in out


def test_cli_route_file_json(tmp_path: Path, capsys):
    p = tmp_path / "prompts.txt"
    p.write_text(f"{SIMPLE_PROMPT}\n---\nhi there\n", encoding="utf-8")
    code = main(["route-file", str(p), "--json"])
    assert code == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["items"]) == 2
    assert payload["summary"]["prompt_count"] == 2
    assert payload["summary"]["default_model_id"]
    assert payload["summary"]["saved_cost"] >= 0
    for item in payload["items"]:
        assert "model_id" in item
        assert "saved_cost" in item


def test_cli_route_file_example_list(capsys):
    example = Path(__file__).resolve().parent.parent / "examples" / "prompt-list.txt"
    if not example.is_file():
        return
    code = main(["route-file", str(example), "--json"])
    assert code == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["prompt_count"] >= 3


def test_cli_route_file_missing(tmp_path: Path, capsys):
    code = main(["route-file", str(tmp_path / "nope.txt")])
    assert code == EXIT_ERROR
    err = capsys.readouterr().err
    assert "not found" in err


def test_cli_route_file_empty(tmp_path: Path, capsys):
    p = tmp_path / "empty.txt"
    p.write_text("\n\n", encoding="utf-8")
    code = main(["route-file", str(p)])
    assert code == EXIT_ERROR
    assert "no prompts" in capsys.readouterr().err


def test_cli_route_file_carbon(tmp_path: Path, capsys):
    p = tmp_path / "prompts.txt"
    p.write_text("hello world\n", encoding="utf-8")
    code = main(["route-file", str(p), "--carbon", "--json"])
    assert code == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["prompt_count"] == 1
