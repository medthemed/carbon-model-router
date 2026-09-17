# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
