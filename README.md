# socionika

Practical socionika.

## Status

This repo currently delivers the **testable shell** for the socionics
medallion generator described in issues #1 and #2:

- `socionics_medallion.plan` builds the canonical 8-inner / 16-outer
  socionics layout (issue #1 AC2–AC4). No CadQuery dependency.
- `socionics_medallion.ir` defines the pure-data CadOp instruction IR
  (`Prism`, `LowerField`, `RaisedSymbol`, `CutSymbol`, `RaisedDivider`,
  `EngravedDivider`) per issue #2 AC1.
- `socionics_medallion.compiler.compile_medallion` is a deterministic,
  CadQuery-free pure function (issue #2 AC2/AC3).
- `socionics_medallion.executor` ships a `StubExecutor` (CadQuery-free,
  emits a JSON dump) and a `CadQueryExecutor` whose `IMPLEMENTED_OPS`
  currently covers `Prism` end-to-end; other ops raise `NotYetImplemented`
  (issue #2 AC5/AC6).
- CLI: `python -m socionics_medallion.cli compile --plan canonical
  --executor {stub,cadquery} --out ... --step ...`.
- CI runs two jobs: `tests-no-cadquery` (always required) and
  `tests-with-cadquery` (installs CadQuery and runs the marked smoke
  tests).

Deferred (named in issue #2's closure condition / issue #1 AC9):
- Implementing `LowerField`, `RaisedSymbol`, `CutSymbol`, `RaisedDivider`,
  `EngravedDivider` in `CadQueryExecutor`.
- STEP/STL export of a full medallion solid.
- Visual / manufacturing tolerances.

Run tests: `python -m unittest discover tests`.
