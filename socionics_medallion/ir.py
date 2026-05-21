"""Pure-data instruction IR for the medallion compiler.

This module MUST NOT import cadquery (or any CAD toolchain). Each CadOp is a
frozen, hashable, equality-comparable value type. Variants are discriminated
by their concrete dataclass type — and additionally tagged with an ``op`` field
in their dict serialization so the stub executor and golden file are stable.

Angle conventions
-----------------
Angles are degrees; IR angles MAY be unwrapped in (-180, 180]. Consumers MUST
NOT reinterpret ordering semantically from unwrapped intervals.

Every op with an angular extent surfaces the **explicit angle quartet**:

* ``angle_start_deg`` — start of the sector arc
* ``angle_end_deg``   — end of the sector arc (CCW from start)
* ``center_angle_deg`` — the angle at the centroid of the arc (already
  resolved by the compiler; consumers MUST NOT recompute it from
  ``(start + end) / 2``)
* ``span_deg``         — total angular extent of the arc (always positive)

Opposite checks MUST use the normalized angular delta provided by
:func:`normalized_angle_delta_deg`, not raw subtraction.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, fields
from typing import Tuple


class SymbolKind(enum.Enum):
    SQUARE = "SQUARE"
    CIRCLE = "CIRCLE"
    TRIANGLE = "TRIANGLE"
    ETHICS = "ETHICS"


class DividerTreatment(enum.Enum):
    RAISED_RIB = "raised_rib"
    ENGRAVED_GROOVE = "engraved_groove"


class CadOp:
    """Marker base class for the sealed set of instruction variants.

    Concrete variants subclass via dataclass inheritance with ``slots=True``
    and ``frozen=True``. Equality is structural via the dataclass machinery.
    """

    __slots__ = ()


# ---------------------------------------------------------------------------
# Sector geometry primitives.
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class Prism(CadOp):
    """A sector prism (the unit cell of the medallion).

    The sector is the planar wedge between two radii at the given inner/outer
    radius, swept from ``angle_start_deg`` to ``angle_end_deg`` (CCW),
    extruded from z=z0 up to z=z1.
    """

    center: Tuple[float, float]
    inner_radius: float
    outer_radius: float
    angle_start_deg: float
    angle_end_deg: float
    center_angle_deg: float
    span_deg: float
    z0: float
    z1: float


@dataclass(frozen=True, slots=True)
class LowerField(CadOp):
    """Subtract a sector slab from a cell's top surface to create a lowered
    (black-polarity) field. The lowered field's top sits at
    ``surface_z - depth``.
    """

    owner_cell_id: str
    center: Tuple[float, float]
    inner_radius: float
    outer_radius: float
    angle_start_deg: float
    angle_end_deg: float
    center_angle_deg: float
    span_deg: float
    surface_z: float
    depth: float


# ---------------------------------------------------------------------------
# Symbol geometry (black raised / white cut).
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class RaisedSymbol(CadOp):
    """A black-polarity aspect symbol raised from its lowered field.

    ``local_top_angle_deg`` is the world-frame angle (degrees) of the symbol's
    local +Y axis (the "top" of the symbol). For a medallion symbol it points
    radially inward toward the medallion center.
    """

    owner_cell_id: str
    symbol_kind: SymbolKind
    center_angle_deg: float
    center_radius: float
    local_top_angle_deg: float
    size_S: float
    height: float
    base_z: float


@dataclass(frozen=True, slots=True)
class CutSymbol(CadOp):
    """A white-polarity aspect symbol carved down into the surface."""

    owner_cell_id: str
    symbol_kind: SymbolKind
    center_angle_deg: float
    center_radius: float
    local_top_angle_deg: float
    size_S: float
    depth: float
    surface_z: float


# ---------------------------------------------------------------------------
# Divider geometry.
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class RaisedDivider(CadOp):
    """A rib protruding above a black-polarity field.

    Each divider op carries full ownership + structural metadata per the
    operator's 2026-05-21 AC6 supersession (see issue #3 §AC3).
    """

    owner_cell_id: str
    boundary_id: str
    side: str  # 'A' or 'B' — which adjacent cell of the boundary owns this op
    ring: str  # 'inner' | 'outer'
    angle_start_deg: float
    angle_end_deg: float
    center_angle_deg: float
    span_deg: float
    inner_radius: float
    outer_radius: float
    height: float
    base_z: float
    treatment: DividerTreatment = DividerTreatment.RAISED_RIB


@dataclass(frozen=True, slots=True)
class EngravedDivider(CadOp):
    """A groove cut into a white-polarity surface.

    Each divider op carries full ownership + structural metadata per the
    operator's 2026-05-21 AC6 supersession (see issue #3 §AC3).
    """

    owner_cell_id: str
    boundary_id: str
    side: str  # 'A' or 'B' — which adjacent cell of the boundary owns this op
    ring: str  # 'inner' | 'outer'
    angle_start_deg: float
    angle_end_deg: float
    center_angle_deg: float
    span_deg: float
    inner_radius: float
    outer_radius: float
    depth: float
    surface_z: float
    treatment: DividerTreatment = DividerTreatment.ENGRAVED_GROOVE


# ---------------------------------------------------------------------------
# Op-name discriminator + dict serialization.
# ---------------------------------------------------------------------------
_OP_NAMES: dict[type, str] = {
    Prism: "prism",
    LowerField: "lower_field",
    RaisedSymbol: "raised_symbol",
    CutSymbol: "cut_symbol",
    RaisedDivider: "raised_divider",
    EngravedDivider: "engraved_divider",
}

ALL_OP_TYPES_ORDERED: tuple[type, ...] = tuple(_OP_NAMES.keys())
ALL_OP_TYPES: frozenset = frozenset(_OP_NAMES.keys())

# Set of op variants that carry an angular extent (and therefore must surface
# the explicit angle quartet). This is referenced by schema tests.
ANGULAR_OP_TYPES: tuple[type, ...] = (
    Prism,
    LowerField,
    RaisedDivider,
    EngravedDivider,
)

# Required angular-extent fields per AC2.
ANGLE_QUARTET_FIELDS: tuple[str, ...] = (
    "angle_start_deg",
    "angle_end_deg",
    "center_angle_deg",
    "span_deg",
)


def op_name(op: CadOp) -> str:
    """Return the stable discriminator string for an op instance."""
    try:
        return _OP_NAMES[type(op)]
    except KeyError as exc:  # pragma: no cover - defensive
        raise TypeError(f"Unknown CadOp variant: {type(op).__name__}") from exc


def _coerce(value: object) -> object:
    if isinstance(value, enum.Enum):
        return value.name
    if isinstance(value, tuple):
        return [_coerce(v) for v in value]
    return value


def op_to_dict(op: CadOp) -> dict:
    """Serialize a CadOp to a JSON-friendly dict.

    Keys: ``op`` (discriminator) + every dataclass field in declaration
    order. Enums are serialized by ``name``; tuples become lists.
    """
    out: dict = {"op": op_name(op)}
    for f in fields(op):  # type: ignore[arg-type]
        out[f.name] = _coerce(getattr(op, f.name))
    return out


# ---------------------------------------------------------------------------
# Angle helpers.
# ---------------------------------------------------------------------------
def normalized_angle_delta_deg(a_deg: float, b_deg: float) -> float:
    """Return the smallest signed angular delta from ``b`` to ``a`` in (-180, 180].

    Use this for opposite-pair checks: opposing cells satisfy
    ``abs(normalized_angle_delta_deg(a, b)) == 180``.
    """
    return ((a_deg - b_deg + 540.0) % 360.0) - 180.0


def center_angle_of(op: CadOp) -> float:
    """Return the resolved center angle of an angular op.

    Reads :attr:`center_angle_deg` directly. Never recomputes from
    ``(start + end) / 2`` — that would break wrap-around cases.
    """
    if not isinstance(op, ANGULAR_OP_TYPES):
        raise TypeError(
            f"center_angle_of() requires an angular-extent op; got {type(op).__name__}"
        )
    return float(getattr(op, "center_angle_deg"))
