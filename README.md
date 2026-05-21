# socionika

Practical socionika.

## Status

This repo delivers a working socionics medallion CAD generator per
issues #1, #2, #3, and #5:

- `socionics_medallion.plan` builds the canonical 8-inner / 16-outer
  socionics layout (issue #1 AC2–AC4). No CadQuery dependency.
- `socionics_medallion.ir` defines the pure-data CadOp instruction IR
  (`Prism`, `LowerField`, `RaisedSymbol`, `CutSymbol`, `RaisedDivider`,
  `EngravedDivider`) per issue #2 AC1.
- `socionics_medallion.compiler.compile_medallion` is a deterministic,
  CadQuery-free pure function (issue #2 AC2/AC3, issue #3 AC1-AC5).
- `socionics_medallion.executor` ships a `StubExecutor` (CadQuery-free,
  emits a JSON dump) and a `CadQueryExecutor` covering every op variant
  (`IMPLEMENTED_OPS == ALL_OP_TYPES`, issue #1 AC9 / issue #2 AC5).
- STEP and STL export end-to-end (issue #5 AC1–AC4): the executor's
  `build_solid()` collapses the union/cut accumulator to a single
  connected `cadquery.Solid`; `export_step` and `export_stl` emit
  ISO-10303-21 STEP and binary STL respectively. `reimport_step` +
  `compare_solids` round-trip the STEP file and report bounds/volume
  deltas.
- CLI: `python -m socionics_medallion.cli compile --plan canonical
  --executor {stub,cadquery} [--out PATH] [--step PATH] [--stl PATH]`.
- CI runs three jobs: `tests-no-cadquery`, `tests-with-cadquery`, and
  `export-artifacts` (the last uploads `out/medallion.step` and
  `out/medallion.stl` as the `medallion-cad` workflow artifact via
  `actions/upload-artifact@v4`).

Run tests: `python -m unittest discover tests`.
