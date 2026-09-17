"""Public API surface, typed errors, and prompt-file integration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import carbon_model_router as cmr
from carbon_model_router.errors import (
    CarbonRouterError,
    CatalogError,
    NoEligibleModelError,
)
from carbon_model_router.types import Catalog, ModelSpec


class TestExceptionHierarchy:
    def test_base(self):
        assert issubclass(CarbonRouterError, Exception)

    def test_catalog_error_is_valueerror(self):
        assert issubclass(CatalogError, ValueError)
        assert issubclass(CatalogError, CarbonRouterError)

    def test_no_eligible_is_valueerror(self):
        assert issubclass(NoEligibleModelError, ValueError)
        assert issubclass(NoEligibleModelError, CarbonRouterError)


class TestTypedRaise:
    def test_missing_catalog_file(self, tmp_path: Path):
        with pytest.raises(CatalogError) as exc_info:
            cmr.load_catalog_json(tmp_path / "missing.json")
        assert "not found" in str(exc_info.value)

    def test_empty_catalog_json(self, tmp_path: Path):
        path = tmp_path / "empty.json"
        path.write_text(json.dumps({"models": []}), encoding="utf-8")
        with pytest.raises(CatalogError, match="no models"):
            cmr.load_catalog_json(path)

    def test_duplicate_ids(self, tmp_path: Path):
        path = tmp_path / "dupes.json"
        entry = {
            "id": "m1",
            "name": "M1",
            "provider": "local",
            "cost_per_1k": 0.0,
            "energy_kwh_per_1k": 0.001,
            "capability": 0.5,
            "max_tokens": 1024,
        }
        path.write_text(json.dumps({"models": [entry, dict(entry)]}), encoding="utf-8")
        with pytest.raises(CatalogError, match="duplicate"):
            cmr.load_catalog_json(path)

    def test_invalid_json(self, tmp_path: Path):
        path = tmp_path / "bad.json"
        path.write_text("{not json", encoding="utf-8")
        with pytest.raises(CatalogError, match="not valid JSON"):
            cmr.load_catalog_json(path)

    def test_pick_smallest_empty(self):
        with pytest.raises(NoEligibleModelError):
            cmr.pick_smallest([])

    def test_route_empty_catalog(self):
        with pytest.raises(CatalogError, match="empty"):
            cmr.route_prompt("hello", Catalog(models=[]))

    def test_legacy_valueerror_catch(self, tmp_path: Path):
        try:
            cmr.pick_smallest([])
        except ValueError:
            pass
        else:
            raise AssertionError("expected ValueError-compatible error")


class TestPublicExports:
    def test_all_lists_core_api(self):
        for name in (
            "analyze_prompt",
            "default_catalog",
            "load_catalog_json",
            "route_prompt",
            "CarbonRouterError",
            "CatalogError",
            "NoEligibleModelError",
        ):
            assert name in cmr.__all__
            assert hasattr(cmr, name)


class TestPromptFileIntegration:
    @pytest.fixture
    def prompt_file(self, tmp_path: Path) -> Path:
        path = tmp_path / "prompts.txt"
        path.write_text(
            "What is the capital of France?\n"
            "---\n"
            "Summarize this in one sentence.\n"
            "---\n"
            "Design a distributed consensus protocol with Raft and prove safety.\n"
            "---\n"
            "```python\ndef add(a, b):\n    return a + b\n```\nWrite unit tests.\n",
            encoding="utf-8",
        )
        return path

    def test_route_every_prompt_in_file(self, prompt_file: Path):
        """Integration: batch-route a prompt list file end to end."""
        raw = prompt_file.read_text(encoding="utf-8")
        prompts = [p.strip() for p in raw.split("\n---\n") if p.strip()]
        assert len(prompts) == 4

        decisions = [cmr.route_prompt(p) for p in prompts]
        assert all(d.model.id for d in decisions)
        assert all(0.0 <= d.confidence <= 1.0 for d in decisions)
        assert all(d.estimated_tokens > 0 for d in decisions)

        # Simple prompts should not require frontier-class capability
        simple_required = decisions[0].complexity.required_capability
        complex_required = decisions[2].complexity.required_capability
        assert simple_required < complex_required

        # Complex consensus prompt should land on a stronger model than greetings
        assert (
            decisions[2].model.capability >= decisions[0].model.capability
        )

    def test_route_file_with_json_catalog(self, prompt_file: Path, tmp_path: Path):
        catalog_path = tmp_path / "catalog.json"
        catalog_path.write_text(
            json.dumps(
                {
                    "models": [
                        {
                            "id": "local-small",
                            "name": "Local Small",
                            "provider": "local",
                            "cost_per_1k": 0.0,
                            "energy_kwh_per_1k": 0.00002,
                            "capability": 0.55,
                            "max_tokens": 8192,
                        },
                        {
                            "id": "hosted-large",
                            "name": "Hosted Large",
                            "provider": "hosted",
                            "cost_per_1k": 0.01,
                            "energy_kwh_per_1k": 0.005,
                            "capability": 0.95,
                            "max_tokens": 65536,
                        },
                    ]
                }
            ),
            encoding="utf-8",
        )
        catalog = cmr.load_catalog_json(catalog_path)
        raw = prompt_file.read_text(encoding="utf-8")
        prompts = [p.strip() for p in raw.split("\n---\n") if p.strip()]
        decisions = [cmr.route_prompt(p, catalog) for p in prompts]
        ids = {d.model.id for d in decisions}
        assert ids <= {"local-small", "hosted-large"}

    def test_cli_route_file_via_stdin_or_arg(self, prompt_file: Path, capsys):
        from carbon_model_router.cli import EXIT_OK, main

        text = prompt_file.read_text(encoding="utf-8").split("\n---\n")[0].strip()
        code = main(["route", text, "--json"])
        assert code == EXIT_OK
        payload = json.loads(capsys.readouterr().out)
        assert "model" in payload
        assert payload["model"]["id"]
