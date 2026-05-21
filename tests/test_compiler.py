"""Tests for socionics_medallion.compiler.

Verifies the compiler produces the canonical instruction stream for the
canonical plan, is deterministic, and never imports cadquery.
"""

from __future__ import annotations

import json
import os
import subprocess
import unittest
from collections import Counter

from socionics_medallion import ir
from socionics_medallion.compiler import compile_medallion
from socionics_medallion.ir import (
    CutSymbol,
    EngravedDivider,
    LowerField,
    Prism,
    RaisedDivider,
    RaisedSymbol,
)
from socionics_medallion.plan import build_plan


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
        # Also identical when re-serialized:
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
        # 4 black inner + 8 black outer = 12 raised symbols.
        self.assertEqual(self.by_type["RaisedSymbol"], 12)

    def test_cut_symbols_match_white_cells(self) -> None:
        # 4 white inner + 8 white outer = 12 cut symbols.
        self.assertEqual(self.by_type["CutSymbol"], 12)

    def test_some_dividers_exist(self) -> None:
        self.assertGreater(
            self.by_type["RaisedDivider"] + self.by_type["EngravedDivider"], 0
        )


class TestPolarityInvariants(unittest.TestCase):
    """Issue #1 AC5/AC6: black aspects raised, white aspects cut."""

    def setUp(self) -> None:
        self.plan = build_plan()
        self.ops = compile_medallion(self.plan)

    def test_raised_symbols_are_only_for_black_cells(self) -> None:
        # Build cell-by-label lookup including outer cell_ids.
        cells_by_id = {c.label: c for c in self.plan.inner_cells}
        for o in self.plan.outer_cells:
            cells_by_id[o.cell_id] = o

        # Each RaisedSymbol's center_angle_deg must align with a BLACK cell;
        # each CutSymbol's must align with a WHITE cell.
        for op in self.ops:
            if isinstance(op, RaisedSymbol):
                self.assertTrue(
                    self._cell_at_angle(op.center_angle_deg, "BLACK"),
                    f"RaisedSymbol at angle={op.center_angle_deg} not over a black cell",
                )
            elif isinstance(op, CutSymbol):
                self.assertTrue(
                    self._cell_at_angle(op.center_angle_deg, "WHITE"),
                    f"CutSymbol at angle={op.center_angle_deg} not over a white cell",
                )

    def _cell_at_angle(self, angle_deg: float, expected_polarity: str) -> bool:
        cells = list(self.plan.inner_cells) + list(self.plan.outer_cells)
        for c in cells:
            if _angle_within(angle_deg, c.start_angle_deg, c.end_angle_deg):
                if c.polarity.name == expected_polarity:
                    return True
        return False


def _angle_within(angle_deg: float, start: float, end: float) -> bool:
    """Test if angle is inside the (CCW) arc [start, end] modulo 360."""
    a = angle_deg % 360.0
    s = start % 360.0
    e = end % 360.0
    if s <= e:
        return s - 1e-9 <= a <= e + 1e-9
    # Wraps around 360.
    return a >= s - 1e-9 or a <= e + 1e-9


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


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
