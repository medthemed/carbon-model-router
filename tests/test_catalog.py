"""Tests for the model catalog."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from carbon_model_router.catalog import (
    DEFAULT_MODELS,
    catalog_from_models,
    default_catalog,
    load_catalog_json,
)
from carbon_model_router.types import ModelSpec


def test_default_catalog_not_empty():
    cat = default_catalog()
    assert len(cat) >= 4
    assert cat.by_id("frontier-x") is not None


def test_catalog_integrity_unique_ids():
    ids = [m.id for m in DEFAULT_MODELS]
    assert len(ids) == len(set(ids))


def test_catalog_integrity_ordering_fields():
    for m in DEFAULT_MODELS:
        assert m.cost_per_1k >= 0
        assert m.energy_kwh_per_1k >= 0
        assert 0.0 <= m.capability <= 1.0
        assert m.max_tokens > 0


def test_capability_monotonic_with_cost_in_default():
    """Cheaper models should not claim higher capability than frontier."""
    by_cap = default_catalog().sorted_by_capability()
    caps = [m.capability for m in by_cap]
    assert caps == sorted(caps)


def test_model_spec_validation_rejects_bad_capability():
    with pytest.raises(ValueError):
        ModelSpec(
            id="bad",
            name="Bad",
            provider="x",
            cost_per_1k=0.1,
            energy_kwh_per_1k=0.1,
            capability=1.5,
            max_tokens=100,
        )


def test_model_spec_validation_rejects_negative_cost():
    with pytest.raises(ValueError):
        ModelSpec(
            id="bad",
            name="Bad",
            provider="x",
            cost_per_1k=-0.1,
            energy_kwh_per_1k=0.1,
            capability=0.5,
            max_tokens=100,
        )


def test_load_catalog_json_roundtrip(tmp_path: Path):
    path = tmp_path / "cat.json"
    payload = {
        "models": [
            {
                "id": "a",
                "name": "A",
                "provider": "local",
                "cost_per_1k": 0.001,
                "energy_kwh_per_1k": 0.0001,
                "capability": 0.5,
                "max_tokens": 4096,
            },
            {
                "id": "b",
                "name": "B",
                "provider": "hosted",
                "cost_per_1k": 0.01,
                "energy_kwh_per_1k": 0.001,
                "capability": 0.9,
                "max_tokens": 16384,
            },
        ]
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    cat = load_catalog_json(path)
    assert len(cat) == 2
    assert cat.by_id("a") is not None


def test_duplicate_ids_rejected():
    m = ModelSpec(
        id="dup",
        name="Dup",
        provider="x",
        cost_per_1k=0.0,
        energy_kwh_per_1k=0.0,
        capability=0.3,
        max_tokens=100,
    )
    with pytest.raises(ValueError):
        catalog_from_models([m, m])


def test_sorted_helpers(catalog):
    by_cost = catalog.sorted_by_cost()
    costs = [m.cost_per_1k for m in by_cost]
    assert costs == sorted(costs)
    by_energy = catalog.sorted_by_energy()
    energies = [m.energy_kwh_per_1k for m in by_energy]
    assert energies == sorted(energies)
