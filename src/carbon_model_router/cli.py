"""Command-line interface for carbon-model-router."""

from __future__ import annotations

import argparse
import json
import sys

from carbon_model_router.analyzer import VALID_DOMAINS, analyze_prompt
from carbon_model_router.catalog import default_catalog, load_catalog_json
from carbon_model_router.router import DEFAULT_CONFIDENCE_THRESHOLD, route_prompt
from carbon_model_router.types import Catalog, RouteDecision

__version__ = "0.2.0"

EXIT_OK = 0
EXIT_ERROR = 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cmr",
        description="Route prompts to the smallest capable LLM to cut cost and carbon.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"carbon-model-router {__version__}",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # route
    p_route = sub.add_parser("route", help="Choose a model for a prompt")
    p_route.add_argument(
        "prompt",
        nargs="?",
        default=None,
        help="Prompt text (or omit and use --file / stdin)",
    )
    p_route.add_argument(
        "-f",
        "--file",
        default=None,
        help="Read prompt from a file",
    )
    p_route.add_argument(
        "--catalog",
        default=None,
        help="Path to a JSON catalog (default: built-in)",
    )
    p_route.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_CONFIDENCE_THRESHOLD,
        help=f"Minimum confidence 0-1 (default: {DEFAULT_CONFIDENCE_THRESHOLD})",
    )
    p_route.add_argument(
        "--carbon",
        action="store_true",
        help="Prefer lowest-energy model among eligible candidates",
    )
    p_route.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit JSON decision",
    )
    p_route.add_argument(
        "--show-rejected",
        action="store_true",
        help="Include rejected models in output",
    )
    p_route.add_argument(
        "--domain",
        choices=VALID_DOMAINS,
        default=None,
        help="Force prompt domain (code|math|chat) instead of auto-detect",
    )

    # catalog
    p_cat = sub.add_parser("catalog", help="List models in the catalog")
    p_cat.add_argument(
        "--catalog",
        default=None,
        help="Path to a JSON catalog (default: built-in)",
    )
    p_cat.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit JSON",
    )

    # analyze
    p_an = sub.add_parser("analyze", help="Show complexity analysis without routing")
    p_an.add_argument("prompt", nargs="?", default=None)
    p_an.add_argument("-f", "--file", default=None)
    p_an.add_argument("--json", action="store_true", dest="as_json")
    p_an.add_argument(
        "--domain",
        choices=VALID_DOMAINS,
        default=None,
        help="Force prompt domain (code|math|chat) instead of auto-detect",
    )

    sub.add_parser("version", help="Print version")
    return parser


def _load_catalog(path: str | None) -> Catalog:
    if path:
        return load_catalog_json(path)
    return default_catalog()


def _read_prompt(args: argparse.Namespace) -> str:
    if getattr(args, "file", None):
        with open(args.file, encoding="utf-8") as fh:
            return fh.read()
    if args.prompt is not None:
        return args.prompt
    if not sys.stdin.isatty():
        return sys.stdin.read()
    return ""


def cmd_route(args: argparse.Namespace) -> int:
    text = _read_prompt(args)
    catalog = _load_catalog(args.catalog)
    decision = route_prompt(
        text,
        catalog,
        confidence_threshold=args.threshold,
        carbon_weighted=args.carbon,
        domain=args.domain,
    )
    if args.as_json:
        payload = decision.to_dict()
        if not args.show_rejected:
            payload.pop("rejected", None)
        sys.stdout.write(json.dumps(payload, indent=2) + "\n")
    else:
        _print_decision(decision, show_rejected=args.show_rejected)
    return EXIT_OK


def _print_decision(decision: RouteDecision, show_rejected: bool = False) -> None:
    m = decision.model
    c = decision.complexity
    print("carbon-model-router decision")
    print("=" * 40)
    print(f"model:       {m.id}  ({m.name}, {m.provider})")
    print(f"capability:  {m.capability:.2f}")
    print(f"confidence:  {decision.confidence:.2f}")
    print(f"complexity:  {c.score:.2f}  (required capability {c.required_capability:.2f})")
    print(f"tokens:      ~{decision.estimated_tokens}")
    print(f"est cost:    ${decision.estimated_cost:.6f}")
    print(f"est energy:  {decision.estimated_energy_kwh:.6f} kWh")
    if decision.carbon_weighted:
        print("mode:        carbon-weighted")
    print()
    print(f"rationale:   {decision.rationale}")
    if show_rejected and decision.rejected:
        print()
        print("rejected:")
        for line in decision.rejected:
            print(f"  - {line}")


def cmd_catalog(args: argparse.Namespace) -> int:
    catalog = _load_catalog(args.catalog)
    if args.as_json:
        payload = {"models": [m.to_dict() for m in catalog.sorted_by_capability()]}
        sys.stdout.write(json.dumps(payload, indent=2) + "\n")
        return EXIT_OK

    print(f"{'id':<18} {'cap':>5} {'cost/1k':>10} {'kWh/1k':>10} {'max_tok':>8}  notes")
    print("-" * 78)
    for m in catalog.sorted_by_capability():
        print(
            f"{m.id:<18} {m.capability:>5.2f} {m.cost_per_1k:>10.5f} "
            f"{m.energy_kwh_per_1k:>10.5f} {m.max_tokens:>8}  {m.notes}"
        )
    return EXIT_OK


def cmd_analyze(args: argparse.Namespace) -> int:
    text = _read_prompt(args)
    score = analyze_prompt(text, domain=args.domain)
    if args.as_json:
        sys.stdout.write(json.dumps(score.to_dict(), indent=2) + "\n")
    else:
        print(f"complexity:          {score.score:.4f}")
        print(f"required_capability: {score.required_capability:.4f}")
        print("signals:")
        for key, value in sorted(score.signals.items()):
            print(f"  {key:<12} {value:.3f}")
        if score.reasons:
            print("reasons:")
            for reason in score.reasons:
                print(f"  - {reason}")
    return EXIT_OK


def cmd_version(_args: argparse.Namespace) -> int:
    print(f"carbon-model-router {__version__}")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "route":
        return cmd_route(args)
    if args.command == "catalog":
        return cmd_catalog(args)
    if args.command == "analyze":
        return cmd_analyze(args)
    if args.command == "version":
        return cmd_version(args)
    parser.error(f"unknown command: {args.command}")
    return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
