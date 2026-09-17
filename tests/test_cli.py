"""CLI tests for carbon-model-router."""

from __future__ import annotations

import json
from pathlib import Path

from carbon_model_router.cli import EXIT_OK, main
from tests.conftest import COMPLEX_PROMPT, SIMPLE_PROMPT


def test_cli_version(capsys):
    code = main(["version"])
    assert code == EXIT_OK
    assert "carbon-model-router" in capsys.readouterr().out


def test_cli_route_simple(capsys):
    code = main(["route", SIMPLE_PROMPT])
    assert code == EXIT_OK
    out = capsys.readouterr().out
    assert "model:" in out
    assert "rationale:" in out


def test_cli_route_json(capsys):
    code = main(["route", SIMPLE_PROMPT, "--json"])
    assert code == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["model"]["id"]
    assert "complexity" in payload


def test_cli_route_complex_picks_capable_model(capsys):
    code = main(["route", COMPLEX_PROMPT, "--json"])
    assert code == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["model"]["capability"] >= 0.75


def test_cli_catalog_lists_models(capsys):
    code = main(["catalog"])
    assert code == EXIT_OK
    out = capsys.readouterr().out
    assert "frontier-x" in out
    assert "small-8b" in out


def test_cli_catalog_json(capsys):
    code = main(["catalog", "--json"])
    assert code == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["models"]) >= 4


def test_cli_analyze(capsys):
    code = main(["analyze", COMPLEX_PROMPT])
    assert code == EXIT_OK
    out = capsys.readouterr().out
    assert "complexity:" in out
    assert "required_capability:" in out


def test_cli_route_from_file(tmp_path: Path, capsys):
    p = tmp_path / "prompt.txt"
    p.write_text(SIMPLE_PROMPT, encoding="utf-8")
    code = main(["route", "-f", str(p), "--json"])
    assert code == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["model"]["id"]


def test_cli_carbon_flag(capsys):
    code = main(["route", "hello there", "--carbon", "--json"])
    assert code == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["carbon_weighted"] is True


def test_cli_show_rejected(capsys):
    code = main(["route", SIMPLE_PROMPT, "--show-rejected", "--json"])
    assert code == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert "rejected" in payload
    assert len(payload["rejected"]) >= 1


def test_cli_custom_catalog(tmp_path: Path, capsys):
    cat = tmp_path / "cat.json"
    cat.write_text(
        json.dumps(
            {
                "models": [
                    {
                        "id": "only",
                        "name": "Only",
                        "provider": "local",
                        "cost_per_1k": 0.0,
                        "energy_kwh_per_1k": 0.0001,
                        "capability": 0.9,
                        "max_tokens": 8192,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    code = main(["route", SIMPLE_PROMPT, "--catalog", str(cat), "--json"])
    assert code == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["model"]["id"] == "only"
