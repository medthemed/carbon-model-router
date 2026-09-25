"""Interop tests: --format json|text and JSON Schema contracts."""

from __future__ import annotations

import json
from pathlib import Path

from carbon_model_router.cli import EXIT_OK, main
from tests.conftest import COMPLEX_PROMPT, SIMPLE_PROMPT

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"


def _load_schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def _validate_required_keys(payload: dict, schema: dict) -> None:
    for key in schema.get("required", []):
        assert key in payload, f"missing required key: {key}"
    props = schema.get("properties", {})
    for key, spec in props.items():
        if key not in payload:
            continue
        expected = spec.get("type")
        if expected is None:
            continue
        types = expected if isinstance(expected, list) else [expected]
        if "null" in types and payload[key] is None:
            continue
        type_map = {
            "object": dict,
            "array": list,
            "string": str,
            "boolean": bool,
            "integer": int,
            "number": (int, float),
        }
        ok = any(isinstance(payload[key], type_map[t]) for t in types if t in type_map)
        assert ok, f"{key}: expected {types}, got {type(payload[key])}"


def test_cli_route_format_text_default(capsys):
    code = main(["route", SIMPLE_PROMPT])
    assert code == EXIT_OK
    out = capsys.readouterr().out
    assert "model:" in out


def test_cli_route_format_json(capsys):
    code = main(["route", SIMPLE_PROMPT, "--format", "json"])
    assert code == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    schema = _load_schema("route-decision.schema.json")
    _validate_required_keys(payload, schema)
    assert payload["model"]["id"]
    assert 0 <= payload["confidence"] <= 1


def test_cli_route_json_shorthand(capsys):
    code = main(["route", SIMPLE_PROMPT, "--json"])
    assert code == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert "model" in payload


def test_cli_route_file_format_json(tmp_path: Path, capsys):
    p = tmp_path / "prompts.txt"
    p.write_text(f"{SIMPLE_PROMPT}\n---\n{COMPLEX_PROMPT}\n", encoding="utf-8")
    code = main(["route-file", str(p), "--format", "json"])
    assert code == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    schema = _load_schema("batch-report.schema.json")
    _validate_required_keys(payload, schema)
    assert payload["summary"]["prompt_count"] == 2
    for item in payload["items"]:
        assert "model_id" in item
        assert "saved_cost" in item


def test_cli_route_file_format_text(tmp_path: Path, capsys):
    p = tmp_path / "prompts.txt"
    p.write_text("hello there friend\n", encoding="utf-8")
    code = main(["route-file", str(p), "--format", "text"])
    assert code == EXIT_OK
    out = capsys.readouterr().out
    assert "batch report" in out


def test_decision_schema_matches_to_dict(capsys):
    code = main(["route", COMPLEX_PROMPT, "--format", "json"])
    assert code == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    schema = _load_schema("route-decision.schema.json")
    _validate_required_keys(payload, schema)
    assert payload["model"]["capability"] >= 0.5
    assert "estimated_tokens" in payload
    assert "estimated_cost" in payload


def test_schema_files_exist():
    assert (SCHEMA_DIR / "route-decision.schema.json").is_file()
    assert (SCHEMA_DIR / "batch-report.schema.json").is_file()
    decision_schema = _load_schema("route-decision.schema.json")
    assert "model" in decision_schema["properties"]
    batch_schema = _load_schema("batch-report.schema.json")
    assert "summary" in batch_schema["properties"]


def test_stdout_contract_json_only_on_stdout(tmp_path: Path, capsys):
    """JSON format writes parseable JSON to stdout; errors stay on stderr."""
    p = tmp_path / "prompts.txt"
    p.write_text(f"{SIMPLE_PROMPT}\n---\nyo\n", encoding="utf-8")
    code = main(["route-file", str(p), "--format", "json"])
    assert code == EXIT_OK
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["summary"]["prompt_count"] == 2
    # stdout should be pure JSON (no banner lines)
    assert captured.out.lstrip().startswith("{")
