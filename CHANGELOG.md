# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2026-09-24

### Added
- `cmr route-file <file>` routes every prompt in a file (separator: a line
  containing only `---`) and prints per-prompt decisions plus a savings
  summary versus always using the frontier model.
- Pure-core batch API: `parse_prompt_file`, `parse_prompt_text`,
  `route_prompts`, `summarize_savings`, `frontier_model`,
  `BatchRouteReport`, `BatchRouteItem`, `SavingsSummary`.
- JSON batch payload (`--json`) with `items[]` and `summary` (routed vs
  default cost/energy, absolute and percent savings).
- Tests covering separator parsing, savings math, CLI text/JSON, and the
  examples/prompt-list.txt fixture.

## [0.3.0] - 2026-09-23

### Added
- User catalog file at `~/.config/cmr/catalog.json` or `~/.config/cmr/cmr.toml`
  (Windows: `%APPDATA%\cmr\...`), merged with the built-in catalog.
- `load_user_catalog()`, `merge_catalogs()`, `effective_catalog()`,
  `user_catalog_path()`.
- `cmr catalog --user` and `cmr route --user` merge user models (same id
  overrides; new ids append).
- README: user catalog format and lookup order.

## [0.2.0] - 2026-09-20

### Added
- Typed exception module (`carbon_model_router.errors`): `CarbonRouterError`,
  `CatalogError`, `NoEligibleModelError`. Typed errors also subclass `ValueError`.
- Integration tests routing a multi-prompt list file against the default and
  a custom JSON catalog.
- `examples/prompt-list.txt` sample batch input.
- README: Python API section with exception hierarchy.

### Changed
- Catalog loaders and `route_prompt` / `pick_smallest` raise typed errors
  instead of bare `ValueError`.

## [0.1.1] - 2026-09-18

### Added
- `--domain code|math|chat` on `cmr route` and `cmr analyze`, plus
  `analyze_prompt(..., domain=...)` / `route_prompt(..., domain=...)`.
  Code/math raise signal floors for short-but-hard prompts; chat soft-caps
  complexity so chatty text stays on small models.
- README: model comparison table with pick-when guidance and a cost/carbon
  worked example.

## [0.1.0] - 2026-09-16

### Added
- Initial public MVP of carbon-model-router.
- Model catalog with cost, energy, capability, and max_tokens per model.
- Heuristic prompt complexity analyzer (length, code fences, math, multi-step, domain keywords).
- Router selecting the smallest model meeting capability and confidence thresholds.
- Optional carbon-weighted ranking among eligible models.
- CLI: `cmr route`, `cmr catalog`, `cmr analyze`, `cmr version`.
- Deterministic routing with no live API calls.
- Pytest suite covering simple/complex routing, catalog integrity, thresholds, and carbon mode.
