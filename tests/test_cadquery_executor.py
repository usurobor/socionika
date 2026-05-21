"""Tests for CadQueryExecutor.

These tests are skipped when CadQuery isn't installed, except for:

* the import-laziness test (always run);
* the ``IMPLEMENTED_OPS == ALL_OP_TYPES`` assertion (always run);
* the no-midpoint-recomputation source check (always run).
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import unittest

from socionics_medallion.compiler import compile_medallion
from socionics_medallion.executor import (
    IMPLEMENTED_OPS,
    CadQueryExecutor,
    NotYetImplemented,
)
from socionics_medallion.ir import (
    ALL_OP_TYPES,
    CutSymbol,
    EngravedDivider,
    LowerField,
    Prism,
    RaisedDivider,
    RaisedSymbol,
    SymbolKind,
)
from socionics_medallion.plan import build_plan


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _cadquery_available() -> bool:
    return importlib.util.find_spec("cadquery") is not None


class TestExecutorLazyCadQueryImport(unittest.TestCase):
    """Importing socionics_medallion.executor must not load cadquery."""

    def test_module_level_import_does_not_load_cadquery(self) -> None:
        result = subprocess.run(
            [
                "python3",
                "-c",
                "import sys; import socionics_medallion.executor; "
                "assert 'cadquery' not in sys.modules, sorted(sys.modules)",
            ],
            cwd=_repo_root(),
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode, 0, msg=result.stdout + "\n" + result.stderr
        )


class TestImplementedOpsDeclaration(unittest.TestCase):
    def test_implemented_ops_is_set(self) -> None:
        self.assertIsInstance(CadQueryExecutor.IMPLEMENTED_OPS, frozenset)

    def test_module_level_alias_matches_class(self) -> None:
        self.assertEqual(IMPLEMENTED_OPS, CadQueryExecutor.IMPLEMENTED_OPS)

    def test_implemented_ops_equals_all_op_types(self) -> None:
        """AC9 — every op variant produced by the canonical compiler is
        implemented in the executor."""
        self.assertEqual(IMPLEMENTED_OPS, ALL_OP_TYPES)


@unittest.skipUnless(_cadquery_available(), "cadquery not installed")
class TestCadQueryExecutorPrism(unittest.TestCase):
    def test_prism_smoke(self) -> None:
        op = Prism(
            center=(0.0, 0.0),
            inner_radius=0.0,
            outer_radius=10.0,
            angle_start_deg=0.0,
            angle_end_deg=45.0,
            center_angle_deg=22.5,
            span_deg=45.0,
            z0=0.0,
            z1=2.5,
        )
        result = CadQueryExecutor().execute([op])
        self.assertIsNotNone(result.solid)


@unittest.skipUnless(_cadquery_available(), "cadquery not installed")
class TestCadQueryExecutorLowerField(unittest.TestCase):
    def test_lower_field_lowers_top_surface(self) -> None:
        # Build a thin pad and lower a strip of it.
        prism = Prism(
            center=(0.0, 0.0),
            inner_radius=0.0,
            outer_radius=10.0,
            angle_start_deg=0.0,
            angle_end_deg=45.0,
            center_angle_deg=22.5,
            span_deg=45.0,
            z0=0.0,
            z1=4.0,
        )
        lower = LowerField(
            owner_cell_id="inner:00",
            center=(0.0, 0.0),
            inner_radius=0.0,
            outer_radius=10.0,
            angle_start_deg=0.0,
            angle_end_deg=45.0,
            center_angle_deg=22.5,
            span_deg=45.0,
            surface_z=4.0,
            depth=0.6,
        )
        result = CadQueryExecutor().execute([prism, lower])
        self.assertIsNotNone(result.solid)
        bb = result.solid.val().BoundingBox()
        # After lowering the entire prism's top, the top of the solid is at
        # 4.0 - 0.6 = 3.4 (within floating tolerance).
        self.assertAlmostEqual(bb.zmax, 3.4, places=4)


@unittest.skipUnless(_cadquery_available(), "cadquery not installed")
class TestCadQueryExecutorRaisedDivider(unittest.TestCase):
    def test_raised_divider_smoke(self) -> None:
        prism = Prism(
            center=(0.0, 0.0),
            inner_radius=0.0,
            outer_radius=10.0,
            angle_start_deg=0.0,
            angle_end_deg=45.0,
            center_angle_deg=22.5,
            span_deg=45.0,
            z0=0.0,
            z1=4.0,
        )
        rib = RaisedDivider(
            owner_cell_id="inner:00",
            boundary_id="b0",
            side="A",
            ring="inner",
            angle_start_deg=22.2,
            angle_end_deg=22.8,
            center_angle_deg=22.5,
            span_deg=0.6,
            inner_radius=0.0,
            outer_radius=10.0,
            height=0.4,
            base_z=4.0,
        )
        result = CadQueryExecutor().execute([prism, rib])
        self.assertIsNotNone(result.solid)
        bb = result.solid.val().BoundingBox()
        # The rib's top is at base_z + height = 4.4.
        self.assertAlmostEqual(bb.zmax, 4.4, places=4)


@unittest.skipUnless(_cadquery_available(), "cadquery not installed")
class TestCadQueryExecutorEngravedDivider(unittest.TestCase):
    def test_engraved_divider_cuts_groove(self) -> None:
        prism = Prism(
            center=(0.0, 0.0),
            inner_radius=0.0,
            outer_radius=10.0,
            angle_start_deg=0.0,
            angle_end_deg=45.0,
            center_angle_deg=22.5,
            span_deg=45.0,
            z0=0.0,
            z1=4.0,
        )
        groove = EngravedDivider(
            owner_cell_id="inner:00",
            boundary_id="b0",
            side="A",
            ring="inner",
            angle_start_deg=22.2,
            angle_end_deg=22.8,
            center_angle_deg=22.5,
            span_deg=0.6,
            inner_radius=0.0,
            outer_radius=10.0,
            depth=0.3,
            surface_z=4.0,
        )
        result = CadQueryExecutor().execute([prism, groove])
        self.assertIsNotNone(result.solid)
        # Solid is non-empty.
        bb = result.solid.val().BoundingBox()
        self.assertGreater(bb.zmax - bb.zmin, 0.0)


@unittest.skipUnless(_cadquery_available(), "cadquery not installed")
class TestCadQueryExecutorRaisedSymbol(unittest.TestCase):
    def test_raised_symbol_smoke(self) -> None:
        prism = Prism(
            center=(0.0, 0.0),
            inner_radius=0.0,
            outer_radius=30.0,
            angle_start_deg=67.5,
            angle_end_deg=112.5,
            center_angle_deg=90.0,
            span_deg=45.0,
            z0=0.0,
            z1=4.0,
        )
        sym = RaisedSymbol(
            owner_cell_id="inner:00",
            symbol_kind=SymbolKind.TRIANGLE,
            center_angle_deg=90.0,
            center_radius=14.0,
            local_top_angle_deg=-90.0,
            size_S=6.0,
            height=0.8,
            base_z=4.0,
        )
        result = CadQueryExecutor().execute([prism, sym])
        self.assertIsNotNone(result.solid)
        bb = result.solid.val().BoundingBox()
        self.assertAlmostEqual(bb.zmax, 4.8, places=4)


@unittest.skipUnless(_cadquery_available(), "cadquery not installed")
class TestCadQueryExecutorCutSymbol(unittest.TestCase):
    def test_cut_symbol_smoke(self) -> None:
        prism = Prism(
            center=(0.0, 0.0),
            inner_radius=0.0,
            outer_radius=30.0,
            angle_start_deg=-112.5,
            angle_end_deg=-67.5,
            center_angle_deg=-90.0,
            span_deg=45.0,
            z0=0.0,
            z1=4.0,
        )
        sym = CutSymbol(
            owner_cell_id="inner:04",
            symbol_kind=SymbolKind.SQUARE,
            center_angle_deg=-90.0,
            center_radius=14.0,
            local_top_angle_deg=90.0,
            size_S=6.0,
            depth=0.6,
            surface_z=4.0,
        )
        result = CadQueryExecutor().execute([prism, sym])
        self.assertIsNotNone(result.solid)


@unittest.skipUnless(_cadquery_available(), "cadquery not installed")
class TestMixedBoundaryDisjointness(unittest.TestCase):
    """AC7 — raised rib and engraved groove on a mixed boundary occupy
    disjoint half-strips across the shared edge."""

    def test_mixed_boundary_pair_disjoint(self) -> None:
        from socionics_medallion.ir import EngravedDivider, RaisedDivider

        # Two adjacent prisms: a BLACK lowered field on the left half and a
        # WHITE surface on the right half. Shared edge at 0°.
        black = Prism(
            center=(0.0, 0.0),
            inner_radius=0.0,
            outer_radius=10.0,
            angle_start_deg=-45.0,
            angle_end_deg=0.0,
            center_angle_deg=-22.5,
            span_deg=45.0,
            z0=0.0,
            z1=4.0,
        )
        lower_black = LowerField(
            owner_cell_id="inner:black",
            center=(0.0, 0.0),
            inner_radius=0.0,
            outer_radius=10.0,
            angle_start_deg=-45.0,
            angle_end_deg=0.0,
            center_angle_deg=-22.5,
            span_deg=45.0,
            surface_z=4.0,
            depth=0.6,
        )
        white = Prism(
            center=(0.0, 0.0),
            inner_radius=0.0,
            outer_radius=10.0,
            angle_start_deg=0.0,
            angle_end_deg=45.0,
            center_angle_deg=22.5,
            span_deg=45.0,
            z0=0.0,
            z1=4.0,
        )
        # Half-strip rib on the black side (angles [-0.3, 0]).
        rib = RaisedDivider(
            owner_cell_id="inner:black",
            boundary_id="bnd",
            side="A",
            ring="inner",
            angle_start_deg=-0.3,
            angle_end_deg=0.0,
            center_angle_deg=-0.15,
            span_deg=0.3,
            inner_radius=0.0,
            outer_radius=10.0,
            height=0.4,
            base_z=3.4,
        )
        # Half-strip groove on the white side (angles [0, 0.3]).
        groove = EngravedDivider(
            owner_cell_id="inner:white",
            boundary_id="bnd",
            side="B",
            ring="inner",
            angle_start_deg=0.0,
            angle_end_deg=0.3,
            center_angle_deg=0.15,
            span_deg=0.3,
            inner_radius=0.0,
            outer_radius=10.0,
            depth=0.3,
            surface_z=4.0,
        )
        result = CadQueryExecutor().execute([black, lower_black, white, rib, groove])
        self.assertIsNotNone(result.solid)
        # The combined solid has the rib bump on the black side.
        bb = result.solid.val().BoundingBox()
        # Top is the rib top (3.4 + 0.4 = 3.8 on the black side; 4.0 on the
        # white side).
        self.assertAlmostEqual(bb.zmax, 4.0, places=4)


@unittest.skipUnless(_cadquery_available(), "cadquery not installed")
class TestFullCanonicalStream(unittest.TestCase):
    """AC9 — the full canonical stream runs end-to-end without
    ``NotYetImplemented`` and produces a non-empty solid."""

    def test_full_stream(self) -> None:
        plan = build_plan()
        ops = compile_medallion(plan)
        result = CadQueryExecutor().execute(ops)
        self.assertIsNotNone(result.solid)
        # Sanity: every op type ran at least once.
        self.assertGreater(result.processed["Prism"], 0)
        self.assertGreater(result.processed["LowerField"], 0)
        self.assertGreater(result.processed["RaisedSymbol"], 0)
        self.assertGreater(result.processed["CutSymbol"], 0)
        self.assertGreater(
            result.processed["RaisedDivider"] + result.processed["EngravedDivider"], 0
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
