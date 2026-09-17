"""carbon-model-router: route prompts to the smallest capable LLM.

Public API:
    analyze_prompt, default_catalog, route_prompt
"""

from __future__ import annotations

from carbon_model_router.analyzer import analyze_prompt, estimate_tokens
from carbon_model_router.catalog import DEFAULT_MODELS, default_catalog, load_catalog_json
from carbon_model_router.router import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    confidence_for,
    eligible_models,
    pick_smallest,
    route_prompt,
)
from carbon_model_router.types import (
    Catalog,
    ComplexityScore,
    ModelSpec,
    RouteDecision,
)

__version__ = "0.1.0"

__all__ = [
    "DEFAULT_CONFIDENCE_THRESHOLD",
    "DEFAULT_MODELS",
    "Catalog",
    "ComplexityScore",
    "ModelSpec",
    "RouteDecision",
    "__version__",
    "analyze_prompt",
    "confidence_for",
    "default_catalog",
    "eligible_models",
    "estimate_tokens",
    "load_catalog_json",
    "pick_smallest",
    "route_prompt",
]
