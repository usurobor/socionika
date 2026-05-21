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


def _aspect_of(label: str) -> str:
    return label[1]


def _polarity_of(label: str) -> str:
    return "BLACK" if label[0] == "Ч" else "WHITE"


def _symbol_kind_of(label: str) -> str:
    return {
        "И": "TRIANGLE",
        "С": "CIRCLE",
        "Л": "SQUARE",
        "Э": "ETHICS",
    }[_aspect_of(label)]


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
        for attr in ("inner_cells", "outer_cells", "symbols", "dividers"):
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
        labels = [c.label for c in plan.inner_cells]
        self.assertEqual(labels, CLOCKWISE_INNER_LABELS)

    def test_inner_first_cell_is_at_top(self) -> None:
        """First inner cell (ЧИ) is centered at 12:00 (90°)."""
        plan = build_plan()
        first = plan.inner_cells[0]
        self.assertAlmostEqual(first.center_angle_deg % 360.0, 90.0, places=6)

    def test_inner_angular_widths(self) -> None:
        plan = build_plan()
        for c in plan.inner_cells:
            self.assertAlmostEqual(
                (c.end_angle_deg - c.start_angle_deg) % 360 or 360,
                45.0,
                places=6,
            )

    def test_inner_polarity_consistent_with_label(self) -> None:
        plan = build_plan()
        for c in plan.inner_cells:
            self.assertEqual(c.polarity.name, _polarity_of(c.label))

    def test_inner_aspect_consistent_with_label(self) -> None:
        plan = build_plan()
        aspect_letter = {"I": "И", "S": "С", "L": "Л", "E": "Э"}
        for c in plan.inner_cells:
            self.assertEqual(aspect_letter[c.aspect.name], _aspect_of(c.label))

    def test_inner_opposites_180_apart(self) -> None:
        plan = build_plan()
        opposites = {"ЧИ": "БИ", "ЧС": "БС", "ЧЛ": "БЛ", "ЧЭ": "БЭ"}
        by_label = {c.label: c for c in plan.inner_cells}
        for a, b in opposites.items():
            diff = (by_label[a].center_angle_deg - by_label[b].center_angle_deg) % 360.0
            # diff should be 180.
            self.assertAlmostEqual(min(diff, 360.0 - diff), 180.0, places=6)

    def test_outer_polarity_opposite_to_inner_parent(self) -> None:
        plan = build_plan()
        inner_by_label = {c.label: c for c in plan.inner_cells}
        for o in plan.outer_cells:
            parent = inner_by_label[o.parent_label]
            self.assertNotEqual(o.polarity, parent.polarity)

    def test_outer_mapping_exactly_matches_AC4(self) -> None:
        plan = build_plan()
        grouped: dict[str, list[str]] = {}
        for o in plan.outer_cells:
            grouped.setdefault(o.parent_label, []).append(o.label)
        for parent, children in grouped.items():
            expected = set(OUTER_MAPPING[parent])
            self.assertEqual(set(children), expected, f"parent={parent}")

    def test_outer_two_cells_per_inner(self) -> None:
        plan = build_plan()
        from collections import Counter

        counts = Counter(o.parent_label for o in plan.outer_cells)
        for parent, n in counts.items():
            self.assertEqual(n, 2, f"parent={parent} has {n} children")

    def test_outer_cells_above_parent_half_spans(self) -> None:
        """Each outer cell's angular span is one half of its parent inner cell."""
        plan = build_plan()
        inner_by_label = {c.label: c for c in plan.inner_cells}
        for o in plan.outer_cells:
            parent = inner_by_label[o.parent_label]
            mid = (parent.start_angle_deg + parent.end_angle_deg) / 2.0
            # outer cell must coincide with [start, mid] or [mid, end].
            left_match = (
                math.isclose(o.start_angle_deg, parent.start_angle_deg, abs_tol=1e-9)
                and math.isclose(o.end_angle_deg, mid, abs_tol=1e-9)
            )
            right_match = (
                math.isclose(o.start_angle_deg, mid, abs_tol=1e-9)
                and math.isclose(o.end_angle_deg, parent.end_angle_deg, abs_tol=1e-9)
            )
            self.assertTrue(left_match or right_match, f"outer={o.label} parent={parent.label}")

    def test_symbol_per_cell(self) -> None:
        """Each of the 8 inner + 16 outer cells gets one symbol = 24 total."""
        plan = build_plan()
        self.assertEqual(len(plan.symbols), 24)

    def test_symbol_kinds_follow_aspect(self) -> None:
        plan = build_plan()
        cells_by_label = {c.label: c for c in plan.inner_cells}
        cells_by_label.update({o.cell_id: o for o in plan.outer_cells})
        for sym in plan.symbols:
            owner = cells_by_label[sym.cell_id]
            expected = _symbol_kind_of(owner.label)
            self.assertEqual(sym.kind.name, expected, f"cell_id={sym.cell_id}")

    def test_dividers_present(self) -> None:
        plan = build_plan()
        # Ring-divider count is implementation-defined; just require nonzero.
        self.assertGreater(len(plan.dividers), 0)


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
