"""Tests for the router."""

from __future__ import annotations

from carbon_model_router.router import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    confidence_for,
    eligible_models,
    pick_smallest,
    route_prompt,
)
from carbon_model_router.types import ComplexityScore, ModelSpec
from tests.conftest import COMPLEX_PROMPT, SIMPLE_PROMPT


def test_simple_prompt_routes_to_small_model(catalog):
    decision = route_prompt(SIMPLE_PROMPT, catalog)
    assert decision.model.capability <= 0.50
    assert decision.model.id in {"nano-classifier", "small-8b"}
    assert decision.confidence >= DEFAULT_CONFIDENCE_THRESHOLD


def test_complex_prompt_routes_to_larger_model(catalog):
    decision = route_prompt(COMPLEX_PROMPT, catalog)
    assert decision.model.capability >= 0.75
    assert decision.model.id in {"large-70b", "frontier-x"}


def test_router_prefers_smaller_among_eligible(catalog):
    simple = route_prompt(SIMPLE_PROMPT, catalog)
    complex_ = route_prompt(COMPLEX_PROMPT, catalog)
    assert simple.model.capability < complex_.model.capability
    assert simple.estimated_cost <= complex_.estimated_cost


def test_threshold_forces_stronger_model(catalog):
    # Very high confidence threshold should skip barely-capable models
    decision = route_prompt(
        "Write a short greeting.",
        catalog,
        confidence_threshold=0.95,
    )
    assert decision.confidence >= 0.95
    # nano (0.25) and small-8b (0.45) rejected on confidence; medium-32b (0.65) selected
    assert decision.model.capability >= 0.60
    assert decision.model.id in {"medium-32b", "large-70b", "frontier-x"}


def test_threshold_zero_still_meets_capability(catalog):
    decision = route_prompt(
        COMPLEX_PROMPT,
        catalog,
        confidence_threshold=0.0,
    )
    assert decision.model.capability >= decision.complexity.required_capability


def test_carbon_mode_selects_low_energy(catalog):
    # Construct a case where two models are eligible; carbon should pick lower kWh
    forced = ComplexityScore(score=0.3, required_capability=0.40)
    decision = route_prompt(
        "hello",
        catalog,
        carbon_weighted=True,
        complexity=forced,
    )
    assert decision.carbon_weighted is True
    eligible = eligible_models(catalog, 0.40, DEFAULT_CONFIDENCE_THRESHOLD, 10)
    min_energy = min(m.energy_kwh_per_1k for m, _ in eligible)
    assert decision.model.energy_kwh_per_1k == min_energy


def test_confidence_zero_below_capability():
    m = ModelSpec(
        id="weak",
        name="Weak",
        provider="x",
        cost_per_1k=0.0,
        energy_kwh_per_1k=0.0,
        capability=0.30,
        max_tokens=1000,
    )
    assert confidence_for(m, 0.50) == 0.0


def test_confidence_increases_with_surplus():
    low = ModelSpec(
        id="a",
        name="A",
        provider="x",
        cost_per_1k=0.0,
        energy_kwh_per_1k=0.0,
        capability=0.50,
        max_tokens=1000,
    )
    high = ModelSpec(
        id="b",
        name="B",
        provider="x",
        cost_per_1k=0.0,
        energy_kwh_per_1k=0.0,
        capability=0.95,
        max_tokens=1000,
    )
    assert confidence_for(high, 0.40) > confidence_for(low, 0.40)


def test_pick_smallest_orders_by_capability(tiny_catalog):
    candidates = [(m, 0.9) for m in tiny_catalog]
    model, _ = pick_smallest(candidates, carbon_weighted=False)
    assert model.id == "tiny"


def test_pick_smallest_carbon_orders_by_energy(tiny_catalog):
    candidates = [(m, 0.9) for m in tiny_catalog]
    model, _ = pick_smallest(candidates, carbon_weighted=True)
    assert model.id == "tiny"  # also lowest energy in this fixture


def test_long_prompt_respects_max_tokens(catalog):
    huge = "word " * 20000  # ~100k chars → ~25k tokens
    decision = route_prompt(huge, catalog, confidence_threshold=0.0)
    # nano/small have low max_tokens and should be rejected on window size
    assert decision.model.max_tokens >= decision.estimated_tokens * 0.5


def test_empty_catalog_raises():
    from carbon_model_router.types import Catalog

    try:
        route_prompt("hi", Catalog(models=[]))
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_decision_to_dict_shape(catalog):
    decision = route_prompt(SIMPLE_PROMPT, catalog)
    payload = decision.to_dict()
    assert payload["model"]["id"]
    assert "complexity" in payload
    assert "rationale" in payload
    assert 0.0 <= payload["confidence"] <= 1.0


def test_rejected_list_populated(catalog):
    decision = route_prompt(SIMPLE_PROMPT, catalog)
    assert any("capability" in r or "confidence" in r for r in decision.rejected)


def test_deterministic_routing(catalog):
    a = route_prompt(COMPLEX_PROMPT, catalog)
    b = route_prompt(COMPLEX_PROMPT, catalog)
    assert a.model.id == b.model.id
    assert a.confidence == b.confidence
