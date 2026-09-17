"""Core types for carbon-model-router."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ModelSpec:
    """A model in the routing catalog.

    Costs and energy are per 1,000 tokens. Capability is 0-1 (1 = frontier).
    """

    id: str
    name: str
    provider: str
    cost_per_1k: float
    energy_kwh_per_1k: float
    capability: float
    max_tokens: int
    notes: str = ""

    def __post_init__(self) -> None:
        if self.cost_per_1k < 0:
            raise ValueError(f"{self.id}: cost_per_1k must be >= 0")
        if self.energy_kwh_per_1k < 0:
            raise ValueError(f"{self.id}: energy_kwh_per_1k must be >= 0")
        if not (0.0 <= self.capability <= 1.0):
            raise ValueError(f"{self.id}: capability must be in [0, 1]")
        if self.max_tokens <= 0:
            raise ValueError(f"{self.id}: max_tokens must be > 0")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ComplexityScore:
    """Result of analyzing a prompt."""

    score: float  # 0-1
    required_capability: float  # 0-1
    signals: dict[str, float] = field(default_factory=dict)
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 4),
            "required_capability": round(self.required_capability, 4),
            "signals": {k: round(v, 4) for k, v in self.signals.items()},
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class RouteDecision:
    """Chosen model plus rationale and alternatives considered."""

    model: ModelSpec
    complexity: ComplexityScore
    confidence: float
    estimated_tokens: int
    estimated_cost: float
    estimated_energy_kwh: float
    carbon_weighted: bool
    rejected: tuple[str, ...] = ()  # model ids rejected with reason packed in
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model.to_dict(),
            "complexity": self.complexity.to_dict(),
            "confidence": round(self.confidence, 4),
            "estimated_tokens": self.estimated_tokens,
            "estimated_cost": round(self.estimated_cost, 8),
            "estimated_energy_kwh": round(self.estimated_energy_kwh, 8),
            "carbon_weighted": self.carbon_weighted,
            "rejected": list(self.rejected),
            "rationale": self.rationale,
        }


@dataclass
class Catalog:
    """Ordered collection of models."""

    models: list[ModelSpec] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.models)

    def __iter__(self):
        return iter(self.models)

    def by_id(self, model_id: str) -> ModelSpec | None:
        for m in self.models:
            if m.id == model_id:
                return m
        return None

    def sorted_by_capability(self) -> list[ModelSpec]:
        return sorted(self.models, key=lambda m: (m.capability, m.cost_per_1k, m.id))

    def sorted_by_cost(self) -> list[ModelSpec]:
        return sorted(self.models, key=lambda m: (m.cost_per_1k, m.capability, m.id))

    def sorted_by_energy(self) -> list[ModelSpec]:
        return sorted(self.models, key=lambda m: (m.energy_kwh_per_1k, m.capability, m.id))
