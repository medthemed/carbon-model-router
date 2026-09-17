"""User catalog discovery, merge behavior, and --user CLI flag."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from carbon_model_router.cli import EXIT_OK, main
from carbon_model_router.config import (
    effective_catalog,
    load_user_catalog,
    merge_catalogs,
    user_catalog_path,
    user_config_dir,
)
from carbon_model_router.errors import CatalogError
from carbon_model_router.types import Catalog, ModelSpec


def _model(mid: str, capability: float = 0.5) -> ModelSpec:
    return ModelSpec(
        id=mid,
        name=mid.upper(),
        provider="local",
        cost_per_1k=0.001,
        energy_kwh_per_1k=0.0001,
        capability=capability,
        max_tokens=4096,
    )


@pytest.fixture
def user_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point user_config_dir at a temp directory."""
    directory = tmp_path / "cmr-config"
    directory.mkdir()
    monkeypatch.setattr(
        "carbon_model_router.config.user_config_dir", lambda: directory
    )
    return directory


class TestUserPaths:
    def test_config_dir_is_platform_path(self):
        d = user_config_dir()
        assert d.name == "cmr"

    def test_no_user_catalog_when_absent(self, user_dir: Path):
        assert user_catalog_path() is None
        assert load_user_catalog() is None

    def test_finds_catalog_json(self, user_dir: Path):
        path = user_dir / "catalog.json"
        path.write_text(
            json.dumps(
                {
                    "models": [
                        {
                            "id": "private-7b",
                            "name": "Private 7B",
                            "provider": "local",
                            "cost_per_1k": 0.0,
                            "energy_kwh_per_1k": 0.00005,
                            "capability": 0.7,
                            "max_tokens": 8192,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        assert user_catalog_path() == path
        catalog = load_user_catalog()
        assert catalog is not None
        assert catalog.by_id("private-7b") is not None

    def test_finds_cmr_toml(self, user_dir: Path):
        path = user_dir / "cmr.toml"
        path.write_text(
            """
[[models]]
id = "regional-3b"
name = "Regional 3B"
provider = "hosted"
cost_per_1k = 0.0002
energy_kwh_per_1k = 0.0002
capability = 0.55
max_tokens = 4096
""",
            encoding="utf-8",
        )
        catalog = load_user_catalog()
        assert catalog is not None
        model = catalog.by_id("regional-3b")
        assert model is not None
        assert model.capability == 0.55

    def test_invalid_user_catalog_raises(self, user_dir: Path):
        (user_dir / "catalog.json").write_text("{oops", encoding="utf-8")
        with pytest.raises(CatalogError, match="not valid JSON"):
            load_user_catalog()

    def test_empty_user_catalog_raises(self, user_dir: Path):
        (user_dir / "catalog.json").write_text(
            json.dumps({"models": []}), encoding="utf-8"
        )
        with pytest.raises(CatalogError, match="no models"):
            load_user_catalog()


class TestMergeCatalogs:
    def test_none_user_returns_base(self):
        base = Catalog(models=[_model("a"), _model("b")])
        merged = merge_catalogs(base, None)
        assert [m.id for m in merged] == ["a", "b"]

    def test_new_models_appended(self):
        base = Catalog(models=[_model("a")])
        user = Catalog(models=[_model("z", capability=0.9)])
        merged = merge_catalogs(base, user)
        assert [m.id for m in merged] == ["a", "z"]

    def test_same_id_overrides(self):
        base = Catalog(models=[_model("small-8b", capability=0.45)])
        user = Catalog(models=[_model("small-8b", capability=0.60)])
        merged = merge_catalogs(base, user)
        assert len(merged) == 1
        assert merged.by_id("small-8b").capability == 0.60

    def test_effective_catalog_includes_user(self, user_dir: Path):
        (user_dir / "catalog.json").write_text(
            json.dumps(
                {
                    "models": [
                        {
                            "id": "team-frontier",
                            "name": "Team Frontier",
                            "provider": "hosted",
                            "cost_per_1k": 0.02,
                            "energy_kwh_per_1k": 0.005,
                            "capability": 0.99,
                            "max_tokens": 200000,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        merged = effective_catalog()
        assert merged.by_id("team-frontier") is not None
        # built-ins still present
        assert merged.by_id("small-8b") is not None
        assert len(merged) > len(load_user_catalog())


class TestCliUserFlag:
    def test_catalog_without_user_shows_builtin(self, user_dir: Path, capsys):
        code = main(["catalog"])
        assert code == EXIT_OK
        out = capsys.readouterr().out
        assert "small-8b" in out
        assert "team-frontier" not in out

    def test_catalog_user_without_config(self, user_dir: Path, capsys):
        code = main(["catalog", "--user"])
        assert code == EXIT_OK
        captured = capsys.readouterr()
        assert "no user catalog found" in captured.err
        assert "small-8b" in captured.out

    def test_catalog_user_merges_models(self, user_dir: Path, capsys):
        (user_dir / "catalog.json").write_text(
            json.dumps(
                {
                    "models": [
                        {
                            "id": "team-local",
                            "name": "Team Local",
                            "provider": "local",
                            "cost_per_1k": 0.0,
                            "energy_kwh_per_1k": 0.00001,
                            "capability": 0.5,
                            "max_tokens": 4096,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        code = main(["catalog", "--user", "--json"])
        assert code == EXIT_OK
        captured = capsys.readouterr()
        assert "user catalog" in captured.err
        payload = json.loads(captured.out)
        ids = {m["id"] for m in payload["models"]}
        assert "team-local" in ids
        assert "small-8b" in ids

    def test_route_user_uses_merged_catalog(self, user_dir: Path, capsys):
        (user_dir / "catalog.json").write_text(
            json.dumps(
                {
                    "models": [
                        {
                            "id": "only-user-model",
                            "name": "Only User",
                            "provider": "local",
                            "cost_per_1k": 0.0,
                            "energy_kwh_per_1k": 0.00001,
                            "capability": 0.40,
                            "max_tokens": 8192,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        # Without --user, built-in catalog is used
        assert main(["route", "hi", "--json"]) == EXIT_OK
        payload = json.loads(capsys.readouterr().out)
        assert payload["model"]["id"] != "only-user-model"
