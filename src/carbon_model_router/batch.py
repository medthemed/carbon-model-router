"""Batch prompt routing and cost/carbon savings summary.

Pure-core note
--------------
``parse_prompt_file``, ``route_prompts``, and ``summarize_savings`` are
side-effect free. Given the same prompt list and catalog they always
produce the same decisions, so callers can shard large files across a
thread or process pool and merge summaries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from carbon_model_router.catalog import default_catalog
from carbon_model_router.router import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    route_prompt,
)
from carbon_model_router.types import Catalog, RouteDecision

PROMPT_SEPARATOR = "---"


def parse_prompt_file(path: str | Path) -> list[str]:
    """Read prompts from a text file.

    Prompts are separated by a line containing only ``---``. Blank lines
    around separators are ignored. A file without separators yields a
    single prompt (the whole file).
    """
    text = Path(path).read_text(encoding="utf-8")
    return parse_prompt_text(text)


def parse_prompt_text(text: str) -> list[str]:
    """Split prompt text on ``---`` separator lines."""
    chunks: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.strip() == PROMPT_SEPARATOR:
            chunk = "\n".join(current).strip()
            if chunk:
                chunks.append(chunk)
            current = []
        else:
            current.append(line)
    chunk = "\n".join(current).strip()
    if chunk:
        chunks.append(chunk)
    return chunks


def frontier_model(catalog: Catalog):
    """The default expensive choice: highest capability (cost as tiebreak)."""
    return max(catalog.models, key=lambda m: (m.capability, m.cost_per_1k))


@dataclass
class BatchRouteItem:
    """One prompt's routing decision plus its frontier comparison."""

    index: int
    prompt_preview: str
    decision: RouteDecision
    default_model_id: str
    default_cost: float
    default_energy_kwh: float
    saved_cost: float
    saved_energy_kwh: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "prompt_preview": self.prompt_preview,
            "model_id": self.decision.model.id,
            "estimated_tokens": self.decision.estimated_tokens,
            "estimated_cost": round(self.decision.estimated_cost, 8),
            "estimated_energy_kwh": round(self.decision.estimated_energy_kwh, 8),
            "default_model_id": self.default_model_id,
            "default_cost": round(self.default_cost, 8),
            "default_energy_kwh": round(self.default_energy_kwh, 8),
            "saved_cost": round(self.saved_cost, 8),
            "saved_energy_kwh": round(self.saved_energy_kwh, 8),
            "confidence": round(self.decision.confidence, 4),
            "complexity": self.decision.complexity.to_dict(),
            "rationale": self.decision.rationale,
        }


@dataclass
class SavingsSummary:
    """Aggregate cost/energy of chosen models vs always-frontier default."""

    prompt_count: int
    total_tokens: int
    routed_cost: float
    routed_energy_kwh: float
    default_cost: float
    default_energy_kwh: float
    default_model_id: str
    saved_cost: float
    saved_energy_kwh: float
    saved_cost_pct: float
    saved_energy_pct: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt_count": self.prompt_count,
            "total_tokens": self.total_tokens,
            "routed_cost": round(self.routed_cost, 8),
            "routed_energy_kwh": round(self.routed_energy_kwh, 8),
            "default_cost": round(self.default_cost, 8),
            "default_energy_kwh": round(self.default_energy_kwh, 8),
            "default_model_id": self.default_model_id,
            "saved_cost": round(self.saved_cost, 8),
            "saved_energy_kwh": round(self.saved_energy_kwh, 8),
            "saved_cost_pct": round(self.saved_cost_pct, 2),
            "saved_energy_pct": round(self.saved_energy_pct, 2),
        }


@dataclass
class BatchRouteReport:
    """All item decisions plus the savings summary."""

    items: list[BatchRouteItem] = field(default_factory=list)
    summary: SavingsSummary | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": [item.to_dict() for item in self.items],
            "summary": self.summary.to_dict() if self.summary else None,
        }


def _preview(prompt: str, width: int = 60) -> str:
    one_line = " ".join(prompt.split())
    if len(one_line) <= width:
        return one_line
    return one_line[: width - 1] + "…"


def route_prompts(
    prompts: Sequence[str],
    catalog: Catalog | None = None,
    *,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    carbon_weighted: bool = False,
    domain: str | None = None,
) -> BatchRouteReport:
    """Route each prompt and compare against always using the frontier model.

    Pure: same inputs produce the same report. Suitable for pool mapping
    when sharding large prompt files.
    """
    cat = catalog if catalog is not None else default_catalog()
    default = frontier_model(cat)

    items: list[BatchRouteItem] = []
    for index, prompt in enumerate(prompts):
        decision = route_prompt(
            prompt,
            cat,
            confidence_threshold=confidence_threshold,
            carbon_weighted=carbon_weighted,
            domain=domain,
        )
        tokens = decision.estimated_tokens
        default_cost = default.cost_per_1k * tokens / 1000.0
        default_energy = default.energy_kwh_per_1k * tokens / 1000.0
        items.append(
            BatchRouteItem(
                index=index,
                prompt_preview=_preview(prompt),
                decision=decision,
                default_model_id=default.id,
                default_cost=default_cost,
                default_energy_kwh=default_energy,
                saved_cost=default_cost - decision.estimated_cost,
                saved_energy_kwh=default_energy - decision.estimated_energy_kwh,
            )
        )

    summary = summarize_savings(items, default_model_id=default.id)
    return BatchRouteReport(items=items, summary=summary)


def summarize_savings(
    items: Sequence[BatchRouteItem],
    default_model_id: str,
) -> SavingsSummary:
    """Aggregate routed vs default cost and energy across items."""
    total_tokens = sum(item.decision.estimated_tokens for item in items)
    routed_cost = sum(item.decision.estimated_cost for item in items)
    routed_energy = sum(item.decision.estimated_energy_kwh for item in items)
    default_cost = sum(item.default_cost for item in items)
    default_energy = sum(item.default_energy_kwh for item in items)
    saved_cost = default_cost - routed_cost
    saved_energy = default_energy - routed_energy
    saved_cost_pct = (saved_cost / default_cost * 100.0) if default_cost > 0 else 0.0
    saved_energy_pct = (
        (saved_energy / default_energy * 100.0) if default_energy > 0 else 0.0
    )
    return SavingsSummary(
        prompt_count=len(items),
        total_tokens=total_tokens,
        routed_cost=routed_cost,
        routed_energy_kwh=routed_energy,
        default_cost=default_cost,
        default_energy_kwh=default_energy,
        default_model_id=default_model_id,
        saved_cost=saved_cost,
        saved_energy_kwh=saved_energy,
        saved_cost_pct=saved_cost_pct,
        saved_energy_pct=saved_energy_pct,
    )


def load_prompt_file_or_text(path: str | Path | None, text: str | None) -> list[str]:
    """Helper for CLI: file path wins, else raw text, else empty."""
    if path is not None:
        return parse_prompt_file(path)
    if text is not None:
        return parse_prompt_text(text)
    return []


__all__ = [
    "BatchRouteItem",
    "BatchRouteReport",
    "PROMPT_SEPARATOR",
    "SavingsSummary",
    "frontier_model",
    "load_prompt_file_or_text",
    "parse_prompt_file",
    "parse_prompt_text",
    "route_prompts",
    "summarize_savings",
]
