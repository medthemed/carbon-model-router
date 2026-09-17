"""Built-in model catalog and loaders."""

from __future__ import annotations

import json
from pathlib import Path

from carbon_model_router.types import Catalog, ModelSpec

# Numbers are illustrative order-of-magnitude estimates for routing demos.
# They are NOT live pricing. Update as your fleet changes.
DEFAULT_MODELS: tuple[ModelSpec, ...] = (
    ModelSpec(
        id="nano-classifier",
        name="Nano Classifier",
        provider="local",
        cost_per_1k=0.0,
        energy_kwh_per_1k=0.00001,
        capability=0.25,
        max_tokens=512,
        notes="Ultra-cheap intent/label routing.",
    ),
    ModelSpec(
        id="small-8b",
        name="Small 8B Instruct",
        provider="local",
        cost_per_1k=0.00005,
        energy_kwh_per_1k=0.00008,
        capability=0.45,
        max_tokens=4096,
        notes="Good for short rewrites, summaries, simple Q&A.",
    ),
    ModelSpec(
        id="medium-32b",
        name="Medium 32B Instruct",
        provider="hosted",
        cost_per_1k=0.0004,
        energy_kwh_per_1k=0.00035,
        capability=0.65,
        max_tokens=8192,
        notes="Solid generalist for multi-step writing and light code.",
    ),
    ModelSpec(
        id="large-70b",
        name="Large 70B Instruct",
        provider="hosted",
        cost_per_1k=0.0012,
        energy_kwh_per_1k=0.0009,
        capability=0.80,
        max_tokens=16384,
        notes="Strong reasoning and non-trivial code.",
    ),
    ModelSpec(
        id="frontier-x",
        name="Frontier X",
        provider="hosted",
        cost_per_1k=0.015,
        energy_kwh_per_1k=0.0045,
        capability=0.97,
        max_tokens=128000,
        notes="Reserve for hard research, long-context, novel design.",
    ),
)


def default_catalog() -> Catalog:
    return Catalog(models=list(DEFAULT_MODELS))


def load_catalog_json(path: str | Path) -> Catalog:
    """Load a catalog from a JSON file: {"models": [ModelSpec dicts]}."""
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        raw_models = data.get("models", [])
    else:
        raw_models = data
    models = [ModelSpec(**item) for item in raw_models]
    if not models:
        raise ValueError(f"catalog file has no models: {p}")
    _validate_unique_ids(models)
    return Catalog(models=models)


def _validate_unique_ids(models: list[ModelSpec]) -> None:
    seen: set[str] = set()
    for m in models:
        if m.id in seen:
            raise ValueError(f"duplicate model id: {m.id}")
        seen.add(m.id)


def catalog_from_models(models: list[ModelSpec]) -> Catalog:
    _validate_unique_ids(models)
    return Catalog(models=list(models))


__all__ = [
    "DEFAULT_MODELS",
    "catalog_from_models",
    "default_catalog",
    "load_catalog_json",
]
