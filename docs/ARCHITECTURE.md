# Architecture

## Problem

Teams default every prompt to a frontier model. Simple tasks (classification,
short rewrites, greetings) pay frontier prices and frontier carbon for no
quality gain. Hard tasks still need frontier capability. The goal is a
**deterministic, offline router** that picks the smallest model that is still
good enough.

## High-level flow

```
 prompt ──► analyzer.py ──► ComplexityScore (score, required_capability)
                                │
                                ▼
              catalog.py ──► Catalog (ModelSpec[])
                                │
                                ▼
              router.py  ──► RouteDecision (model, confidence, rationale)
                                │
                                ▼
              cli.py     ──► text | JSON
```

No network calls. Same input → same model, every time.

## Modules

| Module | Responsibility |
|--------|----------------|
| `types.py` | `ModelSpec`, `ComplexityScore`, `RouteDecision`, `Catalog` |
| `catalog.py` | Built-in models, JSON loader, validation |
| `analyzer.py` | Heuristic signals → complexity 0–1 → required capability |
| `router.py` | Eligibility, confidence, smallest / carbon-weighted pick |
| `cli.py` | `cmr route` / `cmr catalog` / `cmr analyze` / `cmr version` |

## Complexity signals

| Signal | Weight | What it looks at |
|--------|--------|------------------|
| length | 0.20 | character count, ramp 80→1200 |
| code | 0.20 | fences, indentation, language keywords |
| math | 0.15 | formal/math markers, LaTeX, solve/prove |
| multi_step | 0.20 | step language, numbered lists, bullets |
| domain | 0.15 | systems/ML/crypto vocabulary |
| format | 0.10 | JSON/YAML/schema/table requests |

Simple intents ("what is…", "translate…", "summarize in one sentence") are
soft-capped so long-but-trivial prompts do not over-route.

## Capability mapping

Piecewise linear from complexity score to required capability:

```
0.0 → 0.25
0.4 → 0.45
0.6 → 0.65
0.8 → 0.80
1.0 → 0.95
```

## Eligibility rules

A model is eligible when **all** hold:

1. `capability >= required_capability`
2. `confidence >= threshold` (default 0.70)
3. estimated prompt tokens ≤ 75% of `max_tokens` (headroom for the reply)

Confidence = 0 below required capability; otherwise
`min(1.0, 0.5 + surplus / 0.6)` where `surplus = capability - required`.

## Selection

- **Default:** lowest capability, then lowest cost, then lowest energy, then id.
- **Carbon mode (`--carbon`):** lowest energy, then cost, then capability, then id.

If nothing is eligible, the router falls back to the strongest model and says
so in the rationale (so callers never get a silent failure).

## Design decisions

### Heuristics, not a classifier

An MVP router must be auditable and offline. Regex/keyword signals are easy to
tune, test, and explain. A learned classifier can replace `analyze_prompt`
later without changing the router contract.

### Smallest, not cheapest

Cost tables drift; capability ordering is the stable proxy for "don't
over-model." Cost breaks ties. Carbon mode explicitly optimizes energy.

### Determinism is a feature

Routers that call a meta-model to pick a model inherit that model's cost,
latency, and variance. This one is pure functions over text.

### Catalog is data

Models live in `types.ModelSpec` + JSON. Ship your fleet, not ours. Duplicate
ids and invalid fields fail at load time.

## Extension points

- Custom signal plugins (e.g. language detection, tool-use markers)
- Learned scorer behind the same `ComplexityScore` interface
- Live pricing fetchers that rewrite `cost_per_1k` (still offline routing)
- Batch routing with a shared catalog snapshot
