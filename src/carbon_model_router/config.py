"""User config discovery and catalog merging.

Looks for a user catalog at ``~/.config/cmr/catalog.json`` or
``~/.config/cmr/cmr.toml`` (first match wins). Models in the user file
override built-in models with the same ``id`` and are otherwise appended.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from carbon_model_router.catalog import default_catalog
from carbon_model_router.errors import CatalogError
from carbon_model_router.types import Catalog, ModelSpec

USER_CONFIG_DIRNAME = "cmr"
USER_CATALOG_FILENAMES = ("catalog.json", "cmr.toml")


def user_config_dir() -> Path:
    """Platform-appropriate directory for user configuration."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / USER_CONFIG_DIRNAME
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / USER_CONFIG_DIRNAME


def user_catalog_path() -> Path | None:
    """Return the first existing user catalog file, or None."""
    directory = user_config_dir()
    for name in USER_CATALOG_FILENAMES:
        candidate = directory / name
        if candidate.is_file():
            return candidate
    return None


def _models_from_json(data: object) -> list[ModelSpec]:
    if isinstance(data, dict):
        raw_models = data.get("models", [])
    else:
        raw_models = data
    if not isinstance(raw_models, list):
        raise CatalogError("catalog models must be a list")
    models: list[ModelSpec] = []
    for item in raw_models:
        try:
            models.append(ModelSpec(**item))
        except TypeError as exc:
            raise CatalogError(f"invalid model entry: {exc}") from exc
        except ValueError as exc:
            raise CatalogError(f"invalid model values: {exc}") from exc
    return models


def _models_from_toml(text: str) -> list[ModelSpec]:
    try:
        import tomllib
    except ModuleNotFoundError:  # pragma: no cover - py<3.11
        import tomli as tomllib  # type: ignore

    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise CatalogError(f"cmr.toml is not valid TOML: {exc}") from exc
    raw_models = data.get("models") or []
    models: list[ModelSpec] = []
    for item in raw_models:
        try:
            models.append(ModelSpec(**item))
        except TypeError as exc:
            raise CatalogError(f"invalid model entry: {exc}") from exc
        except ValueError as exc:
            raise CatalogError(f"invalid model values: {exc}") from exc
    return models


def load_user_catalog(path: str | Path | None = None) -> Catalog | None:
    """Load the user catalog if a config file exists.

    Returns None when no user catalog is present (not an error).
    Raises CatalogError when a file exists but is invalid.
    """
    p = Path(path) if path is not None else user_catalog_path()
    if p is None or not p.is_file():
        return None
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() in {".toml"}:
        models = _models_from_toml(text)
    else:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise CatalogError(f"catalog file is not valid JSON: {p}: {exc}") from exc
        models = _models_from_json(data)
    if not models:
        raise CatalogError(f"user catalog has no models: {p}")
    return Catalog(models=models)


def merge_catalogs(base: Catalog, user: Catalog | None) -> Catalog:
    """Merge user models into base.

    A user model with the same ``id`` replaces the base entry; new ids are
    appended after the base models.
    """
    if user is None:
        return Catalog(models=list(base.models))
    by_id: dict[str, ModelSpec] = {m.id: m for m in base.models}
    order: list[str] = [m.id for m in base.models]
    for model in user.models:
        if model.id in by_id:
            by_id[model.id] = model
        else:
            by_id[model.id] = model
            order.append(model.id)
    return Catalog(models=[by_id[i] for i in order])


def effective_catalog(user: Catalog | None = None) -> Catalog:
    """Built-in catalog merged with the user catalog (when provided or found)."""
    if user is None:
        user = load_user_catalog()
    return merge_catalogs(default_catalog(), user)


__all__ = [
    "USER_CATALOG_FILENAMES",
    "USER_CONFIG_DIRNAME",
    "effective_catalog",
    "load_user_catalog",
    "merge_catalogs",
    "user_catalog_path",
    "user_config_dir",
]
