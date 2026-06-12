"""Tests for socionics_medallion.plan."""

from __future__ import annotations

import math
import unittest

from socionics_medallion import plan as plan_mod
from socionics_medallion.plan import (
    INNER_SECTOR_DEG,
    INNER_SECTORS,
    OUTER_SECTOR_DEG,
    OUTER_SECTORS,
    Aspect,
    Polarity,
    SymbolKind,
    build_plan,
)


CLOCKWISE_INNER_LABELS = ["ЧИ", "ЧС", "ЧЛ", "ЧЭ", "БИ", "БС", "БЛ", "БЭ"]

# Outer-mapping from issue #1 AC4.
OUTER_MAPPING = {
    "ЧИ": ("БЛ", "БЭ"),
    "ЧС": ("БЛ", "БЭ"),
    "ЧЛ": ("БИ", "БС"),
    "ЧЭ": ("БИ", "БС"),
    "БИ": ("ЧЛ", "ЧЭ"),
    "БС": ("ЧЛ", "ЧЭ"),
    "БЛ": ("ЧИ", "ЧС"),
    "БЭ": ("ЧИ", "ЧС"),
}


def _aspect_of(code: str) -> str:
    return code[1]


def _polarity_of(code: str) -> str:
    return "BLACK" if code[0] == "Ч" else "WHITE"


def _symbol_kind_of(code: str) -> str:
    return {
        "И": "TRIANGLE",
        "С": "CIRCLE",
        "Л": "SQUARE",
        "Э": "ETHICS",
    }[_aspect_of(code)]


class TestPlanConstants(unittest.TestCase):
    def test_inner_outer_sector_counts(self) -> None:
        self.assertEqual(INNER_SECTORS, 8)
        self.assertEqual(OUTER_SECTORS, 16)

    def test_sector_widths(self) -> None:
        self.assertAlmostEqual(INNER_SECTOR_DEG, 45.0)
        self.assertAlmostEqual(OUTER_SECTOR_DEG, 22.5)

    def test_geometric_constants_present(self) -> None:
        for name in (
            "INNER_OUTER_RADIUS",
            "OUTER_RING_RADIUS",
            "MEDALLION_HEIGHT",
            "FIELD_LOWER_DEPTH",
            "SYMBOL_HEIGHT",
            "SYMBOL_CUT_DEPTH",
            "DIVIDER_HEIGHT",
            "DIVIDER_DEPTH",
            "DIVIDER_WIDTH_DEG",
            "INNER_HUB_RADIUS",
        ):
            self.assertTrue(
                hasattr(plan_mod, name), f"plan module missing constant: {name}"
            )


class TestPlanEnums(unittest.TestCase):
    def test_polarity_members(self) -> None:
        self.assertEqual({p.name for p in Polarity}, {"BLACK", "WHITE"})

    def test_aspect_members(self) -> None:
        self.assertEqual({a.name for a in Aspect}, {"I", "S", "L", "E"})

    def test_symbol_kind_members(self) -> None:
        self.assertEqual(
            {k.name for k in SymbolKind},
            {"SQUARE", "CIRCLE", "TRIANGLE", "ETHICS"},
        )


class TestBuildPlan(unittest.TestCase):
    def test_returns_plan_with_required_attrs(self) -> None:
        plan = build_plan()
        for attr in ("inner_cells", "outer_cells", "symbols", "boundaries"):
            self.assertTrue(
                hasattr(plan, attr), f"plan missing attribute: {attr}"
            )

    def test_inner_cell_count(self) -> None:
        plan = build_plan()
        self.assertEqual(len(plan.inner_cells), 8)

    def test_outer_cell_count(self) -> None:
        plan = build_plan()
        self.assertEqual(len(plan.outer_cells), 16)

    def test_inner_clockwise_ordering(self) -> None:
        """ЧИ→ЧС→ЧЛ→ЧЭ→БИ→БС→БЛ→БЭ clockwise from 12:00."""
        plan = build_plan()
        codes = [c.function_code for c in plan.inner_cells]
        self.assertEqual(codes, CLOCKWISE_INNER_LABELS)

    def test_inner_first_cell_is_at_top(self) -> None:
        """First inner cell (ЧИ) is centered at 12:00 (90°)."""
        plan = build_plan()
        first = plan.inner_cells[0]
        self.assertAlmostEqual(first.center_angle_deg % 360.0, 90.0, places=6)

    def test_inner_angular_widths(self) -> None:
        plan = build_plan()
        for c in plan.inner_cells:
            self.assertAlmostEqual(c.span_deg, 45.0, places=6)

    def test_inner_polarity_consistent_with_label(self) -> None:
        plan = build_plan()
        for c in plan.inner_cells:
            self.assertEqual(c.polarity.name, _polarity_of(c.function_code))

    def test_inner_aspect_consistent_with_label(self) -> None:
        plan = build_plan()
        aspect_letter = {"I": "И", "S": "С", "L": "Л", "E": "Э"}
        for c in plan.inner_cells:
            self.assertEqual(aspect_letter[c.aspect.name], _aspect_of(c.function_code))

    def test_inner_opposites_180_apart(self) -> None:
        from socionics_medallion.ir import normalized_angle_delta_deg

        plan = build_plan()
        opposites = {"ЧИ": "БИ", "ЧС": "БС", "ЧЛ": "БЛ", "ЧЭ": "БЭ"}
        by_code = {c.function_code: c for c in plan.inner_cells}
        for a, b in opposites.items():
            delta = normalized_angle_delta_deg(
                by_code[a].center_angle_deg, by_code[b].center_angle_deg
            )
            self.assertAlmostEqual(abs(delta), 180.0, places=6)

    def test_outer_polarity_opposite_to_inner_parent(self) -> None:
        plan = build_plan()
        inner_by_id = {c.cell_id: c for c in plan.inner_cells}
        for o in plan.outer_cells:
            parent = inner_by_id[o.parent_cell_id]
            self.assertNotEqual(o.polarity, parent.polarity)

    def test_outer_mapping_exactly_matches_AC4(self) -> None:
        plan = build_plan()
        inner_by_id = {c.cell_id: c for c in plan.inner_cells}
        grouped: dict[str, list[str]] = {}
        for o in plan.outer_cells:
            parent_code = inner_by_id[o.parent_cell_id].function_code
            grouped.setdefault(parent_code, []).append(o.function_code)
        for parent_code, children_codes in grouped.items():
            expected = set(OUTER_MAPPING[parent_code])
            self.assertEqual(
                set(children_codes), expected, f"parent={parent_code}"
            )

    def test_outer_two_cells_per_inner(self) -> None:
        plan = build_plan()
        from collections import Counter

        counts = Counter(o.parent_cell_id for o in plan.outer_cells)
        for parent, n in counts.items():
            self.assertEqual(n, 2, f"parent={parent} has {n} children")

    def test_outer_cells_above_parent_half_spans(self) -> None:
        """Each outer cell's angular span is one half of its parent inner cell."""
        plan = build_plan()
        inner_by_id = {c.cell_id: c for c in plan.inner_cells}
        for o in plan.outer_cells:
            parent = inner_by_id[o.parent_cell_id]
            mid = (parent.start_angle_deg + parent.end_angle_deg) / 2.0
            left_match = (
                math.isclose(o.start_angle_deg, parent.start_angle_deg, abs_tol=1e-9)
                and math.isclose(o.end_angle_deg, mid, abs_tol=1e-9)
            )
            right_match = (
                math.isclose(o.start_angle_deg, mid, abs_tol=1e-9)
                and math.isclose(o.end_angle_deg, parent.end_angle_deg, abs_tol=1e-9)
            )
            self.assertTrue(
                left_match or right_match,
                f"outer={o.cell_id} parent={parent.cell_id}",
            )

    def test_symbol_per_cell(self) -> None:
        """Each of the 8 inner + 16 outer cells gets one symbol = 24 total."""
        plan = build_plan()
        self.assertEqual(len(plan.symbols), 24)

    def test_symbol_kinds_follow_aspect(self) -> None:
        plan = build_plan()
        cells_by_id = {c.cell_id: c for c in plan.inner_cells}
        cells_by_id.update({c.cell_id: c for c in plan.outer_cells})
        for sym in plan.symbols:
            owner = cells_by_id[sym.cell_id]
            expected = _symbol_kind_of(owner.function_code)
            self.assertEqual(sym.kind.name, expected, f"cell_id={sym.cell_id}")

    def test_boundaries_present(self) -> None:
        plan = build_plan()
        # 8 inner + 16 outer = 24 inter-cell boundaries.
        self.assertEqual(len(plan.boundaries), INNER_SECTORS + OUTER_SECTORS)


# ---------------------------------------------------------------------------
# AC1 — cell_id is unique and distinct from function_code.
# ---------------------------------------------------------------------------
class TestCellIdUniqueness(unittest.TestCase):
    def test_all_24_cell_ids_unique(self) -> None:
        plan = build_plan()
        all_ids = [c.cell_id for c in plan.inner_cells] + [
            c.cell_id for c in plan.outer_cells
        ]
        self.assertEqual(len(all_ids), 24)
        self.assertEqual(len(set(all_ids)), 24)

    def test_outer_function_codes_collide_by_design(self) -> None:
        plan = build_plan()
        outer_codes = [c.function_code for c in plan.outer_cells]
        # 16 outer cells share only 8 distinct function codes.
        self.assertEqual(len(set(outer_codes)), 8)

    def test_inner_function_codes_are_distinct(self) -> None:
        plan = build_plan()
        inner_codes = [c.function_code for c in plan.inner_cells]
        self.assertEqual(len(set(inner_codes)), 8)

    def test_cell_id_never_equals_function_code(self) -> None:
        plan = build_plan()
        for c in list(plan.inner_cells) + list(plan.outer_cells):
            self.assertNotEqual(
                c.cell_id,
                c.function_code,
                f"cell_id collides with function_code: {c.cell_id}",
            )

    def test_inner_cell_id_scheme(self) -> None:
        plan = build_plan()
        expected = [f"inner:{i:02d}" for i in range(8)]
        actual = [c.cell_id for c in plan.inner_cells]
        self.assertEqual(actual, expected)

    def test_outer_cell_id_scheme(self) -> None:
        plan = build_plan()
        ids = sorted(c.cell_id for c in plan.outer_cells)
        expected = sorted(f"outer:{i:02d}" for i in range(16))
        self.assertEqual(ids, expected)


class TestPlanImportPurity(unittest.TestCase):
    """plan.py must not import cadquery (verified out-of-process)."""

    def test_no_cadquery_in_sys_modules_after_import(self) -> None:
        import subprocess

        result = subprocess.run(
            [
                "python3",
                "-c",
                "import sys; import socionics_medallion.plan; "
                "assert 'cadquery' not in sys.modules, sorted(sys.modules)",
            ],
            cwd=_repo_root(),
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode, 0, msg=result.stdout + "\n" + result.stderr
        )


def _repo_root() -> str:
    import os

    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
