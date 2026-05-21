"""Tests for socionics_medallion.ir.

The IR is pure-data: frozen, hashable, value-equal records. No cadquery.
"""

from __future__ import annotations

import os
import subprocess
import unittest
from dataclasses import FrozenInstanceError

from socionics_medallion import ir
from socionics_medallion.ir import (
    CadOp,
    CutSymbol,
    EngravedDivider,
    LowerField,
    Prism,
    RaisedDivider,
    RaisedSymbol,
    SymbolKind,
)


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestIRImportPurity(unittest.TestCase):
    def test_no_cadquery_after_import(self) -> None:
        result = subprocess.run(
            [
                "python3",
                "-c",
                "import sys; import socionics_medallion.ir; "
                "assert 'cadquery' not in sys.modules, sorted(sys.modules)",
            ],
            cwd=_repo_root(),
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode, 0, msg=result.stdout + "\n" + result.stderr
        )


class TestCadOpVariants(unittest.TestCase):
    def test_prism_value_equality(self) -> None:
        a = Prism(
            center=(0.0, 0.0),
            inner_radius=0.0,
            outer_radius=10.0,
            start_angle_deg=0.0,
            end_angle_deg=45.0,
            z0=0.0,
            z1=2.5,
        )
        b = Prism(
            center=(0.0, 0.0),
            inner_radius=0.0,
            outer_radius=10.0,
            start_angle_deg=0.0,
            end_angle_deg=45.0,
            z0=0.0,
            z1=2.5,
        )
        self.assertEqual(a, b)
        self.assertEqual(hash(a), hash(b))

    def test_prism_is_frozen(self) -> None:
        a = Prism(
            center=(0.0, 0.0),
            inner_radius=0.0,
            outer_radius=10.0,
            start_angle_deg=0.0,
            end_angle_deg=45.0,
            z0=0.0,
            z1=2.5,
        )
        with self.assertRaises(FrozenInstanceError):
            a.z1 = 99.0  # type: ignore[misc]

    def test_lower_field_value_type(self) -> None:
        a = LowerField(
            center=(0.0, 0.0),
            inner_radius=0.0,
            outer_radius=10.0,
            start_angle_deg=0.0,
            end_angle_deg=45.0,
            surface_z=2.5,
            depth=0.5,
        )
        b = LowerField(
            center=(0.0, 0.0),
            inner_radius=0.0,
            outer_radius=10.0,
            start_angle_deg=0.0,
            end_angle_deg=45.0,
            surface_z=2.5,
            depth=0.5,
        )
        self.assertEqual(a, b)

    def test_raised_symbol_value_type(self) -> None:
        a = RaisedSymbol(
            symbol_kind=SymbolKind.TRIANGLE,
            center_angle_deg=90.0,
            center_radius=20.0,
            size_S=8.0,
            height=1.0,
            base_z=2.0,
        )
        b = RaisedSymbol(
            symbol_kind=SymbolKind.TRIANGLE,
            center_angle_deg=90.0,
            center_radius=20.0,
            size_S=8.0,
            height=1.0,
            base_z=2.0,
        )
        self.assertEqual(a, b)

    def test_cut_symbol_value_type(self) -> None:
        a = CutSymbol(
            symbol_kind=SymbolKind.SQUARE,
            center_angle_deg=270.0,
            center_radius=20.0,
            size_S=8.0,
            depth=1.0,
            surface_z=2.5,
        )
        b = CutSymbol(
            symbol_kind=SymbolKind.SQUARE,
            center_angle_deg=270.0,
            center_radius=20.0,
            size_S=8.0,
            depth=1.0,
            surface_z=2.5,
        )
        self.assertEqual(a, b)

    def test_raised_divider_value_type(self) -> None:
        a = RaisedDivider(
            start_angle_deg=0.0,
            end_angle_deg=1.0,
            inner_radius=0.0,
            outer_radius=10.0,
            height=0.4,
            base_z=2.5,
        )
        self.assertEqual(a, a)

    def test_engraved_divider_value_type(self) -> None:
        a = EngravedDivider(
            start_angle_deg=0.0,
            end_angle_deg=1.0,
            inner_radius=0.0,
            outer_radius=10.0,
            depth=0.3,
            surface_z=2.5,
        )
        self.assertEqual(a, a)

    def test_all_cadops_are_cadop_instances(self) -> None:
        instances = [
            Prism(
                center=(0.0, 0.0),
                inner_radius=0.0,
                outer_radius=10.0,
                start_angle_deg=0.0,
                end_angle_deg=45.0,
                z0=0.0,
                z1=2.5,
            ),
            LowerField(
                center=(0.0, 0.0),
                inner_radius=0.0,
                outer_radius=10.0,
                start_angle_deg=0.0,
                end_angle_deg=45.0,
                surface_z=2.5,
                depth=0.5,
            ),
            RaisedSymbol(
                symbol_kind=SymbolKind.TRIANGLE,
                center_angle_deg=90.0,
                center_radius=20.0,
                size_S=8.0,
                height=1.0,
                base_z=2.0,
            ),
            CutSymbol(
                symbol_kind=SymbolKind.SQUARE,
                center_angle_deg=270.0,
                center_radius=20.0,
                size_S=8.0,
                depth=1.0,
                surface_z=2.5,
            ),
            RaisedDivider(
                start_angle_deg=0.0,
                end_angle_deg=1.0,
                inner_radius=0.0,
                outer_radius=10.0,
                height=0.4,
                base_z=2.5,
            ),
            EngravedDivider(
                start_angle_deg=0.0,
                end_angle_deg=1.0,
                inner_radius=0.0,
                outer_radius=10.0,
                depth=0.3,
                surface_z=2.5,
            ),
        ]
        for op in instances:
            self.assertIsInstance(op, CadOp)


class TestSymbolKind(unittest.TestCase):
    def test_members(self) -> None:
        self.assertEqual(
            {k.name for k in SymbolKind},
            {"SQUARE", "CIRCLE", "TRIANGLE", "ETHICS"},
        )


class TestIRSerialization(unittest.TestCase):
    def test_to_dict_present(self) -> None:
        op = Prism(
            center=(0.0, 0.0),
            inner_radius=0.0,
            outer_radius=10.0,
            start_angle_deg=0.0,
            end_angle_deg=45.0,
            z0=0.0,
            z1=2.5,
        )
        d = ir.op_to_dict(op)
        self.assertEqual(d["op"], "prism")
        self.assertEqual(d["outer_radius"], 10.0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
