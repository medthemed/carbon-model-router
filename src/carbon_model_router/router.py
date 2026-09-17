"""Pick the smallest capable model for a prompt."""

from __future__ import annotations

from carbon_model_router.analyzer import analyze_prompt, estimate_tokens
from carbon_model_router.catalog import default_catalog
from carbon_model_router.types import (
    Catalog,
    ComplexityScore,
    ModelSpec,
    RouteDecision,
)

DEFAULT_CONFIDENCE_THRESHOLD = 0.70
# Capability headroom: model must clear required by this margin to count as confident
CAPABILITY_MARGIN = 0.02


def confidence_for(model: ModelSpec, required_capability: float) -> float:
    """How confident we are that this model can handle the prompt.

    Confidence is 0 when capability < required, then ramps to 1 as the
    surplus grows. A model that barely meets the requirement gets ~0.5.
    """
    surplus = model.capability - required_capability
    if surplus < 0:
        return 0.0
    # Map surplus [0, 0.3+] → confidence [0.5, 1.0]
    return min(1.0, 0.5 + surplus / 0.6)


def eligible_models(
    catalog: Catalog,
    required_capability: float,
    confidence_threshold: float,
    estimated_tokens: int,
) -> list[tuple[ModelSpec, float]]:
    """Models that meet capability, confidence, and context-window constraints."""
    out: list[tuple[ModelSpec, float]] = []
    for model in catalog:
        conf = confidence_for(model, required_capability)
        if model.capability + 1e-12 < required_capability:
            continue
        if conf < confidence_threshold:
            continue
        # Inbound tokens must fit; leave headroom for the response
        if estimated_tokens > model.max_tokens * 0.75:
            continue
        out.append((model, conf))
    return out


def pick_smallest(
    candidates: list[tuple[ModelSpec, float]],
    carbon_weighted: bool = False,
) -> tuple[ModelSpec, float]:
    """Among eligible models, pick the smallest (or lowest-carbon).

    Smallest = lowest capability, then lowest cost, then lowest energy, then id.
    Carbon mode = lowest energy first, then cost, then capability, then id.
    """
    if not candidates:
        raise ValueError("no eligible models")

    if carbon_weighted:
        ordered = sorted(
            candidates,
            key=lambda pair: (
                pair[0].energy_kwh_per_1k,
                pair[0].cost_per_1k,
                pair[0].capability,
                pair[0].id,
            ),
        )
    else:
        ordered = sorted(
            candidates,
            key=lambda pair: (
                pair[0].capability,
                pair[0].cost_per_1k,
                pair[0].energy_kwh_per_1k,
                pair[0].id,
            ),
        )
    return ordered[0]


def _format_rejection(
    model: ModelSpec, required: float, conf: float, tokens: int, threshold: float
) -> str:
    if model.capability + 1e-12 < required:
        return f"{model.id}: capability {model.capability:.2f} < required {required:.2f}"
    if conf < threshold:
        return f"{model.id}: confidence {conf:.2f} < threshold {threshold:.2f}"
    if tokens > model.max_tokens * 0.75:
        return (
            f"{model.id}: estimated tokens {tokens} exceed 75% of max_tokens {model.max_tokens}"
        )
    return f"{model.id}: not eligible"


def build_rationale(
    model: ModelSpec,
    complexity: ComplexityScore,
    conf: float,
    estimated_cost: float,
    estimated_energy: float,
    carbon_weighted: bool,
    frontier: ModelSpec | None,
) -> str:
    parts = [
        f"complexity={complexity.score:.2f}",
        f"required_capability={complexity.required_capability:.2f}",
        f"chose {model.id} (capability={model.capability:.2f}, confidence={conf:.2f})",
    ]
    if complexity.reasons:
        parts.append("signals: " + "; ".join(complexity.reasons[:4]))
    if frontier is not None and frontier.id != model.id:
        saved_cost = frontier.cost_per_1k - model.cost_per_1k
        saved_energy = frontier.energy_kwh_per_1k - model.energy_kwh_per_1k
        if saved_cost > 0 or saved_energy > 0:
            parts.append(
                f"vs frontier {frontier.id}: saves ${saved_cost:.6f}/1k tokens"
                f" and {saved_energy:.6f} kWh/1k"
            )
    parts.append(
        f"est_cost=${estimated_cost:.6f}, est_energy={estimated_energy:.6f} kWh"
    )
    if carbon_weighted:
        parts.append("carbon-weighted selection")
    return "; ".join(parts)


def route_prompt(
    prompt: str,
    catalog: Catalog | None = None,
    *,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    carbon_weighted: bool = False,
    complexity: ComplexityScore | None = None,
) -> RouteDecision:
    """Route a prompt to the smallest eligible model."""
    cat = catalog if catalog is not None else default_catalog()
    if not cat.models:
        raise ValueError("catalog is empty")

    score = complexity if complexity is not None else analyze_prompt(prompt)
    tokens = estimate_tokens(prompt)
    candidates = eligible_models(
        cat, score.required_capability, confidence_threshold, tokens
    )

    rejected: list[str] = []
    candidate_ids = {m.id for m, _ in candidates}
    for model in cat:
        if model.id in candidate_ids:
            continue
        conf = confidence_for(model, score.required_capability)
        rejected.append(
            _format_rejection(
                model, score.required_capability, conf, tokens, confidence_threshold
            )
        )

    if not candidates:
        # Fall back to the strongest model so the caller still gets a decision
        frontier = max(cat.models, key=lambda m: (m.capability, m.cost_per_1k))
        conf = confidence_for(frontier, score.required_capability)
        est_cost = frontier.cost_per_1k * tokens / 1000.0
        est_energy = frontier.energy_kwh_per_1k * tokens / 1000.0
        rationale = (
            "no model met thresholds; falling back to strongest model. "
            + build_rationale(
                frontier, score, conf, est_cost, est_energy, carbon_weighted, None
            )
        )
        return RouteDecision(
            model=frontier,
            complexity=score,
            confidence=conf,
            estimated_tokens=tokens,
            estimated_cost=est_cost,
            estimated_energy_kwh=est_energy,
            carbon_weighted=carbon_weighted,
            rejected=tuple(rejected),
            rationale=rationale,
        )

    model, conf = pick_smallest(candidates, carbon_weighted=carbon_weighted)
    est_cost = model.cost_per_1k * tokens / 1000.0
    est_energy = model.energy_kwh_per_1k * tokens / 1000.0
    frontier = max(cat.models, key=lambda m: (m.capability, m.cost_per_1k))
    rationale = build_rationale(
        model, score, conf, est_cost, est_energy, carbon_weighted, frontier
    )
    return RouteDecision(
        model=model,
        complexity=score,
        confidence=conf,
        estimated_tokens=tokens,
        estimated_cost=est_cost,
        estimated_energy_kwh=est_energy,
        carbon_weighted=carbon_weighted,
        rejected=tuple(rejected),
        rationale=rationale,
    )


__all__ = [
    "CAPABILITY_MARGIN",
    "DEFAULT_CONFIDENCE_THRESHOLD",
    "build_rationale",
    "confidence_for",
    "eligible_models",
    "pick_smallest",
    "route_prompt",
]
