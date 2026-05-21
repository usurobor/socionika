"""CLI: python -m socionics_medallion.cli compile --plan canonical ...

Usage
-----
Stub path (CadQuery-free, always exits 0 on a valid plan):
    python -m socionics_medallion.cli compile \
        --plan canonical --executor stub --out out/stream.json

CadQuery path (requires cadquery; allowed to fail on unimplemented ops):
    python -m socionics_medallion.cli compile \
        --plan canonical --executor cadquery --step out/medallion.step
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Sequence

from socionics_medallion import ir as ir_mod
from socionics_medallion.compiler import compile_medallion
from socionics_medallion.plan import build_plan

_PLAN_FACTORIES = {
    "canonical": build_plan,
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m socionics_medallion.cli",
        description="Compile and (optionally) execute a medallion plan.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    compile_p = sub.add_parser("compile", help="Compile a plan and run an executor.")
    compile_p.add_argument(
        "--plan",
        choices=sorted(_PLAN_FACTORIES.keys()),
        required=True,
        help="Which plan to compile.",
    )
    compile_p.add_argument(
        "--executor",
        choices=["stub", "cadquery"],
        required=True,
        help="Which executor consumes the compiled stream.",
    )
    compile_p.add_argument(
        "--out",
        type=str,
        default=None,
        help="Output JSON path for the stub executor.",
    )
    compile_p.add_argument(
        "--step",
        type=str,
        default=None,
        help="Output STEP path for the cadquery executor.",
    )
    compile_p.add_argument(
        "--stl",
        type=str,
        default=None,
        help="Output STL path for the cadquery executor.",
    )
    compile_p.add_argument(
        "--verbose",
        action="store_true",
        help="Print operator-visible projection to stdout.",
    )
    return parser


def _ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)


def _run_stub(plan_name: str, out: str | None, verbose: bool) -> int:
    from socionics_medallion.executor import StubExecutor  # local: keeps stub path lazy

    plan = _PLAN_FACTORIES[plan_name]()
    ops = compile_medallion(plan)
    result = StubExecutor().execute(ops)

    if out is None:
        # Default destination for the operator if none is given.
        out = os.path.join("out", "stream.json")
    _ensure_parent_dir(out)
    payload = json.dumps(result, sort_keys=True, indent=2) + "\n"
    with open(out, "w", encoding="utf-8") as f:
        f.write(payload)

    if verbose:
        _print_projection(result)
    return 0


def _print_projection(result: dict) -> None:
    counts = result["counts"]
    out = sys.stdout.write
    out(f"ops total:           {sum(counts.values())}\n")
    out(f"prisms:              {counts.get('Prism', 0)}\n")
    out(f"lowered fields:      {counts.get('LowerField', 0)}\n")
    out(f"raised symbols:      {counts.get('RaisedSymbol', 0)}\n")
    out(f"cut symbols:         {counts.get('CutSymbol', 0)}\n")
    out(f"engraved dividers:   {counts.get('EngravedDivider', 0)}\n")
    out(f"raised dividers:     {counts.get('RaisedDivider', 0)}\n")
    out(f"implemented in cadquery executor: {result['implemented_ops']}\n")
    out(f"not yet implemented:               {result['not_yet_implemented']}\n")


def _run_cadquery(
    plan_name: str, step: str | None, stl: str | None, verbose: bool
) -> int:
    # Lazy import; this raises if cadquery isn't installed.
    from socionics_medallion.executor import CadQueryExecutor

    plan = _PLAN_FACTORIES[plan_name]()
    ops = compile_medallion(plan)
    executor = CadQueryExecutor()
    result = executor.execute(ops)
    if result.solid is None:
        sys.stderr.write("cadquery executor produced no solid.\n")
        return 2
    if step is not None:
        _ensure_parent_dir(step)
        result.solid.val().exportStep(step)
    if stl is not None:
        _ensure_parent_dir(stl)
        # CadQuery's exporter signature differs across releases; do it via
        # the high-level helper that's stable.
        from cadquery import exporters  # type: ignore

        exporters.export(result.solid, stl)
    if verbose:
        sys.stdout.write(f"processed: {dict(result.processed)}\n")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "compile":
        if args.executor == "stub":
            return _run_stub(args.plan, args.out, args.verbose)
        if args.executor == "cadquery":
            return _run_cadquery(args.plan, args.step, args.stl, args.verbose)
    parser.error(f"unknown command: {args.command}")
    return 2  # pragma: no cover


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
