"""carbon-model-router: route prompts to the smallest capable LLM.

Public API:
    analyze_prompt, default_catalog, load_catalog_json, parse_prompt_file,
    route_prompt, route_prompts, summarize_savings
"""

from __future__ import annotations

from carbon_model_router.analyzer import VALID_DOMAINS, analyze_prompt, estimate_tokens
from carbon_model_router.batch import (
    BatchRouteItem,
    BatchRouteReport,
    SavingsSummary,
    parse_prompt_file,
    parse_prompt_text,
    route_prompts,
    summarize_savings,
)
from carbon_model_router.catalog import DEFAULT_MODELS, default_catalog, load_catalog_json
from carbon_model_router.config import (
    effective_catalog,
    load_user_catalog,
    merge_catalogs,
    user_catalog_path,
)
from carbon_model_router.errors import (
    CarbonRouterError,
    CatalogError,
    NoEligibleModelError,
)
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

__version__ = "0.3.0"

__all__ = [
    "DEFAULT_CONFIDENCE_THRESHOLD",
    "DEFAULT_MODELS",
    "VALID_DOMAINS",
    "BatchRouteItem",
    "BatchRouteReport",
    "CarbonRouterError",
    "Catalog",
    "CatalogError",
    "ComplexityScore",
    "ModelSpec",
    "NoEligibleModelError",
    "RouteDecision",
    "SavingsSummary",
    "__version__",
    "analyze_prompt",
    "confidence_for",
    "default_catalog",
    "effective_catalog",
    "eligible_models",
    "estimate_tokens",
    "load_catalog_json",
    "load_user_catalog",
    "merge_catalogs",
    "parse_prompt_file",
    "parse_prompt_text",
    "pick_smallest",
    "route_prompt",
    "route_prompts",
    "summarize_savings",
    "user_catalog_path",
]
