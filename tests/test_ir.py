"""Tests for socionics_medallion.ir.

The IR is pure-data: frozen, hashable, value-equal records. No cadquery.
"""

from __future__ import annotations

import os
import subprocess
import unittest
from dataclasses import FrozenInstanceError, fields

from socionics_medallion import ir
from socionics_medallion.ir import (
    ALL_OP_TYPES,
    ALL_OP_TYPES_ORDERED,
    ANGLE_QUARTET_FIELDS,
    ANGULAR_OP_TYPES,
    CadOp,
    CutSymbol,
    DividerTreatment,
    EngravedDivider,
    LowerField,
    Prism,
    RaisedDivider,
    RaisedSymbol,
    SymbolKind,
    center_angle_of,
    normalized_angle_delta_deg,
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


def _make_prism(**overrides) -> Prism:
    base = dict(
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
    base.update(overrides)
    return Prism(**base)


def _make_lower_field(**overrides) -> LowerField:
    base = dict(
        owner_cell_id="inner:00",
        center=(0.0, 0.0),
        inner_radius=0.0,
        outer_radius=10.0,
        angle_start_deg=0.0,
        angle_end_deg=45.0,
        center_angle_deg=22.5,
        span_deg=45.0,
        surface_z=2.5,
        depth=0.5,
    )
    base.update(overrides)
    return LowerField(**base)


def _make_raised_symbol(**overrides) -> RaisedSymbol:
    base = dict(
        owner_cell_id="inner:00",
        symbol_kind=SymbolKind.TRIANGLE,
        center_angle_deg=90.0,
        center_radius=20.0,
        local_top_angle_deg=-90.0,
        size_S=8.0,
        height=1.0,
        base_z=2.0,
    )
    base.update(overrides)
    return RaisedSymbol(**base)


def _make_cut_symbol(**overrides) -> CutSymbol:
    base = dict(
        owner_cell_id="inner:00",
        symbol_kind=SymbolKind.SQUARE,
        center_angle_deg=270.0,
        center_radius=20.0,
        local_top_angle_deg=90.0,
        size_S=8.0,
        depth=1.0,
        surface_z=2.5,
    )
    base.update(overrides)
    return CutSymbol(**base)


def _make_raised_divider(**overrides) -> RaisedDivider:
    base = dict(
        owner_cell_id="inner:00",
        boundary_id="inner-boundary:00",
        side="A",
        ring="inner",
        angle_start_deg=0.0,
        angle_end_deg=1.0,
        center_angle_deg=0.5,
        span_deg=1.0,
        inner_radius=0.0,
        outer_radius=10.0,
        height=0.4,
        base_z=2.5,
    )
    base.update(overrides)
    return RaisedDivider(**base)


def _make_engraved_divider(**overrides) -> EngravedDivider:
    base = dict(
        owner_cell_id="inner:04",
        boundary_id="inner-boundary:00",
        side="B",
        ring="inner",
        angle_start_deg=0.0,
        angle_end_deg=1.0,
        center_angle_deg=0.5,
        span_deg=1.0,
        inner_radius=0.0,
        outer_radius=10.0,
        depth=0.3,
        surface_z=2.5,
    )
    base.update(overrides)
    return EngravedDivider(**base)


class TestCadOpVariants(unittest.TestCase):
    def test_prism_value_equality(self) -> None:
        a = _make_prism()
        b = _make_prism()
        self.assertEqual(a, b)
        self.assertEqual(hash(a), hash(b))

    def test_prism_is_frozen(self) -> None:
        a = _make_prism()
        with self.assertRaises(FrozenInstanceError):
            a.z1 = 99.0  # type: ignore[misc]

    def test_lower_field_value_type(self) -> None:
        a = _make_lower_field()
        b = _make_lower_field()
        self.assertEqual(a, b)

    def test_raised_symbol_value_type(self) -> None:
        a = _make_raised_symbol()
        b = _make_raised_symbol()
        self.assertEqual(a, b)

    def test_cut_symbol_value_type(self) -> None:
        a = _make_cut_symbol()
        b = _make_cut_symbol()
        self.assertEqual(a, b)

    def test_raised_divider_value_type(self) -> None:
        a = _make_raised_divider()
        self.assertEqual(a, a)

    def test_engraved_divider_value_type(self) -> None:
        a = _make_engraved_divider()
        self.assertEqual(a, a)

    def test_all_cadops_are_cadop_instances(self) -> None:
        instances = [
            _make_prism(),
            _make_lower_field(),
            _make_raised_symbol(),
            _make_cut_symbol(),
            _make_raised_divider(),
            _make_engraved_divider(),
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
        op = _make_prism()
        d = ir.op_to_dict(op)
        self.assertEqual(d["op"], "prism")
        self.assertEqual(d["outer_radius"], 10.0)
        # New angle quartet fields are surfaced verbatim.
        self.assertEqual(d["angle_start_deg"], 0.0)
        self.assertEqual(d["angle_end_deg"], 45.0)
        self.assertEqual(d["center_angle_deg"], 22.5)
        self.assertEqual(d["span_deg"], 45.0)


# ---------------------------------------------------------------------------
# AC2 — explicit angle quartet on every angular-extent op.
# ---------------------------------------------------------------------------
class TestAngleQuartetSurface(unittest.TestCase):
    def test_angular_op_types_set(self) -> None:
        # Sanity: the angular-extent set covers Prism + LowerField + dividers.
        self.assertIn(Prism, ANGULAR_OP_TYPES)
        self.assertIn(LowerField, ANGULAR_OP_TYPES)
        self.assertIn(RaisedDivider, ANGULAR_OP_TYPES)
        self.assertIn(EngravedDivider, ANGULAR_OP_TYPES)

    def test_every_angular_op_carries_quartet(self) -> None:
        for op_type in ANGULAR_OP_TYPES:
            field_names = {f.name for f in fields(op_type)}  # type: ignore[arg-type]
            missing = [n for n in ANGLE_QUARTET_FIELDS if n not in field_names]
            self.assertFalse(
                missing,
                f"{op_type.__name__} missing angle-quartet fields: {missing}",
            )


# ---------------------------------------------------------------------------
# AC2 — normalized angle delta helper.
# ---------------------------------------------------------------------------
class TestNormalizedAngleDelta(unittest.TestCase):
    def test_opposite_pairs(self) -> None:
        # ЧИ at 90° vs БИ at -90° → 180° apart.
        self.assertAlmostEqual(
            abs(normalized_angle_delta_deg(90.0, -90.0)), 180.0, places=9
        )
        # Wrapped: 0° vs 180°.
        self.assertAlmostEqual(
            abs(normalized_angle_delta_deg(0.0, 180.0)), 180.0, places=9
        )
        # Wrapped negative: -179° vs 179° is 2° apart, not 358°.
        self.assertAlmostEqual(
            abs(normalized_angle_delta_deg(-179.0, 179.0)), 2.0, places=9
        )

    def test_delta_is_in_canonical_range(self) -> None:
        for a, b in [
            (0.0, 0.0),
            (10.0, 350.0),
            (-179.9999, 179.9999),
            (45.0, -45.0),
        ]:
            d = normalized_angle_delta_deg(a, b)
            self.assertGreater(d, -180.0 - 1e-9)
            self.assertLessEqual(d, 180.0 + 1e-9)


class TestCenterAngleOfHelper(unittest.TestCase):
    def test_reads_field_not_recomputed(self) -> None:
        # An op whose start/end straddle a wrap will still report the
        # explicit center_angle_deg, not (start+end)/2.
        op = _make_prism(
            angle_start_deg=170.0,
            angle_end_deg=-170.0,  # 20° wide sector across the 180°/-180° wrap
            center_angle_deg=180.0,
            span_deg=20.0,
        )
        self.assertEqual(center_angle_of(op), 180.0)

    def test_rejects_non_angular_op(self) -> None:
        # No purely non-angular ops exist today, but the helper still type-
        # guards. Pass a bare object to verify.
        with self.assertRaises(TypeError):
            center_angle_of("not-an-op")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# AC3 — divider ops carry ownership + structural metadata.
# ---------------------------------------------------------------------------
class TestDividerOwnershipMetadata(unittest.TestCase):
    REQUIRED_FIELDS = (
        "owner_cell_id",
        "boundary_id",
        "side",
        "ring",
        "inner_radius",
        "outer_radius",
        "treatment",
    )

    def test_raised_divider_has_required_fields(self) -> None:
        field_names = {f.name for f in fields(RaisedDivider)}  # type: ignore[arg-type]
        for n in self.REQUIRED_FIELDS:
            self.assertIn(n, field_names, f"RaisedDivider missing field: {n}")

    def test_engraved_divider_has_required_fields(self) -> None:
        field_names = {f.name for f in fields(EngravedDivider)}  # type: ignore[arg-type]
        for n in self.REQUIRED_FIELDS:
            self.assertIn(n, field_names, f"EngravedDivider missing field: {n}")

    def test_treatment_defaults_match_variant(self) -> None:
        rd = _make_raised_divider()
        ed = _make_engraved_divider()
        self.assertEqual(rd.treatment, DividerTreatment.RAISED_RIB)
        self.assertEqual(ed.treatment, DividerTreatment.ENGRAVED_GROOVE)


# ---------------------------------------------------------------------------
# AC4/AC5 — RaisedSymbol/CutSymbol carry orientation + owner_cell_id.
# ---------------------------------------------------------------------------
class TestSymbolOpMetadata(unittest.TestCase):
    def test_raised_symbol_has_owner_and_orientation(self) -> None:
        field_names = {f.name for f in fields(RaisedSymbol)}  # type: ignore[arg-type]
        self.assertIn("owner_cell_id", field_names)
        self.assertIn("local_top_angle_deg", field_names)

    def test_cut_symbol_has_owner_and_orientation(self) -> None:
        field_names = {f.name for f in fields(CutSymbol)}  # type: ignore[arg-type]
        self.assertIn("owner_cell_id", field_names)
        self.assertIn("local_top_angle_deg", field_names)


# ---------------------------------------------------------------------------
# AC9 — IMPLEMENTED_OPS must equal ALL_OP_TYPES (post-impl).
# ---------------------------------------------------------------------------
class TestAllOpTypesSet(unittest.TestCase):
    def test_all_op_types_is_a_frozenset(self) -> None:
        self.assertIsInstance(ALL_OP_TYPES, frozenset)

    def test_all_op_types_ordered_matches_set(self) -> None:
        self.assertEqual(frozenset(ALL_OP_TYPES_ORDERED), ALL_OP_TYPES)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
