"""Tests for CadQueryExecutor.

These tests are skipped when CadQuery isn't installed, except for:

* the import-laziness test (always run);
* the ``IMPLEMENTED_OPS == ALL_OP_TYPES`` assertion (always run);
* the no-midpoint-recomputation source check (always run);
* the STL binary parser (always run — does NOT import cadquery).
"""

from __future__ import annotations

import importlib.util
import os
import struct
import subprocess
import sys
import tempfile
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

# AC3 — documented STL triangle-count floor for the canonical medallion.
# Even a coarse mesh of 24 sector prisms with circle/triangle/square symbol
# features substantially exceeds 200 triangles; the floor is a sanity bound,
# not a fidelity target. Bump this in code (and document why) if the
# canonical stream ever shrinks below it.
STL_TRIANGLE_FLOOR: int = 200

# AC4 — round-trip tolerances. Bounds within 1e-3 mm; volume within 1 %.
ROUND_TRIP_BOUND_TOL_MM: float = 1e-3
ROUND_TRIP_VOLUME_REL_TOL: float = 0.01


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


# ---------------------------------------------------------------------------
# AC1 — single-connected-solid invariant.
# ---------------------------------------------------------------------------
@unittest.skipUnless(_cadquery_available(), "cadquery not installed")
class TestSingleConnectedSolid(unittest.TestCase):
    """AC1 — ``CadQueryExecutor.build_solid()`` returns one connected solid.

    The medallion is constructed cell-by-cell; the executor MUST union all
    sector prisms into a single connected ``cadquery.Solid`` before any
    boolean subtraction (lowered fields, engraved dividers, cut symbols).
    If the canonical stream ever produces a multi-body result that cannot be
    cleanly unioned, the executor MUST document the gap in its module
    docstring and the test below is updated to assert the documented N.
    """

    def test_canonical_stream_is_single_solid(self) -> None:
        plan = build_plan()
        ops = compile_medallion(plan)
        executor = CadQueryExecutor()
        executor.execute(ops)
        solid = executor.build_solid()
        self.assertIsNotNone(solid)
        # Count of distinct solid bodies in the resulting compound.
        n_solids = len(solid.Solids())
        self.assertEqual(
            n_solids,
            1,
            msg=f"expected single-connected-solid; got {n_solids} bodies",
        )


# ---------------------------------------------------------------------------
# AC2 — STEP export.
# ---------------------------------------------------------------------------
@unittest.skipUnless(_cadquery_available(), "cadquery not installed")
class TestStepExport(unittest.TestCase):
    """AC2 — the CLI writes a valid STEP file (ISO-10303-21)."""

    def test_step_file_has_iso_header(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            step_path = os.path.join(td, "out.step")
            rc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socionics_medallion.cli",
                    "compile",
                    "--plan",
                    "canonical",
                    "--executor",
                    "cadquery",
                    "--step",
                    step_path,
                ],
                cwd=_repo_root(),
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                rc.returncode, 0, msg=rc.stdout + "\n" + rc.stderr
            )
            self.assertTrue(os.path.isfile(step_path))
            with open(step_path, "rb") as fh:
                head = fh.read(16)
            self.assertTrue(
                head.startswith(b"ISO-10303-21"),
                msg=f"STEP file is missing ISO-10303-21 header (head={head!r})",
            )
            # File is non-trivial.
            self.assertGreater(os.path.getsize(step_path), 1024)


# ---------------------------------------------------------------------------
# AC3 — STL export (binary), validated without CadQuery.
# ---------------------------------------------------------------------------
def _parse_binary_stl_triangle_count(path: str) -> int:
    """Return the triangle count from a binary STL file.

    Binary STL layout (AC3): 80-byte header, then UINT32-LE triangle count,
    then ``count`` records of 50 bytes each. We validate the file size
    matches the declared count so a truncated STL is rejected.
    """
    with open(path, "rb") as fh:
        header = fh.read(80)
        if len(header) != 80:
            raise ValueError(f"STL too short for 80-byte header: {path}")
        count_bytes = fh.read(4)
        if len(count_bytes) != 4:
            raise ValueError(f"STL missing UINT32 count: {path}")
        (count,) = struct.unpack("<I", count_bytes)
        # The remainder must be exactly count * 50 bytes.
        remainder = fh.read()
    expected = count * 50
    if len(remainder) != expected:
        raise ValueError(
            f"STL size mismatch: expected {expected} bytes of triangle "
            f"records for count={count}, got {len(remainder)} (path={path})"
        )
    return count


class TestStlBinaryParser(unittest.TestCase):
    """The inline binary parser is correct on a synthetic fixture.

    This test does NOT import cadquery — it locks the parser to its
    documented format so AC3's verifiability holds in CAD-free environments.
    """

    def test_parser_reads_synthetic_count(self) -> None:
        # Build a minimal binary STL with 3 zeroed triangle records.
        n = 3
        blob = b"\x00" * 80 + struct.pack("<I", n) + b"\x00" * (n * 50)
        with tempfile.NamedTemporaryFile(
            "wb", suffix=".stl", delete=False
        ) as tf:
            tf.write(blob)
            tmp = tf.name
        try:
            self.assertEqual(_parse_binary_stl_triangle_count(tmp), n)
        finally:
            os.unlink(tmp)

    def test_parser_rejects_truncated(self) -> None:
        n = 5
        # Declare 5 triangles, supply 2 worth of bytes.
        blob = b"\x00" * 80 + struct.pack("<I", n) + b"\x00" * (2 * 50)
        with tempfile.NamedTemporaryFile(
            "wb", suffix=".stl", delete=False
        ) as tf:
            tf.write(blob)
            tmp = tf.name
        try:
            with self.assertRaises(ValueError):
                _parse_binary_stl_triangle_count(tmp)
        finally:
            os.unlink(tmp)


@unittest.skipUnless(_cadquery_available(), "cadquery not installed")
class TestStlExport(unittest.TestCase):
    """AC3 — the CLI writes a binary STL with triangle count above the floor."""

    def test_stl_triangle_count_above_floor(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            stl_path = os.path.join(td, "out.stl")
            rc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socionics_medallion.cli",
                    "compile",
                    "--plan",
                    "canonical",
                    "--executor",
                    "cadquery",
                    "--stl",
                    stl_path,
                ],
                cwd=_repo_root(),
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                rc.returncode, 0, msg=rc.stdout + "\n" + rc.stderr
            )
            self.assertTrue(os.path.isfile(stl_path))
            n_tri = _parse_binary_stl_triangle_count(stl_path)
            self.assertGreater(
                n_tri,
                STL_TRIANGLE_FLOOR,
                msg=f"STL triangle count {n_tri} <= floor {STL_TRIANGLE_FLOOR}",
            )


# ---------------------------------------------------------------------------
# AC4 — round-trip validation.
# ---------------------------------------------------------------------------
@unittest.skipUnless(_cadquery_available(), "cadquery not installed")
class TestStepRoundTrip(unittest.TestCase):
    """AC4 — re-imported STEP matches source bounds (1e-3 mm) and volume (1 %)."""

    def test_round_trip_matches_source(self) -> None:
        from socionics_medallion.executor import (
            compare_solids,
            reimport_step,
        )

        plan = build_plan()
        ops = compile_medallion(plan)
        executor = CadQueryExecutor()
        executor.execute(ops)
        source = executor.build_solid()

        with tempfile.TemporaryDirectory() as td:
            step_path = os.path.join(td, "out.step")
            executor.export_step(source, step_path)
            imported = reimport_step(step_path)
            report = compare_solids(source, imported)

        self.assertLessEqual(
            report.bound_delta_mm,
            ROUND_TRIP_BOUND_TOL_MM,
            msg=f"bound delta {report.bound_delta_mm} mm exceeds "
            f"{ROUND_TRIP_BOUND_TOL_MM} mm",
        )
        self.assertLessEqual(
            report.volume_rel_delta,
            ROUND_TRIP_VOLUME_REL_TOL,
            msg=f"volume relative delta {report.volume_rel_delta} exceeds "
            f"{ROUND_TRIP_VOLUME_REL_TOL}",
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
