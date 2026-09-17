"""Command-line interface for carbon-model-router."""

from __future__ import annotations

import argparse
import json
import sys

from carbon_model_router.analyzer import VALID_DOMAINS, analyze_prompt
from carbon_model_router.batch import parse_prompt_file, route_prompts
from carbon_model_router.catalog import default_catalog, load_catalog_json
from carbon_model_router.config import (
    effective_catalog,
    load_user_catalog,
    user_catalog_path,
)
from carbon_model_router.errors import CatalogError
from carbon_model_router.router import DEFAULT_CONFIDENCE_THRESHOLD, route_prompt
from carbon_model_router.types import Catalog, RouteDecision

__version__ = "0.3.0"

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
    p_route.add_argument(
        "--user",
        action="store_true",
        help="Merge user catalog (~/.config/cmr/catalog.json or cmr.toml)",
    )

    # catalog
    p_cat = sub.add_parser("catalog", help="List models in the catalog")
    p_cat.add_argument(
        "--catalog",
        default=None,
        help="Path to a JSON catalog (default: built-in)",
    )
    p_cat.add_argument(
        "--user",
        action="store_true",
        help="Merge user catalog (~/.config/cmr/catalog.json or cmr.toml)",
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

    # route-file
    p_rf = sub.add_parser(
        "route-file",
        help="Route every prompt in a file and summarize cost/carbon savings",
    )
    p_rf.add_argument(
        "file",
        help="Path to a prompt file (prompts separated by a line with only ---)",
    )
    p_rf.add_argument(
        "--catalog",
        default=None,
        help="Path to a JSON catalog (default: built-in)",
    )
    p_rf.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_CONFIDENCE_THRESHOLD,
        help=f"Minimum confidence 0-1 (default: {DEFAULT_CONFIDENCE_THRESHOLD})",
    )
    p_rf.add_argument(
        "--carbon",
        action="store_true",
        help="Prefer lowest-energy model among eligible candidates",
    )
    p_rf.add_argument(
        "--domain",
        choices=VALID_DOMAINS,
        default=None,
        help="Force prompt domain (code|math|chat) instead of auto-detect",
    )
    p_rf.add_argument(
        "--user",
        action="store_true",
        help="Merge user catalog (~/.config/cmr/catalog.json or cmr.toml)",
    )
    p_rf.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit JSON batch report with items and savings summary",
    )

    sub.add_parser("version", help="Print version")
    return parser


def _load_catalog(path: str | None, use_user: bool = False) -> Catalog:
    if path:
        return load_catalog_json(path)
    if use_user:
        return effective_catalog()
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
    use_user = getattr(args, "user", False)
    try:
        catalog = _load_catalog(args.catalog, use_user=use_user)
    except CatalogError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
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
    use_user = getattr(args, "user", False)
    try:
        catalog = _load_catalog(args.catalog, use_user=use_user)
    except CatalogError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    if use_user and not args.catalog:
        source = user_catalog_path()
        if source is not None:
            print(f"# user catalog: {source}", file=sys.stderr)
        else:
            print("# no user catalog found; showing built-in", file=sys.stderr)
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


def _print_batch_report(report) -> None:
    print("carbon-model-router batch report")
    print("=" * 40)
    for item in report.items:
        m = item.decision.model
        print(
            f"[{item.index}] {m.id:<16} "
            f"${item.decision.estimated_cost:.6f}  "
            f"{item.decision.estimated_energy_kwh:.6f} kWh  "
            f"vs {item.default_model_id} "
            f"(save ${item.saved_cost:.6f})"
        )
        print(f"     {item.prompt_preview}")
    s = report.summary
    if s is None:
        return
    print()
    print("savings vs default (always frontier)")
    print("-" * 40)
    print(f"prompts:          {s.prompt_count}")
    print(f"default model:    {s.default_model_id}")
    print(f"routed cost:      ${s.routed_cost:.6f}")
    print(f"default cost:     ${s.default_cost:.6f}")
    print(f"saved cost:       ${s.saved_cost:.6f}  ({s.saved_cost_pct:.1f}%)")
    print(f"routed energy:    {s.routed_energy_kwh:.6f} kWh")
    print(f"default energy:   {s.default_energy_kwh:.6f} kWh")
    print(f"saved energy:     {s.saved_energy_kwh:.6f} kWh  ({s.saved_energy_pct:.1f}%)")


def cmd_route_file(args: argparse.Namespace) -> int:
    try:
        prompts = parse_prompt_file(args.file)
    except FileNotFoundError:
        print(f"error: prompt file not found: {args.file}", file=sys.stderr)
        return EXIT_ERROR
    except OSError as exc:
        print(f"error: cannot read prompt file: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if not prompts:
        print("error: no prompts found in file", file=sys.stderr)
        return EXIT_ERROR

    use_user = getattr(args, "user", False)
    try:
        catalog = _load_catalog(args.catalog, use_user=use_user)
    except CatalogError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    report = route_prompts(
        prompts,
        catalog,
        confidence_threshold=args.threshold,
        carbon_weighted=args.carbon,
        domain=args.domain,
    )

    if args.as_json:
        sys.stdout.write(json.dumps(report.to_dict(), indent=2) + "\n")
    else:
        _print_batch_report(report)
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "route":
        return cmd_route(args)
    if args.command == "route-file":
        return cmd_route_file(args)
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
