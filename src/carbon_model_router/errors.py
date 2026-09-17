"""Typed exceptions for carbon-model-router.

Callers can catch ``CarbonRouterError`` for any routing failure, or a more
specific subclass. Typed errors also inherit ``ValueError`` so existing
handlers keep working.
"""

from __future__ import annotations


class CarbonRouterError(Exception):
    """Base class for all carbon-model-router errors."""


class CatalogError(CarbonRouterError, ValueError):
    """Catalog file is missing, empty, malformed, or has duplicate ids."""


class NoEligibleModelError(CarbonRouterError, ValueError):
    """No model in the catalog meets capability, confidence, or context limits."""


__all__ = [
    "CarbonRouterError",
    "CatalogError",
    "NoEligibleModelError",
]
