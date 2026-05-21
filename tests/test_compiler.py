"""Tests for socionics_medallion.compiler.

Verifies the compiler produces the canonical instruction stream for the
canonical plan, is deterministic, never imports cadquery, and satisfies
the cycle-3 ACs (cell_id propagation, angle quartet, divider ownership,
mixed-boundary disjointness, symbol orientation).
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import unittest
from collections import Counter
from dataclasses import fields

from socionics_medallion import ir
from socionics_medallion.compiler import compile_medallion, is_opposite_angle
from socionics_medallion.ir import (
    ANGLE_QUARTET_FIELDS,
    ANGULAR_OP_TYPES,
    CutSymbol,
    DividerTreatment,
    EngravedDivider,
    LowerField,
    Prism,
    RaisedDivider,
    RaisedSymbol,
    normalized_angle_delta_deg,
)
from socionics_medallion.plan import (
    INNER_SECTORS,
    OUTER_SECTORS,
    Polarity,
    build_plan,
)


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _fixture_path() -> str:
    return os.path.join(_repo_root(), "tests", "fixtures", "canonical_stream.json")


class TestCompilerImportPurity(unittest.TestCase):
    def test_no_cadquery_after_import(self) -> None:
        result = subprocess.run(
            [
                "python3",
                "-c",
                "import sys; import socionics_medallion.compiler; "
                "assert 'cadquery' not in sys.modules, sorted(sys.modules)",
            ],
            cwd=_repo_root(),
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode, 0, msg=result.stdout + "\n" + result.stderr
        )

    def test_compiler_does_not_import_executor(self) -> None:
        result = subprocess.run(
            [
                "python3",
                "-c",
                "import sys; import socionics_medallion.compiler; "
                "assert 'socionics_medallion.executor' not in sys.modules, sorted(sys.modules)",
            ],
            cwd=_repo_root(),
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode, 0, msg=result.stdout + "\n" + result.stderr
        )


class TestCompilerDeterminism(unittest.TestCase):
    def test_compile_twice_byte_identical(self) -> None:
        plan = build_plan()
        a = compile_medallion(plan)
        b = compile_medallion(plan)
        self.assertEqual(a, b)
        ja = json.dumps([ir.op_to_dict(o) for o in a], sort_keys=True)
        jb = json.dumps([ir.op_to_dict(o) for o in b], sort_keys=True)
        self.assertEqual(ja, jb)


class TestCompilerCounts(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = build_plan()
        self.ops = compile_medallion(self.plan)
        self.by_type: Counter = Counter(type(o).__name__ for o in self.ops)

    def test_prism_count(self) -> None:
        # 8 inner + 16 outer = 24 sector prisms.
        self.assertEqual(self.by_type["Prism"], 24)

    def test_lower_field_count(self) -> None:
        # 4 black inner (Ч*) + 8 black outer = 12 lowered fields.
        self.assertEqual(self.by_type["LowerField"], 12)

    def test_symbol_total(self) -> None:
        raised = self.by_type["RaisedSymbol"]
        cut = self.by_type["CutSymbol"]
        self.assertEqual(raised + cut, 24)

    def test_raised_symbols_match_black_cells(self) -> None:
        self.assertEqual(self.by_type["RaisedSymbol"], 12)

    def test_cut_symbols_match_white_cells(self) -> None:
        self.assertEqual(self.by_type["CutSymbol"], 12)

    def test_some_dividers_exist(self) -> None:
        self.assertGreater(
            self.by_type["RaisedDivider"] + self.by_type["EngravedDivider"], 0
        )


class TestPolarityInvariants(unittest.TestCase):
    """Issue #1 AC5/AC6: black aspects raised, white aspects cut.

    After AC1 the polarity check is via ``owner_cell_id`` rather than
    angle lookup — angle lookup would have silently picked the wrong cell
    when the outer ring had function-code collisions.
    """

    def setUp(self) -> None:
        self.plan = build_plan()
        self.ops = compile_medallion(self.plan)
        self.cells_by_id = {c.cell_id: c for c in self.plan.inner_cells}
        self.cells_by_id.update({c.cell_id: c for c in self.plan.outer_cells})

    def test_raised_symbols_are_owned_by_black_cells(self) -> None:
        for op in self.ops:
            if isinstance(op, RaisedSymbol):
                owner = self.cells_by_id[op.owner_cell_id]
                self.assertEqual(owner.polarity, Polarity.BLACK)

    def test_cut_symbols_are_owned_by_white_cells(self) -> None:
        for op in self.ops:
            if isinstance(op, CutSymbol):
                owner = self.cells_by_id[op.owner_cell_id]
                self.assertEqual(owner.polarity, Polarity.WHITE)


class TestGoldenStream(unittest.TestCase):
    def test_matches_golden_fixture(self) -> None:
        path = _fixture_path()
        self.assertTrue(os.path.exists(path), f"golden file missing: {path}")
        with open(path, "r", encoding="utf-8") as f:
            golden = json.load(f)
        plan = build_plan()
        ops = compile_medallion(plan)
        compiled = [ir.op_to_dict(o) for o in ops]
        self.assertEqual(compiled, golden)


# ---------------------------------------------------------------------------
# AC2 — every angular-extent op in the compiled stream carries the quartet,
# with self-consistent values (start + span = end modulo wrap; center is
# inside the arc).
# ---------------------------------------------------------------------------
class TestAngleQuartetInCompiledStream(unittest.TestCase):
    def setUp(self) -> None:
        self.ops = compile_medallion(build_plan())

    def test_every_angular_op_has_quartet(self) -> None:
        for op in self.ops:
            if not isinstance(op, ANGULAR_OP_TYPES):
                continue
            for fname in ANGLE_QUARTET_FIELDS:
                self.assertTrue(
                    hasattr(op, fname),
                    f"{type(op).__name__} missing {fname}",
                )

    def test_quartet_self_consistency(self) -> None:
        for op in self.ops:
            if not isinstance(op, ANGULAR_OP_TYPES):
                continue
            start = op.angle_start_deg  # type: ignore[attr-defined]
            end = op.angle_end_deg  # type: ignore[attr-defined]
            center = op.center_angle_deg  # type: ignore[attr-defined]
            span = op.span_deg  # type: ignore[attr-defined]
            self.assertGreater(span, 0.0)
            # Compare end ≈ start + span using normalized delta (wrap-safe).
            delta = normalized_angle_delta_deg(end, start + span)
            self.assertAlmostEqual(delta, 0.0, places=6, msg=str(op))
            # Center is inside the arc (via normalized deltas).
            half = span / 2.0
            d_center = abs(normalized_angle_delta_deg(center, start + half))
            self.assertLess(d_center, 1e-6, msg=str(op))


# ---------------------------------------------------------------------------
# AC2 — no '(start + end) / 2' midpoint recomputation in executor source.
# ---------------------------------------------------------------------------
class TestNoMidpointRecomputationInExecutor(unittest.TestCase):
    def test_executor_source_does_not_recompute_midpoint(self) -> None:
        path = os.path.join(_repo_root(), "socionics_medallion", "executor.py")
        with open(path, "r", encoding="utf-8") as f:
            src = f.read()
        # Bare midpoint formula must never appear.
        self.assertNotIn("(start + end) / 2", src)
        self.assertNotIn("(start+end)/2", src)
        # Field-named variant is also forbidden.
        self.assertNotIn("(op.angle_start_deg + op.angle_end_deg) / 2", src)


# ---------------------------------------------------------------------------
# AC3 — divider ownership multiplicity + non-overlap on mixed boundaries.
# ---------------------------------------------------------------------------
class TestDividerOwnershipPerBoundary(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = build_plan()
        self.ops = compile_medallion(self.plan)
        self.cells_by_id = {c.cell_id: c for c in self.plan.inner_cells}
        self.cells_by_id.update({c.cell_id: c for c in self.plan.outer_cells})
        self.boundaries_by_id = {b.boundary_id: b for b in self.plan.boundaries}
        self.divider_ops = [
            op for op in self.ops if isinstance(op, (RaisedDivider, EngravedDivider))
        ]

    def test_every_divider_has_owner(self) -> None:
        for op in self.divider_ops:
            self.assertTrue(op.owner_cell_id, f"divider missing owner: {op}")
            self.assertIn(op.owner_cell_id, self.cells_by_id)

    def test_every_divider_has_boundary_id(self) -> None:
        for op in self.divider_ops:
            self.assertIn(op.boundary_id, self.boundaries_by_id)

    def test_raised_divider_owners_are_black(self) -> None:
        for op in self.divider_ops:
            if isinstance(op, RaisedDivider):
                self.assertEqual(
                    self.cells_by_id[op.owner_cell_id].polarity,
                    Polarity.BLACK,
                    f"RaisedDivider owner not black: {op.owner_cell_id}",
                )

    def test_engraved_divider_owners_are_white(self) -> None:
        for op in self.divider_ops:
            if isinstance(op, EngravedDivider):
                self.assertEqual(
                    self.cells_by_id[op.owner_cell_id].polarity,
                    Polarity.WHITE,
                    f"EngravedDivider owner not white: {op.owner_cell_id}",
                )

    def test_treatment_field_matches_op_type(self) -> None:
        for op in self.divider_ops:
            if isinstance(op, RaisedDivider):
                self.assertEqual(op.treatment, DividerTreatment.RAISED_RIB)
            else:
                self.assertEqual(op.treatment, DividerTreatment.ENGRAVED_GROOVE)

    def test_per_boundary_op_multiplicity(self) -> None:
        ops_per_bid: dict[str, list] = {}
        for op in self.divider_ops:
            ops_per_bid.setdefault(op.boundary_id, []).append(op)

        for bid, ops in ops_per_bid.items():
            boundary = self.boundaries_by_id[bid]
            pa, pb = boundary.polarity_a, boundary.polarity_b
            if pa is Polarity.BLACK and pb is Polarity.BLACK:
                self.assertEqual(
                    len(ops),
                    1,
                    f"BB boundary {bid} expects 1 op, got {len(ops)}",
                )
                self.assertIsInstance(ops[0], RaisedDivider)
            elif pa is Polarity.WHITE and pb is Polarity.WHITE:
                self.assertEqual(
                    len(ops),
                    1,
                    f"WW boundary {bid} expects 1 op, got {len(ops)}",
                )
                self.assertIsInstance(ops[0], EngravedDivider)
            else:
                # Mixed: exactly one raised + one engraved.
                self.assertEqual(
                    len(ops),
                    2,
                    f"mixed boundary {bid} expects 2 ops, got {len(ops)}",
                )
                kinds = {type(o).__name__ for o in ops}
                self.assertEqual(kinds, {"RaisedDivider", "EngravedDivider"})

    def test_mixed_boundary_owners_are_distinct(self) -> None:
        ops_per_bid: dict[str, list] = {}
        for op in self.divider_ops:
            ops_per_bid.setdefault(op.boundary_id, []).append(op)

        for bid, ops in ops_per_bid.items():
            boundary = self.boundaries_by_id[bid]
            if boundary.polarity_a == boundary.polarity_b:
                continue
            owners = {o.owner_cell_id for o in ops}
            self.assertEqual(
                len(owners), 2, f"mixed boundary {bid} owners not distinct: {owners}"
            )

    def test_mixed_boundary_geometries_are_disjoint(self) -> None:
        """The raised and engraved ops on a mixed boundary do not overlap
        angularly — the strip is split at the shared edge."""
        ops_per_bid: dict[str, list] = {}
        for op in self.divider_ops:
            ops_per_bid.setdefault(op.boundary_id, []).append(op)

        for bid, ops in ops_per_bid.items():
            boundary = self.boundaries_by_id[bid]
            if boundary.polarity_a == boundary.polarity_b:
                continue
            raised = [o for o in ops if isinstance(o, RaisedDivider)][0]
            engraved = [o for o in ops if isinstance(o, EngravedDivider)][0]
            # Non-overlap: raised.angle_end_deg <= engraved.angle_start_deg
            # OR engraved.angle_end_deg <= raised.angle_start_deg
            disjoint = (
                raised.angle_end_deg <= engraved.angle_start_deg + 1e-9
                or engraved.angle_end_deg <= raised.angle_start_deg + 1e-9
            )
            self.assertTrue(
                disjoint,
                f"mixed boundary {bid} overlap: "
                f"raised=[{raised.angle_start_deg},{raised.angle_end_deg}] "
                f"engraved=[{engraved.angle_start_deg},{engraved.angle_end_deg}]",
            )

    def test_total_divider_op_count_matches_polarity_mix(self) -> None:
        """1 op for each same-polarity boundary + 2 ops for each mixed."""
        expected = 0
        for b in self.plan.boundaries:
            expected += 1 if b.polarity_a == b.polarity_b else 2
        self.assertEqual(len(self.divider_ops), expected)


# ---------------------------------------------------------------------------
# AC5 — symbol orientation: local_top points toward medallion center.
# ---------------------------------------------------------------------------
class TestSymbolOrientation(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = build_plan()
        self.ops = compile_medallion(self.plan)

    def test_local_top_points_to_center(self) -> None:
        """For every symbol op, ``local_top_angle_deg`` is 180° from
        ``center_angle_deg``."""
        for op in self.ops:
            if not isinstance(op, (RaisedSymbol, CutSymbol)):
                continue
            delta = normalized_angle_delta_deg(
                op.local_top_angle_deg, op.center_angle_deg
            )
            self.assertAlmostEqual(
                abs(delta),
                180.0,
                places=6,
                msg=f"{op.owner_cell_id} local_top vs center mismatch",
            )

    def test_symbol_at_12_oclock_top_points_down(self) -> None:
        """A symbol at center_angle 90° (12:00) has local top at -90°."""
        for op in self.ops:
            if not isinstance(op, (RaisedSymbol, CutSymbol)):
                continue
            if abs(normalized_angle_delta_deg(op.center_angle_deg, 90.0)) < 1e-6:
                self.assertAlmostEqual(
                    abs(normalized_angle_delta_deg(op.local_top_angle_deg, -90.0)),
                    0.0,
                    places=6,
                )
                return
        self.fail("no symbol found at center_angle_deg ≈ 90°")


# ---------------------------------------------------------------------------
# AC1 — cell_id propagation: every op that names a cell uses a valid cell_id.
# ---------------------------------------------------------------------------
class TestCellIdPropagation(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = build_plan()
        self.ops = compile_medallion(self.plan)
        self.valid_ids = {c.cell_id for c in self.plan.inner_cells} | {
            c.cell_id for c in self.plan.outer_cells
        }

    def test_lower_field_owner_resolves(self) -> None:
        for op in self.ops:
            if isinstance(op, LowerField):
                self.assertIn(op.owner_cell_id, self.valid_ids)

    def test_symbol_owner_resolves(self) -> None:
        for op in self.ops:
            if isinstance(op, (RaisedSymbol, CutSymbol)):
                self.assertIn(op.owner_cell_id, self.valid_ids)

    def test_divider_owner_resolves(self) -> None:
        for op in self.ops:
            if isinstance(op, (RaisedDivider, EngravedDivider)):
                self.assertIn(op.owner_cell_id, self.valid_ids)


# ---------------------------------------------------------------------------
# Convenience: is_opposite_angle helper.
# ---------------------------------------------------------------------------
class TestIsOppositeAngleHelper(unittest.TestCase):
    def test_classic_pair(self) -> None:
        self.assertTrue(is_opposite_angle(90.0, -90.0))
        self.assertTrue(is_opposite_angle(45.0, -135.0))

    def test_non_pair(self) -> None:
        self.assertFalse(is_opposite_angle(0.0, 0.0))
        self.assertFalse(is_opposite_angle(0.0, 90.0))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
